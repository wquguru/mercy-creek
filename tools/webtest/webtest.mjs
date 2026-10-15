// 网页版冒烟测试：用本机 Chrome（WebGPU）打开构建，截标题画面，再跑一个结局的自动通关，看控制台里的 PASS。
// node tools/webtest/webtest.mjs [端口] [结局]
import puppeteer from "puppeteer-core";
import { spawn } from "node:child_process";
import path from "node:path";
import fs from "node:fs";

const root = path.resolve(import.meta.dirname, "../..");
const port = process.argv[2] || "8700";
const ending = process.argv[3] || "escape";
const out = path.join(root, "Reviews/web");
fs.mkdirSync(out, { recursive: true });
const server = spawn("python3", ["-m", "http.server", port, "-d", path.join(root, "Game/Builds/Web")], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 1000));

const browser = await puppeteer.launch({
  executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  headless: "new",
  args: ["--enable-unsafe-webgpu", "--enable-features=WebGPU", "--window-size=1600,900", "--use-angle=metal", "--ignore-gpu-blocklist"],
  defaultViewport: { width: 1600, height: 900 },
});
let failed = false;
async function run(query, label, untilText, timeoutMs) {
  const page = await browser.newPage();
  const lines = [];
  page.on("console", (m) => { const t = m.text(); lines.push(t); if (/\[AutoTest\]|\[Story\]|Exception|error/i.test(t)) console.log(`  [${label}] ${t.slice(0, 220)}`); });
  page.on("pageerror", (e) => console.log(`  [${label}] pageerror ${e.message}`));
  const t0 = Date.now();
  await page.goto(`http://localhost:${port}/${query}`, { waitUntil: "load" });
  await page.waitForFunction(() => document.getElementById("overlay")?.classList.contains("gone") || document.getElementById("nogpu")?.style.display === "block", { timeout: 180000 });
  const nogpu = await page.evaluate(() => document.getElementById("nogpu").style.display === "block");
  console.log(`  [${label}] loaded in ${((Date.now() - t0) / 1000).toFixed(1)}s, webgpu=${!nogpu}`);
  if (nogpu) { failed = true; await page.screenshot({ path: path.join(out, `${label}.png`) }); return; }
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline && !(untilText && lines.some((l) => l.includes(untilText)))) await new Promise((r) => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(out, `${label}.png`) });
  if (untilText && !lines.some((l) => l.includes(untilText))) { console.log(`  [${label}] TIMEOUT waiting for ${untilText}`); failed = true; }
  if (lines.some((l) => l.includes("[AutoTest] FAIL"))) failed = true;
  await page.close();
}
try {
  await run("?lang=zh", "title_zh", null, 8000);
  await run(`?autotest=web&ending=${ending}&lang=zh`, `autotest_${ending}`, "[AutoTest] PASS", 240000);
} finally {
  await browser.close();
  server.kill();
}
console.log(failed ? "WEBTEST FAILED" : "WEBTEST PASS");
process.exit(failed ? 1 : 0);
