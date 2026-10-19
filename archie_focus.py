"""
archie_focus.py - the owl focus timer (Pomodoro).

25 minutes of focus, then a 5 minute break; every 4th break is 15 minutes.
The timer keeps exact time from the clock (not by counting ticks), so it stays
right even if Archie is busy. Every finished focus session is kept in
Study/focus_log.jsonl (for the weekly report) and can go in the daily note.
"""

import datetime
import json
import os
import time

MODES = {"focus": ("focus", 25), "short": ("short break", 5), "long": ("long break", 15)}
CYCLE = 4                     # focus sessions before a long break


class FocusTimer:
    def __init__(self, state_path, log_path):
        self.state_path = state_path
        self.log_path = log_path
        self.mode = "focus"
        self.total = MODES["focus"][1] * 60
        self._left = float(self.total)
        self._end = None               # time.monotonic() when it runs out, while running
        self.task = ""
        self.done_today = 0            # focus sessions finished today
        self.minutes_today = 0
        self.day = datetime.date.today().isoformat()
        self.started_at = None         # wall clock, when this focus session started
        self._load()

    # ----- saved between runs (today's count, the last task) -----------------

    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            return
        self.task = st.get("task", "")
        if st.get("day") == self.day:
            self.done_today = int(st.get("done_today", 0))
            self.minutes_today = int(st.get("minutes_today", 0))

    def _save(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump({"day": self.day, "done_today": self.done_today,
                           "minutes_today": self.minutes_today, "task": self.task}, f)
        except OSError:
            pass

    def _new_day(self):
        today = datetime.date.today().isoformat()
        if today != self.day:
            self.day, self.done_today, self.minutes_today = today, 0, 0

    # ----- the clock -----------------------------------------------------------

    @property
    def running(self):
        return self._end is not None

    @property
    def left(self):
        """Seconds left (float)."""
        if self._end is not None:
            return max(0.0, self._end - time.monotonic())
        return self._left

    @property
    def progress(self):
        return 1.0 - self.left / self.total if self.total else 1.0

    def clock(self):
        s = int(round(self.left + 0.49)) if self.running else int(round(self.left))
        return f"{s // 60:02d}:{s % 60:02d}"

    @property
    def session_no(self):
        """Which session of the cycle of 4 this is (1..4)."""
        return self.done_today % CYCLE + 1

    def start(self):
        if self.left <= 0:
            return
        if self.mode == "focus" and self.started_at is None:
            self.started_at = datetime.datetime.now()
        self._end = time.monotonic() + self.left

    def pause(self):
        if self._end is not None:
            self._left = self.left
            self._end = None

    def toggle(self):
        self.pause() if self.running else self.start()

    def add(self, seconds):
        if self._end is not None:
            self._end += seconds
        else:
            self._left += seconds
        self.total = max(self.total, int(self.left))

    def reset(self):
        self._end = None
        self._left = float(self.total)
        self.started_at = None

    def set_mode(self, mode, minutes=None):
        self._new_day()
        self.mode = mode
        self.total = int((minutes or MODES[mode][1]) * 60)
        self._end = None
        self._left = float(self.total)
        self.started_at = None

    def finished(self):
        """True once, when a running timer reaches zero."""
        if self._end is not None and self.left <= 0:
            self._end, self._left = None, 0.0
            return True
        return False

    def next_break(self):
        return "long" if self.done_today % CYCLE == 0 else "short"

    # ----- the log -------------------------------------------------------------

    def record(self, notes=""):
        """A focus session finished: count it and keep it."""
        self._new_day()
        minutes = max(1, round(self.total / 60))
        self.done_today += 1
        self.minutes_today += minutes
        entry = {"date": self.day, "start": (self.started_at or datetime.datetime.now()).strftime("%H:%M"),
                 "minutes": minutes, "task": self.task.strip(), "notes": notes.strip()}
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except OSError:
            pass
        self.started_at = None
        self._save()
        return entry

    def remember_task(self, task):
        self.task = task
        self._save()

    def week(self):
        """{date: minutes} for the last 7 days, from the log."""
        days = {(datetime.date.today() - datetime.timedelta(days=i)).isoformat(): 0 for i in range(7)}
        try:
            with open(self.log_path, encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("date") in days:
                        days[e["date"]] += int(e.get("minutes", 0))
        except OSError:
            pass
        return days


def log_line(entry):
    """How a finished session reads in the daily note."""
    what = entry["task"] or "focus session"
    line = f"focus {entry['minutes']} min: {what}"
    if entry["notes"]:
        line += f". {entry['notes']}"
    return line
