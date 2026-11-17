import collections
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from PySide6.QtCore import QThread, Signal

import config

S = config.S
SR = 16000
BLOCK = 1600  # 0.1 s


class Speaker:
    """Piper TTS (offline). Falls back to the Windows voice if Piper isn't set up."""

    def __init__(self, on_state=lambda s: None):
        self.q = queue.Queue()
        self.pending = 0
        self.lock = threading.Lock()
        self.on_state = on_state
        threading.Thread(target=self._worker, daemon=True).start()

    @property
    def busy(self):
        return self.pending > 0

    def speak(self, text):
        text = re.sub(r"[*_#`>]", "", text).strip()
        if not text:
            return
        with self.lock:
            self.pending += 1
        self.on_state("speaking")
        self.q.put(text)

    def _worker(self):
        while True:
            text = self.q.get()
            try:
                self._say(text)
            except Exception as e:
                print("TTS error:", e)
            with self.lock:
                self.pending -= 1
                done = self.pending == 0
            if done:
                time.sleep(0.3)
                self.on_state("idle")

    def _say(self, text):
        voice = S["voice"]
        if (config.VOICES / f"{voice}.onnx").exists():
            out = Path(tempfile.gettempdir()) / "kanthaka_tts.wav"
            subprocess.run([sys.executable, "-m", "piper", "-m", voice, "--data-dir", str(config.VOICES),
                            "-f", str(out)], input=text.encode(), check=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            with wave.open(str(out)) as w:
                data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
                sd.play(data, w.getframerate())
                sd.wait()
        else:  # fallback
            import pyttsx3
            eng = pyttsx3.init()
            eng.setProperty("rate", 175)
            eng.say(text)
            eng.runAndWait()


class Listener(QThread):
    heard = Signal(str)
    status = Signal(str)

    def __init__(self, speaker):
        super().__init__()
        self.speaker, self.muted, self.alive = speaker, False, True
        self.awake_until = 0.0

    def _record(self, stream, thr):
        pre = collections.deque(maxlen=3)
        frames, started, quiet = [], False, 0.0
        while self.alive:
            data, _ = stream.read(BLOCK)
            if self.speaker.busy or self.muted:
                pre.clear(); frames, started, quiet = [], False, 0.0
                continue
            loud = float(np.sqrt(np.mean(data ** 2))) > thr
            if not started:
                pre.append(data)
                if loud:
                    started, frames = True, list(pre)
                continue
            frames.append(data)
            quiet = 0.0 if loud else quiet + 0.1
            if quiet >= 0.9 or len(frames) > 250:
                return np.concatenate(frames).flatten()
        return None

    def run(self):
        model = WhisperModel(S["whisper"], compute_type="int8")
        wakes = [w.lower() for w in S["wake_words"]]
        wake_re = re.compile(r"(?i)\b(" + "|".join(re.escape(w) for w in wakes) + r")\b[,.!?]*\s*")
        with sd.InputStream(samplerate=SR, channels=1, dtype="float32", blocksize=BLOCK) as st:
            amb = np.mean([np.sqrt(np.mean(st.read(BLOCK)[0] ** 2)) for _ in range(10)])
            thr = max(0.012, float(amb) * 3)
            while self.alive:
                audio = self._record(st, thr)
                if audio is None or len(audio) < SR * 0.4:
                    continue
                segs, _ = model.transcribe(audio, language="en", vad_filter=True, initial_prompt="Kanthaka, open, email, summarize.")
                text = " ".join(s.text for s in segs).strip()
                if st.read_available:
                    st.read(st.read_available)  # drop what piled up while transcribing
                if len(text) < 2:
                    continue
                if wake_re.search(text):
                    text = wake_re.sub("", text, count=1).strip() or "__wake__"
                    self.awake_until = time.time() + 25
                elif time.time() < self.awake_until:
                    self.awake_until = time.time() + 25  # keep conversation open
                else:
                    continue
                self.heard.emit(text)

    def stop(self):
        self.alive = False
