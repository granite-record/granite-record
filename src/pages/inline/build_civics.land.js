(function(){
  var s=document.querySelector(".r-tabs");
  if(!s)return;
  function land(){
    var h=(location.hash||"").slice(1);
    if(!h||!document.getElementById("tab-"+h))return;
    window.scrollTo(0,Math.max(0,s.getBoundingClientRect().top+window.scrollY-8));
  }
  addEventListener("load",function(){land();setTimeout(land,0);});
})();
