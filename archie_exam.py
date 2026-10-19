"""
archie_exam.py - mock quizzes and exams, written and graded like a professor would.

  * make_exam()  writes questions from your material: multiple choice with
    believable wrong answers, true/false, short answer and (for exams) long
    "explain" questions, easy to hard.
  * grade_written()  marks short and long answers against a rubric, with partial
    credit and a line of feedback.
  * review()  sums up what to study next.
Exams are saved in Study/Exams so you can retake them.
"""

import datetime
import json
import os
import random
import re
import uuid

QUESTION_PROMPT = """You are an experienced professor writing a {kind} for a student. \
Write {n} NEW questions from the material below.

Mix:
- about {mc}% multiple choice ("mc"): 4 options, exactly one correct, and wrong options \
that are believable (common misconceptions), never "all/none of the above"
- about {tf}% true/false ("tf")
- about {short}% short answer ("short"): answerable in 1-3 sentences
{long_line}
Difficulty: roughly 30% recall, 50% understanding/applying (small scenarios or numbers), \
20% analysis ("why", "what would happen if", compare).
Stay faithful to the material; don't test trivia or anything it doesn't support. \
Every question must make sense on its own. Don't repeat these existing questions: {avoid}

Return JSON only:
{{"questions": [
  {{"type": "mc", "q": "...", "options": ["...", "...", "...", "..."], "answer": 0, "explain": "why it's right"}},
  {{"type": "tf", "q": "...", "answer": true, "explain": "..."}},
  {{"type": "short", "q": "...", "answer": "model answer", "explain": "key points"}},
  {{"type": "long", "q": "...", "answer": "model answer", "rubric": ["point", "point", "point"]}}
]}}

Material ({what}):
{text}"""

GRADE_PROMPT = """You are a fair professor marking one exam answer. Give partial credit for \
partly-correct reasoning; wording doesn't need to match.

Question ({points} points): {q}
Model answer: {model}
{rubric}
Student's answer: {user}

Return JSON only: {{"points": <number from 0 to {points}>, "feedback": "1-2 sentences: what was \
right, what was missing or wrong, and why"}}"""

REVIEW_PROMPT = """A student just took a {kind} and got {score}%. These are the questions they \
missed or got partly right:

{missed}

In 2-4 short bullet points, tell them exactly what to review (concepts, not question numbers), \
most important first. Be direct and encouraging. Output only the bullets."""

POINTS = {"mc": 1, "tf": 1, "short": 2, "long": 5}


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


def _clean(q):
    """Keep only well-formed questions."""
    t = str(q.get("type", "")).lower()
    text = str(q.get("q", "")).strip()
    if not text:
        return None
    if t == "mc":
        opts = [str(o).strip() for o in (q.get("options") or []) if str(o).strip()]
        try:
            ans = int(q.get("answer"))
        except (TypeError, ValueError):
            a = str(q.get("answer", "")).strip()
            ans = next((i for i, o in enumerate(opts) if o == a or o.lower().startswith(a.lower() + ")")), -1)
        if len(opts) < 3 or not 0 <= ans < len(opts):
            return None
        opts = [re.sub(r"^\(?[A-Da-d][).:]\s+", "", o) for o in opts]
        return {"type": "mc", "q": text, "options": opts, "answer": ans, "explain": str(q.get("explain", ""))}
    if t in ("tf", "truefalse", "true/false"):
        a = q.get("answer")
        if isinstance(a, str):
            a = a.strip().lower() in ("true", "t", "yes")
        return {"type": "tf", "q": text, "answer": bool(a), "explain": str(q.get("explain", ""))}
    if t in ("short", "long"):
        return {"type": t, "q": text, "answer": str(q.get("answer", "")).strip(),
                "explain": str(q.get("explain", "")), "rubric": [str(r) for r in (q.get("rubric") or [])][:6]}
    return None


def make_exam(quick_chat, model, material, what, kind="quiz", n=10, progress=lambda f: None):
    """Returns a list of question dicts (with 'points')."""
    exam = kind != "quiz"
    mix = dict(mc=55, tf=15, short=20) if exam else dict(mc=60, tf=20, short=20)
    n_long = min(3, max(1, n // 10)) if exam else 0
    text = (material or "").strip()
    chunks = [text[i:i + 12000] for i in range(0, len(text), 12000)][:6] or [""]
    batches, left, qs, i = [], n - n_long, [], 0
    while left > 0:
        k = min(8, left)
        batches.append(k)
        left -= k
    if n_long:
        batches.append(0)                      # a last batch just for the long questions
    for bi, k in enumerate(batches):
        progress(bi / len(batches))
        chunk = chunks[bi % len(chunks)]
        long_line = (f"- exactly {n_long} long answer (\"long\") questions that ask to explain or apply "
                     "an idea in a paragraph, each with a 3-5 point rubric") if k == 0 else ""
        want = n_long if k == 0 else k
        mixes = dict(mc=0, tf=0, short=0) if k == 0 else mix
        prompt = QUESTION_PROMPT.format(
            kind="final exam" if kind == "final" else "midterm exam" if kind == "midterm" else kind,
            n=want, long_line=long_line, what=what,
            avoid="; ".join(q["q"][:80] for q in qs[-12:]) or "none", text=chunk or
            "(no material given: use well-established, textbook knowledge of the topic)", **mixes)
        try:
            out = quick_chat(model, prompt, max_tokens=4000, timeout=900, json_mode=True,
                             num_ctx=16384, temperature=0.5)
        except Exception:
            continue
        data = _json(out) or {}
        for q in data.get("questions", []) if isinstance(data, dict) else []:
            c = _clean(q) if isinstance(q, dict) else None
            if not c or any(c["q"].lower() == x["q"].lower() for x in qs):
                continue
            if k == 0 and c["type"] != "long":
                continue
            if k and c["type"] == "long":
                c["type"] = "short"
            c["points"] = POINTS[c["type"]]
            c["id"] = uuid.uuid4().hex[:8]
            qs.append(c)
    progress(1.0)
    random.shuffle(qs)
    qs.sort(key=lambda q: q["type"] == "long")        # long questions last, like a real exam
    return qs


def grade_written(quick_chat, model, q, user):
    if not user.strip():
        return 0.0, "No answer."
    rubric = ("Rubric (points to look for): " + "; ".join(q.get("rubric") or [])) if q.get("rubric") else ""
    out = quick_chat(model, GRADE_PROMPT.format(points=q["points"], q=q["q"], model=q.get("answer", ""),
                                                rubric=rubric, user=user),
                     max_tokens=300, timeout=180, json_mode=True, temperature=0.1)
    data = _json(out) or {}
    try:
        pts = max(0.0, min(float(q["points"]), float(data.get("points", 0))))
    except (TypeError, ValueError):
        pts = 0.0
    return round(pts * 2) / 2, str(data.get("feedback", ""))


def letter(pct):
    for cut, g in ((97, "A+"), (93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"), (77, "C+"),
                   (73, "C"), (70, "C-"), (67, "D+"), (63, "D"), (60, "D-")):
        if pct >= cut:
            return g
    return "F"


def review(quick_chat, model, kind, score, missed):
    if not missed:
        return "- Nothing missed. Try a harder exam, or one on the next chapter."
    text = "\n".join(f"- {q['q']} (correct: {answer_text(q)})" for q in missed[:12])
    try:
        return quick_chat(model, REVIEW_PROMPT.format(kind=kind, score=score, missed=text),
                          max_tokens=300, timeout=180, temperature=0.3).strip()
    except Exception:
        return ""


def answer_text(q):
    if q["type"] == "mc":
        return q["options"][q["answer"]]
    if q["type"] == "tf":
        return "True" if q["answer"] else "False"
    return q.get("answer", "")


# ---------------------------------------------------------------------------
# "make a mock exam on ..."
# ---------------------------------------------------------------------------

_REQ = re.compile(r"\b(?:mock|practice|sample|fake)\s+(?P<k1>exam|test|quiz|midterm|final)s?\b"
                  r"|\b(?:make|create|generate|give|write|build)\s+(?:me\s+)?(?:an?|\d+|a\s+new)?\s*"
                  r"(?:\d+[- ]question\s+)?(?P<k2>exam|test|quiz|midterm|final)\b\s+(?:on|about|from|for|covering|over)\b"
                  r"|^\s*(?P<k3>exam|test)\s+me\s+(?:on|about)\b", re.I)


def parse_request(text):
    """None, or {'kind', 'n', 'minutes', 'source', 'topic'}."""
    if re.match(r"\s*(what|how|why|when|where|who|is|are|does|do|can i|should|explain)\b", text, re.I):
        return None
    m = _REQ.search(text)
    if not m:
        return None
    k = (m.group("k1") or m.group("k2") or ("quiz" if m.group("k3") else "test")).lower()
    kind = "quiz" if k == "quiz" else k if k in ("midterm", "final") else "exam"
    low = text.lower()
    nm = re.search(r"\b(\d{1,3})[- ]?(?:questions?|qs?)\b", low)
    n = int(nm.group(1)) if nm else (10 if kind == "quiz" else 20)
    n = max(3, min(60, n))
    tm = re.search(r"\b(\d{1,3})[- ]?(?:minutes?|mins?)\b", low)
    minutes = int(tm.group(1)) if tm else (None if kind == "quiz" and "timed" not in low else
                                          max(10, round(n * 1.5)) if "timed" in low or kind != "quiz" else None)
    if "untimed" in low or "no timer" in low or "no time limit" in low:
        minutes = None
    if re.search(r"\b(this|my|the|current|open)\s+(obsidian\s+)?(note|page)\b", low):
        source = "note"
    elif re.search(r"\b(that|this chat|this conversation|our chat|above)\b", low):
        source = "chat"
    elif re.search(r"\b(part|book|volume|chapter|chapters|epilogue)\s", low + " "):
        source = "book"
    elif re.search(r"\bdeck\b|\bflashcards?\b", low):
        source = "deck"
    else:
        source = "topic"
    tmatch = re.search(r"\b(?:on|about|from|for|covering|over)\s+(.+)$", text, re.I)
    topic = tmatch.group(1).strip(" .!?") if tmatch else ""
    topic = re.sub(r"\b(\d{1,3}[- ]?(questions?|minutes?|mins?)|timed|untimed|no timer)\b", "", topic, flags=re.I)
    topic = re.sub(r"^(the|my)\s+", "", re.sub(r"\s{2,}", " ", topic).strip(" ,.-"), flags=re.I)
    topic = re.sub(r"\s+(deck|flashcards?)$", "", topic, flags=re.I)
    return {"kind": kind, "n": n, "minutes": minutes, "source": source, "topic": topic}


class ExamStore:
    def __init__(self, folder):
        self.folder = folder
        os.makedirs(folder, exist_ok=True)

    def save(self, exam):
        path = os.path.join(self.folder, exam["id"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(exam, f, indent=1, ensure_ascii=False)
        return path

    def new(self, title, kind, questions, minutes, source):
        exam = {"id": datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S"), "title": title, "kind": kind,
                "minutes": minutes, "source": source, "questions": questions, "attempts": []}
        self.save(exam)
        return exam

    def all(self):
        out = []
        for fn in sorted(os.listdir(self.folder), reverse=True):
            if fn.endswith(".json"):
                try:
                    with open(os.path.join(self.folder, fn), encoding="utf-8") as f:
                        out.append(json.load(f))
                except (OSError, ValueError):
                    pass
        return out
