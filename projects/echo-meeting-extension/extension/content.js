// content.js — detects an in-progress call on supported sites, asks to save,
// and renders a floating control + live-caption widget.

(function () {
  const href = location.href;
  let asked = false;
  let recording = false;
  let widget, captionsEl, statusEl, btn;
  let recog = null;          // webkitSpeechRecognition instance (free engine)
  let recogActive = false;
  let recogStart = 0;

  // ---- free, zero-key live transcription via Chrome's Web Speech API ----
  // Captures the local mic (your side) with no API key. Deepgram (if a key is
  // set) handles full all-party diarized transcription instead.
  function startWebSpeech() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR || recogActive) return;
    try {
      recog = new SR();
      recog.continuous = true;
      recog.interimResults = true;
      recog.lang = navigator.language || "en-US";
      recogStart = Date.now();
      recog.onresult = (e) => {
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          const seg = {
            speaker: "You",
            text: r[0].transcript.trim(),
            ts: (Date.now() - recogStart) / 1000,
            isFinal: r.isFinal
          };
          if (!seg.text) continue;
          addCaption(seg);
          chrome.runtime.sendMessage({ type: "web-speech-segment", segment: seg });
        }
      };
      recog.onend = () => { if (recogActive) { try { recog.start(); } catch {} } }; // auto-restart
      recog.onerror = () => {};
      recogActive = true;
      recog.start();
    } catch {}
  }
  function stopWebSpeech() {
    recogActive = false;
    try { recog && recog.stop(); } catch {}
    recog = null;
  }

  function inCall() {
    const h = location.href;
    if (h.includes("meet.google.com")) return /\/[a-z]{3}-[a-z]{4}-[a-z]{3}/.test(h);
    if (h.includes("zoom.us")) return /\/(wc|j)\//.test(h) || !!document.querySelector("#wc-container-left, .meeting-app");
    if (h.includes("teams.")) return h.includes("meetup-join") || !!document.querySelector('[data-tid="call-roster"], [data-tid="toggle-mute"]');
    if (h.includes("webex.com")) return !!document.querySelector('[class*="meeting"]');
    if (h.includes("whereby.com")) return /\/[\w-]{6,}/.test(location.pathname);
    if (h.includes("discord.com")) return !!document.querySelector('[class*="rtcConnectionStatus"], [aria-label*="Voice Connected"]');
    if (h.includes("slack.com")) return !!document.querySelector('[data-qa="huddle_in_huddle"]');
    return false;
  }

  function platform() {
    const h = location.href;
    if (h.includes("meet.google")) return "Google Meet";
    if (h.includes("zoom.us")) return "Zoom";
    if (h.includes("teams.")) return "Microsoft Teams";
    if (h.includes("webex")) return "Webex";
    if (h.includes("whereby")) return "Whereby";
    if (h.includes("discord")) return "Discord";
    if (h.includes("slack")) return "Slack";
    return "Web call";
  }

  function buildWidget() {
    if (widget) return;
    widget = document.createElement("div");
    widget.id = "echo-widget";
    widget.innerHTML = `
      <div id="echo-head">
        <span id="echo-dot"></span>
        <strong>Echo</strong>
        <span id="echo-status">idle</span>
        <button id="echo-close" title="Hide">×</button>
      </div>
      <div id="echo-captions"></div>
      <button id="echo-btn">● Record call</button>
    `;
    document.documentElement.appendChild(widget);
    captionsEl = widget.querySelector("#echo-captions");
    statusEl = widget.querySelector("#echo-status");
    btn = widget.querySelector("#echo-btn");
    btn.onclick = toggle;
    widget.querySelector("#echo-close").onclick = () => widget.remove();
  }

  function setStatus(s) { if (statusEl) statusEl.textContent = s; }

  async function toggle() {
    if (recording) {
      chrome.runtime.sendMessage({ type: "stop" });
    } else {
      chrome.runtime.sendMessage({ type: "start", meta: { platform: platform(), title: document.title, source: "browser" } });
    }
  }

  function addCaption(seg) {
    if (!captionsEl) return;
    // replace last interim line for same speaker, else append
    let last = captionsEl.lastElementChild;
    if (last && last.dataset.interim === "1") last.remove();
    const line = document.createElement("div");
    line.className = "echo-line";
    line.dataset.interim = seg.isFinal ? "0" : "1";
    line.innerHTML = `<span class="echo-spk">${seg.speaker}:</span> ${escapeHtml(seg.text)}`;
    captionsEl.appendChild(line);
    captionsEl.scrollTop = captionsEl.scrollHeight;
    while (captionsEl.children.length > 60) captionsEl.removeChild(captionsEl.firstChild);
  }

  function escapeHtml(s) {
    return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  chrome.runtime.onMessage.addListener(async (msg) => {
    if (msg.type === "recording-started") {
      recording = true; setStatus("● recording"); if (btn) btn.textContent = "■ Stop"; widget?.classList.add("rec");
      // Web Speech gives live captions (Chrome only). "auto"/no-key uses local
      // Whisper after the call instead (works on Brave), handled in the offscreen.
      const { settings } = await chrome.storage.local.get("settings");
      if (settings?.sttEngine === "webspeech") startWebSpeech();
    }
    if (msg.type === "recording-stopped") { recording = false; setStatus("processing…"); if (btn) btn.textContent = "● Record call"; widget?.classList.remove("rec"); stopWebSpeech(); }
    if (msg.type === "meeting-finalized") setStatus("saved ✓");
    if (msg.type === "live-segment") addCaption(msg.segment);
  });

  // poll for call state
  let tries = 0;
  const iv = setInterval(async () => {
    if (inCall()) {
      buildWidget();
      if (!asked) {
        asked = true;
        const { settings } = await chrome.storage.local.get("settings");
        if (settings?.autoAsk !== false) {
          chrome.runtime.sendMessage({ type: "ask-to-save", meta: { platform: platform(), title: document.title } });
        }
      }
    }
    if (++tries > 1200) clearInterval(iv); // ~1hr safety
  }, 3000);
})();
