(function(){
/* THE ROSTER BY COUNTY, AND NOTHING ELSE SINCE 21 NOVEMBER 2026. This
   script was also the My Town finder -- a box that found a town or a member
   as it was typed -- until the owner made My Town a pop-up (the header's
   "Your town" panel, find.js), opened from the Officials overview's "Find
   your town" box. What is left draws the Legislators tab's By county view
   into #out from legislators.json. */
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// Anchored to the site root, not to the page. legislators.html is served at
// /legislators, and a legislators/ folder of per-member data sits beside it --
// so /legislators can be redirected to /legislators/, and a relative
// "legislators/377204.json" then resolves to /legislators/legislators/... and
// 404s. The bill page had the same trap.
window.DATA=window.DATA||((f)=>new URL(f, location.origin+"/").href);
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

let MEM=[];
fetch(DATA("legislators.json")).then(r=>r.json()).then(L=>{
  if(!Array.isArray(L))L=Object.values(L);
  MEM=L.map(m=>({
    slug:m.slug, chamber:m.chamber, county:m.county||"",
    district:m.district, sortname:m.sort||m.name||"",
    full:m.display_full||m.display_plain||m.name||"",
    p:(m.party||"X")[0].toUpperCase()}));
  roster();
});
})();
