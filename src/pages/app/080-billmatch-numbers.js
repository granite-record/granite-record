// BILLMATCH:BEGIN -- what counts as a bill number; see the note above SYN.
// Asked of every bill in the list, about the same search: the answer for
// the search last asked about is kept. Reading 20,000 pasted letters again
// for each of 2,243 bills, six times a drawing, was two seconds of nothing.
/* A BILL NUMBER AS PEOPLE WRITE IT (the owner, 6 November 2026: test the
   search the way real people search). "H.B. 703", "H. B. 703" and "H.B.703"
   are how a letter, a newspaper or a lawyer's memo writes HB 703, and they
   found nothing; "Senate Bill 11" was read as its words, so it listed HR 11
   and CACR 11, which say "senate", above SB 11. A kind spelled out, or its
   letters with full stops, is read as the kind's letters before the number.
   The longer names first, so "house concurrent resolution" is HCR and not
   "house" and the rest. The ten kinds the General Court names in words; the
   others are written by their letters. */
const NUMBER_WORDS=[
  ["constitutional amendment concurrent resolution","CACR"],
  ["house concurrent resolution","HCR"],["senate concurrent resolution","SCR"],
  ["house joint resolution","HJR"],["senate joint resolution","SJR"],
  ["house resolution","HR"],["senate resolution","SR"],
  ["house bill","HB"],["senate bill","SB"]
].map(([w,k])=>[new RegExp("^"+w.split(" ").join("\\s+")+"\\s*(?:no\\.?\\s*)?(?=\\d)","i"),k]);
function numberForm(p){
  let s=String(p).trim();
  for(const [rx,k] of NUMBER_WORDS)if(rx.test(s)){s=s.replace(rx,k);break;}
  // "H.B.", "H. B." and "H.B": two to five letters, a full stop after each
  // but perhaps the last.
  return s.replace(/^((?:[a-z]\s*\.\s*){1,4}[a-z]\s*\.?\s*)(?=\d)/i,m=>m.replace(/[\s.]/g,""));
}
/* A BILL REQUEST'S NUMBER AS PEOPLE WRITE IT (the owner, 11 November 2026:
   "you also can't search for LSR by number"). A request is "LSR 2027-0002"
   and its id is LSR20270002; people type "2027-0002", "LSR 2027-0002",
   "LSR2027-0002", "LSR 27-0002" and "27-0002". Read as that id, the way a
   bill's number is read as its. The year is the requests' own once it is
   known (setRequestYear): "2026-0002" is no request of this site's, and
   "2026-0002" in the search box is nothing else either. A two-digit year
   takes a four-digit number after it ("27-0002"; "12-5" is not one). "LSR
   0002" is the requests' year and that number. A term's name ("2027-2028",
   "2027-28") is no request. A bare "0002" is a request
   only where the list is the requests' (`bare`, which /bills sets by the
   list on screen): anywhere else it is a number like any other. */
let REQ_YEAR="",REQ_BARE=false;
function setRequestYear(y){REQ_YEAR=String(y||"");NUMBERS_OF=null;}
function requestNumber(p,bare){
  const s=String(p).trim();
  const id=(y,n)=>{
    // "2027-2028" and "2027-28" are the next term's name, not a request.
    if(y.length===4&&(+n===+y+1||(n.length===2&&+n===(+y+1)%100)))return null;
    if(y.length===2)y="20"+y;
    if(REQ_YEAR&&y!==REQ_YEAR)return null;
    return "LSR"+y+String(n).padStart(4,"0");
  };
  let m=/^lsr\s*\.?\s*(\d{4})\s*[-–—\s]\s*(\d{1,4})$/i.exec(s)
     ||/^lsr\s*(\d{2})\s*[-–—\s]\s*(\d{4})$/i.exec(s)
     ||/^(\d{4})\s*[-–—]\s*(\d{1,4})$/.exec(s)
     ||/^(\d{2})\s*[-–—]\s*(\d{4})$/.exec(s)
     ||/^lsr\s*(\d{4})(\d{4})$/i.exec(s);
  if(m)return id(m[1],m[2]);
  m=/^lsr\s*\.?\s*(\d{1,4})$/i.exec(s);
  if(m&&REQ_YEAR&&m[1]!==REQ_YEAR)return id(REQ_YEAR,m[1]);
  // On the requests' list a bare number of one to four digits is a request:
  // "12", "012" and "0012" are LSR 2027-0012 (the owner, 11 November 2026).
  // The year itself, "2027", stays a word.
  if(bare&&REQ_YEAR&&/^\d{1,4}$/.test(s)&&s!==REQ_YEAR)return id(REQ_YEAR,s);
  return null;
}
/* ONLY A KIND THE GENERAL COURT NUMBERS IS A NUMBER (the review of 14 November
   2026). Any two to five letters before digits were read as one, so "covid
   19" was the bill COVID19 and found nothing where "covid-19" found 24 votes,
   and "Rule 64", "Route 101" and "title 5" the same. These are the eighteen
   the site's bills and requests carry, counted off the record (find.js's
   FBILLKIND, with LSR, a request's): HB 23,213; SB 8,618; HR 570; CACR 545;
   HCR 350; LSR 312; SR 147; HJR 117; SCR 68; PET 29; SJR 25; HBI 14; HA 9;
   SSHB 4; SSSB 4; HCO 2; SSHR 1; SSHCR 1. A kind added tomorrow is a word
   until it is added here, and preflight holds the list to the bills'. */
const BILL_KINDS=new Set(["HB","SB","CACR","HCR","SCR","HJR","SJR","HR","SR",
  "PET","HBI","HA","HCO","SSHB","SSSB","SSHR","SSHCR","LSR"]);
let NUMBERS_OF=null,NUMBERS=null,NUMBERS_BARE=false;
function billNumbers(q){
  if(q===NUMBERS_OF&&NUMBERS_BARE===REQ_BARE)return NUMBERS;
  NUMBERS_OF=q;NUMBERS_BARE=REQ_BARE;
  const parts=q.split(",").map(s=>s.trim()).filter(Boolean);
  if(!parts.length)return NUMBERS=null;
  const ids=parts.map(p=>requestNumber(p,REQ_BARE)||numberForm(p).replace(/\s+/g,"").toUpperCase()
                         .replace(/^([A-Z]{2,5})0+(?=\d)/,"$1"));
  return NUMBERS=ids.every(i=>{const m=/^([A-Z]{2,5})\d+$/.exec(i);return !!m&&BILL_KINDS.has(m[1]);})?ids:null;
}
// BILLMATCH:END
