# Following by email — the design, ready to build after launch

Written 14 September 2026. RSS following is live: a bill still moving (or sent
to interim study), a sitting member with a record, and a committee that still
sits each name their feed in the page head, and each record's page has a
**Follow** control that offers it. Email following is designed here and not
built. It is needed before the 2027 session convenes in January, and it ships
only when every guarantee below is true of the running system.

The person's decisions are in the memory file `follow-feature-design` and in
`LAUNCH.md`; this file turns them into a build.

## What a reader gets

1. On a bill, member, committee or topic page, **Follow** offers the feed (today)
   and, once built, an email box: "Email me updates".
2. They enter an address. The page says a confirmation email is on its way and
   nothing else happens until they click it. No confirmation, no follow; an
   unconfirmed request is deleted after 48 hours.
3. The confirmation opens their **manage page**: a private link, not a login.
   There they see what they follow, remove any of it, and choose how often:
   **as it is available** (after the nightly rebuild), **daily** (about 8:00),
   or **weekly** (end of the week — Friday, possibly Saturday, because House
   calendars usually appear Thursday evening and sometimes Friday).
4. Every email ends with the same manage link, and a one-click unsubscribe
   that deletes the address and everything followed with it.
5. A followed bill that concludes sends one last update saying how it ended,
   and the follow ends with it (open decision 2).

"As it is available" cannot be faster than the nightly: the record changes
once a night. The page says so rather than implying real time.

## The privacy line, as built

The person's words: they will not look at who signed up or what anyone follows;
nothing is shared; it is used only to send the updates; unsubscribing is easy.
So the system is built so that **no view, export, log line, report or Claude
session can show an address or a follow list** — not so that people promise not
to look.

- The only number that leaves the system is the **total count of confirmed
  subscribers** (one endpoint, one integer).
- Addresses are stored **encrypted** (AES-GCM) with a key held as a Worker
  secret; a keyed hash (HMAC) of the address is the lookup key, so a duplicate
  sign-up is found without decrypting anything. The person prefers to keep no
  copy of the key; if one is kept it stays private and is used only to fix a
  fault.
- Worker logs never include an address, a token or a follow list: errors log a
  code and a count. `wrangler tail` shows nothing a person could read a name in.
- Tokens (confirm, manage) are random, stored only as hashes, and the manage
  token can be re-issued from the page ("send me a new link"), which also
  invalidates the old one.
- Retention: unconfirmed requests 48 hours; an unsubscribe deletes the row and
  its follows at once; send logs keep counts, never recipients.
- The About page's "no accounts, no email addresses" is rewritten, in the
  person's words above, **before** the sign-up box is public.

## How it runs — on Cloudflare, not the PC

| Piece | What | Where |
|---|---|---|
| Sign-up, confirm, manage, unsubscribe | Pages Functions under `functions/api/follow/` | the site's own origin |
| Subscribers and follows | D1 database, separate from the reports database | Cloudflare |
| What changed tonight | `changes/<date>.json`, written by the nightly build | published with the site |
| Sending | a scheduled Worker (Cron Triggers): hourly check for "as available", 8:00 daily, weekly | Cloudflare |
| Mail | Resend, one verified sending domain, the API key a Worker secret | Resend |
| Abuse | rate limit per IP on the sign-up route; Turnstile on the form (open decision 1) | Cloudflare |

**Nothing in this table may be added under `functions/` before launch**:
anything there deploys with the next publish and becomes a live endpoint.
Build it on a branch in a worktree, against a preview deployment and a
separate D1 database.

## Data model (D1)

    subscribers(id, email_hmac UNIQUE, email_enc, frequency, confirmed_at,
                created_at, manage_token_hash, last_sent_at)
    pending(id, email_hmac, email_enc, follow_kind, follow_ref,
            confirm_token_hash, created_at)          -- purged after 48 h
    follows(subscriber_id, kind, ref, since)          -- kind: bill|member|committee|topic
    sends(date, frequency, emails_sent, items)        -- counts only

A follow's `ref` is the page's own key: `2026/HB1442`, a member id, a committee
code, a topic slug — the same keys the feeds use, so the Follow control already
has it.

## The one thing the site must add first: a nightly changes file

The sender needs "what changed for this bill, member, committee or topic
since the last send", and must not recompute the whole record to find it. The
feeds already hold each item's newest entries with stable guids, so the build
writes `site/changes/<YYYY-MM-DD>.json` — for every followable ref, the guids
and one-line summaries of items new since the previous build (a diff of the
feed items by guid, written by `build_feeds.py`). The sender reads the
changes files since a subscriber's `last_sent_at`. It is public data (the same
facts as the feeds), holds nothing about readers, and is small. Of everything
here it is the only piece worth building before launch, because it can be
tested for weeks against real nights before a single email is sent.

The weekly email also says whether a followed bill had votes or executive
sessions, or has a public hearing coming up; the hearings feed already knows
the upcoming ones. A bill in interim study says whether the committee
recommended future legislation.

## Open decisions — the person's

1. **Turnstile** on the sign-up form: explained on the 13th, not yet agreed. It
   stops scripted sign-ups of other people's addresses (the confirmation email
   already stops them taking effect).
2. **A bill that concludes**: send a final "how it ended" and end the follow
   (proposed), or keep following until the reader removes it.
3. **"As available" against "daily"** when the record refreshes once a night:
   they differ only in timing (after the nightly, around 2-4am, against 8:00).
   Keep both, or fold them into daily.
4. **Topics** as a followable kind: the topic feeds exist; the topic labels for
   archived terms are still being scored, so following a topic is best offered
   for the sitting term only at first.

## Build order after launch

1. `changes/<date>.json` in `build_feeds.py`, with a preflight check that a
   rebuilt night with nothing new writes an empty file rather than none.
2. D1 schema and the Functions on a branch; tests that no response, log or
   error path contains an address (grep the Worker's own output in the test).
3. Resend domain verification (the person's account), the secrets set by the
   person with `wrangler secret put`.
4. The sender Worker against a test list of the person's own addresses.
5. The About page rewrite, then the email box in the Follow control.
