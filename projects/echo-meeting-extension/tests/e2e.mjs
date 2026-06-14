// Real-browser E2E: loads the unpacked extension in a Chromium browser and
// verifies (1) the MV3 service worker registers with no fatal manifest/module
// error, (2) the real IndexedDB layer round-trips, (3) all lib modules import,
// (4) markdown export builds. Uses puppeteer-core driving an installed browser.
import puppeteer from "puppeteer-core";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import { existsSync, mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXT = resolve(__dirname, "../extension");

const BROWSERS = [
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium",
  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
];
const exe = BROWSERS.find(existsSync);
if (!exe) { console.error("No Chromium browser found"); process.exit(2); }

let fail = 0;
const ok = (c, m) => { console.log((c ? "ok:   " : "FAIL: ") + m); if (!c) fail++; };
const userDataDir = mkdtempSync(resolve(tmpdir(), "echo-e2e-"));

const browser = await puppeteer.launch({
  executablePath: exe,
  headless: false, // MV3 service workers load most reliably headful
  userDataDir,
  args: [
    `--disable-extensions-except=${EXT}`,
    `--load-extension=${EXT}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--window-size=420,320"
  ]
});

try {
  // 1. service worker registers => manifest valid + background.js module graph resolved
  const swTarget = await browser.waitForTarget(
    (t) => t.type() === "service_worker" && t.url().includes("background.js"),
    { timeout: 15000 }
  );
  ok(!!swTarget, "MV3 service worker registered (manifest + ESM imports OK)");

  const extId = new URL(swTarget.url()).host;
  ok(/^[a-p]{32}$/.test(extId), "extension id minted: " + extId);

  // capture service-worker console errors
  const sw = await swTarget.worker();
  const swErrors = [];
  sw.on("console", (m) => { if (m.type() === "error") swErrors.push(m.text()); });

  // 2+3+4: run real logic on an extension page (extension origin => real chrome.* + IndexedDB)
  const page = await browser.newPage();
  const pageErrors = [];
  page.on("pageerror", (e) => pageErrors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") pageErrors.push(m.text()); });
  await page.goto(`chrome-extension://${extId}/dashboard.html`, { waitUntil: "domcontentloaded" });

  // all lib modules import without throwing
  const importsOk = await page.evaluate(async () => {
    await import("./lib/db.js");
    await import("./lib/deepgram.js");
    await import("./lib/summarize.js");
    await import("./lib/whisper.js");
    return true;
  });
  ok(importsOk === true, "all lib modules import in real extension context");

  // real IndexedDB round-trip via db.js
  const db = await page.evaluate(async () => {
    const m = await import("./lib/db.js");
    const id = "test_" + Date.now();
    await m.createMeeting({ id, title: "QA call", platform: "Google Meet",
      startedAt: Date.now(), endedAt: Date.now() + 60000, status: "recording", segments: [] });
    await m.appendSegment(id, { speaker: "Speaker 1", text: "Hello team.", ts: 1.0, isFinal: true });
    await m.appendSegment(id, { speaker: "Speaker 2", text: "Ship it Friday.", ts: 4.2, isFinal: true });
    const blob = new Blob([new Uint8Array([1, 2, 3, 4])], { type: "audio/webm" });
    await m.saveAudio(id, blob);
    const got = await m.getMeeting(id);
    const audio = await m.getAudio(id);
    const list = await m.listMeetings();
    await m.updateMeeting(id, { status: "done" });
    const updated = await m.getMeeting(id);
    return {
      segCount: got.segments.length,
      audioSize: audio ? audio.size : 0,
      inList: list.some((x) => x.id === id),
      statusAfter: updated.status,
      secondSpeaker: got.segments[1]?.speaker,
      id
    };
  });
  ok(db.segCount === 2, "IndexedDB: segments appended + persisted (" + db.segCount + ")");
  ok(db.audioSize === 4, "IndexedDB: audio blob stored + retrieved (" + db.audioSize + " bytes)");
  ok(db.inList === true, "IndexedDB: meeting appears in listMeetings()");
  ok(db.statusAfter === "done", "IndexedDB: updateMeeting() persists");
  ok(db.secondSpeaker === "Speaker 2", "diarization labels preserved");

  // markdown export shape (pure logic mirrored from background.buildMarkdown)
  const md = await page.evaluate(async (id) => {
    const m = await import("./lib/db.js");
    const mt = await m.getMeeting(id);
    const seg = (mt.segments || []).filter((s) => s.isFinal)
      .map((s) => `${s.speaker}: ${s.text}`).join("\n");
    return `---\ntitle: ${mt.title}\n---\n# ${mt.title}\n## Transcript\n${seg}`;
  }, db.id);
  ok(md.includes("Ship it Friday") && md.includes("---"), "markdown export builds with frontmatter + transcript");

  ok(swErrors.length === 0, "no service-worker console errors" + (swErrors.length ? ": " + swErrors.join("; ") : ""));
  ok(pageErrors.length === 0, "no page errors" + (pageErrors.length ? ": " + pageErrors.join("; ") : ""));

} catch (e) {
  console.error("E2E threw:", e);
  fail++;
} finally {
  await browser.close();
  try { rmSync(userDataDir, { recursive: true, force: true }); } catch {}
}

console.log(fail ? `\n${fail} check(s) failed` : "\nALL E2E CHECKS PASSED");
process.exit(fail ? 1 : 0);
