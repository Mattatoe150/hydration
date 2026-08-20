-- Baseline the current production schema without rewriting existing data.
-- CREATE IF NOT EXISTS makes this safe for both a fresh database and the live
-- database, whose columns were added before migration tracking was introduced.

CREATE TABLE IF NOT EXISTS suggestions (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  kind       TEXT NOT NULL DEFAULT 'add',
  cat        TEXT,
  lat        REAL NOT NULL,
  lon        REAL NOT NULL,
  name       TEXT,
  note       TEXT,
  submitter  TEXT,
  suppress   INTEGER NOT NULL DEFAULT 0,
  indoor     INTEGER NOT NULL DEFAULT 0,
  rating     INTEGER NOT NULL DEFAULT 0,
  reason     TEXT,
  status     TEXT NOT NULL DEFAULT 'new',
  created    TEXT NOT NULL,
  iphash     TEXT
);

CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_suggestions_kind   ON suggestions(kind);
CREATE INDEX IF NOT EXISTS idx_suggestions_iphash ON suggestions(iphash);
