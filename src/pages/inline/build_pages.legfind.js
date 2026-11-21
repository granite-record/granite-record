(function(){
/* THE ROSTER BY COUNTY, AND NOTHING ELSE SINCE 21 NOVEMBER 2026. This
   script was also the My Town finder -- a box that found a town or a member
   as it was typed -- until the owner made My Town a pop-up (the header's
   "Your town" panel, find.js), opened from the Officials overview's "Find
   your town" box. What is left draws the Legislators tab's By county view
   into #out from legislators.json, and since the owner's word of the same
   day ("The legislators tab should get its own search box") the tab's box
   that finds a member by name, county, party or committee (lsMount). */
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

/* A LEGISLATOR FOUND BY WHAT A READER KNOWS OF THEM (the owner, 21 November
   2026: "The legislators tab should get its own search box"). My Town's box
   found a member by name, county, party or committee and went with it; this
   is that search, on the Legislators tab, in the site's own suggestion list:
   find.js's comboWire drawing the filters' .qoffers, as the town box does.

   Every word typed must begin a word of the member's name, county, district,
   party (in English and in the page's language) or one of their committees,
   so "merrimack dem" is the Democrats of Merrimack County; a name matched
   ranks first. The list keeps the Senate over the House, each under its
   name, never one alphabet across both. Choosing a member opens their page.
   Search, or Return with nothing chosen, lists every match under the box,
   the chambers apart, each the roster's own chip -- and the reader's own
   representatives are marked on those as on every chip that links them
   (find.js ytMark), and in the list by the same words. */
const LS_MOST=10;     // a screen of suggestions, then "Show all"
const lsFold=s=>String(s||"").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g,"")
  .replace(/[^a-z0-9]+/g," ").trim();
// A party's name in the page's language, as the roster says it: the build
// writes each party the roster holds into the box's data-parties
// (build_pages.legislator_box, from parts.party_word, the one table), so this
// script keeps no table of its own. Read when the box is mounted.
let PW={};
function lsHay(m){
  const name=lsFold(m.plain), last=lsFold(m.name);
  const words=s=>lsFold(s).split(" ").filter(Boolean);
  return {name, last, own:new Set([...words(m.plain),...words(m.name)]),
    rest:[m.county,m.dlabel,"district "+(m.district||""),m.party,PW[m.party]||""]
      .flatMap(words),
    cmte:m.committees.map(c=>[c,words(c)])};
}
// [member, tier, the committee it was found by or ""] for each match, best first.
function lsMatch(q){
  const qs=lsFold(q).split(" ").filter(Boolean);
  if(!qs.length)return [];
  const has=(ws,w)=>ws.some(x=>x.startsWith(w));
  const out=[];
  MEM.forEach(m=>{
    const h=m.hay||(m.hay=lsHay(m)), own=[...h.own];
    let by="";
    const ok=qs.every(w=>{
      if(has(own,w)||has(h.rest,w))return true;
      const c=h.cmte.find(([,ws])=>has(ws,w));
      if(c){by=by||c[0];return true;}
      return false;
    });
    if(!ok)return;
    const q1=qs.join(" ");
    const tier=h.name.startsWith(q1)||h.last.startsWith(q1)?0:qs.every(w=>has(own,w))?1:2;
    out.push([m,tier,tier<2?"":by]);
  });
  return out.sort((a,b)=>a[1]-b[1]||a[0].sortname.localeCompare(b[0].sortname));
}
// The Senate first, then the House, each in the order it was ranked.
const lsApart=rows=>["S","H"].flatMap(ch=>rows.filter(r=>r[0].chamber===ch));
const lsChamber=ch=>ch==="S"?tr("lf.senate","Senate"):tr("lf.house","House");
// "Your rep" or "Your senator", where the reader's saved town names them.
function lsMine(m){
  const p=typeof ytPlace==="function"&&ytPlace();
  if(!p||!(p.m||[]).includes(m.slug))return "";
  return `<span class="lsmine">${m.chamber==="S"?tr("yt.your_senator","Your senator"):tr("yt.your_rep","Your rep")}</span>`;
}
function memChip(m){
  return `<div class="mem"><span class="mchip p-${esc(m.p)}" translate="no">`
    +`<a href="legislator/${esc(m.slug)}">${chipName(m.full)}</a></span></div>`;
}
// Every match under the box, the chambers apart, or what was searched.
function lsAll(q){
  const res=document.getElementById("lsres");
  if(!res)return;
  const v=String(q||"").trim();
  if(!v){res.innerHTML="";res.hidden=true;return;}
  const got=lsApart(lsMatch(v));
  const n=got.length;
  const said=!n?tr("lf.ls_none","No sitting member matches that. Names, counties, parties and committees are searched.")
    :n===1?tr("lf.ls_one","1 member matches &ldquo;{q}&rdquo;.",{q:esc(v)})
    :tr("lf.ls_many","{n} members match &ldquo;{q}&rdquo;.",{n,q:esc(v)});
  res.innerHTML=`<p class="lsnote" role="status">${said} <button type="button" class="link" id="lsclear">${tr("lf.ls_clear","Clear")}</button></p>`
    +["S","H"].map(ch=>{
      const ms=got.filter(r=>r[0].chamber===ch).map(r=>r[0]);
      return ms.length?`<h3>${lsChamber(ch)} &mdash; ${ms.length}</h3><div class="grid">${ms.map(memChip).join("")}</div>`:"";
    }).join("");
  res.hidden=false;
}
function lsMount(){
  const box=document.getElementById("lsbox");
  if(!box||typeof comboWire!=="function"||box.dataset.on)return;
  box.dataset.on="1";
  try{PW=JSON.parse(box.dataset.parties||"{}")||{};}catch(e){PW={};}
  const form=box.querySelector("form"),inp=box.querySelector("#lsq");
  if(!form||!inp)return;
  const list=document.createElement("ul");
  list.id="lsq-offers";list.className="qoffers";list.hidden=true;
  list.setAttribute("role","listbox");list.setAttribute("aria-label",tr("lf.ls_list","Members"));
  const say=document.createElement("span");
  say.className="sr";say.setAttribute("role","status");
  inp.setAttribute("role","combobox");inp.setAttribute("aria-autocomplete","list");
  inp.setAttribute("aria-expanded","false");inp.setAttribute("aria-controls",list.id);
  inp.parentNode.appendChild(list);inp.parentNode.appendChild(say);
  let found=0;
  const combo=comboWire(inp,list,say,{
    rows:v=>{
      const got=lsMatch(v);found=got.length;
      const shown=lsApart(got.slice(0,LS_MOST)).map((r,i,a)=>({m:r[0],by:r[2],
        head:!i||a[i-1][0].chamber!==r[0].chamber}));
      if(got.length>LS_MOST)shown.push({all:v,n:got.length});
      return shown;
    },
    // One option element whatever the row: "Show all", or a member under
    // their chamber's name where the chamber changes.
    opt:(r,i,id,on)=>(r.all==null&&r.head?`<li role="presentation" class="qgroup">${lsChamber(r.m.chamber)}</li>`:"")
      +`<li role="option" class="qoffer${r.all!=null?" lsall":""}" id="${id}" data-i="${i}" aria-selected="${on}">`
      +(r.all!=null?`<b>${tr("lf.ls_all","Show all {n}",{n:r.n})}</b>`
        :`<span><b>${esc(r.m.plain)}</b>${lsMine(r.m)}</span>`
        +`<span class="c">${esc([r.by||PW[r.m.party]||r.m.party,r.m.where].filter(Boolean).join(" · "))}</span>`)+"</li>",
    said:()=>found===1?tr("lf.n_member","{n} member",{n:1}):tr("lf.n_members","{n} members",{n:found}),
    pick:r=>{
      if(r.all!=null){lsAll(r.all);return;}
      location.href=new URL("legislator/"+r.m.slug,location.origin+"/").href;
    },
    wait:80});
  form.addEventListener("submit",e=>{e.preventDefault();combo.shut();lsAll(inp.value);});
  document.addEventListener("click",e=>{
    const t=e.target&&e.target.closest&&e.target.closest("#lsclear");
    if(!t)return;
    inp.value="";lsAll("");inp.focus();
  });
  inp.disabled=false;
  const go=form.querySelector("button");if(go)go.disabled=false;
}

let MEM=[];
// find.js, which holds comboWire, is deferred: the box is mounted once it has run.
const lsReady=new Promise(r=>document.readyState==="loading"
  ?document.addEventListener("DOMContentLoaded",r):r());
fetch(DATA("legislators.json")).then(r=>r.json()).then(L=>{
  if(!Array.isArray(L))L=Object.values(L);
  MEM=L.map(m=>({
    slug:m.slug, chamber:m.chamber, county:m.county||"",
    district:m.district, sortname:m.sort||m.name||"",
    full:m.display_full||m.display_plain||m.name||"",
    p:(m.party||"X")[0].toUpperCase(),
    // For the search box: the name as a reader says it, "Rep." left off;
    // the district as the chip says it; the party and the committees.
    plain:(m.display_plain||m.name||"").replace(/^(Rep|Sen)[.][ ]*/,""),
    name:m.name||"", party:m.party||"", dlabel:m.district_label||"",
    where:m.chamber==="S"?tr("off.district","District {d}",{d:m.district}):[m.county,m.district].filter(Boolean).join(" "),
    committees:m.committees||[]}));
  roster();
  return lsReady.then(lsMount);
});
})();
