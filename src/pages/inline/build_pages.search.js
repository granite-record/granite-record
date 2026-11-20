document.addEventListener("DOMContentLoaded",function(){
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const box=document.getElementById("resq");
const out=document.getElementById("resout");
const said=document.getElementById("ressay");
const head=document.getElementById("reshead");
const lead=document.getElementById("reslead");
if(!box||!out)return;

// THE CHAMBERS ARE NOT INTERLEAVED. Every listing of legislators on this site
// puts the Senate and the House under their own headings, and a list of search
// results is a listing. r[2] is "Senate — SD22 — Republican" or "House — ...",
// which is where the chamber is; a row that says neither falls to the last
// bucket rather than being dropped.
const GROUPS=[
  // THE GUIDES STRAIGHT AFTER THE BILLS, AND LEARN WITH THIS SITE'S PAGES
  // (17 October 2026: "the how to guides should be incorporated into the
  // search in some fashion"). A guide is found by its task and its plain
  // words (find.js, _fnamed). It led the page until 8 November 2026, when
  // Alice put it after the bills, as the header's panel puts it: "minimum
  // wage" opened on the guide to your rights at work above the seven bills
  // on it. The Learn pages, which this page listed nowhere before, go with
  // the site's other pages, after the bills.
  // A STATUTE ASKED FOR BY ITS NUMBER, FIRST (the audit of 25 October 2026,
  // M3): find.js's one Law row, "RSA 91-A" (findLawRow).
  {t:"Laws",h:tr("sr.g.laws","Laws"),w:[tr("sr.w.laws_one","law"),tr("sr.w.laws_many","laws")],k:r=>r[0]==="law"&&!findLawIsTitle(r)},
  {t:"Senators",h:tr("sr.g.senators","Senators"),w:[tr("sr.w.senators_one","senator"),tr("sr.w.senators_many","senators")],k:r=>r[0]==="legislator"&&/^Senate/.test(r[2])},
  {t:"Representatives",h:tr("sr.g.representatives","Representatives"),w:[tr("sr.w.representatives_one","representative"),tr("sr.w.representatives_many","representatives")],k:r=>r[0]==="legislator"},
  // THE MEMBERS-ELECT, AFTER THE MEMBERS (the owner, 16 November 2026: find.js,
  // A MEMBER-ELECT), each chamber under its own heading as the members are.
  {t:"Senators-Elect",h:tr("sr.g.senators_elect","Senators-Elect"),w:[tr("sr.w.senators_elect_one","senator-elect"),tr("sr.w.senators_elect_many","senators-elect")],k:r=>r[0]==="elect"&&/^Senate/.test(r[2])},
  {t:"Representatives-Elect",h:tr("sr.g.representatives_elect","Representatives-Elect"),w:[tr("sr.w.representatives_elect_one","representative-elect"),tr("sr.w.representatives_elect_many","representatives-elect")],k:r=>r[0]==="elect"},
  // A committee that no longer sits goes with the people who have left, below
  // the ones that do (find.js, _fgone).
  {t:"Committees",h:tr("sr.g.committees","Committees"),w:[tr("sr.w.committees_one","committee"),tr("sr.w.committees_many","committees")],k:r=>r[0]==="committee"&&!r[5]},
  // A city above its wards, each ward a Ward (find.json, 25 October 2026).
  {t:"Towns and Wards",h:tr("sr.g.towns_and_wards","Towns and Wards"),w:[tr("sr.w.towns_and_wards_one","town or ward"),tr("sr.w.towns_and_wards_many","towns and wards")],k:r=>r[0]==="town"||r[0]==="ward"},
  {t:"Subjects",h:tr("sr.g.subjects","Subjects"),w:[tr("sr.w.subjects_one","subject"),tr("sr.w.subjects_many","subjects")],k:r=>r[0]==="topic"},
  // THE OFFICIALS PAGE AND ITS TABS, before the bills where a name of theirs
  // was typed (the audit of 25 October 2026, M3): "my senator" is the page,
  // "ayotte" its Executive Branch, "shaheen" its Federal Delegation.
  {t:"Officials",h:tr("sr.g.officials","Officials"),w:[tr("sr.w.officials_one","officials page"),tr("sr.w.officials_many","officials pages")],k:r=>r[0]==="page"&&/^[/]?officials([#?]|$)/.test(r[3])},
  // Drawn with the bills, straight after them, wherever they go (draw).
  {t:"How-To Guides",h:tr("sr.g.how_to_guides","How-To Guides"),w:[tr("sr.w.how_to_guides_one","how-to guide"),tr("sr.w.how_to_guides_many","how-to guides")],k:r=>r[0]==="guide"},
  // Their own group, after the bills (AFTER): find.js, _fstudy (18 October 2026).
  {t:"Statutory and Study Committees",h:tr("sr.g.statutory_and_study_committees","Statutory and Study Committees"),w:[tr("sr.w.statutory_and_study_committees_one","statutory or study committee"),tr("sr.w.statutory_and_study_committees_many","statutory and study committees")],k:r=>r[0]==="statutory"||r[0]==="study"},
  {t:"Former Senators",h:tr("sr.g.former_senators","Former Senators"),w:[tr("sr.w.former_senators_one","former senator"),tr("sr.w.former_senators_many","former senators")],k:r=>r[0]==="former"&&/^Senate/.test(r[2])},
  {t:"Former Representatives",h:tr("sr.g.former_representatives","Former Representatives"),w:[tr("sr.w.former_representatives_one","former representative"),tr("sr.w.former_representatives_many","former representatives")],k:r=>r[0]==="former"&&/^House/.test(r[2])},
  {t:"Former Members",h:tr("sr.g.former_members","Former Members"),w:[tr("sr.w.former_members_one","former member"),tr("sr.w.former_members_many","former members")],k:r=>r[0]==="former"},
  {t:"Former Committees",h:tr("sr.g.former_committees","Former Committees"),w:[tr("sr.w.former_committees_one","former committee"),tr("sr.w.former_committees_many","former committees")],k:r=>r[0]==="committee"},
  {t:"Learn",h:tr("sr.g.learn","Learn"),w:[tr("sr.w.learn_one","Learn page"),tr("sr.w.learn_many","Learn pages")],k:r=>r[0]==="learn"},
  // A CHAPTER FOUND BY ITS TITLE, after the guides and the Learn pages (the
  // owner, 10 November 2026; find.js, findLawTitles).
  {t:"Law Chapters",h:tr("sr.g.law_chapters","Law Chapters"),w:[tr("sr.w.law_chapters_one","law chapter"),tr("sr.w.law_chapters_many","law chapters")],k:findLawIsTitle},
  {t:"Pages on This Site",h:tr("sr.g.pages_on_this_site","Pages on This Site"),w:[tr("sr.w.pages_on_this_site_one","page on this site"),tr("sr.w.pages_on_this_site_many","pages on this site")],k:r=>r[0]==="page"}
];

// A committee by its chamber, as the header's rows show it (find.js, findName).
const row=(r,q)=>`<a href="${esc(_froot(r[3]))}">
  <span class="fl1"><span class="fname">${_fmark(findName(r),q)}</span>
  ${chip(findKind(r),"fkind")}</span>
  ${findWhat(r,q)?`<span class="fwhat">${esc(findWhat(r,q))}</span>`:""}</a>`;

// THE BILLS, counted. Until 24 September this was one card at the foot of the
// page, "Search every bill for firearms", under a line saying nothing on the
// site matched -- over 30 bills of this term. find.js's findBills counts them
// with the bill search's own matcher, so the number here is the one /bills?q=
// then shows, and the first five are listed. Before they are counted, or if
// they cannot be, the card offers the bill search without a number.
//
// Its description used to say the bill search reads "the words in its text"
// when it read a bill's number, title, sponsor and committee. Since 1 October
// it does read the topic, the analysis and the text (build_search_index.py),
// and a row found that way says so.
const WHAT=tr("sr.what","The bill search has every term since 1989, with filters for committee, sponsor and what became of it.");
const WHAT_ALL=tr("sr.what_all","In the bill search, with filters for committee, sponsor and what became of it.");
/* EVERY TERM'S BILLS (the person, 24 September: "all terms should show up in
   the full search results"). Until then this page counted the current
   term's alone, as the header's panel does, so a reader looking for SB 412
   of 2000 or the bail bills of 2019 was told about 2026's. B is what the page
   counts: every term's once findBillsLoadAll has them all, and the current
   term's until then or if it cannot, with the page saying which. C is the
   current term's, which gets a row of its own under the total, since the
   bill search opens on it. The rows are dated -- "SB 412 (2000)" -- because
   across terms a number alone names up to nineteen bills, and for a number
   every one of them is listed rather than the first five: SB 412 is in
   fourteen terms, and the 2000 bill is the twelfth of them. */
/* NEXT SESSION'S REQUESTS, ON ONE LINE OF THEIR OWN (the audit of 25
   October 2026, S5): how many of them match, as the line above says how many
   of the bills are this term's, and the bill search opened on their list.
   Not a group and not in the bills' count: requests are not bills yet, and
   no term's (find.js, FREQ). R is findBills(q,0,"requests"). */
const asked=(q,R)=>R&&R.state==="ready"&&R.n
  ?`<a class="fbills" href="/bills?q=${_fenc(q)}&amp;term=${_fenc(R.term)}">
    <span class="fl1"><span class="fname">${R.n===1?tr("sr.one_request_for","1 bill request for {year}",{year:esc(FREQ.year)})
      :tr("sr.n_requests_for","{n} bill requests for {year}",{n:R.n.toLocaleString(),year:esc(FREQ.year)})}</span></span>
    <span class="fwhat">${tr("sr.not_yet","Not bills yet: listed in the bill search under {label}.",{label:esc(FREQ.label||tr("sr.its_requests","its bill requests"))})}</span></a>`:"";
/* A MEMBER'S BILLS WHERE THEIR NAME LISTS NONE (the audit of 25 October 2026,
   M3). A name finds the person and never their bills (app.js, A NAME IS NOT
   WHAT A BILL IS ABOUT), so "daryl abbas" was told "no bill in any of the
   19 terms" under Sen. Abbas, whom the index names as sponsor or co-sponsor
   of 182 (the preview's, 25 October 2026). Where the search finds a
   member by a whole word of their name and no bill, the bills' place is one
   link: theirs, the Sponsor filter on All terms, with the name the bills
   give their sponsor -- the prime sponsor's of a bill whose sponsor_slug is
   the member's page, or their own name where they only co-sponsored, which
   the index spells as the member's (every one of the 328 sitting members
   with a bill, on 25 October 2026). A member no bill names keeps the line
   that says so. {who, name} for the first such member in `rows`, or null.
   A former member elected again is a member-elect's row (find.js, A
   MEMBER-ELECT), and their bills are theirs as before. */
const memberBills=(rows,s)=>{
  const pool=FALL.rows||FBILLS.file||[];
  for(const m of rows){
    if((m[0]!=="legislator"&&m[0]!=="former"&&m[0]!=="elect")||!_fwhole(m,s))continue;
    const slug=String(m[3]||"").replace(/^[/]?legislator[/]/,"").replace(/[.]html$/,"");
    const who=_fbare(findName(m)).replace(/[ ]*[(][^()]*[)]$/,"");
    const own=_fbare(m[1]).replace(/[ ]*[(][^()]*[)]$/,"").replace(/^(Rep|Sen)[.](-elect)? /,"");
    const b=pool.find(x=>x.sponsor_slug===slug);
    const name=b?b.sponsor:pool.some(x=>(x.cosp||[]).includes(own))?own:"";
    if(name)return {who,name};
  }
  return null;
};
const theirs=M=>`<a class="fbills" href="/bills?sponsor=${_fenc(M.name)}&amp;term=all">
    <span class="fl1"><span class="fname">${tr("sr.whose_bills","{who}&rsquo;s bills",{who:esc(M.who)})}</span></span>
    <span class="fwhat">${tr("sr.theirs","Every bill they sponsored or co-sponsored, in the bill search.")}</span></a>`;
const bills=(q,B,C,counting,R,mem)=>{
  const counted=B&&B.state==="ready";
  const every=counted&&B.every;
  const what=every?WHAT_ALL:counting?tr("sr.counting","Counting the earlier terms&hellip;"):WHAT;
  const none=every?tr("sr.none_all","None in any of the {n} terms.",{n:B.terms.length})
    :counted?tr("sr.none_term","None in the {term} term.",{term:esc(termWords(B.term))}):"";
  const now=every&&C&&C.state==="ready"&&C.n&&C.n<B.n
    ?`<a class="fbills" href="/bills?q=${_fenc(q)}">
      <span class="fl1"><span class="fname">${tr("sr.of_them","{n} of them in the {term} term",{n:C.n.toLocaleString(),term:esc(termWords(C.term))})}</span></span>
      <span class="fwhat">${tr("sr.current_term","The current term, where the bill search starts.")}</span></a>`:"";
  const top=B&&B.top?(B.numbers?B.top:B.top.slice(0,5)):[];
  const body=(counted&&B.n
    ?findBillsAll(B,q,what)+now+top.map(b=>findBillRow(b,q,every,B.why.get(b))).join("")
    :counted&&mem?theirs(mem)
    :counted
    ?`<a href="/bills?q=${_fenc(q)}">
      <span class="fl1"><span class="fname">${tr("sr.search_every","Search every bill for &ldquo;{q}&rdquo;",{q:esc(q)})}</span></span>
      <span class="fwhat">${none} ${counting?what:WHAT}</span></a>`
    :findBillsAll(B,q,WHAT))+asked(q,R);
  return `<section class="resgrp"><h2>${tr("sr.g.bills","Bills")}${counted&&B.n
    ?` <span class="resn">${B.n.toLocaleString()}</span>`:""}</h2>
    <div class="findout resout">${body}</div></section>`;
};
// Groups a reader reaches for after the bills: members who have left, and
// this site's own pages.
const AFTER=new Set(["Statutory and Study Committees","Former Senators","Former Representatives",
  "Law Chapters","Former Members","Learn","Pages on This Site"]);
let waiting=false,waitingAll=false,waitingWords=false,waitingLaw=false,waitingReq=false;

function draw(q){
  const s=(q||"").trim();
  if(!s){
    tell("");
    head.textContent=tr("sr.head","Search the record");
    lead.textContent=tr("sr.lead","Every sitting legislator and every member who has left, every committee, every town and ward, every subject bills are filed under, and every bill since 1989.");
    out.innerHTML="";
    return;
  }
  const rows=findMatch(s,Infinity);
  // A statute's number: the Laws pages' list of chapters, then drawn again.
  const law=findLawRow(s);
  if((law&&law.loading||findLawsWanted(s))&&!waitingLaw){
    waitingLaw=true;
    findLawsLoad().then(()=>draw(box.value));
  }
  const C=findBills(s,40);
  const A=findBills(s,40,true);
  // Next session's requests, counted apart (find.js, FREQ).
  const R=findBills(s,0,"requests");
  if(R&&R.state==="loading"&&!waitingReq){
    waitingReq=true;
    findRequestsLoad().then(()=>draw(box.value));
  }
  if(C&&C.state==="loading"&&!waiting){
    waiting=true;
    findBillsLoad().then(()=>draw(box.value));
  }
  if(A&&A.state==="loading"&&!waitingAll){
    waitingAll=true;
    findBillsLoadAll().then(()=>draw(box.value));
  }
  const B=A&&A.state==="ready"?A:C;
  // This term's count is on the page while the others are still coming.
  const counting=!!(A&&A.state==="loading"&&B&&B.state==="ready");
  const nB=B&&B.state==="ready"?B.n:null;
  const term=nB===null?"":B.every?tr("sr.across","across all {n} terms",{n:B.terms.length})
    :tr("sr.in_term","in the {term} term",{term:termWords(B.term)});
  const noBill=nB===null?"":B.every?tr("sr.no_bill_all","no bill in any of the {n} terms",{n:B.terms.length})
    :tr("sr.no_bill_term","no bill in the {term} term",{term:termWords(B.term)});
  // A member found by a whole word of their name, where no bill is: the
  // bills' place is their bills (theirs), and the lead says no "no bill".
  const mem=nB===0?memberBills(rows,s):null;
  const nR=R&&R.state==="ready"?R.n:0;
  // A REQUEST'S NUMBER LEADS WITH THE REQUEST (the owner, 11 November 2026:
  // "2027-0002" was told nothing matched, with the request on one line far
  // below): its own row, number, title and sponsor, linking to its page,
  // above everything else. Requests are not bills, so they are a group of
  // their own and never in the bills' count.
  const RQ=findIsRequest(s)?findBills(s,5,"requests"):null;
  const reqRows=RQ&&RQ.state==="ready"?RQ.top:[];
  const reqWait=!!(RQ&&RQ.state==="loading");
  const reqSection=reqRows.length
    ?`<section class="resgrp"><h2>${tr("sr.g.requests","Bill Requests")}
      <span class="resn">${reqRows.length}</span></h2>
      <div class="findout resout">${reqRows.map(b=>findRequestRow(b,RQ.term,s)).join("")}</div></section>`:"";
  head.innerHTML=tr("sr.results_for","Results for &ldquo;{q}&rdquo;",{q:esc(s)});
  // The answer first. "0 matches on this site, and the bills" is a sentence
  // nobody would write, and "nothing matches" above 30 bills is false.
  // PAGES, NOT "MATCHES ON THIS SITE" (17 October 2026): "4 matches on this
  // site, and 940 bills" left a reader to work out that the four are the
  // legislators, committees, towns and subjects listed below.
  const here=rows.length===1?tr("sr.one_page","One page on this site")
    :tr("sr.n_pages","{n} pages on this site",{n:rows.length});
  const some=nB===1?tr("sr.one_bill","One bill {where}",{where:term})
    :tr("sr.n_bills","{n} bills {where}",{n:(nB||0).toLocaleString(),where:term});
  lead.textContent=reqRows.length&&!rows.length&&!nB
    ?(reqRows.length===1?tr("sr.lead.request_one","A bill request for {year}. It is not a bill yet.",{year:FREQ.year})
      :tr("sr.lead.request_n","{n} bill requests for {year}. They are not bills yet.",{n:reqRows.length,year:FREQ.year}))
    :reqWait&&!rows.length&&!nB?tr("sr.lead.request_wait","Looking for that bill request…")
    :(!rows.length
    ?(nB?(nB===1?tr("sr.lead.one_only","{some} matches. No legislator, committee, town or subject on this site does.",{some})
        :tr("sr.lead.n_only","{some} match. No legislator, committee, town or subject on this site does.",{some}))
      :nB===0&&!counting&&!nR?tr("sr.lead.nothing","Nothing on this site matches that: no legislator, committee, town or subject, and {nobill}.",{nobill:noBill})
      :nB===0?tr("sr.lead.none_and","No legislator, committee, town or subject on this site matches that, and {nobill}.",{nobill:noBill})
      :tr("sr.lead.none","No legislator, committee, town or subject on this site matches that."))
    :nB?tr("sr.lead.here_bills","{here}, and {some}.",{here,some:some.charAt(0).toLowerCase()+some.slice(1)})
    :nB===0&&mem?tr("sr.lead.here","{here}.",{here})
    :nB===0?tr("sr.lead.here_nobill","{here}, and {nobill}.",{here,nobill:noBill})
    :tr("sr.lead.here_the_bills","{here}, and the bills.",{here}))
    +(counting?" "+tr("sr.counting_text","Counting the earlier terms…"):"");
  // WHERE THE BILLS GO, as in the header's panel: first unless a sitting
  // member, committee, town or subject has every word typed as a whole word
  // of its name (_fwhole), and then after those and ahead of the members who
  // have left. "bail" leads with the bail bills; "bailey" with Rep. Bailey.
  // A BILL NUMBER LEADS WITH THE BILLS, whatever else has its words (17
  // October 2026): a guide found by its own words is never put above a bill
  // whose number was typed. A GUIDE OR A LEARN PAGE PUTS NOTHING ABOVE THE
  // BILLS (8 November 2026): their place is beside the bills (withBills,
  // below), so their words are no reason for the members and towns that
  // only begin with the words typed to go first.
  const named=!findBill(s)&&rows.some(r=>(r[0]==="law"&&!findLawIsTitle(r))
    ||(r[0]!=="former"&&r[0]!=="guide"&&r[0]!=="learn"&&_fwhole(r,s)));
  const left=rows.slice(),counts=[];
  // The bills' part of the line a screen reader hears, where the page puts
  // their group.
  const billsSaid=()=>{
    if(nB)counts.push(nB===1?tr("sr.c.one_bill","1 bill"):tr("sr.c.bills","{n} bills",{n:nB.toLocaleString()}));
    if(nR&&!reqRows.length)counts.push(nR===1?tr("sr.c.one_request","1 bill request"):tr("sr.c.requests","{n} bill requests",{n:nR.toLocaleString()}));
  };
  const section=(g,mine)=>{
    counts.push(`${mine.length} ${g.w[mine.length===1?0:1]}`);
    return `<section class="resgrp"><h2>${esc(g.h)}
      <span class="resn">${mine.length}</span></h2>
      <div class="findout resout">${mine.map(r=>row(r,s)).join("")}</div></section>`;
  };
  // THE GUIDES STRAIGHT AFTER THE BILLS, wherever the bills go (Alice, 8
  // November 2026, as the header's panel has them): taken out of the
  // groups' turn and drawn with the bills, so a member found only by the
  // start of a word, who follows the bills, does not come between.
  // WHERE NO BILL MATCHES, THE GUIDES TAKE THE BILLS' PLACE, as the panel
  // draws them with its count at none, and the box saying there is none
  // waits its turn after what does match, as it did before (the review of 8
  // November 2026): "renew my license" put its guide under that box, and
  // "register my car" the box above the County Officials page. Known once
  // the bills are counted at none -- this term's, which come first, while
  // the rest are counted -- so the guide does not stand under the box for
  // the seconds every term takes and then jump above it; a bill an earlier
  // term turns up takes its place above the guide.
  const GUIDES=GROUPS.find(g=>g.t==="How-To Guides");
  const guides=left.filter(GUIDES.k);
  for(const r of guides)left.splice(left.indexOf(r),1);
  const none=nB===0&&!nR&&guides.length>0;
  const theGuides=()=>guides.length?section(GUIDES,guides):"";
  let html="",placed=false,boxed=false;
  if(reqRows.length)counts.push(reqRows.length===1?tr("sr.c.one_request","1 bill request"):tr("sr.c.requests","{n} bill requests",{n:reqRows.length.toLocaleString()}));
  const billsBox=()=>{boxed=true;const h=bills(s,B,C,counting,reqRows.length?null:R,mem);billsSaid();return h;};
  const atBills=()=>{placed=true;return none?theGuides():billsBox()+theGuides();};
  html+=reqSection;
  if(!named)html+=atBills();
  for(const g of GROUPS){
    const mine=[];
    for(let i=left.length-1;i>=0;i--)
      if(g.k(left[i]))mine.unshift(left.splice(i,1)[0]);
    if(!mine.length)continue;
    if(AFTER.has(g.t)){if(!placed)html+=atBills();if(!boxed)html+=billsBox();}
    html+=section(g,mine);
  }
  if(!placed)html+=atBills();
  if(!boxed)html+=billsBox();
  let offered=[],offering=false;
  // Only when something close exists, and only when no bill matched either
  // ("voting" was offered "zoning" over 141 bills). find.js's findOffers
  // gives a name close to what was typed and the word of the bills that a
  // misspelt one sounds like ("medicade", "firarms"), and nothing rather
  // than reaching: a word any bill has used is never offered as another.
  // Not while the earlier terms are still being counted either.
  if(!rows.length&&!nB&&!nR&&!(B&&B.state==="loading")&&!counting){
    const offer=findOffers(s,!!(B&&B.every));
    if(offer.wait&&!waitingWords){
      waitingWords=true;
      offer.wait.then(()=>draw(box.value));
    }
    offered=offer.words;offering=!!offer.wait;
    const did=offer.words.map(d=>
      `<a href="/search?q=${_fenc(d)}">${esc(d)}</a>`);
    if(did.length)html=`<p class="note">${tr("find.did_you_mean","Did you mean {words}?",{words:did.join(" "+tr("find.or","or")+" ")})}</p>`+html;
  }
  out.innerHTML=html;
  // WHAT THE PAGE FOUND, SAID (the accessibility sweep of 29 October 2026,
  // WCAG 4.1.3): the results are drawn as the reader types, and nothing told
  // a screen reader they had come, or how many, or that there were none --
  // the header's panel has said so since 2 October (find.js, findSay). One
  // line the eye does not see, role="status", the groups in the page's own
  // order: "1 town or ward, 19 bills." Nothing while the bills, the earlier
  // terms, the requests, the Laws pages' list or a word to offer are still
  // on their way, so the answer is said once, when it is whole, and not once
  // a step. The Laws list is fetched only once a statute's number is typed,
  // and "RSA 659" said "No matching results." and then "1 law." (the review
  // of 29 October 2026).
  const unsure=!!(law&&law.loading)||(B&&B.state==="loading")||counting
    ||(R&&R.state==="loading")||offering;
  tell(unsure?"":counts.length?counts.join(", ")+"."
    :tr("find.none","No matching results.")+(offered.length?" "+tr("find.did_you_mean","Did you mean {words}?",{words:offered.join(" "+tr("find.or","or")+" ")}):""));
}
// Written only when it changes, so a redraw that finds what the last one
// found is not said again.
function tell(text){
  if(said&&said.textContent!==text)said.textContent=text;
}

const q0=new URLSearchParams(location.search).get("q")||"";
box.value=q0;
box.disabled=true;
findRows().then(()=>{
  box.disabled=false;
  draw(q0);
  // Typed into rather than submitted: the results are already here, so a
  // round trip would only redraw the same page. The address still follows,
  // because a reader who found something wants to be able to send the link.
  let tm=0;
  box.addEventListener("input",()=>{
    clearTimeout(tm);
    tm=setTimeout(()=>{
      const v=box.value.trim();
      draw(v);
      const me=(window.GR_HREFS||{})["search.html"]||"/search";
      const u=v?`${me}?q=${_fenc(v)}`:me;
      history.replaceState(null,"",u);
    },120);
  });
  if(q0)box.focus();
});
// The back button, when a "Did you mean" link or the panel put a new query in
// the address without reloading.
window.addEventListener("popstate",()=>{
  const v=new URLSearchParams(location.search).get("q")||"";
  box.value=v;draw(v);
});
});
