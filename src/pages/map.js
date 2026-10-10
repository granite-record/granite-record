// GRANITE_VERSION: 2026-10-09.2
/* THE DISTRICT MAP (map v1), as a module a page mounts:

     <link rel="stylesheet" href="/map.css">
     <script src="/map.js"></script>
     GRMap.mount(element, {layer:"base"});        // returns its api

   It draws one file, /district_map.json (src/pages/build_district_map.py),
   so a page needs nothing else loaded but the site's stylesheet, whose
   tokens colour it and whose .mchip draws a person in the panel. Polish 3
   places it on the Officials page's My Town tab (the town search above it
   calls api.pickTown) and on the town pages (frame, dim and ward).

   OPTIONS (mount's second argument; each has a default):
     layer   "base" (State House), "senate", "exec", "cong", "county", "towns"
     layers  the layers the switch offers, e.g. ["base","senate","exec","cong"]
     labels  "names" (the default), "numbers" or "none"
     town    a town to choose and zoom to; pick: a district of `layer`
     frame, dim, ward   a town page's map: framed on the town, the rest
             veiled, its own ward named first
     flo     every floterial framed; controls, legend, note, panel, list,
             zoom: false leaves that part out
     prompt  the panel's words before anything is chosen
     data    the file's address, "/district_map.json"
   API (returned at once; api.ready resolves when the data has drawn):
     pickTown(t), select(layer, fid), setLayer(layer), setLabels(mode),
     zoomOn(town, zoom), layer(), labels(), shown() (the labels drawn now).
   The element fires "gmchange" ({layer, labels, town, picked}) whenever a
   reader changes one, for a page that keeps them in its address.

   THE DESIGN IS THE PERSON'S, settled in the approved prototype
   (private/design/polish/map_v2/, its design DISTRICT_MAP.md, and the
   decisions of 8 and 9 October 2026), ported here unchanged in what it
   draws:
     - each district is FILLED with the party of whoever it elected (the D5
       inks, mixed 85% toward the card's colour, map.css); a district whose
       members are of more than one party is drawn in EQUAL STRIPES, never in
       proportion; a district with every seat vacant is a grey hatch, and the
       legend calls it "Vacant"; counties and towns are not coloured;
     - a base district is filled by its OWN members, and a floterial is a
       dashed frame in its members' party, drawn inside its own edge (method
       (a)): all of them on the "Floterial districts" toggle, otherwise only
       the chosen district's;
     - no zoom hint over the map (8 October, round 3).

   LABELS: A TOGGLE, TOWN NAMES BY DEFAULT. The person, 9 October: "Toggle to
   switch between viewing district numbers, town names, and no labels for the
   interactive map with the default being town names." The three modes are
   LABELS below and the default DEFAULT_LABELS; preflight holds both. Each
   mode lays its labels out with a pure function (layout(), below) that
   never lets two of them overlap; node runs it in preflight on the real
   geometry.
     - Town names (namesLayout): every town by its name and a city by its
       wards, wherever the name fits, round two's rule (9 October): the
       chosen town first, then the chosen district's tag, then the counties'
       names on Counties, then the cities, then the towns largest first, then
       the unincorporated places, each only where it fits wholly in view,
       inside its own town and clear of every name already down. A CITY'S
       WARDS ARE NAMED AS A GROUP: all of them in view, or none, and the
       city's own name with them ("Ward 3", or "3" alone for at most a third
       of them where "Ward 3" will not fit).
     - District numbers (numbersLayout): map v1's all-or-none rule, with a
       city's wards as their own group (the person, 8 October, round 3:
       "city wards numbered as their own group"). The numbers in view that
       lie in no one city are one group and each city's wards another (a
       city whose wards are in two or more districts); a group shows only if
       none of its numbers overlaps another or a number already shown, so a
       place is never half-numbered, and a city's neighbours are numbered
       while the city waits for room. A city is never numbered while the
       numbers around it are hidden.
     - No labels.
   There is no line under the map saying what is named (the person, 9
   October: "You can remove the line under the interactive map explaining
   what towns are currently in view").

   KEYBOARD AND SCREEN READERS. The two switches (the kind of district and
   the labels) are native radio buttons in labelled groups, so arrow keys
   move within each and a screen reader says "Town names, radio button, 1
   of 3". The map is one image to a screen reader (164 focusable paths would
   be worse than none, DISTRICT_MAP.md section 6); every district is in the
   list under it, each as a button that chooses it, and the choice is said
   in the panel, a polite live region. The map itself is one stop for the
   keyboard: arrow keys move it, + and - zoom, 0 fits it.

   Nothing here asks any server but the site's own, and nothing about what a
   reader chooses is recorded. */
(function(){
"use strict";
const NS="http://www.w3.org/2000/svg";
const esc=s=>String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const CC={BE:"Belknap",CA:"Carroll",CH:"Cheshire",CO:"Coos",GR:"Grafton",HI:"Hillsborough",ME:"Merrimack",RO:"Rockingham",ST:"Strafford",SU:"Sullivan"};
const NOUN={R:"Republican",D:"Democrat",I:"Independent"};
const PARTY={R:"Republican",D:"Democratic",I:"Independent"};
const NAME={base:"State House district",float:"Floterial district",senate:"State Senate district",
  exec:"Executive Council district",cong:"US House district",county:"",towns:""};
const LAYERS=[["base","State House"],["senate","State Senate"],["exec","Executive Council"],
  ["cong","US House"],["county","Counties"],["towns","Towns"]];
const LAYER_WORDS={base:"State House districts",senate:"State Senate districts",exec:"Executive Council districts",
  cong:"US House districts",county:"counties",towns:"towns"};
/* THE LABEL TOGGLE: its three modes, in the order drawn, and the default. */
const LABELS=[["names","Town names"],["numbers","District numbers"],["none","No labels"]];
const DEFAULT_LABELS="names";
const TINTED={base:1,senate:1,exec:1,cong:1};
/* The unincorporated places (grants, locations, purchases), by the record's
   own spelling: named last, in a quieter ink. */
const PLACE=/(Grant|Gt|Location|Loc\.|Purchase|Pur\.)$/;
const slugOf=(t,w)=>{const s=t.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"");return w&&w!=="0"?s+"-ward-"+w:s;};
const letterOf=p=>String(p||"X")[0].toUpperCase();
/* "Ward 4"; "Wards 1, 3–6" */
function wardWords(ws){
  const n=ws.map(Number).sort((a,b)=>a-b);if(n.length===1)return "Ward "+n[0];
  const runs=[];n.forEach(x=>{const r=runs[runs.length-1];if(r&&x===r[1]+1)r[1]=x;else runs.push([x,x]);});
  return "Wards "+runs.map(([a,b])=>a===b?String(a):b===a+1?a+", "+b:a+"–"+b).join(", ");
}
function label(lk,fid){
  if(lk==="base"||lk==="float")return `${CC[fid.slice(0,2)]} ${fid.slice(2)}`;
  if(lk==="county")return `${fid} County`;
  return fid;
}
/* The chosen district's tag on the map (round two's words). */
function tagWords(lk,fid){
  if(lk==="base")return label(lk,fid);
  if(lk==="float")return "Floterial "+label(lk,fid);
  if(lk==="senate")return "Senate District "+fid;
  if(lk==="exec")return "Council District "+fid;
  if(lk==="cong")return "US House District "+fid;
  return "";
}
/* A district's number as the numbers mode draws it: the number alone (a
   State House number means something only within its county, whose lines
   are drawn heavier), a county by its name. */
function numText(lk,fid){return lk==="base"?fid.slice(2):lk==="county"?fid:lk==="towns"?"":fid;}

/* ---------------------------------------------------------------- data --- */

/* ONE LOAD, ONE MODEL, however many maps a page draws. */
const LOADS={};
function load(url){
  url=url||"/district_map.json";
  if(!LOADS[url])LOADS[url]=fetch(url).then(r=>{if(!r.ok)throw new Error(url+": "+r.status);return r.json();}).then(model);
  return LOADS[url];
}
function model(T){
  const ARCS=T.arcs.map(a=>{const p=[[a[0],a[1]]];for(let i=2;i<a.length;i+=2){const q=p[p.length-1];p.push([q[0]+a[i],q[1]+a[i+1]]);}return p;});
  const M={T,ARCS,cache:{},bx:{},rg:{},tw:{},flo:{},wardsOf:{},area:{},group:{},city:{}};
  const push=(k,v)=>(M.tw[k]=M.tw[k]||[]).push(v);
  for(const t in T.places){const p=T.places[t];
    for(const w in p.w){const [b,f,s,c,g]=p.w[w];
      push("base|"+b,[t,w]);if(f){push("float|"+f,[t,w]);M.flo[b]=f;}
      push("senate|"+s,[t,w]);push("exec|"+c,[t,w]);push("cong|"+g,[t,w]);
      push("county|"+p.c,[t,w]);push("towns|"+t,[t,w]);}}
  (T.cities||[]).forEach(t=>{M.city[t]=1;});
  for(const t in T.wards||{})M.wardsOf[t]=T.wards[t].map(g=>({fid:g.d,wards:g.w,words:wardWords(g.w),l:g.l,b:g.b}));
  /* A district lies in one city when every town-ward it holds is that
     city's ward; its number is then one of that city's group. A city whose
     wards all lie in one district (Franklin's three, Somersworth's five) has
     no wards to number apart: that district is numbered with the rest, as a
     city with wards in two or more districts is named by its wards. */
  for(const lk in T.layers){M.group[lk]={};
    for(const fid in T.layers[lk].f){
      const tw=M.tw[lk+"|"+fid]||[],t0=tw.length?tw[0][0]:null;
      M.group[lk][fid]=(lk!=="county"&&lk!=="towns"&&t0&&(M.wardsOf[t0]||[]).length>1&&tw.every(([t,w])=>t===t0&&w!=="0"))?t0:"";}}
  for(const t in T.layers.towns.f){let a=0;rings(M,"towns",t).forEach(r=>{let s=0;
    for(let i=0;i<r.length;i++){const p=r[i],q=r[(i+1)%r.length];s+=p[0]*q[1]-q[0]*p[1];}a+=Math.abs(s)/2;});M.area[t]=a;}
  return M;
}

/* ------------------------------------------------------------ geometry --- */

function arcPts(M,i){return i>=0?M.ARCS[i]:M.ARCS[~i].slice().reverse();}
/* a feature's rings as point lists, in the map's units, kept once made */
function rings(M,lk,fid){const k=lk+"|"+fid;if(M.rg[k])return M.rg[k];
  return M.rg[k]=M.T.layers[lk].f[fid].r.map(refs=>{let pts=[];refs.forEach((r,j)=>{const a=arcPts(M,r);pts=pts.concat(j?a.slice(1):a);});return pts;});}
function featD(M,lk,fid){const k=lk+"|"+fid;if(!M.cache[k])M.cache[k]=rings(M,lk,fid).map(p=>"M"+p.map(q=>q[0]+" "+q[1]).join("L")+"Z").join("");return M.cache[k];}
/* A feature's outline: only the arcs its rings use once. */
function outlineD(M,lk,fid){const k=lk+"|out|"+fid;if(M.cache[k])return M.cache[k];
  const n={};M.T.layers[lk].f[fid].r.forEach(ring=>ring.forEach(a=>{const i=a<0?~a:a;n[i]=(n[i]||0)+1;}));
  return M.cache[k]=Object.keys(n).filter(i=>n[i]===1).map(i=>"M"+M.ARCS[i].map(p=>p[0]+" "+p[1]).join("L")).join("");}
function meshD(M,lk){const k=lk+"|mesh";if(!M.cache[k])M.cache[k]=M.T.layers[lk].m.map(i=>"M"+M.ARCS[i].map(p=>p[0]+" "+p[1]).join("L")).join("");return M.cache[k];}
/* a feature's box in the map's units: [x0, y0, x1, y1] */
function fbox(M,lk,fid){const k=lk+"|"+fid;if(M.bx[k])return M.bx[k];
  let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
  rings(M,lk,fid).forEach(r=>r.forEach(([x,y])=>{if(x<x0)x0=x;if(x>x1)x1=x;if(y<y0)y0=y;if(y>y1)y1=y;}));
  return M.bx[k]=[x0,y0,x1,y1];}
/* whether a point (map units) lies in a feature: even-odd over its rings */
function inFeature(M,lk,fid,x,y){
  const b=fbox(M,lk,fid);if(x<b[0]||x>b[2]||y<b[1]||y>b[3])return false;
  let c=false;
  rings(M,lk,fid).forEach(r=>{for(let i=0,j=r.length-1;i<r.length;j=i++){const [x1,y1]=r[i],[x2,y2]=r[j];
    if((y1>y)!==(y2>y)&&x<(x2-x1)*(y-y1)/(y2-y1)+x1)c=!c;}});
  return c;
}

/* ------------------------------------------------------ the label rules --- */
/* PURE: what a map shows, given what it is (M), where its view stands (V)
   and what is asked (S). Nothing here reads the page, so preflight runs it in
   node on the real geometry. Boxes are in the view's pixels, x and y in the
   map's units.
     V: {vb: [x, y, w, h] the drawing's box, s: pixels per unit, ox, oy:
         where the box's origin is in the view, vw, vh: the view's size,
         obstacles: [[x0, y0, x1, y1]] (the zoom buttons)}
     S: {mode, layer, here (the chosen town, or a town page's own), ward (a
         ward page's ward), frame, dim, picked: [layer, fid] or null,
         rootPx (the root font size), measure(text, weight, px) -> width} */

/* Sizes on screen in rem, on D3's scale: nothing under 13px, and 13px only
   in capitals and figures. A town, a ward and the tag 14px, a city 16px,
   the chosen town 18px, the counties 13px in capitals, a district's number
   13px. They follow the browser's text size, so a reader with large text
   gets large labels, and fewer of them fit. */
const SIZE={here:1.125,city:1,town:.875,place:.875,ward:.875,hereward:1,county:.8125,tag:.875,num:.8125};
const WEIGHT={here:600,city:600,town:500,place:400,ward:500,hereward:600,county:600,tag:600,num:600};
const GAP=2;
const overlaps=(a,b,g)=>a[0]<b[2]+g&&b[0]<a[2]+g&&a[1]<b[3]+g&&b[1]<a[3]+g;

function layout(M,V,S){
  if(S.mode==="numbers")return numbersLayout(M,V,S);
  if(S.mode==="none")return {mode:"none",shown:[],tag:null,stats:{}};
  return namesLayout(M,V,S);
}

/* ALL OR NONE, A GROUP AT A TIME. Each number's box on screen: its figures
   in the label's face at 13px, a quarter of that again for its halo, 13px
   tall, and GAP kept clear around it. Only the numbers at least partly in
   view count, and one under the zoom buttons counts as out of view. */
function numbersLayout(M,V,S){
  const lk=S.layer,out={mode:"numbers",shown:[],tag:null,stats:{groups:0,groupsShown:0}};
  if(lk==="towns")return out;
  const px=SIZE.num*S.rootPx,X=x=>V.ox+(x-V.vb[0])*V.s,Y=y=>V.oy+(y-V.vb[1])*V.s;
  const obst=V.obstacles||[],by={};
  for(const fid in M.T.layers[lk].f){
    const f=M.T.layers[lk].f[fid],text=numText(lk,fid),w=S.measure(text,WEIGHT.num,px)+px/4,cx=X(f.l[0]),cy=Y(f.l[1]);
    const b=[cx-w/2,cy-px/2,cx+w/2,cy+px/2];
    if(!(b[2]>0&&b[0]<V.vw&&b[3]>0&&b[1]<V.vh)||obst.some(o=>overlaps(b,o,0)))continue;
    const g=M.group[lk][fid]||"";(by[g]=by[g]||[]).push({id:"n:"+fid,k:"num",cls:"lab",text,x:f.l[0],y:f.l[1],box:b,group:g});
  }
  // the numbers in no one city first, then each city's, most wards first.
  // A city waits for its neighbours: while the numbers in no one city are in
  // view and do not fit, no city's are shown either, so a city's wards are
  // never numbered alone on a map that numbers nothing around them.
  const order=Object.keys(by).sort((a,b)=>(a===""?-1:b===""?1:0)||by[b].length-by[a].length||a.localeCompare(b));
  const placed=[];
  for(const g of order){const items=by[g];out.stats.groups++;
    const bx=items.map(i=>i.box).sort((a,b)=>a[0]-b[0]);
    let fits=bx.every(b=>placed.every(p=>!overlaps(b,p,GAP)));
    scan:for(let i=0;fits&&i<bx.length;i++)for(let j=i+1;j<bx.length&&bx[j][0]<bx[i][2]+GAP;j++)
      if(overlaps(bx[i],bx[j],GAP)){fits=false;break scan;}
    if(!fits){if(g==="")break;continue;}
    out.stats.groupsShown++;placed.push(...bx);out.shown.push(...items);}
  return out;
}

/* HOW THE NAMES THIN OUT (round two, 9 October). The names are laid down
   one at a time in this order, each only where its box is wholly in view (a
   name a few pixels over the edge is moved just inside), clear of every name
   already down by GAP and of the zoom buttons:
     1. the chosen town, or a town page's own: always. Where it is a city,
        its wards: on a ward's own page that ward first, in full, then every
        other ward that can be named;
     2. the chosen district's tag, on its label point or just under or over
        the name already there;
     3. on Counties, the ten counties' names;
     4. the other cities, most wards first. A city with wards is named by
        its wards when every ward in view can be named inside its own ward
        and clear of the rest -- "Ward 3", or "3" alone where "Ward 3" does
        not fit, for at most a third of them -- with the city's own name
        inside the city where there is room (else just above or below it);
        otherwise by its name alone. All of a city's wards in view or none;
     5. the towns, largest first, each only where its name fits across the
        town (no wider than the town and no taller, give or take 4px);
     6. the unincorporated places, largest first, the same way.
   A town whose label point is out of view while part of it is in view is
   named inside that part. */
function namesLayout(M,V,S){
  const s=V.s,r=S.rootPx,vw=V.vw,vh=V.vh,vb=V.vb,ms=S.measure;
  const X=x=>V.ox+(x-vb[0])*s,Y=y=>V.oy+(y-vb[1])*s,UX=x=>(x-V.ox)/s+vb[0],UY=y=>(y-V.oy)/s+vb[1];
  const here=S.here&&M.T.layers.towns.f[S.here]?S.here:null,framed=!!(S.frame&&S.dim);
  const byT={},wardsByT={},els=[];
  const mk=(k,text,l,o)=>{const e=Object.assign({k,text,x:l[0],y:l[1]},o);els.push(e);return e;};
  if(S.layer==="county")for(const c in M.T.layers.county.f)mk("county",c.toUpperCase(),M.T.layers.county.f[c].l,{id:"c:"+c,t:c});
  for(const t in M.T.layers.towns.f)
    byT[t]=mk(t===here?"here":M.city[t]?"city":PLACE.test(t)?"place":"town",t,M.T.layers.towns.f[t].l,{id:"t:"+t,t,out:framed&&t!==S.frame});
  for(const t in M.wardsOf)M.wardsOf[t].forEach((w,i)=>{
    const e=mk("ward",w.words,w.l,{id:"w:"+t+"|"+i,t,g:i,full:w.words,short:w.words.replace(/^Wards? /,""),
      here:t===here&&S.ward!=null&&w.wards.includes(String(S.ward)),out:framed&&t!==S.frame});
    (wardsByT[t]=wardsByT[t]||[]).push(e);});
  const placed=(V.obstacles||[]).map(o=>[o[0]-4,o[1]-4,o[2]+4,o[3]+4]),zbx=placed.length?placed[0]:null;
  const show=new Set();
  const sz=k=>SIZE[k]*r;
  const boxAt=(k,txt,cx,cy)=>{const px=sz(k),w=ms(txt,WEIGHT[k],px)+px/4+1,h=px*1.2;return [cx-w/2,cy-h/2,cx+w/2,cy+h/2];};
  const kOf=e=>e.k==="ward"&&e.here?"hereward":e.k;
  const boxOf=e=>boxAt(kOf(e),e.text,X(e.x),Y(e.y));
  const inView=b=>b[0]>=1&&b[1]>=1&&b[2]<=vw-1&&b[3]<=vh-1;
  const clear=(b,list)=>(list||placed).every(p=>b[2]+GAP<=p[0]||p[2]+GAP<=b[0]||b[3]+GAP<=p[1]||p[3]+GAP<=b[1]);
  const put=(e,b)=>{placed.push(b);show.add(e);e.box=b;};
  const fitsIn=(b,fb)=>(b[2]-b[0])<=(fb[2]-fb[0])*s+4&&(b[3]-b[1])<=(fb[3]-fb[1])*s+4;
  const moveTo=(e,b)=>{e.x=UX((b[0]+b[2])/2);e.y=UY((b[1]+b[3])/2);};
  const inTown=(t,x,y)=>inFeature(M,"towns",t,UX(x),UY(y));
  const nudge=b=>{if(inView(b))return b;const w=b[2]-b[0],h=b[3]-b[1];
    const dx=(b[0]<1?1-b[0]:0)+(b[2]>vw-1?vw-1-b[2]:0),dy=(b[1]<1?1-b[1]:0)+(b[3]>vh-1?vh-1-b[3]:0);
    if(Math.abs(dx)>w*0.5||Math.abs(dy)>h)return b;const n=[b[0]+dx,b[1]+dy,b[2]+dx,b[3]+dy];return inView(n)?n:b;};
  /* A town whose own label point lies outside the view while part of the
     town is in it: the first of a few points across that part, from its
     middle out, that lies in the town and gives the name room. */
  function relocate(t,e){
    const fb=fbox(M,"towns",t),x0=Math.max(X(fb[0]),0),x1=Math.min(X(fb[2]),vw),y0=Math.max(Y(fb[1]),0),y1=Math.min(Y(fb[3]),vh);
    const b0=boxOf(e),w=b0[2]-b0[0],h=b0[3]-b0[1];
    if(x1-x0<w+4||y1-y0<h+4)return null;
    const cx=(x0+x1)/2,cy=(y0+y1)/2,pts=[];
    for(let i=0;i<5;i++)for(let j=0;j<5;j++){const x=x0+w/2+2+(x1-x0-w-4)*i/4,y=y0+h/2+2+(y1-y0-h-4)*j/4;pts.push([x,y,(x-cx)**2+(y-cy)**2]);}
    pts.sort((a,b)=>a[2]-b[2]);
    for(const [x,y] of pts){if(!inTown(t,x,y))continue;
      const b=[x-w/2,y-h/2,x+w/2,y+h/2];if(inView(b)&&clear(b))return b;}
    return null;
  }
  const st={zoom:+(S.zoom||1).toFixed(2),towns:0,townsInView:0,cities:0,citiesByWards:0,wards:0,wardsShort:0,places:0};
  /* the city's own name: inside the city as near its top as there is room,
     else just above or below it; null when none is in view, false when
     blocked. On a town page's own city, above it first, like a title. */
  function caption(t,c,forced,own){
    const cb=fbox(M,"towns",t),h=sz(kOf(c))*0.8;let first=null;
    const titled=framed&&t===S.frame;
    const outside=()=>{for(const [x,y] of [[X((cb[0]+cb[2])/2),Y(cb[1])-h],[X((cb[0]+cb[2])/2),Y(cb[3])+h]]){
      let b=boxAt(kOf(c),c.text,x,y);
      if(zbx&&!clear(b,[zbx])){const dx=zbx[0]-GAP-b[2];b=[b[0]+dx,b[1],b[2]+dx,b[3]];}
      if(inView(b)&&clear(b)&&clear(b,own))return b;}return null;};
    if(titled){const o=outside();if(o)return o;}
    {const x0=Math.max(X(cb[0]),0),x1=Math.min(X(cb[2]),vw),y0=Math.max(Y(cb[1]),0),y1=Math.min(Y(cb[3]),vh);
      const b0=boxAt(kOf(c),c.text,0,0),w=b0[2]-b0[0],hh=b0[3]-b0[1];
      if(x1-x0>w&&y1-y0>hh){const cx=(x0+x1)/2,pts=[];
        for(let j=0;j<9;j++)for(let i=0;i<9;i++){const x=x0+w/2+(x1-x0-w)*i/8,y=y0+hh/2+(y1-y0-hh)*j/8;pts.push([x,y,j*1e4+Math.abs(x-cx)]);}
        pts.sort((a,b)=>a[2]-b[2]);
        for(const [x,y] of pts){const b=[x-w/2,y-hh/2,x+w/2,y+hh/2];
          if(!inView(b)||!inTown(t,x,y)||!inTown(t,b[0]+2,y)||!inTown(t,b[2]-2,y))continue;
          if(clear(b)&&clear(b,own))return b;}}}
    const cx=(Math.max(X(cb[0]),0)+Math.min(X(cb[2]),vw))/2;
    const at=[[X((cb[0]+cb[2])/2),Y(cb[1])-h],[X((cb[0]+cb[2])/2),Y(cb[3])+h],[cx,Math.max(Y(cb[1]),0)+h+2],[cx,Math.min(Y(cb[3]),vh)-h-2]];
    for(const [x,y] of at){
      let b=boxAt(kOf(c),c.text,x,y);
      if(zbx&&!clear(b,[zbx])){const dx=zbx[0]-GAP-b[2];b=[b[0]+dx,b[1],b[2]+dx,b[3]];}
      if(!inView(b))continue;first=first||b;
      if((forced||clear(b))&&clear(b,own))return b;}
    return forced?first:false;
  }
  /* A city by its wards. partial (the chosen or the page's own city): every
     ward in view that can be named is; otherwise all of them in view or
     none. skip: a ward already named (a ward's own page). */
  function cityByWards(t,partial,skip){
    const ws=wardsByT[t]||[],groups=M.wardsOf[t]||[];if(ws.length<2)return false;
    const c=byT[t],full=()=>ws.forEach(x=>{if(x!==skip)x.text=x.full;});
    const own=[],done=[];
    for(const e of ws){
      if(e===skip)continue;
      const fb=groups[e.g].b;let ok=null,seen=false;
      for(const txt of [e.full,e.short]){e.text=txt;const b=boxOf(e);
        if(!inView(b))continue;seen=true;
        if(fitsIn(b,fb)&&clear(b)&&clear(b,own)){ok=b;break;}}
      if(!ok){e.text=e.full;if(!seen||partial)continue;full();return false;}
      own.push(ok);done.push([e,ok]);
    }
    if(!done.length&&!skip){full();return false;}
    // a ward's number alone reads as a ward only beside wards named in full
    if(!partial&&done.filter(([e])=>e.text!==e.full).length>Math.floor(done.length/3)){full();return false;}
    const cap=caption(t,c,partial,own);
    if(!cap&&!partial){full();return false;}
    if(cap){moveTo(c,cap);put(c,cap);}
    done.forEach(([e,b])=>{moveTo(e,b);put(e,b);if(e.text!==e.full)st.wardsShort++;});
    st.citiesByWards++;st.wards+=done.length+(skip?1:0);return true;
  }
  let tag=null;
  function placeTag(){
    const p=S.picked;if(!p||!(TINTED[p[0]]||p[0]==="float")||!M.T.layers[p[0]].f[p[1]])return;
    const f=M.T.layers[p[0]].f[p[1]],text=tagWords(p[0],p[1]),px=sz("tag"),w=ms(text,WEIGHT.tag,px)+px*1.1,h=px*1.75;
    const cx=X(f.l[0]),cy=Y(f.l[1]);
    for(const dy of [0,h*0.5+px*0.9,-(h*0.5+px*0.9),h+px*1.2,-(h+px*1.2)]){
      const b=[cx-w/2,cy+dy-h/2,cx+w/2,cy+dy+h/2];
      if(inView(b)&&clear(b)){placed.push(b);tag={id:"tag",k:"tag",text,x:UX(cx),y:UY(cy+dy),box:b,w:w/s,h:h/s};return;}}
  }
  // 1 and 2. the chosen town, or the page's own; then the tag
  const hereE=here&&byT[here];
  if(hereE&&M.wardsOf[here]){
    const hw=S.ward!=null?(wardsByT[here]||[]).find(e=>e.here):null;
    if(hw){const b=nudge(boxOf(hw));moveTo(hw,b);put(hw,b);}
    if(!cityByWards(here,true,hw)){
      let b=nudge(boxOf(hereE));if(!inView(b)){const rb=relocate(here,hereE);if(rb)b=rb;}
      if(hw){const cap=caption(here,hereE,true,placed.slice(1));if(cap)b=cap;}
      if(inView(b)&&clear(b)){moveTo(hereE,b);put(hereE,b);}
    }
    placeTag();
  }else{
    if(hereE){let b=nudge(boxOf(hereE));if(!inView(b)){const rb=relocate(here,hereE);if(rb)b=rb;}
      if(inView(b)&&clear(b)){moveTo(hereE,b);put(hereE,b);}}
    placeTag();
  }
  // 3. counties
  els.filter(e=>e.k==="county").forEach(e=>{const b=boxOf(e);if(inView(b)&&clear(b))put(e,b);});
  // 4. the cities, most wards first
  (M.T.cities||[]).filter(t=>t!==here&&byT[t]).sort((a,b)=>((M.wardsOf[b]||[]).length-(M.wardsOf[a]||[]).length)||a.localeCompare(b)).forEach(t=>{
    // on a town's own page the cities around it are named, never by wards,
    // so "Ward 3" in the veil is never read as the page's own city's
    if(!framed&&cityByWards(t,false,null))return;
    const e=byT[t];e.x=M.T.layers.towns.f[t].l[0];e.y=M.T.layers.towns.f[t].l[1];
    let b=nudge(boxOf(e));if(!inView(b))b=relocate(t,e);
    if(b&&inView(b)&&clear(b)){moveTo(e,b);put(e,b);st.cities++;}});
  // 5 and 6. the towns, then the places, largest first
  const rest=Object.keys(byT).filter(t=>t!==here&&!M.city[t]);
  const vx0=UX(0),vx1=UX(vw),vy0=UY(0),vy1=UY(vh);
  ["town","place"].forEach(k=>rest.filter(t=>byT[t].k===k).sort((a,b)=>M.area[b]-M.area[a]||a.localeCompare(b)).forEach(t=>{
    const e=byT[t],fb=fbox(M,"towns",t);
    if(fb[2]<vx0||fb[0]>vx1||fb[3]<vy0||fb[1]>vy1)return;
    let b=boxOf(e);
    if(!fitsIn(b,fb))return;
    if(k==="town")st.townsInView++;
    b=nudge(b);if(!inView(b)){b=relocate(t,e);if(!b)return;}
    if(clear(b)){moveTo(e,b);put(e,b);if(k==="town")st.towns++;else st.places++;}}));
  const shown=els.filter(e=>show.has(e)).map(e=>({id:e.id,k:kOf(e),t:e.t,text:e.text,x:e.x,y:e.y,box:e.box,
    cls:"nm nm-"+(e.k==="ward"?"ward":e.k)+(e.k==="ward"&&e.here?" is-here":"")+(e.out?" is-out":"")}));
  return {mode:"names",shown,tag,stats:st};
}

/* ---------------------------------------------------- who, in words --- */

function sitting(M,lk,fid){return M.T.who[lk+"|"+fid]||[];}
function seatsOf(M,lk,fid){if(lk==="base"||lk==="float")return M.T.seats[fid]||0;return TINTED[lk]?1:0;}
function fillOf(M,lk,fid){const f=M.T.fill[lk];return f?(f[fid]||""):null;}
/* "Hillsborough 21 elects 2 Democrats" in a title, never by colour alone */
function countWords(ms){
  const c={};ms.forEach(m=>{c[m.p]=(c[m.p]||0)+1;});
  return Object.keys(c).sort((a,b)=>"RDI".indexOf(a)-"RDI".indexOf(b)).map(p=>`${c[p]} ${NOUN[p]||p}${c[p]===1?"":"s"}`).join(", ");
}
/* One person, as the site's chip draws them (.mchip, app.css): the party
   and seat kept as one unit; a councillor or a representative in Congress
   links to their own site, in a new tab (D20). */
function chip(m){
  const p=esc(letterOf(m.p));
  if(m.u)return `<span class="mchip p-${p}"><a class="gmout" href="${esc(m.u)}" target="_blank" rel="noopener">${esc(m.n)} <span class="mtag">(${p})</span><span class="gmvh"> (opens in a new tab)</span></a></span>`;
  const full=String(m.n||""),tag=full.match(/^(.*\S)\s+(\([^()]*\))$/);
  const who=tag?`${esc(tag[1])} <span class="mtag">${esc(tag[2])}</span>`:esc(full);
  return `<span class="mchip p-${p}">${m.s?`<a href="/legislator/${esc(m.s)}.html">${who}</a>`:who}</span>`;
}
/* "Dover (Ward 1, Ward 2, Ward 3)" once, rather than the city ten times,
   each ward its own link with its capital (the person, 10 October 2026) */
function wardsText(list){
  const by={};list.forEach(([t,w])=>(by[t]=by[t]||[]).push(w));
  return Object.entries(by).map(([t,ws])=>{
    if(ws.length===1&&ws[0]==="0")return `<a href="/town/${slugOf(t)}.html">${esc(t)}</a>`;
    return `${esc(t)} (`+ws.sort((a,b)=>a-b).map(w=>`<a href="/town/${slugOf(t,w)}.html">Ward ${esc(w)}</a>`).join(", ")+")";
  }).join("; ");
}

/* --------------------------------------------------------------- mount --- */

let N=0;
function el(tag,attrs){const e=document.createElementNS(NS,tag);for(const a in attrs)e.setAttribute(a,attrs[a]);return e;}

function mount(root,opts){
  opts=Object.assign({layer:"base",layers:null,labels:DEFAULT_LABELS,flo:false,controls:true,panel:true,list:true,
    legend:true,note:true,zoom:true,frame:null,dim:false,ward:null,town:null,pick:null,data:"/district_map.json",
    prompt:"Choose a district on the map, or type a town in the box above."},opts||{});
  const layersShown=LAYERS.filter(([v])=>!opts.layers||opts.layers.includes(v));
  if(!layersShown.some(([v])=>v===opts.layer))opts.layer=layersShown[0][0];
  if(!LABELS.some(([v])=>v===opts.labels))opts.labels=DEFAULT_LABELS;
  const id="gm"+(++N)+"-";
  root.classList.add("gm");
  if(opts.frame&&opts.dim)root.classList.add("framed");
  if(!opts.panel)root.classList.add("nopanel");
  if(!opts.zoom)root.classList.add("static");
  const seg=(name,label,items,on)=>`<div class="gmseg" role="radiogroup" aria-label="${esc(label)}">${items.map(([v,t])=>
    `<label><input type="radio" name="${id}${name}" value="${v}"${v===on?" checked":""}><span>${esc(t)}</span></label>`).join("")}</div>`;
  root.innerHTML=
    (opts.controls?`<div class="gmctl">
      <div class="gmrow">${layersShown.length>1?seg("ly","Kind of district",layersShown,opts.layer):""}
      <label class="gmflo"><input type="checkbox" class="gmfloin"${opts.flo?" checked":""}> Floterial districts</label></div>
      <div class="gmrow gmlabrow"><span class="gmlabhead" id="${id}lab" aria-hidden="true">Labels</span>${seg("lb","Labels on the map",LABELS,opts.labels)}</div>
    </div>`:"")+
    `<div class="gmstage">`+
    (opts.legend?`<div class="gmkey"><div class="gmleg" role="list" aria-label="What the colours mean"></div>${opts.note?`<p class="gmnote gmexplain"></p>`:""}</div>`:"")+
    `<div class="gmbox">
      <div class="gmwrap" tabindex="0" role="group" aria-label="The map. Arrow keys move it; plus and minus zoom in and out."><svg class="gmsvg" role="img" aria-label="Map of New Hampshire"></svg></div>
      ${opts.zoom?`<div class="gmzoom"><button type="button" class="zo" aria-label="Zoom out">&minus;</button><button type="button" class="zi" aria-label="Zoom in">+</button><button type="button" class="zf" aria-label="Fit the whole map">Fit</button></div>`:""}
      <p class="gmcredit">Boundaries: NH GRANIT, University of New Hampshire (2022). Not for legal use.</p>
    </div>${opts.panel?`<div class="gmpanel" role="status" aria-live="polite"><p class="quiet">${esc(opts.prompt)}</p></div>`:""}</div>`+
    (opts.list?`<details class="gmlist"><summary>Every district, as a list</summary><div class="gmlistbody"></div></details>`:"");
  const svg=root.querySelector("svg"),wrap=root.querySelector(".gmwrap"),panel=root.querySelector(".gmpanel");
  let M=null,layer=opts.layer,mode=opts.labels,picked=null,townPicked=null,zoom=1,vb=null,last=null;
  const api={root,ready:null,select,pickTown,clear,setLayer,setLabels,zoomOn,
    layer:()=>layer,labels:()=>mode,shown:()=>last,model:()=>M};

  api.ready=load(opts.data).then(m=>{M=m;
    vb=[0,0,M.T.w,M.T.h];
    if(opts.frame&&M.T.layers.towns.f[opts.frame]){const b=fbox(M,"towns",opts.frame),w=b[2]-b[0],h=b[3]-b[1],pad=Math.max(w,h)*0.06;
      vb=[b[0]-pad,b[1]-pad,w+2*pad,h+2*pad];}
    svg.setAttribute("viewBox",vb.join(" "));
    svg.setAttribute("preserveAspectRatio","xMidYMid meet");
    wire();draw();list();
    if(opts.town)pickTown(opts.town);
    if(opts.pick)select(layer,opts.pick);
    // the first centring is undone by the page settling (fonts, a finder's
    // list filling in above it): centre again once it has
    if(opts.town&&opts.zoom)(document.fonts?document.fonts.ready:Promise.resolve())
      .then(()=>new Promise(r=>setTimeout(r,250))).then(()=>centreOn(fbox(M,"towns",opts.town)));
    // the labels are measured in their own face, so once more when it loads
    if(document.fonts)document.fonts.ready.then(()=>{measures={};relabel();});
    if(window.ResizeObserver)new ResizeObserver(()=>sizeAll()).observe(wrap);
    root.dataset.ready="1";
    return api;}).catch(e=>{
      const box=root.querySelector(".gmbox");
      if(box)box.insertAdjacentHTML("afterbegin",`<p class="gmfail">The map could not be loaded. Every town's districts are on its own page, listed in <a href="/directory/towns.html">every town and ward</a>.</p>`);
      throw e;});

  /* what a page may keep in its address, or remember */
  function changed(){if(root.dispatchEvent&&typeof CustomEvent==="function")
    root.dispatchEvent(new CustomEvent("gmchange",{detail:{layer,labels:mode,town:townPicked,picked}}));}
  function defs(){
    const d=el("defs",{});
    // equal stripes for every mix of parties this layer has
    const mixes=new Set();
    Object.keys(M.T.layers[layer].f).forEach(f=>{const p=fillOf(M,layer,f);if(p&&p.length>1)mixes.add(p);});
    mixes.forEach(ps=>{const n=ps.length;
      const pt=el("pattern",{id:`${id}mix-${ps}`,class:"stripes",patternUnits:"userSpaceOnUse",width:"60",height:"60",patternTransform:"rotate(45)","data-n":n});
      [...ps].forEach((p,k)=>{const r=el("rect",{x:String(60*k/n),y:"0",width:String(60/n),height:"60"});r.setAttribute("style",`fill:var(--fill-${p})`);pt.appendChild(r);});
      d.appendChild(pt);});
    const v=el("pattern",{id:`${id}vac`,class:"hatch",patternUnits:"userSpaceOnUse",width:"40",height:"40",patternTransform:"rotate(45)"});
    const r1=el("rect",{x:"0",y:"0",width:"40",height:"40"});r1.setAttribute("style","fill:var(--surface)");
    const r2=el("rect",{x:"0",y:"0",width:"8",height:"40"});r2.setAttribute("style","fill:var(--edge)");
    v.appendChild(r1);v.appendChild(r2);d.appendChild(v);
    // the cities' outlines, to draw their ward lines inside them
    const c=el("clipPath",{id:`${id}cities`});
    Object.keys(M.wardsOf).forEach(t=>{if(M.T.layers.towns.f[t])c.appendChild(el("path",{d:featD(M,"towns",t)}));});d.appendChild(c);
    if(layer==="base")Object.keys(M.T.layers.float.f).forEach(f=>{const cp=el("clipPath",{id:`${id}cf-${f}`});cp.appendChild(el("path",{d:featD(M,"float",f)}));d.appendChild(cp);});
    return d;
  }
  /* the floterial's frame, clipped to the inside of its own edge */
  function frameGroup(fid){
    const g=el("g",{"clip-path":`url(#${id}cf-${fid})`}),dd=featD(M,"float",fid),ps=fillOf(M,"float",fid)||"";
    g.appendChild(el("path",{class:"fcase",d:dd}));
    if(ps.length<=1)g.appendChild(el("path",{class:"fdash p-"+(ps||"0"),d:dd}));
    else{g.appendChild(el("path",{class:"fdash alt p-"+ps[0],d:dd}));g.appendChild(el("path",{class:"fdash alt2 p-"+ps[1],d:dd}));}
    return g;
  }
  function draw(){
    svg.textContent="";
    const lk=layer;
    root.classList.toggle("tinted",!!TINTED[lk]);
    svg.setAttribute("aria-label",`Map of New Hampshire's ${LAYER_WORDS[lk]}`+(TINTED[lk]?", each coloured by the party of who represents it":"")+
      (opts.list?". Every one is listed below the map.":"."));
    svg.appendChild(defs());
    const fills=el("g",{});
    Object.keys(M.T.layers[lk].f).forEach(fid=>{
      const ps=fillOf(M,lk,fid);
      const cls=ps===null?"p-0":!ps?"vac":ps.length===1?"p-"+ps:"mix";
      const p=el("path",{class:"f "+cls,d:featD(M,lk,fid),"data-f":fid});
      if(cls==="vac")p.setAttribute("fill",`url(#${id}vac)`);
      if(cls==="mix")p.setAttribute("fill",`url(#${id}mix-${ps})`);
      const t=el("title",{}),ms=sitting(M,lk,fid),seats=seatsOf(M,lk,fid);
      t.textContent=(NAME[lk]?NAME[lk]+" ":"")+label(lk,fid)+(TINTED[lk]?": "+(ms.length?countWords(ms):"vacant")+(seats>ms.length&&ms.length?`, ${seats-ms.length} vacant`:""):"");
      p.appendChild(t);fills.appendChild(p);});
    svg.appendChild(fills);
    if(lk!=="towns")svg.appendChild(el("path",{class:"under",d:meshD(M,"towns")}));
    // a city's ward lines: the 2022 State House lines inside the cities, drawn
    // like the town lines (on State House they are its own lines already)
    if(lk!=="base")svg.appendChild(el("path",{class:"under wardl",d:meshD(M,"base"),"clip-path":`url(#${id}cities)`}));
    svg.appendChild(el("path",{class:"mesh",d:meshD(M,lk)}));
    if(lk==="base"||lk==="towns"){svg.appendChild(el("path",{class:"ctyc",d:meshD(M,"county")}));svg.appendChild(el("path",{class:"cty",d:meshD(M,"county")}));}
    const flog=el("g",{class:"flog"});
    if(lk==="base"&&floOn())Object.keys(M.T.layers.float.f).forEach(f=>flog.appendChild(frameGroup(f)));
    svg.appendChild(flog);
    if(opts.frame&&opts.dim&&M.T.layers.towns.f[opts.frame]){
      const big=Math.max(vb[2],vb[3])*4;
      svg.appendChild(el("path",{class:"outside","fill-rule":"evenodd",
        d:`M${vb[0]-big} ${vb[1]-big}h${vb[2]+2*big}v${vb[3]+2*big}h${-(vb[2]+2*big)}Z`+featD(M,"towns",opts.frame)}));
      svg.appendChild(el("path",{class:"tlinec",d:outlineD(M,"towns",opts.frame)}));
      svg.appendChild(el("path",{class:"tline",d:outlineD(M,"towns",opts.frame)}));
    }
    // the chosen district's outline and its floterial's frame go under the
    // labels, so a frame never cuts through one
    svg.appendChild(el("g",{class:"hi"}));
    svg.appendChild(el("g",{class:"labels","aria-hidden":"true"}));
    svg.appendChild(el("g",{class:"dtag","aria-hidden":"true"}));
    const fw=root.querySelector(".gmflo");if(fw)fw.style.display=lk==="base"?"":"none";
    legend();sizeAll();
    if(picked&&picked[0]===lk)select(lk,picked[1],false);
    else if(picked&&picked[0]==="float"&&lk==="base")select("float",picked[1],false);
    else if(townPicked)pickTown(townPicked,false,false);else picked=null;
  }
  function floOn(){const c=root.querySelector(".gmfloin");return c?c.checked:!!opts.flo;}
  function present(){
    const s=new Set(),tw=opts.frame&&opts.dim;
    Object.keys(M.T.layers[layer].f).filter(fid=>!tw||(M.tw[layer+"|"+fid]||[]).some(([t])=>t===opts.frame)).forEach(fid=>{
      const ps=fillOf(M,layer,fid);if(ps===null)return;if(!ps)s.add("vac");else if(ps.length>1)s.add("mix");[...ps].forEach(p=>s.add(p));});
    return s;
  }
  function legend(){
    const box=root.querySelector(".gmleg"),ex=root.querySelector(".gmexplain");if(!box||!M)return;
    const say=h=>{if(ex)ex.innerHTML=h;};
    if(!TINTED[layer]){
      box.innerHTML="";
      say(layer==="county"
        ?"<b>Counties are not coloured by party.</b> Each elects eight officers of its own (three commissioners, a sheriff, an attorney, a treasurer and two registers), several of them on both parties&rsquo; tickets, so no one official&rsquo;s party could stand for a county. Choose one to see its State House delegation."
        :"<b>Towns are not coloured.</b> This layer is for finding a place: choose a town to see every district it votes in.");
      return;}
    const s=present(),k=(cls,txt)=>`<span class="k" role="listitem"><span class="sw ${cls}" aria-hidden="true"></span>${txt}</span>`;
    let h=k("p-R",PARTY.R)+k("p-D",PARTY.D);
    if(s.has("I"))h+=k("p-I",PARTY.I);
    if(s.has("mix"))h+=k("mix","Members of both parties");
    // "Vacant", the person's word (8 October, midday). The hatch is drawn
    // only where every seat is vacant; a district with one seat of two filled
    // takes its sitting member's colour, and its panel says "2 seats · 1 vacant".
    if(s.has("vac"))h+=k("vac","Vacant");
    if(layer==="base"&&floOn())h+=`<span class="k" role="listitem"><span class="sw frame p-R" aria-hidden="true"></span><span class="sw frame p-D" aria-hidden="true"></span>Floterial district, framed in its members&rsquo; party</span>`;
    box.innerHTML=h;
    let e="";
    if(s.has("mix"))e+="<b>Both colours means members of both parties</b>, drawn evenly whatever the count. ";
    if(layer==="base")e+="A floterial district (neighbouring districts that elect extra members together) is "+(floOn()?"framed in its members&rsquo; party. ":"outlined when you choose a district or turn on Floterial districts. ");
    if(mode==="names")e+="A district&rsquo;s name and number show when you choose it. ";
    e+="Colour shows who represents a district, not how many people live there.";
    say(e);
  }
  function select(lk,fid,say=true){
    if(!M||!M.T.layers[lk]||!M.T.layers[lk].f[fid])return;
    picked=[lk,fid];
    svg.querySelectorAll(".f.on").forEach(p=>p.classList.remove("on"));
    const pf=lk===layer?svg.querySelector(`.f[data-f="${CSS.escape(fid)}"]`):null;if(pf)pf.classList.add("on");
    const hi=svg.querySelector(".hi");hi.textContent="";
    if(layer==="base"&&lk==="base"&&!floOn()&&M.flo[fid])hi.appendChild(frameGroup(M.flo[fid]));
    if(layer==="base"&&lk==="float"&&!floOn())hi.appendChild(frameGroup(fid));
    hi.appendChild(el("path",{class:"selc",d:outlineD(M,lk,fid)}));
    hi.appendChild(el("path",{class:"sel",d:outlineD(M,lk,fid)}));
    if(townPicked&&!(opts.frame&&opts.dim)&&M.T.layers.towns.f[townPicked])hi.appendChild(el("path",{class:"town",d:outlineD(M,"towns",townPicked)}));
    relabel();
    if(say&&panel)panel.innerHTML=describe(lk,fid);
    if(say)changed();
  }
  /* NOTHING CHOSEN AGAIN: a click on the map's background, off every
     district, or Escape, puts the map back as it opened (the person,
     10 October 2026: "there isn't an easy way to deselect"). A town page's
     own town stays outlined -- that is the page, not a choice. */
  function clear(){
    if(!picked&&!townPicked)return;
    picked=null;townPicked=opts.frame&&opts.dim?townPicked:null;
    svg.querySelectorAll(".f.on").forEach(p=>p.classList.remove("on"));
    const hi=svg.querySelector(".hi");if(hi)hi.textContent="";
    relabel();
    if(panel)panel.innerHTML=`<p class="quiet">${esc(opts.prompt)}</p>`;
    changed();
  }
  function seatLine(lk,fid){
    const ms=sitting(M,lk,fid),seats=seatsOf(M,lk,fid);
    return `<div class="pk">${seats} seat${seats===1?"":"s"}${seats>ms.length?` &middot; ${seats-ms.length} vacant`:""}</div>`+
      (ms.length?`<div class="chips">${ms.map(chip).join("")}</div>`:`<p class="quiet">Every seat is vacant.</p>`);
  }
  function describe(lk,fid){
    const tw=M.tw[lk+"|"+fid]||[];
    let h=`<h4>${esc(NAME[lk]?NAME[lk]+" ":"")}${esc(label(lk,fid))}</h4>`;
    if(lk==="base"||lk==="senate"||lk==="float")h+=seatLine(lk,fid);
    if(lk==="base"&&M.flo[fid]){const f=M.flo[fid];
      h+=`<div class="flobox"><p>Also elects, with its neighbours, <b>floterial district ${esc(label("float",f))}</b>:</p>${seatLine("float",f)}</div>`;}
    if(lk==="exec")h+=`<div class="pk">Executive councillor</div><div class="chips">${sitting(M,lk,fid).map(chip).join("")}</div>`;
    if(lk==="cong")h+=`<div class="pk">US representative</div><div class="chips">${sitting(M,lk,fid).map(chip).join("")}</div>`;
    if(lk==="county"){const n=Object.keys(M.T.who).filter(k=>/^(base|float)\|/.test(k)&&CC[k.split("|")[1].slice(0,2)]===fid).reduce((a,k)=>a+M.T.who[k].length,0);
      h+=`<div class="pk">House delegation &middot; ${n}</div><p class="quiet">The county&rsquo;s state representatives also sit as its county convention, which raises county taxes and makes its appropriations.</p>`;}
    if(lk==="towns")h+=townSummary(fid);
    else h+=`<div class="pk">Towns and wards</div><p class="towns">${wardsText(tw)}</p>`;
    return h;
  }
  function townSummary(t){
    return Object.entries(M.T.places[t].w).map(([w,[b,f,s,c,g]])=>
      `<div class="pk">${esc(t)}${w!=="0"?" Ward "+esc(w):""}</div><p>State House ${esc(label("base",b))}${f?`, and floterial ${esc(label("float",f))}`:""}; State Senate ${esc(s)}; Executive Council ${esc(c)}; US House ${esc(g)}. <a href="/town/${slugOf(t,w)}.html">Who represents ${esc(t)}${w!=="0"?" Ward "+esc(w):""}</a></p>`).join("");
  }
  /* Choose a town: the district holding it in this layer is chosen, the town
     outlined and named first, and the map zoomed to it. Switching layers
     keeps the town. */
  function pickTown(t,say=true,centre=true){
    if(!M||!M.T.places[t])return;
    townPicked=t;
    const w0=Object.values(M.T.places[t].w)[0],c=M.T.places[t].c;
    const fid=layer==="base"?w0[0]:layer==="senate"?w0[2]:layer==="exec"?w0[3]:layer==="cong"?w0[4]:layer==="county"?c:t;
    select(layer,fid,false);
    if(say&&panel)panel.innerHTML=`<h4>${esc(t)}</h4>`+townSummary(t);
    if(opts.zoom&&centre)centreOn(fbox(M,"towns",t));
    if(say)changed();
  }
  function setLayer(lk){
    if(!layersShown.some(([v])=>v===lk))return;
    layer=lk;const r=root.querySelector(`input[name="${id}ly"][value="${lk}"]`);if(r)r.checked=true;
    if(picked&&picked[0]!==lk&&!(picked[0]==="float"&&lk==="base"))picked=null;
    draw();list();
    if(panel&&!picked)panel.innerHTML=townPicked?`<h4>${esc(townPicked)}</h4>`+townSummary(townPicked):`<p class="quiet">${esc(opts.prompt)}</p>`;
    changed();
  }
  function setLabels(m){
    if(!LABELS.some(([v])=>v===m))return;
    mode=m;const r=root.querySelector(`input[name="${id}lb"][value="${m}"]`);if(r)r.checked=true;
    legend();relabel();changed();
  }

  /* ---- the view: zoom, scroll and the labels laid out over it ---- */
  function scale(){return Math.min(svg.clientWidth/vb[2],svg.clientHeight/vb[3])||0.05;}
  function rootPx(){return parseFloat(getComputedStyle(document.documentElement).fontSize)||16;}
  let measures={};
  function measure(txt,weight,px){
    const fam=getComputedStyle(svg).fontFamily,key=weight+"|"+px+"|"+fam;let m=measures[key];
    if(!m){const c=document.createElement("canvas").getContext("2d");c.font=weight+" "+px+"px "+fam;m=measures[key]={c,w:{}};}
    return m.w[txt]??(m.w[txt]=m.c.measureText(txt).width);
  }
  function view(){
    const s=scale(),w=wrap.getBoundingClientRect(),obstacles=[];
    const zb=root.querySelector(".gmzoom");
    if(zb){const a=zb.getBoundingClientRect();obstacles.push([a.left-w.left,a.top-w.top,a.right-w.left,a.bottom-w.top]);}
    return {vb,s,ox:(svg.clientWidth-vb[2]*s)/2-wrap.scrollLeft,oy:(svg.clientHeight-vb[3]*s)/2-wrap.scrollTop,
      vw:wrap.clientWidth,vh:wrap.clientHeight,obstacles};
  }
  /* Lines, stripes and hatching keep their width on screen at every zoom,
     and the labels their size. */
  function sizeAll(){
    if(!M||!vb)return;
    const s=scale(),r=rootPx();
    Object.keys(SIZE).forEach(k=>svg.style.setProperty("--n-"+k,(SIZE[k]*r/s)+"px"));
    const st=(+getComputedStyle(root).getPropertyValue("--stripe")||4)*2/s;
    svg.querySelectorAll("pattern.stripes").forEach(p=>{const n=+p.dataset.n;p.setAttribute("width",st);p.setAttribute("height",st);
      p.querySelectorAll("rect").forEach((rr,k)=>{rr.setAttribute("x",st*k/n);rr.setAttribute("width",st/n);rr.setAttribute("height",st);});});
    const hs=6/s;svg.querySelectorAll("pattern.hatch").forEach(p=>{p.setAttribute("width",hs);p.setAttribute("height",hs);
      const [a,b]=p.querySelectorAll("rect");a.setAttribute("width",hs);a.setAttribute("height",hs);b.setAttribute("width",1.25/s);b.setAttribute("height",hs);});
    relabel();
  }
  function relabel(){
    if(!M||!vb)return;
    const g=svg.querySelector("g.labels"),tg=svg.querySelector("g.dtag");if(!g||!tg)return;
    last=layout(M,view(),{mode,layer,here:opts.frame||townPicked,ward:opts.ward,frame:opts.frame,dim:opts.dim,
      picked:mode==="names"?picked:null,rootPx:rootPx(),measure,zoom});
    g.textContent="";
    last.shown.forEach(l=>{const t=el("text",{class:l.cls,x:l.x,y:l.y});t.textContent=l.text;g.appendChild(t);});
    tg.textContent="";
    if(last.tag){const s=scale(),b=last.tag;
      tg.appendChild(el("rect",{class:"tagr",x:b.x-b.w/2,y:b.y-b.h/2,width:b.w,height:b.h,rx:3/s}));
      const t=el("text",{class:"tagt",x:b.x,y:b.y});t.textContent=b.text;tg.appendChild(t);}
    root.dataset.labels=mode;root.dataset.shown=last.shown.length;
  }
  function centreOn(bb){
    // the box at about 45% of the view, whichever way the view is shaped
    const k0=Math.min(wrap.clientWidth/vb[2],wrap.clientHeight/vb[3]),w=bb[2]-bb[0]||1,h=bb[3]-bb[1]||1;
    setZoom(Math.max(1,Math.min(12,0.45*Math.min(wrap.clientWidth/(w*k0),wrap.clientHeight/(h*k0)))));
    const s=scale(),ox=(svg.clientWidth-vb[2]*s)/2,oy=(svg.clientHeight-vb[3]*s)/2;
    wrap.scrollLeft=ox+((bb[0]+bb[2])/2-vb[0])*s-wrap.clientWidth/2;
    wrap.scrollTop=oy+((bb[1]+bb[3])/2-vb[1])*s-wrap.clientHeight/2;
    relabel();
  }
  function setZoom(z){zoom=Math.max(1,Math.min(12,z));svg.style.width=(zoom*100)+"%";svg.style.height=(zoom*100)+"%";sizeAll();}
  function zoomAt(next,cx,cy){const r=wrap.getBoundingClientRect();const ox=cx===undefined?r.width/2:cx-r.left,oy=cy===undefined?r.height/2:cy-r.top;
    const k=Math.max(1,Math.min(12,next))/zoom;const sx=(wrap.scrollLeft+ox)*k-ox,sy=(wrap.scrollTop+oy)*k-oy;setZoom(zoom*k);wrap.scrollLeft=sx;wrap.scrollTop=sy;relabel();}
  /* zoom to z with town t in the middle of the view (for a page's address,
     and for the screenshots) */
  function zoomOn(t,z){
    if(!M||!M.T.layers.towns.f[t])return null;
    const bb=fbox(M,"towns",t);setZoom(z);
    const s=scale(),ox=(svg.clientWidth-vb[2]*s)/2,oy=(svg.clientHeight-vb[3]*s)/2;
    wrap.scrollLeft=ox+((bb[0]+bb[2])/2-vb[0])*s-wrap.clientWidth/2;
    wrap.scrollTop=oy+((bb[1]+bb[3])/2-vb[1])*s-wrap.clientHeight/2;
    relabel();return {zoom,shown:last&&last.shown.length};
  }
  function wire(){
    root.querySelectorAll(`input[name="${id}ly"]`).forEach(i=>i.addEventListener("change",e=>{if(e.target.checked)setLayer(e.target.value);}));
    root.querySelectorAll(`input[name="${id}lb"]`).forEach(i=>i.addEventListener("change",e=>{if(e.target.checked)setLabels(e.target.value);}));
    const fl=root.querySelector(".gmfloin");if(fl)fl.addEventListener("change",draw);
    const lb=root.querySelector(".gmlistbody");
    if(lb)lb.addEventListener("click",e=>{const b=e.target.closest("button.gmpick");if(!b)return;
      select(b.dataset.l,b.dataset.f);if(opts.zoom)centreOn(fbox(M,b.dataset.l,b.dataset.f));});
    let dragged=false,from=null;
    svg.addEventListener("click",e=>{if(dragged||!opts.panel)return;const p=e.target.closest(".f");if(p)select(layer,p.dataset.f);else clear();});
    // the box around the drawing is background too, and Escape is the keyboard's way
    wrap.addEventListener("click",e=>{if(!dragged&&opts.panel&&e.target===wrap)clear();});
    root.addEventListener("keydown",e=>{if(e.key==="Escape"&&opts.panel&&(picked||townPicked)){clear();}});
    if(!opts.zoom)return;
    // a pan changes which labels are in view, so the rule is run again
    let queued=false;
    wrap.addEventListener("scroll",()=>{if(queued)return;queued=true;requestAnimationFrame(()=>{queued=false;relabel();});},{passive:true});
    wrap.addEventListener("wheel",e=>{e.preventDefault();zoomAt(zoom*(e.deltaY<0?1.15:1/1.15),e.clientX,e.clientY);},{passive:false});
    wrap.addEventListener("pointerdown",e=>{dragged=false;if(e.pointerType==="touch")return;from={x:e.clientX,y:e.clientY,l:wrap.scrollLeft,t:wrap.scrollTop};});
    wrap.addEventListener("pointermove",e=>{if(!from)return;if(Math.abs(e.clientX-from.x)+Math.abs(e.clientY-from.y)>4){dragged=true;wrap.classList.add("dragging");}
      wrap.scrollLeft=from.l-(e.clientX-from.x);wrap.scrollTop=from.t-(e.clientY-from.y);});
    ["pointerup","pointercancel","pointerleave"].forEach(n=>wrap.addEventListener(n,()=>{from=null;wrap.classList.remove("dragging");}));
    // the keyboard: arrows scroll the focused map natively; these zoom
    wrap.addEventListener("keydown",e=>{
      if(e.altKey||e.ctrlKey||e.metaKey)return;
      if(e.key==="+"||e.key==="="){e.preventDefault();zoomAt(zoom*1.4);}
      else if(e.key==="-"||e.key==="_"){e.preventDefault();zoomAt(zoom/1.4);}
      else if(e.key==="0"){e.preventDefault();setZoom(1);}});
    root.querySelector(".zi").onclick=()=>zoomAt(zoom*1.4);
    root.querySelector(".zo").onclick=()=>zoomAt(zoom/1.4);
    root.querySelector(".zf").onclick=()=>setZoom(1);
  }
  /* THE LIST IS THE SAME ANSWER AS TEXT, party letters included, so nothing
     on the map is carried by colour alone; and each district's name is a
     button that chooses it, so the list is the keyboard's way in. */
  function list(){
    const body=root.querySelector(".gmlistbody");if(!body||!M)return;
    const lk=layer==="towns"?"county":layer,fs=Object.keys(M.T.layers[lk].f);
    const groups={};
    const all=lk==="base"?fs.concat(Object.keys(M.T.layers.float.f).map(f=>"~"+f)):fs;
    all.forEach(f=>{const g=lk==="base"?CC[f.replace("~","").slice(0,2)]:"";(groups[g]=groups[g]||[]).push(f);});
    const num=f=>parseInt(f.replace(/^\D+/,""),10)||0;
    body.innerHTML=Object.keys(groups).sort().map(g=>{
      const items=groups[g].sort((a,b)=>(a[0]==="~")-(b[0]==="~")||num(a)-num(b)||a.localeCompare(b)).map(f0=>{
        const isF=f0[0]==="~",f=f0.replace("~",""),l2=isF?"float":lk;
        const tw=M.tw[l2+"|"+f]||[],ms=sitting(M,l2,f),seats=seatsOf(M,l2,f);
        const who=ms.length?ms.map(m=>esc(m.n.replace(/\s+\([^()]*\)$/,""))+` (${esc(letterOf(m.p))})`).join(", "):"";
        const vac=(TINTED[l2]||l2==="float")&&seats>ms.length?` (${seats-ms.length} of ${seats} vacant)`:"";
        return `<li><button type="button" class="gmpick" data-l="${l2}" data-f="${esc(f)}">${isF?"Floterial ":""}${esc(label(l2,f))}</button>${who?": "+who:""}${vac}. <span class="quiet">${tw.length} town${tw.length===1?"":"s"} and wards</span></li>`;}).join("");
      return g?`<details class="cgrp"><summary>${esc(g)} &middot; ${groups[g].length}</summary><ul>${items}</ul></details>`:`<ul>${items}</ul>`;}).join("");
  }
  return api;
}

const GRMap={mount,load,model,layout,numbersLayout,namesLayout,inFeature,fbox,LABELS,DEFAULT_LABELS,LAYERS,SIZE,WEIGHT,GAP};
if(typeof window!=="undefined")window.GRMap=GRMap;
if(typeof module!=="undefined"&&module.exports)module.exports=GRMap;
})();
