import sqlite3
import threading
import time

import config


class Memory:
    def __init__(self):
        self.db = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS facts(id INTEGER PRIMARY KEY, text TEXT UNIQUE, ts REAL);
            CREATE TABLE IF NOT EXISTS chat(id INTEGER PRIMARY KEY, role TEXT, text TEXT, ts REAL);
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS emails(
                id TEXT PRIMARY KEY, sender TEXT, subject TEXT, date TEXT, body TEXT,
                important INTEGER, category TEXT, summary TEXT, deadline TEXT,
                needs_reply INTEGER, ts REAL);
            """)

    def _q(self, sql, args=(), write=False):
        with self.lock:
            cur = self.db.execute(sql, args)
            if write:
                self.db.commit()
            return cur.fetchall()

    # facts
    def add_fact(self, text):
        self._q("INSERT OR IGNORE INTO facts(text, ts) VALUES(?,?)", (text, time.time()), True)

    def facts(self):
        return [r["text"] for r in self._q("SELECT text FROM facts ORDER BY id")]

    def clear_facts(self):
        self._q("DELETE FROM facts", write=True)

    # conversation
    def add_chat(self, role, text):
        self._q("INSERT INTO chat(role,text,ts) VALUES(?,?,?)", (role, text, time.time()), True)

    def recent_chat(self, n=12):
        rows = self._q("SELECT role,text FROM chat ORDER BY id DESC LIMIT ?", (n,))
        return [{"role": r["role"], "content": r["text"]} for r in reversed(rows)]

    # key/value
    def meta(self, k):
        r = self._q("SELECT v FROM meta WHERE k=?", (k,))
        return r[0]["v"] if r else None

    def set_meta(self, k, v):
        self._q("INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)", (k, v), True)

    # emails
    def known_ids(self):
        return {r["id"] for r in self._q("SELECT id FROM emails")}

    def save_email(self, e):
        self._q("""INSERT OR REPLACE INTO emails
            (id,sender,subject,date,body,important,category,summary,deadline,needs_reply,ts)
            VALUES(:id,:sender,:subject,:date,:body,:important,:category,:summary,:deadline,:needs_reply,:ts)""",
                {**e, "ts": time.time()}, True)

    def recent_emails(self, days=14, important_only=False):
        sql = "SELECT * FROM emails WHERE ts > ?" + (" AND important=1" if important_only else "")
        return [dict(r) for r in self._q(sql + " ORDER BY date DESC", (time.time() - days * 86400,))]

    def deadline_emails(self):
        return [dict(r) for r in self._q(
            "SELECT * FROM emails WHERE important=1 AND deadline IS NOT NULL AND deadline != ''")]
