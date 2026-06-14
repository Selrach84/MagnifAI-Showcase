#!/usr/bin/env python3
"""Echo native messaging host — macOS desktop call detection + (optional) recording.

Two jobs:
  1. Poll for active desktop calls (Zoom/FaceTime/Teams/Webex/Discord) and push
     {"event":"call-started"} / {"event":"call-ended"} to the extension.
  2. On {"cmd":"start-record"} record system audio via ffmpeg, then transcribe +
     summarize and write markdown into the Obsidian vault on {"cmd":"stop-record"}.

Recording requires an audio loopback device (e.g. BlackHole) + ffmpeg. Detection
works without either. Config: ~/.echo/config.json (see config.example.json).
"""
import sys, os, json, struct, threading, subprocess, time, signal, datetime, re, urllib.request, mimetypes, uuid

CONFIG_PATH = os.path.expanduser("~/.echo/config.json")
LOCK = threading.Lock()

def load_config():
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

# ---------- native messaging framing ----------
def read_msg():
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) < 4:
        return None
    (length,) = struct.unpack("<I", raw_len)
    data = sys.stdin.buffer.read(length)
    return json.loads(data.decode("utf-8"))

def send_msg(obj):
    data = json.dumps(obj).encode("utf-8")
    with LOCK:
        sys.stdout.buffer.write(struct.pack("<I", len(data)))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

# ---------- call detection ----------
APP_PROCS = {
    "zoom.us": "Zoom",
    "FaceTime": "FaceTime",
    "Microsoft Teams": "Microsoft Teams",
    "MSTeams": "Microsoft Teams",
    "Webex": "Webex",
    "Cisco Webex Meetings": "Webex",
    "Discord": "Discord",
}

# AppleScript: list window titles of frontmost-capable apps to confirm a live call.
WINDOW_SCRIPT = '''
tell application "System Events"
  set out to ""
  repeat with p in (every process whose background only is false)
    try
      repeat with w in (windows of p)
        set out to out & (name of p) & "||" & (name of w) & linefeed
      end repeat
    end try
  end repeat
end tell
return out
'''

CALL_WINDOW_HINTS = ["zoom meeting", "meeting", "facetime", "call", "huddle"]

def running_apps():
    try:
        out = subprocess.check_output(["ps", "-Axo", "comm"], text=True, timeout=5)
    except Exception:
        return set()
    found = set()
    for line in out.splitlines():
        for proc, label in APP_PROCS.items():
            if proc.lower() in line.lower():
                found.add(label)
    return found

def active_call_label():
    """Return a platform label if a call window looks active, else None."""
    apps = running_apps()
    if not apps:
        return None
    # FaceTime: hard to confirm a live call from CLI; treat running as candidate.
    try:
        win = subprocess.check_output(["osascript", "-e", WINDOW_SCRIPT], text=True, timeout=6)
    except Exception:
        win = ""
    wl = win.lower()
    # Zoom Meeting window is the strongest signal.
    if "zoom" in apps and "zoom meeting" in wl:
        return "Zoom"
    if "Microsoft Teams" in apps and ("meeting" in wl or "call" in wl):
        return "Microsoft Teams"
    if "Webex" in apps and "meeting" in wl:
        return "Webex"
    if "FaceTime" in apps and "facetime" in wl:
        return "FaceTime"
    return None

def detector_loop():
    cfg = load_config()
    interval = float(cfg.get("poll_seconds", 4))
    state = None
    while True:
        try:
            label = active_call_label()
            if label and state != label:
                state = label
                send_msg({"event": "call-started", "app": label, "title": f"{label} call"})
            elif not label and state is not None:
                send_msg({"event": "call-ended", "app": state})
                state = None
        except Exception as e:
            send_msg({"event": "error", "error": "detector: " + str(e)})
        time.sleep(interval)

# ---------- recording ----------
REC = {"proc": None, "path": None, "started": None, "app": None}

def vault_dir(cfg):
    d = cfg.get("vault_dir") or os.path.expanduser("~/EchoMeetings")
    os.makedirs(d, exist_ok=True)
    return d

def start_record(app):
    cfg = load_config()
    if REC["proc"]:
        return
    dev = cfg.get("audio_device_index", ":0")  # avfoundation audio-only ":N"
    out_dir = vault_dir(cfg)
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H-%M")
    path = os.path.join(out_dir, f"{stamp} {app} call.m4a")
    cmd = ["ffmpeg", "-y", "-f", "avfoundation", "-i", dev,
           "-ac", "1", "-ar", "16000", "-c:a", "aac", path]
    try:
        REC["proc"] = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        REC.update(path=path, started=time.time(), app=app)
        send_msg({"event": "record-started", "path": path})
    except FileNotFoundError:
        send_msg({"event": "error", "error": "ffmpeg not found. brew install ffmpeg"})

def stop_record():
    if not REC["proc"]:
        return
    try:
        REC["proc"].send_signal(signal.SIGINT)
        REC["proc"].wait(timeout=10)
    except Exception:
        try: REC["proc"].kill()
        except Exception: pass
    path = REC["path"]; app = REC["app"]
    REC.update(proc=None)
    send_msg({"event": "record-saved", "path": path})
    # transcribe + summarize in background
    threading.Thread(target=process_recording, args=(path, app), daemon=True).start()

def process_recording(path, app):
    cfg = load_config()
    try:
        segments = transcribe(path, cfg)
        transcript = "\n".join(f"{s.get('speaker','Speaker')}: {s['text']}" for s in segments)
        notes = summarize(transcript, cfg) if transcript.strip() else None
        write_markdown(path, app, transcript, notes, cfg)
        send_msg({"event": "record-processed", "path": path})
    except Exception as e:
        send_msg({"event": "error", "error": "process: " + str(e)})

def transcribe(path, cfg):
    # Prefer Deepgram (file upload), fall back to OpenAI Whisper.
    if cfg.get("deepgram_key"):
        with open(path, "rb") as f:
            data = f.read()
        req = urllib.request.Request(
            "https://api.deepgram.com/v1/listen?model=nova-2&diarize=true&punctuate=true&smart_format=true",
            data=data, method="POST",
            headers={"Authorization": "Token " + cfg["deepgram_key"], "Content-Type": "audio/m4a"})
        with urllib.request.urlopen(req, timeout=300) as r:
            j = json.load(r)
        words = j["results"]["channels"][0]["alternatives"][0].get("words", [])
        segs, cur, spk = [], [], None
        for w in words:
            s = w.get("speaker", 0)
            if spk is None: spk = s
            if s != spk and cur:
                segs.append({"speaker": f"Speaker {spk+1}", "text": " ".join(cur)}); cur = []; spk = s
            cur.append(w.get("punctuated_word", w["word"]))
        if cur: segs.append({"speaker": f"Speaker {spk+1}" if spk is not None else "Speaker", "text": " ".join(cur)})
        return segs
    if cfg.get("openai_key"):
        return whisper(path, cfg)
    return []

def whisper(path, cfg):
    boundary = uuid.uuid4().hex
    with open(path, "rb") as f:
        audio = f.read()
    parts = []
    def field(name, val):
        return (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n').encode()
    body = field("model", "whisper-1")
    fname = os.path.basename(path)
    ctype = mimetypes.guess_type(path)[0] or "audio/m4a"
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
             f'Content-Type: {ctype}\r\n\r\n').encode() + audio + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions", data=body, method="POST",
        headers={"Authorization": "Bearer " + cfg["openai_key"],
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        j = json.load(r)
    return [{"speaker": "Speaker", "text": j.get("text", "")}]

def summarize(transcript, cfg):
    sysp = ("Summarize this call. Output JSON with keys summary (string), "
            "action_items (array of strings), decisions (array), topics (array).")
    if cfg.get("anthropic_key"):
        body = json.dumps({"model": cfg.get("anthropic_model", "claude-opus-4-8"),
            "max_tokens": 1500, "system": sysp,
            "messages": [{"role": "user", "content": transcript[:60000]}]}).encode()
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST",
            headers={"x-api-key": cfg["anthropic_key"], "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            j = json.load(r)
        text = "".join(c.get("text", "") for c in j["content"])
    elif cfg.get("openai_key"):
        body = json.dumps({"model": cfg.get("openai_model", "gpt-4o"),
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": sysp},
                         {"role": "user", "content": transcript[:60000]}]}).encode()
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=body, method="POST",
            headers={"Authorization": "Bearer " + cfg["openai_key"], "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=120) as r:
            j = json.load(r)
        text = j["choices"][0]["message"]["content"]
    else:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {"summary": text}

def write_markdown(audio_path, app, transcript, notes, cfg):
    out_dir = vault_dir(cfg)
    base = os.path.splitext(os.path.basename(audio_path))[0]
    md_path = os.path.join(out_dir, base + ".md")
    now = datetime.datetime.now().isoformat()
    md = f"---\ntitle: {base}\ndate: {now}\nplatform: {app}\nsource: echo-native\ntags: [meeting]\n---\n\n# {base}\n\n"
    if notes:
        md += f"## Summary\n{notes.get('summary','')}\n\n"
        if notes.get("action_items"):
            md += "## Action Items\n" + "\n".join(f"- [ ] {a}" for a in notes["action_items"]) + "\n\n"
        if notes.get("decisions"):
            md += "## Decisions\n" + "\n".join(f"- {d}" for d in notes["decisions"]) + "\n\n"
        if notes.get("topics"):
            md += "## Topics\n" + ", ".join(notes["topics"]) + "\n\n"
    md += f"## Transcript\n\n{transcript}\n\n[[{os.path.basename(audio_path)}]]\n"
    with open(md_path, "w") as f:
        f.write(md)

# ---------- command loop ----------
def main():
    threading.Thread(target=detector_loop, daemon=True).start()
    send_msg({"event": "ready"})
    while True:
        msg = read_msg()
        if msg is None:
            break
        cmd = msg.get("cmd")
        if cmd == "ping":
            send_msg({"event": "pong"})
        elif cmd == "start-record":
            start_record(msg.get("app", "Desktop"))
        elif cmd == "stop-record":
            stop_record()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try: send_msg({"event": "error", "error": str(e)})
        except Exception: pass
