# The members who moved, by the term of their last vote (for 11 November)

The branch is `fix/movers-term`, from dev `dd3f7ef9`. The deep walk of dry run 181's preview
found these faults on 6 November 2026. Each is new in the 11 November update, which was held
back from that night for them.

## What was wrong

One roll call is misdated in the record. 1999-S-109, the Senate's vote on CACR 17, is dated
22 October 2009. It sits between two votes of 22 October 1999, and it is the only one of
2,303,047 ballots dated outside its term. Each former member's last vote was taken by its day,
so for every senator of 1999 who cast it, that ballot counted as their last vote.

- **Two members joined to the wrong page.** Frederick King (Senate 1999–2000, House 2003–2008)
  and Leo Fraser (Senate 1999–2000, House 2001–2004) each have one page now. The page kept was
  the Senate's, though both sat in the House after. Their live House addresses answered with a
  301 to "Former Senator Frederick King (R - SD1)" and "Former Senator Leo Fraser" (`m1`,
  against live's `m2`, and `m5` on a phone).
- **One seat taken from the wrong term.** Carl Johnson's seat was read from 1999–2000's bills,
  SD3, not from his last term's (2005–2006), which print him as SD2 118 times. His right
  address, `/legislator/carl-johnson-sd-2`, answered with a 301 to `carl-johnson-sd-3` (`m3`).
- **Whole careers under the last chamber.** Each joined page's search description, its line in
  the former-legislators directory and its row in the site search put all its years under its
  last chamber's seat. For example, "Sen. Jeb Bradley (R - SD3) served in the New Hampshire
  Senate, 1999 to 2024", and "R, SD3, 1999–2024" in the directory (`m4`). He sat in the House
  for Carroll 8 in 1999–2002.
- **The JSON of a joined number.** Each of the 34 joined members' second numbers lost its
  `/legislators/<id>.json`, which live serves and live pages link to.
- **Session days named the wrong member (blocking).** A session day names a member by surname
  ("Rep. King"), and it is matched against the members who sat in that chamber that term. A
  joined page counted only under its own chamber, so its other chamber's years matched no one
  of that name, and they went to a namesake. In 44 days, Frederick King's House years named
  Seth King, Melanie Levesque's named Cassandra Levesque, Jeb Bradley's named Paula Bradley,
  and Leo Fraser's named Marilyn Fraser.

## What it does now

- **A member's last vote is the last of their last term, then of its days.** The term is the
  roll call's own, from its session year (`service_order`). King's and Fraser's pages are the
  House's again, and Carl Johnson stays at SD2. Of the 19 pages that read "served … 1999 to
  2009", the 13 of senators who served after 2000 and left before 2009 are on record to their
  real last year. A member's list of votes is ordered the same way, so 1999-S-109 no longer
  heads it.
- **Six senators still read "to 2009".** The 6 who sat only in 1999–2000 (John King, Richard
  Russman, James Squires, Mary Brown, Patricia Krueger and Rick Trombly) have no later term to set against the misdated vote.
  They read right once the owner corrects the roll call's date. That fix is held on
  `fix/rollcall-date`. It reads the owner's line in `corrections/rollcall_corrections.json`, and
  its README has the line drafted for the owner to paste.
- **The recorded 301s still hold.** `generated/moved_addresses.json` recorded King's and
  Fraser's House addresses under their Senate numbers. A recorded number joined to another's
  page now resolves to that page (`keep_moved`'s links), so nothing in the file is re-pointed.
- **A live page's address is never a 301.** The file only grows. So if a pair were joined and
  later parted, each page's address would be on record for the other's number, and the two
  pages would redirect to each other. A recorded address that is now a page's own, whether
  former or sitting, stays that page's, and the build names it.
- **Each chamber gets its own years.** A joined page's description, directory line and search
  row name each chamber with its own years, as the page's own "On record" line already did:
  "House of Representatives, 1999 to 2002, and Senate, 2009 to 2024"; "R, SD3 · Senate
  2009–2024 · House 1999–2002". The seat stands alone because it is the last term's, and the
  maps of 2002 and 2012 renumbered the seats of earlier years.
- **A joined number's JSON redirects.** `/legislators/<joined number>.json` answers with a 301
  to the page's own.
- **Session days name a joined member in each chamber they sat in.** A page counts in each
  chamber for the terms it sat there, read from `careers.json` under every number the page
  stands for. A page whose numbers `careers.json` lacks counts in its own terms. Replayed on
  the real ballots, the 32 House days that linked Seth King or Cassandra Levesque, who were not
  yet sitting, now link Frederick King and Melanie Levesque. "Jeb Bradley" and "Leo Fraser" on
  days of 2001–2002 now link them, not Paula Bradley or Marilyn Fraser. A bare "Bradley" or
  "Fraser" there stays plain words, as on live, since both of each name sat then.
- **What it does not do.** A sitting member still counts in every term, so a bare "King" in
  2003–2008 reaches Frederick King through that term's ballots, not by the roster. And
  `careers.json` itself joins two pairs of namesakes: Sen. Pat Long's House number with the
  sitting Rep. Patrick Long of Hills 26, and the two Mark Pearsons. So 34 House days of
  2007–2024 still link the Patrick Long of Hills 26, as live does. That is set out for
  24 November; `people.json` has both pairs right.
- **Sitting senators too.** The same reading reaches the House numbers in a sitting senator's
  `member_ids`. Six sitting senators are now matched on House days of the years they sat
  there: Avard, Birdsell, Carson, Gannon, Reardon and Watters. Every change is right by the
  votes. One a reader sees: a bare "Reardon" on House days of 1999–2002 becomes plain words
  instead of a link to Neil Reardon, since Tara Reardon sat in the House then too.
- **A missing `careers.json` is said.** Without it, a member who changed chamber would be
  matched in one chamber only, and the build now prints a warning.

## The shots

These are the preview as it was: `https://6502d18c.graniterecord.pages.dev`, dry run 181,
`dd3f7ef9`, taken on 6 November 2026. `m2` is the live site. This machine holds no data to
build the real pages, so the after shots come from the next dry run's preview. Preflight's
`_movers_by_term` holds each case in the meantime.

`people.json`, which still gives each of the owner's 30 confirmed pairs as two people, is a
separate question for the owner. It needs merges in the person register, which the design
leaves to a person.
