// ===================================================== THE VOTES PAGE ======
//
// /votes (build_votes_page.py writes the page, build_votes.py the files it
// reads; reports/votes-search-design-2026-11.md, stage 3, under the owner's
// decisions of 12 November 2026):
//
//   - EVERY ROLL CALL FROM 1999, both chambers, a file a term (votes/<term>.json),
//     searched by the bill search's own matcher over the bill the vote was on
//     (billNumbers, queryGroups, readShort, matchScore: never a second one), and
//     for a vote on no bill by the Journal's words for it.
//   - NO LABEL OF HOW THE PARTIES DIVIDED, AND NO MARK ON A MEMBER FOR VOTING
//     AGAINST THEIRS: nothing below reads a party, and the counts of a party
//     in a row's file (pc) are not read at all.
//   - A CLOSE VOTE is the data's own: build_votes.py's `cl`, which is set where
//     5 or fewer voters in the House, or 2 or fewer in the Senate, would have
//     had to switch to change the outcome. A tie is shown as tied.
//   - THE TALLY IS THE COUNTED ONE (the owner's rule of 16 September 2026): y
//     and n are the members' ballots, and the clerk's stated figures (ys, ns)
//     are not drawn.
//   - THE SENATE RECORDS NO TIME OF DAY, and none is shown: a day is told in
//     the roll's own number.
//   - THE PAGE SAYS WHAT IT COVERS ("Roll calls from 1999") and nothing of
//     what came before: older roll calls are a later stage.
//   - THE MEMBER FILTER reads the term's ballot strings (votes/ballots-<term>.json,
//     one character a member), fetched when a member is chosen.
//   - EVERY FILTER IS IN THE ADDRESS: ?q=&term=&body=&from=&to=&day=&result=
//     &margin=&kind=&member=&sort=, so a link reproduces what is on the screen.
//     A filter of boxes takes a value a parameter, as the bill search's do
//     (?kind=Amendment&kind=Passage), so ?kind=Amendment, which every link
//     written before the boxes names, ticks the one box it names.
//   - A SESSION DAY (day=, the review of 14 November 2026) is the roll calls
//     its page counts, which the roll-call file may date a day or more later:
//     a row's `s` (build_votes.py) where it does. From and To are the dates
//     the file gives, as each row shows them.
//   - THE TERM FOLLOWS what is chosen where the reader has not picked one: the
//     term of the dates or the day, or of the member's votes, or every term
//     where they span several (votesTermDefault); the address and the
//     controls ask the same function, so a link opens on what was on screen.
//   - THE CONTROLS ARE THE BILL SEARCH'S (the owner on the bench, 24 November
//     2026: "The votes page filters should be more similar to the left
//     sidebar search filters on bill and law pages"; 25 November, start it):
//     the term picker, the box, the Sort and the count across the top, the
//     filters at the side in the bill search's groups, drawn by its own
//     pieces (fgroupFrame, fcheck), and on a narrow screen its Filter button
//     over them (votesFacets).
//
// A row is the member tab's own row (voteRow) -- the date, the bill and the
// question, the result -- and "How everyone voted" opens the bill page's ring
// and party rows in place (voteRing's body), from the bill's record or, for a
// vote on no bill, the term's nobill/ file.
const VT={idx:null,err:"",rows:{},rowsAsked:{},bal:{},balAsked:{},col:{},by:{},words:"",
  people:null,peopleAsked:false,st:null,open:{},kind:null,gs:null,note:"",
  openG:null,cnt:null,present:null,memText:"",drawn:"",termsDrawn:false,sortsDrawn:false};
const VOTES_KINDS=["Committee report","Amendment","Conference report","Veto override",
  "Passage","Motion on a bill","Procedural","Other"];
const VOTES_SORTS=["best","new","close"];
// The orders the list is drawn in, in the Sort's words (the design's: "Best
// match | Newest | Closest"): the best match where there are words, the
// newest roll call first, and the closest first.
const VOTES_SORT_WORDS=[["best","Best match"],["new","Newest"],["close","Closest"]];
const VOTES_SHOW=100;
const VOTES_BALLOT={Y:"Yea",N:"Nay",E:"Not Voting/Excused",X:"Not Voting/Not Excused",
  P:"Presiding",R:"No vote recorded"};
// THE FILTERS THAT ARE SETS OF VALUES, each a group of boxes at the side
// (votesFacets), in this order: the chamber, the result, close and tied, and
// the kind of question.
const VOTES_BODIES=["H","S"],VOTES_RESULTS=["passed","failed"],VOTES_MARGINS=["close","tied"];
const VOTES_TICKS={body:VOTES_BODIES,result:VOTES_RESULTS,margin:VOTES_MARGINS,kind:VOTES_KINDS};
// A row's values for each of them: its chamber, its result, close and tied
// where it is either -- a tie is close where one voter would have carried it,
// and not where the question needed two thirds -- and its kind of question.
function votesValsOf(r,k){
  if(k==="body")return [r.c];
  if(k==="result")return [r.p?"passed":"failed"];
  if(k==="margin")return [r.cl?"close":"",r.y>0&&r.y===r.n?"tied":""].filter(Boolean);
  return [r.k];
}
const votesDay=v=>/^\d{4}-\d{2}-\d{2}$/.test(String(v||""));
// The term a day falls in, from the terms the files name: its year's, or from
// Organization Day, the first Wednesday of December of an even year, the next
// term's, as the roll-call files keep them (proceedings.vote_term): the
// House's sitting of 7 December 2022 is 2023-2024's.
function votesTermOf(iso,terms){
  const s=String(iso||""),y=+s.slice(0,4);
  if(!y)return "";
  const org=y%2?0:1+(3-new Date(Date.UTC(y,11,1)).getUTCDay()+7)%7;
  const yy=org&&+s.slice(5,7)===12&&+s.slice(8,10)>=org?y+1:y;
  return (terms||[]).find(t=>{const [a,b]=String(t).split("-").map(Number);return yy>=a&&yy<=b;})||"";
}
// The terms a member's votes are in, of the terms the files name, where the
// member's record says (a former member's `served`); null where it does not.
const votesOwnTerms=(p,terms)=>p&&p.terms?p.terms.filter(t=>terms.includes(t)):null;
// The term a page opens on where the address names none: the newest; the one
// the session day or the dates name, or every term where they name two; and
// the one that holds a member's votes, or every term where several do and
// the newest is not one of them.
function votesTermDefault(st,terms){
  if(st.day)return votesTermOf(st.day,terms)||"all";
  if(st.from||st.to){
    const a=votesTermOf(st.from,terms),b=votesTermOf(st.to,terms);
    const t=a&&b?(a===b?a:"all"):(a||b);
    return t||"all";
  }
  const own=st.member?votesOwnTerms(votesPerson(st.member),terms):null;
  if(own&&own.length&&!own.includes(terms[0]))return own.length===1?own[0]:"all";
  return terms[0]||"";
}
const votesSortDefault=st=>st.q?"best":"new";
function votesDefault(terms){
  return {q:"",term:terms[0]||"",tauto:true,body:[],from:"",to:"",day:"",result:[],margin:[],
          kind:[],member:"",sort:"",show:0};
}
// The address read into the page's state. A value this does not know is no
// filter, so an old or a mistyped address opens the page as it opens bare. A
// term the address does not name follows what it does (tauto). A filter of
// boxes is each value it names that the filter has, in the filter's order.
function votesRead(search,terms){
  const u=new URLSearchParams(search||""),st=votesDefault(terms);
  const pick=(k,ok)=>{const v=u.get(k)||"";return ok(v)?v:"";};
  const ticked=k=>{const got=u.getAll(k);return VOTES_TICKS[k].filter(v=>got.includes(v));};
  st.q=(u.get("q")||"").trim();
  st.body=ticked("body");
  st.from=pick("from",votesDay);
  st.to=pick("to",votesDay);
  st.day=pick("day",votesDay);
  st.result=ticked("result");
  st.margin=ticked("margin");
  st.kind=ticked("kind");
  st.member=(u.get("member")||"").toLowerCase().replace(/[^a-z0-9-]/g,"");
  st.sort=pick("sort",v=>VOTES_SORTS.includes(v));
  const t=u.get("term")||"";
  st.tauto=!(t==="all"||terms.includes(t));
  st.term=st.tauto?votesTermDefault(st,terms):t;
  return st;
}
// The term again, where the reader has not picked one: after a member, a day
// or the dates are chosen or cleared, and when the members' records arrive.
function votesRetime(st,terms){
  if(st.tauto)st.term=votesTermDefault(st,terms);
}
// The state written into an address: only what differs from the page bare, so
// the address of a page with nothing chosen is /votes.
function votesAddr(st,terms){
  const u=new URLSearchParams(),set=(k,v)=>{if(v)u.set(k,v);},each=k=>st[k].forEach(v=>u.append(k,v));
  set("q",String(st.q||"").trim());
  if(st.term!==votesTermDefault(st,terms))set("term",st.term);
  each("body");set("from",st.from);set("to",st.to);set("day",st.day);each("result");
  each("margin");each("kind");set("member",st.member);
  if(st.sort&&st.sort!==votesSortDefault(st))set("sort",st.sort);
  return u.toString();
}
// How many filters the side has set -- each box ticked, each of the dates, a
// session day and a member: the number the Filter button carries on a
// narrow screen, as the bill search's counts what its groups have ticked.
// The term and the order are across the top, in sight at every width, and
// are not counted.
function votesActive(st){
  return Object.keys(VOTES_TICKS).reduce((n,k)=>n+st[k].length,0)
    +[st.from,st.to,st.day,st.member].filter(Boolean).length;
}
// The one chamber the filter names, "H" or "S", or "" where it names both or neither.
const votesOneBody=st=>st.body.length===1?st.body[0]:"";
// The session day a row's roll call is counted on: the file's date, or the
// day build_votes.py names (`s`), "" where no session day counts it.
const votesSitting=r=>Object.prototype.hasOwnProperty.call(r,"s")?String(r.s||""):r.d;
// The member's ballot on a roll call: Y, N, E, X, P, R, or "." where the member
// was not on it, and null where the ballots are not here (or the member never
// sat in that chamber that term). `ids` are the ids the member has been filed
// under.
function votesLetter(r,ids){
  const B=VT.bal[r.t];
  const ch=B&&B.chambers&&B.chambers[r.c];
  const s=ch&&ch.r&&ch.r[r.id];
  if(!s)return null;
  const k=r.t+"|"+r.c;
  const cols=VT.col[k]||(VT.col[k]=new Map(ch.m.map((m,i)=>[String(m),i])));
  for(const id of ids||[]){const i=cols.get(String(id));if(i!==undefined)return s[i];}
  return null;
}
// Whether a row passes every control but the words: the chamber, the days,
// the result, the margin, the kind of question and the member. `ids` is the
// chosen member's, or null; `ignore`, a filter of boxes left out, which is how
// each group's numbers are counted (votesCounts), as the bill search's are.
function votesPass(r,st,ids,ignore){
  for(const k in VOTES_TICKS){
    const want=st[k];
    if(k!==ignore&&want.length&&!votesValsOf(r,k).some(v=>want.includes(v)))return false;
  }
  if(st.from&&r.d<st.from)return false;
  if(st.to&&r.d>st.to)return false;
  if(st.day&&votesSitting(r)!==st.day)return false;
  if(ids){const l=votesLetter(r,ids);if(!l||l===".")return false;}
  return true;
}
const votesNum=r=>+String(r.id).split("-")[2]||0;
// A day's votes: the House before the Senate, and in each the roll's own
// number, which is the order they were taken in. Neither chamber's clock is
// read: the Senate records none.
const votesNewest=(a,b)=>b.d.localeCompare(a.d)||(a.c===b.c?0:a.c==="H"?-1:1)||votesNum(b)-votesNum(a);
// A bill's index row where its term's index is here, else what the vote
// itself says (a vote on no bill is asked about the Journal's words for it).
function votesBy(t){
  if(!VT.by[t]&&LOADED.has(t)){
    const m=new Map();
    IDX.forEach(b=>{if(b.term===t)m.set(b.id,b);});
    VT.by[t]=m;
  }
  return VT.by[t]||null;
}
// AND THE VOTE'S OWN WORDS (the review of 14 November 2026: "veto" found
// none of the 56 veto overrides of a term, which only the question says):
// the question as the row draws it -- the motion's name and gloss where the
// vote words name it, the record's words -- and its kind of question. A row
// is asked as its bill's index row with these beside the title, so a bill's
// own words and text still find it, and its title is still the title.
function votesOwnWords(r){
  const M=(WORDBOOK.votes||{}).motions||{},m=r.mk&&CMP.own(M,r.mk)?M[r.mk]:null;
  return [m&&m.motion,m&&m.abbr,m&&m.gloss,r.q,r.k].filter(Boolean).join(" ").replace(/[{}]/g," ");
}
function votesSubject(r){
  const m=r.b?votesBy(r.t):null,b=m&&m.get(String(r.b).toUpperCase());
  if(b){
    if(r._sb!==b){
      r._sb=b;r._s=Object.create(b);
      r._s.hayT=`${b.hayT||""} | ${voteNorm(votesOwnWords(r))}`;
    }
    return r._s;
  }
  if(!r._p){
    const id=String(r.b||"").toUpperCase();
    r._p={id,n:id,title:[r.w,r.q].filter(Boolean).join(" "),term:r.t,
      hayT:voteNorm([id,id,r.w,votesOwnWords(r)].join(" ")),hayC:"",_p:1};
  }
  return r._p;
}
function votesBillKey(r){
  try{return r.b?billKey(votesSubject(r)):[1e9,1e9];}catch(_){return [1e9,1e9];}
}
// Best match, as the bill search orders it (sortRows): the newest term, every
// word of the search as a word of the title before the start of a longer one,
// the most of the search, a bill still moving whose title has it, the most of
// the title that is the search, and then a bill's votes together, newest first.
function votesBest(rows,gs){
  const lo=new Map(),sc=new Map(),sh=new Map(),lv=new Map();
  rows.forEach(r=>{
    const s=votesSubject(r);
    if(lo.has(s))return;
    lo.set(s,looseness(s,gs));sc.set(s,matchScore(s,gs));sh.set(s,titleShare(s,gs));
    lv.set(s,sh.get(s)>0&&statusCat(s)==="In Progress"?1:0);
  });
  const sj=r=>votesSubject(r);
  return rows.slice().sort((a,b)=>{
    const x=sj(a),y=sj(b);
    return String(b.t).localeCompare(String(a.t))||lo.get(x)-lo.get(y)||sc.get(y)-sc.get(x)
      ||lv.get(y)-lv.get(x)||sh.get(y)-sh.get(x)
      ||votesBillKey(a)[0]-votesBillKey(b)[0]||votesBillKey(a)[1]-votesBillKey(b)[1]
      ||votesNewest(a,b);});
}
// The rows the words find, whatever the filters: `gs` is the search's groups
// and `ids` the bill numbers it names. The list is those the filters pass,
// and each group's numbers those the other filters pass (votesCounts).
function votesSearched(rows,st,gs,ids){
  if(!st.q)return rows;
  return ids?rows.filter(r=>!!r.b&&ids.includes(String(r.b).toUpperCase()))
    :rows.filter(r=>matchesGroups(votesSubject(r),gs));
}
// Rows in the order the state asks for.
function votesSorted(rows,st,gs){
  const how=st.sort||votesSortDefault(st);
  if(how==="best"&&st.q&&gs)return votesBest(rows,gs);
  if(how==="close")return rows.sort((a,b)=>(a.f==null)-(b.f==null)||(a.f||0)-(b.f||0)||votesNewest(a,b));
  return rows.sort(votesNewest);
}
// The rows of a state, in the order it asks for. `gs` is the search's groups,
// `ids` the bill numbers it names, `mem` the member's ids.
function votesRowsOf(all,st,gs,ids,mem){
  return votesSorted(votesSearched(all.filter(r=>votesPass(r,st,mem)),st,gs,ids),st,gs);
}
// THE NUMBER BESIDE EACH BOX, AS THE BILL SEARCH COUNTS ITS OWN (renderFacets):
// the roll calls the list would hold with that box ticked -- the words found,
// the term shown and every other filter kept, the box's own group left out --
// so a box at none is a box that would list nothing. `hit` is the rows the
// words find (votesSearched), `mem` the member's ids. {group: {value: n}}.
function votesCounts(hit,st,mem){
  const out={};
  for(const k of Object.keys(VOTES_TICKS)){
    const c={};
    for(const r of hit)if(votesPass(r,st,mem,k))for(const v of votesValsOf(r,k))c[v]=(c[v]||0)+1;
    out[k]=c;
  }
  return out;
}
// What "close" says, in the data's own terms: one line, above the list only
// while the Margin filter asks for close votes (the review of 14 November
// 2026: it stood above every list).
function votesCloseWords(){
  const c=(VT.idx&&VT.idx.close)||{H:5,S:2};
  return `Close: ${c.H} or fewer House voters, or ${c.S} or fewer senators, would have had to switch to change the outcome.`;
}
function votesClose(r){
  if(r.y>0&&r.y===r.n)return "Tied";
  if(!r.cl)return "";
  return r.f===1?"Close: 1 voter would have had to switch":`Close: ${r.f} voters would have had to switch`;
}

// ---- what the page fetches, each once; the list is drawn again as it arrives
function votesNeedRows(t){
  if(VT.rows[t]||VT.rowsAsked[t])return;
  VT.rowsAsked[t]=1;
  need(`votes/${encodeURIComponent(t)}.json`).then(j=>{
    VT.rows[t]=(j.rolls||[]).map(r=>{r.t=t;return r;});
    votesDraw();
  }).catch(e=>{VT.rows[t]=[];VT.err=e.message||String(e);votesDraw();});
}
function votesNeedBallots(t){
  if(VT.bal[t]||VT.balAsked[t])return;
  VT.balAsked[t]=1;
  need(`votes/ballots-${encodeURIComponent(t)}.json`).then(j=>{VT.bal[t]=j;votesDraw();})
    .catch(e=>{VT.bal[t]={chambers:{}};VT.err=e.message||String(e);votesDraw();});
}
// WHEN THE MEMBERS ARRIVE (the review of 14 November 2026): a name half typed
// in the Member box keeps its letters, its place and its suggestions, and the
// Filter button keeps its state (votesFacets); a member the address names
// and the lists do not is no filter, as a term or a kind it does not know is
// none, where the page hung on "Reading the votes"; and a term the reader
// has not picked moves to the member's votes (votesTermDefault).
function votesNeedPeople(){
  if(VT.peopleAsked)return;
  VT.peopleAsked=true;
  Promise.all([need("legislators.json").catch(()=>[]),need("former.json").catch(()=>[])]).then(([a,b])=>{
    const norm=s=>String(s||"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\s+/g," ").trim();
    VT.people=[].concat(a||[],b||[]).filter(m=>m&&m.slug).map(m=>({
      m,slug:m.slug,ids:(m.member_ids&&m.member_ids.length?m.member_ids:[m.id]).map(String),
      terms:m.served&&Array.isArray(m.served.terms)?m.served.terms.map(String):null,
      hay:norm([m.display_plain,m.name,m.district_label].join(" ")),former:!!m.former}));
    const st=VT.st;
    if(st&&VT.idx){
      if(st.member&&!votesPerson(st.member))st.member="";
      votesRetime(st,VT.idx.terms);
      votesAddress();
    }
    votesControls();votesDraw();
  });
}
const votesPerson=slug=>(VT.people||[]).find(p=>p.slug===slug)||null;

// A term's bill index, asked for ONCE however many times the list is drawn
// while it is on its way (each drawing would otherwise add a draw to the
// answer, and they multiply); and a term whose index cannot be had is not
// waited for, so the rows show with the bill's number alone.
const VT_ENS={};
const votesWants=t=>published(t)&&!LOADED.has(t)&&VT_ENS[t]!=="failed";
function votesEnsure(t){
  if(VT_ENS[t])return;
  VT_ENS[t]="asked";
  ensureTerm(t).then(()=>votesDraw(),()=>{VT_ENS[t]="failed";votesDraw();});
}

// ---- the controls across the top, written by the page (build_votes_page.py)
// An option as the bill search's pickers draw one: its words, and `short`,
// the words a phone shows (votesFit), where it has them.
function votesOptions(list,cur){
  return list.map(([v,w,short])=>`<option value="${esc(v)}"${short?` data-short="${esc(short)}"`:""}${
    v===cur?" selected":""}>${esc(w)}</option>`).join("");
}
// THE TOP OF THE PAGE AS THE BILL SEARCH'S (the owner, 24 November 2026): the
// term picker beside the box, and under them the Sort and the count beside
// it, as bills.html writes them; build_votes_page.py writes them into the
// page and this fills them once the terms are known. The box is the page's
// and is never written again, so what is typed in it, its focus and its caret
// stay; its words are the state's wherever it does not have the keyboard (a
// "Did you mean", Clear, Back). The terms as the bill search's picker words
// them, All Terms and "2025–2026 Term".
function votesControls(){
  const st=VT.st;
  if(!VT.idx||!st)return;
  const terms=VT.idx.terms;
  const ts=document.getElementById("vterm"),so=document.getElementById("vsort");
  if(ts){
    if(!VT.termsDrawn){
      ts.innerHTML=votesOptions([["all","All Terms"]].concat(terms.map(t=>[t,`${termDash(t)} Term`,termDash(t)])),st.term);
      VT.termsDrawn=true;
    }
    ts.value=st.term;
  }
  if(so){
    if(!VT.sortsDrawn){so.innerHTML=votesOptions(VOTES_SORT_WORDS,"");VT.sortsDrawn=true;}
    so.value=st.sort||votesSortDefault(st);
  }
  for(const id of ["vq","vgo"]){const n=document.getElementById(id);if(n)n.disabled=false;}
  const q=document.getElementById("vq");
  if(q&&document.activeElement!==q)q.value=st.q;
  const c=document.getElementById("vclose");
  if(c){c.textContent=votesCloseWords();c.hidden=!st.margin.includes("close");}
  votesFit();
  votesBadge();
}
// THE PICKERS ON A PHONE, AS THE BILL SEARCH'S ARE (fitPickers, Alice, 8
// November 2026): at a phone's width an option with shorter words shows them,
// "2025–2026" for "2025–2026 Term", in the half of the row each picker has;
// an option is replaced, not its words, and the value chosen kept. And the
// term picker is met in the order it is drawn: after the box on a phone,
// where it stands under it, before the box's label on a wider screen, where
// it stands to its left.
function votesFit(){
  const narrow=!!(PHONE_ROW&&PHONE_ROW.matches);
  for(const s of [document.getElementById("vterm"),document.getElementById("vsort")]){
    if(!s||!s.options)continue;
    const was=s.value;
    for(const o of [...s.options]){
      const short=o.getAttribute("data-short");
      if(!short)continue;
      if(o.getAttribute("data-long")===null)o.setAttribute("data-long",o.textContent);
      const want=narrow?short:o.getAttribute("data-long");
      if(o.textContent===want)continue;
      const n=o.cloneNode(false);
      n.textContent=want;
      s.replaceChild(n,o);
    }
    if(s.value!==was)s.value=was;
  }
  const y=document.getElementById("vterm"),qb=document.querySelector("#vform .qbox");
  if(y&&qb&&y.parentNode&&y.parentNode===qb.parentNode&&typeof qb.compareDocumentPosition==="function"){
    const lab=document.querySelector('label[for="vterm"]'),after=!!(qb.compareDocumentPosition(y)&4);
    if(narrow!==after){
      const ref=narrow?qb.nextSibling:(document.querySelector('label[for="vq"]')||qb);
      if(lab)qb.parentNode.insertBefore(lab,ref);
      qb.parentNode.insertBefore(y,ref);
    }
  }
}
// "The House, February 24, 2021": a session day as the page's filter names it.
function votesDayWords(st){
  const b=votesOneBody(st);
  const ch=b==="H"?"The House":b==="S"?"The Senate":"The House and the Senate";
  return `${ch}, ${dateWords(st.day,"full")}`;
}
// THE COUNT HAS TO BE VISIBLE WITH THE PANEL SHUT, as the bill search's is
// (facetBadge): the Filter button carries how many filters are set.
function votesBadge(){
  const b=document.querySelector("#vftoggle .badge");
  if(!b||!VT.st)return;
  const n=votesActive(VT.st);
  b.textContent=n?String(n):"";b.hidden=!n;
}
// The address keeps the page: replaced as the reader types, never pushed.
function votesAddress(){
  try{
    const qs=votesAddr(VT.st,VT.idx.terms);
    if(qs!==location.search.replace(/^\?/,""))
      history.replaceState(history.state,"",location.pathname+(qs?"?"+qs:"")+location.hash);
  }catch(_){}
}

// ---- the filters at the side
// THE FILTERS AT THE SIDE, AS THE BILL SEARCH'S AND THE LAWS PAGE'S (the
// owner, 24 November 2026): each filter a group that opens and shuts, drawn by
// the bill search's own pieces (fgroupFrame, fcheck) in its classes, 17rem
// wide as its column is -- Chamber, Dates, Result, Margin, Kind of Question
// and Member, in the order the row of them stood in. A filter that is a set of
// values is its boxes, each with the number it would list for the term shown
// (votesCounts), greyed at none, in a fixed order with its zeros in place, as
// Status keeps its own; the Result's words are the rows' own chips, as the
// Status filter's are. The two dates are one group, with a session day an
// address names and its Clear. The member is a name box and the members it
// finds, as the Sponsor group draws them, and the one chosen as their chip
// with its Clear.
// OPEN AS THE BILL SEARCH'S ARE (openGroups, 12 October 2026: Status alone):
// the first group alone at the start, at every width and inside the phone's
// panel too -- Chamber, short and shown whole, as Status is there -- and the
// rest shut, one tap away; and a group an address sets opens with it, as a
// tag or a party does there, so a filter a link brought is in sight with the
// way to take it off (votesOpenFor).
// DRAWN ONLY WHERE IT CAN BE SEEN, as the bill search's panel is (facetsShut):
// on a narrow screen with the panel shut, the Filter button's count alone.
const votesShut=()=>{const l=document.getElementById("vlay");
  return !!(FACETS_NARROW&&FACETS_NARROW.matches)&&!(l&&l.classList&&l.classList.contains("fopen"));};
function votesOpenFor(st){
  const o=VT.openG||(VT.openG=new Set(["body"]));
  for(const k of Object.keys(VOTES_TICKS))if(st[k].length)o.add(k);
  if(st.from||st.to||st.day)o.add("dates");
  if(st.member)o.add("member");
}
// The Dates group: a session day the address names, as the page's filter
// names it, and From and To, the dates the file gives.
function votesDatesHtml(st){
  const day=st.day?`<div class="vday"><div class="fsubh">Session day</div><span class="vmemchip">${
      esc(votesDayWords(st))} <button type="button" class="link" data-vdayclear="1">Clear</button></span></div>`:"";
  return day+`<label class="vdate"><span class="fsubh">From</span><input class="sbox" type="date" id="vf-from" data-vf="from" value="${esc(st.from)}"></label>
    <label class="vdate"><span class="fsubh">To</span><input class="sbox" type="date" id="vf-to" data-vf="to" value="${esc(st.to)}"></label>`;
}
// The Member group: the member chosen, as their chip, with its Clear; or the
// box, what is typed in it kept (VT.memText), and the members it finds.
function votesMemberHtml(st){
  if(st.member){
    const person=votesPerson(st.member);
    return `<div class="vmemchip">${person?pchip(person.m):esc(st.member)}
      <button type="button" class="link" data-vmemclear="1">Clear</button></div>`;
  }
  const sug=votesSugHtml(VT.memText);
  return `<input class="sbox" id="vmem" autocomplete="off" placeholder="Type a name…" value="${esc(VT.memText)}"
      aria-label="Filter to one member's votes" aria-controls="vsug">
    <ul class="vsug" id="vsug"${sug?"":" hidden"}>${sug}</ul>`;
}
// DRAWN AGAIN WITHOUT LOSING WHAT THE READER HAS IN HAND (the review of 14
// November 2026): the members' lists arrive about a second after the page,
// and the list's files after that, and each drawing of the side keeps what is
// typed in the Member box, the focus and the caret, the box or the group head
// that had the keyboard, and where the panel and each group were scrolled to,
// as renderFacets keeps the bill search's. A drawing that would write what is
// there already writes nothing. `cnt` is votesCounts' answer, or null where
// the list is still waiting for what it needs, and the numbers are blank;
// `present`, the kinds of question the term's roll calls hold.
function votesFacets(cnt,present){
  const fx=document.getElementById("vfacets"),st=VT.st;
  if(!fx||!st||!VT.idx||votesShut())return;
  const W=WORDBOOK.votes||{},open=VT.openG||(VT.openG=new Set(["body"]));
  const ticks=(k,label,vals,words)=>fgroupFrame(k,label,open.has(k),st[k].length,vals.map(v=>{
    const c=cnt?((cnt[k]||{})[v]||0):null,on=st[k].includes(v);
    return fcheck("data-vtick",k,v,on,c===0&&!on,false,words(v),c==null?"":c.toLocaleString());
  }).join(""),true);
  const kinds=present&&present.size?VOTES_KINDS.filter(k=>present.has(k)||st.kind.includes(k)):VOTES_KINDS;
  const result=v=>v==="passed"?chip(W.passed||"Motion Passed","rcres pass"):chip(W.failed||"Motion Failed","rcres fail");
  let h=ticks("body","Chamber",VOTES_BODIES,v=>esc(CHAMBER_SHORT[v]||v))
    +fgroupFrame("dates","Dates",open.has("dates"),[st.from,st.to,st.day].filter(Boolean).length,votesDatesHtml(st),true)
    +ticks("result","Result",VOTES_RESULTS,result)
    +ticks("margin","Margin",VOTES_MARGINS,v=>v==="close"?"Close":"Tied")
    +ticks("kind","Kind of Question",kinds,v=>esc(v))
    +fgroupFrame("member","Member",open.has("member"),st.member?1:0,votesMemberHtml(st),false);
  if(votesActive(st))h+=`<button type="button" class="link vclearall" data-vclearf="1">Clear all filters</button>`;
  if(h===VT.drawn&&fx.innerHTML)return;
  const act=document.activeElement,here=act&&act.id&&fx.contains&&fx.contains(act)?act.id:"";
  const caret=here&&typeof act.selectionStart==="number"?[act.selectionStart,act.selectionEnd]:null;
  const held=here?null:focusKey();
  const keep=fx.scrollTop,inner=[...fx.querySelectorAll(".fbody")].map(e=>e.scrollTop);
  fx.innerHTML=h;VT.drawn=h;
  fx.scrollTop=keep;
  [...fx.querySelectorAll(".fbody")].forEach((e,i)=>{if(inner[i]!==undefined)e.scrollTop=inner[i];});
  if(here){
    const n=document.getElementById(here);
    if(n){
      try{n.focus();}catch(_){}
      if(caret&&n.setSelectionRange)try{n.setSelectionRange(caret[0],caret[1]);}catch(_){}
    }
  }else refocus(held);
}
// The members a name typed finds, eight at most, the sitting before those who
// have left, as the Member box has always listed them; each as the Sponsor
// group draws a member, their chip, and a member who has left named as a
// search result names them, "Former Rep." (spLabel). "No match" where the
// lists are here and none fits; nothing while they are on their way.
function votesSugHtml(text){
  const t=String(text||"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\s+/g," ").trim();
  if(!t||!VT.people)return "";
  const words=t.split(" ");
  const hit=VT.people.filter(p=>words.every(w=>p.hay.includes(w)))
    .sort((a,b)=>(a.former-b.former)||a.hay.localeCompare(b.hay)).slice(0,8);
  if(!hit.length)return `<li class="fnone">No match</li>`;
  return hit.map(p=>{
    const l=String(p.m.display_full||p.m.name||"");
    return `<li><button type="button" data-vpick="${esc(p.slug)}">${
      pchip({party:p.m.party_code||p.m.party,display_full:p.former&&/^(Rep|Sen)\. /.test(l)?"Former "+l:l})}</button></li>`;
  }).join("");
}

// ---- one row, as the member tab draws one (voteRow), and the ring under it
// A bill number as the site writes one, "SB 457" or "SR 1 (2009)", where the
// file has "SB457": for a bill the index does not hold, and for a bill's link
// here (renderVotes).
function votesBillWords(id){return String(id||"").replace(/^([A-Za-z]+)\s*(\d)/,"$1 $2");}
// WHETHER A QUESTION SAYS MORE THAN THE JOURNAL'S WORDS ABOVE IT, on a vote on
// no bill (the review of 14 November 2026): "Affirm The Report" under "Affirm
// the Committee Report (Censure Rep. Spillane)" said it twice. Drawn only
// where it has a word of its own -- a mover, a bill, the business of the day
// -- read as the words of each, their first five letters, the small ones left
// out.
const VOTES_SMALL=new Set("a an and as at by for from in into is of on or the to with".split(" "));
function votesSaysMore(q,w){
  const words=s=>String(s||"").toLowerCase().match(/[a-z0-9]+/g)||[];
  const has=new Set(words(w).map(x=>x.slice(0,5)));
  return words(q).some(x=>x.length>1&&!VOTES_SMALL.has(x)&&!has.has(x.slice(0,5)));
}
function votesRowHtml(r,i,letter){
  const rc=(RCX||{})[r.id]||null,b=r.b?(votesBy(r.t)||new Map()).get(String(r.b).toUpperCase()):null;
  const named=r.mk&&r.mk!=="unnamed";
  const question=named?voteHead(r.mk,r.q,rc&&rc.mf):esc(r.q);
  // ONE SET OF WORDS FOR THE RESULT (the review of 14 November 2026): the
  // Result filter's and every named motion's chip, "Motion Passed" and "Motion
  // Failed", where a motion the record does not name said "Adopted".
  const W=WORDBOOK.votes||{};
  const said=named?voteChip(r.mk,!!r.p,r.b||"",rc&&rc.mf)
    :chip(r.p?(W.passed||"Motion Passed"):(W.failed||"Motion Failed"),"rcres "+(r.p?"pass":"fail"));
  const close=votesClose(r);
  // The date the file gives, leading to the session day that counts the roll
  // call, where that is another (`s`), and to none where no page counts it.
  const day=r.d,sat=votesSitting(r);
  const who=r.b&&b?billMention(b.n||r.b,`bill/${String(b.year)}/${String(r.b).toLowerCase()}`)
    :r.b?esc(votesBillWords(r.b))
    :r.w?nobillWords({k:r.id},{w:r.w})
    :`<span class="none">no bill</span>`;
  // A named motion is asked by its name, as the row draws it, without the gloss.
  const M=W.motions||{},name=named&&CMP.own(M,r.mk)?String(M[r.mk].motion||""):"";
  const ask=!r.b&&r.w&&!votesSaysMore(name||r.q,r.w)?"":`<span class="vq">${question}</span>`;
  const mine=letter?`<td class="v" data-l="Their vote"><span class="vcast v-${
    esc(String(VOTES_BALLOT[letter]||"").slice(0,3).toLowerCase())}">${
    esc(ballotWord(VOTES_BALLOT[letter]||""))}</span></td>`:"";
  return `<tr>
    <td class="d" data-l="Date">${sat?sittingLink(r.c,sat,esc(dateWords(day)),b?r.b:"",r.id):esc(dateWords(day))}<span class="vch">${
      esc(CHAMBER_SHORT[r.c]||r.c)}</span></td>
    <td class="b" data-l="On">${who}${b&&b.title?`<span class="vt" translate="no">${esc(b.title)}</span>`:""}
      ${ask}</td>${mine}
    <td class="o" data-l="Result"><span class="vres"><i class="vtal">${r.y}–${r.n}</i>${said}</span>${close?`<i class="thr">${esc(close)}</i>`:""}${
      rc&&rc.tn?`<i class="thr">${esc(rc.tn)}</i>`:""}${rc&&rc.oc?`<i class="thr">${esc(rc.oc)}</i>`:""}</td></tr>`
    +votesRing(r,i,letter?5:4);
}
function votesRing(r,i,cols){
  const rc=(RCX||{})[r.id];
  if(!rc||rc.y==null||rc.n==null)return "";
  const open=!!VT.open[r.id];
  const b=r.b?(votesBy(r.t)||new Map()).get(String(r.b).toUpperCase()):null;
  const nb=!r.b&&rc.c!=null&&rc.ct?String(rc.ct):"";
  const bkey=r.b&&b?`${b.year}/${String(r.b).toUpperCase()}`:nb?`nobill/${nb}`:"";
  let body="";
  if(open){
    const d=bkey&&rc.c!=null?BILL_RECS[bkey]:null,card=d&&(d.rollcalls||[])[rc.c];
    if(bkey&&rc.c!=null&&!CMP.own(BILL_RECS,bkey))(nb?nobillRecord:billRecord)(bkey,votesDraw);
    body=card&&(card.members||[]).length
      ?donut(nb?`NB-${nb}`:String(r.b).toUpperCase(),rc.c,card)
      :simpleDonut({yeas:r.y,nays:r.n,passed:!!r.p,threshold_needed:rc.nd||null},"vs",i);
    if(b)body+=`<p class="src"><a href="bill/${esc(String(b.year))}/${esc(String(r.b).toLowerCase())}/votes">Every vote on ${
      esc(b.n||r.b)}, on its Votes tab</a></p>`;
  }
  return `<tr class="vring"><td colspan="${cols}"><details data-vring="${esc(r.id)}"${open?" open":""}>
    <summary data-vring-s="${esc(r.id)}">How everyone voted</summary>${open?`<div class="vringbody">${body}</div>`:""}
    </details></td></tr>`;
}

// THE COUNT LINE SAYS WHOSE VOTES AND WHICH DAY (the review of 14 November
// 2026): from a member's page on a phone the member's name was only inside
// the folded Filters, and the count was of the roll calls held, 591, where
// she voted on 397. A member's line counts the roll calls they voted yea or
// nay on, of those the list holds; a session day is named by its chamber
// and day, where the term would otherwise be.
function votesCountWords(n,st,person,voted){
  const ch={H:"the House’s session day",S:"the Senate’s session day"}[votesOneBody(st)]||"the session days";
  const where=st.day?`from ${ch} of ${dateWords(st.day,"full")}`
    :`in ${st.term==="all"?"every term":termDash(st.term)}`;
  const who=person?String(person.m.display_plain||person.m.name||st.member):"";
  const rcs=k=>`${k.toLocaleString()} roll call${k===1?"":"s"}`;
  if(who)return n?`${who} voted yea or nay on ${voted.toLocaleString()} of ${rcs(n)} ${where}`
    :`0 roll calls of ${who} ${where}`;
  return `${n.toLocaleString()} ${n===1?"vote":"votes"} ${where}`;
}
// ---- the page's list: everything asked for, then the filters at the side and the rows
function votesDraw(){
  const box=document.getElementById("vlist"),st=VT.st;
  if(!box||!VT.idx||!st)return;
  const terms=VT.idx.terms,scope=st.term==="all"?terms:[st.term];
  const cnt=document.getElementById("vcount");
  const q=st.q;
  scope.forEach(votesNeedRows);
  const loaded=scope.filter(t=>VT.rows[t]);
  const person=st.member?votesPerson(st.member):null;
  if(st.member){votesNeedPeople();scope.forEach(votesNeedBallots);}
  const ids=person?person.ids:null;
  const balReady=!st.member||(person&&scope.every(t=>VT.bal[t]));
  needRollcalls();
  // The search: a bill number is a number; anything else is words, read
  // against the bills of the terms in scope and their text.
  const num=q?billNumbers(q):null;
  let gs=null;
  const need_=[];
  if(q&&!num){
    scope.forEach(t=>{if(votesWants(t))need_.push(t);});
    need_.forEach(votesEnsure);
    wantText(scope,votesDraw);
    gs=voteGroups(q,IDX.filter(b=>scope.includes(b.term)));
  }
  const reading=loaded.length<scope.length||!balReady||need_.length||(q&&!num&&textState(scope)==="loading");
  const pool=[];
  loaded.forEach(t=>VT.rows[t].forEach(r=>pool.push(r)));
  // The rows the words find; the list is those the filters pass, and the
  // filters at the side count those the others pass.
  const held=reading&&(!balReady||need_.length);
  const hit=held?[]:votesSearched(pool,st,gs,num);
  let rows=held?[]:votesSorted(hit.filter(r=>votesPass(r,st,ids)),st,gs);
  VT.present=new Set(pool.map(r=>r.k));
  VT.cnt=held||votesShut()?null:votesCounts(hit,st,ids);
  votesFacets(VT.cnt,VT.present);
  const cap=(st.show||0)+VOTES_SHOW,shown=rows.slice(0,cap);
  // Each shown row's bill is named by its term's index: asked for, and the
  // rows drawn when it is here, so that a number is never drawn bare and then
  // changed.
  const unread=[...new Set(shown.filter(r=>r.b).map(r=>r.t))].filter(votesWants);
  unread.forEach(votesEnsure);
  const waiting=reading||unread.length;
  const where=st.term==="all"?"every term":termDash(st.term);
  if(cnt){
    const voted=ids?rows.filter(r=>{const l=votesLetter(r,ids);return l==="Y"||l==="N";}).length:0;
    cnt.textContent=waiting&&!shown.length?"Reading the votes…"
      :votesCountWords(rows.length,st,person,voted)+(waiting?", reading the rest…":"");
  }
  const clear=`<button type="button" class="link" data-vclear="1">Clear the search and filters</button>`;
  if(VT.err&&!pool.length){
    box.innerHTML=`<p class="note" role="alert">The votes could not be loaded. <code>${esc(VT.err)}</code></p>`;return;
  }
  if(waiting&&!shown.length){box.innerHTML="";return;}
  if(!rows.length){
    let did="";
    if(q&&!num&&gs){
      const sp=spelling(gs,IDX.filter(b=>scope.includes(b.term)));
      if(sp&&sp.need)votesWords();
      else if(sp)did=` Did you mean <button type="button" class="link" data-vq="${esc(sp.q)}">${esc(sp.q)}</button>?`;
    }
    box.innerHTML=`<p class="note" role="status">No recorded vote matches${q?` &ldquo;${esc(q)}&rdquo;`:""}
      in ${esc(where)}.${did} ${clear}.</p>`;
    return;
  }
  const withMember=!!ids;
  const left=rows.length-shown.length;
  box.innerHTML=`<table class="votes vfull${withMember?"":" vthree"}"><thead><tr><th>Date</th>
      <th>The bill and the question</th>${withMember?"<th>Their vote</th>":""}<th>Result</th>
      </tr></thead><tbody>${shown.map((r,i)=>votesRowHtml(r,i,withMember?votesLetter(r,ids):""))
        .join("")}</tbody></table>${left?`<p class="src"><button type="button" class="link" data-vmore="1">Show ${
      Math.min(VOTES_SHOW,left).toLocaleString()} more</button> &mdash; ${left.toLocaleString()} of ${
      rows.length.toLocaleString()} not yet shown.</p>`:""}`;
}
// Every word any bill has used, for "Did you mean" (the bill search's, once).
function votesWords(){
  if(VT.words)return;
  VT.words="loading";
  need("sidx/words.json").then(j=>{VT.words=wordsAdd(j)?"ready":"failed";})
    .catch(()=>{VT.words="failed";}).then(()=>{if(VT.words==="ready")votesDraw();});
}

// ---- the page's controls at work
// A term picked is the reader's; dates picked, or a session day or a member,
// move a term the reader has not picked to theirs (votesRetime), and dates
// picked replace a session day (the review of 14 November 2026: dates in
// 2003 or a former member showed "0 votes in 2025–2026"). The Sort is a
// control like the rest.
function votesChange(k,v){
  const st=VT.st;
  st[k]=v;st.show=0;
  if(k==="term")st.tauto=false;
  if(k==="from"||k==="to"){
    const had=!!st.day;
    st.day="";st.tauto=true;votesRetime(st,VT.idx.terms);
    if(had){votesControls();votesAddress();votesBadge();votesDraw();return;}
    votesTermShown();
  }
  votesAfter();
}
// A box ticked or unticked: its group's values, in the group's own order.
function votesTick(k,v,on){
  const st=VT.st;
  if(!VOTES_TICKS[k])return;
  st[k]=VOTES_TICKS[k].filter(x=>x===v?on:st[k].includes(x));st.show=0;
  votesAfter();
}
// The member chosen or cleared, from a click: the term follows them.
function votesMember(slug){
  const st=VT.st;
  st.member=slug;st.show=0;st.tauto=true;
  if(slug)VT.memText="";
  votesRetime(st,VT.idx.terms);
  votesControls();votesAfter();
}
// Clear all filters, as the bill search's does: every group's, the words, the
// term picked and the order kept; a term the reader has not picked follows.
function votesClearFilters(){
  const st=VT.st;
  for(const k of Object.keys(VOTES_TICKS))st[k]=[];
  st.from="";st.to="";st.day="";st.member="";st.show=0;VT.memText="";
  votesRetime(st,VT.idx.terms);
  votesControls();votesAfter();
}
// The Term select shows the term the dates moved it to.
function votesTermShown(){
  const sel=document.getElementById("vterm");
  if(sel&&VT.st)sel.value=VT.st.term;
}
// After a change: the close-vote line where Margin asks for close votes, the
// Sort's own order where the reader has picked none (a search is best match),
// the address, the Filter button's count and the list.
function votesAfter(){
  const st=VT.st,c=document.getElementById("vclose"),so=document.getElementById("vsort");
  if(c)c.hidden=!st.margin.includes("close");
  if(so&&document.activeElement!==so)so.value=st.sort||votesSortDefault(st);
  votesAddress();votesBadge();votesDraw();
}
function votesSuggest(text){
  VT.memText=String(text||"");
  const ul=document.getElementById("vsug");
  if(!ul)return;
  const h=votesSugHtml(VT.memText);
  ul.innerHTML=h;ul.hidden=!h;
}
document.addEventListener("input",e=>{
  if(!window.GR_VOTES||!VT.st)return;
  const t=e.target;
  if(t.id==="vq"){
    clearTimeout(VT.typing);
    VT.typing=setTimeout(()=>{VT.st.q=t.value.trim();VT.st.show=0;votesAfter();},160);
  }else if(t.id==="vmem"){votesNeedPeople();votesSuggest(t.value);}
});
document.addEventListener("change",e=>{
  if(!window.GR_VOTES||!VT.st)return;
  const t=e.target,d=t.dataset||{};
  if(d.vtick){votesTick(d.vtick,t.value,!!t.checked);return;}
  if(d.vf)votesChange(d.vf,t.value);
});
// RETURN, OR THE BOX'S OWN KEY, as the bill search's: the words now, without
// the pause the typing waits for, and the keyboard let go of.
document.addEventListener("submit",e=>{
  if(!window.GR_VOTES||!e.target||e.target.id!=="vform")return;
  e.preventDefault();
  const q=document.getElementById("vq");
  if(!q||!VT.st)return;
  clearTimeout(VT.typing);
  VT.st.q=q.value.trim();VT.st.show=0;votesAfter();
  if(q.blur)q.blur();
});
document.addEventListener("click",e=>{
  if(!window.GR_VOTES||!VT.st||!e.target.closest)return;
  const c=s=>e.target.closest(s);
  if(c("[data-vmore]")){VT.st.show=(VT.st.show||0)+VOTES_SHOW;votesDraw();return;}
  if(c("[data-vclear]")){
    const m=document.getElementById("vmem");
    if(m)m.value="";
    VT.memText="";
    VT.st=votesDefault(VT.idx.terms);votesControls();votesAfter();return;}
  if(c("[data-vclearf]")){votesClearFilters();return;}
  const vq=c("[data-vq]");
  if(vq){VT.st.q=vq.getAttribute("data-vq");VT.st.show=0;votesControls();votesAfter();return;}
  const pick=c("[data-vpick]");
  if(pick){votesMember(pick.getAttribute("data-vpick"));return;}
  if(c("[data-vmemclear]")){votesMember("");return;}
  if(c("[data-vdayclear]")){
    VT.st.day="";VT.st.show=0;VT.st.tauto=true;votesRetime(VT.st,VT.idx.terms);
    votesControls();votesAfter();return;}
  // A group's head opens or shuts it, and the side is drawn again as it was.
  const g=c("#vfacets .fhead");
  if(g){
    const k=g.getAttribute("data-g"),o=VT.openG||(VT.openG=new Set(["body"]));
    o.has(k)?o.delete(k):o.add(k);
    votesFacets(VT.cnt,VT.present);return;}
  // THE FILTER BUTTON, as the bill search's (#ftoggle): the class on the frame
  // round the button, the groups and the list, which the stylesheet moves,
  // and the groups drawn as they open.
  const ftb=c("#vftoggle");
  if(ftb){
    const l=document.getElementById("vlay");
    if(!l)return;
    const open=l.classList.toggle("fopen");
    ftb.setAttribute("aria-expanded",open?"true":"false");
    if(open)votesDraw();
  }
});
// ESCAPE SHUTS THE PANEL, from inside it or from its button, and leaves the
// keyboard on the button, as the bill search's does.
document.addEventListener("keydown",e=>{
  if(window.GR_VOTES&&e.key==="Escape"&&e.target.closest&&e.target.closest("#vfacets,#vftoggle")){
    const l=document.getElementById("vlay"),b=document.getElementById("vftoggle");
    if(l&&b&&l.classList.contains("fopen")){l.classList.remove("fopen");b.setAttribute("aria-expanded","false");b.focus();}
  }
});
// A ring opened or shut stays so through the list's next drawing.
document.addEventListener("toggle",e=>{
  const d=e.target;
  if(!window.GR_VOTES||!d||!d.matches||!d.matches("details[data-vring]"))return;
  const k=d.getAttribute("data-vring");
  if(!!VT.open[k]===d.open)return;
  if(d.open)VT.open[k]=true;else delete VT.open[k];
  if(d.open)votesDraw();
},true);
window.addEventListener("popstate",()=>{
  if(!window.GR_VOTES||!VT.idx)return;
  VT.st=votesRead(location.search,VT.idx.terms);votesOpenFor(VT.st);votesControls();votesDraw();
});
// A phone turned, or a window narrowed or widened: the pickers' words and
// order, and the side drawn where it has come into sight.
if(PHONE_ROW&&PHONE_ROW.addEventListener)PHONE_ROW.addEventListener("change",()=>{if(window.GR_VOTES)votesFit();});
if(FACETS_NARROW&&FACETS_NARROW.addEventListener)
  FACETS_NARROW.addEventListener("change",()=>{if(window.GR_VOTES&&VT.st&&!votesShut())votesDraw();});

function votesInit(){
  const root=document.getElementById("vpage"),box=document.getElementById("vlist");
  if(!root||!box)return;
  Promise.all([need("meta.json").then(m=>{META=m;}).catch(()=>{}),need("votes/index.json")])
    .then(([,idx])=>{
      if(!idx||!Array.isArray(idx.terms)||!idx.terms.length)throw new Error("votes/index.json names no term");
      VT.idx=idx;
      VT.st=votesRead(location.search,idx.terms);
      votesOpenFor(VT.st);
      if(VT.st.member)votesNeedPeople();
      votesControls();votesDraw();
    })
    .catch(e=>{
      const c=document.getElementById("vcount");
      if(c)c.textContent="";
      box.innerHTML=`<p class="note" role="alert">The votes could not be loaded. <code>${esc(e.message||String(e))}</code></p>`;
    });
}
if(window.GR_VOTES)votesInit();
