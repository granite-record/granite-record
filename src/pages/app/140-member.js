// ---------------------------------------------------------------- member ---
// ONE PERSON, TWO CHAMBERS. A member who moves between the House and the
// Senate is given a new number there, and until 13 September a page showed the
// votes cast under one of them: Sen. Cindy Rosenwald's carried 1,399 of her
// 4,218. The build joins the numbers now (member_links.py says on what
// evidence), and this line says which years are which, so a House vote on a
// senator's page reads as her record rather than as a mistake. Years with a
// recorded roll call, not years in office: that record begins in 1999.
const CHAMBER_SHORT={H:"House",S:"Senate"};
function serviceLine(m){
  const s=m.service||[];
  if(s.length<2)return "";
  // A chamber and its years are one phrase: at 360px "Senate" ended one line
  // and "2019–2026" began the next.
  return `<p class="pserv"><b>Votes on record</b> ${s.map(c=>
    `<span class="svc">${esc(CHAMBER_SHORT[c.chamber]||c.chamber)} ${(c.spans||[]).map(([a,b])=>
      a===b?esc(String(a)):`${esc(String(a))}&ndash;${esc(String(b))}`).join(", ")}</span>`)
    .join(" &middot; ")}</p>`;
}

/* ATTENDANCE, AS THE PERSON DEFINED IT (23-24 September). Two figures, kept
   apart: the days the member's chamber held at least one roll call while they
   held the seat, attended where they voted on any of that day's roll calls;
   and the roll calls held while they sat, against those they voted on.
   build_site_v2.member_attendance counts both per term from the ballots, which
   list every seated member, so an arrival at a special election starts at
   their first roll call and a departure stops at their last.

   A FIGURE ON THIS PAGE AND NOWHERE ELSE: not a column in any list, not a
   rank, and not a colour -- ninety per cent is drawn exactly as a hundred is.
   Presiding is counted as present, as the Votes tab already says it is ("not
   a missed vote"), and so is a declared conflict of interest, a member in the
   room standing aside from one question; each is named where it happened.
   What is missed is not split into excused and not excused: the person chose
   (24 September) that an absence is an absence here, and the Votes tab keeps
   the two labels on each roll call. No note about part days: the person
   asked for none. */
const pctOf=(a,b)=>{
  // Never a rounded 100 beside an absence, nor a rounded 0 beside a vote.
  if(!b||!a)return 0;
  if(a>=b)return 100;
  return Math.max(1,Math.min(99,Math.round(100*a/b)));
};
// "a, b and c", "a or b".
const joinList=(xs,and)=>xs.length>1?`${xs.slice(0,-1).join(", ")} ${and} ${xs[xs.length-1]}`
  :(xs[0]||"");
// `more`: what a caller adds at the end of the block (termGlance's note on
// how bills are counted).
function attendanceBlock(att,t,more){
  const terms=Object.keys(att||{}).sort();
  if(!terms.length)return "";
  const num=n=>Number(n||0).toLocaleString();
  const span=x=>esc(String(x)).replace("-","&ndash;");
  const sum=k=>terms.reduce((s,x)=>s+(Number(att[x][k])||0),0);
  const took=r=>(r.voted||0)+(r.presided||0)+(r.conflict||0);
  // `what` is "in 2025&ndash;2026" under a label that already says days or
  // roll calls, and the noun itself on the line that totals every term.
  const days=(r,what)=>`attended ${num(r.attended)} of ${num(r.days)} ${what} (${
    pctOf(r.attended,r.days)}%)`;
  const calls=(r,what)=>`${joinList([`voted on ${num(r.voted)}`,
      ...(r.presided?[`presided over ${num(r.presided)}`]:[]),
      ...(r.conflict?[`declared a conflict of interest on ${num(r.conflict)}`]:[])],"and")
    } of ${num(r.roll_calls)} ${what} (${pctOf(took(r),r.roll_calls)}%)`;
  const out=[];
  const r=att[t];
  if(r){
    out.push(`<p><b>Days</b> ${days(r,`in ${span(t)}`)} &middot; absent ${
      num(r.days-r.attended)}</p>`);
    out.push(`<p><b>Roll calls</b> ${calls(r,`in ${span(t)}`)} &middot; missed ${
      num((r.roll_calls||0)-took(r))}</p>`);
  }else if(t){
    // A term the member sponsored in and has no ballot for. Before 1999 that
    // is every term, because the record of roll calls starts there.
    out.push(`<p><b>Attendance</b> no roll call is on record for them in ${span(t)}${
      parseInt(t,10)<1999?"; the record of roll calls begins in 1999":""}.</p>`);
  }
  if(terms.length>1){
    const tot={days:sum("days"),attended:sum("attended"),roll_calls:sum("roll_calls"),
               voted:sum("voted"),presided:sum("presided"),conflict:sum("conflict")};
    out.push(`<p><b>All ${terms.length} terms</b> ${days(tot,"days")} &middot; ${
      calls(tot,"roll calls")}</p>`);
  }
  const chs=new Set(terms.flatMap(x=>String(att[x].chambers||"").split("")).filter(Boolean));
  const where=chs.size===1?(chs.has("S")?"the Senate":"the House"):"their chamber";
  const acts=joinList(["voted on",...(sum("presided")?["presided over"]:[]),
    ...(sum("conflict")?["declared a conflict of interest on"]:[])],"or");
  out.push(`<p class="pattnote">A day counts when ${where} held at least one roll
    call while they held the seat, and is attended if they ${acts} any roll call
    that day. Voice votes record no names, so they are not counted.</p>`);
  return `<div class="patt">${out.join("")}${more||""}</div>`;
}

/* "2013 to 2026", from the first and last roll call the member appears in.
   The record's own answer to when somebody served, and the only one it can
   give: the roster carries no dates. One year where both ends fall in it,
   because "2026 to 2026" reads as a fault rather than as a fact. */
function servedYears(m){
  const s=m.served||{};
  const a=String(s.first||"").slice(-4), b=String(s.last||"").slice(-4);
  if(!/^\d{4}$/.test(a)||!/^\d{4}$/.test(b))return "";
  return a===b?a:`${a} to ${b}`;
}

/* THE TITLE IN FULL AT THE TOP OF THE PAGE (the person, 9 October 2026:
   "Member pages should list their title along with their name at the top
   like Senator Sharon Carson or Representative James Spillane"). The
   heading spells out the honorific every list on the site abbreviates --
   "Rep." is Representative and "Sen." Senator, the roster's own title for
   each -- and keeps the party and seat after the name, the one place the
   page gives them. A member who has left is "Former Representative ...":
   the word still joins the honorific. The office a member holds is the line
   under it. build_legislator_pages.head_name writes the page's heading for a
   reader without JavaScript the same way; the page's title, its link card
   and every list keep the short form. */
const HONORIFIC_FULL={"Rep.":"Representative","Sen.":"Senator"};
const fullTitle=who=>String(who||"").replace(/^(Former )?(Rep\.|Sen\.)(-elect)? /,
  (_,f,h,e)=>`${f||""}${HONORIFIC_FULL[h]}${e||""} `);


const memberBills=(m,prime)=>(m.sponsored||[])
  .filter(b=>!!b.prime===prime)
  .filter(b=>!pageTerm()||b.term===pageTerm())
  .map(idxRow);

// NEXT SESSION'S REQUESTS ON A MEMBER'S PAGE (Alice, 7 November 2026): until
// the bills are introduced in January, a member's requests are that term's
// "bills", as build_lsrs matched them (sponsor_slug, one sitting member of the
// name). AND THE ONES THEY CO-SPONSOR (24 November 2026): a request names its
// co-sponsors where the General Court's results page does, so the co-sponsored
// tab lists those naming this member's page among them, as it lists a
// member's co-sponsored bills; until then it said none could be co-sponsored.
const isReqTerm=t=>!!(META.requests&&t&&t===META.requests.term);
const termLabel=t=>isReqTerm(t)?(META.requests.label||`${reqYear()} Bill Requests`):termDash(t);
const memberRequests=(m,prime=true)=>IDX.filter(b=>b.lsr&&isReqTerm(b.term)&&m.slug&&(prime
  ?b.sponsor_slug===m.slug:(b.cosponsors||[]).some(c=>c.slug===m.slug)));
function renderMemberRequests(m,prime){
  // Not "none" before the list has come: the page is drawn before
  // idx/<year>-requests.json is fetched (ensureTerm), and again after.
  if(!LOADED.has(META.requests.term))return `<p class="src">Loading the bill requests&hellip;</p>`;
  const rows=memberRequests(m,prime);
  if(!rows.length)return `<p class="src">${prime?`No bill requests for ${esc(reqYear())}.`
    :tr("req.none_cosponsored","No bill requests co-sponsored for {year}.",{year:esc(reqYear())})}</p>`;
  const left=rows.filter(b=>b.withdrawn).length;
  // Alice's two sentences, the bill search's own note (bills.requests_note),
  // and then how many are this member's.
  return `<p class="src lsrnote">${tr("bills.requests_note","<b>Requests, not bills yet.</b> Each one, called an LSR (Legislative Service Request), is a member&rsquo;s request to have a bill drafted: a title and a sponsor, nothing more, until it is filed as a numbered {year} bill. Some are withdrawn first.",{year:esc(reqYear())})}
    ${prime?`${rows.length.toLocaleString()} filed for ${esc(reqYear())}`
    :tr("req.n_cosponsored","{n} co-sponsored for {year}",{n:rows.length.toLocaleString(),year:esc(reqYear())})}${
    left?`, ${left.toLocaleString()} of them withdrawn`:""}.</p>
    <div class="cards" id="pbills">${rows.map(b=>lsrCardHtml(b,"")).join("")}</div>`;
}

function renderMemberBills(m, prime){
  if(isReqTerm(pageTerm()))return renderMemberRequests(m,prime);
  // A member's own bills name no prime sponsor on their cards: it is the
  // member whose page this is, as the approved prototype draws them (10
  // October 2026). A co-sponsored bill's card names its prime sponsor.
  const rows=memberBills(m,prime).map(b=>prime?Object.assign({},b,{_self:true}):b);
  const t=pageTerm();
  if(!rows.length)return `<p class="src">No bills ${prime?"prime sponsored"
    :"co-sponsored"} in the ${esc(termDash(t))} term.</p>`;
  return billPane(rows,(n,of)=>`${billsOf(n,of)}${
    prime?" prime sponsored":" co-sponsored"} in ${esc(termDash(t))}. Sponsoring a bill is
    putting a name to it, which is not the same as voting for it and is not
    counted as one here.`);
}

// THE TERM A VOTE BELONGS TO IS THE ONE IT WAS CAST IN. This read the
// bill's FILING year, which about three votes in every hundred do not have
// -- a call of the roll or a rules suspension is recorded against no bill --
// and a row with no year passed every term's filter. So a procedural vote
// taken in August 2026 was listed among the same member's 2023-2024 votes,
// and counted in that term's total. The roll call's own year is the first
// field of its key. Checked across 55,522 votes: no vote's roll call year
// and bill year fall in different terms, so nothing else moves.
//
// A row with neither is still shown rather than silently dropped.
const voteYear=x=>x.y||String(x.k||"").split("-")[0];
// The chamber a vote was cast in and its day, as a sitting's address names
// them: the key is "2026-H-302" and the date "8/19/2026".
const voteChamber=x=>String(x.k||"").split("-")[1]||"";
const voteIso=x=>{
  const m=/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(String(x.d||""));
  return m?`${m[3]}-${m[1].padStart(2,"0")}-${m[2].padStart(2,"0")}`:"";};
// The term shown, or every term where the reader has asked for them all
// (PAGE.vall; "?term=all" in the address, as /bills names it).
const memberVotes=m=>(m.votes||[]).filter(x=>{
  const y=voteYear(x);
  return PAGE.vall||!pageTerm()||!y||termOfYear(y)===pageTerm();});

// THE VOTES TAB'S SEARCH IS THE BILL SEARCH (the person, 7 November 2026: "a
// bill number or words, with the bill search's own matching"). This tab had a
// matcher of its own, a substring test over the title and the question, which
// found "housing" in a title and missed what /bills lists for it: the
// synonyms, the bills whose analysis or text say it, a bill number's exact
// form. Now a vote is asked of billNumbers, queryGroups, readShort and
// matchesGroups -- the functions /bills, the header and /search ask -- over
// the bill the vote was on, with the bills' text (sidx) fetched by the same
// loader. A vote on no bill is asked about the words the Journal gives it.
const voteNorm=s=>String(s||"").toLowerCase().replace(/-/g," ");
let VG_KEY=null,VG=[];
function voteGroups(q,rows){
  const key=[q,rows.length,TEXTGEN].join("\u0001");
  if(key!==VG_KEY){VG_KEY=key;VG=readShort(queryGroups(q),rows);}
  return VG;
}
// The row a vote is matched as: the bill's index row where this page holds
// it, else what the vote itself says. Null where there is nothing to ask.
function voteSubject(r){
  if(r.b&&r.b.hayT)return r.b;
  const t=r.x.y?termOfYear(r.x.y):termOfYear(voteYear(r.x));
  const title=r.b?r.b.title:[r.rc&&r.rc.w,r.rc&&r.rc.q,r.x.q].filter(Boolean).join(" ");
  const id=String(r.x.b||"").toUpperCase();
  return {id,n:id,title,term:t,hayT:voteNorm([id,id,title].join(" ")),hayC:""};
}
// The address keeps the search: "?q=housing&topic=Health&term=all", beside
// whatever else it carries, so a link reproduces what is on the screen.
function voteAddress(){
  if(!PAGE||PAGE.kind!=="member")return;
  try{
    const u=new URLSearchParams(location.search);
    const set=(k,v)=>{if(v)u.set(k,v);else u.delete(k);};
    set("q",String(PAGE.vq||"").trim());
    set("topic",PAGE.vtopic||"");
    set("term",PAGE.vall?"all":"");
    const qs=u.toString();
    // Only where it changes: a term chosen on a page whose address names
    // nothing of this must not rewrite the address (a recording's hash).
    if(qs!==location.search.replace(/^\?/,""))
      history.replaceState(history.state,"",location.pathname+(qs?"?"+qs:"")+location.hash);
  }catch(_){}
}
function voteAddressRead(){
  const u=new URLSearchParams(location.search);
  PAGE.vq=u.get("q")||"";
  PAGE.vtopic=u.get("topic")||"";
  PAGE.vall=u.get("term")==="all";
}

// WHAT THE VOTE DECIDED, not only how they voted. This tab listed 1,081 rows
// of "HB2026 / Veto Override / Yea" on one member's page: the record's own
// abbreviations and no outcome. The answers are in one shared file, fetched
// the first time this tab is drawn -- the same 1,504 roll calls describe all 406
// members, so a copy inside each member's own file would add over a hundred
// megabytes to the site for facts that are identical in every copy.
//
// The bill's TITLE is not in that file: this page already has the term's bill
// index loaded, because the sponsored tabs are drawn from it, so the title is
// looked up there rather than shipped twice.
let RCX=null, RCX_ERR="";
function needRollcalls(){
  if(RCX)return;
  RCX={};                     // claimed, so a redraw does not fetch it twice
  fetch(DATA("rollcalls_index.json"))
    .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
    .then(j=>{RCX=j;if(window.GR_VOTES)votesDraw();else renderPage();})
    .catch(e=>{RCX_ERR=e.message||String(e);if(window.GR_VOTES)votesDraw();else renderPage();});
}

// THE PREVAILING SIDE (the person, 23 October 2026: "I'd rather categorize
// votes by whether or not the member voted on the prevailing side of the
// motion since I don't want to label either party as taking a position on a
// bill"). This tab marked each vote "with" or "against" the member's party --
// the side most of that party's members took -- which read as a party's
// position on the bill. The prevailing side is the journals' own term (a
// member who "voted with the prevailing side" may move to reconsider), and it
// is decided by the clerk's recorded outcome, never by the larger number: a
// yes on a motion that carried, or a no on one that failed, so a veto
// override that drew more yeas than nays and missed two thirds counts its
// noes as prevailing. A member absent, excused or presiding took no side, and
// a roll call whose record and ballots disagree (rc.oc) is marked neither way.
function prevailed(x,rc){
  const mine=String(x.v||"");
  if(!rc||rc.oc||(mine!=="Yea"&&mine!=="Nay"))return null;
  return (mine==="Yea")===!!rc.p;
}

// A BILL'S RECORD, FETCHED ONCE, for a page that draws one of its roll calls
// with the Votes tab's own ring: a session day (drawSessionVotes) and a
// member's Votes tab (voteRing). The record is inside the bill's page, or
// beside it for the few too large to inline (gr-data). {key: record|null}.
// `then` is told which record came, so a session day redraws that bill's
// rings and not all forty (drawSessionVotes).
const BILL_RECS={};
function billRecord(key,then){
  if(CMP.own(BILL_RECS,key))return;
  BILL_RECS[key]=null;
  const [yr,id]=key.split("/");
  const url=DATA(`bill/${yr}/${String(id).toLowerCase()}`);
  const got=d=>{BILL_RECS[key]=d;then(key);};
  fetch(url).then(r=>r.ok?r:fetch(url+".html")).then(r=>r.ok?r.text():Promise.reject(new Error("HTTP "+r.status)))
    .then(html=>{
      const doc=new DOMParser().parseFromString(html,"text/html");
      const node=doc.getElementById("gr-data");
      if(node)return got(JSON.parse(node.textContent));
      const ptr=doc.querySelector('meta[name="gr-data"]');
      if(!ptr)return;
      return fetch(DATA(ptr.getAttribute("content").replace(/^\//,"")))
        .then(r=>r.ok?r.json():null).then(d=>{if(d)got(d);});
    }).catch(()=>{});
}

// A TERM'S ROLL CALLS ON NO BILL, FETCHED ONCE: nobill/<term>.json, the cards
// build_site_v2 makes for them with a bill's own code (write_nobill_cards),
// kept in BILL_RECS under "nobill/<term>" beside the bills' records, in the
// same shape ({rollcalls: [card, ...]}).
function nobillRecord(key,then){
  if(CMP.own(BILL_RECS,key))return;
  BILL_RECS[key]=null;
  fetch(DATA(`${key}.json`)).then(r=>r.ok?r.json():null)
    .then(d=>{if(d){BILL_RECS[key]=d;then(key);}}).catch(()=>{});
}

// HOW EVERYONE VOTED, under a member's vote (option A, 23 October 2026: "so
// that someone could view how other members voted on those bills"). Folded,
// one a row; opened, it is the bill page's own ring and party rows (donut),
// which list the members when pressed, drawn from the card the shared index
// names (rc.c): in the bill's record, or for a roll call on no bill in its
// term's nobill/ file (rc.ct). ONE DISPLAY (the person, 23 October 2026:
// "The two displays should not be structured differently from each other"):
// every vote here is a roll call, so every one has its card. Only while the
// card is on its way, or where an older build gave none, is it the ring of
// the counts alone (simpleDonut).
function voteRing(r,i){
  const x=r.x, rc=r.rc;
  if(!rc||rc.y==null||rc.n==null)return "";
  const key=x.k, open=!!(PAGE.vopen&&PAGE.vopen[key]);
  const nb=!x.b&&rc.c!=null&&rc.ct?String(rc.ct):"";
  const bkey=x.b&&x.y?`${x.y}/${String(x.b).toUpperCase()}`:nb?`nobill/${nb}`:"";
  let body="";
  if(open){
    const d=bkey&&rc.c!=null?BILL_RECS[bkey]:null, card=d&&(d.rollcalls||[])[rc.c];
    if(bkey&&rc.c!=null&&!CMP.own(BILL_RECS,bkey))(nb?nobillRecord:billRecord)(bkey,renderPage);
    body=card&&(card.members||[]).length
      ? donut(nb?`NB-${nb}`:String(x.b).toUpperCase(),rc.c,card)
      : simpleDonut({yeas:rc.y,nays:rc.n,passed:!!rc.p,threshold_needed:rc.nd||null},"mv",i);
    if(x.b&&x.y)body+=`<p class="src"><a href="bill/${esc(String(x.y))}/${
      esc(String(x.b).toLowerCase())}/votes">Every vote on ${esc((r.b&&r.b.n)||x.b)}, on its Votes tab</a></p>`;
  }
  return `<tr class="vring"><td colspan="4"><details data-vring="${esc(key)}"${open?" open":""}>
    <summary data-vring-s="${esc(key)}">How everyone voted</summary>${open?`<div class="vringbody">${body}</div>`:""}
    </details></td></tr>`;
}

// How many are drawn before the reader asks for more. The old table stopped
// dead at 600 with a line saying so and no way to see the 481 after it.
const VOTES_SHOWN=200;

// THE VOTES PAGE'S ADDRESS for a member's votes or a bill's (votesAddr, below,
// reads it back): the member's page name, the search as typed, the term.
function votesLinkFor(slug,q,term){
  const u=new URLSearchParams();
  if(slug)u.set("member",slug);
  if(q)u.set("q",q);
  if(term)u.set("term",term);
  const s=u.toString();
  return "votes"+(s?"?"+s:"");
}
function renderMemberVotes(m){
  if(isReqTerm(pageTerm())&&!PAGE.vall)return `<p class="src">No votes: a request is not voted on until
    it is a bill.</p>`;
  const v=memberVotes(m);
  const t=pageTerm();
  if(!v.length)return `<p class="src">No recorded roll call votes in the
    ${esc(termDash(t))} term. Voice and division votes leave no record of individual
    members, so a member can have taken part in many votes and appear in none
    of them.</p>`;
  needRollcalls();

  // Which chamber these were cast in, for a member who has sat in both. A
  // term is one chamber's almost always; where it holds both -- a member who
  // moved in the middle of one -- each row says which.
  const chOf=x=>String(x.k||"").split("-")[1];
  const chs=[...new Set(v.map(chOf))].filter(c=>CHAMBER_SHORT[c]).sort();
  const castIn=(m.service||[]).length>1&&chs.length
    ?` cast in the ${chs.map(c=>CHAMBER_SHORT[c]).join(" and the ")}`:"";

  // Resolved once per row: what the roll call decided, the bill's title from
  // the index this page already holds, and the side the member was on.
  const all=v.map(x=>{
    const rc=(RCX||{})[x.k]||null;
    return {x, rc, side:prevailed(x,rc),
            ch:castIn&&chs.length>1?chOf(x):"",
            b:(x.b&&x.y)?idxRow({id:x.b,year:x.y,term:termOfYear(x.y)}):null};
  });

  // The filters: the member's vote, the side it was on, the bill's topic (the
  // bill search's own list) and words or a bill number (voteSubject, above).
  const q=(PAGE.vfilter||"").toLowerCase(), sd=PAGE.vside||"", tp=PAGE.vtopic||"";
  const find=String(PAGE.vq||"").trim();
  const scope=[...new Set(all.map(r=>r.x.y?termOfYear(r.x.y):termOfYear(voteYear(r.x))).filter(Boolean))];
  // Each term's bills, and for a search in words their text, are fetched the
  // first time they are wanted; the page is drawn again as they arrive.
  const unread=scope.filter(x=>published(x)&&!LOADED.has(x));
  if(unread.length){
    const key=unread.join(",");
    if(PAGE.vasked!==key){PAGE.vasked=key;
      Promise.all(unread.map(ensureTerm)).then(renderPage,renderPage);}
  }
  const ids=find?billNumbers(find):null;
  let gs=null;
  if(find&&!ids){
    gs=voteGroups(find,IDX.filter(b=>scope.includes(b.term)));
    wantText(scope,renderPage);
  }
  const reading=!!find&&!ids&&(unread.length||textState(scope)==="loading");
  const hit=r=>{
    if(!find)return true;
    if(ids)return !!r.x.b&&ids.includes(String(r.x.b).toUpperCase());
    return matchesGroups(voteSubject(r),gs);};
  const rows=all.filter(r=>(!q||String(r.x.v||"").toLowerCase()===q)
    &&(!sd||(r.side!==null&&(sd==="won")===r.side))
    &&(!tp||(r.b&&r.b.topic===tp))&&hit(r));
  const topics={};
  all.forEach(r=>{if(r.b&&r.b.topic)topics[r.b.topic]=(topics[r.b.topic]||0)+1;});
  if(tp&&!topics[tp])topics[tp]=0;
  const tally={};
  v.forEach(x=>{tally[x.v]=(tally[x.v]||0)+1;});
  const sided=all.filter(r=>r.side!==null), won=sided.filter(r=>r.side).length;

  const cap=PAGE.vshow||VOTES_SHOWN;
  const shown=rows.slice(0,cap);
  const left=rows.length-shown.length;

  return `<div class="bfilt"><label>Their vote
      <select data-pf="vfilter"><option value="">Any</option>
      ${Object.keys(tally).sort().map(k=>`<option value="${esc(k.toLowerCase())}"${
        q===k.toLowerCase()?" selected":""}>${esc(ballotWord(k))} (${tally[k]})</option>`).join("")}
      </select></label>${sided.length?`<label>Side
      <select data-pf="vside"><option value="">Any</option>
        <option value="won"${sd==="won"?" selected":""}>Prevailing side (${won.toLocaleString()})</option>
        <option value="lost"${sd==="lost"?" selected":""}>Losing side (${
          (sided.length-won).toLocaleString()})</option>
      </select></label>`:""}${Object.keys(topics).length?`<label>Topic
      <select data-pf="vtopic"><option value="">Any</option>
      ${Object.keys(topics).sort().map(k=>`<option value="${esc(k)}"${
        tp===k?" selected":""}>${esc(k)} (${topics[k].toLocaleString()})</option>`).join("")}
      </select></label>`:""}<label>Search
      <input type="search" data-pf="vq" value="${esc(find)}" placeholder="Bill number or words"
        aria-label="Search the votes by bill number or words"></label></div>
    <p class="src" id="vcount">${rows.length.toLocaleString()} of ${v.length.toLocaleString()}
      recorded votes in ${PAGE.vall?"every term":esc(termDash(t))}${castIn}${
      (PAGE.terms||[]).length>1?` (<button type="button" class="link" data-vall="${
        PAGE.vall?"0":"1"}">${PAGE.vall?`show only ${esc(termDash(t))}`:"search every term"}</button>)`:""}${
      reading?`. Reading the bills&hellip;`:""}, newest first: every roll call this member is
      recorded in, what it was on, and what it decided. The prevailing side is a yes on a
      motion that carried or a no on one that failed; it describes the vote, not the
      member, and nothing here is rated or scored.
      ${m.slug?`<a href="${esc(votesLinkFor(m.slug,find,PAGE.vall?"all":t))}">See these on the votes page</a>.`:""}</p>
    ${RCX_ERR?`<p class="note">What each vote decided could not be loaded, so
      the outcomes and the prevailing side are missing from the rows below.
      The votes themselves are the member's own record and are unaffected.
      <code>${esc(RCX_ERR)}</code></p>`:""}
    ${rows.length?"":`<p class="note" role="status">No recorded vote matches${
      find?` &ldquo;${esc(find)}&rdquo;`:""}${tp?` under the topic ${esc(tp)}`:""} among
      ${PAGE.vall?"every term\u2019s":"this term\u2019s"} ${v.length.toLocaleString()} votes${
      reading?" yet":""}. <button type="button" class="link" data-vclear="1">Clear the
      search and filters</button>.</p>`}
    <table class="votes vfull"${rows.length?"":" hidden"}><thead><tr><th>Date</th>
      <th>The bill and the question</th><th>Their vote</th><th>Result</th>
      </tr></thead><tbody>${shown.map((r,i)=>voteRow(r)+voteRing(r,i)).join("")}
      </tbody></table>
    ${left?`<p class="src"><button type="button" class="link" data-vmore="1"
      >Show ${Math.min(VOTES_SHOWN,left).toLocaleString()} more</button> &mdash;
      ${left.toLocaleString()} of ${rows.length.toLocaleString()} not yet
      shown.</p>`:""}`;
}

// A vote on no bill in a few words (rc.w, build_site_v2.write_rollcall_index
// from journal_motions.json), linked to the roll call's own anchor on its
// sitting's page, "#rc-2026-H-290", where a page draws it under that id.
//
// WHERE THE PAGE SAYS, NOT WHERE rc.w IMPLIES (the preview check of 25
// October 2026): the words come from the Journal and the anchor from the
// session page, which drew 2022-H-4 and -5 on HB 50's card with no rc- id,
// so their links opened 5 January 2022 at its top. rollcallDay asks the
// list the session pages were written with, and gives the day the page
// draws it on, which the file's own date may not be.
function nobillWords(x,rc){
  const b=voteChamber(x), k=String(x.k||""), day=rollcallDay(b,k);
  const w=`<span class="nbw">${esc(rc.w)}</span>`;
  return day?`<a class="nbwa" href="session/${esc(b)}/${esc(day)}#rc-${esc(k)}">${w}</a>`:w;
}

// One row. data-l carries the column's name so the same markup can stack into
// labelled blocks on a phone instead of scrolling sideways, which on a civic
// site reads as "this page was not meant for you".
function voteRow(r){
  const x=r.x, rc=r.rc, b=r.b;
  // THE BILL PAGE'S WORDS FOR THE MOTION (votes.json, components.vote_head):
  // "Inexpedient to Legislate (ITL, Kill the bill)", where the shared index
  // names the motion. Otherwise the plain-English gloss with the record's own
  // word beside it, or the record's word alone: "pass the bill with changes"
  // is what a reader needs, and "OTPA" is what they will see on every other
  // page of the General Court's own site.
  const plain=(rc&&rc.q)||"", raw=x.q||"";
  const named=rc&&rc.mk&&rc.mk!=="unnamed";
  const question=named ? voteHead(rc.mk,raw,rc.mf)
    : plain
    ? `${esc(plain)}${raw&&raw.toLowerCase()!==plain.toLowerCase()
        ?` <span class="dim">(${esc(raw)})</span>`:""}`
    : esc(raw);
  const tallies=rc&&rc.y!=null&&rc.n!=null
    ? ` <i>${rc.y}–${rc.n}</i>`:"";
  // The result as the bill page says it, "Motion Passed: Bill Killed", where
  // the motion is named; "Adopted" or "Failed" where it is not.
  const said=named?voteChip(rc.mk,!!rc.p,x.b||"",rc.mf):"";
  return `<tr>
    <td class="d" data-l="Date">${sittingLink(voteChamber(x),voteIso(x),
      esc(voteIso(x)?dateWords(voteIso(x)):x.d||""),
      // A bill's card only for a bill (`y`, its year): "HRULE64" or "HR" is
      // a rule or a code the roll-call file files a vote under, and no card
      // has it for an id (the preview check of 25 October 2026).
      x.y?x.b:"",x.k)}${
      r.ch?`<span class="vch">${
      esc(CHAMBER_SHORT[r.ch]||r.ch)}</span>`:""}</td>
    <td class="b" data-l="On">${x.b&&x.y
      // A MENTION, components.bill_mention: the number as the link.
      ? billMention((b&&b.n)||x.b,`bill/${String(x.y)}/${String(x.b).toLowerCase()}`)
      // A procedural vote -- a call of the roll, a rules suspension -- is
      // recorded against no bill. It used to render an empty cell wrapped in
      // a link to /bill//.html. WHAT IT WAS ABOUT, where the Journal says
      // (rc.w, 23 October 2026): the session day's own summary or kind of
      // question, linked to the roll call on that day's page, where the
      // Journal's words are quoted with their page. Before the code a vote
      // is filed under, where it has no bill: the House's two votes on Rule
      // 64 of 8 January 2025 said "HRULE64", where the Journal says "Adopt a
      // floor amendment to House Rule 64" (the preview check of 25 October
      // 2026).
      : rc&&rc.w ? nobillWords(x,rc)
      : x.b ? esc(x.b)
      : `<span class="none">no bill</span>`}${
      b&&b.title?`<span class="vt" translate="no">${esc(b.title)}</span>`:""}
      <span class="vq">${question}</span></td>
    <td class="v" data-l="Their vote"><span class="vcast v-${
      esc(String(x.v||"").slice(0,3).toLowerCase())}">${
      /* "Not Voting/Excused" may break after its slash: on a phone at a
         24px text size the half row it has was narrower than the word, which
         ran into the tally beside it (the review of 8 October 2026). */
      esc(ballotWord(x.v||""))}</span>${
      r.side===true?`<i class="pside">On the prevailing side</i>`
      :r.side===false?`<i class="pside lost">On the losing side</i>`:""}</td>
    <td class="o" data-l="Result">${rc
      ? `${said||chip(rc.p?"Adopted":"Failed",rc.p?"pass":"fail")}${
          tallies}${rc.tn?`<i class="thr">${esc(rc.tn)}</i>`:""}${
          rc.oc?`<i class="thr">${esc(rc.oc)}</i>`:""}`
      : `<span class="dim">&mdash;</span>`}</td></tr>`;
}

