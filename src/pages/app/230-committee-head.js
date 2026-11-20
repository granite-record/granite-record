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

