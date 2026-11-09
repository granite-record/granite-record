// GRANITE_VERSION: 2026-11-06.1
/* WHICH MOTION A VOTE WAS ON, in the browser: motions.py's classify, line for
   line, for the live session page (live.js), which says a day's votes as the
   session pages say them before the night's record has the day (the owner,
   30 October 2026: "In short" from the same code and the same words).

   motions.py is the source. preflight's _motions_twin runs both over every
   roll call's question on disk and the cases below them, and fails on one
   that the two read differently, so a pattern changed in one and not the
   other is caught the night it lands.

   Python's re and JavaScript's RegExp read these patterns alike: ASCII
   words, \b, case folded with "i". The one named group, (?P<c>...), is
   (?<c>...) here. str.title() is title() below. */
(function (root) {
"use strict";

var PATTERNS = [
  ["reconsider", "\\breconsider"],
  ["untable", "\\b(?:remove|take|taken)\\s+(?:\\w+\\s+){0,3}?from\\s+(?:the\\s+)?table\\b|\\bRFT\\b"],
  ["table_amendment", "\\b(?:lay|laid)\\b.*\\bamendment\\b.*\\btable\\b|\\btable\\b.*\\bamendment\\b"],
  ["table", "\\b(?:lay|laid)\\b.*\\btable\\b|^\\s*(?:LOT|table)\\b|\\btabled?\\s*$"],
  ["nonconcur_conference", "\\bnon-?\\s*concur\\w*\\b.*\\b(?:request|req\\.?|ask)\\w*\\b.*"
                         + "\\b(?:c\\s*of\\s*c|committee\\s+of\\s+conference|conference)\\b"],
  ["nonconcur", "\\bnon-?\\s*concur"],
  ["refuse_accede", "\\brefus\\w*\\s+to\\s+accede"],
  ["accede", "\\baccede"],
  ["request_conference", "\\brequest\\w*\\s+(?:a\\s+)?(?:c\\s*of\\s*c|committee\\s+of\\s+conference)"],
  ["concur", "\\bconcur"],
  ["conference_report", "\\bconference\\s+(?:committee\\s+)?report\\b|\\bc\\s*of\\s*c\\s+report\\b"],
  ["enrolled_amendment", "\\benrolled\\s+bill\\s+amendment\\b"],
  ["committee_amendment", "\\bcommittee\\s+amendment\\b|\\bCAM\\b"],
  ["floor_amendment", "\\bfloor\\s+amendment\\b|\\bFLAM\\b"],
  ["otpa", "\\bought\\s+to\\s+pass\\s*(?:with|w/)\\s*am|\\bOTP\\s*/\\s*A\\b|\\bOTPA\\b"],
  ["ought_not_to_pass", "\\bought\\s+not\\s+to\\s+pass\\b"],
  ["otp", "\\bought\\s+to\\s+pass\\b|\\bOTP\\b"],
  ["itl", "\\binexpedient\\b|\\bITL\\b"],
  ["is", "\\binterim\\s+study\\b|\\bRFIS\\b|\\bRFS\\b"],
  ["postpone", "\\bindefinitely\\s+postpone"],
  ["recommit", "\\brecommit"],
  ["vacate_referral", "\\bvacate"],
  ["rerefer", "\\bre-?\\s*refer"],
  ["refer", "\\brefer(?:red)?\\s+to\\s+(?:the\\s+)?(?:committee\\s+on\\s+)?"
          + "(?<c>finance|ways\\s+and\\s+means|[A-Z][\\w ,&]+?)\\b(?:\\s+committee)?\\s*$"],
  ["override", "\\boverride\\b|\\bveto\\b"],
  ["special_order", "\\bspecial\\s+order"],
  ["suspend_rules", "\\bsuspen\\w*\\b.*\\brules?\\b|\\brules?\\s+suspen"],
  ["previous_question", "\\bprevious\\s+question\\b"],
  ["limit_debate", "\\blimit\\w*\\s+(?:the\\s+)?debate\\b"],
  ["order_third_reading", "\\border\\w*\\s+(?:to\\s+)?(?:a\\s+)?third\\s+reading\\b"],
  ["final_passage", "\\bfinal\\s+passage\\b"],
  ["third_reading", "\\bthird\\s+reading\\b"],
  ["divide", "^\\s*divide\\b|\\bdivi(?:de|sion\\s+of)\\s+the\\s+question\\b"],
  ["withdraw", "^\\s*withdraw"],
  ["uphold_ruling", "\\bruling\\s+of\\s+the\\s+chair\\b|\\bupheld\\b|\\buphold\\b"
                  + "|\\brule\\s+of\\s+(?:the\\s+)?chair\\b"
                  + "|\\bdecision\\s+of\\s+the\\s+(?:chair|president|speaker)\\b"],
  ["member_continue", "\\bshall\\s+(?:the\\s+)?member\\s+(?:be\\s+(?:allowed|permitted)\\s+to\\s+)?"
                    + "continue\\b"],
  ["print_debate", "\\bprint\\w*\\b.*\\b(?:debate|remarks|journal)\\b"],
  ["reprimand", "\\breprimand"],
  ["introduce_adopt", "\\bintroduc\\w*\\s+and\\s+adopt"],
  ["introduce", "\\bintroduc"],
  ["amendment", "\\bamendment\\b|^\\s*AM\\b"],
  ["adopt", "^\\s*adopt(?:ed|ion)?\\b"]
];
var COMPILED = PATTERNS.map(function (p) { return [p[0], new RegExp(p[1], "i")]; });

var UNNAMED = /^\s*(?:\d{1,2}\/\d{1,2}\/\d{2,4}|[\W\d_]*)\s*$/;
var AMD = /#?\s*\b\d{4}-\d{3,4}[a-z]?\b|\{\d{3,4}\}|#\s*\d{3,4}[a-z]?\b|\(\s*(?:Rep|Sen)s?\.[^)]*\)/gi;
var BILL_NO = /^(?:(?:SS)?(?:HB|SB|CACR|HR|SR|HCR|SCR|HJR|SJR)|HA|HCO)\d+$/i;
var NO_ROW = /\bjustices?\b/i;
var A_MOTION = /\breconsider|\bmotion\b|\breprimand|\bcensure/i;
var RESOLUTION = /^(?:HR|SR|HCR|SCR|HJR|SJR|CACR|SSHR|SSHCR)\d/i;
var SECOND_CMTE = { "finance": "Finance", "ways and means": "Ways and Means" };

function own(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }
// Python's str.title(): each run of letters capitalised, the rest lowered.
function title(s) {
  return String(s).replace(/[A-Za-z]+/g, function (w) { return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase(); });
}
function plain(s) {
  return String(s || "").replace(AMD, " ").toLowerCase().replace(/[^a-z]+/g, " ").trim();
}

// classify(text, bill, body, motionWords): {mk, mf, mrec?}, as motions.classify.
function classify(text, bill, body, motionWords) {
  var t = String(text || "").trim();
  var out = { mk: "", mf: {} };
  if (UNNAMED.test(t)) { out.mk = "unnamed"; return out; }
  if (NO_ROW.test(t)) return out;
  var onBill = BILL_NO.test(String(bill || "").replace(/\s+/g, ""));
  for (var i = 0; i < COMPILED.length; i++) {
    var key = COMPILED[i][0], m = COMPILED[i][1].exec(t);
    if (!m) continue;
    if (key === "adopt" && !RESOLUTION.test(bill || "")) continue;
    if (key === "table" && A_MOTION.test(t)) key = "table_motion";
    if (key === "untable" && A_MOTION.test(t)) break;
    if (key === "override") {
      var first = String(bill || "").slice(0, 1).toUpperCase();
      key = body && first === String(body).toUpperCase().slice(0, 1) ? "override_first" : "override_second";
    }
    if (key === "refer") {
      var c = String((m.groups && m.groups.c) || "").trim();
      if (!c || /\binterim\b|\bcommittee\s*$/i.test(c)) key = "rerefer";
      else out.mf = { Committee: own(SECOND_CMTE, c.toLowerCase()) ? SECOND_CMTE[c.toLowerCase()] : title(c) };
    }
    if (key === "otp" || key === "otpa") {
      var second = /\bref(?:er(?:red)?)?\.?\s+to\s+(?:the\s+)?(finance|ways\s+and\s+means)\b/i.exec(t);
      if (second) {
        key += "_finance";
        var sc = second[1].toLowerCase().replace(/\s+/g, " ");
        out.mf = { Committee: own(SECOND_CMTE, sc) ? SECOND_CMTE[sc] : title(second[1]) };
      }
    }
    if (key === "untable" || key.indexOf("override") === 0) {
      out.mf.Chamber = String(body || "").toUpperCase().slice(0, 1) === "H" ? "House" : "Senate";
    }
    out.mk = key;
    break;
  }
  if (out.mk && !onBill && motionWords != null) {
    var row = (own(motionWords, out.mk) && motionWords[out.mk]) || {};
    var said = ["motion", "gloss", "passed", "failed"].map(function (f) { return String(row[f] || ""); }).join(" ");
    if (/\bbill\b/i.test(said)) out = { mk: "", mf: {} };
  }
  if (out.mk && motionWords != null) {
    var r = (own(motionWords, out.mk) && motionWords[out.mk]) || {};
    var head = r.motion || "";
    Object.keys(out.mf).forEach(function (k) { head = head.split("{" + k + "}").join(out.mf[k]); });
    if (!head || plain(head) !== plain(t)) out.mrec = t;
  }
  return out;
}

var M = { classify: classify };
if (typeof module === "object" && module.exports) module.exports = M;
else root.GRMotions = M;
})(typeof window !== "undefined" ? window : globalThis);
