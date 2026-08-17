-- D1 schema for community submissions (adds + reports).
-- Apply with:  npx wrangler d1 execute hydration --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS suggestions (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  kind    TEXT NOT NULL DEFAULT 'add',  -- 'add' (new spot) | 'report' (problem with an existing spot)
  cat     TEXT,                         -- water | vdrinks | vsnacks | shop | fuel
  lat     REAL NOT NULL,
  lon     REAL NOT NULL,
  name    TEXT,
  note    TEXT,
  reason  TEXT,                         -- for reports: no_shop | gone | moved | closed_wrong | other
  status  TEXT NOT NULL DEFAULT 'new',  -- new | approved | rejected
  created TEXT NOT NULL                 -- ISO-8601 timestamp
);

CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_suggestions_kind   ON suggestions(kind);
