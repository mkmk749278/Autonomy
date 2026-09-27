// Render the 3D scene frame-by-frame in headless Chromium and encode with FFmpeg.
//   node videos/heart3d/render3d.mjs --out build/heart3d/video.mp4 --fps 30 --workers 2 [--from 0 --to 10]
import { chromium } from "playwright-core";
import { spawn } from "node:child_process";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d; };
const OUT = path.resolve(ROOT, arg("out", "build/heart3d/video.mp4"));
const FPS = +arg("fps", 30), WORKERS = +arg("workers", 2), W = 1920, H = 1080;
const CHROME = process.env.CHROME_PATH || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

const TYPES = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
  ".glb": "model/gltf-binary", ".png": "image/png" };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split("?")[0]);
  p = p.startsWith("/lib/three/") ? path.join(ROOT, "node_modules/three", p.slice("/lib/three/".length)) : path.join(ROOT, p);
  if (!p.startsWith(ROOT) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.statusCode = 404; return res.end(); }
  res.setHeader("Content-Type", TYPES[path.extname(p)] || "application/octet-stream");
  fs.createReadStream(p).pipe(res);
}).listen(0);
const port = server.address().port;

async function worker(id, f0, f1) {
  const browser = await chromium.launch({ executablePath: CHROME,
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist",
      "--disable-gpu-vsync", "--font-render-hinting=none"] });
  const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => console.error(`[w${id}] page error:`, e.message));
  page.on("console", (m) => { if (m.type() === "error") console.error(`[w${id}]`, m.text()); });
  await page.goto(`http://127.0.0.1:${port}/videos/heart3d/web/index.html?mode=render`);
  await page.waitForFunction("window.ready === true", null, { timeout: 180000 });
  await page.evaluate(() => document.fonts.ready);
  const part = OUT.replace(/\.mp4$/, `.part${id}.mp4`);
  const ff = spawn("ffmpeg", ["-v", "error", "-y", "-f", "image2pipe", "-framerate", String(FPS), "-c:v", "mjpeg", "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", part], { stdio: ["pipe", "inherit", "inherit"] });
  const t0 = Date.now();
  for (let f = f0; f < f1; f++) {
    await page.evaluate((t) => window.renderAt(t), f / FPS);
    const buf = await page.screenshot({ type: "jpeg", quality: 93 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once("drain", r));
    if ((f - f0) % 150 === 0) {
      const done = f - f0 + 1, rate = (Date.now() - t0) / 1000 / done;
      console.log(`[w${id}] frame ${f} (${done}/${f1 - f0}) ${rate.toFixed(2)} s/frame, ~${((f1 - f) * rate / 60).toFixed(1)} min left`);
    }
  }
  ff.stdin.end();
  await new Promise((r) => ff.on("close", r));
  await browser.close();
  return part;
}

// Quick visual check: --stills 5,20.5,40 writes PNGs to build/heart3d/stills/.
if (arg("stills")) {
  const times = arg("stills").split(",").map(Number);
  const browser = await chromium.launch({ executablePath: CHROME,
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const page = await browser.newPage({ viewport: { width: W, height: H } });
  page.on("pageerror", (e) => console.error("page error:", e.message));
  page.on("console", (m) => console.log("[page]", m.text()));
  const t0 = Date.now();
  await page.goto(`http://127.0.0.1:${port}/videos/heart3d/web/index.html?mode=render`);
  await page.waitForFunction("window.ready === true", null, { timeout: 300000 });
  await page.evaluate(() => document.fonts.ready);
  console.log(`scene ready in ${((Date.now() - t0) / 1000).toFixed(1)} s`);
  const dir = path.join(ROOT, "build/heart3d/stills"); fs.mkdirSync(dir, { recursive: true });
  for (const t of times) {
    await page.evaluate((x) => window.renderAt(x), t);
    await page.screenshot({ path: path.join(dir, `t${String(t).padStart(6, "0")}.png`) });
  }
  await browser.close(); server.close(); process.exit(0);
}

// Probe duration from the page's timeline.
const tl = JSON.parse(fs.readFileSync(path.join(ROOT, "build/heart3d/timeline.json"), "utf8"));
const from = Math.round(+arg("from", 0) * FPS), to = Math.round(+arg("to", tl.duration) * FPS);
const per = Math.ceil((to - from) / WORKERS);
console.log(`Rendering frames ${from}-${to} (${to - from}) with ${WORKERS} worker(s) at ${FPS} fps`);
const parts = await Promise.all(Array.from({ length: WORKERS }, (_, i) =>
  worker(i, from + i * per, Math.min(to, from + (i + 1) * per))));
const list = OUT.replace(/\.mp4$/, ".parts.txt");
fs.writeFileSync(list, parts.map((p) => `file '${p}'`).join("\n"));
await new Promise((r) => spawn("ffmpeg", ["-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", list, "-c", "copy", OUT],
  { stdio: "inherit" }).on("close", r));
parts.forEach((p) => fs.rmSync(p)); fs.rmSync(list);
server.close();
console.log(`Wrote ${OUT}`);
