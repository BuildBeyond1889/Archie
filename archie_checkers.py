"""Real error checkers for the Workshop.

The coding model guesses; these tools know. Each one reports exact problems with a line number:
  Python      the parser, then ruff (a fast checker: undefined names, unused imports, likely bugs)
  JavaScript  node --check
  HTML        a built-in checker: tags left open or closed in the wrong order, duplicate ids,
              links to files that aren't there, and the JavaScript inside <script> tags
  CSS, JSON   built-in checks
  C, C++      gcc / g++ with warnings on, without building anything
  Java        javac with warnings on (output goes to a scratch folder)
  C#          dotnet build (slow, so only when you ask or when Archie builds)
  Arduino     arduino-cli compile (slow, same)
  GDScript    Godot's own --check-only (same)

check(path, runtimes, root, deep) -> {"ok", "tool", "problems": [{"line", "col", "sev", "code", "msg"}], "summary"}
"ok" is False only for errors; warnings are things worth a look that won't stop the program.
"""
import html.parser
import json
import os
import re
import shutil
import subprocess
import tempfile

NOWIN = 0x08000000 if os.name == "nt" else 0
FAST = {".py", ".js", ".mjs", ".html", ".htm", ".css", ".json", ".c", ".h", ".cpp", ".hpp", ".cc", ".java"}
SLOW = {".cs", ".ino", ".gd"}
_ruff = {}

# ruff rules that mean "this will break" rather than "this could be tidier"
RUFF_ERRORS = re.compile(r"^(E9\d\d|F821|F822|F823|F63\d|F7\d\d|F5\d\d|PLE)")
RUFF_SELECT = "E9,F,B,PLE"


def _run(cmd, cwd=None, timeout=60):
    try:
        c = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, creationflags=NOWIN, encoding="utf-8", errors="replace")
        return c.returncode, (c.stdout or "") + (c.stderr or "")
    except subprocess.TimeoutExpired:
        return None, "The checker took too long."
    except OSError as e:
        return None, str(e)


def _p(line, col, sev, msg, code=""):
    return {"line": int(line) if line else None, "col": int(col) if col else None, "sev": sev, "code": code, "msg": msg.strip()[:400]}


def ruff_cmd(rt):
    """How to start ruff here, or None if it isn't installed."""
    py = rt.get("python")
    if py in _ruff:
        return _ruff[py]
    cmd = None
    exe = shutil.which("ruff")
    if exe:
        cmd = [exe]
    elif py:
        code, out = _run([py, "-m", "ruff", "--version"], timeout=20)
        if code == 0 and "ruff" in out.lower():
            cmd = [py, "-m", "ruff"]
    _ruff[py] = cmd
    return cmd


def forget_ruff():
    _ruff.clear()


# ---------------------------------------------------------------- Python
def check_python(path, rt):
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    try:
        compile(src, path, "exec")
    except SyntaxError as e:
        return "python", [_p(e.lineno, e.offset, "error", "%s: %s" % (type(e).__name__, e.msg), "syntax")]
    rc = ruff_cmd(rt)
    if not rc:
        return "python (install ruff for deeper checks)", []
    code, out = _run(rc + ["check", "--output-format=json", "--no-cache", "--isolated", "--select", RUFF_SELECT, "--target-version", "py38", path],
                     cwd=os.path.dirname(path), timeout=40)
    probs = []
    try:
        items = json.loads(out[out.find("["):]) if "[" in out else []
    except ValueError:
        items = []
    for it in items:
        c = it.get("code") or ""
        loc = it.get("location") or {}
        probs.append(_p(loc.get("row"), loc.get("column"), "error" if RUFF_ERRORS.match(c) else "warning", it.get("message", ""), c))
    return "python + ruff", probs


# ---------------------------------------------------------------- JavaScript
def _node_check(rt, path):
    if "node" not in rt:
        return None
    code, out = _run([rt["node"], "--check", path], timeout=20)
    if code in (0, None):
        return []
    m = re.search(r":(\d+)\s*\n", out)
    msg = next((l for l in out.splitlines() if re.match(r"\s*(SyntaxError|ReferenceError|TypeError)", l)), out.strip().splitlines()[-1] if out.strip() else "error")
    return [_p(m.group(1) if m else None, None, "error", msg.strip(), "syntax")]


def check_js(path, rt):
    r = _node_check(rt, path)
    if r is None:
        return "javascript (install Node.js to check it)", []
    return "node --check", r


# ---------------------------------------------------------------- HTML
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr", "!doctype"}
OPTIONAL_CLOSE = {"p", "li", "td", "th", "tr", "thead", "tbody", "tfoot", "option", "dt", "dd", "colgroup", "caption", "optgroup", "rt", "rp", "html", "head", "body"}


class _HTMLCheck(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.probs, self.ids, self.scripts, self.refs = [], [], {}, [], []
        self.doctype = False
        self._in_script = None

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype"):
            self.doctype = True

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        line = self.getpos()[0]
        if a.get("id"):
            if a["id"] in self.ids:
                self.probs.append(_p(line, None, "warning", 'The id "%s" is used twice (first on line %d). Ids should be unique.' % (a["id"], self.ids[a["id"]]), "dup-id"))
            else:
                self.ids[a["id"]] = line
        if tag == "img" and "alt" not in a:
            self.probs.append(_p(line, None, "warning", "This image has no alt text. Screen readers need it.", "img-alt"))
        for k in ("src", "href"):
            v = a.get(k)
            if v and tag in ("script", "link", "img", "source", "audio", "video") and not re.match(r"^([a-z]+:|//|#|data:)", v, re.I):
                self.refs.append((line, v.split("?")[0].split("#")[0], tag))
        if tag == "script" and not a.get("src") and (a.get("type") or "text/javascript").lower() in ("text/javascript", "module", "application/javascript"):
            self._in_script = [line, []]
        if tag not in VOID:
            self.stack.append((tag, line))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_data(self, data):
        if self._in_script is not None:
            self._in_script[1].append(data)

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        if tag == "script" and self._in_script is not None:
            self.scripts.append((self._in_script[0], "".join(self._in_script[1])))
            self._in_script = None
        if tag in VOID:
            return
        if not any(t == tag for t, _ in self.stack):
            self.probs.append(_p(line, None, "error", "</%s> closes a tag that was never opened." % tag, "stray-close"))
            return
        while self.stack:
            t, l = self.stack.pop()
            if t == tag:
                break
            if t not in OPTIONAL_CLOSE:
                self.probs.append(_p(l, None, "error", "<%s> (line %d) is never closed before </%s> on line %d." % (t, l, tag, line), "unclosed"))


def check_html(path, rt, root=None):
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    h = _HTMLCheck()
    try:
        h.feed(src)
        h.close()
    except Exception as e:      # noqa: BLE001 - the parser gave up; report where
        return "html", [_p(None, None, "error", "The page couldn't be read: %s" % e, "parse")]
    probs = list(h.probs)
    for t, l in h.stack:
        if t not in OPTIONAL_CLOSE:
            probs.append(_p(l, None, "error", "<%s> is opened on line %d and never closed." % (t, l), "unclosed"))
    if not h.doctype and re.search(r"<html", src, re.I):
        probs.append(_p(1, None, "warning", "No <!DOCTYPE html> at the top, so browsers use their old 'quirks' mode.", "doctype"))
    base = os.path.dirname(path)
    for line, ref, tag in h.refs:
        if ref and not os.path.exists(os.path.normpath(os.path.join(base, ref))):
            probs.append(_p(line, None, "error", 'The %s points to "%s", but there is no file there.' % (tag, ref), "missing-file"))
    if "node" in rt:
        for start, code in h.scripts:
            if not code.strip():
                continue
            fd, tmp = tempfile.mkstemp(suffix=".js")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(code)
            try:
                for p in _node_check(rt, tmp) or []:
                    if p["line"]:
                        p["line"] = start + p["line"] - 1
                    p["msg"] = "In the <script>: " + p["msg"]
                    probs.append(p)
            finally:
                os.remove(tmp)
    return "html", probs


# ---------------------------------------------------------------- CSS / JSON
def check_css(path, rt):
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    probs, depth, line, i = [], [], 1, 0
    while i < len(src):
        c = src[i]
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            if j < 0:
                probs.append(_p(line, None, "error", "A /* comment is never closed with */.", "comment"))
                break
            line += src.count("\n", i, j)
            i = j + 2
            continue
        if c in "\"'":
            j = src.find(c, i + 1)
            if j < 0 or "\n" in src[i:j]:
                probs.append(_p(line, None, "error", "A quote is never closed.", "quote"))
                j = src.find("\n", i) if j < 0 or "\n" in src[i:j] else j
                if j < 0:
                    break
            i = j + 1
            continue
        if c == "\n":
            line += 1
        elif c == "{":
            depth.append(line)
        elif c == "}":
            if depth:
                depth.pop()
            else:
                probs.append(_p(line, None, "error", "This } has no { to match.", "brace"))
        i += 1
    for l in depth:
        probs.append(_p(l, None, "error", "The { on line %d is never closed with }." % l, "brace"))
    return "css", probs


def check_json(path, rt):
    with open(path, encoding="utf-8", errors="replace") as f:
        src = f.read()
    try:
        json.loads(src)
    except ValueError as e:
        return "json", [_p(getattr(e, "lineno", None), getattr(e, "colno", None), "error", getattr(e, "msg", str(e)), "json")]
    return "json", []


# ---------------------------------------------------------------- compilers
GCC_LINE = re.compile(r"^(.*?):(\d+):(\d+):\s*(fatal error|error|warning|note):\s*(.*)$")


def _gcc_parse(out, path):
    probs = []
    base = os.path.basename(path).lower()
    for l in out.splitlines():
        m = GCC_LINE.match(l.strip())
        if not m or m.group(4) == "note":
            continue
        if os.path.basename(m.group(1)).lower() != base and not m.group(4).endswith("error"):
            continue
        code = (re.search(r"\[(-W[\w=-]+)\]", m.group(5)) or [None, ""])[1]
        probs.append(_p(m.group(2), m.group(3), "error" if "error" in m.group(4) else "warning", re.sub(r"\s*\[-W[\w=-]+\]$", "", m.group(5)), code))
    return probs


def check_c(path, rt, root=None):
    cpp = os.path.splitext(path)[1].lower() in (".cpp", ".hpp", ".cc")
    exe = rt.get("g++" if cpp else "gcc")
    if not exe:
        return "%s (install the compiler to check it)" % ("c++" if cpp else "c"), []
    args = [exe, "-fsyntax-only", "-Wall", "-Wextra", "-fno-diagnostics-color", "-fmax-errors=20"]
    if path.lower().endswith((".h", ".hpp")):
        args += ["-x", "c++-header" if cpp or path.lower().endswith(".hpp") else "c-header"]
    if root:
        args += ["-I", root]
    code, out = _run(args + [path], cwd=os.path.dirname(path), timeout=60)
    return ("g++" if cpp else "gcc") + " -Wall", _gcc_parse(out, path)


def check_java(path, rt, root=None):
    javac = rt.get("javac")
    if not javac and rt.get("java"):
        cand = os.path.join(os.path.dirname(rt["java"]), "javac" + (".exe" if os.name == "nt" else ""))
        javac = cand if os.path.exists(cand) else None
    if not javac:
        return "java (install the JDK to check it)", []
    tmp = tempfile.mkdtemp(prefix="archie-javac-")
    try:
        args = [javac, "-Xlint:all", "-Xmaxerrs", "20", "-d", tmp, "-encoding", "UTF-8"]
        if root:
            args += ["-sourcepath", root]
        code, out = _run(args + [path], cwd=os.path.dirname(path), timeout=90)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    probs = []
    for m in re.finditer(r"^(.*?\.java):(\d+):\s*(error|warning):\s*(.*)$", out, re.M):
        if os.path.basename(m.group(1)).lower() == os.path.basename(path).lower() or m.group(3) == "error":
            probs.append(_p(m.group(2), None, m.group(3), m.group(4), "javac"))
    return "javac -Xlint", probs


def check_cs(path, rt, root=None):
    if "dotnet" not in rt:
        return "c# (install .NET to check it)", []
    proj = None
    for dp, dns, fns in os.walk(root or os.path.dirname(path)):
        dns[:] = [d for d in dns if d not in ("bin", "obj", ".archie", ".git")]
        proj = next((os.path.join(dp, f) for f in fns if f.endswith(".csproj")), None)
        if proj:
            break
    if not proj:
        return "c#", [_p(None, None, "warning", "No .csproj project file, so C# can't be checked or run. Ask Archie to set one up.", "csproj")]
    nc = os.path.join(os.path.dirname(proj), "nuget.config")
    if not os.path.exists(nc):
        try:
            with open(proj, encoding="utf-8", errors="replace") as f:
                if "PackageReference" not in f.read():
                    with open(nc, "w", encoding="utf-8") as g:
                        g.write('<?xml version="1.0" encoding="utf-8"?>\n<!-- Added by Archie so C# builds work offline. -->\n'
                                '<configuration><packageSources><clear /></packageSources></configuration>\n')
        except OSError:
            pass
    code, out = _run([rt["dotnet"], "build", proj, "-nologo", "-v", "q", "-clp:NoSummary"], cwd=os.path.dirname(proj), timeout=240)
    probs, seen = [], set()
    for m in re.finditer(r"^(.*?\.cs)\((\d+),(\d+)\):\s*(error|warning)\s+(\w+):\s*(.*?)(?:\s+\[.*\])?$", out, re.M):
        key = m.group(1, 2, 5)
        if key in seen or os.path.basename(m.group(1)).lower() != os.path.basename(path).lower():
            continue
        seen.add(key)
        probs.append(_p(m.group(2), m.group(3), m.group(4), m.group(6), m.group(5)))
    return "dotnet build", probs


def check_ino(path, rt, board="arduino:avr:uno"):
    if "arduino" not in rt:
        return "arduino (install arduino-cli to check it)", []
    code, out = _run([rt["arduino"], "compile", "--fqbn", board, os.path.dirname(path)], timeout=300)
    if re.search(r"platform not installed|Platform '.*' not found", out or "", re.I):
        return "arduino (board support not installed yet: run checks after 'get Arduino board support')", []
    probs = _gcc_parse(out, path)
    if code and not probs:
        tail = out.strip().splitlines()[-3:] if out.strip() else ["arduino-cli failed"]
        probs = [_p(None, None, "error", " ".join(tail), "arduino")]
    return "arduino-cli compile", probs


def check_gd(path, rt):
    if "godot" not in rt:
        return "gdscript (install Godot to check it)", []
    code, out = _run([rt["godot"], "--headless", "--check-only", "--script", path], timeout=60)
    probs = []
    for m in re.finditer(r"(?:Parse Error|SCRIPT ERROR|ERROR):?\s*(.*?)\n.*?:(\d+)", out, re.S):
        probs.append(_p(m.group(2), None, "error", m.group(1), "godot"))
    return "godot --check-only", probs


# ---------------------------------------------------------------- one entry point
def check(path, rt, root=None, deep=False, board=None):
    ext = os.path.splitext(path)[1].lower()
    if ext in SLOW and not deep:
        return {"ok": True, "tool": "", "problems": [], "summary": "", "skipped": True}
    try:
        if ext == ".py":
            tool, probs = check_python(path, rt)
        elif ext in (".js", ".mjs"):
            tool, probs = check_js(path, rt)
        elif ext in (".html", ".htm"):
            tool, probs = check_html(path, rt, root)
        elif ext == ".css":
            tool, probs = check_css(path, rt)
        elif ext == ".json":
            tool, probs = check_json(path, rt)
        elif ext in (".c", ".h", ".cpp", ".hpp", ".cc"):
            tool, probs = check_c(path, rt, root)
        elif ext == ".java":
            tool, probs = check_java(path, rt, root)
        elif ext == ".cs":
            tool, probs = check_cs(path, rt, root)
        elif ext == ".ino":
            tool, probs = check_ino(path, rt, board or "arduino:avr:uno")
        elif ext == ".gd":
            tool, probs = check_gd(path, rt)
        else:
            return {"ok": True, "tool": "", "problems": [], "summary": "", "skipped": True}
    except OSError as e:
        return {"ok": True, "tool": "", "problems": [], "summary": "couldn't check: %s" % e, "skipped": True}
    probs.sort(key=lambda p: (p["sev"] != "error", p["line"] or 0))
    probs = probs[:40]
    errs = sum(1 for p in probs if p["sev"] == "error")
    warns = len(probs) - errs
    summary = "no problems" if not probs else ", ".join(x for x in ("%d error%s" % (errs, "" if errs == 1 else "s") if errs else "",
                                                                     "%d warning%s" % (warns, "" if warns == 1 else "s") if warns else "") if x)
    return {"ok": errs == 0, "tool": tool, "problems": probs, "summary": summary}


def as_text(rel, res, limit=12):
    """The problems as plain lines, for people and for the model."""
    out = []
    for p in res.get("problems", [])[:limit]:
        out.append("%s line %s: %s%s%s" % (rel, p["line"] or "?", "ERROR " if p["sev"] == "error" else "warning ", p["msg"], (" [%s]" % p["code"]) if p["code"] else ""))
    return "\n".join(out)
