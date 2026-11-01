import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { createAnimationOutput } from "../skills/video-edit/assets/toolchain/motion/output.mjs";

const hasFfmpeg = spawnSync("ffmpeg", ["-version"]).status === 0;

function frameFixture() {
  const rgba = Buffer.alloc(16 * 16 * 4);
  for (let y = 0; y < 16; y++) {
    for (let x = 8; x < 16; x++) {
      const index = (y * 16 + x) * 4;
      rgba[index] = 255;
      rgba[index + 3] = y < 8 ? 128 : 255;
    }
  }
  const encoded = spawnSync(
    "ffmpeg",
    [
      "-v",
      "error",
      "-f",
      "rawvideo",
      "-pix_fmt",
      "rgba",
      "-s",
      "16x16",
      "-i",
      "pipe:0",
      "-frames:v",
      "1",
      "-f",
      "image2pipe",
      "-c:v",
      "png",
      "pipe:1",
    ],
    { input: rgba },
  );
  assert.equal(encoded.status, 0, encoded.stderr.toString());
  return encoded.stdout;
}

async function outputDirectory(t) {
  const directory = await fs.mkdtemp(
    path.join(os.tmpdir(), "Animation output "),
  );
  t.after(() => fs.rm(directory, { recursive: true, force: true }));
  return directory;
}

test(
  "WebM preserves transparent, translucent and opaque pixels without PNG files",
  { skip: !hasFfmpeg },
  async (t) => {
    const directory = await outputDirectory(t);
    const writer = await createAnimationOutput({
      directory,
      width: 16,
      height: 16,
      fps: 30,
      frameCount: 2,
      crf: 0,
    });
    t.after(writer.abort);
    const frame = frameFixture();
    await writer.writeFrame(0, frame);
    await writer.writeFrame(1, frame);
    const result = await writer.finish();
    assert.equal(result.format, "webm");
    assert.equal(result.transparent, true);
    assert.deepEqual(await fs.readdir(directory), ["animation.webm"]);
    const decoded = spawnSync("ffmpeg", [
      "-v",
      "error",
      "-c:v",
      "libvpx-vp9",
      "-i",
      path.join(directory, result.file),
      "-f",
      "rawvideo",
      "-pix_fmt",
      "rgba",
      "pipe:1",
    ]);
    assert.equal(decoded.status, 0, decoded.stderr.toString());
    assert.equal(decoded.stdout.length, 16 * 16 * 4 * 2);
    for (let frameIndex = 0; frameIndex < 2; frameIndex++) {
      const alpha = (x, y) =>
        decoded.stdout[frameIndex * 16 * 16 * 4 + (y * 16 + x) * 4 + 3];
      assert.equal(alpha(2, 2), 0);
      assert.ok(Math.abs(alpha(12, 2) - 128) <= 2);
      assert.equal(alpha(12, 12), 255);
    }
  },
);

test(
  "PNG remains available explicitly, with complete sequential frames",
  { skip: !hasFfmpeg },
  async (t) => {
    const directory = await outputDirectory(t);
    const writer = await createAnimationOutput({
      directory,
      width: 16,
      height: 16,
      fps: 30,
      frameCount: 2,
      format: "png",
    });
    t.after(writer.abort);
    const frame = frameFixture();
    await writer.writeFrame(0, frame);
    await writer.writeFrame(1, frame);
    const result = await writer.finish();
    assert.deepEqual(await fs.readdir(path.join(directory, result.file)), [
      "000000.png",
      "000001.png",
    ]);
    assert.deepEqual(
      await fs.readFile(path.join(directory, result.file, "000000.png")),
      frame,
    );
    assert.ok(
      !(await fs.readdir(directory)).some((name) =>
        name.startsWith(".render-"),
      ),
    );
  },
);

test(
  "A failed encode preserves the previous asset and removes partial output",
  { skip: !hasFfmpeg },
  async (t) => {
    const directory = await outputDirectory(t);
    const previous = Buffer.from("previous asset must survive");
    await fs.writeFile(path.join(directory, "animation.webm"), previous);
    const writer = await createAnimationOutput({
      directory,
      width: 16,
      height: 16,
      fps: 30,
      frameCount: 1,
    });
    t.after(writer.abort);
    try {
      await writer.writeFrame(0, Buffer.from("invalid PNG"));
      await assert.rejects(writer.finish());
    } finally {
      await writer.abort();
    }
    assert.deepEqual(
      await fs.readFile(path.join(directory, "animation.webm")),
      previous,
    );
    assert.deepEqual(await fs.readdir(directory), ["animation.webm"]);
  },
);
