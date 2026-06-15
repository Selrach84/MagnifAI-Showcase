# Video to Notes — AI-Powered Lecture & Tutorial Transcription

> Turn any tutorial, lecture, or training video into structured study notes with screenshots, timestamped transcripts, and AI synthesis.

**Stack:** Python · Claude API · yt-dlp · ffmpeg · Whisper

## The problem

Training videos and tutorials contain valuable knowledge locked inside video format. Watching and manually taking notes is slow. Hiring teams waste hours re-watching onboarding videos. Key information gets lost.

## The solution

An AI agent that takes a video URL and produces a complete study package:

1. **Downloads** the video via yt-dlp (YouTube, Vimeo, or any supported platform)
2. **Transcribes** audio via Whisper API or fetches existing captions
3. **Detects scene changes** via ffmpeg — captures screenshots at each transition
4. **Synthesizes** the transcript + screenshots through Claude into structured notes
5. **Outputs** a markdown document with timed screenshots, transcript highlights, and key takeaways

## Architecture

```
Video URL
    │
    ▼
Download (yt-dlp)
    │
    ├── Audio → Whisper API / Captions → Transcript
    │
    └── Video → ffmpeg scene detection → Screenshots (timed)
                            │
                            ▼
              Claude synthesis → Structured Notes (.md)
```

## Key design decisions

- **Security-first**: SSRF protection, URL validation, path allow-listing — built for safety in production
- **Plugin system**: Installable as Claude Code plugin, claude.ai skill, or Codex plugin
- **Session hooks**: Automatically processes videos when you share a URL in a Claude Code session
- **Local-first**: Everything runs on your machine — no cloud dependency beyond the LLM API call
- **Cost-effective**: Only LLM API cost for the synthesis step; transcription is local or via low-cost Whisper

## Key features

| Feature | Description |
|---------|-------------|
| Video transcription | Whisper API or auto-fetch captions |
| Timestamped screenshots | Auto-captured at scene transitions |
| Claude synthesis | Transcript + visuals → structured notes |
| Local library | All output organized in a local vault |
| Plugin support | Claude Code, claude.ai, Codex |
| Security hardened | SSRF guard, path allow-lists, URL validation |

## Files

| File | What |
|------|------|
| `scripts/watch.py` | Main orchestrator |
| `scripts/security.py` | URL/path validation (SSRF protection) |
| `scripts/download.py` | Video download via yt-dlp |
| `scripts/transcribe.py` | Caption fetching |
| `scripts/whisper.py` | Whisper API client |
| `scripts/scenes.py` | Scene detection via ffmpeg |
| `scripts/frames.py` | Frame extraction |
| `scripts/setup.py` | Installation preflight |
| `scripts/resolve.py` | URL resolution |
| `scripts/library.py` | Local library management |
| `commands/` | Claude Code slash commands |
| `hooks/` | Session automation hooks |
| `tests/` | 12 test files with fixtures |

## Testing

- 12 test files covering security, download, transcription, scene detection, frames, and E2E flow
- CI configuration included (`.github/`)
- Security audit in SECURITY.md

## License

MIT — free to use, modify, and distribute.

## Status

Open-source · Built · Tested · Security-audited
