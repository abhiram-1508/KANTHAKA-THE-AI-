import sys
import threading
from datetime import date, datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
                               QPushButton, QSystemTrayIcon, QTextBrowser, QVBoxLayout, QWidget)

import config
import gmail_client
from brain import Brain
from voice import Listener, Speaker

S = config.S
STYLE = """
QMainWindow, QWidget { background:#0a0f18; color:#cfe8ff; font-family:'Segoe UI'; font-size:14px; }
QTextBrowser { background:#0d1522; border:1px solid #17304d; border-radius:8px; padding:8px; }
QLineEdit { background:#0d1522; border:1px solid #17304d; border-radius:8px; padding:8px; color:#fff; }
QPushButton { background:#10243b; border:1px solid #1f4a77; border-radius:8px; padding:8px 14px; }
QPushButton:hover { background:#17375a; }
"""
STATES = {"idle": ("● LISTENING", "#3ddcff"), "thinking": ("● THINKING", "#ffb43d"),
          "speaking": ("● SPEAKING", "#4dff9a"), "muted": ("● MUTED", "#667788")}


def tray_icon():
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor("#3ddcff")); p.setPen(Qt.NoPen); p.drawEllipse(8, 8, 48, 48)
    p.setBrush(QColor("#0a0f18")); p.drawEllipse(22, 22, 20, 20)
    p.end()
    return QIcon(pm)


class Window(QMainWindow):
    log = Signal(str, str)
    state = Signal(str)
    notify = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("J.A.R.V.I.S.")
        self.resize(560, 700)
        self.brain = Brain()
        self.speaker = Speaker(on_state=self.state.emit)
        self.busy_thinking = False

        # --- UI
        self.status = QLabel(); self.status.setAlignment(Qt.AlignCenter)
        self.status.setStyleSheet("font-size:20px; letter-spacing:4px; padding:12px;")
        self.view = QTextBrowser()
        self.input = QLineEdit(placeholderText="Type a command, or just say 'Jarvis ...'")
        self.input.returnPressed.connect(self.on_type)
        mic = QPushButton("Mute mic"); mic.clicked.connect(lambda: self.toggle_mute(mic))
        brief = QPushButton("Email briefing"); brief.clicked.connect(lambda: self.ask("check my email"))
        row = QHBoxLayout(); row.addWidget(self.input, 1); row.addWidget(brief); row.addWidget(mic)
        lay = QVBoxLayout(); lay.addWidget(self.status); lay.addWidget(self.view, 1); lay.addLayout(row)
        w = QWidget(); w.setLayout(lay); self.setCentralWidget(w); self.setStyleSheet(STYLE)

        # --- tray
        self.tray = QSystemTrayIcon(tray_icon(), self)
        menu = QMenu()
        a = QAction("Show JARVIS", self); a.triggered.connect(self.showNormal)
        q = QAction("Quit", self); q.triggered.connect(self.quit)
        menu.addAction(a); menu.addAction(q)
        self.tray.setContextMenu(menu); self.tray.show()
        self.tray.activated.connect(lambda _: self.showNormal())
        self.setWindowIcon(tray_icon())

        self.log.connect(self.append); self.state.connect(self.set_state); self.notify.connect(self.show_alert)
        self.set_state("idle")

        # --- voice
        self.listener = Listener(self.speaker)
        self.listener.heard.connect(self.on_heard)
        self.listener.start()

        # --- background mail polling + startup briefing
        self.timer = QTimer(self); self.timer.timeout.connect(self.poll)
        self.timer.start(int(S["poll_minutes"]) * 60_000)
        QTimer.singleShot(1500, self.startup)

    # ------------------------------------------------------------ UI helpers
    def append(self, who, text):
        color = "#3ddcff" if who == "JARVIS" else "#9fb4c8"
        self.view.append(f"<p><b style='color:{color}'>{who}</b><br>{text.replace(chr(10), '<br>')}</p>")

    def set_state(self, s):
        if self.listener.muted and s == "idle":
            s = "muted"
        label, color = STATES[s]
        self.status.setText(label)
        self.status.setStyleSheet(f"font-size:20px; letter-spacing:4px; padding:12px; color:{color};")

    def toggle_mute(self, btn):
        self.listener.muted = not self.listener.muted
        btn.setText("Unmute mic" if self.listener.muted else "Mute mic")
        self.set_state("idle")

    def show_alert(self, text):
        self.tray.showMessage("JARVIS", text, QSystemTrayIcon.Information, 10000)
        self.append("JARVIS", text)

    # ------------------------------------------------------------- behaviour
    def on_type(self):
        t = self.input.text().strip()
        self.input.clear()
        if t:
            self.ask(t)

    def on_heard(self, text):
        if text == "__wake__":
            self.append("JARVIS", f"Yes, {S['user_name']}?")
            return self.speaker.speak(f"Yes, {S['user_name']}?")
        self.ask(text)

    def ask(self, text):
        self.append("You", text)
        self.state.emit("thinking")

        def work():
            reply = self.brain.handle(text)
            self.log.emit("JARVIS", reply)
            self.speaker.speak(reply)
        threading.Thread(target=work, daemon=True).start()

    def say_async(self, fn):
        def work():
            try:
                for msg in fn():
                    self.notify.emit(msg)
                    self.speaker.speak(msg)
            except Exception as e:
                self.log.emit("JARVIS", f"Email check failed: {e}")
        threading.Thread(target=work, daemon=True).start()

    def startup(self):
        if not gmail_client.configured():
            msg = (f"Good day, {S['user_name']}. Gmail isn't connected yet. "
                   f"Follow step 4 of the README to enable email intelligence.")
            self.log.emit("JARVIS", msg); self.speaker.speak(msg); return
        if self.brain.mem.meta("last_briefing") != str(date.today()):
            self.say_async(lambda: [self.brain.briefing()])
        else:
            self.say_async(self.brain.poll)

    def poll(self):
        if gmail_client.configured():
            self.say_async(self.brain.poll)

    def closeEvent(self, e):  # close button hides to tray
        e.ignore(); self.hide()
        self.tray.showMessage("JARVIS", "Still running in the background.", QSystemTrayIcon.Information, 3000)

    def quit(self):
        self.listener.stop(); self.tray.hide(); QApplication.quit()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    win = Window(); win.show()
    sys.exit(app.exec())
