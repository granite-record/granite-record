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

