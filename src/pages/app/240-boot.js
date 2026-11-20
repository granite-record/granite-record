// ------------------------------------------------------------------ boot ---
// THE LIST KEEPS ITS HEIGHT THROUGH A REDRAW. A redraw replaces the list's
// contents in one go, and for the length of the replacement the page can be
// shorter than the window, so the footer shows for a frame and the scroll
// place is clamped: the footer flash when a card is opened (the owner's walk
// of dry run 9, 8 November 2026). The height it had is held as a minimum
// until the next frame has painted, then let go, so a list that really is
// shorter shrinks a frame later.
function holdHeight(el){
  if(!el||!el.offsetHeight)return;
  el.style.minHeight=el.offsetHeight+"px";
  const free=()=>{el.style.minHeight="";};
  if(typeof requestAnimationFrame==="function")
    requestAnimationFrame(()=>requestAnimationFrame(free));
  else setTimeout(free,50);
}

function renderPage(){
  if(!PAGE)return;
  const el=$("#results");
  if(!el)return;
  const held=focusKey();
  holdHeight(el);
  parkActions();
  const kept=vwPaneKept(el);
  if(kept){
    while(el.firstChild&&el.firstChild!==kept)el.removeChild(el.firstChild);
    kept.insertAdjacentHTML("beforebegin",committeeTop(PAGE.data));
  }else{
    // The list's own place, kept through the drawing of the same list.
    const list=el.querySelector(".vwlist"), vw=list&&list.closest(".vw");
    const was=vw?[vw.dataset.vwkey,list.scrollTop]:null;
    el.innerHTML = PAGE.kind==="member" ? renderMember(PAGE.data)
                                        : renderCommittee(PAGE.data);
    const now=was&&el.querySelector(".vw");
    if(now&&now.dataset.vwkey===was[0])now.querySelector(".vwlist").scrollTop=was[1];
  }
  vwStick();
  placeActions();
  syncCards([...openCards]);
  showDay();
  showVideo();
  showSelectedTab(el);
  refocus(held);
}

// The tabs, the cards and the filter selects on these two pages. Kept apart
// from the bill list's handlers, which end at "if(PAGE)return" because they
// finish by calling render() and would draw the search over the record.
document.addEventListener("click",e=>{
  if(!PAGE)return;
  const t=e.target.closest("[data-pt]");
  if(t){PAGE_TAB=+t.dataset.pt;
    tabAddress(slugOf(PAGE.kind==="member"?MEMBER_TABS:COMMITTEE_TABS,PAGE_TAB));
    vwBackTo();
    renderPage();return;}
  // Not data-more: that one belongs to the bill list, is read by the
  // handler above this in the file, and calls render(), which would draw the
  // search over the member's record.
  // The keyboard goes to the first of the votes it brought, as "Show 3 more"
  // on a docket puts it on the first line it reveals: the button is drawn
  // again a page further down, and focus left on nothing sent the next Tab
  // press to the top of the member's page (the review of 2 October 2026).
  // Every term, or back to the one shown; and the search and filters cleared.
  const va=e.target.closest("[data-vall]");
  if(va&&PAGE){PAGE.vall=va.dataset.vall==="1";PAGE.vshow=0;voteAddress();
    renderPage();return;}
  const vc=e.target.closest("[data-vclear]");
  if(vc&&PAGE){PAGE.vq="";PAGE.vtopic="";PAGE.vfilter="";PAGE.vside="";PAGE.vshow=0;
    voteAddress();renderPage();
    const b=document.querySelector('input[data-pf="vq"]');if(b)b.focus({preventScroll:true});
    return;}
  const vm=e.target.closest("[data-vmore]");
  if(vm){
    const from=PAGE.vshow||VOTES_SHOWN;
    PAGE.vshow=from+VOTES_SHOWN;renderPage();
    const row=$("#results").querySelectorAll("table.vfull tbody tr")[from];
    if(row&&row.focus){row.tabIndex=-1;row.focus({preventScroll:true});}
    return;}
  // A committee's bills or days, twenty more (A COMMITTEE'S LONG LISTS), and
  // the keyboard on the first of them: a card's number, a day's summary.
  const pm=e.target.closest("[data-pmore]");
  if(pm){
    const from=+pm.dataset.from||0;
    PAGE[pm.dataset.pmore]=from+PAGED_SHOWN;renderPage();
    const box=document.getElementById(pm.getAttribute("aria-controls"));
    const first=box&&box.children?box.children[from]:null;
    const to=first&&((first.querySelector&&first.querySelector("summary,a[href],button"))||first);
    if(to&&to.focus){if(to===first)first.tabIndex=-1;to.focus();}
    return;}
  const ct=e.target.closest(".card .tab[data-t]");
  if(ct){openTab[ct.closest(".card").dataset.id]=ct.dataset.t;renderPage();return;}
  const head=e.target.closest(".card .ctitle")||cardBackground(e);
  if(head){
    const id=head.closest(".card").dataset.id;
    if(openCards.has(id)){openCards.delete(id);renderPage();}
    else openBill(id);
    return;}
});
// A RING OPENED OR SHUT under a member's vote (voteRing) stays so through the
// page's next drawing, as a committee's meetings do; opening one draws it, and
// the bill's record is asked for then. "toggle" does not bubble, so it is
// heard on the way down.
document.addEventListener("toggle",e=>{
  const d=e.target;
  if(!PAGE||!d||!d.matches||!d.matches("details[data-vring]"))return;
  const k=d.getAttribute("data-vring"), was=!!(PAGE.vopen&&PAGE.vopen[k]);
  if(was===d.open)return;
  PAGE.vopen=PAGE.vopen||{};
  if(d.open)PAGE.vopen[k]=true;else delete PAGE.vopen[k];
  if(d.open){const held=focusKey();renderPage();refocus(held);}
},true);
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
    ensureTerm(PAGE.term).then(renderPage);
    // A recording the address named is the old term's: the new term's
    // Videos tab opens on its newest, and the address stops naming it. A
    // committee's only: a member's page, its tabs not a committee's, had
    // its Votes tab's address rewritten as /videos (the review of 29
    // October 2026).
    if(PAGE.kind==="committee"&&/^#v-/.test(location.hash))tabAddress(slugOf(COMMITTEE_TABS,PAGE_TAB));}
  // A narrower filter over a list already expanded to 800 rows left the
  // reader at the bottom of a list of 40.
  if(f==="vfilter"||f==="vside"||f==="vq"||f==="vtopic"||f==="term")PAGE.vshow=0;
  // Choosing a term is choosing the one term.
  if(f==="term")PAGE.vall=false;
  if(f==="vq"||f==="vtopic"||f==="term")voteAddress();
  // And a committee's lists start again at twenty, under the new choice.
  if(f==="status"||f==="term")PAGE.bshow=0;
  if(f==="msort"||f==="term")PAGE.mshow=0;
  renderPage();
});

// THE PICKERS' WORDS ON A PHONE (Alice, 8 November 2026: on a phone the
// search box at full width, and under it the term picker and the Sort side
// by side in equal halves; app.css). Half of a 375px screen's row is 159px
// of select, and "2027 Bill Requests" asks for 185px, "2025–2026 Term"
// 173px and "Most recent action" 169px (Chrome, 8 November 2026): the words
// would be cut off. So at the phone's width an option with data-short shows
// those words -- "2025–2026", "2027 Requests", "Recent action" -- and its
// own again on a wider screen, a phone turned on its side among them.
// Where even those do not fit two to a row (320px), the row stacks them.
// AN OPTION REPLACED, NOT ITS WORDS: Chrome kept a select's width from the
// words an option had before, where only the words changed and the fonts
// were already in, so a reload of the requests at 390px stacked the two
// with "2027 Requests" in a select sized for "2027 Bill Requests" (8
// November 2026). The value chosen is kept.
const PHONE_ROW=typeof matchMedia==="function"?matchMedia("(max-width:45em)"):null;
function fitPickers(){
  const narrow=!!(PHONE_ROW&&PHONE_ROW.matches);
  for(const s of [$("#year"),$("#sort")]){
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
  // AND MET IN THE ORDER THEY ARE DRAWN (the review of 8 November 2026): on
  // a phone the term picker is drawn under the box, and Tab and a screen
  // reader met it first, above; so there it is put after the box in the
  // page, with its label, and back before the box's own label on a wider
  // screen, where it stands to the box's left.
  const y=$("#year"),qb=document.querySelector(".searchrow .qbox");
  if(y&&qb&&y.parentNode&&y.parentNode===qb.parentNode&&typeof qb.compareDocumentPosition==="function"){
    const prev=e=>e.previousElementSibling&&e.previousElementSibling.tagName==="LABEL"?e.previousElementSibling:null;
    const lab=prev(y),after=!!(qb.compareDocumentPosition(y)&4);
    if(narrow!==after){
      const ref=narrow?qb.nextSibling:(prev(qb)||qb);
      if(lab)qb.parentNode.insertBefore(lab,ref);
      qb.parentNode.insertBefore(y,ref);
    }
  }
}
if(PHONE_ROW&&PHONE_ROW.addEventListener)PHONE_ROW.addEventListener("change",fitPickers);

// The term and sort dropdowns order and filter a list of bills. On a page
// showing one member or one committee there is no such list, and a control
// that does nothing is worse than no control.
// A bill's own page is written this way already (shell.py's BILL_ROW, the
// preview check of 25 October 2026), so that its first paint is what this
// leaves: a control this takes down wants writing down there too.
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
  // The person's words for the box on a record's page (9 October 2026): it
  // finds any bill, by its number or the words of its title.
  if(q)q.placeholder="Bill number or title words";
}

/* AND ON A PAGE THAT IS NOT A LIST OF BILLS AT ALL, the box itself goes.
   A town page led with "Search all bills" above the name of the town; so did
   a member's page, a committee's, and every civics page. The Bills tab is
   one click away on all of them.
   Hidden rather than removed: app.js binds seven ids in this row when it
   loads and shell.py asserts every one of them is in the template, because a
   missing #q once drew 33,683 blank pages. [hidden] on the wrapper takes it
   out of the layout and out of what a screen reader walks, and leaves every
   binding where it was. */
function hideBillSearch(){
  const row=document.querySelector(".searchrow");
  if(row)row.hidden=true;
}

/* AND ON A PAGE THAT IS NOT A LIST OF BILLS, the whole of the search goes. A
   town page, a directory listing, a civics page, and a bill's, a member's or
   a committee's own page: the app's job there is to take down the rail, the
   counter and the two pickers that belong to a list it is not going to draw.
   Nothing in it reads the index, so it runs before the index is asked for
   (WHAT THIS PAGE IS). */
function staticChromeDown(){
  const fac=$("#facets"); if(fac){fac.innerHTML="";fac.hidden=true;}
  const sh=document.querySelector(".shell"); if(sh)sh.classList.add("nofacets");
  const c=$("#count"); if(c)c.textContent="";
  hideListControls();
  scrollStops();
}
/* A RECORD'S OWN PAGE THAT COULD NOT LOAD shows the record it was served
   (shell.page's static, hidden under html.js until now) under one plain line,
   where it showed a developer's error (the phone audit of 25 October 2026). */
function plainRecord(){
  const rec=document.getElementById("static-rec"), el=$("#results");
  const line=`<p class="src">Part of this page did not load, so here is its record in
    plain form. Reload the page to try again.</p>`;
  if(rec){rec.classList.add("shown");rec.innerHTML=line+rec.innerHTML;if(el)el.innerHTML="";}
  else if(el)el.innerHTML=line;
}
// A BOX THAT SCROLLS SIDEWAYS IS A TAB STOP WHILE IT SCROLLS, AND ONLY THEN.
// The exports page's coverage table is 420px in a 336px box on a phone, and a
// keyboard has to be able to reach the box to pan it; the page carried
// tabindex="0" on it at every width, so on a desktop, where the table fits
// with room to spare, the Tab key stopped on a box that does nothing (the
// review of 2 October 2026). The page marks the box and this gives it the
// stop where its content is wider than it is, again when the window changes.
// Without this script Chrome and Firefox make a scrolling box a stop
// themselves.
// A Learn table's box carries its name (data-scrolllabel) and is a region
// only while it scrolls, so a table that fits is no landmark: the glossary's
// sixteen letters were sixteen (the review of 30 October 2026). And a box in a
// fold is 0px wide until the fold opens, so each fold's opening measures again.
function scrollStops(){
  const boxes=[...document.querySelectorAll("[data-scrollstop]")];
  const set=()=>boxes.forEach(b=>{
    const wide=b.scrollWidth>b.clientWidth+1, name=b.getAttribute?b.getAttribute("data-scrolllabel"):null;
    if(wide)b.setAttribute("tabindex","0");
    else b.removeAttribute("tabindex");
    if(name!==null){
      if(wide){b.setAttribute("role","region");b.setAttribute("aria-label",name);}
      else{b.removeAttribute("role");b.removeAttribute("aria-label");}
    }});
  if(!boxes.length)return;
  set();
  window.addEventListener("resize",set);
  if(document.addEventListener)document.addEventListener("toggle",set,true);
}

// Every term this record has anything in, newest first. Worked out once,
// when the file lands, so every tab and the control above them agree.
function recordTerms(kind,d){
  const t=new Set();
  if(kind==="member"){
    (d.sponsored||[]).forEach(b=>b.term&&t.add(b.term));
    // The term the vote was cast in, as the Votes tab files it (voteYear): a
    // member whose only ballots of a term are on rules questions, which carry
    // no bill and so no bill year, otherwise had no term at all, and a page
    // with no term drew its attendance as a note with no figures in it.
    (d.votes||[]).forEach(v=>{const x=termOfYear(voteYear(v));if(x)t.add(x);});
    // Next session's requests, where build_lsrs matched any to this member
    // (meta.requests.by_slug). They sort after the term of their own session
    // and before every earlier one, so a member with requests opens on them
    // while 2025-2026 is the newest term (published counts the requests
    // term), and on 2027-2028 from the night it is published; one with none
    // opens on their newest term, as before (Alice, B4).
    const R=META.requests;
    if(R&&R.term&&d.slug&&(R.by_slug||{})[d.slug])t.add(R.term);
    const key=x=>isReqTerm(x)?`${reqYear()}-0000`:x;
    return [...t].sort((a,b)=>key(a)<key(b)?1:key(a)>key(b)?-1:0);
  }else{
    Object.keys(d.bills||{}).forEach(x=>x&&t.add(x));
    (d.sessions||[]).forEach(s=>s.term&&t.add(s.term));
    // A term the committee is on its channel in and on no bill row.
    (d.recordings||[]).forEach(r=>r.term&&t.add(r.term));
  }
  return [...t].sort().reverse();
}

// The address of one sitting on a committee's page. Built from the date
// alone, because that is the only thing about a sitting that a calendar
// entry elsewhere on the site already knows.
function dayId(date){ return "day-" + String(date || ""); }
// A LINK TO A DAY ON THIS PAGE NAMES THIS PAGE (23 October 2026). Every page
// carries <base href="/">, so a bare href="#day-2025-10-01" resolved to the
// home page: a bill card's "at its meeting of" date, a meeting's "voted at
// another meeting" date and the head's "Its last meeting was on" all left
// the committee page for the front page. Written with this document's own
// path and search, as skipHere writes the skip link, the link stays here;
// hashchange then runs showDay, which turns to the meetings tab and opens
// the day, and the link opened in a new tab lands on the same day.
function dayHref(date){ return location.pathname + location.search + "#" + dayId(date); }

/* LANDING ON A DAY. A committee page renders more than once -- the record
   arrives, then the term index, then home.json -- and each render replaces
   #results wholesale, so anything scrolled to is thrown away and rebuilt.
   This runs after every render: it re-marks the day named in the address,
   and scrolls to it ONCE per address, so a later render does not yank a
   reader back to where they arrived after they have started reading.

   It is needed at all because openPage returns before the hash reader that
   serves bills, and nothing else on a committee page has ever read the
   address. */
let dayLanded = "", dayTried = "", dayPaged = "";
// THE PAGE TURNED TO A TERM an address asks for without naming it -- the
// term a day (showDay) or a recording (showVideo) is in -- as choosing it in
// the Term control does (the change handler, data-pf="term"). Whether it
// moved: not where the page shows that term already, or does not have it.
function pageToTerm(t){
  if(!t||!PAGE||t===pageTerm()||!(PAGE.terms||[]).includes(t))return false;
  PAGE.term=t;term=t;PAGE.status="";PAGE.bshow=0;PAGE.mshow=0;PAGE.vshow=0;
  ensureTerm(PAGE.term).then(renderPage);
  return true;
}
function showDay(){
  const want = decodeURIComponent(location.hash.slice(1) || "");
  if(!/^day-\d{4}-\d{2}-\d{2}$/.test(want)){ dayLanded=""; dayTried=""; dayPaged=""; return; }
  document.querySelectorAll(".cmeet.at").forEach(e=>e.classList.remove("at"));
  let el = document.getElementById(want);
  // THE SITTINGS ARE ON THE OTHER TAB. A committee page opens on Bills, and
  // the days live under Sessions -- so a calendar entry linking to a sitting
  // would have landed on a tab that does not contain it and found nothing at
  // all. Being asked for a day IS asking for that tab. Guarded so it is tried
  // once: a date the page genuinely does not hold must not bounce the reader
  // between tabs.
  // AND THE DAY IS IN ITS OWN TERM, which the address does not name: a link
  // to a meeting of 2021 opened in a new tab landed on the Meetings tab of
  // 2025-2026, where the day is not, and said nothing (the Videos tab's
  // "This committee's meeting that day", the review of 29 October 2026). The
  // term holding the day is turned to, as a recording's is (showVideo).
  if(!el && PAGE && PAGE.kind === "committee" && PAGE.data && dayTried !== want){
    dayTried = want;
    const s = (PAGE.data.sessions || []).find(x => dayId(x.date) === want);
    const moved = !!s && pageToTerm(s.term);
    if(moved || PAGE_TAB !== COMMITTEE_TABS.sessions){
      PAGE_TAB = COMMITTEE_TABS.sessions;
      // And the address names the tab it shows, the day kept.
      tabAddress("sessions", true);
      renderPage();                    // which calls this again, tab in hand
      return;
    }
  }
  if(!el) return;                      // no sitting of that date on this page
  // PAST THE TWENTY SHOWN (A COMMITTEE'S LONG LISTS): the address changed
  // while the Meetings tab was up, and the list is drawn again as far as the
  // day, which renderCommitteeSessions reads from the address. Once a date.
  if(el.classList.contains("unshown")){
    if(dayPaged!==want){dayPaged=want;renderPage();}
    return;
  }
  el.classList.add("at");
  // A meeting is folded since 10 October 2026: the one named is opened.
  if(el.tagName==="DETAILS"&&!el.open){el.open=true;
    if(PAGE){PAGE.mopen=PAGE.mopen||{};PAGE.mopen[el.id]=true;}}
  if(dayLanded === want) return;
  dayLanded = want;
  el.scrollIntoView({block:"start"});
}

/* LANDING ON A RECORDING. #v-<id> asks for the Videos tab, as #day-<date>
   asks for the Meetings tab (showDay), and for the term the recording is in,
   since the term is not in the address: tried once an address, so a reader
   is not bounced. A recording the page does not hold leaves the newest
   chosen and says nothing. The row is shown inside its list, and the view on
   the page, once. An id may begin with a dash (#v--vjHAnQ1eXM), so it is
   matched as a string and never put in a selector. */
const vwWanted=()=>{const m=/^#v-(.+)$/.exec(location.hash||"");
  try{return m?decodeURIComponent(m[1]):"";}catch(_){return "";}};
let vwTried="", vwLanded="";
function showVideo(){
  const want=vwWanted();
  if(!want||!PAGE||PAGE.kind!=="committee"||!PAGE.data){vwTried=vwLanded="";return;}
  const r=(PAGE.data.recordings||[]).find(x=>x.id===want);
  if(!r)return;
  if(vwTried!==want){
    vwTried=want;
    PAGE.vid=want;
    pageToTerm(r.term);
    if(PAGE_TAB!==COMMITTEE_TABS.videos){PAGE_TAB=COMMITTEE_TABS.videos;tabAddress("videos",true);}
    renderPage();                      // which calls this again, the tab in hand
    return;
  }
  if(vwLanded===want)return;
  const a=[...document.querySelectorAll(".vwlist a[data-vwpick]")].find(x=>x.dataset.vwpick===want);
  const box=a&&a.closest(".vw");
  if(!box)return;
  vwLanded=want;
  vwListShow(a);
  box.scrollIntoView({block:"start"});
  vwClearStrip(box);
}
window.addEventListener("hashchange", function(){ if(PAGE){ showDay(); showVideo(); } });
/* BACK AND FORWARD ON A RECORD PAGE bring back the tab the address names.
   Turning to a tab writes the address over the entry (tabAddress), so going
   back from a day the head's link opened -- /committee/S07/sessions#day-...,
   which had been /videos#day-... -- arrives at /committee/S07/videos#v-...
   with a popstate and, the path having changed, no hashchange: the address
   named the Videos tab and the Meetings tab stayed up (the review of 29
   October 2026). The tab is read from the path again, and the day or the
   recording the address names is landed on afresh. */
window.addEventListener("popstate", function(){
  if(!PAGE || !PAGE.data) return;
  const tabs_ = PAGE.kind === "member" ? MEMBER_TABS : COMMITTEE_TABS;
  let want = tabs_[tabFromPath()] || 0;
  // A committee with no recording has no Videos tab (committeeTop).
  if(want === COMMITTEE_TABS.videos && PAGE.kind === "committee" && !(PAGE.data.recordings || []).length) want = 0;
  vwTried = vwLanded = ""; dayTried = "";
  if(want !== PAGE_TAB){ PAGE_TAB = want; renderPage(); }
  else { showDay(); showVideo(); }
});
// A MEETING THE READER OPENED OR SHUT STAYS SO through the page's next
// drawing -- the term's index, home.json and the officers each arrive after
// the record and draw it again.
document.addEventListener("toggle",e=>{
  const d=e.target;
  if(!PAGE||!d||!d.classList||!d.classList.contains("cmeet"))return;
  PAGE.mopen=PAGE.mopen||{};PAGE.mopen[d.id]=d.open;
},true);

/* A TERM THAT HOLDS ONLY RECORDINGS OPENS ON THEM. A committee's recordings
   add their terms to its Term control (recordTerms), and the page opens on
   the newest: House Rules opened on 2025-2026 saying "No bills were referred
   to this committee in the 2025-2026 term", its three recordings of that
   term on a tab not shown, where before them it opened on 1997-1998 and its
   one bill (the review of 29 October 2026; six pages). Arriving at the page's
   own address, with no tab named, such a term opens on Videos, and the
   address says so. */
function landingTab(){
  if(!PAGE||PAGE.kind!=="committee"||!PAGE.data||PAGE_TAB!==0||tabFromPath())return;
  const c=PAGE.data;
  if(cmteBills(c).length||cmteSessions(c).length||!cmteRecordings(c).length)return;
  PAGE_TAB=COMMITTEE_TABS.videos;
  tabAddress("videos",true);
}
// The term a record's page opens on: the newest the site publishes. A
// member-elect's newest is the requests term, which has no votes, so their
// Votes tab's own address (a shared ?q= or ?term=all link) opens on the
// newest term that has them (dry run 16, 10 November 2026).
function landingTerm(kind,terms){
  const t=terms.find(published)||terms[0]||"";
  if(kind==="member"&&PAGE_TAB===MEMBER_TABS.votes&&isReqTerm(t))
    return terms.find(x=>!isReqTerm(x)&&published(x))||t;
  return t;
}
function openPage(kind,ref){
  PAGE={kind,data:null,terms:[],term:"",status:"",vfilter:"",vid:"",
        vside:"",vq:"",vtopic:"",vall:false,vopen:{},vshow:0,bshow:0,mshow:0};
  if(kind==="member")voteAddressRead();
  // A member's page has three tabs and a committee's two. Carried over, a
  // member's Votes tab (2) opened a committee on a tab it does not have, and
  // the page drew nothing under the strip.
  PAGE_TAB=0;
  // Or the tab its own address names.
  const tabs_=kind==="member"?MEMBER_TABS:COMMITTEE_TABS;
  if(tabs_[tabFromPath()])PAGE_TAB=tabs_[tabFromPath()];
  // The search chrome belongs to the search, and is down before the index
  // is asked for (staticChromeDown, from WHAT THIS PAGE IS). Left up, the
  // facet panel offered filters for a list that is not on screen and the
  // counter read "2,234 of 2,234 bills" beside one member's name.
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
    // THE NEWEST TERM THE SITE PUBLISHES, not the newest the record names
    // (6 November 2026): a committee with one meeting posted for the term
    // still to come opened on it, an empty "No bills were referred to this
    // committee in the 2027–2028 term", over the term it has a record of.
    // The new term stays in the Term control, its meeting under it.
    PAGE.term=landingTerm(kind,PAGE.terms);
    if(PAGE.term)term=PAGE.term;
    landingTab();
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
    .catch(plainRecord);
}

// TWENTY-FIVE AT A TIME. render() drew the first 400 matches and told the
// reader to narrow the search to see the rest, which is the site asking a
// person to do its work: the 2025-2026 term alone matches 2,234 bills with no
// filters at all, and 400 cards is a slow first paint for a list nobody has
// scrolled yet. Then a hundred, which every letter typed drew again: about a
// second a letter on a mid-range phone (the phone audit of 25 October 2026;
// "housing" typed at a phone's pace, CPU slowed four times, held the page
// 6.5 seconds, and 2.2 with twenty-five cards and the shut filter panel left
// alone). Twenty-five cards are about 9,000px on a phone, ten screens, and
// 7,000px on a desktop (measured on the preview the same day); the observer
// below brings the next twenty-five before the reader reaches the end.
//
// This stays ONE renderer, which is the rule here -- render(true) draws the
// same list one page longer rather than a second function appending to it.
// The observer at the bottom of the list is what calls it.
// PAGE_SIZE, not PAGE: PAGE is already the member-or-committee page
// object declared above, and shadowing it emptied every legislator page.
const PAGE_SIZE = 25;
let SHOWN = PAGE_SIZE;
// THE LIST THE LAST DRAW SHOWED, as its rows' keys in order (render, below).
let SHOWN_OF = null;

// A TOPIC LEFT ON WHERE THE LIST HAS NONE (the webinar, 11 November 2026: a
// topic chosen on a past term hid every one of the 2027 bill requests, which
// carry no topics yet, and could be removed only with "clear all"). Taking a
// list whose bills say no topic at all, the filter is dropped, and the count
// line says so for as long as that list is the one on screen.
let TOPIC_NOTE=null;
function dropEmptyTopics(){
  if(!sel.topic.size||focused)return;
  const rows=IDX.filter(inTermOf);
  if(!rows.length||rows.some(b=>b.topic))return;
  TOPIC_NOTE={term,n:sel.topic.size};
  sel.topic.clear();
}
const topicNote=()=>TOPIC_NOTE&&TOPIC_NOTE.term===term&&!sel.topic.size
  ?` (the topic filter was removed: these ${termNoun()} have no topics yet)`:"";

function render(more){
  // A CHANGE TO THE RESULT SET STARTS AGAIN AT THE FIRST PAGE, AND NOTHING
  // ELSE DOES (the owner, 16 November 2026: opening a request card far down
  // the list flashed the footer and jumped back to LSR 2027-0025). Opening or
  // closing a card, a record arriving, a tab chosen inside a card: each
  // redraws through here with no argument, and each used to set the list back
  // to its first twenty-five, so the card opened forty cards down left the
  // page, the page shrank under the reader, and the scroll was clamped to the
  // last card of the first page. The first page is now taken again only where
  // the rows themselves changed (a search, a filter, a term, an order), read
  // where they are made, below; the observer's render(true) draws one page
  // more, as before.
  // A BILL REQUEST'S NUMBER OPENS THE REQUESTS' LIST (the owner, 11 November
  // 2026): a request is no term's (inTermOf), so on any term a search for
  // "2027-0002" listed nothing and offered the list in a sentence under
  // "No bills match". The term is switched to the requests' instead, and the
  // list shows the one request. (A bill's number found in another term is
  // not switched to: that is a different bill.) A bare "0002" is read as a
  // request only on the requests' list itself.
  {const R=META&&META.requests;
   REQ_BARE=!!(R&&term===R.term);
   if(R&&R.term&&term!==R.term&&!focused&&!PAGE&&!window.GR_STATIC
      &&query.trim()&&String((billNumbers(query)||[])[0]||"").startsWith("LSR")){
     term=R.term;const ys=$("#year");if(ys)ys.value=term;
     forgetCardState();REQ_BARE=true;
     ensureTerm(term).then(render);
     return;
   }}
  // A list still waiting for its term's bills says so, and nothing else: no
  // list of the bills that happen to be here (WAITING).
  if(WAITING&&!focused&&!PAGE){
    dropFocusActions();
    const r=$("#results"),c=$("#count");
    if(r)r.innerHTML=`<div class="empty">${esc(WAITING)}</div>`;
    if(c)c.textContent=WAITING;
    return;
  }
  // Page scroll only. The facet panel restores itself inside renderFacets,
  // synchronously, which is the only way it survives the repaint.
  const _y=window.scrollY;
  // And the keyboard's place: the control that has focus now, to be given it
  // back once the list is drawn again (focusKey, by repaint).
  const held=focusKey();
  // A search in words is ordered by how well each bill matches it, until the
  // reader picks an order themselves; a list with no search, or a search for
  // bill numbers, keeps number order -- but EVERY TERM'S BILLS WITH NO
  // SEARCH ARE THE NEWEST ACTION FIRST (Alice, 8 November 2026): in number
  // order they ran every term's HB 1, then every term's HB 2.
  if(!sortChosen){
    const want=query.trim()&&!billNumbers(query)?"best"
      :!query.trim()&&term===ALL_TERMS?"recent":"num";
    if(sortBy!==want){sortBy=want;const so=$("#sort");if(so)so.value=want;}
  }
  wantText();
  dropEmptyTopics();
  let rows=sortRows(IDX.filter(b=>matches(b)));
  // A CHOSEN SPONSOR'S OWN BILLS FIRST, then the bills they co-sponsored,
  // each part in the order chosen (the person, 12 October 2026).
  const bySponsor=sel.sponsor.size>0&&!billNumbers(query);
  if(bySponsor)rows=rows.filter(primeChosen).concat(rows.filter(b=>!primeChosen(b)));
  // THE FIRST PAGE AGAIN only for a list that is not the one last drawn
  // (render's first words): its rows' keys, in their order, with the term,
  // since one number names a bill in every term.
  {const of=rows.map(b=>b.id+"@"+(b.year||b.term||"")).join(",");
   if(!more&&of!==SHOWN_OF)SHOWN=PAGE_SIZE;
   SHOWN_OF=of;}
  const spN=bySponsor?rows.filter(primeChosen).length:0;
  const inTerm=IDX.filter(inTermOf).length;
  // Say when a search matched on a synonym, so nobody wonders why a bill about
  // firearms turned up for "guns".
  // Nothing when nothing is listed: "also listing bills whose titles say ..."
  // beside "0 of 2,243 bills" is a sentence about a list that is not there.
  const sh=$("#synhint");
  if(sh)sh.textContent=rows.length&&query.trim()&&!billNumbers(query)
    ? searchHint(groupsFor(query.trim()),rows) : "";
  const ids0=billNumbers(query);
  // A focused view is one bill. The count describes a list that is not on
  // screen, and on a bill's own page it read "2,234 of 2,234 bills in the
  // 2025-2026 term" above a single bill.
  // THE COUNT IS ALWAYS THERE. It was empty until a search or a filter took
  // something out, on the argument that "N of N" says nothing. The person,
  // 8 October 2026: "The bill search should always show what number of
  // bills are currently matching the search, even if there are no filters to
  // show the total number of bills for that term, and it also prevents the
  // best match from shifting when you search" -- the count appearing at the
  // first letter typed pushed the Sort select along the row under the
  // reader's eye. With nothing narrowing the list it is the term's whole
  // count, "2,243 bills in the 2025-2026 term" ("33,717 bills across all
  // terms" on the build of 7 October); narrowed, "31 of 2,243 bills in the
  // 2025-2026 term". The requests too, "302 bill requests for 2027": the
  // person said always, and their explainer says what a request is, not how
  // many there are.
  // WRITTEN ONLY WHEN IT SAYS SOMETHING NEW. The count is a live region, and
  // render() runs for far more than a new list -- each page of rows the
  // reader scrolls to, a card opened, a tab in a card, the Sort. While the
  // count was empty with nothing narrowing the list, writing "" over "" was
  // no change at all; a sentence written over the same sentence replaces its
  // text node, and a screen reader may read it out again each time.
  const narrowed=rows.length!==inTerm;
  const said=focused?""
    :ids0
    ?`${rows.length} matching ${termPhrase()}`
    :narrowed
    ?`${rows.length.toLocaleString()} of ${inTerm.toLocaleString()} ${termNoun()} ${termPhrase()}`
    :`${inTerm.toLocaleString()} ${inTerm===1?termNoun().replace(/s$/,""):termNoun()} ${
      termPhrase()}`;
  const ce=$("#count");
  const said2=said?said+topicNote():said;
  if(ce.textContent!==said2)ce.textContent=said2;
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
  //
  // AND IT IS THE BILL ITS RECORD IS: the row of the year yearOf gives, which
  // is the year of the record fetched (dkey) and of the address pushed, and
  // not merely the first of its number. A search typed with 2020's HB 703
  // open leaves it out of the list, and Back to it drew the first HB 703 in
  // the index -- 2025's, where that term's index arrived first -- over 2020's
  // record: the owner's page of 6 November 2026, by another road (that day's
  // review).
  const fy=focused?yearOf(focused):"";
  const isFb=b=>b.id===focused&&(!fy||String(b.year)===fy);
  const fb=focused?(rows.find(isFb)||IDX.find(isFb)):null;
  document.querySelector(".shell").classList.toggle("focused",!!fb);
  // NO SORT ON A BILL'S OWN PAGE (the owner's walk of dry run 9, 8 November
  // 2026): Sort orders a list, and one bill is not a list. The search box
  // and the term picker stay; the list brings Sort back.
  {const so=$("#sort");
   if(so&&so.hidden!==!!fb){
     so.hidden=!!fb;
     const lab=so.previousElementSibling;
     if(lab&&lab.tagName==="LABEL")lab.hidden=!!fb;
   }}
  const shown=fb?[fb]:rows.slice(0,SHOWN);
  // WHAT AN LSR IS, in front of the list rather than behind a link, because
  // nobody who has not worked in the building knows the word. Asked for on 18
  // September: "A brief explainer of what LSRs are should appear at the top of
  // the page", and confirmed that it is right to say some are withdrawn.
  // SHORTER, IN ALICE'S WORDS (8 November 2026): three sentences in place of
  // five. innerHTML rather than textContent here because the explainer
  // carries markup; every value in it is the site's own, none is a reader's.
  const req=META.requests&&term===META.requests.term;
  $("#summary").className=req?"count lsrnote":"count";
  if(req){
    $("#summary").innerHTML=tr("bills.requests_note","<b>Requests, not bills yet.</b> Each one, called an LSR (Legislative Service Request), is a member&rsquo;s request to have a bill drafted: a title and a sponsor, nothing more, until it is filed as a numbered {year} bill. Some are withdrawn first.",{year:esc(reqYear())});
  }else if(!fb&&!(ids&&ids.length>1)&&requestsAhead()){
    // NEXT SESSION'S REQUESTS, OFFERED FROM THE TERM THE SEARCH OPENS ON
    // (Alice, 7 November 2026): the search stays on the newest term, and this
    // says how many requests stand for the next session and opens them. The
    // count is the standing ones (B1): meta's n less the withdrawn, who stay
    // listed in the requests themselves. Gone by itself the night the
    // requests' own session becomes the newest term (requestsAhead).
    const R=META.requests;
    $("#summary").className="count lsrnote";
    $("#summary").innerHTML=`<b>${standingRequests().toLocaleString()} bill requests filed for
      ${esc(reqYear())}</b> &mdash; <button class="link" data-term="${esc(R.term)}">see them<span
      class="sr">: the bill requests for ${esc(reqYear())}</span></button>`;
  }else{
    $("#summary").textContent=fb?"":(ids&&ids.length>1
      ?`Showing ${rows.length} of the ${ids.length} bills you listed.`:"");
  }
  // A heading is a category of the Status filter (statusCat), and a request,
  // which has none, is headed by its own word.
  // COUNTED OVER THE WHOLE RESULT, not over the cards drawn so far: the
  // person, 8 October 2026, "Full totals" -- each heading's number is how
  // many of the list are in that category, "Passed 686" as the sidebar's
  // Passed says 686. It was counted over what is on screen, so that the
  // number matched the cards under it, and the hundred drawn first in the
  // 2025-2026 term (the build of 7 October: one In Progress, then Passed)
  // headed its 686 "Passed 99", a number that grew as the reader scrolled
  // and agreed with nothing else on the page.
  const grpOf=b=>statusCat(b)||chipOf(b);
  const grpN={};
  if(sortBy==="status")for(const b of rows)grpN[grpOf(b)]=(grpN[grpOf(b)]||0)+1;
  // EVERY TERM'S BILLS BY BEST MATCH, A TERM AT A TIME (Alice, 8 November
  // 2026): sortRows puts the newest term's first, and each term is headed
  // as the picker names it, with how many of the whole result are in it,
  // as a Status heading is counted. Not under a chosen sponsor, whose own
  // headings lead the list, as the Status headings give way to them.
  const byTerm=!fb&&!bySponsor&&sortBy==="best"&&term===ALL_TERMS;
  const termN={};
  if(byTerm)for(const b of rows)termN[b.term]=(termN[b.term]||0)+1;
  const termHead=(b,gi,arr)=>byTerm&&(gi===0||arr[gi-1].term!==b.term)
    ?`<h2 class="grp">${esc(termDash(b.term))} Term
       <span>${termN[b.term]===1?"1 bill":`${(termN[b.term]||0).toLocaleString()} bills`}</span></h2>`:"";
  // A LINK, TO THE BILL SEARCH. It was a button that called history.back(),
  // under a label that names a place: opened directly, a bill's page left
  // the site; reached from a member's page, "Back to bill search" went back
  // to the member (the audit of 2 October 2026, S14). The click handler goes
  // back in history only where back IS the search (backIsSearch), so the
  // list returns as it was left; everywhere else this is an ordinary link.
  // The filters in use, above the list (drawFilterBar); none over one bill.
  FBAR_N=fb?null:rows.length;
  drawFilterBar(FBAR_N);
  parkActions(!fb);
  holdHeight($("#results"));
  const spHead=(b,gi,arr)=>!fb&&bySponsor&&(gi===0||primeChosen(arr[gi-1])!==primeChosen(b))
    ?`<h2 class="grp">${primeChosen(b)?"Prime sponsored":"Co-sponsored"}
       <span>${(primeChosen(b)?spN:rows.length-spN).toLocaleString()}</span></h2>`:"";
  $("#results").innerHTML=((rows.length||fb)?shown.map((b,gi,arr)=>`${spHead(b,gi,arr)}${termHead(b,gi,arr)}
    ${!fb&&!bySponsor&&sortBy==="status"&&(gi===0||grpOf(arr[gi-1])!==grpOf(b))
      ?`<h2 class="grp">${esc(grpOf(b)||"No status recorded")}
         <span>${(grpN[grpOf(b)]||0).toLocaleString()}</span></h2>`:""}
    ${b.lsr?lsrCardHtml(b):cardHtml(b,!!fb)}`).join("")+((!fb&&rows.length>SHOWN)?`<p class="more" id="more">Showing ${
      shown.length.toLocaleString()} of ${rows.length.toLocaleString()} — <button
      class="link" data-more="1">show ${Math.min(PAGE_SIZE,rows.length-SHOWN)} more</button></p>`:"")
    :(elsewhere.length
      ?`<div class="empty"><b>Not in the ${esc(termDash(term))} term.</b><br><br>
        ${elsewhere.map(b=>`${esc(b.n)} exists in the
          <button class="link" data-term="${esc(b.term)}">${esc(b.term)}</button>
          term — ${esc(b.title||"")}`).join("<br>")}</div>`
      :emptyResult()));
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
  if(fb){focusActions(fb.id);placeActions();mountTestify(fb,detail[dkey(fb.id)]);}
  else{dropFocusActions();addressList();}
  showSelectedTab($("#results"));
  // A bill's Hearings tab holds a view with one player (hearingView): its
  // band is measured for the phone, where the player stays at the top.
  vwStick();
  if(facetsShut())facetBadge();else renderFacets();
  refocus(held);
  if(window.scrollY!==_y)window.scrollTo(0,_y);
}

// Opening a bill pushes its own address, so the view can be shared and
// reloaded -- and a reload lands on the static page, which is the one a
// crawler and a reader without JavaScript get. Going back never reloads
// anything, so the search comes back exactly as it was: same filters, same
// query, same place on the page.
function focusBill(id,href){
  focusY=window.scrollY;
  savePlace(focusY);
  // THE BILL CLICKED, IN ITS OWN TERM (6 November 2026). A number is a bill
  // only within a term: under All Terms, HB 703 is 2020's prescription-drug
  // bill and 2025's school-meals bill, and everything that finds the open
  // bill finds it by its number in the term chosen. With All Terms chosen,
  // yearOf fell back to the HB 703 whose term's index arrived first and the
  // head to the first in the list's order, so the "(2020)" result opened
  // 2025's bill at /bill/2025/hb703, or the 2025 head over 2020's record (the
  // owner's report). The link's own year says which was clicked; while it is
  // open the term is its own -- as an address naming it already makes it,
  // and as THE OPEN BILL KEEPS ITS OWN TERM says of the picker -- and the
  // term the reader chose is held and put back when it is closed (unfocus).
  const hy=/(?:^|\/)bill\/(\d{4})\//.exec(href||"");
  const own=hy&&IDX.find(b=>b.id===id&&String(b.year)===hy[1]);
  if(own&&own.term&&own.term!==term){
    if(heldTerm===null)heldTerm=term;
    term=own.term;
  }
  const wasFocused=!!focused;
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
    // The list being left keeps the words it was drawn with in its entry
    // (entryWords), and Back to it draws them (listFromAddress): Back twice
    // from a later search to /bills?status=Passed drew the later words over
    // it (the second review of 7 November 2026). Words typed in the moment
    // before the click, not yet drawn, are taken too.
    if(!wasFocused&&/^\/bills(?:\.html)?\/?$/.test(location.pathname)){
      const ns=entryWords();
      if(ns)try{history.replaceState(ns,"",location.pathname+location.search+location.hash);}catch(_){}
    }
    // The entry names the bill's term too, so Back and Forward open this
    // bill and not another of its number (the popstate handler, below).
    try{history.pushState({focus:id,term},"",
      `${BASE}bill/${_y}/${id.toLowerCase()}`);}catch(_){}
    addressed();
  }
  openBill(id);
  window.scrollTo(0,0);
}

// IS THE PAGE BEFORE THIS ONE THE BILL SEARCH? In the search itself it is
// where this bill's entry in history is the one focusBill pushed over the
// list, which the entry's own state says. A bill the address named when the
// page loaded -- /bills#2025/HB2, which the home page's Latest activity and
// the calendar link to -- pushed nothing: behind it is the home page, another
// site, or nothing at all, and "Back to bill search" did nothing in a new
// tab and went back to the home page from the home page (the review of
// 2 October 2026). There the click draws the list instead (unfocus). On a
// bill's own page back is the search only if the reader came from this
// site's /bills, which the referrer says; a page opened from a link
// elsewhere, a bookmark or a member's page has something else behind it, or
// nothing, and "Back to bill search" must not go there.
// BACK TO SEARCH RESULTS (the person, 10 October 2026: a reader browsing
// bills opens one, reads it, "and once they have the information they need,
// they'd want to back out to the search with their filters and page position
// where they'd left it"). Three parts:
//
// THE LIST'S STATE IS IN ITS ADDRESS (addressList): the term, the ticked
// filters and a chosen order, replaced into /bills as they change -- and the
// words searched where the address already names them (addressSearch's own
// rule: typing does not rewrite the address). So the list a bill was opened
// from can be opened again, by a reload, a link or a page load.
//
// ITS PLACE IS KEPT FOR THIS TAB (savePlace, restorePlace): how far down it
// was and how many bills were drawn, under that address, in sessionStorage,
// and the address itself as the tab's last search. A list opened again at
// that address, by Back or by the link, opens there.
//
// THE LINK (billHead): "Back to search results" above the trail, wherever a
// list is behind the bill -- over the search, always; on a bill's own page,
// where it came from the search (backIsSearch) or this tab has searched. It
// goes back in history where that is the search, which brings it back
// exactly; otherwise it opens the tab's last search at its place.
const PLACE_KEY="gr.place:",LAST_KEY="gr.search";
function ssGet(k){try{return sessionStorage.getItem(k);}catch(_){return null;}}
function ssSet(k,v){try{sessionStorage.setItem(k,v);}catch(_){}}
const onList=()=>!window.GR_STANDALONE&&!PAGE&&!focused
  &&/^\/bills(?:\.html)?\/?$/.test(location.pathname);
function addressList(){
  if(!onList())return;
  const was=new URLSearchParams(location.search),p=new URLSearchParams();
  if(was.get("q"))p.set("q",was.get("q"));
  const terms=(META&&META.terms)||[];
  if(term&&term!==defaultTerm(META))p.set("term",term);
  for(const k of ["status","type","topic","committee","sponsor","party","voteday","rsa"])
    for(const v of sel[k])p.append(k,v);
  // TAGS:BEGIN
  for(const v of sel.tag)p.append("tag",v);
  // TAGS:END
  if(withCosp)p.set("cosp","1");
  if(sortChosen&&sortBy)p.set("sort",sortBy);
  const s=p.toString(),want=location.pathname+(s?"?"+s:"");
  // The entry's words follow the list's at every drawing, so Back to it,
  // after Forward or after a reload, draws what the reader left (the third
  // review of 7 November 2026: they were kept only when a bill was opened,
  // and went stale when the box changed after Back).
  const ns=entryWords();
  if(want!==location.pathname+location.search||ns){
    try{history.replaceState(ns||history.state,"",want+location.hash);addressed();}catch(_){}
  }
  ssSet(LAST_KEY,want);
}
// THE LIST'S WORDS IN ITS OWN ENTRY (the reviews of 7 November 2026). A
// list's address names its words only where a search was run; words typed
// and not run are in no address. The entry holds them, beside its address,
// only where the address does not already say them: no q and no words is a
// list of no words. The state the entry should have, or null where it has it.
function entryWords(){
  const st=history.state&&typeof history.state==="object"?history.state:null;
  const aq=new URLSearchParams(location.search).get("q")||"";
  const want=query!==aq?query:undefined;
  const has=st&&typeof st.words==="string"?st.words:undefined;
  if(want===has)return null;
  const ns=Object.assign({},st||{});
  if(want===undefined)delete ns.words;else ns.words=want;
  return ns;
}
function savePlace(y){
  if(!onList())return;
  ssSet(PLACE_KEY+location.pathname+location.search,
    JSON.stringify({y:y===undefined?window.scrollY:y,shown:SHOWN}));
}
function restorePlace(){
  if(!onList())return;
  let at=null;
  try{at=JSON.parse(ssGet(PLACE_KEY+location.pathname+location.search)||"null");}catch(_){}
  const nav=(typeof performance!=="undefined"&&performance.getEntriesByType)
    ?(performance.getEntriesByType("navigation")[0]||{}).type:"";
  const asked=ssGet("gr.back")==="1";
  if(asked)ssSet("gr.back","");
  if(!at||!(asked||nav==="back_forward"))return;
  if(at.shown>SHOWN){SHOWN=at.shown;render(true);}
  requestAnimationFrame(()=>window.scrollTo(0,at.y||0));
}
if(typeof window!=="undefined"&&window.addEventListener)
  window.addEventListener("pagehide",()=>savePlace());
// Where the link leads when history cannot take the reader back: the tab's
// last search, else the search itself.
const lastSearch=()=>ssGet(LAST_KEY)||"";
function showBack(){
  return !window.GR_STANDALONE||backIsSearch()||!!lastSearch();
}

function backIsSearch(){
  if(!window.GR_STANDALONE)return !!(history.state&&history.state.focus);
  // A bill opened in a new tab came from the search and has no page behind
  // it in this tab: back would do nothing at all.
  if(history.length<2)return false;
  try{
    const r=new URL(document.referrer);
    return r.origin===location.origin&&/^\/bills(?:\.html)?\/?$/.test(r.pathname);
  }catch(_){return false;}
}

function unfocus(y,popped){
  // On a bill's own page there is no list behind it to back out to: the
  // reader arrived at that bill directly. Drawing two thousand cards under
  // an address that names one bill would be the wrong page at the wrong URL,
  // so leaving the bill means leaving the page.
  //
  // Unless Back has put a list's entry back into this page: a bill opened
  // from the search and then reloaded keeps the search's entry, and Back
  // reaches it without a load (the reviews of 7 November 2026). Sending the
  // reader to bare /bills there landed them on the newest term with an
  // empty box, the words gone -- the likeliest road to the empty box the
  // laptop saw. The address Back put back is loaded as it is.
  // A load is not Back to the browser, so the list is told it is
  // (restorePlace), and opens where the reader stood in it.
  if(window.GR_STANDALONE){
    if(popped){ssSet("gr.back","1");location.replace(location.pathname+location.search+location.hash);}
    else location.href=BASE+"bills";
    return;
  }
  // Back out to where the reader was standing when they opened the bill --
  // except when they got here by typing a new search, where the old position
  // belongs to a list that is no longer on screen.
  if(y===undefined)y=focusY;
  focused=null;
  // BUT NOT ON BACK (the laptop's test of 7 November 2026). Back has already
  // put the list's own entry back, /bills?q=HB+703&term=all, and pushing
  // /bills over it threw away the search's words -- the list still showed
  // HB 703's results under /bills?term=all, which a reload or a shared link
  // could not bring back -- and the bill's entry with them, so Forward went
  // nowhere. The list is drawn as that entry's address names it
  // (listFromAddress), so the box, the list and the address agree, and
  // nothing is written over it.
  if(popped){
    // A term the reader chose with the picker while the bill was open is
    // still theirs, and the list is drawn in it (its address follows); a
    // term only held while the bill was open gives way to the entry's.
    const picked=heldPicked?heldTerm:null,order=heldSort;
    heldTerm=null;heldPicked=false;heldSort=null;
    listFromAddress();
    if(picked!==null&&picked!==term){term=picked;forgetCardState();const ys=$("#year");if(ys)ys.value=term;}
    // ...and so is an order chosen there.
    if(order!==null){sortBy=order;sortChosen=true;const so=$("#sort");if(so)so.value=order;}
    // A term whose bills are still on their way is said to be loading, as
    // the picker says it, and drawn when they are here: one fetch each,
    // however many have asked (ensureTerm).
    const want=term===ALL_TERMS?((META&&META.terms)||[]):[term];
    // A term that fails is drawn as far as it came, never left "loading".
    if(want.some(x=>!LOADED.has(x))){
      WAITING=term===ALL_TERMS?"loading every term…":"loading "+term+"…";
      const done=()=>{WAITING="";render();};
      Promise.all(want.map(ensureTerm)).then(done,done);
    }
  }
  else{
    // The term the picker chose while the bill was open, taken now.
    if(heldTerm!==null){term=heldTerm;heldTerm=null;forgetCardState();}
    heldPicked=false;heldSort=null;
    // Leaving a bill named in the address would mean the next refresh
    // reopened it, which is not where the reader is standing. Back to the
    // list's own address rather than the bill's -- with the words where the
    // list's address already names them, as on a bill the address opened
    // over the search (/bills?q=HB+703#2020/HB703, "Back to search results").
    const keep=/^\/bills(?:\.html)?\/?$/.test(location.pathname)?location.search:"";
    try{history.pushState({},"",BASE+"bills"+keep);}catch(_){}
  }
  addressed();
  render();
  window.scrollTo(0,y);
}

// BACK AND FORWARD, WITHIN THIS DOCUMENT. An entry focusBill pushed carries
// the bill it opened; going back from it to the list arrives with no state,
// and that used to be the whole test: no state and a bill open meant "back
// to the list". But a link to a place on the page fires the same event, and
// "Skip to this bill" is one. On a bill's own page -- where it has been the
// first Tab stop since the box stopped taking focus on load -- pressing it
// ran unfocus(), which there leaves for /bills: the skip link threw the
// reader off the bill on all 33,717 bill pages, and on /bills#2025/HB2 it
// shut the bill (the review of 2 October 2026). So: where only the fragment
// moved, nothing is redrawn; and an address that is still a bill's own is
// that bill, whatever its fragment and whichever tab it names.
const BILL_PATH=/^\/bill\/\d{4}\/[a-z]{2,5}\d+(?:\.html)?(?:\/[a-z]+)?\/?$/i;
window.addEventListener("popstate",e=>{
  const f=e.state&&e.state.focus;
  const was=STOOD;
  addressed();
  if(f){
    // An entry focusBill pushed names the bill's term: back in it, with the
    // reader's own term held as focusBill held it, before the number is
    // looked up (THE BILL CLICKED, IN ITS OWN TERM).
    const t=e.state.term;
    const moved=!!t&&t!==term&&IDX.some(b=>b.id===f&&b.term===t);
    if(moved){if(heldTerm===null)heldTerm=term;term=t;}
    // ...on the tab its address names, as a page loaded there opens it: Back
    // to All Terms forgot each card's tab, and Forward to /bill/2020/hb703/text
    // drew the Summary under it (the deep walk of dry run 183).
    const tb=BILL_TABS[tabFromPath()];
    if(tb&&openTab[f]!==tb){
      openTab[f]=tb;
      if(tb==="6"){const y=yearOf(f);
        const row=IDX.find(x=>x.id===f&&(!y||String(x.year)===y))||IDX.find(x=>x.id===f);
        if(row)needVersions(row);}
    }
    // Back from a place on the bill's page to the entry that opened it: the
    // bill is already drawn, and the browser puts the scroll back itself.
    if(focused!==f||moved){focused=f;openBill(f);window.scrollTo(0,0);}
    return;
  }
  if(!focused||was===STOOD||BILL_PATH.test(location.pathname))return;
  unfocus(undefined,true);
});

function openBill(id){
  openCards.add(id);
  // A bill request has no record to ask for: its card opens onto what its row
  // holds (lsrBody).
  if(/^LSR\d/.test(String(id))){repaint();return;}
  // THE KEY OF THE BILL ASKED FOR, taken now and kept (the reviews of 6
  // November 2026). dkey follows the term, and the term moves while a record
  // is on its way: opened from All Terms, 2020's HB 703 holds its own term
  // until Back puts All Terms back, and a record that arrived after that was
  // stored under the key All Terms gives the number -- 2025's -- so 2025's
  // HB 703, opened next, drew 2025's head over 2020's record: the owner's
  // page, on a slow connection.
  const key=dkey(id);
  if(detail[key]){repaint();return;}
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
    detail[key]={events:[],rollcalls:[],stations:[],reports:[],sponsors:[],
      documents:[],amendments:[],next_step:"Detail unavailable",
      _error:why+"\n"+url};
    repaint();
  };
  const take=(txt,where)=>{
    let d;
    try{ d=JSON.parse(txt); }
    catch(_){ throw new Error(`${where} arrived but is not JSON. It starts: ${
      txt.slice(0,80).replace(/\s+/g," ")}`); }
    detail[key]=d; repaint();
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
    // The button is replaced by the player, so where the button had focus
    // the player takes it: left on nothing, the next Tab press started from
    // the top of the record (S1). Only then -- a time pressed under the
    // player builds it through this same click and keeps its own focus.
    const had=document.activeElement===stub;
    stub.outerHTML=`<iframe id="yt_${pid}" allow="autoplay" allowfullscreen
      src="https://www.youtube-nocookie.com/embed/${vid}?start=${from}&autoplay=1&enablejsapi=1"
      title="${esc(stub.dataset.title||"Hearing recording")}"></iframe>`;
    const frame=had&&document.getElementById("yt_"+pid);
    if(frame&&frame.focus)frame.focus({preventScroll:true});
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
    const opening=!anOpen.has(id);
    opening?anOpen.add(id):anOpen.delete(id);
    clampAnalysis();
    // THE KEYBOARD STAYS WITH WHAT THE READER IS LOOKING AT. The button sits
    // under the text it opens, so opening HB 2's analysis carried it, and
    // the focus on it, 12,000px down the page while the reader was still at
    // the top of the text (the audit of 2 October 2026, M13). Opened, focus
    // goes to the start of the text that has just been shown -- as "Show 3
    // more" below puts it on the first line it reveals -- and "Show less" is
    // at the end of it, a Tab away. Shut, the button is brought back into
    // view, since the text it was under has gone from above it.
    const text=an.closest(".anbox")&&an.closest(".anbox").querySelector(".antext");
    if(opening&&text){text.tabIndex=-1;text.focus({preventScroll:true});}
    else if(!opening&&an.scrollIntoView)an.scrollIntoView({block:"nearest"});
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
  // "Show 3 more", in How it got here: the hidden lines open where they are,
  // with no redraw, and the keyboard lands on the first of them, since the
  // button it was on is gone. jOpen keeps them open through the next redraw.
  const jm=e.target.closest("[data-jmore]");
  if(jm){
    jOpen.add(jm.dataset.jmore);
    const ul=jm.closest(".jl");
    const shut=ul?[...ul.querySelectorAll("li[hidden]")]:[];
    for(const li of shut)li.hidden=false;
    jm.closest("li").remove();
    if(shut[0]){shut[0].tabIndex=-1;shut[0].focus({preventScroll:true});}
    return;}
  // The bill search's own groups. The Laws page draws its filters with the
  // same classes and opens them itself (build_rsa's LANDING_JS).
  const g=e.target.closest("#facets .fhead");
  if(g){if(g.dataset.g==="rsa"&&!openGroups.has("rsa"))rsaReopen();
    openGroups.has(g.dataset.g)?openGroups.delete(g.dataset.g):openGroups.add(g.dataset.g);renderFacets();return;}
  // The phone's filter disclosure. The class goes on .shell rather than on
  // the panel because the stylesheet has to move three things -- the button,
  // the panel and the results -- and one of them is the element being shown.
  const ftb=e.target.closest("#ftoggle");
  if(ftb){
    const sh=document.querySelector(".shell");
    const open=sh.classList.toggle("fopen");
    ftb.setAttribute("aria-expanded",open?"true":"false");
    if(open)renderFacets();
    return;}
  const un=e.target.dataset.unpick;
  if(un){sel.sponsor.delete(un);render();return;}
  // A pill's × in the filters in use, and its Clear all (filterBarHtml).
  const ux=e.target.closest&&e.target.closest("[data-unfilter]");
  if(ux){unfilter(ux.dataset.unfilter,ux.dataset.v,e.detail===0,
    [...document.querySelectorAll(".fbar .fx")].indexOf(ux));return;}
  if(e.target.closest&&e.target.closest("[data-fclear]")){clearFilters(e.detail===0);return;}
  // Left click opens in place; a modified or middle click falls through to
  // the anchor and gets the static page in a new tab, which still works.
  // On a record page there is no search list to come back to, so the arrow
  // is left to be an ordinary link to the bill's own page.
  const dt=PAGE?null:e.target.closest("a.cnum");
  if(dt&&e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){
    e.preventDefault();
    focusBill(dt.closest(".card").dataset.id,dt.getAttribute("href"));return;}
  // "Back to bill search" is a link to the search. Where the page before
  // this one in history is the search itself, a plain click goes back to it
  // instead, so the list comes back as the reader left it -- same filters,
  // same place. In the search with something else behind the bill, the list
  // is drawn here, where its bills already are, and not fetched again. A
  // modified or middle click, and a bill's own page with anything else
  // behind it, are left to the link.
  if(e.target.closest("[data-back]")){
    if(e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){
      if(backIsSearch()){e.preventDefault();history.back();}
      else if(!window.GR_STANDALONE){e.preventDefault();unfocus();}
      else ssSet("gr.back","1");
    }
    return;}
  // The same thing the observer does, for a keyboard, a reader, or a
  // browser with no IntersectionObserver. The button is replaced by the rows
  // it asked for, so the keyboard goes to the first of them: left on nothing,
  // the next Tab press started from the top of a list two hundred bills long
  // (the review of 2 October 2026). The observer moves nothing.
  if(e.target.closest("[data-more]")){
    const from=SHOWN;
    SHOWN+=PAGE_SIZE;render(true);
    const next=$("#results").querySelectorAll(".card")[from];
    const head=next&&next.querySelector(".ctitle");
    if(head&&head.focus)head.focus({preventScroll:true});
    return;}
  // Everything below reads .card. A member's or a committee's page has none,
  // so a tab click here threw on tab.closest(".card").dataset and the tab did
  // nothing. Those pages have their own handler, registered above.
  if(PAGE)return;
  const head=e.target.closest(".card .ctitle")||cardBackground(e);
  if(head){const id=head.closest(".card").dataset.id;
    if(term===ALL_TERMS){const own=head.closest(".card").querySelector("a.cnum");
      if(own){location.href=own.href;return;}}
    if(openCards.has(id)){openCards.delete(id);render();}else openBill(id);return;}
  // A tally in the Summary: the Votes tab, at that vote's card, where the bill is open.
  const vl=e.target.closest("a[data-vote]");
  if(vl&&e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){
    const vc=vl.closest(".card[data-id]");
    if(vc){
      e.preventDefault();
      const cid=vc.dataset.id;
      openTab[cid]="1";
      if(focused===cid)tabAddress("votes");
      try{history.replaceState(history.state,"",location.pathname+location.search+"#"+vl.dataset.vote);}catch(_){}
      VOTE_JUMP=vl.dataset.vote;
      render();jumpToVote();return;}}
  // A card's own tab: a chamber's page has tabs of its own (chamberStrip).
  const tab=e.target.closest(".card .tab");
  if(tab){
    const cid=tab.closest(".card").dataset.id;
    openTab[cid]=tab.dataset.t;
    // WHEREVER A BILL IS OPEN, not only on its own page. GR_BILL is set by
    // build_bill_pages and by nothing else, so opening a bill from the search
    // page and switching tabs left the address on /bill/2012/hb1181 however
    // many tabs you walked -- the reader could not link to what they were
    // looking at, and the same click on the same card put a different address
    // in the bar depending on how they arrived. focused===cid is the real
    // condition: it says this card is the one open, which is what makes its
    // tab the page's subject. openBill already pushes the bill's own address
    // in the search view, so there is a path here for tabAddress to append to.
    if(focused===cid)tabAddress(slugOf(BILL_TABS,tab.dataset.t));
    // The versions index is fetched when the tab is opened and not before,
    // which is the whole reason it is a separate file.
    if(tab.dataset.t==="6"){
      // The bill drawn, of the year its record is (yearOf), not the first of
      // its number in the index: 2025's HB 2 opened from All Terms asked for
      // 2023's versions and stayed on "Loading the versions…" (the reviews
      // of 6 November 2026).
      const y=yearOf(cid);
      const row=IDX.find(x=>x.id===cid&&(!y||String(x.year)===y))||IDX.find(x=>x.id===cid);
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
  // THE TERM BUTTONS AND NOTHING ELSE: "exists in the X term" and the
  // requests' offer are button.link[data-term]. A glossary mark is a
  // span[data-term] too, with its tooltip inside it (components.js, arm), and
  // a click on the tooltip's words set the term to "FN" -- an empty picker,
  // idx/FN.json asked for, and the open bill drawn as another of its number
  // (the review of 6 November 2026).
  const jt=e.target.closest("button[data-term]");
  // Its bills fetched first where they are not here yet: a request's
  // number is offered next session's requests (requestOffer), which no
  // search has loaded.
  if(jt){term=jt.dataset.term;$("#year").value=term;forgetCardState();ensureTerm(term).then(render);return;}
  // A part of a search that found nothing, offered on its own. Chosen from
  // the keyboard (a click with no pointer behind it), the focus goes to the
  // search box, which now holds the word: drawing the list again takes the
  // button away, and the focus was left on nothing.
  const jq=e.target.closest("[data-q]");
  if(jq){query=jq.dataset.q;$("#q").value=query;clearTimeout(QDRAW);addressSearch(query);render();
    if(e.detail===0)$("#q").focus();
    return;}
  // The Laws Changed box's words go with its filter: they named it.
  if(e.target.id==="clear"){Object.values(sel).forEach(s=>s.clear());withCosp=false;rsaText="";RSA_OFF.open=false;render();return;}
});
document.addEventListener("change",e=>{
  if(PAGE)return;                       // the facet checkboxes are not drawn there
  if(e.target.id==="cosp"){withCosp=!!e.target.checked;render();return;}
  const f=e.target.dataset.f;if(!f)return;
  e.target.checked?sel[f].add(e.target.value):sel[f].delete(e.target.value);render();});
// TAGS:BEGIN
// The Tags group's box (tagGroup), as the Topic group's is heard below.
document.addEventListener("input",e=>{
  if(PAGE||e.target.id!=="gbox")return;
  tagFilter=e.target.value;renderFacets();
  const b=document.getElementById("gbox");if(b){b.focus();b.setSelectionRange(b.value.length,b.value.length);}
});
// TAGS:END
// A law offered under the Laws Changed box, pressed, or its Clear (rsaGroup):
// the keyboard into the box only for a click with no pointer behind it.
document.addEventListener("click",e=>{
  const pk=e.target.closest&&e.target.closest("[data-rsapick]");
  if(!pk||PAGE)return;
  rsaChoose(pk.dataset.rsapick||"",e.detail===0);
});
// THE LAWS CHANGED BOX, heard where it is drawn (rsaGroup, the person, 26
// October 2026). #facets is drawn once and its groups into it, so these
// outlive every drawing of the box; and Escape on an open list is the list's
// before it reaches the document, whose Escape shuts the phone's panel.
{const fx=$("#facets");if(fx&&fx.addEventListener){
  const shut=()=>{clearTimeout(RSADRAW);RSA_OFF.open=false;RSA_OFF.act="";RSA_OFF.miss=null;rsaPaint();};
  // THE BOX SAYS WHAT IS CHOSEN once the reader is done with it (the review
  // of 26 October 2026). With RSA 91-A chosen, the box emptied, or "tax"
  // typed and left, still listed 91-A's 29 bills under ?rsa=91-A while the
  // box read as nothing chosen, or as tax. Now an emptied box takes the law
  // away, as Clear does, after the pause in typing, on Return or on leaving
  // it; and words that chose nothing give way to the chosen law's number when
  // the box is left or Escape is pressed.
  const back=()=>{const ch=sel.rsa.size?[...sel.rsa][0]:"";if(!ch||rsaText===ch)return;
    rsaText=ch;const b=document.getElementById("rsabox");if(b)b.value=ch;};
  const emptied=()=>!String(rsaText||"").trim()&&sel.rsa.size>0;
  // A NUMBER TYPED WHOLE IS CHOSEN ON LEAVING, as Return chooses it (the
  // review of 26 October 2026): "91-A" typed and the box left by a tap
  // elsewhere still read 91-A over a list that it did not filter, with no
  // badge and no line -- where before this filter's box, typing 91-A filtered
  // by itself. A number no bill changes ("91") is not, and words stay as
  // typed. The number is the one read as the box lost the focus (`was`), but
  // only while the box still reads what it read then: left by ticking
  // Withdrawn, the tick's click and change narrowed the list before the box
  // was heard to be left, and no bill left in it changed 91-A; but an offer,
  // a section, Clear or Clear all pressed after "540" or "91-A:" changes the
  // box's words, and what was pressed is what is chosen (the review of 26
  // October 2026), and a snapshot left by a press that brought no click is
  // never taken for words typed since.
  let was=null;
  const leave=()=>{const w=was;was=null;if(RSA_OFF.open)shut();
    if(emptied())return rsaChoose("");
    const a=w&&w.t===rsaText?w.a:rsaNumber();
    if(a&&!sel.rsa.has(a))return rsaChoose(a);
    back();};
  fx.addEventListener("input",e=>{
    if(!e.target||e.target.id!=="rsabox")return;
    rsaText=e.target.value;RSA_OFF.open=true;RSA_OFF.act="";RSA_OFF.miss=null;rsaLawsLoad();
    // A colon typed asks for the sections, which are offered by heading.
    const T=rsaTyped(rsaText);if(T&&T.sec)rsaHeadsLoad();
    clearTimeout(RSADRAW);RSADRAW=setTimeout(()=>{if(emptied())rsaChoose("");else rsaPaint(true);},FO_WAIT);
  });
  fx.addEventListener("keydown",e=>{
    if(!e.target||e.target.id!=="rsabox")return;
    const k=e.key;
    if(k==="ArrowDown"||k==="ArrowUp"){
      clearTimeout(RSADRAW);RSA_OFF.open=true;
      const rows=rsaOffers(rsaText).rows;
      if(!rows.length){rsaPaint(true);return;}
      e.preventDefault();
      const i=rows.findIndex(r=>r.a===RSA_OFF.act);
      RSA_OFF.act=rows[k==="ArrowDown"?(i+1)%rows.length:i<=0?rows.length-1:i-1].a;
      rsaPaint();
    }else if(k==="Enter"){
      e.preventDefault();
      const a=rsaEnter();
      if(a||emptied())rsaChoose(a,true);
      // Nothing to choose: the line under the box says why.
      else{clearTimeout(RSADRAW);RSA_OFF.open=true;RSA_OFF.miss=rsaText;rsaPaint(true);}
    }else if(k==="Escape"){
      const st=rsaState();
      if(st.rows.length||st.note){e.preventDefault();e.stopPropagation();shut();back();}
    }else if(k==="Tab"){
      // Tab leaves the box as its keydown is heard, before the focus moves:
      // what that chooses is drawn with the focus still in the box, so Tab
      // goes on from there to where it was sent (the review of 26 October
      // 2026: chosen once the focus had gone on, the drawing took away Read
      // the law, or the bill, it had gone to, and the focus fell to the page).
      leave();
    }
  });
  // Left otherwise -- a press, a tap, a phone's Done -- the list shuts and the
  // box says what is chosen, the focus left where it went; but not when the
  // box was only drawn again and the focus put back in it.
  const left=()=>{const b=document.getElementById("rsabox");if(!b||b!==document.activeElement)leave();else was=null;};
  // AND NOT UNTIL A PRESS'S CLICK IS HEARD (the review of 26 October 2026).
  // Pressed with the list open, Clear, an offer, "Read the law" and Clear all
  // filters took the focus from the box, the list shut under the pointer
  // before it was let go, what was pressed moved up from under it, and no
  // click came: Clear did not clear. A press and the focus it takes come in
  // one task, so `pressing` is true for that task alone and cannot outlast it
  // (a flag cleared by the release stayed set where the release never reached
  // the page, and the box left later by the keyboard waited on a press long
  // over). A tap's click comes in the same task as the focus it takes,
  // before anything set going by it.
  let pressing=false;
  const heard=()=>setTimeout(left,0);
  document.addEventListener("pointerdown",()=>{pressing=true;setTimeout(()=>{pressing=false;},0);},true);
  fx.addEventListener("focusout",e=>{
    if(!e.target||e.target.id!=="rsabox")return;
    was={t:rsaText,a:rsaNumber()};
    if(pressing)document.addEventListener("click",heard,{once:true});else heard();
  });
}}
// THE SPONSOR FILTER OFFERED FOR A NAME IS TAKEN IN PLACE (sponsorHint, 17
// October 2026). The name typed lists nothing, so it leaves the box, and the
// person is ticked as the one sponsor chosen; the list and its address follow.
// A click with a modifier key is left to the link, which opens the same
// address in a new tab.
document.addEventListener("click",e=>{
  const sp=e.target.closest&&e.target.closest("[data-sponsor]");
  if(!sp||PAGE||e.ctrlKey||e.metaKey||e.shiftKey||e.button)return;
  if(e.preventDefault)e.preventDefault();
  query="";$("#q").value="";clearTimeout(QDRAW);addressSearch("");
  sel.sponsor.clear();sel.sponsor.add(sp.dataset.sponsor);render();
  if(e.detail===0)$("#q").focus();
});
// THE VOTES TAB'S FIND, AS YOU TYPE (the webinar pass of 23 October 2026: it
// filtered only on Return or on leaving the box, and after Return the focus
// fell to the page). A pause in typing draws the list; the box keeps the
// focus and the caret, as the sponsor box below does.
let VQDRAW=null;
document.addEventListener("input",e=>{
  if(PAGE&&e.target.dataset&&e.target.dataset.pf==="vq"){
    const v=e.target.value;clearTimeout(VQDRAW);
    VQDRAW=setTimeout(()=>{if(!PAGE||PAGE.vq===v)return;PAGE.vq=v;PAGE.vshow=0;voteAddress();renderPage();
      const b=document.querySelector('input[data-pf="vq"]');
      if(b){b.focus({preventScroll:true});const n=b.value.length;b.setSelectionRange(n,n);}},250);
    return;}
  if(e.target.id==="sbox"||e.target.id==="tbox"){
    const id=e.target.id;
    if(id==="sbox")sponsorFilter=e.target.value;else topicFilter=e.target.value;
    renderFacets();
    const b=document.getElementById(id);if(b){b.focus();b.setSelectionRange(b.value.length,b.value.length);}}});
// AN OFFERED SEARCH, TAKEN, IS THE ONE THE ADDRESS NAMES. A reader who
// arrived at /bills?q=vacine%20exemption and took "vaccine exemption (12)"
// was shown the twelve bills under an address that still named the
// misspelling: a reload, or the link sent to somebody else, said "No bills
// match" (2 October). Only an address that names a search is rewritten; one
// that names none is left as it is, as typing in the box leaves it.
//
// AND A SEARCH THE READER RAN IS IN THE ADDRESS (`always`). Typing "HB 2" and
// Return on /bills left the address /bills, where the same search from the
// home page is /bills?q=HB%202: it could not be reloaded, bookmarked or sent
// to anybody (the audit of 2 October 2026, M16). Return and the Search button
// name the search in the address whether or not it named one; from then on
// it does name one, so typing keeps it in step, and an emptied box takes the
// search out of it again. Replaced, not pushed: the page is the same page.
function addressSearch(q,always){
  try{
    const p=new URLSearchParams(location.search);
    const had=p.get("q");
    if((had==null&&!always)||(had||"")===q)return;
    if(q)p.set("q",q);else p.delete("q");
    const s=p.toString();
    history.replaceState(history.state,"",location.pathname+(s?"?"+s:"")+location.hash);
    addressed();
  }catch(_){}
}
// Running a search from one bill's own view means leaving that bill, so it
// waits to be told. Everywhere else the list narrows as you type, which is
// what a search box on a list should do.
function submitSearch(){
  query=$("#q").value;
  // From a member's or a committee's page, searching means going to the bill
  // search -- that is where results are drawn. Running render() here wrote
  // the list over the record instead, and the only way back was a reload.
  //
  // AND FROM A BILL'S OWN PAGE, which keeps the box. There the search left
  // for /bills by unfocus(), which carries nothing: the words were thrown
  // away and the reader landed on the whole list with an empty box, and the
  // address written for the search went onto the bill's own entry in history
  // instead, /bill/2025/hb2?q=housing (the review of 2 October 2026). It goes
  // where the others go, with the words -- and with the term, where the
  // bill's is not the newest, since /bills opens on the newest unless told.
  // The term picker is not on a bill's own page (staticChromeDown hides it),
  // so the term is the bill's own.
  if(PAGE||window.GR_STATIC||window.GR_STANDALONE){
    const to=[];
    const newest=((META&&META.terms)||[])[0];
    if(window.GR_STANDALONE&&!PAGE&&term&&newest&&term!==newest)
      to.push("term="+encodeURIComponent(term));
    // Half an emoji is not an address: encodeURIComponent throws on a
    // surrogate with no partner (find.js, _fwell).
    if(query)to.push("q="+encodeURIComponent(
      query.replace(/[\uD800-\uDFFF]/gu,"\uFFFD")));
    location.href=BASE+"bills"+(to.length?"?"+to.join("&"):"");
    return;
  }
  // From a bill opened in the search, running the search means leaving that
  // bill. Back out to the top: the scroll position from before it was opened
  // belongs to a list that is no longer the one on screen. unfocus() has
  // pushed /bills by the time the search is written into the address, so it
  // is the list's entry that names it.
  if(focused){unfocus(0);addressSearch(query,true);return;}
  // On the list the results narrow as they type, a moment behind the typing
  // (QWAIT). Return means they have finished: draw now, let go of the
  // keyboard and bring the first result up to where they are looking.
  clearTimeout(QDRAW);
  addressSearch(query,true);
  render();
  $("#q").blur();
  const first=$("#results")&&$("#results").querySelector(".card");
  if(first)first.scrollIntoView({block:"start",behavior:"smooth"});
}
/* THE LIST IS DRAWN WHEN THE TYPING PAUSES, NOT ON EVERY LETTER. Each letter
   drew the whole list again before the next could be typed: across all
   terms that is 33,000 bills read for "s", "sc", "sch" ... and the letters
   of "college students voting rights act" kept a desktop busy for 36
   seconds, at five seconds a letter on a phone (2 October). /search has
   waited 120 ms since it was written; this box does now. Return, and the
   Search button, draw at once (submitSearch). */
let QDRAW=0;
const QWAIT=120;
// ACROSS EVERY TERM, LONGER. A drawing there reads 33,717 bills, and on a
// phone it held the page for one to three seconds; at 120 ms a letter typed
// at an ordinary pace started a fresh one every time, and "college tuition"
// took 13 seconds to type (the review of 2 October 2026). 400 ms is under the
// gap a reader leaves when they stop to look.
const QWAIT_ALL=400;
$("#q").addEventListener("input",e=>{
  // No live narrowing on a record page: there is no list under it to narrow,
  // and render() would replace the record with one.
  if(focused||PAGE||window.GR_STATIC)return;
  query=e.target.value;
  clearTimeout(QDRAW);
  // An address that names a search names the one on screen (addressSearch).
  QDRAW=setTimeout(()=>{addressSearch(query);render();},
                   term===ALL_TERMS?QWAIT_ALL:QWAIT);
});

// THE FILTERS OFFERED AS THE BOX IS TYPED IN (filterOffers, filterCombo): a
// topic or a committee by its name. Return takes the offer the arrow keys
// are on, and with none searches the words, as it did before there were any.
const QOFFERS=filterCombo($("#q"),{offers:billOffers,choose:takeOffer,label:"Filters that match the words typed"});
$("#q").addEventListener("keydown",e=>{
  if(e.key==="Enter"){e.preventDefault();if(QOFFERS.enter())return;submitSearch();}
});
$("#qgo").addEventListener("click",submitSearch);
// "/" JUMPS TO THE SEARCH BOX, BUT NEVER OUT OF SOMETHING BEING TYPED IN.
// The only exemption used to be the bill-search box itself, so anywhere else
// the key was eaten. Checked with a real keypress rather than a synthetic
// event, in the Report a problem box on /bill/2025/hb1.html: keydown key "/",
// target TEXTAREA, isTrusted true -- the textarea's value did not change and
// focus moved to #q. A reader typing "and/or", a date, or a citation into the
// box we give them for telling us the record is wrong loses the character and
// their place. The hint that taught this shortcut is no longer on any page, so
// nobody is pressing "/" on purpose; what remains is a key that goes missing.
//
// Every field that takes typing is left alone -- the header search (#findq) is
// an input and was eating it too, and select and contenteditable are here so
// the next field added does not have to rediscover this. The whole report box
// is exempt including its Send button: nothing inside the box a reader is
// filling in should move them out of it.
const typingIn=el=>!!el&&(/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)
  ||el.isContentEditable||!!(el.closest&&el.closest(".report")));
document.addEventListener("keydown",e=>{
  if(e.key==="/"&&!typingIn(e.target)){e.preventDefault();$("#q").focus();$("#q").select();}
  // ESCAPE SHUTS THE PHONE'S FILTER PANEL, from inside it or from its button,
  // and leaves the keyboard on the button that opens it -- as it does for the
  // sections menu and the search. It did nothing here (the audit of
  // 2 October 2026, M17).
  if(e.key==="Escape"&&e.target.closest&&e.target.closest("#facets,#ftoggle")){
    const sh=document.querySelector(".shell"),ftb=$("#ftoggle");
    if(sh&&ftb&&sh.classList.contains("fopen")){
      sh.classList.remove("fopen");ftb.setAttribute("aria-expanded","false");ftb.focus();}
  }
  // Tabs carry role="tab", and a screen reader user is told they are tabs, so
  // the arrow keys have to work. They did nothing before.
  const tab=e.target.closest&&e.target.closest(".tab");
  if(tab&&(e.key==="ArrowLeft"||e.key==="ArrowRight"||e.key==="Home"||e.key==="End")){
    const tabs=[...tab.parentElement.querySelectorAll(".tab")];
    const i=tabs.indexOf(tab);
    const to=e.key==="Home"?0:e.key==="End"?tabs.length-1
      :(i+(e.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;
    // The click redraws the strip, which destroyed the tab just focused and
    // sent focus to <body>: every arrow press lost the keyboard's place.
    // Focus goes back to the tab of the same identity in the new strip.
    const next=tabs[to];
    const again=next.id?`#${CSS.escape(next.id)}`
      :next.dataset.pt!==undefined?`.tab[data-pt="${next.dataset.pt}"]`:null;
    e.preventDefault();next.click();
    const fresh=again&&document.querySelector(again);
    (fresh||next).focus();
  }});


// THE SESSION DAY'S VOTES, DRAWN BY THE FUNCTIONS THE BILL PAGES USE.
//
// build_session_pages.py writes the day as static HTML and leaves each counted
// vote as an empty .svote with the count beside it in words. A ROLL CALL IS
// DRAWN WITH THE VOTES TAB'S OWN DISPLAY (the person, 9 October 2026, v2:
// "Don't add a click to see how each member voted, the live site already has
// that functionality in the votes tab by clicking the bar chart or the
// Democrat Yes, Democrat No ..."): its ring and its party rows, which show the
// members when pressed. The ballots are the bill's own record -- the day's
// .svote names the bill and the place of the roll call's card on its Votes tab
// (data-bill, data-card) -- fetched the first time the day is drawn, one
// record a bill. A division, and a roll call whose record will not come, is
// drawn as before with simpleDonut, from the payload at the foot of the page.
//
// Nothing here is required for the page to be true: the count, which side
// prevailed and what it did to the bill are all in the HTML already.
// ONE BILL'S RINGS WHEN ITS RECORD COMES (the phone audit of 25 October
// 2026): a day of 29 bills redrew all 40 rings as each record arrived, and a
// mid-range phone froze for seconds. `only` is the bill whose record came;
// with none, every ring is drawn.
let SESSV=null;        // {votes: payload}; the bills' records are BILL_RECS
function drawSessionVotes(only){
  if(!SESSV)return;
  const slots=document.querySelectorAll(".svote[data-vote]");
  for(const slot of slots){
    const key=slot.getAttribute("data-bill"), card=slot.getAttribute("data-card");
    if(only&&key!==only)continue;
    const n=parseInt(slot.getAttribute("data-vote"),10), v=SESSV.votes[n];
    let html="";
    try{
      if(key&&card!=null){
        // A term's roll calls on no bill ("nobill/2025-2026") are a record
        // of their own, drawn as the member Votes tab draws them.
        const nb=key.indexOf("nobill/")===0;
        (nb?nobillRecord:billRecord)(key,drawSessionVotes);
        const d=BILL_RECS[key], rc=d&&(d.rollcalls||[])[+card];
        if(rc&&(rc.members||[]).length){
          const id=nb?`NB-${key.split("/")[1]}`:key.split("/")[1];
          html=donut(id,+card,rc);
        }
      }
      if(!html&&v)html=simpleDonut(v,"session",n);
    }catch(e){html="";}
    if(html&&slot.innerHTML!==html)slot.innerHTML=html;
  }
}
// VIEW THE REPORT (the owner's words, 23 October 2026): a term's list of
// votes not on a bill links a session day's fold by its id, "#rep-2026-H-290"
// (vote_passage.report_html), and a link to a shut fold should open it.
(function(){
  function openReport(){
    var id="";
    try{ id=decodeURIComponent((location.hash||"").slice(1)); }catch(e){ return; }
    if(!/^rep-[\w-]+$/.test(id))return;
    var el=document.getElementById(id);
    if(el&&el.tagName==="DETAILS"&&!el.open){ el.open=true; el.scrollIntoView(); }
  }
  openReport();
  window.addEventListener("hashchange",openReport);
})();
(function(){
  var tag=document.getElementById("sessvotes");
  if(!tag||typeof simpleDonut!=="function")return;
  var votes;
  try{ votes=JSON.parse(tag.textContent||"[]"); }catch(e){ return; }
  if(!votes.length)return;
  SESSV={votes:votes};
  drawSessionVotes();
})();
// THE DAY'S INDEX (build_session_pages.day_index; the owner, 24 October
// 2026: "some sort of index on the left side below the video for each action
// and bill so you can more quickly look for the bill you're trying to
// find"). It is written shut. Beside the cards, on a wide screen, it is
// opened here and stays open; on a phone it is a bar above the cards, held
// at the top of the screen, that names the bill being read, opens when
// pressed and shuts when a line is chosen or Escape is pressed. As the page
// scrolls, the line of the card or section being read is marked
// (aria-current) and kept in view inside the index -- by scrolling the
// index, never the page. Without this the index is a fold of plain links.
(function(){
  var nav=document.getElementById("dayidx");
  var fold=nav&&nav.querySelector?nav.querySelector("details"):null;
  var list=fold&&fold.querySelector?fold.querySelector(".dilist"):null;
  // Each line links its place by the page's own address and the place's id,
  // "session/H/2026-03-11#HB1601": the page's <base href="/"> sends a bare
  // "#HB1601" to the home page.
  var as=nav&&nav.querySelectorAll?nav.querySelectorAll('a[href*="#"]'):[];
  if(!fold||!list||!as.length)return;
  var mq=window.matchMedia?window.matchMedia("(min-width:60em)"):null;
  var wide=function(){return !!(mq&&mq.matches);};
  if(wide())fold.open=true;
  if(mq&&mq.addEventListener)mq.addEventListener("change",function(){fold.open=wide();});
  var now=fold.querySelector(".dinow"),sum=fold.querySelector("summary");
  var links={};
  for(var i=0;i<as.length;i++)links[as[i].getAttribute("href").split("#")[1]]=as[i];
  nav.addEventListener("click",function(e){
    if(!wide()&&e.target&&e.target.closest&&e.target.closest("a"))fold.open=false;});
  document.addEventListener("keydown",function(e){
    if(e.key!=="Escape"||!fold.open||wide())return;
    fold.open=false;
    if(sum&&sum.focus)sum.focus();});
  if(!("IntersectionObserver" in window))return;
  // What is being read: the first card in the band near the top of the
  // screen, or failing a card, the first section there. A later card of a
  // bill taken up twice marks the bill's one line (data-at).
  var seen=[],cur=null;
  var targets=[].slice.call(document.querySelectorAll(".w4s > .w4[id], .wday .card[id]"));
  var lineOf=function(el){return links[el.getAttribute("data-at")||el.id];};
  var mark=function(){
    var pick=null;
    for(var j=0;j<targets.length&&!pick;j++)
      if(seen.indexOf(targets[j])>=0&&targets[j].classList.contains("card"))pick=targets[j];
    for(var k=0;k<targets.length&&!pick;k++)if(seen.indexOf(targets[k])>=0)pick=targets[k];
    var a=pick&&lineOf(pick);
    if(!a||a===cur)return;
    if(cur)cur.removeAttribute("aria-current");
    a.setAttribute("aria-current","location");cur=a;
    if(now){var n=a.querySelector(".dinum");now.textContent=(n||a).textContent;}
    keep();
  };
  // The box that scrolls is the index beside the cards, under its own line
  // (the summary, held at its top), and the list on a phone.
  var keep=function(){
    if(!cur||!fold.open)return;
    var box=list.scrollHeight>list.clientHeight+1?list:nav;
    if(box.scrollHeight<=box.clientHeight+1)return;
    var r=cur.getBoundingClientRect(),b=box.getBoundingClientRect();
    var top=b.top+(box===nav&&sum?sum.offsetHeight:0);
    if(r.top<top||r.bottom>b.bottom)box.scrollTop+=r.top-top-(b.bottom-top)/3;
  };
  fold.addEventListener("toggle",keep);
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){
      var at=seen.indexOf(e.target);
      if(e.isIntersecting&&at<0)seen.push(e.target);
      else if(!e.isIntersecting&&at>=0)seen.splice(at,1);});
    mark();},{rootMargin:"-15% 0px -75% 0px"});
  targets.forEach(function(t){io.observe(t);});
})();


// THE READER'S OWN DATE IN A CITATION, not the page's. shell.py writes into
// every .citeday the day the page's record last changed (the build day where
// it has none), so a page read without JavaScript still gives a true date for
// the page rather than "Accessed ." -- and a reader who has
// JavaScript gets the day they actually read it, which is what every one of
// those four formats means by "accessed".
//
// IN ONE FORM, "24 Sept. 2026", whatever language the browser is set to (the
// person, 24 September). This was toLocaleDateString(undefined, ...), so an
// English citation read "24 septembre 2026" in a French browser and
// "September 24, 2026" in an American one. CITE_MONTHS is shell.py's list,
// and preflight holds the two to one answer for every month.
const CITE_MONTHS=["Jan.","Feb.","Mar.","Apr.","May","June","July","Aug.",
  "Sept.","Oct.","Nov.","Dec."];
function citeDay(d){ return d.getDate()+" "+CITE_MONTHS[d.getMonth()]+" "+d.getFullYear(); }
// APA and Chicago: "October 30, 2026", the site's full date (dateWords), as
// shell.cite_day_full writes the build's (the cohesion audit, B-5).
function citeDayFull(d){
  return dateWords(d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"
    +String(d.getDate()).padStart(2,"0"),"full");
}
(function(){
  var els=document.querySelectorAll(".citeday");
  var now=new Date(), s=citeDay(now), full=citeDayFull(now);
  for(var i=0;i<els.length;i++)
    els[i].textContent=els[i].classList&&els[i].classList.contains("citefull")?full:s;
  // The note under the Cite box says which date is written in; with the
  // reader's own it says that instead.
  var rd=document.querySelectorAll(".citeread");
  for(var k=0;k<rd.length;k++)rd[k].textContent="The date below is the day you read this page.";
  // The Copy buttons are written hidden, so a page read without JavaScript
  // offers none that does nothing; here they work, so here they show.
  var bs=document.querySelectorAll("[data-citecopy]");
  for(var j=0;j<bs.length;j++)bs[j].hidden=false;
})();

// COPY, beside each form of "Cite this page" (the person, 24 September).
// writeText is called inside the click itself, which is what lets a browser
// allow it. Where it is refused or absent the form's text is selected
// instead, so Ctrl+C does the rest, and either way the result is said in the
// block's status line for a reader who cannot see the button change.
document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest("[data-citecopy]");
  if(!b)return;
  const form=document.getElementById(b.getAttribute("data-citecopy"));
  if(!form)return;
  const name=b.getAttribute("data-citename")||"";
  const st=document.getElementById("citestate");
  const say=m=>{if(st)st.textContent=m;};
  // A form's text as it reads: BibTeX's line breaks are real ones, and a
  // no-break space is pasted as a space.
  const text=String(form.textContent||"").replace(/ /g," ").trim();
  const done=()=>{
    b.textContent="Copied";
    say(`The ${name} citation is copied.`);
    setTimeout(()=>{b.textContent="Copy";},2000);
  };
  const pick=()=>{
    try{
      const sel=window.getSelection&&window.getSelection();
      const r=document.createRange&&document.createRange();
      if(sel&&r){r.selectNodeContents(form);sel.removeAllRanges();sel.addRange(r);}
    }catch(_){}
    say(`The ${name} citation is selected: press Ctrl+C, or Command+C on a Mac, to copy it.`);
  };
  if(navigator.clipboard&&navigator.clipboard.writeText)
    navigator.clipboard.writeText(text).then(done,pick);
  else pick();
});
// ONE PANE OPEN AT A TIME in the row above a heading. Follow's pane and the
// citation's open over the page from the same corner, so opening one shuts
// the other rather than stacking one on top of it.
// A disclosure inside a pane -- Follow's "Follow by RSS instead" (18 October
// 2026) -- is part of that pane: opening it must not shut the pane it is in,
// and a press elsewhere in the pane must not fold it again.
const paneInPane=d=>!!(d.parentNode&&d.parentNode.closest&&d.parentNode.closest("details"));
document.addEventListener("toggle",e=>{
  const d=e.target;
  if(!d||!d.open||!d.closest||!d.closest("#pageacts"))return;
  document.querySelectorAll("#pageacts details[open]").forEach(o=>{
    if(o!==d&&!o.contains(d)&&!paneInPane(o))o.open=false;});
},true);
// AND A PRESS ANYWHERE ELSE SHUTS IT (the person, 10 October 2026: the
// buttons "should deselect when you click on the background since right now
// there isn't an easy way to deselect them"): Cite, Follow and Report a
// problem in the row, wherever the row is -- a bill's, a member's or a
// committee's head, a session day's, a chamber's -- and Escape does the same,
// putting the keyboard back on the button it opened from. Share's line
// ("Link copied") goes with them, unless the press was on the line itself,
// where an address it could not copy waits to be selected.
const ACT_PANES="#pageacts details[open], .pageacts details[open], .racts details[open]";
const SHARE_PRESS="[data-share]";   // named here: Share's own listener is the one that names it
// UNDER ITS OWN BUTTON, AS WIDE AS THE ROW (the owner, 6 November 2026; app.css
// at "AND ON A PHONE, UNDER ITS OWN BUTTON"). A head's pane is measured from
// the button that opens it, and on a phone the buttons are two to a row: CSS
// cannot know which of the two a button is, so this says where the row
// starts, from the button, and how wide it is (--pl, --pw), as it opens --
// on the press, before the pane is drawn, and on the toggle for a pane
// opened any other way -- and again when the window changes. A desktop's
// rule does not read them. Nothing here opens, shuts or moves focus.
// AND HOW FAR DOWN THE BUTTONS GO (--pdown): a short pane -- Testify's, one
// sentence -- lay over the buttons beneath it and left the foot of Report a
// problem showing under it, 8px of a button at 390 (the owner's follow-up,
// 6 November 2026). The pane is at least as tall as what is left of the
// actions below its button, so it covers what it lies on.
// AND WHERE THE BUTTON'S OWN BOX STARTS (--bl, --bt), for the band that a
// high-contrast mode draws with the button rather than the pane's shadow,
// which that mode takes away (app.css, at "IN FORCED COLOURS").
function placeActPane(d){
  if(!d||!d.closest||d.tagName!=="DETAILS"||!d.closest(".racts"))return;
  const row=d.closest(".pageacts")||d.closest(".racts");
  const r=row.getBoundingClientRect(), b=d.getBoundingClientRect();
  d.style.setProperty("--pl",Math.round(r.left-b.left)+"px");
  d.style.setProperty("--pw",Math.round(r.width)+"px");
  d.style.setProperty("--pdown",Math.max(0,Math.round(d.closest(".racts").getBoundingClientRect().bottom-b.bottom))+"px");
  const s=d.querySelector(":scope > summary");
  if(s){
    const sr=s.getBoundingClientRect();
    d.style.setProperty("--bl",Math.round(r.left-sr.left-s.clientLeft)+"px");
    d.style.setProperty("--bt",Math.round(sr.height-s.clientTop)+"px");
  }
}
document.addEventListener("click",e=>{
  const s=e.target&&e.target.closest&&e.target.closest(".racts details > summary");
  if(s)placeActPane(s.parentElement);
},true);
document.addEventListener("toggle",e=>{if(e.target&&e.target.open)placeActPane(e.target);},true);
window.addEventListener("resize",()=>document.querySelectorAll(".racts details[open]").forEach(placeActPane));
document.addEventListener("click",e=>{
  const at=e.target;
  if(!at||!at.closest)return;
  document.querySelectorAll(ACT_PANES).forEach(d=>{if(!d.contains(at)&&!paneInPane(d))d.open=false;});
  if(!at.closest(SHARE_PRESS)&&!at.closest(".sharestate"))
    document.querySelectorAll(".sharestate").forEach(s=>{if(s.textContent)s.textContent="";});
});
document.addEventListener("keydown",e=>{
  if(e.key!=="Escape")return;
  const open=[...document.querySelectorAll(ACT_PANES)];
  if(!open.length)return;
  const back=open.find(d=>d.contains(document.activeElement));
  open.forEach(d=>{d.open=false;});
  const s=back&&back.querySelector("summary");
  if(s&&s.focus)s.focus();
});

// A PAGE THAT CARRIES ITS OWN RECORDINGS -- a study committee's Videos tab, a
// chamber's -- draws them once the whole of this script has run
// (staticVideos): the parts of the view are defined above, after the branch
// that takes the search down on such a page. A study committee's tabs first
// (ssLand), so the view is drawn in the pane the address shows.
if(window.GR_STATIC){ssLand();staticVideos();}

