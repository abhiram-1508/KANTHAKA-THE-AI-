"""
JARVIS - a fully local voice assistant that checks your email.

Say "Jarvis, check my email" or "Jarvis, anything important?"
Run with --text to type instead of talk.
"""
import argparse
import email
import imaplib
import json
import os
import queue
import re
import sys
from email.header import decode_header, make_header

import numpy as np
import ollama
import pyttsx3
import sounddevice as sd
from dotenv import load_dotenv
from faster_whisper import WhisperModel

load_dotenv()

EMAIL_ADDR = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASS = os.getenv("EMAIL_APP_PASSWORD", "")
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
WHISPER_SIZE = os.getenv("WHISPER_MODEL", "base.en")
USER_NAME = os.getenv("USER_NAME", "sir")
MAX_EMAILS = int(os.getenv("MAX_EMAILS", "15"))

SYSTEM_PROMPT = (
    f"You are JARVIS, a witty, calm, highly capable personal assistant, in the style "
    f"of the AI from Iron Man. Address the user as '{USER_NAME}'. Speak in short, "
    f"natural sentences (1-3 sentences unless asked for more) because your replies "
    f"are read aloud. No markdown, no lists, no emojis."
)

SR = 16000
history = [{"role": "system", "content": SYSTEM_PROMPT}]


# ---------------------------------------------------------------- speech out
_tts = pyttsx3.init()
_tts.setProperty("rate", 175)


def say(text: str):
    print(f"\nJARVIS: {text}\n")
    _tts.say(text)
    _tts.runAndWait()


# ----------------------------------------------------------------- speech in
_stt = None


def listen(threshold=0.012, silence_sec=1.0, max_sec=20) -> str:
    """Record until the user stops talking, then transcribe locally."""
    global _stt
    if _stt is None:
        _stt = WhisperModel(WHISPER_SIZE, compute_type="int8")
    q: "queue.Queue[np.ndarray]" = queue.Queue()
    frames, started, quiet = [], False, 0.0
    block = int(SR * 0.1)

    with sd.InputStream(samplerate=SR, channels=1, blocksize=block,
                        dtype="float32", callback=lambda d, *_: q.put(d.copy())):
        total = 0.0
        while total < max_sec:
            chunk = q.get()
            total += 0.1
            loud = float(np.sqrt(np.mean(chunk ** 2))) > threshold
            if loud:
                started, quiet = True, 0.0
            elif started:
                quiet += 0.1
            if started:
                frames.append(chunk)
                if quiet >= silence_sec:
                    break
            elif total > 8:  # nothing said, give back control
                return ""
    if not frames:
        return ""
    audio = np.concatenate(frames).flatten()
    segs, _ = _stt.transcribe(audio, language="en", vad_filter=True)
    return " ".join(s.text for s in segs).strip()


# -------------------------------------------------------------------- email
def _decode(value) -> str:
    try:
        return str(make_header(decode_header(value or "")))
    except Exception:
        return value or ""


def _body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", "ignore")
        for part in msg.walk():  # fall back to HTML, strip tags
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    html = payload.decode(part.get_content_charset() or "utf-8", "ignore")
                    return re.sub(r"<[^>]+>", " ", html)
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(msg.get_content_charset() or "utf-8", "ignore") if payload else ""


def fetch_unread(limit=MAX_EMAILS):
    if not EMAIL_ADDR or not EMAIL_PASS:
        raise RuntimeError("Email credentials missing. Fill in your .env file.")
    box = imaplib.IMAP4_SSL(IMAP_HOST)
    box.login(EMAIL_ADDR, EMAIL_PASS)
    box.select("INBOX", readonly=True)  # readonly: never marks mail as read
    _, data = box.search(None, "UNSEEN")
    ids = data[0].split()[-limit:]
    out = []
    for i in reversed(ids):
        _, d = box.fetch(i, "(BODY.PEEK[])")
        msg = email.message_from_bytes(d[0][1])
        text = re.sub(r"\s+", " ", _body(msg)).strip()[:1200]
        out.append({"from": _decode(msg["From"]), "subject": _decode(msg["Subject"]),
                    "date": msg["Date"], "body": text})
    box.logout()
    return out


def triage(mail: dict) -> dict:
    prompt = (
        "Rate this email's importance for the recipient. Important = needs a reply or "
        "action, deadlines, money/bills, security alerts, personal messages, job/school/"
        "work matters, appointments. Not important = newsletters, promos, social "
        "notifications, spam.\n\n"
        f"From: {mail['from']}\nSubject: {mail['subject']}\nBody: {mail['body']}\n\n"
        'Reply ONLY with JSON: {"important": true/false, "summary": "one short sentence"}'
    )
    try:
        r = ollama.chat(model=MODEL, messages=[{"role": "user", "content": prompt}],
                        format="json")
        return json.loads(r["message"]["content"])
    except Exception:
        return {"important": False, "summary": "could not analyse"}


def email_briefing() -> str:
    say("One moment, checking your inbox.")
    try:
        mails = fetch_unread()
    except Exception as e:
        return f"I couldn't reach your inbox, {USER_NAME}. {e}"
    if not mails:
        return f"Your inbox is clear, {USER_NAME}. No unread messages."

    important = []
    for m in mails:
        res = triage(m)
        if res.get("important"):
            sender = re.sub(r"<.*?>", "", m["from"]).strip().strip('"')
            important.append(f"{sender}: {res.get('summary', m['subject'])}")

    if not important:
        return (f"You have {len(mails)} unread emails, {USER_NAME}, but nothing "
                f"that looks urgent.")
    lines = " ".join(f"{n}. {s}." for n, s in enumerate(important, 1))
    return (f"You have {len(mails)} unread emails, {USER_NAME}. "
            f"{len(important)} look important. {lines}")


# -------------------------------------------------------------------- brain
EMAIL_WORDS = re.compile(r"\b(e-?mails?|mails?|inbox|messages)\b", re.I)


def respond(user_text: str):
    if EMAIL_WORDS.search(user_text):
        reply = email_briefing()
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": reply})
        say(reply)
        return
    history.append({"role": "user", "content": user_text})
    r = ollama.chat(model=MODEL, messages=history[-20:] if len(history) > 21
                    else history)
    reply = r["message"]["content"].strip()
    history.append({"role": "assistant", "content": reply})
    say(reply)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", action="store_true", help="type instead of speak")
    ap.add_argument("--no-wake", action="store_true", help="skip the 'Jarvis' wake word")
    args = ap.parse_args()

    say(f"Systems online. Good to see you, {USER_NAME}.")
    while True:
        try:
            if args.text:
                heard = input("You: ").strip()
            else:
                print("(listening...)", end="\r")
                heard = listen()
            if not heard:
                continue
            print(f"You: {heard}")

            if not args.text and not args.no_wake:
                if "jarvis" not in heard.lower():
                    continue
                heard = re.sub(r"(?i)\bjarvis\b[,.!]?\s*", "", heard).strip()
                if not heard:
                    say(f"Yes, {USER_NAME}?")
                    continue

            if re.search(r"\b(goodbye|shut down|power down|exit)\b", heard, re.I):
                say(f"Powering down. Have a good one, {USER_NAME}.")
                break
            respond(heard)
        except KeyboardInterrupt:
            say("Shutting down.")
            sys.exit(0)


if __name__ == "__main__":
    main()
