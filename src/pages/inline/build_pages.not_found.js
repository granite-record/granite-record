(function(){
  // A LAW OR A BILL ASKED FOR IN CAPITALS, OR A STATUTE BY ITS CITATION
  // (the polish of 12 October 2026): /laws/91-A is chapter 91-A's page and
  // /laws/91-A:4 its section 4. Every such page's address is lower case, so
  // the lower-case form is tried once; an address already in it is left
  // here, which is what keeps this from going round.
  // RSA 404's page is a folder's, at its address with a slash: FOLDERS is
  // build_rsa.FOLDER_CHAPTERS, which preflight holds this to (16 October 2026).
  var FOLDERS=["404"];
  var lp=location.pathname,c=lp.match(/^\/laws\/(\d{1,3}(?:-[a-z]{1,2})?)(?::([0-9a-z.\-]+))?\/?$/i);
  if(c&&(c[2]||c[1]!==c[1].toLowerCase())){var s=c[1].toLowerCase();
    location.replace("/laws/"+s+(FOLDERS.indexOf(s)>=0?"/":"")+(c[2]?"#s"+c[2].toLowerCase():location.hash));return;}
  // And a town's, which is lower case without a slash at the end: /town/Dover
  // and /town/dover/ are /town/dover, which is a page (the review of 7
  // November 2026). Each is tried once, from an address that differs.
  // THE GENERAL COURT'S OWN ADDRESS OF A BILL, with this site's host:
  // /legislation/2025/HB0703.html is /bill/2025/hb703, which this page reads
  // again if it is not there (the third review of 7 November 2026).
  var g=lp.match(/^\/legislation\/(\d{4})\/([a-z]+)0*(\d+)(?:\.html?)?\/?$/i);
  if(g){location.replace("/bill/"+g[1]+"/"+(g[2]+g[3]).toLowerCase()+location.search+location.hash);return;}
  // A capital anywhere in the path counts, /BILL/2025/hb703 among them (the
  // second review of 7 November 2026).
  if(/^\/(bill|laws|town)\//i.test(lp)&&lp!==lp.toLowerCase()){location.replace(lp.toLowerCase()+location.search+location.hash);return;}
  if(/^\/town\/[^\/]+\/$/.test(lp)){location.replace(lp.slice(0,-1)+location.search+location.hash);return;}
  var m=lp.match(/^\/bill\/(\d{4})\/([a-z]+)0*(\d+)/i);
  var t=lp.match(/^\/town\/([^\/?#]+)$/i);
  var lead=document.getElementById("nf-lead"),p=document.getElementById("nf-bill");
  var say=function(el,parts){if(!el)return;el.textContent="";
    for(var i=0;i<parts.length;i++){var x=parts[i];if(typeof x==="string")el.appendChild(document.createTextNode(x));
      else{var a=document.createElement("a");a.href=x[1];a.textContent=x[0];el.appendChild(a);}}
    el.hidden=false;};
  // THE LEAD SPEAKS OF BILLS ON A BILL'S ADDRESS ONLY (the laptop's test of
  // 7 November 2026): a town, a member or a law not found was told about
  // bill numbers and the years they start again in. Any address under
  // /bill/ keeps it -- /bill/hb703 and /bill/2025-2026/hb703 most of all,
  // which is what it explains.
  if(!t&&!/^\/bills?\//i.test(lp)){say(lead,["The address may be mistyped."]);return;}
  if(t){
    // A TOWN NOT FOUND (the laptop's test of 7 November 2026, and its
    // review): the town or ward of that name from the site search's own list
    // (find.json), by its name -- /town/harts-location is Hart's Location,
    // and an address that is a name's exactly, punctuation aside, goes there.
    // A city's row is there under its own page, officials?town=Dover. A ward
    // number the city does not have names the city, never another ward:
    // pointing to the wrong ward points to the wrong representatives.
    //
    // And the second review of that night. The page says it is looking while
    // the list arrives, as a bill's does. A ward address with no number the
    // city has -- /town/dover-ward, /town/manchester-ward-1-2 -- names the
    // city too: it offered Ward 1, or went to Ward 12. The record writes
    // some places short -- Chandler's Pur., Wentworth's Loc., Second College
    // Gt -- so a name is read both as written and word by word with the
    // long words as the record's short ones (WORDS), and the nearer counts:
    // /town/chandlers-purchase offered Hadley's Purchase. Two letters
    // swapped are one slip, not two. And an exact name never goes to the
    // address it is on, which would go round.
    say(lead,["Looking for a town or ward at this address\u2026"]);
    var nothing=function(){say(lead,["No town or ward has a page at this address."]);};
    var WORDS={purchase:"pur",location:"loc",grant:"gt",and:"",atkinson:"atk",gilmanton:"gil",
      meserve:"mess",meserves:"mess"};
    var norm=function(s){return String(s).toLowerCase().replace(/[^a-z0-9]/g,"");};
    // Words are made short only in a name of more than one word: Atkinson
    // and Gilmanton are towns, and as "atk" and "gil" drew /town/ath and
    // /town/hil away from Bath and Hill (the third review).
    var brief=function(s){var w=String(s).toLowerCase().replace(/['\u2019]/g,"").split(/[^a-z0-9]+/),o="";
      var many=w.filter(function(x){return x;}).length>1;
      for(var i=0;i<w.length;i++)o+=many&&WORDS.hasOwnProperty(w[i])?WORDS[w[i]]:w[i];return o;};
    // How far a slip may be: one letter in a word of four or fewer, so
    // /town/xyz is not Rye; two, or a quarter of the letters, beyond that.
    var reach=function(s){return s.length<=4?1:Math.max(2,Math.floor(s.length/4));};
    var dist=function(a,b){var d=[],i,j;for(i=0;i<=a.length;i++){d[i]=[i];}for(j=0;j<=b.length;j++)d[0][j]=j;
      for(i=1;i<=a.length;i++)for(j=1;j<=b.length;j++){
        var c=a.charAt(i-1)===b.charAt(j-1)?0:1;
        d[i][j]=Math.min(d[i-1][j]+1,d[i][j-1]+1,d[i-1][j-1]+c);
        if(i>1&&j>1&&a.charAt(i-1)===b.charAt(j-2)&&a.charAt(i-2)===b.charAt(j-1))d[i][j]=Math.min(d[i][j],d[i-2][j-2]+1);}
      return d[a.length][b.length];};
    var raw;try{raw=decodeURIComponent(t[1]).toLowerCase();}catch(_){raw=t[1].toLowerCase();}
    raw=raw.replace(/\.html?$/,"");
    var wm=raw.match(/^(.+?)[-_\s]*ward[-_\s]*0*(\d+)$/);
    var wx=wm?null:raw.match(/^(.+?)[-_\s]*wards?(?:[^a-z].*)?$/);
    if(typeof fetch!=="function"){nothing();return;}
    fetch("/find.json").then(function(r){return r.ok?r.json():null;}).then(function(rows){
      if(!rows){nothing();return;}
      var places=[],wards=[];
      for(var i=0;i<rows.length;i++){var r=rows[i];
        if(!r||!r[3]||!/^(town\/|officials\?town=)/.test(r[3]))continue;
        if(r[0]==="ward")wards.push(r);else if(r[0]==="town")places.push(r);}
      // The nearest row by either reading of the name, each held to its
      // own length; an address within reach of neither offers nothing.
      var best=function(list,want){var b=null,bd=1e9,ws=[norm(want),brief(want)];
        for(var i=0;i<list.length;i++){var rs=[norm(list[i][1]),brief(list[i][1])];
          for(var f=0;f<2;f++){var dd=dist(ws[f],rs[f]);
            if(dd<bd&&dd<=reach(ws[f])){bd=dd;b=list[i];}}}
        return b?{row:b,d:bd}:null;};
      // The cities, which have wards: where an address names a ward, one of
      // them is meant, before a town of the same distance with none --
      // /town/ochester-ward-3 is Rochester's, not Chester (the third review).
      var cities=places.filter(function(c){for(var j=0;j<wards.length;j++)
        if(norm(wards[j][1]).indexOf(norm(c[1])+"ward")===0)return true;return false;});
      var offer=function(row,more){say(lead,["No town or ward has a page at this address. Did you mean ",
        [row[1],"/"+row[3]],"?"+(more||"")]);};
      var go=function(row){if("/"+row[3]===lp){offer(row);return;}location.replace("/"+row[3]);};
      // A ward named with no number is a ward only of a city that has them:
      // /town/edwards is no ward of Lee.
      var ward=wm||wx,city=ward?(best(cities,ward[1])||best(places,ward[1])):null,its=[];
      if(city)for(var j=0;j<wards.length;j++)
        if(norm(wards[j][1]).indexOf(norm(city.row[1])+"ward")===0)its.push(wards[j]);
      if(wm&&!city){nothing();return;}
      if(city&&(wm||its.length)){
        var n=wm?+wm[2]:-1,w=null;for(var k=0;k<its.length;k++){var wn=norm(its[k][1]).match(/ward(\d+)$/);
          if(wn&&+wn[1]===n)w=its[k];}
        if(w){if(city.d===0)go(w);else offer(w);return;}
        offer(city.row,its.length?" It has wards 1 to "+its.length+".":"");return;
      }
      var hit=best(places.concat(wards),raw);
      if(!hit){nothing();return;}
      if(hit.d===0){go(hit.row);return;}
      // A slip that lands near a ward names the city, never the ward: one
      // letter from Ward 1 is one letter from Ward 11 too
      // (/town/manchester-war-11; the third review).
      if(hit.row[0]==="ward"){var cn=norm(String(hit.row[1]).split(",")[0]);
        for(var ci=0;ci<cities.length;ci++)if(norm(cities[ci][1])===cn){var n2=0;
          for(var j2=0;j2<wards.length;j2++)if(norm(wards[j2][1]).indexOf(cn+"ward")===0)n2++;
          offer(cities[ci]," It has wards 1 to "+n2+".");return;}}
      offer(hit.row);
    })["catch"](function(){nothing();});
    return;
  }
  // A BILL, WITH ITS NUMBER AS THE RECORD WRITES IT ("HB 703"), and where it
  // is in the term the year names: under the term's other year, or the
  // filing year of a bill carried into the next (the laptop's test of 7
  // November 2026: /bill/2026/hb703 and /bill/2019/hb703). One small
  // request asks for the bill's page at the term's other year, and the page
  // says it is looking meanwhile; found, it is said and gone to, its tab
  // kept. An address with more after the number -- a tab there is no such
  // tab -- is first asked at its own year, and goes to the bill's page. A
  // number the term does not have keeps the search, of every term.
  //
  // And the second review of that night. The number as the General Court
  // writes it, padded (/bill/2025/hb0703; its own /legislation/2025/
  // HB0703.html with this host is sent to /bill/2025/hb703 above), and a
  // real tab with a slash at its end
  // (/bill/2025/hb703/votes/) answer 404 though the bill is there: each is
  // asked at its own year as the record writes it, the tab first where the
  // address names one. Every address asked is the bill's, never the one
  // the page is on, and is gone to only where it answers, so nothing goes
  // round. A request that fails says so, rather than that there is no page.
  // An address that is no bill's shape but names a number -- /bill/hb703,
  // /bill/2025-2026/hb703 -- is offered the search for it.
  if(!m){
    var dl;try{dl=decodeURIComponent(lp);}catch(_){dl=lp;}
    var q=/^\/bills?\//i.test(lp)&&dl.match(/\/([a-z]{2,4})[-_\s]*0*(\d{1,4})(?:\.html)?\/?$/i);
    if(q){var qs=q[1].toUpperCase()+" "+q[2];
      say(p,[["Search for "+qs+" in every term","/bills?q="+encodeURIComponent(qs)+"&term=all"]]);}
    return;
  }
  var y=+m[1],id=(m[2]+m[3]).toUpperCase(),said=m[2].toUpperCase()+" "+m[3];
  var search=["Search for "+said+" in every term","/bills?q="+encodeURIComponent(said)+"&term=all"];
  var none=function(){say(p,["No page for "+said+" of "+y+". ",search]);};
  var failed=function(){say(p,["Could not look for "+said+" just now. ",search]);};
  if(y<1989||y>2099||typeof fetch!=="function"){none();return;}
  var term=y%2?y+"-"+(y+1):(y-1)+"-"+y,other=y%2?y+1:y-1;
  var tail=lp.slice(m[0].length).replace(/^\.html/i,""),tab=/^(\/[a-z]+)?\/?$/i.test(tail)?tail.replace(/\/$/,""):"";
  // The address the page is on is the same page with or without .html.
  var here=lp.replace(/\.html?$/i,"");
  var ask=[],add=function(yy,tb){var to="/bill/"+yy+"/"+id.toLowerCase();
    if(to+tb!==here)ask.push([to,tb]);};
  if(tab)add(y,tab);add(y,"");if(tab)add(other,tab);add(other,"");
  say(p,["Looking for "+said+" in the "+term.replace("-","\u2013")+" term\u2026"]);
  var next=function(i){
    if(i>=ask.length){none();return;}
    var to=ask[i][0],go=to+ask[i][1];
    fetch(go,{method:"HEAD"}).then(function(r){
      if(!r.ok){next(i+1);return;}
      say(p,[said+" of the "+term.replace("-","\u2013")+" term is at ",[to,to],"."]);
      location.replace(go+location.search+location.hash);
    })["catch"](function(){failed();});
  };
  next(0);
})();
