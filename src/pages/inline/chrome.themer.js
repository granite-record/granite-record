/* The control, as the person set it out on 13 September. The page follows the
   reader's system until they choose; the button names the theme on screen,
   Light or Dark, and swaps to the other; the choice is kept, so it is made
   once. There is no Auto to cycle through: following the system is what
   happens before anyone chooses, and a third state was a click nobody asked
   for. A value this control no longer writes ("auto", from the one before)
   reads as no choice.
   It starts hidden and is revealed here, so a reader with JavaScript off is
   not shown a control that cannot do anything -- the stylesheet still
   follows their system, which is the sensible default and needs no script. */
(function(){
  var b=document.getElementById("themer"); if(!b) return;
  var K="gr-theme", r=document.documentElement;
  var mq=window.matchMedia?window.matchMedia("(prefers-color-scheme: dark)"):null;
  function chosen(){ try{ var v=localStorage.getItem(K); return v==="light"||v==="dark"?v:""; }
                     catch(e){ return r.dataset.theme||""; } }
  function shown(){ return chosen()||(mq&&mq.matches?"dark":"light"); }
  function draw(){
    var v=shown();
    // NAME THE DESTINATION, NOT THE STATE. It read "Light" while the page was
    // light, which is a label describing what you are already looking at --
    // so the one thing a reader wants from it, what happens if I press this,
    // was the one thing it did not say. The aria-label has always named the
    // destination; the visible word now agrees with it.
    // AN ICON SINCE 24 SEPTEMBER, at the person's request: a sun or a moon
    // for the theme a press will give, the same destination the word named.
    // The word stays in the markup -- hidden beside the icon on a desktop,
    // shown in the phone's Sections panel, where nothing else says "theme".
    var to=v==="dark"?"light":"dark";
    b.setAttribute("data-to",to);
    var w=b.querySelector(".thword"); if(w) w.textContent=to==="light"?tr("theme.light","Light"):tr("theme.dark","Dark");
    b.title=to==="light"?tr("theme.to_light","Switch to the light theme"):tr("theme.to_dark","Switch to the dark theme");
    b.setAttribute("aria-label",v==="dark"
      ?tr("theme.now_dark","Color theme: dark. Activate to switch to light.")
      :tr("theme.now_light","Color theme: light. Activate to switch to dark."));
  }
  b.hidden=false; draw();
  b.addEventListener("click",function(){
    var next=shown()==="dark"?"light":"dark";
    r.dataset.theme=next;
    try{ localStorage.setItem(K,next); }catch(e){}
    draw();
  });
  // The system changing while nothing is chosen -- a laptop turning to its
  // evening setting -- changes the page through the stylesheet; the label
  // follows it.
  if(mq){ var f=function(){ if(!chosen()) draw(); };
    if(mq.addEventListener) mq.addEventListener("change",f);
    else if(mq.addListener) mq.addListener(f); }
})();
