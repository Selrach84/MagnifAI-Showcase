// deepgram.js — live streaming STT with speaker diarization.
// Feeds linear16 PCM from a MediaStream to Deepgram's realtime websocket and
// emits transcript segments. Runs inside the offscreen document.

export class DeepgramLive {
  constructor(apiKey, { language = "en", onSegment, onError, onOpen, url } = {}) {
    this.apiKey = apiKey;
    this.language = language;
    this.baseUrl = url || "wss://api.deepgram.com/v1/listen"; // override for self-host/proxy/testing
    this.onSegment = onSegment || (() => {});
    this.onError = onError || (() => {});
    this.onOpen = onOpen || (() => {});
    this.ws = null;
    this.ctx = null;
    this.proc = null;
    this.source = null;
    this.startTs = 0;
  }

  connect(stream) {
    this.startTs = Date.now();
    const targetRate = 16000;
    const params = new URLSearchParams({
      model: "nova-2",
      diarize: "true",
      punctuate: "true",
      smart_format: "true",
      interim_results: "true",
      encoding: "linear16",
      sample_rate: String(targetRate),
      language: this.language
    });
    const url = `${this.baseUrl}?${params}`;
    // Deepgram accepts token auth via subprotocol.
    this.ws = new WebSocket(url, ["token", this.apiKey]);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      this.onOpen();
      this._startCapture(stream, targetRate);
      // keepalive
      this._ka = setInterval(() => {
        if (this.ws?.readyState === 1) this.ws.send(JSON.stringify({ type: "KeepAlive" }));
      }, 8000);
    };

    this.ws.onmessage = (evt) => {
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }
      if (msg.type !== "Results") return;
      const alt = msg.channel?.alternatives?.[0];
      if (!alt || !alt.transcript) return;
      // derive speaker from first word
      const spk = alt.words?.[0]?.speaker;
      const speaker = spk === undefined ? "Speaker" : `Speaker ${spk + 1}`;
      const elapsed = (msg.start || (Date.now() - this.startTs) / 1000);
      this.onSegment({
        speaker,
        text: alt.transcript,
        ts: elapsed,
        isFinal: !!msg.is_final
      });
    };

    this.ws.onerror = (e) => this.onError(e);
    this.ws.onclose = () => clearInterval(this._ka);
  }

  _startCapture(stream, targetRate) {
    this.ctx = new AudioContext();
    this.source = this.ctx.createMediaStreamSource(stream);
    this.proc = this.ctx.createScriptProcessor(4096, 1, 1);
    const inRate = this.ctx.sampleRate;
    this.source.connect(this.proc);
    this.proc.connect(this.ctx.destination);

    this.proc.onaudioprocess = (e) => {
      if (this.ws?.readyState !== 1) return;
      const input = e.inputBuffer.getChannelData(0);
      const down = this._downsample(input, inRate, targetRate);
      this.ws.send(this._floatTo16(down));
    };
  }

  _downsample(buf, inRate, outRate) {
    if (outRate >= inRate) return buf;
    const ratio = inRate / outRate;
    const len = Math.round(buf.length / ratio);
    const out = new Float32Array(len);
    let oi = 0, ii = 0;
    while (oi < len) {
      const next = Math.round((oi + 1) * ratio);
      let sum = 0, cnt = 0;
      for (; ii < next && ii < buf.length; ii++) { sum += buf[ii]; cnt++; }
      out[oi] = cnt ? sum / cnt : 0;
      oi++;
    }
    return out;
  }

  _floatTo16(f32) {
    const out = new Int16Array(f32.length);
    for (let i = 0; i < f32.length; i++) {
      const s = Math.max(-1, Math.min(1, f32[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out.buffer;
  }

  close() {
    try { this.proc && (this.proc.onaudioprocess = null); } catch {}
    try { this.source && this.source.disconnect(); } catch {}
    try { this.proc && this.proc.disconnect(); } catch {}
    try { this.ctx && this.ctx.close(); } catch {}
    try {
      if (this.ws?.readyState === 1) this.ws.send(JSON.stringify({ type: "CloseStream" }));
      this.ws && this.ws.close();
    } catch {}
    clearInterval(this._ka);
  }
}
