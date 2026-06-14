// localwhisper.js — FREE, no-key, no-cloud transcription via transformers.js
// (Whisper) running fully in-browser on WASM. Works on any Chromium incl. Brave.
// Runs in the offscreen document (needs AudioContext + WASM). The model (~40MB
// for tiny.en) downloads from the Hugging Face CDN once, then is cached locally.

import { pipeline, env } from "./vendor/transformers.js";

env.allowLocalModels = false;       // fetch model from HF CDN
env.useBrowserCache = true;         // cache after first download
// Serve the ONNX wasm from inside the extension (no remote script needed).
env.backends.onnx.wasm.wasmPaths = chrome.runtime.getURL("lib/vendor/");
env.backends.onnx.wasm.numThreads = 1; // non-threaded wasm: no COOP/COEP needed

let _asr = null;
let _model = "Xenova/whisper-tiny.en";

export async function ensureModel(model, onProgress) {
  if (_asr && model === _model) return _asr;
  _model = model || _model;
  _asr = await pipeline("automatic-speech-recognition", _model, {
    progress_callback: (p) => { if (onProgress && p.status === "progress") onProgress(p); }
  });
  return _asr;
}

// Decode any audio Blob and resample to 16kHz mono Float32 (Whisper's rate).
async function blobToPCM16k(blob) {
  const arr = await blob.arrayBuffer();
  const ac = new (self.AudioContext || self.webkitAudioContext)();
  const decoded = await ac.decodeAudioData(arr.slice(0));
  await ac.close();
  const targetRate = 16000;
  if (decoded.sampleRate === targetRate && decoded.numberOfChannels === 1) {
    return decoded.getChannelData(0);
  }
  const frames = Math.ceil(decoded.duration * targetRate);
  const off = new OfflineAudioContext(1, frames, targetRate);
  const src = off.createBufferSource();
  src.buffer = decoded;
  src.connect(off.destination);
  src.start();
  const rendered = await off.startRendering();
  return rendered.getChannelData(0);
}

// Transcribe a recorded Blob -> [{speaker, text, ts, isFinal}]
export async function transcribeLocal(blob, { model, onProgress, language } = {}) {
  const asr = await ensureModel(model, onProgress);
  const pcm = await blobToPCM16k(blob);
  const out = await asr(pcm, {
    chunk_length_s: 30,
    stride_length_s: 5,
    return_timestamps: true,
    language: language && language !== "en" ? language : undefined,
    task: "transcribe"
  });
  const chunks = out.chunks && out.chunks.length ? out.chunks : [{ timestamp: [0, null], text: out.text }];
  return chunks
    .map((c) => ({ speaker: "Speaker", text: (c.text || "").trim(), ts: c.timestamp?.[0] || 0, isFinal: true }))
    .filter((s) => s.text);
}
