// ===================================================== the bill's own facts ==
// THE GENERAL COURT'S OWN FIELDS, AS A TABLE, replacing the CURRENT STATUS
// panel. On a law that panel said the card's chip back word for word, and
// where it did not it concatenated three separate fields into one line --
// "House: PASSED/ADOPTED - Senate: LAID ON TABLE" -- which a reader had to
// unpick. They are three fields, so they are three rows.
//
// Measured on the current term's 847 bills before this was written: every one
// carries a general status, 763 a House status, 526 a Senate status, and the
// two chambers disagree on 321 of them. The per-chamber rows were kept for
// that, and have since given way to How it got here (journeyList), which says
// what each chamber did from the docket on every bill, not the half of them
// whose status page filled the field.
//
// CHAPTER IS NOT AN RSA CHAPTER. Both are called a chapter and they are
// different numberings. `chapter` is the session law: HB 1 of 2025 became
// Chapter 140 of the Laws of 2025. The RSA chapters are the ones the bill
// amends, and HB 1 amends five of them. Two rows, and only the RSA row is
// linked -- every URL there is one already used elsewhere on this page, where
// gc.nh.gov's address for a chaptered law has never been checked and guessing
// it would put a broken link on 305 bills of this term alone.
//
// d.amends, NOT d.rsa. d.rsa is every citation anywhere in the bill, its
// reports and its amendments, which is what makeRsa needs to turn words into
// links and is not a list of what the bill changes: 628 bills cite RSA 91-A
// and 150 amend it, so this row was claiming a bill changed the Right-to-Know
// law where the bill only said "exempt from disclosure under RSA 91-A:5, IV".
// build_site_v2.bill_amends reads the bill's own amending instructions --
// "Amend RSA 91-A:4, IV(a) to read as follows:" -- and 43.5% of the chapter
// claims on this site turned out to be mentions. A bill whose text is not on
// disk carries no `amends` and gets no row, which is the honest answer:
// nothing on file says what it amends.
function rsaChapters(d){
  const seen=new Map();
  for (const [k,u] of Object.entries(d.amends||{})){
    const m=/^RSA\s+([0-9]+(?:-[A-Za-z]+)?)/.exec(k);
    // The link is to the first SECTION of that chapter the bill cites,
    // because that is the address this site has and can stand behind. It
    // lands the reader in the right chapter either way.
    // The site's own page is the chapter's, not the cited section's anchor.
    if(m && !seen.has(m[1])) seen.set(m[1], u.charAt(0)==="/"?u.split("#")[0]:u);
  }
  return [...seen.entries()];
}

// THE JOURNEY AS A LIST: a glyph, the body, what it did in plain words with its
// tally, and the day -- "✓ Senate  Passed with an amendment, 16–8  22 May
// 2025". The glyph carries the state as the rail's does: a check where the
// decision carried the bill on, a cross where it stopped it, a turning arrow
// where it sent it round again (tabled, back to committee, the other
// chamber's amendment refused).
//
// SIX LINES UNTIL ASKED. HB 2 of 2025 went through both chambers, a committee
// of conference and the governor. The first two and the last four are shown
// -- where it began and how it ended -- and the rest are in the list, hidden,
// behind "Show 3 more", which opens them where they are.
//
// NOT A WAY TO THE VOTES TAB. It read "and 3 more on the Votes tab", and of
// the 2,195 bills whose list is capped, 473 hid a line that tab does not
// have: a voice vote has no card there, and HB 396 of 1989's Votes tab reads
// "No roll call votes on this bill." HB 1102 of 2026 hid both chambers'
// voice votes adopting its conference report. The hidden lines are this
// list's own, so this list is where they open.
// AND THE RAIL'S OWN TWO, BARE (the person, 8 October 2026): the line that
// sent the bill to interim study takes the rail's orange "~", and the line
// that laid a bill on the table takes the yellow pause, two bars the
// stylesheet draws (.jl .j-ontable .jg::after) -- while it still lies there,
// and, since the person's answer of the same day ("Show the body it was
// tabled in with the yellow pause, and show the red x mark on the law once it
// died when the session ended"), once it has died there, when a line with
// the cross says so after it. The "~" is drawn rather than typed, so it
// centres at any size, and here before the rail (RAILMARK) takes it too.
//
// AND THE INTERIM STUDY COMMITTEE'S REPORT, ONCE THE SESSION IS OVER (option
// (d), the person, 9 October 2026): its own line, after the cross of the
// bill's death, with a bare arrow (green since 30 October 2026), "f", where the committee
// recommended the subject for future legislation -- advice for a new bill in
// the next term, which the line names and links where the clerk wrote down
// its LSR (s.link) -- and the "~" where it did not. The arrow is drawn, as the
// wave is, and only here: the rail has no stop for it.
// The wave is components.js's since 10 October 2026 (RL_WAVE), where the
// dated rail is drawn in both languages.
const WAVE=RL_WAVE;
const ARROW='<svg class="arrow" viewBox="0 0 12 12" aria-hidden="true" focusable="false">'
  +'<path d="M2 6h7.2M6.4 2.9 9.6 6l-3.2 3.1" fill="none" stroke="currentColor" '
  +'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const JMARK={p:"✓",x:"✕",h:"↺",s:WAVE,t:"",f:ARROW};
// A committee's acts on its meeting's card (actSaid): the interim study
// report it recommended, in the green arrow, and one it did not, killed, in
// the red cross. The arrow is a drawing, so its green is a mark's.
const ACTMARK={rec:ARROW,kill:"\u2715"};
const JCLASS={s:"istudy",t:"ontable",f:"ifuture"};
// A line's words, with the bill it names linked where it names one: the next
// term's bill an interim study report's clerk wrote down (s.link, a bill/
// address on this site). Only the first place the name stands is linked.
// `shown` where the build condensed the line (a law in effect in many stages,
// build_site_v2.law_in_stages); `text` keeps every part for the Laws pages.
function jText(s){
  const t=esc(s.shown||s.text||""), l=s.link;
  if(!l||!l.text||!l.href||!/^bill\/\d{4}\/[a-z0-9]+(?:\.html)?$/.test(l.href))return t;
  const at=t.indexOf(esc(l.text));
  return at<0?t:t.slice(0,at)+billMention(l.text,l.href.replace(/\.html$/,""))+t.slice(at+esc(l.text).length);
}
const JBODY={H:"House",S:"Senate",G:"Governor",L:"Law",V:"Voters"};
const JOURNEY_SHOWN=6;
// A TALLY IS ONE WORD (9 October 2026). A browser may break a line after an
// en dash, and on a phone How it got here set "Passed with an amendment,
// 231–" over "99" and "189–" over "155" (the review of the merge). Held
// whole, the tally takes the next line together. Only a count either side
// of the dash: "355,054–266,883" whole, the comma after it left to break.
const tallyWhole=h=>h.replace(/\d+(?:,\d{3})*–\d+(?:,\d{3})*/g,
  m=>`<span class="tally">${m}</span>`);
// THE MEMBERS THE STORY NAMES, LINKED (the person, 10 October 2026: "movers
// in story text not linked"): each one build_site_v2.story_people could tie
// to one sitting member, as the person in a sentence (personLink), where the
// story names them; any other name stays the words it was. `html` is
// already escaped; the names are matched as escaped, longest first, in one
// pass, so no name is linked inside another's link.
function storyPeople(html,d){
  const ps=((d&&d.story_people)||[]).filter(p=>p&&p.text&&p.slug)
    .sort((a,b)=>b.text.length-a.text.length);
  if(!ps.length)return html;
  const by={};ps.forEach(p=>{by[esc(p.text)]=p;});
  const rx=new RegExp("("+Object.keys(by).map(s=>s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|")
    +")(?![\\w])","g");
  return html.replace(rx,m=>personLink({display_full:by[m].label,slug:by[m].slug}));
}
// THE VOTE CARDS' ANCHORS, AND A TALLY AS A LINK TO ITS CARD (the owner, 10
// November 2026: "when a bill summary cites a vote like 198-167, it should
// link to the votes tab so you can click it to view that particular vote in
// detail"). Each card of the Votes tab has an id, "vote-<date>-<chamber>-
// <yeas>-<nays>" ("vote-2025-03-12-H-231-99"; a second card of the same four
// takes "-2"; the voters' own "vote-ballot"), and a tally in the Summary that
// names a vote of this bill by DATE, CHAMBER AND COUNTS links to
// /bill/<year>/<bill>/votes#<id>. Never by the count alone, and never where
// two cards fit: the tally stays plain text. A How It Got Here row has its
// own date and chamber; a story sentence is read for the one date and the
// first chamber it names. Only a tally written with an en dash, as the build
// writes them, so a date or an amendment number ("2025-0386h") is never one.
const VOTE_HASH=/^vote-[\w-]+$/;
function voteAnchors(d){
  const seen={};
  return (d.rollcalls||[]).map(rc=>{
    const base=`vote-${rc.date||""}-${rc.body||""}-${rc.yeas==null?"x":rc.yeas}-${rc.nays==null?"x":rc.nays}`;
    seen[base]=(seen[base]||0)+1;
    return seen[base]>1?`${base}-${seen[base]}`:base;
  });
}
const TALLY_RX=/(\d+(?:,\d{3})*)–(\d+(?:,\d{3})*)/g;
function voteLinks(html,b,d,ctx){
  const rcs=(d&&d.rollcalls)||[],bal=d&&d.ballot&&!d.ballot.pending?d.ballot:null;
  if((!rcs.length&&!bal)||!b||!b.year||html.indexOf("–")<0)return html;
  const A=voteAnchors(d),num=s=>+String(s).replace(/,/g,"");
  const href=id=>`bill/${esc(b.year)}/${esc(String(b.id).toLowerCase())}/votes#${id}`;
  const find=(y,n,date,body)=>{
    if(body==="V")return bal&&bal.yes===y&&bal.no===n?"vote-ballot":"";
    const hit=(yy,nn)=>{const m=[];rcs.forEach((rc,i)=>{
      if(rc.body===body&&rc.date===date&&rc.yeas===yy&&rc.nays===nn)m.push(A[i]);});return m;};
    let m=hit(y,n);
    if(!m.length)m=hit(n,y);
    return m.length===1?m[0]:"";
  };
  // The tallies outside any tag or link, linked where `pick` names a card.
  const link=(h,pick)=>{
    let inA=0;
    return h.split(/(<[^>]*>)/).map(p=>{
      if(p.charAt(0)==="<"){
        if(/^<a\b/i.test(p))inA++;else if(/^<\/a\s*>/i.test(p))inA=Math.max(0,inA-1);
        return p;}
      if(inA)return p;
      return p.replace(TALLY_RX,(m,y,n)=>{
        const id=pick(num(y),num(n));
        return id?`<a class="vtl" href="${href(id)}" data-vote="${id}">${m}</a>`:m;});
    }).join("");
  };
  if(ctx)return link(html,(y,n)=>find(y,n,ctx.date,ctx.body));
  // A story: one sentence at a time, split where a sentence ends and not at
  // "Sen. Abbas" or "Rep. Smith".
  const MON="(January|February|March|April|May|June|July|August|September|October|November|December)";
  return html.split(/(?<!\b(?:Sen|Rep|Mr|Mrs|Ms|Dr|St|No|Hon))(?<=[.!?])\s+(?=[A-Z“"])/).map(sn=>{
    if(sn.indexOf("–")<0)return sn;
    const plain=sn.replace(/<[^>]*>/g,"");
    const days=new Set();
    plain.replace(new RegExp(MON+" (\\d{1,2}), (\\d{4})","g"),(m,mo,dd,yy)=>{
      days.add(`${yy}-${String(["January","February","March","April","May","June","July","August",
        "September","October","November","December"].indexOf(mo)+1).padStart(2,"0")}-${String(+dd).padStart(2,"0")}`);return m;});
    const ch=/\b(House|Senate)\b/.exec(plain);
    if(days.size!==1||!ch)return sn;
    const date=[...days][0],body=ch[1]==="House"?"H":"S";
    return link(sn,(y,n)=>find(y,n,date,body));
  }).join(" ");
}
// THE GLOSSARY'S TERMS IN THE SUMMARY'S WORDS (the owner, 10 November 2026:
// "the summary does not appear to have tooltips for things like roll call or
// voice vote"). The first use on the page of each term the glossary holds is
// marked, as termMark does, for the popover components.js draws on it; never
// inside a link (a tally's, a person's, a bill's), and a term only once across
// the Summary's How It Got Here and its story. `seen` is one pass's.
const GLOSS_WORDS=[
  ["ought to pass with amendment","OTPA"],["ought to pass","OTP"],["inexpedient to legislate","ITL"],
  ["interim study","IS"],["voice vote","VV"],["division vote","DV"],["roll call","RC"],
  ["consent calendar","CC"],["regular calendar","RC-calendar"],["committee of conference","Committee of conference"],
  ["ordered to a third reading","OT3rdg"],["laid on the table","Laid on the table"],
  ["indefinitely postponed","Indefinitely postponed"],["floor amendment","Floor amendment"],
  ["minority report","Minority report"],["re-referred","Rerefer"],["public hearing","Public hearing"],
  ["executive session","Executive session"],["work session","Work session"],["prime sponsor","Prime sponsor"],
  ["second committee","Second committee"],["special order","Special order"],["fiscal note","FN"],
  ["carried over","Carried over"],["floterial","Floterial district"],["chaptered","Chaptered"],
  ["tabled","Tabled"],["veto","Veto"],["override","Override"],["enrolled","Enrolled"],
  ["reconsidered","Reconsider"],["concur","Concur"]];
function glossPass(){
  const seen=new Set();
  const G=(typeof WORDBOOK!=="undefined"&&WORDBOOK.glossary)||{};
  const words=GLOSS_WORDS.filter(w=>Object.prototype.hasOwnProperty.call(G,w[1]));
  if(!words.length)return h=>h;
  const key={};words.forEach(w=>{key[w[0]]=w[1];});
  const rx=new RegExp("\\b("+words.map(w=>w[0].replace(/[.*+?^${}()|[\]\\]/g,"\\$&"))
    .sort((a,c)=>c.length-a.length).join("|")+")\\b","gi");
  return html=>{
    let skip=0;
    return String(html).split(/(<[^>]*>)/).map(p=>{
      if(p.charAt(0)==="<"){
        if(/^<(a|button)\b/i.test(p)||/^<span\b[^>]*data-term=/i.test(p))skip++;
        else if(/^<\/(a|button|span)\s*>/i.test(p)&&skip)skip--;
        return p;}
      if(skip)return p;
      return p.replace(rx,m=>{
        const k=key[m.toLowerCase()];
        if(!k||seen.has(k))return m;
        seen.add(k);
        return `<span data-term="${k}">${m}</span>`;});
    }).join("");
  };
}
function journeyList(b,d,gl){
  const st=((d.journey||{}).steps)||[];
  if(!st.length)return "";
  const k=dkey(b.id);
  // Folded only where it hides two rows or more: the fold is a row of its
  // own, so hiding one row for it saved nothing (the owner, 10 November 2026,
  // HB 1 with seven steps).
  const cut=st.length>=JOURNEY_SHOWN+2&&!jOpen.has(k);
  const hide=i=>cut&&i>=2&&i<st.length-(JOURNEY_SHOWN-2);
  const said=s=>{
    // A row's words: a vote's tally linked to its card, by the row's own date
    // and chamber, and a term marked for its popover.
    const h=voteLinks(jText(s),b,d,{date:s.date||"",body:s.body});
    return tallyWhole(gl?gl(h):h);
  };
  const line=(s,i)=>`<li class="j-${esc(JCLASS[s.mark]||s.mark)}${s.rec!==undefined?` jrec-${esc(s.rec||"without")}`:""}"${hide(i)?" hidden":""}><span class="jg"
    aria-hidden="true">${JMARK[s.mark]||""}</span><span class="jb">${
    esc(JBODY[s.body]||s.body)}</span><span class="jt">${said(s)}</span><span
    class="jd">${s.date?esc(dateWords(s.date)):""}</span></li>`;
  const rows=st.map(line);
  if(cut)rows.splice(st.length-(JOURNEY_SHOWN-2),0,
    `<li class="jmore"><button type="button" class="link" data-jmore="${esc(k)}">Show ${
      st.length-JOURNEY_SHOWN} more</button></li>`);
  return `<ul class="jl">${rows.join("")}</ul>`;
}

// THE ON THE RECORD BOX IS GONE (option E, the person, 8 October 2026): its
// facts are in the bill's head (billHead), How It Got Here and the RSA
// chapters are sections of the summary (renderSummary, rsaLine), and "This
// bill on gencourt" is the link on "Source: NH General Court". The head has
// no Introduced and no LSR fact (F14, 7 October 2026): the rail dates the
// introduction, and the LSR number is the drafting office's reference.

// HOW A BILL ENDED WHEN NOTHING WAS VOTED ON IT. Two lines, both from the
// record rather than from the status field, and both about bills whose last
// docket line is not an outcome:
//  - a committee that took a bill for interim study reports on it in the
//    autumn, and that report is the end of the story. The docket prints it;
//    the page said nothing, so "Referred for interim study" stood as the last
//    word for months after the committee had answered.
//  - a term that has run out of session days finishes every bill still
//    pending. The status keeps the record's own word ("Committee report
//    filed", where the chip says Died; since 17 October 2026 a tabling reads
//    "Died on the table");
//    this says why nothing follows it. status/status.txt sets the date.
// Since 9 October 2026 the report is read in every wording the docket has
// used (build_site_v2.interim_report), and says one of three things: the
// committee recommended the subject, did not, or made no recommendation
// ("Without Recomendation", 2024; "No Recommendation", HB 1592 of 2014).
// IN THE WORDS EVERY OTHER PLACE SAYS IT IN (23 October 2026): the phrase is
// WORDBOOK.study_report's (src/pages/words/study_report.json), which How it
// got here, a committee's meeting card, the docket's plain line and the
// emails take too, so that none of them can tell the report differently.
const STUDY_SAID=WORDBOOK.study_report.said;
function endNote(d){
  const s=d.study_report,out=[];
  const k=s&&(s.rec!==undefined?s.rec:s.recommended?"rec":"not");
  const said=s&&(k&&Object.prototype.hasOwnProperty.call(STUDY_SAID,k)?STUDY_SAID[k]
    :"filed its report");
  if(s)out.push(`<p class="note"><b>${esc(WORDBOOK.study_report.head)}${s.date?`, ${
    esc(dateWords(s.date))}`:""}:</b> the committee ${said}${
      s.vote?`, ${esc(s.vote)}`:""}.</p>`);
  // NOT "WHATEVER ITS LAST RECORDED STATUS SAYS" (17 October 2026): that
  // set the page against its own Status line, and since the language sweep
  // a stage the bill died at says so there (build_site_v2.ENDED_AS).
  if(d.session_over)out.push(`<p class="note">The chambers do not sit again
    this term: the last session day was ${esc(dateWords(d.session_over))}, and a
    bill that had not passed both chambers by then went no further.</p>`);
  return out.join("");
}

// THE SUMMARY IN W4 SECTIONS (the component plan's C7 and option E, the
// person, 8 October 2026): each heading in a margin in Title Case, beside
// prose about a hundred characters wide, and the whole tab the summary's --
// the ON THE RECORD box is gone, its facts in the head. The official
// analysis first, its source the bill on GenCourt ("Source: NH General
// Court" links to it) and the RSA chapters the bill amends under it; then
// How It Got Here, the story stage by stage under the headings narrative.py
// writes (C8: in their case where they are made, "House Committee
// (Housing)", "On the House Floor"), how it ended, and the docket.
const RSA_SHOWN=8;
// CHANGED THESE STATUTES (RSA_PAGE.md §7): the sections the statute's own
// source notes credit to the law this bill became, each linked to its anchor
// on the statute's page -- the other end of a section's "How it has changed".
function changedLine(d){
  const a=d.changed||[];
  if(!a.length)return "";
  const link=x=>{const p=x.split(":");return `<a class="rsa" href="${esc(lawPath(p[0],p[1]||""))}">${esc(x)}</a>`;};
  const lead=a.length===1?"Changed RSA":"Changed these statutes:";
  if(a.length<=RSA_SHOWN+2)return `<p class="rsaline">${lead} ${a.map(link).join(", ")}</p>`;
  return `<div class="rsaline">${lead} <span class="rsaset">${a.slice(0,RSA_SHOWN).map(link).join(", ")}</span>`
    +`<details class="rsamore"><summary><span class="shut">Show all ${a.length} sections</span>`
    +`<span class="open">Show fewer</span></summary><span class="rsaset">${
      a.slice(RSA_SHOWN).map(link).join(", ")}</span></details></div>`;
}
// THE ARTICLES OF THE STATE CONSTITUTION A CACR CHANGES (17 October 2026),
// which build_site_v2 reads from the CACR's own resolving clauses: each
// linked to its article on the Laws page's Constitution tab. Said the way the
// RSA line says a bill's chapters, in the present tense of what the measure
// does, whatever became of it. A new article is placed after one that exists,
// and that one is the link.
function constLine(d){
  const a=Array.isArray(d.constitution)?d.constitution:[];
  if(!a.length)return "";
  const link=x=>`<a class="rsa" href="${esc(x.href)}">${esc(x.label)}</a>`;
  const out=[];
  const ch=a.filter(x=>x.verb==="amend"||x.verb==="repeal");
  if(ch.length)out.push(`<p class="rsaline">${ch.length===1?"Changes this article of the state Constitution:"
    :"Changes these articles of the state Constitution:"} ${ch.map(link).join(", ")}</p>`);
  a.filter(x=>x.verb==="insert_after").forEach(x=>out.push(
    `<p class="rsaline">Adds a new article to the state Constitution, after ${link(x)}</p>`));
  a.filter(x=>x.verb==="reenact_part").forEach(x=>out.push(
    `<p class="rsaline">Rewrites ${link(x)} of the state Constitution</p>`));
  return out.join("");
}
function rsaLine(d){
  return rsaLines(d)+constLine(d);
}
function rsaLines(d){
  const ch=rsaChapters(d);
  if(!ch.length)return changedLine(d);
  const link=([n,u])=>`<a class="rsa" href="${esc(u)}"${u.charAt(0)==="/"?"":' target="_blank" rel="noopener"'}>${esc(n)}</a>`;
  // The person's words, approved 17 October 2026, for "Amends RSA chapters".
  const lead=ch.length===1?"Changes this chapter of state law (RSA):"
    :"Changes these chapters of state law (RSA):";
  if(ch.length<=RSA_SHOWN+2)return `<p class="rsaline">${lead} ${ch.map(link).join(", ")}</p>`+changedLine(d);
  return `<div class="rsaline">${lead} <span class="rsaset">${ch.slice(0,RSA_SHOWN).map(link).join(", ")}</span>`
    +`<details class="rsamore"><summary><span class="shut">Show all ${ch.length} chapters</span>`
    +`<span class="open">Show fewer</span></summary><span class="rsaset">${
      ch.slice(RSA_SHOWN).map(link).join(", ")}</span></details></div>`+changedLine(d);
}
const gcSource=d=>d.docket_url?`<a href="${esc(d.docket_url)}" target="_blank" rel="noopener">NH General Court</a>`
  :"NH General Court";
// TESTIFY ON THIS BILL (the person, 22 October 2026: "Bills that are from
// the current year should have the testimony box but greyed out when
// testimony submission is not active, with a line saying that testimony
// submission has either passed or not opened yet"). Each chamber's online
// sign-in takes positions -- the House's written testimony too; the Senate's
// confirmation page says where to send it -- only once a bill's public
// hearing is scheduled (the Senate's guidance, civics.SRC_SENATE_TESTIFY),
// and in practice until midnight at the end of the hearing's day (the
// editor's account, an observed() claim in guides.py; the live pane says it
// plainly, the person's choice of 26 October 2026). Neither form can be
// opened at a bill, so the control links to the form of the chamber whose
// hearing is next.
// A BUTTON IN THE ROW, NOT A BOX ON THE SUMMARY (the person, 25 October
// 2026: "The testify option should also be a button when it's active in the
// same format as the print, share, and follow buttons instead of on the
// summary page, and it will be greyed out when the deadline has passed or
// hasn't yet opened and will tell you which one it is when you click on it
// instead of linking you to the submission page with the instructions. When
// it's active, the testify button could maybe be colored in so it's a more
// clear indicator as to when it's live, and it should say when testimony
// submissions close if it's scheduled."). Follow's form: a <details> whose
// <summary> is the button and whose pane opens under it; mountTestify puts
// it in the row. While a hearing is ahead the button is filled in pine and
// says the hearing's day, "Testify until Jan 13" -- the day the sign-in
// takes positions until, to its midnight -- and the pane says the hearing,
// the chamber's form and what to choose on it, in the person's words of 26
// October 2026 (THE LIVE PANE IN THE PERSON'S WORDS, below).
// Otherwise the button is greyed, and its pane says which it is, passed or
// not opened yet, in the box's sentences, with no form and no steps. Grey
// is a colour and nothing more, so the button's own words tell a screen
// reader that it is not open.
// A bill of an earlier term has no control. The term turns on 1 December of
// an even year, the eve of Organization Day.
const TESTIFY_FORMS={H:["House","https://gc.nh.gov/house/committees/remotetestimony/"],
  S:["Senate","https://gc.nh.gov/remotecommittee/senate.aspx"]};
// NEW HAMPSHIRE'S DAY, NOT THE READER'S (the review of 25 October 2026). The
// button names the hearing's day in Concord, and it was live or shut by the
// reader's own clock: in Los Angeles at 11:30 p.m. on 13 January, 2:30 a.m.
// on the 14th in Concord, SB 406 still read "Testify until Jan 13", and in
// London at 1 a.m. on the 14th, 8 p.m. on the 13th in Concord, it read shut.
// The term turns by Concord's day too. The IANA zone carries the
// daylight-saving rule, as workers/follow's nhClock does; a browser without
// it falls back to its own day.
// TWO CLOCKS, ON PURPOSE (the review of 25 October 2026). A DEADLINE IS
// CONCORD'S: the online sign-in closes at midnight in New Hampshire wherever
// the reader is ("Public testimony is open until midnight the day of the
// hearing", the person's words of 26 October 2026, which name no zone), so
// whether it is still open, the day the button names and which term is
// sitting are asked of New Hampshire's day. A DAY'S NAME IS THE READER'S:
// "today", "tomorrow", "in 3 days", "yesterday" and "this week" are words
// about the calendar of the person reading, so a committee's Upcoming
// (calendarBlock), the home page's Coming up and Latest Activity
// (build_pages HOME_JS) and the Calendar (build_calendar WEEK_JS) read the
// reader's own clock, and each of them points here. Those are not to be
// made one: on Concord's clock a reader in London at 1 a.m. on the 14th
// would be told a hearing on the 14th is "tomorrow"; on the reader's, a
// reader in Los Angeles at 11:30 p.m. on the 13th would be sent to a sign-in
// that closed two and a half hours earlier.
// AND ONE THAT IS NEITHER (the review of 26 October 2026): what retires on a
// day (components.js, data-until) names no day. It hides a member-elect from
// the day they take office, an event in Concord of the same kind as a
// testimony deadline, and it reads the reader's clock by a choice (the
// members-elect, 16 October 2026), not by the rule above; it points here too.
// Whether it should follow Concord's day is that choice's to revisit, and
// nothing here forbids it.
const NH_DAY=(()=>{try{return new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",
  year:"numeric",month:"2-digit",day:"2-digit"});}catch(e){return null;}})();
function nhDay(now){
  try{
    const p={};
    NH_DAY.formatToParts(now).forEach(x=>{p[x.type]=x.value;});
    if(p.year&&p.month&&p.day)return `${p.year}-${p.month}-${p.day}`;
  }catch(e){}
  return `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-${String(now.getDate()).padStart(2,"0")}`;
}
function sittingTerm(now){
  const day=nhDay(now), y=+day.slice(0,4), m=+day.slice(5,7), d=+day.slice(8,10);
  // The new term begins on Organization Day, the first Wednesday of December
  // (proceedings.organization_day), not on 1 December.
  const org=1+(3-new Date(Date.UTC(y,11,1)).getUTCDay()+7)%7;
  const first=y%2?y:((m===12&&d>=org)?y+1:y-1);
  return `${first}-${first+1}`;
}
// WHAT TO CHOOSE ON THE FORM (the person, 22 October 2026, asking the emails
// for "instructions on how to select the bill"): neither form opens at a
// bill, so the pane says what to pick, in the order the Senate's guidance
// gives -- the hearing's day, then the committee, then the bill -- which the
// House's form asks for too. workers/follow/mail.js testifyWords gives the
// emails this pane's words, in its order (the person, 26 October 2026:
// "Emails should stay in sync with how the site displays the testify
// button"), for the hearings follow_changes.bill_upcoming reads from the
// record by these functions' rules; preflight's _testify_email_in_sync holds
// the two to one answer, so a change here is a change there.
// A HEARING'S CHAMBER: the station's own body, and where it names neither
// chamber, the chamber whose word the station uses (EACH CHAMBER'S WORD,
// below: "public hearing" is the House's, "hearing" the Senate's). So every
// hearing has a form, and one still to come is always the live button: with
// the form looked up by body alone, a hearing ahead whose body was neither H
// nor S fell through to the shut button, which could call it the hearing
// that "has passed" (the review of 25 October 2026).
const testifyBody=s=>TESTIFY_FORMS[s.body]?s.body:/^public /i.test(s.what||"")?"H":"S";
// A HEARING ON A PROPOSED AMENDMENT IS A PUBLIC HEARING TOO (the review of 26
// October 2026). The House's docket line "Public Hearing on non-germane
// Amendment # 2026-0422h: 02/03/2026 11:20 am GP234" -- and SB 210 of 2025's
// "Public Hearing on Amendment # 2025-2318h: ..." -- is a public hearing on
// the bill, and the House's online sign-in takes positions for it: 1,904 for
// HB 1560-FN's, 1,820 for CACR 12's. No station stands for it: a bill's
// proceedings are read from its own hearing lines (docket_parser), and this
// is not one. The Senate's, "Hearing: 02/18/2026, Room 103, SH, 09:00 am, on
// proposed non-germane amendment # ...", is a station already. The button
// read the stations alone, so on 47 such hearings of 44 bills of 2025-2026
// it named the wrong last hearing -- CACR 12's "was Mar 9, 2026", where its
// Summary has 1,820 signed in on April 15 -- and HB 1560-FN, heard on 27
// January, would have read "has passed" the week before its second hearing.
// So they are read here from the record's own events: the day a person
// corrected the row to where there is one (date_as_recorded), and otherwise
// the line's own -- SB 210's row was entered on 21 May for the 27th; the time
// and the room from the line; the committee that has the bill on the day
// (testifyHouseCommittee, below). A
// line the docket called off (called_off) is no hearing, and one a House
// station already stands for, that day at that time, is not counted twice.
// The stations are left as they are, since the Hearings tab, the recordings
// and their moments read them: this is Testify's reading alone.
// ONE SITTING WITH TWO DATES IS ONE HEARING (the review of 26 October 2026).
// A Senate committee's hearing report that gives a day the docket has no
// Senate hearing of the bill on stands on a station of its own, dated by
// the report (build_site_v2.report_station: dated_by "report", and
// docket_heard the days the docket does record the bill's Senate hearing
// on). Where the docket records one, the two are a single sitting with two
// dates -- SB 76's, on 14 January 2025 by the docket and on the 30th by its
// report -- and the person chose on 24 September that neither is corrected
// to the other; the bill's Hearings tab says both. Testify read them as two
// hearings, and on 14 bills of the sitting term said "its last public
// hearing was" the report's day. So the docket's own station stands for
// that sitting here, and a report's station counts only where the docket
// has no Senate hearing of the bill at all (HB 183, HB 268-FN, HB 435). And
// it is never the hearing ahead (testifyButton): it has no time and no
// room, and a report is filed after the hearing it reports, so a day it
// gives that is still to come is not one the sign-in is open for.
const AMENDMENT_HEARING=new RegExp("^Public\\s+Hearing\\s+on\\s+(?:Proposed\\s+)?(Non-?\\s?Germane\\s+)?"
  +"(?:Amendment|AM)\\b([^:]*):\\s*(\\d{1,2})/(\\d{1,2})/(\\d{4})\\b\\s*"
  +"(?:(\\d{1,2}):(\\d{2})\\s*([ap])\\.?\\s?m\\b\\.?)?\\s*(.*)$","i");
const reportDated=s=>s.dated_by==="report";
// THE COMMITTEE THAT HAS THE BILL THAT DAY (the review of 26 October 2026).
// A hearing on a proposed amendment is held by the committee the bill is in
// on the day, which is often not the one it was first sent to: HB 71-FN,
// referred to Education Policy and Administration and, once the House had
// passed it, to Finance, whose hearing on 2025-0555h was at 1:00 pm on 17
// March 2025 in LOB 210-211, before Finance's executive session there at
// 1:15; HB 524-FN, referred to Health, Human Services and Elderly Affairs
// and then to Ways and Means, whose hearing on 2025-3021h was at 10:10 on 29
// October 2025 in GP 159, after Ways and Means' executive session there at
// 10:00. The pane named the first referral -- the record's house_committee
// -- and the House's form lists the bill under the committee holding the
// hearing. So, in order:
//  - the committee of a House meeting of the bill that day (an executive
//    session, a work session, a hearing; not the floor, whose station names
//    the chamber): where there are two, the one in the line's room, then the
//    one nearest its time;
//  - otherwise the later of the bill's last House referral on or before the
//    day -- "Referred to Finance 02/06/2025", "Introduced ... and referred
//    to ...", "Vacated and Referred to ...", a row citing the Senate's
//    journal or calendar (SJ, SC) being the Senate's, and "Rereferred to
//    Committee" or to interim study naming no committee -- and the committee
//    of its last House meeting before the day, the referral where both fall
//    on one day, since a committee meets on a bill before the House sends it
//    on;
//  - and only where neither exists, house_committee.
const REFERRED=/\b(?:re-?)?referred\s+to\s+(.+?)\s*(?:[(:;]|\b\d{1,2}\/\d{1,2}\/\d{4}\b|$)/i;
function testifyHouseCommittee(d,when,time,room){
  const flat=v=>String(v||"").replace(/\s+/g,"").toLowerCase();
  const mins=t=>{const m=/^(\d{1,2}):(\d{2})/.exec(String(t||""));return m?+m[1]*60+ +m[2]:null;};
  const meets=(d.stations||[]).filter(s=>s.body==="H"&&s.when
    &&String(s.committee||"").trim()&&!/^(house|senate)$/i.test(String(s.committee).trim()));
  const near=s=>(room&&flat(s.venue)===flat(room)?0:1e5)
    +(mins(s.time)==null||mins(time)==null?5e4:Math.abs(mins(s.time)-mins(time)));
  const that=meets.filter(s=>s.when===when).sort((a,b)=>near(a)-near(b))[0];
  if(that)return String(that.committee).trim();
  const met=meets.filter(s=>s.when<when).sort(testifyOrder).pop();
  let sent=null;
  (d.events||[]).forEach(e=>{
    if(e.called_off||/^S[JC]\b/.test(String(e.cite||"").trim())||!e.date||String(e.date)>when)return;
    const m=REFERRED.exec(String(e.text||"").trim());
    if(!m||/^(committee|interim study)\b/i.test(m[1]))return;
    if(!sent||String(e.date)>=sent.date)sent={date:String(e.date),committee:m[1].trim()};
  });
  if(sent&&(!met||sent.date>=met.when))return sent.committee;
  if(met)return String(met.committee).trim();
  return d.house_committee||"";
}
function testifyHearings(d){
  const heard=(d.stations||[]).filter(s=>/^(public )?hearing$/i.test(s.what||"")&&s.when
    &&!(reportDated(s)&&(s.docket_heard||[]).length));
  (d.events||[]).forEach(e=>{
    const m=AMENDMENT_HEARING.exec(String(e.text||"").trim());
    if(!m||e.called_off)return;
    const when=e.date_as_recorded&&e.date?String(e.date)
      :`${m[5]}-${m[3].padStart(2,"0")}-${m[4].padStart(2,"0")}`;
    const time=m[6]?`${String(+m[6]%12+(/p/i.test(m[8])?12:0)).padStart(2,"0")}:${m[7]}`:"";
    if(heard.some(s=>testifyBody(s)==="H"&&s.when===when&&String(s.time||"")===time))return;
    const room=String(m[9]||"").split(/\s*(?:[([;*]|https?:)/)[0].trim();
    const num=(/(?:\d{4}-)?\d{3,4}[a-z]+/i.exec(m[2])||[""])[0];
    heard.push({what:"public hearing",body:"H",when,time,committee:testifyHouseCommittee(d,when,time,room),
      venue:/^[A-Za-z0-9-][A-Za-z0-9 ,.'&-]{0,79}$/.test(room)?room:"",
      amendment:`a proposed ${m[1]?"non-germane ":""}amendment${num?` (${num})`:""}`,amendment_num:num});
  });
  return heard;
}
// Two hearings on one day are two (HB 1300 of 2026's at 10:00, and its
// hearing on 2026-0093h at 10:15): ordered by the day, then the time.
const testifyOrder=(a,b)=>a.when.localeCompare(b.when)||String(a.time||"").localeCompare(String(b.time||""));
// WHETHER A HEARING CAN STILL COME (the review of 25 October 2026). The
// rail's last mark alone said a bill had ended, and missed 46 of the sitting
// term's 2,243 on the preview of 26 October 2026: HR 17, which died on the
// table unheard (its rail ends in the pause), and HR 48, adopted, whose rail
// is empty, were told testimony
// "opens once a public hearing is scheduled"; CACRs, HCRs and an HR whose
// rails end in a stop not reached were told "It opens again" in another
// chamber after they had died, and an HR has no other chamber. So this asks
// what the site already asks to say a bill has stopped moving, in order:
//  - THE TERM HAS STOPPED SITTING: the record's session_over, the last
//    session day (build_site_v2 writes it on a bill that ran out of days),
//    is before New Hampshire's today. Nothing is scheduled after it.
//  - THE INDEX ROW'S KIND, the row of the record's own term, which
//    mountTestify chooses: "active" is a bill still moving, and every other
//    kind has ended -- became law ("law"), adopted ("adopted"), vetoed
//    ("veto"), held for interim study ("study"), or killed, withdrawn, died
//    on the table or with the session ("done"). build_site_v2's
//    bill_disposition gives it, and turns every "active" of the sitting term
//    to "done" once its session is over. Follow's shell.still_moving reads
//    the same kind, and keeps "study" followable too, since the study
//    committee's report is news; a bill sent to study is not heard again
//    this term, so here "active" alone is still moving.
//  - WHERE NO ROW SAYS, THE RAIL: still moving while a chamber's stop is the
//    ring of a bill there now ("h") and nothing on it is crossed. Not the
//    pause ("t"): it is a bill on the table while the session sits and the
//    chamber whose table a bill died on alike (journey_rail), and HR 17's
//    rail, [Introduced p, House t], is the same either way. A rail with no
//    stops, or none of those, has ended: a record with nothing to say it is
//    moving is not told testimony will open. The record's next_step is the
//    General Court's own words, and is not read for this.
function testifyMoving(d,b,today){
  if(d.session_over&&String(d.session_over)<today)return false;
  if(b&&b.kind)return b.kind==="active";
  const rail=((d.journey||{}).rail)||[];
  return !rail.some(s=>s.mark==="x")
    &&rail.some(s=>(s.stop==="House"||s.stop==="Senate")&&s.mark==="h");
}
// THE LIVE PANE IN THE PERSON'S WORDS (26 October 2026: "The testify button
// explanation is overly wordy. It could read more like: 'The public hearing
// on SB 123 is scheduled for Tuesday, April 2nd at 10:30AM in the
// Legislative Office Building Room 123. Public testimony is open until
// midnight the day of the hearing.' ----- 'To submit online testimony,
// choose the hearing date, committee, and bill number as shown below.'
// Submit Online Testimony (LINK) 'Tuesday, April 2nd, 2026' / 'House Housing
// Committee' / 'SB 123'"). Filled from the record: the day as the site
// writes days, with no ordinal; the time as it writes times (clock); the
// room in the words every room on the site is in (roomWords, S7), with
// "Room" only where those words have it; and a part the record lacks left
// out, never "at undefined". Then a rule; the sentence; the chamber's form
// as a button; and the three things the form asks for, each on a line of
// its own: the hearing's date in full, the committee with its chamber, and
// the bill's number as the index has it.
// THE COMMITTEE AS THE PERSON WROTE IT, "House Housing Committee": the
// chamber, the name the station carries (the name its page has, "House
// Housing", less the chamber), and "Committee". A name that says
// "Committee" itself takes only the chamber -- "House Special Committee on
// Housing", not "... on Housing Committee", as cmteTitle has it -- and one
// that already names its chamber is not given it twice.
const testifyCommittee=(house,c)=>{
  const n=String(c||"").trim();
  if(!n)return "";
  const named=n.toLowerCase().startsWith(house.toLowerCase()+" ")?n:`${house} ${n}`;
  return /\bcommittee\b/i.test(n)?named:`${named} Committee`;
};
function testifyButton(d,b,now=new Date()){
  if(!d||!d.term)return "";
  if(d.term!==sittingTerm(now))return "";
  const today=nhDay(now);
  // EACH CHAMBER'S WORD (the audit of 25 October 2026, M2): the House's
  // hearings are "public hearing" and the Senate's "hearing", and the box
  // read the House's alone -- SB 406 of 2026, heard on 13 January, said
  // testimony had not opened. workers/follow reads both the same way. And a
  // hearing on a proposed amendment (testifyHearings).
  const heard=testifyHearings(d);
  const moving=testifyMoving(d,b,today);
  // A hearing still to come, for a bill that can still be heard: a bill that
  // has stopped moving keeps no hearing ahead, whatever a station says; and
  // never a day a committee's report gives (ONE SITTING WITH TWO DATES, at
  // testifyHearings).
  const next=moving?heard.filter(s=>s.when>=today&&!reportDated(s)).sort(testifyOrder)[0]:null;
  const bill=b&&b.n?String(b.n):"";
  // The words beside the drawing are in a span of their own, as Report's
  // are, so the button's gap does not part them.
  const button=(cls,words)=>`<details class="testify ${cls}"><summary>${icon("testify")}<span>${words}</span></summary>`;
  if(next){
    const body=testifyBody(next);
    const [house,url]=TESTIFY_FORMS[body];
    const room=next.venue?roomWords(next.venue):"";
    // THE COMMITTEE WHERE THE STATION NAMES NONE (the review of 26 October
    // 2026): the pane says to choose the committee "as shown below", and
    // three hearings of 2025 -- HB 154's and HB 382's in the Senate, HR 18's
    // in the House -- showed none, where the record names the committee of
    // the bill's referral in that chamber (house_committee, senate_committee),
    // the name the bill's page gives it -- in the House, the committee that
    // has the bill that day (testifyHouseCommittee), which is house_committee
    // where nothing on the record says it has moved.
    const cmte=testifyCommittee(house,next.committee||(body==="H"
      ?testifyHouseCommittee(d,next.when,next.time,next.venue):d.senate_committee));
    // A hearing on a proposed amendment says so (testifyHearings): the bill
    // has had its own, and this one is on "a proposed non-germane amendment
    // (2026-0422h)", in the words the bill's Summary uses for it.
    // ITS NUMBER OPENS IT (the person, 26 October 2026: "the amendment number
    // should link to open it on the bill text tab"): the Bill Text tab, at
    // that amendment, open (AMENDMENT_HASH). Where the record says the tab
    // has amendments to open (namd); otherwise the number is words alone.
    const num=next.amendment_num||"", yr=d.year||(b&&b.year), bid=d.id||(b&&b.id);
    const amd=!next.amendment?"":num&&d.namd&&yr&&bid&&AMENDMENT_HASH.test("amendment-"+num)
      ?esc(next.amendment).replace(`(${esc(num)})`,
        `(<a href="${esc(amendmentHref(yr,bid,num))}">${esc(num)}</a>)`)
      :esc(next.amendment);
    const on=(amd?amd+" to ":"")+(bill?esc(bill):"this bill");
    return button("tlive",`Testify<span class="tuntil"> until ${esc(dateWords(next.when,"short"))}</span>`)
      +`<div class="testifypane">
      <p>The public hearing on ${on} is scheduled for ${esc(dateWords(next.when,"day"))}${
        next.time?` at ${esc(clock(next.time))}`:""}${room?` in ${esc(room)}`:""}. Public testimony is open
      until midnight the day of the hearing.</p>
      <hr class="trule">
      <p>To submit online testimony, choose the hearing date, committee, and bill number as shown below.</p>
      <p><a class="tgo" href="${esc(url)}" target="_blank" rel="noopener">Submit Online Testimony</a></p>
      <ul class="tvals"><li>${esc(dateWords(next.when,"long"))}</li>${cmte?`<li>${esc(cmte)}</li>`:""}${
        bill?`<li>${esc(bill)}</li>`:""}</ul></div></details>`;
  }
  // Only a hearing whose day has gone is one that has passed.
  const past=heard.filter(s=>s.when<today).sort((a,b)=>testifyOrder(b,a));
  const last=past[0];
  // "IT OPENS AGAIN" ONLY WHERE IT CAN: a bill still moving (testifyMoving),
  // heard by one chamber alone -- CACR 13 of 2026, heard in both, was told it
  // opens again in the other -- whose rail has the other chamber's stop and
  // that chamber has not yet decided it. A resolution of one chamber has no
  // such stop: an HR or an SR is never told of another chamber.
  const rail=((d.journey||{}).rail)||[];
  const bodies=new Set(past.map(testifyBody));
  const other=last&&bodies.size===1
    &&rail.find(s=>s.stop===(testifyBody(last)==="H"?"Senate":"House"));
  const again=moving&&!!other&&/^[ht-]$/.test(other.mark||"");
  // ENDED WITHOUT A HEARING (the review of 25 October 2026): HR 2 of 2025,
  // adopted by the House the day it was introduced, and HB 1786 of 2026,
  // whose hearing was cancelled and which died on the table, were never
  // heard, and the pane told their readers testimony "opens once a public
  // hearing is scheduled", which will not happen. It did not open, and the
  // pane says so. The button stays, greyed, since every bill of the sitting
  // term has one (the person, 22 October 2026: "Bills that are from the
  // current year should have the testimony box but greyed out").
  // CLOSED, IN THE OWNER'S WORDS (6 November 2026): "Online testimony
  // submissions for this bill have closed as of January 13, 2026." -- the
  // last past hearing's day, the month in full -- and, only where it can
  // open again (`again`, unchanged), the plain reason, naming the other
  // chamber: "They may open again if the bill goes to the Senate and the
  // Senate holds its own public hearing." Where it is already there, unheard
  // ("h") or tabled ("t") (the owner, 6 November 2026): "They may open again
  // if the Senate holds its own public hearing."
  const there=other&&("the "+other.stop);
  const arrived=again&&/^[ht]$/.test(other.mark||"");
  const why=last
    ?`Online testimony submissions for this bill have closed as of ${esc(dateWords(last.when,"full"))}.`
      +(!again?"":arrived?` They may open again if ${there} holds its own public hearing.`
        :` They may open again if the bill goes to ${there} and ${there} holds its own public hearing.`)
    :moving?"Online testimony has not opened yet: it opens once a public hearing is scheduled."
    :"Online testimony did not open for this bill: it had no public hearing.";
  const shut=last?", closed":moving?", not open yet":", not open: no hearing was held";
  return button("toff",`Testify<span class="sr">${shut}</span>`)
    +`<div class="testifypane"><p>${why}</p></div></details>`;
}
// IN THE ROW AFTER FOLLOW (25 October 2026), or after Cite where a bill has
// none (a bill whose story has ended has no feed): Follow and Testify are the two ways
// to take part in what the bill does next, and Print, Share and Report a
// problem are about this page. Drawn once the bill's record has come, since
// what it says is the record's, and drawn again only when that changes, so
// a pane the reader opened is not shut under them by the next redraw.
// THE ROW OF THE RECORD'S OWN TERM (the review of 25 October 2026): a bill
// number is unique only within its term, and focusActions found HB 104's row
// with no term, so the 2025-2026 bill opened from the search said "then the
// bill, HB 104", the 2023-2024 bill's label, and the next redraw, with the
// right one, drew the button again and shut the pane. The label is the
// row's of the record's term, as Print takes it, whatever row a caller has.
// THIS IS THE ONE PLACE THAT DECIDES THE ROW (the review of 25 October
// 2026): render() and focusActions hand in what they have, and the row of
// the record's own term is chosen here, its label and its kind (whether the
// bill is still moving, testifyMoving) with it. A caller's row is used only
// where the index has none for that term.
const TESTIFY_DRAWN=new WeakMap();
function mountTestify(b,d){
  const acts=document.getElementById("pageacts");
  if(!acts)return;
  if(b&&d&&d.term)b=IDX.find(x=>x.id===b.id&&x.term===d.term)||b;
  const html=b&&d&&!d._error?testifyButton(d,b):"";
  const had=acts.querySelector(".testifyin");
  if(had&&TESTIFY_DRAWN.get(had)===html)return;
  if(had)had.remove();
  if(!html)return;
  const box=document.createElement("div");
  // The open one stands out on a phone too: a row of its own (app.css).
  box.className=html.includes('class="testify tlive"')?"testifyin tliverow":"testifyin";
  box.innerHTML=html;
  TESTIFY_DRAWN.set(box,html);
  const after=acts.querySelector("#followbox")||acts.querySelector(".pcite");
  acts.insertBefore(box,after&&after.parentNode===acts?after.nextSibling:acts.firstChild);
}
function renderSummary(b,d,rsa){
  const S=[];
  // THE SPONSORS FIRST (the owner, 19 November 2026): what was the Sponsors
  // tab, its chips as they were, above the analysis. A bill with none says so
  // here, unless it is of an earlier term, whose About This Record says it.
  const spn=(d&&d.sponsors||[]).length;
  if(spn||!(d&&d.archived))S.push(section("Sponsors",renderSponsors(b,d||{}),"sponsors"));
  const note=d&&d.bill_note;
  if(note&&note.note)S.push(section(titleWords(note.label||"About this bill"),
    `<div class="anbox billnote"><div class="antext">${esc(note.note)}</div></div>
     <p class="src">Written by Granite Record, not quoted from the General Court. It
     describes what this bill number is for, which its title does not say.</p>`,"about"));
  const an=((d.billtext||{}).analysis||"").trim();
  if(an)S.push(section("Official Legislative Analysis",
    `<div class="anbox" data-an="1"><div class="antext" translate="no">${rsa?rsa(esc(an)):esc(an)}</div></div>
     <p class="src">Source: ${gcSource(d)}</p>${rsaLine(d)}`,"analysis"));
  const gl=glossPass();
  const jl=journeyList(b,d,gl);
  if(jl)S.push(section("How It Got Here",jl+(an?"":`<p class="src">Source: ${gcSource(d)}</p>${rsaLine(d)}`),"journey"));
  else if(!an&&(d.docket_url||rsaChapters(d).length||(d.constitution||[]).length))
    S.push(section("Source",`<p class="src">Source: ${gcSource(d)}</p>${rsaLine(d)}`,"source"));
  // ONE HOW IT ENDED (17 October 2026). The story's own closing stage and
  // the session's end were two sections under the same heading; the notes
  // join the stage where the story has one. And what this site holds of an
  // earlier term is not how the bill ended -- a law read it under that
  // heading -- so it has a section of its own.
  const ending=endNote(d);
  let ended=false;
  if(d.stages&&d.stages.length)d.stages.forEach(st=>{
    const here=!!ending&&st.label==="How It Ended";
    if(here)ended=true;
    S.push(section(st.label||"The Story",
    `<p class="story">${gl(voteLinks(storyPeople(esc(st.text),d),b,d))}</p>${(st.notes||[]).map(n=>`<p class="note">${esc(n)}</p>`).join("")}${here?ending:""}`));});
  else if(d.narrative)S.push(section("The Story",`<p class="story">${gl(voteLinks(storyPeople(esc(d.narrative),d),b,d))}</p>`));
  if(ending&&!ended)S.push(section("How It Ended",ending,"ending"));
  const kept=archivedNote(d);
  if(kept)S.push(section("About This Record",kept,"about-record"));
  // NO RELATED BILLS ON THE SUMMARY (Alice, 9 November 2026): it repeated the
  // History tab, which every bill has now. relatedSaid stays for that tab.
  if((d.events||[]).length)S.push(section("The Docket",`<details class="docket"><summary><span class="caret"></span>Show the docket&rsquo;s ${
      d.events.filter(e=>!e.cancelled).length} lines</summary>
      <p class="note">Every action the General Court recorded, in its own words
        and in the order it recorded them.</p>
      <ul class="tl">${d.events.filter(e=>!e.cancelled).map(e=>`<li>
        <span class="d">${e.date?esc(dateWords(e.date)):""}</span>
        <span class="w"><span translate="no">${esc(e.text||"")}</span>${e.cite?` <span class="cite">${
          e.cite_url?`<a href="${esc(e.cite_url)}" target="_blank"
          rel="noopener">${esc(e.cite)}</a>`:esc(e.cite)}</span>`:""}${
          signins(e.testimony)}${
          /* a date put right by hand: the line above still says the other */
          e.date_note?`<span class="note tldate">${esc(e.date_note)}</span>`:""}${
          /* a row the docket files under the wrong bill, and its twin */
          e.row_note?`<span class="note tldate">${esc(e.row_note)}</span>`:""}</span>
        </li>`).join("")}</ul></details>`,"docket"));
  return `${d._error?`<div class="loaderr"><b>This bill's detail did not
    load.</b><span>${esc(d._error)}</span></div>`:""}${
    (d.notes||[]).map(x=>`<p class="note">${esc(x)}</p>`).join("")}<div class="w4s">${S.join("")}</div>`;
}

// THE DAY A VOTE WAS TAKEN LEADS TO THE DAY. A roll call on a bill and a row
// of a member's votes both name the date and the chamber, and each chamber's
// sitting has a page -- /session/H/2026-05-21 -- that nothing here led to:
// of 1,563 sitting pages, 62 had a link from anything but the sitting beside
// them (the audit of 2 October 2026, B3). The date is the link.
//
// ONLY WHERE THE PAGE WAS BUILT. session/days.json is written by the step
// that writes the pages (build_session_pages.py) and lists them; a date not
// on it stays text, because a vote can be on record for a day the sittings
// do not hold and a link to nothing is worse than no link. Asked for once,
// when the first vote is drawn, and the view is drawn again when it lands.
//
// AND THE ROLL CALLS EACH PAGE DRAWS UNDER THEIR OWN ANCHOR (the preview
// check of 25 October 2026): `rc`, {H: {"2025-H-1": "2025-01-08"}, S: {...}},
// read by the same step off the pages it wrote. A page gives "#rc-<key>" only
// to a roll call it draws on no bill, and it may draw one the roll-call file
// files under no bill on a bill's card instead (the House's 2022-H-4 and -5,
// under HB 50 on 5 January 2022), or on a day other than the file's; a link
// to "#rc-<key>" made without asking opened those days at their top.
let SITDAYS=null;       // null while unasked, {} while asked, {H:Set,S:Set,rc}
function needSittings(){
  if(SITDAYS)return;
  SITDAYS={};
  fetch(DATA("session/days.json"))
    .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
    .then(j=>{SITDAYS={H:new Set(j.H||[]),S:new Set(j.S||[]),rc:j.rc||{}};repaint();})
    .catch(()=>{});    // the dates stay text, which is what they were
}
// The day whose page draws roll call `k` ("2025-H-1") of chamber `body` under
// its own anchor, "#rc-2025-H-1", or "" where no page does.
function rollcallDay(body,k){
  const m=SITDAYS&&SITDAYS.rc&&SITDAYS.rc[body];
  const d=m&&k&&Object.prototype.hasOwnProperty.call(m,k)?String(m[k]):"";
  return d&&SITDAYS[body]&&SITDAYS[body].has(d)?d:"";
}
// `text` as a link to that chamber's sitting of `iso` (2026-05-21), or as it
// came where the sitting has no page. `text` is already escaped.
//
// AT THE BILL (the audit of 25 October 2026, M1): a vote's date opened the
// day's top, and HB 282 was some 36,700px below it on a phone. `bill` is the
// card's id on the page, as build_session_pages.card_anchor gives it --
// "HB282", the number upper-cased with anything else dropped -- and the
// address carries no ".html", which cost a redirect.
//
// AT THE ROLL CALL, WHERE THE PAGE DRAWS IT ON ITS OWN (the preview check of
// 25 October 2026): `k`, the roll call's key, leads to "#rc-<key>" where
// that day's page draws it under that id (rollcallDay), before the bill's
// card. The caller passes no `bill` for a vote on a rule or a code
// ("HRULE64", "HR", "LATE"): no card has that id, and the House's Rule 64
// vote of 8 January 2025 opened its day at the top.
function sittingLink(body,iso,text,bill,k){
  needSittings();
  const has=SITDAYS&&SITDAYS[body]&&SITDAYS[body].has(String(iso||""));
  const at=k&&has&&rollcallDay(body,k)===String(iso)?"rc-"+String(k)
    : String(bill||"").toUpperCase().replace(/[^A-Z0-9]/g,"");
  return has?`<a href="session/${esc(body)}/${esc(iso)}${at?"#"+esc(at):""}">${text}</a>`:text;
}

// What a voice or a division vote's card says of it, under its head.
const NO_NAMES="No record of how each member voted.";
function renderVotes(b,d){
  // NOTHING ABOVE THE VOTES. This tab opened, in turn, by explaining the roll
  // call file and the presiding officer's tie-breaking vote; then with one
  // line saying that roll calls record individual legislators where voice and
  // division votes do not; then with the bill's own count of how many of its
  // floor votes went unrecorded. All three are gone, and the last two for the
  // same reason: every card below now says what its own vote was. A reader
  // who wants to know how many were unrecorded can count the cards that say
  // so, and each one says it where they are looking.
  //
  // IN ONE LINE (the audit of 25 October 2026, S1). Each such card said it in
  // two sentences -- "Decided on a voice vote. There is no count and no record
  // of how individual members voted", and a division's count but not its
  // members -- under a head that already names the kind of vote, beside a ring
  // that already is the count or with no ring at all. What the head and the
  // ring do not say is the line: "No record of how each member voted."
  //
  // d.vote_note is still built and still published in the record; it is only
  // no longer drawn here. build_site_v2.vote_note_for and narrative.py are
  // untouched, so nothing downstream of them changes and the sentence is one
  // line away if it is wanted back.
  const VOTE_IDS=voteAnchors(d);
  return ((d.rollcalls||[]).length?d.rollcalls.map((rc,i)=>{
    const vk=rc.vote_kind||"RC";
    let body;
    if(vk==="RC"){
      body=donut(b.id,i,rc)+fullRecord(b.id,i,rc);
    }else if(vk==="DV"&&rc.yeas!=null){
      // A division vote is counted but anonymous. Chart the split; there is no
      // member list to show, and saying so is the point.
      body=simpleDonut(rc,b.id,i)+`<p class="note" style="margin-top:11px">${NO_NAMES}</p>`;
    }else if(rc.wo){
      // BY THE JOURNAL'S OWN WORDS (the owner, 23 October 2026): a motion the
      // Journal says was carried "without objection" was put to no vote.
      body=`<p class="note" style="margin-top:6px">Adopted without objection: no member
        objected, so no vote was taken and nobody was counted.</p>`;
    }else{
      body=`<p class="note" style="margin-top:6px">${NO_NAMES}</p>`;
    }
    // THE APPROVED VOTE WORDS (the person, 8 October 2026; votes.json): the
    // motion's own name with only OTP, OTPA, ITL and IS abbreviated and a
    // plain gloss -- "Inexpedient to Legislate (ITL, Kill the bill)" -- and
    // the chip saying what the vote did, coloured by the vote's outcome,
    // "Motion Passed: Bill Killed". The key is the build's (motions.py, rc.mk);
    // a record built before it has none and its question stands as the head.
    // The record's own words go on a small line under the head where they
    // differ from it by more than case and an amendment number (rc.mrec).
    return `<section class="rc" id="${VOTE_IDS[i]}">
      <div class="rchead"><h2 class="rcq">${voteHead(rc.mk,rc.question,rc.mf)}${
        rc.amendment?` <span class="ramd">${esc(rc.amendment)}</span>`:""}</h2>
      <span class="rcd">${sittingLink(rc.body==="H"?"H":"S",rc.date,dateWords(rc.date),b.id)} · ${
        rc.body==="H"?"House":"Senate"}${rc.wo?" · Without Objection":
          AVK[vk]?` · ${termMark(vk,AVK[vk])}`:""}</span>
      ${voteChip(rc.mk||"",rc.passed,b.id,rc.mf)}</div>
      ${rc.ruling?`<p class="rcrul">${esc(rc.ruling)}</p>`:""}
      ${rc.mrec?`<p class="rcrec">In the record: <span translate="no">${esc(rc.mrec)}</span></p>`:""}
      ${rc.mover?`<p class="rcby">Moved by ${rc.mover_m?personLink(rc.mover_m):esc(rc.mover)}</p>`:""}
      ${rc.threshold_note?`<p class="note" style="margin:6px 0 0">${esc(rc.threshold_note)}</p>`:""}
      ${rc.outcome_conflict?`<p class="note" style="margin:6px 0 0">${esc(rc.outcome_conflict)}</p>`:""}
      ${body}</section>`;}).join("")
      // THE VOTES PAGE, from a bill with roll calls on it (the owner, 12
      // November 2026): the same bill number, in its own term. ONLY WHERE
      // THERE IS A ROLL CALL (the review of 14 November 2026): /votes holds
      // roll calls alone, and some 9,400 bills voted only by voice or
      // division were led to a page with none of them. The number bare, as
      // /votes reads one: "HB 2-FN-A-L" is HB 2.
      +(d.rollcalls.some(rc=>(rc.vote_kind||"RC")==="RC")
        ?`<p class="src vlink"><a href="${esc(votesLinkFor("",votesBillWords(b.id),b.term||termOfYear(b.year)))}">Find these votes on the votes page</a></p>`:"")
    // BEFORE 1999 THE TAB SAYS WHY IT IS EMPTY (the audit of 25 October
    // 2026, S4): HB 200 of 1997's Summary said the House killed it "on a roll
    // call 286-57" and this tab "No roll call votes on this bill". The named
    // votes this site reads -- the General Court's roll-call files -- begin
    // with the 1999 session; the docket's tallies are in How It Got Here.
    // Said here, where the question is asked, and no longer in About This
    // Record (archivedNote). "Here", because the votes did not begin then:
    // the printed journals of 1997 name who voted, the Senate's its own.
    :termStartOf(d)&&termStartOf(d)<1999
      ?`<p class="note">Named roll calls here begin in 1999. The tallies the
        docket recorded are in How It Got Here; the printed House and Senate
        Journals name who voted.</p>`
    :`<p class="note">No roll call votes on this bill.</p>`)+ballotCard(d);
}

// THE VOTERS' VOTE ON A CONSTITUTIONAL AMENDMENT (the person, 5 October 2026:
// "an additional vote on those CACRs for the public vote with the 2/3
// indicator"). After the chambers' votes, the statewide one at the general
// election, from d.ballot (build_site_v2.ballot_card, out of the hand-made
// ballot_results.json), and the day of it where it is still to come.
//
// THE SAME RING AS EVERY OTHER COUNTED VOTE, with the mark at two thirds of
// the votes cast -- not at a majority, which is the whole point of it: CACR 6
// of 2024 won 65.6% and was not ratified, and a majority mark would call that
// a win. Whether it was ratified is the build's answer (ratified()), drawn
// here, not worked out again.
//
// THE COUNTS ARE NOT IN THE RING. They run to six figures with their
// separators -- "452,307" -- and the hole in the ring is 92px across: a roll
// call's "309 | 9" fits there and "452,307 | 237,221" does not. The yes share
// goes there instead, and the counts in full go in the legend beside it,
// which drops under the ring on a phone and does not wrap a number.
const thou=n=>Number(n||0).toLocaleString("en-US");
const share=(n,of)=>`${(of?100*n/of:0).toFixed(1)}%`;
function ballotRing(y,n,won){
  const tot=(y+n)||1;
  const R=60,C=2*Math.PI*R,GAP=32,gap=C*GAP/360,avail=C-gap-C*1.4/360;  // a hair's break where Yes meets No (ring 1c)
  const seg=(len,fill,sideWon)=>`<circle r="${R}" cx="86" cy="86" fill="none" stroke="${fill}"
    stroke-width="24" opacity="${sideWon?1:.75}"
    stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${-gap/2}"></circle>`;
  // Two thirds of the way round from the gap: where the yes side had to reach.
  const a=(180+GAP/2+(360-GAP)*2/3)*Math.PI/180;
  const said=`The voters: ${thou(y)} yes to ${thou(n)} no, ${share(y,tot)} yes, `
    +`needing two thirds; ${won?"ratified":"not ratified"}`;
  const check=wonMark();
  return `<div class="votewrap"><svg class="donut" viewBox="0 0 172 206" width="172" height="206"
    role="img" aria-label="${esc(said)}">
    <g transform="rotate(90 86 86)">${seg(avail*y/tot,"var(--yes)",won)}</g>
    <g transform="translate(172,0) scale(-1,1)"><g transform="rotate(90 86 86)">${seg(avail*n/tot,"var(--no)",!won)}</g></g>
    ${marker(a,R,"Two thirds of the votes cast","")}${yn(GAP,R,won)}
    <text x="86" y="89" text-anchor="middle" font-size="18" font-weight="600"
      style="font-family:var(--serif)" fill="var(--ink)" font-variant-numeric="tabular-nums">${share(y,tot)}</text>
    <text x="86" y="107" text-anchor="middle" font-size="14" fill="var(--ink-2)">yes</text></svg>
    <div class="legend">
      <div class="lrow"><span class="sw" style="background:var(--yes)"></span>
        <span>Yes${won?check:""}</span><span class="c">${thou(y)} · ${share(y,tot)}</span></div>
      <div class="lrow"><span class="sw" style="background:var(--no)"></span>
        <span>No${won?"":check}</span><span class="c">${thou(n)} · ${share(n,tot)}</span></div>
    </div></div>`;
}
// The votes the tab draws: the chambers' and, on a CACR, the voters'.
const votesDrawn=d=>(d.rollcalls||[]).length+(d.ballot&&!d.ballot.pending?1:0);
// ONE DATE STYLE IN THE CARD, the head's: "Nov 3, 2026" over "The vote is on
// 3 November 2026" and "read 5 October 2026" was two in four lines (the
// review of 5 October 2026), and the head's is every vote card's above it.
//
// WHOSE COUNT IT IS COMES WITH THE RECORD (v.by, v.cite, v.whose, from the
// row's own source: build_site_v2.ballot_card, ballot_source.py). This said
// "Ballotpedia, List of New Hampshire ballot measures" on every card, and on
// 7 October 2026 the person made the Secretary of State the source of every
// amendment the voters have decided -- "Secretary of State, Manual for the
// General Court 1993, p. 442 (NHPR's scan)" -- keeping Ballotpedia for the
// one still to come. A label in parentheses is the file's description of
// how the source lists it, "(the only question; unnumbered)" as the reading
// of 7 October 2026 wrote it, not its words, and is said in the card's own
// sentence, without quotation marks and with a comma for its semicolon:
// "which lists it as the only question, unnumbered".
function ballotCard(d){
  const v=d.ballot;
  if(!v)return "";
  const head=res=>`<div class="rchead"><h2 class="rcq">The voters</h2>
      <span class="rcd">${esc(dateWords(v.date))} · State general election</span>${res}</div>`;
  const lab=String(v.label||"");
  const listed=/^\(.*\)$/.test(lab)?esc(lab.slice(1,-1).replace(/;\s*/g,", "))
    :`&ldquo;${esc(lab)}&rdquo;`;
  const cited=[v.by,v.cite].filter(Boolean).join(", ")||v.source;
  const src=`<p class="src">Source: <a href="${esc(v.source)}" target="_blank"
      rel="noopener">${esc(cited)}</a>, read
      ${esc(dateWords(v.read))}, which lists it as ${listed}.</p>`;
  // An election to come, and one past whose count is not in the file yet
  // (v.over, build_site_v2.ballot_card): the status says "went to the voters"
  // the day after, and so does this.
  if(v.pending)return `<section class="rc ballot" id="vote-ballot">${head("")}
    <p class="bout">${v.over
      ?`The vote was on ${esc(dateWords(v.date))}; its count is not recorded here yet.`
      :`The vote is on ${esc(dateWords(v.date))}.`}</p>
    <p class="note">This ${v.over?"was":"is"} the statewide public vote, at the general
      election. An amendment to the constitution needs two thirds of the votes cast
      on it.</p>
    ${src}</section>`;
  const y=v.yes,n=v.no,tot=y+n,won=!!v.ratified;
  const word=won?"Ratified":"Not ratified";
  const how=3*y===2*tot?"exactly":won?"more than":"short of";
  return `<section class="rc ballot" id="vote-ballot">${head(chip(won?"Ratified":"Not Ratified",`rcres ${won?"pass":"fail"}`))}
    <p class="bout">${word}: ${share(y,tot)} voted yes, ${how} the two thirds it needed.</p>
    <p class="note">This was the statewide public vote, at the general election. An
      amendment to the constitution needs two thirds of the votes cast on it: the
      mark on the ring.</p>
    ${ballotRing(y,n,won)}
    ${v.docket?`<p class="note">${docketDiffers(v)}</p>`:""}
    ${src}</section>`;
}
// WHICH FIGURE DIFFERS, AND WHOSE THE CARD'S ARE. "The docket records this vote
// as 249,759 to 204,475" under "No 204,457" left a transposition for the reader
// to find and did not say which of the two the card drew (the review of 5
// October 2026). Whose they are is the row's source (v.whose): "the Secretary
// of State's" under CACR 22 of 1998, whose docket says 159,439 against the
// Manual's 169,439.
function docketDiffers(v){
  const [dy,dn]=v.docket;
  const side=(got,ours,word)=>got===ours?"":`${thou(got)} votes ${word}, not ${thou(ours)}`;
  const said=[side(dy,v.yes,"for"),side(dn,v.no,"against")].filter(Boolean).join(", and ");
  return `The General Court&#39;s docket records ${said}. The counts above are
      ${esc(v.whose||"its source's")}, and How it got here gives the docket&#39;s.`;
}

// What a player's frame is titled: "Recording of HB 2 - House Finance Public
// Hearing, Mar 12, 2025". `when` is the record's own date, drawn as every
// other date here is where it is one and as it came where it is not.
function recTitle(what,when){
  const day=/^\d{4}-\d\d-\d\d$/.test(String(when||""))?dateWords(when):String(when||"");
  return `Recording of ${what}${day?`, ${day}`:""}`;
}

// "HB 1123 - House Labor Public Hearing", "HB 1123 - Senate Floor Debate".
// Only the kind is title-cased: a committee's name is the General Court's own
// and "Labor, Industrial And Rehabilitative Services" is not how it spells it.
const CHWORD={H:"House",S:"Senate"};
// The kind through kindTitle, which keeps a small word after the first small
// (the cohesion audit's P-5, 30 October 2026): capitalising every word made a
// 1995 hearing "Committee Of Conference".
// A floor row's "committee" is already the chamber, so it is not repeated.
function hearingWhere(s){
  const cmte=(s.committee||"").trim();
  const ch=CHWORD[s.body]||"";
  return (!cmte||cmte===ch)?ch:(ch?`${ch} ${cmte}`:cmte);
}
function stationTitle(b,s){
  const kind=s.what?kindTitle(s.what):"";
  const where=hearingWhere(s);
  return [b.n||b.id, [where,kind].filter(Boolean).join(" ")]
    .filter(Boolean).join(" - ");
}

// THE SENATE COMMITTEE'S OWN REPORT OF THE HEARING, on the Reports tab among
// the committees' reports (19 November 2026; it was under the hearing's video).
//
// A Senate committee's aide writes up every public hearing: who came, which
// side each took, and what each said. The person decided on 24 September that
// these are shown as the Senate published them, members of the public named,
// with the points the report attributes to each. (The online sign-in system is
// a different source and stays counts-only -- signins() above.) Closed by
// default: the station is about the recording, and a report can run to forty
// speakers.
//
// Nothing here rewords a point. senate_hearing_reports.py splits a report into
// speakers only where every line could be placed with confidence; where it
// could not, a section arrives as `text`, the paragraphs and bullets in the
// order the report has them, and is drawn that way with no name attached to
// anything.
const HR_SIDE={support:"for",oppose:"against",neutral:"neutral"};
function hrPoint(p){
  if(typeof p==="string")return `<li>${esc(p)}</li>`;
  return `<li>${esc(p.t||"")}${(p.sub||[]).length
    ?`<ul>${p.sub.map(hrPoint).join("")}</ul>`:""}</li>`;
}
function hrSpeaker(sp){
  // A legislator the build resolved to a member is drawn with the chip
  // everyone else on the site is drawn with, carrying the report's own words
  // for them; the rest of the line -- "Prime Sponsor", a district -- follows
  // as the report printed it. Everybody else is the report's text.
  let name=esc(sp.who||"");
  const m=sp.member;
  if(m&&m.label&&String(sp.who||"").startsWith(m.label)){
    const rest=String(sp.who).slice(m.label.length).replace(/^[\s,:;]+/,"");
    name=`${pchip(m)}${rest?`<span class="hrrole">${esc(rest)}</span>`:""}`;
  }
  const also=(sp.also||[]).map(a=>`<span class="hrrole">${esc(a)}</span>`).join("");
  const pts=sp.points||[];
  // h4 UNDER THE SECTION'S h3 (19 November 2026): the report is on the
  // Reports tab, under its committee's h2, and the outline keeps to four
  // levels (no h5 on the site).
  return `<section class="hrsp"><h4>${name}${also}</h4>${pts.length
    ?`<ul class="hrpts">${pts.map(hrPoint).join("")}</ul>`
    :`<p class="hrnone">The report lists no points under this name.</p>`}</section>`;
}
function hrPlain(items){
  // The unsplit case: paragraphs as paragraphs, bullets as bullets.
  return items.map(x=>typeof x==="string"?`<p class="hrpara">${esc(x)}</p>`
    :`<ul class="hrpts">${(x.li||[]).map(hrPoint).join("")}</ul>`).join("");
}
// `video` is whether the station drew a recording above the report: fifteen
// Senate hearings with a report have none, and there the page said "the
// recording above is the hearing itself" over "No recording matched".
function hearingReport(r,video){
  if(!r)return "";
  const secs=r.sections||[];
  // The size of it, in the summary, so a reader knows what opening it costs.
  const bySide={};let spoke=0,plain=false;
  secs.forEach(s=>{
    if(s.text){if(s.text.length)plain=true;return;}
    const n=(s.speakers||[]).length;spoke+=n;
    if(HR_SIDE[s.side])bySide[s.side]=(bySide[s.side]||0)+n;
  });
  const sides=["support","oppose","neutral"].filter(k=>bySide[k])
    .map(k=>`${bySide[k]} ${HR_SIDE[k]}`);
  const size=spoke
    ?`${spoke} spoke${sides.length&&Object.values(bySide).reduce((a,b)=>a+b,0)===spoke
      ?`: ${sides.join(", ")}`:""}`
    :(plain?"the committee’s summary of the testimony":"no testimony summarized");
  const cmte=r.committee||"Senate committee";
  const when=r.completed||r.heard;
  const fact=(k,v)=>v?`<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`:"";
  const times=[r.opened&&`opened ${r.opened}`,r.closed&&`closed ${r.closed}`]
    .filter(Boolean).join(", ");
  const pos=(r.positions||[]).filter(p=>p[1]);
  // A committee can hear an amendment on its own after the bill, the same
  // afternoon, and report it separately; the summary says which this is.
  const amd=r.subject?/AMENDMENT\s*#?\s*([0-9A-Za-z-]+)/i.exec(r.subject):null;
  return `<details class="hrep"><summary><span class="caret"></span><span>
    <b>The committee’s hearing report${amd?` on amendment ${esc(amd[1])}`:""}</b>
    · ${esc(size)}</span></summary>
    <div class="hrb">
    ${r.subject?`<p class="hrsrc"><b>Heard:</b> ${esc(r.subject)}</p>`:""}
    <p class="hrsrc">What each person said, as summarized in the ${esc(cmte)}’s
      hearing report${when?` of ${dateWords(when)}`:""}. The report is the committee
      staff’s summary of the hearing, not a transcript${video
        ?"; the recording of the hearing is on the Videos tab":""}.</p>
    <dl class="hrfacts">${fact("Hearing",times?`${dateWords(r.heard)}, ${times}`:dateWords(r.heard))}${
      fact("Members present",r.present)}${fact("Members absent",r.absent)}</dl>
    ${pos.length?`<h3>Who took a position</h3><dl class="hrfacts">${
      pos.map(p=>fact(p[0],p[1])).join("")}</dl>`:""}
    ${secs.map(s=>{
      const body=s.text?hrPlain(s.text)
        :(s.speakers||[]).map(hrSpeaker).join("");
      const empty=!(s.text||[]).length&&!(s.speakers||[]).length;
      return `<h3>${esc(s.label)}</h3>${s.text&&s.text.length
        ?`<p class="hrnote">This section is shown as the report sets it out,
          because the report does not make clear who said which part.</p>`:""}${
        empty?`<p class="hrnone">${esc(s.note||"None.")}</p>`:body}`;}).join("")}
    </div></details>`;
}

// A SITTING WHOSE RECORDING NEVER NAMES ITS BILL (17 October 2026, the
// wording the person approved). segment_markers found the bill nowhere in the
// recording's captions, by number or by title, so there is no moment to mark
// and none is coming; the page says that rather than "ongoing work". It names
// the captions because they are what was read: a chair may have said a number
// the captions lost, and "the recording does not name it" would then be false.
// The note under the card's one button, said once (the owner, 26 October
// 2026): a paragraph under the note said it a second time, at length.
const NOT_NAMED="bill not named in the captions";

// A ROOM AS THE DOCUMENTS TAB SAYS IT (the person, approved 17 October 2026):
// "Legislative Office Building 210-211" for the clerk's "LOB 210-211", with
// plain_action.BUILDINGS' buildings.
//
// THE SAME WORDS AS plain_action.place, AND EVERYWHERE A ROOM IS SHOWN (the
// audit of 25 October 2026, S7): the Calendar, a committee's meetings,
// those ahead and those held, and its Meets In said the clerk's "GP 231"
// and the database's "GP Room 230" where a bill's Hearings tab said
// "Granite Place 232". One rule,
// in the browser and in build_pages' Calendar alike -- the room together
// ("GP231"), the Office Building with a letter too many ("LOBO 202-204"), a
// building alone, "Room 100, SH", the House chamber -- and preflight holds it
// to plain_action.place's own cases. "GP Room 230" is "Granite Place 230",
// the room the docket calls "GP 230", so one room reads one way.
//
// SL IS THE STATE LIBRARY (the person, 26 October 2026: "SL is the state
// library map room"), and a room with a name is said after its building
// whichever side the clerk wrote it: "SL Map Room", "SL Rm Map Room", "Room
// Map Room, SL" and "Map Room, SL" are all "State Library Map Room", where
// Testify, the Hearings tab and a Senate Education meeting said "SL Map
// Room". And "Rm" is "Room": a Senate committee Meets In "SH Rm 100", its
// hearings "State House 100". plain_action.BUILDINGS, _named and
// _PLACE_BLDG, in the same order.
//
// AND THE CLERK'S OLD CODES (the R2 polish batch, 30 October 2026): the
// docket's "RM207,LOB" before 2007, a study committee's "Room 102 LOB" and
// "LOB Rooms 306-308", the Senate's "SH RM 207", turned round to "LOB 207"
// and so worded. plain_action's _ROOM_FIRST and _ROOM_THEN_CODE.
const ROOM_BUILDINGS={LOB:"Legislative Office Building",LOBO:"Legislative Office Building",
  SH:"State House",GP:"Granite Place",SL:"State Library"};
const roomWords=v=>{
  const t=String(v||"").split(/\s+/).filter(Boolean).join(" ");
  if(/^(?:SH,?\s+)?(?:Reps|Representatives)'?\s+Hall(?:,?\s*SH)?$/i.test(t))
    return "Representatives' Hall, State House";
  if(/^(?:LOBO|LOB|SH|GP|SL)$/.test(t))return ROOM_BUILDINGS[t];
  return t.replace(/\b(?:Room\s+)?((?:[A-Z][\w']*\s+)+Room)\s*,\s*(LOBO|LOB|SH|GP|SL)\b/g,
      (m,n,k)=>`${ROOM_BUILDINGS[k]} ${n}`)
    .replace(/\b(LOBO|LOB|SH|GP|SL)\s+(?:Rm\.?\s+|Room\s+)?((?:[A-Z][\w']*\s+)+Room)\b/g,
      (m,k,n)=>`${ROOM_BUILDINGS[k]} ${n}`)
    .replace(/(^|[,;(]\s*)RMs?\.?\s*,?\s*(\d+(?:-?[A-Z])?(?:\s*[-/]\s*\d+(?:-?[A-Z])?)?)\s*[,/]?\s*(LOB|ST\.?\s*HOUSE|STATE\s+HOUSE|SH)\b/gi,
      (m,p,n,k)=>`${p}${k.toUpperCase()==="LOB"?"LOB":"SH"} ${n.replace(/ /g,"")}`)
    .replace(/(^|[,;(]\s*)[Rr]ooms?\s+(\d+(?:-?[A-Z])?(?:\s*[-/]\s*\d+(?:-?[A-Z])?)?)\s+(LOB|SH|GP|SL)\b/g,
      (m,p,n,k)=>`${p}${k} ${n.replace(/ /g,"")}`)
    .replace(/\bRoom\s+(\w[\w .\-]*?)\s*,\s*([A-Z]{2,3})\b/gi,
      (m,r,k)=>`Room ${r.trim()}, ${ROOM_BUILDINGS[k.toUpperCase()]&&k.toUpperCase()!=="LOBO"
        ?ROOM_BUILDINGS[k.toUpperCase()]:k}`)
    .replace(/\b(LOBO|LOB|SH|GP|SL) ?(?:Rooms? |R[Mm][Ss]?\.? ?)?([0-9][0-9A-Za-z\-]*)\b(?!:)/g,
      (m,k,n)=>`${ROOM_BUILDINGS[k]} ${n}`);
};
// WHERE THIS SITE'S RECORDINGS BEGIN, in one sentence for every page that
// says it: a bill's Hearings tab and a Videos view with nothing in a term
// before then. The month is about_figures.STREAM_START_WORDS, and preflight
// holds the two together.
const STREAM_BEGIN_SAID="Recordings here begin in May 2020, with the General Court&rsquo;s YouTube channels.";
// "approximate", the one word an inferred moment carries (CLAUDE.md,
// Timestamps), on a floor card: where the clerk was not heard to open the
// bill -- a weak marker's start, or no start at all and Play opening shortly
// before the vote.
const floorApprox=s=>s.debate_start==null||s.start_stated===false;
// A floor appearance's motions IN THE VOTES TAB'S WORDS (S2): "Ought to Pass
// with Amendment (OTPA, Pass the bill with changes)" for the record's "OTPA",
// by the key build_site_v2.motion_keys read each one with (motions.classify,
// as a roll call's head on the Votes tab), or the record's own words where it
// names no motion the words have. An amendment's number the record's words
// carry goes beside the head, as it does on the Votes tab (.ramd).
function motionsLine(s){
  const said=(s.motions||[]).map((m,i)=>{const k=(s.mks||[])[i]||{};
    const amd=k.mk?(String(m).match(/\b(?:19|20)\d\d-\d{3,4}[a-z]\b/gi)||[]):[];
    return voteHead(k.mk||"",m,k.mf)+(amd.length?` <span class="ramd">${esc(amd.join(", "))}</span>`:"");});
  return said.length?`<div class="pbar" style="border-top:none">
          <span style="color:var(--ink-2)">${said.length===1?"Motion":"Motions"}: ${
            said.join(" · ")}</span></div>`:"";
}
// A SITTING WITH NO RECORDING TO PLAY, drawn as a card of its own: the day, the
// place, the sign-in counts and the committee's hearing report. A sitting the
// docket notes and the page does not draw, a Senate hearing dated by its
// committee's report, several recordings of the day with none chosen, and
// everything before the chambers streamed. The sittings with a recording are
// the view's (hearingView).
function hearingCard(b,s){
  let inner="";
  // A RECORDING OF THAT DAY EXISTS AND WHICH ONE THIS IS WAS NOT ESTABLISHED:
  // the day and the committee are known and the tape is not (317 proceedings,
  // 236 of them House Finance, whose divisions stream apart). Offered in the
  // order the matcher found them; nothing ranks them. One sentence (the
  // owner, 25 October 2026, S2).
  if(s.state==="candidates"&&(s.candidate_ids||[]).length){
    const ids=s.candidate_ids;
    const links=ids.map((v,i)=>`<a href="https://www.youtube.com/watch?v=${
      esc(v)}" target="_blank" rel="noopener">Recording ${i+1}</a>`).join(" · ");
    const n=["","One","Two","Three","Four","Five"][ids.length]||ids.length;
    inner=`<div class="vbox"><p>${n} recordings that day; the record doesn&rsquo;t
      say which covers this bill: ${links}</p></div>`;
  }
  // A HEARING DATED BY THE SENATE COMMITTEE'S OWN REPORT, where the docket has
  // no Senate hearing of the bill that day (build_site_v2.report_station),
  // said as the person decided on 24 September.
  else if(s.dated_by==="report")inner=`<div class="vbox"><p><b>Dated by the
    committee&rsquo;s own report.</b> The docket records no Senate hearing of
    this bill on this day${(s.docket_heard||[]).length?`; it records one on
    ${s.docket_heard.map(x=>esc(dateWords(x,"full"))).join(" and ")}`:""}. This is the date the Senate
    committee&rsquo;s hearing report gives, and the report is on the Reports
    tab as the Senate filed it. No recording is linked to it.</p></div>`;
  // Before the channels the tab's own note says so once (renderHearings).
  else if(s.state==="prestream")inner="";
  else inner=`<div class="vbox"><p>No recording matched to this proceeding.</p></div>`;
  return `<div class="stn pend">
    <div class="w">${esc(dateWords(s.when))}${s.time?" at "+esc(clock(s.time)):""}${s.venue?" · "+esc(roomWords(s.venue)):""}</div>
    <div class="t">${esc(stationTitle(b,s))}</div>${inner}${
      /* The Senate's hearing report is the Reports tab's (19 November 2026). */
      signinsHeaded(s.testimony)}</div>`;
}

// WHERE THE VIEW OPENS A SITTING'S RECORDING, and what to say of the moment
// (the states are build_site_v2.station_for_proceeding's and station_for_floor's).
// `from` is where the player starts, `start` and `end` the bill's own moments
// where there are any, `approx` whether the start is an inference, `note` what
// to say where the moment was not found.
function hearingPlace(s){
  const h={from:0,start:null,end:null,endWord:"ends",approx:false,note:"",said:""};
  const st=s.state;
  if(st==="located"||st==="stated"){
    // Open essentially AT the mark: a boundary is timed to the caption line
    // the words begin in, so two seconds clips no syllable.
    h.from=Math.max(Math.floor(s.start-2),0);
    h.start=s.start;
    h.end=s.end&&s.end>s.start?s.end:null;
    h.approx=!s.start_stated;
  }else if(st==="approximate"){
    // Hearings run late and never early: a few minutes before the time it
    // was set for, as a place to start scrubbing and not a claim.
    h.from=Math.max(secs(s.predicted)-300,0);
    h.note=s.not_named?NOT_NAMED:"exact moment not found";
  }else if(st==="whole_video"){
    h.note="The recording covers this bill only.";
  }else if(st==="consent"){
    // Named nowhere in the recording, so it went through on the consent
    // calendar: what the calendar adopts is the committee's report, whatever
    // it recommends ("decided", not "passed", 3 October 2026).
    h.said=`Decided on the consent calendar, without separate debate, so there is no moment in the
      recording for it. The recording is the whole session.`;
  }else if(st==="floor_precise"||st==="floor_stated"){
    // A roll call closes the item, so its time is the END of the debate; the
    // player opens where the chair took it up, else ten minutes before.
    const ws=s.window_start!=null?Math.max(Math.floor(s.window_start),0):null;
    h.from=s.debate_start!=null?Math.max(Math.floor(s.debate_start),0):Math.max(ws,Math.floor(s.debate_end)-600);
    h.start=s.debate_start!=null?s.debate_start:null;
    h.end=s.debate_end;
    h.endWord=st==="floor_precise"?"vote at":"ends at";
    h.approx=floorApprox(s);
  }else if(st==="floor_dated"){
    h.from=s.debate_start!=null?Math.max(Math.floor(s.debate_start),0):0;
    h.start=s.debate_start!=null?s.debate_start:null;
    h.approx=floorApprox(s);
    if(s.debate_start==null)h.note="exact moment not found";
  }else h.note=s.not_named?NOT_NAMED:"exact moment not found";
  return h;
}
// What was voted at a sitting: a floor sitting's roll calls of its day and
// chamber (the Votes tab's chip, with its count), a committee's report dated
// to its day (the Reports tab's chip, with its count).
function hearingOutcome(b,d,s){
  const out=[];
  if(/^floor/.test(s.state||"")||/floor/i.test(s.what||"")){
    // A floor sitting names its chamber as its "committee" (station_for_floor).
    const ch=s.body||{House:"H",Senate:"S"}[s.committee]||"";
    // Only the motions this sitting is drawn for (its mks), where it names any:
    // the day's other votes on the bill are the Votes tab's.
    const want=(s.mks||[]).map(k=>k&&k.mk).filter(Boolean);
    (d.rollcalls||[]).filter(rc=>rc.date===s.when&&rc.body===ch&&rc.passed!=null
      &&(!want.length||want.indexOf(rc.mk)>=0)).forEach(rc=>{
      const t=tallyOf(rc);
      out.push(voteChip(rc.mk||"",rc.passed,b.id,rc.mf)+(t?` <span class="vwtally">${tallyWhole(t)}</span>`:""));});
  }else{
    (d.reports||[]).filter(r=>r.date===s.when&&r.dated!=="printed"&&(!r.body||!s.body||r.body===s.body)).forEach(r=>{
      const rec=r.majority_recommendation, x=(r.reports||[]).find(e=>e.vote_yeas!=null);
      if(rec)out.push(recChip(rec,x?`${x.vote_yeas}–${x.vote_nays}`:""));});
  }
  return out.join(" ");
}
// A time in the recording as YouTube writes one: 5:43:23, 43:23.
const hmsShort=x=>{const t=Math.max(0,Math.floor(x)),h=Math.floor(t/3600),m=Math.floor(t/60)%60,
  ss=String(t%60).padStart(2,"0");return h?`${h}:${String(m).padStart(2,"0")}:${ss}`:`${m}:${ss}`;};
// One moment as the button that moves the player there. A ROUND PLAY BUTTON,
// NOT A CHIP'S SHAPE (the owner, 19 November 2026): beside the sign-in counts,
// drawn as chips, two bordered boxes with a time in them read as two more
// counts. `word` is what the moment is, for a screen reader ("starts",
// "ends", "vote at"); `shown` a word beside the time, where the time alone
// would not say it (the floor's vote).
const hearingMoment=(pid,t,word,shown)=>`<button type="button" class="jump vwjump" data-seek="${
  esc(pid)}|${Math.max(0,Math.floor(t))}" aria-label="Play from ${hms(t)}, ${word==="vote at"?"the vote"
  :`where it ${esc(word)}`}">${icon("play")}${hmsShort(t)}${shown?` ${esc(shown)}`:""}</button>`;
// The bill's moments in the recording, as one line by the player: "Where this
// bill is in the recording: [5:43:23] to [5:46:00]", and "approximate" once
// where the moment is inferred (CLAUDE.md, Timestamps).
function hearingMoments(h,pid){
  const end=h.end!=null?hearingMoment(pid,h.end,h.endWord,h.endWord==="vote at"?"vote":""):"";
  const start=h.start!=null?hearingMoment(pid,h.start,"starts",""):"";
  if(!start&&!end)return "";
  // One word for the pair: the start's where there is one, else the end's.
  const approx=!!h.approx;
  return `<p class="vwmoms"><span class="vwml">Where this bill is in the recording</span>${
    start}${start&&end?`<span class="vwto">to</span>`:""}${end}${approx?`<i class="approx">approximate</i>`:""}</p>`;
}
// What is under the player for the sitting chosen. EACH FACT ONCE (the owner,
// 19 November 2026): the row chosen in the list already says the day, the
// kind, the committee and the length, so under the player are only what it
// does not -- the bill's moments, first, by the player they move; then the
// time and the room, with the recording on YouTube; what was voted; and who
// signed in, under their own heading. The Senate's hearing report is the
// Reports tab's.
function hearingDetail(b,d,s,h,pid){
  const out=[hearingMoments(h,pid)];
  if(h.note)out.push(`<p class="vwnone">${esc(h.note[0].toUpperCase()+h.note.slice(1))}${/\.$/.test(h.note)?"":"."}</p>`);
  if(h.said)out.push(`<p class="vwnone">${h.said}</p>`);
  if(s.state==="whole_video"&&s.title)out.push(`<p class="vwnone">${esc(s.title)}</p>`);
  const vid=String(s.video_id||""), at=Math.max(0,Math.floor(h.from||0));
  const where=[s.time?esc(clock(s.time)):"",s.venue?esc(roomWords(s.venue)):"",
    vid?`<a href="https://www.youtube.com/watch?v=${esc(vid)}${at?`&t=${at}s`:""}" target="_blank" rel="noopener">On YouTube</a>`:""];
  out.push(`<p class="vwkinds">${vwJoin(where)}</p>`);
  const oc=hearingOutcome(b,d,s);
  if(oc)out.push(`<p class="vwres">${oc}</p>`);
  out.push(motionsLine(s));
  out.push(signinsHeaded(s.testimony));
  return out.join("");
}
// THE TAB IS A COMMITTEE'S VIDEOS TAB, FOR ONE BILL (the owner, 10 November
// 2026: "changing the ways bills are formatted to be more similar to how the
// committee videos tab is formatted ... we'd only have one player and the
// format would be cleaner"). videoView draws it: one player at the top, the
// bill's recordings as its playlist beside it (below it on a phone), in the
// order of the bill's story -- the docket's: a hearing, its executive
// session, the floor -- and under the player, for the one chosen, what the
// bill's own sittings showed one at a time (hearingDetail). Choosing a row
// loads its recording in the player at the bill's moment.
const HEAR_CHOSEN={};
function hearingView(b,d,rec){
  const key=`bill|${dkey(b.id)}`;
  const rows=rec.map(([s,si])=>{
    const h=hearingPlace(s), pid=`h${si}_${String(s.video_id).replace(/[^\w-]/g,"")}`;
    return {id:`h${si}`,video:s.video_id,pid,date:s.when,seconds:s.seconds,from:h.from,
      who:hearingWhere(s)||b.n||b.id,what:stationTitle(b,s),
      kinds:kindChips([s.what]),line:[hearingWhere(s)],
      playText:h.from>0?`Play from ${hmsShort(h.from)}`:"Play the recording",
      detail:()=>hearingDetail(b,d,s,h,pid)};});
  // A row's address is the bill's Videos tab where the page is a bill's;
  // anywhere else (the search list, with the bill open) it is where the reader is.
  const here=location.pathname.replace(/\/+$/,"");
  const path=/^\/bill\/\d{4}\/[a-z0-9]+(?:\/[a-z]+)?$/i.test(here)
    ?`${here.replace(/\/(?:hearings|videos)$/,"")}/videos`:here;
  // NO CAPTION UNDER THE PLAYER (`bare`, the owner, 19 November 2026): it
  // said the committee, the day and the length the chosen row says, and its
  // "On YouTube" is in the line under the player (hearingDetail).
  return videoView({who:b.n||b.id,key,rows,chosen:HEAR_CHOSEN[key]||rows[0].id,bare:true,
    // THE COUNT AND NOTHING MORE (the owner, 19 November 2026).
    heading:`${rows.length.toLocaleString()} recording${rows.length===1?"":"s"}`,
    href:()=>path,pid:r=>r.pid,onChoose:id=>{HEAR_CHOSEN[key]=id;},
    source:"Recordings from the General Court&rsquo;s House and Senate YouTube channels."});
}
function renderHearings(b,d){
  // WHERE THIS SITE'S RECORDINGS BEGIN, ONCE (the audit of 25 October 2026,
  // S4), at the top of the tab. Not where recording began: the House
  // Calendars of 2013-2019 announce hearings streamed live, and none of those
  // is on either YouTube channel, so "no recording exists" and "not
  // livestreamed before 2020" are both claims the record contradicts. The
  // month is about_figures.STREAM_START_WORDS, and preflight holds the two
  // together.
  const all=d.stations||[];
  const pre=all.some(s=>s.state==="prestream")?`<p class="note">${STREAM_BEGIN_SAID}</p>`:"";
  const rec=all.map((s,si)=>[s,si]).filter(x=>x[0].video_id);
  const plain=all.filter(s=>!s.video_id);
  if(all.length){
    return pre+(rec.length?hearingView(b,d,rec):"")
      +(plain.length?`<div class="hplain">${rec.length?`<h3 class="vwh">No recording to play</h3>`:""}${
        plain.map(s=>hearingCard(b,s)).join("")}</div>`:"");
  }
  // A MEETING THE DOCKET NOTICED AND THE PAGE DOES NOT DRAW. HB 273 of 2017's
  // history says "The docket schedules a public hearing for January 10,
  // 2017", of a bill the House did not introduce, and this tab said there
  // were no scheduled proceedings on file. The notice is a line of the docket
  // (e.notice), with its reason beside it.
  return (d.events||[]).some(e=>e.notice)
    ? `<p class="note">The docket gave notice of a meeting on this bill, and
       none is drawn here. The history on the Summary tab says why, and the
       docket there lists the notice.</p>`
    : `<p class="note">No hearing or meeting is on record for this bill.</p>`;
}

// Each calendar entry carries the majority's recommendation and, when the
// committee split, the minority's. The two are different motions and must
// not both show the majority's -- on a divided report that would read as
// though the dissenters agreed.
// Every report the tab draws, counted the same way it draws them. This used
// to count only the written ones, so HB686 read "(4)" above five blocks, and
// the 319 bills whose only report is one the docket recorded showed no count
// at all above a report that was plainly there.
// Stations with a recording, counted the way the tab draws them. A station
// with no video_id draws "No recording matched" and is not a video; on the
// terms before the House streamed every station is one, so those pages
// carry no count rather than "Hearings (0)".
//
// A "candidates" station HAS a recording -- several, in fact. It is the case
// where the committee was recorded that day and which of its recordings this
// sitting is has not been established, so the page names them all and picks
// none. It carries no video_id precisely because nothing was picked, so a
// filter on video_id alone read it as no recording at all and left it out of
// the count: 263 sittings across 239 bill pages, every one of them a tab
// reading one fewer than the tab lists.
const videoCount=d=>(d.stations||[])
  .filter(s=>s.video_id||s.state==="candidates").length;
// AND THE SENATE'S HEARING REPORTS (19 November 2026), which the tab draws
// as its public hearing reports.
const reportCount=d=>(d.reports||[]).reduce((n,r)=>n+((r.reports||[]).length),0)
                     +(d.docket_reports||[]).length+heardReports(d).length;
// THE SENATE COMMITTEES' REPORTS OF THEIR PUBLIC HEARINGS, in the order of the
// bill's sittings: each on the station of the hearing it reports
// (build_site_v2.attach_hearing_reports), with that station.
const heardReports=d=>(d.stations||[]).flatMap(s=>(s.reports||[]).map(r=>({r,s})));

// The first year of a bill's term, or 0 (17 October 2026: a 1995 report
// was told its calendar "has not been read into the site yet", and no
// calendar before 1997 is online to read).
const termStartOf=d=>parseInt(String((d&&(d.term||d.year))||"").slice(0,4),10)||0;
// A REPORT WITH NO REASONING SAYS WHAT IT DOES RECORD (the manager, 29 October
// 2026). "Records the recommendation and the vote" was said of every report
// with no text, and an interim study statement such as HB 1547 of 2010's
// records a recommendation and no vote. The sentence names what the report
// carries: the recommendation, the vote, both or neither.
function reportNoReasons(hasRec,hasVote){
  const what=hasRec&&hasVote?"the recommendation and the vote":hasRec?"the recommendation":hasVote?"the vote":"";
  return what?`This report records ${what}, and gives no reasoning.`:"This report gives no reasoning.";
}
function renderReports(b,d,rsa){
  const recFor=(r,side)=>side==="Minority"
      ? (r.minority_recommendation||"") : (r.majority_recommendation||"");
  // What the chamber did between one report and the next, keyed on the report
  // it comes before. A bill sent back to a committee that has already reported
  // it comes out reported again, and without this the second report reads as
  // an unexplained repeat of the first -- which is what a committee reporting
  // twice looked like on the nine bills it happens to.
  const acts={};
  (d.report_actions||[]).forEach(a=>{(acts[a.before]=acts[a.before]||[]).push(a);});
  const between=key=>(acts[key]||[]).map(a=>
    `<p class="note" style="margin:0 0 16px">Between these reports the docket
      records, on ${esc(dateWords(a.date))}: <em>${esc(a.text)}</em></p>`).join("");
  // The day the committee signed its report, where the docket states it; the
  // day the calendar carrying it was published, where it does not. Saying
  // which is the difference between a fact and a stand-in for one.
  const when=r=>!r.date?"":`<span class="secsub">${esc(dateWords(r.date))}</span>`
      +(r.dated==="printed"?` <span class="repas">as printed</span>`:"");
  const cited=r=>{
    if(!r.cite)return "";
    // The House's source string IS the citation -- "House Calendar 51, 2025".
    // The Senate's reports come from the General Court's database and their
    // source names that, which is not what a reader wants beside a committee's
    // name; the docket's own citation for the same report is.
    // "Senate Calendar 13" beside the House's "House Calendar 14", not "SC
    // 13" (17 October 2026): docLong spells out the docket's shorthand.
    const t=esc(r.body==="S"?docLong(r.cite):(r.source||r.cite));
    // NO LEADING SEPARATOR. It divided the citation from the date when the two
    // shared a line; in the wide layout the date is above it in a column and
    // the dot divides it from nothing.
    return `<span class="repcite">${r.cite_url
      ? `<a href="${esc(r.cite_url)}" rel="noopener">${t}</a>` : t}</span>`;
  };
  // "SENATE JUDICIARY COMMITTEE" -- whose report this is, as the heading
  // rather than as small print beside the date. A bill can be reported by
  // four different committees and the reader needs to know which one is
  // speaking before they read what it said.
  // In Title Case as typed, now that capitals no longer hide the record's own
  // case (the cohesion audit's I-1): each part through titleWords, so a
  // name stored as "JUDICIARY" reads "Judiciary", and "Committee" added only
  // where the name does not carry it ("Joint Committee on Address").
  const repName=(cmte,body)=>{
    const n=[body,cmte].filter(Boolean).map(titleWords).join(" ");
    return /\bcommittee\b/i.test(n)?n:n+" Committee";};
  // EACH REPORT SAYS WHAT IT IS (the owner, 19 November 2026), under its
  // committee and over its date: a public hearing's report or an executive
  // session's, in the chip the Videos tab's rows give those meetings
  // (kindChips' colours). The committee, the chip, the date, the calendar.
  const head=(r,cmte,body)=>`<div class="rephead">
      ${[body,cmte].filter(Boolean).length
        ? `<h2 class="sech">${esc(repName(cmte,body))}</h2>`:""}${repKind("exec")}
      <div class="repmeta">${when(r)}${cited(r)}</div></div>`;

  // ONE REPORT IS ONE ELEMENT, so that it can be laid out as one. The head
  // and its blocks were siblings of the pane, which left the vertical
  // arrangement as the only one available: `.card .pane > *` caps every child
  // at the measure, so on a 1,094px pane the whole tab ran in a 560px column
  // with 534px of nothing beside it, while the Summary tab next to it used
  // the full width. Wrapped, the two halves can sit side by side above
  // 1100px -- what the report IS on the left, what the committee SAID on the
  // right -- and stack back to exactly today's order below it.
  const rep=(h,body)=>`<article class="rep">
    <div class="repside">${h}</div><div class="repbody">${body}</div></article>`;

  const written=(d.reports||[]).map(r=>{
    const divided=!!r.minority_recommendation;
    // The committee's vote is printed at the end of the report body in the
    // calendar, where it reads as a footnote to a paragraph of prose. It
    // belongs beside the label it is a vote on.
    //
    // Where the committee split, the two numbers are the two sides: the count
    // that carried the majority recommendation, and the count that did not.
    // Where one report was filed, neither number belongs to anybody else, so
    // the whole tally sits with it -- 19-0, or 18-1.
    const tally=(r.reports||[]).map(x=>x).find(x=>x.vote_yeas!=null);
    // THE VOTE INSIDE THE CHIP (the owner's walk of dry run 8, 8 November
    // 2026): "Recommended for Future Legislation (10–4)". A report with a
    // recommendation carries its count in the chip; one without keeps the
    // count beside the label, as before.
    const voteOf=e=>{
      if(e.vote_yeas==null&&!tally)return "";
      const y=e.vote_yeas!=null?e.vote_yeas:tally.vote_yeas;
      const nn=e.vote_nays!=null?e.vote_nays:tally.vote_nays;
      return divided?String(e.side==="Minority"?nn:y):`${y}–${nn}`;
    };
    const committeeTally=e=>{
      if(e.vote_yeas==null&&!tally)return "";
      const y=e.vote_yeas!=null?e.vote_yeas:tally.vote_yeas;
      const nn=e.vote_nays!=null?e.vote_nays:tally.vote_nays;
      return `<span class="cvote" title="Committee vote ${y}–${nn}">${voteOf(e)}</span>`;
    };
    const cmte=((r.reports||[])[0]||{}).committee||"";
    const blocks=(r.reports||[]).map(e=>{
      const rec=recFor(r,e.side);
      return `<div class="repblock">
        <div class="repline">
          <span class="secsub">${esc(e.side)}</span>
          ${rec?"":committeeTally(e)}
          ${rec?recChip(rec,voteOf(e)):""}</div>
        <p class="repby">${/* THE WRITER AS THE PERSON'S CHIP where the build
             named one member for certain (build_site_v2.report_author); the
             report's own words where it did not. */
             e.author_m&&e.author_m.slug?pchip(e.author_m):esc(e.author)}</p>
        ${e.amendment?`<p class="note" style="margin:0 0 7px">Amendment ${
          esc(e.amendment)}.</p>`:""}
        ${/* Where the House Calendar printed another bill's report under
             this heading (report_check.py), the page says so: the text
             below is then the committee's filed copy, or there is none. */
          e.note?`<p class="note" style="margin:0 0 7px">${esc(e.note)}</p>`:""}
        ${(e.text||"").trim()
          ? `<p class="srwhy">${rsa(esc(e.text))}</p>`
          // 350 of the Senate's 1,446 reports carry no reasoning at all. That
          // is a fact about the report, not a gap in the site, and saying so
          // is better than an empty space under a heading. Not where a note
          // above has said why there is none: that report did give reasons,
          // and they are not the ones the calendar printed.
          : e.note?"":`<p class="note" style="margin:0">${
             reportNoReasons(!!rec,!!committeeTally(e))}</p>`}
        </div>`;}).join("");
    return {date:r.date,rank:1,html:between(r.date)+rep(head(r,cmte,r.body==="S"?"Senate":"House"),
      (divided?`<p class="note">The committee split. Both reports are printed
        below in the committee's own words.</p>`:"")+blocks)};});

  // Reports the docket records and this site has no written text for. Once the
  // Senate's own reports came out of the General Court's database, 964 of
  // these turned into written blocks above and what is left is the remainder:
  // a House report printed in a calendar not read in yet, or a Senate report
  // the database does not carry.
  const docket=(d.docket_reports||[]).map(r=>{
    const vote=r.vote_yeas!=null&&r.vote_nays!=null&&!r.recommendation
      ? `<span class="cvote" title="Committee vote ${r.vote_yeas}–${r.vote_nays}"
          >${r.vote_yeas}–${r.vote_nays}</span>` : "";
    // The same three-part heading the written reports use -- who, by what vote,
    // for what motion. The Senate files one report and does not label it, and
    // leaving the label out left a bare "3-2" hanging where every block above
    // it reads "MAJORITY 10" or "COMMITTEE 17-0".
    const amd=r.amendment?`<p class="note" style="margin:0 0 7px">Amendment ${
      esc(r.amendment)}${r.new_title?", which also changes the bill’s title":""}.</p>`:"";
    return {date:r.date,rank:1,html:between(r.date)+rep(head(r,r.committee,r.body==="S"?"Senate":"House"),
      `<div class="repline">
        <span class="secsub">${esc(r.side||"Committee")}</span>${vote}
        ${r.recommendation?recChip(r.recommendation,r.vote_yeas!=null&&r.vote_nays!=null?`${r.vote_yeas}–${r.vote_nays}`:""):""}</div>
      ${amd}
      <p class="note" style="margin:var(--sp-5) 0 0">${r.body!=="S"&&termStartOf(d)&&termStartOf(d)<1997
        ? "The written report for this one is not on the site: the General Court’s online calendars, which print the reports, begin in 1997. This is what the docket records of it."
        : "The written report for this one is not on the site; this is what the docket records of it."}</p>`)};});

  // THE SENATE COMMITTEES' REPORTS OF THEIR PUBLIC HEARINGS (moved from the
  // Videos tab, 19 November 2026), each headed as the committee reports are.
  const heard=heardReports(d).map(({r,s})=>({date:r.heard||s.when,rank:0,html:rep(`<div class="rephead">
      <h2 class="sech">${esc(r.committee||"Senate Committee")}</h2>${repKind("hearing")}
      <div class="repmeta"><span class="secsub">${esc(dateWords(r.heard||s.when))}</span></div></div>`,
    hearingReport(r,!!s.video_id))}));
  const none=`<p class="note">No committee report on file. A report is recorded in the docket
      when a committee reports the bill out, and the reasoning behind it is printed
      in the House Calendar or filed with the Senate; neither has happened here yet.</p>`;
  // ONE LIST, OLDEST FIRST, WHATEVER THE KIND (the owner, 19 November 2026,
  // in place of two groups of the same day): a day's public hearing before
  // its executive session, and a report with no date last. The sort is
  // stable, so reports of one kind and one day keep the order they came in.
  const all=heard.concat(written,docket).sort((x,y)=>{
    const a=x.date||"9999",c=y.date||"9999";
    return a<c?-1:a>c?1:x.rank-y.rank;});
  return veto(d)+(all.length?all.map(x=>x.html).join(""):none)+sosArchive(d);
}
// WHAT A REPORT IS, as a chip under its committee: the meeting it comes out of,
// in the colours the Videos tab's rows give that kind of meeting (kindChips,
// meeting_kinds.json's).
const REP_KIND={hearing:["Public Hearing Report","public hearing"],exec:["Executive Session Report","executive session"]};
function repKind(k){
  const [word,meet]=REP_KIND[k], w=MEET_KIND[meet]||[];
  return `<p class="repkind">${chip(word,`calkind ${w[1]||"k-other"}`)}</p>`;
}
// THE COMMITTEES' OWN FILES (the owner, 19 November 2026: "Link now, trimmed
// PDFs later"): the Secretary of State's archive page listing the bill's
// House and Senate committee files, scanned, where build_site_v2 gives one
// (sos_archives.address says when). Once a bill, under the reports, and not
// counted among them. Nothing of it is fetched; the link leaves the site and
// says so, as every such link does.
function sosArchive(d){
  const u=d&&d.sos_archives;
  return u?`<p class="src repsos">The committee files on this bill, scanned, are at the
    <a href="${esc(u)}" target="_blank" rel="noopener">Secretary of State&rsquo;s archive</a>.</p>`:"";
}

// WHY the governor vetoed it, which the docket does not record. Read into the
// House on the day and printed in that day's calendar under a heading of its
// own; the calendar is cited so a reader can check the words against the
// document they came from.
//
// Quoted in full rather than summarised. It is a short written statement
// published by its author, which is a different thing from a caption -- the
// site does not quote those because they garble bill numbers, and a garbled
// quotation with a citation on it is worse than none.
function veto(d){
  const v=d.veto_message;
  if(!v||!(v.text||[]).length)return "";
  const cite=v.source&&v.source.url
    ? `<a href="${esc(v.source.url)}" target="_blank" rel="noopener">${
        esc(v.source.name||"the House calendar")}</a>`
    : esc((v.source||{}).name||"the House calendar");
  return `<section class="vmsg">
    <h2 class="sech">The Governor&rsquo;s Veto Message</h2>
    ${v.text.map(p=>`<p>${esc(p)}</p>`).join("")}
    <p class="vsig">${esc(v.governor||"")}${
      v.date?` <span class="secsub">${esc(dateWords(v.date))}</span>`:""}</p>
    <p class="src">Printed in ${cite}.</p>
  </section>`;
}

// Sponsors, grouped by chamber with the originating one first. A House bill
// co-sponsored by two senators is a House bill, and reading the Reps first is
// reading it in the order it happened. Which chamber that is comes from the
// PRIME SPONSOR'S OWN SEAT, because that is what settles it for a concurrent
// resolution, where the bill number does not.
function renderSponsors(b,d){
  const spAll=d.sponsors||[];
  const spPrime=spAll.find(s=>s.prime)||spAll[0]||{};
  const chOf=s=>String(s.chamber||"").toUpperCase().slice(0,1);
  const origin=chOf(spPrime)||(/^S/i.test(b.id)?"S":"H");
  const CHNAME={H:"Representatives",S:"Senators"};
  // A sponsor's name links to that member's own page. It was the one place a
  // person was named on this site and could not be followed.
  const pill=pchip;
  const spRest=spAll.filter(s=>!["H","S"].includes(chOf(s)));
  // A SECTION OF THE SUMMARY (19 November 2026), so each chamber's names are
  // an h3 under its "Sponsors", and only where the names are of more than
  // one chamber: a House bill's lone "Representatives" said nothing.
  const split=["H","S"].filter(ch=>spAll.some(s=>chOf(s)===ch)).length+(spRest.length?1:0)>1;
  const spBlock=ch=>{const l=spAll.filter(s=>chOf(s)===ch);return l.length
    ?`${split?`<h3 class="spch">${CHNAME[ch]} <span class="sechn">${l.length}</span></h3>`:""}
      <div class="chosen">${l.map(pill).join(" ")}</div>`:"";};
  // A count per party, and nothing said about it. Sorted by party code, so the
  // order is fixed rather than a ranking by size.
  const pc={};
  spAll.forEach(s=>{const k=String(s.party||"").toUpperCase().slice(0,1);
    if(k)pc[k]=(pc[k]||0)+1;});
  const spParty=Object.keys(pc).sort().map(k=>
    `<span title="${esc(PARTY_NAME[k]||k)}">${pc[k]} ${esc(k)}</span>`).join(" \u00b7 ");
  // THE COUNT UNDER THE CHIPS (the owner, 19 November 2026): over them it
  // stood beside the section's heading and read as a second one.
  const sp=spAll.length?`
    ${spBlock(origin)}${spBlock(origin==="S"?"H":"S")}
    ${spRest.length?`${split?`<h3 class="spch">Chamber Not on File <span class="sechn">${spRest.length}</span></h3>`:""}
      <div class="chosen">${spRest.map(pill).join(" ")}</div>`:""}
    <p class="spcount">${spAll.length} Sponsor${spAll.length===1?"":"s"}${
      spParty?` \u00b7 ${spParty}`:""}</p>`:"";
  // WHERE THE NAMES WERE READ. Before 2023 the only list on this site is the
  // sponsor line printed on the bill's own text (text_sponsors.py): the first
  // name there is taken as prime, and a name matched to nobody who cast a roll
  // call that term is shown as it is printed, without a party.
  const fromText=spAll.length&&spAll.every(s=>s.source==="bill text");
  const asPrinted=fromText&&spAll.some(s=>!s.member_id);
  // 1989 TO 1998 THE NOTE SAYS WHERE THE NAMES WERE READ, AND NO MORE (the
  // owner, 14 November 2026: "not necessary to get into that fine of detail
  // and just let the pages speak for themselves"). The General Court's
  // sponsor record for the bill places a name in full where it can
  // (past_roster.py) and one it cannot is shown as printed; no named roll call
  // of those years is on this site, so none is said to be matched to a
  // member who voted that term. The term is tested as renderVotes tests it.
  const early=termStartOf(d)&&termStartOf(d)<1999;
  // A BILL WHOSE PRINTED LINE NAMES NOBODY. 1991 HCR 13 and HR 19 print "INTRODUCED BY:
  // REFERRED TO:" with no name after either, and the page listed a sponsor called
  // REFERRED TO. Their names come from the General Court's own sponsor record instead
  // (text_sponsors.unprinted), and the page says so rather than implying they were read
  // off the bill like every other name of that term.
  const unprinted=spAll.length&&spAll.every(s=>s.unprinted);
  // A BILL ONLY THE HOUSE JOURNAL CARRIES (journal_bills.py): its sponsors are
  // the journal's list of bills introduced, and the first is taken as prime.
  const fromJournal=spAll.length&&spAll.every(s=>s.source==="House Journal");
  // THE STANDING NOTE IS GONE. It read "Prime sponsor in bold. From the
  // General Court sponsor file." with a link to the docket, and all three
  // parts were being said twice. The prime sponsor carries a PRIME label
  // inside its own chip, which says it in the place a reader is looking and
  // survives being read aloud, where bold does neither. Where the names came
  // from is what the whole site is; the sponsor file is the unremarkable
  // case. And the docket link is on the Summary tab already, in the "On the
  // record" panel as "This bill on gencourt", so nothing here was the only
  // way to the source.
  //
  // WHAT IS KEPT IS THE UNUSUAL CASE, and only on the bills it applies to.
  // Before 2023 there is no sponsor file: the names are read off the sponsor
  // line printed on the bill's own text, and one that matches nobody who cast
  // a roll call that term is shown as printed, without a party. That is a
  // caveat about the record rather than a description of the furniture, no
  // card states it, and a reader comparing a pre-2023 roster with a modern
  // one would otherwise have no way to know the two were gathered differently.
  return `${sp||`<p class="note">No sponsors on file.</p>`}${fromText
    ?`<p class="note" style="margin-top:12px">As named on the sponsor line of
        the bill's text, where the first name is the prime sponsor.${asPrinted&&!early
        ?` A name without a party is shown as the text prints it: it could not
          be matched to one member who voted that term.`:""}</p>`:""}${unprinted
    ?`<p class="note" style="margin-top:12px">The bill's own text names no
        sponsor. These are the names the General Court's sponsor record gives
        it.</p>`:""}${fromJournal
    ?`<p class="note" style="margin-top:12px">As named in the House Journal's
        list of bills introduced, where the first name is the prime
        sponsor.</p>`:""}`;
}

// Amendments, in the order the docket took them up. A committee amendment
// is considered before any floor amendment, and where two touch the same
// section the later one governs -- so the sequence carries meaning, and it
// is shown as the record has it rather than grouped or sorted.
// The fiscal note, as the table the bill's own PDF prints. A figure sits
// under a year only where the row has one figure per year; where it has fewer
// the row spans, because which years the second figure covers is not stated
// and putting it under one of them would be inventing an answer.
//
// ON A PHONE, ONE ROW PER LINE, ITS YEARS BENEATH (the person, 7 November
// 2026). The same table, reflowed by app.css below 45em: each row's name on
// a line of its own, and under it its figures, each over a short heading
// (`data-y`, "FY26" for "FY 2026"), since the column heads are not drawn
// there. A row's class says how wide its figures run, which decides how many
// share a line: "fns" (six characters at most, "$0", "$5,000") all of them,
// "fnm" at most two, "fnl" (a sentence) one each; "fnspan" is a row the
// source did not break down by year, its value once. The roles keep it a
// table to a screen reader when its rows are not drawn as table rows, as on
// the Data page (.dpdl).
const FN_SHORT=6, FN_LONG=40;
const fnYear=y=>{const m=/^FY\s*\d{2}(\d{2})$/i.exec(String(y).trim());return m?`FY${m[1]}`:String(y);};
const fnFit=vs=>{const w=Math.max(0,...vs.map(v=>String(v).length));
  return w<=FN_SHORT?"fns":w<=FN_LONG?"fnm":"fnl";};
function fiscalTable(f){
  if(!f)return "";
  const table=t=>{
    if(t.raw)return `<div class="fnraw">${t.caption?`<h4>${esc(t.caption)}</h4>`:""}
      ${t.raw.map(l=>`<p>${esc(l)}</p>`).join("")}</div>`;
    const n=(t.years||[]).length;
    const short=t.years.map(fnYear);
    return `<div class="fnwrap"><table class="fn" role="table">
      ${t.caption?`<caption>${esc(t.caption)}</caption>`:""}
      <thead role="rowgroup"><tr role="row"><th role="columnheader"></th>${t.years.map(y=>
        `<th scope="col" role="columnheader">${esc(y)}</th>`).join("")}</tr></thead>
      <tbody role="rowgroup">${t.rows.map(r=>`<tr role="row" class="${r.span?"fnspan":fnFit(r.values)}"><th scope="row" role="rowheader">${esc(r.label)}</th>${
        r.span
          ? `<td colspan="${n}" role="cell">${esc(r.values.join(" \u00b7 "))}</td>`
          : r.values.map((v,i)=>`<td role="cell" data-y="${esc(short[i]||"")}">${esc(v)}</td>`).join("")
      }</tr>`).join("")}</tbody></table></div>
      ${t.footnote?`<p class="src">${esc(t.footnote)}</p>`:""}`;
  };
  return `<section class="fnsec"><h3 class="amdsec">Fiscal impact</h3>
    ${f.lead?`<p class="fnlead">${esc(f.lead)}</p>`:""}
    ${(f.tables||[]).map(table).join("")}
    <p class="src">Source: NH General Court</p></section>`;
}

// THE BILL TEXT AS A DOCUMENT: the section that sat below the tabs, as a
// function so the Bill Text tab can hold it too. A bill with one printing
// and no amendments has no version history for the tab to show, and its
// text was drawn only below the tabs on the bill's own page -- so in the
// bills list, where no bill is the page's own, the tab opened empty (the
// person, 24 September: "sometimes just doesn't display anything"). Such a
// bill now carries this in its tab, and the block below the tabs is kept
// for bills with a version history only, so no text is drawn twice.
function billTextSection(b,d,rsa){
        // HOW LONG THE DOCUMENT IS, MEASURED, because this block is not in a
        // tab: it sits below whichever one is open and was never hidden. HB 2
        // of 2025 is 478,101 characters of text and 527,359 more across 43
        // amendments, which laid the card out at 222,985px on a desktop and
        // 504,778px on a phone -- three hundred and fifty screens of document
        // under the summary of it. The median bill of the term is 11,511
        // characters and wants no ceremony, so it opens as it always has.
        const bodyLen=((d.billtext||{}).body||"").length;
        const amdLen=(d.amendments||[]).reduce((n,a)=>n+((a&&a.text)||"").length,0);
        const nAmd=(d.amendments||[]).length;
        const LONG=30000;
        const shut=bodyLen+amdLen>LONG;
        const what=nAmd?`the text and ${nAmd} amendment${nAmd===1?"":"s"}`
                       :"the text";
        return `<section class="btsec"><h2 class="sech">Bill Text</h2>
        <p class="btwhat">The bill and its amendments, as the General Court publishes them. The other tabs are this site’s account of the record; this is the document.</p>
        <details class="btdoc"${shut?"":" open"}><summary><span class="shut">Show ${
          what}</span><span class="open">Hide ${what}</span></summary>${
        renderBillText(b,d,rsa)}</details></section>`;}

function renderBillText(b,d,rsa){
  // What the mark says on hover: an amendment's bracket is the amendment's,
  // and the bill's own is the bill's (17 October 2026: the Bill Text said
  // "removed by this amendment" of a bill with no amendment).
  const brackets=(s,why="removed by this amendment")=>s.replace(/\[([^\]]{1,400})\]/g,
    (_,inner)=>`<del class="cut" title="${why}">${inner}</del>`);
  const amds=(d.amendments||[]).map(x=>{
    const who=x.mover||x.proposed_by||"";
    const state=x.adopted===true?"adopted":x.adopted===false?"rejected":"";
    return `<div class="amd">
      <div class="amdhead"><span class="amdn">${esc(`${x.kind||"Amendment"} ${x.num||""}`.trim())}</span>
        ${state?chip(state==="adopted"?"Adopted":"Rejected",
          `cstat ${state==="adopted"?"s-law":"s-done"}`):""}
        <span class="amdd">${x.date?esc(dateWords(x.date)):""}${
          AVK[x.vote_kind]?` \u00b7 ${AVK[x.vote_kind]}`:""}</span></div>
      ${who?`<p class="amdby">${esc(who)}</p>`:""}
      ${(x.targets||[]).length?`<p class="amdt">Changes ${
        x.targets.map(v=>`<span class="tgt">${esc(v)}</span>`).join(" ")}</p>`:""}
      ${(x.supersedes||[]).length?`<p class="amdsup">Later than ${
        x.supersedes.map(s=>`${esc(s.num)} (${s.shared.map(esc).join(", ")})`).join(", ")
        }, so where they change the same thing this one governs.</p>`:""}
      ${x.text
        ? `<details class="amdtext"><summary>Read the amendment</summary>
             <p translate="no">${brackets(rsa(esc(x.text)))}</p>
             <p class="src">Text in ${"["}brackets] is being removed. Text being
               added is underlined in the original, and underlining is lost when
               a PDF is read as text, so additions are not marked here.${
               x.source?` From ${esc(x.source)}.`:""}</p></details>`
        : `<p class="note">The text is not in the calendars this site has read.
             It was moved on the date above and the docket records the outcome.</p>`}
    </div>`;}).join("");

  // AFTER brackets, which it uses. billLines built above brackets threw
  // "Cannot access 'brackets' before initialization" on every bill, so
  // renderDetail never returned and every card sat on "Loading..." with the
  // data already fetched and in hand. Both now live in this one short
  // function, eight lines apart, where the order is visible.
  //
  // The bill as the General Court publishes it. The version label is the most
  // important thing on it: "as introduced" and "as amended by the House" are
  // different laws, and a reader who misses which one they are looking at has
  // misread everything below. SEC and OUTLINE, which shape it, are module
  // constants now: they depend on nothing and were being recompiled per bill.
  const billLines=(txt)=>String(txt||"").split("\n")
    .flatMap(l=>l.split(OUTLINE)).map(raw=>{
    const line=raw.trim();
    if(!line)return "";
    const html=brackets(rsa(esc(line)),"removed from current law by this bill");
    if(/^(?:Be it Enacted|That the following|Whereas\b|RESOLVED\b)/i.test(line))
      return `<p class="enact">${html}</p>`;
    const m=SEC.exec(line);
    if(m)return `<p class="sec"><b>${esc(m[1])}</b> ${html.slice(m[0].length)}</p>`;
    // A subparagraph indents under the section it belongs to; a new RSA
    // section number stands as a heading, which is how it is printed.
    if(/^(?:[IVXL]{1,5}\.|\([a-z]\))/.test(line))return `<p class="sub">${html}</p>`;
    if(/^\d{1,3}:\d+[-\w]*\s+[A-Z]/.test(line))return `<p class="rsahead">${html}</p>`;
    return `<p class="ln">${html}</p>`;
  }).join("");
  const bt=d.billtext;
  // Amendments belong with the text, not beside it. Each one is a step from
  // one version of the bill to the next, so they are shown as the sequence
  // that produced what is on screen rather than as a separate list to be
  // cross-referenced.
  const btBlock=bt?`
    <div class="btver">${chip(bt.version?titleWords(bt.version):"Version Not Stated","btv")}
      ${(bt.in_text||[]).length?`<span class="btamd">includes ${
        bt.in_text.map(a=>esc(a.num)).join(", ")}</span>`:""}</div>
    ${/* The analysis is the first thing on the Summary tab now. It was
           only here, and this block only renders on a focused bill, so a
           card expanded in a list never showed it. */""}
    ${fiscalTable(bt.fiscal)}
    <div class="bttext"><h3>The bill</h3>
      <p class="src">Text in ${"["}brackets] is being removed from current law.
        Text being added is printed in bold italics in the original, and that
        formatting is lost when the page is read as text, so additions are not
        marked here.</p>
      <div class="billbody" translate="no">${billLines(bt.body||"")}</div></div>
    ${amds?`<div class="amdsteps"><h3 class="amdsec">How it got here</h3>
      <p class="note">Each amendment is a step from one version to the next, in
        the order the docket took them up. A committee amendment is considered
        before any floor amendment, and where two change the same section the
        later one governs.</p>${amds}</div>`:""}`
   :(amds?`<p class="note">The text of this bill has not been read into this
       site yet, but the amendments to it have. The Documents tab links to the
       text on the General Court's own site.</p>
       <div class="amdsteps"><h3 class="amdsec">How it got here</h3>${amds}</div>`
     :`<p class="note">The text of this bill has not been read into this site
       yet. The Documents tab links to it on the General Court's own site.</p>`);
  // New Hampshire prints text being REMOVED in square brackets. Text being
  // added is underlined, and underlining does not survive a PDF being read as
  // text -- so deletions can be marked here and additions cannot. That
  // asymmetry is stated rather than left for a reader to discover, because
  // marked deletions invite the assumption that everything unmarked is
  // unchanged, and half of it is new.
  return btBlock;
}

// THE DOCUMENTS TAB, GROUPED (the person's choice A, 14 October 2026): the
// bill's own three links first, then its calendars and its journals, each
// row dated and saying what happened in plain words, the clerk's line under
// them as the citation. The note that opened the tab ("Everything below is
// published by the General Court...") is gone: every row names whose it is.
const DOCSRC={HC:"House Calendar",SC:"Senate Calendar",HJ:"House Journal",SJ:"Senate Journal"};
const docLong=l=>String(l||"").replace(/^(HC|SC|HJ|SJ)\b/,m=>DOCSRC[m]);
const DOCGROUPS=[["bill","The Bill"],["cal","Calendars"],["jour","Journals"],["other","Other Records"]];
function docGroup(x){
  if(x.kind!=="record")return "bill";
  const m=/^(H|S)(C|J)\b/.exec(String(x.label||""));
  return m?(m[2]==="C"?"cal":"jour"):"other";
}
function renderDocuments(b,d){
  const docs=d.documents||[];
  if(!docs.length)return `<p class="note">No official documents on file for this bill yet. The
         bill text and docket links come from the General Court's status page,
         which is fetched separately.</p>`;
  const rows={bill:[],cal:[],jour:[],other:[]};
  docs.forEach(x=>{
    // THE ACTIONS THIS CITATION IS THE RECORD OF. The docket carries the
    // same citation on the event it belongs to, so the two are joined on it
    // -- and a citation covering several actions names all of them, because
    // it is the record of all of them. Where nothing matches, DOCWHAT's
    // sentence stands as it always did.
    // NOT A ROW THAT CALLS A MEETING OFF (e.called_off, 7 October 2026): the
    // docket list shows it with the note that says so, and here, its mark
    // stripped as every line's is, it would read as the notice it cancels.
    const acts=(d.events||[]).filter(e=>e.cite&&e.cite===x.label&&!e.called_off);
    const g=docGroup(x);
    // The day, which the grouped rows show in a column of their own; a key
    // link of the bill's own carries none.
    const of=acts.length?dateWords(acts[0].date):"";
    // Plain words first where the build wrote them, the clerk's line under
    // them as the citation; the line alone where there are none.
    const what=acts.length
      ? `<span class="docacts">${acts.map(e=>e.plain
          ? `<span class="docplain">${esc(e.plain)}</span><span class="docraw" translate="no">${esc(e.text)}</span>`
          : `<span class="docplain">${esc(e.text)}</span>`).join("")}</span>`
      // NOT "the General Court's page saying where the bill stands" where it did
      // not: a bill the House Journal leaves out of those it introduced reads
      // Not introduced here and IN COMMITTEE there.
      : `<span class="${x.kind==="record"?"docacts":"docwhat"}">${x.kind==="status"&&d.status_source==="House Journal"
          ? STATUS_NOT_FROM_PAGE
          : x.kind==="status"&&d.ballot&&!d.ballot.pending
          ? statusUpToTheVoters(d) : (DOCWHAT[x.kind]||"")}</span>`;
    // ONE DOCUMENT ROW, components.doc_row (the plan's step 7).
    rows[g].push(docRow({kind:x.kind,label:x.kind==="record"?docLong(x.label):x.label,
      url:x.url,of,what}));
  });
  return DOCGROUPS.filter(([k])=>rows[k].length).map(([k,h])=>
    `<h2 class="sech docgrp">${h}</h2><ul class="docs docs-${k}">${rows[k].join("")}</ul>`).join("");
}

// The tabs, and one call per pane. Everything this reads is either a
// parameter or the return value of a call made on the line that uses it,
// so there is no declaration here whose order could be got wrong.
