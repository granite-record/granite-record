// ===================================================== member and committee ==
//
// Two more things a page can be. A bill's page is this app with one bill open;
// a legislator's and a committee's are the same idea, so the cards, the tabs
// and the timestamps are the ones the bill view already draws rather than a
// second set that drifts from them.
//
// Each is told which record it is by a global the shell page sets, for the
// reason GR_BILL exists: the address already names it, and putting it in the
// hash as well would show it twice.

let PAGE = null;          // {kind:"member"|"committee", data:{...}}
let PAGE_TAB = 0;
// home.json's `upcoming`, once, for the committee page's own calendar.
// null while unasked, [] once asked and empty -- the two are not the same
// thing and the page must not say "nothing is scheduled" before it knows.
let UPCOMING = null;

// Redraw whatever is on screen. The bill search and a record page are two
// renderers, and the controls INSIDE an expanded bill card -- the segment
// picker, the routine-lines toggle, the full-text toggle -- are shared by
// both. Those called render() unconditionally, which on a committee's page
// drew four hundred bill cards over the committee.
// Every redraw after something arrives -- the bill text, a version, a member's
// record -- goes through here. Keeping the keyboard's place through it is the
// renderers' own job now (focusKey and refocus, below), so this only chooses
// which of the two to run.
const repaint=()=>{
  // A session day draws its roll calls with the Votes tab's display (below,
  // drawSessionVotes): a party row pressed there redraws them, never the
  // bill list over the day.
  // The votes page (votesDraw, below) draws its list the same way.
  if(window.GR_VOTES){if(typeof votesDraw==="function")votesDraw();}
  else if(PAGE)renderPage();else if(SESSV)drawSessionVotes();else render();
  jumpToTab();
  jumpToAmendment();
  jumpToVote();
};

// A BILL'S ADDRESS THAT NAMES A TAB OPENS AT IT (the webinar pass of 23
// October 2026). /bill/2025/hb282/hearings drew the Hearings tab, chosen,
// 886px down a phone's page, under the summary: the reader saw the summary
// and nothing of what the link was for. Once, when the record has come, the
// tab strip is brought into view if it starts below the top six tenths of the
// window; a reader already scrolling is never moved again.
let TAB_JUMP=null;
// A vote's card, brought into view once it is drawn (voteLinks): below the tab
// strip a bill's page holds at the top, and marked while it is the one asked for.
let VOTE_JUMP=null;
function jumpToVote(){
  if(!VOTE_JUMP)return;
  const el=document.getElementById(VOTE_JUMP);
  const pane=el&&el.closest(".pane");
  if(!el||!pane||pane.hidden)return;
  VOTE_JUMP=null;
  document.querySelectorAll(".rc.rcsel").forEach(x=>x.classList.remove("rcsel"));
  el.classList.add("rcsel");
  const card=el.closest(".card"), strip=card&&card.querySelector(".tabs");
  const held=strip&&getComputedStyle(strip).position==="sticky"?strip.getBoundingClientRect().height:0;
  window.scrollTo(0,Math.max(0,el.getBoundingClientRect().top+window.scrollY-held-16));
}
function jumpToTab(){
  if(!TAB_JUMP||!detail[dkey(TAB_JUMP)])return;
  const card=[...document.querySelectorAll(".card[data-id]")].find(c=>c.dataset.id===TAB_JUMP);
  const strip=card&&card.querySelector(".tabs");
  if(!strip)return;
  TAB_JUMP=null;
  const top=strip.getBoundingClientRect().top;
  if(top>window.innerHeight*0.6&&strip.scrollIntoView)strip.scrollIntoView({block:"start"});
}

// FOCUS SURVIVES EVERY REDRAW. A redraw replaces the element that held focus
// with a copy, and focus fell to <body>. repaint() used to put it back for
// four kinds of control and only on the redraws that went through it; the
// audit of 2 October 2026 (S1) found the rest: a facet's checkbox, a card's
// header, a filter group's head, a legend row, the Term and Status selects of
// a member's or a committee's page, and every tab opened with Enter, Space or
// a click -- the commonest keyboard action on the site, since each tab is its
// own Tab stop. After each, the next Tab press started again from the top of
// the record. Arrowing between tabs had been held since 12 September.
//
// So the three functions that redraw -- render(), renderPage() and
// renderFacets() -- each take the key of the control that has focus before
// they draw and hand focus to the control with that key after. The key is the
// control's own identity as the markup already carries it: its id; or its tag
// and data attributes (data-seg, data-full, data-pf, data-g, data-f with the
// checkbox's value ...), inside its card where it is in one; or, for a
// control with neither, its tag and classes. And its place among the
// controls that key matches, for the few that share one.
//
// "Show more" is left out on purpose: what a reader wants after pressing it
// is the first of the rows it brought, not the next "Show more" a page of
// rows down. Its own handlers put focus there. The browser does not: the
// redraw replaces the whole list, so its starting point is the top of it.
function focusKey(a){
  if(a===undefined)a=document.activeElement;
  if(!a||a===document.body||!a.tagName||!a.closest)return null;
  // Only what a redraw replaces: the list or the record, and the filters.
  if(!a.closest("#results,#facets"))return null;
  const d=a.dataset||{};
  if(d.more!==undefined||d.vmore!==undefined||d.pmore!==undefined)return null;
  let sel;
  if(a.id)sel="#"+CSS.escape(a.id);
  else{
    const card=a.closest(".card[data-id]");
    const within=card&&card!==a?`.card[data-id="${CSS.escape(card.dataset.id)}"] `:"";
    const tag=a.tagName.toLowerCase();
    const keys=Object.keys(d).sort();
    if(keys.length){
      sel=within+tag+keys.map(k=>`[data-${k.replace(/[A-Z]/g,c=>"-"+c.toLowerCase())}="${
        CSS.escape(d[k])}"]`).join("");
      const v=tag==="input"&&a.getAttribute?a.getAttribute("value"):null;
      if(v!==null)sel+=`[value="${CSS.escape(v)}"]`;
    }else{
      const href=tag==="a"&&a.getAttribute?a.getAttribute("href"):null;
      sel=within+tag+[...(a.classList||[])].map(c=>"."+CSS.escape(c)).join("")
        +(href?`[href="${CSS.escape(href)}"]`:"");
    }
  }
  try{return {sel,i:Math.max(0,[...document.querySelectorAll(sel)].indexOf(a))};}
  catch(_){return null;}
}
// Focus, back on the control `key` names -- but only if the redraw took it
// away. Where focus is on something still in the page (the search box while
// the list narrows, or wherever a handler has just put it) it is left there.
function refocus(key){
  if(!key)return;
  const now=document.activeElement;
  if(now&&now!==document.body&&now.isConnected!==false)return;
  let f=null;
  try{f=document.querySelectorAll(key.sel)[key.i]||null;}catch(_){}
  if(f&&f.focus)f.focus({preventScroll:true});
}

// The term a record page is showing. One control for the whole record rather
// than one per tab: a reader looking at 2023-2024 wants that term's bills AND
// that term's sessions, and choosing the term on one tab then finding the
// other back on the current term is the page disagreeing with itself.
const pageTerm=()=>{
  const ts=(PAGE&&PAGE.terms)||[];
  return PAGE&&PAGE.term&&ts.includes(PAGE.term)?PAGE.term:(ts[0]||"");
};
// "2026" -> "2025-2026". A vote records the year it was cast and not the term,
// and the term is what every other list on the page is keyed by.
const termOfYear=y=>{
  const n=parseInt(y,10);
  if(!n)return "";
  return ((META&&META.terms)||[]).find(t=>{
    const [a,b]=String(t).split("-").map(Number);
    return a&&b&&n>=a&&n<=b;})||"";
};

// THE BYLINE UNDER A CARD'S TITLE: sponsor, committees, subject. The middot
// used to be glued to the front of each item rather than set between them, so
// a bill with no sponsor opened with a separator and nothing before it --
// "· House Transportation · Motor Vehicles". That is 22,913 of the 33,683
// bills in site/index.json (counted, and 22,905 of them have a committee or a
// topic to follow the stray mark; the other 8 have neither and were simply
// blank). It is that many because the archive backfill has not reached the
// older terms: every term before 2013-2014 names a sponsor on fewer than
// twenty of its ~1,700 bills, against 14 of 2,234 missing one in 2025-2026.
// Joining the parts that exist says the same thing and cannot open with
// punctuation.
//
// "No Committee Assignment" on 296 cards is the General Court's own wording
// for a bill it never referred, not an empty value: it is a fact about the
// bill and stays.
// Drawn by components.bill_byline (billByline) since 10 October 2026, which
// joins the parts the same way, the sponsor as the person chip (cardHtml).

/* A BILL REQUEST'S CARD, a bill card (lsrCardHtml, below) drawn from the
   request's row alone: a request has a number, a title, a prime sponsor, the
   body it will be filed in and, once they accept, its co-sponsors -- no
   committee, hearing or vote yet, and its text only once filed -- so its card
   opens onto Summary (its sponsors first where it has co-sponsors, as a bill's
   Summary opens), Bill Text (saying where the text stands until the night
   has read it) and History, and its rail has three stops of its own. */
// A BILL REQUEST CAN BE FOLLOWED BY EMAIL (the person, 22 October 2026):
// until it is drafted, when the follow moves onto its bill (build_feeds,
// BILL REQUESTS). Its Follow is on its own page, after Cite, as a bill's is
// on the bill's (mountFollow, GR_REQUEST): the card carries none (the owner,
// 15 November 2026: "removing the follow button on the unexpanded cards", as
// a bill's card has none).
// WHETHER THE FOLLOW PAGES ANSWER, AND NOTHING MORE (5 November 2026). The
// two that ask -- a law's Follow and a record's email box -- want only the
// status, and read none of the count's two bytes; a response
// whose body is never read stays open in the browser until it is collected,
// so a law page and /bills never went quiet (seen by the deck's screenshots:
// network idle never came). Every ask is this one, and lets the body go.
function followUp(){
  return fetch("/api/follow/count",{cache:"no-store"}).then(r=>{
    if(r.body&&r.body.cancel)Promise.resolve().then(()=>r.body.cancel()).catch(()=>{});
    return r.ok;});
}
// A REQUEST'S SPONSORS AS A BILL'S ARE DRAWN (renderSponsors; the owner, 24
// November 2026: "Yes, take them", of the co-sponsors the General Court's
// results page names): the prime sponsor first, labelled Prime, then each
// co-sponsor in the page's order, each a person chip as the byline draws the
// prime (cardSponsor: the row's label, the party read from it, the member's
// page where they have one; a name that matched nobody as typed, with no
// party), and the chamber build_lsrs matched them in, which renderSponsors
// groups them by. build_request_pages.sponsors_section draws the page's.
function lsrSponsors(b){
  const sp=cardSponsor(b);
  return (sp?[Object.assign({},sp,{chamber:b.sponsor_chamber||"",prime:true})]:[]).concat(
    (b.cosponsors||[]).map(c=>Object.assign(cardSponsor({sponsor_label:c.label||c.name||"",
      sponsor_party:c.party||"",sponsor_slug:c.slug||""})||{},{chamber:c.chamber||""})));
}
// The tabs a request has (the numbers are a bill's own, which a tab's
// identity is): Summary; Bill Text, always (the owner, 17 November 2026: "move
// the text about the bill text into a bill text tab and just list it as 0
// until the text is published"), its count 1 once the night has read the text
// and until then the text "0", which recordTabs draws as "(0)" where the
// number 0 draws no count (build_request_pages.text_count); History, where an
// earlier bill has the same title. No Sponsors tab, as a bill has none since
// 19 November 2026: a request's co-sponsors open its Summary (lsrPane).
function lsrTabs(b){
  const hist=b.history||[];
  return [["0","Summary",0],["6","Bill Text",b.text_on_file?1:"0"]].concat(
    hist.length?[["7","History",hist.length]]:[]);
}
// What the Bill Text tab says while the text is not here, by what the row
// says: build_request_pages.text_note's words, the page's.
function lsrTextNote(b){
  if(b.withdrawn)return "<b>Withdrawn.</b> This request was withdrawn before it was filed as a bill, so it has no text.";
  if(b.filed||b.introduced)return "<b>Filed.</b> Its text is public, and is added here once this site has read it."
    +(b.text_pdf?` <a href="${esc(b.text_pdf)}" target="_blank" rel="noopener">The PDF at the General Court</a>.`:"");
  return `<b>Not public yet.</b> This request is still being drafted into a bill. Its text will be public when it is filed as a numbered ${
    esc(String(b.year||reqYear()))} bill.`;
}
// A REQUEST'S TEXT ON ITS CARD (the owner, 17 November 2026: "View the text
// that shows the granite record tab once we've imported the text"): what the
// night read off the PDF the request list links. The row does not carry it --
// a text is long and the list is not -- so the card fetches it once, from the
// request's own file in the data API (api_records: /api/requests/<year>/
// <number>.json, its "text"), when it draws the tab, and fills the tab when it
// comes. The words and the block are the request page's (build_request_pages.
// text_pane). Until the night has read it, the tab says where the text
// stands (lsrTextNote) and asks for nothing.
const LSRTEXT=new Map();
function lsrTextPane(b){
  if(!b.text_on_file)return `<p>${lsrTextNote(b)}</p>`;
  const num=String(b.address||"").split("/").pop(),got=LSRTEXT.get(num);
  const pdf=b.text_pdf?`<p class="src"><a href="${esc(b.text_pdf)}" target="_blank" rel="noopener">The PDF at the General Court</a></p>`:"";
  const head=`<p class="btwhat">The text as the General Court publishes it with this request, read by machine from its PDF: the PDF is the document.</p>`;
  if(typeof got==="string")return head+(got?`<pre class="vtext" translate="no">${esc(got)}</pre>`
    :`<p class="note">The text could not be loaded here.</p>`)+pdf;
  const m=/^(\d{4})-(\d+)$/.exec(num);
  if(!got&&m&&typeof fetch==="function"){
    // Asked for once (true until it comes); the tab drawn again when it does.
    const fill=t=>{LSRTEXT.set(num,t);const p=document.getElementById(`pane_${b.id}_6`);if(p)p.innerHTML=lsrTextPane(b);};
    LSRTEXT.set(num,true);
    fetch(DATA(`api/requests/${m[1]}/${m[2]}.json`)).then(r=>r.ok?r.json():null)
      .then(j=>fill(String((j&&j.text)||""))).catch(()=>fill(""));
  }
  return head+`<p class="src">Loading the text&hellip;</p>`+pdf;
}
// WHAT A REQUEST IS, ON ITS CARD'S SUMMARY (the owner, 17 November 2026:
// "make it so that opening the LSR pages shows the same summary of what LSRs
// are that the full page does since right now it just shows the link to the
// page and almost doesn't look like the card has expanded"): the request
// page's About Requests, in its words (build_request_pages.explain) -- the
// request's year, and what the number's abbreviation stands for from
// meta.requests's abbr -- with no id, since a list opens many cards.
function lsrAbout(b){
  const year=String(b.year||reqYear()),abbr=(META.requests||{}).abbr||{};
  return section("About Requests",`<p class="lsrnote"><b>Requests, not bills yet.</b> Each is a member&rsquo;s request to have a bill drafted: a title and a sponsor, nothing more, until it is filed as a numbered ${
    esc(year)} bill. Some are withdrawn first.${Object.entries(abbr).map(([k,v])=>` ${esc(k)} stands for ${esc(v)}.`).join("")}</p>`);
}
function lsrPane(b,t){
  const cos=b.cosponsors||[],hist=b.history||[];
  if(t==="6")return lsrTextPane(b);
  if(t==="7"){
    return `<p class="src">${hist.length===1?"A bill":"Bills"} of an earlier session with this same title:</p>
      <ul class="lsrhist">${hist.map(h=>`<li><a href="bill/${esc(h.year)}/${esc(String(h.id||"").toLowerCase())}">${
        esc(h.n)} <span class="cyear">(${esc(h.year)})</span></a> ${chip(h.word||h.chip,`cstat ${h.cls||""}`,"m")}</li>`).join("")}</ul>`;
  }
  // WHAT THE BYLINE DOES NOT SAY (the owner, 14 November 2026: "just let the
  // pages speak for themselves"): the chip has the status, the byline the kind,
  // the prime sponsor and the topic; what is left is the co-sponsors and the way
  // on to the request's own page. The co-sponsors as a bill's Summary opens
  // with its sponsors (renderSummary, lsrSponsors), with no id: a list opens
  // many cards.
  // And the bill it was filed as, while it is still a request (the owner, 17
  // November 2026: "Drafted and filed as HB123 sounds fine"). Then what a
  // request is, as its own page's Summary says it (lsrAbout).
  return `${cos.length?section("Sponsors",renderSponsors(b,{sponsors:lsrSponsors(b)})):""}
    ${b.introduced&&!b.moved_to?`<p><b>Filed As:</b> ${b.bill_at?`<a href="${esc(b.bill_at)}">${esc(b.introduced)}</a>`:esc(b.introduced)}</p>`:""}
    ${lsrAbout(b)}
    ${b.address?`<p><a href="${esc(b.moved_to||b.address)}">${b.moved_to?"Read the bill":"Open the request’s own page"}</a></p>`:""}`;
}
// WHAT A REQUEST'S CARD OPENS ONTO: the bill card's tab strip and panes, from
// the row alone (a request has no record to fetch). The tab chosen is
// openTab's, as a bill's is.
function lsrBody(b){
  const tabs=lsrTabs(b),want=openTab[b.id]||"0",t=tabs.some(x=>x[0]===want)?want:"0";
  const pane=([k])=>`<div class="pane" role="tabpanel" id="pane_${esc(b.id)}_${k}" aria-labelledby="tab_${esc(b.id)}_${k}" tabindex="0" data-t="${k}"${k===t?"":" hidden"}>${lsrPane(b,k)}</div>`;
  // The bill's strip (components.recordTabs): Summary and Bill Text at least
  // (lsrTabs), so always a choice to make.
  return recordTabs(b.id,tabs,t)+tabs.map(pane).join("");
}
// `cls`: a class beside "card lsr" (a paged list's "unshown").
//
// A REQUEST'S CARD IS A BILL'S (the owner, 13 November 2026: "update LSR
// cards to also function similarly to bill cards with tabs and clicking on
// the block should open the expanded view"): components.billCard, the
// sponsor as the person chip, the head pressed to open it where it stands,
// and the tabs above.
function lsrCardHtml(b,cls){
  // THE TOPIC AS A BILL'S CARD PRINTS IT (the owner, 14 November 2026: "remove
  // the topic from title label"): the name alone, and nothing for the
  // Miscellaneous of a request request_topics could not place -- the Topic
  // filter lists it, and a card does not print the site's own (cardTopic).
  const kind=[b.body_label,cardTopic(b)].filter(Boolean).join(" · ");
  // THE RAIL, AS A BILL'S CARD HAS ONE (the owner, 15 November 2026: "adding
  // the rail on the card"): the row's own three stops (build_lsrs.rail_stops),
  // drawn by the bill's rail component, the request's page drawing the same
  // ones; a day where the record gives one. A row with no stops draws none,
  // never a bill's four.
  const st=b.rail||[];
  const card=billCard({id:b.id,href:"",n:b.n,year:"",word:chipOf(b),cls:chipCls(b),title:b.title,
    byline:billByline(cardSponsor(b),[],kind),rail:st.length?railHtml(st,false):"",
    open:openCards.has(b.id),body:lsrBody(b),card:"lsr"+(cls?" "+esc(cls):"")});
  // ITS OWN PAGE, or where it went (Alice, 8 November 2026): the address
  // build_lsrs gives it, or the bill's page it became. An anchor inside the
  // number, not a.cnum, which opens a bill in place. The number is plain:
  // what LSR stands for is the request's own page's to say, not a tooltip on
  // the card's link (the owner, 14 November 2026).
  const numHtml=b.address
    ?`<span class="cnum" translate="no"><a href="${esc(b.moved_to||b.address)}">${esc(b.n)}</a></span>`
    :`<span class="cnum" translate="no">${esc(b.n)}</span>`;
  return card.replace(`<span class="cnum" translate="no">${esc(b.n)}</span>`,()=>numHtml);
}

// ONE card, drawn by the search list and by both record pages.
//
// A member's page used to draw its own flatter card with no body, so the same
// bill was two different objects depending on which page you reached it from
// and the detail a reader wanted was a page load away. Sharing the markup is
// also the only way the two stay the same as this card changes.
// The four stops a bill passes, and what happened at each. b.passage is
// "HSGL", one character a stop: p passed, h here now, x stopped here, - never
// reached.
//
// Every state has its own SHAPE as well as its own weight -- filled, ringed,
// crossed, empty -- because this is the site's one piece of ornament and it
// would be a poor one if it depended on telling two greens apart. The stops
// are labelled, so it is read rather than decoded.
//
// Nothing here calls an outcome good or bad. A bill dying is an outcome, not
// a failure, so a stop the bill did not get past is crossed in the same ink
// as one it passed, not in red.
// The four stops a bill passes, in the order IT travelled them. b.passage is
// five characters: the chamber it started in, then one a stop -- p passed,
// h here now, x stopped here, - never reached.
//
// A stop carries a green check where the bill got through and a red cross
// where it stopped, so the state is legible without knowing a key. The glyph
// says it and the colour agrees; neither carries it alone.
//
// AND TWO MARKS OF THE RAIL'S OWN (the person, 8 October 2026, from a
// measured sheet of the marks). A chamber that held the bill for interim
// study is "s", an orange disc with a white "~", where it was the red cross
// of a bill killed: the chamber decided, and the bill is parked, not dead.
// A chamber whose table the bill lies on while the session still sits is
// "t", a yellow disc with two white bars, the pause, where it was the ring
// of a bill moving. And a chamber whose table it died on is the pause too,
// where it was the cross (the person, 8 October 2026: "Show the body it was
// tabled in with the yellow pause, and show the red x mark on the law once it
// died when the session ended"): the Law stop keeps the cross, on the day it
// died. build_site_v2.journey_rail gives a stop these, from the bill's chip
// and the line that laid it on the table it died on, and
// How it got here draws the same two bare (JMARK). Each is a filled disc of
// the check's and the cross's weight with a glyph of its own -- check,
// cross, wave, two bars -- so greyscale, where the four discs are within a
// few points of each other's lightness, still tells them apart, and the
// empty ring of a stop not reached is never one of them. The wave is drawn,
// not typed (WAVE, above journeyList), so it centres in the disc at any
// size; the two bars are the stylesheet's (.stop.s-ontable b::after).
const CHNAME2={H:"House",S:"Senate"};
// THE MARKS, THEIR WORDS AND THEIR CLASSES ARE components.js's (RL_MARK,
// RL_SAY, RL_SAY_DIED, RL_SAID, RL_CLASS) since 10 October 2026, where the
// dated rail is drawn for a session day built ahead as for this page
// (components.rail_html): the pause of a bill that died on the table is
// heard as the tabling it was, "Senate: laid on the table, May 7, 2026", and
// its death at Law, "Law: stopped here, August 19, 2026"; a stop never
// reached is "s-o", and the rail's own two marks are classed by what they
// are. This bare rail reads the same tables.
const railCls=m=>`s-${esc((CMP.own(RL_CLASS,m)&&RL_CLASS[m])||m)}`;
// What the rail's own marks refine in b.passage, which has neither: the
// chip says which (build_site_v2.RAIL_MARK_OF_CHIP).
const RAILCHIP={"Interim Study":["x","s"],"Tabled":["h","t"]};
function rail(b){
  const p=b.passage||"";
  if(!CHNAME2[p[0]])return "";
  const other=p[0]==="H"?"S":"H";
  const own=RAILCHIP[chipOf(b)];
  // Only a chamber's stop: the first two of four, the first of a
  // resolution's two (its second is whether it was adopted).
  const n=p.length===3?1:2;
  const st=p.slice(1).split("").map((m,i)=>own&&i<n&&m===own[0]?own[1]:m);
  // A resolution belongs to one chamber and has two stops: that chamber, and
  // whether it was adopted. Four stops drew it against a Senate it was never
  // going to see and a Law it could never become.
  const stops = st.length===2 ? [CHNAME2[p[0]],"Adopted"]
              : st.length===4 ? [CHNAME2[p[0]],CHNAME2[other],"Governor","Law"]
              : null;
  if(!stops)return "";
  const said=stops.map((name,i)=>`${name}: ${(CMP.own(RL_SAY,st[i])&&RL_SAY[st[i]])||"not known"}`)
    .join("; ");
  return `<span class="rail" role="img" aria-label="${esc(said)}"
    title="${esc(said)}">${stops.map((name,i)=>
      `<span class="stop ${railCls(st[i])}"
        ><b>${(CMP.own(RL_MARK,st[i])&&RL_MARK[st[i]])||""}</b><i>${esc(name)}</i></span>`
    ).join("")}</span>`;
}

// THE RAIL, DATED -- on the bill's own page (the person chose it on 24
// September) and, since 5 October 2026, on every card in a list from the
// start: "One rail, always detailed". Under each stop the day of what
// happened there, and nothing else: "Senate / 22 May". The list card drew
// the bare rail above until then, and opening a card swapped one for the
// other, so the rail changed shape as the card opened; now opening it
// changes nothing about the rail. The bare one is left for a row that carries
// no stops (idxRow's stand-in for a bill the index does not hold).
//
// THE DAY ALONE, NOT THE WORDS (the person, 5 October 2026: "only have
// dates for the actions under each of the items since including the
// explanations like voice vote and such just crowds things up"). Each stop
// carried a word or two under its day as well -- "16–8, amended", "voice
// vote", "signed", "Chapter 160", "Nov 2026" -- and on a card in a list, five
// stops of that was a paragraph under every bill. How each chamber decided is
// told where it always was: How it got here, the history, the Votes tab and
// the voters' card. A stop with no day -- the Law stop, a vote the voters have
// still to take, a stop never reached -- has nothing under its name. The
// sentence a screen reader hears keeps its words, since nothing is drawn
// from it.
//
// Its stops follow the bill's route and come from the record's journey
// (build_site_v2.journey_rail): Introduced first; a resolution of one chamber
// has that chamber; a concurrent resolution two chambers and no governor; a
// CACR goes to the Voters, ringed while it waits for them. The marks are the
// index's passage, and the words are the same lines "How it got here" lists --
// one account in three places.
//
// A CARD IN A LIST HAS NO RECORD YET, so the index row carries the stops
// (b.rail, build_site_v2.index_rail): ["Sp","2025-05-22","16–8, amended"],
// the stop's letter and its mark, its day, and the words its sentence says.
// The bill's own page draws the record's rail, which is the same stops on the
// same days by construction (preflight holds the two equal on every bill) and
// carries what each stop says in full, for the sentence a reader hears.
//
// AND THE CARD KEEPS ITS ROW'S RAIL ONCE OPENED (cardHtml). It drew the
// record's as soon as the record came, and what was drawn stayed the same
// while what a screen reader heard changed under it: "Governor: passed,
// signed" became "Governor: signed, 27 June 2025" (the review of 5 October
// 2026). Opening a card changes nothing about its rail, seen or heard; a row
// with no stops is the one card that still waits for the record's.
//
// A stop not reached has no date. EVERY DATE CARRIES ITS YEAR, month first
// (the person, 8 October 2026: some stops carried the year and some did not,
// on the same bill -- "8 Jan 2025 ... 13 Feb ... 7 Jan 2026"). The year is
// its own span, so where the rail is too narrow for "Jan 8, 2025" on one
// line every stop sets its year on a line of its own alike (app.css, .ry),
// rather than one stop wrapping where its neighbours did not.
// The stops: the record's journey where the bill's record is here, else the
// index row's own ["Sp","2025-05-22","16–8, amended"], which
// components.rail_html reads as they are.
function railStops(b,d){
  const own=((d||{}).journey||{}).rail||[];
  return own.length?own:(b.rail||[]);
}
// THE DATED RAIL IS components.rail_html (railHtml) since 10 October 2026,
// moved there unchanged in what it draws and says, so that a session day
// built ahead in Python draws a bill card's rail as this page does. A row
// with no stops still draws the bare rail above.
function datedRail(b,d){
  const st=railStops(b,d);
  if(!st.length)return rail(b);
  return railHtml(st,chipOf(b)==="Died");
}

// THE CARD IS components.bill_card (billCard) since 10 October 2026 (the
// component plan's step 4 and C5, approved 9 October 2026), the same markup
// a session day built ahead in Python draws. Its head is no longer a button
// holding links: the number and year are the link to the bill's own page --
// which in the bill search opens it here, as the corner arrow did, and on a
// member's or a committee's page goes to it -- the title is the button that
// opens the card in place, and the corner arrow is gone, since the number
// says the same. The chip is the card's short word (components.card_word,
// D18: "Retained", "Passed House", "To the Voters"); the bill's own page
// keeps the full wording. "Carried over" is not drawn: the year beside the
// number says it (the person, 8 October 2026). The sponsor is the person
// chip (D14) and the committees mentions of their pages, the subject beside
// them but never the topic model's "Miscellaneous". `line` is what happened
// to the bill at the meeting or on the day a page lists it under.
// A member-elect's title in the page's language (find.js's findElectName): the
// row carries the English, "Rep.-elect Colin Mitchell (R)" (build_lsrs.elect_title).
const CARD_ELECT_TITLE=/^(Rep|Sen)\.-elect(?= )/;
function cardSponsor(b){
  const who=String(b.sponsor_label||b.sponsor||"").replace(CARD_ELECT_TITLE,(m,h)=>h==="Sen"
    ?tr("elect.title_sen","Sen.-elect"):tr("elect.title_rep","Rep.-elect"));
  if(!who)return null;
  const party=b.sponsor_party||(/\(([A-Z])\b/.exec(who)||[])[1]||"";
  return {display_full:who,party,slug:b.sponsor_slug||""};
}
// The site's own Miscellaneous is the topic model's for an archived bill
// ("granite record") and request_topics' for a request ("title").
const cardTopic=b=>(b.topic==="Miscellaneous"&&(b.topic_by==="granite record"||b.topic_by==="title"))?"":(b.topic||"");
// `cls`: a class beside "card" (a paged list's "unshown").
function cardHtml(b,focus,line,cls){
  const open=openCards.has(b.id);
  const y=b.year||(b.term?String(b.term).slice(0,4):"");
  const d=detail[dkey(b.id)];
  const body=focus||open?(d?renderDetail(b,d):`<p class="spin">Loading…</p>`):"";
  // A BILL'S OWN PAGE IS ITS HEAD AND ITS TABS (the record head, C6): the
  // article stays, since the tabs and their panes are found inside it.
  if(focus)return `<article class="card focus rec" data-id="${esc(b.id)}">${billHead(b,d)}`
    +`<div class="cbody">${body}</div></article>`;
  return billCard({id:b.id,href:`bill/${y}/${String(b.id).toLowerCase()}`,n:b.n,year:y,
    word:cardWord(chipOf(b),b.passage),cls:chipCls(b),title:b.title,
    byline:billByline(b._self?null:cardSponsor(b),b.committees||[b.committee],cardTopic(b),b.term,
      META.committee_codes),
    notes:whyLine(b),line:line||"",
    rail:datedRail(b,!(b.rail||[]).length?d:undefined),
    open,body,card:cls||""});
}
// TAGS:BEGIN
// The bill's own page, and only it, ends with its tags as searches (tagFoot).
cardHtml=(drawn=>function(b,focus,line,cls){
  const h=drawn(b,focus,line,cls);
  return focus&&TAGS_PLACE==="foot"?h.replace(/<\/article>$/,end=>tagFoot(b,detail[dkey(b.id)])+end):h;
})(cardHtml);
// TAGS:END

// A BILL'S NUMBER, ITS SUFFIXES MARKED FOR THEIR POPOVERS (C9: "FN in a
// bill's title too"): "HB 1083-FN" says what FN is on a tap or a held hover,
// and FN-A-LOCAL each of its parts. The number itself is the record's.
const SUFFIX_TERM={FN:"FN",A:"A",L:"LOCAL",LOCAL:"LOCAL"};
const billNumberTerms=n=>esc(n).replace(/-(FN|A|LOCAL|L)(?=-|$)/g,
  (_m,k)=>"-"+termMark(SUFFIX_TERM[k],k));
// "2025-2026" as a term is written in words: "2025–2026".
// components.js's termWords, under the name this file has always used;
// a declaration, so the term menu can ask for it before this line is reached.
function termDash(t){ return termWords(t||""); }
// A STAGE IS NOT WHERE A DEAD BILL STANDS (the audit of 25 October 2026, S4).
// HB 520 of 2017 showed "Died" over "Status: In committee": once its session
// has ended the chip says Died (build_site_v2.chip_word), and the record keeps
// the stage it stood at, which the build leaves where the record does not
// settle how it ended (ended_with_the_term). The page says that stage as the
// end it was -- in the words the build gives the same end on the bills beside
// it -- and changes nothing in the record. build_bill_pages.static_record
// says it the same way to a reader without scripts.
function statusShown(b){
  const s=String((b&&b.status)||"");
  return chipOf(b)==="Died"&&/^(in committee|committee report filed)$/i.test(s)
    ?"Died when the session ended":s;
}
// THE BILL'S HEAD (option E and the record head, C6): the trail -- Bills,
// the term, the kind of measure -- the number with its year and the full
// chip, the title as its one line, up to six facts (the prime sponsor as the
// person chip, the committees, the subject but never the topic model's
// "Miscellaneous", the chapter of law and when it took effect, and the
// status where it says more than the chip), the rail centred, and the
// actions. What the ON THE RECORD box carried is here, in How It Got Here,
// or under the analysis (the person, 8 October 2026: "Remove the ON THE
// RECORD box").
function billHead(b,d){
  const y=b.year||(b.term?String(b.term).slice(0,4):"");
  const tm=b.term||(d&&d.term)||"";
  const prime=((d&&d.sponsors)||[]).find(x=>x.prime);
  const sp=prime||cardSponsor(b);
  const cmtes=(b.committees||[b.committee]).filter(Boolean);
  const law=((((d||{}).journey||{}).rail)||[]).find(x=>x.stop==="Law"&&x.mark==="p"&&x.date);
  const topic=cardTopic(b)||(d&&!(d.subject==="Miscellaneous"&&d.subject_source==="granite record")
    ?(d.subject||""):"");
  const status=statusShown(b);
  const facts=[];
  if(sp)facts.push(["Prime Sponsor",pchip(Object.assign({},sp,{prime:false,role:""}))]);
  if(cmtes.length)facts.push([cmtes.length>1?"Committees":"Committee",
    cmtes.map(c=>cmteLink(c,tm,META.committee_codes)).join(" &middot; ")]);
  if(topic)facts.push(["Subject",esc(topic)]);
  if(d&&d.chapter)facts.push(["Chapter Law",`Chapter ${esc(d.chapter)}, Laws of ${esc(d.year||y)}`,
    law?`Effective ${esc(dateWords(law.date))}`:""]);
  else if(status&&status.toLowerCase()!==chipOf(b).toLowerCase())facts.push(["Status",esc(status)]);
  // THE TRAIL ENDS ON THIS BILL, AND ITS TERM IS THE SEARCH OPENED ON THAT
  // TERM (the person, 10 October 2026): "Bills > 2025-2026 Term > HB 396-FN",
  // where the term led to the term's directory index -- a page most readers
  // will not use -- and the trail ended on the kind of measure.
  const head=recordHead({trail:[["Bills",`${BASE}bills`],[`${termDash(tm)} Term`,
      tm?`${BASE}bills?term=${encodeURIComponent(tm)}`:""],[b.n||b.id,""]],
    title:billNumberTerms(b.n),year:y,chip:chip(chipOf(b),`cstat ${chipCls(b)}`,"m"),
    line:`<span translate="no">${esc(b.title)}</span>`,
    facts,rail:datedRail(b,d),actions:"",kind:"bill"});
  // "BACK TO SEARCH RESULTS" ABOVE THE TRAIL (backIsSearch and lastSearch,
  // above), where a list is behind the bill; the trail's Bills is the tab's
  // last search, or the search, as a plain link.
  const last=lastSearch(),to=last||`${BASE}bills`;
  const back=showBack()?`<p class="rback"><a href="${esc(to)}" data-back="1">`
    +`<span aria-hidden="true">&lsaquo; </span>Back to search results</a></p>`:"";
  return back+head.replace(`<li><a href="${esc(BASE)}bills">`,`<li><a href="${esc(to)}">`);
}

// TAGS:BEGIN
/* A BILL'S TAGS ON ITS OWN PAGE, AS SEARCHES (the owner, 17 November 2026,
   in place of design 5.1 and 5.2: "I don't want tags to be distracting to the
   layout as additional visual clutter and more of a helpful search tool, so
   maybe they could be listed at the bottom of a page or in a certain section
   tab like history"). No card and no list shows a tag, and the head has no
   row of them. On the bill's own page, each tag is a link to the bill search
   on All Terms with that tag ticked -- the history is the point -- under
   "Related searches", by the registry's name, its definition on the hover,
   in the registry's order. Where is the owner's choice, and TAGS_PLACE says
   it: "foot", a short list at the foot of the page, below the tabs and
   under every one; or "history", a section at the end of the History tab,
   with the bills that share this one's language. Nothing where the bill has
   no tag. */
let TAGS_PLACE="foot";
function tagLinks(b,d){
  const ids=tagIdsOf(b);
  const list=(ids.length?ids:((d&&d.tags)||[]).map(t=>t&&t.id)).map(tagOf).filter(Boolean);
  return list.map(t=>`<li><a href="${esc(BASE)}bills?term=all&amp;tag=${encodeURIComponent(t.id)}" `
    +`title="${esc(t.definition)}">${esc(t.name)}</a></li>`).join("");
}
function tagFoot(b,d){
  const li=tagLinks(b,d);
  return li?`<section class="tagfoot" aria-label="Related searches"><h2 class="tagfh">Related searches</h2>`
    +`<ul class="taglinks">${li}</ul></section>`:"";
}
function tagHistory(b,d){
  const li=tagLinks(b,d);
  return li?`<section class="rl-g tagsec"><h2 class="sech">Related Searches</h2><ul class="taglinks">${li}</ul></section>`:"";
}
// TAGS:END
// The tabs inside an expanded card are set after its HTML is in the document,
// because every tab's pane is written and only one is shown. Both renderers
// have to do it, so neither owns it.
// Which analyses the reader has opened out. Keyed on the bill, so opening
// one and then touching any other control does not shut it again.
const anOpen=new Set();

// THE WHOLE CARD OPENS IT (the person, 10 October 2026: "If you click
// anywhere on a bill card except another link like the title, the sponsor
// chip, or the committee, it should open the bill card"). A press on a list
// card's head that is on none of its own controls -- the number, a chip, a
// committee, a term, the rail's marks -- and is not the end of selecting
// text, is a press on its title: the title button that opens and shuts it,
// which stays the keyboard's way to do the same.
// ONLY A CONTROL INSIDE THE HEAD stops it (the owner's walk of dry run 8,
// 8 November 2026). On a member's or a committee's page the cards sit in a
// tab panel with tabindex="0", and the test for a control looked past the
// head to it, so every press there but the title's did nothing.
function cardBackground(e){
  const h=e.target.closest&&e.target.closest(".card:not(.focus) .chead");
  if(!h||e.button>0)return null;
  const ctl=e.target.closest("a,button,input,select,textarea,label,summary,details,[data-term],[tabindex]");
  if(ctl&&h.contains(ctl))return null;
  const s=window.getSelection&&window.getSelection();
  if(s&&String(s).length)return null;
  return h.querySelector(":scope > button.ctitle");
}

// A box is clamped unless the reader opened it, and gets a button only if it
// actually overflows -- which is a measurement, not a guess: the same 300
// characters are three lines on a desktop and eight on a phone.
// The clamp is 9 lines in app.css (.anbox.clamped); AN_SPARE is how far past it
// a text may run and still be shown whole rather than behind a button.
const AN_SPARE=3;
function clampAnalysis(){
  document.querySelectorAll(".card").forEach(card=>{
    const id=card.dataset.id;
    // EVERY .anbox ON THE CARD, not the first one. querySelector returned the
    // bill note, so on the two bills that have a note AND an analysis the
    // analysis was never clamped and never got a button: HB 2 of 2025 put
    // 13,340px of it -- twenty screens at 1440, thirty-six on a phone -- in
    // front of the table, the story and the docket. The open state is keyed
    // per box for the same reason; one key for the card would have opened
    // both or neither.
    card.querySelectorAll(".anbox").forEach((box,i)=>{
      const text=box.querySelector(".antext");
      if(!text)return;
      const key=id+"#"+i;
      const open=anOpen.has(key);
      box.classList.toggle("clamped",!open);
      let over=text.scrollHeight>text.clientHeight+2;
      // NOT FOR A FEW LINES (14 October 2026, the person's ask): a button
      // that hides two lines costs the reader a click to save them a glance,
      // and many analyses ended just past the clamp. So the box opens in full
      // when no more than AN_SPARE lines are past it.
      if(over&&!open){
        const lh=typeof getComputedStyle==="function"?parseFloat(getComputedStyle(text).lineHeight)||0:0;
        if(lh&&text.scrollHeight-text.clientHeight<=AN_SPARE*lh+2){
          box.classList.remove("clamped");
          over=false;
        }
      }
      let btn=box.querySelector(".anmore");
      if(over||open){
        if(!btn){
          btn=document.createElement("button");
          btn.className="anmore";
          btn.type="button";
          box.insertBefore(btn,box.querySelector(".src"));
        }
        btn.textContent=open?"Show less":"Show more";
        btn.setAttribute("aria-expanded",String(open));
        btn.dataset.an=key;
      }else if(btn){
        btn.remove();
      }
    });
  });
}

function syncCards(ids){
  ids.forEach(id=>{
    const c=document.querySelector(`.card[data-id="${id}"]`);
    let t=openTab[id]||"0";
    if(!c||!detail[dkey(id)])return;
    // A TAB THE BILL DOES NOT DRAW OPENS ITS SUMMARY: a saved /sponsors (the
    // Sponsors tab is the Summary's top since 19 November 2026), or /text on
    // a bill with no text, left every pane hidden under the strip.
    if(!c.querySelector(`.pane[data-t="${t}"]`)){t="0";openTab[id]="0";}
    c.querySelectorAll(".tab").forEach(x=>x.setAttribute("aria-selected",x.dataset.t===t));
    c.querySelectorAll(".pane").forEach(p=>p.hidden=p.dataset.t!==t);
  });
  // After the panes are shown, because a clamped box inside a hidden pane
  // measures zero and would never get its button.
  clampAnalysis();
  // A tab clicked on the strip moves the picker beside it, which is the same
  // state told twice: this runs on the cards whose selection just changed.
  showSelectedTab($("#results"));
}

// A record page names a bill by number, term and title and nothing else. The
// card wants its status, its sponsor and its committees, so the index row is
// looked up rather than reconstructed -- and the TERM is part of the lookup,
// because a bill number names one bill in each biennium.
function idxRow(b){
  const id=String(b.id||b.bill||"").toUpperCase();
  const t=b.term||"";
  return IDX.find(x=>x.id===id&&(!t||x.term===t))
      || (b.year?IDX.find(x=>x.id===id&&String(x.year)===String(b.year)):null)
      || {id,n:b.n||id,title:b.title||"",year:b.year||"",term:t,
          status:b.status||"",kind:b.kind||"",chip:b.chip||"",sponsor:"",committees:[]};
}

// The bills of one tab, as cards, with the outcome filter above them. "Bill
// status", not "Status": on a legislator's page a bare "Status: Died" sits
// under the member's own name and facts, and the word is a bill's.
// THE SEARCH'S CATEGORIES (the person, 8 October 2026, "Same categories"):
// In Progress, Passed, Tabled, Interim Study, Died, Withdrawn and Vetoed, in
// that order, only those a bill of this tab is in, and each option in its
// chip's colours as the sidebar paints it, the select itself too once one
// is chosen. It offered each chip's word -- Became Law, Adopted by the
// House, In committee, Re-referred to committee, each a choice of its own,
// in another order than the search's. A category chosen on one tab stays on
// offer on another with no bill in it (PAGE.status is the page's, not the
// tab's), so the empty list reads as its doing and it can be put back to
// Any where it was chosen; the cards keep their own words.
// THE NOTE UNDER IT SAYS HOW MANY OF THE TAB'S BILLS IT LISTS: `note` is
// given the bills listed and the tab's whole count, and says "24 of 137
// bills referred to this committee", as the search's count says "31 of 2,243
// bills" once something narrows it (billsOf). It was given the bills listed
// alone and said "24 bills referred to this committee in 2025-2026" under
// Passed beside a tab reading "Bills (137)", and "0 bills co-sponsored in
// 2025-2026" under a Withdrawn kept from the Prime sponsored tab beside
// "Co-sponsored (37)" (the review of 8 October 2026): a count of the member's
// or the committee's record that was not true of it.
// EACH CATEGORY WITH ITS COUNT (23 October 2026): "Passed (24)", the tab's
// bills in it, as the search's sidebar gives each its number and the Votes
// tab's select each vote its count; a category chosen elsewhere reads "(0)",
// which says why the list is empty. Any carries none, as the Votes tab's.
// `paged`: the list twenty at a time (PAGED_SHOWN), on a committee's page.
function billPane(rows,note,paged){
  rows=rows.slice().sort((a,b)=>billCmp(a.id,b.id));
  const n=Object.create(null);
  rows.forEach(b=>{const c=statusCat(b);if(c)n[c]=(n[c]||0)+1;});
  const cats=catsOffered(new Set(Object.keys(n)),new Set(PAGE.status?[PAGE.status]:[]));
  const shown=rows.filter(b=>!PAGE.status||statusCat(b)===PAGE.status);
  const on=CATCLASS[PAGE.status]||"";
  const cap=paged?pagedCap("bshow"):shown.length;
  return `<div class="bfilt"><label>Bill status
      <select data-pf="status" aria-controls="pbills"${on?` class="${on}"`:""}><option value="">Any</option>
      ${cats.map(x=>`<option value="${esc(x)}" class="${CATCLASS[x]||""}"${
        x===PAGE.status?" selected":""}>${esc(x)} (${(n[x]||0).toLocaleString()})</option>`).join("")}</select></label></div>
    <p class="src">${note(shown.length,rows.length)}</p>
    <div class="cards" id="pbills">${shown.map((b,i)=>{const out=i>=cap?"unshown":"";
      return b.lsr?lsrCardHtml(b,out):cardHtml(b,false,b._line,out);}).join("")}</div>${
      paged?pagedMore("bshow","pbills",Math.min(cap,shown.length),shown.length):""}`;
}

/* A COMMITTEE'S LONG LISTS, TWENTY AT A TIME (the person, 23 October 2026).
   House Executive Departments and Administration's page was 94,689px tall
   at 375px wide: a full card for each of the 164 bills referred to it in
   2025-2026, the term it opens on, about 560px a card on a phone. Its
   Meetings tab, 46 days folded, was 17,712px. Each now shows the first
   twenty, in the order it already had -- the bills by number, as the search
   lists them; the days newest or oldest first, as the reader chose -- and a
   button under the list brings the next twenty.

   EVERY ONE IS STILL IN THE PAGE, AND ON PAPER. The rest carry .unshown,
   which app.css hides on a screen and nowhere else, so a committee's page
   printed is every bill and every day, as it was; the button and its count
   are left off the sheet. Without script the page is static_record's, which
   lists every bill of the newest term.

   THE KEYBOARD GOES TO THE FIRST ONE IT BROUGHT: the redraw replaces the
   button, and focus on nothing sent the next Tab to the top of the page (the
   Votes tab's Show more, the review of 2 October 2026). A card's first stop
   is its number; a day's, its summary. The button names the list it adds to
   (aria-controls) and carries how many are shown (data-from), which is where
   that first one is.

   A DAY THE ADDRESS NAMES IS ALWAYS SHOWN: the Calendar leads to
   committee/<code>.html#day-<date>, and the list stretches as far
   as that day, on arrival and when the address changes after
   (renderCommitteeSessions, showDay). The status select, the order and the
   term each start the list again at twenty. */
const PAGED_SHOWN=20;
const pagedCap=k=>Math.max(PAGED_SHOWN,(PAGE&&+PAGE[k])||0);
// The button under a paged list: `key` is PAGE's count of it, `box` the id of
// the list, `shown` how many are, `of` how many it has.
function pagedMore(key,box,shown,of){
  const left=of-shown;
  if(left<=0)return "";
  return `<button type="button" class="discl pgmore" data-pmore="${esc(key)}" data-from="${shown}"
    aria-controls="${esc(box)}">Show ${Math.min(PAGED_SHOWN,left).toLocaleString()} more &mdash;
    ${left.toLocaleString()} of ${of.toLocaleString()} not yet shown</button>`;
}
// "137 bills", or "24 of 137 bills" where fewer than all are listed.
const billsOf=(n,of)=>`${n===of?"":`${n.toLocaleString()} of `}${
  of.toLocaleString()} bill${of===1?"":"s"}`;

// The term, above the tabs, because it governs all of them.
function termControl(){
  const ts=(PAGE&&PAGE.terms)||[],t=pageTerm();
  if(ts.length<2)return "";
  return `<div class="bfilt pterm"><label>Term
    <select data-pf="term">${ts.map(x=>
      `<option value="${esc(x)}"${x===t?" selected":""}>${esc(termLabel(x))}</option>`
    ).join("")}</select></label></div>`;
}

/* ONE TAB STRIP, AND ON A PHONE IT SCROLLS (16 September).

   Seven sections -- Summary, Bill Text, Votes, Videos, Reports, Sponsors,
   Documents -- wrapped onto three rows at 360px: 120 pixels of chrome above a
   record somebody had already chosen. A phone-only picker was tried first and
   taken out the same day: the person's steer is that the site should be one
   set of styles rather than several systems stitched together, and a second
   control for the same seven sections is exactly that. So the strip stays the
   strip everywhere and the stylesheet lets it scroll below 720px.

   What that costs is that the last tabs sit off the edge, which is why the
   selected one is scrolled into view here -- after a render and after a click,
   so the strip always shows where you are, with the next tab half in frame to
   say there is more. */
function showSelectedTab(scope){
  (scope||document).querySelectorAll(".tabs").forEach(strip=>{
    if(strip.scrollWidth<=strip.clientWidth+2)return;
    const on=strip.querySelector('.tab[aria-selected="true"]');
    if(!on)return;
    const want=on.offsetLeft-(strip.clientWidth-on.offsetWidth)/2;
    strip.scrollTo({left:Math.max(0,want),behavior:"auto"});
  });
}
// THE TAB THE KEYBOARD IS ON IS IN VIEW. Tabbing along a strip that scrolls
// sideways left the focused tab off its edge: at 360px "Documents (6)" on
// HB 2 of 2025 stood at 322 to 413 in a strip ending at 331, its ring out of
// sight (the review of 2 October 2026). The strip is scrolled the least that
// shows the whole tab and its ring, 8px clear of either edge.
document.addEventListener("focusin",e=>{
  const t=e.target&&e.target.closest&&e.target.closest(".tabs .tab");
  const strip=t&&t.parentElement;
  if(!strip||strip.scrollWidth<=strip.clientWidth+2)return;
  const a=t.getBoundingClientRect(),b=strip.getBoundingClientRect(),pad=8;
  if(a.left<b.left+pad)strip.scrollLeft-=b.left+pad-a.left;
  else if(a.right>b.right-pad)strip.scrollLeft+=a.right-(b.right-pad);
});

// One strip per member or committee page, so the ids are fixed: ptab_<i> for a
// tab and ppane for the panel it controls, which pagePane() writes.
function tabStrip(tabs){
  return `<div class="tabs" role="tablist">${tabs.map((t,i)=>
    `<button class="tab" role="tab" id="ptab_${i}" aria-controls="ppane" data-pt="${i}" aria-selected="${
      i===PAGE_TAB}">${esc(t[0])}${t[1]?tabN(t[1].toLocaleString()):""}</button>`
  ).join("")}</div>`;
}
function pagePane(html){
  return `<div class="pane" role="tabpanel" id="ppane" aria-labelledby="ptab_${PAGE_TAB}" tabindex="0">${html}</div>`;
}

// ONE CHIP FOR A PERSON is components.js's pchip, which every page loads.
const mchip=pchip;

