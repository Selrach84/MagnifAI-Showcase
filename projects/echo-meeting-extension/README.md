# Echo — AI Meeting Notetaker

> A privacy-first Fireflies alternative. Records, transcribes (live with speaker labels), summarizes, and files every call — in your browser and from Mac desktop apps.

**Stack:** Chrome MV3 · Whisper (local, free) · Deepgram · Claude/GPT · Obsidian · IndexedDB

## The problem

Meeting notetakers like Fireflies cost $10-19/seat/month, require a bot to join your calls (awkward for external meetings), and store your data in someone else's cloud. For developers and privacy-conscious teams, there was no good self-hosted alternative.

## The solution

A Chrome extension + macOS native helper that:
- **Auto-detects** calls on Meet, Zoom, Teams, Webex, Slack, Discord, Whereby — plus Mac desktop apps
- **Asks** to record when a call starts (no bot to invite)
- **Transcribes** locally with Whisper (free, ~40MB, offline) or optionally Deepgram for live diarized captions
- **Summarizes** with Claude or GPT (action items, decisions, open questions, highlights)
- **Exports** to Obsidian as formatted markdown with frontmatter, tasks, and `[[wikilinks]]`
- **Stores everything locally** — your data never touches a cloud you don't control

## Architecture

```
extension/               Chrome MV3 extension (the whole browser experience)
  manifest.json
  background.js           orchestrator: recording state, storage, summary, export, native bridge
  offscreen.js            audio capture (tab + mic mix)
  content.js / .css       in-page widget: detects calls, live captions, record button
  popup.*                 toolbar popup (start/stop, status)
  options.*               API keys + automation toggles
  dashboard.*             browse/search/play/ask/export past calls
  lib/db.js               IndexedDB (meetings + audio blobs)
  lib/deepgram.js         live streaming STT
  lib/whisper.js          batch STT fallback (OpenAI Whisper)
  lib/summarize.js        LLM notes + "Ask Echo" (Anthropic or OpenAI)
native/                  macOS native messaging host (desktop-app calls)
  call_detector.py        polls for active calls, records via ffmpeg, transcribes, writes vault md
  install.sh              registers the host with your browser
  config.example.json     ~/.echo/config.json template
tests/                    Unit + E2E + real audio pipeline tests
```

## Key design decisions

- **Free by default**: Local Whisper in-browser (WASM, ~40MB, downloads once). No API key needed for transcription.
- **Privacy-first**: Audio + transcripts stay on your machine. Only transcript text leaves for optional AI summary.
- **Dual mode**: In-browser for web meetings, native macOS helper for desktop apps (Zoom app, FaceTime).
- **No bot required**: Unlike Fireflies, Echo doesn't need to "join" the meeting — it captures from your browser tab.

## Testing

| Test | What it proves |
|------|---------------|
| DSP unit tests | Downsampling + PCM encoding correctness |
| Browser E2E | Extension loads in real Chromium, IndexedDB works, all modules import |
| Native host E2E | Native messaging frame encode/decode round-trip, macOS call detection |
| Real audio pipeline | MediaRecorder → encode → IndexedDB → decode → PCM → websocket → parse → markdown — end-to-end with real audio |
| Local Whisper test | Real speech fed through WASM Whisper in the extension returns correct transcript |

All tests pass: `npm test`

## Vitals

- **Cost**: $0 for core transcription. Optional API keys for AI summaries ($0.01-0.03/meeting).
- **Data**: 100% local on your machine. IndexedDB + optional Obsidian vault export.
- **Browser**: Any Chromium (Chrome, Brave, Edge). MV3 compliant.
- **Status**: Built · Tested · Ready to ship

## Setup

```
npm test                    # Verify everything works
# Load extension/ as unpacked in chrome://extensions
# Optional: ./native/install.sh for desktop app support
```
