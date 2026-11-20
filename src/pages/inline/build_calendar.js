(function(){
  "use strict";
  var G=typeof window!=="undefined"?window:globalThis;

  // ==== THE CORE, which touches no page ======================================
  //
  // Dates, the cards' own fields, the filters, the count and the markup of the
  // grid and the preview are plain functions over plain values, so preflight
  // runs them in node against the cards a build actually wrote. The part that
  // touches the page is below them and does no reasoning of its own.
  //
  // Dates are ISO strings, "2026-09-23", and all arithmetic is in UTC: a day
  // is a date, not a moment, and a reader's time zone must not move one.
  // A DATE IN WORDS is components.js's dateWords() and dateSpan(), month
  // first, and a time its clock(); the page loads that file in its head,
  // before this script. The names of the days and months are its lists.
  var DAYNAME=DW_DAYS, MONTH=DW_MONTHS;
  // THE KINDS OF MEETING A READER SHOWS OR HIDES, in the order of the row of
  // boxes above the schedule (build_calendar.CATEGORIES), which is the key to
  // the colours and the filter at once. All of them are on for a new reader
  // except the study and statutory committees, as the person asked on 25
  // September 2026: "each one is selected on by default aside from study
  // committees".
  // KEY DATES, THE SEVENTH BOX (the owner, 24 October 2026: "those dates
  // should show up on the calendar page too under a separate meeting type in
  // the key"), on for a new reader: the elections, town meeting days and the
  // legislature's own dates (key_dates.py). A key date is an entry of the
  // schedule like a card, and not a meeting: nothing that counts meetings
  // counts it (isKD).
  var CATS=["hearing","exec","work","conf","floor","study","date"];
  var CAT_ON=["hearing","exec","work","conf","floor","date"];
  // A card's kinds are its bar's colours, and each answers to one box. A
  // kind the table does not name is one of the committee's other meetings,
  // which Work Session has always covered.
  var CAT_OF={hearing:"hearing",exec:"exec",meet:"work",other:"work",conf:"conf",
              floor:"floor",study:"study",date:"date"};
  // The grid's dots in the order of the boxes, a day's key date first, as
  // its card is first in the day.
  var BAR_ORDER=["date","hearing","exec","meet","conf","floor","study","other"];
  // NO DAY VIEW (the owner's walk of dry run 9, 8 November 2026): the list
  // at that day says the same. An address asking for it reads as the list.
  var VIEWS=["list","week"];
  function viewOf(v){ return v==="day"?"list":VIEWS.indexOf(v)>=0?v:null; }
  // A CARD'S OPENING TAG, NEVER WRITTEN WHOLE HERE. The checks count cards,
  // links and the empty day's sentence in a built page's text, and this
  // script is in that text; spelling the tag out would count as a card.
  // A key date's card has a class of its own (build_pages.cal_days), and is
  // read here as an entry like a meeting's.
  var CARD='<details class="cal'+'meet"', KDCARD='<details class="cal'+'kd"';
  var ANY='<details class="cal(?:meet|kd)"';
  var CARD_TAG=new RegExp("^"+ANY+"[^>]*>"), CARDS=new RegExp(ANY+"[\\s\\S]*?</details>","g");
  function isKD(e){ return e.who==="date"; }
  function meetings(a){ return a.filter(function(e){ return !isKD(e); }); }

  function pad(n){ return (n<10?"0":"")+n; }
  function iso(y,m,d){
    var x=new Date(Date.UTC(y,m-1,d));
    return x.getUTCFullYear()+"-"+pad(x.getUTCMonth()+1)+"-"+pad(x.getUTCDate());
  }
  function utc(s){ return Date.UTC(+s.slice(0,4),+s.slice(5,7)-1,+s.slice(8,10)); }
  function addDays(s,n){ return iso(+s.slice(0,4),+s.slice(5,7),+s.slice(8,10)+n); }
  // Monday is 0: the weeks here are ISO weeks, Monday to Sunday, which is
  // what every week's address names.
  function weekday(s){ return (new Date(utc(s)).getUTCDay()+6)%7; }
  function monday(s){ return addDays(s,-weekday(s)); }
  function weekKey(s){
    var t=addDays(monday(s),3), y=+t.slice(0,4);
    return y+"-W"+pad(Math.floor((utc(t)-Date.UTC(y,0,1))/864e5/7)+1);
  }
  // The fourth of January is always in week 1.
  function keyMonday(k){ return addDays(monday(iso(+k.slice(0,4),1,4)),(+k.slice(6)-1)*7); }
  function month(s){ return s.slice(0,7); }
  function addMonths(m,n){
    var y=+m.slice(0,4), i=+m.slice(5,7)-1+n;
    return (y+Math.floor(i/12))+"-"+pad(((i%12)+12)%12+1);
  }
  function daysIn(m){ return new Date(Date.UTC(+m.slice(0,4),+m.slice(5,7),0)).getUTCDate(); }
  // The rows a month's grid draws: whole weeks, Monday first, so a week is
  // one row and the selected one can be one band.
  // SIX WEEKS, WHATEVER THE MONTH (the person, 7 October 2026, F10: "show
  // the neighbouring months' days, slightly greyed", as a desktop calendar
  // does). The grid drew only the weeks a month's own days fall in, so it
  // showed a day or two of the months either side and sometimes none --
  // February 2027 begins on a Monday and ends on a Sunday -- and changed
  // height from month to month. Six weeks from the Monday on or before the
  // 1st hold any month, and the days of the months either side fill the rest
  // in the grey cellHtml gives them (cmout), each a day the reader may choose.
  function monthRows(m){
    var d=monday(m+"-01"), rows=[];
    for(var w=0;w<6;w++){
      var r=[];
      for(var i=0;i<7;i++){ r.push(d); d=addDays(d,1); }
      rows.push(r);
    }
    return rows;
  }
  function shiftMonth(s,n){
    var m=addMonths(month(s),n);
    return m+"-"+pad(Math.min(+s.slice(8),daysIn(m)));
  }
  function dayWords(s){ return dateWords(s,"day"); }
  // A week's name from its key alone: build_calendar.week_facts's label,
  // "March 9–13, 2026" or "March 30 – April 3, 2026" -- MONDAY TO FRIDAY
  // (the person, 9 October 2026: "Dont display Saturdays and sundays on the
  // week view, only weekdays since there aren't meetings on the weekend").
  // For a week whose month file did not come, so the heading can still name
  // the week the address does; preflight holds the two to the same words. A
  // week with a Saturday or Sunday sitting runs to that day, and only its
  // month file can say so: none has since the calendar's first week.
  // `form` "medium" is the pager's short name for it, "Mar 9–13, 2026".
  function weekLabel(k,form){ var a=keyMonday(k); return dateSpan(a,addDays(a,4),form); }
  function monthWords(m){ return MONTH[+m.slice(5,7)-1]+" "+m.slice(0,4); }
  // build_calendar.day_words's rule, in the reader's clock.
  function relWord(s,today){
    var off=Math.round((utc(s)-utc(today))/864e5);
    return off===0?"today":off===1?"tomorrow":(off>0&&off<=14)?"in "+off+" days":"";
  }
  function plural(n,w){ return n+" "+w+(n===1?"":"s"); }
  function unesc(s){
    return String(s).replace(/&(amp|lt|gt|quot|#x27|#39);/g,function(_m,e){
      return {amp:"&",lt:"<",gt:">",quot:'"',"#x27":"'","#39":"'"}[e]; });
  }
  function words(v){ return String(v||"").split(" ").filter(Boolean); }

  // ---- a card, read off the card ---------------------------------------------
  //
  // EVERYTHING THE GRID, THE PREVIEW AND THE FILTERS NEED IS ON THE CARD
  // ALREADY, put there by build_pages.cal_days for the week's own filter. So
  // an entry is its card's HTML and what that card says about itself, read
  // the same way whether the card came in the page or in a month file.
  function attr(tag,name){
    var m=new RegExp(" "+name+'="([^"]*)"').exec(tag);
    return m?unesc(m[1]):null;
  }
  function parseCard(html){
    var tag=(CARD_TAG.exec(html)||[""])[0],
        name=/<span class="calcmte">([^<]*)<\/span>/.exec(html);
    // pick: the committee as the picker lists it -- the card's own name, or
    // "Committee of conference" for every bill's conference.
    var nm=name?unesc(name[1]):"";
    return {html:html, date:attr(tag,"data-date")||"",
            name:nm, pick:attr(tag,"data-pick")||nm, cmte:attr(tag,"data-cmte")||"",
            body:attr(tag,"data-body")||"", bills:words(attr(tag,"data-bills")),
            time:attr(tag,"data-time")||"", last:attr(tag,"data-last")||"",
            venue:attr(tag,"data-venue")||"",
            study:attr(tag,"data-study")!==null,
            cancelled:attr(tag,"data-cancelled")!==null,
            who:attr(tag,"data-who")||"standing", kinds:words(attr(tag,"data-kinds"))};
  }
  // A day as cal_days draws it: its heading, then its cards, then the close.
  // Cards never nest, so each one runs to the first </details> after it.
  // `tail` is what follows the last card: on a day of key dates alone, the
  // line that says no meeting is on it, which is true under any filter.
  function parseDay(html){
    var a=html.indexOf(CARD), b=html.indexOf(KDCARD), i=a<0?b:b<0?a:Math.min(a,b);
    return {head:i<0?html.replace(/<\/div>\s*$/,""):html.slice(0,i),
            cards:(html.match(CARDS)||[]).map(parseCard),
            tail:i<0?"":html.slice(html.lastIndexOf("</details>")+10).replace(/<\/div>\s*$/,"")};
  }
  function kdHtml(vis){ return vis.filter(isKD).map(function(e){ return e.html; }).join(""); }
  function dayHtml(day,cards){
    return day.head+cards.map(function(e){ return e.html; }).join("")+"</div>";
  }

  // ---- the filters -------------------------------------------------------------
  function defaults(){
    return {v:"list", cats:CAT_ON.slice(), body:"", picks:[], q:""};
  }
  // "HB 1234", "hb1234" and "1234" all mean the same bill to a person typing
  // it, and none of them is what the attribute holds.
  function norm(s){ return String(s||"").toUpperCase().replace(/[^A-Z0-9]/g,""); }
  // WHICH BOXES A CARD ANSWERS TO. The floor is Session Day. A study or
  // statutory committee is Study Committee whatever kind of meeting it held
  // -- a hearing, a regular meeting -- which its card still says in words. A
  // chamber's committee is each kind its items are, so a day of hearings and
  // then an executive session answers to both boxes.
  function catsOf(e){
    if(isKD(e)) return ["date"];
    if(e.who==="floor") return ["floor"];
    if(e.who==="study") return ["study"];
    var out=[];
    e.kinds.forEach(function(k){ var c=CAT_OF[k]||"work"; if(out.indexOf(c)<0) out.push(c); });
    return out.length?out:["work"];
  }
  function found(e,q){
    if(e.cmte.indexOf(q.toLowerCase())>=0) return true;
    var n=norm(q);
    return !!n && e.bills.some(function(b){ return norm(b).indexOf(n)===0; });
  }
  // THE BOXES, AND THE REST. An entry holding several kinds shows when any
  // of them is ticked, and shows whole. Committees chosen by name show only
  // those committees, still in the kinds ticked -- except that a committee
  // ASKED FOR BY NAME, chosen or found by the search, shows while Study
  // Committee is unticked: that box is off for a reader who has not asked,
  // and somebody who picks the Commission on Aging wants the commission.
  function matches(e,f){
    if(f.picks.length && f.picks.indexOf(e.pick)<0) return false;
    if(f.body && e.body.indexOf(f.body)<0) return false;
    var q=String(f.q||"").trim();
    if(q && !found(e,q)) return false;
    var named=!!f.picks.length||!!q;
    return catsOf(e).some(function(c){ return f.cats.indexOf(c)>=0 || (named&&c==="study"); });
  }
  function sameSet(a,b){
    return a.length===b.length && a.every(function(x){ return b.indexOf(x)>=0; });
  }
  // How far the filters are from where a new reader starts, which is what
  // the reset control answers to...
  function narrowed(f){
    return (!sameSet(f.cats,CAT_ON))+(!!f.body)+(!!f.picks.length)+(!!String(f.q||"").trim());
  }
  // ...and how many of them are down the side, which is what that panel's
  // own button says when a phone folds it away.
  function sideOn(f){ return (!!f.body)+(!!f.picks.length)+(!!String(f.q||"").trim()); }
  // A CANCELLED MEETING IS SHOWN AND NOT COUNTED, as the week's lead counts:
  // "22 sittings" of a week in which 21 met was a wrong number. A KEY DATE
  // IS NOT A MEETING, and is not counted at all.
  function tally(entries,f){
    var t={total:0,shown:0,seen:0,study:0};
    // What ticking Study Committee would add, where it is unticked.
    var g=f.cats.indexOf("study")<0
      ? {picks:f.picks,body:f.body,q:f.q,cats:f.cats.concat(["study"])} : null;
    meetings(entries).forEach(function(e){
      var ok=matches(e,f);
      if(!e.cancelled) t.total++;
      if(ok){ t.seen++; if(!e.cancelled) t.shown++; }
      else if(g && !e.cancelled && matches(e,g)) t.study++;
    });
    return t;
  }
  function countLine(t,where){
    var line;
    // A WEEK OF STUDY COMMITTEES ALONE (the R2 polish batch, 30 October
    // 2026): "None of the 18 meetings this week match." spoke of a filter
    // the reader never set. Where every meeting the boxes hide is a study
    // committee's, the line says only that.
    if(!t.seen && t.study && t.study===t.total)
      return (t.study===1 ? "1 study committee meeting is" : t.study+" study committee meetings are")
        +" hidden.";
    if(t.shown===t.total)
      line=(t.total?plural(t.total,"meeting"):"No meetings")+" "+where+".";
    else if(!t.seen)
      line=t.total===1 ? "The one meeting "+where+" does not match."
                       : "None of the "+t.total+" meetings "+where+" match.";
    else
      line=t.shown+" of "+plural(t.total,"meeting")+" shown"
        +(where==="this week"?"":" "+where)+".";
    // THE HIDDEN STUDY MEETINGS SAY SO. Study Committee starts unticked (the
    // person, 25 September), and 30 of the record's 103 weeks hold nothing
    // else, so a new reader met "None of the 7 sittings this week match."
    // with no word of why. The line says how many the box would show -- and
    // no more since 10 October 2026 (the person: the "tick Study Committee
    // to show them" fragment came off; the box beside it says the rest).
    if(t.study)
      line+=" "+(t.study===1 ? "1 study committee meeting is"
                             : t.study+" study committee meetings are")
        +" hidden.";
    return line;
  }

  // ---- the arrangements --------------------------------------------------------
  //
  // THE LIST: the week page's own rule. Every weekday, an empty one saying so
  // under any filter, because "No meetings scheduled" is true of it whatever
  // is ticked; and a Saturday or Sunday only when something shown is on it.
  // A WEEKDAY THE FILTERS EMPTIED STAYS TOO, MONDAY TO FRIDAY (the approved
  // Calendar of 9 October 2026), saying what was hidden -- "4 study
  // committee meetings are hidden." -- as the Week view's column does. It
  // went, rather than stand as a heading over nothing; with that line it is
  // not over nothing, and a reader can tell a quiet day from a filtered one.
  function listDates(dates,days,f){
    return dates.filter(function(d){
      var day=days[d];
      if(!day) return false;
      if(weekday(d)<5) return true;
      return day.cards.some(function(e){ return matches(e,f); });
    });
  }
  // THE WEEK AT A GLANCE, MONDAY TO FRIDAY (the person, 9 October 2026:
  // "Dont display Saturdays and sundays on the week view, only weekdays since
  // there aren't meetings on the weekend. If that would allow the week view
  // to be displayed like the list and day views which keep the month on the
  // left, that would be preferred"). A Saturday or Sunday is a column only
  // when something shown is on it, or when it is the day the reader chose,
  // so a weekend sitting is never hidden in silence. Counted on 9 October
  // 2026: proceedings.csv has eleven weekend days (1999-2015) and the study
  // committees' copy sixty (1994-2015), and neither has one from the
  // calendar's first week, in January 2025, on.
  function weekCols(dates,days,f,sel){
    return dates.filter(function(d){
      return weekday(d)<5 || d===sel
        || ((days[d]||{}).cards||[]).some(function(e){ return matches(e,f); });
    });
  }
  // A DAY'S COLUMN, ONE LINE PER MEETING (the Week view approved on 9
  // October 2026, "Week tab on the calendar looks good"): the card in brief
  // -- its kinds as the divided bar, the time it starts, the name the card
  // prints, its bill count -- in the card's own order, which is the order the
  // day's sittings start (in_order). THE RECORD HAS NO END TIMES, so nothing
  // is drawn to a length on a clock. The entry is read off the card, as the
  // grid's dots and the preview are, and leads where the card does: to the
  // committee's page at that day, or to the session day's own page. A card
  // with no page to lead to -- a study committee's, a conference's, a
  // session day still to come -- opens in the Day view, where it is whole.
  // The kinds are the bar's colours, and are said in words to a screen
  // reader, as the card's chips say them (a session day's name says it).
  // The chip is components.chip's since Polish 1 ("chip calkind k-hearing"),
  // so the hook is found among the classes rather than first.
  var KIND_CHIP=new RegExp('<span class="(?:[^"]* )?cal'+'kind[^"]*">([^<]*)</span>',"g");
  function entryHtml(e){
    var go=/<p class="calmore"><a href="([^"]+)"/.exec(e.html), n=e.bills.length,
        sum=/<summary>([\s\S]*?)<\/summary>/.exec(e.html), said=[];
    String(sum?sum[1]:"").replace(KIND_CHIP,function(_m,w){
      if(!(e.cancelled&&w==="Cancelled")) said.push(w); return ""; });
    var inner='<span class="wkbar" aria-hidden="true">'
          +(e.kinds.length?e.kinds:["other"]).map(function(k){ return '<i class="k-'+k+'"></i>'; }).join("")
          +'</span><span class="wkx">'+(e.time?'<span class="wkt">'+esc(clock(e.time))+'</span>':"")
          +'<span class="wkc">'+esc(e.name)+'</span>'
          +(e.cancelled?'<span class="wkn">Cancelled</span>':n?'<span class="wkn">'+plural(n,"bill")+'</span>':"")
          +(said.length?'<span class="sr">, '+said.join(", ")+'</span>':"")
          +'</span>';
    // A key date's entry wears its colour (wkkd) and opens its day, where
    // its card says what it is and where it comes from.
    return '<li class="wke'+(isKD(e)?" wkkd":"")+'" data-date="'+esc(e.date)+'" data-cmte="'+esc(e.cmte)+'">'
      +(go?'<a class="wkgo" href="'+go[1]+'">'+inner+'</a>'
          :'<button type="button" class="wkgo" data-open="'+esc(e.date+"|"+e.cmte)+'">'+inner
            +'<span class="sr">: open it in the list</span></button>')+'</li>';
  }
  // What a column says where it shows nothing: that nothing is on, or what
  // the filters hid.
  // ONE LINE A WEEK FOR THE STUDY COMMITTEES, NOT ONE A DAY (18 October
  // 2026). A day the unticked Study Committee box emptied said "4 study
  // committee meetings are hidden.", and in the interim nearly every weekday
  // said it: the clutter the person asked to be rid of. The count is said
  // once, in the week's line (countLine), with the control that shows them
  // beside it; a day says only that nothing is shown.
  //
  // AND IT SAYS WHAT THEY ARE (the R2 polish batch, 30 October 2026): "No
  // meetings shown." on every weekday of a week of study committees alone
  // read as an empty calendar, and the why was 500 pixels away. Still no
  // count -- the week's line keeps that -- but the day says what it holds
  // and "Show them" (emptyHtml) shows them, as the line's own button does.
  function studyOnly(cards,f){
    return !!cards.length && cards.every(function(e){ return e.who==="study"; })
      && f.cats.indexOf("study")<0 && !f.picks.length && !String(f.q||"").trim() && !f.body;
  }
  function emptyWords(cards,f){
    if(!cards.length) return "No meetings";
    if(studyOnly(cards,f)) return "Study committee meetings only.";
    return (cards.length===1?"1 meeting is":cards.length+" meetings are")+" hidden by the filters.";
  }
  function emptyHtml(cards,f){
    return esc(emptyWords(cards,f))+(studyOnly(cards,f)
      ? ' <button type="button" class="calshowday">Show them'
        +'<span class="sr"> (the study committee meetings)</span></button>' : "");
  }
  // THE DAY BEFORE AND AFTER A READER WANTS, for the Day view's Previous Day
  // and Next Day: a Saturday or Sunday with nothing on it is stepped over,
  // as the week no longer shows one. A weekend day whose month has not come
  // is taken as empty: none since the calendar's first week holds anything.
  function stepDay(d,n,days){
    var t=addDays(d,n);
    while(weekday(t)>4 && !((days[t]||{}).cards||[]).length) t=addDays(t,n);
    return t;
  }
  // The day a week opens on, when the address does not name one: today if
  // the week holds it, else its first day with a sitting the filters `f`
  // show, else its first day with any sitting, else its Monday. THE FILTERS'
  // SITTING FIRST since study committees start hidden (25 September 2026): a
  // week whose Monday held only a study commission opened on a day that
  // showed nothing, in the Day view and in the grid.
  // A KEY DATE IS NOT A SITTING: a week opens on its first sitting still,
  // and on its first key date only where it holds no sitting at all.
  function firstDay(key,days,today,first,last,f){
    var mon=keyMonday(key);
    for(var i=0;i<7;i++){ if(addDays(mon,i)===today && today>=first && today<=last) return today; }
    var live=function(e){ return !e.cancelled&&!isKD(e); },
        kd=function(e){ return isKD(e)&&(!f||matches(e,f)); },
        tests=f?[function(e){ return live(e)&&matches(e,f); },live,kd]:[live,kd];
    for(var t=0;t<tests.length;t++)
      for(var j=0;j<7;j++){
        var day=days[addDays(mon,j)];
        if(day && day.cards.some(tests[t])) return addDays(mon,j);
      }
    return mon<first?first:mon;
  }

  // ---- the address ---------------------------------------------------------------
  //
  // ONE ADDRESS, WITH THE WEEK IN ITS QUERY (25 September 2026):
  //   /calendar?week=2026-W28&day=2026-07-09&view=day&kinds=hearing,exec
  // Moving to another week used to push that week's own page's address,
  // /calendar/2026-W12#d=..., so the address a reader reloaded, shared or
  // went Back to named a different page from the one they were reading. The
  // person asked for it to stay put, "for things like indexing and reloading
  // the page": now the calendar keeps its own address and says in the query
  // which week, which day (only where it is not the day the week opens on),
  // which view (only where it is not the list) and which filters (only
  // where a new reader's would differ). The week's own page is what gets
  // indexed and cited, and the canonical link, the og tags, the structured
  // data and the citation go on naming it (rename).
  //
  // A DAY THE CALENDAR HAS. "2026-02-30" has the shape of a date and is not
  // one: taken at its word it opened a Day view of nothing, stuck on
  // "Loading". A day is kept only if it comes back from the arithmetic as
  // itself, and a week only if it is a week; an address that names neither
  // opens as the tab does.
  function isDay(d){
    return /^\d{4}-\d\d-\d\d$/.test(d||"") && iso(+d.slice(0,4),+d.slice(5,7),+d.slice(8,10))===d;
  }
  function isWeek(k){ return /^\d{4}-W\d\d$/.test(k||"") && weekKey(keyMonday(k))===k; }
  var CHAMBER_OF={house:"H",senate:"S",h:"H",s:"S"}, CHAMBER_WORD={H:"house",S:"senate"};
  function uniq(a){ return a.filter(function(x,i){ return a.indexOf(x)===i; }); }
  function readQuery(search){
    var p=new URLSearchParams(String(search||"").replace(/^\?/,"")), s={}, any=false;
    var k=String(p.get("week")||"").toUpperCase(), d=p.get("day")||"";
    if(isWeek(k)){ s.week=k; any=true; }
    if(isDay(d)){ s.d=d; any=true; }
    if(viewOf(p.get("view"))){ s.v=viewOf(p.get("view")); any=true; }
    if(p.has("kinds")){
      s.cats=uniq(String(p.get("kinds")).split(",").filter(function(x){ return CATS.indexOf(x)>=0; }));
      any=true;
    }
    var b=CHAMBER_OF[String(p.get("chamber")||"").toLowerCase()];
    if(b){ s.body=b; any=true; }
    var c=uniq(p.getAll("committee").filter(Boolean));
    if(c.length){ s.picks=c; any=true; }
    if(p.get("q")){ s.q=p.get("q"); any=true; }
    return any?s:null;
  }
  // `day` is left out by the caller where it is the day the week opens on.
  // Commas are the lists' own and are left as commas: kinds=hearing,exec
  // reads, and URLSearchParams takes a comma back as itself.
  function writeQuery(f,week,day){
    var p=new URLSearchParams();
    p.set("week",week);
    if(day) p.set("day",day);
    if(f.v!=="list") p.set("view",f.v);
    if(!sameSet(f.cats,CAT_ON))
      p.set("kinds",CATS.filter(function(c){ return f.cats.indexOf(c)>=0; }).join(","));
    if(f.body) p.set("chamber",CHAMBER_WORD[f.body]);
    f.picks.forEach(function(c){ p.append("committee",c); });
    if(String(f.q||"").trim()) p.set("q",String(f.q).trim());
    return "?"+p.toString().replace(/%2C/gi,",");
  }
  // THE ADDRESS AS IT WAS WRITTEN UNTIL 25 SEPTEMBER, in the hash of a week's
  // own page -- /calendar/2026-W11#d=2026-03-11&v=day&what=hearing -- is
  // still read, so a link sent before then opens what it showed, and the
  // page then writes it into the query. Its filters were two questions, who
  // is meeting and what kind of committee meeting, and they come across as
  // the boxes that answer them now. A hash that said nothing about who
  // leaves Study Committee off, as it is for anybody who has not asked.
  var OLD_WHO=["standing","study","floor"], OLD_WHAT=["hearing","exec","work","conf"];
  function readHash(h){
    var p=new URLSearchParams(String(h||"").replace(/^#/,"")), s={}, any=false;
    function list(k,ok){ return String(p.get(k)||"").split(",").filter(function(x){ return ok.indexOf(x)>=0; }); }
    var d=p.get("d")||"";
    if(isDay(d)){ s.d=d; any=true; }
    if(viewOf(p.get("v"))){ s.v=viewOf(p.get("v")); any=true; }
    if(p.has("who")||p.has("what")){
      var who=p.has("who")?list("who",OLD_WHO):null, what=p.has("what")?list("what",OLD_WHAT):OLD_WHAT;
      s.cats=OLD_WHAT.filter(function(c){ return what.indexOf(c)>=0 && (!who||who.indexOf("standing")>=0); });
      if(!who||who.indexOf("floor")>=0) s.cats.push("floor");
      if(who&&who.indexOf("study")>=0) s.cats.push("study");
      // Those filters could not hide a key date, which had no box then
      // (24 October 2026), so the link shows them as it shows a new reader.
      s.cats.push("date");
      any=true;
    }
    if(p.get("b")==="H"||p.get("b")==="S"){ s.body=p.get("b"); any=true; }
    var c=uniq(p.getAll("c").filter(Boolean));
    if(c.length){ s.picks=c; any=true; }
    if(p.get("q")){ s.q=p.get("q"); any=true; }
    return any?s:null;
  }

  // ---- the month grid and the preview ----------------------------------------------
  function barsOf(entries){
    var seen={};
    entries.forEach(function(e){ if(!e.cancelled) e.kinds.forEach(function(k){ seen[k]=1; }); });
    return BAR_ORDER.filter(function(k){ return seen[k]; });
  }
  // One day of the grid. THE MARKER IS A FEW DOTS IN THE KINDS' COLOURS, not a
  // number the eye has to read; the number is in the cell's name, which is
  // what a screen reader announces. c: {view, sel, focus, today, first, last,
  // days, f}.
  function cellHtml(d,c){
    var on=d>=c.first&&d<=c.last, day=c.days[d],
        all=day?day.cards.filter(function(e){ return matches(e,c.f); }):[],
        vis=meetings(all), kds=all.filter(isKD),
        live=vis.filter(function(e){ return !e.cancelled; }).length,
        cls=["cmday"], name=dateWords(d,"long");
    if(month(d)!==c.view) cls.push("cmout");
    if(d<c.today) cls.push("cmpast");
    if(d===c.today) cls.push("cmnow");
    if(d===c.sel) cls.push("cmpick");
    if(!on){ cls.push("cmoff"); name+=", not on the calendar"; }
    else if(!day) name+=", loading";
    else{
      // "No meetings shown" where the day has meetings the boxes above hide (a
      // study committee's, for a reader who has not ticked them): "no
      // meetings" alone said the day was empty (the audit of 25 October 2026).
      var hidden=day.cards.filter(function(e){ return !isKD(e)&&!e.cancelled&&!matches(e,c.f); }).length;
      name+=", "+(live?plural(live,"meeting"):!hidden?"no meetings"
        :studyOnly(meetings(day.cards),c.f)?"study committee meetings only":"no meetings shown");
      if(vis.length>live) name+=", "+(vis.length-live)+" cancelled";
      // The day's key dates by name: the dot alone says only that one is there.
      kds.forEach(function(e){ name+=", "+e.name; });
    }
    vis=all;
    return '<td role="gridcell" class="'+cls.join(" ")+'" data-d="'+d+'" tabindex="'
      +(d===c.focus?"0":"-1")+'" aria-selected="'+(d===c.sel)+'"'
      +(d===c.today?' aria-current="date"':"")+(on?"":' aria-disabled="true"')+'>'
      +'<span class="cmn" aria-hidden="true">'+(+d.slice(8))+'</span>'
      +'<span class="cmdots" aria-hidden="true">'
      +barsOf(vis).map(function(k){ return '<i class="k-'+k+'"></i>'; }).join("")+'</span>'
      +'<span class="sr">'+esc(name)+'</span></td>';
  }
  function gridHtml(c){
    var sw=weekKey(c.sel);
    return '<thead><tr>'+DAYNAME.map(function(n){
        return '<th scope="col"><span aria-hidden="true">'+n.slice(0,2)
          +'</span><span class="sr">'+n+'</span></th>'; }).join("")+'</tr></thead><tbody>'
      +monthRows(c.view).map(function(r){
        return '<tr class="cmrow'+(weekKey(r[0])===sw?" cmsel":"")+'">'
          +r.map(function(d){ return cellHtml(d,c); }).join("")+'</tr>'; }).join("")
      +'</tbody>';
  }
  // The preview of one day: time, committee and the kind's colour, a handful
  // of them and how many more. c: {days, f}.
  function peekHtml(d,c,cap){
    var day=c.days[d], h='<p class="pkd">'+esc(dayWords(d))+'</p>';
    if(!day) return h+'<p class="pkmore">Loading&hellip;</p>';
    var vis=day.cards.filter(function(e){ return matches(e,c.f); });
    if(!vis.length)
      return h+'<p class="pkmore">'+(meetings(day.cards).length ? esc(emptyWords(meetings(day.cards),c.f))
        : day.cards.length ? "Nothing on this day matches the filters." : "Nothing is scheduled.")+'</p>';
    h+='<ul class="pklist">'+vis.slice(0,cap).map(function(e){
      return '<li><span class="pkbar">'+(e.kinds.length?e.kinds:["other"]).map(function(k){
          return '<i class="k-'+k+'"></i>'; }).join("")+'</span>'
        +'<span class="pkt">'+esc(clock(e.time))+'</span>'
        +'<span class="pkn">'+esc(e.name)+(e.cancelled?' <em>cancelled</em>':"")+'</span></li>';
    }).join("")+'</ul>';
    if(vis.length>cap) h+='<p class="pkmore">and '+(vis.length-cap)+' more</p>';
    return h;
  }
  // The arrow keys of a date grid, as the ARIA date-picker pattern has them.
  function stepKey(d,k,shift){
    switch(k){
      case "ArrowLeft": return addDays(d,-1);
      case "ArrowRight": return addDays(d,1);
      case "ArrowUp": return addDays(d,-7);
      case "ArrowDown": return addDays(d,7);
      case "Home": return monday(d);
      case "End": return addDays(monday(d),6);
      case "PageUp": return shiftMonth(d,shift?-12:-1);
      case "PageDown": return shiftMonth(d,shift?12:1);
    }
    return null;
  }

  var CORE={iso:iso, addDays:addDays, weekday:weekday, monday:monday, weekKey:weekKey,
    keyMonday:keyMonday, month:month, addMonths:addMonths, monthRows:monthRows,
    shiftMonth:shiftMonth, dayWords:dayWords, weekLabel:weekLabel, relWord:relWord, parseCard:parseCard,
    parseDay:parseDay, dayHtml:dayHtml, defaults:defaults, catsOf:catsOf, matches:matches,
    narrowed:narrowed, sideOn:sideOn, tally:tally, countLine:countLine, listDates:listDates,
    weekCols:weekCols, entryHtml:entryHtml, emptyWords:emptyWords, emptyHtml:emptyHtml, stepDay:stepDay,
    firstDay:firstDay, clock:clock,
    isDay:isDay, isWeek:isWeek, readQuery:readQuery, writeQuery:writeQuery, readHash:readHash,
    barsOf:barsOf, cellHtml:cellHtml, gridHtml:gridHtml,
    peekHtml:peekHtml, stepKey:stepKey, CATS:CATS, CAT_ON:CAT_ON,
    isKD:isKD, meetings:meetings};
  G.GRCAL=CORE;

  // ==== THE PAGE ===================================================================
  var app=document.getElementById("calapp");
  if(!app||!app.querySelector) return;
  function $(id){ return document.getElementById(id); }
  function all(root,sel){ return [].slice.call(root.querySelectorAll(sel)); }
  var side=$("calside"), bar=$("calbar"), view=$("calview"), grid=$("cmgrid"),
      mtitle=$("cmtitle"), count=$("wkcount"), form=$("wkfilter"), find=$("wkfind"),
      cats=$("calcats"), key=app.querySelector(".calkey"), peek=$("calpeek"),
      reset=$("calreset"), showst=$("calshowst"),
      cpfind=$("cpfind"), cplist=$("cplist"), cpchosen=$("cpchosen"),
      cpall=$("cpall"), cpstat=$("cpstat"), pickhint=$("pickhint"),
      mfold=$("cmfold"), ffold=$("cffold"),
      head=app.querySelector(".calhead"), h1=head.querySelector("h1"),
      lead=head.querySelector("p.src");
  var HERE=app.getAttribute("data-here"), PAGEWEEK=app.getAttribute("data-week"),
      FIRST=keyMonday(app.getAttribute("data-first")),
      LAST=addDays(keyMonday(app.getAttribute("data-last")),6);
  // TODAY IS THE READER'S, not the build's: the page is read for a week after
  // it is made, and "past" and "today" are about when it is read. The
  // reader's day on purpose; a testimony deadline is Concord's (TWO CLOCKS,
  // ON PURPOSE, at app.js's nhDay).
  var now=new Date(), TODAY=iso(now.getFullYear(),now.getMonth()+1,now.getDate());
  var LASTMONTH=month(LAST)>month(TODAY)?month(LAST):month(TODAY);
  var DAYS={}, WEEKS={}, MONTHS={}, OPEN={list:{},week:{},day:{}}, NAMES=null;
  function inRange(d){ return d>=FIRST&&d<=LAST; }
  function clamp(d){ return d<FIRST?FIRST:d>LAST?LAST:d; }
  // Where a week's own page lives: build_calendar.href_for, which puts the
  // week the build called this one at /calendar. It is what the canonical
  // link and the citation name, and where the arrows go opened in a new tab.
  function hrefFor(k){ return k===HERE?"/calendar":"/calendar/"+k; }
  function pathWeek(){ var m=/\/calendar\/(\d{4}-W\d\d)/.exec(location.pathname); return m?m[1]:HERE; }
  // THE CALENDAR'S OWN ADDRESS, which a move keeps the reader on: /calendar,
  // which Cloudflare Pages answers with calendar.html whatever the query.
  // Where the page was reached by its file's name -- a preview served
  // straight from the folder, which knows nothing of /calendar --
  // /calendar.html, so that a reload there finds the page too.
  var TAB=/\.html$/.test(location.pathname)?"/calendar.html":"/calendar";
  function weekDates(){
    var m=monday(SEL), out=[];
    for(var i=0;i<7;i++){ var d=addDays(m,i); if(inRange(d)) out.push(d); }
    return out;
  }
  function visible(d){ return ((DAYS[d]||{}).cards||[]).filter(function(e){ return matches(e,S); }); }

  // The week this page was built with is in it already: the script starts
  // from those cards and needs no file for them.
  all(view,".calday[data-d]").forEach(function(el){ DAYS[el.getAttribute("data-d")]=parseDay(el.outerHTML); });
  WEEKS[PAGEWEEK]={label:h1.textContent.replace(/^The Week of /,""), lead:lead?lead.textContent:""};

  // ---- where the reader is -------------------------------------------------------
  //
  // AUTO: the day selected is the one its week opens on, not one the reader
  // chose, so the address leaves it out and it follows the week's days as
  // they arrive -- a week named by the address whose month file is still on
  // its way opens on its Monday for a moment, then on its first sitting.
  // A new key for the Study Committee box: the one before it remembered
  // turning study committees OFF, when they were on for everybody.
  var SKEY="gr.calendar.showstudy", S, SEL, VIEWM, FOCUS, AUTO;
  function opening(k){ return clamp(firstDay(k,DAYS,TODAY,FIRST,LAST,S)); }
  // Every day of the week the calendar has is here, so what it opens on is
  // settled. The page's own week is whole as it came: a Saturday or Sunday
  // it does not draw is one with nothing on it.
  function whole(k){
    if(k===PAGEWEEK) return true;
    var mon=keyMonday(k);
    for(var i=0;i<7;i++){ var d=addDays(mon,i); if(inRange(d)&&!DAYS[d]) return false; }
    return true;
  }
  // Where the reader is, from the address: the query, else the hash a link
  // sent before 25 September carries, else the page itself -- a week's own
  // page opens on its week, and the tab on the reader's today. Returns what
  // the state was read from, "" where the address held none.
  function fromLocation(){
    var q=readQuery(location.search), h=q?null:readHash(location.hash), st=q||h||{};
    S=defaults();
    ["v","cats","body","picks","q"].forEach(function(k){ if(k in st) S[k]=st[k]; });
    // STUDY AND STATUTORY COMMITTEES ARE OFF for anybody who has not asked
    // for them, and a reader who ticked the box is remembered in this
    // browser. Storage that is blocked or empty leaves them off; an address
    // that says which kinds to show wins over it.
    if(!("cats" in st)){
      try{ if(localStorage.getItem(SKEY)==="1") S.cats.push("study"); }catch(e){}
    }
    var k=st.week||(st.d?weekKey(st.d):"");
    if(k){
      // A week outside the calendar's range is the nearest one it has.
      k=weekKey(clamp(keyMonday(k)));
      if(st.d&&weekKey(st.d)===k&&inRange(st.d)){ SEL=st.d; AUTO=false; }
      else{ SEL=opening(k); AUTO=true; }
    }else if(/\/calendar\/\d{4}-W\d\d/.test(location.pathname)){
      SEL=opening(pathWeek()); AUTO=true;
    }else{
      // FROM SATURDAY, NEXT WEEK, as the home page's Coming up already does
      // (D13): on a weekend the calendar opened on the week just ended (the
      // review of the release, 8 November 2026).
      var wd=weekday(TODAY), START=wd>=5?addDays(TODAY,7-wd):TODAY;
      SEL=inRange(START)?START:inRange(TODAY)?TODAY:opening(HERE); AUTO=true;
    }
    VIEWM=month(SEL); FOCUS=SEL;
    return q?"query":h?"hash":"";
  }
  // The day for the address: none where it is the one the week opens on.
  function dayParam(){
    if(AUTO) return "";
    var k=weekKey(SEL);
    return whole(k)&&SEL===opening(k)?"":SEL;
  }
  function address(){ return TAB+writeQuery(S,weekKey(SEL),dayParam()); }

  // ---- the month files -------------------------------------------------------------
  function load(m){
    if(MONTHS[m]) return;
    if(m<month(FIRST)||m>month(LAST)){ MONTHS[m]="none"; return; }
    MONTHS[m]="loading";
    fetch("/calendar/data/"+m+".json").then(function(r){
      if(!r.ok) throw new Error("HTTP "+r.status);
      return r.json();
    }).then(function(j){
      var shown=weekDates(), fresh=false;
      Object.keys(j.days||{}).forEach(function(d){
        if(!DAYS[d] && shown.indexOf(d)>=0) fresh=true;
        DAYS[d]=parseDay(j.days[d]);
      });
      Object.keys(j.weeks||{}).forEach(function(k){ WEEKS[k]=j.weeks[k]; });
      MONTHS[m]="ok"; landed(fresh);
    }).catch(function(){ MONTHS[m]="fail"; landed(true); });
  }
  function landed(panel){
    // THE DAY A WEEK OPENS ON FOLLOWS ITS DAYS: its first sitting is known
    // only once they are here. The address does not change, because it
    // never named the day.
    if(AUTO&&whole(weekKey(SEL))){
      var d=opening(weekKey(SEL));
      if(d!==SEL){
        if(VIEWM===month(SEL)) VIEWM=month(d);
        if(FOCUS===SEL) FOCUS=d;
        SEL=d; panel=true;
      }
    }
    drawGrid(); drawHead();
    if(panel) drawPanel(); else drawCount();
    if(peekD) showPeek(peekD,peekFrom);
  }
  // The months the grid and the selected week need now; and a moment later
  // the months either side whose days the grid's first and last rows show,
  // which is all a neighbour is fetched for until the reader goes to it.
  var nearT=0;
  function need(){
    var mon=monday(SEL);
    [VIEWM, month(mon), month(addDays(mon,6))].forEach(load);
    clearTimeout(nearT);
    nearT=setTimeout(function(){
      var rows=monthRows(VIEWM);
      [rows[0][0], rows[rows.length-1][6]].forEach(function(d){ load(month(d)); });
    },600);
  }

  // ---- drawing -----------------------------------------------------------------------
  function drawGrid(focusIt){
    var had=focusIt||grid.contains(document.activeElement);
    // The cell that takes Tab is one the grid is showing.
    if(month(FOCUS)!==VIEWM)
      FOCUS=month(SEL)===VIEWM?SEL:month(TODAY)===VIEWM&&inRange(TODAY)?TODAY:clamp(VIEWM+"-01");
    // A live region, so written only when the month changes: set on every
    // redraw it would say the month again over the count.
    if(mtitle.textContent!==monthWords(VIEWM)) mtitle.textContent=monthWords(VIEWM);
    // aria-disabled, not disabled: a button that disables itself under the
    // reader's finger drops their focus on the page.
    $("cmprev").setAttribute("aria-disabled",VIEWM<=month(FIRST)?"true":"false");
    $("cmnext").setAttribute("aria-disabled",VIEWM>=LASTMONTH?"true":"false");
    grid.innerHTML=gridHtml({view:VIEWM, sel:SEL, focus:FOCUS, today:TODAY,
                             first:FIRST, last:LAST, days:DAYS, f:S});
    grid.setAttribute("aria-busy",MONTHS[VIEWM]==="loading"?"true":"false");
    if(had){ var td=grid.querySelector('td[data-d="'+FOCUS+'"]'); if(td) td.focus(); }
  }
  var NAV=null;
  function drawHead(){
    // THE HEADING NAMES THE WEEK THE ADDRESS DOES, whether or not its month
    // file came. It used to wait for the file, so while one loaded -- and for
    // good when one failed -- the address was the new week while the
    // heading, the tab's title, the citation and the canonical link kept the
    // last week that loaded, over a panel saying "This week could not be
    // loaded". A week's name follows from its key (weekLabel); its lead is
    // the build's, and said plainly where the week is not here to count.
    var k=weekKey(SEL), w=WEEKS[k], label=w?w.label:weekLabel(k);
    h1.textContent="The Week of "+label;
    if(lead) lead.textContent=broken()?"The meetings of this week could not be loaded here."
                                      :w?w.lead:"";
    document.title="The Week of "+label+" | Granite Record";
    rename(k,label);
    // The arrows are written again only when they change -- against what was
    // last written here, not against innerHTML, which a browser hands back
    // with "&lsaquo;" decoded and so never matched. AND FOCUS STAYS ON THE
    // ARROW PRESSED. Paging week to week is the page's keyboard flow, and the
    // link that had focus goes with the old arrows: left there, focus fell to
    // the page, a screen reader said nothing, and Enter again did nothing. The
    // same arrow in the new ones takes it; where that arrow is no more --
    // "This Week" on this week, "Next Week" on the last -- the heading
    // that names the week now shown takes it.
    var html=navHtml(k);
    if(html===NAV) return;
    NAV=html;
    var a=document.activeElement, navs=all(app,".wknav"), at=-1, cls="";
    navs.forEach(function(n,i){ if(a&&a!==n&&n.contains(a)){ at=i; cls=(a.className||"").split(" ")[0]; } });
    navs.forEach(function(n){ n.innerHTML=html; });
    if(at>=0){
      var t=cls?navs[at].querySelector("a."+cls):null;
      if(!t){ h1.tabIndex=-1; t=h1; }
      t.focus();
    }
  }
  // THE PAGE NAMES THE WEEK IT SHOWS, not the week it was loaded as. Moving
  // week in place changed the heading and the tab's title and left the rest
  // naming the old week: "Cite this page" cited 9-15 March at its address
  // while the reader looked at 16-22 March, and the canonical link and
  // og:url -- what a phone's share sheet sends -- said the same. So the
  // citation's four forms, the canonical link, the og tags, the description
  // and the structured data follow the heading, with the address
  // build_calendar gives that week. The citation is shell.py's and is not
  // drawn again here: the week and its address are swapped in the text it
  // already holds, which leaves the reader's own date app.js put in it alone.
  var canon=document.querySelector('link[rel="canonical"]'),
      CANON=canon?canon.getAttribute("href")||"":"",
      ORIGIN=CANON.indexOf("/calendar")>0?CANON.slice(0,CANON.indexOf("/calendar")):location.origin;
  // shell.cite_block's BibTeX key: the address, its slashes as hyphens.
  function citeKey(url){
    return url.slice(ORIGIN.length).replace(/^\/+/,"").replace(/\//g,"-").replace(/\./g,"")||"granite-record";
  }
  var NAMED={label:WEEKS[PAGEWEEK].label, url:CANON||ORIGIN+hrefFor(PAGEWEEK)};
  NAMED.key=citeKey(NAMED.url);
  function swap(s,pairs){
    pairs.forEach(function(p){ if(p[0]&&p[0]!==p[1]) s=s.split(p[0]).join(p[1]); });
    return s;
  }
  function swapText(n,pairs){
    for(var i=0;i<n.childNodes.length;i++){
      var c=n.childNodes[i];
      if(c.nodeType===3){ var t=swap(c.data,pairs); if(t!==c.data) c.data=t; }
      else if(c.nodeType===1) swapText(c,pairs);
    }
  }
  // shell.cite_url's rule, for an address drawn again: a break after each
  // slash past the site's own, and the last part kept whole with what follows
  // it (the full stop, BibTeX's "},") in .citetail. Its <wbr>s split the
  // address across text nodes, so swapText cannot find it there; its span is
  // found by its text -- the address, then only that punctuation -- and
  // redrawn whole.
  function citeUrlFill(span,url,after){
    var m=/^(https?:\/\/[^\/]+\/)([\s\S]+)$/.exec(url);
    span.textContent="";
    if(!m){ span.appendChild(document.createTextNode(url+after)); return; }
    var parts=m[2].match(/[^\/]*\/|[^\/]+$/g);
    span.appendChild(document.createTextNode(m[1]));
    parts.forEach(function(p,i){
      span.appendChild(document.createElement("wbr"));
      if(i<parts.length-1){ span.appendChild(document.createTextNode(p)); return; }
      var tail=document.createElement("span");
      tail.className="citetail"; tail.textContent=p+after;
      span.appendChild(tail);
    });
  }
  function rename(k,label){
    var to={label:label, url:ORIGIN+hrefFor(k)};
    to.key=citeKey(to.url);
    if(to.label===NAMED.label && to.url===NAMED.url) return;
    all(document,".pcite .citeurl").forEach(function(s){
      var t=s.textContent, after=t.slice(NAMED.url.length);
      if(t.slice(0,NAMED.url.length)===NAMED.url && /^[.,}]*$/.test(after)) citeUrlFill(s,to.url,after);
    });
    // The address first and whole: "/calendar" is the start of every week's.
    var pairs=[[NAMED.url,to.url],[NAMED.label,to.label],["{"+NAMED.key+",","{"+to.key+","]];
    all(document,".pcite dd").forEach(function(dd){ swapText(dd,pairs); });
    all(document,'script[type="application/ld+json"]').forEach(function(s){ swapText(s,pairs); });
    [['link[rel="canonical"]',"href"],['meta[property="og:url"]',"content"],
     ['meta[property="og:title"]',"content"],['meta[property="og:description"]',"content"],
     ['meta[name="description"]',"content"]].forEach(function(x){
      all(document,x[0]).forEach(function(el){
        var v=el.getAttribute(x[1])||"", t=swap(v,pairs);
        if(t!==v) el.setAttribute(x[1],t);
      });
    });
    NAMED=to;
  }
  // The week's pager, as week_page writes it, stepping from the day
  // selected: previous on the left, next on the right, each with the week
  // it leads to under it, and This Week between them. IN TITLE CASE, as the
  // person asked on 9 October 2026: "This week should be This Week, The
  // week before should be Previous Week, The week after should be Next
  // Week". A week's short name is its month file's, where that has come, and
  // otherwise Monday to Friday from its key.
  function shortOf(k){ return WEEKS[k]&&WEEKS[k].short?WEEKS[k].short:weekLabel(k,"medium"); }
  function navHtml(k){
    var mon=keyMonday(k), h="", tk=weekKey(clamp(TODAY)), pk=weekKey(addDays(mon,-7)), nk=weekKey(addDays(mon,7));
    if(addDays(mon,-1)>=FIRST)
      h+='<a class="wkprev" data-step="-7" href="'+hrefFor(pk)+'"><span class="wkpw">&lsaquo; Previous Week</span>'
        +'<span class="wkpd">'+esc(shortOf(pk))+'</span></a>';
    if(k!==tk && inRange(TODAY))
      h+='<a class="wkhere" data-today="" href="'+hrefFor(tk)+'">This Week</a>';
    if(addDays(mon,7)<=LAST)
      h+='<a class="wknext" data-step="7" href="'+hrefFor(nk)+'"><span class="wkpw">Next Week &rsaquo;</span>'
        +'<span class="wkpd">'+esc(shortOf(nk))+'</span></a>';
    return h;
  }
  // The days the panel needs and does not have, and whether a month file
  // that should have brought them failed.
  function gone(){
    return weekDates().filter(function(d){ return !DAYS[d] && (weekday(d)<5 || (S.v==="day"&&d===SEL)); });
  }
  function broken(){ return gone().some(function(d){ return MONTHS[month(d)]==="fail"; }); }
  function drawCount(){
    var dates=S.v==="day"?[SEL]:weekDates(), list=[];
    dates.forEach(function(d){ if(DAYS[d]) list=list.concat(DAYS[d].cards); });
    // NOT A COUNT OF DAYS THAT ARE NOT HERE: "No sittings this week", said
    // aloud by the live region while the week loaded or after it failed, was
    // a count of nothing.
    var tl=gone().length?null:tally(list,S);
    var t=broken()?"The meetings could not be loaded."
      :!tl?""
      :countLine(tl, S.v==="day"?"on "+dayWords(SEL):"this week");
    // Said once: a live region repeats whatever it is given.
    if(count.textContent!==t) count.textContent=t;
    // THE WAY TO SHOW THEM, beside the one line that says how many study
    // committee meetings are hidden (18 October 2026), and only while it
    // says so. Outside the live region, so the count is said without it.
    if(showst) showst.hidden=!(tl&&tl.study);
  }
  // A day's key dates come first and are not meetings: a day of key dates
  // alone keeps its own line that no meeting is on it, and a day whose
  // meetings the filters hid says so under the key dates still shown.
  function listView(dates){
    return listDates(dates,DAYS,S).map(function(d){
        var day=DAYS[d], vis=visible(d), mt=meetings(day.cards);
        if(!day.cards.length) return dayHtml(day,vis);
        if(!mt.length) return day.head+kdHtml(vis)+day.tail+"</div>";
        return meetings(vis).length ? dayHtml(day,vis)
          : day.head+kdHtml(vis)+'<p class="calempty">'+emptyHtml(mt,S)+'</p></div>'; }).join("")
      || '<p class="calempty">Nothing this week matches the filters.</p>';
  }
  // THE DAY, with the day either side under it as a pager in the week's
  // words (9 October 2026): "Previous Day" and "Next Day", each with the day
  // it leads to, stepping over a Saturday or Sunday with nothing on it.
  function dayView(){
    var d=SEL, day=DAYS[d], vis=visible(d), p=stepDay(d,-1,DAYS), n=stepDay(d,1,DAYS);
    var step='<nav class="calstep" aria-label="Other days">'
      +(p>=FIRST?'<button type="button" class="wkprev calstepb" data-step="-1" data-to="'+p+'">'
        +'<span class="wkpw">&lsaquo; Previous Day</span><span class="wkpd">'+esc(dayWords(p))+'</span></button>':"")
      +(n<=LAST?'<button type="button" class="wknext calstepb calstepn" data-step="1" data-to="'+n+'">'
        +'<span class="wkpw">Next Day &rsaquo;</span><span class="wkpd">'+esc(dayWords(n))+'</span></button>':"")
      +'</nav>';
    var mt=meetings(day.cards);
    if(day.cards.length && !mt.length) return day.head+kdHtml(vis)+day.tail+"</div>"+step;
    if(!meetings(vis).length)
      return day.head+kdHtml(vis)+'<p class="calempty">'+emptyHtml(mt,S)+'</p></div>'+step;
    return dayHtml(day,vis)+step;
  }
  // THE WEEK: a column a day, Monday to Friday, beside the month as the list
  // and the day are; each column the day's meetings in brief (entryHtml), and
  // its heading the way into that day in full. On a narrow screen the days
  // stand one under another, Monday first (app.css).
  function weekView(dates){
    var cols=weekCols(dates,DAYS,S,SEL);
    return '<div class="wkweek"><ol class="wkdays" style="--cols:'+cols.length+'">'
      +cols.map(function(d){
        var vis=visible(d), mt=meetings(((DAYS[d]||{}).cards)||[]);
        return '<li class="wkcol'+(d===SEL?" wksel":"")+(d<TODAY?" wkpast":"")+'"'
          +(d===TODAY?' aria-current="date"':"")+'><h2 class="wkdh"><button type="button" class="wkday" data-d="'+d+'"'
          // ONE NAME FOR THE BUTTON (the cohesion audit's P-9): its spans were
          // read joined, "Monday Nov 2 : open this day". The label starts with
          // the words on the button, so a voice command naming them still finds it.
          +' aria-label="'+DAYNAME[weekday(d)]+' '+dateWords(d,"short")+(d===TODAY?", today":"")+': open this day">'
          +'<span class="wkdn">'+DAYNAME[weekday(d)]+'</span> '
          +'<span class="wkdd">'+dateWords(d,"short")+(d===TODAY?" · Today":"")+'</span>'
          +'</button></h2>'
          +(vis.length?'<ul class="wkes">'+vis.map(entryHtml).join("")+'</ul>':"")
          +(meetings(vis).length?"":'<p class="wkempty">'+emptyHtml(mt,S)+'</p>')
          +'</li>'; }).join("")
      +'</ol></div>';
  }
  function cardKey(m){ return (m.getAttribute("data-date")||"")+"|"+(m.getAttribute("data-cmte")||""); }
  // FOCUS IS NOT LOST WHEN THE PANEL IS DRAWN AGAIN: whatever held it -- a
  // card, a week's entry, a day's button, a step -- is found in the new
  // drawing and given it back, and failing that the schedule itself takes it.
  function focusMark(){
    var a=document.activeElement;
    if(!a||!view.contains(a)) return null;
    var m=a.closest&&a.closest(".calmeet,.calkd");
    if(m) return {card:cardKey(m)};
    var w=a.closest&&a.closest(".wke");
    if(w) return {entry:cardKey(w)};
    if(a.getAttribute("data-d")) return {day:a.getAttribute("data-d")};
    if(a.getAttribute("data-step")) return {step:a.getAttribute("data-step")};
    return {view:1};
  }
  function refocus(k){
    if(!k) return;
    var t=null;
    if(k.card) all(view,".calmeet,.calkd").some(function(m){
      if(cardKey(m)===k.card){ t=m.querySelector("summary"); return true; } return false; });
    else if(k.entry) all(view,".wke").some(function(w){
      if(cardKey(w)===k.entry){ t=w.querySelector(".wkgo"); return true; } return false; });
    else if(k.day) t=view.querySelector('button[data-d="'+k.day+'"]');
    else if(k.step) t=view.querySelector('[data-step="'+k.step+'"]');
    (t||view).focus();
  }
  function drawPanel(){
    var dates=weekDates(), mark=focusMark(), html, k=weekKey(SEL);
    if(gone().length){
      // Said of the week by its name, with the way to its own page, which
      // holds it whole without this script.
      html=broken()
        ? '<p class="calempty">'+(S.v==="day"?esc(dayWords(SEL)):"The week of "
            +esc(WEEKS[k]?WEEKS[k].label:weekLabel(k)))
          +' could not be loaded here. <a href="'+hrefFor(k)+'">Open '
          +(S.v==="day"?"its week":"it")+' on its own page</a>.</p>'
        : '<p class="calempty">Loading the week&hellip;</p>';
    }else if(S.v==="day") html=dayView();
    else if(S.v==="week") html=weekView(dates);
    else html=listView(dates);
    view.innerHTML=html;
    view.setAttribute("data-view",S.v);
    all(view,".calmeet").forEach(function(m){
      var o=OPEN[S.v][cardKey(m)];
      // EVERY MEETING STARTS SHUT (the owner's walk of dry run 9, 8 November
      // 2026); a reader's own opening is kept.
      m.open=o===undefined?false:o;
      addToCalendar(m);
    });
    // A key date's card opens as a meeting's does; it is not offered for a
    // reader's own calendar, being no sitting with a time.
    all(view,".calkd").forEach(function(m){
      var o=OPEN[S.v][cardKey(m)];
      m.open=o===undefined?false:o;
    });
    all(view,".calday[data-d]").forEach(function(el){
      var d=el.getAttribute("data-d"), r=el.querySelector(".cdrel");
      if(r) r.textContent=relWord(d,TODAY);
      if(d===SEL && S.v==="list") el.classList.add("calsel");
    });
    refocus(mark);
    drawCount();
  }
  function drawAll(){ drawGrid(); drawHead(); drawPanel(); syncControls(); }
  // Bring the selected day into view when it is off the screen: the grid is
  // above the schedule on a phone, and beside a long list on a desktop.
  function reveal(){
    var t=S.v==="list"?view.querySelector(".calday.calsel"):view;
    if(!t||!t.getBoundingClientRect) return;
    var r=t.getBoundingClientRect();
    if(r.top<0||r.top>(window.innerHeight||0)*0.75) t.scrollIntoView({block:"start"});
  }
  // The address for where the reader is, on the calendar's own: pushed for a
  // week, a day or a view, so Back undoes it; put in place of the last for a
  // filter, so Back is not a walk back through every box ticked. A week's own
  // page that the reader moves on from is left behind in the history, and
  // Back returns to it.
  function commit(push,frag){
    var url=address()+(frag||"");
    if(url===location.pathname+location.search+location.hash) return;
    try{ history[push?"pushState":"replaceState"](null,"",url); }catch(e){}
    skipTo();
  }
  // The shell's skip link names the page's own address, and the address may
  // now be another. Left as it was, following it loaded the page as it was
  // first opened and threw the reader's place away; with the query in it, it
  // is a step within this page.
  function skipTo(){
    var s=document.querySelector("a.skip");
    if(s) s.setAttribute("href",location.pathname+location.search+"#results");
  }
  // A KEY PRESSED ON A CONTROL KEEPS THAT CONTROL IN VIEW. A click brings
  // the chosen day into view, which is what a pointer came for. A key press
  // leaves focus where it was -- on the arrow, the grid's day, Today -- and
  // bringing the day into view scrolled that off the screen: after Enter on
  // "The week before" at 1440px the focused arrow was out of sight seven
  // presses in eight. So after a key the control is brought back into view,
  // by the least scroll that shows it, which keeps as much of the day in
  // view as the screen has room for.
  function keepInView(el){
    if(!el||el===document.body||!el.getBoundingClientRect) return;
    var r=el.getBoundingClientRect();
    if(r.top<0||r.bottom>(window.innerHeight||0)) el.scrollIntoView({block:"nearest"});
  }
  // `auto`: the day is the one its week opens on rather than one chosen.
  function select(d,how,kb,auto){
    SEL=clamp(d); FOCUS=SEL; VIEWM=month(SEL); AUTO=!!auto;
    need(); drawGrid(how==="key"); drawHead(); drawPanel(); commit(true);
    if(how==="grid"||how==="key"||how==="nav"||how==="today") reveal();
    if(kb||how==="key") keepInView(document.activeElement);
  }
  // A WEEK, NOT A DAY. The arrows and This week open a week on the day its
  // address would -- today in the current week, else its first sitting --
  // so moving week to week reads /calendar?week=2026-W12 and no more. In the
  // Day view the reader is reading a day, and keeps its weekday.
  function toWeek(step,how,kb){
    if(S.v==="day"){ select(addDays(SEL,step),how,kb); return; }
    select(opening(weekKey(clamp(addDays(SEL,step)))),how,kb,true);
  }

  // ---- the controls ---------------------------------------------------------------
  function syncControls(){
    all(cats,'input[name="cat"]').forEach(function(i){ i.checked=S.cats.indexOf(i.value)>=0; });
    all(form,"[data-body]").forEach(function(b){
      b.setAttribute("aria-pressed",(b.getAttribute("data-body")||"")===S.body?"true":"false"); });
    if(find.value!==S.q) find.value=S.q;
    all(bar,"[data-view]").forEach(function(b){
      b.setAttribute("aria-pressed",b.getAttribute("data-view")===S.v?"true":"false"); });
    cpchosen.innerHTML=S.picks.map(function(n){
      return '<button type="button" class="cpchip" data-name="'+esc(n)+'">'+esc(n)
        +'<span class="sr">: stop showing only this committee</span><span aria-hidden="true"> &times;</span></button>';
    }).join("");
    pickhint.hidden=!S.picks.length;
    all(cplist,"input").forEach(function(i){ i.checked=S.picks.indexOf(i.value)>=0; });
    reset.hidden=!narrowed(S);
    var n=sideOn(S);
    ffold.textContent=(side.classList.contains("ffolded")?"Show the filters":"Hide the filters")
      +(n?" ("+n+" on)":"");
  }
  var CHAMBER={"H":"House","S":"Senate","H S":"House and Senate"};
  var GROUP={standing:"Standing committees and committees of conference",study:"Study and statutory committees",
             floor:"Session days"};
  function drawList(){
    var q=cpfind.value.trim().toLowerCase(), open=cpall.getAttribute("aria-expanded")==="true";
    if(!q&&!open){ cplist.hidden=true; cpstat.textContent=""; return; }
    cplist.hidden=false;
    if(!NAMES){ cplist.innerHTML='<p class="calhint">Loading the committees&hellip;</p>'; return; }
    var rows=NAMES.filter(function(c){ return !q||c[0].toLowerCase().indexOf(q)>=0; }), last="";
    cplist.innerHTML=rows.map(function(c){
      var g=c[1]!==last?'<p class="cpgroup">'+esc(GROUP[c[1]]||"")+'</p>':"";
      last=c[1];
      // The chamber is said once: in the name, where the name carries it
      // ("House Judiciary"), or beside it where it does not -- the
      // committees of conference, which are both chambers'.
      var ch=CHAMBER[c[2]]||"", said=ch&&c[0].indexOf(ch+" ")===0;
      return g+'<label class="calchk cpopt"><input type="checkbox" value="'+esc(c[0])+'"'
        +(S.picks.indexOf(c[0])>=0?" checked":"")+'><span>'+esc(c[0])
        +(ch&&!said?' <span class="cpwho">'+ch+'</span>':"")+'</span></label>';
    }).join("")||'<p class="calhint">No committee on the calendar has that in its name.</p>';
    cpstat.textContent=q?plural(rows.length,"committee")+" match.":"";
  }
  var asked=false;
  function loadNames(){
    if(asked) return;
    asked=true;
    fetch("/calendar/data/committees.json").then(function(r){
      if(!r.ok) throw new Error("HTTP "+r.status); return r.json();
    }).then(function(j){ NAMES=j; drawList(); }).catch(function(){
      asked=false;
      cplist.innerHTML='<p class="calhint">The list of committees could not be loaded.</p>';
    });
  }
  function apply(){
    // THE DAY A WEEK OPENS ON CAN CHANGE WITH THE FILTERS, being its first
    // sitting they show. In the list and the week, where the day is only
    // marked, the mark follows it, and the address still needs no day. In
    // the Day view the day is what is being read: it stays, and from then
    // on the address names it, so a reload opens the day that was on the
    // screen.
    if(AUTO&&whole(weekKey(SEL))){
      var o=opening(weekKey(SEL));
      if(o!==SEL){
        if(S.v==="day") AUTO=false;
        else{ if(VIEWM===month(SEL)) VIEWM=month(o); if(FOCUS===SEL) FOCUS=o; SEL=o; }
      }
    }
    syncControls(); drawGrid(); drawPanel(); commit(false);
    if(peekD) showPeek(peekD,peekFrom);
  }
  function setFold(on,store){
    side.classList.toggle("folded",on);
    mfold.setAttribute("aria-expanded",on?"false":"true");
    mfold.textContent=on?"Show the whole month":"Show only this week";
    if(store){ try{ localStorage.setItem("gr.calendar.fold",on?"1":"0"); }catch(e){} }
  }
  function setFilterFold(on){
    side.classList.toggle("ffolded",on);
    ffold.setAttribute("aria-expanded",on?"false":"true");
    syncControls();
  }

  // ---- the hover preview ---------------------------------------------------------------
  //
  // HALF A SECOND OF REST, THEN ONE ELEMENT MOVED, NOT SEVERAL OPENED. Once a
  // preview is up, the next day the pointer rests on takes it over at once, so
  // crossing the grid never opens and closes a string of them; leaving the
  // grid closes it after a beat. It sits beside the day it describes, never on
  // it, and Escape puts it away. Focus shows the same preview after the same
  // wait. A touch has no hover: a tap selects the day, and that is all.
  var peekD=null, peekFrom="", pendD=null, pendFrom="", peekT=0, coolT=0, hushD=null, touchT=0;
  function cellOf(t){ return t&&t.closest?t.closest("td[data-d]"):null; }
  function wantPeek(d,from){
    clearTimeout(coolT);
    if(d===peekD||d===pendD||d===hushD) return;
    hushD=null; pendD=d; pendFrom=from; clearTimeout(peekT);
    peekT=setTimeout(function(){ pendD=null; showPeek(d,from); }, peekD?80:500);
  }
  function showPeek(d,from){
    var td=grid.querySelector('td[data-d="'+d+'"]');
    if(!td||td.getAttribute("aria-disabled")){ hidePeek(); return; }
    peek.innerHTML=peekHtml(d,{days:DAYS,f:S},5);
    peek.hidden=false; peekD=d; peekFrom=from;
    var r=td.getBoundingClientRect(), w=peek.offsetWidth, h=peek.offsetHeight,
        W=document.documentElement.clientWidth, H=window.innerHeight, x, y;
    if(r.right+8+w<=W-8){ x=r.right+8; y=Math.min(Math.max(8,r.top),H-h-8); }
    else if(r.left-8-w>=8){ x=r.left-8-w; y=Math.min(Math.max(8,r.top),H-h-8); }
    else{
      x=Math.min(Math.max(8,r.left+r.width/2-w/2),W-w-8);
      y=r.bottom+8+h<=H-8?r.bottom+8:r.top-8-h;
    }
    peek.style.left=Math.round(x)+"px"; peek.style.top=Math.round(y)+"px";
    all(grid,'[aria-describedby="calpeek"]').forEach(function(x){ x.removeAttribute("aria-describedby"); });
    if(from==="focus") td.setAttribute("aria-describedby","calpeek");
  }
  function hidePeek(){
    clearTimeout(peekT); pendD=null;
    if(peekD===null) return;
    peek.hidden=true; peekD=null;
    all(grid,'[aria-describedby="calpeek"]').forEach(function(x){ x.removeAttribute("aria-describedby"); });
  }

  // ---- putting a sitting in the reader's own calendar ----------------------
  //
  // THE END TIME IS NOT IN THE RECORD. The docket says when a bill is taken
  // up and never when the committee rises, so every event here is an hour
  // long and says so in its own description. Inventing a plausible end and
  // staying quiet about it would put a number in somebody's calendar that no
  // document supports.
  function two(n){ return (n<10?"0":"")+n; }
  function stamp(date,time,addHours){
    var p=date.split("-"), t=(time||"09:00").split(":");
    var d=new Date(+p[0], +p[1]-1, +p[2], +t[0], +t[1]);
    if(addHours) d.setHours(d.getHours()+addHours);
    return d.getFullYear()+two(d.getMonth()+1)+two(d.getDate())+"T"+
           two(d.getHours())+two(d.getMinutes())+"00";
  }
  function details(m){
    var date=m.getAttribute("data-date"), time=m.getAttribute("data-time");
    // A cancelled meeting is not offered for anybody's calendar.
    if(!date || m.hasAttribute("data-cancelled")) return null;
    var cmte=(m.querySelector(".calcmte")||{}).textContent||"A meeting";
    var kinds=[].slice.call(m.querySelectorAll("summary .calkind"))
                 .map(function(k){return k.textContent;}).join(", ");
    var venue=m.getAttribute("data-venue")||"";
    var bills=(m.getAttribute("data-bills")||"").split(" ").filter(Boolean);
    var last=m.getAttribute("data-last");
    // The times in the words the card uses; the entry's own start and end
    // below are the machine's.
    var said=function(t){ return clock(t).replace(/\u00a0/g," "); };
    var note="New Hampshire General Court. "+(kinds||"Meeting")+
      (bills.length? ". Bills: "+bills.join(", ") : "")+
      (last && last!==time ? ". Items are scheduled from "+said(time)+" to "+said(last) : "")+
      ". The General Court does not publish an end time, so this entry is "+
      "one hour long. Source: graniterecord.org";
    // "Legislative Administration (Executive Session)". This goes into
    // somebody else's calendar, where it sits among entries from their
    // work and their family with no context at all, so it has to read as
    // a title: the committee, then what kind of sitting, in brackets and
    // capitalised. The chips on the page keep sentence case, because
    // there they sit under a heading that supplies the context.
    var titled=kinds.replace(/\w\S*/g,function(w){
      return w.charAt(0).toUpperCase()+w.slice(1);});
    return {title:cmte+(titled?" ("+titled+")":""), venue:venue, note:note,
            start:stamp(date,time,0), end:stamp(date,time,1)};
  }
  function ics(d){
    return ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Granite Record//EN",
            "BEGIN:VEVENT","DTSTART:"+d.start,"DTEND:"+d.end,
            "SUMMARY:"+d.title.replace(/[,;]/g,"\\$&"),
            "LOCATION:"+d.venue.replace(/[,;]/g,"\\$&"),
            "DESCRIPTION:"+d.note.replace(/[,;]/g,"\\$&"),
            "END:VEVENT","END:VCALENDAR"].join("\r\n");
  }
  function addToCalendar(m){
    var d=details(m), box=m.querySelector(".calbody");
    if(!d||!box||box.querySelector(".caladd")) return;
    var p=document.createElement("p");
    p.className="caladd";
    var g="https://calendar.google.com/calendar/render?action=TEMPLATE"+
      "&text="+encodeURIComponent(d.title)+
      "&dates="+d.start+"/"+d.end+
      "&details="+encodeURIComponent(d.note)+
      "&location="+encodeURIComponent(d.venue);
    var o="https://outlook.live.com/calendar/0/deeplink/compose?path=/calendar/action/compose"+
      "&subject="+encodeURIComponent(d.title)+
      "&startdt="+d.start.replace(/(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)/,"$1-$2-$3T$4:$5:$6")+
      "&enddt="+d.end.replace(/(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)/,"$1-$2-$3T$4:$5:$6")+
      "&body="+encodeURIComponent(d.note)+
      "&location="+encodeURIComponent(d.venue);
    p.innerHTML='<span>Add to calendar</span>'+
      '<a rel="nofollow noopener" target="_blank" href="'+g+'">Google</a>'+
      '<a rel="nofollow noopener" target="_blank" href="'+o+'">Outlook</a>'+
      '<a class="calics" href="#">Download</a>';
    p.querySelector(".calics").addEventListener("click",function(e){
      e.preventDefault();
      var blob=new Blob([ics(d)],{type:"text/calendar"});
      var a=document.createElement("a");
      a.href=URL.createObjectURL(blob);
      a.download=(m.getAttribute("data-date")||"meeting")+".ics";
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function(){URL.revokeObjectURL(a.href);},2000);
    });
    box.appendChild(p);
  }

  // ---- wiring ------------------------------------------------------------------------
  var came=fromLocation();
  // The row of boxes takes the place of the key a reader without script is
  // given, and says the same six things.
  side.hidden=false; bar.hidden=false; cats.hidden=false;
  if(key) key.hidden=true;
  app.classList.add("on");
  view.tabIndex=-1;
  // A phone opens on the selected week alone, and the filters shut; a
  // reader's own choice about the month is remembered in this browser.
  var folded=null;
  try{ folded=localStorage.getItem("gr.calendar.fold"); }catch(e){}
  var narrow=!!(window.matchMedia&&window.matchMedia("(max-width:40em)").matches);
  setFold(folded===null?narrow:folded==="1");
  setFilterFold(!!(window.matchMedia&&window.matchMedia("(max-width:63.9375em)").matches)&&!sideOn(S));
  need(); drawAll();
  // An address from before 25 September is written again as the one the
  // calendar uses now, and a query in its own spelling -- keeping a fragment
  // that is not a state, the skip link's #results -- while a week's own page,
  // or the tab, opened plainly, is left as it is until the reader moves. The
  // skip link is pointed at the address either way: the shell wrote it for
  // the page's own, and from /calendar?week=2026-W28 that was another page.
  if(came) commit(false,came==="query"&&location.hash&&!readHash(location.hash)?location.hash:"");
  skipTo();

  grid.addEventListener("click",function(e){
    var td=cellOf(e.target);
    if(!td||td.getAttribute("aria-disabled")) return;
    // The day just chosen is on the panel in full, so the focus the redraw
    // gives its new cell does not open its preview again half a second on.
    hidePeek(); hushD=td.getAttribute("data-d"); select(hushD,"grid");
  });
  grid.addEventListener("keydown",function(e){
    var td=cellOf(e.target);
    if(!td) return;
    var d=td.getAttribute("data-d");
    if(e.key==="Enter"||e.key===" "){
      e.preventDefault();
      if(!td.getAttribute("aria-disabled")) select(d,"key");
      return;
    }
    if(e.key==="Escape"){ hushD=peekD; hidePeek(); return; }
    var n=stepKey(d,e.key,e.shiftKey);
    if(!n) return;
    e.preventDefault();
    n=clamp(n); FOCUS=n;
    // Moving off the week a folded grid shows opens the month again, so the
    // focus never goes somewhere the reader cannot see.
    // Not remembered: the reader asked for a day, not for the month open on
    // every visit. Only the fold's own button changes the default.
    if(side.classList.contains("folded")&&weekKey(n)!==weekKey(SEL)) setFold(false);
    if(month(n)!==VIEWM){ VIEWM=month(n); need(); drawGrid(true); }
    else{
      all(grid,"td[data-d]").forEach(function(x){ x.tabIndex=x.getAttribute("data-d")===n?0:-1; });
      var t=grid.querySelector('td[data-d="'+n+'"]'); if(t) t.focus();
    }
  });
  grid.addEventListener("pointerdown",function(e){ if(e.pointerType==="touch") touchT=Date.now(); });
  // A DAY THAT MOVES UNDER A STILL POINTER HAS NOT BEEN POINTED AT. A click
  // on 12 March scrolled the list to that day; the month, which is sticky,
  // moved up a row under a pointer that had not moved, the browser said the
  // pointer was now over 19 March, and half a second later 19 March's
  // preview opened. A pointer that really moves into a day is reported
  // entering it before the move that took it there is reported (the UI
  // Events order: pointerover, then pointermove), so a pointerover at the
  // very spot of the last move or press is the page moving, not the reader,
  // and is not a request for a preview.
  var PX=null, PY=null;
  function still(e){ return typeof e.clientX==="number" && e.clientX===PX && e.clientY===PY; }
  function notePointer(e){ if(typeof e.clientX==="number"){ PX=e.clientX; PY=e.clientY; } }
  document.addEventListener("pointermove",notePointer,{passive:true});
  document.addEventListener("pointerdown",notePointer,{passive:true});
  grid.addEventListener("pointerover",function(e){
    if(e.pointerType==="touch"||still(e)) return;
    var td=cellOf(e.target); if(td) wantPeek(td.getAttribute("data-d"),"pointer");
  });
  grid.addEventListener("pointerleave",function(){
    clearTimeout(peekT); pendD=null; hushD=null;
    coolT=setTimeout(hidePeek,160);
  });
  grid.addEventListener("focusin",function(e){
    if(Date.now()-touchT<800) return;
    var td=cellOf(e.target); if(td) wantPeek(td.getAttribute("data-d"),"focus");
  });
  grid.addEventListener("focusout",function(e){
    if(e.relatedTarget&&grid.contains(e.relatedTarget)) return;
    // Focus has left the grid, so a preview it asked for and was still
    // waiting on goes too: tabbing through in under half a second left one
    // to open beside a day that no longer had focus, and stay.
    if(pendFrom==="focus"){ clearTimeout(peekT); pendD=null; }
    if(peekFrom==="focus") hidePeek();
  });
  document.addEventListener("keydown",function(e){ if(e.key==="Escape"&&peekD){ hushD=peekD; hidePeek(); } });
  // The preview is placed in the window, so anything that moves the day under
  // it -- the page, or the month's own column scrolling by itself -- puts it away.
  window.addEventListener("scroll",function(){ if(peekD) hidePeek(); },{passive:true});
  side.addEventListener("scroll",function(){ if(peekD) hidePeek(); },{passive:true});

  function turn(n){
    var m=addMonths(VIEWM,n);
    if(m<month(FIRST)||m>LASTMONTH) return;
    VIEWM=m;
    // The month is what was asked for, so a grid folded to one week opens --
    // for now: one tap on an arrow is not a choice about every later visit,
    // so it is not remembered. Only the fold's own button is.
    if(side.classList.contains("folded")) setFold(false);
    need(); drawGrid();
  }
  $("cmprev").addEventListener("click",function(){ turn(-1); });
  $("cmnext").addEventListener("click",function(){ turn(1); });
  // A click that no pointer made -- Enter or Space on the control -- has a
  // detail of 0, and is the keyboard's. Today is the day its week opens on;
  // after the calendar's last week, the last day it has is a day chosen.
  $("cmnow").addEventListener("click",function(e){ select(clamp(TODAY),"today",e.detail===0,inRange(TODAY)); });
  mfold.addEventListener("click",function(){
    var on=!side.classList.contains("folded");
    setFold(on,true);
    // Folded, the grid is the selected week's row, so it shows the month that
    // holds that row: folded over another month it was a row of day names.
    if(on && VIEWM!==month(SEL)){ VIEWM=month(SEL); FOCUS=SEL; need(); drawGrid(); }
  });
  ffold.addEventListener("click",function(){ setFilterFold(!side.classList.contains("ffolded")); });
  $("calskip").addEventListener("click",function(){ view.focus(); view.scrollIntoView({block:"start"}); });

  all(bar,"[data-view]").forEach(function(b){
    b.addEventListener("click",function(){
      var v=b.getAttribute("data-view");
      if(v===S.v) return;
      S.v=v; syncControls(); drawPanel(); commit(true);
    });
  });
  // BACK TO WHERE A NEW READER STARTS: every box ticked but Study
  // Committee, no chamber, no committee chosen and nothing typed. The view
  // and the day stay, being where the reader is rather than a filter.
  reset.addEventListener("click",function(){
    var v=S.v; S=defaults(); S.v=v;
    try{ localStorage.setItem(SKEY,"0"); }catch(e){}
    cpfind.value=""; drawList(); apply();
    // The control goes away with what it undid; the view switch keeps the
    // reader's place rather than dropping focus on the page.
    (bar.querySelector('[aria-pressed="true"]')||view).focus();
  });
  // The row of boxes. The Study Committee box is remembered in this browser;
  // the others are a moment's choice, and the address carries them all.
  cats.addEventListener("change",function(e){
    var t=e.target;
    if(!t||t.name!=="cat") return;
    S.cats=all(cats,'input[name="cat"]').filter(function(i){ return i.checked; })
      .map(function(i){ return i.value; });
    if(t.value==="study"){ try{ localStorage.setItem(SKEY,t.checked?"1":"0"); }catch(e2){} }
    apply();
  });
  // "Show them": the Study Committee box ticked, as a reader's own tick is,
  // remembered the same way, and the focus left on the box, which unticks it.
  // The week line's button and a day's (emptyHtml) alike; a day's leaves the
  // focus on the first meeting it now shows, where the reader is, not on the
  // box at the top of the page (the review of 30 October 2026).
  function showStudy(day){
    var box=cats.querySelector('input[name="cat"][value="study"]');
    if(!box) return;
    box.checked=true;
    if(S.cats.indexOf("study")<0) S.cats.push("study");
    try{ localStorage.setItem(SKEY,"1"); }catch(e2){}
    apply();
    var col=day&&all(view,".wkcol").filter(function(c){
      var k=c.querySelector(".wkday"); return k&&k.getAttribute("data-d")===day; })[0];
    var at=day&&(col ? col.querySelector(".wkgo")
      : view.querySelector('.calday[data-d="'+day+'"] .calmeet summary'));
    (at||box).focus();
  }
  if(showst) showst.addEventListener("click",function(){ showStudy(); });
  form.addEventListener("submit",function(e){ e.preventDefault(); });
  form.addEventListener("change",function(e){
    var t=e.target;
    if(!cplist.contains(t)) return;
    var i=S.picks.indexOf(t.value);
    if(t.checked&&i<0) S.picks.push(t.value);
    if(!t.checked&&i>=0) S.picks.splice(i,1);
    apply();
  });
  all(form,"[data-body]").forEach(function(b){
    b.addEventListener("click",function(){ S.body=b.getAttribute("data-body")||""; apply(); });
  });
  var findT=0;
  find.addEventListener("input",function(){
    clearTimeout(findT);
    findT=setTimeout(function(){ S.q=find.value; apply(); },150);
  });
  cpfind.addEventListener("focus",loadNames);
  cpfind.addEventListener("input",function(){ loadNames(); drawList(); });
  cpall.addEventListener("click",function(){
    var open=cpall.getAttribute("aria-expanded")!=="true";
    cpall.setAttribute("aria-expanded",open?"true":"false");
    cpall.textContent=open?"Hide the list":"Browse every committee";
    loadNames(); drawList();
  });
  cpchosen.addEventListener("click",function(e){
    var b=e.target.closest&&e.target.closest(".cpchip");
    if(!b) return;
    var i=S.picks.indexOf(b.getAttribute("data-name"));
    if(i>=0) S.picks.splice(i,1);
    apply();
    (cpchosen.querySelector(".cpchip")||cpfind).focus();
  });

  view.addEventListener("toggle",function(e){
    var m=e.target;
    if(m&&m.classList&&(m.classList.contains("calmeet")||m.classList.contains("calkd")))
      OPEN[S.v][cardKey(m)]=m.open;
  },true);
  view.addEventListener("click",function(e){
    var b=e.target.closest&&e.target.closest("button");
    if(!b||!view.contains(b)) return;
    if(b.classList.contains("wkday")){
      S.v="list"; syncControls(); select(b.getAttribute("data-d"),"view");
    }else if(b.hasAttribute("data-open")){
      // A week's entry with no page to lead to: its day, with it in full.
      var ck=b.getAttribute("data-open");
      S.v="list"; OPEN.list[ck]=true; syncControls(); select(ck.split("|")[0],"view");
      all(view,".calmeet,.calkd").some(function(m){
        if(cardKey(m)!==ck) return false;
        var sm=m.querySelector("summary"); if(sm) sm.focus();
        if(m.scrollIntoView) m.scrollIntoView({block:"nearest"});
        return true;
      });
    }else if(b.hasAttribute("data-step"))
      select(b.getAttribute("data-to")||addDays(SEL,+b.getAttribute("data-step")),"step");
    else if(b.classList.contains("calshowday")){
      var host=b.closest(".calday,.wkcol"), k=host&&host.querySelector(".wkday");
      showStudy(host&&(host.getAttribute("data-d")||(k&&k.getAttribute("data-d"))));
    }
  });
  // The week's arrows move to the week before or after in place, keeping
  // the view and the filters, on the calendar's own address; opened in a new
  // tab they are plain links to the week's own page still.
  app.addEventListener("click",function(e){
    var a=e.target.closest&&e.target.closest(".wknav a");
    if(!a||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button) return;
    e.preventDefault();
    if(a.hasAttribute("data-today")) select(clamp(TODAY),"nav",e.detail===0,true);
    else toWeek(+a.getAttribute("data-step")||0,"nav",e.detail===0);
  });
  // BACK AND FORWARD. Where the address has not changed what is shown -- the
  // skip link's #results is a step in the history too -- nothing is drawn
  // again, and the month the reader had paged to stays. An entry from before
  // 25 September is written as the address the calendar uses now.
  window.addEventListener("popstate",function(){
    var was=address(), keep=[S,SEL,VIEWM,FOCUS,AUTO], came=fromLocation();
    if(address()===was){ S=keep[0]; SEL=keep[1]; VIEWM=keep[2]; FOCUS=keep[3]; AUTO=keep[4]; return; }
    hidePeek(); need(); drawAll(); skipTo();
    if(came==="hash") commit(false);
  });
})();
