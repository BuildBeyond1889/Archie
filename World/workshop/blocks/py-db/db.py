"""A small database (SQLite, built into Python) with simple commands.

    db = DB("app.db")
    people = db.table("people", name="text", age="int", village="text")
    people.add(name="Amina", age=12, village="Kisumu")
    people.find(village="Kisumu")        # list of dicts
    people.search("ami")                 # matches any text field
    people.update(1, age=13); people.delete(1)

SQLite keeps everything in one file and can hold millions of rows on very old computers.
"""
import os
import sqlite3

TYPES = {"text": "TEXT", "int": "INTEGER", "real": "REAL", "date": "TEXT", "bool": "INTEGER"}


class Table:
    def __init__(self, db, name, fields):
        self.db, self.name, self.fields = db, name, fields
        cols = ", ".join('"%s" %s' % (k, TYPES.get(v, "TEXT")) for k, v in fields.items())
        db.con.execute('CREATE TABLE IF NOT EXISTS "%s" (id INTEGER PRIMARY KEY AUTOINCREMENT, %s)' % (name, cols))
        have = {r[1] for r in db.con.execute('PRAGMA table_info("%s")' % name)}
        for k, v in fields.items():                      # new fields added later get added to old databases too
            if k not in have:
                db.con.execute('ALTER TABLE "%s" ADD COLUMN "%s" %s' % (name, k, TYPES.get(v, "TEXT")))
        db.con.commit()

    def _check(self, keys):
        bad = [k for k in keys if k not in self.fields and k != "id"]
        if bad:
            raise KeyError("No field called %s in %s" % (", ".join(bad), self.name))

    def add(self, /, **row):
        self._check(row)
        cur = self.db.con.execute('INSERT INTO "%s" (%s) VALUES (%s)' % (self.name, ", ".join('"%s"' % k for k in row), ", ".join("?" * len(row))), list(row.values()))
        self.db.con.commit()
        return cur.lastrowid

    def get(self, row_id):
        r = self.db.con.execute('SELECT * FROM "%s" WHERE id=?' % self.name, (row_id,)).fetchone()
        return dict(r) if r else None

    def all(self, order="id"):
        self._check([order.lstrip("-")])
        d = " DESC" if order.startswith("-") else ""
        return [dict(r) for r in self.db.con.execute('SELECT * FROM "%s" ORDER BY "%s"%s' % (self.name, order.lstrip("-"), d))]

    def find(self, **eq):
        self._check(eq)
        where = " AND ".join('"%s"=?' % k for k in eq) or "1"
        return [dict(r) for r in self.db.con.execute('SELECT * FROM "%s" WHERE %s ORDER BY id' % (self.name, where), list(eq.values()))]

    def search(self, text):
        cols = [k for k, v in self.fields.items() if v in ("text", "date")]
        if not cols:
            return []
        where = " OR ".join('"%s" LIKE ?' % k for k in cols)
        return [dict(r) for r in self.db.con.execute('SELECT * FROM "%s" WHERE %s ORDER BY id' % (self.name, where), ["%" + text + "%"] * len(cols))]

    def update(self, row_id, /, **changes):
        self._check(changes)
        self.db.con.execute('UPDATE "%s" SET %s WHERE id=?' % (self.name, ", ".join('"%s"=?' % k for k in changes)), list(changes.values()) + [row_id])
        self.db.con.commit()

    def delete(self, row_id):
        self.db.con.execute('DELETE FROM "%s" WHERE id=?' % self.name, (row_id,))
        self.db.con.commit()

    def count(self):
        return self.db.con.execute('SELECT COUNT(*) FROM "%s"' % self.name).fetchone()[0]


class DB:
    def __init__(self, path="app.db"):
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row

    def table(self, table_name, /, **fields):         # the / lets you have a field called 'name'
        return Table(self, table_name, fields)

    def close(self):
        self.con.close()
