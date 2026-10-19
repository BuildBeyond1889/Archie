"""
archie_brief.py - the morning brief, your to-do list and deadlines.

Plain text files you can also edit by hand in Notepad:
  tasks.txt      one task per line:   [ ] Test servo wiring | 2026-09-29
                                      [x] Move Archie to the Seagate
  deadlines.txt  one per line:        2027-01-19 | First day of classes

In the chat you can type:
  add: test servo wiring tomorrow     -> new task (dates like today, tomorrow,
                                         friday, 10/3, 2026-10-03 are understood)
  done: servo                         -> ticks off the task that matches
  deadline: portfolio due 11/15       -> new deadline
  tasks                               -> shows your list
"""

import datetime
import json
import os
import random
import re
import subprocess
import sys

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
SHORT_DAYS = [d[:3] for d in WEEKDAYS]

TASKS_STARTER = """\
# YOUR TO-DO LIST - Archie shows these in the morning brief.
# Add tasks by typing "add: ..." in the chat, or right here:
#   [ ] something to do
#   [ ] something with a due date | 2026-10-03
#   [x] something already done
# Lines starting with # are ignored.
"""

DEADLINES_STARTER = """\
# DEADLINES - Archie counts down to these in the morning brief.
# Format:  YYYY-MM-DD | what it is
# Add more by typing "deadline: portfolio due 11/15" in the chat, or right here.
# Lines starting with # are ignored.

2027-01-19 | First day of classes
"""


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

def parse_due(text, today=None):
    """Pull a date off the end of a task. 'test servo tomorrow' ->
    ('test servo', date). Returns (text, None) when there's no date."""
    today = today or datetime.date.today()
    t = text.strip()
    pattern = (r"(?:\s+(?:by|on|due|for|before))?\s+("
               r"today|tonight|tomorrow|next week|"
               r"(?:next\s+)?(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*|"
               r"\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s*$")
    m = re.search(pattern, t, flags=re.IGNORECASE)
    if not m:
        return t, None
    word = m.group(1).lower()
    due = None
    if word in ("today", "tonight"):
        due = today
    elif word == "tomorrow":
        due = today + datetime.timedelta(days=1)
    elif word == "next week":
        due = today + datetime.timedelta(days=7)
    elif re.match(r"\d{4}-", word):
        try:
            due = datetime.date(*map(int, word.split("-")))
        except ValueError:
            return t, None
    elif "/" in word:
        parts = [int(p) for p in word.split("/")]
        year = parts[2] if len(parts) == 3 else today.year
        if year < 100:
            year += 2000
        try:
            due = datetime.date(year, parts[0], parts[1])
        except ValueError:
            return t, None
        if len(parts) == 2 and due < today:
            due = due.replace(year=due.year + 1)
    else:
        name = word.split()[-1][:3]
        if name in SHORT_DAYS:   # the next one coming up (never today)
            ahead = (SHORT_DAYS.index(name) - today.weekday()) % 7 or 7
            due = today + datetime.timedelta(days=ahead)
    if due is None:
        return t, None
    return t[:m.start()].strip(" ,.-") or t, due


def when_label(due, today=None):
    today = today or datetime.date.today()
    if due is None:
        return ""
    d = (due - today).days
    if d < 0:
        return "overdue"
    if d == 0:
        return "today"
    if d == 1:
        return "tomorrow"
    if d < 7:
        return WEEKDAYS[due.weekday()].capitalize()
    return due.strftime("%b %d").replace(" 0", " ")


# ---------------------------------------------------------------------------
# Tasks and deadlines (plain text files)
# ---------------------------------------------------------------------------

def _read_lines(path, starter):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(starter)
    with open(path, encoding="utf-8-sig") as f:
        return f.read().splitlines()


class Tasks:
    def __init__(self, path):
        self.path = path

    def load(self):
        out = []
        for i, line in enumerate(_read_lines(self.path, TASKS_STARTER)):
            s = line.strip()
            m = re.match(r"\[( |x|X)\]\s*(.+)", s)
            if not m:
                continue
            body, due = m.group(2), None
            if "|" in body:
                body, date_part = (x.strip() for x in body.rsplit("|", 1))
                try:
                    due = datetime.date.fromisoformat(date_part)
                except ValueError:
                    body = m.group(2)
            out.append({"line": i, "done": m.group(1).lower() == "x", "text": body, "due": due})
        return out

    def _rewrite(self, fn):
        lines = _read_lines(self.path, TASKS_STARTER)
        lines = fn(lines)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def add(self, text, due=None):
        entry = f"[ ] {text}" + (f" | {due.isoformat()}" if due else "")
        self._rewrite(lambda lines: lines + [entry])

    def set_done(self, task, done=True):
        def fn(lines):
            if task["line"] < len(lines):
                lines[task["line"]] = re.sub(r"^\s*\[( |x|X)\]", "[x]" if done else "[ ]",
                                             lines[task["line"]], count=1)
            return lines
        self._rewrite(fn)

    def find(self, words):
        """Best matching not-done task for 'done: servo'."""
        words = [w for w in re.findall(r"\w+", words.lower()) if len(w) > 1]
        best, score = None, 0
        for t in self.load():
            if t["done"]:
                continue
            s = sum(w in t["text"].lower() for w in words)
            if s > score:
                best, score = t, s
        return best

    def for_brief(self, today=None, limit=6):
        """Overdue, due soon, and undated tasks, most urgent first."""
        today = today or datetime.date.today()
        todo = [t for t in self.load() if not t["done"]]
        soon = [t for t in todo if t["due"] and (t["due"] - today).days <= 7]
        undated = [t for t in todo if not t["due"]]
        soon.sort(key=lambda t: t["due"])
        return (soon + undated)[:limit]


class Deadlines:
    def __init__(self, path):
        self.path = path

    def load(self):
        out = []
        for line in _read_lines(self.path, DEADLINES_STARTER):
            s = line.strip()
            if not s or s.startswith("#") or "|" not in s:
                continue
            date_part, what = (x.strip() for x in s.split("|", 1))
            try:
                out.append((datetime.date.fromisoformat(date_part), what))
            except ValueError:
                continue
        return sorted(out)

    def add(self, when, what):
        _read_lines(self.path, DEADLINES_STARTER)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(f"{when.isoformat()} | {what}\n")

    def upcoming(self, today=None, limit=2):
        today = today or datetime.date.today()
        return [(d, w, (d - today).days) for d, w in self.load() if d >= today][:limit]


# ---------------------------------------------------------------------------
# Remembering what the last brief saw
# ---------------------------------------------------------------------------

class BriefState:
    def __init__(self, path):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=1)
        except OSError:
            pass

    def shown_today(self):
        return self.data.get("last_date") == datetime.date.today().isoformat()

    def mark_shown(self):
        self.data["last_date"] = datetime.date.today().isoformat()
        self.save()


def notes_snapshot(folder):
    files = {}
    for root, dirs, fs in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fn in fs:
            rel = os.path.relpath(os.path.join(root, fn), folder).replace("\\", "/")
            files[rel] = 1
    return files


def new_notes(folder, state):
    """Files added to the Notes folder since the last brief (None on first run)."""
    now = notes_snapshot(folder)
    before = state.data.get("notes")
    state.data["notes"] = now
    if before is None:
        return None
    return sorted(set(now) - set(before))


# ---------------------------------------------------------------------------
# Chat commands:  add: / done: / deadline: / tasks
# ---------------------------------------------------------------------------

def handle_command(text, tasks, deadlines):
    """Returns a reply string if the message was a to-do command, else None."""
    s = text.strip()
    low = s.lower()
    for prefix in ("add:", "todo:", "task:", "remind me to "):
        if low.startswith(prefix):
            body, due = parse_due(s[len(prefix):])
            if not body:
                return "Tell me what to add, like:  add: test servo wiring tomorrow"
            tasks.add(body, due)
            return f"Added to your list: {body}" + (f" (due {when_label(due)})" if due else "")
    if low.startswith("done:"):
        t = tasks.find(s[5:])
        if not t:
            return "I couldn't find an open task matching that. Type  tasks  to see your list."
        tasks.set_done(t)
        return f"Nice. Ticked off: {t['text']}"
    if low.startswith("deadline:"):
        body, due = parse_due(s[9:])
        if not due:
            return "Give it a date, like:  deadline: portfolio due 11/15"
        deadlines.add(due, body)
        days = (due - datetime.date.today()).days
        return f"Deadline saved: {body} on {due.strftime('%b %d').replace(' 0', ' ')} ({days} days away)"
    if low in ("tasks", "todo", "to do", "my tasks", "list"):
        items = [t for t in tasks.load() if not t["done"]]
        if not items:
            return "Your list is empty. Add something with  add: ..."
        lines = [f"- {t['text']}" + (f"  ({when_label(t['due'])})" if t["due"] else "")
                 for t in items]
        return "Your list:\n" + "\n".join(lines)
    return None


# ---------------------------------------------------------------------------
# Start with Windows
# ---------------------------------------------------------------------------

def startup_shortcut_path():
    appdata = os.environ.get("APPDATA", "")
    return os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs",
                        "Startup", "Archie.lnk")


def set_start_with_windows(enable, app_dir):
    """Add or remove Archie from the Startup folder. Returns an error string or None."""
    if sys.platform != "win32":
        return "Start with Windows only works on Windows."
    link = startup_shortcut_path()
    if not enable:
        try:
            if os.path.exists(link):
                os.remove(link)
            return None
        except OSError as e:
            return f"Couldn't remove it: {e.strerror}"
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    target = pyw if os.path.exists(pyw) else exe
    script = os.path.join(app_dir, "archie.py")
    icon = os.path.join(app_dir, "archie.ico")
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
          "$s.TargetPath='{t}';$s.Arguments='\"{a}\"';$s.WorkingDirectory='{w}';"
          "$s.IconLocation='{i}';$s.Description='Archie';$s.Save()").format(
        link=link.replace("'", "''"), t=target.replace("'", "''"),
        a=script.replace("'", "''"), w=app_dir.replace("'", "''"), i=icon.replace("'", "''"))
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
                       check=True, capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return None
    except Exception as e:
        return f"Couldn't add Archie to startup: {e}"


def starts_with_windows():
    return sys.platform == "win32" and os.path.exists(startup_shortcut_path())
