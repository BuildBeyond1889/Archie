"""Project memory: lets the Workshop work on projects too big to show the model all at once.

Small projects are still shown whole. When a project is bigger than the room in the model's prompt, Archie:
  * keeps an index of the project in <project>/.archie/memory.json: each file cut into pieces (a function, a class,
    or about 60 lines), with a meaning-vector per piece from the local embedding model (nomic-embed-text, the
    same one notes search uses). Only files that changed since last time are re-read.
  * for each request, ranks the files by how well their pieces match it (by meaning, or by keywords when the
    embedding model isn't there), plus the entry file, files named in the request or in an error, and files
    you changed recently;
  * shows the model a MAP of the whole project (every file with its functions and classes) and the best files
    IN FULL, as many as fit.
Archie only edits files it was shown in full, so a file it only knows from the map is never cut short.

Everything stays on this PC.
"""
import json
import math
import os
import re
import threading
import time

PIECE_LINES = 60
INDEX_VERSION = 2
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
STOP = set("""the a an and or of to in is it for on with as at by be this that from if else return def class function var let const
int void public private static new self import include using namespace std true false none null not then end""".split())

SIG = {   # one line per function/class for the project map
    ".py": re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+\w+.*?(?=:\s*(?:#.*)?$)", re.M),
    ".gd": re.compile(r"^\s*(?:static\s+)?(?:func|class_name|class|signal)\s+\w+[^:\n]*", re.M),
    ".js": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function\s*\*?\s*\w+\s*\([^)]*\)|class\s+\w+[^{]*|(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)", re.M),
    ".java": re.compile(r"^\s*(?:(?:public|private|protected|static|final|abstract|sealed)\s+)*(?:class|interface|enum|record)\s+\w+[^{]*|^\s*(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)+[\w<>\[\], ?]+\s+\w+\s*\([^)]*\)", re.M),
    ".cs": re.compile(r"^\s*(?:(?:public|private|protected|internal|static|sealed|abstract|partial|virtual|override|async)\s+)*(?:class|interface|enum|struct|record)\s+\w+[^{]*|^\s*(?:(?:public|private|protected|internal|static|virtual|override|abstract|async)\s+)+[\w<>\[\], ?]+\s+\w+\s*\([^)]*\)", re.M),
    ".c": re.compile(r"^(?:static\s+)?(?:struct\s+\w+\s*\{|typedef\s+struct[^;{]*|[A-Za-z_][\w\s\*]*?\b\w+\s*\([^;{)]*\)\s*(?=\{|$))", re.M),
}
SIG[".h"] = SIG[".c"]
SIG[".cpp"] = SIG[".hpp"] = SIG[".ino"] = re.compile(r"^(?:\s*(?:class|struct)\s+\w+[^;{]*|[A-Za-z_][\w:<>,\s\*&]*?\b[\w:~]+\s*\([^;{)]*\)\s*(?:const\s*)?(?=\{|$))", re.M)
SIG[".ts"] = SIG[".js"]
STARTS = {   # where a new piece may begin
    ".py": re.compile(r"^(?:async\s+)?(?:def|class)\s"), ".gd": re.compile(r"^(?:static\s+)?func\s|^class\s"),
    ".js": re.compile(r"^(?:export\s+)?(?:async\s+)?function\s|^class\s|^(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\("),
}


def words(text):
    return [w.lower() for w in WORD.findall(text) if len(w) > 1 and w.lower() not in STOP] + \
        [p.lower() for w in WORD.findall(text) for p in re.findall(r"[a-z]+|[A-Z][a-z]*", w) if len(p) > 2 and p.lower() not in STOP and p != w]


def pieces(path, text):
    """Cut a file into pieces at functions/classes where we can, else every PIECE_LINES lines."""
    lines = text.splitlines()
    ext = os.path.splitext(path)[1].lower()
    starts = STARTS.get(ext)
    cuts = [0]
    for i, l in enumerate(lines):
        if i - cuts[-1] >= PIECE_LINES or (starts and starts.match(l) and i - cuts[-1] >= 8):
            cuts.append(i)
    cuts.append(len(lines))
    out = []
    for a, b in zip(cuts, cuts[1:]):
        if b > a:
            out.append({"file": path, "start": a + 1, "end": b, "text": "\n".join(lines[a:b])})
    return out


def signatures(path, text, limit=14):
    rx = SIG.get(os.path.splitext(path)[1].lower())
    if not rx:
        return []
    out = []
    for m in rx.finditer(text):
        s = " ".join(m.group(0).split())
        if s and not s.startswith(("if ", "while ", "for ", "switch", "return", "else")) and len(s) < 140:
            out.append(s)
        if len(out) >= limit:
            out.append("...")
            break
    return out


def _cos(a, b):
    num = sum(x * y for x, y in zip(a, b))
    da = math.sqrt(sum(x * x for x in a))
    db = math.sqrt(sum(y * y for y in b))
    return num / (da * db) if da and db else 0.0


class ProjectMemory:
    """One per Workshop. Index files live in each project's .archie folder."""

    def __init__(self, embed=None):
        self.embed = embed            # function(list of str) -> list of vectors; None means keywords only
        self.lock = threading.Lock()
        self.mem = {}                 # folder -> loaded index
        self.no_embed_until = 0       # the embedding model failed: try again later

    def _path(self, folder):
        return os.path.join(folder, ".archie", "memory.json")

    def _load(self, folder):
        if folder in self.mem:
            return self.mem[folder]
        try:
            with open(self._path(folder), encoding="utf-8") as f:
                idx = json.load(f)
            if idx.get("v") != INDEX_VERSION:
                raise ValueError
        except (OSError, ValueError):
            idx = {"v": INDEX_VERSION, "files": {}, "model": ""}
        self.mem[folder] = idx
        return idx

    def _save(self, folder, idx):
        p = self._path(folder)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(idx, f)
        os.replace(p + ".tmp", p)

    def update(self, folder, files):
        """files: [{"path", "mtime", "text"(str)}]. Re-index what changed; drop what's gone. Returns the index."""
        with self.lock:
            idx = self._load(folder)
            F = idx["files"]
            seen = set()
            todo = []
            for f in files:
                seen.add(f["path"])
                old = F.get(f["path"])
                if old and old.get("mtime") == f["mtime"] and old.get("size") == len(f["text"]):
                    if self.embed and not old.get("vecs") and time.time() > self.no_embed_until:
                        todo.append(f["path"])
                    continue
                P = pieces(f["path"], f["text"])
                F[f["path"]] = {"mtime": f["mtime"], "size": len(f["text"]), "lines": f["text"].count("\n") + 1,
                                "sigs": signatures(f["path"], f["text"]), "pieces": [{"start": p["start"], "end": p["end"], "words": sorted(set(words(p["text"])))[:400]} for p in P],
                                "vecs": None, "_text": [p["text"] for p in P]}
                todo.append(f["path"])
            for gone in set(F) - seen:
                del F[gone]
            if todo and self.embed and time.time() > self.no_embed_until:
                texts, owners = [], []
                for path in todo:
                    tx = F[path].pop("_text", None) or [self._piece_text(folder, path, p) for p in F[path]["pieces"]]
                    for t in tx:
                        texts.append(("search_document: %s\n%s" % (path, t))[:6000])
                    owners.append((path, len(tx)))
                try:
                    vecs = []
                    for i in range(0, len(texts), 32):
                        vecs += self.embed(texts[i:i + 32])
                    k = 0
                    for path, n in owners:
                        F[path]["vecs"] = [[round(x, 5) for x in v] for v in vecs[k:k + n]]
                        k += n
                    idx["model"] = "embeddings"
                except Exception:      # noqa: BLE001 - no embedding model, or Ollama is busy: keywords still work
                    self.no_embed_until = time.time() + 600
            for path in F:
                F[path].pop("_text", None)
            if not idx.get("model") or not any(v.get("vecs") for v in F.values()):
                idx["model"] = "keywords"
            self._save(folder, idx)
            return idx

    @staticmethod
    def _piece_text(folder, path, p):
        try:
            with open(os.path.join(folder, path), encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
            return "\n".join(lines[p["start"] - 1:p["end"]])
        except OSError:
            return ""

    def rank(self, folder, files, query, entry="", recent=()):
        """[(path, score, why)] best first for this request."""
        idx = self.update(folder, files)
        F = idx["files"]
        qwords = set(words(query))
        qvec = None
        if self.embed and idx.get("model") == "embeddings" and time.time() > self.no_embed_until and query.strip():
            try:
                qvec = self.embed(["search_query: " + query[:2000]])[0]
            except Exception:      # noqa: BLE001
                self.no_embed_until = time.time() + 600
        out = []
        low = query.lower()
        for path, info in F.items():
            best, why = 0.0, ""
            for i, p in enumerate(info["pieces"]):
                kw = len(qwords & set(p["words"])) / (1 + math.sqrt(len(qwords) or 1))
                s = kw
                if qvec and info.get("vecs") and i < len(info["vecs"]):
                    s = 2.5 * max(0.0, _cos(qvec, info["vecs"][i]) - 0.35) + 0.4 * kw
                if s > best:
                    best, why = s, "lines %d-%d match" % (p["start"], p["end"])
            base = os.path.basename(path).lower()
            if base in low or path.lower() in low or os.path.splitext(base)[0] in qwords:
                best += 2.0
                why = "named in the request"
            if path == entry:
                best += 0.6
                why = why or "the entry file"
            if path in recent:
                best += 0.5
                why = why or "changed recently"
            out.append((path, best, why))
        out.sort(key=lambda x: -x[1])
        return out, idx

    def project_map(self, idx, shown):
        lines = []
        for path in sorted(idx["files"]):
            info = idx["files"][path]
            mark = "(shown in full below)" if path in shown else "(not shown; ask for it by name to work on it)"
            lines.append("%s  %d lines %s" % (path, info.get("lines", 0), mark))
            for s in info.get("sigs") or []:
                lines.append("    " + s)
        return "\n".join(lines)

    def status(self, folder):
        idx = self._load(folder)
        F = idx.get("files") or {}
        return {"files": len(F), "pieces": sum(len(v.get("pieces") or []) for v in F.values()), "mode": idx.get("model") or "not yet"}
