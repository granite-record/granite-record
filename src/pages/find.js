// GRANITE_VERSION: 2026-09-16.41
/* FIND ANYTHING, FROM THE HEADER (16 September, asked for in these words:
   "a search icon in the header that lets you search for anything including
   legislators, committees, towns, and bills ... searching Litchfield would
   show both the town and Rep Melissa Litchfield").

   The bill search is a page; this is the box on every page for the things that
   are not bills. It reads site/find.json -- 406 sitting members, the 1,785
   who have left, every committee, every town and ward, the 43 subjects and
   the fixed pages: 322 KB, 58 KB over the wire -- fetched once, the first
   time somebody opens the box, so no page pays for it up front. Bills are not
   in that file on purpose: 33,683 rows is more than a megabyte. A bill NUMBER
   is recognised here and offered as the first answer, because that is the
   one bill lookup that needs no index; any other words are also looked for
   in the current term's bills, from that term's own index, fetched the first
   time they are needed -- see BILLS, IN THE SAME BOX below. /search, the
   full results, looks in every term's.

   WHAT 18 SEPTEMBER ADDED, in the person's words:

     "listing them like individual entries" -- one row per thing found, each
     naming what it is, rather than a list of bills with everything else in a
     separate block underneath.

     "Search bar should also list former legislators in the results, but
     prioritize to the most recent bills and current legislators before
     listing former ones", and they are named "Former Rep. David Smith"
     rather than carrying a box that says FORMER. Among themselves they are
     ordered by how recently they sat.

     "You should be able to search for topics in the search bar as well" --
     typing education finds both subjects the General Court files bills
     under, and clicking one opens the bill search on it.

     "Rather than 'See all 19 bills with this number' I'd rather it be a more
     general 'See all search results for (term)'", with "No matching
     results." where nothing is found, and "Did you mean firearms?" when what
     was typed is one or two letters away from something that exists.

     "an x icon that's faint but allows you to clear the field". Built here
     rather than left to the browser's own: Firefox draws none at all, and
     the one Chrome draws cannot be made faint.

   The control is built here rather than in the two files that write the
   header, so there is one of it. */
const FIND={rows:null,loading:null,words:null};
/* THE PAGE'S WORDS (i18n.py): components.js's tr(), which every page loads
   before this file. Where it is not there -- a harness that runs this file
   alone -- the English, with {name} filled. */
if(typeof tr!=="function")var tr=function(k,en,v){return v?String(en).replace(/\{([a-z_][a-z0-9_]*)\}/g,
  function(m,n){return Object.prototype.hasOwnProperty.call(v,n)?v[n]:m;}):en;};
/* THE BOXES THE FINDER DRAWS INTO. The header's panel by default; the home
   page's own box passes its own (D13, 8 October 2026: "one search box like
   the header search ... with a dropdown of the top results"), so one matcher
   and one set of rows serve both. */
const FIND_IDS={out:"findout",box:"findq",clear:"findclear",say:"findsay"};
const FKIND={legislator:tr("find.kind.legislator","Legislator"),committee:tr("find.kind.committee","Committee"),
  town:tr("find.kind.town","Town"),page:tr("find.kind.page","Page"),
  former:tr("find.kind.former","Former Member"),topic:tr("find.kind.topic","Subject"),
  // The how-to guides and the Learn pages, from their own pages (12 October 2026).
  // A GUIDE IS A "Guide" (17 October 2026): the kind of thing it is in one
  // word, as "Town" and "Subject" are; the hub's tab keeps its full name.
  guide:tr("find.kind.guide","Guide"),learn:tr("find.kind.learn","Learn")};
const _fesc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>(
  {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
/* A COMMITTEE IS NAMED WITH ITS CHAMBER (the person, 16 October 2026:
   "Committees in the search should show as House Housing Committee or Senate
   Judiciary Committee rather than just Housing so they aren't confused with a
   topic"). find.json keeps the committee's own name, and the matcher reads
   that -- so "house" does not bring every House committee to the top -- and
   this is what a row shows: the chamber from the row's line, and "Committee"
   where the name does not already say it. "Special Committee on Housing" is
   "House Special Committee on Housing"; "Senate Special Committee on
   Redistricting" already names both and stays as it is. */
function findName(r){
  if(!r||r[0]!=="committee")return r?r[1]:"";
  const name=String(r[1]||""), ch=(/^(House|Senate)\b/.exec(String(r[2]||""))||[])[1]||"";
  const named=/\bcommittee\b/i.test(name)?name:`${name} Committee`;
  return !ch||name.startsWith(ch+" ")?named:`${ch} ${named}`;
}
/* A COMMITTEE THAT NO LONGER SITS (the person, 16 October 2026: "some
   indicator of former committees that are no longer meeting like the special
   committee on housing that turned into the standing committee ... so those
   aren't prioritized in the search results"). find.json gives such a row the
   year it last sat in r[5], as a former member's has, and its years in r[6].
   It is a "Former Committee", in the words "Former Member" is, its line says
   what its own page says -- not on the General Court's list today, and when
   it sat -- and it falls in behind the committees that sit, as a member who
   has left falls in behind those who have not, and never above the bills. */
const _fgone=r=>!!r&&(r[0]==="former"||_fstudy(r)||(r[0]==="committee"&&!!r[5]));
function findKind(r){
  return r&&r[0]==="committee"&&r[5]?tr("find.kind.former_committee","Former Committee")
    :(FKIND[r&&r[0]]||(r&&r[0])||"");
}
/* STATUTORY AND STUDY COMMITTEES (18 October 2026: the person, 17 October,
   "they should be included on the committee page and in search results, but
   not as prominently as standing committees and other results"). find.json
   gives each its own kind, the General Court's class -- "statutory" or
   "study" -- and its line says what it is ("Commission, set up in 2019").
   They wait their turn as a former committee does (_fgone): never above the
   bills, and after the standing committees where the match is as good,
   though before the members and committees that have gone (findMatch). */
FKIND.statutory=tr("find.kind.statutory","Statutory Committee");
FKIND.study=tr("find.kind.study","Study Committee");
const _fstudy=r=>!!r&&(r[0]==="statutory"||r[0]==="study");
/* FORMERLY, WHEN AN OLD NAME IS WHAT MATCHED (the person, 16 October 2026: "A
   committee should say formerly if it's an old name"). A committee's earlier
   names are search words, so "housing" finds Criminal Justice and Public
   Safety, which was State Institutions and Housing; a row that then said only
   its name looked like a wrong answer. r[7] is the list of earlier names
   (find.json); the one every word typed is in is named, and only where the
   committee's own name does not hold them all. */
function _fwasNamed(r,s){
  const old=Array.isArray(r&&r[7])?r[7]:[];
  const words=s?_fwords(s):[];
  if(!old.length||!words.length)return "";
  if(words.every(w=>_fhas(String(r[1]||"").toLowerCase(),w)))return "";
  return old.find(n=>words.every(w=>_fhas(String(n).toLowerCase(),w)))||"";
}
// The line under a row -- but not "House committee" under a name that now says
// it. A committee that no longer sits says so in the person's own words for it
// ("former committees that are no longer meeting"), with its years; one found
// by an old name says which.
function findWhat(r,s){
  const w=r?String(r[2]||""):"";
  if(!r||r[0]!=="committee")return w;
  const was=_fwasNamed(r,s);
  const bits=[was?tr("find.formerly","Formerly {name}",{name:was}):"",
    r[5]?tr("find.no_longer","No longer meets")+(r[6]?` · ${r[6]}`:""):""].filter(Boolean);
  return bits.length?bits.join("; "):/^(House|Senate) committee$/i.test(w)?"":w;
}
/* HALF AN EMOJI IS NOT AN ADDRESS. encodeURIComponent throws "URI malformed"
   on a surrogate with no partner, which is what the box holds for a moment
   while some keyboards type an emoji and what a paste cut in the wrong place
   leaves: the panel stopped drawing for that keystroke, on every page, and
   so did /search (2 October). What is typed goes into an address through
   this, which reads the stray half as the replacement character -- under
   the u flag the class matches a surrogate only where it stands alone.
   /search and the home page's box use it too. */
const _fwell=s=>String(s==null?"":s).replace(/[\uD800-\uDFFF]/gu,"\uFFFD");
const _fenc=s=>encodeURIComponent(_fwell(s));

function findRows(){
  if(FIND.rows)return Promise.resolve(FIND.rows);
  if(!FIND.loading)FIND.loading=fetch(new URL("find.json",location.origin+"/").href)
    .then(r=>r.json()).then(rows=>(FIND.rows=rows)).catch(()=>(FIND.rows=[]));
  return FIND.loading;
}

/* WHAT THE GENERAL COURT NUMBERS, counted off the record rather than guessed
   at: the 33,683 bills on this site carry seventeen distinct prefixes and no
   others. HB 23,190; SB 8,616; HR 562; CACR 545; HCR 350; SR 147; HJR 117;
   SCR 68; PET 28; SJR 25; HBI 14; HA 9; HCO 2; and the four special-session
   forms SSHB, SSSB, SSHR and SSHCR, ten between them. A closed set, and the
   thing that makes findBill able to answer at all without an index. */
const FBILLKIND=new Set(["HB","SB","CACR","HCR","SCR","HJR","SJR","HR","SR",
  "PET","HBI","HA","HCO","SSHB","SSSB","SSHR","SSHCR"]);

/* A SEAT IS NOT A BILL. Two to five letters and a number is also the shape of
   every district on the roster -- "Hills 29", "Rock 8", "Straf 14", "SD22" --
   and the shape alone was the whole test, so all 223 district labels the
   sitting members carry were offered as "open this bill number in the bill
   search", drawn ABOVE the three representatives who actually sit for Hills
   29. Return takes the first answer, so a reader who typed their own district
   and pressed it landed on "No bills match in the 2025-2026 term." The same
   went for a ward: "Ward 3" read as bill WARD 3.
   The letters are what tell them apart, and the letters are in the data. Not
   one of the seventeen bill prefixes is a county abbreviation -- Belk, Carr,
   Ches, Coos, Graf, Hills, Merr, Rock, Straf, Sull -- or the Senate's SD, and
   not one county abbreviation is a bill prefix, so the set separates them
   cleanly with nothing left over.
   A number whose prefix is NOT in the set is not a dead end: the panel still
   offers "search every bill for these words" with what was typed, and the
   bill search's own billNumbers() reads any two-to-five letters and digits as
   a number. So a kind the General Court invents tomorrow still arrives at the
   bill, it just is not promoted to the top of this list before it exists.

   A bill number typed in any of the ways people write one: hb115, HB 115,
   "hb 0115". Offered without looking anything up, and handed to the bill
   search, which knows which term is on screen. */
function findBill(q){
  const m=/^\s*([a-z]{2,5})\s*0*(\d{1,4})\s*$/i.exec(q||"");
  if(!m)return "";
  const kind=m[1].toUpperCase();
  return FBILLKIND.has(kind)?`${kind} ${m[2]}`:"";
}
/* A BILL NUMBER OPENS THE BILL (the person, 12 October 2026: "typing a bill
   number in the searchbar will pull up the bill number from this term that
   matches like the legislators do when you type their name rather than first
   taking you to the general page"). The bill of this term with the number
   typed is the first row, so Return opens its page, and the numbers that
   start with it follow as the reader types -- "HB 14" offers HB 14, then
   HB 140 to HB 149 and on -- the way a name is offered from its first
   letters. It reads the current term's index, which a number used to cost
   nothing; a number this term does not have is answered by the rows below
   it, as before. */
function findBillNumber(num,limit){
  if(!FBILLS.rows)return {state:FBILLS.failed?"failed":"loading"};
  const id=String(num||"").replace(/\s+/g,"").toUpperCase();
  const exact=[],starts=[];
  for(const b of FBILLS.rows){
    const bid=String(b.id).toUpperCase();
    if(bid===id)exact.push(b);
    else if(bid.startsWith(id)&&/^\d/.test(bid.slice(id.length)))starts.push(b);
  }
  const n=b=>parseInt(String(b.id).replace(/^\D+/,""),10)||0;
  starts.sort((x,y)=>n(x)-n(y));
  return {state:"ready",top:exact.concat(starts).slice(0,limit==null?5:limit)};
}

// A former member's row is named "Former Rep. Suzanne Vail", and the word
// Former is ours, not part of her name. Ranking against the whole string
// would put all 1,785 of them at the top the moment somebody typed "for",
// and would stop "vail" from being a name that STARTS with what was typed.
const _fbare=s=>String(s||"").replace(/^Former /,"");

// A name that starts with what was typed first, then one with a word
// starting with it -- "Litchfield" puts the town and Rep. Litchfield above
// anyone whose town or committee merely mentions it -- then the rest. `s` is
// the query lowercased and trimmed; `edge` is _fedge(s).
const _fedge=s=>new RegExp("\\b"+s.replace(/[.*+?^${}()|[\]\\]/g,"\\$&"));
function _frank(r,s,edge){
  const name=_fbare(r[1]).toLowerCase();
  return name.startsWith(s)?0:edge.test(name)?1:2;
}

/* A NAME GOES ABOVE THE BILLS ONLY ON A WHOLE WORD (the person, 24
   September: "Should a name like Rep. Bailey outrank bail bills only on a
   whole-word match?" -- "Yes"). A name that merely STARTED with what was
   typed was enough, so "bail" put Rep. Glenn Bailey above the term's bail
   bills, and Return opened his page for a reader who had asked about bail.
   Now a sitting member, committee, town or subject goes above the bills only
   when every word typed is a whole word of its name -- "bailey", "glenn
   bailey", "rep. bailey", "litchfield", "education" -- and part of a word
   ("bail", "litch") leaves the bills first with the name under them. This
   decides which side of the bills a name falls; among the names, the same
   test orders them (_fpart, below), and then _frank. A letter or digit in
   any alphabet belongs to its word, so "2" is not whole in "Straf 20", and
   "josé" is whole in José. */
// "senator" and "representative" are the words a row prints as "Sen." and
// "Rep." (A TITLE AS IT IS SAID, below): "senator carson" has every word of
// it a whole word of her name, and leads with her, as "sen. carson" does.
const _fwords=s=>String(s||"").toLowerCase().split(/\s+/)
  .map(w=>w.replace(/^[^\p{L}\p{N}]+|[^\p{L}\p{N}]+$/gu,""))
  .map(w=>w==="senator"?"sen":w==="representative"?"rep":w).filter(Boolean);
const _fisword=(name,w)=>new RegExp("(^|[^\\p{L}\\p{N}])"
  +w.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")+"(?![\\p{L}\\p{N}])","u").test(name);
/* A GUIDE'S NAME IS ITS TITLE AND ITS TASK (the person, 17 October 2026: "the
   how to guides should be incorporated into the search in some fashion").
   find.json gives a guide's row, after its title, the task in a reader's
   words and the plain words it declares (guides.WORDS: "register my car",
   "food stamps", "testify"), and these two tests read them as part of its
   name: so "renew my license" and "testify" are whole words of a guide and
   bring it above the bills and the Learn pages, which are found only by
   their titles and lines, while a bill number typed still opens the bill
   first (findDraw puts that bill above every row, and /search puts the
   bills first for a number). Its title alone is what a row shows and what
   _frank and the length order read. */
const _fnamed=r=>r&&r[0]==="guide"?`${_fbare(r[1])} ${r[4]||""}`:_fbare(r&&r[1]);
function _fwhole(r,s){
  const name=_fnamed(r).toLowerCase();
  const words=_fwords(s);
  return words.length>0&&words.every(w=>_fisword(name,w));
}

/* THE WORD ITSELF FIRST, AMONG THE NAMES TOO (the person, 25 September:
   "have direct word matches be at the top of the best match sorting"). What
   was typed also finds a name it only begins -- "gun" finds former Rep.
   Michael Gunski, "bail" Rep. Glenn Bailey -- and that stays, lower down:
   a name that has every word typed as a whole word of it, by _fwhole's test,
   comes first. So "hill" lists Hill, Sugar Hill and the members named Hill
   before Hillsborough and the Hills districts' members, and "sd2" the
   senator for SD2 before those for SD20 to SD24. A sitting member's name
   carries their seat, so "merr" lists the Merr districts' members before
   the town of Merrimack, as "hills 29" always has. This counts the words
   typed that are not a whole word of the name, and findMatch orders by it
   before anything else. */
function _fpart(r,s){
  let name=_fnamed(r).toLowerCase();
  // THE SEAT COUNTS ONLY WHEN A NUMBER IS TYPED. "(R - Merr 5)" made "merr"
  // a whole word of every Merrimack County representative, and forty of them
  // pushed the town of Merrimack out of the header's eight rows while a
  // reader was still typing its name; "hills", "ches" and "graf" did the same
  // to Hillsborough, Chester and Grafton. A district is asked for with its
  // number -- "hills 29", "sd2" -- so a query with a digit still reads the
  // seat, and one without reads the name alone.
  if(!/\d/.test(s))name=name.replace(/\s*\([^()]*\)\s*$/,"");
  return _fwords(s).filter(w=>!_fisword(name,w)).length;
}

/* A TITLE AS IT IS SAID (2 October). "senator carson" was answered "No
   matching results.": a member's row is named "Sen. Sharon Carson", and
   "senator" is not in it. The four ways a title is typed are read as the one
   way a row prints it, so "senator carson", "sen carson" and "sen. carson"
   are the same search; "representative" and "rep" likewise. Whole words
   only: "senate" and "representation" are left alone. */
const FTITLE={senator:"sen.",sen:"sen.",representative:"rep.",rep:"rep."};
const _ftitled=s=>s.split(/\s+/).map(w=>
  Object.prototype.hasOwnProperty.call(FTITLE,w)?FTITLE[w]:w).join(" ");

// `limit` is the panel's eight by default. /search passes Infinity: it is a
// page and not a dropdown, so it shows everything that matched -- which is the
// whole reason it exists.
/* A SHORT WORD IS THE START OF A WORD, NOT THE MIDDLE OF ONE (2 October).
   What was typed was looked for anywhere in a row, so "dwi" listed, under
   the bills about driving while intoxicated, the town of Sandwich and six
   members named Baldwin, Edwin, Hardwick and Goodwin. Under five letters a
   word must begin a word of the row -- "dwi" still finds Rep. Dwinell, whose
   name it starts. From five it may stand anywhere, as it did: "field" is
   Litchfield and "borough" Hillsborough. */
function _fhas(hay,w){
  if(w.length>=5)return hay.includes(w);
  for(let i=hay.indexOf(w);i>=0;i=hay.indexOf(w,i+1))
    if(!i||!/[\p{L}\p{N}]/u.test(hay[i-1]))return true;
  return false;
}
function findMatch(q,limit){
  const s=_ftitled((q||"").trim().toLowerCase());
  if(!s||!FIND.rows)return [];
  const words=s.split(/\s+/);
  const edge=_fedge(s);
  const hit=[];
  for(const r of FIND.rows){
    const hay=`${r[1]} ${r[2]} ${r[4]||""}`.toLowerCase();
    if(!words.every(w=>_fhas(hay,w)))continue;
    const name=_fbare(r[1]).toLowerCase();
    const rank=_frank(r,s,edge);
    // Match quality decides first -- the words typed as whole words of the
    // name (_fpart), then where in the name they fall (_frank) -- and only
    // then does a member who has left fall in behind one who has not: that
    // is what "prioritize ... current legislators before listing former
    // ones" means with a list this long. A former member whose name begins
    // with the query still outranks a town that merely mentions it, which is
    // the answer a reader wants.
    // And a committee that no longer sits falls in behind those that do; a
    // statutory or study committee falls in between (_fstudy).
    const gone=_fgone(r)?(_fstudy(r)?1:2):0;
    // Among former members, the most recent first. r[5] is the year they last
    // sat; negated so one sort direction serves both this and name length.
    // A LEARN PAGE AFTER A GUIDE AS GOOD (17 October 2026): of two rows that
    // match as well, the one that says how to do the thing comes before the
    // one that explains it, and a Learn page, a page about a subject, after
    // the members, towns and subjects that match as well.
    const learn=r[0]==="learn"?1:0;
    hit.push([_fpart(r,s),learn,rank,gone,gone?-(r[5]||0):0,name.length,r]);
  }
  hit.sort((a,b)=>a[0]-b[0]||a[1]-b[1]||a[2]-b[2]||a[3]-b[3]||a[4]-b[4]||a[5]-b[5]);
  return hit.slice(0,limit||8).map(x=>x[6]);
}

/* DID YOU MEAN. Only when nothing at all was found, because that is the only
   time it can help and the only time the cost is worth paying: the distance
   is measured against every distinct word in the index, which is a few
   thousand, and a keystroke that DOES find something never runs it.

   Bounded at two edits and abandoned early -- a row of the matrix whose best
   cell already exceeds the bound cannot come back under it -- so a long word
   costs almost nothing. Two edits rather than one because "firarms" is one
   deletion from "firearms" but "comittee" is two from "committee", and a
   reader who has mistyped twice needs the offer more, not less. */
function _fdist(a,b,max){
  if(Math.abs(a.length-b.length)>max)return max+1;
  let prev=Array.from({length:b.length+1},(_,i)=>i);
  for(let i=1;i<=a.length;i++){
    const cur=[i];
    let best=i;
    for(let j=1;j<=b.length;j++){
      const v=Math.min(prev[j]+1,cur[j-1]+1,
        prev[j-1]+(a.charCodeAt(i-1)===b.charCodeAt(j-1)?0:1));
      cur[j]=v;
      if(v<best)best=v;
    }
    if(best>max)return max+1;
    prev=cur;
  }
  return prev[b.length];
}

// Built once. "Former" and the titles are left out: they are our words on
// every one of 1,785 rows, so they would be offered for anything vaguely
// like them and mean nothing when followed.
const FSTOP=new Set(["former","rep.","sen.","rep","sen","house","senate",
  "county","ward","committee","the","and","for"]);
function findWords(){
  if(FIND.words)return FIND.words;
  const w=new Set();
  for(const r of (FIND.rows||[]))
    for(const t of String(r[1]).toLowerCase().split(/[^a-z0-9']+/))
      if(t.length>3&&!FSTOP.has(t))w.add(t);
  FIND.words=Array.from(w);
  return FIND.words;
}

function findSuggest(q){
  const s=(q||"").trim().toLowerCase();
  // One word, and long enough that a two-edit neighbourhood still means
  // something: at four letters nearly everything is two edits from
  // everything, and the offer would be noise.
  if(!/^[a-z][a-z'-]{4,}$/.test(s))return "";
  // Two letters apart only from seven: "comittee" is committee, and "ebike"
  // was offered "mike" (2 October) -- in a word of five or six, two letters
  // are a third of it, and what is that near is another word.
  const most=s.length>=7?2:1;
  let best="",dist=most+1;
  for(const w of findWords()){
    const d=_fdist(s,w,most);
    if(d<dist||(d===dist&&w.length<best.length)){best=w;dist=d;}
  }
  return dist<=most?best:"";
}

// ROOT-RELATIVE, ALWAYS. find.json's rows all carry a relative path, and
// this panel is mounted on every page -- including 404.html, which has no
// <base href="/"> because it is served from the root and never needed one. On
// a Pages 404 the address stays at the depth that was asked for, so
// "legislator/x" resolved under it and every answer in the panel was a dead
// link. Making the href root-relative here fixes it wherever the panel is
// mounted, rather than teaching one more page about <base>.
function _froot(h){
  h = String(h || "");
  return /^([a-z]+:|\/)/i.test(h) ? h : "/" + h;
}

// The part of a name a reader actually typed, marked. Escaped on both sides of
// the mark rather than escaping afterwards, so the tags we add are the only
// ones in the string. The first occurrence only: a second mark in one name
// reads as emphasis rather than as a match.
function _fmark(text,q){
  const t=String(text==null?"":text),s=(q||"").trim();
  if(!s)return _fesc(t);
  const i=t.toLowerCase().indexOf(s.toLowerCase());
  if(i<0)return _fesc(t);
  return _fesc(t.slice(0,i))+"<mark>"+_fesc(t.slice(i,i+s.length))+"</mark>"
    +_fesc(t.slice(i+s.length));
}

/* BILLS, IN THE SAME BOX (24 September). Until then this panel searched
   find.json alone, which has no bills in it on purpose -- so "firearms",
   "abortion", "property tax" and "housing" were answered "No matching
   results." while the bill search held 12 to 119 bills of this term for each
   of them; "guns" and Return opened a former representative named Gunski;
   and "voting" was offered "Did you mean zoning?". Its one road to the bills
   ran through /search, which said nothing matched before it offered them.
   The person had asked for this box to search "anything including
   legislators, committees, towns, and bills", and to "prioritize to the most
   recent bills and current legislators before listing former ones".

   So it searches the current term's bills as well, and counts them with the
   bill search's own matcher -- app.js's, which a page that does not run
   app.js loads as billmatch.js, cut out of app.js by build_pages.py -- so
   that "All 30 bills found for firearms" is the number /bills?q=firearms
   then shows. The term is the one /bills opens on: away from a bill's own
   page app.js's wantedTerm() takes the first of meta.json's terms, and so
   does this. That term's index is about 153 KB over the wire, and with what
   its bills' text is about (238 KB), the matcher and meta.json the first
   word typed costs 443 KB (measured 2 October; this said 135 KB, for the
   index alone). It is fetched the first time somebody types something that is not a bill number and kept
   for the rest of the visit; opening the box, or looking up HB 1442, costs
   nothing.

   When any of that fails the panel still offers the bill search for what
   was typed, without a count, and does not say whether anything matched --
   it cannot know.

   THE PANEL IS THIS TERM'S; /search IS EVERY TERM'S. The person, 24
   September, asked whether the header's search covering the current term
   only was right: "Yes for bills in the search preview, but all terms
   should show up in the full search results". So the panel stays as it is,
   and /search, which reads this file too, loads the other terms' indexes
   through findBillsLoadAll below. */
const FBILLS={rows:null,file:null,term:"",terms:[],api:null,loading:null,
  failed:false,redraw:false};
/* THE BILLS' OWN TEXT (1 October). The bill search reads each bill's topic,
   the drafters' analysis and its text as well as its title, from
   sidx/<term>.json (app.js, "THE BILLS' OWN WORDS"; build_search_index.py
   writes the files). The count here has to be the one /bills?q= then shows,
   so this fetches the same file for the same term and hands it to the same
   matcher, before the first count is shown. A file that cannot be had is not
   an error: that term's bills are counted by title and topic, as /bills
   counts them when its own fetch fails. */
function _ftext(term){
  const A=_fbillApi();
  if(!A||!A.indexAdd)return Promise.resolve(false);
  return _fjson("sidx/"+encodeURIComponent(term)+".json")
    .then(j=>A.indexAdd(term,j)).catch(()=>false);
}
// The haystacks exactly as app.js's ensureTerm() builds them: the title and
// the committees. NO SPONSOR (17 October 2026): a name typed here lists the
// legislator, never their bills (app.js, A NAME IS NOT WHAT A BILL IS ABOUT).
function _fprep(rows){
  const norm=s=>String(s||"").toLowerCase().replace(/-/g," ");
  return (Array.isArray(rows)?rows:[]).map(b=>{
    b.hayT=norm([b.id,b.n,b.title].join(" "));
    b.hayC=norm((b.committees||[b.committee||""]).join(" | "));
    return b;});
}
function _fbillApi(){
  // On bills.html and every record page, app.js is already loaded.
  if(typeof queryGroups==="function"&&typeof groupWeight==="function"
     &&typeof billNumbers==="function"&&typeof billKey==="function"
     &&typeof looseness==="function"&&typeof indexAdd==="function"
     &&typeof readShort==="function"&&typeof whyListed==="function"
     &&typeof spelling==="function"&&typeof wordsAdd==="function")
    return {queryGroups,groupWeight,billNumbers,billKey,looseness,indexAdd,
            readShort,whyListed,spelling,wordsAdd,
            knownWord:typeof knownWord==="function"?knownWord:null,
            matchScore:typeof matchScore==="function"?matchScore:null,
            titleShare:typeof titleShare==="function"?titleShare:null,
            statusCat:typeof statusCat==="function"?statusCat:null};
  return window.GR_BILLMATCH||null;
}
const _fdata=f=>new URL(f,location.origin+"/").href;
function _fjson(f){
  return fetch(_fdata(f)).then(r=>{
    if(!r.ok)throw new Error(`${f} returned ${r.status}`);
    return r.json();});
}
function _fscript(f){
  return new Promise((ok,no)=>{
    const s=document.createElement("script");
    s.src=_fdata(f);s.onload=ok;s.onerror=()=>no(new Error(`${f} did not load`));
    document.head.appendChild(s);
  });
}
function findBillsLoad(){
  if(FBILLS.rows||FBILLS.failed)return Promise.resolve(!!FBILLS.rows);
  if(!FBILLS.loading)FBILLS.loading=Promise.all([
    _fbillApi()?null:_fscript("billmatch.js"),
    _fjson("meta.json").then(m=>{
      FBILLS.terms=((m&&m.terms)||[]).slice();
      FBILLS.term=FBILLS.terms[0]||"";
      if(!FBILLS.term)throw new Error("meta.json names no term");
      return _fjson("idx/"+encodeURIComponent(FBILLS.term)+".json");
    })
  ]).then(([,rows])=>{
    const api=_fbillApi();
    if(!api||!Array.isArray(rows))throw new Error("no matcher, or no bills");
    // The file whole, for every term's count below, and the rows app.js's
    // inTermOf() keeps for this one.
    FBILLS.file=_fprep(rows);
    FBILLS.rows=FBILLS.file.filter(b=>!b.term||b.term===FBILLS.term);
    FBILLS.api=api;
    return _ftext(FBILLS.term).then(()=>true);
  }).catch(()=>{FBILLS.failed=true;return false;});
  return FBILLS.loading;
}

/* EVERY TERM'S BILLS, for /search only. The other eighteen indexes, about
   2.2 MB over the wire between them where the current term's is 135 KB, so
   the panel never asks for them: /search does, once a reader has searched
   for something, and after the current term, whose answer it shows first.
   With each goes that term's sidx file, what its bills' analyses and texts
   are about (build_search_index.py prints what they weigh).
   The rows are every file's, concatenated, as app.js's IDX holds them when
   /bills is opened on "All terms" -- so "All 412 bills" here is the count
   /bills?q=...&term=all then shows. If any term cannot be had, none of them
   is counted: a number short by a term is a wrong number, and /search falls
   back to the current term's, which it can stand behind. */
const FALL={rows:null,terms:[],loading:null,failed:false};
function findBillsLoadAll(){
  if(FALL.rows||FALL.failed)return Promise.resolve(!!FALL.rows);
  if(!FALL.loading)FALL.loading=findBillsLoad().then(ok=>{
    if(!ok)throw new Error("the current term did not load");
    return Promise.all(FBILLS.terms.filter(t=>t!==FBILLS.term).map(t=>
      Promise.all([_fjson("idx/"+encodeURIComponent(t)+".json"),_ftext(t)])
      .then(([rows])=>{
        if(!Array.isArray(rows))throw new Error(`idx/${t}.json holds no list`);
        return _fprep(rows);})));
  }).then(parts=>{
    FALL.rows=FBILLS.file.concat(...parts);
    FALL.terms=FBILLS.terms.slice();
    return true;
  }).catch(()=>{FALL.failed=true;return false;});
  return FALL.loading;
}

/* What /bills?q= lists for this, in the order it lists them: {state:"ready",
   n, term, top} once the index is here; {state:"loading"} or
   {state:"failed"} until then; and null for a search with nothing in it to
   match -- "?" on its own, which the bill search reads as every bill. The
   order is app.js's "best match" (its looseness, scoreOf and sortRows):
   every word of the search as a word of the title before the start of a
   longer one -- "bail" before "bailiffs" -- then the most of the search in
   the title, then the committee (never the sponsor, since 17 October 2026), the
   search's own words in order worth two more, and bill number within each.
   That second number is the matcher's own matchScore(), the one /bills
   orders by: this file added it up for itself until 2 October, a copy that
   could drift. A search for bill numbers is number order.

   `allTerms` counts every term's bills (findBillsLoadAll) where /bills
   would with ?term=all. A bill number is unique only within a term, so
   there the ties between terms go to the newer term -- app.js's sortRows
   breaks them the same way -- which puts this term's answer ahead of
   1995's.
   Among bills that match equally well, a bill still moving whose title has
   the search comes first, and after the newer term the most of the title
   that is the search (16 October 2026): the matcher's own titleShare() and
   statusCat(), in sortRows' order, so that "housing" opens here on the
   bills /bills opens on. A matcher from before them, still in a reader's
   cache, breaks the tie by number as it did. */
function findBills(q,limit,allTerms){
  const s=(q||"").trim();
  if(!s)return null;
  const src=allTerms?FALL:FBILLS;
  if(!src.rows)return {state:src.failed?"failed":"loading"};
  const A=FBILLS.api,ids=A.billNumbers(s);
  let gs=null,words="";
  if(!ids){
    gs=A.queryGroups(s);
    if(!gs.length)return null;
    // In a term where the search lists nothing, a two-letter word is read
    // as the start of one ("special ed"). app.js's groupsFor() does the
    // same, over the same bills.
    if(A.readShort)gs=A.readShort(gs,src.rows);
    words=gs.map(g=>g.word).join(" ");
  }
  const hit=[];
  for(const b of src.rows){
    let sc=0,loose=0;
    if(ids){if(!ids.includes(String(b.id).toUpperCase()))continue;}
    else if(A.matchScore){
      sc=A.matchScore(b,gs);
      if(!sc)continue;
      loose=A.looseness(b,gs);
    }
    else{
      // A matcher from before matchScore, still in a reader's cache.
      let every=true;
      for(const g of gs){const w=A.groupWeight(b,g);if(!w){every=false;break;}sc+=w;}
      if(!every)continue;
      if(gs.length>1&&b.hayT.includes(words))sc+=2;
      loose=A.looseness(b,gs);
    }
    // The title's share of the search, and 1 for a bill still moving whose
    // title has it: sortRows' `sh` and `live`.
    const share=gs&&A.titleShare?A.titleShare(b,gs):0;
    const live=share>0&&A.statusCat&&A.statusCat(b)==="In Progress"?1:0;
    hit.push([sc,A.billKey(b),b,loose,share,live]);
  }
  const newer=(x,y)=>{const a=String(x[2].term||""),b=String(y[2].term||"");
    return a<b?1:a>b?-1:0;};
  const num=(x,y)=>x[1][0]-y[1][0]||x[1][1]-y[1][1];
  hit.sort(ids?(x,y)=>num(x,y)||newer(x,y)
    :(x,y)=>x[3]-y[3]||y[0]-x[0]||y[5]-x[5]||newer(x,y)||y[4]-x[4]||num(x,y));
  const top=hit.slice(0,limit==null?3:limit).map(h=>h[2]);
  // Why each row shown is listed, where its title does not have the word.
  const why=new Map();
  if(gs&&A.whyListed)for(const b of top){const y=A.whyListed(b,gs);if(y)why.set(b,y);}
  return {state:"ready",n:hit.length,term:FBILLS.term,every:!!allTerms,
          terms:allTerms?FALL.terms:[FBILLS.term],numbers:!!ids,why,top};
}

/* A SEARCH THAT LISTS NO BILL, OFFERED AS THE WORD IT SOUNDS LIKE (app.js,
   A SEARCH THAT LISTS NOTHING). For a day the bills row read the word
   again by itself: a former member's surname opened with "All 2,052 bills
   found for houde ... showing house" above the member, and Return went
   there. Now nothing is counted under another word. Where no bill and no
   name matches, the "Did you mean" line the names already had offers the
   bills' word as well.

   What tells a misspelling from a word is sidx/words.json, every word the
   bills use. It is fetched the first time it is needed and not before:
   {state:"loading"} until it is here, with FWORDS.loading to wait on; null
   where there is nothing to offer, or the file cannot be had; else
   {q, n}, the search to offer and how many bills it lists. */
const FWORDS={state:"",loading:null,redraw:false};
function findBillSpelling(q,allTerms){
  const s=(q||"").trim(),src=allTerms?FALL:FBILLS,A=FBILLS.api;
  if(!s||!src.rows||!A||!A.spelling||A.billNumbers(s))return null;
  const sp=A.spelling(A.readShort(A.queryGroups(s),src.rows),src.rows);
  if(!sp||!sp.need)return sp;
  if(FWORDS.state==="failed")return null;
  if(!FWORDS.loading){
    FWORDS.state="loading";
    FWORDS.loading=_fjson("sidx/words.json")
      .then(j=>{FWORDS.state=A.wordsAdd(j)?"ready":"failed";})
      .catch(()=>{FWORDS.state="failed";});
  }
  return FWORDS.state==="loading"?{state:"loading"}:null;
}
// The words to offer for a search nothing matched: the bills', and a name's.
// The bills' first: it goes by sound, and for "medicade" it is Medicaid,
// where the nearest name is the subject Medicare, one letter away. `wait` is
// there while the bills' words are on their way: draw again after.
// The name is offered beside the bills' word only where it is as close to
// what was typed: "vacine" was offered "vaccine or marine", and "morgage"
// "mortgage or morgan" (2 October).
// AND NEVER FOR A WORD THE BILLS USE. A word some bill has used is no
// misspelling, which is the rule /bills and /search keep: the panel offered
// "debra" for "zebra" (HB 594 of 1999, on zebra mussels) and "marston" for
// "marathon" (the review of 2 October 2026). Asked once sidx/words.json is
// in; until then the name is offered as before.
function findOffers(q,allTerms){
  const words=[],sp=findBillSpelling(q,allTerms);
  const wait=sp&&sp.state==="loading"?FWORDS.loading:null;
  if(sp&&sp.q)words.push(sp.q);
  const did=findSuggest(q),s=(q||"").trim().toLowerCase(),A=FBILLS.api;
  const known=FWORDS.state==="ready"&&A&&A.knownWord&&A.knownWord(s);
  if(did&&!known&&!words.includes(did)
     &&(!words.length||_fdist(s,did,2)<=_fdist(s,words[0],2)))words.push(did);
  return {words,wait};
}

// One bill as a row: its number, and its title under it. A resolution's
// title can run past 600 characters, and a row is read at a glance. `dated`
// names the year as the bill's own page does -- "SB 412 (2000)" -- for a
// list that crosses terms, where the number alone names nineteen bills.
function findBillRow(b,q,dated,why){
  const y=String(b.year||String(b.term||"").slice(0,4));
  let t=String(b.title||"");
  const cut=t.length>160;
  if(cut)t=t.slice(0,157).replace(/\s+\S*$/,"");
  return `<a href="/bill/${encodeURIComponent(y)}/${encodeURIComponent(String(b.id).toLowerCase())}">
    <span class="fl1"><span class="fname">${_fesc(b.n||b.id)}${dated&&y?` (${_fesc(y)})`:""}</span>
    ${chip(tr("find.kind.bill","Bill"),"fkind")}</span>
    ${t?`<span class="fwhat">${_fmark(t,q)}${cut?"&hellip;":""}</span>`:""}
    ${why?`<span class="fwhy">${tr("find.listed","Listed for &mdash; {why}",{why:_fesc(why)})}</span>`:""}</a>`;
}

// "1989 to 2026", from the terms newest first.
function _fspan(terms){
  const a=String(terms[terms.length-1]||"").slice(0,4),b=String(terms[0]||"").slice(-4);
  return a&&b?tr("find.span","{from} to {to}",{from:a,to:b}):"";
}

// The row that opens the bill search on what was typed: "All N bills found
// for" it once they are counted, and a plain offer before then or when they
// could not be. `what` is a sentence about the bill search, for /search.
// Counted across every term, it opens the bill search on All terms.
// "Found for", not "that mention": the 19 bills listed for "lgbtq" do not
// mention it, and the sentence said they did (1 October).
function findBillsAll(B,q,what){
  const quoted=`&ldquo;${_fesc(q)}&rdquo;`;
  const ready=B&&B.state==="ready";
  const every=ready&&B.every;
  // "HB 1, SB 5" is a list of numbers, not words a bill mentions.
  const n=ready?B.n.toLocaleString(window.GR_LOCALE||"en-US"):"";
  const name=ready?(B.numbers
      ?(B.n===1?tr("find.one_numbered","1 bill numbered {q}",{q:quoted})
        :tr("find.n_numbered","All {n} bills numbered {q}",{n,q:quoted}))
      :(B.n===1?tr("find.one_found","1 bill found for {q}",{q:quoted})
        :tr("find.n_found","All {n} bills found for {q}",{n,q:quoted})))
    :tr("find.search_bills","Search the bills for {q}",{q:quoted});
  const where=every?tr("find.all_terms","In all {n} terms, {span}.",{n:B.terms.length,span:_fspan(B.terms)})
    :ready?tr("find.in_term","In the {term} term.",{term:_fesc(B.term)})
    :B&&B.state==="loading"?tr("find.counting","Counting this term&rsquo;s bills&hellip;"):"";
  const line=[where,what||(where?"":tr("find.in_search","In the bill search."))].filter(Boolean).join(" ");
  return `<a class="fbills" href="/bills?q=${_fenc(q)}${every?"&amp;term=all":""}">
    <span class="fl1"><span class="fname">${name}</span></span>
    <span class="fwhat">${line}</span></a>`;
}

function findDraw(q,ids){
  ids=ids||FIND_IDS;
  const out=document.getElementById(ids.out);
  if(!out)return;
  const s=(q||"").trim();
  const clr=ids.clear?document.getElementById(ids.clear):null;
  if(clr)clr.hidden=!s;
  if(!s){out.innerHTML=`<p class="fnote">${tr("find.type","Type a legislator, a committee, a town, a subject, a bill number or words from a bill&rsquo;s title.")}</p>`;
    findSay("",ids);return;}
  const num=findBill(s);
  const rows=findMatch(s);
  // THE ONE LINE THAT LEAVES THE PANEL, and it leads to two different places.
  // A bill number is a bill, so it goes to the bill search, which is the page
  // that answers it. Anything else goes to /search, which reads this same
  // index with the eight-row cap off -- it used to go to the bill search too,
  // so a reader who typed Concord was shown eight of its wards and then sent
  // to a search with no towns in it at all.
  //
  // A BILL NUMBER GETS BOTH (24 September). The bill search opens on this
  // term, so "SB 412" led to this term's SB 412 and nowhere else, and the
  // 2000 bill a reader may have meant was a term picker away. /search lists
  // the number in every term, so it is offered under the number.
  const every=`<a class="fall" data-every href="/search?q=${_fenc(s)}">
    <span class="fl1"><span class="fname">${tr("find.see_all","See all search results for {q}",{q:_fesc(s)})}</span></span>
    <span class="fwhat">${num?tr("find.every_term","this number in every term since 1989")
      :tr("find.every_match","every member, committee, town and subject that matches, and the bills of every term")
      }</span></a>`;
  const all=num?`<a class="fall" href="/bills?q=${encodeURIComponent(num)}">
    <span class="fl1"><span class="fname">${_fesc(num)}</span></span>
    <span class="fwhat">${tr("find.open_number","open this bill number in the bill search")}</span></a>`:every;
  const row=r=>`<a href="${_fesc(_froot(r[3]))}">
      <span class="fl1"><span class="fname">${_fmark(findName(r),s)}</span>
      ${chip(findKind(r),"fkind")}</span>
      ${findWhat(r,s)?`<span class="fwhat">${_fesc(findWhat(r,s))}</span>`:""}</a>`;
  // The bills, for anything that is not a bill number: the count and the
  // first three. Hidden once counted at none, because "All 0 bills" is not an
  // answer; shown uncounted while they are fetched, and redrawn when they
  // arrive with whatever is in the box by then.
  const B=num?null:findBills(s,3);
  const N=num?findBillNumber(num):null;
  if(((B&&B.state==="loading")||(N&&N.state==="loading"))&&!FBILLS.redraw){
    FBILLS.redraw=true;
    findBillsLoad().then(()=>{
      const box=document.getElementById(ids.box);
      if(box)findDraw(box.value,ids);});
  }
  const counted=B&&B.state==="ready";
  const bills=B&&(!counted||B.n)?findBillsAll(B,s)
    +(counted?B.top.map(b=>findBillRow(b,s,false,B.why.get(b))).join(""):""):"";
  // WHERE THE BILLS GO: after the sitting members, committees, towns and
  // subjects that have every word typed as a whole word of their name
  // (_fwhole), and ahead of everything else, which is every former member
  // and anything whose name only starts with it or only mentions it. So
  // "Litchfield" still leads with the town and Rep. Litchfield, while "guns"
  // leads with the bills and Gunski follows, and "bail" leads with the bail
  // bills and Rep. Bailey follows. Return takes the first row, so for a
  // subject word it opens the bill search on it.
  const named=rows.filter(r=>!_fgone(r)&&_fwhole(r,s));
  const list=named.map(row).join("")+bills
    +rows.filter(r=>!named.includes(r)).map(row).join("");
  // "No matching results." -- the person's words -- only when nothing here
  // and no bill matches; "Did you mean" only when no bill does either
  // ("voting" was offered "zoning" over 141 bills). Its guesses are a name
  // close to what was typed and, since 1 October, the word of the bills
  // that a misspelt one sounds like (findOffers). While the bills are being
  // counted, neither: it is not known.
  let tail="";
  if(!rows.length&&!num&&(!B||(counted&&!B.n)||B.state==="failed")){
    const none=!B||counted?tr("find.none","No matching results."):"";
    const offer=findOffers(s,false);
    if(offer.wait&&!FWORDS.redraw){
      FWORDS.redraw=true;
      offer.wait.then(()=>{
        const box=document.getElementById(ids.box);
        if(box)findDraw(box.value,ids);});
    }
    // data-find, not data-q: app.js reads data-q anywhere on the page as
    // "run this search in the bill list" (see the panel's click, below).
    const did=offer.words.map(d=>
      `<button type="button" class="fdym" data-find="${_fesc(d)}">${_fesc(d)}</button>`);
    if(none||did.length)tail=`<p class="fnote"${none?" data-none":""}>${none}${did.length
      ?`${none?" ":""}${tr("find.did_you_mean","Did you mean {words}?",{words:did.join(" "+tr("find.or","or")+" ")})}`:""}</p>`;
  }
  const own=N&&N.state==="ready"?N.top.map(b=>findBillRow(b,s,false)).join(""):"";
  out.innerHTML=num?own+all+list+every+tail:list+all+tail;
  findSay(out.innerHTML,ids);
}

// WHAT THE LIST NOW HOLDS, SAID. The answers are drawn as the reader types
// and nothing told a screen reader that they had come, or how many, or that
// there were none (the audit of 2 October 2026, S4: WCAG 4.1.3). One line
// the eye does not see, role="status", written each time the list is drawn:
// "7 results", or the list's own "No matching results." The row that leads
// to every result ("See all search results for ...") is a door and not a
// result, and is not counted; while the bills are still being counted and
// nothing else matches, nothing is said. Read off the markup just written,
// which is the list as the reader has it.
function findSay(html,ids){
  const say=document.getElementById((ids||FIND_IDS).say);
  if(!say)return;
  html=String(html||"");
  const n=(html.match(/<a\s/g)||[]).length-(/data-every|See all search results for/.test(html)?1:0);
  const text=n>0?(n===1?tr("find.one_result","1 result"):tr("find.n_results","{n} results",{n}))
    :/data-none|No matching results/.test(html)?tr("find.none","No matching results."):"";
  if(say.textContent!==text)say.textContent=text;
}

function findMount(){
  const bar=document.querySelector("nav.top .in");
  if(!bar||document.getElementById("findbtn"))return;
  const btn=document.createElement("button");
  btn.id="findbtn";btn.className="findbtn";btn.type="button";
  btn.setAttribute("aria-expanded","false");
  btn.setAttribute("aria-controls","findpanel");
  btn.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" '
    +'cy="11" r="7"/><path d="M16.5 16.5 21 21"/></svg><span>'+tr("search.go","Search")+'</span>';
  // BEFORE THE MENU BUTTON, NOT BEFORE THE THEMER. The theme control moved
  // inside .navdrop so that a phone can fold it behind the menu with the
  // sections; insertBefore requires its reference to be a CHILD of the node
  // it is called on, so reaching for #themer here threw and the search
  // button never mounted. The menu button is a direct child, and appending
  // is the right answer when it is absent.
  const after=document.getElementById("navmenu");
  if(after&&after.parentNode===bar)bar.insertBefore(btn,after);
  else bar.appendChild(btn);
  // The scrim is the phone's way out. The panel there is a sheet that leaves
  // the edge of the page showing, asked for in these words: "rather than
  // taking up the full screen, I was imagining something more like it taking
  // up a decent amount of the screen with the outer edge still showing the
  // page you were on and if you tap on it, it'll take you out of the search
  // menu." So the strip that is still showing is the control that closes it.
  // On a desktop the stylesheet never shows this.
  const scrim=document.createElement("div");
  scrim.className="findscrim";scrim.hidden=true;
  const panel=document.createElement("div");
  panel.id="findpanel";panel.className="findpanel";panel.hidden=true;
  // A search landmark with a name, the box tied to the list it fills, and
  // the one line that says what the list holds (findSay).
  panel.setAttribute("role","search");
  panel.setAttribute("aria-label",tr("find.label","Search the site"));
  panel.innerHTML=`<div class="findin">
    <div class="findgrab" aria-hidden="true"></div>
    <div class="findtop">
    <div class="findbox">
      <label class="sr" for="findq">${tr("find.box","Search for a legislator, committee, town, subject or bill")}</label>
      <input id="findq" type="search" autocomplete="off" aria-controls="findout" placeholder="${_fesc(tr("find.hint","Name, town, committee or bill"))}">
      <button type="button" class="findclear" id="findclear" hidden aria-label="${_fesc(tr("find.clear","Clear the search box"))}">&#10005;</button>
    </div>
    <button type="button" class="findcancel" id="findcancel">${tr("find.cancel","Cancel")}</button>
    </div>
    <p class="sr" id="findsay" role="status"></p>
    <div class="findout" id="findout"></div></div>`;
  const nav=document.querySelector("nav.top");
  nav.parentNode.insertBefore(scrim,nav.nextSibling);
  nav.parentNode.insertBefore(panel,scrim.nextSibling);
  const box=panel.querySelector("#findq");
  const clr=panel.querySelector("#findclear");
  const shut=()=>{
    panel.hidden=true;scrim.hidden=true;
    document.documentElement.classList.remove("findopen");
    btn.setAttribute("aria-expanded","false");
  };
  const open=()=>{
    panel.hidden=false;scrim.hidden=false;
    document.documentElement.classList.add("findopen");
    btn.setAttribute("aria-expanded","true");
    findDraw(box.value);box.focus();findRows().then(()=>findDraw(box.value));
  };
  btn.addEventListener("click",()=>{panel.hidden?open():shut();});
  box.addEventListener("input",()=>findDraw(box.value));
  // Clearing puts the reader back in the box with it empty, which is what
  // they are about to want; leaving focus on a button they just emptied
  // would mean a second click to type again.
  clr.addEventListener("click",()=>{box.value="";findDraw("");box.focus();});
  // The offer is a button rather than a link because it searches again here
  // rather than going anywhere.
  //
  // AND THE CLICK STOPS HERE (2 October). Choosing the offered word closed
  // the panel, and on the Calendar, a Learn article, a session day and a town
  // page it replaced the page with a list of bills under the page's own
  // title. Drawing the answer takes the button out of the document, and the
  // click then went on up to two listeners on the document: the one below,
  // which no longer found its target inside the panel and so shut it; and
  // app.js's, which read the button's data-q as "search the bill list for
  // this" and drew that list over whatever page it was. The button had been
  // the name matcher's since 18 September and did the same then; since 1
  // October it is also how every misspelt bill word is answered.
  document.getElementById("findpanel").addEventListener("click",e=>{
    const d=e.target.closest(".fdym");
    if(!d)return;
    e.stopPropagation();
    box.value=d.dataset.find||"";findDraw(box.value);box.focus();
  });
  box.addEventListener("keydown",e=>{
    if(e.key==="Escape"){shut();btn.focus();}
    // Return takes the first answer, which is what a reader who typed a name
    // and looked at the list is about to click -- and, for a word no name
    // starts with, the bill search on that word (see findDraw).
    if(e.key==="Enter"){const a=panel.querySelector(".findout a");if(a){e.preventDefault();location.href=a.href;}}
  });
  // A WAY OUT THAT IS NOT THE SCRIM. On a phone the sheet covers the page and
  // the only way back was to tap the dimmed strip above it or press Escape --
  // neither of which a thumb goes looking for. Shown only at sheet widths; on
  // a desktop the panel is a dropdown and the scrim is right beside it.
  const cancel=panel.querySelector("#findcancel");
  if(cancel)cancel.addEventListener("click",shut);
  scrim.addEventListener("click",shut);
  // Escape from a row of the panel, or its offer, puts the focus back on the
  // button that opened it, as Escape in the box does: shutting the panel
  // hides whatever had the focus, and it was left on nothing.
  document.addEventListener("keydown",e=>{
    if(e.key!=="Escape"||panel.hidden)return;
    const inside=panel.contains(document.activeElement);
    shut();
    if(inside)btn.focus();
  });
  document.addEventListener("click",e=>{
    if(!panel.hidden&&!panel.contains(e.target)&&e.target!==btn&&!btn.contains(e.target)
       &&e.target!==scrim)shut();
  });
  // LEAVING IT WITH THE KEYBOARD CLOSES IT. Tab past the last answer went on
  // into the page with the panel still open, and on a phone the panel is a
  // sheet over a scrim: the 13th Tab press on /learn/testifying landed on
  // "Cite this page", under the scrim, where the focused link could not be
  // seen (the audit of 2 October 2026, S3: WCAG 2.4.11). Only where focus has
  // gone somewhere else in the page: a press on the panel's own ground, or
  // the window losing focus, names no such place and closes nothing.
  panel.addEventListener("focusout",e=>{
    const to=e.relatedTarget;
    if(panel.hidden||!to||panel.contains(to)||to===btn||btn.contains(to))return;
    shut();
  });
}
/* THE SECTIONS, FOLDED BEHIND ONE BUTTON ON A PHONE.

   It lives here because this file already mounts into nav.top on every page,
   and a second script for one toggle would be a second thing to load and to
   keep in step with the markup.

   The panel is the SAME .navdrop the desktop lays out inline -- there is one
   copy of the sections in the document, not two -- so a reader on a phone and
   a reader on a desktop are looking at the same links, and a section added to
   one is added to both. */
function menuMount(){
  const nav=document.querySelector("nav.top");
  const btn=document.getElementById("navmenu");
  const drop=document.getElementById("navdrop");
  if(!nav||!btn||!drop)return;
  const shut=()=>{nav.classList.remove("open");btn.setAttribute("aria-expanded","false");};
  // INTO THE MENU. The panel comes before its button in the document, so
  // with focus left on the button the next Tab press went on into the page
  // and the sections were three Shift+Tab presses back, behind Search and the
  // theme control (the audit of 2 October 2026, S2: WCAG 2.4.3). Opening it
  // puts focus on its first link.
  const open=()=>{
    nav.classList.add("open");btn.setAttribute("aria-expanded","true");
    const first=drop.querySelector("a[href]");
    if(first)first.focus();
  };
  btn.addEventListener("click",()=>{
    nav.classList.contains("open")?shut():open();
  });
  // AND LEAVING IT CLOSES IT: focus that goes anywhere but the panel or its
  // button -- on into the page, or back to the site's name -- shuts the
  // panel, so it is not left open over a page the reader has moved on into.
  nav.addEventListener("focusout",e=>{
    const to=e.relatedTarget;
    if(!nav.classList.contains("open")||!to||drop.contains(to)||btn.contains(to))return;
    shut();
  });
  // Escape closes and returns the focus to the control that opened it, which
  // is where a keyboard reader expects to be left.
  document.addEventListener("keydown",e=>{
    if(e.key==="Escape"&&nav.classList.contains("open")){shut();btn.focus();}
  });
  document.addEventListener("click",e=>{
    if(nav.classList.contains("open")&&!drop.contains(e.target)&&!btn.contains(e.target))shut();
  });
  // Following a link inside the panel navigates away; closing first means the
  // panel is not left open behind a page that has already changed, which is
  // what a browser's back button would otherwise show.
  drop.addEventListener("click",e=>{if(e.target.closest("a"))shut();});
}

findMount();
menuMount();

// THE SKIP LINK TAKES THE KEYBOARD WITH IT. Its target -- #results on a record
// page, #main on the home page, About and the search page -- is a plain
// container, and a link to one moves where the next Tab starts but leaves the
// focus itself on <body>: no ring anywhere after Skip, on every page (the
// review of 2 October 2026). Here because this is the one script every page
// runs. The target is made focusable only when the link is used -- a
// container that can take focus takes it from every click inside it -- and
// focused whether or not the browser's own move to the fragment did. Its ring
// is suppressed in app.css, deliberately: it would be drawn round the page.
document.addEventListener("click",function(e){
  var s=e.target&&e.target.closest&&e.target.closest("a.skip");
  var id=s&&(s.getAttribute("href")||"").split("#")[1];
  var r=id&&document.getElementById(id);
  if(!r)return;
  if(!r.hasAttribute("tabindex"))r.setAttribute("tabindex","-1");
  setTimeout(function(){if(document.activeElement!==r)r.focus({preventScroll:true});},0);
},true);

// A LINK THAT LEAVES THE SITE OPENS A NEW TAB (8 October 2026, the person's
// D20: "outside links open in a new tab, generally"). At the moment of the
// click, so that it reaches every link a page draws -- the ones app.js writes
// after the page has loaded among them -- without each of the writers
// remembering, and here because this is the one script every page runs.
// app.css marks the same links, by the same test of the address, with the
// arrow and the words a screen reader says. A link that names its own target
// keeps it.
function leavesSite(a,here){
  return !!a&&/^https?:$/.test(a.protocol||"")&&!!a.host&&a.host!==here
    &&a.host!=="graniterecord.org";
}
document.addEventListener("click",function(e){
  var a=e.target&&e.target.closest&&e.target.closest("a[href]");
  if(!leavesSite(a,location.host)||a.getAttribute("target"))return;
  a.setAttribute("target","_blank");
  if(!/\bnoopener\b/.test(a.getAttribute("rel")||""))
    a.setAttribute("rel",((a.getAttribute("rel")||"")+" noopener").trim());
},true);

/* YOUR TOWN (the person, 12 October 2026: "select your town / ward in the
   top right of the website next to the light/dark icon and it will stay in
   your browser and carry over different pages and will highlight your
   legislators and district ... on how to vote it would pull up your polling
   location [and] town clerk and also show up on the learn pages").

   WHAT IS KEPT IS THE PLACE, NEVER THE ADDRESS. The browser keeps one slug --
   "concord-ward-4" -- under gr-town, and nothing is sent to this site. The
   address lookup ("Not sure what ward you're in? Input your address to
   confirm.") asks the US Census Bureau's geocoder, the one outside service
   this page talks to, straight from the reader's browser; the address is
   held in the box until the page is left and is written nowhere. The
   addresses suggested as it is typed (24 October 2026) are this site's own
   files, matched in the browser: this site is asked for the file of the
   street's first two letters, and the Census for the one address chosen or
   looked up, and for nothing while the reader types.

   EVERY FACT IS places.json's, which build_town_pages writes from the data
   the town's own page prints, so the header cannot name a different
   district, member or polling place from that page. Fetched the first time
   it is needed -- on a page with a town saved, or when the panel opens. */
const YT={key:"gr-town",data:null,loading:null};
function ytGet(){try{return localStorage.getItem(YT.key)||"";}catch(e){return "";}}
function ytSave(s){
  try{s?localStorage.setItem(YT.key,s):localStorage.removeItem(YT.key);}catch(e){}
  ytApply();
}
function ytLoad(){
  if(YT.data)return Promise.resolve(YT.data);
  return YT.loading||(YT.loading=fetch("/places.json").then(r=>{
    if(!r.ok)throw new Error(r.status);return r.json();
  }).then(d=>{
    YT.data=d;YT.by={};d.places.forEach(p=>{YT.by[p.s]=p;});return d;
  }).catch(e=>{YT.loading=null;throw e;}));
}
const _ynorm=s=>String(s||"").toLowerCase().normalize("NFKD")
  .replace(/[̀-ͯ]/g,"").replace(/[^a-z0-9]+/g," ").trim();
function ytPlace(){return YT.by&&YT.by[ytGet()]||null;}
// "Merrimack districts 18 and 29 (floterial)", in the words the town's page
// uses in its first line.
function ytDistricts(p){
  const h=p.h||[];
  const say=h.map(x=>`${x[0]} ${x[1]}${x[2]?" ("+tr("yt.floterial","floterial")+")":""}`);
  const bits=[];
  if(say.length)bits.push(tr("yt.state_house","State House {d}",{d:say.length>1
    ?say.slice(0,-1).join(", ")+" "+tr("yt.and","and")+" "+say[say.length-1]:say[0]}));
  if(p.sd)bits.push(tr("yt.senate_d","State Senate district {d}",{d:p.sd}));
  if(p.ec)bits.push(tr("yt.council_d","Executive Council district {d}",{d:p.ec}));
  if(p.cd)bits.push(tr("yt.us_house_d","US House district {d}",{d:p.cd}));
  return bits;
}
function ytPeople(p){
  const ppl=(YT.data&&YT.data.people)||{};
  return '<ul class="ytppl">'+(p.m||[]).map(s=>{
    const w=ppl[s]||[s,""];
    return `<li><span class="mchip p-${_fesc(w[1]||"X")}" translate="no"><a href="/legislator/${_fesc(s)}">${_fesc(w[0])}</a></span></li>`;
  }).join("")+"</ul>";
}
function ytVote(p){
  const out=[];
  if(p.poll)out.push(`<p class="ytpoll"><span class="ytlbl">${tr("yt.where_vote","Where you vote")}</span>${_fesc(p.poll)}${p.hours?`<span class="ythrs">${tr("yt.polls_open","Polls open {hours}",{hours:_fesc(p.hours)})}</span>`:""}</p>`);
  if(p.wards)out.push(`<p class="ytlbl">${tr("yt.by_ward","{town} votes in {n} places, by ward",{town:_fesc(p.t),n:p.wards.length})}</p><ul class="ytwards">`
    +p.wards.map(w=>`<li><b>${tr("yt.ward","Ward {n}",{n:_fesc(w[0])})}</b> ${_fesc(w[1])}${w[2]?` <span class="ythrs">${_fesc(w[2])}</span>`:""}</li>`).join("")+"</ul>");
  if(!p.poll&&!p.wards)out.push(`<p class="ytnote">${tr("yt.no_poll","The Secretary of State&rsquo;s list has no polling place recorded for {place}. The clerk is who to ask.",{place:_fesc(p.n)})}</p>`);
  if(p.clerk)out.push(`<p class="ytclerk"><span class="ytlbl">${p.c?tr("yt.city_clerk","City clerk"):tr("yt.town_clerk","Town clerk")}</span>${_fesc(p.clerk)}`
    +(p.phone?` &middot; <a href="tel:${_fesc(p.phone.replace(/[^0-9+]/g,""))}">${_fesc(p.phone)}</a>`:"")
    +(p.email?` &middot; <a href="mailto:${_fesc(p.email)}">${_fesc(p.email)}</a>`:"")+"</p>");
  if(p.when)out.push(`<p class="ytwhen">${_fesc(p.when)}</p>`);
  return out.join("");
}
// THE MEMBERS, MARKED WHEREVER THEY ARE LINKED: one stylesheet rule per
// member, so a chip app.js draws after this has run is marked as well.
function ytMark(p){
  let st=document.getElementById("ytstyle");
  if(!st){st=document.createElement("style");st.id="ytstyle";document.head.appendChild(st);}
  if(!p){st.textContent="";return;}
  const sel=(s,after)=>`a[href*="legislator/${s}."]${after},a[href$="legislator/${s}"]${after}`;
  const rep=(p.m||[]).filter(s=>!/-sd-\d+$/.test(s)),sen=(p.m||[]).filter(s=>/-sd-\d+$/.test(s));
  let css="";
  if(rep.length)css+=rep.map(s=>sel(s,"::after")).join(",")+'{content:'+JSON.stringify(tr("yt.your_rep","Your rep"))+'}';
  if(sen.length)css+=sen.map(s=>sel(s,"::after")).join(",")+'{content:'+JSON.stringify(tr("yt.your_senator","Your senator"))+'}';
  if(css)css+=(p.m||[]).map(s=>sel(s,"::after")).join(",")
    +"{display:inline-block;margin-left:.375rem;padding:0 .375rem;border-radius:999px;"
    +"font:600 .75rem/1.5 var(--sans);letter-spacing:.02em;text-transform:none;"
    +"text-decoration:none;background:var(--pine-soft);color:var(--pine);vertical-align:.08em}"
    +".ytpanel a::after,.yt a::after{content:none !important}"
    // On a town page the chip sits in a narrow cell beside the contact
    // column, and the tag ran out of the chip into it: it goes under the name.
    +(p.m||[]).map(s=>sel(s,"::after").split(",").map(x=>".offwho "+x).join(",")).join(",")
    +"{display:block;width:max-content;margin:.25rem 0 0}";
  st.textContent=css;
}
// THE LEARN PAGES' SLOTS: <div class="yt" data-yt="reps|vote|county|town">,
// written by the builders where an example from the reader's own town
// belongs. With no town saved, each offers the picker.
// THE MY TOWN TAB'S CARD (the person's choice A, 14 October 2026): with a
// town saved, the tab opens on who represents it -- each seat and who holds
// it -- and the search below it becomes "Look Up Another Town". With none,
// the card is not drawn and the tab is the search, as before.
function ytChip(name,party,href,out){
  const a=href?`<a href="${_fesc(href)}"${out?' target="_blank" rel="noopener"':""}>${_fesc(name)}</a>`:_fesc(name);
  return `<li><span class="mchip p-${_fesc(party||"X")}" translate="no">${a}</span></li>`;
}
/* WHO NOVEMBER'S ELECTION SENT, IN THE CARD (the person's decisions of 16
   October 2026): between the election and Organization Day a place's "e"
   names its races in places.json's "elect", and the State House and Senate
   seats draw them under the sitting members, with "Serving now" over those,
   in components.js's electBlock and electNow -- the town page's own block,
   with untilAttrs, handed no day so that the behaviour judges it by the
   reader's clock. The House seat can be two districts, a floterial over a
   town's own, so where it is each race says which. Outside those weeks
   there is no "e" and the card is what it was. */
function ytElect(p,chamber){
  const E=typeof electBlock==="function"&&YT.data&&YT.data.elect||null;
  const keys=E?(p.e||[]).filter(k=>k.charAt(0)===chamber&&E.races&&E.races[k]):[];
  if(!keys.length)return ["",""];
  const say=k=>{const x=(p.h||[]).find(h=>"H|"+h[0]+"|"+h[1]===k);
    return x?`${x[0]} ${x[1]}${x[2]?" ("+tr("yt.floterial","floterial")+")":""}`:k;};
  return [electNow(E.takes_office,null),
    electBlock(keys.map(k=>[keys.length>1?say(k):"",E.races[k]]),E.election,E.takes_office,null,
      typeof window!=="undefined"?window.GR_LANG:undefined)];
}
function ytSeats(p){
  // In the page's language (tr; the Your Town card in Spanish, 25 October
  // 2026), the people's, places' and districts' names as the record has them.
  const ppl=(YT.data&&YT.data.people)||{},off=(YT.data&&YT.data.offices)||{};
  const reps=(p.m||[]).filter(s=>!/-sd-\d+$/.test(s)),sens=(p.m||[]).filter(s=>/-sd-\d+$/.test(s));
  const who=list=>`<ul class="ytppl">${list.map(s=>{const w=ppl[s]||[s,""];return ytChip(w[0],w[1],"/legislator/"+s);}).join("")}</ul>`;
  const h=(p.h||[]).map(x=>`${x[0]} ${x[1]}${x[2]?" ("+tr("yt.floterial","floterial")+")":""}`);
  const seat=(office,where,body)=>`<div class="ytseat"><p class="ytoff">${office}<span>${_fesc(where)}</span></p>${body}</div>`;
  const named=(k,d)=>{const o=(off[k]||{})[String(d)];
    return o&&o[0]?`<ul class="ytppl">${ytChip(o[0],o[1],o[2],true)}</ul>`:`<p class="ytnote">${tr("yt.not_on_file","Not on file.")}</p>`;};
  const eh=ytElect(p,"H"),es=ytElect(p,"S");
  const district=d=>tr("yt.district","District {d}",{d});
  const seats=[];
  if(h.length)seats.push(seat(tr("yt.seat_house","State House"),h.length>1?h.slice(0,-1).join(", ")+" "+tr("yt.and","and")+" "+h[h.length-1]:h[0],
    eh[0]+(reps.length?who(reps):`<p class="ytnote">${tr("yt.no_member","No sitting member on file.")}</p>`)+eh[1]));
  if(p.sd)seats.push(seat(tr("yt.seat_senate","State Senate"),district(p.sd),
    es[0]+(sens.length?who(sens):`<p class="ytnote">${tr("yt.no_senator","No sitting senator on file.")}</p>`)+es[1]));
  if(p.ec)seats.push(seat(tr("yt.seat_council","Executive Council"),district(p.ec),named("ec",p.ec)));
  if(p.cd)seats.push(seat(tr("yt.seat_us_house","US House"),district(p.cd),named("cd",p.cd)));
  const sub=[p.co?tr("yt.county","{county} County",{county:p.co}):"",
    p.poll?tr("yt.votes_at","votes at {place}",{place:p.poll.split(/\s+\d/)[0]}):""].filter(Boolean).join(" \u00b7 ");
  return `<div class="ytstop"><div><p class="ythead2">${tr("yt.your_town","Your Town")}</p><p class="ytname">${_fesc(p.n)}</p>`
    +(sub?`<p class="ytsub">${_fesc(sub)}</p>`:"")+`</div><div class="ytacts">`
    +`<button type="button" class="ytopen">${tr("yt.change","Change town")}</button>`
    +`<a class="ytgo" href="${_fesc(p.u)}">${tr("yt.page_go","{place}&rsquo;s page &rarr;",{place:_fesc(p.n)})}</a></div></div>`
    +`<div class="ytgrid">${seats.join("")}</div>`;
}
function ytSlots(p){
  const fh=document.getElementById("of-find");
  if(fh)fh.textContent=p?tr("yt.look_another","Look Up Another Town"):tr("yt.find_town","Find Your Town");
  document.querySelectorAll(".yt[data-yt]").forEach(el=>{
    const k=el.dataset.yt;
    if(k==="seats"){
      if(!p){el.hidden=true;el.innerHTML="";return;}
      el.innerHTML=ytSeats(p);el.hidden=false;return;
    }
    // In the page's language (tr; the Learn pages in Spanish, 25 October
    // 2026), the place's and the people's names as the record has them.
    if(!p){
      el.innerHTML=`<p class="ythead2">${tr("yt.for_town","For your town")}</p><p>${tr("yt.choose_see","Choose your town or ward to see this for where you live.")}</p>`
        +`<button type="button" class="ytopen">${tr("yt.choose","Choose your town")}</button>`;
      el.hidden=false;return;
    }
    const link=`<a href="${_fesc(p.u)}">${tr("yt.page_of","{place}&rsquo;s page",{place:_fesc(p.n)})}</a>`;
    let body="";
    if(k==="reps")body=`<p>${tr("yt.reps_in","{place} is represented in {districts}.",{place:_fesc(p.n),districts:ytDistricts(p).map(_fesc).join("; ")})}</p>`
      +ytPeople(p)+`<p>${tr("yt.every_seat","Every seat, with how to reach each person, is on {link}.",{link})}</p>`;
    else if(k==="vote")body=ytVote(p)+`<p>${tr("yt.more_on","More on {link}.",{link})}</p>`;
    else if(k==="county")body=p.co?`<p>${tr("yt.county_conv","{place} is in {county} County, so its county convention is the State House members elected from {county} County &mdash; yours among them.",{place:_fesc(p.n),county:_fesc(p.co)})}</p>`
      +ytPeople({m:(p.m||[]).filter(s=>!/-sd-\d+$/.test(s))})
      +`<p>${tr("yt.county_officials","The county&rsquo;s own officials are under <a href=\"{href}\">County Officials</a>.",{href:((window.GR_HREFS||{})["officials.html"]||"/officials")+"#counties"})}</p>`:"";
    else if(k==="town")body=`<p>${p.c?tr("yt.is_city","{town} is a city. Who runs it is on the City Officials tab of {link}.",{town:_fesc(p.t),link}):tr("yt.is_town","{town} is a town. Who runs it is on the Town Officials tab of {link}.",{town:_fesc(p.t),link})}</p>`;
    if(!body){el.hidden=true;return;}
    el.innerHTML=`<p class="ythead2">${tr("yt.in_town","In your town: {place}",{place:_fesc(p.n)})}</p>`+body
      +`<p class="ytmeta"><button type="button" class="ytopen link">${tr("yt.change_town","Change your town")}</button></p>`;
    el.hidden=false;
  });
}
function ytApply(){
  const s=ytGet(),btn=document.getElementById("ytbtn");
  const done=()=>{
    const p=ytPlace();
    if(btn){
      const w=btn.querySelector(".ytword");
      const said=p?tr("yt.yours","Your town: {place}",{place:p.n}):tr("yt.choose","Choose your town");
      if(w)w.textContent=said;
      btn.setAttribute("aria-label",said);
      btn.title=said;
      btn.classList.toggle("is-set",!!p);
    }
    ytMark(p);ytSlots(p);
    const panel=document.getElementById("ytpanel");
    if(panel&&!panel.hidden)ytDraw();
    // The map on Officials goes to it (LEGFIND_JS's own event).
    if(p&&document.getElementById("ofmap"))
      dispatchEvent(new CustomEvent("grtown",{detail:p.t}));
  };
  if(s||document.querySelector(".yt[data-yt]"))
    ytLoad().then(done,()=>{ytMark(null);});
  else done();
}

/* THE ADDRESS, ASKED OF THE CENSUS BUREAU. Its geocoder answers a script tag
   (JSONP) and not a fetch -- it sends no CORS header -- with every layer the
   point falls in: the town (County Subdivisions) and the State House
   district (State Legislative Districts - Lower, "Merrimack 18"). A city
   ward is then the one ward of that town in that district. In 57 of the 61
   city districts that is one ward; where it is several, the reader is
   asked which, and told where their ward is written. It is asked when Look
   up is pressed or a suggested address chosen (ytLook), and never as the
   address is typed. */
function ytGeocode(addr){
  return new Promise((ok,no)=>{
    const cb="grgeo"+Date.now().toString(36);
    const sc=document.createElement("script");
    const t=setTimeout(()=>{end();no(new Error("timeout"));},20000);
    function end(){clearTimeout(t);try{delete window[cb];}catch(e){window[cb]=undefined;}sc.remove();}
    window[cb]=d=>{end();ok(d);};
    sc.onerror=()=>{end();no(new Error("load"));};
    if(!/\b(nh|new hampshire)\b/i.test(addr))addr+=", NH";
    sc.src="https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?address="
      +_fenc(addr)+"&benchmark=Public_AR_Current&vintage=Current_Current&layers=all"
      +"&format=jsonp&callback="+cb;
    document.head.appendChild(sc);
  });
}
function ytFromCensus(d){
  const m=d&&d.result&&(d.result.addressMatches||[])[0];
  if(!m)return {why:"none"};
  const g=m.geographies||{};
  const layer=re=>{const k=Object.keys(g).find(k=>re.test(k));return k&&g[k][0]||null;};
  const st=layer(/^States$/);
  if(st&&st.STUSAB&&st.STUSAB!=="NH")return {why:"state",addr:m.matchedAddress};
  const sub=layer(/^County Subdivisions$/),low=layer(/State Legislative Districts - Lower$/);
  const town=sub&&_ynorm(sub.BASENAME);
  const all=YT.data.places.filter(p=>_ynorm(p.t)===town);
  if(!all.length)return {why:"town",addr:m.matchedAddress,name:sub&&sub.BASENAME};
  if(all.length===1)return {pick:all[0],addr:m.matchedAddress};
  const dm=low&&/^(.*\S)\s+0*(\d+)$/.exec(low.BASENAME||"");
  const fit=dm?all.filter(p=>(p.h||[]).some(h=>!h[2]&&_ynorm(h[0])===_ynorm(dm[1])&&String(h[1])===dm[2])):[];
  if(fit.length===1)return {pick:fit[0],addr:m.matchedAddress};
  return {wards:fit.length?fit:all,addr:m.matchedAddress,town:all[0].t};
}

/* THE ADDRESS, SUGGESTED AS IT IS TYPED (the person, 24 October 2026: "I'd
   like to make some improvements to the address search so that it shows you
   a dropdown of matching addresses around New Hampshire as you're typing
   with the zip codes").

   FROM THIS SITE'S OWN FILES, MATCHED HERE. The Census geocoder has no
   type-ahead, and one from anybody else would send every key pressed to
   another outside service. So the list is New Hampshire's streets, read from
   the Census Bureau's TIGER/Line files (src/towns/parse_tiger_streets.py) and
   cut by build_addr_index.py into files named by the street's first two
   letters: typing "12 main st conc" asks this site for /addr/ma.json, once,
   and the rest is matched in the browser. Nothing typed goes anywhere until
   an address is chosen or Look up is pressed; then it goes to the Census, as
   before. The file's address is built here from two letters or digits and
   nothing else, so no other server is asked while the reader types
   (preflight's _addr_suggest holds that).

   WHAT IS OFFERED. Up to eight, as "12 Main St, Concord, NH 03301": the
   house number as typed, first where it falls in a range the Census has for
   that street and ZIP code -- its parity is what picks the ZIP where a street
   is a ZIP boundary -- and then, once each, streets whose ranges do not reach
   it, with the nearest range's ZIP. Without a house number, the streets
   alone; choosing one puts it in the box with the cursor in front of it,
   for the number, since the geocoder places a numbered address and nothing
   less ("N Main St, Concord, NH 03301" matches nothing; asked 24 October
   2026). Words after the street are its town ("main st conc"), then perhaps
   NH and the ZIP code. A tie goes to the row the file has first: the
   bigger town, and in it the longer street.

   THE TOWN IS THE MUNICIPALITY the Census puts that side of the street in,
   which is not always the post office's name for it: a Webster house on ZIP
   03303 is offered as Webster, and the geocoder takes it so.

   A COMBOBOX, WAI-ARIA's pattern with a listbox: the box says it controls
   the list and whether it is open; the arrow keys move through the options,
   aria-activedescendant naming the one they are on; Enter takes it; Escape
   closes the list and only the list; a status line says how many there are.
   Each option is 44px high, and the list is in the panel's flow, so a phone
   scrolls it with the panel.

   NOTHING DEPENDS ON IT. A file that does not load -- missing, the network
   down, a site built without the list -- is no suggestions, and the box and
   Look up work as they did before there were any. */
const YA={files:{},timer:0,most:8};
// What the Census's abbreviations stand for, for every word after the first:
// "12 n main street" finds N Main St. The first word's are the build's
// (build_addr_index.forms), because the first word is what names the file.
const YA_ALT={st:["street","saint"],rd:["road"],ave:["avenue","av"],dr:["drive"],ln:["lane"],
  cir:["circle"],ct:["court"],pl:["place"],ter:["terrace"],blvd:["boulevard"],
  tpke:["turnpike","tpk","pike"],hwy:["highway"],trl:["trail"],pkwy:["parkway"],sq:["square"],
  hts:["heights"],lndg:["landing"],xing:["crossing"],pt:["point"],rdg:["ridge"],vw:["view"],
  ests:["estates"],byp:["bypass"],rte:["route","rt"],mt:["mount"],mtn:["mountain"],ft:["fort"],
  exd:["extended","ext"],exn:["extension","ext"],ext:["extension"],
  n:["north"],s:["south"],e:["east"],w:["west"],
  ne:["northeast"],nw:["northwest"],se:["southeast"],sw:["southwest"]};
// build_addr_index.norm, the same: lower case, no accents or apostrophes, and
// anything not a letter or digit a space.
const yaNorm=s=>String(s||"").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g,"")
  .replace(/['\u2019]/g,"").replace(/[^a-z0-9]+/g," ").trim();
// The file a street is in: its first two letters or digits, spaces left out.
const yaKey=s=>{const k=String(s).replace(/ /g,"").slice(0,2);return /^[a-z0-9]{2}$/.test(k)?k:"";};
// "12 main st conc": the number as typed and as a number (none for
// "264-98"), the words after it, and the file they are in.
function yaQuery(raw){
  raw=String(raw||"");
  if(/^\s*\d+[a-z]?\s*$/i.test(raw))return null;
  const m=/^\s*(\d+[a-z]?(?:[-\/]\d+[a-z]?)?)(?:\s*,\s*|\s+)(.*)$/i.exec(raw);
  const num=m?m[1]:"",words=yaNorm(m?m[2]:raw);
  if(!words)return null;
  return {num,n:/^\d+[a-z]?$/i.test(num)?parseInt(num,10):null,t:words.split(" "),
    key:yaKey(words),chars:words.replace(/ /g,"").length};
}
// A word typed against a word of a name: the word or what it abbreviates,
// whole (2) or begun (1); 0 where it is neither.
function yaWord(q,w){
  const alt=YA_ALT[w]||[];
  if(q===w||alt.indexOf(q)>=0)return 2;
  return w.startsWith(q)||alt.some(a=>a.startsWith(q))?1:0;
}
// How the words typed fit a form of a street, then its town, then NH and
// the ZIP code: {s: how well, left: the street's words not typed}, or null.
function yaFit(qt,form,town,zip){
  const ft=form.split(" ");
  let i=0,j=0,s=0;
  while(i<qt.length&&j<ft.length){const k=yaWord(qt[i],ft[j]);if(!k)break;s+=k;i++;j++;}
  if(!i)return null;
  const tt=yaNorm(town).split(" ");
  for(let k=0;i<qt.length&&k<tt.length;k++,i++)if(!yaWord(qt[i],tt[k]))break;
  for(;i<qt.length;i++){
    const q=qt[i];
    if(/^\d+$/.test(q)?!zip.startsWith(q):!["nh","new","hampshire"].some(w=>w.startsWith(q)))return null;
  }
  return {s,left:ft.length-j};
}
// The suggestions a file holds for a query, best first.
function yaSuggest(file,q,most){
  const out=[],towns=(file&&file.t)||[];
  ((file&&file.r)||[]).forEach((r,ord)=>{
    const town=towns[r[1]];
    if(typeof town!=="string"||typeof r[0]!=="string")return;
    let best=null;
    [yaNorm(r[0])].concat(r[4]||[]).forEach((f,fi)=>{
      if(yaKey(f)!==q.key)return;
      const m=yaFit(q.t,f,town,r[2]||"");
      if(m&&(!best||m.s>best.s||m.s===best.s&&m.left<best.left))best={s:m.s,left:m.left,alt:fi?1:0};
    });
    if(!best)return;
    const runs=Array.isArray(r[3])?r[3]:[];
    let gap=Infinity;
    if(q.n!=null)for(let i=0;i+1<runs.length;i+=2){
      const lo=runs[i],hi=runs[i+1],d=q.n<lo?lo-q.n:q.n>hi?q.n-hi:(q.n-lo)%2?1:0;
      if(d<gap)gap=d;
    }
    out.push({name:r[0],town,zip:r[2]||"",s:best.s,alt:best.alt,ord,gap,in:gap===0?1:0});
  });
  let keep=out;
  if(q.n!=null){
    // A street in a town once, unless the number is in range for more than
    // one of its ZIP codes; where it is in range for none, the nearest.
    const by={};keep=[];
    out.forEach(c=>{(by[c.name+"|"+c.town]=by[c.name+"|"+c.town]||[]).push(c);});
    Object.keys(by).forEach(k=>{
      const cs=by[k],hit=cs.filter(c=>c.in);
      if(hit.length)keep.push(...hit);else keep.push(cs.reduce((a,b)=>b.gap<a.gap?b:a));
    });
  }
  keep.sort((a,b)=>(b.in-a.in)||(b.s-a.s)||(a.alt-b.alt)||(a.ord-b.ord));
  return keep.slice(0,most).map(c=>({label:(q.num?q.num+" ":"")+c.name+", "+c.town+", NH"+(c.zip?" "+c.zip:""),
    num:q.num,name:c.name,town:c.town,zip:c.zip,inRange:!!c.in}));
}
// One file, fetched once a page, from this site and nowhere else; anything
// but a file of rows is no file.
function yaFile(k){
  if(!/^[a-z0-9]{2}$/.test(k))return Promise.resolve(null);
  if(!YA.files[k])YA.files[k]=fetch("/addr/"+k+".json").then(r=>r.ok?r.json():null)
    .then(d=>d&&Array.isArray(d.r)&&Array.isArray(d.t)?d:null,()=>null);
  return YA.files[k];
}
// The box, its list and its status line made a combobox; pick(choice) is
// told what was chosen.
function yaCombo(inp,list,say,pick){
  const lid=list.id||"ytalist";
  let rows=[],act=-1,seq=0;
  const draw=()=>{
    list.innerHTML=rows.map((r,i)=>`<li role="option" class="ytaopt" id="${lid}-${i}" data-i="${i}" aria-selected="${i===act}">${_fesc(r.label)}</li>`).join("");
    list.hidden=!rows.length;
    inp.setAttribute("aria-expanded",rows.length?"true":"false");
    if(act>=0){inp.setAttribute("aria-activedescendant",`${lid}-${act}`);
      const o=document.getElementById(`${lid}-${act}`);if(o&&o.scrollIntoView)o.scrollIntoView({block:"nearest"});}
    else inp.removeAttribute("aria-activedescendant");
  };
  const shut=()=>{seq++;say.textContent="";if(rows.length||act>=0){rows=[];act=-1;draw();}};
  const update=()=>{
    const q=yaQuery(inp.value),my=++seq;
    if(!q||!q.key){rows=[];act=-1;draw();say.textContent="";return;}
    yaFile(q.key).then(d=>{
      if(my!==seq)return;
      rows=d&&q.chars>=3?yaSuggest(d,q,YA.most):[];act=-1;draw();
      say.textContent=!rows.length?"":rows.length===1?tr("yt.sugg_one","1 address suggested")
        :tr("yt.sugg_n","{n} addresses suggested",{n:rows.length});
    });
  };
  const choose=i=>{
    const r=rows[i];if(!r)return;
    inp.value=r.label;shut();pick(r);
  };
  inp.addEventListener("input",()=>{clearTimeout(YA.timer);YA.timer=setTimeout(update,120);});
  inp.addEventListener("keydown",e=>{
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){
      e.preventDefault();
      if(!rows.length){update();return;}
      act=e.key==="ArrowDown"?(act+1)%rows.length:act<=0?rows.length-1:act-1;
      draw();
    }else if(e.key==="Enter"){
      if(rows.length&&act>=0){e.preventDefault();choose(act);}else shut();
    }else if(e.key==="Escape"){
      // The list, and not the panel round it, whose own Escape is the document's.
      if(rows.length){e.preventDefault();e.stopPropagation();shut();}
    }else if(e.key==="Tab")shut();
  });
  inp.addEventListener("blur",shut);
  // Pressing an option keeps the focus in the box, so the box is not left
  // (and the list shut) before the click has landed.
  list.addEventListener("mousedown",e=>e.preventDefault());
  // And the click goes no further: choosing redraws the list, so the option
  // pressed has left the page by the time the click reaches the document,
  // whose handler takes a click on nothing in the panel as one outside it
  // and shuts the panel (the browser test found it, 24 October 2026).
  list.addEventListener("click",e=>{
    const o=e.target&&e.target.closest&&e.target.closest("[data-i]");
    if(!o)return;
    e.stopPropagation();choose(+o.getAttribute("data-i"));
  });
}

function ytRows(q){
  const n=_ynorm(q);if(!n||!YT.data)return [];
  const ps=YT.data.places;
  const starts=ps.filter(p=>_ynorm(p.n).startsWith(n));
  const has=ps.filter(p=>!_ynorm(p.n).startsWith(n)&&(" "+_ynorm(p.n)).includes(" "+n));
  return starts.concat(has).slice(0,12);
}
function ytDraw(){
  const panel=document.getElementById("ytpanel");if(!panel)return;
  const out=panel.querySelector("#ytbody");
  const p=ytPlace();
  const here=(location.pathname.match(/^\/town\/([a-z0-9-]+?)(?:\.html)?$/)||[])[1];
  const herep=here&&YT.by&&YT.by[here];
  let h="";
  if(p&&!panel.dataset.changing){
    h+=`<div class="ytnow"><p class="ytplace"><a href="${_fesc(p.u)}">${_fesc(p.n)}</a></p>`
      +`<p class="ytdist">${p.co?_fesc(p.co)+" County. ":""}${ytDistricts(p).map(_fesc).join(" &middot; ")}</p>`
      +`<h3 class="ytsub">${tr("yt.legislators","Your state legislators")}</h3>`+ytPeople(p)
      +`<h3 class="ytsub">${tr("yt.voting","Voting")}</h3>`+ytVote(p)
      +'<p class="ytacts"><button type="button" class="ytbtn2" id="ytchange">'+tr("yt.change","Change town")+'</button>'
      +'<button type="button" class="ytbtn2 ytquiet" id="ytforget">'+tr("yt.forget","Forget it")+'</button></p></div>';
  }else{
    h+=(herep&&herep.s!==ytGet()?`<p class="ytthis"><button type="button" class="ytbtn2" data-pick="${_fesc(herep.s)}">${tr("yt.use_this","Use {place}, this page&rsquo;s town",{place:_fesc(herep.n)})}</button></p>`:"")
      +'<div class="findbox"><label for="ytq" class="ytlbl2">'+tr("yt.box","Your town, or your city and ward")+'</label>'
      +'<input id="ytq" type="search" autocomplete="off" placeholder="'+_fesc(tr("yt.box_hint","Town, or city and ward"))+'" aria-controls="ytout"></div>'
      +'<p class="sr" id="ytqsay" role="status"></p><div class="ytout" id="ytout"></div>'
      +'<details class="ytaddr" id="ytaddrbox"><summary>'+tr("yt.ward_unsure","Not sure what ward you&rsquo;re in? Enter your address to confirm.")+'</summary>'
      // The browser offers the reader's saved address here (the owner, 24
      // October 2026: "it's fine to enable address autofill if it's saved in
      // their browser when they click on it"). The combobox pattern would
      // keep it off, since its list can open over this one for a moment; what
      // it fills is matched as if typed, and a street filled without its
      // town (street-address is the street alone) is offered in each town
      // that has it.
      +'<form id="ytaform" class="ytaform"><label for="ytaddr" class="ytlbl2">'+tr("yt.addr","Street address and town")+'</label>'
      +'<div class="ytarow"><input id="ytaddr" name="street-address" type="text" autocomplete="street-address" placeholder="'+_fesc(tr("yt.addr_hint","12 Main Street, Concord"))+'"'
      +' role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="ytalist">'
      +'<button type="submit" class="ytbtn2">'+tr("yt.look_up","Look up")+'</button></div>'
      +'<ul class="ytalist" id="ytalist" role="listbox" aria-label="'+_fesc(tr("yt.sugg","Suggested addresses"))+'" hidden></ul>'
      +'<p class="sr" id="ytasay" role="status"></p></form>'
      +'<div class="ytares" id="ytares" role="status"></div>'
      +'<p class="ytpriv">'+tr("yt.addr_privacy","Suggestions come from this site&rsquo;s own list of New Hampshire streets and are matched in your browser, so this site sees only the first two letters of the street. The address you look up goes from your browser to the US Census Bureau&rsquo;s address lookup and is not kept anywhere. Only the town or ward it finds is saved.")+'</p></details>'
      +(p?'<p class="ytacts"><button type="button" class="ytbtn2 ytquiet" id="ytback">'+tr("yt.keep","Keep {place}",{place:_fesc(p.n)})+"</button></p>":"");
  }
  h+='<p class="ytpriv">'+tr("yt.privacy","Saved in this browser only. Nothing about it is sent to Granite Record.")+'</p>';
  out.innerHTML=h;
  const q=out.querySelector("#ytq");
  if(q){
    const list=()=>{
      const rows=ytRows(q.value);
      out.querySelector("#ytout").innerHTML=rows.map(r=>
        `<button type="button" class="ytrow" data-pick="${_fesc(r.s)}">${_fesc(r.n)}</button>`).join("")
        +(q.value.trim()&&!rows.length?'<p class="ytnote">'+tr("yt.no_place","No town or ward by that name.")+'</p>':"");
      out.querySelector("#ytqsay").textContent=q.value.trim()
        ?(rows.length===1?tr("yt.one_place","1 place"):tr("yt.n_places","{n} places",{n:rows.length})):"";
    };
    q.addEventListener("input",list);
    q.addEventListener("keydown",e=>{
      if(e.key==="Enter"){const b=out.querySelector(".ytrow");if(b){e.preventDefault();b.click();}}
    });
  }
  const f=out.querySelector("#ytaform");
  if(!f)return;
  const box=out.querySelector("#ytaddr"),res=out.querySelector("#ytares");
  f.addEventListener("submit",e=>{e.preventDefault();ytLook(box,res);});
  yaCombo(box,out.querySelector("#ytalist"),out.querySelector("#ytasay"),c=>{
    if(c.num){ytLook(box,res);return;}
    // A street with no number: it stays in the box, the cursor in front of
    // it, for the number the geocoder needs.
    box.value=" "+c.label;box.focus();
    if(box.setSelectionRange)box.setSelectionRange(0,0);
    res.innerHTML='<p class="ytnote">'+tr("yt.add_number","Add your house number in front of the street, then press Look up.")+"</p>";
  });
}
// Look up, as the box's button does it: the address to the Census, and what
// it found said under the box.
function ytLook(box,res){
  const a=box.value.trim();
  if(!a)return;
  res.innerHTML='<p class="ytnote">'+tr("yt.looking","Looking it up&hellip;")+'</p>';
  ytGeocode(a).then(d=>{
    const r=ytFromCensus(d);
    const said=r.addr?`<p class="ytnote">${tr("yt.matched","Matched: {addr}",{addr:_fesc(r.addr)})}</p>`:"";
    if(r.pick){res.innerHTML=said+`<p>${tr("yt.addr_in","That address is in {place}.",{place:"<b>"+_fesc(r.pick.n)+"</b>"})}</p>`
      +`<button type="button" class="ytbtn2" data-pick="${_fesc(r.pick.s)}">${tr("yt.make_mine","Make {place} my town",{place:_fesc(r.pick.n)})}</button>`;}
    else if(r.wards){res.innerHTML=said+`<p>${tr("yt.addr_wards","That address is in {town}, in a district that holds more than one ward, so the lookup cannot say which. Your ward is on your voter registration, or the clerk can tell you.",{town:_fesc(r.town)})}</p>`
      +r.wards.map(w=>`<button type="button" class="ytrow" data-pick="${_fesc(w.s)}">${_fesc(w.n)}</button>`).join("");}
    else if(r.why==="state")res.innerHTML=said+"<p>"+tr("yt.addr_state","That address is not in New Hampshire.")+"</p>";
    else if(r.why==="town")res.innerHTML=said+`<p>${tr("yt.addr_town","The lookup placed it in {place}, which this site has no page for. Choose your town from the list above.",{place:_fesc(r.name||tr("yt.a_place","a place"))})}</p>`;
    else res.innerHTML="<p>"+tr("yt.addr_none","The Census lookup did not recognize that address. Try the street number, street and town, or choose your town from the list above.")+"</p>";
  },()=>{res.innerHTML="<p>"+tr("yt.addr_down","The Census lookup did not answer. Choose your town from the list above, or try again in a minute.")+"</p>";});
}
/* THE LANGUAGE, A ROW OF SETTINGS (the person, 23 October 2026: "an option
   to select the language manually in the settings section or to
   automatically set it based on the browser"). i18n.py says how the site's
   languages are kept; chrome.LANG_HEAD, in every page's head, has already
   read the choice (gr-lang) and the browser's languages, gone to this page
   in the language wanted where it has one, and marked html.langs where a
   language is on offer to this reader. Without that mark there is no row.
   The choice is the browser's language (nothing kept), or one language;
   choosing reloads the page, and the head's script takes it from there. Its
   label says "Language" in both languages, since a reader who cannot read
   the page is the one looking for it. */
const LANG_NAMES={en:"English",es:"Español"};
function langPref(){return window.GR_PREF||{here:document.documentElement.lang||"en",want:"en",chosen:"",browser:""};}
function langMount(set){
  if(!set||!document.documentElement.classList.contains("langs")||document.getElementById("langsel"))return;
  const P=langPref();
  const row=document.createElement("label");
  row.className="langrow";
  // "Language" in this page's words, and in every other language's.
  const N=window.GR_NOTICE||{},said=[tr("set.lang","Language")];
  Object.keys(N).forEach(c=>{if(N[c].label&&said.indexOf(N[c].label)<0)said.push(N[c].label);});
  if(P.here!=="en"&&said.indexOf("Language")<0)said.push("Language");
  row.innerHTML=`<span class="langword">${_fesc(said.join(" · "))}</span><select id="langsel">`
    +`<option value="">${_fesc(tr("set.lang_browser","Browser’s language"))}</option>`
    +Object.keys(LANG_NAMES).map(c=>`<option value="${c}" lang="${c}">${LANG_NAMES[c]}</option>`).join("")
    +"</select>";
  const sel=row.querySelector("select");
  sel.value=P.chosen||"";
  sel.addEventListener("change",()=>{
    try{sel.value?localStorage.setItem("gr-lang",sel.value):localStorage.removeItem("gr-lang");}catch(e){}
    // The page in the language now wanted, where it has one; this page again
    // otherwise, where its notice says so.
    const want=sel.value||P.browser||"en";
    const to=document.documentElement.getAttribute("data-alt-"+want);
    if(to&&want!==P.here)location.href=to+location.search+location.hash;else location.reload();
  });
  set.insertBefore(row,set.firstChild);
}
/* A PAGE NOT YET IN THE LANGUAGE WANTED says so, once, at its top: the page
   in English is what there is, and the home page is in the reader's
   language. Closed, it stays closed for the visit (sessionStorage). The
   notice is in the language the reader asked for, which is the one thing
   on the page they can be sure to read: its words are that language's, from
   the catalog, which every page's head carries for this (window.GR_NOTICE,
   chrome.notice_words). */
function langNotice(){
  const P=langPref(),N=(window.GR_NOTICE||{})[P.want];
  if(!N||P.want===P.here||!document.documentElement.classList.contains("langs"))return;
  try{if(sessionStorage.getItem("gr-lang-notice")==="shut")return;}catch(e){}
  const main=document.querySelector("main")||document.body;
  if(!main||document.getElementById("langnote"))return;
  const box=document.createElement("p");
  box.id="langnote";box.className="langbar";box.lang=P.want;
  box.innerHTML=`${_fesc(N.text)} <a href="/${P.want}/" data-setlang="${P.want}">${_fesc(N.home)}</a>`
    +`<button type="button" class="langx" aria-label="${_fesc(N.close)}">&#10005;</button>`;
  box.querySelector("button").addEventListener("click",()=>{
    box.remove();try{sessionStorage.setItem("gr-lang-notice","shut");}catch(e){}});
  main.insertBefore(box,main.firstChild);
}
function ytMount(){
  const bar=document.querySelector("nav.top .in");
  if(!bar||document.getElementById("ytbtn"))return;
  const btn=document.createElement("button");
  btn.id="ytbtn";btn.className="ytbtn";btn.type="button";
  btn.setAttribute("aria-expanded","false");btn.setAttribute("aria-controls","ytpanel");
  btn.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-6.5-6.1-6.5-11a6.5 6.5 0 0 1 13 0c0 4.9-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.4"/></svg><span class="ytword">'+tr("yt.title","Your town")+'</span>';
  // SITE-WIDE SETTINGS, IN ONE PLACE (the person, 12 October 2026: "under
  // the hamburger menu on mobile like the light and dark mode is, or on
  // desktop maybe there's a setting icon that drops down to allow you to
  // select town or ward and light/dark mode and other site-wide settings").
  // The theme control and this button go into one group, .navset, at the
  // end of the sections panel: on a phone they are its last rows, under the
  // menu button; on a wider screen the group is the dropdown of a settings
  // button beside search. One copy of each control, as there is one copy of
  // the sections. Anything site-wide added later is a row in this group.
  const drop=document.getElementById("navdrop"),th=document.getElementById("themer");
  const set=document.createElement("div");
  set.id="navset";set.className="navset";
  set.setAttribute("role","group");set.setAttribute("aria-label",tr("set.label","Site settings"));
  if(drop){
    if(th&&th.parentNode===drop)drop.insertBefore(set,th);else drop.appendChild(set);
    if(th)set.appendChild(th);
    set.appendChild(btn);
  }else bar.appendChild(btn);
  langMount(set);
  const gear=document.createElement("button");
  gear.id="setbtn";gear.className="setbtn";gear.type="button";
  gear.setAttribute("aria-expanded","false");gear.setAttribute("aria-controls","navset");
  gear.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg><span>'+tr("set.title","Settings")+'</span>';
  const fb=document.getElementById("findbtn");
  if(fb&&fb.parentNode===bar)bar.insertBefore(gear,fb);else bar.appendChild(gear);
  const nav=document.querySelector("nav.top");
  const setShut=()=>{nav.classList.remove("setopen");gear.setAttribute("aria-expanded","false");};
  gear.addEventListener("click",()=>{
    if(nav.classList.contains("setopen")){setShut();return;}
    // Hung from the gear itself: between 45em and 63em the bar is two rows
    // and the bar's own bottom edge is under the tabs, not under the gear.
    set.style.top=(gear.offsetTop+gear.offsetHeight+6)+"px";
    set.style.right=Math.max(0,bar.clientWidth-gear.offsetLeft-gear.offsetWidth)+"px";
    nav.classList.add("setopen");gear.setAttribute("aria-expanded","true");
    const f=set.querySelector("button:not([hidden])");if(f)f.focus();
  });
  set.addEventListener("focusout",e=>{
    const to=e.relatedTarget;
    if(nav.classList.contains("setopen")&&to&&!set.contains(to)&&to!==gear)setShut();
  });
  document.addEventListener("click",e=>{
    if(nav.classList.contains("setopen")&&!set.contains(e.target)&&!gear.contains(e.target))setShut();
  });
  document.addEventListener("keydown",e=>{
    if(e.key==="Escape"&&nav.classList.contains("setopen")){setShut();gear.focus();}
  });
  // Where the focus goes back to when the panel closes: the control a reader
  // can see -- the settings button, or the phone's menu button -- since the
  // town button itself is folded away again by then.
  const home=()=>[gear,document.getElementById("navmenu")].find(x=>x&&x.offsetParent)||btn;
  const scrim=document.createElement("div");
  scrim.className="findscrim";scrim.hidden=true;
  const panel=document.createElement("div");
  panel.id="ytpanel";panel.className="findpanel ytpanel";panel.hidden=true;
  panel.setAttribute("role","region");panel.setAttribute("aria-label",tr("yt.title","Your town"));
  panel.innerHTML='<div class="findin"><div class="findgrab" aria-hidden="true"></div>'
    +'<div class="yttop"><h2 class="ythead">'+tr("yt.title","Your town")+'</h2>'
    +'<button type="button" class="findcancel ytclose" id="ytclose">'+tr("yt.close","Close")+'</button></div>'
    +'<div id="ytbody"><p class="ytnote">'+tr("yt.loading","Loading&hellip;")+'</p></div></div>';
  nav.parentNode.insertBefore(scrim,nav.nextSibling);
  nav.parentNode.insertBefore(panel,scrim.nextSibling);
  const shut=()=>{
    panel.hidden=true;scrim.hidden=true;delete panel.dataset.changing;
    document.documentElement.classList.remove("findopen");
    btn.setAttribute("aria-expanded","false");
  };
  const open=(change)=>{
    // Out of the menu or the settings dropdown it was chosen from.
    setShut();
    if(nav.classList.contains("open")){nav.classList.remove("open");
      const mb=document.getElementById("navmenu");if(mb)mb.setAttribute("aria-expanded","false");}
    const fp=document.getElementById("findpanel");
    if(fp&&!fp.hidden)document.getElementById("findbtn").click();
    panel.hidden=false;scrim.hidden=false;
    if(change)panel.dataset.changing="1";
    document.documentElement.classList.add("findopen");
    btn.setAttribute("aria-expanded","true");
    ytLoad().then(()=>{ytDraw();
      const f=panel.querySelector("#ytq")||panel.querySelector(".ytplace a");if(f)f.focus();
    },()=>{panel.querySelector("#ytbody").innerHTML='<p class="ytnote">'+tr("yt.no_list","The list of towns did not load. Try again in a moment.")+'</p>';});
  };
  btn.addEventListener("click",()=>{panel.hidden?open():shut();});
  panel.querySelector("#ytclose").addEventListener("click",()=>{shut();home().focus();});
  scrim.addEventListener("click",shut);
  if(fb)fb.addEventListener("click",()=>{if(!panel.hidden)shut();});
  panel.addEventListener("click",e=>{
    const t=e.target.closest("button");if(!t)return;
    e.stopPropagation();
    if(t.dataset.pick){delete panel.dataset.changing;ytSave(t.dataset.pick);
      const a=panel.querySelector(".ytplace a");if(a)a.focus();}
    else if(t.id==="ytchange"){panel.dataset.changing="1";ytDraw();const q=panel.querySelector("#ytq");if(q)q.focus();}
    else if(t.id==="ytback"){delete panel.dataset.changing;ytDraw();}
    else if(t.id==="ytforget"){delete panel.dataset.changing;ytSave("");const q=panel.querySelector("#ytq");if(q)q.focus();}
  });
  document.addEventListener("click",e=>{
    const o=e.target.closest&&e.target.closest(".ytopen");
    if(o){e.preventDefault();open(!!ytGet());return;}
    if(!panel.hidden&&!panel.contains(e.target)&&!btn.contains(e.target)&&e.target!==scrim)shut();
  });
  document.addEventListener("keydown",e=>{
    if(e.key!=="Escape"||panel.hidden)return;
    const inside=panel.contains(document.activeElement);shut();if(inside)home().focus();
  });
  // Another tab that changes it changes it here.
  addEventListener("storage",e=>{if(e.key===YT.key)ytApply();});
  ytApply();
}
ytMount();
langNotice();
