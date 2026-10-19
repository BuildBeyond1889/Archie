"""Archie World: lawmaking, part two (US).

The Supreme Court (every justice's vote in every case, opinions, how often each pair agrees, upcoming
arguments), federal judges' financial disclosures, congressional committees (what each is for, who sits on
it, what's been sent to it, its hearings), lobbying (who lobbies whom on what, and for how much), and stock
trades reported by members of Congress.

Public record only, stored in World/civic/civic.db. No scores or ratings of anyone.

Sources (free, no sign-ups):
  Supreme Court cases and votes ..... Oyez (api.oyez.org; Cornell LII / Justia)
  Argument calendar ................. supremecourt.gov (PDF)
  Judges' financial disclosures ..... CourtListener / Free Law Project bulk data (monthly)
  Committees and their members ...... unitedstates/congress-legislators (public domain)
  Lobbying reports (LD-2, LD-203) ... lda.gov REST API (U.S. Senate / House)
  House stock trades (PTRs) ......... disclosures-clerk.house.gov
  Senate stock trades (PTRs) ........ efdsearch.senate.gov (only if turned on: needs its terms accepted)
"""
import bz2
import csv
import datetime
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import zipfile

csv.field_size_limit(1 << 26)

MORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS sc_cases(id TEXT PRIMARY KEY, term INTEGER, docket TEXT, name TEXT, href TEXT, granted TEXT,
  argued TEXT, decided TEXT, arg_next TEXT, question TEXT, facts TEXT, conclusion TEXT, description TEXT, maj INTEGER,
  min INTEGER, winner TEXT, justia TEXT, votes TEXT, lower TEXT, parties TEXT, detail_at INTEGER, srcmod TEXT);
CREATE INDEX IF NOT EXISTS sc_term ON sc_cases(term);
CREATE TABLE IF NOT EXISTS sc_justices(name TEXT PRIMARY KEY, ident TEXT, role TEXT, appointed_by TEXT, start TEXT, last_seen TEXT);
CREATE TABLE IF NOT EXISTS jd_people(id INTEGER PRIMARY KEY, name TEXT, court TEXT, title TEXT, active INTEGER, scotus INTEGER, start TEXT);
CREATE TABLE IF NOT EXISTS jd_disc(id INTEGER PRIMARY KEY, person INTEGER, year INTEGER, rtype TEXT, url TEXT, pages INTEGER, amended INTEGER);
CREATE INDEX IF NOT EXISTS jd_disc_p ON jd_disc(person);
CREATE TABLE IF NOT EXISTS jd_items(disc INTEGER, kind TEXT, a TEXT, b TEXT, c TEXT, d TEXT, e TEXT);
CREATE INDEX IF NOT EXISTS jd_items_d ON jd_items(disc, kind);
CREATE TABLE IF NOT EXISTS lda(uuid TEXT PRIMARY KEY, year INTEGER, period TEXT, ftype TEXT, client TEXT, client_id INTEGER,
  client_desc TEXT, registrant TEXT, reg_id INTEGER, inhouse INTEGER, amount REAL, issues TEXT, gov TEXT, lobbyists TEXT,
  revolving INTEGER, text TEXT, posted TEXT, url TEXT);
CREATE INDEX IF NOT EXISTS lda_client ON lda(client_id);
CREATE INDEX IF NOT EXISTS lda_reg ON lda(reg_id);
CREATE INDEX IF NOT EXISTS lda_year ON lda(year);
CREATE TABLE IF NOT EXISTS lda_bill(uuid TEXT, bill TEXT, PRIMARY KEY(uuid, bill));
CREATE INDEX IF NOT EXISTS lda_bill_b ON lda_bill(bill);
CREATE TABLE IF NOT EXISTS bill_cmte(bill TEXT, code TEXT, sub TEXT, date TEXT, PRIMARY KEY(bill, code, sub));
CREATE INDEX IF NOT EXISTS bill_cmte_c ON bill_cmte(code);
CREATE TABLE IF NOT EXISTS ptr_docs(doc TEXT PRIMARY KEY, chamber TEXT, who TEXT, name TEXT, area TEXT, filed TEXT, year INTEGER,
  status TEXT, n INTEGER, url TEXT, at INTEGER);
CREATE INDEX IF NOT EXISTS ptr_who ON ptr_docs(who);
CREATE TABLE IF NOT EXISTS trades(doc TEXT, i INTEGER, who TEXT, name TEXT, chamber TEXT, tx_date TEXT, notified TEXT, filed TEXT,
  owner TEXT, ticker TEXT, asset TEXT, atype TEXT, tx TEXT, lo REAL, hi REAL, amount TEXT, note TEXT, PRIMARY KEY(doc, i));
CREATE INDEX IF NOT EXISTS trades_who ON trades(who, tx_date);
CREATE INDEX IF NOT EXISTS trades_date ON trades(tx_date);
CREATE INDEX IF NOT EXISTS trades_tk ON trades(ticker);
"""

MORE_JOBS = {"civ_scotus4": "the Supreme Court's cases (Oyez)", "civ_cmte": "congressional committees",
             "civ_judges2": "judges' financial disclosures (about 50 MB once a month)", "civ_lda": "lobbying reports (a few hundred pages an hour)",
             "civ_trades": "stock trades reported by members of Congress"}

# What makes some committees matter, in a sentence. Plain facts about the job, not opinions about the members.
CMTE_ROLE = {
    "HSAP": "Writes the yearly spending bills that fund the federal government.",
    "SSAP": "Writes the yearly spending bills that fund the federal government.",
    "HSWM": "Writes tax law (the Constitution says tax bills start in the House), plus Social Security, Medicare and trade.",
    "SSFI": "Handles taxes, trade, Social Security and Medicare in the Senate.",
    "HSRU": "Sets the terms for debating each bill on the House floor: how long, and which amendments are allowed.",
    "SSRA": "Runs the Senate's own rules and buildings, and federal election law.",
    "SSJU": "Holds the hearings on the President's picks for federal judges, including Supreme Court justices, and handles criminal law and immigration.",
    "HSJU": "Handles courts, criminal law, immigration, antitrust and constitutional amendments; impeachment starts here.",
    "HSIF": "One of the broadest House committees: health care, energy, telecommunications and consumer protection.",
    "HSBU": "Writes the yearly budget resolution, which sets overall spending and revenue limits.",
    "SSBU": "Writes the yearly budget resolution, which sets overall spending and revenue limits.",
    "SSFR": "Reviews treaties and the President's ambassador picks.",
    "HSFA": "Handles foreign aid, diplomacy and arms sales to other countries.",
    "HSAS": "Writes the yearly defense policy bill (the National Defense Authorization Act).",
    "SSAS": "Writes the yearly defense policy bill and reviews top military promotions.",
    "HLIG": "Oversees the intelligence agencies; much of its work is classified.",
    "SLIN": "Oversees the intelligence agencies; much of its work is classified.",
    "HSGO": "The House's main investigating committee; it can look into almost any part of the government.",
    "SSGA": "The Senate's main investigating committee, and homeland security.",
    "HSBA": "Banks, housing, insurance and financial markets.",
    "SSBK": "Banks, housing, financial markets and the Federal Reserve; reviews nominees for those posts.",
    "HSHA": "Runs the House's own operations and handles federal election law.",
    "HSSO": "Investigates complaints about House members' conduct.",
    "SLET": "Investigates complaints about senators' conduct.",
    "JSTX": "Nonpartisan staff of tax experts who estimate what tax bills would cost. No bills are sent to it.",
    "JSEC": "Studies the economy and holds hearings. No bills are sent to it.",
    "JSLC": "Oversees the Library of Congress and the art in the Capitol.",
    "JSPR": "Oversees the Government Publishing Office.",
    "JCSE": "The Helsinki Commission: watches human rights and security in Europe. Includes members from the executive branch.",
    "HSZS": "A select committee that studies competition between the US and China and makes recommendations. It doesn't write bills.",
    "HSQJ": "A select subcommittee looking into remaining questions about the January 6, 2021 attack on the Capitol.",
}
KEY_CMTES = ["HSAP", "SSAP", "HSWM", "SSFI", "HSRU", "SSJU", "HSIF", "HSAS", "SSAS", "HSBU", "SSBU", "SSFR", "HLIG", "SLIN"]

BILL_REF = re.compile(r"(?<![A-Za-z.])(H\.?\s?R\.?|H\.?\s?J\.?\s?Res\.?|S\.?\s?J\.?\s?Res\.?|H\.?\s?Con\.?\s?Res\.?|S\.?\s?Con\.?\s?Res\.?|H\.?\s?Res\.?|S\.?\s?Res\.?|S\.)\s?(\d{1,5})\b", re.I)

# ---------------------------------------------------------------- House stock-trade PDF text -> trades
TX_RE = re.compile(r"(?:(?<=[\s\]])|^)(P|S \(partial\)|S|E)\s+(\d\d/\d\d/\d{4})\s+(\d\d/\d\d/\d{4})\s+(?=\$|Over|Spouse)")
META = re.compile(r"^(F\s*S|S\s*O|D|C|L|Description|Comments|Filing Status|Subholding Of)\s*:", re.I)
HEAD = re.compile(r"^(P\s*T\s*R|F\s*I|T|ID\s*Owner.*|TypeDate.*|DateAmount.*|Gains\s*>|\$200\?|Name:.*|Status:.*|State/District:.*|"
                  r"Clerk of the House.*|Periodic Transaction Report|Filer Information|Transactions)$", re.I)
TX_TYPES = {"P": "purchase", "S": "sale", "S (partial)": "partial sale", "E": "exchange"}
OWNERS = {"SP": "spouse", "JT": "joint", "DC": "dependent child"}


def _money(s):
    try:
        return float(s.replace("$", "").replace(",", ""))
    except ValueError:
        return None


def _mdy(d):
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", d or "")
    return "%s-%02d-%02d" % (m.group(3), int(m.group(1)), int(m.group(2))) if m else ""


def parse_house_ptr(text):
    """Text of an electronically filed House Periodic Transaction Report -> list of trades."""
    text = (text or "").replace("\x00", "")
    text = re.sub(r"Filing ID #\d+", "\n", text)
    cut = re.search(r"\n\s*\*\s*For the complete list of asset type", text)
    if cut:
        text = text[:cut.start()]
    lines, kinds, meta_prev, prev_line = [], [], False, ""
    for l in (x.strip() for x in text.split("\n")):
        if not l or HEAD.match(l):
            continue
        is_meta = bool(META.match(l)) or (meta_prev and len(prev_line) >= 95 and not re.match(r"^(SP|JT|DC)\s", l))
        lines.append(l)
        kinds.append(is_meta)
        meta_prev, prev_line = is_meta, l
    groups, cur = [], []
    for l, m in zip(lines, kinds):
        if m:
            if cur:
                groups.append([" ".join(cur), []])
                cur = []
            if groups:
                groups[-1][1].append(l)
        else:
            cur.append(l)
    if cur:
        groups.append([" ".join(cur), []])
    trades = []
    for core, meta in groups:
        parts = [core]
        if len(TX_RE.findall(core)) > 1:
            parts = [p for p in re.split(r"\s(?=(?:SP|JT|DC)\s)", core) if p.strip()]
        for core in parts:
            c = " " + core
            m = TX_RE.search(c)
            if not m:
                continue
            om = re.match(r"^\s*(SP|JT|DC)\s+", c)
            owner = OWNERS[om.group(1)] if om else ""
            rest = c[m.end():]
            amts = re.findall(r"\$[\d,]+(?:\.\d+)?", rest)
            over = re.search(r"Over \$[\d,]+", rest)
            lo = _money(amts[0]) if amts else (_money(over.group(0)[5:]) if over else None)
            hi = _money(amts[1]) if len(amts) > 1 else None
            amount = ("%s - %s" % (amts[0], amts[1])) if hi else (amts[0] if amts else (over.group(0) if over else ""))
            asset = re.sub(r"\$[\d,]+(?:\.\d+)?|Over \$[\d,]+|Spouse/DC|\s-\s(?=\s|$)", " ", c[:m.start()] + " " + rest)
            asset = re.sub(r"^\s*(SP|JT|DC)\s+", "", asset)
            at = re.search(r"\[([A-Z]{2})\]", asset)
            asset = re.sub(r"\[[A-Z]{2}\]", " ", asset)
            tk = re.findall(r"\(([A-Z][A-Z0-9.\-]{0,6})\)", asset)
            note = ""
            for ml in meta:
                if ml[:2] == "D:" or ml.lower().startswith("description"):
                    note = ml.split(":", 1)[1].strip()
                elif note and not META.match(ml):
                    note += " " + ml
            trades.append({"owner": owner, "asset": re.sub(r"\s+", " ", asset).strip(" -")[:300], "ticker": tk[-1] if tk else "",
                           "atype": at.group(1) if at else "", "tx": TX_TYPES.get(m.group(1), m.group(1)),
                           "tx_date": _mdy(m.group(2)), "notified": _mdy(m.group(3)), "lo": lo, "hi": hi, "amount": amount, "note": note[:400]})
    return trades


def parse_senate_ptr(page):
    """An electronically filed Senate PTR page (HTML table) -> list of trades."""
    m = re.search(r"<table[^>]*>(.*?)</table>", page or "", re.S | re.I)
    if not m:
        return []
    tab = m.group(1)
    heads = [_clean(h).lower() for h in re.findall(r"<th[^>]*>(.*?)</th>", tab, re.S | re.I)]
    col = lambda *names: next((i for i, h in enumerate(heads) if any(n in h for n in names)), -1)
    ci = {"date": col("transaction date"), "owner": col("owner"), "ticker": col("ticker"), "asset": col("asset name"),
          "atype": col("asset type"), "type": next((i for i, h in enumerate(heads) if h == "type"), col("type")), "amount": col("amount"), "comment": col("comment")}
    out = []
    body = re.search(r"<tbody[^>]*>(.*?)</tbody>", tab, re.S | re.I)
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1) if body else tab, re.S | re.I):
        td = [_clean(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
        if len(td) < 6:
            continue
        g = lambda k: td[ci[k]] if 0 <= ci[k] < len(td) else ""
        own = g("owner").lower()
        owner = "" if own in ("self", "") else "spouse" if "spouse" in own else "joint" if "joint" in own else "dependent child" if "child" in own or "dependent" in own else own
        t = g("type").lower()
        tx = "partial sale" if "partial" in t else "sale" if "sale" in t else "purchase" if "purchase" in t else "exchange" if "exchange" in t else t
        amts = re.findall(r"\$[\d,]+(?:\.\d+)?", g("amount"))
        tk = g("ticker")
        out.append({"owner": owner, "asset": g("asset")[:300], "ticker": "" if tk in ("--", "-", "N/A") else tk.split()[0][:10],
                    "atype": g("atype")[:40], "tx": tx, "tx_date": _mdy(g("date")), "notified": "", "lo": _money(amts[0]) if amts else None,
                    "hi": _money(amts[1]) if len(amts) > 1 else None, "amount": g("amount")[:60], "note": ("" if g("comment") in ("--", "-") else g("comment"))[:400]})
    return out


def _clean(s):
    import html as _h
    return re.sub(r"\s+", " ", _h.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _strip(s):
    return _clean(re.sub(r"</p>|<br\s*/?>", "\n", s or "", flags=re.I))


def _ts(v):
    try:
        return datetime.datetime.utcfromtimestamp(int(v)).strftime("%Y-%m-%d") if v else ""
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _term_now():
    t = datetime.date.today()
    return t.year if t.month >= 10 else t.year - 1


class CivicMore:
    """Mixed into Civic. Uses its storage helpers (q, x, many, kv, download, _ok ...)."""

    def more_init(self):
        self.db.executescript(MORE_SCHEMA)
        self.db.commit()
        self._cm = None
        self._cm_at = 0

    def more_jobs(self):
        return [("civ_cmte", 604800, self.pull_committees), ("civ_scotus4", 21600, self.pull_scotus),
                ("civ_trades", 10800, self.pull_trades), ("civ_lda", 3600, self.pull_lda), ("civ_judges2", 7 * 86400, self.pull_judges)]

    # ================================================================== certificates
    def aia_get(self, url, timeout=40, headers=None):
        """Some sites (api.oyez.org) don't send the middle certificate of their chain. Browsers fetch it themselves;
        Python doesn't. This does what a browser does: reads where the site's certificate says its issuer lives,
        downloads that issuer certificate, and verifies normally against Windows' trusted roots with it added.
        Nothing is trusted that the normal roots wouldn't trust."""
        import ssl, socket, gzip
        host = urllib.parse.urlparse(url).hostname
        pem_path = os.path.join(self.cache, "extra_ca.pem")
        # Windows only keeps the root certificates it has needed so far (it fetches others when a browser asks),
        # so Python can miss a root that's perfectly standard. Archie carries Mozilla's list of trusted roots
        # (the same one Firefox uses, from the certifi package) and adds it to Windows' own.
        mozilla = os.path.join(self.dir, "cacert.pem")
        def make_ctx():
            c = ssl.create_default_context()
            for p in (mozilla, pem_path):
                if os.path.exists(p):
                    try:
                        c.load_verify_locations(cafile=p)
                    except (ssl.SSLError, OSError):
                        pass
            return c
        ctx = make_ctx()
        def fetch_with(c):
            req = urllib.request.Request(url, headers=dict({"User-Agent": self.ua, "Accept-Encoding": "gzip"}, **(headers or {})))
            with urllib.request.urlopen(req, timeout=timeout, context=c) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return body.decode(r.headers.get_content_charset() or "utf-8", errors="replace")
        try:
            return fetch_with(ctx)
        except Exception as e:
            if "issuer" not in str(e):     # only a missing middle certificate is worth chasing
                raise self.FetchError(str(e)[:120])
        try:   # look at the site's own certificate (not trusting it) to find its issuer's address, then that one's issuer
            raw = ssl.create_default_context()
            raw.check_hostname = False
            raw.verify_mode = ssl.CERT_NONE
            with socket.create_connection((host, 443), timeout=20) as sock, raw.wrap_socket(sock, server_hostname=host) as ss:
                der = ss.getpeercert(binary_form=True)
            old = open(pem_path, encoding="ascii", errors="replace").read() if os.path.exists(pem_path) else ""
            added = 0
            for _ in range(3):
                m = re.search(rb"\x06\x08\x2b\x06\x01\x05\x05\x07\x30\x02\x86([\x00-\x7f])", der)
                if not m:
                    break
                issuer_url = der[m.end():m.end() + m.group(1)[0]].decode("ascii", "replace")
                with urllib.request.urlopen(urllib.request.Request(issuer_url, headers={"User-Agent": self.ua}), timeout=30) as r:
                    data = r.read()
                if data.lstrip().startswith(b"-----BEGIN"):
                    pem = data.decode("ascii", "replace")
                    der = ssl.PEM_cert_to_DER_cert(pem)
                elif data[:1] == b"\x30" and b"\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x07\x02" in data[:40]:
                    break      # a PKCS#7 bundle; not handled
                else:
                    der = data
                    pem = ssl.DER_cert_to_PEM_cert(data)
                if pem.strip() not in old:
                    with open(pem_path, "a", encoding="ascii") as f:
                        f.write("\n" + pem.strip() + "\n")
                    old += pem
                    added += 1
                try:
                    return fetch_with(make_ctx())
                except Exception as e2:
                    if "issuer" not in str(e2):
                        raise self.FetchError(str(e2)[:120])
            raise self.FetchError("couldn't complete the site's certificate chain")
        except self.FetchError:
            raise
        except Exception as e:
            raise self.FetchError(str(e)[:120])

    # ================================================================== COMMITTEES
    def pull_committees(self):
        try:
            for name in ("committees-current.json", "committee-membership-current.json"):
                txt = self.get("https://unitedstates.github.io/congress-legislators/" + name, timeout=60)
                json.loads(txt)
                with open(os.path.join(self.cache, name), "w", encoding="utf-8") as f:
                    f.write(txt)
                time.sleep(1)
            self._cm = None
            self._ok("Committees", True, "%d committees" % len(self.cmte_data()["list"]))
        except (self.FetchError, ValueError, OSError) as e:
            self._ok("Committees", bool(self.cmte_data()["list"]), "using the copy built into Archie (%s)" % e)

    def cmte_data(self):
        if self._cm is not None and time.time() - self._cm_at < 600:
            return self._cm
        C = self._json_file("committees-current.json") or []
        M = self._json_file("committee-membership-current.json") or {}
        by, lst = {}, []
        for c in C:
            code = c.get("thomas_id") or ""
            if not code:
                continue
            ch = {"house": "House", "senate": "Senate", "joint": "Joint"}.get(c.get("type"), c.get("type", ""))
            d = {"code": code, "chamber": ch, "name": c.get("name", ""), "short": _short(c.get("name", "")), "url": c.get("url", ""),
                 "about": c.get("jurisdiction", ""), "role": CMTE_ROLE.get(code, ""), "parent": "", "subs": [], "members": M.get(code, [])}
            by[code] = d
            lst.append(d)
            for s in c.get("subcommittees") or []:
                sc = code + (s.get("thomas_id") or "")
                sd = {"code": sc, "chamber": ch, "name": s.get("name", ""), "short": s.get("name", ""), "url": "", "about": "", "role": "",
                      "parent": code, "subs": [], "members": M.get(sc, [])}
                by[sc] = sd
                d["subs"].append(sc)
        mine = {}
        for code, mem in M.items():
            for m in mem:
                if m.get("bioguide"):
                    mine.setdefault(m["bioguide"], []).append((code, m.get("title", ""), m.get("rank", 99)))
        self._cm = {"by": by, "list": lst, "mine": mine}
        self._cm_at = time.time()
        return self._cm

    def _split(self, members):
        P = self.us_people()
        s = {}
        for m in members:
            p = (P.get(m.get("bioguide") or "") or {}).get("party") or ("majority" if m.get("party") == "majority" else "minority")
            s[p] = s.get(p, 0) + 1
        return s

    def committees(self):
        cm = self.cmte_data()
        P = self.us_people()
        counts = {r["code"]: r["n"] for r in self.q("SELECT code, COUNT(DISTINCT bill) n FROM bill_cmte GROUP BY code")}
        moving = {r["code"]: r["n"] for r in self.q("SELECT c.code, COUNT(DISTINCT c.bill) n FROM bill_cmte c JOIN bills b ON b.id=c.bill WHERE b.stage >= 2 GROUP BY c.code")}
        out = []
        for c in cm["list"]:
            mem = c["members"]
            chair = next((m for m in mem if (m.get("title") or "").lower().startswith("chair")), None)
            rank = next((m for m in mem if "ranking" in (m.get("title") or "").lower() or "vice chair" in (m.get("title") or "").lower()), None)
            out.append({"code": c["code"], "chamber": c["chamber"], "name": c["name"], "short": c["short"], "role": c["role"], "key": c["code"] in KEY_CMTES,
                        "n": len(mem), "split": self._split(mem), "subs": len(c["subs"]), "bills": counts.get(c["code"], 0), "moved": moving.get(c["code"], 0),
                        "chair": {"name": chair["name"], "key": "US:" + chair["bioguide"], "party": (P.get(chair["bioguide"]) or {}).get("party", "")} if chair else None,
                        "ranking": {"name": rank["name"], "key": "US:" + rank["bioguide"], "title": rank.get("title", ""), "party": (P.get(rank["bioguide"]) or {}).get("party", "")} if rank else None})
        return {"committees": out, "loaded": bool(out)}

    def committee(self, code):
        cm = self.cmte_data()
        c = cm["by"].get(code)
        if not c:
            return {"error": "not found"}
        P = self.us_people()
        mem = []
        for m in sorted(c["members"], key=lambda m: (m.get("party") != "majority", m.get("rank") or 99)):
            p = P.get(m.get("bioguide") or "") or {}
            mem.append({"name": m.get("name", ""), "key": "US:" + m["bioguide"] if m.get("bioguide") else "", "title": m.get("title", ""), "side": m.get("party", ""),
                        "party": p.get("party", ""), "state": p.get("state", ""), "district": p.get("district"), "chamber": p.get("chamber", "")})
        top = c["parent"] or code
        bills = [dict(r) for r in self.q("""SELECT b.id, b.num, b.title, b.sponsor, b.party, b.stage, b.stage_text, b.latest_date, b.latest_text, MIN(c.date) referred
            FROM bill_cmte c JOIN bills b ON b.id=c.bill WHERE c.code=? """ + ("AND c.sub=? " if c["parent"] else "") + """GROUP BY b.id ORDER BY b.latest_date DESC LIMIT 80""",
                                          (top, code[len(top):]) if c["parent"] else (code,))]
        st = {r["stage"]: r["n"] for r in self.q("SELECT b.stage, COUNT(DISTINCT b.id) n FROM bill_cmte c JOIN bills b ON b.id=c.bill WHERE c.code=? GROUP BY b.stage", (top,))}
        hear = []
        if c["chamber"] == "Senate":
            key = re.sub(r"^(the )", "", c["short"] if not c["parent"] else cm["by"][top]["short"]).lower()
            for r in self.q("SELECT * FROM cal WHERE cc='US' AND kind='Senate committee' AND date >= ? ORDER BY date LIMIT 40", (datetime.date.today().isoformat(),)):
                if key[:28] in (r["body"] or "").lower():
                    hear.append(dict(r))
        lob = [dict(r) for r in self.q("""SELECT b.id, b.num, b.title, COUNT(DISTINCT l.client_id) clients FROM bill_cmte c JOIN lda_bill lb ON lb.bill=c.bill
            JOIN lda l ON l.uuid=lb.uuid JOIN bills b ON b.id=c.bill WHERE c.code=? GROUP BY b.id ORDER BY clients DESC LIMIT 8""", (top,))]
        return {"code": code, "chamber": c["chamber"], "name": c["name"], "short": c["short"], "about": c["about"], "role": c["role"], "url": c["url"] or (cm["by"].get(top) or {}).get("url", ""),
                "parent": c["parent"], "parent_name": cm["by"][c["parent"]]["name"] if c["parent"] else "",
                "subs": [{"code": s, "name": cm["by"][s]["name"], "n": len(cm["by"][s]["members"]),
                          "chair": next((m["name"] for m in cm["by"][s]["members"] if (m.get("title") or "").lower().startswith("chair")), "")} for s in c["subs"]],
                "members": mem, "split": self._split(c["members"]), "bills": bills, "stages": st, "hearings": hear, "lobbied": lob,
                "watching": bool(self.q("SELECT 1 FROM watch WHERE kind='committee' AND id=?", (code,), one=True))}

    def member_committees(self, bio):
        cm = self.cmte_data()
        out = []
        for code, title, rank in sorted(cm["mine"].get(bio, []), key=lambda x: (len(x[0]), x[0])):
            c = cm["by"].get(code)
            if c:
                out.append({"code": code, "name": c["name"] if not c["parent"] else cm["by"][c["parent"]]["short"] + ": " + c["name"], "title": title, "sub": bool(c["parent"])})
        return out

    def save_bill_cmte(self, bid, items):
        """items: [(code like 'HSAG', sub like '15' or '', date)] from BILLSTATUS. Called inside a batch (no commit)."""
        self._xn("DELETE FROM bill_cmte WHERE bill=?", (bid,))
        for code, sub, d in items:
            self._xn("INSERT OR REPLACE INTO bill_cmte(bill, code, sub, date) VALUES(?,?,?,?)", (bid, code, sub, d))

    # ================================================================== SUPREME COURT
    def pull_scotus(self):
        term = _term_now()
        n_new = 0
        try:
            for t in (term, term - 1, term - 2):
                L = self.getj("https://api.oyez.org/cases?per_page=0&filter=term:%d" % t, timeout=60)
                for c in L or []:
                    if self._stop():
                        return
                    if not isinstance(c, dict):
                        continue
                    tl = {e.get("event"): _ts((e.get("dates") or [0])[0]) for e in (c.get("timeline") or []) if isinstance(e, dict)}
                    doc = (c.get("docket_number") or "").strip()
                    if not doc:
                        continue
                    cid = "%d-%s" % (t, doc)
                    mod = json.dumps(tl, sort_keys=True)
                    old = self.q("SELECT srcmod, detail_at FROM sc_cases WHERE id=?", (cid,), one=True)
                    if old and old["srcmod"] == mod and old["detail_at"]:
                        continue
                    self.x("""INSERT INTO sc_cases(id, term, docket, name, href, granted, argued, decided, description, justia, srcmod)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, href=excluded.href, granted=excluded.granted,
                        argued=excluded.argued, decided=excluded.decided, description=excluded.description, justia=excluded.justia""",
                           (cid, t, doc, c.get("name", ""), c.get("href", ""), tl.get("Granted", ""), tl.get("Argued", ""), tl.get("Decided", ""),
                            _strip(c.get("description") or ""), c.get("justia_url") or "", ""))
                    try:
                        self._scotus_detail(cid, c.get("href", ""), mod)
                        n_new += 1
                    except Exception:      # one odd case shouldn't stop the rest
                        pass
                    time.sleep(1.2)
                time.sleep(2)
            self._ok("Supreme Court (Oyez)", True, "%d cases updated" % n_new)
        except (self.FetchError, ValueError, TypeError) as e:
            self._ok("Supreme Court (Oyez)", False, str(e))
        self._scotus_calendar()

    def _scotus_detail(self, cid, href, mod):
        d = self.getj(href, timeout=60)
        if not isinstance(d, dict):
            return
        votes, maj, mn, winner = [], 0, 0, ""
        decs = [x for x in (d.get("decisions") or []) if isinstance(x, dict)]
        if decs:
            dec = decs[0]
            maj, mn, winner = dec.get("majority_vote") or 0, dec.get("minority_vote") or 0, dec.get("winning_party") or ""
            for v in dec.get("votes") or []:
                if not isinstance(v, dict):
                    continue
                m = v.get("member") or {}
                votes.append({"name": m.get("name", ""), "side": v.get("vote") or "", "op": v.get("opinion_type") or "",
                              "joining": [j.get("name", "") for j in (v.get("joining") or []) if isinstance(j, dict)]})
                self._sc_justice(m, d)
        else:
            for hb in d.get("heard_by") or []:
                for m in (hb.get("members") or []) if isinstance(hb, dict) else []:
                    if isinstance(m, dict):
                        self._sc_justice(m, d)
        lower = (d.get("lower_court") or {}).get("name", "") if isinstance(d.get("lower_court"), dict) else ""
        parties = [d.get("first_party") or "", d.get("second_party") or ""]
        tl = {e.get("event"): _ts((e.get("dates") or [0])[0]) for e in (d.get("timeline") or []) if isinstance(e, dict)}
        self.x("""UPDATE sc_cases SET question=?, facts=?, conclusion=?, maj=?, min=?, winner=?, votes=?, lower=?, parties=?, detail_at=?, srcmod=?,
                  granted=COALESCE(NULLIF(?, ''), granted), argued=COALESCE(NULLIF(?, ''), argued), decided=COALESCE(NULLIF(?, ''), decided),
                  justia=COALESCE(NULLIF(?, ''), justia) WHERE id=?""",
               (_strip(d.get("question") or ""), _strip(d.get("facts_of_the_case") or ""), _strip(d.get("conclusion") or ""), maj, mn, winner,
                json.dumps(votes), lower, json.dumps(parties), int(time.time()), mod, tl.get("Granted", ""), tl.get("Argued", ""), tl.get("Decided", ""),
                d.get("justia_url") or "", cid))

    def _sc_justice(self, m, case):
        name = m.get("name") or ""
        if not name:
            return
        roles = [r for r in (m.get("roles") or []) if isinstance(r, dict)]
        r = roles[-1] if roles else {}
        seen = ""
        self.x("""INSERT INTO sc_justices(name, ident, role, appointed_by, start, last_seen) VALUES(?,?,?,?,?,?)
                  ON CONFLICT(name) DO UPDATE SET role=excluded.role, appointed_by=excluded.appointed_by, start=excluded.start,
                  last_seen=MAX(COALESCE(sc_justices.last_seen, ''), excluded.last_seen)""",
               (name, m.get("identifier") or "", r.get("role_title") or "", r.get("appointing_president") or "", _ts(r.get("date_start")), seen))

    def _scotus_calendar(self):
        """The Court's argument calendars (PDFs): which case is argued on which day."""
        try:
            from pypdf import PdfReader
        except ImportError:
            self._ok("Supreme Court argument calendar", False, "needs the PDF reader: run Install Extras.bat")
            return
        today = datetime.date.today()
        term = _term_now()
        months = [(term, m) for m in ("October", "November", "December")] + [(term + 1, m) for m in ("January", "February", "March", "April")]
        rows, got = [], 0
        for yr, mon in months:
            if datetime.date(yr, list(MONTHS).index(mon) + 1, 28) < today:
                continue
            name = "MonthlyArgumentCal%s%d.pdf" % (mon, yr)
            try:
                path = self.download("https://www.supremecourt.gov/oral_arguments/argument_calendars/" + name, "scotus_" + name, timeout=60, max_age=86400)
            except self.FetchError:
                continue      # not published yet
            try:
                text = "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
            except Exception:
                continue
            got += 1
            day = None
            for line in text.split("\n"):
                l = re.sub(r"\s+", " ", line).strip()
                dm = re.match(r"^(Monday|Tuesday|Wednesday|Thursday|Friday),\s*([A-Za-z ]+?)\s*([\d ]{1,3})$", l)
                if dm:
                    mo = re.sub(r"\s", "", dm.group(2))
                    dd = re.sub(r"\s", "", dm.group(3))
                    if mo in MONTHS and dd.isdigit():
                        y = term if MONTHS[mo] >= 10 else term + 1
                        try:
                            day = datetime.date(y, MONTHS[mo], int(dd)).isoformat()
                        except ValueError:
                            day = None
                    continue
                cm = re.search(r"\b(\d{2}-\d{1,5})\b\s+(.*)", l)
                if cm and day:
                    rows.append((cm.group(1), day, cm.group(2)))
        for doc, day, title in rows:
            r = self.q("SELECT id, name FROM sc_cases WHERE docket=? ORDER BY term DESC LIMIT 1", (doc,), one=True)
            if r:
                self.x("UPDATE sc_cases SET arg_next=? WHERE id=?", (day, r["id"]))
            nm = r["name"] if r else title.title()
            if day >= today.isoformat():
                self.x("INSERT OR REPLACE INTO cal(id, cc, date, time, title, kind, body, url, seen) VALUES(?,?,?,?,?,?,?,?,?)",
                       ("US-SC-" + doc, "US", day, "10:00 AM", "Oral argument: " + nm, "Supreme Court", "Supreme Court · No. " + doc,
                        "https://www.supremecourt.gov/oral_arguments/calendarsandlists.aspx", int(time.time())))
        self._ok("Supreme Court argument calendar", True, "%d arguments scheduled in %d calendars" % (len(rows), got))

    def _current_justices(self):
        last = self.q("SELECT votes FROM sc_cases WHERE votes IS NOT NULL AND votes != '[]' ORDER BY decided DESC LIMIT 1", one=True)
        names = [v["name"] for v in json.loads(last["votes"])] if last else []
        J = {r["name"]: dict(r) for r in self.q("SELECT * FROM sc_justices")}
        out = [J.get(n) or {"name": n} for n in names]
        out.sort(key=lambda j: (0 if "Chief" in (j.get("role") or "") else 1, j.get("start") or ""))
        return out

    def scotus(self, term=""):
        terms = [r["term"] for r in self.q("SELECT DISTINCT term FROM sc_cases ORDER BY term DESC")]
        decided_terms = [r["term"] for r in self.q("SELECT DISTINCT term FROM sc_cases WHERE decided != '' ORDER BY term DESC")]
        term = int(term) if str(term).isdigit() else (decided_terms[0] if decided_terms else (terms[0] if terms else _term_now()))
        rows = self.q("SELECT id, term, docket, name, granted, argued, decided, arg_next, maj, min, winner, votes, description, question FROM sc_cases WHERE term=? ORDER BY COALESCE(NULLIF(decided,''), NULLIF(argued,''), arg_next, granted) DESC", (term,))
        cases, stats, pair, pairn = [], {}, {}, {}
        for r in rows:
            d = dict(r)
            V = json.loads(d.pop("votes") or "[]")
            d["n_votes"] = len(V)
            d["question"] = (d["question"] or "")[:300]
            cases.append(d)
            if not V:
                continue
            for v in V:
                s = stats.setdefault(v["name"], {"cases": 0, "majority": 0, "dissent": 0, "wrote_majority": 0, "concur": 0, "wrote_dissent": 0})
                s["cases"] += 1
                if v["side"] == "majority":
                    s["majority"] += 1
                elif v["side"] == "minority":
                    s["dissent"] += 1
                op = (v.get("op") or "").lower()
                if op == "majority" or op == "plurality":
                    s["wrote_majority"] += 1
                elif "concurr" in op:
                    s["concur"] += 1
                elif "dissent" in op:
                    s["wrote_dissent"] += 1
            for a in V:
                for b in V:
                    if a["name"] >= b["name"] or a["side"] not in ("majority", "minority") or b["side"] not in ("majority", "minority"):
                        continue
                    k = a["name"] + "|" + b["name"]
                    pairn[k] = pairn.get(k, 0) + 1
                    if a["side"] == b["side"]:
                        pair[k] = pair.get(k, 0) + 1
        J = self._current_justices()
        names = [j["name"] for j in J] or sorted(stats)
        matrix = {}
        for a in names:
            for b in names:
                if a < b and pairn.get(a + "|" + b):
                    matrix[a + "|" + b] = [pair.get(a + "|" + b, 0), pairn[a + "|" + b]]
        up = [dict(r) for r in self.q("SELECT id, docket, name, arg_next, granted, description FROM sc_cases WHERE arg_next >= ? ORDER BY arg_next LIMIT 40", (datetime.date.today().isoformat(),))]
        pending = [dict(r) for r in self.q("SELECT id, docket, name, argued, granted FROM sc_cases WHERE (decided IS NULL OR decided='') AND (argued != '' OR granted != '') AND (arg_next IS NULL OR arg_next < ?) ORDER BY term DESC, argued DESC LIMIT 40", (datetime.date.today().isoformat(),))]
        unan = sum(1 for c in cases if c["n_votes"] and not c["min"])
        return {"term": term, "terms": terms, "cases": cases, "justices": J, "stats": stats, "matrix": matrix, "upcoming": up, "pending": pending,
                "decided": sum(1 for c in cases if c["decided"]), "unanimous": unan, "loaded": bool(terms),
                "judges": (self.q("SELECT COUNT(*) n FROM jd_people", one=True) or {"n": 0})["n"]}

    def scotus_case(self, cid):
        r = self.q("SELECT * FROM sc_cases WHERE id=?", (cid,), one=True)
        if not r:
            return {"error": "not found"}
        d = dict(r)
        d["votes"] = json.loads(d.get("votes") or "[]")
        d["parties"] = json.loads(d.get("parties") or "[]")
        s = self.q("SELECT text FROM summaries WHERE key=?", ("case:" + cid,), one=True)
        d["plain"] = s["text"] if s else ""
        return d

    def justice(self, name):
        j = self.q("SELECT * FROM sc_justices WHERE name=?", (name,), one=True)
        if not j:
            return {"error": "not found"}
        out = dict(j)
        rec = []
        for r in self.q("SELECT id, term, docket, name, decided, maj, min, votes FROM sc_cases WHERE votes LIKE ? ORDER BY decided DESC LIMIT 400", ('%"' + name.replace('"', '') + '"%',)):
            for v in json.loads(r["votes"] or "[]"):
                if v["name"] == name:
                    rec.append({"id": r["id"], "term": r["term"], "name": r["name"], "decided": r["decided"], "side": v["side"], "op": v["op"],
                                "joining": v.get("joining") or [], "maj": r["maj"], "min": r["min"]})
        out["record"] = rec
        out["disclosure_person"] = self._judge_by_name(name, scotus=True)
        return out

    # ================================================================== JUDGES' FINANCIAL DISCLOSURES (CourtListener)
    CL = "https://com-courtlistener-storage.s3-us-west-2.amazonaws.com"

    def pull_judges(self):
        try:
            x = self.get(self.CL + "/?list-type=2&prefix=bulk-data/financial-disclosures-20", timeout=60)
            dates = sorted(set(re.findall(r"financial-disclosures-(\d{4}-\d\d-\d\d)\.csv\.bz2", x)))
            if not dates:
                raise self.FetchError("no files listed")
            date = dates[-1]
            if self.kv("cl_date") == date and self.q("SELECT 1 FROM jd_disc LIMIT 1", one=True):
                if not self.kv("jd_fix1"):     # 3.17.0 counted Supreme Court law clerks as justices; fix that in place
                    path = self.download("%s/bulk-data/people-db-positions-%s.csv.bz2" % (self.CL, date), "cl_people-db-positions.csv.bz2", timeout=300)
                    jus = {_int(r.get("person_id")) for r in _rows(path) if _is_justice(r)}
                    with self.lock:
                        self.db.execute("UPDATE jd_people SET scotus=0")
                        self.db.executemany("UPDATE jd_people SET scotus=1 WHERE id=?", [(i,) for i in jus])
                        self.db.commit()
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    self.kv_set("jd_fix1", 1)
                self._ok("Judges' disclosures", True, "up to date (%s)" % date)
                return
            def get(prefix):
                return self.download("%s/bulk-data/%s-%s.csv.bz2" % (self.CL, prefix, date), "cl_%s.csv.bz2" % prefix, timeout=900)
            self._ok("Judges' disclosures", True, "downloading the list of disclosures")
            disc = {}
            for r in _rows(get("financial-disclosures")):
                disc[r["id"]] = (r.get("person_id"), r.get("year"), r.get("report_type") or "", r.get("filepath") or r.get("download_filepath") or "",
                                 r.get("page_count"), r.get("is_amended"))
            people = {d[0] for d in disc.values() if d[0]}
            courts = {}
            try:
                for r in _rows(get("courts")):
                    courts[r.get("id")] = r.get("short_name") or r.get("full_name") or r.get("id")
            except self.FetchError:
                pass
            pos = {}
            for r in _rows(get("people-db-positions")):
                p = r.get("person_id")
                if p in people and r.get("court_id"):
                    pos.setdefault(p, []).append(r)
            names = {}
            for r in _rows(get("people-db-people")):
                if r["id"] in people:
                    suf = {"jr": "Jr.", "sr": "Sr.", "ii": "II", "iii": "III", "iv": "IV"}.get((r.get("name_suffix") or "").lower().strip("."), r.get("name_suffix") or "")
                    names[r["id"]] = " ".join(x for x in (r.get("name_first"), r.get("name_middle"), r.get("name_last")) if x) + (", " + suf if suf else "")
            P, scotus = [], set()
            for pid, nm in names.items():
                L = sorted(pos.get(pid, []), key=lambda r: r.get("date_start") or "")
                cur = L[-1] if L else {}
                sc = any(_is_justice(r) for r in L)
                if sc:
                    scotus.add(pid)
                active = 1 if cur and not cur.get("date_termination") else 0
                title = (cur.get("job_title") or "") or {"jus": "Justice", "c-jus": "Chief Justice", "ass-jus": "Associate Justice", "jud": "Judge",
                                                         "c-jud": "Chief Judge", "ass-jud": "Associate Judge", "mag": "Magistrate Judge", "ret-senior-jud": "Senior Judge"}.get(cur.get("position_type"), "Judge")
                P.append((int(pid), nm, courts.get(cur.get("court_id"), cur.get("court_id") or ""), title, active, 1 if sc else 0, cur.get("date_start") or ""))
            with self.lock:
                self.db.execute("DELETE FROM jd_people")
                self.db.execute("DELETE FROM jd_disc")
                self.db.execute("DELETE FROM jd_items")
                self.db.executemany("INSERT OR REPLACE INTO jd_people(id, name, court, title, active, scotus, start) VALUES(?,?,?,?,?,?,?)", P)
                self.db.executemany("INSERT OR REPLACE INTO jd_disc(id, person, year, rtype, url, pages, amended) VALUES(?,?,?,?,?,?,?)",
                                    [(int(k), int(v[0]), _int(v[1]), v[2], ("https://storage.courtlistener.com/" + v[3]) if v[3] and not v[3].startswith("http") else v[3],
                                      _int(v[4]), 1 if str(v[5]).lower() in ("t", "true", "1") else 0) for k, v in disc.items() if v[0] and v[0] in names])
                self.db.commit()
            sc_disc = {k for k, v in disc.items() if v[0] in scotus}
            parts = [("financial-disclosures-gifts", "gift", ("source", "description", "value")),
                     ("financial-disclosures-reimbursements", "reimb", ("source", "date_raw", "location", "purpose", "items_paid_or_provided")),
                     ("financial-disclosures-non-investment-income", "income", ("date_raw", "source_type", "income_amount")),
                     ("financial-disclosures-positions", "position", ("position", "organization_name")),
                     ("financial-disclosures-debts", "debt", ("creditor_name", "description", "value_code")),
                     ("financial-disclosures-agreements", "agreement", ("date_raw", "parties_and_terms")),
                     ("financial-disclosures-spousal-income", "spouse", ("source_type", "date_raw")),
                     ("financial-disclosure-investments", "invest", None)]
            for prefix, kind, cols in parts:
                if self._stop():
                    return
                self._ok("Judges' disclosures", True, "loading %s" % kind)
                try:
                    path = get(prefix)
                except self.FetchError:
                    continue
                batch = []
                for r in _rows(path):
                    did = r.get("financial_disclosure_id")
                    if kind == "invest":
                        if did not in sc_disc:
                            continue
                        vals = (r.get("description"), r.get("gross_value_code"), "%s|%s" % (r.get("income_during_reporting_period_code") or "", r.get("income_during_reporting_period_type") or ""),
                                "%s|%s|%s" % (r.get("transaction_during_reporting_period") or "", r.get("transaction_date_raw") or "", r.get("transaction_value_code") or ""), r.get("transaction_gain_code") or "")
                    else:
                        if did not in disc:
                            continue
                        vals = tuple((r.get(c) or "")[:1500] for c in cols) + ("",) * (5 - len(cols))
                    batch.append((_int(did), kind) + tuple((v or "")[:1500] for v in vals))
                    if len(batch) >= 5000:
                        self.many("INSERT INTO jd_items(disc, kind, a, b, c, d, e) VALUES(?,?,?,?,?,?,?)", batch)
                        batch = []
                if batch:
                    self.many("INSERT INTO jd_items(disc, kind, a, b, c, d, e) VALUES(?,?,?,?,?,?,?)", batch)
                try:
                    os.remove(path)
                except OSError:
                    pass
            self.kv_set("cl_date", date)
            self._ok("Judges' disclosures", True, "%d judges, %d reports (%s)" % (len(P), len(disc), date))
        except (self.FetchError, OSError, EOFError, csv.Error) as e:
            self._ok("Judges' disclosures", False, str(e)[:160])

    def _judge_by_name(self, name, scotus=False):
        toks = self._norm(name)
        if not toks:
            return None
        last = toks[-1]
        for r in self.q("SELECT id, name FROM jd_people WHERE name LIKE ?" + (" AND scotus=1" if scotus else ""), ("%" + last + "%",)):
            t = self._norm(r["name"])
            if last in t and toks[0][:1] == t[0][:1]:
                return r["id"]
        return None

    def judges(self, q="", scope=""):
        w, a = ["1=1"], []
        if q:
            w.append("(name LIKE ? OR court LIKE ?)")
            a += ["%" + q + "%"] * 2
        if scope == "active":
            w.append("active=1")
        rows = self.q("SELECT p.*, (SELECT MAX(year) FROM jd_disc d WHERE d.person=p.id) last, (SELECT COUNT(*) FROM jd_disc d WHERE d.person=p.id) n FROM jd_people p WHERE "
                      + " AND ".join(w) + " ORDER BY scotus DESC, active DESC, last DESC, name LIMIT 150", a)
        tot = self.q("SELECT COUNT(*) n FROM jd_people", one=True)["n"]
        return {"judges": [dict(r) for r in rows], "total": tot, "as_of": self.kv("cl_date", "")}

    def judge(self, pid):
        p = self.q("SELECT * FROM jd_people WHERE id=?", (_int(pid),), one=True)
        if not p:
            return {"error": "not found"}
        out = dict(p)
        reps = []
        for d in self.q("SELECT * FROM jd_disc WHERE person=? ORDER BY year DESC", (p["id"],)):
            items = {}
            for it in self.q("SELECT kind, a, b, c, d, e FROM jd_items WHERE disc=?", (d["id"],)):
                items.setdefault(it["kind"], []).append([it["a"], it["b"], it["c"], it["d"], it["e"]])
            reps.append(dict(d, items=items))
        out["reports"] = reps
        out["as_of"] = self.kv("cl_date", "")
        return out

    # ================================================================== LOBBYING (LDA)
    LDA = "https://lda.gov/api/v1/"

    def _lda(self, path):
        h = {"Accept": "application/json"}
        if self.settings.get("lda_key"):
            h["Authorization"] = "Token " + self.settings["lda_key"]
        return self.getj(self.LDA + path, timeout=60, headers=h)

    def pull_lda(self):
        """Quarterly lobbying reports, 25 per page. Anonymous use allows about 15 requests a minute, so this
        works through the backlog a few hundred pages an hour and then keeps up with new filings."""
        st = self.kv("lda_state", {}) or {}
        y = datetime.date.today().year
        plan = [(y, q) for q in ("Q1", "Q2", "Q3", "Q4")] + [(y - 1, q) for q in ("Q4", "Q3", "Q2", "Q1")]
        gap = 1.0 if self.settings.get("lda_key") else 4.2
        budget, n = (400 if self.settings.get("lda_key") else 120), 0
        try:
            for yr, ft in plan:
                k = "%d%s" % (yr, ft)
                s = st.get(k) or {"page": 1, "done": False}
                if s.get("done"):
                    continue
                if yr == y and ft != "Q1" and datetime.date.today() < datetime.date(y, {"Q2": 7, "Q3": 10, "Q4": 12}[ft], 1 if ft != "Q4" else 31):
                    continue    # not filed yet
                while n < budget and not self._stop():
                    j = self._lda("filings/?filing_year=%d&filing_type=%s&page_size=25&page=%d" % (yr, ft, s["page"]))
                    n += 1
                    self._lda_store(j.get("results") or [])
                    s["total"] = j.get("count") or 0
                    if not j.get("next"):
                        s["done"] = True
                        break
                    s["page"] += 1
                    st[k] = s
                    if n % 10 == 0:
                        self.kv_set("lda_state", st)
                    time.sleep(gap)
                st[k] = s
                self.kv_set("lda_state", st)
                if n >= budget or self._stop():
                    break
            if n < budget and all((st.get("%d%s" % p) or {}).get("done") for p in plan[:1]):
                since = st.get("since") or (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
                page = 1
                while n < budget and not self._stop():
                    j = self._lda("filings/?filing_dt_posted_after=%s&page_size=25&page=%d" % (since, page))
                    n += 1
                    self._lda_store([r for r in j.get("results") or [] if re.match(r"^(Q[1-4]|[1-4]A)$", r.get("filing_type") or "")])
                    if not j.get("next"):
                        st["since"] = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
                        break
                    page += 1
                    time.sleep(gap)
                self.kv_set("lda_state", st)
            tot = self.q("SELECT COUNT(*) n FROM lda", one=True)["n"]
            want = sum((st.get("%d%s" % p) or {}).get("total", 0) for p in plan)
            self._ok("Lobbying reports", True, "%s reports loaded%s" % (format(tot, ","), " of about %s" % format(want, ",") if want > tot + 50 else ""))
        except (self.FetchError, ValueError, TypeError, KeyError) as e:
            self.kv_set("lda_state", st)
            self._ok("Lobbying reports", "429" in str(e) or bool(self.q("SELECT 1 FROM lda LIMIT 1", one=True)), ("paused: lda.gov asked Archie to slow down" if "429" in str(e) else str(e)))

    def _lda_store(self, results):
        rows, refs = [], []
        for f in results:
            u = f.get("filing_uuid")
            if not u:
                continue
            cl, rg = f.get("client") or {}, f.get("registrant") or {}
            inc, exp = f.get("income"), f.get("expenses")
            amount = float(inc) if inc not in (None, "") else float(exp) if exp not in (None, "") else None
            acts = f.get("lobbying_activities") or []
            issues, gov, lob, texts, rev = [], set(), {}, [], 0
            for a in acts:
                if a.get("general_issue_code"):
                    issues.append(a["general_issue_code"])
                for g in a.get("government_entities") or []:
                    if g.get("name"):
                        gov.add(g["name"])
                texts.append((a.get("description") or "")[:700])
                for l in a.get("lobbyists") or []:
                    p = l.get("lobbyist") or {}
                    nm = " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x).title()
                    cp = (l.get("covered_position") or "").strip()
                    if nm and nm not in lob:
                        lob[nm] = cp
                        if cp and cp.lower() not in ("n/a", "na", "none"):
                            rev += 1
            yr = f.get("filing_year") or 0
            text = " || ".join(t for t in texts if t)[:5000]
            rows.append((u, yr, f.get("filing_period") or "", f.get("filing_type") or "", cl.get("name") or "", cl.get("id") or 0,
                         (cl.get("general_description") or "")[:200], rg.get("name") or "", rg.get("id") or 0,
                         1 if (cl.get("name") or "").strip().upper() == (rg.get("name") or "").strip().upper() or (exp not in (None, "") and inc in (None, "")) else 0,
                         amount, ",".join(dict.fromkeys(issues)), "; ".join(sorted(gov))[:600], json.dumps(list(lob.items())[:60]), rev, text,
                         (f.get("dt_posted") or "")[:10], f.get("filing_document_url") or ""))
            cong = (yr - 1789) // 2 + 1 if yr else 0
            for m in BILL_REF.finditer(text):
                t = re.sub(r"[^a-z]", "", m.group(1).lower())
                t = {"hr": "hr", "s": "s", "hjres": "hjres", "sjres": "sjres", "hconres": "hconres", "sconres": "sconres", "hres": "hres", "sres": "sres"}.get(t)
                if t and cong:
                    refs.append((u, "US-%d-%s%s" % (cong, t, int(m.group(2)))))
        if rows:
            self.many("""INSERT OR REPLACE INTO lda(uuid, year, period, ftype, client, client_id, client_desc, registrant, reg_id, inhouse, amount, issues,
                         gov, lobbyists, revolving, text, posted, url) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
        if refs:
            self.many("INSERT OR IGNORE INTO lda_bill(uuid, bill) VALUES(?,?)", list(dict.fromkeys(refs)))

    ISSUES = None

    def lobbying(self, year="", issue="", q=""):
        years = [r["year"] for r in self.q("SELECT DISTINCT year FROM lda ORDER BY year DESC")]
        year = int(year) if str(year).isdigit() else (years[0] if years else datetime.date.today().year)
        w, a = ["year=?"], [year]
        if issue:
            w.append("(',' || issues || ',') LIKE ?")
            a.append("%," + issue + ",%")
        if q:
            w.append("(client LIKE ? OR registrant LIKE ? OR text LIKE ?)")
            a += ["%" + q + "%"] * 3
        W = " AND ".join(w)
        tot = self.q("SELECT COUNT(*) n, SUM(amount) amt, COUNT(DISTINCT client_id) clients, COUNT(DISTINCT reg_id) firms FROM lda WHERE " + W, a, one=True)
        clients = [dict(r) for r in self.q("SELECT client_id, MAX(client) client, MAX(client_desc) about, SUM(amount) amt, COUNT(*) n, GROUP_CONCAT(DISTINCT registrant) firms FROM lda WHERE "
                                            + W + " GROUP BY client_id ORDER BY amt DESC LIMIT 30", a)]
        firms = [dict(r) for r in self.q("SELECT reg_id, MAX(registrant) firm, SUM(amount) amt, COUNT(DISTINCT client_id) clients FROM lda WHERE inhouse=0 AND " + W + " GROUP BY reg_id ORDER BY amt DESC LIMIT 20", a)]
        iss = {}
        for r in self.q("SELECT issues, amount FROM lda WHERE " + W, a):
            for c in (r["issues"] or "").split(","):
                if c:
                    d = iss.setdefault(c, [0, 0.0])
                    d[0] += 1
                    d[1] += r["amount"] or 0
        bills = [dict(r) for r in self.q("""SELECT lb.bill, COUNT(DISTINCT l.client_id) clients, COUNT(*) n, b.num, b.title, b.stage, b.stage_text FROM lda_bill lb JOIN lda l ON l.uuid=lb.uuid
            LEFT JOIN bills b ON b.id=lb.bill WHERE """ + W.replace("year=", "l.year=") + " GROUP BY lb.bill ORDER BY clients DESC LIMIT 25", a)]
        rev = self.q("SELECT SUM(revolving) n FROM lda WHERE " + W, a, one=True)["n"] or 0
        st = self.kv("lda_state", {}) or {}
        return {"year": year, "years": years, "total": dict(tot) if tot else {}, "clients": clients, "firms": firms, "issues": sorted(([k, v[0], v[1]] for k, v in iss.items()), key=lambda x: -x[1]),
                "bills": bills, "revolving": rev, "issue_names": ISSUE_NAMES, "progress": {k: v for k, v in st.items() if isinstance(v, dict)}}

    def lobby_client(self, cid):
        rows = self.q("SELECT * FROM lda WHERE client_id=? ORDER BY year DESC, period DESC", (_int(cid),))
        if not rows:
            return {"error": "not found"}
        F, lob, bills = [], {}, {}
        for r in rows:
            d = dict(r)
            d["lobbyists"] = json.loads(d["lobbyists"] or "[]")
            for nm, cp in d["lobbyists"]:
                lob.setdefault(nm, cp)
            d["text"] = (d["text"] or "")[:1500]
            F.append(d)
        for r in self.q("SELECT lb.bill, b.num, b.title, b.stage, b.stage_text, COUNT(*) n FROM lda_bill lb JOIN lda l ON l.uuid=lb.uuid LEFT JOIN bills b ON b.id=lb.bill WHERE l.client_id=? GROUP BY lb.bill ORDER BY n DESC LIMIT 40", (_int(cid),)):
            bills[r["bill"]] = dict(r)
        return {"client": rows[0]["client"], "about": rows[0]["client_desc"], "filings": F, "lobbyists": [[k, v] for k, v in lob.items()][:120], "bills": list(bills.values()),
                "total": sum(r["amount"] or 0 for r in rows), "issue_names": ISSUE_NAMES}

    def bill_lobbying(self, bid):
        rows = self.q("""SELECT l.uuid, l.year, l.period, l.client, l.client_id, l.registrant, l.inhouse, l.amount, l.issues, l.text, l.url FROM lda_bill lb JOIN lda l ON l.uuid=lb.uuid
                         WHERE lb.bill=? ORDER BY l.year DESC, l.period DESC""", (bid,))
        num = re.match(r"US-\d+-([a-z]+)(\d+)$", bid or "")
        pat = None
        if num:
            lab = {"hr": r"H\.?\s?R\.?", "s": r"S\.", "hjres": r"H\.?\s?J\.?\s?Res\.?", "sjres": r"S\.?\s?J\.?\s?Res\.?", "hres": r"H\.?\s?Res\.?", "sres": r"S\.?\s?Res\.?",
                   "hconres": r"H\.?\s?Con\.?\s?Res\.?", "sconres": r"S\.?\s?Con\.?\s?Res\.?"}.get(num.group(1))
            if lab:
                pat = re.compile(r"(?<![A-Za-z.])" + lab + r"\s?" + num.group(2) + r"\b[^|]{0,240}", re.I)
        by = {}
        for r in rows:
            c = by.setdefault(r["client_id"], {"client": r["client"], "client_id": r["client_id"], "firms": set(), "n": 0, "amount": 0.0, "quote": ""})
            c["n"] += 1
            c["amount"] += r["amount"] or 0
            if not r["inhouse"]:
                c["firms"].add(r["registrant"])
            if pat and not c["quote"]:
                m = pat.search(r["text"] or "")
                if m:
                    c["quote"] = m.group(0)[:260]
        out = sorted(by.values(), key=lambda c: -c["amount"])
        for c in out:
            c["firms"] = sorted(c["firms"])
        st = self.kv("lda_state", {}) or {}
        cm = self.cmte_data()["by"]
        cms = [{"code": r["code"] + r["sub"] if cm.get(r["code"] + r["sub"]) else r["code"],
                "name": ((cm[r["code"]]["short"] + ": ") if r["sub"] and cm.get(r["code"]) and cm.get(r["code"] + r["sub"]) else "") + ((cm.get(r["code"] + r["sub"]) or {}).get("name") or ((cm.get(r["code"]) or {}).get("name", r["code"]) + (" (a subcommittee)" if r["sub"] else ""))),
                "sub": bool(r["sub"]), "date": r["date"]}
               for r in self.q("SELECT code, sub, date FROM bill_cmte WHERE bill=? ORDER BY date, sub", (bid,))]
        return {"clients": out, "filings": len(rows), "committees": cms, "loading": not all(v.get("done") for k, v in st.items() if isinstance(v, dict) and k.startswith(str(datetime.date.today().year)))}

    def lobby_gifts(self, key):
        """Political donations that lobbyists and their employers' PACs reported (LD-203) to a member of Congress. Live; cached a day."""
        p = self.us_people().get((key or "")[3:])
        if not p:
            return {"error": "Only members of Congress."}
        ck = "ld203:" + key
        c = self.kv(ck)
        if c and time.time() - c.get("at", 0) < 86400:
            return c
        last = p.get("last") or p["name"].split()[-1]
        first = self._norm(p["name"])[0] if self._norm(p["name"]) else ""
        by_from, by_firm, total, n, years, partial = {}, {}, 0.0, 0, [], False
        y = datetime.date.today().year
        for yr in (y, y - 1):
            for page in range(1, 7):
                try:
                    j = self._lda("contributions/?filing_year=%d&contribution_honoree=%s&page_size=25&page=%d" % (yr, urllib.parse.quote(last), page))
                except self.FetchError:
                    partial = True
                    break
                for r in j.get("results") or []:
                    firm = (r.get("registrant") or {}).get("name") or ""
                    lb = r.get("lobbyist") or {}
                    who = " ".join(x for x in (lb.get("first_name"), lb.get("last_name")) if x).title()
                    for it in r.get("contribution_items") or []:
                        hn = " ".join(self._norm((it.get("honoree_name") or "") + " " + (it.get("payee_name") or "")))
                        if last.lower() not in hn or (first and first not in hn and first[:1] not in [w[:1] for w in hn.split()]):
                            continue
                        amt = float(it.get("amount") or 0)
                        src = it.get("contributor_name") or ""
                        src = (who or firm) if src.strip().upper() in ("SELF", "") else src
                        total += amt
                        n += 1
                        by_from[src] = by_from.get(src, 0) + amt
                        by_firm[firm] = by_firm.get(firm, 0) + amt
                if not j.get("next"):
                    break
                time.sleep(0.6)
            years.append(yr)
        out = {"total": total, "n": n, "years": years, "partial": partial, "at": time.time(),
               "from": sorted(([k, v] for k, v in by_from.items()), key=lambda x: -x[1])[:40], "firms": sorted(([k, v] for k, v in by_firm.items()), key=lambda x: -x[1])[:25]}
        if not partial:
            self.kv_set(ck, out)
        return out

    # ================================================================== STOCK TRADES
    def pull_trades(self):
        self._house_ptrs()
        if self.settings.get("senate_efd"):
            self._senate_ptrs()
        else:
            self._ok("Stock trades (Senate)", True, "off: turn it on in Lawmaking › data sources")

    def _house_ptrs(self):
        y = datetime.date.today().year
        P = self.us_people()
        seat = {}
        for b, p in P.items():
            if p.get("chamber") == "H":
                seat["%s%02d" % (p["state"], int(p.get("district") or 0))] = b
        try:
            for yr in (y, y - 1):
                path = self.download("https://disclosures-clerk.house.gov/public_disc/financial-pdfs/%dFD.zip" % yr, "house_%dFD.zip" % yr,
                                     timeout=120, max_age=(43200 if yr == y else 30 * 86400))
                with zipfile.ZipFile(path) as z:
                    name = next((n for n in z.namelist() if n.lower().endswith(".txt")), None)
                    txt = z.read(name).decode("utf-8", errors="replace") if name else ""
                rows = []
                for line in txt.splitlines()[1:]:
                    f = line.split("\t")
                    if len(f) < 9 or f[4] != "P":
                        continue
                    doc = f[8].strip()
                    sd = f[5].strip()
                    who = seat.get(sd[:2] + "%02d" % _int(sd[2:])) if len(sd) >= 3 else None
                    if who and P[who].get("last", "").lower()[:4] not in (f[1] or "").lower():
                        who = None
                    nm = " ".join(x for x in (f[2], f[1], f[3]) if x).strip()
                    paper = not doc.startswith("2")
                    rows.append(("H-" + doc, "H", ("US:" + who) if who else "", nm, sd, _mdy(f[7]), yr, "paper" if paper else "new", 0,
                                 "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/%d/%s.pdf" % (yr, doc), int(time.time())))
                self.many("INSERT OR IGNORE INTO ptr_docs(doc, chamber, who, name, area, filed, year, status, n, url, at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows)
                for r in rows:     # people matched later (new member lists) get their key filled in
                    if r[2]:
                        self.x("UPDATE ptr_docs SET who=? WHERE doc=? AND who=''", (r[2], r[0]))
                time.sleep(1)
        except (self.FetchError, zipfile.BadZipFile, OSError) as e:
            self._ok("Stock trades (House)", False, str(e))
            return
        try:
            from pypdf import PdfReader
        except ImportError:
            self._ok("Stock trades (House)", False, "the list of reports is in, but reading them needs the PDF reader: run Install Extras.bat")
            return
        todo = self.q("SELECT * FROM ptr_docs WHERE chamber='H' AND status='new' ORDER BY filed DESC LIMIT 60")
        done = 0
        for d in todo:
            if self._stop():
                break
            try:
                path = self.download(d["url"], "ptr.pdf", timeout=60)
                text = "\n".join(pg.extract_text() or "" for pg in PdfReader(path).pages)
                T = parse_house_ptr(text)
                self._save_trades(d, T)
                self.x("UPDATE ptr_docs SET status=?, n=? WHERE doc=?", ("ok" if T else "empty", len(T), d["doc"]))
                done += 1
            except self.FetchError as e:
                self.x("UPDATE ptr_docs SET status=? WHERE doc=?", ("error" if "404" in str(e) else "new", d["doc"]))
            except Exception:
                self.x("UPDATE ptr_docs SET status='error' WHERE doc=?", (d["doc"],))
            time.sleep(2)
        left = self.q("SELECT COUNT(*) n FROM ptr_docs WHERE chamber='H' AND status='new'", one=True)["n"]
        n = self.q("SELECT COUNT(*) n FROM trades WHERE chamber='H'", one=True)["n"]
        self._ok("Stock trades (House)", True, "%s trades from %d reports%s" % (format(n, ","), self.q("SELECT COUNT(*) n FROM ptr_docs WHERE chamber='H' AND status='ok'", one=True)["n"],
                                                                         "; %d reports still to read" % left if left else ""))

    def _save_trades(self, d, T):
        with self.lock:
            self.db.execute("DELETE FROM trades WHERE doc=?", (d["doc"],))
            self.db.executemany("""INSERT OR REPLACE INTO trades(doc, i, who, name, chamber, tx_date, notified, filed, owner, ticker, asset, atype, tx, lo, hi, amount, note)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                [(d["doc"], i, d["who"], d["name"], d["chamber"], t["tx_date"], t["notified"], d["filed"], t["owner"], t["ticker"], t["asset"],
                                  t["atype"], t["tx"], t["lo"], t["hi"], t["amount"], t["note"]) for i, t in enumerate(T)])
            self.db.commit()

    # ---- Senate (eFD). The site asks visitors to accept its terms first; Archie only does that if you turned it on.
    EFD = "https://efdsearch.senate.gov"

    def _efd_session(self):
        import http.cookiejar
        cj = http.cookiejar.CookieJar()
        op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        op.addheaders = [("User-Agent", self.ua)]
        def go(url, data=None, headers=None):
            req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data is not None else None, headers=headers or {})
            try:
                with op.open(req, timeout=60) as r:
                    return r.read().decode("utf-8", errors="replace"), r.geturl()
            except Exception as e:
                raise self.FetchError(str(e)[:120])
        home, _ = go(self.EFD + "/search/home/")
        tok = re.search(r'name="csrfmiddlewaretoken"\s+value="([^"]+)"', home)
        if tok:
            go(self.EFD + "/search/home/", {"prohibition_agreement": "1", "csrfmiddlewaretoken": tok.group(1)}, {"Referer": self.EFD + "/search/home/"})
        csrf = next((c.value for c in cj if c.name in ("csrftoken", "csrf")), tok.group(1) if tok else "")
        return go, csrf

    def _senate_ptrs(self):
        P = self.us_people()
        sen = [(b, p) for b, p in P.items() if p.get("chamber") == "S"]
        try:
            go, csrf = self._efd_session()
            y = datetime.date.today().year
            start, rows = 0, []
            while True:
                txt, _ = go(self.EFD + "/search/report/data/", {"start": str(start), "length": "100", "report_types": "[11]", "filer_types": "[]",
                                                                "submitted_start_date": "01/01/%d 00:00:00" % (y - 1), "submitted_end_date": "", "candidate_state": "",
                                                                "senator_state": "", "office_id": "", "first_name": "", "last_name": "", "csrfmiddlewaretoken": csrf},
                            {"Referer": self.EFD + "/search/", "X-CSRFToken": csrf})
                j = json.loads(txt)
                data = j.get("data") or []
                for r in data:
                    if len(r) < 5:
                        continue
                    href = re.search(r'href="([^"]+)"', r[3] or "")
                    if not href:
                        continue
                    h = href.group(1)
                    nm = (_clean(r[0]) + " " + _clean(r[1])).strip()
                    who = ""
                    for b, p in sen:
                        if self._norm(r[1])[-1:] and self._norm(r[1])[-1] in self._norm(p["name"]) and self._norm(r[0])[:1] and self._norm(p["name"])[0][:1] == self._norm(r[0])[0][:1]:
                            who = "US:" + b
                            break
                    m = re.search(r"/(ptr|paper)/([0-9a-f-]+)/", h)
                    if not m:
                        continue
                    rows.append(("S-" + m.group(2), "S", who, nm, "", _mdy(r[4]), _int((_mdy(r[4]) or "0")[:4]), "paper" if m.group(1) == "paper" else "new", 0,
                                 self.EFD + h, int(time.time())))
                start += 100
                if not data or start >= _int(j.get("recordsFiltered") or j.get("recordsTotal")):
                    break
                time.sleep(2)
            self.many("INSERT OR IGNORE INTO ptr_docs(doc, chamber, who, name, area, filed, year, status, n, url, at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", rows)
            for d in self.q("SELECT * FROM ptr_docs WHERE chamber='S' AND status='new' ORDER BY filed DESC LIMIT 40"):
                if self._stop():
                    break
                page, url = go(d["url"])
                if "/search/home" in url:      # the session lapsed: agree again
                    go, csrf = self._efd_session()
                    page, url = go(d["url"])
                T = parse_senate_ptr(page)
                self._save_trades(d, T)
                self.x("UPDATE ptr_docs SET status=?, n=? WHERE doc=?", ("ok" if T else "empty", len(T), d["doc"]))
                time.sleep(2.5)
            n = self.q("SELECT COUNT(*) n FROM trades WHERE chamber='S'", one=True)["n"]
            left = self.q("SELECT COUNT(*) n FROM ptr_docs WHERE chamber='S' AND status='new'", one=True)["n"]
            self._ok("Stock trades (Senate)", True, "%s trades%s" % (format(n, ","), "; %d reports still to read" % left if left else ""))
        except (self.FetchError, ValueError, KeyError) as e:
            self._ok("Stock trades (Senate)", False, str(e))

    def trades(self, q="", tx="", who="", offset=0, days=""):
        w, a = ["1=1"], []
        if q:
            w.append("(t.ticker = ? OR t.asset LIKE ? OR t.name LIKE ?)")
            a += [q.upper(), "%" + q + "%", "%" + q + "%"]
        if tx == "buy":
            w.append("t.tx = 'purchase'")
        elif tx == "sell":
            w.append("t.tx LIKE '%sale'")
        if who:
            w.append("t.who = ?")
            a.append(who)
        if str(days).isdigit():
            w.append("t.tx_date >= ?")
            a.append((datetime.date.today() - datetime.timedelta(days=int(days))).isoformat())
        W = " AND ".join(w)
        rows = self.q("SELECT t.* FROM trades t WHERE " + W + " ORDER BY t.filed DESC, t.tx_date DESC LIMIT 100 OFFSET ?", a + [int(offset or 0)])
        P = self.us_people()
        out = []
        for r in rows:
            d = dict(r)
            p = P.get((d["who"] or "")[3:]) or {}
            d["party"] = p.get("party", "")
            d["label"] = p.get("name") or d["name"]
            out.append(d)
        since = (datetime.date.today() - datetime.timedelta(days=90)).isoformat()
        top = [dict(r) for r in self.q("SELECT ticker, MAX(asset) asset, COUNT(*) n, SUM(tx='purchase') buys, SUM(tx LIKE '%sale') sells, COUNT(DISTINCT COALESCE(NULLIF(who,''), name)) people FROM trades WHERE ticker != '' AND tx_date >= ? GROUP BY ticker ORDER BY n DESC LIMIT 15", (since,))]
        act = []
        for r in self.q("SELECT COALESCE(NULLIF(who,''), name) k, MAX(name) name, MAX(who) who, COUNT(*) n, MAX(chamber) chamber FROM trades WHERE tx_date >= ? GROUP BY k ORDER BY n DESC LIMIT 12", (since,)):
            p = P.get((r["who"] or "")[3:]) or {}
            act.append({"name": p.get("name") or r["name"], "who": r["who"], "n": r["n"], "party": p.get("party", ""), "chamber": r["chamber"]})
        st = {r["status"]: r["n"] for r in self.q("SELECT status, COUNT(*) n FROM ptr_docs GROUP BY status")}
        return {"trades": out, "top": top, "active": act, "docs": st, "senate": bool(self.settings.get("senate_efd")),
                "total": self.q("SELECT COUNT(*) n FROM trades", one=True)["n"]}

    def member_trades(self, key):
        rows = [dict(r) for r in self.q("SELECT * FROM trades WHERE who=? ORDER BY tx_date DESC LIMIT 300", (key,))]
        docs = [dict(r) for r in self.q("SELECT doc, filed, status, n, url FROM ptr_docs WHERE who=? ORDER BY filed DESC LIMIT 60", (key,))]
        tick = {}
        for r in rows:
            if r["ticker"]:
                t = tick.setdefault(r["ticker"], {"ticker": r["ticker"], "asset": r["asset"], "n": 0, "buys": 0, "sells": 0, "lo": 0.0})
                t["n"] += 1
                t["buys"] += r["tx"] == "purchase"
                t["sells"] += "sale" in r["tx"]
                t["lo"] += r["lo"] or 0
        p = self.us_people().get(key[3:]) or {}
        return {"trades": rows, "docs": docs, "tickers": sorted(tick.values(), key=lambda t: -t["n"])[:12],
                "senate_off": p.get("chamber") == "S" and not self.settings.get("senate_efd")}

    # ================================================================== glue
    def more_overview(self):
        n = lambda sql: (self.q(sql, one=True) or {"n": 0})["n"]
        return {"cases": n("SELECT COUNT(*) n FROM sc_cases"), "judges": n("SELECT COUNT(*) n FROM jd_people"), "lda": n("SELECT COUNT(*) n FROM lda"),
                "trades": n("SELECT COUNT(*) n FROM trades"), "committees": len(self.cmte_data()["list"]), "senate_efd": bool(self.settings.get("senate_efd")),
                "lda_key": bool(self.settings.get("lda_key"))}

    def more_snap(self, kind, xid):
        if kind == "case":
            r = self.q("SELECT decided, argued, arg_next, maj, min FROM sc_cases WHERE id=?", (xid,), one=True)
            return dict(r) if r else {}
        if kind == "committee":
            top = re.match(r"^[A-Z]{4}", xid).group(0) if re.match(r"^[A-Z]{4}", xid) else xid
            r = self.q("SELECT COUNT(DISTINCT c.bill) n, MAX(b.latest_date) last FROM bill_cmte c JOIN bills b ON b.id=c.bill WHERE c.code=?", (top,), one=True)
            h = [x["id"] for x in self.committee(xid).get("hearings", [])] if self.cmte_data()["by"].get(xid) else []
            return {"n": r["n"] if r else 0, "last": r["last"] if r else "", "hearings": h}
        return {}

    def more_events(self, kind, xid, old, new):
        ev = []
        if kind == "case":
            if new.get("decided") and new.get("decided") != old.get("decided"):
                ev.append(("decided", "The Court decided it, %s–%s" % (new.get("maj") or "?", new.get("min") or 0), new.get("decided")))
            elif new.get("arg_next") and new.get("arg_next") != old.get("arg_next"):
                ev.append(("scheduled", "Oral argument set for " + new["arg_next"], ""))
            elif new.get("argued") and new.get("argued") != old.get("argued"):
                ev.append(("argued", "Argued before the Court", new.get("argued")))
        elif kind == "committee":
            nh = [h for h in new.get("hearings", []) if h not in (old.get("hearings") or [])]
            if nh:
                r = self.q("SELECT date, title FROM cal WHERE id=?", (nh[0],), one=True)
                ev.append(("hearing", "New hearing: " + (r["title"] if r else ""), r["date"] if r else ""))
            if new.get("n", 0) > old.get("n", 0):
                ev.append(("bills", "%d new bill%s sent to it" % (new["n"] - old["n"], "" if new["n"] - old["n"] == 1 else "s"), ""))
            elif new.get("last") != old.get("last") and old.get("last"):
                ev.append(("update", "Action on a bill in its hands", new.get("last") or ""))
        return ev

    def more_link(self, kind, xid):
        return {"case": "gov=law:US:case:", "committee": "gov=law:US:cmte:"}.get(kind, "gov=law:US:") + xid

    def more_label(self, w):
        if w["kind"] == "case":
            r = self.q("SELECT name, docket, decided, argued, arg_next, maj, min FROM sc_cases WHERE id=?", (w["id"],), one=True)
            return dict(r) if r else None
        if w["kind"] == "committee":
            c = self.cmte_data()["by"].get(w["id"])
            return {"name": c["name"], "chamber": c["chamber"]} if c else None
        return None

    def more_get(self, name, a):
        if name == "scotus":
            return self.scotus(a("term"))
        if name == "case":
            return self.scotus_case(a("id"))
        if name == "justice":
            return self.justice(a("name"))
        if name == "judges":
            return self.judges(a("q"), a("scope"))
        if name == "judge":
            return self.judge(a("id"))
        if name == "committees":
            return self.committees()
        if name == "committee":
            return self.committee(a("code"))
        if name == "member_more":
            k = a("key")
            return {"committees": self.member_committees(k[3:]) if k.startswith("US:") else [], **self.member_trades(k)}
        if name == "lobbying":
            return self.lobbying(a("year"), a("issue"), a("q"))
        if name == "lobby_client":
            return self.lobby_client(a("id"))
        if name == "bill_lobbying":
            return self.bill_lobbying(a("id"))
        if name == "lobby_gifts":
            return self.lobby_gifts(a("key"))
        if name == "trades":
            return self.trades(a("q"), a("tx"), a("who"), a("offset", "0"), a("days"))
        return None


MONTHS = {m: i + 1 for i, m in enumerate(["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"])}

ISSUE_NAMES = {"ACC": "Accounting", "ADV": "Advertising", "AER": "Aerospace", "AGR": "Agriculture", "ALC": "Alcohol and drug abuse", "ANI": "Animals", "APP": "Apparel/clothing/textiles",
               "ART": "Arts/entertainment", "AUT": "Automotive industry", "AVI": "Aviation/aircraft/airlines", "BAN": "Banking", "BNK": "Bankruptcy", "BEV": "Beverage industry",
               "BUD": "Budget/appropriations", "CHM": "Chemicals/chemical industry", "CIV": "Civil rights/civil liberties", "CAW": "Clean air and water", "CDT": "Commodities (big ticket)",
               "COM": "Communications/broadcasting/radio/TV", "CPI": "Computer industry", "CSP": "Consumer issues/safety/products", "CON": "Constitution", "CPT": "Copyright/patent/trademark",
               "DEF": "Defense", "DOC": "District of Columbia", "DIS": "Disaster planning/emergencies", "ECN": "Economics/economic development", "EDU": "Education", "ENG": "Energy/nuclear",
               "ENV": "Environment/superfund", "FAM": "Family issues/abortion/adoption", "FIR": "Firearms/guns/ammunition", "FIN": "Financial institutions/investments/securities",
               "FOO": "Food industry (safety, labeling, etc.)", "FOR": "Foreign relations", "FUE": "Fuel/gas/oil", "GAM": "Gaming/gambling/casino", "GOV": "Government issues",
               "HCR": "Health issues", "HOM": "Homeland security", "HOU": "Housing", "IMM": "Immigration", "IND": "Indian/Native American affairs", "INS": "Insurance",
               "INT": "Intelligence and surveillance", "LBR": "Labor issues/antitrust/workplace", "LAW": "Law enforcement/crime/criminal justice", "MAN": "Manufacturing",
               "MAR": "Marine/maritime/boating/fisheries", "MIA": "Media (information/publishing)", "MED": "Medical/disease research/clinical labs", "MMM": "Medicare/Medicaid",
               "MON": "Minting/money/gold standard", "NAT": "Natural resources", "PHA": "Pharmacy", "POS": "Postal", "RRR": "Railroads", "RES": "Real estate/land use/conservation",
               "REL": "Religion", "RET": "Retirement", "ROD": "Roads/highway", "SCI": "Science/technology", "SMB": "Small business", "SPO": "Sports/athletics", "TAR": "Miscellaneous tariff bills",
               "TAX": "Taxation/Internal Revenue Code", "TEC": "Telecommunications", "TOB": "Tobacco", "TOR": "Torts", "TRD": "Trade (domestic and foreign)", "TRA": "Transportation",
               "TOU": "Travel/tourism", "TRU": "Trucking/shipping", "URB": "Urban development/municipalities", "UNM": "Unemployment", "UTI": "Utilities", "VET": "Veterans",
               "WAS": "Waste (hazardous/solid/interstate/nuclear)", "WEL": "Welfare"}


def _int(v):
    try:
        return int(str(v).strip() or 0)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0


def _is_justice(r):
    """A Supreme Court seat (not a law clerk's job at the Court)."""
    return r.get("court_id") == "scotus" and "jus" in (r.get("position_type") or "")


def _short(name):
    n = re.sub(r"^the ", "", re.sub(r"^(House|Senate|United States Senate)\s+(Permanent\s+)?(Select\s+|Special\s+)?Committee on\s+", "", name or ""))
    n = re.sub(r"^Joint Committee (of Congress )?on\s+", "", n)
    return n[:1].upper() + n[1:]


def _rows(path):
    """CourtListener's CSVs: Postgres COPY format with backslash escapes."""
    with bz2.open(path, "rt", encoding="utf-8", errors="replace", newline="") as f:
        for r in csv.DictReader(f, escapechar="\\", doublequote=False):
            yield r
