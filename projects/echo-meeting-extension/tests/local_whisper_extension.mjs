// Proves the FREE local Whisper engine actually transcribes REAL speech INSIDE
// the loaded extension (offscreen-equivalent page context, WASM) on Brave —
// no API key, no cloud STT. Feeds the real speech WAV in as a Blob and runs
// extension/lib/localwhisper.js exactly as the offscreen recorder does.
import puppeteer from "puppeteer-core";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import { existsSync, readFileSync, mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXT = resolve(__dirname, "../extension");
const WAV = "/tmp/echo_speech.wav";
const exe = ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"].find(existsSync);
if (!exe || !existsSync(WAV)) { console.error("missing browser or WAV"); process.exit(2); }

let fail = 0;
const ok = (c, m) => { console.log((c ? "ok:   " : "FAIL: ") + m); if (!c) fail++; };
const b64 = readFileSync(WAV).toString("base64");
const userDataDir = mkdtempSync(resolve(tmpdir(), "echo-lw-"));

const browser = await puppeteer.launch({
  executablePath: exe, headless: false, userDataDir, protocolTimeout: 300000,
  args: [`--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`, "--no-first-run", "--window-size=420,320"]
});

try {
  const sw = await browser.waitForTarget((t) => t.type() === "service_worker" && t.url().includes("background.js"), { timeout: 15000 });
  const extId = new URL(sw.url()).host;
  const page = await browser.newPage();
  page.on("console", (m) => { const t = m.text(); if (/error/i.test(m.type())) console.log("  [page] " + t); });
  await page.goto(`chrome-extension://${extId}/dashboard.html`, { waitUntil: "domcontentloaded" });

  console.log("  (downloading ~40MB model on first run; please wait)…");
  const result = await page.evaluate(async (b64) => {
    const bin = atob(b64);
    const bytes = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    const blob = new Blob([bytes], { type: "audio/wav" });
    const { transcribeLocal } = await import("./lib/localwhisper.js");
    const segs = await transcribeLocal(blob, {});
    return { text: segs.map((s) => s.text).join(" "), count: segs.length };
  }, b64);

  console.log("  TRANSCRIPT:", JSON.stringify(result.text));
  const got = (result.text || "").toLowerCase();
  const hit = ["charles", "echo", "friday", "pipeline", "maria"].filter((w) => got.includes(w));
  ok(result.count > 0, `local Whisper produced ${result.count} segment(s) inside the extension`);
  ok(hit.length >= 2, `transcript matches real speech in-extension (matched: ${hit.join(", ")})`);
} catch (e) {
  console.error("threw:", e); fail++;
} finally {
  await browser.close();
  try { rmSync(userDataDir, { recursive: true, force: true }); } catch {}
}
console.log(fail ? `\n${fail} check(s) failed` : "\nFREE LOCAL WHISPER WORKS INSIDE THE EXTENSION (no key, no cloud, on Brave)");
process.exit(fail ? 1 : 0);
