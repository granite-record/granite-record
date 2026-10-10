// GRANITE_VERSION: 2026-10-09.8
/* THE SITE'S COMPONENTS, IN THE BROWSER. Published as site/components.js and
   loaded by every page, in its head, before app.js, find.js and any page's
   own script, so each of them draws a person, a committee, a date or a time
   with the same helper (the component plan's C1 and C2, approved 9 October
   2026).

   ONE FILE IN EACH LANGUAGE, THE SAME NAMES. components.py holds the same
   helpers for the pages built ahead in Python, each under the same name in
   that language's case: dateWords is date_words, cmteLink is cmte_link. The
   pages a browser draws need JavaScript and the pages built ahead need
   Python, so there are two; preflight keeps them one. Its check "every
   component gives the same answer in Python and in the browser" loads this
   file in node, runs every helper on each case in
   tests/components_cases.json, and compares the answer byte for byte with
   components.py's. It fails on a helper one file has and the other does
   not, a helper no case runs, and any part of a helper no case reaches, in
   either language.

   SO A HELPER HERE IS PURE AND THIN (C4): a plain value in, a string out,
   and no page's globals read -- cmteLink is handed meta.json's committee
   codes rather than reading META. The deciding happens once, upstream, in
   Python. What responds to a reader (a popover, an action) will live here
   too, attached by data attributes, so that it is written once.

   Moved here unchanged on 9 October 2026 from app.js, which drew with them
   already, and from the copies the home page's and the Calendar's scripts
   carried because they ran without app.js. */

/* THE WORDS, WRITTEN ONCE (C3). The chip's words and classes, the kinds of
   meeting, the vote words and the glossary are JSON files in
   src/pages/words/, which components.py reads for the builders. The build
   writes the same here, between the two markers below, as one const --
   WORDBOOK.chips, .meeting_kinds, .votes and .glossary -- which the browser's
   scripts draw with (build_pages.with_words). So this file as it sits in
   src/pages/ holds none of them and the site's copy holds all of them, and
   no table of words is typed twice. A marker missing, doubled or out of
   order stops the build, and preflight holds node's WORDBOOK to
   components.py's byte for byte. (Not WORDS: app.js has that name.) */
// WORDBOOK:START
// WORDBOOK:END

const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

// DATEWORDS:START
// A DATE, ONE WAY, MONTH FIRST (8 October 2026, the person's D6): components.py's
// date_words(), and preflight holds the two to one answer on every form. A
// date is "YYYY-MM-DD" at the start of a string; what is not one comes back
// as it came. The forms: long "Thursday, February 19, 2026"; full "February
// 19, 2026"; medium "Feb 19, 2026", the default; short "Feb 19"; day
// "Thursday, February 19"; wkd "Thu, Feb 19".
var DW_MONTHS=["January","February","March","April","May","June","July",
  "August","September","October","November","December"];
var DW_DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
function dateWords(iso,form){
  var s=iso==null?"":String(iso), m=/^(\d{4})-(\d\d)-(\d\d)/.exec(s);
  if(!m)return s;
  var y=+m[1], mo=+m[2], d=+m[3], t=new Date(Date.UTC(y,mo-1,d));
  if(t.getUTCFullYear()!==y||t.getUTCMonth()!==mo-1||t.getUTCDate()!==d)return s;
  var M=DW_MONTHS[mo-1], Mo=M.slice(0,3), W=DW_DAYS[(t.getUTCDay()+6)%7];
  switch(form){
    case "long": return W+", "+M+" "+d+", "+y;
    case "full": return M+" "+d+", "+y;
    case "short": return Mo+" "+d;
    case "day": return W+", "+M+" "+d;
    case "wkd": return W.slice(0,3)+", "+Mo+" "+d;
    default: return Mo+" "+d+", "+y;
  }
}
// Two days as one span: "October 5–11, 2026", "September 28 – October
// 4, 2026", "December 28, 2026 – January 3, 2027" -- components.date_span.
// The form "medium" says the months short: "Feb 9–13, 2026", the pager's.
function dateSpan(a,b,form){
  form=form||"full";
  if(String(a).slice(0,10)===String(b).slice(0,10))return dateWords(a,form);
  var fa=dateWords(a,form), fb=dateWords(b,form);
  if(fa===String(a)||fb===String(b))return fa+" – "+fb;
  var x=fa.replace(",","").split(" "), z=fb.replace(",","").split(" ");
  if(x[2]!==z[2])return fa+" – "+fb;
  if(x[0]!==z[0])return x[0]+" "+x[1]+" – "+z[0]+" "+z[1]+", "+z[2];
  return x[0]+" "+x[1]+"–"+z[1]+", "+z[2];
}
// DATEWORDS:END

// "13:30" -> "1:30 PM", as a reader says a time: components.clock. A
// no-break space keeps AM or PM with its time; anything that is not a time
// comes back as it was.
function clock(t){
  const m=/^(\d{1,2}):(\d\d)/.exec(String(t||""));
  if(!m||+m[1]>23)return String(t||"");
  const h=+m[1];
  return (h%12||12)+":"+m[2]+"\u00a0"+(h<12?"AM":"PM");
}

// A committee named on a bill, as a link to its page where there is one.
// 3,967 mentions across the site were plain text, so the reader who wanted
// "what else did this committee do" had nowhere to click.
//
// THE NAME AS THE BILL CARRIES IT, TO THE COMMITTEE IT WAS. A name is not
// always one committee: 1995's Corrections and Criminal Justice sits today as
// Criminal Justice and Public Safety, and the Senate's Election Law and
// Internal Affairs of 2007-2008 is not the committee of that name formed for
// 2017-2018. meta.json carries such a name as {"": page, "<term>": page}, and
// the term decides; the label is never changed to the later name. `codes` is
// that table, meta.json's committee_codes.
function cmteLink(name,term,codes){
  const v=(codes||{})[name];
  const code=typeof v==="string"?v
    :v?((term&&Object.prototype.hasOwnProperty.call(v,term))?v[term]:v[""]):"";
  return code?`<a href="committee/${esc(code)}.html">${esc(name)}</a>`:esc(name);
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
  // THE PARTY AND DISTRICT ARE ONE UNIT: "(R - Rock 2)" is a span app.css
  // keeps on one line, so a chip that has to wrap does so before it rather
  // than inside it (components.CHIP_TAG, which this matches).
  const full=String(m.display_full||m.label||m.name||"");
  const tag=full.match(/^(.*\S)\s+(\([^()]*\))$/);
  const who=tag?`${esc(tag[1])} <span class="mtag">${esc(tag[2])}</span>`:esc(full);
  // A LABEL, NOT BOLD. A committee roster has always labelled its Chair, Vice
  // Chair and Clerk through the <i> below, and the prime sponsor was marked
  // with bold alone -- which is not a label, cannot be told from emphasis, and
  // is nothing at all to a screen reader. It reuses the mechanism that was
  // already there rather than adding a second one.
  const role=(m.role&&m.role!=="Member")?m.role:(m.prime?"Prime":"");
  return `<span class="mchip p-${esc(code)}">${
    m.slug?`<a href="legislator/${esc(m.slug)}.html">${who}</a>`:who}${
    role?` <i>${esc(role)}</i>`:""}</span>`;};

// ONE CHIP, IN TWO SIZES (the component plan's step 3, approved 9 October
// 2026): components.chip. A bill's status, a meeting's kind, a vote's result,
// a party's letter and the neutral chip are this one span, which app.css
// draws in the person chip's frame -- 3px corners, a 1px edge, a 3px bar in
// the chip's own ink -- at 14px, or 16px where size is "m", in a head. `cls`
// is the family that colours it and the hook a page places it by, separated
// by spaces; the word comes as it is to be read, its case decided where it
// is made.
function chip(word,cls,size){
  const names=["chip"].concat(size==="m"?["chip-m"]:[],
    String(cls||"").split(" ").filter(Boolean));
  return `<span class="${esc(names.join(" "))}">${esc(word)}</span>`;
}

// A record's words as a chip says them, in Title Case: components.title_words.
// "INEXPEDIENT TO LEGISLATE" is "Inexpedient to Legislate" and "As amended by
// the house" "As Amended by the House"; the small words are meeting_kinds.json's;
// a word with a figure in it is kept, and so is a word in capitals among
// words that are not, which is an abbreviation ("RSA"). The record's own
// abbreviations, chips.json's "capitals", are capitals in any case it wrote
// them ("HB 143", not "Hb 143"), and a small word straight after a dash
// takes a capital, as a title's first word does ("FN - A - As Introduced").
function titleWords(s){
  const t=s==null?"":String(s), shout=!/[a-z]/.test(t), words=t.split(" ");
  const small=WORDBOOK.meeting_kinds.small, caps=WORDBOOK.chips.capitals;
  return words.map((w,i)=>{
    if(caps.indexOf(w.toUpperCase())>=0)return w.toUpperCase();
    if(/[0-9]/.test(w)||(!shout&&/^[^a-z]*[A-Z][^a-z]*[A-Z][^a-z]*$/.test(w)))return w;
    const low=w.toLowerCase();
    return i&&TW_DASHES.indexOf(words[i-1])<0&&small.indexOf(low)>=0?low
      :low.replace(/^([^A-Za-z]*)([a-z])/,(m,a,b)=>a+b.toUpperCase());
  }).join(" ");
}
// A word that is a dash alone, after which titleWords starts again.
const TW_DASHES=["-","–","—"];

// ICONS: the prototype kit's drawings (9 October 2026), components.ICONS --
// the same names, the same markup, held byte for byte. A drawing is never a
// control's only name: aria-hidden, so a screen reader reads the control's
// own words, and currentColor, so it takes the ink of what holds it. app.css
// sizes .icon in rem. A name the table does not hold draws nothing.
var ICON_PAINT='fill="none" stroke="currentColor" stroke-width="1.75" '+
  'stroke-linecap="round" stroke-linejoin="round"';
var ICONS={
  bill:'<path d="M6.25 2.75h7.75l4.25 4.25v14.25H6.25z"/><path d="M13.75 2.75v4.5h4.5"/>'+
    '<path d="M9 11.75h6.5M9 15h6.5M9 18.25h4"/>',
  person:'<circle cx="12" cy="7.75" r="3.75"/>'+
    '<path d="M4.5 20.75c.9-4.25 3.8-6.5 7.5-6.5s6.6 2.25 7.5 6.5"/>',
  committee:'<circle cx="6.25" cy="8.25" r="2.25"/><circle cx="12" cy="6.5" r="2.25"/>'+
    '<circle cx="17.75" cy="8.25" r="2.25"/><path d="M2.75 13.25h18.5"/>'+
    '<path d="M5.25 13.25v7.5M18.75 13.25v7.5"/><path d="M8.5 17h7"/>',
  book:'<path d="M12 6.75C9.6 5 6.6 4.6 3.25 5.25v13.5c3.35-.65 6.35-.25 8.75 1.5 '+
    '2.4-1.75 5.4-2.15 8.75-1.5V5.25C17.4 4.6 14.4 5 12 6.75z"/><path d="M12 6.75v13.5"/>',
  calendar:'<rect x="3.5" y="4.75" width="17" height="16" rx="1.5"/>'+
    '<path d="M3.5 9.75h17M8 2.75v4M16 2.75v4"/>'+
    '<path d="M7.25 13.25h3v3h-3z" fill="currentColor"/>',
  cite:'<path fill="currentColor" stroke="none" d="M4.5 18v-4.6c0-3.4 1.7-6 4.6-7.4l.9 1.6c-1.7 '+
    '1-2.6 2.4-2.8 4.2H10V18zM13.5 18v-4.6c0-3.4 1.7-6 4.6-7.4l.9 1.6c-1.7 1-2.6 2.4-2.8 '+
    '4.2H19V18z"/>',
  follow:'<path d="M6 16.5V11a6 6 0 0 1 12 0v5.5l1.5 1.75h-15z"/>'+
    '<path d="M10 20.75a2 2 0 0 0 4 0"/>',
  print:'<path d="M7 9V3.75h10V9"/><path d="M7 17.25H4.25v-7.5h15.5v7.5H17"/>'+
    '<path d="M7 14h10v6.25H7z"/>',
  testify:'<path d="M4.25 5.25h15.5v10.5H10.5l-4.5 3.75v-3.75H4.25z"/>'+
    '<path d="M8 9.25h8M8 12.25h5"/>',
  report:'<path d="M5.5 21.25V3.5"/><path d="M5.5 4.25h12.25L15 8.75l2.75 4.5H5.5"/>',
  share:'<path d="M12 15V3.25"/><path d="M7.75 7.5 12 3.25l4.25 4.25"/>'+
    '<path d="M8.75 10.75h-3v10h12.5v-10h-3"/>',
  search:'<circle cx="10.5" cy="10.5" r="6.25" stroke-width="2"/><path d="M15.25 15.25l5 5" stroke-width="2"/>',
  close:'<path d="M6 6l12 12M18 6L6 18" stroke-width="2"/>',
  play:'<path fill="currentColor" stroke="none" d="M8 5.5v13l10.5-6.5z"/>'
};
function icon(name){
  var inner=typeof name==="string"&&Object.prototype.hasOwnProperty.call(ICONS,name)?ICONS[name]:null;
  if(inner==null)return "";
  return '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false" '+
    ICON_PAINT+'>'+inner+'</svg>';
}

// ===========================================================================
// POLISH 2: THE RECORD PAGES' COMPONENTS (ws/records, 10 October 2026): the
// component plan's steps 4 to 8, approved 9 October 2026. Each is
// components.py's helper of the same name, held to one answer by
// _components_agree; read the reasons there.
// ===========================================================================
// Own keys only, so a word like "constructor" is never a table's. An object, not a
// function, so that it is no helper of its own (_components_agree).
const CMP={own:(o,k)=>Object.prototype.hasOwnProperty.call(o,k)};

// A bill CARD's chip word (D18): components.card_word.
function cardWord(word,passage){
  const s=word==null?"":String(word), ch=WORDBOOK.chips;
  if(CMP.own(ch.short,s))return ch.short[s];
  const pre=ch.short_prefix.find(x=>s.indexOf(x[0])===0);
  if(pre)return pre[1];
  const p=String(passage||""), names={H:"House",S:"Senate"};
  if(ch.short_passed.indexOf(s)>=0&&CMP.own(names,p.slice(0,1))&&p.slice(1,3).indexOf("p")>=0){
    const other=p.slice(0,1)==="H"?"S":"H";
    return "Passed "+names[p.slice(2,3)==="p"?other:p.slice(0,1)];
  }
  return titleWords(s);
}

// A bill named in running words: components.bill_mention.
function billMention(n,href,year){
  const y=year?` <span class="byr">(${esc(year)})</span>`:"";
  return `<a class="bmention" href="${esc(href)}">${esc(n)}${y}</a>`;
}

// A bill as one row: components.bill_row.
function billRow(r){
  const chp=r.word?chip(r.word,"cstat "+String(r.cls||"")):"";
  const year=r.year?`<span class="byr">(${esc(r.year)})</span>`:"";
  const line=r.line?`<span class="brline">${r.line}</span>`:"";
  return `<div class="brow"><a class="brnum" href="${esc(r.href)}">`+
    `${esc(r.n)}${year}</a><span class="brtitle">${esc(r.title)}</span>${chp}${line}</div>`;
}

// A card's line of who and where: components.bill_byline.
function billByline(sponsor,committees,topic,term,codes){
  const parts=(sponsor?[pchip(sponsor)]:[]).concat(
    (committees||[]).filter(Boolean).map(c=>cmteLink(c,term,codes)),topic?[esc(topic)]:[]);
  return parts.join(' <span class="cdot" aria-hidden="true">&middot;</span> ');
}

// A bill as a card: components.bill_card.
function billCard(c){
  const opened=c.open==null?null:c.open;
  const year=c.year?`<span class="cyear"> (${esc(c.year)})</span>`:"";
  const chp=c.word?chip(c.word,"cstat "+String(c.cls||""),"m"):"";
  const title=opened===null?`<div class="ctitle">${esc(c.title)}</div>`
    :`<button type="button" class="ctitle" aria-expanded="${opened?"true":"false"}">`+
     `${esc(c.title)}</button>`;
  const meta=c.byline?`<div class="cmeta">${c.byline}</div>`:"";
  const line=c.line?`<div class="cline">${c.line}</div>`:"";
  const body=c.body==null?"":`<div class="cbody"${opened?"":" hidden"}>${c.body}</div>`;
  const more=c.card?` ${c.card}`:"";
  const num=c.href?`<a class="cnum" href="${esc(c.href)}">${esc(c.n)}${year}</a>`
    :`<span class="cnum">${esc(c.n)}${year}</span>`;
  return `<article class="card${opened?" open":""}${more}" data-id="${esc(c.id)}">`+
    `<div class="chead"><div class="crow">${num}${chp}</div>${title}${meta}`+
    `${c.notes||""}${line}${c.rail||""}</div>${body}</article>`;
}

// THE DATED RAIL: components.rail_html, and its tables, which app.js's rail
// and How it got here read too (RL_MARK, RL_WAVE ...).
const RL_STOP={I:"Introduced",H:"House",S:"Senate",G:"Governor",L:"Law",V:"Voters"};
const RL_WAVE='<svg class="wave" viewBox="0 0 12 12" aria-hidden="true" focusable="false">'
  +'<path d="M1.7 7.4C2.9 4.8 4.5 4.6 6 6.1s3.1 1.4 4.3-1.2" fill="none" '
  +'stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
const RL_MARK={p:"✓",x:"✕",s:RL_WAVE};
const RL_SAY={p:"passed",h:"is here now",x:"stopped here","-":"never reached",
  s:"sent to interim study",t:"on the table"};
const RL_SAY_DIED={t:"laid on the table"};
const RL_SAID={s:"interim study",t:"tabled"};
const RL_CLASS={"-":"o",s:"istudy",t:"ontable"};
const RL_MON=DW_MONTHS.map(m=>m.slice(0,3));
function railHtml(stops,died){
  const st=(stops||[]).map(s=>{
    if(Array.isArray(s)){
      const row=s.concat(["","",""]), sm=String(row[0]||"");
      return {stop:CMP.own(RL_STOP,sm.slice(0,1))?RL_STOP[sm.slice(0,1)]:sm.slice(0,1),
        mark:sm.slice(1),date:row[1]||"",short:row[2]||"",say:""};
    }
    return {stop:s.stop||"",mark:s.mark||"",date:s.date||"",short:s.short||"",say:s.say||""};
  });
  if(!st.length)return "";
  const words=died?Object.assign({},RL_SAY,RL_SAY_DIED):RL_SAY;
  const cells=[], said=[];
  const mon="("+RL_MON.join("|")+")";
  st.forEach(s=>{
    const day=s.date?dateWords(s.date):"";
    const small=day?`<small>${esc(day.slice(0,-5))}<span class="ry">${esc(day.slice(-5))}</span></small>`:"";
    cells.push(`<span class="stop s-${esc((CMP.own(RL_CLASS,s.mark)&&RL_CLASS[s.mark])||s.mark)}"><b>`+
      `${CMP.own(RL_MARK,s.mark)?RL_MARK[s.mark]:""}</b><i>${esc(s.stop)}</i>${small}</span>`);
    const when=s.date?dateWords(s.date,"full"):"";
    const own=!!s.short&&["Governor","Law","Voters"].indexOf(s.stop)>=0&&["p","x"].indexOf(s.mark)>=0;
    const short=s.short===(CMP.own(RL_SAID,s.mark)?RL_SAID[s.mark]:null)?"":s.short;
    let what=s.say||(own?s.short:[CMP.own(words,s.mark)?words[s.mark]:"",short].filter(Boolean).join(", "));
    what=what.replace(/(\d)–(\d)/g,"$1 to $2")
      .replace(new RegExp("\\b"+mon+" (\\d{1,2}), (\\d{4})\\b","g"),(_m,mo,d,y)=>dateWords(
        `${y}-${String(RL_MON.indexOf(mo)+1).padStart(2,"0")}-${String(+d).padStart(2,"0")}`,"full"))
      .replace(new RegExp("\\b"+mon+" (\\d{4})\\b","g"),(_m,mo,y)=>`${DW_MONTHS[RL_MON.indexOf(mo)]} ${y}`);
    const lawDay=s.stop==="Law"&&s.mark==="p";
    const tail=!when?"":!lawDay?`, ${when}`:what.indexOf("in effect")>=0?"":`, in effect ${when}`;
    said.push(s.stop==="Introduced"?`Introduced${when?` ${when}`:""}`
      :`${s.stop}: ${what.slice(0,1).toLowerCase()+what.slice(1)}${tail}`);
  });
  const s_=esc(said.join("; "));
  return `<span class="rail dated" role="img" aria-label="${s_}" title="${s_}">${cells.join("")}</span>`;
}

// A person in a running sentence: components.person_link.
function personLink(m){
  const full=String(m.display_full||m.label||m.name||""), slug=m.slug||"";
  return slug?`<a class="psent" href="legislator/${esc(slug)}.html">${esc(full)}</a>`:esc(full);
}

// A term marked for its popover: components.term_mark.
function termMark(key,text){
  return `<span data-term="${esc(key)}">${esc(text)}</span>`;
}

// THE VOTE WORDS: components.vote_head and vote_chip.
function voteHead(key,own,fill){
  const v=WORDBOOK.votes, m=key==="consent"?v.consent:(CMP.own(v.motions,key)?v.motions[key]:null);
  const put=s=>Object.keys(fill||{}).reduce((a,k)=>a.split("{"+k+"}").join(String(fill[k])),s);
  if(m===null||m.motion==null)return esc(own||"");
  const gloss=esc(put(m.gloss||""));
  const abbr=m.abbr?termMark(m.abbr,m.abbr)+", ":"";
  return esc(put(m.motion))+(gloss?` (${abbr}${gloss})`:"");
}
function voteChip(key,passed,bill,fill){
  if(passed==null)return "";
  const v=WORDBOOK.votes;
  const m=(key==="consent"?v.consent:(CMP.own(v.motions,key)?v.motions[key]:null))||{};
  const pre=/^[A-Z]+/.exec(String(bill||"").toUpperCase());
  const noun=Object.keys(v.nouns).find(n=>pre&&v.nouns[n].indexOf(pre[0])>=0)||"";
  const all=Object.assign({},fill||{},{Bill:noun});
  const raw=m[passed?"passed":"failed"]||"";
  const put=raw.indexOf("{Bill}")>=0&&!noun?"":
    Object.keys(all).reduce((a,k)=>a.split("{"+k+"}").join(String(all[k])),raw);
  const tail=put.indexOf("{")>=0?"":put;
  return chip((passed?v.passed:v.failed)+(tail?`: ${tail}`:""),"rcres "+(passed?"pass":"fail"));
}

// THE RECORD'S HEAD: components.record_head.
function recordHead(h){
  const crumbs=(h.trail||[]).map(([lab,href])=>href
    ?`<li><a href="${esc(href)}">${esc(lab)}</a></li>`:`<li aria-current="page">${esc(lab)}</li>`).join("");
  const year=h.year?` <span class="ryear">(${esc(h.year)})</span>`:"";
  const facts=(h.facts||[]).slice(0,6).filter(f=>f[1]).map(f=>
    `<div><dt>${esc(f[0])}</dt><dd>${f[1]}`+(f.length>2&&f[2]?`<small>${f[2]}</small>`:"")+"</dd></div>").join("");
  const kind=h.kind?` rh-${esc(h.kind)}`:"";
  return `<header class="rhead${kind}">`
    +(crumbs?`<nav class="rtrail" aria-label="Where this page is"><ol>${crumbs}</ol></nav>`:"")
    +`<div class="rtop"><h1 class="rh1">${h.title||""}${year}</h1>`
    +`${h.chip||""}</div>`
    +(h.line?`<p class="rline">${h.line}</p>`:"")
    +(facts?`<dl class="rfacts">${facts}</dl>`:"")
    +(h.rail?`<div class="rrail">${h.rail}</div>`:"")
    +`<div class="racts">${h.actions||""}</div></header>`;
}

// A document of the record: components.doc_row.
function docRow(x){
  const of=x.of?`<span class="docof">${esc(x.of)}</span>`:"";
  return `<li class="doc doc-${esc(x.kind)}"><a href="${esc(x.url)}" `+
    `target="_blank" rel="noopener">${esc(x.label)}</a>${of}${x.what||""}</li>`;
}

// A W4 section: components.section.
function section(heading,body,sid){
  const i=sid?` id="${esc(sid)}"`:"";
  return `<section class="w4"${i}><h2 class="w4h">${esc(heading)}</h2>`+
    `<div class="w4b">${body}</div></section>`;
}

// BEHAVIOUR:START
// THE TERM POPOVERS (the component plan's C9, approved 9 October 2026: "for
// the tooltips they would show up on a tap or on a mouse hover after a short
// time"). The FIRST visible span[data-term="ITL"] of each term on the page
// becomes a button that opens glossary.json's entry -- its name in full and
// what it means -- on a tap or a click, on a pointer held over it about half
// a second, or on keyboard focus; it stays while the pointer moves onto it,
// and closes on Escape, on a press elsewhere or when focus leaves (WCAG
// 1.4.13: dismissible, hoverable, persistent). Later ones of the same term
// stay as the words they are. Drawn again whenever the page draws itself
// again (a tab, a term, a record arriving), so the first stays the first.
// BEHAVIOUR, NOT A HELPER: an IIFE, which declares no name of its own, so
// _components_agree holds the helpers above and _term_popovers this.
(function(){
  if(typeof document==="undefined"||!document.addEventListener||typeof WORDBOOK==="undefined")return;
  var G=WORDBOOK.glossary||{}, HOLD=500, n=0, open=null, wait=0, shut=0, again=0;
  var has=function(k){return Object.prototype.hasOwnProperty.call(G,k);};
  function plain(s){
    var b=s.querySelector(".termbtn");
    var t=b?b.textContent:s.textContent;
    s.classList.remove("term");
    s.textContent=(s.getAttribute("data-pre")||"")+t+(s.getAttribute("data-post")||"");
  }
  function arm(){
    var seen={}, all=document.querySelectorAll("[data-term]");
    for(var i=0;i<all.length;i++){
      var s=all[i], k=s.getAttribute("data-term");
      if(!has(k)||(s.closest&&s.closest("[hidden]"))||(s.parentNode&&s.parentNode.closest&&
        s.parentNode.closest("a,button,summary,label")))continue;
      if(seen[k]){if(s.classList.contains("term"))plain(s);continue;}
      seen[k]=1;
      if(s.classList.contains("term"))continue;
      var e=G[k], id="gr-term-"+(++n), word=s.textContent;
      s.textContent="";s.classList.add("term");
      var b=document.createElement("button");
      b.type="button";b.className="termbtn";b.textContent=word;
      b.setAttribute("aria-expanded","false");b.setAttribute("aria-controls",id);
      b.setAttribute("aria-describedby",id);
      var p=document.createElement("span");
      p.className="termpop";p.id=id;p.setAttribute("role","tooltip");p.hidden=true;
      p.innerHTML="<b>"+esc(e.name||k)+"</b>"+(e.says?" &mdash; "+esc(e.says):"");
      // THE BRACKET STAYS WITH ITS WORD: a button is set as a box of its own,
      // and a phone broke "Ought to Pass (" from "OTP)" at it (the look of 10
      // October 2026). The mark either side comes into the word's span,
      // which does not break.
      var pre=s.previousSibling, post=s.nextSibling, a="", z="";
      if(pre&&pre.nodeType===3&&/[(\[\u201c"]$/.test(pre.data)){a=pre.data.slice(-1);pre.data=pre.data.slice(0,-1);}
      if(post&&post.nodeType===3&&/^[)\],.;:\u201d"]/.test(post.data)){z=post.data.charAt(0);post.data=post.data.slice(1);}
      s.setAttribute("data-pre",a);s.setAttribute("data-post",z);
      if(a)s.appendChild(document.createTextNode(a));
      s.appendChild(b);
      if(z)s.appendChild(document.createTextNode(z));
      s.appendChild(p);
    }
  }
  function pop(b){return b&&document.getElementById(b.getAttribute("aria-controls"));}
  function hide(b){
    var p=pop(b);
    if(p)p.hidden=true;
    if(b)b.setAttribute("aria-expanded","false");
    if(open===b)open=null;
  }
  function show(b){
    if(open&&open!==b)hide(open);
    var p=pop(b);
    if(!p)return;
    p.hidden=false;p.style.left="";
    b.setAttribute("aria-expanded","true");open=b;
    // Kept on the screen: moved left by however far it runs past the right.
    var r=p.getBoundingClientRect(), w=document.documentElement.clientWidth;
    if(r.right>w-8)p.style.left=Math.round(Math.min(0,w-8-r.right))+"px";
  }
  document.addEventListener("click",function(e){
    var b=e.target.closest&&e.target.closest(".termbtn");
    if(b){e.preventDefault();e.stopPropagation();
      if(open===b&&!wait)hide(b);else show(b);
      clearTimeout(wait);wait=0;return;}
    if(open&&!(e.target.closest&&e.target.closest(".termpop")))hide(open);
  },true);
  document.addEventListener("pointerover",function(e){
    var t=e.target.closest&&e.target.closest(".term");
    if(!t||e.pointerType!=="mouse")return;
    clearTimeout(shut);
    var b=t.querySelector(".termbtn");
    if(b&&open!==b&&!wait)wait=setTimeout(function(){wait=0;show(b);},HOLD);
  });
  document.addEventListener("pointerout",function(e){
    var t=e.target.closest&&e.target.closest(".term");
    if(!t||e.pointerType!=="mouse"||(e.relatedTarget&&t.contains(e.relatedTarget)))return;
    clearTimeout(wait);wait=0;
    var b=t.querySelector(".termbtn");
    if(b&&open===b&&document.activeElement!==b)shut=setTimeout(function(){hide(b);},250);
  });
  document.addEventListener("focusin",function(e){
    var b=e.target.closest&&e.target.closest(".termbtn");
    if(b)show(b);
    else if(open&&!(e.target.closest&&e.target.closest(".term")))hide(open);
  });
  document.addEventListener("keydown",function(e){
    if(e.key==="Escape"&&open){var b=open;hide(b);if(document.activeElement!==b)b.focus();}
  });
  function soon(){clearTimeout(again);again=setTimeout(arm,40);}
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",arm);else arm();
  if(typeof MutationObserver!=="undefined")
    new MutationObserver(soon).observe(document.documentElement,{childList:true,subtree:true,
      attributes:true,attributeFilter:["hidden"]});
})();
// BEHAVIOUR:END
