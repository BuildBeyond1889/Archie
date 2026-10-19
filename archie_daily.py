"""
archie_daily.py - your to-dos and morning brief in today's Obsidian daily note.

Archie keeps one section of the daily note up to date:

    ## Archie
    <!-- archie:start (Archie keeps this part up to date) -->
    ...countdown, to-do checkboxes, brief...
    <!-- archie:end -->

It works both ways: tick a box in Obsidian and Archie marks the task done;
type a new "- [ ] something" line in the To-do list and Archie adds it.
Everything outside the Archie section is yours and never touched.
Plain files only, so it works with Obsidian open or closed, fully offline.
"""

import datetime
import json
import os
import re

from archie_brief import parse_due, when_label

START = "<!-- archie:start (Archie keeps this part up to date) -->"
END = "<!-- archie:end -->"
BRIEF_MARK = "<!-- archie:brief -->"
HEADING = "## Archie"

_TOKENS = [("YYYY", "%Y"), ("YY", "%y"), ("MMMM", "%B"), ("MMM", "%b"), ("MM", "%m"),
           ("dddd", "%A"), ("ddd", "%a"), ("DD", "%d"), ("Do", "{Do}"), ("M", "{M}"), ("D", "{D}")]


def moment_format(fmt, date):
    """Obsidian (moment.js) date formats like 'YYYY-MM-DD' or 'dddd, MMMM Do YYYY'."""
    out, i = "", 0
    while i < len(fmt):
        if fmt[i] == "[":                       # [literal text]
            j = fmt.find("]", i)
            j = len(fmt) if j < 0 else j
            out += fmt[i + 1:j].replace("%", "%%")
            i = j + 1
            continue
        for tok, rep in _TOKENS:
            if fmt.startswith(tok, i):
                out += rep
                i += len(tok)
                break
        else:
            out += "%%" if fmt[i] == "%" else fmt[i]
            i += 1
    d = date.day
    suffix = "th" if 11 <= d % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
    return (date.strftime(out).replace("{Do}", f"{d}{suffix}").replace("{M}", str(date.month))
            .replace("{D}", str(d)))


def settings(vault):
    try:
        with open(os.path.join(vault, ".obsidian", "daily-notes.json"), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    return {"folder": (data.get("folder") or "").strip("/\\"),
            "format": data.get("format") or "YYYY-MM-DD",
            "template": (data.get("template") or "").strip()}


def note_path(vault, date=None):
    s = settings(vault)
    name = moment_format(s["format"], date or datetime.date.today())
    return os.path.join(vault, *[p for p in s["folder"].split("/") if p], *name.split("/")) + ".md"


def _template(vault, date):
    t = settings(vault)["template"]
    if not t:
        return ""
    path = os.path.join(vault, *t.split("/"))
    if not path.lower().endswith(".md"):
        path += ".md"
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    title = moment_format(settings(vault)["format"], date)

    def repl(m):
        tag, fmt = m.group(1), m.group(2)
        if tag == "title":
            return title
        if tag == "time":
            return datetime.datetime.now().strftime("%H:%M")
        return moment_format(fmt or "YYYY-MM-DD", date)
    return re.sub(r"\{\{\s*(date|time|title)(?::([^}]*))?\s*\}\}", repl, text)


def _split(text):
    """(before, block, after); block is None if there's no Archie section yet."""
    a, b = text.find(START), text.find(END)
    if a < 0 or b < a:
        return text, None, ""
    return text[:a], text[a + len(START):b], text[b + len(END):]


_ITEM = re.compile(r"^\s*[-*]\s+\[( |x|X)\]\s+(.+?)\s*$")


def _clean_item(s):
    s = re.sub(r"\s+·\s+(due|overdue).*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


class DailyNote:
    def __init__(self, get_vault, tasks, deadlines):
        self.get_vault = get_vault
        self.tasks = tasks
        self.deadlines = deadlines
        self.last_write = None
        self.coming_up = lambda: []       # Markdown lines for "Coming up" (the calendar)

    def path(self):
        v = self.get_vault()
        return note_path(v) if v and os.path.isdir(v) else None

    def sync(self, brief=None):
        """Read your ticks and new tasks from today's note, then rewrite the Archie
        section. brief = list of Markdown lines to (re)place as today's brief.
        Returns a short summary of what came back from Obsidian (or None)."""
        vault = self.get_vault()
        if not vault or not os.path.isdir(vault):
            return None
        today = datetime.date.today()
        path = note_path(vault, today)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            text = None
        before, block, after = _split(text) if text is not None else ("", None, "")

        # 1. what you did in Obsidian
        changes, ticked = [], set()
        old_brief = None
        if block is not None:
            if BRIEF_MARK in block:
                old_brief = block.split(BRIEF_MARK, 1)[1].strip("\n")
            items = [m for m in (_ITEM.match(l) for l in block.split(BRIEF_MARK)[0].splitlines()) if m]
            all_tasks = self.tasks.load()
            for m in items:
                done, body = m.group(1).lower() == "x", _clean_item(m.group(2))
                if not body:
                    continue
                match = next((t for t in all_tasks if t["text"].lower() == body.lower()), None)
                if match is None:
                    if not done:                       # a task you typed into the note
                        text_, due = parse_due(body)
                        self.tasks.add(text_ or body, due)
                        changes.append(f"added {text_ or body}")
                    continue
                if done:
                    ticked.add(match["text"].lower())
                    if not match["done"]:
                        self.tasks.set_done(match, True)
                        changes.append(f"ticked off {match['text']}")
                elif match["done"]:
                    self.tasks.set_done(match, False)
                    changes.append(f"un-ticked {match['text']}")

        # 2. the fresh Archie section
        lines = []
        for when, what, days in self.deadlines.upcoming(today, limit=3):
            left = "**today!**" if days == 0 else "tomorrow" if days == 1 else f"**{days} days** left"
            lines.append(f"> [!info] {what}: {left} ({when.strftime('%b %d').replace(' 0', ' ')})")
        try:
            coming = self.coming_up() or []
        except Exception:
            coming = []
        if coming:
            lines += ["", "### Coming up"] + coming
        lines += ["", "### To-do"]
        open_tasks = self.tasks.for_brief(today, limit=20)
        done_today = [t for t in self.tasks.load() if t["done"] and t["text"].lower() in ticked]
        for t in open_tasks:
            label = when_label(t["due"], today)
            tail = f" · {'overdue' if label == 'overdue' else 'due ' + label}" if label else ""
            lines.append(f"- [ ] {t['text']}{tail}")
        for t in done_today:
            lines.append(f"- [x] {t['text']}")
        if not open_tasks and not done_today:
            lines.append("- [ ] ")
        lines.append("")
        lines.append("*Tick a box and Archie marks it done. Add a line like `- [ ] call the "
                     "school friday` here and Archie adds it to your list.*")
        brief_part = "\n".join(brief) if brief is not None else old_brief
        if brief_part:
            lines += ["", BRIEF_MARK, brief_part]
        new_block = "\n" + "\n".join(lines).rstrip() + "\n"

        if block is None:
            if text is None:
                text = _template(vault, today)
                before = text + ("\n\n" if text and not text.endswith("\n\n") else "")
            else:
                before = text.rstrip() + "\n\n"
            before += HEADING + "\n"
            after = "\n"
        new_text = before + START + new_block + END + after
        if new_text != text:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_text)
            self.last_write = path
        return ", ".join(changes) if changes else None

    def log(self, entry):
        """'log: fixed the servo jitter' -> '- 14:05 fixed the servo jitter' in today's note
        (under a ### Log heading inside the Archie section, so it's easy to find)."""
        vault = self.get_vault()
        if not vault or not os.path.isdir(vault):
            raise OSError("no Obsidian vault set")
        self.sync()
        path = note_path(vault)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        line = f"- {datetime.datetime.now():%H:%M} {entry.strip()}"
        # the log lives just after the Archie section, and is yours to edit
        idx = text.find(END)
        head = "\n### Log\n"
        if idx >= 0:
            rest = text[idx + len(END):]
            if rest.lstrip("\n").startswith("### Log"):
                # add to the end of the existing log list
                after_head = rest.find("### Log") + len("### Log")
                block_end = re.search(r"\n(?!- )", rest[after_head + 1:])
                cut = after_head + 1 + (block_end.start() if block_end else len(rest) - after_head - 1)
                rest = rest[:cut].rstrip("\n") + "\n" + line + "\n" + rest[cut:].lstrip("\n")
                if not rest.endswith("\n"):
                    rest += "\n"
            else:
                rest = head + line + "\n" + rest
            text = text[:idx + len(END)] + rest
        else:
            text = text.rstrip() + "\n" + head + line + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path
