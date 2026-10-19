"""
archie_gym.py - the drawing gym: timed reference practice.

Drop pictures into the "Drawing Gym" folder (D:/Archie/Drawing Gym). Archie looks at each
new one with the vision model and sorts it (figure, faces, hands, animals, landscapes...).
Before a session you pick what to draw, how long each picture stays up (or no timer), and
how many. Every session is logged so Archie can count your streak and poses per week.

A subfolder named after a category (e.g. "Drawing Gym/hands") overrides the sorting.
What Archie decided is kept in gym.json in the folder; right-click a picture during a
session to move it to another category.
"""

import datetime
import io
import json
import os
import random
import re
import threading
import time
import urllib.request

EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif")

# key, button label, what the vision model is told it means
CATEGORIES = [
    ("figure", "figure", "a whole human body or pose: gesture, figure drawing, dance, sports, people standing or in action"),
    ("faces", "faces", "a head, face or portrait (shoulders up)"),
    ("hands", "hands & feet", "a close-up of hands or feet"),
    ("animals", "animals", "an animal or creature is the main subject"),
    ("landscape", "landscapes", "outdoor nature scenery: mountains, fields, trees, water, sky"),
    ("places", "places", "streets, cities, buildings, rooms and interiors"),
    ("objects", "objects", "still life: everyday objects, food, plants, tools, props"),
    ("vehicles", "vehicles & mechs", "cars, planes, ships, robots, machines, weapons, armor"),
    ("other", "other", "anything else: abstract, patterns, art styles, text"),
]
KEYS = [c[0] for c in CATEGORIES]
LABELS = {c[0]: c[1] for c in CATEGORIES}

TIMES = [(30, "30 s"), (60, "1 min"), (120, "2 min"), (300, "5 min"), (600, "10 min"), (0, "no timer")]
COUNTS = [5, 10, 20, 0]          # 0 = every picture that fits
# the classic figure-class warm-up: lots of quick gestures, then longer poses
LADDER = [30] * 8 + [60] * 4 + [120] * 2 + [300] * 2

SORT_PROMPT = """This picture is a drawing reference. Which ONE category fits it best?
{options}
Return JSON only: {{"category": "<one of: {keys}>", "what": "<3 to 8 words saying what it shows>"}}"""


def _folder_category(folder, path):
    rel = os.path.relpath(os.path.dirname(path), folder)
    for part in rel.replace("\\", "/").split("/"):
        p = part.strip().lower()
        for key, label, _ in CATEGORIES:
            if p in (key, label.lower()) or p.rstrip("s") == key.rstrip("s"):
                return key
    return None


class Gym:
    def __init__(self, folder, log_path, vision_model, ollama_url, busy=lambda: False):
        self.folder = folder
        self.log_path = log_path
        self.vision_model = vision_model          # () -> model name or None
        self.ollama_url = ollama_url
        self.busy = busy
        self.lock = threading.Lock()
        self.sorting = threading.Event()
        self.index = self._load_index()
        self.last_error = ""

    # ----- the pictures ---------------------------------------------------------

    @property
    def index_path(self):
        return os.path.join(self.folder, "gym.json")

    def _load_index(self):
        try:
            with open(self.index_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save_index(self):
        try:
            os.makedirs(self.folder, exist_ok=True)
            tmp = self.index_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.index, f, indent=1, ensure_ascii=False)
            os.replace(tmp, self.index_path)
        except OSError:
            pass

    def _key(self, path):
        return os.path.relpath(path, self.folder).replace("\\", "/")

    def pictures(self):
        """[(path, category or None)] for everything in the folder (subfolders too)."""
        out = []
        if not os.path.isdir(self.folder):
            return out
        for dp, dns, fns in os.walk(self.folder):
            dns[:] = [d for d in dns if not d.startswith(".")]
            for fn in sorted(fns):
                if not fn.lower().endswith(EXT):
                    continue
                path = os.path.join(dp, fn)
                cat = _folder_category(self.folder, path)
                if cat is None:
                    info = self.index.get(self._key(path))
                    if info and info.get("mtime") == int(os.path.getmtime(path)):
                        cat = info.get("category")
                out.append((path, cat))
        return out

    def counts(self):
        c = {k: 0 for k in KEYS}
        unsorted = 0
        for _, cat in self.pictures():
            if cat in c:
                c[cat] += 1
            else:
                unsorted += 1
        return c, unsorted

    def describe(self, path):
        info = self.index.get(self._key(path)) or {}
        return info.get("what", "")

    def set_category(self, path, cat):
        with self.lock:
            info = self.index.setdefault(self._key(path), {})
            info.update(category=cat, mtime=int(os.path.getmtime(path)), by="you")
            self._save_index()

    def pick(self, cats, n, shuffle=True):
        """Pictures in the chosen categories (all if cats is empty), shuffled, n of them (0 = all)."""
        pool = [p for p, c in self.pictures() if not cats or c in cats]
        if shuffle:
            random.shuffle(pool)
        return pool[:n] if n else pool

    # ----- sorting new pictures with the vision model ------------------------------

    def sort_new(self, report=lambda kind, val: None):
        """Background: look at every picture Archie hasn't sorted yet (one at a time,
        pausing while you're chatting)."""
        if self.sorting.is_set():
            return
        self.sorting.set()

        def run():
            done = 0
            try:
                todo = [p for p, c in self.pictures() if c is None]
                if not todo:
                    return
                model = self.vision_model()
                if not model:
                    self.last_error = ("Sorting pictures needs the Vision model (gemma3:4b). "
                                       "Run Get Models.bat, or pick categories by subfolder.")
                    report("gym_error", self.last_error)
                    return
                for path in todo:
                    while self.busy():
                        time.sleep(2)
                    report("gym_status", f"sorting drawing references... {done + 1} of {len(todo)}")
                    try:
                        cat, what = self._classify(model, path)
                    except Exception as e:
                        self.last_error = f"Couldn't sort {os.path.basename(path)}: {e}"
                        report("gym_error", self.last_error)
                        return
                    with self.lock:
                        self.index[self._key(path)] = {"category": cat, "what": what,
                                                       "mtime": int(os.path.getmtime(path))}
                        self._save_index()
                    done += 1
                    report("gym_sorted", (path, cat))
            finally:
                self.sorting.clear()
                report("gym_done", done)
        threading.Thread(target=run, daemon=True).start()

    def _classify(self, model, path):
        import base64
        from PIL import Image, ImageOps
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((640, 640))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode()
        options = "\n".join(f"- {k}: {desc}" for k, _, desc in CATEGORIES)
        body = {"model": model, "stream": False, "format": "json",
                "options": {"temperature": 0.1, "num_predict": 80},
                "messages": [{"role": "user", "images": [b64],
                              "content": SORT_PROMPT.format(options=options, keys=", ".join(KEYS))}]}
        req = urllib.request.Request(self.ollama_url + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            text = json.load(r).get("message", {}).get("content", "")
        try:
            data = json.loads(text)
        except ValueError:
            m = re.search(r"\{.*\}", text, re.S)
            data = json.loads(m.group(0)) if m else {}
        cat = str(data.get("category", "")).strip().lower()
        if cat not in KEYS:
            cat = next((k for k in KEYS if k in cat), "other")
        return cat, str(data.get("what", "")).strip()[:80]

    # ----- the log: streak and poses per week ------------------------------------------

    def _load_log(self):
        try:
            with open(self.log_path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def record(self, poses, seconds, cats):
        if poses <= 0:
            return
        log = self._load_log()
        log.append({"date": datetime.date.today().isoformat(),
                    "at": datetime.datetime.now().strftime("%H:%M"),
                    "poses": int(poses), "seconds": int(seconds), "cats": sorted(cats)})
        try:
            with open(self.log_path, "w", encoding="utf-8") as f:
                json.dump(log[-2000:], f, indent=1)
        except OSError:
            pass

    def stats(self, today=None):
        """{'streak': days in a row, 'week_poses', 'week_minutes', 'today_poses', 'total_poses'}"""
        today = today or datetime.date.today()
        log = self._load_log()
        days = {}
        for e in log:
            days.setdefault(e.get("date"), [0, 0])
            days[e["date"]][0] += e.get("poses", 0)
            days[e["date"]][1] += e.get("seconds", 0)
        streak, d = 0, today
        if today.isoformat() not in days:          # today not done yet: the streak is still alive
            d = today - datetime.timedelta(days=1)
        while d.isoformat() in days:
            streak += 1
            d -= datetime.timedelta(days=1)
        monday = today - datetime.timedelta(days=today.weekday())
        wk = [v for k, v in days.items() if k and k >= monday.isoformat()]
        return {"streak": streak,
                "week_poses": sum(v[0] for v in wk),
                "week_minutes": (sum(v[1] for v in wk) + 30) // 60,
                "today_poses": days.get(today.isoformat(), [0, 0])[0],
                "total_poses": sum(v[0] for v in days.values())}


def plan(picks, seconds, ladder=False):
    """[(path, seconds)] for a session. With the ladder, lengths come from LADDER."""
    if ladder:
        return [(p, s) for p, s in zip(picks, LADDER)]
    return [(p, seconds) for p in picks]


def fmt(secs):
    secs = max(0, int(secs))
    return f"{secs // 60}:{secs % 60:02d}"
