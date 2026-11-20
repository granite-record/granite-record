// The most parts a search may have and still be offered with one left out.
const FEWER_MOST=6;
// NOTHING FOUND is still an answer with somewhere to go. A search of several
// parts that no bill has all of says which parts do find bills on their own,
// with how many, as searches to run -- rather than a blank page for a reader
// who does not know a bill number and has no other way in.
/* WHAT IS OFFERED IS COUNTED AFTER THE PAGE HAS SAID "NO BILLS MATCH". Each
   offer is a whole search run over every bill -- a word on its own, the
   search with one word left out, the word a misspelling sounds like -- and
   a search of five words is eleven of them. Counted before anything was
   drawn, 200 words pasted into the box stopped the page for 17 seconds, and
   on All terms an ordinary search that listed nothing held it for one to
   two (2 October). So the sentence is drawn at once and the offers are
   counted one at a time, the page free to answer between them, and written
   under it when the last is in. A search typed meanwhile drops them. */
/* A NAME TYPED IN THE BOX IS OFFERED THE SPONSOR FILTER (17 October 2026).
   Since that day a name lists no bill here (A NAME IS NOT WHAT A BILL IS
   ABOUT), and a reader who typed "alice wade" was most likely after her
   bills: an empty list with nowhere to go would read as though she had filed
   nothing. So when the search lists nothing and every word typed belongs to
   the name of a sponsor or co-sponsor of the bills in view, one line offers
   the Sponsor filter for that person, which is where their bills are listed.
   Never when the words also list a bill: the person asked for the line only
   where nothing else matched.
   A word may be the start of a word of the name ("tim", for Timothy Lang)
   so long as another is a whole word of it, the way a name is typed from
   memory. "rep" or "senator" must agree with the chamber the index gives the
   prime sponsor, and a co-sponsor the index gives no chamber is not ruled
   out by it. The three people with the most bills in view at most: a surname
   that more share is for the filter's own name box to narrow. */
const HINT_TITLE=Object.assign(Object.create(null),
  {rep:"Rep.",reps:"Rep.",representative:"Rep.",sen:"Sen.",senator:"Sen."});
const HINT_MOST=3;
// A name's letters as a search reads them: lower case, accents off, a hyphen
// or a full stop a space, and an apostrophe, straight or curly, left out
// (the owner's test, 6 November 2026): a phone types "O’Connor", and some
// readers "OConnor", for the O'Connor the record names.
const hintWords=s=>String(s||"").normalize("NFD").replace(/[̀-ͯ]/g,"")
  .toLowerCase().replace(/['‘’]/g,"").split(/[^a-z0-9]+/).filter(Boolean);
/* WHAT A SPONSOR IS CALLED, AND WHICH ONE (12 November 2026: "in old sessions
   searching for legislators didn't appear to work correctly or allow you to
   search for former legislators"). The bills of 1989 to 1998 name a sponsor by
   the surname the printed bill gave, sometimes an initial before it ("Allen",
   "F. Riley"), with the seat beside it ("Hills 44") and no roster to look the
   person up in: no first name, no party, no member page. Three different
   Allens were one name, so the Sponsor filter listed one "Allen" with the
   bills of all three, and a full name typed from memory ("frank riley") fitted
   no word of "F. Riley". Now a sponsor with no member page and a seat is that
   name and that seat (spKey), as the General Court's own list tells two
   people of one surname apart, and a typed word fits an initial that starts
   it (nameFits). A sponsor with a member page is still their name alone.
   The seat as the record gave it for that term is what each is listed with
   (sponsorShow), their party beside it where the record gives one. */
const SEAT_RE=/\(([^()]*)\)\s*$/;
function spKey(b){
  const n=b.sponsor||"";
  // A 1989-1998 prime sponsor the General Court's record for the bill names
  // (sponsor_person, past_roster.py): their full name is theirs alone, and the
  // seat is kept only for a row still left as printed.
  if(!n||b.sponsor_slug||b.sponsor_party||b.sponsor_person)return n;
  const m=SEAT_RE.exec(b.sponsor_label||"");
  return m&&/\d/.test(m[1])?`${n} (${m[1]})`:n;
}
// The words typed against the words of one name: each is a whole word of it,
// or the start of a longer one, or the first letter of an initial the name
// has; at least one is a whole word (or an initial's name), so "rep" alone
// or "a" is no one's.
function nameFits(want,parts){
  if(!want.some(w=>parts.includes(w)))return false;
  return want.every(w=>parts.includes(w)
    ||(w.length>2&&parts.some(x=>x.length>w.length&&x.startsWith(w)))
    ||(w.length>2&&parts.some(x=>x.length===1&&w.startsWith(x))));
}
// What was typed, read for a name: the title said ("rep", "senator") and the
// words that are not stop words.
function nameWords(q){
  let title="";
  const want=[];
  for(const w of hintWords(q)){
    if(HINT_TITLE[w])title=HINT_TITLE[w];
    else if(!STOPSET.has(w))want.push(w);
  }
  return {title,want};
}
// Whether the title typed agrees with the one a label begins with: a label
// that names none (a sponsor matched to nobody) agrees with any; a
// member-elect's "Rep.-elect" is Rep.
const titleAgrees=(title,label)=>{
  const t=/^(Rep\.|Sen\.)/.exec(String(label||""));
  return !title||!t||t[1]===title;
};
/* A REQUEST'S SPONSOR BY EVERY NAME THE SITE PRINTS FOR THEM (the pre-release
   review of 13 November 2026). The request list spells a sponsor its own way
   ("Lee Nyquist", "Jim Creighton"); the card prints the election's spelling
   ("Lee C. Nyquist") and the page it links to the member's own ("James
   Creighton"), and a name copied off either found none of their requests.
   build_lsrs writes those other names as `sponsor_names`, and a name typed as
   any one of them is the sponsor's: in the box (requestByName), in the offer
   of the Sponsor filter (sponsorHint) and in that filter's own box
   (sponsorFits). Each name is fitted on its own (namesFit), so a word of one
   and a word of another are not a name; and initials alone are no one's, so
   "c" does not list Lee C. Nyquist's requests. */
const sponsorNames=b=>b.sponsor?[b.sponsor,...(b.sponsor_names||[])]:[];
const namesFit=(want,names)=>want.some(w=>w.length>1)&&names.some(n=>nameFits(want,hintWords(n)));
function sponsorHint(q,rows){
  const {title,want}=nameWords(q);
  if(!want.length)return [];
  const who=new Map();
  for(const b of rows||[]){
    for(const name of b.cosp?[b.sponsor,...b.cosp]:[b.sponsor]){
      if(!name)continue;
      const key=name===b.sponsor?spKey(b):name;
      let p=who.get(key);
      if(!p)who.set(key,p={name:key,n:0,label:"",names:[]});
      p.n++;
      for(const x of name===b.sponsor?sponsorNames(b):[name])if(!p.names.includes(x))p.names.push(x);
      if(name===b.sponsor&&!p.label&&b.sponsor_label){
        p.label=String(b.sponsor_label).replace(/\s*\(.*$/,"");
        // Two people of one surname are told apart by their seat.
        if(key!==name)p.label+=` (${key.slice(name.length+2,-1)})`;
      }
    }
  }
  const out=[];
  for(const p of who.values()){
    if(!namesFit(want,p.names))continue;
    if(!titleAgrees(title,p.label))continue;
    out.push(p);
  }
  // A surname the bills give a co-sponsor with no seat is not offered beside
  // the same surname with one: it is one of them, not a third person.
  const lone=out.filter(p=>!p.label&&out.some(q=>q.name.startsWith(p.name+" (")));
  return out.filter(p=>!lone.includes(p))
    .sort((a,b)=>b.n-a.n||(a.name<b.name?-1:a.name>b.name?1:0)).slice(0,HINT_MOST);
}
// A SPONSOR, AS THE SPONSOR FILTER LISTS THEM: the name as the term's record
// has it, with the seat and the party they held then (the row's own label,
// which build_site_v2 writes from the roster for that term), and on All Terms
// the newest term's that names them. A co-sponsor, whom the record gives only
// as a name, and a name the label does not carry, is the name alone.
const SP_LABELS=Object.create(null);
// And a request sponsor's other names (sponsorNames), by the same key, for the
// Sponsor filter's box.
const SP_NAMES=Object.create(null);
function noteSponsors(term,rows){
  const m=SP_LABELS[term]||(SP_LABELS[term]=Object.create(null));
  const o=SP_NAMES[term]||(SP_NAMES[term]=Object.create(null));
  for(const b of rows){
    if(!b.sponsor||!b.sponsor_label)continue;
    const k=spKey(b);
    // A member-elect's title goes with the rest ("Rep.-elect Colin Mitchell (R)",
    // build_lsrs.elect_title): the filter lists the name.
    if(!(k in m))m[k]=String(b.sponsor_label).replace(/^(Rep\.|Sen\.)(-elect)?\s*/,"");
    if(b.sponsor_names&&!(k in o))o[k]=b.sponsor_names;
  }
}
// The terms the Sponsor filter lists: the one in view, or every term and the
// requests on All Terms.
const spTerms=()=>term===ALL_TERMS?((META&&META.terms)||[]).concat(META&&META.requests?[META.requests.term]:[])
  :[term];
function sponsorShow(v){
  for(const t of spTerms()){const l=SP_LABELS[t]&&SP_LABELS[t][v];if(l)return l;}
  return v;
}
function sponsorAlso(v){
  for(const t of spTerms()){const n=SP_NAMES[t]&&SP_NAMES[t][v];if(n)return n;}
  return [];
}
// A REQUEST'S SPONSOR IS FOUND BY NAME IN THE BOX (the owner, 12 November
// 2026: "you can't search by legislator name"). A bill's is not: since 17
// October a name lists no bill, and the Sponsor filter is where a person's
// bills are found (A NAME IS NOT WHAT A BILL IS ABOUT, above). A request has a
// title and a sponsor and nothing else, so for it the name IS the other thing
// to search by, and is read as sponsorHint reads it: every word typed is a
// word of the prime sponsor's name (any the site prints for them,
// sponsorNames) or a co-sponsor's, or the start of one ("bail" is not Rep.
// Bailey: a single word must be a whole word of the name). A request whose
// title has the words lists as it did, as well.
function requestByName(b,q){
  if(!b.lsr)return false;
  const {title,want}=nameWords(q);
  if(!want.length)return false;
  if(namesFit(want,sponsorNames(b))&&titleAgrees(title,b.sponsor_label))return true;
  // A co-sponsor is given as a name alone, so a title typed cannot rule one out.
  return (b.cosp||[]).some(c=>namesFit(want,[c]));
}
// The Sponsor filter for one person, as an address /bills reads (addressList):
// the term kept, the search left out, since the name typed lists nothing.
function sponsorHref(name){
  const p=new URLSearchParams(),terms=(META&&META.terms)||[];
  if(term&&term!==defaultTerm(META))p.set("term",term);
  p.append("sponsor",name);
  return `${BASE}bills?${p.toString()}`;
}
function sponsorHintLine(list){
  if(!list.length)return "";
  const named=p=>esc(p.label||p.name);
  const a=(p,text)=>`<a class="qsponsor" href="${esc(sponsorHref(p.name))}" data-sponsor="${
    esc(p.name)}">${text}</a>`;
  return list.length===1
    ?`<br><br>Looking for bills sponsored by ${named(list[0])}? ${a(list[0],"Use the sponsor filter")}.`
    :`<br><br>Looking for bills sponsored by ${list.map(p=>a(p,named(p))).join(" or ")}? `
      +"Choose one to use the sponsor filter.";
}
/* A FILTER OFFERED FOR ITS NAME, AS YOU TYPE (the person, 24 October 2026:
   "Searching for a topic in the searchbar in the laws page or the bills page
   should show a dropdown if you type in the name of a filter like 'housing'
   asking if you want to view all bills with the housing topics or all bills
   referred to the housing committee, and clicking it will select that filter
   without you having to manually scroll through all the list of topics").

   WHAT MATCHES. The words typed against each filter's name, word by word,
   letters only, case and accents set aside, a plural as its singular (stem),
   and the words that name no subject -- "and", "of", "bill" (STOPSET) --
   left out on both sides. "House" and "Senate" name a chamber, not a
   subject: typed alone they offer nothing, and typed with a subject they
   must be the committee's own -- "senate education" is not House Education
   Funding. A filter is offered where every word typed is a word of its name,
   the last perhaps only begun, three letters at least ("hous" offers
   Housing: the reader is still typing it); or where every word of its name
   was typed, with others besides ("affordable housing" offers Housing). A
   filter already chosen is not offered again, and a bill number or a statute
   offers nothing. A committee or a tag is offered on a solid match only
   (the owner, 18 November 2026: "only with a solid match so that ordinary
   searches don't accidentally have an unrelated dropdown pop-up"): a word
   begun counts for it only where it begins one word of all the term's
   names, so "trans" offers no committee and no tag by name (filterOffers'
   `only`); and on the bill search no filter is offered that would list no
   bill (billOffers).

   WHAT CHOOSING ONE DOES. What ticking it in the list does -- the list
   narrows, its group opens with the tick in it, the address names it -- and
   the words it stands for leave the box, since the filter now says them:
   "housing" leaves the box empty, "affordable housing" leaves "affordable".
   Return without choosing searches the words as it always has.

   A COMBOBOX, WAI-ARIA's pattern, as find.js's address box is (filterCombo):
   the box says it controls the list and whether it is open; the arrow keys
   move through the offers, aria-activedescendant naming the one they are on;
   Return takes it; Escape shuts the list and only the list; a status line
   says how many there are. Each offer is 44px high. The Laws page offers its
   own filters through these same two functions (build_rsa's LANDING_JS). */
const FO_MOST=8,FO_KIND=4,FO_MIN=3,FO_WAIT=150;
const FO_CHAMBER=new Set(["house","senate"]);
const foWords=s=>String(s||"").normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase()
  .replace(/&/g," and ").split(/[^a-z0-9]+/).filter(w=>w&&!STOPSET.has(w));
// A word typed against a word of a name: the same, the same as a singular,
// or -- the last word typed, nothing after it -- the start of it.
function foWord(t,v,open){
  return t===v||stem(t)===stem(v)||(open&&t.length>=FO_MIN&&v.startsWith(t));
}
// How the words typed fit a name: null, or {how, used}. `how` 0 is the name
// itself, 1 the name begun or a part of it, 2 the name among other words;
// `used` the words typed that it stands for.
function foFit(typed,open,name){
  const vs=foWords(name),subj=vs.filter(v=>!FO_CHAMBER.has(v));
  const ts=typed.filter(t=>!FO_CHAMBER.has(t));
  if(!ts.length||!subj.length)return null;
  if(typed.some(t=>FO_CHAMBER.has(t)&&!vs.includes(t)&&vs.some(v=>FO_CHAMBER.has(v))))return null;
  const last=typed.length-1;
  if(ts.every(t=>subj.some(v=>foWord(t,v,open&&t===typed[last]))))
    return {how:ts.length===subj.length&&subj.every(v=>ts.some(t=>foWord(t,v,false)))?0:1,
            used:typed.map((_,i)=>i)};
  const used=[];
  for(const v of subj){
    const i=typed.findIndex((t,j)=>!used.includes(j)&&foWord(t,v,false));
    if(i<0)return null;
    used.push(i);
  }
  typed.forEach((t,i)=>{if(FO_CHAMBER.has(t)&&vs.includes(t))used.push(i);});
  return {how:2,used};
}
// The filters offered for what is typed, best first: each group a filter's
// key, its values as [value, name, count], and `say(name, value)`, the
// offer's words in HTML. Each offer carries `rest`, the words typed that it
// does not stand for. A group with `only`, a Set of the words of every name
// offered beside it (foVocab), is offered on a solid match only: a word
// still being typed counts as begun only where every word of those names it
// begins is one word, or that word made longer ("envir" is Environment's,
// and Environmental's; "trans" begins Transit, Transfer, Transparency and
// Transportation, so offers none of them).
function filterOffers(q,groups){
  const raw=String(q||""),typed=foWords(raw),open=!/\s$/.test(raw);
  if(raw.trim().length<FO_MIN||!typed.length)return [];
  const out=[],last=typed[typed.length-1];
  const several=only=>{const s=new Set();for(const w of only)if(w.startsWith(last))s.add(stem(w));
    return s.size>1&&!Array.from(s).some(a=>Array.from(s).every(b=>b.startsWith(a)));};
  for(const g of groups){
    const found=[],begun=open&&!(g.only&&several(g.only));
    for(const [v,name,n] of g.values||[]){
      const fit=foFit(typed,begun,name);
      if(fit)found.push({key:g.key,v,name,n,how:fit.how,html:g.say(name,v),
        rest:typed.filter((_,i)=>!fit.used.includes(i)).join(" ")});
    }
    found.sort((a,b)=>a.how-b.how||(b.n||0)-(a.n||0)||(a.name<b.name?-1:a.name>b.name?1:0));
    out.push(...found.slice(0,g.most||FO_KIND));
  }
  return out.slice(0,FO_MOST);
}
// The words of filters' names, [value, name, ...] each, put into `only`:
// filterOffers' reading of what a word half typed may begin. A chamber's
// word names no subject, and is left out as foFit leaves it out.
function foVocab(only,values){
  for(const x of values||[])for(const w of foWords(x[1]))if(!FO_CHAMBER.has(w))only.add(w);
  return only;
}
// The box `inp` and a list under it, made a combobox. `o.offers(text)` gives
// the offers, `o.choose(offer)` takes one; Return is the caller's, which asks
// enter() first: true where an offer the arrows are on was taken.
function filterCombo(inp,o){
  const lid=inp.id+"-offers";
  const list=document.createElement("ul");
  list.id=lid;list.className="qoffers";list.hidden=true;
  list.setAttribute("role","listbox");list.setAttribute("aria-label",o.label||"Filters that match");
  const say=document.createElement("span");
  say.className="sr";say.setAttribute("role","status");
  inp.setAttribute("role","combobox");inp.setAttribute("aria-autocomplete","list");
  inp.setAttribute("aria-expanded","false");inp.setAttribute("aria-controls",lid);
  if(inp.parentNode){inp.parentNode.appendChild(list);inp.parentNode.appendChild(say);}
  let rows=[],act=-1,timer=0;
  const draw=()=>{
    list.innerHTML=rows.map((r,i)=>`<li role="option" class="qoffer" id="${lid}-${i}" data-i="${i}"
      aria-selected="${i===act}"><span>${r.html}</span>${r.n!=null
      ?`<span class="c">${Number(r.n).toLocaleString()}</span>`:""}</li>`).join("");
    list.hidden=!rows.length;
    inp.setAttribute("aria-expanded",rows.length?"true":"false");
    if(act>=0){
      inp.setAttribute("aria-activedescendant",`${lid}-${act}`);
      const on=document.getElementById(`${lid}-${act}`);
      if(on&&on.scrollIntoView)on.scrollIntoView({block:"nearest"});
    }else inp.removeAttribute("aria-activedescendant");
  };
  const shut=()=>{clearTimeout(timer);if(rows.length||act>=0){rows=[];act=-1;draw();}say.textContent="";};
  const update=()=>{
    rows=o.offers(inp.value)||[];act=-1;draw();
    say.textContent=!rows.length?"":rows.length===1
      ?"1 filter matches; the down arrow chooses it."
      :`${rows.length} filters match; the down arrow chooses one.`;
  };
  const choose=i=>{const r=rows[i];if(!r)return;shut();o.choose(r);};
  inp.addEventListener("input",()=>{clearTimeout(timer);timer=setTimeout(update,FO_WAIT);});
  inp.addEventListener("keydown",e=>{
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){
      if(!rows.length)update();
      if(!rows.length)return;
      e.preventDefault();
      act=e.key==="ArrowDown"?(act+1)%rows.length:act<=0?rows.length-1:act-1;
      draw();
    }else if(e.key==="Escape"){
      // The list, and not the page's own Escape, nor the box's clearing.
      if(rows.length){e.preventDefault();e.stopPropagation();shut();}
    }else if(e.key==="Tab")shut();
  });
  inp.addEventListener("blur",shut);
  // Pressing an offer keeps the focus in the box, so the box is not left,
  // and the list shut, before the click lands.
  list.addEventListener("mousedown",e=>e.preventDefault());
  list.addEventListener("click",e=>{
    const li=e.target&&e.target.closest&&e.target.closest("[data-i]");
    if(!li)return;
    e.stopPropagation();choose(+li.getAttribute("data-i"));
  });
  return {list,say,update,shut,rows:()=>rows,active:()=>act,
    enter(){if(rows.length&&act>=0){choose(act);return true;}shut();return false;}};
}
// THE BILL SEARCH'S OFFERS: a Topic, a Committee or a Tag of the bills in
// the term, by name, and a Sponsor by theirs where it is certain
// (sponsorOffer); each with the count it would list -- the filters already
// chosen kept, this one added, and the words it does not stand for searched;
// one that would list none is not offered.
// IN THE TERM AN OFFER LANDS IN (the review of 26 October 2026). With a bill
// open on /bills and the picker turned, the list's term waits for the bill to
// be closed (heldTerm), and taking an offer closes it (takeOffer, unfocus):
// the offers were counted and chosen in the open bill's term and landed in
// the held one -- 2023-2024's HB 104 open, 2025-2026 chosen, "housing" offered
// "Topic Housing 62" and "House Special Committee on Housing 9", and they
// listed 117 bills and none. So they are worked out in the held term, as the
// list they lead to will be; `term` is put back at once, since the open bill
// is still looked up in its own (render).
function billOffers(q){
  if(!IDX.length)return [];
  const t=String(q||"").trim();
  if(billNumbers(t)||RSA_SHAPE.test(t))return [];
  const own=term;
  if(heldTerm!==null)term=heldTerm;
  try{
    const inYear=IDX.filter(inTermOf);
    const vals=k=>{const c={};inYear.forEach(b=>facetVals(b,k).forEach(v=>{
      if(v&&!sel[k].has(v))c[v]=(c[v]||0)+1;}));return Object.keys(c).map(v=>[v,v,c[v]]);};
    const topics=vals("topic"),
      // "House No Committee Assignment" is a filter, and no committee.
      committees=vals("committee").filter(x=>!/\bno committee\b/i.test(x[0]));
    // A committee or a tag on a solid match only (the owner, 18 November
    // 2026), against the words of every name the term offers (filterOffers).
    const only=foVocab(foVocab(new Set(),topics),committees);
    // TAGS:BEGIN
    foVocab(only,vals("tag").map(([v])=>[v,(tagOf(v)||{}).name||v]));
    // TAGS:END
    const offers=filterOffers(q,[
      {key:"topic",values:topics,say:offerTopic},
      {key:"committee",values:committees,say:offerCommittee,only}]);
    // TAGS:BEGIN
    tagOffers(q,offers,vals,only);
    // TAGS:END
    const who=sponsorOffer(q,inYear,vals);
    if(who){offers.unshift(who);offers.splice(FO_MOST);}
    for(const o of offers){
      const was=query;
      query=o.rest;sel[o.key].add(o.v);
      try{o.n=IDX.filter(b=>matches(b)).length;}
      finally{sel[o.key].delete(o.v);query=was;}
    }
    // An offer that would list no bill is not made: "campaign finance" is
    // no offer of the Finance committees, whose bills never say "campaign".
    return offers.filter(o=>o.n>0);
  }finally{term=own;}
}
// AN OFFER'S WORDS, in the page's language (lang/<code>.json's bills.offer_*):
// a topic by its name; a committee by the name the header's search gives it
// (find.js, findName), its chamber first and "Committee" after it where the
// name does not already say it -- "House Housing Committee", "House Special
// Committee on Housing"; a person by the title and name their chip carries.
const offerTopic=v=>tr("bills.offer_topic","All bills with the topic <b>{name}</b>",{name:esc(v)});
const offerCommittee=v=>tr("bills.offer_committee","All bills referred to the <b>{name}</b>",
  {name:esc(/\bcommittee\b/i.test(v)?v:`${v} Committee`)});
/* A LEGISLATOR OFFERED BY NAME (the owner, 18 November 2026: "typing in
   their topic, tag, legislator, or committee, will show a dropdown that says
   'All bills filed by Rep. Alice Wade' the same way it does for 'All bills
   with the topic Housing' and it applies the filter for you when you click
   it ... It should only show with a solid match so that ordinary searches
   don't accidentally have an unrelated dropdown pop-up"). The Sponsor filter
   for one person of the term, offered first, in the words their chip
   carries: the row's sponsor_label without the seat and party ("Rep. Alice
   Wade", "Sen. Sharon Carson"), a member-elect's "Rep.-elect" in the
   page's language as a card says it (CARD_ELECT_TITLE), and a sponsor of
   1989-1998 with no member page by the name and seat the filter tells them
   apart by (spKey). Taken as any offer is (takeOffer): the person ticked,
   the box emptied.
   ONLY A SOLID MATCH. What was typed, read as a name is (hintWords), a
   title before it set aside ("rep", "senator", and "elect"), must be
     - the whole of one of the person's names, an initial being no part of
       it ("lee nyquist" is Lee C. Nyquist), or its first two whole words
       or more ("mary jane" of Mary Jane Smith);
     - or, after a title, whole words that begin or end it: "rep packard",
       "senator carson";
   and no other sponsor of the term whose title agrees may have every word
   typed as a whole word of a name of theirs -- find.js's rule for a person
   by their whole name (findClear, 3). ONE WORD WITH NO TITLE IS NEVER A
   NAME, a first name no more than a surname: "skip", "jack", "rich",
   "carol", "jordan", "moore" and "white" are ordinary searches as often as
   they are names, so "alice" alone offers nothing and "alice wade" offers
   Rep. Alice Wade. Nor is a name shared by several. A word still being
   typed is not yet a whole word: "alice wad" offers nothing. null where
   nothing fits. `rows` the term's bills, `vals` billOffers' reading of a
   filter's values in it: only a person the Sponsor filter lists there is
   offered. */
const FO_NAME_SKIP=new Set(["elect"]);
function sponsorOffer(q,rows,vals){
  // A chip's own words pasted in, "Rep. Alice Wade (D - Hills 22)", are the name.
  const raw=String(q||"").replace(/\s*\([^()]*\)\s*$/,"");
  if(raw.trim().length<FO_MIN)return null;
  const typed=hintWords(raw);
  let title="",lead=0;
  while(lead<typed.length&&(HINT_TITLE[typed[lead]]||FO_NAME_SKIP.has(typed[lead]))){
    title=HINT_TITLE[typed[lead]]||title;lead++;}
  const t=typed.slice(lead);
  if(!t.length||(t.length<2&&!title))return null;
  const can=new Set(vals("sponsor").map(x=>x[0]));
  if(!can.size)return null;
  const who=new Map();
  for(const b of rows){
    if(!b.sponsor)continue;
    const k=spKey(b);
    if(!can.has(k))continue;
    let p=who.get(k);
    if(!p)who.set(k,p={k,names:[],label:"",term:""});
    for(const n of sponsorNames(b))if(!p.names.includes(n))p.names.push(n);
    // On All Terms, the newest term's label (sponsorShow).
    if(b.sponsor_label&&(!p.label||String(b.term||"")>p.term)){
      p.term=String(b.term||"");
      p.label=String(b.sponsor_label).replace(/\s*\(.*$/,"")+(k!==b.sponsor?` (${k.slice(b.sponsor.length+2,-1)})`:"");
    }
  }
  // A co-sponsor, listed where "Include co-sponsored bills" is ticked, by name alone.
  for(const k of can)if(!who.has(k))who.set(k,{k,names:[k],label:"",term:""});
  const same=(a,b)=>a.length===b.length&&a.every((w,i)=>w===b[i]);
  const starts=(n,w)=>w.length<=n.length&&w.every((x,i)=>x===n[i]);
  const ends=(n,w)=>w.length<=n.length&&w.every((x,i)=>x===n[n.length-w.length+i]);
  const fits=p=>p.names.some(name=>{
    const n=hintWords(name),bare=n.filter(w=>w.length>1);
    return [n,bare].some(v=>v.length&&(same(t,v)||(t.length>1&&starts(v,t))
      ||(title&&(starts(v,t)||ends(v,t)))));
  });
  const has=p=>p.names.some(name=>{const n=hintWords(name);return t.every(w=>n.includes(w));});
  const agree=[...who.values()].filter(p=>titleAgrees(title,p.label));
  const found=agree.filter(fits);
  if(found.length!==1||agree.some(p=>p!==found[0]&&has(p)))return null;
  const p=found[0];
  const shown=(p.label||p.k).replace(CARD_ELECT_TITLE,(m,h)=>h==="Sen"
    ?tr("elect.title_sen","Sen.-elect"):tr("elect.title_rep","Rep.-elect"));
  return {key:"sponsor",v:p.k,name:shown,n:0,how:0,rest:"",
    html:tr("bills.offer_sponsor","All bills filed by <b>{name}</b>",{name:esc(shown)})};
}
// TAGS:BEGIN
/* THE TAGS' OFFERS (design 6.1): "All bills tagged Attorney General" for a
   tag whose name the words typed begin, as a topic or a committee is
   offered; and first, where the whole search is a word that leads to a tag
   or a topic ("weed": the topic Cannabis), that one, standing for all of
   it. `offers` is billOffers' list, which this adds to, `vals` its
   reading of a filter's values in the term, and `only` the words of the
   term's names: a tag, like a committee, on a solid match only. */
function tagOffers(q,offers,vals,only){
  if(!TAGLIST.length)return;
  const named=t=>tr("bills.offer_tag","All bills tagged <b>{name}</b>",{name:esc(t)});
  const tv=vals("tag").map(([v,_n,c])=>[v,(tagOf(v)||{}).name||v,c]);
  const byName=filterOffers(q,[{key:"tag",values:tv,say:named,only}]);
  const to=TAGWORDS.get(tagKey(q))||"",at=to.indexOf(":"),k=to.slice(0,at),v=to.slice(at+1);
  const first=[];
  if(k==="tag"&&tv.some(x=>x[0]===v)&&!byName.some(o=>o.v===v))
    first.push({key:"tag",v,name:tagOf(v).name,n:0,how:0,html:named(tagOf(v).name),rest:""});
  if(k==="topic"&&vals("topic").some(x=>x[0]===v)&&!offers.some(o=>o.key==="topic"&&o.v===v))
    first.push({key:"topic",v,name:v,n:0,how:0,html:offerTopic(v),rest:""});
  offers.unshift(...first);
  offers.push(...byName);
  offers.splice(FO_MOST);
}
// TAGS:END
// An offer taken, as ticking it in the list would be. Off the list -- a
// bill's own page, a member's, a committee's -- it is taken where the list
// is: /bills with the filter in its address, which /bills reads.
function takeOffer(o){
  if(PAGE||window.GR_STATIC||window.GR_STANDALONE){
    const p=new URLSearchParams(),newest=((META&&META.terms)||[])[0];
    if(window.GR_STANDALONE&&!PAGE&&term&&newest&&term!==newest)p.set("term",term);
    if(o.rest)p.set("q",o.rest);
    p.append(o.key,o.v);
    location.href=BASE+"bills?"+p.toString();
    return;
  }
  if(focused)unfocus(0);
  query=o.rest;$("#q").value=o.rest;clearTimeout(QDRAW);addressSearch(o.rest);
  sel[o.key].add(o.v);openGroups.add(o.key==="party"?"sponsor":o.key);
  render();
}
let OFFERS={key:null,html:""};
function emptyResult(){
  const gs=query.trim()&&!billNumbers(query)?groupsFor(query.trim()):[];
  // While the bills' text is on its way, "no bills match" is not known yet.
  if(gs.length&&textState()==="loading")
    return `<div class="empty">Reading the bills&rsquo; text&hellip;</div>`;
  const inTerm=IDX.filter(inTermOf);
  // The parts: each group of a search of several, or each word of a phrase
  // that was the whole search ("teacher pay" finds nothing this term).
  const words=gs.length>1?gs.map(g=>g.word)
    :gs.length===1&&gs[0].word.includes(" ")?gs[0].word.split(" ").filter(w=>!STOPSET.has(w)):[];
  const key=[query.trim(),term,inTerm.length,TEXTGEN,WORDS].join("\u0001");
  if(OFFERS.key!==key){
    OFFERS={key,html:""};
    const count=q=>{const g2=readShort(queryGroups(q),inTerm);
      return inTerm.filter(b=>g2.every(g=>groupWeight(b,g)>0)).length;};
    let did="",who="";
    const parts=[],fewer=[];
    const jobs=[];
    // A word no bill has ever used, offered as the word it sounds like -- an
    // offer, and never a list drawn in its place (see A SEARCH THAT LISTS
    // NOTHING, above). Only where the search itself lists nothing in the
    // term: a list a filter emptied is not a spelling.
    // And a sponsor's name, offered the Sponsor filter (sponsorHint), under
    // the same condition. A name in the bills is a word and not a
    // misspelling, so it is offered no other word.
    if(gs.length)jobs.push(()=>{
      if(inTerm.some(b=>gs.every(g=>groupWeight(b,g)>0)))return;
      who=sponsorHintLine(sponsorHint(query.trim(),inTerm));
      if(who)return;
      const sp=spelling(gs,inTerm);
      if(sp&&sp.need)wantWords();
      else if(sp)did=`<br><br>Did you mean <button class="link" data-q="${esc(sp.q)}">${
        esc(sp.q)}</button> (${sp.n.toLocaleString()})?`;
    });
    // A search of three words or more, with one of them left out: "college
    // students voting" lists nothing, because the bill on student
    // identification at the polls never says "college", and "students voting"
    // lists it (2 October). Offered like the words on their own, and never
    // drawn in the search's place. For a search of three to FEWER_MOST
    // parts, and not for a pasted paragraph.
    if(gs.length>2&&gs.length<=FEWER_MOST)gs.forEach((g,i)=>jobs.push(()=>{
      const q=gs.filter((x,j)=>j!==i).map(x=>x.word).join(" "),n=count(q);
      if(n)fewer.push([q,n]);}));
    words.forEach(w=>jobs.push(()=>{const n=count(w);if(n)parts.push([w,n]);}));
    const offer=list=>list.map(([w,n])=>
      `<button class="link" data-q="${esc(w)}">${esc(w)}</button> (${n.toLocaleString()})`)
      .join(" &middot; ");
    const step=()=>{
      if(OFFERS.key!==key)return;
      const job=jobs.shift();
      if(job){job();setTimeout(step,0);return;}
      // A name's own line stands alone: "On their own: senator (6)" beside
      // the offer for Sen. Carson was a list of guesses at a search that is
      // already answered.
      // A word on its own as a sentence (the audit of 25 October 2026, S7):
      // "'2027' alone matches 4 bills", where "On their own: 2027 (4)" left
      // a reader to work out what the number in brackets counted.
      OFFERS.html=who||`${did}${fewer.length?`<br><br>Without one word: ${offer(fewer)}`:""}${
        parts.length?`<br><br>${parts.map(([w,n])=>`&lsquo;<button class="link" data-q="${
          esc(w)}">${esc(w)}</button>&rsquo; alone matches ${n.toLocaleString()} bill${
          n===1?"":"s"}`).join(" &middot; ")}`:""}`;
      const at=document.getElementById("offers");
      if(at)at.innerHTML=OFFERS.html;
    };
    setTimeout(step,0);
  }
  // termPhrase() brings its own preposition ("in the 2025-2026 term",
  // "across all terms"), so the "in the" that used to sit here made the
  // sentence read "No bills match in the in the 2025-2026 term." -- or, with
  // the picker on All terms, "in the across all terms". The two callers at
  // the count line pass it bare and were always right; this one doubled it.
  // WHAT IS LEFT TO TRY, AND ONLY THAT (the second review of 7 November
  // 2026): the not-found page's search of every term landed here, with no
  // filter ticked and All Terms chosen, on "Try removing a filter, or a
  // different term".
  const tries=[Object.keys(sel).some(k=>sel[k].size)?"removing a filter":"",
               term!==ALL_TERMS?"a different term":""].filter(Boolean);
  return `<div class="empty">No bills match${words.length?" all of that":""}
    ${esc(termPhrase())}.${gs.cut?` ${CUTNOTE}.`:""}<span id="offers">${OFFERS.html
    }</span>${requestOffer()}${tries.length?`<br><br>Try ${tries.join(", or ")}.`:""}</div>`;
}
/* A REQUEST'S NUMBER, OFFERED ITS LIST (the audit of 25 October 2026, S5:
   "LSR 2027-0002" pasted into the bill search listed nothing, and next
   session's requests were reached only by the term menu). A search that
   reads as a request's number -- "LSR ...", or the requests' own year and a
   number, "2027-0002" -- is offered their list, by its own name, with the
   search kept. Requests stay out of every term's list and count (inTermOf);
   this is one line where none of the term's bills matched. */
function requestOffer(){
  const R=META&&META.requests;
  if(!R||!R.term||term===R.term)return "";
  const m=/^\s*(?:lsr(?![a-z])|(\d{4})\s*-\s*\d)/i.exec(query);
  if(!m||(m[1]&&m[1]!==reqYear()))return "";
  return `<br><br>Looking for a bill request? <button class="link" data-term="${esc(R.term)}">${
    esc(R.label||reqYear()+" Bill Requests")}</button>.`;
}
// Said wherever a search was longer than is read (queryGroups, MAXWORDS).
const CUTNOTE="Only the first twelve words of a search are read";
/* THE BILLS' OWN TEXT, FETCHED WHEN SOMEBODY SEARCHES. site/sidx/<term>.json
   is what build_search_index.py made of the analyses and texts of one term's
   bills (see THE BILLS' OWN WORDS, above). Nobody who only browses the list
   pays for it: it is asked for the first time a search in words is run on a
   term, once, and the list is drawn again when it arrives. On All terms that
   is every term's file. If one cannot be had, that term's bills are found by
   title and topic as before, and the line under the search box says so --
   silence there would read as "nothing in the text". */
const TEXT={};
let TEXTGEN=0,TEXTDRAW=0;
// A member's Votes tab asks for the same files for the terms its search spans
// (`terms`) and draws itself again with `redraw`: the one loader, not a copy.
function wantText(terms,redraw){
  if(!terms){
    const q=query.trim();
    if(!q||billNumbers(q))return;
    terms=term===ALL_TERMS?((META&&META.terms)||[]):[term];
  }
  for(const t of terms){
    if(!t||TEXT[t])continue;
    TEXT[t]="loading";
    fetch(DATA("sidx/"+encodeURIComponent(t)+".json"))
      .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
      .then(j=>{TEXT[t]=indexAdd(t,j)?"ready":"failed";})
      .catch(()=>{TEXT[t]="failed";})
      .then(()=>{
        TEXTGEN++;
        // One redraw when the last of them is in, not one for each batch
        // that lands together: on All terms that is nineteen files, and on a
        // phone's connection they came in five batches, each drawing all
        // 33,000 bills again for six seconds (2 October). While more are on
        // their way the list is drawn again only if nothing has arrived for
        // a second and a half, so a connection that stalls still shows what
        // it has.
        clearTimeout(TEXTDRAW);
        TEXTDRAW=setTimeout(redraw||(()=>{if(query.trim())render();}),
          textState(terms)==="loading"?1500:40);
      });
  }
}
// "loading" while any term being searched is still on its way, "failed" if
// one could not be had, "ready" otherwise.
function textState(terms){
  terms=terms||(term===ALL_TERMS?((META&&META.terms)||[]):[term]);
  const st=terms.map(t=>TEXT[t]);
  return st.includes("loading")?"loading":st.includes("failed")?"failed":"ready";
}
/* EVERY WORD THE BILLS USE, FETCHED WHEN A SEARCH LISTS NOTHING.
   sidx/words.json is what tells a misspelt word from a real one that no
   bill of this term is about (spelling(), above). It is about 100 KB over
   the wire, so it is asked for once, the first time a search in words
   comes back empty with a word in it that might be a misspelling, and the
   empty result is drawn again when it arrives. If it cannot be had,
   nothing is offered. */
let WORDS="";
function wantWords(){
  if(WORDS)return;
  WORDS="loading";
  fetch(DATA("sidx/words.json"))
    .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
    .then(j=>{WORDS=wordsAdd(j)?"ready":"failed";})
    .catch(()=>{WORDS="failed";})
    .then(()=>{if(WORDS==="ready"&&query.trim())render();});
}
/* The search as it is read against the bills in view: the groups of
   queryGroups(), with readShort()'s reading of a two-letter word in a term
   where the search lists nothing ("special ed"). Kept until the search, the
   term or what has been fetched changes. */
let QG_KEY=null,QG=[];
function groupsFor(q){
  const key=[q,term,IDX.length,TEXTGEN].join("\u0001");
  if(key!==QG_KEY){QG_KEY=key;QG=readShort(queryGroups(q),IDX.filter(inTermOf));}
  return QG;
}
/* WHY THE LIST IS WHAT IT IS, in the bills' own words. A reader who types
   "lgbtq" is shown bills whose titles never say it. This line under the
   search box says what the bills were searched for: the words that stand
   beside the reader's own (SYN), then the wording of the table (CONCEPTS)
   that found a bill now listed -- only those, because each card says which
   of its own words put it there, and a list of thirty terms that found
   nothing was four lines long. The words typed are not repeated back, and
   nothing here describes a bill -- only what it says. */
function searchHint(gs,rows){
  rows=rows||[];
  const typed=g=>[g.word,stem(g.word),g.pre,...(g.asked||[])];
  const syn=[...new Set(gs.flatMap(g=>g.alts.slice(0,g.tab!=null?g.tab:g.alts.length)
    .filter(x=>!typed(g).includes(x))))];
  const found=new Set();
  for(const b of rows)for(const g of gs){
    const f=g.tab!=null&&fit(b,g);
    if(!f)continue;
    if(f[1]&&f[1][1])found.add(f[1][1]);
    if(f[2])found.add(f[2][1]);
  }
  const tab=[...found].filter(x=>!syn.includes(x)&&!gs.some(g=>typed(g).includes(x)));
  const state=textState();
  return [gs.cut?CUTNOTE.toLowerCase():"",
    syn.length?`also matching: ${syn.join(", ")}`:"",
    tab.length?`${syn.length?"then":"also listing"} bills that say: ${tab.join(", ")}`:"",
    state==="loading"?"reading the bills\u2019 text\u2026"
      :state==="failed"?"the bills\u2019 text could not be read: titles and topics only":""]
    .filter(Boolean).join("; ");
}
// The line on a card that says why it is listed, where its title does not.
function whyLine(b){
  const q=query.trim();
  if(!q||billNumbers(q)||b.lsr)return "";
  const y=whyListed(b,groupsFor(q));
  // "FOUND IN THE BILL'S TEXT" (the review of the release, 8 November 2026):
  // "Listed for — in the bill's text" read as if a word were missing.
  return y?`<div class="cwhy">${/^in /.test(y)?"Found":"Listed for &mdash;"} ${esc(y)}</div>`:"";
}
// The search's own words, in order, in the title, is the strongest sign
// there is: matchScore() counts it, for this page, the header and /search.
function scoreOf(b){
  return matchScore(b,groupsFor(query.trim()));
}
const $=s=>document.querySelector(s);

let IDX=[],META={},term=null,query="",sortBy="num",sortChosen=false;
// "All Terms" in the picker: every term's bills in one list. A bill number is
// unique only within a term, so in that list a card is not opened in place --
// two HB 1s would share one card's state -- and goes to its own page instead.
const ALL_TERMS="all";
// The terms' bills and not the requests, which are no term's and not bills:
// All Terms fetches META.terms alone, but a reader who had opened the
// requests first found their 302 rows in it as well -- "34,019 bills across
// all terms", 302 more than there are, once the count was always said (the
// review of 8 October 2026).
const inTermOf=b=>(term===ALL_TERMS&&!b.lsr)||!term||!b.term||b.term===term;
// "in the 2027-requests term" is not English and not what that list is, so
// the picker's own label speaks for it: "among the 2027 bill requests". The
// word "bills" the count puts before this is wrong for them too, which is why
// the count asks noun() rather than hard-coding it. THE YEAR IS THE
// REQUESTS' OWN (18 October 2026): meta.json's requests.year, which
// build_lsrs takes from the newest session the requests name; it said "for
// 2027" in a literal, which 2028's requests would have carried.
const reqYear=()=>META.requests?String(META.requests.year||String(META.requests.term||"").slice(0,4)):"";
const termPhrase=()=>term===ALL_TERMS?"across all terms"
  :(META.requests&&term===META.requests.term)?`for ${reqYear()}`
  :`in the ${termDash(term)} term`;
const termNoun=()=>(META.requests&&term===META.requests.term)
  ?"bill requests":"bills";
// The requests still standing: meta's n less the withdrawn (Alice, B1, 7
// November 2026).
const standingRequests=()=>META.requests
  ?Math.max((+META.requests.n||0)-(+META.requests.withdrawn||0),0):0;
// THE BANNER'S WINDOW: on the newest term, while the requests' session is
// still ahead of it, and while any request stands. 2027's requests are
// offered from 2025-2026, and not from 2027-2028 once that is the newest
// term -- the site is then on the session they were for.
const requestsAhead=()=>{
  const terms=META.terms||[];
  return !!(META.requests&&terms.length&&term===terms[0]
    &&+reqYear()>+String(terms[0]).slice(0,4)&&standingRequests()>0);
};
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
