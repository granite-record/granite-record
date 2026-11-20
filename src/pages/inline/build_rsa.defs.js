(function(){
  var pop=null,cur=null,wait=0,shut=0,opened=0,touch=false,quiet=false,side="",pressedIn=false,pinned=false,HOLD=500,CUT=400,
      HOME=".rs-art,.lw-read";  // a chapter's text, or the /laws preview of a section's
  // A definition in another chapter is held on this page under data-def.
  function target(a){var d=a.getAttribute("data-def");if(d)return document.getElementById(d);
    var h=a.getAttribute("href")||"",i=h.indexOf("#");return i<0?null:document.getElementById(h.slice(i+1));}
  // The definition's paragraphs, the first without the numbers it opens with.
  function paras(w){
    var ps=[].map.call(w.querySelectorAll("p"),function(p){return p.textContent;});
    if(ps.length)ps[0]=ps[0].replace(/^\s*(?:(?:[IVXLC]+(?:-[a-z]+)?|\d+|[A-H])\.\s*|\([0-9A-Za-z-]+\)\s*)+/,"");
    return ps;}
  function hide(){if(!cur)return;pinned=false;pop.hidden=true;cur.removeAttribute("aria-describedby");cur=null;}
  function el(tag,cls,text){var s=document.createElement(tag);if(cls)s.className=cls;if(text!=null)s.textContent=text;return s;}
  // The words: cut at CUT characters, or whole, a paragraph a line.
  function fill(t,ps,whole){
    t.textContent="";var all=ps.join(" ");
    if(!whole){t.appendChild(el("span","rs-dpp",all.length>CUT+20?all.slice(0,all.lastIndexOf(" ",CUT))+"…":all));return;}
    ps.forEach(function(p){t.appendChild(el("span","rs-dpp",p));});}
  // keep: the side the box opened on, kept when Show more or Show less
  // changes its height, so it never jumps out from under the pointer or the
  // finger that pressed the button (the review of 7 November 2026).
  function place(a,keep){
    var host=pop.offsetParent||a.closest(HOME);if(!host)return;
    var r=a.getBoundingClientRect(),b=host.getBoundingClientRect(),vw=document.documentElement.clientWidth,
        vh=window.innerHeight||document.documentElement.clientHeight||0;
    // A host that scrolls (the /laws preview) is the box's whole world: it
    // opens inside that panel, never wider than it and never past its top or
    // bottom, its words wrapping; a chapter's page is bounded by the screen.
    var lo=8,hi=vw-8,top=8,bot=vh-8,cl=host.clientLeft||0,ct=host.clientTop||0;
    if(window.getComputedStyle&&getComputedStyle(host).overflowX!=="visible"){
      lo=Math.max(lo,b.left+cl+8);hi=Math.min(hi,b.left+cl+host.clientWidth-8);
      top=Math.max(top,b.top+ct+8);bot=Math.min(bot,b.top+ct+host.clientHeight-8);
      pop.style.maxWidth=Math.max(160,hi-lo)+"px";}
    else pop.style.maxWidth="";
    pop.style.maxHeight="";pop.style.left="0px";pop.style.top="0px";
    var p=pop.getBoundingClientRect(),h=p.bottom-p.top;
    // Under the word where it fits; over it where it fits there instead, or
    // where it fits on neither side and there is more room above; no
    // taller than the room on its side, its words scrolling inside it.
    var below=r.bottom+6,roomBelow=bot-below,roomAbove=r.top-6-top;
    if(!keep||!side)side=(vh&&h>roomBelow&&(h<=roomAbove||roomAbove>roomBelow))?"above":"below";
    var room=side==="above"?roomAbove:roomBelow;
    if(vh&&h>room){h=Math.max(room,96);pop.style.maxHeight=h+"px";}
    var y=side==="above"?r.top-6-h:below;
    var x=r.left;
    if(x+(p.right-p.left)>hi)x=hi-(p.right-p.left);
    if(x<lo)x=lo;
    // The pointer: on the edge facing the word, at the word's middle (the
    // line of it the box is nearest) whatever the box was moved by, kept
    // clear of the box's corners.
    var fs=a.getClientRects?a.getClientRects():[],fr=fs.length?fs[side==="above"?0:fs.length-1]:r;
    var bw=p.right-p.left,ax=(fr.left+fr.right)/2-x;
    pop.className="termpop rs-dpop"+(side==="above"?" above":"");
    pop.style.setProperty&&pop.style.setProperty("--arrow",Math.round(Math.max(14,Math.min(Math.max(14,bw-14),ax)))+"px");
    // A host that scrolls (the /laws preview) carries the box with its text.
    pop.style.left=Math.round(x-b.left-cl+(host.scrollLeft||0))+"px";pop.style.top=Math.round(y-b.top-ct+(host.scrollTop||0))+"px";}
  function show(a){
    var w=target(a);if(!w||!a.closest(HOME))return;
    clearTimeout(shut);
    if(cur===a&&pop&&!pop.hidden)return;
    if(cur)hide();
    if(!pop){pop=el("span","termpop rs-dpop");pop.id="rs-dpop";
      pop.addEventListener("pointerenter",function(){clearTimeout(shut);});
      pop.addEventListener("pointerleave",function(e){if(e.pointerType==="mouse"&&!pinned)shut=setTimeout(hide,250);});}
    // Out of the text before its words are read, which can hold it.
    if(pop.parentNode)pop.parentNode.removeChild(pop);
    var ps=paras(w),f=w.getAttribute("data-for"),cite=w.getAttribute("data-cite")||"the definition";
    pop.textContent="";
    var inn=el("span","rs-dpin");pop.appendChild(inn);
    var c=el("span","rs-dpcite",(f?"Defined for "+f+" in ":"Defined in "));c.id="rs-dpcite";
    var go=el("a","",cite);go.href=w.getAttribute("data-href")||a.getAttribute("href");c.appendChild(go);inn.appendChild(c);
    var t=el("span","rs-dptext");t.id="rs-dptext";inn.appendChild(t);fill(t,ps,false);
    if(ps.join(" ").length>CUT+20){
      var m=el("button","rs-dpmore","Show more");m.type="button";m.setAttribute("aria-expanded","false");
      m.setAttribute("aria-controls","rs-dptext");
      m.addEventListener("click",function(){var whole=m.getAttribute("aria-expanded")!=="true";
        fill(t,ps,whole);m.textContent=whole?"Show less":"Show more";m.setAttribute("aria-expanded",whole?"true":"false");
        place(a,true);});
      inn.appendChild(m);}
    a.parentNode.insertBefore(pop,a.nextSibling);
    pop.hidden=false;cur=a;opened=Date.now();a.setAttribute("aria-describedby","rs-dpcite rs-dptext");
    side="";place(a);
  }
  function term(e){return e.target.closest&&e.target.closest("a.rs-tm");}
  function inPop(x){return !!(pop&&x&&pop.contains(x));}
  document.addEventListener("pointerdown",function(e){touch=e.pointerType!=="mouse";pressedIn=inPop(e.target);},true);
  // Escape closes the box, and gives the word the keyboard only where the
  // keyboard was on it or in the box: not from a search box elsewhere.
  document.addEventListener("keydown",function(e){touch=false;pressedIn=false;
    var k=(e.key===" "||e.key==="Spacebar")&&term(e);
    if(k&&target(k)){e.preventDefault();press(k);return;}
    if(e.key==="Escape"&&cur){var a=cur,back=document.activeElement===a||inPop(document.activeElement);hide();
      if(back){quiet=true;a.focus();quiet=false;}}});
  // A press on the word opens the box and keeps it open, wherever the pointer
  // goes, until a press elsewhere, Escape or the word again; it does not
  // navigate (the owner's walk of dry run 8, 8 November 2026). The box's own
  // link still goes to the definition. Enter on the link is a click; Space
  // is given the same meaning here.
  function press(a){
    if(cur===a&&pinned){hide();return;}
    show(a);if(cur===a)pinned=true;}
  document.addEventListener("click",function(e){
    var a=term(e);
    if(a&&target(a)){e.preventDefault();press(a);return;}
    // The box's own link goes to the definition, and the box closes behind it.
    if(cur&&inPop(e.target)&&e.target.closest("a")){hide();return;}
    if(cur&&!inPop(e.target))hide();
  });
  document.addEventListener("pointerover",function(e){
    var a=term(e);if(!a||e.pointerType!=="mouse"||pinned)return;
    clearTimeout(shut);clearTimeout(wait);
    if(cur!==a)wait=setTimeout(function(){show(a);},HOLD);
  });
  document.addEventListener("pointerout",function(e){
    var a=term(e);if(!a||e.pointerType!=="mouse"||(e.relatedTarget&&(a.contains(e.relatedTarget)||inPop(e.relatedTarget))))return;
    clearTimeout(wait);
    if(cur===a&&!pinned&&document.activeElement!==a)shut=setTimeout(hide,250);
  });
  document.addEventListener("focusin",function(e){
    var a=term(e);
    if(a){if(!quiet&&!(pinned&&cur!==a))show(a);}else if(cur&&!inPop(e.target))hide();
  });
  // Focus leaving the word or the box closes it, unless it went into the box
  // or back to the word, or a press inside the box sent it nowhere -- a click
  // on its words, to select them, after pressing Show more.
  document.addEventListener("focusout",function(e){
    if(!cur||pinned||!(e.target===cur||inPop(e.target)))return;
    var to=e.relatedTarget;
    if(to?(inPop(to)||to===cur):pressedIn)return;
    shut=setTimeout(hide,250);
  });
})();
