import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { execFile } from "node:child_process";
import { promisify, parseArgs } from "node:util";
import crypto from "node:crypto";
import puppeteer from "puppeteer-core";

const exec = promisify(execFile);
const tools = path.dirname(fileURLToPath(import.meta.url));

async function browserPath(explicit) {
  if (explicit || process.env.AI_EDITOR_BROWSER)
    return path.resolve(explicit || process.env.AI_EDITOR_BROWSER);
  // Resolve Remotion's browser cache relative to the toolchain, not the caller's directory.
  const { stdout } = await exec(
    process.execPath,
    [
      "--input-type=module",
      "-e",
      "import {ensureBrowser} from '@remotion/renderer'; const status=await ensureBrowser({logLevel:'error'}); console.log(JSON.stringify(status));",
    ],
    { cwd: tools, maxBuffer: 1024 * 1024 },
  );
  const status = JSON.parse(stdout);
  if (!status.path)
    throw new Error(
      "No browser available. Run setup.py install or set AI_EDITOR_BROWSER.",
    );
  return status.path;
}

export async function capturePage({
  project,
  assetId,
  url,
  width = 1920,
  height = 1080,
  scale = 1,
  fullPage = false,
  selector,
  waitFor,
  waitMs = 0,
  timeoutMs = 30000,
  scroll = false,
  format = "png",
  quality = 90,
  transparent = false,
  browserExecutable,
}) {
  project = path.resolve(project);
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]*$/.test(assetId || ""))
    throw new Error("Use a simple asset ID.");
  const address = new URL(url);
  if (!["http:", "https:"].includes(address.protocol))
    throw new Error("Use an HTTP or HTTPS URL (localhost is supported).");
  if (address.username || address.password)
    throw new Error("URLs containing login credentials are not supported.");
  if (fullPage && selector)
    throw new Error("Choose full-page or a selector, not both.");
  if (
    ![width, height, timeoutMs].every((n) => Number.isInteger(n) && n > 0) ||
    !Number.isFinite(scale) ||
    scale < 1 ||
    scale > 4
  )
    throw new Error(
      "Use positive integer dimensions/timeouts and a scale from 1 to 4.",
    );
  if (!Number.isInteger(waitMs) || waitMs < 0 || waitMs > 10000)
    throw new Error("wait-ms must be between 0 and 10000.");
  if (
    !["png", "jpeg", "webp"].includes(format) ||
    !Number.isInteger(quality) ||
    quality < 1 ||
    quality > 100
  )
    throw new Error("Use png, jpeg or webp, with quality between 1 and 100.");
  if (transparent && format === "jpeg")
    throw new Error("JPEG does not support transparency; use PNG or WebP.");
  const manifestFile = path.join(project, "project.json");
  const manifest = JSON.parse(await fs.readFile(manifestFile, "utf8"));
  const id = `web-${assetId}`;
  if (
    !Array.isArray(manifest.assets) ||
    manifest.assets.some((asset) => asset.id === id)
  )
    throw new Error(
      "Asset ID already exists or project registry is invalid; choose a new ID.",
    );
  const parent = path.join(project, "public/web");
  const output = path.join(parent, assetId);
  try {
    await fs.access(output);
    throw new Error("Capture already exists; choose a new asset ID.");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  await fs.mkdir(parent, { recursive: true });
  const staging = await fs.mkdtemp(path.join(parent, ".capture-"));
  let browser;
  let published = false;
  let registryLock;
  const registryLockFile = path.join(project, ".web-capture.lock");
  try {
    browser = await puppeteer.launch({
      executablePath: await browserPath(browserExecutable),
      headless: true,
      args: ["--disable-dev-shm-usage"],
    });
    const page = await browser.newPage();
    await page.setViewport({ width, height, deviceScaleFactor: scale });
    page.setDefaultTimeout(timeoutMs);
    page.setDefaultNavigationTimeout(timeoutMs);
    await page.emulateMediaFeatures([
      { name: "prefers-reduced-motion", value: "reduce" },
    ]);
    const response = await page.goto(address.href, {
      waitUntil: "domcontentloaded",
    });
    if (!response || response.status() >= 400)
      throw new Error(
        `Page returned HTTP ${response?.status() ?? "no response"}.`,
      );
    if (waitFor) await page.waitForSelector(waitFor, { visible: true });
    const warnings = [];
    let scrollLimitReached = false;
    if (scroll || fullPage) {
      scrollLimitReached = await page.evaluate(async () => {
        for (let index = 0; index < 20; index++) {
          if (
            window.scrollY + window.innerHeight >=
            document.documentElement.scrollHeight
          )
            break;
          window.scrollBy(0, Math.max(1, Math.floor(window.innerHeight * 0.8)));
          await new Promise((resolve) =>
            requestAnimationFrame(() => requestAnimationFrame(resolve)),
          );
        }
        const limited =
          window.scrollY + window.innerHeight <
          document.documentElement.scrollHeight;
        window.scrollTo(0, 0);
        return limited;
      });
      if (scrollLimitReached)
        warnings.push(
          "Auto-scroll reached its 20-step limit; check lazy-loaded content.",
        );
    }
    if (selector) {
      const element = await page.waitForSelector(selector, { visible: true });
      await element.scrollIntoView();
    }
    try {
      await page.waitForNetworkIdle({
        idleTime: 300,
        timeout: Math.min(timeoutMs, 3000),
      });
    } catch {
      warnings.push("Network did not become idle; review dynamic content.");
    }
    const fontsReady = await page.evaluate(
      async (timeout) =>
        Promise.race([
          document.fonts.ready.then(() => true),
          new Promise((resolve) => setTimeout(() => resolve(false), timeout)),
        ]),
      Math.min(timeoutMs, 3000),
    );
    if (!fontsReady)
      warnings.push("Fonts did not finish loading before capture.");
    if (waitMs) await new Promise((resolve) => setTimeout(resolve, waitMs));
    const extension = format === "jpeg" ? "jpg" : format;
    const filename = `capture.${extension}`;
    const imageFile = path.join(staging, filename);
    const screenshot = {
      path: imageFile,
      type: format,
      omitBackground: transparent,
      ...(format === "png" ? {} : { quality }),
    };
    if (selector) {
      const element = await page.waitForSelector(selector, { visible: true });
      await element.screenshot(screenshot);
    } else await page.screenshot({ ...screenshot, fullPage });
    const { stdout } = await exec(process.env.AI_EDITOR_FFPROBE || "ffprobe", [
      "-v",
      "error",
      "-select_streams",
      "v:0",
      "-show_entries",
      "stream=width,height",
      "-of",
      "json",
      imageFile,
    ]);
    const dimensions = JSON.parse(stdout).streams?.[0];
    if (!dimensions?.width || !dimensions?.height)
      throw new Error("Captured image dimensions could not be verified.");
    const bytes = await fs.readFile(imageFile);
    const sha256 = crypto.createHash("sha256").update(bytes).digest("hex");
    const src = `web/${assetId}/${filename}`;
    const metadataSrc = `web/${assetId}/capture.json`;
    const record = {
      version: 1,
      id,
      kind: "web-screenshot",
      src,
      metadataSrc,
      sha256,
      bytes: bytes.length,
      sourceUrl: address.href,
      finalUrl: page.url(),
      title: await page.title(),
      capturedAt: new Date().toISOString(),
      viewport: { width, height, deviceScaleFactor: scale },
      width: dimensions.width,
      height: dimensions.height,
      options: {
        fullPage,
        selector: selector ?? null,
        waitFor: waitFor ?? null,
        waitMs,
        timeoutMs,
        scroll,
        format,
        quality: format === "png" ? null : quality,
        transparent,
      },
      warnings,
      clip: { type: "image", src, objectFit: "contain" },
    };
    await fs.writeFile(
      path.join(staging, "capture.json"),
      JSON.stringify(record, null, 2),
    );
    // Prevent simultaneous captures from silently overwriting each other's registry updates.
    try {
      registryLock = await fs.open(registryLockFile, "wx");
    } catch (error) {
      if (error.code === "EEXIST")
        throw new Error(
          "Another capture is updating this project; retry sequentially.",
        );
      throw error;
    }
    // Read again so sequential captures do not discard earlier registered assets.
    const latest = JSON.parse(await fs.readFile(manifestFile, "utf8"));
    if (latest.assets.some((asset) => asset.id === id))
      throw new Error(
        "Asset ID was registered during capture; choose a new ID.",
      );
    latest.assets.push({
      id,
      name: filename,
      kind: record.kind,
      src,
      sha256,
      width: record.width,
      height: record.height,
      metadataSrc,
    });
    await fs.rename(staging, output);
    published = true;
    const temporaryManifest = manifestFile + ".capture-" + crypto.randomUUID();
    try {
      await fs.writeFile(
        temporaryManifest,
        JSON.stringify(latest, null, 2) + "\n",
      );
      await fs.rename(temporaryManifest, manifestFile);
    } finally {
      await fs.rm(temporaryManifest, { force: true });
    }
    return record;
  } catch (error) {
    if (published) await fs.rm(output, { recursive: true, force: true });
    throw error;
  } finally {
    try {
      if (registryLock) {
        await registryLock.close();
        await fs.rm(registryLockFile, { force: true });
      }
    } finally {
      try {
        await browser?.close();
      } finally {
        await fs.rm(staging, { recursive: true, force: true });
      }
    }
  }
}

async function main() {
  const { values, positionals } = parseArgs({
    allowPositionals: true,
    options: {
      help: { type: "boolean" },
      width: { type: "string" },
      height: { type: "string" },
      scale: { type: "string" },
      "full-page": { type: "boolean" },
      selector: { type: "string" },
      "wait-for": { type: "string" },
      "wait-ms": { type: "string" },
      "timeout-ms": { type: "string" },
      scroll: { type: "boolean" },
      format: { type: "string" },
      quality: { type: "string" },
      transparent: { type: "boolean" },
    },
  });
  if (values.help) {
    console.log(
      "node capture-page.mjs <project> <asset-id> <url> [--full-page | --selector CSS] [--width 1920 --height 1080 --scale 2] [--wait-for CSS --wait-ms 500 --scroll] [--format png|jpeg|webp --quality 90 --transparent]",
    );
    return;
  }
  if (positionals.length !== 3)
    throw new Error(
      "Expected project, asset ID and URL. Use --help for options.",
    );
  const result = await capturePage({
    project: positionals[0],
    assetId: positionals[1],
    url: positionals[2],
    width: Number(values.width ?? 1920),
    height: Number(values.height ?? 1080),
    scale: Number(values.scale ?? 1),
    fullPage: values["full-page"] ?? false,
    selector: values.selector,
    waitFor: values["wait-for"],
    waitMs: Number(values["wait-ms"] ?? 0),
    timeoutMs: Number(values["timeout-ms"] ?? 30000),
    scroll: values.scroll ?? false,
    format: values.format ?? "png",
    quality: Number(values.quality ?? 90),
    transparent: values.transparent ?? false,
  });
  console.log(JSON.stringify(result, null, 2));
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href
) {
  main().catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  });
}
