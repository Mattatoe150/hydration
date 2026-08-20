-- Match the public feed and per-IP rate-limit query shapes.
CREATE INDEX IF NOT EXISTS idx_suggestions_feed
  ON suggestions(kind, status, created DESC);
CREATE INDEX IF NOT EXISTS idx_suggestions_rate_limit
  ON suggestions(iphash, created);
