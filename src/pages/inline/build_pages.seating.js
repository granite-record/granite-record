/* THE SEATING CHART, MADE USEFUL. Three ways to the same member, because the
   person asked for three: "you can either click the seat or you can click the
   dropdown sorted by number or search."

   The roster under the chart is already in the HTML, in seat order, so a
   reader with no JavaScript has the whole House and every link in it. All
   this does is filter it and join the two halves together.

   A SEAT IS ASKED, NOT FOLLOWED. Tapping one used to navigate straight to the
   member's page, which on a phone meant that finding out who sits somewhere
   cost a page load and a journey back -- and on a chart where seats are a
   thumb's width apart, an accidental one. A tap now names the member, lights
   the seat and lights their row below; the name it gives you is a link, so
   going through is a second, deliberate tap. */
(function(){
  var list=document.getElementById("seatlist");
  if(!list)return;
  var svg=document.querySelector(".seatmap");
  var wrap=document.querySelector(".seatwrap"), dragged=false;
  var note=document.getElementById("seatnote");
  var q=document.getElementById("sq"), go=document.getElementById("sgo");
  var rows=[].slice.call(list.querySelectorAll(".seatrow"));
  var picked=null;          // the chosen seat's circle, or null

  // 4017 is division 4, seat 17, and the plate reads 4-017. The same
  // function lives in seating.py and in app.js; preflight holds all three
  // together.
  function plate(s){
    s=String(s||"");
    return s.length>3 ? s.slice(0,s.length-3)+"-"+s.slice(-3) : s;
  }
  function rowFor(seat){
    return rows.filter(function(r){return r.dataset.seat===seat;})[0];
  }
  // A seat and its row light together, whichever one the reader reached for,
  // so the answer to "where does my rep sit" and "who sits there" is one
  // gesture either way.
  // The Speaker's circle carries no number: the <g> round it and the word
  // "Speaker" does (seating.svg), so choosing the Speaker named him and lit
  // his row and never his chair (the review of 7 October 2026). A circle
  // with no number of its own takes its group's.
  function mark(seat){
    rows.forEach(function(r){r.classList.toggle("on",!!seat&&r.dataset.seat===seat);});
    if(svg)[].forEach.call(svg.querySelectorAll(".seat"),function(c){
      var p=c.parentNode, n=c.getAttribute("data-seat")||
        (p&&p.getAttribute?p.getAttribute("data-seat"):null);
      c.classList.toggle("on",!!seat&&n===seat);});
  }
  /* THE NAME ABOVE THE SEAT (the owner, 29 October 2026): "a name callout
     ABOVE the selected seat, not at the bottom of the screen", a small box
     with the member's name, their party and district, and a triangle that
     points at the seat. It is the term popovers' box (.termpop), above the
     seat, under it where there is no room above inside the chart or the
     screen, never past the chart's sides, and it follows a seat chosen by a
     tap, by the keyboard or from the list, and one the pointer is over. The
     name in it is the link to the member's page, the next Tab stop after a
     seat, as the note's link under the chart was. The note stays for a
     screen reader, saying the same in words the eye does not see, and
     still says what a search has left showing.

     NEVER UNDER THE KEYBOARD (the accessibility sweep of 29 October 2026,
     WCAG 2.4.3). Tab from a seat to the name under the chart, and focus fell
     to the page: the scroll that brought the name into view moved the
     chart from under a resting pointer, and its mouseout wrote the note
     again, taking out the link focus was on. Nothing here writes the
     callout or the note while focus is in the callout, and what is said
     again unchanged is not written again. */
  var stage=document.querySelector(".seatstage")||(wrap&&wrap.parentNode)||null;
  var pop=null, popA=null, popWhat=null, popSeat=null, popFor=null, quiet=null;
  if(stage&&document.createElement){
    pop=document.createElement("div");
    pop.className="termpop seatpop";pop.id="seatpop";pop.hidden=true;
    popA=document.createElement("a");popA.className="spname";
    popA.setAttribute("aria-describedby","seatpopwhat seatpopseat");
    popWhat=document.createElement("span");popWhat.className="spwhat";popWhat.id="seatpopwhat";
    popSeat=document.createElement("span");popSeat.className="spseat";popSeat.id="seatpopseat";
    pop.appendChild(popA);pop.appendChild(popWhat);pop.appendChild(popSeat);
    if(note&&note.parentNode===stage&&stage.insertBefore)stage.insertBefore(pop,note);
    else stage.appendChild(pop);
  }
  function holds(){
    var a=document.activeElement;
    return !!(a&&pop&&a!==pop&&pop.contains(a));
  }
  // Republican, Belknap 6, seat 2-080: what the note says after the name.
  function about(c){
    return [c.getAttribute("data-party"),c.getAttribute("data-dist"),
      tr("sc.seat","seat {plate}",{plate:plate(c.getAttribute("data-seat"))})].filter(Boolean);
  }
  // Above its seat, the arrow at the seat's middle (--arrow); below it where
  // the box would rise past the top of the chart or of the screen; inside the
  // chart's sides. Out of sight while its seat is scrolled out of the chart,
  // unless focus is in it.
  function place(){
    if(!pop||pop.hidden||!popFor||!stage.getBoundingClientRect||!popFor.getBoundingClientRect)return;
    var st=stage.getBoundingClientRect(), b=popFor.getBoundingClientRect(),
        w=wrap&&wrap.getBoundingClientRect?wrap.getBoundingClientRect():st;
    var cx=b.left+b.width/2, cy=b.top+b.height/2;
    var off=cx<w.left||cx>w.left+w.width||cy<w.top||cy>w.top+w.height;
    pop.classList.toggle("gone",off&&!holds());
    var pw=pop.offsetWidth||0, ph=pop.offsetHeight||0, gap=10, edge=8;
    var left=Math.max(edge,Math.min(cx-st.left-pw/2,st.width-pw-edge));
    var below=b.top-gap-ph<Math.max(w.top,0);
    var top=below?b.top+b.height+gap-st.top:b.top-gap-ph-st.top;
    pop.style.left=Math.round(left)+"px";
    pop.style.top=Math.round(top)+"px";
    var arrow=Math.max(14,Math.min(pw-14,cx-st.left-left));
    if(pop.style.setProperty)pop.style.setProperty("--arrow",Math.round(arrow)+"px");
    pop.classList.toggle("below",below);
  }
  var placing=0;
  function soon(){
    if(placing||typeof requestAnimationFrame!=="function"){if(!placing)place();return;}
    placing=requestAnimationFrame(function(){placing=0;place();});
  }
  function show(c){
    if(!pop)return;
    if(!c){pop.hidden=true;popFor=null;return;}
    if(popFor!==c){
      popFor=c;
      popA.href=DATA("legislator/"+c.getAttribute("data-slug"));
      popA.textContent=c.getAttribute("data-name");
      // The name, then "Republican · Belknap 6", then the seat on a
      // line of its own, its number the licence plate's.
      popWhat.textContent=[c.getAttribute("data-party"),c.getAttribute("data-dist")]
        .filter(Boolean).join(" · ");
      popSeat.textContent=tr("sc.seat_line","Seat {plate}",{plate:plate(c.getAttribute("data-seat"))});
    }
    pop.hidden=false;
    place();
  }
  // Built as nodes rather than markup: a member's name is theirs, and it is
  // not going through innerHTML on my say-so.
  function say(preview){
    if(holds())return;
    var c=preview||picked;
    show(c);
    if(!note)return;
    var shown=rows.filter(function(r){return !r.hidden;}).length;
    var words=c?[c.getAttribute("data-name")].concat(about(c)).join(", ")
      :shown===rows.length?"":tr("sc.shown","{n} of {m} representatives",{n:shown,m:rows.length});
    if(note.getAttribute("data-said")===words)return;
    note.setAttribute("data-said",words);
    note.textContent="";
    // A seat's words are a screen reader's alone, the callout's to the eye:
    // the strip shows nothing, so it is drawn as an empty one, the box's foot
    // with no rule (.seatnote.sronly; the review of 29 October 2026).
    if(note.classList)note.classList.toggle("sronly",!!c);
    if(!c){note.textContent=words;return;}
    var sr=document.createElement("span");
    sr.className="sr";sr.textContent=words;
    note.appendChild(sr);
  }
  function centre(c){
    if(!wrap||!c.getBoundingClientRect)return;
    var b=c.getBoundingClientRect(), w=wrap.getBoundingClientRect();
    wrap.scrollLeft+=(b.left+b.width/2)-(w.left+w.width/2);
    wrap.scrollTop +=(b.top+b.height/2)-(w.top+w.height/2);
  }
  function pick(c){
    picked=c||null;
    mark(picked?picked.getAttribute("data-seat"):"");
    say();
    if(!picked)return;
    var row=rowFor(picked.getAttribute("data-seat"));
    // NO JUMP TO THE LIST (the person, 24 September). Choosing a seat used to
    // scroll the page down to its row; the chart's own link, under it, names
    // the member and goes to their page, so the reader stays on the chart.
    // The row is still marked, and still shown if a search had hidden it.
    if(row)row.hidden=false;
    centre(picked);
  }
  function seatByNumber(seat){
    return svg?svg.querySelector('[data-seat="'+seat+'"][data-slug]'):null;
  }

  function draw(){
    var s=(q&&q.value||"").trim().toLowerCase();
    rows.forEach(function(r){
      var hay=(r.dataset.seat+" "+r.dataset.county+" "+r.textContent).toLowerCase();
      r.hidden=!(!s||hay.indexOf(s)>-1);
    });
    // Searching for one person should light their seat without a second
    // gesture; searching for a county should not light an arbitrary one of
    // its twelve.
    var only=rows.filter(function(r){return !r.hidden;});
    if(s&&only.length===1)pick(seatByNumber(only[0].dataset.seat));
    else {picked=null;mark("");say();}
  }
  if(q)q.addEventListener("input",draw);
  if(go)go.addEventListener("change",function(){
    if(go.value)pick(seatByNumber(go.value));
  });

  /* ZOOM, BECAUSE 400 SEATS DO NOT FIT A PHONE. The chart used to be pinned
     to a 680px minimum inside a sideways-scrolling box: on a 390px screen
     that is a seat about five pixels across, which is under half the
     smallest thing a thumb can reliably hit. It is sized by zoom now, and
     zooming in makes a seat a real target.

     IT OPENS ZOOMED TO FIT, ON A PHONE AS EVERYWHERE (the owner, 29 October
     2026, board item 7). A narrow screen used to open zoomed in, 315% at
     390px, so a phone showed a corner of the floor and the reader had to
     find the rest; now every screen opens with the floor at the box's width
     (app.css, .seatmap) -- where the box is shorter than the floor, as on a
     phone held sideways, its foot is a scroll away -- and + or a pinch
     brings a seat up to a thumb's size. Zoom to fit puts it back. The script writes no zoom until
     the reader asks for one, so a chart drawn in a tab not yet open (the
     page opens on Towns) needs nothing waited for. */
  var zoom=1;
  function apply(){ if(svg)svg.style.width=(zoom*100)+"%"; soon(); }
  // ZOOM ABOUT A POINT, not about the top-left corner. Zooming toward the
  // middle of the box moves whatever the reader was looking at out from under
  // them, which on a chart of 400 near-identical circles means losing your
  // place entirely. The content coordinate under the pointer is worked out
  // first and put back under the pointer afterwards.
  function zoomAt(next, cx, cy){
    if(!wrap)return;
    next=Math.max(1,Math.min(6,next));
    if(next===zoom)return;
    var r=wrap.getBoundingClientRect();
    var ox=(cx===undefined?r.width/2:cx-r.left), oy=(cy===undefined?r.height/2:cy-r.top);
    var k=next/zoom;
    var sx=(wrap.scrollLeft+ox)*k-ox, sy=(wrap.scrollTop+oy)*k-oy;
    zoom=next; apply();
    wrap.scrollLeft=sx; wrap.scrollTop=sy;
  }
  function step(by){ zoomAt(zoom*by); if(picked)centre(picked); }

  if(wrap){
    // THE WHEEL ZOOMS over the chart rather than scrolling past it, which is
    // what a reader expects of something they can drag around, and is what
    // was asked for. preventDefault stops the page moving underneath.
    wrap.addEventListener("wheel",function(e){
      // Turned down over a chart that cannot zoom out further -- the fitted
      // chart it opens as -- the wheel scrolls the page, as it would anywhere
      // else (the review of 29 October 2026).
      if(e.deltaY>0&&zoom<=1)return;
      e.preventDefault();
      zoomAt(zoom*(e.deltaY<0?1.12:1/1.12), e.clientX, e.clientY);
    },{passive:false});

    // DRAGGING MOVES THE FLOOR. Only from the background: a drag that starts
    // on a seat would otherwise swallow the tap that chooses it.
    var from=null;
    wrap.addEventListener("pointerdown",function(e){
      dragged=false;
      if(e.pointerType==="touch")return;      // one finger already pans natively
      if(e.target.closest&&e.target.closest("[data-seat]"))return;
      from={x:e.clientX,y:e.clientY,l:wrap.scrollLeft,t:wrap.scrollTop};
      wrap.setPointerCapture(e.pointerId);
      wrap.classList.add("dragging");
    });
    wrap.addEventListener("pointermove",function(e){
      if(!from)return;
      if(Math.abs(e.clientX-from.x)+Math.abs(e.clientY-from.y)>4)dragged=true;
      wrap.scrollLeft=from.l-(e.clientX-from.x);
      wrap.scrollTop =from.t-(e.clientY-from.y);
    });
    ["pointerup","pointercancel"].forEach(function(n){
      wrap.addEventListener(n,function(){from=null;wrap.classList.remove("dragging");});
    });

    // TWO FINGERS PINCH. One finger is left alone so the box still scrolls
    // the way every other scrollable thing on a phone does, and so a reader
    // can still get past the chart to the rest of the page.
    var gap=0, mid=null;
    function spread(t){
      var dx=t[0].clientX-t[1].clientX, dy=t[0].clientY-t[1].clientY;
      return Math.sqrt(dx*dx+dy*dy);
    }
    wrap.addEventListener("touchstart",function(e){
      if(e.touches.length!==2)return;
      gap=spread(e.touches);
      mid={x:(e.touches[0].clientX+e.touches[1].clientX)/2,
           y:(e.touches[0].clientY+e.touches[1].clientY)/2};
    },{passive:true});
    wrap.addEventListener("touchmove",function(e){
      if(e.touches.length!==2||!gap)return;
      e.preventDefault();
      var now=spread(e.touches);
      zoomAt(zoom*(now/gap), mid.x, mid.y);
      gap=now;
    },{passive:false});
    wrap.addEventListener("touchend",function(e){
      if(e.touches.length<2){gap=0;mid=null;}
    },{passive:true});
  }
  var zi=document.getElementById("szin"), zo=document.getElementById("szout"),
      zf=document.getElementById("szfit");
  if(zi)zi.addEventListener("click",function(){step(1.35);});
  if(zo)zo.addEventListener("click",function(){step(1/1.35);});
  if(zf)zf.addEventListener("click",function(){zoomAt(1);});

  // A seat is a circle with a slug on it, not a link -- an <a> inside the SVG
  // would need its own focus and hit area. One handler on the map covers all
  // 400, and Enter or Space does what a tap does, which is what tabindex and
  // role="button" on each circle promise.
  // The Speaker's seat is a <g> with a rect and a label inside it, so a click
  // lands on a child. closest() walks up to whichever node carries the slug,
  // which makes the rostrum behave like the other 399 circles.
  function seatHit(t){
    if(!t||!t.closest)return null;
    var n=t.closest("[data-slug]");
    return n&&n.getAttribute("data-slug")?n:null;
  }
  if(svg){
    svg.addEventListener("click",function(e){
      var c=seatHit(e.target);
      if(c){e.preventDefault();pick(c===picked?null:c);}
    });
    svg.addEventListener("keydown",function(e){
      if(e.key!=="Enter"&&e.key!==" ")return;
      var c=seatHit(e.target); if(!c)return;
      e.preventDefault(); pick(c===picked?null:c);
    });
    /* ONE STOP FOR THE TAB KEY, AND THE ARROW KEYS WITHIN IT. Every seat was
       its own Tab stop: 382 of them between the chart's controls and the
       list under it, from the 6th Tab press to the 387th (the audit of
       2 October 2026, M22). seating.py writes every seat out of the Tab
       order now; this makes one of them the stop -- the first, until a seat
       is chosen or reached -- and the arrow keys walk the seats in the order
       of their numbers, Home and End to the first and the last. That order
       runs the way the chart is drawn: Division 1 on the left to Division 5
       on the right, so Right goes on toward 5 (seating.LEFT_TO_RIGHT). Focus
       on a seat names its member under the chart, as the pointer over it does. */
    var seats=[].slice.call(svg.querySelectorAll("[data-slug]"))
      .filter(function(c){return c.getAttribute("data-slug");});
    var stopAt=function(c){
      seats.forEach(function(s){s.setAttribute("tabindex",s===c?"0":"-1");});
    };
    if(seats.length)stopAt(seats[0]);
    svg.addEventListener("keydown",function(e){
      var c=seatHit(e.target), i=seats.indexOf(c), j=-1;
      if(i<0)return;
      if(e.key==="ArrowRight"||e.key==="ArrowDown")j=Math.min(seats.length-1,i+1);
      else if(e.key==="ArrowLeft"||e.key==="ArrowUp")j=Math.max(0,i-1);
      else if(e.key==="Home")j=0;
      else if(e.key==="End")j=seats.length-1;
      else return;
      e.preventDefault();
      stopAt(seats[j]); seats[j].focus(); centre(seats[j]);
    });
    /* HEARD ON THE BOX ROUND THE CHART, NOT ON THE CHART. Chrome takes an
       <svg> that listens for focus to be something the Tab key stops on, so
       with these two on the svg the chart itself became a stop between Fit
       and the seat: a ring round all 400 seats, drawn where the box clips
       it, and no key that did anything there. And leaving a seat emptied the
       note under the chart -- which holds the link to the member's page, the
       next thing Tab reaches -- while focus was on its way to it, so that
       press landed on nothing and the link could not be reached from a seat
       at all (the review of 2 October 2026). The link is the callout's now
       (29 October 2026), and the callout is left as it is while focus goes
       into it, and put back when focus leaves it: for the list under the
       chart it says again whatever is chosen, and for a seat the seat's own
       focus names its member a moment later. */
    var host=wrap||svg.parentNode;
    var inPop=function(n){return !!(n&&pop&&(n===pop||pop.contains(n)));};
    // A seat of the chart's: the rows of the list under it carry a slug too.
    var onSeat=function(n){var c=seatHit(n);return c&&svg.contains(c)?c:null;};
    host.addEventListener("focusin",function(e){
      var c=seatHit(e.target); if(c){stopAt(c);if(c!==quiet)say(c);}
    });
    host.addEventListener("focusout",function(e){
      if(e.relatedTarget&&(inPop(e.relatedTarget)||(note&&note.contains(e.relatedTarget))))return;
      say();
    });
    if(pop)pop.addEventListener("focusout",function(e){
      if(e.relatedTarget&&(inPop(e.relatedTarget)||onSeat(e.relatedTarget)))return;
      say();
    });
    // Hovering names who is in a seat without choosing it, so a mouse can
    // read the floor quickly; leaving restores whatever was chosen. The
    // pointer can go from a seat onto its callout, and the callout stays
    // (WCAG 1.4.13, hoverable).
    svg.addEventListener("mouseover",function(e){
      var c=seatHit(e.target); if(c)say(c);
    });
    svg.addEventListener("mouseout",function(e){
      if(inPop(e.relatedTarget))return;
      say();
    });
    if(pop)pop.addEventListener("mouseleave",function(e){
      if(onSeat(e.relatedTarget))return;
      say();
    });
    // A TAP ON THE TRIANGLE IS THE SEAT'S UNDER IT (the walk of 30 October
    // 2026). The triangle reaches past the gap onto the top of the seat it
    // points at, and on a phone the callout opens under the finger before
    // the tap lands, so a tap on a seat landed on the triangle and chose
    // nothing: none of 21 seats tried at 390. It stays where it is, the
    // pointer's way from a seat onto the callout over the seats above it,
    // and a tap or a click on it, below or above the box, goes to the seat
    // under it, found with the callout taken out of the way for a moment.
    if(pop)pop.addEventListener("click",function(e){
      if(e.target!==pop||!pop.getBoundingClientRect||!document.elementFromPoint)return;
      var r=pop.getBoundingClientRect();
      if(e.clientY>=r.top&&e.clientY<=r.bottom)return;
      pop.style.pointerEvents="none";
      var c=onSeat(document.elementFromPoint(e.clientX,e.clientY));
      pop.style.pointerEvents="";
      if(c){e.preventDefault();pick(c===picked?null:c);}
    });
    // Escape lets the callout go, and the keyboard stays where it was: on
    // the seat, or back on it from the name (WCAG 1.4.13, dismissible).
    var dismiss=function(e){
      if(e.key!=="Escape"||!pop||pop.hidden)return;
      var c=popFor, back=holds();
      picked=null;mark("");
      if(back&&c&&c.focus){quiet=c;stopAt(c);c.focus();quiet=null;}
      show(null);
      if(note){note.setAttribute("data-said","");note.textContent="";
        if(note.classList)note.classList.remove("sronly");}
    };
    host.addEventListener("keydown",dismiss);
    if(pop)pop.addEventListener("keydown",dismiss);
  }
  // The callout keeps to its seat while the floor is dragged, zoomed or
  // scrolled, and the page is.
  if(wrap)wrap.addEventListener("scroll",soon,{passive:true});
  if(typeof window!=="undefined"&&window.addEventListener){
    window.addEventListener("resize",soon);
    window.addEventListener("scroll",soon,{passive:true});
  }
  // A CLICK ON THE FLOOR ITSELF LETS GO (the person, 24 September): anywhere
  // in the chart that is not a seat deselects whoever was chosen. A drag to
  // pan also ends in a click, so one that moved is not taken for a let-go.
  if(wrap)wrap.addEventListener("click",function(e){
    if(seatHit(e.target))return;
    if(dragged){dragged=false;return;}
    if(picked)pick(null);
  });
  draw();
})();

/* THREE TABS, WHICH ARE THE ORDERING. The person asked for "three tabs for
   ways to sort the legislators, sorted alphabetically by last name, sorting
   by county as they are now, and sorting by seat number", so the ordering is
   a choice a reader makes once rather than a control they have to find. It
   replaced an Order dropdown inside the seat view, which did the same job in
   a place nobody would look for it.

   All three panes are in the HTML and all three are visible until this runs,
   so a reader with no JavaScript gets the whole roster rather than one pane
   and two empty boxes. The first thing this does is hide two of them -- and
   that is also why losing this block is quiet: every pane simply stays open,
   the tabs still look like tabs, and clicking one changes nothing.

   EVERY STRIP OF THEM (the owner's walk of 7 November 2026): the
   Members-Elect tab lists its people under a strip of its own, and each
   strip shows and hides its own panes.

   AND THE VIEW AN ADDRESS NAMES (the walk of 8 November 2026): an address
   naming a heading inside a view -- /officials#of-eld-house, which By
   district's House heading had and By county's has now -- opens that view,
   on arriving and on a hash change, so the tab strip's script lands on a
   heading that is shown, not on one hidden in another view. */
[].forEach.call(document.querySelectorAll(".rtabs"),function(bar){
  var tabs=[].slice.call(bar.querySelectorAll("[role=tab]"));
  if(!tabs.length)return;
  // Written hidden: shown here, so a page without this script has no strip
  // of buttons that do nothing over its views.
  bar.hidden=false;
  function show(id){
    tabs.forEach(function(t){
      var on=t.dataset.pane===id;
      t.setAttribute("aria-selected",String(on));
      t.tabIndex=on?0:-1;
      var pane=document.getElementById(t.dataset.pane);
      if(pane)pane.hidden=!on;
    });
  }
  tabs.forEach(function(t){
    t.addEventListener("click",function(){pick(t.dataset.pane);});
  });
  // Left and right move between tabs, which is what a tablist promises the
  // moment it says role="tab".
  bar.addEventListener("keydown",function(e){
    var i=tabs.indexOf(document.activeElement);
    if(i<0)return;
    var j;
    if(e.key==="ArrowRight")j=(i+1)%tabs.length;
    else if(e.key==="ArrowLeft")j=(i-1+tabs.length)%tabs.length;
    else return;
    e.preventDefault();
    tabs[j].focus(); pick(tabs[j].dataset.pane);
  });
  // The view holding what the address names, and that element; or null.
  function named(){
    var h;
    try{h=decodeURIComponent(location.hash.slice(1));}catch(e){h="";}
    var el=h&&document.getElementById(h);
    for(var i=0;el&&i<tabs.length;i++){
      var p=document.getElementById(tabs[i].dataset.pane);
      if(p&&p.contains(el))return {pane:tabs[i].dataset.pane,el:el};
    }
    return null;
  }
  // A view the reader picks. Where the address names something in another
  // of these views, it names this one now (no new history entry), so a
  // reload or Back opens the view picked and not the one the address named
  // (the review of 8 November 2026); any other address is left as it is.
  function pick(id){
    var a=named();
    show(id);
    if(a&&a.pane!==id&&history.replaceState)
      history.replaceState(null,"",location.pathname+location.search+"#"+id);
  }
  var at=named();
  show(at?at.pane:tabs[0].dataset.pane);
  addEventListener("hashchange",function(){
    var a=named();
    if(!a)return;
    var hid=document.getElementById(a.pane).hidden;
    show(a.pane);
    if(hid&&a.el.scrollIntoView)a.el.scrollIntoView();
  });
});
