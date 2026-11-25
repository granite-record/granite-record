
(function(){
  "use strict";
  var G=typeof window!=="undefined"?window:globalThis;

  // ==== THE CORE, which touches no page ======================================
  function setOf(ix,id){
    var s=(ix&&ix.sets)||[];
    for(var i=0;i<s.length;i++) if(s[i].id===id) return s[i];
    return null;
  }
  // The sets that hold anything, in the index's order.
  function setsOf(ix){ return ((ix&&ix.sets)||[]).filter(function(s){ return yearsOf(s).length>0; }); }
  // A set's years, newest first.
  function yearsOf(set){ return Object.keys((set&&set.years)||{}).sort().reverse(); }
  // The year to show: the one asked for where the set has it, else its newest.
  function pickYear(set,want){ var ys=yearsOf(set); return ys.indexOf(String(want))>=0?String(want):(ys[0]||""); }
  function docsOf(set,year){ return ((set&&set.years)||{})[year]||[]; }
  // AN ADDRESS IS NEVER MADE HERE: it is the chamber's prefix and the rest of
  // the address as the record holds it, or the whole address where the record
  // holds one that does not begin with the prefix.
  function hrefOf(ix,set,doc){
    var t=String((doc&&doc[1])||"");
    if(!t) return "";
    return /^https:\/\//.test(t)?t:String(((ix&&ix.base)||{})[set.chamber]||"")+t;
  }
  function esc(s){
    return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }
  function options(values,labels,chosen){
    return values.map(function(v,i){
      return '<option value="'+esc(v)+'"'+(String(v)===String(chosen)?" selected":"")+">"+esc(labels[i])+"</option>";
    }).join("");
  }
  // What the picker shows for a choice: the set, the year it settles on, the
  // document, the address the button takes and the two lines said about it.
  function state(ix,setId,year,at){
    var sets=setsOf(ix), set=setOf(ix,setId);
    if(!set||!yearsOf(set).length) set=sets[0]||null;
    if(!set) return null;
    var ys=yearsOf(set), y=pickYear(set,year), docs=docsOf(set,y);
    var i=+at; if(!(i>=0&&i<docs.length)) i=0;
    var doc=docs[i]||null, n=docs.length;
    return {set:set, sets:sets, years:ys, year:y, docs:docs, at:i, doc:doc,
            href:doc?hrefOf(ix,set,doc):"",
            chosen:doc?set.one+", "+doc[0]:"",
            name:doc?"Open the PDF: "+set.one+", "+doc[0]+", at the General Court":"Open the PDF",
            count:n+" "+(n===1?set.one:set.name)+" for "+y+
                  (ys.length>1?"; the list runs "+ys[ys.length-1]+" to "+ys[0]+".":".")};
  }
  G.GRDOCS={setOf:setOf, setsOf:setsOf, yearsOf:yearsOf, pickYear:pickYear, docsOf:docsOf,
            hrefOf:hrefOf, options:options, state:state};

  // ==== THE PAGE ===================================================================
  if(typeof document==="undefined") return;
  var sec=document.getElementById("cdocs");
  if(!sec||!sec.querySelector) return;
  function $(id){ return document.getElementById(id); }
  var form=$("cdpick"), selSet=$("cdset"), selYear=$("cdyear"), selDoc=$("cddoc"),
      open=$("cdopen"), stat=$("cdstat"), now=$("cdnow");
  if(!form||!selSet||!selYear||!selDoc||!open) return;
  var IX=null, LOADING=false, FAILED=false, ASKED=false;

  // The pickers come up. Without script, and on the day the list will not
  // load, the newest of each kind and the directory under the box are the
  // way in: every document of every year is a plain link there. (Under the
  // schedule, until 25 November 2026, the box had a list of the years that
  // the pickers took the place of; on the list page the directory is that.)
  form.hidden=false;

  // THE STATUS LINE SPEAKS ONLY TO A READER WHO HAS COME TO THE PICKERS. It
  // is a live region, and the list is fetched when the box is merely near:
  // at the top of the list page that is as the page loads, as it was on a
  // quiet week under the schedule, where "36 House Calendars for 2026" was
  // then read out to somebody who had asked for nothing. ASKED is set by a
  // focus on a picker or a touch on one; until then nothing is said, and
  // after it the line says what a change of picker brought.
  function say(t){ if(stat&&stat.textContent!==t) stat.textContent=t; }
  // `from` is the picker that changed -- "set", "year", "doc" -- or "all" when
  // the list has just arrived. Only the pickers after it are filled again, so
  // the one under the reader's hand is never rewritten. Until the list has
  // come each picker holds one choice, the one the button opens, and there is
  // nothing to draw.
  function draw(from){
    var s=state(IX,selSet.value,selYear.value,from==="doc"?selDoc.value:0);
    if(!s) return;
    if(from==="all")
      selSet.innerHTML=options(s.sets.map(function(x){ return x.id; }),s.sets.map(function(x){ return x.name; }),s.set.id);
    if(from==="all"||from==="set") selYear.innerHTML=options(s.years,s.years,s.year);
    if(from!=="doc")
      selDoc.innerHTML=options(s.docs.map(function(_d,i){ return i; }),s.docs.map(function(d){ return d[0]; }),s.at);
    selSet.value=s.set.id; selYear.value=s.year; selDoc.value=String(s.at);
    // THE BUTTON IS A LINK, kept in step with the pickers: Enter, a middle
    // click, "open in new tab" and "copy link" all do what they say, and
    // nothing leaves the page because a picker changed.
    if(s.href){ open.setAttribute("href",s.href); open.setAttribute("aria-label",s.name); }
    if(now) now.textContent=s.chosen;
    if(from==="set"||from==="year"||(from==="all"&&ASKED)) say(s.count);
  }
  // Without the list the box is what it is without script -- the newest of
  // each kind, over the directory -- which needs no explaining to a reader
  // who was not in it when the pickers went.
  function fail(){
    FAILED=true; LOADING=false;
    form.hidden=true;
    if(ASKED) say("The list of documents could not be loaded here. Every year is linked below.");
  }
  // `asked` is true where a reader's own act brought the list: only then is
  // the wait said, and what follows it.
  function load(asked){
    if(asked) ASKED=true;
    if(IX||FAILED) return;
    if(asked) say("Loading the list of documents.");
    if(LOADING) return;
    LOADING=true;
    fetch("/calendar/documents.json").then(function(r){
      if(!r.ok) throw new Error("HTTP "+r.status);
      return r.json();
    }).then(function(j){
      if(!setsOf(j).length) throw new Error("empty");
      IX=j; LOADING=false;
      draw("all");
    }).catch(fail);
  }

  selSet.addEventListener("change",function(){ draw("set"); });
  selYear.addEventListener("change",function(){ draw("year"); });
  selDoc.addEventListener("change",function(){ draw("doc"); });
  // Nothing is submitted: Enter in a picker must not reload the page.
  form.addEventListener("submit",function(e){ e.preventDefault(); });

  // THE LIST IS FETCHED WHEN THE BOX IS NEAR, or as soon as a reader heads
  // for it: one file, once. At the top of the list page it is near at once.
  if(typeof IntersectionObserver==="function"){
    var io=new IntersectionObserver(function(es){
      if(es.some(function(e){ return e.isIntersecting; })){ io.disconnect(); load(false); }
    },{rootMargin:"800px 0px"});
    io.observe(sec);
  }else{
    load(false);
  }
  // A reader who reaches for a picker has asked; one who reaches for a link
  // under them has not, and a line appearing above a link as it is pressed
  // would move it from under the finger.
  function reach(e){ load(form.contains(e.target)); }
  sec.addEventListener("focusin",reach);
  sec.addEventListener("pointerdown",reach);
})();
