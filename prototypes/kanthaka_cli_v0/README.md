# KANTHAKA (local)

## Setup
1. Install Python 3.10+ and Ollama (https://ollama.com).
2. Download a model:   ollama pull llama3.1:8b
   (low-end PC? use llama3.2:3b and set OLLAMA_MODEL in .env)
3. pip install -r requirements.txt
4. Copy .env.example to .env and fill in your email.
   Gmail: turn on 2-step verification, then create an App Password at
   https://myaccount.google.com/apppasswords (normal password won't work).
   Outlook: IMAP_HOST=outlook.office365.com   Yahoo: imap.mail.yahoo.com
5. python kanthaka.py            (voice: say "Kanthaka, check my email")
   python kanthaka.py --text     (typing mode, good for testing first)

## Notes
- Mail is opened read-only, so nothing gets marked as read or deleted.
- First run downloads the Whisper speech model once, then works offline.
- Say "goodbye" or "shut down" to exit.
