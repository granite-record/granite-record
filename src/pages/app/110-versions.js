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
// THE TAB OPENS ON THE FULL TEXT (the person, 7 October 2026, F15): the
// current version, whole, as the Court printed it. What changed is one press
// away; it opened on that, which answered a question before the reader had
// read the bill it was about. One default, read by both the pane and what it
// fetches, so the two cannot ask for different views.
const VMODE_FIRST = "text";

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
// A RULE IS DRAWN AS A RULE (the look of 7 October 2026). The Court's
// documents draw their horizontal rules in characters -- a run of "─", "-",
// "_" or ". . .", 40 to 160 of them -- and with Full text now the first view
// (F15), a phone showed the rule under a bill's sponsors wrapped onto three
// lines. Such a paragraph keeps its characters, which are the document's, and
// stays on one line, cut at the column's edge (app.css, .vrule).
const VRULE=/^[\s\-─_.=]+$/;
const vblkClass=(bl,t)=>`vblk vblk-${esc(bl.k||"ln")}${
  VRULE.test(t)&&t.replace(/\s/g,"").length>=8?" vrule":""}`;

function vmarked(bs,ms,link=x=>x){
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
      if(s>=at)html+=link(esc(t.slice(at,s)));
      if(op==="-"){html+=`<del class="vdel">${link(esc(m[4]||""))}</del>`;
        at=Math.max(at,s);}
      else{html+=`<ins class="vins">${link(esc(t.slice(s,e)))}</ins>`;
        at=Math.max(at,e);}
    });
    html+=link(esc(t.slice(at)));
    out.push(`<p class="${vblkClass(bl,t)}">${html}</p>`);
  });
  gap();
  return `<div class="vdoc" tabindex="0" role="region" aria-label="Bill text">${out.join("")}</div>`;
}

// A VERSION'S DAY AS THE RECORD STAMPS IT, "12/11/2025 16:02:08", said the
// way every date on the site is (dateWords, month first): the Bill Text tab
// printed "12/11/2025" under each version and "Amendment of 05/07/2026" until
// the review of the polish foundation (8 October 2026). Anything else is cut
// at its first space, as it was.
function recordDay(s){
  const m=/^(\d{1,2})\/(\d{1,2})\/(\d{4})\b/.exec(String(s||""));
  return m?dateWords(`${m[3]}-${m[1].padStart(2,"0")}-${m[2].padStart(2,"0")}`)
    :String(s||"").split(" ")[0];
}
// WHAT THE DOCKET SAYS OF AN AMENDMENT, set beside it on the Bill Text tab (the
// owner's walk of 8 November 2026: "its number, whether it was only proposed or
// adopted, and whether it came from the committee or from the floor"). The
// record's amendment rows (build_site_v2.bill_amendments) carry it: `kind` is
// the docket line's own word -- Committee Amendment, Floor Amendment, Minority
// Amendment, Enrolled Bill Amendment, or plain Amendment where the line says
// no more -- and `adopted` is true or false only where the line's motion says
// the amendment carried or failed. Where it says neither the row says nothing,
// and a plain "Amendment" gives no origin chip: nothing is guessed. The words
// are the ones renderBillText's amendments already use, in its chips.
const AMD_ORIGIN={"Committee Amendment":"Committee","Floor Amendment":"Floor",
  "Minority Amendment":"Minority","Enrolled Bill Amendment":"Enrolled Bill"};
// "2025-0695h" and "0695h" are one number, as amendmentOwn's matching has it.
const amdSameNo=(a,b)=>{a=String(a||"").toLowerCase();b=String(b||"").toLowerCase();
  return !!a&&!!b&&(a===b||a.endsWith("-"+b)||b.endsWith("-"+a));};
const amdFact=(d,num)=>((d&&d.amendments)||[]).find(x=>amdSameNo(x.num,num))||null;
// THE ORIGIN IS IN THE NAME (Alice, 9 November 2026): "Floor Amendment
// 2025-0695h", not "Amendment 2025-0695h" beside a Floor chip. A docket line
// that says only "Amendment", or no docket line, keeps the plain word.
const amdName=(f,num)=>`${f&&AMD_ORIGIN[f.kind]?f.kind:"Amendment"} ${num}`;
function amdBadges(f){
  if(!f)return "";
  return f.adopted===true?chip("Adopted","cstat s-law"):f.adopted===false?chip("Rejected","cstat s-done"):"";
}
// Who moved it, the day the docket took it up and how it was decided.
function amdWhen(f){
  return [f.mover||f.proposed_by||"",f.date?dateWords(f.date):"",AVK[f.vote_kind]||""]
    .filter(Boolean).map(esc).join(" · ");
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
  // A STATUTE CITED IN A VERSION'S TEXT OR AN AMENDMENT'S LINKS TO ITS LAW'S
  // PAGE, as it does in the bill's own record (makeRsa): the bill's map and
  // the index's, which names every citation in every text of the bill
  // (build_version_links.py). Links alone: a defined term gets no pop-up
  // here, because which chapter's definitions apply to a passage is stated
  // only in the "Amend RSA ..." clause above it, and a pop-up on the wrong
  // chapter's definition would be a false statement of the law.
  const link=makeRsa({rsa:Object.assign({},(d&&d.rsa)||{},ix.rsa||{})});
  // THE CURRENT VERSION BY DEFAULT, which is the last one the record has.
  if(VPICK[key]===undefined)VPICK[key]=vs.length?vs.length-1:0;
  const mode=VMODE[key]||VMODE_FIRST;
  const i=Math.min(VPICK[key],Math.max(0,vs.length-1));

  // A group of toggle buttons, not a tablist: it declared role="tablist" with
  // no role="tab" inside, which a screen reader announces as an empty list of
  // tabs, and no key handler moved through it.
  const vbtn=(v,j)=>`<button class="vbtn${j===i?" sel":""}" data-ver="${esc(key)}|${j}"
      aria-pressed="${j===i?"true":"false"}">${esc(v.title)}<i>${
      esc(recordDay(v.date))}</i></button>`;

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
      :onDoc?vmarked(doc,mk,link)
      // Still waiting on the document, but the excerpt is already here: draw
      // it rather than a spinner, because it answers the question and the
      // better view can replace it when it arrives.
      :Array.isArray(rs)?`<div class="vdiff">${rs.map(([op,txt])=>
          op==="~"?`<span class="vskip">${esc(txt)} words unchanged</span>`
          :op==="+"?`<ins>${link(esc(txt))}</ins>`
          :op==="-"?`<del>${link(esc(txt))}</del>`
          :`<span>${link(esc(txt))}</span>`).join("")}</div>`
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
      :isBlocks?`<div class="vdoc" tabindex="0" role="region" aria-label="Bill text">${got.map(bl=>
          `<p class="${vblkClass(bl,(bl.runs||[]).map(r=>r[1]).join(""))}">${(bl.runs||[]).map(
            ([role,t])=>role==="add"?`<ins class="vins">${link(esc(t))}</ins>`
              :role==="cut"?`<del class="vdel">${link(esc(t))}</del>`
              :link(esc(t))).join("")}</p>`).join("")}</div>`
      :typeof got==="string"?`<pre class="vtext">${link(esc(got))}</pre>`
      // An empty array is a blocks file that parsed to nothing, which is a
      // different failure from a fetch that did not arrive and says so.
      :Array.isArray(got)?`<p class="note">The text of this version is on
         file but could not be read into paragraphs.</p>`
      :`<p class="note">That text could not be loaded.</p>`;
  }

  // EACH AMENDMENT BY ITS NUMBER, with what the docket records of it: whether
  // it carried or failed, and whether the committee or a member from the floor
  // moved it (amdBadges). The number is the index's (build_version_links.py,
  // read from the amendment's own text), and the docket's row is found by it;
  // an amendment the index has no number for keeps "Amendment of <day>" and
  // no badge, since which docket line it is would be a guess. An amendment the
  // docket moved and the index holds no text for is listed after them, with
  // its facts and a plain statement that its text is not on file.
  const used=new Set();
  // IN THE ORDER THE DOCKET TOOK THEM UP where it names them (the record's
  // rows are in that order, and a committee's amendment is considered before a
  // floor amendment), the rest after, as the index lists them -- by the day
  // each was filed, which is not that order.
  const at=f=>f?(d.amendments||[]).indexOf(f):1e6;
  const rows=amds.map((a,j)=>{
    const f=a.num?amdFact(d,a.num):null;
    if(f)used.add(f);
    const nid=AMENDMENT_FOUND[a.text_url]||a.num||"";
    return {pos:at(f)+(f?0:j/1e4),html:`<li${nid?` id="amendment-${esc(nid)}"`:""}><button class="link"
      data-vamd="${esc(key)}|${j}">${a.num?esc(amdName(f,a.num)):`Amendment of ${esc(recordDay(a.date))}`}</button>
      ${amdBadges(f)}${f&&amdWhen(f)?`<span class="dim">${amdWhen(f)}</span>`:""}
      <span class="dim">${(a.chars||0).toLocaleString()} characters</span>${
      VTEXT[a.text_url]!==undefined
        ? `<pre class="vtext">${link(esc(String(VTEXT[a.text_url])))}</pre>` : ""}</li>`};})
    .sort((x,y)=>x.pos-y.pos).map(x=>x.html);
  const unfiled=((d&&d.amendments)||[]).filter(f=>f&&f.num&&!used.has(f)
    &&!amds.some(a=>a.num&&amdSameNo(a.num,f.num)));
  const orphan=f=>`<li id="amendment-${esc(f.num)}"><span class="amdn">${esc(amdName(f,f.num))}</span>
      ${amdBadges(f)}${amdWhen(f)?`<span class="dim">${amdWhen(f)}</span>`:""}${
      f.text?`<details class="amdtext"><summary>Read the amendment</summary>
        <pre class="vtext">${link(esc(f.text))}</pre></details>`
       :`<p class="note">Its text is not on file here.</p>`}</li>`;
  const amdblock=(amds.length||unfiled.length)?`<h2 class="sech">The Amendments Themselves</h2>
    <p class="note">Each amendment as the General Court published it; these are
    not versions of the bill. Whether it carried and whether the committee or
    the floor moved it are the docket&rsquo;s words, and are left out where the
    docket does not say.</p>
    <ul class="vamds">${rows.join("")}${unfiled.map(orphan).join("")}</ul>`:"";

  return picker+toggle+body+amdblock;
}

// Fetch whatever the current view needs and redraw when it lands. Everything
// already here is used from the cache; nothing is asked for twice.
function needVersions(b){
  // A BILL REQUEST HAS NO VERSIONS FILE: its Bill Text tab is its own
  // (lsrTextPane), and since every request has one (17 November 2026) a
  // press on it asked /versions/<year>/LSR....json, which no build writes.
  if(b&&b.lsr)return;
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
  const mode=VMODE[key]||VMODE_FIRST;
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
  seekAmendment(key);
}

// AN AMENDMENT BY ITS NUMBER, FROM THE ADDRESS (the person, 26 October 2026:
// "the amendment number should link to open it on the bill text tab").
// /bill/2026/hb1560/text#amendment-2026-0422h opens HB 1560-FN's Bill Text
// tab with that amendment open and brought into view, as "Amendment of
// January 30, 2026" opens when it is pressed; Testify's pane links its
// number there (testifyButton). The version index lists a bill's amendments
// by their day and length, not their number, and the number is in each one's
// own text, the first thing in it with that shape: "January 30, 2026
// 2026-0422h 05/08 Amendment to HB 1560-FN". So the texts are read in turn
// until the one whose first number is this one, which alone is opened. On
// the preview of 26 October 2026 that found the amendment of every one of
// the 46 hearings on one that the sitting term's records hold. A number none
// of them carries leaves the tab as it always opens.
const AMENDMENT_HASH=/^amendment-((?:\d{4}-)?\d{3,4}[a-z]{1,2})$/i;
const amendmentHref=(year,id,num)=>`bill/${year}/${String(id).toLowerCase()}/text#amendment-${num}`;
// "2026-0422h"; a committee of conference's "2026-2109-CofC" is its own.
const amendmentOwn=t=>{
  const m=/\b(\d{4}-\d{4})(-?[a-z]*)/i.exec(String(t||"").slice(0,1000));
  return m?(m[1]+m[2]).toLowerCase():"";
};
let AMENDMENT_WANT=null;     // {key, num}: the one the address names, until it is looked for
let AMENDMENT_JUMP=null;     // its text's address once found, until it is in view
const AMENDMENT_FOUND={};    // text address -> the number it was found by
function amendmentAsked(b,said){
  const m=AMENDMENT_HASH.exec(String(said||""));
  AMENDMENT_WANT=m?{key:verKey(b),num:m[1].toLowerCase()}:null;
}
async function seekAmendment(key){
  const w=AMENDMENT_WANT, ix=VERS[key];
  if(!w||w.key!==key||!ix||ix._error)return;
  AMENDMENT_WANT=null;
  // The index names each amendment's number (build_version_links.py), so the
  // one asked for is fetched alone; an index that does not is read in turn.
  const named=(ix.amendments||[]).filter(a=>a.num&&amdSameNo(a.num,w.num));
  for(const a of (named.length?named:(ix.amendments||[]))){
    let t=VTEXT[a.text_url];
    if(typeof t!=="string"){
      try{
        const r=await fetch(DATA(a.text_url.replace(/^\//,"")));
        if(!r.ok)continue;
        t=await r.text();
      }catch(_){continue;}
    }
    const own=amendmentOwn(t);
    if(own&&(own===w.num||own.endsWith("-"+w.num))){
      VTEXT[a.text_url]=t;AMENDMENT_FOUND[a.text_url]=w.num;AMENDMENT_JUMP=a.text_url;
      repaint();return;
    }
  }
}
// Brought into view once, when the version's own text above it has come, so
// that text arriving after cannot push it back down the page; and below the
// tab strip, which a bill's own page holds at the top of the window as it
// scrolls: brought to the top, "Amendment of January 30, 2026" and the
// text's first line were under it (the preview, 26 October 2026).
function jumpToAmendment(){
  if(!AMENDMENT_JUMP)return;
  const li=document.getElementById("amendment-"+AMENDMENT_FOUND[AMENDMENT_JUMP]);
  const pane=li&&li.closest(".pane");
  if(!li||!pane||pane.querySelector(".spin"))return;
  AMENDMENT_JUMP=null;
  const card=li.closest(".card"), strip=card&&card.querySelector(".tabs");
  const held=strip&&getComputedStyle(strip).position==="sticky"?strip.getBoundingClientRect().height:0;
  window.scrollTo(0,Math.max(0,li.getBoundingClientRect().top+window.scrollY-held-16));
}
// The same link followed on the Bill Text tab's own address moves only the
// fragment, and the page is not loaded again: the fragment is read then too.
window.addEventListener("hashchange",()=>{
  if(!window.GR_BILL)return;
  let said="";
  try{said=decodeURIComponent(location.hash.slice(1));}catch(_){return;}
  const gm=/^(\d{4})\/([A-Z]{2,5}\d+)$/i.exec(String(window.GR_BILL));
  if(gm&&VOTE_HASH.test(said)){
    const vr=IDX.find(x=>x.id===gm[2].toUpperCase()&&String(x.year)===gm[1]);
    if(vr){openTab[vr.id]="1";VOTE_JUMP=said;repaint();}
    return;
  }
  const row=gm&&AMENDMENT_HASH.test(said)
    ?IDX.find(x=>x.id===gm[2].toUpperCase()&&String(x.year)===gm[1]):null;
  if(!row)return;
  openTab[row.id]="6";amendmentAsked(row,said);needVersions(row);repaint();
});


// A TAB'S COUNT AS A BADGE (the person's choice A, 14 October 2026). The
// words stay "Votes (5)": the brackets are in the text, hidden from sight and
// read aloud, so a screen reader, a copied label and the report box's tab
// name are what they were, and only the look changes.
const tabN=n=>`<span class="tn"><span class="tnp"> (</span>${n}<span class="tnp">)</span></span>`;

function renderDetail(b,d){
  const rsa=makeRsa(d);
  // Below the tabs, outside every pane, and only in the expanded view. The
  // bill text used to be assembled into a const above this template while
  // its own dependencies were declared below it, which threw the moment a
  // bill was focused -- a refresh on a bill page reporting that its detail
  // would not load when the file had arrived fine. It is a call now, made
  // where it is used, so there is nothing left to order wrongly.
  // NOT SINCE 10 OCTOBER 2026: a bill's own page is its head, its tabs and
  // the tab that is open (option E and the approved prototype, where the
  // summary takes the whole tab), and the text is the Bill Text tab's. Drawn
  // under every tab, the whole text ran on below the Summary and the Votes.
  const btsec="";

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
  const btPane=btHas
    ? `<div class="pane" role="tabpanel" id="pane_${b.id}_6" aria-labelledby="tab_${b.id}_6"
        tabindex="0" data-t="6" hidden>${hasVersionIndex(d)?renderVersions(b,d):billTextSection(b,d,makeRsa(d))}</div>`
    : "";

  // RELATED, ONLY WHERE THERE IS SOMETHING TO SHOW (RELATED_BILLS.md §6):
  // build_site_v2.add_related writes d.related only for a bill with a
  // relation the judged sample let through. data-t 7, after the six.
  // THE TAB IS LABELLED HISTORY (the owner's walk of dry run 8, 8 November
  // 2026); its address stays /related. Each bill is counted once.
  const rel=relatedMerge(Array.isArray(d.related)?d.related:[]);
  // EVERY BILL HAS A HISTORY TAB (the owner's walk of dry run 9, 8 November
  // 2026): with no related rows it says so and lists the laws it would change.
  const relPane=true
    ? `<div class="pane" role="tabpanel" id="pane_${b.id}_7" aria-labelledby="tab_${b.id}_7"
        tabindex="0" data-t="7" hidden>${renderRelated(b,rel,d)}</div>`
    : "";

  // THE STRIP IS THE RECORD'S (components.recordTabs, 16 November 2026), the
  // one a request's card and its own page draw too: [key, word, count], in
  // the DOM's order, a count of none drawing no badge.
  return recordTabs(b.id,[["0","Summary",0]].concat(btHas?[["6","Bill Text",d.nver>1?d.nver:0]]:[],[
    // What the pane draws, not the index row's count. b.nrc is the roll
    // calls that are not procedural; the pane draws d.rollcalls, which adds
    // the docket's voice and division votes. The two disagreed on 2,011 of
    // the current term's 2,234 bills -- mostly bills whose only votes were
    // voice votes, which showed "Votes" with nothing beside it and 3
    // sections beneath. And the voters' vote on an amendment they were
    // sent, once cast.
    ["1","Votes",votesDrawn(d)],
    // VIDEOS (the owner, 19 November 2026). It was Hearings from 8 October,
    // when it listed every sitting as a card; since 10 November it is a
    // committee's Videos tab for one bill, a player and its recordings, and
    // the Senate's hearing reports it carried are the Reports tab's. A sitting
    // with no recording still has its entry under the player. The count is
    // the count of recordings, absent on the terms that have none. data-t
    // stays "2": renumbering would repoint every saved link.
    ["2","Videos",videoCount(d)],
    ["3","Reports",reportCount(d)],
    // NO SPONSORS TAB (the owner, 19 November 2026): the sponsors are the top
    // of the Summary, and the strip fits one line at a desktop's width.
    ["5","Documents",(d.documents||[]).length],
    ["7","History",rel.length]]),"0")+`
    <div class="pane" role="tabpanel" id="pane_${b.id}_0" aria-labelledby="tab_${b.id}_0" tabindex="0" data-t="0">${renderSummary(b,d,rsa)}</div>
    ${/* ONLY WHERE THERE IS SOMETHING TO SHOW. 1,149 of 2,234 bills have a
          second version; a tab on the other 1,085 would say "there is one
          version" and fetch a file that is not there. nver comes from the
          manifest build_bill_versions.py writes. */ btPane}
    <div class="pane" role="tabpanel" id="pane_${b.id}_1" aria-labelledby="tab_${b.id}_1" tabindex="0" data-t="1" hidden>${paneNote("votes")}${renderVotes(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_2" aria-labelledby="tab_${b.id}_2" tabindex="0" data-t="2" hidden>${paneNote("hearings")}${renderHearings(b,d)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_3" aria-labelledby="tab_${b.id}_3" tabindex="0" data-t="3" hidden>${paneNote("reports")}${renderReports(b,d,rsa)}</div>
    <div class="pane" role="tabpanel" id="pane_${b.id}_5" aria-labelledby="tab_${b.id}_5"
      tabindex="0" data-t="5" hidden>${renderDocuments(b,d)}</div>${relPane}${btsec}`;
}

// THE RELATED TAB'S LIST. The specific first (RELATED_BILLS.md §6): where its
// language went or came from, then the same text filed before or after, then
// this term's bills with the same text. Each row is the sentence, with the
// other bill linked where the sentence names it, and that bill's title and
// status under it. The sentence is related_bills.sentence's, the one the
// bench judged, so the page says nothing the sample did not.
const RELATED_HEADS=["Where Its Language Went","Filed Before and After","This Term\u2019s Bills with the Same Text"];
// One relation's sentence, the other bill linked where it names it, and its
// term beside it where that is not this bill's.
function relatedSaid(b,e){
  const id=String(e.o).split("/")[1]||"";
  const other=String(e.o).slice(0,9)!==String(b.term||"");
  const href=`bill/${e.y}/${id.toLowerCase()}`;
  const name=`<a href="${esc(href)}">${esc(e.n)}</a>${other?` (${esc(String(e.o).slice(0,9)).replace("-","&ndash;")})`:""}`;
  return esc(e.s).replace("{b}",name);
}
// EACH BILL ONCE (the owner's walk of dry run 8, 8 November 2026): a bill
// whose text was filed again and whose amendment carried the same language
// stood in two sections. The row for the same text stays where it is and each
// amendment's fact follows it as a second sentence; with no such row, the
// first row stays and the rest follow it. build_site_v2.related_entries gives
// an amendment's row m (its number), f (the docket's fate), fb and fv (the
// chamber and the vote).
function amendmentSaid(e){
  const house={H:"House",S:"Senate"}[e.fb]||"chamber";
  const vote=e.fv?`, ${e.fv}`:"";
  const how={adopted:`, which the ${house} adopted${vote},`,failed:`, which the ${house} rejected${vote},`,
    withdrawn:", which was withdrawn,"}[e.f]||"";
  return {s:`Amendment ${e.m}${how} carried its language into it.`,f:e.f||""};
}
// WHAT BECAME OF THE AMENDMENT, NOT OF THE BILL IT WENT INTO (the owner's walk
// of dry run 9, 8 November 2026): a rejected amendment to a bill that became law
// read as if the language had. The chip is the amendment's fate, in the cards'
// passing, failing and neutral colours; the other bill's own outcome follows
// only where the amendment was adopted.
const AMD_CHIP={adopted:["Amendment Adopted","s-law"],failed:["Amendment Rejected","s-done"],
  withdrawn:["Amendment Withdrawn","s-study"]};
const amdChip=f=>AMD_CHIP[f]?chip(AMD_CHIP[f][0],`cstat ${AMD_CHIP[f][1]}`):"";
function relatedMerge(rel){
  const at=new Map(),out=[];
  for(const e of rel){
    if(!at.has(e.o)){at.set(e.o,out.length);out.push(Object.assign({},e));continue;}
    const i=at.get(e.o),p=out[i];
    if(e.m){
      // An amendment's row joins the row already standing for the bill.
      (p.more=p.more||[]).push(amendmentSaid(e));
    }else if(p.m){
      // The standing row is an amendment's and this one is not: this leads.
      const q=Object.assign({},e,{more:[amendmentSaid(p)].concat(p.more||[])});
      out[i]=q;
    }
  }
  return out;
}
// THE SAME NUMBER IN OTHER TERMS (the owner, 10 November 2026: "the history
// tab should match prior bills for standard ones like HB1, HB2, HB25"). For a
// number corrections/bill_notes.json gives a standing meaning, the build
// (build_site_v2.add_same_number) writes d.same_number: the same number in each
// other term the note is true of, newest first. Each row links to that term's
// bill, with its title and its outcome chip as the History tab's other rows.
function sameNumber(b,d){
  const rows=(d&&d.same_number)||[];
  if(!rows.length)return "";
  const num=esc(b.n||b.id);
  return `<section class="rl-g sn"><h2 class="sech">${num} in other terms</h2><ul class="rl-list">${
    rows.map(r=>{
      const term=esc(String(r.term||"").replace("-","\u2013"));
      const c=r.c?" "+chip(r.c,`cstat ${chipCls({chip:r.c})}`):"";
      return `<li class="rl-row"><p class="rl-s"><a href="bill/${esc(r.y)}/${esc(String(r.id||b.id).toLowerCase())}">${
        esc(r.n||b.id)} of ${term}</a></p><p class="rl-t">${esc(r.t||"")}${c}</p></li>`;}).join("")}</ul></section>`;
}
function renderRelated(b,relRows,d){
  const rel=relatedMerge(relRows);
  const groups=[[],[],[]];
  for(const e of rel)(groups[e.g]||groups[2]).push(e);
  // The outcome in the colour the bill cards give that word (chipCls).
  const row=e=>{
    // A folded amendment's sentence carries its own fate chip, so the row's
    // chip stays the other bill's status; an amendment's row leads with the
    // amendment's chip and adds the bill's only if one was adopted.
    const said=relatedSaid(b,e)+(e.more||[]).map(m=>" "+esc(m.s)+" "+amdChip(m.f)).join("");
    const bill=e.c?chip(e.c,`cstat ${chipCls({chip:e.c})}`):"";
    let chips=bill;
    if(e.m){
      const adopted=e.f==="adopted"||(e.more||[]).some(m=>m.f==="adopted");
      chips=amdChip(e.f)+(adopted&&bill?" "+bill:"");
    }
    return `<li class="rl-row"><p class="rl-s">${said}</p>`
      +`<p class="rl-t">${esc(e.t)}${chips?" "+chips:""}</p></li>`;
  };
  return sameNumber(b,d)+groups.map((g,i)=>g.length
    ?`<section class="rl-g"><h2 class="sech">${RELATED_HEADS[i]}</h2><ul class="rl-list">${g.map(row).join("")}</ul></section>`:"").join("")
    +(rel.length?"":`<p class="story">No other bill was found sharing most of this bill&rsquo;s language.</p>`)
    +`<p class="src">Found by comparing the text of bills and their amendments. A bill is listed
      only where most of its language is shared, and an amendment only where the docket
      records what became of it; a match can be missed.</p>`
    // The chapters it would change, linked to the laws' pages, where each
    // section's bill history is shown (the owner's walk of dry run 9).
    +(rsaChapters(d||{}).length?rsaLines(Object.assign({},d,{changed:[]})):"");
}
// TAGS:BEGIN
// The bill's own page's History tab ends with its tags as searches, where
// TAGS_PLACE says so (tagHistory); a card opened in a list shows none.
renderRelated=(drawn=>function(b,relRows,d){
  const h=drawn(b,relRows,d);
  return TAGS_PLACE==="history"&&focused===b.id?h+tagHistory(b,d):h;
})(renderRelated);
// TAGS:END

