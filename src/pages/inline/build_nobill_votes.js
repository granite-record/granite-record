(function(){
  var sel=document.querySelector(".nbkind"),rows=document.querySelectorAll(".nbtab tbody tr"),
      count=document.querySelector(".nbcount");
  if(!sel)return;
  function show(){
    var k=sel.value,n=0;
    [].forEach.call(rows,function(r){var on=!k||r.dataset.kind===k;r.hidden=!on;if(on)n++;});
    count.textContent=n.toLocaleString("en-US")+(n===1?" vote":" votes")+" shown";
    if(history.replaceState)history.replaceState(null,"",location.pathname+(k?"?kind="+k:"")+location.hash);
  }
  sel.addEventListener("change",show);
  var want=new URLSearchParams(location.search).get("kind");
  if(want&&[].some.call(sel.options,function(o){return o.value===want;})){sel.value=want;show();}
})();
