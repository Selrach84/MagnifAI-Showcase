# Jitsi Meetings v3 — Zoom-style Calls + Multistream

> A Chrome MV3 extension that turns Jitsi Meet into a Zoom-like experience with multi-platform livestreaming to YouTube, Facebook, Twitch, TikTok, Instagram, LinkedIn, X, and Kick simultaneously.

**Stack:** Chrome MV3 · Jitsi Meet API · Jibri · ffmpeg · nginx-rtmp

## The problem

Jitsi Meet is a powerful open-source video conferencing platform, but its UI is utilitarian and it lacks the pro features users expect: Zoom-style layouts, MP4 recording, breakout rooms, and livestreaming.

## The solution

A Chrome extension that overlays a polished Zoom-like experience on top of Jitsi, adding:

- **Zoom-style UI** — gallery view, screen share, chat, participants, raise hand
- **MP4 recording** — local recording (Chrome/Brave ≥126)
- **Breakout rooms** — for workshops and large meetings
- **Large-meeting mode** — up to 1,000 participants
- **Multi-platform livestreaming** — stream to YouTube, Facebook, Twitch, TikTok, Instagram, LinkedIn, X, Kick simultaneously

## How streaming works

Browsers can't push RTMP directly, so streaming runs server-side through Jitsi's Jibri. The extension orchestrates it:

```
             ┌── Single mode ──────────────────────────────┐
Jitsi (Jibri) ── RTMP ──> one platform (e.g. YouTube)
             └─────────────────────────────────────────────┘

             ┌── Relay mode (all platforms at once) ───────┐
Jitsi (Jibri) ── RTMP ──> your relay ──┬─> YouTube
                                        ├─> Facebook
   relay = ffmpeg tee / nginx-rtmp /    ├─> TikTok
   Restream.io / Cloudflare Stream      ├─> Instagram
                                        └─> … every destination
```

The extension **generates the exact relay config** (ffmpeg `tee` command + nginx-rtmp conf) from the platform keys you enter.

## Features

| Feature | Status |
|---------|--------|
| Zoom-style meeting UI | ✅ |
| New/Join/Schedule/Recent meetings | ✅ |
| Gallery view + screen share | ✅ |
| Chat + participants (with count) | ✅ |
| Raise hand | ✅ |
| MP4 recording | ✅ |
| Breakout rooms | ✅ |
| Large-meeting mode (≤1000) | ✅ |
| Single-platform livestream | ✅ |
| Multi-platform livestream (relay) | ✅ |
| Configurable Jitsi server | ✅ |

## Testing

```bash
node tests/run.js     # Unit + breakout + MP4 + Go Live wiring + ffmpeg/nginx generators
node tests/smoke.js   # Real meeting.html + bundled external_api.js loads
node tests/live.js    # E2E: real extension joins a real call, records .mp4, verifies Go Live wiring
```

All passing: unit PASS, smoke PASS, live PASS (real .mp4 produced, Go Live wiring verified).

## Files

| File | What |
|------|------|
| `manifest.json` | Chrome MV3 extension manifest |
| `popup.*` | Toolbar popup (meeting controls, Go Live, settings) |
| `meeting.*` | Meeting page (Jitsi iframe + UI overlay) |
| `offline.js` | Extension background logic |
| `tests/` | Unit, smoke, and live E2E tests |

## Setup

```
chrome://extensions → Developer mode ON → Load unpacked → select directory
```

## Honest limitations

- Streaming requires Jibri (JaaS or self-hosted Jitsi)
- Multi-platform streaming needs a relay (your ffmpeg/nginx or Restream/Cloudflare)
- Instagram has no official RTMP; TikTok/LinkedIn/X give per-broadcast URLs
- MP4 recording needs Chrome/Brave ≥126
