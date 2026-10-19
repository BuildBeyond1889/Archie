"""Reminders: things due at a time, once or repeating (daily, weekly, monthly).

    r = Reminders(store_path="data/reminders.json")
    r.add("2026-04-01 08:00", "Vaccines for the calves", repeat="monthly")
    for item in r.due():               # call this every minute (in tkinter: root.after(60000, ...))
        show(item["text"])
"""
import calendar
import datetime as dt
import json
import os

FMT = "%Y-%m-%d %H:%M"


def _next(when, repeat):
    if repeat == "daily":
        return when + dt.timedelta(days=1)
    if repeat == "weekly":
        return when + dt.timedelta(weeks=1)
    if repeat == "monthly":
        y, m = (when.year + 1, 1) if when.month == 12 else (when.year, when.month + 1)
        return when.replace(year=y, month=m, day=min(when.day, calendar.monthrange(y, m)[1]))
    return None


class Reminders:
    def __init__(self, store_path):
        self.path = store_path
        try:
            with open(store_path, encoding="utf-8") as f:
                self.items = json.load(f)
        except (OSError, ValueError):
            self.items = []

    def _save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=1)

    def add(self, when, text, repeat=None):
        when = dt.datetime.strptime(when, FMT) if isinstance(when, str) else when
        if repeat not in (None, "daily", "weekly", "monthly"):
            raise ValueError("repeat must be daily, weekly or monthly")
        item = {"id": max([i["id"] for i in self.items] + [0]) + 1, "when": when.strftime(FMT), "text": text, "repeat": repeat}
        self.items.append(item)
        self._save()
        return item

    def due(self, now=None):
        """Reminders whose time has come. Repeating ones move to their next time; one-off ones are removed."""
        now = now or dt.datetime.now()
        out, keep = [], []
        for i in self.items:
            when = dt.datetime.strptime(i["when"], FMT)
            if when <= now:
                out.append(dict(i))
                nxt = _next(when, i.get("repeat"))
                while nxt and nxt <= now:                 # skip times missed while the computer was off
                    nxt = _next(nxt, i["repeat"])
                if nxt:
                    keep.append(dict(i, when=nxt.strftime(FMT)))
            else:
                keep.append(i)
        if out:
            self.items = keep
            self._save()
        return out

    def upcoming(self, n=10):
        return sorted(self.items, key=lambda i: i["when"])[:n]

    def remove(self, rid):
        self.items = [i for i in self.items if i["id"] != rid]
        self._save()
