"""
archie_study.py - flashcards with spaced repetition, written like a great professor.

  * Decks live in D:/Archie/Study as plain JSON (one file per deck).
  * make_cards() turns notes, a book chapter, a chat or a topic into cards that
    test understanding (why / how / apply-it), not just definitions.
  * schedule() is SM-2 style spaced repetition: a card you know comes back
    later and later (1 day, 3, 8, 3 weeks...); one you miss comes back soon.
  * grade() lets Archie check an answer you typed and say what was right.
"""

import datetime
import json
import os
import re
import threading
import uuid

NEW_PER_DAY = 20            # new cards introduced per day (keeps reviews manageable)

CARD_PROMPT = """You are writing flashcards for spaced repetition, like a brilliant MIT \
professor who wants the student to truly UNDERSTAND the material, not just memorize words.

Rules:
- One idea per card (atomic). The question must make sense on its own (never say "in the text").
- Mix card types: "why" and "how" questions, cause and effect, compare/contrast, \
"what goes wrong if...", small apply-it problems with real numbers when the topic allows, \
and definitions only for truly essential terms.
- Answers: short and precise (1-3 sentences), including the key reason, not just the fact.
- Stay faithful to the material below. Do NOT invent facts that aren't supported by it \
(for a topic with no material, use well-established knowledge only).
- Make about {n} cards, most important ideas first.

Return JSON only: {{"cards": [{{"q": "question", "a": "answer"}}]}}

Material ({what}):
{text}"""

GRADE_PROMPT = """You are a fair, encouraging professor checking a student's flashcard answer.

Question: {q}
Correct answer: {a}
Student's answer: {user}

Judge whether the student understood the key idea (wording doesn't need to match; \
missing the key reason counts as partly right). Return JSON only:
{{"verdict": "right" | "partly" | "wrong",
  "feedback": "1-2 sentences: what they got right, what was missing or off, and why",
  "grade": 1 | 2 | 3 | 4}}
(grade: 1 = didn't know it, 2 = partly / struggled, 3 = right, 4 = right and complete, instantly)"""


def _today():
    return datetime.date.today()


def safe_name(name, max_len=70):
    n = re.sub(r'[<>:"/\\|?*\n\r\t]', " ", name).strip()
    n = re.sub(r"\s+", " ", n)
    return (n[:max_len].rstrip(" .") or "Deck")


class Study:
    def __init__(self, folder):
        self.folder = folder
        self.lock = threading.Lock()
        os.makedirs(folder, exist_ok=True)

    # ----- storage ---------------------------------------------------------------

    def _path(self, deck):
        return os.path.join(self.folder, safe_name(deck) + ".json")

    def decks(self):
        out = []
        try:
            names = sorted(os.listdir(self.folder))
        except OSError:
            return out
        for fn in names:
            if fn.endswith(".json"):
                d = self.load(fn[:-5])
                if d:
                    out.append(d)
        return out

    def load(self, deck):
        try:
            with open(self._path(deck), encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict) or not isinstance(d.get("cards"), list):
                return None           # not a deck (some other file that ended up in this folder)
            d.setdefault("name", deck)
            d.setdefault("cards", [])
            return d
        except (OSError, ValueError):
            return None

    def save(self, d):
        with self.lock:
            tmp = self._path(d["name"]) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=1, ensure_ascii=False)
            os.replace(tmp, self._path(d["name"]))

    def add_cards(self, deck, cards, source=""):
        d = self.load(deck) or {"name": safe_name(deck), "created": _today().isoformat(),
                                "source": source, "cards": []}
        have = {c["q"].strip().lower() for c in d["cards"]}
        added = 0
        for c in cards:
            q, a = (c.get("q") or "").strip(), (c.get("a") or "").strip()
            if not q or not a or q.lower() in have:
                continue
            have.add(q.lower())
            d["cards"].append({"id": uuid.uuid4().hex[:10], "q": q, "a": a, "source": source,
                               "created": _today().isoformat(), "due": _today().isoformat(),
                               "interval": 0, "ease": 2.5, "reps": 0, "lapses": 0, "last": None})
            added += 1
        self.save(d)
        return d["name"], added

    def delete_card(self, deck, card_id):
        d = self.load(deck)
        if d:
            d["cards"] = [c for c in d["cards"] if c["id"] != card_id]
            self.save(d)

    def update_card(self, deck, card):
        d = self.load(deck)
        if not d:
            return
        for i, c in enumerate(d["cards"]):
            if c["id"] == card["id"]:
                d["cards"][i] = {k: v for k, v in card.items() if k != "deck"}
        self.save(d)

    # ----- what's due -------------------------------------------------------------

    def due(self, deck=None, today=None, new_limit=NEW_PER_DAY):
        """Cards to study now: everything due, plus up to new_limit brand-new cards."""
        today = (today or _today()).isoformat()
        reviews, new = [], []
        for d in self.decks():
            if deck and d["name"].lower() != deck.lower():
                continue
            for c in d["cards"]:
                c = dict(c, deck=d["name"])
                if c["reps"] == 0 and c["last"] is None:
                    new.append(c)
                elif c["due"] <= today:
                    reviews.append(c)
        new_done_today = sum(1 for d in self.decks() for c in d["cards"]
                             if c.get("first_seen") == today)
        new = new[:max(0, new_limit - new_done_today)]
        reviews.sort(key=lambda c: c["due"])
        return reviews + new

    def counts(self):
        due = self.due()
        new = sum(1 for c in due if c["reps"] == 0 and c["last"] is None)
        return len(due) - new, new

    def find_deck(self, words):
        words = words.lower().strip()
        if not words:
            return None
        for d in self.decks():
            if d["name"].lower() == words:
                return d["name"]
        for d in self.decks():
            if words in d["name"].lower():
                return d["name"]
        return None


# ---------------------------------------------------------------------------
# Spaced repetition (SM-2 style)
# ---------------------------------------------------------------------------

def schedule(card, grade, today=None):
    """grade: 1 again, 2 hard, 3 good, 4 easy. Returns the updated card."""
    today = today or _today()
    c = dict(card)
    if c.get("reps", 0) == 0 and c.get("last") is None:
        c["first_seen"] = today.isoformat()
    ease, ivl = float(c.get("ease", 2.5)), int(c.get("interval", 0))
    if grade == 1:
        c["lapses"] = c.get("lapses", 0) + 1
        c["reps"] = 0
        ease = max(1.3, ease - 0.2)
        ivl = 0                                   # again today, then tomorrow
    else:
        if c.get("reps", 0) == 0:
            ivl = {2: 1, 3: 1, 4: 3}[grade]
        elif c.get("reps", 0) == 1:
            ivl = {2: 2, 3: 3, 4: 6}[grade]
        else:
            ivl = max(ivl + 1, round(ivl * {2: 1.2, 3: ease, 4: ease * 1.3}[grade]))
        ease = max(1.3, ease + {2: -0.15, 3: 0.0, 4: 0.15}[grade])
        c["reps"] = c.get("reps", 0) + 1
    c["ease"], c["interval"] = round(ease, 2), ivl
    c["due"] = (today + datetime.timedelta(days=max(ivl, 1 if grade == 1 else ivl))).isoformat()
    c["last"] = today.isoformat()
    return c


def preview_intervals(card):
    """What each button would do, like  again: today · hard: 1d · good: 3d · easy: 6d."""
    out = {}
    for g in (1, 2, 3, 4):
        n = schedule(card, g)
        days = (datetime.date.fromisoformat(n["due"]) - _today()).days
        out[g] = "soon" if g == 1 else (f"{days}d" if days < 30 else f"{days // 30}mo")
    return out


# ---------------------------------------------------------------------------
# Talking to the model
# ---------------------------------------------------------------------------

def _json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        m = re.search(r"\{.*\}", text or "", re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except ValueError:
                return None
    return None


def make_cards(quick_chat, model, text, what, n=12, progress=lambda f: None):
    """Cards from material (long material in pieces). Returns [{'q','a'}]."""
    text = (text or "").strip()
    pieces = [text[i:i + 12000] for i in range(0, len(text), 12000)] or [""]
    pieces = pieces[:8]
    per = max(3, round(n / len(pieces)))
    cards = []
    for i, piece in enumerate(pieces):
        progress(i / len(pieces))
        out = quick_chat(model, CARD_PROMPT.format(n=per, what=what, text=piece or "(no material: "
                                                   "use well-established knowledge of the topic)"),
                         max_tokens=3000, timeout=600, json_mode=True, num_ctx=16384, temperature=0.3)
        data = _json(out) or {}
        for c in data.get("cards", []) if isinstance(data, dict) else []:
            if isinstance(c, dict) and c.get("q") and c.get("a"):
                cards.append({"q": str(c["q"]).strip(), "a": str(c["a"]).strip()})
    progress(1.0)
    return cards


def grade(quick_chat, model, q, a, user):
    out = quick_chat(model, GRADE_PROMPT.format(q=q, a=a, user=user), max_tokens=300,
                     timeout=120, json_mode=True, temperature=0.1)
    data = _json(out) or {}
    g = data.get("grade")
    try:
        g = min(4, max(1, int(g)))
    except (TypeError, ValueError):
        g = {"right": 3, "partly": 2, "wrong": 1}.get(data.get("verdict"), 2)
    return {"verdict": data.get("verdict", "partly"), "feedback": data.get("feedback", ""), "grade": g}


# ---------------------------------------------------------------------------
# Understanding "make flashcards from ..."
# ---------------------------------------------------------------------------

_CARDS_RE = re.compile(r"\b(make|create|generate|build|write|give me)\b[^.?!]*\bflash ?cards?\b"
                       r"|^\s*flash ?cards?\b|\b(make|create|generate)\b[^.?!]*\bcards?\b\s+(from|on|about|for)\b",
                       re.I)


def parse_cards_request(text):
    """None, or {'n': int, 'source': 'note'|'chat'|'files'|'book'|'topic', 'topic': str}."""
    if not _CARDS_RE.search(text):
        return None
    low = text.lower()
    m = re.search(r"\b(\d{1,3})\s*(?:flash ?)?cards?\b", low)
    n = min(60, max(3, int(m.group(1)))) if m else 12
    if re.search(r"\b(this|my|the|current|open)\s+(obsidian\s+)?(note|page)\b", low):
        return {"n": n, "source": "note", "topic": ""}
    if re.search(r"\b(that|this chat|this conversation|our chat|above|last answer|what you (just )?said)\b", low):
        return {"n": n, "source": "chat", "topic": ""}
    if re.search(r"\b(part|book|volume|chapter|chapters|epilogue)\s", low + " "):
        return {"n": n, "source": "book", "topic": ""}
    m = re.search(r"\b(?:about|on|for|of|covering)\s+(.+)$", text, re.I)
    topic = m.group(1).strip(" .!?") if m else ""
    topic = re.sub(r"^(the\s+)?(topic\s+of\s+)?", "", topic, flags=re.I)
    return {"n": n, "source": "topic" if topic else "files", "topic": topic}
