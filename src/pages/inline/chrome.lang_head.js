(function(){
  var r=document.documentElement,K="gr-lang",here=r.lang||"en",OFFER=__OFFER__,LANGS=__LANGS__;
  function get(k){try{return localStorage.getItem(k)||"";}catch(e){return "";}}
  if(here!=="en")try{localStorage.setItem("gr-lang-seen","1");}catch(e){}
  document.addEventListener("click",function(e){
    var a=e.target&&e.target.closest&&e.target.closest("[data-setlang]");
    if(a)try{localStorage.setItem(K,a.getAttribute("data-setlang"));}catch(x){}
  },true);
  document.addEventListener("change",function(e){
    var s=e.target;if(!s||!s.hasAttribute||!s.hasAttribute("data-footlang"))return;
    var o=s.options[s.selectedIndex];if(!o||o.value===here)return;
    try{localStorage.setItem(K,o.value);}catch(x){}
    location.href=o.getAttribute("data-href");
  });
  if(OFFER.length<2&&here==="en"&&get("gr-lang-seen")!=="1")return;
  window.GR_NOTICE=__NOTICE__;
  var ls=navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||""];
  var browser="",chosen=get(K);
  for(var i=0;i<ls.length&&!browser;i++){var c=String(ls[i]||"").slice(0,2).toLowerCase();
    if(LANGS.indexOf(c)>=0)browser=c;}
  if(LANGS.indexOf(chosen)<0)chosen="";
  var want=chosen||browser||"en";
  window.GR_PREF={here:here,want:want,chosen:chosen,browser:browser};
  r.classList.add("langs");
  var to=r.getAttribute("data-alt-"+want);
  if(want!==here&&to&&(chosen||here==="en")&&to!==location.pathname)
    location.replace(to+location.search+location.hash);
})();
