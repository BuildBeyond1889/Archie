"""
archie_obsidian.py - connects Archie to your Obsidian vault.

  * Finds your vault (the folder with an .obsidian settings folder inside).
  * Saves Archie answers or whole chats as Obsidian notes in an "Archie" folder,
    with tags and [[links]] to your related notes, so they show up in the graph.
  * Opens a saved note straight in Obsidian.

Reading the vault for search is done by the Notes search (archie_brain.NotesIndex).
"""

import datetime
import os
import re
import sys
import urllib.parse

ARCHIE_FOLDER = "Archie"
HUB_NOTE = "Archie"   # every saved note links here, making an "Archie" cluster in the graph


def count_notes(folder, limit=2000):
    n = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        n += sum(f.endswith(".md") for f in files)
        if n >= limit:
            break
    return n


def find_default_vault():
    """Your main vault: the folder in Documents with .obsidian and the most notes."""
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    best, most = None, 0
    try:
        for name in os.listdir(docs):
            path = os.path.join(docs, name)
            if os.path.isdir(os.path.join(path, ".obsidian")):
                n = count_notes(path)
                if n > most:
                    best, most = path, n
    except OSError:
        pass
    return best


def safe_filename(title, max_len=80):
    t = re.sub(r'[\\/:*?"<>|#^\[\]]', " ", title)
    t = " ".join(t.split()).strip(" .")
    return (t[:max_len].rstrip(" .") or "Archie note")


def link_name(rel_in_vault):
    """How Obsidian links to a file: notes by name without .md, others with extension."""
    base = os.path.basename(rel_in_vault)
    return base[:-3] if base.lower().endswith(".md") else base


def related_links(notes_index, text, label="Obsidian", k=6, want=3):
    """[[links]] to the vault notes closest in meaning to this text."""
    try:
        hits = notes_index.search(text[:2000], k=k, min_score=0.5)
    except Exception:
        return []
    links = []
    for _, rel, _ in hits:
        if not rel.startswith(label + "/"):
            continue
        inside = rel[len(label) + 1:]
        if inside.startswith(ARCHIE_FOLDER + "/"):
            continue       # prefer linking to your own notes, not Archie's
        name = link_name(inside)
        if name not in links:
            links.append(name)
        if len(links) >= want:
            break
    return links


def _tag(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def build_note(title, sections, mode, links, when=None):
    """sections: [(question, answer), ...]"""
    when = when or datetime.datetime.now()
    tags = ["archie"] + ([_tag(mode)] if mode and mode != "General" else [])
    lines = ["---",
             f"created: {when.strftime('%Y-%m-%d %H:%M')}",
             "source: Archie",
             f"mode: {mode or 'General'}",
             "tags: [" + ", ".join(tags) + "]",
             "---",
             f"# {title}", ""]
    for q, a in sections:
        q_lines = (q or "").strip().splitlines() or [""]
        lines.append(f"> [!question] {q_lines[0]}")
        lines += [f"> {l}" for l in q_lines[1:]]
        lines += ["", (a or "").strip(), ""]
    lines.append("---")
    if links:
        lines.append("Related: " + " · ".join(f"[[{l}]]" for l in links))
    lines.append(f"Saved by [[{HUB_NOTE}]]")
    return "\n".join(lines) + "\n"


def ensure_hub(vault):
    folder = os.path.join(vault, ARCHIE_FOLDER)
    os.makedirs(folder, exist_ok=True)
    hub = os.path.join(folder, HUB_NOTE + ".md")
    if not os.path.exists(hub):
        with open(hub, "w", encoding="utf-8") as f:
            f.write("---\ntags: [archie]\n---\n# Archie\n\n"
                    "Notes saved from ARCHIE (Artificial Reasoning Core, Home Intelligence "
                    "Engine), my offline AI. Every saved note links back here, so they "
                    "cluster together in the graph view.\n")
    return folder


def build_voice_note(title, text, secs, links, audio=None, when=None):
    """A voice note: the (edited) transcript, the recording embedded if kept."""
    when = when or datetime.datetime.now()
    m, sec = divmod(int(round(secs)), 60)
    lines = ["---",
             f"created: {when.strftime('%Y-%m-%d %H:%M')}",
             "source: Archie",
             f"length: {m}:{sec:02d}",
             "tags: [archie, voice-note]",
             "---",
             f"# {title}", ""]
    if audio:
        lines += [f"![[{audio}]]", ""]
    lines += [(text or "").strip(), "", "---"]
    if links:
        lines.append("Related: " + " · ".join(f"[[{l}]]" for l in links))
    lines.append(f"Voice note saved by [[{HUB_NOTE}]]")
    return "\n".join(lines) + "\n"


def save_note(vault, title, text, subfolder=None):
    """Write the note into <vault>/Archie/ (or a sub-folder of it). Returns its path inside the vault."""
    folder = ensure_hub(vault)
    rel_folder = ARCHIE_FOLDER
    if subfolder:
        folder = os.path.join(folder, subfolder)
        os.makedirs(folder, exist_ok=True)
        rel_folder = f"{ARCHIE_FOLDER}/{subfolder}"
    base = safe_filename(title)
    name, n = base + ".md", 2
    while os.path.exists(os.path.join(folder, name)):
        name = f"{base} ({n}).md"
        n += 1
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write(text)
    return f"{rel_folder}/{name}"


def open_in_obsidian(vault, rel):
    """Open the note in Obsidian (falls back to the default app for .md files)."""
    url = ("obsidian://open?vault=" + urllib.parse.quote(os.path.basename(vault.rstrip("\\/")))
           + "&file=" + urllib.parse.quote(rel[:-3] if rel.endswith(".md") else rel))
    try:
        if sys.platform == "win32":
            os.startfile(url)
        else:
            import webbrowser
            webbrowser.open(url)
    except OSError:
        path = os.path.join(vault, rel)
        if sys.platform == "win32":
            os.startfile(path)


# ---------------------------------------------------------------------------
# Talking to the running Obsidian app (the "Local REST API" community plugin)
# ---------------------------------------------------------------------------

class LocalApi:
    """Lets Archie see the note you have open in Obsidian, and open notes for you.
    Needs the free 'Local REST API' plugin turned on in Obsidian. Only ever talks
    to 127.0.0.1 (this PC). The key is read from the plugin's own settings."""

    PLUGIN_ID = "obsidian-local-rest-api"

    def __init__(self, get_vault):
        self.get_vault = get_vault

    def _settings(self):
        vault = self.get_vault()
        if not vault:
            return None
        path = os.path.join(vault, ".obsidian", "plugins", self.PLUGIN_ID, "data.json")
        try:
            import json
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def installed(self):
        return self._settings() is not None

    def _request(self, method, route, accept=None, body=None, timeout=4):
        import json
        import ssl
        import urllib.request
        s = self._settings()
        if not s or not s.get("apiKey"):
            raise ApiError("not_installed")
        if s.get("enableInsecureServer"):
            base, ctx = f"http://127.0.0.1:{int(s.get('insecurePort') or 27123)}", None
        else:
            base = f"https://127.0.0.1:{int(s.get('port') or 27124)}"
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE        # its certificate is self-made; this is 127.0.0.1 only
        req = urllib.request.Request(base + route, method=method, data=body)
        req.add_header("Authorization", "Bearer " + s["apiKey"])
        if accept:
            req.add_header("Accept", accept)
        if body is not None:
            req.add_header("Content-Type", "text/markdown")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read()
                ctype = resp.headers.get("Content-Type", "")
                return json.loads(raw) if "json" in ctype and raw else raw.decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ApiError("no_note")
            if e.code in (401, 403):
                raise ApiError("bad_key")
            raise ApiError(f"http {e.code}")
        except (urllib.error.URLError, OSError):
            raise ApiError("not_running")

    def active_note(self):
        """{'path': 'School/Bio.md', 'content': '...'} for the note open in Obsidian."""
        data = self._request("GET", "/active/", accept="application/vnd.olrapi.note+json")
        if isinstance(data, dict):
            return {"path": data.get("path", ""), "content": data.get("content", "")}
        return {"path": "", "content": str(data)}

    def open_note(self, rel):
        self._request("POST", "/open/" + urllib.parse.quote(rel.replace("\\", "/")))


class ApiError(Exception):
    MESSAGES = {
        "not_installed": "To read the note you have open, Obsidian needs the free Local REST API "
                         "plugin: Obsidian > Settings > Community plugins > Browse > \"Local REST "
                         "API\" > Install > Enable. Then ask me again.",
        "not_running": "Obsidian doesn't seem to be open (or the Local REST API plugin is turned "
                       "off), so I can't see your current note.",
        "no_note": "Obsidian is open, but no note is open right now. Click into the note first.",
        "bad_key": "Obsidian refused me (the Local REST API key changed?). Restart Archie and try again.",
    }

    def friendly(self):
        return self.MESSAGES.get(str(self), f"Couldn't reach Obsidian ({self}).")
