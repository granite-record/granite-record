// GRANITE_VERSION: 2026-09-16.6
/* FIND ANYTHING, FROM THE HEADER (16 September, asked for in these words:
   "a search icon in the header that lets you search for anything including
   legislators, committees, towns, and bills ... searching Litchfield would
   show both the town and Rep Melissa Litchfield").

   The bill search is a page; this is the box on every page for the things that
   are not bills. It reads site/find.json -- 406 sitting members, the 1,785
   who have left, every committee, every town and ward, the 43 subjects and
   the fixed pages: 322 KB, 58 KB over the wire -- fetched once, the first
   time somebody opens the box, so no page pays for it up front. Bills are not
   in that file on purpose: 33,683 rows is more than a megabyte, and anything
   the box does not recognise is handed to the bill search, which is one page
   away and already does the hard part. A bill NUMBER is recognised here and
   offered as the first answer, because that is the one bill lookup that needs
   no index.

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

function findMatch(q){
  const s=(q||"").trim().toLowerCase();
  if(!s||!FIND.rows)return [];
  const words=s.split(/\s+/);
  const esc=s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
  const edge=new RegExp("\\b"+esc);
  const hit=[];
  for(const r of FIND.rows){
    const hay=`${r[1]} ${r[2]} ${r[4]||""}`.toLowerCase();
    if(!words.every(w=>hay.includes(w)))continue;
    const name=_fbare(r[1]).toLowerCase();
    // A name that starts with what was typed first, then one with a word
    // starting with it -- "Litchfield" puts the town and Rep. Litchfield above
    // anyone whose town or committee merely mentions it -- then the rest.
    const rank=name.startsWith(s)?0:edge.test(name)?1:2;
    // Match quality decides first, and only then does a member who has left
    // fall in behind one who has not: that is what "prioritize ... current
    // legislators before listing former ones" means with a list this long.
    // A former member whose name begins with the query still outranks a town
    // that merely mentions it, which is the answer a reader wants.
    const gone=r[0]==="former"?1:0;
    // Among former members, the most recent first. r[5] is the year they last
    // sat; negated so one sort direction serves both this and name length.
    hit.push([rank,gone,gone?-(r[5]||0):0,name.length,r]);
  }
  hit.sort((a,b)=>a[0]-b[0]||a[1]-b[1]||a[2]-b[2]||a[3]-b[3]);
  return hit.slice(0,8).map(x=>x[4]);
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

function findDraw(q){
  const out=document.getElementById("findout");
  if(!out)return;
  const s=(q||"").trim();
  const clr=document.getElementById("findclear");
  if(clr)clr.hidden=!s;
  if(!s){out.innerHTML=`<p class="fnote">Type a legislator, a committee, a
    town, a subject or a bill number.</p>`;return;}
  const num=findBill(s);
  const rows=findMatch(s);
  // The one line that leaves the panel for the bill search. It is the answer
  // when a bill number was typed, and the way out when nothing here matched.
  const all=`<a class="fall" href="/bills?q=${encodeURIComponent(num||s)}">
    <span class="fl1"><span class="fname">${num?_fesc(num):"See all search results for "
      +_fesc(s)}</span></span>
    <span class="fwhat">${num?"open this bill number in the bill search"
      :"every bill whose number, title or text matches"}</span></a>`;
  const list=rows.map(r=>`<a href="${_fesc(_froot(r[3]))}">
      <span class="fl1"><span class="fname">${_fmark(r[1],s)}</span>
      <span class="fkind">${_fesc(FKIND[r[0]]||r[0])}</span></span>
      ${r[2]?`<span class="fwhat">${_fesc(r[2])}</span>`:""}</a>`).join("");
  let tail="";
  if(!rows.length&&!num){
    const did=findSuggest(s);
    tail=`<p class="fnote">No matching results.${did?` Did you mean
      <button type="button" class="fdym" data-q="${_fesc(did)}">${_fesc(did)}</button>?`
      :""}</p>`;
  }
  out.innerHTML=(num?all:"")+list+(num?"":all)+tail;
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
      <input id="findq" type="search" autocomplete="off" placeholder="A legislator, a committee, a town, or a bill number">
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
    // and looked at the list is about to click.
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
