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
| `schema.sql` | The D1 tables: `subscribers`, `pending`, `follows`, `sends`, `signup_days`. |
| `address.js` | Sealing an address and what it follows (AES-GCM), the keyed hashes (HMAC-SHA-256) of an address, its inbox and its follows, the derived manage and unsubscribe links, random tokens and their hashes, constant-time comparison. |
| `common.js` | What a follow is, the log (`note`), the site's own names, headers, escaping, New Hampshire's clock. |
| `store.js` | Database calls more than one endpoint makes: forgetting an address, finding the reader a link belongs to, the purge, the count, the day's ceiling. |
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
  without opening anything. In `pending` only, a second keyed hash of the
  inbox the address reaches (its `+tag` and Gmail's dots removed) counts
  requests, so one inbox gets at most three confirmations however its
  address is spelled.
- **What is followed is sealed too.** A followed record's key is sealed under
  the same key, bound to its reader, beside a keyed hash of reader and
  record. Read without the keys -- in the D1 dashboard, or by anyone or any
  session holding this account's wrangler login -- no table shows a follow
  list, or that two readers follow one record. Days are kept where a moment
  is not needed (a confirmation, a follow).
- **The same two links in every email.** The manage and unsubscribe links
  are an HMAC of the reader and a generation number under a key derived
  from `FOLLOW_ADDRESS_KEY` (HKDF), so the sender makes the same links for
  every email without storing them; only their SHA-256 is kept, to find the
  reader. They do not expire. "Send me a new link" moves the generation on
  in one statement, which changes both, and every earlier link -- in every
  earlier email, unsubscribe links included -- matches nothing; pressed twice
  at once, it sends one email. A confirmation link is 32 random bytes, kept
  as its hash, and works once for 48 hours.
- **Where a token can be seen.** A token travels after `#` in every link in
  an email's body, which a browser does not send to a server, so those
  requests' addresses carry none; the page's script reads it, posts it in the
  body, and takes it out of the address bar and the history. **The one
  exception is the `List-Unsubscribe` header**, whose address the mail
  provider POSTs to: its unsubscribe token is in the query string, and so in
  Cloudflare's request log for that request (`wrangler tail`, Workers Logs).
  That token can do nothing but delete the address. The provider's one-click
  POST spends it by deleting the address; a GET of it (a client that opens
  it in a browser) shows the button and leaves the token current until the
  reader asks for a new link.
- **Deleting, and what it does not reach.** A request not confirmed in 48
  hours is deleted. Unsubscribing, a bounce or a complaint deletes the
  subscriber, its follows and its waiting requests from the database at once.
  Two copies are not deleted at once, and the pages say so rather than "for
  good": **D1's Time Travel** keeps point-in-time backups that cannot be
  turned off (30 days on Workers Paid, 7 on Free, as remembered -- check on
  the day; the pages say "at most 30 days"), and **Resend** keeps each email
  it has sent -- recipient and content -- for its plan's retention period. A
  Time Travel restore would bring back every address deleted since its point
  in time, so a restore of this database is never a routine repair. A record
  that concludes gets one last update saying how it ended, and its follow
  ends; an address whose last follow ends is deleted with it, and that email
  says so.
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

   **The two keys** are made by a command, so that nobody types or reads one,
   and they do not go through the clipboard: any program running at that
   moment can read it, a concurrent Claude session included, and Windows'
   clipboard history (Win+V) and "sync across your devices" keep copies
   outside the one password-manager copy. With the address key and this
   account's D1 access, every address opens. So, first: **close every Claude
   session on this machine**, and check Settings > System > Clipboard that
   clipboard history and sync are off.

   Then, in PowerShell (type `powershell` at the `cmd` prompt), in the
   repository folder, for production -- the key lives in a variable and is
   never printed:

       $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); $k = [Convert]::ToBase64String($b); $b = $null
       $k | npx wrangler pages secret put FOLLOW_ADDRESS_KEY --project-name graniterecord
       $k | npx wrangler secret put FOLLOW_ADDRESS_KEY --config workers/follow/wrangler.toml

   The password manager's copy: if it has a command-line tool, pipe `$k` to
   it. If not, `Set-Clipboard -Value $k`, paste it into the manager, and at
   once `Set-Clipboard -Value " "` -- only with history and sync confirmed
   off. Then `$k = $null`, the same again for `FOLLOW_LOOKUP_KEY` (the Pages
   project only), and close the window.

   The preview's keys are separate, and need no copy. A key cannot be read
   back out of Cloudflare: without the copy, moving the sender to a new
   account means every subscriber signs up again. The links in emails are
   derived from `FOLLOW_ADDRESS_KEY`, so a new address key also changes
   every reader's links.

6. **The plan's limits**, from Cloudflare's and Resend's own pages on the
   day, because the figures here are remembered, not checked: D1's
   statements per Worker invocation (50 on Workers Free, 1,000 on Paid) goes
   in `D1_QUERIES_PER_RUN`, the subrequests per invocation bound
   `SEND_LIMIT`, and Resend's daily cap (100 on its free plan) is shared by
   confirmations and updates. D1 Time Travel's window and Resend's retention
   of sent emails are what the About page and the pages' "at most 30 days"
   must agree with.

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

## What reads this database, and what must not

Nothing but the Functions and the sender. Applying `schema.sql` is the one
`wrangler d1 execute` ever run against `graniterecord-follow`: no script, no
report and no Claude session queries it, although this machine's wrangler
login (the one `publish` and `compile_reports.py` use) could. Sealing means
such a query shows hashes and ciphertext, not addresses or follow lists, but
a query is still a look, and the person's line is that nobody looks.
`preflight_checks_to_add.md` (in the assistant's scratchpad) has the check
that no tracked file runs one.

## Before go-live: the person's decisions

These need the person, not code:

- **Resend's dashboard shows each email.** Every email goes to Resend with
  its recipient and its content -- what the reader follows, by name -- and
  Resend's Emails view keeps both for its plan's retention period, readable
  by anyone logged into that account, links included. Sealing the database
  cannot reach that copy. Either the About page says plainly that the mail
  service holds each email for a limited time, or the Resend login is kept
  out of day-to-day use, or both; the About draft's "nobody here ... sees
  what you follow" should not go up as it is.
- **The About page's words for deleting** must match the pages': deleted
  from our database at once; the database's backups age out within at most
  30 days; the mail service's copies of sent emails age out on its schedule.
- **One link per reader**, as FOLLOW.md designed it: every email carries the
  same manage link until the reader asks for a new one, so a forwarded email
  opens the reader's manage page (their follow list, never their address)
  until they do. The manage page says so.

### One thing to check on the first preview deploy

The Functions import this folder by a relative path out of `functions/`.
Whether Pages' bundler follows such an import has not been tried. If it does
not, copy every `.js` here but `sender.js` into a folder under `functions/`
whose files export no `onRequest` handler (`functions/_follow/`), point the
imports there, and have preflight hold the copies byte-identical to these.

## The front end's side

The Turnstile widget's site key, public, for both graniterecord.org and the
dry-run preview (the person, 11 October 2026): `0x4AAAAAAFTdC20uymy0Ut8h`.
Its secret is `TURNSTILE_SECRET`, on Cloudflare only.

The Follow control posts what the reader typed, and stores nothing:

    POST /api/follow/signup
    Content-Type: application/json
    {"email": "...", "kind": "bill", "ref": "2026/HB1442",
     "turnstile": "<the widget's token>", "website": ""}

`website` is a honeypot: an input a person never sees, left empty. The
answers:

| Status | Body | Means |
|---|---|---|
| 202 | `{"ok":true}` | Accepted -- whatever the address. The request is kept and the email sent after the answer, so the answer takes as long for every address; if the inbox already has three waiting, or Resend refuses, nothing arrives and the log says which. The box should say "if this address can take it, a confirmation is on its way". |
| 400 | `{"ok":false,"why":"invalid"}` | Not an address, or not a record key. |
| 400 | `{"ok":false,"why":"check"}` | Turnstile said no; try again. |
| 400 | `{"ok":false,"why":"not-followable"}` | Not followable tonight. |
| 429 | `{"ok":false,"why":"busy"}` | The day's confirmation emails are used up. |
| 503 | `{"ok":false,"why":"unavailable"}` | The changes file, the database or a secret failed on our side. |

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
| `follow sender.resend-refused.429 1` | Resend refused, with its status; the rest wait for the next run, and the refused go first tomorrow. |
| `follow sender.query-budget-reached 6` | The run's D1 statements are spent; these readers wait for the next hour. |
| `follow sender.after-send-failed.Error 1` | An email went, and the cursor or ended follows could not be written twice over; tomorrow's email repeats its news. |
| `follow sender.error.ConfigError 1` | A secret or `MAIL_FROM` is missing. |
| `follow signup.sent 1`, `follow confirm.confirmed 1` | One confirmation emailed; one confirmed. |
| `follow signup.waiting-enough`, `follow signup.day-full` | A request not sent: its inbox has three waiting, or the day's ceiling is reached. |
| `follow unsubscribe.one-click-matched-nothing` | A provider's one-click carried a link that is no longer current; nothing was deleted. |
| `follow manage.new-link-already-moving` | "Send me a new link" pressed twice at once; one email went. |
| `follow bounce.forgot 1`, `follow complaint.forgot 1` | Addresses deleted by Resend's webhook. |
| `follow bounce.unsigned` | A post to the webhook that was not Resend's. |
