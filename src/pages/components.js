// GRANITE_VERSION: 2026-10-09.21
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
// IN SPANISH, DAY FIRST, where a caller names the language "es": the forms
// of components.py's _date_words_es and _date_span_es ("19 de febrero de
// 2026", "19 feb. 2026", "5–11 de octubre de 2026"). A page in Spanish
// passes window.GR_LANG; nothing here reads it, so a case can ask for either.
var DW_ES={months:["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
  "septiembre","octubre","noviembre","diciembre"],
  mons:["ene.","feb.","mar.","abr.","may.","jun.","jul.","ago.","sept.","oct.","nov.","dic."],
  days:["lunes","martes","miércoles","jueves","viernes","sábado","domingo"],
  dys:["lun.","mar.","mié.","jue.","vie.","sáb.","dom."]};
function dateWords(iso,form,lang){
  var s=iso==null?"":String(iso), m=/^(\d{4})-(\d\d)-(\d\d)/.exec(s);
  if(!m)return s;
  var y=+m[1], mo=+m[2], d=+m[3], t=new Date(Date.UTC(y,mo-1,d));
  if(t.getUTCFullYear()!==y||t.getUTCMonth()!==mo-1||t.getUTCDate()!==d)return s;
  if(lang==="es"){
    var mes=DW_ES.months[mo-1], ms=DW_ES.mons[mo-1], dia=DW_ES.days[(t.getUTCDay()+6)%7],
      di=DW_ES.dys[(t.getUTCDay()+6)%7];
    switch(form){
      case "long": return dia+", "+d+" de "+mes+" de "+y;
      case "full": return d+" de "+mes+" de "+y;
      case "short": return d+" "+ms;
      case "day": return dia+", "+d+" de "+mes;
      case "wkd": return di+", "+d+" "+ms;
      default: return d+" "+ms+" "+y;
    }
  }
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
function dateSpan(a,b,form,lang){
  form=form||"full";
  if(String(a).slice(0,10)===String(b).slice(0,10))return dateWords(a,form,lang);
  if(lang==="es"){
    var f=form==="medium"?"medium":"full", sa=String(a).slice(0,10), sb=String(b).slice(0,10);
    var ea=dateWords(sa,f,"es"), eb=dateWords(sb,f,"es");
    if(ea===sa||eb===sb)return ea+" – "+eb;
    if(sa.slice(0,4)!==sb.slice(0,4))return ea+" – "+eb;
    if(f==="medium"){
      var p=ea.split(" "), q=eb.split(" ");
      if(p[1]===q[1])return p[0]+"–"+q[0]+" "+q[1]+" "+q[2];
      return p[0]+" "+p[1]+" – "+q[0]+" "+q[1]+" "+q[2];
    }
    var ma=+sa.slice(5,7), mb=+sb.slice(5,7), da=+sa.slice(8,10), db=+sb.slice(8,10);
    if(ma===mb)return da+"–"+db+" de "+DW_ES.months[mb-1]+" de "+sb.slice(0,4);
    return da+" de "+DW_ES.months[ma-1]+" – "+db+" de "+DW_ES.months[mb-1]+" de "+sb.slice(0,4);
  }
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
function clock(t,lang){
  const m=/^(\d{1,2}):(\d\d)/.exec(String(t||""));
  if(!m||+m[1]>23)return String(t||"");
  const h=+m[1];
  if(lang==="es")return (h%12||12)+":"+m[2]+"\u00a0"+(h<12?"a.":"p.")+"\u00a0m.";
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

// A committee's whole name for a sentence: components.py's cmte_title.
function cmteTitle(name,chamber){
  name=String(name==null?"":name);chamber=String(chamber==null?"":chamber);
  if(chamber&&name.toLowerCase().startsWith(chamber.toLowerCase()+" "))return name;
  if(/\bcommittee\b/i.test(name))return `${chamber} ${name}`.trim();
  return `${chamber} Committee on ${name}`.trim();
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
  // A NAME IS NOT TRANSLATED (23 October 2026): a browser's translation
  // leaves the chip's name and seat alone and translates its role.
  return `<span class="mchip p-${esc(code)}" translate="no">${
    m.slug?`<a href="legislator/${esc(m.slug)}.html">${who}</a>`:who}${
    role?` <i translate="yes">${esc(role)}</i>`:""}</span>`;};

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
  law:'<path d="M12 3.25v17.5M7.75 20.75h8.5M4.75 6.75h14.5M12 3.25v3.5"/>'+
    '<path d="M4.75 6.75 2.25 13a2.5 2.5 0 0 0 5 0zM19.25 6.75 16.75 13a2.5 2.5 0 0 0 5 0z"/>',
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
  play:'<path fill="currentColor" stroke="none" d="M8 5.5v13l10.5-6.5z"/>',
  globe:'<circle cx="12" cy="12" r="8.75"/><path d="M3.25 12h17.5"/>'+
    '<path d="M12 3.25c2.4 2.4 3.6 5.3 3.6 8.75s-1.2 6.35-3.6 8.75c-2.4-2.4-3.6-5.3-3.6-8.75'+
    's1.2-6.35 3.6-8.75z"/>',
  // the Resources hub's topics (build_civics.badge; 24 October 2026)
  capitol:'<path d="M3.25 20.75h17.5M4.25 13.25h15.5"/><path d="M5.75 20.75v-7.5M9.25 20.75v-7.5M14.75 20.75v-7.5M18.25 20.75v-7.5"/><path d="M6.75 13.25a5.25 5.25 0 0 1 10.5 0"/><path d="M12 8V3.25h2.5"/>',
  ballot:'<rect x="3.75" y="11.25" width="16.5" height="9.5" rx="1"/><path d="M7.75 11.25v-7.5h8.5v7.5"/><path d="M10 7.5l1.5 1.5 3-3"/><path d="M8.5 15.75h7"/>',
  car:'<path d="M4.75 12.25 6.4 7.6a1.5 1.5 0 0 1 1.4-1h8.4a1.5 1.5 0 0 1 1.4 1l1.65 4.65"/><rect x="3.25" y="12.25" width="17.5" height="5" rx="1.25"/><path d="M6 17.25v2.5M18 17.25v2.5"/><circle cx="7.25" cy="14.75" r=".75"/><circle cx="16.75" cy="14.75" r=".75"/>',
  heart:'<path d="M12 20.25s-7.75-4.6-7.75-10.1A4.15 4.15 0 0 1 12 7.6a4.15 4.15 0 0 1 7.75 2.55c0 5.5-7.75 10.1-7.75 10.1z"/>',
  house:'<path d="M3.5 11 12 4l8.5 7"/><path d="M5.75 9.25v11.5h12.5V9.25"/><path d="M10 20.75v-5.5h4v5.5"/>',
  pin:'<path d="M12 21s-6.25-6.1-6.25-11a6.25 6.25 0 0 1 12.5 0c0 4.9-6.25 11-6.25 11z"/><circle cx="12" cy="10" r="2.25"/>',
  columns:'<path d="M3.25 20.75h17.5M4.25 9.25h15.5L12 4z"/><path d="M6.75 9.25v11.5M10.25 9.25v11.5M13.75 9.25v11.5M17.25 9.25v11.5"/>',
  chart:'<path d="M3.75 20.25h16.5"/><path d="M6.75 20.25v-6M11 20.25V8.75M15.25 20.25v-9M19.25 20.25V5.75"/>',
  map:'<path d="M3.75 6.25 9 4l6 2.25 5.25-2.25v13.75L15 20l-6-2.25-5.25 2.25z"/><path d="M9 4v13.75M15 6.25V20"/>',
  idcard:'<rect x="2.75" y="5.25" width="18.5" height="13.5" rx="1.5"/><circle cx="8.5" cy="11" r="2"/><path d="M5.5 15.75c.6-1.5 1.6-2.25 3-2.25s2.4.75 3 2.25"/><path d="M14 10h4.5M14 13.25h3"/>',
  gavel:'<path d="M9.4 7.25 12.25 4.4l6.35 6.35-2.85 2.85z"/><path d="M12.6 10.4 4.75 18.25"/><path d="M13 20.75h7.5"/>',
  box:'<path d="M3.75 8.25 12 4.25l8.25 4v9.5L12 21.75l-8.25-4z"/><path d="M3.75 8.25 12 12.25l8.25-4M12 12.25v9.5"/><path d="M7.9 6.25l8.25 4"/>',
  signpost:'<path d="M12 3.25v17.5M8.75 20.75h6.5"/><path d="M12 5.25h6.5l2 2-2 2H12"/><path d="M12 11.25H5.5l-2 2 2 2H12"/>',
  grid:'<rect x="4" y="4" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1"/>',
  // The outdoors: fishing, hunting and boating (25 October 2026).
  tree:'<path d="M12 3.25 7 9.75h2.75L5.5 15.25h13l-4.25-5.5H17z"/><path d="M12 15.25v5.5M9.25 20.75h5.5"/>'
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
  return `<a class="bmention" href="${esc(href)}" translate="no">${esc(n)}${y}</a>`;
}

// A bill as one row: components.bill_row.
function billRow(r){
  const chp=r.word?chip(r.word,"cstat "+String(r.cls||"")):"";
  const year=r.year?`<span class="byr">(${esc(r.year)})</span>`:"";
  const line=r.line?`<span class="brline">${r.line}</span>`:"";
  return `<div class="brow"><a class="brnum" href="${esc(r.href)}" translate="no">`+
    `${esc(r.n)}${year}</a><span class="brtitle" translate="no">${esc(r.title)}</span>${chp}${line}</div>`;
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
  const title=opened===null?`<div class="ctitle" translate="no">${esc(c.title)}</div>`
    :`<button type="button" class="ctitle" aria-expanded="${opened?"true":"false"}" translate="no">`+
     `${esc(c.title)}</button>`;
  const meta=c.byline?`<div class="cmeta">${c.byline}</div>`:"";
  const line=c.line?`<div class="cline">${c.line}</div>`:"";
  const body=c.body==null?"":`<div class="cbody"${opened?"":" hidden"}>${c.body}</div>`;
  const more=c.card?` ${c.card}`:"";
  const num=c.href?`<a class="cnum" href="${esc(c.href)}" translate="no">${esc(c.n)}${year}</a>`
    :`<span class="cnum" translate="no">${esc(c.n)}${year}</span>`;
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
  return slug?`<a class="psent" href="legislator/${esc(slug)}.html" translate="no">${esc(full)}</a>`:esc(full);
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

// WHAT RETIRES ON A DAY (the members-elect, 16 October 2026):
// components.until_attrs. An element that retires on `until` carries it in
// data-until, and is hidden from that day on -- by the reader's own date in
// the browser, which the behaviour below hands it.
function untilAttrs(until,today){
  const u=until==null?"":String(until).slice(0,10), t=today==null?"":String(today).slice(0,10);
  if(!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(u))return " hidden";
  const gone=/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(t)&&t>=u;
  return ` data-until="${esc(u)}"`+(gone?" hidden":"");
}

// MEMBERS-ELECT, DRAWN ONE WAY (the person's decisions of 16 October 2026):
// components.elect_now, elect_race, elect_block and elect_line, which say
// why. The My Town card, the district map's panel and a member's own page
// draw them here, the town pages and the Officials tab in Python, and
// preflight holds the two to one answer. Each element carries data-elect
// and untilAttrs; handed no day, as the browser's scripts hand it, the
// behaviour below judges it by the reader's clock.
function electNow(takesOffice,today){
  return `<p class="elnow" data-elect${untilAttrs(takesOffice,today)}>${tr("elect.serving","Serving now")}</p>`;
}
function electRace(race,lang){
  const r=race||{}, won=r.elected||[];
  const chips=won.map(e=>{
    const p=String(e.p||"");
    return "<li>"+pchip({party_code:p.length===1?p:"X",
      display_full:p?`${e.n||""} (${p})`:(e.n||""),
      slug:e.id&&e.s?e.s:""})+"</li>";
  });
  const left=(r.seats||0)-won.length-(r.not_final||0);
  return (chips.length?'<ul class="ellist">'+chips.join("")+"</ul>":"")
    +(r.not_final?'<p class="elnf"><b>'+tr("elect.not_final","Result not final")+"</b>"
      +(r.recount?" "+tr("elect.recount","&mdash; a recount was requested"):"")+"</p>":"")
    +(left>0?'<p class="elnone">'+(left===1?tr("elect.none_one","No member-elect on file for {n} seat.",{n:left})
      :tr("elect.none","No member-elect on file for {n} seats.",{n:left}))+"</p>":"");
}
function electBlock(races,election,takesOffice,today,lang){
  const body=(races||[]).map(([label,race])=>
    (label?`<p class="elwhere">${esc(label)}</p>`:"")+electRace(race,lang)).join("");
  return `<div class="elect" data-elect${untilAttrs(takesOffice,today)}>`+
    `<p class="elhead"><b>${tr("elect.elected","Elected {day}",{day:esc(dateWords(election,"full",lang))})}</b> `+
    `<span>${tr("elect.takes","Takes office {day}.",{day:esc(dateWords(takesOffice,"full",lang))})}</span></p>${body}</div>`;
}
function electLine(key,election,takesOffice,today){
  const m=/^(?:H\|([^|]+)\|([0-9]+)|S\|([0-9]+))$/.exec(key==null?"":String(key));
  const where=!m?"":m[3]?`Senate District ${m[3]}`:`${m[1]} district ${m[2]}`;
  return `<p class="elline" data-elect${untilAttrs(takesOffice,today)}>`+
    `Elected ${esc(dateWords(election,"full"))}`+(where?`, for ${esc(where)}`:"")+
    `. Takes office ${esc(dateWords(takesOffice,"full"))}.</p>`;
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
      // IN ANOTHER LANGUAGE (the owner, 24 October 2026): the term as the
      // record prints it, then its name and meaning in the page's language,
      // where the shared words file gives them (i18n.gloss_js, GR_GLOSS).
      var L=(typeof window!=="undefined"&&window.GR_GLOSS||{})[k];
      p.innerHTML=L&&L.says
        ?"<b lang=\"en\">"+esc(e.name||k)+"</b>"+(L.name&&L.name!==e.name?" ("+esc(L.name)+")":"")
          +" &mdash; "+esc(L.says)
        :"<b>"+esc(e.name||k)+"</b>"+(e.says?" &mdash; "+esc(e.says):"");
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
// WHAT RETIRES ON A DAY GOES BY THE READER'S CLOCK (the members-elect, 16
// October 2026). Every element carrying data-until is judged by untilAttrs
// with the reader's own date, when the page loads and whenever it draws
// itself again, and hidden from that day on: a page built on 1 December and
// read on the 3rd -- a night held, a copy a browser kept -- shows no
// member-elect, because the day they take office has come. Only ever hides:
// what the build hid stays hidden whatever the reader's clock says. The
// reader's day by that choice, not because a day's name is the reader's: a
// day someone takes office is an event in Concord, as a testimony deadline
// is, and that one is Concord's (TWO CLOCKS, ON PURPOSE, at app.js's nhDay,
// says why and leaves this one open).
(function(){
  if(typeof document==="undefined"||!document.querySelectorAll)return;
  function day(){
    var d=new Date();
    return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+
      String(d.getDate()).padStart(2,"0");
  }
  function judge(){
    var t=day(), all=document.querySelectorAll("[data-until]");
    for(var i=0;i<all.length;i++){
      var el=all[i];
      if(!el.hidden&&/ hidden$/.test(untilAttrs(el.getAttribute("data-until"),t)))el.hidden=true;
    }
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",judge);else judge();
  if(typeof MutationObserver!=="undefined")
    new MutationObserver(judge).observe(document.documentElement,{childList:true,subtree:true});
})();
// THE PAGE'S WORDS (23 October 2026; i18n.py says how they are kept).
// tr(key, English, vals) is the English, or the words of the page's
// language for it where the page carries them (window.GR_WORDS, which
// i18n.page_words writes into the head of a page in another language);
// {name} in either is filled from vals. The key and the English are written
// in each call as double-quoted strings, so the build and preflight can read
// every one. Here, among the behaviour, because it reads what the page
// carries rather than answering a case: a global set on the window, which
// declares no name of its own (_spanish_dates runs it).
(typeof window!=="undefined"?window:globalThis).tr=function(key,en,vals){
  var w=typeof window!=="undefined"&&window.GR_WORDS,
    s=w&&Object.prototype.hasOwnProperty.call(w,key)?w[key]:en;
  return vals?String(s).replace(/\{([a-z_][a-z0-9_]*)\}/g,function(m,k){
    return Object.prototype.hasOwnProperty.call(vals,k)?vals[k]:m;}):s;
};
// A MISTAKE IN A TRANSLATION, REPORTED FROM THE PAGE (the owner, 24 October
// 2026: "We should also add a report button for translation inaccuracy.").
// On a page in another language (<html lang> not "en") the footer's button,
// [data-trreport], written hidden (chrome.tr_report), is shown; while words
// of the page are selected a small button in the corner offers the same.
// Either opens one box, which posts to /api/report as a record's own box does
// (app.js, reportBox): the kind "translation", the page's address, which
// names its language, the reader's words and, where they had selected some
// of the page before pressing, those words too, so a proofreader's note says
// which sentence it means. Nothing identifies the reader. If the send fails
// they keep their words and are offered an email with all of it filled in.
// functions/api/report.js keeps it only from a page the site built in that
// language. In this file, among the behaviour, because the words file of a
// page in another language (/lang/<code>.js) carries what it says (tr).
(function(){
  if(typeof document==="undefined"||!document.addEventListener||!document.documentElement)return;
  var lang=document.documentElement.getAttribute("lang")||"en";
  if(lang==="en")return;
  var TO="contact@graniterecord.org", MAXQ=300, MAXW=650, box=null, pill=null, back=null;
  var quote="", held="", opened=0, build=null;
  function picked(){
    var s=typeof window!=="undefined"&&window.getSelection?window.getSelection():null;
    if(!s||s.isCollapsed||!s.rangeCount)return "";
    var main=document.getElementById("main"), n=s.getRangeAt(0).commonAncestorContainer;
    if(!main||!n||!main.contains(n))return "";
    var t=String(s).replace(/\s+/g," ").trim();
    return t.length>MAXQ?t.slice(0,MAXQ-1)+"…":t;
  }
  function make(){
    box=document.createElement("div");
    box.className="trbox";box.hidden=true;
    box.setAttribute("role","dialog");box.setAttribute("aria-labelledby","trbox-h");
    box.innerHTML='<form class="trform" novalidate><div class="trhead"><h2 id="trbox-h">'
      +esc(tr("trrep.title","Report a mistake in the translation"))+'</h2>'
      +'<button type="button" class="trclose" aria-label="'+esc(tr("trrep.close","Close"))+'">×</button></div>'
      +'<p class="trwhat">'+tr("trrep.what","Tell us what is wrong in this page&rsquo;s translation, and how it should read if you know. Nothing here identifies you, which also means we cannot reply: for an answer, write to {to}.",
        {to:'<a href="mailto:'+TO+'">'+TO+"</a>"})+"</p>"
      +'<div class="trquote" hidden><p class="trql">'+esc(tr("trrep.selected","The words you selected:"))+"</p>"
      +'<blockquote class="trq"></blockquote><label class="trinc"><input type="checkbox" name="quote" checked> '
      +esc(tr("trrep.include","Send them with your note"))+"</label></div>"
      +'<p><label>'+esc(tr("trrep.wrong","What is wrong?"))+'<br><textarea name="note" rows="4" maxlength="'+MAXW+'"></textarea></label></p>'
      +'<p style="position:absolute;left:-9999px" aria-hidden="true"><label>Leave this empty '
      +'<input name="website" tabindex="-1" autocomplete="off"></label></p>'
      +'<p><button type="submit">'+esc(tr("trrep.send","Send"))+'</button> '
      +'<span class="trstate" role="status" aria-live="polite"></span></p></form>';
    document.body.appendChild(box);
  }
  function open(from){
    if(!box)make();
    back=from||null;
    var q=box.querySelector(".trquote");
    q.hidden=!quote;
    box.querySelector(".trq").textContent=quote;
    box.querySelector(".trstate").textContent="";
    box.hidden=false;
    if(pill)pill.hidden=true;
    opened=Date.now();
    if(build===null){
      build="";
      fetch("/build.json").then(function(r){return r.ok?r.json():{};})
        .then(function(d){build=String((d&&d.finished)||"");}).catch(function(){});
    }
    var t=box.querySelector("textarea");
    if(t&&t.focus)t.focus();
  }
  function shut(){
    if(!box||box.hidden)return;
    box.hidden=true;
    if(back&&back.focus)back.focus();
  }
  function failed(st,payload,why){
    var subject="Translation problem on "+location.hostname+payload.url;
    var body=payload.note+"\n\n--\npage: "+location.origin+payload.url+"\nlanguage: "+lang
      +"\nbuild: "+(payload.build||"-")+"\n";
    st.innerHTML=esc(tr("trrep.failed","That did not send ({why}). Your words are still in the box.",{why:why}))
      +' <a href="mailto:'+TO+"?subject="+encodeURIComponent(subject)+"&amp;body="+encodeURIComponent(body)+'">'
      +esc(tr("trrep.by_email","Send it by email instead"))+"</a>.";
  }
  function send(form){
    var st=form.querySelector(".trstate"), btn=form.querySelector("button[type=submit]");
    var words=form.elements.note.value.trim();
    if(words.length<3){st.textContent=tr("trrep.few","Say in a few words what is wrong.");return;}
    var withq=quote&&form.elements.quote&&form.elements.quote.checked;
    var url=location.pathname.replace(/\.html$/,"");
    var payload={record:"translation:"+url,url:url,tab:"",field:"translation",
      note:(withq?"«"+quote+"»\n\n":"")+words,build:build||"",
      elapsed:Date.now()-(opened||Date.now()),website:form.elements.website.value};
    btn.disabled=true;
    st.textContent=tr("trrep.sending","Sending…");
    var ctl=typeof AbortController!=="undefined"?new AbortController():null;
    var timer=setTimeout(function(){if(ctl)ctl.abort();},6000);
    return fetch("/api/report",{method:"POST",signal:ctl?ctl.signal:undefined,
      headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})
      .then(function(r){
        // 503 and 429 are the Function's answers for a report it accepted
        // and could not keep (report.js), so each says so in words.
        if(!r.ok)throw new Error(r.status===503?tr("trrep.unsaved","the site could not save it just now"):
          r.status===429?tr("trrep.full","the site is taking no more reports just now"):
          tr("trrep.status","the server answered {n}",{n:r.status}));
        form.elements.note.value="";
        st.textContent=tr("trrep.thanks","Thank you. We will check the translation.");
      })
      .catch(function(err){
        failed(st,payload,err&&err.name==="AbortError"?tr("trrep.timeout","no answer in six seconds"):
          (err&&err.message)||tr("trrep.offline","no connection"));
      })
      .then(function(){clearTimeout(timer);btn.disabled=false;});
  }
  function arm(){
    var all=document.querySelectorAll("[data-trreport]");
    for(var i=0;i<all.length;i++)all[i].hidden=false;
    if(!pill&&document.body){
      pill=document.createElement("button");
      pill.type="button";pill.className="trpill";pill.hidden=true;
      pill.setAttribute("data-trreport","pill");
      pill.textContent=tr("trrep.pill","Report a mistake in these words");
      document.body.appendChild(pill);
    }
  }
  // The words selected when the button is pressed: a press can take the
  // selection away before the click arrives, so it is held at the press.
  document.addEventListener("pointerdown",function(e){
    if(e.target.closest&&e.target.closest("[data-trreport]"))held=picked();
  },true);
  document.addEventListener("click",function(e){
    var b=e.target.closest&&e.target.closest("[data-trreport]");
    if(b){quote=picked()||held;held="";open(b);return;}
    if(e.target.closest&&e.target.closest(".trclose"))shut();
  });
  document.addEventListener("submit",function(e){
    var f=e.target.closest&&e.target.closest(".trform");
    if(!f)return;
    e.preventDefault();
    send(f);
  });
  document.addEventListener("keydown",function(e){if(e.key==="Escape")shut();});
  document.addEventListener("selectionchange",function(){
    if(pill)pill.hidden=!picked()||!!(box&&!box.hidden);
  });
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",arm);else arm();
})();
// BEHAVIOUR:END
