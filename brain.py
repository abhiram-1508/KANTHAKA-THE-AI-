import json
import re
from datetime import date, datetime

import ollama

import actions
import config
import gmail_client
from memory import Memory

S = config.S


def short(sender: str) -> str:
    return re.sub(r"<.*?>", "", sender).strip().strip('"') or sender


class Brain:
    def __init__(self):
        self.mem = Memory()
        self.last_email = None  # lets you say "reply to it"

    # ------------------------------------------------------------ LLM helpers
    def _system(self):
        facts = "\n".join(f"- {f}" for f in self.mem.facts()) or "- (nothing yet)"
        return (f"You are JARVIS, a calm, witty, highly capable personal assistant like the AI in Iron Man. "
                f"Address the user as '{S['user_name']}'. Your replies are spoken aloud: use short natural "
                f"sentences, no markdown, no lists, no emojis. Never claim to have done something you did not do.\n"
                f"Today is {datetime.now():%A, %d %B %Y, %H:%M}.\nWhat you know about the user:\n{facts}")

    def _llm(self, messages, json_mode=False):
        r = ollama.chat(model=S["model"], messages=messages, options={"temperature": 0.4},
                        format="json" if json_mode else "")
        return r["message"]["content"].strip()

    # ------------------------------------------------------------------ email
    def _triage(self, e):
        facts = "; ".join(self.mem.facts()) or "no extra info"
        prompt = (
            f"Today is {date.today()}. About the recipient: {facts}.\n"
            "Classify this email. Important = needs action or reply, deadlines, placements/jobs/interviews, "
            "research/academic matters, money or bills, security alerts, appointments, personal messages. "
            "Not important = newsletters, promotions, social media notifications, automated receipts.\n\n"
            f"From: {e['sender']}\nSubject: {e['subject']}\nBody: {e['body'][:2000]}\n\n"
            'Reply ONLY with JSON: {"important": bool, "category": "one or two words", '
            '"summary": "one short sentence", "deadline": "YYYY-MM-DD or null", "needs_reply": bool}')
        try:
            d = json.loads(self._llm([{"role": "user", "content": prompt}], json_mode=True))
        except Exception:
            d = {}
        dl = d.get("deadline")
        return {**e, "important": int(bool(d.get("important"))), "category": str(d.get("category", "")),
                "summary": str(d.get("summary") or e["subject"]),
                "deadline": dl if isinstance(dl, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", dl) else None,
                "needs_reply": int(bool(d.get("needs_reply")))}

    def sync(self):
        """Fetch new mail, classify it locally, return the newly stored emails."""
        raw = gmail_client.fetch(S["gmail_query"], S["max_emails"], self.mem.known_ids())
        new = []
        for e in raw:
            t = self._triage(e)
            self.mem.save_email(t)
            new.append(t)
        return new

    def briefing(self):
        self.sync()
        imp = self.mem.recent_emails(days=3, important_only=True)
        h = datetime.now().hour
        greet = "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"
        self.mem.set_meta("last_briefing", str(date.today()))
        if not imp:
            return f"{greet}, {S['user_name']}. Nothing important in your inbox right now."
        items = "\n".join(f"- From {short(e['sender'])} ({e['category']}): {e['summary']}"
                          + (f" Deadline {e['deadline']}." if e["deadline"] else "")
                          + (" Needs your reply." if e["needs_reply"] else "") for e in imp[:6])
        prompt = (f"Write a short spoken briefing. Start with '{greet}, {S['user_name']}.' Say how many "
                  f"important emails there are ({len(imp)}) and describe each in one natural clause. "
                  f"Use only these facts:\n{items}\nEnd by offering to summarise any of them.")
        try:
            return self._llm([{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}])
        except Exception:
            return f"{greet}, {S['user_name']}. You have {len(imp)} important emails. " + " ".join(
                f"{short(e['sender'])}: {e['summary']}." for e in imp[:5])

    def poll(self):
        """Background check: returns spoken/notification alert strings."""
        alerts = [f"Important email from {short(e['sender'])}: {e['summary']}"
                  for e in self.sync() if e["important"]]
        today = date.today()
        for e in self.mem.deadline_emails():
            try:
                left = (date.fromisoformat(e["deadline"]) - today).days
            except ValueError:
                continue
            key = f"dl:{e['id']}:{today}"
            if 0 <= left <= S["alert_deadline_days"] and not self.mem.meta(key):
                self.mem.set_meta(key, "1")
                when = "today" if left == 0 else f"in {left} day{'s' if left > 1 else ''}"
                alerts.append(f"Deadline {when}: {e['subject']}")
        return alerts

    def find_email(self, query):
        stop = {"the", "a", "an", "my", "me", "email", "mail", "message", "about", "from", "regarding",
                "summarize", "summarise", "read", "that", "this", "please", "of", "on", "to", "for", "and", "it"}
        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in stop and len(w) > 2]
        best, score = None, 0
        for e in self.mem.recent_emails(days=30):
            s = sum(3 * (w in e["subject"].lower()) + 2 * (w in e["sender"].lower())
                    + 2 * (w in (e["category"] or "").lower()) + 2 * (w in (e["summary"] or "").lower())
                    + (w in e["body"].lower()) for w in words)
            if s > score:
                best, score = e, s
        return best

    def _email_task(self, e, instruction):
        prompt = (f"{instruction}\n\nFrom: {e['sender']}\nDate: {e['date']}\nSubject: {e['subject']}\n"
                  f"Body: {e['body'][:4000]}")
        return self._llm([{"role": "system", "content": self._system()}, {"role": "user", "content": prompt}])

    # ----------------------------------------------------------------- router
    def handle(self, text: str) -> str:
        t = text.strip()
        low = t.lower().rstrip(".!?")
        reply = self._route(t, low)
        self.mem.add_chat("user", t)
        self.mem.add_chat("assistant", reply)
        return reply

    def _route(self, t, low):
        name = S["user_name"]
        m = re.match(r"(?:please )?remember (?:that )?(.+)", low)
        if m:
            self.mem.add_fact(m.group(1))
            return f"Noted, {name}. I'll remember that {m.group(1)}."
        if re.search(r"what (do you|did you) (remember|know) about me|what have i told you", low):
            f = self.mem.facts()
            return "Here's what I know. " + ". ".join(f) + "." if f else "You haven't told me anything yet."
        if re.search(r"forget everything|clear (your )?memory", low):
            self.mem.clear_facts()
            return "Memory cleared."
        m = re.match(r"(?:please )?(?:open|launch|start) (.+)", low)
        if m:
            return actions.open_target(m.group(1))

        mail_words = re.search(r"\b(e-?mails?|mails?|inbox|gmail)\b", low)
        if mail_words and not gmail_client.configured():
            return "Gmail isn't connected yet. Please follow step 4 in the README."
        try:
            if re.search(r"(draft|write|compose).*(reply|response)|reply to", low):
                e = self.find_email(low) or self.last_email
                if not e:
                    return "Which email should I reply to?"
                self.last_email = e
                return "Here's a draft. " + self._email_task(
                    e, f"Write a polite, concise reply from {name} to this email. Output only the reply text.")
            if mail_words and re.search(r"summari[sz]e|explain|read|tell me about|what does|what('s| is) in|details", low):
                e = self.find_email(low) or (self.last_email if re.search(r"\b(it|that|this)\b", low) else None)
                if not e:
                    return "I couldn't find a matching email. Try naming the sender or topic."
                self.last_email = e
                return self._email_task(e, "Summarise this email in 2-4 spoken sentences. Mention any deadline, "
                                           "requirement or action the recipient must take.")
            if mail_words and re.search(r"important|urgent|check|new|unread|any|brief", low) \
                    or re.search(r"^(good (morning|afternoon|evening)|brief me|daily brief)", low):
                return self.briefing()
        except Exception as ex:
            return f"I ran into a problem with your email, {name}: {ex}"

        msgs = [{"role": "system", "content": self._system()}] + self.mem.recent_chat(12) \
               + [{"role": "user", "content": t}]
        try:
            return self._llm(msgs)
        except Exception as ex:
            return f"I can't reach my language model. Is Ollama running? ({ex})"
