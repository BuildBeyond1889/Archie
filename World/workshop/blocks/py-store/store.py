"""Save data and settings as JSON files next to the app, safely.

    s = Store("farm")              # data/farm.json
    s.set("name", "Shamba ya Juma")
    s.add("harvests", {"crop": "maize", "kg": 40})
    s.get("harvests")               # [{"crop": "maize", "kg": 40, "id": 1}]

Every save writes a new file and then swaps it in, so a power cut can't leave a half-written file.
The last 5 versions are kept in data/.old/ just in case.
"""
import json
import os
import shutil
import time

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


class Store:
    def __init__(self, name="app", folder=None, keep=5):
        self.folder = folder or BASE
        self.path = os.path.join(self.folder, name + ".json")
        self.keep = keep
        os.makedirs(self.folder, exist_ok=True)
        self.data = self._load()

    def _load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except ValueError:                       # damaged file: fall back to the newest good copy
            for old in self._olds():
                try:
                    with open(old, encoding="utf-8") as f:
                        return json.load(f)
                except ValueError:
                    continue
            return {}

    def _olds(self):
        d = os.path.join(self.folder, ".old")
        if not os.path.isdir(d):
            return []
        base = os.path.basename(self.path)
        return sorted((os.path.join(d, f) for f in os.listdir(d) if f.startswith(base)), reverse=True)

    def save(self):
        if os.path.exists(self.path) and self.keep:
            d = os.path.join(self.folder, ".old")
            os.makedirs(d, exist_ok=True)
            shutil.copy2(self.path, os.path.join(d, "%s.%d" % (os.path.basename(self.path), time.time_ns())))
            for extra in self._olds()[self.keep:]:
                os.remove(extra)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def add(self, listname, item):
        """Add a record to a list and give it an id. Returns the record."""
        items = self.data.setdefault(listname, [])
        item = dict(item, id=max([i.get("id", 0) for i in items] + [0]) + 1)
        items.append(item)
        self.save()
        return item

    def update(self, listname, item_id, **changes):
        for i in self.data.get(listname, []):
            if i.get("id") == item_id:
                i.update(changes)
                self.save()
                return i
        return None

    def remove(self, listname, item_id):
        items = self.data.get(listname, [])
        self.data[listname] = [i for i in items if i.get("id") != item_id]
        self.save()
        return len(items) != len(self.data[listname])
