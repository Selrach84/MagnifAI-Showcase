const $ = (s) => document.querySelector(s);

async function send(msg) { return chrome.runtime.sendMessage(msg); }

async function refresh() {
  const st = await send({ type: "get-state" });
  const primary = $("#primary");
  const warn = $("#warn");

  // config warnings
  const s = st.settings || {};
  // Free engine works with no keys; only nudge about optional upgrades.
  const msgs = [];
  if (!s.anthropicKey && !s.openaiKey) msgs.push("AI summaries off — add an LLM key in Settings to enable (transcription works free).");
  else if (!s.deepgramKey) msgs.push("Using free captions (your voice). Add a Deepgram key for all-party speaker labels.");
  if (msgs.length) { warn.hidden = false; warn.textContent = "ℹ " + msgs.join(" "); }
  else warn.hidden = true;

  if (st.active) {
    $("#status-line").textContent = `Recording: ${st.active.title || "call"}`;
    primary.textContent = "■ Stop & save";
    primary.classList.add("recording");
    primary.onclick = async () => { await send({ type: "stop" }); setTimeout(refresh, 300); };
  } else {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    $("#status-line").textContent = tab ? `Ready: ${truncate(tab.title, 34)}` : "No active tab";
    primary.textContent = "● Record this tab";
    primary.classList.remove("recording");
    primary.onclick = async () => {
      await send({ type: "start", tabId: tab.id, meta: { title: tab.title } });
      setTimeout(refresh, 400);
    };
  }
}

function truncate(s = "", n) { return s.length > n ? s.slice(0, n) + "…" : s; }

$("#open-dash").onclick = () => chrome.tabs.create({ url: chrome.runtime.getURL("dashboard.html") });
$("#open-opts").onclick = () => chrome.runtime.openOptionsPage();

// count saved meetings
(async () => {
  try {
    const db = await import(chrome.runtime.getURL("lib/db.js"));
    const all = await db.listMeetings();
    $("#count").textContent = all.length;
  } catch { $("#count").textContent = "0"; }
})();

refresh();
