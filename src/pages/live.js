// GRANITE_VERSION: 2026-10-30.1
/* LIVE NOW, IN THE BROWSER (the live layer's design, sections 1.4, 2.6 and
   4.1). Loaded by /live after components.js, whose clock(), esc() and tr()
   it draws with, so a time reads "10:02 AM" as every page's does and every
   string is one the Spanish catalogue can carry.

   THE PAGE NEVER WAITS ON IT. The night writes /live with today's meetings
   already in it (the Calendar's own cards), both channels' links and a
   <noscript> line. This script adds what was live when the Worker last
   looked, from /api/live/streams, and the day's votes on a session card,
   from /api/live/votes/<date>. With no script, no data or no binding, the
   page is the night's and says so.

   WORDING STATES WHAT WAS CHECKED, NEVER A FACT ABOUT THE WORLD: "No stream
   found right now (checked 2:14 PM)", "Live status has not been checked since
   10:42 AM". The strings "not streaming" and "nothing is live" appear nowhere
   (tests/live/page.test.js holds that).

   THE PURE PART (L.*) takes a file and a moment and gives words or HTML;
   tests run it in node. THE PAGE PART (L.start) fetches, polls once a
   minute while the tab is visible (Page Visibility), with If-None-Match, and
   updates each stream's card in place by its video id, so a player someone
   opened keeps playing.

   A stream's title is matched to a meeting as section 1.2 says: its stem
   (stem(), the Worker's own, held equal by preflight) against the meeting's
   `match` list in the night's schedule. A session stream is one whose stem
   begins "house session" or "senate session". */
(function (root) {
"use strict";
var L = {};
// components.js's own helpers, by their global names (esc is a top-level
// const there, shared between the page's scripts but not on window).
/* global clock, esc, tr, billMention */
var C = { clock: function (t, l) { return clock(t, l); }, esc: function (v) { return esc(v); },
          tr: function (k, en, vals) { return tr(k, en, vals); } };
var LANG = (root && root.GR_LANG) || "en";
var MINUTE = 60000;

// ---- titles: the Worker's stem() (workers/live/youtube.js), word for word --
var DATE_TAIL = /\(\s*[0-9]{1,2}\/[0-9]{1,2}\/[0-9]{2,4}[\s\S]*$/;
L.stem = function (title) {
  var t = String(title || "").replace(DATE_TAIL, "").toLowerCase().replace(/&/g, " and ");
  return (t.match(/[a-z0-9]+/g) || []).join(" ");
};
L.SESSION = { H: /^house session\b/, S: /^senate session\b/ };
L.sessionOf = function (title) {
  var s = L.stem(title);
  for (var c in L.SESSION) if (L.SESSION[c].test(s)) return c;
  return null;
};
// Without its date: the title the page shows for a stream it cannot match.
L.bareTitle = function (title) {
  return String(title || "").replace(DATE_TAIL, "").replace(/\s+$/, "");
};

// ---- New Hampshire's clock --------------------------------------------------
var NH = null;
function nhParts(t) {
  if (!NH) NH = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  var p = {};
  NH.formatToParts(new Date(t)).forEach(function (x) { p[x.type] = x.value; });
  return { date: p.year + "-" + p.month + "-" + p.day, hh: String(Number(p.hour) % 24).padStart(2, "0"), mm: p.minute };
}
L.nhDate = function (t) { return nhParts(t).date; };
// An ISO moment as the site prints a time: "10:02 AM", New Hampshire's.
L.timeOf = function (iso) {
  var t = Date.parse(iso || "");
  if (!isFinite(t)) return "";
  var p = nhParts(t);
  return C.clock(p.hh + ":" + p.mm, LANG);
};

// ---- the streams file: what the page says of it (section 1.4) -------------
// {kind, sentence}: kind is fresh, stale, off or unavailable.
L.streamsStatus = function (file, now, http) {
  if (http === 404) return { kind: "unavailable", sentence: C.tr("live.unavailable", "Live status is not available") };
  if (file && file.status && file.status.problem === "off") {
    return { kind: "off", sentence: C.tr("live.off", "Live status is turned off") };
  }
  var today = L.nhDate(now);
  var fresh = file && file.status && file.status.ok && file.day === today && file.next_check
    && +now <= Date.parse(file.next_check) + 5 * MINUTE;
  if (!fresh) {
    var at = file && file.checked ? L.timeOf(file.checked) : "";
    return { kind: "stale", sentence: at
      ? C.tr("live.stale", "Live status has not been checked since {time}", { time: at })
      : C.tr("live.stale_never", "Live status has not been checked yet today") };
  }
  var live = (file.streams || []).some(function (s) { return s.status === "live"; });
  var when = L.timeOf(file.checked);
  return { kind: "fresh", sentence: live
    ? C.tr("live.checked", "Checked {time}", { time: when })
    : C.tr("live.none_found", "No stream found right now (checked {time})", { time: when }) };
};

// ---- matching a stream to today's meetings (section 1.2) -------------------
// The schedule is the night's live/schedule.json: {days: {date: [row]}}, each
// row {id, chamber, kind, name, href, card, match: [stems]}.
L.match = function (stream, rows) {
  var s = L.stem(stream.title);
  var session = L.sessionOf(stream.title);
  for (var i = 0; i < (rows || []).length; i++) {
    var r = rows[i];
    if (r.chamber && stream.chamber && r.chamber.indexOf(stream.chamber) < 0) continue;
    if (session) { if (r.kind === "floor" && r.chamber === session) return r; continue; }
    var m = r.match || [];
    for (var j = 0; j < m.length; j++) {
      if (m[j] && (s === m[j] || s.indexOf(m[j] + " ") === 0)) return r;
    }
  }
  return null;
};

// ---- the cards ----------------------------------------------------------------
function stub(s, name) {
  return '<div class="player lv-player" data-player="lv-' + C.esc(s.video) + '">'
    + '<button type="button" class="pstub" data-title="' + C.esc(name) + '" data-embed="'
    + C.esc(s.video) + '|0|lv-' + C.esc(s.video) + '"><span aria-hidden="true">&#9654;</span><span>'
    + C.esc(C.tr("live.play", "Play the live stream")) + "</span></button></div>";
}
function youtube(s) {
  return '<a class="lv-yt" href="https://www.youtube.com/watch?v=' + encodeURIComponent(s.video) + '" rel="noopener">'
    + C.esc(C.tr("live.on_youtube", "On YouTube")) + "</a>";
}
L.name = function (s, row) { return row ? row.name : L.bareTitle(s.title); };

// One live stream's card, minus its player: the parts that change. The
// player box is drawn once and kept (L.start).
L.cardParts = function (s, row) {
  var since = s.started ? C.tr("live.since", "Live since {time}", { time: L.timeOf(s.started) }) : "";
  return {
    head: '<h3 class="lv-name">' + (row && row.href ? '<a href="' + C.esc(row.href) + '">' + C.esc(L.name(s, row)) + "</a>"
      : C.esc(L.name(s, row))) + "</h3>" + (since ? '<p class="lv-since">' + C.esc(since) + "</p>" : ""),
    foot: youtube(s) + (row && row.card ? '<div class="lv-agenda">' + row.card + "</div>" : ""),
  };
};

// What the page draws from one streams file: live cards in order, and the
// three lists. {live: [{video, row, name, parts}], scheduled, nostream,
// earlier: [html], status}.
L.view = function (file, schedule, now, http) {
  var today = L.nhDate(now);
  var rows = (schedule && schedule.days && schedule.days[today]) || [];
  var status = L.streamsStatus(file, now, http);
  var out = { live: [], scheduled: [], nostream: [], earlier: [], status: status };
  var seen = {};
  var usable = file && file.day === today && status.kind !== "unavailable";
  (usable ? file.streams || [] : []).forEach(function (s) {
    var row = L.match(s, rows);
    if (row) seen[row.id] = true;
    if (s.status === "live" && status.kind === "fresh") {
      out.live.push({ video: s.video, row: row, name: L.name(s, row), parts: L.cardParts(s, row),
                      embeddable: s.embeddable !== false });
    } else if (s.status === "upcoming") {
      out.scheduled.push('<li>' + C.esc(L.name(s, row)) + " &middot; "
        + C.esc(C.tr("live.at", "scheduled for {time}", { time: L.timeOf(s.scheduled) })) + "</li>");
    } else if (s.status === "ended" || (s.status === "live" && status.kind !== "fresh")) {
      out.earlier.push('<li>' + C.esc(L.name(s, row)) + " &middot; " + youtube(s) + "</li>");
    }
  });
  rows.forEach(function (r) {
    if (!seen[r.id]) out.nostream.push('<li>' + (r.href ? '<a href="' + C.esc(r.href) + '">' + C.esc(r.name) + "</a>"
      : C.esc(r.name)) + "</li>");
  });
  out.live.sort(function (a, b) { return a.name < b.name ? -1 : a.name > b.name ? 1 : 0; });
  return out;
};

// ---- the votes file (section 2.6) ---------------------------------------------
var ENDS = function () {
  return C.tr("votes.ends", "Every vote reaches this page with tomorrow morning's record.");
};
// The sentence under a chamber's votes. `body` is H or S.
L.votesSentence = function (file, now, body, http) {
  var tail = " " + ENDS();
  if (!file || http === 404) return C.tr("votes.none_today", "No roll calls read today.") + tail;
  var st = file.status || {};
  var last = file.read_at ? L.timeOf(file.read_at) : "";
  var since = st.since ? L.timeOf(st.since) : "";
  var overdue = file.next_read_by && +now > Date.parse(file.next_read_by) + 5 * MINUTE;
  var mine = (file.rollcalls || []).filter(function (r) { return r.body === body; }).length;
  var words = {
    connect: C.tr("votes.connect", "Votes last read at {time}; the General Court's database could not be reached since.", { time: last }),
    login: C.tr("votes.login", "Votes last read at {time}; the database has refused the published login since.", { time: last }),
    encrypt: C.tr("votes.encrypt", "Live votes are off: the database asks for an encrypted connection this site's reader cannot make."),
    query: C.tr("votes.query", "Votes last read at {time}; a query has failed since.", { time: last }),
    budget: C.tr("votes.budget", "Live votes reached today's limit on queries and stop until tomorrow."),
    off: C.tr("votes.off", "Live votes were turned off by this site at {time}.", { time: since }),
    day_over: C.tr("votes.day_over", "Reading stopped for the day at {time}.", { time: since }),
  };
  var say;
  if (st.problem && words[st.problem]) say = words[st.problem];
  else if (st.problem || overdue || !last) say = C.tr("votes.not_read", "Not read since {time}.", { time: last || "—" });
  else if (!mine) {
    say = C.tr("votes.none_yet", "No roll calls read yet today (read at {time}).", { time: last });
    if (body === "S") say += " " + C.tr("votes.senate_after", "The Senate enters its roll calls after it rises.");
  } else say = C.tr("votes.read", "Read from the General Court's database at {time}.", { time: last });
  return say + tail;
};

// One chamber's roll calls, newest first, as list items.
L.votesItems = function (file, body) {
  var rcs = ((file && file.rollcalls) || []).filter(function (r) { return r.body === body; })
    .sort(function (a, b) { return b.seq - a.seq; });
  return rcs.map(function (r) {
    var when = r.taken ? L.timeOf(r.taken) : r.saved ? C.tr("votes.saved_at", "saved at {time}", { time: L.timeOf(r.saved) }) : "";
    // The site's own mention of a bill (components.billMention), at the vote's
    // session year: bill/2027/hb2.html.
    var year = String(r.id || "").slice(0, 4);
    var bill = r.bill_as_recorded ? billMention(r.bill_as_recorded, "/bill/" + year + "/"
      + String(r.bill_as_recorded).toLowerCase().replace(/[^a-z0-9]/g, "") + ".html") : "";
    var outcome = r.docket && r.docket.outcome
      ? C.tr("votes.outcome", "{outcome}, clerk's docket", { outcome: r.docket.outcome })
      : C.tr("votes.no_outcome", "outcome not yet in the docket");
    var names = r.ballots_complete ? C.tr("votes.names_in", "names: in") : C.tr("votes.names_follow", "names follow");
    return '<li class="lv-rc" data-id="' + C.esc(r.id) + '">'
      + (when ? '<span class="lv-when">' + C.esc(when) + "</span> " : "") + bill + " "
      + '<span class="lv-q">' + C.esc(r.question || "") + "</span> "
      + '<span class="lv-tally">' + r.yeas + "&ndash;" + r.nays + "</span> "
      + '<span class="lv-outcome">' + C.esc(outcome) + "</span> "
      + '<span class="lv-names">' + C.esc(names) + "</span>"
      + (r.note ? '<span class="lv-note">' + C.esc(r.note) + "</span>" : "") + "</li>";
  });
};

// ---- the page --------------------------------------------------------------------
// Poll once a minute while visible; at once on returning; never while hidden.
L.POLL_MS = 60000;

L.start = function (doc, opts) {
  opts = opts || {};
  var fetchImpl = opts.fetch || root.fetch;
  var now = opts.now || function () { return Date.now(); };
  var box = doc.getElementById("live-now-streams");
  if (!box) return null;
  var scheduleEl = doc.getElementById("live-schedule");
  var schedule = {};
  try { schedule = JSON.parse((scheduleEl && scheduleEl.textContent) || "{}"); } catch (e) { schedule = {}; }
  var etag = null, file = null, http = null, timer = null, stopped = false;

  function draw() {
    var v = L.view(file, schedule, now(), http);
    var statusEl = doc.getElementById("live-now-status");
    if (statusEl) statusEl.textContent = v.status.sentence;
    // Cards keyed by video: an existing card keeps its player; only its
    // words change. A card whose stream is no longer live goes.
    var keep = {};
    v.live.forEach(function (c) {
      keep[c.video] = true;
      var card = box.querySelector('[data-video="' + c.video + '"]');
      if (!card) {
        card = doc.createElement("article");
        card.className = "lv-card";
        card.setAttribute("data-video", c.video);
        card.innerHTML = '<div class="lv-head"></div>' + stub({ video: c.video }, c.name) + '<div class="lv-foot"></div>';
        box.appendChild(card);
      }
      var head = card.querySelector(".lv-head"), foot = card.querySelector(".lv-foot");
      if (head) head.innerHTML = c.parts.head;
      if (foot) foot.innerHTML = c.parts.foot;
    });
    Array.prototype.slice.call(box.querySelectorAll("[data-video]")).forEach(function (card) {
      if (!keep[card.getAttribute("data-video")]) card.remove();
    });
    [["live-now-scheduled", v.scheduled], ["live-now-nostream", v.nostream], ["live-now-earlier", v.earlier]]
      .forEach(function (x) {
        var el = doc.getElementById(x[0]);
        if (el) { el.innerHTML = x[1].join(""); el.hidden = !x[1].length; }
      });
  }

  function poll() {
    if (stopped) return Promise.resolve();
    var headers = etag ? { "If-None-Match": etag } : {};
    return Promise.resolve(fetchImpl("/api/live/streams", { headers: headers })).then(function (r) {
      http = r.status;
      if (r.status === 304) return null;
      if (r.status === 404) { stopped = true; file = null; return null; }   // no binding: say so, ask no more
      if (!r.ok) return null;
      etag = r.headers.get("ETag");
      return r.json().then(function (j) { file = j; });
    }).catch(function () { http = 0; }).then(draw);
  }

  function schedule_() {
    clearTimeout(timer);
    if (!stopped && !doc.hidden) timer = setTimeout(function () { poll().then(schedule_); }, L.POLL_MS);
  }
  doc.addEventListener("visibilitychange", function () {
    if (doc.hidden) clearTimeout(timer);
    else poll().then(schedule_);
  });
  var first = poll().then(schedule_);
  return { poll: poll, draw: draw, first: first, stop: function () { stopped = true; clearTimeout(timer); } };
};

if (typeof module === "object" && module.exports) module.exports = L;
else root.GRLive = L;
if (root && root.document && root.document.getElementById && root.document.getElementById("live-now-streams")) {
  L.start(root.document);
}
})(typeof window !== "undefined" ? window : globalThis);
