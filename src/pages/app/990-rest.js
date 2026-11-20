// ============================================ POLISH 2: A COMMITTEE'S MEETINGS
//
// THE MEETINGS TAB (the person's feedback of 9 October 2026: item 1, bill
// CARDS on a committee's page, each saying "what happened to that bill at
// that meeting"; item 12, "make clearer what changed on each bill at that
// meeting, if anything did"; item 6, one player per livestream; item 14, the
// newest meeting open, or the day the address names; v8, an interim study
// report not recommending future legislation, or making no recommendation,
// shown as killed with what the committee voted; v13, sortable oldest or
// newest first). One entry a day, folded: its date, times, how many bills
// and how many voted on, its room and its kinds of meeting; opened, one
// sentence of what changed, a player for each recording of the day, and a
// card for each bill with its line for this meeting. What happened is the
// build's (committee_acts, build_committees: each meeting's `outcomes`);
// this says it.
const nBills=n=>`${n.toLocaleString()} bill${n===1?"":"s"}`;
// A recommendation's code as the record's shorthand, marked for its popover
// (C9), where it is one of the four a reader meets everywhere.
const REC_TERM={OTP:"OTP",OTPA:"OTPA",ITL:"ITL",IS:"IS"};
function recSaid(words,code){
  return `${esc(words||"")}${REC_TERM[code]?` (${termMark(code,code)})`:""}`;
}
const tallyOf=a=>a&&a.yeas!=null&&a.nays!=null?`${a.yeas}\u2013${a.nays}`:"";
// One act of the committee on a bill, as a sentence: a recommendation with
// its tally and the minority's; an interim study report, which recommended
// the subject for future legislation (the green arrow of How it got here)
// or killed the bill (v8: "listed as killed, explaining what the committee
// voted"); a retention. What the report said is in STUDY_SAID's words (the
// bill page's, endNote above), and one whose row states none of the three
// is said to have reported on its study.
// `tail` goes before the sentence's full stop: the day of a vote taken at
// another meeting (reportedLine).
function actSaid(a,who,tail){
  const t=tallyOf(a), end=(tail||"")+".";
  if(a.act==="report"){
    return `<p class="mact">${who} recommended ${recSaid(a.recommendation,a.code)}${
      a.amendment?` with amendment ${esc(a.amendment)}`:""}${t?`, ${t}`:""}${
      a.minority?`; a minority, ${recSaid(a.minority,a.minority_code)}`:""}${end}</p>`;
  }
  if(a.act==="study report"){
    if(a.said==="rec")return `<p class="mact mrec"><span class="mmark" aria-hidden="true">${
      ACTMARK.rec}</span>${who==="The committee"?"The committee's":esc(who)+"'s"} interim study report: ${
      STUDY_SAID.rec}${t?`, ${t}`:""}${end}</p>`;
    const said=a.said&&Object.prototype.hasOwnProperty.call(STUDY_SAID,a.said)?STUDY_SAID[a.said]
      :"reported on its study";
    // "Died", the word the Bills chip and the bill's own page give a bill
    // that ended so, where this said "Killed" (the cohesion audit of 30
    // October 2026, I-11). Without a recommendation, or a report whose row
    // states none, its mark is plain (the person, 30 October 2026: one
    // colour rule, as RECCOLOUR's).
    return `<p class="mact mkill${a.said==="without"||!a.said?" mwithout":""}"><span class="mmark" aria-hidden="true">${ACTMARK.kill}</span><b>Died:</b> ${
      who==="The committee"?"the committee's":esc(who)+"'s"} interim study report ${said}${
      t?`, ${t}`:""}${end}</p>`;
  }
  return `<p class="mact">${who} retained the bill: it stays in the committee into the next year${end}</p>`;
}
// Where the committee voted, when it did not at this meeting: the day, a
// link to that meeting where the docket dates the vote to one.
function votedElsewhere(v,date){
  if(!v||!v.date)return "";
  const day=v.meeting?`<a href="${esc(dayHref(v.meeting))}">${esc(dateWords(v.date))}</a>`
    :esc(dateWords(v.date));
  const before=v.date<date;
  if(!v.meeting&&v.act==="report")
    // Plainer (the cohesion audit's P-8), and still no claim that the
    // committee did not vote here: a Senate report's date is the sitting's
    // that took it up, and an older House row has no vote date at all.
    return `The docket dates the committee's report ${day}, not this meeting.`;
  const what=v.act==="study report"?"voted its interim study report"
    :v.act==="retained"?"retained the bill":"voted";
  return `No vote at this meeting; the committee ${before?"had ":""}${
    v.act==="retained"&&before?"retained the bill":what} on ${day}.`;
}
function signedSaid(g){
  if(!g||!g.total)return "";
  const n=x=>`<b>${Number(x||0).toLocaleString()}</b>`;
  const bits=[`${n(g.for)} signed in support`,`${n(g.against)} in opposition`]
    .concat(g.neutral?[`${n(g.neutral)} neutral`]:[]);
  return `<p class="msign">Online testimony: ${joinList(bits,"and")}.</p>`;
}
// The kinds of meeting a bill had, as the Calendar's chips.
const kindChips=ks=>(ks||[]).map(k=>{
  const w=MEET_KIND[String(k||"").trim().toLowerCase()]||[kindTitle(k),"k-other"];
  return chip(w[0],`calkind ${w[1]||"k-other"}`);}).join("");
// The line on a bill's card for one meeting: its kinds, its time, the moment
// in the recording where each was taken up (the same times and the same
// "approximate" as before; nothing about a timestamp changes), and what
// happened.
// A BILL'S MOMENTS IN ITS RECORDINGS, as the buttons that move a player there:
// one drawing for a meeting's card on the Meetings tab and for the Videos
// tab's list of bills (videoDetail), so the two give the same times and the
// same "approximate" from the same items, and nothing about a timestamp
// changes. `mine` is the bill's items; `pidOf(item)` names the player each
// one moves.
// EACH BUTTON AND ITS "APPROXIMATE" ARE ONE (.mjump, which does not wrap):
// drawn as two items of a row that wraps, the word could start the next line
// on its own, beside the next button. At 390px House Environment and
// Agriculture's HB 1157-FN of 3 February 2026 read "▸ Full Committee Work
// Session 02:43:55" over "approximate ▸ Executive Session 02:46:00", the
// inferred moment plain and the stated one approximate (the review of 29
// October 2026).
function jumpButtons(mine,pidOf){
  return mine.filter(i=>i.start!=null).map(i=>{
    const t=Math.max(0,Math.floor(i.start));
    // A weak marker's start is an inference, as the bill page says.
    const said=/^(stated|floor_stated|floor_precise)$/.test(i.state||"")&&!i.inferred;
    const pid=pidOf(i);
    const kind=mine.length>1?`${(MEET_KIND[String(i.kind||"").toLowerCase()]||[kindTitle(i.kind)])[0]} `:"";
    return `<span class="mjump"><button type="button" class="jump" data-seek="${esc(pid)}|${t}" aria-label="Play ${
      esc(kind||"this bill ")}from ${hms(t)}">${icon("play")}${esc(kind)}${hms(t)}</button>${
      said?"":`<i class="approx">approximate</i>`}</span>`;}).join("");
}
function meetingLine(s,o,items){
  const mine=items.filter(i=>String(i.bill)===String(o.bill));
  const at=mine.map(i=>i.time).filter(Boolean).sort()[0]||"";
  const jumps=jumpButtons(mine,i=>meetingPid(s,i.video_id||s.video_id));
  const who="The committee";
  let what="";
  if(o.outcome==="voted")what=(o.votes||[]).map(a=>actSaid(a,who)).join("");
  else if(o.outcome==="scheduled")what="";
  else{
    const work=(o.kinds||[]).find(k=>/work session/i.test(k));
    what=(o.outcome==="heard"?signedSaid(o.signins):"")
      +(o.outcome==="worked"&&work?`<p class="mact">Taken up in a ${esc(String(work).toLowerCase())}, with no vote.</p>`:"")
      +(votedElsewhere(o.voted,s.date)?`<p class="mwhen">${votedElsewhere(o.voted,s.date)}</p>`
        :(o.outcome==="heard"||o.outcome==="no vote"?`<p class="mwhen">No vote at this meeting.</p>`:""));
  }
  return `<div class="mline"><span class="mkinds">${kindChips(o.kinds)}</span>${
    at?`<span class="mtime">${esc(clock(at))}</span>`:""}${jumps?`<span class="mjumps">${jumps}</span>`:""}</div>${what}`;
}
// A player's id: this day and this recording, so each recording of the day
// is its own player and a time on a card moves only the one it is in.
const meetingPid=(s,vid)=>`m${String(s.date||"").replace(/-/g,"")}_${String(vid||"").replace(/[^\w-]/g,"")}`;
// One player per recording of the day (item 6), in the order they are first
// named. What the recording is called once it plays: this committee, this
// day.
function meetingPlayers(s,items){
  const c=(PAGE&&PAGE.data)||{};
  const who=[c.chamber==="S"?"Senate":c.chamber==="H"?"House":"",c.name||""].filter(Boolean).join(" ")||"Committee";
  const vids=[...new Set(items.map(i=>i.video_id||"").concat(s.video_id||"").filter(Boolean))];
  if(!vids.length){
    if(items.some(i=>i.state==="candidates"))return `<p class="note">This committee was recorded on
      this day, and which of its recordings each meeting belongs to has not been established
      &mdash; a committee can sit in divisions that stream separately. The bill pages link the
      recordings each could be.</p>`;
    return s.ahead?"":`<p class="note">No recording of this day is on file.</p>`;
  }
  return vids.map(vid=>{
    const pid=meetingPid(s,vid);
    const timed=items.filter(i=>(i.video_id||s.video_id)===vid&&i.start!=null);
    const from=timed.length?Math.max(0,Math.floor(Math.min(...timed.map(i=>i.start)))):0;
    const kinds=[...new Set(items.filter(i=>(i.video_id||s.video_id)===vid).map(i=>String(i.kind||"").toLowerCase()))];
    return `<div class="player" data-player="${esc(pid)}">
      <button type="button" class="pstub" data-title="${esc(recTitle(who,s.date))}"
        data-embed="${esc(vid)}|${from}|${esc(pid)}"><span>${icon("play")}</span><span>Play the recording${
          timed.length?` from ${hms(from)}`:""}</span></button>
      <div class="pbar"><span class="pwho"><b>${esc(who)}</b> &middot; ${esc(dateWords(s.date,"long"))}${
        kinds.length?` &middot; ${esc(kinds.join(", "))}`:""}</span>
        <a href="https://www.youtube.com/watch?v=${esc(vid)}&t=${from}s" target="_blank"
          rel="noopener">On YouTube</a>
        <span class="tolnote">${timed.length?"Choose a time on a card to jump the recording there."
          :"Exact moments not found."}</span></div></div>`;}).join("");
}
// What changed at the meeting, in one sentence (item 12): what the committee
// voted, then what the other bills had.
function meetingSentence(s){
  const oc=s.outcomes||[];
  if(!oc.length)return "";
  if(s.ahead)return `The committee is scheduled to take up ${nBills(oc.length)} at this meeting.`;
  const voted=oc.filter(o=>o.outcome==="voted");
  const recs=voted.filter(o=>(o.votes||[]).some(a=>a.act==="report")).length;
  const studies=voted.filter(o=>(o.votes||[]).some(a=>a.act==="study report"));
  const kept=voted.filter(o=>(o.votes||[]).some(a=>a.act==="retained")).length;
  const rec=studies.filter(o=>(o.votes||[]).some(a=>a.act==="study report"&&a.said==="rec")).length;
  const did=[];
  if(recs)did.push(`voted its recommendation on ${nBills(recs)}`);
  if(studies.length)did.push(`voted its interim study report on ${nBills(studies.length)}${
    rec&&rec<studies.length?` (${rec} recommended for future legislation and ${studies.length-rec} not)`
    :rec?", recommending each for future legislation":", recommending none for future legislation"}`);
  if(kept)did.push(`retained ${nBills(kept)}`);
  const n=k=>oc.filter(o=>o.outcome===k).length;
  const had=[];
  if(n("heard"))had.push(`${nBills(n("heard"))} had ${n("heard")===1?"its":"their"} public hearing`);
  if(n("worked"))had.push(`${nBills(n("worked"))} ${n("worked")===1?"was":"were"} taken up in a work session`);
  if(n("no vote"))had.push(`${nBills(n("no vote"))} ${n("no vote")===1?"was":"were"} in executive session with no vote dated to it`);
  const lead=did.length?`At this meeting the committee ${joinList(did,"and")}`:"At this meeting";
  return `${lead}${did.length&&had.length?"; ":" "}${joinList(had,"and")}${had.length&&!did.length?", with no vote":""}.`
    .replace(/ \.$/,".");
}
// How many of the day's bills the committee voted on, for the folded entry.
const votedCount=s=>(s.outcomes||[]).filter(o=>o.outcome==="voted").length;
// `out`: a day past the twenty shown (A COMMITTEE'S LONG LISTS).
function meetingHtml(s,open,out){
  const items=s.items||[];
  const oc=s.outcomes&&s.outcomes.length?s.outcomes
    :[...new Set(items.map(i=>i.bill))].map(b=>({bill:b,kinds:[...new Set(items.filter(i=>i.bill===b).map(i=>i.kind))],outcome:s.ahead?"scheduled":""}));
  const slots=items.map(i=>i.time||"").filter(Boolean).sort();
  const span=!slots.length?"":slots[0]===slots[slots.length-1]?clock(slots[0])
    :`${clock(slots[0])}\u2013${clock(slots[slots.length-1])}`;
  const rooms=[...new Set(items.map(i=>i.venue||"").filter(Boolean))];
  const kinds=[...new Set(oc.flatMap(o=>o.kinds||[]).map(k=>String(k).toLowerCase()))];
  const bars=[...new Set(kinds.map(k=>(MEET_KIND[k]||["","k-other"])[1]||"k-other"))];
  const v=votedCount(s);
  const cards=oc.map(o=>{
    const it=items.find(i=>String(i.bill)===String(o.bill))||{};
    const b=idxRow({id:o.bill,year:it.year,term:it.term||s.term,n:it.n,title:it.title});
    return cardHtml(b,false,meetingLine(s,o,items));}).join("");
  return `<details class="cmeet${s.ahead?" ahead":""}${out?" unshown":""}" id="${esc(dayId(s.date))}"${open?" open":""}>
    <summary><span class="calmix" aria-hidden="true">${bars.map(c=>`<i class="${c}"></i>`).join("")}</span>
      <span class="cmwhen"><b>${esc(dateWords(s.date,"long"))}</b>${span?` <span class="cmtime">${esc(span)}</span>`:""}</span>
      <span class="cmcount">${nBills(oc.length)}${s.ahead?" scheduled":v?` &middot; <b>${v} voted on</b>`:" &middot; no votes"}${
        rooms.length===1?` &middot; ${esc(roomWords(rooms[0]))}`:""}</span>
      <span class="cmkinds">${kindChips(kinds)}</span><span class="cmcaret" aria-hidden="true"></span></summary>
    <div class="cmbody"><p class="cmsaid">${meetingSentence(Object.assign({},s,{outcomes:oc}))}</p>
      <div class="cmlay"><div class="cmplay">${meetingPlayers(s,items)}</div>
      <div class="cards">${cards}</div></div></div></details>`;
}

function renderCommitteeSessions(c){
  const ss=cmteSessions(c),t=pageTerm();
  if(!(c.sessions||[]).length)return `<p class="src fill">No day of this committee is
    on record. Committees that no longer meet keep their page so the bills they
    handled still have somewhere to point.</p>`;
  if(!ss.length)return `<p class="src fill">No day of this committee is on record in
    the ${esc(termDash(t))} term.</p>`;
  // A DAY STILL TO COME IS NOT ONE IT MET (the survey of 7 October 2026):
  // "56 days this committee met" counted 14 October 2026, booked ahead. The
  // build marks such a day `ahead`; it is listed, told as scheduled, and
  // counted apart.
  const met=ss.filter(s=>!s.ahead).length, ahead=ss.length-met;
  const pg=PAGE||{};
  const old=pg.msort==="old";
  const order=ss.slice().sort((a,b)=>old?String(a.date).localeCompare(String(b.date))
    :String(b.date).localeCompare(String(a.date)));
  // Open: the day the address names, or else the newest the committee met.
  const want=decodeURIComponent(location.hash.slice(1)||"");
  const named=order.find(s=>dayId(s.date)===want);
  const newest=ss.filter(s=>!s.ahead).map(s=>s.date).sort().pop();
  const isOpen=s=>(pg.mopen&&CMP.own(pg.mopen,dayId(s.date)))?pg.mopen[dayId(s.date)]
    :(named?s===named:s.date===newest);
  // Twenty, or as far as the day the address names (A COMMITTEE'S LONG LISTS),
  // and kept that far: the next drawing, or a later address naming a day
  // nearer the top, does not take the days back off.
  const cap=Math.max(pagedCap("mshow"),named?order.indexOf(named)+1:0);
  if(PAGE)PAGE.mshow=cap;
  return `<div class="bfilt msort"><label>Order
      <select data-pf="msort" aria-controls="pmeets"><option value="new"${old?"":" selected"}>Newest first</option>
      <option value="old"${old?" selected":""}>Oldest first</option></select></label></div>
    <p class="src"><b>${met.toLocaleString()} meeting${met===1?"":"s"}</b>${t?` in ${esc(termDash(t))}`:""}${
      ahead?`, and ${ahead.toLocaleString()} still to come`:""}, ${old?"the oldest":"the newest"} first.
      One entry a day, each kind of meeting in its color; opened, each bill&rsquo;s card says
      what happened to it at that meeting.</p>
    <div class="cmeets" id="pmeets">${order.map((s,i)=>meetingHtml(s,isOpen(s),i>=cap)).join("")}</div>${
      pagedMore("mshow","pmeets",Math.min(cap,order.length),order.length)}`;
}

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

// ------------------------------------------------- a committee's Videos tab
// THE TERM'S RECORDINGS, newest first: build_committees' `recordings` (THE
// VIDEOS TAB'S LIST), each a bill row's or one the committee's own title
// names on its channel. Each one's bills, kinds and moments are the page's
// own items that name it, so nothing more is fetched.
const cmteRecordings=c=>(c.recordings||[]).filter(r=>r.term===pageTerm());
// "HB 1042", without the "-FN-LOCAL" the record carries, and on one line.
const vwBill=i=>String(i.n||i.bill||"").replace(/-.*$/,"").replace(/ /g,"\u00a0");
// The kinds of meeting, in the Meetings tab's words and colours (review, 2).
const vwKinds=items=>[...new Set(items.map(i=>String(i.kind||"").trim().toLowerCase()).filter(Boolean))];
// A meeting of this committee on the recording's day, as the Meetings tab
// has it: the address of that day there, which works in a new tab and as a
// copied link.
const vwDayHref=(c,date)=>`/committee/${encodeURIComponent(c.code)}/sessions#${dayId(date)}`;
function cmteVideoRows(c){
  const by=new Map(), met=new Map();
  (c.sessions||[]).forEach(s=>{
    if(!s.ahead)met.set(s.date,s);
    (s.items||[]).forEach(i=>{
      if(!i.video_id)return;
      if(!by.has(i.video_id))by.set(i.video_id,{s,items:[]});
      by.get(i.video_id).items.push(i);
    });
  });
  return cmteRecordings(c).map(r=>{
    const got=by.get(r.id), items=got?got.items:[], day=got?got.s:met.get(r.date)||null;
    // NO BILL TIED TO IT: where the committee's meeting that day is in no
    // other recording, that meeting's kind is the Calendar's for it, and is
    // shown (review, 3); where nothing is known, nothing is.
    const kinds=items.length?vwKinds(items)
      :day&&!(day.items||[]).some(i=>i.video_id)?vwKinds(day.items||[]):[];
    // A space between chips, so their names are not run together when read.
    const chips=kinds.map(k=>kindChips([k])).concat(r.label?[chip(r.label,"calkind k-other")]:[]).join(" ");
    const bills=[...new Set(items.map(vwBill))];
    // The count beside the date, the numbers after the kinds (vwRow), so a
    // line cut short loses numbers and never the count.
    const count=bills.length?nBills(bills.length):"";
    const line=bills.length?`${bills.slice(0,3).join(", ")}${
      bills.length>3?` and ${(bills.length-3).toLocaleString()} more`:""}`:"";
    return {id:r.id,date:r.date,began:r.began,seconds:r.seconds,kinds:chips,count,line,
            detail:()=>cmteVideoDetail(c,r,items,day,chips)};
  });
}
/* WHAT IS UNDER THE PLAYER, the recording's description (the owner, 29
   October 2026: "under the player, list the bills it covers, each with its
   moment button ... that jumps the player there", "the bill number then its
   moment"): its kinds as the Meetings tab's chips and its room; how many
   bills the docket ties to it, and how its times are used, in the Meetings
   tab's own words; then a line a bill in the order the recording reaches
   them -- the number, then its moments, the Meetings tab's own buttons
   (jumpButtons) with "approximate" where a moment is inferred, then its title
   in smaller type under them. It had been the number, then the title, then
   the moments on a line of their own under it: the times, which are what
   the list is for, were the last thing on each bill. A bill with no moment
   is its number and title. Where the docket ties none, that, once and
   plainly (review, 3); and the way to the meeting on the Meetings tab, where
   the committee had one that day. */
// WHAT THE COMMITTEE DID TO A BILL AT THE MEETING A RECORDING IS OF (the
// owner, 8 November 2026): the chip of what it voted that day and the vote as
// counted, beside the bill's moments. Only a vote the docket dates to this
// meeting (outcome "voted", committee_acts.at_meeting), never one of another
// day; a hearing, or a bill the committee did not vote that day, has none.
// The chip is a bill's Reports tab's (recChip), with the tally in it as the
// home page's Latest activity carries it.
function actChip(a){
  const t=tallyOf(a);
  if(a.act==="report")return a.recommendation?recChip(a.recommendation,t):"";
  if(a.act==="study report"){
    // As the home page's chip says it: the report's own words, the head where
    // its row states none of the three.
    const word=Object.prototype.hasOwnProperty.call(STUDY_SAID,a.said||"")&&STUDY_SAID[a.said]||WORDBOOK.study_report.head;
    return tallyWhole(chip(titleWords(word)+(t?` (${t})`:""),
      `cstat ${KIND[a.said==="rec"?"law":a.said==="not"?"done":""]||""}`.trim()));
  }
  return chip("Retained",`cstat ${KIND.active||""}`.trim());
}
function meetingOutcomeChips(day,bill){
  const o=((day&&day.outcomes)||[]).find(x=>String(x.bill)===String(bill));
  return o&&o.outcome==="voted"?(o.votes||[]).map(actChip).filter(Boolean).join(" "):"";
}
function cmteVideoDetail(c,r,items,day,chips){
  const pid=meetingPid({date:r.date},r.id);
  const rooms=[...new Set(items.map(i=>i.venue||"").filter(Boolean))];
  const facts=[chips?`<span class="vwchips">${chips}</span>`:"",rooms.length===1?esc(roomWords(rooms[0])):""].filter(Boolean);
  const out=[facts.length?`<p class="vwkinds">${facts.join(" ")}</p>`:""];
  if(items.length){
    // In the order the recording reaches them, by each bill's first moment;
    // a bill with none after those, in the docket's order.
    const at=b=>Math.min(...items.filter(i=>String(i.bill)===b&&i.start!=null).map(i=>+i.start));
    const order=[...new Set(items.map(i=>String(i.bill)))].map((b,k)=>[b,k,at(b)])
      .sort((x,y)=>(x[2]===y[2]?0:x[2]<y[2]?-1:1)||x[1]-y[1]).map(x=>x[0]);
    const timed=items.some(i=>i.start!=null);
    out.push(`<p class="vwlead">The docket ties ${nBills(order.length)} to this recording.${
      // A recording with no moment marked in it says what a bill's own player
      // says, "(exact moment not found)" (the owner's words of 25 October
      // 2026; the cohesion audit of 30 October, I-11).
      timed?" Choose a time to jump the recording there.":" Exact moments not found."}</p>`);
    // ON A PHONE, THE FIRST FEW AND A BUTTON FOR THE REST, as YouTube folds
    // a description: House Commerce's 26 bills were 2,500px between the
    // player and the playlist at 390px. Every one is in the page, on a wide
    // screen and on paper.
    out.push(`<ol class="vwbills" id="vwbills">${order.map((b,k)=>{
      const mine=items.filter(i=>String(i.bill)===b), it=mine[0];
      const href=it.year?`bill/${esc(it.year)}/${esc(b.toLowerCase())}`:esc(billHref(b));
      const jumps=jumpButtons(mine,()=>pid);
      const did=meetingOutcomeChips(day,b);
      // The number, its moments and its outcome chip on ONE line (.vwmom),
      // the title under them: the chip had wrapped onto a line of its own at
      // the right (the owner, 10 November 2026).
      const mom=(jumps?`<span class="mjumps">${jumps}</span>`:"")+(did?`<span class="vwout">${did}</span>`:"");
      return `<li${k>=VW_BILLS?' class="vwrest"':""}><a class="vwbn" href="${href}">${esc(it.n||b)}</a>${
        mom?`<span class="vwmom">${mom}</span>`:""}${
        it.title?`<span class="vwbt">${esc(it.title)}</span>`:""}</li>`;}).join("")}</ol>${
      order.length>VW_BILLS?`<button type="button" class="discl pgmore vwall" data-vwall="bills" aria-controls="vwbills">Show all ${
        order.length.toLocaleString()} bills</button>`:""}`);
  }else{
    // THE DAY'S BILLS WHOSE RECORDING IS NOT ESTABLISHED: the docket lists
    // them, and which of the day's recordings each is in is not known -- a
    // committee sitting in divisions that stream apart (House Finance), or a
    // day the clock could not tell its recordings apart. Said as the Meetings
    // tab says it of that day (meetingPlayers), where "The docket ties no
    // bill" read as if no bill was before it: House Public Works and
    // Highways' only recording of 5 May 2021, a four-bill public hearing (the
    // review of 29 October 2026; 103 recordings).
    const open=day?[...new Set((day.items||[]).filter(i=>!i.video_id&&i.state==="candidates").map(i=>String(i.bill)))]:[];
    out.push(open.length?`<p class="vwnone">${nBills(open.length)} ${open.length===1?"was":"were"} before the committee that day; which of its recordings ${
      open.length===1?"it is":"each is"} in has not been established.</p>`
      :`<p class="vwnone">The docket ties no bill to this recording.</p>`);
  }
  if(day)out.push(`<p class="src vwlinks"><a href="${esc(vwDayHref(c,day.date))}" data-vwday="${
    esc(day.date)}">${items.length?"What the committee did at this meeting":"This committee&rsquo;s meeting that day"}</a></p>`);
  return out.join("");
}
function renderCommitteeVideos(c){
  const t=pageTerm(), rows=cmteVideoRows(c);
  if(!rows.length)return `<p class="src fill">No recording of this committee from ${
    esc(termDash(t))} is on file.${t&&t<="2019-2020"?" "+STREAM_BEGIN_SAID:""}</p>`;
  const ch=c.chamber==="S"?"Senate":c.chamber==="H"?"House":"";
  const want=PAGE&&PAGE.vid, chosen=rows.some(r=>r.id===want)?want:rows[0].id;
  // What the page asks for is what is drawn: another term's recording, or
  // none, gives way to this term's newest (vwPaneKept reads it).
  if(PAGE)PAGE.vid=chosen;
  return videoView({who:[ch,c.name||""].filter(Boolean).join(" ")||"Committee",key:`${c.code}|${t}`,
    heading:`${rows.length.toLocaleString()} recording${rows.length===1?"":"s"} in ${termDash(t)}`,
    rows,chosen,
    href:id=>`/committee/${encodeURIComponent(c.code)}/videos#v-${id}`,
    pid:r=>meetingPid({date:r.date},r.id),
    onChoose:id=>{if(PAGE)PAGE.vid=id;},
    source:"The recordings are the General Court&rsquo;s own, from its House and Senate YouTube "
      +"channels; which bills each covers is from its docket."});
}
// THE VIDEOS TAB TURNED TO AGAIN shows the recording the reader had chosen
// there (PAGE.vid), and the address names it, as it did when it was chosen:
// it named the tab alone, so Share, a copied link or a reload opened on the
// newest and not on what was shown (the review of 29 October 2026). The
// term's newest, which the tab's own address opens on, is left unnamed; a
// recording of another term is not this term's tab's.
function vwBackTo(){
  if(!PAGE||PAGE.kind!=="committee"||PAGE_TAB!==COMMITTEE_TABS.videos||!PAGE.data||!PAGE.vid)return;
  const rows=cmteRecordings(PAGE.data);
  if(!rows.length||rows[0].id===PAGE.vid||!rows.some(r=>r.id===PAGE.vid))return;
  try{history.replaceState(history.state,"",location.pathname+location.search+"#v-"+PAGE.vid);}catch(_){}
  addressed();
  // Already chosen: not an arrival (showVideo) to be scrolled to.
  vwTried=vwLanded=PAGE.vid;
}
// A meeting's link under the player, pressed: the Meetings tab, opened at
// that day (showDay), with its address in the bar.
// And the head's "Videos tab", pressed: that tab, on the recording it names
// (showVideo), as the address would open it.
document.addEventListener("click",e=>{
  const a=e.target&&e.target.closest&&e.target.closest("a[data-vwday],a[data-vwgo]");
  if(!a||!PAGE||e.defaultPrevented||e.button||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  e.preventDefault();
  try{history.replaceState(history.state,"",a.getAttribute("href"));}catch(_){}
  addressed();
  if(a.dataset.vwgo!==undefined){vwTried=vwLanded="";showVideo();return;}
  PAGE_TAB=COMMITTEE_TABS.sessions;
  dayLanded="";
  renderPage();
});

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
  // AND THE CHAMBER, WHICH THE BILL DOES NOT SETTLE. A bill that crosses is
  // on both chambers' committees' lists -- SB 519 is Senate Judiciary's and
  // House Judiciary's -- so name and bill matched House Judiciary's sitting
  // on it of 30 September 2026 to Senate Judiciary's page too. Replayed over
  // 2025-2026 that put 719 sittings on the other chamber's page, on 384
  // days. home.json's row says whose sitting it is; a row written before it
  // did is left to name and bill, as it was.
  const ch=String(c.chamber||"").trim().toUpperCase();
  return UPCOMING.filter(u=>
    String(u.committee||"").trim().toLowerCase()===name
    && (!ch||!u.body||String(u.body).trim().toUpperCase()===ch)
    && mine.has(String(u.term||"")+"\u0000"+String(u.bill||"").toUpperCase()));
}

// The kinds the General Court's schedule actually uses, in the words a reader
// needs: a public hearing is the one they may speak at, an executive session
// is the one where the committee votes.
// A SEAT AS IT IS WRITTEN ON A PLATE. The roster stores 4017, which is
// division 4 seat 17 and reads as four thousand and seventeen; the plate a
// representative drives around with says 4-017, and that is the form somebody
// looking one up has in their head. The same function is in seating.py and in
// build_pages' chart script; preflight holds the three together.
function plate(s){
  s=String(s==null?"":s);
  return s.length>3 ? s.slice(0,s.length-3)+"-"+s.slice(-3) : s;
}

// THE KINDS OF MEETING: the schedule's word, lower case, to [what a reader
// sees, the class that colours it]. Words, written once (the component plan's
// C3, 9 October 2026): src/pages/words/meeting_kinds.json, which components.js
// carries as WORDBOOK and build_pages draws the home page's calendar with. It
// was a table here and another there, held alike by a check that read both.
const MEET_KIND=WORDBOOK.meeting_kinds.kinds;
// Title case, as build_pages.kind_title: the chips are names, like the
// Calendar's boxes, and a small word after the first stays small.
const KIND_SMALL=new Set(WORDBOOK.meeting_kinds.small);
const kindTitle=k=>String(k||"").split(/\s+/).filter(Boolean)
  .map((w,i)=>(i&&KIND_SMALL.has(w.toLowerCase()))||!/^[a-z]/i.test(w)?w:w.charAt(0).toUpperCase()+w.slice(1))
  .join(" ")||"Meeting";

// THE MARKUP HERE MUST MATCH build_pages.py's calendar_html(). Both emit the
// same component against one set of rules in app.css's SHARED region, and
// preflight fails if the class names drift apart -- which is the only thing
// keeping two renderers of one component honest.
function calendarBlock(rows,heading){
  if(!rows.length)return "";
  const meets=new Map();
  rows.forEach(u=>{
    // NOT THE TIME -- see build_pages.meeting_key, which this has to agree
    // with. The docket gives every BILL its own slot inside a meeting, so a
    // key holding the time made one committee morning into one card per
    // bill: the busiest week of 2026 came out as 356 meetings where it
    // holds 68. The card states the span instead.
    // ONE ENTRY PER COMMITTEE PER DAY -- the same rule as
    // build_pages.meeting_key, which this has to agree with. A
    // committee that holds a hearing and then an executive session
    // has had one day, not two, and the room belongs to the item
    // rather than to the entry: Ways and Means on 30 September is a
    // subcommittee in GP 228 and the full committee in GP 234.
    const k=[u.date||"",u.committee||""].join("\u0000");
    if(!meets.has(k))meets.set(k,[]);
    meets.get(k).push(u);
  });
  // Ordered by when each meeting STARTS, which has left the key.
  const startOf=k=>{
    const s=meets.get(k).map(b=>b.time||"").filter(Boolean).sort();
    return k.split("\u0000")[0]+"\u0000"+(s[0]||"")+"\u0000"+k;
  };
  const keys=[...meets.keys()].sort((a,b)=>startOf(a).localeCompare(startOf(b)));
  const days=new Map();
  keys.forEach(k=>{
    const d=k.split("\u0000")[0];
    if(!days.has(d))days.set(d,[]);
    days.get(d).push(k);
  });
  // The reader's day, on purpose: "today" and "tomorrow" are theirs, where
  // a testimony deadline is Concord's (TWO CLOCKS, ON PURPOSE, at nhDay).
  const today=new Date(); today.setHours(0,0,0,0);
  const when=d=>{
    const dd=new Date(d+"T00:00:00");
    if(isNaN(dd))return [d,""];
    const off=Math.round((dd-today)/86400000);
    const rel=off===0?"today":off===1?"tomorrow":(off>0&&off<14)?`in ${off} days`:"";
    return [dateWords(d,"wkd"),rel];
  };
  const out=[`<section class="cal"><h2>${esc(heading)}</h2>`];
  days.forEach((ks,date)=>{
    const [label,rel]=when(date);
    out.push(`<div class="calday"><h3 class="caldate"><span>${esc(label)}</span>`
      +(rel?`<span class="cdrel">${esc(rel)}</span>`:"")+`</h3>`);
    ks.forEach(k=>{
      const [,cmte]=k.split("\u0000");
      const bills=meets.get(k);
      // First bill to last, which is how the General Court prints a meeting,
      // in the twelve-hour clock the rest of the site's calendars use.
      const slots=bills.map(b=>b.time||"").filter(Boolean).sort();
      const time=!slots.length?""
        :(slots[0]===slots[slots.length-1]?clock(slots[0])
          :clock(slots[0])+"\u2013"+clock(slots[slots.length-1]));
      // The day's items in order, each keeping the time, kind and room
      // it was set for.
      const byslot=new Map();
      bills.slice().sort((a,b)=>((a.time||"~")+(a.what||"")+(a.venue||""))
        .localeCompare((b.time||"~")+(b.what||"")+(b.venue||""))
        ||billCmp(a.bill,b.bill))
        .forEach(b=>{const sk=[b.time||"",b.what||"",b.venue||""].join("\u0000");
          if(!byslot.has(sk))byslot.set(sk,[]);byslot.get(sk).push(b);});
      const kinds=[],rooms=[];
      byslot.forEach((_v,sk)=>{const q=sk.split("\u0000");
        if(kinds.indexOf(q[1])<0)kinds.push(q[1]);
        if(q[2]&&rooms.indexOf(q[2])<0)rooms.push(q[2]);});
      const venue=rooms.length===1?rooms[0]:"";
      const bars=[];
      kinds.forEach(k2=>{const c=(MEET_KIND[String(k2||"").trim().toLowerCase()]||["",""])[1]||"k-other";
        if(bars.indexOf(c)<0)bars.push(c);});
      const kindWord=k2=>MEET_KIND[String(k2||"").trim().toLowerCase()]
        ||[kindTitle(k2),""];
      // EACH BILL ONCE, as build_pages.cal_days counts them. A bill heard
      // and then voted on the same day is two items and one bill, and
      // counting items put "13 bills" over a committee's eight.
      const nb=new Set(bills.map(b=>String(b.bill||"").trim().toUpperCase())
        .filter(Boolean)).size;
      out.push(`<details class="calmeet"><summary>`
        +`<span class="calmix" aria-hidden="true">`
        +bars.map(c=>`<i class="${c}"></i>`).join("")+`</span>`
        +(time?`<span class="caltime">${esc(time)}</span>`:"")
        +`<span class="calcmte">${esc(cmte)}</span>`
        +kinds.map(k2=>{const [w,c]=kindWord(k2);
          return chip(w,`calkind ${c}`);}).join("")
        +`<span class="calcount">${nb} bill${nb===1?"":"s"}</span>`
        +(venue?`<span class="calwhere">${esc(roomWords(venue))}</span>`:"")
        +`<span class="caret"></span></summary>`
        +`<div class="calbody">`);
      const oneSlot=byslot.size===1;
      byslot.forEach((items,sk)=>{
        const q=sk.split("\u0000");
        if(!oneSlot){
          const [w,c]=kindWord(q[1]);
          out.push(`<p class="calslot">`
            +(q[0]?`<span class="caltime">${esc(clock(q[0]))}</span>`:"")
            +chip(w,`calkind ${c}`)
            +(q[2]&&!venue?`<span class="calwhere">${esc(roomWords(q[2]))}</span>`:"")
            +`</p>`);
        }
        out.push(`<ul class="calbills">`);
        items.forEach(b=>{
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
        out.push(`</ul>`);
      });
      out.push(`</div></details>`);
    });
    out.push(`</div>`);
  });
  // The sentences before the executive session's are build_pages.hearing_note,
  // word for word, and preflight holds the copies to it: the person's own (7
  // October 2026) for a House committee, and since 23 October 2026 the
  // Senate's for a Senate committee, whose online sign-in takes no testimony.
  const senate=rows.every(u=>String(u.body||"").trim().toUpperCase()==="S");
  out.push(`<p class="note">${senate?`Anyone may attend a public hearing and ask to
    speak. You can also sign in online to register a position. The page that
    confirms your sign-in says how to send written testimony.`:`Anyone may attend
    a public hearing and ask to speak. You can also sign in online to register a
    position and submit written testimony.`} An executive session is where the
    committee votes on what to recommend; it is open to watch but not to
    testify.</p></section>`);
  return out.join("");
}

// A bill's own page, by the year its number belongs to. yearOf is what the
// rest of this file uses, so a calendar link and a card link agree.
function billHref(id){
  const y=(typeof yearOf==="function"&&yearOf(id))||null;
  return y?`bill/${y}/${String(id).toLowerCase()}`
          :`${BASE}bills#${encodeURIComponent(id)}`;
}

function billTitle(id){
  if(!Array.isArray(IDX))return "";
  const b=IDX.find(x=>x.id===id&&(!term||x.term===term))||IDX.find(x=>x.id===id);
  return (b&&b.title)||"";
}

function renderCommitteeUpcoming(c){
  if(UPCOMING===null)return "";               // not asked yet: say nothing
  const rows=cmteUpcoming(c);
  // MOSTLY (the survey of 7 October 2026): both chambers sat until veto day,
  // 19 August, in 2026, and into the autumn in most years.
  if(!rows.length)
    return `<section class="cal"><h2>Upcoming meeting</h2>
      <p class="note">Nothing is scheduled for this committee in the next two
      weeks. The General Court sits mostly from January to June.</p></section>`;
  return calendarBlock(rows,"Upcoming meeting");
}

// ================================================== POLISH 2: A COMMITTEE
//
// THE COMMITTEE'S HEAD (the record head, C6; the person's question 11,
// approved 9 October 2026: Members and What It Does above the tabs). One
// line says whose committee it is and who chairs it, the chair as the
// person in a sentence (D14); the facts are where it meets and whom to ask;
// and, once what is scheduled has been read, whether it meets in the next
// two weeks and when it last met. Members and What It Does follow as W4
// sections, then the term, the tabs and the record.
function renderCommitteeHead(c){
  const ch=c.chamber==="S"?"Senate":"House";
  const members=c.members||[];
  const chairO=(c.officers||[]).find(o=>/^chair$/i.test(String(o.role||"").trim()));
  const chairM=chairO&&chairO.slug&&members.find(x=>x.slug===chairO.slug);
  const chair=chairO?personLink(chairM||{label:chairO.label||chairO.name,slug:chairO.slug||""}):"";
  const facts=[["Meets In",esc(roomWords(c.room))],["Phone",c.phone?`<a href="tel:${
      esc(String(c.phone).replace(/[^\d+]/g,""))}">${esc(c.phone)}</a>`:""],
    ["Committee Aide",esc(c.aide||"")],["Researcher",esc(c.researcher||"")]];
  const met=(c.sessions||[]).filter(s=>!s.ahead).map(s=>s.date).sort().pop();
  // ITS CHANNEL CAN BE AHEAD OF ITS DOCKET. The Senate's docket lists its
  // committees' hearings and not their executive sessions, so Senate
  // Finance's last meeting on the record is 7 April 2026 and its newest
  // recording 12 May (the Videos tab's list, build_committees). Both are
  // said, so the head and the tab below it do not disagree.
  const rec=(c.recordings||[]).reduce((a,r)=>!a||r.date>a.date?r:a,null);
  // Both dates in the one style, the site's: "on Apr 7, 2026 ... from May
  // 12, 2026", where the sentence mixed "Tuesday, April 7, 2026" with "May
  // 12, 2026" (the review of 29 October 2026; the manager's choice of style,
  // pending the owner's). A last meeting said alone keeps its long form.
  const ahead=rec&&met&&rec.date>met?`; its newest recording, on the <a href="${
    esc(`/committee/${encodeURIComponent(c.code)}/videos#v-${rec.id}`)}" data-vwgo="${esc(rec.id)}">Videos tab</a>, is from ${
    esc(dateWords(rec.date))}`:"";
  const next=UPCOMING===null?"":cmteUpcoming(c).length?""
    :`Nothing is scheduled in the next two weeks.${met?` Its last meeting${ahead?" on the record":""} was on <a href="${
      esc(dayHref(met))}">${esc(ahead?dateWords(met):dateWords(met,"long"))}</a>${ahead}.`:""}`;
  // "The House Special Committee on Housing", not "The House Committee on
  // Special Committee on Housing" (components.js's cmteTitle, 16 October 2026).
  const line=`The ${esc(cmteTitle(c.name||"",ch))}${chair?`, chaired by ${chair}`:""}.`;
  // A FORMER COMMITTEE, SAID PLAINLY (the person, 16 October 2026). The note
  // this replaced explained what the records cannot say -- renamed, divided,
  // merged or ended -- and readers found it confusing. "No longer meets" is
  // the search's own line for the same committees.
  const ran=c.archived&&c.archived.years;
  const notes=[c.archived?`A former committee. It no longer meets${ran
      ?`; its bills and meetings here run from ${esc(ran)}`:""}.`:"",
    (c.names||[]).length?`Named ${c.names.map(n=>`<b>${esc(n.name)}</b> (${esc(n.years||"")})`)
      .join(" and ")} on this record&rsquo;s earlier bills and meetings, which the General
      Court&rsquo;s own records file under this committee.`:"",next].filter(Boolean);
  return recordHead({trail:[["Committees","committees"],[`${ch} Committee`,""]],
      title:esc(c.name||""),line,facts,rail:"",actions:"",kind:"committee cmtehead"})
    +notes.map(n=>`<p class="src fill rnote">${n}</p>`).join("")+sameCode(c);
}
function committeeSections(c){
  const officers=(c.officers||[]).filter(o=>o.name);
  const members=c.members||[];
  const rule=c.purpose||null;
  // ONE CHIP FOR A PERSON: the officers are in the roster with their role in
  // the chip's corner; an officer the roster lacks is a chip with no party.
  const extra=officers.filter(o=>!(o.slug&&members.some(x=>x.slug===o.slug)))
    .map(o=>mchip({name:o.name,label:o.label||o.name,slug:o.slug||"",role:o.role}));
  const S=[];
  if(members.length||extra.length)S.push(section(`Members`,`<p class="mlist">${
    members.map(mchip).concat(extra).join(" ")}</p>${emailCommittee(c)}`,"members")
    .replace('<h2 class="w4h">Members</h2>',`<h2 class="w4h">Members <span class="w4n">${members.length}</span></h2>`));
  if(rule)S.push(section("What It Does",`<p>${esc(rule.text||"")}</p>
      <p class="src">${esc(rule.rule||"")}, as the General Court publishes it.${
        c.url?` Source: <a href="${esc(c.url)}" target="_blank" rel="noopener">NH General Court</a>`:""}</p>`,
      "what"));
  else if(c.url)S.push(section("Source",`<p class="src"><a href="${esc(c.url)}" target="_blank"
      rel="noopener">This committee on gencourt</a></p>`,"source"));
  return S.length?`<div class="w4s">${S.join("")}</div>`:"";
}

// Everything above the tab's pane: the head, the sections, what is coming,
// the term and the tabs. renderPage draws this alone while a recording plays
// in the Videos pane (vwPaneKept).
function committeeTop(c){
  // Counted for the term the page is showing, not across every term. "Bills
  // (107)" over a list of 32 is the tab disagreeing with itself.
  const tabs=[["Bills",cmteBills(c).length],["Meetings",cmteSessions(c).length]];
  // VIDEOS, WHERE THE COMMITTEE HAS A RECORDING IN ANY TERM, counted as the
  // other two are, for the term shown: a term with none keeps the tab, with
  // no count, and its pane says so. A committee with none has no such tab,
  // and an address asking for it opens on Bills.
  if((c.recordings||[]).length)tabs.push(["Videos",cmteRecordings(c).length]);
  else if(PAGE_TAB===COMMITTEE_TABS.videos){PAGE_TAB=0;tabAddress("");}
  // Who they are, then what is coming, then the record. The calendar sits
  // above the term control because it is not about a term: it is about this
  // week, and a reader who came to find out whether they can still turn up
  // and speak should not have to scroll past nineteen years of bills. Where
  // nothing is coming the head says so, and when it last met.
  const up=UPCOMING!==null&&cmteUpcoming(c).length?renderCommitteeUpcoming(c):"";
  return renderCommitteeHead(c) + committeeSections(c) + up + termControl() + tabStrip(tabs);
}
function renderCommittee(c){
  const top=committeeTop(c);
  const body=[()=>renderCommitteeBills(c),()=>renderCommitteeSessions(c),
              ()=>renderCommitteeVideos(c)][PAGE_TAB]||(()=>"");
  return top + pagePane(body());
}
/* THE PANE IS LEFT AS IT IS WHILE A RECORDING PLAYS IN IT. The page is drawn
   again as the term's index, home.json and the officers arrive after the
   record, and a frame that is made again, or moved, starts over: so where the
   Videos pane of the term shown holds a frame, only what is above the pane is
   drawn again. Changing the term or the tab ends the playing, as it ends any
   other; and so does an address that names another recording (the head's
   "Videos tab", #v-<id>), which is a choice of it: the pane had been kept,
   playing the old one under an address naming the new. */
function vwPaneKept(el){
  if(!PAGE||PAGE.kind!=="committee"||PAGE_TAB!==COMMITTEE_TABS.videos||!PAGE.data)return null;
  const pane=el.querySelector("#ppane"), box=pane&&pane.querySelector(".vw");
  return box&&box.querySelector("iframe")
    &&box.dataset.vwkey===`${PAGE.data.code}|${pageTerm()}`
    &&!!VVIEW&&VVIEW.chosen===PAGE.vid&&pane.parentNode===el?pane:null;
}

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
//   - A SESSION DAY (day=, the review of 14 November 2026) is the roll calls
//     its page counts, which the roll-call file may date a day or more later:
//     a row's `s` (build_votes.py) where it does. From and To are the dates
//     the file gives, as each row shows them.
//   - THE TERM FOLLOWS what is chosen where the reader has not picked one: the
//     term of the dates or the day, or of the member's votes, or every term
//     where they span several (votesTermDefault); the address and the
//     controls ask the same function, so a link opens on what was on screen.
//
// A row is the member tab's own row (voteRow) -- the date, the bill and the
// question, the result -- and "How everyone voted" opens the bill page's ring
// and party rows in place (voteRing's body), from the bill's record or, for a
// vote on no bill, the term's nobill/ file.
const VT={idx:null,err:"",rows:{},rowsAsked:{},bal:{},balAsked:{},col:{},by:{},words:"",
  people:null,peopleAsked:false,st:null,open:{},kind:null,gs:null,note:""};
const VOTES_KINDS=["Committee report","Amendment","Conference report","Veto override",
  "Passage","Motion on a bill","Procedural","Other"];
const VOTES_SORTS=["best","new","close"];
const VOTES_SHOW=100;
const VOTES_BALLOT={Y:"Yea",N:"Nay",E:"Not Voting/Excused",X:"Not Voting/Not Excused",
  P:"Presiding",R:"No vote recorded"};
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
  return {q:"",term:terms[0]||"",tauto:true,body:"",from:"",to:"",day:"",result:"",margin:"",
          kind:"",member:"",sort:"",show:0};
}
// The address read into the page's state. A value this does not know is no
// filter, so an old or a mistyped address opens the page as it opens bare. A
// term the address does not name follows what it does (tauto).
function votesRead(search,terms){
  const u=new URLSearchParams(search||""),st=votesDefault(terms);
  const pick=(k,ok)=>{const v=u.get(k)||"";return ok(v)?v:"";};
  st.q=(u.get("q")||"").trim();
  st.body=pick("body",v=>v==="H"||v==="S");
  st.from=pick("from",votesDay);
  st.to=pick("to",votesDay);
  st.day=pick("day",votesDay);
  st.result=pick("result",v=>v==="passed"||v==="failed");
  st.margin=pick("margin",v=>v==="close"||v==="tied");
  st.kind=pick("kind",v=>VOTES_KINDS.includes(v));
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
  const u=new URLSearchParams(),set=(k,v)=>{if(v)u.set(k,v);};
  set("q",String(st.q||"").trim());
  if(st.term!==votesTermDefault(st,terms))set("term",st.term);
  set("body",st.body);set("from",st.from);set("to",st.to);set("day",st.day);set("result",st.result);
  set("margin",st.margin);set("kind",st.kind);set("member",st.member);
  if(st.sort&&st.sort!==votesSortDefault(st))set("sort",st.sort);
  return u.toString();
}
// How many controls beyond the search box are away from where the page opens:
// the number the phone's Filters button carries.
function votesActive(st,terms){
  return [st.term!==votesTermDefault(st,terms),st.body,st.from,st.to,st.day,st.result,st.margin,
          st.kind,st.member].filter(Boolean).length;
}
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
// chosen member's, or null.
function votesPass(r,st,ids){
  if(st.body&&r.c!==st.body)return false;
  if(st.from&&r.d<st.from)return false;
  if(st.to&&r.d>st.to)return false;
  if(st.day&&votesSitting(r)!==st.day)return false;
  if(st.result&&(st.result==="passed")!==!!r.p)return false;
  if(st.margin==="close"&&!r.cl)return false;
  if(st.margin==="tied"&&!(r.y>0&&r.y===r.n))return false;
  if(st.kind&&r.k!==st.kind)return false;
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
// The rows of a state, in the order it asks for. `gs` is the search's groups,
// `ids` the bill numbers it names, `mem` the member's ids.
function votesRowsOf(all,st,gs,ids,mem){
  let rows=all.filter(r=>votesPass(r,st,mem));
  if(st.q){
    rows=ids?rows.filter(r=>!!r.b&&ids.includes(String(r.b).toUpperCase()))
      :rows.filter(r=>matchesGroups(votesSubject(r),gs));
  }
  const how=st.sort||votesSortDefault(st);
  if(how==="best"&&st.q&&gs)return votesBest(rows,gs);
  if(how==="close")return rows.sort((a,b)=>(a.f==null)-(b.f==null)||(a.f||0)-(b.f||0)||votesNewest(a,b));
  return rows.sort(votesNewest);
}
// What "close" says, in the data's own terms: one line, under the filters
// only while the Margin filter asks for close votes (the review of 14
// November 2026: it stood above every list).
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
// phone's Filters keep their state (votesControls); a member the address
// names and the lists do not is no filter, as a term or a kind it does not
// know is none, where the page hung on "Reading the votes"; and a term the
// reader has not picked moves to the member's votes (votesTermDefault).
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

// ---- the controls, drawn once and kept (the list below them is what changes)
function votesOptions(list,cur){
  return list.map(([v,w])=>`<option value="${esc(v)}"${v===cur?" selected":""}>${esc(w)}</option>`).join("");
}
// DRAWN AGAIN WITHOUT LOSING WHAT THE READER HAS IN HAND (the review of 14
// November 2026). The members' lists arrive about a second after the page,
// and drawing the controls again for them emptied the Member box of what had
// been typed, sent the focus to the page's body, and on a phone set the
// Filters button to closed over a panel still open. What is typed in either
// box, the focus and the caret, and the panel's state (#vpage's vfopen) are
// carried through.
function votesControls(){
  const el=document.getElementById("vctl"),st=VT.st;
  if(!el||!VT.idx||!st)return;
  const terms=VT.idx.terms;
  const W=WORDBOOK.votes||{};
  const act=document.activeElement,here=act&&act.id&&el.contains(act)?act.id:"";
  const caret=here&&typeof act.selectionStart==="number"?[act.selectionStart,act.selectionEnd]:null;
  const was=id=>{const n=document.getElementById(id);return n?n.value:"";};
  const typed=st.member?"":was("vmem"),qbox=here==="vq"?was("vq"):st.q;
  const page=document.getElementById("vpage"),open=!!(page&&page.classList.contains("vfopen"));
  const person=st.member?votesPerson(st.member):null;
  const memberBox=st.member
    ?`<span class="vmemchip">${person?pchip(person.m):esc(st.member)}
       <button type="button" class="link" data-vmemclear="1">Clear</button></span>`
    :`<input type="search" id="vmem" autocomplete="off" placeholder="A name" value="${esc(typed)}"
        aria-label="Filter to one member's votes" aria-controls="vsug">
      <ul class="vsug" id="vsug" hidden></ul>`;
  // A session day, where the address names one: what it is and a way out.
  const dayBox=st.day?`<div class="vmember vday"><span class="vlab">Session day</span><span class="vmemchip">${
      esc(votesDayWords(st))}
      <button type="button" class="link" data-vdayclear="1">Clear</button></span></div>`:"";
  el.innerHTML=`<form class="vsearch" role="search" id="vform">
      <label class="sr" for="vq">Search the votes by bill number or words</label>
      <input type="search" id="vq" spellcheck="false" autocomplete="off" value="${esc(qbox)}"
        placeholder="Bill number or words">
      <button type="button" class="vtoggle" id="vftoggle" aria-expanded="${open?"true":"false"}" aria-controls="vfilters">Filters<span
        class="badge" id="vbadge"></span><span class="chev" aria-hidden="true">&#9656;</span></button></form>
    <div class="bfilt vfilters" id="vfilters" role="group" aria-label="Filter the votes">
      <label>Term<select id="vf-term" data-vf="term">${votesOptions([["all","All terms"]].concat(
        terms.map(t=>[t,termDash(t)])),st.term)}</select></label>
      <label>Chamber<select id="vf-body" data-vf="body">${votesOptions([["","Both"],["H","House"],["S","Senate"]],st.body)}</select></label>
      <label>From<input type="date" id="vf-from" data-vf="from" value="${esc(st.from)}"></label>
      <label>To<input type="date" id="vf-to" data-vf="to" value="${esc(st.to)}"></label>
      ${dayBox}
      <label>Result<select id="vf-result" data-vf="result">${votesOptions([["","Any"],["passed",W.passed||"Motion Passed"],
        ["failed",W.failed||"Motion Failed"]],st.result)}</select></label>
      <label>Margin<select id="vf-margin" data-vf="margin">${votesOptions([["","Any"],["close","Close"],
        ["tied","Tied"]],st.margin)}</select></label>
      <label>Kind of question<select id="vf-kind" data-vf="kind">${votesOptions([["","Any"]].concat(
        VOTES_KINDS.map(k=>[k,k])),st.kind)}</select></label>
      <label class="vmember">Member${memberBox}</label>
    </div>
    <p class="src vnote" id="vclose"${st.margin==="close"?"":" hidden"}>${esc(votesCloseWords())}</p>`;
  if(here){
    const n=document.getElementById(here);
    if(n){
      try{n.focus();}catch(_){}
      if(caret&&n.setSelectionRange)try{n.setSelectionRange(caret[0],caret[1]);}catch(_){}
    }
  }
  if(typed&&VT.people)votesSuggest(typed);
  votesBadge();
}
// "The House, February 24, 2021": a session day as the page's filter names it.
function votesDayWords(st){
  const ch=st.body==="H"?"The House":st.body==="S"?"The Senate":"The House and the Senate";
  return `${ch}, ${dateWords(st.day,"full")}`;
}
function votesBadge(){
  const b=document.getElementById("vbadge");
  if(!b||!VT.idx)return;
  const n=votesActive(VT.st,VT.idx.terms);
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
  const ch={H:"the House’s session day",S:"the Senate’s session day"}[st.body]||"the session days";
  const where=st.day?`from ${ch} of ${dateWords(st.day,"full")}`
    :`in ${st.term==="all"?"every term":termDash(st.term)}`;
  const who=person?String(person.m.display_plain||person.m.name||st.member):"";
  const rcs=k=>`${k.toLocaleString()} roll call${k===1?"":"s"}`;
  if(who)return n?`${who} voted yea or nay on ${voted.toLocaleString()} of ${rcs(n)} ${where}`
    :`0 roll calls of ${who} ${where}`;
  return `${n.toLocaleString()} ${n===1?"vote":"votes"} ${where}`;
}
// ---- the page's list: everything asked for, then the rows
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
  let rows=reading&&(!balReady||need_.length)?[]:votesRowsOf(pool,st,gs,num,ids);
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
// 2003 or a former member showed "0 votes in 2025–2026").
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
// The member chosen or cleared, from a click: the term follows them.
function votesMember(slug){
  const st=VT.st;
  st.member=slug;st.show=0;st.tauto=true;
  votesRetime(st,VT.idx.terms);
  votesControls();votesAfter();
}
// The Term select shows the term the dates moved it to.
function votesTermShown(){
  const sel=document.getElementById("vf-term");
  if(sel&&VT.st)sel.value=VT.st.term;
}
function votesAfter(){
  const c=document.getElementById("vclose");
  if(c)c.hidden=VT.st.margin!=="close";
  votesAddress();votesBadge();votesDraw();
}
function votesSuggest(text){
  const ul=document.getElementById("vsug");
  if(!ul)return;
  const t=String(text||"").toLowerCase().replace(/[^a-z0-9 ]/g," ").replace(/\s+/g," ").trim();
  if(!t||!VT.people){ul.hidden=true;ul.innerHTML="";return;}
  const words=t.split(" ");
  const hit=VT.people.filter(p=>words.every(w=>p.hay.includes(w)))
    .sort((a,b)=>(a.former-b.former)||a.hay.localeCompare(b.hay)).slice(0,8);
  ul.innerHTML=hit.map(p=>`<li><button type="button" data-vpick="${esc(p.slug)}">${esc(p.m.display_full||p.m.name)}${
    p.former?" (former)":""}</button></li>`).join("");
  ul.hidden=!hit.length;
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
  const k=e.target.dataset&&e.target.dataset.vf;
  if(k)votesChange(k,e.target.value);
});
document.addEventListener("submit",e=>{
  if(window.GR_VOTES&&e.target&&e.target.id==="vform"){e.preventDefault();}
});
document.addEventListener("click",e=>{
  if(!window.GR_VOTES||!VT.st||!e.target.closest)return;
  const c=s=>e.target.closest(s);
  if(c("[data-vmore]")){VT.st.show=(VT.st.show||0)+VOTES_SHOW;votesDraw();return;}
  if(c("[data-vclear]")){
    const m=document.getElementById("vmem");
    if(m)m.value="";
    VT.st=votesDefault(VT.idx.terms);votesControls();votesAfter();return;}
  const vq=c("[data-vq]");
  if(vq){VT.st.q=vq.getAttribute("data-vq");VT.st.show=0;votesControls();votesAfter();return;}
  const pick=c("[data-vpick]");
  if(pick){votesMember(pick.getAttribute("data-vpick"));return;}
  if(c("[data-vmemclear]")){votesMember("");return;}
  if(c("[data-vdayclear]")){
    VT.st.day="";VT.st.show=0;VT.st.tauto=true;votesRetime(VT.st,VT.idx.terms);
    votesControls();votesAfter();return;}
  if(c("#vftoggle")){
    const p=document.getElementById("vpage"),open=p.classList.toggle("vfopen");
    c("#vftoggle").setAttribute("aria-expanded",open?"true":"false");
  }
});
document.addEventListener("keydown",e=>{
  if(window.GR_VOTES&&e.key==="Escape"&&e.target.closest&&e.target.closest("#vfilters,#vftoggle")){
    const p=document.getElementById("vpage"),b=document.getElementById("vftoggle");
    if(p&&b&&p.classList.contains("vfopen")){p.classList.remove("vfopen");b.setAttribute("aria-expanded","false");b.focus();}
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
  VT.st=votesRead(location.search,VT.idx.terms);votesControls();votesDraw();
});

function votesInit(){
  const root=document.getElementById("vpage"),box=document.getElementById("vlist");
  if(!root||!box)return;
  Promise.all([need("meta.json").then(m=>{META=m;}).catch(()=>{}),need("votes/index.json")])
    .then(([,idx])=>{
      if(!idx||!Array.isArray(idx.terms)||!idx.terms.length)throw new Error("votes/index.json names no term");
      VT.idx=idx;
      VT.st=votesRead(location.search,idx.terms);
      if(VT.st.member)votesNeedPeople();
      votesControls();votesDraw();
    })
    .catch(e=>{
      box.innerHTML=`<p class="note" role="alert">The votes could not be loaded. <code>${esc(e.message||String(e))}</code></p>`;
    });
}
if(window.GR_VOTES)votesInit();
