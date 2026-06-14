import { listMeetings, getMeeting, getAudio, deleteMeeting } from "./lib/db.js";
import { askTranscript } from "./lib/summarize.js";

const $ = (s) => document.querySelector(s);
let meetings = [];
let current = null;
let audioUrl = null;

function fmtTs(sec = 0) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
function esc(s = "") { return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }

async function loadList(filter = "") {
  meetings = await listMeetings();
  const f = filter.toLowerCase();
  const filtered = meetings.filter((m) => {
    if (!f) return true;
    const hay = (m.title + " " + (m.platform || "") + " " +
      (m.segments || []).map((s) => s.text).join(" ") + " " +
      (m.notes?.summary || "")).toLowerCase();
    return hay.includes(f);
  });
  const list = $("#list");
  list.innerHTML = "";
  if (!filtered.length) { list.innerHTML = `<div style="color:#6b7080;padding:10px;font-size:12px">No calls yet.</div>`; return; }
  for (const m of filtered) {
    const el = document.createElement("div");
    el.className = "item" + (current && current.id === m.id ? " active" : "");
    const badge = m.status === "recording" ? `<span class="badge rec">REC</span>`
      : m.status === "processing" ? `<span class="badge">…</span>`
      : m.status === "error" ? `<span class="badge">err</span>` : "";
    el.innerHTML = `<div class="t">${esc(m.notes?.title || m.title)}${badge}</div>
      <div class="s">${esc(m.platform || "Web")} · ${new Date(m.startedAt).toLocaleString()}</div>`;
    el.onclick = () => openMeeting(m.id);
    list.appendChild(el);
  }
}

async function openMeeting(id) {
  current = await getMeeting(id);
  $("#empty").hidden = true;
  $("#detail").hidden = false;
  $("#d-title").textContent = current.notes?.title || current.title;
  const dur = current.endedAt ? Math.round((current.endedAt - current.startedAt) / 60000) : 0;
  $("#d-meta").textContent = `${current.platform || "Web"} · ${new Date(current.startedAt).toLocaleString()} · ${dur} min · ${current.status}`;

  // audio
  if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null; }
  const blob = await getAudio(id);
  const player = $("#player");
  if (blob) { audioUrl = URL.createObjectURL(blob); player.src = audioUrl; player.hidden = false; }
  else player.hidden = true;

  renderNotes();
  renderTranscript();
  $("#chat").innerHTML = "";
  switchTab("notes");
  loadList($("#search").value);
}

function renderNotes() {
  const n = current.notes;
  const pane = $("#tab-notes");
  if (!n || n.error) {
    pane.innerHTML = `<div class="notes-card"><p>${n?.error ? "Summary failed: " + esc(n.error) : "No AI summary. Add an LLM key in Settings, then re-record — or summaries run automatically after each call."}</p></div>`;
    return;
  }
  let h = "";
  if (n.summary) h += card("Summary", `<p>${esc(n.summary)}</p>`);
  if (n.actionItems?.length) h += card("Action Items", n.actionItems.map(
    (a) => `<div class="ai-item">☐ <b>${esc(a.owner || "unassigned")}</b>: ${esc(a.task)}${a.due ? ` <i>(due ${esc(a.due)})</i>` : ""}</div>`).join(""));
  if (n.decisions?.length) h += card("Decisions", n.decisions.map((d) => `<div class="ai-item">• ${esc(d)}</div>`).join(""));
  if (n.questions?.length) h += card("Open Questions", n.questions.map((q) => `<div class="ai-item">? ${esc(q)}</div>`).join(""));
  if (n.highlights?.length) h += card("Highlights", n.highlights.map((x) => `<div class="ai-item"><code>${esc(x.ts)}</code> “${esc(x.quote)}”</div>`).join(""));
  if (n.topics?.length) h += card("Topics", n.topics.map((t) => `<span class="chip">${esc(t)}</span>`).join(""));
  if (n.sentiment) h += `<div class="notes-card">Sentiment: <b>${esc(n.sentiment)}</b></div>`;
  pane.innerHTML = h;
}
function card(title, body) { return `<div class="notes-card"><h3>${title}</h3>${body}</div>`; }

function renderTranscript() {
  const segs = (current.segments || []).filter((s) => s.isFinal);
  const use = segs.length ? segs : (current.segments || []);
  const pane = $("#tab-transcript");
  if (!use.length) { pane.innerHTML = `<p style="color:#6b7080">No transcript.</p>`; return; }
  pane.innerHTML = use.map((s) =>
    `<div class="seg"><span class="ts" data-t="${s.ts}">${fmtTs(s.ts)}</span><span class="sp">${esc(s.speaker)}</span><span>${esc(s.text)}</span></div>`
  ).join("");
  pane.querySelectorAll(".ts").forEach((el) => el.onclick = () => {
    const p = $("#player"); if (!p.hidden) { p.currentTime = parseFloat(el.dataset.t) || 0; p.play(); }
  });
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  $("#tab-notes").hidden = name !== "notes";
  $("#tab-transcript").hidden = name !== "transcript";
  $("#tab-ask").hidden = name !== "ask";
}

// events
document.querySelectorAll(".tab").forEach((t) => t.onclick = () => switchTab(t.dataset.tab));
$("#search").oninput = (e) => loadList(e.target.value);
$("#opts").onclick = () => chrome.runtime.openOptionsPage();

$("#export").onclick = async () => {
  await chrome.runtime.sendMessage({ type: "export", meetingId: current.id });
};
$("#copy").onclick = async () => {
  const { md } = await chrome.runtime.sendMessage({ type: "get-markdown", meetingId: current.id });
  await navigator.clipboard.writeText(md);
  $("#copy").textContent = "✓ Copied"; setTimeout(() => $("#copy").textContent = "⧉ Copy", 1500);
};
$("#del").onclick = async () => {
  if (!confirm("Delete this call permanently?")) return;
  await deleteMeeting(current.id); current = null;
  $("#detail").hidden = true; $("#empty").hidden = false; loadList($("#search").value);
};

async function ask() {
  const q = $("#q").value.trim();
  if (!q || !current) return;
  $("#q").value = "";
  const chat = $("#chat");
  chat.insertAdjacentHTML("beforeend", `<div class="bubble u">${esc(q)}</div>`);
  const a = document.createElement("div"); a.className = "bubble a"; a.textContent = "…"; chat.appendChild(a);
  chat.scrollTop = chat.scrollHeight;
  try {
    const { settings } = await chrome.storage.local.get("settings");
    const segs = (current.segments || []).filter((s) => s.isFinal);
    const transcript = (segs.length ? segs : current.segments || [])
      .map((s) => `[${fmtTs(s.ts)}] ${s.speaker}: ${s.text}`).join("\n");
    a.textContent = await askTranscript(q, transcript, settings || {});
  } catch (e) { a.textContent = "Error: " + e; }
  chat.scrollTop = chat.scrollHeight;
}
$("#send").onclick = ask;
$("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });

// live updates
chrome.runtime.onMessage.addListener((msg) => {
  if (["live-segment", "recording-started", "recording-stopped", "meeting-finalized"].includes(msg.type)) {
    if (current && msg.meetingId === current.id) openMeeting(current.id);
    else loadList($("#search").value);
  }
});

loadList();
