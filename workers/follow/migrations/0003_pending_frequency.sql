-- The sign-up box's choice of daily or weekly (16 October 2026), kept with a
-- request until its confirmation gives it to the new subscriber. Until then a
-- sign-up always became daily, and weekly could be chosen only on the manage
-- page. For a follow database made from schema.sql before this date --
-- graniterecord-follow-preview and graniterecord-follow both were -- and
-- never one made from today's schema.sql, which has it already (SQLite
-- answers "duplicate column name", and nothing changes). README.md has the
-- commands.
--
-- RUN IT BEFORE THE FUNCTIONS THAT READ AND WRITE IT DEPLOY: on the preview
-- before any dev dry run of them, since every dry run deploys the preview with
-- the database bound. On a database without this column both halves fail,
-- and nothing offline can tell. signup.js keeps a request after its answer has
-- gone, so every sign-up is answered "on its way", sends nothing, and logs
-- only "follow signup.error.Error". confirm.js reads the column back, so every
-- confirmation -- a link from a request made before the deploy included --
-- answers "Something went wrong on our side" and logs only
-- "follow confirm.error.Error". A request already waiting when this runs
-- takes the default, 'daily', which is what it was asked as.

ALTER TABLE pending ADD COLUMN frequency TEXT NOT NULL DEFAULT 'daily'
  CHECK (frequency IN ('daily', 'weekly'));
