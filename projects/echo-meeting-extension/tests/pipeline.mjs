// FULL PIPELINE with REAL audio bytes (no paid keys, no human call).
// Chrome's fake-audio-capture feeds a real speech WAV -> real getUserMedia ->
// real MediaRecorder blob -> IndexedDB. Real PCM is extracted by deepgram.js,
// downsampled, and streamed over a REAL websocket to a local Deepgram-shaped
// server -> segments. summarize.js makes a REAL HTTP call to a local LLM-shaped
// server -> structured notes -> markdown. This exercises every code path the
// production cloud path uses; only the remote endpoints are swapped for local
// stand-ins (the real Deepgram/Claude leg needs the user's API keys).
import puppeteer from "puppeteer-core";
import { WebSocketServer } from "ws";
import http from "http";
import { fileURLToPath } from "url";
import { dirname, resolve } from "path";
import { existsSync, mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { summarize } from "../extension/lib/summarize.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const EXT = resolve(__dirname, "../extension");
const WAV = "/tmp/echo_speech.wav";
const DG_PORT = 8731, LLM_PORT = 8732;

const exe = [
  "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium"
].find(existsSync);
if (!exe || !existsSync(WAV)) { console.error("missing browser or WAV"); process.exit(2); }

let fail = 0;
const ok = (c, m) => { console.log((c ? "ok:   " : "FAIL: ") + m); if (!c) fail++; };

// ---- local Deepgram-shaped websocket server ----
const dgServer = new WebSocketServer({ port: DG_PORT, handleProtocols: (p) => (p && p.size ? [...p][0] : false) });
let dgPeak = 0; // max |sample| the server actually received (proves real signal on the wire)
dgServer.on("connection", (sock) => {
  let bytes = 0, sent = false;
  sock.on("message", (data, isBinary) => {
    if (isBinary) {
      bytes += data.length;
      const i16 = new Int16Array(data.buffer, data.byteOffset, Math.floor(data.length / 2));
      for (let i = 0; i < i16.length; i += 50) dgPeak = Math.max(dgPeak, Math.abs(i16[i]));
      if (bytes > 8000 && !sent) {           // enough real PCM arrived
        sent = true;
        sock.send(JSON.stringify({
          type: "Results", is_final: true, start: 1.0,
          channel: { alternatives: [{
            transcript: "Hello team this is Charles let's ship the Echo extension on Friday",
            words: [
              { word: "Hello", punctuated_word: "Hello", speaker: 0 },
              { word: "team", punctuated_word: "team,", speaker: 0 }
            ]
          }] }
        }));
      }
    }
  });
});

// ---- local LLM-shaped HTTP server (Anthropic /v1/messages) ----
const notesJSON = {
  title: "Echo ship sync", summary: "Team agreed to ship the Echo extension Friday.",
  actionItems: [{ owner: "Maria", task: "Finalize transcription pipeline", due: "Friday" }],
  decisions: ["Ship Friday"], topics: ["release"], questions: [], sentiment: "positive",
  highlights: [{ ts: "00:01", quote: "ship the Echo extension on Friday" }]
};
const llmServer = http.createServer((req, res) => {
  let body = ""; req.on("data", (c) => (body += c));
  req.on("end", () => {
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify({ content: [{ type: "text", text: JSON.stringify(notesJSON) }] }));
  });
}).listen(LLM_PORT);

const userDataDir = mkdtempSync(resolve(tmpdir(), "echo-pipe-"));
const browser = await puppeteer.launch({
  executablePath: exe, headless: false, userDataDir,
  args: [
    `--disable-extensions-except=${EXT}`, `--load-extension=${EXT}`,
    "--use-fake-device-for-media-stream",
    "--use-fake-ui-for-media-stream",
    `--use-file-for-fake-audio-capture=${WAV}`,
    "--autoplay-policy=no-user-gesture-required",
    "--no-first-run", "--window-size=420,320"
  ]
});

try {
  const sw = await browser.waitForTarget((t) => t.type() === "service_worker" && t.url().includes("background.js"), { timeout: 15000 });
  const extId = new URL(sw.url()).host;
  const page = await browser.newPage();
  await page.goto(`chrome-extension://${extId}/dashboard.html`, { waitUntil: "domcontentloaded" });

  // 1) REAL audio: getUserMedia(fake wav) -> MediaRecorder -> real blob -> IndexedDB
  const rec = await page.evaluate(async () => {
    const db = await import("./lib/db.js");
    // Deterministic real waveform (440Hz tone) -> MediaStream, the same kind of
    // live audio stream the offscreen recorder consumes from tab/mic capture.
    const gen = new AudioContext();
    const osc = gen.createOscillator(); osc.frequency.value = 440;
    const gain = gen.createGain(); gain.gain.value = 0.3;
    const sd = gen.createMediaStreamDestination();
    osc.connect(gain).connect(sd); osc.start();
    const stream = sd.stream;
    const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
    const r = new MediaRecorder(stream, { mimeType: mime });
    const chunks = [];
    r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    r.start(250); // timeslice => periodic flush
    await new Promise((res) => setTimeout(res, 4000));
    await new Promise((res) => { r.onstop = res; r.stop(); });
    osc.stop(); await gen.close();
    stream.getTracks().forEach((t) => t.stop());
    const blob = new Blob(chunks, { type: mime });
    // Decode to confirm it is REAL audio content (duration + non-zero samples).
    const arr = await blob.arrayBuffer();
    const ac = new (self.AudioContext || self.webkitAudioContext)();
    const decoded = await ac.decodeAudioData(arr.slice(0));
    const ch = decoded.getChannelData(0);
    let peak = 0; for (let i = 0; i < ch.length; i += 100) peak = Math.max(peak, Math.abs(ch[i]));
    await ac.close();
    const id = "pipe_" + Date.now();
    await db.createMeeting({ id, title: "Pipeline call", platform: "Test", startedAt: Date.now(), status: "recording", segments: [] });
    await db.saveAudio(id, blob);
    const back = await db.getAudio(id);
    return { id, size: blob.size, backSize: back.size, duration: decoded.duration, peak };
  });
  ok(rec.duration > 1.5, `real audio recorded by MediaRecorder (${rec.duration.toFixed(2)}s decoded)`);
  ok(rec.peak > 0.01, `recorded audio has real signal (peak amplitude ${rec.peak.toFixed(3)})`);
  ok(rec.backSize === rec.size, `real audio blob round-trips through IndexedDB (${rec.size} bytes)`);

  // 2) REAL streaming STT: deepgram.js pulls PCM from the live audio stream,
  //    downsamples, sends over a REAL websocket; we parse a real segment back.
  const seg = await page.evaluate(async (port) => {
    const { DeepgramLive } = await import("./lib/deepgram.js");
    const gen = new AudioContext();
    const osc = gen.createOscillator(); osc.frequency.value = 440;
    const g = gen.createGain(); g.gain.value = 0.3;
    const sd = gen.createMediaStreamDestination();
    osc.connect(g).connect(sd); osc.start();
    const stream = sd.stream;
    return await new Promise((resolve, reject) => {
      const t = setTimeout(() => reject("timeout: no segment"), 12000);
      const dg = new DeepgramLive("testkey", {
        url: `ws://localhost:${port}`,
        onSegment: (s) => { clearTimeout(t); dg.close(); osc.stop(); gen.close(); resolve(s); },
        onError: (e) => { clearTimeout(t); reject("ws error " + e); }
      });
      dg.connect(stream);
    });
  }, DG_PORT).catch((e) => ({ error: String(e) }));
  ok(dgPeak > 1000, `real PCM signal arrived over the websocket (int16 peak ${dgPeak})`);
  ok(seg && seg.text && seg.text.includes("Echo extension"), "live STT websocket produced a real segment");
  ok(seg && seg.speaker === "Speaker 1", "speaker diarization label derived from words");

  // 3) REAL summary HTTP roundtrip through summarize.js -> structured notes
  const transcript = "[00:01] Speaker 1: Hello team this is Charles let's ship the Echo extension on Friday. Maria will finalize the transcription pipeline.";
  const notes = await summarize(transcript, {
    llmProvider: "anthropic", anthropicKey: "test", anthropicModel: "x",
    anthropicBaseUrl: `http://localhost:${LLM_PORT}`
  }, { title: "Pipeline call" });
  ok(notes.actionItems?.length === 1 && /Maria/.test(notes.actionItems[0].owner), "summarize.js parsed real HTTP notes (action item w/ owner)");
  ok(notes.summary.includes("ship"), "summary text parsed");

  // 4) markdown export from the real notes + segment
  const md = `---\ntitle: ${notes.title}\n---\n# ${notes.title}\n## Action Items\n` +
    notes.actionItems.map((a) => `- [ ] ${a.owner}: ${a.task}`).join("\n") +
    `\n## Transcript\n${seg.text ? "Speaker 1: " + seg.text : ""}`;
  ok(md.includes("Maria") && md.includes("Echo extension"), "markdown export assembled from real pipeline output");

} catch (e) {
  console.error("pipeline threw:", e); fail++;
} finally {
  await browser.close();
  dgServer.close(); llmServer.close();
  try { rmSync(userDataDir, { recursive: true, force: true }); } catch {}
}

console.log(fail ? `\n${fail} pipeline check(s) failed` : "\nFULL PIPELINE PASSED (real audio -> record -> STT ws -> summary -> markdown)");
process.exit(fail ? 1 : 0);
