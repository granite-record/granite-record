(function(){
  var box=document.getElementById("gfind"), list=document.getElementById("gfind-list"),
      stat=document.getElementById("gfind-status"), src=document.getElementById("gfind-data");
  if(!box||!list||!src)return;
  var D=JSON.parse(src.textContent), S=D.s, G=D.g, act=-1, opts=[];
  var STOP={};
  ("a an the to how do does i im my me can could get for of in on is it its what where when who "
   +"and or with need want about your you be am are we our at from as by this that should "
   +"como de del la el los las un una mi mis para que en y o con por se puedo quiero necesito "
   +"sobre su sus al lo le hacer").split(" ").forEach(function(w){STOP[w]=1;});
  var SYN={updat:"renew",renewal:"renew",expir:"renew",licence:"license",testimony:"testify",
    testimoni:"testify",testif:"testify",dump:"transfer",garbage:"trash",rubbish:"trash",
    homeles:"homeless",evict:"eviction",daycare:"child",childcare:"child",snap:"food",
    rep:"representative",reps:"representative",sen:"senator"};
  function norm(s){return String(s||"").toLowerCase().normalize("NFD")
    .replace(/[\u0300-\u036f]/g,"").replace(/['\u2019]/g,"").replace(/[^a-z0-9]+/g," ").trim();}
  function stem(w){
    if(SYN[w])return SYN[w];
    if(w.length>5&&/ies$/.test(w))w=w.slice(0,-3)+"y";
    else if(w.length>5&&/ing$/.test(w))w=w.slice(0,-3);
    else if(w.length>4&&/ed$/.test(w))w=w.slice(0,-2);
    else if(w.length>3&&/s$/.test(w)&&!/ss$/.test(w))w=w.slice(0,-1);
    return SYN[w]||w;
  }
  function toks(s){var o=[];norm(s).split(" ").forEach(function(w){if(w&&!STOP[w])o.push(stem(w));});return o;}
  G.forEach(function(g){
    g.w={};
    [[g.t,3],[g.k,2],[g.l,1]].forEach(function(p){
      toks(p[0]).forEach(function(w){if(!(g.w[w]>=p[1]))g.w[w]=p[1];});
    });
  });
  function score(g,q){
    var s=0,hit=0;
    q.forEach(function(w){
      var best=g.w[w]||0;
      if(!best&&w.length>=3){for(var k in g.w){if(k.indexOf(w)===0&&g.w[k]*0.8>best)best=g.w[k]*0.8;}}
      if(best){s+=best;hit++;}
    });
    return hit?s+(hit===q.length?2:0):0;
  }
  function pick(i){
    opts.forEach(function(li,k){li.setAttribute("aria-selected",k===i?"true":"false");});
    act=i;
    if(i>=0){box.setAttribute("aria-activedescendant",opts[i].id);opts[i].scrollIntoView({block:"nearest"});}
    else box.removeAttribute("aria-activedescendant");
  }
  function close(){list.hidden=true;box.setAttribute("aria-expanded","false");pick(-1);}
  function option(i,href,head,line,cls){
    var li=document.createElement("li"),a=document.createElement("a"),b=document.createElement("b");
    li.id="gfind-o"+i;li.setAttribute("role","option");li.setAttribute("aria-selected","false");
    if(cls)li.className=cls;
    a.href=href;a.tabIndex=-1;b.textContent=head;a.appendChild(b);
    if(line){var sp=document.createElement("span");sp.textContent=line;a.appendChild(sp);}
    li.appendChild(a);list.appendChild(li);return li;
  }
  var found=[];
  function draw(){
    var raw=box.value.trim();
    list.innerHTML="";opts=[];act=-1;
    if(!raw){close();stat.textContent="";return;}
    var q=toks(raw);
    found=G.map(function(g){return [q.length?score(g,q):0,g];})
      .filter(function(x){return x[0]>0;})
      .sort(function(a,b){return b[0]-a[0]||a[1].t.length-b[1].t.length;}).slice(0,6);
    found.forEach(function(x,i){opts.push(option(i,x[1].h,x[1].t,x[1].l));});
    opts.push(option(found.length,"/search?q="+encodeURIComponent(raw),
      S.all.replace("{q}",raw),"","g-findall"));
    list.hidden=false;box.setAttribute("aria-expanded","true");
    stat.textContent=found.length?(found.length===1?S.one:S.many.replace("{n}",found.length)):S.none;
  }
  box.setAttribute("role","combobox");box.setAttribute("aria-autocomplete","list");
  box.setAttribute("aria-controls","gfind-list");box.setAttribute("aria-expanded","false");
  box.addEventListener("input",draw);
  box.addEventListener("focus",function(){if(box.value.trim())draw();});
  box.addEventListener("keydown",function(e){
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){
      if(list.hidden)draw();
      if(!opts.length)return;
      e.preventDefault();
      var n=opts.length,i=e.key==="ArrowDown"?(act+1)%n:(act<=0?n-1:act-1);
      pick(i);
    }else if(e.key==="Enter"){
      var li=act>=0?opts[act]:(found.length?opts[0]:null);
      if(li){e.preventDefault();location.href=li.querySelector("a").href;}
    }else if(e.key==="Escape"){if(!list.hidden){e.preventDefault();close();}}
  });
  document.addEventListener("click",function(e){if(!e.target.closest||!e.target.closest(".g-findbox"))close();});
})();
