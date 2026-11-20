(function(){
  // The year of the laws to show, in every chapter at once (record_years).
  var p=document.querySelector(".g-yrp"), sel=p&&p.querySelector(".g-yr");
  if(!sel)return;
  p.hidden=false;
  sel.addEventListener("change",function(){
    var y=sel.value;
    document.querySelectorAll(".g-laws").forEach(function(box){
      var more=box.querySelector(".rs-more"), none=box.querySelector(".g-yrnone"), shown=0;
      box.querySelectorAll("li[data-y]").forEach(function(li){
        li.hidden=!!y&&li.getAttribute("data-y")!==y; if(!li.hidden)shown++; });
      if(more){ if(y){more.open=true;} more.querySelector("summary").hidden=!!y; }
      if(none)none.hidden=!y||shown>0;
    });
    // Passed, not yet in effect: in the year each passed, or under All.
    document.querySelectorAll(".g-pass").forEach(function(box){
      var more=box.querySelector(".rs-more"), shown=0;
      box.querySelectorAll("li[data-y]").forEach(function(li){
        li.hidden=!!y&&li.getAttribute("data-y")!==y; if(!li.hidden)shown++; });
      if(more){ if(y){more.open=true;} more.querySelector("summary").hidden=!!y; }
      box.hidden=!!y&&!shown;
    });
  });
})();
