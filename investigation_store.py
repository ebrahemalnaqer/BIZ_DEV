"""SQLite persistence for investigations (parameterized queries only)."""
import json, sqlite3
from datetime import datetime

FIELDS = {"priority", "assignee", "status", "suspected_cause", "notes", "next_action"}


class DuplicateInvestigation(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self._c() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS investigations(
                id INTEGER PRIMARY KEY AUTOINCREMENT, alert_key TEXT UNIQUE NOT NULL, source TEXT, snapshot TEXT,
                priority TEXT DEFAULT 'Medium', assignee TEXT DEFAULT '', status TEXT DEFAULT 'Open',
                suspected_cause TEXT DEFAULT '', notes TEXT DEFAULT '', next_action TEXT DEFAULT '',
                final_findings TEXT, verified_impact REAL, created_at TEXT, updated_at TEXT)""")

    def _c(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def create(self, alert_key, source, snapshot, priority="Medium", assignee=""):
        now = datetime.now().isoformat(timespec="seconds")
        try:
            with self._c() as c:
                return c.execute("INSERT INTO investigations(alert_key,source,snapshot,priority,assignee,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                                 (alert_key, source, json.dumps(snapshot, default=str), priority, assignee, now, now)).lastrowid
        except sqlite3.IntegrityError:
            raise DuplicateInvestigation(f"An investigation already exists for {alert_key}")

    def update(self, iid, **f):
        bad = set(f) - FIELDS
        if bad:
            raise ValueError(f"Cannot update fields: {bad}")
        if f.get("status") == "Resolved":
            raise ValueError("Use resolve() with final findings to resolve an investigation.")
        if f:
            sets = ",".join(f"{k}=?" for k in f)
            with self._c() as c:
                c.execute(f"UPDATE investigations SET {sets}, updated_at=? WHERE id=?", (*f.values(), datetime.now().isoformat(timespec="seconds"), iid))

    def resolve(self, iid, findings, verified_impact=None):
        if not str(findings).strip():
            raise ValueError("Final findings are required before resolving.")
        with self._c() as c:
            c.execute("UPDATE investigations SET status='Resolved', final_findings=?, verified_impact=?, updated_at=? WHERE id=?",
                      (findings.strip(), verified_impact, datetime.now().isoformat(timespec="seconds"), iid))

    def list(self):
        with self._c() as c:
            return [dict(r) for r in c.execute("SELECT * FROM investigations ORDER BY id DESC")]
