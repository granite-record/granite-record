// GRANITE_VERSION: 2026-09-12.4
// A MEETING BELONGS TO ONE COMMITTEE, AND THE NAME DOES NOT SAY WHICH.
//
// home.json's `upcoming` gives a committee NAME and no chamber, and seven
// names belong to both chambers: Finance, Judiciary, Education,
// Transportation, Ways and Means, Children and Family Law, and Executive
// Departments and Administration. So the committee page matches on the name
// AND on the meeting's bill being in that committee's own list -- and the
// list has to be read per TERM, because a bill number is not a key. House
// Finance carries a CACR 1 in 2001, 2005 and 2019, and the first version of
// this rule collapsed every term into one set, so any of those three would
// have vouched for a 2026 meeting about an entirely different CACR 1.
//
// That flaw was found by a test whose own fixture was wrong -- it named a
// bill the committee did not have in the term claimed, both Finance
// committees correctly refused it, and chasing why exposed the real bug.
// These cases are the ones that would have caught it directly.
//
// Run by preflight; run alone with:  node tests/test_cmte_match.js

// Extracted from app.js by source text, so it cannot drift from what the
// browser actually runs.
const fs = require("fs");
const src = fs.readFileSync("app.js", "utf8");
const m = src.match(/function cmteUpcoming\(c\)\{[\s\S]*?\n\}/);
if (!m) { console.error("cmteUpcoming not found in app.js"); process.exit(1); }
let UPCOMING = null;
eval(m[0]);

const cmte = code => JSON.parse(fs.readFileSync(`site/committee/${code}.json`, "utf8"));
const H34 = cmte("H34"), S07 = cmte("S07"), H12 = cmte("H12");

const bills2026 = c => new Set((c.bills["2025-2026"] || []).map(b => b.id));
const onlyH = [...bills2026(H34)].filter(b => !bills2026(S07).has(b));
const shared = [...bills2026(H34)].filter(b => bills2026(S07).has(b));

let fails = 0;
const t = (name, got, want) => {
  const ok = JSON.stringify(got) === JSON.stringify(want);
  if (!ok) fails++;
  console.log(`  [${ok ? " ok " : "FAIL"}] ${name}` + (ok ? "" : `\n          got ${JSON.stringify(got)} want ${JSON.stringify(want)}`));
};

const row = (o) => Object.assign(
  {date:"2026-09-18", time:"09:00", term:"2025-2026", what:"public hearing", venue:"LOB 210"}, o);

console.log(`H34 2025-2026 bills: ${bills2026(H34).size}; only in H34: ${onlyH.length}; shared with S07: ${shared.length}\n`);

// 1. the committee that owns the bill shows it
UPCOMING = [row({bill: onlyH[0], committee: "Finance"})];
t(`House Finance shows a meeting on ${onlyH[0]}, which is its own`,
  cmteUpcoming(H34).map(u => u.bill), [onlyH[0]]);

// 2. the same-named committee in the other chamber does not
t(`Senate Finance does NOT show it`, cmteUpcoming(S07).map(u => u.bill), []);

// 2b. A BILL BOTH COMMITTEES LIST DOES NOT SAY WHOSE SITTING IT IS; the row's
//     chamber does. `shared` was computed here and never used, and that was
//     the hole: House Judiciary's executive session on SB 519 of 30 September
//     2026 was on Senate Judiciary's page, because SB 519 is on both lists.
if (shared.length) {
  UPCOMING = [row({bill: shared[0], committee: "Finance", body: "H"})];
  t(`House Finance's sitting on ${shared[0]}, which both Finance committees list, is House Finance's`,
    cmteUpcoming(H34).map(u => u.bill), [shared[0]]);
  t(`and is NOT on Senate Finance's page`, cmteUpcoming(S07).map(u => u.bill), []);
  UPCOMING = [row({bill: shared[0], committee: "Finance", body: "S"})];
  t(`Senate Finance's sitting on ${shared[0]} is Senate Finance's`,
    cmteUpcoming(S07).map(u => u.bill), [shared[0]]);
  t(`and is NOT on House Finance's page`, cmteUpcoming(H34).map(u => u.bill), []);
}

// 3. a bill number from an EARLIER term must not vouch for a current meeting.
//    CACR1 is House Finance's in 2001, 2005 and 2019 and not in 2025-2026.
UPCOMING = [row({bill: "CACR1", committee: "Finance"})];
t("a 2026 meeting on CACR1 is refused, though H34 has a CACR1 in 2001/2005/2019",
  cmteUpcoming(H34).map(u => u.bill), []);

// 4. and it IS accepted for the term it really belongs to
UPCOMING = [row({bill: "CACR1", committee: "Finance", term: "2001-2002"})];
t("the same CACR1 is accepted for term 2001-2002", cmteUpcoming(H34).map(u => u.bill), ["CACR1"]);

// 5. a wrong committee name is refused even with a bill it owns
UPCOMING = [row({bill: onlyH[0], committee: "Ways and Means"})];
t("a name that does not match is refused", cmteUpcoming(H34).map(u => u.bill), []);

// 6. the real data lands where it belongs.
//
// NAMED FROM THE FILE, NOT FROM THE DAY. This case used to assert that H12 had
// HB 1692 and SB 570, which was true on 12 September and false on the 16th,
// when that meeting had happened and dropped out of the fortnight -- a test
// that fails with the calendar rather than with the code. It now takes the
// busiest committee in today's upcoming list, reads that committee's own
// record, and asks that the rows land there and nowhere else.
const upAll = JSON.parse(fs.readFileSync("site/home.json", "utf8")).upcoming || [];
//
// NOT A RETIRED COMMITTEE OF THE SAME NAME. committees.json lists the
// committees the General Court has retired too, and "Commerce" is H33, the
// House's of 1995-2008, before it is S37, the Senate's today; nothing is
// scheduled for a committee that no longer sits, so an archived page is
// passed over here.
const codeOf = name => {
  const all = JSON.parse(fs.readFileSync("site/committees.json", "utf8"));
  const hit = (Array.isArray(all) ? all : []).find(
    c => (c.name || "").toLowerCase() === (name || "").toLowerCase()
      && !(fs.existsSync(`site/committee/${c.code}.json`) && cmte(c.code).archived));
  return hit && hit.code;
};
const byName = {};
upAll.forEach(u => { byName[u.committee] = (byName[u.committee] || 0) + 1; });
const busiest = Object.keys(byName).sort((a, b) => byName[b] - byName[a])[0];
const code = busiest && codeOf(busiest);
if (code && fs.existsSync(`site/committee/${code}.json`)) {
  const C = cmte(code);
  const want = upAll.filter(u => u.committee === busiest).map(u => u.bill).sort();
  UPCOMING = upAll;
  t(`${busiest} keeps its ${want.length} scheduled bills`,
    cmteUpcoming(C).map(u => u.bill).sort(), want);
  const other = [H34, S07, H12].find(x => x.code !== code);
  t("another committee gets none of them",
    cmteUpcoming(other).map(u => u.bill).filter(b => want.includes(b)), []);
  // And no committee page, of every one built, shows the other chamber's
  // sitting. The rows say their chamber since 25 September 2026; a row built
  // before then says none and is not judged here.
  //
  // WHETHER EVERY ROW SAYS IT IS NOT ASKED HERE. This file runs under
  // preflight --code, which nightly.py runs before build_all, and a home.json
  // built before the builder wrote the chamber would fail it on the one night
  // that would rebuild it -- so the nightly would stop, and stay stopped, until
  // a person built by hand. That question is preflight's data check
  // "every upcoming row on the built site says whose sitting it is", and the
  // builder's side of it is _upcoming_shape, on a fixture, under --code.
  const every = fs.readdirSync("site/committee").filter(f => /^[HS]\d+\.json$/.test(f))
    .map(f => cmte(f.slice(0, -5)));
  const crossed = [];
  every.forEach(C => cmteUpcoming(C).forEach(u => {
    if (u.body && C.chamber && u.body !== C.chamber)
      crossed.push(`${C.code} ${u.date} ${u.committee} ${u.bill} (${u.body})`);
  }));
  t("no committee page shows the other chamber's sitting", crossed, []);
} else {
  console.log("  [ ok ] nothing is scheduled in the fortnight, so there is "
              + "nothing to route");
}

// 7. nothing fetched yet is not the same as nothing scheduled
UPCOMING = null;
t("null UPCOMING yields no rows", cmteUpcoming(H12), []);

console.log(fails ? `\n${fails} FAILED` : "\nall passed");
process.exit(fails ? 1 : 0);
