import json
from pathlib import Path

HOME = Path.home() / ".kanthaka"
HOME.mkdir(exist_ok=True)
VOICES = HOME / "voices"
VOICES.mkdir(exist_ok=True)
DB_PATH = HOME / "kanthaka.db"
CREDS = HOME / "credentials.json"
TOKEN = HOME / "token.json"
SETTINGS_FILE = HOME / "settings.json"

DEFAULTS = {
    "user_name": "sir",              # how KANTHAKA addresses you
    "model": "llama3.1:8b",          # any Ollama model (llama3.2:3b for weaker PCs)
    "whisper": "base.en",            # small.en = more accurate, slower
    "voice": "en_GB-alan-medium",    # Piper voice (British, very Kanthaka)
    "wake_words": ["kanthaka", "kantaka", "kanthika", "canthaka", "kanthaca", "kantaka", "kantha ka"],  # spellings Whisper may produce
    "poll_minutes": 10,              # how often to check Gmail
    "gmail_query": "in:inbox category:primary newer_than:3d",
    "max_emails": 25,
    "alert_deadline_days": 2,        # warn when a deadline is this close
}


def load():
    s = dict(DEFAULTS)
    if SETTINGS_FILE.exists():
        try:
            s.update(json.loads(SETTINGS_FILE.read_text()))
        except Exception:
            pass
    else:
        SETTINGS_FILE.write_text(json.dumps(s, indent=2))
    return s


S = load()
