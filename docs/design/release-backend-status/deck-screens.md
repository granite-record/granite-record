# The webinar deck against the weekend release

The release and backend session wrote this on Friday 6 November 2026, about 11 p.m. Eastern. It
is item (d) of the laptop manager's message of 7 November: which of the webinar deck's
screenshots show something the weekend release changes, so they can be retaken from the live
site once the release is out. The deck is the Slides artifact `2kq5DAFQJ94F2LwVBsrSeK`.

**How it was checked.** For each slide with a screenshot, the page it shows was compared on live
(main a0354996) and on dry run 181's preview (dd3f7ef9, which holds the 11 November train). Shots
were taken at 1280×800, and at the deck's own framing (1164×728 at 2x, as `deck/scripts` shoots
it). Each slide was then checked against what the five branches of `release/weekend` add on top
of the preview. A second agent checked every "yes" and "maybe", and spot-checked the rest.

## Retake after the release (the picture changes)

| Slide | Page | What changes |
|---|---|---|
| committee | `/committee/H11` | The facts row (Meets in, Phone, Aide, Researcher) moves up about 30 px, under "chaired by Rep. James Creighton". Live matches the slide pixel for pixel; the preview differs by 26,756 pixels. From the 11 November train (dc8404f6, "facts under the line"). |
| legislator | `/legislator/alice-wade-straf-15` | The row with Committee, Seat, Email and On Record sits right under the party and district line (y 239, not 284 at 1280); the empty band moves below it. Same commit. |
| followkinds | HB 100 of 2026, Follow open | The Follow pane opens to the left of the Follow button, with a pointer, not under the action column. The facts row moves up about 50 px, and all the bill's tabs now show. The panel's words are unchanged. From the 11 November action panes. |

None of the five branches changes any of these screens. The three changes are all dev's
11 November work, which the release carries.

## Words that become wrong (the "Coming soon" slides)

- **coming1, Live Now.**
  - The notes say "it is not on graniterecord.org yet". After the release, graniterecord.org/live
    answers (today it is a 404), with the same status as the preview. It is in the sitemap, with
    no noindex. It is not linked from the menus, the home page or the Calendar until live/session
    lands after the webinar.
  - The eyebrow "Coming soon" and the image's alt text ("on the preview site") are wrong the same
    way. A true line: "now at graniterecord.org/live; not yet in the menus".
- **coming1, the committee video.** "The video plays on the committee's own page" becomes true
  with the release: the live hook on committee pages ships. The House Labor Videos tab in the
  right-hand shot is already on live, identical.
- **coming2, County by County.** The notes and the on-slide label say "in the works", and that
  the screen "is its design, two of the ten cards, not the live site". After the release, the ten
  cards are published on the County Government page, in English and Spanish. Each card now links
  to its county on the Officials page.
- **coming2, the API.** "A beta of the API is planned." After the release, graniterecord.org/api
  answers, saying "A beta until February 1, 2027". It stays unlinked and noindex until the
  December announcement. Whether to say "planned" or "in beta, announced in December" is the
  owner's call.

## Notes already wrong today, on live as on the preview (not the release)

- **hearing.** Note 4 says "the floor debate's link says 'approximate'". The House floor debate
  of 20 February 2025 reads "Play from 04:28:19 · vote at 04:36:34", with no "approximate". The
  only "approximate" on the tab is on the debate of 26 June 2025 (Concur), the last entry.
- **committee.** Note 4's "145 bodies (140 statutory, 5 study)" is now 144 (139 statutory, 5
  study). The list is a folded section on /committees, to be opened.
- **home.** Note 1's "a subject like 'dam safety'": typed in the home box, the suggestions say
  "No matching results". Search finds 7 bills by their text, but it is not a subject on the site.

## Unchanged (no retake)

home, bill, hearing, vote, law, map, town, resources, guides, calendar and follow. Each was
pixel-identical between live and the preview at the deck's framing, apart from the day's data.
The five branches change none of them.

## Worth knowing for the night

- **Three slides still embed their October images**, not the 5 November re-shoots: hearing,
  vote and law. The content is the same. The October law crop lacks the section rail both sites
  now draw.
- **Committee pages check for a live stream on weekdays, 07:00–20:00** New Hampshire time (the
  release's live hook). The webinar on Tuesday 10 November is inside that window. If a committee
  being demoed were streaming that evening, a live card would show above its title. That is
  unlikely, and nobody has seen it.
- **/live on the night** adds an "On today's calendar, no stream found" list on a day with
  meetings, which the slide's shot of 5 November lacks. That follows the day.
- **Email following's beta line** ("in beta until the webinar on November 10") is in the retakes,
  and is right on the night.

Retaken from the live site after the release, the three changed screens will match the
preview's, which the comparison shot at the deck's own framing.
