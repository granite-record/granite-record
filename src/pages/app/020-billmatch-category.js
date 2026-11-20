// BILLMATCH:BEGIN -- a bill's category, which best match reads to put a bill
// still moving first (sortRows, 16 October 2026); see the note above SYN.
// From here, and not from the filter's lines above it: statusCat needs
// nothing they declare.
// Each word a chip can say that is not a stage, and what it is. Not
// introduced, and the one bill only proposed for the 2006 special session
// (HB 3, whose record says nothing after the proposal), ended there; a
// constitutional amendment the voters turned down died at the ballot, one
// they ratified passed, and one still going to them has not concluded; a bill
// awaiting the governor has not concluded either.
const CAT_OF_CHIP=Object.assign(Object.create(null),{
  "Became Law":"Passed","Died":"Died","Interim Study":"Interim Study",
  "Tabled":"Tabled","Vetoed":"Vetoed","Withdrawn":"Withdrawn",
  "Not introduced":"Died","Proposed for the special session":"Died",
  "Passed both chambers, ratified by the voters":"Passed",
  "Passed both chambers, not ratified by the voters":"Died",
  "Passed, awaiting the governor":"In Progress"});
// The stages a bill goes through, which are its chip while its session sits
// (build_site_v2's BEFORE_CONFERENCE and the re-referral): named here as well
// as caught by their kind below, so that an address naming one finds the
// bills still moving out of session too, when no chip says it.
["In committee","In progress","Retained in committee","Re-referred to committee",
 "Committee report filed","Passed one chamber","In a committee of conference",
 "Conference committee report adopted","One chamber did not concur",
 "One chamber did not concur; a committee of conference was asked for"]
  .forEach(w=>{CAT_OF_CHIP[w]="In Progress";});
// And by the kind, for every word not above: a stage of a bill still moving
// (In committee, Passed one chamber, ...) is In Progress, a resolution
// adopted (Adopted by the House, by the Senate, by both chambers) Passed.
const CAT_OF_KIND=Object.assign(Object.create(null),{active:"In Progress",
  law:"Passed",adopted:"Passed",study:"Interim Study",done:"Died",veto:"Died"});
// A chip's word as its category, or "" where the word alone does not say:
// the words above, any resolution adopted (Adopted by the House, by the
// Senate, by both chambers) and an amendment still going to the voters,
// whatever November its line names.
//
// AND ONE THAT WENT TO THEM, WHOSE ANSWER IS NOT IN (the release review of 16
// October 2026). From the day after its election the same amendment says
// "went to the voters" (build_site_v2.cacr_to_the_voters) until a person
// types the count into ballot_results.json, and then Ratified or Not
// Ratified. Its kind is adopted, so it fell to CAT_OF_KIND and read Passed:
// CACR 13 would have been filed under Passed on 4 November 2026 whatever two
// thirds of the voters said. Nothing has concluded that the record knows of,
// so it stays where it was the day before.
function catOfChip(c){
  const s=String(c||"");
  if(CAT_OF_CHIP[s])return CAT_OF_CHIP[s];
  if(/^Adopted by /.test(s))return "Passed";
  if(/^Passed both chambers, (?:goes|went) to the voters/.test(s))return "In Progress";
  return "";
}
// A bill request's status words, which are its categories (Requested: no bill
// yet; Filed: its text is public; Introduced: its bill was introduced, and the
// request forwards to it -- the owner's third stage, 17 November 2026;
// Withdrawn). Nothing else is one.
const REQ_STATUS=Object.assign(Object.create(null),{Requested:"Requested",Filed:"Filed",
  Introduced:"Introduced",Withdrawn:"Withdrawn"});
// A request's own word, and "" for a row with no chip that is not a request.
function statusCat(b){
  const c=b&&b.chip;
  if(!c)return (b&&b.lsr&&REQ_STATUS[b.status])||"";
  return catOfChip(c)||CAT_OF_KIND[b.kind]||"In Progress";
}
// BILLMATCH:END
