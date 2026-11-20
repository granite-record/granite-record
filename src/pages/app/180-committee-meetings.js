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

