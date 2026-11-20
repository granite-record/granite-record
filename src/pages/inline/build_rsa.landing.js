(function(){
  var root=document.getElementById("lw");if(!root)return;
  var box=document.getElementById("rsq"),out=document.getElementById("rsout"),dir=document.getElementById("lwdir"),
      read=document.getElementById("lwread"),count=document.getElementById("lwcount");
  var narrow=function(){return window.matchMedia&&matchMedia("(max-width:59.9375em)").matches;};
  var CH=null,HD=null,WD=null,PAGES={};
  function get(u){return fetch(u).then(function(r){return r.ok?r.json():null;});}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c];});}
  function chOf(a){return a.split(":")[0];}
  // A chapter's address is the one its row links (build_rsa.chapter_path),
  // so RSA 404's keeps the slash the host serves it at.
  function link(a){var p=a.split(":"),g=root.querySelector('.lw-ch[data-ch="'+p[0]+'"] > .lw-go');
    return (g?g.getAttribute("href"):"/laws/"+p[0].toLowerCase())+(p[1]?"#s"+p[1]:"");}
  function heads(){return HD?Promise.resolve(HD):get("laws/headings.json").then(function(d){return HD=d||[];});}
  function chapters(){return CH?Promise.resolve(CH):get("laws/chapters.json").then(function(d){return CH=d||{};});}

  // ---- THE READER: a section's text from its chapter's own page, on the right.
  function page(ch){
    if(!PAGES[ch])PAGES[ch]=fetch(link(ch)).then(function(r){return r.ok?r.text():"";}).then(function(t){
      return new DOMParser().parseFromString(t,"text/html");});
    return PAGES[ch];}
  function open(a){
    if(narrow()){location.href=link(a);return;}
    var ch=chOf(a),li=root.querySelector('.lw-ch[data-ch="'+ch+'"]');
    [].forEach.call(root.querySelectorAll("[data-sec][aria-current]"),function(x){x.removeAttribute("aria-current");});
    [].forEach.call(root.querySelectorAll('[data-sec="'+a+'"]'),function(x){x.setAttribute("aria-current","true");});
    var crumb=li?crumbOf(li):"",name=li?labelOf(li):"Chapter "+ch;
    read.innerHTML='<p class="lw-wait">Opening RSA '+esc(a)+'&hellip;</p>';
    page(ch).then(function(doc){
      var sec=doc&&doc.getElementById("s"+a.split(":")[1]);
      read.innerHTML='<p class="lw-rcrumb">'+esc(crumb)+' &rsaquo; '+esc(name)+'</p>'
        +(sec?sec.outerHTML:'<p>This section could not be opened here.</p>')
        +'<p class="lw-own"><a href="'+link(a)+'">Open RSA '+esc(a)+' on its chapter&rsquo;s page</a></p>';
      // A defined word opens its definition in place, as on the chapter's
      // page (DEFS_JS): the definitions the section's words point at, which
      // that page holds and this section does not, are copied in, hidden.
      if(sec&&doc){var held=document.createElement("div");held.hidden=true;
        [].forEach.call(read.querySelectorAll("a.rs-tm"),function(w){
          var id=w.getAttribute("data-def");
          if(!id){var h=w.getAttribute("href")||"",i=h.indexOf("#");id=i<0?"":h.slice(i+1);}
          if(!id||read.querySelector('[id="'+id+'"]'))return;
          var d=doc.getElementById(id);if(!d)return;
          var c=document.importNode(d,true);c.hidden=true;
          if(!c.getAttribute("data-href"))c.setAttribute("data-href",w.getAttribute("href"));
          held.appendChild(c);});
        if(held.firstChild)read.appendChild(held);}
      // Its lists folded as its chapter's page folds them (CHAPTER_JS, rsFold).
      if(window.rsFold)window.rsFold(read);
      read.scrollTop=0;
      var r=read.getBoundingClientRect();if(r.top<0)read.scrollIntoView({block:"start"});
    });
  }
  root.addEventListener("click",function(e){
    var t=e.target.closest("[data-sec]");if(!t||e.metaKey||e.ctrlKey||e.shiftKey)return;
    if(narrow())return;e.preventDefault();open(t.getAttribute("data-sec"));});

  // A chapter's label and its title's name, from what the row already shows.
  function labelOf(li){var n=li.querySelector(".lw-chname");return "Chapter "+li.getAttribute("data-ch")+": "+(n?n.textContent:"");}
  function crumbOf(li){var t=li.closest(".lw-title"),a=t&&t.querySelector(".lw-tno"),b=t&&t.querySelector(".lw-tname");
    return (a?a.textContent:"")+(b&&b.textContent?": "+b.textContent:"");}
  // ---- A CHAPTER OPENED IN THE DIRECTORY lists its sections, and the way
  // to its own page under them.
  root.addEventListener("toggle",function(e){
    var d=e.target;if(!d.classList||!d.classList.contains("lw-chd")||!d.open)return;
    if(d.querySelector(".lw-secs"))return;
    var ch=d.parentNode.getAttribute("data-ch");
    var ol=document.createElement("ol");ol.className="lw-secs";ol.setAttribute("data-ch",ch);
    ol.innerHTML='<li class="lw-none">Loading the sections&hellip;</li>';
    var own=document.createElement("p");own.className="lw-own";
    own.innerHTML='<a href="'+link(ch)+'">Open Chapter '+esc(ch)+' on its own page</a>';
    d.appendChild(ol);d.appendChild(own);
    heads().then(function(hd){
      var rows=hd.filter(function(x){return chOf(x[0])===ch;});
      ol.innerHTML=rows.length?rows.map(function(x){return '<li><a href="'+link(x[0])+'" data-sec="'+esc(x[0])
        +'"><b>'+esc(x[0])+'</b> '+esc(x[1])+'</a></li>';}).join(""):'<li class="lw-none">No section of this chapter is in force.</li>';
    });
  },true);

  // ---- THE FILTERS: topic, status and title, over the chapters the page
  // lists, in the bill search's groups (the person, 24 October 2026): a
  // group's head opens and shuts it, and how many are chosen in a group is
  // on its head, and on the Filter button that opens them under 60em, as on
  // /bills. What is chosen is in the address (?topic=Housing), which the page
  // reads when it opens, so a filtered list can be kept and sent.
  var rows=[].slice.call(root.querySelectorAll(".lw-ch")),titles=[].slice.call(root.querySelectorAll(".lw-title"));
  var side=document.getElementById("lwfacets"),tog=document.getElementById("lwftoggle"),
      clear=document.getElementById("lwclear"),form=document.getElementById("rsform");
  var NAMES={tp:"topic",st:"status",ti:"title"},SHOWN=[0,0];
  function inputs(name){return [].slice.call(side.querySelectorAll('input[name="'+name+'"]'));}
  function picked(name){return inputs(name).filter(function(x){return x.checked;}).map(function(x){return x.value;});}
  function anyPicked(){return picked("st").length+picked("tp").length+picked("ti").length;}
  function keep(li){
    var st=picked("st"),tp=picked("tp"),ti=picked("ti");
    if(st.length){var ok=st.some(function(v){return v==="in"?li.getAttribute("data-rep")!=="1":
      v==="rep"?li.getAttribute("data-rep")==="1":Number(li.getAttribute("data-pend"))>0;});if(!ok)return false;}
    if(tp.length){var mine=(li.getAttribute("data-topics")||"").split("|");if(!tp.some(function(v){return mine.indexOf(v)>=0;}))return false;}
    if(ti.length&&ti.indexOf(li.getAttribute("data-title"))<0)return false;
    return true;}
  // A chapter the search finds is kept where its row is.
  function keepCh(c){var li=root.querySelector('.lw-ch[data-ch="'+c+'"]');return !li||keep(li);}
  function head(key){return side.querySelector('.fhead[data-lwg="'+key+'"]');}
  function openGroup(h,on){
    if(!h)return;
    h.setAttribute("aria-expanded",on?"true":"false");h.parentNode.classList.toggle("open",on);
    var b=document.getElementById(h.getAttribute("aria-controls"));if(b)b.hidden=!on;}
  side.addEventListener("click",function(e){
    var h=e.target.closest&&e.target.closest(".fhead[data-lwg]");
    if(h)openGroup(h,h.getAttribute("aria-expanded")!=="true");});
  // Under 60em the groups are behind the Filter button, shut until it is
  // pressed; Escape inside them shuts them and goes back to the button.
  if(tog)tog.addEventListener("click",function(){
    var on=!root.classList.contains("fopen");root.classList.toggle("fopen",on);
    tog.setAttribute("aria-expanded",on?"true":"false");});
  root.addEventListener("keydown",function(e){
    if(e.key!=="Escape"||!tog||!root.classList.contains("fopen")||!(e.target.closest&&e.target.closest("#lwfacets,#lwftoggle")))return;
    root.classList.remove("fopen");tog.setAttribute("aria-expanded","false");tog.focus();});
  function badges(){
    var all=0;
    Object.keys(NAMES).forEach(function(k){var n=picked(k).length,b=head(k)&&head(k).querySelector(".badge");all+=n;
      if(b){b.textContent=n?String(n):"";b.hidden=!n;}});
    var tb=tog&&tog.querySelector(".badge");if(tb){tb.textContent=all?String(all):"";tb.hidden=!all;}
  }
  function address(){
    try{
      var p=new URLSearchParams(location.search);
      Object.keys(NAMES).forEach(function(k){p.delete(NAMES[k]);picked(k).forEach(function(v){p.append(NAMES[k],v);});});
      var s=p.toString(),want=location.pathname+(s?"?"+s:"")+location.hash;
      if(want!==location.pathname+location.search+location.hash)history.replaceState(history.state,"",want);
    }catch(e){}
  }
  // The count under the box: the chapters listed, or the search's hits.
  function tell(hits){
    if(hits!=null){count.textContent=hits.toLocaleString()+(hits===1?" match":" matches")
      +(anyPicked()?" in the filters chosen":"");return;}
    count.textContent=anyPicked()?SHOWN[0].toLocaleString()+" chapter"+(SHOWN[0]===1?"":"s")+" in "+SHOWN[1]
      +" title"+(SHOWN[1]===1?"":"s")+" match":count.getAttribute("data-all");
  }
  function filter(){
    var any=anyPicked(),shown=0,ts=0;
    rows.forEach(function(li){var k=keep(li);li.hidden=!k;if(k)shown++;});
    titles.forEach(function(t){var n=t.querySelectorAll(".lw-ch:not([hidden])").length;t.hidden=!n;
      if(n)ts++;var c=t.querySelector(".lw-tn");if(c)c.textContent=any?n+" of "+c.getAttribute("data-all"):c.getAttribute("data-all");
      if(any&&n&&n<=40)t.open=true;});
    SHOWN=[shown,ts];
    clear.hidden=!any;badges();address();
    // The search's hits are held to the filters too, as the bill search's are.
    if(box.value.trim())run();else tell();
  }
  side.addEventListener("change",function(e){if(e.target.matches&&e.target.matches("input[type=checkbox]"))filter();});
  clear.addEventListener("click",function(){
    inputs("st").concat(inputs("tp"),inputs("ti")).forEach(function(x){x.checked=false;});
    titles.forEach(function(t){t.open=false;});filter();});

  // ---- THE SEARCH: a number goes straight to it; words are ranked across the
  // chapters' names, the sections' headings and what each section is about.
  function stem(w){w=w.toLowerCase().replace(/^'+|'+$/g,"");if(/'s$/.test(w))w=w.slice(0,-2);
    if(w.length>4&&/ies$/.test(w))return w.slice(0,-3)+"y";
    if(w.length>3&&/s$/.test(w)&&!/ss$/.test(w))return w.slice(0,-1);return w;}
  var STOP=" a an and are as at be by for from in is it of on or the to with any all under ";
  function words(q){return (q.toLowerCase().match(/[a-z][a-z']{1,}/g)||[]).filter(function(w){
    return STOP.indexOf(" "+w+" ")<0;}).map(stem);}
  function has(text,w){return (text.toLowerCase().match(/[a-z][a-z']+/g)||[]).some(function(x){
    return stem(x)===w||(w.length>=4&&x.indexOf(w)===0);});}
  var CITE=/^\s*(?:rsa\s*)?(?:chapter\s*)?(\d{1,3}(?:-[a-z]{1,2})?)(?::\s*([0-9a-z.\-]+))?\s*$/i;
  function label(a,ch,hd){var c=chOf(a),info=ch[c]||[];
    if(a.indexOf(":")<0)return "Chapter "+c+": "+(info[0]||"");
    var h=(hd.filter(function(x){return x[0]===a;})[0]||[])[1]||"";return h;}
  function show(list,note){
    var on=!!(list||note);
    dir.hidden=on;
    out.innerHTML=!on?"":(note?'<p class="rs-note">'+esc(note)+'</p>':'')+(list&&list.length?'<ol class="rs-hits">'
      +list.slice(0,60).map(function(r){var sec=r[0].indexOf(":")>=0;
        return '<li><a href="'+link(r[0])+'"'+(sec?' data-sec="'+esc(r[0])+'"':'')+'>'
          +(sec?'<b>RSA '+esc(r[0])+'</b> ':'')+esc(r[1]||"")+'</a>'
          +(sec&&CH&&CH[chOf(r[0])]?' <span class="rs-in">in Chapter '+esc(chOf(r[0]))+'</span>':'')+'</li>';}).join("")+'</ol>':'');
    tell(on?(list||[]).length:null);
  }
  function run(){
    var q=box.value.trim();
    if(!q){show(null,"");return;}
    var m=CITE.exec(q);
    Promise.all([chapters(),heads(),WD?WD:get("laws/words.json").then(function(d){return WD=d||{words:{}};})]).then(function(r){
      if(box.value.trim()!==q)return;
      var ch=r[0],hd=r[1],wd=r[2];
      if(m&&ch[m[1].toUpperCase()]){
        var c=m[1].toUpperCase(),a=c+(m[2]?":"+m[2]:"");
        show([[a,label(a,ch,hd)]].concat(m[2]?[[c,label(c,ch,hd)]]:[]),"By number:");
        if(m[2]&&!narrow())open(a);return;
      }
      var ws=words(q);if(!ws.length){show([],"");return;}
      var hit={},name={};
      function add(a,lab,w,pts){var h=hit[a]||(hit[a]={w:{},s:0});h.w[w]=1;h.s+=pts;if(lab)name[a]=lab;}
      Object.keys(ch).forEach(function(c){var known=(ch[c][4]||[]).join(" "),lab="Chapter "+c+": "+ch[c][0];
        ws.forEach(function(w){if(has(ch[c][0]||"",w))add(c,lab,w,3);
          else if(known&&has(known,w))add(c,lab+" (the "+ch[c][4][0]+")",w,3);});});
      hd.forEach(function(x){ws.forEach(function(w){if(has(x[1],w))add(x[0],x[1],w,2);});});
      var hs={};hd.forEach(function(x){hs[x[0]]=x[1];});
      ws.forEach(function(w){var i=0;(wd.words[w]||[]).forEach(function(g){i+=g;var a=(hd[i]||[])[0];
        if(a)add(a,hs[a],w,1);});});
      var list=Object.keys(hit).map(function(a){return [a,name[a]||hs[a]||"",Object.keys(hit[a].w).length,hit[a].s];})
        .filter(function(x){return x[2]>=Math.min(ws.length,Math.max(1,ws.length-1));})
        .filter(function(x){return keepCh(chOf(x[0]));})
        .sort(function(x,y){var cx=x[0].indexOf(":")<0,cy=y[0].indexOf(":")<0;
          return y[2]-x[2]||(cy-cx)||y[3]-x[3]||(x[0]<y[0]?-1:1);});
      var all=list.filter(function(x){return x[2]===ws.length;}).length;
      show(list,list.length?(all===list.length?"Matching every word:":all+" match every word; then the closest:")
        :"Nothing found. Try fewer words, "+(anyPicked()?"fewer filters, ":"")+"or a chapter number such as 91-A.");
    });
  }
  var t=null;box.addEventListener("input",function(){clearTimeout(t);t=setTimeout(run,180);});
  // The search's files are fetched once the box is chosen, not on the first
  // letter typed, so the first answer does not wait for them.
  box.addEventListener("focus",function(){chapters();heads();if(!WD)WD=get("laws/words.json").then(function(d){return WD=d||{words:{}};});},{once:true});

  // ---- A FILTER OFFERED FOR ITS NAME as the box is typed in (the person,
  // 24 October 2026): app.js's filterOffers and filterCombo, which the bill
  // search's box uses, given this page's filters -- a topic, a title by its
  // name, a status. Choosing one ticks it as a click in its group would, and
  // the words it stands for leave the box. app.js loads after this script,
  // so they are taken up once the page has; without them the box searches
  // as it always has.
  var offers=null;
  var SAY_ST={"in":"All chapters <b>in force</b>","pend":"All chapters with <b>pending changes</b>",
              "rep":"All <b>repealed or moved</b> chapters"};
  function named(x){var lab=x.closest("label"),s=lab&&(lab.querySelector(".tname > span")||lab.querySelector("span"));
    return s?s.textContent:x.value;}
  function counted(x){var c=x.closest("label").querySelector(".c");return c?Number(c.textContent.replace(/,/g,"")):null;}
  function lawOffers(q){
    if(CITE.test(q)||!window.filterOffers)return [];
    function vals(k){return inputs(k).filter(function(x){return !x.checked;}).map(function(x){return [x.value,named(x),counted(x)];});}
    return window.filterOffers(q,[
      {key:"tp",values:vals("tp"),say:function(n){return "All chapters with the topic <b>"+esc(n)+"</b>";}},
      {key:"ti",values:vals("ti"),say:function(n,v){return "All chapters in <b>Title "+esc(v)+": "+esc(n)+"</b>";}},
      {key:"st",values:vals("st"),say:function(n,v){return SAY_ST[v]||esc(n);}}]);
  }
  function take(o){
    var x=inputs(o.key).filter(function(i){return i.value===o.v;})[0];
    if(!x)return;
    x.checked=true;openGroup(head(o.key),true);
    box.value=o.rest;clearTimeout(t);
    if(!o.rest)show(null,"");
    filter();
  }
  form.addEventListener("submit",function(e){
    e.preventDefault();
    // Return takes the offer the arrow keys are on; with none, the words are
    // searched, as they always were.
    if(offers&&offers.enter())return;
    clearTimeout(t);run();
  });
  function wire(){
    if(offers||!window.filterCombo)return;
    offers=window.filterCombo(box,{offers:lawOffers,choose:take,label:"Filters that match the words typed"});
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",wire);else wire();

  // ---- WHAT THE ADDRESS NAMES: the filters chosen (?topic=, ?status=,
  // ?title=, each as often as chosen), their groups open; and a search, as
  // the box's form sends one where the page's script has not loaded.
  (function(){
    var p;try{p=new URLSearchParams(location.search);}catch(e){return;}
    Object.keys(NAMES).forEach(function(k){p.getAll(NAMES[k]).forEach(function(v){
      inputs(k).forEach(function(x){if(x.value===v){x.checked=true;openGroup(head(k),true);}});});});
    if(p.get("q"))box.value=p.get("q");
  })();
  // A title linked from a chapter's breadcrumb (/laws#t-VI) opens.
  var h=location.hash.match(/^#t-(.+)$/);if(h){var d=document.getElementById("t-"+decodeURIComponent(h[1]));if(d){d.open=true;}}
  filter();
})();
