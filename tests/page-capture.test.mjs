import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import test from "node:test";
import { capturePage } from "../skills/video-edit/assets/toolchain/capture-page.mjs";

const exec = promisify(execFile);
const fixture = `<!doctype html><html><head><title>Screenshot fixture</title><style>
body{margin:0;display:flow-root;min-height:1400px;font:20px sans-serif}#card{width:180px;height:90px;background:#00cc44;margin:20px}
</style></head><body><div id="card">Reusable asset</div><script>
setTimeout(()=>{const p=document.createElement('p');p.id='ready';p.textContent='Ready';document.body.append(p)},30)
</script></body></html>`;

async function environment(t) {
  const project = await fs.mkdtemp(
    path.join(os.tmpdir(), "Screenshot project "),
  );
  await fs.writeFile(
    path.join(project, "project.json"),
    JSON.stringify({ version: 1, id: "fixture", assets: [] }),
  );
  const server = http.createServer((req, res) => {
    if (req.url === "/redirect") {
      res.writeHead(302, { Location: "/page" });
      res.end();
    } else if (req.url === "/missing") {
      res.writeHead(404);
      res.end("Missing page");
    } else {
      res.setHeader("Content-Type", "text/html");
      res.end(fixture);
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  t.after(async () => {
    await new Promise((resolve) => server.close(resolve));
    await fs.rm(project, { recursive: true, force: true });
  });
  return {
    project,
    url: `http://127.0.0.1:${server.address().port}`,
    browserExecutable: process.env.AI_EDITOR_BROWSER,
  };
}

test(
  "Viewport capture preserves pixel scale, transparency and source provenance",
  { timeout: 180000 },
  async (t) => {
    const env = await environment(t);
    const result = await capturePage({
      ...env,
      assetId: "desktop",
      url: env.url + "/redirect",
      width: 400,
      height: 240,
      scale: 2,
      waitFor: "#ready",
      transparent: true,
    });
    assert.equal(result.width, 800);
    assert.equal(result.height, 480);
    assert.equal(result.title, "Screenshot fixture");
    assert.equal(result.finalUrl, env.url + "/page");
    assert.equal(result.sourceUrl, env.url + "/redirect");
    const image = path.join(env.project, "public", result.src);
    const registry = JSON.parse(
      await fs.readFile(path.join(env.project, "project.json"), "utf8"),
    );
    assert.equal(registry.assets[0].src, result.clip.src);
    assert.equal(registry.assets[0].sha256, result.sha256);
    const metadata = JSON.parse(
      await fs.readFile(
        path.join(env.project, "public", result.metadataSrc),
        "utf8",
      ),
    );
    assert.equal(metadata.viewport.deviceScaleFactor, 2);
    const { stdout } = await exec(
      "ffmpeg",
      [
        "-v",
        "error",
        "-i",
        image,
        "-vf",
        "crop=1:1:700:400,format=rgba",
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "pipe:1",
      ],
      { encoding: "buffer" },
    );
    assert.equal(stdout[3], 0);
    const original = await fs.readFile(image);
    await assert.rejects(
      capturePage({ ...env, assetId: "desktop", url: env.url + "/page" }),
      /already exists/,
    );
    assert.deepEqual(await fs.readFile(image), original);
  },
);

test(
  "Full-page JPEG and isolated element captures register separate reusable assets",
  { timeout: 180000 },
  async (t) => {
    const env = await environment(t);
    const full = await capturePage({
      ...env,
      assetId: "article",
      url: env.url + "/page",
      width: 400,
      height: 240,
      fullPage: true,
      format: "jpeg",
      quality: 80,
    });
    assert.equal(full.width, 400);
    assert.equal(full.height, 1400);
    assert.ok(full.src.endsWith(".jpg"));
    const element = await capturePage({
      ...env,
      assetId: "card",
      url: env.url + "/page",
      width: 400,
      height: 240,
      selector: "#card",
      format: "webp",
    });
    assert.equal(element.width, 180);
    assert.equal(element.height, 90);
    const registry = JSON.parse(
      await fs.readFile(path.join(env.project, "project.json"), "utf8"),
    );
    assert.equal(registry.assets.length, 2);
  },
);

test(
  "Failed navigation or selectors leave no assets or partial captures",
  { timeout: 180000 },
  async (t) => {
    const env = await environment(t);
    await assert.rejects(
      capturePage({ ...env, assetId: "missing", url: env.url + "/missing" }),
      /HTTP 404/,
    );
    await assert.rejects(
      capturePage({
        ...env,
        assetId: "selector",
        url: env.url + "/page",
        selector: "#does-not-exist",
        timeoutMs: 300,
      }),
      /Waiting for selector/,
    );
    assert.deepEqual(
      await fs.readdir(path.join(env.project, "public/web")),
      [],
    );
    const registry = JSON.parse(
      await fs.readFile(path.join(env.project, "project.json"), "utf8"),
    );
    assert.deepEqual(registry.assets, []);
  },
);
