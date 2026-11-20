(function(){
  var box=document.getElementById("statstud");
  if(!box)return;
  var wrap=box.querySelector(".ssfind"),q=document.getElementById("ssq"),
      said=document.getElementById("ssfn"),none=document.getElementById("ssnone"),
      cards=[].slice.call(box.querySelectorAll(".sscard")),
      groups=[].slice.call(box.querySelectorAll(".ssgrp"));
  wrap.hidden=false;
  function words(s){return String(s||"").toLowerCase().replace(/[^a-z0-9 ]+/g," ").split(" ").filter(Boolean);}
  function run(){
    var w=words(q.value),n=0;
    cards.forEach(function(c){
      var hay=" "+c.getAttribute("data-find")+" ";
      var ok=w.every(function(x){return hay.indexOf(" "+x)>=0;});
      c.hidden=!ok;n+=ok?1:0;
    });
    groups.forEach(function(g){g.hidden=!g.querySelector(".sscard:not([hidden])");});
    none.hidden=!!n;
    said.textContent=w.length?(n===1?"1 committee matches.":n+" committees match."):"";
  }
  q.addEventListener("input",run);
  // Opened by an address that names it, as a committee's page leads here.
  function opened(){if(location.hash==="#statstud")box.open=true;}
  opened();
  window.addEventListener("hashchange",opened);
})();
