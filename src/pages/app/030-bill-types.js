const catCmp=(a,b)=>{const x=CATORDER.indexOf(a),y=CATORDER.indexOf(b);
  return (x<0?CATORDER.length:x)-(y<0?CATORDER.length:y);};
// A category, or a word a chip says, in any case, as the category it is in:
// what ?status= in an address is read through, so an address written with a
// chip's word ("Became Law", "In committee") still finds its bills. A word
// that is neither, and that no bill's chip says (`rows`, the index), is "".
function catOfWord(w,rows){
  const s=String(w||"").trim();
  if(!s)return "";
  const lo=s.toLowerCase();
  const named=CATORDER.find(c=>c.toLowerCase()===lo);
  if(named)return named;
  const word=Object.keys(CAT_OF_CHIP).find(c=>c.toLowerCase()===lo);
  if(word)return CAT_OF_CHIP[word];
  const said=catOfChip(s.charAt(0).toUpperCase()+lo.slice(1));
  if(said)return said;
  const row=(rows||[]).find(b=>String(b.chip||"").toLowerCase()===lo);
  return row?statusCat(row):"";
}
/* WHAT KIND OF MEASURE IT IS, from the letters of its number (the person, 8
   October 2026: "sorting between HB, SB, HR, SR, HCR, SCR, CACR"). Each name
   is the one the measure's own document prints over its text -- "HOUSE BILL
   OF INTENT NO. 1", "HOUSE ADDRESS 1", "HOUSE CONCURRENT ORDER 1",
   "SPECIAL SESSION HOUSE CONCURRENT RESOLUTION 1" -- read off the pages
   saved under legislation/ and the records' dockets. PET is a petition for
   redress of a grievance, as its titles and the database's say; SSHR 1 of
   2008, "2008 Special Session Rules of the House", has no page saved, and the
   docket's "SS" and the House adopting it alone are what name it. A code
   with no name here is shown as its letters. A request is not numbered yet
   and its type is the kind of measure it asks for (`body`). */
const TYPE_NAME=Object.assign(Object.create(null),{
  HB:"House Bill",SB:"Senate Bill",HR:"House Resolution",SR:"Senate Resolution",
  HCR:"House Concurrent Resolution",SCR:"Senate Concurrent Resolution",
  CACR:"Constitutional Amendment Concurrent Resolution",
  HJR:"House Joint Resolution",SJR:"Senate Joint Resolution",
  HBI:"House Bill of Intent",HA:"House Address",HCO:"House Concurrent Order",
  PET:"Petition",SSHB:"Special Session House Bill",SSSB:"Special Session Senate Bill",
  SSHR:"Special Session House Resolution",
  SSHCR:"Special Session House Concurrent Resolution"});
const TYPEORDER=["HB","SB","HR","SR","HCR","SCR","CACR","HJR","SJR",
  "HBI","HA","HCO","PET","SSHB","SSSB","SSHR","SSHCR"];
const typeOf=b=>b&&b.lsr?String(b.body||"").toUpperCase()
  :((/^[A-Za-z]+/.exec(String((b&&b.id)||""))||[""])[0]).toUpperCase();
const typeCmp=(a,b)=>{const x=TYPEORDER.indexOf(a),y=TYPEORDER.indexOf(b);
  return (x<0?TYPEORDER.length:x)-(y<0?TYPEORDER.length:y)||String(a).localeCompare(String(b));};
// WHAT THE BALLOT CODE SAYS, AND NOTHING IT DOES NOT. Each line is attributed
// to the record ("Recorded as ...") because the roll call carries the code and
// no reason. On 42% of the House member-days with an Excused ballot,
// 1999-2026, the member voted on another question that day, and a declared
// conflict of interest is coded Excused too; on 81% of those with a Not
// Excused ballot the member voted that day; and 12 roll calls record two
// members presiding. The old lines claimed a whole day arranged beforehand
// with a reason, a single presiding member who votes only on a tie, and a
// member who walked out to avoid the vote. The labels are the person's to
// change.
// These strings are inserted into the page unescaped: no <, & or ".
const OTHER=[["Presiding","Presiding",
  "Recorded as presiding: in the chair, running the chamber for this vote, so no yes or no is recorded for them. The Speaker, the Senate President or a member filling in for them presides. It is not a missed vote."],
 ["Not Voting/Excused","Excused absence",
  "Recorded as excused from this vote. An excuse can cover a whole day, part of a day or a single vote, so a member excused here may have cast other votes the same day."],
 ["Not Voting/Not Excused","Absent, not excused",
  "Recorded as not voting and not excused. The roll call does not say why, or whether the member was in the chamber."]];

/* THE BILL MATCHER IS SHARED WITH THE HEADER SEARCH. Every line between a
   "BILLMATCH:BEGIN" and the "BILLMATCH:END" after it is copied by
   build_pages.py into site/billmatch.js, which find.js loads on the pages
   that do not run this file -- so the header's "All 30 bills found for
   firearms" is counted by the same code that lists /bills?q=firearms, not by
   a second matcher that drifts from this one. What is inside the markers must
   therefore stand alone: no DOM, no page state, and nothing it names that is
   declared outside a marked region. preflight runs the copy on its own and
   fails if it does not. */
