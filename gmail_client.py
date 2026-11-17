"""Read-only Gmail access. JARVIS can never send, delete or modify mail."""
import base64
import re
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def configured():
    return config.CREDS.exists()


def _service():
    creds = None
    if config.TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(config.TOKEN), SCOPES)
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(config.CREDS), SCOPES)
        creds = flow.run_local_server(port=0)  # opens browser once
    config.TOKEN.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _walk(part):
    yield part
    for c in part.get("parts") or []:
        yield from _walk(c)


def _text(payload):
    plain = html = ""
    for p in _walk(payload):
        data = p.get("body", {}).get("data")
        if not data or p.get("filename"):
            continue
        t = base64.urlsafe_b64decode(data + "==").decode("utf-8", "ignore")
        if p.get("mimeType") == "text/plain" and not plain:
            plain = t
        elif p.get("mimeType") == "text/html" and not html:
            html = t
    if not plain and html:
        html = re.sub(r"<(style|script).*?</\1>", " ", html, flags=re.S | re.I)
        plain = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", plain).strip()


def fetch(query, max_results, skip_ids=()):
    svc = _service()
    res = svc.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    out = []
    for m in res.get("messages", []):
        if m["id"] in skip_ids:
            continue
        full = svc.users().messages().get(userId="me", id=m["id"], format="full").execute()
        h = {x["name"].lower(): x["value"] for x in full["payload"]["headers"]}
        date = datetime.fromtimestamp(int(full["internalDate"]) / 1000).strftime("%Y-%m-%d %H:%M")
        out.append({"id": m["id"], "sender": h.get("from", ""), "subject": h.get("subject", "(no subject)"),
                    "date": date, "body": _text(full["payload"])[:6000]})
    return out
