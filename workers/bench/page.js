/*
 * The bench's one page, /bench, answered by functions/bench.js: no file in
 * site/, no link from any page, not in the sitemap, noindex. Its address is
 * /bench#<token>; the token never leaves the browser but in the body of the
 * page's own requests. It is taken out of the address bar as soon as the page
 * reads it -- YouTube's player API sends the page's whole address to YouTube
 * -- and kept on the device (localStorage, "gr.bench"; the owner, 21 November
 * 2026: "Make it remember the link on each device"), so a bookmark of /bench,
 * a new tab or a reload opens it again. A token in the address always wins and
 * replaces the kept one. The device forgets it when the bench answers it 404 (a
 * link turned off, or a wrong one) and when "Forget this link on this
 * device" is pressed, for a shared computer.
 *
 * WHAT IT IS (the design of 17 November 2026 and its mockups): one item, and
 * only its evidence. A timing: the bill, the proceeding, the day, and the
 * recording, cued 8 seconds before the site's time in YouTube's player (the
 * youtube-nocookie player the bill pages use), with -10 s / Play from <the
 * site's time> / +10 s under it; two steps, the start and then the end, where
 * a No asks for the real moment, marked off the player's own clock. A topic
 * or a tag: the bill's title and the drafters' analysis. One question, put so
 * that Yes means the site is right, and NO ANSWER CHOSEN IN ADVANCE. Three
 * large answers where a thumb rests -- No left, Not sure, Yes right -- the
 * arrow keys on a keyboard, and a swipe across the card (never on the
 * player, and only one more across than down). "Saved: Yes -- Undo" for six
 * seconds (Z). A thin bar for the group being worked on, this sitting's
 * answers a lighter part of it; when a group is full the next one simply
 * follows: no score, no streak, no screen between groups. Under the item,
 * how far along each queue is. The owner's link adds the Links tab.
 *
 * Light and dark in the site's palette (site.gen.js PAGE_PALETTE, read from
 * app.css), and the site's three faces. Every value written into the page
 * goes through esc(); the card's words are the pack's, and are escaped all the
 * same. Nothing in it names a state: a card carries its own words.
 */

import { pageResponse } from "./common.js";
import { PAGE_PALETTE } from "../follow/site.gen.js";

export function nonce() {
  let s = "";
  for (const x of crypto.getRandomValues(new Uint8Array(16))) s += String.fromCharCode(x);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// The bench's own tokens beside the site's: the recording's film, this
// sitting's lighter part of the bar, the site's time on the player, a
// paused link's amber, and the second rule.
const OWN = {
  light: { "rule-2": "#B2B7BD", film: "#111416", "film-ink": "#C8CFD1", mine: "#7DB0A8", mark: "#E0B84C",
           amber: "#7A5A00", "amber-soft": "#FBF2D9" },
  dark: { "rule-2": "#525C5D", film: "#000000", "film-ink": "#C8CFD1", mine: "#C4E4DF", mark: "#E0B84C",
          amber: "#E9C46A", "amber-soft": "#3A3016" },
};
const tokens = theme => Object.entries({ ...PAGE_PALETTE[theme], ...OWN[theme] })
  .map(([k, v]) => `--${k}:${v};`).join("");

const STYLE = `
:root{${tokens("light")}
--sans:"Public Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
--serif:"Source Serif 4",Georgia,serif;--brand:"Playfair Display",Georgia,serif;--r-in:3px;--r-out:6px}
@media (prefers-color-scheme:dark){:root{${tokens("dark")}}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.5 var(--sans)}
button,select,input{font:inherit;color:inherit}
button{cursor:pointer}
[hidden]{display:none!important}
:focus-visible{outline:2px solid var(--pine);outline-offset:2px}
.top{position:sticky;top:0;z-index:5;background:var(--paper);border-bottom:1px solid var(--rule)}
.top .in{max-width:760px;margin:0 auto;padding:10px 16px 9px}
.row1{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:40px}
.brand{font:600 18px/1.1 var(--brand);white-space:nowrap}
.brand span{font:500 13px/1 var(--sans);color:var(--ink-2);margin-left:6px;letter-spacing:.02em}
.kind{font:500 14px/1.2 var(--sans);border:1px solid var(--edge);border-radius:var(--r-in);background:var(--surface);
padding:6px 8px;min-height:36px;max-width:52vw}
.tabs{display:flex;gap:4px}
.tabs button{font:600 14px/1 var(--sans);color:var(--ink-2);background:none;border:0;padding:10px 12px 11px;
border-bottom:3px solid transparent}
.tabs button[aria-current]{color:var(--pine);border-bottom-color:var(--pine)}
.chooser{margin-top:8px}
.track{height:6px;background:var(--wash);border-radius:999px;overflow:hidden;display:flex;margin-top:10px}
.track i{display:block;height:100%}
.track .done{background:var(--pine)}
.track .mine{background:var(--mine);transition:width .25s ease}
.plabel{display:flex;justify-content:space-between;gap:10px;margin-top:6px;font:500 13px/1.3 var(--sans);color:var(--ink-2)}
.plabel b{color:var(--ink);font-weight:600}
.plabel .you::before{content:"";display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--mine);
margin-right:5px;vertical-align:0}
main{max-width:760px;margin:0 auto;padding:14px 16px 150px}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-out);padding:16px 16px 18px;
touch-action:pan-y;transition:transform .18s ease,opacity .18s ease}
.card.out-r{transform:translateX(40%);opacity:0}
.card.out-l{transform:translateX(-40%);opacity:0}
.head{font:600 13px/1.35 var(--sans);color:var(--ink-2);margin:0 0 4px;letter-spacing:.01em}
.title{font:600 19px/1.35 var(--serif);margin:0 0 12px}
.label{font:600 12px/1 var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);margin:16px 0 7px}
.prose{font:400 17px/1.6 var(--serif);margin:0;white-space:pre-line}
.claimline{margin:16px 0 0;font:400 16px/1.45 var(--sans)}
.claimline b{font-variant-numeric:tabular-nums}
.def{margin:6px 0 0;color:var(--ink-2);font:400 15px/1.45 var(--sans)}
.q{font:600 21px/1.3 var(--serif);margin:18px 0 0}
.q .claim{color:var(--pine);font-weight:600;text-decoration:underline;text-decoration-thickness:2px;
text-underline-offset:4px;text-decoration-color:var(--mine)}
.meta{font:500 13px/1.35 var(--sans);color:var(--ink-2);margin:0 0 6px}
.billtitle{font:400 15px/1.4 var(--sans);color:var(--ink-2);margin:0 0 12px;display:-webkit-box;-webkit-line-clamp:2;
-webkit-box-orient:vertical;overflow:hidden}
.player{position:relative;aspect-ratio:16/9;background:var(--film);border-radius:var(--r-out);overflow:hidden;margin:2px 0 10px}
.player iframe,.player>div{position:absolute;inset:0;width:100%;height:100%;border:0}
.ctl{display:grid;grid-template-columns:64px 1fr 64px;gap:8px}
.ctl button{min-height:44px;border:1px solid var(--edge);border-radius:var(--r-in);background:var(--surface);
font:600 15px/1.1 var(--sans);font-variant-numeric:tabular-nums}
.ctl .play{background:var(--pine-soft);color:var(--pine);border-color:var(--pine)}
.steps{display:flex;gap:6px;align-items:center;margin:16px 0 0;font:600 12px/1 var(--sans);letter-spacing:.06em;
text-transform:uppercase;color:var(--ink-2)}
.steps i{display:inline-block;width:22px;height:4px;border-radius:2px;background:var(--wash)}
.steps i.on{background:var(--pine)}
.notebtn{margin:14px 0 0;padding:0;border:0;background:none;color:var(--pine);font:600 14px var(--sans);
text-decoration:underline;text-underline-offset:3px}
.notebox{margin:12px 0 0}
.notebox input,.better select{width:100%;min-height:44px;padding:8px 10px;border:1px solid var(--edge);
border-radius:var(--r-in);background:var(--surface);font-size:16px}
.notebox small,.better small{display:block;margin-top:5px;color:var(--ink-2);font-size:13px}
.better{margin:16px 0 0;padding:14px;border:1px dashed var(--rule-2);border-radius:var(--r-out)}
.better .label{margin-top:0}
.answers{position:fixed;left:0;right:0;bottom:0;z-index:6;background:var(--paper);border-top:1px solid var(--rule);
padding:10px 16px calc(10px + env(safe-area-inset-bottom))}
.answers .row{max-width:728px;margin:0 auto;display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}
.answers .row.two{grid-template-columns:1fr 1.6fr}
.ans{min-height:58px;border-radius:var(--r-out);font:600 17px/1.1 var(--sans);border:1.5px solid var(--edge);
background:var(--surface);display:flex;align-items:center;justify-content:center;gap:8px;padding:0 8px;white-space:nowrap}
@media (max-width:389px){.ans{font-size:16px;gap:5px;padding:0 4px}.answers .row{gap:8px}}
.ans svg{width:18px;height:18px;flex:none}
.ans.no{border-color:var(--brick);color:var(--brick)}
.ans.yes,.ans.markit{background:var(--pine);border-color:var(--pine);color:var(--on-pine)}
.ans.markit{font-variant-numeric:tabular-nums}
.ans:disabled{opacity:.55;cursor:default}
.keys{max-width:760px;margin:8px auto 0;font:500 12px/1 var(--sans);color:var(--ink-2);display:none;
justify-content:center;gap:16px;flex-wrap:wrap}
@media (hover:hover) and (pointer:fine){.keys{display:flex}}
kbd{font:600 11px/1 var(--sans);border:1px solid var(--rule-2);border-bottom-width:2px;border-radius:3px;padding:2px 5px;
background:var(--surface);color:var(--ink);margin-right:3px}
.toast{position:fixed;left:50%;transform:translateX(-50%);bottom:94px;z-index:7;background:var(--ink);color:var(--paper);
border-radius:var(--r-out);padding:10px 14px;font:500 14px/1.2 var(--sans);display:flex;gap:16px;align-items:center;
box-shadow:0 6px 18px rgba(0,0,0,.25);white-space:nowrap;max-width:calc(100vw - 32px)}
.toast button{background:none;border:0;color:inherit;font:700 14px var(--sans);text-decoration:underline;
text-underline-offset:3px;padding:4px 0}
.far{margin:22px 0 0}
.far h2{font:600 12px/1 var(--sans);letter-spacing:.08em;text-transform:uppercase;color:var(--ink-2);margin:0 0 10px}
.far ul{list-style:none;margin:0;padding:0}
.far li{display:grid;grid-template-columns:7rem 1fr 6.5rem;gap:10px;align-items:center;padding:6px 0;font:500 14px/1.2 var(--sans)}
.far li .tr{height:5px;background:var(--wash);border-radius:999px;overflow:hidden}
.far li .tr i{display:block;height:100%;background:var(--pine);min-width:2px}
.far li span:last-child{text-align:right;color:var(--ink-2);font-size:13px;font-variant-numeric:tabular-nums}
.small{color:var(--ink-2);font-size:13px;line-height:1.45;margin:14px 0 0}
.empty{padding:28px 18px}
.empty h1{font:600 24px/1.25 var(--serif);margin:0 0 8px}
.lede{color:var(--ink-2);margin:0 0 16px;font-size:15px}
h1.page{font:600 28px/1.2 var(--serif);margin:4px 0 4px}
.box{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-out);padding:14px 16px;margin:0 0 12px}
.new{display:grid;gap:10px}
.new input[type=text]{width:100%;min-height:44px;padding:8px 10px;border:1px solid var(--edge);border-radius:var(--r-in);
background:var(--surface);font-size:16px}
.checks{display:flex;flex-wrap:wrap;gap:8px}
.checks label{display:flex;align-items:center;gap:6px;border:1px solid var(--edge);border-radius:var(--r-in);padding:7px 10px;
font:500 14px/1.2 var(--sans);background:var(--surface)}
.checks input{accent-color:var(--pine);width:16px;height:16px;margin:0}
.btn{min-height:42px;padding:0 14px;border-radius:var(--r-in);border:1px solid var(--edge);background:var(--surface);
font:600 14px/1 var(--sans)}
.btn.primary{background:var(--pine);border-color:var(--pine);color:var(--on-pine)}
.btn.warn{color:var(--brick);border-color:var(--brick)}
.made{border:1px solid var(--pine);background:var(--pine-soft)}
.made p{margin:0 0 8px}
.url{font:500 14px/1.4 ui-monospace,"Cascadia Mono",Consolas,monospace;word-break:break-all;background:var(--surface);
border:1px solid var(--rule-2);border-radius:var(--r-in);padding:8px 10px;margin:0 0 10px}
.acts{display:flex;gap:8px;flex-wrap:wrap}
.link{padding:0}
.link .who{display:flex;justify-content:space-between;align-items:baseline;gap:10px;padding:14px 16px 0}
.link .who b{font:600 19px/1.25 var(--serif)}
.state{font:600 12px/1 var(--sans);letter-spacing:.05em;text-transform:uppercase;padding:4px 7px;border-radius:var(--r-in);
white-space:nowrap}
.state.active{background:var(--pine-soft);color:var(--pine)}
.state.paused{background:var(--amber-soft);color:var(--amber)}
.state.owner,.state.off{background:var(--wash);color:var(--ink-2)}
.link .meta{padding:4px 16px 0;font-size:14px;margin:0}
.nums{display:grid;grid-template-columns:repeat(3,1fr);margin:12px 0 0;border-top:1px solid var(--rule)}
.nums div{padding:10px 16px;border-left:1px solid var(--rule)}
.nums div:first-child{border-left:0}
.nums b{display:block;font:600 18px/1.2 var(--sans);font-variant-numeric:tabular-nums}
.nums span{font-size:12.5px;color:var(--ink-2);line-height:1.3;display:block}
.link .acts{padding:12px 16px 14px;border-top:1px solid var(--rule)}
.said{list-style:none;margin:0;padding:0 16px;border-top:1px solid var(--rule)}
.said li{display:grid;grid-template-columns:1fr auto;gap:4px 10px;padding:10px 0;border-bottom:1px solid var(--rule);font-size:14.5px}
.said li:last-child{border-bottom:0}
.said .what{font-weight:600}
.said .how{color:var(--ink-2);grid-column:1}
.said .v{font:600 13px/1 var(--sans);padding:4px 7px;border-radius:var(--r-in);align-self:start;justify-self:end}
.v.yes{background:var(--pine-soft);color:var(--pine)}.v.no{background:var(--brick-soft);color:var(--brick)}
.v.unsure{background:var(--wash);color:var(--ink-2)}
.said .one{grid-column:2;justify-self:end;background:none;border:0;color:var(--pine);font:600 13px var(--sans);
text-decoration:underline;padding:0}
.merge{border-left:4px solid var(--pine);background:var(--pine-soft);padding:12px 14px;border-radius:var(--r-in);margin:16px 0 0;
font-size:15px}
.forget{margin:24px 0 0}
.forget button{min-height:44px;padding:0;border:0;background:none;color:var(--ink-2);font:500 14px/1.2 var(--sans);
text-decoration:underline;text-underline-offset:3px}
.merge code{font:500 13px/1.4 ui-monospace,"Cascadia Mono",Consolas,monospace;display:block;margin-top:6px;word-break:break-all}
@media (prefers-reduced-motion:reduce){.card,.track .mine{transition:none}}
`;

const FONTS = `<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=Playfair+Display:wght@600&display=swap" rel="stylesheet">`;

// The words the page itself says. A card's words are the pack's.
const NEEDS_LINK = "This page needs a link";
const NEEDS_WORDS = "Open the private link you were sent once on this device, and this page will remember it.";
const FORGET = "Forget this link on this device";
const FORGET_ASK = "Forget this link on this device? To open the bench here again, you will need the link.";
const KEPT = "Your answers are kept with this link, and nothing else about you is. Answers and notes become " +
  "part of Granite Record’s open data, with no name on them.";

// THE PAGE'S SCRIPT, in one function under the answer's nonce. String.raw, so
// the page receives its backslashes as written.
//
// The card has three parts: #head (what is being judged), #player (YouTube's
// player and the bench's own controls, made once and kept between items, so
// a new recording is cued rather than loaded again) and #body (the step, the
// question, a better answer, the note). The answers are #answers, pinned to
// the foot of the screen.
export const SCRIPT = String.raw`(function(){
"use strict";
// THE TOKEN LEAVES THE ADDRESS AT ONCE. YouTube's player API sends the page's whole
// address to YouTube when it makes the player (its forigin), and the address held the
// token after "#" (seen on 17 November 2026). So it is read, taken out of the address
// bar before anything else runs, and kept on this device (localStorage), so /bench
// alone opens it again here; nowhere else, and never sent but in a request's body. A
// token in the address replaces the kept one; one a tab kept before (sessionStorage,
// until 21 November 2026) moves to the device.
var T=(location.hash||"").replace(/^#(t=)?/,"");
if(location.hash){try{history.replaceState(null,"",location.pathname+location.search);}catch(e){}}
var KEY="gr.bench",was="";try{was=sessionStorage.getItem("bench")||"";}catch(e){}
try{if(!T)T=localStorage.getItem(KEY)||was;if(T)localStorage.setItem(KEY,T);if(was)sessionStorage.removeItem("bench");}catch(e){if(!T)T=was;}
// The device forgets the link: when the bench answers it 404, and when asked to.
function forget(){T="";try{localStorage.removeItem(KEY);}catch(e){}try{sessionStorage.removeItem("bench");}catch(e){}
var f=document.getElementById("forget");if(f)f.hidden=true;}
var $=function(id){return document.getElementById(id);};
var E={"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"};
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return E[c];});}
function hms(x){x=Math.max(0,Math.round(Number(x)||0));var h=Math.floor(x/3600),m=Math.floor(x%3600/60),s=x%60;
return (h?h+":"+(m<10?"0":"")+m:m)+":"+(s<10?"0":"")+s;}
function num(n){return Number(n||0).toLocaleString("en-US");}
var MONTHS=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function day(d){var m=/^(\d{4})-(\d\d)-(\d\d)/.exec(d||"");return m?(+m[3])+" "+MONTHS[+m[2]-1]:"";}
var ICON={no:'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/></svg>',
yes:'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>',
unsure:'<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7.2 7.4a2.9 2.9 0 1 1 4.1 2.6c-.8.4-1.3 1-1.3 1.9v.4" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/><circle cx="10" cy="15.6" r="1.25" fill="currentColor"/></svg>',
mark:'<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="10" cy="10" r="2.6" fill="currentColor"/></svg>'};
var SAID={yes:"Yes",no:"No",unsure:"Not sure"};
// What the page holds: the last view the bench gave; the item shown, the
// step it is on and the answers given to its steps; the mode (ask, mark,
// better); whether the note is open; this sitting's answers by group.
var S={view:null,queue:"mix",item:null,step:0,steps:[],mode:"ask",note:false,you:{},busy:false,
tab:"judge",links:null,made:null,open:{},label:"",saved:null,toastT:0};
var TOAST_MS=6000,HOLD_EVERY=120000,LEAD=8,SWIPE=80;

function api(path,body){var b={t:T};for(var k in body)if(Object.prototype.hasOwnProperty.call(body,k))b[k]=body[k];
return fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(b),
credentials:"same-origin",cache:"no-store"}).then(function(r){return r.text().then(function(x){
var d=null;try{d=JSON.parse(x);}catch(e){}return {status:r.status,data:d};});},function(){return {status:0,data:null};});}

// ---- the recording: YouTube's player API, the youtube-nocookie player -------
var YTP=null,ytReady=false,ytWant=null,ytAsked=false,ytVideo="";
function ytLoad(){if(ytAsked)return;ytAsked=true;window.onYouTubeIframeAPIReady=function(){
YTP=new YT.Player("yt",{host:"https://www.youtube-nocookie.com",videoId:ytWant.id,
playerVars:{start:ytWant.start,rel:0,playsinline:1,origin:location.origin},
events:{onReady:function(){ytReady=true;ytVideo=ytWant.id;}}});};
var s=document.createElement("script");s.src="https://www.youtube.com/iframe_api";document.head.appendChild(s);}
// The recording CUED 8 seconds before the site's time, the moment and what leads
// to it, and never played until asked: cueVideoById plays nothing (a seekTo on a
// recording not yet started would).
function cue(id,at){var start=Math.max(0,Math.floor(at-LEAD));ytWant={id:id,start:start};
if(!ytAsked)return ytLoad();if(!ytReady)return;YTP.cueVideoById({videoId:id,startSeconds:start});ytVideo=id;}
function now(){return ytReady&&YTP.getCurrentTime?YTP.getCurrentTime():null;}
function play(at){if(!ytReady)return;YTP.seekTo(Math.max(0,at),true);YTP.playVideo();}
function nudge(d){var t=now();if(t===null)return;YTP.seekTo(Math.max(0,t+d),true);}
function quiet(){if(ytReady&&YTP.pauseVideo)YTP.pauseVideo();}

// ---- drawing -----------------------------------------------------------------
function step(){var c=S.item&&S.item.card;return c&&c.type==="moment"?c.steps[S.step]:null;}
function words(s,at,bold){var t=esc(hms(at));return esc(s||"").replace("{t}",bold?"<b>"+t+"</b>":t);}
function drawTop(){var v=S.view||{},owner=v.role==="owner",judging=S.tab==="judge";
$("tabs").hidden=!owner;
$("judgetab").toggleAttribute("aria-current",judging);$("linkstab").toggleAttribute("aria-current",!judging);
if(judging)$("judgetab").setAttribute("aria-current","page");else $("linkstab").setAttribute("aria-current","page");
var qs=v.queues||[],k=$("kind");
k.innerHTML=qs.map(function(q){return '<option value="'+esc(q.queue)+'">'+esc(q.label)+"</option>";}).join("")+
(qs.length>1?'<option value="mix">A mix of all '+(qs.length===3?"three":qs.length===2?"two":"of them")+"</option>":"");
k.value=S.queue;k.hidden=!qs.length||!judging;
(owner?$("kindrow"):$("kindtop")).appendChild(k);$("kindrow").hidden=!owner||!judging;
var p=v.progress;$("track").hidden=$("plabel").hidden=!judging||!p;if(!p)return;
var you=S.you[p.label]||0,goal=Math.max(1,p.goal);
$("pdone").style.width=(Math.max(0,p.done-you)/goal*100)+"%";$("pmine").style.width=(Math.min(you,p.done)/goal*100)+"%";
$("pgroup").innerHTML=esc(p.label)+": <b>"+num(p.done)+" of "+num(p.goal)+"</b>";
$("pyou").textContent="you "+you;$("pyou").hidden=!you;}
function drawFar(){var f=(S.view&&S.view.far)||[];$("far").hidden=!f.length;
$("farlist").innerHTML=f.map(function(q){var w=q.pool?Math.min(100,q.judged/q.pool*100):0;
return "<li><span>"+esc(q.label)+'</span><span class="tr"><i style="width:'+w.toFixed(2)+'%"></i></span><span>'+
num(q.judged)+" of "+num(q.pool)+"</span></li>";}).join("");}
// A page that only says something: no link, a link paused, nothing waiting, the day's answers given.
function message(title,text,retry){quiet();$("player").hidden=true;$("head").innerHTML="";$("card").className="card empty";
$("body").innerHTML="<h1>"+esc(title)+'</h1><p class="prose">'+esc(text)+"</p>"+
(retry?'<p><button type="button" class="btn" data-do="retry">Try again</button></p>':"");$("answers").innerHTML="";}
function draw(){drawTop();drawFar();var judging=S.tab==="judge";$("judge").hidden=!judging;$("links").hidden=judging;
$("answers").hidden=!judging;if(!judging){$("toast").hidden=true;return quiet();}
var v=S.view;if(!v)return;
if(v.state==="paused")return message("This link is paused","Nothing is asked of it for now. The person who sent it can turn it back on, and it will work again then.");
var it=S.item;if(!it)return message("Nothing waiting right now","Every item this link can be given has an answer. Thank you. New ones are added from time to time; this link keeps working.");
var c=it.card,head="",body="";$("card").className="card";
if(c.type==="moment"){var st=step(),two=c.steps.length>1;$("player").hidden=false;
head='<p class="title">'+esc(c.head)+'</p><p class="meta">'+esc(c.meta)+'</p><p class="billtitle">'+esc(c.title)+"</p>";
$("ctl").innerHTML='<button type="button" data-do="back" aria-label="Back ten seconds">&minus;10 s</button>'+
'<button type="button" class="play" data-do="play">&#9654;&nbsp; Play from '+esc(hms(st.at))+"</button>"+
'<button type="button" data-do="fwd" aria-label="Forward ten seconds">+10 s</button>';
body=(two?'<p class="steps"><i class="on"></i><i class="'+(S.step?"on":"")+'"></i>&nbsp;'+(S.step+1)+" of 2 &middot; "+esc(st.label)+"</p>":"")+
(S.mode==="mark"?'<p class="claimline">'+words(st.find,st.at,true)+"</p>":'<p class="q">'+words(st.q,st.at,false)+"</p>");}
else{quiet();$("player").hidden=true;
head='<p class="head">'+esc(c.head)+'</p><p class="title">'+esc(c.title)+"</p>"+
(c.body?'<p class="label">'+esc(c.label)+'</p><p class="prose">'+esc(c.body)+"</p>":"");
body='<p class="q">'+esc(c.q).replace("{claim}",'<b class="claim">'+esc(c.claim)+"</b>")+"</p>"+(c.def?'<p class="def">'+esc(c.def)+"</p>":"");
if(S.mode==="better"){var o=((v.queues||[]).filter(function(q){return q.queue===it.queue;})[0]||{}).options||[];
body+='<div class="better"><p class="label">'+esc(c.better.label)+'</p><select id="better" aria-label="'+esc(c.better.label)+'">'+
'<option value="">'+esc(c.better.none)+"</option>"+o.map(function(x){return '<option value="'+esc(x)+'">'+esc(x)+"</option>";}).join("")+
"</select><small>"+esc(c.better.from)+"</small></div>";}}
var kept=S.note&&$("note")?$("note").value:"";
body+=S.note?'<div class="notebox"><input type="text" id="note" maxlength="280" aria-label="A note" autocomplete="off">'+
"<small>Optional, one line. Kept with your answer.</small></div>":(S.mode==="mark"?"":'<button type="button" class="notebtn" data-do="note">Add a note</button>');
$("head").innerHTML=head;$("body").innerHTML=body;if(S.note)$("note").value=kept;drawAnswers();}
function drawAnswers(){var a,it=S.item,st=step();
if(S.mode==="mark"){var t=now();a='<div class="row two"><button class="ans" type="button" data-a="lost">'+esc(st.lost)+"</button>"+
'<button class="ans markit" type="button" data-a="mark" id="markit">'+ICON.mark+" "+esc(st.mark)+" "+(t===null?"":esc(hms(t)))+"</button></div>";}
else if(S.mode==="better"){a='<div class="row two"><button class="ans" type="button" data-a="back">Back</button>'+
'<button class="ans yes" type="button" data-a="saveno">Save the No</button></div>';}
else{a='<div class="row"><button class="ans no" type="button" data-a="no" aria-keyshortcuts="ArrowLeft">'+ICON.no+" No</button>"+
'<button class="ans" type="button" data-a="unsure" aria-keyshortcuts="ArrowDown">'+ICON.unsure+" Not sure</button>"+
'<button class="ans yes" type="button" data-a="yes" aria-keyshortcuts="ArrowRight">'+ICON.yes+" Yes</button></div>"+
'<div class="keys"><span><kbd>&larr;</kbd>No</span><span><kbd>&darr;</kbd>Not sure</span><span><kbd>&rarr;</kbd>Yes</span>'+
"<span><kbd>Z</kbd>Undo</span><span><kbd>N</kbd>Note</span>"+(st?"<span><kbd>Space</kbd>Play</span><span><kbd>J</kbd><kbd>L</kbd>10 s</span>":"")+"</div>";}
$("answers").innerHTML=a;}
// The mark button reads the player's own clock, four times a second.
setInterval(function(){if(S.mode!=="mark")return;var b=$("markit"),t=now(),st=step();
if(b&&st)b.innerHTML=ICON.mark+" "+esc(st.mark)+" "+(t===null?"":esc(hms(t)));},250);

// ---- the bench's answers -------------------------------------------------------
function show(v){S.view=v;var it=(v.items||[])[0]||null;S.item=it;S.step=0;S.steps=[];S.mode="ask";S.note=false;
if(it&&it.card.type==="moment")cue(it.card.player.id,it.card.steps[0].at);
S.label=v.progress?v.progress.label:"";draw();}
function start(){if(!/^[A-Za-z0-9_-]{43}$/.test(T))return lost();$("forget").hidden=false;
api("/api/bench/next",{queue:S.queue}).then(function(r){if(r.status===404)return lost();
if(!r.data||r.status>=500)return message("The bench cannot be reached just now","Nothing was lost. Try again in a minute.",true);
S.queue=r.data.queue||"mix";show(r.data);});}
// No link, or one the bench does not know (404: turned off, or wrong),
// which the device then forgets, so a dead link does not linger.
function lost(){forget();needs();}
function needs(){S.view=null;S.item=null;S.tab="judge";S.links=null;S.made=null;S.open={};drawTop();$("far").hidden=true;
$("judge").hidden=false;$("links").hidden=true;$("answers").hidden=false;$("toast").hidden=true;
message("${NEEDS_LINK}","${NEEDS_WORDS}");}
function toast(said,undo){$("toastwords").textContent=said;$("undo").hidden=!undo;$("toast").hidden=false;
clearTimeout(S.toastT);S.toastT=setTimeout(function(){$("toast").hidden=true;},TOAST_MS);}
// AN ANSWER IS SENT ONLY WHEN IT IS GIVEN. Nothing is chosen in advance.
function send(answer,side){if(S.busy)return;S.busy=true;var it=S.item,label=S.label,
note=S.note&&$("note")?$("note").value:"",card=$("card");card.classList.add(side==="no"?"out-l":"out-r");
var go=function(tries){api("/api/bench/judge",{queue:S.queue,ref:it.ref,answer:answer,note:note}).then(function(r){
if(r.status===429&&r.data&&r.data.why==="fast"&&tries<2)return setTimeout(function(){go(tries+1);},1100);
S.busy=false;card.classList.remove("out-l","out-r");
if(r.status===404)return lost();
if(r.status===200){if(label)S.you[label]=(S.you[label]||0)+1;S.saved={label:label};toast("Saved: "+SAID[side],true);return show(r.data);}
if(r.data&&r.data.why==="full"){S.view=r.data;S.item=null;drawTop();return message("That is all for today","Thank you. This link works again tomorrow.");}
if(r.data&&r.data.items){toast(r.data.why==="paused"?"Not saved: this link is paused.":r.status===409?"Not saved: that one had been let go. Here is the next.":"Not saved.",false);return show(r.data);}
toast("Not saved: the bench could not be reached. Try again.",false);draw();});};
go(0);}
function undo(){if(S.busy||$("toast").hidden||$("undo").hidden)return;S.busy=true;$("toast").hidden=true;
api("/api/bench/undo",{queue:S.queue}).then(function(r){S.busy=false;if(r.status===404)return lost();
if(!r.data)return toast("Not undone: the bench could not be reached.",false);
if(r.data.undone&&S.saved&&S.you[S.saved.label])S.you[S.saved.label]--;S.saved=null;show(r.data);});}
function answer(what){var it=S.item;if(!it||S.busy||S.tab!=="judge")return;var c=it.card;
if(what==="back"){S.mode="ask";return draw();}
if(c.type==="moment"){if(S.mode==="ask"&&what==="no"){S.mode="mark";return draw();}
var got=what==="mark"?{answer:"no",mark:now()}:what==="lost"?{answer:"no"}:{answer:what};if(got.mark===null)return;
S.steps[S.step]=got;S.mode="ask";
if(S.step+1<c.steps.length){S.step++;cue(c.player.id,step().at);return draw();}
var sides=S.steps.map(function(x){return x.answer;});
return send({steps:S.steps},sides.indexOf("no")>=0?"no":sides.indexOf("unsure")>=0?"unsure":"yes");}
if(what==="no"&&c.better&&S.mode==="ask"){S.mode="better";return draw();}
if(what==="saveno"){var b=$("better")?$("better").value:"";return send(b?{answer:"no",better:b}:{answer:"no"},"no");}
if(S.mode==="ask")send({answer:what},what);}
function openNote(){S.note=true;draw();var n=$("note");if(n)n.focus();}

document.addEventListener("click",function(e){var t=e.target.closest?e.target.closest("[data-a],[data-do],#undo,[data-tab],[data-link]"):null;
if(!t)return;if(t.id==="undo")return undo();if(t.dataset.a)return answer(t.dataset.a);
if(t.dataset.tab)return tab(t.dataset.tab);if(t.dataset.link)return linkAct(t.dataset.link,t.dataset.id,t.dataset.answer);
var d=t.dataset.do,st=step();if(d==="retry")return start();
if(d==="forget"){if(!confirm("${FORGET_ASK}"))return;forget();return needs();}if(d==="note")return openNote();
if(d==="play"&&st)return play(st.at);if(d==="back")return nudge(-10);if(d==="fwd")return nudge(10);});
$("kind").addEventListener("change",function(){S.queue=this.value;start();});
document.addEventListener("keydown",function(e){
if(e.target.matches&&e.target.matches("input,select,textarea")){if(e.key==="Escape"){if(S.mode==="better")answer("back");else if(S.note){S.note=false;draw();}}return;}
if(e.ctrlKey||e.metaKey||e.altKey||S.tab!=="judge"||!S.item)return;var k=e.key,st=step(),hit=true;
if(k==="ArrowRight")answer(S.mode==="mark"?"mark":S.mode==="better"?"saveno":"yes");
else if(k==="ArrowLeft")answer(S.mode==="mark"?"lost":S.mode==="better"?"back":"no");
else if(k==="ArrowDown"&&S.mode==="ask")answer("unsure");
else if(k==="Escape"&&S.mode!=="ask")answer("back");
else if(k==="z"||k==="Z")undo();
else if((k==="n"||k==="N")&&S.mode!=="mark")openNote();
else if(st&&k===" ")play(st.at);else if(st&&(k==="j"||k==="J"))nudge(-10);else if(st&&(k==="l"||k==="L"))nudge(10);
else hit=false;if(hit)e.preventDefault();});
// A SWIPE, on the card only and never on the player: across, far enough, and
// more across than down, so reading and scrolling never answers anything.
var sx=null,sy=null;
$("card").addEventListener("touchstart",function(e){if(S.mode!=="ask"||(e.target.closest&&e.target.closest("#player,input,select,button"))){sx=null;return;}
sx=e.touches[0].clientX;sy=e.touches[0].clientY;},{passive:true});
$("card").addEventListener("touchend",function(e){if(sx===null)return;var dx=e.changedTouches[0].clientX-sx,dy=e.changedTouches[0].clientY-sy;sx=null;
if(Math.abs(dx)>SWIPE&&Math.abs(dx)>2*Math.abs(dy))answer(dx>0?"yes":"no");},{passive:true});
// The open page keeps what it holds: every two minutes, and when it is looked at again.
setInterval(function(){if(S.item&&!document.hidden)api("/api/bench/hold",{});},HOLD_EVERY);
document.addEventListener("visibilitychange",function(){if(!document.hidden&&S.item)api("/api/bench/hold",{});});
// Another link opened in this tab changes only what follows "#", which loads nothing: read it afresh.
window.addEventListener("hashchange",function(){if(location.hash)location.reload();});

// ---- the owner's Links tab ---------------------------------------------------------
function tab(t){S.tab=t;if(t==="links")return links({action:"list"});draw();}
function links(body){return api("/api/bench/links",body).then(function(r){if(r.status===404){lost();return r;}
if(!r.data){$("linksbody").innerHTML='<p class="lede">The links cannot be read just now. Try again in a minute.</p>';draw();return r;}
if(r.data.links)S.links=r.data.links;if(r.data.made)S.made=r.data.made;if(r.data.answers)S.open[body.id]=r.data.answers;
drawLinks();draw();return r;});}
function queueName(q){var v=((S.view&&S.view.queues)||[]).filter(function(x){return x.queue===q;})[0];return v?v.label:q;}
function drawLinks(){var L=S.links||[],h="",qs=(S.view&&S.view.queues)||[],waiting=0,first="";
h+='<section class="box new" aria-label="A new link"><p class="label">A new link</p>'+
'<input type="text" id="newname" maxlength="60" placeholder="A name only you will see, such as Sam" aria-label="Name">'+
'<div class="checks" role="group" aria-label="What this link may judge">'+qs.map(function(q){
return '<label><input type="checkbox" name="newq" value="'+esc(q.queue)+'" checked> '+esc(q.label)+"</label>";}).join("")+"</div>"+
'<div><button class="btn primary" type="button" data-link="make">Make the link</button></div></section>';
if(S.made){var url=location.origin+"/bench#"+S.made.token;
h+='<section class="box made" aria-label="The new link"><p><b>Text this to '+esc(S.made.name||"them")+".</b> It is shown once; this page keeps only a fingerprint of it.</p>"+
'<p class="url">'+esc(url)+'</p><div class="acts">'+(navigator.share?'<button class="btn primary" type="button" data-link="share">Share&hellip;</button>':"")+
'<button class="btn" type="button" data-link="copy">Copy</button></div></section>';}
L.forEach(function(l){var own=l.role==="owner",list=S.open[l.id];if(!own){waiting+=l.unmerged;if(l.unmerged&&!first)first=l.name;}
var st=own?'<span class="state owner">Your link</span>':'<span class="state '+esc(l.state)+'">'+esc({active:"Active",paused:"Paused",off:"Off"}[l.state]||l.state)+"</span>";
h+='<section class="box link" aria-label="'+esc(own?"You":l.name)+'"><div class="who"><b>'+esc(own?"You":l.name)+"</b>"+st+"</div>"+
'<p class="meta">'+(own?"Every kind &middot; your answers are final and are never asked again":esc(l.queues.map(queueName).join(", "))+
" &middot; made "+esc(day(l.made_on))+(l.last_on?" &middot; last used "+esc(day(l.last_on)):""))+"</p>"+
'<div class="nums"><div><b>'+num(l.answers)+"</b><span>answers</span></div><div><b>"+num(l.unmerged)+"</b><span>not merged yet</span></div>"+
"<div><b>"+(own||!l.asked?"&mdash;":num(l.agree)+" of "+num(l.asked))+"</b><span>"+(own?"the measure the others are held to":"agree with yours")+"</span></div></div>";
if(list){h+='<ul class="said">'+(list.length?list.map(function(a){var f=a.fields||{},bits=[];
if(f.better_topic)bits.push("Better topic: "+esc(f.better_topic));if(f.observed_start)bits.push("Start marked "+esc(f.observed_start));
if(f.observed_end)bits.push("End marked "+esc(f.observed_end));if(a.note)bits.push("&ldquo;"+esc(a.note)+"&rdquo;");if(a.state==="merged")bits.push("merged");
return '<li><span class="what">'+esc(a.head)+(a.what?" &middot; "+esc(a.what):"")+'</span><span class="v '+esc(a.side)+'">'+esc(SAID[a.side]||a.side)+"</span>"+
'<span class="how">'+(bits.join(" &middot; ")||"&nbsp;")+"</span>"+(a.state==="kept"&&!a.calib&&!own?'<button class="one" type="button" data-link="takeone" data-id="'+esc(l.id)+'" data-answer="'+esc(a.id)+'">Take back</button>':"")+"</li>";}).join(""):"<li>No answers yet.</li>")+"</ul>";}
h+='<div class="acts"><button class="btn" type="button" data-link="see" data-id="'+esc(l.id)+'">'+(list?"Hide answers":"See answers")+"</button>";
if(!own&&l.state!=="off"){h+='<button class="btn" type="button" data-link="'+(l.state==="paused"?"resume":"pause")+'" data-id="'+esc(l.id)+'">'+(l.state==="paused"?"Resume":"Pause")+"</button>";
if(l.unmerged)h+='<button class="btn warn" type="button" data-link="takeback" data-id="'+esc(l.id)+'">Take back the '+num(l.unmerged)+"</button>";
h+='<button class="btn warn" type="button" data-link="off" data-id="'+esc(l.id)+'">Turn off</button>';}
h+="</div></section>";});
var who=/\s/.test(first)?'"'+first+'"':first||"sam";
h+='<p class="merge"><b>'+num(waiting)+" answer"+(waiting===1?" waits":"s wait")+" for your merge.</b> On the laptop, at the <code>cmd</code> prompt, to look first and then approve:"+
"<code>python3 src/checks/bench_pull.py</code><code>python3 src/checks/bench_pull.py --approve "+esc(who)+"</code></p>";
$("linksbody").innerHTML=h;}
function linkAct(what,id,answerId){var l=(S.links||[]).filter(function(x){return x.id===id;})[0];
if(what==="make"){var name=$("newname").value.trim(),qs=[].slice.call(document.querySelectorAll("input[name=newq]:checked")).map(function(x){return x.value;});
if(!name||!qs.length)return $("newname").focus();return links({action:"make",name:name,queues:qs}).then(function(r){if(r&&r.data&&r.data.made){S.made.name=name;drawLinks();}});}
if(what==="copy"&&S.made){if(navigator.clipboard)navigator.clipboard.writeText(location.origin+"/bench#"+S.made.token);return;}
if(what==="share"&&S.made&&navigator.share){navigator.share({title:"Granite Record Bench",url:location.origin+"/bench#"+S.made.token}).catch(function(){});return;}
if(what==="see"){if(S.open[id]){delete S.open[id];return drawLinks();}return links({action:"answers",id:id});}
if(what==="takeback"&&l&&!confirm("Take back "+l.name+"’s "+l.unmerged+" answers not merged yet? Their items are asked again."))return;
if(what==="off"&&l&&!confirm("Turn off "+l.name+"’s link? It stops working for good; its answers stay for your merge."))return;
if(what==="takeone"){delete S.open[id];return links({action:"takeone",id:id,answer:Number(answerId)}).then(function(){return links({action:"answers",id:id});});}
S.made=null;links({action:what,id:id});}
start();})();`;

export function benchPage() {
  const n = nonce();
  const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<title>Bench &mdash; Granite Record</title>
${FONTS}
<style>${STYLE}</style></head>
<body>
<header class="top" id="top"><div class="in">
<div class="row1"><div class="brand">Granite Record<span>Bench</span></div>
<div id="kindtop"><select class="kind" id="kind" aria-label="What to judge" hidden></select></div>
<nav class="tabs" id="tabs" aria-label="Bench" hidden><button type="button" id="judgetab" data-tab="judge">Judge</button>
<button type="button" id="linkstab" data-tab="links">Links</button></nav></div>
<div id="kindrow" class="chooser" hidden></div>
<div class="track" id="track" aria-hidden="true" hidden><i class="done" id="pdone"></i><i class="mine" id="pmine"></i></div>
<div class="plabel" id="plabel" hidden><span id="pgroup"></span><span class="you" id="pyou" hidden></span></div>
</div></header>
<main>
<div id="judge">
<article class="card" id="card" aria-live="polite"><div id="head"></div>
<div id="player" hidden><div class="player"><div id="yt"></div></div><div class="ctl" id="ctl"></div></div>
<div id="body"></div></article>
<section class="far" id="far" aria-label="How far along" hidden><h2>How far along</h2><ul id="farlist"></ul>
<p class="small">${KEPT}</p></section>
</div>
<div id="links" hidden><h1 class="page">Links</h1>
<p class="lede">One link for each person you invite. Only this page, opened with your own link, shows them.</p>
<div id="linksbody"></div></div>
<p class="forget" id="forget" hidden><button type="button" data-do="forget">${FORGET}</button></p>
<noscript><p class="lede">This page needs JavaScript. Your link keeps its key after the &ldquo;#&rdquo; in its address,
which your browser sends to no server, and a few lines of script on this page read it from there.</p></noscript>
</main>
<div class="toast" id="toast" hidden role="status"><span id="toastwords"></span><button type="button" id="undo">Undo</button></div>
<footer class="answers" id="answers"></footer>
<script nonce="${n}">${SCRIPT}</script>
</body></html>`;
  return pageResponse(200, html, n);
}
