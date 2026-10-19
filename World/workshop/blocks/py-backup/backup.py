"""Backups you can carry: zip the data folder (to a USB stick, say) and restore it later.

    path = make_backup("data", "E:/backups")       # E:/backups/data-2026-03-31-0915.zip
    restore(path, "data")                           # the current data is zipped first, just in case
"""
import os
import shutil
import time
import zipfile


def make_backup(folder, dest_dir, name=None):
    os.makedirs(dest_dir, exist_ok=True)
    name = name or os.path.basename(os.path.abspath(folder))
    path = os.path.join(dest_dir, "%s-%s.zip" % (name, time.strftime("%Y-%m-%d-%H%M%S")))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _, fs in os.walk(folder):
            for f in fs:
                p = os.path.join(dp, f)
                z.write(p, os.path.relpath(p, folder))
    return path


def list_backups(dest_dir, name=None):
    if not os.path.isdir(dest_dir):
        return []
    fs = [f for f in os.listdir(dest_dir) if f.endswith(".zip") and (not name or f.startswith(name + "-"))]
    return sorted((os.path.join(dest_dir, f) for f in fs), reverse=True)


def restore(zip_path, folder):
    with zipfile.ZipFile(zip_path) as z:
        bad = z.testzip()
        if bad:
            raise ValueError("The backup is damaged (%s). Nothing was changed." % bad)
        for n in z.namelist():                                  # refuse paths that try to escape the folder
            if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/"):
                raise ValueError("Unsafe path in backup: %s" % n)
        if os.path.isdir(folder) and os.listdir(folder):
            make_backup(folder, os.path.join(os.path.dirname(os.path.abspath(folder)), "before-restore"))
            shutil.rmtree(folder)
        z.extractall(folder)
    return folder
