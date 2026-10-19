"""Archie World: lawmaking, part three.

Debate transcripts (what was said on the floor: UK Hansard, the US Congressional Record), UK money (the Electoral
Commission's donations register and MPs' Register of Interests), three more parliaments (Sweden, Norway, Iceland),
how your state lawmakers vote (Open States, with a free key), and election night: results for national elections
around the world as they come in (from Wikipedia's election articles, which volunteers update as official counts are
published).

Public record only. No scores, ratings or labels on anyone.
"""
import datetime
import html
import json
import re
import time
import urllib.parse

EXTRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS elec(id TEXT PRIMARY KEY, title TEXT, date TEXT, cc TEXT, country TEXT, article TEXT,
  data TEXT, at INTEGER, changed INTEGER);
CREATE INDEX IF NOT EXISTS elec_date ON elec(date);
"""

EXTRA_JOBS = {"civ_se": "Sweden", "civ_no": "Norway", "civ_is": "Iceland", "civ_os": "your state legislature (Open States)",
              "civ_elec": "election results"}

SE_PARTY = {"S": "Socialdemokraterna", "M": "Moderaterna", "SD": "Sverigedemokraterna", "V": "Vänsterpartiet", "C": "Centerpartiet",
            "KD": "Kristdemokraterna", "MP": "Miljöpartiet", "L": "Liberalerna", "-": "independent"}
SE_POS = {"ja": "Y", "nej": "N", "avstår": "A", "frånvarande": "X"}
NO_POS = {1: "X", 2: "Y", 3: "N"}
IS_POS = {"já": "Y", "nei": "N", "greiðir ekki atkvæði": "A", "fjarverandi": "X", "boðaði fjarvist": "X"}

ELECTION_SKIP = re.compile(r"municipal|local|mayor|county|city council|school|primary|caucus|by-election|referendum on|regional|"
                           r"provincial|state legislat|state senate|state house|house of delegates|assembly election|cantonal|district council", re.I)


def _ms(v):
    m = re.search(r"Date\((-?\d+)", str(v or ""))
    return datetime.datetime.utcfromtimestamp(int(m.group(1)) / 1000).strftime("%Y-%m-%d") if m else ""


def _txt(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


# ---------------------------------------------------------------- Wikipedia election infobox -> numbers
def _split_top(s):
    """Split template body on '|' that aren't inside nested {{ }} or [[ ]]."""
    out, cur, depth, i = [], [], 0, 0
    while i < len(s):
        two = s[i:i + 2]
        if two in ("{{", "[["):
            depth += 1
            cur.append(two)
            i += 2
            continue
        if two in ("}}", "]]"):
            depth -= 1
            cur.append(two)
            i += 2
            continue
        if s[i] == "|" and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(s[i])
        i += 1
    out.append("".join(cur))
    return out


def _infobox(wikitext):
    m = re.search(r"\{\{\s*Infobox (legislative )?election", wikitext or "", re.I)
    if not m:
        return None
    i, depth = m.start(), 0
    j = i
    while j < len(wikitext):
        if wikitext.startswith("{{", j):
            depth += 1
            j += 2
            continue
        if wikitext.startswith("}}", j):
            depth -= 1
            j += 2
            if depth == 0:
                break
            continue
        j += 1
    body = wikitext[i + 2:j - 2]
    params = {}
    for part in _split_top(body)[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            params[k.strip().lower()] = v.strip()
    return params


def _clean(v):
    v = re.sub(r"<!--.*?-->", "", v or "", flags=re.S)
    v = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", v, flags=re.S | re.I)
    v = re.sub(r"\{\{\s*(increase|gain)\s*\}\}", "+", v, flags=re.I)
    v = re.sub(r"\{\{\s*(decrease|loss)\s*\}\}", "−", v, flags=re.I)
    v = re.sub(r"\{\{\s*(steady|nochange)\s*\}\}", "", v, flags=re.I)
    v = re.sub(r"\{\{\s*(?:nowrap|small|nobold)\s*\|([^{}]*)\}\}", r"\1", v, flags=re.I)
    for _ in range(3):
        v = re.sub(r"\{\{[^{}]*\}\}", "", v)
    v = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", v)
    v = re.sub(r"\[https?://\S+\s+([^\]]*)\]", r"\1", v)
    v = re.sub(r"'{2,}", "", v)
    v = re.sub(r"<br\s*/?>", " ", v, flags=re.I)
    v = re.sub(r"<[^>]+>", "", v)
    return re.sub(r"\s+", " ", html.unescape(v)).strip()


def _num(v):
    m = re.search(r"-?[\d,]+(?:\.\d+)?", (v or "").replace("−", "-"))
    if not m:
        return None
    try:
        x = float(m.group(0).replace(",", ""))
        return int(x) if x.is_integer() and "." not in m.group(0) else x
    except ValueError:
        return None


def _signed(v):
    c = _clean(v)
    n = _num(c)
    if n is None:
        return None
    return -abs(n) if c.startswith("−") or c.startswith("-") else abs(n) if c.startswith("+") else n


def parse_election(wikitext):
    p = _infobox(wikitext)
    if not p:
        return None
    rows = []
    for n in range(1, 40):
        party = _clean(p.get("party%d" % n, ""))
        cand = _clean(p.get("nominee%d" % n, "") or p.get("candidate%d" % n, ""))
        if not party and not cand:
            if n > 3:
                break
            continue
        seats = _num(_clean(p.get("seats%d" % n) or p.get("seats_after%d" % n) or p.get("current_seats%d" % n) or ""))
        before = _num(_clean(p.get("seats_before%d" % n) or "")) if p.get("seats_before%d" % n) else _num(_clean(p.get("last_election%d" % n, "")))
        rows.append({"party": re.sub(r"\s*\((United States|[A-Z][a-z]+)\)$", "", party), "leader": _clean(p.get("leader%d" % n, "")), "candidate": cand,
                     "bloc": _clean(p.get("alliance%d" % n, "")), "seats": seats, "before": before,
                     "change": _signed(p.get("seat_change%d" % n, "")), "votes": _num(_clean(p.get("popular_vote%d" % n, ""))),
                     "pct": _num(_clean(p.get("percentage%d" % n, ""))), "swing": _signed(p.get("swing%d" % n, "")),
                     "electoral": _num(_clean(p.get("electoral_vote%d" % n, ""))), "states": _num(_clean(p.get("states_carried%d" % n, ""))),
                     "color": _clean(p.get("colour%d" % n, "") or p.get("color%d" % n, "")).lstrip("#")})
    have = any(r["seats"] is not None or r["votes"] is not None or r["pct"] is not None or r["electoral"] is not None for r in rows)
    return {"type": _clean(p.get("type", "")), "country": _clean(p.get("country", "")), "date": _clean(p.get("election_date", "")),
            "seats_total": _num(_clean(p.get("seats_for_election", ""))), "majority": _num(_clean(p.get("majority_seats", ""))),
            "turnout": _clean(p.get("turnout", "")), "registered": _clean(p.get("registered", "")), "rows": rows, "results": have,
            "title_after": _clean(p.get("title", "")), "after": _clean(p.get("after_election", "")), "before_who": _clean(p.get("before_election", ""))}


class CivicExtra:
    def extra_init(self):
        self.db.executescript(EXTRA_SCHEMA)
        self.db.commit()

    # ================================================================== DEBATES
    def debates(self, cc, q="", key="", skip=0):
        cc = (cc or "").upper()
        skip = int(skip or 0)
        if cc == "GB":
            qs = {"queryParameters.take": 25, "queryParameters.skip": skip, "queryParameters.orderBy": "SittingDateDesc"}
            if q:
                qs["queryParameters.searchTerm"] = q
            if key.startswith("GB:"):
                qs["queryParameters.memberId"] = key[3:]
            if not q and not key:
                return {"items": [], "total": 0}
            try:
                d = self.getj("https://hansard-api.parliament.uk/search/contributions/Spoken.json?" + urllib.parse.urlencode(qs), timeout=40)
            except self.FetchError as e:
                return {"error": "Couldn't reach Hansard (%s)." % e}
            out = []
            for r in d.get("Results") or []:
                date = (r.get("SittingDate") or "")[:10]
                slug = re.sub(r"[^A-Za-z0-9]+", "", r.get("DebateSection") or "debate") or "debate"
                out.append({"who": r.get("AttributedTo") or r.get("MemberName") or "", "member": "GB:%s" % r["MemberId"] if r.get("MemberId") else "",
                            "date": date, "house": r.get("House") or "", "where": r.get("DebateSection") or "", "section": r.get("Section") or "",
                            "text": (r.get("ContributionTextFull") or r.get("ContributionText") or "").strip()[:1500],
                            "url": "https://hansard.parliament.uk/%s/%s/debates/%s/%s#contribution-%s" % (r.get("House") or "Commons", date, r.get("DebateSectionExtId") or "", slug, r.get("ContributionExtId") or "")})
            return {"items": out, "total": d.get("TotalResultCount") or len(out), "source": "Hansard (UK Parliament)"}
        if cc == "US":
            terms = []
            if q:
                terms.append('"%s"' % q.replace('"', "") if " " in q.strip() else q.strip())
            if key.startswith("US:"):
                p = self.us_people().get(key[3:]) or {}
                if p.get("last"):
                    terms.append('member:"%s"' % p["last"])
            if not terms:
                return {"items": [], "total": 0}
            body = {"query": "collection:CREC AND " + " AND ".join(terms), "pageSize": 25, "offsetMark": "*",
                    "sorts": [{"field": "publishdate", "sortOrder": "DESC"}]}
            api_key = self.settings.get("fec_key") or "DEMO_KEY"
            try:
                raw = self.fetch("https://api.govinfo.gov/search?api_key=" + urllib.parse.quote(api_key), timeout=40,
                                 headers={"Content-Type": "application/json", "Accept": "application/json"}, data=json.dumps(body).encode())
                d = json.loads(raw)
            except (self.FetchError, ValueError) as e:
                return {"error": "Couldn't reach govinfo (%s)%s." % (e, "; the shared demo key may be used up for the hour, a free api.data.gov key fixes that" if api_key == "DEMO_KEY" else "")}
            out = []
            for r in d.get("results") or []:
                g = r.get("granuleId") or ""
                ch = "Senate" if "PgS" in g else "House" if "PgH" in g else "Extensions of Remarks" if "PgE" in g else "Daily Digest" if "PgD" in g else ""
                out.append({"who": "", "date": r.get("dateIssued") or "", "house": ch, "where": (r.get("title") or "").title(), "granule": g,
                            "package": r.get("packageId") or "", "text": "",
                            "url": "https://www.govinfo.gov/app/details/%s/%s" % (r.get("packageId") or "", g)})
            return {"items": out, "total": d.get("count") or len(out), "source": "the Congressional Record (govinfo.gov)"}
        return {"error": "Debate transcripts are available for the US and the UK."}

    def debate_text(self, package, granule, q=""):
        api_key = self.settings.get("fec_key") or "DEMO_KEY"
        try:
            t = self.get("https://api.govinfo.gov/packages/%s/granules/%s/htm?api_key=%s" % (package, granule, urllib.parse.quote(api_key)), timeout=40)
        except self.FetchError as e:
            return {"error": str(e)}
        t = _txt(re.sub(r"(?is)<head.*?</head>", "", t))
        t = re.sub(r"\[\[Page [^\]]*\]\]|\[Congressional Record Volume[^\]]*\]|\[From the U\.S\. Government Publishing Office[^\]]*\]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        speakers = list(dict.fromkeys(re.findall(r"\b(?:Mr|Ms|Mrs)\. [A-Z][A-Z'\-]+(?: of [A-Z][a-z]+(?: [A-Z][a-z]+)?)?", t)))[:8]
        i = t.lower().find(q.lower()) if q else -1
        start = max(0, i - 600) if i > 0 else 0
        return {"text": t[start:start + 2400], "speakers": speakers, "length": len(t), "from": start}

    # ================================================================== UK MONEY
    def uk_money(self, key):
        mid = (key or "")[3:]
        m = self.q("SELECT name, party FROM members WHERE key=?", (key,), one=True)
        if not mid.isdigit() or not m:
            return {"error": "Only UK MPs and peers."}
        ck = "ukmoney:" + key
        c = self.kv(ck)
        if c and time.time() - c.get("at", 0) < 86400:
            return c
        out = {"name": m["name"], "interests": [], "donations": [], "at": time.time(), "errors": []}
        try:
            skip, items = 0, []
            while skip < 200:
                d = self.getj("https://interests-api.parliament.uk/api/v1/Interests?MemberId=%s&Take=20&Skip=%d" % (mid, skip), timeout=40)
                items += d.get("items") or []
                skip += 20
                if skip >= (d.get("totalResults") or 0):
                    break
            for it in items:
                fields = []
                for f in it.get("fields") or []:
                    if f.get("value") not in (None, ""):
                        fields.append([f.get("description") or f.get("name") or "", str(f["value"])])
                    for row in f.get("values") or []:
                        bits = [str(x.get("value")) for x in row if x.get("value") not in (None, "") and x.get("name") not in ("PublicAddress", "IsPrivateIndividual")]
                        if bits:
                            fields.append([f.get("description") or f.get("name") or "", " · ".join(bits)])
                out["interests"].append({"category": (it.get("category") or {}).get("name", ""), "summary": it.get("summary") or "",
                                         "registered": it.get("registrationDate") or "", "fields": fields[:12]})
        except (self.FetchError, ValueError) as e:
            out["errors"].append("Register of Interests: %s" % e)
        try:
            d = self.getj("https://search.electoralcommission.org.uk/api/search/Donations?" + urllib.parse.urlencode(
                {"start": 0, "rows": 300, "query": m["name"], "sort": "AcceptedDate", "order": "desc"}), timeout=60)
            toks = self._norm(m["name"])
            for r in d.get("Result") or []:
                t = self._norm(r.get("RegulatedEntityName") or "")
                if not toks or toks[-1] not in t or toks[0] not in t:
                    continue
                out["donations"].append({"donor": r.get("DonorName") or "", "value": r.get("Value") or 0, "type": r.get("DonationType") or "",
                                         "nature": r.get("NatureOfDonation") or "", "status": r.get("DonorStatus") or "",
                                         "date": _ms(r.get("AcceptedDate") or r.get("ReceivedDate")), "ref": r.get("ECRef") or ""})
        except (self.FetchError, ValueError) as e:
            out["errors"].append("Electoral Commission: %s" % e)
        if not out["errors"]:
            self.kv_set(ck, out)
        return out

    # ================================================================== SWEDEN
    def pull_se(self):
        y, mo = datetime.date.today().year, datetime.date.today().month
        rms = ["%d/%02d" % (y, (y + 1) % 100), "%d/%02d" % (y - 1, y % 100)] if mo >= 9 else ["%d/%02d" % (y - 1, y % 100), "%d/%02d" % (y - 2, (y - 1) % 100)]
        n = 0
        try:
            docs = []
            for rm in rms:
                for page in (1, 2, 3):
                    d = self.getj("https://data.riksdagen.se/dokumentlista/?doktyp=votering&rm=%s&sz=200&utformat=json&sort=datum&sortorder=desc&p=%d" % (urllib.parse.quote(rm), page), timeout=60)
                    L = (d.get("dokumentlista") or {}).get("dokument") or []
                    docs += L
                    if len(L) < 200:
                        break
                if len(docs) > 300:
                    break
            for doc in docs:
                if n >= 50 or self._stop():
                    break
                vid = doc.get("kall_id") or ""
                if not vid or self.have("SE-" + vid):
                    continue
                d = self.getj("https://data.riksdagen.se/voteringlista/?votering_id=%s&sz=500&utformat=json&gruppering=" % vid, timeout=60)
                rows = (d.get("voteringlista") or {}).get("votering") or []
                if isinstance(rows, dict):
                    rows = [rows]
                mem = []
                for r in rows:
                    pos = SE_POS.get((r.get("rost") or "").lower(), "O")
                    mem.append(("SE:" + (r.get("intressent_id") or r.get("namn") or ""), r.get("namn") or "", SE_PARTY.get(r.get("parti") or "", r.get("parti") or ""), pos, r.get("valkrets") or ""))
                title = re.sub(r"^Omröstning:\s*", "", doc.get("titel") or "")
                self.save_vote({"id": "SE-" + vid, "cc": "SE", "chamber": "R", "date": (doc.get("datum") or "")[:10], "title": title,
                                "question": doc.get("undertitel") or "", "result": "", "src": "riksdagen",
                                "url": "https://www.riksdagen.se/sv/dokument-och-lagar/dokument/votering/_%s/" % (doc.get("dok_id") or "")}, mem)
                n += 1
                time.sleep(0.6)
            self._ok("Sweden votes", True, "%d new" % n)
        except (self.FetchError, ValueError, KeyError, TypeError) as e:
            self._ok("Sweden votes", False, str(e))

    # ================================================================== NORWAY
    def pull_no(self):
        t = datetime.date.today()
        ses = ["%d-%d" % (t.year, t.year + 1), "%d-%d" % (t.year - 1, t.year)] if t.month >= 10 else ["%d-%d" % (t.year - 1, t.year), "%d-%d" % (t.year - 2, t.year - 1)]
        checked = self.kv("no_checked", {}) or {}
        n, calls = 0, 0
        try:
            for s in ses:
                d = self.getj("https://data.stortinget.no/eksport/saker?sesjonid=%s&format=json" % s, timeout=60)
                saker = d.get("saker_liste") or []
                saker.sort(key=lambda x: str(x.get("sist_oppdatert_dato") or ""), reverse=True)
                for sak in saker:
                    if calls >= 80 or self._stop():
                        break
                    sid, mod = str(sak.get("id")), str(sak.get("sist_oppdatert_dato") or "")
                    if checked.get(sid) == mod:
                        continue
                    v = self.getj("https://data.stortinget.no/eksport/voteringer?sakid=%s&format=json" % sid, timeout=60)
                    calls += 1
                    for vo in v.get("sak_votering_liste") or []:
                        if not vo.get("personlig_votering"):
                            continue
                        vid = "NO-%s" % vo.get("votering_id")
                        if self.have(vid):
                            continue
                        r = self.getj("https://data.stortinget.no/eksport/voteringsresultat?voteringid=%s&format=json" % vo.get("votering_id"), timeout=60)
                        calls += 1
                        mem = []
                        for x in r.get("voteringsresultat_liste") or []:
                            p = x.get("representant") or {}
                            mem.append(("NO:" + str(p.get("id") or ""), ("%s %s" % (p.get("fornavn") or "", p.get("etternavn") or "")).strip(),
                                        (p.get("parti") or {}).get("navn") or "", NO_POS.get(x.get("votering"), "O"), (p.get("fylke") or {}).get("navn") or ""))
                        self.save_vote({"id": vid, "cc": "NO", "chamber": "S", "date": _ms(vo.get("votering_tid")), "title": sak.get("korttittel") or sak.get("tittel") or "",
                                        "question": vo.get("votering_tema") or "", "result": "Adopted" if vo.get("vedtatt") else "Not adopted", "src": "stortinget",
                                        "yes": vo.get("antall_for"), "no": vo.get("antall_mot"), "absent": vo.get("antall_ikke_tilstede"),
                                        "url": "https://www.stortinget.no/no/Saker-og-publikasjoner/Saker/Sak/?p=%s" % sid}, mem)
                        n += 1
                        time.sleep(0.4)
                    checked[sid] = mod
                    time.sleep(0.4)
                if calls >= 80:
                    break
            self.kv_set("no_checked", checked)
            self._ok("Norway votes", True, "%d new" % n)
        except (self.FetchError, ValueError, KeyError, TypeError) as e:
            self.kv_set("no_checked", checked)
            self._ok("Norway votes", False, str(e))

    # ================================================================== ICELAND
    def pull_is(self):
        import xml.etree.ElementTree as ET
        t = datetime.date.today()
        cur = t.year - 1868 if t.month >= 9 else t.year - 1869
        parties = self.kv("is_parties", {}) or {}
        n = 0
        try:
            for lt in (cur, cur - 1):
                x = ET.fromstring(self.get("https://www.althingi.is/altext/xml/atkvaedagreidslur/?lthing=%d" % lt, timeout=90).encode("utf-8"))
                A = x.findall("atkvæðagreiðsla")
                if not A:
                    continue
                for a in reversed(A):
                    if n >= 50 or self._stop():
                        break
                    num = a.get("atkvæðagreiðslunúmer")
                    if not num or self.have("IS-" + num):
                        continue
                    method = (a.findtext("samantekt/aðferð") or "").strip()
                    if method and method != "atkvæðagreiðslukerfi":
                        continue     # voice votes: no names
                    d = ET.fromstring(self.get("https://www.althingi.is/altext/xml/atkvaedagreidslur/atkvaedagreidsla/?numer=%s" % num, timeout=60).encode("utf-8"))
                    mem = []
                    for tm in d.findall("atkvæðaskrá/þingmaður"):
                        pid = tm.get("id") or ""
                        if pid and pid not in parties:
                            try:
                                ts = self.get("https://www.althingi.is/altext/xml/thingmenn/thingmadur/thingseta/?nr=%s" % pid, timeout=40)
                                fl = re.findall(r"<þingflokkur[^>]*>([^<]+)</þingflokkur>", ts)
                                parties[pid] = fl[-1].strip() if fl else ""
                            except self.FetchError:
                                parties[pid] = ""
                            time.sleep(0.3)
                        pos = IS_POS.get((tm.findtext("atkvæði") or "").strip().lower(), "O")
                        mem.append(("IS:" + pid, (tm.findtext("nafn") or "").strip(), parties.get(pid, ""), pos, ""))
                    res = (a.findtext("samantekt/afgreiðsla") or "").strip()
                    self.save_vote({"id": "IS-" + num, "cc": "IS", "chamber": "A", "date": (a.findtext("tími") or "")[:10],
                                    "title": (a.findtext("mál/málsheiti") or "").strip(), "question": (a.findtext("tegund") or "").strip(),
                                    "result": {"samþykkt": "Adopted", "fellt": "Rejected"}.get(res, res), "src": "althingi",
                                    "url": "https://www.althingi.is/dba-bin/atkvgr.pl?nnafnak=%s" % num}, mem)
                    n += 1
                    time.sleep(0.4)
                if n >= 50:
                    break      # otherwise carry on into last session (a new session starts with few or no named votes)
            self.kv_set("is_parties", parties)
            self._ok("Iceland votes", True, "%d new" % n)
        except (self.FetchError, ET.ParseError, ValueError) as e:
            self.kv_set("is_parties", parties)
            self._ok("Iceland votes", False, str(e))

    # ================================================================== YOUR STATE LEGISLATURE (Open States)
    def pull_openstates(self):
        key = self.settings.get("openstates_key")
        st = ((self.settings.get("home") or {}).get("state") or "").lower()
        if not key or not st:
            self._ok("State legislature votes", True, "off: needs a free Open States key and your state (my reps)" if not key else "pick your state in my reps")
            return
        jur = "ocd-jurisdiction/country:us/state:%s/government" % st
        n = 0
        try:
            for page in (1, 2, 3):
                d = self.getj("https://v3.openstates.org/bills?" + urllib.parse.urlencode({"jurisdiction": jur, "sort": "latest_action_desc", "include": "votes", "per_page": 20, "page": page}),
                              timeout=60, headers={"X-API-KEY": key})
                for b in d.get("results") or []:
                    for v in b.get("votes") or []:
                        vid = "OS-" + (v.get("id") or "").split("/")[-1]
                        if self.have(vid):
                            continue
                        mem = []
                        for x in v.get("votes") or []:
                            opt = (x.get("option") or "").lower()
                            pos = "Y" if opt == "yes" else "N" if opt == "no" else "A" if opt in ("abstain", "not voting", "present") else "X" if opt in ("absent", "excused") else "O"
                            vt = x.get("voter") or {}
                            nm = vt.get("name") or x.get("voter_name") or ""
                            mem.append(("OS:" + (vt.get("id") or self._slug(nm)), nm, vt.get("party") or "", pos, ""))
                        cnt = {c.get("option"): c.get("value") for c in v.get("counts") or []}
                        org = (v.get("organization") or {}).get("classification") or ""
                        self.save_vote({"id": vid, "cc": "US-" + st.upper(), "chamber": {"upper": "U", "lower": "L"}.get(org, org[:1].upper()),
                                        "date": (v.get("start_date") or "")[:10], "title": "%s %s" % (b.get("identifier") or "", b.get("title") or ""),
                                        "question": v.get("motion_text") or "", "result": (v.get("result") or "").title(), "src": "openstates",
                                        "yes": cnt.get("yes"), "no": cnt.get("no"), "absent": cnt.get("absent") or cnt.get("excused"),
                                        "url": b.get("openstates_url") or ""}, mem)
                        n += 1
                if not (d.get("pagination") or {}).get("max_page", 1) > page:
                    break
                time.sleep(1.5)
            self._ok("State legislature votes", True, "%d new from %s" % (n, st.upper()))
        except (self.FetchError, ValueError, KeyError, TypeError) as e:
            self._ok("State legislature votes", False, str(e))

    @staticmethod
    def _slug(s):
        return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")

    def state_votes(self):
        st = ((self.settings.get("home") or {}).get("state") or "").upper()
        h = self.settings.get("home") or {}
        if not st:
            return {"state": "", "votes": []}
        reps = [p for p in (self.states().get(st) or []) if (p.get("c") == "upper" and str(p.get("d")) == str(h.get("upper"))) or
                (p.get("c") == "lower" and str(p.get("d")) == str(h.get("lower")))]
        rows = self.q("SELECT id, date, title, question, result, yes, no, chamber, url FROM votes WHERE cc=? ORDER BY date DESC LIMIT 60", ("US-" + st,))
        out = []
        for r in rows:
            d = dict(r)
            d["mine"] = []
            for p in reps:
                last = (p.get("n") or "").split()[-1:] or [""]
                m = self.q("SELECT name, pos FROM mvotes WHERE vote_id=? AND name LIKE ?", (r["id"], "%" + last[0] + "%"), one=True)
                if m:
                    d["mine"].append({"name": p.get("n"), "pos": m["pos"]})
            out.append(d)
        return {"state": st, "votes": out, "key": bool(self.settings.get("openstates_key")), "reps": [p.get("n") for p in reps]}

    def state_member_key(self, st, name):
        """The Open States voting record for a state lawmaker, found by name (their votes are stored under cc US-XX)."""
        toks = self._norm(name)
        if not toks:
            return {"key": ""}
        for r in self.q("SELECT key, name FROM members WHERE cc=? AND name LIKE ?", ("US-" + (st or "").upper(), "%" + toks[-1] + "%")):
            t = self._norm(r["name"])
            if toks[-1] in t and (len(t) == 1 or toks[0][:1] == t[0][:1]):
                return {"key": r["key"]}
        return {"key": ""}

    # ================================================================== ELECTION NIGHT
    WD_UA = {"Accept": "application/sparql-results+json", "User-Agent": "ArchieWorld/3.19 (a personal offline assistant; results viewer)"}

    def pull_elections(self):
        today = datetime.date.today()
        try:
            if time.time() - (self.kv("elec_list_at", 0) or 0) > 12 * 3600:
                start, end = today - datetime.timedelta(days=60), today + datetime.timedelta(days=90)
                q = ("SELECT ?e ?eLabel ?date ?countryLabel ?cc ?article WHERE { ?e wdt:P31/wdt:P279* wd:Q40231; wdt:P585 ?date. "
                     'FILTER(?date >= "%sT00:00:00Z"^^xsd:dateTime && ?date < "%sT00:00:00Z"^^xsd:dateTime) '
                     "?e wdt:P17 ?country. OPTIONAL { ?country wdt:P297 ?cc. } "
                     "?article schema:about ?e; schema:isPartOf <https://en.wikipedia.org/>. "
                     'SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } } LIMIT 600') % (start.isoformat(), end.isoformat())
                d = self.getj("https://query.wikidata.org/sparql?format=json&query=" + urllib.parse.quote(q), timeout=90, headers=self.WD_UA)
                per = {}
                for b in (d.get("results") or {}).get("bindings") or []:
                    label = b.get("eLabel", {}).get("value", "")
                    if ELECTION_SKIP.search(label) or re.match(r"^Q\d+$", label):
                        continue
                    country = b.get("countryLabel", {}).get("value", "")
                    if per.get(country, 0) >= 5:
                        continue
                    per[country] = per.get(country, 0) + 1
                    eid = b["e"]["value"].rsplit("/", 1)[-1]
                    art = urllib.parse.unquote(b["article"]["value"].rsplit("/wiki/", 1)[-1])
                    self.x("""INSERT INTO elec(id, title, date, cc, country, article, at) VALUES(?,?,?,?,?,?,0)
                              ON CONFLICT(id) DO UPDATE SET title=excluded.title, date=excluded.date, cc=excluded.cc, country=excluded.country, article=excluded.article""",
                           (eid, label, b["date"]["value"][:10], b.get("cc", {}).get("value", ""), country, art))
                self.x("DELETE FROM elec WHERE date < ?", ((today - datetime.timedelta(days=75)).isoformat(),))
                self.kv_set("elec_list_at", time.time())
            n = 0
            for r in self.q("SELECT * FROM elec ORDER BY date DESC"):
                if self._stop() or n >= 25:
                    break
                try:
                    dd = datetime.date.fromisoformat(r["date"])
                except ValueError:
                    continue
                age = (today - dd).days
                every = 600 if -1 <= age <= 4 else 6 * 3600 if age <= 20 else 86400 if age <= 75 else None
                if age < -1:
                    every = 86400 * 3     # upcoming: refresh the line-up now and then
                if every is None or time.time() - (r["at"] or 0) < every:
                    continue
                try:
                    j = self.getj("https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&section=0&redirects=1&format=json&page=" + urllib.parse.quote(r["article"]),
                                  timeout=40, headers={"User-Agent": self.WD_UA["User-Agent"]})
                    wt = ((j.get("parse") or {}).get("wikitext") or {}).get("*", "")
                    data = parse_election(wt) or {}
                except (self.FetchError, ValueError):
                    data = None
                if data is not None:
                    old = r["data"] or ""
                    new = json.dumps(data)
                    self.x("UPDATE elec SET data=?, at=?, changed=CASE WHEN ?!=COALESCE(data,'') THEN ? ELSE changed END WHERE id=?",
                           (new, int(time.time()), new, int(time.time()), r["id"]))
                n += 1
                time.sleep(1)
            self._ok("Election results (Wikipedia)", True, "%d checked" % n)
        except (self.FetchError, ValueError, KeyError) as e:
            self._ok("Election results (Wikipedia)", False, str(e))

    def elections(self, eid=""):
        today = datetime.date.today()
        if eid:
            r = self.q("SELECT * FROM elec WHERE id=?", (eid,), one=True)
            if r and time.time() - (r["at"] or 0) > 600:
                try:   # opened by hand: fetch it now
                    j = self.getj("https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&section=0&redirects=1&format=json&page=" + urllib.parse.quote(r["article"]),
                                  timeout=40, headers={"User-Agent": self.WD_UA["User-Agent"]})
                    data = parse_election(((j.get("parse") or {}).get("wikitext") or {}).get("*", "")) or {}
                    self.x("UPDATE elec SET data=?, at=? WHERE id=?", (json.dumps(data), int(time.time()), eid))
                    r = self.q("SELECT * FROM elec WHERE id=?", (eid,), one=True)
                except (self.FetchError, ValueError):
                    pass
            if not r:
                return {"error": "not found"}
            d = dict(r)
            d["data"] = json.loads(d["data"] or "{}")
            d["url"] = "https://en.wikipedia.org/wiki/" + urllib.parse.quote(d["article"])
            return d
        out = []
        for r in self.q("SELECT id, title, date, cc, country, article, data, at, changed FROM elec ORDER BY date"):
            d = dict(r)
            data = json.loads(d.pop("data") or "{}")
            d["results"] = bool(data.get("results"))
            rows = [x for x in data.get("rows") or [] if x.get("seats") is not None or x.get("pct") is not None or x.get("electoral") is not None]
            d["top"] = sorted(rows, key=lambda x: -(x.get("seats") or x.get("electoral") or x.get("pct") or 0))[:3]
            d["total"] = data.get("seats_total")
            d["majority"] = data.get("majority")
            try:
                d["age"] = (today - datetime.date.fromisoformat(d["date"])).days
            except ValueError:
                d["age"] = None
            out.append(d)
        return {"elections": out, "as_of": self.kv("elec_list_at", 0)}

    def extra_get(self, name, a):
        if name == "debates":
            return self.debates(a("cc"), a("q"), a("key"), a("skip", "0"))
        if name == "debate_text":
            return self.debate_text(a("package"), a("granule"), a("q"))
        if name == "uk_money":
            return self.uk_money(a("key"))
        if name == "state_votes":
            return self.state_votes()
        if name == "state_member":
            return self.state_member_key(a("state"), a("name"))
        if name == "elections":
            return self.elections(a("id"))
        return None
