"""Archie's dates reader: finds the dates in a syllabus, course schedule, assignment sheet, portal screenshot,
work schedule or flyer, and turns them into calendar events. Nothing goes on the calendar until you tick it.

  read(path, ...)  -> the text (PDF, Word, text; pictures through the vision model)
  find(text, ...)  -> the main model lists what it sees as JSON; plan() turns that into events
  plan(raw, ...)   -> rows for the card: weekly classes/labs (split around breaks), exams, quizzes, due dates, other
  add(cal, rows)   -> puts the ticked rows on the calendar; returns their ids (for undo)

Rules:
  - exams, tests and quizzes are titled "<CLASS> Midterm", "<CLASS> Quiz 2", ... so they read well in the brief
  - a weekly class repeats from its first day to its last; a break (spring break, etc.) splits it, so it skips those days
  - a fuzzy date ("week 6", "TBA") is never guessed: it shows as "needs a date" and stays unticked
  - anything already on the calendar (same title, same day) shows as "already on your calendar" and stays unticked
"""
import datetime
import json
import re

KIND_ORDER = ["class", "lab", "exam", "test", "quiz", "due", "event"]
GROUPS = [("CLASSES (WEEKLY)", ("class", "lab")), ("EXAMS", ("exam", "test", "quiz")), ("DUE", ("due",)),
          ("OTHER", ("event",)), ("NEEDS A DATE", ())]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
MAX_CHARS = 12000          # per piece sent to the model
MAX_TOTAL = 60000          # longer documents: only the first part is read

PROMPT = """You read school and work documents and list every dated thing in them, for a calendar.
Today is {today}. The document is named "{name}".

Reply with JSON only, in exactly this shape:
{{"course": "the course code and number as written, like BIO 101 (or empty if none)",
  "term_start": "YYYY-MM-DD or empty",
  "term_end": "YYYY-MM-DD or empty",
  "breaks": [{{"name": "Spring break", "start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}],
  "items": [{{"kind": "class|lab|exam|test|quiz|due|event",
             "title": "short name, like Midterm, Final, Quiz 1, Lab report 1, Office hours",
             "weekly": true or false,
             "days": ["Mon","Wed"] (only for weekly things),
             "date": "YYYY-MM-DD for a one-time thing; for a weekly thing, its first day if written",
             "until": "YYYY-MM-DD, the last day of a weekly thing if written",
             "time": "HH:MM 24-hour or empty",
             "end_time": "HH:MM 24-hour or empty",
             "where": "room or place, or empty",
             "quote": "the exact sentence from the document this came from",
             "page": page number or 0,
             "fuzzy": "if the date is not a real date (week 6, TBA, end of term): the words used; else empty"}}]}}

Rules:
- Lectures/class meetings are kind "class" with weekly true and their days. Lab sections are "lab".
- Midterms and finals are "exam". Quizzes are "quiz". Tests are "test". Homework, papers, reports, projects,
  problem sets and anything "due" are "due". Office hours, add/drop deadlines, holidays and the rest are "event".
- Use the year the document is for. If no year is written, use the next time that date comes after the term starts.
- Never invent a date. If the document says "week 6" or "TBA", put that in "fuzzy" and leave "date" empty.
- One item per dated thing. Do not repeat the weekly class for each week.

The document:
<<<
{text}
>>>"""

VISION_ASK = ("Type out all the text in this picture exactly, in reading order, keeping every date, day, time and "
              "room. Plain text, no comments.")


# ---- reading the file -----------------------------------------------------------------------------
def read(path, read_text, read_image=None):
    """The document's text. read_text: archie_brain.read_text; read_image(path) -> text (the vision model)."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext in ("png", "jpg", "jpeg", "gif", "webp", "bmp", "heic"):
        if not read_image:
            raise ValueError("I need the vision model to read pictures.")
        return read_image(path)
    return read_text(path)


def pieces(text):
    text = text[:MAX_TOTAL]
    if len(text) <= MAX_CHARS:
        return [text]
    out, cur = [], ""
    for para in re.split(r"(\n\s*\n)", text):
        if len(cur) + len(para) > MAX_CHARS and cur.strip():
            out.append(cur)
            cur = ""
        cur += para
        while len(cur) > MAX_CHARS:
            out.append(cur[:MAX_CHARS])
            cur = cur[MAX_CHARS:]
    if cur.strip():
        out.append(cur)
    return out


def _json(s):
    s = (s or "").strip()
    m = re.search(r"\{.*\}", s, re.S)
    try:
        return json.loads(m.group(0) if m else s)
    except ValueError:
        return {}


def find(text, name, ask, today=None, progress=lambda i, n: None):
    """ask(prompt) -> the model's reply. Returns the merged raw result."""
    today = today or datetime.date.today()
    parts = pieces(text)
    merged = {"course": "", "term_start": "", "term_end": "", "breaks": [], "items": []}
    for i, part in enumerate(parts):
        progress(i, len(parts))
        got = _json(ask(PROMPT.format(today=today.isoformat(), name=name, text=part)))
        for k in ("course", "term_start", "term_end"):
            if not merged[k] and isinstance(got.get(k), str):
                merged[k] = got[k].strip()
        merged["breaks"] += [b for b in got.get("breaks") or [] if isinstance(b, dict)]
        merged["items"] += [x for x in got.get("items") or [] if isinstance(x, dict)]
    merged["truncated"] = len(text) > MAX_TOTAL
    return merged


# ---- turning it into events ---------------------------------------------------------------------
def _date(s, today, term_start=None):
    """A date from what the model wrote (ISO, 3/26, March 26, Mar 26 2027). None if it isn't one."""
    s = str(s or "").strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    try:
        if m:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = re.match(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", s)
        if m:
            mo, d, y = int(m.group(1)), int(m.group(2)), m.group(3)
        else:
            m = re.search(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", s.lower())
            if not m or m.group(1) not in MONTHS:
                return None
            mo, d, y = MONTHS.index(m.group(1)) + 1, int(m.group(2)), m.group(3)
        if y:
            y = int(y)
            return datetime.date(y + 2000 if y < 100 else y, mo, d)
        base = term_start or today - datetime.timedelta(days=60)
        cand = datetime.date(base.year, mo, d)
        return cand if cand >= base else datetime.date(base.year + 1, mo, d)
    except ValueError:
        return None


def _time(s):
    s = str(s or "").strip().lower()
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").replace(".", "")
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    return f"{h:02d}:{mi:02d}" if 0 <= h < 24 and 0 <= mi < 60 else None


def _days(v):
    out = []
    for d in v if isinstance(v, list) else re.split(r"[,/&\s]+", str(v or "")):
        k = str(d).strip().lower()[:3]
        if k == "thr":
            k = "thu"
        if k in DAYS and DAYS.index(k) not in out:
            out.append(DAYS.index(k))
    return sorted(out)


def nice_time(t):
    if not t:
        return ""
    h, m = map(int, t.split(":"))
    return f"{h % 12 or 12}:{m:02d} {'AM' if h < 12 else 'PM'}"


def nice_date(d, year=False):
    return f"{DAY_NAMES[d.weekday()]} {d:%b} {d.day}" + (f", {d.year}" if year else "")


def course_title(course, kind, title):
    """'BIO 101 Midterm', 'BIO 101 Quiz 2': exams, tests and quizzes carry the class name."""
    title = re.sub(r"\s+", " ", str(title or "")).strip(" .:-") or kind.title()
    if title.lower() == kind:
        title = kind.title()
    if kind in ("exam", "test", "quiz") and course:
        bare = re.sub(r"\W", "", course.lower())
        if bare and bare not in re.sub(r"\W", "", title.lower()):
            title = f"{course} {title[0].upper() + title[1:]}"
    elif kind == "class" and course:
        if title.lower() in ("class", "lecture", "lectures", "lecture", "class", "class meetings", "lecture meetings", course.lower()):
            title = course
    elif kind == "lab" and course:
        if title.lower() in ("lab", "labs", "lab section", "lab sections", "laboratory"):
            title = f"{course} Lab"
    return title[0].upper() + title[1:]


def plan(raw, course=None, today=None, existing=()):
    """Rows for the card. Each row: {kind, title, when, quote, page, on, events: [calendar.add kwargs], note}."""
    today = today or datetime.date.today()
    course = (course if course is not None else raw.get("course") or "").strip()
    t0, t1 = _date(raw.get("term_start"), today), _date(raw.get("term_end"), today)
    breaks = []
    for b in raw.get("breaks") or []:
        a, z = _date(b.get("start"), today, t0), _date(b.get("end"), today, t0)
        if a:
            breaks.append((str(b.get("name") or "Break").strip(), a, z or a))
    have = {(str(e.get("title", "")).strip().lower(), e.get("date")) for e in existing}
    rows, seen = [], set()
    for x in raw.get("items") or []:
        kind = str(x.get("kind") or "event").lower().strip()
        kind = kind if kind in KIND_ORDER else ("due" if kind in ("assignment", "homework", "deadline") else "event")
        base = re.sub(r"\s+", " ", str(x.get("title") or "")).strip(" .:-")
        if course and base.lower() == course.lower():
            base = kind
        title = course_title(course, kind, base)
        quote = re.sub(r"\s+", " ", str(x.get("quote") or "")).strip()
        try:
            page = int(x.get("page") or 0)
        except (TypeError, ValueError):
            page = 0
        tm, tend = _time(x.get("time")), _time(x.get("end_time"))
        where = str(x.get("where") or "").strip()
        days = _days(x.get("days"))
        weekly = bool(x.get("weekly")) and bool(days)
        row = {"kind": kind, "base": base, "title": title, "quote": quote, "page": page, "on": True, "events": [], "note": ""}
        span = f"{nice_time(tm)} – {nice_time(tend)}" if tm and tend else nice_time(tm)
        if weekly:
            start = _date(x.get("date"), today, t0) or t0
            until = _date(x.get("until"), today, t0) or t1
            if not start or not until or until < start:
                row.update(on=False, fuzzy=True, when=" & ".join(DAY_NAMES[d] for d in days) + (f" · {span}" if span else "")
                           + " · weekly, but I couldn't find the first and last day of term",
                           note="add the term dates and read it again, or add it from the calendar")
                rows.append(row)
                continue
            for d in days:
                first = start + datetime.timedelta(days=(d - start.weekday()) % 7)
                segs, a = [], first
                for _, b0, b1 in sorted(breaks, key=lambda b: b[1]):
                    if b1 < a or b0 > until:
                        continue
                    stop = b0 - datetime.timedelta(days=1)
                    if stop >= a:
                        segs.append((a, stop))
                    a = b1 + datetime.timedelta(days=1)
                    a += datetime.timedelta(days=(d - a.weekday()) % 7)
                if a <= until:
                    segs.append((a, until))
                for s0, s1 in segs:
                    if s0 > s1:
                        continue
                    row["events"].append({"title": title, "date": s0, "kind": kind if kind in ("class", "lab") else "event",
                                          "time": tm, "notes": where, "repeat": "weekly", "until": s1})
            row["when"] = (" & ".join(DAY_NAMES[d] for d in days) + (f" {span}" if span else "")
                           + f" · {start:%b} {start.day} – {until:%b} {until.day}" + (f" · {where}" if where else ""))
            if kind == "event":
                row["on"] = False          # office hours and the like: there if you want them
        else:
            d = _date(x.get("date"), today, t0)
            fz = str(x.get("fuzzy") or "").strip()
            if not d:
                row.update(on=False, fuzzy=True, when=(fz or str(x.get("date") or "no date written")) + " · not a real date yet",
                           note="I won't guess it")
                rows.append(row)
                continue
            row["when"] = nice_date(d) + (f" · {span}" if span else "") + (f" · {where}" if where else "")
            row["events"].append({"title": title, "date": d, "kind": kind, "time": tm,
                                  "notes": " · ".join(p for p in (course if kind == "due" else "", where) if p),
                                  "repeat": None, "until": None})
        key = (kind, title.lower(), row["when"])
        if key in seen:
            continue
        seen.add(key)
        if row["events"] and all((e["title"].lower(), e["date"].isoformat()) in have for e in row["events"]):
            row.update(on=False, note="already on your calendar")
        rows.append(row)
    rows.sort(key=lambda r: (_group(r), r["events"][0]["date"] if r["events"] else datetime.date.max, r["title"]))
    warns = []
    for name, a, z in breaks:
        weekly = [r for r in rows if r["events"] and r["events"][0]["repeat"] and r["on"]]
        if weekly:
            warns.append(f"{name}, {a:%b} {a.day}" + (f" – {z:%b} {z.day}" if z != a else "")
                         + ": the weekly classes skip those days.")
        else:
            warns.append(f"{name}, {a:%b} {a.day}" + (f" – {z:%b} {z.day}" if z != a else "") + ".")
    if raw.get("truncated"):
        warns.append("It's a long document; I read the first part only.")
    return {"course": course, "rows": rows, "warns": warns}


def _group(r):
    if r.get("fuzzy"):
        return len(GROUPS) - 1
    for i, (_, kinds) in enumerate(GROUPS):
        if r["kind"] in kinds:
            return i
    return 3


def grouped(rows):
    out = []
    for i, (label, _) in enumerate(GROUPS):
        rs = [r for r in rows if _group(r) == i]
        if rs:
            out.append((label, rs))
    return out


def retitle(p, course):
    """The card's class changed: re-title the rows (and their events) for the new class name."""
    old, course = p["course"], (course or "").strip()
    for r in p["rows"]:
        r["title"] = course_title(course, r["kind"], r["base"])
        for e in r["events"]:
            e["title"] = r["title"]
            if r["kind"] == "due":
                rest = e.get("notes", "")[len(old):].lstrip(" ·") if old and e.get("notes", "").startswith(old) else e.get("notes", "")
                e["notes"] = " · ".join(x for x in (course, rest) if x)
    p["course"] = course
    return p


def add(cal, rows):
    """Put the ticked rows on the calendar. Returns the new event ids."""
    ids = []
    for r in rows:
        if not r.get("on"):
            continue
        for e in r["events"]:
            ev = cal.add(e["title"], e["date"], kind=e["kind"], time=e["time"], notes=e.get("notes") or "",
                         repeat=e.get("repeat"), until=e.get("until"))
            ids.append(ev["id"])
    return ids
