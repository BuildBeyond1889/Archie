"""Change or remove calendar events by asking, from the PC chat, a laptop or the phone:
"move checking out apartment to 6", "push the dentist to Friday 3pm", "cancel bio lab tomorrow".

Only runs when the message clearly asks to change something AND names an event on the calendar (or says calendar /
event / appointment), so ordinary chat is never mistaken for an edit. The model only picks which event and what changes;
the change is checked (the event must exist, the date and time must be real) before anything is saved, and the reply
says exactly what changed.
"""
import datetime
import json
import re

VERBS = re.compile(r"\b(move|moved|change|changed|reschedul\w*|push(?:ed)?|switch|update|modify|set|make it|"
                   r"delete|cancel\w*|remove|drop|take off|it'?s (?:now|at)|now at|instead)\b", re.I)
CAL_WORDS = re.compile(r"\b(calendar|event|appointment|meeting|time)\b", re.I)
STOP = {"the", "a", "an", "to", "at", "on", "my", "for", "and", "of", "in", "it", "is", "out", "up", "with"}


def _words(s):
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2 and w not in STOP}


def candidates(cal, today=None):
    today = today or datetime.date.today()
    out, seen = [], set()
    for e in cal.load():
        d = datetime.date.fromisoformat(e["date"])
        if e.get("repeat") == "weekly":
            until = e.get("until")
            if until and datetime.date.fromisoformat(until) < today:
                continue
        elif d < today - datetime.timedelta(days=1) or d > today + datetime.timedelta(days=120):
            continue
        if e["id"] not in seen:
            seen.add(e["id"])
            out.append(e)
    return out


def looks_like_edit(text, cal):
    if not VERBS.search(text or ""):
        return False
    if CAL_WORDS.search(text):
        return True
    w = _words(text)
    return any(len(w & _words(e["title"])) >= 1 for e in candidates(cal))


def _time(s, text):
    s = str(s or "").strip().lower()
    if s in ("", "same"):
        return "same"
    if s in ("none", "all day", "null"):
        return None
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", s)
    if not m:
        return "same"
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    # "at 6" with no am/pm: people mean the evening unless they say morning
    if not ap and 1 <= h <= 7 and not re.search(r"\b(am|a\.m\.|morning)\b", text, re.I):
        h += 12
    return f"{h:02d}:{mi:02d}" if 0 <= h < 24 and 0 <= mi < 60 else "same"


def plan(text, cal, ask, today=None):
    """{'action', 'event', 'changes'} or {'error'}. ask(prompt) -> the model's JSON reply."""
    today = today or datetime.date.today()
    evs = candidates(cal, today)
    if not evs:
        return {"error": "Your calendar doesn't have anything coming up to change."}
    lines = [f'{e["id"]} | {e["title"]} | {e["date"]}' + (f' {e["time"]}' if e.get("time") else " all day")
             + (" | weekly" if e.get("repeat") else "") for e in evs[:60]]
    prompt = (f"Today is {today:%A %Y-%m-%d}. The user wants to change their calendar. Their events:\n"
              + "\n".join(lines) + f"\n\nThe user said: \"{text}\"\n\n"
              'Reply ONLY with JSON: {"action": "change" or "delete" or "none", "id": "the event id from the list", '
              '"date": "new YYYY-MM-DD, or empty to keep it", "time": "new HH:MM 24-hour, or empty to keep it, or none for all day", '
              '"title": "new title, or empty to keep it"}. Use "none" if they did not ask to change one of these events.')
    try:
        d = json.loads(re.search(r"\{.*\}", ask(prompt), re.S).group(0))
    except Exception:
        return {"error": "I couldn't work out which event to change. Try: move <event> to <day> <time>."}
    act = str(d.get("action") or "none").lower()
    ev = next((e for e in evs if e["id"] == str(d.get("id") or "").strip()), None)
    if act not in ("change", "delete") or not ev:
        return {"error": "I couldn't find that on your calendar. Say the event's name, like: move checking out apartment to 6pm."}
    if act == "delete":
        return {"action": "delete", "event": ev, "changes": {}}
    ch = {}
    ds = str(d.get("date") or "").strip()
    if ds and ds != ev["date"]:
        try:
            ch["date"] = datetime.date.fromisoformat(ds).isoformat()
        except ValueError:
            pass
    t = _time(d.get("time"), text)
    if t != "same" and t != ev.get("time"):
        ch["time"] = t
    nt = str(d.get("title") or "").strip()
    if nt and nt.lower() != ev["title"].lower() and re.search(r"\b(rename|call it|title)\b", text, re.I):
        ch["title"] = nt
    if not ch:
        return {"error": f"\"{ev['title']}\" already looks like that ({describe(ev)}). Tell me the new day or time."}
    return {"action": "change", "event": ev, "changes": ch}


def describe(e):
    d = datetime.date.fromisoformat(e["date"])
    t = e.get("time")
    if t:
        h, m = map(int, t.split(":"))
        t = f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"
    return f"{d:%a %b} {d.day}" + (f" at {t}" if t else ", all day") + (" (every week)" if e.get("repeat") else "")


def apply(p, cal):
    """Do it. Returns the reply text and an undo function."""
    ev = p["event"]
    if p["action"] == "delete":
        cal.delete(ev["id"])
        return f"Removed \"{ev['title']}\" ({describe(ev)}) from your calendar.", lambda: cal.restore(ev)
    new = cal.update(ev["id"], **p["changes"])
    return (f"Changed \"{ev['title']}\": {describe(ev)} → {describe(new)}.", lambda: cal.restore(ev))


def handle(text, cal, ask):
    """For phone/laptop chat: the reply text (or None if it isn't a calendar change)."""
    if not looks_like_edit(text, cal):
        return None
    p = plan(text, cal, ask)
    if p.get("error"):
        return p["error"]
    return apply(p, cal)[0]
