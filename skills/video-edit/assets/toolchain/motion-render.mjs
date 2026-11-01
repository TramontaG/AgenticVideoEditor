import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";
import { createServer } from "vite";
import motionCanvasModule from "@motion-canvas/vite-plugin";
import puppeteer from "puppeteer-core";
import { ensureBrowser } from "@remotion/renderer";
import { createAnimationOutput } from "./motion/output.mjs";

const tools = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
if (!args[0] || !/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(args[1] || ""))
  throw new Error(
    "Usage: node motion-render.mjs <project> <asset-id> [--width 1920 --height 1080 --fps 30 --duration 2 --format webm|png --crf 18]",
  );
const project = path.resolve(args[0]),
  assetId = args[1];
const option = (name, fallback) =>
  args.includes(name) ? Number(args[args.indexOf(name) + 1]) : fallback;
const width = option("--width", 1920),
  height = option("--height", 1080),
  fps = option("--fps", 30),
  duration = option("--duration", 2);
if (![width, height, fps, duration].every((n) => Number.isFinite(n) && n > 0))
  throw new Error("Dimensions, FPS and duration must be positive");
const frameCount = Math.round(duration * fps);
const format = args.includes("--format")
  ? args[args.indexOf("--format") + 1]
  : "webm";
const crf = option("--crf", 18);
if (!["webm", "png"].includes(format))
  throw new Error("Use --format webm or png");
if (!Number.isInteger(crf) || crf < 0 || crf > 63)
  throw new Error("CRF must be an integer from 0 to 63");
if (frameCount < 1 || !Number.isInteger(width) || !Number.isInteger(height))
  throw new Error("Use integer dimensions and at least one frame");
const source = path.join(project, "motion", assetId),
  output = path.join(project, "public/motion", assetId);
await fs.mkdir(source, { recursive: true });
for (const name of ["scene.tsx", "project.ts"]) {
  try {
    await fs.copyFile(
      path.join(tools, "motion", name),
      path.join(source, name),
      2,
    );
  } catch (e) {
    if (e.code !== "EEXIST") throw e;
  }
}
// Let Vite resolve imports for project sources outside tools without symlinks or global installation.
const aliases = Object.fromEntries(
  ["core", "2d"].map((name) => [
    `@motion-canvas/${name}`,
    path.join(tools, "node_modules/@motion-canvas", name),
  ]),
);
async function hashDirectory(dir, hash) {
  for (const entry of (await fs.readdir(dir, { withFileTypes: true })).sort(
    (a, b) => a.name.localeCompare(b.name),
  )) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) await hashDirectory(full, hash);
    else
      hash.update(path.relative(source, full)).update(await fs.readFile(full));
  }
}
async function getFingerprint() {
  const hash = crypto
    .createHash("sha256")
    .update(JSON.stringify({ width, height, fps, duration, format, crf }));
  await hashDirectory(source, hash);
  hash.update(await fs.readFile(path.join(tools, "package-lock.json")));
  hash.update(await fs.readFile(fileURLToPath(import.meta.url)));
  hash.update(await fs.readFile(path.join(tools, "motion/output.mjs")));
  return hash.digest("hex");
}
const fingerprint = await getFingerprint();
const cacheFile = path.join(output, "render.json");
try {
  const cached = JSON.parse(await fs.readFile(cacheFile, "utf8"));
  if (cached.fingerprint === fingerprint) {
    if (format === "webm") {
      const info = await fs.stat(path.join(project, "public", cached.src));
      if (!info.isFile() || info.size !== cached.bytes)
        throw new Error("Cached video is incomplete");
    } else {
      for (let f = 0; f < frameCount; f++)
        await fs.access(
          path.join(
            project,
            "public",
            cached.src,
            String(f).padStart(6, "0") + ".png",
          ),
        );
    }
    console.log(JSON.stringify({ ...cached, cached: true }));
    process.exit(0);
  }
} catch (e) {
  if (e.code !== "ENOENT")
    console.warn("Animation cache will be rebuilt:", e.message);
}
await fs.mkdir(output, { recursive: true });
const modulePath =
  "/@fs/" + path.join(source, "project.ts").replaceAll("\\", "/");
const motionCanvas = motionCanvasModule.default ?? motionCanvasModule;
const server = await createServer({
  root: tools,
  configFile: false,
  logLevel: "error",
  resolve: { alias: aliases },
  plugins: [motionCanvas({ project: path.join(source, "project.ts"), output })],
  server: {
    host: "127.0.0.1",
    port: 0,
    hmr: false,
    fs: { allow: [tools, project] },
  },
  optimizeDeps: {
    noDiscovery: true,
    entries: [
      path.join(tools, "motion/runtime.ts"),
      path.join(source, "project.ts"),
    ],
    include: [
      "@motion-canvas/core",
      "@motion-canvas/2d",
      "@motion-canvas/2d/lib/jsx-runtime",
      "chroma-js",
    ],
  },
});
let browser;
let animationOutput;
try {
  animationOutput = await createAnimationOutput({
    directory: output,
    width,
    height,
    fps,
    frameCount,
    format,
    crf,
  });
  server.middlewares.use((req, res, next) => {
    if (req.url === "/agent.html") {
      res.setHeader("Content-Type", "text/html");
      res.end("<!doctype html><html><body></body></html>");
    } else next();
  });
  await server.listen();
  let executablePath = process.env.AI_EDITOR_BROWSER;
  if (!executablePath) {
    const status = await ensureBrowser({});
    executablePath = status.path;
    if (!executablePath)
      throw new Error("Browser path unavailable; set AI_EDITOR_BROWSER");
  }
  browser = await puppeteer.launch({
    executablePath,
    headless: true,
    args: ["--disable-dev-shm-usage"],
  });
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.error("Motion Canvas:", e.message));
  await page.exposeFunction("saveFrame", async (index, data) => {
    if (index < frameCount)
      await animationOutput.writeFrame(
        index,
        Buffer.from(data.split(",")[1], "base64"),
      );
  });
  const address = server.httpServer.address();
  await page.goto(`http://127.0.0.1:${address.port}/agent.html`);
  const corePath = "/motion/runtime.ts";
  const result = await page.evaluate(
    async ({
      modulePath,
      corePath,
      width,
      height,
      fps,
      duration,
      frameCount,
    }) => {
      const core = await import(corePath);
      const project = (await import(modulePath + "?project")).default;
      const errors = [];
      project.logger.onLogged.subscribe((log) => {
        if (log.level === "error") errors.push(String(log.message));
      });
      const exporter = {
        id: "agent-png",
        displayName: "Agent PNG",
        async create() {
          return {
            async handleFrame(canvas, frame) {
              if (frame < frameCount)
                await window.saveFrame(frame, canvas.toDataURL("image/png"));
            },
          };
        },
      };
      project.meta.rendering.exporter.exporters.push(exporter);
      const renderer = new core.Renderer(project);
      let status = null;
      renderer.onFinished.subscribe((value) => {
        status = value;
      });
      await renderer.render({
        name: "asset",
        size: new core.Vector2(width, height),
        resolutionScale: 1,
        colorSpace: "srgb",
        background: null,
        fps,
        range: [0, (frameCount - 1) / fps],
        exporter: { name: "agent-png", options: {} },
      });
      return { status, errors };
    },
    { modulePath, corePath, width, height, fps, duration, frameCount },
  );
  if (result.status !== 0)
    throw new Error("Motion Canvas render failed: " + JSON.stringify(result));
  const encoded = await animationOutput.finish();
  const src = `motion/${assetId}/${encoded.file}`;
  const clip =
    format === "webm"
      ? { type: "video", src, transparent: true, volume: 0 }
      : { type: "frames", src, frameCount, framePattern: "%06d.png" };
  const record = {
    assetId,
    fingerprint: await getFingerprint(),
    width,
    height,
    fps,
    frameCount,
    ...encoded,
    src,
    clip,
  };
  const temporaryMetadata = cacheFile + ".tmp";
  await fs.writeFile(temporaryMetadata, JSON.stringify(record, null, 2));
  await fs.rename(temporaryMetadata, cacheFile);
  console.log(JSON.stringify(record));
} finally {
  try {
    await browser?.close();
  } finally {
    try {
      await server.close();
    } finally {
      await animationOutput?.abort();
    }
  }
}
