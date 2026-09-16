// GRANITE_VERSION: 2026-09-16.2
/* FIND ANYTHING, FROM THE HEADER (16 September, asked for in these words:
   "a search icon in the header that lets you search for anything including
   legislators, committees, towns, and bills ... searching Litchfield would
   show both the town and Rep Melissa Litchfield").

   The bill search is a page; this is the box on every page for the things that
   are not bills. It reads site/find.json -- 406 members, every committee, every
   town and ward, and the fixed pages, about 90 KB -- fetched once, the first
   time somebody opens the box, so no page pays for it up front. Bills are not
   in that file on purpose: 33,683 rows is more than a megabyte, and anything
   the box does not recognise is handed to the bill search, which is one page
   away and already does the hard part. A bill NUMBER is recognised here and
   offered as the first answer, because that is the one bill lookup that needs
   no index.

   The control is built here rather than in the two files that write the
   header, so there is one of it. */
const FIND={rows:null,loading:null};
const FKIND={legislator:"Legislator",committee:"Committee",town:"Town",page:"Page"};
const _fesc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>(
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function findRows(){
  if(FIND.rows)return Promise.resolve(FIND.rows);
  if(!FIND.loading)FIND.loading=fetch(new URL("find.json",location.origin+"/").href)
    .then(r=>r.json()).then(rows=>(FIND.rows=rows)).catch(()=>(FIND.rows=[]));
  return FIND.loading;
}

// A bill number typed in any of the ways people write one: hb115, HB 115,
// "hb 0115". Offered without looking anything up, and handed to the bill
// search, which knows which term is on screen.
function findBill(q){
  const m=/^\s*([a-z]{2,5})\s*0*(\d{1,4})\s*$/i.exec(q||"");
  return m?`${m[1].toUpperCase()} ${m[2]}`:"";
}

function findMatch(q){
  const s=(q||"").trim().toLowerCase();
  if(!s||!FIND.rows)return [];
  const words=s.split(/\s+/);
  const hit=[];
  for(const r of FIND.rows){
    const hay=`${r[1]} ${r[2]} ${r[4]||""}`.toLowerCase();
    if(!words.every(w=>hay.includes(w)))continue;
    const name=r[1].toLowerCase();
    // A name that starts with what was typed first, then one with a word
    // starting with it -- "Litchfield" puts the town and Rep. Litchfield above
    // anyone whose town or committee merely mentions it -- then the rest.
    const rank=name.startsWith(s)?0
      :new RegExp("\\b"+s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).test(name)?1:2;
    hit.push([rank,r[1].length,r]);
  }
  hit.sort((a,b)=>a[0]-b[0]||a[1]-b[1]);
  return hit.slice(0,8).map(x=>x[2]);
}

// ROOT-RELATIVE, ALWAYS. find.json's 786 rows all carry a relative path, and
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

function findDraw(q){
  const out=document.getElementById("findout");
  if(!out)return;
  const s=(q||"").trim();
  if(!s){out.innerHTML=`<p class="fnote">Type a legislator, a committee, a town
    or a bill number.</p>`;return;}
  const num=findBill(s);
  const rows=findMatch(s);
  const bills=`<a href="/bills?q=${encodeURIComponent(num||s)}">
    <span class="fkind">${num?"Bill":"Bills"}</span>
    <span><span class="fname">${_fesc(num||s)}</span>
    <span class="fwhat">${num?"open this bill number in the bill search"
      :"search every bill for these words"}</span></span></a>`;
  out.innerHTML=(num?bills:"")
    +rows.map(r=>`<a href="${_fesc(_froot(r[3]))}">
      <span class="fkind">${_fesc(FKIND[r[0]]||r[0])}</span>
      <span><span class="fname">${_fesc(r[1])}</span>
      ${r[2]?`<span class="fwhat">${_fesc(r[2])}</span>`:""}</span></a>`).join("")
    +(num?"":bills)
    +(!rows.length&&!num?`<p class="fnote">Nothing of that name here yet &mdash;
      the search above looks through the bills.</p>`:"");
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
  const themer=document.getElementById("themer");
  bar.insertBefore(btn,themer||null);
  const panel=document.createElement("div");
  panel.id="findpanel";panel.className="findpanel";panel.hidden=true;
  panel.innerHTML=`<div class="findin">
    <label class="sr" for="findq">Search for a legislator, committee, town or bill</label>
    <input id="findq" type="search" autocomplete="off" placeholder="A legislator, a committee, a town, or a bill number">
    <div class="findout" id="findout"></div></div>`;
  const nav=document.querySelector("nav.top");
  nav.parentNode.insertBefore(panel,nav.nextSibling);
  const box=panel.querySelector("#findq");
  const shut=()=>{panel.hidden=true;btn.setAttribute("aria-expanded","false");};
  btn.addEventListener("click",()=>{
    const open=panel.hidden;
    panel.hidden=!open;
    btn.setAttribute("aria-expanded",String(open));
    if(open){findDraw(box.value);box.focus();findRows().then(()=>findDraw(box.value));}
  });
  box.addEventListener("input",()=>findDraw(box.value));
  box.addEventListener("keydown",e=>{
    if(e.key==="Escape"){shut();btn.focus();}
    // Return takes the first answer, which is what a reader who typed a name
    // and looked at the list is about to click.
    if(e.key==="Enter"){const a=panel.querySelector(".findout a");if(a){e.preventDefault();location.href=a.href;}}
  });
  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&!panel.hidden)shut();});
  document.addEventListener("click",e=>{
    if(!panel.hidden&&!panel.contains(e.target)&&e.target!==btn&&!btn.contains(e.target))shut();
  });
}
findMount();
