const FIELDS = ["sttEngine","deepgramKey","language","captureMic","llmProvider","anthropicKey",
  "anthropicModel","openaiKey","openaiModel","autoAsk","autoSummarize","autoExport","nativeDetect",
  "deepgramUrl","anthropicBaseUrl","openaiBaseUrl"];
const DEFAULTS = { sttEngine: "auto", language: "en", captureMic: true, llmProvider: "anthropic",
  anthropicModel: "claude-opus-4-8", openaiModel: "gpt-4o",
  autoAsk: true, autoSummarize: true, autoExport: false, nativeDetect: true };

const $ = (id) => document.getElementById(id);

function toggleProvider() {
  const p = $("llmProvider").value;
  $("anthropic-fields").style.display = p === "anthropic" ? "" : "none";
  $("openai-fields").style.display = p === "openai" ? "" : "none";
}

async function load() {
  const { settings } = await chrome.storage.local.get("settings");
  const s = { ...DEFAULTS, ...(settings || {}) };
  for (const f of FIELDS) {
    const el = $(f);
    if (!el) continue;
    if (el.type === "checkbox") el.checked = !!s[f];
    else el.value = s[f] ?? "";
  }
  toggleProvider();
}

async function save() {
  const s = {};
  for (const f of FIELDS) {
    const el = $(f);
    s[f] = el.type === "checkbox" ? el.checked : el.value.trim();
  }
  await chrome.storage.local.set({ settings: s });
  $("saved").textContent = "✓ Saved";
  setTimeout(() => ($("saved").textContent = ""), 1800);
}

$("llmProvider").addEventListener("change", toggleProvider);
$("save").addEventListener("click", save);
load();
