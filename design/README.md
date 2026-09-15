# design/

Reference material for the visual polish pass, from the person's separate design chat
of 15 September. Nothing in this folder is built or deployed.

- `BRIEF.md` -- that chat's plan for the pass: find where style lives, move every
  literal into tokens with no visual change, add a preflight check against new
  literals, then apply its rules one at a time across every page.
- `homepage.html`, `header.html`, `billtext.html`, `learn.html` -- its mockups. Open
  them in a browser. They specify layout, hierarchy and the rules in the brief, not
  copy: their figures and prose are placeholders ("41 bills · 6h 12m", "$100 a year
  ... unchanged since 1889") and must not ship without being counted from the record.

**The person does not agree with every choice in them.** Which ones stand is decided
with the person before each is built, not read off these files. Decided so far:

- **Overruled, 15 September: the home page keeps its large logo and slogan** under the
  masthead's brand. `BRIEF.md`'s rule that the brand is "never duplicated in a hero"
  does not apply, and `homepage.html`'s headline does not replace "Public Records,
  Made Findable."
- **Agreed in principle:** more uniform formatting and styles, and better tab
  navigation.

`DESIGN.md` at the repository root is still the standing design brief, and where the
two disagree the person decides. Three things in `BRIEF.md` were written without the
repository in front of it, and are out of date:

- `renderDetail` was split into nine functions on 6 September; there is no split left
  to sequence the pass around.
- Its step 1 was run on the 15th. Style is already mostly tokens: `app.css` has 533
  `var()` uses and 4 colour literals outside its token definitions (the video
  placeholder), copied into the stylesheet `build_pages.py` writes. The inconsistency
  is elsewhere: two stylesheets rather than one, eleven font sizes from 10px to 32px
  in `app.css` with no type scale, and spacing with no tokens at all.
- The site's fonts are Public Sans and Newsreader today; the mockups use Playfair
  Display and IBM Plex. Changing families is a decision, not a tidy.
