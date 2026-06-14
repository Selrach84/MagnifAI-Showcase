// whisper.js — batch transcription fallback (used when no Deepgram key).
// Transcribes a recorded audio Blob via OpenAI Whisper and returns segments.

export async function transcribeBlob(blob, settings) {
  if (!settings.openaiKey) throw new Error("Whisper fallback needs an OpenAI key (set in Options).");
  const form = new FormData();
  form.append("file", blob, "audio.webm");
  form.append("model", "whisper-1");
  form.append("response_format", "verbose_json");
  form.append("timestamp_granularities[]", "segment");

  const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
    method: "POST",
    headers: { authorization: `Bearer ${settings.openaiKey}` },
    body: form
  });
  if (!res.ok) throw new Error(`Whisper ${res.status}: ${await res.text()}`);
  const data = await res.json();
  const segs = (data.segments || []).map((s) => ({
    speaker: "Speaker",
    text: s.text.trim(),
    ts: s.start,
    isFinal: true
  }));
  if (!segs.length && data.text) segs.push({ speaker: "Speaker", text: data.text, ts: 0, isFinal: true });
  return segs;
}
