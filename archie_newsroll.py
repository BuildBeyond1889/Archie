"""
archie_newsroll.py - the news notes in Obsidian, folded up as they age so the graph stays readable.

    days   ->  each day links to the day before; the weekly review links its days (a small net forms each week)
    weeks  ->  each weekly review links the week before (weeks are kept)
    months ->  once a month is over (and its last week's review is written), a month note in
               Archie/World/Monthly/<Month YYYY>.md (e.g. October 2026.md) links its weeks and the month before, with a summary of the month;
               that month's daily notes move to Archie/World/Archive/<YYYY-MM>/ (still searchable; links keep working)

In the graph, the filter  -path:"Archie/World/Archive"  hides the archived days, so you see
month <- month, each month holding its weeks, and only the current month's days.

Safe to run any time and as often as you like: everything it does is checked first and done once.
Archie only writes yesterday's daily note and the current week's review, so nothing it still writes is moved.
"""

import datetime
import json
import os
import re
import shutil

DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")
WEEK = re.compile(r"^(\d{4})-W(\d{2})\.md$")          # the old names ("2026-W45.md")
WEEK_KEY = re.compile(r"^week:\s*(\d{4}-W\d{2})\s*$", re.M)
PREV_DAY = "<!-- archie: previous day -->"
PREV_WEEK = "<!-- archie: previous week -->"
SETTLE_DAYS = 9          # a month's days move once its last day is this old (its last week's review is written by then)


def _read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _write(p, text):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)


def _week_of(day):
    y, w, _ = day.isocalendar()
    return f"{y}-W{w:02d}"


def _week_month(wk):
    """A week belongs to the month its Thursday is in (the ISO rule)."""
    y, w = int(wk[:4]), int(wk[6:8])
    thu = datetime.date.fromisocalendar(y, w, 4)
    return f"{thu:%Y-%m}"


def _week_take(text):
    m = re.search(r"^## The week\n(.+?)(?:\n\n|\n## |\Z)", text or "", re.S | re.M)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def week_name(wk):
    """'2026-W45' -> 'Week of Nov 2, 2026' (the Monday)."""
    mon = datetime.date.fromisocalendar(int(wk[:4]), int(wk[6:8]), 1)
    return f"Week of {mon:%b} {mon.day}, {mon.year}"


def _rename_weeks(world, weekly):
    """Weekly reviews named '2026-W45' become 'Week of Nov 2, 2026' (and their charts), with every link in the
    news notes fixed. Returns how many were renamed."""
    if not os.path.isdir(weekly):
        return 0
    ren = {}
    for fn in os.listdir(weekly):
        m = WEEK.match(fn)
        if not m:
            continue
        wk = fn[:-3]
        new = week_name(wk)
        if os.path.exists(os.path.join(weekly, new + ".md")):
            continue
        os.replace(os.path.join(weekly, fn), os.path.join(weekly, new + ".md"))
        png = os.path.join(weekly, f"{wk} fighting.png")
        if os.path.exists(png) and not os.path.exists(os.path.join(weekly, f"{new} fighting.png")):
            os.replace(png, os.path.join(weekly, f"{new} fighting.png"))
        ren[wk] = new
    if not ren:
        return 0
    pat = re.compile(r"(\[\[)(" + "|".join(re.escape(k) for k in ren) + r")(?=[\]|# ])")
    for dp, dns, fns in os.walk(world):
        for fn in fns:
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            text = _read(p)
            if text is None:
                continue
            new_text = pat.sub(lambda m: m.group(1) + ren[m.group(2)], text)
            if new_text != text:
                _write(p, new_text)
    return len(ren)


HUB_TAGS = {"archie-world", "weekly-review"}


def _untag(path):
    """Take the hub tags off a finished month's day or week note (other tags stay)."""
    text = _read(path)
    if not text:
        return False
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return False
    fm = m.group(1)
    t = re.search(r"^tags:\s*\[(.*?)\]\s*$", fm, re.M)
    if not t:
        return False
    tags = [x.strip() for x in t.group(1).split(",") if x.strip()]
    keep = [x for x in tags if x not in HUB_TAGS]
    if keep == tags:
        return False
    fm2 = fm[:t.start()] + (f"tags: [{', '.join(keep)}]" if keep else "news: archived") + fm[t.end():]
    _write(path, "---\n" + fm2 + "\n---\n" + text[m.end():])
    return True


def _drop_line(path, marker):
    """Remove a link line added earlier (one that crossed from one month into another)."""
    text = _read(path)
    if not text or marker not in text:
        return False
    new_text = re.sub(r"\n*" + re.escape(marker) + r"\n[^\n]*\n?", "\n", text).rstrip("\n") + "\n"
    _write(path, new_text)
    return True


def _add_line(path, marker, line, today_guard=None):
    """Add one link line at the end of a note, once."""
    text = _read(path)
    if text is None or marker in text:
        return False
    _write(path, text.rstrip("\n") + f"\n\n{marker}\n{line}\n")
    return True


def roll(vault, chat=None, model=None, today=None, report=lambda msg: None):
    """One pass. chat(model, prompt, **kw) -> str writes the month summaries (optional). Returns what it did."""
    today = today or datetime.date.today()
    world = os.path.join(vault, "Archie", "World")
    if not os.path.isdir(world):
        return {}
    weekly = os.path.join(world, "Weekly")
    monthly = os.path.join(world, "Monthly")
    archive = os.path.join(world, "Archive")
    done = {"linked_days": 0, "linked_weeks": 0, "months": [], "archived": 0, "renamed_weeks": _rename_weeks(world, weekly)}

    # every day note, wherever it is now
    days = {}
    for dp, dns, fns in os.walk(world):
        rel = os.path.relpath(dp, world).replace("\\", "/")
        if rel.startswith(("Weekly", "Monthly", "Lessons")):
            continue
        for fn in fns:
            m = DAY.match(fn)
            if m:
                try:
                    days[datetime.date(*map(int, m.groups()))] = os.path.join(dp, fn)
                except ValueError:
                    pass
    order = sorted(days)

    # 1. days link to the day before, inside the same month (only days Archie won't write again)
    for prev, day in zip(order, order[1:]):
        if prev.strftime("%Y-%m") != day.strftime("%Y-%m"):
            _drop_line(days[day], PREV_DAY)               # each month is its own cluster
            continue
        if (today - day).days >= 2 and _add_line(days[day], PREV_DAY, f"← [[{prev.isoformat()}]]"):
            done["linked_days"] += 1

    # 2. weeks link to the week before (a weekly review is known by its "week: 2026-W45" line, whatever its name)
    names = {}
    if os.path.isdir(weekly):
        for fn in os.listdir(weekly):
            if fn.endswith(".md"):
                m = WEEK_KEY.search((_read(os.path.join(weekly, fn)) or "")[:400])
                if m:
                    names[m.group(1)] = fn[:-3]
    weeks = sorted(names)
    for prev, wk in zip(weeks, weeks[1:]):
        if _week_month(prev) != _week_month(wk):
            _drop_line(os.path.join(weekly, names[wk] + ".md"), PREV_WEEK)
            continue
        if wk != _week_of(today) and _add_line(os.path.join(weekly, names[wk] + ".md"), PREV_WEEK, f"← [[{names[prev]}]]"):
            done["linked_weeks"] += 1

    # 3. finished months: a month note, and the month's days into the archive
    months = sorted({d.strftime("%Y-%m") for d in order} | {_week_month(w) for w in weeks})
    mname = lambda m: datetime.date(int(m[:4]), int(m[5:7]), 1).strftime("%B %Y")   # 2026-10 -> October 2026
    # month notes used to be named 2026-10.md: rename them to "October 2026.md" and fix the links between them
    if os.path.isdir(monthly):
        olds = [f[:-3] for f in os.listdir(monthly) if re.fullmatch(r"\d{4}-\d{2}\.md", f)]
        for old in olds:
            src, dst = os.path.join(monthly, old + ".md"), os.path.join(monthly, mname(old) + ".md")
            if not os.path.exists(dst):
                os.rename(src, dst)
                report(f"news: renamed month note {old} to {mname(old)}")
        if olds:
            for f in os.listdir(monthly):
                if f.endswith(".md"):
                    fp = os.path.join(monthly, f)
                    text = _read(fp)
                    new_text = re.sub(r"\[\[(\d{4}-\d{2})\]\]", lambda m: f"[[{mname(m.group(1))}]]", text or "")
                    if text and new_text != text:
                        _write(fp, new_text)
    for i, mon in enumerate(months):
        y, mo = map(int, mon.split("-"))
        last = (datetime.date(y + (mo == 12), mo % 12 + 1, 1) - datetime.timedelta(days=1))
        if (today - last).days < SETTLE_DAYS:
            continue                                       # still this month, or its last week isn't reviewed yet
        os.makedirs(monthly, exist_ok=True)
        note = os.path.join(monthly, mname(mon) + ".md")
        mweeks = [w for w in weeks if _week_month(w) == mon]
        mdays = [d for d in order if d.strftime("%Y-%m") == mon]
        if not os.path.exists(note) and (mweeks or mdays):
            takes = [(names[w], _week_take(_read(os.path.join(weekly, names[w] + ".md")))) for w in mweeks]
            summary = ""
            if chat and model and any(t for _, t in takes):
                try:
                    raw = chat(model, "Write a plain, neutral 5-sentence summary of this month in world news, using ONLY "
                                      "these weekly summaries. Reply ONLY with JSON: {\"summary\": \"...\"}\n\n" +
                               "\n".join(f"- {w}: {t}" for w, t in takes if t), max_tokens=450, timeout=200,
                               json_mode=True, temperature=0.3)
                    summary = (json.loads(raw).get("summary") or "").strip()
                except Exception:
                    summary = ""
            name = datetime.date(y, mo, 1).strftime("%B %Y")
            prev_mon = months[i - 1] if i else None
            out = ["---", f"month: {mon}", "tags: [archie-world, monthly-review]", "---", "",
                   f"# World · {name}", ""]
            if prev_mon:
                out += [f"← [[{mname(prev_mon)}]]", ""]
            if summary:
                out += ["## The month", summary, ""]
            if takes:
                out += ["## Weeks", ""]
                out += [f"- [[{w}]]" + (f": {t}" if t else "") for w, t in takes]
                out.append("")
                charts = [names[w] for w in mweeks if os.path.exists(os.path.join(weekly, f"{names[w]} fighting.png"))]
                if charts:
                    out += ["## Fighting by region (end of the month)", "", f"![[{charts[-1]} fighting.png]]", ""]
            if mdays:
                out += ["## Days", f"{len(mdays)} daily notes, kept in Archie/World/Archive/{mon}.", "",
                        " · ".join(f"[[{d.isoformat()}|{d.day}]]" for d in mdays), ""]
            _write(note, "\n".join(out))
            done["months"].append(mon)
            report(f"news: wrote the month note for {name}")
        # its days and weeks leave the #archie-world hub (the month note is the one link to it), and a week's
        # links to days of another month become plain dates, so each month is its own cluster in the graph
        for d in mdays:
            if _untag(days[d]):
                done.setdefault("untagged", 0)
                done["untagged"] = done["untagged"] + 1
        for w in mweeks:
            wp = os.path.join(weekly, names[w] + ".md")
            _untag(wp)
            text = _read(wp)
            if text:
                new_text = re.sub(r"\[\[(\d{4}-\d{2})-(\d{2})(\|[^\]]*)?\]\]",
                                  lambda m: m.group(0) if m.group(1) == mon else f"{m.group(1)}-{m.group(2)}", text)
                if new_text != text:
                    _write(wp, new_text)
        # the month's days into the archive (links keep working: Obsidian finds notes by name)
        dest = os.path.join(archive, mon)
        for d in mdays:
            src = days[d]
            if os.path.dirname(src) == dest:
                continue
            os.makedirs(dest, exist_ok=True)
            target = os.path.join(dest, os.path.basename(src))
            if os.path.exists(target):
                continue
            shutil.move(src, target)
            days[d] = target
            done["archived"] += 1
    # a new month note links the one after it, once that exists (month <- month in both directions isn't needed:
    # each month points back, which is enough for the chain)
    return done
