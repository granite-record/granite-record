
(function(){
  function show(){
    var id=(location.hash||"").slice(1), el=id&&document.getElementById(id);
    if(el&&el.tagName==="DETAILS"){ el.open=true; el.scrollIntoView(); }
  }
  window.addEventListener("hashchange",show);
  show();
})();
