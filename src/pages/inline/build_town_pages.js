(function(){
  var el=document.getElementById("twnmap"),api=null;
  if(!el)return;
  function mount(){
    if(api||!window.GRMap||el.offsetParent===null)return;
    api=GRMap.mount(el,{layer:"base",layers:["base","senate","exec","cong"],
      frame:el.dataset.town,town:el.dataset.town,ward:el.dataset.ward||null,
      pick:el.dataset.pick||null,list:false,dim:true});
  }
  addEventListener("DOMContentLoaded",mount);
  var pane=el.closest(".twnpane");
  if(pane&&window.MutationObserver)
    new MutationObserver(mount).observe(pane,{attributes:true,attributeFilter:["hidden"]});
})();
