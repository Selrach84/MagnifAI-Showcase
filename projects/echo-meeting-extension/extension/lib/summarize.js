// summarize.js — turn a transcript into structured meeting notes via an LLM.
// Supports Anthropic and OpenAI. Returns { summary, actionItems, decisions,
// topics, questions, sentiment }.

const SYSTEM_PROMPT = `You are an elite meeting analyst. Given a raw call transcript (with speaker labels and timestamps), produce concise, high-signal notes. Be specific, never generic. Output STRICT JSON only, no markdown fences, with this shape:
{
  "title": "short descriptive meeting title",
  "summary": "3-6 sentence executive summary",
  "actionItems": [{"owner":"name or 'unassigned'","task":"...","due":"date or null"}],
  "decisions": ["..."],
  "topics": ["short topic tags"],
  "questions": ["open questions raised but unanswered"],
  "sentiment": "positive | neutral | tense | mixed",
  "highlights": [{"ts":"mm:ss","quote":"notable verbatim quote"}]
}`;

function buildUserPrompt(transcript, ctx) {
  let s = "";
  if (ctx?.title) s += `Known meeting context: ${ctx.title}\n`;
  if (ctx?.participants?.length) s += `Participants: ${ctx.participants.join(", ")}\n`;
  s += `\nTRANSCRIPT:\n${transcript}`;
  return s;
}

async function callAnthropic(key, model, system, user, baseUrl) {
  const res = await fetch((baseUrl || "https://api.anthropic.com") + "/v1/messages", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": "2023-06-01",
      "anthropic-dangerous-direct-browser-access": "true"
    },
    body: JSON.stringify({
      model: model || "claude-opus-4-8",
      max_tokens: 2000,
      system,
      messages: [{ role: "user", content: user }]
    })
  });
  if (!res.ok) throw new Error(`Anthropic ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.content.map((c) => c.text || "").join("");
}

async function callOpenAI(key, model, system, user, baseUrl) {
  const res = await fetch((baseUrl || "https://api.openai.com") + "/v1/chat/completions", {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${key}` },
    body: JSON.stringify({
      model: model || "gpt-4o",
      response_format: { type: "json_object" },
      messages: [
        { role: "system", content: system },
        { role: "user", content: user }
      ]
    })
  });
  if (!res.ok) throw new Error(`OpenAI ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return data.choices[0].message.content;
}

export async function summarize(transcript, settings, ctx) {
  const user = buildUserPrompt(transcript, ctx);
  let raw;
  if (settings.llmProvider === "openai") {
    raw = await callOpenAI(settings.openaiKey, settings.openaiModel, SYSTEM_PROMPT, user, settings.openaiBaseUrl);
  } else {
    raw = await callAnthropic(settings.anthropicKey, settings.anthropicModel, SYSTEM_PROMPT, user, settings.anthropicBaseUrl);
  }
  // tolerant JSON parse (strip accidental fences)
  const cleaned = raw.replace(/^```(json)?/i, "").replace(/```$/, "").trim();
  try {
    return JSON.parse(cleaned);
  } catch {
    const m = cleaned.match(/\{[\s\S]*\}/);
    if (m) return JSON.parse(m[0]);
    throw new Error("Could not parse LLM JSON output: " + cleaned.slice(0, 300));
  }
}

// Free-form chat over a transcript (the "Ask Echo" feature).
export async function askTranscript(question, transcript, settings) {
  const sys = "You answer questions strictly from the provided meeting transcript. If the answer isn't in it, say so. Be concise and cite speaker + timestamp when relevant.";
  const user = `TRANSCRIPT:\n${transcript}\n\nQUESTION: ${question}`;
  if (settings.llmProvider === "openai") {
    return callOpenAI(settings.openaiKey, settings.openaiModel, sys, user, settings.openaiBaseUrl);
  }
  return callAnthropic(settings.anthropicKey, settings.anthropicModel, sys, user, settings.anthropicBaseUrl);
}
