"""
archie_talk.py - Archie's new voice, talk mode and Quiet.

  VOICES          the voices you can pick (original blends; accent voices come with the audition)
  for_speech()    turns answer text into what should be said (dates, numbers, your pronunciations)
  KokoroSpeaker   speaks through the voice helper (archie_voiced.py, its own Python in Voice\\kokoro\\env);
                  the same calls as the old Piper Speaker, plus captions and Quiet
  Quiet           muted by hand, or by itself: headphones out, library Wi-Fi, in class, quiet hours
  HandsFree       talk mode's ears: hears when you start and stop talking, and when you cut in
  TalkWindow      the talk mode screen
  CaptionPop      Archie's words in the corner while you work (and whenever it's muted)
  VoiceSettings   the Voice / Quiet settings window

Everything runs on this PC, offline.
"""

import datetime
import json
import math
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave

APP_DIR = os.path.dirname(os.path.abspath(__file__))
KOKORO_DIR = os.path.join(APP_DIR, "Voice", "kokoro")
ENV_PY = os.path.join(KOKORO_DIR, "env", "Scripts", "python.exe") if sys.platform == "win32" \
    else os.path.join(KOKORO_DIR, "env", "bin", "python")

# ---------------------------------------------------------------------------
# The voices. Original voices made by blending Kokoro's own; no one real is copied.
# ---------------------------------------------------------------------------

VOICES = [
    {"id": "archie", "name": "Archie · British man", "sub": "calm, dry, the one in the walls",
     "mix": [["bm_george", 0.6], ["bm_fable", 0.4]], "lang": "en-gb"},
    {"id": "british_woman", "name": "British woman", "sub": "clear, quick",
     "mix": [["bf_emma", 0.6], ["bf_isabella", 0.4]], "lang": "en-gb"},
    {"id": "sonia", "name": "Sonia · British woman", "sub": "Microsoft's natural voice · online (offline: British woman)",
     "edge": "en-GB-SoniaNeural", "mix": [["bf_emma", 0.6], ["bf_isabella", 0.4]], "lang": "en-gb"},
    {"id": "ryan", "name": "Ryan · British man", "sub": "Microsoft natural voice · online", "edge": "en-GB-RyanNeural", "mix": [["bm_george", 0.6], ["bm_fable", 0.4]], "lang": "en-gb"},
    {"id": "thomas", "name": "Thomas · British man", "sub": "Microsoft natural voice · online", "edge": "en-GB-ThomasNeural", "mix": [["bm_george", 0.6], ["bm_fable", 0.4]], "lang": "en-gb"},
    {"id": "libby", "name": "Libby · British woman", "sub": "Microsoft natural voice · online", "edge": "en-GB-LibbyNeural", "mix": [["bf_emma", 0.6], ["bf_isabella", 0.4]], "lang": "en-gb"},
    {"id": "connor", "name": "Connor · Irish man", "sub": "Microsoft natural voice · online", "edge": "en-IE-ConnorNeural", "mix": [["bm_george", 0.6], ["bm_fable", 0.4]], "lang": "en-gb"},
    {"id": "emily", "name": "Emily · Irish woman", "sub": "Microsoft natural voice · online", "edge": "en-IE-EmilyNeural", "mix": [["bf_emma", 0.6], ["bf_isabella", 0.4]], "lang": "en-gb"},
    {"id": "william", "name": "William · Australian man", "sub": "Microsoft natural voice · online", "edge": "en-AU-WilliamNeural", "mix": [["bm_george", 0.6], ["bm_fable", 0.4]], "lang": "en-gb"},
    {"id": "natasha", "name": "Natasha · Australian woman", "sub": "Microsoft natural voice · online", "edge": "en-AU-NatashaNeural", "mix": [["bf_emma", 0.6], ["bf_isabella", 0.4]], "lang": "en-gb"},
    {"id": "irish_woman", "name": "Irish woman", "sub": "warm, quick-witted sidekick", "accent": True},
    {"id": "irish_man", "name": "Irish man", "sub": "easygoing, friendly", "accent": True},
    {"id": "londoner", "name": "Older Londoner", "sub": "gravelly, seen-it-all", "accent": True},
    {"id": "scandi", "name": "Scandinavian", "sub": "Swedish-accented English", "accent": True},
    {"id": "british_deep", "name": "British man · deeper", "sub": "George + Daniel",
     "mix": [["bm_george", 0.5], ["bm_daniel", 0.5]], "lang": "en-gb"},
    {"id": "british_young", "name": "British man · younger", "sub": "Fable + Lewis",
     "mix": [["bm_fable", 0.55], ["bm_lewis", 0.45]], "lang": "en-gb"},
    {"id": "american_man", "name": "American man", "sub": "Michael", "mix": [["am_michael", 1.0]], "lang": "en-us"},
    {"id": "american_woman", "name": "American woman", "sub": "Heart", "mix": [["af_heart", 1.0]], "lang": "en-us"},
]
VOICE_BY_ID = {v["id"]: v for v in VOICES}
DEFAULT_VOICE_ID = "archie"
MODE_SPEED = {"Professor": 0.9, "Workshop": 1.05}   # on top of your speed; change in the settings

DEFAULT_PRON = [["A.R.C.H.I.E.", "Archie"], ["Obsidian", "Obsidian"]]

SPOKEN_STYLE = (
    "You are talking OUT LOUD with the user right now (talk mode): what you write is read aloud by your voice. "
    "Answer the way a sharp, friendly person talks: short natural sentences, contractions, no lists, no headings, "
    "no markdown, no emoji, no code (say you'll put code on screen if it's needed). Round numbers the way people say "
    "them. Two to five sentences unless he asks for more. Lead with the answer. When it fits, end with one short "
    "question about what he'd like next.")

NOTES_PROMPT = (
    "Turn this spoken answer into a short on-screen version: a title line, then 2 to 6 tight bullet points with the "
    "exact facts, numbers and terms. No intro, no closing.\n\nQuestion: {q}\n\nSpoken answer: {a}")


ACC_DIR = os.path.join(APP_DIR, "Voice", "accents")


def accent_info():
    """The accent voices to audition (Tools\\Get Accent Voices.bat makes them): {voice id: [candidates]}."""
    try:
        with open(os.path.join(ACC_DIR, "accents.json"), encoding="utf-8") as f:
            return json.load(f).get("candidates") or {}
    except (OSError, ValueError):
        return {}


def accent_ref(vid, cfg):
    sp = (cfg.get("accent_pick") or {}).get(vid)
    for c in accent_info().get(vid, []):
        if sp and c.get("sp") == sp:
            p = os.path.join(ACC_DIR, c["ref"])
            return p if os.path.exists(p) else None
    return None


def kokoro_ready(app_dir=APP_DIR):
    """None if the new voice is installed, else what's missing (in plain words)."""
    k = os.path.join(app_dir, "Voice", "kokoro")
    py = os.path.join(k, "env", "Scripts", "python.exe") if sys.platform == "win32" else os.path.join(k, "env", "bin", "python")
    if not os.path.exists(os.path.join(k, "kokoro-v1.0.onnx")) or not os.path.exists(os.path.join(k, "voices-v1.0.bin")):
        return "Archie's new voice isn't downloaded yet: run Tools\\Get Archie Voice.bat once while online."
    if not os.path.exists(py) and not os.environ.get("ARCHIE_VOICE_PY"):
        return "Archie's new voice isn't set up yet: run Tools\\Get Archie Voice.bat once while online."
    return None


# ---------------------------------------------------------------------------
# Saying things right
# ---------------------------------------------------------------------------

MONTHS = {"jan": "January", "feb": "February", "mar": "March", "apr": "April", "jun": "June", "jul": "July",
          "aug": "August", "sep": "September", "sept": "September", "oct": "October", "nov": "November", "dec": "December"}
ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
       9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth", 13: "thirteenth", 14: "fourteenth", 15: "fifteenth",
       16: "sixteenth", 17: "seventeenth", 18: "eighteenth", 19: "nineteenth", 20: "twentieth", 21: "twenty-first",
       22: "twenty-second", 23: "twenty-third", 24: "twenty-fourth", 25: "twenty-fifth", 26: "twenty-sixth",
       27: "twenty-seventh", 28: "twenty-eighth", 29: "twenty-ninth", 30: "thirtieth", 31: "thirty-first"}
ABBR = [(r"\be\.g\.", "for example"), (r"\bi\.e\.", "that is"), (r"\betc\.", "and so on"), (r"\bvs\b\.?", "versus"),
        (r"\bapprox\b\.?", "about"), (r"\bmin\.(?=\s|$)", "minutes"), (r"\bhrs?\b\.?", "hours"),
        (r"\bDr\.", "Doctor"), (r"\bProf\.", "Professor"), (r"\bMr\.", "Mister"), (r"\bMrs\.", "Missus"),
        (r"\bch\.\s?(\d)", r"chapter \1"), (r"\bpp?\.\s?(\d)", r"page \1"), (r"\bno\.\s?(\d)", r"number \1"),
        (r"(\d)\s?%", r"\1 percent"), (r"(\d)\s?°C\b", r"\1 degrees Celsius"), (r"(\d)\s?°F\b", r"\1 degrees Fahrenheit"),
        (r"(\d)\s?km\b", r"\1 kilometres"), (r"(\d)\s?kg\b", r"\1 kilograms"), (r"(\d)\s?mph\b", r"\1 miles an hour"),
        (r"(\d)\s?GB\b", r"\1 gigabytes"), (r"(\d)\s?MB\b", r"\1 megabytes"), (r"~\s?(\d)", r"about \1"),
        (r"(\d)\s?[–-]\s?(\d)", r"\1 to \2"), (r"\s&\s", " and "), (r"\s/\s", " or "), (r"\+/-", "plus or minus")]


def for_speech(text, pron=()):
    """Answer text -> what Archie should say out loud."""
    t = text
    for a, b in pron or ():
        if a and b and a != b:
            t = re.sub(r"(?<![\w.])" + re.escape(a) + r"(?![\w])", b, t, flags=re.I)
    # dates: "Nov 14" / "November 14th" -> "November fourteenth"; "14 Nov" too
    def md(m):
        mon = MONTHS.get(m.group(1).lower().rstrip("."), m.group(1))
        d = int(m.group(2))
        return f"{mon} {ORD.get(d, m.group(2))}"
    t = re.sub(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\b(?!:)", md, t)
    t = re.sub(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\b",
               lambda m: f"{MONTHS.get(m.group(2).lower(), m.group(2))} {ORD.get(int(m.group(1)), m.group(1))}", t)
    # times: 9:30am -> 9 30 a m; 3pm -> 3 p m; 14:00 -> 2 p m
    def tm(m):
        h, mi, ap = int(m.group(1)), m.group(2), (m.group(3) or "").lower().replace(".", "")
        if not ap and h >= 13:
            h, ap = h - 12, "pm"
        mins = "" if not mi or mi == "00" else (" oh " + mi[1] if mi[0] == "0" else " " + mi)
        return f"{h}{mins}" + (" " + " ".join(ap) if ap else "")
    t = re.sub(r"\b(\d{1,2}):(\d{2})\s*([ap]\.?m\.?)?", tm, t, flags=re.I)
    t = re.sub(r"\b(\d{1,2})\s*([ap])\.?m\.?\b", lambda m: f"{m.group(1)} {m.group(2).lower()} m", t, flags=re.I)
    for a, b in ABBR:
        t = re.sub(a, b, t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


# ---------------------------------------------------------------------------
# Speaking
# ---------------------------------------------------------------------------

_ABBR = set(("mr mrs ms mx dr st prof rev revd fr capt col gen lt sgt cpl maj adm hon jr sr messrs mme mlle vs etc eg ie cf al "
              "no nos vol vols ch chap p pp fig figs approx esp dept est inc ltd co corp ave rd mt ft jan feb mar apr jun "
              "jul aug sep sept oct nov dec mon tue tues wed thu thur thurs fri sat sun").split())
_CAND = re.compile(r"[.!?…]+[\"')\]”’»]*(?=\s)|\n{2,}|\n(?=\s*(?:[-*•]|\d+[.)])\s)")


def next_end(buf, final=False):
    """Where the first whole sentence in buf ends, or None if we can't tell yet.
    A period after Mr / Mrs / Dr / an initial / inside a number doesn't end a sentence,
    and a sentence only ends when the next word starts like a new one."""
    for m in _CAND.finditer(buf):
        end, tok = m.end(), m.group(0)
        if tok.startswith("\n"):
            return end
        nm = re.match(r"\s*([\"'“‘«(\[]*)(\S?)", buf[end:])
        if not nm.group(2) and not nm.group(1):
            return end if final else None          # wait for the next word
        if not (re.match(r"[A-Z0-9À-Þ]", nm.group(2)) or nm.group(1)):
            continue
        if re.fullmatch(r"\.+[\"')\]”’»]*", tok) and ".." not in tok:
            w = re.search(r"([A-Za-z.]+)$", buf[:m.start()])
            word = (w.group(1) if w else "").lower()
            bare = word.replace(".", "")
            if bare in _ABBR or re.fullmatch(r"[a-z]", bare or "-") or re.fullmatch(r"([a-z]\.)+[a-z]?", word):
                continue
        return end
    return None


def _speakable(text):
    try:
        from archie_speak import speakable
        return speakable(text)
    except Exception:
        return text


class KokoroSpeaker:
    """Works like the old Speaker (say / feed / flush / stop / speaking), plus captions and Quiet.

    get_cfg()       Archie's settings (voice_id, voice_speed, voice_room, mode, mode_speed, pronunciations)
    quiet()         True when Archie should stay silent and only show captions
    on_caption(text, seconds, audible)   called (from a background thread) as each sentence starts
    on_error(msg)   a problem, in plain words
    """

    def __init__(self, get_cfg, quiet=lambda: False, on_caption=None, on_error=print, on_idle=None, app_dir=APP_DIR):
        self.get_cfg = get_cfg
        self.quiet = quiet
        self.on_caption = on_caption or (lambda *a: None)
        self.on_error = on_error
        self.on_idle = on_idle or (lambda: None)
        self.app_dir = app_dir
        self.voice_name = get_cfg().get("voice_id") or DEFAULT_VOICE_ID
        self.speed = float(get_cfg().get("voice_speed") or 0.95)
        self.speaking = threading.Event()
        self.buf = ""
        self.in_code = False
        self._gen = 1
        self._n = 0
        self._texts = {}
        self._pending = 0
        self._proc = None
        self._lock = threading.Lock()
        self._silent_q = queue.Queue()
        self._silent_t = None
        self.force_audible = False      # "play it to me" while muted
        self.voice_override = None      # a preview in another voice
        self.last_said = []             # this answer's sentences, for "say it again" / "play it to me"
        self.device = None              # the sound output the helper sees (for "headphones only")

    # --- the calls Archie already makes ----------------------------------------------

    def ready(self):
        return kokoro_ready(self.app_dir)

    def say(self, text, audible=False, voice_id=None):
        self.stop()
        self.force_audible = audible
        self.voice_override = voice_id
        self.feed(text)
        self.flush()

    def start_turn(self):
        """Talk mode: the first phrase of the next answer is spoken as soon as it's there (not the whole sentence)."""
        self.eager, self._turn_spoke = True, False

    def feed(self, piece):
        self.buf += piece
        while True:
            e = next_end(self.buf)
            if not e:
                break
            sentence, self.buf = self.buf[:e], self.buf[e:]
            self._turn_spoke = True
            self._queue(sentence)
        if getattr(self, "eager", False) and not getattr(self, "_turn_spoke", True) and len(self.buf) > 22:
            m = re.search(r"[,;:\u2014\u2013]\s", self.buf[16:])
            if m and "```" not in self.buf:
                cut = 16 + m.end()
                self._turn_spoke = True
                self._queue(self.buf[:cut])
                self.buf = self.buf[cut:]
        if len(self.buf) > 400:
            cut = self.buf.rfind(" ", 0, 300)
            cut = cut if cut > 0 else 300
            self._queue(self.buf[:cut])
            self.buf = self.buf[cut:]

    def flush(self):
        while self.buf.strip():
            e = next_end(self.buf, final=True)
            if not e or e >= len(self.buf.rstrip()):
                break
            sentence, self.buf = self.buf[:e], self.buf[e:]
            self._queue(sentence)
        if self.buf.strip():
            self._queue(self.buf)
        self.buf = ""
        self.in_code = False

    def stop(self):
        with self._lock:
            self._gen += 1
            self._pending = 0
        self.buf = ""
        self.in_code = False
        self.last_said = []
        self.force_audible = False
        self.voice_override = None
        self.eager = False
        self.speaking.clear()
        try:
            while True:
                self._silent_q.get_nowait()
        except queue.Empty:
            pass
        self._send({"op": "stop", "gen": self._gen})

    def mute_now(self):
        """Muted mid-answer: the sound stops now, and the rest of the answer (from the sentence that was playing)
        carries on as captions at talking speed, instead of the whole answer stopping."""
        with self._lock:
            left = [self._texts[k] for k in sorted(self._texts, key=lambda k: int(k[1:]) if k[1:].isdigit() else 0)]
            if not left:
                return                  # nothing was playing: captions already running (or nothing to say) carry on
            self._texts.clear()
            self._gen += 1
            self._pending = 0
            gen = self._gen
        self.force_audible = False
        self._send({"op": "stop", "gen": gen})
        self.speaking.set()
        for text in left:
            self._silent_q.put((gen, text))
        if self._silent_t is None or not self._silent_t.is_alive():
            self._silent_t = threading.Thread(target=self._silent_run, daemon=True)
            self._silent_t.start()

    def repeat(self, audible=False):
        said = list(self.last_said)
        if said:
            self.say(" ".join(said), audible=audible)
        return bool(said)

    def warm(self):
        """Start the voice helper early, so the first sentence isn't slow."""
        threading.Thread(target=self._ensure, daemon=True).start()

    def probe_device(self):
        self._send({"op": "devices"})

    def close(self):
        self._send({"op": "quit"})

    def to_file(self, text, path, voice_id=None):
        self._send({"op": "file", "text": for_speech(_speakable(text), self._pron()), "path": path,
                    "voice": self._voice(voice_id), "speed": self._speed(), "room": bool(self.get_cfg().get("voice_room", True))})

    # --- inside ------------------------------------------------------------------------

    def _pron(self):
        p = self.get_cfg().get("pronunciations")
        return p if isinstance(p, list) else DEFAULT_PRON

    def _voice(self, vid=None):
        v = VOICE_BY_ID.get(vid or self.voice_override or self.get_cfg().get("voice_id") or DEFAULT_VOICE_ID) or VOICE_BY_ID[DEFAULT_VOICE_ID]
        if v.get("accent"):
            ref = accent_ref(v["id"], self.get_cfg()) if self.get_cfg().get("accent_live") else None
            if ref:   # live accent voice: only if turned on (it shares the graphics card with Archie's model and slows him)
                back = VOICE_BY_ID["british_woman" if "woman" in v["id"] else DEFAULT_VOICE_ID]
                return {"clone": ref, "mix": back["mix"], "lang": "en-gb"}
        if v.get("accent") or not v.get("mix"):
            v = VOICE_BY_ID[DEFAULT_VOICE_ID]
        out = {"mix": v["mix"], "lang": v.get("lang", "en-gb")}
        if v.get("edge"):     # online voice: when there's no internet, Archie speaks with the American woman (or your pick)
            out["edge"] = v["edge"]
            off = VOICE_BY_ID.get(self.get_cfg().get("offline_voice") or "american_woman") or VOICE_BY_ID["american_woman"]
            if off.get("mix"):
                out["mix"], out["lang"] = off["mix"], off.get("lang", "en-us")
        return out

    def _speed(self):
        c = self.get_cfg()
        base = float(c.get("voice_speed") or self.speed or 0.95)
        per = (c.get("mode_speed") or {}).get(c.get("mode") or "", MODE_SPEED.get(c.get("mode") or "", 1.0))
        return max(0.6, min(1.6, base * float(per or 1.0)))

    def _queue(self, sentence):
        fences = sentence.count("```")
        if self.in_code or fences:
            if fences % 2 == 1:
                was = self.in_code
                self.in_code = not self.in_code
                sentence = (sentence.split("```")[0] + " (I've put the code on screen.)") if not was else sentence.rsplit("```", 1)[-1]
            elif self.in_code:
                return
        shown = " ".join(_speakable(sentence).split())                 # what the captions show (A.R.C.H.I.E., 6pm)
        text = for_speech(_speakable(sentence), self._pron())          # what the voice says (Sue-Knee, six p m)
        if not re.search(r"[A-Za-z0-9]", text):
            return
        self.last_said.append(text)
        self.speaking.set()
        if self.quiet() and not self.force_audible:
            self._silent_q.put((self._gen, shown or text))
            if self._silent_t is None or not self._silent_t.is_alive():
                self._silent_t = threading.Thread(target=self._silent_run, daemon=True)
                self._silent_t.start()
            return
        with self._lock:
            self._n += 1
            sid = f"s{self._n}"
            self._texts[sid] = shown or text
            self._pending += 1
            gen = self._gen
        if not self._send({"op": "say", "gen": gen, "id": sid, "text": text, "voice": self._voice(),
                           "speed": self._speed(), "room": bool(self.get_cfg().get("voice_room", True)),
                           "vol": float(self.get_cfg().get("voice_volume") or 1.0), "talk": bool(getattr(self, "eager", False))}):
            with self._lock:
                self._pending = max(0, self._pending - 1)
            self._silent_q.put((self._gen, text))       # the voice failed: at least show the words
            if self._silent_t is None or not self._silent_t.is_alive():
                self._silent_t = threading.Thread(target=self._silent_run, daemon=True)
                self._silent_t.start()

    def _silent_run(self):
        """Muted: show each sentence for about as long as it would take to say."""
        while True:
            try:
                gen, text = self._silent_q.get(timeout=2.5)
            except queue.Empty:
                break
            if gen != self._gen:
                continue
            secs = max(1.2, len(text) / 15.0 / max(0.6, self._speed()))
            try:
                self.on_caption(text, secs, False)
            except Exception:
                pass
            end = time.time() + secs
            while time.time() < end and gen == self._gen:
                time.sleep(0.05)
        if self._silent_q.empty() and self._pending == 0:
            self.speaking.clear()
            self.on_idle()

    def _ensure(self):
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return True
            py = os.environ.get("ARCHIE_VOICE_PY") or ENV_PY
            script = os.path.join(self.app_dir, "archie_voiced.py")
            if not os.path.exists(py) or not os.path.exists(script):
                return False
            env = dict(os.environ, ARCHIE_KOKORO_DIR=os.path.join(self.app_dir, "Voice", "kokoro"), PYTHONIOENCODING="utf-8")
            for k in ("PYTHONPATH", "PYTHONHOME"):
                env.pop(k, None)
            try:
                self._proc = subprocess.Popen([py, "-s", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=subprocess.DEVNULL, env=env, cwd=self.app_dir, text=True,
                                              encoding="utf-8", bufsize=1,   # below normal: making speech never freezes Archie's windows
                                              creationflags=0x08000000 if sys.platform == "win32" else 0)
            except OSError as e:
                self.on_error(f"The voice couldn't start: {e}")
                self._proc = None
                return False
            threading.Thread(target=self._read, args=(self._proc,), daemon=True).start()
            return True

    def _send(self, cmd):
        if cmd.get("op") in ("stop", "quit") and (self._proc is None or self._proc.poll() is not None):
            return True
        if not self._ensure():
            return False
        try:
            self._proc.stdin.write(json.dumps(cmd) + "\n")
            self._proc.stdin.flush()
            return True
        except (OSError, ValueError):
            self._proc = None
            return False

    def _read(self, proc):
        for line in proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            e = ev.get("ev")
            if e == "start":
                text = self._texts.get(ev.get("id"), "")
                try:
                    self.on_caption(text, float(ev.get("dur") or 1.0), True)
                except Exception:
                    pass
            elif e == "end":
                self._texts.pop(ev.get("id"), None)
                with self._lock:
                    self._pending = max(0, self._pending - 1)
                    idle = self._pending == 0
                if idle and self._silent_q.empty():
                    self.speaking.clear()
                    self.on_idle()
            elif e == "idle":
                with self._lock:
                    self._pending = 0
                if self._silent_q.empty():
                    self.speaking.clear()
                    self.on_idle()
            elif e == "devices":
                self.device = ev.get("out")
            elif e == "error":
                self.on_error(ev.get("msg") or "The voice had a problem.")
                if ev.get("fatal"):
                    break


# ---------------------------------------------------------------------------
# Quiet
# ---------------------------------------------------------------------------

HEADPHONES = re.compile(r"head ?(phone|set)|ear ?(phone|bud)|\bbuds\b|airpods|hands-?free|wh-1000|\bqc ?\d|jabra|beats|"
                        r"arctis|hyperx|kraken|steelseries|corsair (hs|void)|logitech g\d{3}|astro a\d", re.I)


def wifi_name():
    """The Wi-Fi network this PC is on, or ''."""
    if sys.platform != "win32":
        return ""
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=6,
                             creationflags=0x08000000).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        m = re.match(r"\s*SSID\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1)
    return ""


def output_device():
    """The default sound output's name, asked fresh from Windows (so plugging in headphones is noticed)."""
    if sys.platform != "win32":
        return ""
    ps = ("Add-Type -TypeDefinition @'\nusing System;using System.Runtime.InteropServices;\n"
          "[ComImport,Guid(\"A95664D2-9614-4F35-A746-DE8DB63617E6\"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n"
          "interface IMMDeviceEnumerator{int f();int GetDefaultAudioEndpoint(int a,int b,out IMMDevice d);}\n"
          "[ComImport,Guid(\"D666063F-1587-4E43-81F1-B948E807363F\"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n"
          "interface IMMDevice{int f();int OpenPropertyStore(int a,out IPropertyStore p);}\n"
          "[ComImport,Guid(\"886d8eeb-8cf2-4446-8d02-cdba1dbdcf99\"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]\n"
          "interface IPropertyStore{int f();int g();int GetValue(ref PK k,out PV v);}\n"
          "[StructLayout(LayoutKind.Sequential)] public struct PK{public Guid g;public int p;}\n"
          "[StructLayout(LayoutKind.Sequential)] public struct PV{public short vt;short a,b,c;public IntPtr p;IntPtr q;}\n"
          "[ComImport,Guid(\"BCDE0395-E52F-467C-8E3D-C4579291692E\")] class E{}\n"
          "public static class AD{public static string Name(){var e=(IMMDeviceEnumerator)new E();IMMDevice d;"
          "e.GetDefaultAudioEndpoint(0,1,out d);IPropertyStore s;d.OpenPropertyStore(0,out s);"
          "var k=new PK{g=new Guid(\"a45c254e-df1c-4efd-8020-67d146a850e0\"),p=14};PV v;s.GetValue(ref k,out v);"
          "return Marshal.PtrToStringUni(v.p);}}\n'@\n[AD]::Name()")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                           text=True, timeout=12, creationflags=0x08000000)
        return (r.stdout or "").strip().splitlines()[-1].strip() if r.stdout.strip() else ""
    except Exception:
        return ""


class Quiet:
    """Should Archie make sound right now? cfg keys:
       quiet (bool), quiet_headphones_only (bool), quiet_headphone_names [names you marked as headphones],
       quiet_wifi [network names], quiet_classes (bool), quiet_hours [from, to] like ["23:00", "07:00"] or None,
       notify_quiet "silent" | "some" (sound only for professors' mail and timers)."""

    def __init__(self, get_cfg, calendar=None, lecture_minutes=75):
        self.get_cfg = get_cfg
        self.calendar = calendar
        self.lecture_minutes = lecture_minutes
        self.wifi = ""
        self.device = ""
        self._last = 0
        self._busy = False

    def refresh(self, force=False, every=20):
        """Look at the Wi-Fi and the sound output again (in the background; it takes a moment)."""
        if self._busy or (not force and time.time() - self._last < every):
            return
        c = self.get_cfg()
        need_wifi = bool(c.get("quiet_wifi"))
        need_dev = bool(c.get("quiet_headphones_only")) or force
        if not (need_wifi or need_dev):
            return
        self._busy = True

        def work():
            try:
                if need_wifi or force:
                    self.wifi = wifi_name()
                if need_dev:
                    self.device = output_device() or self.device
            finally:
                self._last = time.time()
                self._busy = False
        threading.Thread(target=work, daemon=True).start()

    def headphones(self):
        d = self.device or ""
        marked = [x.lower() for x in self.get_cfg().get("quiet_headphone_names") or []]
        return bool(d) and (d.lower() in marked or (bool(HEADPHONES.search(d)) and not re.search(r"speaker", d, re.I)))

    def state(self, now=None):
        """(quiet?, why) - why is a few words for the status line."""
        c = self.get_cfg()
        now = now or datetime.datetime.now()
        if c.get("quiet"):
            return True, "muted"
        hrs = c.get("quiet_hours")
        if isinstance(hrs, (list, tuple)) and len(hrs) == 2 and all(hrs):
            try:
                a = datetime.datetime.strptime(hrs[0], "%H:%M").time()
                b = datetime.datetime.strptime(hrs[1], "%H:%M").time()
                t = now.time()
                if (a <= t < b) if a < b else (t >= a or t < b):
                    return True, "quiet hours"
            except ValueError:
                pass
        if c.get("quiet_classes", True) and self.calendar is not None:
            try:
                for e in self.calendar.on(now.date()):
                    if (e.get("kind") or "").lower() not in ("class", "lecture", "lab") or not e.get("time"):
                        continue
                    h, m = [int(x) for x in e["time"].split(":")[:2]]
                    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if start <= now < start + datetime.timedelta(minutes=self.lecture_minutes):
                        return True, "in class"
            except Exception:
                pass
        if self.wifi and self.wifi in (c.get("quiet_wifi") or []):
            return True, f"on {self.wifi}"
        if c.get("quiet_headphones_only") and not self.headphones():
            return True, "no headphones"
        return False, ""

    def is_quiet(self):
        self.refresh()
        return self.state()[0]

    def sound_ok(self, kind="other"):
        """May this notification make a sound? kind: 'prof_mail', 'timer', 'mail', 'other'."""
        q, _ = self.state()
        if not q:
            return True
        return self.get_cfg().get("notify_quiet", "silent") == "some" and kind in ("prof_mail", "timer")


# ---------------------------------------------------------------------------
# Hands-free: hearing when you talk
# ---------------------------------------------------------------------------

class HandsFree:
    """Listens to the mic. Calls on_utterance(wav_path) when you finish a sentence (a short pause),
    on_bargein() when you start talking over Archie, on_level(0..1) for the orb.
    is_speaking() tells it Archie is talking (so its own voice from the speakers isn't taken as you)."""

    RATE = 16000
    FRAME = 1600                  # 100 ms pieces, like the recap recorder (30 ms ones dropped audio on Windows)

    PAUSE = 5                     # 0.5 s of quiet: Archie starts thinking (quietly) in case you're done
    END = 8                       # 0.8 s of quiet: you're done

    def __init__(self, on_utterance, on_bargein, on_level=None, is_speaking=lambda: False, folder=None,
                 on_pause=None, on_resume=None, sens=lambda: 1.0):
        self.on_utterance = on_utterance
        self.sens = sens
        self.on_pause, self.on_resume = on_pause, on_resume
        self.seq, self._pause_path = 0, None
        self.on_bargein = on_bargein
        self.on_level = on_level or (lambda v: None)
        self.is_speaking = is_speaking
        self.folder = folder or tempfile.gettempdir()
        self.stream = None
        self.paused = False
        self.mic_off = False      # muted with the mic key: nothing you say is heard until it's pressed again
        self.floor = 0.0015       # room noise, learned as it goes (starts low so a quiet room hears a distant voice)
        self.echo = 0.0           # how loud Archie's own voice comes back through the mic
        self._frames = []
        self._voiced = 0
        self._silent = 0
        self._talking = False
        self._barged = False

    @property
    def on(self):
        return self.stream is not None

    def start(self):
        import sounddevice as sd
        self.stream = sd.InputStream(samplerate=self.RATE, channels=1, dtype="int16", blocksize=self.FRAME,
                                     latency="high", callback=self._cb)
        self.stream.start()

    def stop(self):
        s, self.stream = self.stream, None
        if s is not None:
            try:
                s.stop()
                s.close()
            except Exception:
                pass
        self._reset()

    def _reset(self):
        self._frames, self._voiced, self._silent, self._talking, self._barged = [], 0, 0, False, False
        self._pause_path = None

    def _wav(self, frames):
        """What you said, turned up so a quiet or distant voice reaches the speech model at a good level."""
        import numpy as np
        path = os.path.join(self.folder, f"talk_{int(time.time() * 1000)}.wav")
        lvl = [float(np.sqrt(np.mean((f[:, 0].astype("float32") / 32768.0) ** 2))) for f in frames]
        soft = max(self.floor * 1.5, 0.0018)               # the first sound above the room: keep from just before it,
        first = next((i for i, v in enumerate(lvl) if v > soft), 0)   # drop the silence (Whisper is quicker on less)
        frames = frames[max(0, first - 2):]
        a = np.concatenate([f[:, 0] for f in frames]).astype("float32") if frames else np.zeros(1, "float32")
        peak = float(np.max(np.abs(a))) or 1.0
        gain = min(12.0, 0.8 * 32767.0 / peak)                  # up to 12x louder, never clipped
        if gain > 1.1:
            a = a * gain
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.RATE)
            w.writeframes(np.clip(a, -32767, 32767).astype("<i2").tobytes())
        return path

    def _cb(self, data, frames, t, status):
        import numpy as np
        if self.mic_off:
            self.on_level(0.0)
            self._reset()
            return
        x = data[:, 0].astype("float32") / 32768.0
        rms = float(np.sqrt(np.mean(x * x)) + 1e-9)
        self.on_level(min(1.0, rms * 18))
        if self.paused:
            self._reset()
            return
        speaking = self.is_speaking()
        try:
            k = max(0.4, min(3.0, float(self.sens())))          # mic sensitivity slider: higher hears quieter voices
        except Exception:
            k = 1.0
        thr = max(self.floor * 2.4, 0.0035 / k)                 # a voice across the room still counts (it was 0.012)
        if speaking:
            thr = max(thr, self.echo * 2.6, 0.03)               # cutting in has to be clearly you
        loud = rms > thr
        if speaking and not self._talking and not loud:
            self.echo = 0.95 * self.echo + 0.05 * rms          # learn the echo while Archie talks (not you)
        elif not speaking and not self._talking and not loud:
            self.floor = 0.95 * self.floor + 0.05 * min(rms, 0.05)
        if not self._talking:
            self._frames = (self._frames + [data.copy()])[-10:]     # keep a full second before you start (soft first words)
            self._voiced = self._voiced + 1 if loud else 0
            if self._voiced >= (3 if speaking else 2):              # 300 ms over Archie, 200 ms otherwise
                self._talking, self._silent = True, 0
                if speaking:
                    self._barged = True
                    try:
                        self.on_bargein()
                    except Exception:
                        pass
            return
        self._frames.append(data.copy())
        voiced_now = rms > max(self.floor * 1.8, 0.0028 / k)
        if voiced_now and self._pause_path and self.on_resume:          # you kept going: drop the early start
            try:
                self.on_resume(self.seq, self._pause_path)
            except Exception:
                pass
            self._pause_path, self.seq = None, self.seq + 1
        self._silent = 0 if voiced_now else self._silent + 1
        secs = len(self._frames) * self.FRAME / self.RATE
        if self.on_pause and self._silent == self.PAUSE and not self._pause_path and secs >= 0.6:
            try:
                self._pause_path = self._wav(self._frames)
                threading.Thread(target=self.on_pause, args=(self.seq, self._pause_path), daemon=True).start()
            except Exception:
                self._pause_path = None
        if self.on_pause and (self._silent >= self.END or secs > 45):     # quick talk: done after 0.8 s
            path, seq = self._pause_path, self.seq
            frames, self._frames = self._frames, []
            self._talking, self._voiced, self._silent, self._pause_path = False, 0, 0, None
            self.seq += 1
            if secs < 0.6:
                return
            try:
                path = path or self._wav(frames)
                threading.Thread(target=self.on_utterance, args=(path, seq), daemon=True).start()
            except Exception:
                pass
            return
        if self._silent >= 12 or secs > 45:                           # 1.2 s of quiet ends what you said
            frames, self._frames = self._frames, []
            self._talking, self._voiced, self._silent = False, 0, 0
            if secs < 0.6:
                return
            path = os.path.join(self.folder, f"talk_{int(time.time() * 1000)}.wav")
            try:
                with wave.open(path, "wb") as w:
                    w.setnchannels(1)
                    w.setsampwidth(2)
                    w.setframerate(self.RATE)
                    for f in frames:
                        w.writeframes(f.tobytes())
                threading.Thread(target=self.on_utterance, args=(path,), daemon=True).start()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Windows (Tk). These only touch Tk from the main thread: Archie calls them from its poll loop.
# ---------------------------------------------------------------------------

def _theme():
    try:
        import archie_theme as th
        return th
    except Exception:
        class T:
            BG, SURFACE, RAISED, BORDER, TEXT, BODY, MUTED, DIM, ACCENT, ON_ACCENT = (
                "#0a0a0a", "#141414", "#1a1a1a", "#262626", "#e8e8e3", "#d9d9d4", "#8a8a85", "#a3a3a3", "#c6f432", "#0a0a0a")
        return T


def _fonts(app):
    sans = getattr(app, "font_sans", None) or ("Segoe UI" if sys.platform == "win32" else "Helvetica")
    serif = "Newsreader" if sys.platform == "win32" else "Times"
    mono = getattr(app, "font_mono", None) or "Consolas"
    return sans, serif, mono


class CaptionPop:
    """Archie's words in a small box in the corner by the owl."""

    def __init__(self, app):
        import tkinter as tk
        th = _theme()
        self.app = app
        self.w = tk.Toplevel(app.root)
        self.w.overrideredirect(True)
        self.w.attributes("-topmost", True)
        self.w.configure(bg=th.ACCENT)
        sans, serif, mono = _fonts(app)
        f = tk.Frame(self.w, bg="#0c0d0b", padx=app.px(14), pady=app.px(10))
        f.pack(padx=1, pady=1, fill="both", expand=True)
        top = tk.Frame(f, bg="#0c0d0b")
        top.pack(fill="x")
        tk.Label(top, text="ARCHIE", bg="#0c0d0b", fg=th.ACCENT, font=(mono, 8, "bold")).pack(side="left")
        self.tag = tk.Label(top, text="", bg="#0c0d0b", fg=th.MUTED, font=(mono, 8))
        self.tag.pack(side="left", padx=(8, 0))
        self.play = tk.Label(top, text="▶ play it to me", bg="#0c0d0b", fg=th.MUTED, font=(mono, 8), cursor="hand2")
        self.play.bind("<Button-1>", lambda e: app.talk_play_aloud())
        self.x = tk.Label(top, text="×", bg="#0c0d0b", fg=th.MUTED, font=(sans, 11), cursor="hand2")
        self.x.pack(side="right")
        self.x.bind("<Button-1>", lambda e: self.hide())
        self.text = tk.Label(f, text="", bg="#0c0d0b", fg="#f2f2ec", font=(serif, 13), justify="left",
                             wraplength=app.px(380), anchor="w")
        self.text.pack(fill="x", pady=(app.px(6), 0))
        self._words, self._i, self._job, self._hide = [], 0, None, None
        self.w.withdraw()

    def show(self, text, secs, audible):
        th = _theme()
        self.tag.configure(text="" if audible else "muted · captions")
        if audible:
            self.play.pack_forget()
        else:
            self.play.pack(side="right", padx=(0, 10))
        self._words = text.split()
        self._i = 0
        self._step = max(0.06, secs / max(1, len(self._words)))
        if self._job:
            self.w.after_cancel(self._job)
        if self._hide:
            self.w.after_cancel(self._hide)
            self._hide = None
        self.text.configure(text=text)          # size the box for the whole sentence, then reveal it
        self._place()
        self.w.deiconify()
        self.w.lift()
        self._tick()

    def _tick(self):
        self._i += 1
        self.text.configure(text=" ".join(self._words[:self._i]))
        if self._i < len(self._words):
            self._job = self.w.after(int(self._step * 1000), self._tick)
        else:
            self._job = None

    def done(self):
        if self._hide:
            self.w.after_cancel(self._hide)
        self._hide = self.w.after(5000, self.hide)

    def hide(self):
        if self._job:
            self.w.after_cancel(self._job)
            self._job = None
        self.w.withdraw()

    def _place(self):
        self.w.update_idletasks()
        app = self.app
        sw, sh = self.w.winfo_screenwidth(), self.w.winfo_screenheight()
        try:
            ox, oy = app.root.winfo_rootx(), app.root.winfo_rooty()
        except Exception:
            ox, oy = sw - 80, sh - 160
        w, h = app.px(420), self.w.winfo_reqheight()
        x = max(8, min(sw - w - 8, ox + app.px(60) - w))
        y = oy - h - app.px(10) if oy - h - app.px(10) > 8 else oy + app.px(70)
        self.w.geometry(f"{w}x{h}+{x}+{max(8, y)}")


class TalkWindow:
    """Talk mode: just talk. Archie listens, answers out loud, and stops the moment you cut in."""

    def __init__(self, app):
        import tkinter as tk
        th = _theme()
        self.app, self.tk = app, tk
        px = app.px
        sans, serif, mono = _fonts(app)
        self.serif, self.mono, self.sans = serif, mono, sans
        self.w = tk.Toplevel(app.root)
        self.w.title("Archie · talk mode")
        self.w.configure(bg=th.BG)
        try:
            self.w.iconphoto(True, app._icon)
        except Exception:
            pass
        W, H = px(1120), px(700)
        sw, sh = self.w.winfo_screenwidth(), self.w.winfo_screenheight()
        self.w.geometry(f"{W}x{H}+{(sw - W) // 2}+{max(20, (sh - H) // 2 - px(30))}")
        self.w.minsize(px(760), px(520))
        self.w.protocol("WM_DELETE_WINDOW", app.talk_end)
        self.w.bind("<Escape>", lambda e: app.talk_end())
        self.w.bind("<space>", lambda e: (app.talk_cut_in(), "break")[1])

        side = tk.Frame(self.w, bg="#111210", width=px(320), highlightthickness=0)
        side.pack(side="right", fill="y")
        side.pack_propagate(False)
        main = tk.Frame(self.w, bg=th.BG)
        main.pack(side="left", fill="both", expand=True)

        hd = tk.Frame(main, bg=th.BG)
        hd.pack(fill="x", padx=px(28), pady=(px(22), 0))
        tk.Label(hd, text="TALK MODE", bg=th.BG, fg=th.ACCENT, font=(mono, 8, "bold")).pack(side="left")
        self.head = tk.Label(hd, text="", bg=th.BG, fg=th.MUTED, font=(mono, 9))
        self.head.pack(side="left", padx=(px(12), 0))
        tk.Label(hd, text="Esc ends · space cuts in", bg=th.BG, fg=th.MUTED, font=(mono, 9)).pack(side="right")

        youf = tk.Frame(main, bg=th.BG)
        youf.pack(fill="x", padx=px(60), pady=(px(26), 0))
        tk.Label(youf, text="YOU", bg=th.BG, fg=th.MUTED, font=(mono, 8)).pack(anchor="w")
        self.you = tk.Label(youf, text="Go ahead, I'm listening.", bg=th.BG, fg="#aeb5a4", font=(serif, 16),
                            justify="left", anchor="w", wraplength=px(700))
        self.you.pack(anchor="w", fill="x")

        self.cv = tk.Canvas(main, width=px(200), height=px(200), bg=th.BG, highlightthickness=0)
        self.cv.pack(pady=(px(14), px(6)))
        pills = tk.Frame(main, bg=th.BG)
        pills.pack()
        self.pills = {}
        for k in ("listening", "thinking", "speaking"):
            l = tk.Label(pills, text=k, bg=th.BG, fg="#5d6455", font=(mono, 9), padx=px(12), pady=px(3),
                         highlightthickness=1, highlightbackground=th.BORDER)
            l.pack(side="left", padx=px(4))
            self.pills[k] = l

        self.cap = tk.Text(main, height=4, bg=th.BG, fg="#f2f2ec", font=(serif, 20), wrap="word", bd=0,
                           highlightthickness=0, padx=px(10), cursor="arrow")
        self.cap.tag_configure("c", justify="center")
        self.cap.tag_configure("old", foreground="#7c8474")
        self.cap.tag_configure("now", foreground="#f2f2ec")
        self.cap.tag_configure("next", foreground="#3f453a")
        self.cap.pack(fill="both", expand=True, padx=px(50), pady=(px(14), 0))
        self.cap.configure(state="disabled")

        self.hint = tk.Label(main, text="Just start talking to cut in: I stop mid-sentence and listen.",
                             bg=th.BG, fg=th.MUTED, font=(mono, 9))
        self.hint.pack(pady=(px(4), px(8)))
        bf = tk.Frame(main, bg=th.BG)
        bf.pack(pady=(0, px(20)))

        def btn(t, cmd, go=False):
            b = tk.Label(bf, text=t, bg=th.ACCENT if go else th.BG, fg=th.ON_ACCENT if go else "#c9d0bf",
                         font=(mono, 9, "bold" if go else "normal"), padx=px(16), pady=px(9), cursor="hand2",
                         highlightthickness=0 if go else 1, highlightbackground="#343a2e")
            b.pack(side="left", padx=px(5))
            b.bind("<Button-1>", lambda e: cmd())
            return b
        self.pause_b = btn("pause listening", app.talk_toggle_listen)
        btn("say it again", app.talk_again)
        btn("slower", app.talk_slower)
        self.mute_b = btn("mute", app.toggle_quiet)
        btn("end talk", app.talk_end, go=True)

        tk.Label(side, text="ON SCREEN", bg="#111210", fg=th.MUTED, font=(mono, 8)).pack(anchor="w", padx=px(22), pady=(px(26), px(8)))
        self.ntitle = tk.Label(side, text="", bg="#111210", fg="#f2f2ec", font=(serif, 15), justify="left",
                               anchor="w", wraplength=px(276))
        self.ntitle.pack(anchor="w", padx=px(22), fill="x")
        self.notes = tk.Label(side, text="The exact version of each answer shows up here, to read while I talk.",
                              bg="#111210", fg="#c9d0bf", font=(sans, 10), justify="left", anchor="nw", wraplength=px(276))
        self.notes.pack(anchor="w", padx=px(22), pady=(px(8), 0), fill="x")
        sb = tk.Frame(side, bg="#111210")
        sb.pack(side="bottom", fill="x", padx=px(22), pady=px(22))
        for t, cmd in (("save to Obsidian", app.talk_save), ("make flashcards from this", app.talk_cards)):
            b = tk.Label(sb, text=t, bg="#111210", fg="#c9d0bf", font=(mono, 9), pady=px(8), cursor="hand2",
                         highlightthickness=1, highlightbackground="#343a2e")
            b.pack(fill="x", pady=px(4))
            b.bind("<Button-1>", lambda e, c=cmd: c())

        self.state = "listening"
        self.level = 0.0
        self.lines = []
        self._t = 0
        self.set_state("listening")
        self._anim()

    def alive(self):
        try:
            return bool(self.w.winfo_exists())
        except Exception:
            return False

    def close(self):
        try:
            self.w.destroy()
        except Exception:
            pass

    def set_head(self, text):
        self.head.configure(text=text)

    def set_you(self, text):
        self.you.configure(text=text, fg="#aeb5a4")

    def set_state(self, st):
        th = _theme()
        self.state = st
        for k, l in self.pills.items():
            on = k == st
            l.configure(fg=th.ACCENT if on else "#5d6455", bg="#10140a" if on else th.BG,
                        highlightbackground=th.ACCENT if on else th.BORDER)

    def set_paused(self, paused):
        self.pause_b.configure(text="resume listening" if paused else "pause listening")
        self.hint.configure(text="Listening is paused: space or the button to talk again." if paused
                            else "Just start talking to cut in: I stop mid-sentence and listen.")

    def set_muted(self, muted, why=""):
        self.mute_b.configure(text="unmute" if muted else "mute")
        if muted:
            self.hint.configure(text=f"Muted ({why}): I'll show what I'd say instead.")

    def caption(self, text):
        """A new sentence starts: the one before dims, this one is bright."""
        self.lines = (self.lines + [text])[-3:]
        c = self.cap
        c.configure(state="normal")
        c.delete("1.0", "end")
        for i, ln in enumerate(self.lines):
            c.insert("end", ln + " ", ("c", "now" if i == len(self.lines) - 1 else "old"))
        c.configure(state="disabled")
        c.see("end")

    def clear_captions(self):
        self.lines = []
        self.cap.configure(state="normal")
        self.cap.delete("1.0", "end")
        self.cap.configure(state="disabled")

    def set_notes(self, text):
        lines = [l.strip() for l in (text or "").strip().splitlines() if l.strip()]
        if not lines:
            return
        if len(lines) < 3:   # a spoken answer is usually one paragraph: its first sentence on top, the rest as points
            sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", " ".join(lines)) if x.strip()]
            lines = sents[:1] + sents[1:8]
        title = re.sub(r"^[#*\s]+|[*]+$", "", lines[0])
        body = "\n".join("• " + re.sub(r"^[-*•\d.)\s]+", "", l).replace("**", "") for l in lines[1:8])
        self.ntitle.configure(text=title)
        self.notes.configure(text=body)

    def _anim(self):
        if not self.alive():
            return
        th = _theme()
        c, px = self.cv, self.app.px
        c.delete("all")
        cx = cy = px(100)
        self._t += 1
        lvl = self.level
        if self.state == "listening":
            r = px(50) + int(px(16) * lvl)
            c.create_oval(cx - px(96), cy - px(96), cx + px(96), cy + px(96), outline="#2a3410")
            c.create_oval(cx - r - px(18), cy - r - px(18), cx + r + px(18), cy + r + px(18), outline="#3a4a17")
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=th.ACCENT, width=2, fill="#10140a")
        elif self.state == "thinking":
            c.create_oval(cx - px(54), cy - px(54), cx + px(54), cy + px(54), outline=th.ACCENT, width=2, fill="#10140a")
            for i in range(3):
                on = (self._t // 6) % 3 == i
                x = cx + (i - 1) * px(20)
                c.create_oval(x - px(5), cy - px(5), x + px(5), cy + px(5), fill=th.ACCENT if on else "#3a4a17", outline="")
        else:
            c.create_oval(cx - px(96), cy - px(96), cx + px(96), cy + px(96), outline="#2a3410")
            c.create_oval(cx - px(74), cy - px(74), cx + px(74), cy + px(74), outline="#3a4a17")
            c.create_oval(cx - px(54), cy - px(54), cx + px(54), cy + px(54), outline=th.ACCENT, width=2, fill="#10140a")
            for i in range(7):
                h = px(8) + int(px(22) * abs(math.sin(self._t * 0.22 + i * 0.9)))
                x = cx + (i - 3) * px(10)
                c.create_line(x, cy - h, x, cy + h, fill=th.ACCENT, width=px(4), capstyle="round")
        self.w.after(50, self._anim)


class VoiceSettings:
    """Right-click the owl > Voice & quiet: pick the voice, speed, how it talks, pronunciations, and Quiet."""

    def __init__(self, app, tab="voice"):
        import tkinter as tk
        th = _theme()
        self.app, self.tk, self.th = app, tk, th
        px = app.px
        sans, serif, mono = _fonts(app)
        self.sans, self.serif, self.mono = sans, serif, mono
        self.w = tk.Toplevel(app.root)
        self.w.title("Archie · voice & quiet")
        self.w.configure(bg=th.BG)
        W, H = px(700), px(820)
        sw, sh = self.w.winfo_screenwidth(), self.w.winfo_screenheight()
        self.w.geometry(f"{W}x{H}+{(sw - W) // 2}+{max(20, (sh - H) // 2 - px(20))}")
        try:
            self.w.iconphoto(True, app._icon)
        except Exception:
            pass
        tabs = tk.Frame(self.w, bg=th.BG)
        tabs.pack(fill="x", padx=px(28), pady=(px(20), 0))
        self.tabb = {}
        for k, l in (("voice", "Archie's voice"), ("quiet", "Quiet")):
            b = tk.Label(tabs, text=l, bg=th.BG, font=(serif, 18), cursor="hand2", padx=px(4))
            b.pack(side="left", padx=(0, px(22)))
            b.bind("<Button-1>", lambda e, k=k: self.show(k))
            self.tabb[k] = b
        holder = tk.Frame(self.w, bg=th.BG)
        holder.pack(fill="both", expand=True, padx=(px(28), px(8)), pady=px(16))
        self.cv = tk.Canvas(holder, bg=th.BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(holder, orient="vertical", command=self.cv.yview, width=px(8))
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.cv, bg=th.BG)
        self._win = self.cv.create_window(0, 0, anchor="nw", window=self.body)
        self.body.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfigure(self._win, width=e.width - px(14)))
        self.w.bind("<MouseWheel>", lambda e: self.cv.yview_scroll(int(-e.delta / 120), "units"))
        self.w.bind("<Button-4>", lambda e: self.cv.yview_scroll(-2, "units"))
        self.w.bind("<Button-5>", lambda e: self.cv.yview_scroll(2, "units"))
        self.show(tab)

    def alive(self):
        try:
            return bool(self.w.winfo_exists())
        except Exception:
            return False

    def lift(self, tab=None):
        if tab:
            self.show(tab)
        self.w.deiconify()
        self.w.lift()
        self.w.focus_force()

    def show(self, tab):
        th = self.th
        self.tab = tab
        for k, b in self.tabb.items():
            b.configure(fg="#f2f2ec" if k == tab else th.MUTED)
        for c in self.body.winfo_children():
            c.destroy()
        (self._voice if tab == "voice" else self._quiet)()
        self.cv.yview_moveto(0)

    # small helpers
    def _k(self, parent, t):
        self.tk.Label(parent, text=t.upper(), bg=self.th.BG, fg=self.th.MUTED, font=(self.mono, 8)).pack(anchor="w", pady=(self.app.px(12), self.app.px(6)))

    def _check(self, parent, text, key, default=False, after=None):
        tk, th, cfg = self.tk, self.th, self.app.cfg
        v = tk.BooleanVar(value=bool(cfg.get(key, default)))

        def flip():
            cfg[key] = bool(v.get())
            self.app.save_cfg()
            if after:
                after()
        cb = tk.Checkbutton(parent, text=text, variable=v, command=flip, bg=th.BG, fg="#c9d0bf", selectcolor="#141414",
                            activebackground=th.BG, activeforeground=th.ACCENT, font=(self.sans, 10), anchor="w",
                            highlightthickness=0, bd=0)
        cb.pack(anchor="w", fill="x")
        return v

    def _voice(self):
        tk, th, app, px = self.tk, self.th, self.app, self.app.px
        cfg = app.cfg
        b = self.body
        self._k(b, "Voice")
        grid = tk.Frame(b, bg=th.BG)
        grid.pack(fill="x")
        cur = cfg.get("voice_id") or DEFAULT_VOICE_ID
        cands = accent_info()
        for i, v in enumerate(VOICES):
            on = v["id"] == cur
            picked = bool(v.get("accent")) and accent_ref(v["id"], cfg) is not None
            aud = bool(v.get("accent")) and bool(cands.get(v["id"])) and not picked
            off = bool(v.get("accent")) and not picked and not aud
            cell = tk.Frame(grid, bg="#141a0c" if on else th.BG, highlightthickness=1,
                            highlightbackground=th.ACCENT if on else ("#343a2e" if not off else "#1f231b"))
            cell.grid(row=i // 2, column=i % 2, sticky="ew", padx=px(3), pady=px(3))
            grid.grid_columnconfigure(i % 2, weight=1)
            t = tk.Frame(cell, bg=cell["bg"])
            t.pack(side="left", fill="x", expand=True, padx=px(10), pady=px(7))
            tk.Label(t, text=v["name"], bg=cell["bg"], fg="#5d6455" if off else "#f2f2ec", font=(self.sans, 10), anchor="w").pack(anchor="w")
            sub = (("not in the open recordings yet" if v["id"] == "scandi" and cands else "comes with the accent audition") if off
                   else f"▶ audition: {len(cands[v['id']])} voices to hear" if aud
                   else (f"{(cfg.get('accent_pick') or {}).get(v['id'])} · for book audio (Feather's Sonia box)"
                         + ("" if cfg.get("accent_live") else "; live uses Archie's voice")) if picked else v["sub"])
            tk.Label(t, text=sub, bg=cell["bg"], fg=th.ACCENT if aud else th.MUTED,
                     font=(self.mono, 8), anchor="w").pack(anchor="w")
            if aud or picked:
                ab = tk.Label(cell, text="audition", bg=cell["bg"], fg=th.MUTED, font=(self.mono, 8), cursor="hand2", padx=px(6))
                ab.pack(side="right")
                ab.bind("<Button-1>", lambda e, vid=v["id"]: self._audition(vid))
            if aud:
                for wdg in (cell, t) + tuple(t.winfo_children()):
                    wdg.bind("<Button-1>", lambda e, vid=v["id"]: self._audition(vid))
                    wdg.configure(cursor="hand2")
            if not off and not aud:
                pl = tk.Label(cell, text="▶", bg=cell["bg"], fg=th.ACCENT if on else th.MUTED, font=(self.sans, 11), cursor="hand2", padx=px(10))
                pl.pack(side="right")
                pl.bind("<Button-1>", lambda e, vid=v["id"]: app.voice_preview(vid))
                for wdg in (cell, t) + tuple(t.winfo_children()):
                    wdg.bind("<Button-1>", lambda e, vid=v["id"]: self._pick(vid))
                    wdg.configure(cursor="hand2")
        row = tk.Frame(b, bg=th.BG)
        row.pack(fill="x", pady=(px(10), 0))
        tk.Label(row, text="speed", bg=th.BG, fg=th.MUTED, font=(self.mono, 9)).pack(side="left")
        sp = tk.Scale(row, from_=0.7, to=1.4, resolution=0.05, orient="horizontal", length=px(220), showvalue=True,
                      bg=th.BG, fg="#c9d0bf", troughcolor="#262a22", highlightthickness=0, bd=0, activebackground=th.ACCENT,
                      font=(self.mono, 8), command=lambda val: self._set("voice_speed", float(val)))
        sp.set(float(cfg.get("voice_speed") or 0.95))
        sp.pack(side="left", padx=px(10))
        sp.bind("<ButtonRelease-1>", lambda e: app.voice_preview(None))
        tk.Label(row, text="volume", bg=th.BG, fg=th.MUTED, font=(self.mono, 9)).pack(side="left", padx=(px(6), 0))
        vo = tk.Scale(row, from_=10, to=100, resolution=5, orient="horizontal", length=px(150), showvalue=True,
                      bg=th.BG, fg="#c9d0bf", troughcolor="#262a22", highlightthickness=0, bd=0, activebackground=th.ACCENT,
                      font=(self.mono, 8), command=lambda val: self._set("voice_volume", int(val) / 100.0))
        vo.set(int(round(100 * float(cfg.get("voice_volume") or 1.0))))
        vo.pack(side="left", padx=px(10))
        vo.bind("<ButtonRelease-1>", lambda e: app.voice_preview(None))
        self._check(row, "room finish (a slight speaker-in-the-room feel)", "voice_room", True)

        self._k(b, "How it talks")
        self._check(b, "In talk mode, answer out loud like a person: short sentences, no lists or headings", "talk_spoken", True)
        self._check(b, "Keep the exact written version on screen while it talks", "talk_notes", True)
        self._check(b, "Listen hands-free in talk mode (stop the moment I talk)", "talk_handsfree", True)
        srow = tk.Frame(b, bg=th.BG)
        srow.pack(fill="x", pady=(px(4), px(2)))
        tk.Label(srow, text="Mic sensitivity (higher hears you further away; lower ignores the keyboard)", bg=th.BG, fg="#c9d0bf",
                 font=(self.sans, 10)).pack(anchor="w")
        sc = tk.Scale(srow, from_=0.5, to=2.5, resolution=0.1, orient="horizontal", bg=th.BG, fg="#c9d0bf", troughcolor="#141414",
                      highlightthickness=0, bd=0, activebackground=th.ACCENT, length=px(260), font=(self.mono, 8))
        sc.set(float(cfg.get("talk_mic", 1.0)))
        sc.pack(anchor="w")
        sc.bind("<ButtonRelease-1>", lambda e: self._set("talk_mic", float(sc.get())))
        self._check(b, "A soft \"hmm\" if an answer takes a moment", "talk_hmm", True)
        self._check(b, f"Quick talk model: use {cfg.get('talk_model') or 'qwen2.5:3b'} in talk mode (about twice as fast, a bit less sharp; "
                       "Tools\\Get Fast Talk.bat downloads it)", "talk_fast_model", False,
                    after=lambda: (cfg.setdefault("talk_model", "qwen2.5:3b"), self.app.save_cfg()))

        self._k(b, "Speed per mode (times your speed)")
        pm = tk.Frame(b, bg=th.BG)
        pm.pack(fill="x")
        ms = dict(MODE_SPEED, **(cfg.get("mode_speed") or {}))
        for i, m in enumerate(("Tutor", "Professor", "Workshop")):
            f = tk.Frame(pm, bg=th.BG, highlightthickness=1, highlightbackground="#262a22")
            f.grid(row=0, column=i, sticky="ew", padx=px(3))
            pm.grid_columnconfigure(i, weight=1)
            tk.Label(f, text=m, bg=th.BG, fg="#f2f2ec", font=(self.sans, 10)).pack(anchor="w", padx=px(10), pady=(px(6), 0))
            sv = tk.StringVar(value=f"{float(ms.get(m, 1.0)):.2f}")
            sb = tk.Spinbox(f, from_=0.7, to=1.3, increment=0.05, textvariable=sv, width=5, bg="#141414", fg="#c9d0bf",
                            buttonbackground="#262a22", highlightthickness=0, bd=0, font=(self.mono, 9),
                            command=lambda m=m, sv=sv: self._mode_speed(m, sv.get()))
            sb.pack(anchor="w", padx=px(10), pady=(px(2), px(8)))

        self._k(b, "Say it right")
        lst = tk.Frame(b, bg=th.BG, highlightthickness=1, highlightbackground="#262a22")
        lst.pack(fill="x")
        pron = cfg.get("pronunciations") if isinstance(cfg.get("pronunciations"), list) else list(DEFAULT_PRON)
        for i, (a, s) in enumerate(pron[:8]):
            r = tk.Frame(lst, bg=th.BG)
            r.pack(fill="x", padx=px(12), pady=px(3))
            tk.Label(r, text=a, bg=th.BG, fg="#f2f2ec", font=(self.sans, 10)).pack(side="left")
            x = tk.Label(r, text="×", bg=th.BG, fg=th.MUTED, font=(self.sans, 11), cursor="hand2")
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, i=i: self._pron_del(i))
            p = tk.Label(r, text="▶", bg=th.BG, fg=th.MUTED, font=(self.sans, 10), cursor="hand2", padx=px(10))
            p.pack(side="right")
            p.bind("<Button-1>", lambda e, a=a: app.voice_say(a))
            tk.Label(r, text=f"“{s}”", bg=th.BG, fg=th.ACCENT, font=(self.mono, 9)).pack(side="right")
        add = tk.Frame(lst, bg=th.BG)
        add.pack(fill="x", padx=px(12), pady=px(6))
        e1 = tk.Entry(add, bg="#141414", fg="#f2f2ec", insertbackground="#f2f2ec", bd=0, font=(self.sans, 10), width=18)
        e2 = tk.Entry(add, bg="#141414", fg="#f2f2ec", insertbackground="#f2f2ec", bd=0, font=(self.sans, 10), width=22)
        e1.insert(0, "written like")
        e2.insert(0, "said like")
        for e in (e1, e2):
            e.bind("<FocusIn>", lambda ev, e=e: e.get() in ("written like", "said like") and e.delete(0, "end"))
            e.pack(side="left", padx=(0, px(6)), ipady=px(3))
        ab = tk.Label(add, text="add", bg=th.ACCENT, fg=th.ON_ACCENT, font=(self.mono, 9, "bold"), padx=px(10), cursor="hand2")
        ab.pack(side="left")
        ab.bind("<Button-1>", lambda ev: self._pron_add(e1.get(), e2.get()))
        tk.Label(b, text="Dates, times, percentages and short forms (e.g., approx., Dr.) are said properly on their own.",
                 bg=th.BG, fg="#5d6455", font=(self.mono, 8)).pack(anchor="w", pady=(px(6), 0))
        foot = tk.Frame(b, bg=th.BG)
        foot.pack(fill="x", pady=(px(16), px(4)))
        hb = tk.Label(foot, text="▶ hear today's brief", bg=th.BG, fg="#c9d0bf", font=(self.mono, 9), padx=px(14), pady=px(8),
                      cursor="hand2", highlightthickness=1, highlightbackground="#343a2e")
        hb.pack(side="left")
        hb.bind("<Button-1>", lambda e: app.voice_brief())
        db = tk.Label(foot, text="done", bg=th.ACCENT, fg=th.ON_ACCENT, font=(self.mono, 9, "bold"), padx=px(20), pady=px(8), cursor="hand2")
        db.pack(side="right")
        db.bind("<Button-1>", lambda e: self.w.destroy())

    def _set(self, key, val):
        self.app.cfg[key] = val
        self.app.save_cfg()

    def _audition(self, vid):
        """Hear each candidate for an accent voice (the same line in each), then keep one."""
        tk, th, app, px = self.tk, self.th, self.app, self.app.px
        cands = accent_info().get(vid) or []
        w = tk.Toplevel(self.w)
        w.title("Archie · accent audition")
        w.configure(bg=th.BG)
        w.attributes("-topmost", True)
        name = (VOICE_BY_ID.get(vid) or {}).get("name", vid)
        tk.Label(w, text=name.upper() + " · AUDITION", bg=th.BG, fg="#f2f2ec", font=(self.mono, 10, "bold")).pack(anchor="w", padx=px(14), pady=(px(12), px(2)))
        tk.Label(w, text="The same line in each voice. Played on this PC; they run offline once picked.", bg=th.BG, fg=th.MUTED,
                 font=(self.mono, 8)).pack(anchor="w", padx=px(14), pady=(0, px(8)))
        mine = (app.cfg.get("accent_pick") or {}).get(vid)

        def play(c):
            p = os.path.join(ACC_DIR, c.get("wav") or "")
            if os.path.exists(p) and sys.platform == "win32":
                import winsound
                winsound.PlaySound(p, winsound.SND_FILENAME | winsound.SND_ASYNC)

        def keep(c):
            ap = dict(app.cfg.get("accent_pick") or {})
            ap[vid] = c["sp"]
            self._set("accent_pick", ap)
            w.destroy()
            self._pick(vid)
        for c in cands:
            row = tk.Frame(w, bg="#141a0c" if c["sp"] == mine else th.BG, highlightthickness=1,
                           highlightbackground=th.ACCENT if c["sp"] == mine else "#343a2e")
            row.pack(fill="x", padx=px(14), pady=px(3))
            who = ("woman" if c.get("gender") == "F" else "man") + (f", {c['age']}" if c.get("age") else "") + (f", {c['region']}" if c.get("region") else "")
            tk.Label(row, text=f"{c['sp']} · {who}", bg=row["bg"], fg="#f2f2ec", font=(self.mono, 9)).pack(side="left", padx=px(10), pady=px(8))
            tk.Button(row, text="use this voice", command=lambda c=c: keep(c), bg=th.ACCENT, fg="#0a0a0a", bd=0, font=(self.mono, 8),
                      cursor="hand2").pack(side="right", padx=px(6), pady=px(6), ipadx=px(6))
            tk.Button(row, text="▶", command=lambda c=c: play(c), bg=row["bg"], fg=th.ACCENT, bd=0, font=(self.sans, 11),
                      cursor="hand2").pack(side="right", padx=px(4))
        tk.Label(w, text="Voices from the VCTK corpus (University of Edinburgh, CC BY 4.0): people who recorded for open research.",
                 bg=th.BG, fg=th.MUTED, font=(self.mono, 7), wraplength=px(460), justify="left").pack(anchor="w", padx=px(14), pady=(px(8), px(12)))

    def _pick(self, vid):
        self._set("voice_id", vid)
        self.app.voice_preview(vid)
        self.show("voice")

    def _mode_speed(self, m, val):
        try:
            v = float(val)
        except ValueError:
            return
        ms = dict(self.app.cfg.get("mode_speed") or {})
        ms[m] = v
        self._set("mode_speed", ms)

    def _pron_add(self, a, s):
        a, s = a.strip(), s.strip()
        if not a or not s or a == "written like" or s == "said like":
            return
        pron = self.app.cfg.get("pronunciations") if isinstance(self.app.cfg.get("pronunciations"), list) else list(DEFAULT_PRON)
        pron = [p for p in pron if p[0].lower() != a.lower()] + [[a, s]]
        self._set("pronunciations", pron)
        self.app.voice_say(a)
        self.show("voice")

    def _pron_del(self, i):
        pron = self.app.cfg.get("pronunciations") if isinstance(self.app.cfg.get("pronunciations"), list) else list(DEFAULT_PRON)
        if 0 <= i < len(pron):
            pron.pop(i)
        self._set("pronunciations", pron)
        self.show("voice")

    def _quiet(self):
        tk, th, app, px = self.tk, self.th, self.app, self.app.px
        cfg = app.cfg
        b = self.body
        top = tk.Frame(b, bg=th.BG)
        top.pack(fill="x", pady=(px(6), 0))
        q, why = app.quiet.state()
        tk.Label(top, text=("Quiet is on" + (f" · {why}" if why else "")) if q else "Quiet is off", bg=th.BG,
                 fg=th.ACCENT if q else "#f2f2ec", font=(self.serif, 15)).pack(side="left")
        mb = tk.Label(top, text=("unmute" if cfg.get("quiet") else "mute") + "  ·  Ctrl+Alt+Q", bg="#141a0c" if cfg.get("quiet") else th.BG,
                      fg=th.ACCENT, font=(self.mono, 9, "bold"), padx=px(14), pady=px(8), cursor="hand2",
                      highlightthickness=1, highlightbackground=th.ACCENT)
        mb.pack(side="right")
        mb.bind("<Button-1>", lambda e: (app.toggle_quiet(), self.show("quiet")))
        tk.Label(b, text="Muted, Archie keeps working: it still \"talks\", you read it instead of hearing it. "
                         "Nothing makes a sound until you unmute.", bg=th.BG, fg="#c9d0bf", font=(self.sans, 10),
                 justify="left", wraplength=px(620)).pack(anchor="w", pady=(px(8), 0))
        self._k(b, "Notifications while it's quiet")
        nv = tk.StringVar(value=cfg.get("notify_quiet", "silent"))
        for val, label in (("silent", "Silent: they slide in at the corner, no sound"),
                           ("some", "Sound only for professors' emails and a timer finishing")):
            tk.Radiobutton(b, text=label, value=val, variable=nv, command=lambda: self._set("notify_quiet", nv.get()),
                           bg=th.BG, fg="#c9d0bf", selectcolor="#141414", activebackground=th.BG, activeforeground=th.ACCENT,
                           font=(self.sans, 10), anchor="w", highlightthickness=0, bd=0).pack(anchor="w", fill="x")
        self._k(b, "Go quiet by itself")
        self._check(b, "Speak only through headphones (captions the moment they come out)", "quiet_headphones_only", False,
                    after=lambda: (app.quiet.refresh(force=True), self.w.after(2500, lambda: self.alive() and self.show("quiet"))))
        dev = app.quiet.device
        dr = tk.Frame(b, bg=th.BG)
        dr.pack(fill="x", padx=(px(24), 0))
        tk.Label(dr, text=(f"Sound is going to: {dev}" + ("  (headphones)" if app.quiet.headphones() else "")) if dev
                 else "Sound output: checking…", bg=th.BG, fg=th.MUTED, font=(self.mono, 8)).pack(side="left")
        if dev and not app.quiet.headphones():
            hb = tk.Label(dr, text="these are headphones", bg=th.BG, fg=th.ACCENT, font=(self.mono, 8), cursor="hand2", padx=px(8))
            hb.pack(side="left")
            hb.bind("<Button-1>", lambda e: (self._set("quiet_headphone_names", (cfg.get("quiet_headphone_names") or []) + [dev]), self.show("quiet")))
        self._check(b, "During classes on my calendar", "quiet_classes", True)
        wf = tk.Frame(b, bg=th.BG)
        wf.pack(fill="x", pady=(px(8), 0))
        nets = cfg.get("quiet_wifi") or []
        tk.Label(wf, text="On these Wi-Fi networks: " + (", ".join(nets) if nets else "none yet"), bg=th.BG, fg="#c9d0bf",
                 font=(self.sans, 10)).pack(side="left")
        cur = app.quiet.wifi or wifi_name()
        if cur and cur not in nets:
            ab = tk.Label(wf, text=f"+ add {cur}", bg=th.BG, fg=th.ACCENT, font=(self.mono, 9), cursor="hand2", padx=px(10))
            ab.pack(side="left")
            ab.bind("<Button-1>", lambda e: (self._set("quiet_wifi", nets + [cur]), self.show("quiet")))
        if nets:
            cb = tk.Label(wf, text="clear", bg=th.BG, fg=th.MUTED, font=(self.mono, 9), cursor="hand2", padx=px(10))
            cb.pack(side="left")
            cb.bind("<Button-1>", lambda e: (self._set("quiet_wifi", []), self.show("quiet")))
        hf = tk.Frame(b, bg=th.BG)
        hf.pack(fill="x", pady=(px(8), 0))
        hrs = cfg.get("quiet_hours") or ["", ""]
        tk.Label(hf, text="Quiet hours from", bg=th.BG, fg="#c9d0bf", font=(self.sans, 10)).pack(side="left")
        a = tk.Entry(hf, width=6, bg="#141414", fg="#f2f2ec", insertbackground="#f2f2ec", bd=0, font=(self.mono, 10))
        a.insert(0, hrs[0] or "23:00")
        a.pack(side="left", padx=px(6), ipady=px(2))
        tk.Label(hf, text="to", bg=th.BG, fg="#c9d0bf", font=(self.sans, 10)).pack(side="left")
        z = tk.Entry(hf, width=6, bg="#141414", fg="#f2f2ec", insertbackground="#f2f2ec", bd=0, font=(self.mono, 10))
        z.insert(0, hrs[1] or "07:00")
        z.pack(side="left", padx=px(6), ipady=px(2))
        on = bool(cfg.get("quiet_hours"))
        tb = tk.Label(hf, text="on" if on else "off", bg="#141a0c" if on else th.BG, fg=th.ACCENT if on else th.MUTED,
                      font=(self.mono, 9, "bold"), padx=px(10), pady=px(2), cursor="hand2", highlightthickness=1,
                      highlightbackground=th.ACCENT if on else "#343a2e")
        tb.pack(side="left", padx=px(8))

        def hours_toggle(e=None):
            if cfg.get("quiet_hours"):
                self._set("quiet_hours", None)
            else:
                ok = all(re.fullmatch(r"\d{1,2}:\d{2}", x.get().strip()) for x in (a, z))
                if ok:
                    self._set("quiet_hours", [a.get().strip().zfill(5), z.get().strip().zfill(5)])
            self.show("quiet")
        tb.bind("<Button-1>", hours_toggle)
        tk.Label(b, text="Quiet covers Archie's voice, talk mode, the focus timer's chime and mail notifications on this PC.",
                 bg=th.BG, fg="#5d6455", font=(self.mono, 8), wraplength=px(620), justify="left").pack(anchor="w", pady=(px(16), 0))
