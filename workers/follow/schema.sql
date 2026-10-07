-- What email following keeps, in its own D1 database, apart from the reports.
--
-- Applied once to each database, by hand (README.md has the commands):
--   npx wrangler d1 execute graniterecord-follow --remote --file workers/follow/schema.sql
--   npx wrangler d1 execute graniterecord-follow-preview --remote --file workers/follow/schema.sql
-- IF NOT EXISTS throughout, so applying it again changes nothing.
--
-- WHAT IDENTIFIES A READER: two columns, and only these two. email_enc is the
-- address sealed with AES-GCM (address.js); email_hmac is a keyed hash of it,
-- which finds a second sign-up of the same address without opening the first.
-- Both appear in subscribers and in pending. There is no column for a name,
-- an IP address, a cookie, a browser or a referrer, and adding one is a
-- decision about the About page's promise, not about this schema.
--
-- WHAT IS KEPT HOW LONG. A request not confirmed within 48 hours is deleted
-- (sender.js purges every hour). An unsubscribe, a bounce or a complaint
-- deletes the subscriber, every follow, every link and every pending request
-- of that address at once. A bill that concludes ends its follows after the
-- last email about it. The send log is counts.
--
-- Times are ISO 8601 UTC ("2026-10-06T12:00:03Z"); days are YYYY-MM-DD.

-- A confirmed reader. Only a confirmation creates one, so every row here is
-- confirmed, and the count endpoint counts rows.
CREATE TABLE IF NOT EXISTS subscribers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email_hmac    TEXT NOT NULL UNIQUE,   -- HMAC-SHA-256 of the address, lower-cased, hex
  email_enc     TEXT NOT NULL,          -- v1.<nonce>.<ciphertext>, AES-GCM, base64url
  frequency     TEXT NOT NULL DEFAULT 'daily' CHECK (frequency IN ('daily', 'weekly')),
  confirmed_at  TEXT NOT NULL,          -- when the first confirmation arrived
  last_sent_on  TEXT,                   -- New Hampshire date of the last scheduled run that took this row
  sent_date     TEXT,                   -- the cursor: the newest night already sent...
  sent_built    TEXT                    -- ...and the build that wrote it (CHANGES_FORMAT.md)
);

-- A request to follow something, waiting for its confirmation email to be
-- clicked. One row per request; the same address may have a few at once.
CREATE TABLE IF NOT EXISTS pending (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  email_hmac          TEXT NOT NULL,
  email_enc           TEXT NOT NULL,
  follow_kind         TEXT NOT NULL CHECK (follow_kind IN ('bill', 'member', 'committee', 'topic')),
  follow_ref          TEXT NOT NULL,
  confirm_token_hash  TEXT NOT NULL UNIQUE,  -- SHA-256 of the token in the email, hex
  created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pending_hmac ON pending(email_hmac);
CREATE INDEX IF NOT EXISTS pending_created ON pending(created_at);

-- What a subscriber follows. kind and ref are the record's own key, the one
-- its page and feed use: bill 2026/HB1442, member 736, committee H05, topic
-- housing.
CREATE TABLE IF NOT EXISTS follows (
  subscriber_id  INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
  kind           TEXT NOT NULL CHECK (kind IN ('bill', 'member', 'committee', 'topic')),
  ref            TEXT NOT NULL,
  since          TEXT NOT NULL,
  PRIMARY KEY (subscriber_id, kind, ref)
);

-- The private links. Every email the sender writes carries a fresh manage
-- link and a fresh unsubscribe link, because a link cannot be rebuilt from
-- its hash; "send me a new link" deletes every one of an address's links and
-- makes one of each. A manage link lasts 60 days and an unsubscribe link 180,
-- except that an address's newest link of each purpose always works.
CREATE TABLE IF NOT EXISTS links (
  token_hash     TEXT PRIMARY KEY,     -- SHA-256 of the token, hex
  subscriber_id  INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
  purpose        TEXT NOT NULL CHECK (purpose IN ('manage', 'unsubscribe')),
  created_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS links_subscriber ON links(subscriber_id, purpose, created_at);

-- What each scheduled run did, in counts. No recipient, no record.
CREATE TABLE IF NOT EXISTS sends (
  date         TEXT NOT NULL,          -- New Hampshire date of the run
  frequency    TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly')),
  emails_sent  INTEGER NOT NULL DEFAULT 0,
  items        INTEGER NOT NULL DEFAULT 0,
  failed       INTEGER NOT NULL DEFAULT 0,
  ended        INTEGER NOT NULL DEFAULT 0,  -- follows ended because their record concluded
  PRIMARY KEY (date, frequency)
);

-- The day's ceiling on confirmation emails, counted and raised in one
-- statement, as reports/schema.sql's report_days is.
CREATE TABLE IF NOT EXISTS signup_days (
  day  TEXT PRIMARY KEY,               -- YYYY-MM-DD, UTC
  n    INTEGER NOT NULL
);
