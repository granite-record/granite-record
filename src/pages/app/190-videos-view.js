// ========================================================== THE VIDEOS VIEW
/* A BODY'S RECORDINGS AS ONE PLAYER AND ITS PLAYLIST (the owner, 26 October
   2026: "Committee pages should have a videos tab that essentially compiles
   the youtube playlist of that committee's meetings in a structured table
   with the date, list of bills, and other pertinent information that can fit
   in a relatively compact table. The embedded player could potentially take
   up most of the tab, and the other videos persist in a scrollable playlist
   on the right side, with the most recent entry in the playlist as the
   default. Same goes for session days, or study committees, commissions,
   etc"). One renderer for every page whose body is livestreamed: a
   committee's Videos tab (renderCommitteeVideos), a chamber's
   (/session/house and /session/senate) and a study or statutory committee's
   Videos tab, the last two drawn from the JSON their pages carry
   (staticVideos).

   o:     {who, what, key, heading, level, rows, chosen, href(id), pid(row), source}
          who is the player's bar ("Senate Finance", "The House"), what the
          same in a sentence ("Recording of the House, ..."), where it
          differs; key the term or the page, so a list drawn again for the
          same keeps its place;
          level the list's heading's, 2 where nothing above it on the page is
          an h2 (a chamber's), or else 3.
   a row: {id, date, began, seconds, kinds (chips' HTML), line (text),
          detail (HTML, or a function that gives it)}

   THE PLAYER IS THE SITE'S STILL. Nothing loads from YouTube -- no
   thumbnail, no frame, no script -- until a person presses Play (the privacy
   page's promise), and the one handler that plays every other recording
   plays this one. It starts at 0: a bill's moment is a button of its own
   (jumpButtons), the Meetings tab's own, so a moment is shown only as the
   record has it -- a stated boundary plain, an inferred one "approximate".

   ONE CAPTION UNDER THE PLAYER (the manager's review of 26 October 2026,
   5): "Senate Finance · May 12, 2026 · 12:58 PM · 1 h 49 min · On YouTube",
   with the outside-link mark app.css gives every link that leaves the
   site. A start or a length the index does not have is left out with its
   separator (the owner's fix S9): never a lone dot, never a dot at the end
   of a line.

   THE LIST IS ROWS OF LINKS, each to its own address (#v-<id>), the chosen
   one aria-current and marked by a bar as well as its colour (review, 7),
   in the document after what plays and what it covers, which is the Tab
   order. Beside the player on a wide screen, as tall as the player and
   scrolling inside.

   ON A PHONE, A PLAYLIST AS YOUTUBE'S IS (the owner, 29 October 2026: "the
   player stays at the top (sticky) while the list of recordings scrolls
   beneath it"). The player and its caption stay at the top of the window,
   under the tab strip that stays there already (.rhead ~ .tabs), and what
   the recording covers and then every recording of the term scroll on the
   page beneath it: the whole list, where it had been the newest twenty and a
   button for the rest, since the list is now what the page scrolls through
   under what plays. House Finance's 106 rows are drawn in a few milliseconds
   (measured 29 October 2026), so nothing is drawn later. Still no box that
   scrolls inside a page that scrolls (review, 6): the page is what scrolls.
   How far down the strip and the player reach is measured (vwStick), so a
   row, a bill or a moment the keyboard moves to is scrolled clear of them
   and never left under the player. */
// The bills under the player, on a phone, the first few and a button for
// the rest (cmteVideoDetail), as YouTube folds a description.
const VW_BILLS=6;
// The view on this page, for choosing a row in it: one a page.
let VVIEW=null;
const VVIEWS={};
// "1 h 49 min", "36 min": a recording's length to the nearest minute, and
// never under one.
function vwLength(s){
  const m=Math.max(1,Math.round((Number(s)||0)/60));
  return m>=60?`${Math.floor(m/60)} h${m%60?` ${m%60} min`:""}`:`${m} min`;
}
/* THE DOT GOES WITH THE PART AFTER IT (the owner's fix S9, as a card's
   byline has it in app.css). Parts (HTML) joined by the middle dot the eye
   reads and the comma a screen reader says: each part after the first is
   drawn with its dot at its head, held to it by a no-break space, so a line
   breaks before a dot and never after one -- at 390px the caption had ended
   "Senate Finance · May 5, 2026 · 1:28 PM ·" over "1 h 15 min", and at 1280
   House Commerce's its length and a dot over "On YouTube". A part that is
   not there is left out with its dot: never a lone one. */
const vwJoin=parts=>parts.filter(Boolean).map((p,i)=>i?`<span class="sr">,</span> <span class="vwi"><span aria-hidden="true">&middot;&nbsp;</span>${p}</span>`:p).join("");
// When it began and how long it ran, each only where the index says it.
const vwWhen=r=>[r.began?clock(r.began):"",r.seconds?vwLength(r.seconds):""].filter(Boolean);
// A row may carry its own `video` (the YouTube id where its own id is a row's),
// `who`, `what`, `from` (the second the player opens at) and `playText`: a
// bill's sittings share recordings and each opens at its own moment.
function vwPlayer(o,r){
  const pid=o.pid(r), day=dateWords(r.date), who=r.who||o.who, what=r.what||o.what||who;
  const vid=r.video||r.id, from=Math.max(0,Math.floor(r.from||0));
  // A date, a time, a length or "On YouTube" is not broken across two lines
  // (.vwcap .vwi): at 390px the link broke between its two words.
  const cap=vwJoin([`<b>${esc(who)}</b>`,...[day,...vwWhen(r)].map(esc),
    `<a href="https://www.youtube.com/watch?v=${esc(vid)}${from?`&t=${from}s`:""}" target="_blank" rel="noopener">On YouTube</a>`]);
  return `<div class="player vwplay" data-player="${esc(pid)}"><button type="button" class="pstub"`
    +` data-title="${esc(recTitle(what,r.date))}" aria-label="${esc(`Play the recording of ${what}, ${day}`)}"`
    +` data-embed="${esc(vid)}|${from}|${esc(pid)}"><span>${icon("play")}</span><span>${esc(r.playText||"Play the recording")}</span></button>`
    // A bill's view (o.bare) draws no caption: its row says it (hearingView).
    +(o.bare?"":`<div class="pbar vwcap"><p>${cap}</p></div>`)+`</div>`;
}
const vwDetail=r=>typeof r.detail==="function"?r.detail():String(r.detail||"");
// A row's second line is text, or its parts, which take the middle dot.
function vwLine(l){
  const t=Array.isArray(l)?vwJoin(l.filter(Boolean).map(esc)):esc(l||"");
  return t?`<span class="vwl">${t}</span>`:"";
}
/* A ROW IS TWO LINES (the review of 29 October 2026, "a relatively compact
   table"): the date, and beside it how many bills ("Oct 14, 2026 · 26
   bills"), with when it began and how long it ran; under them its kinds,
   then its first bills, cut short with an ellipsis where they do not fit. The
   kinds had pushed the bills onto a third line, rows of 90px, and House
   Finance's list showed five of its 106 beside the player at 1280. The count
   is on the first line so that the cut never takes it; every bill is under
   the player once the row is chosen, and the row's whole text is its name to
   a screen reader. */
function vwRow(o,r){
  const when=vwWhen(r), line=vwLine(r.line);
  return `<li><a class="vwrow" href="${esc(o.href(r.id))}" data-vwpick="${
      esc(r.id)}"${r.id===o.chosen?' aria-current="true"':""}><span class="vwd">${
    vwJoin([esc(dateWords(r.date)),r.count?`<span class="vwn">${esc(r.count)}</span>`:""])}</span>${
    when.length?`<span class="vwt"><span class="sr">, </span>${vwJoin(when.map(esc))}</span>`:""}${
    r.kinds||line?`<span class="vwb"><span class="sr">, </span>${r.kinds||""}${r.kinds&&line?" ":""}${
      line}</span>`:""}</a></li>`;
}
function videoView(o){
  const rows=o.rows||[];
  if(!rows.length)return "";
  const on=rows.find(r=>r.id===o.chosen)||rows[0];
  o.chosen=on.id;
  VVIEW=o;
  if(o.key)VVIEWS[o.key]=o;
  // THE SKIP LINK COMES STRAIGHT AFTER THE PLAYER AND ITS CAPTION, before
  // what the recording covers: after it, as it stood, a keyboard passed House
  // Commerce's 37 bills and their moments -- 63 stops -- to reach the link
  // that was to spare them, and again after every row chosen, which puts the
  // keyboard back on Play (the review of 29 October 2026). Play, On YouTube,
  // this, then the detail, then the rows.
  const lv=o.level===2?2:3;
  // THE LIVE STRIP'S PLACE (the live layer's design, approved; the manager,
  // 29 October 2026): the first thing in the band that stays at the top on a
  // phone, empty and hidden, so it is no height at all. The live layer's
  // live.js fills it ("House Finance is live now · Watch") and draws it with
  // its own .lv-strip rules, only on the Videos tab and only once the live
  // card has scrolled away; nothing here writes or styles it.
  return `<div class="vw" data-vwkey="${esc(o.key||"")}"><div class="vwmain"><div class="lv-strip" hidden></div>${vwPlayer(o,on)}`
    +'<p class="vwsay sr" role="status" aria-live="polite"></p>'
    +`<a class="vwskip" href="${esc(location.pathname+location.search)}#vwlist" data-vwskip>Skip to the list of recordings</a></div>`
    +`<div class="vwdet"><div class="vwdetin">${vwDetail(on)}</div></div>`
    +`<div class="vwside"><div class="vwin"><h${lv} class="vwh" id="vwh">${esc(o.heading)}</h${lv}>`
    +`<ol class="vwlist" id="vwlist" aria-labelledby="vwh">${rows.map(r=>vwRow(o,r)).join("")}</ol>`
    +"</div></div>"
    +(o.source?`<p class="src vwsrc">${o.source}</p>`:"")+"</div>";
}
// The chosen row in view INSIDE its list, the least that shows it, and never
// by scrollIntoView, which would move the page as well. A list that does not
// scroll (a phone's) is left alone. A row is measured from the list's top:
// the list is the rows' offsetParent (app.css, .vwlist{position:relative}),
// and where it is not, the list's own offset is taken off.
function vwListShow(a){
  const list=a&&a.closest(".vwlist"), li=a&&a.closest("li");
  if(!list||!li||list.scrollHeight<=list.clientHeight)return;
  const top=li.offsetParent===list?li.offsetTop:li.offsetTop-list.offsetTop, end=top+li.offsetHeight;
  if(top<list.scrollTop)list.scrollTop=top;
  else if(end>list.scrollTop+list.clientHeight)list.scrollTop=end-list.clientHeight;
}
/* CHOOSING A ROW (a plain click, or Return on it; a click with a key held or
   the middle button opens the row's own address in a new tab). Everything
   changes in place -- the row marked, the player, its caption and what is
   under it -- and nothing else is drawn again, so the list keeps its place.
   The address becomes the row's (replaceState: no history entry a row).

   BEFORE ANYONE HAS PRESSED PLAY in this view the still becomes the chosen
   recording's still, nothing is asked of YouTube, and the keyboard goes to
   Play, whose name says what was chosen, so one more Return plays it. ONCE
   A FRAME IS OPEN, the reader has pressed Play here, and choosing a row is
   choosing what plays: the new still is pressed through the one handler,
   which builds the frame, the status line says so, and the keyboard stays on
   the row to choose again. The player is brought into view either way.

   ON A PHONE the player stays at the top already (vwPinned), so it is what
   it covers that is brought into view: chosen before a first press, the page
   goes back up to the recording's bills and their moments, just under the
   player, as YouTube opens a recording's description; once something plays,
   the list stays where it is, the keyboard on the row, to choose again. */
function vwChoose(a){
  const box=a.closest(".vw"), o=(box&&box.dataset&&VVIEWS[box.dataset.vwkey])||VVIEW;
  const r=o&&box&&o.rows.find(x=>x.id===a.dataset.vwpick);
  if(!r)return;
  const playing=!!box.querySelector(".vwplay iframe");
  // THE ROW THAT IS PLAYING, pressed again, goes on playing: a new frame
  // over it would start the recording over from its beginning. It is only
  // brought into view, and the address named it, as a row pressed does --
  // one that had arrived naming a recording not on file still named that.
  if(playing&&r.id===o.chosen){
    try{history.replaceState(history.state,"",o.href(r.id));}catch(_){}
    addressed();
    if(!vwPinned(box))box.querySelector(".vwplay").scrollIntoView({block:"nearest"});
    return;}
  o.chosen=r.id;
  if(o.onChoose)o.onChoose(r.id);
  // Chosen here, so the address it is about to name is not an arrival
  // (showVideo) to be landed on again.
  vwTried=vwLanded=r.id;
  box.querySelectorAll(".vwlist a[aria-current]").forEach(x=>x.removeAttribute("aria-current"));
  a.setAttribute("aria-current","true");
  const old=box.querySelector(".vwplay");
  old.insertAdjacentHTML("beforebegin",vwPlayer(o,r));
  old.remove();
  box.querySelector(".vwdetin").innerHTML=vwDetail(r);
  try{history.replaceState(history.state,"",o.href(r.id));}catch(_){}
  addressed();
  const player=box.querySelector(".vwplay"), stub=player.querySelector(".pstub"),
    say=box.querySelector(".vwsay");
  if(say)say.textContent="";
  if(playing){
    stub.click();
    if(say)say.textContent=`Playing: ${dateWords(r.date)}`;
  }else stub.focus({preventScroll:true});
  if(!vwPinned(box)){player.scrollIntoView({block:"nearest"});return;}
  vwStick();
  const det=box.querySelector(".vwdet");
  if(!playing&&det&&det.getBoundingClientRect().top<vwUnder(box))det.scrollIntoView({block:"start"});
}
/* THE PLAYER THAT STAYS, MEASURED. On a phone the player and its caption
   (.vwmain) stay at the top of the window, under the page's tab strip where
   that strip stays too (.rhead ~ .tabs, 45px at 390px; it can wrap). How far
   down the two reach is written on the view, --vwtop (the strip's foot, where
   the player sticks) and --vwstick (the player's foot), and app.css keeps
   every row, bill and moment that far from the top when it is scrolled to:
   a keyboard moving down the list, or back up it, never has its place under
   the player. Measured again whenever either changes size.

   AND ONLY WHERE IT LEAVES THE LIST ROOM (the review of 29 October 2026,
   1). Stuck at every width below 60em whatever the height, the strip, the
   player and its caption were 517px of a phone held sideways (844 by 390),
   and 548 of a 900 by 600 window, and the list went out of sight under
   them: no row the keyboard reached there was in view. The view is marked
   [data-vwpin], which app.css's sticky rule asks for, only where the three
   take at most VW_PIN_SHARE of the window's height -- 37% of a 390 by 844
   phone, 56% of a small one (375 by 548) with its browser's bars showing,
   46% of a 768 by 1024 tablet (measured on House Finance, 29 October 2026);
   elsewhere the player scrolls with the page, as it did before. The height
   is the document's, which on a phone is the window with the browser's
   bars showing, so the bars folding away as the page scrolls do not pin and
   unpin the player under the reader's thumb. */
const VW_PIN_SHARE=0.6;
const vwPinned=box=>{const m=box&&box.querySelector(".vwmain");
  return !!m&&getComputedStyle(m).position==="sticky";};
// The strip above the view's pane, where it stays at the top of the window.
function vwStrip(box){
  const pane=box.closest("[role=tabpanel]");
  const tab=pane&&document.getElementById(pane.getAttribute("aria-labelledby")||"");
  const strip=tab&&tab.closest("[role=tablist]");
  return strip&&getComputedStyle(strip).position==="sticky"?strip:null;
}
// Where what stays at the top of the window ends: the player's foot while
// it stays, or else the strip's, where the strip stays.
const vwUnder=box=>{
  const m=vwPinned(box)?box.querySelector(".vwmain"):vwStrip(box);
  return m?m.getBoundingClientRect().bottom:0;};
const vwRoom=()=>document.documentElement.clientHeight||window.innerHeight||0;
let VW_SEEN=null, VW_WATCHED=[];
function vwStick(){
  document.querySelectorAll(".vw").forEach(box=>{
    const main=box.querySelector(".vwmain"), strip=vwStrip(box);
    const top=strip?Math.ceil(strip.getBoundingClientRect().height):0;
    const band=top+Math.ceil(main?main.getBoundingClientRect().height:0);
    const pin=!!main&&band<=vwRoom()*VW_PIN_SHARE;
    if(pin)box.setAttribute("data-vwpin","");else box.removeAttribute("data-vwpin");
    box.style.setProperty("--vwtop",`${top}px`);
    // What is under the player is kept clear of its foot where it stays,
    // and of the strip's where it does not.
    box.style.setProperty("--vwstick",`${pin?band:top}px`);
    // Watched for a change of size, and only watched afresh when they are
    // other elements: watching starts with a report, which runs this again.
    const els=[main,strip].filter(Boolean);
    if(typeof ResizeObserver==="undefined"||(els.length===VW_WATCHED.length&&els.every((x,i)=>x===VW_WATCHED[i])))return;
    VW_SEEN=VW_SEEN||new ResizeObserver(()=>vwStick());
    VW_SEEN.disconnect();
    els.forEach(el=>VW_SEEN.observe(el));
    VW_WATCHED=els;
  });
  vwEdge();
}
/* THE STAYING PLAYER'S FOOT (the review of 29 October 2026, 7): rows went
   under the caption with nothing to say the player was a layer over them.
   The view is marked [data-vwstuck], which draws a rule and a shadow at the
   band's foot (app.css), once it has gone up past the strip's foot -- the
   player is then held there over what scrolls -- and not while the player
   rests where it stands, which needs no line under it. Read once a frame
   while the page scrolls. */
function vwEdge(){
  document.querySelectorAll(".vw").forEach(box=>{
    const top=parseFloat(box.style.getPropertyValue("--vwtop"))||0;
    const stuck=box.hasAttribute("data-vwpin")&&vwPinned(box)&&box.getBoundingClientRect().top<top-1;
    if(stuck)box.setAttribute("data-vwstuck","");else box.removeAttribute("data-vwstuck");
  });
}
let vwEdgeAsked=false;
window.addEventListener("scroll",()=>{
  if(vwEdgeAsked)return;
  vwEdgeAsked=true;
  requestAnimationFrame(()=>{vwEdgeAsked=false;vwEdge();});
},{passive:true});
window.addEventListener("resize",()=>vwStick());
// AND WHERE THE BROWSER'S OWN SCROLLING LEAVES IT THERE: the focus, once
// moved, is put clear of the player. Chromium keeps scroll-margin for
// scrollIntoView and not for the Tab key: going back up House Finance's list
// with Shift+Tab at 390px, 31 rows of 40 came to rest under the player with
// app.css's margin alone, and none with this (measured 29 October 2026).
// Where the player does not stay (a wide screen, or a window too short for
// it), what stays is the strip, and the focus is put clear of that.
// And to where the player's foot comes to rest, not where it is: Shift+Tab
// back into a short list from below has the end of the view pushing the
// staying player up, and a scroll up lets it drop back to --vwstick, over
// the row just put clear of it (ss57's 19 rows at 390px, the review of 30
// October 2026).
document.addEventListener("focusin",e=>{
  const t=e.target, box=t&&t.closest&&t.closest(".vw");
  if(!box||t.closest(".vwmain"))return;
  requestAnimationFrame(()=>{
    const under=vwUnder(box), top=t.getBoundingClientRect().top;
    const rest=vwPinned(box)?parseFloat(box.style.getPropertyValue("--vwstick"))||0:0;
    const clear=Math.max(under,rest);
    if(under>0&&top<clear)window.scrollBy(0,top-clear-8);
  });
});
document.addEventListener("click",e=>{
  const t=e.target&&e.target.closest?e.target:null;
  if(!t||e.defaultPrevented)return;
  const pick=t.closest("a[data-vwpick]");
  if(pick){
    if(e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
    e.preventDefault();vwChoose(pick);return;}
  // The rest of a recording's bills on a phone, and the keyboard on the
  // first it brought.
  const all=t.closest("[data-vwall]");
  if(all){
    const list=document.getElementById(all.getAttribute("aria-controls"));
    const first=list&&list.querySelector(".vwrest a");
    if(list)list.classList.add("vwopen");
    all.remove();
    if(first)first.focus();
    return;}
  // Past what is under the player, to the row that is chosen.
  const skip=t.closest("a[data-vwskip]");
  if(skip){
    const on=document.querySelector('.vwlist a[aria-current="true"]')||document.querySelector(".vwlist a");
    if(on){e.preventDefault();on.focus();vwListShow(on);}
    return;}
});

