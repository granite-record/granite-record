// ===================================================== POLISH 2: A MEMBER
//
// THE MEMBER'S HEAD (the record head, C6; the person's feedback of 9 October
// 2026, item 10: "Member pages should list their title along with their name
// at the top like Senator Sharon Carson or Representative James Spillane",
// the Senate President indicated as the Speaker is). The trail, the title
// and name in full in the h1 beside a bar in their party's ink, one line --
// the office the record names them to, the party, the seat and its towns --
// the facts (committees, seat, email, phone, the years on record), and the
// actions. A member who has left is "Former Representative ..." and the line
// says the page is their record, not a directory entry; it never says why
// they left.
const PARTY_WORD={R:"Republican",D:"Democrat",I:"Independent",L:"Libertarian"};
const seatName=m=>m.chamber==="S"?(m.district?`Senate District ${m.district}`:"")
  :([m.county,m.district?`District ${m.district}`:""].filter(Boolean).join(" "));
function renderMemberHead(m){
  const former=!!(m.former||window.GR_FORMER);
  const yrs=former?servedYears(m):"";
  const plain=String(m.display_plain||String(m.display_full||m.display||m.name||"")
    .replace(/\s+\([^()]*\)$/,""));
  // A MEMBER THE ELECTION SENT BACK, WHILE THE MEMBERS-ELECT FILE LASTS
  // (the owner, 13 November 2026). build_legislator_pages hands GR_ELECT the
  // member's id, the race, and for two kinds of member the page's form:
  //   returning -- a former member elected again: headed as a new
  //     member-elect's page is ("Benjamin Baroody (D)", "Member-elect of the
  //     New Hampshire House of Representatives, Hillsborough 16.", the
  //     election's line), the earlier seat kept in the facts below;
  //   chamber -- a sitting member elected to the other chamber: headed as
  //     that chamber's member-elect, "Senator-elect Laura Telerski (D)"
  //     (the owner, 17 November 2026: 'link the new member pages as Sen.
  //     "Elect" Laura Telerski for the title but connect it to their house
  //     record as well'), the page their House record, its line the seat
  //     they hold now, named by its office, with the same sentence beside it.
  // Both end on the day they take office, by the reader's own clock as well
  // as the build's (components.js's untilAttrs): from then on the page is
  // the member's as before.
  const EG=window.GR_ELECT;
  const electLive=!!(EG&&String(EG.id)===String(m.id)&&EG.where&&(()=>{
    const d=new Date(),t=d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"
      +String(d.getDate()).padStart(2,"0");
    return t<String(EG.takes_office||"").slice(0,10);})());
  const retPage=electLive&&EG.mode==="returning", chamPage=electLive&&EG.mode==="chamber";
  // TITLED AS A MEMBER-ELECT (the owner, 16 November 2026): GR_ELECT's title,
  // "Rep.-elect", which fullTitle spells out, as build_legislator_pages.
  // elect_heading heads a new member-elect's page.
  const named=(retPage||chamPage)?(EG.title?String(EG.title)+" ":"")+String(EG.name||plain)+(EG.party?` (${EG.party})`:"")
    :former&&/^(Rep|Sen)\. /.test(plain)?"Former "+plain:plain;
  // The party from the record's own label where the file names none: "(R -
  // Rock 16)" is a Republican's. ON A RETURNING MEMBER'S PAGE, THE ELECTION'S
  // (the review before the release of 16 November 2026): the heading is
  // "Maria Perez (D)", the party she was elected under, and its bar was drawn
  // in the Independent ink of her earlier record. The Earlier seat below keeps
  // the record's own label, "(I - Hills 43)".
  const tagp=/\(([A-Z])[A-Za-z]* - [^()]*\)\s*$/.exec(String(m.display_full||m.display||""));
  const egp=retPage?String(EG.party||"").trim().toUpperCase():"";
  const code=/^[A-Z]$/.test(egp)?egp
    :String(m.party_code||m.party||(tagp?tagp[1]:"")).toUpperCase().slice(0,1);
  const towns=m.towns||[];
  // EACH TOWN TO ITS PAGE, WHERE IT HAS ONE (the audit of 25 October 2026,
  // S6): GR_TOWNS is {town: address} from build_legislator_pages.towns_linked,
  // and a place the roster spells otherwise than the district maps stays words.
  const tp=window.GR_TOWNS||{};
  const place=t=>tp[t]?`<a href="${esc(tp[t])}">${esc(t)}</a>`:esc(t);
  // A member elected to the other chamber: the seat they hold now named by its
  // office, as the record they are joined to has it ("Representative for
  // Hillsborough District 11"), since the heading names the other chamber.
  const nowOffice=chamPage?(m.chamber==="S"?"Senator for ":"Representative for "):"";
  const line=(retPage?[esc(EG.where)]:[m.office?`<b>${esc(m.office)}</b>`:"",esc(PARTY_WORD[code]||m.party||""),
    // The seat's number held to its name: "Senate District" over "14" at 768px.
    (seatName(m)?esc(nowOffice):"")+esc(seatName(m)).replace(/ (?=\S+$)/,"&nbsp;"),
    former?"":joinList(towns.map(place),"and"),
    chamPage?esc(EG.where):""])
    .filter(Boolean)
    // Each dot holds to the words before it, so a wrapped line never opens on
    // one (a phone, 10 October 2026: "· Senate District 14").
    .join("&nbsp;&middot; ");
  // The years on record, by chamber: the record's own service where the
  // member sat in both, else the terms their attendance is counted in -- each
  // term its own, those that run into each other joined, and a term with no
  // roll call a gap, never bridged (the owner's rule for the 1990s, applied
  // after 1999 on 15 November 2026; member_links.record_spans is the twin).
  const yrsOf=t=>t.map(x=>String(x).split("-").map(Number)).filter(x=>x[0]);
  const att=yrsOf(Object.keys(m.attendance||{}));
  const runs=(ch,list)=>{const tm=y=>y%2?y:y-1,out=[];
    list.map(x=>[x[0],x[1]||x[0]]).sort((x,y)=>x[0]-y[0]||x[1]-y[1]).forEach(x=>{const l=out[out.length-1];
      if(l&&tm(x[0])<=tm(l[1])+2)l[1]=Math.max(l[1],x[1]);else out.push([x[0],x[1]]);});
    return {chamber:ch,spans:out};};
  const spans0=(m.service||[]).length?m.service
    :att.length?[runs(m.chamber,att)]:[];
  // THE TERMS BEFORE 1999 THE GENERAL COURT'S SPONSOR RECORD PLACES THEM IN
  // (past_terms: {chamber: [term]}; member_links.record_spans is this one's
  // twin), each added to its own chamber, so the line covers every term the TERM
  // picker offers -- and the terms the Manual for the General Court seats them
  // in with no bill that term (the owner, 14 November 2026; build_site_v2.
  // manual_seats), which the picker does not. The years since 1999 are spans0's
  // runs of terms, or each chamber's own spans where a service list joins two.
  // A 1989-1998 term joins it, or another 1990s term, only where the terms run
  // into each other; a term the record lacks between a 1990s run and the rest
  // is shown as a gap, never bridged ("House, 1989–1990, 2003–2010").
  const pastT=m.past_terms||{};
  const spans=(()=>{
    if(!Object.keys(pastT).length)return spans0;
    let base=spans0;
    if(!base.length){
      const sv=m.served||{},a=String(sv.first||"").slice(-4),b=String(sv.last||"").slice(-4);
      if(/^\d{4}$/.test(a)&&/^\d{4}$/.test(b))base=[{chamber:m.chamber,spans:[[+a,+b]]}];
    }
    const tm=y=>y%2?y:y-1;
    const chs=[...new Set([...base.map(c=>c.chamber),...Object.keys(pastT)])];
    return chs.map(ch=>{
      const own=base.filter(c=>c.chamber===ch).flatMap(c=>c.spans||[]).map(x=>[x[0],x[1]]);
      const past=(pastT[ch]||[]).map(t=>{const y=String(t).split("-").map(Number);return [y[0],y[1]||y[0]];});
      let sp=own.concat(past).sort((x,y)=>x[0]-y[0]||x[1]-y[1]);
      const out=[];sp.forEach(x=>{const l=out[out.length-1];
        if(l&&tm(x[0])<=tm(l[1])+2)l[1]=Math.max(l[1],x[1]);else out.push([x[0],x[1]]);});sp=out;
      return {chamber:ch,spans:sp};
    }).sort((x,y)=>x.spans[0][0]-y.spans[0][0]||(x.chamber===m.chamber?0:1)-(y.chamber===m.chamber?0:1));
  })();
  const svc=spans.map(c=>`${esc(CHAMBER_SHORT[c.chamber]||c.chamber)}, ${(c.spans||[])
    .map(([a,b])=>a===b?esc(String(a)):`${esc(String(a))}&ndash;${esc(String(b))}`).join(", ")}`);
  const facts=[];
  if((m.committees||[]).length)facts.push([m.committees.length>1?"Committees":"Committee",
    m.committees.map(c=>cmteLink((m.chamber==="S"?"Senate ":"House ")+c,"",META.committee_codes))
      .join(" &middot; ")]);
  // The seat they held, as the record labelled it at the time.
  if(retPage)facts.push(["Earlier seat",esc(String(m.display_full||m.display||plain))]);
  if(m.seat)facts.push(["Seat",esc(plate(m.seat))]);
  if(!former&&m.email)facts.push(["Email",`<a href="mailto:${esc(m.email)}">${esc(m.email)}</a>`]);
  // No Phone: a legislator's number is not published (build_site_v2, 22 October 2026).
  if(svc.length)facts.push(["On Record",svc.join(" &middot; ")]);
  else if(yrs)facts.push(["On Record",esc(yrs)]);
  // OFFICIALS, where Legislators was (decision 127, 8 October 2026: the
  // Legislators page is the Officials page, and /legislators 301s to it).
  // A MEMBER WHO HAS LEFT, THROUGH THE LIST OF THOSE WHO HAVE (the audit of
  // 25 October 2026, S6): Officials lists only sitting members.
  // THE LAST STEP IS THE OFFICE ALONE (the owner, 26 October 2026): the step
  // before it already says Former Legislators, and "Officials › Former
  // Legislators › Former Representative" said "former" twice. The heading
  // under the trail still says "Former Representative ...".
  const head=recordHead({trail:[["Officials","officials"],
      ...(former&&!retPage?[["Former Legislators","directory/former-legislators"]]:[]),
      [retPage?"Member-elect":m.chamber==="S"?"Senator":"Representative",""]],
    title:esc(fullTitle(named)),line,facts,rail:"",actions:"",kind:`member rh-p${code||"X"}`});
  // Not while the member-elect form shows: it contradicts the heading.
  const note=former&&!retPage?`<p class="rnote">${!/^(Rep|Sen)\. /.test(plain)?`Former member${
    yrs?` &middot; on record ${esc(yrs)}`:""}. `:""}This page is their record in the
    General Court; it is not a current directory entry.</p>`:"";
  // A MEMBER-ELECT'S ONE LINE (the person's decisions of 16 October 2026):
  // "Elected November 3, 2026, for Rockingham district 13. Takes office
  // December 2, 2026.", which build_legislator_pages hands this page in
  // GR_ELECT from site/members_elect.json, and only on the page of the
  // member it names -- so the id is held to the record being drawn, and a
  // reader who goes on to another member here is shown nothing of it.
  // components.js's electLine, handed no day, leaves the retiring to the
  // reader's clock. The heading above is left as it is until they sit.
  const G=window.GR_ELECT;
  // A returning member's is the new member-elect's: no "for <district>", the
  // sentence under their name says the seat.
  const elect=G&&typeof electLine==="function"&&String(G.id)===String(m.id)
    ?electLine(retPage?null:G.key,G.election,G.takes_office,null):"";
  return head+note+elect;
}

// THE TERM AT A GLANCE (the person's feedback of 9 October 2026, item 7:
// "the selected term's attendance, then attendance on roll calls, then the
// number of bills filed and the number passed, in the selected term"; v7:
// "'bills filed' counts every bill filed, prime and co-sponsor together;
// 'bills passed' the same"). The figures are the build's (member_figures,
// term_figures); attendance is as member_attendance has always counted it,
// and how is said in a fold under the figures. A term with no roll call on
// record (before 1999) says so where the attendance would be.
function termGlance(m,t){
  // A term of requests has no days, roll calls or bills passed to show.
  if(isReqTerm(t))return "";
  const f=(m.term_figures||{})[t]||null, a=(m.attendance||{})[t]||null;
  if(!f&&!a)return attendanceBlock(m.attendance,t);
  const num=n=>Number(n||0).toLocaleString();
  const fig=(big,lab,small)=>`<div class="mf"><b>${big}</b><span>${lab}</span>${small?`<small>${small}</small>`:""}</div>`;
  const took=r=>(r.voted||0)+(r.presided||0)+(r.conflict||0);
  const att=a?fig(`${pctOf(a.attended,a.days)}%`,"of session days attended",
      `${num(a.attended)} of ${num(a.days)} days &middot; absent ${num(a.days-a.attended)}`)
    +fig(`${pctOf(took(a),a.roll_calls)}%`,"of roll calls taken part in",
      `${joinList([`Voted on ${num(a.voted)}`,...(a.presided?[`presided over ${num(a.presided)}`]:[]),
        ...(a.conflict?[`declared a conflict on ${num(a.conflict)}`]:[])],"and")} of ${
        num(a.roll_calls)} &middot; missed ${num((a.roll_calls||0)-took(a))}`)
    :`<p class="mfnone">No roll call is on record for them in ${esc(termDash(t))}${
      parseInt(t,10)<1999?"; the record of roll calls begins in 1999":""}.</p>`;
  const bills=f?fig(num(f.bills_filed),`bill${f.bills_filed===1?"":"s"} filed`,
      `${num(f.prime)} as prime sponsor, ${num(f.cosponsored)} co-sponsored`)
    +fig(num(f.bills_passed),"passed",f.bills_filed?`of the ${num(f.bills_filed)} filed${
      f.became_law?` &middot; ${num(f.became_law)} became law`:""}`:""):"";
  // The fold: every term's attendance together, and how each figure is counted.
  const note=`<p class="pattnote">Bills filed counts every bill the member put their
      name to in the term, as prime sponsor or co-sponsor, each once; passed counts those
      of them that became law, were adopted, or were ratified by the voters.</p>`;
  const how=attendanceBlock(m.attendance,"",note)||`<div class="patt">${note}</div>`;
  return `<section class="mfig" aria-labelledby="mfh"><h2 class="mfh" id="mfh">In the ${esc(termDash(t))} Term</h2>
    <div class="mfgrid"><div class="mfgrp"><h3>Attendance</h3><div class="mfrow">${att}</div></div>${
      bills?`<div class="mfgrp"><h3>Bills</h3><div class="mfrow">${bills}</div></div>`:""}</div>
    <details class="mfhow"><summary>How this is counted</summary>${how}</details>
  </section>`;
}

