"""The Workshop's template library: small, tested building blocks that snap together.

A block is a folder with a card (block.json), its files and a test that proves it works:
  kind     shell (the skeleton of an app), feature (something an app can do), hardware (a sensor or part),
           game, or toolkit
  files    {"where it goes in a project": "file in the block folder"}
  imports  lines added at the shell's marker so the block is ready to use:
             Python  "# archie:imports"       Web  "<!-- archie:scripts -->" / "<!-- archie:styles -->"
             Arduino "// archie:includes"
  use      a short example of using it
  test     {"run": [...]} run in a scratch copy; passing means the block works on this PC
  version + changelog, so a project can see what changed and update.

A recipe is a shell plus blocks plus app files that wire them together: a whole working app to start from.
Library blocks ship with Archie (World/workshop/blocks, recipes); blocks you save from your own projects
live in Workshop/.blocks and work exactly the same.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

MARKERS = {"py": "# archie:imports", "js": "<!-- archie:scripts -->", "css": "<!-- archie:styles -->", "ino": "// archie:includes"}
KINDS = ["shell", "feature", "hardware", "game", "toolkit"]
DEFAULT_SHELL = {"Python": "py-window", "Web (HTML, CSS, JavaScript)": "web-offline-app", "Arduino": "ino-shell", "C": "c-console",
                 "C++": "cpp-game", "Java": "java-console", "C#": "cs-console"}


def _sha(text):
    return hashlib.sha1(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()[:16]


def _read(p):
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()


def _vkey(v):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-]", str(v or "0")))


def _safe_id(s):
    return re.sub(r"[^a-z0-9\-]+", "-", (s or "").lower()).strip("-")[:48] or "block"


class Blocks:
    def __init__(self, lib_dir, user_dir, recipes_dir=None):
        self.lib = lib_dir
        self.user = user_dir
        self.rdir = recipes_dir or os.path.join(os.path.dirname(lib_dir), "recipes")
        os.makedirs(self.user, exist_ok=True)

    # ------------------------------------------------------------- reading the library
    def _load(self, folder, source):
        out = {}
        if not os.path.isdir(folder):
            return out
        for d in sorted(os.listdir(folder)):
            p = os.path.join(folder, d, "block.json")
            if not os.path.isfile(p):
                continue
            try:
                with open(p, encoding="utf-8") as f:
                    c = json.load(f)
            except (OSError, ValueError):
                continue
            c.setdefault("id", d)
            c["source"] = source
            c["dir"] = os.path.join(folder, d)
            out[c["id"]] = c
        return out

    def all(self):
        b = self._load(self.lib, "library")
        b.update(self._load(self.user, "mine"))       # your own version of a block wins
        return b

    def get(self, bid):
        return self.all().get(bid)

    def card(self, c, code=False):
        keep = {k: v for k, v in c.items() if k not in ("dir",)}
        if code:
            keep["code"] = {dest: _read(os.path.join(c["dir"], src)) for dest, src in (c.get("files") or {}).items()
                            if os.path.isfile(os.path.join(c["dir"], src))}
        return keep

    def recipes(self):
        out = []
        for folder, source in ((self.rdir, "library"), (os.path.join(self.user, "_recipes"), "mine")):
            if not os.path.isdir(folder):
                continue
            for d in sorted(os.listdir(folder)):
                p = os.path.join(folder, d, "recipe.json")
                if os.path.isfile(p):
                    try:
                        with open(p, encoding="utf-8") as f:
                            r = json.load(f)
                    except (OSError, ValueError):
                        continue
                    r.setdefault("id", d)
                    r["source"] = source
                    r["dir"] = os.path.join(folder, d)
                    out.append(r)
        return out

    def recipe(self, rid):
        return next((r for r in self.recipes() if r["id"] == rid), None)

    def search(self, q="", lang=None, kind=None, limit=60):
        words = [w for w in re.findall(r"[a-z0-9+#]+", (q or "").lower()) if len(w) > 1]
        res = []
        for c in self.all().values():
            if lang and c.get("lang") != lang and not (lang.startswith("Web") and c.get("lang", "").startswith("Web")):
                continue
            if kind and c.get("kind") != kind:
                continue
            hay = " ".join([c.get("name", ""), c.get("summary", ""), " ".join(c.get("tags") or []), c.get("id", ""), c.get("lang", "")]).lower()
            score = sum(3 if w in (c.get("tags") or []) else 1 for w in words if w in hay) if words else 1
            if score:
                res.append((score, c))
        res.sort(key=lambda x: (-x[0], KINDS.index(x[1].get("kind", "feature")) if x[1].get("kind") in KINDS else 9, x[1].get("name", "")))
        return [self.card(c) for _, c in res[:limit]]

    # ------------------------------------------------------------- putting blocks into a project
    @staticmethod
    def _marker_insert(text, marker, lines):
        """Add lines just after the marker (Python, Arduino) or just before it (HTML), skipping any already there."""
        new = [l for l in lines if l and l not in text]
        if not new or marker not in text:
            return text, bool(new) and marker not in text
        if marker.startswith("<!--"):
            return text.replace(marker, "\n".join(new) + "\n" + marker, 1), False
        i = text.index(marker) + len(marker)
        while True:                                  # keep the order: after any block lines already added under the marker
            nl = text.find("\n", i)
            if nl < 0:
                break
            nxt = text[nl + 1:text.find("\n", nl + 1) if text.find("\n", nl + 1) >= 0 else len(text)]
            if nxt.startswith(("from lib", "import lib", "#include \"")):
                i = nl + 1 + len(nxt)
            else:
                break
        return text[:i] + "\n" + "\n".join(new) + text[i:], False

    def files_for(self, bids, current):
        """What installing these blocks would write. current(rel) -> text or None.
        Returns (files [(rel, text)], installed {id: {"version", "files": {rel: sha}}}, notes [str])."""
        lib = self.all()
        out, installed, notes = {}, {}, []
        order = []

        def add(bid):                                  # a block can ask for other blocks first
            if bid in order:
                return
            c = lib.get(bid)
            if not c:
                notes.append("There's no block called %s." % bid)
                return
            for dep in c.get("uses") or []:
                add(dep)
            order.append(bid)
        for b in bids:
            add(b)

        def cur(rel):
            return out[rel] if rel in out else current(rel)
        for bid in order:
            c = lib[bid]
            rec = {"version": c.get("version", "1.0.0"), "files": {}}
            for dest, src in (c.get("files") or {}).items():
                sp = os.path.join(c["dir"], src)
                if not os.path.isfile(sp):
                    continue
                text = _read(sp)
                if c.get("kind") == "shell" and cur(dest) is not None:
                    continue                               # never replace an app's main file with a fresh shell
                out[dest] = text
                rec["files"][dest] = _sha(text)
            for kind, lines in (c.get("imports") or {}).items():
                target = c.get("import_into") or {"py": None, "js": "index.html", "css": "index.html", "ino": None}.get(kind)
                if not target:
                    target = next((r for r in list(out) + ["main.py", "app.py", "sketch/sketch.ino"] if
                                   (kind == "py" and r.endswith(".py") and MARKERS["py"] in (cur(r) or "")) or
                                   (kind == "ino" and r.endswith(".ino") and MARKERS["ino"] in (cur(r) or ""))), None)
                text = cur(target) if target else None
                if text is None:
                    notes.append("%s: add these lines where you use it: %s" % (c.get("name", bid), " / ".join(lines)))
                    continue
                text, missing = self._marker_insert(text, MARKERS[kind], lines)
                if missing:
                    notes.append("%s: no '%s' marker in %s, so add these lines yourself: %s" % (c.get("name", bid), MARKERS[kind], target, " / ".join(lines)))
                out[target] = text
                if kind == "js":                       # the offline app's service worker must list new files too
                    sw = cur("sw.js")
                    if sw and "/* archie:files */" in sw:
                        for l in lines:
                            m = re.search(r'src="([^"]+)"', l)
                            if m and '"%s"' % m.group(1) not in sw:
                                sw = sw.replace("/* archie:files */", ', "%s"/* archie:files */' % m.group(1), 1)
                        out["sw.js"] = sw
            installed[bid] = rec
        return list(out.items()), installed, notes

    def recipe_files(self, rid):
        r = self.recipe(rid)
        if not r:
            return None, None, ["There's no recipe called %s." % rid]
        files, installed, notes = self.files_for([r["shell"]] + list(r.get("blocks") or []), lambda rel: None)
        files = dict(files)
        for dest, src in (r.get("files") or {}).items():        # the app files that wire the blocks together
            sp = os.path.join(r["dir"], src)
            if os.path.isfile(sp):
                files[dest] = _read(sp)
        for kind, lines in (r.get("imports") or {}).items():
            for rel in list(files):
                if MARKERS[kind] in files[rel]:
                    files[rel], _ = self._marker_insert(files[rel], MARKERS[kind], lines)
        return list(files.items()), installed, notes

    def updates(self, have, current):
        """have = the project's {id: {"version", "files"}}. What's newer in the library, and did you change the block's files?"""
        lib = self.all()
        out = []
        for bid, rec in (have or {}).items():
            c = lib.get(bid)
            if not c or _vkey(c.get("version")) <= _vkey(rec.get("version")):
                continue
            changed = [rel for rel, h in (rec.get("files") or {}).items() if current(rel) is not None and _sha(current(rel)) != h]
            notes = [ch for ch in c.get("changelog") or [] if _vkey(ch.get("version")) > _vkey(rec.get("version"))]
            out.append({"id": bid, "name": c.get("name", bid), "have": rec.get("version"), "now": c.get("version"),
                        "changes": notes, "you_changed": changed})
        return out

    def update_files(self, bid, current, force=False):
        c = self.get(bid)
        if not c:
            return [], {}, ["There's no block called %s." % bid]
        files, rec = [], {"version": c.get("version", "1.0.0"), "files": {}}
        skipped = []
        for dest, src in (c.get("files") or {}).items():
            sp = os.path.join(c["dir"], src)
            if not os.path.isfile(sp) or c.get("kind") == "shell":
                continue
            text = _read(sp)
            files.append((dest, text))
            rec["files"][dest] = _sha(text)
        return files, {bid: rec}, skipped

    # ------------------------------------------------------------- testing
    def test(self, bid, rt):
        """Copy the block (and the blocks it uses) into a scratch folder and run its test."""
        c = self.get(bid)
        if not c:
            return {"ok": False, "output": "no such block"}
        t = c.get("test") or {}
        if not t.get("run"):
            return {"ok": None, "output": "This block has no test yet."}
        tmp = tempfile.mkdtemp(prefix="archie-block-")
        try:
            files, _, _ = self.files_for([bid], lambda rel: None)
            for rel, text in files:
                p = os.path.join(tmp, rel)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
            for extra in t.get("files") or []:
                shutil.copy(os.path.join(c["dir"], extra), os.path.join(tmp, os.path.basename(extra)))
            exe = {"python": rt.get("python") or sys.executable, "node": rt.get("node"), "g++": rt.get("g++"), "gcc": rt.get("gcc"),
                   "javac": rt.get("javac"), "java": rt.get("java"), "dotnet": rt.get("dotnet")}
            cmd = [(exe.get(x) or x) if i == 0 else x for i, x in enumerate(t["run"])]
            if cmd[0] and not os.path.isabs(cmd[0]):
                cmd[0] = shutil.which(cmd[0])
            if not cmd[0]:
                return {"ok": None, "output": "Testing this block needs %s." % t["run"][0]}
            if cmd[0] in (rt.get("g++"), rt.get("gcc")) and "stub" in t:
                stub = os.path.join(os.path.dirname(self.lib), "arduino-stub")
                cmd = cmd[:1] + ["-I", stub] + cmd[1:]
            env = dict(os.environ, PYTHONIOENCODING="utf-8", ARCHIE_TEST="1")
            feed = t.get("input")
            c2 = subprocess.run(cmd, cwd=tmp, capture_output=True, text=True, timeout=180, env=env, encoding="utf-8", errors="replace",
                                input=None if t.get("then") else (feed or ""), creationflags=0x08000000 if os.name == "nt" else 0)
            out = (c2.stdout + c2.stderr)[-3000:]
            if c2.returncode == 0 and t.get("then"):
                c3 = subprocess.run([os.path.join(tmp, t["then"])], cwd=tmp, capture_output=True, text=True, timeout=60, input=feed or "",
                                    encoding="utf-8", errors="replace", creationflags=0x08000000 if os.name == "nt" else 0)
                out += (c3.stdout + c3.stderr)[-2000:]
                return {"ok": c3.returncode == 0, "output": out}
            return {"ok": c2.returncode == 0, "output": out}
        except (OSError, subprocess.SubprocessError) as e:
            return {"ok": False, "output": str(e)}
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    # ------------------------------------------------------------- saving your own
    def save_block(self, project_root, rels, name, summary, lang, kind="feature", tags=None, use=""):
        bid = _safe_id(name)
        d = os.path.join(self.user, bid)
        old = None
        if os.path.isfile(os.path.join(d, "block.json")):
            with open(os.path.join(d, "block.json"), encoding="utf-8") as f:
                old = json.load(f)
        os.makedirs(os.path.join(d, "files"), exist_ok=True)
        files = {}
        for rel in rels:
            src = os.path.realpath(os.path.join(project_root, rel))
            if not src.startswith(os.path.realpath(project_root) + os.sep) or not os.path.isfile(src):
                continue
            dst = os.path.join(d, "files", rel.replace("/", "__"))
            shutil.copy(src, dst)
            files[rel] = "files/" + os.path.basename(dst)
        if not files:
            return {"error": "Pick at least one file from the project."}
        ver = "1.0.0"
        log = [{"version": ver, "note": "first version"}]
        if old:
            parts = [int(x) for x in re.findall(r"\d+", old.get("version", "1.0.0"))[:3]] + [0, 0, 0]
            ver = "%d.%d.0" % (parts[0], parts[1] + 1)
            log = (old.get("changelog") or []) + [{"version": ver, "note": "saved again from your project"}]
        card = {"id": bid, "name": name.strip()[:80], "kind": kind if kind in KINDS else "feature", "lang": lang, "version": ver,
                "summary": summary.strip()[:400], "tags": [t.strip().lower() for t in (tags or []) if t.strip()][:12], "files": files,
                "use": use[:2000], "changelog": log, "made": int(time.time())}
        with open(os.path.join(d, "block.json"), "w", encoding="utf-8") as f:
            json.dump(card, f, indent=1)
        return {"ok": True, "id": bid, "version": ver}
