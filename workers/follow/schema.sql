-- What email following keeps, in its own D1 database, apart from the reports.
--
-- Applied once to each database, by hand (README.md has the commands):
--   npx wrangler d1 execute graniterecord-follow --remote --file workers/follow/schema.sql
--   npx wrangler d1 execute graniterecord-follow-preview --remote --file workers/follow/schema.sql
-- IF NOT EXISTS throughout, so applying it again changes nothing.
--
-- WHAT IDENTIFIES A READER: email_enc, the address sealed with AES-GCM
-- (address.js), and email_hmac, a keyed hash of it, which finds a second
-- sign-up of the same address without opening the first; and, in pending
-- only, mailbox_hmac, a keyed hash of the inbox the address reaches, used to
-- count requests and nothing else. There is no column for a name, an IP
-- address, a cookie, a browser or a referrer, and adding one is a decision
-- about the About page's promise, not about this schema.
--
-- WHAT IS FOLLOWED IS SEALED. follow_enc is the record's key sealed under the
-- same key as the address and bound to the reader; follow_hmac is a keyed
-- hash of the reader and the record together. Read without the keys, no
-- table shows what anyone follows, or that two readers follow one record.
-- Days are kept, not moments, where a moment is not needed: a confirmation
-- and a follow by New Hampshire date.
--
-- WHAT IS KEPT HOW LONG. A request not confirmed within 48 hours is deleted
-- (sender.js purges every hour). An unsubscribe, a bounce or a complaint
-- deletes the subscriber, every follow and every pending request of that
-- address from this database at once. D1's own point-in-time backups (Time
-- Travel) cannot be turned off and age out by themselves; README.md says how
-- long. A record that concludes ends its follows after the last email about
-- it. The send log is counts.
--
-- Times are ISO 8601 UTC ("2026-10-06T12:00:03Z"); days are YYYY-MM-DD.

-- A confirmed reader. Only a confirmation creates one, so every row here is
-- confirmed, and the count endpoint counts rows.
--
-- THE PRIVATE LINKS are not stored: the manage and unsubscribe links are made
-- from email_hmac and link_gen under a derived key (address.js linksFor), so
-- every email carries the same two, and only their SHA-256 is kept, to find
-- the reader a link belongs to. "Send me a new link" adds one to link_gen and
-- replaces both hashes in one statement, and every earlier link then matches
-- nothing.
CREATE TABLE IF NOT EXISTS subscribers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  email_hmac    TEXT NOT NULL UNIQUE,   -- HMAC-SHA-256 of the address, lower-cased, hex
  email_enc     TEXT NOT NULL,          -- v1.<nonce>.<ciphertext>, AES-GCM, base64url
  frequency     TEXT NOT NULL DEFAULT 'daily' CHECK (frequency IN ('daily', 'weekly')),
  confirmed_on  TEXT NOT NULL,          -- New Hampshire date of the first confirmation
  link_gen      INTEGER NOT NULL DEFAULT 0,
  manage_hash   TEXT NOT NULL UNIQUE,   -- SHA-256 of the current manage link's token, hex
  unsub_hash    TEXT NOT NULL UNIQUE,   -- SHA-256 of the current unsubscribe link's token, hex
  last_sent_on  TEXT,                   -- New Hampshire date of the last scheduled run that took this row
  sent_date     TEXT,                   -- the cursor: the newest night already sent...
  sent_built    TEXT                    -- ...and the build that wrote it (CHANGES_FORMAT.md)
);

-- A request to follow something, waiting for its confirmation email to be
-- clicked. One row per request; one inbox may have at most three at once.
CREATE TABLE IF NOT EXISTS pending (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  email_hmac          TEXT NOT NULL,
  email_enc           TEXT NOT NULL,
  mailbox_hmac        TEXT NOT NULL,         -- keyed hash of the inbox, for the limit on requests
  follow_enc          TEXT NOT NULL,         -- the record's key, sealed, bound to email_hmac
  confirm_token_hash  TEXT NOT NULL UNIQUE,  -- SHA-256 of the token in the email, hex
  created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS pending_hmac ON pending(email_hmac);
CREATE INDEX IF NOT EXISTS pending_mailbox ON pending(mailbox_hmac);
CREATE INDEX IF NOT EXISTS pending_created ON pending(created_at);

-- What a subscriber follows. The record's key -- bill 2026/HB1442, member 736,
-- committee H05, topic housing, the key its page and feed use -- is in
-- follow_enc, sealed; follow_hmac finds it.
CREATE TABLE IF NOT EXISTS follows (
  subscriber_id  INTEGER NOT NULL REFERENCES subscribers(id) ON DELETE CASCADE,
  follow_hmac    TEXT NOT NULL,         -- HMAC of the reader's email_hmac and the record's key, hex
  follow_enc     TEXT NOT NULL,         -- the record's key, sealed, bound to the reader
  since          TEXT NOT NULL,         -- New Hampshire date
  PRIMARY KEY (subscriber_id, follow_hmac)
);

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
-- statement, as reports/schema.sql's report_days is. Raised only when an
-- email is about to go, so requests that send nothing cannot fill it.
CREATE TABLE IF NOT EXISTS signup_days (
  day  TEXT PRIMARY KEY,               -- YYYY-MM-DD, UTC
  n    INTEGER NOT NULL
);
