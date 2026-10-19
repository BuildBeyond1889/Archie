"""Vault Check: tests the Vault's search on the real library and writes a report for tuning.

Double-click "Vault Check.bat" in the Archie folder and leave it running (about 15 to 40 minutes on a big drive).
It only reads the library. The report goes to VaultCheck\\report.txt (for reading) and report.json (for Claude).
"""
import datetime
import glob
import json
import os
import platform
import shutil
import sys
import time

APP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(APP, "VaultCheck")
DATA = os.path.join(OUT, "data")
sys.path.insert(0, APP)

QUERIES = [
    # health
    "how to treat a burn", "malaria symptoms", "dehydration in children", "snake bite first aid",
    "oral rehydration solution", "high blood pressure", "broken bone splint",
    # water, farming, energy
    "make water safe to drink", "how to plant maize", "chicken diseases", "compost", "solar panel battery wiring",
    "biogas digester", "rainwater harvesting", "drip irrigation", "how to store grain",
    # repair and electronics
    "bicycle chain keeps slipping", "phone won't charge", "arduino temperature sensor", "replace laptop screen",
    "car battery dead", "how to use a multimeter",
    # coding
    "python list comprehension", "javascript fetch json", "godot move character", "what is a linked list",
    # school
    "fractions for kids", "photosynthesis", "pythagorean theorem", "causes of world war 1", "how volcanoes work",
    "past tense english grammar",
    # kids, reference, survival
    "story about a goat", "Kenya", "Nairobi", "what does resilient mean", "how to tie a bowline knot",
    "what to do in an earthquake",
    # Swahili
    "maji safi", "kilimo cha mahindi",
]
WARM = ["how to treat a burn", "photosynthesis", "bicycle chain keeps slipping", "compost", "Kenya"]
SHELF = [("health", "how to treat a burn"), ("land", "how to plant maize"), ("repair", "phone won't charge")]


def say(*a):
    print(*a, flush=True)


def main():
    os.makedirs(DATA, exist_ok=True)
    # reuse what Archie already learned about the packs, so the check doesn't redo it
    world = os.path.join(APP, "World")
    for f in glob.glob(os.path.join(world, "vault-meta.json")) + glob.glob(os.path.join(world, "vault-r-*.json")):
        if not os.path.exists(os.path.join(DATA, os.path.basename(f))):
            shutil.copy(f, DATA)
    import archie_vault
    try:
        from importlib.metadata import version
        libzim_v = version("libzim")
    except Exception:      # noqa: BLE001
        libzim_v = "?"
    lib = archie_vault.Vault(APP, DATA, wiki_dir=os.path.join(APP, "Wikipedia"))
    rep = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "python": sys.version.split()[0], "libzim": libzim_v,
           "os": platform.platform(), "cpus": os.cpu_count(), "folder": lib.folder()}
    if not lib.folder():
        say("No vault folder found. Is the library in D:\\Archie\\Vault?")
        return
    try:
        rep["free_gb"] = round(shutil.disk_usage(lib.folder()).free / 1e9)
    except OSError:
        pass
    say("Vault Check: %s" % lib.folder())

    # 1. opening every pack and reading its details
    say("\n1/4  Opening every pack (the first time is the slowest)...")
    opens, t0 = {}, time.time()
    for pid, kind, stem, path, size, mtime in lib._files():
        if kind != "zim":
            continue
        t = time.time()
        try:
            if not (lib.meta.get(pid) or {}).get("size") == size:
                lib.meta[pid] = lib._meta_zim(path, stem, size)
            else:
                lib._arch(path)
            opens[pid] = round(time.time() - t, 2)
        except Exception as e:      # noqa: BLE001
            opens[pid] = "ERROR: %s" % e
        if isinstance(opens[pid], float) and opens[pid] > 3:
            say("   slow to open: %s (%.1f s)" % (stem, opens[pid]))
    lib._save("vault-meta.json", lib.meta)
    rep["open_seconds_total"] = round(time.time() - t0, 1)
    rep["open_seconds"] = opens
    say("   opened %d packs in %.0f s" % (len(opens), rep["open_seconds_total"]))
    say("   indexing RACHEL page titles...")
    t0 = time.time()
    lib._scan_meta()
    rep["scan_seconds"] = round(time.time() - t0, 1)
    with lib.lock:
        lib._cat = (0, None)
    packs = lib.packs()
    rep["packs"] = {p["id"]: {"title": p["title"], "shelf": p["shelf"], "gb": round(p["bytes"] / 1e9, 2), "fulltext": p["fulltext"],
                              "articles": p["articles"], "lang": p["lang"], "variant_of": p.get("variant_of", ""), "error": p.get("error", "")}
                    for p in packs.values()}
    say("   %d packs ready (%.0f s more for RACHEL)" % (len(packs), rep["scan_seconds"]))

    # 2. the questions
    say("\n2/4  Searching %d questions across everything..." % len(QUERIES))
    rep["queries"] = []
    for i, q in enumerate(QUERIES, 1):
        row = {"q": q}
        merged, seen = [], set()
        for mode in ("title", "text"):
            lib.slow.clear()
            t = time.time()
            r = lib.search(q, "all", mode, debug=True)
            row[mode + "_s"] = round(time.time() - t, 2)
            row[mode + "_skipped"] = r.get("skipped", [])
            row[mode + "_unreached"] = r.get("unreached", 0)
            timing = r.get("timing") or {}
            row[mode + "_slowest"] = sorted(timing.items(), key=lambda x: -x[1])[:6]
            row[mode + "_top"] = [{"pack": x["pack"], "title": x["title"], "path": x["path"], "score": sc,
                                   "snippet": (x.get("snippet") or "")[:220]} for x, sc in zip(r.get("results", [])[:10], r.get("scores", []))]
            for x in r.get("results", []):
                k = (x["id"], x["title"].lower().strip())
                if k not in seen:
                    seen.add(k)
                    merged.append({"pack": x["pack"], "title": x["title"], "score": x.get("score", 0)})
        merged.sort(key=lambda m: -m["score"])
        row["shown_first"] = merged[:10]
        rep["queries"].append(row)
        say("   %2d/%d  %-34s titles %5.1f s   pages %5.1f s   top: %s" % (
            i, len(QUERIES), q[:34], row["title_s"], row["text_s"], (merged[0]["title"][:40] if merged else "(nothing)")))
        _write(rep)

    # 3. the same questions again, now that the files are warm
    say("\n3/4  Again, warm...")
    rep["warm"] = []
    for q in WARM:
        lib.slow.clear()
        t = time.time()
        lib.search(q, "all", "title")
        a = time.time() - t
        t = time.time()
        lib.search(q, "all", "text")
        rep["warm"].append({"q": q, "title_s": round(a, 2), "text_s": round(time.time() - t, 2)})
        say("   %-34s titles %5.1f s   pages %5.1f s" % (q, a, rep["warm"][-1]["text_s"]))

    # 4. one shelf at a time
    say("\n4/4  One shelf at a time...")
    rep["shelf"] = []
    for sh, q in SHELF:
        lib.slow.clear()
        t = time.time()
        r = lib.search(q, "shelf:" + sh, "text")
        rep["shelf"].append({"shelf": sh, "q": q, "text_s": round(time.time() - t, 2), "skipped": r.get("skipped", []),
                             "top": [x["title"] for x in r.get("results", [])[:5]]})
        say("   %-8s %-30s %5.1f s" % (sh, q, rep["shelf"][-1]["text_s"]))
    rep["finished"] = datetime.datetime.now().isoformat(timespec="seconds")
    _write(rep)
    say("\nDone. The report is in %s" % OUT)
    say("Tell Claude it's finished.")


def _write(rep):
    with open(os.path.join(OUT, "report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    lines = ["VAULT CHECK  %s" % rep.get("when"), "library: %s   python %s   libzim %s" % (rep.get("folder"), rep.get("python"), rep.get("libzim")),
             "opening all packs: %s s   RACHEL titles: %s s" % (rep.get("open_seconds_total", "?"), rep.get("scan_seconds", "?")), ""]
    for row in rep.get("queries", []):
        lines.append("%s   (titles %.1f s, pages %.1f s)" % (row["q"], row.get("title_s", 0), row.get("text_s", 0)))
        for j, x in enumerate(row.get("shown_first", [])[:5], 1):
            lines.append("   %d. %s  [%s]  %.2f" % (j, x["title"], x["pack"], x.get("score", 0)))
        skipped = sorted(set(row.get("title_skipped", []) + row.get("text_skipped", [])))
        if skipped:
            lines.append("   too slow: " + ", ".join(skipped))
        lines.append("")
    with open(os.path.join(OUT, "report.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("Stopped. Whatever finished is in the report.")
