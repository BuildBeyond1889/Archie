"""
install.py - installs or updates Archie Lite on this laptop from the stick (2026-11-09).

Run it with "Install or Update Archie Lite.bat" next to the installer folder. It:
  1. makes sure the encryption package (cryptography) is installed,
  2. closes Archie Lite if it's running,
  3. copies the app into %LOCALAPPDATA%\\ArchieLite (your data there is kept),
  4. brings over your data from an older copy (the stick, or wherever it ran from) if this is
     the first install, plus the newest pairing file,
  5. adds Archie Lite to the Start menu and to "start with Windows", and starts it.
After this, updates come over Wi-Fi from your PC by themselves; the stick is the backup way.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import time

STICK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # ...\ArchieLite on the stick
DEST = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "ArchieLite")
LOCK_PORT = 47323
SKIP_DIRS = {"__pycache__"}
NO_WINDOW = 0x08000000


def say(msg):
    print("  " + msg, flush=True)


def ps(cmd):
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                          capture_output=True, text=True, creationflags=NO_WINDOW)


def pythonw():
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return w if os.path.exists(w) else exe


# ----- 1. the one package Archie Lite needs ---------------------------------------------------
def ensure_cryptography():
    try:
        import cryptography  # noqa: F401
        say("encryption package: already installed")
        return True
    except ImportError:
        pass
    wheels = os.path.join(STICK, "installer", "wheels")
    tries = []
    if os.path.isdir(wheels):
        tries.append(["--no-index", "--find-links", wheels])
    tries.append([])
    for extra in tries:
        say("installing the encryption package (cryptography)" + (" from the stick" if extra else " from the internet") + "...")
        for user in (["--user"], []):        # --user fails inside a virtual environment
            r = subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                                "cryptography"] + user + extra, capture_output=True, text=True)
            if r.returncode == 0:
                import site, importlib
                importlib.invalidate_caches()
                try:
                    sys.path.append(site.getusersitepackages())
                except Exception:
                    pass
                return True
        last = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["?"]
        say("  didn't work: " + last[0][:200])
    return False


# ----- 2. close a running Archie Lite ------------------------------------------------------------
def lock_free():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", LOCK_PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def stop_running():
    if lock_free():
        return
    say("closing the Archie Lite that's running...")
    ps("Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.Name -match '^pythonw?\\.exe$' "
       "-and $_.CommandLine -match '[\\\\/]lite\\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }")
    ps("Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'msedge.exe' -and $_.CommandLine "
       "-match 'ArchieLite\\\\data\\\\edge' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
       "-ErrorAction SilentlyContinue }")
    for _ in range(20):
        if lock_free():
            return
        time.sleep(0.5)
    say("(it didn't close by itself; continuing anyway)")


# ----- 3. copy the app ------------------------------------------------------------------------------
def copy_tree(src, dst):
    n = 0
    for dirpath, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, src)
        out = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(out, exist_ok=True)
        for fn in files:
            if fn.endswith((".pyc", ".tmp", ".new")) or ".bak" in fn:
                continue
            tmp = os.path.join(out, fn + ".new")
            shutil.copyfile(os.path.join(dirpath, fn), tmp)
            os.replace(tmp, os.path.join(out, fn))
            n += 1
    return n


# ----- 4. data ----------------------------------------------------------------------------------------
def old_install_root():
    """Where Archie Lite ran from before (the "start with Windows" entry points at it)."""
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run")
        val, _ = winreg.QueryValueEx(k, "ArchieLite")
        winreg.CloseKey(k)
    except (OSError, ImportError):
        return None
    parts = [p for p in val.split('"') if p.strip().lower().endswith("lite.py")]
    if not parts:
        return None
    return os.path.dirname(os.path.dirname(parts[0].strip()))


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def bring_data():
    data = os.path.join(DEST, "data")
    os.makedirs(data, exist_ok=True)
    mine = os.path.join(data, "lite.json")
    if not os.path.exists(mine):
        cands = []
        for root in (old_install_root(), STICK):
            if root and os.path.normcase(os.path.abspath(root)) != os.path.normcase(DEST):
                p = os.path.join(root, "data", "lite.json")
                d = load_json(p)
                if d is not None:
                    cands.append((len(d.get("pending") or []), d.get("last_ok") or 0, os.path.getmtime(p), p))
        if cands:
            src = max(cands)[3]
            shutil.copyfile(src, mine)
            say("brought over your Archie Lite data from " + os.path.dirname(os.path.dirname(src)))
    d = load_json(mine)
    if d is not None and d.pop("update_done", None) is not None:      # the stick's copy is now what's installed
        with open(mine, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    # pairing: whichever was made by the PC most recently
    best = None
    for p in (os.path.join(data, "pairing.json"), os.path.join(STICK, "data", "pairing.json")):
        j = load_json(p)
        if j and j.get("key") and (best is None or (j.get("made") or 0) > (best[0].get("made") or 0)):
            best = (j, p)
    if best and best[1] != os.path.join(data, "pairing.json"):
        shutil.copyfile(best[1], os.path.join(data, "pairing.json"))
        say("pairing with " + str(best[0].get("pc") or "your PC") + ": copied")
    elif best:
        say("pairing with " + str(best[0].get("pc") or "your PC") + ": already set")
    else:
        say("NOTE: no pairing file found. On the PC, start Archie once, then run 'Make Archie Lite stick.bat'.")


# ----- 5. shortcuts, start with Windows, launch ----------------------------------------------------
def shortcuts():
    app = os.path.join(DEST, "app", "lite.py")
    exe = pythonw()
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                           winreg.KEY_SET_VALUE)
        winreg.SetValueEx(k, "ArchieLite", 0, winreg.REG_SZ, f'"{exe}" "{app}"')
        winreg.CloseKey(k)
        say("starts with Windows: yes (turn off with a right-click on the owl)")
    except OSError as e:
        say(f"couldn't set start with Windows: {e}")
    lnk = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Archie Lite.lnk")
    icon = os.path.join(DEST, "app", "archie_owl.ico")
    q = lambda s: s.replace("'", "''")
    # Windows' own conhost.exe starts pythonw with no window; a shortcut straight to Microsoft Store
    # Python (a WindowsApps stub) shows a blank page on the taskbar instead of the owl.
    conhost = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "conhost.exe")
    target, args = (conhost, f'--headless "{exe}" "{app}" --show') if os.path.exists(conhost) else (exe, f'"{app}" --show')
    cmd = (f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}');"
           f"$s.TargetPath='{q(target)}';$s.Arguments='{q(args)}';$s.WorkingDirectory='{q(DEST)}';$s.WindowStyle=7;"
           f"$s.Description='Archie Lite: Ctrl+Alt+A';" + (f"$s.IconLocation='{q(icon)},0';" if os.path.exists(icon) else "")
           + "$s.Save()")
    r = ps(cmd)
    say("Start menu: 'Archie Lite' added" if r.returncode == 0 else "Start menu shortcut: skipped (" + (r.stderr or "").strip()[:120] + ")")


def write_starter():
    """DEST\\Start Archie Lite.bat, using the same Python the installer used."""
    with open(os.path.join(DEST, "Start Archie Lite.bat"), "w", newline="\r\n") as f:
        f.write("@echo off\nREM Starts Archie Lite with no console window (written by the installer).\n"
                f'cd /d "{DEST}"\nstart "" "{pythonw()}" "{os.path.join(DEST, "app", "lite.py")}"\n')


def launch():
    subprocess.Popen([pythonw(), os.path.join(DEST, "app", "lite.py")], cwd=DEST,
                     creationflags=0x00000008 | 0x00000200 | NO_WINDOW, close_fds=True)


def main():
    print()
    print("  Archie Lite installer")
    print("  ---------------------")
    say(f"Python {sys.version.split()[0]} at {sys.executable}")
    if not os.path.isfile(os.path.join(STICK, "app", "lite.py")):
        say("ERROR: can't find app\\lite.py next to the installer folder.")
        return 1
    if not ensure_cryptography():
        say("ERROR: couldn't install the encryption package. Connect to the internet and run this again.")
        return 1
    was = os.path.exists(os.path.join(DEST, "app", "lite.py"))
    stop_running()
    n = copy_tree(os.path.join(STICK, "app"), os.path.join(DEST, "app"))
    n += copy_tree(os.path.join(STICK, "web"), os.path.join(DEST, "web"))
    for fn in ("README.md",):
        if os.path.exists(os.path.join(STICK, fn)):
            shutil.copyfile(os.path.join(STICK, fn), os.path.join(DEST, fn))
    say(("updated" if was else "installed") + f" {n} files in {DEST}")
    bring_data()
    write_starter()
    if sys.platform == "win32":
        shortcuts()
    launch()
    print()
    say("Done. The owl is on your screen; Ctrl+Alt+A opens the panel.")
    say("From now on, updates arrive over Wi-Fi from your PC. You can unplug the stick.")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        say(f"ERROR: {e}")
        code = 1
    sys.exit(code)
