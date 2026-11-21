// The day without its year where the year goes without saying ("Oct 7" in
// Latest activity), and with it for the status box: out of session, the last
// floor day and the summary's date can be months back, and across a new year
// "Aug 19" is ambiguous. components.js's dateWords() writes both, and the
// server-rendered copy below writes the same with shell.date_words().
// In the page's language: window.GR_LANG on a Spanish page, English
// where it is not set.
const fd=d=>dateWords(d||"","short",window.GR_LANG);
// THE RECORD'S OWN WORDS on a page in another language are marked English
// (i18n.py): a bill's title and the line of its history.
const REC=window.GR_LANG&&window.GR_LANG!=="en"?' lang="en"':"";
// A hand-kept line's Spanish twin (status.txt note_es, milestone_es), where
// the page is Spanish and there is one: the site's own wording, so no
// lang="en" mark.
const ES_ON=window.GR_LANG==="es";
const KEPT=(x,es)=>ES_ON&&es?esc(es):esc(x);
// LATEST ACTIVITY'S DAYS, IN THE READER'S CLOCK (24 October 2026). The box is
// the build's, and a build stands for a day or more: a day it called
// "yesterday" is two days back by the next evening. Each day carries its date,
// and this says how long ago it was as build_pages.past_rel does -- "today",
// "yesterday", "3 days ago", nothing past a fortnight -- from the day the
// reader is in, as Coming up's days say "tomorrow". Not from home.json, so it
// holds with the fetch failing. The reader's day on purpose; a testimony
// deadline is Concord's (TWO CLOCKS, ON PURPOSE, at app.js's nhDay).
const latRel=(d,now)=>{
  const p=String(d||"").split("-").map(Number);
  const off=Math.round((now-new Date(p[0],p[1]-1,p[2]))/86400000);
  return off===0?tr("cal.today","today"):off===1?tr("cal.yesterday","yesterday")
    :off>1&&off<=14?tr("cal.days_ago","{n} days ago",{n:off}):"";
};
document.querySelectorAll("#recent .calday[data-d]").forEach(el=>{
  const rel=el.querySelector(".cdrel");
  if(rel)rel.textContent=latRel(el.dataset.d,new Date(new Date().setHours(0,0,0,0)));});
// If the nightly build stops running, nobody should be reading month-old data
// believing it is current. THIS LINE SPEAKS ONLY THEN (the audit of 25 October
// 2026, M8: "Data rebuilt" stood under Coming up and again in the footer).
// The footer says when every page's data was rebuilt (chrome.FOOT_JS); this
// says it again only as a warning -- three days old or more, or a step of the
// build failed -- which the footer's date alone does not give.
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
fetch(DATA("build.json")).then(r=>r.json()).then(B=>{
  const el=document.getElementById("fresh"); if(!el||!B.finished)return;
  const days=Math.floor((Date.now()-new Date(B.finished))/86400000);
  const failed=(B.steps||[]).filter(s=>s.status==="failed").map(s=>s.step);
  if(days<3&&!failed.length)return;
  const when=new Date(B.finished).toLocaleString(window.GR_LOCALE||"en-US",
    {month:"short",day:"numeric",hour:"numeric",minute:"2-digit"});
  let msg=days>=3?tr("fresh.stale","Data last rebuilt {when} — {days} days ago",{when,days})
    :tr("fresh.rebuilt","Data rebuilt {when}",{when});
  if(failed.length)
    msg+=". "+(failed.length>1
      ?tr("fresh.failed_n","{n} build steps failed, so some sections may be incomplete.",{n:failed.length})
      :tr("fresh.failed_1","1 build step failed, so some sections may be incomplete."));
  el.className="fresh stale";
  el.innerHTML=`<span class="fdot"></span>${esc(msg)}`;
}).catch(()=>{});

// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
fetch(DATA("home.json")).then(r=>r.json()).then(H=>{
  const S=H.status||{};

  // Title case, and a colon after each label. The Python copy below says the
  // same.
  const PHASE={"in session":["live",tr("state.in","In Session")],
               "veto day pending":["wait",tr("state.veto","Awaiting Veto Day")],
               "between sessions":["wait",tr("state.between","Between Sessions")],
               "out of session":["off",tr("state.out","Out of Session")]};
  const ph=PHASE[(S.phase||"").toLowerCase()]||["off",S.phase||tr("state.unknown","Status unknown")];
  const ms=(S.milestones||[])[0];
  const stale=S.stale_days>45;
  // ONE RENDERER WINS, AND IT IS THE SERVER'S. The same box is written into the
  // page at build time and again here, and the two have disagreed on screen:
  // the HTML said 39 hearings and this said 4, because home.json came out of
  // the browser's cache while the page itself is revalidated every time.
  // The built copy is the one a crawler and a reader without JavaScript get, it
  // is never stale, and preflight checks the two say the same thing -- so this
  // draws only where the server drew nothing.
  const _state=document.getElementById("state");
  if(_state&&_state.querySelector(".statebox")){/* already drawn */}
  else if(_state)_state.innerHTML=`
    <div class="statebox ${ph[0]}">
      <div class="stateline"><span class="dot"></span><b>${esc(ph[1])}</b></div>
      ${S.headline?`<p class="statehead"${REC}>${esc(S.headline)}</p>`:""}
      ${S.note?`<p class="statenote"${ES_ON&&S.note_es?"":REC}>${KEPT(S.note,S.note_es)}</p>`:""}
      ${ms?`<p class="statenote"><b>${tr("state.next","Next:")} ${KEPT(ms.label,ms.label_es)}</b>, ${fd(ms.date).replace(/[.]$/,"")}.
        ${KEPT(ms.note||"",ms.note_es)}</p>`:""}
      ${stale?`<p class="statenote stalewarn" style="color:var(--st-veto)"
        data-updated="${esc(S.updated||"")}">${tr("state.stale","This summary was last updated {n} days ago and may be out of date.",{n:S.stale_days})}</p>`
        :(S.updated?`<p class="statemeta upd" hidden data-updated="${esc(S.updated)}"></p>`:"")}
    __YEAR_LINK__</div>`;
  // NO "WHO HOLDS OFFICE" HERE (23 October 2026). The Governor and the
  // Council were drawn under the calendar from home.json's composition,
  // read from a second hand file beside status.txt that was never filled
  // in, so the block never drew; the person retired that file, and who holds an
  // office is the Officials page's, from corrections/officials.json. The
  // chambers and the vacant seats are the legislators page's.

  // THE FIVE COUNTS ARE GONE: they sat between the search box and the three
  // cards that are the actual way in, and nobody arrives to be told how many
  // bills exist. The scale of the record is said once, in the footer's link
  // to the data. .statgrid still styles the same grid on the data page.

  // #upcoming IS NOT TOUCHED HERE, ON PURPOSE. The calendar is rendered into
  // the page by calendar_html() at build time, from the rows the Calendar
  // tab's week is drawn from -- so re-rendering it here would be a second
  // renderer of one thing, which is the mistake this project has paid for
  // more than once, and it would render it WORSE: the bill titles are
  // resolved out of site/idx/<term>.json, 1.19 MB that the home page must not
  // fetch to print four of them, and the meeting rows are <details> elements
  // that need no script to open. Leaving it alone means the calendar also
  // works before this file loads and with JavaScript off.

  // COMING UP, IN THE READER'S OWN CLOCK. The calendar block is written when
  // the site is built, and a build stands for as long as it stands, so the
  // home page has headed a past day "today" with a committee session that had
  // already met at the top of the list. Each day carries its own date, so
  // this drops the days that have gone and says how far off the rest are now.
  //
  // AND THE DAYS PAST THE READER'S SUNDAY. The rail is this week, as the
  // Calendar tab's is, and "this week" is the reader's as much as "today" is:
  // a build made just after midnight on a Monday, read somewhere it is still
  // Sunday evening, holds next week's days, and they are not coming up this
  // week. getDay() calls Sunday 0, which ends an ISO week rather than
  // starting one, so on a Sunday the week has no days left after today.
  // Nothing else here is touched.
  // FROM SATURDAY, NEXT WEEK (D13): on a Saturday or a Sunday in the
  // reader's clock the rail is the coming Monday's week, Monday to Sunday,
  // and its name says so; on a weekday it is today to Sunday, and its name
  // says This Week again for a rail built at the weekend.
  // The reader's day on purpose; a testimony deadline is Concord's (TWO
  // CLOCKS, ON PURPOSE, at app.js's nhDay).
  (function(){
    const now=new Date(); now.setHours(0,0,0,0);
    const dow=now.getDay(),ahead=dow===6||dow===0;
    const from=ahead?(dow===6?2:1):0,to=ahead?from+6:(7-dow)%7;
    // COMING UP'S OWN DAYS: Latest Activity's are days of the same class,
    // all of them past, and this would take every one of them away.
    const days=[...document.querySelectorAll(".cal .calday[data-d]")];
    let left=0;
    days.forEach(d=>{
      const p=d.dataset.d.split("-").map(Number);
      const off=Math.round((new Date(p[0],p[1]-1,p[2])-now)/86400000);
      if(off<from||off>to){d.remove();return;}
      left++;
      const rel=d.querySelector(".cdrel");
      // `off<=14`, as the built labels have it: a week's days never reach
      // it, and a bound that matched them was the point -- `off<14` once left
      // the last day of a fortnight with no label at all.
      if(rel)rel.textContent=off===0?tr("cal.today","today"):off===1?tr("cal.tomorrow","tomorrow")
        :off<=14?tr("cal.in_days","in {n} days",{n:off}):"";
    });
    const cal=document.querySelector(".cal");
    const name=cal&&cal.querySelector&&cal.querySelector(".calwk .chip");
    if(name&&cal.dataset&&cal.dataset.mon){
      const p=cal.dataset.mon.split("-").map(Number);
      const off=Math.round((new Date(p[0],p[1]-1,p[2])-now)/86400000);
      // The rail's Monday against the reader's: this week's is 0 to 6 days
      // back, next week's 1 to 7 days on.
      // AND AN EMPTY RAIL'S SENTENCE WITH IT (the preview check of 25
      // October 2026): built on a Sunday and read on the Monday, the chip
      // said This Week and the note under it "... scheduled next week.", in
      // calendar_html's words for the day it was built. The sentence names
      // the same week as the chip, so it is said again with it, in the same
      // words.
      const none=cal.querySelector(".calnomeet");
      if(off<=0&&off>-7){
        name.textContent=tr("cal.this_week","This Week");
        if(none)none.textContent=tr("cal.none_left","No House or Senate committee meetings are scheduled for the rest of this week.");
      }else if(off>0&&off<=7){
        name.textContent=tr("cal.next_week","Next Week");
        if(none)none.textContent=tr("cal.none_next","No House or Senate committee meetings are scheduled next week.");
      }
    }
    if(cal&&days.length&&!left){
      // The line under the rail stays: it is the way to the full calendar,
      // which is the useful thing to offer under an empty week.
      const more=cal.querySelector(".calall");
      // In calendar_html's words for an empty week: the rail holds the
      // chambers' own meetings, not the study committees.
      cal.innerHTML=`<h2>${tr("cal.coming","Coming Up")}</h2><p class="note">${tr("cal.none_else","No more House or Senate committee meetings are scheduled this week.")}</p>`
        +(more?more.outerHTML:"");
    }
    // "Last updated N days ago" is the one line whose whole job is to say the
    // summary may be stale; it cannot be a number frozen at build time. A
    // fresh summary says nothing about its date (the person, 25 October
    // 2026), so the line shows only as the warning.
    const up=document.querySelector(".statebox .upd,.statebox .stalewarn");
    if(up&&up.dataset.updated){
      const p=up.dataset.updated.split("-").map(Number);
      const age=Math.round((now-new Date(p[0],p[1]-1,p[2]))/86400000);
      if(age>45){
        up.className="statenote stalewarn";
        up.style.color="var(--st-veto)";
        up.hidden=false;
        up.textContent=tr("state.stale","This summary was last updated {n} days ago and may be out of date.",{n:age});
      }else{
        up.className="statemeta upd";
        up.style.color="";
        up.hidden=true;
        up.textContent="";
      }
    }
  })();

  // #recent IS NOT TOUCHED HERE EITHER (24 October 2026). Latest Activity is
  // drawn into the page by build_pages' recent_box, a meeting an item, with
  // what was done to each bill in the site's words for it, which this script
  // does not carry; drawn again here from home.json it would be the second
  // renderer the calendar's comment above warns of. Its days are said again
  // in the reader's own clock, below (latWhen), as Coming up's are.

  // Closest votes and most contested are computed and stored, but not shown.
  // Both invite a reading the site does not want to make, and the page is
  // better without them for now.
  const cl=[], co=[];
  document.getElementById("notable").innerHTML=
    `${cl.length?`<h2>Closest floor votes</h2><table><tbody>${cl.map(v=>
      `<tr><td style="width:86px"><b>${v.y}–${v.nn}</b></td>
       <td><a href="bills#${esc(v.bill)}">${esc(v.n)}</a>
       <span style="color:var(--ink-2)">${esc(v.q||"")}, ${fd(v.date)}</span><br>
       <span class="actw">${esc(v.title)}</span></td></tr>`).join("")}
       </tbody></table>`:""}
     ${co.length?`<h2>Most contested</h2>
       <p class="note">Bills that took the most recorded floor votes to settle.
       Committee and executive session votes are excluded: a committee's
       recommendation is not binding on the chamber, and a 10–9 in committee
       is a different thing from a 201–199 on the floor. This counts the
       record, not what people read here. The site counts page views —
       how many, and which pages — and nothing more; see
       <a href="about">About</a>.</p>
       <table><tbody>${co.map(b=>
       `<tr><td style="width:86px">${b.nrc} votes</td>
        <td><a href="bills#${esc(b.id)}">${esc(b.n)}</a>
        <span style="color:var(--ink-2)">${esc(b.title)}</span></td></tr>`).join("")}
       </tbody></table>`:""}`;

  // #session IS NOT DRAWN HERE. Recent Session Days is the build's
  // (build_pages.recent_sessions, 26 October 2026), in the page's language,
  // where it was drawn from home.json; this only opens its players, below.
});
// PLAY OPENS THE PLAYER, AND ONLY PLAY (the privacy page: "a player only
// loads if you press play"). Recent Session Days' Play is a button with the
// recording's id on it; nothing from YouTube is asked for until it is
// pressed, and then the no-cookie player takes its place, titled for its
// chamber and day (data-title, the build's words in the page's language),
// so the two players here are not both "Floor session" to a screen reader
// (M18). The player takes the focus the button had; left on nothing, the
// next Tab press started from the top of the page (the audit of 2 October
// 2026, S1). app.js does the same on a bill.
document.addEventListener("click",e=>{
  const st=e.target.closest&&e.target.closest("#session [data-embed], .wbrec [data-embed]");
  if(!st)return;
  const box=st.parentNode, had=document.activeElement===st;
  st.outerHTML=`<iframe allow="autoplay" allowfullscreen
    src="https://www.youtube-nocookie.com/embed/${encodeURIComponent(st.dataset.embed)}?autoplay=1"
    title="${esc(st.dataset.title||"")}"></iframe>`;
  const frame=had&&box&&box.querySelector("iframe");
  if(frame)frame.focus({preventScroll:true});
});
// ONE BOX, THE HEADER'S FINDER (D13): find.js's findDraw, given this box's
// ids, draws the header panel's rows into the box's dropdown -- the same
// matcher, the same order, the same rows, so the two boxes cannot disagree.
// find.js is deferred, so it is asked for when a reader types, not now.
// GO IS SEARCH HERE (the webinar's phone check, 16 October 2026; the person
// approved it). This box has a Search button, and Return or a phone's Go key
// took the first row instead, as the header's finder then did: "housing"
// opened the House Housing committee where the reader wanted the housing
// bills. So Return does what the button does -- every result (/search), and
// with nothing typed the bill search, as it always did -- except for a bill
// number, which opens the bill (find.js's findBill: the person's rule of 12
// October). A row is still one tap away. The header's box opens /search
// for a bill number too since 8 November 2026, and this one since 9 November
// (Alice: "Home search opens results"): Return was the Search button, always.
// UNTIL THERE IS ONE CLEAR DESTINATION (the owner, 17 November 2026): Return
// opens the row find.js's findClear finds certain -- this term's bill for its
// number, a member, a town, a seat, a how-to guide -- which the dropdown
// marks and its status line names, as the header's box does (findGo), while
// the dropdown is open; and every result for anything else. The Search
// button is every result, always. The arrows choose a row (findArrow), and
// Return there opens that row.
const HQ={out:"hqout",box:"hq",clear:"",say:"hqsay"};
const hq=document.getElementById("hq"),hqout=document.getElementById("hqout");
// ABOVE THE KEYBOARD. On a phone this box stands most of the way down the
// first screen, and the keyboard covered the rows it opens; as they first
// appear, the box is brought up to the top of the window.
function hqLift(){
  if(!(window.matchMedia&&matchMedia("(max-width:45em)").matches))return;
  const top=hq.getBoundingClientRect().top;
  if(top>80)window.scrollBy({top:top-16,behavior:"smooth"});
}
function hqDraw(){
  const v=hq.value;
  if(!v.trim()||typeof findDraw!=="function"){hqout.hidden=true;return;}
  const opening=hqout.hidden;
  hqout.hidden=false;
  findDraw(v,HQ);
  if(opening)hqLift();
  findRows().then(()=>{if(hq.value===v&&!hqout.hidden)findDraw(v,HQ);});
}
// Half an emoji is not an address (find.js, _fwell).
const hqAddr=v=>{v=(v||"").trim();return v?"/search?q="+encodeURIComponent(
  v.replace(/[\uD800-\uDFFF]/gu,"\uFFFD")):"/bills";};
hq.addEventListener("input",hqDraw);
hq.addEventListener("focus",()=>{if(hq.value.trim())hqDraw();});
hq.addEventListener("keydown",e=>{
  if(e.key==="Escape"){hqout.hidden=true;return;}
  if(typeof findArrow==="function"&&findArrow(e,hq,hqout))return;
  if(e.key!=="Enter")return;
  e.preventDefault();
  location.href=(!hqout.hidden&&typeof findGo==="function"&&findGo(hq.value,HQ))||hqAddr(hq.value);
});
hqout.addEventListener("keydown",e=>{if(typeof findArrow==="function")findArrow(e,hq,hqout);});
document.getElementById("hgo").addEventListener("click",()=>{location.href=hqAddr(hq.value);});
// Away from the box, the dropdown closes; "Did you mean" searches again here.
document.addEventListener("click",e=>{
  const d=e.target.closest&&e.target.closest("#hqout .fdym");
  if(d){e.stopPropagation();hq.value=d.dataset.find;hqDraw();hq.focus();return;}
  if(!(e.target.closest&&e.target.closest(".searchbig")))hqout.hidden=true;
},true);
