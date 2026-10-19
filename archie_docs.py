"""Look it up before answering: the offline programming library in Archie's vault.

The vault (D:\\Archie\\Vault\\zim) holds Kiwix .zim files: the official docs for each language (DevDocs packs),
Stack Overflow, and Stack Exchange sites (Arduino, game development, code review...). Before the Workshop
answers, hints or checks, it searches the ones that fit the language, pulls out the part of the page that
matters (a docs section, or a question and its best answer), hands those to the coding model, and shows
you which pages it used so you can open them yourself.

Everything here reads files on this PC. Nothing goes online.
"""
import html as htmllib
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from html.parser import HTMLParser

# What to search for each language: (file name starts with, label, kind, only when the question mentions...).
# kind "docs" is a reference manual; "qa" is a Stack Exchange site (question + answers).
SOURCES = {
    "python": [("devdocs_en_python", "Python docs", "docs", None),
               ("devdocs_en_pygame", "pygame docs", "docs", ("pygame",)),
               ("devdocs_en_numpy", "NumPy docs", "docs", ("numpy", "np.")),
               ("devdocs_en_pandas", "pandas docs", "docs", ("pandas", "dataframe", "pd.")),
               ("devdocs_en_matplotlib", "Matplotlib docs", "docs", ("matplotlib", "plt.", "pyplot")),
               ("devdocs_en_flask", "Flask docs", "docs", ("flask",)),
               ("devdocs_en_fastapi", "FastAPI docs", "docs", ("fastapi",)),
               ("devdocs_en_sqlite", "SQLite docs", "docs", ("sqlite", "sql")),
               ("devdocs_en_pytorch", "PyTorch docs", "docs", ("torch", "pytorch")),
               ("devdocs_en_scikit-learn", "scikit-learn docs", "docs", ("sklearn", "scikit")),
               ("stackoverflow.com", "Stack Overflow", "qa", None)],
    "web": [("devdocs_en_html", "HTML docs", "docs", None),
            ("devdocs_en_css", "CSS docs", "docs", None),
            ("devdocs_en_javascript", "JavaScript docs", "docs", None),
            ("devdocs_en_dom", "Web page (DOM) docs", "docs", None),
            ("devdocs_en_svg", "SVG docs", "docs", ("svg",)),
            ("devdocs_en_http", "HTTP docs", "docs", ("fetch", "http", "request", "header")),
            ("devdocs_en_threejs", "three.js docs", "docs", ("three", "threejs")),
            ("devdocs_en_leaflet", "Leaflet docs", "docs", ("leaflet", "map")),
            ("devdocs_en_react", "React docs", "docs", ("react", "jsx", "usestate")),
            ("stackoverflow.com", "Stack Overflow", "qa", None)],
    "node": [("devdocs_en_node", "Node.js docs", "docs", None),
             ("devdocs_en_javascript", "JavaScript docs", "docs", None),
             ("devdocs_en_typescript", "TypeScript docs", "docs", ("typescript",)),
             ("stackoverflow.com", "Stack Overflow", "qa", None)],
    "java": [("devdocs_en_openjdk", "Java docs", "docs", None),
             ("stackoverflow.com", "Stack Overflow", "qa", None)],
    "c": [("devdocs_en_c", "C docs", "docs", None),
          ("devdocs_en_gcc", "GCC docs", "docs", ("gcc", "warning", "compile", "flag")),
          ("devdocs_en_gnu-make", "Make docs", "docs", ("make", "makefile")),
          ("devdocs_en_man", "Linux man pages", "docs", ("man", "posix", "unistd")),
          ("stackoverflow.com", "Stack Overflow", "qa", None)],
    "cpp": [("devdocs_en_cpp", "C++ docs", "docs", None),
            ("devdocs_en_cmake", "CMake docs", "docs", ("cmake",)),
            ("devdocs_en_gcc", "GCC docs", "docs", ("gcc", "g++", "warning", "flag")),
            ("stackoverflow.com", "Stack Overflow", "qa", None)],
    "csharp": [("stackoverflow.com", "Stack Overflow", "qa", None),
               ("gamedev.stackexchange.com", "Game Development Q&A", "qa", ("unity", "game", "godot"))],
    "gdscript": [("devdocs_en_godot", "Godot docs", "docs", None),
                 ("gamedev.stackexchange.com", "Game Development Q&A", "qa", None),
                 ("stackoverflow.com", "Stack Overflow", "qa", None)],
    "arduino": [("arduino.stackexchange.com", "Arduino Q&A", "qa", None),
                ("devdocs_en_cpp", "C++ docs", "docs", None),
                ("electronics.stackexchange.com", "Electronics Q&A", "qa", ("voltage", "resistor", "current", "wiring", "sensor", "pin", "led", "motor")),
                ("raspberrypi.stackexchange.com", "Raspberry Pi Q&A", "qa", ("raspberry", "pi ")),
                ("iot.stackexchange.com", "Internet of Things Q&A", "qa", ("mqtt", "wifi", "esp8266", "esp32", "iot")),
                ("stackoverflow.com", "Stack Overflow", "qa", None)],
}
SOURCES["gamedev"] = [("gamedev.stackexchange.com", "Game Development Q&A", "qa", None)]     # the dev coach, any engine
# words that help Stack Overflow find the right language
SO_TAG = {"python": "python", "web": "javascript", "node": "node.js", "java": "java", "c": "c", "cpp": "c++",
          "csharp": "c#", "gdscript": "godot", "arduino": "arduino"}
NICE = {"python": "Python", "web": "Web", "node": "Node.js", "java": "Java", "c": "C", "cpp": "C++", "csharp": "C#",
        "gdscript": "Godot", "arduino": "Arduino", "gamedev": "Game dev"}

STOP = set("""a about above after again all also am an and any are as at be because been before being below between both but by
can cant could did do does doing dont down during each else even every few for from further get gets got had has have having
he her here hers him his how i if in into is isnt it its itself just let lets like make makes me more most my need no nor not
now of off on once only or other our out over own please same she should so some such than that the their them then there
these they this those through to too try trying under until up us use used using very want was way we were what when where
which while who why will with would you your yours step task idea learner code program write change line file their
explain show work works working wrong error errors problem thing things something one two first next new go see""".split())

LIB_HINT = ("Reference pages from the offline library on this PC are below. Use them when they help and prefer them over memory. "
            "When you rely on one, name it in square brackets like [Python docs: Data Structures]. Never invent a page.")


def lang_key(lang):
    """Workshop/course language name -> a key in SOURCES ('' if unknown)."""
    s = (lang or "").lower()
    if s == "gamedev":
        return "gamedev"
    if "gdscript" in s or "godot" in s:
        return "gdscript"
    if "arduino" in s:
        return "arduino"
    if "c#" in s or "csharp" in s or "dotnet" in s:
        return "csharp"
    if "c++" in s or "cpp" in s:
        return "cpp"
    if "node" in s:
        return "node"
    if "web" in s or "html" in s or "javascript" in s or s == "js":
        return "web"
    if "java" in s:
        return "java"
    if "python" in s:
        return "python"
    if s.strip() in ("c", "gcc"):
        return "c"
    return ""


def terms_of(text, limit=8):
    """The words worth searching for: names from code (move_and_slide, IndexError, printf) first, then plain keywords."""
    text = text or ""
    text = re.sub(r"[A-Za-z]:\\[^\s\"']+|/[\w./-]+\.\w+", " ", text)          # file paths
    text = re.sub(r"\bline \d+\b|\b0x[0-9a-f]+\b|\b\d+\b", " ", text, flags=re.I)
    code = re.findall(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", text)
    out, seen = [], set()

    def add(w):
        k = w.lower()
        if k in seen or k in STOP or len(k) < 2:
            return
        seen.add(k)
        out.append(w)
    for w in code:                                   # code-looking names first
        if "_" in w or "." in w or re.search(r"[a-z][A-Z]", w) or re.match(r"[A-Z][a-z]+(Error|Exception)$", w):
            add(w.split(".")[-1] if w.count(".") > 1 else w)
    for w in re.findall(r"[A-Za-z][A-Za-z0-9+#']*", text):
        add(w)
    return out[:limit]


def _is_name(w):
    """Looks like something from code: move_and_slide, getElementById, IndexError, std::vector."""
    return "_" in w or "::" in w or bool(re.search(r"[a-z][A-Z]|^[A-Z][a-z]+[A-Z]", w))


# ----------------------------------------------------------------------------- reading pages
class _Blocks(HTMLParser):
    """HTML -> [(kind, text)] with kind h1/h2/h3/p/li/code/dt. Keeps code blocks (docs examples matter)."""
    SKIP = {"script", "style", "nav", "header", "footer", "devdocs-navbar", "noscript", "svg", "button", "form"}
    TEXT = {"p": "p", "li": "li", "h1": "h1", "h2": "h2", "h3": "h3", "h4": "h3", "dt": "dt", "dd": "p", "blockquote": "p", "td": "p"}
    VOID = {"br", "img", "meta", "link", "hr", "input", "wbr", "source", "col", "area"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.cur, self.pre = [], 0, None, 0

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            if tag == "br" and self.cur is not None:
                self.cur[1].append("\n" if self.pre else " ")
            return
        if self.skip:
            self.skip += 1
            return
        if tag in self.SKIP:
            self.skip = 1
            return
        if tag == "pre":
            self._close()
            self.pre += 1
            self.cur = ["code", []]
        elif not self.pre and tag in self.TEXT:
            self._close()
            self.cur = [self.TEXT[tag], []]

    def handle_endtag(self, tag):
        if tag in self.VOID:
            return
        if self.skip:
            self.skip -= 1
            return
        if tag == "pre" and self.pre:
            self.pre -= 1
            if not self.pre:
                self._close()
        elif not self.pre and tag in self.TEXT and self.cur and self.cur[0] == self.TEXT[tag]:
            self._close()

    def _close(self):
        if self.cur:
            raw = "".join(self.cur[1])
            t = raw.strip("\n").rstrip() if self.cur[0] == "code" else " ".join(raw.split())
            if t:
                self.out.append((self.cur[0], t))
        self.cur = None

    def handle_data(self, data):
        if self.cur is not None and not self.skip:
            self.cur[1].append(data)
        elif not self.skip and not self.pre and data.strip() and self.cur is None:
            self.cur = ["p", [data]]          # loose text between blocks


def blocks_of(html_text):
    p = _Blocks()
    try:
        p.feed(html_text)
        p._close()
    except Exception:      # noqa: BLE001 - a broken page gives what it gave
        pass
    return p.out


def _hits(text, words):
    t = text.lower()
    return sum(t.count(w) for w in words)


def _page_start(html_text):
    i = html_text.find('class="_page')
    return html_text[html_text.rfind("<", 0, i):] if i > 0 else html_text


def docs_excerpt(html_text, words, names=(), limit=1500, info=None):
    """The part of a docs page that answers the question: the page's intro, then the paragraph that matches best
    (exact names like move_and_slide count most) with the heading above it and what follows it."""
    B = blocks_of(_page_start(html_text))
    if not B:
        return ""
    names = [n.lower() for n in names]
    stems = sorted({w[:-1] if len(w) > 4 and w.endswith("s") else w for w in words})
    page = " ".join(t for k, t in B).lower()
    weight = {w: 1.0 / (1 + page.count(w) / 8.0) for w in stems}      # words rare on this page say more

    def score(i):
        kind, text = B[i]
        t = text.lower()
        s = 6 * sum(weight[w] * min(t.count(w), 3) for w in stems) + 5 * sum(t.count(n) for n in names)
        if kind == "code":
            s *= 0.6
        if len(text) < 30 and kind not in ("dt", "h2", "h3"):
            s *= 0.3            # table cells and lists of names say little
        if kind in ("h2", "h3", "dt") and s:
            s = 3 * s + 2
            if any(re.search(r"(^|[^\w])%s([^\w]|$)" % re.escape(n), t) for n in names):
                s += 25         # the heading for the exact function or class
        if t.startswith("see also"):
            s = 0
        return s
    scores = [score(i) for i in range(len(B))]
    anchor = max(range(len(B)), key=lambda i: scores[i])
    if info is not None:        # is this the page that defines the name (its own heading), not one that mentions it?
        info["defines"] = B[anchor][0] in ("h1", "h2", "h3", "dt") and any(n in B[anchor][1].lower() for n in names) or \
            any(n == B[0][1].lower().strip() for n in names)
    intro, total = [], 0
    for kind, text in B:
        if kind == "p" and len(text) > 40 and not re.match(r"(\*|This feature (is well established|is not Baseline|has been)|Baseline|Limited availability|Deprecated:|Some parts of this feature|Note: This feature|Secure context:|Experimental:|Non-standard:)", text):
            intro.append(text if len(text) < 360 else text[:360].rsplit(" ", 1)[0] + "...")
            break
    picked = []
    if scores[anchor] > 0:
        head = next((j for j in range(anchor, -1, -1) if B[j][0] in ("h1", "h2", "h3")), None)
        start = anchor
        while B[anchor][0] == "p" and start > 0 and start - 1 != head and B[start - 1][0] in ("dt", "code") and anchor - start < 2:
            start -= 1          # the signature just above a description
        if head is not None and head < start and B[head][0] != "h1":
            picked.append(B[head])
        picked += B[start:start + 14]
    out = []
    for text in intro:
        out.append(text)
        total += len(text)
    for kind, text in picked:
        if kind == "code" and len(text) > 700:
            text = text[:700] + "\n..."
        if kind == "h1":
            continue
        s = ("== %s ==" % text) if kind in ("h2", "h3") else ("```\n%s\n```" % text) if kind == "code" else ("- " + text if kind == "li" else text)
        if total + len(s) > limit and len(out) > 1:
            if kind not in ("code", "h2", "h3") and total < limit - 150:
                out.append(s[:limit - total].rsplit(" ", 1)[0] + "...")
            break
        if kind in ("h2", "h3") and len(out) > 2 and out[-1].startswith("== "):
            break
        out.append(s)
        total += len(s)
    return "\n".join(out)


class _SE(HTMLParser):
    """A Stack Exchange question page -> question body, answers (score, accepted), tags."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.posts, self.tags, self.stack, self.body = [], [], [], None
        self.post_score, self.accepted, self.in_tag = 0, False, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag == "div" and (a.get("id") == "question" or "answer" in cls.split()):
            self.post_score = int(a.get("data-score") or 0) if (a.get("data-score") or "").lstrip("-").isdigit() else 0
            self.accepted = "accepted-answer" in cls or a.get("itemprop") == "acceptedAnswer"
            self.kind = "q" if a.get("id") == "question" else "a"
        if tag == "a" and "post-tag" in cls:
            self.in_tag = True
        if self.body is not None:
            self.body["depth"] += tag not in _Blocks.VOID
            self.body["html"].append(self.get_starttag_text() or "")
        elif tag == "div" and "js-post-body" in cls:
            self.body = {"depth": 1, "html": [], "kind": getattr(self, "kind", "a"), "score": self.post_score, "accepted": self.accepted}

    def handle_endtag(self, tag):
        if self.in_tag and tag == "a":
            self.in_tag = False
        if self.body is not None:
            if tag not in _Blocks.VOID:
                self.body["depth"] -= 1
            if self.body["depth"] <= 0:
                self.posts.append(self.body)
                self.body = None
            else:
                self.body["html"].append("</%s>" % tag)

    def handle_data(self, data):
        if self.in_tag and data.strip():
            self.tags.append(data.strip().lower())
        if self.body is not None:
            self.body["html"].append(htmllib.escape(data))


def qa_excerpt(html_text, limit=1700):
    """Question (short) + the best answer (accepted first, then highest score). Returns (text, info)."""
    p = _SE()
    try:
        p.feed(html_text)
    except Exception:      # noqa: BLE001
        pass
    q = next((x for x in p.posts if x["kind"] == "q"), None)
    answers = [x for x in p.posts if x["kind"] == "a"]
    if not q or not answers:
        return "", {}
    best = max(answers, key=lambda x: (x["accepted"], x["score"]))
    def flat(post, cap):
        out, total = [], 0
        for kind, text in blocks_of("".join(post["html"])):
            if kind == "code" and len(text) > 800:
                text = text[:800] + "\n..."
            s = ("```\n%s\n```" % text) if kind == "code" else ("- " + text if kind == "li" else text)
            if total + len(s) > cap and out:
                break
            out.append(s)
            total += len(s)
        return "\n".join(out)
    qtext = flat(q, 450)
    atext = flat(best, limit - min(len(qtext), 450))
    info = {"score": best["score"], "accepted": best["accepted"], "answers": len(answers), "tags": p.tags[:8], "qscore": q["score"]}
    head = "Answer (%s, score %d)" % ("accepted" if best["accepted"] else "top-voted", best["score"])
    return "Question:\n%s\n\n%s:\n%s" % (qtext, head, atext), info


# ----------------------------------------------------------------------------- the library
class DocsLibrary:
    def __init__(self, base_dir, settings_path=None):
        self.base = base_dir
        self.settings_path = settings_path
        self.lock = threading.Lock()
        self.open = {}          # path -> (Archive, lock)
        self.cache = {}         # (lang, query, kinds) -> (time, results)
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="docs")
        self._files = None
        self._files_at = 0
        self.slow = {}          # file -> until when to skip it (a search took too long on this drive)

    # where the vault is
    def zim_dir(self):
        cands = []
        for d in (os.path.join(self.base, "Vault"), os.path.join(self.base, "vault")):
            cfg = os.path.join(d, "vault-folder.txt")
            try:
                with open(cfg, encoding="utf-8-sig") as f:
                    cands.append(f.read().strip().strip('"'))
            except OSError:
                pass
            cands.append(d)
        for d in cands:
            if d and os.path.isdir(os.path.join(d, "zim")):
                return os.path.join(d, "zim")
        for d in cands:
            if d and os.path.isdir(d):
                return d
        return ""

    def files(self):
        """{name without .zim: full path} for every finished .zim in the vault (rescanned every 5 minutes)."""
        if self._files is not None and time.time() - self._files_at < 300:
            return self._files
        out = {}
        d = self.zim_dir()
        try:
            for f in os.listdir(d) if d else []:
                if f.lower().endswith(".zim"):
                    out[f[:-4]] = os.path.join(d, f)
        except OSError:
            pass
        self._files, self._files_at = out, time.time()
        return out

    def unfinished(self):
        d = self.zim_dir()
        try:
            names = os.listdir(d) if d else []
            done = {f.lower() for f in names if f.lower().endswith(".zim")}
            return sorted(f[:-9] for f in names if f.lower().endswith(".zim.part") and f[:-5].lower() not in done)
        except OSError:
            return []

    def _match(self, prefix):
        """Newest finished file for a source (devdocs_en_python -> devdocs_en_python_2026-08)."""
        names = [n for n in self.files() if n == prefix or n.startswith(prefix + "_") or n.startswith(prefix + ".") or
                 (n.startswith(prefix) and n[len(prefix):len(prefix) + 1] in ("_", "."))]
        if not names and prefix.endswith(".com"):
            names = [n for n in self.files() if n.startswith(prefix)]
        return sorted(names)[-1] if names else None

    def enabled(self):
        try:
            import json
            with open(self.settings_path, encoding="utf-8") as f:
                return bool(json.load(f).get("on", True))
        except (OSError, ValueError, TypeError):
            return True

    def set_enabled(self, on):
        import json
        if not self.settings_path:
            return
        os.makedirs(os.path.dirname(self.settings_path), exist_ok=True)
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump({"on": bool(on)}, f)

    def have_libzim(self):
        try:
            import libzim.reader  # noqa: F401
            return True
        except ImportError:
            return False

    def status(self):
        """What the Workshop shows: which languages have docs, what's missing, what didn't finish downloading."""
        langs = {}
        for k, srcs in SOURCES.items():
            have = [lab for pre, lab, kind, when in srcs if self._match(pre)]
            langs[NICE[k]] = {"have": sorted(set(have)), "main": bool(self._match(srcs[0][0]))}
        slow = sorted(n for n, t in self.slow.items() if t > time.time())
        return {"on": self.enabled(), "folder": self.zim_dir(), "libzim": self.have_libzim(), "langs": langs, "slow": slow,
                "unfinished": [n for n in self.unfinished() if n.startswith(("devdocs", "stackoverflow")) or "stackexchange" in n]}

    def _archive(self, name):
        path = self.files().get(name)
        if not path:
            return None, None
        with self.lock:
            got = self.open.get(path)
            if not got:
                from libzim.reader import Archive
                got = (Archive(path), threading.Lock())
                self.open[path] = got
        return got

    def _search_one(self, name, label, kind, query, words, n, boost=1.0):
        """[(score, ref)] from one file."""
        zim, lk = self._archive(name)
        if zim is None:
            return []
        from libzim.search import Query, Searcher
        out = []
        with lk:
            try:
                paths = list(Searcher(zim).search(Query().set_query(query)).getResults(0, n))
            except Exception:      # noqa: BLE001 - no index, or a bad query
                paths = []
            for rank, path in enumerate(paths):
                if kind == "qa" and not path.startswith("questions/"):
                    continue
                if kind == "qa" and re.match(r"questions(_page=|/?$)|questions/tagged", path):
                    continue
                try:
                    e = zim.get_entry_by_path(path)
                    for _ in range(5):
                        if not e.is_redirect:
                            break
                        e = e.get_redirect_entry()
                    item = e.get_item()
                    if not item.mimetype.startswith("text/html"):
                        continue
                    h = bytes(item.content).decode("utf-8", "replace")
                except Exception:      # noqa: BLE001
                    continue
                title = re.sub(r"\s+-\s+[^-]*(Stack Exchange|Stack Overflow)\s*$", "", e.title or path).strip()
                if kind == "qa":
                    text, info = qa_excerpt(h)
                    if not text:
                        continue
                    score = 3.0 / (1 + 0.5 * rank) + min(info.get("score", 0), 60) / 30.0 + (0.6 if info.get("accepted") else 0)
                    score += 0.8 * sum(1 for w in words if w.lower() in title.lower())
                    out.append((score, {"src": label, "kind": kind, "title": title, "zim": name, "path": e.path, "text": text, "info": info}))
                else:
                    names = [w for w in words if _is_name(w)]
                    info = {}
                    text = docs_excerpt(h, [w.lower() for w in words], names, info=info)
                    if not text:
                        continue
                    score = boost * 4.0 / (1 + 0.5 * rank) + 1.2 * sum(1 for w in words if w.lower() in title.lower())
                    score += 2.0 * sum(1 for nm in names if nm.lower() in text.lower()) + (5.0 if info.get("defines") else 0) + (0.8 if e.path.startswith(("tutorial/", "getting_started/")) else 0)
                    out.append((score, {"src": label, "kind": kind, "title": title, "zim": name, "path": e.path, "text": text}))
        return out

    def search(self, lang, text, k=3, kinds=("docs", "qa"), deadline=12.0, extra=""):
        """Search the sources for this language. Returns refs: [{src, kind, title, zim, path, text}] (best first)."""
        key = lang_key(lang)
        if not key or not self.enabled() or not self.have_libzim():
            return []
        words = terms_of(text)
        if not words:
            return []
        ck = (key, " ".join(words), tuple(kinds), k)
        hit = self.cache.get(ck)
        if hit and time.time() - hit[0] < 1800:
            return hit[1]
        low = (text + " " + extra).lower()
        jobs = []
        for pre, label, kind, when in SOURCES[key]:
            if kind not in kinds or (when and not any(w in low for w in when)):
                continue
            name = self._match(pre)
            if not name or (self.slow.get(name, 0) > time.time() and deadline < 15):
                continue
            if kind == "qa":
                tag = SO_TAG.get(key, "") if pre.startswith("stackoverflow") else ""
                q = " ".join(([tag] if tag and tag.lower() not in low else []) + words[:6])
                jobs.append(self._timed(name, self._search_one, name, label, kind, q, words, 6))
            else:
                jobs.append(self._timed(name, self._search_one, name, label, kind, " ".join(words[:5]), words, 5))
                names = [w for w in words if _is_name(w)]
                for nm in names[:2]:  # a function or class name on its own finds its own page
                    jobs.append(self._timed(name, self._search_one, name, label, kind, nm, words, 6, 1.5))
        done, late = wait(jobs, timeout=deadline)
        for j in late:          # too slow on this drive: leave it out of answers for 10 minutes (the plain search still uses it)
            self.slow[j.zim_name] = time.time() + 600
        found = []
        for j in done:
            try:
                found += j.result()
            except Exception:      # noqa: BLE001 - one bad file doesn't stop the rest
                pass
        # how much of the question each page actually covers (rank alone says little across different files)
        stems = {w.lower()[:-1] if len(w) > 4 and w.lower().endswith("s") else w.lower() for w in words}
        names = [w.lower() for w in words if _is_name(w)]
        def cover(r):
            t = (r["title"] + " " + r["text"]).lower()
            c = sum(1 for w in stems if w in t) / max(1, len(stems))
            if names and not any(n in t for n in names):
                c *= 0.5
            return c
        found = [(s * (0.3 + cover(r)), r) for s, r in found]
        found.sort(key=lambda x: -x[0])
        if found:               # only pages that are about as good a match as the best one
            top = found[0][0]
            found = [(s, r) for s, r in found if s >= 0.55 * top]
        out, seen, per = [], set(), {}
        for s, r in found:
            if (r["zim"], r["path"]) in seen or per.get(r["src"], 0) >= 2:
                continue
            seen.add((r["zim"], r["path"]))
            per[r["src"]] = per.get(r["src"], 0) + 1
            out.append(r)
            if len(out) >= k:
                break
        # one docs page and one Q&A page beat two of the same kind
        if len(out) > 1 and "docs" in kinds and "qa" in kinds and all(r["kind"] == out[0]["kind"] for r in out):
            other = next((r for s, r in found if r["kind"] != out[0]["kind"] and (r["zim"], r["path"]) not in seen), None)
            if other:
                out[-1] = other
        self.cache[ck] = (time.time(), out)
        if len(self.cache) > 300:
            for old in sorted(self.cache, key=lambda c: self.cache[c][0])[:100]:
                self.cache.pop(old, None)
        return out

    def _timed(self, name, fn, *a):
        f = self.pool.submit(fn, *a)
        f.zim_name = name
        return f

    @staticmethod
    def for_prompt(refs, limit=4200):
        """The pages as a block for the model's prompt ('' if none)."""
        if not refs:
            return ""
        parts, total = [], 0
        for r in refs:
            head = "[%s: %s]" % (r["src"], r["title"])
            body = r["text"]
            room = limit - total - len(head) - 4
            if room < 300:
                break
            parts.append(head + "\n" + body[:room])
            total += len(parts[-1]) + 2
        return "\n\n" + LIB_HINT + "\n\n" + "\n\n".join(parts)

    @staticmethod
    def public(refs):
        """What the page needs to show the links (no page text)."""
        def at(r):              # the section the excerpt came from, so the reader can jump there
            m = re.search(r"^== (.+) ==$", r["text"], re.M)
            return m.group(1) if m else ""
        return [{"src": r["src"], "title": r["title"], "zim": r["zim"], "path": r["path"], "kind": r["kind"], "at": at(r),
                 "score": (r.get("info") or {}).get("score"), "accepted": (r.get("info") or {}).get("accepted")} for r in refs]

    def page(self, zim_name, path):
        """A whole page as plain blocks for the Workshop's reader: {title, src, blocks: [[kind, text]]}."""
        if zim_name not in self.files() or not path or ".." in path:
            return {"error": "That page isn't in the vault."}
        zim, lk = self._archive(zim_name)
        with lk:
            try:
                e = zim.get_entry_by_path(path)
                for _ in range(5):
                    if not e.is_redirect:
                        break
                    e = e.get_redirect_entry()
                item = e.get_item()
                h = bytes(item.content).decode("utf-8", "replace")
            except Exception as ex:      # noqa: BLE001
                return {"error": "Couldn't open that page (%s)." % ex}
        src = next((lab for srcs in SOURCES.values() for pre, lab, kind, when in srcs if zim_name.startswith(pre)), zim_name)
        title = re.sub(r"\s+-\s+[^-]*(Stack Exchange|Stack Overflow)\s*$", "", e.title or path).strip()
        if "js-post-body" in h:
            p = _SE()
            try:
                p.feed(h)
            except Exception:      # noqa: BLE001
                pass
            blocks = []
            posts = sorted(p.posts, key=lambda x: (x["kind"] != "q", not x["accepted"], -x["score"]))
            for post in posts[:6]:
                blocks.append(["h2", "Question (score %d)" % post["score"] if post["kind"] == "q" else
                               "Answer: %s, score %d" % ("accepted" if post["accepted"] else "not accepted", post["score"])])
                blocks += [list(b) for b in blocks_of("".join(post["html"]))]
            return {"title": title, "src": src, "blocks": blocks[:400], "tags": p.tags[:10]}
        return {"title": title, "src": src, "blocks": [list(b) for b in blocks_of(_page_start(h))][:600]}

    def browse(self, lang, q, k=8):
        """The plain search box: no AI, just the library."""
        refs = self.search(lang, q, k=k, deadline=20.0)
        def clean(t):
            t = re.sub(r"```.*?```", " ", t, flags=re.S)
            t = re.sub(r"^== (.+) ==$", r"\1:", t, flags=re.M)
            return re.sub(r"\s+", " ", t.replace("Question:", "").replace("Answer (", "(")).strip()
        return {"results": [dict(self.public([r])[0], snippet=clean(r["text"])[:280]) for r in refs]}
