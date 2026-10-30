// GRANITE_VERSION: 2026-10-30.7
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
// The reader's session day: New Hampshire's date, except that before 06:00 it
// is the day before, so a sitting that ran late stays on until the night's
// record has it (section 4.2). Live Now's session card keys on it too.
L.EARLY_HOURS = 6;
L.readerDay = function (t) {
  var p = nhParts(t);
  if (Number(p.hh) >= L.EARLY_HOURS) return p.date;
  return new Date(Date.parse(p.date + "T12:00:00Z") - 86400000).toISOString().slice(0, 10);
};
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
    head: '<h2 class="lv-name">' + (row && row.href ? '<a href="' + C.esc(row.href) + '">' + C.esc(L.name(s, row)) + "</a>"
      : C.esc(L.name(s, row))) + "</h2>" + (since ? '<p class="lv-since">' + C.esc(since) + "</p>" : ""),
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
  // Today's meetings with no stream found, as the Calendar draws them; only
  // from a fresh look (otherwise the night's list stands, unjudged).
  if (status.kind === "fresh") rows.forEach(function (r) {
    if (!seen[r.id]) out.nostream.push('<li class="lv-meet">' + (r.card || C.esc(r.name)) + "</li>");
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
  // A 404 is a day with no file; a fetch that failed says nothing about the
  // day, and is said as such.
  if (http === 404 || (!file && http === undefined)) return C.tr("votes.none_today", "No roll calls read today.") + tail;
  if (!file) return C.tr("votes.unfetched", "The live votes could not be fetched at {time}; this page asks again.",
                         { time: L.timeOf(new Date(+now).toISOString()) }) + tail;
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

// A roll call's bill's own page, or null. A bill's page is under the year
// it was introduced, not the year it is voted on: a 2025 bill carried over
// and voted in 2026 is /bill/2025/hb1.html. `bills` is the night's
// {term: {year: [id]}} (build_live.bill_years), read from the term's own
// index; a bill it does not hold gets no link, since a wrong link is worse
// than none.
L.billHref = function (r, bills) {
  var term = String((r && r.bill) || "").split("/")[0];
  var id = String((r && r.bill_as_recorded) || "").replace(/\s+/g, "").toUpperCase();
  var years = bills && Object.prototype.hasOwnProperty.call(bills, term) ? bills[term] : null;
  if (!id || !years) return null;
  for (var y in years) {
    if (Object.prototype.hasOwnProperty.call(years, y) && (years[y] || []).indexOf(id) >= 0) {
      return "/bill/" + y + "/" + id.toLowerCase() + ".html";
    }
  }
  return null;
};

// Whether a roll call's motion carried, as a source says it, or null: the
// record's own `passed` (the night's file), else the clerk's docket outcome
// (DOCKET_OUTCOME's words). Never worked out from the tally: an override
// needs two thirds, and the larger number can be the losing one.
L.passedOf = function (r) {
  if (r && typeof r.passed === "boolean") return r.passed;
  var o = r && r.docket && r.docket.outcome;
  if (/ Adopted$/.test(o || "")) return true;
  if (/ (Failed|Lost)$/.test(o || "")) return false;
  return null;
};

// The roll call's ring, drawn by app.js's simpleDonut (the session pages' one
// vote renderer), or "" where app.js is not loaded or no source says which
// side prevailed: the ring marks a winner, and the page never guesses one.
L.ring = function (r, i) {
  var passed = L.passedOf(r);
  if (passed === null || typeof root.simpleDonut !== "function") return "";
  try {
    // The record's rows carry their threshold (null: a majority). A live
    // row's is not on record -- an override needs two thirds -- so its ring
    // draws no mark and claims no number needed.
    var record = typeof r.passed === "boolean";
    return root.simpleDonut({ yeas: Number(r.yeas) || 0, nays: Number(r.nays) || 0, passed: passed,
                              threshold_needed: r.threshold_needed || null,
                              threshold_unknown: !record && !r.threshold_needed }, "live", i, "Roll call");
  } catch (e) { return ""; }
};

// THE OVERLAY'S RULE (design section 4.3): union by roll-call id, the
// record winning. The live roll calls of `body` whose id the record lacks,
// newest first. Once the record has an id, its live copy is not drawn.
L.overlay = function (record, live, body) {
  var have = {};
  ((record && record.rollcalls) || []).forEach(function (r) { have[r.id] = true; });
  return ((live && live.rollcalls) || []).filter(function (r) { return r.body === body && !have[r.id]; })
    .sort(function (a, b) { return b.seq - a.seq; });
};

// One chamber's roll calls, newest first, as list items. opts.rings draws
// each one's ring; opts.provisional marks each "provisional · read at" the
// file's read_at; opts.rollcalls replaces the file's list.
L.votesItems = function (file, body, bills, opts) {
  opts = opts || {};
  var rcs = (opts.rollcalls || ((file && file.rollcalls) || []).filter(function (r) { return r.body === body; }))
    .slice().sort(function (a, b) { return b.seq - a.seq; });
  var read = file && file.read_at ? L.timeOf(file.read_at) : "";
  return rcs.map(function (r, i) {
    var when = r.taken ? L.timeOf(r.taken) : r.saved ? C.tr("votes.saved_at", "saved at {time}", { time: L.timeOf(r.saved) }) : "";
    // The site's own mention of a bill (components.billMention), linked
    // only where the term's index places it (L.billHref).
    var href = L.billHref(r, bills);
    var bill = !r.bill_as_recorded ? ""
      : href ? billMention(r.bill_as_recorded, href)
      : '<span class="bmention" translate="no">' + C.esc(r.bill_as_recorded) + "</span>";
    var outcome = r.docket && r.docket.outcome
      ? C.tr("votes.outcome", "{outcome}, clerk's docket", { outcome: r.docket.outcome })
      : C.tr("votes.no_outcome", "outcome not yet in the docket");
    var names = r.ballots_complete ? C.tr("votes.names_in", "names: in") : C.tr("votes.names_follow", "names follow");
    return '<li class="lv-rc" data-id="' + C.esc(r.id) + '">'
      + (when ? '<span class="lv-when">' + C.esc(when) + "</span> " : "") + bill + " "
      + '<span class="lv-q">' + C.esc(r.question || "") + "</span> "
      + '<span class="lv-tally">' + (Number(r.yeas) || 0) + "&ndash;" + (Number(r.nays) || 0) + "</span> "
      + '<span class="lv-outcome">' + C.esc(outcome) + "</span> "
      + '<span class="lv-names">' + C.esc(names) + "</span>"
      + (opts.provisional ? '<span class="lv-prov">' + C.esc(read
          ? C.tr("votes.provisional_at", "provisional · read at {time}", { time: read })
          : C.tr("votes.provisional", "provisional")) + "</span>" : "")
      + (r.note ? '<span class="lv-note">' + C.esc(r.note) + "</span>" : "")
      + (opts.rings ? L.ring(r, i) : "") + "</li>";
  });
};

// ---- the votes file, polled (section 4.1) --------------------------------------
// Every 30 seconds while the file's next_read_by is within 10 minutes of now
// (a reader is at work), otherwise every 2 minutes; never while hidden.
L.VOTES_FAST_MS = 30000;
L.VOTES_SLOW_MS = 120000;
L.votesEvery = function (file, now) {
  var by = Date.parse((file && file.next_read_by) || "");
  return isFinite(by) && Math.abs(by - now) <= 10 * MINUTE ? L.VOTES_FAST_MS : L.VOTES_SLOW_MS;
};

// A poller for one JSON address with If-None-Match. o: {fetch, doc, url(),
// every(file) -> ms (0 stops), onFile(file, http)}. A 404 is a file not there
// (yet, or no binding): onFile hears it, and every() decides whether to ask
// again. Returns {poll, stop, first}.
L.poller = function (o) {
  var etag = null, file = null, timer = null, stopped = false, url = null;
  function poll() {
    if (stopped) return Promise.resolve();
    var u = o.url();
    if (u !== url) { url = u; etag = null; file = null; }
    var headers = etag ? { "If-None-Match": etag } : {};
    // Called bare, never as o.fetch(): the browser's fetch throws "Illegal
    // invocation" when its `this` is not the window.
    var get = o.fetch;
    return Promise.resolve(get(u, { headers: headers })).then(function (r) {
      if (r.status === 304) return r.status;
      if (r.status === 404) { file = null; etag = null; return 404; }
      if (!r.ok) return r.status;
      etag = r.headers.get("ETag");
      return r.json().then(function (j) { file = j; return 200; });
    }).catch(function () { return 0; }).then(function (http) {
      if (u === url && !stopped) o.onFile(file, http);
    });
  }
  function next() {
    clearTimeout(timer);
    var ms = stopped || o.doc.hidden ? 0 : o.every(file);
    if (ms) timer = setTimeout(function () { poll().then(next); }, ms);
  }
  o.doc.addEventListener("visibilitychange", function () {
    if (o.doc.hidden) clearTimeout(timer);
    else if (!stopped) poll().then(next);
  });
  var first = poll().then(next);
  return { poll: poll, first: first, stop: function () { stopped = true; clearTimeout(timer); } };
};

var CHAMBER = { H: "House", S: "Senate" };

// Live Now's session card for one chamber (section 4.1): the list, the
// section 2.6 sentence, the provisional line, and the chamber's today page.
L.sessionCard = function (file, body, now, http, bills) {
  // Tallies as text: section 4.1. The rings are the today page's.
  var items = L.votesItems(file, body, bills);
  var head = body === "S" ? C.tr("votes.head_senate", "Senate roll calls today") : C.tr("votes.head_house", "House roll calls today");
  var today = body === "S" ? C.tr("votes.today_senate", "The Senate today") : C.tr("votes.today_house", "The House today");
  return '<section class="lv-session" data-body="' + body + '">'
    + '<h2 class="lv-name">' + C.esc(head) + "</h2>"
    + (items.length ? '<ol class="lv-votes">' + items.join("") + "</ol>" : "")
    + '<p class="lv-status">' + C.esc(L.votesSentence(file, now, body, http)) + "</p>"
    + (items.length ? '<p class="lv-provisional">' + C.esc(C.tr("votes.provisional_line",
        "Provisional: the night's record replaces this tomorrow morning; excusals settle days later.")) + "</p>" : "")
    + (body === "S" && items.length ? '<p class="lv-provisional">' + C.esc(C.tr("votes.senate_line",
        "Senate names follow once the Senate enters them, usually that afternoon or the next day.")) + "</p>" : "")
    + '<p class="lv-more"><a href="/session/' + body + '/today">' + C.esc(today) + "</a></p></section>";
};

// The chambers with a session card today: those the night's schedule has a
// floor row for, and any the file already holds roll calls of.
L.sessionBodies = function (schedule, file, today) {
  var out = [];
  ((schedule && schedule.days && schedule.days[today]) || []).forEach(function (r) {
    if (r.kind === "floor") String(r.chamber || "").split("").forEach(function (c) {
      if (CHAMBER[c] && out.indexOf(c) < 0) out.push(c);
    });
  });
  ((file && file.rollcalls) || []).forEach(function (r) { if (CHAMBER[r.body] && out.indexOf(r.body) < 0) out.push(r.body); });
  return out.sort();
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
  var etag = null, file = null, http = null, timer = null, stopped = false, onDraw = null;

  function draw() {
    if (onDraw) onDraw();
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
    // With a fresh look, the night's list of today's meetings gives way to the
    // ones no stream was found for; otherwise it stands as the night wrote it.
    var fresh = v.status.kind === "fresh";
    var today = doc.getElementById("live-now-today"), calH = doc.getElementById("live-now-cal-h");
    if (today) today.hidden = fresh;
    if (calH) calH.hidden = fresh && !v.nostream.length;     // every meeting found: nothing to head
    if (calH) calH.textContent = fresh
      ? C.tr("live.nostream_h", "On today's calendar, no stream found (checked {time})",
             { time: L.timeOf(file && file.checked) })
      : C.tr("live.cal_h", "On today's calendar");
    [["live-now-scheduled", v.scheduled], ["live-now-nostream", v.nostream], ["live-now-earlier", v.earlier]]
      .forEach(function (x) {
        var el = doc.getElementById(x[0]);
        if (el) { el.innerHTML = x[1].join(""); el.hidden = !x[1].length; }
        // An empty list shows no heading (the site's rule).
        var h = doc.getElementById(x[0] + "-h");
        if (h) h.hidden = !x[1].length;
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
  // The session card: asked for only on a day the night's schedule has a
  // sitting on (no request on any other day).
  // Keyed on the reader's session day (L.readerDay), as the today page it
  // links to is: a sitting past midnight keeps its card until 06:00. Checked
  // again on every streams poll, so a page left open overnight finds the next
  // morning's sitting.
  var votesBox = doc.getElementById("live-now-votes");
  function sessionVotes() {
    if (out.votes || stopped || !votesBox || !L.sessionBodies(schedule, null, L.readerDay(now())).length) return;
    out.votes = L.poller({ fetch: fetchImpl, doc: doc,
      url: function () { return "/api/live/votes/" + L.readerDay(now()); },
      every: function (f) { return L.votesEvery(f, now()); },
      onFile: function (f, code) {
        var bodies = L.sessionBodies(schedule, f, L.readerDay(now()));
        votesBox.innerHTML = bodies.map(function (b) { return L.sessionCard(f, b, now(), code, schedule.bills); }).join("");
        votesBox.hidden = !bodies.length;
      } });
  }
  var out = { poll: poll, draw: draw, first: first, votes: null,
              stop: function () { stopped = true; clearTimeout(timer); if (out.votes) out.votes.stop(); } };
  sessionVotes();
  onDraw = sessionVotes;
  return out;
};

if (typeof module === "object" && module.exports) module.exports = L;
else root.GRLive = L;
if (root && root.document && root.document.getElementById && root.document.getElementById("live-now-streams")) {
  L.start(root.document);
}
})(typeof window !== "undefined" ? window : globalThis);
