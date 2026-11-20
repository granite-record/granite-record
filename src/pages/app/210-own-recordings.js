// ------------------------------------- a page that carries its own recordings
/* A STUDY OR STATUTORY COMMITTEE'S VIDEOS TAB (build_study_committees,
   videos_html) and a chamber's (build_full_sessions) carry their rows as
   JSON in the page, under a slot [data-vwview] naming it; this draws the
   view there when the page loads. Without script the slot keeps its one
   line, and each meeting or day keeps its own player. The address can name
   a recording (#v-<id>), which is then the one chosen, and the view is
   brought into view. */
// A study committee's rows: the room and the kind of meeting under the day,
// and under the player the time it was set for where the recording's own
// start is not known, and the way to the meeting on the Meetings tab and on
// the Calendar.
function studyVideoRows(d){
  return (d.rows||[]).map(r=>({id:r.id,date:r.date,began:r.began,seconds:r.seconds,
    line:[r.venue,r.type],
    detail:()=>{
      const facts=[r.venue,r.type,!r.began&&r.time?`Set for ${clock(r.time)}`:""].filter(Boolean);
      const links=[`<a href="${esc(`${d.path}#${r.anchor}`)}" data-ssgo>This meeting</a>`]
        .concat(r.calendar?[`<a href="${esc(r.calendar)}">This meeting on the Calendar</a>`]:[]);
      return (facts.length?`<p class="vwkinds">${vwJoin(facts.map(esc))}</p>`:"")
        +`<p class="src vwlinks">${vwJoin(links)}</p>`;}}));
}
// A CHAMBER'S SESSION DAYS (build_full_sessions, videos_json): a row a
// recording, newest first, its line the day's counts and not its bills (the
// person, 10 October 2026), and under the player what the chamber did that
// day, its full page and its journal, as the day's entry on Session Days says
// them.
const vwPlural=(n,w)=>`${Number(n).toLocaleString()} ${w}${Number(n)===1?"":"s"}`;
const vwJournal=j=>{const m=/^(HJ|SJ)\s*0*(\d+)/.exec(String(j||""));
  return m?`${m[1]==="HJ"?"House":"Senate"} Journal ${m[2]}`:String(j||"");};
function chamberRows(d){
  const rows=[];
  (d.days||[]).slice().sort((a,b)=>String(b.date).localeCompare(String(a.date))).forEach(day=>{
    const c=day.counts||{};
    (day.recordings||(day.videos||[]).map(id=>({id}))).forEach(r=>rows.push({
      id:r.id,date:day.date,began:r.began,seconds:r.seconds,
      line:[c.bills?vwPlural(c.bills,"bill"):"",c.roll_calls?vwPlural(c.roll_calls,"roll call"):""],
      detail:()=>(day.summary?`<p class="cmsaid">${esc(day.summary)}</p>`:"")
        +`<p class="src vwlinks">${vwJoin([`<a class="daylink" href="session/${esc(d.body)}/${esc(day.date)}">The full session day</a>`,
          day.journal_url?`<a href="${esc(day.journal_url)}">${esc(vwJournal(day.journal))} (PDF)</a>`:""])}</p>`}));
  });
  return rows;
}
// The view each kind of page draws from its JSON.
const VW_STATIC={
  // `what`, the committee in a sentence, is the build's (build_study_committees,
  // named): "the Fiscal Committee", and "Administrative Rules", a name that
  // names no body, bare.
  study:d=>{const rows=studyVideoRows(d), n=rows.length;
    return {who:d.who,what:d.what||d.who,key:`ss|${d.key}`,rows,
      heading:`${n.toLocaleString()} recording${n===1?"":"s"}, newest first`,
      href:id=>`${d.path}/videos#v-${id}`,pid:r=>`v${String(r.date).replace(/-/g,"")}_${r.id}`,
      source:"The recordings are the General Court&rsquo;s own, from its House and Senate YouTube channels."};},
  // The chamber's page has its h1 and no h2 above the tab (build_full_sessions,
  // page_head): the list's heading is an h2, where an h3 skipped a level.
  chamber:d=>{const rows=chamberRows(d), n=rows.length, word=d.body==="S"?"Senate":"House";
    const q=d.term&&d.term!==d.latest?`?term=${d.term}`:"";
    return {who:`The ${word}`,what:`the ${word}`,key:`${d.body}|${d.term}`,rows,level:2,
      heading:`${n.toLocaleString()} recording${n===1?"":"s"} in ${termDash(d.term)}`,
      href:id=>`/session/${d.slug}/videos${q}#v-${id}`,pid:r=>`v${String(r.date).replace(/-/g,"")}_${r.id}`,
      empty:`No recording of the ${word}&rsquo;s session days in ${esc(termDash(d.term))} is on file.${
        String(d.term)<="2019-2020"?" "+STREAM_BEGIN_SAID:""}`,
      source:"The recordings are the General Court&rsquo;s own, from its House and Senate YouTube "
        +"channels; what each day did is from its journal."};}};
// Draw one slot from its JSON; `d` in place of the slot's own, for another
// term (chamberVideos). Returns whether the address's recording was chosen.
function vwDraw(slot,d){
  const make=d&&VW_STATIC[d.kind];
  if(!make)return false;
  const o=make(d,slot), want=vwWanted();
  if(o.rows.some(r=>r.id===want)){o.chosen=want;vwTried=vwLanded=want;}
  slot.innerHTML=o.rows.length?videoView(o):`<p class="src fill">${o.empty||""}</p>`;
  vwStick();
  return !!want&&o.chosen===want;
}
function staticVideos(){
  document.querySelectorAll("[data-vwview]").forEach(slot=>{
    const node=document.getElementById(slot.dataset.vwview);
    let d=null;
    try{d=node?JSON.parse(node.textContent):null;}catch(_){d=null;}
    if(!d||!VW_STATIC[d.kind])return;
    if(d.kind==="chamber"){
      VW_CHAMBER=d;chamberStrip(d);
      // Another term the page's script had already fetched before this ran.
      const T=window.GR_CHAMBER_TERM;
      if(T&&T.term&&T.term!==d.term){chamberVideos(T);return;}
    }
    if(vwDraw(slot,d))vwLand(slot);
  });
}
// ARRIVING AT THE RECORDING THE ADDRESS NAMES, once its view is drawn: on a
// chamber's page its tab shown, then its row in view inside the list and the
// view on the page. The same for the term the page carries and for another
// that its script fetched (chamberVideos), whose rows had been chosen and
// left at the top of their list.
function vwLand(slot){
  if(slot.closest(".chpane"))chamberShow(1,true);
  const want=vwWanted();
  vwListShow([...slot.querySelectorAll("a[data-vwpick]")].find(x=>x.dataset.vwpick===want));
  slot.scrollIntoView({block:"start"});
  vwClearStrip(slot);
}
// AND NOT UNDER THE STRIP (the walk of 31 October 2026): brought to the top
// of the window, a study committee's and a chamber's view went 45 to 49px
// under the page's tab strip, which stays there, at every width (measured on
// ss57 and the House at 1280 and 390). The page is moved down by what the
// strip still covers, and no further. A committee's own page too
// (showVideo): .vw's scroll margin is set on a phone only, and S07's view at
// 1280 came to rest clear of the strip only because the page above it grew
// after the scroll (the review of 2 November 2026).
function vwClearStrip(el){
  if(!el||!el.getBoundingClientRect)return;
  const box=el.matches&&el.matches(".vw")?el:(el.querySelector&&el.querySelector(".vw"))||el;
  const strip=box&&box.closest?vwStrip(box):null;
  if(!strip)return;
  const gap=strip.getBoundingClientRect().bottom-el.getBoundingClientRect().top;
  if(gap>0)window.scrollBy(0,-Math.ceil(gap));
}
/* A CHAMBER'S TWO TABS, Session Days | Videos, put above the two panes the
   page carries (build_full_sessions), as a committee's are drawn: the same
   role="tab" buttons, so the arrow keys move along them, each with its
   count. The address names the tab -- /session/house/videos, which the
   site's rewrite serves as the chamber's page -- with the term the page's
   script keeps in it; a day it names (#day-<date>) is on Session Days. */
let VW_CHAMBER=null;
function chamberStrip(d){
  const ctl=document.querySelector(".chamberctl");
  if(!ctl||document.querySelector(".chtabs"))return;
  ctl.insertAdjacentHTML("afterend",`<div class="tabs chtabs" role="tablist">${
    [["Session Days","chdays"],["Videos","chvids"]].map(([w,p],i)=>
      `<button class="tab" role="tab" id="chtab_${i}" aria-controls="${p}" data-chtab="${i}" aria-selected="false">${w}</button>`).join("")}</div>`);
  ["chdays","chvids"].forEach((p,i)=>{const el=document.getElementById(p);
    if(el){el.setAttribute("role","tabpanel");el.setAttribute("aria-labelledby",`chtab_${i}`);el.tabIndex=0;}});
  chamberCounts(d);
  chamberShow(/\/videos\/?$/.test(location.pathname)&&!/^#day-/.test(location.hash)?1:0,false);
}
function chamberCounts(d){
  const n=[(d.days_all||document.querySelectorAll(".chdays > details").length),
           chamberRows(d).length];
  document.querySelectorAll(".chtabs .tab").forEach((t,i)=>{
    const w=i?"Videos":"Session Days";
    t.innerHTML=esc(w)+(n[i]?tabN(Number(n[i]).toLocaleString()):"");});
}
function chamberShow(i,write){
  document.querySelectorAll(".chtabs .tab").forEach((t,k)=>t.setAttribute("aria-selected",String(k===i)));
  const days=document.getElementById("chdays"), vids=document.getElementById("chvids");
  // A RECORDING PLAYING IN THE PANE BEING HIDDEN IS PAUSED, not left playing
  // where nobody can see it or stop it (the review of 29 October 2026; a
  // committee's tabs draw their pane again, which ends it). The frames take
  // YouTube's commands (enablejsapi=1), as a moment's button seeks them, and
  // one paused is where it stopped when its tab is shown again. A frame
  // still loading cannot hear yet, so it is told again once it has loaded,
  // if its pane is still hidden then.
  const hide=i===0?vids:days;
  if(hide&&!hide.hidden)panePause(hide,()=>hide.hidden);
  if(days)days.hidden=i!==0;
  if(vids)vids.hidden=i!==1;
  vwStick();
  if(!write||!VW_CHAMBER)return;
  const path=`/session/${VW_CHAMBER.slug}${i?"/videos":""}`;
  // THE VIDEOS TAB TURNED TO AGAIN names the recording chosen there, as a
  // study committee's does (ssShow): Session Days had taken the #v- off the
  // address, so Share, a copied link or a reload opened on the newest and
  // not on what was shown (the walk of 30 October 2026). An address that
  // already names one keeps it; the newest stays unnamed.
  const named=i&&/^#v-/.test(location.hash), vw=i&&!named&&vids&&vids.querySelector&&vids.querySelector(".vw");
  const back=vw&&VVIEW&&VVIEW.rows&&VVIEW.rows.length&&VVIEW.chosen
    &&VVIEW.chosen!==VVIEW.rows[0].id?VVIEW.chosen:"";
  try{history.replaceState(history.state,"",path+location.search+(named?location.hash:back?`#v-${back}`:""));}catch(_){}
  addressed();
}
document.addEventListener("click",e=>{
  const t=e.target&&e.target.closest&&e.target.closest("[data-chtab]");
  if(t)chamberShow(+t.dataset.chtab,true);
});
// The frames in a pane being hidden, paused (chamberShow, ssShow); `gone()`
// says whether the pane is still hidden when a frame still loading has
// loaded.
function panePause(pane,gone){
  const pause=f=>{try{f.contentWindow.postMessage(JSON.stringify({event:"command",func:"pauseVideo",args:[]}),"*");}catch(_){}};
  pane.querySelectorAll("iframe").forEach(f=>{
    pause(f);
    f.addEventListener("load",()=>{if(gone())pause(f);},{once:true});});
}

/* A STUDY OR STATUTORY COMMITTEE'S TABS (the owner, 29 October 2026: "study
   committees, commissions and boards get the same tab format as standing
   committees: Bills | Meetings | Videos"). build_study_committees writes the
   strip and the panes whole (tabs_html), the strip in a standing committee's
   classes, and the pane it lands on shown from the first paint (html.js);
   this turns to the tab the address names and to the tab pressed. The
   address names the tab as a standing committee's does -- /committee/ss57
   the one it lands on, /committee/ss57/bills, /sessions and /videos the
   others, which the committee rewrite serves -- and a place on one names
   that tab: a meeting
   (#day-<date>, as a Calendar card leads here, or the earlier meetings'
   fold), a recording (#v-<id>), or a pane by its id (#meetings, #videos,
   the sections' addresses before the tabs). A meeting named is opened and
   brought into view. A recording playing in a pane turned from is paused.

   THE PAGE'S OWN ADDRESS OPENS ON ITS MEETINGS (the review of 29 October
   2026, 4): opened on Bills, the State Commission on Aging showed one row,
   HB 621 of 2019, which What It Does names just above, and the Fiscal
   Committee four housekeeping bills, its 165 meetings a click away. The
   strip keeps the owner's order, Bills | Meetings | Videos; the tab the
   page lands on is the one the build writes with no slug (tabs_html,
   landing) -- Meetings wherever the body has met -- and every other tab is
   at its own: /bills, /sessions, /videos. */
const ssTabsOf=strip=>[...strip.querySelectorAll("[data-sstab]")];
const ssPaneOf=t=>document.getElementById(t.getAttribute("aria-controls")||"");
function ssWanted(strip){
  const tabs=ssTabsOf(strip), h=location.hash||"";
  const pane=id=>tabs.find(t=>t.getAttribute("aria-controls")===id);
  const placed=/^#(day-|earlier$)/.test(h)?pane("meetings"):/^#v-/.test(h)?pane("videos"):pane(h.slice(1));
  if(placed)return {tab:placed,placed:true};
  const m=/\/([a-z]+)\/?$/.exec(location.pathname);
  return {tab:(m&&tabs.find(t=>t.dataset.sstab===m[1]))||tabs.find(t=>!t.dataset.sstab)||tabs[0],placed:false};
}
// A meeting brought to the top of the window lands below the strip, which
// stays there (.rhead ~ .tabs): scrolled to the top, Friday, October 23's
// summary was under the strip on the Fiscal Committee's page (the review of
// 29 October 2026, 2). The strip's height is written on the page as
// --ssheld, which app.css keeps above a meeting (scroll-margin-top) -- for
// this script's scrolling and for the browser's own, which lands on the
// address's #day- after this has run and had put the meeting back at 0px.
function ssClear(el,strip){
  const held=strip&&getComputedStyle(strip).position==="sticky"?Math.ceil(strip.getBoundingClientRect().height):0;
  document.documentElement.style.setProperty("--ssheld",`${held}px`);
  el.scrollIntoView({block:"start"});
}
function ssShow(tab,write,keep){
  const strip=tab.closest(".sstabs");
  ssTabsOf(strip).forEach(t=>{
    const on=t===tab, pane=ssPaneOf(t);
    t.setAttribute("aria-selected",String(on));
    if(!pane)return;
    if(!on&&pane.hasAttribute("data-on"))panePause(pane,()=>!pane.hasAttribute("data-on"));
    if(on)pane.setAttribute("data-on","");else pane.removeAttribute("data-on");
  });
  vwStick();
  if(!write)return;
  const slug=tab.dataset.sstab;
  // THE VIDEOS TAB TURNED TO AGAIN names the recording chosen there, as a
  // standing committee's does (vwBackTo): the address had lost its #v-, so
  // Share, a copied link or a reload opened on the newest and not on what
  // was shown (the review of 30 October 2026). The newest stays unnamed.
  const pane=ssPaneOf(tab), vw=pane&&pane.querySelector&&pane.querySelector(".vw");
  const back=!keep&&vw&&VVIEW&&VVIEW.rows&&VVIEW.rows.length&&VVIEW.chosen
    &&VVIEW.chosen!==VVIEW.rows[0].id?VVIEW.chosen:"";
  try{history.replaceState(history.state,"",strip.dataset.base+(slug?`/${slug}`:"")+location.search
    +(keep?location.hash:back?`#v-${back}`:""));}catch(_){}
  // Already chosen: not an arrival (showVideo) to be scrolled to.
  if(back)vwTried=vwLanded=back;
  addressed();
}
// The tab the address names, and the meeting it names opened and in view.
function ssLand(){
  const strip=document.querySelector(".sstabs");
  if(!strip)return;
  const w=ssWanted(strip);
  if(!w.tab)return;
  ssShow(w.tab,w.placed,true);
  let day=null;
  try{day=/^#day-/.test(location.hash)?document.getElementById(decodeURIComponent(location.hash.slice(1))):null;}catch(_){}
  if(!day)return;
  for(let p=day;p;p=p.parentElement)if(p.tagName==="DETAILS")p.open=true;
  ssClear(day,strip);
}
document.addEventListener("click",e=>{
  const t=e.target&&e.target.closest?e.target:null;
  if(!t)return;
  const tab=t.closest("[data-sstab]");
  if(tab){ssShow(tab,true);return;}
  // A meeting on the Meetings tab, from the Videos tab's "This meeting":
  // turned to in place, as a standing committee's is.
  const a=t.closest("a[data-ssgo]");
  if(!a||e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  e.preventDefault();
  try{history.replaceState(history.state,"",a.getAttribute("href"));}catch(_){}
  addressed();
  ssLand();
});
window.addEventListener("hashchange",()=>ssLand());
// Another term, as the page's script fetched it: its Videos tab drawn from
// the same days, and the two counts. A recording the address named is the
// old term's, so the address stops naming it.
function chamberVideos(T){
  if(!VW_CHAMBER)return;
  const slot=document.querySelector("#chvids [data-vwview]");
  if(!slot)return;
  if(/^#v-/.test(location.hash)&&!(T.days||[]).some(x=>(x.videos||[]).includes(vwWanted()))){
    try{history.replaceState(history.state,"",location.pathname+location.search);}catch(_){}
  }
  const d=Object.assign({},VW_CHAMBER,{term:T.term,days:(T.days||[]).filter(x=>(x.videos||[]).length),
    days_all:(T.days||[]).length});
  chamberCounts(d);
  if(vwDraw(slot,d))vwLand(slot);
}

// What the committee reported on a bill, for its card on the Bills tab: each
// act, with the day the docket dates it and a link to that meeting.
function reportedLine(acts){
  if(!(acts||[]).length)return "";
  return acts.map(a=>{
    const day=a.date?(a.meeting?`<a href="${esc(dayHref(a.meeting))}">${esc(dateWords(a.date))}</a>`
      :esc(dateWords(a.date))):"";
    return actSaid(a,"The committee",day?`, ${a.meeting?"at its meeting of":"dated"} ${day}`:"");})
    .join("");
}

