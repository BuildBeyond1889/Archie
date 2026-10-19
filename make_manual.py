#!/usr/bin/env python3
"""
make_manual.py - turns Manual/Archie Manual.md into "Archie Manual.html".

Archie runs this by itself when you open the manual and the .md is newer,
so you only ever edit the .md (in Notepad). Standard Python only; works offline.

Markdown understood: # / ## / ### headings, paragraphs, - and 1. lists
(indent 2 spaces to nest), | tables |, > callouts, **bold**, *italic*,
`code`, [links](#section), and {{Ctrl+Alt+A}} for keyboard keys.
"""

import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "Manual", "Archie Manual.md")
OUT = os.path.join(HERE, "Archie Manual.html")


def slug(text):
    t = re.sub(r"<[^>]+>", "", text).lower()
    t = re.sub(r"[^a-z0-9 \-]", "", t)
    return re.sub(r"\s+", "-", t.strip())


def inline(text):
    t = html.escape(text, quote=False)
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"
    t = re.sub(r"`([^`]+)`", keep, t)
    t = re.sub(r"\{\{(.+?)\}\}", lambda m: "".join(
        f"<kbd>{k}</kbd>" + ("<span class=plus>+</span>" if i < len(m.group(1).split("+")) - 1 else "")
        for i, k in enumerate(m.group(1).split("+"))), t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\((#[^)]+|https?://[^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\x00(\d+)\x00", lambda m: f"<code>{codes[int(m.group(1))]}</code>", t)
    return t


def convert(md):
    lines = md.splitlines()
    title, version = "ARCHIE Manual", ""
    out, toc = [], []
    i = 0
    para = []
    in_section = False

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        s = line.strip()
        m = re.match(r"<!--\s*version:\s*(.*?)\s*-->", s)
        if m:
            version = m.group(1)
            i += 1
            continue
        if not s:
            flush()
            i += 1
            continue
        if s.startswith("# "):
            flush()
            title = s[2:].strip()
            i += 1
            continue
        if s.startswith("## "):
            flush()
            h = s[3:].strip()
            sid = slug(h)
            toc.append((sid, h))
            if in_section:
                out.append("</section>")
            out.append(f'<section id="{sid}"><h2><a class=anchor href="#{sid}">#</a>{inline(h)}</h2>')
            in_section = True
            i += 1
            continue
        if s.startswith("### "):
            flush()
            h = s[4:].strip()
            out.append(f'<h3 id="{slug(h)}">{inline(h)}</h3>')
            i += 1
            continue
        if s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            body = " ".join(quote)
            kind = "tip" if body.lower().startswith("**tip") else "note"
            out.append(f'<div class="callout {kind}">{inline(body)}</div>')
            continue
        if s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            t = ["<div class=table><table>"]
            if rows:
                t.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in rows[0]) + "</tr></thead><tbody>")
                for r in rows[1:]:
                    t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
                t.append("</tbody>")
            t.append("</table></div>")
            out.append("".join(t))
            continue
        if re.match(r"^(\s*)([-*]|\d+\.)\s+", line):
            flush()
            items = []
            while i < len(lines) and (re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i])
                                      or (lines[i].startswith("   ") and lines[i].strip() and items)):
                m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if m:
                    items.append([len(m.group(1)), "ol" if m.group(2)[0].isdigit() else "ul", m.group(3)])
                else:
                    items[-1][2] += " " + lines[i].strip()
                i += 1
            out.append(render_list(items))
            continue
        para.append(s)
        i += 1
    flush()
    if in_section:
        out.append("</section>")
    return title, version, toc, "\n".join(out)


def render_list(items):
    html_out, stack = [], []          # stack of (indent, tag)
    for indent, tag, text in items:
        while stack and indent < stack[-1][0]:
            html_out.append(f"</li></{stack.pop()[1]}>")
        if not stack or indent > stack[-1][0]:
            html_out.append(f"<{tag}>")
            stack.append((indent, tag))
        else:
            html_out.append("</li>")
        html_out.append("<li>" + inline(text))
    while stack:
        html_out.append(f"</li></{stack.pop()[1]}>")
    return "".join(html_out)


OWL = ('<svg viewBox="12.5 18.5 95 95" width="34" height="34" aria-hidden="true"><g fill="none" '
       'stroke="#c6f432" stroke-width="6" stroke-linecap="round" stroke-linejoin="round">'
       '<path d="M28 26 L48 40 L72 40 L92 26 L92 76 L60 106 L28 76 Z" fill="#141414"/>'
       '<polygon points="46,76 33.9,69 33.9,55 46,48 58.1,55 58.1,69"/>'
       '<polygon points="74,76 61.9,69 61.9,55 74,48 86.1,55 86.1,69"/>'
       '<path d="M55 83 L60 91 L65 83"/></g></svg>')

CSS = """
@font-face{font-family:Geist;src:url("fonts/Geist-Regular.ttf")}
@font-face{font-family:Geist;src:url("fonts/Geist-SemiBold.ttf");font-weight:600}
@font-face{font-family:Geist;src:url("fonts/Geist-Bold.ttf");font-weight:700}
@font-face{font-family:"JetBrains Mono";src:url("fonts/JetBrainsMono-Regular.ttf")}
@font-face{font-family:"JetBrains Mono";src:url("fonts/JetBrainsMono-Bold.ttf");font-weight:700}
:root{--bg:#0a0a0a;--surface:#141414;--raised:#1a1a1a;--border:#262626;--text:#e8e8e3;
--body:#d4d4cf;--muted:#8a8a85;--accent:#c6f432;--mono:"JetBrains Mono",Consolas,monospace;
--sans:Geist,"Segoe UI",system-ui,sans-serif}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:20px}
body{margin:0;background:var(--bg);color:var(--body);font:15px/1.65 var(--sans)}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{display:grid;grid-template-columns:260px minmax(0,1fr);max-width:1180px;margin:0 auto}
nav{position:sticky;top:0;height:100vh;overflow:auto;padding:28px 18px 28px 24px;border-right:1px solid var(--border)}
.brand{display:flex;align-items:center;gap:10px;margin-bottom:4px}
.brand b{font:700 15px var(--mono);letter-spacing:.12em;color:var(--text)}
.ver{font:12px var(--mono);color:var(--muted);margin:0 0 18px 44px}
.search{display:flex;align-items:center;gap:8px;background:var(--surface);border:1px solid var(--border);
border-radius:12px;padding:8px 12px;margin-bottom:16px}
.search span{color:var(--accent);font-family:var(--mono)}
.search input{flex:1;min-width:0;background:none;border:0;outline:0;color:var(--text);font:14px var(--mono)}
nav ol{list-style:none;margin:0;padding:0}
nav li a{display:block;color:var(--muted);padding:5px 10px;border-radius:8px;font-size:14px}
nav li a:hover{background:var(--raised);color:var(--text);text-decoration:none}
nav li a.on{color:var(--text);background:var(--raised);box-shadow:inset 2px 0 0 var(--accent)}
nav li.hide{display:none}
main{padding:36px 48px 120px;min-width:0}
h1{font:600 34px/1.15 var(--sans);color:var(--text);margin:0 0 6px}
.lead{color:var(--muted);font:13px var(--mono);margin:0 0 28px}
section{padding:8px 0 18px;border-top:1px solid var(--border)}
section.hide{display:none}
h2{font:600 22px var(--sans);color:var(--text);margin:26px 0 10px;position:relative}
h2 .anchor{position:absolute;left:-24px;color:var(--border);font-family:var(--mono)}
h2:hover .anchor{color:var(--accent)}
h3{font:600 17px var(--sans);color:var(--text);margin:22px 0 6px}
p{margin:10px 0}
ul,ol{margin:8px 0;padding-left:22px}li{margin:4px 0}li::marker{color:var(--muted)}
strong{color:var(--text);font-weight:600}
code{font:13px var(--mono);background:var(--raised);border:1px solid var(--border);border-radius:6px;padding:1px 6px;color:var(--text)}
kbd{font:600 12px var(--mono);background:var(--surface);border:1px solid #3a3a3a;border-bottom-width:2px;
border-radius:6px;padding:1px 7px;color:var(--text)}
.plus{color:var(--muted);margin:0 2px;font-size:12px}
.table{overflow-x:auto;margin:12px 0;border:1px solid var(--border);border-radius:12px}
table{border-collapse:collapse;width:100%;font-size:14px}
th{text-align:left;font:600 12px var(--mono);color:var(--muted);text-transform:lowercase;background:var(--surface)}
th,td{padding:9px 14px;border-bottom:1px solid var(--border);vertical-align:top}
tr:last-child td{border-bottom:0}
.callout{border-left:2px solid var(--accent);background:var(--surface);border-radius:0 12px 12px 0;padding:10px 16px;margin:14px 0}
.callout.note{border-left-color:#5a5a55}
mark{background:var(--accent);color:#0a0a0a;border-radius:3px;padding:0 2px}
.empty{display:none;color:var(--muted);font-family:var(--mono);padding:20px 0}
@media (max-width:820px){.wrap{display:block}nav{position:static;height:auto;border-right:0;border-bottom:1px solid var(--border)}
main{padding:24px 18px 80px}h2 .anchor{display:none}}
@media print{:root{--bg:#fff;--surface:#f4f4f2;--raised:#f0f0ee;--border:#ddd;--text:#111;--body:#222;--muted:#666;--accent:#4d6b00}
nav{display:none}.wrap{display:block}main{padding:0}section{break-inside:avoid-page}}
"""

JS = """
const q=document.getElementById('q'),secs=[...document.querySelectorAll('main section')],
links=[...document.querySelectorAll('nav li')],empty=document.querySelector('.empty');
secs.forEach(s=>s.dataset.html=s.innerHTML);
function esc(t){return t.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')}
function mark(node,re){for(const c of [...node.childNodes]){if(c.nodeType===3){const t=c.textContent;if(re.test(t)){
const s=document.createElement('span');s.innerHTML=t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(re,m=>'<mark>'+m+'</mark>');c.replaceWith(s)}re.lastIndex=0}
else if(c.nodeType===1&&!/^(svg|script)$/i.test(c.tagName))mark(c,re)}}
q.addEventListener('input',()=>{const v=q.value.trim().toLowerCase();let n=0;
secs.forEach((s,i)=>{s.innerHTML=s.dataset.html;const hit=!v||s.textContent.toLowerCase().includes(v);
s.classList.toggle('hide',!hit);links[i].classList.toggle('hide',!hit);if(hit)n++;
if(hit&&v)mark(s,new RegExp(esc(v),'gi'))});empty.style.display=n?'none':'block'});
document.addEventListener('keydown',e=>{if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus()}
if(e.key==='Escape'){q.value='';q.dispatchEvent(new Event('input'))}});
const navA=[...document.querySelectorAll('nav a')];
function spy(){let cur=null;for(const s of secs){if(!s.classList.contains('hide')&&s.getBoundingClientRect().top<140)cur=s.id}
navA.forEach(a=>a.classList.toggle('on',cur&&a.getAttribute('href')==='#'+cur))}
addEventListener('scroll',spy,{passive:true});spy();
"""


def build(src=SRC, out=OUT):
    with open(src, encoding="utf-8") as f:
        title, version, toc, body = convert(f.read())
    nav = "".join(f'<li><a href="#{sid}">{inline(h)}</a></li>' for sid, h in toc)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Archie Manual</title>
<link rel="icon" href="archie.png">
<style>{CSS}</style></head>
<body><div class="wrap">
<nav><div class="brand">{OWL}<b>ARCHIE</b></div><div class="ver">manual · v{html.escape(version.replace("updated: ", ""))}</div>
<label class="search"><span>&gt;</span><input id="q" placeholder="search   /" autocomplete="off"></label>
<ol>{nav}</ol></nav>
<main><h1>{inline(title)}</h1><p class="lead">&gt; works offline · v{html.escape(version.replace("updated: ", ""))}</p>
{body}
<p class="empty">nothing matches that search. press esc to clear.</p>
</main></div>
<script>{JS}</script></body></html>"""
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    return out


def needs_build(src=SRC, out=OUT):
    try:
        return not os.path.exists(out) or os.path.getmtime(src) > os.path.getmtime(out)
    except OSError:
        return False


if __name__ == "__main__":
    print("Wrote", build())


# ---------------------------------------------------------------------------
# Letting Archie answer questions about itself from this manual
# ---------------------------------------------------------------------------

_TRIGGER = re.compile(r"\barchie\b|\bhow (?:do|can|should|would) i\b|\bwhere(?:'s| is| are| do)\b|"
                      r"\bwhat does\b|\bhot ?keys?\b|\bshortcuts?\b|\bbuttons?\b|\bmenu\b|"
                      r"\bsettings?\b|\bmanual\b|\bhelp\b", re.I)
_STOP = set("a an the and or of to in on at for with is are was be it its this that do does did i "
            "me my you your can could should would how what where when why which who archie "
            "please about get make use using there here have has just so if then".split())


def _terms(text):
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9+]+", text.lower())
            if w not in _STOP and len(w) > 1}


def manual_lookup(question, src=SRC, k=2, limit=6000):
    """The parts of the manual that answer a question about Archie itself, or None."""
    if not _TRIGGER.search(question):
        return None
    try:
        with open(src, encoding="utf-8") as f:
            md = f.read()
    except OSError:
        return None
    q = _terms(question)
    if not q:
        return None
    parts = re.split(r"^(?=## )", md, flags=re.M)
    scored = []
    for part in parts:
        if not part.startswith("## "):
            continue
        title, _, body = part.partition("\n")
        if re.match(r"## (Changelog|Coming later)", title) and not (q & {"changelog", "new", "version", "later", "idea", "update"}):
            continue
        words = re.findall(r"[a-z0-9+]+", body.lower())
        counts = {}
        for w in words:
            w = w.rstrip("s")
            if w in q:
                counts[w] = counts.get(w, 0) + 1
        tt = _terms(title)
        in_title = {w for w in q if any(t.startswith(w) or w.startswith(t) for t in tt if len(t) > 2)}
        score = sum(min(c, 3) for c in counts.values()) + 4 * len(in_title)
        if score >= 3:
            scored.append((score, part.strip()))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return None
    text = "\n\n".join(p for _, p in scored[:k])
    return text[:limit]
