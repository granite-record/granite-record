// ------------------------------------------------ THE ELECTIONS TAB ---
// The general elections on file in which this member is recorded, newest
// first (build_member_elections.py; the owner's design of 10 November 2026).
// m.elections is the list the builder wrote, one row for each election, and
// is absent for a member with no race on file, who has no tab. Official
// figures only: the Secretary of State's counts, in the words the elections
// page uses, each row linked to its race's card there. No margin is named and
// nothing is rated.
function electionOrd(n){
  if(window.GR_LANG==="es")return n+".º";
  const t=n%100, s=(t>=11&&t<=13)?"th":({1:"st",2:"nd",3:"rd"})[n%10]||"th";
  return n+s;
}
function electionRace(r){
  const k=String(r.k||"").split("|"), senate=k[0]==="S";
  const where=senate?tr("race.district","District {n}",{n:esc(k[1])})
    :esc(k[1])+" "+esc(k[2]);
  const seats=r.s===1?tr("race.seat_one","{n} seat",{n:1}):tr("race.seat_many","{n} seats",{n:r.s});
  return `${esc(senate?tr("race.senate","Senate"):tr("race.house","House"))}, ${where}`
    +` <span class="dim">(${seats}${r.fl?", "+esc(tr("race.floterial","floterial")):""})</span>`;
}
// The elections page's own words for a result, each asked for in full so the
// translation can be read from the source.
function electionResult(r){
  const word=r.r==="won"?tr("race.won","Elected"):r.r==="lost"?tr("race.lost","Not elected")
    :r.r==="tie"?tr("race.tie","Tied for the last seat")
    :tr("elect.not_final","Result not final");
  const place=r.pl&&r.of?", "+esc(tr("race.place","{ord} of {n}",
    {ord:electionOrd(r.pl),n:r.of})):"";
  return esc(word)+place
    +(r.r==="open"&&r.rq?" "+tr("elect.recount","&mdash; a recount was requested"):"")
    +(r.rc?` <span class="dim">${esc(tr("race.recounted","Recounted"))}</span>`:"");
}
function electionRow(r){
  const href=`/elections/${esc(r.d)}-general#${esc(r.a)}`;
  const share=r.sh!=null?` <span class="dim">(${esc(r.sh.toFixed(1))}%)</span>`:"";
  return `<tr>
    <td class="d" data-l="${esc(tr("race.col_election","Election"))}"><a href="${href}">${
      esc(dateWords(r.d))}</a></td>
    <td class="b" data-l="${esc(tr("race.col_race","Race"))}">${electionRace(r)}</td>
    <td class="v" data-l="${esc(tr("race.col_result","Result"))}">${electionResult(r)}</td>
    <td class="o" data-l="${esc(tr("race.col_votes","Votes"))}">${esc(r.v.toLocaleString())}${share}</td></tr>`;
}
// The strip's entry, or null: a member with no race on file has no tab,
// rather than an empty one.
function memberElectionTab(m){
  const n=(m.elections||[]).length;
  return n?[tr("race.tab","Elections"),n]:null;
}
// A race as its card (the owner, 18 November 2026): "c" is the card the
// elections page draws, written by build_elections.race_card with the
// member's own row marked er-me; headed here by the election's day, linked to
// the race on that page as the row was.
// A primary (the owner, 19 November 2026) is headed by its party's ballot and
// its day, and links nowhere: no page of the primaries is built yet. A special
// election (the owner's "Yes to all 9", the same day) is headed "Special
// election" and its day, a tie's re-run saying so; its primary "Special
// primary" and its party's ballot; neither links anywhere on this site.
function electionCard(r){
  const href=`/elections/${esc(r.d)}-general#${esc(r.a)}`;
  const ballot=r.pp==="D"?tr("race.primary_d","Democratic primary"):r.pp==="R"
    ?tr("race.primary_r","Republican primary"):tr("race.primary_l","Libertarian primary");
  const sballot=r.pp==="D"?tr("race.special_primary_d","Special primary (Democratic)"):r.pp==="R"
    ?tr("race.special_primary_r","Special primary (Republican)"):tr("race.special_primary","Special primary");
  const tie=r.tie?", "+tr("race.special_tie","held after the {year} tie (House Resolution {n})",
    {year:r.tie.y,n:r.tie.hr}):"";
  const when=r.st==="primary"?`<p class="er-when">${esc(ballot)}, ${esc(dateWords(r.d))}</p>`
    :r.st==="special"?`<p class="er-when">${esc(tr("race.special","Special election"))}, ${esc(dateWords(r.d))}${esc(tie)}</p>`
    :r.st==="special-primary"?`<p class="er-when">${esc(sballot)}, ${esc(dateWords(r.d))}</p>`
    :`<p class="er-when"><a href="${href}">${esc(dateWords(r.d))}</a></p>`;
  return electionIncumbent(String(r.c),r.k).replace(/^<article\b[^>]*>/,m=>m+when);
}
// THE INCUMBENT CHIP (the owner, 21 November 2026, in place of the asterisk and its
// line under the cards): build_elections.inc_chip writes it into the card in English,
// beside the candidate's name; here its word and its title are the page's language's.
// The race's chamber is the first letter of its key, as the card's own is. Only the
// title and the word are put in: the chip itself stays the card's.
function electionIncumbent(card,k){
  const say=String(k||"").startsWith("S|")
    ?tr("race.incumbent_s","Held a seat in the Senate on election day.")
    :tr("race.incumbent_h","Held a seat in the House on election day.");
  return card.replace(/(<span class="[^"]*\ber-incb" title=")[^"]*(">)[^<]*(?=<\/span>)/g,
    (_m,a,b)=>a+esc(say)+b+esc(tr("race.incumbent","Incumbent")));
}
// UPCOMING ELECTIONS (the owner, 19 November 2026, "Yes to all 9" of the
// specials and upcoming elections design, A3): m.up, the seat the member holds
// in the term the next general election ends and that election's filing
// period, primary and general, each a day key_dates works out from the law in
// force on it, with its section (build_member_elections.upcoming). Above the
// newest cycle, as the newest thing on the tab. Never who is running.
// build_legislator_pages.upcoming_html draws the same for a new member-elect.
function electionUpcomingLaw(e){
  const law=e.href?`<a href="${esc(e.href)}">RSA ${esc(e.sec)}</a>`:`RSA ${esc(e.sec)}`;
  return e.act&&e.from?tr("race.up_amended","{law}, as amended by {act}, from {date}",
    {law:law,act:esc(e.act),date:esc(dateWords(e.from,"full"))}):law;
}
function electionUpcoming(u){
  if(!u||!(u.e||[]).length)return "";
  const name={filing:tr("race.up_filing","Filing period for the primary"),
    primary:tr("cal.kd.state_primary","State primary"),general:tr("cal.kd.general_election","General election")};
  const rows=u.e.map(e=>`<li><span class="er-up-d">${esc(e.u?dateSpan(e.d,e.u,"medium"):dateWords(e.d))}</span>
      <span class="er-up-w">${esc(name[e.w]||e.w)}</span> <span class="er-up-law">${electionUpcomingLaw(e)}</span></li>`).join("");
  return `<h3 class="er-cycle">${esc(tr("race.up_head","Upcoming elections"))}</h3><div class="er-cards er-stack">`
    +`<article class="er-race er-up"><div class="er-hd"><h4>${electionRace(u)}</h4></div>`
    +`<ul class="er-up-rows">${rows}</ul></article></div>`;
}
// A PRIMARY BESIDE ITS GENERAL (the owner, 21 November 2026: "group the primary and the
// general election in two columns side by side so that the left is the primary and the
// right is the general"). A cycle's rows, newest first, as pairs: each general with the
// member's primary of the same race, each special election with its special primary;
// a primary of no general on the tab, or a general of no primary, a pair of one. The
// primary is always the left cell and the general the right, so a pair of one keeps its
// card in its own column ("Keep the columns aligned down the page", her answer the same
// day). On a phone the cells stack, the primary first (app.css, .er-pairs).
function electionPairs(rows){
  const pairs=[];
  for(const r of rows){
    const first=r.st==="primary"||r.st==="special-primary";
    const kin=r.st==="special"||r.st==="special-primary"?"special":"general";
    const mate=first&&pairs.find(p=>p.g&&!p.p&&p.kin===kin&&p.g.k===r.k);
    if(mate)mate.p=r;
    else pairs.push(first?{kin,p:r,g:null}:{kin,p:null,g:r});
  }
  return pairs;
}
function renderMemberElections(m){
  const rows=m.elections||[];
  if(!rows.length)return "";
  const prim=[...new Set(rows.filter(r=>r.st==="primary").map(r=>r.d.slice(0,4)))].join(", ");
  const days=[...new Set(rows.filter(r=>!r.st).map(r=>r.d))];
  // The special elections, each its Secretary of State page.
  const sp=rows.filter(r=>r.st==="special"&&r.u);
  const spsrc=sp.map(r=>`<a href="${esc(r.u)}">${esc(tr("race.special_of","special election of {date}",
    {date:dateWords(r.d)}))}</a>`).join(", ");
  const src=days.map(d=>`<a href="/elections/${esc(d)}-general">${esc(
    tr("race.year","{year} general election",{year:d.slice(0,4)}))}</a>`).join(", ");
  // A row with no card (a file written before the cards) keeps the table.
  const cards=rows.filter(r=>r.c), plain=rows.filter(r=>!r.c);
  // A HEADING FOR EACH ELECTION CYCLE (the owner, 19 November 2026): the rows come
  // newest first (build_member_elections.sort_rows), a cycle's general and then its
  // primary; a special carries its cycle in "cy". Under it each primary beside its
  // general (electionPairs), a cell with no card left empty; a tab with no primary at
  // all is one column the tab's full width, as it was.
  const cyc=[...new Set(cards.map(r=>r.cy||r.d.slice(0,4)))];
  const two=cards.some(r=>r.st==="primary"||r.st==="special-primary");
  const cell=r=>r?electionCard(r):`<div class="er-gap" aria-hidden="true"></div>`;
  const stack=cyc.map(y=>{
    const rs=cards.filter(r=>(r.cy||r.d.slice(0,4))===y);
    return `<h3 class="er-cycle">${esc(y)}</h3>`+(two
      ?`<div class="er-cards er-pairs">${electionPairs(rs).map(p=>cell(p.p)+cell(p.g)).join("")}</div>`
      :`<div class="er-cards er-stack">${rs.map(electionCard).join("")}</div>`);
  }).join("");
  return `<p class="src">${tr("race.intro","The general elections on file in which this member is recorded, newest first, as the Secretary of State counted them. In a race for one seat a share is of every vote cast, write-ins included; in a race for more than one, where each voter could choose several, it is of all the votes cast for the candidates listed.")}${prim?" "+tr("race.intro_primary","A primary is shown on the member&rsquo;s own party&rsquo;s ballot, first, with that year&rsquo;s general election beside it; a candidate it nominated is marked Nominated."):""}${sp.length?" "+tr("race.intro_special","A special election is shown under the election cycle of the term whose seat it filled, by its date, with its primary first, beside it."):""}</p>
    ${electionUpcoming(m.up)}${stack}${plain.length?`
    <table class="votes vfull"><thead><tr><th>${esc(tr("race.col_election","Election"))}</th>
      <th>${esc(tr("race.col_race","Race"))}</th><th>${esc(tr("race.col_result","Result"))}</th>
      <th>${esc(tr("race.col_votes","Votes"))}</th></tr></thead>
      <tbody>${plain.map(electionRow).join("")}</tbody></table>`:""}
    <p class="src">${tr("race.omitted","A race this member lost appears only where the name and the district match the record exactly, or but for a middle initial; any other is left off.")}
      ${days.length?tr("race.source","Source: the New Hampshire Secretary of State&rsquo;s official results, shown on the elections pages: {years}. Each row links to its race there.",{years:src}):""}${prim?" "+tr("race.source_primary","The primaries are from the Secretary of State&rsquo;s State Primary results files: {years}; no page of them is on this site yet.",{years:esc(prim)}):""}${sp.length?" "+tr("race.source_special","The special elections are from the Secretary of State&rsquo;s page of each: {list}.",{list:spsrc}):""}</p>`;
}

function renderMember(m){
  const election=memberElectionTab(m);
  // An address for a tab this member has none of lands on their first.
  if(PAGE_TAB===MEMBER_TABS.elections&&!election){PAGE_TAB=0;tabAddress("");}
  const tabs=[["Prime sponsored",memberBills(m,true).length],
              ["Co-sponsored",memberBills(m,false).length],
              ["Votes",memberVotes(m).length]];
  if(election)tabs.push(election);
  const body=[()=>renderMemberBills(m,true),()=>renderMemberBills(m,false),
              ()=>renderMemberVotes(m),()=>renderMemberElections(m)][PAGE_TAB]||(()=>"");
  // The term under the head, because it governs the figures and every tab,
  // and the figures above the tabs, because they are about the member rather
  // than about any one tab. The line saying so is said only beside the
  // picker it is about (the audit of 25 October 2026, S7): a member of one
  // term has none, and the line spoke of a control that was not there. The
  // box stays, for the rule it draws between the head and the figures.
  const picker=termControl();
  return renderMemberHead(m) + `<div class="mterm">${picker}${picker?`<p class="src">The figures,
    bills and votes follow the term.</p>`:""}</div>` + termGlance(m,pageTerm())
    + tabStrip(tabs) + pagePane(body());
}

