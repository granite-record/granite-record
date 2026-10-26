# Following by email

A reader who follows a bill, a legislator, a committee or a topic can ask for
email updates, daily or weekly. This folder and `functions/api/follow/` are
everything that does it, and the only code on the site that keeps a reader's
address. Nothing outside these two folders stores, reads back or sends to an
address.

The record itself refreshes once a night, so an update reports what changed
up to last night's build. Nothing here implies real time.

**Live on graniterecord.org since 23 October 2026**, when the root
`wrangler.toml` bound `FOLLOW_DB` for production, as it does for previews.
That binding is the one switch: the Functions answer only where it is bound,
the sender mails nobody while they do not, the Follow pane offers email only
where `/api/follow/count` answers, and `shell.follow_live()` reads it for
what the About and Data pages and the guides say of email.

## What is here

| File | What it does |
|---|---|
| `schema.sql` | The D1 tables: `subscribers`, `pending`, `follows`, `sends`, `signup_days`. |
| `address.js` | Sealing an address and what it follows (AES-GCM), the keyed hashes (HMAC-SHA-256) of an address, its inbox and its follows, the derived manage and unsubscribe links, random tokens and their hashes, constant-time comparison. |
| `common.js` | What a follow is, the log (`note`), the site's own names, headers, escaping, New Hampshire's clock. |
| `store.js` | Database calls more than one endpoint makes: forgetting an address, finding the reader a link belongs to, the purge, the count, the day's ceiling. |
| `changes.js` | Reading the site's `/changes/` files and holding them to `CHANGES_FORMAT.md`. |
| `mail.js` | The one call to Resend, and the five emails: the confirmation, the "You're following" a confirmation sends, a new link, the daily and the weekly, in plain text and simple HTML; and a test's "nothing new" note, which only the preview's test send sends. |
| `site.gen.js` | Written, not edited: the site's colours and words the emails share, which `src/pages/follow_site.py` reads from the site's own files (below). |
| `page.js` | The HTML of the confirm, manage and unsubscribe pages, in the site's colours from `site.gen.js`. |
| `sender.js` | The scheduled Worker that sends the daily and weekly emails; on the preview only, a test send on request (below). |
| `wrangler.toml` | The sender's own configuration: cron, the D1 binding, plain settings. No secret. |
| `CHANGES_FORMAT.md` | The contract for the files the nightly build publishes under `/changes/`, which are all the sender reads. |

**The site's colours and words** (23 October 2026). What an email shares
with the site is never typed in this folder: `site.gen.js` holds it, written
by `python3 src/pages/follow_site.py` from where the site keeps each one, and
`mail.js` imports it. The inks (`--ink`, `--ink-2`, `--rule`, `--pine`), a
bill status's colour (`--st-*`) and the vote ring's two (`--yes`, `--no`) are
`src/pages/app.css`'s light theme; the word each status chip is coloured by
is `src/pages/words/chips.json`'s `chip`; the testimony forms are
`src/pages/app.js`'s `TESTIFY_FORMS`; a study report's words are
`src/pages/words/study_report.json`'s; the line that says email following
is in beta, and the day it stops (`FOLLOW_BETA`), is
`src/pages/words/follow_beta.json`'s, which the site's Follow by email pane
says too; the mark's file and size are
`src/pages/build_brand.py`'s. To change one, change it there, run that
command and commit `site.gen.js` with the change; `preflight` fails until
the two agree, and names the command. The emails' own choices -- the white
ground, the mark's empty alt, every sentence -- stay in `mail.js`. The
confirm, manage and unsubscribe pages take their colours from the same file
(`PAGE_PALETTE`: app.css's light and dark themes); their font stacks stay in
`page.js`, since those pages load no font.

A digest can be rendered without sending it: `node tests/follow/preview_digest.js [--weekly] [--follow kind:ref ...] [--site URL | --dir site]` reads a site's real `/changes/` files and writes the email's HTML and text, through the sender's own `collect()` and `digestEmail()`, to `preview-mail/`. No database, no Resend, no address. It sits beside the tests because it prints, and nothing in the Worker may.

**Testifying on a bill** (22 October 2026). A bill a reader follows tells them
when its public hearing is set, which is when online testimony opens, and, to
a daily reader, the morning before the hearing and the morning of it, since
in practice the sign-in stays open until midnight at the end of the hearing's
day (the editor's account; no document on record states it). Each says it
with the chamber's form as a button and what to choose on it, the hearing's
date, the committee and the bill (`sender.testifyFor`, `mail.testifyWords`); a
weekly reader has the same beside the hearing in the week ahead.

**In step with the site's Testify button** (26 October 2026; the person:
"Emails should stay in sync with how the site displays the testify
button"). The hearings told are the ones a bill's Testify button counts as
live, read by the build from the bill's own record by the button's rules
(`follow_changes.bill_upcoming`; `CHANGES_FORMAT.md`, `form`) -- a hearing on
a proposed amendment among them, its number a link to it on the Bill Text
tab, and in the plain text an address on a line of its own -- and the block
says what the button's live pane says, in its order and words. The line
that set the hearing is not said again beneath the block (`setsHearing`).
`preflight`'s `_testify_email_in_sync` draws the pane and the block for the
same records -- its own, and every record another check draws a Testify
button for -- and fails where they differ. A change to the pane's words is a
change to `mail.js` too, and reaches inboxes once the sender is deployed
again.

**The logo** at the top of every email is `/mail-mark.png`: the site
header's drawing on a white tile, so a mail app's dark mode cannot hide it.
The site build makes it from `mark.png` (`build_brand.mail_mark`), so it is
on every deployment that has the mark, and `check_site.py` refuses one
without it.

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
They import this folder by a relative path out of `functions/`, which Pages'
bundler follows: the preview's `/api/follow/count` answered 200 on 25
October 2026.

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
  turned off (30 days on Workers Paid, 7 on Free; the pages say "at most 30
  days"), and **Resend** keeps each email it has sent -- recipient and
  content -- for its plan's data retention (30 days on every plan but
  Enterprise). Both figures are in *The plan's limits*, below. A
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
`node --test tests/follow/index.js`, standard library only; `index.js`
imports every test file, and the folder form, `node --test tests/follow/`,
which runs the same file, failed on Node 24 under Windows. `preflight`'s
`_follow_tests` runs it whole and names any test that fails, and fails as
well when a `*.test.js` is missing from `index.js`.

## Who deploys it

A person, by hand, never `publish` or the nightly. The Functions deploy with
the site, which binds `FOLLOW_DB` in both environments; the sender deploys
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

   **A database made before 11 October 2026** needs the manage page's two
   settings (pause, and everything or milestones only) added once, with
   `migrations/0001_manager.sql`. Both of this project's were (preview on 10
   October, production on 11 October), so each takes it once; a database
   made from today's `schema.sql` has them already and must not:

       npx wrangler d1 execute graniterecord-follow-preview --remote --file workers/follow/migrations/0001_manager.sql
       npx wrangler d1 execute graniterecord-follow --remote --file workers/follow/migrations/0001_manager.sql

   **And the sender's index** (15 October 2026), on any database made before
   that day, both of this project's included; running it again changes
   nothing:

       npx wrangler d1 execute graniterecord-follow-preview --remote --file workers/follow/migrations/0002_due_index.sql
       npx wrangler d1 execute graniterecord-follow --remote --file workers/follow/migrations/0002_due_index.sql

   **And the sign-up box's daily or weekly** (16 October 2026), kept with a
   request until its confirmation, on any database made before that day,
   both of this project's included; a database made from today's
   `schema.sql` has it already and must not. **Run it before the Functions
   that read and write it deploy** -- the preview's first, since every dev
   dry run deploys the preview with the database bound, so no dry run of a
   commit with these Functions may start until the preview's has run.
   Without the column both halves fail, and nothing offline can tell: every
   sign-up is answered "on its way", sends nothing, and logs only
   `follow signup.error.Error`; and every confirmation -- a link from a
   request made before the deploy included -- answers "Something went wrong
   on our side. Your link still works for 48 hours." and logs only
   `follow confirm.error.Error`, because confirm.js reads the column back.

       npx wrangler d1 execute graniterecord-follow-preview --remote --file workers/follow/migrations/0003_pending_frequency.sql
       npx wrangler d1 execute graniterecord-follow --remote --file workers/follow/migrations/0003_pending_frequency.sql

   `0001` and `0003` add columns: run a second time, each answers "duplicate
   column name" and changes nothing.

2. **Resend.** A verified sending domain; an API key restricted to sending
   from it; a webhook to `https://graniterecord.org/api/follow/bounce` for
   the events `email.bounced` and `email.complained`, whose signing secret is
   `RESEND_WEBHOOK_SECRET`. Set `MAIL_FROM` to the sending address, as
   `Granite Record <name@your-verified-domain>`, in both `wrangler.toml`s.
   **Open and click tracking off** for the sending domain (22 October 2026):
   the Data page promises the emails do not track opens or clicks, and click
   tracking would send every manage and confirm link through Resend's own
   redirect. And the team's API rate limit, which `SEND_GAP_MS` in
   `workers/follow/wrangler.toml` keeps to half of: 10 requests a second,
   the same on every plan (item 6).

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
   | `HEALTHCHECK_URL` (a Healthchecks check of its own, hourly period) | no | yes |
   | `TEST_SEND_TOKEN` (the test send's, below) | no | the preview's only |

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

6. **The plan's limits**, as Cloudflare and Resend publish them, read on 25
   October 2026 (the account is on Workers Paid, and Resend Pro since 15
   October):

   | Limit | Free | Workers Paid, Resend Pro | What here keeps to it |
   |---|---|---|---|
   | D1 queries per Worker invocation (a `db.batch()` counts as one) | 50 | 1,000 | `D1_QUERIES_PER_RUN`, 900, counting a batch's every statement |
   | Subrequests per invocation (each `fetch()`, and each call to D1) | 50 | 10,000 | `SEND_LIMIT`, 200 emails a run, with up to eleven changes files and the run's D1 queries |
   | D1 Time Travel, the backups that cannot be turned off | 7 days | 30 days | the pages' "at most 30 days" |
   | Resend's emails | 100 a day, 3,000 a month | 50,000 a month, no daily limit | shared by confirmations (`SIGNUP_DAILY_CEILING`) and updates |
   | Resend's API rate, per team, the same on every plan | 10 a second | 10 a second | `SEND_GAP_MS`, 200: half of it |
   | Resend's data retention (emails and logs) | 30 days | 30 days | the Data page's "for a limited time" |

   From <https://developers.cloudflare.com/d1/platform/limits/>,
   <https://developers.cloudflare.com/workers/platform/limits/>,
   <https://resend.com/pricing> and
   <https://resend.com/docs/api-reference/rate-limit>. A plan that changes is
   a row to read again.

### The root `wrangler.toml`

The Pages project binds the database as it binds the reports database,
production and preview each stating their own `[[env.<name>.d1_databases]]`
with `binding = "FOLLOW_DB"`, and sets `MAIL_FROM` and `FEEDBACK_URL` in each
environment's `vars` as the sender has them. A fork puts its own database
ids there. The site's names come from `REPORT_ORIGINS`, which each
environment already sets; `FOLLOW_ORIGINS` overrides it for following alone.
`SIGNUP_DAILY_CEILING` (default 1,000, enough for a webinar's sign-ups;
`signup.js` says why) caps confirmation emails a day.

## Sending yourself a test email (preview only)

So that the person can see an email at once rather than wait for the
morning's run (23 October 2026), the preview sender answers one request.
`POST /test-send` sends each confirmed subscriber in the preview's database
-- at most five, the first by id; the answer says if more were left -- the
daily, the weekly and the "You're following" email, built as the real ones
are (`collect()`, `digestEmail()`, `welcomeEmail()`) over the last nights of
the preview site's `/changes/` files, each with `[Test] ` before its subject
and the reader's own manage and unsubscribe links. It records nothing: the
next real email comes when it would have, with what it would have carried.
A reader paused today is left out, as a run leaves them.

What a test shows that a real email would not:

- **A digest with nothing in those nights** is sent as a short note saying
  so, where a real run sends nothing.
- **A followed bill with a public hearing still ahead** shows its testimony
  block on any day; a real daily shows it the morning the hearing is set and
  the two mornings before it. Where no followed bill has one ahead, the
  answer says so.
- **A record that has ended** says, as the real email would, that it has
  been taken off what you follow. A test takes nothing off.

It answers only behind two guards, both or a 404: `TEST_SEND = "on"`, which
only `[env.preview.vars]` in `wrangler.toml` sets, and the secret
`TEST_SEND_TOKEN`, which the request's `Authorization: Bearer` must match.
Production has neither, and no address at all (`workers_dev = false`);
preflight's `_follow_test_send` holds that, and `sender.js`'s A TEST SEND
says the rest.

In PowerShell, in the repository folder:

1. **A token**, made by a command and never printed, as the keys are made:

       $b = New-Object byte[] 32; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); $t = [Convert]::ToBase64String($b); $b = $null

2. **Set it on the preview sender**, with `--env preview`:

       $t | npx.cmd wrangler secret put TEST_SEND_TOKEN --config workers/follow/wrangler.toml --env preview

3. **Redeploy the preview sender**, from a checkout that has this section:

       npx.cmd wrangler deploy --config workers/follow/wrangler.toml --env preview

   Wrangler prints the Worker's address as it finishes,
   `https://graniterecord-follow-sender-preview.<your-subdomain>.workers.dev`,
   where `<your-subdomain>` is the account's own workers.dev name. The
   dashboard shows it too: Workers & Pages, the Worker, Settings, Domains &
   Routes. If wrangler asks to register a workers.dev subdomain, the account
   has none yet, and the name chosen there is the one.

4. **Send.** The address in a variable once, then:

       $u = "https://graniterecord-follow-sender-preview.<your-subdomain>.workers.dev/test-send"
       curl.exe -X POST $u -H "Authorization: Bearer $t"

   With no body it sends all three emails over the last 7 nights, and needs
   no quoting at all. To choose, send `{"kinds": [...], "nights": n}`:
   kinds of `daily`, `weekly` and `welcome`, nights 1 to 10. In PowerShell
   7.3 or later (`pwsh`), as typed:

       curl.exe -X POST $u -H "Authorization: Bearer $t" -H "Content-Type: application/json" -d '{"kinds":["daily"],"nights":7}'

   **Windows PowerShell 5.1** -- what typing `powershell` opens -- strips the
   inner double quotes on the way to curl.exe: the Worker is sent
   `{kinds:[daily],nights:7}`, answers `"why":"invalid"` and sends nothing.
   There the quotes need backslashes,
   `-d '{\"kinds\":[\"daily\"],\"nights\":7}'`, which 7.3 in turn sends with
   the backslashes in, and is refused the same way. `$PSVersionTable.PSVersion`
   says which is open. A file, outside the repository, works the same in
   both:

       Set-Content -Path "$env:TEMP\test-send.json" -Value '{"kinds":["daily"],"nights":7}' -Encoding ascii
       curl.exe -X POST $u -H "Authorization: Bearer $t" -H "Content-Type: application/json" --data-binary "@$env:TEMP\test-send.json"

   The `@...` stays in double quotes: bare, PowerShell reads the `@` as its
   own. Not `-v`, which prints the request's headers, the token among them.

   The answer is counts, never an address: `sent`, `emails` by kind,
   `nothing_new` (the short notes), `testify` (testimony blocks sent),
   `skipped` and `failed` each by reason, and `notes` in words -- that more
   than five subscribers were left, that a night had no file, that the
   preview site's newest night is older than today (the emails are as of
   that night), or that no followed bill has a hearing ahead. A send takes a
   few seconds: `SEND_GAP_MS` apart, as the run's are.

`$t` lives only in that window. Closed, it is gone: make a new one and set
it again (steps 1 and 2), which replaces the old. To turn the test send off,
delete the secret, and `/test-send` is a 404 again:

    npx.cmd wrangler secret delete TEST_SEND_TOKEN --config workers/follow/wrangler.toml --env preview

## What reads this database, and what must not

Nothing but the Functions and the sender. Applying `schema.sql` is the one
`wrangler d1 execute` ever run against `graniterecord-follow`: no script, no
report and no Claude session queries it, although this machine's wrangler
login (the one `publish` and `compile_reports.py` use) could. Sealing means
such a query shows hashes and ciphertext, not addresses or follow lists, but
a query is still a look, and the person's line is that nobody looks.
`preflight_checks_to_add.md` (in the assistant's scratchpad) has the check
that no tracked file runs one.

## What the pages promise

Settled before go-live, and what a change here must keep true:

- **Resend holds a copy of each email**, its recipient and its content --
  what the reader follows, by name -- for its plan's data retention,
  readable by anyone logged into that account. Sealing the database cannot
  reach that copy, and the Data page says so: the mail service keeps its own
  copies for a limited time.
- **Deleting is said one way** on the manage and unsubscribe pages and the
  page after (`page.js`, `DELETES` and `AFTERWARDS`): deleted from our
  database at once; the database's backups age out within at most 30 days;
  the mail service's copies of sent emails age out on its schedule. The
  Data page says the same more briefly: both copies are kept "for a limited
  time".
- **One link per reader**, as FOLLOW.md designed it: every email carries the
  same manage link until the reader asks for a new one, so a forwarded email
  opens the reader's manage page (their follow list, never their address)
  until they do. The manage page says so.

## The front end's side

The Turnstile widget's site key, public, for both graniterecord.org and the
dry-run preview (the person, 11 October 2026): `0x4AAAAAAFTdC20uymy0Ut8h`.
Its secret is `TURNSTILE_SECRET`, on Cloudflare only.

The Follow control posts what the reader typed, and stores nothing:

    POST /api/follow/signup
    Content-Type: application/json
    {"email": "...", "kind": "bill", "ref": "2026/HB1442", "frequency": "daily",
     "turnstile": "<the widget's token>", "website": ""}

`frequency` is the box's Daily or Weekly (16 October 2026), `"daily"` or
`"weekly"`; the confirmation gives it to a new subscriber, and one already
subscribed keeps their own -- the box opens on Daily, and a weekly reader
must not be made daily by not touching it. Where the box asked for the
other one, the manage page the confirmation lands on says so ("daily as
before" or "weekly as before"), above the How often that changes it. A
request that names none is daily, as a page loaded before the box had the
choice sends none; any other value is refused as `invalid`. `website` is a
honeypot: an input a person never sees, left empty. The answers:

| Status | Body | Means |
|---|---|---|
| 202 | `{"ok":true}` | Accepted -- whatever the address. The request is kept and the email sent after the answer, so the answer takes as long for every address; if the inbox already has three waiting, or Resend refuses, nothing arrives and the log says which. The box should say "if this address can take it, a confirmation is on its way". |
| 400 | `{"ok":false,"why":"invalid"}` | Not an address, not a record key, or a frequency other than daily or weekly. |
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
| `follow sender.test-sent 6` | A test send on the preview (above) sent 6 emails; one line each time it is asked. |
| `follow sender.test-failed.resend-422 1` | A test email Resend refused, with its status; `error-<name>` for an error of the sender's own. |
| `follow signup.sent 1`, `follow confirm.confirmed 1` | One confirmation emailed; one confirmed. |
| `follow confirm.welcome-sent 1` | A confirmation that added a record sent its "You're following ..." email, which carries the manage link (16 October 2026). One a confirmation at most, so never more than the day's confirmations. |
| `follow confirm.welcome-refused.429`, `follow confirm.welcome-error.Error` | That email was not sent. The confirmation stands and its page says nothing of it; the reader's way back is then the first update. |
| `follow signup.waiting-enough`, `follow signup.day-full` | A request not sent: its inbox has three waiting, or the day's ceiling is reached. |
| `follow unsubscribe.one-click-matched-nothing` | A provider's one-click carried a link that is no longer current; nothing was deleted. |
| `follow manage.new-link-already-moving` | "Send me a new link" pressed twice at once; one email went. |
| `follow bounce.forgot 1`, `follow complaint.forgot 1` | Addresses deleted by Resend's webhook. |
| `follow bounce.unsigned` | A post to the webhook that was not Resend's. |
