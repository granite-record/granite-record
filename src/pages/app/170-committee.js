// ------------------------------------------------------------- committee ---
// Laid out the way the General Court lays out its own committee pages,
// because that is the layout the people who use these pages already know:
// the officers and the staff side by side, then the whole membership, then
// what the chamber's rules say the committee is for.
// WRITING TO A WHOLE COMMITTEE. Every one of these addresses is published
// by the General Court and 404 of them are already on this site's own member
// pages, so nothing is disclosed here that was not already public. They go in
// the To field rather than Bcc: a person writing to a committee should be
// able to see, and say, who they are writing to.
//
// A member who has left the House keeps their seat in the record and has no
// address on file, so they are not in the link and the count says so. The
// largest committee, House Finance, makes a 720-character mailto with 26
// addresses in it -- well inside what a mail client will take.
function emailCommittee(c){
  const seats=(c.members||[]).filter(m=>m.sitting!==false);
  const with_=seats.filter(m=>m.email);
  if(!with_.length)return "";
  const to=with_.map(m=>m.email).join(",");
  const subject=`${c.name||"Committee"} ${c.chamber==="S"?"(Senate)":"(House)"}`;
  const href=`mailto:${encodeURIComponent(to).replace(/%2C/g,",")}`
    +`?subject=${encodeURIComponent(subject)}`;
  const missing=seats.length-with_.length;
  return `<p class="cmail"><a class="btn" href="${href}">Email the
    ${with_.length} members of this committee</a>${missing?
    `<span class="src"> ${missing} member${missing===1?" has":"s have"} no
     address on file</span>`:""}</p>`;
}

// A NUMBER THE GENERAL COURT GAVE TWO COMMITTEES. Its own records file the
// Senate's Development, Recreation and Environment of 1989-1990 under S03, the
// code they later gave the Senate's Appropriations, and the person decided on
// 25 September 2026 that the two are different committees, listed separately
// (committee_names.GAPS). Each has its own page, and build_committees writes
// `same_code` into both so that each says so plainly and names the other: a
// reader who knows the code, or who came from a bill-status page printing
// APPROPRIATIONS over a 1989 bill, is not left to wonder which is which.
function sameCode(c){
  const s=c.same_code||{};
  const others=(s.others||[]).filter(o=>o.page&&o.name);
  if(!s.code||!others.length)return "";
  const word=c.chamber==="S"?"Senate":"House";
  const them=xs=>joinList(xs.map(o=>`the ${word} Committee on <a href="committee/${
    esc(o.page)}">${esc(o.name)}</a> (${esc(o.years||"")})`),"and");
  const num=`<b>${esc(s.code)}</b>`;
  const later=others.filter(o=>o.when==="later"),
        earlier=others.filter(o=>o.when==="earlier");
  const said=later.length===others.length
    ? `The General Court files this committee under the code ${num} in its own
       records, and later gave the same number to ${them(later)}.`
    : earlier.length===others.length
    ? `The General Court&rsquo;s own records also file an earlier committee under
       the code ${num}: ${them(earlier)}.`
    : `The General Court files this committee under the code ${num} in its own
       records, and gave the same number to ${them(others)} as well.`;
  return `<p class="src">${said} ${others.length===1?"The two are":"They are"}
    different committees, each with its own page here.</p>`;
}


// Each row as the index has it, with what this committee reported on it
// (committee_acts.reported, build_committees), which its card says.
const cmteBills=c=>((c.bills||{})[pageTerm()]||[]).map(r=>
  Object.assign({},idxRow(r),{_line:reportedLine(r.reported)}));
const cmteSessions=c=>(c.sessions||[])
  .filter(s=>!pageTerm()||!s.term||s.term===pageTerm());

function renderCommitteeBills(c){
  const rows=cmteBills(c),t=pageTerm();
  // .fill on the notes that stand in for an empty pane: the width it has (F9).
  if(!rows.length)return `<p class="src fill">No bills were referred to this
    committee in the ${esc(termDash(t))} term.</p>`;
  return billPane(rows,(n,of)=>`${billsOf(n,of)} referred to
    this committee in ${esc(termDash(t))}.`,true);
}

