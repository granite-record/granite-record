# Reporting a security issue

Email **contact@graniterecord.org**. Please do not open a public issue for
anything that looks exploitable.

Tell us what you found, how to reproduce it, and what you think it lets someone
do. You will get an acknowledgement. This is a small project run by one person,
so the honest answer on timing is days rather than hours.

You are welcome to look. Nothing here is a trap, and the surface is small
enough to read in an afternoon.

## What the surface actually is

**graniterecord.org is files on a CDN.** Every page a reader asks for was built
ahead of time by the scripts in this repository. There is no application
server, no database behind the pages, no login, no session, no cookie set by
this site, and no user-supplied string that reaches a query.

What arrives is not quite byte-for-byte what the build produced, which is worth
knowing before you go looking for the difference. The pages link Public Sans
and Newsreader from Google's font CDN, so every view fetches a stylesheet and
the faces from there; nothing is self-hosted. And Cloudflare rewrites the HTML
on the way out — the analytics beacon `/about` describes, and an email
obfuscation pass that replaces every `mailto` with a hex string salted per
request, which is why a contact address on the page only resolves once a
Cloudflare script has run. Those two are dashboard switches rather than
anything this repository emits, and `check_live.py` reports both.

**In this project's own code there is exactly one exception**, and its own
header says so: `functions/api/report.js`, the endpoint behind the "report a
problem" box on bill, member and committee pages. It is write-only, it is on no
page's critical path, and when it is down the box falls back to an email link.
If you are looking for something to attack, it is this.

It has been red-teamed once, and the seven real defects that turned up are
listed in the file's header — knowing what was already wrong is more useful
than a claim that nothing is.

## Things that look like bugs and are not

Worth saying in advance, so you do not spend an evening on them:

- **Nearly every POST to `/api/report` answers `204`.** Success, a duplicate, a
  rejected field, a honeypot hit — the same empty response. That is
  deliberate, so that a script learns nothing from the difference. It does
  mean you cannot tell from outside whether your report was stored. The two
  exceptions are a well-formed report that could not be kept: `503` when the
  database could not keep it, and `429` when the day's ceiling had already
  been reached. Each makes the box on the page offer the reader the email
  address instead of thanking them, and each tells a sender only that storage
  is down or that the day is full.
- **The database credentials for the General Court's SQL host are public.** The
  General Court publishes them at gc.nh.gov/downloads. They are not ours and
  they are not a leak.
- **`site/_headers` sets `Access-Control-Allow-Origin: *` on the JSON and CSV.**
  That is on purpose: the published record is meant to be readable from another
  origin. It is not set site-wide.
- **Legislators' contact details are published.** Those are official addresses
  the members themselves list as official. Members of the public who submit
  testimony are never named — testimony appears as counts only.

## What we would consider serious

- Anything that lets someone write to the site, the deployment, or the report
  database.
- Anything that de-anonymises a reader — of the site, or of a submitted report.
  The report schema has no column for an address, a cookie, a session or a
  name, and `about.html` promises that. A way around it is a real finding.
- A way to get the project's fetching to hammer the General Court. Their
  firewall has blocked this address twice already, and the cost of a third
  block falls on a Clerk's office as much as on us.
- A credential or key findable in the repository or its history. `preflight.py`
  has three checks aimed at this — one for key shapes in tracked files, one for
  the contact address, and one that every commit is authored by the project
  address — and if you get past them, that is worth knowing.

## What is out of scope

Wrong data. A bill with the wrong committee, a misattributed vote, a timestamp
that lands in the wrong place — those are not security issues, they are the
thing this project is for, and the report box on the page is the right route.
They are taken just as seriously; they simply go somewhere else.
