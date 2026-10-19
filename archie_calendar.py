"""
archie_calendar.py - exams, tests, labs, classes, due dates.

Events live in D:/Archie/calendar.json. You can add them from the calendar window
(click the date at the top of Archie) or by typing, e.g.

    exam: bio midterm oct 12 9am
    lab: chem titration friday 2pm
    due: history essay 11/3
    add a quiz on thursday for stats

The brief, today's Obsidian daily note and Archie's answers all know what's coming up.
"""

import datetime
import json
import os
import re
import threading
import uuid

KINDS = {                     # kind -> (label, color); each also differs in brightness
    "exam": ("Exam", "#ff5f57"),      # red
    "test": ("Test", "#ff8a4c"),      # orange
    "quiz": ("Quiz", "#f5a524"),      # amber
    "due": ("Due", "#f472b6"),        # pink: homework and anything due
    "lab": ("Lab", "#2dd4bf"),        # teal
    "class": ("Class", "#60a5fa"),    # blue: scheduled lectures
    "event": ("Event", "#8a8a85"),    # grey: anything else
}
# colors for things that aren't calendar events but show on it
RECORDING = "#c084fc"     # violet: a class that was recorded and has a lecture note
FOCUS = "#c6f432"         # lime: focus sessions
GYM = "#e8e8e3"           # white: drawing gym
DURATION = {"class": 75, "lab": 110, "exam": 90, "test": 60, "quiz": 30, "event": 60, "due": 0}
ALIASES = {"exam": "exam", "exams": "exam", "final": "exam", "finals": "exam", "midterm": "exam",
           "test": "test", "tests": "test", "quiz": "quiz", "quizzes": "quiz",
           "due": "due", "assignment": "due", "homework": "due", "hw": "due",
           "essay": "due", "project": "due", "paper": "due",
           "lab": "lab", "labs": "lab", "class": "class", "lecture": "class", "seminar": "class",
           "event": "event", "appointment": "event", "appt": "event", "meeting": "event", "reminder": "event"}
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATE_PATTERNS = [
    ("iso", re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")),
    ("md", re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")),
    ("mon_d", re.compile(r"\b" + _MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?\b", re.I)),
    ("d_mon", re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + _MON + r"\b(?:,?\s+(\d{4}))?", re.I)),
    ("rel", re.compile(r"\b(today|tonight|tomorrow|day after tomorrow|next week)\b", re.I)),
    ("in", re.compile(r"\bin\s+(\d{1,3})\s+(day|days|week|weeks)\b", re.I)),
    ("wd", re.compile(r"\b(next\s+|this\s+|every\s+)?(mon|tue|tues|wed|weds|thu|thur|thurs|fri|sat|sun)(?:day|nesday|sday|urday|rsday)?s?\b", re.I)),
]
_TIME = re.compile(r"(?:\bat\s+)?\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)\b|(?:\bat\s+)?\b(\d{1,2}):(\d{2})\b|\b(noon|midnight)\b"
                   r"|\bat\s+(\d{1,2})\b(?!\s*(?:/|-|st|nd|rd|th|days?|weeks?))", re.I)


def find_date(text, today=None):
    """(date, (start, end) of the words used) or (None, None)."""
    today = today or datetime.date.today()
    for kind, rx in _DATE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        try:
            if kind == "iso":
                d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            elif kind == "md":
                y = int(m.group(3)) if m.group(3) else today.year
                y += 2000 if y < 100 else 0
                d = datetime.date(y, int(m.group(1)), int(m.group(2)))
                if not m.group(3) and d < today - datetime.timedelta(days=30):
                    d = d.replace(year=d.year + 1)
            elif kind in ("mon_d", "d_mon"):
                mon, day = (m.group(1), m.group(2)) if kind == "mon_d" else (m.group(2), m.group(1))
                y = int(m.group(3)) if m.group(3) else today.year
                d = datetime.date(y, MONTHS.index(mon[:3].lower()) + 1, int(day))
                if not m.group(3) and d < today - datetime.timedelta(days=30):
                    d = d.replace(year=d.year + 1)
            elif kind == "rel":
                w = m.group(1).lower()
                d = today + datetime.timedelta(days={"today": 0, "tonight": 0, "tomorrow": 1,
                                                     "day after tomorrow": 2, "next week": 7}[w])
            elif kind == "in":
                n = int(m.group(1))
                d = today + datetime.timedelta(days=n * (7 if m.group(2).startswith("week") else 1))
            else:
                idx = DAYS.index(m.group(2).lower()[:3])
                ahead = (idx - today.weekday()) % 7
                if m.group(1) and m.group(1).strip().lower() == "next":
                    ahead = ahead + 7 if ahead else 7
                d = today + datetime.timedelta(days=ahead)
            return d, m.span()
        except (ValueError, IndexError):
            continue
    return None, None


def find_time(text):
    """('09:30', span) or (None, None)."""
    for m in _TIME.finditer(text):
        if m.group(6):
            return ("12:00" if m.group(6).lower() == "noon" else "00:00"), m.span()
        if m.group(1):
            h, mi = int(m.group(1)), int(m.group(2) or 0)
            ap = m.group(3).lower().replace(".", "")
            if h == 12:
                h = 0
            if ap == "pm":
                h += 12
        elif m.group(4):
            h, mi = int(m.group(4)), int(m.group(5))
        else:
            h, mi = int(m.group(7)), 0
            if 1 <= h <= 7:
                h += 12                     # "at 2" almost always means the afternoon
        if 0 <= h < 24 and 0 <= mi < 60:
            return f"{h:02d}:{mi:02d}", m.span()
    return None, None


def fmt_time(t):
    if not t:
        return ""
    h, m = map(int, t.split(":"))
    ap = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{':%02d' % m if m else ''}{ap}"


_CMD = re.compile(r"^\s*(?:add\s+(?:an?\s+)?|schedule\s+(?:an?\s+)?|new\s+|put\s+(?:an?\s+)?)?"
                  r"(?P<kind>" + "|".join(sorted(ALIASES, key=len, reverse=True)) + r")\s*(?::|-|\b)\s*(?P<rest>.+)$", re.I)
_ADD = re.compile(r"^\s*(?:add|schedule|put)\s+(?P<rest>.+?)\s+(?:to|on|in)\s+(?:my\s+)?(?:calendar|schedule)\b(?P<tail>.*)$", re.I)
_WEEKLY = re.compile(r"\bevery\s+(mon|tue|wed|thu|fri|sat|sun)|\b(mon|tues|wednes|thurs|fri|satur|sun)days\b|\bweekly\b", re.I)


def parse_event(text, today=None):
    """{'kind', 'title', 'date', 'time'} for messages like 'exam: bio midterm oct 12 9am',
    or None. A date is required (so ordinary chat isn't mistaken for an event)."""
    today = today or datetime.date.today()
    m = _ADD.match(text)
    if m:
        rest, kind = m.group("rest") + " " + m.group("tail").strip(" .!"), None
        w = re.match(r"(?:an?\s+)?(\w+)", rest)
        if w and w.group(1).lower() in ALIASES:
            kind = ALIASES[w.group(1).lower()]
    else:
        m = _CMD.match(text)
        if not m:
            return None
        explicit = ":" in text[:m.start("rest")] or re.match(r"\s*(add|schedule|new|put)\b", text, re.I)
        if not explicit:
            return None
        kind, rest = ALIASES[m.group("kind").lower()], m.group("rest")
    d, dspan = find_date(rest, today)
    if not d:
        return None
    t, tspan = find_time(rest)
    cut = sorted([s for s in (dspan, tspan) if s], reverse=True)
    title = rest
    for a, b in cut:
        title = title[:a] + " " + title[b:]
    title = re.sub(r"\b(on|at|for|due|by|this|next)\s*$", "", title.strip(), flags=re.I)
    title = re.sub(r"^(an?|my|the)\s+", "", title.strip(" ,.-:"), flags=re.I)
    title = re.sub(r"\s+(on|at|for|due|by)\s*(?=[,.]|$)", "", title, flags=re.I)
    title = re.sub(r"\s{2,}", " ", title).strip(" ,.-:")
    title = re.sub(r"^(?:(?:on|at|for|due|by|every|weekly)\s+)+", "", title, flags=re.I)
    title = re.sub(r"\s+(?:every|weekly)\b", "", title, flags=re.I).strip(" ,.-:")
    if not kind:
        kind = next((ALIASES[w] for w in re.findall(r"[a-z]+", title.lower()) if w in ALIASES), "event")
    if not title:
        title = KINDS[kind][0]
    repeat = "weekly" if _WEEKLY.search(rest) else None
    return {"kind": kind, "title": title[0].upper() + title[1:], "date": d, "time": t, "repeat": repeat}


class Calendar:
    def __init__(self, path):
        self.path = path
        self.lock = threading.Lock()

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data.get("events", [])
        except (OSError, ValueError):
            return []

    def _save(self, events):
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"events": sorted(events, key=lambda e: (e["date"], e.get("time") or ""))},
                          f, indent=1, ensure_ascii=False)
            os.replace(tmp, self.path)

    def add(self, title, date, kind="event", time=None, notes="", repeat=None, until=None):
        events = self.load()
        ev = {"id": uuid.uuid4().hex[:10], "title": title.strip(), "date": date.isoformat(),
              "time": time, "kind": kind if kind in KINDS else "event", "notes": notes.strip(),
              "repeat": repeat, "until": until.isoformat() if until else None}
        events.append(ev)
        self._save(events)
        return ev

    def delete(self, ev_id):
        self._save([e for e in self.load() if e["id"] != ev_id])

    def _expand(self, start, end):
        """Every occurrence between start and end (weekly classes repeat)."""
        out = []
        for e in self.load():
            d0 = datetime.date.fromisoformat(e["date"])
            if e.get("repeat") == "weekly":
                until = datetime.date.fromisoformat(e["until"]) if e.get("until") else end
                d = d0 if d0 >= start else d0 + datetime.timedelta(days=((start - d0).days + 6) // 7 * 7)
                while d <= min(end, until):
                    out.append(dict(e, date=d.isoformat()))
                    d += datetime.timedelta(days=7)
            elif start <= d0 <= end:
                out.append(e)
        return sorted(out, key=lambda e: (e["date"], e.get("time") or "99"))

    def on(self, date):
        return self._expand(date, date)

    def between(self, start, end):
        return self._expand(start, end)

    def upcoming(self, today=None, days=7, big_days=45):
        """Everything in the next `days`, plus exams/tests/due dates further out."""
        today = today or datetime.date.today()
        near = self.between(today, today + datetime.timedelta(days=days))
        far = [e for e in self.between(today + datetime.timedelta(days=days + 1),
                                       today + datetime.timedelta(days=big_days))
               if e["kind"] in ("exam", "test", "due") and e.get("repeat") != "weekly"]
        out, seen = [], set()
        for e in near + far:                 # a weekly class: just its next time
            if e.get("repeat"):
                if e["id"] in seen:
                    continue
                seen.add(e["id"])
            out.append(e)
        return out


def when(e, today=None):
    today = today or datetime.date.today()
    d = datetime.date.fromisoformat(e["date"])
    n = (d - today).days
    day = ("today" if n == 0 else "tomorrow" if n == 1 else d.strftime("%a %b %d").replace(" 0", " ")
           if n < 7 else d.strftime("%b %d").replace(" 0", " ") + f" (in {n} days)")
    t = fmt_time(e.get("time"))
    return f"{day}{' ' + t if t else ''}"


def describe(e, today=None):
    return f"{KINDS.get(e['kind'], KINDS['event'])[0]}: {e['title']}, {when(e, today)}"
