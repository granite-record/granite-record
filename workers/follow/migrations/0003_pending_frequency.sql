-- The sign-up box's choice of daily or weekly (16 October 2026), kept with a
-- request until its confirmation gives it to the new subscriber. Until then a
-- sign-up always became daily, and weekly could be chosen only on the manage
-- page. For a follow database made from schema.sql before this date --
-- graniterecord-follow-preview and graniterecord-follow both were -- and
-- never one made from today's schema.sql, which has it already (SQLite
-- answers "duplicate column name", and nothing changes). README.md has the
-- commands.
--
-- RUN IT BEFORE THE FUNCTIONS THAT WRITE IT DEPLOY. signup.js keeps a request
-- after its answer has gone, so on a database without this column every
-- sign-up is answered "on its way", sends nothing, and logs only
-- "follow signup.error.Error"; and confirm.js reads the column back. A
-- request already waiting when this runs takes the default, 'daily', which is
-- what it was asked as.

ALTER TABLE pending ADD COLUMN frequency TEXT NOT NULL DEFAULT 'daily'
  CHECK (frequency IN ('daily', 'weekly'));
