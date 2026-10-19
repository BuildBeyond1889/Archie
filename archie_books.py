"""
archie_books.py - books in your Notes folder, chapter by chapter.

  * Reads EPUB files (plain Python, nothing to install).
  * Splits a book into parts/books and chapters by finding the headings
    ("PART III", "BOOK ONE: 1805", "CHAPTER V", "Chapter 12", "EPILOGUE").
  * Understands requests like "quiz me on Crime and Punishment part 3 chapter 5",
    "war and peace book 2 chapters 1-4" or "the first epilogue", and hands back
    exactly that text so Archie can quiz you on what you've actually read.
"""

import html
import os
import posixpath
import re
import threading
import urllib.parse
import zipfile
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

BOOK_EXT = {".epub", ".txt", ".md", ".pdf", ".docx"}
LIMIT = 20000          # characters of book text sent with each question (~5k tokens)

WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen", "twenty"]
ORDINALS = ["zeroth", "first", "second", "third", "fourth", "fifth", "sixth", "seventh",
            "eighth", "ninth", "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth",
            "fifteenth", "sixteenth", "seventeenth", "eighteenth", "nineteenth", "twentieth"]
_NUM = r"(?:\d{1,3}|[ivxlc]{1,7}|" + "|".join(WORDS[1:] + ORDINALS[1:]) + r")"
STOP = {"the", "and", "of", "a", "an", "in", "on", "to", "by", "for", "with", "or",
        "novel", "edition", "vol", "volume", "complete", "ebook", "gutenberg", "project"}


def to_int(s):
    """'12' / 'XII' / 'twelve' / 'twelfth' -> 12 (None if it isn't a number)."""
    if s is None:
        return None
    s = s.strip().lower().rstrip(".")
    if s.isdigit():
        return int(s)
    if s in WORDS:
        return WORDS.index(s)
    if s in ORDINALS:
        return ORDINALS.index(s)
    vals = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    if s and all(ch in vals for ch in s):
        total = 0
        for i, ch in enumerate(s):
            v = vals[ch]
            total += -v if i + 1 < len(s) and vals[s[i + 1]] > v else v
        return total
    return None


def roman(n):
    out = ""
    for v, r in ((100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
                 (5, "V"), (4, "IV"), (1, "I")):
        while n >= v:
            out += r
            n -= v
    return out


# ---------------------------------------------------------------------------
# EPUB -> text
# ---------------------------------------------------------------------------

class _HtmlText(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "blockquote", "section", "pre", "hr"}
    HEAD = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head"):
            self.skip += 1
        elif tag in self.HEAD:
            self.out.append("\n\n")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.HEAD:
            self.out.append("\n\n")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(re.sub(r"\s+", " ", data))

    def text(self):
        t = "".join(self.out)
        t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
        return re.sub(r"\n{3,}", "\n\n", t).strip()


def _epub_opf(z):
    root = ET.fromstring(z.read("META-INF/container.xml"))
    for el in root.iter():
        if el.tag.endswith("rootfile") and el.get("full-path"):
            return el.get("full-path")
    raise ValueError("no rootfile")


def epub_title(path):
    try:
        with zipfile.ZipFile(path) as z:
            opf = ET.fromstring(z.read(_epub_opf(z)))
        for el in opf.iter():
            if el.tag.endswith("}title") and (el.text or "").strip():
                return el.text.strip()
    except Exception:
        pass
    return None


def epub_text(path):
    """All the readable text of an EPUB, in reading order, headings on their own lines."""
    with zipfile.ZipFile(path) as z:
        opf_path = _epub_opf(z)
        base = posixpath.dirname(opf_path)
        opf = ET.fromstring(z.read(opf_path))
        items, spine = {}, []
        for el in opf.iter():
            if el.tag.endswith("}item"):
                items[el.get("id")] = el.get("href")
            elif el.tag.endswith("}itemref"):
                spine.append(el.get("idref"))
        names = set(z.namelist())
        if "META-INF/encryption.xml" in names:
            enc = z.read("META-INF/encryption.xml").decode("utf-8", "ignore")
            if re.search(r'URI="[^"]+\.x?html?"', enc, re.I):
                raise ValueError("this EPUB is copy-protected (DRM), so its text can't be read")
        parts = []
        for idref in spine:
            href = items.get(idref)
            if not href:
                continue
            name = posixpath.normpath(posixpath.join(base, urllib.parse.unquote(href)))
            if name not in names:
                continue
            raw = z.read(name)
            try:
                doc = raw.decode("utf-8")
            except UnicodeDecodeError:
                doc = raw.decode("latin-1")
            p = _HtmlText()
            try:
                p.feed(doc)
            except Exception:
                continue
            t = p.text()
            if t:
                parts.append(t)
    return html.unescape("\n\n".join(parts))


# ---------------------------------------------------------------------------
# Finding parts and chapters
# ---------------------------------------------------------------------------

PART_RE = re.compile(r"^(?P<kind>part|book|volume)\s+(?:the\s+)?(?P<n>" + _NUM + r")\b[\s.:,—–-]*(?P<rest>.{0,60})$", re.I)
CHAP_RE = re.compile(r"^(?:chapter|chap\.)\s+(?P<n>" + _NUM + r")\b[\s.:,—–-]*(?P<rest>.{0,80})$", re.I)
EPI_RE = re.compile(r"^(?P<which>first|second|third|1st|2nd|3rd)?\s*epilogue\b[\s.:—–-]*(?P<rest>.{0,60})$", re.I)
BARE_RE = re.compile(r"^(?P<n>[IVXLC]{1,7})\.?$")      # a chapter number alone on a line


class Book:
    def __init__(self, path, title, text):
        self.path, self.title = path, title
        self.text = self._trim(text)
        self.sections = self._split(self.text)

    @staticmethod
    def _trim(text):
        s = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG[^\n]*", text, re.I)
        e = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text, re.I)
        return text[s.end() if s else 0:e.start() if e else len(text)]

    def _split(self, text):
        heads = []                  # (pos, end_of_line, kind, number, label)
        use_bare = not re.search(r"^\s*(chapter|chap\.)\s+" + _NUM + r"\b", text, re.I | re.M)
        pos = 0
        for line in text.splitlines(keepends=True):
            s = line.strip()
            if s and len(s) <= 90:
                m = PART_RE.match(s)
                if m and to_int(m.group("n")):
                    n = to_int(m.group("n"))
                    heads.append((pos, pos + len(line), "part", n, s))
                else:
                    m = EPI_RE.match(s)
                    if m and (not m.group("rest") or len(s) < 40):
                        w = (m.group("which") or "").lower()
                        n = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3}.get(w, 1)
                        heads.append((pos, pos + len(line), "epilogue", n, s))
                    else:
                        m = CHAP_RE.match(s) or (BARE_RE.match(s) if use_bare else None)
                        if m and to_int(m.group("n")):
                            heads.append((pos, pos + len(line), "chapter", to_int(m.group("n")), s))
            pos += len(line)

        sections, part, part_label = {}, None, None
        for i, (p, e, kind, n, label) in enumerate(heads):
            nxt = heads[i + 1][0] if i + 1 < len(heads) else len(text)
            if kind == "part":
                part, part_label = ("part", n), label
            elif kind == "epilogue":
                part, part_label = ("epilogue", n), label
            if kind == "chapter" or nxt - e > 1500:     # a part with text straight after it
                ch = n if kind == "chapter" else 0
                key = (part, ch)
                sec = {"part": part, "part_label": part_label, "chapter": ch,
                       "label": label if kind == "chapter" else "", "start": e, "end": nxt}
                old = sections.get(key)
                # the table of contents also lists every heading: keep the real (longest) one
                if old is None or (sec["end"] - sec["start"]) > (old["end"] - old["start"]):
                    sections[key] = sec
        return sorted(sections.values(), key=lambda s: s["start"])

    # --- describing ----------------------------------------------------------

    def parts(self):
        seen = []
        for s in self.sections:
            if s["part"] not in seen:
                seen.append(s["part"])
        return seen

    def part_name(self, part):
        if part is None:
            return ""
        kind, n = part
        if kind == "epilogue":
            eps = [p for p in self.parts() if p and p[0] == "epilogue"]
            return "Epilogue" if len(eps) == 1 else f"{ORDINALS[n].title()} Epilogue"
        word = next((s["part_label"].split()[0].title() for s in self.sections
                     if s["part"] == part and s["part_label"]), "Part")
        return f"{word} {roman(n)}"

    def outline(self):
        """'Part I: 7 chapters · Part II: 7 chapters ...' for messages."""
        if not self.sections:
            return "no chapters found"
        out = []
        for part in self.parts():
            n = len([s for s in self.sections if s["part"] == part and s["chapter"]])
            name = self.part_name(part) or "Chapters"
            out.append(f"{name}: {n} chapter{'s' if n != 1 else ''}" if n else name)
        return " · ".join(out)

    # --- finding what you asked for ---------------------------------------------

    def find(self, ref, current_part=None):
        """Returns (sections, label, note) for a parsed reference."""
        parts = self.parts()
        has_parts = any(p is not None for p in parts)
        note = ""
        if ref.get("epilogue"):
            part = ("epilogue", ref["epilogue"])
            if part not in parts:
                eps = [p for p in parts if p and p[0] == "epilogue"]
                part = eps[0] if len(eps) == 1 and ref["epilogue"] == 1 else None
            if part is None:
                return [], "", f"I couldn't find that epilogue. This book has: {self.outline()}."
        elif ref.get("part"):
            part = ("part", ref["part"])
            if part not in parts:
                return [], "", f"I couldn't find {self._kind_word()} {ref['part']}. This book has: {self.outline()}."
        elif has_parts:
            part = current_part if current_part in parts else next(p for p in parts if p is not None)
            if ref.get("chapter") and len([p for p in parts if p is not None]) > 1 and current_part not in parts:
                note = (f"Chapter numbers start over in each {self._kind_word()}, so I went with "
                        f"{self.part_name(part)}. Say e.g. \"{self._kind_word()} 2 chapter "
                        f"{ref['chapter']}\" for another one.")
        else:
            part = None
        secs = [s for s in self.sections if s["part"] == part]
        c0 = ref.get("chapter")
        if c0:
            c1 = ref.get("chapter_to") or c0
            if c1 < c0:
                c0, c1 = c1, c0
            secs = [s for s in secs if c0 <= s["chapter"] <= c1]
            if not secs:
                where = f" of {self.part_name(part)}" if part else ""
                have = len([s for s in self.sections if s["part"] == part and s["chapter"]])
                return [], "", f"There's no chapter {c0}{where}; it has {have} chapters."
            ch = f"Chapter {roman(c0)}" if c0 == c1 else f"Chapters {roman(c0)}–{roman(c1)}"
            label = f"{self.part_name(part)}, {ch}" if part else ch
        else:
            label = self.part_name(part) or "the whole book"
        return secs, label, note

    def _kind_word(self):
        for s in self.sections:
            if s["part_label"] and s["part"] and s["part"][0] == "part":
                return s["part_label"].split()[0].lower()
        return "part"

    def text_of(self, secs, limit=LIMIT):
        """The text of those sections; if it's too long, evenly spread excerpts."""
        chunks = []
        for s in secs:
            head = s["label"] or self.part_name(s["part"])
            body = self.text[s["start"]:s["end"]].strip()
            chunks.append(f"[{head}]\n{body}" if head else body)
        full = "\n\n".join(chunks)
        if len(full) <= limit:
            return full, False
        n = 8
        size = limit // n
        step = (len(full) - size) / (n - 1)
        pieces = []
        for i in range(n):
            a = int(i * step)
            a = full.rfind("\n", 0, a) + 1 if full.rfind("\n", 0, a) > a - 600 else a
            pieces.append(full[a:a + size].strip())
        return "\n\n[...]\n\n".join(pieces), True


# ---------------------------------------------------------------------------
# Understanding "part 3 chapter 5"
# ---------------------------------------------------------------------------

_CH = r"(?:chapters?|chaps?\.?|ch\.?)"
_REF_PART = re.compile(r"\b(?:part|book|volume)(?:\s*(?=\d)|\s+)(?P<n>" + _NUM + r")\b", re.I)
_REF_PART2 = re.compile(r"\b(?P<n>" + "|".join(ORDINALS[1:]) + r"|\d{1,2}(?:st|nd|rd|th))\s+(?:part|book|volume)\b", re.I)
_REF_CHAP = re.compile(r"\b" + _CH + r"(?:\s*(?=\d)|\s+)(?P<a>" + _NUM + r")\b"
                       r"(?:\s*(?:-|–|—|to|through|thru|and|&)\s*(?:" + _CH + r"\s*)?(?P<b>" + _NUM + r")\b)?", re.I)
_REF_EPI = re.compile(r"\b(?:(?P<w>first|second|1st|2nd)\s+)?epilogue\b", re.I)


def parse_ref(question):
    """{'part', 'chapter', 'chapter_to', 'epilogue'} or None if no chapter is mentioned."""
    ref = {}
    m = _REF_CHAP.search(question)
    if m and to_int(m.group("a")):
        ref["chapter"] = to_int(m.group("a"))
        if m.group("b") and to_int(m.group("b")):
            ref["chapter_to"] = to_int(m.group("b"))
    for m in _REF_PART.finditer(question):
        n = m.group("n")
        # "the book I read..." - a lone I only counts as a number before a comma,
        # the end, or the word chapter
        if n.lower() == "i" and not (n == "I" and re.match(r"\s*(?:$|[,.:;]|ch)", question[m.end():], re.I)):
            continue
        if to_int(n):
            ref["part"] = to_int(n)
            break
    if "part" not in ref:
        m = _REF_PART2.search(question)
        if m:
            n = m.group("n").lower()
            ref["part"] = int(n[:-2]) if n[0].isdigit() else to_int(n)
    m = _REF_EPI.search(question)
    if m:
        ref["epilogue"] = 2 if (m.group("w") or "").lower() in ("second", "2nd") else 1
        ref.pop("part", None)
    return ref or None


def _words(s):
    s = s.lower().replace("&", " and ").replace("’", "'")
    return [w for w in re.findall(r"[a-z0-9']+", s) if w not in STOP]


# ---------------------------------------------------------------------------
# The shelf: every book in the Notes folder
# ---------------------------------------------------------------------------

class Library:
    def __init__(self, folder, read_text):
        self.folder = folder
        self.read_text = read_text     # archie_brain.read_text (PDF / Word / text)
        self._books = {}               # path -> (mtime, Book)
        self._titles = {}              # path -> (mtime, title)
        self._lock = threading.Lock()

    def files(self):
        out = []
        for dp, dns, fns in os.walk(self.folder):
            dns[:] = [d for d in dns if not d.startswith(".")]
            for fn in fns:
                if os.path.splitext(fn)[1].lower() in BOOK_EXT:
                    out.append(os.path.join(dp, fn))
        return out

    def title(self, path):
        try:
            mt = os.path.getmtime(path)
        except OSError:
            return None
        hit = self._titles.get(path)
        if hit and hit[0] == mt:
            return hit[1]
        ext = os.path.splitext(path)[1].lower()
        t = None
        if ext == ".epub":
            t = epub_title(path)
        elif ext in (".txt", ".md"):
            try:
                with open(path, "rb") as f:
                    head = f.read(4000).decode("utf-8", "ignore")
                m = re.search(r"^\s*Title:\s*(.+?)\s*$", head, re.M)
                t = m.group(1) if m else None
            except OSError:
                pass
        if not t:
            t = os.path.splitext(os.path.basename(path))[0]
            t = re.split(r"\s+--\s+|\s+-\s+|_-_", t)[0]
            t = re.sub(r"[\(\[].*?[\)\]]", "", t).replace("_", " ").strip() or t
        self._titles[path] = (mt, t)
        return t

    def is_novel_like(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext == ".epub":
            return True
        if ext in (".txt", ".md"):
            return os.path.getsize(path) > 150_000
        return False

    def match(self, question):
        """Book files whose title is named in the question, best match first."""
        q = set(_words(question))
        scored = []
        for path in self.files():
            tw = set(_words(self.title(path) or ""))
            if not tw:
                continue
            hit = len(tw & q)
            if hit == len(tw) or (hit >= 2 and hit / len(tw) >= 0.6):
                scored.append((hit / len(tw), hit, path))
        scored.sort(reverse=True)
        return [p for _, _, p in scored]

    def load(self, path):
        mt = os.path.getmtime(path)
        with self._lock:
            hit = self._books.get(path)
            if hit and hit[0] == mt:
                return hit[1]
        ext = os.path.splitext(path)[1].lower()
        text = epub_text(path) if ext == ".epub" else self.read_text(path)
        book = Book(path, self.title(path), text)
        with self._lock:
            self._books[path] = (mt, book)
        return book

    def shelf(self):
        """Titles of the books Archie can quiz you on."""
        return sorted({self.title(p) for p in self.files() if self.is_novel_like(p)})

    def lookup(self, question, ref, current=None):
        """Find the book + chapter(s) a question asks about.
        Returns a context dict, or a string explaining what went wrong,
        or None if the question isn't about a book in Notes."""
        paths = self.match(question)
        if paths:
            path = paths[0]
        elif current:
            path = current["path"]
        else:
            novels = [p for p in self.files() if self.is_novel_like(p)]
            if len(novels) == 1:
                path = novels[0]
            elif re.search(r"\b(quiz|test me|read|reading)\b", question, re.I):
                if not novels:
                    return ("I don't see any books in your Notes folder yet. Put the EPUB (or a "
                            "PDF / .txt) in Notes, then ask again.")
                return ("Which book? In your Notes I have: " + "; ".join(self.shelf()[:8]) +
                        ". Say it like: quiz me on <title> part 1 chapter 3.")
            else:
                return None
        try:
            book = self.load(path)
        except Exception as e:
            return f"I couldn't open {os.path.basename(path)}: {e}"
        if not book.sections:
            return (f"I opened {book.title} but couldn't find its chapter headings, so I can't "
                    "pick out one chapter. (Asking with Notes on still works for general questions.)")
        cur_part = current.get("part") if current and current.get("path") == path else None
        secs, label, note = book.find(ref, cur_part)
        if not secs:
            return note
        text, sampled = book.text_of(secs)
        return {"path": path, "title": book.title, "label": label, "part": secs[0]["part"],
                "text": text, "sampled": sampled, "note": note}
