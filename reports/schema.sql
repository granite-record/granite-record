-- GRANITE_VERSION: 2026-09-12.2
-- What a reader's report is, as stored by functions/api/report.js.
--
-- Applied once to each database, by hand:
--   npx wrangler d1 execute graniterecord-reports --remote --file reports/schema.sql
--   npx wrangler d1 execute graniterecord-reports-preview --remote --file reports/schema.sql
-- IF NOT EXISTS throughout, so applying it again changes nothing.
--
-- Nothing here identifies a reader. There is no column for an address, a
-- cookie, a session, a name or an email, and adding one is a decision about
-- the About page's promise, not about this schema.

CREATE TABLE IF NOT EXISTS reports (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,  -- monotonic: the nightly's cursor
  at      TEXT NOT NULL,      -- ISO 8601, the server's clock
  record  TEXT NOT NULL,      -- bill:2026/HB100 | member:736 | committee:H05
  kind    TEXT NOT NULL,      -- bill | member | committee
  url     TEXT NOT NULL,      -- the page's own path, /bill/2026/hb100
  tab     TEXT NOT NULL,      -- the tab that was open, counts stripped, or ''
  field   TEXT NOT NULL,      -- what is wrong, from the fixed list
  note    TEXT NOT NULL,      -- the reader's words: UNTRUSTED, normalised, <= 1000
  build   TEXT NOT NULL,      -- site/build.json "finished", or ''
  hidden  INTEGER NOT NULL DEFAULT 0,  -- 1 if invisible characters were removed
  dedup   TEXT NOT NULL       -- sha256 of the UTC day, record, field and the note, lowercased
);

CREATE UNIQUE INDEX IF NOT EXISTS reports_dedup ON reports(dedup);
CREATE INDEX IF NOT EXISTS reports_at ON reports(at);

-- The daily ceiling, counted in one row per day and raised in the same
-- statement that checks it (INSERT ... ON CONFLICT ... WHERE n < ceiling
-- RETURNING n). Counting the day's reports before inserting let simultaneous
-- posts all read 499 and all go in, and made every post read the whole day.
CREATE TABLE IF NOT EXISTS report_days (
  day  TEXT PRIMARY KEY,      -- YYYY-MM-DD, UTC
  n    INTEGER NOT NULL
);
