"""Once a day, at the first quiet stretch: back up what can't be rebuilt, and keep the Archie folder tidy.

1. Snapshot: your settings, calendar, to-dos, chats, memory, flashcard decks, modes and notes are zipped to
   D:\\Archie Backups\\Daily\\<date>.zip. The last 7 days are kept.
2. Obsidian mirror: new or changed files in your Obsidian vault (lecture notes, reviews, exam prep, ideas)
   are copied to D:\\Archie Backups\\Obsidian. Nothing is ever deleted from the mirror, so a note deleted by
   mistake is still there. (Your vault is on C:, so this also covers the C: drive failing.)
3. Archie\\Backups (the .bak- copies made before every change): keeps the newest copy of each file plus
   anything from the last 30 days; older ones are cleared.
4. Feather\\backups: the pre-change copies (pre-...) older than 30 days go, always keeping the newest 10.
5. Logs: any .log file over 5 MB in Archie, Archie\\World and Feather is cut down to its last 2 MB.
Not backed up (big, and can be downloaded again): models, Wikipedia, the voice and image models, notes_index.json.
"""
import datetime
import json
import os
import re
import shutil
import threading
import time
import zipfile

KEEP_DAYS_SNAPSHOT = 7
KEEP_DAYS_BAK = 30
SKIP_BIGGER = 50 * 1024 * 1024        # files over 50 MB stay out of the daily zip
SNAP_FILES = re.compile(r".+\.(json|txt)$", re.I)
SNAP_SKIP = {"notes_index.json"}
SNAP_DIRS = ("Chats", "Memory", "Study", "Modes", "Notes")


class Housekeep:
    def __init__(self, app_dir, vault, quiet, report=lambda m: None, dest=None):
        self.app_dir = app_dir
        self.vault = vault                    # callable -> Obsidian vault folder (or None)
        self.quiet = quiet                    # callable -> True when it's a good time
        self.report = report
        self.dest = dest or os.path.join(os.path.dirname(os.path.abspath(app_dir)), "Archie Backups")
        self.state_path = os.path.join(app_dir, "housekeep.json")
        self.working = False

    def _state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save(self, st):
        with open(self.state_path + ".tmp", "w", encoding="utf-8") as f:
            json.dump(st, f, indent=1)
        os.replace(self.state_path + ".tmp", self.state_path)

    # 1. the daily snapshot ------------------------------------------------------------------------
    def snapshot(self, today=None):
        today = today or datetime.date.today()
        daily = os.path.join(self.dest, "Daily")
        os.makedirs(daily, exist_ok=True)
        out = os.path.join(daily, f"{today.isoformat()}.zip")
        tmp = out + ".part"
        n = 0
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for fn in os.listdir(self.app_dir):
                p = os.path.join(self.app_dir, fn)
                if os.path.isfile(p) and SNAP_FILES.match(fn) and fn not in SNAP_SKIP and os.path.getsize(p) <= SKIP_BIGGER:
                    z.write(p, fn)
                    n += 1
            for d in SNAP_DIRS:
                root = os.path.join(self.app_dir, d)
                for dp, _, fns in os.walk(root):
                    for fn in fns:
                        p = os.path.join(dp, fn)
                        try:
                            if os.path.getsize(p) <= SKIP_BIGGER:
                                z.write(p, os.path.relpath(p, self.app_dir))
                                n += 1
                        except OSError:
                            pass
        os.replace(tmp, out)
        cut = today - datetime.timedelta(days=KEEP_DAYS_SNAPSHOT - 1)
        for fn in os.listdir(daily):
            m = re.match(r"(\d{4}-\d{2}-\d{2})\.zip$", fn)
            if m and datetime.date.fromisoformat(m.group(1)) < cut:
                os.remove(os.path.join(daily, fn))
        return n

    # 2. the Obsidian mirror ---------------------------------------------------------------------
    def mirror(self):
        vault = self.vault()
        if not vault or not os.path.isdir(vault):
            return 0
        dst_root = os.path.join(self.dest, "Obsidian")
        n = 0
        for dp, dns, fns in os.walk(vault):
            dns[:] = [d for d in dns if d not in (".trash",)]
            for fn in fns:
                s = os.path.join(dp, fn)
                d = os.path.join(dst_root, os.path.relpath(s, vault))
                try:
                    st = os.stat(s)
                    if os.path.exists(d):
                        dt = os.stat(d)
                        if dt.st_size == st.st_size and dt.st_mtime >= st.st_mtime - 2:
                            continue
                    os.makedirs(os.path.dirname(d), exist_ok=True)
                    shutil.copy2(s, d)
                    n += 1
                except OSError:
                    pass
        return n

    # 3. the .bak- copies --------------------------------------------------------------------------
    def prune_baks(self, now=None):
        folder = os.path.join(self.app_dir, "Backups")
        if not os.path.isdir(folder):
            return 0
        now = now or time.time()
        groups = {}
        for dp, _, fns in os.walk(folder):
            for fn in fns:
                m = re.match(r"(.+?)\.bak-", fn)
                if m:
                    p = os.path.join(dp, fn)
                    groups.setdefault(m.group(1).lower(), []).append((os.path.getmtime(p), p))
        gone = 0
        for _, items in groups.items():
            items.sort(reverse=True)                  # newest first: always keep it
            for mt, p in items[1:]:
                if now - mt > KEEP_DAYS_BAK * 86400:
                    try:
                        os.remove(p)
                        gone += 1
                    except OSError:
                        pass
        return gone

    def prune_feather(self, now=None):
        folder = os.path.join(os.path.dirname(os.path.abspath(self.app_dir)), "Feather", "backups")
        if not os.path.isdir(folder):
            return 0
        now = now or time.time()
        pre = sorted(((os.path.getmtime(os.path.join(folder, n)), os.path.join(folder, n)) for n in os.listdir(folder)
                      if n.startswith("pre-") and os.path.isdir(os.path.join(folder, n))), reverse=True)
        gone = 0
        for mt, p in pre[10:]:
            if now - mt > KEEP_DAYS_BAK * 86400:
                shutil.rmtree(p, ignore_errors=True)
                gone += 1
        return gone

    def cap_logs(self, big=5 * 1024 * 1024, keep=2 * 1024 * 1024):
        root = os.path.dirname(os.path.abspath(self.app_dir))
        cut = 0
        for d in (self.app_dir, os.path.join(self.app_dir, "World"), os.path.join(root, "Feather"),
                  os.path.join(root, "Feather", "sync"), os.path.join(root, "Feather", "app")):
            if not os.path.isdir(d):
                continue
            for n in os.listdir(d):
                p = os.path.join(d, n)
                if not n.lower().endswith(".log") or not os.path.isfile(p):
                    continue
                try:
                    if os.path.getsize(p) <= big:
                        continue
                    with open(p, "rb") as f:
                        f.seek(-keep, 2)
                        tail = f.read()
                    tail = tail[tail.find(b"\n") + 1:]
                    with open(p, "wb") as f:
                        f.write(tail)
                    cut += 1
                except OSError:
                    pass                  # in use right now: next time
        return cut

    def run_once(self):
        self.working = True
        try:
            done = {}
            try:
                done["snapshot"] = self.snapshot()
            except Exception as e:
                done["snapshot_error"] = str(e)[:200]
            try:
                done["mirrored"] = self.mirror()
            except Exception as e:
                done["mirror_error"] = str(e)[:200]
            try:
                done["baks_cleared"] = self.prune_baks()
            except Exception as e:
                done["prune_error"] = str(e)[:200]
            try:
                done["feather_cleared"] = self.prune_feather()
                done["logs_cut"] = self.cap_logs()
            except Exception as e:
                done["tidy_error"] = str(e)[:200]
            st = self._state()
            st["ran"] = datetime.date.today().isoformat()
            st["last"] = done
            self._save(st)
            self.report("Backed up today's Archie stuff" + (f", copied {done['mirrored']} changed notes"
                                                           if done.get("mirrored") else "") + ".")
            return done
        finally:
            self.working = False

    def loop(self):
        time.sleep(300)
        while True:
            try:
                if self._state().get("ran") != datetime.date.today().isoformat() and self.quiet():
                    self.run_once()
            except Exception:
                self.working = False
            time.sleep(300)

    def start(self):
        threading.Thread(target=self.loop, daemon=True, name="housekeep").start()
        return self
