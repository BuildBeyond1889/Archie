"""Archie World: lawmaking, part five.

1. Local government, anywhere in the US: pick a state and county, and Archie lists the county and every town, city
   and village in it (from Wikidata). Follow the ones you care about: Archie finds the page on each one's own website
   where it posts meeting agendas and minutes, checks it twice a day, tells you when something new is posted, reads the
   documents (PDF or Word), pulls out the motions and votes recorded in minutes, and can explain them in plain English.
   Where a place uses an agenda system with an open API (Legistar), Archie reads that directly.
2. Bill versions side by side (US Congress): every printed version of a bill from govinfo.gov, and what changed
   between any two, word by word.

Public record only. No scores, ratings or labels on anyone.
"""
import datetime
import difflib
import hashlib
import html
import io
import json
import os
import re
import time
import urllib.parse
import zipfile

LOCAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS loc_bodies(id TEXT PRIMARY KEY, st TEXT, fips TEXT, name TEXT, kind TEXT, website TEXT, meetings_url TEXT,
  pages TEXT, platform TEXT, followed INTEGER DEFAULT 0, checked INTEGER DEFAULT 0, found INTEGER DEFAULT 0, note TEXT, added INTEGER);
CREATE TABLE IF NOT EXISTS loc_docs(id TEXT PRIMARY KEY, body TEXT, url TEXT, title TEXT, kind TEXT, date TEXT, posted TEXT,
  first_seen INTEGER, text TEXT, motions TEXT, read_at INTEGER, note TEXT);
CREATE INDEX IF NOT EXISTS loc_docs_body ON loc_docs(body, date);
"""

LOCAL_JOBS = {"civ_local": "local governments you follow"}

MONTHS = {m: i + 1 for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"])}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
KINDS = ("county", "city", "town", "village", "borough", "township", "municipality", "parish", "charter township", "consolidated city")
PLATFORMS = [("legistar.com", "Legistar"), ("civicclerk.com", "CivicClerk"), ("primegov.com", "PrimeGov"), ("boarddocs.com", "BoardDocs"),
             ("iqm2.com", "IQM2"), ("municodemeetings.com", "Municode Meetings"), ("novusagenda.com", "NovusAgenda"), ("granicus.com", "Granicus"),
             ("agendaonline", "AgendaOnline"), ("diligent.community", "Diligent Community"), ("escribemeetings.com", "eSCRIBE")]
DOC_EXT = re.compile(r"\.(pdf|docx?|rtf)(\?|#|$)|/AgendaCenter/ViewFile/|/Archive\.aspx\?ADID=|DocumentCenter/View/|/download(file)?[/?]", re.I)
MEET_WORDS = re.compile(r"agenda|minute|meeting|mtg|legislat|council|board|session|hearing|resolution|proceeding", re.I)
SKIP_DOCS = re.compile(r"application|permit|form\b|forms/|brochure|newsletter|map\b|flyer|menu|calendar of events|job|employment|bid\b|rfp|tax bill|dog licen", re.I)
VERSION_LABEL = {"ih": "Introduced in House", "is": "Introduced in Senate", "rh": "Reported in House", "rs": "Reported in Senate", "eh": "Passed the House",
                 "es": "Passed the Senate", "enr": "Final (sent to the President)", "eas": "Senate amendment", "eah": "House amendment", "pcs": "Placed on Senate calendar",
                 "rfs": "Received in Senate", "rfh": "Received in House", "ats": "Agreed to (Senate)", "ath": "Agreed to (House)", "pp": "Public print"}


def _iso(y, m, d=1):
    try:
        return datetime.date(int(y), int(m), int(d)).isoformat()
    except (ValueError, TypeError):
        return ""


def doc_date(text, url):
    """(meeting date, posted date) from a link's words and address. Either can be ''."""
    path = urllib.parse.unquote(urllib.parse.urlparse(url or "").path)
    fname = path.rsplit("/", 1)[-1].replace("_", " ")
    today = datetime.date.today()
    MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    mon = lambda w: MONTHS["sept" if w[:4] == "sept" else w[:3]]
    posted = ""
    m = re.search(r"/(20\d\d)[/-](\d{2})(?:[/-](\d{2}))?/", path)
    if m:
        posted = _iso(m.group(1), m.group(2), m.group(3) or 1)

    def full(t):
        tl = t.lower()
        m = re.search(r"\b" + MON + r"\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*(?:&|and|-)\s*\d{1,2}(?:st|nd|rd|th)?)?,?\s+(\d{4})", tl)
        if m:
            return _iso(m.group(3), mon(m.group(1)), m.group(2))
        m = re.search(r"(?<!\d)(\d{1,2})[-.](\d{1,2})[-.](\d{4}|\d{2})(?!\d)", t) or re.search(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])", t)
        if m and 1 <= int(m.group(1)) <= 12:
            return _iso(int(m.group(3)) + (2000 if len(m.group(3)) == 2 else 0), m.group(1), m.group(2))
        m = re.search(r"(?<!\d)(20\d\d)[-._](\d{1,2})[-._](\d{1,2})(?!\d)", t)
        if m:
            return _iso(m.group(1), m.group(2), m.group(3))
        m = re.search(r"(?<!\d)(\d{2})(\d{2})(20\d\d)(?!\d)", t)
        if m and 1 <= int(m.group(1)) <= 12:
            return _iso(m.group(3), m.group(1), m.group(2))
        m = re.search(r"(?<=[A-Za-z])(\d{1,2})(\d{2})(\d{2})(?!\d)", t)      # "ALEG72325": 7/23/25
        if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
            return _iso(2000 + int(m.group(3)), m.group(1), m.group(2))
        return ""

    def month_only(t):
        m = re.search(r"\b" + MON + r"\b\.?,?\s*(20\d\d)?", t.lower())
        if not m:
            return ""
        mo = mon(m.group(1))
        if m.group(2):
            return _iso(m.group(2), mo, 1)
        if posted:
            py, pm = int(posted[:4]), int(posted[5:7])
            return _iso(py if mo <= pm else py - 1, mo, 1)
        return ""

    meet = full(text or "") or month_only(text or "") or full(fname) or month_only(fname)
    if not meet:
        m = re.match(r"^(\d{1,2})-(\d{2})\.\w+$", fname)       # "8-26.pdf": month and year
        if m and 1 <= int(m.group(1)) <= 12:
            meet = _iso(2000 + int(m.group(2)), m.group(1), 1)
    if not meet:
        m = re.search(r"_(\d{2})(\d{2})(20\d\d)-\d+", url or "")     # CivicPlus AgendaCenter: _MMDDYYYY-ID
        if m:
            meet = _iso(m.group(3), m.group(1), m.group(2))
    if meet and (meet > (today + datetime.timedelta(days=400)).isoformat() or meet < "1990"):
        meet = ""
    return meet, posted


def doc_kind(text, url):
    t = (text or "") + " " + urllib.parse.unquote(url or "")
    if re.search(r"minute", t, re.I):
        return "minutes"
    if re.search(r"agenda", t, re.I):
        return "agenda"
    if re.search(r"resolution|local law|ordinance", t, re.I):
        return "resolution"
    if re.search(r"packet", t, re.I):
        return "agenda"
    return "document"


def find_motions(text):
    """Motions, resolutions and recorded votes in a set of minutes, as the minutes word them."""
    if not text:
        return []
    t = re.sub(r"[ \t]+", " ", text.replace("\r", ""))
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n(?=\s*(?:RESOLVED|WHEREAS|Motion|MOTION|Moved|Upon motion|On motion|A motion|Resolution No)\b)", t) if p.strip()]
    out = []
    for p in paras:
        flat = re.sub(r"\s*\n\s*", " ", p)
        if not re.search(r"\bmotion\b|\bmoved\b|\bresolved\b|\bresolution\b|\broll call\b", flat, re.I):
            continue
        res = re.search(r"\b(carried|adopted|approved|passed|unanimously|denied|defeated|failed|tabled|withdrawn|rejected)\b", flat, re.I)
        tally = {}
        for lab, key in (("ayes?|yes|yeas?|in favor", "ayes"), ("nays?|noes?|no\b|opposed|against", "nays"), ("abstain(?:ed|ing|s)?|abstentions?", "abstain"), ("absent", "absent")):
            mm = re.search(r"\b(?:%s)\s*[:\-–]?\s*(\d{1,3})\b" % lab, flat, re.I)
            if mm:
                tally[key] = int(mm.group(1))
            names = re.search(r"\b(?i:%s)\s*[:\-–]\s*((?:(?!(?:Nays?|Noes?|No|Absent|Abstain\w*|Motion|Carried|Adopted|Approved|Excused)\b)[A-Z][A-Za-z.'\-]+(?:\s(?!(?:Nays?|Noes?|Absent|Abstain\w*|Motion|Carried|Adopted|Approved|Excused)\b)[A-Z][A-Za-z.'\-]+)?\s*,?\s*(?:and\s+)?){1,15})" % lab, flat)
            if names and key + "_n" not in tally and not mm:
                L = [x.strip() for x in re.split(r",|\band\b", names.group(1)) if x.strip() and not re.match(r"^(None|Motion|Carried)$", x.strip())]
                if L:
                    tally[key + "_names"] = L[:15]
        if not res and not tally and not re.search(r"\bresolved\b", flat, re.I):
            continue
        out.append({"text": flat[:700] + ("…" if len(flat) > 700 else ""), "outcome": res.group(1).lower() if res else "", "tally": tally})
        if len(out) >= 80:
            break
    return out


def bill_paras(raw):
    """govinfo's plain-text bill (inside <pre>) -> list of paragraphs, boilerplate removed."""
    t = html.unescape(re.sub(r"<[^>]+>", "", raw))
    t = re.sub(r"^\[.*?\]\s*$", "", t, flags=re.M)
    t = t.replace("<DOC>", "").replace("<all>", "")
    paras, cur = [], []
    for line in t.split("\n"):
        s = line.strip()
        if not s or re.match(r"^_{5,}$", s):
            if cur:
                paras.append(" ".join(cur))
                cur = []
            continue
        cur.append(s)
    if cur:
        paras.append(" ".join(cur))
    return [re.sub(r"\s+", " ", p) for p in paras if p]


HEAD = re.compile(r"^(SEC\.|SECTION|TITLE [IVXLC]+|Subtitle [A-Z]|PART [IVXLC\d]+|CHAPTER \d+|DIVISION [A-Z])", re.I)


def diff_bills(A, B, max_hunks=400):
    """Paragraph-level diff with word-level detail inside changed paragraphs. Returns (stats, hunks)."""
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    hunks, added, removed, changed = [], 0, 0, 0
    heads = []
    last = ""
    for i, p in enumerate(B):
        if HEAD.match(p):
            last = p[:140]
        heads.append(last)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        changed += 1
        a_txt, b_txt = A[i1:i2], B[j1:j2]
        aw = sum(len(p.split()) for p in a_txt)
        bw = sum(len(p.split()) for p in b_txt)
        parts = []
        if tag == "replace" and aw + bw < 6000:
            wa, wb = " ¶ ".join(a_txt).split(" "), " ¶ ".join(b_txt).split(" ")
            ws = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
            for t2, x1, x2, y1, y2 in ws.get_opcodes():
                if t2 == "equal":
                    seg = wa[x1:x2]
                    if len(seg) > 60:
                        seg = seg[:25] + ["…"] + seg[-25:]
                    parts.append(("eq", " ".join(seg)))
                else:
                    if x2 > x1:
                        parts.append(("del", " ".join(wa[x1:x2])))
                        removed += x2 - x1
                    if y2 > y1:
                        parts.append(("ins", " ".join(wb[y1:y2])))
                        added += y2 - y1
        else:
            if a_txt:
                parts.append(("del", " ¶ ".join(a_txt)))
                removed += aw
            if b_txt:
                parts.append(("ins", " ¶ ".join(b_txt)))
                added += bw
        if len(hunks) < max_hunks:
            out = []
            for k, s in parts:
                s = s if len(s) < 6000 else s[:3000] + " … [" + str(len(s.split())) + " words in all] … " + s[-1500:]
                e = html.escape(s).replace("¶", "<br>")
                out.append(e if k == "eq" else "<%s>%s</%s>" % (k, e, k))
            where = heads[j1] if j1 < len(heads) else (heads[-1] if heads else "")
            hunks.append({"where": where, "html": " ".join(out), "kind": "added" if tag == "insert" else "removed" if tag == "delete" else "changed",
                          "words": [aw if tag != "insert" else 0, bw if tag != "delete" else 0]})
    return {"added": added, "removed": removed, "changes": changed, "paras": [len(A), len(B)]}, hunks


class CivicLocal:
    def local_init(self):
        self.db.executescript(LOCAL_SCHEMA)
        self.db.commit()
        if self.kv("loc_v") != 2:     # documents used to be shared between places on one website; sort them out again
            self.db.execute("DELETE FROM loc_docs WHERE body IN (SELECT id FROM loc_bodies WHERE meetings_url != '')")
            self.db.execute("UPDATE loc_bodies SET pages='', checked=0, found=0 WHERE meetings_url != ''")
            self.db.commit()
            self.kv_set("loc_v", 2)
        self._diff_cache = {}

    def local_jobs(self):
        return [("civ_local", 1800, self.pull_local)]

    # ------------------------------------------------------------------ places
    def _counties(self):
        p = os.path.join(os.path.dirname(self.dir), "web", "data", "us_counties.json")
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _wd(self, q):
        u = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": q, "format": "json"})
        d = self.getj(u, timeout=90, headers=self.WD_UA)   # Wikidata refuses generic browser names
        return [{k: v.get("value") for k, v in b.items()} for b in (d.get("results") or {}).get("bindings") or []]

    def local_places(self, fips, refresh=False):
        fips = re.sub(r"\D", "", fips or "").zfill(5)
        if len(fips) != 5:
            return {"error": "pick a county"}
        st = next((s for s, L in self._counties().items() for f, n in L if f == fips), "")
        cname = next((n for s, L in self._counties().items() for f, n in L if f == fips), "")
        key = "local_places_" + fips
        cached = self.kv(key)
        if not cached or refresh or (cached.get("at") or 0) < time.time() - 30 * 86400:
            try:
                c = self._wd('SELECT ?c ?w WHERE { ?c wdt:P882 "%s". OPTIONAL { ?c wdt:P856 ?w } }' % fips)
                if not c:
                    raise ValueError("Wikidata doesn't know this county")
                cq = c[0]["c"].rsplit("/", 1)[-1]
                rows = self._wd(
                    "SELECT ?p ?pLabel (SAMPLE(?w) AS ?web) (MAX(?pop) AS ?people) (GROUP_CONCAT(DISTINCT ?tl; separator='|') AS ?types) WHERE { "
                    "{ ?p wdt:P131 wd:%s } UNION { ?p wdt:P131 ?mid. ?mid wdt:P131 wd:%s. ?p wdt:P31 ?vt. ?vt rdfs:label ?vl. FILTER(lang(?vl)='en' && CONTAINS(LCASE(?vl), 'village')) } "
                    "?p wdt:P31 ?t. ?t rdfs:label ?tl. FILTER(lang(?tl)='en') OPTIONAL { ?p wdt:P856 ?w } OPTIONAL { ?p wdt:P1082 ?pop } "
                    "SERVICE wikibase:label { bd:serviceParam wikibase:language 'en'. } } GROUP BY ?p ?pLabel" % (cq, cq))
                places = []
                for r in rows:
                    types = (r.get("types") or "").lower()
                    if "census-designated" in types or "ghost town" in types or "former" in types:
                        continue
                    kind = next((k for k in ("city", "village", "borough", "charter township", "township", "town", "municipality", "parish") if re.search(r"\b%s\b" % k, types)), "")
                    if not kind:
                        continue
                    places.append({"id": r["p"].rsplit("/", 1)[-1], "name": r.get("pLabel") or "", "kind": kind, "web": (r.get("web") or "").rstrip(","),
                                   "pop": int(float(r["people"])) if r.get("people") else None})
                places.sort(key=lambda p: (-(p["pop"] or 0), p["name"]))
                cached = {"at": int(time.time()), "county": {"id": cq, "web": c[0].get("w") or ""}, "places": places}
                self.kv_set(key, cached)
            except (self.FetchError, ValueError, KeyError) as e:
                if not cached:
                    return {"error": "Couldn't get the list of towns from Wikidata (%s)." % e, "st": st, "county": cname}
        body_rows = {r["id"]: dict(r) for r in self.q("SELECT id, followed, found, checked, website, meetings_url, note FROM loc_bodies WHERE fips=?", (fips,))}
        out = [{"id": cached["county"]["id"], "name": cname, "kind": "county", "web": cached["county"]["web"], "pop": None}] + cached["places"]
        for p in out:
            b = body_rows.get(p["id"]) or {}
            p.update({"followed": bool(b.get("followed")), "found": b.get("found") or 0, "checked": b.get("checked") or 0, "note": b.get("note") or "",
                      "web": b.get("website") or p["web"], "meetings_url": b.get("meetings_url") or ""})
        for cid, b in body_rows.items():   # boards you added yourself
            if cid.startswith("custom:"):
                r = self.q("SELECT * FROM loc_bodies WHERE id=?", (cid,), one=True)
                out.append({"id": cid, "name": r["name"], "kind": r["kind"] or "board", "web": r["website"] or "", "pop": None, "followed": bool(r["followed"]),
                            "found": r["found"] or 0, "checked": r["checked"] or 0, "note": r["note"] or "", "meetings_url": r["meetings_url"] or ""})
        return {"st": st, "fips": fips, "county": cname, "places": out, "at": cached.get("at")}

    def local_follow(self, b):
        bid = (b.get("id") or "").strip()
        if b.get("custom_name"):
            bid = "custom:" + hashlib.sha1((b.get("fips", "") + b["custom_name"]).encode()).hexdigest()[:10]
        if not bid:
            return {"error": "nothing to follow"}
        r = self.q("SELECT * FROM loc_bodies WHERE id=?", (bid,), one=True)
        name = b.get("custom_name") or b.get("name") or (r["name"] if r else bid)
        web = (b.get("website") if b.get("website") is not None else (r["website"] if r else "")) or ""
        murl = (b.get("meetings_url") if b.get("meetings_url") is not None else (r["meetings_url"] if r else "")) or ""
        fix = lambda u: (u if re.match(r"^https?://", u, re.I) else "https://" + u.lstrip("/")) if u else ""
        web, murl = fix(web.strip()), fix(murl.strip())     # people paste "townname-ny.gov/..." without the https://
        for u in (web, murl):
            if u and not re.match(r"^https?://[^/\s]+\.[^/\s]+", u):
                return {"error": "That doesn't look like a web address: " + u[:80]}
        if not web and not murl and b.get("fips"):      # the website Wikidata lists for it
            cached = self.kv("local_places_" + re.sub(r"\D", "", b["fips"]).zfill(5)) or {}
            if (cached.get("county") or {}).get("id") == bid:
                web = cached["county"].get("web") or ""
            web = web or next((p["web"] for p in cached.get("places") or [] if p["id"] == bid), "")
        fol = 1 if b.get("on", True) else 0
        reset = bool(r) and ((r["website"] or "") != web or (r["meetings_url"] or "") != murl)
        self.x("""INSERT INTO loc_bodies(id, st, fips, name, kind, website, meetings_url, pages, platform, followed, checked, found, note, added)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET website=excluded.website, meetings_url=excluded.meetings_url,
                  followed=excluded.followed, name=excluded.name, pages=CASE WHEN ? THEN '' ELSE loc_bodies.pages END,
                  checked=CASE WHEN ? THEN 0 ELSE loc_bodies.checked END""",
               (bid, b.get("st") or (r["st"] if r else ""), b.get("fips") or (r["fips"] if r else ""), name, b.get("kind") or (r["kind"] if r else ""), web, murl,
                "", "", fol, 0, 0, "", int(time.time()), 1 if reset else 0, 1 if reset else 0))
        out = {"ok": True, "id": bid}
        if fol and (b.get("scan_now") or not r or reset or not (r["pages"] if r else "")):
            out["scanning"] = self._scan_bg(bid)
        return out

    def _scan_bg(self, bid):
        """Look in the background (a big town website can take a minute); the page asks how it's going."""
        import threading
        busy = self.__dict__.setdefault("_scanning", set())
        if bid in busy:
            return True
        busy.add(bid)

        def run():
            try:
                self.local_scan(bid)
            except Exception as e:      # noqa: BLE001 - shown on the page instead
                self.x("UPDATE loc_bodies SET checked=?, note=? WHERE id=?", (int(time.time()), "Couldn't check: %s" % str(e)[:150], bid))
            finally:
                busy.discard(bid)
        threading.Thread(target=run, daemon=True, name="local-scan").start()
        return True

    # ------------------------------------------------------------------ finding and reading their meeting pages
    @staticmethod
    def _links(page, base):
        out = []
        for m in re.finditer(r"<a\b[^>]*?href\s*=\s*[\"']([^\"'#]+)[\"'][^>]*>(.*?)</a>", page, re.I | re.S):
            href = html.unescape(m.group(1).strip())
            if href.lower().startswith(("mailto:", "javascript:", "tel:")):
                continue
            text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
            if not text:
                t2 = re.search(r"(?:title|aria-label)\s*=\s*[\"']([^\"']+)", m.group(0), re.I)
                text = t2.group(1) if t2 else ""
            out.append((urllib.parse.urljoin(base, href), text[:200]))
        return out

    @staticmethod
    def _site(u):
        n = urllib.parse.urlparse(u).netloc.lower()
        n = n[4:] if n.startswith("www.") else n
        parts = n.split(".")
        return ".".join(parts[-3:]) if len(parts) > 2 and parts[-2] in ("ny", "co", "us", "ca", "pa", "oh", "gov") and len(parts[-1]) == 2 else ".".join(parts[-2:])

    def _page(self, url):
        try:
            return self.get(url, timeout=40, headers={"Accept": "text/html,*/*"})
        except self.FetchError:
            if url.startswith("http://"):
                return self.get("https://" + url[7:], timeout=40, headers={"Accept": "text/html,*/*"})
            raise

    def local_scan(self, bid):
        r = self.q("SELECT * FROM loc_bodies WHERE id=?", (bid,), one=True)
        if not r:
            return {"error": "not followed"}
        start = r["meetings_url"] or r["website"]
        if not start:
            self.x("UPDATE loc_bodies SET note=?, checked=? WHERE id=?", ("No website on file. Paste the page where they post agendas and minutes.", int(time.time()), bid))
            return {"error": "no website"}
        known = json.loads(r["pages"] or "[]")
        year = datetime.date.today().year
        seen_pages, docs, platform, fetched = set(), {}, json.loads(r["platform"] or "{}"), 0
        queue = [(u, 1, 99) for u in known] if known else []
        queue.append((start, 0, 100))
        good_pages = {}
        site = self._site(start)
        first = not r["checked"]
        budget = 8 if known else 16
        pinned = bool(r["meetings_url"])     # you told Archie the page: stay on it (and the year pages it links to)
        maxdepth = 1 if pinned else 3
        if pinned:
            queue = [(start, 0, 100)]
            budget = 5
        errors = []
        while queue and fetched < budget and not self._stop():
            queue.sort(key=lambda x: -x[2])
            url, depth, score = queue.pop(0)
            if url in seen_pages:
                continue
            seen_pages.add(url)
            drive = re.search(r"drive\.google\.com/(?:drive/(?:u/\d+/)?folders/|embeddedfolderview\?id=)([\w-]{10,})", url)
            if drive:      # a shared Google Drive folder (some villages keep their minutes there)
                platform.setdefault("Google Drive", url)
                fetched += 1
                try:
                    got = self._drive(drive.group(1), url)
                except self.FetchError as e:
                    errors.append("Google Drive: %s" % e)
                    continue
                for d in got:
                    docs.setdefault(d["url"], d)
                if got:
                    good_pages[url] = len(got)
                continue
            try:
                page = self._page(url)
            except self.FetchError as e:
                errors.append("%s: %s" % (url, e))
                continue
            fetched += 1
            title = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
            ptitle = re.sub(r"\s+", " ", html.unescape(title.group(1))).strip() if title else ""
            page_is_meetings = bool(re.search(r"agenda|minute|meeting", ptitle + " " + url, re.I))
            n_here = 0
            page_kind = "minutes" if re.search(r"minute", ptitle + " " + url, re.I) and not re.search(r"agenda", ptitle + " " + url, re.I) else \
                "agenda" if re.search(r"agenda", ptitle + " " + url, re.I) and not re.search(r"minute", ptitle + " " + url, re.I) else ""
            for href, text in self._links(page, url):
                low = (href + " " + text).lower()
                if re.search(r"drive\.google\.com/drive/(?:u/\d+/)?folders/", href) and href not in seen_pages and (MEET_WORDS.search(text) or page_is_meetings):
                    queue.append((href, depth + 1, 50))
                    continue
                for dom, pname in PLATFORMS:
                    if dom in low and pname not in platform:
                        platform[pname] = href
                if DOC_EXT.search(href):
                    if SKIP_DOCS.search(text + " " + urllib.parse.unquote(href)) and not re.search(r"agenda|minute", low):
                        continue
                    if not (MEET_WORDS.search(text + " " + urllib.parse.unquote(href)) or page_is_meetings):
                        continue
                    meet, posted = doc_date(text, href)
                    if href not in docs:
                        docs[href] = {"url": href, "title": (text or urllib.parse.unquote(href.rsplit("/", 1)[-1]))[:200], "kind": (lambda k: page_kind if k == "document" and page_kind else k)(doc_kind(text, href)),
                                      "date": meet or posted, "posted": posted, "page": url}
                        n_here += 1
                    continue
                if self._site(href) != site or depth >= maxdepth or href in seen_pages:
                    continue
                if re.search(r"\.(jpg|jpeg|png|gif|zip|mp4|mp3|xlsx?|pptx?|ics)(\?|$)|/(login|search|calendar)\b|facebook|twitter|instagram|youtube", href, re.I):
                    continue
                s = 0
                if re.search(r"agenda|minute", low):
                    s += 6
                if re.search(r"meeting", low):
                    s += 4
                if re.search(r"board|council|legislat|government|clerk|supervisor|trustee|commission", low):
                    s += 2
                ys = [int(y) for y in re.findall(r"\b(20\d\d)\b", low)]
                if ys:
                    s += 3 if max(ys) >= year else (0 if max(ys) == year - 1 else -5)
                if pinned and s < 6 and not ys:
                    continue
                if s >= 2:
                    queue.append((href, depth + 1, s - depth))
            if n_here:
                good_pages[url] = n_here
            time.sleep(0.6)
        cutoff = (datetime.date.today() - datetime.timedelta(days=550)).isoformat()
        recent_pages = sorted(good_pages, key=lambda u: -good_pages[u])
        pages = [u for u in recent_pages if any(d["page"] == u and (d["date"] or "9") >= cutoff for d in docs.values())][:5] or recent_pages[:3]
        if "Legistar" in platform:
            try:
                docs.update(self._legistar(platform["Legistar"]))
            except (self.FetchError, ValueError, KeyError, TypeError) as e:
                errors.append("Legistar: %s" % e)
        new = []
        for d in docs.values():
            did = hashlib.sha1((bid + "|" + d["url"]).encode()).hexdigest()[:16]     # the same file can belong to a town and a village
            if self.q("SELECT 1 FROM loc_docs WHERE id=?", (did,), one=True):
                continue
            self.x("INSERT INTO loc_docs(id, body, url, title, kind, date, posted, first_seen, text, motions, read_at, note) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                   (did, bid, d["url"], d["title"], d["kind"], d["date"], d["posted"], int(time.time()), None, None, 0, d.get("note", "")))
            new.append(d)
        total = self.q("SELECT COUNT(*) n FROM loc_docs WHERE body=?", (bid,), one=True)["n"]
        note = "" if total else ("Archie looked at %d page%s on %s and didn't find agendas or minutes. Paste the page where they post them." % (fetched, "" if fetched == 1 else "s", urllib.parse.urlparse(start).netloc)
                                 + (" (Their agendas may be on %s, which Archie can't read yet.)" % ", ".join(k for k in platform if k != "Legistar") if platform else ""))
        if errors and not fetched:
            note = "Couldn't reach their website: %s" % errors[0][:160]
        self.x("UPDATE loc_bodies SET pages=?, platform=?, checked=?, found=?, note=? WHERE id=?", (json.dumps(pages), json.dumps(platform), int(time.time()), total, note, bid))
        fresh = [d for d in new if (d["date"] or d["posted"] or "") >= (datetime.date.today() - datetime.timedelta(days=45)).isoformat()]
        if fresh and not first:
            label = r["name"]
            for d in fresh[:5]:
                self.x("INSERT INTO watch_events(at, kind, id, label, what, detail, link) VALUES(?,?,?,?,?,?,?)",
                       (int(time.time()), "local", bid, label, d["kind"], d["title"][:300], "gov=local:" + bid))
            try:
                self.svc._alert("local:%s:%s" % (bid, int(time.time()) // 3600), "Local · " + label[:80],
                                "New %s posted: %s" % (fresh[0]["kind"], fresh[0]["title"][:120]) + ("" if len(fresh) == 1 else " (+%d more)" % (len(fresh) - 1)), "gov=local:" + bid)
            except Exception:
                pass
        return {"pages": pages, "new": len(new), "total": total, "platform": list(platform), "note": note, "looked_at": fetched}

    def _drive(self, folder, page_url, depth=0):
        """Files in a public Google Drive folder, going into this year's and last year's subfolders."""
        t = self.get("https://drive.google.com/embeddedfolderview?id=%s" % folder, timeout=40)
        out, subs = [], []
        year = datetime.date.today().year
        ptitle = (re.search(r"<title>([^<]*)", t) or [None, ""])[1]
        for href, name, mod in re.findall(r'<a href="([^"]+)"[\s\S]*?flip-entry-title">([^<]*)<[\s\S]*?last-modified"><div>([^<]*)', t):
            name = html.unescape(name).strip()
            fm = re.search(r"/file/d/([\w-]+)", href)
            dm = re.search(r"/folders/([\w-]+)", href)
            if fm:
                meet, _ = doc_date(name, "")
                k = doc_kind(name, "")
                if k == "document" and re.search(r"minute", ptitle or "", re.I):
                    k = "minutes"
                out.append({"url": "https://drive.google.com/uc?export=download&id=" + fm.group(1), "title": re.sub(r"\.(pdf|docx?)$", "", name, flags=re.I)[:200],
                            "kind": k, "date": meet, "posted": "", "page": page_url})
            elif dm and depth < 2:
                ys = [int(y) for y in re.findall(r"\b(20\d\d)\b", name)]
                if (ys and max(ys) >= year - 1) or (not ys and re.search(r"minute|agenda|meeting", name, re.I)):
                    subs.append((max(ys) if ys else 0, dm.group(1)))
        for _, sub in sorted(subs, reverse=True)[:3]:
            time.sleep(0.5)
            out += self._drive(sub, page_url, depth + 1)
        return out

    def _legistar(self, link):
        m = re.search(r"https?://([a-z0-9\-]+)\.legistar\.com", link, re.I)
        if not m:
            return {}
        client = m.group(1)
        since = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()
        ev = self.getj("https://webapi.legistar.com/v1/%s/events?$filter=EventDate+ge+datetime'%sT00:00:00'&$orderby=EventDate+desc&$top=60" % (client, since), timeout=60)
        out = {}
        for e in ev if isinstance(ev, list) else []:
            date = (e.get("EventDate") or "")[:10]
            body = e.get("EventBodyName") or "Meeting"
            for key, kind in (("EventAgendaFile", "agenda"), ("EventMinutesFile", "minutes")):
                u = e.get(key)
                if u:
                    out[u] = {"url": u, "title": "%s %s" % (body, kind), "kind": kind, "date": date, "posted": "", "page": "legistar",
                              "note": json.dumps({"legistar": client, "event": e.get("EventId")})}
        return out

    def pull_local(self):
        rows = self.q("SELECT id, checked, pages FROM loc_bodies WHERE followed=1")
        n = 0
        for r in rows:
            if self._stop():
                break
            if r["checked"] and time.time() - r["checked"] < 11 * 3600:
                continue
            try:
                res = self.local_scan(r["id"])
                n += res.get("new", 0) if isinstance(res, dict) else 0
            except Exception as e:      # noqa: BLE001 - one town's broken website shouldn't stop the others
                self.x("UPDATE loc_bodies SET checked=?, note=? WHERE id=?", (int(time.time()), "Couldn't check: %s" % str(e)[:150], r["id"]))
        self._ok("Local governments", True, "%d followed, %d new documents" % (len(rows), n) if rows else "none followed yet")

    def local_body(self, bid):
        r = self.q("SELECT * FROM loc_bodies WHERE id=?", (bid,), one=True)
        if not r:
            return {"error": "not found"}
        b = dict(r)
        b["pages"] = json.loads(b["pages"] or "[]")
        b["scanning"] = bid in self.__dict__.get("_scanning", set())
        b["platform"] = json.loads(b["platform"] or "{}")
        b["docs"] = [dict(d) for d in self.q("""SELECT id, url, title, kind, date, posted, first_seen, read_at, note FROM loc_docs WHERE body=?
                     ORDER BY COALESCE(NULLIF(date,''), posted, '') DESC, first_seen DESC LIMIT 120""", (bid,))]
        return b

    def local_feed(self):
        bodies = {r["id"]: dict(r) for r in self.q("SELECT id, name, kind, st, fips, found, checked, note FROM loc_bodies WHERE followed=1")}
        docs = [dict(d) for d in self.q("""SELECT d.id, d.body, d.url, d.title, d.kind, d.date, d.posted, d.first_seen FROM loc_docs d JOIN loc_bodies b ON b.id=d.body
                WHERE b.followed=1 ORDER BY COALESCE(NULLIF(d.date,''), d.posted, '') DESC, d.first_seen DESC LIMIT 40""")]
        for d in docs:
            d["body_name"] = bodies.get(d["body"], {}).get("name", "")
        return {"bodies": list(bodies.values()), "docs": docs}

    def _read_file(self, url):
        try:
            data, _u, ctype = self.fetch(url, timeout=90, raw=True)
        except self.FetchError as e:
            if "certificate verify failed" not in str(e).lower():
                raise
            return self.aia_get(url, 90, None).encode("latin-1", "replace"), ""
        return data[:25 * 1024 * 1024], ctype or ""

    def local_doc(self, did):
        d = self.q("SELECT * FROM loc_docs WHERE id=?", (did,), one=True)
        if not d:
            return {"error": "not found"}
        d = dict(d)
        if d["text"] is None:
            text, note = "", ""
            try:
                data, ctype = self._read_file(d["url"])
                if data[:4] == b"%PDF" or "pdf" in ctype:
                    try:
                        from pypdf import PdfReader
                        text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:80])
                    except ImportError:
                        note = "Reading PDFs needs the PDF reader from Install Extras.bat."
                    except Exception as e:      # noqa: BLE001 - a damaged PDF
                        note = "Couldn't read this PDF (%s)." % str(e)[:80]
                    if not text.strip() and not note:
                        note = "This PDF is a scanned picture of the pages, so there's no text for Archie to read. Open the original."
                elif data[:2] == b"PK":
                    with zipfile.ZipFile(io.BytesIO(data)) as z:
                        x = z.read("word/document.xml").decode("utf-8", "replace")
                    text = html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"</w:p>", "\n\n", x)))
                elif "html" in ctype or data[:200].lstrip()[:1] == b"<":
                    text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style).*?</\1>", "", data.decode("utf-8", "replace"))))
                else:
                    note = "Archie can't read this kind of file (%s). Open the original." % (ctype or "unknown")
            except (self.FetchError, KeyError, zipfile.BadZipFile) as e:
                note = "Couldn't download it: %s" % e
            text = re.sub(r"[ \t]+\n", "\n", text or "")[:250000]
            mot = find_motions(text) if d["kind"] in ("minutes", "resolution", "document") or re.search(r"\bmotion\b", text[:20000], re.I) else []
            self.x("UPDATE loc_docs SET text=?, motions=?, read_at=?, note=? WHERE id=?", (text, json.dumps(mot), int(time.time()), note, did))
            d.update({"text": text, "motions": json.dumps(mot), "note": note})
        d["motions"] = json.loads(d["motions"] or "[]")
        d["body_name"] = (self.q("SELECT name FROM loc_bodies WHERE id=?", (d["body"],), one=True) or {"name": ""})["name"]
        d["chars"] = len(d["text"] or "")
        d["text"] = (d["text"] or "")[:60000]
        return d

    def local_search(self, q):
        q = (q or "").strip()
        if len(q) < 3:
            return {"items": []}
        rows = self.q("""SELECT d.id, d.title, d.kind, d.date, d.body, b.name, d.text FROM loc_docs d JOIN loc_bodies b ON b.id=d.body
                         WHERE d.text LIKE ? OR d.title LIKE ? ORDER BY d.date DESC LIMIT 40""", ("%" + q + "%", "%" + q + "%"))
        out = []
        for r in rows:
            t = r["text"] or ""
            i = t.lower().find(q.lower())
            out.append({"id": r["id"], "title": r["title"], "kind": r["kind"], "date": r["date"], "body": r["body"], "body_name": r["name"],
                        "snip": re.sub(r"\s+", " ", t[max(0, i - 160):i + 200]) if i >= 0 else ""})
        return {"items": out}

    def local_summary_text(self, xid):
        d = self.q("SELECT d.title, d.kind, d.date, d.text, b.name FROM loc_docs d JOIN loc_bodies b ON b.id=d.body WHERE d.id=?", (xid,), one=True)
        if not d or not (d["text"] or "").strip():
            return None
        return ("Local government: %s\nDocument: %s (%s, %s)\n%s" % (d["name"], d["title"], d["kind"], d["date"], d["text"][:7000]),
                "local government %s (say what was decided or is up for a decision; list votes as the document records them)" % (d["kind"] or "document"))

    # ------------------------------------------------------------------ bill versions (US Congress)
    def _gi_key(self):
        return self.settings.get("fec_key") or "DEMO_KEY"

    def bill_versions(self, bid):
        m = re.match(r"^US-(\d+)-([a-z]+)(\d+)$", bid or "")
        if not m:
            return {"error": "Side-by-side versions are available for US bills."}
        pkg = "BILLSTATUS-%s%s%s" % m.groups()
        key = "bv_" + bid
        c = self.kv(key)
        if c and (c.get("at") or 0) > time.time() - 6 * 3600:
            return c
        try:
            d = self.getj("https://api.govinfo.gov/related/%s/BILLS?api_key=%s" % (pkg, self._gi_key()), timeout=60)
        except self.FetchError as e:
            return {"error": "Couldn't reach govinfo.gov (%s)." % e}
        V = []
        for r in d.get("results") or []:
            code = r.get("billVersion") or r.get("packageId", "").rsplit(m.group(3), 1)[-1]
            V.append({"pkg": r.get("packageId"), "code": code, "label": VERSION_LABEL.get(code, r.get("billVersionLabel") or code), "official": r.get("billVersionLabel") or "", "date": r.get("dateIssued") or ""})
        V.sort(key=lambda v: (v["date"], v["pkg"]))
        out = {"id": bid, "versions": V, "at": int(time.time())}
        self.kv_set(key, out)
        return out

    def _bill_text(self, pkg):
        if not re.match(r"^BILLS-\d+[a-z]+\d+[a-z]+$", pkg or ""):
            raise ValueError("bad version")
        folder = os.path.join(self.cache, "billtext")
        os.makedirs(folder, exist_ok=True)
        p = os.path.join(folder, pkg + ".txt")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return f.read()
        t = self.get("https://api.govinfo.gov/packages/%s/htm?api_key=%s" % (pkg, self._gi_key()), timeout=180)
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
        return t

    def bill_diff(self, a, b, offset=0):
        ck = (a, b)
        res = self._diff_cache.get(ck)
        if not res:
            try:
                A, B = bill_paras(self._bill_text(a)), bill_paras(self._bill_text(b))
            except (self.FetchError, ValueError, OSError) as e:
                return {"error": "Couldn't get the bill text from govinfo.gov (%s)." % e}
            t0 = time.time()
            stats, hunks = diff_bills(A, B)
            stats["secs"] = round(time.time() - t0, 1)
            res = {"a": a, "b": b, "stats": stats, "hunks": hunks}
            if len(self._diff_cache) > 6:
                self._diff_cache.pop(next(iter(self._diff_cache)))
            self._diff_cache[ck] = res
        off = max(0, int(offset or 0))
        return {"a": a, "b": b, "stats": res["stats"], "hunks": res["hunks"][off:off + 40], "offset": off, "total": len(res["hunks"])}

    # ------------------------------------------------------------------ routes
    def local_get(self, name, a):
        if name == "local_places":
            return self.local_places(a("fips"), a("refresh") == "1")
        if name == "local_body":
            return self.local_body(a("id"))
        if name == "local_doc":
            return self.local_doc(a("id"))
        if name == "local_feed":
            return self.local_feed()
        if name == "local_search":
            return self.local_search(a("q"))
        if name == "bill_versions":
            return self.bill_versions(a("id"))
        if name == "bill_diff":
            return self.bill_diff(a("a"), a("b"), a("offset", "0"))
        return None

    def local_post(self, name, b):
        if name == "local_follow":
            return self.local_follow(b)
        if name == "local_scan":
            return {"ok": True, "scanning": self._scan_bg(b.get("id", ""))}
        return None
