-- The sender's hourly question (15 October 2026): who of this frequency is
-- not yet sent today, least recently served first (sender.js run). With few
-- readers a scan answers it as fast; with thousands, an index does it without
-- reading every row, inside the run's statement budget's time. For a follow
-- database made from schema.sql before this date -- graniterecord-follow-preview
-- and graniterecord-follow both were. Safe to run again, or on a database
-- made from today's schema.sql: IF NOT EXISTS makes it a no-op there.
-- README.md has the commands.

CREATE INDEX IF NOT EXISTS subscribers_due ON subscribers(frequency, last_sent_on);
