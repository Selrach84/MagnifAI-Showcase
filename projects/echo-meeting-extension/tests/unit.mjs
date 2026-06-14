// Minimal sanity tests for pure DSP logic (no browser APIs touched).
import { DeepgramLive } from "../extension/lib/deepgram.js";

let fail = 0;
const ok = (c, m) => { if (!c) { console.error("FAIL:", m); fail++; } else console.log("ok:", m); };

const dg = new DeepgramLive("x"); // constructor stores only, no I/O

// downsample 48k -> 16k should give ~1/3 length
const inBuf = new Float32Array(48000).map((_, i) => Math.sin(i / 10));
const down = dg._downsample(inBuf, 48000, 16000);
ok(Math.abs(down.length - 16000) <= 2, `downsample length ~16000 got ${down.length}`);
ok(down.every((v) => v >= -1 && v <= 1), "downsample stays in [-1,1]");

// passthrough when out>=in
const same = dg._downsample(inBuf, 16000, 16000);
ok(same === inBuf, "no downsample when rate unchanged");

// float -> int16 conversion bounds
const pcm = new Int16Array(dg._floatTo16(new Float32Array([0, 1, -1, 0.5])));
ok(pcm[0] === 0, "0.0 -> 0");
ok(pcm[1] === 32767, "1.0 -> 32767");
ok(pcm[2] === -32768, "-1.0 -> -32768");
ok(Math.abs(pcm[3] - 16383) <= 1, "0.5 -> ~16383");

console.log(fail ? `\n${fail} test(s) failed` : "\nAll tests passed");
process.exit(fail ? 1 : 0);
