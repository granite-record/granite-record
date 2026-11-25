// A bill against a search read into groups: every group must match, and any
// of its alternatives will do. /bills (matches, below) and a member's Votes
// tab (voteSearch) both ask it, so the two cannot come to disagree.
const matchesGroups=(b,gs)=>gs.every(g=>groupWeight(b,g)>0);
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
  for(const k of["committee","topic","sponsor","status","type","party"])
    if(k!==ignore&&sel[k].size&&!facetVals(b,k).some(v=>sel[k].has(v)))return false;
  // TAGS:BEGIN
  // Two tags ticked are either, as two topics are; a tag and a topic are
  // both (Education - General and Mental health), being two keys (design 5.3).
  if(ignore!=="tag"&&sel.tag.size&&!tagIdsOf(b).some(v=>sel.tag.has(v)))return false;
  // TAGS:END
  if(ignore!=="voteday"&&sel.voteday.size&&!(b.votedays||[]).some(d=>sel.voteday.has(d)))return false;
  if(ignore!=="rsa"&&sel.rsa.size&&![...sel.rsa].some(a=>rsaHas(b,a)))return false;
  const q=query.trim(); if(!q)return true;
  // A statute typed in the search box is the statute filter: "RSA 91-A:4"
  // lists the bills that change it, not the bills that print those words.
  const rq=/^\s*rsa\b/i.test(q)&&hasRsa()?rsaOfQuery(q):"";
  if(rq)return rsaHas(b,rq);
  // A request's sponsor is found by name (requestByName); its title, as ever.
  if(b.lsr&&requestByName(b,q))return true;
  // Every group must match, and any of its alternatives will do.
  return matchesGroups(b,groupsFor(q));
}

// `paint`, where given, draws each value as a chip of that class, the one
// chip (components.js), at the size everywhere but a head: the Status
// filter's words look as they do on the cards. The chip wraps here (app.css,
// .fopt .chip): "Passed both chambers, goes to the voters in November 2026"
// ran out of the 250px column on one line and was cut off at "the vote".
// `show`, where given, is what a value reads as, in HTML: the Bill Type
// filter's "HB House Bill" for the value HB.
// 5c (the person, 9 October 2026, item 2): ONCE A SEARCH OR A FILTER NARROWS
// THE LIST, the long lists -- Committee, Topic, Sponsor's found names,
// Floor Vote Day -- put the options with bills first and the greyed zeros
// after them, each part in the list's own order, with a rule above the first
// zero. Unnarrowed, nothing moves. Status and Bill Type keep their fixed
// orders, their zeros in place: both are short and shown whole, and Status's
// order is decided (round two's question 8b, as recommended). NOT 5b: a ticked
// choice keeps its place in its part and does not move to the top.
const ZEROS_LAST=new Set(["committee","topic","sponsor","voteday"]);
function narrowedNow(){
  return !!String(query||"").trim()||Object.values(sel).some(s=>s.size);
}
function zerosLast(key,vals,counts){
  if(!ZEROS_LAST.has(key)||!narrowedNow())return {vals,rule:-1};
  const some=vals.filter(v=>counts[v]),none=vals.filter(v=>!counts[v]);
  return {vals:some.concat(none),rule:some.length&&none.length?some.length:-1};
}
// `extra` is a second choice drawn inside this group after its own options
// (the Sponsor group's prime-sponsor party), `extraN` how many of it are ticked.
// A typed name against a sponsor as the Sponsor filter lists them: the way it
// always was (the letters anywhere in the name), and by word as a name is
// said, which finds "Weyler, Kenneth", "rep weyler" and "kenneth w" as well
// (12 November 2026), a former member's among them. A request's sponsor by any
// name the site prints for them (sponsorNames): "lee c" lists Lee Nyquist,
// whose card says Lee C. Nyquist, and "james" Jim Creighton.
function sponsorFits(v,f){
  return [v,...sponsorAlso(v)].some(n=>sponsorFitsName(n,f));
}
function sponsorFitsName(v,f){
  if(v.toLowerCase().includes(f))return true;
  const {want}=nameWords(f);
  if(!want.length)return false;
  // The search box's own rule (namesFit), so a name typed as its card prints
  // it ("W. Packy Campbell") or with an initial's full stop left off ("lee c
  // nyquist") lists the sponsor here as it lists their requests there.
  if(namesFit(want,[v]))return true;
  const parts=hintWords(v);
  // One of the words must start a word of the name itself: an initial alone
  // ("a" of "A. Merrill") is no reason to list a sponsor for "allen".
  const real=want.filter(w=>parts.some(x=>x.length>1&&x.startsWith(w)));
  return real.length>0&&want.every(w=>real.includes(w)||(w.length>2&&parts.some(x=>x.length===1&&w.startsWith(x))));
}
/* THE SPONSOR FILTER LISTS THE TERM'S MEMBERS (the owner, 19 November 2026:
   "Today you have to know a name to select a sponsor ... Make it a dropdown
   list of the sitting term's State Representatives and Senators that you can
   scroll and type into"). In a term, the Sponsor group lists every member of
   it the record names, the House and then the Senate, each by surname, as the
   member's chip with the number of their bills beside it; the box narrows
   them by any part of a name, a town or a district, and a member ticked is
   listed whatever is typed. All Terms keeps the box alone, a name typed
   listing up to fifteen, since thirty-seven years of members is no list.
   Who they are is site/sponsors/<term>.json (sponsor_roster.py), fetched the
   first time the group is open in that term: the term's sponsors and
   co-sponsors with the seat each held then, and for the term the sitting
   roster describes, every sitting member and every member who has since left,
   whether or not they filed a bill, with their district's towns. Until it
   comes, or where there is none, the list is the people the term's own rows
   name (spPeople), so it is never empty for want of a file.
   THE COUNT IS THE LIST THE FILTER WOULD GIVE (fgroup's counts, the other
   filters and the search applied): prime sponsorships, or with "Include
   co-sponsored bills" ticked, those and the co-sponsorships together, each
   part on its hover. A member at none goes after those with bills in their
   chamber, under the rule the long lists draw (zerosLast), greyed, so the
   members with bills are the top of each list.
   A MEMBER WHO HAS LEFT is listed in their place among the rest, named as a
   search result names them, "Former Rep." (treat-former-members-the-same):
   no badge, no group of their own, nothing about why. Only in the term the
   sitting roster describes; in a finished term every member named is named
   with the seat they held in it. */
const SP_ROSTER=Object.create(null);
function spRosterLoad(t){
  if(!t||t===ALL_TERMS||SP_ROSTER[t]||!published(t)||!((META&&META.terms)||[]).includes(t))return;
  SP_ROSTER[t]="asked";
  need("sponsors/"+encodeURIComponent(t)+".json")
    .then(j=>{SP_ROSTER[t]=j&&Array.isArray(j.members)?j.members:[];},()=>{SP_ROSTER[t]=[];})
    .then(()=>{if(t===term&&openGroups.has("sponsor")&&!facetsShut())renderFacets();});
}
// A name surname first, for the order the list reads in where the file gives
// none: "Bob Lynn Jr." is "lynn, bob".
const spOrder=n=>{const w=String(n||"").split(/\s+/).filter(Boolean);
  while(w.length>1&&/^(jr|sr|ii|iii|iv|v)\.?$/i.test(w[w.length-1]))w.pop();
  return (w.length>1?w[w.length-1]+", "+w.slice(0,-1).join(" "):w.join(" ")).toLowerCase();};
// The chamber a label's honorific names; a member-elect's "Rep.-elect" is Rep.
const spChamber=l=>{const h=String(l||"").split(" ")[0].replace(/-elect$/,"");return h==="Rep."?"H":h==="Sen."?"S":"";};
// Everyone the list offers in this term, once each by the key the filter
// keeps: the file's members, then anyone the term's rows name that it does
// not, then a sponsor ticked elsewhere whom this term names nowhere.
function spPeople(rows){
  const r=SP_ROSTER[term],m=new Map();
  for(const p of Array.isArray(r)?r:[])if(p&&p.k)m.set(p.k,{k:p.k,l:p.l||p.k,c:p.c||"",p:p.p||"",
    o:p.o||spOrder(p.k),t:p.t||[],f:!!p.f});
  // The prime sponsors first, by their own labels: a co-sponsor of one bill
  // who files another is listed by the label that bill gives them.
  for(const b of rows){
    const k=spKey(b);
    if(k&&!m.has(k))m.set(k,{k,l:b.sponsor_label||k,c:spChamber(b.sponsor_label),p:b.sponsor_party||"",
      o:spOrder(b.sponsor||k),t:[],f:false});
  }
  for(const b of rows)
    for(const c of b.cosp||[])if(c&&!m.has(c))m.set(c,{k:c,l:c,c:"",p:"",o:spOrder(c),t:[],f:false});
  for(const k of sel.sponsor)if(!m.has(k))m.set(k,{k,l:sponsorShow(k),c:"",p:"",o:spOrder(k),t:[],f:false});
  return [...m.values()];
}
// What is typed against a member: their name as the box always read it
// (sponsorFits), or a part of their district ("hills 12", "sd22") or of a
// town of it ("bedf").
function spFits(p,f){
  if(sponsorFits(p.k,f))return true;
  const seat=String((SEAT_RE.exec(p.l)||["",""])[1]).split(" - ").pop().toLowerCase();
  return !!seat&&/\d/.test(seat)&&seat.includes(f)||(p.t||[]).some(x=>String(x).toLowerCase().includes(f));
}
const spLabel=p=>p.f&&/^(Rep|Sen)\. /.test(p.l)?"Former "+p.l:p.l;
function spRow(p,counts,prime,chosen,rule){
  const n=counts[p.k]||0,pn=prime[p.k]||0;
  const how=withCosp?` title="${esc(`${pn.toLocaleString()} prime, ${(n-pn).toLocaleString()} co-sponsored`)}"`:"";
  return `<label class="fopt sprow${!n&&!chosen.has(p.k)?" off":""}${rule?" fzero":""}"><input type="checkbox" data-f="sponsor"
        value="${esc(p.k)}" ${chosen.has(p.k)?"checked":""}><span class="spn">${pchip({party_code:p.p,display_full:spLabel(p)})}</span>
        <span class="c"${how}>${n.toLocaleString()}</span></label>`;
}
const SP_CHAMBERS=[["H","House"],["S","Senate"],["","Others these bills name"]];
function spPicker(chosen,counts,f){
  const rows=IDX.filter(inTermOf);
  if(openGroups.has("sponsor"))spRosterLoad(term);
  const prime={};
  rows.filter(b=>matches(b,"sponsor")).forEach(b=>{const k=spKey(b);if(k)prime[k]=(prime[k]||0)+1;});
  const ppl=spPeople(rows).filter(p=>chosen.has(p.k)||!f||spFits(p,f));
  let h="";
  for(const [c,name] of SP_CHAMBERS){
    const of=ppl.filter(p=>c?p.c===c:p.c!=="H"&&p.c!=="S")
      .sort((a,b)=>a.o<b.o?-1:a.o>b.o?1:a.k<b.k?-1:a.k>b.k?1:0);
    if(!of.length)continue;
    const has=p=>counts[p.k]||chosen.has(p.k);
    const some=of.filter(has),none=of.filter(p=>!has(p));
    h+=`<div class="sphead" data-ch="${c||"X"}">${name} <span>${of.length.toLocaleString()} ${of.length===1?"member":"members"}</span></div>`
      +some.map(p=>spRow(p,counts,prime,chosen,false)).join("")
      +none.map((p,i)=>spRow(p,counts,prime,chosen,i===0&&some.length>0)).join("");
  }
  return h||(f?`<p class="fnone">No match</p>`:"");
}
function fgroup(key,label,vals,counts,searchable,paint,show,extra,extraN){
  const chosen=sel[key],open=openGroups.has(key);
  let inner="";
  if(searchable){
    // THE TOPIC FILTER IS THE SPONSOR FILTER'S BOX (12 November 2026, the
    // topics plan, stage 1): the same box, the same typing and the same
    // zeros-last order, narrowing the topic names by what is typed (anywhere
    // in the name, any case). With nothing typed the whole list is shown, as
    // before, not the sponsor list's empty start; a ticked topic stays in the
    // list whatever is typed, so it can be unticked where it is. No synonyms:
    // CONCEPTS maps a public word to bill wording, not to a topic's name.
    const isTopic=key==="topic";
    const picker=!isTopic&&term!==ALL_TERMS;
    const f=(isTopic?topicFilter:sponsorFilter).toLowerCase();
    const pick=isTopic
      ?vals.filter(v=>!f||chosen.has(v)||v.toLowerCase().includes(f))
      :(f?vals.filter(v=>sponsorFits(v,f)).slice(0,15):[]);
    const found=zerosLast(key,pick,counts);
    const shown=found.vals;
    const pills=isTopic?"":[...chosen].map(v=>`<span class="pill">${esc(sponsorShow(v))}<button data-unpick="${esc(v)}">×</button></span>`).join("");
    const box=isTopic
      ?`<input class="sbox" id="tbox" aria-label="Find a topic by name" placeholder="Type a topic…" value="${esc(topicFilter)}" autocomplete="off">`
      :`<input class="sbox" id="sbox" aria-label="${picker?"Find a sponsor by name, town or district":"Find a sponsor by name"}" placeholder="${picker?"Name, town or district…":"Type a name…"}" value="${esc(sponsorFilter)}" autocomplete="off">
      <label class="fcosp"><input type="checkbox" id="cosp" ${withCosp?"checked":""}><span>${termNoun()==="bills"?"Include co-sponsored bills":"Include co-sponsored requests"}</span></label>${extra||""}`;
    inner=`${pills?`<div class="chosen">${pills}</div>`:""}${box}`
      +(picker?spPicker(chosen,counts,f.trim()):shown.map((v,i)=>`<label class="fopt ${!counts[v]&&!(isTopic&&chosen.has(v))?'off':''}${i===found.rule?' fzero':''}"><input type="checkbox" data-f="${key}"
        value="${esc(v)}" ${chosen.has(v)?"checked":""}><span>${esc(isTopic?v:sponsorShow(v))}</span>
        <span class="c">${(counts[v]||0).toLocaleString()}</span></label>`).join("")
        ||((isTopic?topicFilter:sponsorFilter)?`<p class="fnone">No match</p>`:""));
    // TAGS:BEGIN
    if(isTopic)inner=topicLed(inner,f);
    // TAGS:END
  }else{
    const order=zerosLast(key,vals,counts);
    inner=order.vals.map((v,i)=>fcheck("data-f",key,v,chosen.has(v),!counts[v]&&!chosen.has(v),i===order.rule,
      paint?chip(v,paint(v)):show?show(v):esc(v),(counts[v]||0).toLocaleString())).join("");
  }
  // A short list that is the same few words in every term -- the Status
  // filter's categories, the kinds of measure -- is shown whole (.whole):
  // in the box that scrolls, a phone's 210px showed six of the 2025-2026
  // term's seven kinds and none of All Terms' after SCR, CACR among them,
  // with nothing to say the list went on.
  const whole=key==="status"||key==="type";
  return fgroupFrame(key,label,open,chosen.size+(extraN||0),inner,whole);
}
// ONE FILTER GROUP, AS fgroup DRAWS IT, and the votes page draws its own with
// it (votesFacets, 25 November 2026): its head the button that opens and
// shuts it, with how many are chosen in it in a badge, and under it the
// group's body, `inner`, shown whole where `whole` says its list is short.
// `open` is true or false.
function fgroupFrame(key,label,open,n,inner,whole){
  return `<div class="fgroup ${open?'open':''}"><button class="fhead" data-g="${key}"
    aria-expanded="${open}"><span>${label}</span>${n?`<span class="badge">${n}</span>`:""}
    <span class="chev">▸</span></button><div class="fbody${whole?" whole":""}" ${open?"":"hidden"}>${inner}</div></div>`;
}
// ONE OPTION OF A GROUP, AS fgroup DRAWS ITS SHORT LISTS' (Status, Bill Type,
// Committee), and the votes page's boxes with it: the box, ticked where `on`;
// the value's words, in HTML; and how many the list would hold with it,
// greyed where that is none (`off`), with the hairline above the first zero of
// a narrowed long list (`zero`). `attr` is the attribute a page hears the box
// by -- data-f, the bill search's (sel); data-vtick, the votes page's.
function fcheck(attr,key,v,on,off,zero,words,count){
  return `<label class="fopt ${off?'off':''}${zero?' fzero':''}">
      <input type="checkbox" ${attr}="${key}" value="${esc(v)}" ${on?"checked":""}>
      <span>${words}</span>
      <span class="c">${count}</span></label>`;
}

// TAGS:BEGIN
/* THE TAGS FILTER (design 5.3, as the owner's 17 November 2026 note leaves
   it: tags are "a helpful search tool"). A group of its own after Topic,
   closed until opened as the others are: the tags the list's bills carry,
   each by the registry's name with its count and its definition on the
   hover, by name with the zeros last as the topics are, and a box that
   narrows them by name and by the words that lead to each, which it never
   shows ("deepfake" lists Artificial intelligence and data centers). A tag
   ticked is listed whatever is typed, so it can be unticked where it is;
   two ticked are either, and a tag and a topic both (matches). */
let tagFilter="";
function tagGroup(inYear){
  if(!TAGLIST.length)return "";
  const typed=tagKey(tagFilter);
  const ledTo=tagLedTo(typed);
  const carried=new Set(inYear.flatMap(tagIdsOf));
  if(!carried.size&&!sel.tag.size)return "";
  const c={};
  inYear.filter(b=>matches(b,"tag")).forEach(b=>tagIdsOf(b).forEach(v=>{c[v]=(c[v]||0)+1;}));
  const pick=TAGLIST.map(t=>t.id).filter(id=>carried.has(id)||sel.tag.has(id))
    .filter(id=>sel.tag.has(id)||!typed||tagKey(tagOf(id).name).includes(typed)||ledTo.has("tag:"+id))
    .sort((a,b)=>tagOf(a).name.localeCompare(tagOf(b).name));
  const order=zerosLast("topic",pick,c);
  const open=openGroups.has("tag");
  const list=order.vals.map((id,i)=>`<label class="fopt ${!c[id]&&!sel.tag.has(id)?'off':''}${i===order.rule?' fzero':''}"><input type="checkbox" data-f="tag"
        value="${esc(id)}" ${sel.tag.has(id)?"checked":""}><span title="${esc(tagOf(id).definition)}">${esc(tagOf(id).name)}</span>
        <span class="c">${(c[id]||0).toLocaleString()}</span></label>`).join("")||(typed?`<p class="fnone">No match</p>`:"");
  return `<div class="fgroup ${open?'open':''}"><button class="fhead" data-g="tag"
    aria-expanded="${open}"><span>Tags</span>${sel.tag.size?`<span class="badge">${sel.tag.size}</span>`:""}
    <span class="chev">▸</span></button><div class="fbody" ${open?"":"hidden"}>`
    +`<input class="sbox" id="gbox" aria-label="Find a tag" placeholder="Type a subject…" value="${esc(tagFilter)}" autocomplete="off">`
    +`${list}</div></div>`;
}
// Where the words typed lead: each word of the table that is the words
// typed, or that they begin once they are three letters long.
function tagLedTo(typed){
  return new Set(typed?[...TAGWORDS].filter(([w])=>w===typed||(typed.length>2&&w.startsWith(typed)))
    .map(([,to])=>to):[]);
}
/* THE TOPIC BOX FINDS A TOPIC BY A WORD THAT LEADS TO IT (design 5.3): "weed"
   lists Cannabis under Topic, as the search does (tagGroups). `inner` is the
   group's box and topics as fgroup drew them, `f` what is typed in the box;
   each topic a typed word leads to that its name did not list is added, with
   its count, and "No match" goes where one is. */
function topicLed(inner,f){
  if(!TAGLIST.length)return inner;
  const ledTo=tagLedTo(tagKey(f));
  const inYear=IDX.filter(inTermOf);
  const here=new Set(inYear.map(b=>b.topic).filter(Boolean));
  const more=[...ledTo].filter(to=>/^topic:/.test(to)).map(to=>to.slice(6))
    .filter(t=>(here.has(t)||sel.topic.has(t))&&!inner.includes(`value="${esc(t)}"`)).sort();
  if(!more.length)return inner;
  const c={};
  inYear.filter(b=>matches(b,"topic")).forEach(b=>{if(b.topic)c[b.topic]=(c[b.topic]||0)+1;});
  return inner.replace(`<p class="fnone">No match</p>`,"")+more.map(t=>`<label class="fopt ${!c[t]&&!sel.topic.has(t)?'off':''}"><input type="checkbox" data-f="topic"
        value="${esc(t)}" ${sel.topic.has(t)?"checked":""}><span>${esc(t)}</span>
        <span class="c">${(c[t]||0).toLocaleString()}</span></label>`).join("");
}
// TAGS:END
/* THE LAWS CHANGED FILTER (the person, 26 October 2026: "it's a bit unclear
   what the most changed by these bills section means and those don't seem to
   have any particular meaning. It's more of a power user filter for folks who
   know a specific chapter of law they want to search for bills that change
   it, but it should still be easily understandable"). It was headed "RSA
   (Statute)" over ten pills of bare chapter numbers, "RSA 674 79", which said
   nothing to anybody who did not already know chapter 674. Now:

   ITS HEADING SAYS WHAT IT FILTERS BY, "Laws Changed (RSA)": the laws a bill
   changes, said as a bill's own page says it ("Changes this chapter of state
   law (RSA)", the person's words of 17 October 2026) and in the word the
   site's Laws tab is named by, with the letters a reader who knows them looks
   for. Title Case, as every filter's heading is (8 October 2026).

   ITS BOX TAKES A NUMBER OR A NAME. As the reader types, the chapters some
   bill of the list changes are offered -- by number ("91" offers RSA 91-A),
   by a section ("91-A:4", or "91-A:" for each section of it a bill changes),
   or by the words of the chapter's name, or of the name it is known by, or
   of its topic ("right to know" and "governmental records" offer RSA 91-A,
   Access to Governmental Records and Meetings) -- each with how many of the
   bills it would list, the filters already chosen kept. Nothing is filtered
   until one is chosen -- pressed, taken by Return, or a number typed whole
   and the box left: typing "91-A" used to list RSA 9's bills, then RSA
   91's, on the way. A chapter no bill changes is never offered; where what
   was typed finds none a bill changes, one line under the box says so, and
   nothing is chosen that would list no bill. Words name no law there ("No
   bill in the 2025-2026 term changes a law whose name has “students” in
   it."): the law of the whole list they fit best was named, and it was a
   law nobody had asked about. A number names the chapter typed, since that
   is the law asked about ("No bill ... changes RSA 404, Dog Licensing."), as
   it does for a section no bill changes, its chapter offered above it
   ("91-A:99"), and for Return on a number no bill changes ("91", where RSA
   91-A is offered), which chooses nothing and would otherwise seem to do
   nothing at all.

   ONE CHOSEN, ONE LINE NAMES IT: "Bills that change RSA 91-A, Access to
   Governmental Records and Meetings · Read the law · Clear". It was the
   number alone, and "Read the statute", a word the heading no longer uses.

   THE NAMES ARE THE LAWS PAGES' OWN LIST, laws/chapters.json (150 KB),
   fetched once, when the group is opened -- never for a reader who does not
   open it (the phone-speed work of 25 October 2026 keeps /bills light). The
   numbers, the counts and the filter need nothing from it: without it the
   offers are numbers alone and the words find nothing, which the line under
   the box says. A COMBOBOX, as the address box and the bill search's offers
   are (filterCombo): the box says it controls the list and whether it is
   open; the arrow keys move through it, aria-activedescendant naming the one
   they are on; Return takes it; Escape shuts the list and only the list; a
   status line says how many there are. The list is drawn in place as the box
   is typed in, so the box and the status line are not replaced under the
   reader; choosing one draws the page. */
const RSA_MOST=6;
// The Laws pages' own lists, each asked for once, when it is first wanted:
// chapters.json, the chapters' names (150 KB), when the group is opened, and
// headings.json, every section's heading (1.1 MB, 295 KB as sent), only when a
// colon is typed for a chapter's sections. A list that fails stays failed for
// that opening of the group, so it is not asked for again on every letter;
// the next opening asks again (the review of 26 October 2026: one failure kept
// the words off for the rest of the visit, a phone a moment offline among the
// ways to get one).
const RSA_LAWS={data:null,loading:null,failed:false};
const RSA_HEADS={data:null,loading:null,failed:false};
function rsaFetch(o,file,take,then){
  if(o.data||o.failed)return Promise.resolve();
  if(!o.loading)o.loading=fetch(DATA(file))
    .then(r=>{if(!r.ok)throw new Error(file+" returned "+r.status);return r.json();})
    .then(j=>{o.data=take(j);},()=>{o.failed=true;})
    .then(()=>{o.loading=null;if(!PAGE&&openGroups.has("rsa")&&!facetsShut())then();});
  return o.loading;
}
// The names: the group drawn again with them; and where the reader is typing,
// the status line told what they found, as a pause in typing tells it.
function rsaLawsLoad(){
  return rsaFetch(RSA_LAWS,"laws/chapters.json",j=>j&&typeof j==="object"?j:{},
    ()=>{renderFacets();if(RSA_OFF.open)rsaPaint(true);});
}
// The headings, as {"91-A:4": "Minutes and Records Available for Public
// Inspection."}: the offers drawn again with them.
function rsaHeadsLoad(){
  return rsaFetch(RSA_HEADS,"laws/headings.json",j=>{const m={};
    (Array.isArray(j)?j:[]).forEach(x=>{if(Array.isArray(x)&&x[0])m[x[0]]=String(x[1]||"");});return m;},
    ()=>{if(RSA_OFF.open)rsaPaint();});
}
// The next opening of the group asks again for a list that failed.
function rsaReopen(){RSA_LAWS.failed=false;RSA_HEADS.failed=false;}
// A chapter's row of the Laws pages' list, for a chapter or a section of it.
function rsaLaw(a){const c=RSA_LAWS.data&&RSA_LAWS.data[String(a).split(":")[0]];return Array.isArray(c)?c:null;}
// A section's heading as the Laws pages print it, without its full stop; ""
// where it is not here (a section a bill would write anew has none).
function rsaHead(a){const h=RSA_HEADS.data&&RSA_HEADS.data[a];
  return h?String(h).replace(/\s+/g," ").trim().replace(/\.$/,""):"";}
// ", Access to Governmental Records and Meetings" after RSA 91-A; a section
// is "in" it; nothing where the name is not here.
function rsaOf(a){const c=rsaLaw(a);return c&&c[0]?(a.indexOf(":")<0?", ":", in ")+c[0]:"";}
const rsaNamed=a=>`RSA ${a}${rsaOf(a)}`;
// Chapters and sections in the statute's own order: 9, 9-A, 91, 91-A, 91-A:2, 91-A:10.
function rsaCmp(x,y){
  const p=s=>{const m=/^(\d+)(?:-([A-Z]+))?(?::(\d+)?(.*))?$/.exec(s)||[];
    return [+m[1]||0,m[2]||"",m[3]===undefined?-1:+m[3],m[4]||""];};
  const a=p(x),b=p(y);
  for(let i=0;i<4;i++)if(a[i]!==b[i])return a[i]<b[i]?-1:1;
  return 0;
}
// What is typed, read: {num} -- the chapter, and the section after a colon,
// as far as they are typed, "91a" and "91 a" read as 91-A, after "RSA",
// "chapter" or both; `dash` where the chapter is begun, "21-" -- or {words};
// or {odd}, a number no RSA number is shaped like, "1234" or "91-A:4:5",
// with no word of three letters in it, which is told what one looks like
// rather than read as words (the review of 26 October 2026).
function rsaTyped(t){
  t=String(t||"").trim().replace(/^(?:(?:rsa|chapter)(?=[\s.\d]|$)\.?\s*)+/i,"");
  const m=/^(\d{1,3})(-?)([a-z]{0,2})(?::([0-9a-z.\-]*))?$/i.exec(t.replace(/\s+/g,""));
  if(m){
    const ch=m[1]+(m[3]?"-"+m[3].toUpperCase():""),sec=m[4]!==undefined;
    return {num:ch+(sec?":"+m[4].toLowerCase():""),ch,sec,dash:!!m[2]&&!m[3]&&!sec};
  }
  if(/\d/.test(t)&&!/[a-z]{3}/i.test(t))return {odd:t};
  const w=foWords(t);
  return w.length&&t.length>=FO_MIN?{words:w,raw:t}:null;
}
// How well the words typed fit a chapter of the list: 0 its name, 1 the name
// it is known by, 2 its topics; -1 not at all. The last word may be begun.
function rsaFit(ws,open,c){
  const last=ws.length-1,fits=text=>{const vs=foWords(text);
    return ws.every((t,i)=>vs.some(v=>foWord(t,v,open&&i===last)));};
  return fits(c[0]||"")?0:fits((c[0]||"")+" "+(c[4]||[]).join(" "))?1
    :fits((c[0]||"")+" "+(c[4]||[]).join(" ")+" "+(c[5]||[]).join(" "))?2:-1;
}
// The bills each chapter and section would list, the other filters and the
// search kept: worked out when the group is drawn, which every change to them
// does, and read as the box is typed in.
let RSA_N={};
const rsaNarrowed=()=>!!String(query||"").trim()||Object.keys(sel).some(k=>k!=="rsa"&&sel[k].size);
// "No bill in the 2025-2026 term changes RSA 404, Dog Licensing.", or "None
// of these bills changes ..." with another filter or the search on. Said only
// in a term whose bills say which laws they change (rsaGroup): of a bill
// request, which has no text yet, it would be a guess stated as a fact (the
// review of 26 October 2026: "No bill request for 2027 changes RSA 91-A",
// while two of them are plainly about it).
function rsaNone(what){
  return (rsaNarrowed()?"None of these bills changes ":`No bill ${termPhrase()} changes `)+what+".";
}
// A NAME A TITLE'S FIRST CHAPTER IS KNOWN BY IS THE TITLE'S (the review of 26
// October 2026). "criminal code" found RSA 625 alone, Preliminary, by the name
// it is known by -- while bills change chapter after chapter of the Criminal
// Code: RSA 625:1, "This title shall be known as the Criminal Code". So where
// the words fit no law by its own name, and fit best the name a title's first
// chapter is known by, the offers are the six chapters of that title the
// bills change most, the most bills first -- 625 among them only where a bill
// changes it and it is one of those six -- and where the bills change none of
// the title, the line names it: "None of these bills changes the Criminal
// Code." Anywhere else the name is the chapter's own (RSA 406-B is the
// "Uniform Unlicensed Insurers Act"), and so it is where the chapter is its
// title's only one (RSA 624, known as the Revised Statutes Annotated, is all
// of title LXI). In the list of 26 October 2026, 625 is the one chapter this
// applies to. null where it does not apply; else the name the title is known
// by and the offers.
function rsaTitleOf(best){
  const L=RSA_LAWS.data,law=L[best.a],t=law[1];
  if(best.how!==1||!t)return null;
  const of=Object.keys(L).filter(a=>Array.isArray(L[a])&&L[a][1]===t);
  if(of.length<2||of.some(a=>rsaCmp(a,best.a)<0))return null;
  return {name:law[4][0],rows:of.filter(a=>RSA_N[a]).map(a=>({a,n:RSA_N[a]}))
    .sort((x,y)=>y.n-x.n||rsaCmp(x.a,y.a)).slice(0,RSA_MOST)};
}
// The offers for what is typed: {rows:[{a, n}], note, miss}, `note` the line
// that says why there are none, `miss` the one Return says where it finds
// nothing to choose.
function rsaOffers(t){
  const T=rsaTyped(t),c=RSA_N;
  let rows=[];
  if(!T)return {rows,note:"",miss:""};
  if(T.odd)return {rows,note:"RSA numbers look like 91-A or 91-A:4.",miss:""};
  if(T.num){
    // Sections after a colon, and the chapter itself after them, always, so
    // its name is there; else the chapters whose number begins with what is
    // typed -- "21-" with exactly that, 21-J and not 210 (the review of 26
    // October 2026: "1-" offered 189 and 198) -- the one typed first.
    const num=T.num.replace(/:$/,""),pre=T.sec?T.num:T.dash?T.ch+"-":T.ch;
    rows=Object.keys(c).filter(a=>(a.indexOf(":")>=0)===T.sec&&a.startsWith(pre))
      .map(a=>({a,n:c[a]})).sort((x,y)=>(y.a===num)-(x.a===num)||y.n-x.n||rsaCmp(x.a,y.a));
    // A section no bill changes, typed whole: said so over its chapter.
    const unchanged=T.sec&&num!==T.ch&&!rows.length;
    rows=T.sec&&c[T.ch]?rows.slice(0,RSA_MOST-1).concat([{a:T.ch,n:c[T.ch]}]):rows.slice(0,RSA_MOST);
    // "21-", begun, names no chapter: RSA 21 itself may well be changed.
    const none=rsaNone(T.dash?`a law whose number begins “${T.ch}-”`:rsaNamed(num));
    return {rows,note:rows.length&&!unchanged?"":none,miss:T.dash?"":none};
  }
  if(!RSA_LAWS.data)return {rows,miss:"",note:RSA_LAWS.failed
    ?"The laws’ names could not be loaded. Type a chapter’s number, like 91-A."
    :"Looking up the laws’ names…"};
  // A last word begun and not yet three letters is not read until it is:
  // "right to kn" said "No law matches" between "right to" and "right to kno"
  // (found in Chromium on the preview, 26 October 2026). Now it offers what
  // "right" does, a whole word.
  const begun=!/\s$/.test(String(t||""));
  const cut=begun&&T.words.length>1&&T.words[T.words.length-1].length<FO_MIN;
  const ws=cut?T.words.slice(0,-1):T.words,open=begun&&!cut;
  // Every law of the list the words fit: offered where a bill here changes
  // it; and the one they fit best, for a title's name (rsaTitleOf).
  let best=null;
  for(const a of Object.keys(RSA_LAWS.data)){
    const law=RSA_LAWS.data[a],how=Array.isArray(law)?rsaFit(ws,open,law):-1;
    if(how<0)continue;
    if(c[a])rows.push({a,n:c[a],how});
    if(!best||how<best.how)best={a,how};
  }
  const title=best&&rsaTitleOf(best);
  if(title)return {rows:title.rows,miss:"",note:title.rows.length?"":rsaNone("the "+title.name)};
  rows.sort((x,y)=>x.how-y.how||y.n-x.n||rsaCmp(x.a,y.a));
  // None a bill changes: said so, naming no law. The law of the whole list
  // the words fit best was named, and "students" named RSA 110-E, "driving"
  // RSA 287-G, laws nobody had asked about (the review of 26 October 2026).
  return {rows:rows.slice(0,RSA_MOST),miss:"",
    note:rows.length?"":rsaNone(`a law whose name has “${T.raw}” in it`)};
}
// The list and the line under the box as they stand: shut, or what is typed
// offered, the one the arrow keys are on by its number. `miss` is what was
// typed when Return found nothing to choose, until it is typed in again.
const RSA_OFF={open:false,act:"",miss:null};
let RSADRAW=null;
function rsaState(){
  if(!RSA_OFF.open)return {rows:[],note:"",act:-1};
  const r=rsaOffers(rsaText);
  if(!r.note&&RSA_OFF.miss===rsaText)r.note=r.miss;
  return {...r,act:r.rows.findIndex(x=>x.a===RSA_OFF.act)};
}
// Each offer: the number, and under it a chapter's name or a section's
// heading -- a section's chapter is offered with it, named once, rather than
// the same name under every section -- and how many bills at the right. A
// section was its number alone, "RSA 91-A:4 8", the bare numbers the person
// asked to be rid of (the review of 26 October 2026).
function rsaRows(st){
  return st.rows.map((r,i)=>{const law=r.a.indexOf(":")<0&&rsaLaw(r.a);
    const under=law?law[0]||"":r.a.indexOf(":")>=0?rsaHead(r.a):"";
    return `<li role="option" class="qoffer" id="rsaoffers-${i}" data-rsapick="${esc(r.a)}"
    aria-selected="${i===st.act}"><span class="rn"><b>RSA ${esc(r.a)}</b>${under
      ?`<span class="sr">, </span><span class="rt">${esc(under)}</span>`:""}</span>
    <span class="c">${Number(r.n).toLocaleString()}<span class="sr"> ${r.n===1?"bill":"bills"}</span></span></li>`;}).join("");
}
// The list drawn again in place, the box and the status line kept. `say`
// where what is typed changed: the status line says how many, or the line
// under the box. Shut, the status line is emptied with it: it went on saying
// "6 laws match" after Tab had shut the six (the review of 26 October 2026).
function rsaPaint(say){
  const box=document.getElementById("rsabox"),list=document.getElementById("rsaoffers");
  if(!box||!list)return;
  const st=rsaState(),note=document.getElementById("rsanote");
  list.innerHTML=rsaRows(st);list.hidden=!st.rows.length;
  box.setAttribute("aria-expanded",st.rows.length?"true":"false");
  if(st.act>=0){
    box.setAttribute("aria-activedescendant","rsaoffers-"+st.act);
    const on=document.getElementById("rsaoffers-"+st.act);
    if(on&&on.scrollIntoView)on.scrollIntoView({block:"nearest"});
  }else box.removeAttribute("aria-activedescendant");
  if(note){note.textContent=st.note;note.hidden=!st.note;}
  const s=document.getElementById("rsasay");
  if(s&&(say||!RSA_OFF.open))s.textContent=st.note||(!st.rows.length?"":st.rows.length===1
    ?"1 law matches; the down arrow chooses it.":`${st.rows.length} laws match; the down arrow chooses one.`);
}
// Return: the offer the arrow keys are on; else what was typed, where a bill
// changes it -- "540:", its sections not begun, is RSA 540; else, for words,
// the best of the offers.
function rsaEnter(){
  const r=rsaOffers(rsaText),T=rsaTyped(rsaText);
  const on=r.rows.find(x=>x.a===RSA_OFF.act);
  if(on)return on.a;
  if(T&&T.num)return rsaNumber();
  return T&&r.rows.length?r.rows[0].a:"";
}
// The number typed, where a bill here changes it: "91-A", "91-A:4", or
// "540:", its sections not begun, for RSA 540; "" for words, for a number
// begun ("21-") and for one no bill changes ("91").
function rsaNumber(){
  const T=rsaTyped(rsaText);if(!T||!T.num||T.dash)return "";
  const a=T.num.replace(/:$/,"");return RSA_N[a]?a:"";
}
// A law chosen, or "" for Clear, and the list drawn. The focus stays where
// the reader sent it (render keeps it, in the box drawn anew where it was in
// the box), and is put in the box, after its last letter, only `into` it:
// from the keyboard -- Return, or Clear's own button, which is gone once it
// is pressed -- never from a finger or the mouse: on a phone that brought the
// keyboard up over the bills just chosen (the review of 26 October 2026).
// Where there is no box, in the bill requests, Clear takes the group with
// it, and the focus goes to the head of the filter above it, which stays,
// rather than to the page.
function rsaChoose(a,into){
  clearTimeout(RSADRAW);RSA_OFF.open=false;RSA_OFF.act="";RSA_OFF.miss=null;
  sel.rsa.clear();if(a)sel.rsa.add(a);rsaText=a;
  render();
  const b=document.getElementById("rsabox");
  if(b){if(into){b.focus({preventScroll:true});const n=b.value.length;b.setSelectionRange(n,n);}return;}
  const hs=document.querySelectorAll("#facets .fhead"),h=hs[hs.length-1]||$("#year");
  if(h&&h.focus)h.focus({preventScroll:true});
}
function rsaGroup(inYear){
  const open=openGroups.has("rsa"),chosen=sel.rsa.size?[...sel.rsa][0]:"";
  // A TERM WHOSE BILLS SAY NO LAW, the bill requests (the review of 26
  // October 2026): nothing can be offered there or said not to change, so
  // there is no box; a law chosen in another term stays, as a ticked status
  // does, named with a line that says why it lists none, so it can be undone
  // where it was done.
  const told=hasRsa();
  if(!told&&!chosen)return "";
  let inner="";
  // Shut, nothing in it is drawn or counted, and the names are not fetched.
  if(open){
    rsaLawsLoad();
    // The link to read it, where the Laws pages have the chapter: one a bill
    // would write anew (RSA 194-G) has no page there yet.
    const page=!RSA_LAWS.data||rsaLaw(chosen);
    const line=chosen?`<p class="frsa">Bills that change <b>RSA ${esc(chosen)}</b>${esc(rsaOf(chosen))} &middot; `
      +(page?`<a href="${esc(rsaHref(chosen))}">Read the law</a> &middot; `:"")
      +`<button class="link" data-rsapick="">Clear</button></p>`:"";
    if(!told){
      inner=`<p class="fnone">${termNoun()==="bills"?"Which laws these bills change is not known."
        :"A bill request has no text yet, so the laws it would change are not known."}</p>`+line;
    }else{
      const c={};inYear.filter(b=>matches(b,"rsa")).forEach(b=>(b.rsa||[]).forEach(a=>{c[a]=(c[a]||0)+1;}));
      RSA_N=c;
      const st=rsaState();
      // "A few words", as the search box above says, rather than "a name",
      // which under the Sponsor filter's "Type a name…" read as a person's
      // (the review of 26 October 2026). Short enough for the box at 1280,
      // which has 250px for it: "A number like 91-A, or a few words" took
      // 257 and lost its last word; this takes 185 (measured in Chromium).
      inner=`<input class="sbox" id="rsabox" role="combobox" aria-autocomplete="list" aria-controls="rsaoffers"
        aria-expanded="${st.rows.length?"true":"false"}"${st.act>=0?` aria-activedescendant="rsaoffers-${st.act}"`:""}
        aria-label="A law’s RSA number, like 91-A, or a few words from its name" placeholder="Like 91-A, or a few words"
        value="${esc(rsaText)}" autocomplete="off" spellcheck="false">`
        +`<ul class="rsaoffers" id="rsaoffers" role="listbox" aria-label="Laws these bills change"${st.rows.length?"":" hidden"}>${rsaRows(st)}</ul>`
        +`<p class="fnone" id="rsanote"${st.note?"":" hidden"}>${esc(st.note)}</p><span class="sr" id="rsasay" role="status"></span>`
        +line;
    }
  }
  return `<div class="fgroup ${open?'open':''}"><button class="fhead" data-g="rsa"
    aria-expanded="${open}"><span>Laws Changed (RSA)</span>${chosen?`<span class="badge">1</span>`:""}
    <span class="chev">▸</span></button><div class="fbody whole" ${open?"":"hidden"}>${inner}</div></div>`;
}

/* THE FILTERS IN USE, IN ONE PLACE (the owner, 19 November 2026: "selected
   filters should be easily viewable and should have an x mark next to them
   to deselect them ... you have a prime sponsor selected, but you switch to
   a different term or apply a different filter that doesn't overlap and you
   have to scroll through to deselect that specific filter"). Every filter
   ticked is a pill here, the Sponsor group's pill's look, saying which filter
   it is and what, with an × that takes that one off (a button, "Remove
   filter: ..."); "Include co-sponsored bills" is one while a sponsor is
   chosen; two or more and "Clear all" ends the row. Nothing ticked, no bar.
   The address follows, as it follows every filter (render, addressList).
   A FILTER KEPT ACROSS A TERM IS KEPT, AND SAYS SO. A filter that names no
   bill of the term in view -- a sponsor who did not serve then, a tag no bill
   of it carries -- stays (dropping it would change the list unseen) and is
   drawn muted and dashed, its hover and a line under the bar saying it
   matches nothing in this term. And where the filters together list nothing
   though each lists something, each pill whose removal alone would list
   bills again is marked, with how many on its hover, and the line says so.
   WHERE IT GOES: above the results (FBAR_PLACE "results"), where it is in
   view on a phone with the panel shut and beside the count it explains; or,
   "facets", at the top of the filter panel, sticking there as the panel
   scrolls. */
let FBAR_PLACE="results";
// The result's length as render() last drew it, for the bar in the panel.
let FBAR_N=null;
const FBAR_KEYS=[["status","Status"],["type","Bill type"],["committee","Committee"],["topic","Topic"],
  ["tag","Tag"],["sponsor","Sponsor"],["party","Party"],["rsa","Law"],["voteday","Vote day"]];
function fbarShow(k,v){
  if(k==="tag")return (tagOf(v)||{}).name||v;
  if(k==="sponsor")return sponsorShow(v);
  if(k==="type")return TYPE_NAME[v]||v;
  if(k==="rsa")return "RSA "+v;
  return v;
}
// Whether a filter names any bill of the term in view, the others aside.
function fbarHas(k,v,rows){
  if(k==="cosp")return true;
  if(k==="tag")return rows.some(b=>tagIdsOf(b).includes(v));
  if(k==="voteday")return rows.some(b=>(b.votedays||[]).includes(v));
  if(k==="rsa")return rows.some(b=>rsaHas(b,v));
  return rows.some(b=>facetVals(b,k).includes(v));
}
function fbarItems(){
  const out=[];
  for(const [k,name] of FBAR_KEYS)for(const v of sel[k]||[])out.push({k,v,name,show:fbarShow(k,v)});
  if(withCosp&&sel.sponsor.size)out.push({k:"cosp",v:"1",name:"",
    show:termNoun()==="bills"?"Co-sponsored bills included":"Co-sponsored requests included"});
  return out;
}
// How many the list would hold without this one filter.
function fbarWithout(it){
  if(it.k==="cosp"){withCosp=false;const n=IDX.filter(b=>matches(b)).length;withCosp=true;return n;}
  sel[it.k].delete(it.v);
  const n=IDX.filter(b=>matches(b)).length;
  sel[it.k].add(it.v);
  return n;
}
function filterBarHtml(n){
  const items=fbarItems();
  if(!items.length)return "";
  const rows=IDX.filter(inTermOf),noun=termNoun(),where=termPhrase();
  for(const it of items)it.none=!fbarHas(it.k,it.v,rows);
  // Each list something, and together nothing: which one alone is in the way.
  const stuck=n===0&&items.length>1&&!billNumbers(query)&&!items.some(it=>it.none);
  if(stuck)for(const it of items)it.without=fbarWithout(it);
  const said=it=>it.name?`${it.name}: ${it.show}`:it.show;
  const pills=items.map(it=>{
    const tip=it.none?`Matches no ${noun} ${where}`
      :it.without?`Without this, ${it.without.toLocaleString()} ${it.without===1?noun.replace(/s$/,"")+" matches":noun+" match"}`:"";
    return `<span class="pill fpill${it.none?" none":""}${it.without?" fblock":""}"${tip?` title="${esc(tip)}"`:""}>`
      +`<span class="fv">${it.name?`<span class="fk">${esc(it.name)}:</span> `:""}${esc(it.show)}</span>`
      +(tip?`<span class="sr"> (${esc(tip)})</span>`:"")
      +`<button type="button" class="fx" data-unfilter="${esc(it.k)}" data-v="${esc(it.v)}" aria-label="${
        esc("Remove filter: "+said(it))}">×</button></span>`;
  }).join("");
  const note=items.some(it=>it.none)
    ?`A dashed filter matches no ${noun} ${where}.`
    :stuck?(items.some(it=>it.without)?`No ${noun.replace(/s$/,"")} matches all of these together. Removing an outlined one lists some again.`
      :`No ${noun.replace(/s$/,"")} matches all of these together.`):"";
  return `<div class="fbar" role="region" aria-label="Filters in use">${pills}${
    items.length>1?`<button type="button" class="link fclear" data-fclear="1">Clear all</button>`:""}${
    note?`<p class="fbarnote">${esc(note)}</p>`:""}</div>`;
}
// The bar above the results: in #fbar, made before the summary where the
// page has none; hidden on a bill's own view and with nothing ticked.
function drawFilterBar(n){
  const html=n==null||FBAR_PLACE!=="results"?"":filterBarHtml(n);
  let el=document.getElementById("fbar");
  if(!el){
    const main=document.getElementById("main"),sum=document.getElementById("summary");
    if(!html||!main||!sum||!main.insertBefore)return;
    el=document.createElement("div");el.id="fbar";main.insertBefore(el,sum);
  }
  if(el.innerHTML!==html)el.innerHTML=html;
  el.hidden=!html;
}
// A filter taken off from its pill, or all of them; from the keyboard, the
// focus goes to the pill now where it was, or to the search box.
function unfilter(k,v,kbd,at){
  if(k==="cosp")withCosp=false;
  else if(sel[k]){sel[k].delete(v);if(k==="rsa")rsaText="";}
  render();
  if(kbd){const xs=document.querySelectorAll(".fbar .fx");
    const to=xs[Math.min(at||0,xs.length-1)]||$("#q");if(to&&to.focus)to.focus();}
}
function clearFilters(kbd){
  Object.values(sel).forEach(s=>s.clear());withCosp=false;rsaText="";RSA_OFF.open=false;render();
  if(kbd){const q=$("#q");if(q&&q.focus)q.focus();}
}

function renderFacets(){
  const inYear=IDX.filter(inTermOf);
  const cnt=(k,ig)=>{const c={};inYear.filter(b=>matches(b,ig)).forEach(b=>{
    facetVals(b,k).forEach(v=>{if(v)c[v]=(c[v]||0)+1;});});return c;};
  const present=k=>[...new Set(inYear.flatMap(b=>facetVals(b,k)).filter(Boolean))].sort();
  let h="";
  // STATUS AND BILL TYPE FIRST (the person, 10 October 2026): the two that
  // open by default head the list, above Committee, Topic and Sponsor.
  // No "Year Filed" facet. The term picker above the list already chooses
  // the biennium, and splitting one term into its two filing years was a
  // second control for a distinction the card prints on its own. (The
  // <select id="year"> is the TERM picker, despite its id, and stays.)
  // THE CATEGORIES (statusCat, above), each in its own chip's colour and in
  // their one order, and only those a bill of this term is in (all of them
  // on All Terms): the person, 8 October 2026, "Hide at zero". The first
  // five were offered in every term at first, so that the list kept its
  // shape, and an ended term offered In Progress and Tabled at none. A
  // category a reader has ticked stays, at none, wherever they take it --
  // into a term with no bill in it, or into the requests, which have no
  // status yet and are otherwise offered no Status filter at all -- so the
  // empty list can be seen to be its doing and undone where it was done. It
  // offered the chip's words, a stage at a time, and before that four kinds
  // -- In progress, Became law, Killed, Vetoed -- with no way to ask for
  // interim study.
  const cats=catsOffered(new Set(present("status")),sel.status);
  if(cats.length)h+=fgroup("status","Status",cats,
    cnt("status","status"),false,v=>CATCLASS[v]||"");
  // WHAT KIND OF MEASURE (TYPE_NAME), in the person's order (TYPEORDER), each
  // as its letters and its name. A type ticked in another term stays on
  // offer, at none, so it can be unticked where it lists nothing; so does a
  // ticked category above.
  h+=fgroup("type","Bill Type",[...new Set([...present("type"),...sel.type])].sort(typeCmp),
    cnt("type","type"),false,null,
    v=>`<span class="tname"><b class="tcode">${esc(v)}</b>${
      TYPE_NAME[v]?`<span>${esc(TYPE_NAME[v])}</span>`:""}</span>`);
  // A committee or topic ticked in another term stays on offer, at none, so
  // it can be unticked on its own where it lists nothing.
  // NO COMMITTEE FILTER WHERE NO REQUEST HAS A COMMITTEE (the owner, 13
  // November 2026: "Committee should not be one of the search filters until
  // bills are assigned to a certain committee ... it's just blank on the LSRs
  // search"). It is offered the day any request names one, by itself, and a
  // committee ticked elsewhere stays, so it can be unticked.
  {const cm=[...new Set([...present("committee"),...sel.committee])].sort();
   if(termNoun()==="bills"||cm.length)h+=fgroup("committee","Committee",cm,cnt("committee","committee"));}
  // ONE NAME FOR THE GROUP IN EVERY TERM (the owner, 14 November 2026: "remove
  // the topic from title label"). A request's topic is read from its title
  // (request_topics.py), and one it cannot place is Miscellaneous, listed here.
  h+=fgroup("topic","Topic",[...new Set([...present("topic"),...sel.topic])].sort(),cnt("topic","topic"),true);
  // TAGS:BEGIN
  h+=tagGroup(inYear);
  // TAGS:END
  // THE PRIME SPONSOR'S PARTY is a choice inside the Sponsor group it narrows
  // (the owner, 10 November 2026), below the name box and the co-sponsorship
  // box: a short list shown whole, in the legislators' chip shape and colour
  // (.mchip), where a party chosen in another term stays, at none, so it can
  // be unticked.
  const pc=cnt("party","party");
  const pOpts=[...new Set([...present("party"),...sel.party])].sort(partyCmp);
  const partyHtml=`<div class="fsub"><div class="fsubh">Prime sponsor’s party</div>${
    pOpts.map(v=>`<label class="fopt ${!pc[v]&&!sel.party.has(v)?'off':''}"><input type="checkbox" data-f="party" value="${esc(v)}" ${sel.party.has(v)?"checked":""}>
      <span>${partyShow(v)}</span><span class="c">${(pc[v]||0).toLocaleString()}</span></label>`).join("")}</div>`;
  h+=fgroup("sponsor","Sponsor",present("sponsor"),cnt("sponsor","sponsor"),true,null,null,partyHtml,sel.party.size);
  // THE STATUTE, where the Floor Vote Day filter was (the person, 11 October
  // 2026): Laws Changed (RSA) since 26 October, a box that offers the laws
  // these bills change by number or by name (rsaGroup), and the law itself
  // one link away. A vote day an old address names still filters; the group
  // is no longer drawn. Not drawn either in a term whose bills say no law,
  // unless a law is chosen (rsaGroup).
  h+=rsaGroup(inYear);
  if(Object.values(sel).some(s=>s.size))h+=`<button class="link" id="clear" style="margin-top:12px">Clear all filters</button>`;
  // The filters in use, at the panel's top where the bar is put there (FBAR_PLACE).
  if(FBAR_PLACE==="facets"&&FBAR_N!=null)h=filterBarHtml(FBAR_N)+h;
  // Replacing innerHTML resets scrollTop to zero. Capture it first and put it
  // back in the same tick, before anything is painted, or every tick of a
  // checkbox throws the reader back to the top of the list.
  const fx=$("#facets");
  const keep=fx?fx.scrollTop:0;
  const inner=fx?fx.querySelectorAll(".fbody"):[];
  const innerKeep=[...inner].map(el=>el.scrollTop);
  // The checkbox just ticked, or the group head just pressed, is one of the
  // things replaced: focus goes back on its copy once the scroll is restored
  // (focusKey, by repaint).
  const held=focusKey();
  // And the caret in the Laws Changed box, where the laws' names arrive
  // while it is being typed in (rsaLawsLoad).
  const ae=document.activeElement;
  const caret=ae&&ae.id==="rsabox"&&ae.selectionStart!=null?[ae.selectionStart,ae.selectionEnd]:null;
  fx.innerHTML=h;
  fx.scrollTop=keep;
  facetBadge();
  [...fx.querySelectorAll(".fbody")].forEach((el,i)=>{
    if(innerKeep[i]!==undefined)el.scrollTop=innerKeep[i];
  });
  refocus(held);
  const rb=caret&&document.getElementById("rsabox");
  if(rb&&rb===document.activeElement&&rb.setSelectionRange)rb.setSelectionRange(caret[0],caret[1]);
}
// THE COUNT HAS TO BE VISIBLE WITH THE PANEL SHUT. A reader who filtered by
// topic, scrolled, and came back to a closed panel would otherwise have no
// way of knowing why the list is short. Same badge the groups carry.
function facetBadge(){
  const ftb=document.getElementById("ftoggle");
  if(!ftb)return;
  ftb.hidden=false;
  const on=Object.values(sel).reduce((n,s)=>n+s.size,0);
  const bd=ftb.querySelector(".badge");
  if(bd){bd.textContent=on?String(on):"";bd.hidden=!on;}
}
// THE PANEL IS DRAWN ONLY WHERE IT CAN BE SEEN (the phone audit of 25
// October 2026). render() rebuilt it on every letter typed, counting every
// bill of the term once for each group, behind a button nobody had pressed:
// below 60em the panel is shut until its button opens it (app.css, 5d), and
// it is hidden beside one bill and on a page that is not the list. Shut, the
// list redraws its button's badge alone; the button opening it, or a window
// widened past 60em, draws the panel as it stands.
const FACETS_NARROW=typeof matchMedia==="function"?matchMedia("(max-width:59.9375em)"):null;
function facetsShut(){
  const sh=document.querySelector(".shell"), c=sh?sh.classList:null;
  return !c||c.contains("focused")||c.contains("nofacets")
    ||(!!FACETS_NARROW&&FACETS_NARROW.matches&&!c.contains("fopen"));
}
if(FACETS_NARROW&&FACETS_NARROW.addEventListener)
  FACETS_NARROW.addEventListener("change",()=>{if(!facetsShut())renderFacets();});

// THE SIDE THAT PREVAILED, SAID AS WELL AS TICKED (the accessibility sweep
// of 29 October 2026). The tick beside a vote's winning side was read aloud
// as "check mark", or not at all, and nothing else on the row said which
// side had won: the tick is hidden from a screen reader now, and a word the
// eye does not see says it -- "Yes (prevailed)". Every tally's tick is this
// one (simpleDonut, donut's party rows, ballotRing), in the page's language.
function wonMark(){
  return `<span class="won" title="${esc(tr("vote.won_title","this side prevailed"))}" aria-hidden="true">\u2713</span>`
    +`<span class="sr"> ${esc(tr("vote.won_sr","(prevailed)"))}</span>`;
}
function simpleDonut(rc,bid,i,what){
  // A division vote is counted but anonymous. Same ring, same colours, same
  // threshold line as a roll call -- the difference between the two is who is
  // named, not how the count should look. It used to be drawn in a different
  // palette with no threshold at all, which made the same 191 to 158 look like
  // a different kind of vote.
  const y=rc.yeas||0,n=rc.nays||0,tot=(y+n)||1;
  const R=60,C=2*Math.PI*R,GAP=32,gap=C*GAP/360,avail=C-gap-C*1.4/360;  // a hair's break where Yes meets No (ring 1c)
  const won=!!rc.passed;
  const seg=(len,fill,sideWon)=>`<circle r="${R}" cx="86" cy="86" fill="none" stroke="${fill}"
    stroke-width="24" opacity="${sideWon?1:.75}"
    stroke-dasharray="${len} ${C-len}" stroke-dashoffset="${-gap/2}"></circle>`;
  const need=rc.threshold_needed||Math.floor(tot/2)+1;
  const frac=Math.min(1,Math.max(0,need/tot));
  const a=(180+GAP/2+(360-GAP)*frac)*Math.PI/180;
  // No mark where the record says more than a majority was needed and the
  // count it was needed of is not on record -- three fifths of the members in
  // office, on a division, where nobody's ballot was recorded. A majority mark
  // there would be a wrong one.
  // The rule rides on the mark as a roll call's does (17 October 2026): a
  // division on a constitutional amendment now carries three fifths of the
  // members in office, and "237 needed" alone does not say of what.
  const tick=rc.threshold_unknown?"":marker(a,R,need,rc.threshold_rule||"");
  return `<div class="votewrap"><svg class="donut" viewBox="0 0 172 206" width="172" height="206"
    role="img" aria-label="${what||"Division vote"}, ${y} yes to ${n} no, needing ${
      rc.threshold_unknown?"more than a majority":need}${
      rc.threshold_rule?`, ${esc(rc.threshold_rule)}`:""}">
    <g transform="rotate(90 86 86)">${seg(avail*y/tot,"var(--yes)",won)}</g>
    <g transform="translate(172,0) scale(-1,1)"><g transform="rotate(90 86 86)">${seg(avail*n/tot,"var(--no)",!won)}</g></g>
    ${tick}${yn(GAP,R,won)}
    ${score(y,n,won)}</svg>
    <div class="legend">
      <div class="lrow"><span class="sw" style="background:var(--yes)"></span>
        <span>Yes${won?wonMark():""}</span>
        <span class="c">${y}</span></div>
      <div class="lrow"><span class="sw" style="background:var(--no)"></span>
        <span>No${won?"":wonMark()}</span>
        <span class="c">${n}</span></div></div></div>`;
}

/* WHO PRESIDED, BY THE OFFICE THEY HELD THAT DAY (the person, 9 October
   2026: Rep. Steven Smith "is the deputy speaker and sometimes fills in for
   Sherman Packard if he has other business, as does Jim Kofalt occasionally
   as speaker pro temp"). A roll call records its presiding officer as a
   ballot and nothing of their office, so the list under Presiding said
   "Rep. Steven Smith (R)" with nothing to say why it was him. officers.json
   (build_site_v2.build_officers) is who held the chair's offices on which
   days, read from the journals and the calendars, keyed by the sort key the
   ballots carry; it is asked for the first time a presiding ballot is
   drawn. A member the record gives no office that day is listed as before. */
let OFFICERS=null;      // null while unasked, [] while asked or unavailable
function needOfficers(){
  if(OFFICERS)return;
  OFFICERS=[];
  fetch(DATA("officers.json"))
    .then(r=>r.ok?r.json():Promise.reject(new Error("HTTP "+r.status)))
    .then(j=>{OFFICERS=(j&&j.officers)||[];repaint();})
    .catch(()=>{});     // the ballots are listed as they were
}
function presidingOffice(rc,m){
  if(!m||m.v!=="Presiding")return "";
  needOfficers();
  const d=String(rc.date||"");
  const o=OFFICERS.find(t=>t.b===rc.body&&t.s===m.s&&t.from<=d&&d<t.to);
  return o?o.office:"";
}
// One member in a roll call's list of names, and under it their office where
// they presided over it: on the same line, "Deputy Speaker of the House"
// broke after "Deputy" in a 250px column.
function ballotCell(rc,m){
  const o=presidingOffice(rc,m);
  return `<div class="m" translate="no">${esc(m.n)}${o?`<span class="p mo" translate="yes">${esc(o)}</span>`:""}</div>`;
}

// THE BALLOTS AGAINST THE COUNT (the owner, 23 October 2026, who saw one
// Republican ballot drawn as a whole ring under a count of 214-119 and took
// the site for broken). The party ring is drawn from the members' ballots,
// and its proportions are only true where those ballots add up to the
// clerk's count. Where they do not, the ring is the count's own (the
// division's ring) and a line says why; BALLOT_SLACK is how far apart the
// two may be and still be drawn by party. None, because none is needed:
// measured that day on all 9,565 roll calls of 1999-2026, every card's Yea
// and Nay ballots add up to its count exactly -- rollcall_parser makes the
// ballots the headline and keeps the 14 summaries that disagree as "stated"
// -- so the count's ring is drawn only for a record that is broken.
const BALLOT_SLACK=0;
const BALLOT_GAP_NOTE=`<p class="note ballotgap">The list of members’
      votes does not add up to the recorded count, so the ring shows the count alone.</p>`;
function ballotsAddUp(rc){
  let y=0,n=0;
  for(const tl of Object.values(rc.tally||{})){y+=tl.Yea||0;n+=tl.Nay||0;}
  return Math.abs(y-(rc.yeas||0))<=BALLOT_SLACK&&Math.abs(n-(rc.nays||0))<=BALLOT_SLACK;
}
function donut(bid,i,rc){
  if(!ballotsAddUp(rc))
    return simpleDonut(rc,bid,i,"Roll call")+BALLOT_GAP_NOTE;
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
  const R=60,C=2*Math.PI*R,GAP=32,gap=C*GAP/360,avail=C-gap-C*1.4/360;  // a hair's break where Yes meets No (ring 1c)
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
    return `<circle r="${R}" cx="86" cy="86" fill="none" stroke="${fill}" stroke-width="24"
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
  // The ring is 24 wide about radius R (ring 1c), so its edges are at R-12 and R+12. The
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
  // THE SWATCH IS THE PARTY'S COLOUR: red, blue and purple, with the side in
  // words beside it (the owner's walk of the release candidate, 30 October
  // 2026). The audit of 25 October (S1) had made it the side's green or
  // salmon, the ring's, so that every row's key read the same as a division
  // vote's; the owner wants the parties told apart at a glance. A division's
  // legend, which has no parties, stays Yes and No.
  const legend=rows.map(s=>{
    const winner=(s.side==="Yea")===won;
    return `<button type="button" class="lrow ${chosen===s.key?'sel':''}" aria-pressed="${chosen===s.key}" data-seg="${key}|${s.key}">
    <span class="sw" style="background:${PARTY_COLOR[s.p]||"var(--ink-2)"}"></span>
    <span>${PARTY_NAME[s.p]||s.p} — ${s.side==="Yea"?"Yes":"No"}${
      winner?wonMark():""}</span>
    <span class="c">${s.n}</span></button>`;}).join("");
  const others=OTHER.map(([st,label])=>({st,label,n:(rc.members||[]).filter(m=>m.v===st).length})).filter(o=>o.n);
  const oTot=others.reduce((a,o)=>a+o.n,0);
  // "DID NOT VOTE", NOT "OTHER ... NOT IN CHART" (17 October 2026): every
  // ballot here is a member who cast no yes or no -- presiding, excused or
  // absent -- which is what the reader needs to know of them.
  const oRows=others.length?`<div class="othergrp"><div class="otherhd">Did not vote — ${oTot}</div>
    ${others.map(o=>`<button type="button" class="lrow ${chosen==="other-"+o.st?'sel':''}" aria-pressed="${chosen==="other-"+o.st}" data-seg="${key}|other-${o.st}">
    <span class="sw sw-o"></span><span>${o.label}</span><span class="c">${o.n}</span></button>`).join("")}</div>`:"";
  let list="";
  if(chosen){
    const grid=a=>`<div class="mgrid">${a.map(m=>ballotCell(rc,m)).join("")}</div>`;
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
    fill="var(--ink)"><title>${need} needed${rule?` \u2014 ${esc(rule)}`:""}</title></polygon>`;
}

function yn(GAP,R,won){
  // YES AND NO IN WORDS (the person, 14 October 2026, ring 1c): under the
  // two ends of the ring, set wider apart than the ends themselves so each
  // reads as its side's label, the side that carried in bold. They were a
  // 30px Y and N with the winner underlined.
  // --ink-2 FOR THE LOSING WORD, never a token that does not exist: an
  // unresolved var() in an SVG fill falls back to black without a warning
  // (see the note on --ink-3 in the history of this function).
  const Y=190;
  const at=(x,txt,won)=>`<text x="${x}" y="${Y}" text-anchor="middle" font-size="17"
      font-weight="${won?700:400}" fill="var(--ink${won?"":"-2"})">${txt}</text>`;
  return at(36,"Yes",won)+at(136,"No",!won);
}

// The count in the middle, with the side that prevailed in bold.
//
// PREVAILED, not the larger number. A veto override at 204 to 116 has more
// yeses and still failed, because it needed two thirds; bolding 204 would say
// the yes side won a vote it lost. The threshold tick on the ring shows why,
// and this agrees with it.
function score(y,n,won){
  // The tally in the serif, and under it in small capitals whether the vote
  // carried (ring 1c, 14 October 2026) -- the word, not a bolder number, says
  // which side prevailed, which on a failed override is the smaller one.
  return `<text x="86" y="90" text-anchor="middle" font-size="18" font-weight="600"
    style="font-family:var(--serif)" fill="var(--ink)" font-variant-numeric="tabular-nums">${y}\u2013${n}</text>
    <text x="86" y="109" text-anchor="middle" font-size="13" font-weight="700" letter-spacing="1"
    fill="var(${won?"--st-law":"--st-done"})">${won?"PASSED":"FAILED"}</text>`;
}

function fullRecord(bid,i,rc){
  const k=`${bid}|${i}`;
  if(!fullOpen.has(k))return `<button type="button" class="discl" aria-expanded="false" data-full="${k}">View full voting record →</button>`;
  // Sorted on the surname-first key, not on what is displayed: ordering
  // "Rep. Jodi Nelson (R)" alphabetically groups 400 members by honorific
  // and then by first name.
  const col=(v,p)=>(rc.members||[]).filter(m=>m.v===v&&(p==null||(m.p||"X")===p))
    .sort((a,b)=>(a.s||a.n||"").localeCompare(b.s||b.n||""));
  const grid=a=>`<div class="mgrid">${a.map(m=>ballotCell(rc,m)).join("")}</div>`;
  const sect=([st,label,blurb])=>{const a=col(st);return a.length?`<div class="mlist">
    <h3>${label} — ${a.length}</h3><p class="note" style="margin:0 0 9px">${blurb}</p>${grid(a)}</div>`:"";};
  const y=col("Yea"),n=col("Nay"),tot=(rc.members||[]).length;
  // One pair of columns per party, Republicans first, then Democrats, then
  // anyone else: a party's yea and nay sit side by side, so its split is read
  // across one row rather than hunted for in two lists 400 names long. Headed
  // Yes and No, as the legend above them is: "Republican Yea" under
  // "Republican — Yes" was two words for one side (the audit of 25 October
  // 2026, S1).
  const parties=[...new Set((rc.members||[]).filter(m=>m.v==="Yea"||m.v==="Nay")
    .map(m=>m.p||"X"))].sort(byParty);
  const pair=p=>{const py=col("Yea",p),pn=col("Nay",p),nm=PARTY_NAME[p]||p;
    return `<div class="full"><div><h3>${nm} Yes — ${py.length}</h3>${grid(py)}</div>
    <div><h3>${nm} No — ${pn.length}</h3>${grid(pn)}</div></div>`;};
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
//
// AN INTERIM STUDY COMMITTEE'S REPORT (the person's walk of the preview, 30
// October 2026): green where it recommends the subject for future
// legislation, red where it does not, and no colour where it makes no
// recommendation -- the clerks' "Without Recomendation" and "No
// Recommendation" among them. First, so that "NOT RECOMMENDED" is read before
// "RECOMMENDED", and before the motions below. As the clerks varied it too
// (src/parse/interim_statements.py): "Not Recommended for Further
// Legislation" (SB 366 of 2010), "Not Recommended for Legislation" (HB 1415
// of 2006).
// A report that states none of the three ("Interim Study Report filed") is
// plain, as one without a recommendation is, and not the orange of the
// motion to study below.
const RECCOLOUR=[[/\b(?:WITHOUT|NO)\s+RECOMM?ENDATION\b/i,""],
                 [/\bNOT\s+RECOMMENDED\b/i,"s-done"],
                 [/\bRECOMMENDED\s+FOR\b/i,"s-law"],
                 [/\bINTERIM\s+STUDY\s+REPORT\b/i,""],
                 [/INEXPEDIENT/i,"s-done"],
                 [/INTERIM\s+STUDY|RE-?REFER/i,"s-study"],
                 [/OUGHT\s+TO\s+PASS/i,"s-law"]];
const recColour=r=>{const m=RECCOLOUR.find(([re])=>re.test(r||""));
  return m?m[1]:"";};
// A committee's recommendation as a chip, with its vote in brackets where the
// record carries one (the owner's walk of dry run 8, 8 November 2026). The
// tally is held whole so that a phone does not break it after the dash.
const recChip=(rec,vote)=>tallyWhole(chip(titleWords(rec)+(vote?` (${vote})`:""),`cstat ${recColour(rec)}`));
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
// ON THE VIDEOS TAB THE COUNTS ARE UNDER A HEADING OF THEIR OWN, below the
// moments (the owner, 19 November 2026), in their chips' colours as the
// docket's lines draw them (signins): support green, oppose red, neutral
// grey. The moments are round play buttons, which tells them apart.
const signinsHeaded=t=>{
  const s=signins(t);
  return s?`<div class="vwsg"><h4 class="vwsh">Public sign-ins</h4><p class="vwsign">${s}</p></div>`:"";
};
const signins=t=>{
  if(!t||!t.total)return "";
  const n=x=>Number(x||0).toLocaleString();
  // Each count is a chip, the one shape (components.js): a neutral ground,
  // and the support or the opposition in its ink and its bar.
  const bit=(v,label,cls)=>v?chip(`${n(v)} ${label}`,`sgn ${cls}`):"";
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
// THE LINK TAKES THE CITATION'S WHOLE TOKEN. A key is a chapter ("RSA 275")
// and the text may go on past it ("RSA 275:1", or the calendar's "RSA
// 275E:3"); the link was the key alone, and since every link that leaves the
// site carries its mark (D20, 8 October 2026) the mark landed inside the
// citation, "RSA 275↗E:3" (the review of the polish foundation). The rest of
// the token is in the link's words now, and where it points is unchanged.
function makeRsa(d){
  return (s)=>{const m=d.rsa||{},ks=Object.keys(m);
    if(!ks.length)return s;
    const re=new RegExp("("+ks.sort((a,b)=>b.length-a.length)
      .map(k=>k.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")).join("|")+")([\\w:.-]*\\w)?","g");
    // The site's own statute pages open here; only the General Court's, where
    // a night had no statute table, leave the site.
    return s.replace(re,(all,k)=>`<a href="${esc(m[k])}"`
      +(m[k].charAt(0)==="/"?"":` target="_blank" rel="noopener"`)+` class="rsa">${esc(all)}</a>`);};
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
  // The Reports tab's note ("The recommendation, the vote and the day it was
  // signed come from the docket; the reasoning ... in the committee's own
  // words") came out on 14 October 2026 at the person's ask, for the same
  // reason: each report already names its source under it.
};
const paneNote=(k)=>PANE_NOTE[k]?`<p class="src">${PANE_NOTE[k]}</p>`:"";

// THE OFFICIAL ANALYSIS AND A BILL'S NOTE are sections of renderSummary since
// 10 October 2026. The note is Granite Record's words, not the General
// Court's, and says so under it: HB1 has been the state budget in every term
// since 1993-1994 and its title says only "making appropriations for the
// expenses of certain departments of the state". A long analysis is clamped
// and given a button by clampAnalysis(), which measures rather than guessing
// from a character count.

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

  // WHAT IS MISSING, AND NOTHING ELSE (the audit of 25 October 2026, S4).
  // This note also said where the record's boundaries fall -- the named roll
  // calls in 1999, the House's written reports in 1997 -- and what was here,
  // which the tabs beside it show: 79 words on HB 200 of 1997, whose
  // Summary had just said the House killed it "on a roll call 286-57" while
  // its Votes tab said there were none. Each boundary is said once, where
  // the reader asks: the roll calls' on the Votes tab (renderVotes), the
  // written reports' on each report the Reports tab draws (renderReports),
  // the recordings' at the top of the Hearings tab (renderHearings), the
  // bill's own text on the Bill Text tab (renderBillText). And a boundary is
  // not a gap: the roll calls of a term before 1999 are not listed below as
  // missing, nor the written reports of one before 1997.
  //
  // The !c.docket branch is NOT dead code: it is the state every backfill
  // term passes through, between landing in data/bills.json and having its
  // docket narrated.
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
    return P(`This bill is from an earlier term. Here: ${and(have)}. Not on
      this site yet for its term: ${and(gaps)}.`);
  }

  // Has a docket. What is missing beyond it is what the reader needs told,
  // and where nothing is, there is no note. The written reports are the
  // House committees': no archived term has a Senate committee's.
  const gaps=[];
  if(!hasSp)gaps.push("the sponsors");
  if(!c.reports&&y>=1997)gaps.push("the House committees' written reports");
  if(!c.votes&&y>=1999)gaps.push("the roll calls naming individual members");
  if(!c.video&&y>=2019)gaps.push("a recording of any hearing");
  if(!gaps.length)return "";
  return P(`This bill is from an earlier term, and its docket is here: every
    action the General Court recorded, and the committee's recommendation and
    the vote on it. Not on this site yet for its term: ${and(gaps)}.`);
}

