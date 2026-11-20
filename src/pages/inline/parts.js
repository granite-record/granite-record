(function(){
  var bar=document.querySelector(".twntabs");
  if(!bar)return;
  var tabs=[].slice.call(bar.querySelectorAll("[role=tab]"));
  if(!tabs.length)return;
  // The tab an address names: a panel's own, or the one holding what it names.
  function named(h){
    if(!h)return null;
    for(var i=0;i<tabs.length;i++)if(tabs[i].dataset.pane===h)return h;
    var el=document.getElementById(h),p=el&&el.closest&&el.closest(".twnpane");
    for(i=0;p&&i<tabs.length;i++)if(tabs[i].dataset.pane===p.id)return p.id;
    return null;
  }
  function hash(){try{return decodeURIComponent(location.hash.slice(1));}catch(e){return "";}}
  // A TAB THAT HAS RETIRED (the owner, 7 November 2026): from 2 December
  // the Officials page's Members-Elect tab hides itself (data-until, judged
  // by the reader's own date as components.js judges it), and an address
  // naming it -- a bookmark, a link someone shared -- opened six tabs with
  // none chosen and nothing under them. It opens the strip's data-retired
  // tab instead (Legislators, which the tab's intro said "lists who holds
  // each seat"), else the first tab still shown, and says so in the address.
  function gone(t){
    if(!t)return false;
    if(t.hidden)return true;
    var u=t.getAttribute("data-until");
    if(u===null)return false;
    var d=new Date(),day=d.getFullYear()+"-"+("0"+(d.getMonth()+1)).slice(-2)+"-"+
      ("0"+d.getDate()).slice(-2);
    return !/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(u)||day>=u;
  }
  function tab(id){for(var i=0;i<tabs.length;i++)if(tabs[i].dataset.pane===id)return tabs[i];return null;}
  function live(){return tabs.filter(function(t){return !gone(t);});}
  function instead(){
    var r=bar.getAttribute("data-retired");
    if(r&&tab(r)&&!gone(tab(r)))return r;
    var l=live();
    return (l[0]||tabs[0]).dataset.pane;
  }
  // To what a section's address names, once its panel is open.
  function land(){
    var h=hash(),id=named(h);
    if(!id||h===id||gone(tab(id)))return;
    var el=document.getElementById(h);
    if(el)el.scrollIntoView();
  }
  // AGAIN ONCE LOADED AND WHEN THE FONTS ARRIVE, but only on a first arrival
  // and only while the reader has not moved: a reload or Back is put back
  // where the reader was by the browser itself, and a reader who has scrolled
  // on, on a slow connection, was pulled back to the heading 17 seconds later
  // (the review of 6 November 2026).
  var moved=false,restored=false;
  try{var nv=performance.getEntriesByType("navigation")[0];
    restored=!!nv&&(nv.type==="reload"||nv.type==="back_forward");}catch(e){}
  ["wheel","touchmove","keydown","pointerdown"].forEach(function(t){
    addEventListener(t,function(){moved=true;},{passive:true,once:true});
  });
  // A reader sent from a retired tab is shown the strip, once loaded, so
  // that what they were given -- Legislators, chosen -- is in view.
  var sent=false;
  function later(){if(moved||restored)return;if(sent)toStrip();else land();}
  // A LINK TO A TAB from inside another -- County Officials' "by county in
  // Legislators" -- shows that tab; the browser's own jump went to a panel
  // still hidden and left the reader where they were, halfway down a
  // different list. The strip is brought back into view, as the hub's
  // LAND_JS sets it for a tab's address.
  function toStrip(){
    var t=bar.getBoundingClientRect().top;
    if(t<0)window.scrollTo(0,Math.max(0,t+window.scrollY-8));
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
    inView();
  }
  // THE CHOSEN TAB IN VIEW, as the Officials page's strip does: on a phone the
  // strip scrolls, and /town/acworth#services opened Services with its tab
  // past the strip's edge (the town-pages fix of 25 October 2026). The strip
  // moves, 2rem clear of the edge where its shadow is; the page does not.
  function inView(){
    var t=bar.querySelector('[aria-selected="true"]');
    if(!t||bar.scrollWidth<=bar.clientWidth+2)return;
    var a=t.getBoundingClientRect(),b=bar.getBoundingClientRect();
    if(a.left<b.left)bar.scrollLeft-=b.left-a.left+32;
    else if(a.right>b.right)bar.scrollLeft+=a.right-b.right+32;
  }
  tabs.forEach(function(t){
    t.addEventListener("click",function(){show(t.dataset.pane,true);});
  });
  // The keys go round the tabs still shown: a retired one takes no focus.
  // One that retired while it had it -- a page left open past midnight --
  // gives the keys to the tab it hands over to.
  bar.addEventListener("keydown",function(e){
    var on=live(),i=on.indexOf(document.activeElement);
    if(i<0&&tabs.indexOf(document.activeElement)>=0)i=on.indexOf(tab(instead()));
    if(i<0)return;
    var j;
    if(e.key==="ArrowRight")j=(i+1)%on.length;
    else if(e.key==="ArrowLeft")j=(i-1+on.length)%on.length;
    else if(e.key==="Home")j=0;
    else if(e.key==="End")j=on.length-1;
    else return;
    e.preventDefault();
    on[j].focus(); show(on[j].dataset.pane,true);
  });
  addEventListener("hashchange",function(){
    var h=hash(),id=named(h);
    if(!id)return;
    if(gone(tab(id))){show(instead(),true);toStrip();return;}
    show(id,false);
    if(h===id)toStrip();else land();
  });
  bar.hidden=false;
  var first=named(hash());
  if(first&&gone(tab(first))){sent=true;show(instead(),true);}
  else show(first||(live()[0]||tabs[0]).dataset.pane,false);
  addEventListener("load",later);
  // and again once the fonts have their widths
  if(document.fonts&&document.fonts.ready)
    document.fonts.ready.then(function(){inView();later();});
})();
