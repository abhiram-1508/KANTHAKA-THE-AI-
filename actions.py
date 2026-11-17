"""PC control. JARVIS can only open things on these allow-lists (edit ~/.jarvis/apps.json to add more)."""
import json
import os
import subprocess
import webbrowser

import config

APPS = {
    "notepad": "notepad.exe", "calculator": "calc.exe", "paint": "mspaint.exe",
    "file explorer": "explorer.exe", "explorer": "explorer.exe", "task manager": "taskmgr.exe",
    "command prompt": "cmd.exe", "settings": "ms-settings:", "chrome": "chrome",
    "edge": "msedge", "firefox": "firefox", "vs code": "code", "word": "winword",
    "excel": "excel", "powerpoint": "powerpnt", "spotify": "spotify",
}
SITES = {
    "gmail": "https://mail.google.com", "youtube": "https://youtube.com",
    "google": "https://google.com", "github": "https://github.com",
    "chatgpt": "https://chatgpt.com", "calendar": "https://calendar.google.com",
}

_user = config.HOME / "apps.json"
if _user.exists():
    try:
        APPS.update(json.loads(_user.read_text()))
    except Exception:
        pass


def open_target(name: str) -> str:
    name = name.lower().strip(" .")
    if name in SITES:
        webbrowser.open(SITES[name])
        return f"Opening {name}."
    cmd = APPS.get(name)
    if not cmd:
        return f"I'm not permitted to open '{name}'. You can add it to apps.json."
    try:
        if cmd.endswith(":"):
            os.startfile(cmd)
        else:
            subprocess.Popen(f'start "" "{cmd}"', shell=True)  # cmd comes only from the allow-list
        return f"Opening {name}."
    except Exception as e:
        return f"I couldn't open {name}: {e}"
