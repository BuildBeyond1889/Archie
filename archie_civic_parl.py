"""Archie World: lawmaking, part four. Six more parliaments.

Italy (Camera dei deputati, linked open data), Lithuania (Seimas), Ukraine (Verkhovna Rada), Chile (Cámara de
Diputados), the Czech Republic (Poslanecká sněmovna) and Australia (both houses, through They Vote For You, which
needs a free key).

Each one is the official public record of who voted how. No scores, ratings or labels on anyone.
"""
import csv
import datetime
import io
import json
import os
import re
import time
import urllib.parse
import zipfile

PARL_JOBS = {"civ_it": "Italy", "civ_lt": "Lithuania", "civ_ua2": "Ukraine", "civ_cl": "Chile", "civ_cz": "the Czech Republic (a few MB)",
             "civ_au": "Australia (They Vote For You)"}

PARL_COUNTRIES = {
    "IT": ("Italy", {"C": "Chamber of Deputies"}, "every electronic vote, by name"),
    "LT": ("Lithuania", {"S": "Seimas"}, "every recorded vote, by name (some are agreed by consensus with no names)"),
    "UA": ("Ukraine", {"R": "Verkhovna Rada"}, "every roll-call vote, by name"),
    "CL": ("Chile", {"C": "Chamber of Deputies"}, "every electronic vote, by name"),
    "CZ": ("Czech Republic", {"P": "Chamber of Deputies"}, "every vote, by name (from the Chamber's weekly open-data files)"),
    "AU": ("Australia", {"R": "House of Representatives", "S": "Senate"}, "every division, by name (from They Vote For You; needs a free key)"),
}

IT_GROUPS = {"FDI": "Fratelli d'Italia", "PD-IDP": "Partito Democratico", "M5S": "Movimento 5 Stelle", "LEGA": "Lega",
             "FI-PPE": "Forza Italia", "AVS": "Alleanza Verdi e Sinistra", "AZ-PER-RE": "Azione", "APERRE": "Azione",
             "IV-C-RE": "Italia Viva", "NM-M-C": "Noi Moderati", "MISTO": "Gruppo misto"}
IT_POS = {"favorevole": "Y", "contrario": "N", "astensione": "A", "non ha votato": "X"}
LT_POS = {"už": "Y", "prieš": "N", "susilaikė": "A"}
LT_GROUPS = [(r"^LSDP", "Lietuvos socialdemokratų partija"), (r"^TS-LKD", "Tėvynės sąjunga – Lietuvos krikščionys demokratai"),
             (r"^LS", "Liberalų sąjūdis"), (r"^LVŽ|^LVZ", "Lietuvos valstiečių, žaliųjų ir Krikščioniškų šeimų sąjunga"),
             (r"^DSVL", "Demokratų sąjunga „Vardan Lietuvos“"), (r"^(P?NA)F?$|^NA", "Nemuno aušra"), (r"^MSNG", "Mišri Seimo narių grupė")]
UA_POS = {1: "Y", 2: "N", 3: "A", 4: "X", 0: "X"}
UA_SKL = 9      # the Rada elected in 2019 sits until the next election (none can be held under martial law)
CZ_POS = {"A": "Y", "B": "N", "N": "N", "C": "A", "K": "A", "F": "X", "@": "X", "M": "X", "W": "O"}


def _title(s):
    return " ".join(w[:1].upper() + w[1:].lower() if w.isupper() else w for w in (s or "").split())


def _lt_group(code):
    for pat, name in LT_GROUPS:
        if re.match(pat, code or ""):
            return name
    return code or ""


def _ua_group(name):
    n = re.sub(r"^(Фракція політичної партії|Фракція|Депутатська група|Група)\s*", "", name or "").strip()
    n = re.sub(r"\s*у Верховній Раді України.*$", "", n)
    n = n.replace('""', '"').strip('" ')
    n = re.sub(r'^Партія "', "Партія ", n)
    n = n.replace('"', "")
    return n[:1].upper() + n[1:].lower() if n.isupper() else n


class CivicParl:
    def parl_jobs(self):
        return [("civ_it", 21600, self.pull_it), ("civ_lt", 21600, self.pull_lt), ("civ_ua2", 21600, self.pull_ua),
                ("civ_cl", 21600, self.pull_cl), ("civ_cz", 43200, self.pull_cz), ("civ_au", 21600, self.pull_au)]

    # ================================================================== ITALY (dati.camera.it SPARQL)
    def _sparql(self, q):
        u = "https://dati.camera.it/sparql?" + urllib.parse.urlencode({"query": q, "format": "application/sparql-results+json"})
        d = self.getj(u, timeout=90, headers={"Accept": "application/sparql-results+json"})
        return [{k: v.get("value") for k, v in b.items()} for b in (d.get("results") or {}).get("bindings") or []]

    def pull_it(self):
        P = "PREFIX ocd: <http://dati.camera.it/ocd/> PREFIX dc: <http://purl.org/dc/elements/1.1/> "
        n = 0
        try:
            L = self._sparql(P + "SELECT DISTINCT ?v ?d ?t ?desc ?ty ?ok ?fin ?fav ?con ?ast WHERE { ?v a ocd:votazione; dc:date ?d; dc:title ?t. "
                             "OPTIONAL{?v dc:description ?desc} OPTIONAL{?v dc:type ?ty} OPTIONAL{?v ocd:approvato ?ok} OPTIONAL{?v ocd:votazioneFinale ?fin} "
                             "OPTIONAL{?v ocd:favorevoli ?fav} OPTIONAL{?v ocd:contrari ?con} OPTIONAL{?v ocd:astenuti ?ast} } ORDER BY DESC(?d) LIMIT 300")
            seen = set()
            for r in L:
                if n >= 40 or self._stop():
                    break
                uri = r.get("v") or ""
                if uri in seen:
                    continue
                seen.add(uri)
                vid = "IT-" + uri.rsplit("/", 1)[-1]
                if self.have(vid):
                    continue
                M = self._sparql(P + "SELECT ?dep ?t ?g ?fn ?sn WHERE { ?x ocd:rif_votazione <%s>; dc:type ?t; ocd:rif_deputato ?dep. "
                                 "OPTIONAL{?x ocd:siglaGruppo ?g} OPTIONAL{?dep <http://xmlns.com/foaf/0.1/firstName> ?fn; <http://xmlns.com/foaf/0.1/surname> ?sn} }" % uri)
                mem, got = [], set()
                for m in M:
                    k = "IT:" + (m.get("dep") or "").rsplit("/", 1)[-1].split("_")[0]
                    if k in got:
                        continue
                    got.add(k)
                    g = m.get("g") or ""
                    mem.append((k, _title("%s %s" % (m.get("fn") or "", m.get("sn") or "")).strip(), IT_GROUPS.get(g, g),
                                IT_POS.get((m.get("t") or "").strip().lower(), "O"), ""))
                d = r.get("d") or ""
                q = (r.get("ty") or "").strip()
                if r.get("fin") == "1":
                    q = (q + " · final vote").strip(" ·")
                self.save_vote({"id": vid, "cc": "IT", "chamber": "C", "date": "%s-%s-%s" % (d[:4], d[4:6], d[6:8]) if len(d) >= 8 else d,
                                "title": (r.get("t") or "").replace("Votazione ", "", 1).strip(), "question": q,
                                "result": {"1": "Adopted", "0": "Rejected"}.get(r.get("ok"), ""), "src": "camera",
                                "yes": r.get("fav"), "no": r.get("con"), "abstain": r.get("ast"), "url": uri}, mem)
                n += 1
                time.sleep(0.8)
            self._ok("Italy votes", True, "%d new" % n)
        except (self.FetchError, ValueError, KeyError, TypeError) as e:
            self._ok("Italy votes", False, str(e))

    # ================================================================== LITHUANIA (apps.lrs.lt)
    def pull_lt(self):
        import xml.etree.ElementTree as ET
        n = 0
        done = self.kv("lt_sittings", {}) or {}
        try:
            S = self.get("https://apps.lrs.lt/sip/p2b.ad_seimo_sesijos?ar_visos=T", timeout=60)
            ses = re.findall(r'sesijos_id="(\d+)"[^>]*data_nuo="([\d-]+)"', S)
            ses.sort(key=lambda x: x[1], reverse=True)
            for sid, _ in ses[:2]:
                P = self.get("https://apps.lrs.lt/sip/p2b.ad_seimo_posedziai?sesijos_id=%s" % sid, timeout=60)
                sits = re.findall(r'posėdžio_id="(-?\d+)"[^>]*pradžia="([\d-]+)', P)
                for pid, day in sorted(sits, key=lambda x: x[1], reverse=True):
                    if n >= 60 or self._stop():
                        break
                    if pid in done:
                        continue
                    x = ET.fromstring(self.get("https://apps.lrs.lt/sip/p2b.ad_seimo_posedzio_eiga_full?posedzio_id=%s" % pid, timeout=90).encode("utf-8"))
                    finished = True
                    for q in x.iter("darbotvarkes-klausimas"):
                        for b in q.iter("balsavimas"):
                            bid = b.get("bals_id")
                            if not bid or b.find("iki") is None:
                                continue          # agreed by consensus: no names recorded
                            vid = "LT-" + bid.lstrip("-")
                            if self.have(vid):
                                continue
                            if n >= 60:
                                finished = False
                                break
                            r = self.get("https://apps.lrs.lt/sip/p2b.ad_sp_balsavimo_rezultatai?balsavimo_id=%s" % bid, timeout=60)
                            mem = []
                            for m in re.finditer(r'<IndividualusBalsavimoRezultatas asmens_id="(\d+)" vardas="([^"]*)" pavardė="([^"]*)" frakcija="([^"]*)" kaip_balsavo="([^"]*)"', r):
                                mem.append(("LT:" + m.group(1), "%s %s" % (m.group(2), m.group(3)), _lt_group(m.group(4)), LT_POS.get(m.group(5).lower(), "X"), ""))
                            desc = (b.findtext("aprasas") or "").strip()
                            res = "Adopted" if desc.lower().startswith("pritarta") else "Rejected" if desc.lower().startswith("nepritarta") else ""
                            title = (q.findtext("pavadinimas") or "").strip()
                            dok = q.get("dok_key") or ""
                            self.save_vote({"id": vid, "cc": "LT", "chamber": "S", "date": (b.findtext("nuo") or day)[:10], "title": title,
                                            "question": ("%s: %s" % ((q.findtext("stadija") or "").strip(), desc)).strip(": "), "result": res, "src": "lrs",
                                            "url": "https://e-seimas.lrs.lt/portal/legalAct/lt/TAP/%s" % dok if dok else "https://www.lrs.lt/sip/portal.show?p_r=37067&p_k=1&p_a=sale_bals&p_bals_id=%s" % bid}, mem)
                            n += 1
                            time.sleep(0.5)
                        if not finished:
                            break
                    if finished and day < datetime.date.today().isoformat():
                        done[pid] = 1
                    time.sleep(0.5)
            self.kv_set("lt_sittings", done)
            self._ok("Lithuania votes", True, "%d new" % n)
        except (self.FetchError, ET.ParseError, ValueError) as e:
            self.kv_set("lt_sittings", done)
            self._ok("Lithuania votes", False, str(e))

    # ================================================================== UKRAINE (data.rada.gov.ua)
    def _ua_get(self, url, timeout=60):
        """The Rada's server drops some connections partway through the secure handshake. If that happens,
        try again the way a browser would (an older-style handshake, a browser's name)."""
        try:
            return self.get(url, timeout=timeout)
        except self.FetchError as e:
            if not re.search(r"EOF|SSL|handshake|reset", str(e), re.I):
                raise
        import ssl
        import urllib.request
        ctx = ssl.create_default_context()
        try:
            ctx.load_verify_locations(os.path.join(self.dir, "cacert.pem"))
        except (OSError, ssl.SSLError):
            pass
        ctx.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            pass
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36",
                                                   "Accept": "*/*", "Accept-Language": "uk,en;q=0.8"})
        last = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                    return r.read().decode(r.headers.get_content_charset() or "utf-8", errors="replace")
            except Exception as e:      # noqa: BLE001 - reported to the status page
                last = e
                time.sleep(3)
        raise self.FetchError(str(last)[:150])

    def _ua_people(self):
        path = os.path.join(self.cache, "ua_mps%d.json" % UA_SKL)
        if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 7 * 86400:
            t = self._ua_get("https://data.rada.gov.ua/ogd/mps/skl%d/mps%02d-data.json" % (UA_SKL, UA_SKL), timeout=300)
            with open(path + ".part", "w", encoding="utf-8") as f:
                f.write(t)
            os.replace(path + ".part", path)
        with open(path, encoding="utf-8") as f:
            L = json.load(f)
        return {int(p["rada_id"]): (p.get("full_name") or "", p.get("district_text") or "") for p in L if p.get("rada_id") is not None}

    def pull_ua(self):
        root = "https://data.rada.gov.ua/ogd/zal/ppz/skl%d/" % UA_SKL
        n = 0
        done = self.kv("ua_days", {}) or {}
        try:
            page = self._ua_get("https://data.rada.gov.ua/open/data/chron_ppz-skl%d" % UA_SKL, timeout=60)   # lists each sitting day's file
            days = sorted({"%s-%s-%s" % (m[4:], m[2:4], m[:2]) for m in re.findall(r"/json/(\d{8})\.json", page)}, reverse=True)
            people = self._ua_people()
            fr = {}
            for row in csv.reader(io.StringIO(self._ua_get(root + "plenary_fractions-skl%d.csv" % UA_SKL, timeout=60))):
                if row and row[0].isdigit():
                    fr[int(row[0])] = _ua_group(row[2] if len(row) > 2 else "")
            old = (datetime.date.today() - datetime.timedelta(days=3)).isoformat()
            for d in days[:4]:
                if self._stop() or n >= 120:
                    break
                if done.get(d) and d < old:
                    continue
                J = json.loads(self._ua_get(root + "json/%s%s%s.json" % (d[8:10], d[5:7], d[:4]), timeout=120))
                for q in J.get("question") or []:
                    for ev in q.get("event_question") or []:
                        for r in ev.get("result_event") or []:
                            if not r.get("id_event") or not r.get("result_by_name"):
                                continue
                            vid = "UA-%s" % r["id_event"]
                            if self.have(vid):
                                continue
                            mem = []
                            for x in r["result_by_name"]:
                                pid = x.get("id_mp")
                                nm, area = people.get(int(pid), ("", "")) if pid is not None else ("", "")
                                mem.append(("UA:%s" % pid, nm or "MP %s" % pid, fr.get(x.get("faction"), ""), UA_POS.get(x.get("result"), "O"), area))
                            dt = ev.get("date_event") or ""
                            self.save_vote({"id": vid, "cc": "UA", "chamber": "R", "date": "%s-%s-%s" % (dt[6:10], dt[3:5], dt[:2]) if len(dt) >= 10 else d,
                                            "title": (ev.get("name_event") or "").strip(), "question": "",
                                            "result": "Adopted" if str(r.get("voting_result")) == "1" else "Not adopted", "src": "rada",
                                            "yes": r.get("for"), "no": r.get("against"), "abstain": r.get("abstain"), "absent": r.get("absent"),
                                            "url": "https://w1.c1.rada.gov.ua/pls/radan_gs09/ns_golos?g_id=%s" % r["id_event"]}, mem)
                            n += 1
                done[d] = 1
                time.sleep(2)
            self.kv_set("ua_days", done)
            self._ok("Ukraine votes", True, "%d new" % n)
        except (self.FetchError, ValueError, KeyError, TypeError, OSError) as e:
            self.kv_set("ua_days", done)
            self._ok("Ukraine votes", False, str(e))

    # ================================================================== CHILE (opendata.camara.cl)
    def pull_cl(self):
        import xml.etree.ElementTree as ET
        NS = "{http://opendata.camara.cl/camaradiputados/v1}"
        base = "https://opendata.camara.cl/camaradiputados/WServices/"
        n = 0
        try:
            parties = self.kv("cl_parties", {}) or {}
            if not parties or (self.kv("cl_parties_at", 0) or 0) < time.time() - 7 * 86400:
                x = ET.fromstring(self.get(base + "WSDiputado.asmx/retornarDiputadosPeriodoActual", timeout=90).encode("utf-8"))
                parties = {}
                for dp in x.iter(NS + "DiputadoPeriodo"):
                    dip = dp.find(NS + "Diputado")
                    if dip is None:
                        continue
                    did = dip.findtext(NS + "Id") or ""
                    best, bdate = "", ""
                    for mi in dip.iter(NS + "Militancia"):
                        start = mi.findtext(NS + "FechaInicio") or ""
                        end = mi.find(NS + "FechaTermino")
                        cur = end is None or not (end.text or "").strip()
                        key = ("9" if cur else "0") + start
                        if key >= bdate:
                            bdate, best = key, (mi.findtext(NS + "Partido/" + NS + "Nombre") or "").strip()
                    parties[did] = best
                self.kv_set("cl_parties", parties)
                self.kv_set("cl_parties_at", int(time.time()))
            y = datetime.date.today().year
            for yr in (y, y - 1):
                x = ET.fromstring(self.get(base + "WSLegislativo.asmx/retornarVotacionesXAnno?prmAnno=%d" % yr, timeout=120).encode("utf-8"))
                V = list(x.iter(NS + "Votacion"))
                V.sort(key=lambda e: (e.findtext(NS + "Fecha") or ""), reverse=True)
                for v in V:
                    if n >= 50 or self._stop():
                        break
                    i = v.findtext(NS + "Id") or ""
                    if not i or self.have("CL-" + i):
                        continue
                    d = ET.fromstring(self.get(base + "WSLegislativo.asmx/retornarVotacionDetalle?prmVotacionId=%s" % i, timeout=60).encode("utf-8"))
                    mem = []
                    for vo in d.iter(NS + "Voto"):
                        dip = vo.find(NS + "Diputado")
                        if dip is None:
                            continue
                        did = dip.findtext(NS + "Id") or ""
                        nm = " ".join(filter(None, [(dip.findtext(NS + t) or "").strip() for t in ("Nombre", "ApellidoPaterno", "ApellidoMaterno")]))
                        op = (vo.findtext(NS + "OpcionVoto") or "").strip().lower()
                        pos = "Y" if op.startswith("afirm") else "N" if ("contra" in op or op.startswith("negat")) else "A" if op.startswith("absten") else "X" if op else "O"
                        mem.append(("CL:" + did, nm, parties.get(did, ""), pos, ""))
                    desc = re.sub(r"\s+", " ", v.findtext(NS + "Descripcion") or "").strip()
                    bol = re.search(r"Bolet[ií]n\s*N?°?\s*([\d-]+)", desc)
                    self.save_vote({"id": "CL-" + i, "cc": "CL", "chamber": "C", "date": (v.findtext(NS + "Fecha") or "")[:10], "title": desc,
                                    "question": (v.findtext(NS + "Tipo") or v.findtext(NS + "Quorum") or "").strip(),
                                    "result": {"aprobado": "Adopted", "rechazado": "Rejected"}.get((v.findtext(NS + "Resultado") or "").strip().lower(), (v.findtext(NS + "Resultado") or "").strip()),
                                    "src": "camara.cl", "yes": v.findtext(NS + "TotalSi"), "no": v.findtext(NS + "TotalNo"), "abstain": v.findtext(NS + "TotalAbstencion"),
                                    "url": ("https://www.camara.cl/legislacion/ProyectosDeLey/tramitacion.aspx?prmBOLETIN=%s" % bol.group(1)) if bol else "https://www.camara.cl/legislacion/sala_sesiones/votaciones.aspx"}, mem)
                    n += 1
                    time.sleep(0.6)
                if n >= 50 or V:
                    break      # last year only matters in early January, before this year has votes
            self._ok("Chile votes", True, "%d new" % n)
        except (self.FetchError, ET.ParseError, ValueError) as e:
            self._ok("Chile votes", False, str(e))

    # ================================================================== CZECH REPUBLIC (psp.cz open data, UNL files)
    @staticmethod
    def _unl(z, name):
        with z.open(name) as f:
            for line in io.TextIOWrapper(f, encoding="cp1250", errors="replace"):
                yield line.rstrip("\r\n").split("|")

    def pull_cz(self):
        base = "https://www.psp.cz/eknih/cdrom/opendata/"
        n = 0
        try:
            pz = self.download(base + "poslanci.zip", "cz_poslanci.zip", timeout=300, max_age=7 * 86400)
            with zipfile.ZipFile(pz) as z:
                names = {os.path.basename(x).lower(): x for x in z.namelist()}
                org = {r[0]: r for r in self._unl(z, names["organy.unl"]) if len(r) > 6}
                terms = [(int(re.sub(r"\D", "", r[3]) or 0), r[0], r[6]) for r in org.values() if re.match(r"^PSP\d+$", r[3] or "")]
                terms.sort()
                term_no, term_id, term_from = terms[-1]
                osoby = {r[0]: ("%s %s" % (r[3], r[2])).strip() for r in self._unl(z, names["osoby.unl"]) if len(r) > 3}
                posl = {}
                for r in self._unl(z, names["poslanec.unl"]):
                    if len(r) > 4 and r[4] == term_id:
                        posl[r[0]] = r[1]
                clubs = {}
                for r in self._unl(z, names["zarazeni.unl"]):
                    if len(r) > 4 and r[2] == "0" and not (r[4] or "").strip():
                        o = org.get(r[1])
                        if o and re.match(r"Poslanecký klub|Klub", o[4] or ""):
                            clubs[r[0]] = (o[3] or re.sub(r"^Poslanecký klub\s*", "", o[4])).strip()   # the short name: ANO, ODS, STAN...
            yr = term_from[-4:] if re.search(r"\d{4}$", term_from or "") else term_from[:4]
            hz = self.download(base + "hl-%sps.zip" % yr, "cz_hl%s.zip" % yr, timeout=600, max_age=20 * 3600)
            with zipfile.ZipFile(hz) as z:
                names = {os.path.basename(x).lower(): x for x in z.namelist()}
                sname = next((v for k, v in names.items() if re.match(r"hl\d+s\.unl$", k)), None)
                hnames = [v for k, v in sorted(names.items()) if re.match(r"hl\d+h\d+\.unl$", k)]
                V = [r for r in self._unl(z, sname) if len(r) > 15]
                def _iso(d):
                    m = re.match(r"(\d+)\.(\d+)\.(\d{4})", d or "")
                    return "%s-%02d-%02d" % (m.group(3), int(m.group(2)), int(m.group(1))) if m else d
                V.sort(key=lambda r: (_iso(r[5]), r[6]), reverse=True)
                want = {}
                for r in V:
                    if len(want) >= 150:
                        break
                    if not self.have("CZ-" + r[0]):
                        want[r[0]] = r
                if want:
                    per = {k: [] for k in want}
                    for hn in hnames:
                        for r in self._unl(z, hn):
                            if len(r) > 2 and r[1] in per:
                                per[r[1]].append(r)
                    for vid, r in want.items():
                        if self._stop():
                            break
                        mem = []
                        for x in per[vid]:
                            oid = posl.get(x[0], "")
                            mem.append(("CZ:" + (oid or x[0]), osoby.get(oid, "MP " + x[0]), clubs.get(oid, ""), CZ_POS.get(x[2], "O"), ""))
                        title = (r[15] or r[16] or "").strip()
                        self.save_vote({"id": "CZ-" + vid, "cc": "CZ", "chamber": "P", "date": _iso(r[5]), "title": title or "Vote %s, sitting %s" % (r[3], r[2]),
                                        "question": (r[16] or "").strip() if r[15] and r[16] and r[16] != r[15] else "",
                                        "result": {"A": "Adopted", "R": "Rejected"}.get(r[14], ""), "src": "psp.cz",
                                        "yes": r[7], "no": r[8], "abstain": r[9],
                                        "url": "https://www.psp.cz/sqw/hlasy.sqw?g=%s" % vid}, mem)
                        n += 1
            self._ok("Czech votes", True, "%d new (term %d)" % (n, term_no))
        except (self.FetchError, zipfile.BadZipFile, KeyError, IndexError, ValueError, OSError, StopIteration, TypeError) as e:
            self._ok("Czech votes", False, str(e) or e.__class__.__name__)

    # ================================================================== AUSTRALIA (They Vote For You, free key)
    def pull_au(self):
        key = self.settings.get("tvfy_key")
        if not key:
            self._ok("Australia votes", True, "off: needs a free They Vote For You key")
            return
        n = 0
        try:
            start = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()
            L = self.getj("https://theyvoteforyou.org.au/api/v1/divisions.json?" + urllib.parse.urlencode({"key": key, "start_date": start}), timeout=60)
            if isinstance(L, dict):
                L = L.get("divisions") or []
            L.sort(key=lambda d: (d.get("date") or "", d.get("number") or 0), reverse=True)
            for dv in L:
                if n >= 40 or self._stop():
                    break
                did = dv.get("id")
                vid = "AU-%s" % did
                if not did or self.have(vid):
                    continue
                d = self.getj("https://theyvoteforyou.org.au/api/v1/divisions/%s.json?key=%s" % (did, urllib.parse.quote(key)), timeout=60)
                ch = "S" if (d.get("house") or dv.get("house")) == "senate" else "R"
                mem = []
                for x in d.get("votes") or []:
                    m = x.get("member") or {}
                    pid = (m.get("person") or {}).get("id") or m.get("id")
                    v = (x.get("vote") or "").lower()
                    mem.append(("AU:%s" % pid, ("%s %s" % (m.get("first_name") or "", m.get("last_name") or "")).strip(), m.get("party") or "",
                                "Y" if v.startswith("aye") else "N" if v.startswith("no") else "O", m.get("electorate") or ""))
                bills = d.get("bills") or []
                self.save_vote({"id": vid, "cc": "AU", "chamber": ch, "date": d.get("date") or dv.get("date") or "", "title": d.get("name") or dv.get("name") or "",
                                "question": ", ".join(b.get("title") or "" for b in bills[:2]), "result": "", "src": "theyvoteforyou",
                                "yes": d.get("aye_votes"), "no": d.get("no_votes"),
                                "url": "https://theyvoteforyou.org.au/divisions/%s/%s/%s" % ("senate" if ch == "S" else "representatives", d.get("date") or "", d.get("number") or "")}, mem)
                n += 1
                time.sleep(1)
            self._ok("Australia votes", True, "%d new" % n)
        except (self.FetchError, ValueError, KeyError, TypeError, AttributeError) as e:
            self._ok("Australia votes", False, str(e))
