"""Archie World: live cosmic alerts for the Milky Way view.

  * gravitational waves: black holes and neutron stars colliding, from LIGO-Virgo-KAGRA's public alerts (GraceDB).
    Each alert carries a sky map; Archie takes its most likely direction and its distance from it.
  * supernovae: the brightest ones being watched right now (David Bishop's Latest Supernovae list).
  * gamma-ray bursts: from the GCN Circulars that NASA's Fermi and Swift teams post with a position.

Directions are where in the sky each came from; distances (when known) turn into the right place in the universe.
"""
import base64
import json
import math
import re
import struct
import time
import urllib.parse

H0, OM, OL = 67.7, 0.31, 0.69
C_KMS = 299792.458
MPC_LY = 3.26156e6


def _cosmo_table():
    """z -> (comoving distance in light-years, light travel time in years), flat Lambda-CDM."""
    zs, dc, tl = [0.0], [0.0], [0.0]
    z, D, T, dz = 0.0, 0.0, 0.0, 0.0005
    hubble_time = 977.8e9 / H0   # years
    while z < 20:
        zm = z + dz / 2
        E = math.sqrt(OM * (1 + zm) ** 3 + OL)
        D += C_KMS / H0 * dz / E
        T += hubble_time * dz / ((1 + zm) * E)
        z += dz
        if z > 2:
            dz = 0.005
        zs.append(z); dc.append(D * MPC_LY); tl.append(T)
    return zs, dc, tl


_TAB = None


def from_z(z):
    global _TAB
    if _TAB is None:
        _TAB = _cosmo_table()
    zs, dc, tl = _TAB
    if z <= 0:
        return 0.0, 0.0
    lo, hi = 0, len(zs) - 1
    while hi - lo > 1:
        m = (lo + hi) // 2
        if zs[m] < z:
            lo = m
        else:
            hi = m
    f = (z - zs[lo]) / ((zs[hi] - zs[lo]) or 1)
    return dc[lo] + f * (dc[hi] - dc[lo]), tl[lo] + f * (tl[hi] - tl[lo])


def from_lum_mpc(dl):
    """Luminosity distance (Mpc) -> (z, comoving ly, light travel time years)."""
    global _TAB
    if _TAB is None:
        _TAB = _cosmo_table()
    zs, dc, tl = _TAB
    for i in range(1, len(zs)):
        if (1 + zs[i]) * dc[i] / MPC_LY >= dl:
            return zs[i], dc[i], tl[i]
    return zs[-1], dc[-1], tl[-1]


# ---- HEALPix (nested) pixel -> direction, for the gravitational-wave sky maps
_JRLL = [2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4]
_JPLL = [1, 3, 5, 7, 0, 2, 4, 6, 1, 3, 5, 7]


def _compress(v):
    out, bit = 0, 0
    while v:
        out |= (v & 1) << bit
        v >>= 2
        bit += 1
    return out


def pix2ang_nest(nside, ipix):
    """(theta, phi) in radians, the HEALPix convention."""
    npface = nside * nside
    face, ipf = divmod(ipix, npface)
    ix, iy = _compress(ipf), _compress(ipf >> 1)
    jr = _JRLL[face] * nside - ix - iy - 1
    nl4 = 4 * nside
    if jr < nside:
        nr, z, kshift = jr, 1 - jr * jr / (3.0 * npface), 0
    elif jr > 3 * nside:
        nr = nl4 - jr
        z, kshift = nr * nr / (3.0 * npface) - 1, 0
    else:
        nr, z, kshift = nside, (2 * nside - jr) * 2.0 / (3 * nside), (jr - nside) & 1
    jp = (_JPLL[face] * nr + ix - iy + 1 + kshift) // 2
    if jp > nl4:
        jp -= nl4
    if jp < 1:
        jp += nl4
    phi = (jp - (kshift + 1) * 0.5) * (math.pi / 2 / nr)
    return math.acos(max(-1.0, min(1.0, z))), phi


def read_skymap(raw):
    """A LIGO multi-order FITS sky map -> (ra, dec, area90 sq deg, distmean Mpc, diststd Mpc)."""
    pos, hdr, hdus = 0, {}, []
    while pos < len(raw) and len(hdus) < 2:
        h = {}
        while True:
            block = raw[pos:pos + 2880]
            pos += 2880
            if not block:
                break
            done = False
            for i in range(0, 2880, 80):
                card = block[i:i + 80].decode("ascii", "replace")
                k = card[:8].strip()
                if k == "END":
                    done = True
                    break
                if card[8:10] == "= ":
                    v = card[10:].split("/")[0].strip().strip("'").strip()
                    h[k] = v
            if done:
                break
        n = int(h.get("NAXIS1") or 0) * int(h.get("NAXIS2") or 0) if int(h.get("NAXIS") or 0) >= 2 else 0
        hdus.append((h, pos))
        pos += ((n + 2879) // 2880) * 2880
    if len(hdus) < 2:
        raise ValueError("no table in the sky map")
    hdr, start = hdus[1]
    rowlen, nrows = int(hdr["NAXIS1"]), int(hdr["NAXIS2"])
    cols, off, offs = [], 0, {}
    for i in range(1, int(hdr.get("TFIELDS") or 0) + 1):
        name, form = hdr.get("TTYPE%d" % i, ""), hdr.get("TFORM%d" % i, "")
        size = {"K": 8, "D": 8, "E": 4, "J": 4}.get(form[-1:], 8)
        offs[name] = (off, form[-1:])
        off += size
    if "UNIQ" not in offs or "PROBDENSITY" not in offs:
        raise ValueError("unexpected sky map columns")
    uo, po = offs["UNIQ"][0], offs["PROBDENSITY"][0]
    best, bu, items = -1, 0, []
    for r in range(nrows):
        b = start + r * rowlen
        u = struct.unpack(">q", raw[b + uo:b + uo + 8])[0]
        p = struct.unpack(">d", raw[b + po:b + po + 8])[0]
        order = int(math.log2(u // 4) // 2)
        area = 4 * math.pi / (12 * 4 ** order)
        items.append((p, area))
        if p > best:
            best, bu = p, u
    order = int(math.log2(bu // 4) // 2)
    th, ph = pix2ang_nest(2 ** order, bu - 4 * 4 ** order)
    items.sort(reverse=True)
    acc, a90 = 0.0, 0.0
    for p, a in items:
        if acc >= 0.9:
            break
        acc += p * a
        a90 += a
    dm = float(hdr["DISTMEAN"]) if hdr.get("DISTMEAN") else None
    ds = float(hdr["DISTSTD"]) if hdr.get("DISTSTD") else None
    return math.degrees(ph), 90 - math.degrees(th), a90 * (180 / math.pi) ** 2, dm, ds


def _hms(s, deg=False):
    m = re.match(r"([+-]?)(\d+):(\d+):([\d.]+)", s.strip())
    if not m:
        return None
    v = int(m.group(2)) + int(m.group(3)) / 60 + float(m.group(4)) / 3600
    v = v * (15 if not deg else 1)
    return -v if m.group(1) == "-" else v


GW_KIND = {"BBH": "two black holes merging", "BNS": "two neutron stars merging", "NSBH": "a neutron star and a black hole merging"}


def pull_gw(get, getj, old):
    """The latest significant gravitational-wave alerts. old: {id: item} already worked out (sky maps are big)."""
    q = urllib.parse.urlencode({"query": "category: Production label: SIGNIF_LOCKED", "count": 12, "format": "json"})
    d = getj("https://gracedb.ligo.org/api/superevents/?" + q, timeout=60)
    out, fetched = [], 0
    for s in d.get("superevents") or []:
        sid = s.get("superevent_id") or ""
        if "RETRACTED" in (s.get("labels") or []):
            continue
        if sid in old:
            out.append(old[sid])
            continue
        if fetched >= 3:
            continue
        fetched += 1
        files = getj("https://gracedb.ligo.org/api/superevents/%s/files/" % sid, timeout=60)
        alerts = sorted([k for k in files if re.match(re.escape(sid) + r"-(preliminary|initial|update)\.json$", k)],
                        key=lambda k: ["preliminary", "initial", "update"].index(k.rsplit("-", 1)[1][:-5]))
        if not alerts:
            continue
        j = json.loads(get(files[alerts[-1]], timeout=120))
        ev = j.get("event") or {}
        cls = ev.get("classification") or {}
        kind = max(cls, key=cls.get) if cls else ""
        item = {"kind": "gw", "id": sid, "name": s.get("gw_id") or sid, "t": ev.get("time") or s.get("created"),
                "what": GW_KIND.get(kind, "not sure what" if kind != "Terrestrial" else "possibly a glitch on Earth, not space"),
                "p": round(cls.get(kind, 0) * 100) if kind else None, "terrestrial": round(cls.get("Terrestrial", 0) * 100, 1),
                "url": "https://gracedb.ligo.org/superevents/%s/view/" % sid}
        if ev.get("skymap"):
            try:
                ra, dec, a90, dm, dsd = read_skymap(base64.b64decode(ev["skymap"]))
                item.update({"ra": round(ra, 2), "dec": round(dec, 2), "area": round(a90)})
                if dm:
                    z, ly, lb = from_lum_mpc(dm)
                    item.update({"ly": round(ly), "lookback": round(lb), "z": round(z, 3), "dist_mpc": round(dm), "dist_err": round(dsd or 0)})
            except (ValueError, KeyError, struct.error, IndexError) as e:
                item["note"] = "sky map unreadable: %s" % e
        out.append(item)
        time.sleep(1)
    return out


def pull_sn(get):
    """The brightest supernovae being watched now."""
    t = get("https://www.rochesterastronomy.org/snimages/snactive.html", timeout=90, headers={"Range": "bytes=0-120000", "Accept-Encoding": "identity"})
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", t, re.S):
        c = [re.sub(r"<[^>]+>", "", x).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(c) < 12:
            continue
        name, host, ra, dec, mag, last, typ, z = c[0], c[1], c[2], c[3], c[5], c[6], c[7], c[8]
        if not typ or typ in ("EGN", "Nova", "nova", "LRN", "LBV", "unk", "CV") or "nova" in typ.lower() and not typ.startswith("SN"):
            continue
        r, d_ = _hms(ra), _hms(dec, deg=True)
        if r is None or d_ is None:
            continue
        try:
            zf = float(z)
        except ValueError:
            zf = None
        item = {"kind": "sn", "id": name, "name": ("SN " + name) if re.match(r"^\d{4}", name) else name, "host": host, "ra": round(r, 3), "dec": round(d_, 3),
                "mag": mag, "type": typ, "last": last.replace("/", "-"), "first": c[11].replace("/", "-") if len(c) > 11 else "",
                "found_by": c[12] if len(c) > 12 else "", "url": "https://www.rochesterastronomy.org/supernova.html#" + name}
        if zf and zf > 0:
            ly, lb = from_z(zf)
            item.update({"z": zf, "ly": round(ly), "lookback": round(lb)})
        out.append(item)
        if len(out) >= 15:
            break
    return out


def pull_grb(get, getj, old):
    """Gamma-ray bursts from the last few weeks that the GCN Circulars give a position for."""
    h = get("https://gcn.nasa.gov/circulars?query=GRB&limit=60", timeout=60)
    by = {}
    for cid, subj in re.findall(r'href="/circulars/(\d+)[^"]*"[^>]*>([^<]+)<', h):
        m = re.search(r"GRB\s?(\d{6}[A-Z]?)", subj)
        if m:
            by.setdefault("GRB " + m.group(1), []).append((int(cid), subj))
    out, fetched = [], 0
    for name, L in sorted(by.items(), key=lambda x: -max(c for c, _ in x[1])):
        o = old.get(name)
        if o and not (o.get("nopos") and time.time() - (o.get("tried") or 0) > 6 * 3600 and max(c for c, _ in L) > (o.get("last_c") or 0)):
            out.append(o)
            continue
        L.sort(key=lambda x: (0 if re.search(r"Swift|XRT|BAT|Localization|position|optical", x[1], re.I) else 1, -x[0]))
        for cid, subj in L[:3]:
            if fetched >= 10:
                break
            fetched += 1
            j = getj("https://gcn.nasa.gov/circulars/%d.json" % cid, timeout=60)
            body = j.get("body") or ""
            m = (re.search(r"RA\s*=\s*([\d.]+)[^,\n]*,\s*Dec\s*=\s*([+-]?[\d.]+)", body) or
                 re.search(r"RA,\s*Dec\s*=?\s*([\d.]+)\s*,\s*([+-]?[\d.]+)", body))
            time.sleep(0.5)
            if not m:
                continue
            err = re.search(r"uncertainty of ([\d.]+) (deg|arcmin|arcsec)", body)
            item = {"kind": "grb", "id": name, "name": name, "ra": float(m.group(1)), "dec": float(m.group(2)), "t": "20%s-%s-%s" % (name[4:6], name[6:8], name[8:10]),
                    "err": ("%s %s" % (err.group(1), {"deg": "degrees", "arcmin": "arcminutes", "arcsec": "arcseconds"}[err.group(2)])) if err else "",
                    "short": bool(re.search(r"\bSHORT\b", body)), "src": subj[:140], "url": "https://gcn.nasa.gov/circulars/%d" % cid}
            zm = re.search(r"redshift of z\s*=\s*([\d.]+)", body)
            if zm:
                item["z"] = float(zm.group(1))
                item["ly"], item["lookback"] = [round(v) for v in from_z(item["z"])]
            out.append(item)
            break
        else:
            if fetched < 10:
                out.append({"kind": "grb", "id": name, "name": name, "nopos": True, "tried": time.time(), "last_c": max(c for c, _ in L)})   # remembered, so it isn't looked up again
        if sum(1 for x in out if not x.get("nopos")) >= 10:
            break
    return out
