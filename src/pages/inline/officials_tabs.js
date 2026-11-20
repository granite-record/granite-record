(function(){
// electMatch is the whole of the matching, so a test can run it alone: an
// item {st, p, ch, hay} against what was typed and chosen; every word typed
// must be in hay ("names | district words | towns"), accents folded and
// apostrophes left out (the hay carries both readings). Its own rules:
// a word under five letters starts a word; rep, sen, the long forms and the
// chip's own "rep.-elect" and "sen.-elect" are left out of a name, and
// before a number name the chamber; "elect" (the
// chip's word) is left out; a number is a district's: after a county word
// ("merr 5", "sd 8") or "district", or alone, it is that number in the
// district part; after "ward" it is a ward of the town named before it;
// after any other word it is the district or that town's ward.
function fold(s){s=String(s==null?"":s).toLowerCase();
  s=s.normalize?s.normalize("NFD").replace(/[\u0300-\u036f]/g,""):s;
  return s.replace(/['‘’ʼ]/g,"");}
// A title is left out of a name; before a number it names the chamber.
var TITLE={rep:"H","rep.":"H",representative:"H",sen:"S","sen.":"S",senator:"S",
  "rep.-elect":"H","rep-elect":"H","representative-elect":"H",
  "sen.-elect":"S","sen-elect":"S","senator-elect":"S"};
// What the chip prints beside the title, and how the record shortens a place.
var ELECT={elect:1,electo:1,electa:1,"electo/a":1};
var LONG={"loc.":"location","pur.":"purchase"};
// The words a district part can begin with: a county, the Senate.
var DW=__DISTRICT_WORDS__;
function own(o,k){return Object.prototype.hasOwnProperty.call(o,k);}
function dword(p){for(var k=0;k<DW.length;k++)if(DW[k].indexOf(p)===0)return true;return false;}
function startsWord(h,w){
  if(w.length>=5)return h.indexOf(w)>=0;
  for(var i=h.indexOf(w);i>=0;i=h.indexOf(w,i+1))
    if(!i||!/[a-z0-9]/.test(h.charAt(i-1)))return true;
  return false;
}
function pairAt(t,pre,n,exact){
  for(var i=0;i+1<t.length;i++)
    if((exact?t[i]===pre:t[i].indexOf(pre)===0)&&t[i+1]===n)return true;
  return false;
}
function threeAt(t,pre,mid,n){
  for(var i=0;i+2<t.length;i++)
    if(t[i].indexOf(pre)===0&&t[i+1]===mid&&t[i+2]===n)return true;
  return false;
}
function electMatch(it,q,st,p,ch){
  if(st&&it.st!==st)return false;
  if(p&&it.p!==p)return false;
  if(ch&&it.ch!==ch)return false;
  var w=fold(q).split(/\s+/).map(function(x){
    x=x.replace(/^[“”"(\[]+|[“”")\],]+$/g,"");x=x.replace(/^([a-z])\.$/,"$1");return own(LONG,x)?LONG[x]:x;
  }).filter(function(x){return x&&/[a-z0-9]/.test(x)&&!own(ELECT,x);});
  // A chip pasted whole ends "(R - SD8)": the party letter is not a name.
  if(w.length>1)w=w.filter(function(x){return (x.length>1||x!==it.p.toLowerCase())&&!/^[a-z](\/[a-z])+$/.test(x);});
  var parts=it.hay.split(" | "),
      dist=(parts.length>2?parts[1]:it.hay).split(" "),
      town=(parts.length>2?parts.slice(2).join(" "):it.hay).split(" "),
      nm=parts.length>2?parts[0]:it.hay,nw=nm.split(" ");
  function named(c,d){return !!c&&nw.indexOf(d)>=0&&startsWord(nm,c);}
  function intown(c,d){return !!c&&pairAt(town,c,d,false);}
  for(var j=0;j<w.length;j++){
    var x=w[j];
    if(own(TITLE,x))continue;
    // The word before, and the one before that, as typed (titles kept).
    var b=j&&!/[0-9]/.test(w[j-1])?w[j-1]:"",
        a=j>1&&!/[0-9]/.test(w[j-2])&&!own(TITLE,w[j-2])?w[j-2]:"";
    if(/^[0-9]+$/.test(x)){
      var t2=j>1&&own(TITLE,w[j-2])?TITLE[w[j-2]]:"",c=j>2&&!/[0-9]/.test(w[j-3])&&!own(TITLE,w[j-3])?w[j-3]:"";
      if(own(TITLE,b)){if(it.ch!==TITLE[b]||!pairAt(dist,"district",x,true))return false;}
      else if(t2&&(b==="district"||dword(b))&&it.ch!==t2)return false;
      else if(b==="ward"&&!named(a,b)){if(!(a?threeAt(town,a,"ward",x):pairAt(town,"ward",x,true)))return false;}
      else if(b==="district"){if(!(a&&dword(a)&&!named(c,a)&&!intown(c,a)?threeAt(dist,a,"district",x):pairAt(dist,"district",x,true)))return false;}
      else if(!b){if(!pairAt(dist,"district",x,true))return false;}
      else if(dword(b)&&!named(a,b)&&!intown(a,b)){if(!pairAt(dist,b,x,false))return false;}
      else if(!pairAt(dist,"district",x,true)&&!threeAt(town,b,"ward",x))return false;
    }else if(/[0-9]/.test(x)){
      if(dist.indexOf(x)<0)return false;
    }else if(!startsWord(it.hay,x))return false;
  }
  return true;
}
if(typeof window!=="undefined")window.electMatch=electMatch;
var bar=document.querySelector(".elfilter");
if(!bar)return;
var panel=bar.parentNode, box=bar.querySelector(".elq"), say=bar.querySelector(".elcount");
var sels={st:bar.querySelector(".elst"),p:bar.querySelector(".elpa"),ch:bar.querySelector(".elch")};
// Every member-elect is in both views; the counts are read from the first.
var rows=[].slice.call(panel.querySelectorAll("[data-st]")).map(function(el){
  return {el:el,st:el.dataset.st,p:el.dataset.p,ch:el.dataset.ch,hay:el.dataset.hay||""};});
var once=rows.filter(function(r){return !!r.el.closest("#pane-elast");});
// The line that counts the whole list is not true of a part of it.
var allLine=panel.querySelectorAll(".elall")[0];
// Races not final have nobody in them to find; a search that finds no one
// and names one says its result is not final (data-nf).
var NF=[];try{NF=JSON.parse(bar.dataset.nf||"[]");}catch(e){}
// A heading's count and a county's: kept as written, and drawn as what is
// shown while a search or a filter is on.
var heads=[].slice.call(panel.querySelectorAll("h2[id^=of-el],.pcol h3")).map(function(h){
  var m=/^(.*?\s\u2014\s)([0-9,]+)$/.exec(h.textContent);
  return m?{h:h,pre:m[1],all:m[2],col:h.parentNode.className==="pcol"?h.parentNode:null,
            s:/senate/.test(h.id||"")}:null;}).filter(Boolean);
var cgrps=[].slice.call(panel.querySelectorAll("details.cgrp")).map(function(d){
  var n=d.querySelector(".ccount");
  return {d:d,n:n,all:n?n.textContent:"",open:d.open};});
function seen(box){return box.querySelectorAll("[data-st]:not(.elout)").length;}
function apply(){
  var q=box.value,st=sels.st.value,p=sels.p.value,ch=sels.ch.value,
      on=!!(q.trim()||st||p||ch),n=0;
  rows.forEach(function(r){r.el.classList.toggle("elout",!electMatch(r,q,st,p,ch));});
  once.forEach(function(r){if(!r.el.classList.contains("elout"))n++;});
  heads.forEach(function(x){
    var c=x.col?seen(x.col):once.filter(function(r){
      return !r.el.classList.contains("elout")&&(r.ch==="S")===x.s;}).length;
    if(x.col)x.col.classList.toggle("elout",!c);
    x.h.textContent=on?x.pre+c:x.pre+x.all;
  });
  cgrps.forEach(function(g){
    var c=seen(g.d);
    g.d.classList.toggle("elout",!c);
    if(g.n)g.n.textContent=on?c:g.all;
    g.d.open=on?c>0:g.open;
  });
  if(allLine)allLine.classList.toggle("elout",on);
  var nfs=[];
  if(!n&&q.trim()&&!st&&!p)NF.forEach(function(x){
    if(electMatch({st:"",p:"",ch:x.ch,hay:x.hay},q,"","",ch))nfs.push(x.say);});
  say.textContent=!on?"":n?bar.dataset.some.replace("{n}",n).replace("{m}",bar.dataset.n)
    :nfs.length&&nfs.length<4?nfs.join(" "):bar.dataset.none;
}
["input","change"].forEach(function(t){
  [box,sels.st,sels.p,sels.ch].forEach(function(c){c.addEventListener(t,apply);});});
bar.hidden=false;
})();
