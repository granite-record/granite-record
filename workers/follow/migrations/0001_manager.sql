-- The manage page's two settings (11 October 2026), for a follow database
-- made from schema.sql before they were in it. Run ONCE on each database that
-- was already there -- graniterecord-follow-preview and graniterecord-follow
-- were made on 10 and 11 October -- and never on one made from today's
-- schema.sql, which has them already (SQLite answers "duplicate column name",
-- and nothing changes). README.md has the commands.
--
--   paused_until  New Hampshire date nothing is sent through; NULL is not
--                 paused, 9999-12-31 is until the reader turns it back on
--   detail        'all', or 'milestones': hearings scheduled, committee and
--                 floor votes, and how a bill ended (CHANGES_FORMAT.md)

ALTER TABLE subscribers ADD COLUMN paused_until TEXT;
ALTER TABLE subscribers ADD COLUMN detail TEXT NOT NULL DEFAULT 'all'
  CHECK (detail IN ('all', 'milestones'));
