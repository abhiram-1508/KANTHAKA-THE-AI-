# JARVIS Desktop (Windows)

Local AI brain (Ollama) + local speech (Whisper, Piper). Only Gmail uses the internet, read-only.
Settings live in `C:\Users\<you>\.jarvis\settings.json` (created on first run).

## 1. Install the engines
- Python 3.10+ (tick "Add to PATH") and Ollama: https://ollama.com
- In a terminal:  `ollama pull llama3.1:8b`   (weak PC: `llama3.2:3b`, then set "model" in settings.json)

## 2. Install dependencies
    cd jarvis_desktop
    pip install -r requirements.txt

## 3. Download the voice (one time)
    python -m piper.download_voices en_GB-alan-medium --data-dir "%USERPROFILE%\.jarvis\voices"
(If this fails, JARVIS falls back to the built-in Windows voice. Other voices: browse "Piper voices".)

## 4. Connect Gmail (one time, ~5 min)
1. console.cloud.google.com -> create a project -> APIs & Services -> enable **Gmail API**.
2. OAuth consent screen -> External -> add your own Gmail as a **Test user**.
3. Credentials -> Create credentials -> OAuth client ID -> **Desktop app** -> download the JSON.
4. Save it as `C:\Users\<you>\.jarvis\credentials.json`.
5. Start JARVIS; a browser opens once to approve **read-only** access.
Note: apps left in "Testing" make Google expire the login every 7 days. To stop that, set the
consent screen's publishing status to "In production" (personal use, ignore the unverified warning).

## 5. Run
    python main.py
Say "Jarvis, ..." then keep talking naturally (it stays awake 25 s after each reply).

## Try saying
- "Jarvis, check my email" / "Jarvis, good morning"
- "Summarize the placement email"
- "Draft a reply to the research paper email" (draft only, nothing is ever sent)
- "Remember that my placement interview prep is on Fridays"
- "Open Chrome" / "Open Notepad" (allow-list in actions.py, add more in ~/.jarvis/apps.json)
- Anything else: normal conversation, with memory of what you told it.

## Behaviour
- Startup: first launch each day gives a spoken briefing. Every 10 min it checks mail and
  alerts (tray notification + voice) on new important emails and deadlines within 2 days.
- Closing the window hides it to the tray; right-click the tray icon to quit.
- Only your Primary tab, last 3 days, is scanned (change "gmail_query" to widen it).
- Mic mutes itself while JARVIS speaks, so it won't hear itself.
