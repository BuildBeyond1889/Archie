"""The dev coach: a dev log for each game you're making, in any engine (Godot, Unity, Unreal, anything).

You tell it what you're working on or testing ("testing new turret placements; players say the corner turrets
never fire"), and it answers in the same shape every time:
  * what's probably going on
  * the design idea behind it (coverage, chokepoints, pacing, feedback, cost curves...)
  * next steps
  * how to do it in your engine (GDScript for Godot, C# for Unity, Blueprint or C++ for Unreal)
  * a small experiment: what to change and what to measure
  * the concept, as a short teaching note
It remembers each game across sessions: design notes, decisions (with why), what you tried and how it went, and
open questions. It only files what YOU said or decided, never its own suggestions, and you can edit or delete any
of it. Before answering it looks things up in the offline docs (Godot docs, Game Development Q&A, Stack Overflow).

For a Godot or Unity game you can link the project folder: the coach can then read the scripts that matter for your
question (it never writes to them). Unreal projects are never read or touched: advice only.
Everything runs on this PC.
"""
import json
import os
import re
import secrets
import threading
import time

ENGINES = {
    "Godot": {"lang": "GDScript (Godot)", "how": "Godot 4 and GDScript (nodes, scenes, signals); C# only if they ask", "read": (".gd", ".tscn", ".cs", ".gdshader", ".cfg")},
    "Unity": {"lang": "C#", "how": "Unity and C# (MonoBehaviour, components, prefabs, ScriptableObjects, the Inspector)", "read": (".cs", ".shader")},
    "Unreal": {"lang": "C++", "how": "Unreal Engine 5: Blueprint first (name the nodes), and C++ when it matters (UCLASS, UPROPERTY, Tick, components)", "read": ()},
    "Other": {"lang": "", "how": "whatever engine or framework they name; keep it general if unsure", "read": (".py", ".js", ".lua", ".cs", ".cpp", ".gd")},
}
KINDS = ("notes", "decisions", "tried", "questions")
KIND_NAMES = {"notes": "Design notes", "decisions": "Decisions", "tried": "Tried", "questions": "Open questions"}

COACH_RULES = """You are Archie's dev coach: a friendly, experienced game designer and programmer coaching a self-taught developer.
Be concrete and honest. Teach the WHY. Plain words; no emoji; no hype. Short sentences."""


def _now():
    return int(time.time())


def _slug(s):
    s = re.sub(r"[^A-Za-z0-9 _-]+", "", s or "").strip().replace(" ", "-")
    return s[:50] or "game"


class DevCoach:
    def __init__(self, workshop_dir, chat, docs=None, pmem=None, alert=None):
        """chat(system, prompt, tokens, json_mode) -> text."""
        self.dir = os.path.join(workshop_dir, ".games")
        os.makedirs(self.dir, exist_ok=True)
        self.chat = chat
        self.docs = docs
        self.pmem = pmem
        self.alert = alert or (lambda *a: None)
        self.lock = threading.RLock()

    # ------------------------------------------------------------------ storage
    def _gdir(self, gid):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", gid or ""):
            raise ValueError("bad game id")
        return os.path.join(self.dir, gid)

    def _load(self, gid):
        try:
            with open(os.path.join(self._gdir(gid), "game.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _save(self, g):
        d = self._gdir(g["id"])
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "game.json")
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(g, f, indent=1, ensure_ascii=False)
        os.replace(p + ".tmp", p)

    def _log(self, gid, limit=200):
        out = []
        try:
            with open(os.path.join(self._gdir(gid), "log.jsonl"), encoding="utf-8") as f:
                for line in f:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        pass
        except OSError:
            pass
        return out[-limit:]

    def _append(self, gid, entry):
        with open(os.path.join(self._gdir(gid), "log.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ games
    def games(self):
        out = []
        for d in sorted(os.listdir(self.dir)):
            g = self._load(d) if os.path.isdir(os.path.join(self.dir, d)) else None
            if g:
                out.append({k: g.get(k) for k in ("id", "name", "engine", "pitch", "updated", "folder")} | {"entries": len(self._log(d, 100000))})
        out.sort(key=lambda g: -(g.get("updated") or 0))
        return {"games": out, "engines": list(ENGINES)}

    def new(self, b):
        name = (b.get("name") or "").strip()[:80]
        if not name:
            return {"error": "Give the game a name."}
        engine = b.get("engine") if b.get("engine") in ENGINES else "Other"
        folder = (b.get("folder") or "").strip().strip('"')
        if folder and engine == "Unreal":
            folder = ""            # Unreal: advice only, Archie never reads or touches the project
        if folder and not os.path.isdir(folder):
            return {"error": "That folder doesn't exist: %s" % folder}
        gid = _slug(name)
        while os.path.exists(os.path.join(self.dir, gid)):
            gid = _slug(name) + "-" + secrets.token_hex(2)
        g = {"id": gid, "name": name, "engine": engine, "engine_other": (b.get("engine_other") or "").strip()[:60], "pitch": (b.get("pitch") or "").strip()[:1500],
             "folder": folder, "created": _now(), "updated": _now(), "memory": {k: [] for k in KINDS}}
        self._save(g)
        return {"ok": True, "id": gid}

    def get(self, gid):
        g = self._load(gid)
        if not g:
            return {"error": "no such game"}
        return {"game": g, "log": self._log(gid, 80), "kind_names": KIND_NAMES}

    def edit(self, b):
        with self.lock:
            g = self._load(b.get("id"))
            if not g:
                return {"error": "no such game"}
            for k in ("name", "pitch", "engine_other"):
                if k in b:
                    g[k] = str(b[k]).strip()[:1500]
            if b.get("engine") in ENGINES:
                g["engine"] = b["engine"]
            if "folder" in b:
                f = str(b["folder"]).strip().strip('"')
                if f and (g["engine"] == "Unreal" or not os.path.isdir(f)):
                    return {"error": "Unreal projects stay hands-off." if g["engine"] == "Unreal" else "That folder doesn't exist."}
                g["folder"] = f
            g["updated"] = _now()
            self._save(g)
            return {"ok": True}

    def memory(self, b):
        """Add, change or delete one remembered item: {id, op: add|edit|delete, kind, i, text}."""
        with self.lock:
            g = self._load(b.get("id"))
            kind = b.get("kind")
            if not g or kind not in KINDS:
                return {"error": "no such game or kind"}
            L = g["memory"].setdefault(kind, [])
            op = b.get("op")
            text = re.sub(r"\s+", " ", str(b.get("text") or "")).strip()[:400]
            i = b.get("i")
            if op == "add" and text:
                L.append({"text": text, "at": _now(), "by": "you"})
            elif op == "edit" and isinstance(i, int) and 0 <= i < len(L) and text:
                L[i]["text"] = text
            elif op == "delete" and isinstance(i, int) and 0 <= i < len(L):
                L.pop(i)
            else:
                return {"error": "nothing to do"}
            g["updated"] = _now()
            self._save(g)
            return {"ok": True, "memory": g["memory"]}

    def delete(self, gid, trash_dir):
        d = self._gdir(gid)
        if not os.path.isdir(d):
            return {"error": "no such game"}
        os.makedirs(trash_dir, exist_ok=True)
        os.replace(d, os.path.join(trash_dir, "game--%s--%s" % (gid, time.strftime("%Y%m%d-%H%M%S"))))
        return {"ok": True}

    # ------------------------------------------------------------------ coaching
    def _memory_text(self, g):
        parts = []
        for k in KINDS:
            items = g["memory"].get(k) or []
            if items:
                parts.append("%s:\n%s" % (KIND_NAMES[k], "\n".join("- " + x["text"] for x in items[-25:])))
        return "\n\n".join(parts) or "(nothing yet: this is the first entry)"

    def _peek(self, g, text, limit=7000):
        """For a linked Godot/Unity folder: the scripts that matter for this message, read-only."""
        folder = g.get("folder")
        exts = ENGINES.get(g["engine"], {}).get("read") or ()
        if not folder or not exts or not self.pmem or not os.path.isdir(folder):
            return ""
        files = []
        for dp, dns, fns in os.walk(folder):
            dns[:] = [d for d in dns if not d.startswith(".") and d not in ("Library", "Temp", "Logs", "obj", "bin", "Build", "Builds", "addons", "Packages")]
            for fn in fns:
                if fn.lower().endswith(exts):
                    p = os.path.join(dp, fn)
                    try:
                        if os.path.getsize(p) > 80000:
                            continue
                        with open(p, encoding="utf-8", errors="replace") as f:
                            files.append({"path": os.path.relpath(p, folder).replace("\\", "/"), "mtime": int(os.path.getmtime(p)), "text": f.read()})
                    except OSError:
                        continue
                if len(files) >= 300:
                    break
        if not files:
            return ""
        idx_dir = os.path.join(self._gdir(g["id"]), "index")      # the index lives with the dev log, never in their project
        ranked, idx = self.pmem.rank(idx_dir, files, text)
        body = {f["path"]: f["text"] for f in files}
        out, room = [], limit
        for path, score, why in ranked[:6]:
            if score <= 0 or room < 500:
                break
            t = body[path][:room - 100]
            out.append("<<<FILE %s>>>\n%s\n<<<END>>>" % (path, t))
            room -= len(t) + 40
        if not out:
            return ""
        return "\n\nFrom their project folder (read-only; only the files that seem to matter):\n" + "\n".join(out)

    def say(self, gid, text):
        g = self._load(gid)
        if not g:
            return {"error": "no such game"}
        text = (text or "").strip()[:4000]
        if not text:
            return {"error": "Say what you're working on or testing."}
        eng = g["engine"]
        info = ENGINES.get(eng, ENGINES["Other"])
        engine_name = g.get("engine_other") or eng if eng == "Other" else eng
        self._append(gid, {"at": _now(), "who": "you", "text": text})
        lib, refs = "", []
        if self.docs:
            try:
                found = []
                if info["lang"]:
                    found += self.docs.search(info["lang"], text, k=2)
                found += self.docs.search("gamedev", text, k=2, kinds=("qa",))
                seen, uniq = set(), []
                for r in found:
                    if (r["zim"], r["path"]) not in seen:
                        seen.add((r["zim"], r["path"]))
                        uniq.append(r)
                refs = uniq[:3]
                lib = self.docs.for_prompt(refs, limit=3600)
                refs = self.docs.public(refs)
            except Exception:      # noqa: BLE001 - docs are a help, never a reason to fail
                lib, refs = "", []
        recent = [e for e in self._log(gid, 12) if e.get("who") in ("you", "coach")][:-1][-6:]
        convo = "\n".join(("Developer: " + e["text"]) if e["who"] == "you" else ("Coach: " + (e.get("reply") or {}).get("going_on", "")) for e in recent)
        peek = self._peek(g, text)
        unreal = ("\nUNREAL: give advice only. Name Blueprint nodes and C++ classes you're sure of; if unsure of an exact UE5 API, say so and "
                  "describe what to look for. Never suggest Archie edit or open their Unreal project.") if eng == "Unreal" else ""
        prompt = ("The game: %s (%s)\nPitch: %s\n\nWhat Archie remembers about this game:\n%s\n\nRecent dev log:\n%s\n\nThe developer says now:\n%s%s%s\n\n"
                  "Answer for %s.%s\nReturn JSON with exactly these keys:\n"
                  "{\"going_on\": \"what's probably going on, 2-4 sentences\",\n"
                  " \"idea\": \"the design idea behind it (name the principle: coverage, chokepoints, readability, feedback, pacing, risk/reward, cost curves...), 2-4 sentences\",\n"
                  " \"steps\": [\"3 to 5 concrete next steps\"],\n"
                  " \"how\": \"how to do it in %s: specific nodes/components/functions, with a short code snippet in a ``` block if it helps\",\n"
                  " \"experiment\": {\"change\": \"one small thing to try\", \"measure\": \"what to watch or count, and what result would mean what\"},\n"
                  " \"concept\": \"a short teaching note: the general idea they can reuse in any game, 2-3 sentences\",\n"
                  " \"remember\": {\"notes\": [], \"decisions\": [], \"tried\": [], \"questions\": []}}\n"
                  "For \"remember\": ONLY facts the developer stated in THIS message (a design note about their game, a decision they made with "
                  "their reason, something they tried and what happened, a question they're still unsure about), each one short line in their "
                  "terms. Never your own suggestions. Leave lists empty if nothing fits.")
        prompt = prompt % (g["name"], engine_name, g.get("pitch") or "(none given)", self._memory_text(g), convo or "(none)", text, peek, lib,
                           engine_name, unreal, info["how"])
        raw = self.chat(COACH_RULES, prompt, 1500, True)
        try:
            v = json.loads(raw)
            if not isinstance(v, dict):
                raise ValueError
        except ValueError:
            v = {"going_on": (raw or "").strip()[:2000] or "Archie couldn't answer that one. Try again.", "steps": [], "remember": {}}
        reply = {k: v.get(k) for k in ("going_on", "idea", "steps", "how", "experiment", "concept")}
        if not isinstance(reply.get("steps"), list):
            reply["steps"] = [str(reply.get("steps"))] if reply.get("steps") else []
        if not isinstance(reply.get("experiment"), dict):
            reply["experiment"] = {"change": str(reply.get("experiment") or ""), "measure": ""}
        added = {}
        rem = v.get("remember") if isinstance(v.get("remember"), dict) else {}
        with self.lock:
            g = self._load(gid)
            for k in KINDS:
                have = {x["text"].lower() for x in g["memory"].get(k) or []}
                for item in (rem.get(k) or [])[:4]:
                    t = re.sub(r"\s+", " ", str(item)).strip()[:300]
                    if len(t) > 6 and t.lower() not in have:
                        g["memory"].setdefault(k, []).append({"text": t, "at": _now(), "by": "coach"})
                        added.setdefault(k, []).append(t)
            g["updated"] = _now()
            self._save(g)
        entry = {"at": _now(), "who": "coach", "reply": reply, "refs": refs, "remembered": added}
        self._append(gid, entry)
        self.alert("Dev coach · " + g["name"], (reply.get("going_on") or "")[:120])
        return entry
