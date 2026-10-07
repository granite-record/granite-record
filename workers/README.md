# workers/

Cloudflare Workers deployed on their own, each in its own folder with its
own `wrangler.toml`; a person deploys one with
`wrangler deploy --config workers/<name>/wrangler.toml`, never `publish` or
the night. The first will be `workers/follow/`, with email following: the
email sender (daily and Saturday runs), the follow database's schema, and the
address and token helpers it shares with `functions/api/follow/`. With
`functions/api/follow/`, it will be the only code that stores, reads back or
sends to a subscriber's address, and preflight will fail if anything under
`src/` or at the root names the follow database.

Empty until then. Does not belong here: a page endpoint (`functions/`, which
Cloudflare Pages requires at the root), anything the build runs (`src/`).
