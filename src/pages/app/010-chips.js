// esc, dateWords and dateSpan, clock, cmteLink and pchip are components.js's,
// which every page loads before this file (the component plan's C1 and C2),
// and so is WORDBOOK, the words of src/pages/words/ that the build writes into
// it: the chip's classes and the kinds of meeting are read from there (C3).
// What each kind of document actually is, said once rather than in every row.
const DOCWHAT={text:"the bill as it currently stands",
  status:"the General Court's page saying where the bill stands",
  docket:"every recorded action, in the General Court's own words",
  record:"the official record of one action",
  report:"the calendar a committee report was printed in"};
// The status page of a bill whose status this site reads from the House
// Journal instead (status_source): seven bills the House's resolution of
// introduction steps over, on 2 October 2026.
const STATUS_NOT_FROM_PAGE="the General Court's own status page for this bill; "
  +"the status shown here is read from the House Journal instead";
// And of a constitutional amendment the voters have answered: its status page
// stops at the second chamber, so "ratified" or "not ratified" is the docket's
// referendum line or the count on the Votes tab (build_site_v2's
// status_source), not this page's (the review of 5 October 2026).
const statusUpToTheVoters=d=>"the General Court's own status page for this "
  +"amendment, which stops at the second chamber's vote; whether the voters "
  +"ratified it is read from "+(d.status_source==="General Court docket"
    ?"its docket's referendum line":"the count on the Votes tab");
// WHAT THE SHORTHAND STANDS FOR. A citation is printed the way the General
// Court prints it -- "HJ 1, page 32" is what a reader would quote -- but HJ
// and SC are insider shorthand, and this site exists to make the record
// findable. The Learn section explains the same four at
// civics.py's "Reading the shorthand" table; this is the one place a reader
// meets them without having gone looking.
const CITE_OF={HJ:"House Journal",SJ:"Senate Journal",
  HC:"House Calendar",SC:"Senate Calendar"};
const citeSource=lab=>CITE_OF[(String(lab).match(/^([A-Z]{2})\b/)||[])[1]]||"";

const PARTY_NAME={R:"Republican",D:"Democrat",I:"Independent",L:"Libertarian",
  X:"Party not on file"};
// A roll call's legend keys each row by its party (the owner's walk of the
// release candidate, 30 October 2026: "the roll call vote legend doesn't
// show as blue and red or purple by party; instead it colors them red and
// green by the yes or no vote, like division votes").
const PARTY_COLOR={R:"var(--rep)",D:"var(--dem)",I:"var(--ind)",L:"var(--ind)",
  X:"var(--ink-2)"};
// Where a party sits in a vote's legend and full record: Republicans, then
// Democrats, then anyone else by letter, and within a party yes before no.
// The split inside a caucus is what those two rows are compared for, so they
// have to be adjacent; ordered by size, the Republican no drifted to fourth
// with both Democrat rows between it and the Republican yes.
const PARTY_RANK={R:0,D:1};
const partyRank=p=>(p in PARTY_RANK)?PARTY_RANK[p]:2;
const byParty=(a,b)=>partyRank(a)-partyRank(b)||String(a).localeCompare(String(b));
const yeaFirst=(a,b)=>a===b?0:(a==="Yea"?-1:1);
// A BALLOT IN THE BILL PAGES' WORDS (17 October 2026): a member's own page
// listed "Yea", "Nay" and "Not Voting/Not Excused" where every roll call says
// Yes, No and "Absent, not excused" (OTHER, below). The value filtered on is
// still the record's.
const ballotWord=v=>v==="Yea"?"Yes":v==="Nay"?"No"
  :(OTHER.find(o=>o[0]===v)||[])[1]||v;
// A chip's class by the bill's kind, for a word that is not one of the six.
// It and CHIPCLASS below are words, written once (the component plan's C3,
// 9 October 2026): src/pages/words/chips.json, which components.js carries
// as WORDBOOK and the builders read through components.py.
const KIND=WORDBOOK.chips.kind;
// THE CHIP: six words for where a bill stands, and a still-moving bill's
// stage (the person, 5 October 2026). build_site_v2.chip_word chooses the
// word and the index carries it as `chip`; this only draws it. The status --
// "Killed", "Vetoed, override failed" -- stays on the bill's own view, in On
// the record, the history and the rail. The colour is the word's, so every
// Died is one colour whether the bill was killed or its veto stood; a word
// that is not one of the six -- a stage, an adopted resolution -- takes its
// kind's. "Became law" is wrong for a resolution, which is adopted and is
// not law: its chip is its own word, "Adopted by the House".
// Interim Study and Tabled take their rail marks' inks (the person, 8 October
// 2026): the orange of the "~" and the yellow of the pause (graphite for a
// day). A stage still moving -- "In committee" and the rest, KIND.active --
// is slate blue since the same evening, so Tabled and In committee are two
// colours. Under protanopia the yellow is near the orange, so the chip's
// word and the rail's shape tell them apart.
// The six and their classes are chips.json's "chip", in the person's order.
const CHIPCLASS=WORDBOOK.chips.chip;
const CHIPORDER=Object.keys(CHIPCLASS);
// A request's row has no chip, and its status is its word.
const chipOf=b=>(b&&(b.chip||b.status))||"";
// A status its kind would colour wrongly (chips.json's by_status): a CACR
// the voters did not ratify is "adopted" by kind and drawn as Died.
const BY_STATUS=WORDBOOK.chips.by_status||{};
// A BILL REQUEST'S THREE WORDS (the owner, 13 November 2026), each with its
// class: Requested, Filed, Withdrawn (chips.json's "request"). Their own
// table, so the six and the seven stay a bill's.
const REQCLASS=WORDBOOK.chips.request||{};
const REQCATS=Object.keys(REQCLASS);
const chipCls=b=>CHIPCLASS[chipOf(b)]||BY_STATUS[(b&&b.status)||""]||(b&&b.lsr&&REQCLASS[chipOf(b)])||KIND[b.kind]||"";
// The six first, in their order, then the rest as words.
const chipCmp=(a,b)=>{const x=CHIPORDER.indexOf(a),y=CHIPORDER.indexOf(b);
  return (x<0?CHIPORDER.length:x)-(y<0?CHIPORDER.length:y)
    ||String(a).localeCompare(String(b));};
/* THE STATUS FILTER ASKS A QUESTION THE CHIP DOES NOT. The person, 8 October
   2026: "I'd rather have one In Progress selection to click in the bill
   search sidebar to sort for bills that haven't concluded, separate to those
   that Passed, Died, were sent to Interim Study, or those that are Tabled
   before the end of the session" -- and every bill that became law and every
   resolution that passed is Passed, "since sometimes bills are passed but
   haven't yet become law due to their effective date". The filter offered
   the chip's words one by one, so a reader after the bills still moving
   ticked In committee, Retained in committee, Re-referred to committee,
   Passed one chamber and the rest, and the adopted resolutions were three
   options of their own.
   FILTER ONLY, which is what the person answered the same evening: a card's
   chip keeps its own word (Became Law, Adopted by the House, In committee,
   Tabled), and only the sidebar's Status filter, the Status sort's headings
   and a member's or a committee's Bill status select (billPane) use these.
   Withdrawn and Vetoed are their own: Vetoed only while an override vote is
   still to come, since a veto that stood is already Died. A bill passed and
   awaiting the governor is In Progress, which the person confirmed the same
   evening: the governor has yet to act on it.
   Each is OFFERED ONLY WHERE A BILL IS ONE ("Hide at zero", the person's
   answer of 8 October 2026), in this order whichever are offered; a category
   a reader has chosen stays on offer at none, so it can be undone.
   Read by the chip first and then by its kind (build_site_v2.chip_word), so a
   word this table has never seen -- a stage the General Court names tomorrow
   -- still lands somewhere: preflight walks every row of the nineteen terms
   and fails if one reaches the last line.
   Tables a word from an address is looked up in have no prototype (A WORD
   SOMEBODY TYPES IS NOT A PROPERTY OF AN OBJECT, below).
   The categories, in this order, each with its chip's class, are words:
   chips.json's "category" (WORDBOOK.chips.category; the component plan's C3). */
const STATUSCATS=Object.keys(WORDBOOK.chips.category);
// What is offered: the categories some bill listed is in (`have`), and any a
// reader has chosen (`chosen`, a Set), in STATUSCATS' order.
// A bill request's words (REQCATS) come first, where a request is one: they
// are never a bill's, so a list of bills offers none of them.
const CATORDER=REQCATS.filter(c=>!STATUSCATS.includes(c)).concat(STATUSCATS);
const catsOffered=(have,chosen)=>CATORDER.filter(c=>have.has(c)||chosen.has(c));
// Each in its chip's class, in the sidebar and in a record page's select.
const CATCLASS=Object.assign(Object.create(null),WORDBOOK.chips.category);
Object.assign(CATCLASS,REQCLASS);
