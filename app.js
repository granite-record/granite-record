// GRANITE_VERSION: 2026-09-07.8
// What each kind of document actually is, said once rather than in every row.
const DOCWHAT={text:"the bill as it currently stands",
  status:"the page this site takes a bill's status from",
  docket:"every recorded action, in the General Court's own words",
  record:"the official record of one action",
  report:"the calendar a committee report was printed in"};
const PARTY_NAME={R:"Republican",D:"Democrat",I:"Independent",L:"Libertarian",
  X:"Party not on file"};
const PARTY_COLOR={R:"var(--rep)",D:"var(--dem)",I:"var(--ind)",L:"var(--ind)",
  X:"var(--ink-3)"};
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
           voteday:new Set(),year:new Set()};
// On a phone the filter column stacks ABOVE the results, and an open
// Committee group is 340 pixels of it -- so the first bill sat past a
// screen and a half of filters on a 375-wide screen. Someone arriving on
// a phone came for the bills; the filters are one tap away either way.
const wideEnough=typeof matchMedia==="function"
  && matchMedia("(min-width:721px)").matches;
const openGroups=new Set(wideEnough?["committee"]:[]);
let sponsorFilter="";
const openCards=new Set(),openTab={},detail={},segSel={},fullOpen=new Set();
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
const need=(f)=>fetch(DATA(f)).then(r=>{
  if(!r.ok)throw new Error(`${f} returned ${r.status} ${r.statusText}`);
  return r.json().catch(()=>{throw new Error(`${f} is not valid JSON`);});
});
Promise.all([need("index.json"),need("meta.json")])
 .then(([i,m])=>{
   IDX=i;META=m;
   // Build the search haystack here rather than shipping it — one pass, instant,
   // and it keeps index.json about a third smaller over the wire.
   IDX.forEach(b=>b.hay=[b.id,b.n,b.title,b.sponsor,
     ...(b.committees||[b.committee||""]),b.topic].join(" ").toLowerCase());
   const terms=META.terms&&META.terms.length?META.terms
     :[...new Set(IDX.map(b=>b.term).filter(Boolean))].sort().reverse();
   term=terms[0];
   const ys=$("#year");
   ys.innerHTML=terms.map(t=>`<option value="${t}">${t} term</option>`).join("");
   ys.value=term;
   ys.addEventListener("change",e=>{term=e.target.value;render();});
   const so=$("#sort");
   if(so)so.addEventListener("change",e=>{sortBy=e.target.value;render();});
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
     return;
   }
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
  if(ignore!=="year"&&sel.year.size&&!sel.year.has(String(b.year)))return false;
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
      <input class="sbox" id="sbox" placeholder="Type a name…" value="${esc(sponsorFilter)}" autocomplete="off">`
      +(shown.map(v=>`<label class="fopt ${!counts[v]?'off':''}"><input type="checkbox" data-f="${key}"
        value="${esc(v)}" ${chosen.has(v)?"checked":""}><span>${esc(v)}</span>
        <span class="c">${counts[v]||0}</span></label>`).join("")
        ||(sponsorFilter?`<p style="font-size:12.5px;color:var(--ink-3)">No match</p>`:""));
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
  h+=fgroup("sponsor","Prime sponsor",present("sponsor"),cnt("sponsor","sponsor"),true);
  // Year is a facet inside the term, not a hard filter on the whole site.
  // A term's bills split into the year they were filed, and that is useful to
  // narrow by -- but it must never be the thing that hides a bill you searched
  // for by number.
  const yc=cnt("year","year");
  h+=fgroup("year","Year filed",Object.keys(yc).sort(),yc);
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
  const legend=segs.map(s=>{
    const winner=(s.side==="Yea")===won;
    return `<button class="lrow ${chosen===s.key?'sel':''}" data-seg="${key}|${s.key}">
    <span class="sw" style="background:${PARTY_COLOR[s.p]||"var(--ink-3)"}"></span>
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
    role="img" aria-label="Votes by party: ${segs.map(s=>`${PARTY_NAME[s.p]||s.p} ${s.side==='Yea'?'yes':'no'} ${s.n}`).join(", ")}. ${
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
  const at=(x,txt,won)=>`<text x="${x}" y="${Y}" text-anchor="middle" font-size="30"
      letter-spacing=".04em" font-weight="${won?700:400}"
      fill="var(--ink${won?"":"-3"})">${txt}</text>`
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
  const col=v=>(rc.members||[]).filter(m=>m.v===v)
    .sort((a,b)=>(a.s||a.n||"").localeCompare(b.s||b.n||""));
  const grid=a=>`<div class="mgrid">${a.map(m=>`<div class="m">${esc(m.n)}</div>`).join("")}</div>`;
  const sect=([st,label,blurb])=>{const a=col(st);return a.length?`<div class="mlist">
    <h3>${label} — ${a.length}</h3><p class="note" style="margin:0 0 9px">${blurb}</p>${grid(a)}</div>`:"";};
  const y=col("Yea"),n=col("Nay"),tot=(rc.members||[]).length;
  return `<button class="discl" data-full="${k}">Hide full voting record</button>
    <div class="full"><div><h3>Yea — ${y.length}</h3>${grid(y)}</div>
    <div><h3>Nay — ${n.length}</h3>${grid(n)}</div></div>
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
const AVK={VV:"voice vote",DV:"division vote",RC:"roll call"};
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
  return `<span class="tnote">${bit(t.support,"for","for")}${
    bit(t.oppose,"against","against")}${bit(t.neutral,"neutral","")} ${
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
const FACTS=[["gen_status","Status"],["house_status","In the House"],
  ["senate_status","In the Senate"],["date_introduced","Introduced"],
  ["floor_date","Floor date"],["lsr","LSR number"],["chapter","Chapter"],
  ["local","Local government impact"],["committee_code","Committee code"]];

function factsTable(d){
  const f=Object.assign({},d.facts||{});
  if(d.chapter)f.chapter=d.chapter;
  const rows=FACTS.filter(([k])=>f[k]).map(([k,lab])=>{
    const v=k==="local"?(f[k]==="Y"?"yes":f[k]==="N"?"no":f[k]):f[k];
    return `<tr><th scope="row">${esc(lab)}</th><td>${esc(v)}</td></tr>`;
  }).join("");
  if(!rows)return "";
  return `<section class="facts"><h3>On the record</h3>
    <p class="src">Quoted from the General Court bill status page, not worked
      out from the docket.</p>
    <table class="facttab"><tbody>${rows}</tbody></table></section>`;
}

// The sentences that say where a section's facts came from and how to read
// them. They were written for the Python renderer and are the site's voice
// about its own limits, which is the part of it worth keeping most.
const PANE_NOTE={
  votes:`Roll call tallies and individual votes from the General Court roll
    call files, in the order the docket records them. Presiding, excused and
    absent are shown separately: one member presides over each House roll call
    and does not vote except to break a tie.`,
  hearings:`Recordings are the General Court\u2019s own, on YouTube. A start
    time is the moment the chair opened the item, taken from what they said.
    One marked <i>approximate</i> was worked out from where the bill is
    discussed rather than quoted, and can be a few minutes out. Where neither
    was possible the recording is linked without a time.`,
  reports:`The recommendation, the vote and the day it was signed come from the
    docket; the reasoning, where there is any, is reproduced from the House
    Calendar in the committee\u2019s own words.`,
};
const paneNote=(k)=>PANE_NOTE[k]?`<p class="src">${PANE_NOTE[k]}</p>`:"";

function renderSummary(b,d){
  // The citation at the end of a docket line names the journal or calendar
  // that recorded the action. Linking it turns each line from something the
  // reader has to take on trust into something they can check.
  return `${d._error?`<div class="loaderr"><b>This bill's detail did not
    load.</b><span>${esc(d._error)}</span></div>`:""}
    <div class="status ${KIND[b.kind]}"><div class="lab">CURRENT STATUS</div>
    <div class="val">${esc(d.next_step)}</div>
    ${d.status_source?`<div style="font-size:12px;color:var(--ink-3);margin-top:6px">
      ${esc(d.status_source)}${d.chapter?` \u00b7 Chapter ${esc(d.chapter)}`:""}
      ${d.text_pdf?` \u00b7 <a href="${esc(d.text_pdf)}" target="_blank"
        rel="noopener">bill text (PDF)</a>`:""}</div>`:""}</div>
    ${(d.notes||[]).map(x=>`<p class="note">${esc(x)}</p>`).join("")}
    ${factsTable(d)}
    ${(d.stages&&d.stages.length)
      ? `<div class="story">${d.stages.map(st=>
          `<div class="stg">${st.label?`<h3>${esc(st.label)}</h3>`:""}
           <p>${esc(st.text)}</p></div>`).join("")}</div>`
      : (d.narrative?`<p class="story"><span class="stg">${esc(d.narrative)}</span></p>`:"")}
    ${d.archived?`<p class="note" style="margin:10px 0 0">This is an archived
      term. The General Court's own search gives every bill of it with its
      title, its status in each chamber, the committee it went to and the date
      of its hearing, and the recorded votes come from the General Court's
      database &#8212; but the docket, the sponsors and the written committee
      reports are one request per bill and are not loaded. The bill's own text
      and its full record are linked above.</p>`:""}
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
  return (d.rollcalls||[]).length?d.rollcalls.map((rc,i)=>{
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
        vk!=="RC"?` · ${esc(rc.vote_kind_label||"")}`:""}</span>
      <span class="rcres ${rc.passed?'pass':'fail'}">${rc.passed?"Adopted":"Failed"}</span></div>
      ${rc.threshold_note?`<p class="note" style="margin:6px 0 0">${esc(rc.threshold_note)}</p>`:""}
      ${body}</section>`;}).join("")
    :`<p class="note">No roll call votes on this bill. Where a chamber acts by voice or
      division vote, no record exists of how individual members voted — not withheld, never captured.</p>`;
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
          <span style="color:var(--ink-3)">${esc(s.title)}</span></div>`:""}</div>`;
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
          <span style="color:var(--ink-3)">Motions: ${s.motions.map(esc).join(" · ")}</span>
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
      <div class="t">${esc(s.committee||"")} ${esc(s.what)}</div>${inner}</div>`;}).join("")
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
  const head=(r,cmte,body)=>`<div style="display:flex;gap:9px;align-items:baseline;
      flex-wrap:wrap;border-top:1px solid var(--rule);padding-top:11px;margin-bottom:9px">
      ${when(r)}<span class="note" style="font-size:12px">${
        esc([body,cmte].filter(Boolean).join(" "))}${cited(r)}</span></div>`;

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
        <p style="font-size:12.5px;color:var(--ink-3);margin:3px 0 8px">${esc(e.author)}</p>
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

  return (written||docket)?written+docket
    :`<p class="note">No committee report on file. A report is recorded in the docket
      when a committee reports the bill out, and the reasoning behind it is printed
      in the House Calendar or filed with the Senate; neither has happened here yet.</p>`;
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
  const pill=s=>{const who=esc(s.display_full||s.label||s.name||"");
    const inner=s.prime?`<b>${who}</b>`:who;
    return s.slug
      ? `<a class="pill plink" href="legislator/${esc(s.slug)}.html">${inner}</a>`
      : `<span class="pill" style="background:var(--wash);color:var(--ink-2)">${inner}</span>`;};
  const spBlock=ch=>{const l=spAll.filter(s=>chOf(s)===ch);return l.length
    ?`<h3 class="spgrp">${CHNAME[ch]} <span>${l.length}</span></h3>
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
    ${spRest.length?`<h3 class="spgrp">Chamber not on file <span>${spRest.length}</span></h3>
      <div class="chosen">${spRest.map(pill).join(" ")}</div>`:""}`:"";
  return `${sp||`<p class="note">No sponsors on file.</p>`}
      ${(d.sponsors||[]).some(x=>x.prime_inferred)?`<p class="note"
        style="margin-top:12px">Taken from the docket page, because the sponsor
        files cover the current session only. The docket lists the prime sponsor
        first but does not mark the field, so that one is inferred from the
        order.</p>`:""}
      <p class="note" style="margin-top:12px">Prime sponsor in bold. From the
      General Court sponsor file.
      <a href="${esc(d.docket_url)}" target="_blank" rel="noopener">Full docket and bill text on gencourt</a></p>`;
}

// Amendments, in the order the docket took them up. A committee amendment
// is considered before any floor amendment, and where two touch the same
// section the later one governs -- so the sequence carries meaning, and it
// is shown as the record has it rather than grouped or sorted.
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
    ${bt.analysis?`<div class="btan"><h3>Analysis</h3>
      <p>${rsa(esc(bt.analysis))}</p>
      <p class="src">Written by the General Court, not by this site.</p></div>`:""}
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
  return (d.documents||[]).length
      ? `<p class="note">Everything below is published by the General Court. This
         site quotes and summarises these; they are the record itself.</p>
         <ul class="docs">${d.documents.map(x=>`<li class="doc doc-${esc(x.kind)}">
           <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>
           <span>${DOCWHAT[x.kind]||""}</span></li>`).join("")}</ul>`
      : `<p class="note">No official documents on file for this bill yet. The
         bill text and docket links come from the General Court's status page,
         which is fetched separately.</p>`;
}

// The tabs, and one call per pane. Everything this reads is either a
// parameter or the return value of a call made on the line that uses it,
// so there is no declaration here whose order could be got wrong.
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
    ? `<section class="btsec"><h3 class="amdsec">Bill text</h3>
        <p class="btwhat">The bill and its amendments, as the General Court publishes them. Everything above is this site’s account of the record; this is the document.</p>${
        renderBillText(b,d,rsa)}</section>`
    : "";

  return `<div class="tabs" role="tablist">
    <button class="tab" role="tab" id="tab_${b.id}_0" aria-controls="pane_${b.id}_0" aria-selected="true" data-t="0">Summary</button>

    <button class="tab" role="tab" id="tab_${b.id}_1" aria-controls="pane_${b.id}_1" aria-selected="false" data-t="1">Votes${b.nrc?` (${b.nrc})`:""}</button>
    <button class="tab" role="tab" id="tab_${b.id}_2" aria-controls="pane_${b.id}_2" aria-selected="false" data-t="2">Videos</button>
    <button class="tab" role="tab" id="tab_${b.id}_3" aria-controls="pane_${b.id}_3" aria-selected="false" data-t="3">Reports${
      reportCount(d)?` (${reportCount(d)})`:""}</button>
    <button class="tab" role="tab" id="tab_${b.id}_4" aria-controls="pane_${b.id}_4" aria-selected="false" data-t="4">Sponsors${(d.sponsors||[]).length?` (${(d.sponsors||[]).length})`:""}</button>

    <button class="tab" role="tab" id="tab_${b.id}_5" aria-controls="pane_${b.id}_5"
      aria-selected="false" data-t="5">Documents${
        (d.documents||[]).length?` (${d.documents.length})`:""}</button></div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_0" aria-labelledby="tab_${b.id}_0" tabindex="0" data-t="0">${renderSummary(b,d)}</div>
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

// A bill, as a card small enough to list a hundred of. Clicking goes to the
// bill's own page, which is this app again with that bill open.
function billCard(b){
  const y = b.year || (b.term ? String(b.term).slice(0,4) : "");
  return `<a class="bcard ${KIND[b.kind]||""}" href="bill/${esc(String(y))}/${
    esc(String(b.id||b.bill||"").toLowerCase())}.html">
    <span class="bc-n">${esc(b.n||b.id||b.bill||"")}</span>
    <span class="bc-t">${esc(b.title||"")}</span>
    ${b.status?`<span class="bc-s">${esc(b.status)}</span>`:""}</a>`;
}

// The filter strip above a list of bills: which term, and which outcome.
function billFilters(terms, term, statuses, status){
  return `<div class="bfilt">
    ${terms.length>1?`<label>Term
      <select data-pf="term">${terms.map(t=>
        `<option value="${esc(t)}"${t===term?" selected":""}>${esc(t)}</option>`
      ).join("")}</select></label>`:""}
    <label>Status
      <select data-pf="status">
        <option value="">Any</option>
        ${statuses.map(x=>`<option value="${esc(x)}"${x===status?" selected":""}>${
          esc(x)}</option>`).join("")}
      </select></label>
  </div>`;
}

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
      m.committees.map(c=>esc(c)).join(" &middot; ")}</p>`:""}
    ${m.email?`<p class="pmeta"><a href="mailto:${esc(m.email)}">${esc(m.email)}</a></p>`:""}
  </div>`;
}

function renderMemberBills(m, prime){
  const all = (m.sponsored||[]).filter(b=>!!b.prime===prime);
  if(!all.length)return `<p class="src">${prime
    ?"No bills prime sponsored in the terms on this site."
    :"No bills co-sponsored in the terms on this site."}</p>`;
  const terms=[...new Set(all.map(b=>b.term).filter(Boolean))].sort().reverse();
  const t=PAGE.term&&terms.includes(PAGE.term)?PAGE.term:terms[0];
  const inTerm=all.filter(b=>!terms.length||b.term===t);
  const statuses=[...new Set(inTerm.map(b=>b.status).filter(Boolean))].sort();
  const shown=inTerm.filter(b=>!PAGE.status||b.status===PAGE.status);
  return billFilters(terms,t,statuses,PAGE.status||"")
    + `<p class="src">${shown.length.toLocaleString()} bill${shown.length===1?"":"s"}${
        prime?" prime sponsored":" co-sponsored"}. Sponsoring a bill is putting a
        name to it, which is not the same as voting for it and is not counted as
        one here.</p>`
    + `<div class="bcards">${shown.map(billCard).join("")}</div>`;
}

function renderMemberVotes(m){
  const v=m.votes||[];
  if(!v.length)return `<p class="src">No recorded roll call votes. Voice and
    division votes leave no record of individual members, so a member can have
    taken part in many votes and appear in none of them.</p>`;
  const q=(PAGE.vfilter||"").toLowerCase();
  const rows=v.filter(x=>!q||String(x.v||"").toLowerCase()===q);
  const tally={};
  v.forEach(x=>{tally[x.v]=(tally[x.v]||0)+1;});
  return `<div class="bfilt"><label>Vote
      <select data-pf="vfilter"><option value="">Any</option>
      ${Object.keys(tally).sort().map(k=>`<option value="${esc(k.toLowerCase())}"${
        q===k.toLowerCase()?" selected":""}>${esc(k)} (${tally[k]})</option>`).join("")}
      </select></label></div>
    <p class="src">${rows.length.toLocaleString()} of ${v.length.toLocaleString()}
      recorded votes, newest first. Every roll call this member is recorded in,
      as it was cast and on what. Nothing here is rated or scored.</p>
    <table class="votes"><thead><tr><th>Date</th><th>Bill</th><th>Question</th>
      <th>Vote</th></tr></thead><tbody>${rows.slice(0,600).map(x=>`<tr>
      <td class="d">${esc(x.d||"")}</td>
      <td class="b"><a href="bill/${esc(String(x.y||yearOf(x.b)||""))}/${
        esc(String(x.b||"").toLowerCase())}.html">${esc(x.b||"")}</a></td>
      <td>${esc(x.q||"")}</td><td class="v">${esc(x.v||"")}</td></tr>`).join("")}
      </tbody></table>
    ${rows.length>600?`<p class="src">Showing the most recent 600 of ${
      rows.length.toLocaleString()}.</p>`:""}`;
}

function renderMember(m){
  const nPrime=(m.sponsored||[]).filter(b=>b.prime).length;
  const nCo=(m.sponsored||[]).length-nPrime;
  const tabs=[["Prime sponsored",nPrime],["Co-sponsored",nCo],
              ["Votes",(m.votes||[]).length]];
  const body=[()=>renderMemberBills(m,true),()=>renderMemberBills(m,false),
              ()=>renderMemberVotes(m)][PAGE_TAB]||(()=>"");
  return renderMemberHead(m)
    + `<div class="tabs" role="tablist">${tabs.map((t,i)=>
        `<button class="tab" role="tab" data-pt="${i}" aria-selected="${
          i===PAGE_TAB}">${esc(t[0])}${t[1]?` (${t[1].toLocaleString()})`:""}</button>`
      ).join("")}</div>
      <div class="pane" role="tabpanel" tabindex="0">${body()}</div>`;
}

// ------------------------------------------------------------- committee ---
function renderCommitteeHead(c){
  const lead=(c.members||[]).filter(m=>m.role&&m.role!=="Member");
  const rest=(c.members||[]).filter(m=>!m.role||m.role==="Member");
  const chip=m=>`<span class="mchip p-${esc((m.party_code||"X"))}">${
    m.slug?`<a href="legislator/${esc(m.slug)}.html">${esc(m.label||m.name)}</a>`
          :esc(m.label||m.name)}${m.role&&m.role!=="Member"
      ?` <i>${esc(m.role)}</i>`:""}</span>`;
  return `<div class="phead">
    <h1>${esc(c.name||"")}</h1>
    <p class="pmeta">${esc(c.chamber==="S"?"State Senate":"House of Representatives")}
      ${c.room?` &middot; Room ${esc(c.room)}`:""}${c.phone?` &middot; ${esc(c.phone)}`:""}
      ${c.aide?` &middot; Aide: ${esc(c.aide)}`:""}</p>
    ${lead.length?`<p class="plead">${lead.map(chip).join(" ")}</p>`:""}
    ${rest.length?`<details class="mroster"><summary><span class="caret"></span>
      ${rest.length} more member${rest.length===1?"":"s"}</summary>
      <p class="mlist">${rest.map(chip).join(" ")}</p></details>`:""}
    ${c.url?`<p class="src"><a href="${esc(c.url)}" target="_blank"
      rel="noopener">This committee on gencourt &#8599;</a></p>`:""}
  </div>`;
}

function renderCommitteeBills(c){
  const terms=Object.keys(c.bills||{}).sort().reverse();
  if(!terms.length)return `<p class="src">No bills referred to this committee
    in the terms on this site.</p>`;
  const t=PAGE.term&&terms.includes(PAGE.term)?PAGE.term:terms[0];
  const inTerm=(c.bills[t]||[]);
  const statuses=[...new Set(inTerm.map(b=>b.status).filter(Boolean))].sort();
  const shown=inTerm.filter(b=>!PAGE.status||b.status===PAGE.status);
  return billFilters(terms,t,statuses,PAGE.status||"")
    + `<p class="src">${shown.length.toLocaleString()} bill${
        shown.length===1?"":"s"} referred to this committee in ${esc(t)}.</p>`
    + `<div class="bcards">${shown.map(billCard).join("")}</div>`;
}

function renderCommitteeSessions(c){
  const ss=c.sessions||[];
  if(!ss.length)return `<p class="src">No sitting day of this committee is on
    record. Committees that no longer meet keep their page so the bills they
    handled still have somewhere to point.</p>`;
  const terms=[...new Set(ss.map(s=>s.term).filter(Boolean))].sort().reverse();
  const t=PAGE.term&&terms.includes(PAGE.term)?PAGE.term:terms[0];
  const shown=ss.filter(s=>!terms.length||s.term===t);
  return (terms.length>1?billFilters(terms,t,[],""):"")
    + `<p class="src">${shown.length.toLocaleString()} sitting day${
        shown.length===1?"":"s"}, newest first. What was taken up and when,
        composed from the record rather than written.</p>`
    + shown.map(s=>`<section class="cday">
        <h3>${esc(fdate(s.date))}</h3>
        <p class="cnarr">${esc(s.narrative||"")}</p>
        <ul class="tl">${(s.items||[]).map(i=>`<li>
          <span class="d">${i.start!=null?hms(i.start):"&mdash;"}</span>
          <span class="w"><a href="bill/${esc(String(i.year||""))}/${
            esc(String(i.bill||"").toLowerCase())}.html">${esc(i.n||i.bill||"")}</a>
            &mdash; ${esc(i.kind||"")}${i.title?`<span class="ctitle">${
              esc(i.title)}</span>`:""}
            ${i.video_id&&i.start!=null?` <a class="cite" target="_blank"
              rel="noopener" href="https://www.youtube.com/watch?v=${
                esc(i.video_id)}&t=${Math.max(0,Math.floor(i.start)-2)}s">watch
              from ${hms(i.start)} &#8599;</a>`:""}</span></li>`).join("")}</ul>
        ${s.video_id?`<p class="src"><a href="https://www.youtube.com/watch?v=${
          esc(s.video_id)}" target="_blank" rel="noopener">the whole day's
          recording &#8599;</a></p>`:""}
      </section>`).join("");
}

function renderCommittee(c){
  const nBills=Object.values(c.bills||{}).reduce((a,v)=>a+v.length,0);
  const tabs=[["Bills",nBills],["Sittings",(c.sessions||[]).length]];
  const body=[()=>renderCommitteeBills(c),()=>renderCommitteeSessions(c)][PAGE_TAB]
    ||(()=>"");
  return renderCommitteeHead(c)
    + `<div class="tabs" role="tablist">${tabs.map((t,i)=>
        `<button class="tab" role="tab" data-pt="${i}" aria-selected="${
          i===PAGE_TAB}">${esc(t[0])}${t[1]?` (${t[1].toLocaleString()})`:""}</button>`
      ).join("")}</div>
      <div class="pane" role="tabpanel" tabindex="0">${body()}</div>`;
}

// ------------------------------------------------------------------ boot ---
function renderPage(){
  if(!PAGE)return;
  const el=$("#results");
  if(!el)return;
  el.innerHTML = PAGE.kind==="member" ? renderMember(PAGE.data)
                                      : renderCommittee(PAGE.data);
}

// The tabs and the filter selects on these two pages. Kept apart from the bill
// list's handlers, which key on .card and would not find one here.
document.addEventListener("click",e=>{
  if(!PAGE)return;
  const t=e.target.closest("[data-pt]");
  if(t){PAGE_TAB=+t.dataset.pt;renderPage();}
});
document.addEventListener("change",e=>{
  if(!PAGE)return;
  const f=e.target.dataset.pf;
  if(!f)return;
  PAGE[f]=e.target.value;
  renderPage();
});

function openPage(kind,ref){
  PAGE={kind,data:null,term:"",status:"",vfilter:""};
  // The search chrome belongs to the search. Left up, the facet panel offered
  // filters for a list that is not on screen and the counter read "2,234 of
  // 2,234 bills" beside one member's name.
  const fac=$("#facets"); if(fac){fac.innerHTML="";fac.hidden=true;}
  const sh=document.querySelector(".shell"); if(sh)sh.classList.add("nofacets");
  const c=$("#count"); if(c)c.textContent="";
  const sy=$("#synhint"); if(sy)sy.textContent="";
  const url=DATA(kind==="member"?`legislators/${ref}.json`
                                :`committee/${ref}.json`);
  const el=$("#results");
  if(el)el.innerHTML=`<p class="src">Loading&hellip;</p>`;
  fetch(url).then(r=>{
    if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for this file`);
    return r.json();
  }).then(d=>{PAGE.data=d;renderPage();})
    .catch(e=>{if(el)el.innerHTML=`<div class="empty"><b>This page's record did
      not load.</b><br><br><code>${esc(e.message||e)}</code><br><br>
      The file it wanted is <code>${esc(url)}</code>.</div>`;});
}

function render(){
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
  $("#count").textContent=ids0
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
  const shown=fb?[fb]:rows.slice(0,400);
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
    <article class="card ${openCards.has(b.id)?'open':''}${fb?' focus':''}" data-id="${b.id}">
      ${fb?"":`<a class="detail" href="bill/${b.year}/${esc(b.id.toLowerCase())}.html"
        title="${esc(b.n)} on its own page: its own address, and a link worth sharing"
        aria-label="Open the standalone page for ${esc(b.n)}">&#8599;</a>`}
      <button class="chead" aria-expanded="${openCards.has(b.id)}">
        <div class="crow"><span class="cnum">${esc(b.n)}</span>
        <span class="cyear">filed ${b.year}${b.carried
          ?` <span class="chip" title="Filed one year, acted on in the next — retained in committee or sent to interim study">carried over</span>`:""}</span>
        <span class="cstat ${KIND[b.kind]}">${esc(b.status)}</span></div>
        <div class="ctitle">${esc(b.title)}</div>
        <div class="cmeta">${esc(b.sponsor_label||b.sponsor)}${(b.committees||[b.committee]).filter(Boolean).map(c=>" · "+esc(c)).join("")}${b.topic?" · "+esc(b.topic):""}</div>
      </button>
      <div class="cbody" ${openCards.has(b.id)?"":"hidden"}>${
        openCards.has(b.id)?(detail[dkey(b.id)]?renderDetail(b,detail[dkey(b.id)]):`<p class="spin">Loading…</p>`):""}</div>
    </article>`).join("")+(rows.length>400?`<p class="spin">Showing the first 400. Narrow the search to see more.</p>`:"")
    :(elsewhere.length
      ?`<div class="empty"><b>Not in the ${esc(term)} term.</b><br><br>
        ${elsewhere.map(b=>`${esc(b.n)} exists in the
          <button class="link" data-term="${esc(b.term)}">${esc(b.term)}</button>
          term — ${esc(b.title||"")}`).join("<br>")}</div>`
      :`<div class="empty">No bills match. Try removing a filter, or a different
        term.</div>`));
  rows.filter(b=>openCards.has(b.id)).forEach(b=>{
    const c=document.querySelector(`.card[data-id="${b.id}"]`),t=openTab[b.id]||"0";
    if(!c||!detail[dkey(b.id)])return;
    c.querySelectorAll(".tab").forEach(x=>x.setAttribute("aria-selected",x.dataset.t===t));
    c.querySelectorAll(".pane").forEach(p=>p.hidden=p.dataset.t!==t);
  });
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
  // The address of THIS view, not of a different document.
  //
  // It used to push bill/2026/hb1123.html, so the bar read like a real page
  // and a shared link was crawlable. But that address belongs to the static
  // page: refresh it and the browser fetches that instead, which holds the
  // same facts in a different layout with no charts. The reader had pressed
  // F5 and nothing else, and the page changed under them.
  //
  // A URL should name what is on screen. This one does, and reloading it
  // reopens the same bill in the same view. The static page keeps its own
  // address for crawlers, for the sitemap, for a reader without JavaScript,
  // and for anyone opening the arrow in a new tab -- the anchor still points
  // there, so a middle click gets it.
  const _y=yearOf(id);
  try{history.pushState({focus:id},"",
    `?q=${encodeURIComponent(id.toLowerCase())}#${_y?_y+"/":""}${id}`);}catch(_){}
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
  if(location.hash){
    try{history.replaceState(history.state,"",
      location.pathname+location.search);}catch(_){}
  }
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
  if(detail[dkey(id)]){render();return;}
  render();
  // What went wrong, not merely that something did.
  //
  // This used to report "Detail unavailable" and nothing else, which is how a
  // refresh on a bill page stayed unexplained through two wrong guesses at the
  // cause. A 404, a file that is not JSON, and a refused connection all looked
  // identical from the outside, and they are three different problems.
  const yr=yearOf(id);
  const url=DATA(`bills/${yr}/${id}.json`);
  const fail=(why)=>{
    detail[dkey(id)]={events:[],rollcalls:[],stations:[],reports:[],sponsors:[],
      documents:[],amendments:[],next_step:"Detail unavailable",
      _error:why+"\n"+url};
    render();
  };
  fetch(url).then(r=>{
    if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for this file`);
    return r.text();
  }).then(txt=>{
    let d;
    try{ d=JSON.parse(txt); }
    catch(_){ throw new Error(`the file arrived but is not JSON. It starts: ${
      txt.slice(0,80).replace(/\s+/g," ")}`); }
    detail[dkey(id)]=d; render();
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
  const seg=e.target.closest("[data-seg]");
  if(seg){const[bid,i,which]=seg.dataset.seg.split("|");const k=`${bid}|${i}`;
    segSel[k]=segSel[k]===which?null:which;render();return;}
  const rt=e.target.closest("[data-routine]");
  if(rt){const id=rt.dataset.routine;
    showRoutine.has(id)?showRoutine.delete(id):showRoutine.add(id);
    render();return;}
  const f=e.target.closest("[data-full]");
  if(f){const k=f.dataset.full;fullOpen.has(k)?fullOpen.delete(k):fullOpen.add(k);render();return;}
  const g=e.target.closest(".fhead");
  if(g){openGroups.has(g.dataset.g)?openGroups.delete(g.dataset.g):openGroups.add(g.dataset.g);renderFacets();return;}
  const un=e.target.dataset.unpick;
  if(un){sel.sponsor.delete(un);render();return;}
  // Left click opens in place; a modified or middle click falls through to
  // the anchor and gets the static page in a new tab, which still works.
  const dt=e.target.closest("a.detail");
  if(dt&&e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){
    e.preventDefault();
    focusBill(dt.closest(".card").dataset.id,dt.getAttribute("href"));return;}
  if(e.target.closest("[data-back]")){history.back();return;}
  // Everything below reads .card. A member's or a committee's page has none,
  // so a tab click here threw on tab.closest(".card").dataset and the tab did
  // nothing. Those pages have their own handler, registered above.
  if(PAGE)return;
  const head=e.target.closest(".chead");
  if(head&&!e.target.closest("a")){const id=head.closest(".card").dataset.id;
    if(openCards.has(id)){openCards.delete(id);render();}else openBill(id);return;}
  const tab=e.target.closest(".tab");
  if(tab){openTab[tab.closest(".card").dataset.id]=tab.dataset.t;render();return;}
  const jt=e.target.closest("[data-term]");
  if(jt){term=jt.dataset.term;$("#year").value=term;render();return;}
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
  if(focused)return;
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
