"""
lite_quick.py - turns one line from the quick-add bar (Ctrl+Alt+Space) into a change, on the laptop,
so it works offline. Dates and times are read by lite_cal.py, a copy of D:\\Archie\\archie_calendar.py,
so "fri 3pm" means the same thing on both machines.

    dentist fri 3pm                  -> calendar: Dentist, Friday 3:00 pm
    bio exam dec 12 9am              -> calendar (exam)
    lab every tuesday 2pm            -> calendar, weekly
    essay due friday                 -> deadline (countdown)
    finish lab report by thursday    -> to-do, due Thursday
    pay rent friday                  -> to-do, due Friday (no time, not a class/exam/appointment)
    call mom                         -> to-do
    https://...                      -> saved article (your PC reads it)
    note: idea for the final project -> a note (goes to Obsidian)
"""

import datetime
import re

import lite_cal as cal

URL = re.compile(r"https?://\S+", re.I)
TASK = re.compile(r"^\s*(?:to-?do|task|tdo)\s*[:\-]\s*", re.I)
NOTE = re.compile(r"^\s*(?:note|idea)\s*[:\-]\s*", re.I)
DEADLINE = re.compile(r"\b(due|deadline|submit|turn in|hand in)\b", re.I)
BY = re.compile(r"\bby\b", re.I)
CAL_WORDS = re.compile(r"\b(exam|exams|final|finals|midterm|test|quiz|lab|class|lecture|seminar|meeting|appointment|appt|"
                       r"interview|dentist|doctor|dinner|lunch|party|game|flight|concert|practice|shift|call with)\b", re.I)


def _strip(text, spans):
    for a, b in sorted([s for s in spans if s], reverse=True):
        text = text[:a] + " " + text[b:]
    text = re.sub(r"\b(on|at|for|due|by|this|next|before)\s*$", "", text.strip(), flags=re.I)
    text = re.sub(r"\s+(on|at|for|due|by|before)\s*(?=[,.]|$)", "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text).strip(" ,.-:")
    return text[:1].upper() + text[1:] if text else text


def _when(d, t=None):
    s = d.strftime("%a %b %d").replace(" 0", " ")
    return s + (" " + cal.fmt_time(t) if t else "")


def classify(text, today=None):
    """-> (op for Lite.change, what to tell the user) or (None, reason)."""
    text = (text or "").strip()
    today = today or datetime.date.today()
    if not text:
        return None, "nothing typed"
    m = URL.search(text)
    if m:
        url = m.group(0).rstrip(").,;'\"")
        return {"type": "save_story", "title": url, "url": url, "publisher": "", "time": None}, "Saving the link on your PC"
    if NOTE.match(text):
        body = NOTE.sub("", text, count=1).strip()
        return {"type": "note_quick", "text": body}, "Note saved"
    if TASK.match(text):
        body = TASK.sub("", text, count=1).strip()
        d, ds = cal.find_date(body, today)
        title = _strip(body, [ds]) if d else body
        return ({"type": "task_add", "text": title or body, "due": d.isoformat() if d else None},
                "To-do: " + (title or body) + (" · due " + _when(d) if d else ""))
    d, ds = cal.find_date(text, today)
    if not d:
        return {"type": "task_add", "text": text[:300], "due": None}, "To-do: " + text[:80]
    t, ts = cal.find_time(text)
    if DEADLINE.search(text) and not t:
        what = _strip(re.sub(r"\b(due|deadline)\b", " ", text[:ds[0]] + " " + text[ds[1]:], flags=re.I), []) or text
        return {"type": "deadline_add", "what": what, "date": d.isoformat()}, "Deadline: " + what + " · " + _when(d)
    if not t and (BY.search(text) or not CAL_WORDS.search(text)):
        title = _strip(re.sub(r"\bby\b", " ", text[:ds[0]], flags=re.I) + " " + text[ds[1]:], [])
        return {"type": "task_add", "text": title or text, "due": d.isoformat()}, "To-do: " + (title or text) + " · due " + _when(d)
    ev = cal.parse_event("add " + text + " to my calendar", today)
    if ev and ev.get("date"):
        item = {"title": ev["title"], "date": ev["date"].isoformat(), "time": ev.get("time"), "kind": ev.get("kind") or "event",
                "notes": "", "repeat": ev.get("repeat"), "until": None}
        return ({"type": "cal_add", "item": item},
                "Calendar: " + ev["title"] + " · " + _when(ev["date"], ev.get("time")) + (" · weekly" if ev.get("repeat") else ""))
    title = _strip(text, [ds, ts])
    return {"type": "task_add", "text": title or text, "due": d.isoformat()}, "To-do: " + (title or text) + " · due " + _when(d)
