// GRANITE_VERSION: 2026-09-07.58
// What each kind of document actually is, said once rather than in every row.
const DOCWHAT={text:"the bill as it currently stands",
  status:"the page this site takes a bill's status from",
  docket:"every recorded action, in the General Court's own words",
  record:"the official record of one action",
  report:"the calendar a committee report was printed in"};
const PARTY_NAME={R:"Republican",D:"Democrat",I:"Independent",L:"Libertarian",
  X:"Party not on file"};
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
const KIND={active:"s-active",law:"s-law",done:"s-done",veto:"s-veto",
            study:"s-study",adopted:"s-adopted"};
// "Became law" is wrong for a resolution: an adopted House Resolution is
// finished and successful and is not law. It needed its own word.
const KINDL={active:"In progress",law:"Became law",done:"Killed",
             veto:"Vetoed",study:"Interim study",adopted:"Adopted"};
const OTHER=[["Presiding","Presiding",
  "One member presides over each roll call and does not vote except to break a tie. This is the role, not a missed vote."],
 ["Not Voting/Excused","Excused absence",
  "Excused in advance for the whole day — illness, a death in the family, or other significant obligation."],
 ["Not Voting/Not Excused","Absent, not excused",
  "Either left the chamber rather than vote on this question, or was away for the day without arranging an excuse."]];

const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* Bills are drafted in statutory vocabulary; people search in ordinary words.
   "AN ACT relative to the state minimum hourly rate" will never be found by
   someone typing "minimum wage". These are GROUPS rather than mappings: every
   term in a group matches every other, so nothing is declared the real name for
   anything else. That matters on contested subjects, where deciding that one
   word "means" another is a framing choice rather than a translation. Matching
   is by substring, so a singular form also catches its plural. */
const SYN=[
  ["gun","firearm","weapon","pistol","rifle"],
  ["school","education","student","teacher","classroom"],
  ["tax","taxation","revenue","levy"],
  ["housing","zoning","dwelling","rent","landlord","tenant"],
  ["childcare","child care","daycare","day care"],
  ["marijuana","cannabis","thc","weed"],
  ["dui","dwi","intoxicated","impaired driving"],
  ["healthcare","health care","health","medical","insurance"],
  ["police","law enforcement","officer","sheriff"],
  ["veteran","military","national guard","armed forces"],
  ["elderly","senior","older adult","aging"],
  ["vote","voting","election","ballot","absentee","voter"],
  ["internet","broadband","telecommunication"],
  ["road","highway","transportation","bridge"],
  ["climate","emission","greenhouse","renewable","solar"],
  ["trash","landfill","solid waste","recycling"],
  ["opioid","controlled substance","narcotic","drug","fentanyl"],
  ["abortion","reproductive","pregnancy termination"],
  ["transgender","gender identity","gender-affirming"],
  ["immigration","immigrant","noncitizen","alien"],
  ["minimum wage","hourly rate","wage"],
  ["union","collective bargaining","labor"],
  ["water","groundwater","pfas","drinking water"],
  ["prison","corrections","inmate","incarcerat"],
  ["court","judicial","judge","judiciary"],
  ["property tax","assessment","abatement"],
  ["energy","electric","utility","ratepayer"],
  ["mental health","behavioral health","psychiatric"],
  ["disability","disabled","accessib"],
  ["farm","agriculture","livestock","dairy"],
];
const SYNMAP={};
SYN.forEach(g=>g.forEach(t=>{SYNMAP[t]=g;}));
// Match at a word boundary, not anywhere in the string. Plain substring search
// makes "gun" hit "begun" and "act" hit "enacted". Matching at the START of a
// word still catches plurals and endings, so "firearm" finds "firearms" and
// "incarcerat" finds "incarcerated".
const RXC={};
function hasTerm(hay, term){
  if(term.includes(" ")) return hay.includes(term);
  let rx=RXC[term];
  if(!rx){ rx=new RegExp("\\b"+term.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
           RXC[term]=rx; }
  return rx.test(hay);
}

function expand(word){
  // The original word is ALWAYS kept. Dropping it silently narrows the search:
  // "care" is a prefix of "child care", so without this a search for "care"
  // would match childcare bills and stop matching "health care" — worse than
  // having no synonyms at all.
  //
  // Partial matches need at least four characters, so "gun" does not fire on
  // "begun" and short words do not drag in whole groups.
  let best=null;
  for(const t in SYNMAP){
    // Prefix match, not "contains anywhere". "guns" should reach the firearm
    // group; "begun" should not, and it does under a contains test.
    const hit = word===t ||
      (word.length>=4 && (word.startsWith(t)||t.startsWith(word)));
    if(hit && (!best||t.length>best.length)) best=t;
  }
  return best ? [...new Set([word, ...SYNMAP[best]])] : [word];
}
const fdate=d=>{if(!d)return"";const[y,m,dd]=d.split("-");
  return new Date(y,m-1,dd).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});};
const $=s=>document.querySelector(s);

let IDX=[],META={},term=null,query="",sortBy="num";
// A bill number is unique within a two-year term and not beyond it, so
// every address for one carries its filing year: the static page has done
// so from the start, and the detail file and this view do now.
// WITHIN THE SELECTED TERM. HB1 exists in every biennium, and finding the
// first row with that number across the whole index served the 2025 bill's
// history under the 2023 bill's heading -- the card said "filed 2023" and the
// body said "introduced on February 20, 2025".
const yearOf=id=>{const b=IDX.find(x=>x.id===id&&(!term||x.term===term))
                       ||IDX.find(x=>x.id===id);
  return b&&b.year?String(b.year):"";};
// The detail cache is keyed the same way, or switching terms hands back the
// bill of the same number that was looked at first.
const dkey=id=>`${yearOf(id)}/${id}`;

// House bills before Senate bills, then numerically. Bill numbers are strings
// like "HB 1442", so a plain string sort puts HB 1000 before HB 99 and mixes
// the chambers together.
const KINDORDER={HB:0,HR:1,HCR:2,CACR:3,SB:4,SR:5,SCR:6,HJR:7,SJR:8};
function billKey(b){
  const m=/^([A-Z]+)\s*(\d+)/.exec(b.id.toUpperCase())||[];
  return [KINDORDER[m[1]] ?? 99, parseInt(m[2]||"0",10)];
}
// A bill has one status and one subject, but it can pass through two
// committees, so a facet value is a list. Sorting the list alphabetically also
// groups it: every House committee, then every Senate one.
function facetVals(b,k){
  if(k==="kind")return [b.kind];
  if(k==="committee")return b.committees||(b.committee?[b.committee]:[]);
  return [b[k]];
}

function sortRows(rows){
  const by={
    num:(a,b)=>{const x=billKey(a),y=billKey(b);
                return x[0]-y[0] || x[1]-y[1];},
    recent:(a,b)=>(b.last_action||"").localeCompare(a.last_action||"")
                  || billKey(a)[1]-billKey(b)[1],
    // Bills still moving come first, because those are the ones a reader can
    // still do something about -- turn up, sign in, write to the committee.
    // After that the outcomes group together and run alphabetically inside
    // each group. That is a filing order, not a ranking: a bill dying is an
    // outcome, not a failure, and nothing here puts one outcome above another.
    status:(a,b)=>((a.kind==="active"?0:1)-(b.kind==="active"?0:1))
                  || (a.kind||"").localeCompare(b.kind||"")
                  || (a.status||"").localeCompare(b.status||"")
                  || billKey(a)[1]-billKey(b)[1],
  }[sortBy]||(()=>0);
  return rows.slice().sort(by);
}
const sel={committee:new Set(),topic:new Set(),sponsor:new Set(),kind:new Set(),
           voteday:new Set()};
// On a phone the filter column stacks ABOVE the results, and an open
// Committee group is 340 pixels of it -- so the first bill sat past a
// screen and a half of filters on a 375-wide screen. Someone arriving on
// a phone came for the bills; the filters are one tap away either way.
// 861px, which is where .shell actually becomes two columns. It was 721,
// so between those two widths the panel stacked ABOVE the results with its
// longest group open -- fourteen committees before the first bill.
const wideEnough=typeof matchMedia==="function"
  && matchMedia("(min-width:861px)").matches;
const openGroups=new Set(wideEnough?["committee"]:[]);
let sponsorFilter="";
const openCards=new Set(),openTab={},detail={},segSel={},fullOpen=new Set();

// A BILL NUMBER IS NOT UNIQUE ACROSS TERMS, and four of those five are keyed
// on the bare number. HB 100 exists in most terms and is a different bill in
// each, so expanding a few rows and then changing the term left those same
// numbers expanded -- showing the NEW term's bills opened, on the strength of
// what a reader had opened in the old one, with whichever tab the old bill had
// been left on.
//
// detail is the exception and needs no clearing: dkey() keys it on
// `${yearOf(id)}/${id}`, so the cache is already per term and keeping it means
// switching back does not refetch.
//
// This is the same confusion build_data.py guards against on the data side --
// "HB100 of 2023 and HB100 of 2025 have different sponsors, and a flat file
// gives the second to the first without saying so" -- arriving in the browser
// as view state rather than as data.
function forgetCardState(){
  openCards.clear();
  fullOpen.clear();
  for (const k of Object.keys(openTab)) delete openTab[k];
  for (const k of Object.keys(segSel)) delete segSel[k];
}
// Which bill is filling the screen, and where the reader was standing when
// they opened it.
let focused=null,focusY=0;
// Bills whose procedural lines the reader has chosen to see.
const showRoutine=new Set();

// Report which file failed and why. The old handler blamed file:// for every
// failure, including a missing or malformed JSON file, which sent people
// looking in entirely the wrong place.
// Anchored to the site root, not to the page.
//
// The same page is served at /bills and /bills.html, and a bills/ folder of
// per-bill data sits alongside it -- so a request for /bills can be redirected
// to /bills/, and a relative "bills/HB1123.json" then resolves to
// /bills/bills/HB1123.json. That is why refreshing while looking at a bill
// gave "Detail unavailable" while the same file loaded from the search page.
const DATA=(f)=>new URL(f, location.origin + "/").href;
// The site's root, so a pushed address is absolute rather than relative to
// whatever folder the current page happens to sit in -- /bill/2026/ is three
// deep and a relative push from there lands in /bill/2026/bill/2026/.
const BASE="/";
const need=(f)=>fetch(DATA(f)).then(r=>{
  if(!r.ok)throw new Error(`${f} returned ${r.status} ${r.statusText}`);
  return r.json().catch(()=>{throw new Error(`${f} is not valid JSON`);});
});
// A record's own page is served at both /bill/2026/hb1123.html and
// /bill/2026/hb1123. Show the second, so the address bar matches what the
// site links and what a reader would paste. Same document either way, so this
// replaces rather than pushes.
if(/^\/(?:bill|legislator|committee)\/.+\.html$/.test(location.pathname)){
  try{history.replaceState(history.state,"",
    location.pathname.slice(0,-5)+location.search+location.hash);}catch(_){}
}
// WHICH TERM TO LOAD FIRST. A record page names it in its own address --
// /bill/2026/hb1442 -- so a 1995 bill loads the 1995 index and not the
// current one. Anything else starts at the newest, which is what the picker
// opens on.
function wantedTerm(m){
  const terms=(m.terms&&m.terms.length)?m.terms:[];
  const mm=location.pathname.match(/^\/bill\/(\d{4})\//);
  if(mm){
    const y=+mm[1], t=terms.find(x=>{const a=+String(x).slice(0,4);return y===a||y===a+1;});
    if(t)return t;
  }
  return terms[0]||"";
}
// A term already in IDX is never fetched again.
const LOADED=new Set();
function ensureTerm(t){
  if(!t||LOADED.has(t))return Promise.resolve();
  return need("idx/"+encodeURIComponent(t)+".json").then(rows=>{
    LOADED.add(t);
    rows.forEach(b=>b.hay=[b.id,b.n,b.title,b.sponsor,
      ...(b.committees||[b.committee||""]),b.topic].join(" ").toLowerCase());
    IDX=IDX.concat(rows);
  });
}

need("meta.json")
 .then(m=>{
   META=m;
   const first=wantedTerm(m);
   return ensureTerm(first).then(()=>[IDX,m]);})
 .then(([i,m])=>{
   IDX=i;META=m;
   // The haystack is built in ensureTerm, once per term as it arrives.
   const terms=META.terms&&META.terms.length?META.terms
     :[...new Set(IDX.map(b=>b.term).filter(Boolean))].sort().reverse();
   term=wantedTerm(META)||terms[0];
   const ys=$("#year");
   ys.innerHTML=terms.map(t=>`<option value="${t}">${t} Term</option>`).join("");
   ys.value=term;
   ys.addEventListener("change",e=>{
     // On a record page there is no list to re-filter, and render() would
     // write one over the record.
     if(PAGE||window.GR_STATIC){location.href="bills.html";return;}
     term=e.target.value;
     forgetCardState();
     // The term's bills may not be here yet. Fetch, then draw -- and say so
     // meanwhile, because a picker that does nothing for a moment reads as
     // broken.
     const c=$("#count"); if(c&&!LOADED.has(term))c.textContent="loading "+term+"…";
     ensureTerm(term).then(render);});
   const so=$("#sort");
   if(so)so.addEventListener("change",e=>{
     if(PAGE||window.GR_STATIC)return;
     sortBy=e.target.value;render();});
   $("#q").disabled=false;
   // The button next to it does the same job on the focused view, so it waits
   // for the same data.
   $("#qgo").disabled=false;
   // Arriving from the home page search box, with the query in the URL.
   const pre=new URLSearchParams(location.search).get("q");
   if(pre){ $("#q").value=pre; query=pre; }
   // WHAT THIS PAGE IS, decided before anything is drawn.
   //
   // These three used to sit after render(), which meant a member's page
   // built the whole 2,234-bill list into #results and then threw it away --
   // 300KB of DOM nobody saw -- and the committees index, whose listing is
   // already in the HTML it was served, had that listing replaced by the bill
   // search and showed nothing at all.
   //
   // Focus is not taken either: a reader who opened a member's page did not
   // ask to be put in the search box.
   if(window.GR_STATIC){
     // The content is in the HTML. Take the chrome down and leave it alone.
     const fac=$("#facets"); if(fac){fac.innerHTML="";fac.hidden=true;}
     const sh=document.querySelector(".shell"); if(sh)sh.classList.add("nofacets");
     const c=$("#count"); if(c)c.textContent="";
     hideListControls();
     return;
   }
   // A bill's own page is one bill, so the controls that filter and sort a
   // LIST have nothing to act on. They were left up, with the count reading
   // "2,234 of 2,234 bills in the 2025-2026 term" above a single bill --
   // which at 360px was the whole first screen.
   if(window.GR_BILL)hideListControls();
   if(window.GR_MEMBER){openPage("member",String(window.GR_MEMBER));return;}
   if(window.GR_COMMITTEE){openPage("committee",String(window.GR_COMMITTEE));return;}
   $("#q").focus();
   render();
   // A bare #HB1442 link from elsewhere opens that bill.
   // Arriving with a bill in the address -- a refresh, a shared link, or the
   // "open it in the searchable view" link on a static page -- opens it the
   // way clicking the arrow would have, rather than merely expanding the card
   // somewhere down a list of two thousand.
   // "#2026/HB1442", and still the bare "#HB1442" that links already in
   // circulation use. The year is what tells two terms' HB1442 apart;
   // without it the first match in the index wins, which is only safe
   // while one term is loaded.
   // A bill's own page at /bill/2026/hb1094 is this same app with one bill
   // open, rather than a second renderer drawing the same JSON in Python. It
   // says which bill in GR_BILL, because it cannot say it in the hash without
   // putting the bill number twice in an address that already names it.
   // A legislator's or a committee's page is this same app with one record
   // open, so it takes over here rather than drawing the bill list first and
   // replacing it. The index is still loaded: a vote names a bill and not its
   // year, and yearOf needs the index to turn one into a link.
   const h=decodeURIComponent(location.hash.slice(1))||(window.GR_BILL||"");
   const hm=/^(?:(\d{4})\/)?([A-Z]{2,5}\d+)$/i.exec(h);
   if(hm){
     const id=hm[2].toUpperCase(),hy=hm[1]||"";
     const row=IDX.find(b=>b.id===id&&(!hy||String(b.year)===hy));
     if(row){
       focused=id;
       // A link into another term must switch the term first, or the
       // card it names is filtered out of the list it would be drawn in.
       if(row.term&&term&&row.term!==term){term=row.term;$("#year").value=term;}
     }
     openBill(id);
   }
 }).catch(e=>{
   $("#results").innerHTML=`<div class="empty"><b>Could not load the data.</b><br><br>
     <code>${esc(e.message||e)}</code><br><br>
     If that mentions a status code, the file is missing from this folder — run
     <code>build_site_v2.py</code>. If it mentions CORS or the scheme, the page was
     opened from disk rather than served: <code>cd site</code> then
     <code>python3 -m http.server 8000</code>.</div>`;
 });

function billNumbers(q){
  const parts=q.split(",").map(s=>s.trim()).filter(Boolean);
  if(!parts.length)return null;
  const ids=parts.map(p=>p.replace(/\s+/g,"").toUpperCase());
  return ids.every(i=>/^[A-Z]{2,5}\d+$/.test(i))?ids:null;
}
function matches(b,ignore){
  // A bill number is unique WITHIN a term, so a number search ignores the
  // sidebar filters -- they can only hide the answer. It stays inside the
  // selected term though: once earlier terms are backfilled there really is an
  // HB 84 in each of them, and returning four unrelated bills is its own kind
  // of unhelpful. When nothing matches in this term, the page says whether the
  // number exists in another rather than just showing nothing.
  const ids=billNumbers(query);
  if(ids)return ids.includes(b.id.toUpperCase())&&(!b.term||!term||b.term===term);

  if(b.term&&term&&b.term!==term)return false;
  for(const k of["committee","topic","sponsor","kind"])
    if(k!==ignore&&sel[k].size&&!facetVals(b,k).some(v=>sel[k].has(v)))return false;
  if(ignore!=="voteday"&&sel.voteday.size&&!(b.votedays||[]).some(d=>sel.voteday.has(d)))return false;
  const q=query.trim().toLowerCase(); if(!q)return true;
  // Every word must match, but any of its synonyms will do.
  return q.replace(/,/g," ").split(/\s+/).filter(Boolean)
    .every(w=>expand(w).some(alt=>hasTerm(b.hay, alt)));
}

function fgroup(key,label,vals,counts,searchable){
  const chosen=sel[key],open=openGroups.has(key);
  let inner="";
  if(searchable){
    const f=sponsorFilter.toLowerCase();
    const shown=f?vals.filter(v=>v.toLowerCase().includes(f)).slice(0,15):[];
    inner=`${[...chosen].map(v=>`<span class="pill">${esc(v)}<button data-unpick="${esc(v)}">×</button></span>`).join("")
      ?`<div class="chosen">${[...chosen].map(v=>`<span class="pill">${esc(v)}<button data-unpick="${esc(v)}">×</button></span>`).join("")}</div>`:""}
      <input class="sbox" id="sbox" aria-label="Find a prime sponsor by name" placeholder="Type a name…" value="${esc(sponsorFilter)}" autocomplete="off">`
      +(shown.map(v=>`<label class="fopt ${!counts[v]?'off':''}"><input type="checkbox" data-f="${key}"
        value="${esc(v)}" ${chosen.has(v)?"checked":""}><span>${esc(v)}</span>
        <span class="c">${counts[v]||0}</span></label>`).join("")
        ||(sponsorFilter?`<p style="font-size:12.5px;color:var(--ink-2)">No match</p>`:""));
  }else{
    inner=vals.map(v=>`<label class="fopt ${!counts[v]&&!chosen.has(v)?'off':''}">
      <input type="checkbox" data-f="${key}" value="${esc(v)}" ${chosen.has(v)?"checked":""}>
      <span>${key==="kind"?`<span class="cstat ${KIND[v]}" style="padding:1px 8px">${KINDL[v]}</span>`:esc(v)}</span>
      <span class="c">${counts[v]||0}</span></label>`).join("");
  }
  return `<div class="fgroup ${open?'open':''}"><button class="fhead" data-g="${key}"
    aria-expanded="${open}"><span>${label}</span>${chosen.size?`<span class="badge">${chosen.size}</span>`:""}
    <span class="chev">▸</span></button><div class="fbody" ${open?"":"hidden"}>${inner}</div></div>`;
}

function renderFacets(){
  const inYear=IDX.filter(b=>!term||!b.term||b.term===term);
  const cnt=(k,ig)=>{const c={};inYear.filter(b=>matches(b,ig)).forEach(b=>{
    facetVals(b,k).forEach(v=>{if(v)c[v]=(c[v]||0)+1;});});return c;};
  const present=k=>[...new Set(inYear.flatMap(b=>facetVals(b,k)).filter(Boolean))].sort();
  let h="";
  h+=fgroup("committee","Committee",present("committee"),cnt("committee","committee"));
  h+=fgroup("topic","Topic",present("topic"),cnt("topic","topic"));
  h+=fgroup("sponsor","Prime Sponsor",present("sponsor"),cnt("sponsor","sponsor"),true);
  // No "Year Filed" facet. The term picker above the list already chooses
  // the biennium, and splitting one term into its two filing years was a
  // second control for a distinction the card prints on its own. (The
  // <select id="year"> is the TERM picker, despite its id, and stays.)
  h+=fgroup("kind","Status",["active","law","done","veto"].filter(k=>present("kind").includes(k)),cnt("kind","kind"));
  const days={};inYear.filter(b=>matches(b,"voteday")).forEach(b=>(b.votedays||[]).forEach(d=>days[d]=(days[d]||0)+1));
  const allDays=[...new Set(inYear.flatMap(b=>b.votedays||[]))].sort().reverse();
  if(allDays.length)h+=fgroup("voteday","Floor vote day",allDays,days);
  if(Object.values(sel).some(s=>s.size))h+=`<button class="link" id="clear" style="margin-top:12px">Clear all filters</button>`;
  // Replacing innerHTML resets scrollTop to zero. Capture it first and put it
  // back in the same tick, before anything is painted, or every tick of a
  // checkbox throws the reader back to the top of the list.
  const fx=$("#facets");
  const keep=fx?fx.scrollTop:0;
  const inner=fx?fx.querySelectorAll(".fbody"):[];
  const innerKeep=[...inner].map(el=>el.scrollTop);
  fx.innerHTML=h;
  fx.scrollTop=keep;
  [...fx.querySelectorAll(".fbody")].forEach((el,i)=>{
    if(innerKeep[i]!==undefined)el.scrollTop=innerKeep[i];
  });
}

function simpleDonut(rc,bid,i){
  // A division vote is counted but anonymous. Same ring, same colours, same
  // threshold line as a roll call -- the difference between the two is who is
  // named, not how the count should look. It used to be drawn in a different
  // palette with no threshold at all, which made the same 191 to 158 look like
  // a different kind of vote.
  const y=rc.yeas||0,n=rc.nays||0,tot=(y+n)||1;
  const R=60,C=2*Math.PI*R,GAP=32,gap=C*GAP/360,avail=C-gap;
  const won=!!rc.passed;
  const seg=(len,fill,sideWon)=>`<circle r="${R}" cx="86" cy="86" fill="none" stroke="${fill}"
    stroke-width="28" opacity="${sideWon?1:.75}"
    stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${-gap/2}"></circle>`;
  const need=rc.threshold_needed||Math.floor(tot/2)+1;
  const frac=Math.min(1,Math.max(0,need/tot));
  const a=(180+GAP/2+(360-GAP)*frac)*Math.PI/180;
  const tick=marker(a,R,need,"");
  return `<div class="votewrap"><svg class="donut" viewBox="0 0 172 206" width="172" height="206"
    role="img" aria-label="Division vote, ${y} yes to ${n} no, needing ${need}">
    <g transform="rotate(90 86 86)">${seg(avail*y/tot,"var(--yes)",won)}</g>
    <g transform="translate(172,0) scale(-1,1)"><g transform="rotate(90 86 86)">${seg(avail*n/tot,"var(--no)",!won)}</g></g>
    ${tick}${yn(GAP,R,won)}
    ${score(y,n,won)}</svg>
    <div class="legend">
      <div class="lrow"><span class="sw" style="background:var(--yes)"></span>
        <span>Yes${won?`<span class="won" title="this side prevailed">\u2713</span>`:""}</span>
        <span class="c">${y}</span></div>
      <div class="lrow"><span class="sw" style="background:var(--no)"></span>
        <span>No${won?"":`<span class="won" title="this side prevailed">\u2713</span>`}</span>
        <span class="c">${n}</span></div></div></div>`;
}

function donut(bid,i,rc){
  // Yes on the LEFT in green, no on the RIGHT in red, growing up from a gap at
  // six o'clock. Green for yes and red for no is the chamber's own convention
  // -- the buttons on a member's desk -- so it describes the vote rather than
  // judging it. Nothing here relies on telling the two apart by colour: the
  // Y and N under the ring, the gap and the legend all carry it, which matters
  // because red and green are the pair most readers cannot separate.
  const yes=[],no=[];
  for(const[p,tl]of Object.entries(rc.tally||{})){
    if(tl.Yea)yes.push({key:`${p}-Yea`,p,side:"Yea",n:tl.Yea});
    if(tl.Nay)no.push({key:`${p}-Nay`,p,side:"Nay",n:tl.Nay});
  }
  // Biggest group nearest the gap, smallest nearest the top. The two sides
  // meet at twelve o'clock, so ordering each one this way puts the party that
  // carried it at the base and the members who crossed over adjacent to each
  // other across the meeting point -- which is where you compare them. The
  // old order left one crossover group at the base of one arc and the other at
  // the top of the other, as far apart as the ring allows.
  yes.sort((a,b)=>b.n-a.n);
  no.sort((a,b)=>b.n-a.n);
  const segs=yes.concat(no);
  // The ring keeps the order above -- its geometry puts crossovers adjacent
  // at twelve o'clock. The legend does not follow it: read as a list,
  // R-Yes, R-No, D-Yes, D-No puts each party's split on adjacent rows.
  const rows=segs.slice().sort((a,b)=>byParty(a.p,b.p)||yeaFirst(a.side,b.side));
  const total=segs.reduce((a,s)=>a+s.n,0)||1;
  // A wider gap: at ten degrees the two sides read as one ring with a nick in
  // it. At twenty-five they read as two sides of a question.
  const R=60,C=2*Math.PI*R,GAP=32,gap=C*GAP/360,avail=C-gap;
  const key=`${bid}|${i}`,chosen=segSel[key];
  // At rest each side is one unbroken colour, because the first question is
  // whether it passed and a ring cut into party blocks answers a different one
  // before it is asked. The divisions appear when a group is chosen, which is
  // the moment they are what you are looking at.
  const PART=chosen?C*1.4/360:0;
  const arc=(list,fill,sideWon)=>{let off=gap/2;return list.map(s=>{
    const len=Math.max(0,avail*s.n/total-PART),o=-off;off+=len+PART;
    // The losing side sits back a quarter, so which way it went reads before
    // the numbers do. A chosen group overrides that: then the question is who,
    // not which.
    const dim=chosen?(chosen===s.key?1:.28):(sideWon?1:.75);
    return `<circle r="${R}" cx="86" cy="86" fill="none" stroke="${fill}" stroke-width="28"
      stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${o}" opacity="${dim}"
      data-seg="${key}|${s.key}"></circle>`;
    }).join("");};
  // Where the yes side had to reach. rollcall_parser works this out per
  // motion, so a veto override marks two thirds and a CACR three fifths of the
  // whole membership rather than of those who turned up. Without it a chart
  // showing 204 to 116 looks like a comfortable win, and that vote failed.
  const voting=(rc.yeas||0)+(rc.nays||0);
  const need=rc.threshold_needed||Math.floor(voting/2)+1;
  const frac=voting?Math.min(1,Math.max(0,need/voting)):0.5;
  const a=(180+GAP/2+(360-GAP)*frac)*Math.PI/180;
  // The ring is 28 wide about radius R, so its edges are at R-14 and R+14. The
  // tick starts flush with the inner edge and runs six past the outer one:
  // grounded on the inside, proud on the outside, so it reads as a mark
  // against the ring rather than a line drawn through it.
  const tick=voting?marker(a,R,need,rc.threshold_rule):"";
  const won=!!rc.passed;
  const circles=`<g transform="rotate(90 86 86)">${arc(yes,"var(--yes)",won)}</g>
    <g transform="translate(172,0) scale(-1,1)"><g transform="rotate(90 86 86)">${arc(no,"var(--no)",!won)}</g></g>`;
  // A check beside every group on the side that prevailed. Which side won is
  // the first thing anyone wants from a vote, and it should not have to be
  // worked out by comparing two numbers against a threshold.
  const legend=rows.map(s=>{
    const winner=(s.side==="Yea")===won;
    return `<button class="lrow ${chosen===s.key?'sel':''}" data-seg="${key}|${s.key}">
    <span class="sw" style="background:${PARTY_COLOR[s.p]||"var(--ink-2)"}"></span>
    <span>${PARTY_NAME[s.p]||s.p} — ${s.side==="Yea"?"Yes":"No"}${
      winner?`<span class="won" title="this side prevailed">\u2713</span>`:""}</span>
    <span class="c">${s.n}</span></button>`;}).join("");
  const others=OTHER.map(([st,label])=>({st,label,n:(rc.members||[]).filter(m=>m.v===st).length})).filter(o=>o.n);
  const oTot=others.reduce((a,o)=>a+o.n,0);
  const oRows=others.length?`<div class="othergrp"><div class="otherhd">Other — ${oTot}<span class="c">not in chart</span></div>
    ${others.map(o=>`<button class="lrow ${chosen==="other-"+o.st?'sel':''}" data-seg="${key}|other-${o.st}">
    <span class="sw sw-o"></span><span>${o.label}</span><span class="c">${o.n}</span></button>`).join("")}</div>`:"";
  let list="";
  if(chosen){
    const grid=a=>`<div class="mgrid">${a.map(m=>`<div class="m">${esc(m.n)}</div>`).join("")}</div>`;
    if(chosen.startsWith("other-")){
      const st=chosen.slice(6),o=OTHER.find(x=>x[0]===st)||[st,st,""];
      const names=(rc.members||[]).filter(m=>m.v===st);
      list=`<div class="mlist"><h3>${o[1]} — ${names.length}</h3>
        <p class="note" style="margin:0 0 9px">${o[2]}</p>${grid(names)}</div>`;
    }else{
      const[p,side]=chosen.split("-");
      const names=(rc.members||[]).filter(m=>m.p===p&&m.v===side);
      list=`<div class="mlist"><h3>${PARTY_NAME[p]||p}s who voted ${side==="Yea"?"yes":"no"} — ${names.length}</h3>${grid(names)}</div>`;
    }
  }
  return `<div class="votewrap"><svg class="donut" viewBox="0 0 172 206" width="172" height="206"
    role="img" aria-label="Votes by party: ${rows.map(s=>`${PARTY_NAME[s.p]||s.p} ${s.side==='Yea'?'yes':'no'} ${s.n}`).join(", ")}. ${
      rc.threshold_rule?`Needed ${need}, ${esc(rc.threshold_rule)}`:`Needed ${need} for a majority`}.">
    ${circles}${tick}${yn(GAP,R,won)}
    ${score(rc.yeas,rc.nays,won)}</svg>
    <div class="legend">${legend}${oRows}</div></div>${list}`;
}

// Y and N sit either side of the gap, on the side whose votes they are. The
// winner is bold, which is the same fact the ring shows, said a second way for
// anyone who cannot use the first.
// What the yes side had to reach, as a triangle at the rim pointing in at the
// ring. A dashed line crossing the band read as part of the chart's furniture;
// a mark outside it, aimed at the point it is about, reads as a pointer.
function marker(a,R,need,rule){
  // Tip ON the outer edge, base further out. It used to point from outside to
  // a tip nine pixels INSIDE the band, which read as part of the ring rather
  // than as something aimed at it.
  const tip=R+14, out=R+14+11, half=6.5;
  const px=(r,off)=>[86+r*Math.sin(a+off), 86-r*Math.cos(a+off)];
  const [tx,ty]=px(tip,0);
  const [lx,ly]=px(out,-half/out);
  const [rx,ry]=px(out,half/out);
  return `<polygon points="${tx.toFixed(1)},${ty.toFixed(1)}
    ${lx.toFixed(1)},${ly.toFixed(1)} ${rx.toFixed(1)},${ry.toFixed(1)}"
    fill="var(--ink-2)"><title>${need} needed${rule?` \u2014 ${esc(rule)}`:""}</title></polygon>`;
}

function yn(GAP,R,won){
  // Below the ring rather than on it. Following the curve put them at an angle
  // to each other and close together near the gap, which read as decoration on
  // the chart; set on a line underneath, they read as labels for the two sides.
  // The legend beside the donut is taller than the donut, so this space costs
  // nothing.
  const Y=188;
  // --ink-2 FOR THE LOSING LETTER, and it was --ink-3, which has not existed
  // since the palette went to two inks on 7 September. An unresolved var() in
  // an SVG fill does not inherit and does not warn: it falls back to the
  // property's initial value, which for fill is BLACK. On the light palette
  // black read as emphasis and nobody noticed for five days; on the dark one
  // the losing side's Y or N was black on a dark card and effectively gone.
  //
  // Worth knowing why every search missed it: the token name is BUILT here by
  // concatenation, so the string "--ink-3" appears nowhere in this file and
  // grep for it finds only comments. The same shape of bug is already
  // recorded in app.css about --brick, which was used and never defined, so
  // color-mix() dropped the whole declaration silently. A var() that does not
  // resolve is the quietest failure in this codebase.
  const at=(x,txt,won)=>`<text x="${x}" y="${Y}" text-anchor="middle" font-size="30"
      letter-spacing=".04em" font-weight="${won?700:400}"
      fill="var(--ink${won?"":"-2"})">${txt}</text>`
    // Bold and underlined, so the prevailing side survives being printed in
    // grey, photocopied, or read by somebody who cannot see the colours.
    +(won?`<line x1="${x-14}" y1="${Y+8}" x2="${x+14}" y2="${Y+8}"
      stroke="var(--ink)" stroke-width="2.5"></line>`:"");
  return at(42,"Y",won)+at(130,"N",!won);
}

// The count in the middle, with the side that prevailed in bold.
//
// PREVAILED, not the larger number. A veto override at 204 to 116 has more
// yeses and still failed, because it needed two thirds; bolding 204 would say
// the yes side won a vote it lost. The threshold tick on the ring shows why,
// and this agrees with it.
function score(y,n,won){
  const part=(v,b)=>`<tspan font-weight="${b?700:400}">${v}</tspan>`;
  return `<text x="86" y="91" text-anchor="middle" font-size="16" fill="var(--ink)"
    font-variant-numeric="tabular-nums">${part(y,won)}<tspan fill="var(--rule-2)"
    font-weight="400" dx="2" dy="0">\u2009|\u2009</tspan>${part(n,!won)}</text>`;
}

function fullRecord(bid,i,rc){
  const k=`${bid}|${i}`;
  if(!fullOpen.has(k))return `<button class="discl" data-full="${k}">View full voting record →</button>`;
  // Sorted on the surname-first key, not on what is displayed: ordering
  // "Rep. Jodi Nelson (R)" alphabetically groups 400 members by honorific
  // and then by first name.
  const col=(v,p)=>(rc.members||[]).filter(m=>m.v===v&&(p==null||(m.p||"X")===p))
    .sort((a,b)=>(a.s||a.n||"").localeCompare(b.s||b.n||""));
  const grid=a=>`<div class="mgrid">${a.map(m=>`<div class="m">${esc(m.n)}</div>`).join("")}</div>`;
  const sect=([st,label,blurb])=>{const a=col(st);return a.length?`<div class="mlist">
    <h3>${label} — ${a.length}</h3><p class="note" style="margin:0 0 9px">${blurb}</p>${grid(a)}</div>`:"";};
  const y=col("Yea"),n=col("Nay"),tot=(rc.members||[]).length;
  // One pair of columns per party, Republicans first, then Democrats, then
  // anyone else: a party's yea and nay sit side by side, so its split is read
  // across one row rather than hunted for in two lists 400 names long.
  const parties=[...new Set((rc.members||[]).filter(m=>m.v==="Yea"||m.v==="Nay")
    .map(m=>m.p||"X"))].sort(byParty);
  const pair=p=>{const py=col("Yea",p),pn=col("Nay",p),nm=PARTY_NAME[p]||p;
    return `<div class="full"><div><h3>${nm} Yea — ${py.length}</h3>${grid(py)}</div>
    <div><h3>${nm} Nay — ${pn.length}</h3>${grid(pn)}</div></div>`;};
  return `<button class="discl" data-full="${k}">Hide full voting record</button>
    ${parties.map(pair).join("")}
    ${OTHER.map(sect).join("")}
    <p class="note" style="margin-top:12px">All ${tot} recorded members accounted for:
      ${y.length} yes, ${n.length} no, ${tot-y.length-n.length} not voting.</p>`;
}

/* ---- the panes -------------------------------------------------------
   One function per tab. This was one 472-line function holding 26 consts
   in a single scope, and three times in one day a template literal read
   one of them before its line ran: a blank card, with the bill's data
   already fetched and sitting in hand.

   These are function DECLARATIONS rather than consts holding arrows.
   Declarations are hoisted and initialised before any of this runs, so
   the order they appear in cannot be got wrong. Order still matters
   inside each one, and each one is now short enough to see it.

   b is the index row, d the fetched detail. rsa is passed in rather than
   rebuilt: it compiles a RegExp from the bill's own statute citations,
   two of these need it, and a parameter says so where scope would not. */

// Pure and identical for every bill, so built once here rather than
// rebuilt inside a map callback that runs for each of 2,234 of them.
// How a vote was taken, title-cased because every place this appears is a
// LABEL beside a date rather than a clause in a sentence: "12 March 2025 ·
// House · Voice Vote". Prose elsewhere still says "decided on a voice vote" in
// lower case, which is correct there and is not this constant.
const AVK={VV:"Voice Vote",DV:"Division Vote",RC:"Roll Call"};
// A committee report's colour, from what was MOVED rather than from who won.
//
// It used to be chosen from `side` alone: Committee and Majority green,
// Minority red. So a unanimous committee recommending a bill be killed got
// the same green as one recommending it pass, and a minority that wanted it
// to pass got the red. 1,248 of 2,637 chips read as the opposite of the
// motion they label -- 556 of them a whole committee's Inexpedient to
// Legislate shown in the colour of approval.
//
// Which side prevailed is already on the row: the Majority/Minority label
// sits to the left of the chip and the committee's vote beside it, so
// nothing is lost by colouring the motion instead.
const RECCOLOUR=[[/INEXPEDIENT/i,"s-done"],
                 [/INTERIM\s+STUDY|RE-?REFER/i,"s-study"],
                 [/OUGHT\s+TO\s+PASS/i,"s-law"]];
const recColour=r=>{const m=RECCOLOUR.find(([re])=>re.test(r||""));
  return m?m[1]:"";};
// Who signed in for and against the bill at a hearing.
//
// Counts only, deliberately. The General Court's sign-in sheet carries a name,
// a town and often written testimony for each of some 400,000 rows, and almost
// every one is a member of the public who signed a committee's sheet rather
// than a public figure. The number is the civic fact; the person is not this
// site's to republish.
//
// "dated" is the difference between a fact and a number that looks like one:
// with it the count is this hearing's, without it the database had the bill
// but not this date and the figure covers every hearing the bill had.
const signins=t=>{
  if(!t||!t.total)return "";
  const n=x=>Number(x||0).toLocaleString();
  const bit=(v,label,cls)=>v?`<span class="sgn ${cls}">${n(v)} ${label}</span>`:"";
  return `<span class="tnote">${bit(t.support,"support","for")}${
    bit(t.oppose,"oppose","against")}${bit(t.neutral,"neutral","")} ${
    n(t.total)} signed in${t.dated?"":" across this bill’s hearings"}</span>`;
};
const CHNAME={H:"Representatives",S:"Senators"};
const hms=x=>new Date(x*1000).toISOString().substr(11,8);
// "0:02:00" or "-0:05:00" as the manifest wrote it -- and a plain number of
// seconds, which is what actually arrives now. build_proceedings.py runs the
// manifest string through as_seconds() and build_site_v2 writes the float, so
// String(2646) matched nothing here and every estimate collapsed to zero.
const secs=v=>{if(typeof v==="number")return v;
  const m=/^(-?)(\d+):(\d{2}):(\d{2})$/.exec(String(v||""));
  if(m)return (m[1]?-1:1)*(+m[2]*3600+ +m[3]*60+ +m[4]);
  const n=parseFloat(v); return isFinite(n)?n:0;};
// The bill's own shape: a numbered section opens a block, and everything
// under it belongs to that section. Set as one paragraph it is unreadable,
// and anyone used to the printed version loses their footing entirely.
const SEC=/^\s*(\d{1,3})\s+(?=[A-Z(])/;
// The General Court puts a whole section in one paragraph. The outline a
// reader knows from the printed bill -- I., (a), (b), II.(a), a new RSA
// section number -- exists only in that document's typography, and is gone
// by the time the page is read as text.
//
// So it is rebuilt, and only where the record is unambiguous: a break goes
// in before a marker that OPENS after a full stop or a colon and is followed
// by a capital or an opening quote. "either (a) all new or (b) repealed"
// does not qualify, because what follows is lower case.
//
// This changes the layout and not one word. The text is the General Court's;
// where its lines fall on this page is ours, and could not be otherwise --
// the line breaks were never in the file.
const OUTLINE=/(?<=[.:])\s+(?=(?:[IVXL]{1,5}\.(?:\([a-z]\))?|\([a-z]\)|\d{1,3}:\d+[-\w]*)\s+[A-Z\u201C"])/g;

// Statutes cited in the committee's own words become links. Applied AFTER
// escaping, which is safe because a citation has nothing in it to escape,
// and longest first so "RSA 91-A" cannot eat the front of "RSA 91-A:4".
// One pass, not one pass per citation: replacing in sequence rescans what it
// has already written, so "RSA 91-A" matched inside the anchor just built for
// "RSA 91-A:4". Longest first inside the alternation keeps the longer
// citation winning where both could match.
function makeRsa(d){
  return (s)=>{const m=d.rsa||{},ks=Object.keys(m);
    if(!ks.length)return s;
    const re=new RegExp(ks.sort((a,b)=>b.length-a.length)
      .map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|"),"g");
    return s.replace(re,k=>`<a href="${esc(m[k])}" target="_blank" rel="noopener"`
      +` class="rsa">${esc(k)}</a>`);};
}

// Quoted from the General Court's own bill status page, in the order that page
// states them. This table lived only in the Python renderer that drew these
// bills a second time; every one of the 4,230 bill files carries a facts
// object, so deleting that renderer without this would have taken the stated
// status off every bill on the site.
//
// Nothing here is worked out. "Local government impact" is the page's Y or N
// written as a word, and that is the whole of the interpretation.
// FACTS and factsTable drew the status page's own fields at the top of the
// Documents tab -- status, date introduced, committee code -- every one of
// which is already on the summary in a sentence. Removed rather than
// hidden, so nothing calls a function that is not there.
const PANE_NOTE={
  // The Videos tab had a paragraph here explaining, once at the top, how
  // every start time below it was arrived at. Each proceeding already says
  // that for itself -- the word "approximate" beside a time that is one, and
  // a line under the player saying what the number is -- so the paragraph was
  // the same thing said twice, above rather than beside the claim it was
  // about.
  reports:`The recommendation, the vote and the day it was signed come from the
    docket; the reasoning, where there is any, is reproduced from the House
    Calendar in the committee\u2019s own words.`,
};
const paneNote=(k)=>PANE_NOTE[k]?`<p class="src">${PANE_NOTE[k]}</p>`:"";

// The General Court's own analysis of the bill, at the top of the summary
// because it is the shortest true answer to what the bill does. Long ones are
// clamped to six lines by CSS and given a button by clampAnalysis(), which
// measures rather than guessing from a character count -- six lines is a
// different number of characters on a phone and on a desktop.
function analysis(d, rsa){
  const t=((d.billtext||{}).analysis||"").trim();
  if(!t)return "";
  return `<section class="anbox" data-an="1">
    <h2 class="anlab">Official legislative analysis</h2>
    <div class="antext">${rsa?rsa(esc(t)):esc(t)}</div>
    <p class="src">Source: NH General Court</p></section>`;
}

// WHAT THIS BILL IS, where its number carries a standing meaning. HB1 has
// been the state budget in every term since 1993-1994 and its title says only
// "making appropriations for the expenses of certain departments of the
// state", which is accurate and tells a reader nothing.
//
// ATTRIBUTED TO THIS SITE, NOT TO THE RECORD. Everything else in this box is
// the General Court's -- the official analysis says "Source: NH General
// Court" underneath it for exactly this reason. These words are Granite
// Record's, and a reader who cannot tell the difference has been given a
// worse page, not a fuller one.
function billNote(d){
  const n=d&&d.bill_note;
  if(!n||!n.note)return "";
  return `<section class="anbox billnote">
    <h2 class="anlab">${esc(n.label||"About this bill")}</h2>
    <div class="antext">${esc(n.note)}</div>
    <p class="src">Written by Granite Record, not quoted from the General
      Court. It describes what this bill number is for, which its title does
      not say.</p></section>`;
}

// WHAT AN ARCHIVED TERM ACTUALLY HAS, which is not the same in all eighteen
// of them. This was one paragraph on one boolean, drawn on 31,449 of the
// site's 33,683 bill pages, and it was wrong in both directions at once.
//
// It understated the recent terms: 2017-2018, 2019-2020 and 2023-2024 have
// full dockets, and the "View docket" block that contradicts the paragraph
// renders seven lines below it in this same function.
//
// It overstated the older ones. "The recorded votes come from the General
// Court's database" was false for fifteen terms; named roll calls exist only
// for 2023-2024 and the current term. "The committee it went to" was false
// for the five terms 1989-1998, which have none.
//
// d.archived is now the term's coverage object rather than true, computed at
// build time from what was fetched. It stays truthy, so nothing that merely
// tests it had to change. The wording is derived from the flags rather than
// from a list of terms, because the fetches are still landing -- 2021-2022's
// docket is being pulled as this is written -- and a hard-coded list would be
// wrong again by the afternoon.
//
// NEVER "DOES NOT EXIST". These are records not yet fetched. The General
// Court has them; this site does not have them yet, and saying otherwise
// would be inventing a fact about somebody else's archive.
function archivedNote(d){
  const a=d&&d.archived;
  if(!a)return "";
  const c=(typeof a==="object")?a:{};
  const P=s=>`<p class="note" style="margin:10px 0 0">${s} The bill's own
    record at the General Court is linked above.</p>`;

  // The first year of the term. Roll calls are on record from 1999 and
  // hearings on video from May 2020; before those, no such thing exists to
  // fetch, and the page must not say it is merely missing.
  const y=parseInt(String(d.term||d.year||"").slice(0,4),10)||0;
  const and=xs=>xs.join(", ").replace(/, ([^,]*)$/," and $1");

  if(!c.docket){
    // WHAT IS HERE, THEN WHAT IS NOT. This branch told every bill of
    // 1999-2016 that "the recorded votes ... have not been fetched yet" --
    // 15,389 pages, each with a Votes tab beside the sentence -- because it
    // never looked at c.votes, and it said nothing of the hearings that
    // 1989-1998 have. It reads every flag now.
    const have=["the title and the status in each chamber"];
    if(c.committee)have.push("the committee it went to");
    if(c.hearings)have.push("its hearings");
    // No comma inside an item: and() turns the last comma into "and", which
    // made this "its roll calls and member by member".
    if(c.votes)have.push("each member's vote on its roll calls");
    if(c.sponsors)have.push("its sponsors");
    if(c.reports)have.push("the committee's written report");
    const gaps=["the docket's full history"];
    if(!c.sponsors)gaps.push("the sponsors");
    if(!c.reports)gaps.push("the written committee reports");
    if(!c.votes&&y>=1999)gaps.push("the roll calls");
    if(!c.hearings)gaps.push("its hearings");
    return P(`This term is archived. Here: ${and(have)}. Not yet on this
      site for it: ${and(gaps)}.${!c.votes&&y&&y<1999?` No roll call from
      before 1999 is in the General Court's own record of votes.`:""}`);
  }

  // Has a docket. What is missing beyond it is what the reader needs told.
  const gaps=[];
  if(!c.sponsors)gaps.push("the sponsors");
  if(!c.reports)gaps.push("the written committee reports");
  if(!c.votes&&y>=1999)gaps.push("the roll calls naming individual members");
  if(!c.video&&y>=2019)gaps.push("a recording of any hearing");
  if(!gaps.length)
    return P(`This term is archived, but its record is close to complete: the
      docket, the sponsors, the committee reports and the recorded votes are
      all here. What a current term adds is the bill's own text, which is
      linked rather than loaded.`);
  return P(`This term is archived, and its docket is here: every action the
    General Court recorded, and the committee's recommendation and the vote on
    it. Not yet fetched for this term: ${and(gaps)}.`);
}

// ===================================================== the bill's own facts ==
// THE GENERAL COURT'S OWN FIELDS, AS A TABLE, replacing the CURRENT STATUS
// panel. On a law that panel said the card's chip back word for word, and
// where it did not it concatenated three separate fields into one line --
// "House: PASSED/ADOPTED - Senate: LAID ON TABLE" -- which a reader had to
// unpick. They are three fields, so they are three rows.
//
// Measured on the current term's 847 bills before this was written: every one
// carries a general status, 763 a House status, 526 a Senate status, and the
// two chambers disagree on 321 of them. The per-chamber rows are not
// decoration, which is why they are kept and the panel is not.
//
// CHAPTER IS NOT AN RSA CHAPTER. Both are called a chapter and they are
// different numberings. `chapter` is the session law: HB 1 of 2025 became
// Chapter 140 of the Laws of 2025. The RSA chapters are the ones the bill
// amends, and HB 1 amends five of them. Two rows, and only the RSA row is
// linked -- every URL there is one already used elsewhere on this page, where
// gc.nh.gov's address for a chaptered law has never been checked and guessing
// it would put a broken link on 305 bills of this term alone.
function rsaChapters(d){
  const seen=new Map();
  for (const [k,u] of Object.entries(d.rsa||{})){
    const m=/^RSA\s+([0-9]+(?:-[A-Za-z]+)?)/.exec(k);
    // The link is to the first SECTION of that chapter the bill cites,
    // because that is the address this site has and can stand behind. It
    // lands the reader in the right chapter either way.
    if(m && !seen.has(m[1])) seen.set(m[1], u);
  }
  return [...seen.entries()];
}

function factsTable(b,d){
  const f=d.facts||{};
  const rows=[];
  const add=(k,v)=>{ if(v) rows.push([k,v]); };

  // NOT facts.gen_status, WHICH IS NOT A STATUS ON MOST BILLS. Counted over
  // the current term's 2,234: it reads "HOUSE" on 1,065 and "SENATE" on 454
  // -- 68% -- because the field records which chamber the bill is in, not
  // what happened to it. A row labelled "Bill Status" saying "HOUSE" is
  // worse than no row. Where it IS a status (SIGNED BY GOVERNOR, VETOED BY
  // GOVERNOR, PASSED, LAW WITHOUT SIGNATURE, VETO OVERRIDDEN, 715 bills) the
  // site's own classification says the same thing in words a reader uses, so
  // nothing is lost by taking it from there for all of them.
  add("Bill Status", esc(b.status||d.next_step||""));
  // The Court's own per-chamber fields, which ARE the extra information: 763
  // bills carry a House status, 526 a Senate status, and the two differ on
  // 321 of them.
  if(f.house_status) add("House Status", esc(f.house_status));
  if(f.senate_status && f.senate_status!==f.house_status)
    add("Senate Status", esc(f.senate_status));
  if(d.chapter)
    add("Chapter", `Chapter ${esc(d.chapter)}`
      + (d.year?`, Laws of ${esc(d.year)}`:""));
  const ch=rsaChapters(d);
  if(ch.length)
    add(ch.length===1?"Amends RSA chapter":"Amends RSA chapters",
      ch.map(([n,u])=>`<a class="rsa" href="${esc(u)}" target="_blank"`
        +` rel="noopener">${esc(n)}</a>`).join(", "));
  if(d.house_committee) add("House Committee", cmteLink("House "+d.house_committee));
  if(d.senate_committee) add("Senate Committee", cmteLink("Senate "+d.senate_committee));
  add("Subject", esc(d.subject||""));
  add("Introduced", esc(f.date_introduced||""));
  add("LSR", esc(f.lsr||""));
  if(!rows.length) return "";
  return `<section class="facts"><h2>On the record</h2>
    <table class="facttab"><tbody>${rows.map(([k,v])=>
      `<tr><th scope="row">${esc(k)}</th><td>${v}</td></tr>`).join("")}</tbody></table>
    ${d.docket_url?`<p class="src"><a href="${esc(d.docket_url)}" target="_blank"
      rel="noopener">This bill on gencourt &#8599;</a></p>`:""}</section>`;
}

function renderSummary(b,d,rsa){
  const _an=billNote(d)+analysis(d,rsa);
  // THE FACTS TABLE IS EMITTED FIRST, and the stylesheet moves it on narrow
  // screens rather than the other way round. It was emitted after the
  // analysis, which read better in source order and cost a 274px hole in the
  // page: a grid row is as tall as its tallest item, so the row holding the
  // 482px panel gave the 208px analysis beside it a dead tail, and no span
  // fixed every bill -- two rows left 75px on HB 1, three left an empty row
  // on HB 751. A float cannot push in-flow content down at all, which is the
  // property actually wanted, and a float has to come first to sit at the
  // top. So: first in the DOM, floated right above 1100px, and ordered back
  // below the analysis underneath that. See .facts in app.css.
  return factsTable(b,d) + _an + `
${d._error?`<div class="loaderr"><b>This bill's detail did not
    load.</b><span>${esc(d._error)}</span></div>`:""}
    ${(d.notes||[]).map(x=>`<p class="note">${esc(x)}</p>`).join("")}
    ${(d.stages&&d.stages.length)
      ? `<div class="story">${d.stages.map(st=>
          `<div class="stg">${st.label?`<h2>${esc(st.label)}</h2>`:""}
           <p>${esc(st.text)}</p>${(st.notes||[]).map(n=>
             `<p class="note">${esc(n)}</p>`).join("")}</div>`).join("")}</div>`
      : (d.narrative?`<p class="story"><span class="stg">${esc(d.narrative)}</span></p>`:"")}
    ${archivedNote(d)}
    ${(d.events||[]).length?`<details class="docket"><summary><span class="caret"></span>View docket</summary>
      <p class="note">Every action the General Court recorded, in its own words
        and in the order it recorded them.</p>
      <ul class="tl">${d.events.filter(e=>!e.cancelled).map(e=>`<li>
        <span class="d">${e.date?esc(fdate(e.date)):""}</span>
        <span class="w">${esc(e.text||"")}${e.cite?` <span class="cite">${
          e.cite_url?`<a href="${esc(e.cite_url)}" target="_blank"
          rel="noopener">${esc(e.cite)}</a>`:esc(e.cite)}</span>`:""}${
          signins(e.testimony)}</span>
        </li>`).join("")}</ul></details>`:""}
`;
}

function renderVotes(b,d){
  // What this tab holds, in one sentence, naming the bill it is about. It
  // used to explain the roll call file, the ordering, and the presiding
  // officer's tie-breaking vote before a reader reached a single vote.
  const lead=`<p class="src">All recorded votes on ${esc(b.n||b.id)}. Roll
    call votes record how individual legislators voted on a certain motion,
    but voice or division votes do not.</p>`
    + (d.vote_note?`<p class="note">${esc(d.vote_note)}</p>`:"");
  return lead+((d.rollcalls||[]).length?d.rollcalls.map((rc,i)=>{
    const vk=rc.vote_kind||"RC";
    let body;
    if(vk==="RC"){
      body=donut(b.id,i,rc)+fullRecord(b.id,i,rc);
    }else if(vk==="DV"&&rc.yeas!=null){
      // A division vote is counted but anonymous. Chart the split; there is no
      // member list to show, and saying so is the point.
      body=simpleDonut(rc,b.id,i)+`<p class="note" style="margin-top:11px">A division vote
        records the count but not who voted which way, so there is no list of
        members for this one.</p>`;
    }else{
      body=`<p class="note" style="margin-top:6px">Decided on a voice vote. Only
        which side sounded louder was recorded — there is no count and no record
        of how any member voted.</p>`;
    }
    return `<section class="rc">
      <div class="rchead"><span class="rcq">${esc(rc.question)}${
        rc.amendment?` <span class="ramd">${esc(rc.amendment)}</span>`:""}</span>
      <span class="rcd">${fdate(rc.date)} · ${rc.body==="H"?"House":"Senate"}${
        AVK[vk]?` · ${AVK[vk]}`:""}</span>
      <span class="rcres ${rc.passed?'pass':'fail'}">${rc.passed?"Adopted":"Failed"}</span></div>
      ${rc.mover?`<p class="rcby">Moved by ${esc(rc.mover)}</p>`:""}
      ${rc.threshold_note?`<p class="note" style="margin:6px 0 0">${esc(rc.threshold_note)}</p>`:""}
      ${body}</section>`;}).join("")
    :`<p class="note">No roll call votes on this bill.</p>`);
}

// "HB 1123 - House Labor Public Hearing", "HB 1123 - Senate Floor Debate".
// Only the kind is title-cased: a committee's name is the General Court's own
// and "Labor, Industrial And Rehabilitative Services" is not how it spells it.
const CHWORD={H:"House",S:"Senate"};
function stationTitle(b,s){
  const kind=(s.what||"").replace(/\b[a-z]/g,c=>c.toUpperCase());
  const cmte=(s.committee||"").trim();
  const ch=CHWORD[s.body]||"";
  // A floor row's "committee" is already the chamber, so it is not repeated.
  const where=(!cmte||cmte===ch)?ch:(ch?`${ch} ${cmte}`:cmte);
  return [b.n||b.id, [where,kind].filter(Boolean).join(" ")]
    .filter(Boolean).join(" - ");
}

function renderHearings(b,d){
  // si, because the pid was built from the video and the timestamp, so two
  // proceedings on the same recording resolving to the same second shared one
  // -- and the seek handler resolves a pid with querySelector, which returns
  // the first match. Pressing a timestamp under the second player moved the
  // first. 238 stations.
  return (d.stations||[]).length?d.stations.map((s,si)=>{
    let inner;
    // Whether this station ends up pointing at a moment. It was a list of
    // state strings kept in a second place, which is how "stated" came to be
    // marked pending while an estimate was marked done.
    let placed=false;
    // A recording we have is a recording the reader can watch, whether or not
    // we can say where in it the bill is. Pinning down start times is ongoing
    // work; sending somebody to YouTube in the meantime is a worse answer than
    // handing them the tape and saying so.
    const player=(from,stub,note)=>{
      const pid=`${esc(s.video_id)}_${si}_${Math.max(0,Math.floor(from))}`;
      return `<div class="player" data-player="${pid}">
        <button type="button" class="pstub"
          data-embed="${esc(s.video_id)}|${Math.max(0,Math.floor(from))}|${pid}"
          ><span>\u25B6</span><span>${stub}</span></button>
        <div class="pbar">
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}&t=${
             Math.max(0,Math.floor(from))}s"
             target="_blank" rel="noopener">Open on YouTube</a>
          <span class="tolnote">${note}</span></div></div>`;};
    // "stated" is "located" with the boundary in the chair's own words. It
    // was its own state string and matched no branch here, so the best data
    // this site has -- 3,829 proceedings, a median of one second -- fell
    // through to "the moment was not identified". The branch below already
    // reads start_stated and words itself accordingly; it only ever needed to
    // be reached.
    if(s.state==="located"||s.state==="stated"){
      // Open essentially AT the mark. The old lead was five minutes for an
      // estimate and 45 seconds for a quotation, on the reasoning that
      // arriving early costs only scrubbing -- but it made the commonest case
      // land the reader in the middle of the previous bill, and the page then
      // had to explain a time that was not the bill's. A boundary is timed to
      // the caption line the words begin in, so two seconds is enough not to
      // clip the first syllable and little enough to be inaudible.
      const LEAD = 2;
      const from = Math.max(Math.floor(s.start - LEAD), 0);
      // One word, and only when the placement is an inference rather than
      // something the chair said. Everything else the page used to print about
      // provenance -- the tolerance, which of the two dates it was showing,
      // "about where it ends" -- was methodology in the reader's way. What
      // matters is that clicking lands on the bill.
      const approx = s.start_stated ? "" : " approximate";
      // end_stated is no longer read here: a stated close and an inferred
      // one are both just the end now, and the page does not rank them.
      const hasend = s.end && s.end > s.start;
      placed = true;
      const pid = `${esc(s.video_id)}_${si}_${Math.floor(s.start)}`;
      // Guard on the seconds, not on the rounded string: "0 min" is truthy, so
      // a twenty-second segment printed "about 0 min".
      const span = hasend ? s.end - s.start : 0;
      const mins = Math.round(span / 60);
      const dur = mins >= 1 ? `${mins} min` : (span > 0 ? `${Math.round(span)} sec` : "");
      const range = hasend ? `${hms(s.start)}\u2013${hms(s.end)}` : `from ${hms(s.start)}`;
      inner=`<div class="player" data-player="${pid}">
        <button type="button" class="pstub" data-embed="${esc(s.video_id)}|${from}|${pid}">
          <span>▶</span><span>Play ${esc(s.what)} on this bill — ${range}${
            dur?`, about ${dur}`:""}</span></button>
        <div class="pbar">
          <button class="jump" data-seek="${pid}|${Math.floor(s.start)}">${hms(s.start)} starts</button>
          ${hasend?`<button class="jump"
            data-seek="${pid}|${Math.floor(s.end)}">${hms(s.end)} ends</button>`:""}
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}&t=${from}s"
             target="_blank" rel="noopener">Open on YouTube</a>
          ${approx?`<span class="tolnote">approximate</span>`:""}
        </div></div>`;
    }
    else if(s.state==="approximate"){
      // Open a few minutes before the scheduled time, since hearings run late
      // and never early. It is a place to start scrubbing, not a claim.
      const from=Math.max(secs(s.predicted)-300,0);
      inner=player(from,
        `Play the recording from ${hms(from)} \u2014 scheduled for ${
          esc(s.time||"this day")}, start time not identified yet`,
        "start time not identified yet")
        +`<p class="note" style="margin-top:8px">Matching proceedings to the
        moment they begin is ongoing work, and this one is not done. The
        recording is the whole sitting; hearings run behind, so the bill is
        usually after the scheduled time rather than before it.${
        s.candidate?` An automatic pass suggested ${hms(s.candidate)}, but not
        confidently enough to publish as fact.`:""}</p>`;
    }
    // else if, not if. Opening a second chain here meant every station that
    // matched the FIRST chain -- located, stated, approximate -- fell through
    // this one to the "s.video_id" catch-all below, which overwrote the inner
    // that had just been built correctly. 5,453 stations carried a real
    // timestamp the page then threw away.
    else if(s.state==="whole_video"){
      // The recording covers exactly this bill, so it plays from the start and
      // there is nothing to estimate.
      placed=true;
      const pid=`${esc(s.video_id)}_${si}_w`;
      inner=`<div class="player" data-player="${pid}">
        <button type="button" class="pstub" data-embed="${esc(s.video_id)}|0|${pid}">
          <span>&#9654;</span><span>Play the whole recording &mdash; it covers this
          bill only</span></button>
        <div class="pbar">
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}"
             target="_blank" rel="noopener">Open on YouTube</a>
          <span class="tolnote">entire recording is this bill</span></div>
        ${s.title?`<div class="pbar" style="border-top:none">
          <span style="color:var(--ink-2)">${esc(s.title)}</span></div>`:""}</div>`;
    }
    else if(s.state==="consent"){
      // Named nowhere in the recording, so it went through on the consent
      // calendar. There is no moment to point at, and saying "this bill was
      // taken up that day" over a link to nine hours of other business would
      // be worse than saying nothing.
      inner=`<p class="note">Passed on the consent calendar — adopted with the
        rest of the block, without being debated or voted on separately, so
        there is no moment in the recording to point to.
        <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}"
           target="_blank" rel="noopener">The session is here</a> if you want
        the day as a whole.</p>`;
    }
    else if(s.state==="floor_precise"||s.state==="floor_stated"){
      // A roll call closes the item, so its timestamp is the END of the
      // debate, good to a few seconds. The window opens at the PREVIOUS bill's
      // last vote, and everything in between is other bills -- on one real
      // session that gap is 37 minutes. Landing the reader there means 37
      // minutes of the wrong debate before the right one starts.
      //
      // So the player opens shortly before the vote, which is certainly this
      // bill, and the window is offered as a jump for anyone who wants the
      // whole span. Ten minutes covers all but the longest floor debates, and
      // it never runs back past the window.
      // Where the clerk actually opened it, if that was found. The window is
      // the previous bill's roll call and can be half an hour of other
      // business earlier, so it is only a fallback -- and ten minutes before
      // the vote is a worse fallback still, just a less wrong one.
      // floor_stated has a start and an end the chair said, and no roll call
      // at all. Everything below is the same except what may be claimed about
      // the end: "timed to the second" is true of a roll call clock and false
      // of a caption line, and the difference is the whole point of the
      // wording on this site.
      placed=true;
      const voted=s.state==="floor_precise";
      // Guard on the field, not the coerced value. `||0` turned a missing
      // window into a button reading "00:00:00 window opens" that seeked to
      // the gavel-in -- the absence of data printed as a timestamp. A
      // window_start of exactly 0 is real for the first roll call of a
      // session, so the test has to be against null, not against zero.
      const ws=s.window_start!=null?Math.max(Math.floor(s.window_start),0):null;
      // One number, shown and used. The header said debate_start while the
      // player seeked to debate_start-15 and the jump buttons showed two other
      // values again -- four numbers for one moment, and a reader has no way
      // to tell which is the claim.
      const from=s.debate_start!=null
        ? Math.max(Math.floor(s.debate_start),0)
        : Math.max(ws,Math.floor(s.debate_end)-600);
      const pid=`${esc(s.video_id)}_${si}_f${Math.floor(s.debate_end)}`;
      inner=`<div class="player" data-player="${pid}">
        <button type="button" class="pstub" data-embed="${esc(s.video_id)}|${from}|${pid}">
          <span>▶</span><span>${s.debate_start!=null
            ? `Play from ${hms(from)}, where the clerk takes it up`
            : `Play the floor session from ${hms(from)}`} — debate on
          this bill ends at ${hms(s.debate_end)}</span></button>
        <div class="pbar">
          ${ws!=null&&ws<from?`<button class="jump" data-seek="${pid}|${ws}">${
            hms(ws)} window opens</button>`:""}
          <button class="jump" data-seek="${pid}|${Math.floor(s.debate_end)}">
            ${hms(s.debate_end)} ${voted?"the vote":"ends"}</button>
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}&t=${from}s"
             target="_blank" rel="noopener">Open on YouTube</a>
          <span class="tolnote">${voted
            ? (s.debate_start!=null
               ? "the clerk takes it up here; the vote is timed to the second"
               : "vote timed to the second")
            : "the chair opens and closes it; no roll call on this one"
            }</span></div>
        ${(s.motions||[]).length?`<div class="pbar" style="border-top:none">
          <span style="color:var(--ink-2)">Motions: ${s.motions.map(esc).join(" · ")}</span>
          </div>`:""}</div>`;
    }
    // A voice or division vote leaves no roll call to time the end, but the
    // clerk still opened the item and segment_markers still heard it. 393 of
    // these carried debate_start and were being told they had no moment. Its
    // own arm rather than the branch above, which dereferences debate_end in
    // three places and would print "ends at 00:00:00".
    else if(s.state==="floor_dated"&&s.debate_start!=null){
      placed=true;
      const from=Math.max(Math.floor(s.debate_start),0);
      inner=player(from,
        `Play from ${hms(from)}, where the clerk takes it up`,
        "the clerk takes it up here; no roll call to time the end")
        +`<p class="note" style="margin-top:8px">A voice or division vote leaves
        no timestamp for the end, so this points at the opening only.</p>`;
    }
    else if(s.state==="floor_dated")inner=player(0,
      "Play the floor session \u2014 this bill was taken up that day",
      "moment not identified")
      +`<p class="note" style="margin-top:8px">A voice or division vote leaves no
      timestamp in the record, so there is nothing to point at within the
      sitting. The whole session is here.</p>`;
    else if(s.state==="prestream")inner=`<div class="vbox"><p><b>No recording exists.</b>
      Hearings were not livestreamed before 2020, so the written record is all there is.</p></div>`;
    // Defensive: if a proceeding carries a video id but an unrecognised state,
    // still offer the recording. Saying "no recording" when one is right there
    // is the worst possible failure -- it hides working data and looks like the
    // site has less than it does.
    else if(s.video_id)inner=player(0,
      "Play the recording \u2014 the moment was not identified",
      "moment not identified")
      +`<p class="note" style="margin-top:8px">This proceeding has a recording but
      no timestamp yet. That work is ongoing.</p>`;
    else inner=`<div class="vbox"><p>No recording matched to this proceeding.</p></div>`;
    // Was a second list of state strings, which never gained "stated" or
    // "floor_stated" -- so the site's best-evidenced proceedings wore the
    // pending dot while an unlocated estimate wore the finished one. It now
    // follows the branch that actually ran.
    return `<div class="stn ${placed?"done":"pend"}">
      <div class="w">${esc(s.when)}${s.time?" at "+esc(s.time):""}${s.venue?" · "+esc(s.venue):""}</div>
      <div class="t">${esc(stationTitle(b,s))}</div>${
        signins(s.testimony)}${inner}</div>`;}).join("")
    :`<p class="note">No scheduled proceedings on file.</p>`;
}

// Each calendar entry carries the majority's recommendation and, when the
// committee split, the minority's. The two are different motions and must
// not both show the majority's -- on a divided report that would read as
// though the dissenters agreed.
// Every report the tab draws, counted the same way it draws them. This used
// to count only the written ones, so HB686 read "(4)" above five blocks, and
// the 319 bills whose only report is one the docket recorded showed no count
// at all above a report that was plainly there.
// Stations with a recording, counted the way the tab draws them. A station
// with no video_id draws "No recording matched" and is not a video; on the
// terms before the House streamed every station is one, so those pages
// carry no count rather than "Videos (0)".
const videoCount=d=>(d.stations||[]).filter(s=>s.video_id).length;
const reportCount=d=>(d.reports||[]).reduce((n,r)=>n+((r.reports||[]).length),0)
                     +(d.docket_reports||[]).length;

function renderReports(b,d,rsa){
  const recFor=(r,side)=>side==="Minority"
      ? (r.minority_recommendation||"") : (r.majority_recommendation||"");
  // What the chamber did between one report and the next, keyed on the report
  // it comes before. A bill sent back to a committee that has already reported
  // it comes out reported again, and without this the second report reads as
  // an unexplained repeat of the first -- which is what a committee reporting
  // twice looked like on the nine bills it happens to.
  const acts={};
  (d.report_actions||[]).forEach(a=>{(acts[a.before]=acts[a.before]||[]).push(a);});
  const between=key=>(acts[key]||[]).map(a=>
    `<p class="note" style="margin:0 0 16px">Between these reports the docket
      records, on ${esc(fdate(a.date))}: <em>${esc(a.text)}</em></p>`).join("");
  // The day the committee signed its report, where the docket states it; the
  // day the calendar carrying it was published, where it does not. Saying
  // which is the difference between a fact and a stand-in for one.
  const when=r=>!r.date?"":`<span class="secsub">${esc(fdate(r.date))}</span>`
      +(r.dated==="printed"?` <span class="note" style="font-size:11.5px">as printed</span>`:"");
  const cited=r=>{
    if(!r.cite)return "";
    // The House's source string IS the citation -- "House Calendar 51, 2025".
    // The Senate's reports come from the General Court's database and their
    // source names that, which is not what a reader wants beside a committee's
    // name; the docket's own citation for the same report is.
    const t=esc(r.body==="S"?r.cite:(r.source||r.cite));
    return r.cite_url?` · <a href="${esc(r.cite_url)}" rel="noopener">${t}</a>`
                     :` · ${t}`;
  };
  // "SENATE JUDICIARY COMMITTEE" -- whose report this is, as the heading
  // rather than as small print beside the date. A bill can be reported by
  // four different committees and the reader needs to know which one is
  // speaking before they read what it said.
  const head=(r,cmte,body)=>`<div class="rephead">
      ${[body,cmte].filter(Boolean).length
        ? `<h2>${esc([body,cmte].filter(Boolean).join(" "))} committee</h2>`:""}
      <div class="repmeta">${when(r)}<span class="note"
        style="font-size:12px">${cited(r)}</span></div></div>`;

  const written=(d.reports||[]).map(r=>{
    const divided=!!r.minority_recommendation;
    // The committee's vote is printed at the end of the report body in the
    // calendar, where it reads as a footnote to a paragraph of prose. It
    // belongs beside the label it is a vote on.
    //
    // Where the committee split, the two numbers are the two sides: the count
    // that carried the majority recommendation, and the count that did not.
    // Where one report was filed, neither number belongs to anybody else, so
    // the whole tally sits with it -- 19-0, or 18-1.
    const tally=(r.reports||[]).map(x=>x).find(x=>x.vote_yeas!=null);
    const committeeTally=e=>{
      if(e.vote_yeas==null&&!tally)return "";
      const y=e.vote_yeas!=null?e.vote_yeas:tally.vote_yeas;
      const nn=e.vote_nays!=null?e.vote_nays:tally.vote_nays;
      const full=`Committee vote ${y}–${nn}`;
      return `<span class="cvote" title="${full}">${
        divided?(e.side==="Minority"?nn:y):`${y}–${nn}`}</span>`;
    };
    const cmte=((r.reports||[])[0]||{}).committee||"";
    const blocks=(r.reports||[]).map(e=>{
      const rec=recFor(r,e.side);
      return `<div style="margin-bottom:20px">
        <div style="display:flex;gap:9px;align-items:baseline;flex-wrap:wrap">
          <span class="secsub">${esc(e.side)}</span>
          ${committeeTally(e)}
          ${rec?`<span class="cstat ${recColour(rec)}">${esc(rec)}</span>`:""}</div>
        <p style="font-size:12.5px;color:var(--ink-2);margin:3px 0 8px">${esc(e.author)}</p>
        ${e.amendment?`<p class="note" style="margin:0 0 7px">Amendment ${
          esc(e.amendment)}.</p>`:""}
        ${(e.text||"").trim()
          ? `<p style="font-family:var(--serif);font-size:16px;line-height:1.6;margin:0">${rsa(esc(e.text))}</p>`
          // 350 of the Senate's 1,446 reports carry no reasoning at all. That
          // is a fact about the report, not a gap in the site, and saying so
          // is better than an empty space under a heading.
          : `<p class="note" style="margin:0">This report records the
             recommendation and the vote, and gives no reasoning.</p>`}
        </div>`;}).join("");
    return between(r.date)+head(r,cmte,r.body==="S"?"Senate":"House")
      +(divided?`<p class="note">The committee split. Both reports are printed
        below in the committee's own words.</p>`:"")+blocks;}).join("");

  // Reports the docket records and this site has no written text for. Once the
  // Senate's own reports came out of the General Court's database, 964 of
  // these turned into written blocks above and what is left is the remainder:
  // a House report printed in a calendar not read in yet, or a Senate report
  // the database does not carry.
  const docket=(d.docket_reports||[]).map(r=>{
    const vote=r.vote_yeas!=null&&r.vote_nays!=null
      ? `<span class="cvote" title="Committee vote ${r.vote_yeas}–${r.vote_nays}"
          >${r.vote_yeas}–${r.vote_nays}</span>` : "";
    // The same three-part heading the written reports use -- who, by what vote,
    // for what motion. The Senate files one report and does not label it, and
    // leaving the label out left a bare "3-2" hanging where every block above
    // it reads "MAJORITY 10" or "COMMITTEE 17-0".
    const amd=r.amendment?`<p class="note" style="margin:0 0 7px">Amendment ${
      esc(r.amendment)}${r.new_title?", which also changes the bill’s title":""}.</p>`:"";
    return between(r.date)+head(r,r.committee,r.body==="S"?"Senate":"House")
      +`<div style="display:flex;gap:9px;align-items:baseline;flex-wrap:wrap;margin-bottom:6px">
        <span class="secsub">${esc(r.side||"Committee")}</span>${vote}
        <span class="cstat ${recColour(r.recommendation)}">${esc(r.recommendation)}</span></div>
      ${amd}
      <p class="note" style="margin:0 0 20px">${r.body==="S"
        ? "The written report for this one is not on the site; this is what the docket records of it."
        : "The calendar carrying this report has not been read into the site yet, so only what the docket states is shown."}</p>`;}).join("");

  return veto(d)+((written||docket)?written+docket
    :`<p class="note">No committee report on file. A report is recorded in the docket
      when a committee reports the bill out, and the reasoning behind it is printed
      in the House Calendar or filed with the Senate; neither has happened here yet.</p>`);
}

// WHY the governor vetoed it, which the docket does not record. Read into the
// House on the day and printed in that day's calendar under a heading of its
// own; the calendar is cited so a reader can check the words against the
// document they came from.
//
// Quoted in full rather than summarised. It is a short written statement
// published by its author, which is a different thing from a caption -- the
// site does not quote those because they garble bill numbers, and a garbled
// quotation with a citation on it is worse than none.
function veto(d){
  const v=d.veto_message;
  if(!v||!(v.text||[]).length)return "";
  const cite=v.source&&v.source.url
    ? `<a href="${esc(v.source.url)}" target="_blank" rel="noopener">${
        esc(v.source.name||"the House calendar")}</a>`
    : esc((v.source||{}).name||"the House calendar");
  return `<section class="vmsg">
    <h2 class="amdsec">The governor&rsquo;s veto message</h2>
    ${v.text.map(p=>`<p>${esc(p)}</p>`).join("")}
    <p class="vsig">${esc(v.governor||"")}${
      v.date?` <span class="secsub">${esc(fdate(v.date))}</span>`:""}</p>
    ${v.date?`<p class="note" style="margin:6px 0 0">The message carries its own
      date, which is the day the governor signed it. The docket records the day
      the veto reached the House, and on three of these the two are days
      apart.</p>`:""}
    <p class="src">Read into the House and printed in ${cite}. The docket
      records that a bill was vetoed and the day it happened; the reasons are
      only in the message.</p>
  </section>`;
}

// Sponsors, grouped by chamber with the originating one first. A House bill
// co-sponsored by two senators is a House bill, and reading the Reps first is
// reading it in the order it happened. Which chamber that is comes from the
// PRIME SPONSOR'S OWN SEAT, because that is what settles it for a concurrent
// resolution, where the bill number does not.
function renderSponsors(b,d){
  const spAll=d.sponsors||[];
  const spPrime=spAll.find(s=>s.prime)||spAll[0]||{};
  const chOf=s=>String(s.chamber||"").toUpperCase().slice(0,1);
  const origin=chOf(spPrime)||(/^S/i.test(b.id)?"S":"H");
  const CHNAME={H:"Representatives",S:"Senators"};
  // A sponsor's name links to that member's own page. It was the one place a
  // person was named on this site and could not be followed.
  const pill=pchip;
  const spBlock=ch=>{const l=spAll.filter(s=>chOf(s)===ch);return l.length
    ?`<h2 class="spgrp">${CHNAME[ch]} <span>${l.length}</span></h2>
      <div class="chosen">${l.map(pill).join(" ")}</div>`:"";};
  const spRest=spAll.filter(s=>!["H","S"].includes(chOf(s)));
  // A count per party, and nothing said about it. Sorted by party code, so the
  // order is fixed rather than a ranking by size.
  const pc={};
  spAll.forEach(s=>{const k=String(s.party||"").toUpperCase().slice(0,1);
    if(k)pc[k]=(pc[k]||0)+1;});
  const spParty=Object.keys(pc).sort().map(k=>
    `<span title="${esc(PARTY_NAME[k]||k)}">${pc[k]} ${esc(k)}</span>`).join(" \u00b7 ");
  const sp=spAll.length?`
    <p class="spcount">${spAll.length} sponsor${spAll.length===1?"":"s"}${
      spParty?` \u00b7 ${spParty}`:""}</p>
    ${spBlock(origin)}${spBlock(origin==="S"?"H":"S")}
    ${spRest.length?`<h2 class="spgrp">Chamber not on file <span>${spRest.length}</span></h2>
      <div class="chosen">${spRest.map(pill).join(" ")}</div>`:""}`:"";
  return `${sp||`<p class="note">No sponsors on file.</p>`}
      <p class="note" style="margin-top:12px">Prime sponsor in bold. From the
      General Court sponsor file.
      <a href="${esc(d.docket_url)}" target="_blank" rel="noopener">Full docket and bill text on gencourt</a></p>`;
}

// Amendments, in the order the docket took them up. A committee amendment
// is considered before any floor amendment, and where two touch the same
// section the later one governs -- so the sequence carries meaning, and it
// is shown as the record has it rather than grouped or sorted.
// The fiscal note, as the table the bill's own PDF prints. A figure sits
// under a year only where the row has one figure per year; where it has fewer
// the row spans, because which years the second figure covers is not stated
// and putting it under one of them would be inventing an answer.
function fiscalTable(f){
  if(!f)return "";
  const table=t=>{
    if(t.raw)return `<div class="fnraw">${t.caption?`<h4>${esc(t.caption)}</h4>`:""}
      ${t.raw.map(l=>`<p>${esc(l)}</p>`).join("")}</div>`;
    const n=(t.years||[]).length;
    return `<div class="fnwrap"><table class="fn">
      ${t.caption?`<caption>${esc(t.caption)}</caption>`:""}
      <thead><tr><th></th>${t.years.map(y=>
        `<th scope="col">${esc(y)}</th>`).join("")}</tr></thead>
      <tbody>${t.rows.map(r=>`<tr><th scope="row">${esc(r.label)}</th>${
        r.span
          ? `<td colspan="${n}">${esc(r.values.join(" \u00b7 "))}</td>`
          : r.values.map(v=>`<td>${esc(v)}</td>`).join("")
      }</tr>`).join("")}</tbody></table></div>
      ${t.footnote?`<p class="src">${esc(t.footnote)}</p>`:""}`;
  };
  return `<section class="fnsec"><h2 class="amdsec">Fiscal impact</h2>
    ${f.lead?`<p class="fnlead">${esc(f.lead)}</p>`:""}
    ${(f.tables||[]).map(table).join("")}
    <p class="src">Source: NH General Court</p></section>`;
}

function renderBillText(b,d,rsa){
  const brackets=(s)=>s.replace(/\[([^\]]{1,400})\]/g,
    (_,inner)=>`<del class="cut" title="removed by this amendment">${inner}</del>`);
  const amds=(d.amendments||[]).map(x=>{
    const who=x.mover||x.proposed_by||"";
    const state=x.adopted===true?"adopted":x.adopted===false?"rejected":"";
    return `<div class="amd">
      <div class="amdhead"><span class="amdn">${esc(x.num)}</span>
        <span class="amdk">${esc(x.kind||"Amendment")}</span>
        ${state?`<span class="cstat ${state==="adopted"?"s-law":"s-done"}">${state}</span>`:""}
        <span class="amdd">${x.date?esc(fdate(x.date)):""}${
          AVK[x.vote_kind]?` \u00b7 ${AVK[x.vote_kind]}`:""}</span></div>
      ${who?`<p class="amdby">${esc(who)}</p>`:""}
      ${(x.targets||[]).length?`<p class="amdt">Changes ${
        x.targets.map(v=>`<span class="tgt">${esc(v)}</span>`).join(" ")}</p>`:""}
      ${(x.supersedes||[]).length?`<p class="amdsup">Later than ${
        x.supersedes.map(s=>`${esc(s.num)} (${s.shared.map(esc).join(", ")})`).join(", ")
        }, so where they change the same thing this one governs.</p>`:""}
      ${x.text
        ? `<details class="amdtext"><summary>Read the amendment</summary>
             <p>${brackets(rsa(esc(x.text)))}</p>
             <p class="src">Text in ${"["}brackets] is being removed. Text being
               added is underlined in the original, and underlining is lost when
               a PDF is read as text, so additions are not marked here.${
               x.source?` From ${esc(x.source)}.`:""}</p></details>`
        : `<p class="note">The text is not in the calendars this site has read.
             It was moved on the date above and the docket records the outcome.</p>`}
    </div>`;}).join("");

  // AFTER brackets, which it uses. billLines built above brackets threw
  // "Cannot access 'brackets' before initialization" on every bill, so
  // renderDetail never returned and every card sat on "Loading..." with the
  // data already fetched and in hand. Both now live in this one short
  // function, eight lines apart, where the order is visible.
  //
  // The bill as the General Court publishes it. The version label is the most
  // important thing on it: "as introduced" and "as amended by the House" are
  // different laws, and a reader who misses which one they are looking at has
  // misread everything below. SEC and OUTLINE, which shape it, are module
  // constants now: they depend on nothing and were being recompiled per bill.
  const billLines=(txt)=>String(txt||"").split("\n")
    .flatMap(l=>l.split(OUTLINE)).map(raw=>{
    const line=raw.trim();
    if(!line)return "";
    const html=brackets(rsa(esc(line)));
    if(/^(?:Be it Enacted|That the following|Whereas\b|RESOLVED\b)/i.test(line))
      return `<p class="enact">${html}</p>`;
    const m=SEC.exec(line);
    if(m)return `<p class="sec"><b>${esc(m[1])}</b> ${html.slice(m[0].length)}</p>`;
    // A subparagraph indents under the section it belongs to; a new RSA
    // section number stands as a heading, which is how it is printed.
    if(/^(?:[IVXL]{1,5}\.|\([a-z]\))/.test(line))return `<p class="sub">${html}</p>`;
    if(/^\d{1,3}:\d+[-\w]*\s+[A-Z]/.test(line))return `<p class="rsahead">${html}</p>`;
    return `<p class="ln">${html}</p>`;
  }).join("");
  const bt=d.billtext;
  // Amendments belong with the text, not beside it. Each one is a step from
  // one version of the bill to the next, so they are shown as the sequence
  // that produced what is on screen rather than as a separate list to be
  // cross-referenced.
  const btBlock=bt?`
    <div class="btver"><span class="btv">${esc(bt.version||"Version not stated")}</span>
      ${(bt.in_text||[]).length?`<span class="btamd">includes ${
        bt.in_text.map(a=>esc(a.num)).join(", ")}</span>`:""}</div>
    ${/* The analysis is the first thing on the Summary tab now. It was
           only here, and this block only renders on a focused bill, so a
           card expanded in a list never showed it. */""}
    ${fiscalTable(bt.fiscal)}
    <div class="bttext"><h3>The bill</h3>
      <p class="src">Text in ${"["}brackets] is being removed from current law.
        Text being added is printed in bold italics in the original, and that
        formatting is lost when the page is read as text, so additions are not
        marked here.</p>
      <div class="billbody">${billLines(bt.body||"")}</div></div>
    ${amds?`<div class="amdsteps"><h3 class="amdsec">How it got here</h3>
      <p class="note">Each amendment is a step from one version to the next, in
        the order the docket took them up. A committee amendment is considered
        before any floor amendment, and where two change the same section the
        later one governs.</p>${amds}</div>`:""}`
   :(amds?`<p class="note">The text of this bill has not been read into this
       site yet, but the amendments to it have. The Documents tab links to the
       text on the General Court's own site.</p>
       <div class="amdsteps"><h3 class="amdsec">How it got here</h3>${amds}</div>`
     :`<p class="note">The text of this bill has not been read into this site
       yet. The Documents tab links to it on the General Court's own site.</p>`);
  // New Hampshire prints text being REMOVED in square brackets. Text being
  // added is underlined, and underlining does not survive a PDF being read as
  // text -- so deletions can be marked here and additions cannot. That
  // asymmetry is stated rather than left for a reader to discover, because
  // marked deletions invite the assumption that everything unmarked is
  // unchanged, and half of it is new.
  return btBlock;
}

function renderDocuments(b,d){
  // The status fields the site quotes, with the documents it quotes them
  // alongside. This is the provenance tab, and the table is provenance: nine
  // values taken from the General Court's own status page rather than worked
  // out from anything.
  // factsTable used to open this tab with the status page's own fields --
  // status, the date introduced, the committee code. Every one of them is
  // already on the summary, in a sentence, above the tab strip.
  return ((d.documents||[]).length
      ? `<p class="note">Everything below is published by the General Court. This
         site quotes and summarises these; they are the record itself.</p>
         <ul class="docs">${d.documents.map(x=>`<li class="doc doc-${esc(x.kind)}">
           <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>
           <span>${DOCWHAT[x.kind]||""}</span></li>`).join("")}</ul>`
      : `<p class="note">No official documents on file for this bill yet. The
         bill text and docket links come from the General Court's status page,
         which is fetched separately.</p>`);
}

// The tabs, and one call per pane. Everything this reads is either a
// parameter or the return value of a call made on the line that uses it,
// so there is no declaration here whose order could be got wrong.
// ============================================================== versions ==
//
// WHAT EACH AMENDMENT CHANGED. A bill is reprinted at every stage and the
// changes are usually small -- HB650's first amendment turned one word,
// "unencumbered" into "unobligated" -- which is exactly what nobody finds by
// reading two seven-thousand-character documents side by side.
//
// Three files rather than one, and each fetched only when it is picked: the
// index (median 1.1 KB), a version's text, and one comparison's detail. One
// file held all of it at first and HB2, the budget with 54 versions, came to
// 11.4 MB.
const VERS = {};                       // bill -> the index, once fetched
const VTEXT = {};                      // url -> text, once fetched
const VPICK = {};                      // bill -> which version is showing
const VMODE = {};                      // bill -> "text" or "changes"

function verKey(b){ return `${b.year||yearOf(b.id)}/${b.id}`; }

function renderVersions(b,d){
  const key=verKey(b), ix=VERS[key];
  if(!ix)return `<p class="spin">Loading the versions…</p>`;
  if(ix._error)return `<p class="note">The versions of this bill could not be
    loaded. ${esc(ix._error)}</p>`;
  const vs=ix.versions||[], amds=ix.amendments||[];
  // THE CURRENT VERSION BY DEFAULT, which is the last one the record has.
  if(VPICK[key]===undefined)VPICK[key]=vs.length?vs.length-1:0;
  const mode=VMODE[key]||"changes";
  const i=Math.min(VPICK[key],Math.max(0,vs.length-1));

  const picker=vs.length?`<div class="vpick" role="tablist" aria-label="Versions of this bill's text">${
    vs.map((v,j)=>`<button class="vbtn${j===i?" sel":""}" data-ver="${esc(key)}|${j}"
      aria-current="${j===i?"true":"false"}">${esc(v.title)}<i>${
      esc((v.date||"").split(" ")[0])}</i></button>`).join("")}</div>`:"";

  // The step that produced the version being shown, if there is one.
  const step=(ix.steps||[]).find(s=>s.to===i);
  const toggle=step?`<div class="vmode">
    <button class="vtog${mode==="changes"?" sel":""}" data-vmode="${esc(key)}|changes">What changed</button>
    <button class="vtog${mode==="text"?" sel":""}" data-vmode="${esc(key)}|text">Full text</button>
    <span class="vcount">+${step.added} \u2212${step.removed} words against
      ${esc((vs[step.from]||{}).title||"the version before")}</span></div>`
    : `<p class="note">This is the first version the record has, so there is
       nothing before it to compare.</p>`;

  let body="";
  if(step&&mode==="changes"){
    const runs=VTEXT[step.runs_url];
    body=runs===undefined?`<p class="spin">Loading what changed…</p>`
      :Array.isArray(runs)?`<div class="vdiff">${runs.map(([op,txt])=>
          op==="~"?`<span class="vskip">${esc(txt)} words unchanged</span>`
          :op==="+"?`<ins>${esc(txt)}</ins>`
          :op==="-"?`<del>${esc(txt)}</del>`
          :`<span>${esc(txt)}</span>`).join("")}</div>`
      :`<p class="note">That comparison could not be loaded.</p>`;
  }else{
    const u=(vs[i]||{}).text_url;
    const txt=u?VTEXT[u]:null;
    body=txt===undefined?`<p class="spin">Loading the text…</p>`
      :typeof txt==="string"?`<pre class="vtext">${esc(txt)}</pre>`
      :`<p class="note">That text could not be loaded.</p>`;
  }

  const amdblock=amds.length?`<h2 class="amdsec">The amendments themselves</h2>
    <p class="note">The General Court publishes the text of each amendment as
    its own document, naming the statute it amends and what it replaces. These
    are those, not versions of the bill.</p>
    <ul class="vamds">${amds.map((a,j)=>`<li><button class="link"
      data-vamd="${esc(key)}|${j}">Amendment of ${esc((a.date||"").split(" ")[0])}</button>
      <span class="dim">${(a.chars||0).toLocaleString()} characters</span>${
      VTEXT[a.text_url]!==undefined
        ? `<pre class="vtext">${esc(String(VTEXT[a.text_url]))}</pre>` : ""}</li>`
      ).join("")}</ul>`:"";

  return picker+toggle+body+amdblock;
}

// Fetch whatever the current view needs and redraw when it lands. Everything
// already here is used from the cache; nothing is asked for twice.
function needVersions(b){
  const key=verKey(b);
  if(VERS[key]===undefined){
    VERS[key]=null;
    fetch(DATA(`versions/${key}.json`))
      .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
      .then(j=>{VERS[key]=j;repaint();wantVersionBody(b);})
      .catch(e=>{VERS[key]={_error:e.message||String(e)};repaint();});
    return;
  }
  if(VERS[key])wantVersionBody(b);
}

function wantVersionBody(b){
  const key=verKey(b), ix=VERS[key];
  if(!ix||ix._error)return;
  const i=VPICK[key]===undefined?(ix.versions||[]).length-1:VPICK[key];
  const mode=VMODE[key]||"changes";
  const step=(ix.steps||[]).find(s=>s.to===i);
  const url=(step&&mode==="changes")?step.runs_url
    :((ix.versions||[])[i]||{}).text_url;
  if(!url||VTEXT[url]!==undefined)return;
  VTEXT[url]=undefined;
  const json=url.endsWith(".json");
  fetch(DATA(url.replace(/^\//,"")))
    .then(r=>r.ok?(json?r.json():r.text()):Promise.reject(new Error("HTTP "+r.status)))
    .then(x=>{VTEXT[url]=json?(x.runs||[]):x;repaint();})
    .catch(()=>{VTEXT[url]=null;repaint();});
}

function renderDetail(b,d){
  const rsa=makeRsa(d);
  // Below the tabs, outside every pane, and only in the expanded view. The
  // bill text used to be assembled into a const above this template while
  // its own dependencies were declared below it, which threw the moment a
  // bill was focused -- a refresh on a bill page reporting that its detail
  // would not load when the file had arrived fine. It is a call now, made
  // where it is used, so there is nothing left to order wrongly.
  const btsec=(focused===b.id&&((d.billtext&&d.billtext.body)
    ||(d.amendments||[]).length))
    ? `<section class="btsec"><h2 class="amdsec">Bill text</h2>
        <p class="btwhat">The bill and its amendments, as the General Court publishes them. Everything above is this site’s account of the record; this is the document.</p>${
        renderBillText(b,d,rsa)}</section>`
    : "";

  // BILL TEXT SITS SECOND, and the data-t numbers are deliberately NOT
  // renumbered. They are the tab's identity: PAGE_TAB holds one, the pane
  // carries the matching one, and a bookmark or a back button restores by it.
  // Renumbering to match the new order would silently repoint every saved
  // tab -- somebody's link to the Votes tab would open Bill Text. So the
  // order here is the DOM order, which is what a reader and the keyboard both
  // follow, and 6 stays 6.
  const btTab=(d.nver||0)>1||(d.namd||0)
    ? `<button class="tab" role="tab" id="tab_${b.id}_6" aria-controls="pane_${b.id}_6"
        aria-selected="false" data-t="6">Bill Text${d.nver>1?` (${d.nver})`:""}</button>`
    : "";
  const btPane=(d.nver||0)>1||(d.namd||0)
    ? `<div class="pane" role="tabpanel" id="pane_${b.id}_6" aria-labelledby="tab_${b.id}_6"
        tabindex="0" data-t="6" hidden>${renderVersions(b,d)}</div>`
    : "";

  return `<div class="tabs" role="tablist">
    <button class="tab" role="tab" id="tab_${b.id}_0" aria-controls="pane_${b.id}_0" aria-selected="true" data-t="0">Summary</button>
    ${btTab}
    <button class="tab" role="tab" id="tab_${b.id}_1" aria-controls="pane_${b.id}_1" aria-selected="false" data-t="1">Votes${
        // What the pane draws, not the index row's count. b.nrc is the roll
        // calls that are not procedural; the pane draws d.rollcalls, which
        // adds the docket's voice and division votes. The two disagreed on
        // 2,011 of the current term's 2,234 bills -- mostly bills whose only
        // votes were voice votes, which showed "Votes" with nothing beside
        // it and 3 sections beneath.
        (d.rollcalls||[]).length?` (${d.rollcalls.length})`:""}</button>
    <button class="tab" role="tab" id="tab_${b.id}_2" aria-controls="pane_${b.id}_2" aria-selected="false" data-t="2">Videos${videoCount(d)?` (${videoCount(d)})`:""}</button>
    <button class="tab" role="tab" id="tab_${b.id}_3" aria-controls="pane_${b.id}_3" aria-selected="false" data-t="3">Reports${
      reportCount(d)?` (${reportCount(d)})`:""}</button>
    <button class="tab" role="tab" id="tab_${b.id}_4" aria-controls="pane_${b.id}_4" aria-selected="false" data-t="4">Sponsors${(d.sponsors||[]).length?` (${(d.sponsors||[]).length})`:""}</button>

    <button class="tab" role="tab" id="tab_${b.id}_5" aria-controls="pane_${b.id}_5"
      aria-selected="false" data-t="5">Documents${
        (d.documents||[]).length?` (${d.documents.length})`:""}</button></div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_0" aria-labelledby="tab_${b.id}_0" tabindex="0" data-t="0">${renderSummary(b,d,rsa)}</div>
    ${/* ONLY WHERE THERE IS SOMETHING TO SHOW. 1,149 of 2,234 bills have a
          second version; a tab on the other 1,085 would say "there is one
          version" and fetch a file that is not there. nver comes from the
          manifest build_bill_versions.py writes. */ btPane}
    <div class="pane" role="tabpanel" id="pane_${b.id}_1" aria-labelledby="tab_${b.id}_1" tabindex="0" data-t="1" hidden>${paneNote("votes")}${renderVotes(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_2" aria-labelledby="tab_${b.id}_2" tabindex="0" data-t="2" hidden>${paneNote("hearings")}${renderHearings(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_3" aria-labelledby="tab_${b.id}_3" tabindex="0" data-t="3" hidden>${paneNote("reports")}${renderReports(b,d,rsa)}</div>


    <div class="pane" role="tabpanel" id="pane_${b.id}_4" aria-labelledby="tab_${b.id}_4" tabindex="0" data-t="4" hidden>${renderSponsors(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_5" aria-labelledby="tab_${b.id}_5"
      tabindex="0" data-t="5" hidden>${renderDocuments(b,d)}</div>${btsec}`;
}

// ===================================================== member and committee ==
//
// Two more things a page can be. A bill's page is this app with one bill open;
// a legislator's and a committee's are the same idea, so the cards, the tabs
// and the timestamps are the ones the bill view already draws rather than a
// second set that drifts from them.
//
// Each is told which record it is by a global the shell page sets, for the
// reason GR_BILL exists: the address already names it, and putting it in the
// hash as well would show it twice.

let PAGE = null;          // {kind:"member"|"committee", data:{...}}
let PAGE_TAB = 0;
// home.json's `upcoming`, once, for the committee page's own calendar.
// null while unasked, [] once asked and empty -- the two are not the same
// thing and the page must not say "nothing is scheduled" before it knows.
let UPCOMING = null;

// Redraw whatever is on screen. The bill search and a record page are two
// renderers, and the controls INSIDE an expanded bill card -- the segment
// picker, the routine-lines toggle, the full-text toggle -- are shared by
// both. Those called render() unconditionally, which on a committee's page
// drew four hundred bill cards over the committee.
const repaint=()=>PAGE?renderPage():render();

// The term a record page is showing. One control for the whole record rather
// than one per tab: a reader looking at 2023-2024 wants that term's bills AND
// that term's sessions, and choosing the term on one tab then finding the
// other back on the current term is the page disagreeing with itself.
const pageTerm=()=>{
  const ts=(PAGE&&PAGE.terms)||[];
  return PAGE&&PAGE.term&&ts.includes(PAGE.term)?PAGE.term:(ts[0]||"");
};
// "2026" -> "2025-2026". A vote records the year it was cast and not the term,
// and the term is what every other list on the page is keyed by.
const termOfYear=y=>{
  const n=parseInt(y,10);
  if(!n)return "";
  return ((META&&META.terms)||[]).find(t=>{
    const [a,b]=String(t).split("-").map(Number);
    return a&&b&&n>=a&&n<=b;})||"";
};

// A committee named on a bill, as a link to its page where there is one.
// 3,967 mentions across the site were plain text, so the reader who wanted
// "what else did this committee do" had nowhere to click.
function cmteLink(name){
  const code=(META&&META.committee_codes||{})[name];
  return code?`<a href="committee/${esc(code)}.html">${esc(name)}</a>`:esc(name);
}

// ONE card, drawn by the search list and by both record pages.
//
// A member's page used to draw its own flatter card with no body, so the same
// bill was two different objects depending on which page you reached it from
// and the detail a reader wanted was a page load away. Sharing the markup is
// also the only way the two stay the same as this card changes.
// The four stops a bill passes, and what happened at each. b.passage is
// "HSGL", one character a stop: p passed, h here now, x stopped here, - never
// reached.
//
// Every state has its own SHAPE as well as its own weight -- filled, ringed,
// crossed, empty -- because this is the site's one piece of ornament and it
// would be a poor one if it depended on telling two greens apart. The stops
// are labelled, so it is read rather than decoded.
//
// Nothing here calls an outcome good or bad. A bill dying is an outcome, not
// a failure, so a stop the bill did not get past is crossed in the same ink
// as one it passed, not in red.
// The four stops a bill passes, in the order IT travelled them. b.passage is
// five characters: the chamber it started in, then one a stop -- p passed,
// h here now, x stopped here, - never reached.
//
// A stop carries a green check where the bill got through and a red cross
// where it stopped, so the state is legible without knowing a key. The glyph
// says it and the colour agrees; neither carries it alone.
const CHNAME2={H:"House",S:"Senate"};
const RAILMARK={p:"\u2713", x:"\u2715", h:"", "-":""};
const RAILSAY={p:"passed", h:"is here now", x:"stopped here",
               "-":"never reached"};
function rail(b){
  const p=b.passage||"";
  if(!CHNAME2[p[0]])return "";
  const other=p[0]==="H"?"S":"H";
  const st=p.slice(1);
  // A resolution belongs to one chamber and has two stops: that chamber, and
  // whether it was adopted. Four stops drew it against a Senate it was never
  // going to see and a Law it could never become.
  const stops = st.length===2 ? [CHNAME2[p[0]],"Adopted"]
              : st.length===4 ? [CHNAME2[p[0]],CHNAME2[other],"Governor","Law"]
              : null;
  if(!stops)return "";
  const said=stops.map((name,i)=>`${name}: ${RAILSAY[st[i]]||"not known"}`)
    .join("; ");
  return `<span class="rail" role="img" aria-label="${esc(said)}"
    title="${esc(said)}">${stops.map((name,i)=>
      `<span class="stop s-${esc(st[i]==="-"?"o":st[i])}"
        ><b>${RAILMARK[st[i]]||""}</b><i>${esc(name)}</i></span>`
    ).join("")}</span>`;
}

function cardHtml(b,focus){
  const open=openCards.has(b.id);
  const y=b.year||(b.term?String(b.term).slice(0,4):"");
  return `<article class="card ${open?'open':''}${focus?' focus':''}" data-id="${b.id}">
      ${focus?"":`<a class="detail" href="bill/${esc(String(y))}/${esc(b.id.toLowerCase())}.html"
        title="${esc(b.n)} on its own page: its own address, and a link worth sharing"
        aria-label="Open the standalone page for ${esc(b.n)}">&#8599;</a>`}
      <button class="chead" aria-expanded="${open}">
        <div class="crow"><span class="cnum">${esc(b.n)} (${esc(String(y))})</span>
        <span class="cyear">${b.carried
          ?` <span class="chip" title="Filed one year, acted on in the next — retained in committee or sent to interim study">carried over</span>`:""}</span>
        <span class="cstat ${KIND[b.kind]||""}">${esc(b.status||"")}</span></div>
        <div class="ctitle">${esc(b.title)}</div>
        <div class="cmeta">${esc(b.sponsor_label||b.sponsor||"")}${
          (b.committees||[b.committee]).filter(Boolean).map(c=>" · "+cmteLink(c)).join("")}${b.topic?" · "+esc(b.topic):""}</div>
        ${rail(b)}
      </button>
      <div class="cbody" ${open?"":"hidden"}>${
        open?(detail[dkey(b.id)]?renderDetail(b,detail[dkey(b.id)]):`<p class="spin">Loading…</p>`):""}</div>
    </article>`;
}

// The tabs inside an expanded card are set after its HTML is in the document,
// because every tab's pane is written and only one is shown. Both renderers
// have to do it, so neither owns it.
// Which analyses the reader has opened out. Keyed on the bill, so opening
// one and then touching any other control does not shut it again.
const anOpen=new Set();

// A box is clamped unless the reader opened it, and gets a button only if it
// actually overflows -- which is a measurement, not a guess: the same 300
// characters are three lines on a desktop and eight on a phone.
function clampAnalysis(){
  document.querySelectorAll(".card").forEach(card=>{
    const id=card.dataset.id, box=card.querySelector(".anbox");
    if(!box)return;
    const text=box.querySelector(".antext");
    const open=anOpen.has(id);
    box.classList.toggle("clamped",!open);
    const over=text.scrollHeight>text.clientHeight+2;
    let btn=box.querySelector(".anmore");
    if(over||open){
      if(!btn){
        btn=document.createElement("button");
        btn.className="anmore";
        btn.type="button";
        box.insertBefore(btn,box.querySelector(".src"));
      }
      btn.textContent=open?"Show less":"Show more";
      btn.setAttribute("aria-expanded",String(open));
      btn.dataset.an=id;
    }else if(btn){
      btn.remove();
    }
  });
}

function syncCards(ids){
  ids.forEach(id=>{
    const c=document.querySelector(`.card[data-id="${id}"]`),t=openTab[id]||"0";
    if(!c||!detail[dkey(id)])return;
    c.querySelectorAll(".tab").forEach(x=>x.setAttribute("aria-selected",x.dataset.t===t));
    c.querySelectorAll(".pane").forEach(p=>p.hidden=p.dataset.t!==t);
  });
  // After the panes are shown, because a clamped box inside a hidden pane
  // measures zero and would never get its button.
  clampAnalysis();
}

// A record page names a bill by number, term and title and nothing else. The
// card wants its status, its sponsor and its committees, so the index row is
// looked up rather than reconstructed -- and the TERM is part of the lookup,
// because a bill number names one bill in each biennium.
function idxRow(b){
  const id=String(b.id||b.bill||"").toUpperCase();
  const t=b.term||"";
  return IDX.find(x=>x.id===id&&(!t||x.term===t))
      || (b.year?IDX.find(x=>x.id===id&&String(x.year)===String(b.year)):null)
      || {id,n:b.n||id,title:b.title||"",year:b.year||"",term:t,
          status:b.status||"",kind:b.kind||"",sponsor:"",committees:[]};
}

// The bills of one tab, as cards, with the outcome filter above them.
function billPane(rows,note){
  const statuses=[...new Set(rows.map(b=>b.status).filter(Boolean))].sort();
  const shown=rows.filter(b=>!PAGE.status||b.status===PAGE.status);
  return `<div class="bfilt"><label>Status
      <select data-pf="status"><option value="">Any</option>
      ${statuses.map(x=>`<option value="${esc(x)}"${x===PAGE.status?" selected":""}>${
        esc(x)}</option>`).join("")}</select></label></div>
    <p class="src">${note(shown.length)}</p>
    <div class="cards">${shown.map(b=>cardHtml(b,false)).join("")}</div>`;
}

// The term, above the tabs, because it governs all of them.
function termControl(){
  const ts=(PAGE&&PAGE.terms)||[],t=pageTerm();
  if(ts.length<2)return "";
  return `<div class="bfilt pterm"><label>Term
    <select data-pf="term">${ts.map(x=>
      `<option value="${esc(x)}"${x===t?" selected":""}>${esc(x)}</option>`
    ).join("")}</select></label></div>`;
}

function tabStrip(tabs){
  return `<div class="tabs" role="tablist">${tabs.map((t,i)=>
    `<button class="tab" role="tab" data-pt="${i}" aria-selected="${
      i===PAGE_TAB}">${esc(t[0])}${t[1]?` (${t[1].toLocaleString()})`:""}</button>`
  ).join("")}</div>`;
}

// ONE CHIP FOR A PERSON, wherever they appear. A committee's members were
// drawn in party colour and a bill's sponsors were not: the sponsor pill was
// pine green for everyone, so the same member read as one party on a
// committee page and as no party on a bill. Prime sponsorship stays bold and
// a committee role stays in the corner; nothing else differs between them.
//
// The party comes from party_code where the roster supplied one and from the
// first letter of party where only the word is there, because the sponsor
// records carry "Republican" and the roster carries "R".
const pchip=m=>{
  const code=String(m.party_code||m.party||"").toUpperCase().slice(0,1)||"X";
  const who=esc(m.display_full||m.label||m.name||"");
  const inner=m.prime?`<b>${who}</b>`:who;
  return `<span class="mchip p-${esc(code)}">${
    m.slug?`<a href="legislator/${esc(m.slug)}.html">${inner}</a>`:inner}${
    m.role&&m.role!=="Member"?` <i>${esc(m.role)}</i>`:""}</span>`;};
const mchip=pchip;

// ---------------------------------------------------------------- member ---
function renderMemberHead(m){
  const towns = m.towns||[];
  return `<div class="phead">
    <h1>${esc(m.display_full||m.display||m.name||"")}</h1>
    <p class="pmeta">${esc(m.chamber==="S"?"State Senate":"House of Representatives")}${
      m.district?` &middot; District ${esc(m.district)}`:""}${
      m.county?` &middot; ${esc(m.county)} County`:""}</p>
    ${towns.length?`<p class="ptowns"><b>Represents</b> ${
      towns.map(t=>esc(t)).join(" &middot; ")}</p>`:
      `<p class="ptowns note">The towns in this district are not on file.</p>`}
    ${(m.committees||[]).length?`<p class="pcmte"><b>Committees</b> ${
      m.committees.map(c=>cmteLink(
        (m.chamber==="S"?"Senate ":"House ")+c)).join(" &middot; ")}</p>`:""}
    ${m.email?`<p class="pmeta"><a href="mailto:${esc(m.email)}">${esc(m.email)}</a></p>`:""}
  </div>`;
}

const memberBills=(m,prime)=>(m.sponsored||[])
  .filter(b=>!!b.prime===prime)
  .filter(b=>!pageTerm()||b.term===pageTerm())
  .map(idxRow);

function renderMemberBills(m, prime){
  const rows=memberBills(m,prime);
  const t=pageTerm();
  if(!rows.length)return `<p class="src">No bills ${prime?"prime sponsored"
    :"co-sponsored"} in the ${esc(t)} term.</p>`;
  return billPane(rows,n=>`${n.toLocaleString()} bill${n===1?"":"s"}${
    prime?" prime sponsored":" co-sponsored"} in ${esc(t)}. Sponsoring a bill is
    putting a name to it, which is not the same as voting for it and is not
    counted as one here.`);
}

// THE TERM A VOTE BELONGS TO IS THE ONE IT WAS CAST IN. This read the
// bill's FILING year, which about three votes in every hundred do not have
// -- a call of the roll or a rules suspension is recorded against no bill --
// and a row with no year passed every term's filter. So a procedural vote
// taken in August 2026 was listed among the same member's 2023-2024 votes,
// and counted in that term's total. The roll call's own year is the first
// field of its key. Checked across 55,522 votes: no vote's roll call year
// and bill year fall in different terms, so nothing else moves.
//
// A row with neither is still shown rather than silently dropped.
const voteYear=x=>x.y||String(x.k||"").split("-")[0];
const memberVotes=m=>(m.votes||[]).filter(x=>{
  const y=voteYear(x);
  return !pageTerm()||!y||termOfYear(y)===pageTerm();});

// WHAT THE VOTE DECIDED, not only how they voted. This tab listed 1,081 rows
// of "HB2026 / Veto Override / Yea" on one member's page: the record's own
// abbreviations, no outcome, and no way to see when somebody had broken with
// their own party. All three answers are in one shared file, fetched the
// first time this tab is drawn -- the same 1,504 roll calls describe all 406
// members, so a copy inside each member's own file would add over a hundred
// megabytes to the site for facts that are identical in every copy.
//
// The bill's TITLE is not in that file: this page already has the term's bill
// index loaded, because the sponsored tabs are drawn from it, so the title is
// looked up there rather than shipped twice.
let RCX=null, RCX_ERR="";
function needRollcalls(){
  if(RCX)return;
  RCX={};                     // claimed, so a redraw does not fetch it twice
  fetch(DATA("rollcalls_index.json"))
    .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
    .then(j=>{RCX=j;renderPage();})
    .catch(e=>{RCX_ERR=e.message||String(e);renderPage();});
}

// Which way a party went on one roll call, where it went a way at all. Five
// members is the floor: a party of two has no majority worth naming, and an
// even split has no side. Both come back blank rather than as a coin toss,
// and only Yea and Nay are counted -- a member who did not vote did not take
// a side, and counting an absence as agreement would be an invention.
const PARTY_FLOOR=5;
function partySide(rc,code){
  const c=rc&&rc.s&&rc.s[code];
  if(!c)return "";
  const yea=c[0]||0, nay=c[1]||0;
  if(yea+nay<PARTY_FLOOR||yea===nay)return "";
  return yea>nay?"Yea":"Nay";
}

// Whether this member took the side most of their own party took. It is a
// fact about one vote, and the count of them below is a count -- neither is
// turned into a percentage, a rating or a rank. Breaking with your party is
// not a virtue or a failing here; it is a thing that happened, and a reader
// who wants to know how often can see the number and the denominator.
function partyMark(m,x,rc){
  const code=String(m.party_code||m.party||"").toUpperCase().slice(0,1);
  if(code==="X"||!PARTY_NAME[code])return null;
  const side=partySide(rc,code), mine=String(x.v||"");
  if(!side||(mine!=="Yea"&&mine!=="Nay"))return null;
  return {agreed:mine===side, code, word:PARTY_NAME[code]+"s"};
}

// How many are drawn before the reader asks for more. The old table stopped
// dead at 600 with a line saying so and no way to see the 481 after it.
const VOTES_SHOWN=200;

function renderMemberVotes(m){
  const v=memberVotes(m);
  const t=pageTerm();
  if(!v.length)return `<p class="src">No recorded roll call votes in the
    ${esc(t)} term. Voice and division votes leave no record of individual
    members, so a member can have taken part in many votes and appear in none
    of them.</p>`;
  needRollcalls();

  // Resolved once per row: what the roll call decided, the bill's title from
  // the index this page already holds, and where the member stood in their
  // own party.
  const all=v.map(x=>{
    const rc=(RCX||{})[x.k]||null;
    return {x, rc, mark:partyMark(m,x,rc),
            b:(x.b&&x.y)?idxRow({id:x.b,year:x.y,term:termOfYear(x.y)}):null};
  });

  const q=(PAGE.vfilter||"").toLowerCase(), pf=PAGE.vparty||"";
  const rows=all.filter(r=>(!q||String(r.x.v||"").toLowerCase()===q)
    &&(!pf||(r.mark&&(pf==="with")===r.mark.agreed)));
  const tally={};
  v.forEach(x=>{tally[x.v]=(tally[x.v]||0)+1;});

  // The denominator is the roll calls where their party actually took a side,
  // not every roll call: on the rest there was nothing to break with.
  const marked=all.filter(r=>r.mark);
  const broke=marked.filter(r=>!r.mark.agreed).length;
  const pname=PARTY_NAME[String(m.party_code||m.party||"")
    .toUpperCase().slice(0,1)]||"";

  const cap=PAGE.vshow||VOTES_SHOWN;
  const shown=rows.slice(0,cap);
  const left=rows.length-shown.length;

  return `<div class="bfilt"><label>Vote
      <select data-pf="vfilter"><option value="">Any</option>
      ${Object.keys(tally).sort().map(k=>`<option value="${esc(k.toLowerCase())}"${
        q===k.toLowerCase()?" selected":""}>${esc(k)} (${tally[k]})</option>`).join("")}
      </select></label>${marked.length?`<label>Their party
      <select data-pf="vparty"><option value="">Any</option>
        <option value="with"${pf==="with"?" selected":""}>Voted with ${
          esc(pname)}s (${(marked.length-broke).toLocaleString()})</option>
        <option value="against"${pf==="against"?" selected":""}>Voted against ${
          esc(pname)}s (${broke.toLocaleString()})</option>
      </select></label>`:""}</div>
    <p class="src">${rows.length.toLocaleString()} of ${v.length.toLocaleString()}
      recorded votes in ${esc(t)}, newest first. Every roll call this member is
      recorded in, as it was cast and on what. Nothing here is rated or
      scored.${marked.length?` On the ${marked.length.toLocaleString()} where
      ${esc(pname)}s took a side, this member took the other one
      ${broke.toLocaleString()} time${broke===1?"":"s"}.`:""}</p>
    ${RCX_ERR?`<p class="note">What each vote decided could not be loaded, so
      the outcomes and the party comparison are missing from the rows below.
      The votes themselves are the member's own record and are unaffected.
      <code>${esc(RCX_ERR)}</code></p>`:""}
    <table class="votes vfull"><thead><tr><th>Date</th>
      <th>What the vote was on</th><th>Their vote</th><th>Outcome</th>
      </tr></thead><tbody>${shown.map(r=>voteRow(r)).join("")}
      </tbody></table>
    ${left?`<p class="src"><button type="button" class="link" data-vmore="1"
      >Show ${Math.min(VOTES_SHOWN,left).toLocaleString()} more</button> &mdash;
      ${left.toLocaleString()} of ${rows.length.toLocaleString()} not yet
      shown.</p>`:""}`;
}

// One row. data-l carries the column's name so the same markup can stack into
// labelled blocks on a phone instead of scrolling sideways, which on a civic
// site reads as "this page was not meant for you".
function voteRow(r){
  const x=r.x, rc=r.rc, b=r.b;
  // The record's own word for the question and the plain-English one are both
  // kept: "pass the bill with changes" is what a reader needs, and "OTPA" is
  // what they will see on every other page of the General Court's own site.
  const plain=(rc&&rc.q)||"", raw=x.q||"";
  const question=plain
    ? `${esc(plain)}${raw&&raw.toLowerCase()!==plain.toLowerCase()
        ?` <span class="dim">(${esc(raw)})</span>`:""}`
    : esc(raw);
  const tallies=rc&&rc.y!=null&&rc.n!=null
    ? ` <i>${rc.y}–${rc.n}</i>`:"";
  return `<tr>
    <td class="d" data-l="Date">${esc(x.d||"")}</td>
    <td class="b" data-l="On">${x.b&&x.y
      ? `<a href="bill/${esc(String(x.y))}/${esc(String(x.b).toLowerCase())
        }.html">${esc((b&&b.n)||x.b)}</a>`
      : x.b ? esc(x.b)
      // A procedural vote -- a call of the roll, a rules suspension -- is
      // recorded against no bill. It used to render an empty cell wrapped in
      // a link to /bill//.html.
      : `<span class="none">no bill</span>`}${
      b&&b.title?`<span class="vt">${esc(b.title)}</span>`:""}
      <span class="vq">${question}</span></td>
    <td class="v" data-l="Their vote"><span class="vcast v-${
      esc(String(x.v||"").slice(0,3).toLowerCase())}">${esc(x.v||"")}</span>${
      r.mark?`<i class="pm${r.mark.agreed?"":" broke"}">${
        r.mark.agreed?"with":"against"} ${esc(r.mark.word)}</i>`:""}</td>
    <td class="o" data-l="Outcome">${rc
      ? `<span class="${rc.p?"pass":"fail"}">${rc.p?"Adopted":"Failed"}</span>${
          tallies}${rc.tn?`<i class="thr">${esc(rc.tn)}</i>`:""}`
      : `<span class="dim">&mdash;</span>`}</td></tr>`;
}

function renderMember(m){
  const tabs=[["Prime sponsored",memberBills(m,true).length],
              ["Co-sponsored",memberBills(m,false).length],
              ["Votes",memberVotes(m).length]];
  const body=[()=>renderMemberBills(m,true),()=>renderMemberBills(m,false),
              ()=>renderMemberVotes(m)][PAGE_TAB]||(()=>"");
  return renderMemberHead(m) + termControl() + tabStrip(tabs)
    + `<div class="pane" role="tabpanel" tabindex="0">${body()}</div>`;
}

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

function renderCommitteeHead(c){
  const officers=(c.officers||[]).filter(o=>o.name);
  const staff=[["Committee aide",c.aide],["Researcher",c.researcher],
               ["Room",c.room],["Phone",c.phone]].filter(x=>x[1]);
  const members=c.members||[];
  const rule=c.purpose||null;
  const dl=(cls,rows)=>rows.length?`<dl class="${cls}">${rows.map(
    ([k,v])=>`<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>`:"";
  return `<div class="phead">
    <h1>${esc(c.name||"")}</h1>
    <p class="pmeta">${esc(c.chamber==="S"?"State Senate":"House of Representatives")}</p>
    <div class="cinfo">
      ${dl("cofficers",officers.map(o=>[o.role,
        o.slug?`<a href="legislator/${esc(o.slug)}.html">${esc(o.label||o.name)}</a>`
              :esc(o.name)]))}
      ${dl("cstaff",staff.map(([k,v])=>[k,esc(v)]))}
    </div>
    ${members.length?`<div class="croster">
      <h2>Members <span>${members.length}</span></h2>
      <p class="mlist">${members.map(mchip).join(" ")}</p>
      ${emailCommittee(c)}</div>`:""}
    ${rule?`<div class="cpurpose"><h2>What it does</h2>
      <p>${esc(rule.text||"")}</p>
      <p class="src">${esc(rule.rule||"")}, as the General Court publishes it.</p>
      </div>`:""}
    ${c.url?`<p class="src"><a href="${esc(c.url)}" target="_blank"
      rel="noopener">This committee on gencourt &#8599;</a></p>`:""}
  </div>`;
}

const cmteBills=c=>((c.bills||{})[pageTerm()]||[]).map(idxRow);
const cmteSessions=c=>(c.sessions||[])
  .filter(s=>!pageTerm()||!s.term||s.term===pageTerm());

function renderCommitteeBills(c){
  const rows=cmteBills(c),t=pageTerm();
  if(!rows.length)return `<p class="src">No bills were referred to this
    committee in the ${esc(t)} term.</p>`;
  return billPane(rows,n=>`${n.toLocaleString()} bill${n===1?"":"s"} referred to
    this committee in ${esc(t)}.`);
}

// One day the committee met: what it did, the recording, and the moment each
// bill was taken up. The timestamps drive the player above them rather than
// sending the reader to YouTube and back.
function sessionHtml(s,si){
  const items=s.items||[];
  const pid=`d${String(s.date||"").replace(/-/g,"")}_${si}`;
  const timed=items.filter(i=>i.start!=null);
  const from=timed.length?Math.max(0,Math.floor(timed[0].start)):0;
  const vid=s.video_id||"";
  // ONE number, shown and seeked. Where the header, the player and the button
  // each carried a slightly different offset, a reader had no way to tell
  // which one was the claim.
  const player=vid?`<div class="player" data-player="${esc(pid)}">
      <button type="button" class="pstub" data-embed="${esc(vid)}|${from}|${esc(pid)}">
        <span>&#9654;</span><span>Play this day's recording${timed.length
          ?` from ${hms(from)}, where the first bill is taken up`:""}</span></button>
      <div class="pbar">
        <a href="https://www.youtube.com/watch?v=${esc(vid)}&t=${from}s"
           target="_blank" rel="noopener">Open on YouTube</a>
        <span class="tolnote">${timed.length
          ?"the times below move this player"
          :"no moment in this recording has been identified yet"}</span>
      </div></div>`
    :`<p class="note">No recording of this day is on file.</p>`;
  return `<section class="cday">
    <h3>${esc(fdate(s.date))}</h3>
    <p class="cnarr">${esc(s.narrative||"")}</p>
    ${player}
    <ul class="tl">${items.map(i=>{
      // "stated" is a boundary the chair spoke; anything else was worked out
      // from the schedule or the surrounding recording and says so.
      const said=/^(stated|floor_stated|floor_precise)$/.test(i.state||"");
      const at=i.start!=null?Math.max(0,Math.floor(i.start)):null;
      return `<li>
      <span class="d">${at!=null
        ? (vid?`<button class="jump" data-seek="${esc(pid)}|${at}">${hms(at)}</button>`
             :`${hms(at)}`)
        : "&mdash;"}${at!=null&&!said?`<i class="approx">approximate</i>`:""}</span>
      <span class="w"><a href="bill/${esc(String(i.year||""))}/${
        esc(String(i.bill||"").toLowerCase())}.html">${esc(i.n||i.bill||"")}</a>
        &mdash; ${esc(i.kind||"")}${i.title?`<span class="cd-title">${
          esc(i.title)}</span>`:""}</span></li>`;}).join("")}</ul>
  </section>`;
}

function renderCommitteeSessions(c){
  const ss=cmteSessions(c),t=pageTerm();
  if(!(c.sessions||[]).length)return `<p class="src">No day of this committee is
    on record. Committees that no longer meet keep their page so the bills they
    handled still have somewhere to point.</p>`;
  if(!ss.length)return `<p class="src">No day of this committee is on record in
    the ${esc(t)} term.</p>`;
  return `<p class="src">${ss.length.toLocaleString()} day${ss.length===1?"":"s"}
      this committee met in ${esc(t)}, newest first. Each is the day's recording
      with the moment every bill was taken up, composed from the record rather
      than written.</p>`
    + ss.map(sessionHtml).join("");
}

// ======================================================= upcoming session ==
// The same block the home page prints, for one committee. It reads
// home.json's `upcoming`, which is where the site publishes what is
// scheduled; a second file carrying the same facts is how a record ends up
// with two answers, and this project has paid for that more than once.
//
// MATCHED BY NAME AND BY BILL, not by name alone. Seven committee names
// belong to both chambers -- Finance, Judiciary, Education, Transportation,
// Ways and Means, Children and Family Law, Executive Departments and
// Administration -- and `upcoming` carries no chamber. So a bare name match
// would put a Senate Finance hearing on House Finance's page. A meeting is
// this committee's only if the name matches AND at least one of its bills is
// in this committee's own bill list. Where nothing matches, nothing is shown:
// omitting a real meeting is recoverable, and attributing one to the wrong
// committee is the kind of error somebody quotes.
function cmteUpcoming(c){
  if(!Array.isArray(UPCOMING)||!UPCOMING.length)return [];
  const name=String(c.name||"").trim().toLowerCase();
  if(!name)return [];
  // KEYED BY TERM AND NUMBER, because a bill number is not a key. CACR 1 is
  // a different bill in every biennium and House Finance carries three of
  // them -- 2001, 2005 and 2019. Collapsing the terms would let a CACR 1 of
  // 2001 vouch for a 2026 meeting about something else entirely, which is
  // the join CLAUDE.md warns about in as many words: the pair is bill+term.
  // Found by a test whose own fixture was wrong, which is the only reason
  // the flaw showed at all.
  const mine=new Set();
  Object.entries(c.bills||{}).forEach(([t,rows])=>(rows||[]).forEach(b=>{
    if(b&&b.id)mine.add(t+"\u0000"+String(b.id).toUpperCase());
  }));
  return UPCOMING.filter(u=>
    String(u.committee||"").trim().toLowerCase()===name
    && mine.has(String(u.term||"")+"\u0000"+String(u.bill||"").toUpperCase()));
}

// The kinds the General Court's schedule actually uses, in the words a reader
// needs: a public hearing is the one they may speak at, an executive session
// is the one where the committee votes.
const MEET_KIND={"public hearing":["Public hearing","k-hearing"],
                 "hearing":["Public hearing","k-hearing"],
                 "executive session":["Executive session","k-exec"],
                 "work session":["Work session",""],
                 "subcommittee work session":["Subcommittee work session",""]};

// THE MARKUP HERE MUST MATCH build_pages.py's calendar_html(). Both emit the
// same component against one set of rules in app.css's SHARED region, and
// preflight fails if the class names drift apart -- which is the only thing
// keeping two renderers of one component honest.
function calendarBlock(rows,heading){
  if(!rows.length)return "";
  const meets=new Map();
  rows.forEach(u=>{
    const k=[u.date||"",u.time||"",u.committee||"",u.what||"",u.venue||""].join("\u0000");
    if(!meets.has(k))meets.set(k,[]);
    meets.get(k).push(u);
  });
  const keys=[...meets.keys()].sort();
  const days=new Map();
  keys.forEach(k=>{
    const d=k.split("\u0000")[0];
    if(!days.has(d))days.set(d,[]);
    days.get(d).push(k);
  });
  const today=new Date(); today.setHours(0,0,0,0);
  const when=d=>{
    const dd=new Date(d+"T00:00:00");
    if(isNaN(dd))return [d,""];
    const off=Math.round((dd-today)/86400000);
    const rel=off===0?"today":off===1?"tomorrow":(off>0&&off<14)?`in ${off} days`:"";
    return [dd.toLocaleDateString(undefined,
      {weekday:"short",day:"numeric",month:"short"}),rel];
  };
  const out=[`<section class="cal"><h2>${esc(heading)}</h2>`];
  days.forEach((ks,date)=>{
    const [label,rel]=when(date);
    out.push(`<div class="calday"><h3 class="caldate"><span>${esc(label)}</span>`
      +(rel?`<span class="cdrel">${esc(rel)}</span>`:"")+`</h3>`);
    ks.forEach(k=>{
      const [,time,cmte,what,venue]=k.split("\u0000");
      const bills=meets.get(k);
      const [word,kcls]=MEET_KIND[String(what||"").trim().toLowerCase()]
        ||[what?what.charAt(0).toUpperCase()+what.slice(1):"Meeting",""];
      out.push(`<details class="calmeet"><summary>`
        +(time?`<span class="caltime">${esc(time)}</span>`:"")
        +`<span class="calcmte">${esc(cmte)}</span>`
        +`<span class="calkind ${kcls}">${esc(word)}</span>`
        +`<span class="calcount">${bills.length} bill${bills.length===1?"":"s"}</span>`
        +(venue?`<span class="calwhere">${esc(venue)}</span>`:"")
        +`<span class="caret"></span></summary>`
        +`<div class="calbody"><ul class="calbills">`);
      bills.forEach(b=>{
        const id=String(b.bill||"");
        const num=id.replace(/^([A-Za-z]+)(\d)/,"$1 $2");
        // billHref resolves the year the same way every other link on this
        // page does, so a calendar row and a card row cannot disagree.
        // The title from the row if the builder put one there, otherwise out
        // of the term index this page has already loaded. `upcoming` carries
        // no title, so without this the committee page would print a column
        // of bare bill numbers while the home page prints the same four with
        // their titles -- one component, two answers.
        const ti=b.title||billTitle(id);
        out.push(`<li><a class="cbn" href="${esc(billHref(id))}">${esc(num)}</a>`
          +(ti?`<span class="cbt">${esc(ti)}</span>`:"")+`</li>`);
      });
      out.push(`</ul></div></details>`);
    });
    out.push(`</div>`);
  });
  out.push(`<p class="note">Anyone may attend and speak at a public hearing,
    or sign in for or against without speaking. An executive session is where
    the committee votes on what to recommend; it is open to watch but not to
    testify.</p></section>`);
  return out.join("");
}

// A bill's own page, by the year its number belongs to. yearOf is what the
// rest of this file uses, so a calendar link and a card link agree.
function billHref(id){
  const y=(typeof yearOf==="function"&&yearOf(id))||null;
  return y?`bill/${y}/${String(id).toLowerCase()}.html`
          :`bills.html#${encodeURIComponent(id)}`;
}

function billTitle(id){
  if(!Array.isArray(IDX))return "";
  const b=IDX.find(x=>x.id===id&&(!term||x.term===term))||IDX.find(x=>x.id===id);
  return (b&&b.title)||"";
}

function renderCommitteeUpcoming(c){
  if(UPCOMING===null)return "";               // not asked yet: say nothing
  const rows=cmteUpcoming(c);
  if(!rows.length)
    return `<section class="cal"><h2>Upcoming session</h2>
      <p class="note">Nothing is scheduled for this committee in the next two
      weeks. The General Court sits from January to June.</p></section>`;
  return calendarBlock(rows,"Upcoming session");
}

function renderCommittee(c){
  // Counted for the term the page is showing, not across every term. "Bills
  // (107)" over a list of 32 is the tab disagreeing with itself.
  const tabs=[["Bills",cmteBills(c).length],["Sessions",cmteSessions(c).length]];
  const body=[()=>renderCommitteeBills(c),()=>renderCommitteeSessions(c)][PAGE_TAB]
    ||(()=>"");
  // Who they are, then what is coming, then the record. The calendar sits
  // above the term control because it is not about a term: it is about this
  // week, and a reader who came to find out whether they can still turn up
  // and speak should not have to scroll past nineteen years of bills.
  return renderCommitteeHead(c) + renderCommitteeUpcoming(c)
    + termControl() + tabStrip(tabs)
    + `<div class="pane" role="tabpanel" tabindex="0">${body()}</div>`;
}

// ------------------------------------------------------------------ boot ---
function renderPage(){
  if(!PAGE)return;
  const el=$("#results");
  if(!el)return;
  el.innerHTML = PAGE.kind==="member" ? renderMember(PAGE.data)
                                      : renderCommittee(PAGE.data);
  syncCards([...openCards]);
}

// The tabs, the cards and the filter selects on these two pages. Kept apart
// from the bill list's handlers, which end at "if(PAGE)return" because they
// finish by calling render() and would draw the search over the record.
document.addEventListener("click",e=>{
  if(!PAGE)return;
  const t=e.target.closest("[data-pt]");
  if(t){PAGE_TAB=+t.dataset.pt;renderPage();return;}
  // Not data-more: that one belongs to the bill list, is read by the
  // handler above this in the file, and calls render(), which would draw the
  // search over the member's record.
  const vm=e.target.closest("[data-vmore]");
  if(vm){PAGE.vshow=(PAGE.vshow||VOTES_SHOWN)+VOTES_SHOWN;renderPage();return;}
  const ct=e.target.closest(".card .tab[data-t]");
  if(ct){openTab[ct.closest(".card").dataset.id]=ct.dataset.t;renderPage();return;}
  const head=e.target.closest(".chead");
  if(head&&!e.target.closest("a")){
    const id=head.closest(".card").dataset.id;
    if(openCards.has(id)){openCards.delete(id);renderPage();}
    else openBill(id);
    return;}
});
document.addEventListener("change",e=>{
  if(!PAGE)return;
  const f=e.target.dataset.pf;
  if(!f)return;
  PAGE[f]=e.target.value;
  // A status chosen in one term rarely exists in another, so keeping it
  // emptied the list while the control still read the old value -- a reader
  // seeing nothing, with nothing on screen saying why.
  //
  // The term also moves the GLOBAL term, because dkey and yearOf resolve a
  // bill number within it: a card opened on a 2023-2024 page would otherwise
  // have fetched the 2025-2026 bill of that number and shown its history.
  // THE TERM'S BILLS, FETCHED. idxRow looks a bill up in IDX, and IDX only
  // ever held the term the site opened on -- so choosing an earlier term
  // here left every bill on the page with no title and its number unspaced,
  // on the sponsored tabs as well as this one. Nothing asked for that term's
  // index because nothing on a record page ever had.
  if(f==="term"){PAGE.status="";term=PAGE.term;
    ensureTerm(PAGE.term).then(renderPage);}
  // A narrower filter over a list already expanded to 800 rows left the
  // reader at the bottom of a list of 40.
  if(f==="vfilter"||f==="vparty"||f==="term")PAGE.vshow=0;
  renderPage();
});

// The term and sort dropdowns order and filter a list of bills. On a page
// showing one member or one committee there is no such list, and a control
// that does nothing is worse than no control.
function hideListControls(){
  ["#year","#sort"].forEach(sel=>{
    const el=$(sel); if(!el)return;
    el.hidden=true;
    const lab=el.previousElementSibling;
    if(lab&&lab.tagName==="LABEL")lab.hidden=true;
  });
  const hint=document.querySelector(".qhint");
  if(hint)hint.hidden=true;
  const q=$("#q");
  if(q)q.placeholder="Search all bills";
}

// Every term this record has anything in, newest first. Worked out once,
// when the file lands, so every tab and the control above them agree.
function recordTerms(kind,d){
  const t=new Set();
  if(kind==="member"){
    (d.sponsored||[]).forEach(b=>b.term&&t.add(b.term));
    (d.votes||[]).forEach(v=>{const x=termOfYear(v.y);if(x)t.add(x);});
  }else{
    Object.keys(d.bills||{}).forEach(x=>x&&t.add(x));
    (d.sessions||[]).forEach(s=>s.term&&t.add(s.term));
  }
  return [...t].sort().reverse();
}

function openPage(kind,ref){
  PAGE={kind,data:null,terms:[],term:"",status:"",vfilter:"",
        vparty:"",vshow:0};
  // The search chrome belongs to the search. Left up, the facet panel offered
  // filters for a list that is not on screen and the counter read "2,234 of
  // 2,234 bills" beside one member's name.
  const fac=$("#facets"); if(fac){fac.innerHTML="";fac.hidden=true;}
  const sh=document.querySelector(".shell"); if(sh)sh.classList.add("nofacets");
  const c=$("#count"); if(c)c.textContent="";
  const sy=$("#synhint"); if(sy)sy.textContent="";
  hideListControls();
  const url=DATA(kind==="member"?`legislators/${ref}.json`
                                :`committee/${ref}.json`);
  const el=$("#results");
  if(el)el.innerHTML=`<p class="src">Loading&hellip;</p>`;
  fetch(url).then(r=>{
    if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for this file`);
    return r.json();
  }).then(d=>{
    PAGE.data=d;
    PAGE.terms=recordTerms(kind,d);
    // The global term follows the page's, because dkey and yearOf resolve a
    // bill number inside it and a card opened here fetches by that key.
    PAGE.term=PAGE.terms[0]||"";
    if(PAGE.term)term=PAGE.term;
    renderPage();
    // And on the way in: a member whose newest term is not the site's opens
    // on their own, whose index nothing has asked for either.
    if(PAGE.term)ensureTerm(PAGE.term).then(renderPage);
    // What is scheduled, for the committee page's own calendar. 13 KB, asked
    // once, and asked AFTER the record it belongs to -- the page is useful
    // without it and must not wait on it. A failure leaves UPCOMING null,
    // which draws nothing rather than claiming nothing is scheduled.
    if(kind==="committee"&&UPCOMING===null){
      fetch(DATA("home.json"))
        .then(r=>r.ok?r.json():null)
        .then(h=>{UPCOMING=(h&&h.upcoming)||[];renderPage();})
        .catch(()=>{});
    }
  })
    .catch(e=>{if(el)el.innerHTML=`<div class="empty"><b>This page's record did
      not load.</b><br><br><code>${esc(e.message||e)}</code><br><br>
      The file it wanted is <code>${esc(url)}</code>.</div>`;});
}

// A HUNDRED AT A TIME. render() drew the first 400 matches and told the
// reader to narrow the search to see the rest, which is the site asking a
// person to do its work: the 2025-2026 term alone matches 2,234 bills with no
// filters at all, and 400 cards is a slow first paint for a list nobody has
// scrolled yet.
//
// This stays ONE renderer, which is the rule here -- render(true) draws the
// same list one page longer rather than a second function appending to it.
// The observer at the bottom of the list is what calls it.
// PAGE_SIZE, not PAGE: PAGE is already the member-or-committee page
// object declared above, and shadowing it emptied every legislator page.
const PAGE_SIZE = 100;
let SHOWN = PAGE_SIZE;

function render(more){
  // Any change to the result set starts again at the first hundred. Every
  // existing caller passes nothing, so only the observer extends.
  if(!more)SHOWN=PAGE_SIZE;
  // Page scroll only. The facet panel restores itself inside renderFacets,
  // synchronously, which is the only way it survives the repaint.
  const _y=window.scrollY;
  const rows=sortRows(IDX.filter(b=>matches(b)));
  const inTerm=IDX.filter(b=>!term||!b.term||b.term===term).length;
  // Say when a search matched on a synonym, so nobody wonders why a bill about
  // firearms turned up for "guns".
  const qw=query.trim().toLowerCase().replace(/,/g," ").split(/\s+/).filter(Boolean);
  const used=[...new Set(qw.flatMap(w=>{const e=expand(w);
    return e.length>1&&!e.includes(w)?e.slice(0,3):(e.length>1?e.filter(x=>x!==w).slice(0,3):[]);}))];
  const sh=$("#synhint");
  if(sh)sh.textContent=used.length&&!billNumbers(query)
    ? `also matching: ${used.join(", ")}` : "";
  const ids0=billNumbers(query);
  // A focused view is one bill. The count describes a list that is not on
  // screen, and on a bill's own page it read "2,234 of 2,234 bills in the
  // 2025-2026 term" above a single bill.
  $("#count").textContent=focused?""
    :ids0
    ?`${rows.length} matching in the ${term} term`
    :`${rows.length.toLocaleString()} of ${inTerm.toLocaleString()} bills in the ${term} term`;
  // Same number, different term: say so instead of an empty page.
  const elsewhere=ids0&&!rows.length
    ? IDX.filter(b=>ids0.includes(b.id.toUpperCase())&&b.term&&b.term!==term)
    : [];
  const ids=billNumbers(query);
  // A focused bill is shown on its own, whether or not the current filters
  // would have listed it -- somebody arriving on a shared link has no filters
  // and should still see the bill.
  //
  // DECLARED BEFORE ITS FIRST USE, which is not a style point: const is in the
  // temporal dead zone until this line runs, so reading fb above it threw
  // "Cannot access 'fb' before initialization" and took the whole of render()
  // with it. The page loaded, the data loaded, and nothing listed.
  const fb=focused?(rows.find(b=>b.id===focused)||IDX.find(b=>b.id===focused)):null;
  document.querySelector(".shell").classList.toggle("focused",!!fb);
  const shown=fb?[fb]:rows.slice(0,SHOWN);
  $("#summary").textContent=fb?"":(ids&&ids.length>1
    ?`Showing ${rows.length} of the ${ids.length} bills you listed.`:"");
  // Counted over what is on screen, not over the whole result set, so the
  // number beside a heading always matches the cards under it.
  const grpN={};
  if(sortBy==="status")for(const b of shown)grpN[b.status||""]=(grpN[b.status||""]||0)+1;
  $("#results").innerHTML=(fb?`<button class="backto" data-back="1">\u2190 Back to
    bill search</button>`:"")+((rows.length||fb)?shown.map((b,gi,arr)=>`
    ${!fb&&sortBy==="status"&&(gi===0||arr[gi-1].status!==b.status)
      ?`<h2 class="grp">${esc(b.status||"No status recorded")}
         <span>${grpN[b.status||""]}</span></h2>`:""}
    ${cardHtml(b,!!fb)}`).join("")+((!fb&&rows.length>SHOWN)?`<p class="more" id="more">Showing ${
      shown.length.toLocaleString()} of ${rows.length.toLocaleString()} — <button
      class="link" data-more="1">show ${Math.min(PAGE_SIZE,rows.length-SHOWN)} more</button></p>`:"")
    :(elsewhere.length
      ?`<div class="empty"><b>Not in the ${esc(term)} term.</b><br><br>
        ${elsewhere.map(b=>`${esc(b.n)} exists in the
          <button class="link" data-term="${esc(b.term)}">${esc(b.term)}</button>
          term — ${esc(b.title||"")}`).join("<br>")}</div>`
      :`<div class="empty">No bills match. Try removing a filter, or a different
        term.</div>`));
  // Reaching the end of the list is the request for more of it. The button
  // in the sentinel does the same thing for a keyboard or a reader that never
  // fires an intersection.
  const sentinel=$("#more");
  if(sentinel){
    if(window._moreObs)window._moreObs.disconnect();
    if(window.IntersectionObserver){
      window._moreObs=new IntersectionObserver(es=>{
        if(es.some(e=>e.isIntersecting)){SHOWN+=PAGE_SIZE;render(true);}
      },{rootMargin:"400px"});
      window._moreObs.observe(sentinel);
    }
  }
  syncCards(rows.filter(b=>openCards.has(b.id)).map(b=>b.id));
  renderFacets();
  if(window.scrollY!==_y)window.scrollTo(0,_y);
}

// Opening a bill pushes its own address, so the view can be shared and
// reloaded -- and a reload lands on the static page, which is the one a
// crawler and a reader without JavaScript get. Going back never reloads
// anything, so the search comes back exactly as it was: same filters, same
// query, same place on the page.
function focusBill(id,href){
  focusY=window.scrollY;
  focused=id;
  // /bill/2026/hb1123 -- the address a person would paste, and the same
  // shape a legislator's page uses.
  //
  // This used to push "?q=hb1123#2026/HB1123", because the static page's own
  // address belonged to a DIFFERENT document: reloading it fetched the same
  // facts in another layout with no charts, and a reader who pressed F5 got a
  // page that had changed under them. That stopped being true when the
  // renderer was unified. /bill/2026/hb1123.html is this app with one bill
  // open, so reloading the clean address reopens exactly this view.
  const _y=yearOf(id);
  if(_y){
    try{history.pushState({focus:id},"",
      `${BASE}bill/${_y}/${id.toLowerCase()}`);}catch(_){}
  }
  openBill(id);
  window.scrollTo(0,0);
}

function unfocus(y){
  // On a bill's own page there is no list behind it to back out to: the
  // reader arrived at that bill directly. Drawing two thousand cards under
  // an address that names one bill would be the wrong page at the wrong URL,
  // so leaving the bill means leaving the page.
  if(window.GR_STANDALONE){location.href="bills.html";return;}
  // Back out to where the reader was standing when they opened the bill --
  // except when they got here by typing a new search, where the old position
  // belongs to a list that is no longer on screen.
  if(y===undefined)y=focusY;
  focused=null;
  // Leaving a bill named in the address would mean the next refresh reopened
  // it, which is not where the reader is standing.
  // Back to the list's own address rather than the bill's.
  try{history.pushState({},"",BASE+"bills.html");}catch(_){}
  render();
  window.scrollTo(0,y);
}

window.addEventListener("popstate",e=>{
  const f=e.state&&e.state.focus;
  if(f){focused=f;openBill(f);window.scrollTo(0,0);}
  else if(focused)unfocus();
});

function openBill(id){
  openCards.add(id);
  if(detail[dkey(id)]){repaint();return;}
  repaint();
  // What went wrong, not merely that something did.
  //
  // This used to report "Detail unavailable" and nothing else, which is how a
  // refresh on a bill page stayed unexplained through two wrong guesses at the
  // cause. A 404, a file that is not JSON, and a refused connection all looked
  // identical from the outside, and they are three different problems.
  const yr=yearOf(id);
  // THE RECORD TRAVELS INSIDE THE PAGE unless it is large. A bill's page used
  // to be a 4.3 KB shell that fetched its record as a second round trip, and
  // for half the bills here that record is 1.3 KB -- so the envelope cost
  // more than the letter and took an extra journey to deliver it. 33,585 of
  // 33,683 records are now in the page; the 98 over 100 KB, which are almost
  // all roll call ballots, keep a file and the page says where it is.
  const url=DATA(`bill/${yr}/${id.toLowerCase()}`);
  const fail=(why)=>{
    detail[dkey(id)]={events:[],rollcalls:[],stations:[],reports:[],sponsors:[],
      documents:[],amendments:[],next_step:"Detail unavailable",
      _error:why+"\n"+url};
    repaint();
  };
  const take=(txt,where)=>{
    let d;
    try{ d=JSON.parse(txt); }
    catch(_){ throw new Error(`${where} arrived but is not JSON. It starts: ${
      txt.slice(0,80).replace(/\s+/g," ")}`); }
    detail[dkey(id)]=d; repaint();
  };

  // ON A BILL'S OWN PAGE THE ANSWER IS ALREADY HERE. Either the record
  // itself, or -- for the 98 too large to travel inside a page -- the address
  // of the file holding it. Reading the pointer from this document rather
  // than fetching the page again saves HB1442 from asking for itself before
  // asking for its votes.
  const mine=window.GR_BILL&&
    String(window.GR_BILL).toUpperCase()===`${yr}/${id}`.toUpperCase();
  if(mine){
    const own=document.getElementById("gr-data");
    if(own){
      try{ take(own.textContent,"this page's record"); }catch(e){ fail(e.message); }
      return;
    }
    const here=document.querySelector('meta[name="gr-data"]');
    if(here){
      const u=DATA(here.getAttribute("content").replace(/^\//,""));
      fetch(u).then(r=>{
        if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for ${u}`);
        return r.text();
      }).then(txt=>take(txt,"the record file"))
        .catch(e=>fail(e.message||String(e)));
      return;
    }
  }

  // Otherwise fetch the bill's page and read the record out of it. A script
  // tag with an id is one DOMParser call; the alternative was pulling a
  // JavaScript assignment out of the text by hand.
  // Extensionless, because that is the address the host serves and the one
  // the canonical names. A plain static file server -- the one used to look
  // at this site locally -- serves only the .html form, so a 404 is retried
  // there. In production the first request succeeds and the retry never runs.
  fetch(url).then(r=>r.ok?r:fetch(url+".html")).then(r=>{
    if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for this page`);
    return r.text();
  }).then(html=>{
    const doc=new DOMParser().parseFromString(html,"text/html");
    const node=doc.getElementById("gr-data");
    if(node)return take(node.textContent,"the record in that page");
    const ptr=doc.querySelector('meta[name="gr-data"]');
    if(!ptr)throw new Error("that page carries neither the record nor a link to it");
    const u=DATA(ptr.getAttribute("content").replace(/^\//,""));
    return fetch(u).then(r=>{
      if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for ${u}`);
      return r.text();
    }).then(txt=>take(txt,"the record file"));
  }).catch(e=>fail(e.message||String(e)));
}

document.addEventListener("click",e=>{
  // Swap the still for a real player only when asked. Eight iframes on one
  // page would each pull YouTube's payload before anyone pressed play.
  const stub=e.target.closest("[data-embed]");
  if(stub){
    const [vid,from,pid]=stub.dataset.embed.split("|");
    stub.outerHTML=`<iframe id="yt_${pid}" allow="autoplay" allowfullscreen
      src="https://www.youtube-nocookie.com/embed/${vid}?start=${from}&autoplay=1&enablejsapi=1"
      title="Hearing recording"></iframe>`;
    return;
  }
  const seek=e.target.closest("[data-seek]");
  if(seek){
    const [pid,t]=seek.dataset.seek.split("|");
    const box=document.querySelector(`[data-player="${pid}"]`);
    let f=document.getElementById("yt_"+pid);
    if(!f){
      // Load it AT the time that was asked for. This used to click the stub,
      // which builds the player at the opening offset -- a few seconds to five
      // minutes before the bill -- and then post seekTo to an iframe created
      // one line earlier. YouTube's API is not listening until the frame has
      // loaded, so the message went nowhere and the video sat at a different
      // time from the button that had just been pressed. That is the mismatch
      // between the player's own clock and the times printed beside it.
      const st=box&&box.querySelector("[data-embed]");
      if(st){
        const [vid,,p2]=st.dataset.embed.split("|");
        st.dataset.embed=`${vid}|${Math.max(0,Math.floor(Number(t)))}|${p2}`;
        st.click();
        f=document.getElementById("yt_"+pid);
        if(f)f.scrollIntoView({block:"nearest"});
        return;
      }
    }
    if(f){
      // seekTo over postMessage keeps playback going instead of reloading.
      f.contentWindow.postMessage(JSON.stringify(
        {event:"command",func:"seekTo",args:[Number(t),true]}),"*");
      f.scrollIntoView({block:"nearest"});
    }
    return;
  }
  // These three live INSIDE an expanded bill card, which a member's and a
  // committee's page now draw too, so they redraw whichever view is up.
  const an=e.target.closest(".anmore");
  if(an){
    const id=an.dataset.an;
    anOpen.has(id)?anOpen.delete(id):anOpen.add(id);
    clampAnalysis();
    return;
  }
  const seg=e.target.closest("[data-seg]");
  if(seg){const[bid,i,which]=seg.dataset.seg.split("|");const k=`${bid}|${i}`;
    segSel[k]=segSel[k]===which?null:which;repaint();return;}
  const rt=e.target.closest("[data-routine]");
  if(rt){const id=rt.dataset.routine;
    showRoutine.has(id)?showRoutine.delete(id):showRoutine.add(id);
    repaint();return;}
  const f=e.target.closest("[data-full]");
  if(f){const k=f.dataset.full;fullOpen.has(k)?fullOpen.delete(k):fullOpen.add(k);repaint();return;}
  const g=e.target.closest(".fhead");
  if(g){openGroups.has(g.dataset.g)?openGroups.delete(g.dataset.g):openGroups.add(g.dataset.g);renderFacets();return;}
  const un=e.target.dataset.unpick;
  if(un){sel.sponsor.delete(un);render();return;}
  // Left click opens in place; a modified or middle click falls through to
  // the anchor and gets the static page in a new tab, which still works.
  // On a record page there is no search list to come back to, so the arrow
  // is left to be an ordinary link to the bill's own page.
  const dt=PAGE?null:e.target.closest("a.detail");
  if(dt&&e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){
    e.preventDefault();
    focusBill(dt.closest(".card").dataset.id,dt.getAttribute("href"));return;}
  if(e.target.closest("[data-back]")){history.back();return;}
  // The same thing the observer does, for a keyboard, a reader, or a
  // browser with no IntersectionObserver.
  if(e.target.closest("[data-more]")){SHOWN+=PAGE_SIZE;render(true);return;}
  // Everything below reads .card. A member's or a committee's page has none,
  // so a tab click here threw on tab.closest(".card").dataset and the tab did
  // nothing. Those pages have their own handler, registered above.
  if(PAGE)return;
  const head=e.target.closest(".chead");
  if(head&&!e.target.closest("a")){const id=head.closest(".card").dataset.id;
    if(openCards.has(id)){openCards.delete(id);render();}else openBill(id);return;}
  const tab=e.target.closest(".tab");
  if(tab){
    const cid=tab.closest(".card").dataset.id;
    openTab[cid]=tab.dataset.t;
    // The versions index is fetched when the tab is opened and not before,
    // which is the whole reason it is a separate file.
    if(tab.dataset.t==="6"){
      const row=IDX.find(x=>x.id===cid);
      if(row)needVersions(row);
    }
    render();return;}
  // Picking a version, or switching between what changed and the full text.
  const vb=e.target.closest("[data-ver]");
  if(vb){
    const [key,j]=vb.dataset.ver.split("|");
    VPICK[key]=+j;
    const row=IDX.find(x=>verKey(x)===key);
    if(row){needVersions(row);}
    render();return;}
  const vm=e.target.closest("[data-vmode]");
  if(vm){
    const [key,mode]=vm.dataset.vmode.split("|");
    VMODE[key]=mode;
    const row=IDX.find(x=>verKey(x)===key);
    if(row){needVersions(row);}
    render();return;}
  // An amendment's own text, opened one at a time.
  const va=e.target.closest("[data-vamd]");
  if(va){
    const [key,j]=va.dataset.vamd.split("|");
    const ix=VERS[key], a=ix&&(ix.amendments||[])[+j];
    if(a&&VTEXT[a.text_url]===undefined){
      VTEXT[a.text_url]=undefined;
      fetch(DATA(a.text_url.replace(/^\//,"")))
        .then(r=>r.ok?r.text():Promise.reject(new Error("HTTP "+r.status)))
        .then(x=>{VTEXT[a.text_url]=x;repaint();})
        .catch(()=>{VTEXT[a.text_url]=null;repaint();});
    }
    render();return;}
  const jt=e.target.closest("[data-term]");
  if(jt){term=jt.dataset.term;$("#year").value=term;forgetCardState();render();return;}
  if(e.target.id==="clear"){Object.values(sel).forEach(s=>s.clear());render();return;}
});
document.addEventListener("change",e=>{
  if(PAGE)return;                       // the facet checkboxes are not drawn there
  const f=e.target.dataset.f;if(!f)return;
  e.target.checked?sel[f].add(e.target.value):sel[f].delete(e.target.value);render();});
document.addEventListener("input",e=>{
  if(e.target.id==="sbox"){sponsorFilter=e.target.value;renderFacets();
    const b=document.getElementById("sbox");if(b){b.focus();b.setSelectionRange(b.value.length,b.value.length);}}});
// Running a search from one bill's own view means leaving that bill, so it
// waits to be told. Everywhere else the list narrows as you type, which is
// what a search box on a list should do.
function submitSearch(){
  query=$("#q").value;
  // From a member's or a committee's page, searching means going to the bill
  // search -- that is where results are drawn. Running render() here wrote
  // the list over the record instead, and the only way back was a reload.
  if(PAGE||window.GR_STATIC){
    location.href="bills.html"+(query?`?q=${encodeURIComponent(query)}`:"");
    return;
  }
  // From a bill's own view, running the search means leaving that bill. Back
  // out to the top: the scroll position from before it was opened belongs to
  // a list that is no longer the one on screen.
  if(focused){unfocus(0);return;}
  // On the list the results have already narrowed as they typed, so there is
  // nothing to run. Return means they have finished typing: let go of the
  // keyboard and bring the first result up to where they are looking.
  render();
  $("#q").blur();
  const first=$("#results")&&$("#results").querySelector(".card");
  if(first)first.scrollIntoView({block:"start",behavior:"smooth"});
}
$("#q").addEventListener("input",e=>{
  // No live narrowing on a record page: there is no list under it to narrow,
  // and render() would replace the record with one.
  if(focused||PAGE||window.GR_STATIC)return;
  query=e.target.value;
  render();
});
$("#q").addEventListener("keydown",e=>{
  if(e.key==="Enter"){e.preventDefault();submitSearch();}
});
$("#qgo").addEventListener("click",submitSearch);
document.addEventListener("keydown",e=>{
  if(e.key==="/"&&document.activeElement!==$("#q")){e.preventDefault();$("#q").focus();$("#q").select();}
  // Tabs carry role="tab", and a screen reader user is told they are tabs, so
  // the arrow keys have to work. They did nothing before.
  const tab=e.target.closest&&e.target.closest(".tab");
  if(tab&&(e.key==="ArrowLeft"||e.key==="ArrowRight"||e.key==="Home"||e.key==="End")){
    const tabs=[...tab.parentElement.querySelectorAll(".tab")];
    const i=tabs.indexOf(tab);
    const to=e.key==="Home"?0:e.key==="End"?tabs.length-1
      :(i+(e.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;
    e.preventDefault();tabs[to].focus();tabs[to].click();
  }});
