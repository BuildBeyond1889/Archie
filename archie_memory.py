"""
archie_memory.py - helping Archie know what you're in the middle of.

1. Where I left off: when a focus session ends you can jot where you stopped and what's
   next. It comes back the next time you start that project, and in the morning brief.
   Kept in Memory/left_off.json.

2. This week: every Sunday Archie drafts a short summary of your week from your recaps,
   focus sessions, drawing gym, lectures and chats. You keep or cut each line, and what you
   keep goes into every answer that week. Kept in Memory/this_week.json and in Obsidian
   (Archie/This week.md).

3. Patterns: after a few weeks of logs, when you actually do deep work, where your hours
   go, what's slipping, and a few suggestions. Worked out from the logs; no model needed.
"""

import datetime
import glob
import json
import os
import re

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _key(task):
    return re.sub(r"[^a-z0-9]+", " ", (task or "").lower()).strip()


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, path)
    except OSError:
        pass


# ----- 1. where I left off -------------------------------------------------------------

class LeftOff:
    def __init__(self, path):
        self.path = path

    def _all(self):
        d = _load_json(self.path, {})
        return d if isinstance(d, dict) else {}

    def remember(self, task, note, minutes=0, when=None):
        task, note = (task or "").strip(), (note or "").strip()
        if not task or not note:
            return
        d = self._all()
        when = when or datetime.datetime.now()
        d[_key(task)] = {"task": task, "note": note, "date": when.strftime("%Y-%m-%d"),
                         "time": when.strftime("%H:%M"), "minutes": int(minutes)}
        _save_json(self.path, d)

    def get(self, task):
        return self._all().get(_key(task)) if task and task.strip() else None

    def recent(self, n=3, days=None, today=None):
        today = today or datetime.date.today()
        items = sorted(self._all().values(), key=lambda e: (e.get("date", ""), e.get("time", "")), reverse=True)
        if days is not None:
            cut = (today - datetime.timedelta(days=days)).isoformat()
            items = [e for e in items if e.get("date", "") >= cut]
        return items[:n]


def split_note(note):
    """'stopped at panel 12. next: fight beat' -> ('stopped at panel 12.', 'fight beat')"""
    m = re.search(r"\bnext\s*[:\-]\s*", note or "", re.I)
    stopped, nxt = (note[:m.start()], note[m.end():]) if m else (note or "", "")
    stopped = re.sub(r"^\s*(i\s+)?stopped\s*(at|on|with)?\s*[:\-]?\s*", "", stopped.strip(), flags=re.I)
    return stopped.strip(" ,.;"), nxt.strip()


def when_label(date_iso, today=None):
    today = today or datetime.date.today()
    try:
        d = datetime.date.fromisoformat(date_iso)
    except (TypeError, ValueError):
        return ""
    n = (today - d).days
    if n <= 0:
        return "today"
    if n == 1:
        return "yesterday"
    if n < 7:
        return DAY_NAMES[d.weekday()][:3].lower()
    return d.strftime("%b %d").replace(" 0", " ").lower()


def fmt_minutes(m):
    m = int(m or 0)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


# ----- reading the logs --------------------------------------------------------------------

def focus_log(path):
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    e = json.loads(line)
                    datetime.date.fromisoformat(e["date"])
                    out.append(e)
                except (ValueError, KeyError, TypeError):
                    continue
    except OSError:
        pass
    return out


def gym_log(path):
    d = _load_json(path, [])
    return d if isinstance(d, list) else []


def recent_tasks(entries, n=4):
    seen, out = set(), []
    for e in sorted(entries, key=lambda e: (e.get("date", ""), e.get("start", "")), reverse=True):
        t = (e.get("task") or "").strip()
        if t and _key(t) not in seen:
            seen.add(_key(t))
            out.append(t)
        if len(out) >= n:
            break
    return out


def project_of(task):
    """Group 'comic · ep 3 storyboard' and 'comic storyboard' together:
    the words before a separator, else the first three words."""
    t = (task or "").strip().lower()
    if not t:
        return "(untitled)"
    for sep in ("·", " - ", ":", "|", ","):
        if sep in t:
            return t.split(sep)[0].strip()
    return " ".join(t.split()[:3])


# ----- 3. patterns ------------------------------------------------------------------------

def patterns(focus_entries, gym_entries, today=None, weeks=4):
    today = today or datetime.date.today()
    start = today - datetime.timedelta(days=weeks * 7 - 1)
    heat = [[0] * 24 for _ in range(7)]
    per_week = {}                     # project -> [minutes per week, oldest first]
    per_day_blocks = [[] for _ in range(7)]
    daily = {}
    sessions = 0
    for e in focus_entries:
        try:
            d = datetime.date.fromisoformat(e["date"])
        except (KeyError, ValueError):
            continue
        if d < start or d > today:
            continue
        sessions += 1
        mins = int(e.get("minutes", 0))
        daily[d] = daily.get(d, 0) + mins
        try:
            h, m = map(int, (e.get("start") or "12:00").split(":"))
        except ValueError:
            h, m = 12, 0
        left, hr, mm = mins, h, m
        while left > 0 and hr < 24:           # spread the session over the hours it covered
            chunk = min(left, 60 - mm)
            heat[d.weekday()][hr] += chunk
            left -= chunk
            hr, mm = hr + 1, 0
        wk = (d - start).days // 7
        p = project_of(e.get("task"))
        per_week.setdefault(p, [0] * weeks)[min(weeks - 1, wk)] += mins
    for d, mins in daily.items():
        per_day_blocks[d.weekday()].append(mins)
    # how many weeks of each weekday were in range (for averages)
    counts = [0] * 7
    for i in range(weeks * 7):
        counts[(start + datetime.timedelta(days=i)).weekday()] += 1
    blocks_by_day = []
    for wd in range(7):
        n = sum(1 for e in focus_entries if _in(e, start, today) and
                datetime.date.fromisoformat(e["date"]).weekday() == wd)
        blocks_by_day.append(round(n / counts[wd], 1) if counts[wd] else 0)
    # best hours: the 3-hour window with the most minutes (weekdays and weekends apart)
    def best(days):
        tot = [sum(heat[d][h] for d in days) for h in range(24)]
        scores = [(sum(tot[h:h + 3]), h) for h in range(0, 22)]
        s, h = max(scores)
        return (h, h + 3, s) if s else None
    best_week, best_weekend = best(range(5)), best((5, 6))
    total = sum(sum(r) for r in heat)
    share = (best_week[2] / total) if best_week and total else 0
    slipping = []
    for p, wk in per_week.items():
        if sum(wk[:-2]) >= 60 and sum(wk[-2:]) < 30:
            slipping.append(p)
    # drawing gym: what time it usually happens
    gym_hours = {}
    gym_days = set()
    for g in gym_entries:
        try:
            d = datetime.date.fromisoformat(g.get("date", ""))
        except ValueError:
            continue
        if start <= d <= today:
            gym_days.add(d)
            try:
                gym_hours[int(g.get("at", "12:00").split(":")[0])] = gym_hours.get(int(g.get("at", "12:00").split(":")[0]), 0) + 1
            except ValueError:
                pass
    gym_top = max(gym_hours.items(), key=lambda kv: kv[1]) if gym_hours else None
    return {"start": start, "end": today, "weeks": weeks, "sessions": sessions, "minutes": total,
            "heat": heat, "per_week": dict(sorted(per_week.items(), key=lambda kv: -sum(kv[1]))),
            "blocks_by_day": blocks_by_day, "best_week": best_week, "best_weekend": best_weekend,
            "best_share": share, "slipping": slipping, "gym_top": gym_top,
            "gym_sessions": sum(gym_hours.values()), "gym_days": len(gym_days), "daily": daily}


def _in(e, start, end):
    try:
        d = datetime.date.fromisoformat(e["date"])
    except (KeyError, ValueError):
        return False
    return start <= d <= end


def hour_label(h):
    h = h % 24
    return f"{(h - 1) % 12 + 1}{'am' if h < 12 else 'pm'}" if h not in (0, 12) else ("midnight" if h == 0 else "noon")


def suggestions(p):
    out = []
    if p["sessions"] < 6:
        return ["Not enough to go on yet. After a couple of weeks of focus sessions, I'll show when you do "
                "your best work and what's slipping."]
    if p["best_week"]:
        a, b, _ = p["best_week"]
        out.append(f"Your deep work happens {hour_label(a)}–{hour_label(b)} on weekdays "
                   f"({round(p['best_share'] * 100)}% of your focus time). Protect that window for the hard stuff.")
    bd = p["blocks_by_day"]
    if any(bd):
        top = max(range(7), key=lambda i: bd[i])
        low = min(range(5), key=lambda i: bd[i])
        if bd[top] and bd[top] - bd[low] >= 1:
            out.append(f"{DAY_NAMES[top]}s are your strongest day ({bd[top]:g} sessions on average); "
                       f"{DAY_NAMES[low]}s the lightest ({bd[low]:g}). Plan around that instead of against it.")
    for s in p["slipping"][:2]:
        out.append(f"{s.capitalize()} has barely moved in two weeks. Park it on purpose, or give it one block this weekend?")
    if p["gym_top"] and p["gym_sessions"] >= 4:
        h, n = p["gym_top"]
        out.append(f"The drawing gym sticks around {hour_label(h)} ({n} of {p['gym_sessions']} rounds). "
                   "Keep it there.")
    return out[:4]


def brief_line(p, today=None):
    """One line for the morning brief, or ''."""
    today = today or datetime.date.today()
    if p["sessions"] < 6:
        return ""
    avg = p["blocks_by_day"][today.weekday()]
    bits = []
    if avg:
        bits.append(f"{DAY_NAMES[today.weekday()]}s you average {avg:g} focus session{'s' if avg != 1 else ''}")
    bw = p["best_week"] if today.weekday() < 5 else p["best_weekend"]
    if bw:
        bits.append(f"your best hours are {hour_label(bw[0])}–{hour_label(bw[1])}")
    return ("; ".join(bits) + ".") if bits else ""


# ----- 2. this week -----------------------------------------------------------------------

WEEK_PROMPT = """You are Archie, the user's offline assistant. Below is what happened in their week ({start} to {end}):
their evening recaps, focus sessions (with where they left off), drawing practice, lectures and the chats they had with you.

Write a SHORT, honest summary of their week in JSON, using only what's below (no guessing, no advice):
{{"working_on": ["what they're actively working on, one line each, specific (project + where it's at)"],
 "stalling": ["things they meant to do or mentioned but that didn't move, one line each"],
 "on_mind": ["worries or open questions they said out loud in recaps, one line each"],
 "coming_up": ["deadlines, due dates and events in the next two weeks, one line each"]}}
3 to 5 lines for working_on, 0 to 3 for the others. Plain words, like a friend who was paying attention.

Their week:
{material}"""


def gather_week(end, focus_entries, gym_entries, recaps_dir, lectures, chats, upcoming, left_off):
    """Everything from the last 7 days as text for the weekly prompt, plus hours per project."""
    start = end - datetime.timedelta(days=6)
    lines, hours = [], {}
    for e in sorted((e for e in focus_entries if _in(e, start, end)), key=lambda e: (e["date"], e.get("start", ""))):
        lines.append(f"- focus {e['date']} {e.get('start', '')} {e.get('minutes', 0)} min: {e.get('task') or 'untitled'}"
                     + (f" ({e['notes']})" if e.get("notes") else ""))
        p = project_of(e.get("task"))
        hours[p] = hours.get(p, 0) + int(e.get("minutes", 0))
    gym_n = sum(g.get("poses", 0) for g in gym_entries if start.isoformat() <= g.get("date", "") <= end.isoformat())
    if gym_n:
        gym_min = sum(g.get("seconds", 0) for g in gym_entries if start.isoformat() <= g.get("date", "") <= end.isoformat()) // 60
        lines.append(f"- drawing gym: {gym_n} pictures, {gym_min} min")
        hours["drawing gym"] = hours.get("drawing gym", 0) + gym_min
    for lo in left_off:
        if start.isoformat() <= lo.get("date", "") <= end.isoformat():
            lines.append(f"- where they left off on {lo['task']}: {lo['note']}")
    for path in sorted(glob.glob(os.path.join(recaps_dir, "*.json"))):
        day = os.path.basename(path)[:10]
        if start.isoformat() <= day <= end.isoformat():
            r = _load_json(path, {})
            bits = []
            for k in ("today", "mind"):
                if r.get(k):
                    bits.append(f"{k}: " + "; ".join(r[k]))
            for t in r.get("tomorrow") or []:
                bits.append("to do: " + (t.get("task", "") if isinstance(t, dict) else str(t)))
            if bits:
                lines.append(f"- recap {day}: " + " | ".join(bits))
    for day, title in lectures:
        lines.append(f"- lecture {day}: {title}")
    for day, title in chats[:25]:
        lines.append(f"- chat {day}: {title}")
    for u in upcoming:
        lines.append(f"- coming up: {u}")
    return start, "\n".join(lines) or "(nothing logged this week)", hours


def draft_week(chat, model, end, material, start):
    raw = chat(model, WEEK_PROMPT.format(start=start.strftime("%b %d"), end=end.strftime("%b %d"),
                                         material=material[:14000]),
               max_tokens=900, timeout=600, json_mode=True, temperature=0.3, num_ctx=8192)
    try:
        d = json.loads(raw)
    except (ValueError, TypeError):
        m = re.search(r"\{.*\}", raw or "", re.S)
        d = json.loads(m.group(0)) if m else {}
    out = {}
    for k in ("working_on", "stalling", "on_mind", "coming_up"):
        out[k] = [str(x).strip() for x in d.get(k) or [] if str(x).strip()][:6]
    return out


SECTIONS = [("working_on", "what you're working on"), ("stalling", "stalling"),
            ("on_mind", "on your mind"), ("coming_up", "coming up")]


class ThisWeek:
    def __init__(self, path):
        self.path = path

    def load(self):
        d = _load_json(self.path, {})
        return d if isinstance(d, dict) else {}

    def save(self, week_of, kept, hours):
        _save_json(self.path, {"week_of": week_of, "saved": datetime.date.today().isoformat(),
                               "kept": kept, "hours": hours})

    def due(self, today=None):
        """True from Sunday on if this week hasn't been reviewed yet."""
        today = today or datetime.date.today()
        last_sunday = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
        saved = self.load().get("week_of", "")
        return saved < last_sunday.isoformat()

    def prompt_block(self, today=None):
        """What goes into the system prompt: only lines the user kept, only while they're fresh."""
        today = today or datetime.date.today()
        d = self.load()
        try:
            if (today - datetime.date.fromisoformat(d.get("week_of", ""))).days > 10:
                return ""
        except ValueError:
            return ""
        kept = d.get("kept") or {}
        parts = []
        for k, label in SECTIONS:
            if kept.get(k):
                parts.append(f"{label}: " + "; ".join(kept[k]))
        if not parts:
            return ""
        return ("What the user is in the middle of this week (they reviewed this themselves; use it when it helps, "
                "don't recite it):\n- " + "\n- ".join(parts))


def week_markdown(week_of, kept, hours):
    lines = ["---", "tags: [archie, weekly]", f"week_of: {week_of}", "---", "",
             f"# This week · {week_of}", "",
             "> [!info] Archie keeps this in mind for the week. Edit or delete lines here and in Archie's review.", ""]
    if hours:
        lines += ["## Where the hours went", ""]
        lines += [f"- {p}: {fmt_minutes(m)}" for p, m in sorted(hours.items(), key=lambda kv: -kv[1])]
        lines.append("")
    for k, label in SECTIONS:
        if kept.get(k):
            lines += [f"## {label[0].upper() + label[1:]}", ""]
            lines += [f"- {x}" for x in kept[k]]
            lines.append("")
    return "\n".join(lines)
