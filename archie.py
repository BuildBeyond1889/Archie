#!/usr/bin/env python3
"""
Archie - a floating desktop helper for your local AI models.

A small owl floats on top of your other windows. Drag it anywhere.
Click it to open a chat panel and ask questions. Answers come from a model
running on YOUR computer through Ollama. Nothing leaves the machine.

  * + button (or drag files onto the chat) to attach PDFs, Word docs, text,
    code, or images (photos of notes, screenshots).
  * Notes button: Archie searches everything in the Notes folder and uses
    it to answer.
  * Right-click the owl for more (owl size, open Notes folder, quit).

The file archie_brain.py next to this one does the reading, searching and
talking to Ollama. This file is the window you see.
"""

import datetime
import glob
import json
import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog

from archie_brain import (ArchieError, NotesIndex, OLLAMA_URL, SUPPORTED_EXT,
                          WikiLibrary, delete_chat, file_kind, is_vision_model,
                          list_chats, list_models, load_model_names, load_modes, pick_vision_model, read_image_b64,
                          quick_chat, read_small_text, read_text, save_chat, stream_chat)

from archie_snip import GlobalHotkeys, SnipOverlay, grab_screen, pretty_combo
import archie_obsidian as obs
import archie_theme as th
from archie_daily import DailyNote
import archie_books as books
import archie_study as study
import archie_apps as apps
import archie_imagine as imagine
import archie_calendar as cal
import archie_exam as exam
import archie_focus as focusmod
import archie_recap as recapmod
import archie_gym as gym
import archie_lecture as lecture
import archie_review as review
import archie_newsroll as newsroll
import archie_autoupdate as autoupdate
import archie_warm as warm
import archie_cool as cool
import archie_housekeep as housekeep
import archie_inbox as inboxm
import archie_dates as datesm
import archie_mail as mailm
import archie_calchat as calchat
import archie_examprep as examprep
import archie_memory as mem
try:
    import archie_world as world
except Exception:          # World is optional; Archie runs without it
    world = None
try:
    import archie_banner as banner
except Exception:          # Pillow missing: no picture strip
    banner = None
import random
import time
import make_manual
from archie_scan import HandwritingReader
from archie_voice import Recorder, Transcriber, VoiceError, fmt_time, tidy as voice_tidy
from archie_speak import Speaker, VOICES, DEFAULT_VOICE
try:   # Archie's new voice, talk mode and Quiet
    import archie_talk as talk
except Exception:
    talk = None
from archie_listen import Listener
import archie_vaultgen as vaultgen
from archie_brief import (BriefState, Deadlines, Tasks, handle_command, new_notes,
                          set_start_with_windows, starts_with_windows, when_label)

try:
    from PIL import Image, ImageOps, ImageTk
except Exception:
    Image = ImageOps = ImageTk = None

try:  # optional: drag-and-drop support (installed by Install Extras.bat)
    from tkinterdnd2 import DND_FILES, TkinterDnD
except Exception:
    TkinterDnD = None

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "archie_config.json")
NOTES_DIR = os.path.join(APP_DIR, "Notes")
NOTES_INDEX = os.path.join(APP_DIR, "notes_index.json")
CHATS_DIR = os.path.join(APP_DIR, "Chats")
BANNERS_DIR = os.path.join(APP_DIR, "Banners")               # pictures for the header strip
GYM_DIR = os.path.join(APP_DIR, "Drawing Gym")               # reference pictures for the drawing gym
MEMORY_DIR = os.path.join(APP_DIR, "Memory")                  # gym log, where you left off, this week
UPDATE_STAMP = os.path.join(APP_DIR, "last_update.txt")   # written by Update Archie.bat
UPDATE_EVERY_DAYS = 365


def days_since_update():
    """Days since Update Archie.bat last ran (starts counting from the first launch)."""
    try:
        with open(UPDATE_STAMP, encoding="utf-8") as f:
            last = datetime.date.fromisoformat(f.read().strip()[:10])
    except (OSError, ValueError):
        try:
            with open(UPDATE_STAMP, "w", encoding="utf-8") as f:
                f.write(datetime.date.today().isoformat())
        except OSError:
            pass
        return 0
    return (datetime.date.today() - last).days
MODES_DIR = os.path.join(APP_DIR, "Modes")
ABOUT_PATH = os.path.join(APP_DIR, "about_me.txt")
MODEL_NAMES_PATH = os.path.join(APP_DIR, "model_names.txt")
WIKI_DIR = os.path.join(APP_DIR, "Wikipedia")
SNIPS_DIR = os.path.join(APP_DIR, "Screenshots")
TASKS_PATH = os.path.join(APP_DIR, "tasks.txt")
DEADLINES_PATH = os.path.join(APP_DIR, "deadlines.txt")
BRIEF_STATE_PATH = os.path.join(APP_DIR, "brief_state.json")
RECORDINGS_DIR = os.path.join(APP_DIR, "Recordings")
STUDY_DIR = os.path.join(APP_DIR, "Study")
LISTEN_STATE = os.path.join(APP_DIR, "listen_state.json")
IMAGES_DIR = os.path.join(APP_DIR, "Images")
CALENDAR_PATH = os.path.join(APP_DIR, "calendar.json")
VOICE_MODELS_DIR = os.path.join(APP_DIR, "Voice")
PIPER_DIR = os.path.join(VOICE_MODELS_DIR, "piper")
FULL_NAME = "Artificial Reasoning Core, Home Intelligence Engine"
MAX_ATTACH_CHARS = 40000   # roughly 10,000 words per message

DEFAULT_CONFIG = {
    "model": "qwen2.5:7b",
    "owl_size": "Medium",
    "use_notes": False,
    "use_wiki": False,
    "text_size": "Normal",
    "brief_daily": True,
    "obsidian_vault": None,        # your Obsidian vault folder (found automatically)           # show the morning brief the first time Archie opens each day
    "save_drops_to_notes": True,
    "read_handwriting": True,
    "daily_note": True,
    "phone_tidy": True,            # tidy voice notes from the phone into clean notes
    "lecture_wake": False,         # wake the PC after each class on the calendar (scheduled task)
    "lecture_minutes": 75,         # how long a class runs (for naming recordings and the wake time)
    "lecture_sleep_after": True,   # after a wake-up, go back to sleep once the note is written
    "audiobooks_paused": False,
    "audiobook_model": None,       # Whisper model for audiobooks (None = same as voice notes)
    "files_dir": None,             # where new files Archie writes are saved (None = Documents\\Archie Files)            # to-dos + brief in today's Obsidian daily note      # read photos / scanned PDFs in Notes into searchable text
    "ocr_model": None,             # which vision model reads them (None = best one installed)   # copy files you drop into the chat into Notes
    "hotkey_chat": "ctrl+alt+a",   # show / hide Archie from anywhere
    "hotkey_snip": "ctrl+alt+s",   # drag a box on screen and send it to Archie
    "hotkey_voice": "ctrl+alt+v",  # start / stop a voice note
    "voice_model": "small.en",     # Whisper model (Get Voice.bat downloads it)
    "voice_device": "cpu",         # "cpu" leaves the graphics card to the chat models
    "hotkey_talk": "ctrl+alt+t",
    "hotkey_recap": "ctrl+alt+r",
    "hotkey_quiet": "ctrl+alt+q",  # mute / unmute Archie (it shows captions instead)
    "hotkey_mic": "alt+m",         # in talk: your mic off / on
    "voice_id": "archie",          # the new voice (Voice\\kokoro); "voice_engine": "piper" goes back to the old one
    "voice_speed": 0.95,
    "voice_room": True,
    "talk_spoken": True,           # talk mode answers like a person talks
    "talk_notes": True,            # ...with the exact version on screen
    "talk_handsfree": True,        # talk mode listens by itself and stops when you cut in
    "talk_hmm": True,
    "quiet": False,                # muted by hand
    "quiet_headphones_only": False,
    "quiet_wifi": [],
    "quiet_classes": True,
    "quiet_hours": None,
    "notify_quiet": "silent",
    "banner": True,                # the picture strip in the header
    "banner_minutes": 15,          # how often it changes (0 = only when clicked, 1440 = once a day)
    "banner_pinned": None,         # a picture you pinned  # the evening recap: press to start, press again to wrap up   # talk to Archie: press, speak, press again
    "speak_answers": False,        # read every answer out loud
    "talk_speaks": False,          # Ctrl+Alt+T answers out loud even with speak off
    "speech_voice": "en_GB-alan-medium",
    "speech_speed": 1.0,
    "mode": "General",
    "context_tokens": 16384,
    "bubble_x": None,
    "bubble_y": None,
    "system_prompt": (
        "You are ARCHIE (Artificial Reasoning Core, Home Intelligence Engine), a "
        "private, offline assistant running on the user's own computer. You're named "
        "after Merlin's owl. Be clear, patient and "
        "practical. Explain technical ideas in plain language first, then give "
        "the details. Keep answers concise unless asked to go deeper. When the user "
        "shares a file, read it carefully and refer to specific parts of it."
    ),
}

ABOUT_STARTER = """\
# ABOUT ME - Archie reads this before every answer, so it always knows who you are.
# Edit it anytime in Notepad (right-click the owl > Edit About me). Changes apply
# to your next message. Lines starting with # are notes to yourself and are ignored.

Name: [your name]

Goals:
- [what you're working toward: a course, a degree, a skill, a job]

Background:
- [what you already know, so explanations start in the right place]

Projects:
- [things you're building, writing or studying]

How I like things explained:
- Plain language first, then the technical details.
- Step by step, and tell me WHY, not just what.
"""

DEFAULT_MODES = {
    "General": (None, """\
General mode: be a helpful all-round assistant. Match the length of your answer
to the question."""),
    "Tutor": ("qwen2.5:7b", """\
Tutor mode: your job is to help the user actually learn, not to hand over answers.
- For homework-style questions, first ask what the user already knows or has tried.
- Give hints and guide them one step at a time; let them do the thinking.
- Use analogies from hands-on work (building, tools, materials) when they help.
- End with one short question that checks the user understood.
- When the user asks to be quizzed: one question at a time, wait for their answer, then
  say what was right, what was off, and why."""),
    "Programmer": ("qwen2.5-coder:7b", """\
Programmer mode: help write, explain and debug code (Python, C#, GDScript for
Godot, JavaScript, Arduino C++ and more).
- Say in plain words what the code does or what the fix is, then show it.
- Give complete, runnable code, not fragments, unless asked for a snippet.
- When debugging, point to the exact line and explain the cause.
- Suggest how to test that it works."""),
    "Robotics": ("qwen2.5:7b", """\
Robotics mode: help with Arduino, Raspberry Pi, sensors, motors, servos, wiring,
power and mechanical builds.
- Safety first: call out voltage, current, battery (especially LiPo) and heat risks.
- Give parts lists with typical specs, and describe wiring pin by pin.
- Provide microcontroller code with comments, and troubleshoot step by step
  (power, wiring, code, in that order)."""),
    "Literature & Writing": ("qwen2.5:7b", """\
Literature & Writing mode: help with reading, essays, college application
writing, stories, scripts and worldbuilding.
- When giving feedback, point to specific sentences and explain why.
- Suggest improvements but keep the user's own voice; don't rewrite whole pieces
  unless the user asks.
- For books and stories, discuss themes, characters, structure and style."""),
    "Professor": ("qwen2.5:7b", """\
Professor mode: teach like a world-class MIT professor who is also a wonderful
explainer. Go deep and be rigorous, but make every step understandable to a smart
student who is new to the topic. Adapt this structure to the size of the question:
1. The big idea: one or two plain sentences on what it is and why it matters.
   Build intuition first (an analogy from hands-on work, building or machines
   when it genuinely fits).
2. First principles: build it up step by step. Define every term the moment it
   appears. Show WHY each step follows from the last; no hand-waving.
3. The precise version: the definitions, equations or code, with every symbol
   and unit explained in words.
4. A worked example with real numbers (or real code), step by step.
5. Where it breaks: common misconceptions, edge cases, and what people get wrong.
6. Connections: how it links to other ideas and to real uses (game development,
   animation, robotics, programming) when that's natural.
7. Finish with 2-3 check-your-understanding questions of rising difficulty.
   Don't give the answers unless asked.
Say when something is simplified, and what the fuller story is. Depth over
breadth: better to truly nail one idea than skim five. Never use jargon without
explaining it. After a long explanation, remind them the user can type
"make flashcards from that" to keep it."""),
}

# Colors - "Graphite x Terminal" (see archie_theme.py)
BG = th.BG              # window background
SURFACE = th.SURFACE    # cards / tab bar
INPUT_BG = th.RAISED    # boxes, bubbles, hover
BORDER = th.BORDER
TEXT = th.TEXT
BODY = th.BODY
MUTED = th.MUTED
DIM = th.DIM
ACCENT = th.ACCENT      # lime
ACCENT_HI = th.ACCENT_HI
TILE = th.ON_ACCENT     # dark text on lime
REC = "#ff5f57"                # recording red
TRANSPARENT_KEY = "#ff00fe"  # painted color that Windows makes see-through

# Fonts - the bundled Geist + JetBrains Mono (chosen once the window exists)
FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"
FONT_SEMI = FONT
MONO = "Consolas"
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

THIS_NOTE = __import__("re").compile(
    r"\b(this|my|the|current|open|opened)\s+(obsidian\s+)?(note|page)\b"
    r"|\bobsidian\s+(note|page|doc|document|file|tab)\b"
    r"|\b(note|page)\s+am\s+i\s+(on|in|reading|viewing|looking at)\b"
    r"|\b(note|page|doc|document|file|tab)\s+(that\s+)?i\s*('?m|am|have|got)\s+(on|in|reading|looking at|viewing|open)"
    r"|\b(open|looking at|viewing|reading|on)\b[^.?!]{0,25}\bin obsidian\b"
    r"|\bobsidian\b[^.?!]{0,40}\b(open|opened|on screen|looking at|viewing)\b", __import__("re").I)

COMMAND_CARDS = [
    ("Archie: how do you add a task to your to-do list?", "add: <task> <optional date>   e.g. add: test servo wiring tomorrow  (todo: and task: work too)"),
    ("Archie: add a task in plain words?", "remind me to <task> <date>   e.g. remind me to call the school friday"),
    ("Archie: tick off a task?", "done: <a word from it>   e.g. done: servo"),
    ("Archie: see your open tasks?", "tasks"),
    ("Archie: add a big countdown to the top of the brief?", "deadline: <what> <date>   e.g. deadline: portfolio due 11/15"),
    ("Archie: add an exam?", "exam: <what> <date> <time>   e.g. exam: bio midterm oct 12 9am  (final: and midterm: work too)"),
    ("Archie: add a test or a quiz?", "test: <what> <date>   /   quiz: <what> <date>"),
    ("Archie: add something that's due?", "due: <what> <date>   e.g. due: history essay 11/3  (assignment:, homework:, essay:, project: too)"),
    ("Archie: add a lab?", "lab: <what> <day> <time>   e.g. lab: chem titration friday 2pm"),
    ("Archie: add a class that repeats every week?", "class: <name> <day with an s> <time>   e.g. class: intro to animation mondays 6pm"),
    ("Archie: add any other event?", "event: <what> <date> <time>  (appointment:, meeting:, reminder: too)  or  add <what> on <date> to my calendar"),
    ("Archie: open the calendar?", "click the date at the top, or type  calendar"),
    ("Archie: open today's Obsidian daily note?", "daily"),
    ("Archie: jot a timestamped line in today's daily note?", "log: <what happened>   e.g. log: fixed the servo jitter"),
    ("Archie: make flashcards on a topic?", "make flashcards about <topic>   (add a number: make 20 flashcards about ...)"),
    ("Archie: make flashcards from the note open in Obsidian?", "make flashcards from this note"),
    ("Archie: make flashcards from its last answer?", "make flashcards from that   (... from this chat for the whole conversation)"),
    ("Archie: review flashcards?", "study   (or study <deck name>;  decks  lists them)"),
    ("Archie study window: the keys?", "Space = show answer, type + Enter = check my answer, 1 again / 2 hard / 3 good / 4 easy"),
    ("Archie: quiz yourself on one chapter of a book?", "quiz me on <book> part <#> chapter <#>   then  now chapter <#>  for the next"),
    ("Archie: list books / put the book away?", "books   /   stop book"),
    ("Archie: check audiobook progress?", "audiobooks"),
    ("Archie: use the note you have open in Obsidian?", "say this note, e.g.  quiz me on this note  /  summarize this note"),
    ("Archie: turn a chat into a linked Obsidian wiki?", "build wiki"),
    ("Archie: open an app or folder?", "open <app or folder>   e.g. open blender, open my notes folder  (launch / start / run too)"),
    ("Archie: have it write a new file?", "make a <kind> script called <name> that ...   e.g. make a godot script called player.gd that moves with WASD"),
    ("Archie: make a picture?", "draw <description>   (paint, sketch, make an image of ...);  image: <exact prompt> uses your words as-is"),
    ("Archie: open the manual?", "manual   (help lists everything with a link to it; or just ask how do I ...)"),
    ("Archie hotkey: open / hide Archie?", "Ctrl+Alt+A"),
    ("Archie: make a mock exam?", "make a mock exam on <topic>   (20 questions, timed; add e.g. 30 questions, timed 45 minutes)"),
    ("Archie: make a practice quiz?", "make a practice quiz on <topic>   or   test me on <topic>   (10 questions)"),
    ("Archie: mock exam from a book, note or deck?", "mock midterm on <book> part 1 chapters 1-5  /  practice quiz on this note  /  practice exam from my <deck> deck"),
    ("Archie mock exam: the keys?", "A-D pick an answer, T/F for true/false, arrows move, Ctrl+Enter next on written answers"),
    ("Archie: see or retake past mock exams?", "exams"),
    ("Archie hotkey: snip the screen?", "Ctrl+Alt+S, then drag a box"),
    ("Archie hotkey: record a voice note?", "Ctrl+Alt+V (again to stop)"),
    ("Archie hotkey: ask by voice?", "Ctrl+Alt+T, talk, Ctrl+Alt+T again to send"),
    ("Archie: open the owl focus timer?", "focus   (or pomodoro / timer, or click the timer next to the date)"),
    ("Archie: start a focus session on something?", "focus: <what you're working on>   e.g. focus: network+ subnetting"),
    ("Archie: shrink the focus timer to the owl on your desktop?", "the corner button (arrow) at the top right of the timer, or Esc"),
    ("Archie: sum up your week so Archie keeps it in mind?", "this week   (it offers on Sundays in the brief too)"),
    ("Archie: see when you do your best work and what's slipping?", "patterns"),
    ("Archie: see everything it can do?", "click help at the bottom (or type help)"),
    ("Archie: see how a school day with Archie goes?", "school day"),
    ("Archie: record a lecture?", "record it with Obsidian's audio recorder on your phone during a class that's on your calendar; the notes show up in Obsidian under Lectures/<class>"),
    ("Archie: open your lecture notes?", "lectures   (or right-click the owl > Lectures > Open lecture notes)"),
    ("Archie: wake the PC after class so notes are ready?", "wake after class on   (off: wake after class off)"),
    ("Archie: open the drawing gym?", "type gym (or drawing gym), or right-click the owl > Drawing gym"),
    ("Archie: add pictures to the drawing gym?", "drop them in the Drawing Gym folder (open folder in the gym); Archie sorts them into figure, faces, hands, animals, landscapes..."),
    ("Archie drawing gym: the keys?", "Space = pause, → next, ← back, M = mirror, G = gray, Esc = end"),
    ("Archie: start the evening recap?", "click recap (the moon, next to the timer), type recap, or press Ctrl+Alt+R"),
    ("Archie: finish the evening recap?", "done, wrap it up (or Ctrl+Alt+R again)"),
    ("Archie: turn a drawing into a finished picture?", "type sketch (or right-click the owl > Sketch to image...), then drop, paste or snip your drawing"),
    ("Archie: make the picture stick closely to your lines?", "follow my lines: strict  (loose = rough layout, balanced = the default)"),
]


MODE_TABS = [("Tutor", "Tutor"), ("Professor", "Professor"), ("Programmer", "Code"), ("Robotics", "Robotics"),
             ("Literature & Writing", "Writing")]


# ---------------------------------------------------------------------------
# Owl shape - the "Faceted" line-art owl (120x120 design grid)
# ---------------------------------------------------------------------------

import math

OWL_HEAD = [(28, 26), (48, 40), (72, 40), (92, 26), (92, 76), (60, 106), (28, 76)]


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except OSError:
        pass


def friendly_source(rel):
    """'Chats/2026-09-26_215600.md' -> 'our chat on Sep 26'."""
    if rel.startswith("Chats/"):
        try:
            d = datetime.datetime.strptime(rel[6:16], "%Y-%m-%d")
            return "our chat on " + d.strftime("%b %d").replace(" 0", " ")
        except ValueError:
            return "a past chat"
    if rel.startswith("Obsidian/"):
        return "Obsidian: " + obs.link_name(rel)
    return rel


def open_folder(path):
    if not os.path.splitext(path)[1]:
        os.makedirs(path, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ---------------------------------------------------------------------------
# The app
# ---------------------------------------------------------------------------


def _mix(a, b, t):
    """Blend two #rrggbb colors (t=0 -> a, t=1 -> b)."""
    a, b = a.lstrip("#"), b.lstrip("#")
    ca = [int(a[i:i + 2], 16) for i in (0, 2, 4)]
    cb = [int(b[i:i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ca, cb))

class ArchieApp:
    PANEL_SIZES = {"Small": (380, 500), "Medium": (460, 640),
                   "Large": (580, 780), "Extra large": (720, 940)}
    TEXT_SIZES = {"Small": 9, "Normal": 10, "Large": 12, "Extra large": 14}
    PANEL_MIN = (320, 380)
    SIZES = {"Tiny": 36, "Small": 46, "Medium": 56, "Large": 76}

    def __init__(self):
        self.cfg = load_config()
        if self.cfg.get("hotkey_mic") == "ctrl+alt+m":   # the mic key moved to Alt+M
            self.cfg["hotkey_mic"] = "alt+m"
        try:                       # one context size for every request, so the model is never reloaded mid-use
            import archie_brain as _ab
            _ab.DEFAULT_CTX = int(self.cfg.get("context_tokens", 16384))
        except Exception:
            pass
        self.history = []          # [{"role", "content", optional "images"}]
        self.attachments = []      # file paths waiting to go with the next message
        self.keep = {}             # path -> True if it should also be saved to Notes
        self.busy = False
        self.q = None              # events for the answer in progress
        self.bg_q = queue.Queue()  # events from background notes indexing
        self.stop_evt = None
        self.reply_buf = ""
        self.sources = []
        self.panel_moved_by_hand = False
        self._blink_on = False
        if not self.cfg.get("obsidian_vault"):
            found = obs.find_default_vault()
            if found:
                self.cfg["obsidian_vault"] = found
                save_config(self.cfg)
        self.notes = NotesIndex(NOTES_DIR, NOTES_INDEX, self._search_folders())
        self.chat_meta = None      # the saved record for this conversation
        self.history_win = None
        self.book_ctx = None       # the book chapter we're working on in this chat
        if not os.path.exists(ABOUT_PATH):
            try:
                with open(ABOUT_PATH, "w", encoding="utf-8") as f:
                    f.write(ABOUT_STARTER)
            except OSError:
                pass
        self.model_names = load_model_names(MODEL_NAMES_PATH)
        self.wiki = WikiLibrary(WIKI_DIR)
        self.library = books.Library(NOTES_DIR, read_text)
        self.study = study.Study(STUDY_DIR)
        self.exams = exam.ExamStore(os.path.join(STUDY_DIR, "Exams"))
        try:   # the command cheat sheet as a deck ("study Archie commands"); new commands get added
            d = self.study.load("Archie commands")
            if not d or d.get("seeded", 0) < len(COMMAND_CARDS):
                self.study.add_cards("Archie commands", [{"q": q, "a": a} for q, a in COMMAND_CARDS],
                                     source="Archie manual")
                d = self.study.load("Archie commands")
                d["seeded"] = len(COMMAND_CARDS)
                self.study.save(d)
        except Exception:
            pass
        self.apps = apps.Apps()
        self.imager = imagine.ImageMaker(lambda ev: self.bg_q.put(("img", ev)))
        self.img_win = None
        threading.Thread(target=lambda: self.apps.apps(), daemon=True).start()   # warm up the app list
        self.obs_api = obs.LocalApi(self.vault)
        self._brief_parts = None
        self._brief_jobs = {}
        self.recorder = Recorder(RECORDINGS_DIR)
        self.transcriber = None
        self.bg_transcriber = None
        self._fg_transcribing = False
        os.makedirs(os.path.join(NOTES_DIR, "Audiobooks"), exist_ok=True)
        os.makedirs(os.path.join(NOTES_DIR, "Voice inbox"), exist_ok=True)
        os.makedirs(os.path.join(NOTES_DIR, "Lectures"), exist_ok=True)
        self.listener = Listener(NOTES_DIR, self.vault, LISTEN_STATE, self._bg_transcriber,
                                 lambda k, v: self.bg_q.put((k, v)), self._listen_busy,
                                 tidy=lambda t, idea=False: (self._idea_tidy(t) if idea else
                                                             voice_tidy(quick_chat, self.cfg["model"], t)),
                                 want_tidy=lambda: self.cfg.get("phone_tidy", True),
                                 paused=lambda: bool(self.cfg.get("audiobooks_paused")),
                                 lecture=self._lecture_note, hint=self._lecture_hint)
        self.reviewer = None
        try:                      # the lecture review: professor's material lined up with your recording
            self.reviewer = review.Reviewer(
                lambda: (self.vault() if self.vault() and os.path.isdir(self.vault()) else NOTES_DIR),
                quick_chat, lambda: self.cfg["model"],
                os.path.join(APP_DIR, "review_cache.json"), os.path.join(APP_DIR, "review_state.json"),
                vision=self._review_vision, transcribe=self._review_transcribe,
                wait=self._review_wait, report=lambda k, v: self.bg_q.put((k, v))).start()
        except Exception:
            self.reviewer = None
        threading.Thread(target=self._newsroll_loop, daemon=True, name="news-roll").start()
        self.updater = None
        try:                      # once a day, at the first quiet stretch: Ollama, every model, then a health check
            self.updater = autoupdate.AutoUpdate(
                APP_DIR, OLLAMA_URL, lambda: self.cfg["model"],
                busy=lambda: bool(self._listen_busy() or any(getattr(x, "working", False) for x in
                                  (getattr(self, "reviewer", None), getattr(self, "examprep", None)))),
                report=lambda m: self.bg_q.put(("status", m))).start()
        except Exception:
            self.updater = None
        self.housekeep = None
        try:                      # once a day when it's quiet: back up your stuff, keep the Backups folder tidy
            self.housekeep = housekeep.Housekeep(
                APP_DIR, lambda: self.vault(),
                quiet=lambda: bool(self.updater and self.updater.quiet() and not self.updater.working),
                report=lambda m: self.bg_q.put(("status", m))).start()
        except Exception:
            self.housekeep = None
        self.examprep = None
        try:                      # flashcards from every lecture, and a study guide before every exam
            self.examprep = examprep.ExamPrep(
                lambda: (self.vault() if self.vault() and os.path.isdir(self.vault()) else NOTES_DIR),
                lambda: self.calendar, quick_chat, lambda: self.cfg["model"], self.study, self.exams,
                os.path.join(APP_DIR, "examprep_state.json"), wait=self._review_wait,
                report=lambda k, v: self.bg_q.put((k, v))).start()
        except Exception:
            self.examprep = None
        self.speaker = None
        self._rec_kind = "note"
        self._talk_pending = False
        self._speak_now = False
        self.voice_wins = []
        os.makedirs(os.path.join(NOTES_DIR, "Handwritten"), exist_ok=True)
        self.scanner = HandwritingReader(NOTES_DIR, lambda k, v: self.bg_q.put((k, v)),
                                         lambda: self.busy, lambda: self.cfg.get("ocr_model"),
                                         lambda: self.vault())
        if self.vault():
            try:   # where photos / scans of paper notes go inside Obsidian
                os.makedirs(os.path.join(self.vault(), "Handwritten"), exist_ok=True)
            except OSError:
                pass
        self.tasks = Tasks(TASKS_PATH)
        self.deadlines = Deadlines(DEADLINES_PATH)
        self.daily = DailyNote(self.vault, self.tasks, self.deadlines)
        self.calendar = cal.Calendar(CALENDAR_PATH)
        self.quiet = talk.Quiet(lambda: self.cfg, self.calendar, int(self.cfg.get("lecture_minutes") or 75)) if talk else None
        self.talk_win = None
        self.handsfree = None
        self.caption_pop = None
        self.voice_settings_win = None
        self._talk_mode_send = False
        self._talk_last = None
        self._spoke_at = 0.0
        try:                      # keep the main brain loaded around classes and while you're using Archie
            self.warm = warm.Warm(OLLAMA_URL, lambda: self.cfg["model"], self.calendar,
                                  lambda: bool(getattr(self, "busy", False) or
                                               getattr(getattr(self, "recorder", None), "recording", False))).start()
        except Exception:
            self.warm = None
        try:                      # all-day running: game mode, cool down while you're away, a fresh start each morning
            self.cool = cool.Cool(OLLAMA_URL,
                                  in_class=lambda: bool(self.warm and self.warm.in_class_window()),
                                  busy=lambda: bool(getattr(self, "busy", False)
                                                    or getattr(getattr(self, "recorder", None), "recording", False)
                                                    or cool.STATE.get("talk")),
                                  report=lambda m: self.bg_q.put(("status", m))).start()
        except Exception:
            self.cool = None
        try:                      # Archie Inbox: drop, paste or "Send to Archie" -> a card that files it
            self.inbox = inboxm.Inbox(APP_DIR, lambda: self.vault(), self.calendar)
        except Exception:
            self.inbox = None
        self.inbox_types = inboxm.TYPES
        self.focus = focusmod.FocusTimer(os.path.join(APP_DIR, "focus_state.json"),
                                         os.path.join(STUDY_DIR, "focus_log.jsonl"))
        self._focus_view = "focus"
        self._mini = False
        self.recap = recapmod.RecapStore(os.path.join(APP_DIR, "Recaps"))
        self.world = None
        if world and self.cfg.get("world", True):
            try:
                self.world = world.WorldService(
                    get_model=lambda: self.cfg["model"], vault=self.vault, wiki=self.wiki,
                    add_calendar=lambda title, day, tm, notes: self.calendar.add(title, day, "event", tm, notes))
                self.world.start()
            except Exception as e:      # e.g. the port is taken: say so when asked, carry on
                self.world = None
                self._world_err = str(e)
        self.sync = None
        try:   # 2026-11-08: Archie Lite on the laptop syncs through this (home network, paired laptop only)
            import archie_sync
            self.sync = archie_sync.SyncService(self).start()
        except Exception as e:
            self._sync_err = str(e)
        self.mail_cards = []
        try:   # 2026-11-09: Gmail (Outlook forwards into it) -> cards for school mail, attachments and dates; read-only
            def _push(title, body, m):        # the phone: tapping it opens Archie (the Gmail app has its own)
                ph = getattr(self.sync, "phone", None) if self.sync else None
                if ph:
                    ph.push(title, body, "today", f"mail:{m.get('uid')}")
            self.mail = mailm.Mail(APP_DIR, on_card=self.mail_cards.append, push=_push).start()
        except Exception:
            self.mail = None
        os.makedirs(GYM_DIR, exist_ok=True)
        os.makedirs(MEMORY_DIR, exist_ok=True)
        old_gym = os.path.join(STUDY_DIR, "gym_log.json")        # 3.4 kept it with the flashcards: move it
        if os.path.exists(old_gym) and not os.path.exists(os.path.join(MEMORY_DIR, "gym_log.json")):
            try:
                os.replace(old_gym, os.path.join(MEMORY_DIR, "gym_log.json"))
            except OSError:
                pass
        self.gym = gym.Gym(GYM_DIR, os.path.join(MEMORY_DIR, "gym_log.json"), self._gym_vision, OLLAMA_URL,
                           busy=self._listen_busy)
        self._gs = None
        self.leftoff = mem.LeftOff(os.path.join(MEMORY_DIR, "left_off.json"))
        self.thisweek = mem.ThisWeek(os.path.join(MEMORY_DIR, "this_week.json"))
        self._recap_state = "idle"
        self._recap_data = None
        self.daily.coming_up = lambda: self._cal_lines_md()
        self.brief_state = BriefState(BRIEF_STATE_PATH)
        self._brief_n = 0
        self.modes = load_modes(MODES_DIR, DEFAULT_MODES)
        if self.cfg.get("mode") not in self.modes:
            self.cfg["mode"] = next(iter(self.modes))

        th.load_private_fonts(FONTS_DIR)
        self.root = TkinterDnD.Tk() if TkinterDnD else tk.Tk()
        self.root.title("Archie")
        global FONT, FONT_SEMI, MONO
        FONT, FONT_SEMI, MONO = th.pick_fonts(self.root)
        for opt, val in (("*Menu.background", SURFACE), ("*Menu.foreground", TEXT),
                         ("*Menu.activeBackground", BORDER), ("*Menu.activeForeground", ACCENT),
                         ("*Menu.selectColor", ACCENT), ("*Menu.relief", "flat"),
                         ("*Menu.borderWidth", 1), ("*Menu.activeBorderWidth", 0),
                         ("*Menu.font", f"{{{FONT}}} 9")):
            self.root.option_add(opt, val)
        self.imgs = {}             # keep drawn images alive
        self.spans = []            # left bars next to answers / the brief
        self.bubbles = []          # your message bubbles
        self._bars_pending = False
        try:
            self._icon = tk.PhotoImage(file=os.path.join(APP_DIR, "archie.png"))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            pass
        # Scale pixel sizes for high-DPI screens (e.g. the Surface's 200% display)
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)

        self.snipping = False
        self._build_bubble()
        self._build_panel()
        self.panel.withdraw()
        self.hotkeys = GlobalHotkeys({"chat": self.cfg.get("hotkey_chat"),
                                      "snip": self.cfg.get("hotkey_snip"),
                                      "voice": self.cfg.get("hotkey_voice"),
                                      "talk": self.cfg.get("hotkey_talk"),
                                      "recap": self.cfg.get("hotkey_recap"),
                                      "quiet": self.cfg.get("hotkey_quiet"),
                                      "mic": self.cfg.get("hotkey_mic") or "alt+m"}, self.bg_q.put)
        self.hotkeys.start()
        if self.cfg.get("brief_daily", True) and not self.brief_state.shown_today():
            self.root.after(900, self._auto_brief)
        self.root.after(30, self._poll)
        self.root.after(3000, self._inbox_poll)
        self.root.after(8000, self._scan_tick)
        self.root.after(2500, self._daily_tick)
        self.root.after(600, self._focus_tick)
        if talk:
            self.root.after(4000, self._quiet_tick)
            if self._new_voice_ok():      # load the voice early, so the first answer starts talking at once
                self.root.after(6000, lambda: self._get_speaker(quiet=True))
        if getattr(self, "banner", None) is not None:
            self.root.after(1500, self._banner_schedule)
            self.root.after(3000, self._banner_watch)
        if self.cfg.get("use_notes"):
            self.refresh_notes_in_background(quiet=True)

    @property
    def PANEL_W(self):
        return int(self.cfg.get("panel_w") or self.PANEL_SIZES["Medium"][0])

    @property
    def PANEL_H(self):
        return int(self.cfg.get("panel_h") or self.PANEL_SIZES["Medium"][1])

    @property
    def BUBBLE(self):
        return self.SIZES.get(self.cfg.get("owl_size"), 56)

    def px(self, n):
        return int(round(n * self.scale))

    # ----- the floating owl bubble -----------------------------------------

    def _build_bubble(self):
        r = self.root
        size = self.px(self.BUBBLE)
        r.overrideredirect(True)          # no title bar / borders
        r.attributes("-topmost", True)    # stay above other windows
        try:
            r.attributes("-transparentcolor", TRANSPARENT_KEY)  # Windows only
            bg = TRANSPARENT_KEY
        except tk.TclError:
            bg = BG
        r.configure(bg=bg)

        self.canvas = tk.Canvas(r, width=size, height=size, bg=bg,
                                highlightthickness=0, bd=0, cursor="hand2")
        self.canvas.pack()
        self._draw_owl()

        sw, sh = r.winfo_screenwidth(), r.winfo_screenheight()
        x = self.cfg.get("bubble_x")
        y = self.cfg.get("bubble_y")
        if x is None or y is None or not (0 <= x < sw - 20 and 0 <= y < sh - 20):
            x, y = sw - size - self.px(40), sh - size - self.px(110)
        r.geometry(f"{size}x{size}+{x}+{y}")

        c = self.canvas
        c.bind("<ButtonPress-1>", self._bubble_press)
        c.bind("<B1-Motion>", self._bubble_drag)
        c.bind("<ButtonRelease-1>", self._bubble_release)
        c.bind("<Button-3>", self._bubble_menu)

        self.menu = tk.Menu(r, tearoff=0)
        self.menu.add_command(label=f"Open / hide chat  ({pretty_combo(self.cfg.get('hotkey_chat') or '')})",
                              command=self.toggle_panel)
        self.menu.add_command(label="New conversation", command=self.new_conversation)
        self.menu.add_separator()
        self.menu.add_command(label=f"Snip screen  ({pretty_combo(self.cfg.get('hotkey_snip') or '')})",
                              command=self.start_snip)
        self.menu.add_command(label=f"Record a voice note  ({pretty_combo(self.cfg.get('hotkey_voice') or '')})",
                              command=self.toggle_record)
        self.menu.add_command(label=f"Talk to Archie  ({pretty_combo(self.cfg.get('hotkey_talk') or '')})",
                              command=self.toggle_talk)
        self.menu.add_command(label="Stop talking", command=self.stop_speaking)
        self.voice_menu = tk.Menu(self.menu, tearoff=0, postcommand=lambda: self._fill_voice_menu())
        self.voice_choice = tk.StringVar(value=self.cfg.get("speech_voice") or DEFAULT_VOICE)
        self.speed_choice = tk.StringVar(value=str(self.cfg.get("speech_speed") or 1.0))
        self.menu.add_cascade(label="Archie's voice", menu=self.voice_menu)
        if talk:
            self.menu.add_command(label=f"Mute / unmute  ({pretty_combo(self.cfg.get('hotkey_quiet') or '')})",
                                  command=self.toggle_quiet)
            self.menu.add_command(label=f"Mic off / on in talk  ({pretty_combo(self.cfg.get('hotkey_mic') or 'alt+m')})",
                                  command=self.toggle_mic)
            self.menu.add_command(label="Voice & quiet settings...", command=lambda: self.open_voice_settings())
        self.menu.add_command(label="Study flashcards", command=lambda: self.show_study(None))
        self._study_menu_index = self.menu.index("end")
        self.menu.configure(postcommand=self._refresh_menu_labels)
        self.menu.add_command(label="Calendar", command=lambda: self.show_calendar())
        self.menu.add_command(label="Focus timer (the owl)", command=lambda: self.show_focus())
        self.menu.add_command(label="Drawing gym", command=lambda: self.show_gym())
        self.menu.add_command(label="This week (what I keep in mind)", command=lambda: self.show_week())
        self.menu.add_command(label="Patterns", command=lambda: self.show_patterns())
        self.menu.add_command(label="Archie World (the globe)", command=lambda: self.show_world())
        self.menu.add_command(label="Workshop (code with Archie)", command=lambda: self.show_workshop())
        self.menu.add_command(label="Vault (the offline library)", command=lambda: self.show_vault())
        lec_menu = tk.Menu(self.menu, tearoff=0)
        self.lecture_wake_var = tk.BooleanVar(value=bool(self.cfg.get("lecture_wake")))
        self.lecture_sleep_var = tk.BooleanVar(value=bool(self.cfg.get("lecture_sleep_after", True)))
        lec_menu.add_command(label="Open lecture notes", command=self._open_lectures)
        lec_menu.add_command(label="Your classes (calendar)", command=lambda: self.show_calendar())
        lec_menu.add_separator()
        lec_menu.add_checkbutton(label="Wake the PC after class", variable=self.lecture_wake_var,
                                 command=lambda: self._lecture_wake_toggle(self.lecture_wake_var.get()))
        lec_menu.add_checkbutton(label="Sleep again when the note is done", variable=self.lecture_sleep_var,
                                 command=lambda: (self.cfg.update(lecture_sleep_after=bool(self.lecture_sleep_var.get())),
                                                  save_config(self.cfg)))
        self.menu.add_cascade(label="Lectures", menu=lec_menu)
        self.menu.add_command(label=f"Evening recap  ({pretty_combo(self.cfg.get('hotkey_recap') or '')})",
                              command=lambda: self.hotkey_recap())
        self.menu.add_command(label="Make an image...", command=lambda: self.show_imagine())
        self.menu.add_command(label="Sketch to image...", command=lambda: self.show_sketch())
        self.banner_var = tk.BooleanVar(value=bool(self.cfg.get("banner", True)))
        self.menu.add_checkbutton(label="Header pictures", variable=self.banner_var,
                                  command=lambda: self._banner_toggle(self.banner_var.get()))
        self.menu.add_command(label="Morning brief", command=self.show_brief)
        self.menu.add_command(label="Edit to-do list", command=lambda: open_folder(TASKS_PATH))
        self.menu.add_command(label="Edit deadlines", command=lambda: open_folder(DEADLINES_PATH))
        self.menu.add_command(label="Chat history...", command=self.show_history)
        self.menu.add_command(label="Save this chat to Obsidian", command=self.save_chat_to_obsidian)
        self.menu.add_command(label="Build an Obsidian wiki from this chat...", command=self.build_wiki)
        self.menu.add_command(label="Choose Obsidian vault...", command=self.choose_vault)
        self.menu.add_command(label="Edit About me", command=lambda: open_folder(ABOUT_PATH))
        self.menu.add_command(label="Open Modes folder", command=lambda: open_folder(MODES_DIR))
        self.menu.add_command(label="Edit model names", command=lambda: open_folder(MODEL_NAMES_PATH))
        self.menu.add_command(label="Open Notes folder", command=lambda: open_folder(NOTES_DIR))
        self.menu.add_command(label="Open the manual", command=self.open_manual)
        self.menu.add_command(label="Open Recordings folder", command=lambda: open_folder(RECORDINGS_DIR))
        self.menu.add_command(label="Open Audiobooks folder",
                              command=lambda: open_folder(os.path.join(NOTES_DIR, "Audiobooks")))
        self.ab_pause_var = tk.BooleanVar(value=bool(self.cfg.get("audiobooks_paused")))
        self.menu.add_checkbutton(label="Pause audiobooks", variable=self.ab_pause_var,
                                  command=self._toggle_audiobooks)
        self.menu.add_command(label="Re-read notes now", command=self._reread_notes)
        size_menu = tk.Menu(self.menu, tearoff=0)
        self.size_var = tk.StringVar(value=self.cfg.get("owl_size", "Medium"))
        for name in self.SIZES:
            size_menu.add_radiobutton(label=name, variable=self.size_var, value=name,
                                      command=lambda n=name: self.set_owl_size(n))
        self.menu.add_cascade(label="Owl size", menu=size_menu)
        chat_menu = tk.Menu(self.menu, tearoff=0)
        for name in self.PANEL_SIZES:
            chat_menu.add_command(label=name, command=lambda n=name: self.set_panel_size(*self.PANEL_SIZES[n]))
        chat_menu.add_separator()
        chat_menu.add_command(label="Tip: drag the chat's bottom-right corner", state="disabled")
        self.menu.add_cascade(label="Chat size", menu=chat_menu)
        text_menu = tk.Menu(self.menu, tearoff=0)
        self.text_size_var = tk.StringVar(value=self.cfg.get("text_size", "Normal"))
        for name in self.TEXT_SIZES:
            text_menu.add_radiobutton(label=name, variable=self.text_size_var, value=name,
                                      command=lambda n=name: self.set_text_size(n))
        self.menu.add_cascade(label="Text size", menu=text_menu)
        self.save_drops_var = tk.BooleanVar(value=bool(self.cfg.get("save_drops_to_notes", True)))
        self.menu.add_checkbutton(label="Save dropped files to Notes", variable=self.save_drops_var,
                                  command=self._toggle_save_drops)
        self.daily_var = tk.BooleanVar(value=bool(self.cfg.get("daily_note", True)))
        self.menu.add_checkbutton(label="To-dos in Obsidian daily note", variable=self.daily_var,
                                  command=self._toggle_daily)
        self.menu.add_command(label="Open today's daily note", command=self.open_daily)
        self.handwriting_var = tk.BooleanVar(value=bool(self.cfg.get("read_handwriting", True)))
        self.menu.add_checkbutton(label="Read photos of notes automatically", variable=self.handwriting_var,
                                  command=self._toggle_handwriting)
        self.brief_daily_var = tk.BooleanVar(value=bool(self.cfg.get("brief_daily", True)))
        self.menu.add_checkbutton(label="Show the brief each morning", variable=self.brief_daily_var,
                                  command=self._toggle_brief_daily)
        self.startup_var = tk.BooleanVar(value=starts_with_windows())
        self.menu.add_checkbutton(label="Start Archie with Windows", variable=self.startup_var,
                                  command=self._toggle_startup)
        self.menu.add_separator()
        self.menu.add_command(label="Quit Archie", command=self.quit)

    def _draw_owl(self):
        """The Faceted owl from the chat window's corner: lime lines on a dark
        head, hexagon eyes, a little beak. Drawn smooth with Pillow; the dark
        fill keeps it readable on any wallpaper and easy to grab. While Archie
        is thinking, the eyes blink."""
        c = self.canvas
        size = self.px(self.BUBBLE)
        key = c.cget("bg")
        try:
            self.imgs["owl_open"] = th.owl_keyed(size, key)
            self.imgs["owl_blink"] = th.owl_keyed(size, key, eyes="closed")
            c.create_image(size // 2, size // 2, image=self.imgs["owl_open"], tags=("owl",))
        except Exception:   # no Pillow: a simple lime outline so Archie still shows up
            k = size / 90.0
            pts = [v for x, y in OWL_HEAD for v in ((x - 15) * k, (y - 21) * k)]
            c.create_polygon(pts, fill=SURFACE, outline=ACCENT, width=max(1.5, 5 * k),
                             joinstyle="round", tags=("owl",))

    def _owl_eyes(self, which):
        if getattr(self, "_mini", False):
            return
        img = self.imgs.get("owl_blink" if which == "closed" else "owl_open")
        if img is not None:
            try:
                self.canvas.itemconfigure("owl", image=img)
            except tk.TclError:
                pass

    def set_owl_size(self, name):
        self._mini_exit()
        old = self.px(self.BUBBLE)
        self.cfg["owl_size"] = name
        save_config(self.cfg)
        size = self.px(self.BUBBLE)
        # keep the owl's bottom-right corner in the same spot
        x = self.root.winfo_x() + old - size
        y = self.root.winfo_y() + old - size
        self.canvas.configure(width=size, height=size)
        self.canvas.delete("all")
        self._draw_owl()
        self.root.geometry(f"{size}x{size}+{x}+{y}")
        if self.panel_visible() and not self.panel_moved_by_hand:
            self.root.update_idletasks()
            self.place_panel()

    def _bubble_press(self, e):
        self._drag = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._moved = False

    def _bubble_drag(self, e):
        sx, sy, wx, wy = self._drag
        dx, dy = e.x_root - sx, e.y_root - sy
        if abs(dx) + abs(dy) > 4:
            self._moved = True
        if self._moved:
            self.root.geometry(f"+{wx + dx}+{wy + dy}")
            if self.panel_visible() and not self.panel_moved_by_hand:
                self.place_panel()

    def _bubble_release(self, _e):
        if self._moved:
            self.cfg["bubble_x"], self.cfg["bubble_y"] = self._bubble_home()
            save_config(self.cfg)
        elif getattr(self, "_mini", False):
            self.show_focus()
        else:
            self.toggle_panel()

    def _bubble_menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    # ----- the chat panel ---------------------------------------------------

    # ----- the menu wheel: click ARCHIE, scroll to turn, click the green one to open it ----------------------
    # (name, menu label it opens, description, little tags)
    WHEEL = [("New chat", "New conversation", "Start fresh. This conversation is kept in your chat history.",
              ["new conversation"]),
             ("Study", "Study flashcards", "Flashcards with spaced repetition, one deck per class, plus your mock exams.",
              ["flashcards", "decks", "mock exams"]),
             ("Lectures", "Lectures", "Every class: lecture notes, reviews against the professor's slides, and exam prep.",
              ["notes", "reviews", "exam prep"]),
             ("Calendar", "Calendar", "Classes, exams, deadlines and everything else, synced to your phone and laptops.",
              ["this week", "classes", "exams"]),
             ("World", "Archie World (the globe)", "The globe: today's brief, live stories, governments, and the fighting by region.",
              ["brief", "globe", "governments"]),
             ("Workshop", "Workshop (code with Archie)", "Write code with Archie: projects, courses with real tests, and the offline docs.",
              ["courses", "projects"]),
             ("Vault", "Vault (the offline library)", "The offline library: Wikipedia, programming docs and Stack Exchange, no internet needed.",
              ["Wikipedia", "docs"]),
             ("Focus", "Focus timer (the owl)", "A focus timer on the owl. It blocks the distractions you pick until the time is up.",
              ["timer", "blocking"]),
             ("Create", "Make an image...", "Make an image from words, or turn a rough sketch into a picture.",
              ["make an image", "sketch to image"]),
             ("Brief", "Morning brief", "Your morning brief: today's classes, what's due, countdowns and the news.",
              ["classes", "due", "news"]),
             ("To-do", "Edit to-do list", "Your to-dos and deadlines, the same ones on every device.",
              ["to-do", "deadlines"]),
             ("History", "Chat history...", "Past conversations. Open one, keep going, or turn it into an Obsidian wiki.",
              ["chat history", "build a wiki"]),
             ("Voice", "Archie's voice", "How Archie sounds when it talks to you.",
              ["voice"]),
             ("Everything", None, "Every option in Archie's menu, all in one list.",
              ["full menu"])]

    # line icons on a 24-unit grid (same shapes as the mockup): ("l", x1,y1,x2,y2,...) polyline, ("o", x1,y1,x2,y2) circle,
    # ("r", x1,y1,x2,y2) box, ("a", x1,y1,x2,y2,start,extent) arc, ("p", ...) closed outline
    WHEEL_ICONS = {
        "New chat": [("l", 12, 5, 12, 19), ("l", 5, 12, 19, 12)],
        "Study": [("r", 4, 6, 16, 18), ("l", 8, 6, 8, 3, 20, 3, 20, 15, 16, 15)],
        "Lectures": [("l", 9, 6, 9, 12), ("l", 15, 6, 15, 12), ("a", 9, 3, 15, 9, 0, 180), ("a", 9, 9, 15, 15, 180, 180),
                     ("a", 5, 4, 19, 18, 180, 180), ("l", 12, 18, 12, 21)],
        "Calendar": [("r", 4, 6, 20, 20), ("l", 4, 10, 20, 10), ("l", 9, 3, 9, 7), ("l", 15, 3, 15, 7)],
        "World": [("o", 3, 3, 21, 21), ("l", 3, 12, 21, 12), ("o", 8, 3, 16, 21)],
        "Workshop": [("l", 8, 8, 3, 12, 8, 16), ("l", 16, 8, 21, 12, 16, 16), ("l", 14, 5, 10, 19)],
        "Vault": [("r", 4, 5, 10, 20), ("r", 10, 5, 14, 20), ("p", 15, 6, 19, 5, 21, 19, 17, 20)],
        "Focus": [("o", 4, 4, 20, 20), ("l", 12, 8, 12, 12, 15, 14)],
        "Create": [("r", 4, 4, 20, 20), ("l", 4, 17, 9, 12, 13, 16, 16, 13, 20, 17), ("o", 14, 7.5, 16.5, 10)],
        "Brief": [("a", 7, 12, 17, 22, 0, 180), ("l", 7, 17, 17, 17), ("l", 12, 3, 12, 5), ("l", 5.6, 5.6, 7, 7),
                  ("l", 3, 12, 5, 12), ("l", 19, 12, 21, 12), ("l", 17, 7, 18.4, 5.6)],
        "To-do": [("l", 9, 6, 20, 6), ("l", 9, 12, 20, 12), ("l", 9, 18, 20, 18),
                  ("o", 3.5, 5.5, 4.5, 6.5), ("o", 3.5, 11.5, 4.5, 12.5), ("o", 3.5, 17.5, 4.5, 18.5)],
        "History": [("a", 3, 3, 21, 21, 120, 300), ("l", 3, 3, 3, 8, 8, 8), ("l", 12, 8, 12, 12, 15, 14)],
        "Voice": [("p", 4, 9, 8, 9, 13, 5, 13, 19, 8, 15, 4, 15), ("a", 10, 8, 18, 16, -50, 100), ("a", 9, 5, 21, 19, -50, 100)],
        "Everything": [("r", 4, 4, 10, 10), ("r", 14, 4, 20, 10), ("r", 4, 14, 10, 20), ("r", 14, 14, 20, 20)],
    }

    def _wheel_icon(self, c, name, x, y, size, col, tags):
        s = size / 24.0
        w = max(1, round(self.px(2) * size / 24.0))
        for op in self.WHEEL_ICONS.get(name, []):
            k, v = op[0], op[1:]
            if k == "a":
                x1, y1, x2, y2, st, ex = v
                c.create_arc(x + (x1 - 12) * s, y + (y1 - 12) * s, x + (x2 - 12) * s, y + (y2 - 12) * s, start=st, extent=ex,
                             style="arc", outline=col, width=w, tags=tags)
                continue
            pts = [(x + (v[j] - 12) * s, y + (v[j + 1] - 12) * s) for j in range(0, len(v), 2)]
            flat = [q for p in pts for q in p]
            if k == "l":
                c.create_line(*flat, fill=col, width=w, capstyle="round", joinstyle="round", tags=tags)
            elif k == "p":
                c.create_polygon(*flat, fill="", outline=col, width=w, joinstyle="round", tags=tags)
            elif k == "o":
                c.create_oval(*flat, outline=col, width=w, tags=tags)
            elif k == "r":
                c.create_rectangle(*flat, outline=col, width=w, tags=tags)

    def _wheel_open(self):
        if getattr(self, "_wh", None):
            return self._wheel_close()
        p = self.panel
        p.update_idletasks()
        w, h = p.winfo_width(), p.winfo_height()
        items = []
        for name, label, desc, subs in self.WHEEL:
            idx = None
            if label:
                for i in range((self.menu.index("end") or 0) + 1):
                    try:
                        if self.menu.type(i) in ("command", "cascade") and self.menu.entrycget(i, "label") == label:
                            idx = i
                            break
                    except tk.TclError:
                        pass
                if idx is None:
                    continue
            items.append((name, idx, desc, subs))
        if not items:
            return
        top = tk.Toplevel(p)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        try:
            top.attributes("-alpha", 0.97)
        except tk.TclError:
            pass
        top.geometry(f"{w}x{h}+{p.winfo_rootx()}+{p.winfo_rooty()}")
        c = tk.Canvas(top, width=w, height=h, bg="#0a0a0a", highlightthickness=0, bd=0)
        c.pack(fill="both", expand=True)
        cx, cy = self.px(60), self.px(26)
        side = w >= h * 1.15                                  # wide window: the details sit on the right, else under the wheel
        R = min(self.px(330), int((w * 0.5 if side else min(w, h * 0.55)) * 0.78))
        for rr, dash, col in ((R, None, "#2b3311"), (int(R * 1.45), (3, 5), "#20260d"), (int(R * 0.6), None, "#1d1d1d")):
            c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline=col, dash=dash, width=1)
        c.create_line(cx, cy, cx + R * 1.1, cy + R * 1.1, fill="#1d2409", width=1)      # the 45° guide line
        self._wh = {"top": top, "c": c, "items": items, "sel": 1 if len(items) > 1 else 0, "pos": 0.0, "cx": cx, "cy": cy,
                    "R": R, "w": w, "h": h, "side": side, "anim": None, "grow": 0.0}
        c.bind("<MouseWheel>", lambda e: self._wheel_turn(-1 if e.delta > 0 else 1))
        c.bind("<Button-4>", lambda e: self._wheel_turn(-1))
        c.bind("<Button-5>", lambda e: self._wheel_turn(1))
        c.bind("<Button-1>", self._wheel_click)
        top.bind("<Escape>", lambda e: self._wheel_close())
        top.bind("<Return>", lambda e: self._wheel_go())
        top.bind("<Up>", lambda e: self._wheel_turn(-1))
        top.bind("<Down>", lambda e: self._wheel_turn(1))
        top.bind("<FocusOut>", lambda e: self.root.after(120, self._wheel_close_if_away))
        top.focus_force()
        self._wheel_step()

    def _wheel_close_if_away(self):
        wh = getattr(self, "_wh", None)
        if wh and wh["top"].focus_displayof() is None:
            self._wheel_close()

    def _wheel_close(self):
        wh = getattr(self, "_wh", None)
        if not wh:
            return
        wh["closing"] = True               # collapse back into the corner, then go
        if not wh["anim"]:
            self._wheel_step()

    def _wheel_turn(self, d):
        wh = getattr(self, "_wh", None)
        if wh and not wh.get("closing"):
            wh["sel"] = (wh["sel"] + d) % len(wh["items"])
            if not wh["anim"]:
                self._wheel_step()

    def _wheel_click(self, e):
        wh = getattr(self, "_wh", None)
        if not wh or wh.get("closing"):
            return
        hit = wh["c"].find_overlapping(e.x - 3, e.y - 3, e.x + 3, e.y + 3)
        for item in reversed(hit):
            for t in wh["c"].gettags(item):
                if t.startswith("wi") and t[2:].isdigit():   # one option ("wi" alone is the shared tag)
                    i = int(t[2:])
                    if i == wh["sel"]:
                        return self._wheel_go()
                    wh["sel"] = i
                    if not wh["anim"]:
                        self._wheel_step()
                    return
                if t == "wpanel":
                    return                          # a click on the details text: do nothing
        self._wheel_close()                         # clicked outside the options: fold it away

    def _wheel_go(self):
        wh = getattr(self, "_wh", None)
        if not wh or wh.get("closing"):
            return
        name, idx = wh["items"][wh["sel"]][:2]
        x, y = wh["top"].winfo_rootx() + self.px(80), wh["top"].winfo_rooty() + self.px(60)
        self._wheel_close()

        def run():
            try:
                if idx is None:
                    self.menu.tk_popup(x, y)
                elif self.menu.type(idx) == "cascade":
                    self.root.nametowidget(self.menu.entrycget(idx, "menu")).tk_popup(x, y)
                else:
                    self.menu.invoke(idx)
            except tk.TclError:
                pass
        self.root.after(260, run)

    def _wheel_step(self):
        import math
        wh = getattr(self, "_wh", None)
        if not wh:
            return
        n, c, px = len(wh["items"]), wh["c"], self.px
        target = wh["sel"]
        d = target - wh["pos"]
        if d > n / 2:
            d -= n
        if d < -n / 2:
            d += n
        wh["pos"] = (wh["pos"] + d * 0.28) % n
        g = wh["grow"] + ((0.0 if wh.get("closing") else 1.0) - wh["grow"]) * 0.3
        wh["grow"] = g
        c.delete("wi")
        R = wh["R"] * (0.25 + 0.75 * g)
        for i, (name, _, _, _) in enumerate(wh["items"]):
            off = i - wh["pos"]
            if off > n / 2:
                off -= n
            if off < -n / 2:
                off += n
            a = abs(off)
            if a > 3.6:
                continue
            ang = math.radians(45 + off * 15 * g - (1 - g) * 40)
            x, y = wh["cx"] + R * math.cos(ang), wh["cy"] + R * math.sin(ang)
            on = a < 0.5
            rad = px(27 if on else 22) * (0.4 + 0.6 * g)
            shade = max(0.25, 1 - a * 0.24) * g
            mix = lambda h1: "#%02x%02x%02x" % tuple(int(int(h1[k:k + 2], 16) * shade + 10 * (1 - shade)) for k in (1, 3, 5))
            tags = ("wi", f"wi{i}")
            if on:                                  # the chosen one: lime circle with a soft halo
                for gr, col in ((px(13), "#141a07"), (px(7), "#1d2409")):
                    c.create_oval(x - rad - gr, y - rad - gr, x + rad + gr, y + rad + gr, fill=col, outline="", tags=tags)
            c.create_oval(x - rad, y - rad, x + rad, y + rad, fill="#c6f432" if on else "#141414",
                          outline="" if on else mix("#2e2e2e"), width=1, tags=tags)
            if g > 0.35:
                self._wheel_icon(c, name, x, y, rad * 0.95, "#0a0a0a" if on else mix("#c6f432"), tags)
            c.create_text(x + rad + px(12), y, text=name, anchor="w", fill=mix("#c6f432") if on else mix("#bdbdb7"),
                          font=(FONT, 15 if on else 11, "bold" if on else "normal"), tags=tags)
        # the details of the chosen option: number, big name, what it does, its tags
        if g > 0.6 and not wh.get("closing"):
            name, _, desc, subs = wh["items"][wh["sel"]]
            W, H = wh["w"], wh["h"]
            if wh["side"]:
                x0, y0, tw = int(W * 0.56), int(H * 0.2), int(W * 0.4)
            else:
                x0, y0, tw = px(26), int(wh["cy"] + wh["R"] * 1.08 + px(20)), W - px(52)
            pt = ("wi", "wpanel")
            c.create_text(x0, y0, anchor="nw", text=f"{wh['sel'] + 1:02d} / {n:02d}", fill="#c6f432",
                          font=(MONO, 9, "bold"), tags=pt)
            yy = y0 + px(22)
            t = c.create_text(x0, yy, anchor="nw", text=name, fill="#f2f2ec", font=(FONT, 24, "bold"), width=tw, tags=pt)
            yy = c.bbox(t)[3] + px(10)
            t = c.create_text(x0, yy, anchor="nw", text=desc, fill="#b9b9b3", font=(FONT, 11), width=tw, tags=pt)
            yy = c.bbox(t)[3] + px(14)
            xx = x0
            for s in subs:                         # little outlined tags, wrapping to a new row when full
                t = c.create_text(xx + px(12), yy + px(6), anchor="nw", text=s, fill="#c6f432", font=(MONO, 9), tags=pt)
                b = c.bbox(t)
                if b[2] + px(12) > x0 + tw and xx > x0:
                    c.delete(t)
                    xx, yy = x0, yy + px(34)
                    t = c.create_text(xx + px(12), yy + px(6), anchor="nw", text=s, fill="#c6f432", font=(MONO, 9), tags=pt)
                    b = c.bbox(t)
                r = (b[3] - b[1] + px(12)) / 2
                c.create_line(b[0] - px(12) + r, b[1] - px(6), b[2] + px(12) - r, b[1] - px(6), fill="#4d5e14", tags=pt)
                c.create_line(b[0] - px(12) + r, b[3] + px(6), b[2] + px(12) - r, b[3] + px(6), fill="#4d5e14", tags=pt)
                c.create_arc(b[0] - px(12), b[1] - px(6), b[0] - px(12) + 2 * r, b[3] + px(6), start=90, extent=180,
                             style="arc", outline="#4d5e14", tags=pt)
                c.create_arc(b[2] + px(12) - 2 * r, b[1] - px(6), b[2] + px(12), b[3] + px(6), start=-90, extent=180,
                             style="arc", outline="#4d5e14", tags=pt)
                xx = b[2] + px(12) + px(8)
            c.create_text(x0, yy + px(46), anchor="nw", fill="#6f6f6a", width=tw, font=(MONO, 8), tags=pt,
                          text="scroll to turn the wheel · click the green one to open · Esc closes")
        if wh.get("closing") and g < 0.05:
            wh["top"].destroy()
            self._wh = None
            return
        if abs(d) > 0.01 or abs((0.0 if wh.get("closing") else 1.0) - g) > 0.01:
            wh["anim"] = self.root.after(16, self._wheel_step)
        else:
            wh["anim"] = None
            wh["pos"] = float(target)

    def _build_panel(self):
        p = self.panel = tk.Toplevel(self.root)
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        p.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=BORDER)
        px = self.px

        # ---- header (drag it to move the panel):  owl ARCHIE (• model) ... ☀ ⟲ + ✕
        head = tk.Frame(p, bg=BG)
        head.pack(fill="x", padx=px(14), pady=(px(12), px(6)))
        try:
            self.imgs["head_owl"] = th.owl_photo(px(24))
            owl = tk.Label(head, image=self.imgs["head_owl"], bg=BG, bd=0)
        except Exception:
            owl = tk.Label(head, text="◆", fg=ACCENT, bg=BG)
        # (the owl icon was retired from the header: ARCHIE starts at the edge, the banner gets the room)
        title = tk.Label(head, text="ARCHIE", bg=BG, fg=TEXT, font=(MONO, 11, "bold"))
        title.pack(side="left", padx=(0, px(8)))
        self.head_title, self.head_owl = title, owl
        title.configure(cursor="hand2", text="ARCHIE ▾")
        self._chips_compact = False
        self._chip_w = {}
        head.bind("<Configure>", lambda e: self.root.after_idle(self._fit_header), add="+")
        self.chip = tk.Canvas(head, bg=BG, highlightthickness=0, bd=0, height=px(22),
                              width=px(80), cursor="hand2")
        self.chip.pack(side="left")
        self.chip.bind("<ButtonRelease-1>", lambda e: self._show_model_menu())
        self._tip(self.chip, "Change model")
        for w in (head, title, owl):
            w.bind("<ButtonPress-1>", self._panel_press)
            w.bind("<B1-Motion>", self._panel_drag)
        # ARCHIE opens the menu wheel on a click; dragging it still moves the window
        title.bind("<ButtonPress-1>", lambda e: setattr(self, "_title_down", (e.x_root, e.y_root)), add="+")
        title.bind("<ButtonRelease-1>", lambda e: self._wheel_open() if (
            abs(e.x_root - getattr(self, "_title_down", (-99, -99))[0]) + abs(e.y_root - getattr(self, "_title_down", (-99, -99))[1]) < 6
        ) else None)
        self.model_popup = tk.Menu(p, tearoff=0)
        self.model_choice = tk.StringVar(value=self.cfg["model"])

        for name, cmd, tip in (("close", self.hide_panel, "Hide (Esc)"),
                               ("plus", self.new_conversation, "New chat"),
                               ("history", self.show_history, "Chat history"),
                               ("brief", self.show_brief, "Morning brief")):
            b = self._icon_btn(head, name, cmd, tip)
            b.pack(side="right")
            self.head_icons = getattr(self, "head_icons", []) + [b]
        self.date_chip = tk.Canvas(head, bg=BG, highlightthickness=0, bd=0, height=px(22), width=px(70),
                                   cursor="hand2")
        self.date_chip.pack(side="left", padx=(px(6), 0))
        self.date_chip.bind("<ButtonRelease-1>", lambda e: self.show_calendar())
        self._tip(self.date_chip, "Calendar: exams, tests, labs, classes")
        self.focus_chip = tk.Canvas(head, bg=BG, highlightthickness=0, bd=0, height=px(22), width=px(56),
                                    cursor="hand2")
        self.focus_chip.pack(side="left", padx=(px(6), 0))
        self.focus_chip.bind("<ButtonRelease-1>", lambda e: self.show_focus())
        self._tip(self.focus_chip, "Focus timer (the owl)")
        self.recap_chip = tk.Canvas(head, bg=BG, highlightthickness=0, bd=0, height=px(22), width=px(64),
                                    cursor="hand2")
        self.recap_chip.pack(side="left", padx=(px(6), 0))
        self.recap_chip.bind("<ButtonRelease-1>", lambda e: self._recap_chip_click())
        self._tip(self.recap_chip, f"Evening recap: talk about your day ({pretty_combo(self.cfg.get('hotkey_recap') or '')})")

        # ---- mode tabs:  Tutor | Code | Robotics | Writing
        self.tabs = tk.Canvas(p, bg=BG, highlightthickness=0, bd=0, height=px(36), cursor="hand2")
        self.tabs.pack(fill="x", padx=px(14), pady=(px(2), px(8)))
        self.tabs.bind("<Configure>", lambda e: self._draw_tabs())
        self.tabs.bind("<ButtonRelease-1>", self._tab_click)
        self.tabs.bind("<Motion>", self._tab_hover)
        self.tabs.bind("<Leave>", lambda e: self._tab_hover(None))
        self.more_modes_menu = tk.Menu(p, tearoff=0)

        # ---- bottom bar, terminal style (packed FIRST so it can never be squeezed out)
        #   > ask archie ............................ [RUN]
        #   [+ attach] [snip] [notes ●] [wiki ○]      status
        bottom = tk.Frame(p, bg=BG)
        bottom.pack(side="bottom", fill="x")
        tk.Frame(bottom, bg=th.LINE, height=1).pack(fill="x")
        row = tk.Frame(bottom, bg=BG)
        row.pack(fill="x", padx=px(14), pady=(px(12), px(8)))
        tk.Label(row, text=">", bg=BG, fg=ACCENT, font=(MONO, 12)).pack(side="left", anchor="n",
                                                                       pady=(px(2), 0))
        self.send_btn = tk.Label(row, bg=BG, bd=0, cursor="hand2", compound="center",
                                 font=(MONO, 9, "bold"), fg=TILE)
        self.send_btn.pack(side="right", anchor="n", padx=(px(8), 0))
        self.send_btn.bind("<ButtonRelease-1>", lambda e: self.send_or_stop())
        self.send_btn.bind("<Enter>", lambda e: self._style_send_btn(hover=True))
        self.send_btn.bind("<Leave>", lambda e: self._style_send_btn())
        self.entry = tk.Text(row, height=1, bg=BG, fg=TEXT, insertbackground=ACCENT,
                             insertwidth=px(2), wrap="word", bd=0, padx=px(6), pady=px(4),
                             font=(MONO, 10), highlightthickness=0, selectbackground=ACCENT,
                             selectforeground=TILE)
        self.entry.pack(side="left", fill="both", expand=True)
        self.placeholder = tk.Label(self.entry, text="ask archie", bg=BG, fg="#55554f",
                                    font=(MONO, 10), bd=0, cursor="xterm")
        self.placeholder.bind("<Button-1>", lambda e: self.entry.focus_set())
        self.entry.bind("<Return>", self._on_enter)
        self.entry.bind("<Shift-Return>", lambda e: self.root.after_idle(self._entry_changed))
        self.entry.bind("<KeyRelease>", lambda e: self._entry_changed())
        self.entry.bind("<Configure>", lambda e: self._entry_changed())
        self.entry.bind("<<Paste>>", lambda e: self.root.after_idle(self._entry_changed))

        tools = tk.Frame(bottom, bg=BG)
        tools.pack(fill="x", padx=px(14), pady=(0, px(6)))
        self.attach_btn = self._term_btn(tools, "+ attach", self.pick_files)
        self.snip_btn = self._term_btn(tools, "snip", self.start_snip)
        self.notes_btn = self._term_btn(tools, "notes", self.toggle_notes)
        self.wiki_btn = self._term_btn(tools, "wiki", self.toggle_wiki)
        self.mic_btn = self._term_btn(tools, "mic", self.toggle_record)
        self._tip(self.mic_btn, f"Record a voice note ({pretty_combo(self.cfg.get('hotkey_voice') or '')}). "
                                "Click again to stop.")
        self.speak_btn = self._term_btn(tools, "speak", self.toggle_speak)
        self._tip(self.speak_btn, "Read answers out loud. Talk to Archie with "
                                  f"{pretty_combo(self.cfg.get('hotkey_talk') or '')}")
        self.help_btn = self._term_btn(tools, "help", self.show_help)
        self._tip(self.help_btn, "Everything Archie can do")
        self._tip(self.attach_btn, "Attach files (or drag them onto the chat)")
        self._tip(self.snip_btn, f"Snip the screen ({pretty_combo(self.cfg.get('hotkey_snip') or '')})")
        self._tip(self.notes_btn, "Search your Notes, past chats and Obsidian")
        self._tip(self.wiki_btn, "Look things up in offline Wikipedia")
        self.status = tk.Label(bottom, text="", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w")
        self.status.pack(fill="x", padx=(px(15), px(24)), pady=(0, px(8)))
        self._style_notes_btn()
        self._style_speak_btn()
        self.chips = tk.Frame(p, bg=BG, padx=px(14), pady=px(4))   # shown only when needed

        # ---- conversation
        self.body = tk.Frame(p, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.chat = tk.Text(self.body, bg=BG, fg=BODY, wrap="word", bd=0, padx=px(20), pady=px(6),
                            font=(FONT, 10), highlightthickness=0, cursor="arrow",
                            insertwidth=0, state="disabled", selectbackground=ACCENT,
                            selectforeground=TILE, inactiveselectbackground=BORDER)
        sb = th.SlimScrollbar(self.body, self.chat, width=px(8))
        sb.on_scroll = self._queue_bars
        self.chat.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", padx=(0, px(3)), pady=px(4))
        self.chat.pack(side="left", fill="both", expand=True)
        # the thin lime line beside Archie's answers lives in the chat's left margin
        self.bars = tk.Canvas(self.body, bg=BG, highlightthickness=0, bd=0, width=px(2))
        self.bars.place(in_=self.body, x=px(8), y=0, width=px(2), relheight=1.0)
        self.chat.bind("<Configure>", self._chat_resized)
        self.chat.bind("<1>", lambda e: self.chat.focus_set())   # select + copy answers

        p.bind("<Control-v>", self._inbox_paste, add="+")    # a screenshot or copied files -> inbox card
        # Drag-and-drop files onto the panel
        if TkinterDnD:
            for w in (p, self.chat, self.entry):
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self._on_drop)
                except Exception:
                    pass

        # Resize grip in the bottom-right corner
        self.grip = tk.Label(p, text="◢", bg=BG, fg="#3a3a3a", font=(FONT, 9),
                             cursor="size_nw_se" if sys.platform == "win32" else "bottom_right_corner")
        self.grip.place(relx=1.0, rely=1.0, anchor="se", x=-px(2), y=-px(1))
        self.grip.bind("<ButtonPress-1>", self._grip_press)
        self.grip.bind("<B1-Motion>", self._grip_drag)
        self.grip.bind("<ButtonRelease-1>", self._grip_release)

        p.bind("<Escape>", lambda e: self.hide_panel())
        self._greeted = False
        self._rounded = None
        self.apply_text_size()
        self._style_send_btn()
        self._draw_chip()
        self._draw_date_chip()
        self._draw_focus_chip()
        self._draw_recap_chip()
        self._entry_changed()
        if banner is not None and Image is not None:
            self._build_banner()
            head.bind("<Configure>", lambda e: self.root.after_idle(self._banner_place), add="+")

    # ----- little building blocks for the panel -------------------------------

    def _tip(self, widget, text):
        """Small tooltip after hovering for a moment."""
        state = {"job": None, "win": None}

        def show():
            if state["win"] or not widget.winfo_viewable():
                return
            t = tk.Toplevel(widget)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            tk.Label(t, text=text, bg=SURFACE, fg=TEXT, font=(MONO, 8), padx=8, pady=4,
                     highlightthickness=1, highlightbackground=BORDER).pack()
            t.geometry(f"+{widget.winfo_rootx()}+{widget.winfo_rooty() + widget.winfo_height() + 4}")
            state["win"] = t

        def enter(_e):
            state["job"] = widget.after(600, show)

        def leave(_e):
            if state["job"]:
                widget.after_cancel(state["job"])
                state["job"] = None
            if state["win"]:
                state["win"].destroy()
                state["win"] = None
        widget.bind("<Enter>", enter, add="+")
        widget.bind("<Leave>", leave, add="+")
        widget.bind("<ButtonPress>", leave, add="+")

    def _icon_btn(self, parent, name, command, tip):
        px = self.px
        try:
            normal = th.icon(name, px(17), MUTED, box=px(32))
            hover = th.icon(name, px(17), TEXT, box=px(32), hover_bg=INPUT_BG)
            b = tk.Label(parent, image=normal, bg=BG, bd=0, cursor="hand2")
            self.imgs[f"ico_{name}"] = (normal, hover)
            b.bind("<Enter>", lambda e: b.configure(image=hover), add="+")
            b.bind("<Leave>", lambda e: b.configure(image=normal), add="+")
        except Exception:
            b = tk.Label(parent, text={"close": "✕", "plus": "+", "history": "⟲",
                                       "brief": "☀"}[name], bg=BG, fg=MUTED,
                         font=(FONT, 11), padx=6, cursor="hand2")
        b.bind("<ButtonRelease-1>", lambda e: command())
        self._tip(b, tip)
        return b

    def _term_btn(self, parent, text, command):
        """Square little code-style button: [ + attach ]."""
        b = tk.Label(parent, text=text, bg=BG, fg=DIM, font=(MONO, 8), padx=self.px(8),
                     pady=self.px(3), bd=0, highlightthickness=1, highlightbackground=BORDER,
                     highlightcolor=BORDER, cursor="hand2", disabledforeground="#4a4a4a")
        b.pack(side="left", padx=(0, self.px(6)))
        b._on = False
        b.bind("<ButtonRelease-1>", lambda e: command() if str(b.cget("state")) != "disabled" else None)
        b.bind("<Enter>", lambda e: b.configure(fg=ACCENT_HI if b._on else TEXT), add="+")
        b.bind("<Leave>", lambda e: b.configure(fg=ACCENT if b._on else DIM), add="+")
        return b

    def _style_send_btn(self, hover=False):
        px = self.px
        label = "STOP" if self.busy else "RUN"
        key = f"send_{label}_{hover}"
        if key not in self.imgs:
            w = tkfont.Font(family=MONO, size=9, weight="bold").measure(label) + px(24)
            try:
                self.imgs[key] = th.rounded(w, px(30), px(4), ACCENT_HI if hover else ACCENT)
            except Exception:
                self.imgs[key] = None
        img = self.imgs[key]
        if img is not None:
            self.send_btn.configure(image=img, text=label)
        else:
            self.send_btn.configure(text=f" {label} ", bg=ACCENT, padx=px(8), pady=px(4))

    def _entry_changed(self):
        """Grow the input box with what you type (up to 6 lines) + placeholder."""
        e = self.entry
        empty = not e.get("1.0", "end-1c")
        if empty:
            self.placeholder.place(x=self.px(6), y=self.px(4))
        else:
            self.placeholder.place_forget()
        try:
            n = e.count("1.0", "end", "displaylines")
            n = n[0] if isinstance(n, tuple) else n
        except tk.TclError:
            n = 1
        want = max(1, min(6, int(n or 1)))
        if int(e.cget("height")) != want:
            e.configure(height=want)

    def _draw_chip(self):
        """The '• Main brain' pill in the header (click it to switch models)."""
        c, px = self.chip, self.px
        c.delete("all")
        text = self.nice(self.cfg["model"])
        if len(text) > 22:
            text = text[:20] + "…"
        if getattr(self, "_model_short", False) and " " in text:
            text = text.split()[0]
        f = (MONO, 8)
        tw = tkfont.Font(family=MONO, size=8).measure(text)
        h = px(22)
        w = px(22) + tw + px(10)
        c.configure(width=w, height=h)
        try:
            self.imgs["chip"] = th.rounded(w, h, h // 2, BG, BORDER,
                                           dots=[(px(11), h / 2, px(3), ACCENT)])
            c.create_image(0, 0, anchor="nw", image=self.imgs["chip"])
        except Exception:
            c.create_oval(px(8), h / 2 - px(3), px(14), h / 2 + px(3), fill=ACCENT, width=0)
        c.create_text(px(20), h / 2, anchor="w", text=text, fill=MUTED, font=f)

    def _show_model_menu(self):
        self.refresh_models()
        self.model_popup.tk_popup(self.chip.winfo_rootx(),
                                  self.chip.winfo_rooty() + self.chip.winfo_height() + 4)

    def _tab_items(self):
        items = [(label, name) for name, label in MODE_TABS if name in self.modes]
        extra = [m for m in self.modes if m != "General" and m not in dict(MODE_TABS)]
        if extra:
            cur = self.cfg.get("mode")
            items.append((cur if cur in extra else "more ▾", "__more__"))
        return items, extra

    def _draw_tabs(self, hover=None):
        c, px = self.tabs, self.px
        W, H = c.winfo_width(), int(c.cget("height"))
        if W < 20:
            return
        c.delete("all")
        items, extra = self._tab_items()
        if not items:
            return
        cur = self.cfg.get("mode")
        pad, gap = px(4), px(4)
        n = len(items)
        tw = (W - 2 * pad - (n - 1) * gap) / n
        try:
            key = ("tabbar", W, H)
            if self.imgs.get("tabbar_key") != key:
                self.imgs["tabbar"] = th.rounded(W, H, px(12), SURFACE, BORDER)
                self.imgs["tabbar_key"] = key
            c.create_image(0, 0, anchor="nw", image=self.imgs["tabbar"])
        except Exception:
            c.create_rectangle(0, 0, W - 1, H - 1, fill=SURFACE, outline=BORDER)
        self._tab_boxes = []
        font = tkfont.Font(family=FONT, size=9)
        for i, (label, name) in enumerate(items):
            x0 = pad + i * (tw + gap)
            x1, y0, y1 = x0 + tw, pad, H - pad
            sel = name == cur or (name == "__more__" and cur in extra)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            if sel:
                tw_text = font.measure(label)
                dot_x = (tw - tw_text) / 2 - px(5)
                try:
                    k = ("tabsel", int(tw), int(y1 - y0), int(dot_x))
                    if self.imgs.get("tabsel_key") != k:
                        self.imgs["tabsel"] = th.rounded(tw, y1 - y0, px(8), BORDER, bg=SURFACE,
                                                         dots=[(dot_x, (y1 - y0) / 2, px(2.5), ACCENT)])
                        self.imgs["tabsel_key"] = k
                    c.create_image(x0, y0, anchor="nw", image=self.imgs["tabsel"])
                except Exception:
                    c.create_rectangle(x0, y0, x1, y1, fill=BORDER, width=0)
                cx += px(5)
            color = TEXT if sel or hover == i else MUTED
            c.create_text(cx, cy, text=label, fill=color, font=(FONT, 9))
            self._tab_boxes.append((x0, x1, name))

    def _tab_at(self, x):
        for i, (x0, x1, name) in enumerate(getattr(self, "_tab_boxes", [])):
            if x0 <= x <= x1:
                return i, name
        return None, None

    def _tab_hover(self, e):
        i = None if e is None else self._tab_at(e.x)[0]
        if i != getattr(self, "_tab_hovered", None):
            self._tab_hovered = i
            self._draw_tabs(hover=i)

    def _tab_click(self, e):
        i, name = self._tab_at(e.x)
        if name is None:
            return
        if name == "__more__":
            m = self.more_modes_menu
            m.delete(0, "end")
            for mode in self._tab_items()[1]:
                m.add_command(label=mode, command=lambda n=mode: self.set_mode(n))
            m.tk_popup(e.x_root, e.y_root)
        elif name == self.cfg.get("mode") and "General" in self.modes:
            self.set_mode("General")     # click the lit tab again to go back to General
        else:
            self.set_mode(name)

    # ----- the conversation text ------------------------------------------------

    def _clear_chat(self):
        self.chat.configure(state="normal")
        self.chat.delete("1.0", "end")
        self.chat.configure(state="disabled")
        for b in self.bubbles:
            try:
                b.destroy()
            except tk.TclError:
                pass
        self.bubbles = []
        self.spans = []
        self._queue_bars()

    def _you(self, text):
        """Your message: a rounded bubble on the right."""
        t = self.chat
        t.configure(state="normal")
        if t.index("end-1c") != "1.0" and t.get("end-2c") != "\n":
            t.insert("end", "\n")
        bub = tk.Canvas(t, bg=BG, highlightthickness=0, bd=0, cursor="arrow")
        bub.text = text
        self.bubbles.append(bub)
        self._draw_bubble(bub)
        t.window_create("end", window=bub, align="top")
        t.insert("end", "\n")
        t.tag_add("ubub", "end-3c", "end-1c")
        t.configure(state="disabled")
        t.see("end")
        self._queue_bars()

    def _draw_bubble(self, bub):
        px = self.px
        s = self.TEXT_SIZES.get(self.cfg.get("text_size"), 10)
        width = self.chat.winfo_width()
        if width < 50:
            width = px(self.PANEL_W) - px(40)
        maxw = int(max(px(140), (width - 2 * px(20) - px(12)) * 0.78))
        padx, pady = px(14), px(9)
        bub.delete("all")
        tid = bub.create_text(padx, pady, anchor="nw", text=bub.text, fill=TEXT,
                              font=(FONT, s), width=maxw - 2 * padx)
        x0, y0, x1, y1 = bub.bbox(tid)
        w, h = (x1 - x0) + 2 * padx, (y1 - y0) + 2 * pady
        try:
            bub.img = th.rounded(w, h, (px(16), px(16), px(4), px(16)), INPUT_BG, BORDER)
            bub.create_image(0, 0, anchor="nw", image=bub.img)
            bub.tag_raise(tid)
        except Exception:
            bub.create_rectangle(0, 0, w - 1, h - 1, fill=INPUT_BG, outline=BORDER)
            bub.tag_raise(tid)
        bub.configure(width=w, height=h)

    def _chat_resized(self, e):
        if getattr(self, "_chat_w", None) != e.width:
            self._chat_w = e.width
            if getattr(self, "_rebubble_job", None):
                self.root.after_cancel(self._rebubble_job)
            self._rebubble_job = self.root.after(120, self._redraw_bubbles)
        self._queue_bars()

    def _redraw_bubbles(self):
        self._rebubble_job = None
        for b in self.bubbles:
            try:
                self._draw_bubble(b)
            except tk.TclError:
                pass
        self._queue_bars()

    def _start_span(self, color=None):
        """Begin a left bar (Archie's answer or the brief) at the end of the chat."""
        self._brief_n += 1
        m = f"span{self._brief_n}"
        self.chat.mark_set(m, "end-1c")
        self.chat.mark_gravity(m, "left")
        span = {"s": m, "e": None, "color": color or ACCENT}
        self.spans.append(span)
        return span

    def _end_span(self, span=None):
        span = span or next((s for s in reversed(self.spans) if s["e"] is None), None)
        if not span:
            return
        m = span["s"] + "e"
        self.chat.mark_set(m, "end-1c")
        self.chat.mark_gravity(m, "left")
        span["e"] = m
        self._queue_bars()

    def _archie(self):
        """Start Archie's reply (the lime line runs down its left side)."""
        t = self.chat
        if t.index("end-1c") != "1.0" and t.get("end-2c") != "\n":
            self._w("\n")
        self._start_span()

    def _queue_bars(self):
        if not self._bars_pending:
            self._bars_pending = True
            self.root.after_idle(self._draw_bars)

    def _draw_bars(self):
        self._bars_pending = False
        c, t = self.bars, self.chat
        try:
            c.delete("all")
            h = t.winfo_height()
            top, bot = t.index("@0,0"), t.index(f"@0,{h}")
        except tk.TclError:
            return
        for sp in self.spans:
            try:
                s = t.index(sp["s"])
                e = t.index(sp["e"]) if sp["e"] else t.index("end-1c")
            except tk.TclError:
                continue
            if t.compare(e, "<=", s):
                continue
            last = t.index(f"{e} -1c")
            if t.compare(last, "<", top) or t.compare(s, ">", f"{bot} lineend"):
                continue
            d1 = t.dlineinfo(s) if t.compare(s, ">=", top) else None
            d2 = t.dlineinfo(last) if t.compare(last, "<=", f"{bot} lineend") else None
            y0 = d1[1] if d1 else 0
            y1 = d2[1] + d2[3] if d2 else h
            if y1 - y0 > 2:
                c.create_rectangle(0, y0 + self.px(3), self.px(2), y1 - self.px(3),
                                   fill=sp["color"], width=0)

    def _panel_press(self, e):
        self._pdrag = (e.x_root, e.y_root, self.panel.winfo_x(), self.panel.winfo_y())

    def _panel_drag(self, e):
        sx, sy, wx, wy = self._pdrag
        self.panel.geometry(f"+{wx + e.x_root - sx}+{wy + e.y_root - sy}")
        self.panel_moved_by_hand = True

    def _grip_press(self, e):
        self._gdrag = (e.x_root, e.y_root, self.panel.winfo_width(), self.panel.winfo_height())

    def _grip_drag(self, e):
        sx, sy, w0, h0 = self._gdrag
        w = max(self.px(self.PANEL_MIN[0]), w0 + e.x_root - sx)
        h = max(self.px(self.PANEL_MIN[1]), h0 + e.y_root - sy)
        self.panel.geometry(f"{w}x{h}+{self.panel.winfo_x()}+{self.panel.winfo_y()}")
        self._gsize = (w, h)

    def _grip_release(self, _e):
        w, h = getattr(self, "_gsize", (self.panel.winfo_width(), self.panel.winfo_height()))
        self.cfg["panel_w"] = round(w / self.scale)
        self.cfg["panel_h"] = round(h / self.scale)
        save_config(self.cfg)
        self.panel_moved_by_hand = True   # keep it where you put it this session
        self._round_panel()

    def _round_panel(self):
        """Rounded corners (Windows 11 draws them + a hairline border for us)."""
        ok = th.round_corners(self.panel, self.px(14))
        if ok and self._rounded is not True:
            self.panel.configure(highlightthickness=0)
        self._rounded = ok

    def apply_text_size(self):
        s = self.TEXT_SIZES.get(self.cfg.get("text_size"), 10)
        px = self.px
        c = self.chat
        c.configure(font=(FONT, s))
        self.entry.configure(font=(MONO, s))
        self.placeholder.configure(font=(MONO, s))
        c.tag_configure("abody", foreground=BODY, spacing3=px(2))
        c.tag_configure("body", foreground=TEXT, spacing3=px(2))
        c.tag_configure("ubub", justify="right", spacing1=px(12), spacing3=px(12))
        c.tag_configure("sys", foreground=MUTED, font=(MONO, s - 2), spacing1=px(5), spacing3=px(3))
        c.tag_configure("file", foreground=MUTED, font=(MONO, s - 2), spacing1=px(0),
                        spacing3=px(6), justify="right")
        c.tag_configure("src", foreground=MUTED, font=(MONO, s - 2), spacing1=px(8))
        c.tag_configure("b_title", foreground=TEXT, font=(FONT_SEMI, s + 6, "bold" if FONT_SEMI == FONT else "normal"),
                        spacing1=px(2), spacing3=px(8))
        c.tag_configure("b_sub", foreground=MUTED, font=(MONO, s - 2), spacing1=px(4))
        c.tag_configure("b_head", foreground=MUTED, font=(MONO, s - 2), spacing1=px(12), spacing3=px(3))
        c.tag_configure("b_box", background=INPUT_BG, foreground=TEXT, lmargin1=px(2),
                        lmargin2=px(2), spacing1=px(4), spacing3=px(4))
        c.tag_configure("b_hot", foreground=ACCENT, font=(MONO, s - 1))
        c.tag_configure("b_muted", foreground=MUTED, font=(MONO, s - 2))
        c.tag_configure("b_link", foreground=ACCENT, underline=False, font=(MONO, s - 2))
        c.tag_configure("b_done", foreground=MUTED, overstrike=True)
        c.tag_raise("b_hot")
        c.tag_raise("b_link")
        c.tag_raise("sel")
        if hasattr(self, "tabs"):
            self._redraw_bubbles()

    def set_text_size(self, name):
        self.cfg["text_size"] = name
        self.text_size_var.set(name)
        save_config(self.cfg)
        self.apply_text_size()

    def _toggle_handwriting(self):
        self.cfg["read_handwriting"] = bool(self.handwriting_var.get())
        save_config(self.cfg)
        if self.cfg["read_handwriting"]:
            self.scanner.start()

    def _scan_tick(self):
        """Every minute: read any new photos / scans that landed in Notes."""
        if self.cfg.get("read_handwriting", True) and not self.snipping:
            self.scanner.start()
        self.listener.start()
        if self.cfg.get("lecture_wake"):
            self._lecture_sync_wake(quiet=True)
        if getattr(self, "ollama_ok", False) and not self.gym.sorting.is_set():
            try:
                if any(c is None for _, c in self.gym.pictures()):
                    self.gym.sort_new(lambda k, v: self.bg_q.put((k, v)))
            except OSError:
                pass
        self.root.after(60000, self._scan_tick)

    def _reread_notes(self):
        self.refresh_notes_in_background(quiet=False)
        if self.cfg.get("read_handwriting", True):
            self.scanner.start()

    def _handwriting_done(self, done, problems):
        if done:
            names = ", ".join(done[:4]) + (f" +{len(done) - 4} more" if len(done) > 4 else "")
            self._write(f"Read {len(done)} new page{'s' if len(done) != 1 else ''} of notes: {names}. "
                        "They're searchable now with notes ● on. (The text is saved next to each "
                        "photo as a (transcribed).md file; edit it to fix a word.)\n", "sys")
            if self.cfg.get("use_notes"):
                self.refresh_notes_in_background(quiet=True)
        for p in problems[:3]:
            self._write(f"Couldn't read {p}\n", "sys")
        if not self.busy:
            self._update_status()

    def _toggle_save_drops(self):
        self.cfg["save_drops_to_notes"] = bool(self.save_drops_var.get())
        save_config(self.cfg)

    def set_panel_size(self, w, h):
        self.cfg["panel_w"], self.cfg["panel_h"] = w, h
        save_config(self.cfg)
        if not self.panel_visible():
            self.show_panel()
        else:
            self.panel_moved_by_hand = False
            self.place_panel()

    def panel_visible(self):
        return self.panel.winfo_viewable()

    def place_panel(self):
        W, H, S, gap = self.px(self.PANEL_W), self.px(self.PANEL_H), self.px(self.BUBBLE), self.px(10)
        bx, by = self.root.winfo_x(), self.root.winfo_y()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        W, H = min(W, sw - self.px(20)), min(H, sh - self.px(60))
        x = bx - W - gap if bx - W - gap >= 0 else bx + S + gap
        y = max(0, min(max(0, by + S - H), sh - H - self.px(40)))
        x = min(max(0, x), sw - W)
        self.panel.geometry(f"{W}x{H}+{x}+{y}")
        if self._rounded is False and sys.platform == "win32":
            self.root.after_idle(self._round_panel)   # Windows 10: re-cut the rounded shape

    def toggle_panel(self):
        if self.panel_visible():
            self.hide_panel()
        else:
            self.show_panel()

    def show_panel(self):
        self._mini_exit()
        self.panel_moved_by_hand = False
        self.place_panel()
        self.panel.deiconify()
        if getattr(self, "banner", None) is not None:
            self.root.after(60, self._banner_place)
        self.panel.lift()
        if not self._rounded:
            self._round_panel()
        self.refresh_models()
        self.modes = load_modes(MODES_DIR, DEFAULT_MODES)   # pick up edits to mode files
        self._fill_mode_menu()
        if not self._greeted:
            self._greeted = True
            if self.cfg.get("brief_daily", True) and not self.brief_state.shown_today():
                self.show_brief()
            else:
                self._greet()
        self.entry.focus_force()

    def hide_panel(self):
        self.panel.withdraw()

    # ----- attachments ------------------------------------------------------

    def pick_files(self):
        patterns = " ".join("*" + e for e in sorted(SUPPORTED_EXT))
        self.panel.attributes("-topmost", False)   # let the file picker show on top
        try:
            paths = filedialog.askopenfilenames(
                parent=self.panel, title="Attach files for Archie",
                filetypes=[("Files Archie can read", patterns), ("All files", "*.*")])
        finally:
            self.panel.attributes("-topmost", True)
        self.add_attachments(paths)

    def _on_drop(self, e):
        """A dropped file gets an inbox card (save it where it belongs, or ask Archie about it)."""
        paths = list(self.root.tk.splitlist(e.data))
        rest = []
        for p in paths:
            if self.inbox and os.path.isfile(p):
                self._inbox_card(p)
            else:
                rest.append(p)
        if rest:
            self.add_attachments(rest)
        return e.action

    # ----- Archie Inbox: drop / paste / "Send to Archie" -> one card: what it is, which class, where it goes ---------
    def _inbox_poll(self):
        try:
            for path in self.inbox.take_queue() if self.inbox else []:
                if not self.panel_visible():
                    self.show_panel()
                self._inbox_card(path)
            while self.mail_cards:             # new mail: a Windows notification, and its card waits in the chat
                m = self.mail_cards.pop(0)
                self._mail_card(m)

                prof = bool(m.get("prof")) or any("prof" in str(w).lower() for w in (m.get("why") or []))
                silent = bool(self.quiet) and not self.quiet.sound_ok("prof_mail" if prof else "mail")

                def toast(m=m, silent=silent):
                    try:
                        ok = mailm.windows_toast(m, os.path.join(APP_DIR, "archie.png"), silent=silent)
                    except Exception:
                        ok = False
                    if not ok:
                        self._mail_show = True     # no Windows notification: open the panel instead (as before)
                threading.Thread(target=toast, daemon=True, name="mail-toast").start()
            if getattr(self, "_mail_show", False):
                self._mail_show = False
                if not self.panel_visible():
                    self.show_panel()
            for path, klass in self.inbox.take_dates() if self.inbox else []:
                if not self.panel_visible():
                    self.show_panel()
                self._dates_card(path, klass)
        except Exception:
            pass
        self.root.after(2000, self._inbox_poll)

    def _inbox_paste(self, _e=None):
        """Ctrl+V: a screenshot or copied files become inbox cards. Plain text pastes as usual."""
        try:
            from PIL import ImageGrab
            got = ImageGrab.grabclipboard()
        except Exception:
            return None
        if got is None:
            return None
        if isinstance(got, list):
            files = [p for p in got if os.path.isfile(p)]
            for p in files:
                self._inbox_card(p)
            return "break" if files else None
        try:
            os.makedirs(SNIPS_DIR, exist_ok=True)
            now = datetime.datetime.now()
            stamp = now.strftime("%Y-%m-%d ") + now.strftime("%I.%M %p").lstrip("0")
            path = os.path.join(SNIPS_DIR, f"Screenshot ({stamp}).png")
            i = 2
            while os.path.exists(path):
                path = os.path.join(SNIPS_DIR, f"Screenshot ({stamp}) {i}.png")
                i += 1
            got.save(path)
        except Exception:
            return None
        self._inbox_card(path)
        return "break"

    def _inbox_card(self, path):
        px = self.px
        try:
            g = self.inbox.guess(path)
        except Exception as e:
            self._write(f"I couldn't read {os.path.basename(path)} ({e}).\n", "sys")
            return
        t = self.chat
        W = max(px(300), t.winfo_width() - px(70))
        card = tk.Frame(t, bg=SURFACE, highlightthickness=1, highlightbackground="#4d5e14", padx=px(14), pady=px(12))
        tk.Frame(card, bg=SURFACE, width=W, height=1).pack(anchor="w")          # holds the card's width
        st = {"kind": g["kind"], "klass": g["klass"], "done": False}
        size = g["size"]
        sz = f"{size / 1048576:.1f} MB" if size >= 1048576 else f"{max(1, size // 1024)} KB"
        tk.Label(card, text=g["name"], bg=SURFACE, fg=TEXT, font=(FONT, 10, "bold"), anchor="w", justify="left",
                 wraplength=W).pack(anchor="w", fill="x")
        tk.Label(card, text=f"{sz} · just arrived", bg=SURFACE, fg=MUTED, font=(MONO, 8), anchor="w").pack(anchor="w")
        tk.Label(card, text="NAME", bg=SURFACE, fg=DIM, font=(MONO, 7)).pack(anchor="w", pady=(px(10), px(3)))
        nrow = tk.Frame(card, bg=SURFACE)
        nrow.pack(anchor="w", fill="x")
        stem0, ext0 = os.path.splitext(g["name"])
        name_var = tk.StringVar(value=stem0)
        ne = tk.Entry(nrow, textvariable=name_var, bg=INPUT_BG, fg=TEXT, insertbackground=ACCENT, relief="flat",
                      font=(FONT, 10), highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        ne.pack(side="left", fill="x", expand=True, ipady=px(4))
        tk.Label(nrow, text=ext0, bg=SURFACE, fg=MUTED, font=(MONO, 9), padx=px(6)).pack(side="left")
        guess = tk.Label(card, bg=SURFACE, fg=MUTED, font=(MONO, 9), anchor="w", justify="left", wraplength=W)
        guess.pack(anchor="w", pady=(px(8), 0))
        if g.get("dup"):
            d = g["dup"]
            tk.Label(card, text=f"⚠ already saved {d.get('date', '')} → {self.inbox.rel(d.get('dest', ''))}",
                     bg=SURFACE, fg="#f5a524", font=(MONO, 9), anchor="w", justify="left",
                     wraplength=W).pack(anchor="w", pady=(px(6), 0))
        rows = {}
        for key, title in (("kind", "WHAT IS IT"), ("klass", "CLASS")):
            tk.Label(card, text=title, bg=SURFACE, fg=DIM, font=(MONO, 7)).pack(anchor="w", pady=(px(10), px(3)))
            rows[key] = tk.Frame(card, bg=SURFACE)
            rows[key].pack(anchor="w", fill="x")
        tk.Label(card, text="SAVE TO", bg=SURFACE, fg=DIM, font=(MONO, 7)).pack(anchor="w", pady=(px(10), px(3)))
        dest = tk.Label(card, bg=INPUT_BG, fg=BODY, font=(MONO, 9), anchor="w", justify="left", wraplength=W - px(16),
                        padx=px(8), pady=px(5))
        dest.pack(anchor="w", fill="x")
        acts = tk.Frame(card, bg=SURFACE)
        acts.pack(anchor="w", fill="x", pady=(px(12), 0))
        cf = tkfont.Font(family=FONT, size=9)

        def chips(frame, options, cur, pick):
            for w in frame.winfo_children():
                w.destroy()
            line, used = None, W + 1
            for opt, label in options:
                wv = cf.measure(label) + px(26)
                if used + wv > W:
                    line = tk.Frame(frame, bg=SURFACE)
                    line.pack(anchor="w", pady=(0, px(5)))
                    used = 0
                on = opt == cur
                c = tk.Label(line, text=label, bg=ACCENT if on else INPUT_BG, fg=TILE if on else BODY,
                             font=(FONT, 9, "bold" if on else "normal"), padx=px(9), pady=px(2), cursor="hand2")
                c.pack(side="left", padx=(0, px(6)))
                c.bind("<ButtonRelease-1>", lambda e, o=opt: pick(o))
                used += wv

        def redraw():
            if st["done"]:
                return
            chips(rows["kind"], [(k, k) for k in self.inbox_types], st["kind"], lambda o: (st.update(kind=o), redraw()))
            cls = [(c, c) for c in self.inbox.classes()] + [(None, "no class")]
            if st["klass"] and st["klass"] not in [c for c, _ in cls]:
                cls.insert(0, (st["klass"], st["klass"]))
            chips(rows["klass"], cls, st["klass"], lambda o: (st.update(klass=o), redraw()))
            gg = dict(g, kind=st["kind"], klass=st["klass"])
            guess.configure(text="looks like " + self.inbox.describe(gg) if st["kind"] == g["kind"] and st["klass"] == g["klass"]
                            else "you picked " + self.inbox.describe(gg))
            dest.configure(text=self.inbox.rel(os.path.join(self.inbox.dest_dir(st["kind"], st["klass"]),
                                                             self.inbox.renamed(path, name_var.get()))))
            self._queue_bars()

        def button(text, cmd, main=False):
            b = tk.Label(acts, text=text, bg=ACCENT if main else INPUT_BG, fg=TILE if main else BODY,
                         font=(MONO, 9, "bold" if main else "normal"), padx=px(14), pady=px(6), cursor="hand2")
            b.pack(side="left", padx=(0, px(8)))
            b.bind("<ButtonRelease-1>", lambda e: cmd())
            return b

        def finish(msg, uid=None):
            st["done"] = True
            for w in card.winfo_children()[1:]:
                w.destroy()
            line = tk.Frame(card, bg=SURFACE)
            line.pack(anchor="w", fill="x")
            tk.Label(line, text=msg, bg=SURFACE, fg="#d9f08a", font=(MONO, 9), anchor="w", justify="left",
                     wraplength=W - px(90)).pack(side="left")
            if uid:
                u = tk.Label(line, text="undo 10", bg=SURFACE, fg=ACCENT, font=(MONO, 9, "bold"), cursor="hand2")
                u.pack(side="right")

                def tick(n):
                    if not u.winfo_exists():
                        return
                    if n <= 0:
                        u.destroy()
                        return
                    u.configure(text=f"undo {n}")
                    self.root.after(1000, tick, n - 1)

                def do_undo():
                    if self.inbox.undo(uid):
                        for w in line.winfo_children():
                            w.destroy()
                        tk.Label(line, text="↶ undone, nothing was saved", bg=SURFACE, fg=MUTED, font=(MONO, 9)).pack(side="left")
                u.bind("<ButtonRelease-1>", lambda e: do_undo())
                tick(10)
            self._queue_bars()

        def save():
            try:
                out, uid = self.inbox.save(path, st["kind"], st["klass"], new_name=name_var.get())
            except Exception as e:
                return finish(f"couldn't save it: {e}")
            finish(f"✓ saved to {self.inbox.rel(out)}", uid)
            if st["kind"] == "syllabus" and not st.get("dates"):   # a syllabus: read its dates right away (nothing is added until you tick)
                self._dates_card(out, st["klass"])

        def dates():
            if st.get("dates"):
                return
            st["dates"] = True
            db.configure(text="reading its dates ↓", fg=MUTED, cursor="")
            self._dates_card(path, st["klass"])

        def ask():
            finish("attached to your next message")
            self.add_attachments([path])

        button("Save again anyway" if g.get("dup") else "Save", save, main=True)
        db = button("Find dates", dates) if file_kind(path) else None
        button("Ask Archie about it", ask)
        if path.lower().endswith((".pdf", ".epub", ".txt", ".md")):
            button("Send to Feather", lambda: finish(self.send_to_feather([path])))
        button("Not now", lambda: finish("left where it was"))
        redraw()
        name_var.trace_add("write", lambda *a: redraw())
        ne.bind("<Return>", lambda e: (save(), "break")[1])
        t.configure(state="normal")
        if t.index("end-1c") != "1.0" and t.get("end-2c") != "\n":
            t.insert("end", "\n")
        t.window_create("end", window=card, padx=px(4), pady=px(4))
        t.insert("end", "\n")
        t.configure(state="disabled")
        t.see("end")
        self._queue_bars()

    def _mail_card(self, m):
        """New mail that matters: who, what, why; its attachments go to the inbox card, its dates to the dates reader."""
        px = self.px
        t = self.chat
        W = max(px(300), t.winfo_width() - px(70))
        card = tk.Frame(t, bg=SURFACE, highlightthickness=1, highlightbackground="#4d5e14" if m.get("prof") else BORDER,
                        padx=px(14), pady=px(12))
        tk.Frame(card, bg=SURFACE, width=W, height=1).pack(anchor="w")
        top = tk.Frame(card, bg=SURFACE)
        top.pack(anchor="w", fill="x")
        tk.Label(top, text="✉ GMAIL", bg=SURFACE, fg=ACCENT, font=(MONO, 8, "bold")).pack(side="left")
        try:
            d = datetime.datetime.fromisoformat(m["date"])
            when = f"{d:%a %b} {d.day} · {d.hour % 12 or 12}:{d:%M} {'AM' if d.hour < 12 else 'PM'}"
        except (ValueError, KeyError):
            when = ""
        tk.Label(top, text="  " + " · ".join([when] + m.get("why", [])), bg=SURFACE, fg=MUTED, font=(MONO, 8)).pack(side="left")
        tk.Label(card, text=m.get("from") or m.get("addr", ""), bg=SURFACE, fg=TEXT, font=(FONT, 11, "bold"), anchor="w",
                 justify="left", wraplength=W).pack(anchor="w", pady=(px(8), 0))
        tk.Label(card, text=m.get("subject", ""), bg=SURFACE, fg=BODY, font=(FONT, 10), anchor="w", justify="left",
                 wraplength=W).pack(anchor="w")
        if m.get("snippet"):
            tk.Label(card, text=m["snippet"], bg=SURFACE, fg=MUTED, font=(FONT, 9), anchor="w", justify="left",
                     wraplength=W).pack(anchor="w", pady=(px(6), 0))
        files = [p for p in m.get("attachments") or [] if os.path.exists(p)]
        if files:
            tk.Label(card, text="ATTACHMENTS · click one to file it", bg=SURFACE, fg=DIM, font=(MONO, 7)).pack(anchor="w", pady=(px(10), px(3)))
            for p in files:
                sz = os.path.getsize(p)
                f = tk.Label(card, text=f"📎 {os.path.basename(p)}  ·  {sz / 1048576:.1f} MB" if sz >= 1048576 else
                             f"📎 {os.path.basename(p)}  ·  {max(1, sz // 1024)} KB", bg=INPUT_BG, fg=BODY, font=(FONT, 9),
                             anchor="w", padx=px(8), pady=px(4), cursor="hand2")
                f.pack(anchor="w", fill="x", pady=(0, px(4)))
                f.bind("<ButtonRelease-1>", lambda e, p=p, f=f: (f.configure(fg=MUTED, text=f.cget("text") + "  ↓", cursor=""),
                                                                 f.unbind("<ButtonRelease-1>"), self._inbox_card(p)))
        acts = tk.Frame(card, bg=SURFACE)
        acts.pack(anchor="w", fill="x", pady=(px(12), 0))

        def button(text, cmd, main=False):
            b = tk.Label(acts, text=text, bg=ACCENT if main else INPUT_BG, fg=TILE if main else BODY,
                         font=(MONO, 9, "bold" if main else "normal"), padx=px(14), pady=px(6), cursor="hand2")
            b.pack(side="left", padx=(0, px(8)))
            b.bind("<ButtonRelease-1>", lambda e: cmd(b))
            return b

        def open_mail(b):
            import webbrowser
            webbrowser.open(m.get("link") or "https://mail.google.com/")

        def dates(b):
            b.configure(text="reading its dates ↓", fg=MUTED, cursor="")
            b.unbind("<ButtonRelease-1>")
            self._dates_card(m["body_path"], None)

        def done(b):
            for w in card.winfo_children()[1:]:
                w.destroy()
            tk.Label(card, text=f"✓ {m.get('subject', '')}"[:90], bg=SURFACE, fg=MUTED, font=(MONO, 9), anchor="w").pack(anchor="w")
            self._queue_bars()

        button("Open in Gmail", open_mail, main=True)
        if m.get("body_path") and os.path.exists(m["body_path"]):
            button("Find dates", dates)
        button("Done", done)
        t.configure(state="normal")
        if t.index("end-1c") != "1.0" and t.get("end-2c") != "\n":
            t.insert("end", "\n")
        t.window_create("end", window=card, padx=px(4), pady=px(4))
        t.insert("end", "\n")
        t.configure(state="disabled")
        t.see("end")
        self._queue_bars()

    def _dates_card(self, path, klass=None):
        """The dates reader: reads a syllabus/schedule/screenshot, lists what it found; ticked ones go on the calendar."""
        px = self.px
        t = self.chat
        W = max(px(300), t.winfo_width() - px(70))
        card = tk.Frame(t, bg=SURFACE, highlightthickness=1, highlightbackground="#4d5e14", padx=px(14), pady=px(12))
        tk.Frame(card, bg=SURFACE, width=W, height=1).pack(anchor="w")
        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower().strip(".")[:4].upper() or "FILE"
        src = tk.Frame(card, bg=INPUT_BG, padx=px(10), pady=px(8))
        src.pack(anchor="w", fill="x")
        tk.Label(src, text=ext, bg="#1b1b1b", fg=ACCENT, font=(MONO, 8, "bold"), width=4, pady=px(6)).pack(side="left")
        srct = tk.Frame(src, bg=INPUT_BG, padx=px(10))
        srct.pack(side="left", fill="x", expand=True)
        tk.Label(srct, text=name, bg=INPUT_BG, fg=TEXT, font=(FONT, 9), anchor="w", justify="left",
                 wraplength=W - px(90)).pack(anchor="w")
        status = tk.Label(srct, text="reading it… about a minute; keep working", bg=INPUT_BG, fg=MUTED, font=(MONO, 8), anchor="w")
        status.pack(anchor="w")
        body = tk.Frame(card, bg=SURFACE)
        body.pack(anchor="w", fill="x")
        st = {"plan": None, "done": False, "err": None, "raw": None, "t0": time.time(), "step": ""}
        cf = tkfont.Font(family=FONT, size=9)

        def place():
            t.configure(state="normal")
            if t.index("end-1c") != "1.0" and t.get("end-2c") != "\n":
                t.insert("end", "\n")
            t.window_create("end", window=card, padx=px(4), pady=px(4))
            t.insert("end", "\n")
            t.configure(state="disabled")
            t.see("end")
            self._queue_bars()

        def work():
            try:
                model = self.cfg["model"]

                def look(p):
                    with open(p, "rb") as f:
                        return self._review_vision(f.read(), "page")
                text = datesm.read(path, read_text, look)
                if not text.strip():
                    raise ValueError("there's no text in it I can read")
                ask = lambda prompt: quick_chat(model, prompt, max_tokens=4096, timeout=900, num_ctx=16384,
                                                json_mode=True, temperature=0.1)
                st["raw"] = datesm.find(text, name, ask, progress=lambda i, n: st.update(step=f" · part {i + 1} of {n}" if n > 1 else ""))
            except Exception as e:
                st["err"] = str(e) or type(e).__name__
            st["done"] = True

        def wait():
            if not card.winfo_exists():
                return
            if not st["done"]:
                status.configure(text=f"reading it{st['step']}… {int(time.time() - st['t0'])} s; keep working")
                return self.root.after(1000, wait)
            if st["err"]:
                status.configure(text=f"couldn't read it: {st['err']}"[:200], fg="#f5a524")
                return self._queue_bars()
            try:
                existing = self.calendar.load()
            except Exception:
                existing = []
            raw = st["raw"]
            course = klass or raw.get("course") or ""
            st["plan"] = datesm.plan(raw, course=course, existing=existing)
            st["found"] = raw.get("course") or ""
            status.configure(text=f"read in {int(time.time() - st['t0'])} s · nothing added yet")
            show()

        def show():
            for w in body.winfo_children():
                w.destroy()
            p = st["plan"]
            rows = p["rows"]
            if not rows:
                tk.Label(body, text="I didn't find any dates in it.", bg=SURFACE, fg=TEXT, font=(FONT, 12, "bold"),
                         anchor="w").pack(anchor="w", pady=(px(12), px(4)))
                return self._queue_bars()
            tk.Label(body, text=f"Found {len(rows)} thing{'s' if len(rows) != 1 else ''}" + (f" in {p['course']}" if p["course"] else ""),
                     bg=SURFACE, fg=TEXT, font=(FONT, 13, "bold"), anchor="w").pack(anchor="w", pady=(px(12), px(2)))
            tk.Label(body, text="Untick anything that's wrong. Hover a line to see where I found it.", bg=SURFACE, fg=MUTED,
                     font=(FONT, 9), anchor="w").pack(anchor="w")
            # which class these are for (names exams "<class> Midterm", and weekly classes "<class>")
            tk.Label(body, text="CLASS", bg=SURFACE, fg=DIM, font=(MONO, 7)).pack(anchor="w", pady=(px(10), px(3)))
            crow = tk.Frame(body, bg=SURFACE)
            crow.pack(anchor="w", fill="x")
            opts = []
            for c in [p["course"], st["found"], klass] + (self.inbox.classes() if self.inbox else []):
                if c and c not in opts:
                    opts.append(c)
            line, used = None, W + 1
            for c in opts + [""]:
                lab = c or "no class"
                wv = cf.measure(lab) + px(26)
                if used + wv > W:
                    line = tk.Frame(crow, bg=SURFACE)
                    line.pack(anchor="w", pady=(0, px(5)))
                    used = 0
                on = c == p["course"]
                ch = tk.Label(line, text=lab, bg=ACCENT if on else INPUT_BG, fg=TILE if on else BODY,
                              font=(FONT, 9, "bold" if on else "normal"), padx=px(9), pady=px(2), cursor="hand2")
                ch.pack(side="left", padx=(0, px(6)))
                ch.bind("<ButtonRelease-1>", lambda e, c=c: (datesm.retitle(p, c), show()))
                used += wv
            for label, rs in datesm.grouped(rows):
                tk.Label(body, text=label, bg=SURFACE, fg=DIM, font=(MONO, 7)).pack(anchor="w", pady=(px(12), px(3)))
                for r in rs:
                    row(r)
            for w_ in p["warns"]:
                tk.Label(body, text="⚠ " + w_, bg=SURFACE, fg="#f5a524", font=(FONT, 9), anchor="w", justify="left",
                         wraplength=W).pack(anchor="w", pady=(px(8), 0))
            acts = tk.Frame(body, bg=SURFACE)
            acts.pack(anchor="w", fill="x", pady=(px(12), 0))
            n = sum(1 for r in rows if r["on"] and r["events"])
            b = tk.Label(acts, text=f"Add {n} to calendar" if n else "Nothing ticked", bg=ACCENT if n else INPUT_BG,
                         fg=TILE if n else MUTED, font=(MONO, 9, "bold"), padx=px(14), pady=px(6), cursor="hand2" if n else "")
            b.pack(side="left", padx=(0, px(8)))
            if n:
                b.bind("<ButtonRelease-1>", lambda e: add())
            c_ = tk.Label(acts, text="Cancel", bg=INPUT_BG, fg=BODY, font=(MONO, 9), padx=px(14), pady=px(6), cursor="hand2")
            c_.pack(side="left")
            c_.bind("<ButtonRelease-1>", lambda e: end("nothing added"))
            self._queue_bars()

        def row(r):
            can = bool(r["events"])
            f = tk.Frame(body, bg=SURFACE, pady=px(3), cursor="hand2" if can else "")
            f.pack(anchor="w", fill="x")
            box = tk.Label(f, text="☑" if r["on"] else "☐", bg=SURFACE, fg=ACCENT if r["on"] else (MUTED if can else DIM),
                           font=(FONT, 11), width=2, anchor="n")
            box.pack(side="left", anchor="n")
            tk.Label(f, text="●", bg=SURFACE, fg=cal.KINDS.get(r["kind"], cal.KINDS["event"])[1], font=(FONT, 7),
                     anchor="n").pack(side="left", anchor="n", pady=(px(3), 0), padx=(0, px(6)))
            txt = tk.Frame(f, bg=SURFACE)
            txt.pack(side="left", fill="x", expand=True)
            tl = tk.Label(txt, text=r["title"], bg=SURFACE, fg=TEXT if r["on"] else MUTED, anchor="w",
                          font=(FONT, 10, "bold" if r["on"] else "overstrike" if can else "normal"))
            tl.pack(anchor="w")
            wl = tk.Label(txt, text=r["when"] + (f" · {r['note']}" if r["note"] else ""), bg=SURFACE, fg=MUTED,
                          font=(FONT, 9), anchor="w", justify="left", wraplength=W - px(50))
            wl.pack(anchor="w")
            if r["quote"]:
                q = "“" + (r["quote"][:140] + ("…" if len(r["quote"]) > 140 else "")) + "”" + (f" · page {r['page']}" if r["page"] else "")
                for w_ in (f, tl, wl):
                    self._tip(w_, q)
            if can:
                def flip(_e=None, r=r):
                    r["on"] = not r["on"]
                    show()
                for w_ in (f, box, tl, wl, txt):
                    w_.bind("<ButtonRelease-1>", flip)

        def add():
            try:
                ids = datesm.add(self.calendar, st["plan"]["rows"])
            except Exception as e:
                return end(f"couldn't add them: {e}")
            end(f"✓ added {len(ids)} to your calendar" if len(ids) != 1 else "✓ added 1 to your calendar", ids)

        def end(msg, ids=None):
            for w in body.winfo_children():
                w.destroy()
            line = tk.Frame(body, bg=SURFACE)
            line.pack(anchor="w", fill="x", pady=(px(10), 0))
            tk.Label(line, text=msg, bg=SURFACE, fg="#d9f08a", font=(MONO, 9), anchor="w").pack(side="left")
            if ids:
                op = tk.Label(line, text="open calendar", bg=SURFACE, fg=MUTED, font=(MONO, 9), cursor="hand2")
                op.pack(side="left", padx=(px(12), 0))
                first = min((e["date"] for r in st["plan"]["rows"] if r["on"] for e in r["events"]), default=None)
                op.bind("<ButtonRelease-1>", lambda e: self.show_calendar(first) if first else self.show_calendar())
                u = tk.Label(line, text="undo 10", bg=SURFACE, fg=ACCENT, font=(MONO, 9, "bold"), cursor="hand2")
                u.pack(side="right")

                def tick(n):
                    if not u.winfo_exists():
                        return
                    if n <= 0:
                        return u.destroy()
                    u.configure(text=f"undo {n}")
                    self.root.after(1000, tick, n - 1)

                def undo():
                    for i in ids:
                        try:
                            self.calendar.delete(i)
                        except Exception:
                            pass
                    for w in line.winfo_children():
                        w.destroy()
                    tk.Label(line, text="↶ undone, nothing was added", bg=SURFACE, fg=MUTED, font=(MONO, 9)).pack(side="left")
                u.bind("<ButtonRelease-1>", lambda e: undo())
                tick(10)
            self._queue_bars()

        place()
        threading.Thread(target=work, daemon=True, name="dates-reader").start()
        self.root.after(1000, wait)

    def add_attachments(self, paths):
        for path in paths:
            if os.path.isdir(path):
                self._write(f"{os.path.basename(path)} is a folder. To use a whole folder, "
                            "put it in your Notes folder and turn Notes on.\n", "sys")
                continue
            if not file_kind(path):
                self._write(f"I can't read {os.path.basename(path)} yet. I understand PDFs, "
                            "Word (.docx), text, code, and images.\n", "sys")
                continue
            if path not in self.attachments:
                self.attachments.append(path)
                is_snip = os.path.dirname(os.path.abspath(path)) == os.path.abspath(SNIPS_DIR)
                in_notes = os.path.abspath(path).startswith(os.path.abspath(NOTES_DIR) + os.sep)
                self.keep[path] = (bool(self.cfg.get("save_drops_to_notes", True))
                                   and not is_snip and not in_notes)
        self._render_chips()
        self.entry.focus_set()

    def _render_chips(self):
        for w in self.chips.winfo_children():
            w.destroy()
        if not self.attachments:
            self.chips.pack_forget()
            return
        shown = self.attachments[:3]
        mono = (MONO, 8)
        for path in shown:
            chip = tk.Frame(self.chips, bg=BG, highlightthickness=1, highlightbackground=BORDER)
            chip.pack(side="left", padx=(0, self.px(6)), pady=self.px(2))
            name = os.path.basename(path)
            if len(name) > 18:
                name = name[:15] + "..."
            icon = "img" if file_kind(path) == "image" else "doc"
            tk.Label(chip, text=f"{icon} {name}", bg=BG, fg=TEXT, font=mono,
                     padx=self.px(6), pady=self.px(2)).pack(side="left")
            on = self.keep.get(path)
            keep = tk.Label(chip, text="notes ●" if on else "notes ○", bg=BG,
                            fg=ACCENT if on else MUTED, font=mono, padx=self.px(3), cursor="hand2")
            keep.pack(side="left")
            keep.bind("<ButtonRelease-1>", lambda e, p=path: self._toggle_keep(p))
            self._tip(keep, "Also save this file to your Notes folder")
            x = tk.Label(chip, text="✕", bg=BG, fg=MUTED, font=mono, padx=self.px(5), cursor="hand2")
            x.pack(side="left")
            x.bind("<ButtonRelease-1>", lambda e, p=path: self._remove_attachment(p))
        extra = len(self.attachments) - len(shown)
        if extra > 0:
            tk.Label(self.chips, text=f"+{extra} more", bg=BG, fg=MUTED,
                     font=mono).pack(side="left")
        self.chips.pack(side="bottom", fill="x", before=self.body)

    def _toggle_keep(self, path):
        self.keep[path] = not self.keep.get(path)
        self._render_chips()

    def _save_to_notes(self, paths):
        """Copy files into Notes/Saved from chat so Archie can find them later."""
        import shutil
        dest_dir = os.path.join(NOTES_DIR, "Saved from chat")
        os.makedirs(dest_dir, exist_ok=True)
        saved = []
        for src in paths:
            name = os.path.basename(src)
            base, ext = os.path.splitext(name)
            dest, n = os.path.join(dest_dir, name), 2
            while os.path.exists(dest):
                try:
                    if os.path.getsize(dest) == os.path.getsize(src):
                        break          # already saved earlier
                except OSError:
                    pass
                dest = os.path.join(dest_dir, f"{base} ({n}){ext}")
                n += 1
            try:
                if not os.path.exists(dest):
                    shutil.copy2(src, dest)
                saved.append(os.path.basename(dest))
            except OSError as e:
                self._write(f"(Couldn't save {name} to Notes: {e.strerror})\n", "sys")
        return saved

    def _remove_attachment(self, path):
        if path in self.attachments:
            self.attachments.remove(path)
        self._render_chips()

    # ----- Obsidian ------------------------------------------------------------

    def vault(self):
        v = self.cfg.get("obsidian_vault")
        return v if v and os.path.isdir(v) else None

    def _search_folders(self):
        folders = {"Chats": CHATS_DIR}
        if self.vault():
            folders["Obsidian"] = self.vault()
        return folders

    def choose_vault(self):
        self.panel.attributes("-topmost", False)
        try:
            path = filedialog.askdirectory(parent=self.panel, title="Pick your Obsidian vault folder",
                                           initialdir=self.vault() or os.path.expanduser("~"))
        finally:
            self.panel.attributes("-topmost", True)
        if not path:
            return
        if not os.path.isdir(os.path.join(path, ".obsidian")):
            self._write("That folder doesn't look like an Obsidian vault (no .obsidian folder "
                        "inside). Pick the vault's main folder.\n", "sys")
            return
        self.cfg["obsidian_vault"] = os.path.normpath(path)
        save_config(self.cfg)
        self.notes.extra_folders = self._search_folders()
        self._write(f"Connected to your Obsidian vault: {os.path.basename(path)}. With Notes on, "
                    "I'll search it too.\n", "sys")
        if self.cfg.get("use_notes"):
            self.refresh_notes_in_background(quiet=False)

    def save_chat_to_obsidian(self):
        pairs, q = [], None
        for m in self.history:
            if m["role"] == "user":
                q = m.get("display") or m["content"]
            elif q is not None:
                pairs.append((q, m["content"]))
                q = None
        if not pairs:
            self._write("There's nothing in this chat to save yet.\n", "sys")
            return
        title = (self.chat_meta or {}).get("title") or pairs[0][0][:80]
        self.save_to_obsidian(title, pairs)

    def save_to_obsidian(self, title, pairs):
        vault = self.vault()
        if not vault:
            self._write("I don't know where your Obsidian vault is yet. Right-click the owl > "
                        "Choose Obsidian vault...\n", "sys")
            return
        mode = self.cfg.get("mode")
        self.status.configure(text="Saving to Obsidian...")

        def work():
            try:
                text = " ".join(q + " " + a for q, a in pairs)
                links = obs.related_links(self.notes, text)
                note = obs.build_note(" ".join(title.split()), pairs, mode, links)
                rel = obs.save_note(vault, title, note)
                self.bg_q.put(("obsidian_saved", (rel, links, None)))
            except Exception as e:
                self.bg_q.put(("obsidian_saved", (None, [], str(e))))
        threading.Thread(target=work, daemon=True).start()

    def _obsidian_saved(self, rel, links, err):
        self._update_status()
        if err:
            self._write(f"Couldn't save to Obsidian: {err}\n", "sys")
            return
        self._w("Saved to Obsidian: " + rel, "src")
        if links:
            self._w("  ·  linked to " + ", ".join(links), "src")
        self._w("   ")
        self._link("open", lambda: obs.open_in_obsidian(self.vault(), rel), "src")
        self._w("\n")
        self.chat.see("end")

    # ----- build an Obsidian wiki from the conversation -----------------------

    def build_wiki(self):
        if not self.vault():
            self._write("Connect your vault first: right-click the owl > Choose Obsidian vault...\n", "sys")
            return
        if len([m for m in self.history if m["role"] == "user"]) < 1:
            self._write("Talk the topic through with me first, then build the wiki from that chat.\n", "sys")
            return
        if getattr(self, "wiki_win", None) is not None and self.wiki_win.winfo_exists():
            self.wiki_win.lift()
            return
        from tkinter import ttk
        w = self.wiki_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, self.px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = self.px(440), self.px(560)
        w.geometry(f"{W}x{H}+{self.panel.winfo_x() + self.px(10)}+{max(0, self.panel.winfo_y() - self.px(20))}")
        top = tk.Frame(w, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text="Build an Obsidian wiki", bg=SURFACE, fg=ACCENT,
                 font=(FONT, 11, "bold"), padx=10, pady=6).pack(side="left")
        tk.Button(top, text="✕", command=self._close_wiki, bg=SURFACE, fg=MUTED, bd=0,
                  activebackground=INPUT_BG, activeforeground=TEXT, relief="flat",
                  font=(FONT, 10), padx=8, cursor="hand2").pack(side="right")
        self.wiki_body = tk.Frame(w, bg=BG, padx=12, pady=10)
        self.wiki_body.pack(fill="both", expand=True)
        self.wiki_status = tk.Label(self.wiki_body, text="Reading the conversation...", bg=BG, fg=TEXT,
                                    font=(FONT, 10), anchor="w", justify="left", wraplength=W - 40)
        self.wiki_status.pack(fill="x")
        style = ttk.Style(w)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Archie.Horizontal.TProgressbar", troughcolor=INPUT_BG, background=ACCENT,
                        bordercolor=INPUT_BG, lightcolor=ACCENT, darkcolor=ACCENT)
        self.wiki_bar = ttk.Progressbar(self.wiki_body, style="Archie.Horizontal.TProgressbar",
                                        mode="indeterminate")
        self.wiki_bar.pack(fill="x", pady=8)
        self.wiki_bar.start(12)
        self.wiki_stop = threading.Event()
        history, model = [dict(m) for m in self.history], self.cfg["model"]

        def work():
            try:
                plan = vaultgen.plan(model, history,
                                     progress=lambda s: self.bg_q.put(("wiki_status", (s, None))))
                self.bg_q.put(("wiki_plan", plan))
            except ArchieError as e:
                self.bg_q.put(("wiki_error", str(e)))
            except Exception as e:
                self.bg_q.put(("wiki_error", f"Something went wrong: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _close_wiki(self):
        if getattr(self, "wiki_stop", None):
            self.wiki_stop.set()
        if getattr(self, "wiki_win", None) is not None and self.wiki_win.winfo_exists():
            self.wiki_win.destroy()

    def _wiki_preview(self, plan):
        if not (getattr(self, "wiki_win", None) and self.wiki_win.winfo_exists()):
            return
        self.wiki_plan = plan
        self.wiki_bar.stop()
        self.wiki_bar.pack_forget()
        body = self.wiki_body
        self.wiki_status.configure(text=f"Here's the plan ({plan['kind']}). Untick anything you "
                                        "don't want, rename pages, then build.")
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", pady=(6, 4))
        tk.Label(row, text="Title", bg=BG, fg=MUTED, font=(FONT, 9)).pack(side="left")
        self.wiki_title = tk.Entry(row, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, bd=0,
                                   font=(FONT, 10), highlightthickness=1,
                                   highlightbackground=INPUT_BG, highlightcolor=ACCENT)
        self.wiki_title.insert(0, plan["title"])
        self.wiki_title.pack(side="left", fill="x", expand=True, padx=(8, 0), ipady=3)

        btns = tk.Frame(body, bg=BG)
        btns.pack(side="bottom", fill="x", pady=(8, 0))
        modes = tk.Frame(body, bg=BG)
        modes.pack(side="bottom", fill="x", pady=(6, 0))
        self.wiki_expand = tk.BooleanVar(value=False)
        for text, val in (("Only what I said", False), ("Expand it (Archie's ideas are marked)", True)):
            tk.Radiobutton(modes, text=text, variable=self.wiki_expand, value=val, bg=BG, fg=TEXT,
                           selectcolor=INPUT_BG, activebackground=BG, activeforeground=ACCENT,
                           font=(FONT, 9), anchor="w").pack(fill="x")

        tk.Label(body, text=f"{len(plan['sections'])} sections · {len(plan['items'])} pages · "
                            f"{len(plan['links'])} cross-links", bg=BG, fg=MUTED,
                 font=(FONT, 8), anchor="w").pack(fill="x")
        lst = self.wiki_list = tk.Listbox(body, selectmode="multiple", bg=BG, fg=TEXT,
                                          selectbackground=ACCENT, selectforeground=TILE, bd=0,
                                          highlightthickness=1, highlightbackground=INPUT_BG,
                                          font=(FONT, 9), activestyle="none", exportselection=False)
        lst.pack(fill="both", expand=True, pady=4)
        self._wiki_rows = []
        for s in plan["sections"]:
            for it in [i for i in plan["items"] if i["section"] == s["name"]]:
                self._wiki_rows.append(it)
                lst.insert("end", f"{s['name']}  ›  {it['name']}")
        lst.select_set(0, "end")
        tk.Label(body, text="Click to tick/untick · double-click to rename", bg=BG, fg=MUTED,
                 font=(FONT, 8), anchor="w").pack(fill="x")
        lst.bind("<Double-Button-1>", lambda e: self._wiki_rename())

        style = dict(bd=0, relief="flat", font=(FONT, 9, "bold"), padx=14, pady=4, cursor="hand2")
        tk.Button(btns, text="Build it", command=self._wiki_build, bg=ACCENT, fg=TILE,
                  activebackground=ACCENT_HI, **style).pack(side="right")
        tk.Button(btns, text="Cancel", command=self._close_wiki, bg=INPUT_BG, fg=MUTED,
                  activebackground=INPUT_BG, activeforeground=TEXT, **style).pack(side="left")

    def _wiki_rename(self):
        lst = self.wiki_list
        idx = lst.nearest(lst.winfo_pointery() - lst.winfo_rooty())
        if idx < 0 or idx >= len(self._wiki_rows):
            return
        it = self._wiki_rows[idx]
        bbox = lst.bbox(idx)
        if not bbox:
            return
        e = tk.Entry(lst, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, bd=0, font=(FONT, 9))
        e.insert(0, it["name"])
        e.place(x=0, y=bbox[1], relwidth=1, height=bbox[3] + 4)
        e.focus_set()
        e.select_range(0, "end")

        def done(_=None):
            new = " ".join(e.get().replace("[", "").replace("]", "").split())
            if new and new != it["name"]:
                old = it["name"]
                for l in self.wiki_plan["links"]:
                    if l["from"] == old:
                        l["from"] = new
                    if l["to"] == old:
                        l["to"] = new
                it["name"] = new
                was = lst.selection_includes(idx)
                lst.delete(idx)
                lst.insert(idx, f"{it['section']}  ›  {new}")
                if was:
                    lst.select_set(idx)
            e.destroy()
        e.bind("<Return>", done)
        e.bind("<FocusOut>", done)
        e.bind("<Escape>", lambda _: e.destroy())

    def _wiki_build(self):
        plan = self.wiki_plan
        keep = [self._wiki_rows[i] for i in self.wiki_list.curselection()]
        if not keep:
            self.wiki_status.configure(text="Tick at least one page to build.")
            return
        names = {i["name"] for i in keep}
        plan = dict(plan, items=keep,
                    links=[l for l in plan["links"] if l["from"] in names and l["to"] in names],
                    sections=[s for s in plan["sections"] if any(i["section"] == s["name"] for i in keep)],
                    title=" ".join(self.wiki_title.get().split()) or plan["title"])
        expand = bool(self.wiki_expand.get())
        for child in self.wiki_body.winfo_children():
            if child is not self.wiki_status:
                child.destroy()
        from tkinter import ttk
        self.wiki_bar = ttk.Progressbar(self.wiki_body, style="Archie.Horizontal.TProgressbar",
                                        mode="determinate", maximum=1.0)
        self.wiki_bar.pack(fill="x", pady=8)
        tk.Button(self.wiki_body, text="Stop", command=lambda: self.wiki_stop.set(), bg=INPUT_BG,
                  fg=MUTED, bd=0, relief="flat", font=(FONT, 9, "bold"), padx=14, pady=4,
                  cursor="hand2").pack(anchor="e")
        self.wiki_status.configure(text="Writing pages... (a big wiki takes a few minutes)")
        vault, model, stop = self.vault(), self.cfg["model"], self.wiki_stop

        def work():
            try:
                res = vaultgen.build(model, plan, vault, expand=expand, stop=stop,
                                     progress=lambda s, f=None: self.bg_q.put(("wiki_status", (s, f))))
                self.bg_q.put(("wiki_done", res))
            except ArchieError as e:
                self.bg_q.put(("wiki_error", str(e)))
            except Exception as e:
                self.bg_q.put(("wiki_error", f"Something went wrong: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _wiki_finished(self, res):
        root_rel, count, hub_path = res
        self._write(f"Built your Obsidian wiki: {count} pages in {os.path.basename(self.vault())}/{root_rel}  ", "file")
        self._link("open", lambda: obs.open_in_obsidian(self.vault(), hub_path + ".md"), "file")
        self._w("\n")
        if not (getattr(self, "wiki_win", None) and self.wiki_win.winfo_exists()):
            return
        for child in self.wiki_body.winfo_children():
            if child is not self.wiki_status:
                child.destroy()
        self.wiki_status.configure(text=f"Done! {count} pages are in your vault, in the folder "
                                        f"\"{root_rel}\". Open the graph view to see them connect.")
        style = dict(bd=0, relief="flat", font=(FONT, 9, "bold"), padx=14, pady=4, cursor="hand2")
        row = tk.Frame(self.wiki_body, bg=BG)
        row.pack(fill="x", pady=10)
        tk.Button(row, text="Open in Obsidian", bg=ACCENT, fg=TILE, activebackground=ACCENT_HI,
                  command=lambda: obs.open_in_obsidian(self.vault(), hub_path + ".md"), **style).pack(side="right")
        tk.Button(row, text="Close", bg=INPUT_BG, fg=MUTED, command=self._close_wiki,
                  activebackground=INPUT_BG, activeforeground=TEXT, **style).pack(side="left")

    # ----- morning brief -----------------------------------------------------

    def _toggle_brief_daily(self):
        self.cfg["brief_daily"] = bool(self.brief_daily_var.get())
        save_config(self.cfg)

    def _toggle_startup(self):
        want = bool(self.startup_var.get())
        err = set_start_with_windows(want, APP_DIR)
        if err:
            self.startup_var.set(not want)
            self._write(err + "\n", "sys")
        else:
            self._write("Archie will now start with Windows.\n" if want else
                        "Archie won't start with Windows anymore.\n", "sys")

    def _run_bat(self, name):
        path = os.path.join(APP_DIR, name)
        if not os.path.exists(path):
            self._write(f"I can't find {name} in {APP_DIR}.\n", "sys")
            return
        try:
            os.startfile(path)
            self._write(f"Started {name}. It opens its own window; leave it open until it says Done.\n", "sys")
        except Exception as e:
            self._write(f"Couldn't start {name}: {e}\n", "sys")

    def open_manual(self):
        """Open the offline manual in the browser (rebuilt first if the .md was edited)."""
        try:
            if make_manual.needs_build():
                make_manual.build()
            if not os.path.exists(make_manual.OUT):
                raise OSError("Archie Manual.html is missing")
            open_folder(make_manual.OUT)
            self._write("Opened the manual in your browser (it works offline). You can also just "
                        "ask me things like \"how do I snip the screen?\"\n", "sys")
        except Exception as e:
            self._write(f"I couldn't open the manual: {e}\n", "sys")

    def _auto_brief(self):
        if not self.panel_visible() and not self.brief_state.shown_today():
            self.show_panel()      # show_panel shows the brief when it's due

    def _w(self, text, *tags):
        self.chat.configure(state="normal")
        self.chat.insert("end", text, tags)
        self.chat.configure(state="disabled")
        self._queue_bars()

    def _link(self, text, command, *tags):
        """Clickable text in the chat."""
        self._brief_n += 1
        tag = f"lnk{self._brief_n}"
        self._w(text, "b_link", tag, *tags)
        self.chat.tag_bind(tag, "<Button-1>", lambda e: command())
        self.chat.tag_bind(tag, "<Enter>", lambda e: self.chat.configure(cursor="hand2"))
        self.chat.tag_bind(tag, "<Leave>", lambda e: self.chat.configure(cursor="arrow"))
        return tag

    def _placeholder(self, text="...", head=None):
        """Waiting text (and optional section heading) that gets filled in or
        removed once the background work is done."""
        self._brief_n += 1
        tag = f"ph{self._brief_n}"
        if head:
            self._w(head + "\n", "b_head", tag)
        self._w(text, "b_muted", tag)
        return tag

    def _fill(self, tag, parts):
        """Replace a placeholder with [(text, tags...), ...] or remove it (parts=None)."""
        rng = self.chat.tag_ranges(tag)
        if not rng:
            return
        self.chat.configure(state="normal")
        start = self.chat.index(rng[0])
        self.chat.delete(rng[0], rng[1])
        if parts:
            for text, *tags in reversed(parts):
                self.chat.insert(start, text, tuple(tags) + (tag,))
        self.chat.configure(state="disabled")
        self._queue_bars()

    def _brief_name(self):
        for line in read_small_text(ABOUT_PATH).splitlines():
            if line.lower().startswith("name:"):
                return line.split(":", 1)[1].strip().split(" ")[0]
        return ""

    def show_brief(self):
        if not self.panel_visible():
            self._greeted = True
            self.show_panel()
        today = datetime.date.today()
        hour = datetime.datetime.now().hour
        hello = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        name = self._brief_name()
        if self.chat.index("end-1c") != "1.0":
            self._w("\n")
        brief_start = self.chat.index("end-1c")
        span = self._start_span(BORDER)
        self._w("> brief · " + today.strftime("%a %d %b").replace(" 0", " ").lower() + "\n", "b_sub")
        self._w(f"{hello}{', ' + name if name else ''}\n", "b_title")

        # Countdown
        for when, what, days in self.deadlines.upcoming(today):
            left = "today!" if days == 0 else "tomorrow" if days == 1 else f"{days}d"
            self._w(f"  {what}   ", "b_box")
            self._w(f"{left}  \n", "b_box", "b_hot")

        # From last night's recap
        rc = self.recap.last_night()
        if rc:
            self._w("from last night's recap\n", "b_head")
            if rc.get("summary"):
                self._w(rc["summary"] + "\n", "body")
            if rc.get("mind"):
                self._w("on your mind: " + "; ".join(rc["mind"][:3]) + "\n", "b_muted")
            if rc.get("mind"):
                self._link("make a plan for that", lambda rc=rc: self._recap_plan(rc), "b_muted")
                self._w("   ")
            vault = self.vault()
            if rc.get("note") and vault:
                self._link("open the recap note", lambda rc=rc: obs.open_in_obsidian(vault, rc["note"]),
                           "b_muted")
            self._w("\n")

        # Pick up where you left off (from the focus timer)
        los = self.leftoff.recent(2, days=5, today=today)
        if los:
            self._w("pick up where you left off\n", "b_head")
            for lo in los:
                stopped, nxt = mem.split_note(lo["note"])
                self._w(lo["task"] + "   ", "body")
                self._w(mem.when_label(lo["date"], today)
                        + (f" · {mem.fmt_minutes(lo['minutes'])}" if lo.get("minutes") else "") + "\n", "b_muted")
                if stopped:
                    self._w("  stopped: " + stopped + "\n", "b_muted")
                if nxt:
                    self._w("  next: " + nxt + "\n", "body")
                self._w("  ")
                self._link("resume", lambda t=lo["task"]: self.show_focus(task=t, start=True), "b_muted")
                self._w("\n")

        # Sunday: the week is ready to look over
        if today.weekday() in (6, 0) and self.thisweek.due(today):
            self._w("your week\n", "b_head")
            self._w("I can sum up your week so I keep it in mind: what you're working on, what's stalling. ", "b_muted")
            self._link("look over my week", self.show_week, "b_muted")
            self._w("\n")

        # Patterns: a realistic day
        try:
            pl = mem.brief_line(self._patterns(), today)
        except Exception:
            pl = ""
        if pl:
            self._w("patterns: " + pl + "  ", "b_muted")
            self._link("see patterns", self.show_patterns, "b_muted")
            self._w("\n")

        # Once a year: a nudge to refresh the models
        if days_since_update() >= UPDATE_EVERY_DAYS:
            self._w("  yearly checkup: time to update Archie's models (needs internet)  ", "b_box", "b_hot")
            self._w("\n")
            self._link("run Update Archie.bat", lambda: self._run_bat("Update Archie.bat"), "b_muted")
            self._w("   ")
            self._link("how it works", self.open_manual, "b_muted")
            self._w("\n")

        # The world, overnight (only when Archie World has something)
        try:
            wl = self.world.brief_lines() if self.world else None
        except Exception:
            wl = None
        if wl and (wl["events"] or wl["stories"] or wl["moves"]):
            self._w("the world\n", "b_head")
            for e in wl["events"]:
                self._w("● " if e["confirmed"] else "○ ", "b_hot" if e["confirmed"] else "b_muted")
                self._link(e["t"], lambda h="event=" + e["id"]: self.show_world(h), "body")
                self._w("  " + e["where"] + "\n", "b_muted")
            for s_ in wl["stories"]:
                self._w("  ")
                self._link(s_["t"], lambda h="story=" + s_["id"]: self.show_world(h), "body")
                self._w(f"  {s_['n']} outlets\n", "b_muted")
            if wl["moves"]:
                self._w("  " + "  ·  ".join(wl["moves"]) + "\n", "b_muted")
            self._link("news brief", lambda: self.show_world("brief"), "b_muted")
            self._w("   ")
            self._link("open the globe", lambda: self.show_world(), "b_muted")
            self._w("   ")
            self._link("morning note", lambda: self.show_world("note"), "b_muted")
            self._w("\n")

        # Coming up (calendar)
        coming = self.calendar.upcoming(today)[:6]
        self._w("coming up\n", "b_head")
        if not coming:
            self._w("nothing on the calendar yet. Type  exam: bio midterm oct 12 9am  or click the "
                    "date at the top.\n", "b_muted")
        if coming:
            for e in coming:
                col = cal.KINDS.get(e["kind"], cal.KINDS["event"])[1]
                tag = f"k_{e['kind']}"
                self.chat.tag_configure(tag, foreground=col, font=(MONO, self.TEXT_SIZES.get(self.cfg.get("text_size"), 10) - 2))
                self._w(cal.KINDS.get(e["kind"], cal.KINDS["event"])[0].lower() + "  ", tag)
                self._w(e["title"] + "  ", "body")
                self._w(cal.when(e, today) + "\n", "b_muted")
            self._link("open calendar", lambda: self.show_calendar(), "b_muted")
            self._w("\n")

        # Today's list
        self._w("today\n", "b_head")
        items = self.tasks.for_brief(today)
        if not items:
            self._w("Nothing on your list. Type  add: something  to add a task.\n", "b_muted")
        for t in items:
            self._task_line(t)

        # Where you left off
        chats = list_chats(CHATS_DIR)[:2]
        jobs = []
        self._brief_parts = {"chats": [[c.get("title", "Chat"), ""] for c in chats]}
        self._brief_jobs = {}
        if chats:
            self._w("recent chats\n", "b_head")
            for c in chats:
                self._w(c.get("title", "Chat") + "   ", "body")
                self._link("Reopen", lambda c=c: self.open_chat(c))
                self._w("\n")
                jobs.append(("summary", self._placeholder("thinking back...") , c))
                self._w("\n")

        # New in your notes
        fresh = new_notes(NOTES_DIR, self.brief_state)
        if fresh:
            self._w("new in your notes\n", "b_head")
            shown = [os.path.basename(f) for f in fresh[:4]]
            more = f"  +{len(fresh) - 4} more" if len(fresh) > 4 else ""
            self._w(" · ".join(shown) + more + "\n", "body")
            self._brief_parts["fresh"] = ", ".join(shown) + more

        # Wikipedia fact
        if self.wiki.describe():
            jobs.append(("wiki", self._placeholder("finding something interesting...",
                                                   head="from your wikipedia"), None))
            self._w("\n")

        # Quick question from notes
        if self.notes.random_chunk() is not None:
            jobs.append(("quiz", self._placeholder("writing a question...",
                                                   head="quick question from your notes"), None))
            self._w("\n")

        # Flashcards
        rev, new = self.study.counts()
        if rev or new:
            self._w("flashcards\n", "b_head")
            self._w(f"{rev} due, {new} new   ", "body")
            self._link("study now", lambda: self.show_study(None))
            self._w("\n")
            self._brief_parts["cards"] = (rev, new)

        # What updated itself since last time (shown once)
        try:
            up = self.updater.brief_line() if self.updater else None
        except Exception:
            up = None
        if up:
            self._w("updates\n", "b_head")
            self._w(up[0] + "\n", "body")
            self.updater.mark_shown()

        # Footer
        foot = []
        part = [f for f in os.listdir(WIKI_DIR) if f.endswith(".part")] if os.path.isdir(WIKI_DIR) else []
        if part and not self.wiki.describe():
            gb = os.path.getsize(os.path.join(WIKI_DIR, part[0])) / 1e9
            foot.append(f"Wikipedia downloading ({gb:.0f} GB so far)")
        n = len([m for m in (list_models() or []) if not m.startswith("nomic-embed")])
        foot.append(f"{n} models ready" if n else "Ollama isn't running")
        foot.append("add a task with  add: ...")
        self._w("\n" + "  ·  ".join(foot), "b_muted")
        self._end_span(span)
        self._w("\n", "b_muted")
        self.chat.see("end")
        self.chat.see(brief_start)   # show the top of the brief

        self.brief_state.mark_shown()
        for i, (kind, tag, data) in enumerate(jobs):
            self._brief_jobs[tag] = (kind, chats.index(data) if kind == "summary" else None)
        self._sync_daily(quiet=True)
        if jobs:
            threading.Thread(target=self._brief_worker, args=(jobs, self.cfg["model"]),
                             daemon=True).start()

    def _task_line(self, t):
        label = when_label(t["due"])
        extra = f"  ({label})" if label else ""
        self._brief_n += 1
        tag = f"task{self._brief_n}"

        def toggle():
            done = not state["done"]
            try:
                self.tasks.set_done(t, done)
                self.root.after(50, lambda: self._sync_daily(quiet=True))
            except OSError:
                return
            state["done"] = done
            rng = self.chat.tag_ranges(tag)
            if rng:
                self.chat.configure(state="normal")
                self.chat.delete(rng[0], rng[1])
                self.chat.insert(rng[0], ("☑ " if done else "☐ ") + t["text"] + extra,
                                 ("b_done", tag) if done else ("body", tag))
                self.chat.configure(state="disabled")

        state = {"done": False}
        hot = ("b_hot",) if label in ("overdue", "today") else ()
        self._w("☐ " + t["text"] + extra, "body", tag, *hot)
        self._w("\n")
        self.chat.tag_bind(tag, "<Button-1>", lambda e: toggle())
        self.chat.tag_bind(tag, "<Enter>", lambda e: self.chat.configure(cursor="hand2"))
        self.chat.tag_bind(tag, "<Leave>", lambda e: self.chat.configure(cursor="arrow"))

    def _brief_worker(self, jobs, model):
        """Background: the bits of the brief that need the AI or Wikipedia."""
        for kind, tag, data in jobs:
            result = None
            try:
                if kind == "summary":
                    lines = []
                    for m in data.get("messages", [])[-6:]:
                        who = "You" if m["role"] == "user" else "Archie"
                        lines.append(f"{who}: {(m.get('display') or m['content'])[:600]}")
                    text = quick_chat(model, "In ONE short sentence (under 20 words), starting "
                                      "with 'You were', say where this conversation left off:\n\n"
                                      + "\n".join(lines), max_tokens=60)
                    result = [(text.strip().split("\n")[0], "b_muted")] if text else None
                elif kind == "wiki":
                    art = self.wiki.random_article()
                    if art:
                        title, para = art
                        result = [("from your wikipedia\n", "b_head"),
                                  (title + ": ", "b_hot"), (para, "body")]
                elif kind == "quiz":
                    pick = self.notes.random_chunk()
                    if pick:
                        rel, chunk = pick
                        out = quick_chat(model, "Write ONE short quiz question that tests the most "
                                         "important idea in this text, then its answer. Use exactly "
                                         "this format:\nQ: ...\nA: ...\n\nText:\n" + chunk[:2500],
                                         max_tokens=160)
                        q = a = None
                        for line in out.splitlines():
                            if line.strip().lower().startswith("q:"):
                                q = line.split(":", 1)[1].strip()
                            elif line.strip().lower().startswith("a:"):
                                a = line.split(":", 1)[1].strip()
                        if q and a:
                            result = ("quiz", q, a, os.path.basename(rel))
            except Exception:
                result = None
            self.bg_q.put(("brief_fill", (tag, result)))

    def _brief_to_daily(self, tag, result):
        job = self._brief_jobs.get(tag)
        if not job or not self._brief_parts or not result:
            return
        kind, idx = job
        try:
            if kind == "summary":
                self._brief_parts["chats"][idx][1] = result[0][0].strip()
            elif kind == "wiki":
                self._brief_parts["wiki"] = (result[1][0].rstrip(": "), result[2][0].strip())
            elif kind == "quiz":
                self._brief_parts["quiz"] = result[1:]
        except (IndexError, TypeError):
            return
        self._sync_daily(quiet=True)

    def _brief_quiz(self, tag, q, a, source):
        self._fill(tag, [("quick question from your notes\n", "b_head"), (q + "   ", "body")])
        rng = self.chat.tag_ranges(tag)
        # insert the answer link right after the question
        self._brief_n += 1
        ans_tag, link_tag = f"ans{self._brief_n}", f"lnk{self._brief_n}"
        self.chat.configure(state="normal")
        pos = self.chat.index(f"{rng[1]}") if rng else "end"
        self.chat.insert(pos, "Show answer", ("b_link", link_tag))
        self.chat.configure(state="disabled")

        def reveal():
            r = self.chat.tag_ranges(link_tag)
            if r:
                self.chat.configure(state="normal")
                self.chat.delete(r[0], r[1])
                self.chat.insert(r[0], f"{a}  (from {source})", ("b_hot",))
                self.chat.configure(state="disabled")
        self.chat.tag_bind(link_tag, "<Button-1>", lambda e: reveal())
        self.chat.tag_bind(link_tag, "<Enter>", lambda e: self.chat.configure(cursor="hand2"))
        self.chat.tag_bind(link_tag, "<Leave>", lambda e: self.chat.configure(cursor="arrow"))

    # ----- hotkeys and screen snip ------------------------------------------

    def hotkey_chat(self):
        if self.snipping:
            return
        if self.panel_visible():
            self.hide_panel()
        else:
            self.root.deiconify()
            self.show_panel()
            self.panel.lift()
            self.panel.focus_force()
            self.entry.focus_force()

    def start_snip(self):
        if self.snipping:
            return
        self.snipping = True
        self._panel_was_open = self.panel_visible()
        self.menu.unpost()
        self.panel.withdraw()        # hide Archie so it isn't in the picture
        self.root.withdraw()
        self.root.after(250, self._grab_and_show)

    def _grab_and_show(self):
        try:
            img = grab_screen()
            self._overlay = SnipOverlay(self.root, img, SNIPS_DIR, self._snip_done, self._snip_cancel)
        except Exception as e:
            self._snip_cancel()
            self._write(f"I couldn't capture the screen ({e}). If it mentions PIL, run "
                        "Tools\\Install Extras.bat.\n", "sys")

    def _restore_after_snip(self):
        self.snipping = False
        self.root.deiconify()
        self.root.attributes("-topmost", True)

    def _snip_done(self, path):
        self._restore_after_snip()
        if getattr(self, "_snip_for_sketch", False):
            self._snip_for_sketch = False
            self.show_sketch(path)
            return
        if not self.panel_visible():
            self.show_panel()
        if getattr(self, "inbox", None):          # a snip gets the inbox card: save it, or ask Archie about it
            self._inbox_card(path)
        else:
            self.add_attachments([path])
        self.panel.lift()
        self.panel.focus_force()
        self.entry.focus_force()

    def _snip_cancel(self):
        self._restore_after_snip()
        if getattr(self, "_snip_for_sketch", False):
            self._snip_for_sketch = False
            self.show_sketch()
            return
        if getattr(self, "_panel_was_open", False):
            self.show_panel()

    # ----- opening apps and making files ------------------------------------------

    def _app_folders(self):
        home = os.path.expanduser("~")
        f = {"notes": NOTES_DIR, "archie": APP_DIR, "recordings": RECORDINGS_DIR,
             "screenshots": SNIPS_DIR, "flashcards": STUDY_DIR,
             "downloads": os.path.join(home, "Downloads"), "documents": os.path.join(home, "Documents"),
             "desktop": os.path.join(home, "Desktop"), "pictures": os.path.join(home, "Pictures"),
             "created files": self._files_dir(),
             "audiobooks": os.path.join(NOTES_DIR, "Audiobooks"),
             "voice inbox": os.path.join(NOTES_DIR, "Voice inbox")}
        if self.vault():
            f["vault"] = f["obsidian vault"] = f["obsidian folder"] = self.vault()
        return f

    def _files_dir(self):
        return self.cfg.get("files_dir") or os.path.join(os.path.expanduser("~"), "Documents", "Archie Files")

    def _open_thing(self, what, text):
        """'open blender' / 'open my notes folder'. Runs the lookup in the background."""
        self.apps.folders = self._app_folders()
        key, path = self.apps.folder_for(what)
        self._you(text)
        if path:
            open_folder(path)
            self._archie()
            self._write(f"Opened your {key} folder.", "abody")
            self._end_span()
            self._write("\n", "abody")
            return
        self.status.configure(text=f"looking for {what}...")

        def work():
            try:
                name, how = self.apps.find(what)
                if name:
                    self.apps.launch(how)
                self.bg_q.put(("call", lambda: done(name, how)))
            except Exception as e:
                self.bg_q.put(("call", lambda msg=str(e): done(None, [], msg)))

        def done(name, how, err=None):
            self._update_status()
            self._archie()
            if err:
                self._write(f"I couldn't open that: {err}", "abody")
            elif name:
                self._write(f"Opening {name}.", "abody")
            else:
                sug = f" Did you mean {', '.join(s.title() for s in how)}?" if how else ""
                self._write(f"I couldn't find \"{what}\" in your Start menu. If you just installed it, "
                            f"it'll show up once it's in the Start menu.{sug}", "abody")
            self._end_span()
            self._write("\n", "abody")
        threading.Thread(target=work, daemon=True).start()

    def _make_file(self, req, text):
        """'make a godot script called player.gd that...': write it, then show it before saving."""
        self._you(text)
        models = list_models() or []
        coder = next((m for m in models if m.startswith("qwen2.5-coder")), None)
        model = coder if coder and req["ext"] not in (".md", ".txt", ".csv") else self.cfg["model"]
        self._write(f"Writing it with {self.nice(model)}... I'll show it to you before anything is saved.\n", "sys")

        def work():
            try:
                name = req["name"]
                if not name:
                    raw = quick_chat(model, apps.NAME_PROMPT.format(ext=req["ext"], request=text),
                                     max_tokens=20, temperature=0.2)
                    name = re.sub(r"[^\w.\-]", "", (raw or "").strip().split()[0] if raw else "") or "new_file"
                    if not name.lower().endswith(req["ext"]):
                        name = os.path.splitext(name)[0] + req["ext"]
                self.bg_q.put(("status", f"writing {name}..."))
                body = quick_chat(model, apps.FILE_PROMPT.format(name=name, request=text),
                                  max_tokens=4096, timeout=600, num_ctx=16384, temperature=0.2)
                content = apps.clean_code(body)
                self.bg_q.put(("call", lambda: self.show_new_file(name, content)))
            except Exception as e:
                self.bg_q.put(("voice_error", f"Couldn't write the file: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def show_new_file(self, name, content):
        self._update_status()
        px = self.px
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = px(max(480, self.PANEL_W)), px(max(480, self.PANEL_H - 40))
        w.geometry(f"{W}x{H}+{self.panel.winfo_x() + px(10)}+{self.panel.winfo_y() + px(20)}")
        folder = tk.StringVar(value=self._files_dir())
        fname = tk.StringVar(value=name)

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(6)))
        tk.Label(top, text="NEW FILE", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        tk.Label(top, text="  nothing is saved until you click save", bg=BG, fg=MUTED,
                 font=(MONO, 8)).pack(side="left")
        self._icon_btn(top, "close", w.destroy, "Cancel").pack(side="right")
        top.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
        top.bind("<B1-Motion>", lambda e: w.geometry(
            f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))

        row = tk.Frame(w, bg=BG)
        row.pack(fill="x", padx=px(14), pady=(0, px(4)))
        tk.Label(row, text="name", bg=BG, fg=MUTED, font=(MONO, 8), width=6, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=fname, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0,
                 font=(MONO, 10), highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=px(3))
        row2 = tk.Frame(w, bg=BG)
        row2.pack(fill="x", padx=px(14), pady=(0, px(8)))
        tk.Label(row2, text="folder", bg=BG, fg=MUTED, font=(MONO, 8), width=6, anchor="w").pack(side="left")
        tk.Label(row2, textvariable=folder, bg=BG, fg=BODY, font=(MONO, 8), anchor="w").pack(side="left", fill="x", expand=True)

        def pick():
            w.attributes("-topmost", False)
            try:
                d = filedialog.askdirectory(parent=w, initialdir=folder.get() if os.path.isdir(folder.get())
                                            else os.path.expanduser("~"), title="Save the file in...")
            finally:
                w.attributes("-topmost", True)
            if d:
                folder.set(os.path.normpath(d))
                refresh()
        ch = tk.Label(row2, text="change", bg=BG, fg=ACCENT, font=(MONO, 8), cursor="hand2")
        ch.pack(side="right")
        ch.bind("<ButtonRelease-1>", lambda e: pick())

        bottom = tk.Frame(w, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=px(14), pady=(px(6), px(12)))
        status = tk.Label(w, text="Edit anything before saving. Ctrl+Z undoes.", bg=BG, fg=MUTED,
                          font=(MONO, 8), anchor="w")
        status.pack(side="bottom", fill="x", padx=px(14))
        box = tk.Frame(w, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True, padx=px(14))
        ed = tk.Text(box, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, wrap="none", bd=0, undo=True,
                     padx=px(10), pady=px(8), highlightthickness=0, font=(MONO, 9),
                     selectbackground=ACCENT, selectforeground=TILE, tabs=("4c",))
        sb = th.SlimScrollbar(box, ed, width=px(8))
        sb.configure(bg=SURFACE)
        ed.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=px(4))
        ed.pack(side="left", fill="both", expand=True)
        ed.insert("1.0", content)
        ed.edit_reset()

        def target():
            n = re.sub(r'[<>:"/\\|?*]', "", fname.get().strip()) or "new_file.txt"
            return os.path.join(folder.get(), n)

        def save(open_after=False):
            path = target()
            exists = os.path.exists(path)
            if exists and not getattr(w, "_ok_replace", False):
                w._ok_replace = True
                status.configure(text=f"{os.path.basename(path)} already exists there. Click again to REPLACE it.",
                                 fg=REC)
                return
            try:
                os.makedirs(folder.get(), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(ed.get("1.0", "end-1c"))
            except OSError as e:
                status.configure(text=f"Couldn't save: {e.strerror}", fg=REC)
                return
            self.cfg["files_dir"] = folder.get()
            save_config(self.cfg)
            self._write(f"Saved {path}\n", "sys")
            if open_after:
                try:
                    os.startfile(path) if sys.platform == "win32" else open_folder(path)
                except OSError:
                    open_folder(folder.get())
            w.destroy()

        def refresh(*_):
            w._ok_replace = False
            status.configure(text=("Heads up: a file with this name already exists there."
                                   if os.path.exists(target()) else "Edit anything before saving. Ctrl+Z undoes."),
                             fg=REC if os.path.exists(target()) else MUTED)
        fname.trace_add("write", refresh)

        def btn(text, cmd, primary=False):
            b = tk.Label(bottom, text=text, font=(MONO, 8, "bold" if primary else "normal"),
                         bg=ACCENT if primary else BG, fg=TILE if primary else DIM, padx=px(10), pady=px(4),
                         bd=0, cursor="hand2", highlightthickness=0 if primary else 1, highlightbackground=BORDER)
            b.bind("<ButtonRelease-1>", lambda e: cmd())
            return b
        btn("save & open", lambda: save(True), primary=True).pack(side="right")
        btn("save", save).pack(side="right", padx=(0, px(6)))
        btn("open folder", lambda: open_folder(folder.get())).pack(side="left")
        w.bind("<Escape>", lambda e: w.destroy())
        refresh()

    # ----- recordings from the phone + audiobooks (background) -------------------

    def _bg_transcriber(self):
        """A second copy of Whisper for background jobs, so an audiobook never makes
        your own voice notes wait."""
        if self.bg_transcriber is None:
            self.bg_transcriber = Transcriber(VOICE_MODELS_DIR,
                                              self.cfg.get("audiobook_model") or self.cfg.get("voice_model"),
                                              self.cfg.get("voice_device"))
        return self.bg_transcriber

    def _listen_busy(self):
        return bool(self.busy or self.recorder.recording or self._fg_transcribing
                    or getattr(getattr(self, "imager", None), "working", False))

    def _toggle_audiobooks(self):
        self.cfg["audiobooks_paused"] = bool(self.ab_pause_var.get())
        save_config(self.cfg)
        if not self.cfg["audiobooks_paused"]:
            self.listener.start()

    def _exam_prep_event(self, val):
        klass, title, out, left = val
        vault = self.vault()
        self._write(f"Exam prep ready: {title} ({'today' if left == 0 else 'tomorrow' if left == 1 else f'in {left} days'}). ", "sys")
        if vault and os.path.abspath(out).startswith(os.path.abspath(vault)):
            rel = os.path.relpath(out, vault).replace("\\", "/")
            self._link("open in obsidian", lambda: obs.open_in_obsidian(vault, rel), "sys")
        self._write("\n", "sys")

    def _review_event(self, val):
        klass, out = val
        vault = self.vault()
        self._write(f"Lecture review ready: {klass}: {os.path.basename(out)[11:-3]}. ", "sys")
        if vault and os.path.abspath(out).startswith(os.path.abspath(vault)):
            rel = os.path.relpath(out, vault).replace("\\", "/")
            self._link("open in obsidian", lambda: obs.open_in_obsidian(vault, rel), "sys")
        else:
            self._link("open it", lambda: open_folder(out), "sys")
        self._write("\n", "sys")

    def _listen_event(self, kind, val):
        if kind == "listen_lecture":
            name, out = val
            info = getattr(self, "_lecture_last", {}) or {}
            vault = self.vault()
            what = (info.get("klass") + ": " if info.get("klass") else "") + (info.get("title") or os.path.basename(out)[11:-3])
            self._write(f"Lecture notes ready: {what}. ", "sys")
            if vault and os.path.abspath(out).startswith(os.path.abspath(vault)):
                rel = os.path.relpath(out, vault).replace("\\", "/")
                self._link("open in obsidian", lambda: obs.open_in_obsidian(vault, rel), "sys")
            else:
                self._link("open it", lambda: open_folder(out), "sys")
            if info.get("added"):
                n = info["added"]
                self._write(f"  ({n} to-do{'s' if n != 1 else ''} from class added to your list)", "sys")
            self._write("\n", "sys")
        elif kind == "listen_note":
            name, out = val
            vault = self.vault()
            self._write(f"Typed out your recording {name}. ", "sys")
            if vault and os.path.abspath(out).startswith(os.path.abspath(vault)):
                rel = os.path.relpath(out, vault).replace("\\", "/")
                self._link("open in obsidian", lambda: obs.open_in_obsidian(vault, rel), "sys")
            else:
                self._link("open it", lambda: open_folder(out), "sys")
            self._write("\n", "sys")
        elif kind == "listen_book":
            title, done, total, what = val
            if what == "start":
                self._write(f"Starting to listen to the audiobook \"{title}\" ({total} part{'s' if total != 1 else ''}). This runs in "
                            "the background and can take hours; it pauses while you use me and picks up "
                            "where it left off. Type  audiobooks  to check on it.\n", "sys")
            else:
                self._write(f"Finished typing out \"{title}\". Try: quiz me on {title} chapter 1\n", "sys")
        elif kind == "listen_error":
            self._write(val + "\n", "sys")
        if not self.busy:
            self._update_status()

    def audiobook_report(self):
        books_ = self.listener.book_status()
        if not books_:
            self._write("No audiobooks yet. Put one in Notes\\Audiobooks: a folder of MP3s (one per "
                        "chapter) or a single .m4b / .mp3, and I'll start typing it out.\n", "sys")
            return
        lines = []
        for t, d, tot, err in books_:
            if err and "copy-protected" in err:
                state = f"can't read it: {err}"
            elif err:
                state = f"couldn't open it yet ({err}); retrying every 10 minutes"
            elif tot and d >= tot:
                state = "done. Try: quiz me on " + t + " chapter 1"
            elif tot:
                state = f"{d} of {tot} parts typed out"
            else:
                state = "starting within a minute or so"
            lines.append(f"{t}: {state}")
        if self.listener.running.is_set() and not self.cfg.get("audiobooks_paused"):
            lines.append("(working on it now; it pauses while you're chatting)")
        extra = " (paused: right-click the owl > Pause audiobooks)" if self.cfg.get("audiobooks_paused") else ""
        self._write("Audiobooks" + extra + ":\n" + "\n".join(lines) + "\n", "sys")

    # ----- this week and patterns (what Archie keeps in mind about you) ---------------------

    def _chrome_win(self, attr, title, W, H):
        """A plain Archie window: title, a subtitle, close, draggable; returns (window, subtitle, body)."""
        px = self.px
        w = getattr(self, attr, None)
        if w is not None and w.winfo_exists():
            w.destroy()
        w = tk.Toplevel(self.root)
        setattr(self, attr, w)
        w.withdraw()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        t = tk.Label(top, text=title, bg=BG, fg=TEXT, font=(MONO, 10, "bold"))
        t.pack(side="left")
        sub = tk.Label(top, text="", bg=BG, fg=MUTED, font=(MONO, 8))
        sub.pack(side="left", padx=(px(10), 0))
        self._icon_btn(top, "close", w.destroy, "Close (Esc)").pack(side="right")
        for wd in (top, t, sub):
            wd.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
            wd.bind("<B1-Motion>", lambda e: w.geometry(
                f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))
        tk.Frame(w, bg=th.LINE, height=1).pack(fill="x")
        body = tk.Frame(w, bg=BG)
        body.pack(fill="both", expand=True)
        w.bind("<Escape>", lambda e: w.destroy())
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        W, H = min(W, sw - px(40)), min(H, sh - px(80))
        try:
            x = self.panel.winfo_x() + px(10) if self.panel_visible() else (sw - W) // 2
            y = self.panel.winfo_y() + px(10) if self.panel_visible() else (sh - H) // 2
        except tk.TclError:
            x, y = (sw - W) // 2, (sh - H) // 2
        x, y = max(0, min(x, sw - W)), max(0, min(y, sh - H - px(40)))
        w.geometry(f"{W}x{H}+{x}+{y}")
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.deiconify()
        w.lift()
        return w, sub, body

    def _bar_row(self, parent, label, frac, value, color=None, width=None):
        px = self.px
        r = tk.Frame(parent, bg=BG)
        r.pack(fill="x", pady=(0, px(5)))
        tk.Label(r, text=label, bg=BG, fg=BODY, font=(FONT, 9), width=22, anchor="w").pack(side="left")
        tk.Label(r, text=value, bg=BG, fg=MUTED, font=(MONO, 8), width=8, anchor="e").pack(side="right")
        c = tk.Canvas(r, bg=BG, height=px(6), highlightthickness=0, bd=0)
        c.pack(side="left", fill="x", expand=True, padx=(px(8), px(8)), pady=(px(4), 0))

        def draw(_e=None):
            c.delete("all")
            W = c.winfo_width()
            c.create_rectangle(0, 0, W, px(6), fill="#1f1f1f", width=0)
            c.create_rectangle(0, 0, max(0, W * min(1.0, frac)), px(6), fill=color or ACCENT, width=0)
        c.bind("<Configure>", draw)

    # this week

    def _week_material(self):
        today = datetime.date.today()
        end = today if today.weekday() == 6 else today - datetime.timedelta(days=(today.weekday() + 1) % 7)
        if today.weekday() in (0, 1):          # early in the week: sum up the week that just ended
            end = today - datetime.timedelta(days=today.weekday() + 1)
        start = end - datetime.timedelta(days=6)
        lectures = []
        vault = self.vault()
        base = vault if vault and os.path.isdir(vault) else NOTES_DIR
        for path in glob.glob(os.path.join(base, "Lectures", "*", "*.md")):
            name = os.path.basename(path)
            if name.endswith("(mind map).md"):
                continue
            day = name[:10]
            if start.isoformat() <= day <= end.isoformat():
                lectures.append((day, os.path.basename(os.path.dirname(path)) + ": " + name[11:-3]))
        chats = []
        for c in list_chats(CHATS_DIR)[:80]:
            day = str(c.get("started", ""))[:10]
            if start.isoformat() <= day <= end.isoformat():
                chats.append((day, c.get("title", "chat")))
        upcoming = [cal.describe(e, today) for e in self.calendar.upcoming(today, days=14)[:10]]
        upcoming += [f"{what}: {when:%b %d} ({days} days)" for when, what, days in self.deadlines.upcoming(today)]
        focus = mem.focus_log(self.focus.log_path)
        gyms = mem.gym_log(self.gym.log_path)
        _s, material, hours = mem.gather_week(end, focus, gyms, os.path.join(APP_DIR, "Recaps"), lectures,
                                              chats, upcoming, self.leftoff.recent(20))
        n_focus = sum(1 for e in focus if start.isoformat() <= e.get("date", "") <= end.isoformat())
        n_recaps = sum(1 for p in glob.glob(os.path.join(APP_DIR, "Recaps", "*.json"))
                       if start.isoformat() <= os.path.basename(p)[:10] <= end.isoformat())
        counts = f"{n_recaps} recap{'s' if n_recaps != 1 else ''}, {n_focus} focus session{'s' if n_focus != 1 else ''}, " \
                 f"{len(lectures)} lecture{'s' if len(lectures) != 1 else ''}, {len(chats)} chat{'s' if len(chats) != 1 else ''}"
        return start, end, material, hours, counts

    def show_week(self):
        px = self.px
        if not self.panel_visible():
            self.show_panel()
        w, sub, body = self._chrome_win("week_win", "THIS WEEK", px(620), px(max(700, self.PANEL_H + 60)))
        try:
            start, end, material, hours, counts = self._week_material()
        except Exception as e:
            tk.Label(body, text=f"Couldn't read your week: {e}", bg=BG, fg=REC, font=(MONO, 9)).pack(pady=px(40))
            return
        sub.configure(text=f"{start:%b %d} – {end:%b %d}".lower().replace(" 0", " ") + f" · {counts}")
        self._wk = {"start": start, "end": end, "hours": hours, "body": body, "win": w}
        tk.Label(body, text="reading your week...", bg=BG, fg=MUTED, font=(MONO, 9)).pack(pady=px(60))

        def work():
            try:
                draft = mem.draft_week(quick_chat, self.cfg["model"], end, material, start)
                err = None
            except Exception as e:
                draft, err = {}, str(e)
            self.bg_q.put(("call", lambda: self._week_review(draft, err)))
        threading.Thread(target=work, daemon=True).start()

    def _week_review(self, draft, err=None):
        px = self.px
        wk = getattr(self, "_wk", None)
        if not wk or not wk["win"].winfo_exists():
            return
        body = wk["body"]
        for c in body.winfo_children():
            c.destroy()
        inner = tk.Frame(body, bg=BG)
        inner.pack(fill="both", expand=True, padx=px(20), pady=(px(12), 0))
        wrap = px(620) - 2 * px(20) - px(30)
        if err:
            tk.Label(inner, text=f"I couldn't write the summary ({err}). The hours are below; try again in a bit.",
                     bg=BG, fg=REC, font=(FONT, 10), wraplength=wrap, justify="left", anchor="w").pack(fill="x")
        tk.Label(inner, text="Here's what I think is going on. Untick anything that's wrong or private; what you "
                             "keep is what I'll keep in mind this week.", bg=BG, fg=MUTED, font=(FONT, 10),
                 wraplength=wrap, justify="left", anchor="w").pack(fill="x")
        hours = wk["hours"]
        if hours:
            tk.Label(inner, text="> where your hours went", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(
                fill="x", pady=(px(12), px(5)))
            top = max(hours.values())
            for p_, m in sorted(hours.items(), key=lambda kv: -kv[1])[:6]:
                self._bar_row(inner, p_[:24], m / top if top else 0, mem.fmt_minutes(m))
        wk["vars"] = {}
        for key, label in mem.SECTIONS:
            items = draft.get(key) or []
            if not items:
                continue
            tk.Label(inner, text="> " + label, bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(
                fill="x", pady=(px(12), px(4)))
            for it in items:
                var = tk.BooleanVar(value=True)
                wk["vars"].setdefault(key, []).append((it, var))
                row = tk.Frame(inner, bg=BG)
                row.pack(fill="x", pady=(0, px(4)))
                box = tk.Label(row, text="■", bg=BG, fg=ACCENT, font=(MONO, 10), cursor="hand2")
                box.pack(side="left", anchor="n")
                lab = tk.Label(row, text=it, bg=BG, fg=BODY, font=(FONT, 10), wraplength=wrap, justify="left",
                               anchor="w", cursor="hand2")
                lab.pack(side="left", fill="x", padx=(px(8), 0))

                def flip(_e=None, var=var, box=box, lab=lab):
                    var.set(not var.get())
                    box.configure(text="■" if var.get() else "□", fg=ACCENT if var.get() else DIM)
                    lab.configure(fg=BODY if var.get() else "#5a5a56",
                                  font=(FONT, 10) if var.get() else (FONT, 10, "overstrike"))
                box.bind("<ButtonRelease-1>", flip)
                lab.bind("<ButtonRelease-1>", flip)
        if not wk["vars"] and not err:
            tk.Label(inner, text="Not much logged this week. Focus sessions, recaps and lectures are what I read.",
                     bg=BG, fg=MUTED, font=(FONT, 10), wraplength=wrap, justify="left", anchor="w").pack(
                fill="x", pady=(px(12), 0))
        row = tk.Frame(body, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(20), pady=(px(10), px(16)))
        self._fbtn(row, "keep these", lambda: self._week_keep(open_note=False), primary=True).pack(
            side="right", padx=(px(8), 0))
        self._fbtn(row, "keep + open in Obsidian", lambda: self._week_keep(open_note=True)).pack(side="right")
        self._fbtn(row, "redo", self.show_week).pack(side="left")

    def _week_keep(self, open_note=False):
        wk = self._wk
        kept = {k: [it for it, v in items if v.get()] for k, items in wk.get("vars", {}).items()}
        week_of = wk["end"].isoformat()
        self.thisweek.save(week_of, kept, wk["hours"])
        vault = self.vault()
        rel = None
        if vault and os.path.isdir(vault):
            try:
                folder = os.path.join(vault, obs.ARCHIE_FOLDER)
                os.makedirs(folder, exist_ok=True)
                with open(os.path.join(folder, "This week.md"), "w", encoding="utf-8") as f:
                    f.write(mem.week_markdown(week_of, kept, wk["hours"]))
                rel = f"{obs.ARCHIE_FOLDER}/This week.md"
            except OSError:
                rel = None
        n = sum(len(v) for v in kept.values())
        self._write(f"Got it: I'll keep {n} thing{'s' if n != 1 else ''} about your week in mind. ", "sys")
        if rel:
            self._link("open in obsidian", lambda: obs.open_in_obsidian(vault, rel), "sys")
        self._write("\n", "sys")
        if open_note and rel:
            obs.open_in_obsidian(vault, rel)
        try:
            wk["win"].destroy()
        except tk.TclError:
            pass

    # patterns

    def _patterns(self):
        return mem.patterns(mem.focus_log(self.focus.log_path), mem.gym_log(self.gym.log_path))

    def show_patterns(self):
        px = self.px
        if not self.panel_visible():
            self.show_panel()
        W = px(760)
        w, sub, body = self._chrome_win("patterns_win", "PATTERNS", W, px(max(760, self.PANEL_H + 100)))
        p = self._patterns()
        sub.configure(text=f"last {p['weeks']} weeks · {p['sessions']} focus sessions · "
                           f"{p['gym_sessions']} drawing gym rounds")
        inner = tk.Frame(body, bg=BG)
        inner.pack(fill="both", expand=True, padx=px(22), pady=(px(12), px(16)))
        tk.Label(inner, text="> when you actually get deep work done", bg=BG, fg=MUTED, font=(MONO, 8),
                 anchor="w").pack(fill="x", pady=(0, px(6)))
        H0, H1 = 7, 24
        cw = (W - 2 * px(22) - px(40)) / (H1 - H0)
        ch = px(18)
        heat = tk.Canvas(inner, bg=BG, highlightthickness=0, bd=0, height=int(ch * 7 + px(18)))
        heat.pack(fill="x")
        mx = max([max(r[H0:H1]) for r in p["heat"]] + [1])
        for d in range(7):
            heat.create_text(0, px(16) + d * ch + ch / 2, text=mem.DAY_NAMES[d][:3], fill=MUTED, font=(MONO, 7), anchor="w")
            for i, h in enumerate(range(H0, H1)):
                v = p["heat"][d][h] / mx
                x0, y0 = px(40) + i * cw, px(16) + d * ch
                if v:
                    col = _mix(BG, ACCENT, 0.12 + 0.88 * v)
                else:
                    col = "#161616"
                heat.create_rectangle(x0 + 1, y0 + 1, x0 + cw - 2, y0 + ch - 2, fill=col, width=0)
        for i, h in enumerate(range(H0, H1)):
            if h % 3 == 0:
                heat.create_text(px(40) + i * cw + cw / 2, px(6), text=mem.hour_label(h), fill="#6a6a66", font=(MONO, 7))
        tk.Label(inner, text="brighter = more focused minutes in that hour", bg=BG, fg=MUTED, font=(FONT, 9),
                 anchor="w").pack(fill="x", pady=(px(4), 0))
        if p["per_week"]:
            tk.Label(inner, text=f"> hours per project, week by week (oldest → this week)", bg=BG, fg=MUTED,
                     font=(MONO, 8), anchor="w").pack(fill="x", pady=(px(14), px(6)))
            top = max([max(v) for v in p["per_week"].values()] + [1])
            for proj, wks in list(p["per_week"].items())[:6]:
                r = tk.Frame(inner, bg=BG)
                r.pack(fill="x", pady=(0, px(4)))
                slipping = proj in p["slipping"]
                tk.Label(r, text=proj[:26], bg=BG, fg=BODY, font=(FONT, 9), width=24, anchor="w").pack(side="left")
                tk.Label(r, text=("slipping · " if slipping else "") + mem.fmt_minutes(sum(wks)), bg=BG,
                         fg="#f5a524" if slipping else MUTED, font=(MONO, 8), width=20, anchor="e").pack(side="right")
                c = tk.Canvas(r, bg=BG, height=px(18), highlightthickness=0, bd=0)
                c.pack(side="left", fill="x", expand=True, padx=(px(8), px(8)))

                def draw(_e=None, c=c, wks=wks, slipping=slipping):
                    c.delete("all")
                    Wc = c.winfo_width()
                    bw = Wc / len(wks)
                    for i, m in enumerate(wks):
                        hgt = px(16) * (m / top)
                        col = "#f5a524" if slipping and i >= len(wks) - 2 else ACCENT
                        c.create_rectangle(i * bw + 2, px(17) - max(1, hgt), (i + 1) * bw - 4, px(17),
                                           fill=col if m else "#1f1f1f", width=0)
                c.bind("<Configure>", draw)
        card = tk.Frame(inner, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(px(16), 0))
        tk.Label(card, text="what I'd suggest", bg=SURFACE, fg=ACCENT, font=(MONO, 8), anchor="w").pack(
            fill="x", padx=px(14), pady=(px(10), px(4)))
        for s_ in mem.suggestions(p):
            tk.Label(card, text="→  " + s_, bg=SURFACE, fg=BODY, font=(FONT, 10), anchor="w", justify="left",
                     wraplength=W - 2 * px(22) - px(40)).pack(fill="x", padx=px(14), pady=(0, px(6)))
        tk.Frame(card, bg=SURFACE, height=px(4)).pack()

    # ----- class capture: lecture notes, and waking the PC after class -------------------

    def _lecture_note(self, path, is_vault, text, timed):
        """Called from the listener (background) after a recording is typed out. Returns the
        note's path if it's a lecture, None to treat it as an ordinary voice note."""
        if "ideas" in [p_.lower() for p_ in re.split(r"[\\/]", os.path.dirname(path))]:
            return None                         # Ideas recordings become idea notes, never lectures
        minutes = int(self.cfg.get("lecture_minutes") or 75)
        duration = timed[-1][1] if timed else 0.0
        start = lecture.recording_start(path, duration)
        klass = lecture.folder_class(path) or lecture.class_for(start, self.calendar, minutes)
        if not (klass or lecture.in_lectures_folder(path) or duration >= lecture.LONG_ENOUGH):
            return None
        name = os.path.basename(path)
        label = lecture.recording_label(name)
        paras = lecture.paragraphs(timed)
        report = lambda f, what: self.bg_q.put(("status", f"lecture notes for {klass or name}: {what}..."))
        vault = self.vault()
        base = vault if vault and os.path.isdir(vault) else NOTES_DIR
        # The same lecture recorded on more than one device (both the whole time, or the phone died and the
        # laptop took over): stitch them into one transcript, no part twice, and rewrite that lecture's note.
        me = {"audio": name, "start": start.timestamp(), "dur": duration,
              "segs": [[round(a_, 2), round(b_, 2), x] for a_, b_, x in timed], "label": label}
        other = self._lecture_match(base, klass, start, duration, name) if klass else None
        side = self._lecture_sides()
        srcs = [me]
        if other:
            known = (side.get(os.path.normcase(other["path"])) or {}).get("sources") or [
                {"audio": other["audio"], "start": other["start"].timestamp(), "dur": other["duration"],
                 "paras": [[t, x] for t, x in other["paras"]], "label": ""}]
            srcs = [x for x in known if x["audio"] != name] + [me]
        t0, merged_segs, spans = review.stitch(srcs)
        start_all = datetime.datetime.fromtimestamp(t0) if spans else start
        dur_all = max([x["start"] + float(x.get("dur") or 0) for x in srcs]) - t0 if spans else duration
        merged = lecture.paragraphs(merged_segs) if spans else paras
        label = next((x.get("label") for x in srcs if x.get("label")), "")

        def wait():
            while self._listen_busy():
                time.sleep(2)
        try:
            data = lecture.build(quick_chat, self.cfg["model"], merged, klass, progress=report, wait=wait)
        except Exception as e:
            data = {"title": f"Lecture {start_all:%b %d}".replace(" 0", " "),
                    "summary": f"*(Archie couldn't sort this one ({e}). The full transcript is below; "
                               "ask Archie about this note to summarize it.)*",
                    "key_points": [], "topics": [], "terms": [], "todos": [], "questions": [], "mindmap": []}
        if label:
            data["title"] = label               # the name you gave it on the phone or laptop
        todos = lecture.resolve_todos(data.get("todos") or [], start_all.date(), cal.find_date)
        out = other["path"] if other else lecture.note_path(base, klass, start_all, data["title"])
        mm_stem = None
        if data.get("mindmap"):
            mm_stem = os.path.splitext(os.path.basename(out))[0] + " (mind map)"
            try:
                with open(os.path.join(os.path.dirname(out), mm_stem + ".md"), "w", encoding="utf-8") as f:
                    f.write(lecture.mindmap_file(data, todos, klass))
            except OSError:
                mm_stem = None
        first = spans[0][0] if spans else name
        md = lecture.note_markdown(data, klass=klass, start=start_all, duration=dur_all, audio_name=first,
                                   audio_in_vault=bool(is_vault), paras=merged, todos=todos, audio_path=path,
                                   mindmap_note=mm_stem)
        if len(srcs) > 1:
            md = self._stitched_md(md, spans, start_all, bool(is_vault),
                                   [x["audio"] for x in srcs if x["audio"] not in {sp[0] for sp in spans}])
        with open(out, "w", encoding="utf-8") as f:
            f.write(md)
        key = os.path.normcase(out)
        rec = side.get(key) or {}
        had = set(rec.get("todos") or [])
        added = 0
        for t in todos:
            if t["task"] in had:                # already on your list (from another recording of this lecture)
                continue
            had.add(t["task"])
            try:
                self.tasks.add(t["task"] + (f" ({klass})" if klass else ""), t.get("due"))
                added += 1
            except Exception:
                pass
        side[key] = {"sources": srcs, "todos": sorted(had), "at": time.time()}
        self._lecture_sides(side)
        self._lecture_last = {"klass": klass, "title": data["title"] + (f" (stitched from {len(spans)} recordings)" if len(spans) > 1 else ""),
                              "added": added}
        if getattr(self, "reviewer", None):
            self.reviewer.kick.set()           # line it up with the professor's material, if there is any
        if getattr(self, "examprep", None):
            self.examprep.kick.set()           # flashcards, and the exam guide if an exam is coming
        return out

    IDEA_PROMPT = """Below is the user thinking out loud (a recorded idea, typed out from speech). Turn it into a clear
idea note in Markdown, keeping THEIR ideas and wording, adding nothing the user didn't say:
## The idea
(2 to 4 sentences: what it is, in their words)
## Details
(bullets, grouped under short headings if there are several threads)
## Next steps
(things they said they'd do or should check; "none mentioned" if there are none)
## Open questions
(what the user wasn't sure about; leave the section out if there are none)
Fix obvious speech-to-text mistakes, drop filler. Output only the note.

Transcript:
"""

    def _idea_tidy(self, text):
        parts, buf = [], ""
        for para in text.split("\n\n"):
            if buf and len(buf) + len(para) > 12000:
                parts.append(buf)
                buf = ""
            buf += ("\n\n" if buf else "") + para
        if buf:
            parts.append(buf)
        out = [quick_chat(self.cfg["model"], self.IDEA_PROMPT + p_, max_tokens=4096, timeout=900, num_ctx=16384,
                          temperature=0.2) for p_ in parts]
        return "\n\n".join(o.strip() for o in out if o and o.strip())

    def _lecture_sides(self, data=None):
        """Each lecture's recordings, kept so a later one can be stitched in: lecture_sources.json."""
        p = os.path.join(APP_DIR, "lecture_sources.json")
        if data is None:
            try:
                with open(p, encoding="utf-8") as f:
                    d = json.load(f)
                return d if isinstance(d, dict) else {}
            except (OSError, ValueError):
                return {}
        if len(data) > 400:                     # keep the newest 400 lectures
            data = dict(sorted(data.items(), key=lambda kv: kv[1].get("at", 0))[-400:])
        try:
            with open(p + ".tmp", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(p + ".tmp", p)
        except OSError:
            pass

    def _lecture_match(self, base, klass, start, duration, name):
        """A lecture note for this class whose recording overlaps this one or comes within 15 minutes of it
        (the phone and the laptop both recorded it, or one took over from the other), or None."""
        d = os.path.join(base, "Lectures", re.sub(r'[<>:"/\\|?*#^\[\]]', " ", klass).strip() or "Other")
        if not os.path.isdir(d):
            return None
        a0, a1 = start.timestamp(), start.timestamp() + duration
        best = None
        for fn in os.listdir(d):
            if not fn.endswith(".md") or fn.endswith((" (review).md", " (review, rebuilt).md", "(mind map).md")):
                continue
            if fn[:10] not in (start.strftime("%Y-%m-%d"), (start - datetime.timedelta(days=1)).strftime("%Y-%m-%d")):
                continue
            lec = review.read_lecture(os.path.join(d, fn))
            if not lec or lec["audio"] == name:
                continue
            b0 = lec["start"].timestamp()
            b1 = b0 + (lec["duration"] or 0)
            gap = max(a0, b0) - min(a1, b1)    # negative when they overlap
            if gap <= 15 * 60 and (best is None or gap < best[0]):
                best = (gap, lec)
        return best[1] if best else None

    @staticmethod
    def _stitched_md(md, spans, start_all, in_vault, unused=()):
        """Name every recording in a stitched lecture note, and which part of the lecture came from each."""
        fmt = lambda s: (f"{int(s) // 3600}:{int(s) % 3600 // 60:02d}:{int(s) % 60:02d}" if s >= 3600
                         else f"{int(s) // 60:02d}:{int(s) % 60:02d}")
        recs = ";".join(f"{a}@{off:.0f}" for a, off, _, _ in spans)
        md = md.replace("\n---\n", f'\nrecordings: "{recs}"\nseconds: {start_all.second}\n---\n', 1)
        line = ("> Stitched from " + str(len(spans)) + " recordings: " +
                " · ".join(f"[[{a}]] {fmt(f)}–{fmt(t)}" for a, _, f, t in spans) +
                " (where they overlapped, the part that heard more was used)") if len(spans) > 1 else ""
        if unused:
            line += ("\n" if line else "") + "> Also recorded: " + ", ".join(f"[[{a}]]" for a in unused) + \
                " (the other recording heard more, so the notes use it)"
        anchor = "> Recorded on your phone, typed out and sorted on your PC by Archie."
        md = md.replace(anchor, anchor + "\n" + line, 1) if line else md
        if in_vault:
            first = f"![[{spans[0][0]}]]"
            md = md.replace(first, "\n".join(f"![[{a}]]" for a, _, _, _ in spans), 1)
        return md

    def _newsroll_loop(self):
        """The news notes fold up as they age: days -> weeks -> months (archie_newsroll.py). At start, then every 3 hours."""
        time.sleep(90)
        while True:
            try:
                vault = self.vault()
                if vault and os.path.isdir(vault):
                    newsroll.roll(vault, quick_chat, self.cfg["model"],
                                  report=lambda m: self.bg_q.put(("status", m)))
            except Exception:
                pass
            time.sleep(3 * 3600)

    def _lecture_hint(self, path):
        """Whisper's spelling list for a recording: terms from its class's material."""
        if not getattr(self, "reviewer", None):
            return None
        try:
            klass = lecture.folder_class(path) or lecture.class_for(
                lecture.recording_start(path), self.calendar, int(self.cfg.get("lecture_minutes") or 75))
        except Exception:
            klass = None
        return self.reviewer.hint(path, klass) if klass else None

    def _review_wait(self):
        while self._listen_busy() or self.listener.running.is_set():
            time.sleep(3)

    def _review_vision(self, data, what):
        """Read a picture (a scanned page or a board photo) with the vision model."""
        import base64, tempfile
        model = pick_vision_model(self.cfg["model"])
        fd, tmp = tempfile.mkstemp(suffix=".jpg" if data[:2] == b"\xff\xd8" else ".png")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            b64 = read_image_b64(tmp)
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
        ask = ("Type out everything written on this whiteboard or chalkboard: words, formulas, diagrams "
               "described in a few words. Plain text, no comments." if what == "board" else
               "Type out all the text on this page exactly, in reading order. Plain text, no comments.")
        from archie_brain import _post
        import json as _j
        with _post("/api/chat", {"model": model, "stream": False, "options": {"num_predict": 1500, "temperature": 0.1},
                                 "messages": [{"role": "user", "content": ask, "images": [b64]}]}, timeout=600) as r:
            return (_j.load(r).get("message", {}).get("content") or "").strip()

    def _review_transcribe(self, path):
        timed = []
        self._bg_transcriber().transcribe(path, pause=self._listen_busy, timed=timed)
        return timed

    SCHOOL_DAY = [
        ("Morning", "Open me and read the brief: your countdowns, today's classes, to-dos from yesterday's "
                    "lectures with due dates, and last night's recap. Then put the PC to sleep (not shut down)."),
        ("In class", "When the lecture starts, tap the microphone in Obsidian on your phone. Tap it again when it "
                     "ends. That's all."),
        ("While you're out", "About 20 minutes after class, the PC wakes itself (if wake after class is on), "
                             "the recording syncs, and I write the lecture note: summary, key points with times, "
                             "notes, terms, to-dos, questions, a mind map. Homework goes on your to-do list. Then "
                             "the PC goes back to sleep."),
        ("Home", "Every lecture is in Obsidian under Lectures. Skim the summary, jump to a time in the recording "
                 "if something didn't click, and with the note open type  make flashcards from this note  or "
                 "ask me about  this note."),
        ("Homework", "focus: <what you're working on>  starts the owl timer; it goes in your daily note."),
        ("Drawing", "gym  for 15 minutes of timed references (the class ladder is a good warm-up). It keeps "
                    "your streak."),
        ("Night", "Click the moon (recap) and talk for a minute. Tomorrow's brief picks it up."),
    ]

    def _help_items(self):
        hk = lambda k: pretty_combo(self.cfg.get(k) or "") or "(no hotkey)"
        return [
            ("Talking and learning", [
                ("Ask anything", "type and press Enter. The tabs change how I answer: Tutor, Professor, Code, "
                                 "Robotics, Writing.", None),
                ("Talk out loud", f"{hk('hotkey_talk')}, speak, then press it again. Turn on  speak  to hear every answer.", None),
                ("Look things up", "notes  searches your Notes, past chats and Obsidian;  wiki  uses offline Wikipedia.", None),
                ("Ask about your screen", f"snip  or {hk('hotkey_snip')}, then drag a box around anything.", self.start_snip),
                ("Files and photos", "drag them onto the chat or use  + attach : PDFs, Word, code, photos of handwriting.", None),
            ]),
            ("Studying", [
                ("Flashcards", "study  to review.  make flashcards about <topic>  or  ... from this note.", lambda: self.show_study(None)),
                ("Mock exams", "make a mock exam on <topic>  (timed) or  make a practice quiz on <topic>.", None),
                ("Books", "quiz me on <book> chapter 3.  audiobooks  shows how the typing-out is going.", None),
                ("The Vault", "vault  opens the offline library: every pack on a shelf, its own front page, search across all of it, "
                              "a random page, three picks for today, and flashcards from any page.  vault <words>  searches it.",
                 lambda: self.show_vault()),
                ("Lectures", "record a class with the mic in Obsidian on your phone; the notes land in Lectures. "
                             "school day  walks through it.", self._open_lectures),
            ]),
            ("Your day", [
                ("Morning brief", "the sun icon at the top: countdowns, classes, to-dos, last night's recap.", self.show_brief),
                ("To-dos", "add: <task> <date>,  done: <a word from it>,  tasks  to see them.", None),
                ("Calendar", "click the date, or type  exam: bio midterm oct 12 9am  /  class: <name> mondays 6pm. "
                             "The week view shows classes, recordings, due dates, focus and your best hours, color coded.",
                 lambda: self.show_calendar()),
                ("Daily note", "daily  opens today's Obsidian note;  log: <what happened>  adds a line.", None),
                ("Focus timer", "focus, or  focus: <task>  to start right away. When it ends, jot where you stopped "
                                "and what's next; it comes back next time and in the brief.", lambda: self.show_focus()),
                ("This week", "this week  sums up what you're working on and what's stalling; you keep or cut each "
                              "line and I keep the rest in mind. Offered every Sunday.", lambda: self.show_week()),
                ("Patterns", "patterns  shows when you do your best work, where your hours go and what's slipping.",
                 lambda: self.show_patterns()),
                ("Evening recap", f"the moon, type  recap, or {hk('hotkey_recap')}. Talk for a minute about your day.", None),
            ]),
            ("Making", [
                ("Pictures", "draw <anything>, or right-click the owl > Make an image.", lambda: self.show_imagine()),
                ("Sketch to image", "sketch  turns your drawing into a finished picture in 20 styles.", lambda: self.show_sketch()),
                ("Drawing gym", "gym  for timed reference practice from your own folder of pictures.", lambda: self.show_gym()),
                ("Code files", "make a godot script called player.gd that moves with WASD", None),
                ("Open apps", "open blender, open my notes folder", None),
            ]),
            ("The world (online)", [
                ("Archie World", "world  opens the globe: conflict reports from both sides (Telegram and local papers, "
                                 "translated), disasters, weather radar, pipelines, straits and markets. Zoom in for street maps.",
                 lambda: self.show_world()),
                ("Ask the map", "world <question>, like  world what's happening near Hormuz. Answers cite the reports.", None),
                ("News brief", "news  opens the news brief, written fresh at 6 am: the world, at home, close to home, and the "
                               "topics you follow. When big stories break later, a refresh bar shows up in it.", lambda: self.show_world("brief")),
                ("What's new", "whats new  (or the lime  N new since…  button on the globe) lists everything that came in "
                               "since you last looked; new things glow on the map.", lambda: self.show_world("new")),
                ("News quiz", "news quiz  (or  quiz me on the news ) asks 5 questions from the biggest stories of the day or week.",
                 lambda: self.show_world("quiz")),
                ("World lessons", "teach me  on any story, or  news lesson on <topic> : a short class on it (background, "
                                  "who's involved, words to know, check questions). Save it to Archie/World/Lessons.", None),
                ("Solar system", "solar system  (or the  solar system  button on the globe) shows an orrery with every planet where "
                                 "it really is today, the Sun's space weather, Mars weather from Curiosity, and 30+ spacecraft from "
                                 "every country; search it, or ask  where is Voyager 1 .", lambda: self.show_world("solar")),
                ("Governments", "governments  (button next to layers, or  who runs France ) opens a briefing on every country: who holds office, "
                                "the cabinet, parliament and seats, courts, elections, economy and military, plus a world map you can color by "
                                "how each country is run, its next vote, or how long its leader has been in office.", lambda: self.show_world("gov=")),
                ("Lawmaking", "lawmaking ,  bill tracker ,  executive orders ,  how did <name> vote ,  who funds <name> : every bill and where it stands, "
                              "every recorded vote and who cast it (US Congress, UK, EU Parliament, Canada, Ireland, France, Germany, Spain, Poland, "
                              "Brazil, Switzerland, Finland, Denmark, Netherlands, Estonia), each lawmaker's record, campaign money from the FEC, "
                              "plain-English summaries.  my reps  finds your representatives;  political calendar  shows hearings and elections.",
                 lambda: self.show_world("gov=law")),
                ("Space archive", "people in space ,  golden record ,  golden record album ,  mission planner : the solar system's archive menu "
                                  "(also under  archive ▾  in the solar system). Or  andromeda merger  to play the collision.", lambda: self.show_world("archive=people")),
                ("Milky Way", "milky way  (or scroll all the way out of the solar system) shows the galaxy with every known planet "
                              "outside our solar system from NASA's Exoplanet Archive, plus nebulae and star clusters; click any "
                              "system for its star and planets, or ask  star system TRAPPIST-1 .", lambda: self.show_world("galaxy")),
                ("Wrong label?", "if a map icon is wrong (a pig story marked shelling), open it and press  wrong label? . "
                                 "Pick a telling word and Archie remembers. Undo in Sources.", None),
                ("Morning note", "morning note  (or  markets ) opens the markets briefing Archie writes after 6 am.",
                 lambda: self.show_world("note")),
                ("Watch and alerts", "star an area, country, strait, pipeline or price on the globe; I pop up a note when "
                                     "something confirmed happens there.", None),
                ("Save articles", "save  on any report keeps a picture of the headline plus a note with the link and text "
                                  "in World\\Saved Articles.", lambda: self._open_saved_articles()),
                ("Catch me up", "catch me up  on any story (or type  catch me up on <topic> ) shows how it developed day by day "
                                "over two weeks, with the story so far and what's new since yesterday.", None),
                ("Background", "background  on any card (a story, armed group, country, strait, pipeline, stock index, "
                               "central bank) explains who and what it is, from your offline Wikipedia.", None),
                ("World calendar", "world calendar : elections, central-bank decisions, big economic numbers, big earnings "
                                   "and rocket launches for the next 60 days; add any to your calendar.", lambda: self.show_world("calendar")),
                ("Nightly digest", "every night the day's confirmed events go into Archie/World in your vault, with links "
                                   "back to the globe.", None),
                ("Weekly review", "Sunday night: Archie/World/Weekly gets the week's fighting trends by region (with a chart), "
                                  "biggest stories, what grew and faded, markets and disasters.  world review  writes it now.",
                 lambda: self._world_weekly()),
            ]),
            ("Obsidian and your notes", [
                ("The note you have open", "quiz me on this note,  summarize this note,  what's missing from this note, "
                                           "make flashcards from this note.", None),
                ("Search everything you've written", "turn on  notes  and I search your Notes folder, your whole vault "
                                                     "and past chats, and show where each answer came from (src:).", None),
                ("Daily note", "daily  opens today's note with your to-dos;  log: <what happened>  adds a timestamped "
                               "line. Focus sessions, the drawing gym and recaps log there too, while  To-dos in "
                               "Obsidian daily note  is on.", None),
                ("Save to your vault", "save → obsidian  under any answer, or right-click the owl > Save this chat. "
                                       "Saved notes link to related ones, so they join the graph.", None),
                ("Linked wiki", "build wiki  turns a whole conversation into a set of linked notes.", None),
                ("Handwriting", "photos, scans or Surface pen pages in Notes\\Handwritten or your vault get read by "
                                "themselves, so your handwriting becomes searchable.", None),
                ("Voice notes", "record with the mic in Obsidian on your phone (or drop audio in a Voice inbox); it comes "
                                "back typed out and tidied, next to the recording.", None),
                ("Lectures", "recordings from class become full notes in Lectures/<class>, plus an editable mind map "
                             "for the Mindmap plugin.", self._open_lectures),
                ("Books", "put an EPUB, PDF or audiobook in Notes, then  quiz me on <book> chapter 3.", None),
                ("Pictures", "save any picture you make to Obsidian; your Excalidraw and handwritten sketches show up "
                             "in the sketch window.", None),
            ]),
        ]

    # ----- Archie World --------------------------------------------------------

    def show_workshop(self):
        if not self.world or not getattr(self.world, "workshop", None):
            why = getattr(self, "_world_err", "") or getattr(self.world, "workshop_err", "") if self.world else getattr(self, "_world_err", "")
            self._write("The Workshop isn't running" + (f" ({why})" if why else "") + ". It needs archie_workshop.py and Archie World.\n", "sys")
            return
        self.world.open_workshop()

    def show_vault(self, hash_=""):
        if not self.world or not getattr(self.world, "vaultlib", None):
            why = getattr(self.world, "vault_err", "") if self.world else getattr(self, "_world_err", "")
            self._write("The Vault isn't running" + (f" ({why})" if why else "") + ". It needs archie_vault.py and Archie World.\n", "sys")
            return
        self.world.open_vault(hash_)

    def show_world(self, hash_=""):
        if not self.world:
            why = getattr(self, "_world_err", "")
            self._write("Archie World isn't running" + (f" ({why})" if why else "") +
                        ". It needs archie_world.py and the World folder next to Archie.\n", "sys")
            return
        self.world.open_window(hash_)

    def _world_weekly(self):
        if not self.world or not self.vault():
            self._write("The weekly review needs Archie World running and your Obsidian vault chosen.\n", "sys")
            return
        self._write("Writing this week's world review...\n", "sys")

        def work():
            try:
                path = self.world.maybe_weekly(force=True)
            except Exception as e:
                path, err = None, str(e)
            else:
                err = "" if path else "there's nothing stored for the week yet"
            self.bg_q.put(("call", lambda: self._world_weekly_done(path, err)))
        threading.Thread(target=work, daemon=True).start()

    def _world_weekly_done(self, path, err):
        if not path:
            self._write(f"I couldn't write the weekly review: {err}.\n", "sys")
            return
        rel = os.path.relpath(path, self.vault())
        self._write("The weekly review is in Obsidian: " + rel.replace("\\", "/") + "  ", "sys")
        self._link("open it", lambda: obs.open_in_obsidian(self.vault(), rel), "sys")
        self._write("\n", "sys")

    def _open_saved_articles(self):
        if world:
            os.makedirs(world.SAVED_DIR, exist_ok=True)
            open_folder(world.SAVED_DIR)

    def _world_alerts(self):
        """Every 30 s: pop up new watchlist alerts from Archie World."""
        try:
            for a in (self.world.pop_alerts() if self.world else []):
                self._world_toast(a)
        except Exception:
            pass
        self.root.after(30000, self._world_alerts)

    def _world_toast(self, a):
        px = self.px
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        self._toasts = [t for t in getattr(self, "_toasts", []) if t.winfo_exists()] + [w]
        W_, H_ = px(360), px(92)
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        w.geometry(f"{W_}x{H_}+{sw - W_ - px(18)}+{sh - (H_ + px(10)) * len(self._toasts) - px(56)}")
        w.after(60, lambda: th.round_corners(w, px(10)))
        tk.Frame(w, bg=ACCENT, width=px(4)).pack(side="left", fill="y")
        body = tk.Frame(w, bg=BG, cursor="hand2")
        body.pack(side="left", fill="both", expand=True, padx=px(12), pady=px(9))
        when = datetime.datetime.fromtimestamp(a["time"]).strftime("%I:%M %p").lstrip("0").lower()
        tk.Label(body, text="ARCHIE WORLD · " + when, bg=BG, fg=ACCENT, font=(MONO, 8, "bold"), anchor="w").pack(fill="x")
        tk.Label(body, text=a["title"][:120], bg=BG, fg=TEXT, font=(FONT, 10), anchor="w", justify="left",
                 wraplength=px(320)).pack(fill="x")
        tk.Label(body, text=(a.get("body") or "") + "  ·  click to see it", bg=BG, fg=DIM, font=(MONO, 8),
                 anchor="w").pack(fill="x")

        def close(_e=None):
            if w.winfo_exists():
                w.destroy()

        def go(_e=None):
            self.show_world(a.get("hash") or "")
            close()
        for wid in [body] + list(body.winfo_children()):
            wid.bind("<Button-1>", go)
            wid.bind("<Button-3>", close)
        w.after(15000, close)

    def show_help(self):
        """Everything Archie can do, in the same layout as the school day."""
        if not self.panel_visible():
            self.show_panel()
        top = self.chat.index("end-1c")
        self._write("Everything I can do:\n", "abody")
        for group, items in self._help_items():
            self._write(group.lower() + "\n", "b_head")
            for label, what, action in items:
                self._write(f"  {label}: ", "b_hot")
                self._write(what + "  ", "abody")
                if action:
                    self._link("open", action, "abody")
                self._write("\n", "abody")
        hk = lambda k: pretty_combo(self.cfg.get(k) or "")
        keys = [(hk("hotkey_chat"), "open or hide me"), (hk("hotkey_snip"), "snip"), (hk("hotkey_voice"), "voice note"),
                (hk("hotkey_talk"), "talk"), (hk("hotkey_recap"), "recap")]
        keys = [f"{k} {v}" for k, v in keys if k]
        if keys:
            self._write("keys: " + "  ·  ".join(keys) + "\n", "sys")
        self._write("More: type  school day  for a class day start to finish, or ", "sys")
        self._link("open the full manual", self.open_manual, "sys")
        self._write(".\n", "sys")
        self.root.after_idle(lambda: self.chat.yview(top))     # start at the top of the list

    def _school_day(self):
        self._write("A school day with Archie:\n", "abody")
        for when, what in self.SCHOOL_DAY:
            self._write(f"  {when}: ", "b_hot")
            self._write(what + "\n", "abody")
        on = "on" if self.cfg.get("lecture_wake") else "off (type  wake after class on)"
        self._write(f"Wake after class is {on}. Add classes like  class: intro to animation mondays 6pm. "
                    "Before relying on it, test one long recording with your phone locked, and check each "
                    "syllabus about recording.\n", "sys")

    def _open_lectures(self):
        vault = self.vault()
        base = vault if vault and os.path.isdir(vault) else NOTES_DIR
        folder = os.path.join(base, "Lectures")
        os.makedirs(folder, exist_ok=True)
        open_folder(folder)

    def _lecture_launch_cmd(self):
        exe = sys.executable
        if exe.lower().endswith("python.exe"):
            w = exe[:-len("python.exe")] + "pythonw.exe"
            if os.path.exists(w):
                exe = w
        return exe, f'"{os.path.abspath(__file__)}" --lecture-wake', APP_DIR

    def _lecture_sync_wake(self, quiet=False):
        """Make Windows' wake-up tasks match the weekly classes on the calendar."""
        plan = lecture.wake_plan(self.calendar, int(self.cfg.get("lecture_minutes") or 75))
        sig = json.dumps([(k, wd, [t.strftime("%H:%M") for t in ts]) for k, wd, ts, _ in plan])
        if quiet and sig == getattr(self, "_lecture_sig", None):
            return
        self._lecture_sig = sig
        state = os.path.join(APP_DIR, "lecture_wake.json")
        if not plan:
            lecture.clear_wake_tasks(state)
            if not quiet:
                self._write("Wake after class is on, but there are no weekly classes on your calendar yet. "
                            "Add them like  class: intro to animation mondays 6pm  and I'll set the wake-ups.\n", "sys")
            return
        cmd, args, wd = self._lecture_launch_cmd()

        def work():
            try:
                made, problems = lecture.set_wake_tasks(plan, cmd, args, wd, state, APP_DIR)
            except Exception as e:
                made, problems = 0, [str(e)]
            self.bg_q.put(("call", lambda: self._lecture_synced(plan, made, problems, quiet)))
        threading.Thread(target=work, daemon=True).start()

    def _lecture_synced(self, plan, made, problems, quiet):
        if problems:
            self._write("I couldn't set every wake-up: " + "; ".join(problems[:3]) + "\n", "sys")
        if (quiet and not problems) or not made:
            return
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        lines = [f"  {k}, {days[wd]}: wakes at {ts[0].strftime('%I:%M %p').lstrip('0').lower()}"
                 for k, wd, ts, _ in plan]
        self._write(f"Wake after class is on ({made} class{'es' if made != 1 else ''}). The PC wakes about "
                    f"20 minutes after each one, types up the recording, then goes back to sleep:\n"
                    + "\n".join(lines) + "\n"
                    "One-time Windows step: Control Panel > Power Options > Change plan settings > Change "
                    "advanced power settings > Sleep > Allow wake timers > Enable.\n", "sys")

    def _lecture_wake_toggle(self, on):
        self.cfg["lecture_wake"] = bool(on)
        save_config(self.cfg)
        try:
            self.lecture_wake_var.set(bool(on))
        except Exception:
            pass
        if on:
            self._lecture_sig = None
            self._lecture_sync_wake(quiet=False)
        else:
            lecture.clear_wake_tasks(os.path.join(APP_DIR, "lecture_wake.json"))
            self._lecture_sig = None
            self._write("Wake after class is off. The PC won't wake up for classes anymore.\n", "sys")

    def _lecture_woke(self):
        """Windows woke the PC after a class: let Obsidian sync, type up the lecture, then sleep."""
        self._woke_at = time.time()
        try:
            if not lecture.obsidian_running():
                os.startfile("obsidian://open")
        except Exception:
            pass
        self.listener.start()
        if not getattr(self, "_wake_checking", False):
            self._wake_checking = True
            self.root.after(60000, self._wake_check)

    def _wake_check(self):
        t0 = getattr(self, "_woke_at", None)
        if not t0:
            self._wake_checking = False
            return
        mins = (time.time() - t0) / 60
        self.listener.start()
        try:
            waiting = bool(self.listener.voice_notes())
        except Exception:
            waiting = False
        working = self.listener.running.is_set() or waiting
        if mins < 12 or (working and mins < 120):       # give the phone time to sync, then finish the note
            self.root.after(60000, self._wake_check)
            return
        self._woke_at = None
        self._wake_checking = False
        if self.cfg.get("lecture_sleep_after", True) and lecture.idle_seconds() >= 600 and not self.busy:
            lecture.sleep_pc()

    # ----- the drawing gym (timed reference practice) --------------------------------

    def show_gym(self):
        px = self.px
        self._mini_exit()
        w = getattr(self, "gym_win", None)
        if w is None or not w.winfo_exists():
            w = self._build_gym_win()
        if getattr(self, "_gs", None) and self._gs.get("plan") and not self._gs.get("over"):
            w.deiconify()
            w.lift()
            return
        self._gym_setup()
        w.deiconify()
        w.lift()
        w.focus_force()
        self.gym.sort_new(lambda k, v: self.bg_q.put((k, v)))

    def _build_gym_win(self):
        px = self.px
        w = self.gym_win = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        gw = self._gw = {}
        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        gw["title"] = tk.Label(top, text="DRAWING GYM", bg=BG, fg=TEXT, font=(MONO, 10, "bold"))
        gw["title"].pack(side="left")
        gw["sub"] = tk.Label(top, text="", bg=BG, fg=MUTED, font=(MONO, 8))
        gw["sub"].pack(side="left", padx=(px(10), 0))
        self._icon_btn(top, "close", self._gym_close, "Close (Esc)").pack(side="right")
        for wd in (top, gw["title"], gw["sub"]):
            wd.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
            wd.bind("<B1-Motion>", lambda e: w.geometry(
                f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))
        tk.Frame(w, bg=th.LINE, height=1).pack(fill="x")
        gw["body"] = tk.Frame(w, bg=BG)
        gw["body"].pack(fill="both", expand=True)
        w.bind("<Escape>", lambda e: self._gym_escape())
        w.bind("<space>", lambda e: self._gym_key("space"))
        w.bind("<Right>", lambda e: self._gym_key("next"))
        w.bind("<Left>", lambda e: self._gym_key("back"))
        w.bind("<Return>", lambda e: self._gym_key("enter"))
        w.bind("<KeyPress-m>", lambda e: self._gym_key("mirror"))
        w.bind("<KeyPress-g>", lambda e: self._gym_key("gray"))
        return w

    def _gym_place(self, W, H):
        w = self.gym_win
        px = self.px
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        W, H = min(W, sw - px(40)), min(H, sh - px(80))
        try:
            x = self.panel.winfo_x() + px(10) if self.panel_visible() else (sw - W) // 2
            y = self.panel.winfo_y() + px(10) if self.panel_visible() else (sh - H) // 2
        except tk.TclError:
            x, y = (sw - W) // 2, (sh - H) // 2
        x, y = max(0, min(x, sw - W)), max(0, min(y, sh - H - px(40)))
        w.geometry(f"{W}x{H}+{x}+{y}")
        w.update_idletasks()
        th.round_corners(w, px(12))

    def _gym_clear(self):
        for c in self._gw["body"].winfo_children():
            c.destroy()

    def _gym_sub(self):
        st = self.gym.stats()
        bits = []
        if st["streak"]:
            bits.append(f"{st['streak']}-day streak")
        if st["week_poses"]:
            bits.append(f"{st['week_poses']} this week")
        self._gw["sub"].configure(text="  ·  ".join(bits))

    # setup: what to draw, how long, how many

    def _gym_setup(self):
        px = self.px
        self._gs = None
        self._gym_clear()
        self._gym_place(px(470), px(max(640, self.PANEL_H)))
        self._gw["title"].configure(text="DRAWING GYM")
        self._gym_sub()
        body = self._gw["body"]
        g = self._gsel = getattr(self, "_gsel", None) or {
            "cats": set(self.cfg.get("gym_cats") or []),
            "time": self.cfg.get("gym_time", 60),
            "count": int(self.cfg.get("gym_count", 10))}
        inner = tk.Frame(body, bg=BG)
        inner.pack(fill="both", expand=True, padx=px(18), pady=(px(12), 0))
        maxw = px(470) - 2 * px(18)

        def head(text):
            tk.Label(inner, text=text, bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(fill="x", pady=(px(10), px(5)))

        head("> what to draw")
        cats_box = tk.Frame(inner, bg=BG)
        cats_box.pack(fill="x")
        self._gw["cats_box"] = cats_box
        self._gw["folder_line"] = tk.Label(inner, text="", bg=BG, fg=DIM, font=(MONO, 8), anchor="w",
                                           justify="left", wraplength=maxw)
        self._gw["folder_line"].pack(fill="x", pady=(px(2), 0))
        self._gym_draw_cats()

        head("> time per picture")
        opts = [lbl for _, lbl in gym.TIMES] + ["class ladder"]
        cur = "class ladder" if g["time"] == "ladder" else dict(gym.TIMES).get(g["time"], "1 min")
        time_box = tk.Frame(inner, bg=BG)
        time_box.pack(fill="x")

        def pick_time(label):
            g["time"] = "ladder" if label == "class ladder" else next(s for s, l in gym.TIMES if l == label)
            self._gym_summary()
        self._chip_row(time_box, opts, cur, pick_time, max_width=maxw)
        self._gw["time_hint"] = tk.Label(inner, text="", bg=BG, fg=DIM, font=(MONO, 8), anchor="w",
                                         justify="left", wraplength=maxw)
        self._gw["time_hint"].pack(fill="x", pady=(px(2), 0))

        wrap = self._gw["count_wrap"] = tk.Frame(inner, bg=BG)
        wrap.pack(fill="x")
        tk.Label(wrap, text="> how many", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(
            fill="x", pady=(px(10), px(5)))
        count_box = tk.Frame(wrap, bg=BG)
        count_box.pack(fill="x")
        labels = {5: "5", 10: "10", 20: "20", 0: "all"}

        def pick_count(label):
            g["count"] = next(k for k, v in labels.items() if v == label)
            self._gym_summary()
        self._gw["count_paint"] = self._chip_row(count_box, list(labels.values()), labels.get(g["count"], "10"),
                                                 pick_count, max_width=maxw)

        card = self._gw["card"] = tk.Frame(inner, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(px(16), 0))
        self._gw["summary"] = tk.Label(card, text="", bg=SURFACE, fg=TEXT, font=(MONO, 10), anchor="w")
        self._gw["summary"].pack(fill="x", padx=px(12), pady=(px(10), px(2)))
        st = self.gym.stats()
        line = (f"streak {st['streak']} day{'s' if st['streak'] != 1 else ''}  ·  this week {st['week_poses']} "
                f"picture{'s' if st['week_poses'] != 1 else ''}, {st['week_minutes']} min") if st["total_poses"] else "your first session: have fun with it"
        tk.Label(card, text=line, bg=SURFACE, fg=MUTED, font=(MONO, 8), anchor="w").pack(
            fill="x", padx=px(12), pady=(0, px(10)))
        self._gw["thumbs"] = tk.Frame(inner, bg=BG)
        self._gw["thumbs"].pack(fill="x", pady=(px(12), 0))

        row = tk.Frame(body, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(18), pady=(px(10), px(18)))
        self._gw["start"] = self._fbtn(row, "start", self._gym_start, primary=True)
        self._gw["start"].pack(side="left", fill="x", expand=True)
        self._fbtn(row, "open folder", self._gym_open_folder).pack(side="right", padx=(px(8), 0))
        self._gym_summary()

    def _gym_draw_cats(self):
        px = self.px
        box = self._gw.get("cats_box")
        if not box or not box.winfo_exists():
            return
        for c in box.winfo_children():
            c.destroy()
        counts, unsorted = self.gym.counts()
        total = sum(counts.values())
        g = self._gsel
        g["cats"] = {c for c in g["cats"] if counts.get(c)}
        font = tkfont.Font(family=MONO, size=8)
        maxw = px(470) - 2 * px(18)
        row, used = None, 0
        items = [("all", "all", total)] + [(k, lbl, counts[k]) for k, lbl, _ in gym.CATEGORIES if counts[k]]
        for key, label, n in items:
            text = f"{label} {n}"
            wid = font.measure(text) + px(23)
            if row is None or used + wid > maxw:
                row = tk.Frame(box, bg=BG)
                row.pack(fill="x", pady=(0, px(5)))
                used = 0
            used += wid
            on = (not g["cats"]) if key == "all" else key in g["cats"]
            b = tk.Label(row, text=text, bg=INPUT_BG if on else BG, fg=ACCENT if on else DIM, font=(MONO, 8),
                         padx=px(8), pady=px(4), cursor="hand2", highlightthickness=1,
                         highlightbackground=ACCENT if on else BORDER, highlightcolor=ACCENT if on else BORDER)
            b.pack(side="left", padx=(0, px(5)))
            b.bind("<ButtonRelease-1>", lambda e, k=key: self._gym_toggle_cat(k))
        if not total and not unsorted:
            msg = ("Drop pictures into the Drawing Gym folder (poses, faces, hands, animals, landscapes...). "
                   "Archie sorts them by itself.")
        elif unsorted and self.gym.sorting.is_set():
            msg = f"sorting {unsorted} new picture{'s' if unsorted != 1 else ''}... (they join in as they're sorted)"
        elif unsorted:
            msg = f"{unsorted} picture{'s' if unsorted != 1 else ''} not sorted yet" + (
                f": {self.gym.last_error}" if self.gym.last_error else "")
        else:
            msg = ""
        self._gw["folder_line"].configure(text=msg)
        if msg:
            self._gw["folder_line"].pack(fill="x", pady=(px(2), 0))
        else:
            self._gw["folder_line"].pack_forget()

    def _gym_toggle_cat(self, key):
        g = self._gsel
        if key == "all":
            g["cats"] = set()
        elif key in g["cats"]:
            g["cats"].discard(key)
        else:
            g["cats"].add(key)
        self._gym_draw_cats()
        self._gym_summary()

    def _gym_pool(self):
        g = self._gsel
        return [p for p, c in self.gym.pictures() if c and (not g["cats"] or c in g["cats"])]

    def _gym_summary(self):
        if not self._gw.get("summary") or not self._gw["summary"].winfo_exists():
            return
        g = self._gsel
        n_pool = len(self._gym_pool())
        ladder = g["time"] == "ladder"
        if ladder:
            n = min(n_pool, len(gym.LADDER))
            secs = sum(gym.LADDER[:n])
            hint = "8 × 30 s, 4 × 1 min, 2 × 2 min, 2 × 5 min: quick gestures first, then longer poses, like a figure class"
        else:
            n = min(n_pool, g["count"]) if g["count"] else n_pool
            secs = n * g["time"]
            hint = ("no clock: take as long as you like, then press next (→)" if not g["time"] else
                    "gesture: catch the whole pose, no details" if g["time"] <= 60 else
                    "shapes and proportions, a little shading" if g["time"] <= 120 else
                    "a proper study: structure, then values")
        self._gw["time_hint"].configure(text=hint)
        if ladder:
            self._gw["count_wrap"].pack_forget()
        else:
            self._gw["count_wrap"].pack(fill="x", before=self._gw["card"])
        if not n:
            text = "no pictures yet" if not self.gym.pictures() else "nothing sorted in that category yet"
        else:
            length = "no timer" if (not ladder and not g["time"]) else f"about {max(1, round(secs / 60))} min"
            text = f"{n} picture{'s' if n != 1 else ''}  ·  {length}"
        self._gw["summary"].configure(text=text)
        self._gym_thumbs()
        self._gw["start"].configure(fg=TILE if n else "#4a5a14")
        self.cfg.update(gym_cats=sorted(g["cats"]), gym_time=g["time"], gym_count=g["count"])

    def _gym_thumbs(self):
        """A peek at the pictures in the set you picked."""
        px = self.px
        box = self._gw.get("thumbs")
        if not box or not box.winfo_exists():
            return
        for c in box.winfo_children():
            c.destroy()
        pool = sorted(self._gym_pool(), key=lambda p: os.path.getmtime(p), reverse=True)
        if not pool:
            return
        n = 5
        side = (px(470) - 2 * px(18) - (n - 1) * px(6)) // n
        cache = self.__dict__.setdefault("_gym_thumb_cache", {})
        from PIL import Image, ImageOps, ImageTk
        for i, path in enumerate(pool[:n]):
            key = (path, side, os.path.getmtime(path))
            if key not in cache:
                try:
                    with Image.open(path) as im:
                        im = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), (side, side))
                    if len(cache) > 60:
                        cache.clear()
                    cache[key] = ImageTk.PhotoImage(im)
                except Exception:
                    continue
            tk.Label(box, image=cache[key], bg=BG, bd=0).pack(side="left", padx=(0 if i == 0 else px(6), 0))
        more = len(pool) - n
        if more > 0:
            tk.Label(box, text=f"+{more}", bg=BG, fg=MUTED, font=(MONO, 8)).place(relx=1.0, rely=1.0, anchor="se")

    def _gym_open_folder(self):
        os.makedirs(GYM_DIR, exist_ok=True)
        open_folder(GYM_DIR)

    # the session

    def _gym_start(self, again=False):
        g = self._gsel
        save_config(self.cfg)
        ladder = g["time"] == "ladder"
        picks = self._gym_pool()
        random.shuffle(picks)
        n = len(gym.LADDER) if ladder else g["count"]
        picks = picks[:n] if n else picks
        if not picks:
            self._gym_draw_cats()
            return
        plan = gym.plan(picks, g["time"] if not ladder else 0, ladder=ladder)
        self._gs = {"plan": plan, "i": 0, "paused": False, "mirror": False, "gray": False,
                    "left": plan[0][1], "last": time.monotonic(), "shown": 0.0, "active": 0.0,
                    "poses": 0, "cats": set(g["cats"]) or {"all"}, "over": False}
        self._gym_session_view()
        self._gym_show(0)
        self._gym_tick()

    def _gym_session_view(self):
        px = self.px
        self._gym_clear()
        sw, sh = self.gym_win.winfo_screenwidth(), self.gym_win.winfo_screenheight()
        self._gym_place(min(px(900), int(sw * 0.62)), min(px(820), int(sh * 0.86)))
        body = self._gw["body"]
        gw = self._gw
        info = tk.Frame(body, bg=BG)
        info.pack(fill="x", padx=px(16), pady=(px(10), px(6)))
        gw["count"] = tk.Label(info, text="", bg=BG, fg=MUTED, font=(MONO, 9), anchor="w")
        gw["count"].pack(side="left")
        gw["clock"] = tk.Label(info, text="", bg=BG, fg=TEXT, font=(MONO, 20))
        gw["clock"].pack(side="right")
        gw["cv"] = tk.Canvas(body, bg="#000000", highlightthickness=0, bd=0)
        gw["cv"].pack(fill="both", expand=True, padx=px(16))
        gw["cv"].bind("<Configure>", lambda e: self._gym_render())
        gw["cv"].bind("<Button-3>", self._gym_menu)
        gw["cv"].bind("<Double-Button-1>", lambda e: self._gym_key("space"))
        gw["bar"] = tk.Canvas(body, bg=BORDER, height=px(3), highlightthickness=0, bd=0)
        gw["bar"].pack(fill="x", padx=px(16))
        row = tk.Frame(body, bg=BG)
        row.pack(fill="x", padx=px(16), pady=(px(10), px(14)))
        self._fbtn(row, "←", lambda: self._gym_key("back")).pack(side="left")
        gw["pause"] = self._fbtn(row, "pause", lambda: self._gym_key("space"), primary=True)
        gw["pause"].pack(side="left", padx=(px(8), 0))
        self._fbtn(row, "next →", lambda: self._gym_key("next")).pack(side="left", padx=(px(8), 0))
        self._fbtn(row, "end", self._gym_end).pack(side="right")
        gw["gray"] = self._fbtn(row, "gray", lambda: self._gym_key("gray"))
        gw["gray"].pack(side="right", padx=(0, px(8)))
        gw["mirror"] = self._fbtn(row, "mirror", lambda: self._gym_key("mirror"))
        gw["mirror"].pack(side="right", padx=(0, px(8)))
        self.gym_win.focus_force()

    def _gym_show(self, i):
        s = self._gs
        s["i"] = i
        s["left"] = s["plan"][i][1]
        s["shown"] = 0.0
        s["last"] = time.monotonic()
        try:
            from PIL import Image, ImageOps
            with Image.open(s["plan"][i][0]) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((2000, 2000))
                s["img"] = im.copy()
        except Exception:
            s["img"] = None
        self._gym_render()
        self._gym_labels()

    def _gym_render(self):
        s = getattr(self, "_gs", None)
        cv = self._gw.get("cv")
        if not s or not cv or not cv.winfo_exists():
            return
        cv.delete("all")
        W, H = cv.winfo_width(), cv.winfo_height()
        if W < 20 or H < 20:
            return
        im = s.get("img")
        if im is None:
            cv.create_text(W // 2, H // 2, text="couldn't open this picture", fill=MUTED, font=(MONO, 10))
            return
        from PIL import ImageOps, ImageTk
        pic = im.copy()
        pic.thumbnail((W, H))
        if s["mirror"]:
            pic = ImageOps.mirror(pic)
        if s["gray"]:
            pic = ImageOps.grayscale(pic).convert("RGB")
        photo = ImageTk.PhotoImage(pic)
        self.imgs["gym_pic"] = photo
        cv.create_image(W // 2, H // 2, image=photo)
        if s["paused"]:
            cv.create_rectangle(W // 2 - 70, H // 2 - 22, W // 2 + 70, H // 2 + 22, fill="#0a0a0a", outline=ACCENT)
            cv.create_text(W // 2, H // 2, text="paused", fill=ACCENT, font=(MONO, 12, "bold"))

    def _gym_labels(self):
        s = self._gs
        gw = self._gw
        path, secs = s["plan"][s["i"]]
        cat = dict(self.gym.pictures()).get(path) or ""
        gw["count"].configure(text=f"{s['i'] + 1} / {len(s['plan'])}  ·  {gym.LABELS.get(cat, cat)}"
                                   + (f"  ·  {gym.fmt(secs)}" if secs else ""))
        for key in ("mirror", "gray"):
            gw[key].configure(fg=ACCENT if s[key] else TEXT)
        gw["pause"].configure(text="resume" if s["paused"] else "pause")

    def _gym_tick(self):
        s = getattr(self, "_gs", None)
        if not s or s.get("over") or not self.gym_win.winfo_exists():
            return
        now = time.monotonic()
        dt = now - s["last"]
        s["last"] = now
        secs = s["plan"][s["i"]][1]
        if not s["paused"]:
            s["active"] += dt
            s["shown"] += dt
            if secs:
                s["left"] -= dt
        gw = self._gw
        try:
            if secs:
                left = max(0.0, s["left"])
                gw["clock"].configure(text=gym.fmt(left + 0.99), fg=ACCENT if left <= 5 else TEXT)
                bar = gw["bar"]
                bar.delete("all")
                bar.create_rectangle(0, 0, bar.winfo_width() * (1 - left / secs), self.px(3), fill=ACCENT, width=0)
            else:
                gw["clock"].configure(text=gym.fmt(s["shown"]), fg=MUTED)
                gw["bar"].delete("all")
        except tk.TclError:
            return
        if secs and s["left"] <= 0 and not s["paused"]:
            self._gym_advance()
        self.root.after(200, self._gym_tick)

    def _gym_count_pose(self):
        s = self._gs
        secs = s["plan"][s["i"]][1]
        if s["shown"] >= min(20, secs * 0.6 if secs else 20):
            s["poses"] += 1

    def _gym_advance(self):
        s = self._gs
        self._gym_count_pose()
        if s["i"] + 1 >= len(s["plan"]):
            self._gym_end()
        else:
            self._gym_show(s["i"] + 1)

    def _gym_key(self, what):
        s = getattr(self, "_gs", None)
        if not s or s.get("over"):
            if what == "enter" and getattr(self, "_gsel", None) and not s:
                self._gym_start()
            return
        if what == "space":
            s["paused"] = not s["paused"]
            s["last"] = time.monotonic()
            self._gym_render()
        elif what == "next":
            self._gym_advance()
            return
        elif what == "back" and s["i"] > 0:
            self._gym_show(s["i"] - 1)
            return
        elif what in ("mirror", "gray"):
            s[what] = not s[what]
            self._gym_render()
        self._gym_labels()

    def _gym_menu(self, e):
        s = getattr(self, "_gs", None)
        if not s:
            return
        path = s["plan"][s["i"]][0]
        m = tk.Menu(self.gym_win, tearoff=0)
        sub = tk.Menu(m, tearoff=0)
        cur = dict(self.gym.pictures()).get(path)
        for key, label, _ in gym.CATEGORIES:
            sub.add_command(label=("● " if key == cur else "   ") + label,
                            command=lambda k=key: (self.gym.set_category(path, k), self._gym_labels()))
        m.add_cascade(label="This picture is really...", menu=sub)
        m.add_command(label="Show in folder", command=lambda: open_folder(os.path.dirname(path)))
        m.tk_popup(e.x_root, e.y_root)

    def _gym_end(self):
        s = getattr(self, "_gs", None)
        if not s or s.get("over"):
            return
        s["over"] = True
        if s["i"] + 1 < len(s["plan"]) or s["plan"][s["i"]][1] == 0:
            self._gym_count_pose()          # the one on screen counts if you spent time on it
        self.gym.record(s["poses"], s["active"], s["cats"])
        try:
            if not self.cfg.get("daily_note", True):   # 2026-11-08: respect the daily-note checkbox
                raise OSError("daily note is off")
            self.daily.log(f"drawing gym: {s['poses']} pictures, {max(1, round(s['active'] / 60))} min")
        except Exception:
            pass
        self._gym_done_view()

    def _gym_done_view(self):
        px = self.px
        s = self._gs
        self._gym_clear()
        self._gym_place(px(470), px(max(640, self.PANEL_H)))
        self._gym_sub()
        body = self._gw["body"]
        st = self.gym.stats()
        box = tk.Frame(body, bg=BG)
        box.pack(fill="both", expand=True, padx=px(22), pady=(px(40), 0))
        mins = max(1, round(s["active"] / 60)) if s["active"] >= 30 else 0
        tk.Label(box, text=f"{s['poses']} picture{'s' if s['poses'] != 1 else ''}", bg=BG, fg=TEXT,
                 font=(MONO, 34)).pack()
        tk.Label(box, text=(f"{mins} min of drawing" if mins else "a quick one") + ". nice work.", bg=BG,
                 fg=MUTED, font=(MONO, 9)).pack(pady=(px(4), px(24)))
        card = tk.Frame(box, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x")
        for label, val in (("streak", f"{st['streak']} day{'s' if st['streak'] != 1 else ''}"),
                           ("this week", f"{st['week_poses']} picture{'s' if st['week_poses'] != 1 else ''} · {st['week_minutes']} min"),
                           ("all time", f"{st['total_poses']} picture{'s' if st['total_poses'] != 1 else ''}")):
            r = tk.Frame(card, bg=SURFACE)
            r.pack(fill="x", padx=px(14), pady=(px(8), 0))
            tk.Label(r, text=label, bg=SURFACE, fg=MUTED, font=(MONO, 8)).pack(side="left")
            tk.Label(r, text=val, bg=SURFACE, fg=ACCENT if label == "streak" else TEXT, font=(MONO, 10)).pack(side="right")
        tk.Frame(card, bg=SURFACE, height=px(10)).pack()
        row = tk.Frame(body, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(18), pady=(px(10), px(18)))
        self._fbtn(row, "again", self._gym_start, primary=True).pack(side="left", fill="x", expand=True)
        self._fbtn(row, "change setup", self._gym_setup).pack(side="right", padx=(px(8), 0))

    def _gym_escape(self):
        s = getattr(self, "_gs", None)
        if s and not s.get("over"):
            self._gym_end()
        else:
            self._gym_close()

    def _gym_close(self):
        s = getattr(self, "_gs", None)
        if s and not s.get("over"):
            self._gym_end()
        save_config(self.cfg)
        self._gs = None
        try:
            self.gym_win.withdraw()
        except tk.TclError:
            pass

    def _gym_event(self, kind, val):
        if kind == "gym_status":
            if not self.busy:
                self.status.configure(text=val)
        elif kind in ("gym_sorted", "gym_done"):
            w = getattr(self, "gym_win", None)
            if w is not None and w.winfo_exists() and not getattr(self, "_gs", None):
                self._gym_draw_cats()
                self._gym_summary()
            if kind == "gym_done" and not self.busy:
                self._update_status()
        elif kind == "gym_error":
            if val != getattr(self, "_gym_last_err", None):
                self._gym_last_err = val
                self._write(val + "\n", "sys")

    def _gym_vision(self):
        try:
            return pick_vision_model(self.cfg.get("model") or "")
        except Exception:
            return None

    # ----- making images (Stable Diffusion XL, on this PC) ------------------------

    def _img_event(self, ev):
        if getattr(self, "_img_target", None) == "sketch":
            return self._sketch_event(ev)
        w = self.img_win
        kind = ev.get("type")
        if kind == "bye":
            return
        if not (w and w.winfo_exists()):
            if kind == "image":
                self._write(f"Made an image: {ev['path']}\n", "sys")
            elif kind == "error":
                self._write(f"Image maker: {ev['text']}\n", "sys")
            return
        if kind == "status":
            w._status.configure(text=ev["text"], fg=MUTED)
        elif kind == "progress":
            frac = ((ev["i"] + ev["step"] / float(ev["steps"])) / ev["n"])
            w._status.configure(text=f"painting {ev['i'] + 1} of {ev['n']} · step {ev['step']}/{ev['steps']}", fg=MUTED)
            w._bar(frac)
        elif kind == "image":
            w._add(ev["path"], ev["seed"])
        elif kind == "done":
            w._busy = False
            w._bar(1.0)
            w._status.configure(text="done. Click a picture for options (open, obsidian, more like this...)",
                                fg=ACCENT)
            w._gen_btn.configure(text="generate again")
        elif kind == "error":
            w._busy = False
            w._status.configure(text="Couldn't make it: " + ev["text"], fg=REC)
            w._gen_btn.configure(text="try again")

    def start_image(self, req, text):
        if not self.panel_visible():
            self.show_panel()
        why = imagine.installed()
        self._you(text)
        if why:
            self._write(imagine.MESSAGES[why] + "\n", "sys")
            return
        w = self.show_imagine(req.get("n", 1))
        if req["raw"]:
            w._prompt.insert("1.0", req["what"])
            w._generate()
            return
        w._status.configure(text="writing a detailed prompt for the image model...")
        about = "\n".join(l for l in read_small_text(ABOUT_PATH).splitlines() if not l.lstrip().startswith("#"))

        def work():
            data = {}
            try:
                out = quick_chat(self.cfg["model"], imagine.EXPAND_PROMPT.format(
                    about="Context about the user and their projects (use only if relevant):\n" + about[:1500],
                    request=req["what"]), max_tokens=400, json_mode=True, temperature=0.6)
                data = json.loads(out)
            except Exception:
                data = {}
            self.bg_q.put(("call", lambda: filled(data)))

        def filled(data):
            if not w.winfo_exists():
                return
            w._prompt.insert("1.0", (data.get("prompt") or req["what"]).strip())
            w._neg.insert(0, (data.get("negative") or "blurry, low quality, deformed hands, extra fingers, "
                                                      "watermark, text, signature").strip())
            if data.get("shape") in imagine.SHAPES:
                w._shape.set(data["shape"])
                w._draw_opts()
            w._generate()
        threading.Thread(target=work, daemon=True).start()

    def show_imagine(self, n=1):
        px = self.px
        if self.img_win and self.img_win.winfo_exists():
            self.img_win.destroy()
        w = self.img_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = px(max(500, self.PANEL_W + 40)), px(max(640, self.PANEL_H))
        w.geometry(f"{W}x{H}+{max(0, self.panel.winfo_x() - px(40))}+{self.panel.winfo_y()}")
        w._busy, w._imgs, w._shape, w._n, w._q = False, [], tk.StringVar(value="square"), tk.IntVar(value=n), tk.StringVar(value="good")

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(6)))
        tk.Label(top, text="IMAGINE", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        tk.Label(top, text="  made on your graphics card, offline", bg=BG, fg=MUTED, font=(MONO, 8)).pack(side="left")
        self._icon_btn(top, "close", w.destroy, "Close (pictures are kept in the Images folder)").pack(side="right")
        to_sketch = tk.Label(top, text="from a sketch", bg=BG, fg=DIM, font=(MONO, 8), padx=px(8), pady=px(3),
                             cursor="hand2", highlightthickness=1, highlightbackground=BORDER)
        to_sketch.pack(side="right", padx=(0, px(10)))
        to_sketch.bind("<ButtonRelease-1>", lambda e: (w.destroy(), self.show_sketch()))
        top.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
        top.bind("<B1-Motion>", lambda e: w.geometry(
            f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))

        box = tk.Frame(w, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="x", padx=px(14))
        w._prompt = tk.Text(box, height=4, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, wrap="word", bd=0,
                            padx=px(10), pady=px(8), highlightthickness=0, font=(FONT, 10), undo=True)
        w._prompt.pack(fill="x")
        nrow = tk.Frame(w, bg=BG)
        nrow.pack(fill="x", padx=px(14), pady=(px(6), 0))
        tk.Label(nrow, text="avoid", bg=BG, fg=MUTED, font=(MONO, 8), width=6, anchor="w").pack(side="left")
        w._neg = tk.Entry(nrow, bg=BG, fg=BODY, insertbackground=ACCENT, bd=0, font=(MONO, 8),
                          highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        w._neg.pack(side="left", fill="x", expand=True, ipady=px(2))

        opts = tk.Frame(w, bg=BG)
        opts.pack(fill="x", padx=px(14), pady=px(8))

        def chip(parent, text, var, value):
            b = tk.Label(parent, text=text, bg=BG, font=(MONO, 8), padx=px(7), pady=px(2), cursor="hand2",
                         highlightthickness=1)
            b.bind("<ButtonRelease-1>", lambda e: (var.set(value), w._draw_opts()))
            b._var, b._val = var, value
            return b
        w._chips = []
        for group, var, items in (("", w._shape, [("square", "square"), ("wide", "wide"), ("tall", "tall")]),
                                  ("  ", w._n, [("1", 1), ("2", 2), ("4", 4)]),
                                  ("  ", w._q, [("fast", "fast"), ("good", "good")])):
            if group:
                tk.Label(opts, text=group, bg=BG).pack(side="left")
            for label, val in items:
                c = chip(opts, label, var, val)
                c.pack(side="left", padx=(0, px(4)))
                w._chips.append(c)

        def draw_opts():
            for c in w._chips:
                on = c._var.get() == c._val
                c.configure(fg=ACCENT if on else DIM, highlightbackground=ACCENT if on else BORDER,
                            highlightcolor=ACCENT if on else BORDER)
        w._draw_opts = draw_opts
        draw_opts()
        w._gen_btn = tk.Label(opts, text="generate", bg=ACCENT, fg=TILE, font=(MONO, 9, "bold"),
                              padx=px(12), pady=px(4), cursor="hand2")
        w._gen_btn.pack(side="right")
        w._gen_btn.bind("<ButtonRelease-1>", lambda e: w._generate())

        w._status = tk.Label(w, text="", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w")
        w._status.pack(fill="x", padx=px(14))
        bar = tk.Canvas(w, height=px(3), bg=BORDER, highlightthickness=0, bd=0)
        bar.pack(fill="x", padx=px(14), pady=(px(4), px(8)))

        def set_bar(frac):
            bar.delete("all")
            bar.create_rectangle(0, 0, bar.winfo_width() * max(0.0, min(1.0, frac)), px(3), fill=ACCENT, width=0)
        w._bar = set_bar

        gallery = tk.Frame(w, bg=BG)
        gallery.pack(fill="both", expand=True, padx=px(14), pady=(0, px(12)))
        menu = tk.Menu(w, tearoff=0)

        def add(path, seed):
            idx = len(w._imgs)
            try:
                im = Image.open(path)
                side = (W - px(40)) // 2
                im.thumbnail((side, side))
                photo = ImageTk.PhotoImage(im)
            except Exception:
                return
            lbl = tk.Label(gallery, image=photo, bg=BG, cursor="hand2", bd=0)
            lbl.image = photo
            lbl.grid(row=idx // 2, column=idx % 2, padx=px(3), pady=px(3))
            w._imgs.append((path, seed))

            def pop(e, path=path, seed=seed):
                menu.delete(0, "end")
                menu.add_command(label="Open full size", command=lambda: open_folder(path))
                menu.add_command(label="Save to Obsidian", command=lambda: self._image_to_obsidian(path, w))
                menu.add_command(label="More like this (same look, new variations)",
                                 command=lambda: w._generate(seed=seed + 1000))
                menu.add_command(label="Ask Archie about it (attach to chat)",
                                 command=lambda: (self.add_attachments([path]), self.panel.lift()))
                menu.add_command(label="Show in folder", command=lambda: open_folder(os.path.dirname(path)))
                menu.tk_popup(e.x_root, e.y_root)
            lbl.bind("<Button-1>", pop)
            lbl.bind("<Button-3>", pop)
        w._add = add

        def generate(seed=None):
            if w._busy:
                return
            prompt = w._prompt.get("1.0", "end").strip()
            if not prompt:
                w._status.configure(text="Describe what you want first.", fg=REC)
                return
            w._busy = True
            for c in gallery.winfo_children():
                c.destroy()
            w._imgs = []
            set_bar(0)
            w._gen_btn.configure(text="working...")
            w._status.configure(text="making room on the graphics card...", fg=MUTED)
            out = os.path.join(IMAGES_DIR, datetime.date.today().isoformat())
            steps = 20 if w._q.get() == "fast" else 30
            neg = w._neg.get().strip()
            shape, n = w._shape.get(), int(w._n.get())

            def work():
                imagine.free_ollama_gpu(OLLAMA_URL)
                self.bg_q.put(("img", {"type": "status", "text": "starting the image helper..."}))
                try:
                    self.imager.make(prompt, neg, shape, n, steps, out, seed)
                except Exception as e:
                    self.bg_q.put(("img", {"type": "error", "text": str(e)}))
            threading.Thread(target=work, daemon=True).start()
            watch()

        def watch():
            """If the helper goes quiet for too long, say so (and where to look)."""
            if not w.winfo_exists() or not w._busy:
                return
            quiet = time.time() - getattr(self.imager, "last_heard", time.time())
            if quiet > 150:
                w._status.configure(text="the image helper has been quiet for a while... (details in "
                                         "Images\\image_helper.log)", fg="#f5a524")
            w.after(5000, watch)
        w._generate = generate
        w.bind("<Escape>", lambda e: w.destroy())
        return w

    def _image_to_obsidian(self, path, w=None):
        vault = self.vault()
        if not vault:
            self._write("Set your Obsidian vault first: right-click the owl > Choose Obsidian vault...\n", "sys")
            return
        import shutil
        try:
            from PIL import Image as _I
            info = _I.open(path).info
        except Exception:
            info = {}
        folder = os.path.join(vault, obs.ARCHIE_FOLDER, "Images")
        os.makedirs(folder, exist_ok=True)
        name = os.path.basename(path)
        shutil.copy2(path, os.path.join(folder, name))
        prompt = info.get("prompt", "")
        title = obs.safe_filename(" ".join(prompt.split()[:8]) or "Archie image")
        note = (f"---\ntags: [archie, image]\ncreated: {datetime.datetime.now():%Y-%m-%d %H:%M}\n"
                f"seed: {info.get('seed', '')}\n---\n# {title}\n\n![[{name}]]\n\n**Prompt:** {prompt}\n\n"
                f"**Avoid:** {info.get('negative', '')}\n\nMade offline by [[{obs.HUB_NOTE}]] "
                "(Stable Diffusion XL).\n")
        rel = obs.save_note(vault, title, note, subfolder="Images")
        msg = f"Saved to Obsidian: {rel}"
        if w is not None and w.winfo_exists():
            w._status.configure(text=msg, fg=ACCENT)
        self._write(msg + "\n", "sys")

    # ----- calendar ---------------------------------------------------------------

    def _draw_date_chip(self):
        c, px = self.date_chip, self.px
        c.delete("all")
        today = datetime.date.today()
        text = today.strftime("%a %b %d").replace(" 0", " ").lower()
        self._chip_w["date"] = tkfont.Font(family=MONO, size=8).measure(text)
        if getattr(self, "_date_compact", False):
            text = today.strftime("%b %d").replace(" 0", " ").lower()
        self._chip_w["date_short"] = tkfont.Font(family=MONO, size=8).measure(text)
        has = bool(self.calendar.on(today))
        tw = tkfont.Font(family=MONO, size=8).measure(text)
        h = px(22)
        w = tw + px(20) + (px(10) if has else 0)
        c.configure(width=w, height=h)
        dots = [(w - px(11), h / 2, px(3), cal.KINDS[self.calendar.on(today)[0]["kind"]][1])] if has else []
        try:
            self.imgs["datechip"] = th.rounded(w, h, h // 2, BG, BORDER, dots=dots)
            c.create_image(0, 0, anchor="nw", image=self.imgs["datechip"])
        except Exception:
            pass
        c.create_text(px(10), h / 2, anchor="w", text=text, fill=MUTED, font=(MONO, 8))
        self._date_shown = today

    def _cal_lines_md(self):
        """For today's daily note."""
        today = datetime.date.today()
        return [f"- **{cal.KINDS.get(e['kind'], cal.KINDS['event'])[0]}:** {e['title']} · {cal.when(e, today)}"
                for e in self.calendar.upcoming(today)[:10]]

    def _cal_context(self):
        """For Archie's answers: what's on the calendar in the next month."""
        today = datetime.date.today()
        evs = self.calendar.between(today, today + datetime.timedelta(days=30))
        seen, lines = set(), []
        for e in evs:
            key = (e["id"], e["kind"]) if e.get("repeat") == "weekly" else None
            if key and key in seen:
                continue
            if key:
                seen.add(key)
                lines.append(f"- {cal.KINDS[e['kind']][0]}: {e['title']}, every "
                             f"{datetime.date.fromisoformat(e['date']).strftime('%A')}"
                             + (f" at {cal.fmt_time(e['time'])}" if e.get("time") else ""))
            else:
                lines.append("- " + cal.describe(e, today))
        return lines[:15]

    def change_event_from_text(self, text):
        """Change or remove an event by asking (the model picks which; the change is checked, then shown with undo)."""
        self._you(text)
        res = {}

        def work():
            try:
                res["p"] = calchat.plan(text, self.calendar, lambda p: quick_chat(
                    self.cfg["model"], p, max_tokens=200, timeout=120, json_mode=True, temperature=0.1))
            except Exception as e:
                res["p"] = {"error": f"I couldn't change it: {e}"}

        def done():
            if "p" not in res:
                return self.root.after(300, done)
            p = res["p"]
            self._archie()
            if p.get("error"):
                self._write(p["error"] + "\n", "abody")
                return self._end_span()
            msg, undo = calchat.apply(p, self.calendar)
            self._write(msg + " ", "abody")
            if p["action"] == "change":
                d = datetime.date.fromisoformat(p["changes"].get("date") or p["event"]["date"])
                self._link("open calendar", lambda: self.show_calendar(d), "abody")
                self._write("  ", "abody")

            def back():
                undo()
                self._draw_date_chip()
                self._sync_daily(quiet=True)
                self.bg_q.put(("status", "undone: the calendar is back how it was"))
            self._link("undo", back, "abody")
            self._end_span()
            self._write("\n", "abody")
            self._draw_date_chip()
            self.root.after(50, lambda: self._sync_daily(quiet=True))
        threading.Thread(target=work, daemon=True, name="cal-change").start()
        self.root.after(300, done)

    def add_event_from_text(self, ev, text):
        e = self.calendar.add(ev["title"], ev["date"], ev["kind"], ev.get("time"), repeat=ev.get("repeat"))
        self._you(text)
        self._archie()
        rep = " (every week)" if e.get("repeat") else ""
        self._write(f"Added to your calendar: {cal.describe(e)}{rep}. ", "abody")
        self._link("open calendar", lambda: self.show_calendar(datetime.date.fromisoformat(e["date"])), "abody")
        self._end_span()
        self._write("\n", "abody")
        self._draw_date_chip()
        self.root.after(50, lambda: self._sync_daily(quiet=True))

    # ----- sketch to image ------------------------------------------------------

    SKETCH_EXT = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".heic", ".heif")

    def show_sketch(self, path=None):
        """Imagine > from a sketch: bring in a drawing, then paint it."""
        why = imagine.installed()
        if why:
            self._write(imagine.MESSAGES[why] + "\n", "sys")
            return
        if not imagine.sketch_installed():
            self._write("Turning sketches into pictures needs one small extra download (the sketch reader). "
                        "Quit Archie, run Tools\\Get Sketch Model.bat (online, once), then start Archie again.\n", "sys")
            return
        if not self.panel_visible():
            self.show_panel()
        w = getattr(self, "sketch_win", None)
        if w is None or not w.winfo_exists():
            w = self._build_sketch_win()
        if path:
            self._sketch_load(path)
        elif not getattr(self, "_sk", {}).get("path"):
            self._sketch_view("pick")
        w.deiconify()
        w.lift()

    def _build_sketch_win(self):
        px = self.px
        w = self.sketch_win = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = px(960), px(640)
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        x = max(0, min(self.panel.winfo_x() - W + px(420), sw - W - px(10)))
        y = max(0, min(self.panel.winfo_y(), sh - H - px(50)))
        w.geometry(f"{W}x{H}+{x}+{y}")
        self._sk = {"path": None, "follow": "balanced", "style": "concept art", "n": 4, "shape": "square",
                    "busy": False, "results": [], "sel": None, "lines": None, "show_lines": False, "summary": ""}
        sw_ = self._skw = {}

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(16), pady=(px(12), px(8)))
        tk.Label(top, text="IMAGINE", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        sw_["sub"] = tk.Label(top, text="  from a sketch", bg=BG, fg=MUTED, font=(MONO, 8))
        sw_["sub"].pack(side="left")
        words = tk.Label(top, text="from words", bg=BG, fg=DIM, font=(MONO, 8), padx=px(8), pady=px(3),
                         cursor="hand2", highlightthickness=1, highlightbackground=BORDER)
        words.pack(side="left", padx=(px(18), 0))
        words.bind("<ButtonRelease-1>", lambda e: (w.withdraw(), self.show_imagine()))
        self._icon_btn(top, "close", w.withdraw, "Close (pictures are kept in the Images folder)").pack(side="right")
        for wd in (top, sw_["sub"]):
            wd.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
            wd.bind("<B1-Motion>", lambda e: w.geometry(
                f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))
        tk.Frame(w, bg=th.LINE, height=1).pack(fill="x")
        sw_["body"] = tk.Frame(w, bg=BG)
        sw_["body"].pack(fill="both", expand=True)
        w.bind("<Escape>", lambda e: w.withdraw())
        w.bind("<Control-v>", lambda e: self._sketch_paste())
        if TkinterDnD:
            try:
                w.drop_target_register(DND_FILES)
                w.dnd_bind("<<Drop>>", self._sketch_drop)
            except Exception:
                pass
        return w

    def _sketch_clear(self):
        for c in self._skw["body"].winfo_children():
            c.destroy()

    def _sketch_view(self, name):
        self._sk["view"] = name
        self._sketch_clear()
        {"pick": self._sketch_pick_view, "setup": self._sketch_setup_view,
         "paint": self._sketch_paint_view}[name]()

    def _sketch_btn(self, parent, text, cmd, primary=False, small=False):
        b = self._fbtn(parent, text, cmd, primary=primary)
        if small:
            b.configure(pady=self.px(5), padx=self.px(10), font=(MONO, 8, "bold") if primary else (MONO, 8))
        return b

    # --- 1. bring in a sketch

    def _recent_sketches(self, limit=3):
        vault = self.vault()
        if not vault or not os.path.isdir(vault):
            return []
        found = []
        for root, dirs, files in os.walk(vault):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            low = root.lower()
            if "excalidraw" not in low and "handwritten" not in low and "sketch" not in low:
                continue
            for f in files:
                if f.lower().endswith(self.SKETCH_EXT):
                    p = os.path.join(root, f)
                    try:
                        found.append((os.path.getmtime(p), p))
                    except OSError:
                        pass
        return [p for _t, p in sorted(found, reverse=True)[:limit]]

    def _sketch_pick_view(self):
        px, body = self.px, self._skw["body"]
        self._skw["sub"].configure(text="  from a sketch")
        row = tk.Frame(body, bg=BG)
        row.pack(fill="both", expand=True, padx=px(20), pady=px(18))
        side = tk.Frame(row, bg=BG, width=px(280))
        side.pack(side="right", fill="y", padx=(px(18), 0))
        side.pack_propagate(False)
        drop = tk.Frame(row, bg="#0d0d0d", highlightthickness=1, highlightbackground="#3a3a3a")
        drop.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(drop, bg="#0d0d0d")
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(inner, text="✎", bg="#0d0d0d", fg=ACCENT, font=(FONT, 34)).pack()
        tk.Label(inner, text="Drop a sketch here", bg="#0d0d0d", fg=TEXT, font=(FONT_SEMI, 16, "bold")).pack(pady=(px(4), px(6)))
        tk.Label(inner, text="A photo of paper, a drawing from your Surface, or an Excalidraw sketch.\n"
                             "Rough is fine: Archie keeps your layout and poses and paints the rest.",
                 bg="#0d0d0d", fg=DIM, font=(FONT, 10), justify="center").pack()
        btns = tk.Frame(inner, bg="#0d0d0d")
        btns.pack(pady=(px(16), 0))
        self._sketch_btn(btns, "choose a file", self._sketch_choose, primary=True).pack(side="left")
        self._sketch_btn(btns, "paste (Ctrl+V)", self._sketch_paste).pack(side="left", padx=(px(8), 0))
        self._sketch_btn(btns, "snip the screen", self._sketch_snip).pack(side="left", padx=(px(8), 0))
        self._skw["pick_msg"] = tk.Label(inner, text="", bg="#0d0d0d", fg="#f5a524", font=(MONO, 8))
        self._skw["pick_msg"].pack(pady=(px(10), 0))

        tk.Label(side, text="> recent sketches in your vault", bg=BG, fg=MUTED, font=(MONO, 8),
                 anchor="w").pack(fill="x")
        recent = self._recent_sketches()
        grid = tk.Frame(side, bg=BG)
        grid.pack(fill="x", pady=(px(8), 0))
        self._skw["thumbs"] = []
        for i, p in enumerate(recent):
            try:
                im = Image.open(p)
                im = ImageOps.exif_transpose(im) if ImageOps else im
                im.thumbnail((px(128), px(96)))
                bgim = Image.new("RGB", (px(128), px(96)), (239, 238, 232))
                if im.mode in ("RGBA", "LA", "P"):
                    im = im.convert("RGBA")
                    bgim.paste(im, ((px(128) - im.width) // 2, (px(96) - im.height) // 2), im)
                else:
                    bgim.paste(im.convert("RGB"), ((px(128) - im.width) // 2, (px(96) - im.height) // 2))
                photo = ImageTk.PhotoImage(bgim)
            except Exception:
                continue
            b = tk.Label(grid, image=photo, bg=BORDER, bd=0, cursor="hand2", highlightthickness=1,
                         highlightbackground=BORDER)
            b.image = photo
            b.grid(row=i // 2, column=i % 2, padx=(0, px(8)), pady=(0, px(8)))
            b.bind("<ButtonRelease-1>", lambda e, p=p: self._sketch_load(p))
            self._skw["thumbs"].append(b)
        if not recent:
            tk.Label(side, text="(none yet: sketches in Excalidraw/ and Handwritten/ in your vault show up here)",
                     bg=BG, fg=MUTED, font=(FONT, 9), wraplength=px(270), justify="left", anchor="w").pack(fill="x")
        tip = tk.Frame(side, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        tip.pack(side="bottom", fill="x")
        tk.Label(tip, text="tips for fight scenes", bg=SURFACE, fg=TEXT, font=(MONO, 8), anchor="w").pack(
            fill="x", padx=px(10), pady=(px(8), px(2)))
        tk.Label(tip, text="Draw bodies as simple shapes (circle head, box chest), keep the figures from "
                           "overlapping too much, and make weapons clear lines.", bg=SURFACE, fg=DIM,
                 font=(FONT, 9), wraplength=px(255), justify="left", anchor="w").pack(fill="x", padx=px(10),
                                                                                        pady=(0, px(10)))

    def _sketch_choose(self):
        self.sketch_win.attributes("-topmost", False)
        try:
            p = filedialog.askopenfilename(parent=self.sketch_win, title="Choose a sketch",
                                           filetypes=[("Pictures", " ".join("*" + e for e in self.SKETCH_EXT)),
                                                      ("All files", "*.*")])
        finally:
            self.sketch_win.attributes("-topmost", True)
        if p:
            self._sketch_load(p)

    def _sketch_drop(self, e):
        paths = self.root.tk.splitlist(e.data)
        for p in paths:
            if p.lower().endswith(self.SKETCH_EXT):
                self._sketch_load(p)
                break
        return e.action

    def _sketch_paste(self):
        try:
            from PIL import ImageGrab
            got = ImageGrab.grabclipboard()
        except Exception:
            got = None
        if isinstance(got, list):
            got = next((p for p in got if str(p).lower().endswith(self.SKETCH_EXT)), None)
            if got:
                self._sketch_load(got)
                return
        if got is None or isinstance(got, str):
            if self._skw.get("pick_msg") and self._skw["pick_msg"].winfo_exists():
                self._skw["pick_msg"].configure(text="No picture on the clipboard. Copy one first (Ctrl+C).")
            return
        os.makedirs(SNIPS_DIR, exist_ok=True)
        p = os.path.join(SNIPS_DIR, f"Pasted sketch {datetime.datetime.now():%Y-%m-%d_%H%M%S}.png")
        got.save(p)
        self._sketch_load(p)

    def _sketch_snip(self):
        self.sketch_win.withdraw()
        self._snip_for_sketch = True
        self.start_snip()

    # --- 2. Archie reads it, you choose

    def _sketch_load(self, path):
        sk = self._sk
        sk.update(path=path, summary="", prompt="", results=[], sel=None, lines=None)
        try:
            sk["shape"] = imagine.sketch_shape(path)
        except Exception as e:
            if self._skw.get("pick_msg") and self._skw["pick_msg"].winfo_exists():
                self._skw["pick_msg"].configure(text=f"Couldn't open that picture: {e}")
            return
        self._sketch_view("setup")
        self.sketch_win.deiconify()
        self.sketch_win.lift()
        self._sketch_read()

    def _sketch_read(self):
        """The vision model looks at the sketch and starts the prompt."""
        path = self._sk["path"]
        token = object()
        self._sk["read_job"] = token

        def work():
            try:
                model = pick_vision_model(self.cfg["model"])
                b64 = read_image_b64(path)
                out = imagine.describe_sketch(OLLAMA_URL, model, b64)
            except Exception as e:
                out = {"summary": "", "prompt": "", "error": str(e)}
            self.bg_q.put(("call", lambda: self._sketch_read_done(token, out)))
        threading.Thread(target=work, daemon=True).start()

    def _sketch_read_done(self, token, out):
        sk, sw_ = self._sk, self._skw
        if sk.get("read_job") is not token or sk.get("view") != "setup":
            return
        sk["summary"] = out.get("summary", "")
        if not sw_["summary"].winfo_exists():
            return
        if out.get("error"):
            sw_["summary"].configure(text="Couldn't read it automatically (" + out["error"][:120] +
                                          "). Just describe it yourself.", fg="#f5a524")
        else:
            sw_["summary"].configure(text=sk["summary"] or "(nothing clear. Describe it yourself.)", fg=BODY)
        box = sw_["prompt"]
        if not box.get("1.0", "end").strip() and out.get("prompt"):
            box.insert("1.0", out["prompt"])

    def _sketch_preview(self, parent, maxw, maxh, lines_on=False):
        """The sketch (or its lines) as a picture."""
        try:
            im = Image.open(self._sk["path"])
            im = ImageOps.exif_transpose(im) if ImageOps else im
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bgim = Image.new("RGBA", im.size, (239, 238, 232, 255))
                bgim.alpha_composite(im)
                im = bgim
            im = im.convert("RGB")
            im.thumbnail((maxw, maxh))
            photo = ImageTk.PhotoImage(im)
        except Exception:
            return tk.Label(parent, text="(can't show the sketch)", bg=SURFACE, fg=MUTED)
        lab = tk.Label(parent, image=photo, bg=BG, bd=0)
        lab.image = photo
        return lab

    def _chip_row(self, parent, items, current, on_pick, per_row=None, max_width=None):
        px = self.px
        chips = {}
        row = None
        used = 0
        font = tkfont.Font(family=MONO, size=8)
        for i, item in enumerate(items):
            wid = font.measure(str(item)) + px(16) + px(2) + px(5)
            new_row = row is None or (per_row and i % per_row == 0) or (max_width and used + wid > max_width)
            if new_row:
                row = tk.Frame(parent, bg=BG)
                row.pack(fill="x", pady=(0, px(5)))
                used = 0
            used += wid
            b = tk.Label(row, text=str(item), bg=BG, font=(MONO, 8), padx=px(8), pady=px(4), cursor="hand2",
                         highlightthickness=1)
            b.pack(side="left", padx=(0, px(5)))
            chips[item] = b

        def paint(sel):
            for k, b in chips.items():
                on = k == sel
                b.configure(fg=ACCENT if on else DIM, bg=INPUT_BG if on else BG,
                            highlightbackground=ACCENT if on else BORDER, highlightcolor=ACCENT if on else BORDER)
        for k, b in chips.items():
            b.bind("<ButtonRelease-1>", lambda e, k=k: (on_pick(k), paint(k)))
        paint(current)
        return paint

    FOLLOW_HINTS = {"loose": "Uses your sketch as a rough layout. Archie invents more: good for environments and mood.",
                    "balanced": "Keeps your composition and poses, free with the details. The best place to start.",
                    "strict": "Stays right on your lines, like inking and coloring your drawing. Best for character designs."}
    STYLE_HINTS = {
        "concept art": "Loose, confident brushwork like a game or film pitch painting.",
        "cinematic still": "Looks like a frame from a live-action movie: real lighting, lens depth.",
        "anime": "Clean line art, flat cel shading, bold color.",
        "cel-shaded game art": "Hard-edged shading like a stylized 3D game.",
        "comic book": "Inked outlines, bold color, halftone texture.",
        "graphic novel noir": "High-contrast black and white with one accent color.",
        "painterly": "Visible brush strokes, soft edges, rich color.",
        "oil painting": "Thick, textured paint like a canvas.",
        "watercolor": "Soft washes and paper texture.",
        "ink and wash": "Brush ink lines with gray washes.",
        "charcoal": "Smudgy, dramatic, black and white.",
        "storyboard": "Quick gray-tone frames for planning shots in your series.",
        "character sheet": "Clean design view on a plain background, good for turnarounds.",
        "matte painting": "Huge detailed environments, film backdrop style.",
        "dark fantasy": "Moody, gothic, heavy shadows.",
        "sci-fi": "Hard surfaces, glowing tech, futuristic.",
        "3D render": "Smooth modeled look, like a Blender or Maya render.",
        "low poly": "Faceted shapes, flat colors, like the owl.",
        "pixel art": "Retro game pixels.",
        "clay / stop motion": "Handmade clay figures and sets.",
    }

    def _sketch_setup_view(self):
        px, body, sk, sw_ = self.px, self._skw["body"], self._sk, self._skw
        self._skw["sub"].configure(text="  from a sketch")
        row = tk.Frame(body, bg=BG)
        row.pack(fill="both", expand=True, padx=px(20), pady=(px(16), px(14)))
        left = tk.Frame(row, bg=BG, width=px(420))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        right = tk.Frame(row, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(px(22), 0))

        pv = tk.Frame(left, bg="#efeee8", height=px(275))
        pv.pack(fill="x")
        pv.pack_propagate(False)
        self._sketch_preview(pv, px(420), px(275)).place(relx=0.5, rely=0.5, anchor="center")
        info = tk.Frame(left, bg=BG)
        info.pack(fill="x", pady=(px(8), px(8)))
        tk.Label(info, text=os.path.basename(sk["path"])[:48], bg=BG, fg=MUTED, font=(MONO, 8)).pack(side="left")
        ch = tk.Label(info, text="change", bg=BG, fg=ACCENT, font=(MONO, 8), cursor="hand2")
        ch.pack(side="right")
        ch.bind("<ButtonRelease-1>", lambda e: (self._sk.update(path=None), self._sketch_view("pick")))
        card = tk.Frame(left, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x")
        tk.Label(card, text="archie read your sketch", bg=SURFACE, fg=ACCENT, font=(MONO, 8), anchor="w").pack(
            fill="x", padx=px(12), pady=(px(10), px(2)))
        sw_["summary"] = tk.Label(card, text=sk.get("summary") or "looking at it...", bg=SURFACE,
                                  fg=BODY if sk.get("summary") else MUTED, font=(FONT, 10),
                                  wraplength=px(390), justify="left", anchor="w")
        sw_["summary"].pack(fill="x", padx=px(12), pady=(0, px(10)))

        tk.Label(right, text="> describe it (Archie starts it for you; change anything)", bg=BG, fg=MUTED,
                 font=(MONO, 8), anchor="w").pack(fill="x")
        pbox = tk.Frame(right, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        pbox.pack(fill="x", pady=(px(4), px(12)))
        sw_["prompt"] = tk.Text(pbox, height=4, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, wrap="word", bd=0,
                                padx=px(10), pady=px(8), highlightthickness=0, font=(FONT, 10), undo=True)
        sw_["prompt"].pack(fill="x")
        if sk.get("prompt"):
            sw_["prompt"].insert("1.0", sk["prompt"])

        tk.Label(right, text="> follow my lines", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(fill="x")
        fr = tk.Frame(right, bg=BG)
        fr.pack(fill="x", pady=(px(4), 0))
        hint = tk.Label(right, text=self.FOLLOW_HINTS[sk["follow"]], bg=BG, fg=DIM, font=(FONT, 9), anchor="w",
                        justify="left", wraplength=px(440))
        self._chip_row(fr, ["loose", "balanced", "strict"], sk["follow"],
                       lambda k: (sk.update(follow=k), hint.configure(text=self.FOLLOW_HINTS[k])))
        hint.pack(fill="x", pady=(0, px(10)))

        tk.Label(right, text="> style", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(fill="x")
        st = tk.Frame(right, bg=BG)
        st.pack(fill="x", pady=(px(4), 0))
        shint = tk.Label(right, text=self.STYLE_HINTS.get(sk["style"], ""), bg=BG, fg=DIM, font=(FONT, 9),
                         anchor="w", justify="left", wraplength=px(440))
        self._chip_row(st, list(imagine.STYLES), sk["style"],
                       lambda k: (sk.update(style=k), shint.configure(text=self.STYLE_HINTS.get(k, ""))),
                       max_width=px(470))
        shint.pack(fill="x", pady=(0, px(10)))

        bottom = tk.Frame(right, bg=BG)
        bottom.pack(side="bottom", fill="x")
        gen = self._sketch_btn(bottom, "generate", self._sketch_generate, primary=True)
        gen.configure(font=(MONO, 11, "bold"), pady=px(12))
        gen.pack(side="bottom", fill="x", pady=(px(10), 0))
        opts = tk.Frame(bottom, bg=BG)
        opts.pack(side="bottom", fill="x")
        tk.Label(opts, text="shape", bg=BG, fg=MUTED, font=(MONO, 8)).pack(side="left", padx=(0, px(6)))
        shapes = tk.Frame(opts, bg=BG)
        shapes.pack(side="left")
        self._chip_row(shapes, ["square", "wide", "tall"], sk["shape"], lambda k: sk.update(shape=k))
        tk.Label(opts, text="how many", bg=BG, fg=MUTED, font=(MONO, 8)).pack(side="left", padx=(px(16), px(6)))
        cnt = tk.Frame(opts, bg=BG)
        cnt.pack(side="left")
        eta = tk.Label(opts, text="", bg=BG, fg=MUTED, font=(MONO, 8))
        eta.pack(side="right")

        def set_n(k):
            sk.update(n=k)
            eta.configure(text=f"about {k * 1.5:g} min")
        self._chip_row(cnt, [1, 2, 4], sk["n"], set_n)
        set_n(sk["n"])
        sw_["setup_msg"] = tk.Label(right, text="", bg=BG, fg="#f5a524", font=(MONO, 8), anchor="w")
        sw_["setup_msg"].pack(side="bottom", fill="x", pady=(0, px(6)))

    # --- 3 + 4. painting and results

    def _sketch_generate(self, seed=None):
        sk, sw_ = self._sk, self._skw
        if sk["busy"]:
            return
        if sk.get("view") == "setup":
            sk["prompt"] = sw_["prompt"].get("1.0", "end").strip()
        if not sk.get("prompt"):
            if sw_.get("setup_msg") and sw_["setup_msg"].winfo_exists():
                sw_["setup_msg"].configure(text="Describe the picture first (Archie may still be reading the sketch).")
            return
        sk.update(busy=True, results=[], sel=None, seed=seed)
        self._img_target = "sketch"
        self._sketch_view("paint")
        prompt = f"{sk['prompt']}, {imagine.STYLES.get(sk['style'], '')}".strip(", ")
        out = os.path.join(IMAGES_DIR, datetime.date.today().isoformat())
        args = (prompt, imagine.SKETCH_NEGATIVE, sk["shape"], sk["n"], 30, out, seed)

        def work():
            imagine.free_ollama_gpu(OLLAMA_URL)
            self.bg_q.put(("img", {"type": "status", "text": "starting the image helper..."}))
            try:
                self.imager.make(*args, sketch=sk["path"], follow=sk["follow"])
            except Exception as e:
                self.bg_q.put(("img", {"type": "error", "text": str(e)}))
        threading.Thread(target=work, daemon=True).start()

    def _sketch_paint_view(self):
        px, body, sk, sw_ = self.px, self._skw["body"], self._sk, self._skw
        self._skw["sub"].configure(text=f"  from a sketch · {sk['follow']} · {sk['style']}")
        row = tk.Frame(body, bg=BG)
        row.pack(fill="both", expand=True, padx=px(20), pady=(px(16), px(14)))
        left = tk.Frame(row, bg=BG, width=px(270))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        right = tk.Frame(row, bg=BG)
        right.pack(side="left", fill="both", expand=True, padx=(px(20), 0))

        tk.Label(left, text="> your sketch", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(fill="x")
        pv = tk.Frame(left, bg="#efeee8", height=px(175))
        pv.pack(fill="x", pady=(px(4), px(8)))
        pv.pack_propagate(False)
        self._sketch_preview(pv, px(270), px(175)).place(relx=0.5, rely=0.5, anchor="center")
        sw_["lines_var"] = tk.BooleanVar(value=sk["show_lines"])
        tk.Checkbutton(left, text="show my lines on top", variable=sw_["lines_var"], bg=BG, fg=DIM,
                       selectcolor=SURFACE, activebackground=BG, activeforeground=TEXT, font=(MONO, 8), bd=0,
                       highlightthickness=0, anchor="w", cursor="hand2",
                       command=lambda: (sk.update(show_lines=sw_["lines_var"].get()), self._sketch_gallery())
                       ).pack(fill="x")
        card = tk.Frame(left, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", pady=(px(8), 0))
        sw_["pstatus"] = tk.Label(card, text="making room on the graphics card...", bg=SURFACE, fg=TEXT,
                                  font=(MONO, 8), anchor="w", justify="left", wraplength=px(240))
        sw_["pstatus"].pack(fill="x", padx=px(10), pady=(px(10), px(6)))
        sw_["pbar"] = tk.Canvas(card, bg=SURFACE, highlightthickness=0, bd=0, height=px(6))
        sw_["pbar"].pack(fill="x", padx=px(10), pady=(0, px(10)))
        sw_["actions"] = tk.Frame(left, bg=BG)
        sw_["actions"].pack(fill="x", pady=(px(10), 0))
        low = tk.Frame(left, bg=BG)
        low.pack(side="bottom", fill="x")
        sw_["stop"] = self._sketch_btn(low, "stop", self._sketch_stop, small=True)
        sw_["stop"].pack(side="left", fill="x", expand=True)
        self._sketch_btn(low, "edit prompt", self._sketch_edit, small=True).pack(
            side="left", fill="x", expand=True, padx=(px(6), 0))
        other = "loose" if sk["follow"] == "strict" else "strict"
        sw_["try"] = self._sketch_btn(low, f"try {other}", lambda o=other: self._sketch_retry(o), small=True)
        sw_["try"].pack(side="left", fill="x", expand=True, padx=(px(6), 0))

        sw_["gallery"] = tk.Frame(right, bg=BG)
        sw_["gallery"].pack(fill="both", expand=True)
        self._sketch_gallery()

    def _sketch_edit(self):
        if not self._sk["busy"]:
            self._sketch_view("setup")

    def _sketch_retry(self, follow):
        if self._sk["busy"]:
            return
        self._sk["follow"] = follow
        self._sketch_generate()

    def _sketch_stop(self):
        if not self._sk["busy"]:
            return
        try:
            self.imager.stop()
        except Exception:
            pass
        self._sk["busy"] = False
        self._img_target = None
        if self._skw["pstatus"].winfo_exists():
            self._skw["pstatus"].configure(text="stopped.", fg=MUTED)

    def _sketch_gallery(self):
        """2 x 2 results (placeholders while painting)."""
        px, sk, sw_ = self.px, self._sk, self._skw
        g = sw_.get("gallery")
        if not g or not g.winfo_exists():
            return
        for c in g.winfo_children():
            c.destroy()
        g.update_idletasks()
        cw = max(px(300), (g.winfo_width() or px(620)) // 2 - px(8))
        ch = int(cw * 0.66)
        lines = None
        if sk["show_lines"] and sk.get("lines") and os.path.exists(sk["lines"]):
            try:
                lines = Image.open(sk["lines"]).convert("L")
            except Exception:
                lines = None
        for i in range(max(sk["n"], len(sk["results"]))):
            r, c = divmod(i, 2)
            if i < len(sk["results"]):
                path, seed = sk["results"][i]
                try:
                    im = Image.open(path).convert("RGB")
                    if lines is not None:
                        ov = lines.resize(im.size)
                        white = Image.new("RGB", im.size, (255, 255, 255))
                        im = Image.composite(white, im, ov.point(lambda v: int(v * 0.7)))
                    im.thumbnail((cw, ch))
                    photo = ImageTk.PhotoImage(im)
                except Exception:
                    continue
                on = sk["sel"] == i
                lab = tk.Label(g, image=photo, bg=BG, bd=0, cursor="hand2", highlightthickness=2,
                               highlightbackground=ACCENT if on else BORDER)
                lab.image = photo
                lab.bind("<ButtonRelease-1>", lambda e, i=i: self._sketch_select(i))
                lab.bind("<Double-Button-1>", lambda e, p=path: open_folder(p))
            else:
                lab = tk.Frame(g, bg="#0d0d0d", width=cw, height=ch, highlightthickness=1,
                               highlightbackground=ACCENT if (sk["busy"] and i == len(sk["results"])) else BORDER)
            lab.grid(row=r, column=c, padx=px(4), pady=px(4))
        self._sketch_actions()

    def _sketch_select(self, i):
        self._sk["sel"] = i
        self._sketch_gallery()

    def _sketch_actions(self):
        px, sk, box = self.px, self._sk, self._skw.get("actions")
        if not box or not box.winfo_exists():
            return
        for c in box.winfo_children():
            c.destroy()
        if sk["sel"] is None or sk["sel"] >= len(sk["results"]):
            if sk["results"] and not sk["busy"]:
                tk.Label(box, text="click a picture for options (double-click opens it)", bg=BG, fg=MUTED,
                         font=(MONO, 8), anchor="w").pack(fill="x")
            return
        path, seed = sk["results"][sk["sel"]]
        tk.Label(box, text=f"picked: #{sk['sel'] + 1}", bg=BG, fg=ACCENT, font=(MONO, 8), anchor="w").pack(
            fill="x", pady=(0, px(4)))
        for text, cmd, prim in (("open full size", lambda: open_folder(path), False),
                                ("more like this one", lambda: self._sketch_generate(seed=seed + 1000), False),
                                ("ask Archie about it", lambda: (self.add_attachments([path]), self.panel.lift()), False),
                                ("save to Obsidian", lambda: self._image_to_obsidian(path, None), True)):
            self._sketch_btn(box, text, cmd, primary=prim, small=True).pack(fill="x", pady=(0, px(4)))

    def _sketch_event(self, ev):
        """Image helper events while a sketch is painting."""
        sk, sw_ = self._sk, getattr(self, "_skw", {})
        kind = ev.get("type")
        alive = sw_.get("pstatus") is not None and sw_["pstatus"].winfo_exists()
        if kind == "bye":
            return
        if kind == "status" and alive:
            sw_["pstatus"].configure(text=ev["text"], fg=TEXT)
        elif kind == "lines":
            sk["lines"] = ev["path"]
        elif kind == "progress" and alive:
            frac = (ev["i"] + ev["step"] / float(ev["steps"])) / ev["n"]
            sw_["pstatus"].configure(text=f"painting {ev['i'] + 1} of {ev['n']} · step {ev['step']}/{ev['steps']}",
                                     fg=TEXT)
            c, px = sw_["pbar"], self.px
            c.delete("all")
            W = max(c.winfo_width(), px(200))
            c.create_rectangle(0, 0, W, px(6), fill=BORDER, width=0)
            c.create_rectangle(0, 0, W * frac, px(6), fill=ACCENT, width=0)
        elif kind == "image":
            sk["results"].append((ev["path"], ev["seed"]))
            if sk["sel"] is None:
                sk["sel"] = 0
            self._sketch_gallery()
        elif kind == "done":
            sk["busy"] = False
            self._img_target = None
            if alive:
                sw_["pstatus"].configure(text="done. click a picture for options.", fg=ACCENT)
            self._sketch_gallery()
            try:
                if not self.sketch_win.winfo_viewable():      # it was closed: bring it back
                    self.sketch_win.deiconify()
                self.sketch_win.lift()
            except tk.TclError:
                pass
        elif kind == "error":
            sk["busy"] = False
            self._img_target = None
            if alive:
                sw_["pstatus"].configure(text="Couldn't make it: " + ev["text"], fg=REC)
            else:
                self._write(f"Sketch to image: {ev['text']}\n", "sys")

    # ----- the evening recap ----------------------------------------------------

    def _draw_recap_chip(self):
        """The recap pill next to the timer: idle, recording, working, or ready."""
        c, px = self.recap_chip, self.px
        c.delete("all")
        st = self._recap_state
        evening = datetime.datetime.now().hour >= 19 and not self.recap.done_today()
        if st == "recording":
            dot = "●" if int(time.time() * 2) % 2 == 0 or self.recorder.paused else " "
            text, col, edge, moon = f"{dot} rec {fmt_time(self.recorder.seconds())}", REC, REC, False
        elif st == "processing":
            pct = getattr(self, "_recap_pct", None)
            text, col, edge, moon = (f"recap {int(pct * 100)}%" if pct is not None else "recap ···"), MUTED, BORDER, True
        elif st == "review":
            text, col, edge, moon = "recap ready", ACCENT, ACCENT, True
        else:
            text, col, edge, moon = "recap", ACCENT if evening else MUTED, ACCENT if evening else BORDER, True
        font = tkfont.Font(family=MONO, size=8)
        tw = font.measure(text)
        h = px(22)
        mx = px(9)
        tx = px(10) + (px(12) if moon else 0)
        w = tx + tw + px(10) + (px(9) if (st == "idle" and evening) else 0)
        self._chip_w["recap"] = (w, h + (px(9) if (st == "idle" and evening) else 0))
        icon_only = self._chips_compact and st == "idle"
        if icon_only:
            w = h + (px(9) if evening else 0)
            mx = px(4)
        key = ("recapchip", w, edge)
        if self.imgs.get("recapchip_key") != key:
            try:
                self.imgs["recapchip"] = th.rounded(w, h, h // 2, BG, edge)
                self.imgs["recapchip_key"] = key
            except Exception:
                self.imgs["recapchip"] = None
        c.configure(width=w, height=h)
        if self.imgs.get("recapchip"):
            c.create_image(0, 0, anchor="nw", image=self.imgs["recapchip"])
        if moon:     # a crescent: a lit circle with a dark one over it
            r = px(4.5)
            c.create_oval(mx + px(2) - r, h / 2 - r, mx + px(2) + r, h / 2 + r, fill=col, outline="")
            c.create_oval(mx + px(4.5) - r, h / 2 - r - px(2), mx + px(4.5) + r, h / 2 + r - px(2),
                          fill=BG, outline="")
        if not icon_only:
            c.create_text(tx, h / 2, anchor="w", text=text, fill=col, font=(MONO, 8))
        if st == "idle" and evening:
            c.create_oval(w - px(12), h / 2 - px(2.5), w - px(7), h / 2 + px(2.5), fill=ACCENT, outline="")
        self._chip_changed("recap", w)

    def _chip_changed(self, name, w):
        last = getattr(self, "_chip_drawn", {})
        self._chip_drawn = last
        if last.get(name) != w:
            last[name] = w
            if not getattr(self, "_fitting", False):
                self.root.after_idle(self._fit_header)

    def _fit_header(self):
        """Make the header fit the chat's width. Step by step, only as far as needed:
        timer and recap become icons, the ARCHIE word hides, the date drops the weekday,
        the model name shortens, the running timer drops its dot."""
        if getattr(self, "_fitting", False) or not hasattr(self, "recap_chip"):
            return
        head = self.chip.master
        avail = head.winfo_width()
        if avail < 120:
            return
        self._fitting = True
        px = self.px
        try:
            for level in range(6):
                self._chips_compact = level >= 1
                show_title = level < 2
                self._date_compact = level >= 3
                self._model_short = level >= 4
                self._focus_nodot = level >= 5
                placed = bool(self.head_title.winfo_manager())
                if show_title and not placed:
                    self.head_title.pack(side="left", padx=(0, px(8)), before=self.chip)
                elif not show_title and placed:
                    self.head_title.pack_forget()
                self._draw_chip()
                self._draw_date_chip()
                self._draw_focus_chip()
                self._draw_recap_chip()
                need = sum(c.winfo_reqwidth() for c in head.winfo_children()
                           if c is not self.head_title and c.winfo_manager()) + px(6) * 3 + px(8)
                if show_title:
                    need += self.head_title.winfo_reqwidth() + px(8)
                if need <= avail:
                    break
        finally:
            self._fitting = False
        if getattr(self, "banner", None) is not None:
            self.root.after_idle(self._banner_place)

    def _recap_chip_click(self):
        if self._recap_state == "idle":
            self.start_recap()
        else:
            self.show_recap()

    def hotkey_recap(self):
        if self._recap_state == "recording":
            self._recap_finish()
        elif self._recap_state == "idle":
            self.start_recap()
        else:
            self.show_recap()

    def start_recap(self):
        if self.recorder.recording:
            if self._rec_kind == "recap":
                self.show_recap()
            else:
                self._write("Finish the voice note first (click stop), then start the recap.\n", "sys")
            return
        if not self.panel_visible():
            self.show_panel()
        self.stop_speaking()
        try:
            self.recorder.start()
        except VoiceError as e:
            self._write(str(e) + "\n", "sys")
            return
        self.recorder.paused = False
        self._rec_kind = "recap"
        self._recap_state = "recording"
        self._recap_levels = []
        self._recap_crossed = set()
        self._recap_started = datetime.datetime.now()
        self._style_mic()
        self.show_recap()
        self._recap_tick()

    def show_recap(self):
        px = self.px
        if not self.panel_visible():
            self.show_panel()
        w = getattr(self, "recap_win", None)
        if w is None or not w.winfo_exists():
            w = self._build_recap_win()
        W, H = px(460), px(max(640, self.PANEL_H))
        w.geometry(f"{W}x{H}+{self.panel.winfo_x() + px(10)}+{self.panel.winfo_y() + px(10)}")
        view = {"recording": "record", "processing": "process", "review": "review"}.get(self._recap_state)
        if view is None:
            w.withdraw()
            return
        self._recap_show_view(view)
        w.deiconify()
        w.lift()

    def _build_recap_win(self):
        px = self.px
        w = self.recap_win = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        rw = self._rw = {}

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        tk.Label(top, text="EVENING RECAP", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        rw["when"] = tk.Label(top, text="", bg=BG, fg=MUTED, font=(MONO, 8))
        rw["when"].pack(side="left", padx=(px(10), 0))
        self._icon_btn(top, "close", lambda: w.withdraw(),
                       "Hide (the recap keeps going; click recap at the top to come back)").pack(side="right")
        for wd in (top,) + tuple(top.winfo_children()[:2]):
            wd.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
            wd.bind("<B1-Motion>", lambda e: w.geometry(
                f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))
        tk.Frame(w, bg=th.LINE, height=1).pack(fill="x")
        rw["views"] = tk.Frame(w, bg=BG)
        rw["views"].pack(fill="both", expand=True)

        # --- recording
        v = rw["v_record"] = tk.Frame(rw["views"], bg=BG)
        rw["wave"] = tk.Canvas(v, bg=BG, highlightthickness=0, bd=0, height=px(90))
        rw["wave"].pack(fill="x", padx=px(20), pady=(px(22), px(4)))
        row = tk.Frame(v, bg=BG)
        row.pack()
        rw["time"] = tk.Label(row, text="0:00", bg=BG, fg=TEXT, font=(MONO, 36))
        rw["time"].pack(side="left")
        rw["rec"] = tk.Label(row, text="● recording", bg=BG, fg=REC, font=(MONO, 9))
        rw["rec"].pack(side="left", padx=(px(12), 0), pady=(px(14), 0))
        card = tk.Frame(v, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=px(20), pady=(px(18), 0))
        tk.Label(card, text="> talk about (any order, skip what you want; click one to cross it off)",
                 bg=SURFACE, fg=MUTED, font=(MONO, 8), anchor="w").pack(fill="x", padx=px(12), pady=(px(10), px(4)))
        rw["prompts"] = []
        for i, ptext in enumerate(recapmod.PROMPTS):
            lab = tk.Label(card, text=ptext, bg=SURFACE, fg=TEXT, font=(FONT, 11), anchor="w", cursor="hand2")
            lab.pack(fill="x", padx=px(12), pady=px(2))
            lab.bind("<ButtonRelease-1>", lambda e, i=i: self._recap_cross(i))
            rw["prompts"].append(lab)
        tk.Frame(card, bg=SURFACE, height=px(8)).pack()
        tk.Label(v, text="stays on your PC. nothing goes online.", bg=BG, fg=MUTED,
                 font=(MONO, 8)).pack(pady=(px(12), 0))
        row = tk.Frame(v, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(20), pady=(px(12), px(18)))
        rw["pause"] = self._fbtn(row, "pause", self._recap_pause)
        rw["pause"].pack(side="left")
        self._fbtn(row, "cancel", self._recap_cancel).pack(side="left", padx=(px(8), 0))
        self._fbtn(row, "done, wrap it up", self._recap_finish, primary=True).pack(
            side="right", fill="x", expand=True, padx=(px(8), 0))

        # --- typing it out and sorting it
        v = rw["v_process"] = tk.Frame(rw["views"], bg=BG)
        card = tk.Frame(v, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=px(20), pady=(px(20), 0))
        rw["steps"] = []
        for label in ("recorded", "typing it out on your PC", "sorting it into today, tomorrow and what's on your mind"):
            r = tk.Frame(card, bg=SURFACE)
            r.pack(fill="x", padx=px(12), pady=(px(10), 0))
            mark = tk.Label(r, text="○", bg=SURFACE, fg=MUTED, font=(MONO, 11), width=2)
            mark.pack(side="left")
            txt = tk.Label(r, text=label, bg=SURFACE, fg=MUTED, font=(FONT, 11), anchor="w",
                           wraplength=px(330), justify="left")
            txt.pack(side="left", fill="x", expand=True)
            pct = tk.Label(r, text="", bg=SURFACE, fg=ACCENT, font=(MONO, 9))
            pct.pack(side="right")
            rw["steps"].append((mark, txt, pct))
        rw["bar"] = tk.Canvas(card, bg=SURFACE, highlightthickness=0, bd=0, height=px(8))
        rw["bar"].pack(fill="x", padx=(px(40), px(12)), pady=(px(8), px(4)))
        rw["heard"] = tk.Label(card, text="", bg=SURFACE, fg=DIM, font=(FONT, 10), anchor="w",
                               justify="left", wraplength=px(370))
        rw["heard"].pack(fill="x", padx=px(12), pady=(px(6), px(12)))
        rw["pnote"] = tk.Label(v, text="about a minute. you can close this, it keeps going and pops up when "
                                       "it's ready.", bg=BG, fg=MUTED, font=(MONO, 8), wraplength=px(400))
        rw["pnote"].pack(pady=(px(12), 0))
        row = tk.Frame(v, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(20), pady=(px(12), px(18)))
        rw["p_btns"] = row

        # --- review (filled in when it's ready)
        rw["v_review"] = tk.Frame(rw["views"], bg=BG)
        w.bind("<Escape>", lambda e: w.withdraw())
        return w

    def _recap_show_view(self, name):
        rw = self._rw
        for n in ("record", "process", "review"):
            rw["v_" + n].pack_forget()
        rw["v_" + name].pack(fill="both", expand=True)
        started = getattr(self, "_recap_started", None) or datetime.datetime.now()
        rw["when"].configure(text=started.strftime("%a %b %d · %I:%M %p").replace(" 0", " ").lower())
        if name == "review":
            self._recap_fill_review()

    def _recap_cross(self, i):
        lab = self._rw["prompts"][i]
        crossed = i in self._recap_crossed
        (self._recap_crossed.discard if crossed else self._recap_crossed.add)(i)
        lab.configure(fg=TEXT if crossed else MUTED,
                      font=(FONT, 11) if crossed else tkfont.Font(family=FONT, size=11, overstrike=1))

    def _recap_tick(self):
        if self._recap_state != "recording" or not self.recorder.recording:
            return
        rw = getattr(self, "_rw", None)
        lv = 0.0 if self.recorder.paused else self.recorder.level
        self._recap_levels.append(lv)
        self._recap_levels = self._recap_levels[-44:]
        if rw and rw["wave"].winfo_exists() and rw["wave"].winfo_viewable():
            c, px = rw["wave"], self.px
            c.delete("all")
            W, H = max(c.winfo_width(), px(400)), px(90)
            n, bw, gap = 44, px(5), px(3)
            x0 = (W - (n * bw + (n - 1) * gap)) / 2
            levels = [0.0] * (n - len(self._recap_levels)) + self._recap_levels
            for i, v in enumerate(levels):
                bh = max(px(3), min(H, (0.08 + 0.92 * min(1.0, v * 1.6)) * H * (0.35 if v == 0 else 1)))
                x = x0 + i * (bw + gap)
                c.create_rectangle(x, (H - bh) / 2, x + bw, (H + bh) / 2,
                                   fill=ACCENT if v > 0 else BORDER, width=0)
            rw["time"].configure(text=fmt_time(self.recorder.seconds()))
            rw["rec"].configure(text="paused" if self.recorder.paused else "● recording",
                                fg=MUTED if self.recorder.paused else REC)
        self._draw_recap_chip()
        self._style_mic()
        self.root.after(100, self._recap_tick)

    def _recap_pause(self):
        self.recorder.paused = not self.recorder.paused
        self._rw["pause"].configure(text="resume" if self.recorder.paused else "pause")

    def _recap_cancel(self):
        path = None
        if self.recorder.recording:
            path, _secs = self.recorder.stop()
        self.recorder.paused = False
        if path:
            try:
                os.remove(path)
            except OSError:
                pass
        self._recap_state = "idle"
        self._style_mic()
        self._draw_recap_chip()
        if getattr(self, "recap_win", None):
            self.recap_win.withdraw()

    def _recap_finish(self):
        """Stop recording, type it out, sort it."""
        if not self.recorder.recording:
            return
        self.recorder.paused = False
        path, secs = self.recorder.stop()
        self._style_mic()
        if not path:
            self._recap_state = "idle"
            self._draw_recap_chip()
            if getattr(self, "recap_win", None):
                self.recap_win.withdraw()
            self._write("That recap was too short to keep. Try again and talk for a bit longer.\n", "sys")
            return
        stamp = (getattr(self, "_recap_started", None) or datetime.datetime.now()).strftime("%Y-%m-%d_%H%M%S")
        new = os.path.join(os.path.dirname(path), f"Recap {stamp}.wav")
        try:
            os.replace(path, new)
            path = new
        except OSError:
            pass
        self._recap_audio, self._recap_secs = path, secs
        self._recap_state = "processing"
        self._recap_pct = 0.0
        self.show_recap()
        self._recap_steps(1, 0.0)
        self._recap_process(path, secs)

    def _recap_steps(self, stage, frac=None, heard=None):
        """stage 1 = typing it out, 2 = sorting, 3 = done."""
        rw = getattr(self, "_rw", None)
        if not rw or not rw["steps"][0][0].winfo_exists():
            return
        for i, (mark, txt, pct) in enumerate(rw["steps"]):
            if i < stage:
                mark.configure(text="✓", fg=ACCENT)
                txt.configure(fg=DIM)
                pct.configure(text="")
            elif i == stage:
                mark.configure(text="●", fg=ACCENT)
                txt.configure(fg=TEXT)
                pct.configure(text=f"{int(frac * 100)}%" if (frac is not None and stage == 1) else "")
            else:
                mark.configure(text="○", fg=MUTED)
                txt.configure(fg=MUTED)
        rw["steps"][0][1].configure(text=f"recorded ({fmt_time(getattr(self, '_recap_secs', 0))})")
        c, px = rw["bar"], self.px
        c.delete("all")
        W = max(c.winfo_width(), px(300))
        c.create_rectangle(0, 0, W, px(6), fill=BORDER, width=0)
        f = (frac or 0.0) if stage == 1 else (1.0 if stage > 1 else 0.0)
        c.create_rectangle(0, 0, W * f, px(6), fill=ACCENT, width=0)
        if heard is not None:
            rw["heard"].configure(text=(f'> heard: "{heard[:260]}{"..." if len(heard) > 260 else ""}"'
                                        if heard else ""))
        for b in rw["p_btns"].winfo_children():
            b.destroy()
        self._fbtn(rw["p_btns"], "cancel", self._recap_discard).pack(side="left", fill="x", expand=True)

    def _recap_process(self, path, secs):
        tr = self._get_transcriber()
        f = self.focus
        focus_line = (f"The user finished {f.done_today} focus session(s) today, {f.minutes_today} minutes in all."
                      if f.done_today else "")
        token = object()
        self._recap_job = token

        def ui(fn):
            self.bg_q.put(("call", lambda: fn() if self._recap_job is token else None))

        def work():
            self._fg_transcribing = True
            try:
                text = tr.transcribe(path, progress=lambda fr: ui(lambda fr=fr: (
                    setattr(self, "_recap_pct", fr), self._recap_steps(1, fr), self._draw_recap_chip())))
            except Exception as e:
                ui(lambda msg=str(e): self._recap_failed(f"Couldn't type it out: {msg}", None))
                return
            finally:
                self._fg_transcribing = False
            try:
                with open(os.path.splitext(path)[0] + ".txt", "w", encoding="utf-8") as fh:
                    fh.write(text + "\n")
            except OSError:
                pass
            if not text.strip():
                ui(lambda: self._recap_failed("I couldn't hear any words in that recording.", ""))
                return
            ui(lambda: (setattr(self, "_recap_pct", None), self._recap_steps(2, None, text),
                        self._draw_recap_chip()))
            try:
                data = recapmod.sort_recap(quick_chat, self.cfg["model"], text, focus_line)
            except Exception as e:
                data = {"today": [], "tomorrow": [], "mind": [], "summary": "", "error": str(e)}
            data["transcript"] = text
            ui(lambda: self._recap_ready(data))
        threading.Thread(target=work, daemon=True).start()

    def _recap_failed(self, msg, text):
        self._recap_state = "review"
        self._recap_data = {"today": [], "tomorrow": [], "mind": [], "summary": "",
                            "transcript": text or "", "error": msg}
        self._draw_recap_chip()
        self.show_recap()

    def _recap_ready(self, data):
        """Sorted: show it for review, popping it up even if it was hidden."""
        self._recap_data = data
        self._recap_state = "review"
        self._draw_recap_chip()
        self.show_recap()
        try:
            self.recap_win.lift()
            self.recap_win.focus_force()
        except tk.TclError:
            pass

    def _recap_fill_review(self):
        px, rw = self.px, self._rw
        v = rw["v_review"]
        for ch in v.winfo_children():
            ch.destroy()
        data = self._recap_data or {}
        f = self.focus
        today_lines = list(data.get("today", []))
        if f.done_today and not any("focus" in x.lower() for x in today_lines):
            today_lines.append(f"{f.done_today} focus session{'s' if f.done_today != 1 else ''}, "
                               f"{f.minutes_today} min")
        card = tk.Frame(v, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True, padx=px(14), pady=(px(10), 0))
        size = self.TEXT_SIZES.get(self.cfg.get("text_size"), 10)

        def head(text):
            tk.Label(card, text=text, bg=SURFACE, fg=MUTED, font=(MONO, 8), anchor="w").pack(
                fill="x", padx=px(14), pady=(px(10), px(2)))

        def box(lines):
            t = tk.Text(card, height=max(1, min(5, len(lines))), bg=SURFACE, fg=TEXT, insertbackground=ACCENT,
                        bd=0, wrap="word", font=(FONT, size), highlightthickness=0, undo=True)
            t.insert("1.0", "\n".join(lines))
            t.pack(fill="x", padx=px(14))
            return t

        if data.get("error"):
            tk.Label(card, text=data["error"] + ("  The transcript is below the lists." if data.get("transcript") else ""),
                     bg=SURFACE, fg="#f5a524", font=(FONT, 10), anchor="w", justify="left",
                     wraplength=px(380)).pack(fill="x", padx=px(14), pady=(px(10), 0))
        head("> today")
        rw["r_today"] = box(today_lines)
        head("> tomorrow · checked ones go on your to-do list")
        rw["r_tasks"] = []
        for t in data.get("tomorrow", []) or []:
            r = tk.Frame(card, bg=SURFACE)
            r.pack(fill="x", padx=px(10), pady=px(1))
            var = tk.BooleanVar(value=t.get("keep", True))
            tk.Checkbutton(r, variable=var, bg=SURFACE, activebackground=SURFACE, selectcolor=BG,
                           fg=ACCENT, bd=0, highlightthickness=0, cursor="hand2").pack(side="left")
            e = tk.Entry(r, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0, font=(FONT, size),
                         highlightthickness=0)
            e.insert(0, t["task"])
            e.pack(side="left", fill="x", expand=True)
            tk.Label(r, text=recapmod.due_label(t["due"]), bg=SURFACE, fg=MUTED, font=(MONO, 8)).pack(side="right")
            rw["r_tasks"].append((var, e, t["due"]))
        if not data.get("tomorrow"):
            tk.Label(card, text="(nothing for tomorrow. add tasks later with  add: ...)", bg=SURFACE, fg=MUTED,
                     font=(FONT, 10), anchor="w").pack(fill="x", padx=px(14))
        head("> on your mind")
        rw["r_mind"] = box(data.get("mind") or [])
        links = tk.Frame(card, bg=SURFACE)
        links.pack(fill="x", padx=px(14), pady=(px(10), px(12)))
        for text, cmd in (("full transcript", lambda: self.show_transcript(
                              getattr(self, "_recap_audio", ""), getattr(self, "_recap_secs", 0),
                              (self._recap_data or {}).get("transcript", ""))),
                          ("play it back", lambda: self._open_path(getattr(self, "_recap_audio", "")))):
            l = tk.Label(links, text=text, bg=SURFACE, fg=ACCENT, font=(MONO, 8), cursor="hand2")
            l.pack(side="left", padx=(0, px(14)))
            l.bind("<ButtonRelease-1>", lambda e, c=cmd: c())
        tk.Label(links, text=fmt_time(getattr(self, "_recap_secs", 0)), bg=SURFACE, fg=MUTED,
                 font=(MONO, 8)).pack(side="right")
        row = tk.Frame(v, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(14), pady=(px(12), px(16)))
        self._fbtn(row, "discard", self._recap_discard).pack(side="left")
        self._fbtn(row, "redo", self._recap_redo).pack(side="left", padx=(px(8), 0))
        self._fbtn(row, "save to tomorrow + daily note", self._recap_save, primary=True).pack(
            side="right", fill="x", expand=True, padx=(px(8), 0))

    def _open_path(self, path):
        if path and os.path.exists(path):
            try:
                os.startfile(path) if sys.platform == "win32" else open_folder(path)
            except Exception as e:
                self._write(f"Couldn't open it: {e}\n", "sys")

    def _recap_discard(self):
        self._recap_job = None
        self._recap_state = "idle"
        self._recap_data = None
        self._draw_recap_chip()
        if getattr(self, "recap_win", None):
            self.recap_win.withdraw()

    def _recap_redo(self):
        self._recap_discard()
        self.start_recap()

    def _recap_save(self):
        rw, data = self._rw, dict(self._recap_data or {})

        def lines(t):
            return [x.strip(" -•\t") for x in t.get("1.0", "end").splitlines()
                    if x.strip(" -•\t") and not x.startswith("(nothing")]
        data["today"] = lines(rw["r_today"])
        data["mind"] = lines(rw["r_mind"])
        tasks, added = [], 0
        for var, e, due in rw["r_tasks"]:
            text = e.get().strip()
            if not text:
                continue
            tasks.append({"task": text, "due": due, "keep": bool(var.get())})
            if var.get():
                try:
                    self.tasks.add(text, datetime.date.fromisoformat(due))
                    added += 1
                except Exception:
                    pass
        data["tomorrow"] = tasks
        data["saved_at"] = datetime.datetime.now().isoformat(timespec="seconds")
        data["audio"] = getattr(self, "_recap_audio", "")
        data.pop("error", None)
        where = ""
        vault = self.vault()
        if vault:
            try:
                d = datetime.date.today()
                rel = obs.save_note(vault, f"Evening recap {d.isoformat()}", recapmod.note_markdown(data),
                                    subfolder="Recaps")
                data["note"] = rel
                where = " It's in Obsidian (Archie/Recaps)"
                try:
                    if not self.cfg.get("daily_note", True):   # 2026-11-08: respect the daily-note checkbox
                        raise OSError("daily note is off")
                    self.daily.log(f"evening recap: [[{obs.link_name(rel)}]]")
                    where += " and linked in today's daily note"
                except Exception:
                    pass
                where += "."
            except Exception as e:
                where = f" (Couldn't save it to Obsidian: {e})"
        try:
            self.recap.save(data)
        except OSError as e:
            self._write(f"Couldn't save the recap: {e}\n", "sys")
            return
        self._recap_state = "idle"
        self._recap_data = None
        self._draw_recap_chip()
        if getattr(self, "recap_win", None):
            self.recap_win.withdraw()
        n = f"{added} task{'s' if added != 1 else ''} on your list" if added else "nothing added to your list"
        self._write(f"Saved your recap: {n}. It'll be in tomorrow's brief.{where}\n", "sys")

    # ----- the header picture strip (Banners folder) ----------------------------

    BANNER_PACES = (("every 5 minutes", 5), ("every 15 minutes", 15), ("every 30 minutes", 30),
                    ("every hour", 60), ("once a day", 1440), ("only when I click", 0))

    def _build_banner(self):
        self.banner = tk.Canvas(self.panel, bg=BG, highlightthickness=0, bd=0, cursor="hand2")
        self.banner.bind("<ButtonRelease-1>", lambda e: self._banner_next())
        self.banner.bind("<Button-3>", self._banner_menu)
        self._banner_size = None
        self._banner_pil = None
        self._banner_job = None
        self._banner_tod = None
        self._banner_timer_text = None
        self._banner_load()
        self.banner_menu = tk.Menu(self.panel, tearoff=0)

    def _banner_folder_stamp(self):
        try:
            return (os.path.getmtime(BANNERS_DIR), len(os.listdir(BANNERS_DIR)))
        except OSError:
            return None

    def _banner_watch(self):
        """Every 20 seconds: pictures added to (or removed from) the Banners folder join in."""
        try:
            stamp = self._banner_folder_stamp()
            if stamp != getattr(self, "_banner_stamp", None):
                was = self._banner_list[self._banner_i] if self._banner_list else None
                self._banner_load()
                if was in self._banner_list:
                    self._banner_i = self._banner_list.index(was)
                new = [p for p in self._banner_list if p not in getattr(self, "_banner_seen", set())]
                self._banner_seen = set(self._banner_list)
                if new and getattr(self, "_banner_stamp", None) is not None:
                    self._banner_i = self._banner_list.index(new[-1])    # show the newest one right away
                    self._banner_size = None
                self._banner_stamp = stamp
                self._banner_place()
                if self._banner_size and new:
                    self._banner_draw(crossfade=True)
        except Exception:
            pass
        self.root.after(20000, self._banner_watch)

    def _banner_load(self):
        os.makedirs(BANNERS_DIR, exist_ok=True)
        self._banner_list = banner.list_pictures(BANNERS_DIR)
        self._banner_focus = banner.load_focus(BANNERS_DIR)
        n = len(self._banner_list)
        pinned = self.cfg.get("banner_pinned")
        if pinned and pinned in self._banner_list:
            self._banner_i = self._banner_list.index(pinned)
        elif n and int(self.cfg.get("banner_minutes", 15)) == 1440:
            self._banner_i = datetime.date.today().toordinal() % n
        else:
            self._banner_i = random.randrange(n) if n else 0

    def _banner_place(self):
        """Fit the strip between the recap button and the icons, from the window's top edge
        down to just above the mode tabs."""
        b = getattr(self, "banner", None)
        if b is None:
            return
        px, p = self.px, self.panel
        try:
            if not self.cfg.get("banner", True) or not self._banner_list or not p.winfo_ismapped():
                b.place_forget()
                return
            self.recap_chip.master.update_idletasks()      # measure after the buttons settle
            icons = [w for w in getattr(self, "head_icons", []) if w.winfo_ismapped()]
            x0 = self.recap_chip.winfo_rootx() - p.winfo_rootx() + self.recap_chip.winfo_width() + px(10)
            x1 = (min(w.winfo_rootx() for w in icons) - p.winfo_rootx() - px(8)) if icons else p.winfo_width() - px(20)
            y1 = self.tabs.winfo_rooty() - p.winfo_rooty() - px(4)
        except tk.TclError:
            return
        W, H = x1 - x0, y1
        if W < px(90) or H < px(20):
            b.place_forget()
            return
        b.place(x=x0, y=0, width=W, height=H)
        b.tk.call("raise", b._w)           # above the header (Canvas.lift means something else)
        if self._banner_size != (W, H):
            self._banner_size = (W, H)
            self._banner_draw()

    def _banner_frame(self):
        if not self._banner_list or not self._banner_size:
            return None
        W, H = self._banner_size
        path = self._banner_list[self._banner_i % len(self._banner_list)]
        f = self.focus
        timer = None
        if f.running:
            timer = (f.progress, f.clock())
        focus = self._banner_focus.get(os.path.basename(path).lower(), (50.0, 55.0))
        try:
            tod = getattr(self, "_banner_tod_preview", None) or banner.time_of_day()
            return banner.compose(path, W, H, focus, tod, timer,
                                  os.path.join(FONTS_DIR, "JetBrainsMono-Bold.ttf"), scale=self.scale,
                                  clock=datetime.datetime.now().strftime("%H:%M"),
                                  clock_font=self._clock_font())
        except Exception:
            return None

    def _clock_font(self):
        p = os.path.join(FONTS_DIR, "Micro5-Regular.ttf")
        return p if os.path.exists(p) else os.path.join(FONTS_DIR, "JetBrainsMono-Bold.ttf")

    def _banner_draw(self, crossfade=False):
        img = self._banner_frame()
        if img is None:
            return
        old = self._banner_pil if crossfade and self._banner_pil is not None and \
            self._banner_pil.size == img.size else None
        self._banner_pil = img
        if old is None:
            self._banner_show(img)
            return
        steps = 12

        def step(k=1):
            if self._banner_pil is not img:
                return                      # something newer was drawn meanwhile
            self._banner_show(Image.blend(old, img, k / float(steps)))
            if k < steps:
                self.root.after(45, lambda: step(k + 1))
        step()

    def _banner_show(self, pil):
        try:
            self.imgs["banner"] = ImageTk.PhotoImage(pil)
            self.banner.delete("all")
            self.banner.create_image(0, 0, anchor="nw", image=self.imgs["banner"])
        except tk.TclError:
            pass

    def _banner_next(self, step=1):
        if not self._banner_list:
            return
        self._banner_i = (self._banner_i + step) % len(self._banner_list)
        if self.cfg.get("banner_pinned"):
            self.cfg["banner_pinned"] = self._banner_list[self._banner_i]
            save_config(self.cfg)
        self._banner_draw(crossfade=True)
        self._banner_schedule()

    def _banner_schedule(self):
        if self._banner_job:
            try:
                self.root.after_cancel(self._banner_job)
            except tk.TclError:
                pass
            self._banner_job = None
        mins = int(self.cfg.get("banner_minutes", 15) or 0)
        if mins <= 0 or self.cfg.get("banner_pinned"):
            return
        if mins >= 1440:     # once a day: check back every hour for the new day
            self._banner_job = self.root.after(3600000, self._banner_daily)
            return
        self._banner_job = self.root.after(mins * 60000, lambda: self._banner_next())

    def _banner_daily(self):
        n = len(self._banner_list)
        if n:
            i = datetime.date.today().toordinal() % n
            if i != self._banner_i:
                self._banner_i = i
                self._banner_draw(crossfade=True)
        self._banner_schedule()

    def _banner_tick(self):
        """From the focus tick: redraw when the timer's time changes, or the time of day does."""
        if getattr(self, "banner", None) is None or not self._banner_size:
            return
        f = self.focus
        text = (f.clock() if f.running else "") + datetime.datetime.now().strftime("|%H:%M")
        tod = banner.time_of_day()
        if text != self._banner_timer_text or tod != self._banner_tod:
            changed_tod = tod != self._banner_tod and self._banner_tod is not None
            self._banner_timer_text, self._banner_tod = text, tod
            self._banner_draw(crossfade=changed_tod)

    def _banner_menu(self, e):
        m = self.banner_menu
        m.delete(0, "end")
        m.add_command(label="Next picture", command=self._banner_next)
        m.add_command(label="Previous picture", command=lambda: self._banner_next(-1))
        pinned = bool(self.cfg.get("banner_pinned"))
        m.add_command(label="Unpin (go back to changing)" if pinned else "Pin this picture",
                      command=self._banner_pin)
        pace = tk.Menu(m, tearoff=0)
        cur = int(self.cfg.get("banner_minutes", 15) or 0)
        for label, mins in self.BANNER_PACES:
            pace.add_command(label=("● " if mins == cur else "   ") + label,
                             command=lambda mins=mins: self._banner_pace(mins))
        m.add_cascade(label="Change pictures...", menu=pace)
        m.add_command(label="Preview morning / day / evening / night", command=self._banner_preview)
        m.add_separator()
        m.add_command(label="Open the Banners folder (add your own pictures)",
                      command=lambda: open_folder(BANNERS_DIR))
        m.add_command(label="Reload pictures", command=self._banner_reload)
        m.add_command(label="Hide the picture strip", command=lambda: self._banner_toggle(False))
        m.tk_popup(e.x_root, e.y_root)

    def _banner_preview(self, k=0):
        """Show each time of day for a few seconds, then go back to the real one."""
        order = ("morning", "day", "evening", "night")
        if k < len(order):
            self._banner_tod_preview = order[k]
            self._banner_draw(crossfade=True)
            self.status.configure(text=f"picture strip: {order[k]}")
            self.root.after(3000, lambda: self._banner_preview(k + 1))
        else:
            self._banner_tod_preview = None
            self._banner_draw(crossfade=True)
            self._update_status()

    def _banner_pin(self):
        if self.cfg.get("banner_pinned"):
            self.cfg["banner_pinned"] = None
        elif self._banner_list:
            self.cfg["banner_pinned"] = self._banner_list[self._banner_i]
        save_config(self.cfg)
        self._banner_schedule()

    def _banner_pace(self, mins):
        self.cfg["banner_minutes"] = mins
        save_config(self.cfg)
        self._banner_schedule()

    def _banner_reload(self):
        self._banner_load()
        self._banner_size = None
        self._banner_place()
        if not self._banner_list:
            self._write(f"There are no pictures in {BANNERS_DIR} yet. Drop some .jpg or .png files in there, "
                        "then right-click the strip > Reload pictures.\n", "sys")

    def _banner_toggle(self, on=None):
        self.cfg["banner"] = (not self.cfg.get("banner", True)) if on is None else bool(on)
        save_config(self.cfg)
        if hasattr(self, "banner_var"):
            self.banner_var.set(self.cfg["banner"])
        self._banner_size = None
        self._banner_place()
        if not self.cfg["banner"]:
            self._write("Picture strip hidden. Turn it back on: right-click the owl > Header pictures.\n", "sys")

    # ----- the owl focus timer (Pomodoro) --------------------------------------

    FOCUS_TIPS = ("stand up and stretch your back and shoulders", "drink some water",
                  "look at something 20 feet away for 20 seconds")

    def _draw_focus_chip(self):
        """The little timer pill next to the date: 'focus', or the time left while it runs."""
        c, px = self.focus_chip, self.px
        f = self.focus
        c.delete("all")
        on = f.running or (f.left < f.total and f.left > 0)
        if f.mode == "focus":
            text = f"● {f.clock()}" if f.running else (f"❚❚ {f.clock()}" if on else "focus")
            if getattr(self, "_focus_nodot", False) and text != "focus":
                text = f.clock()
        else:
            text = f"break {f.clock()}"
        col = ACCENT if f.running else MUTED
        tw = tkfont.Font(family=MONO, size=8).measure(text)
        h = px(22)
        w = tw + px(20)
        icon_only = self._chips_compact and text == "focus"
        self._chip_w["focus"] = (w, h)
        if icon_only:
            w = h
        key = ("focuschip", w, f.running)
        if self.imgs.get("focuschip_key") != key:
            try:
                self.imgs["focuschip"] = th.rounded(w, h, h // 2, BG, ACCENT if f.running else BORDER)
                self.imgs["focuschip_key"] = key
            except Exception:
                self.imgs["focuschip"] = None
        c.configure(width=w, height=h)
        if self.imgs.get("focuschip"):
            c.create_image(0, 0, anchor="nw", image=self.imgs["focuschip"])
        if icon_only:           # a little clock
            r = px(5.5)
            c.create_oval(w / 2 - r, h / 2 - r, w / 2 + r, h / 2 + r, outline=col, width=max(1, px(1.4)))
            c.create_line(w / 2, h / 2, w / 2, h / 2 - r * 0.6, fill=col, width=max(1, px(1.4)))
            c.create_line(w / 2, h / 2, w / 2 + r * 0.45, h / 2, fill=col, width=max(1, px(1.4)))
        else:
            c.create_text(px(10), h / 2, anchor="w", text=text, fill=col, font=(MONO, 8))
        self._chip_changed("focus", w)

    def _fbtn(self, parent, text, command, primary=False):
        px = self.px
        b = tk.Label(parent, text=text, bg=ACCENT if primary else SURFACE, fg=TILE if primary else TEXT,
                     font=(MONO, 10, "bold") if primary else (MONO, 9), padx=px(14), pady=px(10),
                     cursor="hand2", highlightthickness=0 if primary else 1,
                     highlightbackground=BORDER, highlightcolor=BORDER)
        b.bind("<ButtonRelease-1>", lambda e: command())
        b.bind("<Enter>", lambda e: b.configure(bg=ACCENT_HI if primary else INPUT_BG))
        b.bind("<Leave>", lambda e: b.configure(bg=ACCENT if primary else SURFACE))
        return b

    def show_focus(self, task=None, start=False):
        """Open the owl timer (next to the chat panel)."""
        px = self.px
        self._mini_exit()
        if not self.panel_visible():
            self.show_panel()
        if task:
            self.focus.remember_task(task)
        w = getattr(self, "focus_win", None)
        if w is None or not w.winfo_exists():
            w = self._build_focus_win()
            self._focus_show_view(self._focus_view)
        W, H = px(460), px(max(720, self.PANEL_H))
        w.geometry(f"{W}x{H}+{self.panel.winfo_x() + px(10)}+{self.panel.winfo_y() + px(10)}")
        w.deiconify()
        w.lift()
        if task is not None:
            self._fw["task"].delete(0, "end")
            self._fw["task"].insert(0, self.focus.task)
        if start and self.focus.mode == "focus" and not self.focus.running:
            self._focus_toggle()
        self._focus_render()

    def _build_focus_win(self):
        px = self.px
        w = self.focus_win = tk.Toplevel(self.root)
        w.withdraw()
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        fw = self._fw = {}

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        fw["title"] = tk.Label(top, text="FOCUS", bg=BG, fg=TEXT, font=(MONO, 10, "bold"))
        fw["title"].pack(side="left")
        fw["sub"] = tk.Label(top, text="", bg=BG, fg=MUTED, font=(MONO, 8))
        fw["sub"].pack(side="left", padx=(px(10), 0))
        self._icon_btn(top, "close", self._focus_close, "Close (the timer keeps going)").pack(side="right")
        self._icon_btn(top, "shrink", self._focus_minimize, "Shrink to the owl (Esc)").pack(side="right")
        fw["dots"] = tk.Canvas(top, bg=BG, highlightthickness=0, bd=0, width=px(64), height=px(14))
        fw["dots"].pack(side="right", padx=(0, px(6)))
        for wd in (top, fw["title"], fw["sub"]):
            wd.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
            wd.bind("<B1-Motion>", lambda e: w.geometry(
                f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))
        tk.Frame(w, bg=th.LINE, height=1).pack(fill="x")

        pills = fw["pills"] = tk.Frame(w, bg=BG)
        pills.pack(fill="x", padx=px(14), pady=(px(10), 0))
        fw["pill"] = {}
        for mode, label in (("focus", "focus 25"), ("short", "short break 5"), ("long", "long break 15")):
            b = tk.Label(pills, text=label, bg=BG, fg=DIM, font=(MONO, 8), padx=px(10), pady=px(4),
                         cursor="hand2", highlightthickness=1, highlightbackground=BORDER, highlightcolor=BORDER)
            b.pack(side="left", padx=(0, px(6)))
            b.bind("<ButtonRelease-1>", lambda e, m=mode: self._focus_mode(m))
            fw["pill"][mode] = b

        fw["owl"] = tk.Canvas(w, bg=BG, highlightthickness=0, bd=0, width=px(420),
                              height=int(px(420) * 128 / 200))
        fw["owl"].pack(pady=(px(6), 0))
        fw["clock"] = tk.Label(w, text="25:00", bg=BG, fg=TEXT, font=(MONO, 40))
        fw["clock"].pack()
        fw["status"] = tk.Label(w, text="", bg=BG, fg=MUTED, font=(MONO, 8))
        fw["status"].pack(pady=(0, px(8)))

        # the bottom part changes: focus / break / done
        fw["views"] = tk.Frame(w, bg=BG)
        fw["views"].pack(fill="both", expand=True)

        # focus: what you're working on + buttons
        v = fw["v_focus"] = tk.Frame(fw["views"], bg=BG)
        card = tk.Frame(v, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=px(20))
        tk.Label(card, text="> working on", bg=SURFACE, fg=MUTED, font=(MONO, 8), anchor="w").pack(
            fill="x", padx=px(12), pady=(px(8), 0))
        fw["task"] = tk.Entry(card, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0, font=(FONT, 11),
                              highlightthickness=0)
        fw["task"].pack(fill="x", padx=px(12), pady=(px(2), px(10)))
        fw["task"].insert(0, self.focus.task)
        fw["task"].bind("<Return>", lambda e: (self._focus_toggle() if not self.focus.running else None))
        fw["task"].bind("<FocusOut>", lambda e: self.focus.remember_task(fw["task"].get()))
        fw["task"].bind("<KeyRelease>", lambda e: self._focus_last_later(), add="+")
        fw["last"] = tk.Frame(v, bg="#10130a", highlightthickness=1, highlightbackground=ACCENT)
        fw["last_head"] = tk.Label(fw["last"], text="", bg="#10130a", fg=ACCENT, font=(MONO, 8), anchor="w")
        fw["last_head"].pack(fill="x", padx=px(12), pady=(px(7), 0))
        fw["last_body"] = tk.Label(fw["last"], text="", bg="#10130a", fg=BODY, font=(FONT, 10), anchor="w",
                                   justify="left", wraplength=px(390))
        fw["last_body"].pack(fill="x", padx=px(12), pady=(px(2), px(8)))
        fw["recent"] = tk.Frame(v, bg=BG)
        row = tk.Frame(v, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(20), pady=(px(12), px(18)), before=fw["task"].master)
        fw["main"] = self._fbtn(row, "start", self._focus_toggle, primary=True)
        fw["main"].pack(side="left", fill="x", expand=True)
        self._fbtn(row, "reset", self._focus_reset).pack(side="right", padx=(px(8), 0))
        self._fbtn(row, "+5 min", lambda: (self.focus.add(300), self._focus_render())).pack(
            side="right", padx=(px(8), 0))

        # break: what to do on the break
        v = fw["v_break"] = tk.Frame(fw["views"], bg=BG)
        card = tk.Frame(v, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=px(20))
        tk.Label(card, text="> on your break", bg=SURFACE, fg=MUTED, font=(MONO, 8), anchor="w").pack(
            fill="x", padx=px(12), pady=(px(8), px(2)))
        for tip in self.FOCUS_TIPS:
            tk.Label(card, text=tip, bg=SURFACE, fg=TEXT, font=(FONT, 10), anchor="w").pack(
                fill="x", padx=px(12))
        tk.Frame(card, bg=SURFACE, height=px(8)).pack()
        row = tk.Frame(v, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(20), pady=(px(12), px(18)))
        self._fbtn(row, "skip break", self._focus_skip_break).pack(side="left")
        fw["next"] = self._fbtn(row, "start next session", self._focus_next, primary=True)
        fw["next"].pack(side="right", fill="x", expand=True, padx=(px(8), 0))

        # done: log what you did
        v = fw["v_done"] = tk.Frame(fw["views"], bg=BG)
        card = tk.Frame(v, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=px(20))
        tk.Label(card, text="> what did you get done? (goes in today's daily note)", bg=SURFACE, fg=MUTED,
                 font=(MONO, 8), anchor="w").pack(fill="x", padx=px(12), pady=(px(8), 0))
        fw["notes"] = tk.Text(card, height=2, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0,
                              font=(FONT, 11), wrap="word", highlightthickness=0)
        fw["notes"].pack(fill="x", padx=px(12), pady=(px(2), px(8)))
        card = tk.Frame(v, bg=SURFACE, highlightthickness=1, highlightbackground=ACCENT)
        card.pack(fill="x", padx=px(20), pady=(px(8), 0))
        tk.Label(card, text="> where you stopped · what's next", bg=SURFACE, fg=ACCENT,
                 font=(MONO, 8), anchor="w").pack(fill="x", padx=px(12), pady=(px(8), 0))
        fw["leftoff"] = tk.Text(card, height=2, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0,
                                font=(FONT, 11), wrap="word", highlightthickness=0)
        fw["leftoff"].pack(fill="x", padx=px(12), pady=(px(2), px(8)))
        self._tip(fw["leftoff"], "Like: stopped at panel 12. next: the fight beat, panels 13-18. It comes back the "
                                 "next time you start this, and in tomorrow's brief.")
        fw["today"] = tk.Canvas(v, bg=BG, highlightthickness=0, bd=0, height=px(40))
        fw["today"].pack(fill="x", padx=px(20), pady=(px(10), 0))
        row = tk.Frame(v, bg=BG)
        row.pack(side="bottom", fill="x", padx=px(20), pady=(px(12), px(18)), before=fw["notes"].master)
        self._fbtn(row, "skip log", lambda: self._focus_save(log=False)).pack(side="left")
        self._fbtn(row, "flashcards", lambda: self._focus_save(cards=True)).pack(side="left", padx=(px(8), 0))
        self._fbtn(row, "save + start break", self._focus_save, primary=True).pack(
            side="right", fill="x", expand=True, padx=(px(8), 0))

        w.bind("<Escape>", lambda e: self._focus_minimize())
        self._focus_view = getattr(self, "_focus_view", "focus")
        return w

    def _focus_show_view(self, name):
        self._focus_view = name
        fw = getattr(self, "_fw", None)
        if not fw:
            return
        for n in ("focus", "break", "done"):
            fw["v_" + n].pack_forget()
        fw["v_" + name].pack(fill="both", expand=True)
        if name == "done":
            fw["notes"].delete("1.0", "end")
            fw["leftoff"].delete("1.0", "end")
            fw["notes"].focus_set()
        if name == "focus":
            self._focus_last()
        self._focus_render()

    def _focus_render(self):
        """Labels and buttons (the owl itself is drawn by the tick)."""
        fw = getattr(self, "_fw", None)
        f = self.focus
        if not fw or not fw["title"].winfo_exists():
            return
        view = self._focus_view
        fw["title"].configure(text="BREAK" if (view == "focus" and f.mode != "focus")
                              else {"focus": "FOCUS", "break": "BREAK", "done": "SESSION DONE"}[view],
                              fg=ACCENT if view == "done" else TEXT)
        n = f.session_no if view in ("focus", "done") else (f.done_today - 1) % 4 + 1 if f.done_today else 1
        fw["sub"].configure(text=f"session {n} of 4" if view != "break"
                            else f"{'long' if f.mode == 'long' else 'short'} · {f.total // 60} min")
        d = fw["dots"]
        d.delete("all")
        done_in_cycle = f.done_today % 4
        if view == "done":
            done_in_cycle += 1                      # the one you just finished (saved on the next click)
        elif view == "break" and f.done_today and done_in_cycle == 0:
            done_in_cycle = 4
        for i in range(4):
            x, y, r = self.px(8) + i * self.px(15), self.px(7), self.px(4)
            pts = [x, y - r, x + r, y, x, y + r, x - r, y]
            if i < done_in_cycle:
                d.create_polygon(pts, fill=ACCENT, outline=ACCENT)
            elif i == done_in_cycle and view == "focus":
                d.create_polygon(pts, fill="", outline=ACCENT, width=1.5)
            else:
                d.create_polygon(pts, fill="", outline=BORDER, width=1.5)
        for mode, b in fw["pill"].items():
            on = f.mode == mode
            b.configure(fg=ACCENT if on else DIM, highlightbackground=ACCENT if on else BORDER,
                        highlightcolor=ACCENT if on else BORDER, bg=INPUT_BG if on else BG)
        if view == "done":
            fw["pills"].pack_forget()
        elif not fw["pills"].winfo_ismapped():
            fw["pills"].pack(fill="x", padx=self.px(14), pady=(self.px(10), 0), before=fw["owl"])
        fw["clock"].configure(text=f.clock())
        if view == "focus":
            fw["main"].configure(text="pause" if f.running else ("start" if f.left > 0 else "done"))
            if f.running:
                status = "the wings open as you work"
            elif f.left >= f.total:
                status = "press start (or Enter)"
            else:
                status = "paused"
            if f.mode != "focus":
                status = ("break time. step away from the screen" if f.running
                          else "a break. press start when you're ready")
        elif view == "break":
            status = "break time. step away from the screen" if f.running else "paused"
            fw["next"].configure(text=f"next session in {f.clock()}" if f.running else "start next session")
        else:
            status = "wings open. nice work."
            fw["clock"].configure(text=f"{max(1, round(f.total / 60))} min focused")
            self._focus_draw_today()
        fw["status"].configure(text=status)

    def _focus_draw_today(self):
        c, px, f = self._fw["today"], self.px, self.focus
        c.delete("all")
        c.update_idletasks()
        W = max(c.winfo_width(), px(400))
        c.create_text(0, px(8), anchor="w", text="> today", fill=MUTED, font=(MONO, 8))
        pending = self._focus_view == "done"           # count the session that just ended
        done = f.done_today + (1 if pending else 0)
        mins = f.minutes_today + (max(1, round(f.total / 60)) if pending else 0)
        n = max(4, done)
        label = f"{mins} min"
        lw = tkfont.Font(family=MONO, size=8).measure(label) + px(10)
        seg = (W - lw - (n - 1) * px(6)) / n
        for i in range(n):
            x0 = i * (seg + px(6))
            c.create_rectangle(x0, px(22), x0 + seg, px(32), fill=ACCENT if i < done else BORDER, width=0)
        c.create_text(W, px(27), anchor="e", text=label, fill=TEXT, font=(MONO, 8))

    # ----- actions

    def _focus_toggle(self):
        f = self.focus
        fw = getattr(self, "_fw", None)
        if fw and fw["task"].winfo_exists():
            f.remember_task(fw["task"].get().strip())
        if f.left <= 0:
            f.reset()
        was = f.running
        f.toggle()
        if f.running and not was:
            self._focus_flash = time.time()      # a pulse when it starts
        self._focus_render()
        self._draw_focus_chip()

    def _focus_reset(self):
        self.focus.reset()
        self._focus_render()
        self._draw_focus_chip()

    def _focus_mode(self, mode):
        self.focus.set_mode(mode)
        self._focus_show_view("focus")
        self._draw_focus_chip()

    def _focus_skip_break(self):
        self.focus.set_mode("focus")
        self._focus_show_view("focus")
        self._draw_focus_chip()

    def _focus_next(self):
        self.focus.set_mode("focus")
        self._focus_show_view("focus")
        self._focus_toggle()

    def _focus_save(self, log=True, cards=False):
        fw, f = self._fw, self.focus
        notes = fw["notes"].get("1.0", "end").strip()
        where = fw["leftoff"].get("1.0", "end").strip()
        entry = f.record(notes)
        if where:
            self.leftoff.remember(entry["task"] or "focus session", where, entry["minutes"])
        if log and self.cfg.get("daily_note", True) and self.vault():
            try:
                self.daily.log(focusmod.log_line(entry))
            except Exception as e:
                self._write(f"Couldn't add the session to today's daily note: {e}\n", "sys")
        if cards and (notes or entry["task"]):
            self.entry.delete("1.0", "end")
            self.entry.insert("1.0", f"make flashcards on {notes or entry['task']}")
            self._entry_changed()
            self.root.after(50, self._send)
        f.set_mode(f.next_break())
        f.start()
        self._focus_show_view("break")
        self._draw_focus_chip()

    def _focus_last_later(self):
        fw = self._fw
        if fw.get("_last_job"):
            try:
                self.root.after_cancel(fw["_last_job"])
            except tk.TclError:
                pass
        fw["_last_job"] = self.root.after(350, self._focus_last)

    def _focus_last(self):
        """Under 'working on': where you left off last time on this, and your recent projects."""
        fw = getattr(self, "_fw", None)
        if not fw or "last" not in fw:
            return
        px = self.px
        task = fw["task"].get().strip()
        lo = self.leftoff.get(task)
        if lo and not self.focus.running:
            stopped, nxt = mem.split_note(lo["note"])
            fw["last_head"].configure(text=f"last time · {mem.when_label(lo['date'])}"
                                           + (f", {mem.fmt_minutes(lo['minutes'])}" if lo.get("minutes") else ""))
            fw["last_body"].configure(text=(f"stopped: {stopped}" if stopped else "")
                                           + (("\n" if stopped else "") + f"next: {nxt}" if nxt else ""))
            fw["last"].pack(fill="x", padx=px(20), pady=(px(10), 0), after=fw["task"].master)
        else:
            fw["last"].pack_forget()
        for c in fw["recent"].winfo_children():
            c.destroy()
        recent = [t for t in mem.recent_tasks(mem.focus_log(self.focus.log_path), 5)
                  if mem._key(t) != mem._key(task)][:3]
        if recent and not self.focus.running:
            tk.Label(fw["recent"], text="recent:", bg=BG, fg=MUTED, font=(MONO, 8)).pack(side="left", padx=(0, px(6)))
            for t in recent:
                short = t if len(t) <= 22 else t[:21] + "…"
                b = tk.Label(fw["recent"], text=short, bg=BG, fg=DIM, font=(MONO, 8), padx=px(6), pady=px(2),
                             cursor="hand2", highlightthickness=1, highlightbackground=BORDER)
                b.pack(side="left", padx=(0, px(4)))
                b.bind("<ButtonRelease-1>", lambda e, t=t: (fw["task"].delete(0, "end"), fw["task"].insert(0, t),
                                                            self.focus.remember_task(t), self._focus_last()))
            fw["recent"].pack(fill="x", padx=px(20), pady=(px(8), 0),
                              after=fw["last"] if fw["last"].winfo_manager() else fw["task"].master)
        else:
            fw["recent"].pack_forget()

    def _focus_close(self):
        if getattr(self, "focus_win", None) and self.focus_win.winfo_exists():
            self.focus_win.withdraw()

    def _focus_minimize(self):
        """The corner button: hide the timer and the chat, the owl bubble keeps counting."""
        self._focus_close()
        self.hide_panel()
        self._mini_enter()

    # ----- the owl bubble while the timer runs in the background

    def _mini_size(self):
        return self.px(150), int(self.px(150) * 128 / 200) + self.px(30)

    def _mini_enter(self):
        if getattr(self, "_mini", False):
            return
        size = self.px(self.BUBBLE)
        MW, MH = self._mini_size()
        x = self.root.winfo_x() + size - MW          # keep the bottom-right corner where it was
        y = self.root.winfo_y() + size - MH
        self._mini = True
        self.canvas.configure(width=MW, height=MH)
        self.canvas.delete("all")
        self.root.geometry(f"{MW}x{MH}+{max(0, x)}+{max(0, y)}")
        self._mini_draw()

    def _mini_exit(self):
        if not getattr(self, "_mini", False):
            return
        size = self.px(self.BUBBLE)
        MW, MH = self._mini_size()
        x = self.root.winfo_x() + MW - size
        y = self.root.winfo_y() + MH - size
        self._mini = False
        self.canvas.configure(width=size, height=size)
        self.canvas.delete("all")
        self._draw_owl()
        self.root.geometry(f"{size}x{size}+{x}+{y}")

    def _bubble_home(self):
        """Where the normal owl bubble sits (even while it's the wide timer owl)."""
        x, y = self.root.winfo_x(), self.root.winfo_y()
        if getattr(self, "_mini", False):
            size = self.px(self.BUBBLE)
            MW, MH = self._mini_size()
            x, y = x + MW - size, y + MH - size
        return x, y

    def _mini_draw(self):
        from PIL import Image as _I, ImageDraw as _D, ImageFont as _F
        f = self.focus
        MW, MH = self._mini_size()
        owl = self._focus_owl_image(MW, ss=2)
        img = _I.new("RGBA", (MW, MH), (0, 0, 0, 0))
        img.alpha_composite(owl, (0, 0))
        d = _D.Draw(img)
        text = f.clock() if f.mode == "focus" else "break " + f.clock()
        try:
            font = _F.truetype(os.path.join(FONTS_DIR, "JetBrainsMono-Bold.ttf"), self.px(13))
        except Exception:
            font = _F.load_default()
        tw = d.textlength(text, font=font)
        pw, ph = tw + self.px(18), self.px(22)
        x0, y0 = (MW - pw) / 2, MH - ph - self.px(2)
        d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph / 2, fill=th._rgb(BG) + (255,),
                            outline=th._rgb(ACCENT if f.running else BORDER) + (255,), width=max(1, self.px(1)))
        d.text((MW / 2, y0 + ph / 2), text, font=font, anchor="mm",
               fill=th._rgb(TEXT if f.running else MUTED) + (255,))
        self.imgs["mini"] = th.keyed_photo(img, self.canvas.cget("bg"))
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self.imgs["mini"], tags=("owl",))

    # ----- drawing the owl and the tick

    def _focus_owl_image(self, width, ss=3):
        f, now = self.focus, time.time()
        view = getattr(self, "_focus_view", "focus")
        breath = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(now / 4.0 * 2 * math.pi))
        flash = getattr(self, "_focus_flash", 0)
        pulse = (now - flash) / 0.9 if now - flash < 0.9 else None
        blink = (now % 6.0) < 0.17
        if view == "done":
            return th.owl_flight_rgba(width, 1.0, breath=breath, eyes="closed" if blink else "open", ss=ss)
        if not f.running:                   # not running (any timer): the owl sleeps
            return th.owl_flight_rgba(width, f.progress, breath=breath, zzz=True, eyes="closed",
                                      ghost=True, ss=ss)
        return th.owl_flight_rgba(width, f.progress, breath=breath, pulse_t=pulse, ss=ss,
                                  eyes="closed" if blink else "open", ghost=True)

    def _focus_tick(self):
        f = self.focus
        try:
            if f.running:
                m = int(f.left // 60)
                if getattr(self, "_focus_min", None) not in (None, m):
                    self._focus_flash = time.time()       # the once-a-minute pulse
                self._focus_min = m
            if f.finished():
                self._focus_done()
            w = getattr(self, "focus_win", None)
            if w is not None and w.winfo_exists() and w.winfo_viewable():
                fw = self._fw
                img = self._focus_owl_image(self.px(420), ss=2)
                self.imgs["focus_owl"] = ImageTk.PhotoImage(img) if ImageTk else None
                fw["owl"].delete("all")
                if self.imgs["focus_owl"]:
                    fw["owl"].create_image(0, 0, anchor="nw", image=self.imgs["focus_owl"])
                clock = f.clock()
                if self._focus_view != "done" and fw["clock"].cget("text") != clock:
                    self._focus_render()
            if getattr(self, "_mini", False):
                self._mini_draw()
            if getattr(self, "banner", None) is not None:
                self._banner_tick()
            if f.running or getattr(self, "_chip_running", None) != f.running:
                self._chip_running = f.running
                self._draw_focus_chip()
        except Exception:
            import traceback
            err = traceback.format_exc()
            if err != getattr(self, "_focus_last_err", None):      # write each problem once
                self._focus_last_err = err
                try:
                    with open(os.path.join(APP_DIR, "archie_error.log"), "a", encoding="utf-8") as fh:
                        fh.write(f"\n--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} focus timer ---\n{err}")
                except OSError:
                    pass
        self.root.after(125, self._focus_tick)

    def _focus_done(self):
        """Time's up: pop the timer up on screen, with a sound."""
        f = self.focus
        if f.mode == "focus":
            self._focus_view = "done"
        else:
            f.set_mode("focus")
            self._focus_view = "focus"
        self.show_focus()
        self._focus_show_view(self._focus_view)
        if self._focus_view == "focus":
            self._fw["status"].configure(text="break's over. ready when you are")
        try:
            self.focus_win.attributes("-topmost", True)
            self.focus_win.lift()
            self.focus_win.focus_force()
        except tk.TclError:
            pass
        if self.quiet is None or self.quiet.sound_ok("timer"):
            try:
                import winsound
                winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                try:
                    self.root.bell()
                except Exception:
                    pass
        self._draw_focus_chip()

    def show_calendar(self, select=None):
        px = self.px
        if not self.panel_visible():
            self.show_panel()
        if getattr(self, "cal_win", None) and self.cal_win.winfo_exists():
            self.cal_win.destroy()
        w = self.cal_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = px(460), px(max(720, self.PANEL_H))
        WW = px(980)                                   # the week view is wider
        today = datetime.date.today()
        st = {"sel": select or today, "month": (select or today).replace(day=1), "kind": "exam",
              "view": self.cfg.get("calendar_view", "month")}
        x0_, y0_ = self.panel.winfo_x() + px(10), self.panel.winfo_y() + px(10)
        sw_ = w.winfo_screenwidth()

        def place():
            ww = WW if st["view"] == "week" else W
            w.geometry(f"{ww}x{H}+{max(0, min(x0_, sw_ - ww - px(10)))}+{y0_}")
            w.after(60, lambda: th.round_corners(w, px(12)))
        place()
        facts = self._cal_facts()

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        tk.Label(top, text="CALENDAR", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        self._icon_btn(top, "close", w.destroy, "Close (Esc)").pack(side="right")
        view_btns = {}
        for v_ in ("week", "month"):
            b = tk.Label(top, text=v_, bg=BG, font=(MONO, 8), padx=px(8), pady=px(2), cursor="hand2",
                         highlightthickness=1)
            b.pack(side="right", padx=(0, px(6)))
            b.bind("<ButtonRelease-1>", lambda e, v_=v_: set_view(v_))
            view_btns[v_] = b

        def paint_views():
            for v_, b in view_btns.items():
                on = st["view"] == v_
                b.configure(fg=ACCENT if on else DIM, bg=INPUT_BG if on else BG,
                            highlightbackground=ACCENT if on else BORDER, highlightcolor=ACCENT if on else BORDER)
        paint_views()
        top.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
        top.bind("<B1-Motion>", lambda e: w.geometry(
            f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))

        nav = tk.Frame(w, bg=BG)
        nav.pack(fill="x", padx=px(14), pady=(px(4), px(6)))

        def navbtn(text, cmd):
            b = tk.Label(nav, text=text, bg=BG, fg=DIM, font=(MONO, 12), padx=px(8), cursor="hand2")
            b.bind("<ButtonRelease-1>", lambda e: cmd())
            b.bind("<Enter>", lambda e: b.configure(fg=TEXT))
            b.bind("<Leave>", lambda e: b.configure(fg=DIM))
            return b
        navbtn("‹", lambda: move(-1)).pack(side="left")
        month_l = tk.Label(nav, text="", bg=BG, fg=TEXT, font=(FONT_SEMI, 13))
        month_l.pack(side="left", padx=px(6))
        navbtn("›", lambda: move(1)).pack(side="left")
        tl = tk.Label(nav, text="today", bg=BG, fg=ACCENT, font=(MONO, 8), cursor="hand2")
        tl.pack(side="right")
        tl.bind("<ButtonRelease-1>", lambda e: pick(today))

        month_box = tk.Frame(w, bg=BG)
        grid = tk.Canvas(month_box, bg=BG, highlightthickness=0, bd=0, height=px(300))
        grid.pack(fill="x", padx=px(14))
        legend = tk.Frame(month_box, bg=BG)
        legend.pack(fill="x", padx=px(16), pady=(px(4), 0))
        for k_, col_ in (("class", cal.KINDS["class"][1]), ("recorded", cal.RECORDING), ("due", cal.KINDS["due"][1]),
                         ("exam", cal.KINDS["exam"][1]), ("quiz/test", cal.KINDS["quiz"][1]), ("lab", cal.KINDS["lab"][1])):
            tk.Label(legend, text="▬", bg=BG, fg=col_, font=(MONO, 7)).pack(side="left")
            tk.Label(legend, text=k_, bg=BG, fg=MUTED, font=(MONO, 7)).pack(side="left", padx=(px(2), px(8)))
        tk.Label(legend, text="glow = focus", bg=BG, fg=ACCENT, font=(MONO, 7)).pack(side="right")

        day_l = tk.Label(month_box, text="", bg=BG, fg=TEXT, font=(MONO, 9, "bold"), anchor="w")
        day_l.pack(fill="x", padx=px(14), pady=(px(10), px(4)))
        lst = tk.Frame(month_box, bg=BG)
        lst.pack(fill="x", padx=px(14))
        week_box = tk.Frame(w, bg=BG)
        wk = tk.Canvas(week_box, bg=BG, highlightthickness=0, bd=0)
        wk.pack(fill="both", expand=True, padx=px(14))

        # add form
        form = tk.Frame(w, bg=BG)
        form.pack(side="bottom", fill="x", padx=px(14), pady=(px(6), px(12)))
        form_anchor = form
        kinds = tk.Frame(w, bg=BG)
        kinds.pack(side="bottom", fill="x", padx=px(14))
        tk.Frame(w, bg=th.LINE, height=1).pack(side="bottom", fill="x", pady=(px(8), px(8)))
        kind_btns = {}

        def draw_kinds():
            for k, b in kind_btns.items():
                on = st["kind"] == k
                col = cal.KINDS[k][1]
                b.configure(fg=col if on else DIM, highlightbackground=col if on else BORDER,
                            highlightcolor=col if on else BORDER)
        for k, (label, col) in cal.KINDS.items():
            b = tk.Label(kinds, text=label.lower(), bg=BG, font=(MONO, 8), padx=px(6), pady=px(1),
                         cursor="hand2", highlightthickness=1)
            b.pack(side="left", padx=(0, px(4)))
            b.bind("<ButtonRelease-1>", lambda e, k=k: (st.update(kind=k), draw_kinds()))
            kind_btns[k] = b
        draw_kinds()
        tk.Label(form, text="+", bg=BG, fg=ACCENT, font=(MONO, 12)).pack(side="left")
        what = tk.Entry(form, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0, font=(FONT, 10),
                        highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        what.pack(side="left", fill="x", expand=True, ipady=px(4), padx=(px(4), px(6)))
        weekly = tk.BooleanVar(value=False)
        tk.Checkbutton(form, text="weekly", variable=weekly, bg=BG, fg=MUTED, selectcolor=SURFACE,
                       activebackground=BG, activeforeground=TEXT, font=(MONO, 8), bd=0,
                       highlightthickness=0).pack(side="left", padx=(0, px(6)))
        addb = tk.Label(form, text="add", bg=ACCENT, fg=TILE, font=(MONO, 9, "bold"), padx=px(10),
                        pady=px(3), cursor="hand2")
        addb.pack(side="left")
        hint = tk.Label(w, text="", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w")
        hint.pack(side="bottom", fill="x", padx=px(14))

        def stop_edit(_e=None):
            if st.get("edit"):
                st["edit"] = None
                what.delete(0, "end")
                weekly.set(False)
                addb.configure(text="add")
                draw()

        def start_edit(e):
            """Click an event: its words go in the box; change them, pick another day to move it, then save."""
            st["edit"] = e
            st["sel"] = datetime.date.fromisoformat(e["date"]) if not e.get("repeat") else st["sel"]
            st["month"] = st["sel"].replace(day=1)
            st["kind"] = e["kind"] if e["kind"] in cal.KINDS else "event"
            draw_kinds()
            what.delete(0, "end")
            what.insert(0, e["title"] + (f" {cal.fmt_time(e['time'])}" if e.get("time") else ""))
            weekly.set(bool(e.get("repeat")))
            addb.configure(text="save")
            draw()
            what.focus_set()
            what.icursor("end")
        what.bind("<Escape>", stop_edit)

        def add():
            txt = what.get().strip()
            if not txt:
                return
            t, span = cal.find_time(txt)
            title = (txt[:span[0]] + txt[span[1]:]).strip(" ,.-") if span else txt
            if st.get("edit"):
                old = st["edit"]
                e = self.calendar.update(old["id"], title=title or old["title"], kind=st["kind"], time=t,
                                         date=old["date"] if old.get("repeat") and weekly.get() else st["sel"],
                                         repeat="weekly" if weekly.get() else None)
                st["edit"] = None
                what.delete(0, "end")
                weekly.set(False)
                addb.configure(text="add")
                draw()
                if e:
                    hint.configure(text=f"saved {cal.describe(e)}", fg=ACCENT)
                self._draw_date_chip()
                self._sync_daily(quiet=True)
                return
            e = self.calendar.add(title or cal.KINDS[st["kind"]][0], st["sel"], st["kind"], t,
                                  repeat="weekly" if weekly.get() else None)
            what.delete(0, "end")
            weekly.set(False)
            hint.configure(text=f"added {cal.describe(e)}", fg=ACCENT)
            draw()
            self._draw_date_chip()
            self._sync_daily(quiet=True)
        addb.bind("<ButtonRelease-1>", lambda e: add())
        what.bind("<Return>", lambda e: add())

        def move(n):
            if st["view"] == "week":
                st["sel"] = st["sel"] + datetime.timedelta(days=7 * n)
                st["month"] = st["sel"].replace(day=1)
                draw()
                return
            m = st["month"].month - 1 + n
            st["month"] = datetime.date(st["month"].year + m // 12, m % 12 + 1, 1)
            draw()

        def set_view(v_):
            st["view"] = v_
            self.cfg["calendar_view"] = v_
            save_config(self.cfg)
            paint_views()
            place()
            draw()

        def pick(d):
            st["sel"] = d
            st["month"] = d.replace(day=1)
            draw()

        def cells():
            first = st["month"]
            start = first - datetime.timedelta(days=(first.weekday() + 1) % 7)   # weeks start Sunday
            return [start + datetime.timedelta(days=i) for i in range(42)]

        def draw():
            if st["view"] == "week":
                month_box.pack_forget()
                week_box.pack(fill="both", expand=True, before=form_anchor)
                w.after(30, draw_week)
                return
            week_box.pack_forget()
            month_box.pack(fill="x", before=form_anchor)
            grid.update_idletasks()
            gw = grid.winfo_width() or (W - px(28))
            cw, top_h = gw / 7.0, px(22)
            ch = (int(grid.cget("height")) - top_h) / 6.0
            grid.delete("all")
            month_l.configure(text=st["month"].strftime("%B %Y"))
            for i, d in enumerate(["sun", "mon", "tue", "wed", "thu", "fri", "sat"]):
                grid.create_text(cw * i + cw / 2, top_h / 2, text=d, fill=MUTED, font=(MONO, 8))
            days = cells()
            evs = self.calendar.between(days[0], days[-1])
            by = {}
            for e in evs:
                by.setdefault(e["date"], []).append(e)
            grid._cells = []
            for i, d in enumerate(days):
                x0, y0 = cw * (i % 7), top_h + ch * (i // 7)
                inside = d.month == st["month"].month
                mins = facts["focus_min"].get(d, 0)
                if mins and inside:
                    glow = _mix(BG, ACCENT, 0.04 + 0.24 * min(1.0, mins / 180))
                    grid.create_rectangle(x0 + 2, y0 + 2, x0 + cw - 2, y0 + ch - 2, fill=glow, width=0)
                if d == st["sel"]:
                    grid.create_rectangle(x0 + 2, y0 + 2, x0 + cw - 2, y0 + ch - 2, fill="" if mins else INPUT_BG,
                                          outline=TEXT if mins else BORDER)
                if d == today:
                    r = px(11)
                    cx, cy = x0 + cw / 2, y0 + px(14)
                    grid.create_oval(cx - r, cy - r, cx + r, cy + r, outline=ACCENT, width=px(1.5))
                grid.create_text(x0 + cw / 2, y0 + px(14), text=str(d.day),
                                 fill=(ACCENT if d == today else TEXT) if inside else "#4a4a4a",
                                 font=(MONO, 9, "bold" if d == today else "normal"))
                cols_ = []
                for e in by.get(d.isoformat(), []):
                    c_ = cal.KINDS.get(e["kind"], cal.KINDS["event"])[1]
                    if c_ not in cols_:
                        cols_.append(c_)
                if facts["lectures"].get(d):
                    cols_.insert(1 if cols_ else 0, cal.RECORDING)
                for j, c_ in enumerate(cols_[:4]):
                    by_ = y0 + ch - px(8) - j * px(5)
                    grid.create_rectangle(x0 + px(8), by_, x0 + cw - px(8), by_ + px(3), fill=c_, width=0)
                grid._cells.append((x0, y0, x0 + cw, y0 + ch, d))
            # the chosen day's list
            for c in lst.winfo_children():
                c.destroy()
            sel = st["sel"]
            n = (sel - today).days
            rel = "today" if n == 0 else "tomorrow" if n == 1 else "yesterday" if n == -1 else \
                (f"in {n} days" if n > 0 else f"{-n} days ago")
            day_l.configure(text=f"{sel.strftime('%A, %B %d').replace(' 0', ' ')}  ·  {rel}")
            items = self.calendar.on(sel)
            extra = []
            for klass, title_, path_ in facts["lectures"].get(sel, []):
                extra.append((cal.RECORDING, "recorded", f"{klass}: {title_}" if klass else title_, path_))
            for e_ in facts["focus"].get(sel, []):
                extra.append((cal.FOCUS, e_.get("start", ""), f"focus {e_.get('minutes', 0)} min · {e_.get('task') or 'untitled'}", None))
            for g_ in facts["gym"].get(sel, []):
                extra.append((cal.GYM, g_.get("at", ""), f"drawing gym · {g_.get('poses', 0)} pictures", None))
            if not items and not extra:
                tk.Label(lst, text="nothing yet. Add something below.", bg=BG, fg=MUTED,
                         font=(MONO, 8), anchor="w").pack(fill="x")
            room = max(2, 6 - min(len(items), 4))
            if len(extra) > room:
                more_ = len(extra) - room + 1
                extra = extra[:room - 1] + [(MUTED, "", f"+{more_} more · see the week view", None)]
            for col_, when_, text_, path_ in extra:
                row = tk.Frame(lst, bg=BG)
                row.pack(fill="x", pady=px(2))
                tk.Frame(row, bg=col_, width=px(3)).pack(side="left", fill="y")
                tk.Label(row, text=when_, bg=BG, fg=MUTED, font=(MONO, 8), width=8, anchor="w").pack(side="left", padx=(px(8), 0))
                lab_ = tk.Label(row, text=text_, bg=BG, fg=BODY, font=(FONT, 10), anchor="w",
                                cursor="hand2" if path_ else "")
                lab_.pack(side="left", fill="x", expand=True)
                if path_:
                    lab_.bind("<ButtonRelease-1>", lambda e, p_=path_: self._open_note_path(p_))
            for e in items[:4]:
                row = tk.Frame(lst, bg=BG)
                row.pack(fill="x", pady=px(2))
                tk.Frame(row, bg=cal.KINDS.get(e["kind"], cal.KINDS["event"])[1], width=px(3)).pack(side="left", fill="y")
                tk.Label(row, text=cal.fmt_time(e.get("time")) or "all day", bg=BG, fg=MUTED, font=(MONO, 8),
                         width=8, anchor="w").pack(side="left", padx=(px(8), 0))
                x = tk.Label(row, text="✕", bg=BG, fg=MUTED, font=(MONO, 10), cursor="hand2", padx=px(4))
                x.pack(side="right")                                      # always visible, however long the title is
                x.bind("<ButtonRelease-1>", lambda ev, e=e: remove(e))
                x.bind("<Enter>", lambda ev, w=x: w.configure(fg="#ff5f57"))
                x.bind("<Leave>", lambda ev, w=x: w.configure(fg=MUTED))
                tk.Label(row, text=cal.KINDS.get(e["kind"], cal.KINDS["event"])[0].lower(), bg=BG,
                         fg=cal.KINDS.get(e["kind"], cal.KINDS["event"])[1], font=(MONO, 8)).pack(side="right", padx=px(6))
                title_ = e["title"] + ("  ↻" if e.get("repeat") else "")
                tl_ = tk.Label(row, text=title_ if len(title_) <= 44 else title_[:42].rstrip() + "…", bg=BG,
                               fg=ACCENT if (st.get("edit") or {}).get("id") == e["id"] else TEXT,
                               font=(FONT, 10), anchor="w", cursor="hand2")
                tl_.pack(side="left", fill="x", expand=True)
                tl_.bind("<ButtonRelease-1>", lambda ev, e=e: start_edit(e))
            if st.get("edit"):
                hint.configure(text=f"editing \"{st['edit']['title']}\" · change it, click another day to move it, "
                                    f"then save ({sel.strftime('%a %b %d').replace(' 0', ' ')}) · Esc cancels", fg=ACCENT)
            else:
                hint.configure(text=f"adding to {sel.strftime('%a %b %d').replace(' 0', ' ')} · e.g. "
                                    "bio midterm 9am · click an event to change it", fg=MUTED)

        def remove(e):
            if e.get("repeat"):
                hint.configure(text="removed the weekly event (all weeks)", fg=MUTED)
            self.calendar.delete(e["id"])
            draw()
            self._draw_date_chip()
            self._sync_daily(quiet=True)

        def draw_week():
            wk.update_idletasks()
            Wc, Hc = wk.winfo_width(), wk.winfo_height()
            if Wc < 100 or Hc < 100:
                return
            wk.delete("all")
            sel = st["sel"]
            ws = sel - datetime.timedelta(days=sel.weekday())            # Monday
            days = [ws + datetime.timedelta(days=i) for i in range(7)]
            month_l.configure(text="week of " + ws.strftime("%b %d, %Y").replace(" 0", " "))
            H0, H1 = 8, 23
            gut, head = px(36), px(40)
            leg_h = px(20)
            cw = (Wc - gut) / 7.0
            rh = (Hc - head - leg_h) / (H1 - H0)
            heat = facts["heat"]
            hmax = max([max(r[H0:H1]) for r in heat] + [1])
            evs = self.calendar.between(days[0], days[-1])
            wk._cols = []
            now = datetime.datetime.now()

            def y(t):
                return head + (t - H0) * rh
            for h in range(H0, H1):
                wk.create_text(gut - px(6), y(h), text=f"{(h - 1) % 12 + 1}{'a' if h < 12 else 'p'}",
                               fill="#6a6a66", font=(MONO, 7), anchor="e")
            for i, d in enumerate(days):
                x0, x1 = gut + i * cw, gut + (i + 1) * cw
                wk._cols.append((x0, x1, d))
                if d == today:
                    wk.create_rectangle(x0, head, x1, y(H1), fill="#0f0f0f", width=0)
                for h in range(H0, H1):                     # your best hours glow (from patterns)
                    v = heat[d.weekday()][h] / hmax
                    if v > 0.15:
                        wk.create_rectangle(x0 + 1, y(h), x1 - 1, y(h + 1), width=0,
                                            fill=_mix("#0f0f0f" if d == today else BG, ACCENT, 0.05 + 0.22 * v))
                    wk.create_line(x0, y(h), x1, y(h), fill="#161616")
                wk.create_line(x0, head, x0, y(H1), fill="#1f1f1f")
                wk.create_text(x0 + px(4), px(10), text=d.strftime("%a %d").lower(), anchor="w",
                               fill=TEXT if d == today else (ACCENT if d == sel else DIM),
                               font=(MONO, 8, "bold" if d == today else "normal"))
                tags = [e for e in evs if e["date"] == d.isoformat() and (not e.get("time") or e["kind"] == "due")]
                for j, e in enumerate(tags[:2]):
                    col = cal.KINDS.get(e["kind"], cal.KINDS["event"])[1]
                    ty = px(20) + j * px(11)
                    wk.create_rectangle(x0 + px(3), ty, x1 - px(3), ty + px(10), fill=col, width=0)
                    wk.create_text(x0 + px(6), ty + px(5), text=e["title"][:int(cw / px(6))], anchor="w",
                                   fill="#0a0a0a", font=(MONO, 7))

            items = []          # (day index, t0, t1, args, kwargs): drawn after overlaps are worked out

            def block(i, t0, t1, *a, **k):
                items.append([i, t0, t1, a, k, 0, 1])

            def draw_block(i, t0, t1, fill, outline, text, sub="", fg=TEXT, edge=None, dash=None, lane=0, lanes=1):
                bw_ = (cw - px(6)) / lanes
                x0 = gut + i * cw + px(3) + lane * bw_
                x1 = x0 + bw_ - (px(2) if lanes > 1 else 0)
                y0, y1 = y(max(H0, t0)), max(y(max(H0, t0)) + px(14), y(min(H1, t1)) - 1)
                wk.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=1, dash=dash)
                if edge:
                    wk.create_rectangle(x0, y0, x0 + px(3), y1, fill=edge[0], width=0)
                    if len(edge) > 1:
                        wk.create_rectangle(x1 - px(3), y0, x1, y1, fill=edge[1], width=0)
                chars = max(3, int((x1 - x0 - px(8)) / px(5.6)))
                wk.create_text(x0 + px(6), y0 + px(3), text=text[:chars], anchor="nw", fill=fg,
                               font=(FONT, 8, "bold"))
                if sub and y1 - y0 > px(26):
                    wk.create_text(x0 + px(6), y0 + px(15), text=sub[:chars], anchor="nw", fill=fg, font=(MONO, 7))
            for e in evs:
                if not e.get("time") or e["kind"] == "due":
                    continue
                d = datetime.date.fromisoformat(e["date"])
                i = (d - ws).days
                h_, m_ = map(int, e["time"].split(":"))
                t0 = h_ + m_ / 60
                dur = int(self.cfg.get("lecture_minutes") or 75) if e["kind"] == "class" else cal.DURATION.get(e["kind"], 60)
                t1 = t0 + max(20, dur) / 60
                col = cal.KINDS.get(e["kind"], cal.KINDS["event"])[1]
                fill = _mix(BG, col, 0.2)
                if e["kind"] == "class":
                    done = [x for x in facts["lectures"].get(d, []) if not x[0] or x[0].lower() == e["title"].lower()]
                    end_ = datetime.datetime.combine(d, datetime.time(h_, m_)) + datetime.timedelta(minutes=dur)
                    if done:
                        block(i, t0, t1, fill, "", e["title"], "■ recorded · ✓ note", edge=(col, cal.RECORDING))
                    elif end_ > now:
                        block(i, t0, t1, fill, "", e["title"], "record it", edge=(col,))
                    else:
                        block(i, t0, t1, fill, "", e["title"], "no recording", edge=(col,), fg=DIM)
                else:
                    block(i, t0, t1, fill, "", e["title"], cal.KINDS[e["kind"]][0].lower(), edge=(col,))
            for d in days:                                  # focus sessions you did
                i = (d - ws).days
                for e in facts["focus"].get(d, []):
                    try:
                        h_, m_ = map(int, e.get("start", "12:00").split(":"))
                    except ValueError:
                        continue
                    t0 = h_ + m_ / 60
                    block(i, t0, t0 + int(e.get("minutes", 25)) / 60, cal.FOCUS, "", e.get("task") or "focus",
                          f"{e.get('minutes', 25)} min", fg="#0a0a0a")
                for g in facts["gym"].get(d, []):            # drawing gym
                    try:
                        h_, m_ = map(int, g.get("at", "18:00").split(":"))
                    except ValueError:
                        continue
                    x0 = gut + i * cw + px(4)
                    yy = y(h_ + m_ / 60)
                    wk.create_rectangle(x0, yy, x0 + px(56), yy + px(12), fill=cal.GYM, width=0)
                    wk.create_text(x0 + px(4), yy + px(6), text=f"gym {max(1, g.get('seconds', 0) // 60)}m",
                                   anchor="w", fill="#0a0a0a", font=(MONO, 7))
                dues = [e for e in evs if e["date"] == d.isoformat() and e["kind"] == "due"]
                if dues:
                    t_ = dues[0].get("time") or "23:59"
                    h_, m_ = map(int, t_.split(":"))
                    yy = y(min(H1 - 0.02, h_ + m_ / 60))
                    x0, x1 = gut + i * cw, gut + (i + 1) * cw
                    wk.create_line(x0, yy, x1, yy, fill=cal.KINDS["due"][1], width=2)
                    wk.create_text(x1 - px(4), yy - px(6), text="due " + cal.fmt_time(t_), anchor="e",
                                   fill=cal.KINDS["due"][1], font=(MONO, 7))
            for i in range(7):                              # side by side where they overlap
                day_items = sorted([it for it in items if it[0] == i], key=lambda it: it[1])
                lanes_end = []
                for it in day_items:
                    lane = next((n for n, end in enumerate(lanes_end) if end <= it[1] + 1e-6), len(lanes_end))
                    if lane == len(lanes_end):
                        lanes_end.append(it[2])
                    else:
                        lanes_end[lane] = it[2]
                    it[5] = lane
                for it in day_items:
                    over = [o for o in day_items if o[1] < it[2] and it[1] < o[2]]
                    it[6] = max(o[5] for o in over) + 1
                for it in day_items:
                    draw_block(it[0], it[1], it[2], *it[3], lane=it[5], lanes=it[6], **it[4])
            if ws <= today <= days[-1]:
                i = (today - ws).days
                t = now.hour + now.minute / 60
                if H0 <= t <= H1:
                    wk.create_line(gut + i * cw, y(t), gut + (i + 1) * cw, y(t), fill="#ffffff", width=2)
            ly = Hc - px(8)
            lx = gut
            for label, col in (("lecture", cal.KINDS["class"][1]), ("recorded", cal.RECORDING),
                               ("due", cal.KINDS["due"][1]), ("exam", cal.KINDS["exam"][1]),
                               ("quiz/test", cal.KINDS["quiz"][1]), ("lab", cal.KINDS["lab"][1]),
                               ("focus", cal.FOCUS), ("gym", cal.GYM), ("other", cal.KINDS["event"][1])):
                wk.create_rectangle(lx, ly - px(4), lx + px(10), ly + px(2), fill=col, width=0)
                t_id = wk.create_text(lx + px(14), ly - px(1), text=label, anchor="w", fill=MUTED, font=(MONO, 7))
                bb = wk.bbox(t_id)
                lx = (bb[2] if bb else lx + px(60)) + px(14)
            t_id = wk.create_text(Wc - px(4), ly - px(1), text="glow = your best hours (patterns)", anchor="e",
                                  fill=ACCENT, font=(MONO, 7))
            hint.configure(text=f"adding to {sel.strftime('%a %b %d').replace(' 0', ' ')} (click a day) · e.g. "
                                "bio midterm 9am", fg=MUTED)

        def wk_click(ev):
            for x0, x1, d in getattr(wk, "_cols", []):
                if x0 <= ev.x < x1:
                    st["sel"] = d
                    draw_week()
                    what.focus_set()
                    return
        wk.bind("<Button-1>", wk_click)
        wk.bind("<Configure>", lambda e: draw_week() if st["view"] == "week" else None)

        def click(ev):
            for x0, y0, x1, y1, d in getattr(grid, "_cells", []):
                if x0 <= ev.x < x1 and y0 <= ev.y < y1:
                    pick(d)
                    what.focus_set()
                    return
        grid.bind("<Button-1>", click)
        grid.bind("<Configure>", lambda e: draw())
        w.bind("<Escape>", lambda e: w.destroy())
        w.bind("<MouseWheel>", lambda e: move(-1 if e.delta > 0 else 1))
        draw()
        what.focus_set()

    def _cal_facts(self):
        """What the calendar shows besides events: focus sessions, drawing gym, lecture notes, and the
        focus heat from your patterns."""
        focus, focus_min, gym_ = {}, {}, {}
        for e in mem.focus_log(self.focus.log_path):
            try:
                d = datetime.date.fromisoformat(e["date"])
            except (KeyError, ValueError):
                continue
            focus.setdefault(d, []).append(e)
            focus_min[d] = focus_min.get(d, 0) + int(e.get("minutes", 0))
        for g in mem.gym_log(self.gym.log_path):
            try:
                d = datetime.date.fromisoformat(g.get("date", ""))
            except ValueError:
                continue
            gym_.setdefault(d, []).append(g)
            focus_min[d] = focus_min.get(d, 0) + int(g.get("seconds", 0)) // 60
        lectures = {}
        vault = self.vault()
        base = vault if vault and os.path.isdir(vault) else NOTES_DIR
        for path in glob.glob(os.path.join(base, "Lectures", "*", "*.md")):
            name = os.path.basename(path)
            if name.endswith("(mind map).md"):
                continue
            try:
                d = datetime.date.fromisoformat(name[:10])
            except ValueError:
                continue
            klass = os.path.basename(os.path.dirname(path))
            lectures.setdefault(d, []).append(("" if klass == "Other" else klass, name[11:-3], path))
        try:
            heat = self._patterns()["heat"]
        except Exception:
            heat = [[0] * 24 for _ in range(7)]
        return {"focus": focus, "focus_min": focus_min, "gym": gym_, "lectures": lectures, "heat": heat}

    def _open_note_path(self, path):
        vault = self.vault()
        if vault and os.path.abspath(path).startswith(os.path.abspath(vault)):
            obs.open_in_obsidian(vault, os.path.relpath(path, vault).replace("\\", "/"))
        else:
            open_folder(path)

    # ----- mock quizzes and exams ----------------------------------------------------

    def _gather(self, src, topic, text, files):
        """(material, what it is, a name) for mock exams. Runs in a background thread."""
        if src == "note":
            note = self.obs_api.active_note()
            return note["content"], f"the Obsidian note {note['path']}", obs.link_name(note["path"])
        if src == "chat":
            last = "\n\n".join((m.get("display") or m["content"]) for m in self.history[-12:])
            return last, "our conversation", (self.chat_meta or {}).get("title") or "This chat"
        if src == "book":
            found = self.library.lookup(text, books.parse_ref(text) or {}, self.book_ctx)
            if not isinstance(found, dict):
                raise ValueError(found or "I couldn't find that book in your Notes.")
            return found["text"], f"{found['title']}, {found['label']}", f"{found['title']} - {found['label']}"
        if src == "deck":
            name = self.study.find_deck(topic) or self.study.find_deck(topic.split()[0] if topic else "")
            d = self.study.load(name) if name else None
            if not d:
                raise ValueError(f"I couldn't find a deck called \"{topic}\". Type  decks  to see them.")
            return ("\n".join(f"Q: {c['q']}\nA: {c['a']}" for c in d["cards"]),
                    f"the flashcard deck {d['name']}", d["name"])
        if files:
            parts = [read_text(p) for p in files if file_kind(p) == "text"]
            return "\n\n".join(parts), ", ".join(os.path.basename(p) for p in files), \
                os.path.splitext(os.path.basename(files[0]))[0]
        # a topic: your own notes first, then offline Wikipedia
        name = topic or "General knowledge"
        for e in self.calendar.upcoming(datetime.date.today(), days=60):
            words = [w for w in re.findall(r"\w+", topic.lower()) if len(w) > 2]
            if words and all(w in e["title"].lower() for w in words[:2]):
                name = e["title"]
        chunks = []
        try:
            for _s, rel, txt in self.notes.search(topic or text, k=6):
                chunks.append(f"[from {friendly_source(rel)}]\n{txt}")
        except Exception:
            pass
        if self.cfg.get("use_wiki") or not chunks:
            try:
                chunks += [f"[Wikipedia: {t}]\n{x}" for t, x in self.wiki.search(topic or text)[:3]]
            except Exception:
                pass
        return "\n\n".join(chunks), f"the topic: {topic or text}" + (" (from your notes)" if chunks else ""), name

    def start_mock(self, req, text, files):
        self._you(text)
        label = {"quiz": "quiz", "midterm": "mock midterm", "final": "mock final"}.get(req["kind"], "mock exam")
        self._write(f"Writing a {req['n']}-question {label}"
                    + (f" ({req['minutes']} minutes)" if req["minutes"] else "") + "... this takes a minute "
                    "or two. You can keep chatting.\n", "sys")
        model = self.cfg["model"]

        def work():
            try:
                material, what, name = self._gather(req["source"], req["topic"], text, files)
                qs = exam.make_exam(quick_chat, model, material, what, req["kind"], req["n"],
                                    progress=lambda f: self.bg_q.put(("status", f"writing the {label}... {int(f * 100)}%")))
                if len(qs) < 3:
                    raise ValueError("the model didn't write enough usable questions. Try again, or a narrower topic.")
                title = f"{name} ({label})"
                ex = self.exams.new(title, req["kind"], qs, req["minutes"], what)
                self.bg_q.put(("call", lambda: (self._update_status(), self._exam_ready(ex))))
                if req.get("to_feather"):
                    self.bg_q.put(("call", lambda: self.feather_xfer("a2f", ex["title"], kind="exam", eid=str(ex["id"]))))
            except obs.ApiError as e:
                self.bg_q.put(("voice_error", e.friendly()))
            except Exception as e:
                self.bg_q.put(("voice_error", f"Couldn't make the {label}: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _exam_ready(self, ex):
        n = len(ex["questions"])
        pts = sum(q["points"] for q in ex["questions"])
        kinds = {t: sum(1 for q in ex["questions"] if q["type"] == t) for t in ("mc", "tf", "short", "long")}
        parts = ", ".join(f"{v} {k}" for k, v in (("multiple choice", kinds["mc"]), ("true/false", kinds["tf"]),
                                                   ("short answer", kinds["short"]), ("long answer", kinds["long"])) if v)
        self._archie()
        self._w(f"Your {ex['title']} is ready: {n} questions, {pts} points ({parts})"
                + (f", {ex['minutes']} minutes" if ex.get("minutes") else "") + ".  ", "abody")
        self._link("start it", lambda: self.show_exam(ex), "abody")
        self._end_span()
        self._write("\n", "abody")

    def show_exam(self, ex, retake=False):
        px = self.px
        if getattr(self, "exam_win", None) and self.exam_win.winfo_exists():
            self.exam_win.destroy()
        w = self.exam_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = px(max(520, self.PANEL_W + 40)), px(max(660, self.PANEL_H + 20))
        w.geometry(f"{W}x{H}+{max(0, self.panel.winfo_x() - px(30))}+{max(0, self.panel.winfo_y() - px(10))}")
        qs = [dict(q) for q in ex["questions"]]
        if retake:
            for q in qs:
                if q["type"] == "mc":
                    right = q["options"][q["answer"]]
                    random.shuffle(q["options"])
                    q["answer"] = q["options"].index(right)
        st = {"i": 0, "ans": {}, "flag": set(), "start": time.time(), "done": False, "confirm": False}
        s = self.TEXT_SIZES.get(self.cfg.get("text_size"), 10)

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        tk.Label(top, text="MOCK " + ("QUIZ" if ex["kind"] == "quiz" else "EXAM"), bg=BG, fg=TEXT,
                 font=(MONO, 10, "bold")).pack(side="left")
        timer = tk.Label(top, text="", bg=BG, fg=MUTED, font=(MONO, 10))
        timer.pack(side="left", padx=px(10))
        self._icon_btn(top, "close", w.destroy, "Close (your progress on this attempt is lost)").pack(side="right")
        top.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
        top.bind("<B1-Motion>", lambda e: w.geometry(
            f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))
        tk.Label(w, text=ex["title"], bg=BG, fg=MUTED, font=(MONO, 8), anchor="w").pack(fill="x", padx=px(14))
        dots = tk.Canvas(w, bg=BG, highlightthickness=0, bd=0, height=px(24 if len(qs) <= 20 else 46))
        dots.pack(fill="x", padx=px(14), pady=(px(6), px(4)))

        body = tk.Frame(w, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        body.pack(fill="both", expand=True, padx=px(14), pady=px(6))
        bottom = tk.Frame(w, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=px(14), pady=(px(4), px(12)))
        note = tk.Label(w, text="", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w")
        note.pack(side="bottom", fill="x", padx=px(14))

        def btn(parent, text, cmd, primary=False, color=None):
            b = tk.Label(parent, text=text, font=(MONO, 8, "bold" if primary else "normal"),
                         bg=(color or ACCENT) if primary else BG, fg=TILE if primary else DIM, padx=px(10),
                         pady=px(4), bd=0, cursor="hand2", highlightthickness=0 if primary else 1,
                         highlightbackground=BORDER)
            b.bind("<ButtonRelease-1>", lambda e: cmd())
            return b

        def draw_dots():
            dots.delete("all")
            per_row = 20
            size, gap = px(16), px(5)
            dots._boxes = []
            for i, q in enumerate(qs):
                r, c = divmod(i, per_row)
                x0, y0 = c * (size + gap), r * (size + px(6))
                answered = i in st["ans"] and str(st["ans"][i]).strip() != ""
                fill = ACCENT if answered else SURFACE
                out = "#f5a524" if i in st["flag"] else (TEXT if i == st["i"] else BORDER)
                dots.create_rectangle(x0, y0, x0 + size, y0 + size, fill=fill, outline=out,
                                      width=2 if i == st["i"] or i in st["flag"] else 1)
                dots.create_text(x0 + size / 2, y0 + size / 2, text=str(i + 1), font=(MONO, 7),
                                 fill=TILE if answered else MUTED)
                dots._boxes.append((x0, y0, x0 + size, y0 + size, i))

        def dot_click(e):
            for x0, y0, x1, y1, i in getattr(dots, "_boxes", []):
                if x0 <= e.x <= x1 and y0 <= e.y <= y1:
                    save_text()
                    st["i"] = i
                    draw()
        dots.bind("<Button-1>", dot_click)

        def save_text():
            if getattr(body, "_text", None) is not None and body._text.winfo_exists():
                st["ans"][st["i"]] = body._text.get("1.0", "end").strip()

        def draw():
            if st["done"]:
                return
            for c in body.winfo_children():
                c.destroy()
            body._text = None
            q = qs[st["i"]]
            kind = {"mc": "multiple choice", "tf": "true or false", "short": "short answer",
                    "long": "long answer"}[q["type"]]
            tk.Label(body, text=f"question {st['i'] + 1} of {len(qs)}  ·  {kind}  ·  {q['points']} "
                                f"point{'s' if q['points'] != 1 else ''}", bg=SURFACE, fg=MUTED,
                     font=(MONO, 8), anchor="w").pack(fill="x", padx=px(16), pady=(px(14), px(4)))
            tk.Label(body, text=q["q"], bg=SURFACE, fg=TEXT, font=(FONT_SEMI, s + 2), justify="left",
                     anchor="w", wraplength=W - px(80)).pack(fill="x", padx=px(16), pady=(0, px(12)))
            if q["type"] in ("mc", "tf"):
                opts = q["options"] if q["type"] == "mc" else ["True", "False"]
                for j, o in enumerate(opts):
                    val = j if q["type"] == "mc" else (j == 0)
                    chosen = st["ans"].get(st["i"]) == val and st["i"] in st["ans"]
                    row = tk.Frame(body, bg=INPUT_BG if chosen else SURFACE, highlightthickness=1,
                                   highlightbackground=ACCENT if chosen else BORDER, cursor="hand2")
                    row.pack(fill="x", padx=px(16), pady=px(3))
                    lab = tk.Label(row, text=f"{'ABCD'[j] if q['type'] == 'mc' else 'TF'[j]}   {o}",
                                   bg=row.cget("bg"), fg=ACCENT if chosen else TEXT, font=(FONT, s), justify="left",
                                   anchor="w", wraplength=W - px(110), cursor="hand2")
                    lab.pack(fill="x", padx=px(10), pady=px(7))
                    for wd in (row, lab):
                        wd.bind("<ButtonRelease-1>", lambda e, v=val: choose(v))
            else:
                t = tk.Text(body, height=4 if q["type"] == "short" else 9, bg=BG, fg=TEXT, insertbackground=ACCENT,
                            wrap="word", bd=0, padx=px(10), pady=px(8), font=(FONT, s), highlightthickness=1,
                            highlightbackground=BORDER, highlightcolor=ACCENT, undo=True)
                t.pack(fill="both", expand=True, padx=px(16), pady=(0, px(14)))
                t.insert("1.0", st["ans"].get(st["i"], ""))
                t.bind("<KeyRelease>", lambda e: (save_text(), draw_dots()))
                t.focus_set()
                body._text = t
            for c in bottom.winfo_children():
                c.destroy()
            btn(bottom, "flag" if st["i"] not in st["flag"] else "unflag", toggle_flag).pack(side="left")
            last = st["i"] == len(qs) - 1
            btn(bottom, "submit", submit, primary=True).pack(side="right")
            if not last:
                btn(bottom, "next ›", lambda: go(1)).pack(side="right", padx=(0, px(6)))
            if st["i"] > 0:
                btn(bottom, "‹ prev", lambda: go(-1)).pack(side="right", padx=(0, px(6)))
            left = len(qs) - sum(1 for i in range(len(qs)) if str(st["ans"].get(i, "")).strip() != "")
            note.configure(text=f"{left} unanswered · keys: A-D / T-F to answer, arrows to move" if q["type"] in ("mc", "tf")
                           else f"{left} unanswered · Ctrl+Enter for next", fg=MUTED)
            st["confirm"] = False
            draw_dots()

        def choose(v):
            st["ans"][st["i"]] = v
            draw()
            if st["i"] < len(qs) - 1:
                w.after(250, lambda: go(1))

        def go(d):
            save_text()
            st["i"] = max(0, min(len(qs) - 1, st["i"] + d))
            draw()

        def toggle_flag():
            st["flag"].symmetric_difference_update({st["i"]})
            draw()

        def tick():
            if not w.winfo_exists() or st["done"]:
                return
            el = time.time() - st["start"]
            if ex.get("minutes"):
                left = ex["minutes"] * 60 - el
                timer.configure(text=f"{int(left // 60)}:{int(left % 60):02d} left" if left > 0 else "time's up",
                                fg=REC if left < 120 else MUTED)
                if left <= 0:
                    save_text()
                    note.configure(text="Time's up, so I'm handing it in.", fg=REC)
                    return finish()
            else:
                timer.configure(text=f"{int(el // 60)}:{int(el % 60):02d}")
            w.after(1000, tick)

        def submit():
            save_text()
            left = [i + 1 for i in range(len(qs)) if str(st["ans"].get(i, "")).strip() == ""]
            if left and not st["confirm"]:
                st["confirm"] = True
                note.configure(text=f"{len(left)} unanswered (#{', #'.join(map(str, left[:8]))}"
                                    f"{'...' if len(left) > 8 else ''}). Click submit again to hand it in anyway.",
                               fg=REC)
                return
            finish()

        def finish():
            st["done"] = True
            st["time"] = time.time() - st["start"]
            for c in bottom.winfo_children():
                c.destroy()
            for c in body.winfo_children():
                c.destroy()
            dots.delete("all")
            msg = tk.Label(body, text="grading...", bg=SURFACE, fg=MUTED, font=(MONO, 9))
            msg.pack(pady=px(40))
            model = self.cfg["model"]
            answers = dict(st["ans"])

            def work():
                results = []
                written = [i for i, q in enumerate(qs) if q["type"] in ("short", "long")]
                for i, q in enumerate(qs):
                    a = answers.get(i, "")
                    if q["type"] in ("mc", "tf"):
                        ok = a == q["answer"] and str(a) != ""
                        results.append({"pts": q["points"] if ok else 0, "fb": q.get("explain", "")})
                    else:
                        n = written.index(i) + 1
                        self.bg_q.put(("call", lambda n=n: msg.winfo_exists() and msg.configure(
                            text=f"grading your written answers... {n} of {len(written)}")))
                        try:
                            pts, fb = exam.grade_written(quick_chat, model, q, str(a))
                        except Exception as e:
                            pts, fb = 0.0, f"(couldn't grade this one: {e})"
                        results.append({"pts": pts, "fb": fb})
                total = sum(q["points"] for q in qs)
                got = sum(r["pts"] for r in results)
                pct = round(100 * got / total) if total else 0
                missed = [q for q, r in zip(qs, results) if r["pts"] < q["points"]]
                tips = exam.review(quick_chat, model, ex["kind"], pct, missed)
                self.bg_q.put(("call", lambda: show_results(results, got, total, pct, tips)))
            threading.Thread(target=work, daemon=True).start()

        def show_results(results, got, total, pct, tips):
            if not w.winfo_exists():
                return
            ex.setdefault("attempts", []).append({"date": datetime.datetime.now().isoformat(timespec="minutes"),
                                                  "score": pct, "points": got, "of": total,
                                                  "minutes": round(st["time"] / 60, 1)})
            self.exams.save(ex)
            for c in body.winfo_children():
                c.destroy()
            head = tk.Frame(body, bg=SURFACE)
            head.pack(fill="x", padx=px(16), pady=(px(14), px(4)))
            tk.Label(head, text=f"{pct}%", bg=SURFACE, fg=ACCENT if pct >= 80 else "#f5a524" if pct >= 60 else REC,
                     font=(FONT_SEMI, 28)).pack(side="left")
            tk.Label(head, text=f"  {exam.letter(pct)}   ·   {got:g} / {total} points   ·   "
                                f"{int(st['time'] // 60)} min", bg=SURFACE, fg=MUTED, font=(MONO, 9)).pack(side="left")
            prev = ex["attempts"][:-1]
            if prev:
                tk.Label(body, text=f"last time: {prev[-1]['score']}%", bg=SURFACE, fg=MUTED, font=(MONO, 8),
                         anchor="w").pack(fill="x", padx=px(16))
            txt = tk.Text(body, bg=SURFACE, fg=BODY, wrap="word", bd=0, padx=px(16), pady=px(8),
                          font=(FONT, s - 1), highlightthickness=0, cursor="arrow")
            sb = th.SlimScrollbar(body, txt, width=px(8))
            sb.configure(bg=SURFACE)
            txt.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            txt.pack(fill="both", expand=True)
            txt.tag_configure("h", foreground=TEXT, font=(MONO, s - 2, "bold"), spacing1=px(10))
            txt.tag_configure("ok", foreground=ACCENT)
            txt.tag_configure("part", foreground="#f5a524")
            txt.tag_configure("bad", foreground=REC)
            txt.tag_configure("q", foreground=TEXT, spacing1=px(8))
            txt.tag_configure("m", foreground=MUTED, font=(FONT, s - 2))
            if tips:
                txt.insert("end", "what to review\n", "h")
                txt.insert("end", tips.strip() + "\n", "")
            txt.insert("end", "every question\n", "h")
            for i, (q, r) in enumerate(zip(qs, results)):
                a = st["ans"].get(i, "")
                mark, tag = ("✓", "ok") if r["pts"] >= q["points"] else (("~", "part") if r["pts"] > 0 else ("✗", "bad"))
                txt.insert("end", f"{mark} {i + 1}. ", tag)
                txt.insert("end", q["q"] + f"  ({r['pts']:g}/{q['points']})\n", "q")
                if q["type"] == "mc":
                    yours = q["options"][a] if isinstance(a, int) and not isinstance(a, bool) and 0 <= a < len(q["options"]) else "(no answer)"
                elif q["type"] == "tf":
                    yours = ("True" if a else "False") if isinstance(a, bool) else "(no answer)"
                else:
                    yours = str(a) or "(no answer)"
                txt.insert("end", "your answer: " + yours + "\n", "m")
                if r["pts"] < q["points"]:
                    txt.insert("end", "answer: " + exam.answer_text(q) + "\n", "m")
                if r["fb"]:
                    txt.insert("end", r["fb"] + "\n", "m")
            txt.configure(state="disabled")
            missed = [q for q, r in zip(qs, results) if r["pts"] < q["points"]]

            def cards_from_mistakes():
                cards = [{"q": q["q"] + (("\n" + "\n".join(f"{'ABCD'[k]}) {o}" for k, o in enumerate(q["options"])))
                                         if q["type"] == "mc" else ""),
                          "a": exam.answer_text(q) + (f". {q['explain']}" if q.get("explain") else "")}
                         for q in missed]
                name, added = self.study.add_cards(ex["title"] + " mistakes", cards, source=ex["title"])
                note.configure(text=f"Added {added} cards to the deck \"{name}\". Type  study  to review them.", fg=ACCENT)

            def save_obsidian():
                vault = self.vault()
                if not vault:
                    note.configure(text="No Obsidian vault set.", fg=REC)
                    return
                lines = [f"---\ntags: [archie, mock-exam]\nscore: {pct}\ndate: {datetime.date.today()}\n---",
                         f"# {ex['title']}", "", f"**Score:** {pct}% ({exam.letter(pct)}), {got:g}/{total} points, "
                         f"{int(st['time'] // 60)} minutes", ""]
                if tips:
                    lines += ["## What to review", tips.strip(), ""]
                lines.append("## Questions")
                for i, (q, r) in enumerate(zip(qs, results)):
                    mark = "✓" if r["pts"] >= q["points"] else "✗"
                    lines.append(f"{i + 1}. {mark} {q['q']}")
                    if q["type"] == "mc":
                        lines += [f"    - {'ABCD'[k]}) {o}" for k, o in enumerate(q["options"])]
                    lines.append(f"    - **Answer:** {exam.answer_text(q)}")
                    if r["fb"]:
                        lines.append(f"    - {r['fb']}")
                rel = obs.save_note(vault, ex["title"] + f" {datetime.date.today()}", "\n".join(lines) + "\n",
                                    subfolder="Mock exams")
                note.configure(text="Saved to Obsidian: " + rel, fg=ACCENT)

            btn(bottom, "close", w.destroy, primary=True).pack(side="right")
            btn(bottom, "retake", lambda: self.show_exam(ex, retake=True)).pack(side="right", padx=(0, px(6)))
            btn(bottom, "save → obsidian", save_obsidian).pack(side="right", padx=(0, px(6)))
            if missed:
                btn(bottom, "flashcards from my mistakes", cards_from_mistakes).pack(side="left")
            timer.configure(text="")
            note.configure(text="Scroll to see every question, your answer and the right one.", fg=MUTED)

        def key(e):
            if st["done"]:
                return
            q = qs[st["i"]]
            if isinstance(e.widget, tk.Text):
                if e.keysym == "Return" and (e.state & 0x4):
                    go(1)
                    return "break"
                return None
            if q["type"] == "mc" and e.char and e.char.upper() in "ABCD"[:len(q["options"])]:
                choose("ABCD".index(e.char.upper()))
            elif q["type"] == "tf" and e.char and e.char.upper() in "TF":
                choose(e.char.upper() == "T")
            elif e.keysym in ("Right", "Down"):
                go(1)
            elif e.keysym in ("Left", "Up"):
                go(-1)
        w.bind("<Key>", key)
        w.bind("<Escape>", lambda e: None)
        draw()
        tick()
        w.focus_force()

    def list_exams(self):
        exs = self.exams.all()
        if not exs:
            self._write("No mock exams yet. Try: make a mock exam on PID control\n", "sys")
            return
        self._archie()
        try:
            with open(os.path.join(STUDY_DIR, ".feather_exams"), encoding="utf-8") as f:
                fx = json.load(f).get("exams") or {}
        except (OSError, ValueError, AttributeError):
            fx = {}
        self._w("Your mock exams:\n", "abody")
        for ex in exs[:10]:
            best = max((a["score"] for a in ex.get("attempts", [])), default=None)
            f = fx.get(str(ex.get("id")))
            st = ("" if not f else "  ·  Feather has new attempts" if f.get("linked") and f.get("fnewer")
                  else "  ·  in Feather" if f.get("linked") else "  ·  Feather has a copy")
            self._w(f"{ex['title']}  ·  {len(ex['questions'])} q"
                    + (f"  ·  best {best}%" if best is not None else "  ·  not taken yet") + st + "   ", "abody")
            self._link("take it" if best is None else "retake", lambda ex=ex: self.show_exam(ex, retake=True), "abody")
            self._w("   ", "abody")
            self._link("send to Feather", lambda ex=ex: self.feather_xfer("a2f", ex["title"], kind="exam", eid=str(ex["id"])), "abody")
            if f:
                self._w("   ", "abody")
                self._link("get Feather's", lambda ex=ex: self.feather_xfer("f2a", ex["title"], kind="exam", eid=str(ex["id"])), "abody")
            self._w("\n", "abody")
        mine = {str(ex.get("id")) for ex in exs}
        for eid, f in fx.items():
            if eid not in mine:
                self._w(f"{f.get('title')}  ·  only in Feather   ", "abody")
                self._link("request", lambda eid=eid, f=f: self.feather_xfer("f2a", f.get("title") or eid, kind="exam", eid=eid), "abody")
                self._w("\n", "abody")
        self._end_span()
        self._write("\n", "abody")

    # ----- study: flashcards + spaced review ------------------------------------

    def _study_label(self):
        try:
            rev, new = self.study.counts()
        except Exception:
            return "Study flashcards"
        return f"Study flashcards  ({rev} due, {new} new)" if rev or new else "Study flashcards  (all done)"

    def _refresh_menu_labels(self):
        try:
            self.menu.entryconfigure(self._study_menu_index, label=self._study_label())
        except (tk.TclError, AttributeError):
            pass

    def _make_cards(self, req, text, files):
        """'make flashcards from this note / that / <book> chapter 3 / about X'."""
        self._you(text)
        src = req["source"]
        if src == "files" and not files:
            src = "chat" if any(m["role"] == "assistant" for m in self.history) else None
        if src is None:
            self._write("What should the cards be about? Try: make flashcards about the Krebs cycle, "
                        "... from this note, ... from that (my last answer), or attach a file and "
                        "say make flashcards.\n", "sys")
            return
        last = next((m["content"] for m in reversed(self.history) if m["role"] == "assistant"), "")
        chat_text = "\n\n".join((m.get("display") or m["content"]) for m in self.history[-12:])
        model, n = self.cfg["model"], req["n"]
        self._write(f"Making about {n} flashcards... (you can keep chatting)\n", "sys")

        def work():
            try:
                if src == "note":
                    note = self.obs_api.active_note()
                    material, what = note["content"], f"the Obsidian note {note['path']}"
                    deck = obs.link_name(note["path"])
                elif src == "chat":
                    material = last if re.search(r"\b(that|last answer|what you (just )?said)\b",
                                                 text, re.I) and last else chat_text
                    what, deck = "our conversation", (self.chat_meta or {}).get("title") or "Chat cards"
                elif src == "book":
                    ref = books.parse_ref(text)
                    found = self.library.lookup(text, ref or {}, self.book_ctx)
                    if not isinstance(found, dict):
                        raise ValueError(found or "I couldn't find that book in your Notes.")
                    material, what = found["text"], f"{found['title']}, {found['label']}"
                    deck = f"{found['title']} - {found['label']}"
                elif src == "files":
                    parts = []
                    for p in files:
                        if file_kind(p) == "text":
                            parts.append(read_text(p))
                    if not parts:
                        raise ValueError("I can only make cards from text files (PDF, Word, notes...).")
                    material = "\n\n".join(parts)
                    what = ", ".join(os.path.basename(p) for p in files)
                    deck = os.path.splitext(os.path.basename(files[0]))[0]
                else:
                    topic = req["topic"]
                    material, what, deck = "", f"the topic: {topic}", topic.title()
                    if self.cfg.get("use_wiki"):
                        try:
                            arts = self.wiki.search(topic)
                            material = "\n\n".join(f"Wikipedia: {t}\n{x}" for t, x in arts[:3])
                            what += " (from offline Wikipedia)"
                        except Exception:
                            pass
                cards = study.make_cards(quick_chat, model, material, what, n,
                                         progress=lambda f: self.bg_q.put(("status", f"making flashcards... {int(f * 100)}%")))
                if not cards:
                    raise ValueError("the model didn't return any cards. Try again, or a smaller piece.")
                name, added = self.study.add_cards(deck, cards, source=what)
                self.bg_q.put(("call", lambda: self._cards_made(name, added)))
            except obs.ApiError as e:
                self.bg_q.put(("voice_error", e.friendly()))
            except Exception as e:
                self.bg_q.put(("voice_error", f"Couldn't make flashcards: {e}"))
        threading.Thread(target=work, daemon=True).start()

    def _cards_made(self, deck, added):
        self._update_status()
        self._archie()
        self._w(f"Made {added} new flashcard{'s' if added != 1 else ''} in the deck \"{deck}\". ", "abody")
        self._link("study them now", lambda: self.show_study(deck), "abody")
        self._w("  ·  ", "abody")
        self._link("study everything due", lambda: self.show_study(None), "abody")
        self._end_span()
        self._write("\n", "abody")

    def show_study(self, deck=None):
        """The review window: question, your answer (optional), reveal, then rate it."""
        queue_ = self.study.due(deck)
        if not self.panel_visible():
            self.show_panel()
        if not queue_:
            self._write("Nothing to study right now. " + ("Make some cards: e.g. make flashcards about "
                        "the Krebs cycle." if not self.study.decks() else "You're all caught up.") + "\n", "sys")
            return
        if getattr(self, "study_win", None) and self.study_win.winfo_exists():
            self.study_win.destroy()
        px = self.px
        w = self.study_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = px(max(440, self.PANEL_W - 20)), px(max(480, self.PANEL_H - 60))
        w.geometry(f"{W}x{H}+{self.panel.winfo_x() + px(10)}+{self.panel.winfo_y() + px(30)}")
        state = {"q": list(queue_), "i": 0, "total": len(queue_), "right": 0, "shown": False,
                 "graded": None, "busy": False}

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        tk.Label(top, text="STUDY", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        prog = tk.Label(top, text="", bg=BG, fg=MUTED, font=(MONO, 9))
        prog.pack(side="left", padx=px(8))
        self._icon_btn(top, "close", w.destroy, "Close (Esc)").pack(side="right")
        send_l = tk.Label(top, text="send set to Feather", bg=BG, fg=ACCENT, font=(MONO, 8), cursor="hand2")
        send_l.pack(side="right", padx=(0, px(8)))

        def send_set(_e=None):
            c = current()
            if c:
                self.feather_xfer("a2f", c["deck"])
                send_l.configure(text="sent at next sync", fg=MUTED)
        send_l.bind("<ButtonRelease-1>", send_set)
        for wid in (top, prog):
            wid.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
            wid.bind("<B1-Motion>", lambda e: w.geometry(
                f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))
        deck_l = tk.Label(w, text="", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w")
        deck_l.pack(fill="x", padx=px(14))

        s = self.TEXT_SIZES.get(self.cfg.get("text_size"), 10)
        card = tk.Frame(w, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True, padx=px(14), pady=px(8))
        q_l = tk.Label(card, text="", bg=SURFACE, fg=TEXT, font=(FONT_SEMI, s + 3), justify="left",
                       anchor="nw", wraplength=W - px(70))
        q_l.pack(fill="x", padx=px(16), pady=(px(16), px(8)))
        a_l = tk.Label(card, text="", bg=SURFACE, fg=BODY, font=(FONT, s + 1), justify="left",
                       anchor="nw", wraplength=W - px(70))
        a_l.pack(fill="x", padx=px(16), pady=(0, px(6)))
        fb_l = tk.Label(card, text="", bg=SURFACE, fg=ACCENT, font=(FONT, s), justify="left",
                        anchor="nw", wraplength=W - px(70))
        fb_l.pack(fill="x", padx=px(16))
        exp_l = tk.Label(card, text="explain this deeper in the chat  →", bg=SURFACE, fg=ACCENT,
                         font=(MONO, 8), cursor="hand2")
        exp_l.bind("<ButtonRelease-1>", lambda e: explain())

        bottom = tk.Frame(w, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=px(14), pady=(px(4), px(12)))
        hint = tk.Label(w, text="", bg=BG, fg=MUTED, font=(MONO, 8), anchor="w")
        hint.pack(side="bottom", fill="x", padx=px(14))
        ans_box = tk.Frame(w, bg=BG)
        ans_box.pack(side="bottom", fill="x", padx=px(14))
        tk.Label(ans_box, text=">", bg=BG, fg=ACCENT, font=(MONO, 11)).pack(side="left", anchor="n")
        ans = tk.Text(ans_box, height=2, bg=BG, fg=TEXT, insertbackground=ACCENT, bd=0, wrap="word",
                      font=(MONO, s - 1), highlightthickness=0, padx=px(6), pady=px(3))
        ans.pack(side="left", fill="x", expand=True)

        def btn(parent, text, cmd, primary=False, color=None):
            b = tk.Label(parent, text=text, font=(MONO, 8, "bold" if primary else "normal"),
                         bg=(color or ACCENT) if primary else BG, fg=TILE if primary else DIM,
                         padx=px(10), pady=px(5), bd=0, cursor="hand2",
                         highlightthickness=0 if primary else 1, highlightbackground=color or BORDER)
            b.bind("<ButtonRelease-1>", lambda e: cmd())
            return b

        def current():
            return state["q"][state["i"]] if state["i"] < len(state["q"]) else None

        def draw():
            for x in bottom.winfo_children():
                x.destroy()
            c = current()
            done_n = state["i"]
            prog.configure(text=f"{min(done_n + 1, len(state['q']))} / {len(state['q'])}")
            if c is None:
                finish()
                return
            deck_l.configure(text=f"{c['deck']}" + ("  ·  new card" if c["reps"] == 0 and not c["last"] else ""))
            q_l.configure(text=c["q"])
            if not state["shown"]:
                exp_l.pack_forget()
                a_l.configure(text="")
                fb_l.configure(text="")
                ans.configure(state="normal")
                btn(bottom, "show answer", reveal, primary=True).pack(side="right")
                btn(bottom, "check my answer", check).pack(side="right", padx=(0, px(6)))
                btn(bottom, "delete card", delete).pack(side="left")
                hint.configure(text="type + Enter: Archie checks it  ·  Space: just show it")
                ans.focus_set()
            else:
                a_l.configure(text=c["a"])
                pv = study.preview_intervals(c)
                for g, label, col in ((4, "easy", "#5eead4"), (3, "good", ACCENT), (2, "hard", "#f5a524"),
                                      (1, "again", REC)):
                    b = btn(bottom, f"{g} {label} · {pv[g]}", lambda g=g: rate(g), primary=True, color=col)
                    b.pack(side="right", padx=(px(6), 0))
                exp_l.pack(side="bottom", anchor="w", padx=px(16), pady=(0, px(12)))
                sug = state["graded"]
                hint.configure(text=(f"Archie suggests {sug}. " if sug else "") +
                               "How well did you know it?  keys 1-4")

        def reveal():
            if state["shown"]:
                return
            state["shown"] = True
            ans.configure(state="disabled")
            draw()

        def check():
            user = ans.get("1.0", "end").strip()
            c = current()
            if not user or not c or state["busy"]:
                return reveal() if not user else None
            state["busy"] = True
            hint.configure(text="checking your answer...")

            def work():
                try:
                    r = study.grade(quick_chat, self.cfg["model"], c["q"], c["a"], user)
                except Exception as e:
                    r = {"verdict": "", "feedback": f"(couldn't check: {e})", "grade": None}
                self.bg_q.put(("call", lambda: checked(r)))
            threading.Thread(target=work, daemon=True).start()

        def checked(r):
            state["busy"] = False
            if not w.winfo_exists():
                return
            mark = {"right": "✓ right. ", "partly": "~ partly. ", "wrong": "✗ not quite. "}.get(r["verdict"], "")
            state["graded"] = {1: "1 again", 2: "2 hard", 3: "3 good", 4: "4 easy"}.get(r["grade"])
            state["shown"] = True
            ans.configure(state="disabled")
            draw()
            fb_l.configure(text=mark + r["feedback"],
                           fg={"right": ACCENT, "partly": "#f5a524", "wrong": REC}.get(r["verdict"], MUTED))

        def rate(g):
            c = current()
            if not c or not state["shown"]:
                return
            new = study.schedule(c, g)
            self.study.update_card(c["deck"], new)
            if g == 1:
                state["q"].append(dict(new, deck=c["deck"]))   # see it again this session
            else:
                state["right"] += 1
            state["i"] += 1
            state["shown"], state["graded"] = False, None
            ans.configure(state="normal")
            ans.delete("1.0", "end")
            draw()

        def delete():
            c = current()
            if c:
                self.study.delete_card(c["deck"], c["id"])
                state["q"] = [x for x in state["q"] if x["id"] != c["id"]]
                state["shown"] = False
                draw()

        def explain():
            c = current()
            if not c:
                return
            if "Professor" in self.modes and self.cfg.get("mode") != "Professor":
                self.set_mode("Professor", announce=False)
            self.entry.delete("1.0", "end")
            self.entry.insert("1.0", f"Teach me this properly, from first principles: {c['q']}\n"
                                     f"(The short answer on my flashcard: {c['a']})")
            self._send()
            w.lower()
            self.panel.lift()

        def finish():
            exp_l.pack_forget()
            q_l.configure(text="Session done. Nice work.")
            reviewed = state["i"]
            a_l.configure(text=f"{reviewed} cards reviewed · {state['right']} passed on the first try or later.")
            rev, new = self.study.counts()
            fb_l.configure(text="Nothing else is due today." if not rev and not new
                           else f"Still waiting: {rev} due, {new} new.", fg=MUTED)
            ans.configure(state="disabled")
            hint.configure(text="")
            btn(bottom, "close", w.destroy, primary=True).pack(side="right")
            self._sync_daily(quiet=True)

        def key(e):
            if isinstance(e.widget, tk.Text) and not state["shown"]:
                if e.keysym == "Return":
                    check()
                    return "break"
                return None
            if e.keysym == "space" and not state["shown"]:
                reveal()
                return "break"
            if e.char in "1234" and e.char and state["shown"]:
                rate(int(e.char))
                return "break"
            return None

        w.bind("<Key>", key)
        ans.bind("<Return>", lambda e: (check(), "break")[1])
        ans.bind("<space>", lambda e: (reveal(), "break")[1] if not ans.get("1.0", "end").strip() else None)
        w.bind("<Escape>", lambda e: w.destroy())
        draw()

    def _feather_sets(self):
        """Feather's flashcard sets as your PC last saw them (written by Feather's hub at each sync)."""
        try:
            with open(os.path.join(STUDY_DIR, ".feather_decks"), encoding="utf-8") as f:
                return json.load(f).get("decks") or {}
        except (OSError, ValueError, AttributeError):
            return {}

    def send_to_feather(self, paths):
        """A PDF, EPUB or text book into Feather's Reading on every device (your PC adds it at the next sync).
        Other files stay here: Feather's Reading only takes books."""
        import shutil
        inc = os.path.join(os.path.dirname(APP_DIR), "Feather", "incoming")
        sent, skipped = [], []
        for p in paths:
            if os.path.isfile(p) and p.lower().endswith(".md"):
                try:
                    with open(p, encoding="utf-8", errors="replace") as f:
                        r = self.note_to_feather(f.read())
                    sent.append(os.path.basename(p) + " (as a quick note)") if r else skipped.append(os.path.basename(p))
                except OSError as e:
                    skipped.append(f"{os.path.basename(p)} ({e})")
                continue
            if not (os.path.isfile(p) and p.lower().endswith((".pdf", ".epub", ".txt"))):
                skipped.append(os.path.basename(p))
                continue
            try:
                os.makedirs(inc, exist_ok=True)
                stem, ext = os.path.splitext(os.path.basename(p))
                to, n = os.path.join(inc, stem + ext), 2
                while os.path.exists(to):
                    to, n = os.path.join(inc, f"{stem} ({n}){ext}"), n + 1
                shutil.copy2(p, to)
                sent.append(os.path.basename(p))
            except OSError as e:
                skipped.append(f"{os.path.basename(p)} ({e})")
        msg = (f"sent to Feather: {', '.join(sent)} · in Reading on your phone and laptops after their next sync" if sent else "")
        if skipped:
            msg += ("  ·  " if msg else "") + "not sent (Feather takes PDF, EPUB, text and .md notes): " + ", ".join(skipped)
        return msg or "nothing to send"

    # ----- Sonia audio for Feather: your PC reads chapters with Sonia, the phone and laptops play them offline -----
    def _sonia_books(self):
        try:
            with open(os.path.join(APP_DIR, "feather_books.json"), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def sonia_ask(self, rid=None, book=None, fr=0, to=None, devs=("phone", "laptops"), setting=None):
        """A request for Feather's hub (it picks it up at the next sync with your phone or a laptop)."""
        import uuid
        q = os.path.join(os.path.dirname(APP_DIR), "Feather", "sonia_in")
        rec = {"id": "p" + uuid.uuid4().hex[:11]}
        if rid or book:
            rec.update(rid=rid, book=book, **{"from": int(fr), "to": None if to is None else int(to), "for": list(devs)})
        if setting:
            rec["set"] = setting
        try:
            os.makedirs(q, exist_ok=True)
            with open(os.path.join(q, rec["id"] + ".tmp"), "w", encoding="utf-8") as f:
                json.dump(rec, f)
            os.replace(os.path.join(q, rec["id"] + ".tmp"), os.path.join(q, rec["id"] + ".json"))
            return True
        except OSError:
            return False

    def sonia_window(self):
        if getattr(self, "_sonia_w", None) is not None and self._sonia_w.winfo_exists():
            self._sonia_w.lift()
            return
        px = self.px
        info = self._sonia_books()
        books = sorted((info.get("books") or {}).items(), key=lambda kv: str(kv[1].get("name")).lower())
        st = info.get("set") or {}
        w = self._sonia_w = tk.Toplevel(self.root)
        w.title("Archie · Sonia audio")
        w.configure(bg=BG)
        w.attributes("-topmost", True)
        w.geometry(f"{px(560)}x{px(560)}")
        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(4)))
        tk.Label(top, text="SONIA AUDIO", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        tk.Label(top, text="  your PC makes it (online), Feather plays it offline", bg=BG, fg=MUTED, font=(MONO, 8)).pack(side="left")
        if not books:
            tk.Label(w, text="No books from Feather's Reading yet. Open Feather on your phone or a laptop once\n(its sync tells Archie which books there are), then open this again.",
                     bg=BG, fg=BODY, font=(MONO, 9), justify="left").pack(anchor="w", padx=px(14), pady=px(12))
            return
        tk.Label(w, text="BOOK", bg=BG, fg=MUTED, font=(MONO, 8)).pack(anchor="w", padx=px(14), pady=(px(8), 0))
        lb = tk.Listbox(w, bg=SURFACE, fg=TEXT, selectbackground=ACCENT, selectforeground=TILE, bd=0, highlightthickness=1,
                        highlightbackground=BORDER, font=(MONO, 10), height=7, exportselection=False)
        for rid, b in books:
            lb.insert("end", f"{b.get('name')}  ·  {b.get('pages')} ch.")
        lb.selection_set(0)
        lb.pack(fill="x", padx=px(14), pady=px(4))
        row = tk.Frame(w, bg=BG)
        row.pack(fill="x", padx=px(14), pady=px(6))
        whole = tk.BooleanVar(value=False)
        fr_v, to_v = tk.StringVar(value="1"), tk.StringVar(value="3")
        tk.Label(row, text="chapters", bg=BG, fg=MUTED, font=(MONO, 9)).pack(side="left")
        for var, lab in ((fr_v, None), (to_v, "to")):
            if lab:
                tk.Label(row, text=lab, bg=BG, fg=MUTED, font=(MONO, 9)).pack(side="left", padx=px(4))
            tk.Entry(row, textvariable=var, width=5, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0, font=(MONO, 10),
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT).pack(side="left", padx=px(4), ipady=px(2))
        tk.Checkbutton(row, text="whole book", variable=whole, bg=BG, fg=BODY, selectcolor=SURFACE, activebackground=BG,
                       activeforeground=TEXT, font=(MONO, 9)).pack(side="left", padx=px(12))
        row2 = tk.Frame(w, bg=BG)
        row2.pack(fill="x", padx=px(14), pady=px(2))
        tk.Label(row2, text="send to", bg=BG, fg=MUTED, font=(MONO, 9)).pack(side="left")
        ph, lp = tk.BooleanVar(value=True), tk.BooleanVar(value=True)
        for var, t in ((ph, "phone"), (lp, "laptops")):
            tk.Checkbutton(row2, text=t, variable=var, bg=BG, fg=BODY, selectcolor=SURFACE, activebackground=BG,
                           activeforeground=TEXT, font=(MONO, 9)).pack(side="left", padx=px(6))
        msg = tk.Label(w, text="", bg=BG, fg=ACCENT, font=(MONO, 9), justify="left", anchor="w")

        def make():
            sel = lb.curselection()
            if not sel:
                return
            rid, b = books[sel[0]]
            n = int(b.get("pages") or 1)
            try:
                fr, to = (0, n - 1) if whole.get() else (max(1, int(fr_v.get())) - 1, min(n, int(to_v.get())) - 1)
            except ValueError:
                msg.configure(text="Chapters are numbers, like 3 to 10.", fg=MUTED)
                return
            devs = [d for d, v in (("phone", ph), ("laptops", lp)) if v.get()]
            if not devs:
                msg.configure(text="Tick the phone or the laptops.", fg=MUTED)
                return
            ok = self.sonia_ask(rid=rid, fr=fr, to=max(fr, to), devs=devs)
            msg.configure(text=(f"Asked for {b.get('name')}, ch. {fr + 1}–{max(fr, to) + 1}. Your PC starts at the next sync with Feather\n"
                                "and sends it to your " + " and ".join(devs) + ".") if ok else "Couldn't queue that.", fg=ACCENT if ok else MUTED)
        tk.Button(w, text="Make it with Sonia", command=make, bg=ACCENT, fg=TILE, activebackground=ACCENT_HI, bd=0,
                  font=(MONO, 10, "bold"), cursor="hand2").pack(fill="x", padx=px(14), pady=(px(10), px(4)), ipady=px(6))
        msg.pack(fill="x", padx=px(14))
        tk.Label(w, text="PLAYBACK (SAVED IN FEATHER: THE SAME ON THE PHONE AND LAPTOPS)", bg=BG, fg=MUTED, font=(MONO, 8)).pack(anchor="w", padx=px(14), pady=(px(12), 0))
        sp = tk.Scale(w, from_=0.6, to=2.0, resolution=0.05, orient="horizontal", label="speed", bg=BG, fg=BODY, troughcolor=SURFACE,
                      highlightthickness=0, bd=0, activebackground=ACCENT, font=(MONO, 8))
        sp.set(float(st.get("speed") or 1.0))
        sp.pack(fill="x", padx=px(14))
        vo = tk.Scale(w, from_=0, to=100, resolution=5, orient="horizontal", label="volume %", bg=BG, fg=BODY, troughcolor=SURFACE,
                      highlightthickness=0, bd=0, activebackground=ACCENT, font=(MONO, 8))
        vo.set(int(round(100 * float(1.0 if st.get("vol") is None else st["vol"]))))
        vo.pack(fill="x", padx=px(14))
        sp.bind("<ButtonRelease-1>", lambda e: self.sonia_ask(setting={"speed": float(sp.get())}))
        vo.bind("<ButtonRelease-1>", lambda e: self.sonia_ask(setting={"vol": int(vo.get()) / 100.0}))
        voices = [("en-GB-SoniaNeural", "Sonia · British woman"), ("en-GB-LibbyNeural", "Libby · British woman"), 
                  ("en-GB-RyanNeural", "Ryan · British man"), ("en-GB-ThomasNeural", "Thomas · British man"), ("en-IE-EmilyNeural", "Emily · Irish woman"),
                  ("en-IE-ConnorNeural", "Connor · Irish man"), ("en-AU-NatashaNeural", "Natasha · Australian woman"), ("en-AU-WilliamNeural", "William · Australian man")]
        vrow = tk.Frame(w, bg=BG)
        vrow.pack(fill="x", padx=px(14), pady=(px(4), 0))
        tk.Label(vrow, text="voice for new chapters", bg=BG, fg=MUTED, font=(MONO, 9)).pack(side="left")
        voices += [(a["v"], a["name"]) for a in info.get("accents") or []]
        vv = tk.StringVar(value=dict(voices).get(st.get("voice") or "en-GB-SoniaNeural", voices[0][1]))
        om = tk.OptionMenu(vrow, vv, *[n for _, n in voices], command=lambda n: self.sonia_ask(setting={"voice": next(v for v, x in voices if x == n)}))
        om.configure(bg=SURFACE, fg=TEXT, activebackground=INPUT_BG, activeforeground=TEXT, bd=0, highlightthickness=0, font=(MONO, 9))
        om["menu"].configure(bg=SURFACE, fg=TEXT, font=(MONO, 9))
        om.pack(side="left", padx=px(8))
        nv = tk.BooleanVar(value=st.get("night") is not False)
        tk.Checkbutton(w, text="overnight: record my next 3 chapters of what I'm reading, each night (accent voices are made overnight)",
                       variable=nv, command=lambda: self.sonia_ask(setting={"night": bool(nv.get())}), bg=BG, fg=BODY, selectcolor=SURFACE,
                       activebackground=BG, activeforeground=TEXT, font=(MONO, 8), anchor="w", wraplength=px(520), justify="left").pack(fill="x", padx=px(14))
        stat = tk.Label(w, text="", bg=BG, fg=MUTED, font=(MONO, 8), justify="left", anchor="w")
        stat.pack(fill="x", padx=px(14), pady=px(8))

        def tick():
            if not w.winfo_exists():
                return
            i2 = self._sonia_books()
            names = {k: v.get("name") for k, v in (i2.get("books") or {}).items()}
            made = "  ·  ".join(f"{names.get(k, k)}: {len(v)} ch." for k, v in (i2.get("made") or {}).items() if v) or "nothing made yet"
            stat.configure(text=(f"Making {i2['left']} chapter(s) now.\n" if i2.get("left") else "")
                           + (f"{i2['night_left']} chapter(s) waiting for tonight (accent voice).\n" if i2.get("night_left") else "")
                           + ("Making a chapter in an accent voice now: Archie will be slower until it's done.\n" if i2.get("accent_now") else "") + (f"{i2['err']}\n" if i2.get("err") else "") + "Made: " + made)
            w.after(5000, tick)
        tick()

    def note_to_feather(self, text):
        """A note into Feather's quick notes on every device (your PC adds it at the next sync). Each note goes once."""
        import uuid
        text = (text or "").strip()
        if not text:
            return None
        q = os.path.join(os.path.dirname(APP_DIR), "Feather", "notes_in")
        try:
            os.makedirs(q, exist_ok=True)
            rid = "an" + uuid.uuid4().hex[:12]
            tmp = os.path.join(q, rid + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"id": rid, "t": time.time(), "text": text[:20000]}, f)
            os.replace(tmp, os.path.join(q, rid + ".json"))
            return rid
        except OSError:
            return None

    def feather_xfer(self, op, deck, **extra):
        """Move a set between Archie and Feather, only when asked. a2f: this set replaces Feather's copy.
        f2a: Feather's set replaces this one. Your PC does it at the next sync with a Feather device; the old copy is kept."""
        import uuid
        ob = os.path.join(STUDY_DIR, ".feather_outbox")
        try:
            os.makedirs(ob, exist_ok=True)
            rid = "a" + uuid.uuid4().hex[:12]
            tmp = os.path.join(ob, rid + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(dict(extra, id=rid, op=op, deck=deck, t=time.time()), f)
            os.replace(tmp, os.path.join(ob, rid + ".json"))
        except OSError as e:
            self._write(f"Couldn't queue that: {e}\n", "sys")
            return
        if op == "restore":
            self._write(f"Putting back that version of “{deck}” at the next sync with your phone or a laptop "
                        "(what it replaces goes into the history too).\n", "sys")
        elif op == "a2f":
            self._write(f"Sending “{deck}”{' (a clean copy)' if extra.get('clean') else ''} to Feather. It replaces Feather's copy at the next sync with your phone or a "
                        "laptop (the old one is kept as a backup).\n", "sys")
        elif extra.get("kind") == "exam":
            self._write(f"Asking Feather for the exam “{deck}”. It lands here at the next sync with your phone or a laptop "
                        "(Archie's old copy is kept; type  shelf history  to put it back).\n", "sys")
        elif self.study.load(deck) or self.study.find_deck(deck):
            self._write(f"Asking Feather for “{deck}”. It replaces Archie's copy at the next sync with your phone or a "
                        "laptop (the old one goes to Study\\Backups).\n", "sys")
        else:
            self._write(f"Asking Feather for “{deck}”. It shows up here at the next sync with your phone or a laptop.\n", "sys")

    def list_decks(self):
        decks = self.study.decks()
        fd = self._feather_sets()
        if not decks and not fd:
            self._write("No flashcard decks yet. Try: make flashcards about photosynthesis, or "
                        "make flashcards from this note.\n", "sys")
            return
        today = datetime.date.today().isoformat()
        key = lambda n: " ".join(str(n).split()).lower()
        fk = {key(n): (n, x) for n, x in fd.items()}
        self._w("Your decks:\n", "sys")
        for d in decks:
            due = sum(1 for c in d["cards"] if c.get("last") and c.get("due", "") <= today)
            new = sum(1 for c in d["cards"] if not c.get("last"))
            f = fk.get(key(d["name"]))
            if not f:
                st = "not in Feather yet"
            elif not f[1].get("linked"):
                st = "Feather has a set with this name"
            elif f[1].get("fnewer"):
                st = "Feather has a newer version"
            else:
                st = "in Feather"
            self._w(f"{d['name']}: {len(d['cards'])} cards ({due} due, {new} new) · {st}   ", "sys")
            self._link("send to Feather", lambda n=d["name"]: self.feather_xfer("a2f", n), "sys")
            self._w("  ", "sys")
            self._link("clean copy", lambda n=d["name"]: self.feather_xfer("a2f", n, clean=True), "sys")
            if f:
                self._w("   ", "sys")
                self._link("get Feather's", lambda n=f[0]: self.feather_xfer("f2a", n), "sys")
            self._w("\n", "sys")
        mine = {key(d["name"]) for d in decks}
        only = sorted(n for k, (n, x) in fk.items() if k not in mine)
        if only:
            self._w("Only in Feather:\n", "sys")
            for n in only:
                self._w(f"{n}: {fd[n].get('n', 0)} cards   ", "sys")
                self._link("request", lambda n=n: self.feather_xfer("f2a", n), "sys")
                self._w("\n", "sys")
        self._write("Type  study  for everything due, or  study <deck name>.  Or:  send <deck> to feather  ·  "
                    "get <deck> from feather  ·  shelf history  ·  note to feather: <text>.\n", "sys")

    def shelf_history(self):
        """Every version a send or get replaced, with put it back."""
        try:
            with open(os.path.join(STUDY_DIR, ".feather_history"), encoding="utf-8") as f:
                hist = list(reversed(json.load(f)))
        except (OSError, ValueError):
            hist = []
        if not hist:
            self._write("Nothing replaced yet. When a send or get replaces a set, the old version shows up here.\n", "sys")
            return
        self._w("History (newest first):\n", "sys")
        for h in hist[:30]:
            when = datetime.datetime.fromtimestamp(h.get("t", 0)).strftime("%b %d %H:%M")
            side = "Archie's" if h.get("side") == "archie" else "Feather's"
            what = f"mock exam · {h.get('n', 0)} questions" if h.get("kind") == "exam" else f"{h.get('n', 0)} cards"
            self._w(f"{h.get('name')} · {side} copy · {what} · {when}   ", "sys")
            self._link("put it back", lambda h=h: self.feather_xfer("restore", h.get("name"), hid=h.get("id")), "sys")
            self._w("\n", "sys")

    # ----- Obsidian daily note + the note you have open ---------------------------

    def _sync_daily(self, quiet=False):
        """Two-way sync of your to-dos (and today's brief) with today's daily note."""
        if not self.cfg.get("daily_note", True) or not self.vault():
            return
        try:
            # 2026-11-08: the chat's morning brief stays out of Obsidian (only to-dos sync);
            # an empty list also clears a brief already in today's note
            changes = self.daily.sync(brief=[])
        except Exception as e:
            if not quiet:
                self._write(f"Couldn't update today's daily note: {e}\n", "sys")
            return
        if changes:
            self._write(f"From your daily note: {changes}.\n", "sys")

    def _daily_tick(self):
        if getattr(self, "_date_shown", None) != datetime.date.today():
            self._draw_date_chip()
        if self._recap_state == "idle":
            self._draw_recap_chip()
        self._sync_daily(quiet=True)
        self.root.after(90000, self._daily_tick)

    def _toggle_daily(self):
        self.cfg["daily_note"] = bool(self.daily_var.get())
        save_config(self.cfg)
        if self.cfg["daily_note"]:
            self._sync_daily()
            self._write("Your to-dos now go in today's Obsidian daily note "
                        "(in an \"Archie\" section). Type  daily  to open it.\n", "sys")

    def _recap_plan(self, rc):
        if self.busy:
            return
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", "From my recap last night, this is on my mind: " + "; ".join(rc.get("mind", [])) +
                          ". Help me make a simple, realistic plan for it.")
        self._entry_changed()
        self._send()

    def _brief_md(self):
        p = self._brief_parts
        lines = [f"### Morning brief · {datetime.date.today():%a %b %d}".replace(" 0", " ")]
        rc = self.recap.last_night()
        if rc and (rc.get("summary") or rc.get("mind")):
            link = f" ([[{obs.link_name(rc['note'])}]])" if rc.get("note") else ""
            lines.append(f"**Last night's recap:** {rc.get('summary', '')}{link}".rstrip())
            if rc.get("mind"):
                lines.append("- on your mind: " + "; ".join(rc["mind"][:3]))
        if p.get("chats"):
            lines.append("**Where you left off**")
            for title, summary in p["chats"]:
                lines.append(f"- {title}" + (f": {summary}" if summary else ""))
        if p.get("fresh"):
            lines.append(f"**New in your notes:** {p['fresh']}")
        if p.get("wiki"):
            title, para = p["wiki"]
            para = para if len(para) < 500 else para[:480].rsplit(" ", 1)[0] + "..."
            lines.append(f"**From your Wikipedia: {title}.** {para}")
        if p.get("cards"):
            rev, new = p["cards"]
            lines.append(f"**Flashcards:** {rev} due, {new} new (type `study` in Archie)")
        if p.get("quiz"):
            q, a, src = p["quiz"]
            lines += [f"> [!question]- Quick question: {q}", f"> {a} *(from {src})*"]
        return lines

    def open_daily(self):
        vault = self.vault()
        if not vault:
            self._write("Set your Obsidian vault first: right-click the owl > Choose Obsidian vault...\n", "sys")
            return
        self._sync_daily()
        rel = os.path.relpath(self.daily.path(), vault).replace("\\", "/")
        obs.open_in_obsidian(vault, rel)
        self._write(f"Opened today's daily note ({rel}).\n", "sys")

    def _log_entry(self, entry):
        try:
            self.daily.log(entry)
            self._write("Logged in today's daily note.\n", "sys")
        except Exception as e:
            self._write(f"Couldn't log that: {e}\n", "sys")

    # ----- talking: Archie speaks, and you can ask by voice ---------------------

    def _get_speaker(self, quiet=False):
        if self.speaker is None:
            if self._new_voice_ok():
                self.speaker = talk.KokoroSpeaker(lambda: self.cfg, quiet=self._quiet_now, on_caption=self._on_caption,
                                                  on_error=lambda m: self.bg_q.put(("voice_error", m)),
                                                  on_idle=lambda: self.bg_q.put(("call", self._voice_idle)), app_dir=APP_DIR)
                self.speaker.warm()
            else:
                self.speaker = Speaker(PIPER_DIR, self.cfg.get("speech_voice"), self.cfg.get("speech_speed"),
                                       on_error=lambda m: self.bg_q.put(("voice_error", m)))
        why = self.speaker.ready()
        if why:
            if not quiet:
                self._write(why + "\n", "sys")
            return None
        return self.speaker

    def _get_transcriber(self):
        if self.transcriber is None:
            self.transcriber = Transcriber(VOICE_MODELS_DIR, self.cfg.get("voice_model"),
                                           self.cfg.get("voice_device"))
        return self.transcriber

    def toggle_speak(self):
        if not self.cfg.get("speak_answers"):
            if not self._get_speaker():
                return
            self.cfg["speak_answers"] = True
            self._write("I'll read my answers out loud. Click speak again to stop that.\n", "sys")
        else:
            self.cfg["speak_answers"] = False
            if self.speaker:
                self.speaker.stop()
        save_config(self.cfg)
        self._style_speak_btn()

    def _style_speak_btn(self):
        on = bool(self.cfg.get("speak_answers"))
        self.speak_btn._on = on
        muted = self._quiet_now() if talk else False
        self.speak_btn.configure(text=f"speak {'●' if on else '○'}" + (" · muted" if muted else ""), fg=ACCENT if on else DIM,
                                 highlightbackground=ACCENT if on else BORDER,
                                 highlightcolor=ACCENT if on else BORDER)

    def speak_text(self, text):
        if self._quiet_now() and not (talk and self._new_voice_ok()):
            self._update_status("muted: Ctrl+Alt+Q to unmute")
            return
        sp = self._get_speaker()
        if sp:
            sp.say(text)

    def stop_speaking(self):
        if self.speaker:
            self.speaker.stop()

    def set_voice(self, name):
        self.cfg["speech_voice"] = name
        save_config(self.cfg)
        if self.speaker:
            self.speaker.stop()
        self.speaker = None
        sp = self._get_speaker()
        if sp:
            sp.say(f"Hi, I'm Archie. This is how I sound.")

    def set_speech_speed(self, speed):
        self.cfg["speech_speed"] = speed
        save_config(self.cfg)
        if self.speaker:
            self.speaker.speed = speed
            self.speaker.say("This is my new speed.")

    def _fill_voice_menu(self):
        m = self.voice_menu
        m.delete(0, "end")
        if self._new_voice_ok():
            self.voice_choice.set(self.cfg.get("voice_id") or talk.DEFAULT_VOICE_ID)
            for v in talk.VOICES:
                if v.get("accent"):
                    continue
                m.add_radiobutton(label=v["name"], variable=self.voice_choice, value=v["id"],
                                  command=lambda n=v["id"]: self._pick_new_voice(n))
            m.add_separator()
            m.add_command(label="Voice & quiet settings...", command=lambda: self.open_voice_settings())
            return
        found = [v for v in VOICES if os.path.exists(os.path.join(PIPER_DIR, v + ".onnx"))]
        for v in found:
            m.add_radiobutton(label=VOICES[v], variable=self.voice_choice, value=v,
                              command=lambda n=v: self.set_voice(n))
        if not found:
            m.add_command(label="(run Tools\\Get Voice.bat to download voices)", state="disabled")
        m.add_separator()
        for label, sp in (("Slower", 0.85), ("Normal speed", 1.0), ("Faster", 1.2)):
            m.add_radiobutton(label=label, variable=self.speed_choice, value=str(sp),
                              command=lambda s=sp: self.set_speech_speed(s))

    def toggle_talk(self):
        """Ctrl+Alt+T: talk mode (hands-free). Falls back to press-to-talk if talk mode can't start."""
        if self.talk_win is not None and self.talk_win.alive():
            if self.recorder.recording and self._rec_kind == "talk":
                self.recorder.stop()
                self._style_mic()
            return self.talk_end()
        if self.recorder.recording and self._rec_kind in ("talk", "recap", "note"):
            return self._toggle_talk_ptt()
        if talk and self.cfg.get("talk_handsfree", True) and self.talk_start():
            return
        return self._toggle_talk_ptt()

    def _toggle_talk_ptt(self):
        """Press to start listening, press again to send (the old way; also talk mode's fallback)."""
        if self.recorder.recording and self._rec_kind == "recap":
            self.show_recap()
            return
        if self.recorder.recording:
            if self._rec_kind != "talk":
                self._write("Finish the voice note first (click stop).\n", "sys")
                return
            path, secs = self.recorder.stop()
            self._style_mic()
            if not path:
                self._update_status()
                return
            self.status.configure(text="catching what you said...")
            tr = self._get_transcriber()

            def work():
                self._fg_transcribing = True
                try:
                    text = tr.transcribe(path)
                    self.bg_q.put(("talk_done", text))
                except VoiceError as e:
                    self.bg_q.put(("voice_error", str(e)))
                except Exception as e:
                    self.bg_q.put(("voice_error", f"Couldn't catch that: {e}"))
                finally:
                    self._fg_transcribing = False
                    try:
                        os.remove(path)          # quick questions aren't kept
                    except OSError:
                        pass
            threading.Thread(target=work, daemon=True).start()
            return
        self.stop_speaking()
        if not self.panel_visible():
            self.show_panel()
        try:
            self.recorder.start()
        except VoiceError as e:
            self._write(str(e) + "\n", "sys")
            return
        self._rec_kind = "talk"
        self._rec_blink = False
        self.status.configure(text=f"listening... {pretty_combo(self.cfg.get('hotkey_talk') or '')} "
                                   "again to send")
        self._style_mic()
        self._rec_tick()

    def _talk_done(self, text):
        self._update_status()
        text = (text or "").strip()
        if not text:
            self._write("I didn't catch any words. Try again a little closer to the mic.\n", "sys")
            return
        if self.busy:
            self._stop()
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", text)
        self._talk_pending = True
        self._send()
        self._entry_changed()

    # ----- the new voice, talk mode and Quiet (archie_talk.py) ----------------

    def save_cfg(self):
        save_config(self.cfg)

    def _new_voice_ok(self):
        return (talk is not None and self.cfg.get("voice_engine", "kokoro") != "piper"
                and talk.kokoro_ready(APP_DIR) is None)

    def _quiet_now(self):
        return bool(self.quiet and self.quiet.is_quiet())

    def _prompt_for_send(self):
        p = self.build_system_prompt()
        if self._talk_mode_send and talk and self.cfg.get("talk_spoken", True):
            p += "\n\n" + talk.SPOKEN_STYLE
        return p

    def _on_caption(self, text, secs, audible):        # from the voice's thread
        self.bg_q.put(("call", lambda: self._show_caption(text, secs, audible)))

    def _show_caption(self, text, secs, audible):
        tw = self.talk_win
        if tw is not None and tw.alive():
            tw.caption(text)
            tw.set_state("speaking")
            return
        if self.panel_visible():
            return                                    # the chat already shows it
        try:
            if self.caption_pop is None:
                self.caption_pop = talk.CaptionPop(self)
            self.caption_pop.show(text, secs, audible)
        except Exception as e:
            print("caption:", e)

    def _voice_idle(self):
        self._spoke_at = time.time()
        if self.caption_pop is not None:
            self.caption_pop.done()
        tw = self.talk_win
        if tw is not None and tw.alive() and not self.busy:
            tw.set_state("listening")

    def _pick_new_voice(self, vid):
        self.cfg["voice_id"] = vid
        save_config(self.cfg)
        self.voice_preview(vid)

    def voice_preview(self, vid=None):
        sp = self._get_speaker()
        if sp and talk and isinstance(sp, talk.KokoroSpeaker):
            sp.say("Hi, I'm Archie. This is how I sound. Shall we get started?", audible=True, voice_id=vid)

    def voice_say(self, text):
        sp = self._get_speaker()
        if sp and talk and isinstance(sp, talk.KokoroSpeaker):
            sp.say(text, audible=True)

    def voice_brief(self):
        now = datetime.datetime.now()
        part = "morning" if now.hour < 12 else "afternoon" if now.hour < 18 else "evening"
        line = f"Good {part}. It's {now:%A, %B} {now.day}."
        try:
            up = self.calendar.upcoming(days=7)
            if up:
                line += " Coming up: " + cal.describe(up[0]) + "."
        except Exception:
            pass
        try:
            due = self.study.due_count() if hasattr(self.study, "due_count") else 0
            if due:
                line += f" You've got {due} flashcards due."
        except Exception:
            pass
        self.voice_say(line + " What would you like to start with?")

    def open_voice_settings(self, tab="voice"):
        if not talk:
            return
        if self.quiet:
            self.quiet.refresh(force=True)
        w = self.voice_settings_win
        if w is not None and w.alive():
            w.lift(tab)
            return
        self.voice_settings_win = talk.VoiceSettings(self, tab)
        if self._new_voice_ok() is False and talk.kokoro_ready(APP_DIR):
            self._write(talk.kokoro_ready(APP_DIR) + "\n", "sys")

    def toggle_mic(self):
        """The mic key: in talk, Archie stops hearing you until it's pressed again (your headphones' mute, but faster)."""
        key = pretty_combo(self.cfg.get("hotkey_mic") or "alt+m")
        hf, tw = self.handsfree, self.talk_win
        if hf is None or tw is None or not tw.alive():
            self.bg_q.put(("status", f"{key} turns your mic off while talk is open."))
            return
        hf.mic_off = not getattr(hf, "mic_off", False)
        msg = f"Mic off: I'm not listening. {key} turns it back on." if hf.mic_off else "Mic on: I'm listening."
        try:
            tw.hint.configure(text=msg)
        except Exception:
            pass
        self.bg_q.put(("status", msg))

    def toggle_quiet(self):
        if not talk:
            return
        self.cfg["quiet"] = not self.cfg.get("quiet")
        save_config(self.cfg)
        muted = self._quiet_now()
        if muted and self.speaker is not None and isinstance(self.speaker, talk.KokoroSpeaker):
            self.speaker.mute_now()              # silence now; the rest of the answer carries on as captions
        elif muted and self.speaker is not None:
            self.speaker.stop()                  # silence now, including sentences already handed to the voice
            if not isinstance(self.speaker, talk.KokoroSpeaker):
                self._speak_now = False          # the old voice can't do captions: the rest of this answer stays silent
        self._style_speak_btn()
        q, why = self.quiet.state()
        self._update_status("muted: captions instead of sound (Ctrl+Alt+Q to unmute)" if q else "sound back on")
        if self.talk_win is not None and self.talk_win.alive():
            self.talk_win.set_muted(q, why)
        if self.voice_settings_win is not None and self.voice_settings_win.alive() and self.voice_settings_win.tab == "quiet":
            self.voice_settings_win.show("quiet")
        if not self.panel_visible():
            try:
                if self.caption_pop is None:
                    self.caption_pop = talk.CaptionPop(self)
                self.caption_pop.show("Muted. I'll show my words here instead." if q else "Sound's back on.", 1.5, not q)
                self.caption_pop.done()
            except Exception:
                pass

    def _quiet_tick(self):
        """Every few seconds: if Quiet just came on by itself (headphones out, library Wi-Fi), go silent now."""
        try:
            if self.quiet:
                sp = self.speaker
                speaking = sp is not None and getattr(sp, "speaking", None) is not None \
                    and (sp.speaking.is_set() or getattr(sp, "_pending", 0) > 0)
                self.quiet.refresh(every=4 if speaking and self.cfg.get("quiet_headphones_only") else 20)
                q, why = self.quiet.state()
                if q != getattr(self, "_was_quiet", None):
                    self._was_quiet = q
                    self._style_speak_btn()
                    if self.talk_win is not None and self.talk_win.alive():
                        self.talk_win.set_muted(q, why)
                if q and speaking and not getattr(sp, "force_audible", False):
                    if not isinstance(sp, talk.KokoroSpeaker):
                        sp.stop()
                        self._speak_now = False
                        raise StopIteration
                    if getattr(sp, "_pending", 0) > 0:     # sound still going out: the rest carries on as captions
                        sp.mute_now()
        except StopIteration:
            pass
        except Exception as e:
            print("quiet tick:", e)
        self.root.after(3000, self._quiet_tick)

    # talk mode -----------------------------------------------------------------

    def talk_start(self):
        sp = self._get_speaker(quiet=True)
        if sp is None:
            return False
        try:
            self._get_transcriber()
        except Exception:
            return False
        if self.recorder.recording:
            return False
        self.talk_win = talk.TalkWindow(self)
        cool.STATE["talk"] = True          # background AI (World, exam prep) waits while you talk
        voice = (talk.VOICE_BY_ID.get(self.cfg.get("voice_id") or "") or {}).get("name", "Archie") \
            if isinstance(sp, talk.KokoroSpeaker) else "the old voice"
        self.talk_win.set_head(f"{self.cfg.get('mode') or 'General'}  ·  voice: {voice}")
        q, why = self.quiet.state() if self.quiet else (False, "")
        if q:
            self.talk_win.set_muted(True, why)
        self.handsfree = None
        self.qt_hist, self._qt_job, self._qt_spec = [], None, None
        self._qt_started = datetime.datetime.now().strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
        self._qt_warm()
        if isinstance(sp, talk.KokoroSpeaker):
            sp.warm()
        if self.cfg.get("talk_handsfree", True):
            try:
                hf = talk.HandsFree(self._qt_utterance, lambda: self.bg_q.put(("call", self._talk_barge)),
                                    on_level=self._talk_level, is_speaking=self._archie_talking,
                                    folder=os.path.join(APP_DIR, "Recordings"), on_pause=self._qt_pause, on_resume=self._qt_resume,
                                    sens=lambda: self.cfg.get("talk_mic", 1.0))
                hf.start()
                self.handsfree = hf
            except Exception as e:
                self.talk_win.hint.configure(text=f"The mic couldn't start ({e}). Press space to talk instead.")
        if self.handsfree is None:
            self.talk_win.set_paused(True)
        self.talk_win.w.focus_force()
        return True

    # ----- quick talk: talk mode's own fast path (no chat panel, no lookups unless asked, model kept loaded) -----
    QT_LOOK = re.compile(r"\b(?:check|search|look in|in) (?:my )?notes\b|\blook (?:it|that|this) up\b|\bwikipedia\b|\bsearch (?:for|the wiki)\b", re.I)

    QT_SCHED = re.compile(r"\b(calendar|schedule|today|tonight|tomorrow|this week|next week|weekend|monday|tuesday|wednesday|thursday|"
                          r"friday|saturday|sunday|plans?|planned|coming up|what do i have|what have i got|class(es)?|exams?|due|deadlines?|"
                          r"homework|appointments?|meetings?|events?|tasks?|to-?do|busy|free)\b", re.I)
    QT_FILES = re.compile(r"\b(file|files|pdf|document|doc|picture|photo|image|scan|screenshot|snip|added|uploaded|dropped|inbox|"
                          r"lecture|recording|notes?|that thing i|the one i)\b", re.I)
    QT_CMD = re.compile(r"^\W*(?:please\s+)?(?:add|put|schedule|move|cancel|delete|remove|reschedule|remind me|set a reminder|"
                        r"deadline:|make (?:me )?(?:some |a )?(?:flashcards|cards|a mock exam|an exam|a quiz)|note to feather|send .+ to feather|"
                        r"make sonia audio|save (?:this|that) to obsidian)\b", re.I)
    QT_STOP = set("the and for with that this what when where which about have your from they them then there their just like "
                  "know does dont want tell show give make could would should will into were been being also some more much".split())

    QT_OPEN = re.compile(r"\b(how should|help me|should i|plan(?:ning)? (?:my|the|out)|why|advice|ideas?|prioriti[sz]e|organi[sz]e|"
                         r"what's the best|balance|stress|overwhelm)\b", re.I)
    QT_ASK = re.compile(r"\b(what(?:'s| is| do i have| have i got| am i doing)|anything|do i have|have i got|am i (?:busy|free)|"
                        r"is there|what's on|whats on|what is on|coming up|due|to-?dos?|tasks?|deadlines?|schedule|calendar|plans?)\b", re.I)

    def _qt_clean(self, t):
        t = re.sub(r"\(\s*\)", "", str(t))
        return " ".join(t.replace(" ,", ",").split()).strip(" ,;")

    def _qt_say_day(self, d):
        n = d.day
        suf = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        today = datetime.date.today()
        if d == today:
            return "Today"
        if d == today + datetime.timedelta(days=1):
            return "Tomorrow"
        return f"{d:%A}, {d:%B} {n}{suf}" + (f" {d.year}" if d.year != today.year and (d - today).days > 300 else "")

    def _qt_entries(self, d, dl, tasks):
        got = []
        try:
            for e in self.calendar.between(d, d):
                tm = f" at {cal.fmt_time(e['time'])}" if e.get("time") else ""
                got.append(self._qt_clean(e["title"]) + tm)
        except Exception:
            pass
        got += [self._qt_clean(x) + " (deadline)" for x in dl.get(d.isoformat(), [])]
        got += [self._qt_clean(t) + " (to-do)" for t, due in tasks if due == d.isoformat()]
        return got

    def _qt_sched_answer(self, text):
        """Plain schedule questions answered straight from Archie's calendar, deadlines and to-dos: exact, and instant."""
        if self.QT_OPEN.search(text):
            return None
        follow = bool(re.search(r"\b(what about|and|how about)\b.*\b(day after|next day|day before|that day|following day)\b|^\W*(the )?(day after|next day|day before)\b", text, re.I))
        if re.search(r"\b(phone|number|email|address|website|who|where is|how much|cost|price)\b", text, re.I) \
                and not re.search(r"\b(calendar|schedule|due|to-?do|tasks?|deadlines?)\b", text, re.I):
            return None                                  # a question about something else that happens to mention a day
        found = self._qt_find_entry(text)
        if found is not None:
            return found
        if not (self.QT_SCHED.search(text) or follow):
            return None
        days = self._qt_dates(text)
        low, today = text.lower(), datetime.date.today()
        dl = {}
        for line in read_small_text(DEADLINES_PATH).splitlines():
            m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+)", line)
            if m:
                dl.setdefault(m.group(1), []).append(m.group(2).strip())
        tasks = self._qt_tasks()
        if days:
            self._qt_lastdays = days
            busy = [(d, self._qt_entries(d, dl, tasks)) for d in days]
            withs = [(d, g) for d, g in busy if g]
            if not withs:
                if len(days) > 1:
                    return f"Nothing on the {days[0].day}{'th' if 11 <= days[0].day % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(days[0].day % 10, 'th')} for the next few months: those days are clear."
                return f"{self._qt_say_day(days[0])} is clear: nothing on your calendar, no deadlines, no to-dos."
            parts = [f"{self._qt_say_day(d)}: " + "; ".join(g) + "." for d, g in withs]
            clear = [d for d, g in busy if not g]
            if clear and len(days) == len(clear) + len(withs) and len(withs) < len(days) and len(days) <= 2:
                parts.append(f"{self._qt_say_day(clear[0])} is clear.")
            return " ".join(parts)
        if re.search(r"\b(to-?dos?|tasks?|due)\b", low) and not re.search(r"\b(calendar|schedule|week|coming up)\b", low):
            open_ = [(t, d) for t, d in tasks]
            if not open_:
                return "Your to-do list is clear."
            over = [t for t, d in open_ if d and d <= today.isoformat()]
            rest = [t for t, d in open_ if not d or d > today.isoformat()]
            out = []
            if over:
                out.append(f"Due today{' or overdue' if len(over) > 1 else ''}: " + "; ".join(self._qt_clean(t) for t in over) + ".")
            if rest:
                out.append("Also on your list: " + "; ".join(self._qt_clean(t) for t in rest[:6]) + ".")
            return " ".join(out)
        if not re.search(r"\b(calendar|schedule|week|coming up|soon|plans?|planned|busy|free|what do i have|what have i got|deadlines?)\b", low):
            return None                                  # not an overview question: let Archie answer normally
        span = 7
        lines = []
        for i in range(span + 1):
            d = today + datetime.timedelta(days=i)
            g = [x for x in self._qt_entries(d, dl, tasks) if not x.endswith("(to-do)") or i == 0]
            if g:
                lines.append(f"{self._qt_say_day(d)}: " + "; ".join(g) + ".")
        later = sorted((k, v) for k, v in dl.items() if (today + datetime.timedelta(days=span)).isoformat() < k <= (today + datetime.timedelta(days=90)).isoformat())
        if later:
            k, v = later[0]
            lines.append(f"Next deadline after that: {self._qt_clean(v[0])}, {self._qt_say_day(datetime.date.fromisoformat(k))}.")
        return " ".join(lines) if lines else "Your next week is clear: nothing on the calendar and no deadlines."

    def _qt_find_entry(self, text):
        """'Is the reminder about Sean on my calendar?' / 'When is the apartment visit?': look it up by its words."""
        low = text.lower()
        if not re.search(r"\b(is (?:the|my|a|there)|when(?:'s| is)|do i have (?:a|the|my)|did i (?:add|put|set)|on my (?:calendar|list|to-?do))\b", low):
            return None
        skip = self.QT_STOP | {"calendar", "reminder", "reminders", "schedule", "list", "todo", "to-do", "tasks", "task", "event", "events",
                               "today", "tomorrow", "week", "check", "there", "anything", "something", "deadline", "deadlines", "not", "set", "added",
                               "what's", "whats", "what", "this", "next", "coming", "have", "has", "got", "going", "any", "time", "date", "day"}
        words = [w for w in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", low) if w not in skip]
        if not words:
            return None
        today = datetime.date.today()
        hits = []
        try:
            for e in self.calendar.between(today - datetime.timedelta(days=7), today + datetime.timedelta(days=365)):
                if any(w in e["title"].lower() for w in words):
                    d = datetime.date.fromisoformat(e["date"]) if isinstance(e["date"], str) else e["date"]
                    hits.append(f"{self._qt_clean(e['title'])}, {self._qt_say_day(d)}" + (f" at {cal.fmt_time(e['time'])}" if e.get("time") else ""))
        except Exception:
            pass
        for line in read_small_text(DEADLINES_PATH).splitlines():
            m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+)", line)
            if m and any(w in m.group(2).lower() for w in words):
                hits.append(f"{self._qt_clean(m.group(2))} (deadline), {self._qt_say_day(datetime.date.fromisoformat(m.group(1)))}")
        for t, due in self._qt_tasks():
            if any(w in t.lower() for w in words):
                hits.append(f"{self._qt_clean(t)} (to-do" + (f", due {self._qt_say_day(datetime.date.fromisoformat(due))}" if due else "") + ")")
        if hits:
            return "Yes: " + "; ".join(hits[:4]) + "."
        return f"No, I don't see anything about {' '.join(words[:3])} on your calendar, deadlines or to-do list."

    NUMW = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
            "eleven": 11, "twelve": 12}

    def _qt_norm_time(self, text):
        """Spoken times into what the calendar reads: '9 o'clock a.m.' / 'nine a.m.' / 'half past three p.m.' -> 9am, 3:30pm;
        'noon' -> 12pm; 'from 9am' / 'at 9am' kept with the date, not the title."""
        t = text
        t = re.sub(r"\b(" + "|".join(self.NUMW) + r")\b(?=\s*(?:o'?\s*clock|[ap]\.?\s*m\b|thirty|fifteen|forty))",
                   lambda m: str(self.NUMW[m.group(1).lower()]), t, flags=re.I)
        t = re.sub(r"\bhalf past (\d{1,2})", r"\1:30", t, flags=re.I)
        t = re.sub(r"\bquarter past (\d{1,2})", r"\1:15", t, flags=re.I)
        t = re.sub(r"\b(\d{1,2})\s+(thirty|fifteen|forty[- ]?five)\b", lambda m: f"{m.group(1)}:{ {'thirty': '30', 'fifteen': '15'}.get(m.group(2).lower(), '45') }", t, flags=re.I)
        t = re.sub(r"\b(\d{1,2}(?::\d{2})?)\s*o'?\s*clock\b", r"\1", t, flags=re.I)
        t = re.sub(r"\b(\d{1,2}(?::\d{2})?)\s*([ap])\.?\s*m\b\.?", lambda m: m.group(1) + m.group(2).lower() + "m", t, flags=re.I)
        t = re.sub(r"\bnoon\b", "12pm", t, flags=re.I)
        t = re.sub(r"\bmidnight\b", "12am", t, flags=re.I)
        t = re.sub(r"\b(?:from|starting at|starting)\s+(\d{1,2}(?::\d{2})?[ap]m)\b", r"at \1", t, flags=re.I)
        return t

    def _qt_check_dates(self, answer, facts):
        """An open answer that names a date not in the user's entries gets the exact entries instead."""
        months = "january|february|march|april|may|june|july|august|september|october|november|december"
        said = re.findall(rf"\b({months})\s+(\d{{1,2}})", answer.lower())
        if not said or not facts:
            return answer
        ok = {(m, int(dd)) for m, dd in re.findall(rf"\b({months})\s+(\d{{1,2}})", facts.lower())}
        today = datetime.date.today()
        for k in range(0, 3):
            dd = today + datetime.timedelta(days=k)
            ok.add((dd.strftime("%B").lower(), dd.day))
        if all((m, int(dd)) in ok for m, dd in said):
            return answer
        exact = self._qt_sched_answer("what's on my calendar this week") or ""
        return "Let me read it straight from your calendar: " + exact

    def _qt_today(self):
        """A small 'today' card for every talk answer: date, time, today's events and what's due."""
        now = datetime.datetime.now()
        today = now.date()
        bits = [f"Right now it's {now:%A %B %d, %Y}, {now:%I:%M %p}".replace(" 0", " ") + "."]
        try:
            evs = self.calendar.between(today, today + datetime.timedelta(days=1))
            if evs:
                bits.append("Today/tomorrow on the user's Archie calendar: " + "; ".join(cal.describe(e, today) for e in evs[:6]) + ".")
        except Exception:
            pass
        due = [t for t in self._qt_tasks() if t[1] and t[1] <= today.isoformat()]
        if due:
            bits.append("Tasks due today or overdue: " + "; ".join(t[0] for t in due[:6]) + ".")
        return " ".join(bits)

    def _qt_tasks(self):
        out = []
        for line in read_small_text(TASKS_PATH).splitlines():
            m = re.match(r"\s*\[( |x)\]\s*(.+?)\s*(?:\|\s*(\d{4}-\d{2}-\d{2}))?\s*$", line)
            if m and m.group(1) == " ":
                out.append((m.group(2), m.group(3) or ""))
        return out

    ORD = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
           "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15, "sixteenth": 16, "seventeenth": 17,
           "eighteenth": 18, "nineteenth": 19, "twentieth": 20, "twenty-first": 21, "twenty first": 21, "twenty-second": 22,
           "twenty second": 22, "twenty-third": 23, "twenty third": 23, "twenty-fourth": 24, "twenty fourth": 24, "twenty-fifth": 25,
           "twenty fifth": 25, "twenty-sixth": 26, "twenty sixth": 26, "twenty-seventh": 27, "twenty seventh": 27, "twenty-eighth": 28,
           "twenty eighth": 28, "twenty-ninth": 29, "twenty ninth": 29, "thirtieth": 30, "thirty-first": 31, "thirty first": 31}
    MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

    def _qt_dates(self, text):
        """The days a question is about (today, tomorrow, Friday, the 8th, January 8...), worked out here, not by the model."""
        low, today = text.lower(), datetime.date.today()
        out = []

        def nxt_day(day, months=None):
            d, found = today, []
            for _ in range(400):
                if d.day == day and (months is None or d.month in months):
                    found.append(d)
                    if len(found) >= (1 if months else 3):
                        break
                d += datetime.timedelta(days=1)
            return found
        if re.search(r"\btoday\b|\btonight\b", low):
            out.append(today)
        if "tomorrow" in low:
            out.append(today + datetime.timedelta(days=1))
        for i, wd in enumerate(["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            if re.search(rf"\b{wd}\b", low):
                ahead = (i - today.weekday()) % 7 or (7 if "next" in low else 0)
                out.append(today + datetime.timedelta(days=ahead + (7 if "next" in low and ahead < 7 else 0)))
        month = next((n for m, n in self.MONTHS.items() if re.search(rf"\b{m}[a-z]*\b", low)), None)
        days = [int(x) for x in re.findall(r"\b(\d{1,2})(?:st|nd|rd|th)\b", low) if 1 <= int(x) <= 31]       # "the 8th", "8th"
        if month:
            days += [int(x) for x in re.findall(r"\b(\d{1,2})\b", low) if 1 <= int(x) <= 31]               # "January 8"
        days = list(dict.fromkeys(days))
        days += [n for w, n in self.ORD.items() if re.search(rf"\b{w}\b", low)]
        for day in days[:2]:
            out += nxt_day(day, {month} if month else None)
        last = getattr(self, "_qt_lastdays", None)
        if not out and last:                           # follow-ups: "the day after", "the day before", "that day"
            if re.search(r"\b(day after|next day|following day)\b", low):
                out = [last[-1] + datetime.timedelta(days=1)]
            elif re.search(r"\bday before\b", low):
                out = [last[0] - datetime.timedelta(days=1)]
            elif re.search(r"\b(that day|same day|then)\b", low):
                out = list(last)
        if out:
            self._qt_lastdays = sorted(set(out))[:6]
        return sorted(set(out))[:6]

    def _qt_day_facts(self, days):
        """Exactly what's on those days: Archie's calendar, deadlines and to-dos (nothing guessed)."""
        dl = {}
        for line in read_small_text(DEADLINES_PATH).splitlines():
            m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+)", line)
            if m:
                dl.setdefault(m.group(1), []).append(m.group(2).strip())
        tasks = self._qt_tasks()
        lines = []
        for d in days:
            got = []
            try:
                got += [cal.describe(e, datetime.date.today()) for e in self.calendar.between(d, d)]
            except Exception:
                pass
            got += ["Deadline: " + x for x in dl.get(d.isoformat(), [])]
            got += ["To-do due: " + t for t, due in tasks if due == d.isoformat()]
            lines.append(f"- {d:%A %B %d, %Y}: " + ("; ".join(got) if got else "nothing on the calendar, no deadlines, no to-dos"))
        return ("EXACT entries for the day(s) the user asked about. Answer from these lines only, keep each entry with its own date, "
                "and if a day says nothing, say it's clear:\n" + "\n".join(lines))

    def _qt_schedule(self):
        """Everything Archie keeps about the user's time: their Archie calendar, deadlines and to-do list."""
        today = datetime.date.today()
        lines = []
        try:
            for e in self.calendar.between(today, today + datetime.timedelta(days=120))[:25]:
                lines.append("- " + cal.describe(e, today))
        except Exception:
            pass
        dl = []
        for line in read_small_text(DEADLINES_PATH).splitlines():
            m = re.match(r"\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(.+)", line)
            if m and m.group(1) >= today.isoformat():
                dl.append(f"- {m.group(2).strip()} ({datetime.date.fromisoformat(m.group(1)):%a %b %d, %Y})")
        tasks = [f"- {t}" + (f" (due {d})" if d else "") for t, d in self._qt_tasks()]
        out = f"The user's own schedule, from Archie's calendar and lists (today is {today:%A %B %d, %Y}). Use it to answer; don't ask them what they have planned.\n"
        out += "Calendar, next 4 months (each line is one entry, with its own date):\n" + ("\n".join(lines) if lines else "- nothing on it") + "\n"
        out += "Deadlines:\n" + ("\n".join(dl) if dl else "- none") + "\n"
        out += "To-do list (not done yet):\n" + ("\n".join(tasks[:15]) if tasks else "- nothing")
        return out

    def _qt_files(self, text):
        """Files the user gave Archie: the recent ones, and a quick word search of what Archie read from them and their notes."""
        out = []
        try:
            idx = json.load(open(os.path.join(APP_DIR, "inbox_index.json"), encoding="utf-8"))
            rec = sorted(idx.values(), key=lambda v: v.get("date", ""), reverse=True)[:8]
            if rec:
                out.append("Files the user recently added to Archie:\n" + "\n".join(
                    f"- {os.path.basename(v.get('dest', ''))} ({v.get('kind') or 'file'}, {v.get('date', '')})" for v in rec))
        except (OSError, ValueError):
            pass
        if self.attachments:
            out.append("Attached in the current chat: " + ", ".join(os.path.basename(a) for a in self.attachments[:6]))
        words = {w for w in re.findall(r"[a-z0-9][a-z0-9'-]{3,}", text.lower()) if w not in self.QT_STOP}
        if words:
            hits = []
            try:
                for rel, f in (self.notes.data.get("files") or {}).items():
                    name = rel.lower()
                    for c in f.get("chunks", []):
                        low = c["text"].lower()
                        score = sum(low.count(w) for w in words) + 3 * sum(w in name for w in words)
                        if score >= 2:
                            hits.append((score, rel, c["text"]))
            except Exception:
                hits = []
            hits.sort(key=lambda h: -h[0])
            seen, picked = set(), []
            for sc, rel, txt in hits:
                if rel in seen:
                    continue
                seen.add(rel)
                picked.append(f"From {rel}:\n{txt[:900]}")
                if len(picked) >= 3:
                    break
            if picked:
                out.append("From the user's notes and the files Archie has read (a quick word search; use it if it fits):\n\n" + "\n\n".join(picked))
        return "\n\n".join(out)

    def _qt_is_cmd(self, text):
        """Something to DO (add to the calendar, a reminder, flashcards...): full Archie handles those."""
        try:
            if calchat.looks_like_edit(text, self.calendar) or cal.parse_event(text) or exam.parse_request(text):
                return True
        except Exception:
            pass
        return bool(self.QT_CMD.search(text))

    def _qt_model(self):
        if self.cfg.get("talk_fast_model") and self.cfg.get("talk_model") and not getattr(self, "_qt_model_missing", False):
            return self.cfg["talk_model"]
        return self.cfg["model"]

    def _qt_transcriber(self):
        if getattr(self, "_qt_tr", None) is None:
            dev = self.cfg.get("voice_device") or "cpu"
            name = self.cfg.get("talk_voice_model") or ("small.en" if dev == "cuda" else "base.en")
            have = os.path.isdir(os.path.join(VOICE_MODELS_DIR, "models--Systran--faster-whisper-" + name))
            self._qt_tr = Transcriber(VOICE_MODELS_DIR, name, dev) if have else self._get_transcriber()
        return self._qt_tr

    def _qt_warm(self):
        """Talk mode opened: load the speech model and the chat model now, so the first answer is quick."""
        def work():
            try:
                self._qt_transcriber()._load()
            except Exception:
                pass
            try:
                quick_chat(self._qt_model(), "Hi", max_tokens=1, timeout=120, num_ctx=int(self.cfg.get("context_tokens", 16384)),
                           system=self._qt_system(), keep_alive="30m")
            except ArchieError as e:
                if "not found" in str(e) and self._qt_model() != self.cfg["model"]:
                    self._qt_model_missing = True
                    self.bg_q.put(("call", lambda: self.talk_win and self.talk_win.alive() and self.talk_win.hint.configure(
                        text=f"The quick talk model ({self.cfg.get('talk_model')}) isn't downloaded: run Tools\\Get Fast Talk.bat. Using {self.nice(self.cfg['model'])} for now.")))
            except Exception:
                pass
        threading.Thread(target=work, daemon=True).start()

    def _qt_system(self):
        p = self.build_system_prompt()
        if self.cfg.get("talk_spoken", True):
            p += "\n\n" + talk.SPOKEN_STYLE
        return p

    def _qt_new_job(self, text, seq, commit):
        """Start an answer. Until it's committed, it's made quietly (you might still be talking)."""
        job = {"text": text, "seq": seq, "toks": [], "fed": 0, "done": False, "commit": False, "stop": threading.Event(),
               "err": None, "first_at": None}
        try:
            canned = self._qt_sched_answer(text)
        except Exception:
            canned = None
        if canned:                                        # straight from the calendar: exact, no model needed
            job.update(toks=[canned], done=True, first_at=time.time(), canned=True, notes=canned)
            if commit:
                self.bg_q.put(("call", lambda j=job: self._qt_commit(j)))
            return job
        checking = bool(self.QT_SCHED.search(text))       # schedule-ish open answers: checked before they're spoken
        hist = list(self.qt_hist[-16:])
        model = self._qt_model()
        system = [{"role": "system", "content": self._qt_system()}]
        extra = [self._qt_today() + " Never make up phone numbers, emails, addresses, prices or dates: if they're not in what you were given, "
                 "say you don't have it offline and suggest where to find it."]   # these go right next to the question
        try:
            days = self._qt_dates(text)
            if self.QT_SCHED.search(text) or days:
                extra.append(self._qt_schedule())
            if days:
                extra.append(self._qt_day_facts(days))
            if self.QT_FILES.search(text) or not self.QT_SCHED.search(text):
                f = self._qt_files(text)
                if f:
                    extra.append(f)
        except Exception:
            pass

        def run():
            q = queue.Queue()
            try:
                if self.QT_LOOK.search(text):          # asked for: one lookup, for this question only
                    try:
                        hits = self.notes.search(text, k=4) if "wiki" not in text.lower() else []
                        if hits:
                            system.append({"role": "system", "content": "Excerpts from the user's notes that may help:\n\n" +
                                           "\n\n".join(f"From {rel}:\n{txt}" for _, rel, txt in hits)})
                        if self.cfg.get("use_wiki") or "wiki" in text.lower() or "look" in text.lower():
                            arts = self.wiki.search(text)
                            if arts:
                                system.append({"role": "system", "content": "Excerpts from the user's offline Wikipedia:\n\n" +
                                               "\n\n".join(f"Wikipedia: {t}\n{x}" for t, x in arts)})
                    except Exception:
                        pass
                ctx = [{"role": "system", "content": "\n\n".join(extra)}]
                th = threading.Thread(target=lambda: self._qt_stream(model, system + hist + ctx + [{"role": "user", "content": text}], q, job), daemon=True)
                th.start()
                while True:
                    kind, val = q.get()
                    if kind == "token":
                        if checking:
                            job.setdefault("held", []).append(val)
                            continue
                        job["toks"].append(val)
                        if job["first_at"] is None:
                            job["first_at"] = time.time()
                        if job["commit"]:
                            self.bg_q.put(("call", lambda j=job: self._qt_flow(j)))
                    else:
                        if kind == "error":
                            job["err"] = val
                        break
            finally:
                if checking and job.get("held"):
                    job["toks"] = [self._qt_check_dates("".join(job["held"]), "\n".join(extra))]
                    job["first_at"] = job["first_at"] or time.time()
                job["done"] = True
                self.bg_q.put(("call", lambda j=job: self._qt_flow(j)))
        threading.Thread(target=run, daemon=True).start()
        if commit:
            self.bg_q.put(("call", lambda j=job: self._qt_commit(j)))
        return job

    def _qt_stream(self, model, msgs, q, job):
        """Like stream_chat, but a dropped early start is cut off at once (even while Ollama is still reading the
        prompt), so it never holds up the real answer behind it."""
        import urllib.request
        import urllib.error

        def run(m):
            body = json.dumps({"model": m, "messages": msgs, "stream": True, "keep_alive": "30m",
                               "options": {"num_ctx": int(self.cfg.get("context_tokens", 16384))}}).encode("utf-8")
            req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=body, headers={"Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=600)
            job["resp"] = resp
            if job["stop"].is_set():
                resp.close()
                return
            def watch():
                while not job["stop"].wait(0.2):
                    if job["done"] or job.get("streamed"):
                        return
                self._qt_close(resp)
            threading.Thread(target=watch, daemon=True).start()
            try:
                for raw in resp:
                    if job["stop"].is_set():
                        return
                    raw = raw.strip()
                    if not raw:
                        continue
                    data = json.loads(raw)
                    if "error" in data:
                        raise ArchieError(data["error"])
                    piece = data.get("message", {}).get("content", "")
                    if piece:
                        q.put(("token", piece))
                    if data.get("done"):
                        break
            finally:
                job["streamed"] = True
                self._qt_close(resp)
        try:
            try:
                run(model)
            except urllib.error.HTTPError as e:
                if e.code == 404 and model != self.cfg["model"]:       # quick model not downloaded: use the usual one
                    self._qt_model_missing = True
                    run(self.cfg["model"])
                else:
                    raise ArchieError(f"Ollama said {e.code}")
            q.put(("done", None))
        except Exception as e:
            q.put(("done", None) if job["stop"].is_set() else ("error", str(e)))

    def _qt_close(self, resp):
        try:
            resp.close()
        except Exception:
            pass

    def _qt_pause(self, seq, path):            # mic thread: a short pause, so start thinking quietly
        spec = {"seq": seq, "path": path, "ready": threading.Event(), "job": None, "text": "", "dead": False}
        self._qt_spec = spec
        try:
            spec["text"] = (self._qt_transcriber().transcribe(path, fast=True) or "").strip()
        except Exception:
            spec["text"] = ""
        if not spec["dead"] and re.search(r"[A-Za-z0-9]", spec["text"]) and not self._qt_is_bye(spec["text"]):
            old = getattr(self, "_qt_early", None)
            if old is not None and not old["commit"]:
                old["stop"].set()                    # only one early start at a time
            spec["job"] = self._qt_early = self._qt_new_job(spec["text"], seq, commit=False)
        spec["ready"].set()

    def _qt_resume(self, seq, path):           # you kept talking: drop the early start
        spec = getattr(self, "_qt_spec", None)
        if spec and spec["seq"] == seq:
            spec["dead"] = True
            if spec["job"]:
                spec["job"]["stop"].set()
            self._qt_spec = None

    def _qt_is_bye(self, text):
        return bool(re.fullmatch(r"\W*(stop|end talk( mode)?|that's all|goodbye|bye( archie)?)\W*", text, re.I))

    def _qt_utterance(self, path, seq):       # mic thread: you're done (0.8 s of quiet)
        spec = getattr(self, "_qt_spec", None)
        try:
            if spec and spec["seq"] == seq and not spec["dead"]:
                spec["ready"].wait(15)
                text, job = spec["text"], spec["job"]
            else:
                text, job = (self._qt_transcriber().transcribe(path, fast=True) or "").strip(), None
        except Exception as e:
            self.bg_q.put(("voice_error", f"Couldn't catch that: {e}"))
            return
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        if not re.search(r"[A-Za-z0-9]", text or ""):
            return
        if self._qt_is_bye(text):
            self.bg_q.put(("call", self.talk_end))
            return
        pend = getattr(self, "_qt_pending", None)
        if pend is not None:                 # answering "Add it?"
            self._qt_pending = None
            if re.match(r"\W*(yes|yeah|yep|yup|sure|do it|add it|go ahead|please|ok(ay)?|correct|right)\b", text, re.I):
                self.bg_q.put(("call", lambda p=pend: self._qt_do_add(p)))
                return
            if re.match(r"\W*(no|nope|nah|cancel|don'?t|never ?mind|stop)\b", text, re.I):
                self.bg_q.put(("call", lambda: self._qt_say("Okay, I won't add it.")))
                return
        try:
            text_t = self._qt_norm_time(text)
            ereq = cal.parse_event(text_t)
            if not ereq and re.match(r"\W*(?:please\s+)?(?:add|put|schedule)\b", text_t, re.I) and "calendar" not in text_t.lower():
                ereq = cal.parse_event(text_t.rstrip(" .!?") + " to my calendar")     # "add dentist Friday at 3:30"
            if not ereq:
                m = re.match(r"\W*(?:(?:please|can you|could you)\s+)?(?:set (?:a |me a )?reminder|remind me|add a reminder)\s*(?:for\s+|to\s+|that\s+)?(.+)", text_t, re.I)
                if m:
                    ereq = cal.parse_event("reminder: " + m.group(1))
                    if ereq:
                        ttl = re.sub(r"^(?:at\s+\d{1,2}(?::\d{2})?[ap]m\s+)?(?:to|that)\s+", "", ereq["title"], flags=re.I)
                        ereq["title"] = "Reminder: " + ttl[:1].upper() + ttl[1:]
        except Exception:
            ereq = None
        if ereq:                             # "add dentist Friday at 3": checked with you first
            d = ereq["date"] if isinstance(ereq["date"], datetime.date) else datetime.date.fromisoformat(str(ereq["date"]))
            tm = f" at {cal.fmt_time(ereq['time'])}" if ereq.get("time") else ""
            self._qt_pending = (ereq, text)
            dsay = self._qt_say_day(d)
            dsay = dsay.lower() if dsay in ("Today", "Tomorrow") else dsay
            self.bg_q.put(("call", lambda: self._qt_say(f"{self._qt_clean(ereq['title'])}, {dsay}{tm}"
                                                      + (", every week" if ereq.get("repeat") else "") + ". Add it?", you=text)))
            return
        if self._qt_is_cmd(text):            # do it with full Archie (calendar, reminders, flashcards...), answered out loud
            if job is not None:
                job["stop"].set()
            self.qt_hist += [{"role": "user", "content": text}, {"role": "assistant", "content": "(done in the chat)"}]
            self.bg_q.put(("call", lambda t=text: self._talk_heard(t)))
            return
        if job is None:
            job = self._qt_new_job(text, seq, commit=True)
        else:
            self.bg_q.put(("call", lambda j=job: self._qt_commit(j)))

    def _qt_commit(self, job):                 # main thread: this is the answer, say it
        tw = self.talk_win
        if tw is None or not tw.alive() or job["stop"].is_set():
            return
        old = getattr(self, "_qt_job", None)
        if old is not None and old is not job:
            old["stop"].set()
        self._qt_job = job
        job["commit"], job["t0"] = True, time.time()
        tw.set_you(job["text"])
        tw.clear_captions()
        tw.set_state("thinking")
        sp = self.speaker
        if sp is not None:
            sp.stop()
            if isinstance(sp, talk.KokoroSpeaker):
                sp.start_turn()
        if self.cfg.get("talk_hmm", True):
            self.root.after(1400, lambda j=job: self._qt_hmm(j))
        self._qt_flow(job)

    def _qt_hmm(self, job):
        if job is getattr(self, "_qt_job", None) and not job["fed"] and not job["done"] and self.speaker is not None \
                and isinstance(self.speaker, talk.KokoroSpeaker) and not self.speaker.speaking.is_set():
            self.speaker.feed(random.choice(["Mm. ", "Right. ", "Hmm. "]))

    def _qt_flow(self, job):                   # main thread: hand new words to the voice
        if job is not getattr(self, "_qt_job", None) or not job["commit"]:
            return
        sp = self.speaker
        new = job["toks"][job["fed"]:]
        job["fed"] = len(job["toks"])
        if new and sp is not None:
            sp.feed("".join(new))
        if job["done"] and not job.get("closed"):
            job["closed"] = True
            if sp is not None:
                sp.flush()
            answer = "".join(job["toks"]).strip()
            tw = self.talk_win
            if job["err"] and not answer:
                if tw is not None and tw.alive():
                    tw.hint.configure(text="That didn't work: " + str(job["err"])[:120])
                return
            if not answer:
                return
            if job["stop"].is_set():
                answer += " [cut off]"
            self.qt_hist += [{"role": "user", "content": job["text"]}, {"role": "assistant", "content": answer}]
            self._talk_last = (job["text"], answer)
            if tw is not None and tw.alive() and self.cfg.get("talk_notes", True):
                try:
                    tw.set_notes(answer)
                except Exception:
                    pass
            if tw is not None and tw.alive() and not self.panel_visible():
                pass
            if tw is not None and tw.alive():
                took = (job["first_at"] or time.time()) - job.get("t0", time.time())
                tw.hint.configure(text=f"{len(self.qt_hist) // 2} said so far · saved to your chats when you end talk"
                                  + (f" · first words in {max(0.0, took):.1f}s" if job.get("first_at") else ""))

    def _qt_say(self, line, you=None):
        """Say one fixed line in talk mode (confirmations)."""
        job = {"text": you or "", "seq": -1, "toks": [line], "fed": 0, "done": True, "commit": False, "stop": threading.Event(),
               "err": None, "first_at": time.time(), "canned": True}
        tw = self.talk_win
        if tw is not None and tw.alive() and you:
            tw.set_you(you)
        self._qt_commit(job)

    def _qt_do_add(self, pend):
        ereq, text = pend
        try:
            self.add_event_from_text(ereq, text)
            e_day = ereq["date"] if isinstance(ereq["date"], datetime.date) else datetime.date.fromisoformat(str(ereq["date"]))
            self._qt_say(f"Added. {self._qt_clean(ereq['title'])} is on your calendar for {self._qt_say_day(e_day).lower() if self._qt_say_day(e_day) in ('Today', 'Tomorrow') else self._qt_say_day(e_day)}.", you="yes")
        except Exception as e:
            self._qt_say(f"I couldn't add it: {e}")

    def _qt_save_chat(self):
        """Talk ended: the whole conversation goes into Archie's chats (history, search, Obsidian, flashcards)."""
        if not self.qt_hist:
            return None
        now = datetime.datetime.now()
        first = " ".join(self.qt_hist[0]["content"].split())[:50]
        meta = {"id": now.strftime("%Y-%m-%d_%H%M%S") + "_talk", "started": self._qt_started or now.strftime("%b %d, %Y %I:%M %p"),
                "title": "Talk: " + first, "mode": self.cfg.get("mode"), "model": self._qt_model(),
                "updated": now.isoformat(timespec="seconds"), "messages": list(self.qt_hist), "talk": True}
        try:
            save_chat(CHATS_DIR, meta)
            return meta
        except OSError as e:
            self._write(f"(Couldn't save the talk: {e})\n", "sys")
            return None

    def _archie_talking(self):
        sp = self.speaker
        j = getattr(self, "_qt_job", None)
        return bool((sp is not None and sp.speaking.is_set()) or self.busy or (j is not None and j["commit"] and not j["done"])
                    or time.time() - self._spoke_at < 0.8)

    def _talk_level(self, v):
        tw = self.talk_win
        if tw is not None:
            tw.level = v

    def _talk_utterance(self, path):          # background thread: you finished a sentence
        try:
            text = self._get_transcriber().transcribe(path)
        except Exception as e:
            text = ""
            self.bg_q.put(("voice_error", f"Couldn't catch that: {e}"))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        text = (text or "").strip()
        if text and re.search(r"[A-Za-z0-9]", text):
            self.bg_q.put(("call", lambda: self._talk_heard(text)))

    def _talk_barge(self):
        """You started talking over Archie: stop now and listen."""
        if self.speaker is not None:
            self.speaker.stop()
        if self.busy:
            self._stop()
        j = getattr(self, "_qt_job", None)
        if j is not None and not j["done"]:
            j["stop"].set()
        tw = self.talk_win
        if tw is not None and tw.alive():
            tw.set_state("listening")

    def _talk_heard(self, text):
        tw = self.talk_win
        if tw is None or not tw.alive():
            return
        if re.fullmatch(r"\W*(stop|end talk( mode)?|that's all|goodbye|bye( archie)?)\W*", text, re.I):
            return self.talk_end()
        tw.set_you(text)
        tw.clear_captions()
        tw.set_state("thinking")
        if self.busy:
            self._stop()
        self.stop_speaking()
        if not self.panel_visible():
            self.show_panel()
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", text)
        self._talk_mode_send = True
        self._talk_q = text
        self._send()
        self._entry_changed()

    def _talk_hmm(self):
        if self.busy and not self.reply_buf and self._talk_mode_send and self.speaker is not None \
                and talk and isinstance(self.speaker, talk.KokoroSpeaker) and not self.speaker.speaking.is_set():
            self.speaker.feed("Hmm. ")

    def _talk_answered(self, answer):
        q = getattr(self, "_talk_q", "") or ""
        self._talk_last = (q, answer)
        tw = self.talk_win
        if tw is None or not tw.alive() or not self.cfg.get("talk_notes", True):
            return
        try:                      # the answer itself, laid out on screen: no second trip to the model (that made talk lag)
            tw.set_notes(answer)
        except Exception:
            pass

    def talk_end(self):
        hf, self.handsfree = self.handsfree, None
        if hf is not None:
            hf.stop()
        j = getattr(self, "_qt_job", None)
        if j is not None:
            j["stop"].set()
        self.stop_speaking()
        tw, self.talk_win = self.talk_win, None
        cool.STATE["talk"] = False
        if tw is not None:
            tw.close()
        meta = self._qt_save_chat()
        if meta:
            n = len(self.qt_hist) // 2
            self._w(f"Talk saved to your chats: “{meta['title'][6:]}” · {n} exchange{'s' if n != 1 else ''}   ", "sys")
            self._link("open it", lambda m=meta: self._qt_open(m), "sys")
            self._w("\n", "sys")
        self.qt_hist = []

    def _qt_open(self, meta):
        """Open a saved talk as a chat (so you can keep going by typing, make flashcards, save to Obsidian)."""
        try:
            self.open_chat(meta)
        except Exception:
            self.show_history()

    def talk_cut_in(self):
        """Space in talk mode: stop Archie and listen (or, with no hands-free, start / stop listening)."""
        tw = self.talk_win
        self._talk_barge()
        if self.handsfree is not None:
            self.handsfree.paused = False
            if tw is not None:
                tw.set_paused(False)
            return
        self._toggle_talk_ptt_for_talk_mode()

    def _toggle_talk_ptt_for_talk_mode(self):
        if self.recorder.recording and self._rec_kind == "talk":
            path, secs = self.recorder.stop()
            self._style_mic()
            if path:
                if self.talk_win is not None:
                    self.talk_win.set_state("thinking")
                threading.Thread(target=self._qt_utterance, args=(path, -1), daemon=True).start()
            return
        try:
            self.recorder.start()
        except VoiceError as e:
            self._write(str(e) + "\n", "sys")
            return
        self._rec_kind = "talk"
        if self.talk_win is not None:
            self.talk_win.set_state("listening")
            self.talk_win.hint.configure(text="Listening... press space again when you're done.")

    def talk_toggle_listen(self):
        hf = self.handsfree
        if hf is None:
            return self._toggle_talk_ptt_for_talk_mode()
        hf.paused = not hf.paused
        if self.talk_win is not None:
            self.talk_win.set_paused(hf.paused)

    def talk_again(self):
        sp = self.speaker
        if sp is not None and talk and isinstance(sp, talk.KokoroSpeaker):
            if not sp.repeat(audible=False) and self._talk_last:
                sp.say(self._talk_last[1])

    def talk_slower(self):
        self.cfg["voice_speed"] = round(max(0.7, float(self.cfg.get("voice_speed") or 0.95) - 0.05), 2)
        save_config(self.cfg)
        if self.talk_win is not None:
            self.talk_win.hint.configure(text=f"A bit slower now ({self.cfg['voice_speed']:.2f}x). Change it any time in Voice & quiet settings.")

    def talk_play_aloud(self):
        sp = self.speaker
        if sp is not None and talk and isinstance(sp, talk.KokoroSpeaker):
            if not sp.repeat(audible=True) and self._talk_last:
                sp.say(self._talk_last[1], audible=True)

    def talk_save(self):
        if not self._talk_last:
            return
        if not self.vault():
            self._write("Set your Obsidian vault first: right-click the owl > Choose Obsidian vault...\n", "sys")
            return
        pairs = [(self.qt_hist[i]["content"], self.qt_hist[i + 1]["content"]) for i in range(0, len(self.qt_hist) - 1, 2)] \
            if getattr(self, "qt_hist", None) else [self._talk_last]
        title = "Talk - " + " ".join(pairs[0][0].split())[:70]
        model = self.cfg["model"]

        def work():           # a short summary on top, then the whole conversation
            try:
                convo = "\n".join(f"You: {q}\nArchie: {a}" for q, a in pairs)[:9000]
                summ = quick_chat(model, "Summarize this spoken conversation as a title line and 3 to 8 tight bullet points "
                                         "(the facts, decisions and things to remember). No intro.\n\n" + convo, max_tokens=320, timeout=120)
            except Exception:
                summ = ""
            self.bg_q.put(("call", lambda: self.save_to_obsidian(title, ([("Summary", summ)] if summ else []) + pairs)))
        threading.Thread(target=work, daemon=True).start()
        if self.talk_win is not None:
            self.talk_win.hint.configure(text=f"Saving the whole conversation ({len(pairs)} exchanges) to Obsidian, with a summary on top...")

    def talk_cards(self):
        if not self._talk_last:
            return
        convo = "\n".join(f"{'You' if m['role'] == 'user' else 'Archie'}: {m['content']}" for m in (getattr(self, "qt_hist", None) or []))
        self.entry.delete("1.0", "end")
        self.entry.insert("1.0", ("make flashcards from this conversation:\n" + convo[:8000]) if convo else "make flashcards from that")
        self._send()
        if self.talk_win is not None:
            self.talk_win.hint.configure(text="Making flashcards from this conversation (they're in the chat).")

    # ----- voice notes --------------------------------------------------------

    def toggle_record(self):
        if self.recorder.recording and self._rec_kind == "recap":
            self.show_recap()
            return
        if self.recorder.recording and self._rec_kind == "talk":
            return self.toggle_talk()
        if self.recorder.recording:
            path, secs = self.recorder.stop()
            self._style_mic()
            if not path:
                self._write("That recording was too short, so I didn't keep it.\n", "sys")
                return
            self._write(f"Got it ({fmt_time(secs)}). Typing it out... I'll pop up the transcript "
                        "when it's ready. You can keep chatting meanwhile.\n", "sys")
            self._transcribe(path, secs)
            return
        try:
            self.recorder.start()
        except VoiceError as e:
            self._write(str(e) + "\n", "sys")
            return
        self._rec_kind = "note"
        self._rec_blink = False
        self._style_mic()
        self._rec_tick()

    def _rec_tick(self):
        if not self.recorder.recording:
            return
        self._rec_blink = not self._rec_blink
        self._style_mic()
        self.root.after(500, self._rec_tick)

    def _style_mic(self):
        b = self.mic_btn
        if self.recorder.recording:
            dot = "●" if getattr(self, "_rec_blink", False) else "○"
            b._on = True
            end = {"talk": "send", "recap": "recap"}.get(self._rec_kind, "stop")
            b.configure(text=f"{dot} {fmt_time(self.recorder.seconds())} {end}", fg=REC,
                        highlightbackground=REC, highlightcolor=REC)
        else:
            b._on = False
            b.configure(text="mic", fg=DIM, highlightbackground=BORDER, highlightcolor=BORDER)

    def _transcribe(self, path, secs):
        if self.transcriber is None:
            self.transcriber = Transcriber(VOICE_MODELS_DIR, self.cfg.get("voice_model"),
                                           self.cfg.get("voice_device"))

        def work():
            self._fg_transcribing = True
            try:
                text = self.transcriber.transcribe(
                    path, progress=lambda f: self.bg_q.put(("voice_progress", f)))
                try:
                    with open(os.path.splitext(path)[0] + ".txt", "w", encoding="utf-8") as f:
                        f.write(text + "\n")
                except OSError:
                    pass
                self.bg_q.put(("voice_done", (path, secs, text)))
            except VoiceError as e:
                self.bg_q.put(("voice_error", str(e)))
            except Exception as e:
                self.bg_q.put(("voice_error", f"Couldn't type out the recording: {e}"))
            finally:
                self._fg_transcribing = False
        self.bg_q.put(("voice_progress", 0.0))
        threading.Thread(target=work, daemon=True).start()

    def show_transcript(self, path, secs, text):
        """An editable transcript: fix it, tidy it, ask Archie about it, or save it to Obsidian."""
        if not self.panel_visible():
            self.show_panel()
        px = self.px
        w = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        n = len([x for x in self.voice_wins if x.winfo_exists()])
        W, H = px(self.PANEL_W - 30), px(max(420, self.PANEL_H - 100))
        w.geometry(f"{W}x{H}+{self.panel.winfo_x() + px(15 + 20 * n)}+{self.panel.winfo_y() + px(50 + 20 * n)}")
        self.voice_wins.append(w)

        top = tk.Frame(w, bg=BG)
        top.pack(fill="x", padx=px(14), pady=(px(12), px(6)))
        tk.Label(top, text="VOICE NOTE", bg=BG, fg=TEXT, font=(MONO, 10, "bold")).pack(side="left")
        tk.Label(top, text=f"  {fmt_time(secs)}", bg=BG, fg=MUTED, font=(MONO, 9)).pack(side="left")
        self._icon_btn(top, "close", w.destroy, "Close (the recording and text stay in "
                                               "the Recordings folder)").pack(side="right")
        for wid in (top,) + tuple(top.winfo_children()[:2]):
            wid.bind("<ButtonPress-1>", lambda e: setattr(w, "_drag", (e.x_root, e.y_root, w.winfo_x(), w.winfo_y())))
            wid.bind("<B1-Motion>", lambda e: w.geometry(
                f"+{w._drag[2] + e.x_root - w._drag[0]}+{w._drag[3] + e.y_root - w._drag[1]}"))

        now = datetime.datetime.now()
        title_var = tk.StringVar(value="Voice note " + now.strftime("%b %d %I:%M %p").replace(" 0", " "))
        trow = tk.Frame(w, bg=BG)
        trow.pack(fill="x", padx=px(14), pady=(0, px(8)))
        tk.Label(trow, text="title", bg=BG, fg=MUTED, font=(MONO, 8)).pack(side="left", padx=(0, px(8)))
        tk.Entry(trow, textvariable=title_var, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, bd=0,
                 font=(FONT, 10), highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", fill="x", expand=True, ipady=px(4))

        bottom = tk.Frame(w, bg=BG)
        bottom.pack(side="bottom", fill="x", padx=px(14), pady=(px(6), px(12)))
        status = tk.Label(w, text="Edit anything below. Ctrl+Z undoes.", bg=BG, fg=MUTED,
                          font=(MONO, 8), anchor="w")
        status.pack(side="bottom", fill="x", padx=px(14))
        keep_audio = tk.BooleanVar(value=False)
        tk.Checkbutton(w, text="put the recording in Obsidian too", variable=keep_audio, bg=BG,
                       fg=MUTED, selectcolor=SURFACE, activebackground=BG, activeforeground=TEXT,
                       font=(MONO, 8), bd=0, highlightthickness=0, anchor="w",
                       cursor="hand2").pack(side="bottom", fill="x", padx=px(10))

        box = tk.Frame(w, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        box.pack(fill="both", expand=True, padx=px(14), pady=(0, px(6)))
        ed = tk.Text(box, bg=SURFACE, fg=TEXT, insertbackground=ACCENT, wrap="word", bd=0,
                     padx=px(12), pady=px(10), undo=True, maxundo=-1, highlightthickness=0,
                     font=(FONT, self.TEXT_SIZES.get(self.cfg.get("text_size"), 10)),
                     selectbackground=ACCENT, selectforeground=TILE)
        sb = th.SlimScrollbar(box, ed, width=px(8))
        sb.configure(bg=SURFACE)
        ed.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=px(4))
        ed.pack(side="left", fill="both", expand=True)
        ed.insert("1.0", text or "(I couldn't hear any words in that recording.)")
        ed.edit_reset()
        ed.focus_set()

        def body():
            return ed.get("1.0", "end-1c").strip()

        def tidy_up():
            if getattr(w, "_tidying", False):
                return
            w._tidying = True
            status.configure(text="Tidying into notes with " + self.nice(self.cfg["model"]) + "...")
            original = body()

            def work():
                try:
                    out = voice_tidy(quick_chat, self.cfg["model"], original,
                                     progress=lambda f: self.bg_q.put(("call", lambda: status.winfo_exists()
                                         and status.configure(text=f"Tidying into notes... {int(f * 100)}%"))))
                    self.bg_q.put(("call", lambda: done(out, None)))
                except Exception as e:
                    self.bg_q.put(("call", lambda msg=str(e): done(None, msg)))

            def done(out, err):
                w._tidying = False
                if not w.winfo_exists():
                    return
                if err or not out:
                    status.configure(text=f"Couldn't tidy it: {err or 'no answer'}")
                    return
                ed.edit_separator()
                ed.delete("1.0", "end")
                ed.insert("1.0", out)
                ed.edit_separator()
                status.configure(text="Tidied. Ctrl+Z brings back the word-for-word version.")
            threading.Thread(target=work, daemon=True).start()

        def ask():
            t = body()
            if not t:
                return
            self.entry.delete("1.0", "end")
            self.entry.insert("1.0", "Here's a voice note I recorded:\n\n" + t +
                              "\n\nSummarize it and tell me what to do next.")
            self._entry_changed()
            self.panel.lift()
            self.entry.focus_force()
            status.configure(text="Put it in the chat box. Edit the question, then press Enter.")

        def copy():
            w.clipboard_clear()
            w.clipboard_append(body())
            status.configure(text="Copied.")

        def save():
            vault = self.vault()
            if not vault:
                status.configure(text="No Obsidian vault set. Right-click the owl > Choose Obsidian vault...")
                return
            t, title = body(), " ".join(title_var.get().split()) or "Voice note"
            status.configure(text="Saving to Obsidian...")

            def work():
                try:
                    audio = None
                    if keep_audio.get():
                        import shutil
                        adir = os.path.join(vault, obs.ARCHIE_FOLDER, "Voice notes", "audio")
                        os.makedirs(adir, exist_ok=True)
                        audio = os.path.basename(path)
                        shutil.copy2(path, os.path.join(adir, audio))
                    links = obs.related_links(self.notes, t)
                    note = obs.build_voice_note(title, t, secs, links, audio)
                    rel = obs.save_note(vault, title, note, subfolder="Voice notes")
                    self.bg_q.put(("call", lambda: saved(rel, links, None)))
                except Exception as e:
                    self.bg_q.put(("call", lambda msg=str(e): saved(None, [], msg)))

            def saved(rel, links, err):
                if w.winfo_exists():
                    if err:
                        status.configure(text=f"Couldn't save: {err}")
                        return
                    status.configure(text="Saved to " + rel)
                    save_btn.configure(text="open in obsidian")
                    save_btn._cmd = lambda: obs.open_in_obsidian(vault, rel)
                self._obsidian_saved(rel, links, err)
            threading.Thread(target=work, daemon=True).start()

        def btn(text, cmd, primary=False):
            b = tk.Label(bottom, text=text, font=(MONO, 8, "bold" if primary else "normal"),
                         bg=ACCENT if primary else BG, fg=TILE if primary else DIM,
                         padx=px(10), pady=px(4), bd=0, cursor="hand2",
                         highlightthickness=0 if primary else 1, highlightbackground=BORDER)
            b._cmd = cmd
            b.bind("<ButtonRelease-1>", lambda e: b._cmd())
            if not primary:
                b.bind("<Enter>", lambda e: b.configure(fg=TEXT))
                b.bind("<Leave>", lambda e: b.configure(fg=DIM))
            return b

        save_btn = btn("save → obsidian", save, primary=True)
        save_btn.pack(side="right")
        for label, cmd, tip in (("tidy up", tidy_up, "Turn it into clean notes (Ctrl+Z to undo)"),
                                ("ask archie", ask, "Put it in the chat to ask about it"),
                                ("copy", copy, "Copy the text")):
            b = btn(label, cmd)
            b.pack(side="left", padx=(0, px(6)))
            self._tip(b, tip)
        w.bind("<Escape>", lambda e: w.destroy())

    # ----- notes (knowledge folder) -----------------------------------------

    def _style_notes_btn(self):
        for btn, key, label in ((self.notes_btn, "use_notes", "notes"),
                                (self.wiki_btn, "use_wiki", "wiki")):
            on = bool(self.cfg.get(key))
            btn._on = on
            btn.configure(text=f"{label} {'●' if on else '○'}", fg=ACCENT if on else DIM,
                          highlightbackground=ACCENT if on else BORDER,
                          highlightcolor=ACCENT if on else BORDER)

    def toggle_wiki(self):
        self.cfg["use_wiki"] = not self.cfg.get("use_wiki")
        save_config(self.cfg)
        self._style_notes_btn()
        if not self.cfg["use_wiki"]:
            self._write("Wikipedia is off.\n", "sys")
            return
        found = self.wiki.describe()
        if found:
            self._write(f"Wikipedia is on. I'll look things up in {found} (offline) "
                        "and tell you which articles I used.\n", "sys")
        else:
            self._write("Wikipedia is on, but there's no Wikipedia file yet. Double-click "
                        "Get Wikipedia.bat in the Archie\\Tools folder to download one.\n", "sys")

    def toggle_notes(self):
        self.cfg["use_notes"] = not self.cfg.get("use_notes")
        save_config(self.cfg)
        self._style_notes_btn()
        if self.cfg["use_notes"]:
            os.makedirs(NOTES_DIR, exist_ok=True)
            has_files = any(files for _, _, files in os.walk(NOTES_DIR))
            if self.vault():
                self._write("Notes are on. I'll search your Notes folder, our past chats and your "
                            f"Obsidian vault ({os.path.basename(self.vault())}). The first read of the "
                            "vault can take a few minutes; after that only changes are read.\n", "sys")
                self.refresh_notes_in_background(quiet=False)
                return
            if has_files:
                self._write("Notes are on. I'll search your Notes folder for anything that "
                            "helps answer your questions.\n", "sys")
            else:
                self._write("Notes are on, but your Notes folder is empty. Put class notes, "
                            "PDFs, Word docs or project files in it (right-click the owl, "
                            "then Open Notes folder).\n", "sys")
            self.refresh_notes_in_background(quiet=not has_files)
        else:
            self._write("Notes are off.\n", "sys")

    def refresh_notes_in_background(self, quiet=False):
        def work():
            try:
                summary, problems = self.notes.refresh(
                    progress=lambda s: self.bg_q.put(("status", s)))
                self.bg_q.put(("notes_done", (summary, problems, quiet)))
            except ArchieError as e:
                self.bg_q.put(("notes_error", str(e)))
            except Exception as e:
                self.bg_q.put(("notes_error", f"Couldn't read your notes: {e}"))
        threading.Thread(target=work, daemon=True).start()

    # ----- modes and About me ----------------------------------------------

    def _fill_mode_menu(self):
        self._draw_tabs()

    def set_mode(self, name, announce=True):
        self.cfg["mode"] = name
        save_config(self.cfg)
        self._draw_tabs()
        want = (self.modes.get(name) or {}).get("model")
        note = ""
        if want:
            installed = list_models() or []
            match = next((n for n in installed if n == want or n.split(":")[0] == want), None)
            if match:
                self.set_model(match)
            elif installed:
                note = f" (it works best with {want}: run  ollama pull {want})"
        if announce:
            self._write(f"Mode: {name}{note}\n", "sys")
        self._update_status()

    def build_system_prompt(self):
        """Archie's standing instructions + your About me file + the current mode."""
        parts = [self.cfg["system_prompt"]]
        about = "\n".join(line for line in read_small_text(ABOUT_PATH).splitlines()
                          if not line.lstrip().startswith("#")).strip()
        if about:
            parts.append("What you know about the user (from their About me file):\n" + about)
        try:
            sched = self._cal_context()
        except Exception:
            sched = []
        if sched:
            parts.append(f"The user's calendar (today is {datetime.date.today():%A %B %d, %Y}); use it when "
                         "the user asks about their schedule, exams or what's coming up:\n" + "\n".join(sched))
        try:
            wk = self.thisweek.prompt_block()
        except Exception:
            wk = ""
        if wk:
            parts.append(wk)
        try:
            los = self.leftoff.recent(3, days=10)
        except Exception:
            los = []
        if los:
            parts.append("Where the user left off on their recent projects (from their focus timer):\n"
                         + "\n".join(f"- {lo['task']} ({lo['date']}): {lo['note']}" for lo in los))
        mode = self.modes.get(self.cfg.get("mode"))
        if mode and mode["prompt"]:
            parts.append(mode["prompt"])
        return "\n\n".join(parts)

    # ----- chat history -----------------------------------------------------

    def _save_current_chat(self):
        if not self.history:
            return
        now = datetime.datetime.now()
        if self.chat_meta is None:
            first = self.history[0].get("display") or self.history[0]["content"]
            title = " ".join(first.split())[:60] or "Chat"
            self.chat_meta = {"id": now.strftime("%Y-%m-%d_%H%M%S"),
                              "started": now.strftime("%b %d, %Y %I:%M %p").replace(" 0", " "),
                              "title": title}
        self.chat_meta.update(mode=self.cfg.get("mode"), model=self.cfg.get("model"),
                              updated=now.isoformat(timespec="seconds"),
                              messages=self.history)
        try:
            save_chat(CHATS_DIR, self.chat_meta)
        except OSError as e:
            self._write(f"(Couldn't save this chat: {e})\n", "sys")

    def show_history(self):
        if not self.panel_visible():
            self.show_panel()
        if self.history_win is not None and self.history_win.winfo_exists():
            self.history_win.lift()
            return
        w = self.history_win = tk.Toplevel(self.root)
        w.overrideredirect(True)
        w.after(80, lambda: th.round_corners(w, self.px(12)))
        w.attributes("-topmost", True)
        w.configure(bg=BG, highlightthickness=1, highlightbackground=BORDER)
        W, H = self.px(self.PANEL_W - 40), self.px(self.PANEL_H - 120)
        w.geometry(f"{W}x{H}+{self.panel.winfo_x() + self.px(20)}+{self.panel.winfo_y() + self.px(60)}")

        top = tk.Frame(w, bg=SURFACE)
        top.pack(fill="x")
        tk.Label(top, text="Chat history", bg=SURFACE, fg=ACCENT, font=(FONT, 11, "bold"),
                 padx=10, pady=6).pack(side="left")
        tk.Button(top, text="✕", command=w.destroy, bg=SURFACE, fg=MUTED, bd=0,
                  activebackground=INPUT_BG, activeforeground=TEXT, relief="flat",
                  font=(FONT, 10), padx=8, cursor="hand2").pack(side="right")

        search_var = tk.StringVar()
        search = tk.Entry(w, textvariable=search_var, bg=INPUT_BG, fg=TEXT,
                          insertbackground=TEXT, bd=0, font=(FONT, 10), highlightthickness=1,
                          highlightbackground=INPUT_BG, highlightcolor=ACCENT)
        search.pack(fill="x", padx=8, pady=(8, 4), ipady=4)
        hint = tk.Label(w, text="Type to search. Double-click a chat to open it.",
                        bg=BG, fg=MUTED, font=(FONT, 8), anchor="w")
        hint.pack(fill="x", padx=8)

        btns = tk.Frame(w, bg=BG)
        btns.pack(side="bottom", fill="x", padx=8, pady=8)
        lst = tk.Listbox(w, bg=BG, fg=TEXT, selectbackground=ACCENT, selectforeground=TILE,
                         bd=0, highlightthickness=0, font=(FONT, 9), activestyle="none")
        lst.pack(fill="both", expand=True, padx=8, pady=4)

        chats = list_chats(CHATS_DIR)
        shown = []

        def refill(*_):
            q = search_var.get().lower().strip()
            lst.delete(0, "end")
            shown.clear()
            for c in chats:
                if q and q not in (c.get("title", "") + " " + c.get("text", "")).lower():
                    continue
                shown.append(c)
                day = c.get("started", "").split(",")[0]
                lst.insert("end", f"{day}  ·  {c.get('title', 'Chat')}  ({c.get('mode', '')})")
            if not shown:
                lst.insert("end", "No saved chats yet." if not chats else "No matches.")

        def selected():
            sel = lst.curselection()
            return shown[sel[0]] if sel and sel[0] < len(shown) else None

        def open_sel(*_):
            c = selected()
            if c:
                w.destroy()
                self.open_chat(c)

        def delete_sel():
            c = selected()
            if not c:
                return
            if del_btn.cget("text") != "Sure? Delete":   # ask once before deleting
                del_btn.configure(text="Sure? Delete", fg=TEXT)
                w.after(3000, lambda: del_btn.winfo_exists() and
                        del_btn.configure(text="Delete", fg=MUTED))
                return
            del_btn.configure(text="Delete", fg=MUTED)
            if c:
                delete_chat(CHATS_DIR, c["id"])
                chats.remove(c)
                if self.chat_meta and self.chat_meta.get("id") == c["id"]:
                    self.chat_meta = None
                refill()

        style = dict(bd=0, relief="flat", font=(FONT, 9, "bold"), padx=12, pady=3, cursor="hand2")
        tk.Button(btns, text="Open", command=open_sel, bg=ACCENT, fg=TILE,
                  activebackground=ACCENT_HI, **style).pack(side="right")
        del_btn = tk.Button(btns, text="Delete", command=delete_sel, bg=INPUT_BG, fg=MUTED,
                            activebackground=INPUT_BG, activeforeground=TEXT, **style)
        del_btn.pack(side="left")
        search_var.trace_add("write", refill)
        lst.bind("<Double-Button-1>", open_sel)
        lst.bind("<Return>", open_sel)
        w.bind("<Escape>", lambda e: w.destroy())
        refill()
        search.focus_set()

    def open_chat(self, c):
        if self.busy:
            self._stop()
        self.book_ctx = None
        self.history = [dict(m) for m in c.get("messages", [])]
        self.chat_meta = {k: v for k, v in c.items() if k not in ("text", "messages")}
        self.attachments = []
        self._render_chips()
        self._clear_chat()
        self._write(f"Reopened: {c.get('title', 'Chat')} ({c.get('started', '')})\n", "sys")
        for m in self.history:
            if m["role"] == "user":
                self._you(m.get("display") or m["content"])
            else:
                self._archie()
                self._write(m["content"], "abody")
                self._end_span()
                self._write("\n", "abody")
        if c.get("mode") in self.modes and c.get("mode") != self.cfg.get("mode"):
            self.set_mode(c["mode"], announce=False)
        self._write("Keep going: anything you send continues this chat.\n", "sys")

    # ----- models -----------------------------------------------------------

    def refresh_models(self):
        names = list_models()
        menu = self.model_popup
        menu.delete(0, "end")
        if names is None:
            self.status.configure(text=f"Ollama not reachable at {OLLAMA_URL}")
            menu.add_command(label=self.cfg["model"], command=lambda: None)
            self.ollama_ok = False
            return
        self.ollama_ok = True
        chat_models = [n for n in names if not n.startswith("nomic-embed")]
        if not chat_models:
            menu.add_command(label="(no models pulled yet)", state="disabled")
        self.model_names = load_model_names(MODEL_NAMES_PATH)
        for n in chat_models:
            label = self.nice(n) if self.nice(n) == n else f"{self.nice(n)}   ({n})"
            menu.add_radiobutton(label=label, command=lambda v=n: self.set_model(v),
                                 variable=self.model_choice, value=n)
        if chat_models and self.cfg["model"] not in chat_models:
            self.set_model(chat_models[0])
        self._update_status()

    def nice(self, model):
        """Friendly name for a model, from model_names.txt."""
        return (self.model_names.get(model) or self.model_names.get(model.split(":latest")[0])
                or model)

    def set_model(self, name):
        self.cfg["model"] = name
        self.model_choice.set(name)
        save_config(self.cfg)
        self._update_status()

    def _update_status(self, extra=""):
        self._draw_chip()
        self.status.configure(text=extra or "offline · local")

    # ----- conversation -----------------------------------------------------

    def _greet(self):
        tip = ("drag files onto this window or use +" if TkinterDnD
               else "use + to attach files")
        self._write(f"Hi, I'm ARCHIE: {FULL_NAME}. Everything we talk about stays on this computer. "
                    f"Ask me anything, or {tip} (PDFs, Word, code, notes, photos). "
                    "Enter sends, Shift+Enter adds a new line. Click help (or type it) for everything I can do.\n", "sys")
        if self.hotkeys.supported:
            self._write(f"Shortcuts: {pretty_combo(self.cfg.get('hotkey_chat') or '')} opens or hides "
                        f"me from anywhere; {pretty_combo(self.cfg.get('hotkey_snip') or '')} (or the "
                        "snip button) lets you drag a box on screen and send it to me.\n", "sys")
        self._write("School day: record a class with the mic in Obsidian on your phone and the notes are waiting "
                    "in Obsidian when you get home. Type  school day  for the whole walkthrough.\n", "sys")
        if not getattr(self, "ollama_ok", False):
            self._write("I can't find Ollama right now. Start the Ollama app, then click "
                        "+ (New chat) to try again.\n", "sys")
        elif not list_models():
            self._write("No models are installed yet. Double-click Tools\\Get Models.bat in the "
                        "Archie folder.\n", "sys")

    def new_conversation(self):
        if self.busy:
            self._stop()
        self.book_ctx = None
        self.history = []
        self.chat_meta = None
        self.attachments = []
        self._render_chips()
        self._clear_chat()
        if not self.panel_visible():
            self._greeted = True
            self.show_panel()
        self.refresh_models()
        self._greet()

    def _write(self, text, tag):
        self.chat.configure(state="normal")
        self.chat.insert("end", text, tag)
        self.chat.configure(state="disabled")
        self.chat.see("end")
        self._queue_bars()

    def _on_enter(self, _e):
        self.send_or_stop()
        return "break"  # don't insert a newline

    def send_or_stop(self):
        if self.busy:
            self._stop()
        else:
            self._send()
        self.root.after_idle(self._entry_changed)

    def _send(self):
        text = self.entry.get("1.0", "end").strip()
        files = list(self.attachments)
        low = text.lower().strip(" .!?")
        if low in ("help", "what can you do", "what can you do?", "commands", "functions", "features", "all commands",
                   "what do you do", "show commands", "list commands", "help me", "archie help"):
            self.entry.delete("1.0", "end")
            self.show_help()
            return
        if low in ("news", "news brief", "world news", "the news", "brief me on the news", "whats in the news",
                   "what's in the news", "whats the news", "what's the news", "morning news"):
            self.entry.delete("1.0", "end")
            self.show_world("brief")
            return
        if low in ("world calendar", "calendar world", "world events", "upcoming world events", "elections"):
            self.entry.delete("1.0", "end")
            self.show_world("calendar")
            return
        if low in ("solar system", "the solar system", "planets", "orrery", "show the solar system", "open the solar system",
                   "show me the planets", "space"):
            self.entry.delete("1.0", "end")
            self.show_world("solar")
            return
        if low in ("governments", "government", "world governments", "who governs", "who runs the world", "show governments"):
            self.entry.delete("1.0", "end")
            self.show_world("gov=")
            return
        law = {"lawmaking": "law", "bill tracker": "law:US:bills", "bills in congress": "law:US:bills", "track bills": "law:US:bills",
               "votes in congress": "law:US:votes", "how did congress vote": "law:US:votes", "congress votes": "law:US:votes", "voting records": "law:US:people",
               "executive orders": "law:US:exec", "executive actions": "law:US:exec", "political calendar": "cal", "hearings": "cal", "upcoming elections": "cal",
               "my representatives": "reps", "my reps": "reps", "who represents me": "reps", "my congressman": "reps", "my senators": "reps",
               "campaign money": "law:US:people", "campaign finance": "law:US:people"}
        if low.strip(" ?") in law:
            self.entry.delete("1.0", "end")
            self.show_world("gov=" + law[low.strip(" ?")])
            return
        for pre, suf in (("how did ", " vote"), ("how does ", " vote"), ("voting record of ", ""), ("who funds ", ""), ("who pays for ", ""), ("campaign money for ", "")):
            t = low.strip(" ?")
            if t.startswith(pre) and t.endswith(suf) and len(t) > len(pre) + len(suf) + 2:
                name = t[len(pre):len(t) - len(suf)].strip()
                if name not in ("congress", "the senate", "the house", "parliament"):
                    self.entry.delete("1.0", "end")
                    self.show_world("gov=law:US:find:" + name.replace(" ", "+"))
                    return
        for pre in ("who runs ", "who governs ", "who leads ", "government of ", "who is in charge of ", "who's in charge of "):
            if low.startswith(pre) and len(low) > len(pre) + 1:
                self.entry.delete("1.0", "end")
                self.show_world("gov=" + low[len(pre):].strip(" ?").replace("the ", "", 1).replace(" ", "-"))
                return
        arc = {"people in space": "people", "who is in space": "people", "who's in space": "people", "astronauts": "people", "golden record": "golden-record",
               "the golden record": "golden-record", "voyager golden record": "golden-record", "golden record pictures": "golden-album", "golden record album": "golden-album",
               "mission planner": "planner", "plan a mission": "planner", "andromeda merger": "merger", "galaxy collision": "merger"}
        if low in arc:
            self.entry.delete("1.0", "end")
            self.show_world("merger" if arc[low] == "merger" else "archive=" + arc[low])
            return
        if low in ("milky way", "the milky way", "galaxy", "the galaxy", "show the galaxy", "show me the milky way", "show the milky way",
                   "exoplanets", "other solar systems", "other star systems"):
            self.entry.delete("1.0", "end")
            self.show_world("galaxy")
            return
        if low.startswith(("show me the system ", "star system ", "exoplanet ")):
            self.entry.delete("1.0", "end")
            self.show_world("system=" + low.split(" ", 2)[-1].replace("the system ", "").strip().replace(" ", "-"))
            return
        if low.startswith(("where is voyager", "where's voyager", "where is new horizons", "where's new horizons", "where is juno",
                           "where is parker", "where is the james webb", "where is jwst")):
            self.entry.delete("1.0", "end")
            name = low.split(" is ", 1)[-1].split("'s ", 1)[-1].replace("the ", "").strip()
            self.show_world("craft=" + ("james-webb-space-telescope" if "webb" in name or "jwst" in name else name.replace(" ", "-")))
            return
        if low in ("news quiz", "world quiz", "quiz me on the news", "quiz me on world news", "quiz me on the world",
                   "current events quiz", "quiz me on this week", "quiz me on current events"):
            self.entry.delete("1.0", "end")
            self.show_world("quiz")
            return
        if low in ("whats new", "what's new", "whats new in the world", "what's new in the world", "anything new",
                   "what did i miss", "new since i looked"):
            self.entry.delete("1.0", "end")
            self.show_world("new")
            return
        if low in ("news lesson", "world lesson") or low.startswith(("news lesson on ", "news lesson about ", "world lesson on ",
                                                                     "world lesson about ", "teach me the news about ",
                                                                     "teach me about the news on ", "explain the news about ")):
            self.entry.delete("1.0", "end")
            topic = ""
            for pre in ("news lesson on ", "news lesson about ", "world lesson on ", "world lesson about ",
                        "teach me the news about ", "teach me about the news on ", "explain the news about "):
                if low.startswith(pre):
                    topic = text.strip()[len(pre):].strip()
                    break
            self.show_world("lesson=" + topic)
            return
        if low.startswith(("catch me up on ", "catch me up about ", "catch up on ")):
            self.entry.delete("1.0", "end")
            self.show_world("catchup=" + text.strip().split(" on ", 1)[-1].split(" about ", 1)[-1].strip())
            return
        if low in ("world review", "week in review", "weekly world review", "this week in the world"):
            self.entry.delete("1.0", "end")
            self._world_weekly()
            return
        if low in ("vault", "the vault", "open the vault", "open vault", "library", "the library", "offline library") or \
                low.startswith(("vault ", "search the vault for ", "look in the vault for ")):
            self.entry.delete("1.0", "end")
            q = re.sub(r"^(vault|search the vault for|look in the vault for)\s+", "", text.strip(), flags=re.I) if " " in low and not low.startswith(("open", "the ")) else ""
            import urllib.parse as _up
            self.show_vault(("search/all/" + _up.quote(q)) if q else "")
            return
        if low in ("workshop", "open workshop", "the workshop", "code", "coding", "open the workshop"):
            self.entry.delete("1.0", "end")
            self.show_workshop()
            return
        if low in ("world", "globe", "archie world", "open world", "open the globe", "show the globe",
                   "morning note", "markets", "market note", "the markets") or low.startswith(("world ", "globe ")):
            self.entry.delete("1.0", "end")
            rest = text.strip().split(" ", 1)[1].strip() if low.startswith(("world ", "globe ")) else ""
            if low in ("morning note", "markets", "market note", "the markets"):
                self.show_world("note")
            elif rest:
                self.show_world("ask=" + rest)
            else:
                self.show_world()
            return
        if low in ("manual", "open manual", "open the manual", "show manual", "user manual", "open archie manual", "open the archie manual"):
            self.entry.delete("1.0", "end")
            self.open_manual()
            return
        if low in ("study", "review", "study flashcards", "review flashcards", "quiz me on my flashcards",
                   "flashcards", "my flashcards"):
            self.entry.delete("1.0", "end")
            self.show_study(None)
            return
        if low in ("audiobooks", "audiobook", "my audiobooks", "audiobook status"):
            self.entry.delete("1.0", "end")
            self.audiobook_report()
            return
        if low in ("shelf history", "card history", "flashcard history", "deck history", "exam history"):
            self.entry.delete("1.0", "end")
            self.shelf_history()
            return
        if low in ("decks", "my decks", "list decks", "shelf", "my shelf", "open shelf"):
            self.entry.delete("1.0", "end")
            self.list_decks()
            return
        if low in ("sonia", "sonia audio", "sonia window", "open sonia", "make sonia audio"):
            self.entry.delete("1.0", "end")
            self.sonia_window()
            return
        m_sv = re.fullmatch(r"sonia\s+(speed|volume)\s+(?:to\s+)?([\d.]+)\s*(?:x|%)?", low)
        if m_sv:
            self.entry.delete("1.0", "end")
            v = float(m_sv.group(2))
            st = {"speed": max(0.6, min(2.0, v))} if m_sv.group(1) == "speed" else {"vol": max(0.0, min(1.0, v / 100 if v > 1 else v))}
            self.sonia_ask(setting=st)
            self._write(f"Sonia's {m_sv.group(1)} set for Feather (phone and laptops), at the next sync.\n", "sys")
            return
        m_sa = re.fullmatch(r"(?:please\s+)?(?:make|get|do|record)\s+sonia(?:\s+audio)?\s+(?:for|of)\s+(?:(?:chapters?\s+(\d+)(?:\s*(?:-|–|to|through)\s*(\d+))?|the\s+whole\s+book|all(?:\s+of)?)\s+(?:of|from|in)\s+)?(.+?)(?:\s+(?:on|for|to)\s+(?:my\s+|the\s+)?(phone|laptops?))?", low)
        if m_sa:
            self.entry.delete("1.0", "end")
            info = self._sonia_books()
            want = " ".join(m_sa.group(3).split())
            hit = next(((k, b) for k, b in (info.get("books") or {}).items() if " ".join(str(b.get("name")).lower().split()) == want), None) \
                or next(((k, b) for k, b in (info.get("books") or {}).items() if want in str(b.get("name")).lower()), None)
            fr = int(m_sa.group(1)) - 1 if m_sa.group(1) else 0
            to = (int(m_sa.group(2)) - 1 if m_sa.group(2) else fr) if m_sa.group(1) else None
            devs = ["laptops"] if (m_sa.group(4) or "").startswith("laptop") else ["phone"] if m_sa.group(4) == "phone" else ["phone", "laptops"]
            ok = self.sonia_ask(rid=hit[0] if hit else None, book=None if hit else m_sa.group(3), fr=max(0, fr), to=to, devs=devs)
            what = f"chapters {fr + 1}–{to + 1}" if to is not None and to != fr else f"chapter {fr + 1}" if to is not None else "the whole book"
            self._write((f"Sonia will read {what} of {hit[1].get('name') if hit else m_sa.group(3)} for your {' and '.join(devs)}. "
                         "Your PC starts at the next sync with Feather (it needs the internet for Sonia); then it plays offline.\n") if ok
                        else "Couldn't queue that.\n", "sys")
            return
        m_nf = re.match(r"^(?:note|jot)\s+(?:to|for|in)\s+feather\s*[:\-,]?\s*(.+)$", text.strip(), re.I | re.S)
        if m_nf or (not self.attachments and re.fullmatch(r"(?:please\s+)?(?:send|save|put|copy)\s+(?:that|this|it|the last answer|your answer|that answer)\s+(?:to|in|into|on)\s+feather(?:\s+as\s+an?\s+(?:quick\s+)?note)?(?:\s+please)?", low)):
            body = m_nf.group(1).strip() if m_nf else next((m.get("display") or m["content"] for m in reversed(self.history) if m["role"] == "assistant"), "")
            self.entry.delete("1.0", "end")
            if not body:
                self._write("Nothing to send yet: ask me something first, or type  note to feather: <your note>.\n", "sys")
            elif self.note_to_feather(body):
                self._write("Sent to Feather as a quick note. It shows up on your phone and laptops after their next sync.\n", "sys")
            else:
                self._write("Couldn't queue that note for Feather.\n", "sys")
            return
        m_fx = re.match(r"^(?:send|move|push|copy)\s+(?:the\s+)?(.+?)\s+(?:deck\s+|set\s+|flashcards\s+)?to\s+feather$", low)
        m_fg = re.match(r"^(?:get|pull|request|fetch)\s+(?:the\s+)?(.+?)\s+(?:deck\s+|set\s+|flashcards\s+)?from\s+feather$", low)
        if self.attachments and re.fullmatch(r"(?:please\s+)?(?:send|put|move|copy)\s+(?:it|this|these|them|that|the files?)?\s*(?:to|on|onto|into)\s+(?:feather|my phone|the phone)(?:\s+please)?", low):
            self.entry.delete("1.0", "end")
            files_ = list(self.attachments)
            self.attachments, self.keep = [], {}
            self._render_chips()
            self._write(self.send_to_feather(files_) + "\n", "sys")
            return
        if m_fx:
            d = self.study.find_deck(m_fx.group(1))
            self.entry.delete("1.0", "end")
            if d:
                self.feather_xfer("a2f", d)
            else:
                self._write(f"I don't have a set called “{m_fx.group(1)}”. Type  decks  to see them.\n", "sys")
            return
        if m_fg:
            w = m_fg.group(1).strip()
            names = list(self._feather_sets())
            hit = next((n for n in names if n.lower() == w), None) or next((n for n in names if w in n.lower()), None)
            self.entry.delete("1.0", "end")
            if hit:
                self.feather_xfer("f2a", hit)
            else:
                self._write(f"Feather has no set called “{w}” (as of its last sync). Type  decks  to see them.\n", "sys")
            return
        if low.startswith(("study ", "review ")) and len(low) > 6:
            d = self.study.find_deck(low.split(" ", 1)[1])
            if d:
                self.entry.delete("1.0", "end")
                self.show_study(d)
                return
        if low in ("daily", "daily note", "today's note", "todays note", "open daily note", "open my daily note", "open the daily note",
                   "open today's note", "open today's daily note", "open todays daily note"):
            self.entry.delete("1.0", "end")
            self.open_daily()
            return
        if text.lower().startswith("log:") and text[4:].strip():
            self.entry.delete("1.0", "end")
            self._you(text)
            self._log_entry(text[4:])
            return
        what = self.apps.parse_open(text) if not files else None
        if what:
            self.apps.folders = self._app_folders()
            known = self.apps.folder_for(what)[1] or len(what.split()) <= 3
            if known:
                self.entry.delete("1.0", "end")
                self._open_thing(what, text)
                return
        if low in ("recap", "evening recap", "my recap", "start recap", "start my recap", "wrap up my day",
                   "wrap up the day", "daily recap", "end of day recap"):
            self.entry.delete("1.0", "end")
            self.hotkey_recap()
            return
        if low in ("this week", "my week", "weekly review", "week review", "review my week", "sum up my week",
                   "weekly summary", "look over my week"):
            self.entry.delete("1.0", "end")
            self.show_week()
            return
        if low in ("patterns", "my patterns", "show patterns", "show my patterns", "habits", "my habits"):
            self.entry.delete("1.0", "end")
            self.show_patterns()
            return
        if low in ("school day", "a school day", "a day with archie", "day with archie", "day in the field",
                   "walkthrough", "walk me through a day", "how do i use you at school", "school walkthrough"):
            self.entry.delete("1.0", "end")
            self._school_day()
            return
        if low in ("lectures", "lecture notes", "my lectures", "open lectures", "class notes", "open lecture notes"):
            self.entry.delete("1.0", "end")
            self._open_lectures()
            return
        if low in ("wake after class", "wake after class on", "lecture wake on", "turn on wake after class"):
            self.entry.delete("1.0", "end")
            self._lecture_wake_toggle(True)
            return
        if low in ("wake after class off", "lecture wake off", "turn off wake after class", "stop waking after class"):
            self.entry.delete("1.0", "end")
            self._lecture_wake_toggle(False)
            return
        if low in ("gym", "drawing gym", "draw gym", "gesture drawing", "gesture practice", "figure drawing",
                   "drawing practice", "practice drawing", "reference practice", "start drawing gym"):
            self.entry.delete("1.0", "end")
            self.show_gym()
            return
        if low in ("focus", "pomodoro", "timer", "focus timer", "start focus", "start a pomodoro",
                   "start pomodoro", "focus mode", "owl timer"):
            self.entry.delete("1.0", "end")
            self.show_focus()
            return
        m_focus = re.match(r"^(?:focus|pomodoro)\s*:\s*(.+)$", text.strip(), re.I)
        if m_focus:
            self.entry.delete("1.0", "end")
            self.show_focus(task=m_focus.group(1).strip(), start=True)
            return
        if low in ("calendar", "my calendar", "open calendar", "open my calendar", "schedule", "my schedule",
                   "show my calendar", "show calendar"):
            self.entry.delete("1.0", "end")
            self.show_calendar()
            return
        if low in ("exams", "my exams", "mock exams", "my mock exams", "quizzes", "my quizzes"):
            self.entry.delete("1.0", "end")
            self.list_exams()
            return
        if not files and calchat.looks_like_edit(text, self.calendar):   # "move X to 6pm", "cancel Y"
            self.entry.delete("1.0", "end")
            self.change_event_from_text(text)
            return
        ereq = cal.parse_event(text) if not files else None
        if ereq:
            self.entry.delete("1.0", "end")
            self.add_event_from_text(ereq, text)
            return
        # "... and send it to feather": make it, then send it to Feather (at the next sync)
        m_tf = re.search(r"[\s,]*(?:and|then|&)?\s*(?:send|put|move|copy)\s+(?:it|that|this|them)?\s*(?:over\s+)?(?:to|on|onto|into|in)\s+(?:feather|my phone|the phone)\s*[.!]*\s*$", text, re.I)
        mreq = exam.parse_request(text[:m_tf.start()] if m_tf else text)
        if mreq and m_tf:
            mreq["to_feather"] = True
        if mreq:
            self.entry.delete("1.0", "end")
            files_ = list(self.attachments)
            self.attachments, self.keep = [], {}
            self._render_chips()
            self.start_mock(mreq, text, files_)
            return
        if low in ("sketch", "from a sketch", "sketch to image", "draw from my sketch", "draw from a sketch",
                   "paint my sketch", "sketch mode"):
            self.entry.delete("1.0", "end")
            self.show_sketch()
            return
        pics = [f for f in files if f.lower().endswith(self.SKETCH_EXT)] if files else []
        if pics and re.search(r"\b(sketch|drawing|doodle|line ?art)\b", low) and \
                re.search(r"\b(turn|make|paint|render|draw|finish|colou?r|into)\b", low):
            self.entry.delete("1.0", "end")
            self.attachments = [a for a in self.attachments if a not in pics]
            self._render_chips()
            self.show_sketch(pics[0])
            return
        dreq = imagine.parse_draw(text) if not files else None
        if dreq:
            self.entry.delete("1.0", "end")
            self.start_image(dreq, text)
            return
        creq = study.parse_cards_request(text)
        if creq:
            self.entry.delete("1.0", "end")
            files = list(self.attachments)
            self.attachments, self.keep = [], {}
            self._render_chips()
            self._make_cards(creq, text, files)
            return
        freq = None if files or re.match(r"\s*(how|what|why|when|where|which|should|is|are|does|do i|"
                                         r"can i|explain|tell me)\b", text, re.I) else apps.parse_create(text)
        if freq:
            self.entry.delete("1.0", "end")
            self._make_file(freq, text)
            return
        if low in ("books", "my books", "list books", "what books do you have",
                   "stop book", "done with the book", "stop quiz", "stop the quiz"):
            self.entry.delete("1.0", "end")
            if low.startswith(("stop", "done")):
                self.book_ctx = None
                self._write("OK, I've put the book away for this chat.\n", "sys")
            else:
                shelf = self.library.shelf()
                self._write(("Books in your Notes: " + "; ".join(shelf) + ".\nTry: quiz me on "
                             f"{shelf[0]} part 1 chapter 1\n") if shelf else
                            "No books in your Notes folder yet. Put EPUBs (or PDF / .txt books) in "
                            "Notes, then ask: quiz me on <title> part 1 chapter 1\n", "sys")
            return
        if text.lower().strip(" .!") in ("build wiki", "build a wiki", "build vault",
                                          "make a wiki", "make wiki", "wiki this"):
            self.entry.delete("1.0", "end")
            self.build_wiki()
            return
        if text and not files:
            try:
                reply = handle_command(text, self.tasks, self.deadlines)
            except OSError as e:
                reply = f"I couldn't update your list: {e.strerror}"
            if reply:   # to-do commands are handled right here, no AI needed
                self.root.after(50, lambda: self._sync_daily(quiet=True))
                self.entry.delete("1.0", "end")
                self._you(text)
                self._archie()
                self._write(reply, "abody")
                self._end_span()
                self._write("\n", "abody")
                return
        if not text and not files:
            return
        if not text:
            text = "Take a look at this. Tell me what it is and summarize the important parts."
        self.entry.delete("1.0", "end")
        to_keep = [f for f in files if self.keep.get(f)]
        self.attachments = []
        self.keep = {}
        self._render_chips()

        self._you(text)
        if files:
            line = "attached: " + ", ".join(os.path.basename(f) for f in files)
            saved = self._save_to_notes(to_keep) if to_keep else []
            if saved:
                line += "  ·  saved to Notes"
            self._write(line + "\n", "file")
        display = text
        if files:
            display += "\n[attached: " + ", ".join(os.path.basename(f) for f in files) + "]"
        msg = {"role": "user", "content": text, "display": display}
        self.history.append(msg)

        self._archie()
        self.stop_speaking()
        self._speak_now = bool(self.cfg.get("speak_answers")
                               or (self._talk_pending and self.cfg.get("talk_speaks"))
                               or self._talk_mode_send)
        self._talk_pending = False
        if self._speak_now and not self._get_speaker(quiet=not self.cfg.get("speak_answers")):
            self._speak_now = False
        if self._speak_now and self._quiet_now() and not (talk and isinstance(self.speaker, talk.KokoroSpeaker)):
            self._speak_now = False      # the old voice can't do captions: Quiet means silent
        if self._talk_mode_send and self.cfg.get("talk_hmm", True):
            self.root.after(1700, self._talk_hmm)
        self.reply_buf = ""
        self.sources = []
        self._set_busy(True)
        self.q = queue.Queue()
        self.stop_evt = threading.Event()
        threading.Thread(target=self._answer,
                         args=(self.cfg["model"], list(self.history), msg, text, files,
                               (bool(self.cfg.get("use_notes")), bool(self.cfg.get("use_wiki"))),
                               self._prompt_for_send(),
                               (self.chat_meta or {}).get("id"), self.q, self.stop_evt),
                         daemon=True).start()

    def _answer(self, model, history, msg, question, files, lookups, system_prompt,
                chat_id, out_q, stop_evt):
        """Background thread: read attachments, search notes, then stream the answer."""
        try:
            # 1. Read attached files into the message
            parts, images = [question], []
            budget = MAX_ATTACH_CHARS
            for path in files:
                name = os.path.basename(path)
                if file_kind(path) == "image":
                    out_q.put(("status", f"Looking at {name}..."))
                    images.append(read_image_b64(path))
                    continue
                out_q.put(("status", f"Reading {name}..."))
                content = read_text(path)
                if len(content) > budget:
                    content = content[:max(budget, 0)]
                    out_q.put(("note", f"{name} is long, so I only read the first part. "
                                       "For big files, put them in your Notes folder instead."))
                budget -= len(content)
                parts.append(f"--- Attached file: {name} ---\n{content}\n--- End of {name} ---")
            msg["content"] = "\n\n".join(parts)
            if images:
                msg["images"] = images

            # 2. Pick a model that can see, if this conversation has pictures
            if any(m.get("images") for m in history):
                out_q.put(("status", "Finding a model that can read images..."))
                vision = pick_vision_model(model)
                if vision != model:
                    if images:  # say so once, when the picture is first attached
                        out_q.put(("note", f"Using {self.nice(vision)} for this, since it can read "
                                           "images. (Click + for a new chat to go back to your usual model.)"))
                    model = vision
            send = []
            can_see = is_vision_model(model) if any(m.get("images") for m in history) else False
            for m in history:
                m2 = {"role": m["role"], "content": m["content"]}
                if m.get("images") and can_see:
                    m2["images"] = m["images"]
                send.append(m2)

            # 3. Search the Notes folder
            use_notes, use_wiki = lookups
            # 2b. A book chapter ("quiz me on crime and punishment part 3 chapter 5")
            ctx = self.book_ctx
            ref = books.parse_ref(question)
            if ref:
                out_q.put(("status", "Finding that chapter..."))
                found = self.library.lookup(question, ref, ctx)
                if isinstance(found, dict):
                    ctx = found
                    out_q.put(("book", ctx))
                    how = (" (a long stretch, so I'm reading excerpts spread through it)"
                           if ctx["sampled"] else "")
                    out_q.put(("note", f"Reading {ctx['title']}, {ctx['label']}{how}. "
                                       "Say \"stop book\" or start a new chat to put it away."
                               + (f" {ctx['note']}" if ctx["note"] else "")))
                elif found:
                    out_q.put(("note", found))
            system = [{"role": "system", "content": system_prompt}]
            if THIS_NOTE.search(question):
                out_q.put(("status", "Reading the note you have open in Obsidian..."))
                try:
                    note = self.obs_api.active_note()
                    body = note["content"]
                    if len(body) > 24000:
                        body = body[:24000] + "\n[...the rest of the note is cut off...]"
                    system.append({"role": "system", "content":
                        f"The user has this note open in Obsidian right now ({note['path']}). When they "
                        "says \"this note\" or asks what the user has open, the user means this one, not any other notes or "
                        "excerpts below. Use it to answer; if the user asks to be quizzed, "
                        "ask one question at a time about it.\n\n--- " + note["path"] + " ---\n"
                        + body + "\n--- end of note ---"})
                    out_q.put(("sources", ["Obsidian: " + obs.link_name(note["path"])]))
                except obs.ApiError as e:
                    out_q.put(("note", e.friendly()))
            manual = make_manual.manual_lookup(question)
            if manual:
                system.append({"role": "system", "content":
                    "The message may be a question about using Archie (you) itself. If it is, "
                    "answer from these parts of Archie's user manual: short, step by step, using "
                    "the exact button and menu names, and don't invent features that aren't in it. "
                    "If the message isn't about Archie, ignore this.\n\n" + manual})
            wiki_sources = []
            if use_wiki:
                out_q.put(("status", "Looking it up in Wikipedia..."))
                try:
                    articles = self.wiki.search(question)
                except ArchieError as e:
                    out_q.put(("note", str(e)))
                    articles = []
                if articles:
                    excerpts = "\n\n".join(f"[W{i}] Wikipedia: {t}\n{txt}"
                                           for i, (t, txt) in enumerate(articles, 1))
                    system.append({"role": "system", "content":
                        "Below are excerpts from the user's offline copy of Wikipedia that may "
                        "help answer their next message. Prefer these facts over your own "
                        "memory when they apply, and mention the article, like (Wikipedia: "
                        "Photosynthesis). If they don't help, answer normally.\n\n" + excerpts})
                    wiki_sources = [f"Wikipedia: {t}" for t, _ in articles]
                    out_q.put(("sources", wiki_sources))
            if ctx:
                system.append({"role": "system", "content":
                    f"The user is reading {ctx['title']}. Below is the text of {ctx['label']}"
                    + (" (excerpts spread across it, because it is long)" if ctx["sampled"] else "")
                    + ". Work ONLY from this text. When the user asks to be quizzed: ask ONE question at "
                    "a time (events, characters, details, why things happen), wait for their answer, "
                    "then say what was right and what was off, and quote the line that shows it. "
                    "Don't reveal anything that happens later in the book. If the user asks about "
                    "something this text doesn't cover, say so.\n\n"
                    f"--- {ctx['title']}, {ctx['label']} ---\n{ctx['text']}\n--- end ---"})
                out_q.put(("sources", wiki_sources + [f"{ctx['title']}, {ctx['label']}"]))
            if use_notes and not ctx:
                out_q.put(("status", "Checking your notes..."))
                self.notes.refresh(progress=lambda s: out_q.put(("status", s)))
                own = f"Chats/{chat_id}.md" if chat_id else None
                hits = [h for h in self.notes.search(question, k=5) if h[1] != own][:4]
                if hits:
                    excerpts = "\n\n".join(f"[{i}] From {rel}:\n{txt}"
                                           for i, (_, rel, txt) in enumerate(hits, 1))
                    system.append({"role": "system", "content":
                        "Below are excerpts from the user's own notes and past chats with you "
                        "that may help with their next message. Use them when they're "
                        "relevant and say where it came from, like (from biology-notes.pdf) "
                        "or (from our chat on Sep 26). If they don't help, ignore them "
                        "and answer normally.\n\n" + excerpts})
                    out_q.put(("sources", wiki_sources +
                               sorted({friendly_source(rel) for _, rel, _ in hits})))

            # 4. Ask the model
            out_q.put(("status", f"{self.nice(model)} · thinking..."))
            stream_chat(model, system + send, out_q, stop_evt,
                        num_ctx=int(self.cfg.get("context_tokens", 16384)))
            out_q.put(("done", None))
        except ArchieError as e:
            out_q.put(("error", str(e)))
        except Exception as e:  # keep the app alive no matter what
            out_q.put(("error", f"Something went wrong: {e}"))

    def _stop(self):
        if self.stop_evt:
            self.stop_evt.set()
        self._speak_now = False
        self.stop_speaking()
        self._write("  [stopped]", "sys")
        self._finish()

    def _finish(self, error=False):
        if self.reply_buf:
            self.history.append({"role": "assistant", "content": self.reply_buf})
            self._save_current_chat()
            if self._speak_now and self.speaker:
                self.speaker.flush()
            self._speak_now = False
            if self._talk_mode_send:
                self._talk_answered(self.reply_buf)
            extras = []
            spoken = self.reply_buf
            if self.sources:
                extras.append(lambda: self._w("src: " + ", ".join(self.sources), "src"))
            extras.append(lambda: self._link("read aloud", lambda: self.speak_text(spoken), "src"))
            if self.vault():
                q = self.history[-2] if len(self.history) >= 2 else {}
                question = q.get("display") or q.get("content", "")
                answer = self.reply_buf
                extras.append(lambda: self._link("save → obsidian", lambda: self.save_to_obsidian(
                    question[:80], [(question, answer)]), "src"))
            if extras:
                self._w("\n")
                for i, add in enumerate(extras):
                    if i:
                        self._w("   ·   ", "src")
                    add()
        elif error and self.history and self.history[-1]["role"] == "user":
            self.history.pop()  # so a retry doesn't send the question twice
        self._talk_mode_send = False
        self._end_span()
        self._write("\n", "abody")
        self.q = None
        self._set_busy(False)

    def _set_busy(self, busy):
        self.busy = busy
        self._style_send_btn()
        self.attach_btn.configure(state="disabled" if busy else "normal")
        self._update_status("thinking..." if busy else "")
        if busy:
            self._blink_on = False
            self.root.after(700, self._blink)
        else:
            self._owl_eyes("open")

    def _blink(self):
        """Blink every so often while thinking: eyes shut briefly, then open."""
        if not self.busy:
            self._owl_eyes("open")
            return
        self._blink_on = not self._blink_on
        self._owl_eyes("closed" if self._blink_on else "open")
        self.root.after(160 if self._blink_on else 900, self._blink)

    def _poll(self):
        q = self.q
        if q is not None:
            try:
                while self.q is q:
                    kind, val = q.get_nowait()
                    if kind == "token":
                        if not self.reply_buf:
                            val = val.lstrip()
                        self.reply_buf += val
                        self._write(val, "abody")
                        if self._speak_now and self.speaker:
                            self.speaker.feed(val)
                    elif kind == "status":
                        self.status.configure(text=val)
                    elif kind == "note":
                        self._write(val + "\n", "sys")
                    elif kind == "sources":
                        self.sources = val
                    elif kind == "book":
                        self.book_ctx = val
                    elif kind == "error":
                        self._write(val, "sys")
                        self._finish(error=True)
                    elif kind == "done":
                        self._finish()
            except queue.Empty:
                pass
        try:
            while True:
                kind, val = self.bg_q.get_nowait()
                if kind == "call":           # something a background thread wants done on screen
                    try:
                        val()
                    except Exception as e:
                        print("call failed:", e)
                elif kind == "status" and not self.busy:
                    self.status.configure(text=val)
                elif kind == "notes_done":
                    summary, problems, quiet = val
                    if not self.busy:
                        self._update_status(summary)
                    if not quiet and not self.busy:
                        self._write(f"Notes ready: {summary}.\n", "sys")
                        for p in problems[:5]:
                            self._write(p + "\n", "sys")
                elif kind == "show_me":
                    self.root.deiconify()
                    if not self.panel_visible():
                        self.show_panel()
                    self.panel.lift()
                    self.panel.focus_force()
                elif kind == "wiki_status":
                    if getattr(self, "wiki_win", None) and self.wiki_win.winfo_exists():
                        text, frac = val
                        self.wiki_status.configure(text=text)
                        if frac is not None:
                            try:
                                self.wiki_bar.configure(value=frac)
                            except tk.TclError:
                                pass
                elif kind == "wiki_plan":
                    self._wiki_preview(val)
                elif kind == "wiki_done":
                    self._wiki_finished(val)
                elif kind == "wiki_error":
                    self._write(val + "\n", "sys")
                    if getattr(self, "wiki_win", None) and self.wiki_win.winfo_exists():
                        self.wiki_status.configure(text=val)
                        try:
                            self.wiki_bar.stop()
                        except tk.TclError:
                            pass
                elif kind == "img":
                    self._img_event(val)
                elif kind.startswith("gym_"):
                    self._gym_event(kind, val)
                elif kind == "lecture_wake":
                    self._lecture_woke()
                elif kind in ("listen_note", "listen_book", "listen_error", "listen_lecture"):
                    self._listen_event(kind, val)
                elif kind == "lecture_review":
                    self._review_event(val)
                    if getattr(self, "examprep", None):
                        self.examprep.kick.set()
                elif kind == "exam_prep":
                    self._exam_prep_event(val)
                elif kind == "talk_done":
                    self._talk_done(val)
                elif kind == "voice_progress":
                    if not self.busy:
                        self.status.configure(text=f"typing out voice note... {int(val * 100)}%")
                elif kind == "voice_done":
                    if not self.busy:
                        self._update_status()
                    self.show_transcript(*val)
                elif kind == "voice_error":
                    self._write(val + "\n", "sys")
                    if not self.busy:
                        self._update_status()
                elif kind == "call":
                    try:
                        val()
                    except tk.TclError:
                        pass
                elif kind == "handwriting_done":
                    self._handwriting_done(*val)
                elif kind == "obsidian_saved":
                    self._obsidian_saved(*val)
                elif kind == "brief_fill":
                    tag, result = val
                    self._brief_to_daily(tag, result)
                    if isinstance(result, tuple) and result and result[0] == "quiz":
                        self._brief_quiz(tag, *result[1:])
                    else:
                        self._fill(tag, result)
                elif kind == "hotkey":
                    if val == "chat":
                        self.hotkey_chat()
                    elif val == "snip":
                        self.start_snip()
                    elif val == "voice":
                        self.toggle_record()
                    elif val == "talk":
                        self.toggle_talk()
                    elif val == "recap":
                        self.hotkey_recap()
                    elif val == "quiet":
                        self.toggle_quiet()
                    elif val == "mic":
                        self.toggle_mic()
                elif kind == "hotkey_failed":
                    for name, combo, why in val:
                        what = {"chat": "show/hide Archie", "snip": "snip the screen",
                                "voice": "record a voice note",
                                "talk": "talk to Archie",
                                "recap": "start the evening recap",
                                "quiet": "mute Archie",
                                "mic": "turn your mic off in talk"}.get(name, name)
                        self._write(f"The hotkey {pretty_combo(combo)} (to {what}) didn't work: "
                                    f"{why}. You can pick another in archie_config.json "
                                    f"(\"hotkey_{name}\"), then restart Archie.\n", "sys")
                elif kind == "notes_error":
                    if not self.busy:
                        self._write(val + "\n", "sys")
                        self._update_status()
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    # ----- lifecycle --------------------------------------------------------

    def quit(self):
        if self.stop_evt:
            self.stop_evt.set()
        if self.recorder.recording:
            self.recorder.stop()   # the recording is kept in the Recordings folder
        try:
            self.imager.stop()
        except Exception:
            pass
        self.hotkeys.stop()
        try:
            if self.world:
                self.world.shutdown()
        except Exception:
            pass
        self.cfg["bubble_x"], self.cfg["bubble_y"] = self._bubble_home()
        save_config(self.cfg)
        self.root.destroy()

    def run(self):
        if self.world:
            self.root.after(45000, self._world_alerts)
        self.root.mainloop()


SINGLE_PORT = 53917   # a private "doorbell" on this PC only, so just one Archie runs


def claim_single_instance(message=b"show"):
    """Returns a listening socket if we're the only Archie, or None if another
    Archie is already running (in which case we've passed it the message)."""
    import socket
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if sys.platform == "win32":
        srv.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", 0x0004), 1)
    try:
        srv.bind(("127.0.0.1", SINGLE_PORT))
        srv.listen(2)
        return srv
    except OSError:
        srv.close()
        try:
            with socket.create_connection(("127.0.0.1", SINGLE_PORT), timeout=2) as c:
                c.sendall(message)
        except OSError:
            pass
        return None


def listen_for_others(srv, on_show, on_wake=lambda: None):
    """Background: when someone starts Archie again, bring this one forward
    (or, from the after-class wake-up task, go type up the lecture)."""
    def run():
        while True:
            try:
                conn, _ = srv.accept()
                with conn:
                    msg = conn.recv(16)
                    if msg.startswith(b"show"):
                        on_show()
                    elif msg.startswith(b"wake"):
                        on_wake()
            except OSError:
                return
    threading.Thread(target=run, daemon=True).start()


def main():
    if sys.platform == "win32":
        try:  # crisp text on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    woke = "--lecture-wake" in sys.argv
    srv = claim_single_instance(b"wake" if woke else b"show")
    if srv is None:
        return   # Archie is already running; it has been brought to the front (or told to wake)
    app = ArchieApp()
    listen_for_others(srv, lambda: app.bg_q.put(("show_me", None)),
                      lambda: app.bg_q.put(("lecture_wake", None)))
    if woke:
        app.root.after(5000, app._lecture_woke)
    if "--world" in sys.argv:
        app.root.after(4000, app.show_world)
    app.run()
    os._exit(0)      # make sure nothing (like the globe's web server) keeps an old Archie running after Quit


def crash_report():
    """If Archie can't start, say why instead of silently not opening."""
    import traceback
    err = traceback.format_exc()
    log = os.path.join(APP_DIR, "archie_error.log")
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now():%Y-%m-%d %H:%M:%S} ---\n{err}")
    except OSError:
        pass
    try:
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror("Archie couldn't start",
                             "Something went wrong while starting Archie.\n\n"
                             + err.strip().splitlines()[-1][:300]
                             + f"\n\nThe full details are in:\n{log}")
        r.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        crash_report()
