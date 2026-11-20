#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A proceeding as the station a bill's page draws: a committee sitting
(station_for_proceeding) or a floor or conference appearance
(station_for_floor), placed on its recording by the chair's stated boundary,
the clustering estimate or the schedule alone, and the caption times that
cannot be trusted taken out first (withhold_late_captions).

    import stations as STN
    STN.withhold_late_captions(segs, marks, work, summary)   # the recordings withheld
    STN.station_for_proceeding(p, "HB1", segs, marks, claimed)
    STN.station_for_floor(f, "HB1", marks)
    STN.fold_conference_notices(rows)   # a conference's notice folded into its recording

A SECTION OF build_site_v2.py UNTIL 20 NOVEMBER 2026 (the refactor's finding
4, reports/refactor/stage0-code.md: proceedings' stations and caption
withholding). It moved here as it stood, comments and all: CONCURRENCE,
concurrence_action, invented_end and weak_marker, which only the stations
read, then station_for_proceeding to withhold_late_captions. It imports no
builder (_import_cycles_cut). build_site_v2 imports every name here back
under its own, so build_site_v2.station_for_floor and the rest answer as they
did, for bill_stations, build_bills, load_transcripts and the checks.
"""

import re

import caption_span
import motions as MO
# Where the recordings this site links begin: one constant, which about.html
# states in words and station_for_proceeding and station_for_floor split on.
from about_figures import STREAM_START
# The vote words, which motion_keys reads a motion's key from.
from components import WORDBOOK as _WORDBOOK


CONCURRENCE = re.compile(r"concur|conference|\bc\s*of\s*c\b|accede|recede", re.I)


def concurrence_action(f):
    """True for a floor row that is a committee of conference, or whose
    action is a concurrence, a non-concurrence, a request for a committee of
    conference, an accession or a recession -- business between the chambers
    that the consent calendar never carries (station_for_floor)."""
    return (f.get("kind") == "committee of conference"
            or any(CONCURRENCE.search(str(x)) for x in (f.get("motions") or [])))


def invented_end(said):
    """True for an end segment_markers took from the bill's last mention
    where that mention was within 30 seconds of the opening, so the end is a
    minute after the chair read the number whatever the item ran.

    (17 October 2026.) 761 such ends were published; the three a person
    timed ran 809, 142 and 227 seconds against the 62, 62 and 89 shown.
    segment_markers no longer writes them -- it ends such an item at a close
    naming no bill or a vote's result, or not at all -- and this keeps a
    candidate file written before that from publishing one. last mention + 60
    under 90 seconds after the start is exactly a mention within 30."""
    return (said.get("end_from") == "last mention of the bill"
            and said.get("end") is not None and said.get("start") is not None
            and said["end"] - said["start"] < 90)


def weak_marker(mark):
    """Whether segment_markers found this boundary with a weak marker, which
    it says in the marker's "how": an inference, drawn "approximate"."""
    return "(weak marker)" in str((mark or {}).get("how") or "")


def station_for_proceeding(p, bid, segs, marks, claimed=None):
    """One committee proceeding -- a hearing or an executive session -- as the
    station the page draws. `claimed` is the set of the bill's recordings
    whose marker naming no proceeding a sitting has already taken, which
    bill_stations shares across the bill's sittings in docket order.

    Split out of main() with station_for_floor below it. The two used to sit
    ninety lines apart inside one 955-line function, which is how a lookup
    added to one of them silently missed the other.
    """
    seg = None
    for s in segs.get(p.get("video_id", ""), []):
        if s.get("bill", "").upper() == bid and s.get("kind") == p["proceeding"]:
            seg = s
            break
    # A CLUSTERING PLACEMENT WITH NO MENTION OF THE BILL INSIDE IT IS NOT
    # PUBLISHED. (17 October 2026.) The aligner gives every scheduled
    # proceeding a span, and where the bill is never named inside the span it
    # chose, the span is a slot the docket's order left over, most often its
    # 30-second minimum: 321 of the site's 1,099 clustered placements were
    # exactly 30 seconds, and 399 had no mention of the bill inside. The four
    # of them a person timed were 4, 30, 77 and 202 minutes out. Without one
    # the sitting keeps its recording and says the start was not identified,
    # which is true, and offers no "automatic pass suggested" time either.
    #
    # A mention in the minute before the span counts as inside it. (After
    # review, 17 October 2026.) 27 of the 372 withheld had the bill named just
    # before: "On to House Bill 1315 relative to the sale of tobacco products"
    # at 3:42:30 on 120gOWa2Jl0, its 30-second slot half a minute on.
    # segment_markers finds those where the captions are and lists them under
    # _named_before as "BILL|kind".
    if (seg and seg.get("located") and seg.get("mentions_inside") == 0
            and f"{bid}|{p['proceeding']}" not in
            ((marks.get("_named_before") or {}).get(p.get("video_id") or "") or [])):
        seg = None
    # THE RECORDINGS THIS SITTING COULD BE, where the matcher declined to
    # pick one of them. build_manifest writes the ids whenever more than one
    # recording of the committee exists that day; build_proceedings carries
    # them. Empty on every row where one recording was chosen, and on every
    # row from a day that had only one.
    cands = [v for v in str(p.get("candidate_ids") or "").split(" | ") if v]
    # Five states, and the two in the middle are the point. A recording
    # matched to the proceeding with only an approximate starting point is
    # still far more useful than no link at all: the reader scrubs a few
    # minutes instead of hunting through 331 videos. Exact timestamps
    # are an upgrade to this, not a precondition for it.
    #
    # `candidates` is the same argument one level up -- the day and the
    # committee are known and the tape is not. It is tested before the date,
    # because "recordings of this committee exist that day" is a fact about
    # the index and STREAM_START, the day the General Court's YouTube
    # channels begin, is a fact about the calendar; nothing reaches both,
    # since the index holds nothing older than the channels. 317
    # proceedings of 100,556 are in it: 236 Finance, whose divisions stream
    # separately and which the docket does not tell apart, and 81 whose
    # scheduled minute fell inside more than one stream. They used to fall
    # to "novideo", which app.js draws as "No recording matched to this
    # proceeding." -- a claim this site's own manifest contradicts.
    if seg and seg.get("located"):
        state, start = "located", seg["start"]
    elif p.get("video_id"):
        state, start = "approximate", None
    elif cands:
        state, start = "candidates", None
    elif p["sched_date"] < STREAM_START:
        state, start = "prestream", None
    else:
        state, start = "novideo", None
    # A stated boundary replaces the estimate outright.
    # The filter exists to stop a hearing's boundary being handed to an
    # executive session on the same recording. A marker that names the
    # proceeding is checked against the kind; one that does not -- a weak
    # marker with no noun, or the bare word "session", which one chair uses
    # for what the docket calls a public hearing -- makes no claim to check,
    # so it is kept as a fallback rather than discarded.
    #
    # Two passes, in that order. Discarding the ambiguous ones outright cost
    # HB1123 its boundary: the chair said "we're opening the session on House
    # Bill 1123", the docket calls it a public hearing, neither word contained
    # the other, and the only quotation on the recording was thrown away in
    # favour of a clustered guess a minute and a half out.
    AMBIGUOUS = {"", "session"}

    # THE LAST WORD IS NOT THE DISTINGUISHING WORD. An executive session, a
    # work session and a subcommittee work session all end in "session", so a
    # last-word test says a marker for one is a marker for another. That was
    # harmless only while segment_markers mislabelled every one of them as the
    # bare word "session", which AMBIGUOUS caught and demoted. Fixing that
    # labelling on 2,580 markers turned the weakness live: measured against the
    # rebuilt markers, 460 stations would take a marker of the wrong kind --
    # 301 an executive session's moment onto a work session, 159 the reverse.
    # On one recording those are different times, so each is a wrong moment
    # published as a stated one.
    #
    # "exec" is what chairs actually say -- "going to open up the exec session
    # for HB 251" -- and "exact" is what the captions make of it, 402 times.
    # Both are the same sitting and both normalise here; the captions garble
    # bill numbers the same way, which is why nothing on this site quotes them.
    def _kind_key(s):
        s = re.sub(r"[^a-z ]", " ", str(s or "").lower())
        s = re.sub(r"\b(?:exec|exact)\b", "executive", s)
        for k in ("conference", "floor", "executive", "work", "hearing"):
            if k in s:
                return k
        return ""

    def _matches(cand):
        want = str(p.get("proceeding") or "").lower()
        what = str(cand.get("what") or "")
        if not want or not what or what in AMBIGUOUS:
            return None
        kw, kp = _kind_key(what), _kind_key(want)
        # Neither recognisable: no claim to check, so it stays a fallback
        # rather than becoming a match or a refusal.
        if not kw or not kp:
            return None
        return kw == kp

    usable = [c for c in (marks.get(p.get("video_id") or "") or {}).get(bid, [])
              if isinstance(c, dict) and c.get("start") is not None]
    said = next((c for c in usable if _matches(c) is True), None)
    # AN AMBIGUOUS MARKER SERVES ONE PROCEEDING. (17 October 2026.) A marker
    # that names no proceeding is a fallback for whichever sitting of the
    # bill on this recording has none of its own, and the first such marker
    # was handed to every one of them: 341 moments were published on two
    # proceedings of one bill, 687 stations, chiefly an executive session and
    # the hearing or full committee work session before it. bill_stations
    # calls this in docket order with one `claimed` for the bill, so the
    # first sitting with no marker of its own takes the first such marker
    # spoken, and the later ones take none.
    #
    # Not the next one along, which was tried first and read: of the 39
    # sittings it moved to a second marker that names no proceeding, about
    # nine were their own openings ("open up executive uh session on HB
    # 1256") and most of the rest were the same hearing a minute on -- the
    # sponsor's "introduce house bill 10 40" 68 seconds after the chair's
    # "begin house bill 1040" -- or a remark ("open to everyone for people to
    # enjoy"). A later sitting falls back to the clustering, or to the
    # recording with its start not identified.
    vid = p.get("video_id") or ""
    if said is None and (claimed is None or vid not in claimed):
        said = next((c for c in usable if _matches(c) is None), None)
        if said is not None and claimed is not None:
            claimed.add(vid)

    # The clustering's end, but only where it is describing the same span.
    #
    # A stated start replaces the clustered one outright, and it does that
    # precisely in the cases where the two disagree. Reaching past it for the
    # clustered END then pairs a quotation with an inference about somewhere
    # else in the recording. 2,732 proceedings did that: 429 ended at or
    # before the start they were pinned to -- which the page dropped without a
    # word, so a wrong number became a missing one in silence -- and 743 more
    # came from a placement further from the chair's than the clustering's own
    # tolerance allows, giving the reader a duration that was never measured
    # from that point.
    #
    # The threshold is the segment's own tolerance rather than one invented
    # here: the aligner already says how sure it is, from 30 seconds where the
    # evidence was thick to half an hour where it was thin, and a placement
    # inside that is the same placement. Where it is not, the proceeding keeps
    # its stated start and no end, which the page already draws as "from
    # 1:19:26".
    seg_end = None
    # Not where the bill was named only before the span (_named_before): the
    # start is the item, a little late, and the end is the aligner's
    # 30-second minimum, which is no measurement of how long it ran.
    if (seg and seg.get("located") and seg.get("end") is not None
            and seg.get("mentions_inside") != 0):
        anchor = said["start"] if said else seg.get("start")
        near = (abs(seg["start"] - anchor) <= (seg.get("tolerance") or 300)
                if said else True)
        if anchor is not None and seg["end"] > anchor and near:
            seg_end = seg["end"]

    # WHERE THE END CAME FROM, AND WHETHER IT IS WORTH PUBLISHING.
    #
    # segment_markers.py records how it decided each end and the site threw
    # that away, so a chair announcing "we are closed on 1118" and the moment
    # the NEXT bill happened to be opened arrived on the page as the same
    # kind of fact. Scored against 43 hand-timed proceedings:
    #
    #   the chair closed it        10 scored, median 0m 04s, 10/10 in a minute
    #   last mention of the bill    8 scored, median 0m 59s,  5/8
    #   next boundary               7 scored, median 29m 06s, 1/7
    #
    # An end taken from the next boundary inherits every error in the
    # placement of the item after it, and it does so in both directions:
    # HB84's hearing was published as 101 seconds against the 29 minutes it
    # ran, SB659's was stretched 94 minutes past where it finished. There is
    # no offset that repairs a thing that fails both ways, and 2,338 segments
    # -- 43% of every end this site has -- come from it.
    #
    # So it is not published. The proceeding keeps its start, which is good
    # to four seconds where a chair spoke it, and the page draws it as "from
    # 1:19:26" exactly as it already does for a proceeding that never had an
    # end. end_from still records what the candidate was, so a null end here
    # reads as "we had a number and would not stand behind it" rather than as
    # "we found nothing".
    UNPUBLISHABLE = {"next boundary"}
    end_from = None
    end_val = None
    if said and said.get("end") is not None:
        end_from = said.get("end_from") or "the chair closed it"
        end_val = said["end"]
    elif seg_end is not None:
        end_from = "clustered"
        end_val = seg_end
    if end_from in UNPUBLISHABLE or (said and invented_end(said)):
        end_val = None
    # A HEARING TAKES NO VOTE, so a vote result does not end one. (17 October
    # 2026, after review.) segment_markers knows the proceeding only where the
    # chair named it; four of the five vote-result ends published on hearings
    # were testimony or an aside. The docket's kind is the one that knows.
    if end_from == "vote result" and "hearing" in str(p.get("proceeding") or "").lower():
        end_val = None

    # The state the page will actually see, computed once: the key below has
    # to agree with it, and an inline ternary in two places is how two things
    # that must agree stop agreeing.
    shown = "stated" if said else state
    return {
        "when": p["sched_date"], "time": p.get("sched_time"),
        "what": p["proceeding"], "committee": p.get("committee"),
        # Which chamber's committee, from proceedings.csv's own
        # column. A House bill is heard by a Senate committee too,
        # so this cannot be read off the bill number.
        "body": p.get("body"),
        "venue": p.get("venue"), "video_id": p.get("video_id"),
        "watch": p.get("watch_url"), "predicted": p.get("predicted_offset"),
        "start": said["start"] if said else start,
        "state": shown,
        # ONLY WHERE NOTHING WAS CHOSEN. A row that got a pick carries these
        # ids too -- build_manifest writes them whenever the day held more
        # than one recording, and 246 of the 563 were resolved by the clock
        # -- and shipping them beside a chosen recording would invite the
        # page to offer a reader alternatives to a match this site stands
        # behind. Absent rather than null on the other 100,239 stations, the
        # way "archived" is absent on a current bill: every key is paid for
        # 33,683 times.
        **({"candidate_ids": cands} if shown == "candidates" else {}),
        # NOT NAMED ON THE RECORDING (17 October 2026, the wording the person
        # approved). Where the recording's captions never name the bill, by
        # number or by title, no pattern can mark a moment in it, and the
        # page said the matching "is not done". segment_markers lists such
        # bills under _not_named; the page now says the recording does not
        # name the bill. Only on a sitting drawn with no start, and absent
        # elsewhere, as candidate_ids is.
        **({"not_named": True} if shown == "approximate" and bid in (
            (marks.get("_not_named") or {}).get(p.get("video_id") or "") or []) else {}),
        # The aligner sets a tolerance per segment from how much
        # evidence it had -- 3 minutes with many bill mentions, 30 with
        # a short span and few. Dropping it here made every hearing on
        # the site claim the same +/-5 minutes, understating the good
        # ones and, worse, overstating the weak ones.
        "tolerance": (5 if said else
                      (seg.get("tolerance") if seg else None)),
        "short": bool(seg.get("short")) if seg else False,
        # The aligner produces a span, not a point. Showing only the
        # start throws away half of it -- and the duration is what tells
        # a reader whether a proceeding was a five-minute executive
        # session or a two-hour hearing before they click anything.
        # A stated close outranks a clustered one: four seconds at the
        # median against whatever the cluster's tail happened to be.
        "end": end_val,
        # WHAT IT SAYS, NOT WHETHER THERE IS ONE. This was
        # bool(said and said.get("end")), which is "an end exists" -- so
        # SB659's end, which is the second HB1815 was opened 94 minutes after
        # the hearing finished, was recorded as stated by the chair. It is
        # true now only where the close itself was spoken: segment_markers
        # leaves end_from unset in exactly that case, and those score four
        # seconds at the median against a stopwatch.
        "end_stated": bool(said and said.get("end") is not None
                           and not said.get("end_from")),
        # How the end was decided, or -- where end is null -- what the
        # candidate was that this refused to publish.
        "end_from": end_from,
        "candidate": seg["start"] if seg and not seg.get("located") else None,
        # Which ends of this span were stated by the chair rather than
        # inferred, written by apply_markers.py. The page does not say
        # so in words -- the tolerance carries that -- but it decides
        # the tolerance's unit and how early the player opens, and it
        # is what a methodology page would count.
        #
        # Per end, not per segment: a Senate chair announces the close
        # and not the opening, so a proceeding can have a quoted end
        # and an estimated start.
        #
        # The caption lines themselves stay in work/<id>/segments.json
        # as the audit trail and are not shipped to the browser.
        # Seconds, not minutes: a boundary the chair said is good to
        # about a second, and calling that "+/- 1 min" would understate
        # it as badly as the old tolerances overstated theirs.
        # A WEAK MARKER IS AN INFERENCE (23 October 2026). segment_markers
        # calls a phrase weak where it names no proceeding or is a reading
        # the chair did not frame as an opening -- the bill's title read and
        # then a motion, the sponsor welcomed -- and says so in its "how".
        # Good to a few seconds on the bench, but not the chair saying "we
        # will now open", so the page gives it the one word an inferred
        # start carries, "approximate" (CLAUDE.md, Timestamps).
        "start_stated": (not weak_marker(said)) if said else (
            bool(seg.get("start_stated")) if seg else False),
        # The words are deliberately NOT published. Captions mangle
        # bill numbers constantly, and a garbled quote presented as the
        # chair's own words is a transcription error wearing the
        # clothes of a citation. How it was found is kept, because that
        # is a fact about this site's method rather than a claim about
        # what anyone said.
        "said_how": said.get("how") if said else None,
        "end_stated_cluster": bool(seg.get("end_stated")) if seg else False,
    }


def fold_conference_notices(rows):
    """One bill's floor rows, with a conference's notice folded into its recording.

    A committee of conference that was noticed on a docket and recorded on a
    channel is two rows of proceedings.csv: the docket's, with the time and
    the room and no recording, and the floor index's, with the recording and
    neither. Each became a station, so the bill page drew the one sitting
    twice on the same day -- once as "No recording matched to this
    proceeding." at 09:30 in LOB 206-208, and once as the recording with no
    time -- and HB 1709's of 26 May 2026, which is on two recordings, three
    times. 61 Senate bill-days were drawn so, SB 108's of 13 June 2025 among
    them, and reading the House's notices too (docket_parser) made it 159.

    So where a bill has a recorded conference on a day, a notice of a
    conference that day with no recording is the same sitting: it is dropped,
    and its time and room go onto the recorded row, which has none of its own.
    Where there are several notices the earliest time is the one the sitting
    was called for. A notice no recording covers is left as it is, and draws
    "No recording matched", which is true. Nothing else is touched: a floor
    debate is never folded, and neither is a conference on another day.
    """
    conf = "committee of conference"
    recorded = {f.get("date") for f in rows
                if f.get("kind") == conf and f.get("video_id")}
    notice = {}
    for f in rows:
        if (f.get("kind") == conf and not f.get("video_id")
                and f.get("date") in recorded):
            cur = notice.get(f["date"])
            if cur is None or (f.get("time") or "~") < (cur.get("time") or "~"):
                notice[f["date"]] = f
    if not notice:
        return list(rows)
    out = []
    for f in rows:
        if f.get("kind") != conf or f.get("date") not in notice:
            out.append(f)
        elif f.get("video_id"):
            n = notice[f["date"]]
            out.append(dict(f, time=f.get("time") or n.get("time") or "",
                            venue=f.get("venue") or n.get("venue") or ""))
    return out


def motion_keys(motions, bid, body):
    """[{"mk": key, "mf"?: fill}] for each of a floor appearance's motions,
    in their order: the key and the fill of the approved vote words
    (motions.classify, as a roll call on the Votes tab has them), so the
    Hearings tab names a motion as the Votes tab does -- "Ought to Pass with
    Amendment (OTPA, Pass the bill with changes)" where the floor index has
    the clerk's "OTPA" (the audit of 25 October 2026, S2). A key of "" is
    a motion the words do not name, and the page then shows the record's."""
    words = _WORDBOOK["votes"]["motions"]
    out = []
    for m in motions or []:
        k = MO.classify(m, bid, body, words)
        out.append({"mk": k["mk"], **({"mf": k["mf"]} if k.get("mf") else {})})
    return out


def station_for_floor(f, bid, marks):
    """One floor appearance as a station.

    Returns a finished dict. The consent case and the stated-boundary upgrade
    are applied before returning, rather than by reaching back into
    stations[-1] after appending.
    """
    precise = f.get("precise") and f.get("debate_end")
    # NO RECORDING AT ALL. 1,613 committee-of-conference sittings are on the
    # docket and on neither of the General Court's channels, and they came
    # through here as "floor_dated" -- which app.js draws as a player: an
    # embed of an empty id and an "Open on YouTube" link to watch?v=, on
    # sittings from 1990 on. They take the two states a committee sitting
    # with nothing to play takes, split on the same date: older than the
    # channels, or since them and unmatched. And they keep the time and the
    # room the docket gives, which proceedings.csv has for all but one and
    # the page used to drop.
    if not f.get("video_id"):
        # The index's own word for what this is, as below.
        kind = f.get("kind") or "floor debate"
        return {
            "when": f["date"], "time": f.get("time") or None,
            "what": kind,
            "committee": ("House" if f.get("body") == "H" else "Senate"
                          ) if kind == "floor debate" else None,
            "venue": f.get("venue") or None, "video_id": "", "watch": None,
            "predicted": None, "start": None, "debate_end": None,
            "window_start": None,
            "motions": f.get("motions", []), "tallies": f.get("tallies", []),
            "state": ("prestream" if (f.get("date") or "") < STREAM_START
                      else "novideo"),
            "candidate": None}
    # A conference's time and room, where fold_conference_notices put its
    # docket notice's onto the recording. A floor-index row carries neither
    # of its own, so on every other recorded row these are None as they were.
    conf_when = (f.get("time") or None, f.get("venue") or None) if (
        f.get("kind") == "committee of conference") else (None, None)
    if f.get("whole_video"):
        # The title names the bill, so the entire recording is this
        # proceeding. No timestamp to estimate and none needed.
        return {
            "when": f["date"], "time": conf_when[0],
            "what": f.get("kind", "committee of conference"),
            "committee": None, "venue": conf_when[1],
            "video_id": f["video_id"],
            "watch": f"https://www.youtube.com/watch?v={f['video_id']}",
            "predicted": None, "start": 0, "debate_end": None,
            "window_start": None, "motions": [], "tallies": [],
            "title": f.get("title", ""),
            "state": "whole_video", "candidate": None}
    # THE INDEX'S OWN WORD FOR WHAT THIS IS, not "floor debate" for everything
    # that is not a whole recording. build_floor_index.py writes three kinds --
    # "floor debate", "committee of conference" and "recording naming this
    # bill" -- and only the whole_video branch above read it, so a conference
    # was labelled a floor debate whenever its recording named more than one
    # bill. 63 of the 114 recordings that carry a kind name several, and the
    # page called 191 committee-of-conference proceedings "House Floor Debate"
    # and 12 more the same.
    #
    # And no chamber on those, the way the whole_video branch already does it:
    # a committee of conference is both chambers sitting together, so
    # "House Committee Of Conference" would be a second wrong claim under the
    # first. f["body"] is the chamber whose channel carried the recording, not
    # the body that met.
    kind = f.get("kind") or "floor debate"
    st = {
        "when": f["date"], "time": conf_when[0],
        "what": kind,
        "committee": ("House" if f.get("body") == "H" else "Senate"
                      ) if kind == "floor debate" else None,
        "venue": conf_when[1], "video_id": f["video_id"],
        "watch": (f"https://www.youtube.com/watch?v={f['video_id']}"
                  f"&t={max(int(f.get('window_start') or 0) - 60, 0)}s"),
        "predicted": None,
        "start": (max(f.get("window_start", 0),
                      f["debate_end"] - 1800) if precise else None),
        "debate_end": f.get("debate_end") if precise else None,
        "window_start": f.get("window_start") if precise else None,
        "motions": f.get("motions", []), "tallies": f.get("tallies", []),
        "state": "floor_precise" if precise else "floor_dated",
        "candidate": None,
    }
    # Each motion's key in the approved vote words, so the Hearings tab
    # names it as the Votes tab does (motion_keys).
    if st["motions"]:
        st["mks"] = motion_keys(st["motions"], bid, f.get("body") or "")
    # The clerk reads a committee report to open every bill, and
    # segment_markers.py finds it. That is the START of the debate --
    # exact, and from the clerk's own words. Without it the player fell
    # back to the window, which opens at the PREVIOUS bill's roll call
    # and can be half an hour of other business away.
    #
    # This branch once did not consult the markers at all: they were
    # found, written, and ignored, because floor stations were built in
    # one place and the lookup was added in another, ninety lines away
    # in the same function. The same manifest-and-floor-index split, for
    # the fifth time. Both halves are now one short function each, and
    # the station is finished before it is returned rather than adjusted
    # through stations[-1] after the fact.
    # A bill never named on its own floor recording passed on the
    # consent calendar: adopted as part of a block, never read out,
    # never debated. Offering to play a nine-hour session for it invites
    # a reader to listen for something that is not there.
    #
    # A recorded roll call on the bill that day overrules it. (17 October
    # 2026.) "Never named" is read off the captions, and the captions garble
    # bill numbers: HB 1002 was tabled 187-157 on 12 February 2026 while
    # the clerk's reading came out as "house bill 10002", and HB 1602 had two
    # roll calls on 19 February, so both were drawn as passed on the consent
    # calendar, which is a wrong fact rather than a missing time. A roll call
    # is the chamber's own record that the bill was voted on by itself, and
    # a bill on the consent calendar never is. The roll call's tallies are
    # what proceedings.csv carries for that day, so they decide it.
    #
    # NOR IS A CONCURRENCE OR A CONFERENCE EVER THE CONSENT CALENDAR. (After
    # review, 17 October 2026.) Concurring or not with the other chamber's
    # amendment, asking for a committee of conference, acceding to one and
    # adopting its report are taken up in their own order, and often off any
    # recording of the day's session: HB 250's non-concurrence of 22 May 2025
    # (YobZAwJsSQo) was drawn as passed on consent, and 74 consent stations
    # of the 15 October build were actions of that kind. They show the day.
    if (bid in (marks.get("_absent") or {}).get(f.get("video_id") or "", [])
            and not f.get("tallies") and not concurrence_action(f)):
        st["state"] = "consent"
        st["start"] = None
        # Not a debate. The heading read "House floor debate" over a paragraph
        # explaining the bill was never debated, which is the page contradicting
        # itself in two lines.
        st["what"] = "consent calendar"
        return st

    # A COMMITTEE OF CONFERENCE TAKES ITS OWN OPENING. (17 October 2026.)
    # segment_markers names one "committee of conference" when the chair
    # convenes it, and this accepted only "" or "floor debate", so 25
    # conference sittings with the chair's own words on record drew no time
    # and 2 drew a later, wrong one: HB 710 on dIumWRhMDrY showed 1:20:08,
    # "open the door", where the chair said "convene the Committee of
    # Conference on House Bill 710" at 0:16:39. Still the first one spoken,
    # not its own kind first: "We'll open a COC on Senate Bill 96" at 0:02:48
    # on 89R50nnQFrE is the opening and names no proceeding the patterns
    # know, and "convene the committee of conference on Senate Bill 96" is
    # the same sitting coming back two and a half hours later.
    kinds = ("", "floor debate") + (("committee of conference",)
                                    if kind == "committee of conference" else ())
    said_f = None
    for cand in (marks.get(f.get("video_id") or "") or {}).get(bid, []):
        if not isinstance(cand, dict) or cand.get("start") is None:
            continue
        if str(cand.get("what") or "") not in kinds:
            continue
        end = f.get("debate_end")
        if precise and end and not (0 <= end - cand["start"] <= 7200):
            continue      # not this sitting's debate
        said_f = cand
        break
    if said_f:
        st["start"] = said_f["start"]
        st["debate_start"] = said_f["start"]
        st["start_stated"] = not weak_marker(said_f)
        st["said_how"] = said_f.get("how")
        if not precise and said_f.get("end") and not invented_end(said_f):
            st["debate_end"] = said_f["end"]
            st["state"] = "floor_stated"
    return st


def withhold_late_captions(segs, marks, work, summary=caption_span.SUMMARY):
    """Take every time read off a caption track that is out of step with its
    recording out of both sources, before a station is drawn from either.

    The chair's stated boundary and the clustering estimate are both read off
    the captions, so a track that starts an hour late puts both an hour early.
    When it was measured, that was 74 published starts on nine recordings, 55
    of them drawn as the moment the chair opened the proceeding. caption_span.py
    holds the measurement and the line.

    What is left is the schedule, which comes from the stream's own clock: the
    page opens the recording five minutes before the scheduled time and says
    the start was not identified, which is true. The consent calendar goes
    too -- "never named on the recording" is read off the same track, and a
    track that stops short of its recording may simply not reach the bill.

    ON THE NIGHTLY'S MACHINE there are no caption files, and `summary` --
    caption_spans.json, written where they are -- answers for each recording
    instead. With a summary in use, a recording that has times and neither a
    caption file nor an entry is withheld as well: nothing here can say its
    track is in step, and a summary that fell behind must cost a "start not
    identified", never a start an hour early.
    """
    vids = set(segs) | {k for k in marks if not k.startswith("_")}
    spans = caption_span.load_summary(summary)
    rep = {}
    late, compared, undated = caption_span.out_of_step(vids, work, spans=spans,
                                                       report=rep)
    unknown = rep.get("unsummarised") or []
    # A caption job that did not rewrite the summary leaves a handful of new
    # recordings unknown, and withholding them is the right answer. Most of
    # them unknown is not a summary that fell behind -- it is an empty one, or
    # another machine's -- and a site with every timestamp withdrawn is a
    # failed build, not a cautious one.
    if spans is not None and len(unknown) > max(25, len(vids) // 20):
        raise SystemExit(
            f"{summary} knows {rep.get('from_summary', 0):,} of the "
            f"{len(vids):,} recordings with times, and {len(unknown):,} have "
            f"neither an entry there nor a caption file under {work}/. That is "
            "the wrong summary or an empty one. Rewrite it where the captions "
            "are: python3 src/hearings/caption_span.py --write")

    def read_off(vs):
        return (sum(len(c) for v in vs for c in (marks.get(v) or {}).values()),
                sum(1 for v in vs for s in (segs.get(v) or []) if s.get("located")))
    said, placed = read_off(late)
    u_said, u_placed = read_off(unknown)
    # segment_markers' one list of the maps beside the recordings.
    from segment_markers import SIDES
    for v in list(late) + list(unknown):
        segs.pop(v, None)
        marks.pop(v, None)
        for side in SIDES:
            if isinstance(marks.get(side), dict):
                marks[side].pop(v, None)
    print(f"caption tracks: {compared:,} recordings compared with the length "
          "YouTube published")
    if rep.get("from_summary"):
        print(f"  {rep['from_summary']:,} of them answered by {summary}: no "
              f"caption file for them under {work}/ on this machine")
    if unknown:
        print(f"  {len(unknown):,} have times and neither a caption file under "
              f"{work}/ nor an entry in {summary}, so nothing here says their "
              f"captions are in step; their {u_said:,} stated boundaries and "
              f"{u_placed:,} clustered placements are withheld: "
              f"{', '.join(unknown[:6])}{' ...' if len(unknown) > 6 else ''}")
    # Nothing compared is not the same as nothing late, and the two print
    # differently.
    if vids and not compared:
        print(f"  NONE could be compared -- no caption file under {work}/ for "
              f"any of {len(vids):,} recordings, or no videos_*.csv here -- so "
              "nothing was checked and nothing withheld")
    if undated:
        print(f"  {len(undated):,} have captions and no published length, so "
              f"were not compared: {', '.join(undated[:4])}")
    if late:
        print(f"  {len(late):,} stop more than {caption_span.SLACK // 60} "
              f"minutes short of their recording; {said:,} stated boundaries "
              f"and {placed:,} clustered placements read off them are "
              f"withheld: {', '.join(sorted(late))}")
    return late
