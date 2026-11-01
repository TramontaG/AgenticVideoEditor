import fs from "node:fs/promises";
import path from "node:path";
import { spawn, execFile } from "node:child_process";
import { promisify } from "node:util";

const exec = promisify(execFile);

/** Encode PNG buffers as they arrive; WebM never writes individual frames to disk. */
export async function createAnimationOutput({
  directory,
  width,
  height,
  fps,
  frameCount,
  format = "webm",
  crf = 18,
}) {
  if (!["webm", "png"].includes(format))
    throw new Error("Use --format webm or png");
  await fs.mkdir(directory, { recursive: true });
  const staging = await fs.mkdtemp(path.join(directory, ".render-"));
  let encoder;
  let completed;
  let encoderError;
  let stderr = "";
  let received = 0;
  let finalized = false;

  async function abort() {
    if (encoder && encoder.exitCode === null && encoder.signalCode === null) {
      encoder.stdin.destroy();
      encoder.kill();
      await completed;
    }
    await fs.rm(staging, { recursive: true, force: true });
  }

  if (format === "webm") {
    encoder = spawn(
      process.env.AI_EDITOR_FFMPEG || "ffmpeg",
      [
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-f",
        "image2pipe",
        "-framerate",
        String(fps),
        "-c:v",
        "png",
        "-i",
        "pipe:0",
        "-an",
        "-c:v",
        "libvpx-vp9",
        "-pix_fmt",
        "yuva420p",
        "-b:v",
        "0",
        "-crf",
        String(crf),
        ...(crf === 0 ? ["-lossless", "1"] : []),
        "-auto-alt-ref",
        "0",
        "-threads",
        "2",
        "-row-mt",
        "1",
        path.join(staging, "animation.webm"),
      ],
      { stdio: ["pipe", "ignore", "pipe"] },
    );
    completed = new Promise((resolve) => {
      encoder.once("error", (error) => {
        encoderError = error;
        resolve({ code: null });
      });
      encoder.once("close", (code) => resolve({ code }));
    });
    encoder.stdin.on("error", (error) => {
      encoderError = error;
    });
    encoder.stderr.on("data", (data) => {
      stderr = (stderr + data).slice(-8192);
    });
  }

  async function writeFrame(index, png) {
    if (finalized || index !== received || index >= frameCount) {
      throw new Error(
        `Unexpected animation frame ${index}; expected ${received}`,
      );
    }
    if (format === "png") {
      await fs.writeFile(
        path.join(staging, String(index).padStart(6, "0") + ".png"),
        png,
      );
    } else {
      if (encoderError || encoder.exitCode !== null) {
        throw new Error(
          `FFmpeg could not encode transparent WebM: ${stderr || encoderError || encoder.exitCode}`,
        );
      }
      // Await the write callback so a slow encoder cannot accumulate all frames in memory.
      await new Promise((resolve, reject) =>
        encoder.stdin.write(png, (error) =>
          error ? reject(error) : resolve(),
        ),
      );
    }
    received++;
  }

  async function finish() {
    try {
      if (received !== frameCount)
        throw new Error(`Expected ${frameCount} frames, received ${received}`);
      if (format === "png") {
        const folder =
          "frames-" + path.basename(staging).replace(".render-", "");
        await fs.rename(staging, path.join(directory, folder));
        finalized = true;
        return { file: folder, format, framePattern: "%06d.png", frameCount };
      }
      encoder.stdin.end();
      const { code } = await completed;
      if (code !== 0 || encoderError)
        throw new Error(
          `Transparent WebM encoding failed: ${stderr || encoderError || code}`,
        );
      const temporary = path.join(staging, "animation.webm");
      const { stdout } = await exec(
        process.env.AI_EDITOR_FFPROBE || "ffprobe",
        [
          "-v",
          "error",
          "-count_frames",
          "-select_streams",
          "v:0",
          "-show_entries",
          "stream=codec_name,width,height,nb_read_frames:stream_tags=alpha_mode",
          "-of",
          "json",
          temporary,
        ],
      );
      const stream = JSON.parse(stdout).streams?.[0];
      if (
        stream?.codec_name !== "vp9" ||
        stream.width !== width ||
        stream.height !== height ||
        Number(stream.nb_read_frames) !== frameCount ||
        String(stream.tags?.alpha_mode ?? stream.tags?.ALPHA_MODE) !== "1"
      ) {
        throw new Error(
          "Encoded animation failed dimension, frame count, or alpha validation",
        );
      }
      const bytes = (await fs.stat(temporary)).size;
      // Replace the prior video only after successful encoding and validation.
      await fs.rename(temporary, path.join(directory, "animation.webm"));
      finalized = true;
      await fs.rm(staging, { recursive: true, force: true });
      return {
        file: "animation.webm",
        format,
        transparent: true,
        bytes,
        frameCount,
      };
    } catch (error) {
      await abort();
      throw error;
    }
  }

  return { writeFrame, finish, abort };
}
