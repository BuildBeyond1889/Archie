"""
archie_listen.py - recordings that arrive from elsewhere, typed out in the background.

1. Walk-and-talk voice notes from your phone
   Record in Obsidian's mobile app (the Audio recorder button) and let it sync,
   or drop any recording into a "Voice inbox" folder (in your vault or Notes).
   Lectures (recorded during a class on the calendar, dropped in a "Lectures" folder, or
   longer than 30 minutes) become full lecture notes instead: see archie_lecture.py.
   Archie types it out, tidies it into notes, and saves a note next to it:
   "<recording> (transcribed).md" with the audio embedded, tagged #voice-note.

2. Audiobooks
   Put a book in Notes/Audiobooks: a folder of files (one per chapter) or a
   single .m4b/.mp3. Archie types it out chapter by chapter (it can take hours,
   so it resumes where it left off and pauses while you chat) and saves it as a
   book in Notes/Books, so "quiz me on <book> chapter 3" works.
"""

import datetime
import json
import os
import re
import threading
import time

AUDIO_EXT = {".mp3", ".mp4", ".m4a", ".m4b", ".m4v", ".mkv", ".mka", ".aac", ".ogg", ".oga", ".opus", ".webm", ".wav", ".flac", ".wma", ".3gp", ".amr"}
DRM_EXT = {".aax", ".aa", ".aaxc"}
SUFFIX = " (transcribed).md"
CHUNK = 30 * 60          # books without chapter marks are cut into 30-minute parts


def _natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


class Listener:
    def __init__(self, notes_dir, get_vault, state_path, transcriber, report, is_busy,
                 tidy=None, want_tidy=lambda: True, paused=lambda: False, lecture=None):
        self.notes_dir = notes_dir
        self.get_vault = get_vault
        self.state_path = state_path
        self.transcriber = transcriber      # () -> Transcriber
        self.report = report                # (kind, value)
        self.is_busy = is_busy
        self.tidy = tidy                    # (text) -> tidied text, or None
        self.want_tidy = want_tidy
        self.paused = paused
        self.lecture = lecture              # (path, is_vault, text, timed) -> note path, or None if it isn't a lecture
        self.running = threading.Event()
        self.state = self._load()

    # ----- remembering progress ---------------------------------------------------

    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                st = json.load(f)
        except (OSError, ValueError):
            st = {"done": {}, "books": {}}
        for b in st.get("books", {}).values():   # an older version gave up on books it couldn't open
            if b.get("finished") and not b.get("total"):
                b.pop("finished", None)
        return st

    def _save(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=1)
        os.replace(tmp, self.state_path)

    # ----- what's waiting ------------------------------------------------------------

    def voice_notes(self):
        out, now = [], time.time()
        roots = []
        vault = self.get_vault()
        if vault and os.path.isdir(vault):
            roots.append((vault, True))
        roots.append((self.notes_dir, False))
        for root, is_vault in roots:
            for dp, dns, fns in os.walk(root):
                dns[:] = [d for d in dns if not d.startswith(".") and d.lower() not in ("audiobooks", "recordings")]
                parts = [p.lower() for p in os.path.relpath(dp, root).split(os.sep)]
                inbox = "voice inbox" in parts or "lectures" in parts
                for fn in fns:
                    ext = os.path.splitext(fn)[1].lower()
                    if ext not in AUDIO_EXT:
                        continue
                    # Obsidian's recorder names files "Recording 20260928123456.webm"
                    if not (inbox or (is_vault and fn.lower().startswith("recording"))):
                        continue
                    path = os.path.join(dp, fn)
                    try:
                        mt = os.path.getmtime(path)
                    except OSError:
                        continue
                    if now - mt < 20 or self.state["done"].get(path) == mt:
                        continue
                    if os.path.exists(os.path.splitext(path)[0] + SUFFIX):
                        continue
                    out.append((path, is_vault))
        return sorted(out, key=lambda x: os.path.getmtime(x[0]))

    def audiobooks(self):
        """[(title, [files])] in Notes/Audiobooks."""
        base = os.path.join(self.notes_dir, "Audiobooks")
        books = []
        if not os.path.isdir(base):
            return books
        for name in sorted(os.listdir(base), key=_natural):
            p = os.path.join(base, name)
            if os.path.isdir(p):
                files = []
                for dp, dns, fns in os.walk(p):
                    dns.sort(key=_natural)
                    files += [os.path.join(dp, f) for f in sorted(fns, key=_natural)
                              if os.path.splitext(f)[1].lower() in AUDIO_EXT | DRM_EXT]
                if files:
                    books.append((name, files))
            elif os.path.splitext(name)[1].lower() in AUDIO_EXT | DRM_EXT:
                books.append((os.path.splitext(name)[0], [p]))
        return books

    def book_status(self):
        """For messages: [(title, done_parts, total_parts or None, problem or None)]."""
        out = []
        for title, _files in self.audiobooks():
            b = self.state["books"].get(title, {})
            out.append((title, len(b.get("parts", {})), b.get("total"), b.get("error")))
        return out

    # ----- doing it --------------------------------------------------------------------

    def start(self):
        if self.running.is_set():
            return
        self.running.set()
        threading.Thread(target=self._run, daemon=True).start()

    def _wait(self):
        return self.is_busy() or self.paused()

    def _run(self):
        try:
            for path, is_vault in self.voice_notes():
                self._voice_note(path, is_vault)
            if not self.paused():
                for title, files in self.audiobooks():
                    if not self._book(title, files):
                        break           # one book at a time; stop if something went wrong
        except Exception as e:
            self.report("listen_error", str(e))
        finally:
            self.running.clear()

    def _voice_note(self, path, is_vault):
        name = os.path.basename(path)
        try:
            while self.is_busy():
                time.sleep(2)
            self.report("status", f"typing out {name}...")
            tr = self.transcriber()
            timed = []
            text = tr.transcribe(path, pause=self.is_busy, timed=timed,
                                 progress=lambda f: self.report("status", f"typing out {name}... {int(f * 100)}%"))
            if self.lecture and text:
                out = self.lecture(path, is_vault, text, timed)
                if out:
                    self.state["done"][path] = os.path.getmtime(path)
                    self._save()
                    self.report("listen_lecture", (name, out))
                    return
            tidied = ""
            if text and self.tidy and self.want_tidy():
                self.report("status", f"tidying {name} into notes...")
                try:
                    tidied = self.tidy(text)
                except Exception:
                    tidied = ""
            when = datetime.datetime.fromtimestamp(os.path.getmtime(path))
            title = f"Voice note {when:%b %d %I:%M %p}".replace(" 0", " ")
            lines = ["---", "tags: [voice-note]", f"recorded: {when:%Y-%m-%d %H:%M}",
                     f"source: \"[[{name}]]\"", "---", "", f"# {title}", "",
                     f"![[{name}]]" if is_vault else f"*Recording: {path}*", ""]
            if tidied:
                lines += [tidied.strip(), "", "> [!quote]- Word for word"]
                lines += ["> " + l if l else ">" for l in (text or "(no words heard)").splitlines()]
            else:
                lines.append(text or "*(I couldn't hear any words in this recording.)*")
            out = os.path.splitext(path)[0] + SUFFIX
            vault = self.get_vault()
            if not is_vault and vault and os.path.isdir(vault):
                # it came in through Notes: put the note in Obsidian, where you'll look for it
                folder = os.path.join(vault, "Archie", "Voice notes")
                os.makedirs(folder, exist_ok=True)
                out = os.path.join(folder, re.sub(r'[<>:"/\\|?*]', " ", title) + ".md")
                n = 2
                while os.path.exists(out):
                    out = os.path.join(folder, re.sub(r'[<>:"/\\|?*]', " ", title) + f" ({n}).md")
                    n += 1
            with open(out, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            self.state["done"][path] = os.path.getmtime(path)
            self._save()
            self.report("listen_note", (name, out))
        except Exception as e:
            self.state["done"][path] = os.path.getmtime(path)
            self._save()
            self.report("listen_error", f"Couldn't type out {name}: {e}")

    def _plan(self, title, files):
        """The parts of a book: [(label, file, start, end)]."""
        from archie_voice import audio_info
        parts = []
        if len(files) > 1:
            for i, f in enumerate(files, 1):
                parts.append((f"CHAPTER {i}", f, 0.0, float("inf")))
            return parts
        f = files[0]
        dur, chapters = audio_info(f)
        if len(chapters) > 1:
            for i, (name, s, e) in enumerate(chapters, 1):
                label = f"CHAPTER {i}" + (f": {name}" if name and not re.fullmatch(r"(chapter\s*)?\d+", name.strip(), re.I) else "")
                parts.append((label, f, s, e))
        else:
            n = max(1, int(dur // CHUNK) + (1 if dur % CHUNK > 60 else 0))
            for i in range(n):
                parts.append((f"CHAPTER {i + 1}", f, i * CHUNK, min(dur, (i + 1) * CHUNK) if i < n - 1 else float("inf")))
        return parts

    def _book(self, title, files):
        drm = [f for f in files if os.path.splitext(f)[1].lower() in DRM_EXT]
        b = self.state["books"].setdefault(title, {"parts": {}})
        if drm:
            b["error"] = "it's a copy-protected Audible .aax file; MP3 / M4B / M4A work"
            if not b.get("warned"):
                b["warned"] = True
                self._save()
                self.report("listen_error", f"\"{title}\" is an Audible .aax file, which is copy-protected, "
                                            "so I can't listen to it. MP3 / M4B / M4A files work.")
            return True
        if b.get("finished"):
            return True
        if time.time() < b.get("retry_after", 0):
            return True
        try:
            plan = self._plan(title, files)
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"
            if b.get("error") != msg:
                self.report("listen_error", f"Couldn't open the audiobook \"{title}\" yet ({msg}). "
                                            "I'll keep trying every 10 minutes.")
            b["error"], b["retry_after"] = msg, time.time() + 600
            self._save()
            self._log(title, e)
            return True
        b.pop("error", None)
        b.pop("retry_after", None)
        b["total"] = len(plan)
        if not b.get("title"):
            b["title"] = self._nice_title(title, files)
        work_dir = os.path.join(self.notes_dir, "Books", ".audiobook-work", re.sub(r'[<>:"/\\|?*]', " ", title))
        os.makedirs(work_dir, exist_ok=True)
        if not b["parts"]:
            self.report("listen_book", (title, 0, len(plan), "start"))
        tr = self.transcriber()
        from archie_voice import decode_range
        for i, (label, f, s, e) in enumerate(plan):
            key = str(i)
            if key in b["parts"]:
                continue
            while self._wait():
                time.sleep(3)
            self.report("status", f"audiobook: {title}, part {i + 1} of {len(plan)}...")
            try:
                audio = f if (s == 0 and e == float("inf")) else decode_range(f, s, e)
                text = tr.transcribe(audio, pause=self._wait,
                                     progress=lambda p, i=i: self.report(
                                         "status", f"audiobook: {title}, part {i + 1} of {len(plan)}... {int(p * 100)}%"))
            except Exception as ex:
                self.report("listen_error", f"Audiobook \"{title}\" stopped at part {i + 1}: {ex}. "
                                            "I'll try again later.")
                self._log(title, ex)
                b["retry_after"] = time.time() + 600
                self._save()
                return False
            with open(os.path.join(work_dir, f"{i:04d}.txt"), "w", encoding="utf-8") as fh:
                fh.write(f"{label}\n\n{text}\n")
            b["parts"][key] = label
            self._save()
            self._write_book(title, work_dir, len(plan))
        b["finished"] = True
        self._save()
        self.report("listen_book", (title, len(plan), len(plan), "done"))
        return True

    def _nice_title(self, title, files):
        """'WarPeaceV101-28_librivox' -> the real title stored inside the file, if there is one."""
        try:
            import av
            with av.open(files[0]) as c:
                meta = {k.lower(): v for k, v in (c.metadata or {}).items()}
            for key in ("album", "title"):
                t = (meta.get(key) or "").strip()
                if t and len(t) > 2 and not re.fullmatch(r"(chapter|track|part)?\s*\d+", t, re.I):
                    return t
        except Exception:
            pass
        return title

    def _log(self, title, e):
        import traceback
        try:
            with open(os.path.join(os.path.dirname(self.state_path), "archie_error.log"), "a",
                      encoding="utf-8") as f:
                f.write(f"\n--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} audiobook {title} ---\n"
                        + "".join(traceback.format_exception(type(e), e, e.__traceback__)))
        except OSError:
            pass

    def _write_book(self, title, work_dir, total):
        parts = sorted(fn for fn in os.listdir(work_dir) if fn.endswith(".txt"))
        body = []
        for fn in parts:
            with open(os.path.join(work_dir, fn), encoding="utf-8") as fh:
                body.append(fh.read().strip())
        out = os.path.join(self.notes_dir, "Books", f"{title} (audiobook).txt")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(f"Title: {self.state['books'].get(title, {}).get('title') or title}\nTyped out by Archie from the audiobook "
                     f"({len(parts)} of {total} parts so far).\n\n" + "\n\n".join(body) + "\n")
