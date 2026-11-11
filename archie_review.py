"""
archie_review.py - the lecture review: your recording lined up with what the professor gives you.

Put the professor's material for a class in your vault under  Lectures\\<class>\\Materials\\
(or share/drop it from the phone or laptop with the class picked: Archie files it there for you):

    slides (.pptx, or PDF exports), PDFs, handouts (.docx, .txt, .md), photos or scans of pages,
    and the professor's own recordings.

Archie reads each one (once; scanned pages and photos are read by the vision model), works out which
lecture it belongs to, and writes a review note next to that lecture's notes:

    <date> <lecture title> (review).md

    * flagged in class ("this will be on the exam", assignments): quoted, with the time
    * said in class but not in the material (examples, explanations, hints)
    * the lecture slide by slide: each slide, what was actually said about it, your marks and board photos
    * in the material but never mentioned in class
    * every file used and how Archie matched it

Every point says where it came from: 🎙 said in class (time in your recording), 📑 the professor's file,
📼 the professor's recording, 📷 your board photo, ⭐ your mark. It rebuilds by itself when new material
for that lecture arrives (slides posted a few days late are fine).

Which lecture a file belongs to:
  1. a date in its name or folder (2026-11-09, 11-09, Nov 9) that matches a lecture's date, else
  2. what's in it: the lecture where most of its key words were actually said, else
  3. the lecture closest to when the file arrived (within a week).
Files that arrive before the lecture wait for it. Their words also help Whisper spell the class's terms.

Nothing here goes online: it uses the models Archie already runs on this PC.
"""

import datetime
import hashlib
import json
import math
import os
import re
import threading
import time
import zipfile
from xml.etree import ElementTree as ET

VERSION = 2
SUFFIX = " (review).md"
SUFFIX_KEPT = " (review, rebuilt).md"
MATERIALS = "materials"
DOC_EXT = {".pdf", ".pptx", ".docx", ".txt", ".md", ".rtf"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".heic", ".heif"}
AUDIO_EXT = {".mp3", ".mp4", ".m4a", ".m4b", ".m4v", ".mkv", ".mka", ".aac", ".ogg", ".oga", ".opus", ".webm",
             ".wav", ".flac", ".wma", ".3gp", ".amr"}
OLD_EXT = {".ppt", ".doc", ".key", ".odp", ".pages"}           # can't be read: say so, ask for an export
GROUP_CHARS = 7000            # material + transcript per model call
MATCH = 0.2                   # share of a slide's key words heard in a stretch of the lecture to count as covered
BOARD = re.compile(r"Board \(?(20\d{12}|20\d{2}-\d{2}-\d{2} \d{1,2}\.\d{2}(?:\.\d{2})? ?[AP]M)", re.I)


def board_time(fn):
    """When a board photo was taken, from its name: 'Board 20261109140300' or 'Board (2026-11-09 2.03 PM)'."""
    m = BOARD.search(fn or "")
    if not m:
        return None
    t = m.group(1)
    if re.fullmatch(r"20\d{12}", t):
        try:
            return datetime.datetime.strptime(t, "%Y%m%d%H%M%S")
        except ValueError:
            return None
    try:
        from archie_lecture import nice_time
        return nice_time("(" + t + ")")
    except Exception:
        return None
RECORDING = re.compile(r"(20\d{2})(\d{2})(\d{2})[ _-]?(\d{2})(\d{2})(\d{2})")
FLAGS = re.compile(r"\b(on the (exam|test|quiz|final|midterm)|(will|going to) be on|(exam|test|quiz|final|midterm)s? "
                   r"(will|is|are|covers?)|know this|remember this|this is important|really important|make sure you|"
                   r"due (on|by|next|this|monday|tuesday|wednesday|thursday|friday)|homework|assignment|problem set|"
                   r"read (chapter|section|pages?))\b", re.I)

STOP = set("""about above after again against all also although always among and another any anyone anything are
around because been before being below between both but can cannot could did does doing done down during each
either else even ever every few for from further get gets getting give given goes going gone got had has have
having here hers herself him himself his how however into its itself just keep kind know known let like likely
look made make makes making many may maybe mean means might more most much must myself need needs never next
not now off once one ones only onto other others our ours out over own part really right said same say says see
seen she should show shown since some something sort still such sure take taken than that thats the their theirs
them themselves then there therefore these they thing things think this those though through thus too two under
until upon use used uses using very want was way ways well were what whatever when where whether which while who
whom whose why will with within without would yeah yes yet you your yours yourself okay alright gonna wanna kinda
actually basically probably pretty lot lots little bit today guys everybody somebody question questions slide
slides page pages example examples figure chapter section lecture class week time first second third last
""".split())


# ----- small helpers ---------------------------------------------------------------------------------

def clock(secs):
    secs = int(max(0, secs or 0))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def secs(t):
    """'12:34' / '1:02:03' / '[12:34]' -> seconds, or None."""
    m = re.match(r"^\[?(\d{1,2}):(\d{2})(?::(\d{2}))?\]?$", str(t or "").strip())
    if not m:
        return None
    a, b, c = m.groups()
    return int(a) * 3600 + int(b) * 60 + int(c) if c else int(a) * 60 + int(b)


def _stem(w):
    for suf in ("ations", "ation", "ings", "ing", "ies", "ed", "es", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def words(text):
    return [_stem(w) for w in re.findall(r"[a-z][a-z0-9\-]{3,}", (text or "").lower()) if w not in STOP]


def _json(raw):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        m = re.search(r"\{.*\}", raw or "", re.S)
        try:
            return json.loads(m.group(0)) if m else {}
        except ValueError:
            return {}


def _safe(s, fallback="note"):
    return re.sub(r'[<>:"/\\|?*#^\[\]]', " ", str(s or "")).strip() or fallback


def _one_line(s, n=400):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


# ----- reading the professor's material --------------------------------------------------------------

def _pptx(path):
    """[(slide number, title, text, speaker notes)] straight from the file, no extra installs."""
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/main}t"
    out = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        order = []
        try:                                          # the real slide order lives in presentation.xml + its rels
            rels = ET.fromstring(z.read("ppt/_rels/presentation.xml.rels"))
            target = {r.get("Id"): r.get("Target") for r in rels}
            pres = ET.fromstring(z.read("ppt/presentation.xml"))
            for sid in pres.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sldId"):
                rid = sid.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
                t = target.get(rid, "")
                if t:
                    order.append("ppt/" + t.lstrip("/").replace("../", "") if not t.startswith("ppt/") else t)
        except Exception:
            order = []
        if not order:
            order = sorted((n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                           key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
        for i, name in enumerate(order, 1):
            if name not in names:
                continue
            root = ET.fromstring(z.read(name))
            paras, title = [], ""
            for sp in root.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sp"):
                ph = sp.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}ph")
                is_title = ph is not None and (ph.get("type") or "") in ("title", "ctrTitle")
                for p in sp.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}p"):
                    line = "".join(t.text or "" for t in p.iter(ns)).strip()
                    if not line:
                        continue
                    if is_title and not title:
                        title = line
                    else:
                        paras.append(line)
            notes = ""
            rel = name.replace("slides/", "slides/_rels/") + ".rels"
            if rel in names:
                try:
                    for r in ET.fromstring(z.read(rel)):
                        if (r.get("Type") or "").endswith("/notesSlide"):
                            np_ = "ppt/" + r.get("Target").replace("../", "")
                            if np_ in names:
                                nroot = ET.fromstring(z.read(np_))
                                bits = []
                                for sp in nroot.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sp"):
                                    ph = sp.find(".//{http://schemas.openxmlformats.org/presentationml/2006/main}ph")
                                    if ph is not None and ph.get("type") == "body":
                                        bits += ["".join(t.text or "" for t in p.iter(ns)).strip()
                                                 for p in sp.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}p")]
                                notes = " ".join(b for b in bits if b)
                except Exception:
                    notes = ""
            if not title and paras:
                title = paras.pop(0)
            out.append((i, title, "\n".join(paras), notes))
    return out


def _pdf_pages(path):
    """[(page number, text, [image bytes] when the page has no text)]"""
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader                    # noqa: older install
    reader = PdfReader(path)
    out = []
    for i, page in enumerate(reader.pages, 1):
        try:
            t = (page.extract_text() or "").strip()
        except Exception:
            t = ""
        imgs = []
        if len(t) < 25:
            try:
                ims = sorted(page.images, key=lambda im: len(im.data), reverse=True)
                imgs = [ims[0].data] if ims else []
            except Exception:
                imgs = []
        out.append((i, t, imgs))
    return out


def _sections(text, size=1400):
    """Plain text -> roughly page-sized pieces, split at headings or blank lines."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n|\n(?=#{1,4} )", text or "") if b.strip()]
    out, buf = [], ""
    for b in blocks:
        if buf and len(buf) + len(b) > size:
            out.append(buf)
            buf = ""
        buf = (buf + "\n\n" + b).strip()
    if buf:
        out.append(buf)
    return out


def _docx(path):
    import docx
    d = docx.Document(path)
    lines = []
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            lines.append("")
            continue
        style = (getattr(p.style, "name", "") or "").lower()
        lines.append(("## " + t) if style.startswith("heading") or style == "title" else t)
    for table in d.tables:
        for row in table.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(lines)


def _title_of(text):
    for line in (text or "").splitlines():
        line = line.strip("#* \t")
        if 3 <= len(line) <= 90:
            return line
    return ""


def read_material(path, vision=None, transcribe=None):
    """-> {"kind": "slides"|"pdf"|"doc"|"image"|"audio"|"unreadable", "units": [...], "read": "what was read"}
    unit = {"n": number, "label": "Slide 4", "title": "...", "text": "...", "at": seconds (audio only)}"""
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext in OLD_EXT:
        return {"kind": "unreadable", "units": [],
                "read": f"can't read {ext} files: save it as {'.pptx or PDF' if ext in ('.ppt', '.key', '.odp') else '.docx or PDF'}"}
    if ext == ".pptx":
        units = []
        for n, title, body, notes in _pptx(path):
            text = body + (f"\n(speaker notes) {notes}" if notes else "")
            units.append({"n": n, "label": f"Slide {n}", "title": title, "text": text.strip()})
        return {"kind": "slides", "units": units, "read": f"{len(units)} slide{'s' if len(units) != 1 else ''}"}
    if ext == ".pdf":
        units, scanned = [], 0
        for n, text, imgs in _pdf_pages(path):
            if len(text) < 25 and imgs and vision:
                try:
                    text = vision(imgs[0], "page") or text
                    scanned += 1
                except Exception:
                    pass
            units.append({"n": n, "label": f"p.{n}", "title": _title_of(text), "text": text})
        kind = "slides" if units and sum(len(u["text"]) for u in units) / len(units) < 900 else "pdf"
        read = f"{len(units)} page{'s' if len(units) != 1 else ''}" + (f" ({scanned} scanned, read by the vision model)" if scanned else "")
        return {"kind": kind, "units": units, "read": read}
    if ext in (".docx", ".txt", ".md", ".rtf"):
        if ext == ".docx":
            text = _docx(path)
        else:
            with open(path, "rb") as f:
                raw = f.read(2_000_000)
            text = ""
            for enc in ("utf-8-sig", "cp1252", "latin-1"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            if ext == ".rtf":
                text = re.sub(r"\\[a-z]+-?\d* ?|[{}]", "", text)
            if ext == ".md":
                text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
        secs_ = _sections(text)
        units = [{"n": i, "label": f"part {i}", "title": _title_of(s), "text": s} for i, s in enumerate(secs_, 1)]
        return {"kind": "doc", "units": units, "read": f"{len(units)} part{'s' if len(units) != 1 else ''}"}
    if ext in IMAGE_EXT:
        if not vision:
            return {"kind": "unreadable", "units": [], "read": "no vision model to read pictures"}
        with open(path, "rb") as f:
            data = f.read()
        text = vision(data, "page") or ""
        return {"kind": "image", "units": [{"n": 1, "label": "picture", "title": _title_of(text), "text": text}],
                "read": "picture, read by the vision model"}
    if ext in AUDIO_EXT:
        if not transcribe:
            return {"kind": "unreadable", "units": [], "read": "Whisper isn't available"}
        timed = transcribe(path)
        units, buf, t0 = [], [], None
        for start, end, text in timed:
            if t0 is None:
                t0 = start
            buf.append(text.strip())
            if end - t0 >= 120:
                units.append({"n": len(units) + 1, "label": clock(t0), "title": "", "text": " ".join(buf), "at": t0})
                buf, t0 = [], None
        if buf:
            units.append({"n": len(units) + 1, "label": clock(t0), "title": "", "text": " ".join(buf), "at": t0})
        dur = timed[-1][1] if timed else 0
        return {"kind": "audio", "units": units, "read": f"recording, {clock(dur)} typed out by Whisper"}
    return {"kind": "unreadable", "units": [], "read": f"can't read {ext or 'this'} files"}


# ----- one lecture, recorded on more than one device ------------------------------------------------------

def stitch(sources):
    """Recordings of the same lecture (phone and laptop; one may have died halfway) -> one transcript with no
    part twice. Each is placed on the clock by when it started; where they overlap, the stretch comes from the
    one that heard more words there, and nothing said before the hand-off is repeated after it.
    sources: [{"audio", "start": epoch seconds, "dur": seconds, "segs": [[start, end, text], ...]}]
             (older ones may have "paras": [[t, text], ...] instead)
    -> (t0, [(start, end, text)] relative to t0, [(audio, offset, used_from, used_to)] in seconds from t0)"""
    srcs = []
    for s in sources:
        segs = s.get("segs") or [[t, t + 60, x] for t, x in (s.get("paras") or [])]
        if segs:
            srcs.append((s, [(float(a), float(b), str(x)) for a, b, x in segs]))
    if not srcs:
        return (min((s["start"] for s in sources), default=0), [], [])
    ends = {id(s): s["start"] + max(float(s.get("dur") or 0), segs[-1][1]) for s, segs in srcs}
    t0 = min(s["start"] for s, _ in srcs)
    cuts = sorted({s["start"] for s, _ in srcs} | set(ends.values()))
    picked, used = [], {}
    for a, b in zip(cuts, cuts[1:]):
        here = [(s, segs) for s, segs in srcs if s["start"] <= a and ends[id(s)] >= b]
        if not here:
            continue
        s, segs = max(here, key=lambda sg: (sum(len(x.split()) for st, en, x in sg[1] if a <= sg[0]["start"] + st < b),
                                            -sg[0]["start"]))
        for st, en, x in segs:
            if a <= s["start"] + st < b:
                picked.append((s["start"] + st - t0, s["start"] + en - t0, x, s["audio"]))
        u = used.setdefault(s["audio"], [s["start"] - t0, a - t0, b - t0])
        u[1], u[2] = min(u[1], a - t0), max(u[2], b - t0)
    picked.sort()
    out, last_end, last_src = [], -1e9, None
    for st, en, x, aud in picked:
        if aud != last_src and st < last_end - 0.5:
            continue                            # the other device already had this sentence
        out.append((round(st, 2), round(en, 2), x))
        last_end, last_src = max(last_end, en), aud
    spans = sorted(((aud, off, f, to) for aud, (off, f, to) in used.items()), key=lambda x: x[2])
    return t0, out, spans


# ----- the lectures Archie already wrote --------------------------------------------------------------

def read_lecture(path):
    """A lecture note written by archie_lecture -> dict, or None if it isn't one."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m or "## Transcript" not in text:
        return None
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip().strip('"')
    if not fm.get("tags", "").startswith("[lecture") or fm.get("type") == "lecture-review":
        return None
    try:
        day = datetime.date.fromisoformat(fm.get("date", "")[:10])
    except ValueError:
        return None
    try:
        hh, mm = map(int, (fm.get("time") or "00:00").split(":")[:2])
    except ValueError:
        hh, mm = 0, 0
    start = datetime.datetime.combine(day, datetime.time(hh, mm))
    src = re.search(r"\[\[([^\]|]+)", fm.get("source", ""))
    audio = src.group(1) if src else os.path.basename(fm.get("source", ""))
    try:
        from archie_lecture import nice_time
        nt = nice_time(audio)
    except Exception:
        nt = None
    rm = None if nt else RECORDING.search(audio or "")
    if nt:
        start = nt
    if rm:
        try:
            start = datetime.datetime(*map(int, rm.groups()))
        except ValueError:
            pass
    title = re.search(r"^# (.+)$", text, re.M)
    paras = []
    tpart = text.split("## Transcript", 1)[1]
    for t, body in re.findall(r"^> \*\*(\d{1,2}:\d{2}(?::\d{2})?)\*\*\s+(.*)$", tpart, re.M):
        paras.append((secs(t), body.strip()))
    terms = re.findall(r"^\| \*\*(.+?)\*\* \|", text, re.M)
    recs = []                                   # a stitched lecture: "a.webm@0;b.webm@2400"
    for part in (fm.get("recordings") or "").split(";"):
        if "@" in part:
            a, off = part.rsplit("@", 1)
            try:
                recs.append((a.strip(), float(off)))
            except ValueError:
                pass
    if recs:
        start = datetime.datetime.combine(day, datetime.time(hh, mm, int(fm.get("seconds") or 0)))
    return {"path": path, "klass": fm.get("class") or None, "date": day, "start": start,
            "recordings": recs or [(audio, 0.0)],
            "duration": secs(fm.get("duration")) or (paras[-1][0] + 60 if paras else 0),
            "title": title.group(1).strip() if title else os.path.splitext(os.path.basename(path))[0],
            "audio": audio, "paras": paras, "terms": terms,
            "stem": os.path.splitext(os.path.basename(path))[0]}


def lectures_in(class_dir):
    out = []
    for fn in sorted(os.listdir(class_dir)):
        if not fn.endswith(".md") or fn.endswith(SUFFIX) or fn.endswith(SUFFIX_KEPT) or fn.endswith("(mind map).md"):
            continue
        if not re.match(r"\d{4}-\d\d-\d\d ", fn):
            continue
        p = os.path.join(class_dir, fn)
        if time.time() - os.path.getmtime(p) < 20:         # still being written
            continue
        lec = read_lecture(p)
        if lec:
            out.append(lec)
    return out


def marks_for(class_dir, lec):
    """Your marks from the phone recorder for this recording: [(seconds, label)]."""
    out = []
    for fn in os.listdir(class_dir):
        if not fn.endswith(".md") or not fn.startswith(lec["date"].isoformat()):
            continue
        try:
            with open(os.path.join(class_dir, fn), encoding="utf-8", errors="replace") as f:
                text = f.read(20000)
        except OSError:
            continue
        if "## Marked moments" not in text:
            continue
        off = next((o for a, o in lec.get("recordings") or [(lec["audio"], 0.0)] if a and a in text), None)
        if off is None:
            continue
        for t, label in re.findall(r"^- \*\*(\d{1,2}:\d{2}(?::\d{2})?)\*\*\s*(.*)$", text, re.M):
            s = secs(t)
            if s is not None:
                out.append((s + off, label.strip() or "marked"))
    return sorted(set(out))


def notes_for(class_dir, lec):
    """Notes you wrote for this class on the day of the lecture (phone or laptop): [(path, title, text)]."""
    out = []
    day = lec["date"].isoformat()
    for fn in sorted(os.listdir(class_dir)):
        if not fn.endswith(".md") or not fn.startswith(day + " ") or fn.endswith(SUFFIX) or fn.endswith(SUFFIX_KEPT):
            continue
        p = os.path.join(class_dir, fn)
        if os.path.normcase(p) == os.path.normcase(lec["path"]):
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read(200_000)
        except OSError:
            continue
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m or "lecture-notes" not in m.group(1) or "## Marked moments" in text:
            continue
        body = text[m.end():]
        t = re.search(r"^# (.+)$", body, re.M)
        if t:
            body = body[t.end():]
        body = re.sub(r"^Recording: \[\[.*$", "", body, flags=re.M).strip()
        if len(words(body)) >= 4:
            out.append((p, t.group(1).strip() if t else fn[11:-3], body))
    return out


def boards_for(class_dir, lec):
    """Board photos taken during this lecture: [(seconds into the recording, path)]."""
    out = []
    for sub in ("Files", ""):
        d = os.path.join(class_dir, sub) if sub else class_dir
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            at = board_time(fn)
            if not at:
                continue
            off = (at - lec["start"]).total_seconds()
            if -600 <= off <= (lec["duration"] or 0) + 900:
                out.append((max(0.0, off), os.path.join(d, fn)))
    return sorted(out)


def materials_in(class_dir):
    """Professor files for this class: everything under Materials, plus documents dropped in Files."""
    out = []
    for dp, dns, fns in os.walk(class_dir):
        rel = os.path.relpath(dp, class_dir)
        parts = [p.lower() for p in re.split(r"[\\/]", rel) if p and p != "."]
        in_mat = MATERIALS in parts
        in_files = parts[:1] == ["files"]
        if not (in_mat or in_files):
            continue
        for fn in fns:
            ext = os.path.splitext(fn)[1].lower()
            if fn.startswith((".", "~$")) or BOARD.search(fn):
                continue
            if in_mat and ext in DOC_EXT | IMAGE_EXT | AUDIO_EXT | OLD_EXT:
                out.append(os.path.join(dp, fn))
            elif in_files and ext in DOC_EXT - {".md"} | OLD_EXT:
                out.append(os.path.join(dp, fn))
    return sorted(out)


# ----- which lecture is it for? -----------------------------------------------------------------------

MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def dates_in(text, year):
    """Dates written in a file or folder name."""
    out = set()
    s = text.lower()
    for y, mo, d in re.findall(r"(20\d\d)[-_. ]?(\d\d)[-_. ]?(\d\d)", s):
        try:
            out.add(datetime.date(int(y), int(mo), int(d)))
        except ValueError:
            pass
    for mo, d in re.findall(r"(?<![\d])(\d{1,2})[-_.](\d{1,2})(?![\d])", s):
        try:
            out.add(datetime.date(year, int(mo), int(d)))
        except ValueError:
            pass
    for mo, d in re.findall(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[ _-]?(\d{1,2})\b", s):
        try:
            out.add(datetime.date(year, MONTHS[mo], int(d)))
        except ValueError:
            pass
    return out


def _weights(docs):
    """Inverse document frequency over pieces of text (words said all lecture long count less)."""
    df = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    n = max(1, len(docs))
    return {w: math.log(1 + n / c) for w, c in df.items()}


def coverage(unit_words, heard, idf):
    """Share of a piece's key words (weighted) that were heard."""
    keys = set(unit_words)
    if len(keys) < 3:
        return 0.0
    tot = sum(idf.get(w, 1.5) for w in keys)
    got = sum(idf.get(w, 1.5) for w in keys if w in heard)
    return got / tot if tot else 0.0


def assign(material_paths, cache, lectures, class_dir):
    """{material path: (lecture path, why)} for the files Archie can place."""
    out = {}
    if not lectures:
        return out
    lw = {l["path"]: set(words(" ".join(t for _, t in l["paras"]))) for l in lectures}
    idf = _weights(list(lw.values()))
    by_date = {}
    for l in lectures:
        by_date.setdefault(l["date"], []).append(l)
    for p in material_paths:
        c = cache.get(p) or {}
        if not c.get("units"):
            continue
        rel = os.path.relpath(p, class_dir)
        named = [d for d in dates_in(rel, lectures[-1]["date"].year) if d in by_date]
        if named:
            l = by_date[sorted(named)[-1]][-1]
            out[p] = (l["path"], f"date in the {'name' if len(named) == 1 else 'names'} ({sorted(named)[-1]:%b %d})".replace(" 0", " "))
            continue
        mw = words(" ".join(u["text"] + " " + u.get("title", "") for u in c["units"]))
        scores = sorted(((coverage(mw, lw[l["path"]], idf), l) for l in lectures), key=lambda x: -x[0])
        best = scores[0]
        second = scores[1][0] if len(scores) > 1 else 0.0
        if best[0] >= 0.3 and best[0] >= second * 1.2 + 0.03:
            out[p] = (best[1]["path"], f"what's in it: {int(best[0] * 100)}% of its key words were said in this lecture")
            continue
        try:
            arrived = datetime.date.fromtimestamp(os.path.getmtime(p))
        except OSError:
            continue
        near = sorted(lectures, key=lambda l: abs((l["date"] - arrived).days))
        if near and abs((near[0]["date"] - arrived).days) <= 7 and best[0] >= 0.12:
            out[p] = (near[0]["path"], f"the lecture closest to when it arrived ({arrived:%b %d})".replace(" 0", " "))
    return out


# ----- lining the material up with the transcript -------------------------------------------------------

def windows(paras, span=150.0):
    """Overlapping stretches of the lecture, about 2.5 minutes each: [(start, end, text)]."""
    out = []
    for i, (t0, _) in enumerate(paras):
        buf, j = [], i
        while j < len(paras) and (paras[j][0] - t0 <= span or not buf):
            buf.append(paras[j][1])
            j += 1
        end = paras[j][0] if j < len(paras) else t0 + span
        out.append((t0, end, " ".join(buf)))
        if j >= len(paras):
            break
    return out


def align(units, wins):
    """Match pieces (in order) to stretches of the lecture, keeping their order.
    -> [(unit index, window index, score)] for the pieces that were covered."""
    if not units or not wins:
        return []
    ww = [set(words(t)) for _, _, t in wins]
    idf = _weights(ww)
    uw = [words(u.get("title", "") + " " + u["text"]) for u in units]
    S = [[coverage(uw[u], ww[w], idf) for w in range(len(wins))] for u in range(len(units))]
    U, W = len(units), len(wins)
    NEG = -1.0
    f = [[0.0] * W for _ in range(U + 1)]
    how = [[0] * W for _ in range(U + 1)]           # 0 skip unit, 1 carry from w-1, 2 take
    for u in range(U):
        for w in range(W):
            best, h = f[u][w], 0
            if w and f[u + 1][w - 1] > best:
                best, h = f[u + 1][w - 1], 1
            if S[u][w] >= MATCH and f[u][w] + S[u][w] > best:
                best, h = f[u][w] + S[u][w], 2
            f[u + 1][w], how[u + 1][w] = best, h
    out, u, w = [], U, W - 1
    while u > 0 and w >= 0:
        h = how[u][w]
        if h == 2:
            out.append((u - 1, w, S[u - 1][w]))
            u -= 1
        elif h == 1:
            w -= 1
        else:
            u -= 1
    _ = NEG
    return sorted(out)


GROUP_PROMPT = """You are lining up a professor's material with what was actually said in a college lecture{klass}.

MATERIAL: the professor's files, and possibly the student's own notes (each piece has an id in brackets):
{material}

LECTURE TRANSCRIPT, typed out from your recording (expect small mistakes). Each paragraph starts with its time [mm:ss]:
{transcript}

Return JSON only:
{{"items": [{{"id": "M1", "said": ["what the professor said about this that goes beyond what is written: an explanation, example, warning or detail (short bullets)"], "at": "mm:ss where it was discussed"}}],
 "only_said": [{{"point": "something important said in this stretch that is NOT in the material above", "at": "mm:ss"}}],
 "fixes": [{{"heard": "a word as the transcript wrote it", "is": "the correct spelling, from the material"}}]}}
Rules: use only the transcript and the material, no outside facts. Give "said" an empty list when the professor
only read the piece out. "only_said": up to 5, real content only (examples, explanations, exam or homework hints),
never small talk. "fixes": only clear misspellings of terms that appear in the material."""

SOLO_PROMPT = """These are the important moments of a college lecture{klass}, typed out from a recording (expect small
mistakes). Each paragraph starts with its time [mm:ss]:
{transcript}

There is no professor material for this stretch. Return JSON only:
{{"only_said": [{{"point": "an important point, example or hint from this stretch", "at": "mm:ss"}}]}}
Up to 5, real content only, no outside facts."""


def _tx(paras, t0, t1):
    return "\n".join(f"[{clock(t)}] {x}" for t, x in paras if t0 <= t < t1)


def plan_groups(lec, mats, aligned):
    """Split the lecture into stretches for the model, each with the material discussed in it.
    mats: [(material path, kind, units)]; aligned: {path: [(unit index, window index, score)]}.
    -> [{"t0", "t1", "pieces": [(path, unit index, at)]}]"""
    wins = windows(lec["paras"])
    hits = []
    pw = [set(words(x)) for _, x in lec["paras"]]
    idf = _weights(pw)
    for p, kind, units in mats:
        for ui, wi, sc in aligned.get(p, []):
            t0, t1, _ = wins[wi]               # narrow the stretch down to the paragraph that matches best
            uw = words(units[ui].get("title", "") + " " + units[ui]["text"])
            best = max(((coverage(uw, pw[j], idf), -j, t) for j, (t, _) in enumerate(lec["paras"]) if t0 <= t < t1),
                       default=(0, 0, t0))
            hits.append((best[2] if best[0] > 0 else t0, p, ui))
    hits.sort()
    end = (lec["paras"][-1][0] + 60) if lec["paras"] else 0
    groups, cur = [], {"t0": 0.0, "t1": end, "pieces": []}
    size = 0
    unit_len = {}
    for p, kind, units in mats:
        for i, u in enumerate(units):
            unit_len[(p, i)] = min(1600, len(u["text"]) + len(u.get("title", "")) + 40)
    para_len = lambda a, b: sum(len(x) + 9 for t, x in lec["paras"] if a <= t < b)
    for at, p, ui in hits:
        add = unit_len[(p, ui)] + para_len(cur["pieces"][-1][2] if cur["pieces"] else cur["t0"], at)
        if cur["pieces"] and size + add > GROUP_CHARS:
            cur["t1"] = at
            groups.append(cur)
            cur, size = {"t0": at, "t1": end, "pieces": []}, 0
        cur["pieces"].append((p, ui, at))
        size += add
    groups.append(cur)
    out = []                                           # long stretches with nothing matched get split up
    for g in groups:
        span = [(t, x) for t, x in lec["paras"] if g["t0"] <= t < g["t1"]]
        mat = sum(unit_len[(p, i)] for p, i, _ in g["pieces"])
        if sum(len(x) + 9 for _, x in span) + mat <= GROUP_CHARS * 1.4 or not span:
            out.append(g)
            continue
        t0, n, pieces = g["t0"], 0, list(g["pieces"])
        budget = max(2500, GROUP_CHARS - mat)
        for t, x in span:
            n += len(x) + 9
            if n > budget:
                mine = [pc for pc in pieces if pc[2] < t]
                pieces = [pc for pc in pieces if pc[2] >= t]
                out.append({"t0": t0, "t1": t, "pieces": mine})
                t0, n = t, len(x) + 9
        out.append({"t0": t0, "t1": g["t1"], "pieces": pieces})
    return [g for g in out if any(g["t0"] <= t < g["t1"] for t, _ in lec["paras"])]


def _material_line(mid, path, unit):
    name = os.path.basename(path)
    head = f"[{mid}] {unit['label']} of {name}" + (f" · \"{unit['title']}\"" if unit.get("title") else "")
    body = unit["text"]
    if unit.get("title") and body.startswith(unit["title"]):
        body = body[len(unit["title"]):]
    return head + "\n" + _one_line(body, 1500)


def build(lec, mats, aligned, chat, model, klass=None, wait=lambda: None, progress=lambda f, w: None):
    """Ask the model about each stretch. -> {"said": {(path, i): {"bullets", "at"}}, "only": [...], "fixes": [...]}"""
    kl = f" ({klass})" if klass else ""
    groups = plan_groups(lec, mats, aligned)
    units = {p: u for p, _, u in mats}
    said, only, fixes = {}, [], []
    for gi, g in enumerate(groups, 1):
        wait()
        progress((gi - 1) / max(1, len(groups)), f"lining up part {gi} of {len(groups)}")
        tx = _tx(lec["paras"], g["t0"], g["t1"])
        if not tx.strip():
            continue
        ids = {}
        lines = []
        for k, (p, ui, at) in enumerate(g["pieces"], 1):
            mid = f"M{k}"
            ids[mid] = (p, ui, at)
            lines.append(_material_line(mid, p, units[p][ui]))
        prompt = (GROUP_PROMPT.format(klass=kl, material="\n\n".join(lines), transcript=tx) if lines
                  else SOLO_PROMPT.format(klass=kl, transcript=tx))
        try:
            d = _json(chat(model, prompt, max_tokens=1500, timeout=900, json_mode=True, temperature=0.2, num_ctx=8192))
        except Exception:
            d = {}
        lo, hi = g["t0"] - 90, g["t1"] + 90
        fix_at = lambda t, default: (secs(t) if secs(t) is not None and lo <= secs(t) <= hi else default)
        for it in d.get("items") or []:
            if not isinstance(it, dict) or str(it.get("id", "")).strip() not in ids:
                continue
            p, ui, at = ids[str(it["id"]).strip()]
            bullets = [_one_line(b, 300) for b in it.get("said") or [] if isinstance(b, str) and b.strip()][:5]
            t = secs(it.get("at"))                    # the model's time only if it's near where the content matched
            said[(p, ui)] = {"bullets": bullets, "at": t if t is not None and abs(t - at) <= 150 else at}
        for o in d.get("only_said") or []:
            if isinstance(o, dict) and str(o.get("point", "")).strip():
                only.append({"point": _one_line(o["point"], 300), "at": fix_at(o.get("at"), g["t0"])})
        mat_low = "\n".join(lines).lower()
        tx_low = tx.lower()
        for fx in d.get("fixes") or []:
            if not (isinstance(fx, dict) and fx.get("heard") and fx.get("is")):
                continue
            a, b = str(fx["heard"]).strip(), str(fx["is"]).strip()
            if a.lower() != b.lower() and a.lower() in tx_low and b.lower() in mat_low and a.lower() not in mat_low:
                fixes.append((_one_line(a, 60), _one_line(b, 60)))
        for p, ui, at in g["pieces"]:                   # covered even if the model said nothing about it
            said.setdefault((p, ui), {"bullets": [], "at": at})
    progress(1.0, "writing the review")
    seen, uniq = set(), []
    for o in sorted(only, key=lambda o: o["at"] or 0):
        k = o["point"].lower()[:60]
        if k not in seen:
            seen.add(k)
            uniq.append(o)
    fx_seen, fx = set(), []
    for a, b in fixes:
        if a.lower() not in fx_seen:
            fx_seen.add(a.lower())
            fx.append((a, b))
    return {"said": said, "only": uniq, "fixes": fx[:30]}


def flagged(paras, limit=12):
    """Moments the professor flagged (exam, homework, 'important'), quoted from the transcript."""
    out = []
    for t, text in paras:
        for sent in re.split(r"(?<=[.!?])\s+", text):
            if FLAGS.search(sent):
                out.append((t, _one_line(sent, 220)))
                break
        if len(out) >= limit:
            break
    return out


# ----- the note ---------------------------------------------------------------------------------------

def _link(path, unit, kind):
    name = os.path.basename(path)
    if name.lower().endswith(".pdf"):
        return f"[[{name}#page={unit['n']}|{name} p.{unit['n']}]]"
    if kind == "audio":
        return f"[[{name}]] at {unit['label']}"
    if kind == "notes":
        return f"[[{os.path.splitext(name)[0]}|your note]]" + (f" ({unit['label']})" if unit.get("label") != "part 1" else "")
    if kind in ("doc", "image"):
        return f"[[{name}]]" + (f" ({unit['label']})" if kind == "doc" else "")
    return f"[[{name}]] {unit['label'].lower()}"


def _icon(kind):
    return "📼" if kind == "audio" else "📝" if kind == "notes" else "📑"


def _quote(text, n=700):
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    out, size = [], 0
    for l in lines:
        if size + len(l) > n:
            out.append("…")
            break
        out.append(l)
        size += len(l)
    return out


def note_markdown(lec, klass, mats, aligned, why, result, marks, boards, board_text, problems=()):
    units = {p: (k, u) for p, k, u in mats}
    day = lec["start"].strftime("%a %b %d, %Y").replace(" 0", " ")
    ctag = re.sub(r"[^a-z0-9]+", "-", (klass or "").lower()).strip("-")
    used = [p for p, _, _ in mats]
    lines = ["---", "type: lecture-review", "tags: [lecture-review" + (f", {ctag}" if ctag else "") + "]"]
    if klass:
        lines.append(f'class: "{klass}"')
    lines += [f"date: {lec['date'].isoformat()}", f'lecture: "[[{lec["stem"]}]]"',
              "materials: [" + ", ".join(f'"[[{os.path.splitext(os.path.basename(p))[0] if p.lower().endswith(".md") else os.path.basename(p)}]]"' for p in used) + "]",
              f"built: {datetime.datetime.now():%Y-%m-%d %H:%M}", "---", "",
              f"# Review · {lec['title']}", ""]
    srcs = [f"your recording ({clock(lec['duration'])})"] + \
           [f"{os.path.splitext(os.path.basename(p))[0] if p.lower().endswith('.md') else os.path.basename(p)} ({why[p][1].split(' (')[0]})" for p in used]
    if boards:
        srcs.append(f"{len(boards)} board photo{'s' if len(boards) != 1 else ''}")
    if marks:
        srcs.append(f"{len(marks)} mark{'s' if len(marks) != 1 else ''}")
    lines += [f"> [!info] {klass + ' · ' if klass else ''}{day} · notes: [[{lec['stem']}|{lec['title']}]]",
              "> Built from " + ", ".join(srcs) + ".",
              "> Where each point comes from: 🎙 said in class (time in your recording) · 📑 the professor's file · "
              "📼 the professor's recording · 📝 your notes · 📷 your board photo · ⭐ your mark.",
              "> Archie rebuilds this by itself when more material for this lecture arrives.", ""]

    flags = flagged(lec["paras"])
    if flags:
        lines += ["## Flagged in class", ""]
        lines += [f"- 🎙 `{clock(t)}` “{q}”" for t, q in flags]
        lines.append("")

    if result["only"]:
        lines += ["## Said in class, not in the material", ""]
        lines += [f"- {o['point']} 🎙 `{clock(o['at'])}`" for o in result["only"]]
        lines.append("")

    # the lecture in order: covered pieces, marks and board photos by time
    events = []
    for (p, ui), s in result["said"].items():
        events.append((s["at"] or 0, 0, ("piece", p, ui, s)))
    for t, label in marks:
        events.append((t, 1, ("mark", label)))
    for t, path in boards:
        events.append((t, 2, ("board", path)))
    events.sort(key=lambda e: (e[0], e[1]))
    if events:
        lines += ["## The lecture, piece by piece", ""]
        for t, _, ev in events:
            if ev[0] == "piece":
                _, p, ui, s = ev
                kind, us = units[p]
                u = us[ui]
                head = u.get("title") or u["label"]
                lines += [f"### {_icon(kind)} {_one_line(head, 90)} · 🎙 `{clock(t)}`", "",
                          f"*{_link(p, u, kind)}*", ""]
                q = _quote(u["text"][len(u.get('title') or ''):] if u["text"].startswith(u.get("title") or "\0") else u["text"])
                if q:
                    lines += [f"> [!quote]{'+' if kind == 'notes' else '-'} {'What you wrote' if kind == 'notes' else 'On the recording' if kind == 'audio' else 'On the slide' if kind == 'slides' else 'On the page'}"]
                    lines += [f"> {l}" for l in q]
                    lines.append("")
                if s["bullets"]:
                    lines += [f"- {b} 🎙" for b in s["bullets"]]
                else:
                    lines.append("- *covered in class, nothing added beyond what's written* 🎙")
                lines.append("")
            elif ev[0] == "mark":
                lines += [f"- ⭐ `{clock(t)}` your mark: {ev[1]}", ""]
            else:
                name = os.path.basename(ev[1])
                lines += [f"📷 `{clock(t)}` board photo", "", f"![[{name}|420]]", ""]
                bt = board_text.get(ev[1])
                if bt:
                    lines += ["> [!note]- What's on the board"] + [f"> {l}" for l in _quote(bt, 900)] + [""]

    unplaced = []
    for p, kind, us in mats:
        if kind != "notes":
            continue
        for i, u in enumerate(us):
            if (p, i) not in result["said"]:
                unplaced.append(f"- 📝 {_one_line(u['text'], 160)} · {_link(p, u, kind)}")
    if unplaced:
        lines += ["## Your notes not matched to the recording", ""] + unplaced[:30] + [""]
    missed = []
    for p, kind, us in mats:
        hit = {ui for ui, _, _ in aligned.get(p, [])}
        for i, u in enumerate(us):
            if kind == "notes":
                break
            if i in hit or (p, i) in result["said"] or len(set(words(u.get("title", "") + " " + u["text"]))) < 4:
                continue
            missed.append(f"- {_icon(kind)} {_one_line(u.get('title') or u['text'], 90)} · {_link(p, u, kind)}")
    if missed:
        lines += ["## In the material, not mentioned in class", "",
                  "Not heard in your recording. Worth reading on your own, or asking about.", ""] + missed[:40]
        if len(missed) > 40:
            lines.append(f"- …and {len(missed) - 40} more")
        lines.append("")

    if lec["terms"]:
        lines += ["## Terms", "", " · ".join(f"[[{t}]]" for t in lec["terms"][:20]), ""]

    lines += ["## Where this came from", "", "| File | What Archie read | Matched to this lecture by |", "|---|---|---|",
              f"| 🎙 [[{lec['audio']}]] | your recording, {clock(lec['duration'])} | it's this lecture |" if lec["audio"] else
              f"| 🎙 your recording | {clock(lec['duration'])} | it's this lecture |"]
    for p, kind, us in mats:
        nm = os.path.splitext(os.path.basename(p))[0] if kind == "notes" else os.path.basename(p)
        lines.append(f"| {_icon(kind)} [[{nm}]] | {why[p][1]} | {why[p][0]} |")
    if boards:
        lines.append(f"| 📷 board photos | {len(boards)}, read by the vision model | taken during the lecture |")
    if marks:
        lines.append(f"| ⭐ your marks | {len(marks)} | made while recording |")
    for name, msg in problems:
        lines.append(f"| ⚠️ [[{name}]] | {msg} | not used |")
    lines.append("")
    if result["fixes"]:
        lines += ["> [!tip]- Words the transcript misheard (spelled right in the material)"]
        lines += [f"> - “{a}” → **{b}**" for a, b in result["fixes"]]
        lines.append("")
    return "\n".join(lines) + "\n"


# ----- Whisper's spelling list ------------------------------------------------------------------------

def glossary(cache, class_dir, limit=700):
    """Terms from this class's material, for Whisper's initial prompt, so it spells them right."""
    if not class_dir or not os.path.isdir(class_dir):
        return None
    counts, shown = {}, {}

    def add(term, w=1.0):
        k = term.lower()
        if len(k) < 3 or k in STOP or k.split()[0] in STOP or k.split()[-1] in STOP:
            return
        counts[k] = counts.get(k, 0) + w
        shown.setdefault(k, term)
    for p in materials_in(class_dir):
        c = cache.get(p) or {}
        if c.get("kind") == "audio":
            continue
        for u in c.get("units") or []:
            for line in ((u.get("title") or "") + "\n" + u.get("text", "")).splitlines():
                line = re.sub(r"^\(speaker notes\)\s*", "", line.strip())
                for t in re.findall(r"\b(?:[A-Z]{2,}[0-9]*[a-z]?|[A-Za-z]+[0-9]+[A-Za-z0-9]*)\b", line):
                    add(t, 1.5)                                          # NADH, FADH2, CO2
                for t in re.findall(r"\b[A-Z][a-z]+(?:[ \t]+(?:[A-Z][a-z]+|of|and)){1,3}\b", line):
                    if not t.endswith((" of", " and")):
                        add(t, 1.2)                                      # Krebs Cycle, Electron Transport Chain
                for t in re.findall(r"(?<=[a-z,;:] )[A-Z][a-z]{3,}\b", line):
                    add(t)                                               # a name in the middle of a sentence
                for t in re.findall(r"\b[a-z]{9,}\b", line):
                    add(t, 0.5)                                          # long technical words
    if not counts:
        return None
    multi = [k for k in counts if " " in k]
    out, size, have = [], 0, set()
    for k, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if k in have or (" " not in k and any(k in m.split() for m in multi)):
            continue                                                     # "Cycle" when "Krebs Cycle" is there
        t = shown[k]
        if size + len(t) + 2 > limit:
            break
        out.append(t)
        have.add(k)
        size += len(t) + 2
    return ("Terms from this class: " + ", ".join(out) + ".") if out else None


# ----- the worker ------------------------------------------------------------------------------------

class Reviewer:
    """Watches Lectures\\<class> folders and keeps each lecture's review up to date. Everything heavy waits
    while you're using Archie (wait())."""

    def __init__(self, get_base, chat, model, cache_path, state_path, vision=None, transcribe=None,
                 wait=lambda: None, report=lambda k, v: None):
        self.get_base = get_base          # () -> vault folder (or Archie's Notes)
        self.chat = chat
        self.model = model                # () -> model name
        self.vision = vision              # (image bytes, what) -> text
        self.transcribe = transcribe      # (path) -> [(start, end, text)]
        self.wait = wait
        self.report = report
        self.cache_path = cache_path
        self.state_path = state_path
        self.cache = self._load(cache_path)
        self.state = self._load(state_path)
        self.state.setdefault("built", {})
        self.lock = threading.Lock()
        self.kick = threading.Event()
        self.last_error = None
        self.last_pass = None

    @staticmethod
    def _load(p):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    @staticmethod
    def _save(p, d):
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
        os.replace(tmp, p)

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="lecture-review").start()
        return self

    def _loop(self):
        time.sleep(45)
        while True:
            try:
                self.run_once()
                self.last_error = None
            except Exception as e:                   # never take Archie down; try again next round
                self.last_error = f"{type(e).__name__}: {e}"
            self.last_pass = time.time()
            self.kick.wait(120)
            self.kick.clear()

    def hint(self, recording_path, klass=None):
        """Whisper's spelling list for a recording (from its class's material)."""
        base = self.get_base()
        if not base:
            return None
        if not klass:
            return None
        try:
            return glossary(self.cache, os.path.join(base, "Lectures", _safe(klass, "Other")))
        except Exception:
            return None

    # -- reading files once ----------------------------------------------------------------------------
    def _read(self, p):
        try:
            st = os.stat(p)
        except OSError:
            return None
        sig = f"{st.st_size}:{int(st.st_mtime)}"
        c = self.cache.get(p)
        if c and c.get("sig") == sig and c.get("v") == VERSION:
            return c
        if time.time() - st.st_mtime < 15:          # still syncing in
            return None
        self.wait()
        self.report("status", f"lecture review: reading {os.path.basename(p)}...")
        try:
            r = read_material(p, self.vision, self.transcribe)
        except Exception as e:
            r = {"kind": "unreadable", "units": [], "read": f"couldn't read it ({type(e).__name__}: {_one_line(e, 120)})"}
        r.update(sig=sig, v=VERSION)
        with self.lock:
            self.cache[p] = r
            self._save(self.cache_path, self.cache)
        return r

    def _board_text(self, path):
        key = "board:" + path
        c = self.cache.get(key)
        if c is not None:
            return c.get("text", "")
        if not self.vision:
            return ""
        self.wait()
        try:
            with open(path, "rb") as f:
                text = self.vision(f.read(), "board") or ""
        except Exception:
            text = ""
        with self.lock:
            self.cache[key] = {"text": text}
            self._save(self.cache_path, self.cache)
        return text

    # -- one pass over every class ---------------------------------------------------------------------
    def run_once(self):
        base = self.get_base()
        root = os.path.join(base, "Lectures") if base else None
        if not root or not os.path.isdir(root):
            return []
        built = []
        for klass in sorted(os.listdir(root)):
            d = os.path.join(root, klass)
            if not os.path.isdir(d) or klass.lower() in ("inbox", "lecture inbox"):
                continue
            mats = materials_in(d)
            for p in mats:
                self._read(p)
            lecs = lectures_in(d)
            if not lecs:
                continue
            placed = assign(mats, self.cache, lecs, d)
            for lec in lecs:
                mine = [p for p in mats if placed.get(p, (None,))[0] == lec["path"]]
                if not mine and not notes_for(d, lec):
                    continue
                out = self._build_one(lec, klass, d, mine, placed, latest=lecs[-1])
                if out:
                    built.append(out)
        return built

    def _build_one(self, lec, klass, class_dir, mine, placed, latest=None):
        marks = marks_for(class_dir, lec)
        boards = boards_for(class_dir, lec)
        notes = notes_for(class_dir, lec)
        bad = sorted(p for p in materials_in(class_dir) if (self.cache.get(p) or {}).get("kind") == "unreadable") \
            if lec is latest else []
        sig_src = json.dumps([VERSION, bad, [t for t in lec["paras"]],
                              [(p, (self.cache.get(p) or {}).get("sig"), placed[p][1]) for p in mine],
                              marks, [b[1] for b in boards], [(n[0], n[2]) for n in notes]], default=str)
        sig = hashlib.sha1(sig_src.encode("utf-8", "replace")).hexdigest()
        key = os.path.normcase(lec["path"])
        rec = self.state["built"].get(key) or {}
        if rec.get("sig") == sig and rec.get("out") and os.path.exists(rec["out"]):
            return None
        mats = [(p, self.cache[p]["kind"], self.cache[p]["units"]) for p in mine if self.cache.get(p, {}).get("units")]
        for p, title, body in notes:                 # your notes, lined up with the recording like the material
            units = [{"n": i, "label": f"part {i}", "title": _one_line(_title_of(s), 70), "text": s}
                     for i, s in enumerate(_sections(body, 1), 1)]   # one piece per paragraph
            mats.append((p, "notes", units))
        wins = windows(lec["paras"])
        aligned = {}
        for p, kind, units in mats:
            aligned[p] = align(units, wins)
        name = f"{klass} · {lec['title']}"
        report = lambda f, what: self.report("status", f"lecture review for {name}: {what}...")
        result = build(lec, mats, aligned, self.chat, self.model(), klass, wait=self.wait, progress=report)
        board_text = {p: self._board_text(p) for _, p in boards}
        why = {p: (placed[p][1], self.cache[p]["read"]) for p in mine}
        for p, title, body in notes:
            why[p] = ("written for this class that day", "your notes")
        problems = []
        if lec is latest:                            # files Archie can't read: said once, on the newest review
            problems = [(os.path.basename(p), self.cache[p]["read"]) for p in materials_in(class_dir)
                        if (self.cache.get(p) or {}).get("kind") == "unreadable"]
        md = note_markdown(lec, klass, mats, aligned, why, result, marks, boards, board_text, problems)
        out = os.path.join(class_dir, lec["stem"] + SUFFIX)
        if rec.get("out") and os.path.exists(rec["out"]) and rec.get("mtime") and \
                abs(os.path.getmtime(rec["out"]) - rec["mtime"]) > 2:
            out = os.path.join(class_dir, lec["stem"] + SUFFIX_KEPT)      # you edited the review: keep yours
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)
        self._link_from_lecture(lec, os.path.splitext(os.path.basename(out))[0])
        with self.lock:
            self.state["built"][key] = {"sig": sig, "out": out, "mtime": os.path.getmtime(out), "at": time.time(),
                                        "materials": [os.path.basename(p) for p in mine]}
            self._save(self.state_path, self.state)
        self.report("lecture_review", (klass, out))
        return out

    @staticmethod
    def _link_from_lecture(lec, review_stem):
        """One line in the lecture note pointing at its review (added once)."""
        try:
            with open(lec["path"], encoding="utf-8") as f:
                text = f.read()
            if f"[[{review_stem}" in text:
                return
            line = f"> Review with the professor's material: [[{review_stem}|open the review]]"
            anchor = "> Recorded on your phone, typed out and sorted on your PC by Archie."
            if anchor in text:
                text = text.replace(anchor, anchor + "\n" + line, 1)
            else:
                m = re.match(r"^---\n.*?\n---\n", text, re.S)
                cut = m.end() if m else 0
                text = text[:cut] + "\n" + line + "\n" + text[cut:]
            st = os.stat(lec["path"])
            with open(lec["path"], "w", encoding="utf-8") as f:
                f.write(text)
            os.utime(lec["path"], (st.st_atime, st.st_mtime))      # keep its date as it was
        except OSError:
            pass

    def status(self):
        b = self.state.get("built") or {}
        last = max((v.get("at", 0) for v in b.values()), default=0)
        return {"reviews": len(b), "last_review": last or None, "last_pass": self.last_pass, "error": self.last_error,
                "files_read": sum(1 for k in self.cache if not k.startswith("board:"))}
