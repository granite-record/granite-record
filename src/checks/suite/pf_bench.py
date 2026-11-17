#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.1
"""
preflight's checks of the bench: the ledger a person's judgments are kept in
(review/checked.jsonl) and every reader of it (src/lib/bench_ledger.py,
src/checks/review.py, src/hearings/probe_alignment.py read_bench), and the
shared bench the owner approved on 17 November 2026 -- its database and the
code its Pages Functions share (workers/bench/), the Functions
(functions/bench.js, functions/api/bench/), their tests (tests/bench/), and
the two laptop tools (src/checks/bench_pack.py, src/checks/bench_pull.py).

A module of its own, because the bench is one feature written across four
folders. Its checks are not in ORDER.json, and run after those it lists.
This module uses pf_core and itself, and no other area's module.
"""

import io
import json
import shutil
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

from pf_core import check


def _ledger(path, lines):
    """A ledger at `path`, one JSON line a dict of `lines`."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("".join(json.dumps(d) + "\n" for d in lines), encoding="utf-8")


class _Answer:
    """What review.Bench.do_POST sent, read back: status, and the page."""

    def __init__(self, raw):
        head, _, body = raw.partition(b"\r\n\r\n")
        self.status = int(head.split(b" ")[1])
        self.head = head.decode("latin-1")
        self.body = body.decode("utf-8", "replace")


def _post(RV, fields):
    """POST /save to the laptop's bench, with no socket: the handler's own
    do_POST over a form of `fields`."""
    from urllib.parse import urlencode
    body = urlencode(fields).encode("utf-8")
    h = RV.Bench.__new__(RV.Bench)
    h.rfile, h.wfile = io.BytesIO(body), io.BytesIO()
    h.headers = {"Content-Length": str(len(body))}
    h.request_version, h.command = "HTTP/1.1", "POST"
    h.requestline, h.client_address = "POST /save HTTP/1.1", ("127.0.0.1", 0)
    h.close_connection = True
    h.do_POST()
    return _Answer(h.wfile.getvalue())


@check("build", "the laptop's bench chooses no answer for you: no verdict is checked in advance, "
                "a Save with none records nothing and draws the same item again, and an answer "
                "records one line, at the moment it is given", needs=("review",))
def _bench_no_answer_chosen(RV):
    """From its first day (9 September 2026) the bench drew every form with
    the first answer checked -- "correct", or "yes" for a tag -- so Save
    pressed without reading recorded a judgment, and nothing in the ledger
    tells such a line from one meant (the owner, 17 November 2026: "must not
    pre-select an answer"). Held, for every kind the bench has: no radio of
    the form is checked and each is required; the answers offered are the
    kind's verdicts(); a Save with no verdict, or one the kind does not
    offer, answers 400 with the reason and the same item and writes nothing;
    a Save with one writes one line, "by": "hand"; a Skip is a line of its
    own; and record() keeps a moment it is given (bench_pull.py merges a
    hosted answer with the time it was made), and gives one where none is."""
    import re
    shows = {k: v["show"] for k, v in RV.KINDS.items()}
    item = {"key": "v1|HB1|hearing", "bill": "HB1"}
    try:
        for kind in RV.KINDS:
            RV.KINDS[kind]["show"] = lambda it: "<p>the item</p>"
            form = RV.form_html(kind, item)
            radios = re.findall(r'<input type="radio"[^>]*>', form)
            assert radios and len(radios) == len(RV.verdicts(kind)), (kind, radios)
            assert not [r for r in radios if re.search(r"\bchecked\b", r)], (
                f"{kind}: an answer is checked before anyone chose it: {radios}")
            assert all(" required" in r for r in radios), f"{kind}: an answer is not required"
            got = re.findall(r'name="verdict" value="([^"]*)"', form)
            assert got == [v for v, _ in RV.verdicts(kind)], (kind, got)
    finally:
        for kind, fn in shows.items():
            RV.KINDS[kind]["show"] = fn

    tmp = Path(tempfile.mkdtemp(prefix="gr-bench-"))
    saved = (RV.OUT, RV.LEDGER, dict(RV.Bench.pool), RV.KINDS["topic"]["show"])
    try:
        RV.OUT, RV.LEDGER = tmp / "review", tmp / "review" / "checked.jsonl"
        topic = {"key": "topic|2023-2024|HB267", "kind": "topic", "term": "2023-2024",
                 "bill": "HB267", "title": "t", "committee": "c", "topic": "Employment",
                 "margin": 0.9, "why": []}
        RV.Bench.pool = {"topic": [topic]}
        RV.KINDS["topic"]["show"] = lambda it: "<p>the item</p>"
        form = {"kind": "topic", "key": topic["key"], "shown": json.dumps(topic), "note": "",
                "better_topic": "Labor", "action": "save"}
        for what, extra in (("no answer", {}), ("an answer the kind does not offer", {"verdict": "yes"})):
            a = _post(RV, {**form, **extra})
            assert a.status == 400 and RV.NOT_SAVED in a.body and topic["key"] in a.body, (
                f"a Save with {what} answered {a.status}, or not with its reason and the same item")
            assert not RV.LEDGER.exists(), f"a Save with {what} wrote to the ledger"
        a = _post(RV, {**form, "verdict": "wrong"})
        assert a.status == 303, a.head
        lines = [json.loads(x) for x in RV.LEDGER.read_text(encoding="utf-8").splitlines()]
        assert len(lines) == 1 and lines[0]["verdict"] == "wrong" and lines[0]["by"] == "hand" and \
            lines[0]["fields"] == {"better_topic": "Labor"} and re.match(
                r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$", lines[0]["at"]), lines
        a = _post(RV, {**form, "action": "skip"})
        lines = [json.loads(x) for x in RV.LEDGER.read_text(encoding="utf-8").splitlines()]
        assert a.status == 303 and len(lines) == 2 and lines[1]["verdict"] == "skipped", lines
        RV.record({"kind": "topic", "key": "k", "verdict": "correct", "by": "link:ab12",
                   "at": "2026-11-20T19:04:12"})
        last = json.loads(RV.LEDGER.read_text(encoding="utf-8").splitlines()[-1])
        assert last["at"] == "2026-11-20T19:04:12", "record() replaced the moment it was given"
    finally:
        RV.OUT, RV.LEDGER, RV.Bench.pool, RV.KINDS["topic"]["show"] = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(RV.KINDS)} kinds' forms with no answer checked and every one required; a "
                  "Save with none, or one not offered, answered 400 and wrote nothing; an answer "
                  "and a Skip wrote a line each; a given moment kept")


# A ledger written for the check below: the owner's line and a contributor's on
# one item in both orders, a contributor's alone, a withdrawn link's, a line
# that is no one's, a topic and a tag. Seconds are the observed starts.
_HAND, _SAM, _ANN, _GONE = "hand", "link:ab12", "link:cd34", "link:ef56"


def _timing(vid, by, start, verdict="wrong"):
    return {"kind": "timestamp", "key": f"{vid}|HB1|hearing", "verdict": verdict, "note": "",
            "by": by, "fields": {"observed_start": start} if start else {},
            "shown": {"video_id": vid, "bill": "HB1", "proceeding": "hearing",
                      "committee": "c", "start": 90}}


_MIXED = [
    _timing("V1", _SAM, "0:01:40"),            # theirs, before hers
    _timing("V1", _HAND, "0:03:20"),           # hers: the one that counts
    _timing("V1", _SAM, "0:05:00"),            # theirs, after hers: never replaces it
    _timing("V2", _ANN, "0:06:40"),            # theirs alone: counts, as theirs
    _timing("V3", _GONE, "0:08:20"),           # a link the owner withdrew
    _timing("V4", "agent", "0:10:00"),         # no one's
    _timing("V5", _ANN, "", "correct"),        # theirs, accepted without timing
    {"kind": "topic", "key": "topic|2023-2024|HB267", "verdict": "correct", "by": _HAND,
     "shown": {}},
    {"kind": "topic", "key": "topic|2023-2024|HB267", "verdict": "wrong", "by": _SAM, "shown": {}},
    {"kind": "tag", "key": "tag|mental-health|title|2001-2002/HB11", "verdict": "no", "by": _SAM,
     "shown": {"hard": False}},
    {"kind": "tag", "key": "tag|mental-health|title|2001-2002/HB11", "verdict": "yes", "by": _HAND,
     "shown": {"hard": False}},
    {"kind": "tag", "key": "tag|mental-health|title|2001-2002/HB12", "verdict": "yes", "by": _ANN,
     "shown": {"hard": False}},
    {"kind": "withdraw", "by": _HAND, "link": "ef56"},
]


@check("build", "every reader of the bench's ledger lets the owner's line beat a contributor's in "
                "either order, reads no withdrawn link's line and no one's, and prints the pools "
                "apart only where a contributor's line counts",
       needs=("review", "probe_alignment", "bench_ledger"))
def _bench_hand_beats_link(RV, PA, BL):
    """The shared bench (approved 17 November 2026) merges a contributor's
    answers into review/checked.jsonl as "by": "link:<id>", after the owner
    approves them. Every reader took the LAST line of an item until then
    (review.judged's lists, --report, the tag gates, probe_alignment
    read_bench), so a contributor's line merged after the owner's would have
    replaced hers without a word. Held, on a ledger written here in the file's
    order and again reversed: review.judged() ends each item on the owner's
    line where she has one, keeps a contributor's alone, and leaves out a
    withdrawn link's and a line no one's (bench_ledger.py); read_bench gives
    the owner's mark where both timed a proceeding, a contributor's as theirs
    (who "link", from "checked.jsonl, contributors"), none of a withdrawn link
    or of no one, the contributors' confirmations apart, and --hand-only's
    reading leaves theirs out; --report and the tag gate count the owner's
    verdict and say how many counted are contributors'; and a ledger of the
    owner's lines alone prints no word of contributors."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-bench-"))
    saved = (RV.OUT, RV.LEDGER)
    try:
        for order, lines in (("in the file's order", _MIXED), ("reversed", _MIXED[::-1])):
            led = tmp / order.replace(" ", "-") / "checked.jsonl"
            _ledger(led, lines)
            RV.OUT, RV.LEDGER = led.parent, led
            seen = RV.judged()
            last = {k: v[-1] for k, v in seen.items()}
            v1, v2 = ("timestamp", "V1|HB1|hearing"), ("timestamp", "V2|HB1|hearing")
            assert last[v1]["by"] == _HAND and last[v1]["fields"]["observed_start"] == "0:03:20", (
                f"{order}: the item both judged ends on {last[v1]}, not the owner's line")
            assert last[v2]["by"] == _ANN, f"{order}: a contributor's line alone was lost"
            assert not [k for k in seen if k[1].startswith(("V3|", "V4|"))], (
                f"{order}: a withdrawn link's line or a line no one's was read: {sorted(seen)}")
            assert last[("topic", "topic|2023-2024|HB267")]["by"] == _HAND, order
            marks, confirmed, split = PA.read_bench(led, pools=True)
            got = {(m["video"], m["obs"], m["who"], m["src"]) for m in marks}
            assert got == {("V1", 200, "hand", "checked.jsonl"),
                           ("V2", 400, "link", "checked.jsonl" + PA.BENCH_THEIRS)}, (order, got)
            assert confirmed == 1 and split == {"hand": 0, "link": 1}, (order, confirmed, split)
            mine, _c = PA.read_bench(led, hand_only=True)
            assert [(m["video"], m["obs"]) for m in mine] == [("V1", 200)], (order, mine)
            out = io.StringIO()
            with redirect_stdout(out):
                RV.report()
            said = out.getvalue()
            assert "yours 3, contributors 3" in said and "(contributors 2)" in said, said
            assert "1 no" not in said.split("Tags (")[0], f"{order}: the tag's count read theirs: {said}"
            assert "title 2/2" in said and "contributors' answers among them: 1" in said, said
        # The owner's lines alone: not a word of contributors, as before the shared bench.
        led = tmp / "hers" / "checked.jsonl"
        _ledger(led, [x for x in _MIXED if x.get("by") == _HAND and x["kind"] != "withdraw"])
        RV.OUT, RV.LEDGER = led.parent, led
        out = io.StringIO()
        with redirect_stdout(out):
            RV.report()
        assert "contributor" not in out.getvalue(), out.getvalue()
        assert BL.who({"by": "hand"}) == "hand" and BL.who({}) == "hand" and \
            BL.who({"by": "link:ab12"}) == "link" and BL.who({"by": "link:"}) is None and \
            BL.who({"by": "agent"}) is None and BL.who({"by": "link:AB 12"}) is None
    finally:
        RV.OUT, RV.LEDGER = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("on a ledger in the file's order and reversed: the owner's line counts where both "
                  "judged, a contributor's alone counts as theirs, a withdrawn link and a line no "
                  "one's are read by no reader (judged, read_bench, --report, the tag gate); the "
                  "pools printed apart, and not a word of them on the owner's lines alone")
