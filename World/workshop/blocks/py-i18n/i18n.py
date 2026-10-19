"""Your app in more than one language (English and Swahili to start).

    T = Strings({"en": {"save": "Save", "hello": "Hello, {name}"},
                 "sw": {"save": "Hifadhi", "hello": "Habari, {name}"}})
    T.lang = "sw"
    T("save")                     # "Hifadhi"
    T("hello", name="Juma")       # "Habari, Juma"
A word missing in one language falls back to English, then to the key itself, so nothing ever breaks.
"""

COMMON = {
    "en": {"save": "Save", "cancel": "Cancel", "add": "Add", "delete": "Delete", "edit": "Edit", "search": "Search",
           "date": "Date", "name": "Name", "total": "Total", "yes": "Yes", "no": "No", "back": "Back", "print": "Print",
           "export": "Export", "import": "Import", "settings": "Settings", "language": "Language", "saved": "Saved"},
    "sw": {"save": "Hifadhi", "cancel": "Ghairi", "add": "Ongeza", "delete": "Futa", "edit": "Hariri", "search": "Tafuta",
           "date": "Tarehe", "name": "Jina", "total": "Jumla", "yes": "Ndiyo", "no": "Hapana", "back": "Rudi", "print": "Chapisha",
           "export": "Hamisha", "import": "Leta", "settings": "Mipangilio", "language": "Lugha", "saved": "Imehifadhiwa"},
}


class Strings:
    def __init__(self, table=None, lang="en", fallback="en"):
        self.table = {k: dict(v) for k, v in COMMON.items()}
        for lg, words in (table or {}).items():
            self.table.setdefault(lg, {}).update(words)
        self.lang, self.fallback = lang, fallback

    def __call__(self, key, **fill):
        s = self.table.get(self.lang, {}).get(key) or self.table.get(self.fallback, {}).get(key) or key
        try:
            return s.format(**fill) if fill else s
        except (KeyError, IndexError):
            return s

    def languages(self):
        return sorted(self.table)

    def missing(self, lang):
        """Keys that still need translating into lang."""
        return sorted(set(self.table.get(self.fallback, {})) - set(self.table.get(lang, {})))
