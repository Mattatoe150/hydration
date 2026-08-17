-- D1 schema for community spot suggestions.
-- Apply with:  npx wrangler d1 execute hydration --remote --file=schema.sql

CREATE TABLE IF NOT EXISTS suggestions (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  lat     REAL NOT NULL,
  lon     REAL NOT NULL,
  cat     TEXT NOT NULL,              -- water | vending | shop | fuel
  name    TEXT,
  note    TEXT,
  status  TEXT NOT NULL DEFAULT 'new',-- new | approved | rejected
  created TEXT NOT NULL               -- ISO-8601 timestamp
);

CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
