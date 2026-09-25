// GRANITE_VERSION: 2026-09-16.9
/* FIND ANYTHING, FROM THE HEADER (16 September, asked for in these words:
   "a search icon in the header that lets you search for anything including
   legislators, committees, towns, and bills ... searching Litchfield would
   show both the town and Rep Melissa Litchfield").

   The bill search is a page; this is the box on every page for the things that
   are not bills. It reads site/find.json -- 406 sitting members, the 1,785
   who have left, every committee, every town and ward, the 43 subjects and
   the fixed pages: 322 KB, 58 KB over the wire -- fetched once, the first
   time somebody opens the box, so no page pays for it up front. Bills are not
   in that file on purpose: 33,683 rows is more than a megabyte. A bill NUMBER
   is recognised here and offered as the first answer, because that is the
   one bill lookup that needs no index; any other words are also looked for
   in the current term's bills, from that term's own index, fetched the first
   time they are needed -- see BILLS, IN THE SAME BOX below. /search, the
   full results, looks in every term's.

   WHAT 18 SEPTEMBER ADDED, in the person's words:

     "listing them like individual entries" -- one row per thing found, each
     naming what it is, rather than a list of bills with everything else in a
     separate block underneath.

     "Search bar should also list former legislators in the results, but
     prioritize to the most recent bills and current legislators before
     listing former ones", and they are named "Former Rep. David Smith"
     rather than carrying a box that says FORMER. Among themselves they are
     ordered by how recently they sat.

     "You should be able to search for topics in the search bar as well" --
     typing education finds both subjects the General Court files bills
     under, and clicking one opens the bill search on it.

     "Rather than 'See all 19 bills with this number' I'd rather it be a more
     general 'See all search results for (term)'", with "No matching
     results." where nothing is found, and "Did you mean firearms?" when what
     was typed is one or two letters away from something that exists.

     "an x icon that's faint but allows you to clear the field". Built here
     rather than left to the browser's own: Firefox draws none at all, and
     the one Chrome draws cannot be made faint.

   The control is built here rather than in the two files that write the
   header, so there is one of it. */
const FIND={rows:null,loading:null,words:null};
const FKIND={legislator:"Legislator",committee:"Committee",town:"Town",
  page:"Page",former:"Former member",topic:"Subject"};
const _fesc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>(
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function findRows(){
  if(FIND.rows)return Promise.resolve(FIND.rows);
  if(!FIND.loading)FIND.loading=fetch(new URL("find.json",location.origin+"/").href)
    .then(r=>r.json()).then(rows=>(FIND.rows=rows)).catch(()=>(FIND.rows=[]));
  return FIND.loading;
}

/* WHAT THE GENERAL COURT NUMBERS, counted off the record rather than guessed
   at: the 33,683 bills on this site carry seventeen distinct prefixes and no
   others. HB 23,190; SB 8,616; HR 562; CACR 545; HCR 350; SR 147; HJR 117;
   SCR 68; PET 28; SJR 25; HBI 14; HA 9; HCO 2; and the four special-session
   forms SSHB, SSSB, SSHR and SSHCR, ten between them. A closed set, and the
   thing that makes findBill able to answer at all without an index. */
const FBILLKIND=new Set(["HB","SB","CACR","HCR","SCR","HJR","SJR","HR","SR",
  "PET","HBI","HA","HCO","SSHB","SSSB","SSHR","SSHCR"]);

/* A SEAT IS NOT A BILL. Two to five letters and a number is also the shape of
   every district on the roster -- "Hills 29", "Rock 8", "Straf 14", "SD22" --
   and the shape alone was the whole test, so all 223 district labels the
   sitting members carry were offered as "open this bill number in the bill
   search", drawn ABOVE the three representatives who actually sit for Hills
   29. Return takes the first answer, so a reader who typed their own district
   and pressed it landed on "No bills match in the 2025-2026 term." The same
   went for a ward: "Ward 3" read as bill WARD 3.
   The letters are what tell them apart, and the letters are in the data. Not
   one of the seventeen bill prefixes is a county abbreviation -- Belk, Carr,
   Ches, Coos, Graf, Hills, Merr, Rock, Straf, Sull -- or the Senate's SD, and
   not one county abbreviation is a bill prefix, so the set separates them
   cleanly with nothing left over.
   A number whose prefix is NOT in the set is not a dead end: the panel still
   offers "search every bill for these words" with what was typed, and the
   bill search's own billNumbers() reads any two-to-five letters and digits as
   a number. So a kind the General Court invents tomorrow still arrives at the
   bill, it just is not promoted to the top of this list before it exists.

   A bill number typed in any of the ways people write one: hb115, HB 115,
   "hb 0115". Offered without looking anything up, and handed to the bill
   search, which knows which term is on screen. */
function findBill(q){
  const m=/^\s*([a-z]{2,5})\s*0*(\d{1,4})\s*$/i.exec(q||"");
  if(!m)return "";
  const kind=m[1].toUpperCase();
  return FBILLKIND.has(kind)?`${kind} ${m[2]}`:"";
}

// A former member's row is named "Former Rep. Suzanne Vail", and the word
// Former is ours, not part of her name. Ranking against the whole string
// would put all 1,785 of them at the top the moment somebody typed "for",
// and would stop "vail" from being a name that STARTS with what was typed.
const _fbare=s=>String(s||"").replace(/^Former /,"");

// A name that starts with what was typed first, then one with a word
// starting with it -- "Litchfield" puts the town and Rep. Litchfield above
// anyone whose town or committee merely mentions it -- then the rest. `s` is
// the query lowercased and trimmed; `edge` is _fedge(s).
const _fedge=s=>new RegExp("\\b"+s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
function _frank(r,s,edge){
  const name=_fbare(r[1]).toLowerCase();
  return name.startsWith(s)?0:edge.test(name)?1:2;
}

/* A NAME GOES ABOVE THE BILLS ONLY ON A WHOLE WORD (the person, 24
   September: "Should a name like Rep. Bailey outrank bail bills only on a
   whole-word match?" -- "Yes"). A name that merely STARTED with what was
   typed was enough, so "bail" put Rep. Glenn Bailey above the term's bail
   bills, and Return opened his page for a reader who had asked about bail.
   Now a sitting member, committee, town or subject goes above the bills only
   when every word typed is a whole word of its name -- "bailey", "glenn
   bailey", "rep. bailey", "litchfield", "education" -- and part of a word
   ("bail", "litch") leaves the bills first with the name under them. This
   decides which side of the bills a name falls; among the names, the same
   test orders them (_fpart, below), and then _frank. A letter or digit in
   any alphabet belongs to its word, so "2" is not whole in "Straf 20", and
   "josé" is whole in José. */
const _fwords=s=>String(s||"").toLowerCase().split(/\s+/)
  .map(w=>w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu,"")).filter(Boolean);
const _fisword=(name,w)=>new RegExp("(^|[^\\p{L}\\p{N}])"
  +w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"(?![\\p{L}\\p{N}])","u").test(name);
function _fwhole(r,s){
  const name=_fbare(r[1]).toLowerCase();
  const words=_fwords(s);
  return words.length>0&&words.every(w=>_fisword(name,w));
}

/* THE WORD ITSELF FIRST, AMONG THE NAMES TOO (the person, 25 September:
   "have direct word matches be at the top of the best match sorting"). What
   was typed also finds a name it only begins -- "gun" finds former Rep.
   Michael Gunski, "bail" Rep. Glenn Bailey -- and that stays, lower down:
   a name that has every word typed as a whole word of it, by _fwhole's test,
   comes first. So "hill" lists Hill, Sugar Hill and the members named Hill
   before Hillsborough and the Hills districts' members, and "sd2" the
   senator for SD2 before those for SD20 to SD24. A sitting member's name
   carries their seat, so "merr" lists the Merr districts' members before
   the town of Merrimack, as "hills 29" always has. This counts the words
   typed that are not a whole word of the name, and findMatch orders by it
   before anything else. */
function _fpart(r,s){
  const name=_fbare(r[1]).toLowerCase();
  return _fwords(s).filter(w=>!_fisword(name,w)).length;
}

// `limit` is the panel's eight by default. /search passes Infinity: it is a
// page and not a dropdown, so it shows everything that matched -- which is the
// whole reason it exists.
function findMatch(q,limit){
  const s=(q||"").trim().toLowerCase();
  if(!s||!FIND.rows)return [];
  const words=s.split(/\s+/);
  const edge=_fedge(s);
  const hit=[];
  for(const r of FIND.rows){
    const hay=`${r[1]} ${r[2]} ${r[4]||""}`.toLowerCase();
    if(!words.every(w=>hay.includes(w)))continue;
    const name=_fbare(r[1]).toLowerCase();
    const rank=_frank(r,s,edge);
    // Match quality decides first -- the words typed as whole words of the
    // name (_fpart), then where in the name they fall (_frank) -- and only
    // then does a member who has left fall in behind one who has not: that
    // is what "prioritize ... current legislators before listing former
    // ones" means with a list this long. A former member whose name begins
    // with the query still outranks a town that merely mentions it, which is
    // the answer a reader wants.
    const gone=r[0]==="former"?1:0;
    // Among former members, the most recent first. r[5] is the year they last
    // sat; negated so one sort direction serves both this and name length.
    hit.push([_fpart(r,s),rank,gone,gone?-(r[5]||0):0,name.length,r]);
  }
  hit.sort((a,b)=>a[0]-b[0]||a[1]-b[1]||a[2]-b[2]||a[3]-b[3]||a[4]-b[4]);
  return hit.slice(0,limit||8).map(x=>x[5]);
}

/* DID YOU MEAN. Only when nothing at all was found, because that is the only
   time it can help and the only time the cost is worth paying: the distance
   is measured against every distinct word in the index, which is a few
   thousand, and a keystroke that DOES find something never runs it.

   Bounded at two edits and abandoned early -- a row of the matrix whose best
   cell already exceeds the bound cannot come back under it -- so a long word
   costs almost nothing. Two edits rather than one because "firarms" is one
   deletion from "firearms" but "comittee" is two from "committee", and a
   reader who has mistyped twice needs the offer more, not less. */
function _fdist(a,b,max){
  if(Math.abs(a.length-b.length)>max)return max+1;
  let prev=Array.from({length:b.length+1},(_,i)=>i);
  for(let i=1;i<=a.length;i++){
    const cur=[i];
    let best=i;
    for(let j=1;j<=b.length;j++){
      const v=Math.min(prev[j]+1,cur[j-1]+1,
        prev[j-1]+(a.charCodeAt(i-1)===b.charCodeAt(j-1)?0:1));
      cur[j]=v;
      if(v<best)best=v;
    }
    if(best>max)return max+1;
    prev=cur;
  }
  return prev[b.length];
}

// Built once. "Former" and the titles are left out: they are our words on
// every one of 1,785 rows, so they would be offered for anything vaguely
// like them and mean nothing when followed.
const FSTOP=new Set(["former","rep.","sen.","rep","sen","house","senate",
  "county","ward","committee","the","and","for"]);
function findWords(){
  if(FIND.words)return FIND.words;
  const w=new Set();
  for(const r of (FIND.rows||[]))
    for(const t of String(r[1]).toLowerCase().split(/[^a-z0-9']+/))
      if(t.length>3&&!FSTOP.has(t))w.add(t);
  FIND.words=Array.from(w);
  return FIND.words;
}

function findSuggest(q){
  const s=(q||"").trim().toLowerCase();
  // One word, and long enough that a two-edit neighbourhood still means
  // something: at four letters nearly everything is two edits from
  // everything, and the offer would be noise.
  if(!/^[a-z][a-z'-]{4,}$/.test(s))return "";
  let best="",dist=3;
  for(const w of findWords()){
    const d=_fdist(s,w,2);
    if(d<dist||(d===dist&&w.length<best.length)){best=w;dist=d;}
  }
  return dist<=2?best:"";
}

// ROOT-RELATIVE, ALWAYS. find.json's rows all carry a relative path, and
// this panel is mounted on every page -- including 404.html, which has no
// <base href="/"> because it is served from the root and never needed one. On
// a Pages 404 the address stays at the depth that was asked for, so
// "legislator/x" resolved under it and every answer in the panel was a dead
// link. Making the href root-relative here fixes it wherever the panel is
// mounted, rather than teaching one more page about <base>.
function _froot(h){
  h = String(h || "");
  return /^([a-z]+:|\/)/i.test(h) ? h : "/" + h;
}

// The part of a name a reader actually typed, marked. Escaped on both sides of
// the mark rather than escaping afterwards, so the tags we add are the only
// ones in the string. The first occurrence only: a second mark in one name
// reads as emphasis rather than as a match.
function _fmark(text,q){
  const t=String(text==null?"":text),s=(q||"").trim();
  if(!s)return _fesc(t);
  const i=t.toLowerCase().indexOf(s.toLowerCase());
  if(i<0)return _fesc(t);
  return _fesc(t.slice(0,i))+"<mark>"+_fesc(t.slice(i,i+s.length))+"</mark>"
    +_fesc(t.slice(i+s.length));
}

/* BILLS, IN THE SAME BOX (24 September). Until then this panel searched
   find.json alone, which has no bills in it on purpose -- so "firearms",
   "abortion", "property tax" and "housing" were answered "No matching
   results." while the bill search held 12 to 119 bills of this term for each
   of them; "guns" and Return opened a former representative named Gunski;
   and "voting" was offered "Did you mean zoning?". Its one road to the bills
   ran through /search, which said nothing matched before it offered them.
   The person had asked for this box to search "anything including
   legislators, committees, towns, and bills", and to "prioritize to the most
   recent bills and current legislators before listing former ones".

   So it searches the current term's bills as well, and counts them with the
   bill search's own matcher -- app.js's, which a page that does not run
   app.js loads as billmatch.js, cut out of app.js by build_pages.py -- so
   that "All 30 bills that mention firearms" is the number /bills?q=firearms
   then shows. The term is the one /bills opens on: away from a bill's own
   page app.js's wantedTerm() takes the first of meta.json's terms, and so
   does this. That term's index is about 135 KB over the wire, fetched the
   first time somebody types something that is not a bill number and kept
   for the rest of the visit; opening the box, or looking up HB 1442, costs
   nothing.

   When any of that fails the panel still offers the bill search for what
   was typed, without a count, and does not say whether anything matched --
   it cannot know.

   THE PANEL IS THIS TERM'S; /search IS EVERY TERM'S. The person, 24
   September, asked whether the header's search covering the current term
   only was right: "Yes for bills in the search preview, but all terms
   should show up in the full search results". So the panel stays as it is,
   and /search, which reads this file too, loads the other terms' indexes
   through findBillsLoadAll below. */
const FBILLS={rows:null,file:null,term:"",terms:[],api:null,loading:null,
  failed:false,redraw:false};
// The three haystacks exactly as app.js's ensureTerm() builds them.
function _fprep(rows){
  const norm=s=>String(s||"").toLowerCase().replace(/-/g," ");
  return (Array.isArray(rows)?rows:[]).map(b=>{
    b.hayT=norm([b.id,b.n,b.title].join(" "));
    b.hayS=norm(b.sponsor);
    b.hayC=norm((b.committees||[b.committee||""]).join(" | "));
    return b;});
}
function _fbillApi(){
  // On bills.html and every record page, app.js is already loaded.
  if(typeof queryGroups==="function"&&typeof groupWeight==="function"
     &&typeof billNumbers==="function"&&typeof billKey==="function"
     &&typeof looseness==="function")
    return {queryGroups,groupWeight,billNumbers,billKey,looseness};
  return window.GR_BILLMATCH||null;
}
const _fdata=f=>new URL(f,location.origin+"/").href;
function _fjson(f){
  return fetch(_fdata(f)).then(r=>{
    if(!r.ok)throw new Error(`${f} returned ${r.status}`);
    return r.json();});
}
function _fscript(f){
  return new Promise((ok,no)=>{
    const s=document.createElement("script");
    s.src=_fdata(f);s.onload=ok;s.onerror=()=>no(new Error(`${f} did not load`));
    document.head.appendChild(s);
  });
}
function findBillsLoad(){
  if(FBILLS.rows||FBILLS.failed)return Promise.resolve(!!FBILLS.rows);
  if(!FBILLS.loading)FBILLS.loading=Promise.all([
    _fbillApi()?null:_fscript("billmatch.js"),
    _fjson("meta.json").then(m=>{
      FBILLS.terms=((m&&m.terms)||[]).slice();
      FBILLS.term=FBILLS.terms[0]||"";
      if(!FBILLS.term)throw new Error("meta.json names no term");
      return _fjson("idx/"+encodeURIComponent(FBILLS.term)+".json");
    })
  ]).then(([,rows])=>{
    const api=_fbillApi();
    if(!api||!Array.isArray(rows))throw new Error("no matcher, or no bills");
    // The file whole, for every term's count below, and the rows app.js's
    // inTermOf() keeps for this one.
    FBILLS.file=_fprep(rows);
    FBILLS.rows=FBILLS.file.filter(b=>!b.term||b.term===FBILLS.term);
    FBILLS.api=api;
    return true;
  }).catch(()=>{FBILLS.failed=true;return false;});
  return FBILLS.loading;
}

/* EVERY TERM'S BILLS, for /search only. The other eighteen indexes, about
   2.2 MB over the wire between them where the current term's is 135 KB, so
   the panel never asks for them: /search does, once a reader has searched
   for something, and after the current term, whose answer it shows first.
   The rows are every file's, concatenated, as app.js's IDX holds them when
   /bills is opened on "All terms" -- so "All 412 bills" here is the count
   /bills?q=...&term=all then shows. If any term cannot be had, none of them
   is counted: a number short by a term is a wrong number, and /search falls
   back to the current term's, which it can stand behind. */
const FALL={rows:null,terms:[],loading:null,failed:false};
function findBillsLoadAll(){
  if(FALL.rows||FALL.failed)return Promise.resolve(!!FALL.rows);
  if(!FALL.loading)FALL.loading=findBillsLoad().then(ok=>{
    if(!ok)throw new Error("the current term did not load");
    return Promise.all(FBILLS.terms.filter(t=>t!==FBILLS.term).map(t=>
      _fjson("idx/"+encodeURIComponent(t)+".json").then(rows=>{
        if(!Array.isArray(rows))throw new Error(`idx/${t}.json holds no list`);
        return _fprep(rows);})));
  }).then(parts=>{
    FALL.rows=FBILLS.file.concat(...parts);
    FALL.terms=FBILLS.terms.slice();
    return true;
  }).catch(()=>{FALL.failed=true;return false;});
  return FALL.loading;
}

/* What /bills?q= lists for this, in the order it lists them: {state:"ready",
   n, term, top} once the index is here; {state:"loading"} or
   {state:"failed"} until then; and null for a search with nothing in it to
   match -- "?" on its own, which the bill search reads as every bill. The
   order is app.js's "best match" (its looseness, scoreOf and sortRows):
   every word of the search as a word of the title or the sponsor's name
   before the start of a longer one -- "bail" before "bailiffs" -- then the
   most of the search in the title, then the sponsor, then the committee, the
   search's own words in order worth two more, and bill number within each.
   A search for bill numbers is number order.

   `allTerms` counts every term's bills (findBillsLoadAll) where /bills
   would with ?term=all. A bill number is unique only within a term, so
   there the ties between terms go to the newer term -- app.js's sortRows
   breaks them the same way -- which puts this term's answer ahead of
   1995's. */
function findBills(q,limit,allTerms){
  const s=(q||"").trim();
  if(!s)return null;
  const src=allTerms?FALL:FBILLS;
  if(!src.rows)return {state:src.failed?"failed":"loading"};
  const A=FBILLS.api,ids=A.billNumbers(s);
  let gs=null,words="";
  if(!ids){
    gs=A.queryGroups(s);
    if(!gs.length)return null;
    words=gs.map(g=>g.word).join(" ");
  }
  const hit=[];
  for(const b of src.rows){
    let sc=0,loose=0;
    if(ids){if(!ids.includes(String(b.id).toUpperCase()))continue;}
    else{
      let every=true;
      for(const g of gs){const w=A.groupWeight(b,g);if(!w){every=false;break;}sc+=w;}
      if(!every)continue;
      if(gs.length>1&&b.hayT.includes(words))sc+=2;
      loose=A.looseness(b,gs);
    }
    hit.push([sc,A.billKey(b),b,loose]);
  }
  const newer=(x,y)=>{const a=String(x[2].term||""),b=String(y[2].term||"");
    return a<b?1:a>b?-1:0;};
  const num=(x,y)=>x[1][0]-y[1][0]||x[1][1]-y[1][1];
  hit.sort(ids?(x,y)=>num(x,y)||newer(x,y)
    :(x,y)=>x[3]-y[3]||y[0]-x[0]||newer(x,y)||num(x,y));
  return {state:"ready",n:hit.length,term:FBILLS.term,every:!!allTerms,
          terms:allTerms?FALL.terms:[FBILLS.term],numbers:!!ids,
          top:hit.slice(0,limit==null?3:limit).map(h=>h[2])};
}

// One bill as a row: its number, and its title under it. A resolution's
// title can run past 600 characters, and a row is read at a glance. `dated`
// names the year as the bill's own page does -- "SB 412 (2000)" -- for a
// list that crosses terms, where the number alone names nineteen bills.
function findBillRow(b,q,dated){
  const y=String(b.year||String(b.term||"").slice(0,4));
  let t=String(b.title||"");
  const cut=t.length>160;
  if(cut)t=t.slice(0,157).replace(/\s+\S*$/,"");
  return `<a href="/bill/${encodeURIComponent(y)}/${encodeURIComponent(String(b.id).toLowerCase())}">
    <span class="fl1"><span class="fname">${_fesc(b.n||b.id)}${dated&&y?` (${_fesc(y)})`:""}</span>
    <span class="fkind">Bill</span></span>
    ${t?`<span class="fwhat">${_fmark(t,q)}${cut?"&hellip;":""}</span>`:""}</a>`;
}

// "1989 to 2026", from the terms newest first.
function _fspan(terms){
  const a=String(terms[terms.length-1]||"").slice(0,4),b=String(terms[0]||"").slice(-4);
  return a&&b?`${a} to ${b}`:"";
}

// The row that opens the bill search on what was typed: "All N bills that
// mention" it once they are counted, and a plain offer before then or when
// they could not be. `what` is a sentence about the bill search, for /search.
// Counted across every term, it opens the bill search on All terms.
function findBillsAll(B,q,what){
  const quoted=`&ldquo;${_fesc(q)}&rdquo;`;
  const ready=B&&B.state==="ready";
  const every=ready&&B.every;
  // "HB 1, SB 5" is a list of numbers, not words a bill mentions.
  const verb=B&&B.numbers?["numbered","numbered"]:["that mentions","that mention"];
  const name=ready?(B.n===1?`1 bill ${verb[0]} ${quoted}`
      :`All ${B.n.toLocaleString()} bills ${verb[1]} ${quoted}`)
    :`Search the bills for ${quoted}`;
  const where=every?`In all ${B.terms.length} terms, ${_fspan(B.terms)}.`
    :ready?`In the ${_fesc(B.term)} term.`
    :B&&B.state==="loading"?"Counting this term&rsquo;s bills&hellip;":"";
  const line=[where,what||(where?"":"In the bill search.")].filter(Boolean).join(" ");
  return `<a class="fbills" href="/bills?q=${encodeURIComponent(q)}${every?"&amp;term=all":""}">
    <span class="fl1"><span class="fname">${name}</span></span>
    <span class="fwhat">${line}</span></a>`;
}

function findDraw(q){
  const out=document.getElementById("findout");
  if(!out)return;
  const s=(q||"").trim();
  const clr=document.getElementById("findclear");
  if(clr)clr.hidden=!s;
  if(!s){out.innerHTML=`<p class="fnote">Type a legislator, a committee, a
    town, a subject, a bill number or words from a bill&rsquo;s title.</p>`;return;}
  const num=findBill(s);
  const rows=findMatch(s);
  // THE ONE LINE THAT LEAVES THE PANEL, and it leads to two different places.
  // A bill number is a bill, so it goes to the bill search, which is the page
  // that answers it. Anything else goes to /search, which reads this same
  // index with the eight-row cap off -- it used to go to the bill search too,
  // so a reader who typed Concord was shown eight of its wards and then sent
  // to a search with no towns in it at all.
  //
  // A BILL NUMBER GETS BOTH (24 September). The bill search opens on this
  // term, so "SB 412" led to this term's SB 412 and nowhere else, and the
  // 2000 bill a reader may have meant was a term picker away. /search lists
  // the number in every term, so it is offered under the number.
  const every=`<a class="fall" href="/search?q=${encodeURIComponent(s)}">
    <span class="fl1"><span class="fname">See all search results for ${_fesc(s)}</span></span>
    <span class="fwhat">${num?"this number in every term since 1989"
      :"every member, committee, town and subject that matches, and the bills of every term"
      }</span></a>`;
  const all=num?`<a class="fall" href="/bills?q=${encodeURIComponent(num)}">
    <span class="fl1"><span class="fname">${_fesc(num)}</span></span>
    <span class="fwhat">open this bill number in the bill search</span></a>`:every;
  const row=r=>`<a href="${_fesc(_froot(r[3]))}">
      <span class="fl1"><span class="fname">${_fmark(r[1],s)}</span>
      <span class="fkind">${_fesc(FKIND[r[0]]||r[0])}</span></span>
      ${r[2]?`<span class="fwhat">${_fesc(r[2])}</span>`:""}</a>`;
  // The bills, for anything that is not a bill number: the count and the
  // first three. Hidden once counted at none, because "All 0 bills" is not an
  // answer; shown uncounted while they are fetched, and redrawn when they
  // arrive with whatever is in the box by then.
  const B=num?null:findBills(s,3);
  if(B&&B.state==="loading"&&!FBILLS.redraw){
    FBILLS.redraw=true;
    findBillsLoad().then(()=>{
      const box=document.getElementById("findq");
      if(box)findDraw(box.value);});
  }
  const counted=B&&B.state==="ready";
  const bills=B&&(!counted||B.n)?findBillsAll(B,s)
    +(counted?B.top.map(b=>findBillRow(b,s)).join(""):""):"";
  // WHERE THE BILLS GO: after the sitting members, committees, towns and
  // subjects that have every word typed as a whole word of their name
  // (_fwhole), and ahead of everything else, which is every former member
  // and anything whose name only starts with it or only mentions it. So
  // "Litchfield" still leads with the town and Rep. Litchfield, while "guns"
  // leads with the bills and Gunski follows, and "bail" leads with the bail
  // bills and Rep. Bailey follows. Return takes the first row, so for a
  // subject word it opens the bill search on it.
  const named=rows.filter(r=>r[0]!=="former"&&_fwhole(r,s));
  const list=named.map(row).join("")+bills
    +rows.filter(r=>!named.includes(r)).map(row).join("");
  // "No matching results." -- the person's words -- only when nothing here
  // and no bill matches; "Did you mean" only when no bill does either, since
  // its guesses come from names alone ("voting" was offered "zoning" over
  // 141 bills). While the bills are being counted, neither: it is not known.
  let tail="";
  if(!rows.length&&!num&&(!B||(counted&&!B.n)||B.state==="failed")){
    const none=!B||counted?"No matching results.":"";
    const did=findSuggest(s);
    if(none||did)tail=`<p class="fnote">${none}${did?`${none?" ":""}Did you mean
      <button type="button" class="fdym" data-q="${_fesc(did)}">${_fesc(did)}</button>?`
      :""}</p>`;
  }
  out.innerHTML=num?all+list+every+tail:list+all+tail;
}

function findMount(){
  const bar=document.querySelector("nav.top .in");
  if(!bar||document.getElementById("findbtn"))return;
  const btn=document.createElement("button");
  btn.id="findbtn";btn.className="findbtn";btn.type="button";
  btn.setAttribute("aria-expanded","false");
  btn.setAttribute("aria-controls","findpanel");
  btn.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" '
    +'cy="11" r="7"/><path d="M16.5 16.5 21 21"/></svg><span>Search</span>';
  // BEFORE THE MENU BUTTON, NOT BEFORE THE THEMER. The theme control moved
  // inside .navdrop so that a phone can fold it behind the menu with the
  // sections; insertBefore requires its reference to be a CHILD of the node
  // it is called on, so reaching for #themer here threw and the search
  // button never mounted. The menu button is a direct child, and appending
  // is the right answer when it is absent.
  const after=document.getElementById("navmenu");
  if(after&&after.parentNode===bar)bar.insertBefore(btn,after);
  else bar.appendChild(btn);
  // The scrim is the phone's way out. The panel there is a sheet that leaves
  // the edge of the page showing, asked for in these words: "rather than
  // taking up the full screen, I was imagining something more like it taking
  // up a decent amount of the screen with the outer edge still showing the
  // page you were on and if you tap on it, it'll take you out of the search
  // menu." So the strip that is still showing is the control that closes it.
  // On a desktop the stylesheet never shows this.
  const scrim=document.createElement("div");
  scrim.className="findscrim";scrim.hidden=true;
  const panel=document.createElement("div");
  panel.id="findpanel";panel.className="findpanel";panel.hidden=true;
  panel.innerHTML=`<div class="findin">
    <div class="findgrab" aria-hidden="true"></div>
    <div class="findtop">
    <div class="findbox">
      <label class="sr" for="findq">Search for a legislator, committee, town, subject or bill</label>
      <input id="findq" type="search" autocomplete="off" placeholder="A legislator, a town, a subject or a bill">
      <button type="button" class="findclear" id="findclear" hidden aria-label="Clear the search box">&#10005;</button>
    </div>
    <button type="button" class="findcancel" id="findcancel">Cancel</button>
    </div>
    <div class="findout" id="findout"></div></div>`;
  const nav=document.querySelector("nav.top");
  nav.parentNode.insertBefore(scrim,nav.nextSibling);
  nav.parentNode.insertBefore(panel,scrim.nextSibling);
  const box=panel.querySelector("#findq");
  const clr=panel.querySelector("#findclear");
  const shut=()=>{
    panel.hidden=true;scrim.hidden=true;
    document.documentElement.classList.remove("findopen");
    btn.setAttribute("aria-expanded","false");
  };
  const open=()=>{
    panel.hidden=false;scrim.hidden=false;
    document.documentElement.classList.add("findopen");
    btn.setAttribute("aria-expanded","true");
    findDraw(box.value);box.focus();findRows().then(()=>findDraw(box.value));
  };
  btn.addEventListener("click",()=>{panel.hidden?open():shut();});
  box.addEventListener("input",()=>findDraw(box.value));
  // Clearing puts the reader back in the box with it empty, which is what
  // they are about to want; leaving focus on a button they just emptied
  // would mean a second click to type again.
  clr.addEventListener("click",()=>{box.value="";findDraw("");box.focus();});
  // The offer is a button rather than a link because it searches again here
  // rather than going anywhere.
  document.getElementById("findpanel").addEventListener("click",e=>{
    const d=e.target.closest(".fdym");
    if(!d)return;
    box.value=d.dataset.q||"";findDraw(box.value);box.focus();
  });
  box.addEventListener("keydown",e=>{
    if(e.key==="Escape"){shut();btn.focus();}
    // Return takes the first answer, which is what a reader who typed a name
    // and looked at the list is about to click -- and, for a word no name
    // starts with, the bill search on that word (see findDraw).
    if(e.key==="Enter"){const a=panel.querySelector(".findout a");if(a){e.preventDefault();location.href=a.href;}}
  });
  // A WAY OUT THAT IS NOT THE SCRIM. On a phone the sheet covers the page and
  // the only way back was to tap the dimmed strip above it or press Escape --
  // neither of which a thumb goes looking for. Shown only at sheet widths; on
  // a desktop the panel is a dropdown and the scrim is right beside it.
  const cancel=panel.querySelector("#findcancel");
  if(cancel)cancel.addEventListener("click",shut);
  scrim.addEventListener("click",shut);
  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!panel.hidden)shut();});
  document.addEventListener("click",e=>{
    if(!panel.hidden&&!panel.contains(e.target)&&e.target!==btn&&!btn.contains(e.target)
       &&e.target!==scrim)shut();
  });
}
/* THE SECTIONS, FOLDED BEHIND ONE BUTTON ON A PHONE.

   It lives here because this file already mounts into nav.top on every page,
   and a second script for one toggle would be a second thing to load and to
   keep in step with the markup.

   The panel is the SAME .navdrop the desktop lays out inline -- there is one
   copy of the sections in the document, not two -- so a reader on a phone and
   a reader on a desktop are looking at the same links, and a section added to
   one is added to both. */
function menuMount(){
  const nav=document.querySelector("nav.top");
  const btn=document.getElementById("navmenu");
  const drop=document.getElementById("navdrop");
  if(!nav||!btn||!drop)return;
  const shut=()=>{nav.classList.remove("open");btn.setAttribute("aria-expanded","false");};
  const open=()=>{nav.classList.add("open");btn.setAttribute("aria-expanded","true");};
  btn.addEventListener("click",()=>{
    nav.classList.contains("open")?shut():open();
  });
  // Escape closes and returns the focus to the control that opened it, which
  // is where a keyboard reader expects to be left.
  document.addEventListener("keydown",e=>{
    if(e.key==="Escape"&&nav.classList.contains("open")){shut();btn.focus();}
  });
  document.addEventListener("click",e=>{
    if(nav.classList.contains("open")&&!drop.contains(e.target)&&!btn.contains(e.target))shut();
  });
  // Following a link inside the panel navigates away; closing first means the
  // panel is not left open behind a page that has already changed, which is
  // what a browser's back button would otherwise show.
  drop.addEventListener("click",e=>{if(e.target.closest("a"))shut();});
}

findMount();
menuMount();
