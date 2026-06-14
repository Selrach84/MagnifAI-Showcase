// offscreen.js — the only context allowed to capture media in MV3.
// Captures tab audio (+ optional mic), records to a Blob, and streams to
// Deepgram for live diarized transcription. Talks to the service worker.

import { DeepgramLive } from "./lib/deepgram.js";

let state = null; // { meetingId, recorder, chunks, dg, ctx, streams, monitorGain }

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.target !== "offscreen") return;
  if (msg.type === "start-capture") {
    start(msg).then(() => sendResponse({ ok: true })).catch((e) => {
      report("error", { meetingId: msg.meetingId, error: String(e) });
      sendResponse({ ok: false, error: String(e) });
    });
    return true;
  }
  if (msg.type === "stop-capture") {
    stop().then(() => sendResponse({ ok: true })).catch((e) => sendResponse({ ok: false, error: String(e) }));
    return true;
  }
});

function report(type, payload) {
  chrome.runtime.sendMessage({ source: "offscreen", type, ...payload });
}

async function start({ streamId, meetingId, settings }) {
  if (state) await stop();

  // 1. Tab audio stream from the media stream id minted by the service worker.
  const tabStream = await navigator.mediaDevices.getUserMedia({
    audio: { mandatory: { chromeMediaSource: "tab", chromeMediaSourceId: streamId } },
    video: false
  });

  // 2. Optional mic stream (captures the user's own voice).
  let micStream = null;
  if (settings.captureMic) {
    try {
      micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      report("warn", { meetingId, warn: "Mic capture denied: " + e });
    }
  }

  // 3. Mix into one stream; keep the tab audible to the user.
  const ctx = new AudioContext();
  const dest = ctx.createMediaStreamDestination();
  const tabSrc = ctx.createMediaStreamSource(tabStream);
  tabSrc.connect(dest);
  // monitor: route tab audio to speakers so the user still hears the call
  const monitorGain = ctx.createGain();
  monitorGain.gain.value = 1.0;
  tabSrc.connect(monitorGain).connect(ctx.destination);
  if (micStream) {
    const micSrc = ctx.createMediaStreamSource(micStream);
    micSrc.connect(dest); // mic into recording, NOT into monitor (avoid echo)
  }
  const mixed = dest.stream;

  // 4. Record to a Blob.
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus" : "audio/webm";
  const recorder = new MediaRecorder(mixed, { mimeType: mime });
  const chunks = [];
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.start(1000);

  // 5. Live transcription.
  let dg = null;
  if (settings.deepgramKey) {
    dg = new DeepgramLive(settings.deepgramKey, {
      language: settings.language || "en",
      url: settings.deepgramUrl || undefined,
      onOpen: () => report("status", { meetingId, status: "transcribing" }),
      onSegment: (seg) => report("segment", { meetingId, segment: seg }),
      onError: (e) => report("warn", { meetingId, warn: "Deepgram error: " + (e?.message || e) })
    });
    dg.connect(mixed);
  } else {
    report("status", { meetingId, status: "recording" }); // whisper fallback at stop
  }

  state = { meetingId, recorder, chunks, dg, ctx, mime, settings,
            streams: [tabStream, micStream].filter(Boolean) };
  report("status", { meetingId, status: dg ? "transcribing" : "recording" });
}

async function stop() {
  if (!state) return;
  const s = state;
  state = null;

  await new Promise((resolve) => {
    s.recorder.onstop = resolve;
    try { s.recorder.stop(); } catch { resolve(); }
  });
  try { s.dg && s.dg.close(); } catch {}
  try { s.ctx && s.ctx.close(); } catch {}
  s.streams.forEach((st) => st.getTracks().forEach((t) => t.stop()));

  const blob = new Blob(s.chunks, { type: s.mime });

  // Free local transcription (no key, works on Brave) when Deepgram wasn't used.
  const eng = s.settings?.sttEngine || "auto";
  const useLocal = !s.dg && (eng === "local" || (eng === "auto" && !s.settings?.deepgramKey));
  let localSegs = null;
  if (useLocal) {
    try {
      report("status", { meetingId: s.meetingId, status: "transcribing-local" });
      const { transcribeLocal } = await import("./lib/localwhisper.js");
      localSegs = await transcribeLocal(blob, {
        language: s.settings?.language,
        onProgress: (p) => report("model-progress", { meetingId: s.meetingId, progress: Math.round(p.progress || 0) })
      });
      for (const seg of localSegs) report("segment", { meetingId: s.meetingId, segment: seg }); // live UI
    } catch (e) {
      report("warn", { meetingId: s.meetingId, warn: "Local Whisper failed: " + (e?.message || e) });
    }
  }

  const buf = await blob.arrayBuffer();
  // Hand the audio back to the service worker for storage + post-processing.
  // Pass local segments inline so the summary step has them race-free.
  report("recording-done", { meetingId: s.meetingId, mime: s.mime, audio: buf, segments: localSegs });
}
