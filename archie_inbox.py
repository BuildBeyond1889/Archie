"""Archie Inbox: anything you drop on Archie gets one card (what it is, which class, where it goes) and one tap saves it.

Filing follows the SAME rules as files dropped on a laptop or shared from the phone (archie_sync._file_drop), so the
lecture review finds everything where it already looks:
  - a professor's files for a class (slides, handouts, readings, the syllabus) -> Lectures/<class>/Materials,
    original file name and date kept (the review matches files to lectures by the date in the name, the content,
    and the arrival date)
  - your own recordings -> Lectures/<class> (Archie's listener types them up as lecture notes) or Voice inbox
  - board photos and other files for a class -> Lectures/<class>/Files, names untouched
  - ideas -> Ideas
Every saved file (except notes and recordings) gets a small Obsidian note beside it, like the laptop's drops do.
Nothing is ever renamed or re-dated, and a file that's already been saved is spotted instead of copied twice.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import threading
import time

MATERIAL_EXT = {".pdf", ".ppt", ".pptx", ".key", ".odp", ".doc", ".docx", ".rtf", ".odt", ".xls", ".xlsx", ".csv"}
AUDIO_EXT = {".mp3", ".m4a", ".wav", ".webm", ".ogg", ".opus", ".aac", ".flac", ".mp4", ".mov", ".mkv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp"}
TEXT_EXT = {".md", ".txt"}
EMBED_EXT = IMAGE_EXT | {".pdf"}
CLASS_KINDS = ("class", "lab")
DURATION = {"class": 75, "lab": 110}
GUESS_WINDOW = 60          # minutes after a class ends that a drop still counts as "for that class"

TYPES = ["slides / handout", "reading", "syllabus", "assignment", "board photo", "my notes", "recording", "idea", "other"]
MATERIAL_TYPES = {"slides / handout", "reading", "syllabus"}


def _safe(s, fallback="file"):
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(s or "")).strip().strip(".")
    return s[:120] or fallback


def _unique(path):
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(path)
    i = 2
    while os.path.exists(f"{stem} ({i}){ext}"):
        i += 1
    return f"{stem} ({i}){ext}"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _own_recording(name):
    return bool(re.search(r"Recording \d{14}|\b20\d{6} \d{6}\.|\(20\d\d-\d\d-\d\d \d{1,2}\.\d\d ?[AP]M\)\.\w+$|^Recording\b", name))


def _board(name):
    return bool(re.search(r"\bboard\b", name, re.I))


class Inbox:
    KINDS = tuple(TYPES)

    def __init__(self, app_dir, vault, calendar=None, classes_extra=None):
        self.app_dir = app_dir
        self.vault = vault                      # callable -> Obsidian vault folder (or None)
        self.calendar = calendar                # archie_calendar.Calendar or None
        self.index_path = os.path.join(app_dir, "inbox_index.json")
        self.queue_path = os.path.join(app_dir, "inbox_queue.txt")   # "Send to Archie" writes paths here
        self.lock = threading.Lock()
        self._undo = {}

    # ---- where things go ---------------------------------------------------------------------
    def base(self):
        v = None
        try:
            v = self.vault()
        except Exception:
            pass
        return v if v and os.path.isdir(v) else os.path.join(self.app_dir, "Notes")

    def classes(self):
        """Class names: weekly classes/labs on the calendar, then the folders already in Lectures."""
        names = []
        try:
            for e in self.calendar.load():
                if e.get("kind") in CLASS_KINDS and e.get("title") and e["title"] not in names:
                    names.append(e["title"])
        except Exception:
            pass
        lec = os.path.join(self.base(), "Lectures")
        if os.path.isdir(lec):
            for d in sorted(os.listdir(lec)):
                if os.path.isdir(os.path.join(lec, d)) and d not in names and not d.startswith("."):
                    names.append(d)
        return names

    def class_now(self, now=None):
        """The class that's on, or ended within the last hour (from the calendar)."""
        now = now or datetime.datetime.now()
        mins = now.hour * 60 + now.minute
        best = None
        try:
            events = self.calendar.on(now.date())
        except Exception:
            return None
        for e in events:
            if e.get("kind") not in CLASS_KINDS:
                continue
            m = re.match(r"\s*(\d{1,2}):(\d{2})", e.get("time") or "")
            if not m:
                continue
            start = int(m.group(1)) * 60 + int(m.group(2))
            end = start + DURATION.get(e["kind"], 75)
            if start - 10 <= mins <= end + GUESS_WINDOW:
                best = e["title"]
        return best

    def dest_dir(self, kind, klass):
        base = self.base()
        if kind == "idea":
            return os.path.join(base, "Ideas")
        if not klass:
            if kind == "recording":
                return os.path.join(base, "Archie Lite", "Voice inbox")
            return os.path.join(base, "Archie Inbox")
        cls = os.path.join(base, "Lectures", _safe(klass, "Other"))
        if kind in MATERIAL_TYPES:
            return os.path.join(cls, "Materials")
        if kind == "assignment":
            return os.path.join(cls, "Assignments")
        if kind == "recording":
            return cls
        if kind == "my notes":
            return cls
        return os.path.join(cls, "Files")

    def rel(self, path):
        try:
            return os.path.relpath(path, self.base()).replace("\\", "/")
        except ValueError:
            return path

    # ---- the guess ---------------------------------------------------------------------------
    def guess(self, path, now=None):
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        low = name.lower()
        klass = self.class_now(now)
        for c in self.classes():                       # a class name in the file name wins
            if re.sub(r"\W", "", c.lower()) and re.sub(r"\W", "", c.lower()) in re.sub(r"\W", "", low):
                klass = c
                break
        if "syllabus" in low:
            kind, why = "syllabus", "the name says syllabus"
        elif ext in AUDIO_EXT:
            kind, why = "recording", ("one of your recordings" if _own_recording(name) else "a recording")
            if klass and not _own_recording(name):
                kind, why = "slides / handout", "audio from the professor"
        elif ext in IMAGE_EXT:
            if _board(name) or klass:
                kind, why = "board photo", "a photo during class" if klass else "a board photo"
            else:
                kind, why = "other", "a picture"
        elif re.search(r"assign|homework|\bhw\d*\b|worksheet|lab report|problem set|pset|due", low):
            kind, why = "assignment", "the name looks like an assignment"
        elif ext in {".ppt", ".pptx", ".key", ".odp"}:
            kind, why = "slides / handout", "slides"
        elif re.search(r"chapter|\bch\.? ?\d|reading|article|paper", low) and ext in MATERIAL_EXT:
            kind, why = "reading", "the name looks like a reading"
        elif ext in TEXT_EXT:
            kind, why = "my notes", "a text note"
        elif ext in MATERIAL_EXT and klass:
            kind, why = "slides / handout", "a class file"
        else:
            kind, why = "other", "a file"
        dup = self.already(path)
        return {"path": path, "name": name, "kind": kind, "klass": klass, "why": why, "dup": dup,
                "dest": self.dest_dir(kind, klass), "size": os.path.getsize(path)}

    def describe(self, g):
        what = {"slides / handout": "slides or a handout", "board photo": "a photo of the board",
                "my notes": "your notes", "recording": "a recording", "other": "something to sort"}.get(g["kind"], g["kind"])
        return f"{what} for {g['klass']}" if g.get("klass") else what

    # ---- duplicates ------------------------------------------------------------------------------
    def _index(self):
        try:
            with open(self.index_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_index(self, idx):
        with open(self.index_path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=0)
        os.replace(self.index_path + ".tmp", self.index_path)

    def already(self, path):
        """{'dest', 'date'} if this exact file was saved before (by its contents), else None."""
        try:
            if os.path.getsize(path) > 2 * 1024 ** 3:
                return None
            h = sha256(path)
        except OSError:
            return None
        rec = self._index().get(h)
        if rec and os.path.exists(rec.get("dest", "")):
            return rec
        return None

    def remember(self, path, kind="file", klass=None):
        """Note a file saved some other way (the laptop's or phone's older filing), for the duplicate check."""
        h = sha256(path)
        with self.lock:
            idx = self._index()
            idx[h] = {"dest": path, "date": datetime.date.today().isoformat(), "kind": kind, "klass": klass or ""}
            self._save_index(idx)

    # ---- saving ----------------------------------------------------------------------------------
    @staticmethod
    def renamed(original, new_stem):
        """The file name to save under when you rename it. A date and time in the original name
        (like "Board (2026-01-21 1.47 PM)") is kept on the end, because the lecture review uses it."""
        stem, ext = os.path.splitext(os.path.basename(original))
        new_stem = _safe((new_stem or "").strip(), "")
        if not new_stem or new_stem == stem:
            return _safe(os.path.basename(original))
        m = re.search(r"\((?:[A-Za-z]+ )?(20\d\d-\d\d-\d\d[^)]*)\)", stem)
        if m and m.group(1) not in new_stem:
            label = "Board " if re.search(r"\bboard\b", stem, re.I) else ""
            new_stem = f"{new_stem} ({label}{m.group(1)})"
        return new_stem + ext

    def save(self, path, kind, klass, source="PC", new_name=None):
        """Copy the file to where it belongs (date kept), add its little note. Returns (dest, undo_id)."""
        name = self.renamed(path, new_name) if new_name else _safe(os.path.basename(path))
        ext = os.path.splitext(name)[1].lower()
        day = datetime.date.fromtimestamp(os.path.getmtime(path)).isoformat()
        dest_dir = self.dest_dir(kind, klass)
        os.makedirs(dest_dir, exist_ok=True)
        dest = _unique(os.path.join(dest_dir, name if ext != ".md" else f"{day} {name}"))
        shutil.copy2(path, dest)                      # keeps the file's own date
        made = [dest]
        material = kind in MATERIAL_TYPES and bool(klass)
        if ext not in AUDIO_EXT and ext != ".md" and kind != "recording":
            note_dir = os.path.dirname(dest_dir) if dest_dir.endswith(("Materials", "Files", "Assignments")) else dest_dir
            stem = os.path.splitext(name)[0]
            note = _unique(os.path.join(note_dir, f"{day} {_safe(stem, 'File')}.md"))
            fname = os.path.basename(dest)
            size = os.path.getsize(dest)
            tags = "lecture-file, archie-inbox" if klass else ("idea, archie-inbox" if kind == "idea" else "file, archie-inbox")
            lines = ["---", f"tags: [{tags}]"] + ([f'class: "{klass}"'] if klass else []) + [
                f"date: {day}", f'file: "[[{fname}]]"', f"kind: {kind}", f"source: Archie Inbox ({source})", "---", "",
                f"# {stem}", "",
                f"- **File:** [[{fname}]] ({size / 1048576:.1f} MB)" if size >= 1048576 else f"- **File:** [[{fname}]] ({max(1, size // 1024)} KB)",
                f"- **Class:** {klass}" if klass else "", f"- **Kind:** {kind}",
                f"- **Saved:** {datetime.date.today().isoformat()}, from the {source}",
                "- **Lecture review:** Archie lines this up with the lecture it belongs to" if material else "", ""]
            if ext in EMBED_EXT:
                lines += [f"![[{fname}]]", ""]
            if ext in TEXT_EXT:
                try:
                    with open(dest, encoding="utf-8", errors="replace") as f:
                        lines += ["## Text", "", f.read(200_000)]
                except OSError:
                    pass
            with open(note, "w", encoding="utf-8") as f:
                f.write("\n".join(l for l in lines if l != "") + "\n")
            made.append(note)
        try:
            h = sha256(dest)
            with self.lock:
                idx = self._index()
                idx[h] = {"dest": dest, "date": datetime.date.today().isoformat(), "kind": kind, "klass": klass or "",
                          "at": time.time(), "source": source}
                self._save_index(idx)
        except OSError:
            h = None
        uid = os.urandom(6).hex()
        self._undo[uid] = (made, h, time.time())
        return dest, uid

    def undo(self, uid):
        made, h, t = self._undo.pop(uid, (None, None, 0))
        if not made:
            return False
        for p in made:
            try:
                os.remove(p)
            except OSError:
                pass
        if h:
            with self.lock:
                idx = self._index()
                idx.pop(h, None)
                self._save_index(idx)
        return True

    def recent(self, days=7):
        """What got filed lately (for the phone's "since you last opened")."""
        cut = time.time() - days * 86400
        out = [dict(r) for r in self._index().values() if (r.get("at") or 0) >= cut and os.path.exists(r.get("dest", ""))]
        return sorted(out, key=lambda r: r["at"])[-30:]

    # ---- the dates reader: a syllabus that arrives from the laptop or phone opens it on the PC ----------
    def queue_dates(self, path, klass=None):
        with self.lock:
            with open(os.path.join(self.app_dir, "dates_queue.txt"), "a", encoding="utf-8") as f:
                f.write(json.dumps({"path": path, "klass": klass or None}) + "\n")

    def take_dates(self):
        q = os.path.join(self.app_dir, "dates_queue.txt")
        if not os.path.exists(q):
            return []
        try:
            with self.lock:
                tmp = q + ".taking"
                os.replace(q, tmp)
                with open(tmp, encoding="utf-8", errors="replace") as f:
                    lines = [l for l in f if l.strip()]
                os.remove(tmp)
        except OSError:
            return []
        out = []
        for l in lines:
            try:
                d = json.loads(l)
                if os.path.isfile(d.get("path", "")):
                    out.append((d["path"], d.get("klass")))
            except ValueError:
                pass
        return out

    # ---- "Send to Archie" from the Windows right-click menu ---------------------------------------
    def take_queue(self):
        """Paths queued by Tools\\Send to Archie.bat (one per line). Returns them and empties the queue."""
        if not os.path.exists(self.queue_path):
            return []
        try:
            tmp = self.queue_path + ".taking"
            os.replace(self.queue_path, tmp)
            with open(tmp, encoding="utf-8", errors="replace") as f:
                paths = [l.strip().strip('"') for l in f if l.strip()]
            os.remove(tmp)
        except OSError:
            return []
        return [p for p in paths if os.path.isfile(p)]
