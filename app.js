// GRANITE_VERSION: 2026-09-07.122
// What each kind of document actually is, said once rather than in every row.
const DOCWHAT={text:"the bill as it currently stands",
  status:"the page this site takes a bill's status from",
  docket:"every recorded action, in the General Court's own words",
  record:"the official record of one action",
  report:"the calendar a committee report was printed in"};
// WHAT THE SHORTHAND STANDS FOR. A citation is printed the way the General
// Court prints it -- "HJ 1, page 32" is what a reader would quote -- but HJ
// and SC are insider shorthand, and this site exists to make the record
// findable. The Learn section explains the same four at
// civics.py's "Reading the shorthand" table; this is the one place a reader
// meets them without having gone looking.
const CITE_OF={HJ:"House Journal",SJ:"Senate Journal",
  HC:"House Calendar",SC:"Senate Calendar"};
const citeSource=lab=>CITE_OF[(String(lab).match(/^([A-Z]{2})\b/)||[])[1]]||"";

const PARTY_NAME={R:"Republican",D:"Democrat",I:"Independent",L:"Libertarian",
  X:"Party not on file"};
const PARTY_COLOR={R:"var(--rep)",D:"var(--dem)",I:"var(--ind)",L:"var(--ind)",
  X:"var(--ink-2)"};
// Where a party sits in a vote's legend and full record: Republicans, then
// Democrats, then anyone else by letter, and within a party yes before no.
// The split inside a caucus is what those two rows are compared for, so they
// have to be adjacent; ordered by size, the Republican no drifted to fourth
// with both Democrat rows between it and the Republican yes.
const PARTY_RANK={R:0,D:1};
const partyRank=p=>(p in PARTY_RANK)?PARTY_RANK[p]:2;
const byParty=(a,b)=>partyRank(a)-partyRank(b)||String(a).localeCompare(String(b));
const yeaFirst=(a,b)=>a===b?0:(a==="Yea"?-1:1);
const KIND={active:"s-active",law:"s-law",done:"s-done",veto:"s-veto",
            study:"s-study",adopted:"s-adopted"};
// "Became law" is wrong for a resolution: an adopted House Resolution is
// finished and successful and is not law. It needed its own word.
const KINDL={active:"In progress",law:"Became law",done:"Killed",
             veto:"Vetoed",study:"Interim study",adopted:"Adopted"};
// WHAT THE BALLOT CODE SAYS, AND NOTHING IT DOES NOT. Each line is attributed
// to the record ("Recorded as ...") because the roll call carries the code and
// no reason. On 42% of the House member-days with an Excused ballot,
// 1999-2026, the member voted on another question that day, and a declared
// conflict of interest is coded Excused too; on 81% of those with a Not
// Excused ballot the member voted that day; and 12 roll calls record two
// members presiding. The old lines claimed a whole day arranged beforehand
// with a reason, a single presiding member who votes only on a tie, and a
// member who walked out to avoid the vote. The labels are the person's to
// change.
// These strings are inserted into the page unescaped: no <, & or ".
const OTHER=[["Presiding","Presiding",
  "Recorded as presiding: in the chair, running the chamber for this vote, so no yes or no is recorded for them. The Speaker, the Senate President or a member filling in for them presides. It is not a missed vote."],
 ["Not Voting/Excused","Excused absence",
  "Recorded as excused from this vote. An excuse can cover a whole day, part of a day or a single vote, so a member excused here may have cast other votes the same day."],
 ["Not Voting/Not Excused","Absent, not excused",
  "Recorded as not voting and not excused. The roll call does not say why, or whether the member was in the chamber."]];

const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/* THE BILL MATCHER IS SHARED WITH THE HEADER SEARCH. Every line between a
   "BILLMATCH:BEGIN" and the "BILLMATCH:END" after it is copied by
   build_pages.py into site/billmatch.js, which find.js loads on the pages
   that do not run this file -- so the header's "All 30 bills that mention
   firearms" is counted by the same code that lists /bills?q=firearms, not by
   a second matcher that drifts from this one. What is inside the markers must
   therefore stand alone: no DOM, no page state, and nothing it names that is
   declared outside a marked region. preflight runs the copy on its own and
   fails if it does not. */
// BILLMATCH:BEGIN
/* Bills are drafted in statutory vocabulary; people search in ordinary words.
   "AN ACT relative to the state minimum hourly rate" will never be found by
   someone typing "minimum wage". These are GROUPS rather than mappings: every
   term in a group matches every other, so nothing is declared the real name for
   anything else. That matters on contested subjects, where deciding that one
   word "means" another is a framing choice rather than a translation. Matching
   is by substring, so a singular form also catches its plural. */
const SYN=[
  ["gun","firearm","weapon","pistol","rifle"],
  ["school","education","student","teacher","classroom"],
  // Not "revenue": the Department of Revenue Administration is named in bills
  // that levy nothing.
  ["tax","taxation","levy"],
  // Three groups where there was one: "zoning" returned every landlord-tenant
  // bill of the term, 166 of them, because all six words shared a group.
  ["housing","dwelling"],
  // Not "lease" (the state leases buildings) nor "subdivision" (every
  // "political subdivision"): measured, both pulled in bills about neither.
  ["landlord","tenant","eviction","rental housing"],
  ["zoning","land use","planning board"],
  ["childcare","daycare"],
  ["marijuana","cannabis","thc"],
  ["dui","dwi","intoxicated","impaired driving"],
  // Not "insurance": a search for health returned every auto and home policy bill.
  ["healthcare","health care","health","medical"],
  ["police","law enforcement","police officer","peace officer","sheriff"],
  ["veteran","military","national guard","armed forces"],
  ["elderly","senior","older adult","aging"],
  ["vote","voting","election","ballot","absentee","voter"],
  // Broadband is internet ACCESS: with "internet" and "telecommunication" in
  // the group it returned obscenity filters and wiretaps.
  ["broadband","internet service","high speed internet"],
  ["road","highway","transportation","bridge"],
  ["climate","emission","greenhouse","renewable","solar"],
  ["trash","landfill","solid waste","recycling"],
  // Two groups: "opioids" found the prescription drug affordability board.
  ["opioid","fentanyl","narcotic","heroin","overdose","naloxone","substance use",
   "substance misuse","addiction"],
  ["drug","controlled substance"],
  ["vaccine","vaccination","immunization"],
  ["betting","wagering","gambling","casino"],
  ["abortion","reproductive","pregnancy termination"],
  ["transgender","gender identity","gender-affirming"],
  ["immigration","immigrant","noncitizen","alien"],
  ["minimum wage","hourly rate","wage"],
  ["union","collective bargaining"],
  // Two groups: "pfas" found every bill naming water, docks and dams included.
  ["water","groundwater","drinking water"],
  ["pfas","perfluoroalkyl","polyfluoroalkyl","forever chemical"],
  ["prison","correctional","department of corrections","inmate","incarcerated","incarceration"],
  ["court","judicial","judge","judiciary"],
  ["property tax","assessment","abatement"],
  ["energy","electric","ratepayer"],
  ["mental health","behavioral health","psychiatric"],
  ["disability","disabled","accessible","accessibility"],
  ["farm","agriculture","livestock","dairy"],
];
const SYNMAP={};
SYN.forEach(g=>g.forEach(t=>{SYNMAP[t]=g;}));
// Match at a word boundary, not anywhere in the string. Plain substring search
// makes "gun" hit "begun" and "act" hit "enacted". Matching at the START of a
// word still catches plurals and endings, so "firearm" finds "firearms" and
// "incarcerat" finds "incarcerated".
const RXC={};
function hasTerm(hay, term){
  if(term.includes(" ")) return hay.includes(term);
  let rx=RXC[term];
  if(!rx){ rx=new RegExp("\\b"+term.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
           RXC[term]=rx; }
  return rx.test(hay);
}

function expand(word){
  // The original word is ALWAYS kept. Dropping it silently narrows the search:
  // "care" is a prefix of "child care", so without this a search for "care"
  // would match childcare bills and stop matching "health care" — worse than
  // having no synonyms at all.
  //
  // Partial matches need at least four characters, so "gun" does not fire on
  // "begun" and short words do not drag in whole groups.
  // The word's own entry first. "wage" is in the minimum wage group; taking
  // the longest entry it begins put it in the gambling group, by "wagering",
  // and "minimum wage" returned the minimum age for sports betting.
  if(SYNMAP[word])return [...new Set([word, ...SYNMAP[word]])];
  let best=null;
  for(const t in SYNMAP){
    // Prefix match, not "contains anywhere". "guns" should reach the firearm
    // group; "begun" should not, and it does under a contains test. Only
    // one-word entries: "minimum" is not a way of saying "minimum wage", and
    // reading it as one made every bill saying "wage" twice a match.
    if(t.includes(" "))continue;
    // A longer entry the word begins only for a word of six letters or more:
    // "rates" begins "ratepayer", and "electric rates" found 77 energy bills.
    const hit = word.length>=4 && (word.startsWith(t)||(word.length>=6&&t.startsWith(word)));
    if(hit && (!best||t.length>best.length)) best=t;
  }
  return best ? [...new Set([word, ...SYNMAP[best]])] : [word];
}

/* THE WORDS A QUESTION IS ASKED IN. Measured on 14 September against 36
   everyday searches: every word had to match, so "bills about guns" and "bail
   reform" found nothing, and "public education funding" found 11 bills where
   "education funding" found 95. A plural ("rentals") did not find its singular
   and a hyphen ("short-term") did not find its two words. So: words that carry
   no subject are skipped, unless they are all a search has; a plural is read
   as its singular; hyphens are spaces on both sides. */
const STOP=[
  "a","an","the","of","and","or","for","to","in","on","at","by","about","with",
  "from","regarding","relative","related","relating","concerning","bill","bills",
  "law","laws","act","acts","legislation","nh","hampshire","reform","reforms",
  "committee","committees"
];
const STOPSET=new Set(STOP);
/* A PHRASE IS ONE IDEA, and the words people ask in are not the words a bill
   is titled in: nobody files "public education funding", they file "the cost
   of an adequate education". Groups, like SYN -- any phrase of a concept in a
   search stands for all of its terms -- and the terms are the record's own
   wording, read out of the titles, not a judgment about what a bill is for.
   The longest phrase is taken first, and what it covers is not read again. */
const CONCEPTS=[
  {phrases:["public education funding","public school funding","education funding",
    "school funding","funding for public schools","funding for schools","education aid",
    "school aid","adequate education","education adequacy"],
   terms:["education funding","school funding","adequate education","adequacy",
    "education trust fund","education grant","school building aid","opportunity budget"]},
  {phrases:["school choice","education freedom account","education freedom accounts",
    "education savings account","education savings accounts","school voucher",
    "school vouchers"],
   // Not "voucher" alone: housing vouchers are vouchers too, and a landlord
   // bill came up for "school choice".
   terms:["education freedom account","school choice","education savings account",
    "school voucher","scholarship organization","open enrollment"]},
  // Phrases, because as two words each found bills about something else:
  // "climate" and "change" a portfolio standard's changes, "teacher" and "pay"
  // payments to schools, "sex" and "education" biological sex in athletics.
  {phrases:["climate change","global warming"],
   terms:["climate change","global warming","greenhouse gas","carbon emission"]},
  {phrases:["teacher pay","teacher salary","teacher salaries","teacher wages",
    "teacher compensation","educator pay"],
   terms:["teacher pay","teacher salary","teacher salaries","teacher compensation",
    "educator salary","educator salaries","minimum teacher salary","salaries of teachers"]},
  {phrases:["sex education","sex ed","sexual education","sexuality education",
    "sexual health education"],
   terms:["sex education","sexual education","sexuality education","human sexuality",
    "sexual health education"]},
  {phrases:["right to work","right-to-work"],
   terms:["right to work","union membership","labor organization"]},
  {phrases:["term limits","term limit"],
   terms:["term limit","term limits","consecutive terms"]},
  // A phrase, because as two words "child" and "care" found foster care.
  {phrases:["child care","childcare","day care","daycare"],
   terms:["child care","childcare","day care","daycare"]},
  {phrases:["paid family leave","paid family and medical leave","family leave","paid leave"],
   terms:["family and medical leave","paid family","family leave","paid leave"]},
  {phrases:["short term rental","short term rentals","vacation rental","vacation rentals","airbnb"],
   terms:["short term rental","vacation rental"]},
  {phrases:["bail reform","bail","pretrial release"],
   terms:["bail","pretrial"]},
  {phrases:["affordable housing","workforce housing","housing affordability"],
   terms:["affordable housing","workforce housing","housing affordability","housing champion"]},
  {phrases:["right to know","public records","open records","freedom of information","foia"],
   terms:["right to know","91 a","public records","governmental records"]},
  {phrases:["death penalty","capital punishment"],
   terms:["death penalty","capital punishment","capital murder"]},
  {phrases:["voter id","voter identification","photo id"],
   terms:["voter identification","photo identification","government issued identification",
    "voter id","proof of identity","voter identity","identification of voter"]},
  // Sports only: with gambling in it, "sports betting" returned 26 bills about
  // horse racing and video lottery. "gambling" alone still finds those (SYN).
  {phrases:["sports betting","sports wagering","sports gambling","sportsbook"],
   terms:["sports betting","sports wagering","sports book","sportsbook"]}
];
const CPHRASES=CONCEPTS.flatMap(c=>c.phrases.map(p=>[p,c]))
  .sort((a,b)=>b[0].length-a[0].length);
function stem(w){
  if(w.length<5||/(ss|us|is)$/.test(w))return w;
  if(/ies$/.test(w))return w.slice(0,-3)+"y";
  if(/(xes|ches|shes|sses)$/.test(w))return w.slice(0,-2);
  return w.endsWith("s")?w.slice(0,-1):w;
}
/* THE MARKS A QUESTION IS ASKED WITH, taken off the ENDS of words and nowhere
   else. Only the comma and the hyphen were being removed, so a reader who
   typed the way people type -- "right to know?" -- got 0 bills where "right
   to know" gets 14, and "school funding." got 0 against 33. The question mark
   rode along on the last word: the phrase test looks for " right to know "
   and saw " right to know? ", and the word test then asked the titles for
   /\bknow\?/, which no bill title contains.
   The ends only, because the middle carries meaning here. "91-a:4" is an RSA
   citation and its colon is part of the number -- titles are searched with
   the hyphen already read as a space, so the query must keep the rest of the
   citation intact. "children's" keeps its apostrophe for the same reason: it
   is inside a word, not around one. And this strips a named list of marks
   rather than "anything that is not a-z0-9", which would have eaten the
   final letter of an accented word. */
const EDGEMARK=/^[.?!;:'"“”‘’()\[\]{}…]+|[.?!;:'"“”‘’()\[\]{}…]+$/g;
// The search as groups, every one required: a concept's phrase is one group of
// its terms, each other word a group of its synonyms.
function queryGroups(raw){
  let q=" "+String(raw||"").toLowerCase().replace(/[,\-]/g," ")
    .split(/\s+/).map(w=>w.replace(EDGEMARK,"")).filter(Boolean).join(" ")+" ";
  const out=[];
  for(const [p,c] of CPHRASES){
    if(q.includes(" "+p+" ")){
      out.push({word:p,alts:[...new Set([p,...c.terms])]});
      q=q.split(" "+p+" ").join(" ");
    }
  }
  const words=q.split(" ").filter(Boolean);
  const kept=words.filter(w=>!STOPSET.has(w));
  (kept.length||out.length?kept:words).forEach(w=>{
    const s=stem(w);
    out.push({word:w,alts:[...new Set([w,...expand(s)])]});
  });
  return out;
}
let QG_KEY=null,QG=[];
function groupsFor(q){ if(q!==QG_KEY){QG_KEY=q;QG=queryGroups(q);} return QG; }

/* WHERE A WORD MATCHES, AND HOW. Read against the bills 36 searches returned
   (14 September), the irrelevant ones came from four places:
   - the TOPIC label, a broad bucket: "mental health" returned 80 bills --
     ambulance services, the prescription drug board -- whose only link was a
     topic reading "...Mental Health". Text matching leaves it out; the Topic
     filter is still there for anyone who wants the bucket.
   - a SPONSOR's name read as the start of a word: "bail" found every bill of a
     member named Bailey. A name matches as a whole word.
   - a SYNONYM read as the start of a word: "alien" found "parental alienation".
     The reader's own word still matches as a start ("educat" finds education),
     but a word this file supplies matches as itself, or with an ending.
   - no order: the 33 bills titled about school funding sat among 74 that only
     share the Education Funding committee. Best match puts the title first. */
const RXW={};
function altRx(term){
  return RXW[term]||(RXW[term]=new RegExp("\\b"
    +term.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"(?:s|es|ed|d|ing|ings|er|ers|al)?\\b"));
}
// The reader's own word, or its singular: matched as the start of a word.
const typedAlt=(g,alt)=>!alt.includes(" ")&&(alt===g.word||alt===stem(g.word));
function inText(hay,g,alt){ return typedAlt(g,alt)?hasTerm(hay,alt):altRx(alt).test(hay); }
// 3 in the title, 2 in the sponsor's name, 1 in a committee's name, 0 not at all.
// A sponsor's name or a committee's matches only what the reader typed: a
// synonym found in a committee's name ("energy", for "electric vehicles") put a
// bill about hunting from a vehicle in the results.
function groupWeight(b,g){
  let w=0;
  for(const alt of g.alts){
    if(inText(b.hayT,g,alt))return 3;
    if(!(typedAlt(g,alt)||alt===g.word))continue;
    if(w<2&&altRx(alt).test(b.hayS))w=2;
    if(w<1&&inText(b.hayC,g,alt))w=1;
  }
  return w;
}
/* THE WORD ITSELF BEFORE A LONGER WORD IT BEGINS (the person, 25 September:
   "have direct word matches be at the top of the best match sorting"). The
   reader's own word matches as the start of a word, so "bail" finds bills
   about bailiffs, "gun" the Gunstock Area Commission and "tax" "taxpayer
   funded investigations" -- and they stay found, lower down. A part of the
   search is met directly where it is a word of the bill's title -- the word
   itself, with one of altRx's endings ("guns", "taxes"), or one of its
   synonyms -- or exactly a word of its sponsor's name, since a name is not a
   word with an ending: "fish" is not Rep. Fisher, nor "mun" Rep. Muns. Each
   part a bill does not meet that way adds how far short it falls: 1 where
   the title has only a longer word the part begins, or the sponsor's name
   only the word with an ending; 2 where only a committee's name has it; 3
   where a committee's name has only a longer word. Best match orders by the
   total before anything else, so a bill whose title or sponsor has every
   word of the search is never listed below one that has only the start of
   one.
   A committee's name counts for less than a longer word in the title: that
   is "Best match puts the title first", above, kept. Counted as direct, the
   committee put the 187 bills of 2025-2026 whose only link to "municipal"
   is a committee named for municipal affairs above the 26 whose titles say
   "municipalities". */
const RXN={};
function nameRx(term){
  return RXN[term]||(RXN[term]=new RegExp("\\b"
    +term.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"\\b"));
}
function looseness(b,gs){
  let n=0;
  for(const g of gs){
    let d=3;
    for(const alt of g.alts){
      const own=typedAlt(g,alt)||alt===g.word;
      if(altRx(alt).test(b.hayT)||(own&&nameRx(alt).test(b.hayS))){d=0;break;}
      if(d>1&&(inText(b.hayT,g,alt)||(own&&altRx(alt).test(b.hayS))))d=1;
      if(d>2&&own&&altRx(alt).test(b.hayC))d=2;
    }
    n+=d;
  }
  return n;
}
// BILLMATCH:END
// NOTHING FOUND is still an answer with somewhere to go. A search of several
// parts that no bill has all of says which parts do find bills on their own,
// with how many, as searches to run -- rather than a blank page for a reader
// who does not know a bill number and has no other way in.
function emptyResult(){
  const gs=query.trim()&&!billNumbers(query)?groupsFor(query.trim()):[];
  const inTerm=IDX.filter(inTermOf);
  // The parts: each group of a search of several, or each word of a phrase
  // that was the whole search ("teacher pay" finds nothing this term).
  const words=gs.length>1?gs.map(g=>g.word)
    :gs.length===1&&gs[0].word.includes(" ")?gs[0].word.split(" ").filter(w=>!STOPSET.has(w)):[];
  const parts=words.map(w=>{const g2=queryGroups(w);
    return [w,inTerm.filter(b=>g2.every(g=>groupWeight(b,g)>0)).length];}).filter(p=>p[1]);
  // termPhrase() brings its own preposition ("in the 2025-2026 term",
  // "across all terms"), so the "in the" that used to sit here made the
  // sentence read "No bills match in the in the 2025-2026 term." -- or, with
  // the picker on All terms, "in the across all terms". The two callers at
  // the count line pass it bare and were always right; this one doubled it.
  return `<div class="empty">No bills match${words.length?" all of that":""}
    ${esc(termPhrase())}.${parts.length?`<br><br>On their own: ${parts.map(([w,n])=>
      `<button class="link" data-q="${esc(w)}">${esc(w)}</button> (${n.toLocaleString()})`)
      .join(" &middot; ")}`:""}<br><br>Try removing a filter, or a different term.</div>`;
}
function scoreOf(b){
  const gs=groupsFor(query.trim());
  let s=gs.reduce((t,g)=>t+groupWeight(b,g),0);
  // The search's own words, in order, in the title, is the strongest sign there is.
  const words=gs.map(g=>g.word).join(" ");
  if(gs.length>1&&b.hayT.includes(words))s+=2;
  return s;
}
const fdate=d=>{if(!d)return"";const[y,m,dd]=d.split("-");
  return new Date(y,m-1,dd).toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric"});};
const $=s=>document.querySelector(s);

let IDX=[],META={},term=null,query="",sortBy="num",sortChosen=false;
// "All terms" in the picker: every term's bills in one list. A bill number is
// unique only within a term, so in that list a card is not opened in place --
// two HB 1s would share one card's state -- and goes to its own page instead.
const ALL_TERMS="all";
const inTermOf=b=>term===ALL_TERMS||!term||!b.term||b.term===term;
// "in the 2027-requests term" is not English and not what that list is, so
// the picker's own label speaks for it: "among the 2027 bill requests". The
// word "bills" the count puts before this is wrong for them too, which is why
// the count asks noun() rather than hard-coding it.
const termPhrase=()=>term===ALL_TERMS?"across all terms"
  :(META.requests&&term===META.requests.term)?"for 2027"
  :`in the ${term} term`;
const termNoun=()=>(META.requests&&term===META.requests.term)
  ?"bill requests":"bills";
// A bill number is unique within a two-year term and not beyond it, so
// every address for one carries its filing year: the static page has done
// so from the start, and the detail file and this view do now.
// WITHIN THE SELECTED TERM. HB1 exists in every biennium, and finding the
// first row with that number across the whole index served the 2025 bill's
// history under the 2023 bill's heading -- the card said "filed 2023" and the
// body said "introduced on February 20, 2025".
const yearOf=id=>{const b=IDX.find(x=>x.id===id&&(!term||x.term===term))
                       ||IDX.find(x=>x.id===id);
  return b&&b.year?String(b.year):"";};
// The detail cache is keyed the same way, or switching terms hands back the
// bill of the same number that was looked at first.
const dkey=id=>`${yearOf(id)}/${id}`;

// House bills before Senate bills, then numerically. Bill numbers are strings
// like "HB 1442", so a plain string sort puts HB 1000 before HB 99 and mixes
// the chambers together.
// BILLMATCH:BEGIN -- the order bills sort in; see the note above SYN.
const KINDORDER={HB:0,HR:1,HCR:2,CACR:3,SB:4,SR:5,SCR:6,HJR:7,SJR:8};
function billKey(b){
  const m=/^([A-Z]+)\s*(\d+)/.exec(b.id.toUpperCase())||[];
  return [KINDORDER[m[1]] ?? 99, parseInt(m[2]||"0",10)];
}
// BILLMATCH:END
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
  if(k==="kind")return [b.kind];
  if(k==="committee")return b.committees||(b.committee?[b.committee]:[]);
  return [b[k]];
}

// NEWER TERM FIRST, which changes nothing in a list of one term and orders
// the list on All terms: by number, two bills of one number (HB 1 is in
// every term) run newest first; by best match, among bills that match
// equally well, the newer term's come first and then by number. Without it
// those came in whichever order the terms' indexes happened to arrive, and
// /search's list of every term's bills (find.js's findBills, which orders
// them this way) could not be the same list (24 September).
const newerTerm=(a,b)=>{const x=String(a.term||""),y=String(b.term||"");
  return x<y?1:x>y?-1:0;};
function sortRows(rows){
  const by={
    num:(a,b)=>{const x=billKey(a),y=billKey(b);
                return x[0]-y[0] || x[1]-y[1] || newerTerm(a,b);},
    recent:(a,b)=>(b.last_action||"").localeCompare(a.last_action||"")
                  || billKey(a)[1]-billKey(b)[1],
    // Bills still moving come first, because those are the ones a reader can
    // still do something about -- turn up, sign in, write to the committee.
    // After that the outcomes group together and run alphabetically inside
    // each group. That is a filing order, not a ranking: a bill dying is an
    // outcome, not a failure, and nothing here puts one outcome above another.
    status:(a,b)=>((a.kind==="active"?0:1)-(b.kind==="active"?0:1))
                  || (a.kind||"").localeCompare(b.kind||"")
                  || (a.status||"").localeCompare(b.status||"")
                  || billKey(a)[1]-billKey(b)[1],
  }[sortBy]||(()=>0);
  // BEST MATCH: every word of the search as a word of the title or the
  // sponsor's name before the start of a longer one (looseness), then the
  // most of the search in the title, then the sponsor, then the committee,
  // and bill number within each.
  if(sortBy==="best"){
    const gs=groupsFor(query.trim());
    const lo=new Map(rows.map(b=>[b,looseness(b,gs)]));
    const sc=new Map(rows.map(b=>[b,scoreOf(b)]));
    const num=(a,b)=>{const x=billKey(a),y=billKey(b);return x[0]-y[0]||x[1]-y[1];};
    return rows.slice().sort((a,b)=>lo.get(a)-lo.get(b)||sc.get(b)-sc.get(a)
      ||newerTerm(a,b)||num(a,b));
  }
  return rows.slice().sort(by);
}
const sel={committee:new Set(),topic:new Set(),sponsor:new Set(),kind:new Set(),
           voteday:new Set()};
// On a phone the filter column stacks ABOVE the results, and an open
// Committee group is 340 pixels of it -- so the first bill sat past a
// screen and a half of filters on a 375-wide screen. Someone arriving on
// a phone came for the bills; the filters are one tap away either way.
// 861px, which is where .shell actually becomes two columns. It was 721,
// so between those two widths the panel stacked ABOVE the results with its
// longest group open -- fourteen committees before the first bill.
const wideEnough=typeof matchMedia==="function"
  && matchMedia("(min-width:861px)").matches;
const openGroups=new Set(wideEnough?["committee"]:[]);
let sponsorFilter="";
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
// "hearings" comes BEFORE "videos" and both map to 2. slugOf takes the first
// key with a matching value, so a tab switched today writes /hearings, while a
// link somebody already saved or a search engine already indexed still opens
// on /videos. An address that has been published is a promise; renaming the
// label is not a reason to break it.
const BILL_TABS={text:"6",votes:"1",hearings:"2",videos:"2",
                 reports:"3",sponsors:"4",documents:"5"};
const MEMBER_TABS={cosponsored:1,votes:2};
const COMMITTEE_TABS={sessions:1};
const TAB_PATH=/^(\/(?:bill\/\d{4}\/[a-z]{2,5}\d+|legislator\/[^\/]+|committee\/[^\/]+))\/([a-z]+)\/?$/i;
const isTabSlug=s=>!!(BILL_TABS[s]||MEMBER_TABS[s]||COMMITTEE_TABS[s]);
function tabFromPath(){
  const m=TAB_PATH.exec(location.pathname);
  return m&&isTabSlug(m[2].toLowerCase())?m[2].toLowerCase():"";
}
function tabAddress(slug){
  const m=TAB_PATH.exec(location.pathname);
  const base=m&&isTabSlug(m[2].toLowerCase())?m[1]:location.pathname.replace(/\/$/,"");
  try{history.replaceState(history.state,"",base+(slug?"/"+slug:"")+location.search);}catch(_){}
  skipHere();
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
function skipHere(){
  const s=document.querySelector("a.skip");
  if(s)s.setAttribute("href",location.pathname+"#results");
}
const slugOf=(map,v)=>Object.keys(map).find(k=>map[k]===v)||"";
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
// they opened it.
let focused=null,focusY=0;
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
}
// WHICH TERM TO LOAD FIRST. A record page names it in its own address --
// /bill/2026/hb1442 -- so a 1995 bill loads the 1995 index and not the
// current one. Anything else starts at the newest, which is what the picker
// opens on.
function wantedTerm(m){
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
  }
  return terms[0]||"";
}
// A term already in IDX is never fetched again. All terms is every one of
// them, which is what the picker's own "All terms" fetches.
const LOADED=new Set();
function ensureTerm(t){
  if(t===ALL_TERMS)return Promise.all(((META&&META.terms)||[]).map(ensureTerm));
  if(!t||LOADED.has(t))return Promise.resolve();
  return need("idx/"+encodeURIComponent(t)+".json").then(rows=>{
    LOADED.add(t);
    rows.forEach(b=>{
      const norm=s=>String(s||"").toLowerCase().replace(/-/g," ");
      b.hayT=norm([b.id,b.n,b.title].join(" "));
      b.hayS=norm(b.sponsor);
      b.hayC=norm((b.committees||[b.committee||""]).join(" | "));
    });
    IDX=IDX.concat(rows);
  });
}

need("meta.json")
 .then(m=>{
   META=m;
   const first=wantedTerm(m);
   return ensureTerm(first).then(()=>[IDX,m]);})
 .then(([i,m])=>{
   IDX=i;META=m;
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
   ys.innerHTML=`<option value="${ALL_TERMS}">All terms</option>`
     +(META.requests?`<option value="${esc(META.requests.term)}">${
       esc(META.requests.label)}</option>`:"")
     +terms.map(t=>`<option value="${t}">${t} Term</option>`).join("");
   ys.value=term;
   ys.addEventListener("change",e=>{
     // On a record page there is no list to re-filter, and render() would
     // write one over the record.
     if(PAGE||window.GR_STATIC){location.href=BASE+"bills";return;}
     term=e.target.value;
     forgetCardState();
     // ON A BILL'S OWN PAGE THE PICKER CHOOSES THE TERM THE NEXT SEARCH RUNS
     // IN, AND NOTHING ELSE. Re-rendering here swapped the record under the
     // reader: a focused view is found by bill number alone, so changing the
     // term redrew the page as the bill with the SAME NUMBER in the new term
     // -- a different bill, about a different subject, at an address still
     // naming the old one. A bill number is only unique within a biennium,
     // which is the whole reason every address on this site carries the year.
     // The term is still taken, and its bills still fetched, so the search
     // that follows runs in it immediately.
     if(focused){
       const t=term===ALL_TERMS?terms:[term];
       t.forEach(ensureTerm);
       return;}
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
     sortChosen=true;sortBy=e.target.value;render();});
   $("#q").disabled=false;
   // 63 CHARACTERS IN A 342px BOX. The placeholder overflowed by 212px at
   // 420px wide, so a phone read "Bill number, key phrase, or several nu" --
   // the clause about commas, which is the only place that feature is
   // explained, was the part that fell off the end. Two strings, and the
   // narrow one says what to type rather than everything you may type.
   if(matchMedia("(max-width:720px)").matches)
     $("#q").placeholder="Bill number, or a few words";
   // The button next to it does the same job on the focused view, so it waits
   // for the same data.
   $("#qgo").disabled=false;
   // Arriving from the home page search box, with the query in the URL.
   const params=new URLSearchParams(location.search);
   const pre=params.get("q");
   if(pre){ $("#q").value=pre; query=pre; }
   // ...or from the header search, having clicked a subject. Asked for on 18
   // September: "when you click the topic it brings you to bill search and
   // shows all bills from the current term which match the topic." The term
   // needs no saying -- the current one is what this page opens on -- so the
   // subject is ticked in the Topic facet and the list narrows to it, with
   // the tick showing so a reader can see what narrowed it and untick it.
   // A subject that is not one of the 43 is ignored rather than left
   // selected: a facet nothing matches shows an empty list and no reason.
   const ptopic=params.get("topic");
   if(ptopic&&(META.topics||[]).includes(ptopic)) sel.topic.add(ptopic);
   // ...or from the home page's Latest activity, which shows five rows and
   // hands the rest over here. The sort has to survive the arrival, so
   // sortChosen is set: without it the first render would helpfully put the
   // list back on bill number and the reader would land on the opposite of
   // what they clicked. An unknown value is ignored rather than accepted,
   // because the picker only offers four.
   const psort=params.get("sort");
   if(psort&&["best","num","recent","status"].includes(psort)){
     sortBy=psort; sortChosen=true;
     const so=$("#sort"); if(so)so.value=psort;
   }
   // WHAT THIS PAGE IS, decided before anything is drawn.
   //
   // These three used to sit after render(), which meant a member's page
   // built the whole 2,234-bill list into #results and then threw it away --
   // 300KB of DOM nobody saw -- and the committees index, whose listing is
   // already in the HTML it was served, had that listing replaced by the bill
   // search and showed nothing at all.
   //
   // Focus is not taken either: a reader who opened a member's page did not
   // ask to be put in the search box.
   // Every page built from this template that is not a bill or a list of
   // them: the towns, the members, the committees and the civics pages.
   // A bill's own page is the exception and keeps the box -- GR_STANDALONE
   // is on bill pages too, and there the next bill is a plausible next
   // thought rather than a change of subject.
   if(!window.GR_BILL&&(window.GR_STATIC||window.GR_STANDALONE))
     hideBillSearch();
   if(window.GR_STATIC){
     // The content is in the HTML. Take the chrome down and leave it alone.
     staticChromeDown();
     return;
   }
   // A bill's own page is one bill, so the controls that filter and sort a
   // LIST have nothing to act on. They were left up, with the count reading
   // "2,234 of 2,234 bills in the 2025-2026 term" above a single bill --
   // which at 360px was the whole first screen.
   if(window.GR_BILL)hideListControls();
   // A record's own page gets the report box. Only its own page: the record
   // and the address must agree for the report to be accepted, and a card
   // expanded in the search list is not at its own address.
   if(window.GR_BILL)mountReport("bill",String(window.GR_BILL));
   if(window.GR_MEMBER)mountReport("member",String(window.GR_MEMBER));
   if(window.GR_COMMITTEE)mountReport("committee",String(window.GR_COMMITTEE));
   mountFollow(window.GR_BILL?"bill":window.GR_MEMBER?"member":window.GR_COMMITTEE?"committee":"");
   if(window.GR_MEMBER){openPage("member",String(window.GR_MEMBER));return;}
   if(window.GR_COMMITTEE){openPage("committee",String(window.GR_COMMITTEE));return;}
   $("#q").focus();
   render();
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
   const h=decodeURIComponent(location.hash.slice(1))||(window.GR_BILL||"");
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
       if(t){openTab[id]=t;if(t==="6"&&row)needVersions(row);}
     }
     openBill(id);
   }
 }).catch(e=>{
   /* THE ERROR WENT WHERE THE RECORD WAS. This handler wrote into #results
      whatever page it was on, and the GR_STATIC exit above it sits INSIDE the
      .then chain -- so a rejected fetch never reached it and fell straight
      through to here. One 404 or one dropped connection on idx/2025-2026.json
      and a reader on Alton's town page, or on "Every bill of 2019-2020", had
      the officials or all 1,983 of that term's bills replaced by "Could not
      load the data ... run build_site_v2.py": instructions for a developer,
      about a file that page never needed, standing where the record had been.
      357 pages are built with GR_STATIC -- every town and ward, the directory
      listings, the civics pages, the committees index and the exports page --
      and every one of them carries its whole record in the HTML the reader
      already has.
      So a static page gets the same teardown it gets on success and keeps
      what it was served. It says nothing about the failure because nothing on
      it came out of the file that failed; the bill search, and the bill,
      member and committee pages, whose content really does come from it,
      still get the message below. GR_BILL is never set on a GR_STATIC page,
      so the search row can go unconditionally here. */
   if(window.GR_STATIC){hideBillSearch();staticChromeDown();return;}
   $("#results").innerHTML=`<div class="empty"><b>Could not load the data.</b><br><br>
     <code>${esc(e.message||e)}</code><br><br>
     If that mentions a status code, the file is missing from this folder — run
     <code>build_site_v2.py</code>. If it mentions CORS or the scheme, the page was
     opened from disk rather than served: <code>cd site</code> then
     <code>python3 -m http.server 8000</code>.</div>`;
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
// BILLMATCH:BEGIN -- what counts as a bill number; see the note above SYN.
function billNumbers(q){
  const parts=q.split(",").map(s=>s.trim()).filter(Boolean);
  if(!parts.length)return null;
  const ids=parts.map(p=>p.replace(/\s+/g,"").toUpperCase()
                         .replace(/^([A-Z]{2,5})0+(?=\d)/,"$1"));
  return ids.every(i=>/^[A-Z]{2,5}\d+$/.test(i))?ids:null;
}
// BILLMATCH:END
function matches(b,ignore){
  // A bill number is unique WITHIN a term, so a number search ignores the
  // sidebar filters -- they can only hide the answer. It stays inside the
  // selected term though: once earlier terms are backfilled there really is an
  // HB 84 in each of them, and returning four unrelated bills is its own kind
  // of unhelpful. When nothing matches in this term, the page says whether the
  // number exists in another rather than just showing nothing.
  const ids=billNumbers(query);
  if(ids)return ids.includes(b.id.toUpperCase())&&inTermOf(b);

  if(!inTermOf(b))return false;
  for(const k of["committee","topic","sponsor","kind"])
    if(k!==ignore&&sel[k].size&&!facetVals(b,k).some(v=>sel[k].has(v)))return false;
  if(ignore!=="voteday"&&sel.voteday.size&&!(b.votedays||[]).some(d=>sel.voteday.has(d)))return false;
  const q=query.trim(); if(!q)return true;
  // Every group must match, and any of its alternatives will do.
  return groupsFor(q).every(g=>groupWeight(b,g)>0);
}

function fgroup(key,label,vals,counts,searchable){
  const chosen=sel[key],open=openGroups.has(key);
  let inner="";
  if(searchable){
    const f=sponsorFilter.toLowerCase();
    const shown=f?vals.filter(v=>v.toLowerCase().includes(f)).slice(0,15):[];
    inner=`${[...chosen].map(v=>`<span class="pill">${esc(v)}<button data-unpick="${esc(v)}">×</button></span>`).join("")
      ?`<div class="chosen">${[...chosen].map(v=>`<span class="pill">${esc(v)}<button data-unpick="${esc(v)}">×</button></span>`).join("")}</div>`:""}
      <input class="sbox" id="sbox" aria-label="Find a prime sponsor by name" placeholder="Type a name…" value="${esc(sponsorFilter)}" autocomplete="off">`
      +(shown.map(v=>`<label class="fopt ${!counts[v]?'off':''}"><input type="checkbox" data-f="${key}"
        value="${esc(v)}" ${chosen.has(v)?"checked":""}><span>${esc(v)}</span>
        <span class="c">${counts[v]||0}</span></label>`).join("")
        ||(sponsorFilter?`<p style="font-size:12.5px;color:var(--ink-2)">No match</p>`:""));
  }else{
    inner=vals.map(v=>`<label class="fopt ${!counts[v]&&!chosen.has(v)?'off':''}">
      <input type="checkbox" data-f="${key}" value="${esc(v)}" ${chosen.has(v)?"checked":""}>
      <span>${key==="kind"?`<span class="cstat ${KIND[v]}" style="padding:1px 8px">${KINDL[v]}</span>`:esc(v)}</span>
      <span class="c">${counts[v]||0}</span></label>`).join("");
  }
  return `<div class="fgroup ${open?'open':''}"><button class="fhead" data-g="${key}"
    aria-expanded="${open}"><span>${label}</span>${chosen.size?`<span class="badge">${chosen.size}</span>`:""}
    <span class="chev">▸</span></button><div class="fbody" ${open?"":"hidden"}>${inner}</div></div>`;
}

function renderFacets(){
  const inYear=IDX.filter(inTermOf);
  const cnt=(k,ig)=>{const c={};inYear.filter(b=>matches(b,ig)).forEach(b=>{
    facetVals(b,k).forEach(v=>{if(v)c[v]=(c[v]||0)+1;});});return c;};
  const present=k=>[...new Set(inYear.flatMap(b=>facetVals(b,k)).filter(Boolean))].sort();
  let h="";
  h+=fgroup("committee","Committee",present("committee"),cnt("committee","committee"));
  h+=fgroup("topic","Topic",present("topic"),cnt("topic","topic"));
  h+=fgroup("sponsor","Prime Sponsor",present("sponsor"),cnt("sponsor","sponsor"),true);
  // No "Year Filed" facet. The term picker above the list already chooses
  // the biennium, and splitting one term into its two filing years was a
  // second control for a distinction the card prints on its own. (The
  // <select id="year"> is the TERM picker, despite its id, and stays.)
  h+=fgroup("kind","Status",["active","law","done","veto"].filter(k=>present("kind").includes(k)),cnt("kind","kind"));
  const days={};inYear.filter(b=>matches(b,"voteday")).forEach(b=>(b.votedays||[]).forEach(d=>days[d]=(days[d]||0)+1));
  const allDays=[...new Set(inYear.flatMap(b=>b.votedays||[]))].sort().reverse();
  if(allDays.length)h+=fgroup("voteday","Floor vote day",allDays,days);
  if(Object.values(sel).some(s=>s.size))h+=`<button class="link" id="clear" style="margin-top:12px">Clear all filters</button>`;
  // Replacing innerHTML resets scrollTop to zero. Capture it first and put it
  // back in the same tick, before anything is painted, or every tick of a
  // checkbox throws the reader back to the top of the list.
  const fx=$("#facets");
  const keep=fx?fx.scrollTop:0;
  const inner=fx?fx.querySelectorAll(".fbody"):[];
  const innerKeep=[...inner].map(el=>el.scrollTop);
  fx.innerHTML=h;
  fx.scrollTop=keep;
  // THE COUNT HAS TO BE VISIBLE WITH THE PANEL SHUT. A reader who filtered by
  // topic, scrolled, and came back to a closed panel would otherwise have no
  // way of knowing why the list is short. Same badge the groups carry.
  const ftb=document.getElementById("ftoggle");
  if(ftb){
    ftb.hidden=false;
    const on=Object.values(sel).reduce((n,s)=>n+s.size,0);
    const bd=ftb.querySelector(".badge");
    if(bd){bd.textContent=on?String(on):"";bd.hidden=!on;}
  }
  [...fx.querySelectorAll(".fbody")].forEach((el,i)=>{
    if(innerKeep[i]!==undefined)el.scrollTop=innerKeep[i];
  });
}

function simpleDonut(rc,bid,i){
  // A division vote is counted but anonymous. Same ring, same colours, same
  // threshold line as a roll call -- the difference between the two is who is
  // named, not how the count should look. It used to be drawn in a different
  // palette with no threshold at all, which made the same 191 to 158 look like
  // a different kind of vote.
  const y=rc.yeas||0,n=rc.nays||0,tot=(y+n)||1;
  const R=60,C=2*Math.PI*R,GAP=32,gap=C*GAP/360,avail=C-gap;
  const won=!!rc.passed;
  const seg=(len,fill,sideWon)=>`<circle r="${R}" cx="86" cy="86" fill="none" stroke="${fill}"
    stroke-width="28" opacity="${sideWon?1:.75}"
    stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${-gap/2}"></circle>`;
  const need=rc.threshold_needed||Math.floor(tot/2)+1;
  const frac=Math.min(1,Math.max(0,need/tot));
  const a=(180+GAP/2+(360-GAP)*frac)*Math.PI/180;
  // No mark where the record says more than a majority was needed and the
  // count it was needed of is not on record -- three fifths of the members in
  // office, on a division, where nobody's ballot was recorded. A majority mark
  // there would be a wrong one.
  const tick=rc.threshold_unknown?"":marker(a,R,need,"");
  return `<div class="votewrap"><svg class="donut" viewBox="0 0 172 206" width="172" height="206"
    role="img" aria-label="Division vote, ${y} yes to ${n} no, needing ${
      rc.threshold_unknown?"more than a majority":need}">
    <g transform="rotate(90 86 86)">${seg(avail*y/tot,"var(--yes)",won)}</g>
    <g transform="translate(172,0) scale(-1,1)"><g transform="rotate(90 86 86)">${seg(avail*n/tot,"var(--no)",!won)}</g></g>
    ${tick}${yn(GAP,R,won)}
    ${score(y,n,won)}</svg>
    <div class="legend">
      <div class="lrow"><span class="sw" style="background:var(--yes)"></span>
        <span>Yes${won?`<span class="won" title="this side prevailed">\u2713</span>`:""}</span>
        <span class="c">${y}</span></div>
      <div class="lrow"><span class="sw" style="background:var(--no)"></span>
        <span>No${won?"":`<span class="won" title="this side prevailed">\u2713</span>`}</span>
        <span class="c">${n}</span></div></div></div>`;
}

function donut(bid,i,rc){
  // Yes on the LEFT in green, no on the RIGHT in red, growing up from a gap at
  // six o'clock. Green for yes and red for no is the chamber's own convention
  // -- the buttons on a member's desk -- so it describes the vote rather than
  // judging it. Nothing here relies on telling the two apart by colour: the
  // Y and N under the ring, the gap and the legend all carry it, which matters
  // because red and green are the pair most readers cannot separate.
  const yes=[],no=[];
  for(const[p,tl]of Object.entries(rc.tally||{})){
    if(tl.Yea)yes.push({key:`${p}-Yea`,p,side:"Yea",n:tl.Yea});
    if(tl.Nay)no.push({key:`${p}-Nay`,p,side:"Nay",n:tl.Nay});
  }
  // Biggest group nearest the gap, smallest nearest the top. The two sides
  // meet at twelve o'clock, so ordering each one this way puts the party that
  // carried it at the base and the members who crossed over adjacent to each
  // other across the meeting point -- which is where you compare them. The
  // old order left one crossover group at the base of one arc and the other at
  // the top of the other, as far apart as the ring allows.
  yes.sort((a,b)=>b.n-a.n);
  no.sort((a,b)=>b.n-a.n);
  const segs=yes.concat(no);
  // The ring keeps the order above -- its geometry puts crossovers adjacent
  // at twelve o'clock. The legend does not follow it: read as a list,
  // R-Yes, R-No, D-Yes, D-No puts each party's split on adjacent rows.
  const rows=segs.slice().sort((a,b)=>byParty(a.p,b.p)||yeaFirst(a.side,b.side));
  const total=segs.reduce((a,s)=>a+s.n,0)||1;
  // A wider gap: at ten degrees the two sides read as one ring with a nick in
  // it. At twenty-five they read as two sides of a question.
  const R=60,C=2*Math.PI*R,GAP=32,gap=C*GAP/360,avail=C-gap;
  const key=`${bid}|${i}`,chosen=segSel[key];
  // At rest each side is one unbroken colour, because the first question is
  // whether it passed and a ring cut into party blocks answers a different one
  // before it is asked. The divisions appear when a group is chosen, which is
  // the moment they are what you are looking at.
  const PART=chosen?C*1.4/360:0;
  const arc=(list,fill,sideWon)=>{let off=gap/2;return list.map(s=>{
    const len=Math.max(0,avail*s.n/total-PART),o=-off;off+=len+PART;
    // The losing side sits back a quarter, so which way it went reads before
    // the numbers do. A chosen group overrides that: then the question is who,
    // not which.
    const dim=chosen?(chosen===s.key?1:.28):(sideWon?1:.75);
    return `<circle r="${R}" cx="86" cy="86" fill="none" stroke="${fill}" stroke-width="28"
      stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${o}" opacity="${dim}"
      data-seg="${key}|${s.key}"></circle>`;
    }).join("");};
  // Where the yes side had to reach. rollcall_outcomes works this out per
  // motion, so a veto override marks two thirds of those voting and passing a
  // CACR three fifths of the members in office, which can sit beyond the ring
  // entirely. Without it a chart showing 204 to 116 looks like a comfortable
  // win, and that vote failed. Where the record says a vote needed more than a
  // majority without saying of what (threshold_unknown), no mark is drawn
  // rather than a majority mark that would be wrong; the note says why.
  const voting=(rc.yeas||0)+(rc.nays||0);
  const need=rc.threshold_needed||Math.floor(voting/2)+1;
  const frac=voting?Math.min(1,Math.max(0,need/voting)):0.5;
  const a=(180+GAP/2+(360-GAP)*frac)*Math.PI/180;
  // The ring is 28 wide about radius R, so its edges are at R-14 and R+14. The
  // tick starts flush with the inner edge and runs six past the outer one:
  // grounded on the inside, proud on the outside, so it reads as a mark
  // against the ring rather than a line drawn through it.
  const tick=(voting&&!rc.threshold_unknown)?marker(a,R,need,rc.threshold_rule):"";
  const won=!!rc.passed;
  const circles=`<g transform="rotate(90 86 86)">${arc(yes,"var(--yes)",won)}</g>
    <g transform="translate(172,0) scale(-1,1)"><g transform="rotate(90 86 86)">${arc(no,"var(--no)",!won)}</g></g>`;
  // A check beside every group on the side that prevailed. Which side won is
  // the first thing anyone wants from a vote, and it should not have to be
  // worked out by comparing two numbers against a threshold.
  const legend=rows.map(s=>{
    const winner=(s.side==="Yea")===won;
    return `<button type="button" class="lrow ${chosen===s.key?'sel':''}" aria-pressed="${chosen===s.key}" data-seg="${key}|${s.key}">
    <span class="sw" style="background:${PARTY_COLOR[s.p]||"var(--ink-2)"}"></span>
    <span>${PARTY_NAME[s.p]||s.p} — ${s.side==="Yea"?"Yes":"No"}${
      winner?`<span class="won" title="this side prevailed">\u2713</span>`:""}</span>
    <span class="c">${s.n}</span></button>`;}).join("");
  const others=OTHER.map(([st,label])=>({st,label,n:(rc.members||[]).filter(m=>m.v===st).length})).filter(o=>o.n);
  const oTot=others.reduce((a,o)=>a+o.n,0);
  const oRows=others.length?`<div class="othergrp"><div class="otherhd">Other — ${oTot}<span class="c">not in chart</span></div>
    ${others.map(o=>`<button type="button" class="lrow ${chosen==="other-"+o.st?'sel':''}" aria-pressed="${chosen==="other-"+o.st}" data-seg="${key}|other-${o.st}">
    <span class="sw sw-o"></span><span>${o.label}</span><span class="c">${o.n}</span></button>`).join("")}</div>`:"";
  let list="";
  if(chosen){
    const grid=a=>`<div class="mgrid">${a.map(m=>`<div class="m">${esc(m.n)}</div>`).join("")}</div>`;
    if(chosen.startsWith("other-")){
      const st=chosen.slice(6),o=OTHER.find(x=>x[0]===st)||[st,st,""];
      const names=(rc.members||[]).filter(m=>m.v===st);
      list=`<div class="mlist"><h3>${o[1]} — ${names.length}</h3>
        <p class="note" style="margin:0 0 9px">${o[2]}</p>${grid(names)}</div>`;
    }else{
      const[p,side]=chosen.split("-");
      const names=(rc.members||[]).filter(m=>m.p===p&&m.v===side);
      list=`<div class="mlist"><h3>${PARTY_NAME[p]||p}s who voted ${side==="Yea"?"yes":"no"} — ${names.length}</h3>${grid(names)}</div>`;
    }
  }
  return `<div class="votewrap"><svg class="donut" viewBox="0 0 172 206" width="172" height="206"
    role="img" aria-label="Votes by party: ${rows.map(s=>`${PARTY_NAME[s.p]||s.p} ${s.side==='Yea'?'yes':'no'} ${s.n}`).join(", ")}. ${
      rc.threshold_unknown?"Needed more than a majority":
      rc.threshold_rule?`Needed ${need}, ${esc(rc.threshold_rule)}`:`Needed ${need} for a majority`}.">
    ${circles}${tick}${yn(GAP,R,won)}
    ${score(rc.yeas,rc.nays,won)}</svg>
    <div class="legend">${legend}${oRows}</div></div>${list}`;
}

// Y and N sit either side of the gap, on the side whose votes they are. The
// winner is bold, which is the same fact the ring shows, said a second way for
// anyone who cannot use the first.
// What the yes side had to reach, as a triangle at the rim pointing in at the
// ring. A dashed line crossing the band read as part of the chart's furniture;
// a mark outside it, aimed at the point it is about, reads as a pointer.
function marker(a,R,need,rule){
  // Tip ON the outer edge, base further out. It used to point from outside to
  // a tip nine pixels INSIDE the band, which read as part of the ring rather
  // than as something aimed at it.
  const tip=R+14, out=R+14+11, half=6.5;
  const px=(r,off)=>[86+r*Math.sin(a+off), 86-r*Math.cos(a+off)];
  const [tx,ty]=px(tip,0);
  const [lx,ly]=px(out,-half/out);
  const [rx,ry]=px(out,half/out);
  return `<polygon points="${tx.toFixed(1)},${ty.toFixed(1)}
    ${lx.toFixed(1)},${ly.toFixed(1)} ${rx.toFixed(1)},${ry.toFixed(1)}"
    fill="var(--ink-2)"><title>${need} needed${rule?` \u2014 ${esc(rule)}`:""}</title></polygon>`;
}

function yn(GAP,R,won){
  // Below the ring rather than on it. Following the curve put them at an angle
  // to each other and close together near the gap, which read as decoration on
  // the chart; set on a line underneath, they read as labels for the two sides.
  // The legend beside the donut is taller than the donut, so this space costs
  // nothing.
  const Y=188;
  // --ink-2 FOR THE LOSING LETTER, and it was --ink-3, which has not existed
  // since the palette went to two inks on 7 September. An unresolved var() in
  // an SVG fill does not inherit and does not warn: it falls back to the
  // property's initial value, which for fill is BLACK. On the light palette
  // black read as emphasis and nobody noticed for five days; on the dark one
  // the losing side's Y or N was black on a dark card and effectively gone.
  //
  // Worth knowing why every search missed it: the token name is BUILT here by
  // concatenation, so the string "--ink-3" appears nowhere in this file and
  // grep for it finds only comments. The same shape of bug is already
  // recorded in app.css about --brick, which was used and never defined, so
  // color-mix() dropped the whole declaration silently. A var() that does not
  // resolve is the quietest failure in this codebase.
  const at=(x,txt,won)=>`<text x="${x}" y="${Y}" text-anchor="middle" font-size="30"
      letter-spacing=".04em" font-weight="${won?700:400}"
      fill="var(--ink${won?"":"-2"})">${txt}</text>`
    // Bold and underlined, so the prevailing side survives being printed in
    // grey, photocopied, or read by somebody who cannot see the colours.
    +(won?`<line x1="${x-14}" y1="${Y+8}" x2="${x+14}" y2="${Y+8}"
      stroke="var(--ink)" stroke-width="2.5"></line>`:"");
  return at(42,"Y",won)+at(130,"N",!won);
}

// The count in the middle, with the side that prevailed in bold.
//
// PREVAILED, not the larger number. A veto override at 204 to 116 has more
// yeses and still failed, because it needed two thirds; bolding 204 would say
// the yes side won a vote it lost. The threshold tick on the ring shows why,
// and this agrees with it.
function score(y,n,won){
  const part=(v,b)=>`<tspan font-weight="${b?700:400}">${v}</tspan>`;
  return `<text x="86" y="91" text-anchor="middle" font-size="16" fill="var(--ink)"
    font-variant-numeric="tabular-nums">${part(y,won)}<tspan fill="var(--rule-2)"
    font-weight="400" dx="2" dy="0">\u2009|\u2009</tspan>${part(n,!won)}</text>`;
}

function fullRecord(bid,i,rc){
  const k=`${bid}|${i}`;
  if(!fullOpen.has(k))return `<button type="button" class="discl" aria-expanded="false" data-full="${k}">View full voting record →</button>`;
  // Sorted on the surname-first key, not on what is displayed: ordering
  // "Rep. Jodi Nelson (R)" alphabetically groups 400 members by honorific
  // and then by first name.
  const col=(v,p)=>(rc.members||[]).filter(m=>m.v===v&&(p==null||(m.p||"X")===p))
    .sort((a,b)=>(a.s||a.n||"").localeCompare(b.s||b.n||""));
  const grid=a=>`<div class="mgrid">${a.map(m=>`<div class="m">${esc(m.n)}</div>`).join("")}</div>`;
  const sect=([st,label,blurb])=>{const a=col(st);return a.length?`<div class="mlist">
    <h3>${label} — ${a.length}</h3><p class="note" style="margin:0 0 9px">${blurb}</p>${grid(a)}</div>`:"";};
  const y=col("Yea"),n=col("Nay"),tot=(rc.members||[]).length;
  // One pair of columns per party, Republicans first, then Democrats, then
  // anyone else: a party's yea and nay sit side by side, so its split is read
  // across one row rather than hunted for in two lists 400 names long.
  const parties=[...new Set((rc.members||[]).filter(m=>m.v==="Yea"||m.v==="Nay")
    .map(m=>m.p||"X"))].sort(byParty);
  const pair=p=>{const py=col("Yea",p),pn=col("Nay",p),nm=PARTY_NAME[p]||p;
    return `<div class="full"><div><h3>${nm} Yea — ${py.length}</h3>${grid(py)}</div>
    <div><h3>${nm} Nay — ${pn.length}</h3>${grid(pn)}</div></div>`;};
  return `<button type="button" class="discl" aria-expanded="true" data-full="${k}">Hide full voting record</button>
    ${parties.map(pair).join("")}
    ${OTHER.map(sect).join("")}
    <p class="note" style="margin-top:12px">All ${tot} recorded members accounted for:
      ${y.length} yes, ${n.length} no, ${tot-y.length-n.length} not voting.</p>`;
}

/* ---- the panes -------------------------------------------------------
   One function per tab. This was one 472-line function holding 26 consts
   in a single scope, and three times in one day a template literal read
   one of them before its line ran: a blank card, with the bill's data
   already fetched and sitting in hand.

   These are function DECLARATIONS rather than consts holding arrows.
   Declarations are hoisted and initialised before any of this runs, so
   the order they appear in cannot be got wrong. Order still matters
   inside each one, and each one is now short enough to see it.

   b is the index row, d the fetched detail. rsa is passed in rather than
   rebuilt: it compiles a RegExp from the bill's own statute citations,
   two of these need it, and a parameter says so where scope would not. */

// Pure and identical for every bill, so built once here rather than
// rebuilt inside a map callback that runs for each of 2,234 of them.
// How a vote was taken, title-cased because every place this appears is a
// LABEL beside a date rather than a clause in a sentence: "12 March 2025 ·
// House · Voice Vote". Prose elsewhere still says "decided on a voice vote" in
// lower case, which is correct there and is not this constant.
const AVK={VV:"Voice Vote",DV:"Division Vote",RC:"Roll Call"};
// A committee report's colour, from what was MOVED rather than from who won.
//
// It used to be chosen from `side` alone: Committee and Majority green,
// Minority red. So a unanimous committee recommending a bill be killed got
// the same green as one recommending it pass, and a minority that wanted it
// to pass got the red. 1,248 of 2,637 chips read as the opposite of the
// motion they label -- 556 of them a whole committee's Inexpedient to
// Legislate shown in the colour of approval.
//
// Which side prevailed is already on the row: the Majority/Minority label
// sits to the left of the chip and the committee's vote beside it, so
// nothing is lost by colouring the motion instead.
const RECCOLOUR=[[/INEXPEDIENT/i,"s-done"],
                 [/INTERIM\s+STUDY|RE-?REFER/i,"s-study"],
                 [/OUGHT\s+TO\s+PASS/i,"s-law"]];
const recColour=r=>{const m=RECCOLOUR.find(([re])=>re.test(r||""));
  return m?m[1]:"";};
// Who signed in for and against the bill at a hearing.
//
// Counts only, deliberately. The General Court's sign-in sheet carries a name,
// a town and often written testimony for each of some 400,000 rows, and almost
// every one is a member of the public who signed a committee's sheet rather
// than a public figure. The number is the civic fact; the person is not this
// site's to republish.
//
// "dated" is the difference between a fact and a number that looks like one:
// with it the count is this hearing's, without it the database had the bill
// but not this date and the figure covers every hearing the bill had.
const signins=t=>{
  if(!t||!t.total)return "";
  const n=x=>Number(x||0).toLocaleString();
  const bit=(v,label,cls)=>v?`<span class="sgn ${cls}">${n(v)} ${label}</span>`:"";
  return `<span class="tnote">${bit(t.support,"support","for")}${
    bit(t.oppose,"oppose","against")}${bit(t.neutral,"neutral","")} ${
    n(t.total)} signed in${t.dated?"":" across this bill’s hearings"}</span>`;
};
const CHNAME={H:"Representatives",S:"Senators"};
const hms=x=>new Date(x*1000).toISOString().substr(11,8);
// "0:02:00" or "-0:05:00" as the manifest wrote it -- and a plain number of
// seconds, which is what actually arrives now. build_proceedings.py runs the
// manifest string through as_seconds() and build_site_v2 writes the float, so
// String(2646) matched nothing here and every estimate collapsed to zero.
const secs=v=>{if(typeof v==="number")return v;
  const m=/^(-?)(\d+):(\d{2}):(\d{2})$/.exec(String(v||""));
  if(m)return (m[1]?-1:1)*(+m[2]*3600+ +m[3]*60+ +m[4]);
  const n=parseFloat(v); return isFinite(n)?n:0;};
// The bill's own shape: a numbered section opens a block, and everything
// under it belongs to that section. Set as one paragraph it is unreadable,
// and anyone used to the printed version loses their footing entirely.
const SEC=/^\s*(\d{1,3})\s+(?=[A-Z(])/;
// The General Court puts a whole section in one paragraph. The outline a
// reader knows from the printed bill -- I., (a), (b), II.(a), a new RSA
// section number -- exists only in that document's typography, and is gone
// by the time the page is read as text.
//
// So it is rebuilt, and only where the record is unambiguous: a break goes
// in before a marker that OPENS after a full stop or a colon and is followed
// by a capital or an opening quote. "either (a) all new or (b) repealed"
// does not qualify, because what follows is lower case.
//
// This changes the layout and not one word. The text is the General Court's;
// where its lines fall on this page is ours, and could not be otherwise --
// the line breaks were never in the file.
const OUTLINE=/(?<=[.:])\s+(?=(?:[IVXL]{1,5}\.(?:\([a-z]\))?|\([a-z]\)|\d{1,3}:\d+[-\w]*)\s+[A-Z\u201C"])/g;

// Statutes cited in the committee's own words become links. Applied AFTER
// escaping, which is safe because a citation has nothing in it to escape,
// and longest first so "RSA 91-A" cannot eat the front of "RSA 91-A:4".
// One pass, not one pass per citation: replacing in sequence rescans what it
// has already written, so "RSA 91-A" matched inside the anchor just built for
// "RSA 91-A:4". Longest first inside the alternation keeps the longer
// citation winning where both could match.
function makeRsa(d){
  return (s)=>{const m=d.rsa||{},ks=Object.keys(m);
    if(!ks.length)return s;
    const re=new RegExp(ks.sort((a,b)=>b.length-a.length)
      .map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|"),"g");
    return s.replace(re,k=>`<a href="${esc(m[k])}" target="_blank" rel="noopener"`
      +` class="rsa">${esc(k)}</a>`);};
}

// Quoted from the General Court's own bill status page, in the order that page
// states them. This table lived only in the Python renderer that drew these
// bills a second time; every one of the 4,230 bill files carries a facts
// object, so deleting that renderer without this would have taken the stated
// status off every bill on the site.
//
// Nothing here is worked out. "Local government impact" is the page's Y or N
// written as a word, and that is the whole of the interpretation.
// FACTS and factsTable drew the status page's own fields at the top of the
// Documents tab -- status, date introduced, committee code -- every one of
// which is already on the summary in a sentence. Removed rather than
// hidden, so nothing calls a function that is not there.
const PANE_NOTE={
  // The Videos tab had a paragraph here explaining, once at the top, how
  // every start time below it was arrived at. Each proceeding already says
  // that for itself -- the word "approximate" beside a time that is one, and
  // a line under the player saying what the number is -- so the paragraph was
  // the same thing said twice, above rather than beside the claim it was
  // about.
  reports:`The recommendation, the vote and the day it was signed come from the
    docket; the reasoning, where there is any, is reproduced from the House
    Calendar in the committee\u2019s own words.`,
};
const paneNote=(k)=>PANE_NOTE[k]?`<p class="src">${PANE_NOTE[k]}</p>`:"";

// The General Court's own analysis of the bill, at the top of the summary
// because it is the shortest true answer to what the bill does. Long ones are
// clamped to six lines by CSS and given a button by clampAnalysis(), which
// measures rather than guessing from a character count -- six lines is a
// different number of characters on a phone and on a desktop.
function analysis(d, rsa){
  const t=((d.billtext||{}).analysis||"").trim();
  if(!t)return "";
  return `<section class="anbox" data-an="1">
    <h2 class="anlab">Official legislative analysis</h2>
    <div class="antext">${rsa?rsa(esc(t)):esc(t)}</div>
    <p class="src">Source: NH General Court</p></section>`;
}

// WHAT THIS BILL IS, where its number carries a standing meaning. HB1 has
// been the state budget in every term since 1993-1994 and its title says only
// "making appropriations for the expenses of certain departments of the
// state", which is accurate and tells a reader nothing.
//
// ATTRIBUTED TO THIS SITE, NOT TO THE RECORD. Everything else in this box is
// the General Court's -- the official analysis says "Source: NH General
// Court" underneath it for exactly this reason. These words are Granite
// Record's, and a reader who cannot tell the difference has been given a
// worse page, not a fuller one.
function billNote(d){
  const n=d&&d.bill_note;
  if(!n||!n.note)return "";
  return `<section class="anbox billnote">
    <h2 class="anlab">${esc(n.label||"About this bill")}</h2>
    <div class="antext">${esc(n.note)}</div>
    <p class="src">Written by Granite Record, not quoted from the General
      Court. It describes what this bill number is for, which its title does
      not say.</p></section>`;
}

// WHAT AN ARCHIVED TERM ACTUALLY HAS, which is not the same in all eighteen
// of them. This was one paragraph on one boolean, drawn on 31,449 of the
// site's 33,683 bill pages, and it was wrong in both directions at once.
//
// It understated the recent terms: 2017-2018, 2019-2020 and 2023-2024 have
// full dockets, and the "View docket" block that contradicts the paragraph
// renders seven lines below it in this same function.
//
// It overstated the older ones. "The recorded votes come from the General
// Court's database" was false for fifteen terms; named roll calls exist only
// for 2023-2024 and the current term. "The committee it went to" was false
// for the five terms 1989-1998, which have none.
//
// d.archived is now the term's coverage object rather than true, computed at
// build time from what was fetched. It stays truthy, so nothing that merely
// tests it had to change. The wording is derived from the flags rather than
// from a list of terms, because the fetches are still landing -- 2021-2022's
// docket is being pulled as this is written -- and a hard-coded list would be
// wrong again by the afternoon.
//
// NEVER "DOES NOT EXIST". These are records not yet fetched. The General
// Court has them; this site does not have them yet, and saying otherwise
// would be inventing a fact about somebody else's archive.
function archivedNote(d){
  const a=d&&d.archived;
  if(!a)return "";
  const c=(typeof a==="object")?a:{};
  const P=s=>`<p class="note" style="margin:10px 0 0">${s} The bill's own
    record at the General Court is linked above.</p>`;

  // The first year of the term. The General Court's roll-call files begin in
  // 1999, its online calendars in 1997 and its YouTube channels in May 2020;
  // before those, the copy this site reads does not exist to fetch, and the
  // page must not say it is merely missing.
  const y=parseInt(String(d.term||d.year||"").slice(0,4),10)||0;
  const and=xs=>xs.join(", ").replace(/, ([^,]*)$/," and $1");
  // A TERM'S SPONSORS ARRIVE A BILL AT A TIME, from the text the lane saves, so
  // the term's flag can be false on a bill whose Sponsors tab has names in it.
  // The bill's own list is asked first.
  const hasSp=c.sponsors||(d.sponsors||[]).length>0;

  // WHERE THE ROLL CALL RECORD STARTS, which is not where this site's
  // fetching has got to. RollCallHistory.txt and RollCallSummary.txt are the
  // General Court's own files of named votes and both begin with the 1999
  // session, so for the five terms 1989-1998 there is nothing to fetch.
  //
  // It said this in one place -- the !c.docket branch below -- and that branch
  // renders on no page at all while narratives.json covers all nineteen terms,
  // so the sentence reached zero readers. Meanwhile the has-docket branch
  // correctly refuses to list the roll calls as a gap before 1999 and then
  // said nothing about them, leaving 8,525 bills of 1989-1998 to read the
  // silence as a backlog. Both branches use it now; neither owns it.
  //
  // The !c.docket branch is NOT dead code and must not be removed with it: it
  // is the state every backfill term passes through, between landing in
  // data/bills.json and having its docket narrated.
  //
  // THE FILES START IN 1999, NOT THE VOTES. The House Journal of 1997 prints
  // its roll calls name by name, so "that is where the record starts" was
  // false for every one of those 8,525 pages. What begins in 1999 is the
  // General Court's roll-call files, and the sentence now says so.
  const before1999=(!c.votes&&y&&y<1999)?` No roll call from before 1999 is
    listed by name here: the General Court's roll-call files, RollCallHistory.txt
    and RollCallSummary.txt, which every named vote on this site is read from,
    begin with the 1999 session. The docket gives the tallies it recorded, and
    the printed journals name who voted which way.`:"";

  // WHERE THE WRITTEN REPORTS START, which is the same kind of boundary. The
  // House's written committee reports on this site are read from its
  // calendars, and the General Court's online calendars begin in 1997, so the
  // 6,676 bills of 1989-1996 were told the reports were "not yet fetched" --
  // a backlog that no fetch could clear. For those terms the docket's report
  // lines are the record of what each committee recommended, and the page
  // already shows them.
  //
  // THE HOUSE'S REPORTS, NOT EVERYONE'S. Every written report on an archived
  // bill came from a House Calendar; the Senate's are read from the
  // database, which holds 2025-2026 alone. And the docket's report lines
  // (a COMM, COMMITTEE, MAJ or MIN REPORT that is not a conference's or an
  // adoption) carry "(VOTE n-n)" on 93 to 96 per cent of the House's in each
  // term of 1989-1996, but on none of the Senate's 3,601 of 1989-1994 --
  // the one that does is a House report filed under S -- and on 510 of
  // 1995-1996's 1,085. So "and its vote" was false of most Senate committees
  // these pages name, and "the House committee's vote" would leave out the
  // Senate's where the docket has it.
  const before1997=(!c.reports&&y&&y<1997)?` The House committees' written
    reports begin here with 1997, the first year of the General Court's online
    calendars, which print them; the Senate committees' begin with 2025. For
    this term the page gives each committee's recommendation as the docket
    records it, and the committee's vote wherever the docket gives one.`:"";
  // A bill that carries its own text does not need telling the text is
  // elsewhere: 94 to 98 per cent of every archived term's bills have it.
  const hasText=!!(((d.billtext||{}).body||"").trim());

  if(!c.docket){
    // WHAT IS HERE, THEN WHAT IS NOT. This branch told every bill of
    // 1999-2016 that "the recorded votes ... have not been fetched yet" --
    // 15,389 pages, each with a Votes tab beside the sentence -- because it
    // never looked at c.votes, and it said nothing of the hearings that
    // 1989-1998 have. It reads every flag now.
    const have=["the title and the status in each chamber"];
    if(c.committee)have.push("the committee it went to");
    if(c.hearings)have.push("its hearings");
    // No comma inside an item: and() turns the last comma into "and", which
    // made this "its roll calls and member by member".
    if(c.votes)have.push("each member's vote on its roll calls");
    if(hasSp)have.push("its sponsors");
    if(c.reports)have.push("the House committee's written report");
    const gaps=["the docket's full history"];
    if(!hasSp)gaps.push("the sponsors");
    if(!c.reports&&y>=1997)gaps.push("the House committees' written reports");
    if(!c.votes&&y>=1999)gaps.push("the roll calls");
    if(!c.hearings)gaps.push("its hearings");
    return P(`This term is archived. Here: ${and(have)}. Not yet on this
      site for it: ${and(gaps)}.${before1997}${before1999}`);
  }

  // Has a docket. What is missing beyond it is what the reader needs told.
  const gaps=[];
  if(!hasSp)gaps.push("the sponsors");
  if(!c.reports&&y>=1997)gaps.push("the House committees' written reports");
  if(!c.votes&&y>=1999)gaps.push("the roll calls naming individual members");
  if(!c.video&&y>=2019)gaps.push("a recording of any hearing");
  // Both returns carry it, not just the one with gaps. A pre-1999 term whose
  // sponsors and reports have landed reaches the first of these, and "the
  // recorded votes are all here" is false for every term before 1999 --
  // which is the same wrong claim in the other direction.
  //
  // WHAT IS HERE, NAMED FROM THE FLAGS. This said "the docket, the sponsors
  // and the committee reports are all here" whenever nothing was missing,
  // which a term before 1997 now reaches with no written report on it at all.
  //
  // "CLOSE TO COMPLETE" ONLY WHERE IT IS. A term of 1989-1996 reaches here
  // with no written report, no named vote and no recording, and was told its
  // record was close to complete; it is told what is here instead. And the
  // written reports are the House committees': no archived term has a
  // Senate committee's.
  if(!gaps.length){
    const have=["the docket", "the sponsors"];
    if(c.reports)have.push("the House committees' written reports");
    if(c.votes)have.push("the recorded votes");
    const lead=(c.reports&&c.votes)
      ?`This term is archived, but its record is close to complete:
      ${and(have)} are all here.`
      :`This term is archived, and ${and(have)} are here.`;
    return P(`${lead}${hasText?"":` What a current term adds is the
      bill's own text, which is linked rather than loaded.`}${
      before1997}${before1999}`);
  }
  return P(`This term is archived, and its docket is here: every action the
    General Court recorded, and the committee's recommendation and the vote on
    it. Not yet fetched for this term: ${and(gaps)}.${before1997}${before1999}`);
}

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
    if(m && !seen.has(m[1])) seen.set(m[1], u);
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
const JMARK={p:"✓",x:"✕",h:"↺"};
const JBODY={H:"House",S:"Senate",G:"Governor",L:"Law",V:"Voters"};
const JOURNEY_SHOWN=6;
function journeyList(b,d){
  const st=((d.journey||{}).steps)||[];
  if(!st.length)return "";
  const k=dkey(b.id);
  const cut=st.length>JOURNEY_SHOWN&&!jOpen.has(k);
  const hide=i=>cut&&i>=2&&i<st.length-(JOURNEY_SHOWN-2);
  const line=(s,i)=>`<li class="j-${esc(s.mark)}"${hide(i)?" hidden":""}><span class="jg"
    aria-hidden="true">${JMARK[s.mark]||""}</span><span class="jb">${
    esc(JBODY[s.body]||s.body)}</span><span class="jt">${esc(s.text)}</span><span
    class="jd">${s.date?esc(railDay(s.date,true)):""}</span></li>`;
  const rows=st.map(line);
  if(cut)rows.splice(st.length-(JOURNEY_SHOWN-2),0,
    `<li class="jmore"><button type="button" class="link" data-jmore="${esc(k)}">Show ${
      st.length-JOURNEY_SHOWN} more</button></li>`);
  return `<ul class="jl">${rows.join("")}</ul>`;
}

function factsTable(b,d){
  const f=d.facts||{};
  const rows=[];
  const add=(k,v,wide)=>{ if(v) rows.push([k,v,wide]); };

  // NOT facts.gen_status, WHICH IS NOT A STATUS ON MOST BILLS. Counted over
  // the current term's 2,234: it reads "HOUSE" on 1,065 and "SENATE" on 454
  // -- 68% -- because the field records which chamber the bill is in, not
  // what happened to it. A row labelled "Bill Status" saying "HOUSE" is
  // worse than no row. Where it IS a status (SIGNED BY GOVERNOR, VETOED BY
  // GOVERNOR, PASSED, LAW WITHOUT SIGNATURE, VETO OVERRIDDEN, 715 bills) the
  // site's own classification says the same thing in words a reader uses, so
  // nothing is lost by taking it from there for all of them.
  add("Bill Status", esc(b.status||d.next_step||""));
  // HOW IT GOT HERE, IN PLACE OF THE HOUSE STATUS AND SENATE STATUS ROWS.
  // Those were the General Court's own per-chamber fields, and they are blank
  // for one chamber on most bills: this term 932 bills carried only a House
  // status, 351 only a Senate one and 156 neither -- HB 57 of 2025 passed the
  // House on a voice vote and its House field is empty. The journey is read
  // from the docket instead, one line per decision, the same lines the rail
  // above is dated from (the person chose it on 24 September).
  //
  // ACROSS THE WHOLE PANEL, its label on a line of its own. Beside the
  // analysis the panel is at most 440px, and in the value column of a 42%
  // label the list's glyph, body and day left about 66px for the words:
  // "Passed with an amendment, 16–8" ran to four lines, a conference refusal
  // to nine. Spanning both columns gives the words about 250px.
  add("How it got here", journeyList(b,d), true);
  if(d.chapter)
    add("Chapter", `Chapter ${esc(d.chapter)}`
      + (d.year?`, Laws of ${esc(d.year)}`:""));
  // HB 2 OF 2025 AMENDS 238 CHAPTERS, from 685 cited sections. Written out
  // in full, that single row is about thirty lines of the table on a desktop
  // and most of a screen on a phone -- in the panel a reader meets first, in
  // front of everything they came for. Eight, and the rest behind a native
  // disclosure: no script, the count is in the control so the scale of it is
  // still stated, and eight chapters is enough to see what kind of bill this
  // is. Ten or fewer are all shown, because hiding two behind a control that
  // costs a line is not a saving.
  const ch=rsaChapters(d);
  const rsaLink=([n,u])=>`<a class="rsa" href="${esc(u)}" target="_blank"`
    +` rel="noopener">${esc(n)}</a>`;
  const RSA_SHOWN=8;
  if(ch.length && ch.length<=RSA_SHOWN+2)
    add(ch.length===1?"Amends RSA chapter":"Amends RSA chapters",
      ch.map(rsaLink).join(", "));
  else if(ch.length)
    add("Amends RSA chapters",
      `<span class="rsaset">${ch.slice(0,RSA_SHOWN).map(rsaLink).join(", ")}</span>`
      +`<details class="rsamore"><summary><span class="shut">Show all ${
        ch.length} chapters</span><span class="open">Show fewer</span></summary>`
      +`<span class="rsaset">${ch.slice(RSA_SHOWN).map(rsaLink).join(", ")}</span>`
      +`</details>`);
  if(d.house_committee) add("House Committee", cmteLink("House "+d.house_committee,b.term));
  if(d.senate_committee) add("Senate Committee", cmteLink("Senate "+d.senate_committee,b.term));
  // THE TOPIC MODEL'S REFUSAL IS NOT A SUBJECT. "Miscellaneous" is what
  // topic_model.py returns below its confidence floor -- its own way of
  // declining to answer -- and the General Court's 46 subject codes do not
  // contain it. In this row it reads as the record's word for what the bill is
  // about. 69 of the archive's organisation-day housekeeping resolutions carry
  // it under titles that are word for word the 14 this term correctly leaves
  // blank ("Adopting the rules of the 2024 session for the 2025-2026
  // biennium", "RESOLVED, that the biennium salary of the members of the
  // Senate be paid in one undivided sum"), and 10,894 bills carry it in all.
  //
  // OMITTED, NOT BLANKED. A row that is not there says nothing, which is what
  // is known. The guard is on where the word came from and not on the word: a
  // subject the General Court itself filed a bill under is printed whatever it
  // says.
  if(!(d.subject==="Miscellaneous"&&d.subject_source==="granite record"))
    add("Subject", esc(d.subject||""));
  add("Introduced", esc(f.date_introduced||""));
  add("LSR", esc(f.lsr||""));
  if(!rows.length) return "";
  return `<section class="facts"><h2>On the record</h2>
    <table class="facttab"><tbody>${rows.map(([k,v,wide])=>wide
      ?`<tr class="wideh"><th scope="colgroup" colspan="2">${esc(k)}</th></tr>`
        +`<tr class="wide"><td colspan="2">${v}</td></tr>`
      :`<tr><th scope="row">${esc(k)}</th><td>${v}</td></tr>`).join("")}</tbody></table>
    ${d.docket_url?`<p class="src"><a href="${esc(d.docket_url)}" target="_blank"
      rel="noopener">This bill on gencourt &#8599;</a></p>`:""}</section>`;
}

// HOW A BILL ENDED WHEN NOTHING WAS VOTED ON IT. Two lines, both from the
// record rather than from the status field, and both about bills whose last
// docket line is not an outcome:
//  - a committee that took a bill for interim study reports on it in the
//    autumn, and that report is the end of the story. The docket prints it;
//    the page said nothing, so "Referred for interim study" stood as the last
//    word for months after the committee had answered.
//  - a term that has run out of session days finishes every bill still
//    pending. The chip keeps the record's own word ("Laid on the table");
//    this says why nothing follows it. status/status.txt sets the date.
function endNote(d){
  const s=d.study_report,out=[];
  if(s)out.push(`<p class="note"><b>Interim study report${s.date?`, ${
    esc(fdate(s.date))}`:""}:</b> the committee ${s.recommended
      ?"recommended the subject for future legislation"
      :"did not recommend the subject for future legislation"}${
      s.vote?`, ${esc(s.vote)}`:""}.</p>`);
  if(d.session_over)out.push(`<p class="note">The chambers do not sit again
    this term: the last session day was ${esc(fdate(d.session_over))}. A bill
    that had not passed by then did not advance, whatever its last recorded
    status says.</p>`);
  return out.join("");
}

function renderSummary(b,d,rsa){
  const _an=billNote(d)+analysis(d,rsa);
  // ON THE RECORD SITS AT THE TOP ON A WIDE SCREEN, AND UNDER THE ANALYSIS ON
  // A NARROW ONE. Asked for in those terms on 20 September.
  //
  // THIS REVERSED AN EARLIER DECISION, which is worth keeping rather than
  // quietly overwriting. The comment here used to read "WHAT A BILL OPENS
  // WITH IS THE WRITING, NOT THE TABLE. Asked for in those terms", and it
  // moved the panel after the analysis in the markup so the float started
  // below the prose and sat beside the story. Both arrangements were asked
  // for, a fortnight apart; this is the newer one.
  //
  // A FLOATED BOX HAS TO COME FIRST IN THE DOM TO SIT AT THE TOP, so the
  // panel is emitted before the writing and the narrow layout orders it back
  // -- .anbox is order:1 and .facts order:2 below 1100px, which is what puts
  // the analysis above it on a phone and has done all along. app.css's .facts
  // float has described exactly this arrangement the whole time; the markup
  // is what had drifted away from it.
  //
  // What that cost, and why it is still a float: a grid row is as tall as its
  // tallest item, so the row holding the 488px panel gave the analysis beside
  // it a 274px dead tail, and no span fixed every bill -- two rows left 75px
  // on HB 1, three left an empty row on HB 751. A float cannot push in-flow
  // content down at all, which is the property actually wanted. See .facts in
  // app.css.
  // A BAND ACROSS THE TOP (the person, 24 September): on a desktop the
  // analysis and any bill notes on the left and On the record on the right,
  // with the stage sections full width below; on a phone the panel first,
  // then the writing. The band holds the two as siblings in their own box, so
  // the story below can never run under the panel, which is what the float
  // did once text stopped being capped at 560px. No writing: the panel alone.
  const _top=_an
    ? `<div class="sumtop"><div class="sumrow"><div class="sumlead">${_an}</div>${factsTable(b,d)}</div></div>`
    : factsTable(b,d);
  return _top + `
${d._error?`<div class="loaderr"><b>This bill's detail did not
    load.</b><span>${esc(d._error)}</span></div>`:""}
    ${(d.notes||[]).map(x=>`<p class="note">${esc(x)}</p>`).join("")}
    ${(d.stages&&d.stages.length)
      ? `<div class="story">${d.stages.map(st=>
          `<div class="stg">${st.label?`<h2>${esc(st.label)}</h2>`:""}
           <p>${esc(st.text)}</p>${(st.notes||[]).map(n=>
             `<p class="note">${esc(n)}</p>`).join("")}</div>`).join("")}</div>`
      : (d.narrative?`<p class="story"><span class="stg">${esc(d.narrative)}</span></p>`:"")}
    ${endNote(d)}
    ${archivedNote(d)}
    ${(d.events||[]).length?`<details class="docket"><summary><span class="caret"></span>View docket</summary>
      <p class="note">Every action the General Court recorded, in its own words
        and in the order it recorded them.</p>
      <ul class="tl">${d.events.filter(e=>!e.cancelled).map(e=>`<li>
        <span class="d">${e.date?esc(fdate(e.date)):""}</span>
        <span class="w">${esc(e.text||"")}${e.cite?` <span class="cite">${
          e.cite_url?`<a href="${esc(e.cite_url)}" target="_blank"
          rel="noopener">${esc(e.cite)}</a>`:esc(e.cite)}</span>`:""}${
          signins(e.testimony)}${
          /* a date put right by hand: the line above still says the other */
          e.date_note?`<span class="note tldate">${esc(e.date_note)}</span>`:""}${
          /* a row the docket files under the wrong bill, and its twin */
          e.row_note?`<span class="note tldate">${esc(e.row_note)}</span>`:""}</span>
        </li>`).join("")}</ul></details>`:""}
`;
}

function renderVotes(b,d){
  // NOTHING ABOVE THE VOTES. This tab opened, in turn, by explaining the roll
  // call file and the presiding officer's tie-breaking vote; then with one
  // line saying that roll calls record individual legislators where voice and
  // division votes do not; then with the bill's own count of how many of its
  // floor votes went unrecorded. All three are gone, and the last two for the
  // same reason: every card below now says what its own vote was, in the
  // words the person wrote -- "There is no count and no record of how
  // individual members voted" on a voice vote, the count but not the members
  // on a division. A reader who wants to know how many were unrecorded can
  // count the cards that say so, and each one says it where they are looking.
  //
  // d.vote_note is still built and still published in the record; it is only
  // no longer drawn here. build_site_v2.vote_note_for and narrative.py are
  // untouched, so nothing downstream of them changes and the sentence is one
  // line away if it is wanted back.
  return ((d.rollcalls||[]).length?d.rollcalls.map((rc,i)=>{
    const vk=rc.vote_kind||"RC";
    let body;
    if(vk==="RC"){
      body=donut(b.id,i,rc)+fullRecord(b.id,i,rc);
    }else if(vk==="DV"&&rc.yeas!=null){
      // A division vote is counted but anonymous. Chart the split; there is no
      // member list to show, and saying so is the point.
      body=simpleDonut(rc,b.id,i)+`<p class="note" style="margin-top:11px">Decided on a
        division vote. There is a total count of how many legislators voted for
        each side, but no record of how individual members voted.</p>`;
    }else{
      body=`<p class="note" style="margin-top:6px">Decided on a voice vote. There is
        no count and no record of how individual members voted.</p>`;
    }
    return `<section class="rc">
      <div class="rchead"><h2 class="rcq">${esc(rc.question)}${
        rc.amendment?` <span class="ramd">${esc(rc.amendment)}</span>`:""}</h2>
      <span class="rcd">${fdate(rc.date)} · ${rc.body==="H"?"House":"Senate"}${
        AVK[vk]?` · ${AVK[vk]}`:""}</span>
      <span class="rcres ${rc.passed?'pass':'fail'}">${rc.passed?"Adopted":"Failed"}</span></div>
      ${rc.mover?`<p class="rcby">Moved by ${esc(rc.mover)}</p>`:""}
      ${rc.threshold_note?`<p class="note" style="margin:6px 0 0">${esc(rc.threshold_note)}</p>`:""}
      ${rc.outcome_conflict?`<p class="note" style="margin:6px 0 0">${esc(rc.outcome_conflict)}</p>`:""}
      ${body}</section>`;}).join("")
    :`<p class="note">No roll call votes on this bill.</p>`);
}

// "HB 1123 - House Labor Public Hearing", "HB 1123 - Senate Floor Debate".
// Only the kind is title-cased: a committee's name is the General Court's own
// and "Labor, Industrial And Rehabilitative Services" is not how it spells it.
const CHWORD={H:"House",S:"Senate"};
function stationTitle(b,s){
  const kind=(s.what||"").replace(/\b[a-z]/g,c=>c.toUpperCase());
  const cmte=(s.committee||"").trim();
  const ch=CHWORD[s.body]||"";
  // A floor row's "committee" is already the chamber, so it is not repeated.
  const where=(!cmte||cmte===ch)?ch:(ch?`${ch} ${cmte}`:cmte);
  return [b.n||b.id, [where,kind].filter(Boolean).join(" ")]
    .filter(Boolean).join(" - ");
}

// THE SENATE COMMITTEE'S OWN REPORT OF THE HEARING, under the hearing's video.
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
  return `<section class="hrsp"><h3>${name}${also}</h3>${pts.length
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
      hearing report${when?` of ${fdate(when)}`:""}. The report is the committee
      staff’s summary of the hearing, not a transcript${video
        ?"; the recording above is the hearing itself":""}.</p>
    <dl class="hrfacts">${fact("Hearing",times?`${fdate(r.heard)}, ${times}`:fdate(r.heard))}${
      fact("Members present",r.present)}${fact("Members absent",r.absent)}</dl>
    ${pos.length?`<h2>Who took a position</h2><dl class="hrfacts">${
      pos.map(p=>fact(p[0],p[1])).join("")}</dl>`:""}
    ${secs.map(s=>{
      const body=s.text?hrPlain(s.text)
        :(s.speakers||[]).map(hrSpeaker).join("");
      const empty=!(s.text||[]).length&&!(s.speakers||[]).length;
      return `<h2>${esc(s.label)}</h2>${s.text&&s.text.length
        ?`<p class="hrnote">This section is shown as the report sets it out,
          because who said which part could not be read from its layout with
          confidence.</p>`:""}${
        empty?`<p class="hrnone">${esc(s.note||"None.")}</p>`:body}`;}).join("")}
    </div></details>`;
}

function renderHearings(b,d){
  // si, because the pid was built from the video and the timestamp, so two
  // proceedings on the same recording resolving to the same second shared one
  // -- and the seek handler resolves a pid with querySelector, which returns
  // the first match. Pressing a timestamp under the second player moved the
  // first. 238 stations.
  return (d.stations||[]).length?d.stations.map((s,si)=>{
    let inner;
    // Whether this station ends up pointing at a moment. It was a list of
    // state strings kept in a second place, which is how "stated" came to be
    // marked pending while an estimate was marked done.
    let placed=false;
    // A recording we have is a recording the reader can watch, whether or not
    // we can say where in it the bill is. Pinning down start times is ongoing
    // work; sending somebody to YouTube in the meantime is a worse answer than
    // handing them the tape and saying so.
    const player=(from,stub,note)=>{
      const pid=`${esc(s.video_id)}_${si}_${Math.max(0,Math.floor(from))}`;
      return `<div class="player" data-player="${pid}">
        <button type="button" class="pstub"
          data-embed="${esc(s.video_id)}|${Math.max(0,Math.floor(from))}|${pid}"
          ><span>\u25B6</span><span>${stub}</span></button>
        <div class="pbar">
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}&t=${
             Math.max(0,Math.floor(from))}s"
             target="_blank" rel="noopener">Open on YouTube</a>
          <span class="tolnote">${note}</span></div></div>`;};
    // "stated" is "located" with the boundary in the chair's own words. It
    // was its own state string and matched no branch here, so the best data
    // this site has -- 3,829 proceedings, a median of one second -- fell
    // through to "the moment was not identified". The branch below already
    // reads start_stated and words itself accordingly; it only ever needed to
    // be reached.
    if(s.state==="located"||s.state==="stated"){
      // Open essentially AT the mark. The old lead was five minutes for an
      // estimate and 45 seconds for a quotation, on the reasoning that
      // arriving early costs only scrubbing -- but it made the commonest case
      // land the reader in the middle of the previous bill, and the page then
      // had to explain a time that was not the bill's. A boundary is timed to
      // the caption line the words begin in, so two seconds is enough not to
      // clip the first syllable and little enough to be inaudible.
      const LEAD = 2;
      const from = Math.max(Math.floor(s.start - LEAD), 0);
      // One word, and only when the placement is an inference rather than
      // something the chair said. Everything else the page used to print about
      // provenance -- the tolerance, which of the two dates it was showing,
      // "about where it ends" -- was methodology in the reader's way. What
      // matters is that clicking lands on the bill.
      const approx = s.start_stated ? "" : " approximate";
      // end_stated is no longer read here: a stated close and an inferred
      // one are both just the end now, and the page does not rank them.
      const hasend = s.end && s.end > s.start;
      placed = true;
      const pid = `${esc(s.video_id)}_${si}_${Math.floor(s.start)}`;
      // Guard on the seconds, not on the rounded string: "0 min" is truthy, so
      // a twenty-second segment printed "about 0 min".
      const span = hasend ? s.end - s.start : 0;
      const mins = Math.round(span / 60);
      const dur = mins >= 1 ? `${mins} min` : (span > 0 ? `${Math.round(span)} sec` : "");
      const range = hasend ? `${hms(s.start)}\u2013${hms(s.end)}` : `from ${hms(s.start)}`;
      inner=`<div class="player" data-player="${pid}">
        <button type="button" class="pstub" data-embed="${esc(s.video_id)}|${from}|${pid}">
          <span>▶</span><span>Play ${esc(s.what)} on this bill — ${range}${
            dur?`, about ${dur}`:""}</span></button>
        <div class="pbar">
          <button class="jump" data-seek="${pid}|${Math.floor(s.start)}">${hms(s.start)} starts</button>
          ${hasend?`<button class="jump"
            data-seek="${pid}|${Math.floor(s.end)}">${hms(s.end)} ends</button>`:""}
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}&t=${from}s"
             target="_blank" rel="noopener">Open on YouTube</a>
          ${approx?`<span class="tolnote">approximate</span>`:""}
        </div></div>`;
    }
    else if(s.state==="approximate"){
      // Open a few minutes before the scheduled time, since hearings run late
      // and never early. It is a place to start scrubbing, not a claim.
      const from=Math.max(secs(s.predicted)-300,0);
      inner=player(from,
        `Play the recording from ${hms(from)} \u2014 scheduled for ${
          esc(s.time||"this day")}, start time not identified yet`,
        "start time not identified yet")
        +`<p class="note" style="margin-top:8px">Matching proceedings to the
        moment they begin is ongoing work, and this one is not done. The
        recording is the whole sitting; hearings run behind, so the bill is
        usually after the scheduled time rather than before it.${
        s.candidate?` An automatic pass suggested ${hms(s.candidate)}, but not
        confidently enough to publish as fact.`:""}</p>`;
    }
    // else if, not if. Opening a second chain here meant every station that
    // matched the FIRST chain -- located, stated, approximate -- fell through
    // this one to the "s.video_id" catch-all below, which overwrote the inner
    // that had just been built correctly. 5,453 stations carried a real
    // timestamp the page then threw away.
    else if(s.state==="whole_video"){
      // The recording covers exactly this bill, so it plays from the start and
      // there is nothing to estimate.
      placed=true;
      const pid=`${esc(s.video_id)}_${si}_w`;
      inner=`<div class="player" data-player="${pid}">
        <button type="button" class="pstub" data-embed="${esc(s.video_id)}|0|${pid}">
          <span>&#9654;</span><span>Play the whole recording &mdash; it covers this
          bill only</span></button>
        <div class="pbar">
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}"
             target="_blank" rel="noopener">Open on YouTube</a>
          <span class="tolnote">entire recording is this bill</span></div>
        ${s.title?`<div class="pbar" style="border-top:none">
          <span style="color:var(--ink-2)">${esc(s.title)}</span></div>`:""}</div>`;
    }
    else if(s.state==="consent"){
      // Named nowhere in the recording, so it went through on the consent
      // calendar. There is no moment to point at, and saying "this bill was
      // taken up that day" over a link to nine hours of other business would
      // be worse than saying nothing.
      inner=`<p class="note">Passed on the consent calendar — adopted with the
        rest of the block, without being debated or voted on separately, so
        there is no moment in the recording to point to.
        <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}"
           target="_blank" rel="noopener">The session is here</a> if you want
        the day as a whole.</p>`;
    }
    // A RECORDING OF THAT DAY EXISTS AND WHICH ONE THIS IS WAS NOT
    // ESTABLISHED. Not the claim "approximate" makes: that one knows the tape
    // and not the minute, this one knows the day and the committee and not
    // the tape. 317 proceedings of 100,556, across 64 committee-days and 269
    // bills -- 236 of them Finance, whose divisions stream separately and
    // which the docket does not tell apart, and 81 whose scheduled minute
    // fell inside more than one stream.
    //
    // Until this branch they fell to the final else and read "No recording
    // matched to this proceeding." over a sitting that was filmed and whose
    // recordings are in this site's own index. The wording here is the same
    // honesty as "estimated within +-5 min" one level up: it says what is
    // not known, names what is, and does not resolve the uncertainty by
    // picking. The site must not choose one of these, so nothing below ranks
    // them or calls any of them likelier -- they are offered in the order
    // the matcher found them.
    //
    // Numbered rather than titled: proceedings.csv carries the ids, which are
    // addressable; the manifest's `candidates` column carries the titles and
    // they are for a person reading the manifest.
    else if(s.state==="candidates"&&(s.candidate_ids||[]).length){
      const ids=s.candidate_ids;
      const links=ids.map((v,i)=>`<a href="https://www.youtube.com/watch?v=${
        esc(v)}" target="_blank" rel="noopener">Recording ${i+1}</a>`
        ).join(" · ");
      // Spelled, because the sentence is prose and "there are 3 recordings"
      // beside "there are two recordings" reads as two voices. Two and
      // three are the only counts there are -- 213 and 104 of the 317 -- and
      // the digit is there for a fourth that has never happened. There is no
      // one-recording case at all: build_manifest writes this column only
      // where more than one recording of the committee exists that day, and
      // a lone recording is simply matched.
      const n=["","one","two","three","four","five"][ids.length]||ids.length;
      inner=`<div class="vbox"><p><b>This committee was recorded that day.
        Which of its recordings is this sitting has not been established.</b>
        There are ${n} recordings of it for that day, nothing in the record
        says which one took this bill up, and this site will not pick one.
        They are all here: ${links}</p>
        <p style="margin-top:8px">A committee can sit in divisions that stream
        separately, and a scheduled time can fall inside more than one
        recording; in neither case does the record say which one the bill was
        taken up in. The day, the committee and the recordings are all on
        record. Which goes with which is not, and a guess here would read as
        a fact.</p></div>`;
    }
    else if(s.state==="floor_precise"||s.state==="floor_stated"){
      // A roll call closes the item, so its timestamp is the END of the
      // debate, good to a few seconds. The window opens at the PREVIOUS bill's
      // last vote, and everything in between is other bills -- on one real
      // session that gap is 37 minutes. Landing the reader there means 37
      // minutes of the wrong debate before the right one starts.
      //
      // So the player opens shortly before the vote, which is certainly this
      // bill, and the window is offered as a jump for anyone who wants the
      // whole span. Ten minutes covers all but the longest floor debates, and
      // it never runs back past the window.
      // Where the clerk actually opened it, if that was found. The window is
      // the previous bill's roll call and can be half an hour of other
      // business earlier, so it is only a fallback -- and ten minutes before
      // the vote is a worse fallback still, just a less wrong one.
      // floor_stated has a start the clerk read (the committee report) and an
      // end the chair said (the result), and no roll call at all. Everything
      // below is the same except what may be claimed about the end: "timed
      // to the second" is true of a roll call clock and false
      // of a caption line, and the difference is the whole point of the
      // wording on this site.
      placed=true;
      const voted=s.state==="floor_precise";
      // Guard on the field, not the coerced value. `||0` turned a missing
      // window into a button reading "00:00:00 window opens" that seeked to
      // the gavel-in -- the absence of data printed as a timestamp. A
      // window_start of exactly 0 is real for the first roll call of a
      // session, so the test has to be against null, not against zero.
      const ws=s.window_start!=null?Math.max(Math.floor(s.window_start),0):null;
      // One number, shown and used. The header said debate_start while the
      // player seeked to debate_start-15 and the jump buttons showed two other
      // values again -- four numbers for one moment, and a reader has no way
      // to tell which is the claim.
      const from=s.debate_start!=null
        ? Math.max(Math.floor(s.debate_start),0)
        : Math.max(ws,Math.floor(s.debate_end)-600);
      const pid=`${esc(s.video_id)}_${si}_f${Math.floor(s.debate_end)}`;
      inner=`<div class="player" data-player="${pid}">
        <button type="button" class="pstub" data-embed="${esc(s.video_id)}|${from}|${pid}">
          <span>▶</span><span>${s.debate_start!=null
            ? `Play from ${hms(from)}, where the clerk takes it up`
            : `Play the floor session from ${hms(from)}`} — debate on
          this bill ends at ${hms(s.debate_end)}</span></button>
        <div class="pbar">
          ${ws!=null&&ws<from?`<button class="jump" data-seek="${pid}|${ws}">${
            hms(ws)} window opens</button>`:""}
          <button class="jump" data-seek="${pid}|${Math.floor(s.debate_end)}">
            ${hms(s.debate_end)} ${voted?"the vote":"ends"}</button>
          <a href="https://www.youtube.com/watch?v=${esc(s.video_id)}&t=${from}s"
             target="_blank" rel="noopener">Open on YouTube</a>
          <span class="tolnote">${voted
            ? (s.debate_start!=null
               ? "the clerk takes it up here; the vote is timed to the second"
               : "vote timed to the second")
            : "the chair opens and closes it; no roll call on this one"
            }</span></div>
        ${(s.motions||[]).length?`<div class="pbar" style="border-top:none">
          <span style="color:var(--ink-2)">Motions: ${s.motions.map(esc).join(" · ")}</span>
          </div>`:""}</div>`;
    }
    // A voice or division vote leaves no roll call to time the end, but the
    // clerk still opened the item and segment_markers still heard it. 393 of
    // these carried debate_start and were being told they had no moment. Its
    // own arm rather than the branch above, which dereferences debate_end in
    // three places and would print "ends at 00:00:00".
    else if(s.state==="floor_dated"&&s.debate_start!=null){
      placed=true;
      const from=Math.max(Math.floor(s.debate_start),0);
      inner=player(from,
        `Play from ${hms(from)}, where the clerk takes it up`,
        "the clerk takes it up here; no roll call to time the end")
        +`<p class="note" style="margin-top:8px">A voice or division vote leaves
        no timestamp for the end, so this points at the opening only.</p>`;
    }
    else if(s.state==="floor_dated")inner=player(0,
      "Play the floor session \u2014 this bill was taken up that day",
      "moment not identified")
      +`<p class="note" style="margin-top:8px">A voice or division vote leaves no
      timestamp in the record, so there is nothing to point at within the
      sitting. The whole session is here.</p>`;
    // A HEARING DATED BY THE SENATE COMMITTEE'S OWN REPORT, where the docket
    // has no Senate hearing of the bill that day (report_station, in
    // build_site_v2). Shown, as the person decided on 24 September, and saying
    // where the date comes from: the report's date and the docket's are both
    // the General Court's, and this site does not say which one is right.
    else if(s.dated_by==="report")inner=`<div class="vbox"><p><b>Dated by the
      committee&rsquo;s own report.</b> The docket records no Senate hearing of
      this bill on this day${(s.docket_heard||[]).length?`; it records one on
      ${s.docket_heard.map(esc).join(" and ")}`:""}. This is the date the Senate
      committee&rsquo;s hearing report gives, and the report is below as the
      Senate filed it. No recording is linked to it.</p></div>`;
    // WHERE THIS SITE'S RECORDINGS BEGIN, not where recording began. The
    // House Calendars of 2013-2019 announce hearings streamed live, and none
    // of those is on either YouTube channel, so "no recording exists" and
    // "not livestreamed before 2020" were both claims the record contradicts.
    // The month is about_figures.STREAM_START_WORDS, and preflight holds the
    // two to each other.
    else if(s.state==="prestream")inner=`<div class="vbox"><p><b>No recording to link.</b>
      The General Court&rsquo;s YouTube channels, where this site finds its recordings, begin in May 2020, and this sitting was earlier.</p></div>`;
    // Defensive: if a proceeding carries a video id but an unrecognised state,
    // still offer the recording. Saying "no recording" when one is right there
    // is the worst possible failure -- it hides working data and looks like the
    // site has less than it does.
    else if(s.video_id)inner=player(0,
      "Play the recording \u2014 the moment was not identified",
      "moment not identified")
      +`<p class="note" style="margin-top:8px">This proceeding has a recording but
      no timestamp yet. That work is ongoing.</p>`;
    else inner=`<div class="vbox"><p>No recording matched to this proceeding.</p></div>`;
    // Was a second list of state strings, which never gained "stated" or
    // "floor_stated" -- so the site's best-evidenced proceedings wore the
    // pending dot while an unlocated estimate wore the finished one. It now
    // follows the branch that actually ran.
    return `<div class="stn ${placed?"done":"pend"}">
      <div class="w">${esc(s.when)}${s.time?" at "+esc(s.time):""}${s.venue?" · "+esc(s.venue):""}</div>
      <div class="t">${esc(stationTitle(b,s))}</div>${
        signins(s.testimony)}${inner}${(s.reports||[]).map(r=>
          hearingReport(r,inner.includes('class="player"'))).join("")}</div>`;}).join("")
    :`<p class="note">No scheduled proceedings on file.</p>`;
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
const reportCount=d=>(d.reports||[]).reduce((n,r)=>n+((r.reports||[]).length),0)
                     +(d.docket_reports||[]).length;

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
      records, on ${esc(fdate(a.date))}: <em>${esc(a.text)}</em></p>`).join("");
  // The day the committee signed its report, where the docket states it; the
  // day the calendar carrying it was published, where it does not. Saying
  // which is the difference between a fact and a stand-in for one.
  const when=r=>!r.date?"":`<span class="secsub">${esc(fdate(r.date))}</span>`
      +(r.dated==="printed"?` <span class="repas">as printed</span>`:"");
  const cited=r=>{
    if(!r.cite)return "";
    // The House's source string IS the citation -- "House Calendar 51, 2025".
    // The Senate's reports come from the General Court's database and their
    // source names that, which is not what a reader wants beside a committee's
    // name; the docket's own citation for the same report is.
    const t=esc(r.body==="S"?r.cite:(r.source||r.cite));
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
  const head=(r,cmte,body)=>`<div class="rephead">
      ${[body,cmte].filter(Boolean).length
        ? `<h2>${esc([body,cmte].filter(Boolean).join(" "))} committee</h2>`:""}
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
    const committeeTally=e=>{
      if(e.vote_yeas==null&&!tally)return "";
      const y=e.vote_yeas!=null?e.vote_yeas:tally.vote_yeas;
      const nn=e.vote_nays!=null?e.vote_nays:tally.vote_nays;
      const full=`Committee vote ${y}–${nn}`;
      return `<span class="cvote" title="${full}">${
        divided?(e.side==="Minority"?nn:y):`${y}–${nn}`}</span>`;
    };
    const cmte=((r.reports||[])[0]||{}).committee||"";
    const blocks=(r.reports||[]).map(e=>{
      const rec=recFor(r,e.side);
      return `<div class="repblock">
        <div class="repline">
          <span class="secsub">${esc(e.side)}</span>
          ${committeeTally(e)}
          ${rec?`<span class="cstat ${recColour(rec)}">${esc(rec)}</span>`:""}</div>
        <p class="repby">${esc(e.author)}</p>
        ${e.amendment?`<p class="note" style="margin:0 0 7px">Amendment ${
          esc(e.amendment)}.</p>`:""}
        ${(e.text||"").trim()
          ? `<p style="font-family:var(--serif);font-size:16px;line-height:1.6;margin:0">${rsa(esc(e.text))}</p>`
          // 350 of the Senate's 1,446 reports carry no reasoning at all. That
          // is a fact about the report, not a gap in the site, and saying so
          // is better than an empty space under a heading.
          : `<p class="note" style="margin:0">This report records the
             recommendation and the vote, and gives no reasoning.</p>`}
        </div>`;}).join("");
    return between(r.date)+rep(head(r,cmte,r.body==="S"?"Senate":"House"),
      (divided?`<p class="note">The committee split. Both reports are printed
        below in the committee's own words.</p>`:"")+blocks);}).join("");

  // Reports the docket records and this site has no written text for. Once the
  // Senate's own reports came out of the General Court's database, 964 of
  // these turned into written blocks above and what is left is the remainder:
  // a House report printed in a calendar not read in yet, or a Senate report
  // the database does not carry.
  const docket=(d.docket_reports||[]).map(r=>{
    const vote=r.vote_yeas!=null&&r.vote_nays!=null
      ? `<span class="cvote" title="Committee vote ${r.vote_yeas}–${r.vote_nays}"
          >${r.vote_yeas}–${r.vote_nays}</span>` : "";
    // The same three-part heading the written reports use -- who, by what vote,
    // for what motion. The Senate files one report and does not label it, and
    // leaving the label out left a bare "3-2" hanging where every block above
    // it reads "MAJORITY 10" or "COMMITTEE 17-0".
    const amd=r.amendment?`<p class="note" style="margin:0 0 7px">Amendment ${
      esc(r.amendment)}${r.new_title?", which also changes the bill’s title":""}.</p>`:"";
    return between(r.date)+rep(head(r,r.committee,r.body==="S"?"Senate":"House"),
      `<div class="repline">
        <span class="secsub">${esc(r.side||"Committee")}</span>${vote}
        <span class="cstat ${recColour(r.recommendation)}">${esc(r.recommendation)}</span></div>
      ${amd}
      <p class="note" style="margin:var(--sp-5) 0 0">${r.body==="S"
        ? "The written report for this one is not on the site; this is what the docket records of it."
        : "The calendar carrying this report has not been read into the site yet, so only what the docket states is shown."}</p>`);}).join("");

  return veto(d)+((written||docket)?written+docket
    :`<p class="note">No committee report on file. A report is recorded in the docket
      when a committee reports the bill out, and the reasoning behind it is printed
      in the House Calendar or filed with the Senate; neither has happened here yet.</p>`);
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
    <h2 class="amdsec">The governor&rsquo;s veto message</h2>
    ${v.text.map(p=>`<p>${esc(p)}</p>`).join("")}
    <p class="vsig">${esc(v.governor||"")}${
      v.date?` <span class="secsub">${esc(fdate(v.date))}</span>`:""}</p>
    ${v.date?`<p class="note" style="margin:6px 0 0">The message carries its own
      date, which is the day the governor signed it. The docket records the day
      the veto reached the House, and on three of these the two are days
      apart.</p>`:""}
    <p class="src">Read into the House and printed in ${cite}. The docket
      records that a bill was vetoed and the day it happened; the reasons are
      only in the message.</p>
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
  const spBlock=ch=>{const l=spAll.filter(s=>chOf(s)===ch);return l.length
    ?`<h2 class="spgrp">${CHNAME[ch]} <span>${l.length}</span></h2>
      <div class="chosen">${l.map(pill).join(" ")}</div>`:"";};
  const spRest=spAll.filter(s=>!["H","S"].includes(chOf(s)));
  // A count per party, and nothing said about it. Sorted by party code, so the
  // order is fixed rather than a ranking by size.
  const pc={};
  spAll.forEach(s=>{const k=String(s.party||"").toUpperCase().slice(0,1);
    if(k)pc[k]=(pc[k]||0)+1;});
  const spParty=Object.keys(pc).sort().map(k=>
    `<span title="${esc(PARTY_NAME[k]||k)}">${pc[k]} ${esc(k)}</span>`).join(" \u00b7 ");
  const sp=spAll.length?`
    <p class="spcount">${spAll.length} Sponsor${spAll.length===1?"":"s"}${
      spParty?` \u00b7 ${spParty}`:""}</p>
    ${spBlock(origin)}${spBlock(origin==="S"?"H":"S")}
    ${spRest.length?`<h2 class="spgrp">Chamber not on file <span>${spRest.length}</span></h2>
      <div class="chosen">${spRest.map(pill).join(" ")}</div>`:""}`:"";
  // WHERE THE NAMES WERE READ. Before 2023 the only list on this site is the
  // sponsor line printed on the bill's own text (text_sponsors.py): the first
  // name there is taken as prime, and a name matched to nobody who cast a roll
  // call that term is shown as it is printed, without a party.
  const fromText=spAll.length&&spAll.every(s=>s.source==="bill text");
  const asPrinted=fromText&&spAll.some(s=>!s.member_id);
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
        the bill's text, where the first name is the prime sponsor.${asPrinted
        ?` A name without a party is shown as the text prints it: it could not
          be matched to one member who voted that term.`:""}</p>`:""}`;
}

// Amendments, in the order the docket took them up. A committee amendment
// is considered before any floor amendment, and where two touch the same
// section the later one governs -- so the sequence carries meaning, and it
// is shown as the record has it rather than grouped or sorted.
// The fiscal note, as the table the bill's own PDF prints. A figure sits
// under a year only where the row has one figure per year; where it has fewer
// the row spans, because which years the second figure covers is not stated
// and putting it under one of them would be inventing an answer.
function fiscalTable(f){
  if(!f)return "";
  const table=t=>{
    if(t.raw)return `<div class="fnraw">${t.caption?`<h4>${esc(t.caption)}</h4>`:""}
      ${t.raw.map(l=>`<p>${esc(l)}</p>`).join("")}</div>`;
    const n=(t.years||[]).length;
    return `<div class="fnwrap"><table class="fn">
      ${t.caption?`<caption>${esc(t.caption)}</caption>`:""}
      <thead><tr><th></th>${t.years.map(y=>
        `<th scope="col">${esc(y)}</th>`).join("")}</tr></thead>
      <tbody>${t.rows.map(r=>`<tr><th scope="row">${esc(r.label)}</th>${
        r.span
          ? `<td colspan="${n}">${esc(r.values.join(" \u00b7 "))}</td>`
          : r.values.map(v=>`<td>${esc(v)}</td>`).join("")
      }</tr>`).join("")}</tbody></table></div>
      ${t.footnote?`<p class="src">${esc(t.footnote)}</p>`:""}`;
  };
  return `<section class="fnsec"><h2 class="amdsec">Fiscal impact</h2>
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
        return `<section class="btsec"><h2 class="amdsec">Bill text</h2>
        <p class="btwhat">The bill and its amendments, as the General Court publishes them. Everything above is this site’s account of the record; this is the document.</p>
        <details class="btdoc"${shut?"":" open"}><summary><span class="shut">Show ${
          what}</span><span class="open">Hide ${what}</span></summary>${
        renderBillText(b,d,rsa)}</details></section>`;}

function renderBillText(b,d,rsa){
  const brackets=(s)=>s.replace(/\[([^\]]{1,400})\]/g,
    (_,inner)=>`<del class="cut" title="removed by this amendment">${inner}</del>`);
  const amds=(d.amendments||[]).map(x=>{
    const who=x.mover||x.proposed_by||"";
    const state=x.adopted===true?"adopted":x.adopted===false?"rejected":"";
    return `<div class="amd">
      <div class="amdhead"><span class="amdn">${esc(x.num)}</span>
        <span class="amdk">${esc(x.kind||"Amendment")}</span>
        ${state?`<span class="cstat ${state==="adopted"?"s-law":"s-done"}">${state}</span>`:""}
        <span class="amdd">${x.date?esc(fdate(x.date)):""}${
          AVK[x.vote_kind]?` \u00b7 ${AVK[x.vote_kind]}`:""}</span></div>
      ${who?`<p class="amdby">${esc(who)}</p>`:""}
      ${(x.targets||[]).length?`<p class="amdt">Changes ${
        x.targets.map(v=>`<span class="tgt">${esc(v)}</span>`).join(" ")}</p>`:""}
      ${(x.supersedes||[]).length?`<p class="amdsup">Later than ${
        x.supersedes.map(s=>`${esc(s.num)} (${s.shared.map(esc).join(", ")})`).join(", ")
        }, so where they change the same thing this one governs.</p>`:""}
      ${x.text
        ? `<details class="amdtext"><summary>Read the amendment</summary>
             <p>${brackets(rsa(esc(x.text)))}</p>
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
    const html=brackets(rsa(esc(line)));
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
    <div class="btver"><span class="btv">${esc(bt.version||"Version not stated")}</span>
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
      <div class="billbody">${billLines(bt.body||"")}</div></div>
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

function renderDocuments(b,d){
  // The status fields the site quotes, with the documents it quotes them
  // alongside. This is the provenance tab, and the table is provenance: nine
  // values taken from the General Court's own status page rather than worked
  // out from anything.
  // factsTable used to open this tab with the status page's own fields --
  // status, the date introduced, the committee code. Every one of them is
  // already on the summary, in a sentence, above the tab strip.
  return ((d.documents||[]).length
      ? `<p class="note">Everything below is published by the General Court. This
         site quotes and summarises these; they are the record itself.</p>
         <ul class="docs">${d.documents.map(x=>{
           // THE ACTIONS THIS CITATION IS THE RECORD OF. The docket carries
           // the same citation on the event it belongs to, so the two are
           // joined on it -- and a citation covering several actions names
           // all of them, because it is the record of all of them. Where
           // nothing matches, DOCWHAT's sentence stands as it always did.
           const acts=(d.events||[]).filter(e=>e.cite&&e.cite===x.label);
           const src=x.kind==="record"?citeSource(x.label):"";
           const when=acts.length?fdate(acts[0].date):"";
           const of=[src,when].filter(Boolean).join(" \u00b7 ");
           return `<li class="doc doc-${esc(x.kind)}">
           <a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.label)}</a>
           ${of?`<span class="docof">${esc(of)}</span>`:""}
           ${acts.length
             ? `<span class="docacts">${acts.map(e=>esc(e.text)).join("<br>")}</span>`
             : `<span>${DOCWHAT[x.kind]||""}</span>`}</li>`;
         }).join("")}</ul>`
      : `<p class="note">No official documents on file for this bill yet. The
         bill text and docket links come from the General Court's status page,
         which is fetched separately.</p>`);
}

// The tabs, and one call per pane. Everything this reads is either a
// parameter or the return value of a call made on the line that uses it,
// so there is no declaration here whose order could be got wrong.
// ============================================================== versions ==
//
// WHAT EACH AMENDMENT CHANGED. A bill is reprinted at every stage and the
// changes are usually small -- HB650's first amendment turned one word,
// "unencumbered" into "unobligated" -- which is exactly what nobody finds by
// reading two seven-thousand-character documents side by side.
//
// Three files rather than one, and each fetched only when it is picked: the
// index (median 1.1 KB), a version's text, and one comparison's detail. One
// file held all of it at first and HB2, the budget with 54 versions, came to
// 11.4 MB.
const VERS = {};                       // bill -> the index, once fetched
const VTEXT = {};                      // url -> text, once fetched
const VPICK = {};                      // bill -> which version is showing
const VMODE = {};                      // bill -> "text" or "changes"

function verKey(b){ return `${b.year||yearOf(b.id)}/${b.id}`; }

// IS THERE AN INDEX TO ASK FOR. build_bill_versions writes
// /versions/<year>/<ID>.json for a bill with more than one version or with
// amendments, and for no other -- 1,087 of the 33,030 records that draw a
// Bill Text tab. The tab itself is drawn far more often than that, because a
// bill with one version and no amendments still has TEXT, and that text is in
// the record already.
//
// Without this the pane asked for the index on all 33,030 and printed "The
// versions of this bill could not be loaded. HTTP 404" on the 29,841 where
// there was never going to be one -- in a warning box, above the bill text
// that had loaded fine. Checked against the built site: this predicate is
// true for exactly the bills that have the file, 0 either way.
function hasVersionIndex(d){
  return !!d && (((d.nver || 0) > 1) || !!(d.namd || 0));
}

// WHAT ONE PRINTING DID TO THE NEXT, DRAWN ON THE DOCUMENT rather than beside
// it. The older view excerpts the changed passages with context and elides the
// rest, which answers "what changed" but loses where. This keeps the bill's
// own paragraphs and marks the change in place, so a reader sees the section
// it happened in.
//
// TWO MARKINGS, TWO VIEWS, NEVER OVERLAID. The Full text view shows the
// COURT's marking -- what the bill does to existing law. This shows the
// AMENDMENT's -- what this printing did to the one before it. They are
// different questions about the same words, and drawing both at once would
// make a passage that is added-by-the-bill and removed-by-an-amendment
// unreadable, so this view reads the block's plain text and ignores the
// per-run roles.
function vmarked(bs,ms){
  const by={};
  ms.forEach(m=>{(by[m[0]]=by[m[0]]||[]).push(m);});
  const out=[];let skipped=0;
  const gap=()=>{
    if(!skipped)return;
    out.push(`<p class="vgapn">${skipped.toLocaleString()} paragraph${
      skipped===1?"":"s"} unchanged</p>`);
    skipped=0;
  };
  bs.forEach((bl,bi)=>{
    const mine=by[bi];
    if(!mine){if(bl.k!=="head"&&bl.k!=="legend")skipped++;return;}
    gap();
    const t=(bl.runs||[]).map(r=>r[1]).join("");
    // A removal is anchored at the same offset as the insertion that replaces
    // it, so the struck words are drawn first and read as "this became that".
    mine.sort((x,y)=>(x[1]-y[1])||(x[3]==="-"?-1:1));
    let at=0,html="";
    mine.forEach(m=>{
      const s=m[1],e=m[2],op=m[3];
      if(s>=at)html+=esc(t.slice(at,s));
      if(op==="-"){html+=`<del class="vdel">${esc(m[4]||"")}</del>`;
        at=Math.max(at,s);}
      else{html+=`<ins class="vins">${esc(t.slice(s,e))}</ins>`;
        at=Math.max(at,e);}
    });
    html+=esc(t.slice(at));
    out.push(`<p class="vblk vblk-${esc(bl.k||"ln")}">${html}</p>`);
  });
  gap();
  return `<div class="vdoc">${out.join("")}</div>`;
}

function renderVersions(b,d){
  const key=verKey(b), ix=VERS[key];
  // Nothing to load, so nothing to say about loading it. The bill's own text
  // is rendered below this pane from the record, which is where it has always
  // come from for these bills; an empty pane leaves that as the whole answer
  // rather than putting a failure notice on top of it.
  if(!hasVersionIndex(d))return "";
  if(!ix)return `<p class="spin">Loading the versions…</p>`;
  if(ix._error)return `<p class="note">The versions of this bill could not be
    loaded. ${esc(ix._error)}</p>`;
  const vs=ix.versions||[], amds=ix.amendments||[];
  // THE CURRENT VERSION BY DEFAULT, which is the last one the record has.
  if(VPICK[key]===undefined)VPICK[key]=vs.length?vs.length-1:0;
  const mode=VMODE[key]||"changes";
  const i=Math.min(VPICK[key],Math.max(0,vs.length-1));

  // A group of toggle buttons, not a tablist: it declared role="tablist" with
  // no role="tab" inside, which a screen reader announces as an empty list of
  // tabs, and no key handler moved through it.
  const vbtn=(v,j)=>`<button class="vbtn${j===i?" sel":""}" data-ver="${esc(key)}|${j}"
      aria-pressed="${j===i?"true":"false"}">${esc(v.title)}<i>${
      esc((v.date||"").split(" ")[0])}</i></button>`;

  // NO BARS. There used to be a proportional bar between each pair of
  // versions, drawn to the bill at its longest, showing how many words went
  // out and how many came in. Asked for in these terms on 20 September: "I
  // don't think the bars help, I think they're visual clutter that gets in
  // the way of seeing the amendment itself."
  //
  // That is right, and the reason is worth keeping rather than just the
  // instruction. A bar answers "how much changed" with a shape. The question
  // a reader of this tab actually has is "what changed", and since the
  // comparison began drawing itself on the bill's own paragraphs that
  // question is answered by the document one click away. The bar was a
  // summary standing in front of the thing it summarised.
  //
  // WHAT SURVIVES IT, because the bars were carrying two facts and only one
  // was decoration. The exact word counts are still stated -- "+180 -70 words
  // against As Introduced" in the line below -- because those are the record
  // and they were always the honest half. What is gone is the proportion, the
  // scale sentence that had to explain the denominator, and the six-row
  // ordered list that existed to hang them on.
  //
  // So the picker is the row of buttons it used to fall back to, in every
  // case rather than only when a word count was missing.
  const picker=!vs.length?"":
    `<div class="vpick" role="group" aria-label="Versions of this bill's text">${
        vs.map(vbtn).join("")}</div>`;

  // The step that produced the version being shown, if there is one.
  const step=(ix.steps||[]).find(s=>s.to===i);
  const toggle=step?`<div class="vmode">
    <button class="vtog${mode==="changes"?" sel":""}" data-vmode="${esc(key)}|changes">What changed</button>
    <button class="vtog${mode==="text"?" sel":""}" data-vmode="${esc(key)}|text">Full text</button>
    <span class="vcount">+${step.added} \u2212${step.removed} words against
      ${esc((vs[step.from]||{}).title||"the version before")}</span></div>`
    : `<p class="note">This is the first version the record has, so there is
       nothing before it to compare.</p>`;

  let body="";
  if(step&&mode==="changes"){
    const sf=VTEXT[step.runs_url];
    const vb=vs[i]||{};
    const doc=vb.blocks_url?VTEXT[vb.blocks_url]:undefined;
    // THE PAYLOAD IS AN OBJECT NOW, and an array before this shipped. Both are
    // handled because a reader's browser may hold either: the file changed
    // shape and a cached copy of the old one is still a perfectly good diff.
    const rs=sf&&!Array.isArray(sf)?(sf.runs||null):(Array.isArray(sf)?sf:null);
    const mk=sf&&!Array.isArray(sf)?(sf.marks||null):null;
    // MARKS WHEN BOTH HALVES ARE HERE, the excerpt otherwise. The marks are
    // positions in the blocks file, so without the document they point at
    // nothing -- and a version too old to have one still has its runs.
    const onDoc=mk&&mk.length&&Array.isArray(doc)&&doc.length;
    body=sf===undefined?`<p class="spin">Loading what changed…</p>`
      :onDoc?vmarked(doc,mk)
      // Still waiting on the document, but the excerpt is already here: draw
      // it rather than a spinner, because it answers the question and the
      // better view can replace it when it arrives.
      :Array.isArray(rs)?`<div class="vdiff">${rs.map(([op,txt])=>
          op==="~"?`<span class="vskip">${esc(txt)} words unchanged</span>`
          :op==="+"?`<ins>${esc(txt)}</ins>`
          :op==="-"?`<del>${esc(txt)}</del>`
          :`<span>${esc(txt)}</span>`).join("")}</div>`
      :`<p class="note">That comparison could not be loaded.</p>`;
  }else{
    // THE BILL AS THE COURT SET IT, with the Court's own marking of what it
    // adds to and removes from existing law. A New Hampshire bill is an edit
    // to the statute -- added matter in bold italics, removed matter in
    // brackets and struck through -- and the plain text column the site used
    // to read had that flattened out of it. The blocks file keeps it.
    //
    // THE BRACKETS STAY VISIBLE and the struck text is struck as well, which
    // is belt and braces on purpose: they are two encodings of one fact in
    // the source, a reader who cannot see the strike still reads the
    // brackets, and printing the Court's own convention is the honest thing
    // to show for a document this page is quoting rather than paraphrasing.
    const vv=vs[i]||{};
    const u=vv.blocks_url||vv.text_url;
    const got=u?VTEXT[u]:null;
    const isBlocks=Array.isArray(got)&&got.length&&got[0]&&got[0].runs;
    body=got===undefined?`<p class="spin">Loading the text…</p>`
      :isBlocks?`<div class="vdoc">${got.map(bl=>
          `<p class="vblk vblk-${esc(bl.k||"ln")}">${(bl.runs||[]).map(
            ([role,t])=>role==="add"?`<ins class="vins">${esc(t)}</ins>`
              :role==="cut"?`<del class="vdel">${esc(t)}</del>`
              :esc(t)).join("")}</p>`).join("")}</div>`
      :typeof got==="string"?`<pre class="vtext">${esc(got)}</pre>`
      // An empty array is a blocks file that parsed to nothing, which is a
      // different failure from a fetch that did not arrive and says so.
      :Array.isArray(got)?`<p class="note">The text of this version is on
         file but could not be read into paragraphs.</p>`
      :`<p class="note">That text could not be loaded.</p>`;
  }

  const amdblock=amds.length?`<h2 class="amdsec">The amendments themselves</h2>
    <p class="note">The General Court publishes the text of each amendment as
    its own document, naming the statute it amends and what it replaces. These
    are those, not versions of the bill.</p>
    <ul class="vamds">${amds.map((a,j)=>`<li><button class="link"
      data-vamd="${esc(key)}|${j}">Amendment of ${esc((a.date||"").split(" ")[0])}</button>
      <span class="dim">${(a.chars||0).toLocaleString()} characters</span>${
      VTEXT[a.text_url]!==undefined
        ? `<pre class="vtext">${esc(String(VTEXT[a.text_url]))}</pre>` : ""}</li>`
      ).join("")}</ul>`:"";

  return picker+toggle+body+amdblock;
}

// Fetch whatever the current view needs and redraw when it lands. Everything
// already here is used from the cache; nothing is asked for twice.
function needVersions(b){
  const key=verKey(b);
  // The record is the authority, when it has arrived. On a bill's own page it
  // is inline and this is answered before the first paint; reached from the
  // search list it arrives with openBill, and the repaint that follows calls
  // through here again. Either way no request is made for a file that the
  // record says does not exist.
  const rec=detail[dkey(b.id)];
  if(rec && !hasVersionIndex(rec))return;
  if(VERS[key]===undefined){
    VERS[key]=null;
    fetch(DATA(`versions/${key}.json`))
      .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
      .then(j=>{VERS[key]=j;repaint();wantVersionBody(b);})
      .catch(e=>{VERS[key]={_error:e.message||String(e)};repaint();});
    return;
  }
  if(VERS[key])wantVersionBody(b);
}

function wantVersionBody(b){
  const key=verKey(b), ix=VERS[key];
  if(!ix||ix._error)return;
  const i=VPICK[key]===undefined?(ix.versions||[]).length-1:VPICK[key];
  const mode=VMODE[key]||"changes";
  const step=(ix.steps||[]).find(s=>s.to===i);
  // THE BLOCKS FILE WHERE THERE IS ONE, and the plain text where there is not.
  // build_bill_versions writes blocks_url BESIDE text_url rather than in place
  // of it, so this is the only line that has to know the difference and a
  // version without one behaves exactly as it always did.
  const v=(ix.versions||[])[i]||{};
  // WHAT CHANGED NEEDS TWO FILES NOW. The step file says WHERE the change is
  // and the version's blocks file is the document those positions are in.
  // Both are asked for together; whichever lands second triggers the repaint
  // that draws them, and if the blocks never arrive the step file's runs
  // still render the excerpt view this always had.
  const need=(step&&mode==="changes")
    ? [step.runs_url, v.blocks_url].filter(Boolean)
    : [v.blocks_url||v.text_url];
  need.forEach(url=>{
    if(!url||VTEXT[url]!==undefined)return;
    VTEXT[url]=undefined;
    const json=url.endsWith(".json");
    fetch(DATA(url.replace(/^\//,"")))
      .then(r=>r.ok?(json?r.json():r.text()):Promise.reject(new Error("HTTP "+r.status)))
      // THE WHOLE OBJECT FOR A STEP FILE, where this used to keep x.runs and
      // discard every other key. A step file carrying marks and no runs would
      // have yielded [] under the old line -- an empty comparison, drawn with
      // no error, on all 2,582 steps. Blocks stay an array because that is
      // what they are; a step is an object because it has more than one part.
      //
      // The alternative -- renaming text_url to point at JSON -- would have
      // sent 3,731 plain texts through r.json() and blanked the Full text
      // view, which is the mode a reader lands on when a version has no step
      // before it. text_url still means what it always meant.
      .then(x=>{VTEXT[url]=json?(x.blocks||x):x;repaint();})
      .catch(()=>{VTEXT[url]=null;repaint();});
  });
}

function renderDetail(b,d){
  const rsa=makeRsa(d);
  // Below the tabs, outside every pane, and only in the expanded view. The
  // bill text used to be assembled into a const above this template while
  // its own dependencies were declared below it, which threw the moment a
  // bill was focused -- a refresh on a bill page reporting that its detail
  // would not load when the file had arrived fine. It is a call now, made
  // where it is used, so there is nothing left to order wrongly.
  const btsec=(focused===b.id&&hasVersionIndex(d)&&((d.billtext&&d.billtext.body)
    ||(d.amendments||[]).length))
    ? billTextSection(b,d,rsa)
    : "";

  // BILL TEXT SITS SECOND, and the data-t numbers are deliberately NOT
  // renumbered. They are the tab's identity: PAGE_TAB holds one, the pane
  // carries the matching one, and a bookmark or a back button restores by it.
  // Renumbering to match the new order would silently repoint every saved
  // tab -- somebody's link to the Votes tab would open Bill Text. So the
  // order here is the DOM order, which is what a reader and the keyboard both
  // follow, and 6 stays 6.
  // A BILL WITH ONE VERSION STILL HAS A TEXT. This asked only whether there
  // was something to DIFF -- more than one version, or an amendment -- so a
  // bill whose text the archive holds and which was never amended offered no
  // tab at all. Sampled over the built pages: 291 of 291 texted bills in 2012,
  // 292 of 292 in 2020, and 159 of 295 in the CURRENT term, which is where it
  // stops being an archive problem.
  //
  // The text was never lost -- the block below the tabs renders it, and that
  // placement is deliberate for the very long documents. What was missing is
  // the tab a reader looks for, so the test is now "is there a text", with the
  // version count still shown only when there is more than one to count.
  const btHas=(d.nver||0)>1||(d.namd||0)||!!(((d.billtext||{}).body||"").trim())
    ||!!(d.amendments||[]).length;
  const btTab=btHas
    ? `<button class="tab" role="tab" id="tab_${b.id}_6" aria-controls="pane_${b.id}_6"
        aria-selected="false" data-t="6">Bill Text${d.nver>1?` (${d.nver})`:""}</button>`
    : "";
  const btPane=btHas
    ? `<div class="pane" role="tabpanel" id="pane_${b.id}_6" aria-labelledby="tab_${b.id}_6"
        tabindex="0" data-t="6" hidden>${hasVersionIndex(d)?renderVersions(b,d):billTextSection(b,d,makeRsa(d))}</div>`
    : "";

  return `<div class="tabs" role="tablist">
    <button class="tab" role="tab" id="tab_${b.id}_0" aria-controls="pane_${b.id}_0" aria-selected="true" data-t="0">Summary</button>
    ${btTab}
    <button class="tab" role="tab" id="tab_${b.id}_1" aria-controls="pane_${b.id}_1" aria-selected="false" data-t="1">Votes${
        // What the pane draws, not the index row's count. b.nrc is the roll
        // calls that are not procedural; the pane draws d.rollcalls, which
        // adds the docket's voice and division votes. The two disagreed on
        // 2,011 of the current term's 2,234 bills -- mostly bills whose only
        // votes were voice votes, which showed "Votes" with nothing beside
        // it and 3 sections beneath.
        (d.rollcalls||[]).length?` (${d.rollcalls.length})`:""}</button>
    <!-- HEARINGS, NOT VIDEOS. The tab lists a bill's sittings -- the date, the
         time and the room -- and a recording where one exists. Recordings
         begin on 14 May 2020, so for fifteen of the nineteen terms the tab was
         headed "Videos" and every entry under it read "No recording exists".
         The sittings are the content and the video is the bonus, so the label
         now says what is always there rather than what usually is not. The
         count stays the count of recordings, which is why it is absent on the
         terms that have none. data-t stays "2": renumbering would repoint
         every saved link. -->
    <button class="tab" role="tab" id="tab_${b.id}_2" aria-controls="pane_${b.id}_2" aria-selected="false" data-t="2">Hearings${videoCount(d)?` (${videoCount(d)})`:""}</button>
    <button class="tab" role="tab" id="tab_${b.id}_3" aria-controls="pane_${b.id}_3" aria-selected="false" data-t="3">Reports${
      reportCount(d)?` (${reportCount(d)})`:""}</button>
    <button class="tab" role="tab" id="tab_${b.id}_4" aria-controls="pane_${b.id}_4" aria-selected="false" data-t="4">Sponsors${(d.sponsors||[]).length?` (${(d.sponsors||[]).length})`:""}</button>

    <button class="tab" role="tab" id="tab_${b.id}_5" aria-controls="pane_${b.id}_5"
      aria-selected="false" data-t="5">Documents${
        (d.documents||[]).length?` (${d.documents.length})`:""}</button></div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_0" aria-labelledby="tab_${b.id}_0" tabindex="0" data-t="0">${renderSummary(b,d,rsa)}</div>
    ${/* ONLY WHERE THERE IS SOMETHING TO SHOW. 1,149 of 2,234 bills have a
          second version; a tab on the other 1,085 would say "there is one
          version" and fetch a file that is not there. nver comes from the
          manifest build_bill_versions.py writes. */ btPane}
    <div class="pane" role="tabpanel" id="pane_${b.id}_1" aria-labelledby="tab_${b.id}_1" tabindex="0" data-t="1" hidden>${paneNote("votes")}${renderVotes(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_2" aria-labelledby="tab_${b.id}_2" tabindex="0" data-t="2" hidden>${paneNote("hearings")}${renderHearings(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_3" aria-labelledby="tab_${b.id}_3" tabindex="0" data-t="3" hidden>${paneNote("reports")}${renderReports(b,d,rsa)}</div>


    <div class="pane" role="tabpanel" id="pane_${b.id}_4" aria-labelledby="tab_${b.id}_4" tabindex="0" data-t="4" hidden>${renderSponsors(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_5" aria-labelledby="tab_${b.id}_5"
      tabindex="0" data-t="5" hidden>${renderDocuments(b,d)}</div>${btsec}`;
}

// ======================================================= report a problem ==
//
// A box at the foot of a record's own page. It posts to /api/report
// (functions/api/report.js), the one thing on this site that runs.
//
// OUTSIDE #results, deliberately. Every tab click redraws #results, so a box
// inside it would lose whatever the reader had typed the moment they checked
// another tab to see if the problem was there too.
//
// WHAT IT SENDS is only what the page already knows -- the record, its
// address, the open tab, what kind of thing is wrong (from the list), the
// reader's words, the build the page came from, and how long the box was open
// -- plus an empty field no person fills in. Nothing identifies the reader,
// and the box says there is no way to reply.
//
// IF THE SEND FAILS, the reader keeps their words and gets an email link with
// the same facts filled in, so a broken endpoint costs them a click, not a
// retyping. With no JavaScript there is no box, and the footer's address is
// the whole feature, as it was before.
const REPORT_FIELDS=[["date","A date"],["status","The status"],["sponsor","A sponsor"],
  ["vote","A vote or its count"],["hearing","A hearing, its day or its time"],
  ["committee","A committee"],["text","The bill text or an amendment"],["link","A link"],
  ["chapter","The chapter of law"],["veto","A veto message"],["topic","The topic"],
  ["fiscal","The fiscal note"],["other","Something else"]];
const REPORT_TO="contact@graniterecord.org";
// The tabs the pages render. The Function accepts no other value, so a tab
// renamed here and not there sends "", rather than having the report dropped.
const REPORT_TABS=new Set(["Summary","Bill Text","Votes","Videos","Reports","Sponsors",
  "Documents","Prime sponsored","Co-sponsored","Bills","Sessions"]);
let reportBuild=null;       // site/build.json's "finished", fetched once, on first open

function reportBox(kind,ref){
  return `<details class="report" data-rkind="${esc(kind)}" data-rref="${esc(ref)}">
  <summary>Report a problem with this page</summary>
  <form class="reportform" novalidate>
    <p class="reportwhat">Tell us what is wrong and we will check it against the official record.
    Nothing here identifies you, which also means we cannot reply: for an answer, write to
    <a href="mailto:${REPORT_TO}">${REPORT_TO}</a>.</p>
    <p><label>What is wrong<br><select name="field"><option value="">Choose one</option>${
      REPORT_FIELDS.map(([v,t])=>`<option value="${v}">${t}</option>`).join("")}</select></label></p>
    <p><label>What does the record say instead?<br>
    <textarea name="note" rows="4" maxlength="1000"></textarea></label></p>
    <p style="position:absolute;left:-9999px" aria-hidden="true"><label>Leave this empty
    <input name="website" tabindex="-1" autocomplete="off"></label></p>
    <p><button type="submit">Send</button> <span class="reportstate" role="status" aria-live="polite"></span></p>
  </form></details>`;
}

function mountReport(kind,ref){
  if(document.getElementById("reportbox"))return;
  const res=$("#results");
  if(!res)return;
  const div=document.createElement("div");
  div.id="reportbox";
  div.innerHTML=reportBox(kind,ref);
  res.after(div);
}

// FOLLOW, WHERE THERE IS SOMETHING TO FOLLOW. A record's page names its feed
// in its head exactly where the build writes one -- a bill still moving, a
// member with a vote or a bill, a committee not archived (shell.py decides
// all three) -- so the control reads that link and asks nothing else. RSS
// only for now: following by email is designed (FOLLOW.md) and not built, and
// is not offered until it works.
const FOLLOWS={bill:"each new action, hearing and vote on this bill",
  member:"this member's newest votes and the bills they put their name to",
  committee:"each day this committee sits, and what it does with each bill"};
function mountFollow(kind){
  const link=document.querySelector('link[rel="alternate"][type="application/rss+xml"]');
  const res=$("#results");
  if(!kind||!link||!res||document.getElementById("followbox"))return;
  const href=link.getAttribute("href")||"";
  const div=document.createElement("div");
  div.id="followbox";
  div.className="followrow";
  // BESIDE "CITE THIS PAGE", in the row shell.py writes above the heading,
  // where there is one (every page built since 24 September): one row of
  // quiet controls rather than two stacked. A page from an older build has no
  // row, and Follow makes its own as it always did.
  const acts=document.getElementById("pageacts");
  if(acts)div.className="followin";
  div.innerHTML=`<details class="follow"><summary>Follow</summary>
    <div class="followpane">
      <p><b>By RSS</b>, in any feed reader: ${esc(FOLLOWS[kind]||"what is new here")}.
        The record is rebuilt once a night, so an update arrives the morning after
        it happens.</p>
      <p class="feedurl"><input type="text" readonly aria-label="The feed's address"
        value="${esc(new URL(href,location.origin).href)}">
        <button type="button" class="link" data-copyfeed="1">Copy the address</button>
        <a href="${esc(href)}">Open the feed</a></p>
    </div></details>`;
  if(acts)acts.insertBefore(div,acts.firstChild);
  else res.before(div);
}
document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest("[data-copyfeed]");
  if(!b)return;
  const input=b.parentNode.querySelector("input");
  const done=()=>{b.textContent="Copied";setTimeout(()=>{b.textContent="Copy the address";},2000);};
  const pick=()=>{input.focus();input.select();};
  if(navigator.clipboard&&navigator.clipboard.writeText)
    navigator.clipboard.writeText(input.value).then(done,pick);
  else pick();
});

function reportFallback(form,payload,why){
  const st=form.querySelector(".reportstate");
  const subject=`Problem on ${location.hostname}${payload.url}`;
  const body=`${payload.note}\n\n--\npage: ${location.origin}${payload.url}\n`+
    `record: ${payload.record}\nwhat: ${payload.field}\ntab: ${payload.tab||"-"}\nbuild: ${payload.build||"-"}\n`;
  st.innerHTML=`That did not send (${esc(why)}). Your words are still in the box. `+
    `<a href="mailto:${REPORT_TO}?subject=${encodeURIComponent(subject)}&amp;body=${encodeURIComponent(body)}">Send it by email instead</a>.`;
}

document.addEventListener("toggle",e=>{
  const box=e.target;
  if(!box.classList||!box.classList.contains("report")||!box.open)return;
  const form=box.querySelector(".reportform");
  if(form&&!form.dataset.opened)form.dataset.opened=String(Date.now());
  if(reportBuild===null){
    reportBuild="";
    fetch("/build.json").then(r=>r.ok?r.json():{}).then(d=>{reportBuild=String((d&&d.finished)||"");})
      .catch(()=>{});
  }
},true);

document.addEventListener("submit",async e=>{
  const form=e.target.closest&&e.target.closest(".reportform");
  if(!form)return;
  e.preventDefault();
  const box=form.closest(".report"), st=form.querySelector(".reportstate");
  const btn=form.querySelector("button[type=submit]");
  const note=form.elements.note.value.trim();
  if(!form.elements.field.value){st.textContent="Choose what is wrong from the list.";return;}
  if(note.length<3){st.textContent="Say in a few words what is wrong.";return;}
  const tab=document.querySelector('.tabs .tab[aria-selected="true"]');
  // The label without its count, in any locale's way of writing a number.
  const tabLabel=tab?tab.textContent.trim().replace(/\s*\([\d.,\s']+\)\s*$/,""):"";
  const payload={
    record:`${box.dataset.rkind}:${box.dataset.rref}`,
    url:location.pathname.replace(/\.html$/,""),
    tab:REPORT_TABS.has(tabLabel)?tabLabel:"",
    field:form.elements.field.value,
    note,
    build:reportBuild||"",
    elapsed:Date.now()-(+form.dataset.opened||Date.now()),
    website:form.elements.website.value};
  btn.disabled=true;
  st.textContent="Sending…";
  const ctl=new AbortController();
  const timer=setTimeout(()=>ctl.abort(),6000);
  try{
    const r=await fetch("/api/report",{method:"POST",signal:ctl.signal,
      headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    // 503 and 429 are the Function's two answers for a report it accepted and
    // could not keep (functions/api/report.js) -- storage down, and the day's
    // ceiling reached -- so each gets words a reader can use. Where the zone's
    // rate rule in front of the Function answers 429 as well, the same words
    // are as true of it. Any other failure still offers the email address.
    if(!r.ok)throw new Error(r.status===503?"the site could not save it just now":
      r.status===429?"the site is taking no more reports just now":
      `the server answered ${r.status}`);
    form.elements.note.value="";
    st.textContent="Thank you. It will be checked against the record.";
  }catch(err){
    reportFallback(form,payload,err&&err.name==="AbortError"?"no answer in six seconds":
      (err&&err.message)||"no connection");
  }finally{
    clearTimeout(timer);
    btn.disabled=false;
  }
});

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
// record -- goes through here. The redraw replaces the element that held focus
// with a copy, and focus fell to <body>: a keyboard reader who arrowed onto
// Bill Text lost their place the moment its text loaded. Put focus back on the
// copy, matched by id or, for a member or committee tab, by its position.
// The Votes tab's own controls carry neither an id nor data-pt -- the
// full-record button and the legend's rows -- so each is found again by
// the data attribute saying what it opens (24 September).
const repaint=()=>{
  const a=document.activeElement;
  const sel=a&&a!==document.body
    ?(a.id?`#${CSS.escape(a.id)}`:a.dataset&&a.dataset.pt!==undefined?`.tab[data-pt="${a.dataset.pt}"]`
      :a.dataset&&a.dataset.full!==undefined?`[data-full="${CSS.escape(a.dataset.full)}"]`
      :a.dataset&&a.dataset.seg!==undefined?`[data-seg="${CSS.escape(a.dataset.seg)}"]`:null)
    :null;
  if(PAGE)renderPage();else render();
  if(sel){const f=document.querySelector(sel);if(f&&f!==document.activeElement)f.focus({preventScroll:true});}
};

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

// A committee named on a bill, as a link to its page where there is one.
// 3,967 mentions across the site were plain text, so the reader who wanted
// "what else did this committee do" had nowhere to click.
//
// THE NAME AS THE BILL CARRIES IT, TO THE COMMITTEE IT WAS. A name is not
// always one committee: 1995's Corrections and Criminal Justice sits today as
// Criminal Justice and Public Safety, and the Senate's Election Law and
// Internal Affairs of 2007-2008 is not the committee of that name formed for
// 2017-2018. meta.json carries such a name as {"": page, "<term>": page}, and
// the term decides; the label is never changed to the later name.
function cmteLink(name,term){
  const v=(META&&META.committee_codes||{})[name];
  const code=typeof v==="string"?v
    :v?((term&&Object.prototype.hasOwnProperty.call(v,term))?v[term]:v[""]):"";
  return code?`<a href="committee/${esc(code)}.html">${esc(name)}</a>`:esc(name);
}

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
function cmeta(b){
  return [esc(b.sponsor_label||b.sponsor||""),
    ...(b.committees||[b.committee]).filter(Boolean).map(c=>cmteLink(c,b.term)),
    b.topic?esc(b.topic):""].filter(Boolean).join(" · ");
}

/* A BILL REQUEST'S CARD, which is shorter because a request is smaller.

   "Cards should be shorter", asked for on 18 September, and the reason they
   can be is that an LSR has four facts and a bill has forty: a number, a
   title, a prime sponsor, and which body it will be filed in. No committee,
   no hearing, no votes, no text -- so there is nothing to expand into, no
   standalone page to link to, and no four-stop rail to draw. Forcing this
   through cardHtml would have meant five conditionals inside it and a card
   that opened onto an empty drawer.

   The sponsor is a link wherever the name matched a sitting member, which on
   the 241 requests filed so far is all of them. */
function lsrCardHtml(b){
  const who=b.sponsor_label||b.sponsor||"";
  return `<article class="card lsr" data-id="${esc(b.id)}">
      <div class="chead">
        <div class="crow"><span class="cnum">${esc(b.n)}</span>
        <span class="cstat ${b.withdrawn?"veto":""}">${esc(b.status||"")}</span></div>
        <div class="ctitle">${esc(b.title)}</div>
        <div class="cmeta">${b.sponsor_slug
          ?`<a href="legislator/${esc(b.sponsor_slug)}.html">${esc(who)}</a>`
          :esc(who)}${b.body_label?` &middot; ${esc(b.body_label)}`:""}</div>
      </div>
    </article>`;
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
const CHNAME2={H:"House",S:"Senate"};
const RAILMARK={p:"\u2713", x:"\u2715", h:"", "-":""};
const RAILSAY={p:"passed", h:"is here now", x:"stopped here",
               "-":"never reached"};
function rail(b){
  const p=b.passage||"";
  if(!CHNAME2[p[0]])return "";
  const other=p[0]==="H"?"S":"H";
  const st=p.slice(1);
  // A resolution belongs to one chamber and has two stops: that chamber, and
  // whether it was adopted. Four stops drew it against a Senate it was never
  // going to see and a Law it could never become.
  const stops = st.length===2 ? [CHNAME2[p[0]],"Adopted"]
              : st.length===4 ? [CHNAME2[p[0]],CHNAME2[other],"Governor","Law"]
              : null;
  if(!stops)return "";
  const said=stops.map((name,i)=>`${name}: ${RAILSAY[st[i]]||"not known"}`)
    .join("; ");
  return `<span class="rail" role="img" aria-label="${esc(said)}"
    title="${esc(said)}">${stops.map((name,i)=>
      `<span class="stop s-${esc(st[i]==="-"?"o":st[i])}"
        ><b>${RAILMARK[st[i]]||""}</b><i>${esc(name)}</i></span>`
    ).join("")}</span>`;
}

// THE RAIL ON A BILL'S OWN VIEW, DATED -- the bill's own page and a card
// opened in the list (the person chose it on 24 September). Under each stop
// the day and one or two words of what happened there: "Senate / 22 May /
// 16–8, amended". The list card keeps the bare rail above, which is a glyph
// to scan past; this one is read.
//
// Its stops follow the bill's route and come from the record's journey
// (build_site_v2.journey_rail): Introduced first; a resolution of one chamber
// has that chamber; a concurrent resolution two chambers and no governor; a
// CACR goes to the Voters, ringed while it waits for them. The marks are the
// index's passage, the same the list card draws, and the words are the same
// lines "How it got here" lists -- one account in three places.
//
// A stop not reached has no date. The year is on the first date and wherever
// it changes, so "8 Jan 2025 ... 13 Feb ... 7 Jan 2026" reads without a key.
const RAILMON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const RAILMONTH=["January","February","March","April","May","June","July",
  "August","September","October","November","December"];
function railDay(iso,year,long){
  const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(iso||"");
  if(!m)return "";
  return `${+m[3]} ${(long?RAILMONTH:RAILMON)[+m[2]-1]}${year?` ${m[1]}`:""}`;
}
function datedRail(b,d){
  const st=((d||{}).journey||{}).rail||[];
  if(!st.length)return rail(b);
  let was="";
  const cells=st.map(s=>{
    const y=(s.date||"").slice(0,4);
    const day=s.date?railDay(s.date,y!==was):"";
    if(s.date)was=y;
    const sub=[day,s.short].filter(Boolean);
    return `<span class="stop s-${esc(s.mark==="-"?"o":s.mark)}"><b>${
      RAILMARK[s.mark]||""}</b><i>${esc(s.stop)}</i>${sub.length
      ?`<small>${sub.map(esc).join("<br>")}</small>`:""}</span>`;
  });
  // The same facts as a sentence, for a reader who hears the page: every
  // date in full -- the Law stop's words carry one of their own, "in effect
  // 11 Jan 2026" -- and a tally read "16 to 8" rather than a dash.
  const said=st.map(s=>{
    const when=s.date?railDay(s.date,true,true):"";
    const what=(s.say||"").replace(/(\d)–(\d)/g,"$1 to $2")
      .replace(/\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{4})\b/g,
        (_m,d,mo,y)=>`${d} ${RAILMONTH[RAILMON.indexOf(mo)]} ${y}`);
    return s.stop==="Introduced"
      ?`Introduced${when?` ${when}`:""}`
      :`${s.stop}: ${what.charAt(0).toLowerCase()+what.slice(1)}${when?`, ${when}`:""}`;
  }).join("; ");
  return `<span class="rail dated" role="img" aria-label="${esc(said)}"
    title="${esc(said)}">${cells.join("")}</span>`;
}

function cardHtml(b,focus){
  const open=openCards.has(b.id);
  const y=b.year||(b.term?String(b.term).slice(0,4):"");
  return `<article class="card ${open?'open':''}${focus?' focus':''}" data-id="${b.id}">
      ${focus?"":`<a class="detail" href="bill/${esc(String(y))}/${esc(b.id.toLowerCase())}.html"
        title="${esc(b.n)} on its own page: its own address, and a link worth sharing"
        aria-label="Open the standalone page for ${esc(b.n)}">&#8599;</a>`}
      <button class="chead" aria-expanded="${open}">
        <div class="crow"><span class="cnum">${esc(b.n)} (${esc(String(y))})</span>
        <span class="cyear">${b.carried
          ?` <span class="chip" title="The docket shows action in more than one year of the term — usually a bill the committee retained in the first year and reported in the second">carried over</span>`:""}</span>
        <span class="cstat ${KIND[b.kind]||""}">${esc(b.status||"")}</span></div>
        <div class="ctitle">${esc(b.title)}</div>
        <div class="cmeta">${cmeta(b)}</div>
        ${(open||focus)&&detail[dkey(b.id)]?datedRail(b,detail[dkey(b.id)]):rail(b)}
      </button>
      <div class="cbody" ${open?"":"hidden"}>${
        open?(detail[dkey(b.id)]?renderDetail(b,detail[dkey(b.id)]):`<p class="spin">Loading…</p>`):""}</div>
    </article>`;
}

// The tabs inside an expanded card are set after its HTML is in the document,
// because every tab's pane is written and only one is shown. Both renderers
// have to do it, so neither owns it.
// Which analyses the reader has opened out. Keyed on the bill, so opening
// one and then touching any other control does not shut it again.
const anOpen=new Set();

// A box is clamped unless the reader opened it, and gets a button only if it
// actually overflows -- which is a measurement, not a guess: the same 300
// characters are three lines on a desktop and eight on a phone.
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
      const over=text.scrollHeight>text.clientHeight+2;
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
    const c=document.querySelector(`.card[data-id="${id}"]`),t=openTab[id]||"0";
    if(!c||!detail[dkey(id)])return;
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
          status:b.status||"",kind:b.kind||"",sponsor:"",committees:[]};
}

// The bills of one tab, as cards, with the outcome filter above them.
function billPane(rows,note){
  rows=rows.slice().sort((a,b)=>billCmp(a.id,b.id));
  const statuses=[...new Set(rows.map(b=>b.status).filter(Boolean))].sort();
  const shown=rows.filter(b=>!PAGE.status||b.status===PAGE.status);
  return `<div class="bfilt"><label>Status
      <select data-pf="status"><option value="">Any</option>
      ${statuses.map(x=>`<option value="${esc(x)}"${x===PAGE.status?" selected":""}>${
        esc(x)}</option>`).join("")}</select></label></div>
    <p class="src">${note(shown.length)}</p>
    <div class="cards">${shown.map(b=>b.lsr?lsrCardHtml(b):cardHtml(b,false)).join("")}</div>`;
}

// The term, above the tabs, because it governs all of them.
function termControl(){
  const ts=(PAGE&&PAGE.terms)||[],t=pageTerm();
  if(ts.length<2)return "";
  return `<div class="bfilt pterm"><label>Term
    <select data-pf="term">${ts.map(x=>
      `<option value="${esc(x)}"${x===t?" selected":""}>${esc(x)}</option>`
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

// One strip per member or committee page, so the ids are fixed: ptab_<i> for a
// tab and ppane for the panel it controls, which pagePane() writes.
function tabStrip(tabs){
  return `<div class="tabs" role="tablist">${tabs.map((t,i)=>
    `<button class="tab" role="tab" id="ptab_${i}" aria-controls="ppane" data-pt="${i}" aria-selected="${
      i===PAGE_TAB}">${esc(t[0])}${t[1]?` (${t[1].toLocaleString()})`:""}</button>`
  ).join("")}</div>`;
}
function pagePane(html){
  return `<div class="pane" role="tabpanel" id="ppane" aria-labelledby="ptab_${PAGE_TAB}" tabindex="0">${html}</div>`;
}

// ONE CHIP FOR A PERSON, wherever they appear. A committee's members were
// drawn in party colour and a bill's sponsors were not: the sponsor pill was
// pine green for everyone, so the same member read as one party on a
// committee page and as no party on a bill. Prime sponsorship stays bold and
// a committee role stays in the corner; nothing else differs between them.
//
// The party comes from party_code where the roster supplied one and from the
// first letter of party where only the word is there, because the sponsor
// records carry "Republican" and the roster carries "R".
const pchip=m=>{
  const code=String(m.party_code||m.party||"").toUpperCase().slice(0,1)||"X";
  const who=esc(m.display_full||m.label||m.name||"");
  // A LABEL, NOT BOLD. A committee roster has always labelled its Chair, Vice
  // Chair and Clerk through the <i> below, and the prime sponsor was marked
  // with bold alone -- which is not a label, cannot be told from emphasis, and
  // is nothing at all to a screen reader. It reuses the mechanism that was
  // already there rather than adding a second one.
  const role=(m.role&&m.role!=="Member")?m.role:(m.prime?"Prime":"");
  return `<span class="mchip p-${esc(code)}">${
    m.slug?`<a href="legislator/${esc(m.slug)}.html">${who}</a>`:who}${
    role?` <i>${esc(role)}</i>`:""}</span>`;};
const mchip=pchip;

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
function attendanceBlock(att,t){
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
  return `<div class="patt">${out.join("")}</div>`;
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

/* "FORMER REP." IN THE NAME ITSELF, as the person settled it in September: a
   legislator who has left is written "Former Rep. David Smith" -- the word
   joins the honorific, never a chip, badge or pill beside it -- on their own
   page and in search results (find.json), and nowhere else. The honorific is
   the record's own, the office they last held under it. A name the record
   gives no honorific ("Member #377204") is left as it is, and the line under
   it keeps saying "Former member". build_legislator_pages.heading() writes
   the page's title and link card the same way. */
function formerName(m){
  const who=m.display_full||m.display||m.name||"";
  return /^(Rep|Sen)\. /.test(who)?"Former "+who:"";
}

function renderMemberHead(m){
  const towns = m.towns||[];
  /* FORMER MEMBERS, ON THEIR OWN PAGE AND NOWHERE ELSE. A reader arriving
     cold at a page with a full voting record should not be left thinking the
     person still holds the seat, so the page says plainly that they do not:
     its heading names them "Former Rep." or "Former Sen." (formerName).
     That is a statement of tenure, and it is different in kind from a badge
     in a list: in a roll call or a sponsor list a former member is drawn
     exactly like a sitting one, same honorific, party and seat.
     It says nothing about WHY they left. The site does not distinguish a
     member who resigned from one who lost, retired or died, and must not
     start here -- people who served alongside them read this. */
  const former = !!(m.former || window.GR_FORMER);
  const yrs = former ? servedYears(m) : "";
  const titled = former ? formerName(m) : "";
  return `<div class="phead">
    <h1>${esc(titled||m.display_full||m.display||m.name||"")}</h1>
    <p class="pmeta">${esc(m.chamber==="S"?"State Senate":"House of Representatives")}${
      m.district?` &middot; District ${esc(m.district)}`:""}${
      m.county?` &middot; ${esc(m.county)} County`:""}</p>
    ${former?`<p class="pformer">${
      /* The years are the span of the RECORD -- roll calls here begin in 1999,
         so a member sworn in before that appears from the year the evidence
         starts. "On record" carries that; the person's call was to leave it at
         one phrase rather than explain it, the case being rare. The heading
         already says "Former", so the line says it only where the heading
         could not. */
      titled?(yrs?`On record ${esc(yrs)}. `:"")
        :`Former member${yrs?` &middot; on record ${esc(yrs)}`:""}. `}This page is
      their record in the General Court; it is not a current directory entry.</p>`:""}
    ${serviceLine(m)}
    ${former?"":(towns.length?`<p class="ptowns"><b>Represents</b> ${
      towns.map(t=>esc(t)).join(" &middot; ")}</p>`:
      `<p class="ptowns note">The towns in this district are not on file.</p>`)}
    ${(m.committees||[]).length?`<p class="pcmte"><b>Committees</b> ${
      m.committees.map(c=>cmteLink(
        (m.chamber==="S"?"Senate ":"House ")+c)).join(" &middot; ")}</p>`:""}
    ${m.seat?`<p class="pseat"><b>Seat</b> ${esc(plate(m.seat))}</p>`:""}
    ${(!former&&m.email)?`<p class="pmeta"><b>Email</b> <a href="mailto:${
      esc(m.email)}">${esc(m.email)}</a></p>`:""}
  </div>`;
}

const memberBills=(m,prime)=>(m.sponsored||[])
  .filter(b=>!!b.prime===prime)
  .filter(b=>!pageTerm()||b.term===pageTerm())
  .map(idxRow);

function renderMemberBills(m, prime){
  const rows=memberBills(m,prime);
  const t=pageTerm();
  if(!rows.length)return `<p class="src">No bills ${prime?"prime sponsored"
    :"co-sponsored"} in the ${esc(t)} term.</p>`;
  return billPane(rows,n=>`${n.toLocaleString()} bill${n===1?"":"s"}${
    prime?" prime sponsored":" co-sponsored"} in ${esc(t)}. Sponsoring a bill is
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
const memberVotes=m=>(m.votes||[]).filter(x=>{
  const y=voteYear(x);
  return !pageTerm()||!y||termOfYear(y)===pageTerm();});

// WHAT THE VOTE DECIDED, not only how they voted. This tab listed 1,081 rows
// of "HB2026 / Veto Override / Yea" on one member's page: the record's own
// abbreviations, no outcome, and no way to see when somebody had broken with
// their own party. All three answers are in one shared file, fetched the
// first time this tab is drawn -- the same 1,504 roll calls describe all 406
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
    .then(j=>{RCX=j;renderPage();})
    .catch(e=>{RCX_ERR=e.message||String(e);renderPage();});
}

// Which way a party went on one roll call, where it went a way at all. Five
// members is the floor: a party of two has no majority worth naming, and an
// even split has no side. Both come back blank rather than as a coin toss,
// and only Yea and Nay are counted -- a member who did not vote did not take
// a side, and counting an absence as agreement would be an invention.
const PARTY_FLOOR=5;
function partySide(rc,code){
  const c=rc&&rc.s&&rc.s[code];
  if(!c)return "";
  const yea=c[0]||0, nay=c[1]||0;
  if(yea+nay<PARTY_FLOOR||yea===nay)return "";
  return yea>nay?"Yea":"Nay";
}

// Whether this member took the side most of their own party took. It is a
// fact about one vote, and the count of them below is a count -- neither is
// turned into a percentage, a rating or a rank. Breaking with your party is
// not a virtue or a failing here; it is a thing that happened, and a reader
// who wants to know how often can see the number and the denominator.
function partyMark(m,x,rc){
  const code=String(m.party_code||m.party||"").toUpperCase().slice(0,1);
  if(code==="X"||!PARTY_NAME[code])return null;
  const side=partySide(rc,code), mine=String(x.v||"");
  if(!side||(mine!=="Yea"&&mine!=="Nay"))return null;
  return {agreed:mine===side, code, word:PARTY_NAME[code]+"s"};
}

// How many are drawn before the reader asks for more. The old table stopped
// dead at 600 with a line saying so and no way to see the 481 after it.
const VOTES_SHOWN=200;

function renderMemberVotes(m){
  const v=memberVotes(m);
  const t=pageTerm();
  if(!v.length)return `<p class="src">No recorded roll call votes in the
    ${esc(t)} term. Voice and division votes leave no record of individual
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
  // the index this page already holds, and where the member stood in their
  // own party.
  const all=v.map(x=>{
    const rc=(RCX||{})[x.k]||null;
    return {x, rc, mark:partyMark(m,x,rc),
            ch:castIn&&chs.length>1?chOf(x):"",
            b:(x.b&&x.y)?idxRow({id:x.b,year:x.y,term:termOfYear(x.y)}):null};
  });

  const q=(PAGE.vfilter||"").toLowerCase(), pf=PAGE.vparty||"";
  const rows=all.filter(r=>(!q||String(r.x.v||"").toLowerCase()===q)
    &&(!pf||(r.mark&&(pf==="with")===r.mark.agreed)));
  const tally={};
  v.forEach(x=>{tally[x.v]=(tally[x.v]||0)+1;});

  // The denominator is the roll calls where their party actually took a side,
  // not every roll call: on the rest there was nothing to break with.
  const marked=all.filter(r=>r.mark);
  const broke=marked.filter(r=>!r.mark.agreed).length;
  const pname=PARTY_NAME[String(m.party_code||m.party||"")
    .toUpperCase().slice(0,1)]||"";

  const cap=PAGE.vshow||VOTES_SHOWN;
  const shown=rows.slice(0,cap);
  const left=rows.length-shown.length;

  return `<div class="bfilt"><label>Vote
      <select data-pf="vfilter"><option value="">Any</option>
      ${Object.keys(tally).sort().map(k=>`<option value="${esc(k.toLowerCase())}"${
        q===k.toLowerCase()?" selected":""}>${esc(k)} (${tally[k]})</option>`).join("")}
      </select></label>${marked.length?`<label>Their party
      <select data-pf="vparty"><option value="">Any</option>
        <option value="with"${pf==="with"?" selected":""}>Voted with ${
          esc(pname)}s (${(marked.length-broke).toLocaleString()})</option>
        <option value="against"${pf==="against"?" selected":""}>Voted against ${
          esc(pname)}s (${broke.toLocaleString()})</option>
      </select></label>`:""}</div>
    <p class="src">${rows.length.toLocaleString()} of ${v.length.toLocaleString()}
      recorded votes in ${esc(t)}${castIn}, newest first. Every roll call this member is
      recorded in, as it was cast and on what. Nothing here is rated or
      scored.${marked.length?` On the ${marked.length.toLocaleString()} where
      ${esc(pname)}s took a side, this member took the other one
      ${broke.toLocaleString()} time${broke===1?"":"s"}.`:""}</p>
    ${RCX_ERR?`<p class="note">What each vote decided could not be loaded, so
      the outcomes and the party comparison are missing from the rows below.
      The votes themselves are the member's own record and are unaffected.
      <code>${esc(RCX_ERR)}</code></p>`:""}
    <table class="votes vfull"><thead><tr><th>Date</th>
      <th>What the vote was on</th><th>Their vote</th><th>Outcome</th>
      </tr></thead><tbody>${shown.map(r=>voteRow(r)).join("")}
      </tbody></table>
    ${left?`<p class="src"><button type="button" class="link" data-vmore="1"
      >Show ${Math.min(VOTES_SHOWN,left).toLocaleString()} more</button> &mdash;
      ${left.toLocaleString()} of ${rows.length.toLocaleString()} not yet
      shown.</p>`:""}`;
}

// One row. data-l carries the column's name so the same markup can stack into
// labelled blocks on a phone instead of scrolling sideways, which on a civic
// site reads as "this page was not meant for you".
function voteRow(r){
  const x=r.x, rc=r.rc, b=r.b;
  // The record's own word for the question and the plain-English one are both
  // kept: "pass the bill with changes" is what a reader needs, and "OTPA" is
  // what they will see on every other page of the General Court's own site.
  const plain=(rc&&rc.q)||"", raw=x.q||"";
  const question=plain
    ? `${esc(plain)}${raw&&raw.toLowerCase()!==plain.toLowerCase()
        ?` <span class="dim">(${esc(raw)})</span>`:""}`
    : esc(raw);
  const tallies=rc&&rc.y!=null&&rc.n!=null
    ? ` <i>${rc.y}–${rc.n}</i>`:"";
  return `<tr>
    <td class="d" data-l="Date">${esc(x.d||"")}${r.ch?`<span class="vch">${
      esc(CHAMBER_SHORT[r.ch]||r.ch)}</span>`:""}</td>
    <td class="b" data-l="On">${x.b&&x.y
      ? `<a href="bill/${esc(String(x.y))}/${esc(String(x.b).toLowerCase())
        }.html">${esc((b&&b.n)||x.b)}</a>`
      : x.b ? esc(x.b)
      // A procedural vote -- a call of the roll, a rules suspension -- is
      // recorded against no bill. It used to render an empty cell wrapped in
      // a link to /bill//.html.
      : `<span class="none">no bill</span>`}${
      b&&b.title?`<span class="vt">${esc(b.title)}</span>`:""}
      <span class="vq">${question}</span></td>
    <td class="v" data-l="Their vote"><span class="vcast v-${
      esc(String(x.v||"").slice(0,3).toLowerCase())}">${esc(x.v||"")}</span>${
      r.mark?`<i class="pm${r.mark.agreed?"":" broke"}">${
        r.mark.agreed?"with":"against"} ${esc(r.mark.word)}</i>`:""}</td>
    <td class="o" data-l="Outcome">${rc
      ? `<span class="${rc.p?"pass":"fail"}">${rc.p?"Adopted":"Failed"}</span>${
          tallies}${rc.tn?`<i class="thr">${esc(rc.tn)}</i>`:""}${
          rc.oc?`<i class="thr">${esc(rc.oc)}</i>`:""}`
      : `<span class="dim">&mdash;</span>`}</td></tr>`;
}

function renderMember(m){
  const tabs=[["Prime sponsored",memberBills(m,true).length],
              ["Co-sponsored",memberBills(m,false).length],
              ["Votes",memberVotes(m).length]];
  const body=[()=>renderMemberBills(m,true),()=>renderMemberBills(m,false),
              ()=>renderMemberVotes(m)][PAGE_TAB]||(()=>"");
  // Attendance under the term control, because the term governs it as it
  // governs the tabs, and above them, because it is about the member rather
  // than about any one tab.
  return renderMemberHead(m) + termControl() + attendanceBlock(m.attendance, pageTerm())
    + tabStrip(tabs) + pagePane(body());
}

// ------------------------------------------------------------- committee ---
// Laid out the way the General Court lays out its own committee pages,
// because that is the layout the people who use these pages already know:
// the officers and the staff side by side, then the whole membership, then
// what the chamber's rules say the committee is for.
// WRITING TO A WHOLE COMMITTEE. Every one of these addresses is published
// by the General Court and 404 of them are already on this site's own member
// pages, so nothing is disclosed here that was not already public. They go in
// the To field rather than Bcc: a person writing to a committee should be
// able to see, and say, who they are writing to.
//
// A member who has left the House keeps their seat in the record and has no
// address on file, so they are not in the link and the count says so. The
// largest committee, House Finance, makes a 720-character mailto with 26
// addresses in it -- well inside what a mail client will take.
function emailCommittee(c){
  const seats=(c.members||[]).filter(m=>m.sitting!==false);
  const with_=seats.filter(m=>m.email);
  if(!with_.length)return "";
  const to=with_.map(m=>m.email).join(",");
  const subject=`${c.name||"Committee"} ${c.chamber==="S"?"(Senate)":"(House)"}`;
  const href=`mailto:${encodeURIComponent(to).replace(/%2C/g,",")}`
    +`?subject=${encodeURIComponent(subject)}`;
  const missing=seats.length-with_.length;
  return `<p class="cmail"><a class="btn" href="${href}">Email the
    ${with_.length} members of this committee</a>${missing?
    `<span class="src"> ${missing} member${missing===1?" has":"s have"} no
     address on file</span>`:""}</p>`;
}

function renderCommitteeHead(c){
  const officers=(c.officers||[]).filter(o=>o.name);
  const staff=[["Committee aide",c.aide],["Researcher",c.researcher],
               ["Room",c.room],["Phone",c.phone]].filter(x=>x[1]);
  const members=c.members||[];
  const rule=c.purpose||null;
  const dl=(cls,rows)=>rows.length?`<dl class="${cls}">${rows.map(
    ([k,v])=>`<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>`:"";
  return `<div class="phead">
    <h1>${esc(c.name||"")}</h1>
    <p class="pmeta">${esc(c.chamber==="S"?"State Senate":"House of Representatives")}</p>
    ${c.archived?`<p class="src">Not on the General Court&rsquo;s list of committees today.
      Its bills and sitting days on this record run ${esc(c.archived.years||"")}; the
      records do not say whether it was renamed, divided, merged or ended.</p>`:""}
    ${/* The names it carried before, so a reader who followed an older name
         here from a bill knows this is the committee it was. The bills and
         sittings below keep the name they were given at the time. */
      (c.names||[]).length?`<p class="src">Named ${c.names.map(n=>
        `<b>${esc(n.name)}</b> (${esc(n.years||"")})`).join(" and ")} on this
      record&rsquo;s earlier bills and sittings, which the General Court&rsquo;s
      own records file under this committee.</p>`:""}
    <div class="cinfo">
      ${dl("cofficers",officers.map(o=>[o.role,
        o.slug?`<a href="legislator/${esc(o.slug)}.html">${esc(o.label||o.name)}</a>`
              :esc(o.name)]))}
      ${dl("cstaff",staff.map(([k,v])=>[k,esc(v)]))}
    </div>
    ${members.length?`<div class="croster">
      <h2>Members <span>${members.length}</span></h2>
      <p class="mlist">${members.map(mchip).join(" ")}</p>
      ${emailCommittee(c)}</div>`:""}
    ${rule?`<div class="cpurpose"><h2>What it does</h2>
      <p>${esc(rule.text||"")}</p>
      <p class="src">${esc(rule.rule||"")}, as the General Court publishes it.</p>
      </div>`:""}
    ${c.url?`<p class="src"><a href="${esc(c.url)}" target="_blank"
      rel="noopener">This committee on gencourt &#8599;</a></p>`:""}
  </div>`;
}

const cmteBills=c=>((c.bills||{})[pageTerm()]||[]).map(idxRow);
const cmteSessions=c=>(c.sessions||[])
  .filter(s=>!pageTerm()||!s.term||s.term===pageTerm());

function renderCommitteeBills(c){
  const rows=cmteBills(c),t=pageTerm();
  if(!rows.length)return `<p class="src">No bills were referred to this
    committee in the ${esc(t)} term.</p>`;
  return billPane(rows,n=>`${n.toLocaleString()} bill${n===1?"":"s"} referred to
    this committee in ${esc(t)}.`);
}

// One day the committee met: what it did, the recording, and the moment each
// bill was taken up. The timestamps drive the player above them rather than
// sending the reader to YouTube and back.
function sessionHtml(s,si){
  const items=s.items||[];
  const pid=`d${String(s.date||"").replace(/-/g,"")}_${si}`;
  const timed=items.filter(i=>i.start!=null);
  const from=timed.length?Math.max(0,Math.floor(timed[0].start)):0;
  const vid=s.video_id||"";
  // ONE number, shown and seeked. Where the header, the player and the button
  // each carried a slightly different offset, a reader had no way to tell
  // which one was the claim.
  const player=vid?`<div class="player" data-player="${esc(pid)}">
      <button type="button" class="pstub" data-embed="${esc(vid)}|${from}|${esc(pid)}">
        <span>&#9654;</span><span>Play this day's recording${timed.length
          ?` from ${hms(from)}, where the first bill is taken up`:""}</span></button>
      <div class="pbar">
        <a href="https://www.youtube.com/watch?v=${esc(vid)}&t=${from}s"
           target="_blank" rel="noopener">Open on YouTube</a>
        <span class="tolnote">${timed.length
          ?"the times below move this player"
          :"no moment in this recording has been identified yet"}</span>
      </div></div>`
    // THE COMMITTEE WAS RECORDED; WHICH RECORDING THIS IS, IS NOT SETTLED.
    // A day whose sittings are all in the "candidates" state has no video_id
    // for the same reason a bill's station does: more than one recording of
    // this committee exists for that day and nothing in the record says which
    // took the bill up, so the site picks none. Reading that as "no recording
    // of this day is on file" said the opposite of what the manifest holds,
    // on 46 days and 261 bill items -- the same contradiction the candidates
    // state was created to remove from bill pages, still standing here.
    : (items.some(i=>i.state==="candidates")
      ? `<p class="note">This committee was recorded on this day, and which of
         its recordings each sitting belongs to has not been established &mdash;
         a committee can sit in divisions that stream separately. Each bill
         below links the recordings it could be.</p>`
      : `<p class="note">No recording of this day is on file.</p>`);
  // A DAY IS SOMETHING YOU CAN LINK TO. It had no id at all, so a calendar
  // entry could name the committee and not the sitting, and the only per-day
  // string in the DOM was the player id -- which is absent on days with no
  // recording and carries the day's index inside the TERM-FILTERED list, so
  // it changes when the term picker moves. The date does neither.
  return `<section class="cday" id="${esc(dayId(s.date))}">
    <h3><a class="daylink" href="#${esc(dayId(s.date))}"
      title="A link to this sitting">${esc(fdate(s.date))}</a></h3>
    <p class="cnarr">${esc(s.narrative||"")}</p>
    ${player}
    <ul class="tl">${items.map(i=>{
      // "stated" is a boundary the chair spoke; anything else was worked out
      // from the schedule or the surrounding recording and says so.
      const said=/^(stated|floor_stated|floor_precise)$/.test(i.state||"");
      const at=i.start!=null?Math.max(0,Math.floor(i.start)):null;
      return `<li>
      <span class="d">${at!=null
        ? (vid?`<button class="jump" data-seek="${esc(pid)}|${at}">${hms(at)}</button>`
             :`${hms(at)}`)
        : "&mdash;"}${at!=null&&!said?`<i class="approx">approximate</i>`:""}</span>
      <span class="w"><a href="bill/${esc(String(i.year||""))}/${
        esc(String(i.bill||"").toLowerCase())}.html">${esc(i.n||i.bill||"")}</a>
        &mdash; ${esc(i.kind||"")}${i.title?`<span class="cd-title">${
          esc(i.title)}</span>`:""}</span></li>`;}).join("")}</ul>
  </section>`;
}

function renderCommitteeSessions(c){
  const ss=cmteSessions(c),t=pageTerm();
  if(!(c.sessions||[]).length)return `<p class="src">No day of this committee is
    on record. Committees that no longer meet keep their page so the bills they
    handled still have somewhere to point.</p>`;
  if(!ss.length)return `<p class="src">No day of this committee is on record in
    the ${esc(t)} term.</p>`;
  return `<p class="src">${ss.length.toLocaleString()} day${ss.length===1?"":"s"}
      this committee met in ${esc(t)}, newest first. Each is the day's recording
      with the moment every bill was taken up, composed from the record rather
      than written.</p>`
    + ss.map(sessionHtml).join("");
}

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

const MEET_KIND={"public hearing":["Public hearing","k-hearing"],
                 "hearing":["Public hearing","k-hearing"],
                 "executive session":["Executive session","k-exec"],
                 "work session":["Work session","k-meet"],
                 "subcommittee work session":["Subcommittee work session","k-meet"],
                 "full committee work session":["Full committee work session","k-meet"],
                 "study committee":["Study committee","k-study"],
                 "statutory committee":["Statutory committee","k-study"],
                 "committee of conference":["Committee of conference","k-conf"],
                 "floor debate":["Floor session","k-floor"]};

// "13:30" -> "1:30 PM", as a reader says a time: build_pages.clock, and the
// Calendar page's own, which preflight holds this to. A no-break space keeps
// AM or PM with its time; anything that is not a time comes back as it was.
function clock(t){
  const m=/^(\d{1,2}):(\d\d)/.exec(String(t||""));
  if(!m||+m[1]>23)return String(t||"");
  const h=+m[1];
  return (h%12||12)+":"+m[2]+"\u00a0"+(h<12?"AM":"PM");
}

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
  const today=new Date(); today.setHours(0,0,0,0);
  const when=d=>{
    const dd=new Date(d+"T00:00:00");
    if(isNaN(dd))return [d,""];
    const off=Math.round((dd-today)/86400000);
    const rel=off===0?"today":off===1?"tomorrow":(off>0&&off<14)?`in ${off} days`:"";
    return [dd.toLocaleDateString(undefined,
      {weekday:"short",day:"numeric",month:"short"}),rel];
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
        ||[k2?k2.charAt(0).toUpperCase()+k2.slice(1):"Meeting",""];
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
          return `<span class="calkind ${c}">${esc(w)}</span>`;}).join("")
        +`<span class="calcount">${nb} bill${nb===1?"":"s"}</span>`
        +(venue?`<span class="calwhere">${esc(venue)}</span>`:"")
        +`<span class="caret"></span></summary>`
        +`<div class="calbody">`);
      const oneSlot=byslot.size===1;
      byslot.forEach((items,sk)=>{
        const q=sk.split("\u0000");
        if(!oneSlot){
          const [w,c]=kindWord(q[1]);
          out.push(`<p class="calslot">`
            +(q[0]?`<span class="caltime">${esc(clock(q[0]))}</span>`:"")
            +`<span class="calkind ${c}">${esc(w)}</span>`
            +(q[2]&&!venue?`<span class="calwhere">${esc(q[2])}</span>`:"")
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
  out.push(`<p class="note">Anyone may attend and speak at a public hearing,
    or sign in for or against without speaking. An executive session is where
    the committee votes on what to recommend; it is open to watch but not to
    testify.</p></section>`);
  return out.join("");
}

// A bill's own page, by the year its number belongs to. yearOf is what the
// rest of this file uses, so a calendar link and a card link agree.
function billHref(id){
  const y=(typeof yearOf==="function"&&yearOf(id))||null;
  return y?`bill/${y}/${String(id).toLowerCase()}.html`
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
  if(!rows.length)
    return `<section class="cal"><h2>Upcoming session</h2>
      <p class="note">Nothing is scheduled for this committee in the next two
      weeks. The General Court sits from January to June.</p></section>`;
  return calendarBlock(rows,"Upcoming session");
}

function renderCommittee(c){
  // Counted for the term the page is showing, not across every term. "Bills
  // (107)" over a list of 32 is the tab disagreeing with itself.
  const tabs=[["Bills",cmteBills(c).length],["Sessions",cmteSessions(c).length]];
  const body=[()=>renderCommitteeBills(c),()=>renderCommitteeSessions(c)][PAGE_TAB]
    ||(()=>"");
  // Who they are, then what is coming, then the record. The calendar sits
  // above the term control because it is not about a term: it is about this
  // week, and a reader who came to find out whether they can still turn up
  // and speak should not have to scroll past nineteen years of bills.
  return renderCommitteeHead(c) + renderCommitteeUpcoming(c)
    + termControl() + tabStrip(tabs) + pagePane(body());
}

// ------------------------------------------------------------------ boot ---
function renderPage(){
  if(!PAGE)return;
  const el=$("#results");
  if(!el)return;
  el.innerHTML = PAGE.kind==="member" ? renderMember(PAGE.data)
                                      : renderCommittee(PAGE.data);
  syncCards([...openCards]);
  showDay();
  showSelectedTab(el);
}

// The tabs, the cards and the filter selects on these two pages. Kept apart
// from the bill list's handlers, which end at "if(PAGE)return" because they
// finish by calling render() and would draw the search over the record.
document.addEventListener("click",e=>{
  if(!PAGE)return;
  const t=e.target.closest("[data-pt]");
  if(t){PAGE_TAB=+t.dataset.pt;
    tabAddress(slugOf(PAGE.kind==="member"?MEMBER_TABS:COMMITTEE_TABS,PAGE_TAB));
    renderPage();return;}
  // Not data-more: that one belongs to the bill list, is read by the
  // handler above this in the file, and calls render(), which would draw the
  // search over the member's record.
  const vm=e.target.closest("[data-vmore]");
  if(vm){PAGE.vshow=(PAGE.vshow||VOTES_SHOWN)+VOTES_SHOWN;renderPage();return;}
  const ct=e.target.closest(".card .tab[data-t]");
  if(ct){openTab[ct.closest(".card").dataset.id]=ct.dataset.t;renderPage();return;}
  const head=e.target.closest(".chead");
  if(head&&!e.target.closest("a")){
    const id=head.closest(".card").dataset.id;
    if(openCards.has(id)){openCards.delete(id);renderPage();}
    else openBill(id);
    return;}
});
document.addEventListener("change",e=>{
  if(!PAGE)return;
  const f=e.target.dataset.pf;
  if(!f)return;
  PAGE[f]=e.target.value;
  // A status chosen in one term rarely exists in another, so keeping it
  // emptied the list while the control still read the old value -- a reader
  // seeing nothing, with nothing on screen saying why.
  //
  // The term also moves the GLOBAL term, because dkey and yearOf resolve a
  // bill number within it: a card opened on a 2023-2024 page would otherwise
  // have fetched the 2025-2026 bill of that number and shown its history.
  // THE TERM'S BILLS, FETCHED. idxRow looks a bill up in IDX, and IDX only
  // ever held the term the site opened on -- so choosing an earlier term
  // here left every bill on the page with no title and its number unspaced,
  // on the sponsored tabs as well as this one. Nothing asked for that term's
  // index because nothing on a record page ever had.
  if(f==="term"){PAGE.status="";term=PAGE.term;
    ensureTerm(PAGE.term).then(renderPage);}
  // A narrower filter over a list already expanded to 800 rows left the
  // reader at the bottom of a list of 40.
  if(f==="vfilter"||f==="vparty"||f==="term")PAGE.vshow=0;
  renderPage();
});

// The term and sort dropdowns order and filter a list of bills. On a page
// showing one member or one committee there is no such list, and a control
// that does nothing is worse than no control.
function hideListControls(){
  ["#year","#sort"].forEach(sel=>{
    const el=$(sel); if(!el)return;
    el.hidden=true;
    const lab=el.previousElementSibling;
    if(lab&&lab.tagName==="LABEL")lab.hidden=true;
  });
  const hint=document.querySelector(".qhint");
  if(hint)hint.hidden=true;
  const q=$("#q");
  if(q)q.placeholder="Search all bills";
}

/* AND ON A PAGE THAT IS NOT A LIST OF BILLS AT ALL, the box itself goes.
   A town page led with "Search all bills" above the name of the town; so did
   a member's page, a committee's, and every civics page. The Bills tab is
   one click away on all of them.
   Hidden rather than removed: app.js binds seven ids in this row when it
   loads and shell.py asserts every one of them is in the template, because a
   missing #q once drew 33,683 blank pages. [hidden] on the wrapper takes it
   out of the layout and out of what a screen reader walks, and leaves every
   binding where it was. */
function hideBillSearch(){
  const row=document.querySelector(".searchrow");
  if(row)row.hidden=true;
}

/* AND ON A PAGE WHOSE RECORD IS ALREADY IN THE HTML, the whole of the search
   goes. A town page, a directory listing, a civics page: the app's only job
   there is to take down the rail, the counter and the two pickers that
   belong to a list of bills it is not going to draw.
   A function rather than six lines inside the .then, because it is needed in
   two places now -- when the index arrives and when it does not. Nothing in
   it reads the index, which is the reason it can be called from the catch. */
function staticChromeDown(){
  const fac=$("#facets"); if(fac){fac.innerHTML="";fac.hidden=true;}
  const sh=document.querySelector(".shell"); if(sh)sh.classList.add("nofacets");
  const c=$("#count"); if(c)c.textContent="";
  hideListControls();
}

// Every term this record has anything in, newest first. Worked out once,
// when the file lands, so every tab and the control above them agree.
function recordTerms(kind,d){
  const t=new Set();
  if(kind==="member"){
    (d.sponsored||[]).forEach(b=>b.term&&t.add(b.term));
    // The term the vote was cast in, as the Votes tab files it (voteYear): a
    // member whose only ballots of a term are on rules questions, which carry
    // no bill and so no bill year, otherwise had no term at all, and a page
    // with no term drew its attendance as a note with no figures in it.
    (d.votes||[]).forEach(v=>{const x=termOfYear(voteYear(v));if(x)t.add(x);});
  }else{
    Object.keys(d.bills||{}).forEach(x=>x&&t.add(x));
    (d.sessions||[]).forEach(s=>s.term&&t.add(s.term));
  }
  return [...t].sort().reverse();
}

// The address of one sitting on a committee's page. Built from the date
// alone, because that is the only thing about a sitting that a calendar
// entry elsewhere on the site already knows.
function dayId(date){ return "day-" + String(date || ""); }

/* LANDING ON A DAY. A committee page renders more than once -- the record
   arrives, then the term index, then home.json -- and each render replaces
   #results wholesale, so anything scrolled to is thrown away and rebuilt.
   This runs after every render: it re-marks the day named in the address,
   and scrolls to it ONCE per address, so a later render does not yank a
   reader back to where they arrived after they have started reading.

   It is needed at all because openPage returns before the hash reader that
   serves bills, and nothing else on a committee page has ever read the
   address. */
let dayLanded = "", dayTried = "";
function showDay(){
  const want = decodeURIComponent(location.hash.slice(1) || "");
  if(!/^day-\d{4}-\d{2}-\d{2}$/.test(want)){ dayLanded=""; dayTried=""; return; }
  document.querySelectorAll(".cday.at").forEach(e=>e.classList.remove("at"));
  let el = document.getElementById(want);
  // THE SITTINGS ARE ON THE OTHER TAB. A committee page opens on Bills, and
  // the days live under Sessions -- so a calendar entry linking to a sitting
  // would have landed on a tab that does not contain it and found nothing at
  // all. Being asked for a day IS asking for that tab. Guarded so it is tried
  // once: a date the page genuinely does not hold must not bounce the reader
  // between tabs.
  if(!el && PAGE && PAGE.kind === "committee"
     && PAGE_TAB !== COMMITTEE_TABS.sessions && dayTried !== want){
    dayTried = want;
    PAGE_TAB = COMMITTEE_TABS.sessions;
    renderPage();                      // which calls this again, tab in hand
    return;
  }
  if(!el) return;                      // no sitting of that date on this page
  el.classList.add("at");
  if(dayLanded === want) return;
  dayLanded = want;
  el.scrollIntoView({block:"start"});
}

window.addEventListener("hashchange", function(){ if(PAGE) showDay(); });

function openPage(kind,ref){
  PAGE={kind,data:null,terms:[],term:"",status:"",vfilter:"",
        vparty:"",vshow:0};
  // A member's page has three tabs and a committee's two. Carried over, a
  // member's Votes tab (2) opened a committee on a tab it does not have, and
  // the page drew nothing under the strip.
  PAGE_TAB=0;
  // Or the tab its own address names.
  const tabs_=kind==="member"?MEMBER_TABS:COMMITTEE_TABS;
  if(tabs_[tabFromPath()])PAGE_TAB=tabs_[tabFromPath()];
  // The search chrome belongs to the search. Left up, the facet panel offered
  // filters for a list that is not on screen and the counter read "2,234 of
  // 2,234 bills" beside one member's name.
  const fac=$("#facets"); if(fac){fac.innerHTML="";fac.hidden=true;}
  const sh=document.querySelector(".shell"); if(sh)sh.classList.add("nofacets");
  const c=$("#count"); if(c)c.textContent="";
  const sy=$("#synhint"); if(sy)sy.textContent="";
  hideListControls();
  const url=DATA(kind==="member"?`legislators/${ref}.json`
                                :`committee/${ref}.json`);
  const el=$("#results");
  if(el)el.innerHTML=`<p class="src">Loading&hellip;</p>`;
  fetch(url).then(r=>{
    if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for this file`);
    return r.json();
  }).then(d=>{
    PAGE.data=d;
    PAGE.terms=recordTerms(kind,d);
    // The global term follows the page's, because dkey and yearOf resolve a
    // bill number inside it and a card opened here fetches by that key.
    PAGE.term=PAGE.terms[0]||"";
    if(PAGE.term)term=PAGE.term;
    renderPage();
    // And on the way in: a member whose newest term is not the site's opens
    // on their own, whose index nothing has asked for either.
    if(PAGE.term)ensureTerm(PAGE.term).then(renderPage);
    // What is scheduled, for the committee page's own calendar. 13 KB, asked
    // once, and asked AFTER the record it belongs to -- the page is useful
    // without it and must not wait on it. A failure leaves UPCOMING null,
    // which draws nothing rather than claiming nothing is scheduled.
    if(kind==="committee"&&UPCOMING===null){
      fetch(DATA("home.json"))
        .then(r=>r.ok?r.json():null)
        .then(h=>{UPCOMING=(h&&h.upcoming)||[];renderPage();})
        .catch(()=>{});
    }
  })
    .catch(e=>{if(el)el.innerHTML=`<div class="empty"><b>This page's record did
      not load.</b><br><br><code>${esc(e.message||e)}</code><br><br>
      The file it wanted is <code>${esc(url)}</code>.</div>`;});
}

// A HUNDRED AT A TIME. render() drew the first 400 matches and told the
// reader to narrow the search to see the rest, which is the site asking a
// person to do its work: the 2025-2026 term alone matches 2,234 bills with no
// filters at all, and 400 cards is a slow first paint for a list nobody has
// scrolled yet.
//
// This stays ONE renderer, which is the rule here -- render(true) draws the
// same list one page longer rather than a second function appending to it.
// The observer at the bottom of the list is what calls it.
// PAGE_SIZE, not PAGE: PAGE is already the member-or-committee page
// object declared above, and shadowing it emptied every legislator page.
const PAGE_SIZE = 100;
let SHOWN = PAGE_SIZE;

function render(more){
  // Any change to the result set starts again at the first hundred. Every
  // existing caller passes nothing, so only the observer extends.
  if(!more)SHOWN=PAGE_SIZE;
  // Page scroll only. The facet panel restores itself inside renderFacets,
  // synchronously, which is the only way it survives the repaint.
  const _y=window.scrollY;
  // A search in words is ordered by how well each bill matches it, until the
  // reader picks an order themselves; a list with no search, or a search for
  // bill numbers, keeps number order.
  if(!sortChosen){
    const want=query.trim()&&!billNumbers(query)?"best":"num";
    if(sortBy!==want){sortBy=want;const so=$("#sort");if(so)so.value=want;}
  }
  const rows=sortRows(IDX.filter(b=>matches(b)));
  const inTerm=IDX.filter(inTermOf).length;
  // Say when a search matched on a synonym, so nobody wonders why a bill about
  // firearms turned up for "guns".
  const used=query.trim()?[...new Set(groupsFor(query.trim()).flatMap(g=>
    g.alts.filter(x=>x!==g.word&&x!==stem(g.word)).slice(0,3)))]:[];
  const sh=$("#synhint");
  if(sh)sh.textContent=used.length&&!billNumbers(query)
    ? `also matching: ${used.join(", ")}` : "";
  const ids0=billNumbers(query);
  // A focused view is one bill. The count describes a list that is not on
  // screen, and on a bill's own page it read "2,234 of 2,234 bills in the
  // 2025-2026 term" above a single bill.
  // A COUNT THAT SAYS N OF N SAYS NOTHING. Until something narrows the list,
  // "2,234 of 2,234 bills in the 2025-2026 term" is the first line a reader
  // meets and it cannot be false; the picker beside it already names the term.
  // It appears when a search or a filter has taken something out.
  const narrowed=rows.length!==inTerm;
  $("#count").textContent=focused?""
    :ids0
    ?`${rows.length} matching ${termPhrase()}`
    :narrowed
    ?`${rows.length.toLocaleString()} of ${inTerm.toLocaleString()} ${termNoun()} ${termPhrase()}`
    :"";
  // Same number, different term: say so instead of an empty page.
  const elsewhere=ids0&&!rows.length
    ? IDX.filter(b=>ids0.includes(b.id.toUpperCase())&&b.term&&b.term!==term)
    : [];
  const ids=billNumbers(query);
  // A focused bill is shown on its own, whether or not the current filters
  // would have listed it -- somebody arriving on a shared link has no filters
  // and should still see the bill.
  //
  // DECLARED BEFORE ITS FIRST USE, which is not a style point: const is in the
  // temporal dead zone until this line runs, so reading fb above it threw
  // "Cannot access 'fb' before initialization" and took the whole of render()
  // with it. The page loaded, the data loaded, and nothing listed.
  const fb=focused?(rows.find(b=>b.id===focused)||IDX.find(b=>b.id===focused)):null;
  document.querySelector(".shell").classList.toggle("focused",!!fb);
  const shown=fb?[fb]:rows.slice(0,SHOWN);
  // WHAT AN LSR IS, in front of the list rather than behind a link, because
  // nobody who has not worked in the building knows the word. Asked for on 18
  // September: "A brief explainer of what LSRs are should appear at the top of
  // the page", and confirmed that it is right to say some are withdrawn.
  // innerHTML rather than textContent here because the explainer carries a
  // link; every value in it is the site's own, none is a reader's.
  const req=META.requests&&term===META.requests.term;
  $("#summary").className=req?"count lsrnote":"count";
  if(req){
    $("#summary").innerHTML=`<b>These are requests, not bills yet.</b> Before a
      bill exists, a member asks the Office of Legislative Services to draft
      one, and it is given a request number. A request has a title and a prime
      sponsor and nothing else &mdash; no text, no committee, no hearing &mdash;
      until it is drafted and filed, when it becomes a numbered bill and picks
      up the rest of its record. Some are withdrawn first and never become
      anything. These will be replaced by the 2027 bills themselves as they are
      filed.`;
  }else{
    $("#summary").textContent=fb?"":(ids&&ids.length>1
      ?`Showing ${rows.length} of the ${ids.length} bills you listed.`:"");
  }
  // Counted over what is on screen, not over the whole result set, so the
  // number beside a heading always matches the cards under it.
  const grpN={};
  if(sortBy==="status")for(const b of shown)grpN[b.status||""]=(grpN[b.status||""]||0)+1;
  $("#results").innerHTML=(fb?`<button class="backto" data-back="1">\u2190 Back to
    bill search</button>`:"")+((rows.length||fb)?shown.map((b,gi,arr)=>`
    ${!fb&&sortBy==="status"&&(gi===0||arr[gi-1].status!==b.status)
      ?`<h2 class="grp">${esc(b.status||"No status recorded")}
         <span>${grpN[b.status||""]}</span></h2>`:""}
    ${b.lsr?lsrCardHtml(b):cardHtml(b,!!fb)}`).join("")+((!fb&&rows.length>SHOWN)?`<p class="more" id="more">Showing ${
      shown.length.toLocaleString()} of ${rows.length.toLocaleString()} — <button
      class="link" data-more="1">show ${Math.min(PAGE_SIZE,rows.length-SHOWN)} more</button></p>`:"")
    :(elsewhere.length
      ?`<div class="empty"><b>Not in the ${esc(term)} term.</b><br><br>
        ${elsewhere.map(b=>`${esc(b.n)} exists in the
          <button class="link" data-term="${esc(b.term)}">${esc(b.term)}</button>
          term — ${esc(b.title||"")}`).join("<br>")}</div>`
      :emptyResult()));
  // Reaching the end of the list is the request for more of it. The button
  // in the sentinel does the same thing for a keyboard or a reader that never
  // fires an intersection.
  const sentinel=$("#more");
  if(sentinel){
    if(window._moreObs)window._moreObs.disconnect();
    if(window.IntersectionObserver){
      window._moreObs=new IntersectionObserver(es=>{
        if(es.some(e=>e.isIntersecting)){SHOWN+=PAGE_SIZE;render(true);}
      },{rootMargin:"400px"});
      window._moreObs.observe(sentinel);
    }
  }
  syncCards(rows.filter(b=>openCards.has(b.id)).map(b=>b.id));
  showSelectedTab($("#results"));
  renderFacets();
  if(window.scrollY!==_y)window.scrollTo(0,_y);
}

// Opening a bill pushes its own address, so the view can be shared and
// reloaded -- and a reload lands on the static page, which is the one a
// crawler and a reader without JavaScript get. Going back never reloads
// anything, so the search comes back exactly as it was: same filters, same
// query, same place on the page.
function focusBill(id,href){
  focusY=window.scrollY;
  focused=id;
  // /bill/2026/hb1123 -- the address a person would paste, and the same
  // shape a legislator's page uses.
  //
  // This used to push "?q=hb1123#2026/HB1123", because the static page's own
  // address belonged to a DIFFERENT document: reloading it fetched the same
  // facts in another layout with no charts, and a reader who pressed F5 got a
  // page that had changed under them. That stopped being true when the
  // renderer was unified. /bill/2026/hb1123.html is this app with one bill
  // open, so reloading the clean address reopens exactly this view.
  const _y=yearOf(id);
  if(_y){
    try{history.pushState({focus:id},"",
      `${BASE}bill/${_y}/${id.toLowerCase()}`);}catch(_){}
  }
  openBill(id);
  window.scrollTo(0,0);
}

function unfocus(y){
  // On a bill's own page there is no list behind it to back out to: the
  // reader arrived at that bill directly. Drawing two thousand cards under
  // an address that names one bill would be the wrong page at the wrong URL,
  // so leaving the bill means leaving the page.
  if(window.GR_STANDALONE){location.href=BASE+"bills";return;}
  // Back out to where the reader was standing when they opened the bill --
  // except when they got here by typing a new search, where the old position
  // belongs to a list that is no longer on screen.
  if(y===undefined)y=focusY;
  focused=null;
  // Leaving a bill named in the address would mean the next refresh reopened
  // it, which is not where the reader is standing.
  // Back to the list's own address rather than the bill's.
  try{history.pushState({},"",BASE+"bills");}catch(_){}
  render();
  window.scrollTo(0,y);
}

window.addEventListener("popstate",e=>{
  const f=e.state&&e.state.focus;
  if(f){focused=f;openBill(f);window.scrollTo(0,0);}
  else if(focused)unfocus();
});

function openBill(id){
  openCards.add(id);
  if(detail[dkey(id)]){repaint();return;}
  repaint();
  // What went wrong, not merely that something did.
  //
  // This used to report "Detail unavailable" and nothing else, which is how a
  // refresh on a bill page stayed unexplained through two wrong guesses at the
  // cause. A 404, a file that is not JSON, and a refused connection all looked
  // identical from the outside, and they are three different problems.
  const yr=yearOf(id);
  // THE RECORD TRAVELS INSIDE THE PAGE unless it is large. A bill's page used
  // to be a 4.3 KB shell that fetched its record as a second round trip, and
  // for half the bills here that record is 1.3 KB -- so the envelope cost
  // more than the letter and took an extra journey to deliver it. 33,585 of
  // 33,683 records are now in the page; the 98 over 100 KB, which are almost
  // all roll call ballots, keep a file and the page says where it is.
  const url=DATA(`bill/${yr}/${id.toLowerCase()}`);
  const fail=(why)=>{
    detail[dkey(id)]={events:[],rollcalls:[],stations:[],reports:[],sponsors:[],
      documents:[],amendments:[],next_step:"Detail unavailable",
      _error:why+"\n"+url};
    repaint();
  };
  const take=(txt,where)=>{
    let d;
    try{ d=JSON.parse(txt); }
    catch(_){ throw new Error(`${where} arrived but is not JSON. It starts: ${
      txt.slice(0,80).replace(/\s+/g," ")}`); }
    detail[dkey(id)]=d; repaint();
  };

  // ON A BILL'S OWN PAGE THE ANSWER IS ALREADY HERE. Either the record
  // itself, or -- for the 98 too large to travel inside a page -- the address
  // of the file holding it. Reading the pointer from this document rather
  // than fetching the page again saves HB1442 from asking for itself before
  // asking for its votes.
  const mine=window.GR_BILL&&
    String(window.GR_BILL).toUpperCase()===`${yr}/${id}`.toUpperCase();
  if(mine){
    const own=document.getElementById("gr-data");
    if(own){
      try{ take(own.textContent,"this page's record"); }catch(e){ fail(e.message); }
      return;
    }
    const here=document.querySelector('meta[name="gr-data"]');
    if(here){
      const u=DATA(here.getAttribute("content").replace(/^\//,""));
      fetch(u).then(r=>{
        if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for ${u}`);
        return r.text();
      }).then(txt=>take(txt,"the record file"))
        .catch(e=>fail(e.message||String(e)));
      return;
    }
  }

  // Otherwise fetch the bill's page and read the record out of it. A script
  // tag with an id is one DOMParser call; the alternative was pulling a
  // JavaScript assignment out of the text by hand.
  // Extensionless, because that is the address the host serves and the one
  // the canonical names. A plain static file server -- the one used to look
  // at this site locally -- serves only the .html form, so a 404 is retried
  // there. In production the first request succeeds and the retry never runs.
  fetch(url).then(r=>r.ok?r:fetch(url+".html")).then(r=>{
    if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for this page`);
    return r.text();
  }).then(html=>{
    const doc=new DOMParser().parseFromString(html,"text/html");
    const node=doc.getElementById("gr-data");
    if(node)return take(node.textContent,"the record in that page");
    const ptr=doc.querySelector('meta[name="gr-data"]');
    if(!ptr)throw new Error("that page carries neither the record nor a link to it");
    const u=DATA(ptr.getAttribute("content").replace(/^\//,""));
    return fetch(u).then(r=>{
      if(!r.ok)throw new Error(`the server answered HTTP ${r.status} for ${u}`);
      return r.text();
    }).then(txt=>take(txt,"the record file"));
  }).catch(e=>fail(e.message||String(e)));
}

document.addEventListener("click",e=>{
  // Swap the still for a real player only when asked. Eight iframes on one
  // page would each pull YouTube's payload before anyone pressed play.
  const stub=e.target.closest("[data-embed]");
  if(stub){
    const [vid,from,pid]=stub.dataset.embed.split("|");
    stub.outerHTML=`<iframe id="yt_${pid}" allow="autoplay" allowfullscreen
      src="https://www.youtube-nocookie.com/embed/${vid}?start=${from}&autoplay=1&enablejsapi=1"
      title="Hearing recording"></iframe>`;
    return;
  }
  const seek=e.target.closest("[data-seek]");
  if(seek){
    const [pid,t]=seek.dataset.seek.split("|");
    const box=document.querySelector(`[data-player="${pid}"]`);
    let f=document.getElementById("yt_"+pid);
    if(!f){
      // Load it AT the time that was asked for. This used to click the stub,
      // which builds the player at the opening offset -- a few seconds to five
      // minutes before the bill -- and then post seekTo to an iframe created
      // one line earlier. YouTube's API is not listening until the frame has
      // loaded, so the message went nowhere and the video sat at a different
      // time from the button that had just been pressed. That is the mismatch
      // between the player's own clock and the times printed beside it.
      const st=box&&box.querySelector("[data-embed]");
      if(st){
        const [vid,,p2]=st.dataset.embed.split("|");
        st.dataset.embed=`${vid}|${Math.max(0,Math.floor(Number(t)))}|${p2}`;
        st.click();
        f=document.getElementById("yt_"+pid);
        if(f)f.scrollIntoView({block:"nearest"});
        return;
      }
    }
    if(f){
      // seekTo over postMessage keeps playback going instead of reloading.
      f.contentWindow.postMessage(JSON.stringify(
        {event:"command",func:"seekTo",args:[Number(t),true]}),"*");
      f.scrollIntoView({block:"nearest"});
    }
    return;
  }
  // These three live INSIDE an expanded bill card, which a member's and a
  // committee's page now draw too, so they redraw whichever view is up.
  const an=e.target.closest(".anmore");
  if(an){
    const id=an.dataset.an;
    anOpen.has(id)?anOpen.delete(id):anOpen.add(id);
    clampAnalysis();
    return;
  }
  const seg=e.target.closest("[data-seg]");
  if(seg){const[bid,i,which]=seg.dataset.seg.split("|");const k=`${bid}|${i}`;
    segSel[k]=segSel[k]===which?null:which;repaint();return;}
  const rt=e.target.closest("[data-routine]");
  if(rt){const id=rt.dataset.routine;
    showRoutine.has(id)?showRoutine.delete(id):showRoutine.add(id);
    repaint();return;}
  const f=e.target.closest("[data-full]");
  if(f){const k=f.dataset.full;fullOpen.has(k)?fullOpen.delete(k):fullOpen.add(k);repaint();return;}
  // "Show 3 more", in How it got here: the hidden lines open where they are,
  // with no redraw, and the keyboard lands on the first of them, since the
  // button it was on is gone. jOpen keeps them open through the next redraw.
  const jm=e.target.closest("[data-jmore]");
  if(jm){
    jOpen.add(jm.dataset.jmore);
    const ul=jm.closest(".jl");
    const shut=ul?[...ul.querySelectorAll("li[hidden]")]:[];
    for(const li of shut)li.hidden=false;
    jm.closest("li").remove();
    if(shut[0]){shut[0].tabIndex=-1;shut[0].focus({preventScroll:true});}
    return;}
  const g=e.target.closest(".fhead");
  if(g){openGroups.has(g.dataset.g)?openGroups.delete(g.dataset.g):openGroups.add(g.dataset.g);renderFacets();return;}
  // The phone's filter disclosure. The class goes on .shell rather than on
  // the panel because the stylesheet has to move three things -- the button,
  // the panel and the results -- and one of them is the element being shown.
  const ftb=e.target.closest("#ftoggle");
  if(ftb){
    const sh=document.querySelector(".shell");
    const open=sh.classList.toggle("fopen");
    ftb.setAttribute("aria-expanded",open?"true":"false");
    return;}
  const un=e.target.dataset.unpick;
  if(un){sel.sponsor.delete(un);render();return;}
  // Left click opens in place; a modified or middle click falls through to
  // the anchor and gets the static page in a new tab, which still works.
  // On a record page there is no search list to come back to, so the arrow
  // is left to be an ordinary link to the bill's own page.
  const dt=PAGE?null:e.target.closest("a.detail");
  if(dt&&e.button===0&&!e.metaKey&&!e.ctrlKey&&!e.shiftKey&&!e.altKey){
    e.preventDefault();
    focusBill(dt.closest(".card").dataset.id,dt.getAttribute("href"));return;}
  if(e.target.closest("[data-back]")){history.back();return;}
  // The same thing the observer does, for a keyboard, a reader, or a
  // browser with no IntersectionObserver.
  if(e.target.closest("[data-more]")){SHOWN+=PAGE_SIZE;render(true);return;}
  // Everything below reads .card. A member's or a committee's page has none,
  // so a tab click here threw on tab.closest(".card").dataset and the tab did
  // nothing. Those pages have their own handler, registered above.
  if(PAGE)return;
  const head=e.target.closest(".chead");
  if(head&&!e.target.closest("a")){const id=head.closest(".card").dataset.id;
    if(term===ALL_TERMS){const own=head.closest(".card").querySelector("a.detail");
      if(own){location.href=own.href;return;}}
    if(openCards.has(id)){openCards.delete(id);render();}else openBill(id);return;}
  const tab=e.target.closest(".tab");
  if(tab){
    const cid=tab.closest(".card").dataset.id;
    openTab[cid]=tab.dataset.t;
    // WHEREVER A BILL IS OPEN, not only on its own page. GR_BILL is set by
    // build_bill_pages and by nothing else, so opening a bill from the search
    // page and switching tabs left the address on /bill/2012/hb1181 however
    // many tabs you walked -- the reader could not link to what they were
    // looking at, and the same click on the same card put a different address
    // in the bar depending on how they arrived. focused===cid is the real
    // condition: it says this card is the one open, which is what makes its
    // tab the page's subject. openBill already pushes the bill's own address
    // in the search view, so there is a path here for tabAddress to append to.
    if(focused===cid)tabAddress(slugOf(BILL_TABS,tab.dataset.t));
    // The versions index is fetched when the tab is opened and not before,
    // which is the whole reason it is a separate file.
    if(tab.dataset.t==="6"){
      const row=IDX.find(x=>x.id===cid);
      if(row)needVersions(row);
    }
    render();return;}
  // Picking a version, or switching between what changed and the full text.
  const vb=e.target.closest("[data-ver]");
  if(vb){
    const [key,j]=vb.dataset.ver.split("|");
    VPICK[key]=+j;
    const row=IDX.find(x=>verKey(x)===key);
    if(row){needVersions(row);}
    render();return;}
  const vm=e.target.closest("[data-vmode]");
  if(vm){
    const [key,mode]=vm.dataset.vmode.split("|");
    VMODE[key]=mode;
    const row=IDX.find(x=>verKey(x)===key);
    if(row){needVersions(row);}
    render();return;}
  // An amendment's own text, opened one at a time.
  const va=e.target.closest("[data-vamd]");
  if(va){
    const [key,j]=va.dataset.vamd.split("|");
    const ix=VERS[key], a=ix&&(ix.amendments||[])[+j];
    if(a&&VTEXT[a.text_url]===undefined){
      VTEXT[a.text_url]=undefined;
      fetch(DATA(a.text_url.replace(/^\//,"")))
        .then(r=>r.ok?r.text():Promise.reject(new Error("HTTP "+r.status)))
        .then(x=>{VTEXT[a.text_url]=x;repaint();})
        .catch(()=>{VTEXT[a.text_url]=null;repaint();});
    }
    render();return;}
  const jt=e.target.closest("[data-term]");
  if(jt){term=jt.dataset.term;$("#year").value=term;forgetCardState();render();return;}
  // A part of a search that found nothing, offered on its own.
  const jq=e.target.closest("[data-q]");
  if(jq){query=jq.dataset.q;$("#q").value=query;render();return;}
  if(e.target.id==="clear"){Object.values(sel).forEach(s=>s.clear());render();return;}
});
document.addEventListener("change",e=>{
  if(PAGE)return;                       // the facet checkboxes are not drawn there
  const f=e.target.dataset.f;if(!f)return;
  e.target.checked?sel[f].add(e.target.value):sel[f].delete(e.target.value);render();});
document.addEventListener("input",e=>{
  if(e.target.id==="sbox"){sponsorFilter=e.target.value;renderFacets();
    const b=document.getElementById("sbox");if(b){b.focus();b.setSelectionRange(b.value.length,b.value.length);}}});
// Running a search from one bill's own view means leaving that bill, so it
// waits to be told. Everywhere else the list narrows as you type, which is
// what a search box on a list should do.
function submitSearch(){
  query=$("#q").value;
  // From a member's or a committee's page, searching means going to the bill
  // search -- that is where results are drawn. Running render() here wrote
  // the list over the record instead, and the only way back was a reload.
  if(PAGE||window.GR_STATIC){
    location.href=BASE+"bills"+(query?`?q=${encodeURIComponent(query)}`:"");
    return;
  }
  // From a bill's own view, running the search means leaving that bill. Back
  // out to the top: the scroll position from before it was opened belongs to
  // a list that is no longer the one on screen.
  if(focused){unfocus(0);return;}
  // On the list the results have already narrowed as they typed, so there is
  // nothing to run. Return means they have finished typing: let go of the
  // keyboard and bring the first result up to where they are looking.
  render();
  $("#q").blur();
  const first=$("#results")&&$("#results").querySelector(".card");
  if(first)first.scrollIntoView({block:"start",behavior:"smooth"});
}
$("#q").addEventListener("input",e=>{
  // No live narrowing on a record page: there is no list under it to narrow,
  // and render() would replace the record with one.
  if(focused||PAGE||window.GR_STATIC)return;
  query=e.target.value;
  render();
});

$("#q").addEventListener("keydown",e=>{
  if(e.key==="Enter"){e.preventDefault();submitSearch();}
});
$("#qgo").addEventListener("click",submitSearch);
// "/" JUMPS TO THE SEARCH BOX, BUT NEVER OUT OF SOMETHING BEING TYPED IN.
// The only exemption used to be the bill-search box itself, so anywhere else
// the key was eaten. Checked with a real keypress rather than a synthetic
// event, in the Report a problem box on /bill/2025/hb1.html: keydown key "/",
// target TEXTAREA, isTrusted true -- the textarea's value did not change and
// focus moved to #q. A reader typing "and/or", a date, or a citation into the
// box we give them for telling us the record is wrong loses the character and
// their place. The hint that taught this shortcut is no longer on any page, so
// nobody is pressing "/" on purpose; what remains is a key that goes missing.
//
// Every field that takes typing is left alone -- the header search (#findq) is
// an input and was eating it too, and select and contenteditable are here so
// the next field added does not have to rediscover this. The whole report box
// is exempt including its Send button: nothing inside the box a reader is
// filling in should move them out of it.
const typingIn=el=>!!el&&(/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)
  ||el.isContentEditable||!!(el.closest&&el.closest(".report")));
document.addEventListener("keydown",e=>{
  if(e.key==="/"&&!typingIn(e.target)){e.preventDefault();$("#q").focus();$("#q").select();}
  // Tabs carry role="tab", and a screen reader user is told they are tabs, so
  // the arrow keys have to work. They did nothing before.
  const tab=e.target.closest&&e.target.closest(".tab");
  if(tab&&(e.key==="ArrowLeft"||e.key==="ArrowRight"||e.key==="Home"||e.key==="End")){
    const tabs=[...tab.parentElement.querySelectorAll(".tab")];
    const i=tabs.indexOf(tab);
    const to=e.key==="Home"?0:e.key==="End"?tabs.length-1
      :(i+(e.key==="ArrowRight"?1:-1)+tabs.length)%tabs.length;
    // The click redraws the strip, which destroyed the tab just focused and
    // sent focus to <body>: every arrow press lost the keyboard's place.
    // Focus goes back to the tab of the same identity in the new strip.
    const next=tabs[to];
    const again=next.id?`#${CSS.escape(next.id)}`
      :next.dataset.pt!==undefined?`.tab[data-pt="${next.dataset.pt}"]`:null;
    e.preventDefault();next.click();
    const fresh=again&&document.querySelector(again);
    (fresh||next).focus();
  }});


// THE SITTING DAY'S VOTE RINGS, DRAWN BY THE FUNCTION THE BILL PAGES USE.
//
// build_session_pages.py writes the day's narrative as static HTML and leaves
// each counted vote as an empty .svote with the tally beside it in words. This
// fills them, calling simpleDonut -- the same renderer, not a copy of it.
// Drawing a second ring in Python that merely looked like this one is the
// mistake this repository keeps a check under, and a session page holds up to
// twenty votes, which is twenty chances for the two to drift apart.
//
// A ROLL CALL IS DRAWN AS A DIVISION IS. simpleDonut is the anonymous ring;
// the named ballots are on the bill's own page, which the markup already links
// to, because a day with eleven roll calls would otherwise carry four thousand
// names. The ring says the same thing either way -- the difference between a
// roll call and a division is who is named, not how the count should look.
//
// Nothing here is required for the page to be true: the count, which side
// prevailed and what it did to the bill are all in the HTML already.
(function(){
  var tag=document.getElementById("sessvotes");
  if(!tag||typeof simpleDonut!=="function")return;
  var votes;
  try{ votes=JSON.parse(tag.textContent||"[]"); }catch(e){ return; }
  if(!votes.length)return;
  var slots=document.querySelectorAll(".svote[data-vote]");
  for(var i=0;i<slots.length;i++){
    var n=parseInt(slots[i].getAttribute("data-vote"),10);
    var v=votes[n];
    if(!v)continue;
    try{
      var box=document.createElement("div");
      // bid and i only build a selection key inside simpleDonut; the day has
      // no bill of its own at this point, so they are a label, not a lookup.
      box.innerHTML=simpleDonut(v,"session",n);
      slots[i].appendChild(box.firstChild||box);
    }catch(e){ /* the tally in the markup stands on its own */ }
  }
})();


// THE READER'S OWN DATE IN A CITATION, not the build's. shell.py writes the
// build date into every .citeday so a page read without JavaScript still gives
// a true date for the page rather than "Accessed ." -- and a reader who has
// JavaScript gets the day they actually read it, which is what every one of
// those four formats means by "accessed".
//
// IN ONE FORM, "24 Sept. 2026", whatever language the browser is set to (the
// person, 24 September). This was toLocaleDateString(undefined, ...), so an
// English citation read "24 septembre 2026" in a French browser and
// "September 24, 2026" in an American one. CITE_MONTHS is shell.py's list,
// and preflight holds the two to one answer for every month.
const CITE_MONTHS=["Jan.","Feb.","Mar.","Apr.","May","June","July","Aug.",
  "Sept.","Oct.","Nov.","Dec."];
function citeDay(d){ return d.getDate()+" "+CITE_MONTHS[d.getMonth()]+" "+d.getFullYear(); }
(function(){
  var els=document.querySelectorAll(".citeday");
  var s=citeDay(new Date());
  for(var i=0;i<els.length;i++)els[i].textContent=s;
  // The Copy buttons are written hidden, so a page read without JavaScript
  // offers none that does nothing; here they work, so here they show.
  var bs=document.querySelectorAll("[data-citecopy]");
  for(var j=0;j<bs.length;j++)bs[j].hidden=false;
})();

// COPY, beside each form of "Cite this page" (the person, 24 September).
// writeText is called inside the click itself, which is what lets a browser
// allow it. Where it is refused or absent the form's text is selected
// instead, so Ctrl+C does the rest, and either way the result is said in the
// block's status line for a reader who cannot see the button change.
document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest("[data-citecopy]");
  if(!b)return;
  const form=document.getElementById(b.getAttribute("data-citecopy"));
  if(!form)return;
  const name=b.getAttribute("data-citename")||"";
  const st=document.getElementById("citestate");
  const say=m=>{if(st)st.textContent=m;};
  // A form's text as it reads: BibTeX's line breaks are real ones, and a
  // no-break space is pasted as a space.
  const text=String(form.textContent||"").replace(/ /g," ").trim();
  const done=()=>{
    b.textContent="Copied";
    say(`The ${name} citation is copied.`);
    setTimeout(()=>{b.textContent="Copy";},2000);
  };
  const pick=()=>{
    try{
      const sel=window.getSelection&&window.getSelection();
      const r=document.createRange&&document.createRange();
      if(sel&&r){r.selectNodeContents(form);sel.removeAllRanges();sel.addRange(r);}
    }catch(_){}
    say(`The ${name} citation is selected: press Ctrl+C, or Command+C on a Mac, to copy it.`);
  };
  if(navigator.clipboard&&navigator.clipboard.writeText)
    navigator.clipboard.writeText(text).then(done,pick);
  else pick();
});
// ONE PANE OPEN AT A TIME in the row above a heading. Follow's pane and the
// citation's open over the page from the same corner, so opening one shuts
// the other rather than stacking one on top of it.
document.addEventListener("toggle",e=>{
  const d=e.target;
  if(!d||!d.open||!d.closest||!d.closest("#pageacts"))return;
  document.querySelectorAll("#pageacts details[open]").forEach(o=>{if(o!==d)o.open=false;});
},true);
