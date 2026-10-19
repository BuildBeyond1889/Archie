"""
archie_apps.py - "open blender", "launch unity", "make a Godot script called player.gd".

Apps are found fresh from the Windows Start menu (every app you install shows up
there, including Store apps), so anything installed later just works.
Archie only ever launches things that are actually in your Start menu or a few
well-known folders, and never deletes or overwrites a file without asking.
"""

import difflib
import json
import os
import re
import subprocess
import sys
import time

_OPEN = re.compile(r"^\s*(?:hey\s+)?(?:archie[,:]?\s+)?(?:can you\s+|could you\s+|please\s+)?"
                   r"(?:open|launch|start|run|fire up|pull up|bring up|boot up|load up)\s+(?:up\s+)?"
                   r"(?:the\s+|my\s+)?(?P<what>.+?)(?:\s+(?:app|application|program|for me|please|now))*[\s.!?]*$",
                   re.I)
_JUNK = re.compile(r"uninstall|readme|read me|help|documentation|manual|website|release notes|"
                   r"license|licence|changelog|report a bug|support|visit|online|repair|modify", re.I)

EXT_FOR = [
    (r"\bgodot\b|\bgdscript\b|\bgd script\b", ".gd"), (r"\bunity\b|\bc#|\bc sharp\b|\bcsharp\b", ".cs"),
    (r"\bpython\b|\bpy script\b", ".py"), (r"\barduino\b|\bsketch\b", ".ino"),
    (r"\bc\+\+|\bcpp\b", ".cpp"), (r"\bjavascript\b|\bjs\b|\bnode\b", ".js"),
    (r"\btypescript\b", ".ts"), (r"\bhtml\b|\bweb ?page\b|\bwebsite\b", ".html"), (r"\bcss\b", ".css"),
    (r"\bjson\b", ".json"), (r"\blua\b", ".lua"), (r"\bjava\b", ".java"), (r"\bbatch\b|\.bat\b", ".bat"),
    (r"\bpowershell\b", ".ps1"), (r"\bshader\b|\bglsl\b", ".glsl"), (r"\bmarkdown\b|\bnote\b", ".md"),
    (r"\bcsv\b|\bspreadsheet\b", ".csv"), (r"\byaml\b", ".yaml"), (r"\btext file\b|\btxt\b", ".txt"),
]
_FILENAME = re.compile(r"(?<![\w/\\.-])([\w\-]{1,60}\.(?:py|gd|cs|js|ts|html|css|json|md|txt|cpp|h|hpp|c|ino|"
                       r"lua|java|glsl|hlsl|shader|yaml|yml|toml|bat|ps1|csv|xml|ini|cfg|tscn|gdshader))\b", re.I)
_CREATE = re.compile(r"\b(create|make|write|generate|start|build|give me|new)\b", re.I)
_KIND_WORD = re.compile(r"\b(file|script|program|sketch|page|document|doc|module|class|shader|config)\b", re.I)


ALIASES = {"vs code": "visual studio code", "vscode": "visual studio code", "code": "visual studio code",
           "ps": "photoshop", "chrome": "google chrome", "word": "microsoft word", "excel": "microsoft excel",
           "powerpoint": "microsoft powerpoint", "files": "file explorer", "explorer": "file explorer",
           "calculator": "calculator", "calc": "calculator", "task manager": "task manager"}


def _norm(s):
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9+#. ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Apps:
    def __init__(self, folders=None):
        self.folders = folders or {}        # spoken name -> folder path (Notes, vault, ...)
        self._apps = None
        self._when = 0

    # ----- finding what's installed ---------------------------------------------------

    def _scan(self):
        apps = {}
        if sys.platform == "win32":
            try:    # every Start-menu app, including Microsoft Store ones
                out = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress"],
                    capture_output=True, text=True, timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
                data = json.loads(out) if out.strip() else []
                if isinstance(data, dict):
                    data = [data]
                for a in data:
                    name = (a.get("Name") or "").strip()
                    if name and a.get("AppID") and not _JUNK.search(name):
                        apps[name] = ("appid", a["AppID"])
            except Exception:
                pass
            # shortcuts too (covers anything Get-StartApps missed)
            roots = [os.path.join(os.environ.get("ProgramData", ""), r"Microsoft\Windows\Start Menu\Programs"),
                     os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                     os.path.join(os.path.expanduser("~"), "Desktop"),
                     os.path.join(os.environ.get("PUBLIC", ""), "Desktop")]
            for root in roots:
                for dp, _dns, fns in os.walk(root):
                    for fn in fns:
                        if fn.lower().endswith((".lnk", ".url")):
                            name = os.path.splitext(fn)[0]
                            if not _JUNK.search(name) and name not in apps:
                                apps[name] = ("path", os.path.join(dp, fn))
        extras = {"File Explorer": ("cmd", ["explorer.exe"]), "Task Manager": ("cmd", ["taskmgr.exe"]),
                  "Settings": ("path", "ms-settings:"), "Notepad": ("cmd", ["notepad.exe"])}
        for k, v in extras.items():
            apps.setdefault(k, v)
        return apps

    def apps(self, fresh=False):
        if fresh or self._apps is None or time.time() - self._when > 120:
            self._apps = self._scan()
            self._when = time.time()
        return self._apps

    def find(self, what):
        """Best (name, how) for a spoken app name, or (None, suggestions)."""
        q = _norm(what)
        q = re.sub(r"^(the|my)\s+", "", q)
        q = ALIASES.get(q, q)
        for fresh in (False, True):             # just installed? look again
            apps = self.apps(fresh)
            scored = []
            for name, how in apps.items():
                n = _norm(name)
                if not n:
                    continue
                if n == q:
                    s = 100
                elif n.startswith(q + " ") or n.startswith(q):
                    s = 90 - len(n) / 10
                elif re.search(r"\b" + re.escape(q) + r"\b", n):
                    s = 80 - len(n) / 10
                elif all(w in n.split() for w in q.split()):
                    s = 70 - len(n) / 10
                else:
                    r = difflib.SequenceMatcher(None, q, n).ratio()
                    s = r * 70 if r > 0.78 else 0
                if s:
                    scored.append((s, name, how))
            if scored:
                scored.sort(key=lambda x: -x[0])
                return scored[0][1], scored[0][2]
        close = difflib.get_close_matches(q, [_norm(n) for n in self.apps()], n=3, cutoff=0.5)
        return None, close

    # ----- understanding and doing ------------------------------------------------------

    def parse_open(self, text):
        if len(text.split()) > 9:
            return None
        m = _OPEN.match(text)
        return m.group("what").strip() if m else None

    def folder_for(self, what):
        q = _norm(what)
        for key, path in self.folders.items():
            if q == key or q == key + " folder" or q == "my " + key:
                return key, path
        return None, None

    def launch(self, how):
        kind, target = how
        if kind == "appid":
            subprocess.Popen(["explorer.exe", "shell:AppsFolder\\" + target])
        elif kind == "cmd":
            subprocess.Popen(target)
        elif sys.platform == "win32":
            os.startfile(target)
        else:
            subprocess.Popen(["xdg-open", target])


def parse_create(text):
    """{'name': 'player.gd' or None, 'ext': '.gd'} if the message asks to make a file."""
    if not _CREATE.search(text):
        return None
    m = _FILENAME.search(text)
    if m:
        name = m.group(1).strip()
        return {"name": name, "ext": os.path.splitext(name)[1].lower()}
    if not _KIND_WORD.search(text):
        return None
    low = text.lower()
    for pat, ext in EXT_FOR:
        if re.search(pat, low):
            m = re.search(r"\b(?:called|named)\s+[\"']?([\w\- ]{1,40}?)[\"']?(?:\s+(?:that|which|to|with|for)\b|[.!?]|$)",
                          text, re.I)
            name = (m.group(1).strip().replace(" ", "_") + ext) if m else None
            return {"name": name, "ext": ext}
    return None


FILE_PROMPT = """Write the COMPLETE contents of a file named {name}.

What the user asked for: {request}

Rules:
- Output ONLY the file's contents. No explanation before or after, no Markdown code fences.
- Make it complete and working, with short, helpful comments.
- For Unity C# scripts, the class name must match the file name. For Godot, use Godot 4 GDScript.
- For Arduino sketches, include setup() and loop() and note the pins used in a comment at the top."""

NAME_PROMPT = """Suggest a short, good file name (with the {ext} extension) for this request. \
Reply with ONLY the file name.

Request: {request}"""


def clean_code(text):
    t = (text or "").strip()
    m = re.match(r"^```[\w+#.-]*\s*\n(.*?)\n?```\s*$", t, re.S)
    return (m.group(1) if m else t).rstrip() + "\n"
