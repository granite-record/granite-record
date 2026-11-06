# A committee page opens on a term the site publishes (for 11 November)

The branch is `fix/committee-term`. A committee's record can name a term the site has not built
yet: a meeting the General Court posts for after Organization Day (2 December 2026), filed under
2027–2028, before the new term's first night. The committee's page opened on the newest term its
record named, so it read "No bills were referred to this committee in the 2027–2028 term" over the
term it has a record of, and asked for `idx/2027-2028.json`, an index the site does not publish,
which answered 404, unhandled, on the page and on every tab.

Now the page opens on the newest term the site publishes (meta.json's terms, or the bill requests'),
and asks for no index of a term it does not publish. The term to come stays in the Term control,
with its meeting under Meetings when a reader chooses it. No committee on the live site names such
a term today (86 of the 88 committee records were read on 6 November; the other two answer 404 for
reasons of their own), so nothing on graniterecord.org changes until the turn.

## How the shots were made

Each shot is `<item>-<page>-<before|after>-<390|1280>-<light|dark>.png`.

- **Both** are preflight's fixture site built as if on 29 November 2026, three days before the
  turn: its one meeting still to come is dated by the clock three days ahead, so it falls on
  2 December and is filed under 2027–2028. **Before** is dev (2e324165); **after** is this branch.
- Each was served on the machine and drawn in Chromium, with only the site's web fonts let
  through. The logo is the placeholder a clone has; the art is not in the repository.

## 1. Committee H43, a desktop (`b1`, `b2`)

`b1`, before: Term 2027–2028; Bills says no bills were referred in 2027–2028; Meetings (1); no
count on Videos. The browser's console shows `idx/2027-2028.json` 404 and the error left
unhandled. `b2`, after: Term 2025–2026; Bills (1) with HB 1442, Meetings (2), Videos (3). The
only request that fails is `/build.json`, which the fixture does not write.

## 2. The same page on a phone (`b3`, `b4`)

The same, at 390 pixels.

Not shown: choosing 2027–2028 in the Term control after the fix shows the 2 December meeting
under Meetings and asks for no index; switching back restores 2025–2026.
