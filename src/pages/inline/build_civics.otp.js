(function(){
  var d=document.querySelector(".l-otp");
  if(!d)return;
  document.addEventListener("click",function(e){
    if(!d.open)return;
    if(e.target.closest(".l-otpb a")||!e.target.closest(".l-otp"))d.open=false;
  });
  document.addEventListener("keydown",function(e){
    if(e.key==="Escape"&&d.open){d.open=false;d.querySelector("summary").focus();}
  });
  // Common Questions print open (civics.faq).
  window.addEventListener("beforeprint",function(){
    document.querySelectorAll(".l-faq details").forEach(function(x){x.open=true;});
  });
  // The same list beside the page, where app.css gives it a column
  // (.l-sidewrap), the section being read marked as the reader scrolls.
  var page=document.querySelector(".l-page"),src=d.querySelector(".l-otpb");
  if(!page||!src)return;
  var wrap=document.createElement("div"),nav=document.createElement("nav"),h=document.createElement("p");
  wrap.className="l-sidewrap";nav.className="l-side";
  nav.setAttribute("aria-label",src.getAttribute("aria-label")||"On this page");
  h.className="l-sidehead";h.textContent=d.querySelector("summary").textContent;
  nav.appendChild(h);nav.appendChild(src.querySelector("ol").cloneNode(true));
  wrap.appendChild(nav);page.insertBefore(wrap,page.firstChild);
  var links={};
  nav.querySelectorAll("a").forEach(function(a){var i=a.href.indexOf("#");if(i>=0)links[decodeURIComponent(a.href.slice(i+1))]=a;});
  var secs=[].slice.call(document.querySelectorAll(".l-art > .l-sec[id]")).filter(function(s){return links[s.id];});
  if(!secs.length||!("IntersectionObserver" in window))return;
  var cur=null;
  function mark(){
    var y=window.innerHeight*0.25,best=secs[0];
    secs.forEach(function(s){if(s.getBoundingClientRect().top<=y)best=s;});
    if(best===cur)return;
    if(cur)links[cur.id].removeAttribute("aria-current");
    cur=best;links[cur.id].setAttribute("aria-current","location");
  }
  var io=new IntersectionObserver(mark,{rootMargin:"0px 0px -75% 0px"});
  secs.forEach(function(s){io.observe(s);});
  window.addEventListener("scroll",mark,{passive:true});mark();
})();
