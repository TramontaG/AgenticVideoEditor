import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { selectComposition, renderMedia } from "@remotion/renderer";

const tools = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
if (!args[0])
  throw new Error(
    "Usage: node render.mjs <project> [--preview] [--output file.mp4]",
  );
const project = path.resolve(args[0]);
const manifest = JSON.parse(
  await fs.readFile(path.join(project, "timeline/manifest.json"), "utf8"),
);
for (const key of ["width", "height", "fps", "durationInFrames"]) {
  if (!Number.isInteger(manifest[key]) || manifest[key] <= 0)
    throw new Error(`Invalid ${key}`);
}
const ids = new Set();
for (const clip of manifest.clips) {
  if (ids.has(clip.id) || !clip.id)
    throw new Error("Clip IDs must be unique and nonempty");
  ids.add(clip.id);
  if (!["image", "video", "audio", "frames", "title"].includes(clip.type))
    throw new Error(`Unknown clip type ${clip.type}`);
  if (
    !Number.isInteger(clip.from) ||
    clip.from < 0 ||
    !Number.isInteger(clip.durationInFrames) ||
    clip.durationInFrames < 1 ||
    clip.from + clip.durationInFrames > manifest.durationInFrames
  )
    throw new Error(`Invalid timing: ${clip.id}`);
  if (clip.type !== "title") {
    if (
      !clip.src ||
      path.isAbsolute(clip.src) ||
      clip.src.split(/[\\/]/).includes("..")
    )
      throw new Error(`Invalid media path: ${clip.id}`);
    await fs.access(path.join(project, "public", clip.src));
  }
}
const preview = args.includes("--preview");
const outIndex = args.indexOf("--output");
const stamp = new Date().toISOString().replace(/[:.]/g, "-");
const outputLocation =
  outIndex >= 0
    ? path.resolve(args[outIndex + 1])
    : path.join(
        project,
        "exports",
        `${preview ? "preview" : "final"}-${stamp}.mp4`,
      );
try {
  await fs.access(outputLocation);
  throw new Error("Output exists; choose a new filename");
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}
await fs.mkdir(path.dirname(outputLocation), { recursive: true });
const serveUrl = await bundle({
  entryPoint: path.join(tools, "src/index.tsx"),
  publicDir: path.join(project, "public"),
});
const inputProps = { manifest };
const browserExecutable = process.env.AI_EDITOR_BROWSER || undefined;
const composition = await selectComposition({
  serveUrl,
  id: "Timeline",
  inputProps,
  browserExecutable,
});
await renderMedia({
  composition,
  serveUrl,
  inputProps,
  outputLocation,
  browserExecutable,
  codec: "h264",
  pixelFormat: "yuv420p",
  crf: preview ? 28 : 18,
  scale: preview ? 0.5 : 1,
  concurrency: 2,
  onProgress: ({ progress }) => {
    if (progress === 1) console.log("Rendered 100%");
  },
});
await fs.writeFile(
  outputLocation + ".json",
  JSON.stringify(
    { manifest, preview, created: new Date().toISOString() },
    null,
    2,
  ),
);
console.log(outputLocation);
