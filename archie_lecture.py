"""
archie_lecture.py - class capture: lecture recordings turned into Plaud-style notes.

Record a class with Obsidian's audio recorder on your phone (or drop the recording into a
"Lectures" folder). When it syncs to the PC, Archie types it out with timestamps and writes
a lecture note in Obsidian under Lectures/<class>/:

    summary · key points (with times) · notes by topic · terms · to-dos and due dates ·
    questions to review · a mind map · the full transcript (folded)

A recording counts as a lecture when it was made during a class on your calendar
("class: intro to animation mondays 6pm"), when it's in a folder called Lectures, or when
it's longer than 30 minutes.

It can also wake the PC after each class (a Windows scheduled task with "wake to run"),
so the note is waiting when you get home, and put it back to sleep afterwards.
"""

import datetime
import json
import os
import re
import subprocess
import sys
from xml.sax.saxutils import escape

LONG_ENOUGH = 30 * 60          # recordings longer than this count as lectures
CHUNK_CHARS = 9000             # about 20 minutes of talking per pass
WAKE_DELAYS = (20, 50)         # minutes after class ends: first try, then a second chance
TASK_PREFIX = "Archie Lecture Wake"


# ----- which class is it? ---------------------------------------------------------

def recording_start(path, duration=0.0):
    """When the recording started. Obsidian names them 'Recording 20260930141502.webm'."""
    m = re.search(r"(20\d{2})(\d{2})(\d{2})[ _-]?(\d{2})(\d{2})(\d{2})", os.path.basename(path))
    if m:
        try:
            return datetime.datetime(*map(int, m.groups()))
        except ValueError:
            pass
    try:
        return datetime.datetime.fromtimestamp(os.path.getmtime(path) - (duration or 0))
    except OSError:
        return datetime.datetime.now()


def class_for(start, calendar, minutes=75):
    """The class on the calendar that this recording fits, or None."""
    try:
        events = calendar.on(start.date())
    except Exception:
        return None
    best = None
    for e in events:
        if e.get("kind") not in ("class", "lab") or not e.get("time"):
            continue
        h, m = map(int, e["time"].split(":"))
        t0 = datetime.datetime.combine(start.date(), datetime.time(h, m))
        if t0 - datetime.timedelta(minutes=20) <= start <= t0 + datetime.timedelta(minutes=minutes):
            gap = abs((start - t0).total_seconds())
            if best is None or gap < best[0]:
                best = (gap, e["title"])
    return best[1] if best else None


def in_lectures_folder(path):
    parts = [p.lower() for p in re.split(r"[\\/]", os.path.dirname(path))]
    return "lectures" in parts or "lecture inbox" in parts


def folder_class(path):
    """Lectures/<Class name>/recording.m4a -> 'Class name'."""
    parts = re.split(r"[\\/]", os.path.dirname(path))
    low = [p.lower() for p in parts]
    if "lectures" in low:
        i = low.index("lectures")
        if i + 1 < len(parts) and parts[i + 1].lower() not in ("inbox", "lecture inbox"):
            return parts[i + 1]
    return None


# ----- turning the transcript into notes ---------------------------------------------

def clock(secs):
    secs = int(max(0, secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def paragraphs(timed, gap=2.0, every=75.0):
    """[(start, end, text)] segments -> [(start, text)] paragraphs: a new one after a pause
    or about every minute, so each paragraph has a useful timestamp."""
    out, cur, t0, last = [], [], None, 0.0
    for start, end, text in timed:
        text = text.strip()
        if not text:
            continue
        if cur and (start - last > gap or start - t0 > every):
            out.append((t0, " ".join(cur)))
            cur = []
        if not cur:
            t0 = start
        cur.append(text)
        last = end
    if cur:
        out.append((t0, " ".join(cur)))
    return out


CHUNK_PROMPT = """You are making study notes from a college lecture{klass}. This is part {i} of {n} of the transcript
(typed out from speech, so expect small mistakes). Each paragraph starts with its time [mm:ss].

Return JSON only, using what the lecturer actually said (no outside facts):
{{"topics": [{{"title": "short topic name", "at": "mm:ss when it starts", "notes": ["3 to 6 short bullet notes"]}}],
 "key_points": [{{"point": "one important idea, one sentence", "at": "mm:ss"}}],
 "terms": [{{"term": "a word or concept that was defined or stressed", "meaning": "what it means, as explained"}}],
 "todos": [{{"task": "homework, reading, assignment, exam prep the lecturer mentioned, starting with a verb", "when": "the due day as said, like 'friday' or 'oct 12', or ''"}}],
 "questions": ["a question a student should be able to answer after this part"]}}
Keep it tight: 1 to 4 topics, up to 5 key points, only real terms, only to-dos that were actually assigned.

Transcript part {i}:
\"\"\"{text}\"\"\""""

FINAL_PROMPT = """These are notes from a college lecture{klass}, gathered part by part:
{outline}

Return JSON only:
{{"title": "a short, specific title for this lecture (max 8 words, no class name)",
 "summary": "3 to 5 sentences: what the lecture covered and why it matters, plain and clear",
 "key_points": [{{"point": "...", "at": "mm:ss"}}],
 "mindmap": [{{"branch": "main idea (2 to 5 words)", "leaves": ["2 to 5 words", "..."]}}],
 "questions": ["..."]}}
Pick the 5 to 7 most important key points (keep their times), 3 to 6 mind map branches with 2 to 4 leaves each,
and the 4 to 6 best review questions."""


def _json(raw):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        m = re.search(r"\{.*\}", raw or "", re.S)
        try:
            return json.loads(m.group(0)) if m else {}
        except ValueError:
            return {}


def _chunks(paras, size=CHUNK_CHARS):
    out, buf, n = [], [], 0
    for t, text in paras:
        line = f"[{clock(t)}] {text}"
        if buf and n + len(line) > size:
            out.append("\n".join(buf))
            buf, n = [], 0
        buf.append(line)
        n += len(line) + 1
    if buf:
        out.append("\n".join(buf))
    return out


def build(chat, model, paras, klass=None, progress=lambda f, what: None, wait=lambda: None):
    """chat(model, prompt, **kw) -> str. Returns the note's pieces as a dict."""
    kl = f" ({klass})" if klass else ""
    parts = _chunks(paras) or [""]
    topics, points, terms, todos, questions = [], [], [], [], []
    for i, text in enumerate(parts, 1):
        wait()
        progress((i - 1) / (len(parts) + 1), f"sorting part {i} of {len(parts)}")
        d = _json(chat(model, CHUNK_PROMPT.format(klass=kl, i=i, n=len(parts), text=text),
                       max_tokens=1400, timeout=600, json_mode=True, temperature=0.2, num_ctx=8192))
        for t in d.get("topics") or []:
            if isinstance(t, dict) and str(t.get("title", "")).strip():
                topics.append({"title": str(t["title"]).strip(), "at": str(t.get("at", "")).strip(),
                               "notes": [str(x).strip() for x in t.get("notes") or [] if str(x).strip()][:8]})
        for k in d.get("key_points") or []:
            if isinstance(k, dict) and str(k.get("point", "")).strip():
                points.append({"point": str(k["point"]).strip(), "at": str(k.get("at", "")).strip()})
        seen = {x["term"].lower() for x in terms}
        for k in d.get("terms") or []:
            if isinstance(k, dict) and str(k.get("term", "")).strip() and k["term"].strip().lower() not in seen:
                terms.append({"term": str(k["term"]).strip(), "meaning": str(k.get("meaning", "")).strip()})
                seen.add(k["term"].strip().lower())
        for k in d.get("todos") or []:
            if isinstance(k, str):
                k = {"task": k, "when": ""}
            if isinstance(k, dict) and str(k.get("task", "")).strip():
                todos.append({"task": str(k["task"]).strip().rstrip("."), "when": str(k.get("when", "")).strip()})
        questions += [str(q).strip() for q in d.get("questions") or [] if str(q).strip()]
    wait()
    progress(len(parts) / (len(parts) + 1), "writing the summary and mind map")
    outline = []
    for t in topics:
        outline.append(f"- {t['title']} [{t['at']}]: " + "; ".join(t["notes"]))
    for k in points:
        outline.append(f"* key point [{k['at']}]: {k['point']}")
    fin = _json(chat(model, FINAL_PROMPT.format(klass=kl, outline="\n".join(outline)[:12000]),
                     max_tokens=1200, timeout=600, json_mode=True, temperature=0.3, num_ctx=8192))
    final_points = [{"point": str(k.get("point", "")).strip(), "at": str(k.get("at", "")).strip()}
                    for k in fin.get("key_points") or [] if isinstance(k, dict) and str(k.get("point", "")).strip()]
    mind = []
    for b in fin.get("mindmap") or []:
        if isinstance(b, dict) and str(b.get("branch", "")).strip():
            mind.append({"branch": str(b["branch"]).strip(),
                         "leaves": [str(x).strip() for x in b.get("leaves") or [] if str(x).strip()][:5]})
    if not mind:
        mind = [{"branch": t["title"], "leaves": [n[:40] for n in t["notes"][:3]]} for t in topics[:6]]
    progress(1.0, "done")
    return {"title": str(fin.get("title", "")).strip().strip('"') or (topics[0]["title"] if topics else "Lecture"),
            "summary": str(fin.get("summary", "")).strip(),
            "key_points": final_points or points[:7],
            "topics": topics, "terms": terms, "todos": todos,
            "questions": [str(q).strip() for q in fin.get("questions") or [] if str(q).strip()] or questions[:6],
            "mindmap": mind}


def resolve_todos(todos, lecture_date, find_date):
    """Turn 'friday' / 'oct 12' into dates, counted from the day of the lecture."""
    out = []
    for t in todos:
        due = None
        if t.get("when"):
            try:
                d = find_date(t["when"], lecture_date)
                d = d[0] if isinstance(d, tuple) else d
                if isinstance(d, datetime.date) and d >= lecture_date:
                    due = d
            except Exception:
                due = None
        out.append({"task": t["task"][0].upper() + t["task"][1:], "due": due})
    return out


def _mm(text):
    """Text that's safe inside a Mermaid mind map node."""
    t = re.sub(r"[()\[\]{}\"`<>#;:|]", " ", str(text))
    return re.sub(r"\s+", " ", t).strip()[:60] or "..."


def _at(t):
    t = (t or "").strip().strip("[]")
    return f" `{t}`" if re.match(r"^\d{1,2}:\d{2}(:\d{2})?$", t) else ""


def mindmap_file(data, todos, klass=None):
    """The mind map as a note for the Obsidian "Mindmap" plugin (by YunXiaoYi): it opens as an
    editable map you can drag, add to and collapse."""
    kids = []
    for b in data.get("mindmap") or []:
        kids.append({"name": b["branch"], "children": [{"name": l} for l in b["leaves"]]})
    if data.get("terms"):
        kids.append({"name": "Terms", "children": [{"name": t["term"]} for t in data["terms"][:6]]})
    if todos:
        kids.append({"name": "To-dos", "children": [
            {"name": t["task"] + (f" (due {t['due']:%b %d})".replace(" 0", " ") if t.get("due") else "")}
            for t in todos[:6]]})
    root = {"name": data["title"] + (f" · {klass}" if klass else ""), "children": kids}
    return ("---\ntype: mindmap-plugin\ntags:\n  - mindmap\n  - lecture\n---\n\n<%%\n\n%%>\n\n```json\n"
            + json.dumps(root, ensure_ascii=False) + "\n```\n")


def note_markdown(data, *, klass, start, duration, audio_name, audio_in_vault, paras, todos, audio_path="",
                  mindmap_note=None):
    day = start.strftime("%a %b %d, %Y").replace(" 0", " ")
    lines = ["---", "tags: [lecture" + (", " + re.sub(r"[^a-z0-9]+", "-", klass.lower()).strip("-") if klass else "") + "]"]
    if klass:
        lines.append(f"class: \"{klass}\"")
    lines += [f"date: {start:%Y-%m-%d}", f"time: \"{start:%H:%M}\"", f"duration: \"{clock(duration)}\"",
              f"source: \"[[{audio_name}]]\"" if audio_in_vault else f"source: \"{audio_path}\"", "---", "",
              f"# {data['title']}", "",
              f"> [!abstract] {klass + ' · ' if klass else ''}{day} · {start:%I:%M %p}".replace(" 0", " ")
              + f" · {clock(duration)}",
              "> Recorded on your phone, typed out and sorted on your PC by Archie.", ""]
    lines += [f"![[{audio_name}]]" if audio_in_vault else f"*Recording: {audio_path}*", ""]
    if data.get("summary"):
        lines += ["## Summary", "", data["summary"], ""]
    if data.get("key_points"):
        lines += ["## Key points", ""]
        lines += [f"- {k['point']}{_at(k['at'])}" for k in data["key_points"]]
        lines.append("")
    if data.get("topics"):
        lines += ["## Notes", ""]
        for i, t in enumerate(data["topics"], 1):
            lines += [f"### {i}. {t['title']}{_at(t['at'])}", ""]
            lines += [f"- {n}" for n in t["notes"]]
            lines.append("")
    if data.get("terms"):
        lines += ["## Terms", "", "| Term | Meaning |", "|---|---|"]
        lines += [f"| **{t['term'].replace('|', '/')}** | {t['meaning'].replace('|', '/')} |" for t in data["terms"]]
        lines.append("")
    lines += ["## To-dos", ""]
    if todos:
        for t in todos:
            lines.append(f"- [ ] {t['task']}" + (f" 📅 {t['due'].isoformat()}" if t.get("due") else ""))
    else:
        lines.append("- nothing was assigned")
    lines.append("")
    if data.get("questions"):
        lines += ["## Questions to review", ""]
        lines += [f"{i}. {q}" for i, q in enumerate(data["questions"], 1)]
        lines.append("")
    if mindmap_note:
        lines += ["## Mind map", "", f"Open it as a mind map you can edit: [[{mindmap_note}|{data['title']} · mind map]]", ""]
    if data.get("mindmap"):
        if not mindmap_note:
            lines += ["## Mind map", ""]
        lines += ["```mermaid", "mindmap", f"  root(({_mm(data['title'])}))"]
        for b in data["mindmap"]:
            lines.append(f"    {_mm(b['branch'])}")
            lines += [f"      {_mm(l)}" for l in b["leaves"]]
        lines += ["```", ""]
    lines += ["## Transcript", "", "> [!quote]- Full transcript (click to open)"]
    if paras:
        for t, text in paras:
            lines += [f"> **{clock(t)}**  {text}", ">"]
        lines.pop()
    else:
        lines.append("> *(no words heard)*")
    return "\n".join(lines) + "\n"


def note_path(base, klass, start, title):
    safe = lambda s: re.sub(r'[<>:"/\\|?*#^\[\]]', " ", s).strip() or "Lecture"
    folder = os.path.join(base, "Lectures", safe(klass) if klass else "Other")
    os.makedirs(folder, exist_ok=True)
    stem = f"{start:%Y-%m-%d} {safe(title)[:70]}"
    out, n = os.path.join(folder, stem + ".md"), 2
    while os.path.exists(out):
        out = os.path.join(folder, f"{stem} ({n}).md")
        n += 1
    return out


# ----- waking the PC after class ------------------------------------------------------

DAY_TAGS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def wake_plan(calendar, minutes=75, today=None):
    """[(class title, weekday 0-6, [datetime.time, ...])] for each weekly class on the calendar."""
    today = today or datetime.date.today()
    out = []
    for e in calendar.load():
        if e.get("kind") not in ("class", "lab") or e.get("repeat") != "weekly" or not e.get("time"):
            continue
        if e.get("until"):
            try:
                if datetime.date.fromisoformat(e["until"]) < today:
                    continue
            except ValueError:
                pass
        h, m = map(int, e["time"].split(":"))
        wd = datetime.date.fromisoformat(e["date"]).weekday()
        end = datetime.datetime.combine(today, datetime.time(h, m)) + datetime.timedelta(minutes=minutes)
        times = [(end + datetime.timedelta(minutes=d)).time() for d in WAKE_DELAYS]
        out.append((e["title"], wd, times, e["id"]))
    return out


def task_xml(klass, weekday, times, command, arguments, workdir, start_date=None):
    start_date = start_date or datetime.date.today()
    trig = []
    for t in times:
        trig.append(f"""    <CalendarTrigger>
      <StartBoundary>{start_date.isoformat()}T{t.strftime('%H:%M')}:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek><DaysOfWeek><{DAY_TAGS[weekday]} /></DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>
    </CalendarTrigger>""")
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>{escape(f"Archie: wakes the PC after {klass} so the lecture recording is typed up and sorted by the time you get home. Turn off in Archie: right-click the owl > Lectures.")}</Description>
  </RegistrationInfo>
  <Triggers>
{chr(10).join(trig)}
  </Triggers>
  <Principals>
    <Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>false</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(command)}</Command>
      <Arguments>{escape(arguments)}</Arguments>
      <WorkingDirectory>{escape(workdir)}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _run(args):
    flags = 0x08000000 if sys.platform == "win32" else 0     # CREATE_NO_WINDOW
    r = subprocess.run(args, capture_output=True, text=True, creationflags=flags, timeout=30)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def set_wake_tasks(plan, command, arguments, workdir, state_path, tmp_dir):
    """Replace Archie's wake tasks with one per weekly class. Returns (made, problems)."""
    if sys.platform != "win32":
        return 0, ["waking the PC only works on Windows"]
    clear_wake_tasks(state_path)
    made, problems, names = 0, [], []
    for i, (klass, wd, times, _id) in enumerate(plan, 1):
        name = f"{TASK_PREFIX} {i} - {re.sub(r'[^A-Za-z0-9 ]+', '', klass)[:40]} {DAY_TAGS[wd][:3]}"
        xml_path = os.path.join(tmp_dir, f"lecture_wake_{i}.xml")
        with open(xml_path, "w", encoding="utf-16") as f:
            f.write(task_xml(klass, wd, times, command, arguments, workdir))
        code, out = _run(["schtasks", "/create", "/tn", name, "/xml", xml_path, "/f"])
        try:
            os.remove(xml_path)
        except OSError:
            pass
        if code == 0:
            made += 1
            names.append(name)
        else:
            problems.append(f"{klass}: {out.strip()[:200]}")
    try:
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({"tasks": names}, f)
    except OSError:
        pass
    return made, problems


def clear_wake_tasks(state_path):
    try:
        with open(state_path, encoding="utf-8") as f:
            names = json.load(f).get("tasks", [])
    except (OSError, ValueError):
        names = []
    for n in names:
        if sys.platform == "win32":
            try:
                _run(["schtasks", "/delete", "/tn", n, "/f"])
            except Exception:
                pass
    try:
        os.remove(state_path)
    except OSError:
        pass


def idle_seconds():
    """Seconds since the last keyboard or mouse input (Windows), else 0."""
    if sys.platform != "win32":
        return 0
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    li = LASTINPUTINFO()
    li.cbSize = ctypes.sizeof(li)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
        return 0
    return max(0, (ctypes.windll.kernel32.GetTickCount() - li.dwTime) & 0xFFFFFFFF) / 1000.0


def sleep_pc():
    """Put the PC back to sleep (not hibernate, not shut down)."""
    if sys.platform != "win32":
        return False
    import ctypes
    return bool(ctypes.windll.powrprof.SetSuspendState(False, False, False))


def obsidian_running():
    if sys.platform != "win32":
        return True
    try:
        code, out = _run(["tasklist", "/fi", "imagename eq Obsidian.exe", "/nh"])
        return "obsidian.exe" in out.lower()
    except Exception:
        return True
