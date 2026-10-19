"""Courses in the Workshop, built the way CS50 and MIT's open courses are: lessons, worked examples,
problem sets graded by real tests, quizzes, and a final project you defend.

What makes it different from asking a chatbot:
  * The course is written and checked ahead of time (World/workshop/courses/<course>/). The local model
    tutors (hints, explaining a failed test, grading your explanations) but never invents the curriculum.
  * Exercises are graded by running your code against tests, some hidden, like a real problem set.
  * Mastery gates: a unit counts as mastered at 85% (exercises passed on your own, plus the quiz).
    The next unit opens when this one is mastered.
  * Spaced review: what you master becomes flashcards in Study, and each new unit starts with a
    warm-up from an older one (retrieval practice).
  * A skills map shows how strong you are in each skill across the whole course.

Your work lives in an ordinary Workshop project (Course-Python), one folder per unit, so you write it in
VSCodium and press Ctrl+Alt+K to check.
"""
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time

MASTERY = 0.85


def _now():
    return int(time.time())


def _norm(s, case=False):
    s = re.sub(r"[ \t]+", " ", str(s)).strip()
    s = "\n".join(l.strip() for l in s.splitlines())
    return s if case else s.lower()


HARNESS = r'''
import builtins, io, json, math, sys, contextlib
path, tests = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
feed = []
def fake_input(prompt=""):
    if not feed:
        raise EOFError("the test gave no more input")
    return feed.pop(0)
builtins.input = fake_input
sys.dont_write_bytecode = True
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.abspath(path)))   # so the learner's file can import modules sitting next to it
import types
m = types.ModuleType("learner")      # compiled fresh from the file every time: never a stale cached copy
m.__file__ = path
out = io.StringIO()
try:
    with contextlib.redirect_stdout(out):
        exec(compile(open(path, encoding="utf-8").read(), path, "exec"), m.__dict__)
    load_err = None
except BaseException as e:
    load_err = "%s: %s" % (type(e).__name__, e)
CODE = "\n".join(l for l in open(path, encoding="utf-8").read().splitlines() if not l.strip().startswith("#"))   # the code without comment lines
res = []
def same(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-9)
        except (TypeError, ValueError):
            return False
    return a == b
for t in tests:
    if load_err and not t.get("allow_load_error"):
        res.append({"ok": False, "got": "Your file stopped with an error before any test ran: " + load_err}); continue
    feed[:] = list(t.get("inputs") or [])
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            if "call" in t:
                got = eval(t["call"], {"m": m, "CODE": CODE, **vars(m)})
            else:
                env = {"m": m, "CODE": CODE, **vars(m)}
                exec(t["check"], env)
                got = None
        if "expect" in t and not same(got, t["expect"]):
            res.append({"ok": False, "got": repr(got), "want": repr(t["expect"])})
        elif "expect_print" in t and t["expect_print"].strip().lower() not in buf.getvalue().strip().lower():
            res.append({"ok": False, "got": buf.getvalue()[-300:], "want": t["expect_print"]})
        else:
            res.append({"ok": True})
    except AssertionError as e:
        res.append({"ok": False, "got": str(e) or "a check failed"})
    except BaseException as e:
        res.append({"ok": False, "got": "%s: %s" % (type(e).__name__, e)})
print("@@ARCHIE@@" + json.dumps(res))
'''


class Courses:
    def __init__(self, lib_dir):
        self.dir = lib_dir

    # ------------------------------------------------------------ the course content
    def list(self):
        out = []
        if not os.path.isdir(self.dir):
            return out
        for d in sorted(os.listdir(self.dir)):
            p = os.path.join(self.dir, d, "course.json")
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    c = json.load(f)
                c["id"] = d
                out.append(c)
        return out

    def course(self, cid):
        p = os.path.join(self.dir, cid, "course.json")
        with open(p, encoding="utf-8") as f:
            c = json.load(f)
        c["id"] = cid
        return c

    def unit(self, cid, uid):
        with open(os.path.join(self.dir, cid, "units", uid + ".json"), encoding="utf-8") as f:
            u = json.load(f)
        u["id"] = uid
        return u

    def units(self, cid):
        c = self.course(cid)
        return [self.unit(cid, u) for u in c.get("units", [])]

    # ------------------------------------------------------------ grading
    def grade(self, ex, path, rt, lang="Python"):
        """Run the learner's file against the exercise's tests. Returns {"ok", "passed", "total", "results": [...]}"""
        tests = ex.get("tests") or []
        if lang != "Python":
            return self._grade_other(ex, path, rt, lang)
        python = python_for(rt) if isinstance(rt, dict) else rt
        prog = [t for t in tests if "stdin" in t or "out" in t]
        func = [t for t in tests if t not in prog]
        results = []
        if not os.path.isfile(path):
            return {"ok": False, "passed": 0, "total": len(tests), "results": [{"ok": False, "why": "There's no %s yet." % os.path.basename(path)}]}
        for t in prog:
            try:
                c = subprocess.run([python, "-u", path], input=t.get("stdin", ""), capture_output=True, text=True, timeout=t.get("timeout", 6),
                                   cwd=os.path.dirname(path), env=dict(os.environ, PYTHONIOENCODING="utf-8"), encoding="utf-8", errors="replace",
                                   creationflags=0x08000000 if os.name == "nt" else 0)
                got = c.stdout
                if c.returncode:
                    results.append(self._res(t, False, "It stopped with an error:\n" + (c.stderr.strip().splitlines() or ["?"])[-1]))
                    continue
            except subprocess.TimeoutExpired:
                results.append(self._res(t, False, "It didn't finish in %d seconds. Is there a loop that never ends, or an input() the test didn't expect?" % t.get("timeout", 6)))
                continue
            want = t.get("out") or []
            want = [want] if isinstance(want, str) else want
            hay = _norm(got, t.get("case", False))
            miss = [w for w in want if _norm(w, t.get("case", False)) not in hay]
            if "exact" in t and _norm(got, True) != _norm(t["exact"], True):
                miss.append(t["exact"])
            if "not" in t and any(_norm(x) in hay for x in t["not"]):
                miss.append("(it printed something it shouldn't: %s)" % ", ".join(t["not"]))
            results.append(self._res(t, not miss, "" if not miss else "Expected to see: %s\nIt printed: %s" % (" / ".join(repr(m) for m in miss), (got.strip()[-300:] or "(nothing)"))))
        if func:
            fd, tp = tempfile.mkstemp(suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(func, f)
            hd, hp = tempfile.mkstemp(suffix=".py")
            with os.fdopen(hd, "w", encoding="utf-8") as f:
                f.write(HARNESS)
            try:
                c = subprocess.run([python, hp, path, tp], capture_output=True, text=True, timeout=20, cwd=os.path.dirname(path),
                                   env=dict(os.environ, PYTHONIOENCODING="utf-8"), encoding="utf-8", errors="replace",
                                   creationflags=0x08000000 if os.name == "nt" else 0)
                raw = c.stdout.split("@@ARCHIE@@")[-1] if "@@ARCHIE@@" in c.stdout else None
                got = json.loads(raw) if raw else [{"ok": False, "got": (c.stderr.strip().splitlines() or ["the tests couldn't run"])[-1]}] * len(func)
            except subprocess.TimeoutExpired:
                got = [{"ok": False, "got": "It didn't finish in time (a loop that never ends?)."}] * len(func)
            finally:
                os.remove(tp)
                os.remove(hp)
            for t, g in zip(func, got):
                why = "" if g["ok"] else ("%s gave %s, expected %s" % (t.get("call"), g.get("got"), g.get("want")) if "want" in g and t.get("call") else g.get("got", ""))
                results.append(self._res(t, g["ok"], why))
        passed = sum(1 for r in results if r["ok"])
        return {"ok": passed == len(results) and bool(results), "passed": passed, "total": len(results), "results": results}

    def _grade_other(self, ex, path, rt, lang):
        import archie_graders as G
        tests = ex.get("tests") or []
        if not os.path.isfile(path):
            return {"ok": False, "passed": 0, "total": len(tests), "results": [{"ok": False, "why": "There's no %s yet." % os.path.basename(path)}]}
        fn = {"Java": G.grade_java, "C": G.grade_c, "C++": G.grade_c, "C#": G.grade_cs, "JavaScript": G.grade_js}.get(lang)
        if lang.startswith("Web"):
            try:
                import archie_checkers
            except ImportError:
                archie_checkers = None
            out, err = G.grade_web(ex, path, rt, archie_checkers)
        elif fn:
            out, err = fn(ex, path, rt)
        else:
            out, err = None, "Archie can't grade %s yet." % lang
        if out is None:
            results = [self._res(t, False, err) for t in tests]
        else:
            results = [self._res(t, ok, why) for t, ok, why in out]
        passed = sum(1 for r in results if r["ok"])
        return {"ok": passed == len(results) and bool(results), "passed": passed, "total": len(results), "results": results}

    @staticmethod
    def _res(t, ok, why):
        r = {"ok": ok, "name": t.get("name", ""), "hidden": bool(t.get("hidden"))}
        if not ok:
            r["why"] = (t.get("hint_if_fail") or "One of the hidden tests failed. Think about unusual cases (empty input, zero, negative numbers, capitals).") if t.get("hidden") else (why + (("\n" + t["hint_if_fail"]) if t.get("hint_if_fail") else ""))
        return r


# ------------------------------------------------------------ progress (kept in the course project's meta)
def unit_score(u, prog):
    """0..1: exercises passed on your own count fully, ones you looked up count half; the quiz counts as one more exercise."""
    exs = u.get("exercises") or []
    p = prog.get(u["id"]) or {}
    if p.get("testout") and exs and (p.get("quiz") or 0) >= MASTERY and exs[-1]["id"] in (p.get("passed") or []) \
            and exs[-1]["id"] not in (p.get("shown") or []):
        return 1.0                      # tested out: passed the quiz and the hardest exercise on their own
    own = sum(1 for e in exs if e["id"] in (p.get("passed") or []) and e["id"] not in (p.get("shown") or []))
    looked = sum(1 for e in exs if e["id"] in (p.get("passed") or []) and e["id"] in (p.get("shown") or []))
    total = len(exs) + (1 if u.get("quiz") else 0)
    pts = own + 0.5 * looked + ((p.get("quiz") or 0) if u.get("quiz") else 0)
    return pts / total if total else 1.0


def skills_map(units, prog):
    acc = {}
    for u in units:
        s = unit_score(u, prog)
        for k in u.get("skills") or []:
            acc.setdefault(k, []).append(s)
    return {k: round(sum(v) / len(v), 2) for k, v in acc.items()}


def unlocked(units, prog):
    """Units you can open: every unit up to and including the first one not yet mastered."""
    out = []
    for u in units:
        out.append(u["id"])
        if unit_score(u, prog) < MASTERY:
            break
    return out


def warmup(units, prog, current_uid, rng=random):
    """One exercise you passed at least two units ago, to keep it fresh."""
    ids = [u["id"] for u in units]
    if current_uid not in ids:
        return None
    i = ids.index(current_uid)
    pool = [(u["id"], e) for u in units[:max(0, i - 1)] for e in u.get("exercises") or [] if e["id"] in ((prog.get(u["id"]) or {}).get("passed") or [])]
    return rng.choice(pool) if pool else None


def python_for(rt):
    return rt.get("python") or sys.executable


# ------------------------------------------------------------ the Workshop side (mixed into Workshop)
def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def _comment(fname, text):
    ext = os.path.splitext(fname)[1].lower()
    lines = text.splitlines() or [""]
    if ext == ".py":
        return "".join("# %s\n" % l for l in lines)
    if ext in (".html", ".htm"):
        return "<!--\n%s\n-->\n" % "\n".join("  " + l.replace("--", "-") for l in lines)
    if ext == ".css":
        return "/*\n%s\n*/\n" % "\n".join("  " + l.replace("*/", "* /") for l in lines)
    return "".join("// %s\n" % l for l in lines)


def _header(e):
    """The exercise's title and task at the top of its file, as comments in that language. HTML keeps its doctype first."""
    h = _comment(e["file"], "%s\n%s" % (e["title"], e["prompt"])) + "\n"
    return h


def with_header(e, body):
    """The file as written for the learner: the task as a comment at the top (after <!DOCTYPE> in a web page)."""
    if e["file"].lower().endswith((".html", ".htm")) and body.lstrip().lower().startswith("<!doctype"):
        first, _, rest = body.lstrip().partition("\n")
        return first + "\n" + _comment(e["file"], "%s\n%s" % (e["title"], e["prompt"])) + rest
    return _header(e) + body


class CourseMixin:
    """Course projects: a Workshop project in mode "course" with meta {"course", "progress", "unit"}."""

    def course_list(self):
        out = []
        for c in self.courses.list():
            proj = next((n for n in self._project_names() if self.meta(n).get("course") == c["id"]), None)
            out.append({"id": c["id"], "name": c["name"], "summary": c.get("summary", ""), "levels": c.get("levels", []),
                        "units": len(c.get("units", [])), "project": proj})
        return {"courses": out}

    def _project_names(self):
        names = set(self.links)
        for d in os.listdir(self.dir):
            if os.path.isdir(os.path.join(self.dir, d)) and not d.startswith("."):
                names.add(d)
        return sorted(names)

    def start_course(self, cid):
        c = self.courses.course(cid)
        name = "Course-" + re.sub(r"[^A-Za-z0-9#+]+", "-", c["name"].split(" (")[0]).strip("-").replace("#", "Sharp").replace("+", "p")
        root = self.folder(name)
        if not os.path.isdir(os.path.join(root, ".archie")):
            os.makedirs(os.path.join(root, ".archie"), exist_ok=True)
            self.save_meta(name, {"name": name, "mode": "course", "course": cid, "lang": c.get("lang", "Python"), "goal": c.get("summary", ""),
                                  "entry": "", "watch": True, "created": _now(), "updated": _now(), "history": [], "progress": {}, "unit": c["units"][0]})
            with open(os.path.join(root, "README.txt"), "w", encoding="utf-8") as f:
                f.write("Your %s course. Each unit has its own folder; open the exercise files in VSCodium, save, and press Ctrl+Alt+K to check.\n" % c["name"])
            self.event(name, "info", "Course started: " + c["name"], c.get("summary", ""))
        return {"ok": True, "name": name}

    def _clang(self, name):
        c = self.courses.course(self.meta(name).get("course"))
        return c.get("grader") or c.get("lang", "Python")

    def _course_projects(self):
        out = []
        for n in self._project_names():
            m = self.meta(n)
            if m.get("mode") == "course" and m.get("course"):
                out.append((n, m))
        return out

    def known_concepts(self, skip_course=None):
        """Ideas you've mastered in any course: {concept: [course names]}."""
        known = {}
        for n, m in self._course_projects():
            if m["course"] == skip_course:
                continue
            try:
                c = self.courses.course(m["course"])
                units = self.courses.units(m["course"])
            except (OSError, ValueError):
                continue
            prog = m.get("progress") or {}
            for u in units:
                if unit_score(u, prog) >= MASTERY:
                    for k in u.get("concepts") or []:
                        known.setdefault(k, [])
                        if c["name"] not in known[k]:
                            known[k].append(c["name"])
        return known

    def _known_from(self, u, known):
        cs = u.get("concepts") or []
        if not cs or not all(k in known for k in cs):
            return []
        names = set(known[cs[0]])
        for k in cs[1:]:
            names &= set(known[k])
        return sorted(names) or sorted(known[cs[0]])

    def _compare(self, cid, u, limit=2):
        """The same idea in other languages: the closest unit in each other course, with its worked example."""
        cs = set(u.get("concepts") or [])
        if not cs:
            return []
        started = {m["course"] for _, m in self._course_projects()}
        out = []
        for c in self.courses.list():
            if c["id"] == cid:
                continue
            best, score = None, 0
            for oid in c.get("units", []):
                try:
                    ou = self.courses.unit(c["id"], oid)
                except (OSError, ValueError):
                    continue
                sc = len(cs & set(ou.get("concepts") or []))
                if sc > score and (ou.get("example") or {}).get("code"):
                    best, score = ou, sc
            if best:
                out.append({"course": c["name"], "started": c["id"] in started, "unit": best["title"], "code": best["example"]["code"], "score": score})
        out.sort(key=lambda x: (not x["started"], -x["score"]))
        return out[:limit]

    def course_testout(self, name, uid):
        m, prog = self._cprog(name)
        prog.setdefault(uid, {})["testout"] = True
        m["progress"] = prog
        self.save_meta(name, m)
        self.event(name, "info", "Testing out", "Pass the quiz (85%) and the last exercise on your own, and this unit counts as mastered.")
        return {"ok": True}

    def _cprog(self, name):
        m = self.meta(name)
        return m, m.get("progress") or {}

    def course_state(self, name):
        m, prog = self._cprog(name)
        cid = m.get("course")
        c = self.courses.course(cid)
        units = self.courses.units(cid)
        open_ids = unlocked(units, prog)
        known = self.known_concepts(skip_course=cid)
        U = []
        for u in units:
            p = prog.get(u["id"]) or {}
            U.append({"id": u["id"], "level": u["level"], "title": u["title"], "skills": u.get("skills", []), "project": bool(u.get("project")),
                      "score": round(unit_score(u, prog), 2), "open": u["id"] in open_ids, "mastered": unit_score(u, prog) >= MASTERY,
                      "exercises": len(u.get("exercises") or []), "passed": len(p.get("passed") or []), "known_from": self._known_from(u, known)})
        done = sum(1 for u in U if u["mastered"])
        return {"name": name, "course": {k: c.get(k) for k in ("id", "name", "summary", "levels", "certs")}, "units": U, "unit": m.get("unit"),
                "skills": skills_map(units, prog), "mastered": done, "total": len(U), "mastery": MASTERY}

    def _unit_dir(self, name, u):
        return os.path.join(self.folder(name), "%s-%s" % (u["id"], _slug(u["title"])))

    def open_unit(self, name, uid):
        m, prog = self._cprog(name)
        cid = m.get("course")
        units = self.courses.units(cid)
        if uid not in unlocked(units, prog):
            return {"error": "Master the unit before this one first (85%)."}
        u = next(x for x in units if x["id"] == uid)
        d = self._unit_dir(name, u)
        os.makedirs(d, exist_ok=True)
        made = False
        for e in u.get("exercises") or []:
            for fname, body in (e.get("extra_files") or {}).items():      # images or data an exercise needs
                fp = os.path.join(d, fname)
                if not os.path.exists(fp):
                    os.makedirs(os.path.dirname(fp), exist_ok=True)
                    with open(fp, "w", encoding="utf-8", newline="\n") as f:
                        f.write(body)
            p = os.path.join(d, e["file"])
            if not os.path.exists(p):
                made = True
                with open(p, "w", encoding="utf-8", newline="\n") as f:
                    f.write(with_header(e, e.get("starter", "")))
        ex = u.get("example") or {}
        exfile = ex.get("file") or "example.py"
        if ex.get("code") and not os.path.exists(os.path.join(d, exfile)):
            made = True
            with open(os.path.join(d, exfile), "w", encoding="utf-8", newline="\n") as f:
                f.write(_comment(exfile, "Worked example: run it, change it, break it on purpose and read the error.") + ex["code"])
        if made:      # Archie made these files: the watcher shouldn't treat them as your saves
            self.snap[name] = self._scan(name, self.snap.get(name))
        if m.get("unit") != uid:
            m["unit"] = uid
            m["updated"] = _now()
            self.save_meta(name, m)
        p = prog.get(uid) or {}
        wu = warmup(units, prog, uid)
        rel = os.path.relpath(d, self.folder(name)).replace("\\", "/")
        safe_ex = [{"id": e["id"], "title": e["title"], "prompt": e["prompt"], "file": rel + "/" + e["file"], "hints": len(e.get("hints") or []),
                    "tests": [{"name": t.get("name", ""), "hidden": bool(t.get("hidden"))} for t in e.get("tests") or []],
                    "passed": e["id"] in (p.get("passed") or []), "shown": e["id"] in (p.get("shown") or []), "attempts": (p.get("attempts") or {}).get(e["id"], 0),
                    "hints_used": (p.get("hints") or {}).get(e["id"], 0)} for e in u.get("exercises") or []]
        quiz = [{"q": q["q"], "choices": q["choices"]} for q in u.get("quiz") or []]
        known = self.known_concepts(skip_course=cid)
        return {"unit": {k: u.get(k) for k in ("id", "level", "title", "skills", "concepts", "lesson", "example", "explain", "project", "bridge")}, "folder": rel,
                "example_file": rel + "/" + exfile, "known_from": self._known_from(u, known), "compare": self._compare(cid, u),
                "testout": bool(p.get("testout")), "lang": self._clang(name),
                "exercises": safe_ex, "quiz": quiz, "quiz_score": p.get("quiz"), "explained": p.get("explained"),
                "score": round(unit_score(u, prog), 2), "mastered": unit_score(u, prog) >= MASTERY,
                "warmup": {"unit": wu[0], "id": wu[1]["id"], "title": wu[1]["title"], "prompt": wu[1]["prompt"]} if wu else None}

    def _find_ex(self, name, file=None, uid=None, eid=None):
        m, prog = self._cprog(name)
        units = self.courses.units(m.get("course"))
        if file:
            rp = os.path.realpath(file)
            for u in units:
                for e in u.get("exercises") or []:
                    if os.path.realpath(os.path.join(self._unit_dir(name, u), e["file"])) == rp:
                        return u, e
            return None, None
        u = next((x for x in units if x["id"] == (uid or m.get("unit"))), None)
        e = next((x for x in (u or {}).get("exercises") or [] if x["id"] == eid), None) if u else None
        return u, e

    def course_check(self, name, file=None, uid=None, eid=None):
        u, e = self._find_ex(name, file, uid, eid)
        if not e:
            return {"error": "That file isn't one of the course exercises. Open the unit in the Workshop and use its exercise files."}
        path = os.path.join(self._unit_dir(name, u), e["file"])
        rel = os.path.relpath(path, self.folder(name)).replace("\\", "/")
        lint = self.lint(name, rel, deep=True) if os.path.exists(path) else {"ok": True, "problems": []}
        g = self.courses.grade(e, path, self.runtimes(), self._clang(name))
        m, prog = self._cprog(name)
        p = prog.setdefault(u["id"], {})
        p.setdefault("attempts", {})[e["id"]] = p.get("attempts", {}).get(e["id"], 0) + 1
        before = unit_score(u, prog) >= MASTERY
        if g["ok"] and e["id"] not in p.setdefault("passed", []):
            p["passed"].append(e["id"])
        m["progress"] = prog
        m["updated"] = _now()
        self.save_meta(name, m)
        lines = []
        for r in g["results"]:
            label = r.get("name") or ("hidden test" if r.get("hidden") else "test")
            lines.append(("PASS  " if r["ok"] else "FAIL  ") + label + ("" if r["ok"] else "\n      " + r.get("why", "").replace("\n", "\n      ")))
        text = "%d of %d tests passed.\n%s" % (g["passed"], g["total"], "\n".join(lines))
        if not lint["ok"]:
            text += "\n\nThe checker also found: " + "; ".join("line %s: %s" % (x["line"], x["msg"]) for x in lint["problems"] if x["sev"] == "error")
        if g["ok"]:
            self.event(name, "pass", "%s: passed" % e["title"], text, rel)
        else:
            first_line = next((x["line"] for x in lint["problems"] if x["sev"] == "error"), None)
            self.event(name, "tryagain", "%s: not yet" % e["title"], text + "\n\nPress hint for a nudge, or 'why did it fail?' for an explanation.", rel, first_line)
        after = unit_score(u, prog) >= MASTERY
        if after and not before:
            self._mastered(name, u)
        return {"pass": g["ok"], "passed": g["passed"], "total": g["total"], "results": g["results"], "feedback": text, "unit_score": round(unit_score(u, prog), 2)}

    def _mastered(self, name, u):
        self.event(name, "done", "Unit mastered: %s" % u["title"], "The next unit is open. What you learned is now in your flashcards (Study), and it'll come back as a warm-up later.")
        self.alert("Workshop · course", "Unit mastered: " + u["title"])
        cards = u.get("cards") or []
        if cards and self.study_dir:
            try:
                import archie_study
                c = self.courses.course(self.meta(name).get("course"))
                archie_study.Study(self.study_dir).add_cards("Course - " + c["name"], cards, source="Course: " + u["title"])
            except Exception:      # noqa: BLE001 - flashcards are a bonus
                pass

    def course_hint(self, name, uid, eid):
        u, e = self._find_ex(name, uid=uid, eid=eid)
        if not e:
            return {"error": "no such exercise"}
        m, prog = self._cprog(name)
        p = prog.setdefault(u["id"], {})
        n = p.setdefault("hints", {}).get(e["id"], 0)
        H = e.get("hints") or []
        refs = None
        if n < len(H):
            text = H[n]
        else:
            path = os.path.join(self._unit_dir(name, u), e["file"])
            code = open(path, encoding="utf-8", errors="replace").read()[:6000] if os.path.exists(path) else ""
            lib, refs = self._lookup(self._clang(name), "%s %s" % (e["title"], e["prompt"][:400]), k=2, kinds=("docs",))
            text = self._chat(self.TEACH, "Exercise: %s\n%s\n\nTheir code:\n%s\n\nThey've used all the written hints. Give ONE more nudge (2-3 sentences) toward the idea, without writing the code. "
                              "If a reference page below explains the idea, point them to it by name.%s"
                              % (e["title"], e["prompt"], code, lib), tokens=260, temp=0.4)
        p["hints"][e["id"]] = n + 1
        m["progress"] = prog
        self.save_meta(name, m)
        self.event(name, "hint", "Hint %d for %s" % (n + 1, e["title"]), text, refs=refs)
        return {"text": text, "n": n + 1}

    def course_solution(self, name, uid, eid):
        u, e = self._find_ex(name, uid=uid, eid=eid)
        if not e:
            return {"error": "no such exercise"}
        m, prog = self._cprog(name)
        p = prog.setdefault(u["id"], {})
        tries = (p.get("attempts") or {}).get(e["id"], 0)
        if tries < 3 and e["id"] not in (p.get("passed") or []):
            return {"error": "Have at least 3 tries first (you've had %d). Struggling a bit is where the learning happens; use the hints." % tries}
        if e["id"] not in (p.get("passed") or []) and e["id"] not in p.setdefault("shown", []):
            p["shown"].append(e["id"])        # looked-up exercises count half towards mastery
        m["progress"] = prog
        self.save_meta(name, m)
        self.event(name, "show", "A solution for %s" % e["title"], "```\n%s```\nType it in yourself rather than copying: your fingers learn too. Then change something and check it still works." % e["solution"])
        return {"solution": e["solution"]}

    def course_why(self, name, uid, eid):
        """Like a teaching assistant: look at the failed tests and the code and explain what's going on."""
        u, e = self._find_ex(name, uid=uid, eid=eid)
        if not e:
            return {"error": "no such exercise"}
        path = os.path.join(self._unit_dir(name, u), e["file"])
        g = self.courses.grade(e, path, self.runtimes(), self._clang(name))
        code = open(path, encoding="utf-8", errors="replace").read()[:6000] if os.path.exists(path) else ""
        fails = "\n".join(r.get("why", "") for r in g["results"] if not r["ok"]) or "everything passed"
        lib, refs = self._lookup(self._clang(name), "%s %s" % (fails[:500], e["title"]), k=2, extra=code[:2000])
        text = self._chat(self.TEACH, "Exercise: %s\n%s\n\nThe learner's code:\n%s\n\nWhat the tests found:\n%s\n\nExplain in 3-5 plain sentences why it fails and what to look at. "
                          "Don't write the fixed code.%s" % (e["title"], e["prompt"], code, fails, lib), tokens=420, temp=0.3)
        self.event(name, "explain", "Why %s fails" % e["title"], text, os.path.relpath(path, self.folder(name)).replace("\\", "/"), refs=refs)
        return {"text": text}

    def course_quiz(self, name, uid, answers):
        m, prog = self._cprog(name)
        units = self.courses.units(m.get("course"))
        u = next((x for x in units if x["id"] == uid), None)
        if not u or not u.get("quiz"):
            return {"error": "no quiz"}
        before = unit_score(u, prog) >= MASTERY
        res = []
        for i, q in enumerate(u["quiz"]):
            a = answers[i] if i < len(answers) else None
            res.append({"ok": a == q["answer"], "answer": q["answer"], "why": q.get("why", "")})
        score = sum(r["ok"] for r in res) / len(res)
        p = prog.setdefault(uid, {})
        p["quiz"] = max(p.get("quiz") or 0, score)
        m["progress"] = prog
        self.save_meta(name, m)
        self.event(name, "pass" if score >= MASTERY else "tryagain", "Quiz: %d of %d" % (sum(r["ok"] for r in res), len(res)),
                   "\n".join("%s %d. %s" % ("✓" if r["ok"] else "✗", i + 1, r["why"]) for i, r in enumerate(res)))
        if unit_score(u, prog) >= MASTERY and not before:
            self._mastered(name, u)
        return {"score": score, "results": res}

    def course_explain(self, name, uid, text):
        """Explain-it-back: you teach the idea; Archie grades your explanation against the lesson."""
        m, prog = self._cprog(name)
        u = next((x for x in self.courses.units(m.get("course")) if x["id"] == uid), None)
        if not u or not (text or "").strip():
            return {"error": "Write your explanation first."}
        raw = self._chat(self.TEACH, "Lesson the learner studied:\n%s\n\nTask: %s\n\nTheir explanation:\n%s\n\nGrade it like a kind but honest teacher. Return JSON: "
                         "{\"score\": 0 to 10, \"right\": what they got right (1-2 sentences), \"missing\": what's missing or wrong (1-2 sentences), "
                         "\"tip\": one way to make it clearer}" % (u.get("lesson", "")[:5000], u.get("explain", ""), text[:3000]), tokens=400, json_mode=True)
        try:
            v = json.loads(raw)
        except ValueError:
            v = {"score": None, "right": "", "missing": "Archie couldn't grade that one. Try again.", "tip": ""}
        p = prog.setdefault(uid, {})
        p["explained"] = {"text": text[:3000], "score": v.get("score"), "at": _now()}
        m["progress"] = prog
        self.save_meta(name, m)
        self.event(name, "explain", "Your explanation: %s/10" % v.get("score", "?"), "Right: %s\nMissing: %s\nTip: %s" % (v.get("right", ""), v.get("missing", ""), v.get("tip", "")))
        return v
