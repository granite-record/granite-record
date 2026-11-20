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

