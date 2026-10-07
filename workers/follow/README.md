# Following by email

A reader who follows a bill, a legislator, a committee or a topic can ask for
email updates, daily or weekly. This folder and `functions/api/follow/` are
everything that does it, and the only code on the site that keeps a reader's
address. Nothing outside these two folders stores, reads back or sends to an
address.

The record itself refreshes once a night, so an update reports what changed
up to last night's build. Nothing here implies real time.

## What is here

| File | What it does |
|---|---|
| `schema.sql` | The D1 tables: `subscribers`, `pending`, `follows`, `links`, `sends`, `signup_days`. |
| `address.js` | Sealing an address (AES-GCM), its keyed lookup hash (HMAC-SHA-256), random tokens and their hashes, constant-time comparison. |
| `common.js` | What a follow is, the log (`note`), the site's own names, headers, escaping, New Hampshire's clock. |
| `store.js` | Database calls more than one endpoint makes: forgetting an address, links, the purge, the count, the day's ceiling. |
| `changes.js` | Reading the site's `/changes/` files and holding them to `CHANGES_FORMAT.md`. |
| `mail.js` | The one call to Resend, and the confirmation, new-link, daily and weekly emails, in plain text and simple HTML. |
| `page.js` | The HTML of the confirm, manage and unsubscribe pages. |
| `sender.js` | The scheduled Worker that sends the daily and weekly emails. |
| `wrangler.toml` | The sender's own configuration: cron, the D1 binding, plain settings. No secret. |
| `CHANGES_FORMAT.md` | The contract for the files the nightly build publishes under `/changes/`, which are all the sender reads. |

And under `functions/api/follow/`, Pages Functions on the site's own origin:

| Address | What it does |
|---|---|
| `POST /api/follow/signup` | Keeps a request (sealed) and emails a confirmation link. Its answer never depends on the address. |
| `/api/follow/confirm` | GET shows one button; POST turns the request into a follow. |
| `/api/follow/manage` | The reader's private page: what they follow, how often, a new link, unsubscribe. |
| `/api/follow/unsubscribe` | Deletes the address and everything it follows, at once. Takes the mail provider's one-click POST (RFC 8058). |
| `GET /api/follow/count` | The number of confirmed subscribers, as one integer. The only figure that leaves the database. |
| `POST /api/follow/bounce` | Resend's webhook. A signed bounce or complaint deletes the address. |

Every Function answers 404 until the `FOLLOW_DB` binding exists on the
deployment, so a deployment without the database has no follow endpoints.

## How a reader's data is kept

- **The address** is stored only sealed with AES-GCM under
  `FOLLOW_ADDRESS_KEY`, beside an HMAC-SHA-256 of it under
  `FOLLOW_LOOKUP_KEY`. The hash finds a second request from the same address
  without opening anything. These two columns, in `subscribers` and
  `pending`, are the only ones about a reader.
- **Links are tokens**: 32 random bytes, of which only the SHA-256 is stored.
  A token travels after `#` in every link, which a browser does not send to
  a server, so no request address -- and so no Cloudflare log -- carries one.
  The page's script reads it and posts it in the body. The one exception is
  the `List-Unsubscribe` header, whose address the mail provider POSTs to; it
  carries an unsubscribe token, good only for deleting, and spent by that
  request.
- **Each email carries fresh links.** A link cannot be rebuilt from its hash,
  so the sender makes a manage link and an unsubscribe link for every email.
  A manage link lasts 60 days and an unsubscribe link 180, and an address's
  newest link always works. "Send me a new link" deletes every link the
  address has and emails one new pair.
- **Nothing is kept longer than it is needed.** A request not confirmed in 48
  hours is deleted. Unsubscribing, a bounce or a complaint deletes the
  subscriber, its follows, links and waiting requests at once. A bill that
  concludes gets one last update saying how it ended, and its follow ends;
  an address whose last follow ends is deleted with it, and that email says so.
- **The log is codes and counts.** Every line is `follow <code>` or
  `follow <code> <n>`, written by `common.note` and nowhere else. An error is
  logged by its name only, never its message: Resend's error messages name
  the address they refused.
- **No reply address.** Emails say to use the report box on a record's page,
  or the feedback form.

`tests/follow/` holds each of these as a test, and runs with
`node --test tests/follow/`, standard library only.

## Who deploys it

A person, by hand, never `publish` or the nightly. The Functions deploy with
the site once the root `wrangler.toml` binds `FOLLOW_DB`; the sender deploys
on its own:

    npx wrangler deploy --config workers/follow/wrangler.toml
    npx wrangler deploy --config workers/follow/wrangler.toml --env preview

### Once, before the first deploy

1. **The databases.** `npx wrangler d1 create graniterecord-follow` and
   `npx wrangler d1 create graniterecord-follow-preview`. Put each id into
   `workers/follow/wrangler.toml` where it says FILL IN, and into the root
   `wrangler.toml` (below). Then apply the schema to both:

       npx wrangler d1 execute graniterecord-follow --remote --file workers/follow/schema.sql
       npx wrangler d1 execute graniterecord-follow-preview --remote --file workers/follow/schema.sql

2. **Resend.** A verified sending domain; an API key restricted to sending
   from it; a webhook to `https://graniterecord.org/api/follow/bounce` for
   the events `email.bounced` and `email.complained`, whose signing secret is
   `RESEND_WEBHOOK_SECRET`. Set `MAIL_FROM` to the sending address, as
   `Granite Record <name@your-verified-domain>`, in both `wrangler.toml`s.

3. **Turnstile.** A widget for the site's names (and the preview's). Its site
   key is public and goes in the front end; its secret is `TURNSTILE_SECRET`.

4. **A rate rule** on the zone for `/api/follow/signup`, as the report box
   has for `/api/report`. It needs no address and keeps none.

5. **The secrets**, set with wrangler, never written in a file. Names only:

   | Secret | Pages project | Sender |
   |---|---|---|
   | `RESEND_API_KEY` | yes | yes |
   | `FOLLOW_ADDRESS_KEY` (32 random bytes, base64) | yes | yes, the same value |
   | `FOLLOW_LOOKUP_KEY` (32 random bytes, base64) | yes | no |
   | `TURNSTILE_SECRET` | yes | no |
   | `RESEND_WEBHOOK_SECRET` | yes | no |

   On the Pages project: `npx wrangler pages secret put <NAME> --project-name
   graniterecord` (and the same for preview; check `--help` on the day for
   how the version installed names it). On the sender: `npx wrangler secret
   put <NAME> --config workers/follow/wrangler.toml` (add `--env preview`).
   Both read the value from standard input when it is piped.

   **The two keys** are made by a command, so that nobody types or reads one.
   In `cmd`, for production, where one copy goes into a password manager:

       node -e "process.stdout.write(require('crypto').randomBytes(32).toString('base64'))" | clip

   paste it into the password manager, then hand the same clipboard to both
   places that need it and clear it:

       powershell -NoProfile -Command "Get-Clipboard" | npx wrangler pages secret put FOLLOW_ADDRESS_KEY --project-name graniterecord
       powershell -NoProfile -Command "Get-Clipboard" | npx wrangler secret put FOLLOW_ADDRESS_KEY --config workers/follow/wrangler.toml
       echo.| clip

   and once more for `FOLLOW_LOOKUP_KEY`, which only the Pages project gets.
   The preview's keys are separate, and need no copy. A key cannot be read
   back out of Cloudflare: without the copy, moving the sender to a new
   account means every subscriber signs up again.

### The root `wrangler.toml`, at go-live

The Functions need the database bound on the Pages project, production and
preview each stating their own, as the reports database is:

```toml
[[env.production.d1_databases]]
binding = "FOLLOW_DB"
database_name = "graniterecord-follow"
database_id = "<from wrangler d1 create>"

[[env.preview.d1_databases]]
binding = "FOLLOW_DB"
database_name = "graniterecord-follow-preview"
database_id = "<from wrangler d1 create>"
```

and, in each environment's `vars`, `MAIL_FROM` and `FEEDBACK_URL` as the
sender has them. The site's names come from `REPORT_ORIGINS`, which each
environment already sets; `FOLLOW_ORIGINS` overrides it for following alone.
`SIGNUP_DAILY_CEILING` (default 50) caps confirmation emails a day.

### One thing to check on the first preview deploy

The Functions import this folder by a relative path out of `functions/`.
Whether Pages' bundler follows such an import has not been tried. If it does
not, copy every `.js` here but `sender.js` into a folder under `functions/`
whose files export no `onRequest` handler (`functions/_follow/`), point the
imports there, and have preflight hold the copies byte-identical to these.

## The front end's side

The Follow control posts what the reader typed, and stores nothing:

    POST /api/follow/signup
    Content-Type: application/json
    {"email": "...", "kind": "bill", "ref": "2026/HB1442",
     "turnstile": "<the widget's token>", "website": ""}

`website` is a honeypot: an input a person never sees, left empty. The
answers:

| Status | Body | Means |
|---|---|---|
| 202 | `{"ok":true}` | A confirmation is on its way -- whatever the address. |
| 400 | `{"ok":false,"why":"invalid"}` | Not an address, or not a record key. |
| 400 | `{"ok":false,"why":"check"}` | Turnstile said no; try again. |
| 400 | `{"ok":false,"why":"not-followable"}` | Not followable tonight. |
| 429 | `{"ok":false,"why":"busy"}` | The day's confirmations are used up. |
| 503 | `{"ok":false,"why":"unavailable"}` | Something failed on our side. |

## Reading the log

`npx wrangler tail graniterecord-follow-sender` shows lines like these, and
nothing a person could read a name in:

| Line | Means |
|---|---|
| `follow sender.sent 12` | Emails sent this run. |
| `follow sender.follows-ended 2` | Follows ended because their record concluded. |
| `follow sender.purged 3` | Unconfirmed requests deleted. |
| `follow sender.waiting-for-tonight 40` | Tonight's changes file is not published yet; tried again next hour until noon. |
| `follow sender.tonight-missing-sending-anyway 40` | Noon, and still no file: sent what earlier nights had. |
| `follow sender.nights-missing 2` | Nights in the window with no file. |
| `follow sender.entries-dropped-or-mended 1` | The changes files broke their format somewhere; `tests/follow/check_changes.js` says where. |
| `follow sender.resend-refused.429 1` | Resend refused, with its status; the rest wait for the next run. |
| `follow sender.error.ConfigError 1` | A secret or `MAIL_FROM` is missing. |
| `follow signup.sent 1`, `follow confirm.confirmed 1` | One confirmation emailed; one confirmed. |
| `follow bounce.forgot 1`, `follow complaint.forgot 1` | Addresses deleted by Resend's webhook. |
| `follow bounce.unsigned` | A post to the webhook that was not Resend's. |
