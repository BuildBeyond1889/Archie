"""Keeps Archie's main brain loaded on the graphics card when you're likely to need it, so the first reply is
instant instead of waiting a few seconds for the model to load (Ollama unloads a model after ~5 idle minutes).

Warm while:
  - a class, lab, exam, test or quiz on your calendar is about to start, running, or just ended
    (15 minutes before until 30 minutes after), or
  - you've used Archie in the last 30 minutes.
Otherwise it lets Ollama unload the model as usual, so the graphics card is free for games and everything else.
"""
import datetime
import json
import re
import threading
import time
import urllib.request

BEFORE, AFTER, RECENT = 15, 30, 30        # minutes
PING_EVERY = 4 * 60                       # seconds; each ping keeps the model loaded for 10 more minutes
DURATION = {"class": 75, "lab": 110, "exam": 90, "test": 60, "quiz": 30}


def _minutes(t):
    m = re.match(r"\s*(\d{1,2}):(\d{2})", t or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


class Warm:
    def __init__(self, ollama_url, main_model, calendar, active):
        self.url = ollama_url.rstrip("/")
        self.main_model = main_model      # callable -> model name
        self.calendar = calendar          # archie_calendar.Calendar (has .on(date))
        self.active = active              # callable -> True while you're using Archie
        self.last_used = 0.0
        self.last_ping = 0.0

    def in_class_window(self, now=None):
        now = now or datetime.datetime.now()
        mins = now.hour * 60 + now.minute
        try:
            events = self.calendar.on(now.date())
        except Exception:
            return False
        for e in events:
            k = e.get("kind")
            start = _minutes(e.get("time"))
            if k not in DURATION or start is None:
                continue
            if start - BEFORE <= mins <= start + DURATION[k] + AFTER:
                return True
        return False

    def want(self):
        return self.in_class_window() or (time.time() - self.last_used) < RECENT * 60

    def ping(self):
        body = json.dumps({"model": self.main_model(), "prompt": "", "keep_alive": "10m", "stream": False}).encode()
        req = urllib.request.Request(self.url + "/api/generate", data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:      # an empty prompt just loads the model
            r.read()

    def loop(self):
        while True:
            try:
                if self.active():
                    self.last_used = time.time()
                if self.want() and time.time() - self.last_ping >= PING_EVERY:
                    self.last_ping = time.time()
                    self.ping()
            except Exception:
                pass
            time.sleep(30)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="keep-warm").start()
        return self
