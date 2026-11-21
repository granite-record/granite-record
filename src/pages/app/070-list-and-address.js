// The same order for two bare bill numbers. A committee's bills, a member's
// and a calendar slot arrive already listed by the build (bill_order.py is
// this key in Python), and these sort them again so that the page never
// depends on the file having done it: those lists have no sort control, and
// as text HB 1003 came before HB 101.
const billCmp=(a,b)=>{const x=billKey({id:String(a||"")}),y=billKey({id:String(b||"")});
  return x[0]-y[0]||x[1]-y[1];};
// A bill has one status and one subject, but it can pass through two
// committees, so a facet value is a list. Sorting the list alphabetically also
// groups it: every House committee, then every Senate one.
function facetVals(b,k){
  // TAGS:BEGIN
  if(k==="tag")return tagIdsOf(b);
  // TAGS:END
  // The Status filter is the chip's category (statusCat), not its word. Not
  // chipOf: a request has no chip, and its own word -- Requested, Filed,
  // Withdrawn -- is its category (13 November 2026).
  if(k==="status")return [statusCat(b)];
  if(k==="type")return [typeOf(b)];
  if(k==="committee")return b.committees||(b.committee?[b.committee]:[]);
  // A SPONSOR IS THE PRIME SPONSOR, AND A CO-SPONSOR ONLY WHERE THE READER
  // TICKS "Include co-sponsored bills" (Alice, 8 November 2026: "by default it
  // should only be prime sponsored bills"). It had been either, always (the
  // person, 12 October 2026). build_site_v2 writes the co-sponsors' names as
  // `cosp`, spelled as the prime sponsor's is; render() puts a chosen
  // sponsor's own bills first.
  if(k==="sponsor")return withCosp&&b.cosp?[spKey(b),...b.cosp]:[spKey(b)];
  if(k==="party")return [partyOfSponsor(b)];
  return [b[k]];
}
// THE PRIME SPONSOR'S PARTY (Alice, 8 November 2026: "filter by the prime
// sponsor's party"), as the record has it for the bill's own term: the row's
// `sponsor_party` is the party the roster gives that person for that term
// (build_site_v2), not the one they hold today -- save 1989-1998, which have
// no roster of the term: there it is their page's where every record of
// them gives that one party, else the one the bill's term's Manual gives
// them where it names one (build_site_v2.early_party, the owner, 15
// November 2026). The party's name as the
// roll calls' legend says it (PARTY_NAME), and "Party not on file" where the
// bill names no sponsor or the record gives the sponsor none. Every bill is
// in exactly one of them, so the options add up to the list.
const partyOfSponsor=b=>PARTY_NAME[String(b.sponsor_party||"").toUpperCase().slice(0,1)||"X"]||"Other party";
// Republicans, then Democrats, then any other by name, then not on file.
const partyCmp=(a,b)=>{const r=v=>v===PARTY_NAME.R?0:v===PARTY_NAME.D?1:v===PARTY_NAME.X?3:2;
  return r(a)-r(b)||String(a).localeCompare(String(b));};
// Each with its party's colour, as the roll calls' legend keys a party (a
// swatch), where a person's chip would be a name a translator must not touch.
const partyShow=v=>{const code=Object.keys(PARTY_NAME).find(k=>PARTY_NAME[k]===v)||"X";
  return `<span class="sw" style="background:${PARTY_COLOR[code]}"></span><span>${esc(v)}</span>`;};
// Whether the bill's PRIME sponsor is one the Sponsor filter has chosen.
const primeChosen=b=>sel.sponsor.has(spKey(b));

// NEWER TERM FIRST, which changes nothing in a list of one term and orders
// the list on All terms: by number, two bills of one number (HB 1 is in
// every term) run newest first; by best match, each term's bills together,
// the newest term's first, under a heading of their own (render, termHead;
// Alice, 8 November 2026), and inside a term in the best match's order
// (sortRows). Without it those came in whichever order the terms' indexes
// happened to arrive, and /search's list of every term's bills (find.js's
// findBills, which orders them this way) could not be the same list (24
// September).
const newerTerm=(a,b)=>{const x=String(a.term||""),y=String(b.term||"");
  return x<y?1:x>y?-1:0;};
function sortRows(rows){
  const by={
    num:(a,b)=>{const x=billKey(a),y=billKey(b);
                return x[0]-y[0] || x[1]-y[1] || newerTerm(a,b);},
    // HIGH TO LOW (the owner, 16 November 2026: "work ascending or descending
    // with bill numbers"): the kinds in the same order (House bills, then the
    // Senate's, then the rest), the numbers inside each the other way, and in
    // All Terms the newer term's first, as low to high has it.
    numdesc:(a,b)=>{const x=billKey(a),y=billKey(b);
                    return x[0]-y[0] || y[1]-x[1] || newerTerm(a,b);},
    recent:(a,b)=>(b.last_action||"").localeCompare(a.last_action||"")
                  || billKey(a)[1]-billKey(b)[1],
    // THE OTHER WAY IN TIME (Alice, 8 November 2026: "a sort option for
    // the other chronological direction"): the same date as "recent", the
    // oldest first, and the same tie by number. A bill with no action
    // recorded has no date to be old by, and comes last either way, as it
    // does in "recent".
    oldest:(a,b)=>(!a.last_action)-(!b.last_action)
                  || (a.last_action||"").localeCompare(b.last_action||"")
                  || billKey(a)[1]-billKey(b)[1],
    // Bills still moving come first, because those are the ones a reader can
    // still do something about -- turn up, sign in, write to the committee.
    // After that the outcomes group together and run alphabetically inside
    // each group. That is a filing order, not a ranking: a bill dying is an
    // outcome, not a failure, and nothing here puts one outcome above another.
    // A group is a category of the Status filter, in its order (In Progress,
    // Passed, Tabled, Interim Study, Died, Withdrawn, Vetoed: the person, 8
    // October 2026), and inside it the bills run by their chip's word and
    // then by their status, as the groups ran before they were categories:
    // Became Law before Adopted by the House, and the Died listed killed
    // with killed and tabled with tabled.
    status:(a,b)=>catCmp(statusCat(a),statusCat(b))
                  || chipCmp(chipOf(a),chipOf(b))
                  || (a.status||"").localeCompare(b.status||"")
                  || billKey(a)[1]-billKey(b)[1],
  }[sortBy]||(()=>0);
  // BEST MATCH: every word of the search as a word of the title or the
  // sponsor's name before the start of a longer one (looseness), then the
  // most of the search in the title, then the sponsor, then the committee
  // (matchScore). Among bills that match equally well (16 October 2026): a
  // bill still moving first, where its title has the search; then the most
  // of the title that is the search (titleShare); and bill number last.
  // "Still moving" is the one category put above another, for the reason
  // the Status sort gives -- a reader can still do something about it -- and
  // nothing else here reads a bill's status: Passed is not put above Died,
  // nor Died above Interim Study. Only where the title has the search, so
  // that a search by a sponsor's name keeps their bills in number order.
  // ON ALL TERMS, A TERM AT A TIME (Alice, 8 November 2026): the newest
  // term's bills first, in that order, then the term before's, each under
  // its heading (render, termHead). The newer term had been a tie-break, so
  // an older term's bill ran in among the newest's wherever it matched
  // better. In one term it decides nothing.
  if(sortBy==="best"){
    const gs=groupsFor(query.trim());
    const lo=new Map(rows.map(b=>[b,looseness(b,gs)]));
    const sc=new Map(rows.map(b=>[b,scoreOf(b)]));
    const sh=new Map(rows.map(b=>[b,titleShare(b,gs)]));
    const live=b=>sh.get(b)>0&&statusCat(b)==="In Progress"?1:0;
    const num=(a,b)=>{const x=billKey(a),y=billKey(b);return x[0]-y[0]||x[1]-y[1];};
    return rows.slice().sort((a,b)=>newerTerm(a,b)||lo.get(a)-lo.get(b)||sc.get(b)-sc.get(a)
      ||live(b)-live(a)||sh.get(b)-sh.get(a)||num(a,b));
  }
  return rows.slice().sort(by);
}
const sel={committee:new Set(),topic:new Set(),sponsor:new Set(),status:new Set(),
           type:new Set(),voteday:new Set(),rsa:new Set(),party:new Set()};
// TAGS:BEGIN
// The tags ticked, by id: inside the Topic group, under its own key (?tag=).
sel.tag=new Set();
// TAGS:END
// THE STATUTE FILTER (the person, 11 October 2026: the RSA search replaces the
// floor vote day filter). A bill's index row carries `rsa`, the chapters and
// sections its own text says it changes (rsa.py), each section's chapter with
// it; a chapter or a section chosen here (rsaGroup, Laws Changed) keeps the
// bills that change it. RSA_SHAPE reads "RSA 91-A:4", "91-a:4" or "91-A"
// alike, in the address (?rsa=) and in the search box.
let rsaText="";
// THE FILTERS AND THE ORDER AN ADDRESS NAMES, ticked as the list would have
// written them (addressList): read when the page loads, and when Back puts a
// list's own entry back (listFromAddress).
function filtersFromAddress(params){
   // Every topic the address names, as addressList writes each one ticked:
   // reading the first alone lost the rest on every Back once Back read the
   // address (the second review of 7 November 2026), and on a reload before.
   for(const pt of params.getAll("topic"))
     if(pt&&(META.topics||[]).includes(pt)) sel.topic.add(pt);
   // TAGS:BEGIN
   // ...and every tag, by its id (?tag=), ignored where meta.json has no such tag.
   for(const w of params.getAll("tag"))if(w&&tagOf(w))sel.tag.add(w);
   if(sel.tag.size)openGroups.add("tag");
   // TAGS:END
   // ...or with a Status or a Bill Type named, the same way: ?status=Passed,
   // ?type=CACR. A status is read through catOfWord, so an address written
   // with a chip's own word -- ?status=Became%20Law, ?status=In%20committee,
   // what the filter offered before 8 October 2026 -- ticks the category
   // that word is now in. Each may be given more than once; a word that is
   // neither a category nor any bill's chip, or letters that are no kind of
   // measure, is ignored like an unknown topic. One that is, and that this
   // term has none of, stays ticked and is offered at none, so the empty
   // list says why.
   for(const w of params.getAll("status")){
     const c=catOfWord(w,IDX); if(c)sel.status.add(c);}
   for(const w of params.getAll("type")){
     const t=String(w||"").trim().toUpperCase();
     if(t&&(TYPE_NAME[t]||IDX.some(b=>typeOf(b)===t)))sel.type.add(t);}
   // ...or from the home page's Latest activity, which shows five rows and
   // hands the rest over here. The sort has to survive the arrival, so
   // sortChosen is set: without it the first render would helpfully put the
   // list back on bill number and the reader would land on the opposite of
   // what they clicked. An unknown value is ignored rather than accepted,
   // because the picker only offers five.
   // ...and the rest of the filters the list itself writes into its address
   // (addressList): a committee, a prime sponsor, a floor vote day, each as
   // the facet names it. Ticked as given; one this term has none of is
   // offered at none, as a status is.
   withCosp=params.get("cosp")==="1";
   for(const k of ["committee","sponsor","voteday","party"])
     for(const w of params.getAll(k)){const v=String(w||"").trim();if(v)sel[k].add(v);}
   // The party is a choice inside the Sponsor group: it opens with it.
   if(sel.party.size)openGroups.add("sponsor");
   {const r=rsaNorm(params.get("rsa")||"");if(r){sel.rsa.add(r);rsaText=r;}}
   const psort=params.get("sort");
   if(psort&&["best","num","numdesc","recent","oldest","status"].includes(psort)){
     sortBy=psort; sortChosen=true;
     const so=$("#sort"); if(so)so.value=psort;
   }
}
// THE LIST BACK AS ITS OWN ENTRY SAYS IT WAS (the reviews of 7 November
// 2026). Back from a bill puts the list's entry back, and that address is
// the whole of the list as it stood: its words where a search was run, its
// term, every filter ticked and an order chosen (addressList writes them
// all). Taking the words alone drew a list nobody saw -- Back twice, from a
// list of HB 1 in 2023-2024 past the bill to /bills?q=HB+703&term=all, drew
// HB 703 in 2023-2024 and wrote that over the entry. Words typed and never
// run are not in an address; where it names none, the words the list was
// left with are in its entry (entryWords), and are taken from there -- the
// box kept whatever a later list had put in it, and Back twice drew those
// words over the first list (the second review of 7 November 2026).
function listFromAddress(){
  const p=new URLSearchParams(location.search);
  const aq=p.get("q"),st=history.state;
  // An entry whose address names no words and holds none is a list of no
  // words (entryWords keeps them wherever there were any).
  const words=aq!==null?aq:(st&&typeof st.words==="string"?st.words:"");
  query=words;$("#q").value=words;
  const t=wantedTerm(META);
  if(t&&t!==term){term=t;forgetCardState();}
  const ys=$("#year"); if(ys)ys.value=term;
  for(const k of Object.keys(sel))sel[k].clear();
  rsaText="";
  sortChosen=false;sortBy="num";
  const so=$("#sort"); if(so)so.value=sortBy;
  filtersFromAddress(p);
}
const RSA_SHAPE=/^\s*(?:rsa\s*)?(\d{1,3}(?:-[a-z]{1,2})?)(?:\s*:\s*([0-9]{1,4}(?:\.[0-9]{1,2})?(?:-[a-z0-9]{1,4})?))?\s*$/i;
/* A LAW CITED TO ITS PARAGRAPH (the owner's test, 6 November 2026): "RSA
   91-A:4 IV" and "91-A:4, IV" found nothing, while "91-A:4" listed the bills
   that change it. Bills are indexed to the section, so a paragraph after
   one -- IV, "(iv)", "IV(a)", with or without a comma -- is read as the
   section. find.js's findLaw reads it the same way (RSA_PARAGRAPH there). */
const RSA_PARAGRAPH=/^(\s*(?:rsa\s*)?\d{1,3}(?:-[a-z]{1,2})?\s*:\s*[0-9]{1,4}(?:\.[0-9]{1,2})?(?:-[a-z0-9]{1,4})?)\s*(?:,\s*)?(?:\(?[ivxlc]+\)?|\([a-z0-9]{1,4}\))(?:\s*\([a-z0-9]{1,4}\))*\s*$/i;
function rsaNorm(t){const m=RSA_SHAPE.exec(String(t||"").replace(RSA_PARAGRAPH,"$1"));return m?m[1].toUpperCase()+(m[2]?":"+m[2].toLowerCase():""):"";}
function rsaHas(b,want){return (b.rsa||[]).includes(want);}
// The statute a search names, worked out once for the search and not again
// for each bill matches() is asked about (the review of 7 November 2026).
let RSAQ_OF=null,RSAQ="";
function rsaOfQuery(q){if(q!==RSAQ_OF){RSAQ_OF=q;RSAQ=rsaNorm(q);}return RSAQ;}
// A CHAPTER'S ADDRESS, AS build_rsa.chapter_path WRITES IT (the sitemap
// audit, 16 October 2026): RSA 404's page is a folder's index.html, which the
// host serves at the address with a slash and redirects to from the one
// without. LAW_FOLDERS is build_rsa.FOLDER_CHAPTERS, and preflight holds the
// two to each other. Every chapter address this file draws comes from here.
const LAW_FOLDERS=["404"];
function lawPath(ch,sec){const s=String(ch).toLowerCase();
  return "/laws/"+s+(LAW_FOLDERS.includes(s)?"/":"")+(sec?"#s"+sec:"");}
function rsaHref(a){const p=a.split(":");return lawPath(p[0],p[1]);}
// WHETHER THE LISTED TERM'S BILLS SAY WHICH LAWS THEY CHANGE, asked of the
// term on the list (the review of 26 October 2026). Every term's bills do but
// the bill requests', which have no text yet. It was asked once, of whatever
// was loaded first, so a page opened on ?term=2027-requests had no Laws
// Changed filter in any term it was switched to. Kept for each term and for
// what is loaded of it, since a term's rows arrive after it is chosen.
const HAS_RSA={};
function hasRsa(){
  const k=term+" "+IDX.length;
  if(!(k in HAS_RSA))HAS_RSA[k]=IDX.some(b=>b.rsa&&b.rsa.length&&inTermOf(b));
  return HAS_RSA[k];
}
// 5a (the person, 9 October 2026, item 2): STATUS AND BILL TYPE OPEN,
// COMMITTEE CLOSED, at every width -- inside the Filters panel below 960px as
// well, so a reader who opens it sees the categories at once (round two's
// question 8a, as recommended). Both are short and shown whole, and Status
// answers the commonest question; the committee list is the long one.
// STATUS ALONE SINCE 12 OCTOBER 2026 (the person: "Just have the status
// filter open by default rather than status and bill type"). Bill Type is
// folded with the rest, one tap away.
const openGroups=new Set(["status"]);
let sponsorFilter="";
let topicFilter="";
let withCosp=false;
const openCards=new Set(),openTab={},detail={},segSel={},fullOpen=new Set();
// The bills whose How it got here the reader opened past its first six lines.
const jOpen=new Set();

/* A TAB HAS AN ADDRESS, 14 September. /bill/2026/hb1442/votes opens that
   bill's Votes tab, /legislator/<who>/votes a member's, /committee/H05/sessions
   a committee's; choosing a tab puts its address in the bar, so it can be
   shared. The canonical link stays the record's own address and no tab
   address is in the sitemap, so a search engine indexes each record once.
   site/_redirects (build_pages.py, the same slugs) serves the record's page
   at a tab's address. The first tab of each has no slug: its address is the
   record's. */
// "videos" comes BEFORE "hearings" and both map to 2. slugOf takes the first
// key with a matching value, so a tab switched today writes /videos -- the
// tab is Videos again (the owner, 19 November 2026) -- while a link somebody
// already saved or a search engine already indexed still opens on /hearings.
// An address that has been published is a promise; renaming the label is not
// a reason to break it.
// AND /sponsors (the same day): the Sponsors tab became the top of the
// Summary, and its address is kept for the links already made. It names tab
// 4, which a bill no longer draws, so the bill opens on its Summary, where the
// sponsors are (syncCards); a request's card keeps its own Sponsors tab.
const BILL_TABS={text:"6",votes:"1",videos:"2",hearings:"2",
                 reports:"3",sponsors:"4",documents:"5",related:"7"};
const MEMBER_TABS={cosponsored:1,votes:2,elections:3};
// A committee's Videos tab (the owner, 26 October 2026) is "videos", a slug
// a bill's page keeps for its Hearings tab too: TAB_PATH tells a bill's
// address from a committee's, so the two never meet.
// AND "bills" (29 October 2026): a study committee's page lands on its
// Meetings, so its Bills tab is at /committee/ss57/bills, which the
// committee rewrite serves for every committee. A standing committee's
// Bills is still its page's own address, the one this script writes
// (slugOf gives tab 0 no slug), and /bills opens it there too.
const COMMITTEE_TABS={bills:0,sessions:1,videos:2};
const TAB_PATH=/^(\/(?:bill\/\d{4}\/[a-z]{2,5}\d+|legislator\/[^\/]+|committee\/[^\/]+))\/([a-z]+)\/?$/i;
// A slug is one a map names, whatever tab it stands for: Bills is tab 0.
const ownSlug=(map,s)=>Object.prototype.hasOwnProperty.call(map,s);
const isTabSlug=s=>ownSlug(BILL_TABS,s)||ownSlug(MEMBER_TABS,s)||ownSlug(COMMITTEE_TABS,s);
function tabFromPath(){
  const m=TAB_PATH.exec(location.pathname);
  return m&&isTabSlug(m[2].toLowerCase())?m[2].toLowerCase():"";
}
// `hash`: the fragment kept, where the address named a place on the tab it
// asked for -- a day (showDay) or a recording (showVideo).
function tabAddress(slug,hash){
  const m=TAB_PATH.exec(location.pathname);
  const base=m&&isTabSlug(m[2].toLowerCase())?m[1]:location.pathname.replace(/\/$/,"");
  try{history.replaceState(history.state,"",base+(slug?"/"+slug:"")+location.search
    +(hash?location.hash:""));}catch(_){}
  addressed();
}

// THE SKIP LINK MUST POINT AT THIS DOCUMENT, and after a tab is opened it did
// not. shell.py writes it absolute -- href="/bill/2026/hb1442#results" -- and
// it has to: bills.html carries <base href="/">, so a bare "#results" would
// resolve to the home page. But opening the Votes tab rewrites the address to
// /bill/2026/hb1442/votes, and the skip link then names a DIFFERENT document.
// It is the first thing a keyboard reaches on the page, so the reader most
// likely to use it is the one it navigates away from -- and because the
// opening tab is read out of the path, landing back at the canonical address
// throws the tab away rather than merely redrawing it.
// AND ITS SEARCH. Written with the path alone, the link on /bills?q=bathroom
// named /bills -- another document -- and following it loaded the list
// again without the search, the keyboard back in the box (2 October 2026).
function skipHere(){
  const s=document.querySelector("a.skip");
  if(s)s.setAttribute("href",location.pathname+location.search+"#results");
}
// The skip link takes the keyboard with it: find.js, which every page runs.
// The first tab is the record's own address: no slug, though a committee's
// /bills names it too.
const slugOf=(map,v)=>v===0?"":Object.keys(map).find(k=>map[k]===v)||"";
// WHERE THE ADDRESS STOOD, WITHOUT ITS FRAGMENT, when this script last wrote
// it or was last told it had moved. A link to a place on the page -- the skip
// link is one -- adds an entry to history and fires popstate with no state,
// which is also what going back from a bill to the list fires. The two are
// told apart by this: only the fragment moved, or the page did. Everything
// here that writes the address calls addressed(), which also keeps the skip
// link naming this document.
let STOOD=location.pathname+location.search;
function addressed(){
  STOOD=location.pathname+location.search;
  skipHere();
}
try{skipHere();}catch(_){}

// A BILL NUMBER IS NOT UNIQUE ACROSS TERMS, and four of those five are keyed
// on the bare number. HB 100 exists in most terms and is a different bill in
// each, so expanding a few rows and then changing the term left those same
// numbers expanded -- showing the NEW term's bills opened, on the strength of
// what a reader had opened in the old one, with whichever tab the old bill had
// been left on.
//
// detail is the exception and needs no clearing: dkey() keys it on
// `${yearOf(id)}/${id}`, so the cache is already per term and keeping it means
// switching back does not refetch.
//
// This is the same confusion build_data.py guards against on the data side --
// "HB100 of 2023 and HB100 of 2025 have different sponsors, and a flat file
// gives the second to the first without saying so" -- arriving in the browser
// as view state rather than as data.
function forgetCardState(){
  openCards.clear();
  fullOpen.clear();
  jOpen.clear();
  for (const k of Object.keys(openTab)) delete openTab[k];
  for (const k of Object.keys(segSel)) delete segSel[k];
}
// Which bill is filling the screen, and where the reader was standing when
// they opened it. heldTerm is a term the picker chose while it was open,
// taken when it is closed (the picker's change handler, and unfocus) -- or
// the reader's own term, held while a bill opened in its own (focusBill, a
// Back to a bill's entry). heldPicked says which: on Back to a list's entry
// a term the reader chose is taken, and one only held gives way to the term
// the entry names (listFromAddress).
let focused=null,focusY=0,heldTerm=null,heldPicked=false,heldSort=null;
// Bills whose procedural lines the reader has chosen to see.
const showRoutine=new Set();

// Report which file failed and why. The old handler blamed file:// for every
// failure, including a missing or malformed JSON file, which sent people
// looking in entirely the wrong place.
// Anchored to the site root, not to the page.
//
// The same page is served at /bills and /bills.html, and a bills/ folder of
// per-bill data sits alongside it -- so a request for /bills can be redirected
// to /bills/, and a relative "bills/HB1123.json" then resolves to
// /bills/bills/HB1123.json. That is why refreshing while looking at a bill
// gave "Detail unavailable" while the same file loaded from the search page.
const DATA=(f)=>new URL(f, location.origin + "/").href;
// The site's root, so a pushed address is absolute rather than relative to
// whatever folder the current page happens to sit in -- /bill/2026/ is three
// deep and a relative push from there lands in /bill/2026/bill/2026/.
//
// ONE ADDRESS FOR THE BILL SEARCH PAGE, reported by the person on 16 September.
// It was reachable at three: /bills from the header, /bills?q= from the home
// page's Search with an empty box, and /bills.html from the back button on a
// bill. The last is the one a redirect cannot tidy -- history.pushState never
// touches the network, so the .html the host would have redirected stayed in
// the address bar. Three addresses for one page is three entries in a reader's
// history, three things to paste to somebody, and three ways for a link to be
// shared.
//
// The host serves /bills and redirects /bills.html to it, so that is the one.
const BASE="/";
const need=(f)=>fetch(DATA(f)).then(r=>{
  if(!r.ok)throw new Error(`${f} returned ${r.status} ${r.statusText}`);
  return r.json().catch(()=>{throw new Error(`${f} is not valid JSON`);});
});
// A record's own page is served at both /bill/2026/hb1123.html and
// /bill/2026/hb1123. Show the second, so the address bar matches what the
// site links and what a reader would paste. Same document either way, so this
// replaces rather than pushes.
if(/^\/(?:bill|legislator|committee)\/.+\.html$/.test(location.pathname)){
  try{history.replaceState(history.state,"",
    location.pathname.slice(0,-5)+location.search+location.hash);}catch(_){}
  try{addressed();}catch(_){}
}
// WHICH TERM TO LOAD FIRST. A record page names it in its own address --
// /bill/2026/hb1442 -- so a 1995 bill loads the 1995 index and not the
// current one. Anything else starts at the newest, which is what the picker
// opens on.
function wantedTerm(m,now=new Date()){
  const terms=(m.terms&&m.terms.length)?m.terms:[];
  const mm=location.pathname.match(/^\/bill\/(\d{4})\//);
  if(mm){
    const y=+mm[1], t=terms.find(x=>{const a=+String(x).slice(0,4);return y===a||y===a+1;});
    if(t)return t;
  }
  // ...OR THE BILL SEARCH'S ADDRESS NAMES IT: ?term=all, which /search's
  // "All 412 bills that mention bail" opens on since 24 September, when that
  // page began counting every term's bills. A term the picker offers is
  // taken too; anything else is ignored and the search opens as it always
  // has, on the newest.
  if(!mm&&!window.GR_STATIC&&!window.GR_MEMBER&&!window.GR_COMMITTEE){
    const want=new URLSearchParams(location.search).get("term");
    if(want===ALL_TERMS||terms.includes(want)
       ||(m.requests&&want===m.requests.term))return want;
    if(!want&&requestsFirst(m,now))return m.requests.term;
  }
  return terms[0]||"";
}
// THE SEARCH OPENS ON NEXT SESSION'S BILL REQUESTS AFTER THE ELECTION (the
// owner, 11 November 2026): from the day after the general election -- the
// Tuesday after the first Monday in November of the year before the
// requests' own -- until the new term's bills are introduced, with no date to
// keep. THROUGH DECEMBER, NOT TO THE FIRST BILL (the owner, 17 November 2026:
// requests "do not become bills until the first session in January when they
// are introduced and referred to committees"): the new term's first bills are
// in meta.json from Organization Day, numbered as their texts are signed off,
// and until then the rule stopped there; it now holds while the newest term
// is the requests' own and none of them has been introduced on a day of
// their own year (meta.requests.introduced_in_session, build_lsrs; the
// resolutions Organization Day adopts are the December before). Before the
// election the search opens on the current term as it always has. The day is
// Concord's (nhDay), as a deadline's is; the build's day is in what meta.json
// lists (its terms, the requests and how many stand). An address that names a
// term is read first.
function electionDayOf(y){
  const dow=new Date(Date.UTC(y,10,1)).getUTCDay();
  return `${y}-11-${String(2+(8-dow)%7).padStart(2,"0")}`;
}
// The term the search opens on with no address to say: what the address
// leaves out when the term is this one (addressList, sponsorHref).
function defaultTerm(m,now=new Date()){
  return requestsFirst(m,now)?m.requests.term:((m&&m.terms)||[])[0]||"";
}
function requestsFirst(m,now=new Date()){
  const R=m&&m.requests, terms=(m&&m.terms)||[];
  if(!R||!R.term||!terms.length||!((+R.n||0)-(+R.withdrawn||0)>0))return false;
  const ry=+(R.year||String(R.term).slice(0,4)),t0=+String(terms[0]).slice(0,4);
  if(ry<t0||(ry===t0&&(+R.introduced_in_session||0)>0))return false;
  return nhDay(now)>electionDayOf(ry-1);
}
// A term already in IDX is never fetched again. All terms is every one of
// them, which is what the picker's own "All Terms" fetches.
const LOADED=new Set();
// THE TERMS THE SITE PUBLISHES AN INDEX OF (6 November 2026): meta.json's,
// and the bill requests' (idx/<year>-requests.json). A record can name a term
// the site has not built yet -- a committee's meeting the General Court posts
// after Organization Day, before the new term's first night -- and its
// idx/2027-2028.json answered 404, unhandled, on the committee's page and
// every tab. With no terms in meta.json, every term is taken as published.
function published(t){
  const ts=(META&&META.terms)||[];
  return !ts.length||ts.includes(t)||!!(META&&META.requests&&t===META.requests.term);
}
// A TERM ASKED FOR ONCE AT A TIME (the second review of 7 November 2026).
// Nothing is in LOADED until its index has arrived, so a second ask while the
// first was on its way fetched it again, and both landed: the picker turned
// with a bill open, then Back at once, drew every bill of that term twice,
// for the rest of the page's life. An ask on its way is handed to whoever
// asks again; one that fails is forgotten, so the next ask tries again.
const ASKING=new Map();
// WHAT THE LIST WAITS FOR, said where it would be drawn (unfocus, render): a
// term picked with a bill open whose bills are not here yet, after Back.
// Drawn before they came, the list said "Not in the 2019-2020 term" or "0
// bills" of a term that has them (the third review of 7 November 2026).
let WAITING="";
function ensureTerm(t){
  if(t===ALL_TERMS)return Promise.all(((META&&META.terms)||[]).map(ensureTerm));
  if(!t||LOADED.has(t)||!published(t))return Promise.resolve();
  if(ASKING.has(t))return ASKING.get(t);
  const asked=need("idx/"+encodeURIComponent(t)+".json").then(rows=>{
    ASKING.delete(t);
    if(LOADED.has(t))return;
    LOADED.add(t);
    // TWO HAYSTACKS, NOT THREE (17 October 2026): the sponsor's name had one
    // of its own until a name stopped listing bills (A NAME IS NOT WHAT A
    // BILL IS ABOUT, above).
    rows.forEach(b=>{
      const norm=s=>String(s||"").toLowerCase().replace(/-/g," ");
      b.hayT=norm([b.id,b.n,b.title].join(" "));
      b.hayC=norm((b.committees||[b.committee||""]).join(" | "));
    });
    noteSponsors(t,rows);
    IDX=IDX.concat(rows);
  },e=>{ASKING.delete(t);throw e;});
  ASKING.set(t,asked);
  return asked;
}

// WHAT THIS PAGE IS, decided before anything is asked for (the phone audit
// of 25 October 2026). About 3,800 pages carry their whole record in the
// HTML and are built with GR_STATIC -- the towns, the laws, the guides, the
// Calendar, the session days, the directories -- and each downloaded the
// bill index it never reads, 2 MB, with the bill search's controls standing
// on screen until it came ("Loading…", and on a phone "Filter by topic…")
// and then taken down, so the page jumped. Now they ask for nothing, and the
// controls go the moment this script runs (and shell.page writes them shut
// for the moment before it does). A bill's, a member's and a committee's own
// page still needs the index, and takes the list's controls down before
// asking for it too. Every page built from this template that is not a list
// of bills loses the search row; a bill's own page keeps the box --
// GR_STANDALONE is on bill pages too, and there the next bill is a
// plausible next thought rather than a change of subject.
if(window.GR_STATIC||window.GR_STANDALONE){
  if(!window.GR_BILL&&!window.GR_REQUEST)hideBillSearch();
  staticChromeDown();
  // A REQUEST'S OWN PAGE KEEPS THE BOX AS A BILL'S DOES (11 November 2026),
  // and it works the same way: submitSearch takes the words to /bills.
  if(window.GR_REQUEST){const q=$("#q"),go=$("#qgo");if(q)q.disabled=false;if(go)go.disabled=false;}
}
// A law's page can be followed by email (build_rsa's GR_LAW), and only by
// email: the box is drawn only where the sign-up answers, so the live site
// shows no Follow with nothing in it before email goes live.
if(window.GR_STATIC){
  if(window.GR_LAW)followUp()
    .then(ok=>{if(ok)mountFollow("law","",String(window.GR_LAW));}).catch(()=>{});
  // A BILL REQUEST'S OWN PAGE (build_request_pages, 11 November 2026) is
  // followed as its card in the list is (lsrCardHtml): by email alone, the
  // key "lsr:2027-0012", drawn only where the sign-up answers, in the head's
  // action column after Cite. The page names it only for a request that can
  // be followed -- not a withdrawn one -- as GR_FOLLOW, "lsr:2027-0012".
  if(window.GR_FOLLOW)followUp()
    .then(ok=>{if(ok){const k=String(window.GR_FOLLOW),i=k.indexOf(":");
      mountFollow(k.slice(0,i),"",k.slice(i+1));}}).catch(()=>{});
  // REPORT A PROBLEM ON A SESSION DAY AND A STUDY COMMITTEE (the cohesion
  // audit of 30 October 2026, I-8): the page names its record (GR_REPORT,
  // "session:H/2010-03-11", "study:ss1451") and the box goes after the Share
  // the page wrote, as on a bill's. report.js accepts each only from its own
  // address. AFTER THIS SCRIPT HAS RUN: this block runs as the file loads,
  // and reportBox reads REPORT_TO and REPORT_FIELDS, declared further down
  // (a ReferenceError here, found by the screenshots of 30 October 2026).
  if(window.GR_REPORT){
    // A TOWN'S PAGE ("town:concord-ward-4", the owner, 10 November 2026) has
    // the Report box alone: it writes no Share, and none was asked for.
    const rec=String(window.GR_REPORT),at=rec.indexOf(":");
    if(at>0)setTimeout(()=>mountReport(rec.slice(0,at),rec.slice(at+1),
      rec.slice(0,at)!=="town"&&!document.querySelector("#pageacts [data-share]")),0);
  }
}else need("meta.json")
 .then(m=>{
   META=m;
   const first=wantedTerm(m);
   return ensureTerm(first).then(()=>[IDX,m]);})
 .then(([i,m])=>{
   IDX=i;META=m;
   setRequestYear(META.requests?reqYear():"");
   // TAGS:BEGIN
   setTagWords(META.tags,META.tag_words);
   // TAGS:END
   // The haystack is built in ensureTerm, once per term as it arrives.
   const terms=META.terms&&META.terms.length?META.terms
     :[...new Set(IDX.map(b=>b.term).filter(Boolean))].sort().reverse();
   term=wantedTerm(META)||terms[0];
   const ys=$("#year");
   // ALL TERMS, above the current one: the person asked on 14 September for
   // the picker to open on the current term with a way to search every term.
   // BETWEEN ALL TERMS AND THE CURRENT ONE, which is where the person asked
   // for it on 18 September: the 2027 bill requests are not a term the
   // General Court has sat for, so they are not in META.terms and nothing
   // that walks the terms -- the directory, the sitemap, the archive pages --
   // sees them. The picker is the one place they belong, and the current term
   // stays the default "until the bills for next term are fully available".
   // "All Terms", in the Title Case of the terms below it (the person, 8
   // October 2026); a sentence that says "across all terms" stays a sentence.
   // data-short: the words a phone shows (fitPickers).
   ys.innerHTML=`<option value="${ALL_TERMS}">All Terms</option>`
     +(META.requests?`<option value="${esc(META.requests.term)}"${reqYear()
       ?` data-short="${esc(reqYear())} Requests"`:""}>${
       esc(META.requests.label)}</option>`:"")
     +terms.map(t=>`<option value="${t}" data-short="${termDash(t)}">${termDash(t)} Term</option>`).join("");
   fitPickers();
   ys.value=term;
   ys.addEventListener("change",e=>{
     // On a record page there is no list to re-filter, and render() would
     // write one over the record.
     if(PAGE||window.GR_STATIC){location.href=BASE+"bills";return;}
     // ON /bills WITH A BILL OPEN, THE PICKER CHOOSES THE TERM THE LIST WILL
     // BE IN ONCE THE BILL IS CLOSED, AND NOTHING ELSE. (A bill's own page
     // has no picker: staticChromeDown hides it.) Re-rendering here swapped
     // the record under the reader: an open bill is found by its number
     // alone, so changing the term redrew it as the bill with the SAME
     // NUMBER in the new term -- a different bill, about a different subject,
     // at an address still naming the old one. A bill number is only unique
     // within a biennium, which is the whole reason every address on this
     // site carries the year.
     // AND THE OPEN BILL KEEPS ITS OWN TERM UNTIL IT IS CLOSED (the review of
     // 25 October 2026). The term was taken at once, so the next redraw --
     // a tab pressed -- did the swapping instead: 2023-2024's HB 104, the
     // picker turned to 2025-2026, became 2025-2026's HB 104 under the old
     // bill's row, its Cite still /bill/2023/hb104 and a live Testify for the
     // other bill in it. The choice is held (heldTerm) and taken when the
     // bill is closed (unfocus), which a search or an offer taken from the
     // open bill does first; the offers under the box are the held term's
     // meanwhile (billOffers). Its bills are fetched now, so the list is
     // there to draw when the bill is closed.
     if(focused){
       heldTerm=e.target.value;heldPicked=true;
       (heldTerm===ALL_TERMS?terms:[heldTerm]).forEach(ensureTerm);
       return;}
     term=e.target.value;
     forgetCardState();
     // The term's bills may not be here yet. Fetch, then draw -- and say so
     // meanwhile, because a picker that does nothing for a moment reads as
     // broken.
     const want=term===ALL_TERMS?terms:[term];
     const c=$("#count"); if(c&&want.some(x=>!LOADED.has(x)))
       c.textContent=term===ALL_TERMS?"loading every term…":"loading "+term+"…";
     Promise.all(want.map(ensureTerm)).then(render);});
   const so=$("#sort");
   if(so)so.addEventListener("change",e=>{
     if(PAGE||window.GR_STATIC)return;
     // An order chosen with a bill open is the reader's for the list behind
     // it, as the term picker's is (heldSort; the third review of 7 November
     // 2026): Back read the list's address and dropped it.
     if(focused)heldSort=e.target.value;
     sortChosen=true;sortBy=e.target.value;render();});
   $("#q").disabled=false;
   // 63 CHARACTERS IN A 342px BOX. The placeholder overflowed by 212px at
   // 420px wide, so a phone read "Bill number, key phrase, or several nu" --
   // the clause about commas, which is the only place that feature is
   // explained, was the part that fell off the end. Two strings, and the
   // narrow one says what to type rather than everything you may type.
   // THE PERSON'S WORDS SINCE 9 OCTOBER 2026, both of them shorter: "Bill
   // number or key words" in bills.html, and this for the phone's cards.
   // The commas are explained on Using this site.
   if(!window.GR_BILL&&matchMedia("(max-width:45em)").matches)
     $("#q").placeholder="Bill number or a few words";
   // The button next to it does the same job on the focused view, so it waits
   // for the same data.
   $("#qgo").disabled=false;
   // Arriving from the home page search box, with the query in the URL.
   const params=new URLSearchParams(location.search);
   // ...or loaded at a list's own entry that holds words its address does
   // not name (entryWords): a bill reloaded, then Back, loads that entry, and
   // the words typed and not run came back as an empty box (the third review
   // of 7 November 2026). A shared link has no entry, and is its address.
   const held=history.state&&typeof history.state.words==="string"&&!window.GR_STANDALONE
     &&/^\/bills(?:\.html)?\/?$/.test(location.pathname)?history.state.words:null;
   const pre=params.get("q")!==null?params.get("q"):held;
   if(pre){ $("#q").value=pre; query=pre; }
   // ...or from the header search, having clicked a subject. Asked for on 18
   // September: "when you click the topic it brings you to bill search and
   // shows all bills from the current term which match the topic." The term
   // needs no saying -- the current one is what this page opens on -- so the
   // subject is ticked in the Topic facet and the list narrows to it, with
   // the tick showing so a reader can see what narrowed it and untick it.
   // A subject that is not one of the 43 is ignored rather than left
   // selected: a facet nothing matches shows an empty list and no reason.
   filtersFromAddress(params);
   // A RECORD'S OWN PAGE IS NOT THE LIST, decided before anything is drawn.
   // This used to sit after render(), which meant a member's page built the
   // whole 2,234-bill list into #results and then threw it away -- 300KB of
   // DOM nobody saw. The list's controls are already down (WHAT THIS PAGE
   // IS, above): the count read "2,234 of 2,234 bills in the 2025-2026 term"
   // above a single bill, which at 360px was the whole first screen. Focus
   // is not taken either: a reader who opened a member's page did not ask
   // to be put in the search box.
   // A record's own page gets the report box. Only its own page: the record
   // and the address must agree for the report to be accepted, and a card
   // expanded in the search list is not at its own address.
   if(window.GR_BILL)mountReport("bill",String(window.GR_BILL));
   if(window.GR_MEMBER)mountReport("member",String(window.GR_MEMBER));
   if(window.GR_COMMITTEE)mountReport("committee",String(window.GR_COMMITTEE));
   mountFollow(window.GR_BILL?"bill":window.GR_MEMBER?"member":window.GR_COMMITTEE?"committee":"","",
     String(window.GR_BILL||window.GR_MEMBER||window.GR_COMMITTEE||""));
   if(window.GR_MEMBER){openPage("member",String(window.GR_MEMBER));return;}
   if(window.GR_COMMITTEE){openPage("committee",String(window.GR_COMMITTEE));return;}
   // THE BILL SEARCH STARTS IN ITS BOX; A BILL'S OWN PAGE STARTS AT THE TOP.
   // The box took focus on both, so on /bill/2025/hb2 the first Tab press
   // went to the box's button: "Skip to this bill" and the nav were behind
   // the starting point, reached only with Shift+Tab, and a screen reader
   // began in an edit field instead of at the page (the audit of 2 October
   // 2026, S7). On the search page the box is the page.
   if(!window.GR_BILL)$("#q").focus();
   render();
   restorePlace();
   // A bare #HB1442 link from elsewhere opens that bill.
   // Arriving with a bill in the address -- a refresh, a shared link, or the
   // "open it in the searchable view" link on a static page -- opens it the
   // way clicking the arrow would have, rather than merely expanding the card
   // somewhere down a list of two thousand.
   // "#2026/HB1442", and still the bare "#HB1442" that links already in
   // circulation use. The year is what tells two terms' HB1442 apart;
   // without it the first match in the index wins, which is only safe
   // while one term is loaded.
   // A bill's own page at /bill/2026/hb1094 is this same app with one bill
   // open, rather than a second renderer drawing the same JSON in Python. It
   // says which bill in GR_BILL, because it cannot say it in the hash without
   // putting the bill number twice in an address that already names it.
   // A legislator's or a committee's page is this same app with one record
   // open, so it takes over here rather than drawing the bill list first and
   // replacing it. The index is still loaded: a vote names a bill and not its
   // year, and yearOf needs the index to turn one into a link.
   // A bill's own page whose fragment names a place in it, not a bill --
   // /bill/2026/hb1560/text#amendment-2026-0422h (AMENDMENT_HASH, below) --
   // is still that bill's page (26 October 2026).
   const said=decodeURIComponent(location.hash.slice(1));
   const h=said&&!(window.GR_BILL&&(AMENDMENT_HASH.test(said)||VOTE_HASH.test(said)))?said:(window.GR_BILL||"");
   const hm=/^(?:(\d{4})\/)?([A-Z]{2,5}\d+)$/i.exec(h);
   if(hm){
     const id=hm[2].toUpperCase(),hy=hm[1]||"";
     const row=IDX.find(b=>b.id===id&&(!hy||String(b.year)===hy));
     if(row){
       focused=id;
       // A link into another term must switch the term first, or the
       // card it names is filtered out of the list it would be drawn in.
       if(row.term&&term&&row.term!==term){term=row.term;$("#year").value=term;}
     }
     // The tab this bill's own address names.
     if(window.GR_BILL){
       const t=BILL_TABS[tabFromPath()];
       if(t){openTab[id]=t;
         if(t==="6"&&row){amendmentAsked(row,said);needVersions(row);}
         TAB_JUMP=id;}
     // A link to one vote opens the Votes tab, and its card is brought up.
     if(window.GR_BILL&&VOTE_HASH.test(said)){openTab[id]="1";VOTE_JUMP=said;}
     }
     openBill(id);
   }
 }).catch(e=>{
   /* THE ERROR WENT WHERE THE RECORD WAS. One 404 or one dropped connection
      on idx/2025-2026.json put "Could not load the data ... run
      build_site_v2.py" -- instructions for a developer, about a file the
      reader never asked for -- where the record had been. A page built with
      GR_STATIC never asks for it now (WHAT THIS PAGE IS, above), and a
      bill's, a member's or a committee's page, whose record is in its HTML
      too (shell.page's static), shows that record with one plain line
      (plainRecord, the phone audit of 25 October 2026). The bill search,
      which has no record without the index, says so in one plain line with
      the way round it, the Directory; what failed goes to the console, where
      a developer looks (the same audit's follow-up). */
   if(window.GR_STANDALONE)return plainRecord();
   if(typeof console!=="undefined")console.error("bill search: could not load its index", e);
   $("#results").innerHTML=`<div class="empty"><p>The bill search did not load. Reload the
     page to try again, or find a bill in the <a href="/directory">Directory</a>.</p></div>`;
 });

/* HB 0115 IS HOW THE GENERAL COURT WRITES IT. Its own archive addresses a
   bill as HB0115 -- gc.nh.gov/legislation/2017/HB0115.html -- and its PDFs
   and calendars pad the same way, so a padded number is what a reader copying
   from the source has in their clipboard. The header's Search box already
   read it (find.js takes the zeros off before handing the number over); this
   box did not, and "HB 0115" returned nothing while "HB 115" returned the
   bill. The id in the index is unpadded: HB115, across all 33,683 of them,
   not one of which carries a leading zero. The lookahead keeps a digit, so
   even a nonsense "HB000" comes out as a number rather than as "HB". */
