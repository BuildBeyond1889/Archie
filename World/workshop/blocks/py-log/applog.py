"""Logging and crash reports: when something goes wrong in the field, there's a record of what happened.

    log = setup("farm-app")        # writes logs/farm-app.log (keeps the last 5 files of 1 MB)
    log.info("Saved harvest %s", item_id)
If the app crashes, the full error goes into the log and a short crash report is saved in logs/,
so someone can send it to you later on a USB stick.
"""
import logging
import logging.handlers
import os
import sys
import time
import traceback

LOGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def setup(name="app", folder=None, level=logging.INFO):
    folder = folder or LOGS
    os.makedirs(folder, exist_ok=True)
    log = logging.getLogger(name)
    log.setLevel(level)
    if not log.handlers:
        h = logging.handlers.RotatingFileHandler(os.path.join(folder, name + ".log"), maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)

    def crash(kind, value, tb):
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("CRASH\n%s", text)
        with open(os.path.join(folder, "crash-%s.txt" % time.strftime("%Y%m%d-%H%M%S")), "w", encoding="utf-8") as f:
            f.write("%s crashed at %s\n\n%s" % (name, time.strftime("%Y-%m-%d %H:%M:%S"), text))
        sys.__excepthook__(kind, value, tb)
    sys.excepthook = crash
    return log
