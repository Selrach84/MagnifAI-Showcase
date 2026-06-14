// Proves local Whisper (transformers.js) transcribes real audio with NO key and
// NO cloud STT service — the free, browser-independent engine.
import { pipeline, env } from "@xenova/transformers";
import { readFileSync } from "fs";
env.allowLocalModels = false;

const buf = readFileSync("/tmp/echo_speech.wav");
const di = buf.indexOf(Buffer.from("data")) + 8;
const pcm = new Int16Array(buf.buffer, buf.byteOffset + di, (buf.length - di) >> 1);
const f32 = Float32Array.from(pcm, (v) => v / 32768);
console.log("samples:", f32.length, `(~${(f32.length / 16000).toFixed(1)}s)`);

console.time("load+infer");
const asr = await pipeline("automatic-speech-recognition", "Xenova/whisper-tiny.en");
const out = await asr(f32);
console.timeEnd("load+infer");
console.log("TRANSCRIPT:", JSON.stringify(out.text));

const got = out.text.toLowerCase();
const hit = ["charles", "echo", "friday", "pipeline"].filter((w) => got.includes(w));
console.log(hit.length >= 2 ? `\nLOCAL WHISPER WORKS (matched: ${hit.join(", ")})` : "\nweak match: " + hit.join(","));
process.exit(hit.length >= 2 ? 0 : 1);
