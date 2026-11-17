-- What the shared bench keeps, in a D1 database of its own (binding BENCH_DB),
-- apart from the reports and the follows.
--
-- Applied once to each database, by hand (README.md has the commands):
--   npx wrangler d1 execute graniterecord-bench --remote --file workers/bench/schema.sql
--   npx wrangler d1 execute graniterecord-bench-preview --remote --file workers/bench/schema.sql
-- IF NOT EXISTS throughout, so applying it again changes nothing.
--
-- WHAT IS KEPT ABOUT A PERSON: the name the owner gives a link, the day it was
-- made and the day it was last used. There is no column for an email address,
-- an IP address, a cookie, a device, a browser or a referrer, and adding one
-- is a decision about the page's promise ("nothing else about you is kept"),
-- not about this schema. A link's token is never kept: only its SHA-256, which
-- finds the link a request carries in one indexed read.
--
-- WHAT IS ANSWERED BECOMES OPEN DATA, with no name on it: the owner merges an
-- answer into review/checked.jsonl (src/checks/bench_pull.py) under the
-- link's id, never its name.
--
-- Times are ISO 8601 UTC with milliseconds ("2026-11-20T19:04:12.345Z");
-- days are YYYY-MM-DD, UTC.

-- One link a person. The owner's own link (role 'owner') is made on the laptop
-- (bench_pull.py --owner-link); every other is made on the owner's Links page.
CREATE TABLE IF NOT EXISTS links (
  id          TEXT PRIMARY KEY,             -- six letters and digits: what the ledger names
  name        TEXT NOT NULL,                -- what the owner calls the link; never leaves here
  token_hash  TEXT NOT NULL UNIQUE,         -- SHA-256 of the link's token, hex
  role        TEXT NOT NULL CHECK (role IN ('owner', 'contributor')),
  queues      TEXT NOT NULL,                -- JSON array of the queues it may judge
  state       TEXT NOT NULL DEFAULT 'active' CHECK (state IN ('active', 'paused', 'off')),
  made_on     TEXT NOT NULL,                -- day
  last_on     TEXT,                         -- day it was last used
  daily_cap   INTEGER                       -- answers a day; NULL: no cap (the owner's)
);

-- A queue: what the page's chooser names, and how far along the whole of it
-- is -- its pool, and how many of the pool the ledger had judged when the
-- last pack or merge said so (`judged`, as of `as_of`). `options` is the list
-- a No may choose a better answer from (a topic), or NULL.
CREATE TABLE IF NOT EXISTS queues (
  queue    TEXT PRIMARY KEY,                -- timing, topic, tag
  label    TEXT NOT NULL,
  pool     INTEGER NOT NULL,
  judged   INTEGER NOT NULL,
  as_of    TEXT NOT NULL,
  options  TEXT,
  ord      INTEGER NOT NULL
);

-- A group of items worked through together: a tag's thirty, a term's topics,
-- a year's recordings.
CREATE TABLE IF NOT EXISTS groups (
  grp    TEXT PRIMARY KEY,
  queue  TEXT NOT NULL,
  label  TEXT NOT NULL,
  ord    INTEGER NOT NULL
);

-- What to judge, one row a question, loaded by a pack (src/checks/bench_pack.py).
-- SERVED ONCE: claimed by one statement (store.js claimOne) that holds it for
-- one link for ten minutes, renewed while the page is open; an answer marks
-- it judged in the same batch; 'elsewhere' is an item the owner judged on the
-- laptop after it was packed.
CREATE TABLE IF NOT EXISTS items (
  kind        TEXT NOT NULL,                -- the ledger's kind: timestamp, older, topic, tag
  key         TEXT NOT NULL,                -- the ledger's key
  queue       TEXT NOT NULL REFERENCES queues(queue),
  pack        TEXT NOT NULL,                -- the pack that loaded it
  grp         TEXT NOT NULL REFERENCES groups(grp),
  ord         INTEGER NOT NULL,             -- the order it is served in
  card        TEXT NOT NULL,                -- JSON: what the page draws
  shown       TEXT NOT NULL,                -- JSON: the item as the sampler drew it, kept in the ledger
  state       TEXT NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'judged', 'elsewhere')),
  held_by     TEXT REFERENCES links(id),
  held_until  TEXT,
  PRIMARY KEY (kind, key)
);
CREATE INDEX IF NOT EXISTS items_next ON items(state, queue, ord);
CREATE INDEX IF NOT EXISTS items_held ON items(held_by);
CREATE INDEX IF NOT EXISTS items_grp ON items(grp, state);

-- An item the owner has judged already, asked again of a contributor one time
-- in twenty-five, and never of a link that has answered it (calibration).
-- `hers` is which way she went: 'yes' (the site is right) or 'no'. Kept here
-- alone: a calibration answer is never merged into the ledger.
CREATE TABLE IF NOT EXISTS calib (
  kind   TEXT NOT NULL,
  key    TEXT NOT NULL,
  queue  TEXT NOT NULL REFERENCES queues(queue),
  card   TEXT NOT NULL,
  hers   TEXT NOT NULL CHECK (hers IN ('yes', 'no')),
  ord    INTEGER NOT NULL,
  PRIMARY KEY (kind, key)
);

-- A calibration item given to a link and not answered yet.
CREATE TABLE IF NOT EXISTS calib_holds (
  link        TEXT NOT NULL REFERENCES links(id),
  kind        TEXT NOT NULL,
  key         TEXT NOT NULL,
  held_until  TEXT NOT NULL,
  PRIMARY KEY (link, kind, key)
);

-- An answer, in the ledger's words: `verdict` (correct, wrong, unsure; yes,
-- no, unsure for a tag), `fields` (JSON: a time marked, a better topic) and
-- `note`; `side` is which way it went for the agreement measure ('yes' the
-- site is right, 'no', 'unsure'). 'kept' until the owner merges it or it is
-- taken back ('undone').
CREATE TABLE IF NOT EXISTS judgments (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  kind     TEXT NOT NULL,
  key      TEXT NOT NULL,
  link     TEXT NOT NULL REFERENCES links(id),
  verdict  TEXT NOT NULL,
  fields   TEXT NOT NULL DEFAULT '{}',
  note     TEXT NOT NULL DEFAULT '',
  side     TEXT NOT NULL CHECK (side IN ('yes', 'no', 'unsure')),
  at       TEXT NOT NULL,
  calib    INTEGER NOT NULL DEFAULT 0,
  state    TEXT NOT NULL DEFAULT 'kept' CHECK (state IN ('kept', 'undone', 'merged'))
);
CREATE INDEX IF NOT EXISTS judgments_link ON judgments(link, id);
CREATE INDEX IF NOT EXISTS judgments_item ON judgments(kind, key);
CREATE INDEX IF NOT EXISTS judgments_state ON judgments(state);

-- A link's answers on a day, counted and raised in one statement: the daily cap.
CREATE TABLE IF NOT EXISTS link_days (
  link  TEXT NOT NULL REFERENCES links(id),
  day   TEXT NOT NULL,
  n     INTEGER NOT NULL,
  PRIMARY KEY (link, day)
);
