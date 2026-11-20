(function(){
  var el=document.getElementById("ofmap"),api=null,want=null;
  if(!el)return;
  function mount(){
    if(api||!window.GRMap||el.offsetParent===null)return;
    api=GRMap.mount(el,{layer:"base",layers:["base","senate","exec","cong"]});
    if(want)api.ready.then(function(){api.pickTown(want);});
  }
  addEventListener("DOMContentLoaded",mount);
  var pane=el.closest(".twnpane");
  if(pane&&window.MutationObserver)
    new MutationObserver(mount).observe(pane,{attributes:true,attributeFilter:["hidden"]});
  addEventListener("grtown",function(e){
    want=e.detail;
    if(api)api.ready.then(function(){api.pickTown(want);});else mount();
  });
})();
// THE CHOSEN TAB IN VIEW. Below 1024px the strip scrolls, so an address
// naming the fourth or fifth tab (/officials#executive) opened it with its
// tab half past the strip's edge; the strip is moved to show it, at load and
// whenever a tab is chosen, and the page itself does not move.
(function(){
  var bar=document.querySelector(".oftabs");
  if(!bar)return;
  function shown(){
    var t=bar.querySelector('[aria-selected="true"]');
    if(!t)return;
    var l=t.offsetLeft-bar.offsetLeft,r=l+t.offsetWidth;
    // 2rem clear of the edge, where the strip's shadow says it goes on
    if(l<bar.scrollLeft)bar.scrollLeft=Math.max(0,l-32);
    else if(r>bar.scrollLeft+bar.clientWidth)bar.scrollLeft=r-bar.clientWidth+32;
  }
  shown();
  // and again once the fonts have their widths
  if(document.fonts)document.fonts.ready.then(shown);
  bar.addEventListener("click",function(){setTimeout(shown,0);});
  bar.addEventListener("keydown",function(){setTimeout(shown,0);});
  addEventListener("hashchange",shown);
})();
