(function(){
  var bar=document.querySelector(".lw-tabs");
  if(!bar)return;
  var tabs=[].slice.call(bar.querySelectorAll("[role=tab]"));
  if(!tabs.length)return;
  function paneOf(h){
    if(!h)return null;
    for(var i=0;i<tabs.length;i++)if(tabs[i].dataset.pane===h)return h;
    var el=document.getElementById(h),p=el&&el.closest(".twnpane");
    return p?p.id:null;
  }
  function show(id,write){
    tabs.forEach(function(t){
      var on=t.dataset.pane===id;
      t.setAttribute("aria-selected",String(on));
      t.tabIndex=on?0:-1;
      var pane=document.getElementById(t.dataset.pane);
      if(pane)pane.hidden=!on;
    });
    if(write&&history.replaceState)
      history.replaceState(null,"",location.pathname+location.search+"#"+id);
  }
  function hash(){try{return decodeURIComponent(location.hash.slice(1));}catch(e){return "";}}
  function land(){
    var h=hash(),id=paneOf(h);
    if(!id||h===id)return;
    var el=document.getElementById(h);
    if(el)el.scrollIntoView();
  }
  tabs.forEach(function(t){
    t.addEventListener("click",function(){show(t.dataset.pane,true);});
  });
  bar.addEventListener("keydown",function(e){
    var i=tabs.indexOf(document.activeElement);
    if(i<0)return;
    var j;
    if(e.key==="ArrowRight")j=(i+1)%tabs.length;
    else if(e.key==="ArrowLeft")j=(i-1+tabs.length)%tabs.length;
    else if(e.key==="Home")j=0;
    else if(e.key==="End")j=tabs.length-1;
    else return;
    e.preventDefault();
    tabs[j].focus(); show(tabs[j].dataset.pane,true);
  });
  addEventListener("hashchange",function(){
    var id=paneOf(hash());
    if(id){show(id,false);land();}
  });
  bar.hidden=false;
  show(paneOf(hash())||tabs[0].dataset.pane,false);
  addEventListener("load",function(){land();});
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(land);
})();
