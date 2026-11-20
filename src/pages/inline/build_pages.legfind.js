(function(){
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
const SHOW=12;            // matches at once: a screen of them, not a scroll
const MIN=2;              // letters before the list appears

let TOWNS=[], MEM=[], picked=null;
// A party as the page's language says it, so a reader can find the members
// of one by typing its name in that language too (the Officials page in
// Spanish, 25 October 2026). In English these are the words already searched.
const PW={R:tr("party.r","Republican"),D:tr("party.d","Democrat"),
          I:tr("party.i","Independent"),L:tr("party.l","Libertarian")};

function slugOf(s){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,"-")
  .replace(/^-|-$/g,"");}

/* RANKED, NOT JUST FILTERED. Somebody typing "Dover" was shown Andover first
   and their own town second, under a town they do not live in. Three tiers:
   the exact name, then names that BEGIN with what was typed, then names with
   a word that begins with it. "Hampton" lists Hampton, Hampton Falls, New
   Hampton and North Hampton, and all four are real answers.
   FROM THE START OF A WORD (the audit of 25 October 2026, M4): the third tier
   was any name that held the letters, so "Dover" still listed Andover, and
   "ham" Durham. A member's name and record are still searched anywhere in
   them (render(), m.hay). */
function tier(hay,n){const s=hay.toLowerCase();
  return s===n?0:s.startsWith(n)?1:(" "+s.replace(/-/g," ")).includes(" "+n)?2:3;}

function townRow(t){
  // ONE ROW PER TOWN, and the row says one thing: the name. The live list
  // said the name and, for a city, how many wards it has -- and that is all
  // it needs to say. "Town", "Go" and "who represents it" were three labels
  // repeating what a row in a list of towns obviously is.
  // A town without wards is a link straight to its page. A city cannot be:
  // there is no town/concord.html, only concord-ward-1 through 10. So it
  // opens its wards, one chip each, and the chip is the link.
  if(t.wards.length>1)
    return `<button type="button" class="lmrow${picked===t.town?" sel":""}"
      data-town="${esc(t.town)}"><b>${esc(t.town)}</b>
      <span class="wct">${tr("lf.wards","{n} wards",{n:t.wards.length})}</span></button>`
      + (picked===t.town ? `<div class="wards">` + t.wards.map(w=>
          `<a class="wbtn" href="town/${esc(t.slug)}-ward-${esc(w)}"
            >${tr("lf.ward","Ward {w}",{w:esc(w)})}</a>`).join("") + `</div>` : "");
  return `<a class="lmrow" href="town/${esc(t.slug)}"
    ><b>${esc(t.town)}</b></a>`;
}

function render(){
  const box=document.getElementById("lq");
  const out=document.getElementById("lmatch");
  const n=(box.value||"").trim().toLowerCase();
  /* RANKED, NOT JUST FILTERED, AND NEVER EMPTY. With nothing typed this is
     every town in the state, scrollable -- which is what it was before, and
     what somebody unsure of their spelling needs. Typing ranks it and adds
     the members that match. */
  const towns=(n?TOWNS.map(t=>[tier(t.town,n),t]).filter(r=>r[0]<3)
                   .sort((a,b)=>a[0]-b[0]||a[1].i-b[1].i)
               :TOWNS.map(t=>[0,t]));
  const mem=n.length>=MIN
    ? MEM.map(m=>[Math.min(tier(m.name,n),m.hay.includes(n)?2:3),m])
         .filter(r=>r[0]<3)
         .sort((a,b)=>a[0]-b[0]||a[1].sortname.localeCompare(b[1].sortname))
    : [];
  const parts=[];
  if(towns.length){
    if(mem.length)parts.push('<p class="lmhead">'+tr("lf.towns","Towns")+'</p>');
    parts.push(towns.map(([,t])=>townRow(t)).join(""));
  }
  if(mem.length){
    parts.push('<p class="lmhead">'+tr("lf.members","Members")+'</p>');
    parts.push(mem.slice(0,SHOW).map(([,m])=>
      `<a class="lmrow" href="legislator/${esc(m.slug)}">`
      +`<b>${esc(m.display)}</b>`
      +chip(m.p,"pt-"+m.p)
      +`<span class="lmwhere">${esc(m.where)}</span>`
      +`<span class="lmwhat">${m.chamber==="S"?tr("lf.senate","Senate"):tr("lf.house","House")}</span></a>`)
      .join(""));
    if(mem.length>SHOW)parts.push('<p class="lmnone">'
      +tr("lf.more","and {n} more members &mdash; type another letter or two.",{n:mem.length-SHOW})
      +'</p>');
  }
  // No apostrophe in these sentences on purpose: this is JavaScript inside a
  // Python string, where a backslash belongs to whichever one reads it
  // first. Python read one, dropped it, and left the JavaScript with an
  // unterminated string and the whole page with no script.
  /* THE MAP FOLLOWS THE FINDER: a town named in full, or a city whose
     wards were opened, is the map's town too (OFFICIALS_MAP_JS). */
  const exact=towns.length&&n&&towns[0][1].town.toLowerCase()===n?towns[0][1].town:null;
  const tw=picked||exact;
  if(tw&&tw!==window.__grTown){window.__grTown=tw;
    dispatchEvent(new CustomEvent("grtown",{detail:tw}));}
  out.innerHTML=parts.length?parts.join("")
    :'<p class="lmnone">'+tr("lf.none","Nothing matches that. Towns and wards, member names, counties, parties and committees are all searched.")+'</p>';
  /* WHAT THE LIST NOW HOLDS, SAID. It is redrawn at every letter and nothing
     told a screen reader that it had changed (the audit of 2 October 2026,
     S4). One line the eye does not see, role="status": how many towns and
     members match what was typed, or that nothing does. Silent while the box
     is empty, when the list is every town and is not an answer to anything. */
  const say=document.getElementById("lsay");
  if(say){
    const said=[towns.length?(towns.length===1?tr("lf.n_town","{n} town",{n:1})
                                 :tr("lf.n_towns","{n} towns",{n:towns.length})):"",
                mem.length?(mem.length===1?tr("lf.n_member","{n} member",{n:1})
                             :tr("lf.n_members","{n} members",{n:mem.length})):""]
      .filter(Boolean);
    const what=said.length===2?tr("lf.and","{a} and {b}",{a:said[0],b:said[1]}):said[0];
    const text=!n?"":!said.length?tr("lf.nothing","Nothing matches that.")
      :towns.length+mem.length===1?tr("lf.matches","{what} matches",{what:what})
      :tr("lf.match","{what} match",{what:what});
    if(say.textContent!==text)say.textContent=text;
  }
  /* The chips into view, and no further than the row they belong to. */
  const wb=out.querySelector(".wards");
  if(wb){
    const lr=out.getBoundingClientRect(), wr=wb.getBoundingClientRect();
    if(wr.bottom>lr.bottom)
      out.scrollTop+=Math.min(wr.bottom-lr.bottom,
        wb.previousElementSibling.getBoundingClientRect().top-lr.top);
  }
}

/* The roster: every member, by chamber and then by county, each county shut
   until it is asked for. */
// The name, then the party and district as one unit app.css keeps whole, so
// a chip that wraps in its cell does so before "(D - Straf 17)", never in it.
function chipName(full){
  const s=String(full||""), i=s.lastIndexOf(" (");
  return i>0&&s.endsWith(")")?`${esc(s.slice(0,i))} <span class="mtag">${esc(s.slice(i+1))}</span>`:esc(s);
}
function roster(){
  const by={};
  MEM.forEach(m=>{const ch=m.chamber==="S"?"Senate":"House";
    (by[ch]=by[ch]||{});
    (by[ch][m.county||"Not on file"]=by[ch][m.county||"Not on file"]||[]).push(m);});
  const html=["Senate","House"].filter(ch=>by[ch]).map(ch=>{
    const counties=Object.keys(by[ch]).sort();
    const total=counties.reduce((n,c)=>n+by[ch][c].length,0);
    const chName=ch==="Senate"?tr("lf.senate","Senate"):tr("lf.house","House");
    return `<h2>${chName} &mdash; ${total}</h2>`+counties.map(c=>{
      // By district number, then by name. Alphabetical order inside a county
      // scattered the members of one district across the list, when the
      // district is the thing a reader is looking for: it is what a town
      // lookup returns and what a ballot is organised by.
      const ms=by[ch][c].slice().sort((a,b)=>
        (parseInt(a.district,10)||0)-(parseInt(b.district,10)||0)
        ||a.sortname.localeCompare(b.sortname));
      return `<details class="cgrp"><summary><span>${c==="Not on file"?tr("lf.not_on_file","Not on file"):esc(c)}</span>`
        +`<span class="ccount">${ms.length}</span>`
        +`<span class="caret">&#9656;</span></summary><div class="grid">`
        // THE SAME CHIP AS THE OTHER TWO VIEWS (pchip in Python), which the
        // person asked for on 19 September; this view kept its own name, pill
        // and district until 24 September. display_full carries all three.
        +ms.map(m=>`<div class="mem"><span class="mchip p-${esc(m.p)}" translate="no">`
          +`<a href="legislator/${esc(m.slug)}">${chipName(m.full)}</a></span></div>`).join("")
        +`</div></details>`;
    }).join("");
  }).join("");
  document.getElementById("out").innerHTML=html;
}

Promise.all([fetch(DATA("districts.json")).then(r=>r.json()).catch(()=>({})),
             fetch(DATA("legislators.json")).then(r=>r.json())])
 .then(([D,L])=>{
   if(!Array.isArray(L))L=Object.values(L);
   // ONE ENTRY PER TOWN, with its wards inside it. 259 rows a reader can
   // scroll, not 320 with Concord taking ten of them.
   Object.keys(D).sort().forEach(town=>{
     const wards=Object.keys(D[town]||{})
       .sort((a,b)=>parseInt(a)-parseInt(b));
     TOWNS.push({town:town, slug:slugOf(town), wards:wards, i:TOWNS.length});
   });
   MEM=L.map(m=>({
     slug:m.slug, chamber:m.chamber, county:m.county||"",
     district:m.district, dlabel:m.district_label||("dist "+m.district),
     display:m.display_plain||m.name, sortname:m.sort||m.name||"",
     full:m.display_full||m.display_plain||m.name||"",
     // [.] and [ ] rather than the escapes: this JavaScript lives inside a
     // Python string, and a backslash in one is a warning in the other.
     name:(m.display_plain||m.name||"").replace(/^(Rep|Sen)[.][ ]*/,""),
     p:(m.party||"X")[0].toUpperCase(),
     where:[m.county,m.district_label].filter(Boolean).join(" "),
     hay:[m.name,m.party,m.county,"district "+m.district,m.district_label,
          m.title||"",(m.committees||[]).join(" "),
          (m.towns||[]).join(" "),PW[(m.party||"X")[0].toUpperCase()]||""].join(" ").toLowerCase()}));
   const box=document.getElementById("lq");
   box.disabled=false;
   document.getElementById("lcount").textContent=
     tr("lf.count","{t} towns and cities, {m} sitting members",{t:TOWNS.length,m:MEM.length});
   roster();
   /* ?town= and ?q= arrive from the home page's finder. Both fill the one
      field: a town that is warded cannot be resolved to a page without
      knowing the ward, so the reader picks it from the matches. */
   const pr=new URLSearchParams(location.search);
   const pre=(pr.get("town")||pr.get("q")||"").trim();
   if(pre)box.value=pre;
   /* A CITY NAMED IN THE ADDRESS OPENS ITS WARDS: the site search's one row
      for a city, "Concord, 10 wards", leads here (find.json, 25 October
      2026), and the reader came for a ward. */
   const city=TOWNS.find(t=>t.wards.length>1&&t.town.toLowerCase()===pre.toLowerCase());
   if(city)picked=city.town;
   /* AND THE TAB NAMES THE TOWN (the cohesion audit of 30 October 2026,
      B-4): /town/concord comes here for its wards (MOVED), and the tab and
      a bookmark said only "Officials". The page's own title, with the town
      ?town= names before it -- only a town of the list, never a search's
      words. The canonical stays this page's: the address is this page. */
   const named=TOWNS.find(t=>t.town.toLowerCase()===(pr.get("town")||"").trim().toLowerCase());
   if(named)document.title=named.town+" — "+document.title;
   render();
   box.focus();
   box.addEventListener("input",()=>{picked=null;render();});
   /* One handler on the list rather than one per row: the list is rebuilt on
      every keystroke and a listener per row would be rebuilt with it. */
   document.getElementById("lmatch").addEventListener("click",e=>{
     const b=e.target.closest("[data-town]");
     if(!b)return;
     picked=picked===b.dataset.town?null:b.dataset.town;
     render();
   });
 });
})();
