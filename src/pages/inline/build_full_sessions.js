(function(){
  var ctl=document.querySelector(".chamberctl");
  if(!ctl)return;
  var b=ctl.dataset.body,term=ctl.querySelector(".chterm"),sort=document.querySelector(".chsort"),
      list=document.querySelector(".chdays"),count=document.querySelector(".chcount"),
      word=b==="S"?"Senate":"House",cache={};
  function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function plural(n,w){return n.toLocaleString("en-US")+" "+w+(n===1?"":"s");}
  function long(d){return typeof dateWords==="function"?dateWords(d):d;}
  function journal(j){var m=String(j||"").match(/^(HJ|SJ)\s*0*(\d+)/);
    return m?(m[1]==="HJ"?"House Journal ":"Senate Journal ")+m[2]:String(j||"");}
  function day(d){
    var c=d.counts||{},said=[],pl="";
    if(c.bills)said.push(plural(c.bills,"bill"));
    if(c.roll_calls)said.push(plural(c.roll_calls,"roll call"));
    (d.videos||[]).forEach(function(v){
      var pid="c"+String(d.date).replace(/-/g,"")+"_"+String(v).replace(/[^\w-]/g,"");
      pl+='<div class="player" data-player="'+esc(pid)+'"><button type="button" class="pstub" data-title="'
        +esc("Recording of the "+word+", "+long(d.date))+'" data-embed="'+esc(v)+'|0|'+esc(pid)+'">'
        +'<span>'+(typeof icon==="function"?icon("play"):"")+'</span><span>Play the recording</span></button>'
        +'<div class="pbar"><span class="pwho"><b>The '+word+'</b> &middot; '+esc(long(d.date))+'</span>'
        +'<a href="https://www.youtube.com/watch?v='+esc(v)+'" target="_blank" rel="noopener">On YouTube</a></div></div>';
    });
    var links=['<a class="daylink" href="session/'+b+'/'+esc(d.date)+'">The full session day</a>'];
    if(d.journal_url)links.push('<a href="'+esc(d.journal_url)+'">'+esc(journal(d.journal))+' (PDF)</a>');
    return '<details class="cmeet" id="day-'+esc(d.date)+'" data-date="'+esc(d.date)+'">'
      +'<summary><span class="cmwhen"><b>'+esc(long(d.date))+'</b></span>'
      +'<span class="cmcount">'+said.join(" &middot; ")+'</span>'
      +'<span class="cmcaret" aria-hidden="true"></span></summary>'
      +'<div class="cmbody"><p class="cmsaid">'+esc(d.summary||"")+'</p>'
      +(pl?'<div class="cmplay">'+pl+'</div>':'<p class="note">No recording of this day is on file.</p>')
      +'<p class="src">'+links.join(" &middot; ")+'</p></div></details>';
  }
  function line(n,t){
    return plural(n,"day")+" the "+word+" sat in "+esc(t)+", "
      +(sort.value==="old"?"oldest":"newest")+" first. Open a day for what the chamber did and its "
      +"recording; its full page has every bill it took up, in the order the journal prints it, "
      +"and how it voted.";
  }
  function order(){
    var items=[].slice.call(list.children),up=sort.value==="old";
    items.sort(function(x,y){var a=x.dataset.date,c=y.dataset.date;
      return a<c?(up?-1:1):a>c?(up?1:-1):0;});
    items.forEach(function(s){list.appendChild(s);});
    count.innerHTML=line(items.length,term.value);
  }
  function show(t,write){
    if(!cache[t])cache[t]=fetch("/session/"+b+"/"+t+".json").then(function(r){
      if(!r.ok)throw new Error(r.status);return r.json();});
    list.setAttribute("aria-busy","true");
    cache[t].then(function(T){
      list.innerHTML=(T.days||[]).map(day).join("");
      order();
      opened();
      // The Videos tab's, from the same days (app.js, chamberVideos), now
      // or, where app.js has not run yet, when it does (staticVideos).
      window.GR_CHAMBER_TERM=T;
      if(typeof chamberVideos==="function")chamberVideos(T);
      if(write&&history.replaceState)history.replaceState(null,"",
        location.pathname+"?term="+t+location.hash);
    }).catch(function(){
      count.textContent="The session days of "+t+" could not be loaded.";
    }).then(function(){list.removeAttribute("aria-busy");});
  }
  // A day the address names (a session day's trail leads here at
  // #day-<date>) is opened, as a committee's meeting is.
  function opened(){
    var m=/^#day-(\d{4}-\d\d-\d\d)$/.exec(location.hash||"");
    var d=m&&document.getElementById("day-"+m[1]);
    if(d&&d.tagName==="DETAILS"){d.open=true;}
  }
  opened();
  term.addEventListener("change",function(){show(term.value,true);});
  sort.addEventListener("change",order);
  // THE OTHER CHAMBER (build_full_sessions, THE OTHER CHAMBER): its page, at
  // the term chosen here where it sat in it and that is not its newest (its
  // page's own), on Videos from Videos. The select says this page's chamber
  // when the page is shown, coming Back to it included, whatever a browser
  // kept of the choice, so the other can be chosen again.
  var cham=ctl.querySelector(".chbody");
  if(cham){
    var mine=b==="S"?"senate":"house";
    cham.value=mine;
    cham.addEventListener("change",function(){
      var o=cham.options[cham.selectedIndex];
      if(!o||o.value===mine)return;
      var k=String(o.getAttribute("data-terms")||"").split(" ").indexOf(term.value);
      location.href="/session/"+o.value+(/\/videos\/?$/.test(location.pathname)?"/videos":"")
        +(k>0?"?term="+term.value:"");
    });
    addEventListener("pageshow",function(){cham.value=mine;});
  }
  var want=new URLSearchParams(location.search).get("term");
  if(want&&want!==term.value&&[].some.call(term.options,function(o){return o.value===want;})){
    term.value=want;show(want,false);
  }
})();
