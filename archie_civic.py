"""Archie World: lawmaking.

Votes (who voted how), bills and where they stand, campaign money (US), executive actions (US),
the political calendar, and your own representatives. Everything is the public record, stored on this PC
in World/civic/civic.db so it works offline once it has been pulled.

Sources (all free, no sign-ups needed; optional keys go in World/civic/settings.json):
  US House roll calls ............ clerk.house.gov (XML)
  US Senate roll calls ........... senate.gov (XML)
  US bills + CRS summaries ....... govinfo.gov BILLSTATUS bulk data
  US members ..................... unitedstates/congress-legislators (public domain)
  US state legislators ........... Open States (CC0)
  Campaign money ................. FEC bulk files (+ the FEC API for earmarked/bundled money)
  Executive orders and rules ..... federalregister.gov API
  Your districts ................. US Census geocoder
  UK Commons/Lords votes, bills .. parliament.uk APIs
  European Parliament ............ HowTheyVote.eu (ODbL)
  Canada ......................... openparliament.ca
  Ireland ........................ Houses of the Oireachtas API
  Poland ......................... Sejm API
  Germany ........................ abgeordnetenwatch.de (CC0)
  Brazil ......................... Câmara dos Deputados open data
  Switzerland .................... parlament.ch open data
  Finland ........................ Eduskunta open data
  Denmark ........................ Folketinget open data (oda.ft.dk)
  Netherlands .................... Tweede Kamer open data (party votes)
  Estonia ........................ Riigikogu API
  France ......................... Assemblée nationale open data
  Spain .......................... Congreso de los Diputados open data
"""
import csv
import datetime
import html
import io
import json
import os
import re
import sqlite3
import threading
import time
import unicodedata
import urllib.parse
import urllib.request
import zipfile
import xml.etree.ElementTree as ET

from archie_civic_more import CivicMore, MORE_JOBS
from archie_civic_extra import CivicExtra, EXTRA_JOBS
from archie_civic_parl import CivicParl, PARL_JOBS, PARL_COUNTRIES
from archie_civic_local import CivicLocal, LOCAL_JOBS

CIVIC_SCHEMA = """
CREATE TABLE IF NOT EXISTS votes(
  id TEXT PRIMARY KEY, cc TEXT, chamber TEXT, date TEXT, title TEXT, question TEXT, result TEXT,
  yes INTEGER, no INTEGER, abstain INTEGER, absent INTEGER, bill TEXT, url TEXT, by_party TEXT,
  detail INTEGER DEFAULT 0, kind TEXT, src TEXT, extra TEXT);
CREATE INDEX IF NOT EXISTS votes_cc ON votes(cc, date);
CREATE INDEX IF NOT EXISTS votes_bill ON votes(bill);
CREATE TABLE IF NOT EXISTS mvotes(vote_id TEXT, member TEXT, name TEXT, party TEXT, pos TEXT,
  PRIMARY KEY(vote_id, member));
CREATE INDEX IF NOT EXISTS mvotes_member ON mvotes(member);
CREATE TABLE IF NOT EXISTS members(key TEXT PRIMARY KEY, cc TEXT, chamber TEXT, name TEXT, party TEXT,
  area TEXT, extra TEXT, seen TEXT);
CREATE INDEX IF NOT EXISTS members_cc ON members(cc);
CREATE TABLE IF NOT EXISTS bills(id TEXT PRIMARY KEY, cc TEXT, num TEXT, title TEXT, sponsor TEXT,
  sponsor_key TEXT, party TEXT, introduced TEXT, updated TEXT, stage INTEGER, stage_text TEXT,
  latest_date TEXT, latest_text TEXT, enacted TEXT, url TEXT, summary TEXT, subject TEXT, chamber TEXT,
  extra TEXT, srcmod TEXT);
CREATE INDEX IF NOT EXISTS bills_cc ON bills(cc, latest_date);
CREATE INDEX IF NOT EXISTS bills_sponsor ON bills(sponsor_key);
CREATE TABLE IF NOT EXISTS execs(id TEXT PRIMARY KEY, kind TEXT, title TEXT, date TEXT, signed TEXT,
  number TEXT, url TEXT, abstract TEXT, agency TEXT);
CREATE INDEX IF NOT EXISTS execs_date ON execs(date);
CREATE TABLE IF NOT EXISTS cal(id TEXT PRIMARY KEY, cc TEXT, date TEXT, time TEXT, title TEXT,
  kind TEXT, body TEXT, url TEXT, seen INTEGER);
CREATE TABLE IF NOT EXISTS fec_cand(cand_id TEXT, cycle INTEGER, name TEXT, party TEXT, receipts REAL,
  indiv REAL, pac REAL, party_c REAL, self_c REAL, transfers REAL, disb REAL, cash REAL, end_date TEXT,
  PRIMARY KEY(cand_id, cycle));
CREATE TABLE IF NOT EXISTS fec_cmte(cmte_id TEXT PRIMARY KEY, name TEXT, org TEXT, type TEXT,
  party TEXT, dsgn TEXT, cand_id TEXT);
CREATE TABLE IF NOT EXISTS fec_ccl(cmte_id TEXT, cand_id TEXT, cycle INTEGER, dsgn TEXT,
  PRIMARY KEY(cmte_id, cand_id, cycle));
CREATE TABLE IF NOT EXISTS fec_pac(cand_id TEXT, cycle INTEGER, cmte_id TEXT, kind TEXT, amount REAL,
  n INTEGER, PRIMARY KEY(cand_id, cycle, cmte_id, kind));
CREATE TABLE IF NOT EXISTS fec_bundle(conduit TEXT, recipient TEXT, cycle INTEGER, total REAL,
  n INTEGER, PRIMARY KEY(conduit, recipient, cycle));
CREATE TABLE IF NOT EXISTS watch(kind TEXT, id TEXT, label TEXT, cc TEXT, added INTEGER, snap TEXT,
  PRIMARY KEY(kind, id));
CREATE TABLE IF NOT EXISTS watch_events(n INTEGER PRIMARY KEY AUTOINCREMENT, at INTEGER, kind TEXT, id TEXT, label TEXT,
  what TEXT, detail TEXT, link TEXT, seen INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS summaries(key TEXT PRIMARY KEY, text TEXT, at INTEGER);
CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT, updated INTEGER);
"""

COUNTRIES = {   # cc: (name, chambers {code: label}, what the source gives)
    "US": ("United States", {"H": "House", "S": "Senate"}, "every recorded vote, by name"),
    "GB": ("United Kingdom", {"C": "Commons", "L": "Lords"}, "every division, by name"),
    "EU": ("European Union", {"P": "European Parliament"}, "every roll-call vote, by name"),
    "CA": ("Canada", {"C": "House of Commons"}, "every recorded division, by name"),
    "IE": ("Ireland", {"D": "Dáil", "S": "Seanad"}, "every division, by name"),
    "FR": ("France", {"A": "National Assembly"}, "every public ballot, by name"),
    "DE": ("Germany", {"B": "Bundestag"}, "roll-call (named) votes only; most Bundestag votes are by show of hands"),
    "ES": ("Spain", {"C": "Congress of Deputies"}, "every electronic vote, by name, from the sittings Archie has seen"),
    "PL": ("Poland", {"S": "Sejm"}, "every electronic vote, by name"),
    "BR": ("Brazil", {"C": "Chamber of Deputies"}, "named votes; many are symbolic (no names recorded)"),
    "CH": ("Switzerland", {"N": "National Council"}, "every electronic vote, by name"),
    "FI": ("Finland", {"E": "Eduskunta"}, "every plenary vote, by name"),
    "DK": ("Denmark", {"F": "Folketing"}, "every vote, by name"),
    "NL": ("Netherlands", {"T": "House of Representatives"}, "how each party voted (most Dutch votes are by party)"),
    "EE": ("Estonia", {"R": "Riigikogu"}, "every vote, by name"),
    "SE": ("Sweden", {"R": "Riksdag"}, "every vote, by name"),
    "NO": ("Norway", {"S": "Storting"}, "every electronic vote, by name (many are decided without a recorded vote)"),
    "IS": ("Iceland", {"A": "Althing"}, "every electronic vote, by name"),
}
COUNTRIES.update(PARL_COUNTRIES)
JOB_NAMES = {"civ_people": "lists of US lawmakers", "civ_house2": "US House votes", "civ_senate": "US Senate votes", "civ_usbills": "US bills (about 50 MB the first time)",
             "civ_exec": "executive actions", "civ_cal": "the political calendar", "civ_fec2": "campaign money from the FEC (about 150 MB the first time)",
             "civ_bundle": "bundled donations (a few FEC lookups an hour)", "civ_gb": "UK Parliament votes", "civ_gbbills": "UK bills",
             "civ_eu": "European Parliament votes", "civ_ca": "Canada", "civ_ie": "Ireland", "civ_pl2": "Poland", "civ_de": "Germany",
             "civ_br": "Brazil", "civ_ch": "Switzerland", "civ_fi": "Finland", "civ_dk": "Denmark", "civ_nl": "the Netherlands",
             "civ_ee": "Estonia", "civ_fr": "France (about 30 MB)", "civ_es": "Spain"}
JOB_NAMES.update(MORE_JOBS)
JOB_NAMES.update(EXTRA_JOBS)
JOB_NAMES.update(PARL_JOBS)
JOB_NAMES.update(LOCAL_JOBS)
STAGES = ["Introduced", "Being debated / in committee", "Out of committee, ready for a vote", "Passed one chamber",
          "Passed both chambers", "Sent for signature", "Became law"]
POSNAME = {"Y": "yes", "N": "no", "A": "abstain", "X": "didn't vote", "O": "other"}

# Groups that collect donations from individuals and pass them on to candidates ("earmarked" / "bundled").
# Matched against FEC committee names; a mix across the spectrum. Platforms (ActBlue, WinRed) are left out
# on purpose: they carry everyone's donations and aren't an interest group.
DEFAULT_CONDUITS = [
    r"^AMERICAN ISRAEL PUBLIC AFFAIRS COMMITTEE POLITICAL ACTION COMMITTEE$",
    r"^J STREET ?PAC$",
    r"^CLUB FOR GROWTH PAC$",
    r"^NORPAC$",
    r"^COUNCIL FOR A LIVABLE WORLD$",
    r"^EMILY'?S LIST$",
    r"^SENATE CONSERVATIVES FUND$",
    r"^HOUSE FREEDOM FUND$",
    r"^END CITIZENS UNITED",
    r"^SUSAN B\.? ANTHONY LIST",
    r"^NATIONAL RIFLE ASSOCIATION OF AMERICA POLITICAL VICTORY FUND$",
    r"^LEAGUE OF CONSERVATION VOTERS",
]
US_TYPES = ["hr", "s", "hjres", "sjres", "hconres", "sconres", "hres", "sres"]
US_TYPE_LABEL = {"hr": "H.R.", "s": "S.", "hjres": "H.J.Res.", "sjres": "S.J.Res.", "hconres": "H.Con.Res.",
                 "sconres": "S.Con.Res.", "hres": "H.Res.", "sres": "S.Res."}
US_STATES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
             "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
             "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
             "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
             "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
             "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
             "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
             "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
             "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
             "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia", "PR": "Puerto Rico",
             "GU": "Guam", "VI": "U.S. Virgin Islands", "AS": "American Samoa", "MP": "Northern Mariana Islands"}
FIPS_STATE = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
              "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
              "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
              "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
              "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
              "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY", "72": "PR", "66": "GU", "78": "VI",
              "60": "AS", "69": "MP"}

SUM_PROMPT = """You explain what governments are doing to a general reader.
In 2 to 4 short sentences of plain English, say what this {kind} does or decides. Rules:
- Be strictly neutral: no opinions, no praise or criticism, no guesses about motives or effects.
- Only say what the text says. If the text is thin, say only what it is about.
- If the text is not in English, translate it.
- No preamble; start with the substance.

{text}"""


def _now():
    return int(time.time())


def _today():
    return datetime.date.today()


def strip_html(s):
    s = re.sub(r"<(br|/p|/li|/div)[^>]*>", "\n", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n", s)).strip()


def _t(el, path, default=""):
    if el is None:
        return default
    x = el.find(path)
    return (x.text or "").strip() if x is not None and x.text else default


def _int(v):
    try:
        return int(str(v).strip() or 0)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0


def _num(v):
    try:
        return float(str(v).strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def slugify(x):
    x = unicodedata.normalize("NFD", (x or "").lower())
    x = "".join(ch for ch in x if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", x).strip("-")


def nice_name(n):
    """'Mika AALTOLA' -> 'Mika Aaltola'; 'Pisarello Prados, Gerardo' -> 'Gerardo Pisarello Prados'."""
    n = (n or "").strip().rstrip(".")
    if "," in n and n.count(",") == 1:
        a, b = [p.strip() for p in n.split(",")]
        if a and b:
            n = b + " " + a
    out = []
    for w in n.split():
        if len(w) > 1 and w.isupper() and not re.match(r"^[IVX]+$", w):
            w = "-".join(p[:1] + p[1:].lower() for p in w.split("-"))
        out.append(w)
    return " ".join(out)


def ms_date(v):
    """OData '/Date(1790873170270)/' -> 'YYYY-MM-DD'."""
    m = re.search(r"Date\((\d+)", str(v or ""))
    return datetime.datetime.utcfromtimestamp(int(m.group(1)) / 1000).strftime("%Y-%m-%d") if m else ""


class Civic(CivicMore, CivicExtra, CivicParl, CivicLocal):
    def __init__(self, svc, world_dir, fetch, fetch_json, FetchError, ua):
        self.svc = svc
        self.fetch = fetch
        self.fetch_json = fetch_json
        self.FetchError = FetchError
        self.ua = ua
        self.dir = os.path.join(world_dir, "civic")
        self.cache = os.path.join(self.dir, "cache")
        os.makedirs(self.cache, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(os.path.join(self.dir, "civic.db"), check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(CIVIC_SCHEMA)
        self.db.commit()
        self.more_init()
        self.extra_init()
        self.local_init()
        self.settings_path = os.path.join(self.dir, "settings.json")
        self.settings = self._load_settings()
        self._us = None          # Congress members (bioguide -> record)
        self._states = None      # state legislators
        self._sum_lock = threading.Lock()
        self.status = {}         # source -> (ok, when, note)
        self.current = None      # (job key, started) while a job runs
        try:
            for r in svc.store.q("SELECT name, ok, last, error FROM health WHERE name LIKE 'Lawmaking: %'"):
                self.status[r["name"][11:]] = (bool(r["ok"]), r["last"], r["error"] or "")
        except Exception:
            pass

    # ------------------------------------------------------------------ storage helpers
    def q(self, sql, args=(), one=False):
        with self.lock:
            rows = self.db.execute(sql, args).fetchall()
        return (rows[0] if rows else None) if one else rows

    def x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def _xn(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def many(self, sql, rows):
        with self.lock:
            self.db.executemany(sql, rows)
            self.db.commit()

    def kv(self, key, default=None):
        r = self.q("SELECT value FROM kv WHERE key=?", (key,), one=True)
        if not r:
            return default
        try:
            return json.loads(r["value"])
        except ValueError:
            return default

    def kv_set(self, key, value):
        self.x("INSERT OR REPLACE INTO kv(key, value, updated) VALUES(?,?,?)", (key, json.dumps(value), _now()))

    def _load_settings(self):
        s = {"fec_key": "", "congress_key": "", "home": {}, "conduits": DEFAULT_CONDUITS}
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                s.update(json.load(f))
        except (OSError, ValueError):
            pass
        return s

    def save_settings(self, b):
        for k in ("fec_key", "congress_key"):
            if k in b and isinstance(b[k], str):
                self.settings[k] = b[k].strip()
        if isinstance(b.get("home"), dict):
            self.settings["home"] = b["home"]
        if isinstance(b.get("openstates_key"), str):
            self.settings["openstates_key"] = b["openstates_key"].strip()
        if isinstance(b.get("lda_key"), str):
            self.settings["lda_key"] = b["lda_key"].strip()
        if isinstance(b.get("tvfy_key"), str):
            self.settings["tvfy_key"] = b["tvfy_key"].strip()
        if "senate_efd" in b:
            self.settings["senate_efd"] = bool(b["senate_efd"])
        tmp = self.settings_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=1)
        os.replace(tmp, self.settings_path)
        return {"ok": True, "fec_key": bool(self.settings.get("fec_key")), "congress_key": bool(self.settings.get("congress_key")),
                "lda_key": bool(self.settings.get("lda_key")), "senate_efd": bool(self.settings.get("senate_efd")),
                "openstates_key": bool(self.settings.get("openstates_key")), "tvfy_key": bool(self.settings.get("tvfy_key"))}

    def _ok(self, name, ok, note=""):
        self.status[name] = (bool(ok), _now(), note[:200])
        try:
            self.svc.store.health("Lawmaking: " + name, "civic", ok, 0, note[:200])
        except Exception:
            pass

    def _stop(self):
        return self.svc.stop.is_set()

    def get(self, url, timeout=40, headers=None):
        try:
            return self.fetch(url, timeout=timeout, headers=headers)
        except self.FetchError as e:
            if "certificate verify failed" not in str(e).lower():
                raise
            return self.aia_get(url, timeout, headers)   # the site left out part of its certificate chain

    def getj(self, url, timeout=40, headers=None):
        h = {"Accept": "application/json"}
        h.update(headers or {})
        try:
            return self.fetch_json(url, timeout=timeout, headers=h)
        except self.FetchError as e:
            if "certificate verify failed" not in str(e).lower():
                raise
            try:
                return json.loads(self.aia_get(url, timeout, h))
            except ValueError:
                raise self.FetchError("not JSON")

    def download(self, url, name, timeout=600, max_age=0):
        """Save a (possibly large) file into the cache, streaming it. Returns the path."""
        path = os.path.join(self.cache, name)
        if max_age and os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age:
            return path
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        tmp = path + ".part"
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
                while True:
                    if self._stop():
                        raise self.FetchError("stopping")
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    f.write(chunk)
        except self.FetchError:
            raise
        except Exception as e:
            try:
                os.remove(tmp)
            except OSError:
                pass
            raise self.FetchError(str(e)[:120])
        os.replace(tmp, path)
        return path

    # ------------------------------------------------------------------ people files
    def us_people(self):
        if self._us is None:
            d = {}
            for p in (self._json_file("us_legislators.json") or {}).get("people", []):
                d[p["bio"]] = p
            self._us = d
            self._lis = {p["lis"]: b for b, p in d.items() if p.get("lis")}
        return self._us

    def _json_file(self, name):
        for base in (os.path.join(self.cache, name), os.path.join(self.dir, name)):
            try:
                with open(base, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                continue
        return None

    def pull_us_people(self):
        """Weekly: refresh the list of members of Congress (with their FEC ids) and state legislators."""
        try:
            L = self.fetch_json("https://unitedstates.github.io/congress-legislators/legislators-current.json", timeout=60)
            out = []
            for p in L:
                t = p["terms"][-1]
                i, n = p["id"], p["name"]
                out.append({"bio": i["bioguide"], "lis": i.get("lis", ""), "fec": i.get("fec", []),
                            "name": n.get("official_full") or (n.get("first", "") + " " + n.get("last", "")).strip(),
                            "last": n.get("last", ""), "party": t.get("party", ""), "state": t["state"],
                            "district": t.get("district"), "chamber": "S" if t["type"] == "sen" else "H",
                            "start": p["terms"][0]["start"], "term_start": t["start"], "term_end": t["end"],
                            "url": t.get("url", ""), "phone": t.get("phone", ""), "class": t.get("class"),
                            "rank": t.get("state_rank", ""), "terms": len(p["terms"])})
            if len(out) > 400:
                with open(os.path.join(self.cache, "us_legislators.json"), "w", encoding="utf-8") as f:
                    json.dump({"source": "unitedstates/congress-legislators", "people": out}, f)
                self._us = None
            self._ok("Congress members", True)
        except (self.FetchError, KeyError, ValueError, TypeError) as e:
            self._ok("Congress members", False, str(e))
        try:   # state legislators (Open States publishes a CSV per state)
            if self._stop():
                return
            states = {}
            for st in US_STATES:
                txt = self.get("https://data.openstates.org/people/current/%s.csv" % st.lower(), timeout=40)
                rows = list(csv.DictReader(io.StringIO(txt)))
                L = [{"n": r.get("name", ""), "p": r.get("current_party", ""), "c": r.get("current_chamber", ""),
                      "d": r.get("current_district", ""), "e": r.get("email", ""),
                      "ph": r.get("capitol_voice") or r.get("district_voice") or "",
                      "u": (r.get("links") or "").split(";")[0].strip()} for r in rows if r.get("name")]
                if L:
                    states[st] = L
                time.sleep(0.3)
            if len(states) > 40:
                with open(os.path.join(self.cache, "state_legislators.json"), "w", encoding="utf-8") as f:
                    json.dump({"built": _today().isoformat(), "source": "Open States (CC0)", "states": states}, f)
                self._states = None
            self._ok("State legislators", True)
        except (self.FetchError, ValueError) as e:
            self._ok("State legislators", True, "using the copy built into Archie (Open States' download said %s)" % e)

    # ------------------------------------------------------------------ saving votes
    def save_vote(self, v, members=None):
        """v: dict with id, cc, chamber, date, title, ... ; members: [(key, name, party, pos, area)]"""
        by_party = v.get("by_party")
        if members:
            bp = {}
            for m in members:
                d = bp.setdefault(m[2] or "?", {"Y": 0, "N": 0, "A": 0, "X": 0, "O": 0})
                d[m[3]] = d.get(m[3], 0) + 1
            by_party = by_party or bp
            if not any(v.get(k) for k in ("yes", "no", "abstain")):
                v["yes"] = sum(1 for m in members if m[3] == "Y")
                v["no"] = sum(1 for m in members if m[3] == "N")
                v["abstain"] = sum(1 for m in members if m[3] == "A")
                v["absent"] = sum(1 for m in members if m[3] == "X")
        with self.lock:
            self.db.execute("""INSERT OR REPLACE INTO votes(id, cc, chamber, date, title, question, result, yes, no, abstain,
                absent, bill, url, by_party, detail, kind, src, extra) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (v["id"], v["cc"], v.get("chamber", ""), v.get("date", ""), (v.get("title") or "")[:600],
                             (v.get("question") or "")[:400], v.get("result", ""), _int(v.get("yes")), _int(v.get("no")),
                             _int(v.get("abstain")), _int(v.get("absent")), v.get("bill", ""), v.get("url", ""),
                             json.dumps(by_party or {}), 1 if members is not None else _int(v.get("detail")),
                             v.get("kind", ""), v.get("src", ""), json.dumps(v.get("extra") or {})))
            if members is not None:
                self.db.execute("DELETE FROM mvotes WHERE vote_id=?", (v["id"],))
                self.db.executemany("INSERT OR REPLACE INTO mvotes(vote_id, member, name, party, pos) VALUES(?,?,?,?,?)",
                                    [(v["id"], m[0], m[1], m[2], m[3]) for m in members])
                self.db.executemany("""INSERT INTO members(key, cc, chamber, name, party, area, extra, seen) VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(key) DO UPDATE SET name=excluded.name, party=CASE WHEN excluded.seen >= members.seen THEN excluded.party ELSE members.party END,
                    area=CASE WHEN excluded.area != '' THEN excluded.area ELSE members.area END, chamber=excluded.chamber,
                    seen=MAX(members.seen, excluded.seen)""",
                                    [(m[0], v["cc"], v.get("chamber", ""), m[1], m[2] or "", (m[4] if len(m) > 4 else "") or "", "{}",
                                      v.get("date", "")) for m in members])
            self.db.commit()

    def have(self, vid):
        return self.q("SELECT detail FROM votes WHERE id=?", (vid,), one=True)

    def need_detail(self, cc, limit):
        return [r["id"] for r in self.q("SELECT id FROM votes WHERE cc=? AND detail=0 ORDER BY date DESC LIMIT ?", (cc, limit))]

    # ------------------------------------------------------------------ jobs
    def jobs(self):
        return [
            ("civ_people", 604800, self.pull_us_people),
            ("civ_house2", 10800, self.pull_us_house),
            ("civ_senate", 10800, self.pull_us_senate),
            ("civ_exec", 21600, self.pull_exec),
            ("civ_elec", 900, self.pull_elections),
            ("civ_cal", 21600, self.pull_calendar),
            ("civ_cmte", 604800, self.pull_committees),
            ("civ_scotus4", 21600, self.pull_scotus),
            ("civ_gb", 21600, self.pull_gb),
            ("civ_gbbills", 43200, self.pull_gb_bills),
            ("civ_eu", 21600, self.pull_eu),
            ("civ_ca", 21600, self.pull_ca),
            ("civ_ie", 21600, self.pull_ie),
            ("civ_pl2", 21600, self.pull_pl),
            ("civ_de", 43200, self.pull_de),
            ("civ_br", 21600, self.pull_br),
            ("civ_ch", 43200, self.pull_ch),
            ("civ_fi", 43200, self.pull_fi),
            ("civ_dk", 21600, self.pull_dk),
            ("civ_nl", 21600, self.pull_nl),
            ("civ_ee", 43200, self.pull_ee),
            ("civ_fr", 604800, self.pull_fr),
            ("civ_es", 21600, self.pull_es),
            ("civ_se", 21600, self.pull_se),
            ("civ_no", 21600, self.pull_no),
            ("civ_is", 43200, self.pull_is),
            ("civ_os", 21600, self.pull_openstates),
        ] + self.parl_jobs() + self.local_jobs() + [
            ("civ_watch", 1800, self.check_watch),
            ("civ_trades", 10800, self.pull_trades),
            ("civ_usbills", 21600, self.pull_us_bills),
            ("civ_fec2", 604800, self.pull_fec),
            ("civ_bundle", 3600, self.pull_bundles),
            ("civ_lda", 3600, self.pull_lda),
            ("civ_judges2", 7 * 86400, self.pull_judges),
        ]

    # ================================================================== UNITED STATES
    @staticmethod
    def congress_of(year):
        return (year - 1789) // 2 + 1

    @staticmethod
    def us_bill_id(congress, text):
        """'H R 498' / 'H.R. 9340' / 'S.J.Res. 4' -> 'US-119-hr498'"""
        m = re.match(r"^\s*([HS])\s*\.?\s*(J\s*\.?\s*RES|CON\s*\.?\s*RES|RES|R)?\s*\.?\s*(\d+)\s*$", (text or "").upper())
        if not m:
            return ""
        ch, kind, n = m.group(1), re.sub(r"[\s.]", "", m.group(2) or ""), m.group(3)
        t = {("H", "R"): "hr", ("S", ""): "s", ("H", "JRES"): "hjres", ("S", "JRES"): "sjres", ("H", "CONRES"): "hconres",
             ("S", "CONRES"): "sconres", ("H", "RES"): "hres", ("S", "RES"): "sres"}.get((ch, kind))
        return "US-%d-%s%s" % (congress, t, n) if t else ""

    def pull_us_house(self):
        today = _today()
        years = [today.year - 1, today.year] if today.year % 2 == 0 else [today.year]
        people = self.us_people()
        got = 0
        try:
            for y in reversed(years):
                idx = self.get("https://clerk.house.gov/evs/%d/index.asp" % y, timeout=40)
                nums = [int(n) for n in re.findall(r"rollnumber=(\d+)", idx)]
                top = max(nums) if nums else 0
                have = {r["id"] for r in self.q("SELECT id FROM votes WHERE id LIKE ?", ("US-H-%d-%%" % y,))}
                todo = [n for n in range(top, 0, -1) if "US-H-%d-%d" % (y, n) not in have][:200 - got]
                for n in todo:
                    if self._stop():
                        return
                    try:
                        self._house_roll(y, n, people)
                        got += 1
                    except (self.FetchError, ET.ParseError) as e:
                        if "404" in str(e):
                            continue
                        raise
                    time.sleep(0.25)
                if got >= 200:
                    break
            self._ok("US House votes", True, "%d new" % got)
        except (self.FetchError, ET.ParseError) as e:
            # the House Clerk's site turns away some non-browser requests; Voteview (UCLA) republishes every roll call
            try:
                n = self._house_voteview(people)
                self._ok("US House votes", True, "%d new (via Voteview; the Clerk's site said %s)" % (n, e))
            except (self.FetchError, ValueError, KeyError, IndexError) as e2:
                self._ok("US House votes", False, "Clerk: %s; Voteview: %s" % (e, e2))

    def _house_voteview(self, people):
        congress = self.congress_of(_today().year)
        base = "https://voteview.com/static/data/out/"
        rc = list(csv.DictReader(io.StringIO(self.get(base + "rollcalls/H%d_rollcalls.csv" % congress, timeout=120))))
        have = {r["id"] for r in self.q("SELECT id FROM votes WHERE id LIKE 'US-H-%'")}
        todo = {}
        for r in rc:
            vid = "US-H-%s-%s" % (r["date"][:4], r["clerk_rollnumber"])
            if vid not in have:
                todo[r["rollnumber"]] = (vid, r)
        if not todo:
            return 0
        mem = {}
        for m in csv.DictReader(io.StringIO(self.get(base + "members/H%d_members.csv" % congress, timeout=120))):
            mem[m["icpsr"]] = m
        PARTY = {"100": "Democratic", "200": "Republican", "328": "Independent"}
        votes = {}
        for line in self.get(base + "votes/H%d_votes.csv" % congress, timeout=300).splitlines()[1:]:
            c = line.split(",")
            if len(c) < 5 or c[2] not in todo:
                continue
            code = _int(c[4])
            if code == 0:
                continue
            m = mem.get(c[3]) or {}
            bio = m.get("bioguide_id") or ""
            p = people.get(bio) or {}
            pos = "Y" if code in (1, 2, 3) else "N" if code in (4, 5, 6) else "A" if code == 7 else "X"
            votes.setdefault(c[2], []).append(("US:" + (bio or "icpsr-" + c[3]), p.get("name") or nice_name(m.get("bioname", "")),
                                               PARTY.get(m.get("party_code"), p.get("party", "")), pos,
                                               (m.get("state_abbrev") or "") + ("-%s" % m["district_code"] if m.get("district_code") not in (None, "", "0") else "")))
        n = 0
        for rn, (vid, r) in todo.items():
            if self._stop():
                break
            M = votes.get(rn)
            if not M:
                continue
            y = r["date"][:4]
            self.save_vote({"id": vid, "cc": "US", "chamber": "H", "date": r["date"], "title": r.get("vote_desc") or r.get("dtl_desc") or r.get("bill_number") or "",
                            "question": r.get("vote_question") or "", "result": r.get("vote_result") or "",
                            "bill": self.us_bill_id(congress, r.get("bill_number") or ""),
                            "url": "https://clerk.house.gov/Votes/%s%s" % (y, r["clerk_rollnumber"]), "kind": r.get("majority_requirement") or "",
                            "extra": {"ref": r.get("bill_number"), "roll": r["clerk_rollnumber"], "needs": r.get("majority_requirement") or "", "via": "Voteview"}}, M)
            n += 1
        return n

    def _house_roll(self, y, n, people):
        root = ET.fromstring(self.get("https://clerk.house.gov/evs/%d/roll%03d.xml" % (y, n), timeout=40).encode("utf-8"))
        md = root.find("vote-metadata")
        congress = _int(_t(md, "congress")) or self.congress_of(y)
        try:
            date = datetime.datetime.strptime(_t(md, "action-date"), "%d-%b-%Y").strftime("%Y-%m-%d")
        except ValueError:
            date = "%d-01-01" % y
        bp = {}
        for tp in md.findall("vote-totals/totals-by-party"):
            bp[_t(tp, "party")] = {"Y": _int(_t(tp, "yea-total")), "N": _int(_t(tp, "nay-total")),
                                   "A": _int(_t(tp, "present-total")), "X": _int(_t(tp, "not-voting-total"))}
        tv = md.find("vote-totals/totals-by-vote")
        P = {"D": "Democratic", "R": "Republican", "I": "Independent"}
        members = []
        for rv in root.findall("vote-data/recorded-vote"):
            lg = rv.find("legislator")
            if lg is None:
                continue
            bio = lg.get("name-id") or ""
            vt = (_t(rv, "vote") or "").lower()
            pos = "Y" if vt in ("yea", "aye") else "N" if vt in ("nay", "no") else "A" if vt == "present" else "X" if "not voting" in vt else "O"
            p = people.get(bio) or {}
            members.append(("US:" + bio, p.get("name") or (lg.text or "").strip(), P.get(lg.get("party"), lg.get("party") or ""), pos,
                            lg.get("state", "") + ("-%s" % p["district"] if p.get("district") not in (None, "") else "")))
        legis = _t(md, "legis-num")
        self.save_vote({"id": "US-H-%d-%d" % (y, n), "cc": "US", "chamber": "H", "date": date,
                        "title": _t(md, "vote-desc") or legis, "question": _t(md, "vote-question"), "result": _t(md, "vote-result"),
                        "yes": _int(_t(tv, "yea-total")), "no": _int(_t(tv, "nay-total")), "abstain": _int(_t(tv, "present-total")),
                        "absent": _int(_t(tv, "not-voting-total")), "bill": self.us_bill_id(congress, legis),
                        "url": "https://clerk.house.gov/Votes/%d%d" % (y, n), "by_party": bp, "kind": _t(md, "vote-type"),
                        "extra": {"ref": legis, "roll": n}}, members)

    def pull_us_senate(self):
        today = _today()
        congress = self.congress_of(today.year)
        sessions = [1, 2] if today.year % 2 == 0 else [1]
        self.us_people()
        got = 0
        try:
            for s in reversed(sessions):
                menu = ET.fromstring(self.get("https://www.senate.gov/legislative/LIS/roll_call_lists/vote_menu_%d_%d.xml" % (congress, s), timeout=40).encode("utf-8"))
                nums = [_int(_t(v, "vote_number")) for v in menu.findall("votes/vote")]
                have = {r["id"] for r in self.q("SELECT id FROM votes WHERE id LIKE ?", ("US-S-%d-%d-%%" % (congress, s),))}
                for n in sorted(nums, reverse=True):
                    if got >= 200 or self._stop():
                        break
                    if "US-S-%d-%d-%d" % (congress, s, n) in have:
                        continue
                    try:
                        self._senate_roll(congress, s, n)
                        got += 1
                    except (self.FetchError, ET.ParseError):
                        continue
                    time.sleep(0.3)
            self._ok("US Senate votes", True, "%d new" % got)
        except (self.FetchError, ET.ParseError) as e:
            self._ok("US Senate votes", False, str(e))

    def _senate_roll(self, congress, s, n):
        root = ET.fromstring(self.get("https://www.senate.gov/legislative/LIS/roll_call_votes/vote%d%d/vote_%d_%d_%05d.xml" % (congress, s, congress, s, n), timeout=40).encode("utf-8"))
        m = re.match(r"(\w+) (\d+), (\d{4})", _t(root, "vote_date"))
        try:
            date = datetime.datetime.strptime(" ".join(m.groups()), "%B %d %Y").strftime("%Y-%m-%d") if m else ""
        except ValueError:
            date = ""
        P = {"D": "Democratic", "R": "Republican", "I": "Independent"}
        members = []
        for mm in root.findall("members/member"):
            lis = _t(mm, "lis_member_id")
            bio = self._lis.get(lis, "") if hasattr(self, "_lis") else ""
            vc = _t(mm, "vote_cast").lower()
            pos = "Y" if vc in ("yea", "guilty") else "N" if vc in ("nay", "not guilty") else "A" if vc == "present" else "X" if "not voting" in vc else "O"
            name = (self._us.get(bio) or {}).get("name") or (_t(mm, "first_name") + " " + _t(mm, "last_name")).strip()
            members.append(("US:" + (bio or "lis-" + lis), name, P.get(_t(mm, "party"), _t(mm, "party")), pos, _t(mm, "state")))
        doc = root.find("document")
        dname = _t(doc, "document_name")
        self.save_vote({"id": "US-S-%d-%d-%d" % (congress, s, n), "cc": "US", "chamber": "S", "date": date,
                        "title": _t(root, "vote_title") or _t(root, "vote_document_text"), "question": _t(root, "question") or _t(root, "vote_question_text"),
                        "result": _t(root, "vote_result"), "yes": _int(_t(root, "count/yeas")), "no": _int(_t(root, "count/nays")),
                        "abstain": _int(_t(root, "count/present")), "absent": _int(_t(root, "count/absent")),
                        "bill": self.us_bill_id(congress, dname),
                        "url": "https://www.senate.gov/legislative/LIS/roll_call_votes/vote%d%d/vote_%d_%d_%05d.htm" % (congress, s, congress, s, n),
                        "kind": _t(root, "majority_requirement"), "extra": {"ref": dname, "needs": _t(root, "majority_requirement")}}, members)

    # ---- bills (GovInfo BILLSTATUS)
    def pull_us_bills(self):
        congress = self.congress_of(_today().year)
        base = "https://www.govinfo.gov/bulkdata/BILLSTATUS/%d/" % congress
        try:
            # first time for each type: the whole zip (all bills at once)
            for t in US_TYPES:
                key = "uszip2_%d_%s" % (congress, t)
                if self.kv(key):
                    continue
                self._ok("US bills", True, "downloading the %s file" % US_TYPE_LABEL[t])
                path = self.download(base + "%s/BILLSTATUS-%d-%s.zip" % (t, congress, t), "BILLSTATUS-%d-%s.zip" % (congress, t), timeout=900, max_age=7 * 86400)
                n = 0
                with zipfile.ZipFile(path) as z:
                    names = [x for x in z.namelist() if x.endswith(".xml")]
                    for name in names:
                        if self._stop():
                            with self.lock:
                                self.db.commit()
                            return
                        try:
                            self._us_bill(z.read(name), "", commit=False)
                            n += 1
                        except (ET.ParseError, ValueError, KeyError):
                            pass
                        if n % 400 == 0:
                            with self.lock:
                                self.db.commit()
                            self._ok("US bills", True, "loading %s bills: %d of %d" % (US_TYPE_LABEL[t], n, len(names)))
                with self.lock:
                    self.db.commit()
                try:
                    os.remove(path)
                except OSError:
                    pass
                self.kv_set(key, {"at": _now(), "n": n})
                self.kv_set("ussitemap_%d" % congress, datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"))
                self._ok("US bills", True, "loaded %d %s" % (n, US_TYPE_LABEL[t]))
                time.sleep(2)
            # after that: only bills that changed, from the sitemaps
            todo = []
            for t in US_TYPES:
                sm = self.get("https://www.govinfo.gov/sitemap/bulkdata/BILLSTATUS/%d%s/sitemap.xml" % (congress, t), timeout=90)
                for loc, mod in re.findall(r"<loc>([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>", sm):
                    m = re.search(r"BILLSTATUS-(\d+)([a-z]+)(\d+)\.xml", loc)
                    if not m:
                        continue
                    bid = "US-%s-%s%s" % m.groups()
                    todo.append((mod, bid, loc))
            stored = {r["id"]: r["srcmod"] or "" for r in self.q("SELECT id, srcmod FROM bills WHERE cc='US'")}
            last = self.kv("ussitemap_%d" % congress, "") or ""
            changed = [x for x in todo if x[0] > max(stored.get(x[1]) or "", last)]
            changed.sort(reverse=True)
            n = 0
            for mod, bid, loc in changed[:300]:
                if self._stop():
                    return
                try:
                    self._us_bill(self.fetch(loc, timeout=60, raw=True)[0], mod)
                    n += 1
                except (self.FetchError, ET.ParseError, ValueError, KeyError):
                    continue
                time.sleep(0.2)
            if len(changed) <= 300 and todo:
                self.kv_set("ussitemap_%d" % congress, max(x[0] for x in todo))
            self._ok("US bills", True, "%d updated, %d waiting" % (n, max(0, len(changed) - 300)))
        except (self.FetchError, zipfile.BadZipFile, OSError) as e:
            self._ok("US bills", False, str(e))

    def _us_bill(self, data, srcmod, commit=True):
        root = ET.fromstring(data)
        b = root.find("bill")
        if b is None:
            return
        t = _t(b, "type").lower() or _t(b, "billType").lower()
        num, congress = _t(b, "number") or _t(b, "billNumber"), _int(_t(b, "congress"))
        if not t or not num:
            return
        bid = "US-%d-%s%s" % (congress, t, num)
        sp = b.find("sponsors/item")
        acts = []
        votes = []
        for a in b.findall("actions/item"):
            acts.append((_t(a, "actionDate"), _t(a, "text"), _t(a, "type"), _t(a, "sourceSystem/name")))
            for rv in a.findall("recordedVotes/recordedVote"):
                ch, roll, dt = _t(rv, "chamber"), _int(_t(rv, "rollNumber")), _t(rv, "date")
                if ch.startswith("House") and dt:
                    votes.append("US-H-%s-%d" % (dt[:4], roll))
                elif ch.startswith("Senate"):
                    yr = _int(dt[:4]) if dt else 0
                    votes.append("US-S-%d-%d-%d" % (_int(_t(rv, "congress")) or congress, 1 if yr % 2 == 1 else 2, roll))
        acts.sort(key=lambda a: a[0])
        low = [a[1].lower() for a in acts]
        laws = [_t(l, "number") for l in b.findall("laws/item")]
        simple = t in ("hres", "sres")
        def has(*keys):
            return any(any(k in x for k in keys) for x in low)
        house = has("passed/agreed to in house", "passed house")
        senate = has("passed/agreed to in senate", "passed senate")
        stage = 0
        if low:
            stage = 1 if has("referred to", "committee") else 0
        if has("reported by", "ordered to be reported", "placed on the union calendar", "placed on the house calendar",
               "placed on senate legislative calendar", "discharged"):
            stage = max(stage, 2)
        if house or senate:
            stage = 6 if simple else max(stage, 3)
        if house and senate:
            stage = max(stage, 4)
        if has("presented to president"):
            stage = max(stage, 5)
        if laws or has("became public law", "became private law"):
            stage = 6
        stage_text = STAGES[stage]
        if simple and stage == 6:
            stage_text = "Adopted (resolutions don't need a signature)"
        if has("vetoed by president") and not laws:
            stage, stage_text = -1, "Vetoed by the President" + (" (veto overridden)" if has("passed over veto", "override") else "")
        if has("failed of passage", "not agreed to in house", "not agreed to in senate") and stage < 3:
            stage, stage_text = -1, "Failed a floor vote"
        sums = sorted(b.findall("summaries/summary"), key=lambda s: (_t(s, "actionDate"), _t(s, "updateDate")))
        summary = strip_html(_t(sums[-1], "text")) if sums else ""
        la = b.find("latestAction")
        extra = {"actions": [list(a[:3]) for a in (acts[:3] + acts[-37:] if len(acts) > 40 else acts)],
                 "cosponsors": len(b.findall("cosponsors/item")), "votes": sorted(set(votes)),
                 "summary_version": _t(sums[-1], "actionDesc") if sums else "", "laws": laws,
                 "committees": sorted({_t(c, "name") for c in b.findall("committees/item") if _t(c, "name")})}
        cm = []
        for c in b.findall("committees/item"):
            code = _t(c, "systemCode").upper()
            if len(code) >= 4:
                dates = sorted(_t(a, "date")[:10] for a in c.findall("activities/item") if _t(a, "date"))
                cm.append((code[:4], "", dates[0] if dates else ""))
                for sc in c.findall("subcommittees/item"):
                    sco = _t(sc, "systemCode").upper()
                    if len(sco) >= 6 and sco[4:6] != "00":
                        sd = sorted(_t(a, "date")[:10] for a in sc.findall("activities/item") if _t(a, "date"))
                        cm.append((code[:4], sco[4:6], sd[0] if sd else ""))
        (self.x if commit else self._xn)("""INSERT OR REPLACE INTO bills(id, cc, num, title, sponsor, sponsor_key, party, introduced, updated, stage, stage_text,
            latest_date, latest_text, enacted, url, summary, subject, chamber, extra, srcmod) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (bid, "US", "%s %s" % (US_TYPE_LABEL.get(t, t.upper()), num), _t(b, "title"),
                re.sub(r"\s*\[.*\]$", "", _t(sp, "fullName")), "US:" + _t(sp, "bioguideId") if sp is not None else "",
                _t(sp, "party"), _t(b, "introducedDate"), _t(b, "updateDate"), stage, stage_text,
                _t(la, "actionDate"), _t(la, "text"), ("Public Law " + laws[0]) if laws else "",
                _t(b, "legislationUrl") or "https://www.congress.gov/bill/%dth-congress/%s/%s" % (congress, t, num),
                summary, _t(b, "policyArea/name"), _t(b, "originChamber"), json.dumps(extra), srcmod or _t(b, "updateDate")))
        self.save_bill_cmte(bid, cm)
        if commit:
            with self.lock:
                self.db.commit()

    # ---- executive actions (Federal Register)
    def pull_exec(self):
        F = "".join("&fields[]=" + f for f in ("title", "type", "subtype", "abstract", "document_number", "html_url",
                                                 "publication_date", "signing_date", "executive_order_number", "agencies", "significant"))
        base = "https://www.federalregister.gov/api/v1/documents.json?order=newest"
        n = 0
        try:
            for cond, per, kind in (("&conditions[type][]=PRESDOCU", 100, None), ("&conditions[type][]=RULE&conditions[significant]=1", 60, "Major final rule"),
                                    ("&conditions[type][]=PRORULE&conditions[significant]=1", 40, "Major proposed rule")):
                j = self.getj(base + "&per_page=%d" % per + cond + F, timeout=60)
                rows = []
                for d in j.get("results") or []:
                    ag = ", ".join(a.get("name") or a.get("raw_name") or "" for a in (d.get("agencies") or []))
                    rows.append((d["document_number"], kind or d.get("subtype") or "Presidential document", d.get("title") or "",
                                 d.get("publication_date") or "", d.get("signing_date") or "", d.get("executive_order_number") or "",
                                 d.get("html_url") or "", d.get("abstract") or "", ag))
                self.many("INSERT OR REPLACE INTO execs(id, kind, title, date, signed, number, url, abstract, agency) VALUES(?,?,?,?,?,?,?,?,?)", rows)
                n += len(rows)
            self._ok("Executive actions", True, "%d documents" % n)
        except (self.FetchError, KeyError) as e:
            self._ok("Executive actions", False, str(e))

    # ---- calendar
    def pull_calendar(self):
        today = _today()
        rows = []
        try:
            x = ET.fromstring(self.get("https://www.senate.gov/general/committee_schedules/hearings.xml", timeout=40).encode("utf-8"))
            for m in x.findall("meeting"):
                d = _t(m, "date_iso_8601")
                if not d or d < today.isoformat():
                    continue
                rows.append(("US-SH-" + _t(m, "identifier"), "US", d, _t(m, "time"), _t(m, "matter") or "(hearing)", "Senate committee",
                             "Senate " + _t(m, "committee") + (" · " + _t(m, "room") if _t(m, "room") else ""),
                             "https://www.senate.gov/committees/hearings_meetings.htm"))
            self._ok("US Senate hearings", True)
        except (self.FetchError, ET.ParseError) as e:
            self._ok("US Senate hearings", False, str(e))
        try:
            page = self.get("https://docs.house.gov/floor/", timeout=40)
            wk = re.search(r"Week of ([A-Z][a-z]{2})\.? (\d+), (\d{4})", page)
            if wk:
                try:
                    start = datetime.datetime.strptime("%s %s %s" % wk.groups(), "%b %d %Y").date()
                except ValueError:
                    start = today
                if start + datetime.timedelta(days=6) >= today:
                    for num, txt in re.findall(r'class="legisNum"[^>]*>\s*([^<]+?)\s*</td>\s*<td[^>]*class="floorText"[^>]*>\s*([^<]+?)\s*</td>', page)[:40]:
                        rows.append(("US-HF-%s-%s" % (start.isoformat(), slugify(num)), "US", start.isoformat(), "this week",
                                     num.strip() + " — " + html.unescape(txt.strip()), "House floor", "US House: up for a vote this week",
                                     "https://docs.house.gov/floor/"))
            self._ok("US House floor schedule", True)
        except self.FetchError as e:
            self._ok("US House floor schedule", False, str(e))
        try:
            end = today + datetime.timedelta(days=21)
            ev = self.getj("https://whatson-api.parliament.uk/calendar/events/list.json?queryParameters.startDate=%s&queryParameters.endDate=%s" % (today.isoformat(), end.isoformat()), timeout=60)
            for e in ev or []:
                cat, typ = e.get("Category") or "", e.get("Type") or ""
                if "Private" in cat:
                    continue
                cm = e.get("Committee") or {}
                inq = (cm.get("Inquiries") or [{}])[0].get("Description") if cm.get("Inquiries") else ""
                title = e.get("Description") or e.get("BillName") or inq or cm.get("Description") or cat
                if not title:
                    continue
                body = "UK " + (e.get("House") or "") + ((" · " + cm["Description"]) if cm.get("Description") else "")
                rows.append(("GB-%s" % e.get("Id"), "GB", (e.get("StartDate") or "")[:10], e.get("StartTime") or "",
                             strip_html(title)[:300], typ or cat, body, "https://whatson.parliament.uk/"))
            self._ok("UK Parliament calendar", True)
        except (self.FetchError, AttributeError, TypeError) as e:
            self._ok("UK Parliament calendar", False, str(e))
        if rows:
            self.x("DELETE FROM cal WHERE date < ?", ((today - datetime.timedelta(days=1)).isoformat(),))
            self.many("INSERT OR REPLACE INTO cal(id, cc, date, time, title, kind, body, url, seen) VALUES(?,?,?,?,?,?,?,?,?)",
                      [r + (_now(),) for r in rows])

    # ---- campaign money (FEC bulk files)
    def _fec_cycles(self):
        y = _today().year
        cur = y if y % 2 == 0 else y + 1
        return [cur, cur - 2, cur - 4, cur - 6]   # six years back covers every sitting senator's last race

    def _member_fec_ids(self):
        ids = set()
        for p in self.us_people().values():
            ids.update(p.get("fec") or [])
        return ids

    def pull_fec(self):
        """Weekly: FEC bulk files for every federal candidate (Congress and President), so anyone who has run
        (a cabinet member who used to be in Congress, a president) has their campaign money too."""
        class _All:
            def __contains__(self, x):
                return bool(x)
        ids = _All()
        for i, cyc in enumerate(self._fec_cycles()):
            if self._stop():
                return
            if self.kv("fec2_done_%d" % cyc) and (_now() - (self.kv("fec2_done_%d" % cyc) or 0)) < (6 if i == 0 else 30) * 86400:
                continue           # older cycles barely change: monthly is plenty
            yy = "%02d" % (cyc % 100)
            base = "https://www.fec.gov/files/bulk-downloads/%d/" % cyc
            try:
                # all candidates: totals by source
                p = self.download(base + "weball%s.zip" % yy, "weball%s.zip" % yy, max_age=5 * 86400)
                rows = []
                with zipfile.ZipFile(p) as z:
                    with z.open(z.namelist()[0]) as f:
                        for line in io.TextIOWrapper(f, encoding="latin-1"):
                            c = line.rstrip("\n").split("|")
                            if len(c) < 28 or c[0] not in ids or _num(c[5]) <= 0:
                                continue
                            rows.append((c[0], cyc, c[1], c[4], _num(c[5]), _num(c[17]), _num(c[25]), _num(c[26]),
                                         _num(c[11]) + _num(c[12]), _num(c[6]), _num(c[7]), _num(c[10]), c[27]))
                self.x("DELETE FROM fec_cand WHERE cycle=?", (cyc,))
                self.many("INSERT OR REPLACE INTO fec_cand VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
                # committees (names of the PACs that give)
                p = self.download(base + "cm%s.zip" % yy, "cm%s.zip" % yy, max_age=5 * 86400)
                rows = []
                with zipfile.ZipFile(p) as z:
                    with z.open(z.namelist()[0]) as f:
                        for line in io.TextIOWrapper(f, encoding="latin-1"):
                            c = line.rstrip("\n").split("|")
                            if len(c) >= 15:
                                rows.append((c[0], c[1], c[13], c[9], c[10], c[8], c[14]))
                self.many("INSERT OR REPLACE INTO fec_cmte VALUES(?,?,?,?,?,?,?)", rows)
                # which committees belong to which candidate
                p = self.download(base + "ccl%s.zip" % yy, "ccl%s.zip" % yy, max_age=5 * 86400)
                rows = []
                with zipfile.ZipFile(p) as z:
                    with z.open(z.namelist()[0]) as f:
                        for line in io.TextIOWrapper(f, encoding="latin-1"):
                            c = line.rstrip("\n").split("|")
                            if len(c) >= 6 and c[0] in ids:
                                rows.append((c[3], c[0], cyc, c[5]))
                self.x("DELETE FROM fec_ccl WHERE cycle=?", (cyc,))
                self.many("INSERT OR REPLACE INTO fec_ccl VALUES(?,?,?,?)", rows)
                if self._stop():
                    return
                # money from PACs and other committees to candidates, and outside spending for/against them
                self._ok("Campaign money (FEC)", True, "downloading %d-%d files" % (cyc - 1, cyc))
                p = self.download(base + "pas2%s.zip" % yy, "pas2%s.zip" % yy, timeout=1800, max_age=5 * 86400)
                agg = {}
                KIND = {"24K": "direct", "24Z": "direct", "24R": "direct", "24P": "direct", "24C": "party", "24F": "for",
                        "24E": "for", "24N": "against", "24A": "against", "24H": "direct"}
                with zipfile.ZipFile(p) as z:
                    with z.open(z.namelist()[0]) as f:
                        for line in io.TextIOWrapper(f, encoding="latin-1"):
                            c = line.rstrip("\n").split("|")
                            if len(c) < 17 or c[16] not in ids:
                                continue
                            k = KIND.get(c[5])
                            if not k or c[19:20] == ["X"]:
                                continue
                            key = (c[16], c[0], k)
                            a = agg.setdefault(key, [0.0, 0])
                            a[0] += _num(c[14])
                            a[1] += 1
                self.x("DELETE FROM fec_pac WHERE cycle=?", (cyc,))
                self.many("INSERT OR REPLACE INTO fec_pac VALUES(?,?,?,?,?,?)",
                          [(k[0], cyc, k[1], k[2], round(v[0], 2), v[1]) for k, v in agg.items()])
                for name in ("weball%s.zip", "cm%s.zip", "ccl%s.zip", "pas2%s.zip"):
                    try:
                        os.remove(os.path.join(self.cache, name % yy))
                    except OSError:
                        pass
                self.kv_set("fec2_done_%d" % cyc, _now())
                self._ok("Campaign money (FEC)", True, "cycle %d" % cyc)
            except (self.FetchError, zipfile.BadZipFile, OSError, IndexError) as e:
                self._ok("Campaign money (FEC)", False, "cycle %d: %s" % (cyc, e))
                return

    def pull_bundles(self):
        """Hourly, a few calls at a time: money that groups collected from their members and passed on (FEC API)."""
        key = self.settings.get("fec_key") or "DEMO_KEY"
        budget = 40 if key != "DEMO_KEY" else 4
        pats = [re.compile(p, re.I) for p in (self.settings.get("conduits") or DEFAULT_CONDUITS)]
        if not self.q("SELECT 1 FROM fec_cmte LIMIT 1", one=True):
            return
        conduits = [r["cmte_id"] for r in self.q("SELECT cmte_id, name FROM fec_cmte") if any(p.search(r["name"] or "") for p in pats)]
        state = self.kv("bundle_state", {}) or {}
        calls = 0
        for cyc in self._fec_cycles()[:2]:
            for cid in conduits:
                st = state.get("%s_%d" % (cid, cyc)) or {"page": 1, "done": 0}
                if st["done"] and _now() - st["done"] < (7 if cyc == self._fec_cycles()[0] else 60) * 86400:
                    continue
                if st["done"]:
                    st = {"page": 1, "done": 0}
                while calls < budget and not self._stop():
                    try:
                        j = self.getj("https://api.open.fec.gov/v1/schedules/schedule_b/by_recipient_id/?committee_id=%s&cycle=%d&per_page=100&page=%d&api_key=%s"
                                      % (cid, cyc, st["page"], key), timeout=60)
                    except self.FetchError as e:
                        state["%s_%d" % (cid, cyc)] = st
                        self.kv_set("bundle_state", state)
                        self._ok("Bundled donations (FEC API)", "429" in str(e) or "403" in str(e), "paused: " + str(e))
                        return
                    calls += 1
                    rows = [(cid, r.get("recipient_id") or "", cyc, _num(r.get("total")), _int(r.get("count"))) for r in j.get("results") or [] if r.get("recipient_id")]
                    if st["page"] == 1:
                        self.x("DELETE FROM fec_bundle WHERE conduit=? AND cycle=?", (cid, cyc))
                    self.many("INSERT OR REPLACE INTO fec_bundle VALUES(?,?,?,?,?)", rows)
                    pages = _int((j.get("pagination") or {}).get("pages"))
                    if st["page"] >= pages or not rows:
                        st = {"page": 1, "done": _now()}
                        break
                    st["page"] += 1
                state["%s_%d" % (cid, cyc)] = st
                if calls >= budget:
                    self.kv_set("bundle_state", state)
                    self._ok("Bundled donations (FEC API)", True, "working through it" + ("" if key != "DEMO_KEY" else " (free demo key: a few calls an hour)"))
                    return
        self.kv_set("bundle_state", state)
        self._ok("Bundled donations (FEC API)", True, "up to date")

    def _fec_find(self, name):
        """Federal candidates whose FEC name matches (FEC writes 'LAST, FIRST MIDDLE')."""
        t = self._norm(name)
        if len(t) < 2:
            return [], []
        first, last = t[0], t[-1]
        found = {}
        for r in self.q("SELECT cand_id, name, cycle, receipts FROM fec_cand WHERE name LIKE ?", ("%" + last.upper() + "%",)):
            nm = r["name"] or ""
            parts = nm.split(",", 1)
            ln, fn = self._norm(parts[0]), self._norm(parts[1] if len(parts) > 1 else "")
            if last not in ln or not fn or not (fn[0] == first or fn[0].startswith(first) or first.startswith(fn[0])):
                continue
            f = found.setdefault(r["cand_id"], {"id": r["cand_id"], "fec_name": nm, "total": 0.0, "cycles": []})
            f["total"] += r["receipts"] or 0
            f["cycles"].append(r["cycle"])
        L = sorted(found.values(), key=lambda f: -f["total"])
        OFF = {"P": "President", "S": "Senate", "H": "House"}
        for f in L:
            f["office"] = OFF.get(f["id"][:1], "")
            f["state"] = f["id"][2:4] if f["id"][:1] in "HS" else ""
        if len({(f["office"], f["state"]) for f in L}) > 3:      # a common name: keep the biggest campaigns only
            L = L[:2]
        return [f["id"] for f in L], L

    def money(self, bio="", name=""):
        matched = None
        if bio:
            p = self.us_people().get(bio)
            if not p:
                return {"error": "Not a member of Congress."}
            ids, label = p.get("fec") or [], p["name"]
            if not ids:
                return {"error": "No FEC candidate id on file for %s." % p["name"]}
        else:
            ids, matched = self._fec_find(name)
            label = name
            if not ids:
                return {"name": name, "cycles": [], "not_candidate": True,
                        "loaded": bool(self.q("SELECT 1 FROM fec_cand LIMIT 1", one=True))}
        p = {"name": label}
        qs = ",".join("?" * len(ids))
        out = []
        for cyc in self._fec_cycles():
            cands = self.q("SELECT * FROM fec_cand WHERE cycle=? AND cand_id IN (%s) ORDER BY receipts DESC" % qs, [cyc] + ids)
            pacs = self.q("""SELECT f.cmte_id, f.kind, SUM(f.amount) amt, SUM(f.n) n, c.name, c.org, c.type FROM fec_pac f
                             LEFT JOIN fec_cmte c ON c.cmte_id = f.cmte_id WHERE f.cycle=? AND f.cand_id IN (%s)
                             GROUP BY f.cmte_id, f.kind""" % qs, [cyc] + ids)
            cmtes = [r["cmte_id"] for r in self.q("SELECT cmte_id FROM fec_ccl WHERE cycle=? AND cand_id IN (%s)" % qs, [cyc] + ids)]
            bundles = self.q("""SELECT b.conduit, SUM(b.total) total, SUM(b.n) n, c.name, c.org FROM fec_bundle b LEFT JOIN fec_cmte c ON c.cmte_id=b.conduit
                                WHERE b.cycle=? AND b.recipient IN (%s) GROUP BY b.conduit""" % (",".join("?" * len(cmtes)) or "''"), [cyc] + cmtes) if cmtes else []
            if not cands and not pacs:
                continue
            c = cands[0] if cands else None
            donors = {}
            def org_of(name, org):
                org = (org or "").strip()
                if org.upper() in ("NONE", "N/A", "NA", "NONE.", "-"):
                    org = ""
                nm = org or (name or "").strip()
                nm = re.sub(r"\bPOLITICAL ACTION COMMITTEE\b", "PAC", nm, flags=re.I)
                return nm
            outside = {}
            for r in pacs:
                nm = org_of(r["name"], r["org"]) or r["cmte_id"]
                if r["kind"] in ("for", "against"):
                    o = outside.setdefault(nm, {"name": nm, "for": 0.0, "against": 0.0, "type": r["type"] or "", "ids": []})
                    o[r["kind"]] += r["amt"] or 0
                    o["ids"].append(r["cmte_id"])
                    continue
                d = donors.setdefault(nm, {"name": nm, "direct": 0.0, "earmarked": 0.0, "type": r["type"] or "", "ids": []})
                d["direct"] += r["amt"] or 0
                d["ids"].append(r["cmte_id"])
            for r in bundles:
                nm = org_of(r["name"], r["org"]) or r["conduit"]
                d = donors.setdefault(nm, {"name": nm, "direct": 0.0, "earmarked": 0.0, "type": "", "ids": []})
                direct_same = sum(x["amt"] or 0 for x in pacs if x["cmte_id"] == r["conduit"] and x["kind"] == "direct")
                d["earmarked"] += max(0.0, (r["total"] or 0) - direct_same)
            for d in donors.values():
                d["total"] = round(d["direct"] + d["earmarked"], 2)
            dl = sorted(donors.values(), key=lambda d: -d["total"])
            ol = sorted(outside.values(), key=lambda o: -(o["for"] + o["against"]))
            src = None
            if c:
                other = (c["receipts"] or 0) - (c["indiv"] or 0) - (c["pac"] or 0) - (c["party_c"] or 0) - (c["self_c"] or 0) - (c["transfers"] or 0)
                src = {"individuals": c["indiv"], "pacs": c["pac"], "party": c["party_c"], "self": c["self_c"],
                       "other": max(0.0, other), "transfers": c["transfers"]}
            out.append({"cycle": cyc, "receipts": c["receipts"] if c else None, "spent": c["disb"] if c else None,
                        "cash": c["cash"] if c else None, "through": c["end_date"] if c else "", "sources": src,
                        "donors": dl[:40], "n_donors": len(dl), "outside": ol[:25], "cand_ids": [r["cand_id"] for r in cands]})
        return {"name": p["name"], "cycles": out, "fec_ids": ids, "key": bool(self.settings.get("fec_key")), "matched": matched,
                "bundle_status": self.status.get("Bundled donations (FEC API)")}

    # ---- live FEC lookups (API; free demo key, or your own key) for what the bulk files don't break out
    def _fec_api(self, path):
        key = self.settings.get("fec_key") or "DEMO_KEY"
        try:
            return self.getj("https://api.open.fec.gov/v1/" + path + ("&" if "?" in path else "?") + "api_key=" + key, timeout=60), None
        except self.FetchError as e:
            if "429" in str(e) or "403" in str(e):
                return None, ("The FEC's free demo key is out of lookups for this hour; try again later, or add a free personal key "
                              "(api.data.gov) under lawmaking › data sources." if key == "DEMO_KEY" else "The FEC says the key has hit its limit for now.")
            return None, "Couldn't reach the FEC (%s)." % e

    def donations(self, name):
        """What this person gave to federal campaigns, parties and PACs (like OpenSecrets' donor lookup)."""
        t = self._norm(name)
        if len(t) < 2:
            return {"error": "Need a first and last name."}
        ck = "don:" + " ".join(t)
        hit = self.kv(ck)
        if hit and _now() - hit.get("at", 0) < 30 * 86400:
            return hit
        cname = "%s, %s" % (t[-1].upper(), t[0].upper())
        cyc = self._fec_cycles()
        rows, err = [], None
        for period in cyc[:3]:
            j, err = self._fec_api("schedules/schedule_a/?contributor_name=%s&is_individual=true&per_page=100&sort=-contribution_receipt_amount&two_year_transaction_period=%d"
                                   % (urllib.parse.quote(cname), period))
            if j is None:
                break
            rows += j.get("results") or []
        if err and not rows:
            return {"error": err}
        first = t[0]
        to, emp, parties = {}, {}, {}
        for r in rows:
            nm = self._norm(r.get("contributor_name") or "")
            if t[-1] not in nm or not any(x == first or x.startswith(first) or first.startswith(x) for x in nm if x != t[-1]):
                continue
            cm = r.get("committee") or {}
            cn = (cm.get("name") or r.get("committee_name") or "").strip()
            if not cn or re.match(r"^(ACTBLUE|WINRED)\b", cn.upper()):
                continue      # pass-through platforms: the money is counted where it lands
            amt = _num(r.get("contribution_receipt_amount"))
            d = to.setdefault(cn, {"name": cn, "amount": 0.0, "n": 0, "party": cm.get("party") or "", "type": cm.get("committee_type_full") or ""})
            d["amount"] += amt
            d["n"] += 1
            pk = {"REP": "Republican", "DEM": "Democratic"}.get((cm.get("party") or "").upper(), "No party listed")
            parties[pk] = parties.get(pk, 0) + amt
            e = (r.get("contributor_employer") or "").strip()
            if e:
                emp[e] = emp.get(e, 0) + 1
        out = {"name": name, "searched": cname, "total": round(sum(d["amount"] for d in to.values()), 2), "count": sum(d["n"] for d in to.values()),
               "to": sorted(to.values(), key=lambda d: -d["amount"])[:40], "parties": parties,
               "employers": [e for e, _ in sorted(emp.items(), key=lambda x: -x[1])[:5]], "cycles": cyc[:3], "at": _now(),
               "partial": bool(err)}
        if not err:
            self.kv_set(ck, out)
        return out

    def employers(self, cand_id, cycle):
        """Where a candidate's individual donors work (employer totals from the FEC; OpenSecrets builds its 'top contributors' the same way)."""
        ck = "emp:%s:%s" % (cand_id, cycle)
        hit = self.kv(ck)
        if hit and _now() - hit.get("at", 0) < 30 * 86400:
            return hit
        cm = self.q("SELECT cmte_id FROM fec_ccl WHERE cand_id=? AND cycle=? ORDER BY dsgn='P' DESC LIMIT 1", (cand_id, int(cycle)), one=True)
        if not cm:
            return {"error": "No campaign committee on file for that cycle."}
        j, err = self._fec_api("schedules/schedule_a/by_employer/?committee_id=%s&cycle=%s&sort=-total&per_page=40" % (cm["cmte_id"], cycle))
        if j is None:
            return {"error": err}
        SKIP = re.compile(r"^(RETIRED|NOT EMPLOYED|NONE|SELF[- ]?EMPLOYED|SELF|N/?A|HOMEMAKER|INFORMATION REQUESTED.*|REQUESTED|UNEMPLOYED|STUDENT|DISABLED|ENTREPRENEUR|)$", re.I)
        L = [{"name": r.get("employer") or "", "total": _num(r.get("total")), "n": _int(r.get("count"))} for r in j.get("results") or []]
        out = {"employers": [x for x in L if not SKIP.match(x["name"].strip())][:20], "skipped": sum(x["total"] for x in L if SKIP.match(x["name"].strip())), "at": _now()}
        self.kv_set(ck, out)
        return out

    # ================================================================== UNITED KINGDOM
    def pull_gb(self):
        got = 0
        try:
            L = self.getj("https://commonsvotes-api.parliament.uk/data/divisions.json/search?queryParameters.take=50", timeout=60)
            for d in L or []:
                if got >= 40 or self._stop():
                    break
                vid = "GB-C-%s" % d["DivisionId"]
                if self.have(vid):
                    continue
                try:
                    D = self.getj("https://commonsvotes-api.parliament.uk/data/division/%s.json" % d["DivisionId"], timeout=60)
                except self.FetchError:
                    continue
                mem = []
                for lst, pos in (("Ayes", "Y"), ("Noes", "N"), ("NoVoteRecorded", "X")):
                    for m in D.get(lst) or []:
                        mem.append(("GB:%s" % m.get("MemberId"), m.get("Name") or "", m.get("Party") or "", pos, m.get("MemberFrom") or ""))
                a, n = _int(D.get("AyeCount")), _int(D.get("NoCount"))
                self.save_vote({"id": vid, "cc": "GB", "chamber": "C", "date": (D.get("Date") or "")[:10], "title": D.get("Title") or "",
                                "question": D.get("FriendlyTitle") or "", "result": "Ayes had it" if a > n else "Noes had it",
                                "yes": a, "no": n, "absent": len(D.get("NoVoteRecorded") or []),
                                "url": "https://votes.parliament.uk/votes/commons/division/%s" % d["DivisionId"]}, mem)
                got += 1
                time.sleep(0.2)
            L = self.getj("https://lordsvotes-api.parliament.uk/data/Divisions/search?skip=0&take=40", timeout=60)
            for D in L or []:
                vid = "GB-L-%s" % D.get("divisionId")
                if self.have(vid):
                    continue
                mem = []
                for lst, pos in (("contents", "Y"), ("notContents", "N")):
                    for m in D.get(lst) or []:
                        mem.append(("GB:%s" % m.get("memberId"), m.get("name") or "", m.get("party") or "", pos, m.get("memberFrom") or ""))
                a, n = _int(D.get("authoritativeContentCount")), _int(D.get("authoritativeNotContentCount"))
                self.save_vote({"id": vid, "cc": "GB", "chamber": "L", "date": (D.get("date") or "")[:10], "title": D.get("title") or "",
                                "question": strip_html(D.get("amendmentMotionNotes") or "")[:400], "result": "Contents had it" if a > n else "Not-contents had it",
                                "yes": a, "no": n, "url": "https://votes.parliament.uk/votes/lords/division/%s" % D.get("divisionId"),
                                "extra": {"govwin": D.get("isGovernmentWin")}}, mem)
                got += 1
            self._ok("UK Parliament votes", True, "%d new" % got)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("UK Parliament votes", False, str(e))

    def pull_gb_bills(self):
        newest = self.kv("gb_bills_newest", "") or ""
        top = ""
        n = 0
        try:
            for page in range(12):
                j = self.getj("https://bills-api.parliament.uk/api/v1/Bills?SortOrder=DateUpdatedDescending&Take=50&Skip=%d" % (page * 50), timeout=60)
                items = j.get("items") or []
                stop = False
                for b in items:
                    lu = b.get("lastUpdate") or ""
                    top = max(top, lu)
                    if newest and lu <= newest:
                        stop = True
                        break
                    self._gb_bill(b)
                    n += 1
                if stop or not items or self._stop():
                    break
            if top:
                self.kv_set("gb_bills_newest", top)
            self._ok("UK bills", True, "%d updated" % n)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("UK bills", False, str(e))

    def _gb_bill(self, b):
        cs = b.get("currentStage") or {}
        desc, house, orig = (cs.get("description") or ""), cs.get("house") or "", b.get("originatingHouse") or ""
        d = desc.lower()
        if b.get("isAct"):
            stage, txt = 6, "Became law (Royal Assent)"
        elif b.get("billWithdrawn") or b.get("isDefeated"):
            stage, txt = -1, "Withdrawn" if b.get("billWithdrawn") else "Defeated"
        elif "royal assent" in d:
            stage, txt = 5, "Awaiting Royal Assent"
        elif "consideration of" in d or "ping pong" in d or "amendments" in d:
            stage, txt = 4, desc + " (" + house + ")"
        elif house and orig and house != orig and house != "Unassigned":
            stage, txt = 3, "Passed the %s; now in the %s: %s" % (orig, house, desc)
        elif "1st reading" in d:
            stage, txt = 0, "Introduced in the %s" % (house or orig)
        elif "3rd reading" in d or "report" in d:
            stage, txt = 2, desc + " (" + (house or orig) + ")"
        else:
            stage, txt = 1, (desc or "In progress") + (" (" + (house or orig) + ")" if (house or orig) else "")
        bid = "GB-%s" % b.get("billId")
        old = self.q("SELECT summary, extra FROM bills WHERE id=?", (bid,), one=True)
        self.x("""INSERT OR REPLACE INTO bills(id, cc, num, title, sponsor, sponsor_key, party, introduced, updated, stage, stage_text,
            latest_date, latest_text, enacted, url, summary, subject, chamber, extra, srcmod) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (bid, "GB", "", b.get("shortTitle") or "", "", "", "", "", (b.get("lastUpdate") or "")[:10], stage, txt,
                (b.get("lastUpdate") or "")[:10], desc, "Act of Parliament" if b.get("isAct") else "",
                "https://bills.parliament.uk/bills/%s" % b.get("billId"), old["summary"] if old else "", "", orig,
                old["extra"] if old else json.dumps({"session": b.get("introducedSessionId")}), b.get("lastUpdate") or ""))

    def _gb_bill_detail(self, bid):
        n = bid.split("-", 1)[1]
        d = self.getj("https://bills-api.parliament.uk/api/v1/Bills/%s" % n, timeout=40)
        st = self.getj("https://bills-api.parliament.uk/api/v1/Bills/%s/Stages?Take=60" % n, timeout=40)
        acts = []
        for s in st.get("items") or []:
            dates = [x.get("date", "")[:10] for x in s.get("stageSittings") or [] if x.get("date")]
            acts.append([dates[0] if dates else "", "%s: %s" % (s.get("house") or "", s.get("description") or ""), ""])
        sp = (d.get("sponsors") or [{}])[0] if d.get("sponsors") else {}
        mem = sp.get("member") or {}
        org = (sp.get("organisation") or {}).get("name") or ""
        summary = strip_html(d.get("summary") or "") or strip_html(d.get("longTitle") or "")
        extra = {"actions": acts, "long_title": strip_html(d.get("longTitle") or "")}
        self.x("UPDATE bills SET sponsor=?, sponsor_key=?, party=?, summary=?, extra=?, introduced=? WHERE id=?",
               (mem.get("name", "") + (" (" + org + ")" if org else ""), "GB:%s" % mem["memberId"] if mem.get("memberId") else "",
                mem.get("party", ""), summary, json.dumps(extra), acts[0][0] if acts else "", bid))

    # ================================================================== EUROPEAN PARLIAMENT
    def pull_eu(self):
        got = 0
        try:
            for page in (1, 2):
                j = self.getj("https://howtheyvote.eu/api/votes?page=%d&page_size=50" % page, timeout=60)
                for v in j.get("results") or []:
                    if got >= 30 or self._stop():
                        break
                    vid = "EU-%s" % v["id"]
                    if self.have(vid):
                        continue
                    try:
                        self._eu_vote(v["id"])
                        got += 1
                    except (self.FetchError, KeyError):
                        continue
                    time.sleep(0.3)
            try:     # plenary days ahead
                cal = []
                for yr in (_today().year, _today().year + 1):
                    j = self.getj("https://data.europarl.europa.eu/api/v2/meetings?year=%d&format=application%%2Fld%%2Bjson&offset=0&limit=200" % yr, timeout=120)
                    for m in j.get("data") or []:
                        dt = (m.get("activity_date") or "")[:10]
                        if dt >= _today().isoformat() and "PLENARY" in (m.get("had_activity_type") or ""):
                            where = "Strasbourg" if "FRA_SXB" in (m.get("hasLocality") or "") else "Brussels" if "BEL_BRU" in (m.get("hasLocality") or "") else ""
                            cal.append(("EU-" + dt, "EU", dt, "", "European Parliament plenary sitting" + (" in " + where if where else ""), "Plenary",
                                        "European Parliament (votes happen during plenary weeks)", "https://www.europarl.europa.eu/plenary/en/home.html", _now()))
                if cal:
                    self.many("INSERT OR REPLACE INTO cal(id, cc, date, time, title, kind, body, url, seen) VALUES(?,?,?,?,?,?,?,?,?)", cal)
            except (self.FetchError, TypeError, AttributeError):
                pass
            self._ok("European Parliament votes", True, "%d new" % got)
        except (self.FetchError, KeyError) as e:
            self._ok("European Parliament votes", False, str(e))

    def _eu_vote(self, n):
        d = self.getj("https://howtheyvote.eu/api/votes/%s" % n, timeout=60)
        P = {"FOR": "Y", "AGAINST": "N", "ABSTENTION": "A", "DID_NOT_VOTE": "X"}
        mem = []
        for mv in d.get("member_votes") or []:
            m = mv.get("member") or {}
            g = (m.get("group") or {}).get("short_label") or (m.get("group") or {}).get("code") or ""
            mem.append(("EU:%s" % m.get("id"), nice_name(m.get("full_name") or ""), g, P.get(mv.get("position"), "O"),
                        (m.get("country") or {}).get("label") or ""))
        tot = (d.get("stats") or {}).get("total") or {}
        proc = d.get("procedure") or {}
        q = d.get("description") or ""
        if d.get("amendment_number"):
            q = "Amendment %s%s" % (d["amendment_number"], (": " + d["amendment_subject"]) if d.get("amendment_subject") else "")
        self.save_vote({"id": "EU-%s" % n, "cc": "EU", "chamber": "P", "date": (d.get("timestamp") or "")[:10],
                        "title": d.get("display_title") or proc.get("title") or "", "question": q,
                        "result": {"ADOPTED": "Adopted", "REJECTED": "Rejected"}.get(d.get("result"), d.get("result") or ""),
                        "yes": tot.get("FOR"), "no": tot.get("AGAINST"), "abstain": tot.get("ABSTENTION"), "absent": tot.get("DID_NOT_VOTE"),
                        "bill": proc.get("reference") or "", "url": "https://howtheyvote.eu/votes/%s" % n,
                        "extra": {"procedure": proc, "main": d.get("is_main")}}, mem)

    # ================================================================== CANADA
    def pull_ca(self):
        H = {"API-Version": "v1"}
        got = 0
        try:
            pols = {}
            if not self.kv("ca_pols") or (_now() - (self.kv("ca_pols_at", 0) or 0)) > 7 * 86400:
                j = self.getj("https://api.openparliament.ca/politicians/?format=json&limit=500", timeout=60, headers=H)
                for p in j.get("objects") or []:
                    pols[p["url"]] = [p.get("name") or "", ((p.get("current_party") or {}).get("short_name") or {}).get("en") or "",
                                      ((p.get("current_riding") or {}).get("name") or {}).get("en") or ""]
                self.kv_set("ca_pols", pols)
                self.kv_set("ca_pols_at", _now())
            pols = self.kv("ca_pols", {}) or {}
            j = self.getj("https://api.openparliament.ca/votes/?format=json&limit=60", timeout=60, headers=H)
            for v in j.get("objects") or []:
                if got >= 30 or self._stop():
                    break
                vid = "CA-%s-%s" % (v["session"], v["number"])
                if self.have(vid):
                    continue
                b = self.getj("https://api.openparliament.ca/votes/ballots/?format=json&limit=500&vote=" + urllib.parse.quote(v["url"]), timeout=60, headers=H)
                P = {"Yes": "Y", "No": "N", "Paired": "O", "Didn't vote": "X"}
                mem = []
                for x in b.get("objects") or []:
                    pu = x.get("politician_url") or ""
                    info = pols.get(pu) or [nice_name(pu.strip("/").split("/")[-1].replace("-", " ").title()), "", ""]
                    mem.append(("CA:" + pu.strip("/").split("/")[-1], info[0], info[1], P.get(x.get("ballot"), "O"), info[2]))
                bill = ""
                if v.get("bill_url"):
                    m = re.match(r"/bills/([^/]+)/([^/]+)/", v["bill_url"])
                    bill = "CA-%s-%s" % m.groups() if m else ""
                self.save_vote({"id": vid, "cc": "CA", "chamber": "C", "date": v.get("date") or "",
                                "title": (v.get("description") or {}).get("en") or "", "result": v.get("result") or "",
                                "yes": v.get("yea_total"), "no": v.get("nay_total"), "bill": bill,
                                "url": "https://openparliament.ca" + v["url"], "extra": {"paired": v.get("paired_total")}}, mem)
                got += 1
                time.sleep(0.4)
            sess = (j.get("objects") or [{}])[0].get("session") if j.get("objects") else None
            if sess and not self._stop():
                self._ca_bills(sess, H)
            self._ok("Canada votes and bills", True, "%d new votes" % got)
        except (self.FetchError, KeyError, TypeError, AttributeError) as e:
            self._ok("Canada votes and bills", False, str(e))

    def _ca_bills(self, sess, H):
        j = self.getj("https://api.openparliament.ca/bills/?format=json&limit=500&session=%s" % sess, timeout=60, headers=H)
        known = {r["id"]: r["srcmod"] for r in self.q("SELECT id, srcmod FROM bills WHERE cc='CA'")}
        todo = []
        for b in j.get("objects") or []:
            bid = "CA-%s-%s" % (b["session"], b["number"])
            if bid not in known:
                todo.append((0, bid, b))
            elif _now() - _int(known[bid] or 0) > 5 * 86400:
                todo.append((_int(known[bid] or 0), bid, b))
        todo.sort(key=lambda x: x[0])
        for _, bid, b in todo[:40]:
            if self._stop():
                return
            try:
                d = self.getj("https://api.openparliament.ca%s?format=json" % b["url"], timeout=40, headers=H)
            except self.FetchError:
                continue
            code = d.get("status_code") or ""
            home = d.get("home_chamber") or "House"
            stx = (d.get("status") or {}).get("en") or code
            c = code.lower()
            if "royalassent" in c and "awaiting" not in c:
                stage = 6
            elif "awaiting" in c:
                stage = 5
            elif "defeated" in c or "notproceeded" in c or "withdrawn" in c or "proforma" in c:
                stage = -1
            elif (home == "House" and c.startswith("senate")) or (home == "Senate" and c.startswith("house")):
                stage = 3
            elif "1streading" in c or c == "introduced":
                stage = 0
            elif "report" in c or "3rdreading" in c:
                stage = 2
            else:
                stage = 1
            sp = (d.get("sponsor_politician_url") or "").strip("/").split("/")[-1]
            pol = (self.kv("ca_pols", {}) or {}).get(d.get("sponsor_politician_url") or "") or ["", "", ""]
            name = (d.get("name") or {}).get("en") or ""
            short = (d.get("short_title") or {}).get("en") or ""
            self.x("""INSERT OR REPLACE INTO bills(id, cc, num, title, sponsor, sponsor_key, party, introduced, updated, stage, stage_text,
                latest_date, latest_text, enacted, url, summary, subject, chamber, extra, srcmod) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                   (bid, "CA", d.get("number") or b["number"], short or name, pol[0] or sp.replace("-", " ").title(), "CA:" + sp if sp else "",
                    pol[1], d.get("introduced") or "", "", stage, stx, d.get("introduced") or "", stx,
                    "Royal Assent" if stage == 6 else "", d.get("legisinfo_url") or "https://openparliament.ca" + b["url"],
                    name if short else "", "", home, json.dumps({"private": d.get("private_member_bill"), "votes": d.get("vote_urls") or []}), str(_now())))
            time.sleep(0.3)

    # ================================================================== IRELAND
    def pull_ie(self):
        got = 0
        start = (_today() - datetime.timedelta(days=120)).isoformat()
        try:
            parties = self.kv("ie_parties", {}) or {}
            for ch in ("dail", "seanad"):
                j = self.getj("https://api.oireachtas.ie/v1/divisions?chamber_type=house&chamber=%s&date_start=%s&limit=200" % (ch, start), timeout=90)
                res = j.get("results") or []
                hno = ((res[0].get("division") or {}).get("house") or {}).get("houseNo") if res else None
                if hno and (not parties.get(ch + hno)):
                    mj = self.getj("https://api.oireachtas.ie/v1/members?chamber=%s&house_no=%s&limit=400" % (ch, hno), timeout=90)
                    pm = {}
                    for r in mj.get("results") or []:
                        m = r.get("member") or {}
                        ms = (m.get("memberships") or [{}])[0].get("membership") or {}
                        pt = ((ms.get("parties") or [{}])[-1].get("party") or {}).get("showAs") or ""
                        rp = ((ms.get("represents") or [{}])[0].get("represent") or {}).get("showAs") or ""
                        pm[m.get("memberCode")] = [m.get("fullName") or "", pt, rp]
                    parties[ch + hno] = pm
                    self.kv_set("ie_parties", parties)
                pm = parties.get(ch + (hno or ""), {})
                for r in res:
                    d = r.get("division") or {}
                    vid = "IE-%s-%s-%s" % (ch, d.get("date"), d.get("voteId"))
                    if self.have(vid):
                        continue
                    mem = []
                    for k, pos in (("taVotes", "Y"), ("nilVotes", "N"), ("staonVotes", "A")):
                        for x in ((d.get("tallies") or {}).get(k) or {}).get("members") or []:
                            m = x.get("member") or {}
                            info = pm.get(m.get("memberCode")) or [nice_name(m.get("showAs") or ""), "", ""]
                            mem.append(("IE:%s" % m.get("memberCode"), info[0] or nice_name(m.get("showAs") or ""), info[1], pos, info[2]))
                    t = d.get("tallies") or {}
                    self.save_vote({"id": vid, "cc": "IE", "chamber": "D" if ch == "dail" else "S", "date": d.get("date") or "",
                                    "title": (d.get("debate") or {}).get("showAs") or "", "question": ((d.get("subject") or {}).get("showAs") or "").strip(" :"),
                                    "result": d.get("outcome") or "", "yes": (t.get("taVotes") or {}).get("tally"), "no": (t.get("nilVotes") or {}).get("tally"),
                                    "abstain": (t.get("staonVotes") or {}).get("tally"),
                                    "url": "https://www.oireachtas.ie/en/debates/vote/%s/%s/%s/%s/" % (ch, hno or "", d.get("date"), (d.get("voteId") or "").replace("vote_", ""))}, mem)
                    got += 1
            # bills
            j = self.getj("https://api.oireachtas.ie/v1/legislation?limit=300&date_start=%s" % (_today() - datetime.timedelta(days=730)).isoformat(), timeout=90)
            for r in j.get("results") or []:
                self._ie_bill(r.get("bill") or {})
            self._ok("Ireland votes and bills", True, "%d new votes" % got)
        except (self.FetchError, KeyError, TypeError, IndexError) as e:
            self._ok("Ireland votes and bills", False, str(e))

    def _ie_bill(self, b):
        if not b.get("billNo"):
            return
        st = (b.get("status") or "")
        mr = (b.get("mostRecentStage") or {}).get("event") or {}
        origin = ((b.get("originHouse") or {}).get("showAs") or "")
        house = ((mr.get("house") or {}).get("chamberCode") or "")
        ps = _int(mr.get("progressStage"))
        if st == "Enacted":
            stage, txt = 6, "Enacted (signed into law)"
        elif st in ("Defeated", "Withdrawn", "Lapsed", "Rejected"):
            stage, txt = -1, st
        elif house and origin and not origin.lower().startswith(("dáil" if house == "dail" else "seanad")):
            stage, txt = 3, "Passed the %s; now at %s in the %s" % (origin, mr.get("showAs") or "", "Seanad" if house == "seanad" else "Dáil")
        else:
            stage = 0 if ps <= 1 else 1 if ps <= 3 else 2
            txt = (mr.get("showAs") or "In progress") + (" (" + origin + ")" if origin else "")
        acts = []
        for s in b.get("stages") or []:
            e = s.get("event") or {}
            ds = [x.get("date") for x in e.get("dates") or [] if x.get("date")]
            acts.append([ds[0] if ds else "", "%s: %s" % ((e.get("chamber") or {}).get("showAs") or "", e.get("showAs") or ""), ""])
        sp = [s.get("sponsor") or {} for s in b.get("sponsors") or []]
        spn = ", ".join(((x.get("by") or {}).get("showAs") or (x.get("as") or {}).get("showAs") or "") for x in sp if x)
        spk = ((sp[0].get("by") or {}).get("uri") or "").rsplit("/", 1)[-1] if sp else ""
        last = max([a[0] for a in acts if a[0]] or [b.get("lastUpdated", "")[:10]])
        self.x("""INSERT OR REPLACE INTO bills(id, cc, num, title, sponsor, sponsor_key, party, introduced, updated, stage, stage_text,
            latest_date, latest_text, enacted, url, summary, subject, chamber, extra, srcmod) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               ("IE-%s-%s" % (b.get("billYear"), b.get("billNo")), "IE", "Bill %s of %s" % (b.get("billNo"), b.get("billYear")),
                b.get("shortTitleEn") or "", spn, "IE:" + spk if spk else "", b.get("source") or "", acts[0][0] if acts else "",
                (b.get("lastUpdated") or "")[:10], stage, txt, last, mr.get("showAs") or "", (b.get("act") or {}).get("shortTitleEn", "") if isinstance(b.get("act"), dict) else "",
                "https://www.oireachtas.ie/en/bills/bill/%s/%s/" % (b.get("billYear"), b.get("billNo")), strip_html(b.get("longTitleEn") or ""),
                "", origin, json.dumps({"actions": acts, "source": b.get("source")}), b.get("lastUpdated") or ""))

    # ================================================================== POLAND
    def pull_pl(self):
        try:
            term = self.kv("pl_term") or 10
            try:
                terms = self.getj("https://api.sejm.gov.pl/sejm/term", timeout=40)
                cur = [t["num"] for t in terms if t.get("current")]
                term = cur[0] if cur else term
                self.kv_set("pl_term", term)
            except (self.FetchError, KeyError, TypeError):
                pass
            base = "https://api.sejm.gov.pl/sejm/term%s" % term
            if not self.kv("pl_mps_at") or _now() - self.kv("pl_mps_at") > 7 * 86400:
                mps = self.getj(base + "/MP", timeout=60)
                self.kv_set("pl_mps", {str(m["id"]): [m.get("firstLastName") or "", m.get("club") or "", m.get("districtName") or ""] for m in mps})
                self.kv_set("pl_mps_at", _now())
            try:
                cal = []
                for pr in self.getj(base + "/proceedings", timeout=60) or []:
                    for dt in pr.get("dates") or []:
                        if dt >= _today().isoformat():
                            cal.append(("PL-%s-%s" % (pr.get("number"), dt), "PL", dt, "", "Sejm sitting no. %s%s" % (pr.get("number"), (": " + pr["title"]) if pr.get("title") and "Posiedzenie" not in pr.get("title", "") else ""),
                                        "Sitting", "Polish Sejm (votes are usually held on these days)", "https://www.sejm.gov.pl/", _now()))
                if cal:
                    self.many("INSERT OR REPLACE INTO cal(id, cc, date, time, title, kind, body, url, seen) VALUES(?,?,?,?,?,?,?,?,?)", cal)
            except (self.FetchError, TypeError, KeyError, AttributeError):
                pass
            sittings = self.getj(base + "/votings", timeout=60)
            for s in sorted(sittings, key=lambda s: s.get("proceeding", 0))[-3:]:
                L = self.getj(base + "/votings/%s" % s["proceeding"], timeout=60)
                for v in L:
                    vid = "PL-%s-%s-%s" % (term, v.get("sitting"), v.get("votingNumber"))
                    if self.have(vid):
                        continue
                    self.save_vote({"id": vid, "cc": "PL", "chamber": "S", "date": (v.get("date") or "")[:10],
                                    "title": v.get("topic") or v.get("title") or "", "question": v.get("title") or "",
                                    "yes": v.get("yes"), "no": v.get("no"), "abstain": v.get("abstain"), "absent": v.get("notParticipating"),
                                    "url": "https://www.sejm.gov.pl/sejm10.nsf/agent.xsp?symbol=glosowania&nrkadencji=%s&nrposiedzenia=%s&nrglosowania=%s" % (term, v.get("sitting"), v.get("votingNumber")),
                                    "kind": v.get("kind") or "", "extra": {"term": term, "sitting": v.get("sitting"), "n": v.get("votingNumber"),
                                                                             "majority": v.get("majorityType")}})
            for vid in self.need_detail("PL", 25):
                if self._stop():
                    return
                self.detail(vid)
                time.sleep(0.2)
            known = {r["id"]: r["srcmod"] for r in self.q("SELECT id, srcmod FROM bills WHERE cc='PL'")}
            j = self.getj(base + "/processes?limit=5000", timeout=120)
            for p in j:
                if known.get("PL-%s-%s" % (term, p.get("number"))) == (p.get("changeDate") or ""):
                    continue
                passed = p.get("passed")
                eli = p.get("ELI") or ""
                stage = 6 if eli else 3 if passed else 1
                txt = ("Published as law (%s)" % p.get("displayAddress")) if eli else "Passed by the Sejm" if passed else "In the Sejm"
                self.x("""INSERT OR REPLACE INTO bills(id, cc, num, title, sponsor, sponsor_key, party, introduced, updated, stage, stage_text,
                    latest_date, latest_text, enacted, url, summary, subject, chamber, extra, srcmod) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                       ("PL-%s-%s" % (term, p.get("number")), "PL", "Print %s" % p.get("number"), p.get("title") or "", "", "",
                        p.get("documentType") or "", p.get("processStartDate") or "", (p.get("changeDate") or "")[:10], stage, txt,
                        (p.get("changeDate") or "")[:10], txt, p.get("displayAddress") or "" if eli else "",
                        "https://www.sejm.gov.pl/Sejm%s.nsf/PrzebiegProc.xsp?nr=%s" % (term, p.get("number")),
                        p.get("titleFinal") or "", "", "Sejm", json.dumps({"type": p.get("documentType")}), p.get("changeDate") or ""))
            self._ok("Poland votes and bills", True)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Poland votes and bills", False, str(e))

    # ================================================================== GERMANY
    def pull_de(self):
        try:
            lp = self.kv("de_lp")
            if not lp or _now() - (self.kv("de_lp_at", 0) or 0) > 30 * 86400:
                lp = self.getj("https://www.abgeordnetenwatch.de/api/v2/parliaments/5", timeout=40)["data"]["current_project"]["id"]
                self.kv_set("de_lp", lp)
                self.kv_set("de_lp_at", _now())
            j = self.getj("https://www.abgeordnetenwatch.de/api/v2/polls?field_legislature=%s&range_end=40&sort_by=field_poll_date&sort_direction=desc" % lp, timeout=60)
            got = 0
            for p in j.get("data") or []:
                vid = "DE-%s" % p["id"]
                if self.have(vid) or got >= 10 or self._stop():
                    continue
                vs = self.getj("https://www.abgeordnetenwatch.de/api/v2/votes?poll=%s&range_end=1000" % p["id"], timeout=90)
                P = {"yes": "Y", "no": "N", "abstain": "A", "no_show": "X"}
                mem = []
                for x in vs.get("data") or []:
                    md = x.get("mandate") or {}
                    mem.append(("DE:%s" % md.get("id"), re.sub(r"\s*\(.*\)$", "", md.get("label") or ""),
                                re.sub(r"\s*\(.*\)$", "", (x.get("fraction") or {}).get("label") or ""), P.get(x.get("vote"), "O"), ""))
                intro = strip_html(p.get("field_intro") or "")
                self.save_vote({"id": vid, "cc": "DE", "chamber": "B", "date": p.get("field_poll_date") or "", "title": p.get("label") or "",
                                "question": "", "result": "Adopted" if p.get("field_accepted") else "Rejected",
                                "url": p.get("abgeordnetenwatch_url") or "", "extra": {"intro": intro[:1500]}}, mem)
                got += 1
                time.sleep(0.5)
            self._ok("Germany named votes", True, "%d new" % got)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Germany named votes", False, str(e))

    # ================================================================== BRAZIL
    def pull_br(self):
        try:
            j = self.getj("https://dadosabertos.camara.leg.br/api/v2/votacoes?idOrgao=180&ordem=DESC&ordenarPor=dataHoraRegistro&itens=100", timeout=60)
            for v in j.get("dados") or []:
                vid = "BR-%s" % v["id"]
                if self.have(vid):
                    continue
                po = v.get("proposicaoObjeto") or ""
                self.save_vote({"id": vid, "cc": "BR", "chamber": "C", "date": v.get("data") or "", "title": v.get("descricao") or "",
                                "question": po, "result": "Approved" if v.get("aprovacao") == 1 else "Rejected" if v.get("aprovacao") == 0 else "",
                                "url": "https://www.camara.leg.br/busca-portal?contextoBusca=BuscaProposicoes&q=" + urllib.parse.quote(po or v.get("descricao") or "")})
            for vid in self.need_detail("BR", 30):
                if self._stop():
                    return
                self.detail(vid)
                time.sleep(0.3)
            self._ok("Brazil votes", True)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Brazil votes", False, str(e))

    # ================================================================== SWITZERLAND
    def _odata(self, j):
        d = j.get("d") if isinstance(j, dict) else None
        if isinstance(d, dict):
            return d.get("results") or []
        return d or (j.get("value") if isinstance(j, dict) else []) or []

    def pull_ch(self):
        try:
            j = self.getj("https://ws.parlament.ch/odata.svc/Vote?$top=80&$filter=Language%20eq%20'EN'&$orderby=VoteEnd%20desc&$format=json", timeout=60)
            for v in self._odata(j):
                vid = "CH-%s" % v["ID"]
                if self.have(vid):
                    continue
                q = " / ".join(x for x in ("Yes = " + (v.get("MeaningYes") or "") if v.get("MeaningYes") else "",
                                           "No = " + (v.get("MeaningNo") or "") if v.get("MeaningNo") else "") if x)
                self.save_vote({"id": vid, "cc": "CH", "chamber": "N", "date": ms_date(v.get("VoteEnd")),
                                "title": "%s %s" % (v.get("BusinessShortNumber") or "", v.get("BusinessTitle") or v.get("BillTitle") or ""),
                                "question": ((v.get("Subject") or "") + (" — " if v.get("Subject") and q else "") + q),
                                "url": "https://www.parlament.ch/en/ratsbetrieb/abstimmungen/abstimmungs-datenbank-nr",
                                "extra": {"business": v.get("BusinessNumber"), "session": v.get("SessionName")}})
            for vid in self.need_detail("CH", 30):
                if self._stop():
                    return
                self.detail(vid)
                time.sleep(0.3)
            self._ok("Switzerland votes", True)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Switzerland votes", False, str(e))

    # ================================================================== FINLAND
    def pull_fi(self):
        try:
            yr = _today().year
            seen = 0
            for page in range(0, 60):
                j = self.getj("https://avoindata.eduskunta.fi/api/v1/tables/SaliDBAanestys/rows?perPage=100&page=%d&columnName=IstuntoVPVuosi&columnValue=%d" % (page, yr), timeout=60)
                cols = j.get("columnNames") or []
                for r in j.get("rowData") or []:
                    d = dict(zip(cols, r))
                    if str(d.get("KieliId")) != "1":
                        continue
                    vid = "FI-%s" % d["AanestysId"]
                    seen += 1
                    if self.have(vid):
                        continue
                    self.save_vote({"id": vid, "cc": "FI", "chamber": "E", "date": (d.get("AanestysAlkuaika") or d.get("IstuntoPvm") or "")[:10],
                                    "title": (d.get("KohtaOtsikko") or "").strip(), "question": (d.get("AanestysOtsikko") or "").strip(),
                                    "yes": _int(d.get("AanestysTulosJaa")), "no": _int(d.get("AanestysTulosEi")),
                                    "abstain": _int(d.get("AanestysTulosTyhjia")), "absent": _int(d.get("AanestysTulosPoissa")),
                                    "bill": (d.get("AanestysValtiopaivaasia") or "").strip(" /"),
                                    "url": "https://www.eduskunta.fi/FI/taysistunto/Sivut/default.aspx",
                                    "extra": {"note": "Jaa/Ei are the two options named in the question, not always yes/no on a bill."}})
                if not j.get("hasMore") or self._stop():
                    break
                time.sleep(0.2)
            for vid in self.need_detail("FI", 20):
                if self._stop():
                    return
                self.detail(vid)
                time.sleep(0.3)
            self._ok("Finland votes", True, "%d this year" % seen)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Finland votes", False, str(e))

    # ================================================================== DENMARK
    def pull_dk(self):
        try:
            j = self.getj("https://oda.ft.dk/api/Afstemning?$orderby=id%20desc&$top=80&$expand=M%C3%B8de,Sagstrin/Sag&$format=json", timeout=60)
            for a in j.get("value") or []:
                vid = "DK-%s" % a["id"]
                if self.have(vid):
                    continue
                sag = (a.get("Sagstrin") or {}).get("Sag") or {}
                kon = a.get("konklusion") or ""
                def cnt(pat):
                    m = re.search(pat + r"\s+(\d+)", kon)
                    return int(m.group(1)) if m else 0
                self.save_vote({"id": vid, "cc": "DK", "chamber": "F", "date": ((a.get("Møde") or {}).get("dato") or "")[:10],
                                "title": sag.get("titelkort") or sag.get("titel") or "", "question": (a.get("Sagstrin") or {}).get("titel") or "",
                                "result": "Adopted" if a.get("vedtaget") else "Rejected", "yes": cnt("For stemte"), "no": cnt("imod stemte"),
                                "abstain": cnt("hverken for eller imod stemte"), "bill": sag.get("nummer") or "",
                                "url": "https://www.ft.dk/da/search?q=%s" % urllib.parse.quote(sag.get("nummer") or sag.get("titelkort") or ""),
                                "extra": {"conclusion": kon, "summary": sag.get("resume") or ""}})
            for vid in self.need_detail("DK", 25):
                if self._stop():
                    return
                self.detail(vid)
                time.sleep(0.3)
            self._ok("Denmark votes", True)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Denmark votes", False, str(e))

    # ================================================================== NETHERLANDS (party votes)
    def pull_nl(self):
        try:
            base = "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Besluit?$filter=Verwijderd%20eq%20false%20and%20StemmingsSoort%20ne%20null&$orderby=GewijzigdOp%20desc&$top=150&$expand=Stemming,Zaak"
            try:
                j = self.getj(base + ",Agendapunt($expand=Activiteit)", timeout=90)
            except self.FetchError:
                j = self.getj(base, timeout=90)
            for b in j.get("value") or []:
                vid = "NL-%s" % b["Id"]
                if self.have(vid):
                    continue
                st = [s for s in b.get("Stemming") or [] if not s.get("Verwijderd") and not s.get("Vergissing")]
                if not st:
                    continue
                z = (b.get("Zaak") or [{}])[0] if b.get("Zaak") else {}
                P = {"Voor": "Y", "Tegen": "N", "Niet deelgenomen": "X"}
                personal = any(s.get("Persoon_Id") for s in st)
                mem, y, n, x = [], 0, 0, 0
                for s in st:
                    pos = P.get(s.get("Soort"), "O")
                    size = 1 if personal else _int(s.get("FractieGrootte")) or 1
                    y += size if pos == "Y" else 0
                    n += size if pos == "N" else 0
                    x += size if pos == "X" else 0
                    if personal:
                        mem.append(("NL:%s" % s.get("Persoon_Id"), s.get("ActorNaam") or "", s.get("ActorFractie") or "", pos, ""))
                    else:
                        mem.append(("NL:party:%s" % slugify(s.get("ActorFractie") or s.get("ActorNaam") or ""), (s.get("ActorFractie") or s.get("ActorNaam") or "") + " (party)",
                                    s.get("ActorFractie") or "", pos, "%s seats" % size))
                bs = b.get("BesluitSoort") or ""
                act = ((b.get("Agendapunt") or {}).get("Activiteit") or {}) if isinstance(b.get("Agendapunt"), dict) else {}
                vdate = (act.get("Datum") or act.get("Aanvangstijd") or b.get("GewijzigdOp") or "")[:10]
                self.save_vote({"id": vid, "cc": "NL", "chamber": "T", "date": vdate,
                                "title": (z.get("Onderwerp") or z.get("Titel") or b.get("BesluitTekst") or "").strip(),
                                "question": " · ".join(x for x in ((z.get("Soort") or ""), (z.get("Titel") or ""), (b.get("StemmingsSoort") or "")) if x),
                                "result": "Adopted" if "aangenomen" in bs else "Rejected" if "verworpen" in bs else bs.replace("Stemmen - ", ""),
                                "yes": y, "no": n, "absent": x, "bill": z.get("Nummer") or "",
                                "url": "https://www.tweedekamer.nl/kamerstukken/detail?id=%s" % (z.get("Nummer") or ""),
                                "kind": "personal" if personal else "party", "extra": {"party_votes": not personal}}, mem)
            self._ok("Netherlands votes", True)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Netherlands votes", False, str(e))

    # ================================================================== ESTONIA
    def pull_ee(self):
        try:
            end = _today()
            start = end - datetime.timedelta(days=60)
            j = self.getj("https://api.riigikogu.ee/api/votings?startDate=%s&endDate=%s&lang=EN" % (start.isoformat(), end.isoformat()), timeout=60)
            for s in j if isinstance(j, list) else []:
                for v in s.get("votings") or []:
                    if ((v.get("type") or {}).get("code") or "") == "KOHALOLEKU_KONTROLL":
                        continue
                    vid = "EE-%s" % v["uuid"]
                    if self.have(vid):
                        continue
                    self.save_vote({"id": vid, "cc": "EE", "chamber": "R", "date": (v.get("startDateTime") or "")[:10],
                                    "title": v.get("description") or "", "question": s.get("title") or "",
                                    "yes": v.get("inFavor"), "no": v.get("against"), "abstain": _int(v.get("abstained")) + _int(v.get("neutral")),
                                    "absent": v.get("absent"), "url": "https://www.riigikogu.ee/tegevus/tooulevaade/haaletustulemused/",
                                    "extra": {"number": v.get("votingNumber"), "type": (v.get("type") or {}).get("value")}})
            for vid in self.need_detail("EE", 25):
                if self._stop():
                    return
                self.detail(vid)
                time.sleep(0.3)
            self._ok("Estonia votes", True)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Estonia votes", False, str(e))

    # ================================================================== FRANCE
    def pull_fr(self):
        leg = self.kv("fr_leg") or 17
        base = "https://data.assemblee-nationale.fr/static/openData/repository/%s/" % leg
        try:
            amo = self.download(base + "amo/deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip", "fr_amo.zip", timeout=900)
            people, groups = {}, {}
            with zipfile.ZipFile(amo) as z:
                for name in z.namelist():
                    if "/organe/" in name:
                        o = json.loads(z.read(name)).get("organe") or {}
                        if o.get("codeType") == "GP":
                            groups[o.get("uid")] = o.get("libelleAbrev") or o.get("libelleAbrege") or o.get("libelle") or ""
                    elif "/acteur/" in name:
                        a = json.loads(z.read(name)).get("acteur") or {}
                        uid = a.get("uid")
                        uid = uid.get("#text") if isinstance(uid, dict) else uid
                        idn = ((a.get("etatCivil") or {}).get("ident") or {})
                        mands = (a.get("mandats") or {}).get("mandat") or []
                        mands = mands if isinstance(mands, list) else [mands]
                        gp = [m for m in mands if m.get("typeOrgane") == "GP" and not m.get("dateFin")]
                        circ = [m for m in mands if m.get("typeOrgane") == "ASSEMBLEE" and not m.get("dateFin")]
                        area = ""
                        if circ:
                            el = (circ[0].get("election") or {}).get("lieu") or {}
                            area = "%s (%s)" % (el.get("departement") or "", el.get("numCirco") or "") if el.get("departement") else ""
                        people[uid] = [("%s %s" % (idn.get("prenom", ""), idn.get("nom", ""))).strip(),
                                       ((gp[0].get("organes") or {}).get("organeRef")) if gp else "", area]
            if self._stop():
                return
            path = self.download(base + "loi/scrutins/Scrutins.json.zip", "fr_scrutins.zip", timeout=1800)
            have = {r["id"] for r in self.q("SELECT id FROM votes WHERE cc='FR'")}
            with zipfile.ZipFile(path) as z:
                names = sorted((n for n in z.namelist() if n.endswith(".json")), key=lambda n: _int(re.search(r"V(\d+)", n).group(1)) if re.search(r"V(\d+)", n) else 0)
                for name in names[-400:]:
                    if self._stop():
                        return
                    s = json.loads(z.read(name)).get("scrutin") or {}
                    vid = "FR-%s-%s" % (leg, s.get("numero"))
                    if vid in have:
                        continue
                    P = {"pours": "Y", "contres": "N", "abstentions": "A", "nonVotants": "X"}
                    mem = []
                    gl = (((s.get("ventilationVotes") or {}).get("organe") or {}).get("groupes") or {}).get("groupe") or []
                    for g in gl if isinstance(gl, list) else [gl]:
                        gname = groups.get(g.get("organeRef"), "")
                        dn = ((g.get("vote") or {}).get("decompteNominatif")) or {}
                        for k, pos in P.items():
                            vv = (dn.get(k) or {}).get("votant") if isinstance(dn.get(k), dict) else None
                            for x in (vv if isinstance(vv, list) else [vv] if vv else []):
                                ref = x.get("acteurRef")
                                info = people.get(ref) or [ref, "", ""]
                                mem.append(("FR:%s" % ref, info[0], gname or groups.get(info[1], ""), pos, info[2]))
                    dc = ((s.get("syntheseVote") or {}).get("decompte")) or {}
                    obj = (s.get("objet") or {})
                    self.save_vote({"id": vid, "cc": "FR", "chamber": "A", "date": s.get("dateScrutin") or "",
                                    "title": (obj.get("libelle") or s.get("titre") or "").strip(),
                                    "question": ((s.get("typeVote") or {}).get("libelleTypeVote") or ""),
                                    "result": {"adopté": "Adopted", "rejeté": "Rejected"}.get((s.get("sort") or {}).get("code"), (s.get("sort") or {}).get("code") or ""),
                                    "yes": dc.get("pour"), "no": dc.get("contre"), "abstain": dc.get("abstentions"), "absent": dc.get("nonVotants"),
                                    "bill": ((obj.get("dossierLegislatif") or {}).get("dossierRef")) or "",
                                    "url": "https://www.assemblee-nationale.fr/dyn/%s/scrutins/%s" % (leg, s.get("numero"))}, mem)
            self._ok("France votes", True)
        except (self.FetchError, zipfile.BadZipFile, OSError, ValueError, KeyError, TypeError, AttributeError) as e:
            self._ok("France votes", False, str(e))

    # ================================================================== SPAIN
    def pull_es(self):
        try:
            page = self.get("https://www.congreso.es/es/opendata/votaciones", timeout=60)
            links = sorted(set(re.findall(r'href="(/webpublica/opendata/votaciones/[^"]+?\.json)"', page)))
            P = {"Sí": "Y", "No": "N", "Abstención": "A", "No vota": "X"}
            got = 0
            for l in links:
                m = re.search(r"Sesion(\d+)/(\d{8})/Votacion(\d+)", l)
                if not m:
                    continue
                leg = (re.search(r"Leg(\d+)", l) or [None, "15"])[1]
                vid = "ES-%s-%s-%s" % (leg, m.group(1), m.group(3))
                if self.have(vid) or self._stop():
                    continue
                try:
                    d = self.getj("https://www.congreso.es" + l, timeout=40)
                except self.FetchError:
                    continue
                inf, tot = d.get("informacion") or {}, d.get("totales") or {}
                mem = [("ES:%s" % slugify(x.get("diputado")), nice_name(x.get("diputado") or ""), x.get("grupo") or "", P.get(x.get("voto"), "O"), "")
                       for x in d.get("votaciones") or []]
                dt = m.group(2)
                self.save_vote({"id": vid, "cc": "ES", "chamber": "C", "date": "%s-%s-%s" % (dt[:4], dt[4:6], dt[6:]),
                                "title": (inf.get("textoExpediente") or "").strip(), "question": " · ".join(x for x in (inf.get("titulo"), inf.get("tituloSubGrupo"), inf.get("textoSubGrupo")) if x),
                                "yes": tot.get("afavor"), "no": tot.get("enContra"), "abstain": tot.get("abstenciones"), "absent": tot.get("noVotan"),
                                "url": "https://www.congreso.es" + l,
                                "kind": "assent" if (tot.get("asentimiento") or "") == "Sí" else ""}, mem if mem else None)
                got += 1
                time.sleep(0.3)
            self._ok("Spain votes", True, "%d new" % got)
        except (self.FetchError, KeyError, TypeError) as e:
            self._ok("Spain votes", False, str(e))

    # ================================================================== lazy detail (names behind a vote)
    def detail(self, vid):
        """Fetch who voted how for a vote we only have the totals for. Returns True if it worked."""
        v = self.q("SELECT * FROM votes WHERE id=?", (vid,), one=True)
        if not v:
            return False
        if v["detail"]:
            return True
        cc = v["cc"]
        v = dict(v)
        v["by_party"] = None
        ex = json.loads(v.get("extra") or "{}")
        try:
            if cc == "PL":
                d = self.getj("https://api.sejm.gov.pl/sejm/term%s/votings/%s/%s" % (ex.get("term"), ex.get("sitting"), ex.get("n")), timeout=60)
                mps = self.kv("pl_mps", {}) or {}
                P = {"YES": "Y", "NO": "N", "ABSTAIN": "A", "ABSENT": "X", "VOTE_VALID": "O"}
                mem = [("PL:%s" % x.get("MP"), ((mps.get(str(x.get("MP"))) or [""])[0]) or ("%s %s" % (x.get("firstName", ""), x.get("lastName", ""))).strip(),
                        x.get("club") or "", P.get(x.get("vote"), "O"), (mps.get(str(x.get("MP"))) or ["", "", ""])[2]) for x in d.get("votes") or []]
            elif cc == "BR":
                d = self.getj("https://dadosabertos.camara.leg.br/api/v2/votacoes/%s/votos" % vid[3:], timeout=60)
                P = {"Sim": "Y", "Não": "N", "Abstenção": "A"}
                mem = [("BR:%s" % (x.get("deputado_") or {}).get("id"), (x.get("deputado_") or {}).get("nome") or "", (x.get("deputado_") or {}).get("siglaPartido") or "",
                        P.get(x.get("tipoVoto"), "O"), (x.get("deputado_") or {}).get("siglaUf") or "") for x in d.get("dados") or []]
                if not mem:
                    v["kind"] = "symbolic"
            elif cc == "CH":
                d = self.getj("https://ws.parlament.ch/odata.svc/Voting?$top=300&$filter=Language%%20eq%%20'EN'%%20and%%20IdVote%%20eq%%20%s&$format=json" % vid[3:], timeout=60)
                mem = []
                for x in self._odata(d):
                    dt = (x.get("DecisionText") or "").lower()
                    pos = "Y" if dt in ("ja", "yes", "oui") else "N" if dt in ("nein", "no", "non") else "A" if dt.startswith(("enth", "abst")) else "X"
                    mem.append(("CH:%s" % x.get("PersonNumber"), "%s %s" % (x.get("FirstName", ""), x.get("LastName", "")),
                                x.get("ParlGroupNameAbbreviation") or x.get("ParlGroupName") or "", pos, x.get("CantonName") or ""))
                if mem:
                    v["date"] = v["date"] or ms_date(self._odata(d)[0].get("VoteEnd"))
            elif cc == "FI":
                d = self.getj("https://avoindata.eduskunta.fi/api/v1/tables/SaliDBAanestysEdustaja/rows?perPage=250&page=0&columnName=AanestysId&columnValue=%s" % vid[3:], timeout=60)
                cols = d.get("columnNames") or []
                P = {"jaa": "Y", "ei": "N", "tyhjää": "A", "poissa": "X"}
                mem = []
                for r in d.get("rowData") or []:
                    x = dict(zip(cols, r))
                    mem.append(("FI:%s" % (x.get("EdustajaHenkiloNumero") or "").strip(), ("%s %s" % ((x.get("EdustajaEtunimi") or "").strip(), (x.get("EdustajaSukunimi") or "").strip())).strip(),
                                (x.get("EdustajaRyhmaLyhenne") or "").strip(), P.get((x.get("EdustajaAanestys") or "").strip().lower(), "O"), ""))
            elif cc == "DK":
                url = "https://oda.ft.dk/api/Stemme?$filter=afstemningid%%20eq%%20%s&$expand=Akt%%C3%%B8r&$top=200&$format=json" % vid[3:]
                P = {1: "Y", 2: "N", 3: "X", 4: "A"}
                mem = []
                for _ in range(4):
                    d = self.getj(url, timeout=60)
                    for x in d.get("value") or []:
                        a = x.get("Aktør") or {}
                        bio = a.get("biografi") or ""
                        pm = re.search(r"<title>[^<]*\(([^)]+)\)</title>", bio) or re.search(r"<partyShortname>([^<]+)<", bio)
                        mem.append(("DK:%s" % x.get("aktørid"), a.get("navn") or "", pm.group(1) if pm else "", P.get(x.get("typeid"), "O"), ""))
                    url = d.get("odata.nextLink") or d.get("@odata.nextLink")
                    if not url:
                        break
            elif cc == "EE":
                d = self.getj("https://api.riigikogu.ee/api/votings/%s?lang=EN" % vid[3:], timeout=60)
                P = {"POOLT": "Y", "VASTU": "N", "ERAPOOLETU": "A", "PUUDUB": "X", "KOHAL": "X"}
                mem = [("EE:%s" % x.get("uuid"), x.get("fullName") or "", re.sub(r"\s+Parliamentary Group$", "", (x.get("faction") or {}).get("name") or ""),
                        P.get((x.get("decision") or {}).get("code"), "O"), "") for x in d.get("voters") or []]
            else:
                return False
        except (self.FetchError, KeyError, TypeError, AttributeError, ValueError):
            return False
        self.save_vote(v, mem)
        return True

    # ================================================================== reading (API for the page)
    def overview(self):
        out = []
        for cc, (name, chambers, note) in COUNTRIES.items():
            r = self.q("SELECT COUNT(*) n, MAX(date) last, SUM(detail) d FROM votes WHERE cc=?", (cc,), one=True)
            b = self.q("SELECT COUNT(*) n FROM bills WHERE cc=?", (cc,), one=True)
            out.append({"cc": cc, "name": name, "chambers": chambers, "note": note, "votes": r["n"] or 0, "last": r["last"] or "",
                        "named": r["d"] or 0, "bills": b["n"] or 0, "money": cc == "US", "exec": cc == "US"})
        e = self.q("SELECT COUNT(*) n FROM execs", one=True)
        st = {k: {"ok": v[0], "at": v[1], "note": v[2]} for k, v in self.status.items()}
        cur = None
        if self.current:
            cur = {"job": JOB_NAMES.get(self.current[0], self.current[0]), "since": self.current[1]}
        return {"countries": out, "execs": e["n"] or 0, "status": st, "stages": STAGES, "working_on": cur,
                "keys": {"fec": bool(self.settings.get("fec_key")), "congress": bool(self.settings.get("congress_key")), "openstates": bool(self.settings.get("openstates_key")), "tvfy": bool(self.settings.get("tvfy_key"))}, "more": self.more_overview()}

    def _vote_row(self, r):
        d = dict(r)
        d["by_party"] = json.loads(d.get("by_party") or "{}")
        d["extra"] = json.loads(d.get("extra") or "{}")
        return d

    def votes(self, cc, chamber="", q="", offset=0, bill=""):
        args, w = [cc], ["cc=?"]
        if chamber:
            w.append("chamber=?")
            args.append(chamber)
        if bill:
            w.append("bill=?")
            args.append(bill)
        if q:
            w.append("(title LIKE ? OR question LIKE ? OR bill LIKE ?)")
            args += ["%" + q + "%"] * 3
        rows = self.q("SELECT id, cc, chamber, date, title, question, result, yes, no, abstain, absent, bill, url, detail, kind FROM votes WHERE "
                      + " AND ".join(w) + " ORDER BY date DESC, id DESC LIMIT 60 OFFSET ?", args + [int(offset or 0)])
        return {"votes": [dict(r) for r in rows]}

    def vote(self, vid):
        r = self.q("SELECT * FROM votes WHERE id=?", (vid,), one=True)
        if not r:
            return {"error": "not found"}
        if not r["detail"] and r["cc"] not in ("US", "GB", "EU", "CA", "IE", "FR", "DE", "NL", "ES"):
            if self.detail(vid):
                r = self.q("SELECT * FROM votes WHERE id=?", (vid,), one=True)
        v = self._vote_row(r)
        v["members"] = [dict(m) for m in self.q("SELECT member, name, party, pos FROM mvotes WHERE vote_id=? ORDER BY party, name", (vid,))]
        if v["bill"]:
            b = self.q("SELECT id, num, title, stage, stage_text FROM bills WHERE id=?", (v["bill"],), one=True)
            v["bill_info"] = dict(b) if b else None
        v["country"] = COUNTRIES.get(v["cc"], ("", {}, ""))[0]
        v["chamber_name"] = COUNTRIES.get(v["cc"], ("", {}, ""))[1].get(v["chamber"], "")
        if v["cc"].startswith("US-"):     # a state legislature (Open States)
            v["country"] = US_STATES.get(v["cc"][3:], v["cc"][3:]) + " legislature"
            v["chamber_name"] = {"U": "State Senate", "L": "State House / Assembly"}.get(v["chamber"], "")
        return v

    def members(self, cc, q="", chamber=""):
        if cc == "US":
            out = []
            for p in self.us_people().values():
                if chamber and p["chamber"] != chamber:
                    continue
                if q and q.lower() not in (p["name"] + " " + p["state"] + " " + US_STATES.get(p["state"], "")).lower():
                    continue
                out.append({"key": "US:" + p["bio"], "name": p["name"], "party": p["party"], "chamber": p["chamber"],
                            "area": p["state"] + ("-%s" % p["district"] if p.get("district") not in (None, "") else "")})
            out.sort(key=lambda x: (x["chamber"], x["area"], x["name"]))
            return {"members": out}
        args, w = [cc], ["cc=?"]
        if chamber:
            w.append("chamber=?")
            args.append(chamber)
        if q:
            w.append("(name LIKE ? OR party LIKE ? OR area LIKE ?)")
            args += ["%" + q + "%"] * 3
        rows = [dict(r) for r in self.q("SELECT key, name, party, chamber, area, seen FROM members WHERE " + " AND ".join(w) + " ORDER BY seen DESC, name LIMIT 1500", args)]
        newest = rows[0]["seen"] if rows else ""
        try:
            cut = (datetime.date.fromisoformat(newest[:10]) - datetime.timedelta(days=400)).isoformat()
            out = [r for r in rows if (r["seen"] or "") >= cut]
        except ValueError:
            out = rows
        out.sort(key=lambda x: (x["party"] or "", x["name"]))
        return {"members": out}

    # ---- the watchlist: bills and lawmakers you've pinned; Archie tells you when they move
    def _snap(self, kind, xid):
        if kind in ("case", "committee"):
            return self.more_snap(kind, xid)
        if kind == "bill":
            b = self.q("SELECT stage, stage_text, latest_date, latest_text FROM bills WHERE id=?", (xid,), one=True)
            return dict(b) if b else {}
        r = self.q("""SELECT v.date, v.id FROM mvotes m JOIN votes v ON v.id=m.vote_id WHERE m.member=? ORDER BY v.date DESC, v.id DESC LIMIT 1""", (xid,), one=True)
        n = self.q("SELECT COUNT(*) n FROM mvotes WHERE member=?", (xid,), one=True)["n"]
        t = self.q("SELECT COUNT(*) n FROM trades WHERE who=?", (xid,), one=True)["n"]
        return {"last_date": r["date"] if r else "", "last_id": r["id"] if r else "", "n": n, "trades": t}

    def watch_set(self, b):
        kind, xid = b.get("kind"), b.get("id")
        if kind not in ("bill", "member", "case", "committee") or not xid:
            return {"error": "bad request"}
        if b.get("on"):
            self.x("INSERT OR REPLACE INTO watch(kind, id, label, cc, added, snap) VALUES(?,?,?,?,?,?)",
                   (kind, xid, (b.get("label") or "")[:200], b.get("cc") or ("US" if kind in ("case", "committee") else xid.split("-")[0].split(":")[0]), _now(), json.dumps(self._snap(kind, xid))))
        else:
            self.x("DELETE FROM watch WHERE kind=? AND id=?", (kind, xid))
        return {"ok": True, "watching": bool(b.get("on"))}

    def watching(self, kind="", xid=""):
        if kind and xid:
            return {"watching": bool(self.q("SELECT 1 FROM watch WHERE kind=? AND id=?", (kind, xid), one=True))}
        items = []
        for w in self.q("SELECT * FROM watch ORDER BY added DESC"):
            d = dict(w)
            if w["kind"] == "bill":
                b = self.q("SELECT num, title, stage, stage_text, latest_date, latest_text, cc FROM bills WHERE id=?", (w["id"],), one=True)
                d["now"] = dict(b) if b else None
            elif w["kind"] in ("case", "committee"):
                d["now"] = self.more_label(w)
            else:
                d["now"] = self._snap("member", w["id"])
                last = self.q("""SELECT v.id, v.date, v.title, v.question, m.pos FROM mvotes m JOIN votes v ON v.id=m.vote_id WHERE m.member=?
                                 ORDER BY v.date DESC, v.id DESC LIMIT 3""", (w["id"],))
                d["recent"] = [dict(r) for r in last]
            items.append(d)
        ev = [dict(r) for r in self.q("SELECT * FROM watch_events ORDER BY n DESC LIMIT 60")]
        return {"items": items, "events": ev, "unseen": sum(1 for e in ev if not e["seen"])}

    def watch_seen(self):
        self.x("UPDATE watch_events SET seen=1 WHERE seen=0")
        return {"ok": True}

    def check_watch(self):
        """Every half hour: compare each pinned bill or lawmaker with what Archie last saw. Local only; no downloads."""
        P = {"Y": "yes", "N": "no", "A": "abstain", "X": "didn't vote", "O": "other"}
        for w in self.q("SELECT * FROM watch"):
            old = json.loads(w["snap"] or "{}")
            new = self._snap(w["kind"], w["id"])
            if not new:
                continue
            events = []
            if w["kind"] == "bill":
                if new.get("stage") != old.get("stage") and old.get("stage") is not None:
                    events.append(("moved", new.get("stage_text") or "", new.get("latest_text") or ""))
                elif new.get("latest_date") != old.get("latest_date") or new.get("latest_text") != old.get("latest_text"):
                    if old:
                        events.append(("update", new.get("latest_text") or "new action", new.get("latest_date") or ""))
                link = "gov=law:%s:bill:%s" % (w["cc"] or "US", w["id"])
            elif w["kind"] in ("case", "committee"):
                events = self.more_events(w["kind"], w["id"], old, new) if old else []
                link = self.more_link(w["kind"], w["id"])
            else:
                if new.get("n", 0) > old.get("n", 0) and old:
                    rows = self.q("""SELECT v.id, v.date, v.title, v.question, m.pos FROM mvotes m JOIN votes v ON v.id=m.vote_id
                                     WHERE m.member=? AND (v.date > ? OR (v.date = ? AND v.id != ?)) ORDER BY v.date, v.id LIMIT 20""",
                                  (w["id"], old.get("last_date") or "", old.get("last_date") or "", old.get("last_id") or ""))
                    week = (_today() - datetime.timedelta(days=7)).isoformat()
                    rows = [r for r in rows if (r["date"] or "") >= week]     # old votes arriving in a backfill aren't news
                    for r in rows[-5:]:
                        events.append(("vote", "voted %s: %s" % (P.get(r["pos"], r["pos"]), r["title"] or r["question"] or ""), r["date"]))
                if "trades" in old and new.get("trades", 0) > old.get("trades", 0):
                    T = self.q("SELECT ticker, asset, tx, filed FROM trades WHERE who=? ORDER BY rowid DESC LIMIT ?", (w["id"], new["trades"] - old.get("trades", 0)))
                    T = [t for t in T if (t["filed"] or "") >= (_today() - datetime.timedelta(days=14)).isoformat()]   # backfilled old reports aren't news
                if "trades" in old and new.get("trades", 0) > old.get("trades", 0) and T:
                    names = list(dict.fromkeys((t["ticker"] or t["asset"][:30]) for t in T))
                    events.append(("trade", "reported %d new stock trade%s: %s" % (len(T), "" if len(T) == 1 else "s", ", ".join(names[:6])), ""))
                link = "gov=law:%s:member:%s" % ((w["id"].split(":")[0]), w["id"])
            for what, detail, extra in events:
                self.x("INSERT INTO watch_events(at, kind, id, label, what, detail, link) VALUES(?,?,?,?,?,?,?)",
                       (_now(), w["kind"], w["id"], w["label"], what, (detail + (" (" + extra + ")" if extra and what != "vote" else ""))[:400], link))
            if events:     # one notification per person or bill per check, not one per vote
                body = events[-1][1] if len(events) == 1 else "%d updates; latest: %s" % (len(events), events[-1][1])
                try:
                    self.svc._alert("watch:%s:%s" % (w["id"], _now() // 600), "Watching · " + (w["label"] or w["id"])[:80], body[:200], link)
                except Exception:
                    pass
            if new != old:
                self.x("UPDATE watch SET snap=? WHERE kind=? AND id=?", (json.dumps(new), w["kind"], w["id"]))
        self.x("DELETE FROM watch_events WHERE at < ?", (_now() - 60 * 86400,))

    # ---- a person from the governments directory: find whatever the record has on them
    @staticmethod
    def _norm(n):
        n = re.sub(r"\b([a-z])\.\s?([a-z])\.", r"\1\2", unicodedata.normalize("NFD", (n or "").lower()))   # "J.D." -> "jd"
        n = "".join(ch for ch in n if unicodedata.category(ch) != "Mn")
        n = re.sub(r"\b(sir|dame|dr|mr|mrs|ms|jr|sr|iii|ii|iv|hon|lord|baroness|baron)\b\.?", " ", n)
        return [t for t in re.split(r"[^a-z0-9]+", n) if len(t) > 1 or False]

    DEPT = [(r"secretary of state$", "State Department"), (r"treasury", "Treasury"), (r"secretary of (war|defense)", "Defense Department"),
            (r"attorney general", "Justice Department"), (r"interior", "Interior Department"), (r"agriculture", "Agriculture Department"),
            (r"commerce", "Commerce Department"), (r"labor", "Labor Department"), (r"health and human services", "Health and Human Services"),
            (r"housing and urban", "Housing and Urban Development"), (r"transportation", "Transportation Department"), (r"energy", "Energy Department"),
            (r"education", "Education Department"), (r"veterans", "Veterans Affairs"), (r"homeland security", "Homeland Security"),
            (r"environmental protection", "Environmental Protection Agency"), (r"small business", "Small Business Administration"),
            (r"management and budget", "Management and Budget"), (r"trade representative", "Trade Representative")]

    def person(self, cc, name, title=""):
        cc = (cc or "").upper()
        q = self._norm(name)
        out = {"cc": cc, "name": name, "title": title, "member": None, "confirm": [], "execs": [], "laws": [], "in_record": cc in COUNTRIES}
        if not q:
            return out
        first, last = q[0], q[-1]
        def match(cand):
            t = self._norm(cand)
            return bool(t) and last in t and (first in t or any(x[:1] == first[:1] for x in t[:-1]))
        if cc == "US":
            hits = [p for p in self.us_people().values() if match(p["name"])]
            if hits:
                out["member"] = "US:" + hits[0]["bio"]
            for j in self.q("SELECT name FROM sc_justices"):
                if match(j["name"]):
                    out["justice"] = j["name"]
                    break
        elif cc in COUNTRIES:
            best, bestn = None, -1
            for r in self.q("SELECT key, name FROM members WHERE cc=? AND name LIKE ?", (cc, "%" + last[:4] + "%")):
                if match(r["name"]):
                    n = self.q("SELECT COUNT(*) n FROM mvotes WHERE member=?", (r["key"],), one=True)["n"]
                    if n > bestn:
                        best, bestn = r["key"], n
            if not best:   # accents and transliterations: try every member of that country
                for r in self.q("SELECT key, name FROM members WHERE cc=?", (cc,)):
                    if match(r["name"]):
                        best = r["key"]
                        break
            out["member"] = best
        if cc == "US":
            lastcap = name.split()[-1] if name.split() else ""
            for v in self.q("""SELECT id, date, title, question, result, yes, no, abstain, absent FROM votes WHERE cc='US' AND chamber='S'
                               AND (question LIKE '%Nomination%' OR title LIKE 'Confirmation%' OR question LIKE '%Cloture%') AND title LIKE ? ORDER BY date DESC LIMIT 10""",
                               ("%" + lastcap + "%",)):
                if match(re.sub(r",.*", "", re.sub(r"^[^:]*:\s*", "", v["title"]))) or last in self._norm(v["title"]):
                    out["confirm"].append(dict(v))
            tl = (title or "").lower()
            if re.search(r"\bpresident of the united states\b|^president$", tl):
                out["execs"] = [dict(r) for r in self.q("SELECT id, kind, title, date, signed, number FROM execs WHERE kind NOT LIKE 'Major%' ORDER BY COALESCE(NULLIF(signed,''), date) DESC LIMIT 40")]
                out["laws"] = [dict(r) for r in self.q("SELECT id, num, title, enacted, latest_date FROM bills WHERE cc='US' AND stage=6 AND (num LIKE 'H.R.%' OR num LIKE 'S.%' OR num LIKE 'H.J.Res.%' OR num LIKE 'S.J.Res.%') AND enacted != '' ORDER BY latest_date DESC LIMIT 40")]
                out["role"] = "president"
            else:
                for rx, dept in self.DEPT:
                    if re.search(rx, tl):
                        out["dept"] = dept
                        out["execs"] = [dict(r) for r in self.q("SELECT id, kind, title, date, signed, number, agency FROM execs WHERE agency LIKE ? ORDER BY date DESC LIMIT 25", ("%" + (dept if dept.startswith("State") else dept.split()[0]) + "%",))]
                        break
        return out

    def find(self, q):
        """Lawmakers in any parliament whose name matches (for the directory's search box)."""
        q = (q or "").strip()
        if len(q) < 3:
            return {"people": []}
        nq = " ".join(self._norm(q))
        out = []
        for p in self.us_people().values():
            if nq in " ".join(self._norm(p["name"])):
                out.append({"key": "US:" + p["bio"], "name": p["name"], "party": p["party"], "cc": "US",
                            "area": ("U.S. Senator, " if p["chamber"] == "S" else "U.S. Representative, ") + p["state"] + ("-%s" % p["district"] if p.get("district") not in (None, "") else "")})
        for r in self.q("SELECT key, cc, name, party, area, chamber FROM members WHERE name LIKE ? AND cc != 'US' LIMIT 60", ("%" + q + "%",)):
            ch = COUNTRIES.get(r["cc"], ("", {}, ""))[1].get(r["chamber"], "")
            out.append({"key": r["key"], "name": r["name"], "party": r["party"], "cc": r["cc"], "area": ", ".join(x for x in (ch, r["area"]) if x)})
        return {"people": out[:30]}

    def member(self, key):
        cc = key.split(":", 1)[0]
        prof = {"key": key, "cc": cc}
        if cc == "US":
            p = self.us_people().get(key[3:]) or {}
            prof.update({"name": p.get("name", ""), "party": p.get("party", ""), "chamber": p.get("chamber", ""), "state": p.get("state", ""),
                         "district": p.get("district"), "since": p.get("start", ""), "term_end": p.get("term_end", ""), "url": p.get("url", ""),
                         "phone": p.get("phone", ""), "terms": p.get("terms"), "rank": p.get("rank", ""), "state_name": US_STATES.get(p.get("state", ""), "")})
        else:
            m = self.q("SELECT * FROM members WHERE key=?", (key,), one=True)
            if m:
                prof.update({"name": m["name"], "party": m["party"], "chamber": m["chamber"], "area": m["area"], "cc": m["cc"]})
                if (m["cc"] or "").startswith("US-"):     # a state lawmaker (Open States)
                    prof["area"] = US_STATES.get(m["cc"][3:], m["cc"][3:]) + " " + {"U": "State Senate", "L": "State House / Assembly"}.get(m["chamber"], "legislature")
        rows = self.q("""SELECT v.id, v.date, v.title, v.question, v.result, v.bill, v.by_party, v.chamber, m.pos, m.party FROM mvotes m
                         JOIN votes v ON v.id = m.vote_id WHERE m.member=? ORDER BY v.date DESC, v.id DESC LIMIT 2000""", (key,))
        rec, with_party, against_party, missed, counted = [], 0, 0, 0, 0
        for r in rows:
            bp = json.loads(r["by_party"] or "{}").get(r["party"] or "") or {}
            maj = "Y" if bp.get("Y", 0) > bp.get("N", 0) else "N" if bp.get("N", 0) > bp.get("Y", 0) else ""
            if r["pos"] == "X":
                missed += 1
            if r["pos"] in ("Y", "N") and maj:
                counted += 1
                if r["pos"] == maj:
                    with_party += 1
                else:
                    against_party += 1
            if len(rec) < 150:
                rec.append({"id": r["id"], "date": r["date"], "title": r["title"], "question": r["question"], "result": r["result"],
                            "pos": r["pos"], "party_pos": maj, "bill": r["bill"], "chamber": r["chamber"]})
        prof["record"] = rec
        prof["stats"] = {"votes": len(rows), "missed": missed, "with_party": with_party, "against_party": against_party, "counted": counted,
                         "first": rows[-1]["date"] if rows else "", "last": rows[0]["date"] if rows else ""}
        prof["sponsored"] = [dict(b) for b in self.q("SELECT id, num, title, stage, stage_text, latest_date FROM bills WHERE sponsor_key=? ORDER BY latest_date DESC LIMIT 60", (key,))]
        if not prof.get("name") and rows:
            prof["name"] = self.q("SELECT name FROM mvotes WHERE member=? LIMIT 1", (key,), one=True)["name"]
        return prof

    def bills(self, cc, q="", stage="", offset=0, sort="latest"):
        args, w = [cc], ["cc=?"]
        if q:
            w.append("(title LIKE ? OR num LIKE ? OR sponsor LIKE ? OR subject LIKE ? OR summary LIKE ?)")
            args += ["%" + q + "%"] * 5
        if stage not in ("", None):
            if stage == "moving":
                w.append("stage BETWEEN 2 AND 5")
            elif stage == "law":
                w.append("stage = 6")
            elif stage == "dead":
                w.append("stage = -1")
            else:
                w.append("stage = ?")
                args.append(int(stage))
        order = {"latest": "latest_date DESC", "introduced": "introduced DESC", "stage": "stage DESC, latest_date DESC"}.get(sort, "latest_date DESC")
        rows = self.q("SELECT id, num, title, sponsor, party, introduced, stage, stage_text, latest_date, latest_text, enacted, subject, chamber, url FROM bills WHERE "
                      + " AND ".join(w) + " ORDER BY " + order + " LIMIT 80 OFFSET ?", args + [int(offset or 0)])
        counts = {r["stage"]: r["n"] for r in self.q("SELECT stage, COUNT(*) n FROM bills WHERE cc=? GROUP BY stage", (cc,))}
        return {"bills": [dict(r) for r in rows], "counts": counts}

    def bill(self, bid):
        r = self.q("SELECT * FROM bills WHERE id=?", (bid,), one=True)
        if not r:
            return {"error": "not found"}
        if r["cc"] == "GB" and not json.loads(r["extra"] or "{}").get("actions"):
            try:
                self._gb_bill_detail(bid)
                r = self.q("SELECT * FROM bills WHERE id=?", (bid,), one=True)
            except (self.FetchError, KeyError, TypeError, ValueError):
                pass
        b = dict(r)
        b["extra"] = json.loads(b.get("extra") or "{}")
        b["votes"] = [dict(v) for v in self.q("SELECT id, date, chamber, question, result, yes, no FROM votes WHERE bill=? ORDER BY date DESC", (bid,))]
        s = self.q("SELECT text FROM summaries WHERE key=?", ("bill:" + bid,), one=True)
        b["plain"] = s["text"] if s else ""
        return b

    def execs(self, kind="", q="", offset=0, xid=""):
        if xid:
            return {"items": [dict(r) for r in self.q("SELECT * FROM execs WHERE id=?", (xid,))]}
        args, w = [], ["1=1"]
        if kind == "eo":
            w.append("kind='Executive Order'")
        elif kind == "rules":
            w.append("kind LIKE 'Major%'")
        elif kind == "other":
            w.append("kind NOT LIKE 'Major%' AND kind != 'Executive Order'")
        if q:
            w.append("(title LIKE ? OR abstract LIKE ? OR agency LIKE ?)")
            args += ["%" + q + "%"] * 3
        rows = self.q("SELECT * FROM execs WHERE " + " AND ".join(w) + " ORDER BY date DESC LIMIT 80 OFFSET ?", args + [int(offset or 0)])
        return {"items": [dict(r) for r in rows]}

    def calendar(self):
        rows = self.q("SELECT * FROM cal WHERE date >= ? ORDER BY date, time LIMIT 800", ((_today()).isoformat(),))
        elections = []
        try:   # national elections with exact dates, from Archie's world calendar (Wikidata)
            for it in self.svc.store.kv_get("worldcal", []) or []:
                if it.get("kind") == "election" and (it.get("date") or "") >= _today().isoformat():
                    elections.append({"date": it["date"], "title": it.get("title", ""), "where": it.get("where", ""), "url": it.get("url", "")})
        except Exception:
            pass
        return {"events": [dict(r) for r in rows], "elections": elections, "status": {k: v[0] for k, v in self.status.items() if "calendar" in k.lower() or "hearing" in k.lower() or "floor" in k.lower()}}

    # ---- plain-English summaries (Archie's own model)
    def summary(self, kind, xid, force=False):
        key = "%s:%s" % (kind, xid)
        if not force:
            r = self.q("SELECT text FROM summaries WHERE key=?", (key,), one=True)
            if r and r["text"]:
                return {"text": r["text"], "cached": True}
        text, label = "", kind
        if kind == "bill":
            b = self.q("SELECT * FROM bills WHERE id=?", (xid,), one=True)
            if not b:
                return {"error": "not found"}
            ex = json.loads(b["extra"] or "{}")
            text = "Title: %s\n%s\nOfficial summary: %s" % (b["title"], ("Long title: " + ex["long_title"]) if ex.get("long_title") else "", (b["summary"] or "")[:5000])
            label = "bill (proposed law)"
        elif kind == "vote":
            v = self.q("SELECT * FROM votes WHERE id=?", (xid,), one=True)
            if not v:
                return {"error": "not found"}
            ex = json.loads(v["extra"] or "{}")
            text = "Parliament: %s\nWhat was voted on: %s\nQuestion: %s\nResult: %s\n%s" % (COUNTRIES.get(v["cc"], ("",))[0], v["title"], v["question"], v["result"],
                                                                                      (ex.get("intro") or ex.get("summary") or "")[:3000])
            label = "vote"
        elif kind == "case":
            c = self.q("SELECT * FROM sc_cases WHERE id=?", (xid,), one=True)
            if not c:
                return {"error": "not found"}
            text = "Supreme Court case: %s (No. %s)\nQuestion: %s\nFacts: %s\nDecision: %s" % (c["name"], c["docket"], c["question"] or "", (c["facts"] or "")[:3000], (c["conclusion"] or "")[:3000])
            label = "Supreme Court case"
        elif kind == "exec":
            e = self.q("SELECT * FROM execs WHERE id=?", (xid,), one=True)
            if not e:
                return {"error": "not found"}
            body = ""
            for fld in ("raw_text_url", "body_html_url"):
                try:
                    j = self.getj("https://www.federalregister.gov/api/v1/documents/%s.json?fields[]=%s" % (xid, fld), timeout=40)
                    if j.get(fld):
                        body = strip_html(self.get(j[fld], timeout=60))[:6000]
                        break
                except self.FetchError:
                    continue
            text = "%s: %s\n%s\n%s" % (e["kind"], e["title"], e["abstract"] or "", body)
            label = e["kind"].lower()
        elif kind == "localdoc":
            got = self.local_summary_text(xid)
            if not got:
                return {"error": "Open the document first so Archie can read it (scanned pages have no text to explain)."}
            text, label = got
        else:
            return {"error": "unknown kind"}
        if len(text.strip()) < 30:
            return {"error": "There isn't enough text to summarize."}
        with self._sum_lock:
            try:
                from archie_brain import quick_chat
                ans = quick_chat(self.svc.get_model(), SUM_PROMPT.format(kind=label, text=text), max_tokens=260, timeout=180)
            except Exception as e:
                return {"error": "Couldn't reach Archie's model: %s" % e}
        ans = (ans or "").strip()
        if ans:
            self.x("INSERT OR REPLACE INTO summaries(key, text, at) VALUES(?,?,?)", (key, ans, _now()))
        return {"text": ans, "cached": False}

    # ---- your representatives
    def states(self):
        if self._states is None:
            self._states = (self._json_file("state_legislators.json") or {}).get("states", {})
        return self._states

    def myreps(self, b=None):
        matched = ""      # the address Census matched: shown once, never saved
        if b:
            home = {}
            if b.get("address"):
                try:
                    j = self.getj("https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address=%s&benchmark=Public_AR_Current&vintage=Current_Current&layers=all&format=json"
                                  % urllib.parse.quote(b["address"]), timeout=60)
                    ms = (j.get("result") or {}).get("addressMatches") or []
                except self.FetchError as e:
                    return {"error": "Couldn't reach the Census address lookup (%s). You can pick your state and districts instead." % e}
                if not ms:
                    return {"error": "The Census lookup didn't recognize that address. Try the full street address with town and ZIP, or pick your districts below."}
                g = ms[0].get("geographies") or {}
                def layer(rx):
                    for k, v in g.items():
                        if re.search(rx, k) and v:
                            return v[0]
                    return {}
                st = layer(r"^States$")
                cd = layer(r"Congressional Districts")
                up = layer(r"Legislative Districts - Upper")
                lo = layer(r"Legislative Districts - Lower")
                cdv = next((v for k, v in cd.items() if re.match(r"^CD\d+$", k)), "")
                matched = ms[0].get("matchedAddress", "")
                home = {"state": st.get("STUSAB") or FIPS_STATE.get(st.get("STATE", ""), ""), "cd": str(_int(cdv)) if cdv not in ("", None) else "",
                        "upper": (up.get("SLDU") or "").lstrip("0") or up.get("BASENAME", ""), "lower": (lo.get("SLDL") or "").lstrip("0") or lo.get("BASENAME", ""),
                        "upper_name": up.get("NAME", ""), "lower_name": lo.get("NAME", "")}
            else:
                home = {k: str(b.get(k) or "") for k in ("state", "cd", "upper", "lower")}
            self.save_settings({"home": home})
        home = self.settings.get("home") or {}
        if not home.get("state"):
            return {"home": {}, "states": US_STATES}
        st = home["state"]
        fed = []
        for p in self.us_people().values():
            if p["state"] != st:
                continue
            if p["chamber"] == "S" or (p["chamber"] == "H" and (str(p.get("district")) == str(home.get("cd")) or (p.get("district") in (0, None) and home.get("cd") in ("0", "98", "")))):
                fed.append({"key": "US:" + p["bio"], "name": p["name"], "party": p["party"], "chamber": p["chamber"],
                            "office": ("U.S. Senator" + (" (%s)" % p["rank"] if p.get("rank") else "")) if p["chamber"] == "S" else "U.S. Representative, district %s" % (p.get("district") or "at large"),
                            "phone": p.get("phone", ""), "url": p.get("url", ""), "since": p.get("start", ""), "term_end": p.get("term_end", "")})
        fed.sort(key=lambda x: (x["chamber"] != "S", x["name"]))
        stl = []
        for x in self.states().get(st, []):
            d = (x.get("d") or "").lstrip("0")
            if (x.get("c") == "upper" and d and d == (home.get("upper") or "").lstrip("0")) or (x.get("c") in ("lower", "legislature") and d and d == (home.get("lower") or "").lstrip("0")):
                stl.append({"name": x["n"], "party": x.get("p", ""), "chamber": x.get("c"), "district": x.get("d"), "email": x.get("e", ""),
                            "phone": x.get("ph", ""), "url": x.get("u", "")})
        return {"home": home, "federal": fed, "state": stl, "state_name": US_STATES.get(st, st), "states": US_STATES,
                "matched": matched}
