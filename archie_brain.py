"""
archie_brain.py - everything Archie does that isn't drawing the window.

  * Talking to Ollama (chat, model info, embeddings) - all on localhost.
  * Reading files you attach: PDFs, Word docs, text and code, images.
  * The Notes (knowledge) folder: splits your notes into small pieces, turns
    each piece into a list of numbers ("embedding") that captures its meaning,
    and later finds the pieces closest in meaning to your question.
    This technique is called RAG - retrieval-augmented generation.

Nothing here talks to the internet.
"""

import base64
import json
import math
import os
import threading
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("ARCHIE_OLLAMA_URL", "http://localhost:11434").rstrip("/")

EMBED_MODEL = "nomic-embed-text"
# Vision models Archie will switch to automatically when you attach an image,
# in order of preference.
VISION_PREFERENCE = ("gemma3", "qwen2.5vl", "llama3.2-vision", "minicpm-v", "llava")

TEXT_EXT = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv", ".json", ".xml",
    ".yaml", ".yml", ".ini", ".cfg", ".toml", ".html", ".htm", ".css", ".tex",
    ".py", ".pyw", ".ipynb", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt", ".c",
    ".h", ".cpp", ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".lua", ".gd",
    ".swift", ".sql", ".sh", ".bat", ".ps1", ".ino", ".m", ".r", ".glsl", ".hlsl",
}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".heic", ".heif"}
DOC_EXT = {".pdf", ".docx", ".epub"}
SUPPORTED_EXT = TEXT_EXT | IMAGE_EXT | DOC_EXT


class ArchieError(Exception):
    """An error with a friendly, plain-language message."""


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def _post(path, payload, timeout=120):
    req = urllib.request.Request(
        OLLAMA_URL + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def _http_error_text(e):
    try:
        return json.loads(e.read()).get("error", str(e))
    except Exception:
        return str(e)


def list_models():
    """Names of models you've pulled, or None if Ollama isn't reachable."""
    try:
        with urllib.request.urlopen(OLLAMA_URL + "/api/tags", timeout=2) as resp:
            data = json.load(resp)
        return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        return None


_vision_cache = {}


def is_vision_model(name):
    """Ask Ollama whether a model can look at images."""
    if name in _vision_cache:
        return _vision_cache[name]
    ok = False
    try:
        with _post("/api/show", {"model": name}, timeout=10) as resp:
            info = json.load(resp)
        caps = info.get("capabilities")
        if caps is not None:
            ok = "vision" in caps
        else:  # older Ollama: look for a vision projector
            ok = bool(info.get("projector_info")) or "clip" in json.dumps(info.get("details", {}))
    except Exception:
        ok = any(name.startswith(p) for p in VISION_PREFERENCE)
    _vision_cache[name] = ok
    return ok


def pick_vision_model(current):
    """Return a model that can see images, preferring the current one."""
    if is_vision_model(current):
        return current
    names = list_models() or []
    for pref in VISION_PREFERENCE:
        for n in names:
            if n.startswith(pref) and is_vision_model(n):
                return n
    for n in names:
        if is_vision_model(n):
            return n
    raise ArchieError("To read images I need a vision model. In a terminal run:  "
                      "ollama pull gemma3:4b   then try again.")


def embed(texts):
    """Turn a list of strings into meaning-vectors using the local embedding model."""
    try:
        with _post("/api/embed", {"model": EMBED_MODEL, "input": texts}, timeout=300) as resp:
            return json.load(resp)["embeddings"]
    except urllib.error.HTTPError as e:
        msg = _http_error_text(e)
        if "not found" in msg:
            raise ArchieError("Searching your notes needs the embedding model. Run "
                              "Install Extras.bat, or in a terminal:  ollama pull "
                              f"{EMBED_MODEL}")
        raise ArchieError(f"Embedding failed: {msg}")
    except urllib.error.URLError:
        raise ArchieError("I can't reach Ollama. Is it running?")


def stream_chat(model, messages, out_q, stop_evt, num_ctx=16384):
    """Stream an answer. Pushes ("token", text) pieces; raises ArchieError on failure."""
    body = {"model": model, "messages": messages, "stream": True,
            "options": {"num_ctx": num_ctx}}
    try:
        with _post("/api/chat", body, timeout=900) as resp:
            for raw in resp:
                if stop_evt.is_set():
                    return
                raw = raw.strip()
                if not raw:
                    continue
                data = json.loads(raw)
                if "error" in data:
                    raise ArchieError(data["error"])
                piece = data.get("message", {}).get("content", "")
                if piece:
                    out_q.put(("token", piece))
                if data.get("done"):
                    break
    except urllib.error.HTTPError as e:
        msg = _http_error_text(e)
        if "not found" in msg:
            msg += f"  (Try:  ollama pull {model})"
        raise ArchieError(msg)
    except urllib.error.URLError:
        raise ArchieError("I can't reach Ollama. Is it running? Open the Ollama app, "
                          "or run  ollama serve  in a terminal, then try again.")


def quick_chat(model, prompt, max_tokens=120, timeout=120, json_mode=False,
               num_ctx=None, temperature=0.4, system=None):
    """One non-streamed answer (morning brief, vault builder). json_mode makes
    Ollama return valid JSON."""
    messages = ([{"role": "system", "content": system}] if system else []) + \
               [{"role": "user", "content": prompt}]
    options = {"num_predict": max_tokens, "temperature": temperature}
    if num_ctx:
        options["num_ctx"] = num_ctx
    body = {"model": model, "stream": False, "messages": messages, "options": options}
    if json_mode:
        body["format"] = "json"
    try:
        with _post("/api/chat", body, timeout=timeout) as resp:
            return json.load(resp).get("message", {}).get("content", "").strip()
    except urllib.error.HTTPError as e:
        raise ArchieError(_http_error_text(e))
    except urllib.error.URLError:
        raise ArchieError("I can't reach Ollama.")


# ---------------------------------------------------------------------------
# Reading files
# ---------------------------------------------------------------------------

def file_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in DOC_EXT or ext in TEXT_EXT:
        return "text"
    return None


def read_text(path):
    """Return the readable text inside a PDF, Word doc, or text/code file."""
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                raise ArchieError("Reading PDFs needs one extra piece. Double-click "
                                  "Install Extras.bat in the Archie folder, then restart Archie.")
        try:
            reader = PdfReader(path)
            pages = []
            for i, page in enumerate(reader.pages, 1):
                t = (page.extract_text() or "").strip()
                if t:
                    pages.append(f"[page {i}]\n{t}")
        except Exception as e:
            raise ArchieError(f"I couldn't read {name}: {e}")
        text = "\n\n".join(pages)
        if not text.strip():
            raise ArchieError(f"{name} looks like a scanned PDF (pictures of pages, no "
                              "text layer). Screenshot or export the pages as images and "
                              "attach those instead.")
        return text
    if ext == ".epub":
        try:
            from archie_books import epub_text
            text = epub_text(path)
        except Exception as e:
            raise ArchieError(f"I couldn't read {name}: {e}")
        if not text.strip():
            raise ArchieError(f"{name} has no readable text (it may be copy-protected).")
        return text
    if ext == ".docx":
        try:
            import docx
        except ImportError:
            raise ArchieError("Reading Word files needs one extra piece. Double-click "
                              "Install Extras.bat in the Archie folder, then restart Archie.")
        try:
            d = docx.Document(path)
            parts = [p.text for p in d.paragraphs if p.text.strip()]
            for table in d.tables:
                for row in table.rows:
                    parts.append(" | ".join(c.text.strip() for c in row.cells))
        except Exception as e:
            raise ArchieError(f"I couldn't read {name}: {e}")
        return "\n".join(parts)
    if ext == ".ipynb":
        try:
            with open(path, encoding="utf-8") as f:
                nb = json.load(f)
            return "\n\n".join("".join(c.get("source", "")) for c in nb.get("cells", []))
        except Exception as e:
            raise ArchieError(f"I couldn't read {name}: {e}")
    if ext in TEXT_EXT:
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            raise ArchieError(f"I couldn't open {name}: {e.strerror}")
        for enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
    raise ArchieError(f"I can't read {name} yet. I understand PDFs, Word (.docx), EPUB "
                      "books, text, code, and images.")


def read_image_b64(path):
    """Load an image as base64 PNG/JPEG for a vision model (shrinks huge photos)."""
    name = os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()
    try:
        from PIL import Image, ImageOps
        import io
        if ext in (".heic", ".heif"):
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                raise ArchieError(f"{name} is an iPhone photo (.heic). Reading those needs one "
                                  "extra piece: run Install Extras.bat.")
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)   # phone photos: the right way up
            im = im.convert("RGB")
            im.thumbnail((1600, 1600))  # phone photos are huge; this keeps it quick
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=90)
            return base64.b64encode(buf.getvalue()).decode()
    except ArchieError:
        raise
    except ImportError:
        if ext not in (".png", ".jpg", ".jpeg"):
            raise ArchieError(f"To read {name} I need Pillow. Run Install Extras.bat.")
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception as e:
        raise ArchieError(f"I couldn't open the image {name}: {e}")


# ---------------------------------------------------------------------------
# Notes folder (RAG)
# ---------------------------------------------------------------------------

def split_into_chunks(text, size=1200, overlap=200):
    """Cut text into overlapping pieces, preferring to break at paragraphs."""
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            cut = text.rfind("\n\n", start + size // 2, end)
            if cut == -1:
                cut = text.rfind("\n", start + size // 2, end)
            if cut == -1:
                cut = text.rfind(". ", start + size // 2, end)
            if cut != -1:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _normalize(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class NotesIndex:
    """Keeps a searchable index of everything in the Notes folder."""

    def __init__(self, folder, index_path, extra_folders=None):
        """folder: the Notes folder. extra_folders: {"Chats": path, ...} - other
        folders to search too; their files show up as "Chats/<file>"."""
        self.folder = folder
        self.extra_folders = dict(extra_folders or {})
        self.index_path = index_path
        self.lock = threading.Lock()
        self.data = {"model": EMBED_MODEL, "files": {}}
        os.makedirs(folder, exist_ok=True)
        try:
            with open(index_path, encoding="utf-8") as f:
                d = json.load(f)
            if d.get("model") == EMBED_MODEL:
                self.data = d
        except (OSError, ValueError):
            pass
        self._matrix = None

    def _save(self):
        tmp = self.index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.index_path)

    def _scan(self):
        """Find every readable file. Returns {name shown to you: (mtime, full path)}."""
        found = {}
        roots = [("", self.folder)] + [(label + "/", path)
                                       for label, path in self.extra_folders.items()]
        for prefix, base in roots:
            if not os.path.isdir(base):
                continue
            for root, dirs, files in os.walk(base):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for fn in files:
                    path = os.path.join(root, fn)
                    if (file_kind(path) != "text" or fn.endswith(".json")
                            or fn.endswith(".excalidraw.md")):   # drawings, not notes
                        continue
                    if fn.lower().endswith(".pdf") and os.path.exists(
                            os.path.splitext(path)[0] + " (transcribed).md"):
                        continue          # a scanned PDF: its transcript is read instead
                    rel = prefix + os.path.relpath(path, base).replace("\\", "/")
                    try:
                        found[rel] = (os.path.getmtime(path), path)
                    except OSError:
                        pass
        return found

    def refresh(self, progress=None):
        """Index new or changed files, forget deleted ones. Returns a summary string."""
        with self.lock:
            files = self.data["files"]
            found = self._scan()
            removed = [r for r in files if r not in found]
            for r in removed:
                del files[r]
            todo = [r for r, (m, _) in found.items()
                    if r not in files or files[r].get("mtime") != m]
            problems = []
            for i, rel in enumerate(todo, 1):
                if progress:
                    progress(f"Reading notes {i}/{len(todo)}: {rel}")
                try:
                    text = read_text(found[rel][1])
                except ArchieError as e:
                    problems.append(str(e))   # not saved, so it's retried next time
                    files.pop(rel, None)
                    continue
                pieces = split_into_chunks(text)
                vectors = []
                for b in range(0, len(pieces), 16):
                    batch = pieces[b:b + 16]
                    vectors += embed([f"search_document: {os.path.basename(rel)}\n{p}"
                                      for p in batch])
                files[rel] = {"mtime": found[rel][0],
                              "chunks": [{"text": p, "vec": [round(x, 5) for x in _normalize(v)]}
                                         for p, v in zip(pieces, vectors)]}
            if todo or removed:
                self._save()
                self._matrix = None
            def is_extra(r):
                return any(r.startswith(label + "/") for label in self.extra_folders)
            n_files = sum(1 for r, f in files.items() if f["chunks"] and not is_extra(r))
            n_other = sum(1 for r, f in files.items() if f["chunks"] and is_extra(r))
            summary = f"{n_files} note file(s)"
            if n_other:
                summary += f" + {n_other} past chat(s)"
            summary += " searchable"
            if problems:
                summary += f" ({len(problems)} couldn't be read)"
            return summary, problems

    def random_chunk(self, min_len=300):
        """A random piece of your own notes (not past chats), for quiz questions."""
        import random
        with self.lock:
            pool = [(rel, c["text"]) for rel, f in self.data["files"].items()
                    if not any(rel.startswith(l + "/") for l in self.extra_folders)
                    for c in f["chunks"] if len(c["text"]) >= min_len]
        return random.choice(pool) if pool else None

    def _build_matrix(self):
        rows = []
        for rel, f in self.data["files"].items():
            for c in f["chunks"]:
                rows.append((rel, c["text"], c["vec"]))
        self._matrix = rows

    def search(self, query, k=4, min_score=0.3):
        """Return the k note pieces closest in meaning to the question."""
        with self.lock:
            if self._matrix is None:
                self._build_matrix()
            rows = self._matrix
        if not rows:
            return []
        q = _normalize(embed([f"search_query: {query}"])[0])
        try:
            import numpy as np
            m = np.array([r[2] for r in rows], dtype="float32")
            scores = (m @ np.array(q, dtype="float32")).tolist()
        except ImportError:
            scores = [sum(a * b for a, b in zip(q, r[2])) for r in rows]
        ranked = sorted(zip(scores, rows), key=lambda t: t[0], reverse=True)
        return [(s, r[0], r[1]) for s, r in ranked[:k] if s >= min_score]


# ---------------------------------------------------------------------------
# About me, modes, and saved chats
# ---------------------------------------------------------------------------

def read_small_text(path, default=""):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return f.read().strip()
    except OSError:
        return default


def load_modes(folder, defaults):
    """Each .txt file in the Modes folder is a mode. Optional first line
    'model: <name>' picks the model that mode prefers. Returns an ordered
    {mode name: {"model": str or None, "prompt": str}}."""
    os.makedirs(folder, exist_ok=True)
    for i, (name, (model, prompt)) in enumerate(defaults.items(), 1):
        path = os.path.join(folder, f"{i} - {name}.txt")
        if not any(fn.split(" - ", 1)[-1][:-4] == name for fn in os.listdir(folder)):
            with open(path, "w", encoding="utf-8") as f:
                if model:
                    f.write(f"model: {model}\n")
                f.write(prompt.strip() + "\n")
    modes = {}
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(".txt"):
            continue
        name = os.path.splitext(fn)[0]
        name = name.split(" - ", 1)[1] if " - " in name else name
        text = read_small_text(os.path.join(folder, fn))
        model = None
        lines = text.splitlines()
        if lines and lines[0].lower().startswith("model:"):
            model = lines[0].split(":", 1)[1].strip() or None
            text = "\n".join(lines[1:]).strip()
        modes[name] = {"model": model, "prompt": text}
    return modes


def save_chat(folder, chat):
    """Save a conversation as .json (for reopening) and .md (for searching)."""
    os.makedirs(folder, exist_ok=True)
    base = os.path.join(folder, chat["id"])
    clean = []
    for m in chat["messages"]:
        clean.append({k: v for k, v in m.items() if k != "images"})
    data = dict(chat, messages=clean)
    tmp = base + ".json.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, base + ".json")
    lines = [f"# {chat['title']}", f"Chat from {chat['started']} (mode: {chat.get('mode', '')})", ""]
    for m in clean:
        who = "You" if m["role"] == "user" else "Archie"
        text = m.get("display") or m["content"]
        lines += [f"**{who}:** {text}", ""]
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def list_chats(folder):
    """Newest first: [{"id", "title", "started", "mode", "text"}]."""
    out = []
    if not os.path.isdir(folder):
        return out
    for fn in os.listdir(folder):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, fn), encoding="utf-8") as f:
                c = json.load(f)
        except (OSError, ValueError):
            continue
        c["text"] = " ".join((m.get("display") or m.get("content", "")) for m in c.get("messages", []))
        out.append(c)
    out.sort(key=lambda c: c.get("id", ""), reverse=True)
    return out


def delete_chat(folder, chat_id):
    for ext in (".json", ".md"):
        try:
            os.remove(os.path.join(folder, chat_id + ext))
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Friendly model names
# ---------------------------------------------------------------------------

MODEL_NAMES_STARTER = """\
# Friendly names for your models, shown in Archie's Model menu.
# Format:   real model name = the name you want to see
# Edit anytime (right-click the owl > Edit model names). Lines starting with # are ignored.

qwen2.5:7b = Main brain
qwen2.5-coder:7b = Coder
gemma3:4b = Vision (reads images)
qwen2.5:1.5b = Starter (small)
llama3.1:8b = Llama (second opinion)
"""


def load_model_names(path):
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(MODEL_NAMES_STARTER)
        except OSError:
            pass
    names = {}
    for line in read_small_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        real, nice = (s.strip() for s in line.split("=", 1))
        if real and nice:
            names[real] = nice
    return names


# ---------------------------------------------------------------------------
# Offline Wikipedia (Kiwix .zim files)
# ---------------------------------------------------------------------------

STOPWORDS = set("""a about an and are as at be been but by can could did do does for from
had has have how i if in into is it its me my of on or our please so tell than that the
their them then there these they this to us was we were what when where which who whom
why will with would you your explain describe give show more some any also just like
between vs versus""".split())


def search_terms(question):
    import re
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'\-]*", question)
    kept = [w for w in words if w.lower() not in STOPWORDS and len(w) > 1]
    return kept or words


def html_to_paragraphs(html_text):
    """Pull readable paragraphs (and section headings) out of a Wikipedia page."""
    from html.parser import HTMLParser

    class P(HTMLParser):
        SKIP = {"script", "style", "table", "sup", "figure", "figcaption", "math", "nav"}
        KEEP = {"p", "li", "h2", "h3", "dd"}
        VOID = {"br", "img", "meta", "link", "hr", "input", "wbr", "source", "col", "area"}

        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.skip_depth = 0   # >0 while inside something we're ignoring
            self.cur = None
            self.out = []

        def handle_starttag(self, tag, attrs):
            if tag in self.VOID:
                if tag == "br" and self.cur is not None:
                    self.cur[1].append(" ")
                return
            if self.skip_depth:
                self.skip_depth += 1
                return
            cls = dict(attrs).get("class") or ""
            if tag in self.SKIP or "reference" in cls or "mw-ref" in cls or "infobox" in cls:
                self.skip_depth = 1
            elif tag in self.KEEP:
                self.cur = [tag, []]

        def handle_endtag(self, tag):
            if tag in self.VOID:
                return
            if self.skip_depth:
                self.skip_depth -= 1
                return
            if self.cur and tag == self.cur[0]:
                text = " ".join("".join(self.cur[1]).split())
                if text:
                    self.out.append(("== " + text + " ==") if tag in ("h2", "h3") else text)
                self.cur = None

        def handle_data(self, data):
            if self.cur is not None and not self.skip_depth:
                self.cur[1].append(data)

    p = P()
    try:
        p.feed(html_text)
    except Exception:
        pass
    return p.out


class WikiLibrary:
    """Searches the Wikipedia .zim file(s) in the Wikipedia folder."""

    def __init__(self, folder):
        self.folder = folder
        self.lock = threading.Lock()
        self._archive = None
        self._path = None
        os.makedirs(folder, exist_ok=True)

    def zim_files(self):
        try:
            files = [os.path.join(self.folder, f) for f in os.listdir(self.folder)
                     if f.lower().endswith(".zim")]
        except OSError:
            return []
        return sorted(files, key=os.path.getsize, reverse=True)

    def _open(self):
        files = self.zim_files()
        if not files:
            raise ArchieError("There's no Wikipedia file yet. Double-click Get Wikipedia.bat "
                              "in the Archie folder (and let the download finish).")
        try:
            from libzim.reader import Archive
        except ImportError:
            raise ArchieError("Wikipedia search needs one extra piece. Double-click "
                              "Install Extras.bat, then restart Archie.")
        if self._path != files[0]:
            try:
                self._archive = Archive(files[0])
            except Exception as e:
                raise ArchieError(f"I couldn't open {os.path.basename(files[0])}. If it's "
                                  f"still downloading, wait for it to finish. ({e})")
            self._path = files[0]
        return self._archive

    def describe(self):
        files = self.zim_files()
        if not files:
            return None
        gb = os.path.getsize(files[0]) / 1e9
        return f"{os.path.basename(files[0])} ({gb:.1f} GB)"

    def _article(self, zim, path):
        entry = zim.get_entry_by_path(path)
        for _ in range(5):
            if not entry.is_redirect:
                break
            entry = entry.get_redirect_entry()
        item = entry.get_item()
        if not item.mimetype.startswith("text/html"):
            return None, []
        html_text = bytes(item.content).decode("utf-8", "replace")
        return entry.title, html_to_paragraphs(html_text)

    def random_article(self, tries=25, min_chars=400, min_first=120):
        """(title, first paragraph) of a random real article, for the brief."""
        with self.lock:
            zim = self._open()
            for _ in range(tries):
                try:
                    entry = zim.get_random_entry()
                    title, paras = self._article(zim, entry.path)
                except Exception:
                    continue
                body = [p for p in paras if not p.startswith("==")]
                if not title or not body or sum(len(p) for p in body) < min_chars:
                    continue
                if title.lower().startswith(("list of", "index of")) or len(body[0]) < min_first:
                    continue
                first = body[0]
                if len(first) > 420:
                    cut = first.rfind(". ", 0, 420)
                    first = first[:cut + 1] if cut > 150 else first[:420] + "..."
                return title, first
        return None

    def search(self, question, k=3, chars_per_article=1800):
        """Return [(title, excerpt)] for the articles that best match the question."""
        with self.lock:
            zim = self._open()
            from libzim.search import Query, Searcher
            terms = search_terms(question)[:8]
            scores = {}

            def add(paths, weight):
                for rank, p in enumerate(paths):
                    scores[p] = scores.get(p, 0) + weight / (1 + 0.3 * rank)

            def fulltext(q, n):
                try:
                    return list(Searcher(zim).search(Query().set_query(q)).getResults(0, n))
                except Exception:
                    return []

            def titles(q, n):
                try:
                    from libzim.suggestion import SuggestionSearcher
                    return list(SuggestionSearcher(zim).suggest(q).getResults(0, n))
                except Exception:
                    return []

            # Whole question first, then each keyword on its own. Articles that
            # match many keywords (in the title or the text) rise to the top.
            add(fulltext(" ".join(terms), k + 3), 4)
            add(titles(" ".join(terms), 2), 4)
            for t in terms:
                add(titles(t, 2), 2.5 if t[:1].isupper() else 2)
                add(fulltext(t, 5), 1)
            paths = sorted(scores, key=scores.get, reverse=True)
            if not paths and not (zim.has_fulltext_index or zim.has_title_index):
                raise ArchieError("This Wikipedia file has no search index, so I can't search it.")
            lowered = [t.lower() for t in terms]
            results, seen = [], set()
            for path in paths:
                if len(results) >= k:
                    break
                try:
                    title, paras = self._article(zim, path)
                except Exception:
                    continue
                if not title or title in seen or not paras:
                    continue
                seen.add(title)
                body = [p for p in paras if not p.startswith("==")]
                picked = body[:2]  # the intro says what the thing is
                scored = sorted(body[2:], key=lambda p: -sum(p.lower().count(t) for t in lowered))
                for p in scored[:4]:
                    if sum(p.lower().count(t) for t in lowered):
                        picked.append(p)
                text, total = [], 0
                for p in picked:
                    if total + len(p) > chars_per_article and text:
                        break
                    text.append(p)
                    total += len(p)
                results.append((title, "\n".join(text)[:chars_per_article + 400]))
            return results
