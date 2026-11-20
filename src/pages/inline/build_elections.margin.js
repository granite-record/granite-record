(function(){
  var each=function(s,r){return [].slice.call((r||document).querySelectorAll(s));};
  each(".er-filt").forEach(function(f){
    var pane=document.getElementById(f.getAttribute("data-pane"));
    if(!pane)return;
    var cards=each(".er-race",pane),home=cards.map(function(c){return c.parentNode;});
    var flat=pane.querySelector(".er-flat"),heads=each(".er-county",pane),btns=each("button[data-band]",f);
    var sel=f.querySelector("select"),say=f.querySelector(".er-count"),box=pane.querySelector(".er-find");
    var find=box&&box.querySelector("input"),band="";
    f.hidden=false;if(box)box.hidden=false;
    var num=function(c,k){var v=c.getAttribute("data-"+k);return v===null||v===""?null:+v;};
    var by=function(up){return function(a,b){
      var x=num(a,"points"),y=num(b,"points");
      if(x===null||y===null)return (x===null)-(y===null)||cards.indexOf(a)-cards.indexOf(b);
      return (up?x-y:y-x)||(up?num(a,"gap")-num(b,"gap"):num(b,"gap")-num(a,"gap"))||cards.indexOf(a)-cards.indexOf(b);};};
    function apply(){
      var q=find?find.value.trim().toLowerCase():"",ord=sel?sel.value:"district",n=0;
      cards.forEach(function(c){
        var on=(!band||c.getAttribute("data-band")===band)&&(!q||(c.getAttribute("data-towns")||"").indexOf(q)>=0);
        c.hidden=!on;if(on)n++;});
      if(ord==="district"||!flat){
        cards.forEach(function(c,i){home[i].appendChild(c);});
        if(flat)flat.hidden=true;
        heads.forEach(function(h){var g=h.nextElementSibling;
          h.hidden=!cards.some(function(c){return c.parentNode===g&&!c.hidden;});if(g)g.hidden=h.hidden;});
      }else{
        cards.slice().sort(by(ord==="small")).forEach(function(c){flat.appendChild(c);});
        flat.hidden=false;
        heads.forEach(function(h){h.hidden=true;if(h.nextElementSibling)h.nextElementSibling.hidden=true;});
      }
      say.textContent=band||q?n+" of "+cards.length+" races"+(q?" with a town or ward matching \u201c"+find.value.trim()+"\u201d":""):"";
    }
    btns.forEach(function(b){b.addEventListener("click",function(){
      band=b.getAttribute("data-band");
      btns.forEach(function(x){x.setAttribute("aria-pressed",x===b?"true":"false");});apply();});});
    if(sel)sel.addEventListener("change",apply);
    if(find)find.addEventListener("input",apply);
    each("a[data-order]").forEach(function(a){if(a.getAttribute("data-pane")!==pane.id)return;
      a.addEventListener("click",function(){if(sel)sel.value=a.getAttribute("data-order");band="";
        btns.forEach(function(x){x.setAttribute("aria-pressed",x.getAttribute("data-band")===""?"true":"false");});apply();});});
  });
})();
