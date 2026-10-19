"""Search records by what people type, forgiving small differences.

    search(rows, "amina kis", fields=["name", "village"])   # best matches first
Every word must appear somewhere; capitals and accents don't matter; whole-word matches rank higher.
"""
import unicodedata


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def search(rows, query, fields=None, limit=50):
    words = norm(query).split()
    if not words:
        return list(rows)[:limit]
    out = []
    for r in rows:
        keys = fields or list(r)
        hay = " " + " ".join(norm(r.get(k, "")) for k in keys) + " "
        if all(w in hay for w in words):
            score = sum(3 if (" " + w + " ") in hay else 2 if (" " + w) in hay else 1 for w in words)
            out.append((score, r))
    out.sort(key=lambda x: -x[0])
    return [r for _, r in out[:limit]]
