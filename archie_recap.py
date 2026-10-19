"""
archie_recap.py - the evening recap.

You talk for a minute or two about your day. Archie types it out (on your PC),
then sorts it into: what you got done today, what's for tomorrow (which can go
on the to-do list), and what's on your mind. The next morning's brief opens
with it.

Recaps are kept in Recaps/<date>.json next to the recording.
"""

import datetime
import json
import os
import re

import archie_calendar as cal

PROMPTS = ("what did you get done today?", "what's still hanging?",
           "what does tomorrow look like?", "anything on your mind?")

SORT_PROMPT = """The user just recorded their evening recap (a spoken wrap-up of their day). Today is {today}.
{focus}
Sort what they SAID into JSON. Use their own words, shortened; don't invent anything they didn't say.

- "today": things they got done or worked on today (short phrases, 1 line each)
- "tomorrow": things they want or need to do next, each {{"task": "...", "when": "..."}}.
  "when" is the day they said ("tomorrow", "friday", "oct 17"), or "" if they didn't say one.
  Tasks start with a verb and are short, like "redo the network+ practice exam".
- "mind": anything they're worried about, thinking about or want help with (short phrases)
- "summary": ONE short sentence recapping the day, written to them ("You ...").

Leave a list empty if they didn't talk about it. Return JSON only:
{{"today": [], "tomorrow": [], "mind": [], "summary": ""}}

The recap (typed out from speech, so expect small mistakes):
\"\"\"{text}\"\"\""""


def sort_recap(chat, model, text, focus_line=""):
    """chat(model, prompt, ...) -> str. Returns {'today', 'tomorrow', 'mind', 'summary'}."""
    today = datetime.date.today()
    raw = chat(model, SORT_PROMPT.format(today=today.strftime("%A, %B %d, %Y"), text=text[:12000],
                                         focus=focus_line), max_tokens=700, timeout=240,
               json_mode=True, temperature=0.2, num_ctx=8192)
    try:
        data = json.loads(raw)
    except ValueError:
        m = re.search(r"\{.*\}", raw or "", re.S)
        data = json.loads(m.group(0)) if m else {}
    out = {"today": [], "tomorrow": [], "mind": [], "summary": ""}
    for key in ("today", "mind"):
        out[key] = [str(x).strip() for x in data.get(key) or [] if str(x).strip()][:10]
    tomorrow = today + datetime.timedelta(days=1)
    for t in data.get("tomorrow") or []:
        if isinstance(t, str):
            t = {"task": t, "when": ""}
        task = str(t.get("task", "")).strip().rstrip(".")
        if not task:
            continue
        when = str(t.get("when", "")).strip()
        due = None
        if when:
            try:
                due = cal.find_date(when, today)
            except Exception:
                due = None
            if isinstance(due, tuple):
                due = due[0]
        if not isinstance(due, datetime.date) or due < tomorrow:
            due = tomorrow
        out["tomorrow"].append({"task": task, "due": due.isoformat(), "keep": True})
    out["tomorrow"] = out["tomorrow"][:10]
    out["summary"] = str(data.get("summary", "")).strip()
    return out


def due_label(iso):
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return ""
    today = datetime.date.today()
    if d == today + datetime.timedelta(days=1):
        return d.strftime("%a").lower()
    if (d - today).days < 7:
        return d.strftime("%a").lower()
    return d.strftime("%b %d").replace(" 0", " ").lower()


def note_markdown(recap):
    """The recap as an Obsidian note."""
    d = datetime.datetime.fromisoformat(recap["saved_at"])
    lines = ["---", f"created: {d:%Y-%m-%d %H:%M}", "source: Archie", "type: evening recap",
             "tags: [archie, recap]", "---", "", f"# Evening recap · {d:%a %b %d}".replace(" 0", " "), ""]
    if recap.get("summary"):
        lines += [recap["summary"], ""]
    if recap.get("today"):
        lines += ["## Today"] + [f"- {x}" for x in recap["today"]] + [""]
    kept = [t for t in recap.get("tomorrow", []) if t.get("keep")]
    if kept:
        lines += ["## Next"] + [f"- [ ] {t['task']} ({due_label(t['due'])})" for t in kept] + [""]
    if recap.get("mind"):
        lines += ["## On my mind"] + [f"- {x}" for x in recap["mind"]] + [""]
    if recap.get("transcript"):
        lines += ["## What I said", "", recap["transcript"].strip(), ""]
    return "\n".join(lines)


class RecapStore:
    def __init__(self, folder):
        self.folder = folder

    def path_for(self, day):
        return os.path.join(self.folder, f"{day}.json")

    def save(self, recap):
        os.makedirs(self.folder, exist_ok=True)
        day = recap["saved_at"][:10]
        with open(self.path_for(day), "w", encoding="utf-8") as f:
            json.dump(recap, f, indent=1)

    def load(self, day):
        try:
            with open(self.path_for(day), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def done_today(self):
        """A recap was already saved this evening."""
        return self.load(datetime.date.today().isoformat()) is not None

    def last_night(self):
        """The recap for this morning's brief: last evening's, or one made after midnight."""
        today = datetime.date.today()
        for day in (today, today - datetime.timedelta(days=1)):
            r = self.load(day.isoformat())
            if not r:
                continue
            t = datetime.datetime.fromisoformat(r["saved_at"])
            if t.date() == today and t.hour >= 5:
                continue          # tonight's own recap isn't "last night" yet
            return r
        return None
