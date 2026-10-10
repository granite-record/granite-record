// GRANITE_VERSION: 2026-10-09.6
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
