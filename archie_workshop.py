"""Archie's Workshop: code with Archie on this PC, offline.

Two ways to work on a project (each is a folder under D:\\Archie\\Workshop, or any folder you link):
  * Build: say what you want; Archie writes the files, runs them, reads any error and fixes it (a few tries),
    showing each change. Undo puts the last version back.
  * Teach: Archie plans the project as small lessons. Each one explains an idea and gives you a task; you
    write it (in VSCodium or anything else), press check, and Archie runs your code and tells you how it
    went, with hints instead of answers unless you ask. What you learn becomes flashcards.

It watches the project folder while you work: every save is checked, and if something's broken Archie
explains the error in plain words. With the Archie Coach add-on in VSCodium it also knows which file and line
you're on, answers "explain this", and puts its hints right on the line in the editor.

All local: the coding model runs in Ollama; code runs on this PC, inside the project folder.
"""
import difflib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time

import archie_blocks
import archie_docs
import archie_projmem
import archie_coach
import archie_course
import archie_checkers as checkers

LANGS = {   # language: (entry file, how to run, file extensions)
    "Python": ("main.py", "python", (".py",)),
    "Web (HTML, CSS, JavaScript)": ("index.html", "preview", (".html", ".css", ".js")),
    "JavaScript (Node)": ("main.js", "node", (".js",)),
    "Java": ("Main.java", "java", (".java",)),
    "C": ("main.c", "gcc", (".c", ".h")),
    "C++": ("main.cpp", "g++", (".cpp", ".hpp", ".h")),
    "C#": ("Program.cs", "dotnet", (".cs",)),
    "GDScript (Godot)": ("main.gd", "godot", (".gd",)),
    "Arduino": ("sketch/sketch.ino", "arduino", (".ino",)),
}
TEXT_EXT = {".py", ".js", ".html", ".htm", ".css", ".json", ".md", ".txt", ".java", ".c", ".h", ".cpp", ".hpp", ".cs", ".gd", ".ino",
            ".ts", ".csv", ".xml", ".yml", ".yaml", ".toml", ".ini", ".bat", ".sh", ".sql", ".svg"}
SKIP_DIRS = {".archie", ".git", "__pycache__", "node_modules", ".vscode", "bin", "obj", "build", "dist", ".godot"}

BUILD_RULES = """You are Archie, a careful programmer working on the user's own PC, offline.
Write complete, working files for the request. Rules:
- Keep it small and readable, with short comments that explain the important parts to a learner.
- Use only the standard library unless the user asks for a package. For Python windows use tkinter.
- Put everything in this one project folder. Entry file: {entry}.
- Reply with ONE short line starting "PLAN:" saying what you'll do, then every file you create or change, each written in full like this:
<<<FILE relative/path.ext>>>
(the whole file)
<<<END>>>
- Never write a file outside the project, never delete anything, never anything harmful."""

TEACH_RULES = """You are Archie, a patient programming teacher. The learner is a beginner who learns best with plain words,
one idea at a time, and real projects. Be encouraging but honest. Never use emoji."""


def _now():
    return int(time.time())


def _safe(name):
    s = re.sub(r"[^A-Za-z0-9 _\-]+", "", name or "").strip().replace(" ", "-")
    return s[:60] or "project"


class Workshop(archie_course.CourseMixin):
    TEACH = TEACH_RULES

    def __init__(self, base_dir, get_model, study_dir=None, alert=None):
        self.dir = os.path.join(base_dir, "Workshop")
        os.makedirs(self.dir, exist_ok=True)
        self.get_model = get_model
        self.study_dir = study_dir
        self.alert = alert or (lambda *a: None)
        self.lock = threading.RLock()
        self.jobs = {}
        self.events = []       # newest last: {"n", "at", "project", "kind", "title", "text", "file", "line"}
        self.n = 0
        self.editor = {}       # what the VSCodium add-on last told us: file, line, selection, language
        self.hints = {}        # absolute file path -> [{"line", "text", "at"}]
        self.problems = {}     # absolute file path -> what the real checkers found: [{"line", "col", "sev", "code", "msg"}]
        self.runs = {}         # project -> Popen still running (a window, a loop)
        self.snap = {}         # project -> {relpath: (mtime, text)} as last seen by the watcher
        self.stop = threading.Event()
        tp = os.path.join(self.dir, ".token")
        try:
            with open(tp, encoding="utf-8") as f:
                self.token = f.read().strip()
        except OSError:
            self.token = ""
        if len(self.token) < 20:
            self.token = secrets.token_hex(24)
            with open(tp, "w", encoding="utf-8") as f:
                f.write(self.token)
        self.links = self._jload(os.path.join(self.dir, "linked.json"), {})
        self.courses = archie_course.Courses(os.path.join(base_dir, "World", "workshop", "courses"))
        self.blocks = archie_blocks.Blocks(os.path.join(base_dir, "World", "workshop", "blocks"), os.path.join(self.dir, ".blocks"))
        self.docs = archie_docs.DocsLibrary(base_dir, os.path.join(self.dir, ".docs.json"))     # the offline docs in the vault
        self.pmem = archie_projmem.ProjectMemory(embed=self._embed)   # big projects: a map plus the files that matter
        self.shown = {}        # project -> files the model last saw in full (None: all of them)
        self.coach = archie_coach.DevCoach(self.dir, self._chat_main, docs=self.docs, pmem=self.pmem, alert=self.alert)   # a dev log per game
        threading.Thread(target=self._watch_loop, daemon=True, name="workshop-watch").start()

    # ------------------------------------------------------------------ small helpers
    @staticmethod
    def _jload(p, default):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return default

    @staticmethod
    def _jsave(p, d):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(d, f, indent=1, ensure_ascii=False)
        os.replace(p + ".tmp", p)

    def folder(self, name):
        if name in self.links:
            return self.links[name]
        return os.path.join(self.dir, _safe(name))

    def meta(self, name):
        return self._jload(os.path.join(self.folder(name), ".archie", "project.json"), {})

    def save_meta(self, name, m):
        self._jsave(os.path.join(self.folder(name), ".archie", "project.json"), m)

    def _inside(self, name, rel):
        root = os.path.realpath(self.folder(name))
        p = os.path.realpath(os.path.join(root, rel))
        if not (p == root or p.startswith(root + os.sep)):
            raise ValueError("outside the project")
        return p

    def model(self):
        try:
            from archie_brain import list_models
            ms = list_models() or []
        except Exception:
            ms = []
        for want in ("qwen2.5-coder:7b", "qwen2.5-coder"):
            m = next((x for x in ms if x.startswith(want)), None)
            if m:
                return m
        m = next((x for x in ms if "coder" in x), None)
        return m or self.get_model()

    def _chat_main(self, system, prompt, tokens=1600, json_mode=False):
        """Design talk goes to Archie's main model (better at reasoning than the coding model)."""
        from archie_brain import quick_chat
        return quick_chat(self.get_model(), prompt, max_tokens=tokens, timeout=600, json_mode=json_mode, num_ctx=16384, temperature=0.4, system=system)

    def _chat(self, system, prompt, tokens=1600, json_mode=False, temp=0.3):
        from archie_brain import quick_chat
        return quick_chat(self.model(), prompt, max_tokens=tokens, timeout=600, json_mode=json_mode, num_ctx=16384, temperature=temp, system=system)

    EXT_LANG = {".py": "Python", ".html": "Web", ".htm": "Web", ".css": "Web", ".js": "Web", ".java": "Java", ".c": "C", ".h": "C",
                ".cpp": "C++", ".hpp": "C++", ".cs": "C#", ".gd": "GDScript (Godot)", ".ino": "Arduino"}

    def _lang(self, name, file=""):
        """The language to look things up in: the project's, else from the file's extension."""
        m = self.meta(name) if name else {}
        if m.get("mode") == "course" and m.get("course"):
            try:
                return self._clang(name)
            except Exception:      # noqa: BLE001
                pass
        if m.get("lang"):
            return m["lang"]
        return self.EXT_LANG.get(os.path.splitext(file or "")[1].lower(), "")

    def _lookup(self, lang, text, k=2, kinds=("docs", "qa"), extra=""):
        """Look it up before answering: (text for the prompt, links for the feed). Empty when the vault has nothing."""
        try:
            refs = self.docs.search(lang, text, k=k, kinds=kinds, extra=extra)
        except Exception:      # noqa: BLE001 - the docs are a help, never a reason to fail
            refs = []
        return self.docs.for_prompt(refs), self.docs.public(refs)

    def event(self, project, kind, title, text="", file="", line=None, refs=None):
        with self.lock:
            self.n += 1
            e = {"n": self.n, "at": _now(), "project": project, "kind": kind, "title": title, "text": text[:6000], "file": file, "line": line}
            if refs:
                e["refs"] = refs
            self.events.append(e)
            self.events = self.events[-400:]
        if project:
            try:
                with open(os.path.join(self.folder(project), ".archie", "log.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            except OSError:
                pass
        return e

    def _job(self, fn, *a):
        jid = secrets.token_hex(6)
        self.jobs[jid] = {"status": "working", "at": _now(), "result": None}

        def run():
            try:
                self.jobs[jid]["result"] = fn(*a)
                self.jobs[jid]["status"] = "done"
            except Exception as e:      # noqa: BLE001 - shown in the Workshop
                self.jobs[jid]["result"] = {"error": str(e)[:400]}
                self.jobs[jid]["status"] = "done"
                self.event(a[0] if a and isinstance(a[0], str) else "", "error", "Something went wrong", str(e)[:400])
        threading.Thread(target=run, daemon=True, name="workshop-job").start()
        return {"job": jid}

    # ------------------------------------------------------------------ projects
    def runtimes(self):
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe"):
            exe = exe[:-5] + ".exe"
        found = {"python": exe}
        extra = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"), r"C:\Program Files\nodejs", r"C:\Program Files\dotnet"]
        import glob
        extra += sorted(glob.glob(r"C:\Program Files\Eclipse Adoptium\jdk-*\bin"), reverse=True)
        extra += glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\BrechtSanders.WinLibs*\mingw64\bin"))
        search = os.pathsep.join([os.environ.get("PATH", "")] + [d for d in extra if os.path.isdir(d)])
        for k, names in (("node", ["node"]), ("java", ["java"]), ("javac", ["javac"]), ("gcc", ["gcc"]), ("g++", ["g++"]), ("dotnet", ["dotnet"]),
                         ("godot", ["godot", "godot4", "Godot_v4"]), ("arduino", ["arduino-cli"]), ("codium", ["codium", "codium.cmd"])):
            for n in names:
                p = shutil.which(n, path=search)
                if p:
                    found[k] = p
                    break
        if "codium" not in found:
            for p in (os.path.expandvars(r"%LOCALAPPDATA%\Programs\VSCodium\bin\codium.cmd"), r"C:\Program Files\VSCodium\bin\codium.cmd"):
                if os.path.exists(p):
                    found["codium"] = p
                    break
        return found

    def state(self):
        names = set(self.links)
        for d in os.listdir(self.dir):
            if os.path.isdir(os.path.join(self.dir, d)) and not d.startswith("."):
                names.add(d)
        P = []
        for n in sorted(names):
            m = self.meta(n)
            lesson = m.get("lesson") or {}
            P.append({"name": n, "mode": m.get("mode", "build"), "lang": m.get("lang", ""), "goal": m.get("goal", ""), "linked": n in self.links,
                      "folder": self.folder(n), "watch": bool(m.get("watch", True)), "updated": m.get("updated", 0),
                      "progress": [lesson.get("current", 0), len(lesson.get("steps") or [])] if lesson else self._course_progress(n, m)})
        P.sort(key=lambda p: -p["updated"])
        rt = self.runtimes()
        return {"projects": P, "runtimes": sorted(rt), "codium": "codium" in rt, "model": self.model(), "langs": list(LANGS), "folder": self.dir,
                "ruff": bool(checkers.ruff_cmd(rt)), "blocks": len(self.blocks.all()), "arduino_core": self.arduino_ready() if "arduino" in rt else None,
                "recipes": [dict({k: r.get(k) for k in ("id", "name", "lang", "summary", "for", "cheap", "tags", "parts")}, teach=bool((r.get("guide") or {}).get("lessons")))
                            for r in self.blocks.recipes()]}

    def _course_progress(self, name, m):
        if m.get("mode") != "course":
            return None
        try:
            units = self.courses.units(m["course"])
            return [sum(1 for u in units if archie_course.unit_score(u, m.get("progress") or {}) >= archie_course.MASTERY), len(units)]
        except (OSError, ValueError, KeyError):
            return None

    def files(self, name):
        root = self.folder(name)
        out = []
        for dp, dns, fns in os.walk(root):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for f in fns:
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, root).replace("\\", "/")
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                out.append({"path": rel, "size": st.st_size, "mtime": int(st.st_mtime), "text": os.path.splitext(f)[1].lower() in TEXT_EXT})
                if len(out) >= 400:
                    return out
        return sorted(out, key=lambda x: x["path"])

    def read(self, name, rel):
        p = self._inside(name, rel)
        if os.path.getsize(p) > 400000:
            return {"path": rel, "text": "", "note": "too big to show"}
        with open(p, encoding="utf-8", errors="replace") as f:
            return {"path": rel, "text": f.read()}

    def project(self, name):
        m = self.meta(name)
        if not m and name not in self.links and not os.path.isdir(self.folder(name)):
            return {"error": "no such project"}
        hist = m.get("history") or []
        return {"name": name, "meta": {k: v for k, v in m.items() if k != "history"}, "folder": self.folder(name), "files": self.files(name),
                "history": [{"at": h["at"], "what": h["what"], "files": list(h["before"])} for h in hist[-20:]], "guide": self.guide(m),
                "events": [e for e in self.events if e["project"] == name][-80:], "editor": self.editor if self.editor.get("project") == name else {},
                "running": name in self.runs and self.runs[name].poll() is None, "memory": self.pmem.status(self.folder(name)),
                "big": sum(f["size"] for f in self.files(name) if f["text"] and f["size"] <= 60000) > 24000}

    def new(self, b):
        name = _safe(b.get("name") or b.get("goal", "")[:30])
        mode = "teach" if b.get("mode") == "teach" else "build"
        lang = b.get("lang") if b.get("lang") in LANGS else "Python"
        if b.get("folder"):
            f = os.path.abspath(os.path.expandvars(b["folder"].strip().strip('"')))
            if not os.path.isdir(f):
                return {"error": "That folder doesn't exist: " + f}
            name = _safe(b.get("name") or os.path.basename(f))
            self.links[name] = f
            self._jsave(os.path.join(self.dir, "linked.json"), self.links)
        root = self.folder(name)
        if os.path.isdir(os.path.join(root, ".archie")) and not b.get("folder"):
            return {"error": "There's already a project called %s." % name}
        os.makedirs(os.path.join(root, ".archie"), exist_ok=True)
        m = {"name": name, "mode": mode, "lang": lang, "goal": (b.get("goal") or "").strip()[:2000], "entry": LANGS[lang][0],
             "watch": True, "created": _now(), "updated": _now(), "history": []}
        if b.get("folder"):
            ent = next((f["path"] for f in self.files(name) if os.path.basename(f["path"]).lower() in ("main.py", "app.py", "index.html", "main.js", "main.java", "program.cs")), "")
            m["entry"] = ent or m["entry"]
        rec = self.blocks.recipe(b["recipe"]) if b.get("recipe") else None
        if rec:
            m["lang"] = rec.get("lang", m["lang"])
            m["entry"] = LANGS.get(m["lang"], (m["entry"],))[0]
            m["recipe"] = rec["id"]
            m["goal"] = m["goal"] or rec.get("summary", "")
        self.save_meta(name, m)
        teach_rec = rec and mode == "teach" and (rec.get("guide") or {}).get("lessons")
        if rec or b.get("blocks"):
            if rec:
                files, installed, notes = self.blocks.recipe_files(rec["id"])
                if teach_rec:          # you write the main file yourself, step by step; the blocks are given
                    G = rec["guide"]
                    files = [(r, G.get("starter", "") if r == G["main"] else t) for r, t in files]
                    m = self.meta(name)
                    m.update(mode="teach", entry=G["main"], lesson={"title": rec["name"], "steps": G["lessons"], "current": 0, "done": [], "prewritten": True})
                    self.save_meta(name, m)
            else:
                shell = b.get("shell") or archie_blocks.DEFAULT_SHELL.get(lang)
                files, installed, notes = self.blocks.files_for(([shell] if shell else []) + list(b["blocks"]), lambda rel: None)
            self._apply(name, files, "started from " + (rec["name"] if rec else "blocks"))
            m = self.meta(name)
            m["blocks"] = installed
            self.save_meta(name, m)
            self.event(name, "change", "Started from %s: %d files" % ("the %s recipe" % rec["name"] if rec else "blocks", len(files)),
                       "Blocks: " + ", ".join(sorted(installed)) + ("\n" + "\n".join(notes) if notes else "") +
                       ("\n\nParts: " + ", ".join(rec.get("parts") or []) if rec and rec.get("parts") else ""))
        self.snap[name] = self._scan(name)
        self.event(name, "info", "Project started", "%s · %s" % (self.meta(name).get("lang", lang), "Archie builds it" if mode == "build" else "you build it, Archie teaches"))
        out = {"ok": True, "name": name}
        if mode == "teach" and m["goal"] and not teach_rec:
            out.update(self._job(self._plan_lesson, name))
        elif mode == "build" and m["goal"] and not b.get("folder") and not rec and not b.get("blocks"):
            out.update(self._job(self._build, name, m["goal"]))
        return out

    # ------------------------------------------------------------------ running code
    def run(self, name, rel=None, wait=8):
        m = self.meta(name)
        rel = rel or m.get("entry") or ""
        root = self.folder(name)
        try:
            p = self._inside(name, rel)
        except ValueError:
            return {"status": "error", "output": "That file is outside the project."}
        if not os.path.isfile(p):
            return {"status": "error", "output": "There's no %s yet." % rel}
        ext = os.path.splitext(p)[1].lower()
        rt = self.runtimes()
        if ext in (".html", ".htm"):
            return {"status": "preview", "url": "/ws/preview/%s/%s" % (name, rel), "output": "Open the preview to see the page."}
        old = self.runs.pop(name, None)
        if old and old.poll() is None:
            try:
                old.kill()
            except OSError:
                pass
        cmd, cwd = None, os.path.dirname(p)
        if ext == ".py":
            cmd = [rt["python"], "-u", p]
        elif ext == ".js" and "node" in rt:
            cmd = [rt["node"], p]
        elif ext == ".java" and "java" in rt:
            cmd = [rt["java"], p]
        elif ext in (".c", ".cpp") and (("gcc" if ext == ".c" else "g++") in rt):
            exe = os.path.join(root, ".archie", "build", os.path.splitext(os.path.basename(p))[0] + ".exe")
            os.makedirs(os.path.dirname(exe), exist_ok=True)
            srcs = [os.path.join(dp, f) for dp, _, fs in os.walk(root) if ".archie" not in dp for f in fs if f.endswith(ext)]
            if m.get("mode") == "course":
                srcs = [p]           # course folders hold many small programs, each with its own main()
            c = subprocess.run([rt["gcc" if ext == ".c" else "g++"], "-g", "-o", exe] + srcs, cwd=root, capture_output=True, text=True, timeout=120)
            if c.returncode:
                return self._finish(name, rel, "error", (c.stdout + c.stderr)[-6000:])
            cmd = [exe]
        elif ext == ".cs" and "dotnet" in rt:
            proj = next((os.path.join(dp, f) for dp, _, fs in os.walk(root) for f in fs if f.endswith(".csproj")), None)
            if not proj or m.get("mode") == "course":
                return self._run_cs_file(name, rel, p, rt)
            self._offline_nuget(name, proj)
            cmd, cwd = [rt["dotnet"], "run", "--project", proj], root
        elif ext == ".gd":
            return {"status": "error", "output": "GDScript runs inside Godot: open the project in Godot and press play. Archie can still read and check your scripts."}
        elif ext == ".ino" and ("arduino" in rt or "g++" in rt):
            out = ""
            if "arduino" in rt:
                c = subprocess.run([rt["arduino"], "compile", "--fqbn", m.get("board") or "arduino:avr:uno", os.path.dirname(p)], capture_output=True, text=True, timeout=300,
                                   creationflags=0x08000000 if os.name == "nt" else 0)
                out = (c.stdout + c.stderr)
                if not re.search(r"platform not installed|Platform '.*' not found|not found.*platform|Error during build: .*core", out, re.I):
                    return self._finish(name, rel, "error" if c.returncode else "ok", out[-6000:] or "Compiled. Upload it from the Arduino app or arduino-cli upload.")
            if "g++" not in rt:
                return self._finish(name, rel, "error", out[-3000:] + "\nThe Arduino board support isn't installed yet. Press 'get Arduino board support' at the top (needs internet once).")
            # no board support yet: check it with Archie's practice Arduino, so lessons still work offline
            stub = os.path.join(os.path.dirname(self.dir), "World", "workshop", "arduino-stub")
            c = subprocess.run([rt["g++"], "-std=c++17", "-fsyntax-only", "-x", "c++", "-include", "Arduino.h", "-I", stub, "-I", os.path.dirname(p), p],
                               capture_output=True, text=True, timeout=120, creationflags=0x08000000 if os.name == "nt" else 0)
            note = "\n(Checked with Archie's practice Arduino because the real board support isn't installed. Press 'get Arduino board support' at the top once while online to compile for a real board.)"
            return self._finish(name, rel, "error" if c.returncode else "ok", ((c.stdout + c.stderr)[-5000:] or "It compiles.") + note)
        else:
            need = {".js": "Node.js", ".java": "Java (JDK)", ".c": "a C compiler (gcc)", ".cpp": "a C++ compiler (g++)", ".cs": ".NET", ".ino": "arduino-cli"}.get(ext)
            return {"status": "error", "output": ("Running %s needs %s. Get Code Editor.bat can install it." % (ext, need)) if need else "Archie doesn't know how to run %s files." % ext}
        flags = 0x08000000 if os.name == "nt" and ext != ".py" else 0     # no black console window for compiled programs
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags,
                                env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1"))
        buf = []
        threading.Thread(target=lambda: [buf.append(l) for l in iter(proc.stdout.readline, b"")], daemon=True).start()
        t0 = time.time()
        while proc.poll() is None and time.time() - t0 < wait:
            time.sleep(0.1)
        out = b"".join(buf).decode("utf-8", "replace")
        if proc.poll() is None:
            self.runs[name] = proc
            return self._finish(name, rel, "running", out[-6000:] + ("\n" if out else "") + "(still running: a window or a loop. It keeps going until you close it or press stop.)")
        time.sleep(0.2)
        out = b"".join(buf).decode("utf-8", "replace")
        return self._finish(name, rel, "error" if proc.returncode else "ok", out[-6000:] or "(it ran and printed nothing)")

    def _run_cs_file(self, name, rel, p, rt):
        """One C# file with no project: build it on its own in a scratch project and run it."""
        import archie_graders as G
        import tempfile
        tmp = tempfile.mkdtemp(prefix="archie-cs-run-")
        try:
            shutil.copy(p, os.path.join(tmp, "Program.cs"))
            src = open(p, encoding="utf-8", errors="replace").read()
            mm = re.search(r"\bclass\s+(\w+)[^{]*\{[^}]*?static\s+(?:async\s+)?\w+\s+Main\s*\(", src, re.S)
            ns = re.search(r"^\s*namespace\s+([\w.]+)", src, re.M)
            with open(os.path.join(tmp, "App.csproj"), "w", encoding="utf-8") as f:
                f.write(G.CSPROJ % ((ns.group(1) + "." if ns else "") + (mm.group(1) if mm else "Program")))
            with open(os.path.join(tmp, "nuget.config"), "w", encoding="utf-8") as f:
                f.write(G.NUGET)
            c, o, e = G.run([rt["dotnet"], "build", "App.csproj", "-nologo", "-v", "q", "-o", "out", "-clp:NoSummary"], tmp, timeout=240)
            if c:
                return self._finish(name, rel, "error", "\n".join(sorted(set(l.split("[")[0].strip() for l in (o + e).splitlines() if " error " in l))) or (o + e)[-3000:])
            c, o, e = G.run([rt["dotnet"], os.path.join(tmp, "out", "App.dll")], tmp, "", timeout=20)
            return self._finish(name, rel, "error" if c else "ok", ((o or "") + (e or ""))[-6000:] or "(it ran and printed nothing)")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _offline_nuget(self, name, proj):
        """dotnet tries to reach nuget.org even for projects with no packages, and fails offline.
        A nuget.config with no online sources fixes that; only added when the project uses no packages."""
        d = os.path.dirname(proj)
        if os.path.exists(os.path.join(d, "nuget.config")) or os.path.exists(os.path.join(d, "NuGet.Config")):
            return
        try:
            with open(proj, encoding="utf-8", errors="replace") as f:
                if "PackageReference" in f.read():
                    return
            with open(os.path.join(d, "nuget.config"), "w", encoding="utf-8") as f:
                f.write('<?xml version="1.0" encoding="utf-8"?>\n<!-- Added by Archie: no online package sources, so this builds with no internet. '
                        'Remove the <clear /> line if you add NuGet packages. -->\n<configuration>\n  <packageSources>\n    <clear />\n  </packageSources>\n</configuration>\n')
            self.event(name, "info", "Added nuget.config so C# builds work offline", "dotnet otherwise tries to reach nuget.org on every build, even with no packages.")
        except OSError:
            pass

    def stop_run(self, name):
        p = self.runs.pop(name, None)
        if p and p.poll() is None:
            p.kill()
            return {"ok": True}
        return {"ok": False}

    def _finish(self, name, rel, status, output):
        line = self._error_line(output, rel)
        self.event(name, "run", {"ok": "Ran %s" % rel, "error": "%s has an error" % rel, "running": "%s is running" % rel}[status], output, rel, line)
        return {"status": status, "output": output, "line": line, "file": rel}

    @staticmethod
    def _error_line(out, rel):
        base = os.path.basename(rel or "")
        hits = re.findall(r'File "([^"]+)", line (\d+)', out or "")
        hits = [h for h in hits if os.path.basename(h[0]) == base] or hits
        if hits:
            return int(hits[-1][1])
        m = re.search(re.escape(base) + r":(\d+)", out or "") if base else None
        return int(m.group(1)) if m else None

    # ------------------------------------------------------------------ build mode
    @staticmethod
    def _embed(texts):
        from archie_brain import embed
        return embed(texts)

    def _context(self, name, limit=24000, query=""):
        """The project as the model sees it. Small projects: every file in full. Bigger ones (project memory): a map of
        every file with its functions and classes, then the files that matter most for this request, in full."""
        code = [f for f in self.files(name) if f["text"] and f["size"] <= 60000]
        if sum(f["size"] for f in code) <= limit:
            self.shown[name] = None
            parts = ["<<<FILE %s>>>\n%s\n<<<END>>>" % (f["path"], self.read(name, f["path"])["text"]) for f in code]
            return "\n".join(parts) or "(the project is empty)"
        m = self.meta(name)
        texts = [{"path": f["path"], "mtime": f["mtime"], "text": self.read(name, f["path"])["text"]} for f in code]
        recent = {r for h in (m.get("history") or [])[-3:] for r in h.get("before", {})} | {f["path"] for f in code if _now() - f["mtime"] < 1800}
        ranked, idx = self.pmem.rank(self.folder(name), texts, query or m.get("goal", ""), m.get("entry", ""), recent)
        body = {t["path"]: t["text"] for t in texts}
        shown, parts = [], []
        room = limit - min(len(self.pmem.project_map(idx, set())), limit // 3)
        for path, score, why in ranked:
            t = body[path]
            if len(t) + 40 > room:
                continue
            if shown and score <= 0 and len(shown) >= 2:
                break
            shown.append(path)
            room -= len(t) + 40
            parts.append("<<<FILE %s>>>\n%s\n<<<END>>>" % (path, t))
        self.shown[name] = set(shown)
        pmap = self.pmem.project_map(idx, set(shown))
        if len(pmap) > limit // 3:
            pmap = pmap[:limit // 3] + "\n..."
        return ("PROJECT MAP (every file, with its functions and classes; only some are shown in full, so only change those):\n%s\n\n%s"
                % (pmap, "\n".join(parts)))

    @staticmethod
    def parse_files(text):
        out = []
        for m in re.finditer(r"<<<FILE\s+([^\n>]+?)\s*>>>\s*\n(.*?)\n?<<<END>>>", text or "", re.S):
            body = m.group(2)
            body = re.sub(r"^\s*```[\w+-]*\n", "", body)
            body = re.sub(r"\n```\s*$", "", body)
            out.append((m.group(1).strip().strip("`").lstrip("/\\"), body.rstrip() + "\n"))
        return out

    def _apply(self, name, files, what, seen=None):
        """Write the files Archie produced. seen: the files it was shown in full (None: all), so it can't cut short a file it only saw on the map."""
        m = self.meta(name)
        before = {}
        changed = []
        for rel, body in files:
            p = self._inside(name, rel)
            old = None
            if os.path.isfile(p):
                with open(p, encoding="utf-8", errors="replace") as f:
                    old = f.read()
            if old == body:
                continue
            if old is not None and seen is not None and rel not in seen:
                # Archie only knew this file from the project map: writing it would cut out everything it didn't see
                self.event(name, "error", "Didn't change %s" % rel, "Archie only had a summary of %s, not the whole file, so it left it alone. "
                           "Mention %s by name in your request and Archie will read it in full." % (rel, rel))
                continue
            before[rel] = old
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
            changed.append((rel, old, body))
        if before:
            m.setdefault("history", []).append({"at": _now(), "what": what[:200], "before": before})
            m["history"] = m["history"][-30:]
            m["updated"] = _now()
            self.save_meta(name, m)
            self.snap[name] = self._scan(name)
        return changed

    @staticmethod
    def diff(rel, old, new):
        d = difflib.unified_diff((old or "").splitlines(), (new or "").splitlines(), "before/" + rel, "after/" + rel, lineterm="", n=2)
        return "\n".join(list(d)[:400])

    def _build(self, name, request):
        m = self.meta(name)
        entry = m.get("entry") or LANGS.get(m.get("lang"), ("main.py",))[0]
        system = BUILD_RULES.format(entry=entry) + "\nLanguage: %s." % m.get("lang", "Python")
        self.event(name, "work", "Archie is writing code", request)
        lib, refs = self._lookup(m.get("lang"), request, k=2, kinds=("docs",))
        prompt = "Project goal: %s\n\nThe project's files now:\n%s\n\nRequest: %s%s%s" % (m.get("goal", ""), self._context(name, query=request), request, self._blocks_for_prompt(name, request), lib)
        seen = self.shown.get(name)
        ans = self._chat(system, prompt, tokens=3500)
        files = self.parse_files(ans)
        plan = (re.search(r"PLAN:\s*(.+)", ans or "") or [None, ""])[1].strip()
        if not files:
            self.event(name, "error", "Archie didn't produce any files", (ans or "")[:1500])
            return {"error": "no files", "answer": ans}
        changed = self._apply(name, files, request, seen)
        self.event(name, "change", plan or "Changed %d file%s" % (len(changed), "" if len(changed) == 1 else "s"),
                   "\n\n".join(self.diff(r, o, n) for r, o, n in changed)[:6000], refs=refs)
        touched = {r for r, _, _ in changed}
        res, bad = self._run_and_check(name, entry, touched)
        tries = 0
        while (res["status"] == "error" or bad) and tries < 3 and not self.stop.is_set():
            tries += 1
            self.event(name, "work", "Fixing the error (try %d of 3)" % tries, bad)
            what = []
            if res["status"] == "error":
                what.append("Running %s gave this error:\n%s" % (entry, res["output"][-3000:]))
            if bad:
                what.append("The checkers (compiler / linter) found these errors, with exact lines:\n" + bad)
            lib, refs = self._lookup(m.get("lang"), (res["output"][-600:] if res["status"] == "error" else "") + "\n" + bad[:600], k=2)
            ctx = self._context(name, query="\n".join(what)[:3000] + "\n" + request)
            seen = self.shown.get(name)
            ans = self._chat(system, "The project's files now:\n%s\n\n%s\n\nFix it. Change only what's needed.%s" % (ctx, "\n\n".join(what), lib), tokens=3500)
            files = self.parse_files(ans)
            if not files:
                break
            why = (res["output"].strip().splitlines()[-1][:120] if res["status"] == "error" and res["output"].strip() else bad.splitlines()[0][:120] if bad else "")
            changed = self._apply(name, files, "fix: " + why if why else "fix", seen)
            touched |= {r for r, _, _ in changed}
            self.event(name, "change", "Fixed: " + ((re.search(r"PLAN:\s*(.+)", ans or "") or [None, ""])[1].strip() or "changed %d file(s)" % len(changed)),
                       "\n\n".join(self.diff(r, o, n) for r, o, n in changed)[:6000], refs=refs)
            res, bad = self._run_and_check(name, entry, touched)
        if res["status"] != "error" and bad:
            res = dict(res, status="error", output=bad)
        done = {"ok": "Done, and it runs.", "running": "Done: it's running now.", "preview": "Done: open the preview to see it.",
                "error": "It still has an error after 3 tries. Read the error with Archie, or ask for a smaller change."}[res["status"]]
        self.event(name, "done", done, res.get("output", "")[-1500:])
        self.alert("Workshop · " + name, done)
        return res

    def _run_and_check(self, name, entry, rels):
        """Run the program, then let the real checkers look at the files that changed. Returns (run result, error text or "")."""
        res = self.run(name, entry)
        found = self.lint_project(name, deep=True, rels=set(rels) | {entry})
        bad = self._problem_text(found, errors_only=True)
        warn = self._problem_text({k: dict(v, problems=[p for p in v["problems"] if p["sev"] != "error"]) for k, v in found.items()}, limit=6)
        if warn and not bad:
            self.event(name, "lint", "The checkers have a few suggestions (not errors)", warn)
        return res, bad

    # ------------------------------------------------------------------ the template library
    def _current(self, name):
        def cur(rel):
            try:
                p = self._inside(name, rel)
            except ValueError:
                return None
            if not os.path.isfile(p):
                return None
            with open(p, encoding="utf-8", errors="replace") as f:
                return f.read()
        return cur

    def add_blocks(self, name, ids):
        files, installed, notes = self.blocks.files_for(ids, self._current(name))
        if not files:
            return {"error": "Nothing to add.", "notes": notes}
        changed = self._apply(name, files, "added blocks: " + ", ".join(ids))
        m = self.meta(name)
        m.setdefault("blocks", {}).update(installed)
        self.save_meta(name, m)
        self.event(name, "change", "Added %s" % ", ".join(self.blocks.get(i).get("name", i) for i in installed if self.blocks.get(i)),
                   ("\n".join(notes) + "\n\n" if notes else "") + "\n\n".join(self.diff(r, o, n) for r, o, n in changed)[:6000])
        return {"ok": True, "added": sorted(installed), "notes": notes}

    def block_updates(self, name):
        return {"updates": self.blocks.updates(self.meta(name).get("blocks"), self._current(name))}

    def update_blocks(self, name, ids=None, force=False):
        ups = self.blocks.updates(self.meta(name).get("blocks"), self._current(name))
        done, skipped = [], []
        rt = self.runtimes()
        for u in ups:
            if ids and u["id"] not in ids:
                continue
            if u["you_changed"] and not force:
                skipped.append({"id": u["id"], "why": "you changed " + ", ".join(u["you_changed"])})
                continue
            t = self.blocks.test(u["id"], rt)
            if t["ok"] is False:
                skipped.append({"id": u["id"], "why": "the new version failed its test on this PC", "output": t["output"][-800:]})
                continue
            files, rec, _ = self.blocks.update_files(u["id"], self._current(name))
            self._apply(name, files, "update block %s %s -> %s" % (u["id"], u["have"], u["now"]))
            m = self.meta(name)
            m.setdefault("blocks", {}).update(rec)
            self.save_meta(name, m)
            done.append(u)
        if done or skipped:
            self.event(name, "change", "Updated %d block%s" % (len(done), "" if len(done) == 1 else "s"),
                       "\n".join("%s %s -> %s: %s" % (u["name"], u["have"], u["now"], "; ".join(c.get("note", "") for c in u["changes"])) for u in done) +
                       ("\nSkipped: " + "; ".join("%s (%s)" % (s["id"], s["why"]) for s in skipped) if skipped else ""))
        return {"updated": [u["id"] for u in done], "skipped": skipped}

    def save_block(self, name, b):
        rels = [r for r in (b.get("files") or []) if isinstance(r, str)]
        lang = self.meta(name).get("lang", "Python")
        r = self.blocks.save_block(self.folder(name), rels, b.get("block_name") or "", b.get("summary") or "", lang, b.get("kind") or "feature",
                                   re.split(r"[,\s]+", b.get("tags") or ""), b.get("use") or "")
        if r.get("ok"):
            self.event(name, "info", "Saved as a block: %s (v%s)" % (b.get("block_name"), r["version"]), "It's in your library now, for any project.")
        return r

    def guide(self, m):
        """How the project works: the recipe's overview, parts and wiring, and what each file is for (from the blocks)."""
        rec = self.blocks.recipe(m["recipe"]) if m.get("recipe") else None
        g = dict((rec or {}).get("guide") or {})
        files = {f["file"]: f for f in g.get("files") or []}
        lib = self.blocks.all()
        for bid in (m.get("blocks") or {}):
            c = lib.get(bid)
            if not c or c.get("kind") == "shell":
                continue
            for dest in (c.get("files") or {}):
                if dest.endswith("__init__.py"):
                    continue
                f = files.setdefault(dest, {"file": dest})
                f.setdefault("why", c.get("explain") or c.get("summary", ""))
                f.setdefault("block", c.get("name", bid))
                if c.get("points") and "points" not in f:
                    f["points"] = c["points"]
        if not files and not g:
            return None
        order = g.get("order") or []
        g["files"] = sorted(files.values(), key=lambda f: (order.index(f["file"]) if f["file"] in order else 99, f["file"]))
        g["parts"] = g.get("parts") or (rec or {}).get("parts") or []
        g["name"] = (rec or {}).get("name", "")
        g["can_teach"] = bool(g.get("lessons"))
        g.pop("lessons", None)
        g.pop("starter", None)
        return g

    def _blocks_for_prompt(self, name, request, limit=3):
        """Known-good blocks that match the request, as reference code for the model."""
        m = self.meta(name)
        have = set(m.get("blocks") or {})
        cands = [c for c in self.blocks.search(request, lang=m.get("lang")) if c["kind"] != "shell" and c["id"] not in have][:limit]
        if not cands:
            return ""
        out = []
        for c in cands:
            full = self.blocks.card(self.blocks.get(c["id"]), code=True)
            out.append("BLOCK %s: %s\nUse: %s\nImport: %s\n%s" % (c["id"], c.get("summary", ""), c.get("use", ""),
                       " / ".join(sum((c.get("imports") or {}).values(), [])),
                       "\n".join("<<<FILE %s>>>\n%s\n<<<END>>>" % (k, v) for k, v in full.get("code", {}).items())))
        return ("\n\nTested building blocks from the library that fit this request. If they help, copy them into the project unchanged "
                "(same paths) and use them instead of writing that part from scratch:\n\n" + "\n\n".join(out))[:14000]

    # ------------------------------------------------------------------ deleting (always recoverable)
    def trash_dir(self):
        return os.path.join(self.dir, ".trash")

    def delete_project(self, name):
        """A Workshop project goes to Workshop/.trash (restore it any time). A linked folder is only unlinked:
        Archie never deletes a folder of yours that lives somewhere else."""
        if name in self.links:
            self.links.pop(name)
            self._jsave(os.path.join(self.dir, "linked.json"), self.links)
            self.snap.pop(name, None)
            return {"ok": True, "unlinked": True}
        src = self.folder(name)
        if not os.path.isdir(src) or os.path.dirname(os.path.realpath(src)) != os.path.realpath(self.dir):
            return {"error": "no such project"}
        self.stop_run(name)
        os.makedirs(self.trash_dir(), exist_ok=True)
        dst = os.path.join(self.trash_dir(), "%s--%s" % (os.path.basename(src), time.strftime("%Y%m%d-%H%M%S")))
        shutil.move(src, dst)
        self.snap.pop(name, None)
        return {"ok": True, "trashed": os.path.basename(dst)}

    def trash(self):
        d = self.trash_dir()
        if not os.path.isdir(d):
            return {"items": []}
        out = []
        for f in sorted(os.listdir(d), reverse=True):
            p = os.path.join(d, f)
            if os.path.isdir(p):
                kind = "block" if f.startswith("block--") else "game" if f.startswith("game--") else "project"
                out.append({"id": f, "name": f.split("--")[1] if kind != "project" else f.rsplit("--", 1)[0], "when": f.rsplit("--", 1)[-1] if "--" in f else "",
                            "kind": kind})
        return {"items": out}

    def restore(self, tid):
        src = os.path.join(self.trash_dir(), os.path.basename(tid or ""))
        if not tid or not os.path.isdir(src):
            return {"error": "Not in the trash."}
        if tid.startswith("block--"):
            name = tid.split("--")[1]
            dst = os.path.join(self.dir, ".blocks", name)
        elif tid.startswith("game--"):
            name = tid.split("--")[1]
            dst = os.path.join(self.dir, ".games", name)
        else:
            name = tid.rsplit("--", 1)[0]
            dst = os.path.join(self.dir, name)
        if os.path.exists(dst):
            return {"error": "There's already a %s called %s. Rename or delete that one first." % (tid.split("--")[0] if tid.startswith(("block--", "game--")) else "project", name)}
        shutil.move(src, dst)
        return {"ok": True, "name": name}

    def empty_trash(self):
        """The only permanent delete, and only from the trash."""
        d = self.trash_dir()
        n = 0
        if os.path.isdir(d):
            for f in os.listdir(d):
                shutil.rmtree(os.path.join(d, f), ignore_errors=True)
                n += 1
        return {"ok": True, "removed": n}

    def reset_lessons(self, name):
        """Throw away the lesson plan (your code stays) so Archie can plan new lessons."""
        m = self.meta(name)
        if m.pop("lesson", None) is None:
            return {"error": "No lessons to reset."}
        self.save_meta(name, m)
        self.event(name, "info", "Lessons cleared", "Your files are untouched. Press plan the lessons for a new plan, or change the goal first.")
        return {"ok": True}

    def set_goal(self, name, goal):
        m = self.meta(name)
        m["goal"] = (goal or "").strip()[:2000]
        self.save_meta(name, m)
        return {"ok": True}

    def delete_block(self, bid):
        c = self.blocks.get(bid)
        if not c or c.get("source") != "mine":
            return {"error": "Only blocks you saved yourself can be deleted. The library's own blocks stay."}
        os.makedirs(self.trash_dir(), exist_ok=True)
        shutil.move(c["dir"], os.path.join(self.trash_dir(), "block--%s--%s" % (bid, time.strftime("%Y%m%d-%H%M%S"))))
        return {"ok": True}

    def undo(self, name):
        m = self.meta(name)
        h = m.get("history") or []
        if not h:
            return {"error": "Nothing to undo."}
        last = h.pop()
        for rel, old in last["before"].items():
            p = self._inside(name, rel)
            if old is None:
                if os.path.isfile(p):
                    os.remove(p)      # a file Archie made in that step: take it back out
            else:
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(old)
        m["history"] = h
        m["updated"] = _now()
        self.save_meta(name, m)
        self.snap[name] = self._scan(name)
        self.event(name, "change", "Undid: " + last["what"])
        return {"ok": True}

    # ------------------------------------------------------------------ teach mode
    def _plan_lesson(self, name):
        m = self.meta(name)
        self.event(name, "work", "Archie is planning your lessons")
        prompt = ("Plan a beginner-friendly %s project, built step by step by the learner: %s\n"
                  "Return JSON: {\"title\": short title, \"steps\": [5 to 8 steps, each {\"title\": short, \"concept\": the one new idea, "
                  "\"explain\": 3 to 6 sentences teaching the idea in plain words, with a tiny example, \"task\": exactly what to write or change "
                  "in %s this step, \"check\": what the program should do or print when the step is done}]}. "
                  "Each step builds on the last and ends with something the learner can run.") % (m.get("lang"), m.get("goal"), m.get("entry"))
        raw = self._chat(TEACH_RULES, prompt, tokens=2500, json_mode=True)
        try:
            plan = json.loads(raw)
            steps = [s for s in plan.get("steps") or [] if isinstance(s, dict) and s.get("task")]
        except ValueError:
            steps = []
        if not steps:
            self.event(name, "error", "Archie couldn't plan the lessons", (raw or "")[:800])
            return {"error": "no plan"}
        m["lesson"] = {"title": plan.get("title") or m.get("goal"), "steps": steps[:8], "current": 0, "done": []}
        m["updated"] = _now()
        self.save_meta(name, m)
        p = self._inside(name, m["entry"])
        if not os.path.exists(p):
            cm = "#" if m["entry"].endswith((".py", ".gd")) else "//"
            starter = {"index.html": "<!-- %s -->\n<!-- Step 1: %s -->\n" % (m["lesson"]["title"], steps[0].get("title", ""))}.get(os.path.basename(m["entry"]),
                       "%s %s\n%s Step 1: %s\n%s %s\n" % (cm, m["lesson"]["title"], cm, steps[0].get("title", ""), cm, steps[0].get("task", "")))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                f.write(starter)
            self.snap[name] = self._scan(name)
        self.event(name, "lesson", "Your lessons are ready: %d steps" % len(steps), "\n".join("%d. %s" % (i + 1, s.get("title", "")) for i, s in enumerate(steps)))
        return {"ok": True}

    def _step(self, m):
        L = m.get("lesson") or {}
        S = L.get("steps") or []
        i = L.get("current", 0)
        return (S[i] if i < len(S) else None), i, len(S)

    def check(self, name):
        m = self.meta(name)
        step, i, n = self._step(m)
        if not step:
            return {"error": "All the steps are done."}
        res = self.run(name, m.get("entry"), wait=5)
        lint = self.lint(name, m.get("entry"), deep=True) if m.get("entry") else {"ok": True, "problems": []}
        code = self._context(name, 12000, query="%s %s %s" % (step.get("title") or "", step.get("task") or "", res["output"][-600:]))
        lib, refs = self._lookup(m.get("lang"), "%s %s %s" % (step.get("concept") or "", step.get("title") or "", res["output"][-400:] if res["status"] == "error" else ""), k=2)
        prompt = ("Step %d of %d. Idea: %s\nTask: %s\nWhen it's done: %s\n\nThe learner's code:\n%s\n\nWhat happened when Archie ran it (%s):\n%s\n\nWhat the checker found: %s\n\n"
                  "Did they complete THIS step (not later ones)? Return JSON: {\"pass\": true or false, \"feedback\": 2 to 4 friendly sentences about what "
                  "they did, \"hint\": if not passed, one nudge without giving the code, \"cards\": if passed, 1 or 2 flashcards about the idea, each "
                  "{\"q\": a question, \"a\": a short answer}}") % (i + 1, n, step.get("concept"), step.get("task"), step.get("check"), code, res["status"], res["output"][-2000:],
                     checkers.as_text(m.get("entry"), lint, 8) or "no problems") + lib
        raw = self._chat(TEACH_RULES, prompt, tokens=700, json_mode=True)
        try:
            v = json.loads(raw)
        except ValueError:
            v = {"pass": False, "feedback": "Archie couldn't judge that one. Try check again.", "hint": ""}
        ok = bool(v.get("pass")) and res["status"] != "error" and lint["ok"]
        src = self.read(name, m.get("entry"))["text"] if m.get("entry") else ""
        missing = [x for x in step.get("must") or [] if x.replace(" ", "") not in src.replace(" ", "")]
        if missing and not ok:
            pass
        elif missing:
            ok = False
            v["feedback"] = "Almost: the step also needs %s in %s. " % (" and ".join("`%s`" % x for x in missing), m.get("entry")) + (v.get("feedback") or "")
        elif step.get("must") and res["status"] != "error" and lint["ok"] and not ok and m.get("lesson", {}).get("prewritten"):
            ok = True                 # every required piece is there, it compiles/runs and the checker is happy: trust the tests over the model
            v["feedback"] = "It %s and has everything this step needs. Next, see it work for real: %s" % ("compiles" if m.get("entry", "").endswith(".ino") else "runs", step.get("check") or "")
        if not lint["ok"]:
            err = next(p for p in lint["problems"] if p["sev"] == "error")
            v["hint"] = v.get("hint") or ""
            v["feedback"] = ("The checker found an error on line %s: %s. Fix that first. " % (err["line"] or "?", err["msg"])) + (v.get("feedback") or "")
            res = dict(res, line=res.get("line") or err["line"])
        if ok:
            L = m["lesson"]
            L.setdefault("done", []).append({"step": i, "at": _now()})
            L["current"] = i + 1
            m["updated"] = _now()
            self.save_meta(name, m)
            cards = [c for c in v.get("cards") or [] if isinstance(c, dict) and c.get("q") and c.get("a")]
            if cards and self.study_dir:
                try:
                    import archie_study
                    archie_study.Study(self.study_dir).add_cards("Coding - " + re.sub(r"\s*\(.*", "", m.get("lang", "Python")), cards[:2], source="Workshop: " + name)
                except Exception:      # flashcards are a bonus; the lesson goes on
                    pass
            nxt = L["steps"][i + 1] if i + 1 < len(L["steps"]) else None
            self.event(name, "pass", "Step %d done" % (i + 1), (v.get("feedback") or "") + ("\n\nNext: " + nxt.get("title", "") if nxt else "\n\nThat's the whole project. Nice work."), refs=refs)
        else:
            self.event(name, "tryagain", "Not quite yet", (v.get("feedback") or "") + ("\n\nHint: " + v["hint"] if v.get("hint") else ""),
                       m.get("entry"), res.get("line"), refs=refs)
            if v.get("hint") and res.get("line"):
                self._hint(name, m.get("entry"), res["line"], v["hint"])
        return {"pass": ok, "feedback": v.get("feedback", ""), "hint": v.get("hint", ""), "run": res}

    def hint(self, name):
        m = self.meta(name)
        step, i, n = self._step(m)
        if not step:
            return {"error": "All the steps are done."}
        lib, refs = self._lookup(m.get("lang"), "%s %s" % (step.get("concept") or "", step.get("title") or ""), k=2, kinds=("docs",))
        ans = self._chat(TEACH_RULES, "Step: %s\nTask: %s\nTheir code:\n%s\n\nGive ONE hint (2 or 3 sentences) that points them the right way without writing the code for them. "
                         "If a reference page below explains the idea, point them to it by name.%s"
                         % (step.get("title"), step.get("task"), self._context(name, 10000, query="%s %s" % (step.get("title"), step.get("task"))), lib), tokens=260, temp=0.4)
        self.event(name, "hint", "Hint for step %d" % (i + 1), ans, refs=refs)
        return {"text": ans}

    def show(self, name):
        m = self.meta(name)
        step, i, n = self._step(m)
        if not step:
            return {"error": "All the steps are done."}
        if step.get("code"):          # written ahead of time and tested: show that, not a guess
            ans = "```\n%s\n```\n%s" % (step["code"].rstrip(), step.get("code_notes", "Type it in yourself rather than pasting: your fingers learn too."))
            self.event(name, "show", "How to do step %d" % (i + 1), ans)
            return {"text": ans}
        lib, refs = self._lookup(m.get("lang"), "%s %s %s" % (step.get("concept") or "", step.get("title") or "", step.get("task") or ""), k=2, kinds=("docs",))
        ans = self._chat(TEACH_RULES, "Step: %s\nTask: %s\nTheir code:\n%s\n\nShow the code for just this step as a short snippet in a code block, then explain each line in one sentence. "
                         "Tell them where it goes. Don't rewrite the rest of their program.%s" % (step.get("title"), step.get("task"), self._context(name, 10000, query="%s %s" % (step.get("title"), step.get("task"))), lib), tokens=700)
        self.event(name, "show", "How to do step %d" % (i + 1), ans, refs=refs)
        return {"text": ans}

    def skip(self, name, back=False):
        m = self.meta(name)
        L = m.get("lesson") or {}
        L["current"] = max(0, min(len(L.get("steps") or []), L.get("current", 0) + (-1 if back else 1)))
        self.save_meta(name, m)
        return {"ok": True}

    # ------------------------------------------------------------------ explain (from the Workshop or VSCodium)
    def project_of(self, path):
        if not path:
            return ""
        rp = os.path.realpath(path)
        for n in list(self.links) + [d for d in os.listdir(self.dir) if os.path.isdir(os.path.join(self.dir, d))]:
            root = os.path.realpath(self.folder(n))
            if rp.startswith(root + os.sep):
                return n
        return ""

    def ask(self, b):
        file, sel, q = b.get("file") or "", (b.get("selection") or "")[:4000], (b.get("question") or "").strip()
        line = b.get("line")
        name = b.get("project") or self.project_of(file)
        text = ""
        if file and os.path.isfile(file):
            with open(file, encoding="utf-8", errors="replace") as f:
                text = f.read()[:16000]
        elif name and b.get("path"):
            text = self.read(name, b["path"]).get("text", "")[:16000]
            file = os.path.join(self.folder(name), b["path"])
        if not sel and line and text:
            L = text.splitlines()
            sel = "\n".join(L[max(0, line - 3):line + 2])
        code_names = " ".join(dict.fromkeys(w for w in archie_docs.terms_of(sel or text[:1500], 12) if archie_docs._is_name(w)))
        lib, refs = self._lookup(self._lang(name, file), (q + "\n" + code_names) if q else (sel or text[:1500])[:2500], k=3, extra=text[:3000])
        rest = ""
        if name and len([f for f in self.files(name) if f["text"]]) > 1:     # the rest of the project, as much as matters for this question
            rest = "\n\nThe rest of the project (for context):\n" + self._context(name, 9000, query="%s\n%s" % (q, sel or text[:1500]))
            self.shown.pop(name, None)       # an answer never edits files, so this view mustn't limit the next build
        prompt = ("File %s:\n%s\n\nThe part they're asking about%s:\n%s\n\n%s%s%s" %
                  (os.path.basename(file), text, (" (around line %s)" % line) if line else "", sel or "(the whole file)",
                   q or "Explain what this does in plain words, line by line if it's short. Point out anything that looks wrong.", rest, lib))
        ans = self._chat(TEACH_RULES, prompt, tokens=800)
        self.event(name, "explain", (q[:80] or "What %s does" % ("this part of " + os.path.basename(file) if sel else os.path.basename(file))), ans, os.path.basename(file), line, refs=refs)
        return {"text": ans}

    def _hint(self, name, rel, line, text):
        if not rel or not line:
            return
        p = os.path.realpath(os.path.join(self.folder(name), rel))
        with self.lock:
            self.hints[p.lower()] = [{"line": int(line), "text": re.sub(r"\s+", " ", text)[:300], "at": _now()}]

    def hints_for(self, file):
        if not file:
            return {"hints": []}
        k = os.path.realpath(file).lower()
        H = self.hints.get(k, [])
        return {"hints": [h for h in H if _now() - h["at"] < 3600], "problems": self.problems.get(k, [])}

    def set_editor(self, b):
        f = b.get("file") or ""
        self.editor = {"file": f, "name": os.path.basename(f), "line": b.get("line"), "selection": (b.get("selection") or "")[:2000],
                       "language": b.get("language") or "", "at": _now(), "project": self.project_of(f)}
        return {"ok": True, "project": self.editor["project"]}

    # ------------------------------------------------------------------ watching the folder
    def _scan(self, name, old=None):
        out = {}
        root = self.folder(name)
        for f in self.files(name):
            if not f["text"] or f["size"] > 200000:
                continue
            if old and f["path"] in old and old[f["path"]][0] == f["mtime"]:
                out[f["path"]] = old[f["path"]]      # unchanged since last look: don't re-read it
                continue
            try:
                with open(os.path.join(root, f["path"]), encoding="utf-8", errors="replace") as fh:
                    out[f["path"]] = (f["mtime"], fh.read())
            except OSError:
                pass
        return out

    def lint(self, name, rel, deep=False):
        """Run the real checker for this file (compiler, ruff, node...) and remember what it found."""
        p = self._inside(name, rel)
        res = checkers.check(p, self.runtimes(), self.folder(name), deep=deep, board=self.meta(name).get("board"))
        if not res.get("skipped"):
            with self.lock:
                self.problems[os.path.realpath(p).lower()] = [dict(x, at=_now()) for x in res["problems"]]
        return res

    def lint_project(self, name, deep=True, rels=None):
        """Check every code file (or just rels). Returns {rel: result} for files with something to say."""
        out = {}
        for f in self.files(name):
            if not f["text"] or (rels is not None and f["path"] not in rels):
                continue
            if os.path.splitext(f["path"])[1].lower() not in checkers.FAST | checkers.SLOW:
                continue
            r = self.lint(name, f["path"], deep=deep)
            if r["problems"]:
                out[f["path"]] = r
        return out

    @staticmethod
    def _problem_text(found, errors_only=False, limit=12):
        lines = []
        for rel, r in found.items():
            sub = dict(r, problems=[p for p in r["problems"] if p["sev"] == "error"]) if errors_only else r
            t = checkers.as_text(rel, sub, limit)
            if t:
                lines.append(t)
        return "\n".join(lines)

    def check_all(self, name):
        found = self.lint_project(name, deep=True)
        if not found:
            self.event(name, "lint", "Checked every file: no problems found")
            return {"ok": True, "found": {}}
        errs = sum(1 for r in found.values() for p in r["problems"] if p["sev"] == "error")
        warns = sum(len(r["problems"]) for r in found.values()) - errs
        first = next(((rel, p) for rel, r in found.items() for p in r["problems"]), (None, {}))
        self.event(name, "lint", "Checked every file: %d error%s, %d warning%s" % (errs, "" if errs == 1 else "s", warns, "" if warns == 1 else "s"),
                   self._problem_text(found, limit=20), first[0] or "", first[1].get("line"))
        return {"ok": errs == 0, "found": {k: v["problems"] for k, v in found.items()}}

    def get_arduino_core(self):
        """Install the Arduino Uno/Nano board support for arduino-cli. Needs internet once."""
        rt = self.runtimes()
        if "arduino" not in rt:
            return {"ok": False, "error": "arduino-cli isn't installed (Get Code Editor.bat can add it)."}
        self.event("", "work", "Getting Arduino board support")
        out = ""
        for cmd in (["core", "update-index"], ["core", "install", "arduino:avr"], ["lib", "install", "DHT sensor library"]):
            c = subprocess.run([rt["arduino"]] + cmd, capture_output=True, text=True, timeout=900, creationflags=0x08000000 if os.name == "nt" else 0)
            out += c.stdout + c.stderr
        c = subprocess.run([rt["arduino"], "core", "list"], capture_output=True, text=True, timeout=60, creationflags=0x08000000 if os.name == "nt" else 0)
        ok = "arduino:avr" in c.stdout
        self._ard_ok = ok
        self.event("", "done" if ok else "error", "Arduino board support is ready" if ok else "Arduino board support didn't install", "" if ok else out[-1500:])
        return {"ok": ok}

    def arduino_ready(self):
        rt = self.runtimes()
        if "arduino" not in rt:
            return False
        if getattr(self, "_ard_ok", None) is None:
            try:
                c = subprocess.run([rt["arduino"], "core", "list"], capture_output=True, text=True, timeout=30, creationflags=0x08000000 if os.name == "nt" else 0)
                self._ard_ok = "arduino:avr" in c.stdout
            except (OSError, subprocess.SubprocessError):
                self._ard_ok = False
        return self._ard_ok

    def get_ruff(self):
        """Install ruff (the Python checker) into the Python Archie uses. Needs internet once."""
        py = self.runtimes()["python"]
        self.event("", "work", "Getting ruff, the Python checker")
        c = subprocess.run([py, "-m", "pip", "install", "--user", "--upgrade", "ruff"], capture_output=True, text=True, timeout=600,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        checkers.forget_ruff()
        ok = bool(checkers.ruff_cmd(self.runtimes()))
        self.event("", "done" if ok else "error", "ruff is ready: Python files get the deeper check now" if ok else "ruff didn't install",
                   "" if ok else (c.stdout + c.stderr)[-1500:])
        return {"ok": ok}

    def _watch_loop(self):
        while not self.stop.is_set():
            time.sleep(2)
            try:
                names = set(self.links) | {d for d in os.listdir(self.dir) if os.path.isdir(os.path.join(self.dir, d)) and not d.startswith(".")}
                names = [n for n in names if self.meta(n).get("watch", True)]
            except Exception:      # noqa: BLE001 - the folder may be mid-change; try next time
                continue
            for name in names:
                if name not in self.snap:
                    self.snap[name] = self._scan(name)
                    continue
                old = self.snap[name]
                new = self._scan(name, old)
                if old == new:
                    continue
                self.snap[name] = new
                for rel, (mt, text) in new.items():
                    if rel in old and old[rel][1] == text:
                        continue
                    before = old.get(rel, (0, ""))[1]
                    added = sum(1 for l in difflib.ndiff(before.splitlines(), text.splitlines()) if l.startswith("+ "))
                    removed = sum(1 for l in difflib.ndiff(before.splitlines(), text.splitlines()) if l.startswith("- "))
                    s = self.lint(name, rel)
                    p = os.path.realpath(os.path.join(self.folder(name), rel)).lower()
                    if s["ok"]:
                        m = self.meta(name)
                        step, i, n = self._step(m) if m.get("mode") in ("teach", "course") else (None, 0, 0)
                        tip = ("\nNo errors so far. When you think step %d is done, press check my work (Ctrl+Alt+K in VSCodium)." % (i + 1)) if step else ""
                        warn = ("\nThe checker (%s) noticed %s:\n%s" % (s["tool"], s["summary"], checkers.as_text(rel, s, 8))) if s["problems"] else ""
                        self.event(name, "saved", "You saved %s" % rel, "+%d / -%d lines" % (added, removed) + warn + tip, rel,
                                   s["problems"][0]["line"] if s["problems"] else None)
                        self.hints.pop(p, None)
                    else:
                        first = next(x for x in s["problems"] if x["sev"] == "error")
                        self.event(name, "syntax", "%s won't run yet: line %s" % (rel, first["line"] or "?"),
                                   "%s found: %s\n%s" % (s["tool"], s["summary"], checkers.as_text(rel, s, 10)), rel, first["line"])
                        threading.Thread(target=self._explain_error, args=(name, rel, {"line": first["line"], "error": first["msg"]}, text), daemon=True).start()

    def _explain_error(self, name, rel, s, text):
        L = text.splitlines()
        ln = s.get("line") or 1
        around = "\n".join("%4d  %s" % (i + 1, L[i]) for i in range(max(0, ln - 4), min(len(L), ln + 2)))
        lib, refs = self._lookup(self._lang(name, rel), "%s\n%s" % (s["error"], L[ln - 1] if 0 < ln <= len(L) else ""), k=2, extra=text[:2000])
        ans = self._chat(TEACH_RULES, "This error came up in %s:\n%s\n\nThe lines around it:\n%s\n\nIn 2 or 3 plain sentences: what the error means and what to look at to fix it. "
                         "Don't rewrite their code.%s" % (rel, s["error"], around, lib), tokens=240, temp=0.3)
        self.event(name, "explain", "What that error means", ans, rel, s.get("line"), refs=refs)
        self._hint(name, rel, s.get("line"), ans)

    def set_watch(self, name, on):
        m = self.meta(name)
        m["watch"] = bool(on)
        self.save_meta(name, m)
        return {"ok": True}

    def open_codium(self, name, rel=""):
        rt = self.runtimes()
        if "codium" not in rt:
            return {"error": "VSCodium isn't installed yet. Run Get Code Editor.bat in the Archie folder."}
        args = [rt["codium"], self.folder(name)] + ([self._inside(name, rel)] if rel else [])
        subprocess.Popen(args, shell=rt["codium"].lower().endswith(".cmd"), creationflags=0x08000000 if os.name == "nt" else 0)
        return {"ok": True}

    def open_folder(self, name):
        if os.name == "nt":
            os.startfile(self.folder(name))      # noqa: S606 - opens Explorer on the project folder
        return {"ok": True}

    # ------------------------------------------------------------------ routes (the World server hands /api/ws/* here)
    def get(self, what, a):
        if what == "state":
            return self.state()
        if what == "token":
            return {"token": self.token}
        if what == "project":
            return self.project(a("name"))
        if what == "file":
            return self.read(a("name"), a("path"))
        if what == "job":
            j = self.jobs.get(a("id"))
            return j or {"status": "gone"}
        if what == "events":
            since = int(a("since", "0") or 0)
            return {"events": [e for e in self.events if e["n"] > since and (not a("name") or e["project"] == a("name"))][-60:], "editor": self.editor}
        if what == "hints":
            return self.hints_for(a("file"))
        if what == "lint":
            return self.lint(a("name"), a("path"), deep=a("deep", "") == "1")
        if what == "blocks":
            return {"blocks": self.blocks.search(a("q", ""), lang=a("lang") or None, kind=a("kind") or None)}
        if what == "block":
            c = self.blocks.get(a("id"))
            return self.blocks.card(c, code=True) if c else {"error": "no such block"}
        if what == "updates":
            return self.block_updates(a("name"))
        if what == "courses":
            return self.course_list()
        if what == "games":
            return self.coach.games()
        if what == "game":
            return self.coach.get(a("id"))
        if what == "docs_status":
            return self.docs.status()
        if what == "docs":
            return self.docs.browse(a("lang") or self._lang(a("name")), a("q", ""))
        if what == "docpage":
            return self.docs.page(a("zim"), a("path"))
        if what == "trash":
            return self.trash()
        if what == "course":
            return self.course_state(a("name"))
        if what == "unit":
            return self.open_unit(a("name"), a("id"))
        if what == "diff":
            m = self.meta(a("name"))
            h = (m.get("history") or [])
            if not h:
                return {"diff": ""}
            last = h[-1]
            out = []
            for rel, old in last["before"].items():
                try:
                    new = self.read(a("name"), rel)["text"]
                except (OSError, ValueError):
                    new = ""
                out.append(self.diff(rel, old, new))
            return {"what": last["what"], "diff": "\n\n".join(out)}
        return None

    def post(self, what, b):
        n = b.get("name", "")
        if what == "new":
            return self.new(b)
        if what == "build":
            return self._job(self._build, n, (b.get("request") or "").strip()[:4000])
        if what == "run":
            return self.run(n, b.get("path"))
        if what == "stop":
            return self.stop_run(n)
        if what == "undo":
            return self.undo(n)
        if what == "check":
            return self._job(self.check, n)
        if what == "plan":
            return self._job(self._plan_lesson, n)
        if what == "check_file":
            n = self.project_of(b.get("file", ""))
            if n and self.meta(n).get("mode") == "course":
                return self._job(self.course_check, n, b.get("file"))
            return self._job(self.check, n) if n else {"error": "That file isn't in a Workshop project. Link its folder in the Workshop first."}
        if what == "start_course":
            return self.start_course(b.get("course", ""))
        if what == "course_check":
            return self._job(self.course_check, n, None, b.get("unit"), b.get("ex"))
        if what == "course_hint":
            return self._job(self.course_hint, n, b.get("unit"), b.get("ex"))
        if what == "course_solution":
            return self.course_solution(n, b.get("unit"), b.get("ex"))
        if what == "course_why":
            return self._job(self.course_why, n, b.get("unit"), b.get("ex"))
        if what == "course_testout":
            return self.course_testout(n, b.get("unit"))
        if what == "course_quiz":
            return self.course_quiz(n, b.get("unit"), [x if isinstance(x, int) else None for x in b.get("answers") or []])
        if what == "course_explain":
            return self._job(self.course_explain, n, b.get("unit"), b.get("text", ""))
        if what == "hint":
            n = n or self.project_of(b.get("file", ""))
            if n and self.meta(n).get("mode") == "course" and b.get("file"):
                u, e = self._find_ex(n, b["file"])
                return self._job(self.course_hint, n, u["id"], e["id"]) if e else {"error": "That file isn't a course exercise."}
            return self._job(self.hint, n)
        if what == "show":
            return self._job(self.show, n)
        if what == "skip":
            return self.skip(n, bool(b.get("back")))
        if what == "ask":
            return self._job(self.ask, b)
        if what == "editor":
            return self.set_editor(b)
        if what == "lint":
            n = n or self.project_of(b.get("file", ""))
            return self._job(self.check_all, n) if n else {"error": "That file isn't in a Workshop project."}
        if what == "get_ruff":
            return self._job(self.get_ruff)
        if what == "get_arduino_core":
            self._ard_ok = None
            return self._job(self.get_arduino_core)
        if what == "add_blocks":
            return self.add_blocks(n, [i for i in b.get("ids") or [] if isinstance(i, str)])
        if what == "update_blocks":
            return self._job(self.update_blocks, n, b.get("ids"), bool(b.get("force")))
        if what == "save_block":
            return self.save_block(n, b)
        if what == "test_block":
            return self._job(lambda bid: self.blocks.test(bid, self.runtimes()), b.get("id", ""))
        if what == "watch":
            return self.set_watch(n, b.get("on"))
        if what == "game_new":
            return self.coach.new(b)
        if what == "game_say":
            return self._job(self.coach.say, b.get("id", ""), b.get("text", ""))
        if what == "game_edit":
            return self.coach.edit(b)
        if what == "game_mem":
            return self.coach.memory(b)
        if what == "game_delete":
            return self.coach.delete(b.get("id", ""), self.trash_dir())
        if what == "docs_on":
            self.docs.set_enabled(bool(b.get("on")))
            return self.docs.status()
        if what == "codium":
            return self.open_codium(n, b.get("path", ""))
        if what == "folder":
            return self.open_folder(n)
        if what == "delete":
            return self.delete_project(n)
        if what == "restore":
            return self.restore(b.get("id", ""))
        if what == "empty_trash":
            return self.empty_trash()
        if what == "reset_lessons":
            return self.reset_lessons(n)
        if what == "set_goal":
            return self.set_goal(n, b.get("goal", ""))
        if what == "delete_block":
            return self.delete_block(b.get("id", ""))
        if what == "unlink":
            self.links.pop(n, None)
            self._jsave(os.path.join(self.dir, "linked.json"), self.links)
            return {"ok": True}
        return None
