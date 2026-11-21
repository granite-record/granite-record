(function(){
  var OLD={"#towns":"#overview","#my-town":"#overview","#statewide":"#executive"};
  // MY TOWN IS A POP-UP NOW (the owner, 21 November 2026): the page opens on
  // the Overview, and an address that named the old tab -- a guide's "Find
  // your town", a bookmark, the old page's #towns -- opens the Overview with
  // the town panel open over it. find.js reads GR_TOWN_ASK and opens it.
  var ASK={"#towns":1,"#my-town":1};
  // THE MEMBERS-ELECT, ONCE THEY ARE GONE (the owner, 7 November 2026): from
  // the build of 2 December the tab and its panel are not drawn at all, and
  // /officials#members-elect -- or a heading inside it -- named nothing and
  // opened My Town with the dead address. While nothing on the page has that
  // id, it is Legislators, which the tab said "lists who holds each seat".
  // Between the reader's midnight and that build, the tab is still drawn,
  // retired, and TABS_JS opens Legislators for it.
  // BY DISTRICT HAS GONE (the walk of 8 November 2026): its view's own
  // address opens By county, where its chambers' headings (#of-eld-house)
  // are now.
  OLD["#pane-edist"]=OLD["#tab-edist"]="#pane-ecounty";
  var GONE={"#members-elect":1,"#of-elect-senate":1,"#of-elect-house":1,
    "#of-eld-senate":1,"#of-eld-house":1,"#pane-elast":1,"#pane-ecounty":1};
  function alias(){
    var to=OLD[location.hash],t=to||location.hash;
    if(ASK[location.hash]&&typeof window!=="undefined")window.GR_TOWN_ASK=1;
    if(GONE[t]&&!document.getElementById(t.slice(1)))to="#legislators";
    if(to&&history.replaceState)
      history.replaceState(null,"",location.pathname+location.search+to);
  }
  alias();
  addEventListener("hashchange",alias);
})();
