"""Graders for course exercises in languages other than Python.

Every grader returns a list of results like {"ok", "name", "hidden", "why"} built by the caller's _res().
Test kinds (an exercise can mix them):
  program tests   {"stdin": "...", "out": [...], "exact": "...", "not": [...]}   run the program, compare what it prints
  call tests      {"call": "<expression>", "expect": ...}                         call your function, compare the result
                  Java / C# / C / C++ compare the printed value as text; JavaScript compares the JSON value
  source tests    {"src_has": "...", "src_not": "...", "why": "..."}              look at your code (comments ignored)
  page tests      {"html": [rules]}                                               look at a web page's structure (see check_page)
  checker tests   {"clean": true}                                                 Archie's real checker must find no errors
"""
import html.parser
import json
import os
import re
import shutil
import subprocess
import tempfile

NOWIN = 0x08000000 if os.name == "nt" else 0


def run(cmd, cwd, stdin="", timeout=20):
    try:
        c = subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace",
                           creationflags=NOWIN, env=dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_NOLOGO="1", DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1"))
        err = "\n".join(l for l in (c.stderr or "").splitlines() if not l.startswith("Picked up JAVA_TOOL_OPTIONS"))
        return c.returncode, c.stdout, err
    except subprocess.TimeoutExpired:
        return None, "", "It didn't finish in %d seconds (a loop that never ends, or waiting for input the test didn't give?)." % timeout
    except OSError as e:
        return None, "", str(e)


def norm(s, case=False):
    s = re.sub(r"[ \t]+", " ", str(s)).strip()
    s = "\n".join(l.strip() for l in s.splitlines())
    return s if case else s.lower()


def strip_comments(src, ext):
    if ext in (".py",):
        return "\n".join(l for l in src.splitlines() if not l.strip().startswith("#"))
    if ext in (".html", ".htm"):
        return re.sub(r"<!--.*?-->", "", src, flags=re.S)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return "\n".join(re.sub(r"(^|\s)//.*$", "", l) for l in src.splitlines())


def compare_out(t, got):
    want = t.get("out") or []
    want = [want] if isinstance(want, str) else want
    hay = norm(got, t.get("case", False))
    miss = [w for w in want if norm(w, t.get("case", False)) not in hay]
    if "exact" in t and norm(got, True) != norm(t["exact"], True):
        miss.append(t["exact"])
    if any(norm(x) in hay for x in t.get("not") or []):
        miss.append("(it printed something it shouldn't: %s)" % ", ".join(t["not"]))
    return miss


def program_result(t, code, out, err):
    if code is None:
        return False, err
    if code:
        last = (err.strip().splitlines() or out.strip().splitlines() or ["?"])
        return False, "It stopped with an error:\n" + "\n".join(last[-3:])
    miss = compare_out(t, out)
    return not miss, "" if not miss else "Expected to see: %s\nIt printed: %s" % (" / ".join(repr(m) for m in miss), out.strip()[-300:] or "(nothing)")


def source_results(tests, src):
    out = []
    for t in tests:
        ok = True
        if "src_has" in t and t["src_has"].replace(" ", "") not in src.replace(" ", ""):
            ok = False
        if "src_not" in t and t["src_not"].replace(" ", "") in src.replace(" ", ""):
            ok = False
        out.append((t, ok, "" if ok else t.get("why", "Read the task again: the code needs a particular piece.")))
    return out


def split_tests(tests):
    prog = [t for t in tests if "stdin" in t or "out" in t or "exact" in t]
    call = [t for t in tests if "call" in t]
    src = [t for t in tests if "src_has" in t or "src_not" in t]
    page = [t for t in tests if "html" in t]
    clean = [t for t in tests if t.get("clean")]
    return prog, call, src, page, clean


def _javac(rt):
    j = rt.get("javac")
    if not j and rt.get("java"):
        cand = os.path.join(os.path.dirname(rt["java"]), "javac" + (".exe" if os.name == "nt" else ""))
        j = cand if os.path.exists(cand) else None
    return j or shutil.which("javac")


# ------------------------------------------------------------------------------------------------ Java
def grade_java(ex, path, rt):
    javac, java = _javac(rt), rt.get("java") or shutil.which("java")
    if not javac or not java:
        return None, "Java isn't installed (Get Code Editor.bat can add it)."
    prog, call, src, page, clean = split_tests(ex.get("tests") or [])
    tmp = tempfile.mkdtemp(prefix="archie-java-")
    res = []
    try:
        cls = os.path.splitext(os.path.basename(path))[0]
        shutil.copy(path, os.path.join(tmp, os.path.basename(path)))
        files = [os.path.basename(path)]
        if call:
            lines = ["public class ArchieHarness {", "  public static void main(String[] archieArgs) {"]
            for i, t in enumerate(call):
                lines.append('    try { System.out.println("@@%d@@" + String.valueOf(%s)); } catch (Throwable e) { System.out.println("@@%d@@!ERR " + e.getClass().getName()); }' % (i, t["call"], i))
            lines += ["  }", "}"]
            with open(os.path.join(tmp, "ArchieHarness.java"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            files.append("ArchieHarness.java")
        code, out, err = run([javac, "-encoding", "UTF-8", "-d", "."] + files, tmp, timeout=90)
        if code:
            msg = "It doesn't compile yet:\n" + "\n".join((err or out).strip().splitlines()[:6])
            if call and "ArchieHarness" in (err or out) and os.path.basename(path) not in (err or out):
                msg = "The test couldn't call your code. Check the class and method names and the parameters match the task.\n" + "\n".join((err or out).strip().splitlines()[:4])
            return [(t, False, msg) for t in prog + call] + [(t, ok, w) for t, ok, w in source_results(src, strip_comments(open(path, encoding="utf-8").read(), ".java"))], None
        for t in prog:
            c, o, e = run([java, "-cp", ".", cls], tmp, t.get("stdin", ""), timeout=t.get("timeout", 10))
            ok, why = program_result(t, c, o, e)
            res.append((t, ok, why))
        if call:
            c, o, e = run([java, "-cp", ".", "ArchieHarness"], tmp, "", timeout=15)
            got = dict(re.findall(r"@@(\d+)@@(.*)", o))
            for i, t in enumerate(call):
                g = got.get(str(i))
                want = t["expect"] if isinstance(t["expect"], str) else json.dumps(t["expect"])
                ok = g is not None and g.strip() == str(want)
                res.append((t, ok, "" if ok else "%s gave %s, expected %s" % (t["call"], g if g is not None else "nothing (it crashed or never returned)", want)))
        res += source_results(src, strip_comments(open(path, encoding="utf-8").read(), ".java"))
        return res, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ C and C++
def grade_c(ex, path, rt):
    cpp = path.lower().endswith((".cpp", ".cc"))
    cc = rt.get("g++" if cpp else "gcc") or shutil.which("g++" if cpp else "gcc")
    if not cc:
        return None, "The %s compiler isn't installed (Get Code Editor.bat can add it)." % ("C++" if cpp else "C")
    prog, call, src, page, clean = split_tests(ex.get("tests") or [])
    tmp = tempfile.mkdtemp(prefix="archie-c-")
    res = []
    try:
        name = os.path.basename(path)
        shutil.copy(path, os.path.join(tmp, name))
        std = ["-std=c++17"] if cpp else ["-std=c11"]
        if prog:
            code, out, err = run([cc] + std + ["-Wall", "-o", "prog.exe", name, "-lm"], tmp, timeout=90)
            if code:
                msg = "It doesn't compile yet:\n" + "\n".join(l for l in (err or out).splitlines() if "error" in l)[:900]
                res += [(t, False, msg) for t in prog]
            else:
                for t in prog:
                    c, o, e = run([os.path.join(tmp, "prog.exe")], tmp, t.get("stdin", ""), timeout=t.get("timeout", 10))
                    ok, why = program_result(t, c, o, e)
                    res.append((t, ok, why))
        if call:
            # the learner's main() is renamed while their file is included, so the harness can have its own
            head = ['#define main learner_main', '#include "%s"' % name, '#undef main']
            if cpp:
                body = ["#include <iostream>", "#include <string>", "#include <vector>"] + head + ["int main() {", "  std::cout << std::boolalpha;"]
                for i, t in enumerate(call):
                    body.append('  std::cout << "@@%d@@" << (%s) << "\\n";' % (i, t["call"]))
            else:
                body = ["#include <stdio.h>", "#include <stdbool.h>"] + head + ["int main(void) {"]
                for i, t in enumerate(call):
                    body.append('  printf("@@%d@@%s\\n", %s);' % (i, t.get("fmt", "%d"), t["call"]))
            body += ["  return 0;", "}"]
            hname = "archie_harness" + (".cpp" if cpp else ".c")
            with open(os.path.join(tmp, hname), "w", encoding="utf-8") as f:
                f.write("\n".join(body))
            code, out, err = run([cc] + std + ["-o", "harness.exe", hname, "-lm"], tmp, timeout=90)
            if code:
                msg = "It doesn't compile yet (or the function's name or parameters don't match the task):\n" + "\n".join(l for l in (err or out).splitlines() if "error" in l)[:900]
                res += [(t, False, msg) for t in call]
            else:
                c, o, e = run([os.path.join(tmp, "harness.exe")], tmp, "", timeout=15)
                got = dict(re.findall(r"@@(\d+)@@(.*)", o))
                for i, t in enumerate(call):
                    g = got.get(str(i))
                    want = t["expect"] if isinstance(t["expect"], str) else json.dumps(t["expect"])
                    ok = g is not None and g.strip() == str(want)
                    res.append((t, ok, "" if ok else "%s gave %s, expected %s" % (t["call"], g if g is not None else "nothing (it crashed)", want)))
        res += source_results(src, strip_comments(open(path, encoding="utf-8").read(), ".c"))
        return res, None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ C#
CSPROJ = """<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType><TargetFramework>net8.0</TargetFramework>
<Nullable>disable</Nullable><ImplicitUsings>enable</ImplicitUsings><StartupObject>%s</StartupObject><InvariantGlobalization>true</InvariantGlobalization></PropertyGroup></Project>"""
NUGET = '<?xml version="1.0" encoding="utf-8"?><configuration><packageSources><clear /></packageSources></configuration>'


def grade_cs(ex, path, rt):
    dn = rt.get("dotnet") or shutil.which("dotnet")
    if not dn:
        return None, ".NET isn't installed (Get Code Editor.bat can add it)."
    prog, call, src, page, clean = split_tests(ex.get("tests") or [])
    res = []
    code_text = open(path, encoding="utf-8").read()

    def build(extra, startup):
        tmp = tempfile.mkdtemp(prefix="archie-cs-")
        shutil.copy(path, os.path.join(tmp, "Learner.cs"))
        if extra:
            with open(os.path.join(tmp, "ArchieHarness.cs"), "w", encoding="utf-8") as f:
                f.write(extra)
        with open(os.path.join(tmp, "App.csproj"), "w", encoding="utf-8") as f:
            f.write(CSPROJ % startup)
        with open(os.path.join(tmp, "nuget.config"), "w", encoding="utf-8") as f:
            f.write(NUGET)
        c, o, e = run([dn, "build", "App.csproj", "-nologo", "-v", "q", "-o", "out", "-clp:NoSummary"], tmp, timeout=240)
        return tmp, c, o + e

    if prog:
        m = re.search(r"\bclass\s+(\w+)[^{]*\{[^}]*?static\s+(?:async\s+)?\w+\s+Main\s*\(", code_text, re.S)
        start = m.group(1) if m else "Program"
        ns = re.search(r"^\s*namespace\s+([\w.]+)", code_text, re.M)
        tmp, c, out = build("", (ns.group(1) + "." if ns else "") + start)
        try:
            if c:
                msg = "It doesn't compile yet:\n" + "\n".join(sorted(set(l.split("[")[0].strip() for l in out.splitlines() if " error " in l)))[:900]
                res += [(t, False, msg) for t in prog]
            else:
                dll = os.path.join(tmp, "out", "App.dll")
                for t in prog:
                    c2, o2, e2 = run([dn, dll], tmp, t.get("stdin", ""), timeout=t.get("timeout", 15))
                    ok, why = program_result(t, c2, o2, e2)
                    res.append((t, ok, why))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if call:
        body = ["using System; using System.Globalization;", "public static class ArchieHarness {", "  public static void Main() {",
                "    CultureInfo.DefaultThreadCurrentCulture = CultureInfo.InvariantCulture; CultureInfo.CurrentCulture = CultureInfo.InvariantCulture;"]
        for i, t in enumerate(call):
            body.append('    try { Console.WriteLine("@@%d@@" + Show(%s)); } catch (Exception e) { Console.WriteLine("@@%d@@!ERR " + e.GetType().Name); }' % (i, t["call"], i))
        body += ["  }",
                 "  static string Show(object o) { if (o == null) return \"null\"; if (o is bool b) return b ? \"true\" : \"false\";"
                 " if (o is System.Collections.IEnumerable e && !(o is string)) { var p = new System.Collections.Generic.List<string>(); foreach (var x in e) p.Add(Show(x)); return \"[\" + string.Join(\", \", p) + \"]\"; }"
                 " return Convert.ToString(o, CultureInfo.InvariantCulture); }", "}"]
        tmp, c, out = build("\n".join(body), "ArchieHarness")
        try:
            if c:
                msg = "It doesn't compile yet (or the method's name or parameters don't match the task):\n" + "\n".join(sorted(set(l.split("[")[0].strip() for l in out.splitlines() if " error " in l)))[:900]
                res += [(t, False, msg) for t in call]
            else:
                c2, o2, e2 = run([dn, os.path.join(tmp, "out", "App.dll")], tmp, "", timeout=20)
                got = dict(re.findall(r"@@(\d+)@@(.*)", o2))
                for i, t in enumerate(call):
                    g = got.get(str(i))
                    want = t["expect"] if isinstance(t["expect"], str) else json.dumps(t["expect"])
                    ok = g is not None and g.strip() == str(want)
                    res.append((t, ok, "" if ok else "%s gave %s, expected %s" % (t["call"], g if g is not None else "nothing (it crashed)", want)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    res += source_results(src, strip_comments(code_text, ".cs"))
    return res, None


# ------------------------------------------------------------------------------------------------ JavaScript
JS_HARNESS = r"""
const vm = require("vm"), fs = require("fs");
const [path, testsPath, stdin] = [process.argv[2], process.argv[3], process.argv[4] || ""];
const tests = JSON.parse(fs.readFileSync(testsPath, "utf8"));
const logs = [];
// a small pretend page, so scripts that use document.getElementById, addEventListener and click() can be tested without a browser
function makeEl(id, tag) {
  const el = { id, tagName: (tag || "div").toUpperCase(), textContent: "", innerHTML: "", value: "", checked: false, disabled: false, style: {}, dataset: {}, children: [], _l: {},
    classList: { _s: new Set(), add(...c) { c.forEach((x) => this._s.add(x)); }, remove(...c) { c.forEach((x) => this._s.delete(x)); }, toggle(c, f) { const on = f === undefined ? !this._s.has(c) : f; on ? this._s.add(c) : this._s.delete(c); return on; }, contains(c) { return this._s.has(c); } },
    addEventListener(t, f) { (this._l[t] = this._l[t] || []).push(f); },
    removeEventListener(t, f) { this._l[t] = (this._l[t] || []).filter((x) => x !== f); },
    dispatch(t) { const ev = { type: t, target: el, currentTarget: el, preventDefault() {} }; (this._l[t] || []).forEach((f) => f(ev)); if (typeof this["on" + t] === "function") this["on" + t](ev); },
    click() { this.dispatch("click"); },
    appendChild(c) { this.children.push(c); c.parentNode = this; return c; }, append(...c) { c.forEach((x) => this.appendChild(typeof x === "string" ? Object.assign(makeEl(""), { textContent: x }) : x)); },
    remove() {}, setAttribute(k, v) { this[k] = String(v); }, getAttribute(k) { return this[k] === undefined ? null : this[k]; },
    querySelector() { return null; }, querySelectorAll() { return []; }, focus() {} };
  return el;
}
const document = { _els: {}, getElementById(id) { return this._els[id] = this._els[id] || makeEl(id); },
  querySelector(sel) { return sel[0] === "#" ? this.getElementById(sel.slice(1)) : (this._els["q:" + sel] = this._els["q:" + sel] || makeEl("", sel.replace(/[^a-z].*$/i, "") || "div")); },
  querySelectorAll() { return []; }, createElement(t) { return makeEl("", t); }, createTextNode(t) { return Object.assign(makeEl(""), { textContent: t }); },
  addEventListener(t, f) { if (t === "DOMContentLoaded") f(); }, body: makeEl("body", "body") };
const storage = { d: {}, getItem(k) { return k in this.d ? this.d[k] : null; }, setItem(k, v) { this.d[k] = String(v); }, removeItem(k) { delete this.d[k]; }, clear() { this.d = {}; }, get length() { return Object.keys(this.d).length; }, key(i) { return Object.keys(this.d)[i] ?? null; } };
// fetch() reads files that sit next to the exercise, so lessons about fetch work offline
const pathMod = require("path"), baseDir = pathMod.dirname(path);
function fakeFetch(url) {
  const rel = String(url).replace(/^\.\//, "").split("?")[0];
  const file = pathMod.join(baseDir, rel);
  return new Promise((resolve) => {
    if (/^https?:/i.test(String(url)) || !file.startsWith(baseDir) || !fs.existsSync(file)) { resolve({ ok: false, status: 404, statusText: "Not Found", json: async () => { throw new SyntaxError("Unexpected token N in JSON"); }, text: async () => "Not Found" }); return; }
    const txt = fs.readFileSync(file, "utf8");
    resolve({ ok: true, status: 200, statusText: "OK", json: async () => JSON.parse(txt), text: async () => txt });
  });
}
const sandbox = { console: { log: (...a) => logs.push(a.join(" ")), error: () => {}, warn: () => {} }, module: { exports: {} }, Math, JSON, Number, String, Array, Object, Date, parseInt, parseFloat, isNaN, isFinite, Set, Map,
  document, localStorage: storage, fetch: fakeFetch, Promise, alert() {}, confirm() { return true; }, prompt() { return null; }, setTimeout: (f) => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {}, logs };
sandbox.exports = sandbox.module.exports; sandbox.globalThis = sandbox; sandbox.window = sandbox;
vm.createContext(sandbox);
let loadErr = null;
try { vm.runInContext(fs.readFileSync(path, "utf8") + "\n;globalThis.__names = {};", sandbox, { timeout: 3000 }); } catch (e) { loadErr = String(e); }
const out = [];
// results that come later (async functions, fetch) are waited for, up to 3 seconds
const settle = (v) => (v && typeof v.then === "function") ? Promise.race([v, new Promise((_, no) => setTimeoutReal(() => no(new Error("it never finished (a promise that never resolves?)")), 3000))]) : v;
const setTimeoutReal = setTimeout;
(async () => {
for (const t of tests) {
  if (loadErr) { out.push({ ok: false, got: "Your file stopped with an error before any test ran: " + loadErr }); continue; }
  try {
    if (t.check) { await settle(vm.runInContext(t.check, sandbox, { timeout: 3000 })); out.push({ ok: true }); continue; }
    logs.length = 0;
    const got = await settle(vm.runInContext(t.call, sandbox, { timeout: 3000 }));
    const same = JSON.stringify(got) === JSON.stringify(t.expect) || (typeof got === "number" && typeof t.expect === "number" && Math.abs(got - t.expect) < 1e-9);
    out.push(same ? { ok: true } : { ok: false, got: JSON.stringify(got), want: JSON.stringify(t.expect) });
  } catch (e) { out.push({ ok: false, got: String(e) }); }
}
console.log("@@ARCHIE@@" + JSON.stringify(out));
})();
"""


def grade_js(ex, path, rt):
    node = rt.get("node") or shutil.which("node")
    if not node:
        return None, "Node.js isn't installed (Get Code Editor.bat can add it)."
    prog, call, src, page, clean = split_tests(ex.get("tests") or [])
    checks = [t for t in ex.get("tests") or [] if "check" in t]
    res = []
    for t in prog:
        c, o, e = run([node, path], os.path.dirname(path), t.get("stdin", ""), timeout=t.get("timeout", 10))
        ok, why = program_result(t, c, o, e)
        res.append((t, ok, why))
    fn = call + checks
    if fn:
        tmp = tempfile.mkdtemp(prefix="archie-js-")
        try:
            hp, tp = os.path.join(tmp, "h.js"), os.path.join(tmp, "t.json")
            with open(hp, "w", encoding="utf-8") as f:
                f.write(JS_HARNESS)
            with open(tp, "w", encoding="utf-8") as f:
                json.dump(fn, f)
            c, o, e = run([node, hp, path, tp], tmp, timeout=20)
            got = json.loads(o.split("@@ARCHIE@@")[-1]) if "@@ARCHIE@@" in o else [{"ok": False, "got": (e.strip().splitlines() or ["the tests couldn't run"])[-1]}] * len(fn)
            for t, g in zip(fn, got):
                why = "" if g["ok"] else ("%s gave %s, expected %s" % (t.get("call"), g.get("got"), g.get("want")) if "want" in g else g.get("got", ""))
                res.append((t, g["ok"], why))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    res += source_results(src, strip_comments(open(path, encoding="utf-8").read(), ".js"))
    return res, None


# ------------------------------------------------------------------------------------------------ web pages
class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids, self.text = tag, dict(attrs), parent, [], ""

    def all_text(self):
        return self.text + " ".join(k.all_text() for k in self.kids)


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class _Tree(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", {}, None)
        self.cur = self.root
        self.styles = []
        self._style = False

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n
        self._style = tag == "style"

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent
        self._style = False

    def handle_data(self, data):
        self.cur.text += data
        if self._style:
            self.styles.append(data)


def _walk(n):
    for k in n.kids:
        yield k
        yield from _walk(k)


def _match_simple(n, sel):
    m = re.match(r"^([a-zA-Z][\w-]*|\*)?((?:[#.][\w-]+|\[[^\]]+\])*)$", sel)
    if not m:
        return False
    tag, rest = m.group(1), m.group(2)
    if tag and tag != "*" and n.tag != tag.lower():
        return False
    for part in re.findall(r"[#.][\w-]+|\[[^\]]+\]", rest):
        if part[0] == "#" and n.attrs.get("id") != part[1:]:
            return False
        if part[0] == "." and part[1:] not in (n.attrs.get("class") or "").split():
            return False
        if part[0] == "[":
            k, _, v = part[1:-1].partition("=")
            if k.strip() not in n.attrs or (v and (n.attrs.get(k.strip()) or "") != v.strip().strip("\"'")):
                return False
    return True


def select(root, selector):
    out = []
    for sel in selector.split(","):
        parts = sel.split()
        for n in _walk(root):
            if not parts or not _match_simple(n, parts[-1]):
                continue
            p, i = n.parent, len(parts) - 2
            while i >= 0 and p is not None:
                if _match_simple(p, parts[i]):
                    i -= 1
                p = p.parent
            if i < 0 and n not in out:
                out.append(n)
    return out


def css_rules(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    rules = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", text):
        sel = m.group(1).strip()
        if sel.startswith("@"):
            continue
        sel = re.sub(r"^.*\{", "", sel).strip()
        decls = {}
        for d in m.group(2).split(";"):
            if ":" in d:
                k, v = d.split(":", 1)
                decls[k.strip().lower()] = v.strip().lower()
        rules.append((re.sub(r"\s+", " ", sel), decls))
    return rules, ("@media" in text)


def check_page(path, rules):
    """Rules: {"has": sel, "min": n} · {"text": sel, "contains": s} · {"attr": sel, "needs": name} · {"css": sel, "prop": p, "value": v (optional)}
    · {"media": true} (a phone-width @media rule exists). Returns [(ok, why)]."""
    src = open(path, encoding="utf-8", errors="replace").read()
    t = _Tree()
    try:
        t.feed(src)
    except Exception as e:      # noqa: BLE001
        return [(False, "The page couldn't be read: %s" % e)] * len(rules)
    css = "\n".join(t.styles)
    for ln in select(t.root, "link[rel=stylesheet]"):
        href = (ln.attrs.get("href") or "").split("?")[0]
        p = os.path.join(os.path.dirname(path), href)
        if href and os.path.isfile(p):
            css += "\n" + open(p, encoding="utf-8", errors="replace").read()
    if path.lower().endswith(".css"):
        css = src
    rl, has_media = css_rules(css)
    out = []
    for r in rules:
        if "has" in r:
            n = len(select(t.root, r["has"]))
            ok = n >= r.get("min", 1)
            out.append((ok, "" if ok else "Expected at least %d %s on the page, found %d." % (r.get("min", 1), r["has"], n)))
        elif "text" in r:
            ns = select(t.root, r["text"])
            ok = any(r["contains"].lower() in n.all_text().lower() for n in ns)
            out.append((ok, "" if ok else "Expected a %s with the text \"%s\"." % (r["text"], r["contains"])))
        elif "attr" in r:
            ns = select(t.root, r["attr"])
            ok = bool(ns) and all((n.attrs.get(r["needs"]) or "").strip() for n in ns)
            out.append((ok, "" if ok else "Every %s needs a %s attribute with something in it." % (r["attr"], r["needs"])))
        elif "css" in r:
            want_sel = re.sub(r"\s+", " ", r["css"].strip())
            hit = [d for s, d in rl if want_sel in [x.strip() for x in s.split(",")] and r["prop"] in d]
            ok = bool(hit) and (not r.get("value") or any(r["value"].lower() in d[r["prop"]] for d in hit))
            out.append((ok, "" if ok else "Expected a CSS rule for %s that sets %s%s." % (r["css"], r["prop"], (" to " + r["value"]) if r.get("value") else "")))
        elif "media" in r:
            out.append((has_media, "" if has_media else "Add an @media rule so the layout changes on narrow (phone) screens."))
    return out


def grade_web(ex, path, rt, checkers=None):
    if path.lower().endswith(".js"):
        return grade_js(ex, path, rt)
    prog, call, src, page, clean = split_tests(ex.get("tests") or [])
    res = []
    if not os.path.isfile(path):
        return [(t, False, "There's no %s yet." % os.path.basename(path)) for t in ex.get("tests") or []], None
    for t in page:
        for ok, why in check_page(path, t["html"]):
            if not ok:
                res.append((t, False, why))
                break
        else:
            res.append((t, True, ""))
    for t in clean:
        if checkers:
            r = checkers.check(path, rt, os.path.dirname(path))
            errs = [p for p in r["problems"] if p["sev"] == "error"]
            res.append((t, not errs, "" if not errs else "Archie's page checker found: " + "; ".join("line %s: %s" % (p["line"], p["msg"]) for p in errs[:4])))
        else:
            res.append((t, True, ""))
    res += source_results(src, strip_comments(open(path, encoding="utf-8").read(), os.path.splitext(path)[1].lower()))
    return res, None
