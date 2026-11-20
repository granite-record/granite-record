// THE RECORDING IN THE PAGE. Loaded only when a sample has one, so the other
// four kinds do not fetch YouTube's player to show a paragraph of prose.
// AFTER THE DOCUMENT, not with it. This sat in the head and ran before the
// body existed, so getElementById("ytdata") was null every time and the whole
// function returned without building a player -- silently, which is why the
// page looked finished and had no video in it.
document.addEventListener("DOMContentLoaded", function(){
  var d = document.getElementById("ytdata");
  if(!d) return;
  var player = null, ready = false;
  window.onYouTubeIframeAPIReady = function(){
    player = new YT.Player("ytplayer", {
      videoId: d.dataset.video,
      playerVars: {start: parseInt(d.dataset.start || "0", 10), rel: 0},
      events: {onReady: function(){ ready = true; }}
    });
  };
  var s = document.createElement("script");
  s.src = "https://www.youtube.com/iframe_api";
  document.head.appendChild(s);

  function hms(x){
    x = Math.max(0, Math.round(x));
    var h = Math.floor(x/3600), m = Math.floor((x%3600)/60), s2 = x%60;
    return h + ":" + String(m).padStart(2,"0") + ":" + String(s2).padStart(2,"0");
  }
  document.addEventListener("click", function(e){
    var seek = e.target.closest("[data-seek]");
    if(seek && ready){
      var to = seek.dataset.seek === "end" ? d.dataset.end : d.dataset.start;
      if(to !== ""){ player.seekTo(parseInt(to,10), true); player.playVideo(); }
      return;
    }
    // WHAT IS PLAYING, NOT WHAT WAS TYPED. Reading a time off the player and
    // retyping it is where a digit gets dropped, and this is a file measured
    // in seconds.
    var grab = e.target.closest("[data-grab]");
    if(grab && ready){
      var f = document.querySelector('[name="' + grab.dataset.grab + '"]');
      if(f){ f.value = hms(player.getCurrentTime()); f.focus(); }
    }
  });
});
