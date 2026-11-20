// ======================================================= report a problem ==
//
// A box at the foot of a record's own page. It posts to /api/report
// (functions/api/report.js), the one thing on this site that runs.
//
// OUTSIDE #results, deliberately. Every tab click redraws #results, so a box
// inside it would lose whatever the reader had typed the moment they checked
// another tab to see if the problem was there too.
//
// WHAT IT SENDS is only what the page already knows -- the record, its
// address, the open tab, what kind of thing is wrong (from the list), the
// reader's words, the build the page came from, and how long the box was open
// -- plus an empty field no person fills in. Nothing identifies the reader,
// and the box says there is no way to reply.
//
// IF THE SEND FAILS, the reader keeps their words and gets an email link with
// the same facts filled in, so a broken endpoint costs them a click, not a
// retyping. With no JavaScript there is no box, and the footer's address is
// the whole feature, as it was before.
const REPORT_FIELDS=[["date","A date"],["status","The status"],["sponsor","A sponsor"],
  ["vote","A vote or its count"],["hearing","A hearing, its day or its time"],
  ["committee","A committee"],["text","The bill text or an amendment"],["link","A link"],
  ["chapter","The chapter of law"],["veto","A veto message"],["topic","The topic"],
  ["fiscal","The fiscal note"],["other","Something else"]];
const REPORT_TO="contact@graniterecord.org";
// The tabs the pages render. The Function accepts no other value, so a tab
// renamed here and not there sends "", rather than having the report dropped.
// HEARINGS, AS THE TAB IS NAMED (8 October 2026). The bill's third tab was
// renamed from Videos and this list was not, so a report sent from it named
// no tab at all. The Function still takes "Videos" from a page loaded before
// the rename and stores it as "Hearings" (report.js RENAMED_TABS), and a
// committee's "Sessions", the Meetings tab's name before D19, as "Meetings".
// A COMMITTEE'S VIDEOS TAB, AND A STUDY COMMITTEE'S (the walk of 31 October
// 2026): a tab of its own since the Videos section, and missing here, so a
// report from it named no tab. report.js renames "Videos" only on a bill.
const REPORT_TABS=new Set(["Summary","Bill Text","Votes","Hearings","Reports","Sponsors",
  "Documents","Related","History","Prime sponsored","Co-sponsored","Bills","Meetings","Videos",
  "Elections"]);
let reportBuild=null;       // site/build.json's "finished", fetched once, on first open

function reportBox(kind,ref){
  return `<details class="report" data-rkind="${esc(kind)}" data-rref="${esc(ref)}">
  <summary>${icon("report")}<span>Report<span class="rpw"> a problem</span></span></summary>
  <form class="reportform" novalidate>
    <p class="reportwhat">Tell us what is wrong and we will check it against the official record.
    Nothing here identifies you, which also means we cannot reply: for an answer, write to
    <a href="mailto:${REPORT_TO}">${REPORT_TO}</a>.</p>
    <p><label>What is wrong<br><select name="field"><option value="">Choose one</option>${
      REPORT_FIELDS.map(([v,t])=>`<option value="${v}">${t}</option>`).join("")}</select></label></p>
    <p><label>What does the record say instead?<br>
    <textarea name="note" rows="4" maxlength="1000"></textarea></label></p>
    <p style="position:absolute;left:-9999px" aria-hidden="true"><label>Leave this empty
    <input name="website" tabindex="-1" autocomplete="off"></label></p>
    <p><button type="submit">Send</button> <span class="reportstate" role="status" aria-live="polite"></span></p>
  </form></details>`;
}

// SHARE, BESIDE IT (the person, 9 October 2026: "add a share button
// alongside the report button with the same thing in mind"). The browser's
// own share sheet, with the page's title and address, where the browser has
// one; where it has none, or the sheet fails for any reason but the reader
// closing it, the address is copied and the line beside the button says so.
// Nothing is loaded from anywhere and nothing is counted: no share service,
// no tracking parameter on the address.
function shareBox(){
  return `<button type="button" class="pshare" data-share>${icon("share")}Share</button>`+
    `<span class="sharestate" role="status" aria-live="polite"></span>`;
}

// THE ACTIONS ARE ONE STACK IN THE RECORD'S HEAD (the record head of the
// component plan, C6, and the person's option E: "Actions stacked on the
// right on a desktop", in a row below the rail on a phone): Cite this page,
// Follow, Print (a bill's), Share and Report a problem, in that order, each
// the quiet action button. shell.py writes the row (#pageacts) with Cite in
// it; Follow goes in after Cite (mountFollow), and Print, Share and Report a
// problem after Follow, here; a bill of the sitting term has Testify between
// Follow and Print (mountTestify, 25 October 2026). The row is moved into
// the head each time the head is drawn (placeActions) and out of the way
// before the record is drawn
// again (parkActions), so it is one row a page, whatever is open in it or
// typed into it. A page from an older build, with no row, keeps the old
// arrangement below the record.
function printBox(){
  return `<button type="button" class="pshare pprint" data-print>${icon("print")}Print</button>`;
}
// A static page that writes its own Share (a session day's, a study
// committee's) asks for Report a problem alone (`share` false), into the
// same row, after Share, as a bill's has it.
function mountReport(kind,ref,share=true){
  if(document.getElementById("reportbox"))return;
  const res=$("#results");
  const acts=document.getElementById("pageacts");
  if(!res&&!acts)return;
  const div=document.createElement("div");
  div.id="reportbox";
  div.innerHTML=(kind==="bill"&&acts?printBox():"")+(share?shareBox():"")+reportBox(kind,ref);
  if(acts){div.className="inacts";acts.appendChild(div);}
  else res.after(div);
}
// A BILL OPENED FROM THE SEARCH HAS ITS ROW TOO (the person, 10 October
// 2026: "some bill pages are missing the action buttons like print, report,
// and share entirely"). focusBill draws the bill under its own address
// without loading its page, and the row was mounted only on a page that
// loaded as a bill's (GR_BILL), so every bill reached from the list had no
// Cite, Follow, Print, Share or Report. Its own page's row is fetched -- Cite
// as the build wrote it, and the bill's feed -- and the rest mounted into it
// as on that page; the row goes when the list comes back (dropFocusActions).
let focusActs=null;
function dropFocusActions(){
  if(!focusActs)return;
  focusActs=null;
  const a=document.getElementById("pageacts");
  if(a&&a.dataset.focus)a.remove();
}
// KEPT UNDER THE BILL, NOT ITS NUMBER: its year and number, as the record is
// (dkey). Under the number alone, history taken straight from 2025's HB 703
// to 2020's drew 2020's record under 2025's Cite and Report, since the row
// for "HB703" was already up (the review of 6 November 2026).
function focusActions(id){
  const y=yearOf(id), k=`${y}/${id}`;
  if(window.GR_STANDALONE||PAGE||focusActs===k)return;
  dropFocusActions();
  if(!y||document.getElementById("pageacts")||typeof fetch!=="function"||typeof DOMParser==="undefined")return;
  focusActs=k;
  const path=`bill/${y}/${String(id).toLowerCase()}`;
  fetch(`${BASE}${path}`).then(r=>r.ok?r:fetch(`${BASE}${path}.html`)).then(r=>r.ok?r.text():Promise.reject(r.status)).then(html=>{
    if(focusActs!==k||focused!==id||document.getElementById("pageacts"))return;
    const doc=new DOMParser().parseFromString(html,"text/html");
    const acts=doc.getElementById("pageacts");
    if(!acts)return;
    const feed=doc.querySelector('link[rel="alternate"][type="application/rss+xml"]');
    const row=document.importNode(acts,true);
    row.dataset.focus="1";
    // as the page's own script does on load: the day read, and Copy shown
    row.querySelectorAll(".citeday").forEach(x=>{
      x.textContent=x.classList.contains("citefull")?citeDayFull(new Date()):citeDay(new Date());});
    row.querySelectorAll("[data-citecopy]").forEach(x=>{x.hidden=false;});
    const res=$("#results");
    if(!res)return;
    res.before(row);
    mountFollow(feed?"bill":"",feed?feed.getAttribute("href"):"",`${y}/${id}`);
    mountReport("bill",`${y}/${id}`);
    // Testify too, for a bill of the sitting term, as render() draws it on
    // the bill's own page (the person, 25 October 2026). Which row -- HB 104
    // is a bill of every term -- is mountTestify's to decide, by the record's
    // own term, and nobody else's: this hands it the number alone.
    mountTestify({id,n:id},detail[dkey(id)]);
    placeActions();
  }).catch(()=>{if(focusActs===k)focusActs=null;});
}
// The row, out of the record before the record is drawn again, and into the
// head once it is drawn. The template's hidden <h1> gives way to the head's.
// HIDDEN WHILE THE LIST IS DRAWN (`hide`): a bill's own page that goes back
// to the list for a search has no record on it to cite, print, share or
// report, and the row stood over the first card (the look of 10 October 2026).
function parkActions(hide){
  const a=document.getElementById("pageacts"), r=$("#results");
  if(a&&r&&r.contains(a)){r.before(a);a.classList.remove("inhead");}
  if(a)a.hidden=!!hide;
}
function placeActions(){
  const a=document.getElementById("pageacts");
  const slot=document.querySelector("#results .rhead .racts");
  if(a)a.hidden=false;
  if(a&&slot&&a.parentNode!==slot){slot.appendChild(a);a.classList.add("inhead");}
  if(document.querySelector("#results .rh1")){
    const sr=document.querySelector("main > h1.sr");
    if(sr)sr.hidden=true;
  }
}
// PRINT, on a bill's own page: the print sheet (print.js, GRPrint.open),
// fetched the first time it is asked for, with the record this page holds.
document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest("[data-print]");
  if(!b)return;
  const id=focused||String(window.GR_BILL||"").split("/").pop().toUpperCase();
  const d=detail[dkey(id)];
  if(!d||d._error)return;
  const row=IDX.find(x=>x.id===id&&(!d.term||x.term===d.term))||{id,n:id,chip:""};
  const go=()=>{try{GRPrint.open(d,row,{});}catch(err){b.disabled=false;}};
  if(typeof GRPrint!=="undefined")return go();
  b.disabled=true;
  const sc=document.createElement("script");
  sc.src="/print.js";
  sc.onload=()=>{b.disabled=false;go();};
  sc.onerror=()=>{b.disabled=false;};
  document.head.appendChild(sc);
});

// The address shared is the one in the bar -- a tab's own address where a
// tab is open -- without a fragment, which only scrolls this reader's page;
// but with #v-<id>, which names the recording chosen on a Videos view.
function shareCopy(b,url){
  const st=b.parentNode&&b.parentNode.querySelector(".sharestate");
  const say=t=>{if(st)st.textContent=t;};
  const shown=()=>say(`Copy this address: ${url}`);
  say("");   // emptied first, so a second press is said again
  if(navigator.clipboard&&navigator.clipboard.writeText)
    return navigator.clipboard.writeText(url).then(()=>say("Link copied"),shown);
  shown();
  return Promise.resolve();
}
document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest("[data-share]");
  if(!b)return;
  const url=/^#v-/.test(location.hash)?location.href:location.href.split("#")[0];
  if(navigator.share){
    navigator.share({title:document.title,url}).catch(err=>{
      if(!err||err.name!=="AbortError")shareCopy(b,url);});
    return;
  }
  shareCopy(b,url);
});

// FOLLOW, WHERE THERE IS SOMETHING TO FOLLOW. A record's page names its feed
// in its head exactly where the build writes one -- a bill still moving, a
// member with a vote or a bill, a committee not archived (shell.py decides
// all three) -- so the control reads that link and asks nothing else. Email
// is offered beside it only where it works (followMail, below).
const FOLLOWS={bill:"each new action, hearing and vote on this bill",
  lsr:"one email when this request is drafted into a bill, and from then on the bill itself",
  member:"this member's newest votes and the bills they put their name to",
  committee:"each day this committee sits, and what it does with each bill",
  law:"each of this term's bills that would change this chapter, as it is filed, heard, voted on and decided"};
// EMAIL, BESIDE RSS (FOLLOW.md; the person's accounts of 11 October 2026).
// The box is drawn only where it can work: the sign-up answers (the
// deployment has the follow database bound, which production does not until
// go-live) and tonight's /changes/current.json lists this record as
// followable. Asked once, when Follow is first opened, so no page pays for
// it on load. The Turnstile widget's site key is public.
const FOLLOW_SITEKEY="0x4AAAAAAFTdC20uymy0Ut8h";
const FOLLOW_SAID={invalid:"That does not look like an email address.",
  check:"The check that you are a person did not finish. Please try again.",
  waiting:"Checking that you are a person…",
  broken:"The check that you are a person could not run on this page",
  "not-followable":"This can no longer be followed by email.",
  busy:"Too many sign-ups today. Please try again tomorrow.",
  // Not "the feed above still is" (16 October 2026): the feed has sat below the
  // email box since 12 October, and a law has no feed at all.
  unavailable:"Email updates are not working right now. Please try again later."};
// How often, in the manage page's own words (manage.js, "How often"), so the
// confirmation says what the reader chose the way the page that changes it
// later will. preflight holds the two to the same words.
const FOLLOW_OFTEN={daily:"About 8:00 a.m. New Hampshire time, only on days when something is new",
  weekly:"Saturday about 8:00 a.m.: the week ahead, then the week's news"};
function mountFollow(kind,feed,ref){
  const link=feed?null:document.querySelector('link[rel="alternate"][type="application/rss+xml"]');
  const res=$("#results");
  // A LAW HAS NO FEED (11 October 2026): its Follow is email alone, and is
  // drawn only once the email box can work there (followMail).
  if(!kind||!res||document.getElementById("followbox"))return;
  // A REQUEST HAS NONE EITHER (its feed starts with its bill).
  if(kind!=="law"&&kind!=="lsr"&&!(feed||link))return;
  const href=feed||(link&&link.getAttribute("href"))||"";
  const div=document.createElement("div");
  div.id="followbox";
  div.className="followrow";
  div.dataset.fkey=kind&&ref?`${kind}:${ref}`:"";
  // BESIDE "CITE THIS PAGE", in the row shell.py writes above the heading,
  // where there is one (every page built since 24 September): one row of
  // quiet controls rather than two stacked. A page from an older build has no
  // row, and Follow makes its own as it always did.
  const acts=document.getElementById("pageacts");
  if(acts)div.className="followin";
  // THE ADDRESS TO COPY, AND NOTHING THAT OPENS THE FEED (the person,
  // 16 October 2026). "Open the feed" sat beside Copy the address, and on a
  // phone it showed the feed's raw XML, which reads as a broken page. A feed
  // is for a feed reader, which wants its address, so the pane gives the
  // address in its box and a button to copy it; a reader whose browser
  // follows feeds finds this one named in the head of the record's own page.
  // Only there: a bill focused in the search list has its feed from the page
  // focusActions fetched, and the search page's head does not name it.
  // RSS IS DRAWN OPEN, AND FOLDED ONLY ONCE EMAIL ARRIVES (the person,
  // 18 October 2026). Email is the default way to follow, so where the
  // email box is drawn the feed moves under "Follow by RSS instead"
  // (followMail). Until then -- and for good on a deployment that cannot take
  // email, which is production until go-live -- the feed is the pane's only
  // content, and folding it would leave a pane with nothing in it but a
  // disclosure to open.
  if(href)div.dataset.feed=href;
  div.innerHTML=`<details class="follow"><summary>${icon("follow")}Follow</summary>
    <div class="followpane"><div class="followmail" hidden></div>${href?`<div class="followrss">${followRss(kind,href,false)}</div>`:""}
    </div></details>`;
  if(acts){const c=acts.querySelector(".pcite");acts.insertBefore(div,c?c.nextSibling:acts.firstChild);}
  else res.before(div);
}
// The feed's part of the pane: open, or folded under a disclosure of its own
// beneath the email box. Folded, its summary already says "by RSS", so the
// sentence starts at the feed reader rather than saying it twice.
function followRss(kind,href,folded){
  const what=esc(FOLLOWS[kind]||"what is new here");
  const body=`<p>${folded?"In":"<b>By RSS</b>, in"} any feed reader: ${what}.</p>
      <p class="feedurl"><input type="text" readonly aria-label="The feed's address"
        value="${esc(new URL(href,location.origin).href)}">
        <button type="button" class="link" data-copyfeed="1">Copy the address</button></p>`;
  return folded?`<details class="followalt"><summary>Follow by RSS instead</summary>
    <div class="followaltbody">${body}</div></details>`:body;
}
// EMAIL FOLLOWING IS IN BETA UNTIL THE WEBINAR (the person, 26 October
// 2026: "Email following can maybe have a disclosure that email following is
// in beta testing right now until the webinar so folks know that even though
// it's live, things may be changing day by day"). One line in the small
// print, src/pages/words/follow_beta.json's, which every email that follows
// sends says too (site.gen.js's FOLLOW_BETA). It retires on its "until", the
// day after the webinar of 10 November, as the home page's webinar box does:
// data-until, which components.js's behaviour judges by the reader's date.
function followBeta(){
  const b=WORDBOOK.follow_beta;
  return b&&b.note?`<p class="panfine followbeta"${untilAttrs(b.until)}>${esc(b.note)}</p>`:"";
}
function followMailForm(key){
  // ONE PANEL WITH CHOOSING YOUR TOWN (the person's choice A, 14 October
  // 2026): a heading, one sentence, one field and its button, and the
  // promises in the small print under them -- the same words as before.
  // DAILY OR WEEKLY BESIDE THE ADDRESS (the person, 16 October 2026), Daily
  // chosen, just before the button: the manage page's own control, in its
  // words and its markup (manage.js, "How often"), so the sign-up and the
  // page that changes it later ask the same question the same way. Before
  // this a sign-up was always daily. A div, not a p, holds the row: a
  // fieldset is not allowed inside a p, and the parser would close the p
  // before it and leave the button outside the row.
  return `<form class="followform" novalidate>
    <p class="panh">Follow by email</p>
    <p class="pansay">Daily or weekly: ${esc(FOLLOWS[key.split(":")[0]]||"what is new here")}.</p>
    <div class="followaddr"><label><span class="sr">Your email address</span>
      <input type="email" name="email" autocomplete="email" maxlength="254" required
        placeholder="you@example.com"></label>
      <fieldset class="followfreq"><legend class="sr">Send me updates</legend>
        <label><input type="radio" name="frequency" value="daily" checked><span>Daily</span></label>
        <label><input type="radio" name="frequency" value="weekly"><span>Weekly</span></label></fieldset>
      <button type="submit" class="followsend">Email me updates</button></div>
    <p class="panfine">Nothing is sent until you confirm. Every email lets you change what you follow or
      unsubscribe.</p>
    ${followBeta()}
    <p style="position:absolute;left:-9999px" aria-hidden="true"><label>Leave this empty
    <input name="website" tabindex="-1" autocomplete="off"></label></p>
    <div class="followcheck"></div>
    <p class="followstate" role="status" aria-live="polite"></p>
  </form>
  <div class="followdone" hidden></div>`;
}
let turnstileLoad=null;
function turnstileReady(){
  if(window.turnstile)return Promise.resolve(window.turnstile);
  if(!turnstileLoad)turnstileLoad=new Promise((ok,no)=>{
    const sc=document.createElement("script");
    sc.src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit";
    sc.async=true;sc.onload=()=>window.turnstile?ok(window.turnstile):no(new Error("turnstile"));
    sc.onerror=()=>{turnstileLoad=null;no(new Error("turnstile"));};
    document.head.appendChild(sc);
  });
  return turnstileLoad;
}
function followMail(box){
  const key=box.dataset.fkey||"", slot=box.querySelector(".followmail");
  if(!key||!slot||box.dataset.mail)return;
  box.dataset.mail="asked";
  Promise.all([followUp(),fetch("/changes/current.json")])
    .then(([up,cur])=>up&&cur.ok?cur.json():null)
    .then(cur=>{
      if(!cur||!cur.followable||!Object.prototype.hasOwnProperty.call(cur.followable,key))return;
      slot.innerHTML=followMailForm(key);
      slot.hidden=false;
      box.dataset.mail="shown";
      // Email drawn, the feed folds under it (mountFollow says why only now).
      const rss=box.querySelector(".followrss");
      if(rss&&box.dataset.feed)rss.innerHTML=followRss(key.split(":")[0],box.dataset.feed,true);
      // The email box arrives after the pane opened, and lengthens it.
      paneInView(box.querySelector(".followpane"));
      followCheck(slot.querySelector(".followcheck"));
    }).catch(()=>{});
}
// THE CHECK IS WAITED FOR (the person's dry run of 12 October 2026, where
// "interaction-only" hid the widget as it ran and a press of the button
// before it had finished sent no token, which the sign-up can only call a
// failed check). The widget now stays in view, the button waits for its token,
// and a widget that cannot run says so with Turnstile's own error code --
// 110200 is a hostname the widget was not given -- instead of sending a form
// that is bound to be refused.
const FOLLOW_TS=new WeakMap();
function followCheck(w){
  if(!w||FOLLOW_TS.has(w))return;
  const st={token:"",err:"",wait:[]};
  FOLLOW_TS.set(w,st);
  const settle=()=>{const q=st.wait;st.wait=[];q.forEach(f=>f());};
  turnstileReady().then(t=>{
    w.dataset.widget=t.render(w,{sitekey:FOLLOW_SITEKEY,size:"flexible",action:"follow",
      "refresh-expired":"auto",
      callback:tok=>{st.token=tok||"";st.err="";settle();},
      "expired-callback":()=>{st.token="";},
      "error-callback":code=>{st.token="";st.err=String(code||"unknown");settle();}});
  }).catch(()=>{st.err="script";settle();});
}
function followToken(w,ms){
  const st=w&&FOLLOW_TS.get(w);
  if(!st)return Promise.resolve({err:"script"});
  if(st.token||st.err)return Promise.resolve({token:st.token,err:st.err});
  return new Promise(ok=>{
    const done=()=>{clearTimeout(tm);ok({token:st.token,err:st.err||(st.token?"":"timeout")});};
    const tm=setTimeout(()=>{st.wait=st.wait.filter(f=>f!==done);done();},ms);
    st.wait.push(done);
  });
}
function followUsed(w){
  const st=w&&FOLLOW_TS.get(w);
  if(st)st.token="";
  if(window.turnstile&&w&&w.dataset.widget)try{window.turnstile.reset(w.dataset.widget);}catch(_){}
}
// A PANE THAT OPENS BELOW THE FOLD IS BROUGHT INTO VIEW (the webinar's phone
// check, 16 October 2026). Follow's and Cite's panes hang under their buttons,
// and on a phone with the action row near the foot of the screen Follow's
// opened at y=842 of 812: the press seemed to do nothing. The window moves
// only as far as shows the pane, and only when some of it is out of sight;
// the button pressed stays where the reader's finger is whenever the pane
// fits below it.
function paneInView(p){
  if(!p||typeof p.getBoundingClientRect!=="function")return;
  (window.requestAnimationFrame||setTimeout)(()=>{
    const r=p.getBoundingClientRect(), h=window.innerHeight||0;
    if(h&&(r.bottom>h||r.top<0))
      p.scrollIntoView({block:r.height>h?"start":"nearest",behavior:"smooth"});
  });
}
document.addEventListener("toggle",e=>{
  const d=e.target;
  if(d.classList&&d.classList.contains("follow")&&d.open){
    const box=d.closest("#followbox,.followbox");
    if(box)followMail(box);
  }
  if(d.open&&d.classList&&(d.classList.contains("follow")||d.classList.contains("pcite")
      ||d.classList.contains("testify")))
    paneInView(d.querySelector(".followpane,.citebody,.testifypane"));
  // The feed opened under the email box lengthens the pane in the same way.
  if(d.open&&d.classList&&d.classList.contains("followalt"))
    paneInView(d.closest(".followpane"));
},true);
// The line under the button: a word of progress, or a refusal drawn as one.
function followSay(st,words,bad){
  if(!st)return;
  st.textContent=words;
  if(st.classList)st.classList.toggle("followerr",!!(bad&&words));
}
// SENDING… ON THE BUTTON, AND ONE REQUEST AT A TIME (the person, 18 October
// 2026). The button is the thing just pressed, so it is where the press is
// seen to have been taken; and a second press or Enter while the first is
// out would ask for a second confirmation email with a token Turnstile has
// already spent, which the sign-up can only refuse. The form's own flag
// holds the line even where the disabled button would not -- Enter in the
// address field submits on its own.
function followBusy(form,btn,on){
  if(on)form.dataset.busy="1";else delete form.dataset.busy;
  if(on)form.setAttribute("aria-busy","true");else form.removeAttribute("aria-busy");
  if(btn){btn.disabled=on;btn.textContent=on?"Sending…":"Email me updates";}
}
// CHECK YOUR EMAIL, IN PLACE OF THE FORM (the person, 18 October 2026: "once
// you click submit for your email, the display doesn't look like much
// happened if anything because only the text below it changes"). A sign-up
// taken is a different pane: a heading that says what to do, the address
// the link went to -- where a mistyped one is caught, since the answer is
// the same for every address -- what to do with the email, and how often
// the reader chose. It stays until they ask to enter an address again. The
// keyboard is put on the heading, so a screen reader says it at once and
// Tab carries on from there. The form is hidden rather than removed, and
// with it the Turnstile widget, which is neither reset nor drawn again: the
// widget starting over as the pane said "on its way" is what made a sign-up
// that went through look as if it had failed.
function followDone(form,email,freq){
  const done=form.parentNode&&form.parentNode.querySelector(".followdone");
  if(!done)return;
  done.innerHTML=`<h2 class="panh" tabindex="-1">Check your email</h2>
    <p class="pansay">A link to confirm is on its way to <b class="followto">${esc(email)}</b>.</p>
    <ol class="followsteps">
      <li>Open the email from Granite Record and use its link to confirm. Nothing is sent until you do.</li>
      <li>It can take a minute or two to arrive. If it has not come, look in your spam or junk folder.</li>
    </ol>
    <p class="followoften">You chose <b>${freq==="weekly"?"Weekly":"Daily"}</b>
      (${esc((FOLLOW_OFTEN[freq]||FOLLOW_OFTEN.daily).replace(/^About\b/,"about"))}).
      Every email has a link to change it.</p>
    <p class="panfine">Wrong address? <button type="button" class="link" data-followagain="1">Enter it again</button></p>`;
  form.hidden=true;
  done.hidden=false;
  const h=done.querySelector(".panh");
  if(h&&h.focus)h.focus();
  paneInView(form.closest(".followpane"));
}
// Sent through the page's one submit listener, the report box's, below.
async function followSubmit(e,form){
  e.preventDefault();
  if(form.dataset.busy)return;
  const box=form.closest("#followbox,.followbox"), st=form.querySelector(".followstate");
  const btn=form.querySelector(".followsend"), w=form.querySelector(".followcheck");
  const [kind,...rest]=(box&&box.dataset.fkey||"").split(":");
  const email=form.elements.email.value.trim();
  if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)){followSay(st,FOLLOW_SAID.invalid,true);return;}
  followBusy(form,btn,true);
  followSay(st,FOLLOW_SAID.waiting,false);
  const {token:pass,err}=await followToken(w,20000);
  if(!pass){
    followSay(st,err&&err!=="timeout"?`${FOLLOW_SAID.broken} (Turnstile ${err}).`:FOLLOW_SAID.check,true);
    followBusy(form,btn,false);return;
  }
  followSay(st,"Sending…",false);
  // The radio that is checked; daily where none is, which is what the
  // sign-up makes of a request that names none.
  const fq=form.querySelector('input[name="frequency"]:checked');
  const freq=fq&&fq.value==="weekly"?"weekly":"daily";
  let said="", took=false;
  try{
    const r=await fetch("/api/follow/signup",{method:"POST",headers:{"Content-Type":"application/json"},
      body:JSON.stringify({email,kind,ref:rest.join(":"),frequency:freq,turnstile:pass,
        website:form.elements.website.value})});
    const j=await r.json().catch(()=>({}));
    took=r.status===202;
    if(!took){
      said=FOLLOW_SAID[j.why]||FOLLOW_SAID.unavailable;
      if(j.why==="check"&&Array.isArray(j.codes)&&j.codes.length)
        said=`${said.replace(/\.$/,"")} (Turnstile ${j.codes.map(String).join(", ")}).`;
    }
  }catch(_){said=FOLLOW_SAID.unavailable;}
  followBusy(form,btn,false);
  // The token went with the request either way and is not sent twice.
  const ts=w&&FOLLOW_TS.get(w);
  if(ts)ts.token="";
  if(took){followSay(st,"",false);followDone(form,email,freq);return;}
  // A REFUSAL KEEPS THE ADDRESS AND ASKS FOR A NEW CHECK (18 October 2026).
  // What was typed stays in the box to send again, and only here is the
  // widget reset: the next press needs a token of its own.
  followSay(st,said,true);
  followUsed(w);
}
// ENTER IT AGAIN: the form back as it was, its address kept to correct, and
// a fresh check for the new request -- the one place outside a refusal that
// the widget is reset, since the last token went with the request taken.
document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest("[data-followagain]");
  if(!b)return;
  const slot=b.closest(".followmail"), form=slot&&slot.querySelector(".followform");
  const done=slot&&slot.querySelector(".followdone");
  if(!form||!done)return;
  done.hidden=true;
  form.hidden=false;
  followSay(form.querySelector(".followstate"),"",false);
  followUsed(form.querySelector(".followcheck"));
  const input=form.elements.email;
  if(input&&input.focus){input.focus();if(input.select)input.select();}
});

document.addEventListener("click",e=>{
  const b=e.target.closest&&e.target.closest("[data-copyfeed]");
  if(!b)return;
  const input=b.parentNode.querySelector("input");
  const done=()=>{b.textContent="Copied";setTimeout(()=>{b.textContent="Copy the address";},2000);};
  const pick=()=>{input.focus();input.select();};
  if(navigator.clipboard&&navigator.clipboard.writeText)
    navigator.clipboard.writeText(input.value).then(done,pick);
  else pick();
});

// THE RECORD'S OWN ADDRESS, WHATEVER TAB IS OPEN (30 October 2026). A tab
// writes its name into the address (tabAddress: /bill/2026/hb1/votes,
// /committee/H05/sessions), and report.js takes a report only from the
// record's own address, so a report sent from any tab but the first was
// dropped while the reader was thanked. The tab goes as the payload's tab.
function reportPath(){
  const p=location.pathname.replace(/\.html$/,""),m=TAB_PATH.exec(p);
  return m&&isTabSlug(m[2].toLowerCase())?m[1]:p.replace(/\/$/,"");
}
function reportFallback(form,payload,why){
  const st=form.querySelector(".reportstate");
  const subject=`Problem on ${location.hostname}${payload.url}`;
  const body=`${payload.note}\n\n--\npage: ${location.origin}${payload.url}\n`+
    `record: ${payload.record}\nwhat: ${payload.field}\ntab: ${payload.tab||"-"}\nbuild: ${payload.build||"-"}\n`;
  st.innerHTML=`That did not send (${esc(why)}). Your words are still in the box. `+
    `<a href="mailto:${REPORT_TO}?subject=${encodeURIComponent(subject)}&amp;body=${encodeURIComponent(body)}">Send it by email instead</a>.`;
}

document.addEventListener("toggle",e=>{
  const box=e.target;
  if(!box.classList||!box.classList.contains("report")||!box.open)return;
  const form=box.querySelector(".reportform");
  if(form&&!form.dataset.opened)form.dataset.opened=String(Date.now());
  if(reportBuild===null){
    reportBuild="";
    fetch("/build.json").then(r=>r.ok?r.json():{}).then(d=>{reportBuild=String((d&&d.finished)||"");})
      .catch(()=>{});
  }
},true);

document.addEventListener("submit",async e=>{
  const ff=e.target.closest&&e.target.closest(".followform");
  if(ff)return followSubmit(e,ff);
  const form=e.target.closest&&e.target.closest(".reportform");
  if(!form)return;
  e.preventDefault();
  const box=form.closest(".report"), st=form.querySelector(".reportstate");
  const btn=form.querySelector("button[type=submit]");
  const note=form.elements.note.value.trim();
  if(!form.elements.field.value){st.textContent="Choose what is wrong from the list.";return;}
  if(note.length<3){st.textContent="Say in a few words what is wrong.";return;}
  const tab=document.querySelector('.tabs .tab[aria-selected="true"]');
  // The label without its count, in any locale's way of writing a number.
  const tabLabel=tab?tab.textContent.trim().replace(/\s*\([\d.,\s']+\)\s*$/,""):"";
  const payload={
    record:`${box.dataset.rkind}:${box.dataset.rref}`,
    url:reportPath(),
    tab:REPORT_TABS.has(tabLabel)?tabLabel:"",
    field:form.elements.field.value,
    note,
    build:reportBuild||"",
    elapsed:Date.now()-(+form.dataset.opened||Date.now()),
    website:form.elements.website.value};
  btn.disabled=true;
  st.textContent="Sending…";
  const ctl=new AbortController();
  const timer=setTimeout(()=>ctl.abort(),6000);
  try{
    const r=await fetch("/api/report",{method:"POST",signal:ctl.signal,
      headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});
    // 503 and 429 are the Function's two answers for a report it accepted and
    // could not keep (functions/api/report.js) -- storage down, and the day's
    // ceiling reached -- so each gets words a reader can use. Where the zone's
    // rate rule in front of the Function answers 429 as well, the same words
    // are as true of it. Any other failure still offers the email address.
    if(!r.ok)throw new Error(r.status===503?"the site could not save it just now":
      r.status===429?"the site is taking no more reports just now":
      `the server answered ${r.status}`);
    form.elements.note.value="";
    st.textContent="Thank you. It will be checked against the record.";
  }catch(err){
    reportFallback(form,payload,err&&err.name==="AbortError"?"no answer in six seconds":
      (err&&err.message)||"no connection");
  }finally{
    clearTimeout(timer);
    btn.disabled=false;
  }
});

