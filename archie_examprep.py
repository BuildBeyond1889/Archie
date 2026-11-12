"""
archie_examprep.py - flashcards from every lecture, and a study guide before every exam.

Flashcards
  Each lecture note becomes about 10 cards in a deck named after the class ("BIO 101") in Archie's Study
  (spaced repetition: they come back when you're about to forget them). When the lecture's review is
  built (the professor's material lined up with the recording), up to 6 more cards come from what the
  professor stressed in class. Each lecture is carded once.

Exam prep
  An exam, test or quiz on your calendar whose title names a class ("BIO 101 Midterm") gets a note in
  Lectures/<class>/: "Exam prep · <title> (<date>).md". It starts 3 weeks before an exam (2 for a test,
  1 for a quiz), covers every lecture since that class's previous exam, and is rebuilt as lectures come in:
      a countdown · where to start · flagged in class (quoted, with times) · your marks · lecture by lecture
      · gaps (in the professor's material, never covered in class) · terms · practice questions · a mock
      exam saved in Archie (Study → Exams) · the class's flashcard deck
"""

import datetime
import hashlib
import json
import os
import re
import sys
import threading
import time

WINDOW = {"exam": 21, "test": 14, "quiz": 7}
LOOKBACK = 150                       # days to look back for the class's previous exam
SUFFIX_REVIEW = (" (review).md", " (review, rebuilt).md")


def _read(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _safe(s, fallback="Note"):
    return re.sub(r'[<>:"/\\|?*#^\[\]]', " ", str(s or "")).strip() or fallback


def _section(text, head):
    """The lines of a '## head' section (up to the next '## ')."""
    m = re.search(r"^## " + re.escape(head) + r"\s*\n(.*?)(?=^## |\Z)", text or "", re.S | re.M)
    return [l.rstrip() for l in m.group(1).splitlines() if l.strip()] if m else []


def class_of(title, notes, classes):
    """Which class an exam is for: the class whose name is in its title (or notes), longest match first."""
    hay = f"{title} {notes or ''}".lower()
    for c in sorted(classes, key=len, reverse=True):
        if c and c.lower() in hay:
            return c
    return None



def _cool(name, default=False):
    """Ask archie_cool (game mode, away, night) when Archie has loaded it; otherwise carry on as before."""
    m = sys.modules.get("archie_cool")
    try:
        return getattr(m, name)() if m else default
    except Exception:
        return default

class ExamPrep:
    def __init__(self, get_base, calendar, chat, model, study, exams, state_path, wait=lambda: None,
                 report=lambda k, v: None):
        self.get_base = get_base          # () -> vault (or Archie's Notes)
        self._cal = calendar              # the calendar, or () -> the calendar (Archie makes it a little later)
        self.chat = chat
        self.model = model                # () -> model name
        self.study = study
        self.exams = exams
        self.state_path = state_path
        self.wait = wait
        self.report = report
        self.kick = threading.Event()
        self.last_error = None
        try:
            with open(state_path, encoding="utf-8") as f:
                self.state = json.load(f)
        except (OSError, ValueError):
            self.state = {}
        self.state.setdefault("carded", {})
        self.state.setdefault("preps", {})

    @property
    def calendar(self):
        return self._cal() if callable(self._cal) and not hasattr(self._cal, "load") else self._cal

    def _save(self):
        tmp = self.state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False)
        os.replace(tmp, self.state_path)

    def start(self):
        threading.Thread(target=self._loop, daemon=True, name="exam-prep").start()
        return self

    def _loop(self):
        time.sleep(120)
        while True:
            try:
                if not _cool("game") and not _cool("busy"):   # not during a game, a talk or an answer
                    self.run_once()
                self.last_error = None
            except Exception as e:                   # never take Archie down
                self.last_error = f"{type(e).__name__}: {e}"
            self.kick.wait(30 * 60)
            self.kick.clear()

    # ----- the class folders --------------------------------------------------------------------------
    def _classes(self):
        out = []
        for e in self.calendar.load():
            if e.get("kind") in ("class", "lab") and e.get("title") and e["title"] not in out:
                out.append(e["title"])
        return out

    def _lectures(self, class_dir):
        import archie_review as review
        out = []
        if not os.path.isdir(class_dir):
            return out
        for fn in sorted(os.listdir(class_dir)):
            if not fn.endswith(".md") or fn.endswith(SUFFIX_REVIEW) or fn.endswith("(mind map).md") \
                    or fn.startswith("Exam prep"):
                continue
            lec = review.read_lecture(os.path.join(class_dir, fn))
            if lec:
                rv = next((os.path.join(class_dir, lec["stem"] + s) for s in SUFFIX_REVIEW
                           if os.path.exists(os.path.join(class_dir, lec["stem"] + s))), None)
                lec["review"] = rv
                out.append(lec)
        return out

    def run_once(self, today=None):
        today = today or datetime.date.today()
        base = self.get_base()
        if not base:
            return {}
        classes = self._classes()
        done = {"cards": 0, "preps": []}
        for klass in classes:
            d = os.path.join(base, "Lectures", _safe(klass, "Other"))
            for lec in self._lectures(d):
                done["cards"] += self._cards(klass, lec)
        for ev, day in self._exams(today):
            klass = class_of(ev["title"], ev.get("notes"), classes)
            if not klass:
                continue
            out = self._prep(base, klass, ev, day, today)
            if out:
                done["preps"].append(out)
        return done

    # ----- flashcards -----------------------------------------------------------------------------------
    def _cards(self, klass, lec):
        """Cards from a lecture note (once), and from its review (once). Returns how many were added."""
        import archie_study as study
        key = os.path.normcase(lec["path"])
        rec = self.state["carded"].setdefault(key, [])
        added = 0
        src = f"{klass} · {lec['date'].isoformat()} {lec['title']}"
        if "lecture" not in rec:
            text = _read(lec["path"]).split("## Transcript")[0]
            text = re.sub(r"```mermaid.*?```", "", text, flags=re.S)
            if len(text.split()) > 60:
                self.wait()
                self.report("status", f"flashcards for {klass}: {lec['title']}...")
                cards = study.make_cards(self.chat, self.model(), text, f"a {klass} lecture: {lec['title']}", n=10)
                added += self.study.add_cards(klass, cards, source=src)[1] if cards else 0
            rec.append("lecture")
            self._save()
        if lec.get("review") and "review" not in rec:
            rt = _read(lec["review"])
            stressed = "\n".join(_section(rt, "Flagged in class") + _section(rt, "Said in class, not in the material"))
            if len(stressed.split()) > 25:
                self.wait()
                cards = study.make_cards(self.chat, self.model(), stressed,
                                         f"what the professor stressed in a {klass} lecture", n=6)
                added += self.study.add_cards(klass, cards, source=src + " (review)")[1] if cards else 0
            rec.append("review")
            self._save()
        return added

    # ----- exams on the calendar ------------------------------------------------------------------------
    def _exams(self, today):
        """[(event, date)] exams/tests/quizzes coming up inside their window (and on the day itself)."""
        out, seen = [], set()
        for k in range(0, max(WINDOW.values()) + 1):
            day = today + datetime.timedelta(days=k)
            try:
                evs = self.calendar.on(day)
            except Exception:
                evs = []
            for e in evs:
                kind = e.get("kind")
                if kind in WINDOW and k <= WINDOW[kind] and (e.get("id"), day) not in seen:
                    seen.add((e.get("id"), day))
                    out.append((e, day))
        return out

    def _prev_exam(self, klass, day, classes):
        for k in range(1, LOOKBACK):
            d = day - datetime.timedelta(days=k)
            try:
                evs = self.calendar.on(d)
            except Exception:
                evs = []
            if any(e.get("kind") in ("exam", "test") and class_of(e.get("title", ""), e.get("notes"), classes) == klass
                   for e in evs):
                return d
        return None

    def _prep(self, base, klass, ev, day, today):
        classes = self._classes()
        prev = self._prev_exam(klass, day, classes)
        class_dir = os.path.join(base, "Lectures", _safe(klass, "Other"))
        lecs = [l for l in self._lectures(class_dir) if (prev is None or l["date"] > prev) and l["date"] <= day]
        kind = ev.get("kind")
        title = ev.get("title") or f"{klass} {kind}"
        name = f"Exam prep · {_safe(title)} ({day:%b} {day.day})"
        path = os.path.join(class_dir, name + ".md")
        key = f"{ev.get('id')}|{day.isoformat()}"
        rec = self.state["preps"].setdefault(key, {})
        sig = hashlib.sha1(json.dumps([(l["path"], os.path.getmtime(l["path"]),
                                        l.get("review") and os.path.getmtime(l["review"])) for l in lecs]).encode()).hexdigest()

        # what each lecture gives the guide
        flagged, gaps, terms, questions, per, marks = [], [], [], [], [], []
        import archie_review as review
        for l in lecs:
            text = _read(l["path"])
            kp = [re.sub(r"\s*`[\d:]+`\s*$", "", x[2:]) for x in _section(text, "Key points") if x.startswith("- ")]
            per.append((l, kp[:6]))
            for row in _section(text, "Terms")[2:]:
                m = re.match(r"^\| \*\*(.+?)\*\* \| (.*) \|$", row)
                if m:
                    terms.append((m.group(1), m.group(2), l["stem"]))
            questions += [(re.sub(r"^\d+\.\s*", "", q), l["stem"]) for q in _section(text, "Questions to review")
                          if re.match(r"^\d+\.", q)]
            if l.get("review"):
                rt = _read(l["review"])
                rstem = os.path.splitext(os.path.basename(l["review"]))[0]
                flagged += [(x[2:], l["stem"], rstem) for x in _section(rt, "Flagged in class") if x.startswith("- ")]
                gaps += [(x[2:], rstem) for x in _section(rt, "In the material, not mentioned in class") if x.startswith("- ")]
            else:
                for t, q in review.flagged(l["paras"]):
                    flagged.append((f"🎙 `{review.clock(t)}` “{q}”", l["stem"], None))
            try:
                for t, lab in review.marks_for(class_dir, l):
                    marks.append((t, lab, l["stem"]))
            except Exception:
                pass

        # a short "start here" and a mock exam: made again only when the lectures change (at most daily)
        if rec.get("sig") != sig and rec.get("made") != today.isoformat() and lecs:
            self.wait()
            focus = []
            try:
                from archie_review import _json
                raw = self.chat(self.model(),
                                f"A student has a {kind} for {klass} on {day:%A %B} {day.day}. From these lecture key points and "
                                "the moments the professor flagged in class, write the 5 most important things to study "
                                "first, most important first, each one short line naming the topic. Use ONLY this material. "
                                "Reply JSON only: {\"focus\": [\"...\"]}\n\nFLAGGED:\n" +
                                "\n".join(f[0] for f in flagged[:30]) + "\n\nKEY POINTS:\n" +
                                "\n".join(f"- {p}" for _, kp in per for p in kp)[:9000],
                                max_tokens=500, timeout=300, json_mode=True, temperature=0.2)
                focus = [str(x).strip() for x in (_json(raw).get("focus") or []) if str(x).strip()][:6]
            except Exception:
                focus = []
            exam_id = rec.get("exam_id")
            try:
                import archie_exam
                material = "\n\n".join(_read(l["path"]).split("## Transcript")[0] for l in lecs)
                material += "\n\nFlagged in class:\n" + "\n".join(f[0] for f in flagged)
                n = {"exam": 20, "test": 15, "quiz": 10}.get(kind, 12)
                qs = archie_exam.make_exam(self.chat, self.model(), material, f"{klass}: {title}",
                                           kind="midterm" if kind == "exam" else "quiz", n=n)
                if qs:
                    ex = self.exams.new(f"Practice · {title}", "midterm" if kind == "exam" else "quiz", qs,
                                        {"exam": 75, "test": 50, "quiz": 20}.get(kind, 40), f"{len(lecs)} {klass} lectures")
                    exam_id = ex["id"]
            except Exception:
                pass
            rec.update(sig=sig, made=today.isoformat(), focus=focus, exam_id=exam_id)
            self._save()

        # the note (rewritten when anything in it changes, so the countdown stays right)
        left = (day - today).days
        when = (f"{ev.get('time')} " if ev.get("time") else "")
        tag = re.sub(r"[^a-z0-9]+", "-", klass.lower()).strip("-")
        lines = ["---", f"tags: [exam-prep, {tag}]", f'class: "{klass}"', f"exam: {day.isoformat()}", "---", "",
                 f"# {title}", "",
                 f"> [!danger] {'Today' if left == 0 else 'Tomorrow' if left == 1 else f'In {left} days'} · "
                 f"{day:%A %B} {day.day}{(' · ' + when.strip()) if when else ''}",
                 f"> Covers {len(lecs)} lecture{'s' if len(lecs) != 1 else ''}" +
                 (f" since the last exam ({prev:%b} {prev.day})" if prev else "") +
                 ". Archie rebuilds this guide as lectures come in.", ""]
        if not lecs:
            lines += ["*No lectures recorded for this class in that stretch yet. Record them in the Class tab and they'll "
                      "show up here.*", ""]
        if rec.get("focus"):
            lines += ["## Start here", ""] + [f"{i}. {x}" for i, x in enumerate(rec["focus"], 1)] + [""]
        if flagged:
            lines += ["## Flagged in class", "What the professor stressed: exam hints, \"know this\", homework.", ""]
            lines += [f"- {txt} · [[{stem}]]" for txt, stem, _ in flagged[:40]] + [""]
        if marks:
            lines += ["## Your marks", ""] + [f"- ⭐ `{review.clock(t)}` {lab} · [[{stem}]]" for t, lab, stem in marks[:30]] + [""]
        if per:
            lines += ["## Lecture by lecture", ""]
            for l, kp in per:
                rv = os.path.splitext(os.path.basename(l["review"]))[0] if l.get("review") else None
                lines += [f"### [[{l['stem']}|{l['title']}]] · {l['date']:%b} {l['date'].day}" +
                          (f" · [[{rv}|review]]" if rv else ""), ""]
                lines += [f"- {p}" for p in kp] or ["- *(no key points)*"]
                lines.append("")
        if gaps:
            lines += ["## Gaps: in the material, never covered in class", "Read these yourself, or ask about them.", ""]
            lines += [f"- {g} · [[{r}|review]]" for g, r in gaps[:40]] + [""]
        if terms:
            lines += ["## Terms", "", "| Term | Meaning | Lecture |", "|---|---|---|"]
            seen = set()
            for t, m, stem in terms:
                if t.lower() in seen:
                    continue
                seen.add(t.lower())
                lines.append(f"| **{t}** | {m} | [[{stem}]] |")
            lines.append("")
        lines += ["## Practice", ""]
        if rec.get("exam_id"):
            lines.append(f"- **Mock {kind}:** in Archie, Study → Exams → *Practice · {title}* (timed, graded like the real thing).")
        try:
            d_ = self.study.load(klass)
            n_cards = len(d_["cards"]) if d_ else 0
        except Exception:
            n_cards = 0
        if n_cards:
            lines.append(f"- **Flashcards:** the *{klass}* deck in Archie's Study ({n_cards} cards); a few minutes a day beats one long night.")
        if questions:
            lines += ["", "Questions from your lectures:", ""] + [f"- {q} · [[{s}]]" for q, s in questions[:25]]
        lines.append("")
        md = "\n".join(lines)
        if _read(path) != md:
            os.makedirs(class_dir, exist_ok=True)
            with open(path + ".tmp", "w", encoding="utf-8") as f:
                f.write(md)
            os.replace(path + ".tmp", path)
            if not rec.get("announced"):
                rec["announced"] = True
                self._save()
                self.report("exam_prep", (klass, title, path, left))
        return path


def countdowns(calendar, today=None, days=45):
    """Upcoming exams, tests and quizzes as countdown items for the phone and laptop Today tabs."""
    today = today or datetime.date.today()
    out, seen = [], set()
    for k in range(0, days + 1):
        d = today + datetime.timedelta(days=k)
        try:
            evs = calendar.on(d)
        except Exception:
            evs = []
        for e in evs:
            if e.get("kind") in WINDOW and (e.get("id"), d) not in seen:
                seen.add((e.get("id"), d))
                out.append({"date": d.isoformat(), "what": e.get("title") or e["kind"], "exam": e["kind"]})
    return out
