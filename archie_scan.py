"""
archie_scan.py - reads your handwriting.

Photos of notes (and scanned PDFs) that land in the Notes folder are read
ONCE by a vision model on your own PC. What it reads is saved right next to
the photo as "<name> (transcribed).md", so from then on the page is searchable
like typed notes: Notes search, brief quizzes, Obsidian, everything.

  * Fix a misread word?  Edit the .md in Notepad; Archie uses your version.
  * Want a page read again?  Delete its .md.
  * It waits while you're chatting, so it never slows down an answer.
"""

import base64
import datetime
import io
import json
import os
import threading
import time
import urllib.error

from archie_brain import (ArchieError, IMAGE_EXT, _http_error_text, _post, is_vision_model,
                          list_models)

SUFFIX = " (transcribed).md"
# Best at reading text in pictures first. qwen2.5vl reads handwriting noticeably better.
OCR_PREFERENCE = ("qwen2.5vl", "qwen3-vl", "gemma3", "minicpm-v", "llama3.2-vision", "llava")
SKIP_DIRS = {"screenshots"}
MAX_PDF_PAGES = 60

PROMPT = """Transcribe ALL of the text in this image exactly as it is written. It is \
probably handwritten notes (it could also be a printed page or a whiteboard).
- Keep the original wording, spelling, line breaks, headings, bullet points, numbering, \
arrows and math (write math like  x^2 + 3x = 7).
- If a word is hard to read, write your best guess followed by [?].
- For a drawing, diagram, chart or sketch, write  [Diagram: what it shows, including its labels].
- Crossed-out text: leave it out.
- Output ONLY the transcription in Markdown. No introduction, no comments."""


def transcript_path(path):
    base = os.path.splitext(path)[0]
    if base.lower().endswith(".excalidraw"):      # "Lecture 3.excalidraw.png" -> "Lecture 3 (transcribed).md"
        base = base[:-len(".excalidraw")]
    return base + SUFFIX


def is_drawing(path):
    """A pen page from Obsidian's Excalidraw plugin (auto-exported PNG)."""
    return ".excalidraw." in os.path.basename(path).lower()


READABLE = set(IMAGE_EXT) | {".heic", ".heif", ".pdf"}


def pick_ocr_model(preferred=None):
    names = list_models()
    if names is None:
        raise ArchieError("I can't reach Ollama.")
    if preferred:
        hit = next((n for n in names if n == preferred or n.split(":")[0] == preferred), None)
        if hit:
            return hit
    for pref in OCR_PREFERENCE:
        for n in names:
            if n.startswith(pref) and is_vision_model(n):
                return n
    for n in names:
        if is_vision_model(n):
            return n
    raise ArchieError("Reading handwriting needs a vision model. Run Get Handwriting Model.bat.")


def _image_b64(img):
    """PIL image -> base64 JPEG, sized for reading small handwriting."""
    img = img.convert("RGB")
    img.thumbnail((1800, 1800))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return base64.b64encode(buf.getvalue()).decode()


def open_image(path):
    """Open a photo the right way up (phones store rotation separately), HEIC included."""
    from PIL import Image, ImageOps
    if path.lower().endswith((".heic", ".heif")):
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
        except ImportError:
            raise ArchieError("iPhone photos (.heic) need one extra piece: run Install Extras.bat.")
    im = Image.open(path)
    return ImageOps.exif_transpose(im)


def pdf_page_images(path):
    """The scanned page pictures inside a PDF that has no text layer, or None if it has text."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    from PIL import Image
    reader = PdfReader(path)
    text = "".join((p.extract_text() or "") for p in reader.pages[:5])
    if len(text.strip()) > 40:
        return None                          # a normal PDF: Notes already reads it
    pages = []
    for page in reader.pages[:MAX_PDF_PAGES]:
        best = None
        try:
            for im in page.images:
                pil = Image.open(io.BytesIO(im.data))
                if best is None or pil.width * pil.height > best.width * best.height:
                    best = pil
        except Exception:
            best = None
        pages.append(best)
    return pages if any(pages) else None


def read_image(model, b64, keep_alive="2m"):
    body = {"model": model, "stream": False, "keep_alive": keep_alive,
            "messages": [{"role": "user", "content": PROMPT, "images": [b64]}],
            "options": {"temperature": 0.1, "num_ctx": 8192, "num_predict": 2500}}
    try:
        with _post("/api/chat", body, timeout=600) as resp:
            return json.load(resp).get("message", {}).get("content", "").strip()
    except urllib.error.HTTPError as e:
        raise ArchieError(_http_error_text(e))
    except urllib.error.URLError:
        raise ArchieError("I can't reach Ollama.")


def _clean(text):
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        t = t.rsplit("```", 1)[0]
    return t.strip()


class HandwritingReader:
    """Finds photos / scanned PDFs in Notes that haven't been read yet and reads them."""

    def __init__(self, notes_dir, report, is_busy, get_model=lambda: None, get_vault=lambda: None):
        self.notes_dir = notes_dir
        self.get_vault = get_vault        # your Obsidian vault (also watched, see _wanted)
        self.report = report              # report(kind, value) -> Archie's event queue
        self.is_busy = is_busy            # True while you're chatting: wait
        self.get_model = get_model
        self.running = threading.Event()
        self.failed = {}                  # path -> mtime we already failed on (don't loop)
        self.warned = set()               # "Ollama is off"-type messages: say them once

    def _candidates(self):
        """(path, in_vault) for every file that could need reading.
        Notes folder: every photo / scan.  Obsidian vault: only pen pages
        (Excalidraw PNG exports, anywhere) and anything inside a folder called
        Handwritten, so your reference pictures and art are left alone."""
        for dp, dns, fns in os.walk(self.notes_dir):
            dns[:] = [d for d in dns if not d.startswith(".") and d.lower() not in SKIP_DIRS]
            for fn in fns:
                if os.path.splitext(fn)[1].lower() in READABLE:
                    yield os.path.join(dp, fn), False
        vault = self.get_vault()
        if vault and os.path.isdir(vault):
            for dp, dns, fns in os.walk(vault):
                dns[:] = [d for d in dns if not d.startswith(".")]
                in_hw = "handwritten" in [x.lower() for x in os.path.relpath(dp, vault).split(os.sep)]
                for fn in fns:
                    path = os.path.join(dp, fn)
                    ext = os.path.splitext(fn)[1].lower()
                    if (ext == ".png" and is_drawing(path)) or (in_hw and ext in READABLE):
                        yield path, True

    def pending(self):
        out = []
        now = time.time()
        for path, in_vault in self._candidates():
            try:
                mt = os.path.getmtime(path)
            except OSError:
                continue
            tp = transcript_path(path)
            if os.path.exists(tp):
                # a pen page you've added to since it was read: read it again
                if not (is_drawing(path) and mt > os.path.getmtime(tp) + 2):
                    continue
            if self.failed.get(path) == mt:
                continue
            # wait until it's finished copying / you've stopped drawing for a minute
            if now - mt < (60 if is_drawing(path) else 5):
                continue
            out.append(path)
        return sorted(out, key=lambda p: os.path.getmtime(p))

    def start(self):
        """Read everything waiting, in the background. Safe to call often."""
        if self.running.is_set():
            return
        self.running.set()
        threading.Thread(target=self._run, daemon=True).start()

    def _wait_idle(self):
        while self.is_busy():
            time.sleep(2)

    def _run(self):
        done, problems = [], []
        try:
            todo = self.pending()
            pdfs = [p for p in todo if p.lower().endswith(".pdf")]
            images = [p for p in todo if not p.lower().endswith(".pdf")]
            # only scanned PDFs need reading; normal PDFs are skipped quietly
            scans = []
            for p in pdfs:
                try:
                    pages = pdf_page_images(p)
                except Exception:
                    pages = None
                if pages:
                    scans.append((p, pages))
                else:
                    self.failed[p] = os.path.getmtime(p)
            jobs = [(p, None) for p in images] + scans
            if not jobs:
                return
            model = pick_ocr_model(self.get_model())
            total = len(jobs)
            for i, (path, pages) in enumerate(jobs, 1):
                name = os.path.basename(path)
                try:
                    if pages is None:
                        self._wait_idle()
                        self.report("status", f"Reading handwriting: {name} ({i} of {total})...")
                        text = _clean(read_image(model, _image_b64(open_image(path)),
                                                 keep_alive="2m" if i < total else 0))
                    else:
                        parts = []
                        for n, img in enumerate(pages, 1):
                            self._wait_idle()
                            self.report("status", f"Reading scan: {name} page {n} of {len(pages)} "
                                                  f"({i} of {total})...")
                            if img is None:
                                continue
                            last = i == total and n == len(pages)
                            parts.append(f"## Page {n}\n\n" + _clean(
                                read_image(model, _image_b64(img), keep_alive=0 if last else "2m")))
                        text = "\n\n".join(parts)
                    if not text.strip():
                        raise ArchieError("no text found")
                    today = datetime.date.today()
                    stamp = today.strftime("%b %d, %Y").replace(" 0", " ")
                    title = os.path.basename(transcript_path(path))[:-len(SUFFIX)]
                    kind = "pen" if is_drawing(path) else "scan" if pages else "photo"
                    with open(transcript_path(path), "w", encoding="utf-8") as f:
                        f.write(f"---\ntags: [handwritten]\nsource: \"[[{name}]]\"\n"
                                f"kind: {kind}\ntranscribed: {today.isoformat()}\n---\n\n"
                                f"# {title}\n\n![[{name}]]\n\n"
                                f"*Typed out by Archie from **{name}** on {stamp} ({model}). "
                                "Edit this note to fix any misread words.*\n\n" + text + "\n")
                    done.append(name)
                except ArchieError as e:
                    if "can't reach Ollama" in str(e):
                        raise                      # try again later; not this file's fault
                    problems.append(f"{name}: {e}")
                    self.failed[path] = os.path.getmtime(path)
                except Exception as e:
                    problems.append(f"{name}: {e}")
                    self.failed[path] = os.path.getmtime(path)
        except ArchieError as e:
            if str(e) not in self.warned:
                self.warned.add(str(e))
                problems.append(f"your photos of notes: {e}")
        finally:
            self.running.clear()
            if done or problems:
                self.report("handwriting_done", (done, problems))
