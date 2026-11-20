(function(){
  // "SHOW ALL N" OPENS THE REST OF ITS OWN LIST (in_place; the person, 7
  // November 2026). A list longer than its data-fold shows that many, with
  // the button under it; pressed, the rest of the same list opens where it
  // is, the button follows it as "Show fewer", and the keyboard goes to the
  // first item it showed. Closing the fold around it folds it again. The
  // Laws page's reader puts a chapter's section into itself after the page
  // has loaded, and asks rsFold of what it put there (LANDING_JS).
  function fold(root){
    [].forEach.call(root.querySelectorAll("ul[data-fold]"),function(ul){
      var n=+ul.getAttribute("data-fold"),li=ul.children;
      if(!(n>0)||li.length<=n||ul.getAttribute("data-folded"))return;ul.setAttribute("data-folded","1");
      var b=document.createElement("button");b.type="button";b.className="rs-all";
      function set(open){for(var i=n;i<li.length;i++)li[i].hidden=!open;
        b.textContent=open?"Show fewer":"Show all "+li.length;b.setAttribute("aria-expanded",open?"true":"false");}
      b.addEventListener("click",function(){var open=b.getAttribute("aria-expanded")!=="true";set(open);
        var a=open&&li[n].querySelector("a");if(a)a.focus();});
      set(false);ul.parentNode.insertBefore(b,ul.nextSibling);
      var d=ul.parentNode.closest&&ul.parentNode.closest("details");
      if(d)d.addEventListener("toggle",function(){if(!d.open)set(false);});
    });}
  window.rsFold=fold;fold(document);
})();
(function(){
  // The sidebar's sections: the one being read marked as the page scrolls
  // past it. ON A PHONE (the person, 11 October 2026: "The index is not
  // accessible on mobile on individual chapters") the list is a bar held at
  // the top of the screen, naming the section being read; it opens over the
  // page, and choosing a section closes it.
  var d=document.querySelector(".rs-sidebox");if(!d)return;
  var narrow=function(){return window.matchMedia&&matchMedia("(max-width:60em)").matches;};
  if(narrow())d.open=false;
  var links={},box=d.querySelector("ol"),cur=null,now=d.querySelector(".rs-now");
  [].forEach.call(d.querySelectorAll("a[href*='#']"),function(a){links[a.getAttribute("href").split("#")[1]]=a;});
  d.addEventListener("click",function(e){if(e.target.closest("a")&&narrow())d.open=false;});
  document.addEventListener("keydown",function(e){if(e.key==="Escape"&&d.open&&narrow()){d.open=false;d.querySelector("summary").focus();}});
  if(!("IntersectionObserver" in window)||!box)return;
  var io=new IntersectionObserver(function(es){es.forEach(function(e){
    if(!e.isIntersecting)return;var a=links[e.target.id];if(!a||a===cur)return;
    if(cur)cur.removeAttribute("aria-current");a.setAttribute("aria-current","location");cur=a;
    if(now){var b=a.querySelector("b");now.textContent=b?b.textContent:a.textContent.split(" ")[0];}
    var li=a.parentNode;if(li.offsetTop<box.scrollTop||li.offsetTop>box.scrollTop+box.clientHeight-40)
      box.scrollTop=li.offsetTop-box.clientHeight/3;});},{rootMargin:"-15% 0px -75% 0px"});
  [].forEach.call(document.querySelectorAll(".rs-sec[id],.rs-repealed[id]"),function(s){io.observe(s);});
})();
