# Plugins / libraries / models for KANTHAKA

## A. Required (already in requirements.txt)
| Component | Purpose |
|---|---|
| Ollama + `llama3.1:8b` | Local LLM (brain). Use `llama3.2:3b` on weak PCs |
| faster-whisper | Offline speech recognition |
| piper-tts + `en_GB-alan-medium` | Offline natural voice |
| PySide6 | Desktop UI + system tray |
| sounddevice, numpy | Microphone capture / audio playback |
| google-api-python-client, google-auth-oauthlib | Gmail API (read-only) |
| pyttsx3 | Fallback voice |

## B. Strongly recommended next (highest value)
| Add-on | Why |
|---|---|
| **openWakeWord** | Real wake-word detection (needs a custom-trained "Kanthaka" model; pretrained ones only cover words like "hey jarvis") instead of transcribing everything; far lower CPU, fewer mishears |
| **silero-vad** (or webrtcvad) | Much better start/stop-of-speech detection than the energy threshold |
| **keyring** | Store the Gmail token in Windows Credential Manager, not a plain file |
| **Google Calendar API** (same OAuth, add `calendar.readonly`) | "What's on my schedule?", meeting-aware alerts |
| **`nomic-embed-text`** (Ollama model) + **chromadb** or sqlite-vec | Semantic email/memory search ("the email about my interview") instead of keyword matching |
| **pycaw + comtypes** | Volume/mute control by voice |
| **psutil** | System status ("how's my battery / CPU?") |

## C. Nice to have
| Add-on | Why |
|---|---|
| APScheduler | Reminders and timed tasks ("remind me at 6") |
| qwen2.5:7b (Ollama) | Alternative model, often better at structured JSON triage |
| pystray / win11toast | Richer native Windows notifications |
| pytest | Tests for the router and email triage |
| PyInstaller | Package into a single .exe |
| Piper alternatives (Kokoro TTS) | More expressive voice |

## D. Security rules (keep these)
- Gmail scope stays `gmail.readonly`.
- Never commit `credentials.json`, `token.json`, `.env` (already in .gitignore).
- PC control only via the allow-list in `actions.py`.
- KANTHAKA drafts replies but never sends them without a new, explicit feature + confirmation step.
