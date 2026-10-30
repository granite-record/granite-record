# workers/

Cloudflare Workers deployed on their own, each in its own folder with its
own `wrangler.toml`; a person deploys one with
`wrangler deploy --config workers/<name>/wrangler.toml`, never `publish` or
the night.

- `follow/`: email following. The email sender (daily and Saturday runs), the
  follow database's schema, and the address and token helpers it shares with
  `functions/api/follow/`. With `functions/api/follow/`, it is the only code
  that stores, reads back or sends to a subscriber's address, and preflight
  fails if anything under `src/` or at the root names the follow database.
- `night-timer/`: starts the nightly at 08:17 UTC (since 23 October 2026,
  when GitHub's own schedule had begun starting it hours late). One secret, a
  token that can only start this repository's workflows; it stores nothing.
- `live/`: Live Now's data (approved by the person on 26 October 2026). Every
  two minutes it asks YouTube's Data API which House and Senate streams are
  live and writes the day's list to the private R2 bucket
  `graniterecord-live`, where `control.json`, written only by a person, is
  its switch. Deployed with `--env production`, the only configuration with a
  cron; its README says how, and preflight's `_live_layer` holds it.

Does not belong here: a page endpoint (`functions/`, which Cloudflare Pages
requires at the root), anything the build runs (`src/`).
