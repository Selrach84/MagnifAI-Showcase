// background.js — service worker orchestrator.
// Owns: settings, offscreen lifecycle, recording state, native call detection,
// storage, post-call summary, and auto-export.

import { createMeeting, updateMeeting, appendSegment, getMeeting, saveAudio } from "./lib/db.js";
import { summarize } from "./lib/summarize.js";
import { transcribeBlob } from "./lib/whisper.js";

const DEFAULT_SETTINGS = {
  sttEngine: "auto",       // auto = free Web Speech unless a Deepgram key is set
  deepgramKey: "",
  llmProvider: "anthropic",
  anthropicKey: "",
  anthropicModel: "claude-opus-4-8",
  openaiKey: "",
  openaiModel: "gpt-4o",
  captureMic: true,
  language: "en",
  autoAsk: true,           // auto-prompt when a call is detected
  autoSummarize: true,
  autoExport: false,       // auto-write markdown via downloads on stop
  nativeDetect: true       // listen to the Mac native call detector
};

// active recording: { meetingId, tabId, title, segments:[] }
let active = null;
let nativePort = null;

// ---------- settings ----------
async function getSettings() {
  const { settings } = await chrome.storage.local.get("settings");
  return { ...DEFAULT_SETTINGS, ...(settings || {}) };
}

// ---------- offscreen lifecycle ----------
async function ensureOffscreen() {
  const has = await chrome.offscreen.hasDocument?.();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: "offscreen.html",
    reasons: ["USER_MEDIA"],
    justification: "Capture and transcribe call audio."
  });
}

// ---------- recording control ----------
async function startRecording(tabId, meta = {}) {
  if (active) throw new Error("Already recording: " + active.meetingId);
  const settings = await getSettings();
  const tab = await chrome.tabs.get(tabId);

  const streamId = await chrome.tabCapture.getMediaStreamId({ targetTabId: tabId });
  await ensureOffscreen();

  const meetingId = "m_" + Date.now();
  const meeting = {
    id: meetingId,
    title: meta.title || tab.title || "Untitled call",
    url: tab.url || meta.url || "",
    source: meta.source || "browser",
    platform: meta.platform || detectPlatform(tab.url),
    startedAt: Date.now(),
    endedAt: null,
    status: "recording",
    segments: [],
    notes: null
  };
  await createMeeting(meeting);
  active = { meetingId, tabId, title: meeting.title };

  await chrome.runtime.sendMessage({
    target: "offscreen", type: "start-capture", streamId, meetingId, settings
  });

  await setBadge(tabId, "REC");
  broadcast({ type: "recording-started", meetingId, title: meeting.title });
  return meetingId;
}

async function stopRecording() {
  if (!active) return;
  const { meetingId } = active;
  await chrome.runtime.sendMessage({ target: "offscreen", type: "stop-capture" });
  await updateMeeting(meetingId, { status: "processing", endedAt: Date.now() });
  await setBadge(active.tabId, "");
  active = null;
  broadcast({ type: "recording-stopped", meetingId });
  // offscreen will send 'recording-done' which finishes processing.
}

function detectPlatform(url = "") {
  if (url.includes("meet.google")) return "Google Meet";
  if (url.includes("zoom.us")) return "Zoom";
  if (url.includes("teams.")) return "Microsoft Teams";
  if (url.includes("webex")) return "Webex";
  if (url.includes("slack")) return "Slack";
  if (url.includes("discord")) return "Discord";
  if (url.includes("whereby")) return "Whereby";
  return "Web";
}

async function setBadge(tabId, text) {
  try {
    await chrome.action.setBadgeBackgroundColor({ color: "#e2483d" });
    await chrome.action.setBadgeText({ text });
  } catch {}
}

function broadcast(msg) {
  chrome.runtime.sendMessage(msg).catch(() => {});
}

// ---------- post-call processing ----------
async function finishProcessing(meetingId, audioBuf, mime, inlineSegments) {
  const settings = await getSettings();
  const blob = new Blob([audioBuf], { type: mime || "audio/webm" });
  await saveAudio(meetingId, blob);

  let meeting = await getMeeting(meetingId);

  // Persist inline (local Whisper) segments race-free if not already stored.
  if (inlineSegments && inlineSegments.length && (!meeting.segments || meeting.segments.length === 0)) {
    for (const s of inlineSegments) await appendSegment(meetingId, s);
    meeting = await getMeeting(meetingId);
  }

  // Cloud Whisper fallback only if we still have no transcript.
  if ((!meeting.segments || meeting.segments.length === 0)) {
    try {
      const segs = await transcribeBlob(blob, settings);
      for (const s of segs) await appendSegment(meetingId, s);
      meeting = await getMeeting(meetingId);
    } catch (e) {
      console.warn("Whisper fallback failed:", e);
    }
  }

  const transcript = segmentsToText(meeting.segments || []);
  let notes = null;
  if (settings.autoSummarize && transcript.trim() && (settings.anthropicKey || settings.openaiKey)) {
    try {
      notes = await summarize(transcript, settings, {
        title: meeting.title, participants: []
      });
    } catch (e) {
      console.warn("Summarize failed:", e);
      notes = { error: String(e) };
    }
  }
  await updateMeeting(meetingId, { status: "done", notes });

  if (settings.autoExport) {
    try { await exportMarkdown(meetingId); } catch (e) { console.warn("export failed", e); }
  }

  notify("Echo — call saved", `"${meeting.title}" transcribed${notes && !notes.error ? " + summarized" : ""}.`);
  broadcast({ type: "meeting-finalized", meetingId });
}

function segmentsToText(segments) {
  // collapse interim duplicates: keep finals, plus trailing interim
  const finals = segments.filter((s) => s.isFinal);
  const use = finals.length ? finals : segments;
  return use.map((s) => `[${fmtTs(s.ts)}] ${s.speaker}: ${s.text}`).join("\n");
}

function fmtTs(sec = 0) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// ---------- markdown export (Obsidian-friendly) ----------
async function buildMarkdown(meetingId) {
  const m = await getMeeting(meetingId);
  const n = m.notes && !m.notes.error ? m.notes : null;
  const date = new Date(m.startedAt);
  const dur = m.endedAt ? Math.round((m.endedAt - m.startedAt) / 60000) : 0;
  let md = `---
title: ${JSON.stringify(n?.title || m.title)}
date: ${date.toISOString()}
platform: ${m.platform}
duration_min: ${dur}
source: echo
tags: [meeting${n?.topics ? ", " + n.topics.map((t) => t.replace(/\s+/g, "-")).join(", ") : ""}]
---

# ${n?.title || m.title}

**When:** ${date.toLocaleString()}  •  **Platform:** ${m.platform}  •  **Duration:** ${dur} min
`;
  if (n) {
    md += `\n## Summary\n${n.summary || ""}\n`;
    if (n.actionItems?.length) {
      md += `\n## Action Items\n` + n.actionItems.map(
        (a) => `- [ ] **${a.owner || "unassigned"}**: ${a.task}${a.due ? ` _(due ${a.due})_` : ""}`
      ).join("\n") + "\n";
    }
    if (n.decisions?.length) md += `\n## Decisions\n` + n.decisions.map((d) => `- ${d}`).join("\n") + "\n";
    if (n.questions?.length) md += `\n## Open Questions\n` + n.questions.map((q) => `- ${q}`).join("\n") + "\n";
    if (n.highlights?.length) md += `\n## Highlights\n` + n.highlights.map((h) => `- \`${h.ts}\` "${h.quote}"`).join("\n") + "\n";
    if (n.sentiment) md += `\n**Sentiment:** ${n.sentiment}\n`;
  }
  md += `\n## Transcript\n\n${segmentsToText(m.segments || [])}\n`;
  return md;
}

async function exportMarkdown(meetingId) {
  const md = await buildMarkdown(meetingId);
  const m = await getMeeting(meetingId);
  const safe = (m.notes?.title || m.title || "call").replace(/[^\w\- ]+/g, "").slice(0, 60).trim();
  const fname = `Echo Meetings/${new Date(m.startedAt).toISOString().slice(0, 10)} ${safe}.md`;
  const url = "data:text/markdown;charset=utf-8," + encodeURIComponent(md);
  await chrome.downloads.download({ url, filename: fname, saveAs: false });
}

// ---------- notifications ----------
function notify(title, message, buttons) {
  const opts = {
    type: "basic", iconUrl: "icons/icon128.png", title, message, priority: 2
  };
  if (buttons) opts.buttons = buttons;
  return new Promise((res) => chrome.notifications.create("", opts, res));
}

// "Ask to save" prompt for a detected call.
const pendingAsk = new Map(); // notificationId -> {tabId|null, meta}
async function askToSave(meta) {
  const id = await new Promise((res) =>
    chrome.notifications.create("", {
      type: "basic", iconUrl: "icons/icon128.png",
      title: "Echo detected a call",
      message: `${meta.platform || meta.app || "A call"} is active. Record & transcribe it?`,
      buttons: [{ title: "Save it" }, { title: "Ignore" }],
      requireInteraction: true, priority: 2
    }, res)
  );
  pendingAsk.set(id, meta);
}

chrome.notifications.onButtonClicked.addListener(async (notifId, btnIdx) => {
  const meta = pendingAsk.get(notifId);
  if (!meta) return;
  pendingAsk.delete(notifId);
  chrome.notifications.clear(notifId);
  if (btnIdx !== 0) return; // ignore
  try {
    if (meta.source === "native") {
      // desktop app call → ask native host to record
      startNativeRecording(meta);
    } else if (meta.tabId != null) {
      await startRecording(meta.tabId, meta);
    }
  } catch (e) {
    notify("Echo — couldn't start", String(e));
  }
});

// ---------- native messaging (Mac desktop call detection) ----------
function connectNative() {
  try {
    nativePort = chrome.runtime.connectNative("com.echo.calldetector");
  } catch (e) {
    console.warn("native connect failed", e);
    return;
  }
  nativePort.onMessage.addListener(async (msg) => {
    if (msg.event === "call-started") {
      const settings = await getSettings();
      if (settings.autoAsk) askToSave({ source: "native", app: msg.app, platform: msg.app, title: msg.title || msg.app });
    } else if (msg.event === "record-saved") {
      notify("Echo — desktop call saved", `Saved to ${msg.path}`);
    } else if (msg.event === "error") {
      console.warn("native error", msg.error);
    }
  });
  nativePort.onDisconnect.addListener(() => {
    nativePort = null;
    // retry later
    chrome.alarms.create("native-retry", { delayInMinutes: 1 });
  });
}

function startNativeRecording(meta) {
  if (!nativePort) connectNative();
  nativePort?.postMessage({ cmd: "start-record", app: meta.app });
}

chrome.alarms.onAlarm.addListener(async (a) => {
  if (a.name === "native-retry") {
    const s = await getSettings();
    if (s.nativeDetect && !nativePort) connectNative();
  }
});

// ---------- message routing ----------
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  // from offscreen
  if (msg.source === "offscreen") {
    if (msg.type === "segment") {
      appendSegment(msg.meetingId, msg.segment).catch(() => {});
      broadcast({ type: "live-segment", meetingId: msg.meetingId, segment: msg.segment });
    } else if (msg.type === "status") {
      updateMeeting(msg.meetingId, { status: msg.status }).catch(() => {});
      broadcast({ type: "status", meetingId: msg.meetingId, status: msg.status });
    } else if (msg.type === "model-progress") {
      broadcast({ type: "model-progress", meetingId: msg.meetingId, progress: msg.progress });
    } else if (msg.type === "recording-done") {
      finishProcessing(msg.meetingId, msg.audio, msg.mime, msg.segments).catch((e) => console.warn(e));
    } else if (msg.type === "warn") {
      console.warn("offscreen:", msg.warn);
    } else if (msg.type === "error") {
      console.warn("offscreen error:", msg.error);
      updateMeeting(msg.meetingId, { status: "error" }).catch(() => {});
      active = null;
    }
    return;
  }

  // free Web Speech captions from a content script
  if (msg.type === "web-speech-segment") {
    if (active) {
      appendSegment(active.meetingId, msg.segment).catch(() => {});
      broadcast({ type: "live-segment", meetingId: active.meetingId, segment: msg.segment });
    }
    return; // no async response needed
  }

  // command API (popup, content, dashboard)
  (async () => {
    try {
      switch (msg.type) {
        case "get-state":
          sendResponse({ active: active ? { ...active } : null, settings: await getSettings() });
          break;
        case "start":
          sendResponse({ meetingId: await startRecording(msg.tabId ?? sender.tab?.id, msg.meta || {}) });
          break;
        case "stop":
          await stopRecording(); sendResponse({ ok: true });
          break;
        case "ask-to-save":
          await askToSave({ ...msg.meta, tabId: sender.tab?.id ?? msg.tabId, source: "browser" });
          sendResponse({ ok: true });
          break;
        case "export":
          await exportMarkdown(msg.meetingId); sendResponse({ ok: true });
          break;
        case "get-markdown":
          sendResponse({ md: await buildMarkdown(msg.meetingId) });
          break;
        default:
          sendResponse({ error: "unknown message: " + msg.type });
      }
    } catch (e) {
      sendResponse({ error: String(e) });
    }
  })();
  return true; // async
});

// keyboard shortcut
chrome.commands.onCommand.addListener(async (cmd) => {
  if (cmd !== "toggle-recording") return;
  if (active) return stopRecording();
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (tab) startRecording(tab.id, {});
});

// init
chrome.runtime.onStartup.addListener(initNative);
chrome.runtime.onInstalled.addListener(initNative);
async function initNative() {
  const s = await getSettings();
  if (s.nativeDetect) connectNative();
}
