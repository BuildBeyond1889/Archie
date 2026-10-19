"""
archie_vaultgen.py - turns a conversation into a linked Obsidian wiki.

Three levels, for any topic (a game, a religion, a robot, a story, a subject):
    Hub note  ->  Section notes (with a comparison table)  ->  Detail pages
plus cross-links between detail pages ("strong against", "part of", "influenced").

Steps:
  1. plan()   - the AI reads the conversation and lists the sections, the things
                in each section, their properties, and how things relate (JSON).
  2. You review/rename/untick things in Archie's preview window.
  3. build()  - the AI writes one page per thing, then the section pages and hub,
                and everything is saved into a new folder in your vault.
"""

import datetime
import json
import os
import re

from archie_brain import ArchieError, quick_chat
from archie_obsidian import ensure_hub, safe_filename

KIND_HINTS = """Pick sections that fit the topic. Examples (use only what fits):
- video game: Mechanics, Weapons, Armor, Enemies, Levels, Characters, Items, UI
- story / worldbuilding: Characters, Locations, Factions, Events, Themes, Objects
- religion / philosophy: Beliefs, Figures, Texts, Practices, History, Concepts
- robotics / engineering: Components, Subsystems, Sensors, Wiring, Software, Build Steps
- study subject: Concepts, Terms, Processes, Examples, Formulas, People
- anything else: whatever 3-7 categories best organize what was discussed"""

PLAN_PROMPT = """You organize conversations into a wiki. Read the conversation below and plan an
Obsidian wiki about its main topic.

{hints}

Return JSON with exactly these keys:
{{
  "title": "short name of the topic",
  "kind": "one or two words, e.g. video game, religion, robot, story, study subject",
  "summary": "2-3 sentences describing the topic, based on the conversation",
  "sections": [ {{"name": "Weapons", "about": "one sentence"}} ],
  "items": [ {{"name": "Tesla Turret", "section": "Weapons",
              "summary": "one sentence from the conversation",
              "properties": {{"damage": "high", "range": "short"}} }} ],
  "links": [ {{"from": "Tesla Turret", "to": "Rift Crawler", "relation": "strong against"}} ]
}}
Rules: 3-7 sections. Every item belongs to one section. Items are specific named things
(a weapon, a person, a belief, a part, a level) - not vague ideas. Only include things
actually discussed. Properties are short values that were mentioned (can be empty).
Links only between items in your list.

CONVERSATION:
{text}"""

PAGE_PROMPT = """Write an Obsidian wiki page for "{name}", which is one of the {section} in
"{title}" ({kind}).

What the conversation says (use this as your source):
{excerpts}

Known properties: {props}
Related pages you may link with [[double brackets]]: {related}

{mode_rule}

Format (Markdown, no title line, no front matter):
## Overview
2-4 sentences.
## Details
Bullet points or short paragraphs with the specifics.
## Connections
How it relates to the related pages, using [[links]].
## Open questions
Bullets for things still undecided (skip this section if none)."""

SECTION_PROMPT = """Write a short introduction (2-4 sentences) for the "{section}" section of a wiki
about "{title}" ({kind}). It contains: {names}. Base it on this conversation:
{excerpts}
Plain text only, no headings."""

HUB_PROMPT = """Write the overview for the main page of a wiki about "{title}" ({kind}).
Summary so far: {summary}
Sections: {sections}
Write 1-3 short paragraphs that explain the topic and how the sections fit together,
based on this conversation:
{excerpts}
Plain text only, no headings."""

ONLY_SAID = ("Use ONLY information from the conversation. If something isn't covered, "
             "put it under Open questions instead of inventing it.")
EXPAND = ("Organize what the conversation says, then add your own useful ideas to fill "
          "gaps. Mark every idea that did NOT come from the conversation with "
          "'(suggestion)' at the start of the line.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def transcript(history):
    lines = []
    for m in history:
        who = "You" if m["role"] == "user" else "Archie"
        text = m.get("display") or m.get("content", "")
        lines.append(f"{who}: {text.strip()}")
    return "\n\n".join(lines)


def chunks_of(text, size=9000):
    if len(text) <= size:
        return [text]
    parts, cur = [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) > size and cur:
            parts.append(cur)
            cur = ""
        cur += para + "\n\n"
    if cur.strip():
        parts.append(cur)
    return parts


def excerpts_about(text, name, limit=3500):
    """Paragraphs of the conversation that mention this name (or all of it if short)."""
    if len(text) <= limit:
        return text
    words = [w for w in re.findall(r"\w+", name.lower()) if len(w) > 2] or [name.lower()]
    paras = text.split("\n\n")
    hits = [p for p in paras if any(w in p.lower() for w in words)]
    out = "\n\n".join(hits) or text[:limit]
    return out[:limit]


def _ask_json(model, prompt, num_ctx=16384, max_tokens=3000):
    for attempt in range(2):
        raw = quick_chat(model, prompt if attempt == 0 else prompt + "\n\nReturn ONLY valid JSON.",
                         max_tokens=max_tokens, timeout=900, json_mode=True,
                         num_ctx=num_ctx, temperature=0.2)
        try:
            return json.loads(raw)
        except ValueError:
            m = re.search(r"\{.*\}", raw, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except ValueError:
                    pass
    raise ArchieError("The AI didn't return a usable plan. Try again, or use a bigger model.")


def _clean_name(s):
    return " ".join(str(s or "").replace("[", "").replace("]", "").split())[:80]


def merge_plans(plans):
    """Combine plans from several chunks of a long conversation."""
    out = {"title": "", "kind": "", "summary": "", "sections": [], "items": [], "links": []}
    seen_s, seen_i, seen_l = {}, {}, set()
    for p in plans:
        out["title"] = out["title"] or _clean_name(p.get("title"))
        out["kind"] = out["kind"] or str(p.get("kind") or "")[:30]
        out["summary"] = out["summary"] or str(p.get("summary") or "")
        for s in p.get("sections") or []:
            name = _clean_name(s.get("name") if isinstance(s, dict) else s)
            if name and name.lower() not in seen_s:
                seen_s[name.lower()] = name
                out["sections"].append({"name": name, "about": (s.get("about", "") if isinstance(s, dict) else "")})
        for it in p.get("items") or []:
            if not isinstance(it, dict):
                continue
            name = _clean_name(it.get("name"))
            if not name:
                continue
            key = name.lower()
            props = it.get("properties") if isinstance(it.get("properties"), dict) else {}
            if key in seen_i:
                seen_i[key]["properties"].update({k: v for k, v in props.items() if v})
                continue
            item = {"name": name, "section": _clean_name(it.get("section")),
                    "summary": str(it.get("summary") or ""),
                    "properties": {str(k)[:30]: str(v)[:80] for k, v in props.items() if str(v).strip()}}
            seen_i[key] = item
            out["items"].append(item)
        for l in p.get("links") or []:
            if not isinstance(l, dict):
                continue
            a, b = _clean_name(l.get("from")), _clean_name(l.get("to"))
            rel = str(l.get("relation") or "related to")[:40]
            if a and b and a.lower() != b.lower() and (a.lower(), b.lower()) not in seen_l:
                seen_l.add((a.lower(), b.lower()))
                out["links"].append({"from": a, "to": b, "relation": rel})
    # every item's section must exist
    names = {s["name"].lower(): s["name"] for s in out["sections"]}
    for it in out["items"]:
        if it["section"].lower() not in names:
            sec = it["section"] or "General"
            names[sec.lower()] = sec
            out["sections"].append({"name": sec, "about": ""})
        it["section"] = names[it["section"].lower() if it["section"] else "general"]
    # links only between known items
    known = {i["name"].lower(): i["name"] for i in out["items"]}
    out["links"] = [dict(l, **{"from": known[l["from"].lower()], "to": known[l["to"].lower()]})
                    for l in out["links"] if l["from"].lower() in known and l["to"].lower() in known]
    out["title"] = out["title"] or "Untitled topic"
    out["kind"] = out["kind"] or "topic"
    return out


# ---------------------------------------------------------------------------
# 1. Plan
# ---------------------------------------------------------------------------

def plan(model, history, progress=lambda s: None, max_items=40):
    text = transcript(history)
    if len(text.strip()) < 40:
        raise ArchieError("This chat is too short to build a wiki from. Talk it through a bit more first.")
    parts = chunks_of(text)
    plans = []
    for i, part in enumerate(parts, 1):
        progress(f"Reading the conversation ({i}/{len(parts)})...")
        plans.append(_ask_json(model, PLAN_PROMPT.format(hints=KIND_HINTS, text=part)))
    p = merge_plans(plans)
    p["items"] = p["items"][:max_items]
    if not p["items"]:
        raise ArchieError("I couldn't find specific things to make pages for. Try naming things "
                          "(characters, parts, weapons, beliefs...) in the chat.")
    p["_text"] = text
    return p


# ---------------------------------------------------------------------------
# 2. Build
# ---------------------------------------------------------------------------

def build(model, p, vault, expand=False, progress=lambda s, f=None: None, stop=None):
    """Write the wiki into <vault>/<title>/. Returns (folder inside vault, page count)."""
    text = p["_text"]
    title, kind = p["title"], p["kind"]
    base = safe_filename(title)
    root_rel, n = base, 2
    while os.path.exists(os.path.join(vault, root_rel)):
        root_rel = f"{base} ({n})"
        n += 1
    root = os.path.join(vault, root_rel)
    os.makedirs(root)
    ensure_hub(vault)     # the [[Archie]] note every build links back to
    mode_rule = EXPAND if expand else ONLY_SAID
    today = datetime.date.today().isoformat()
    topic_tag = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "topic"

    # paths inside the vault, used for exact [[path|name]] links
    sec_path = {s["name"]: f"{root_rel}/{safe_filename(s['name'])}/{safe_filename(s['name'])}"
                for s in p["sections"]}
    item_path = {i["name"]: f"{root_rel}/{safe_filename(i['section'])}/{safe_filename(i['name'])}"
                 for i in p["items"]}
    hub_path = f"{root_rel}/{base}"

    def link(name):
        path = item_path.get(name) or sec_path.get(name)
        return f"[[{path}|{name}]]" if path else f"[[{name}]]"

    def fix_links(body):
        """Point [[Name]] at the exact generated page; unknown links become plain text."""
        lookup = {k.lower(): k for k in list(item_path) + list(sec_path)}

        def sub(m):
            inner = m.group(1).split("|")[-1].strip()
            real = lookup.get(inner.lower())
            return link(real) if real else inner
        return re.sub(r"\[\[([^\]]+)\]\]", sub, body)

    def front(kind_of, extra=None):
        lines = ["---", f"type: {kind_of}", f"topic: \"{title}\"", f"created: {today}",
                 "source: Archie"]
        for k, v in (extra or {}).items():
            key = re.sub(r"[^a-zA-Z0-9_ -]", "", k).strip().replace(" ", "_").lower() or "prop"
            lines.append(f"{key}: \"{str(v).replace(chr(34), chr(39))}\"")
        lines += [f"tags: [{topic_tag}, archie]", "---", ""]
        return "\n".join(lines)

    total = len(p["items"]) + len(p["sections"]) + 1
    done = 0

    # detail pages
    rel_by_item = {}
    for l in p["links"]:
        rel_by_item.setdefault(l["from"], []).append((l["relation"], l["to"]))
        rel_by_item.setdefault(l["to"], []).append((f"{l['relation']} (from)", l["from"]))
    for it in p["items"]:
        if stop and stop.is_set():
            raise ArchieError("Stopped. The pages written so far are in your vault.")
        done += 1
        progress(f"Writing {it['name']} ({done}/{total})...", done / total)
        related = sorted({o for _, o in rel_by_item.get(it["name"], [])} |
                         {o["name"] for o in p["items"] if o["section"] == it["section"] and o is not it})
        props = ", ".join(f"{k}: {v}" for k, v in it["properties"].items()) or "none recorded"
        body = quick_chat(model, PAGE_PROMPT.format(
            name=it["name"], section=it["section"], title=title, kind=kind,
            excerpts=excerpts_about(text, it["name"]), props=props,
            related=", ".join(related[:12]) or "none", mode_rule=mode_rule),
            max_tokens=700, timeout=600, num_ctx=16384, temperature=0.5)
        rels = rel_by_item.get(it["name"], [])
        lines = [front(it["section"].lower(), it["properties"]), f"# {it['name']}", "",
                 f"*Part of {link(it['section'])} in {('[[' + hub_path + '|' + title + ']]')}*", ""]
        if it["summary"]:
            lines += [f"> {it['summary']}", ""]
        lines.append(fix_links(body.strip()))
        if rels:
            lines += ["", "## Relationships"] + [f"- {r} {link(o)}" for r, o in rels]
        path = os.path.join(vault, item_path[it["name"]] + ".md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # section pages with comparison tables
    for s in p["sections"]:
        if stop and stop.is_set():
            raise ArchieError("Stopped. The pages written so far are in your vault.")
        done += 1
        progress(f"Writing the {s['name']} section ({done}/{total})...", done / total)
        members = [i for i in p["items"] if i["section"] == s["name"]]
        intro = quick_chat(model, SECTION_PROMPT.format(
            section=s["name"], title=title, kind=kind,
            names=", ".join(i["name"] for i in members) or "nothing yet",
            excerpts=excerpts_about(text, s["name"] + " " + " ".join(i["name"] for i in members))),
            max_tokens=220, timeout=300, num_ctx=16384, temperature=0.5)
        lines = [front("section"), f"# {s['name']}", "", f"*Section of [[{hub_path}|{title}]]*", "",
                 fix_links(intro.strip()), ""]
        if members:
            cols = []
            for i in members:
                for k in i["properties"]:
                    if k not in cols:
                        cols.append(k)
            cols = cols[:6]
            header = ["Name"] + [c.replace("_", " ").title() for c in cols] + ["Summary"]
            lines += ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
            for i in members:
                cells = [i["properties"].get(c, "") for c in cols] + [i["summary"][:90]]
                cells = [str(x).replace("|", "/") for x in cells]
                name_cell = link(i["name"]).replace("|", "\\|")   # tables need \| inside links
                lines.append("| " + " | ".join([name_cell] + cells) + " |")
        path = os.path.join(vault, sec_path[s["name"]] + ".md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # hub
    done += 1
    progress(f"Writing the main page ({done}/{total})...", 1.0)
    overview = quick_chat(model, HUB_PROMPT.format(
        title=title, kind=kind, summary=p["summary"],
        sections=", ".join(s["name"] for s in p["sections"]), excerpts=text[:6000]),
        max_tokens=400, timeout=300, num_ctx=16384, temperature=0.5)
    lines = [front("hub", {"kind": kind}), f"# {title}", "", fix_links(overview.strip()), "",
             "## Sections"]
    for s in p["sections"]:
        members = [i["name"] for i in p["items"] if i["section"] == s["name"]]
        about = f" - {s['about']}" if s.get("about") else ""
        lines.append(f"- {link(s['name'])}{about}")
        lines += [f"    - {link(m)}" for m in members]
    lines += ["", f"*Built by [[Archie]] from a conversation on {today}"
              + (" (with Archie's suggestions marked)" if expand else "") + ".*"]
    with open(os.path.join(vault, hub_path + ".md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return root_rel, total, hub_path
