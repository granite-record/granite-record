#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.20
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
This module uses pf_core, pf_shared (_tap_failures, node's TAP read as the
follow tests' check reads it) and itself, and no other area's module.
"""

import io
import json
import re
import shutil
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import _paths

from pf_core import _in_suite, _run, _source, check
from pf_shared import _tap_failures


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


# ---- a pack -----------------------------------------------------------------------

def _pack_fixture():
    """(pools, ledger, info): three pools, a ledger and the bills' words, small, with
    every case bench_pack must tell apart: judged by the owner, by a contributor,
    by a withdrawn link; packed before; Miscellaneous; a tag's pair; a timing
    before 2025; a calibration item and a line that is no calibration item."""
    def timing(i, year, end=True):
        return {"key": f"V{i}|HB{i}|public hearing", "bill": f"HB{i}", "year": year, "video_id": f"VID{i:08d}",
                "committee": "Election Law", "date": f"{year}-02-03", "proceeding": "public hearing",
                "title": "", "start": 600.0 + i, "end": (900.0 + i) if end else None, "state": "stated"}
    timings = [timing(i, "2026") for i in range(1, 8)] + [timing(i, "2025") for i in range(10, 14)] + \
        [timing(i, "2024", end=False) for i in range(20, 23)]
    timings.append({**timing(30, "2026"), "key": "V30|HB30|floor debate", "proceeding": "floor debate"})

    def topic(i, term, t="Education - General"):
        return {"key": f"topic|{term}|HB{i}", "kind": "topic", "term": term, "bill": f"HB{i}",
                "title": f"relative to {i}.", "committee": "Education", "topic": t, "margin": 0.9,
                "why": ["CMTE:Education", "school"]}
    topics = [topic(i, "2023-2024") for i in range(100, 106)] + [topic(i, "2021-2022") for i in range(110, 113)] + \
        [topic(120, "2023-2024", "Miscellaneous")]

    def tag(i, tid, sample, order):
        return {"kind": "tag", "tag": tid, "order": order, "tag_name": tid.title(), "definition": "Bills about it.",
                "hard": False, "term": "2025-2026", "bill": f"SB{i}", "title": f"relative to {tid}.",
                "topic": "Health", "analysis": "" if i % 2 else "This bill does a thing.", "chapters": ["126-A"],
                "tier": "T", "why": "T:" + tid, "sample": sample, "key": f"tag|{tid}|{sample}|2025-2026/SB{i}"}
    tags = [tag(i, "medicaid", s, 0) for i, s in ((1, "title"), (2, "other"), (3, "miss"), (4, "title"))] + \
        [tag(9, "housing", "title", 1),
         {"kind": "tag", "tag": "housing", "order": 1, "sample": "pair", "key": "tag|housing|pair",
          "tag_name": "Housing", "a": {}, "b": {}},
         {"kind": "tag", "tag": "medicaid", "order": 0, "sample": "pair", "key": "tag|medicaid|pair",
          "tag_name": "Medicaid", "a": {}, "b": {}}]
    hand, theirs = "hand", "link:ab12"
    ledger = [
        {"kind": "timestamp", "key": "V1|HB1|public hearing", "verdict": "correct", "by": hand,
         "shown": timings[0]},                                                  # judged; calibration (yes)
        {"kind": "timestamp", "key": "V2|HB2|public hearing", "verdict": "wrong", "by": hand,
         "shown": {**timings[1], "start": None}},                               # judged; graded on the schedule
        {"kind": "topic", "key": "topic|2023-2024|HB100", "verdict": "wrong", "by": hand,
         "shown": topics[0]},                                                   # judged; calibration (no)
        {"kind": "topic", "key": "topic|2023-2024|HB101", "verdict": "correct", "by": theirs,
         "shown": topics[1]},                                                   # judged by a contributor
        {"kind": "topic", "key": "topic|2023-2024|HB102", "verdict": "correct", "by": "link:gone12",
         "shown": topics[2]},                                                   # a withdrawn link's: not judged
        {"kind": "withdraw", "by": hand, "link": "gone12"},
        {"kind": "tag", "key": tags[0]["key"], "verdict": "partly", "by": hand, "shown": tags[0]},  # calibration (yes)
        {"kind": "tag", "key": "tag|medicaid|pair", "verdict": "yes", "by": hand, "shown": tags[-1]},
        {"kind": "timestamp", "key": "V11|HB11|public hearing", "verdict": "wrong", "by": hand,
         "fields": {"observed_start": "0:10:00"}, "shown": timings[8]},         # judged since it was packed
    ]

    class Info:
        def title(self, term, bill):
            return f"the title of {bill} ({term})"

        def analysis(self, term, bill):
            return f"The analysis of {bill}."

        def options(self):
            return ["Education - General", "Employment", "Miscellaneous"]
    return {"timestamp": timings, "topic": topics, "tag": tags}, ledger, Info()


@check("build", "a pack for the shared bench: seeded groups that leave out everything judged or packed "
                "before, timings split as the ledger keeps them, topics placed and tags asked blind, the "
                "owner's own judgments as calibration, and SQL the bench's schema loads and serves",
       needs=("bench_pack", "bench_ledger", "review"))
def _bench_pack(BP, BL, RV):
    """src/checks/bench_pack.py (step 5 of the shared bench, approved 17 November 2026), on a
    fixture of three pools, a ledger and the bills' words. Held: no item is a key the ledger
    holds -- the owner's, a contributor's -- nor one an earlier pack holds, but a withdrawn
    link's key is asked again; a timing before 2025 goes as "older" and after as
    "timestamp", a year a group, newest first, at most 50; a floor debate is asked as "taken
    up"; no topic is Miscellaneous, a term a group; a tag's pair is never asked, and a tag's
    card says nothing of how the rule attached it; the same seed draws the same pack and
    another seed another; calibration is every item of hers a card can show (not one graded
    on the schedule, not a pair), with which way she went; a packed key judged on the laptop
    since is marked elsewhere; how far along counts each whole pool; the keys line reads
    back; a statement D1 would refuse is refused here; and the SQL, loaded into the bench's
    own schema in node (tests/bench/apply_pack.js), serves every queue and keeps an answer."""
    import subprocess
    pools, ledger, info = _pack_fixture()
    packed = {"timestamp\tV11|HB11|public hearing", "timestamp\tV12|HB12|public hearing"}
    pack = BP.draw(pools, ledger, info, packed, seed=7, groups=3, per={"timing": 4}, as_of="2026-11-20T10:00:00Z")
    keys = [r["key"] for r in pack["items"]]
    judged = {d["key"] for d in BL.judgments(ledger)}
    assert not set(keys) & judged, f"a key the ledger holds was packed: {sorted(set(keys) & judged)}"
    assert "topic|2023-2024|HB102" in keys, "a withdrawn link's key was not asked again"
    assert not {k.split(chr(9))[1] for k in packed} & set(keys), "a key an earlier pack holds was packed"
    by = {r["key"]: r for r in pack["items"]}
    kinds = {r["kind"] for r in pack["items"] if r["queue"] == "timing"}
    assert kinds == {"older", "timestamp"} and all(
        r["kind"] == ("older" if r["shown"]["date"] < "2025" else "timestamp")
        for r in pack["items"] if r["queue"] == "timing"), f"a timing's kind is not the ledger's: {kinds}"
    groups = [(g["queue"], g["label"]) for g in pack["groups"]]
    assert groups == [("timing", "2026 recordings"), ("timing", "2025 recordings"), ("timing", "2024 recordings"),
                      ("topic", "Bills of 2023-2024"), ("topic", "Bills of 2021-2022"), ("tag", "Medicaid"),
                      ("tag", "Housing")], groups
    assert sum(1 for r in pack["items"] if r["grp"] == "timing|2026") == 4, "a group over its size"
    floor = BP.moment_card(pools["timestamp"][-1], "t")
    assert floor["steps"][0]["q"] == "Is HB 30 taken up at {t}?" and floor["head"] == "HB 30 · floor debate", floor
    one = by["V3|HB3|public hearing"]["card"] if "V3|HB3|public hearing" in by else \
        next(r["card"] for r in pack["items"] if r["queue"] == "timing" and "floor" not in r["key"])
    assert one["type"] == "moment" and one["words"] == {"yes": "correct", "no": "wrong", "unsure": "unsure"} and \
        one["player"]["host"] == "youtube" and [s["field"] for s in one["steps"]] == ["start", "end"] and \
        one["title"].startswith("the title of HB"), one
    assert not [r for r in pack["items"] if r["queue"] == "topic" and r["card"]["claim"] == "Miscellaneous"]
    assert all(r["card"]["better"]["field"] == "better_topic" for r in pack["items"] if r["queue"] == "topic")
    tags = [r for r in pack["items"] if r["queue"] == "tag"]
    assert tags and not [r for r in tags if r["key"].endswith("|pair")], "a tag's pair was asked"
    for r in tags:
        words = json.dumps(r["card"]).lower()
        assert not re.search(r'"(sample|why|tier|attached)"|\b(title tier|the rule|attached|missed)\b', words), (
            "a tag's card says how the rule attached it: " + words[:200])
        assert r["card"]["words"] == {"yes": "yes", "no": "no", "unsure": "unsure"}
    no_analysis = [r["card"] for r in tags if not r["shown"]["analysis"]]
    assert no_analysis and all(c["label"] == "The laws it amends" and c["body"] == "RSA 126-A" for c in no_analysis)
    again = BP.draw(pools, ledger, info, packed, seed=7, groups=3, per={"timing": 4}, as_of="2026-11-20T10:00:00Z")
    assert again == pack, "the same seed drew another pack"
    other = BP.draw(pools, ledger, info, packed, seed=8, groups=3, per={"timing": 4}, as_of="2026-11-20T10:00:00Z")
    assert [r["key"] for r in other["items"]] != keys, "another seed drew the same pack"
    cal = {(c["kind"], c["key"]): c["hers"] for c in pack["calib"]}
    assert cal == {("timestamp", "V1|HB1|public hearing"): "yes", ("topic", "topic|2023-2024|HB100"): "no",
                   ("tag", pools["tag"][0]["key"]): "yes", ("timestamp", "V11|HB11|public hearing"): "no"}, cal
    assert pack["elsewhere"] == [("timestamp", "V11|HB11|public hearing")], pack["elsewhere"]
    assert [(r["queue"], r["pool"], r["judged"]) for r in pack["queues"]] == [
        ("timing", 15, 3), ("topic", 10, 2), ("tag", 7, 2)], pack["queues"]
    assert pack["queues"][1]["options"] == info.options() and pack["queues"][0]["options"] is None

    # A REFRESH THAT COMES BACK EMPTY KEEPS THE POOL. The owner's tag pool is drawn from a
    # draft registry (review.py --tags), and review.pool_for deletes a cache an empty draw
    # leaves; a refresh without the draft would have thrown her pool away.
    tmp = Path(tempfile.mkdtemp(prefix="gr-pack-"))
    saved = (RV.OUT, RV.KINDS["tag"]["sample"])
    try:
        RV.OUT = tmp / "review"
        RV.OUT.mkdir()
        cache = RV.OUT / ".pool-tag.json"
        cache.write_text(json.dumps([{"key": "kept"}]), encoding="utf-8")
        RV.KINDS["tag"]["sample"] = lambda: []
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            got = BP.read_pool("tag", refresh=True)
        assert got == [{"key": "kept"}] and cache.is_file(), "an empty refresh threw the cached pool away"
        RV.KINDS["tag"]["sample"] = lambda: [{"key": "new"}]
        assert BP.read_pool("tag", refresh=True) == [{"key": "new"}] and \
            json.loads(cache.read_text(encoding="utf-8")) == [{"key": "new"}], "a refresh did not keep its draw"
        assert BP.read_pool("tag") == [{"key": "new"}], "the cache is not what a pack reads"
    finally:
        RV.OUT, RV.KINDS["tag"]["sample"] = saved
        shutil.rmtree(tmp, ignore_errors=True)

    tmp = Path(tempfile.mkdtemp(prefix="gr-pack-"))
    try:
        path = tmp / "2026-11-20.sql"
        sql = BP.to_sql(pack, path.stem, "graniterecord-bench-preview", path, 7, "a fixture")
        path.write_text(sql, encoding="utf-8")
        assert BP.packed_keys(tmp) == set(pack["keys"]), "the keys line does not read back"
        assert "npx wrangler d1 execute graniterecord-bench-preview --remote --file" in sql
        big = {**pack, "items": [{**pack["items"][0], "card": {"body": "x" * 95_000}}], "calib": [], "elsewhere": []}
        try:
            BP.to_sql(big, "x", "db", path, 7, "")
        except SystemExit as e:
            assert "D1 refuses" in str(e)
        else:
            raise AssertionError("a statement over D1's limit was written")
        node = shutil.which("node") or shutil.which("node.exe")
        if not node:
            return "skip", "node is not on PATH: the pack was drawn and written, and not loaded"
        r = _run([node, "--disable-warning=ExperimentalWarning", "tests/bench/apply_pack.js", str(path)],
                 capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
        got = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert got["items"] == len(pack["items"]) and got["groups"] == len(pack["groups"]) and \
        got["calib"] == len(pack["calib"]), got
    assert got["given"] == {"timing": ["timing", "timing"], "topic": ["topic", "topic"], "tag": ["tag", "tag"]} and \
        got["owner"] == 2 and got["kept"] and got["kept"]["ok"], got
    return "ok", (f"{len(pack['items'])} items in {len(pack['groups'])} groups drawn from a fixture, nothing "
                  f"judged or packed before, {len(pack['calib'])} calibration items, one marked elsewhere; the "
                  "same seed the same pack; the SQL loaded into the bench's schema and served every queue")


def _grow_fixture():
    """_pack_fixture's pools with a third term of topics and two more tags, so that a second
    pack has something left to draw after the first."""
    pools, ledger, info = _pack_fixture()
    topic = pools["topic"][0]
    pools["topic"] += [{**topic, "key": f"topic|2019-2020|HB{i}", "term": "2019-2020", "bill": f"HB{i}",
                        "title": f"relative to {i}."} for i in range(130, 133)]
    tag = pools["tag"][0]
    for tid, order, bills in (("veterans", 2, (20, 21, 22)), ("water", 3, (30, 31))):
        for i, sample in zip(bills, ("title", "other", "miss")):
            pools["tag"].append({**tag, "tag": tid, "order": order, "tag_name": tid.title(), "bill": f"SB{i}",
                                 "sample": sample, "key": f"tag|{tid}|{sample}|2025-2026/SB{i}"})
    return pools, ledger, info


@check("build", "a later pack follows the earlier ones: its items and groups numbered after every earlier "
                "pack for its database and served after them, group by group; --queues and --groups-of draw "
                "only what they name; --pools and --ledger draw with nothing read or written in review/",
       needs=("bench_pack", "bench_ledger", "review"))
def _bench_pack_grows(BP, BL, RV):
    """PACKS THAT CAN GROW (the owner, 23 November 2026: "add more entries for the tag and topics
    on the bench"). The bench serves an open item by its order (store.js claimOne, ORDER BY ord)
    and every pack numbered its own from 0, so a second pack's items came between the first's.
    Held, on draw(): the defaults are today's (every queue, --groups each, numbered from 0); a
    base moves every item and group by it and no calibration item; a group continued in a later
    pack is numbered after it; --queues gives each queue drawn what a pack of all three gives it
    and the others nothing, calibration included; --groups-of all draws every group of one
    queue; a group too big for a pack's numbering is refused; a pack's keys over D1's limit on
    one line written over as many "-- keys:" lines as they need, each under it, and pack_files
    reading every one back past the header's first twelve lines. And on main(), run twice in a tree
    with no review/: the second pack numbered from PACK_BASE because the folder holds one before
    it, both loaded into the bench's schema in node (tests/bench/apply_pack.js) and served pack by
    pack and group by group; a queue not drawn has no row in the pack; --pools and --ledger read
    there, --refresh writes the pool drawn there alone, nothing reaches review/, and a --queues,
    --groups-of or --ledger the pack cannot use is refused."""
    import contextlib
    import os
    pools, ledger, info = _grow_fixture()
    at = "2026-11-23T10:00:00Z"
    full = BP.draw(pools, ledger, info, (), seed=7, as_of=at)
    assert BP.draw(pools, ledger, info, (), seed=7, as_of=at, queues=list(BP.ORDER), groups_of={}, base=0) == full
    assert [(g["queue"], g["ord"]) for g in full["groups"]] == [
        ("timing", 0), ("timing", 1), ("topic", 0), ("topic", 1), ("tag", 0), ("tag", 1)], full["groups"]
    assert min(r["ord"] for r in full["items"]) == 0 and max(r["ord"] for r in full["items"]) < BP.GROUP_SPAN * 2
    later = BP.draw(pools, ledger, info, (), seed=7, as_of=at, base=2 * BP.PACK_BASE)
    assert [r["ord"] - 2 * BP.PACK_BASE for r in later["items"]] == [r["ord"] for r in full["items"]] and \
        [g["ord"] - 2 * BP.PACK_BASE for g in later["groups"]] == [g["ord"] for g in full["groups"]] and \
        later["calib"] == full["calib"] and full["calib"], "a base did not move items and groups alone"
    half = BP.draw(pools, ledger, info, (), seed=7, as_of=at, groups=1, per={"tag": 2})
    rest = BP.draw(pools, ledger, info, set(half["keys"]), seed=7, as_of=at, groups=1, base=BP.PACK_BASE)
    cont = [r for r in rest["items"] if r["grp"] == "tag|medicaid"]
    assert len(cont) == 1 and cont[0]["ord"] >= BP.PACK_BASE > max(r["ord"] for r in half["items"]), cont
    some = BP.draw(pools, ledger, info, (), seed=7, as_of=at, queues=["topic", "tag"])
    assert some["queues"] == [r for r in full["queues"] if r["queue"] != "timing"] and \
        some["groups"] == [g for g in full["groups"] if g["queue"] != "timing"] and \
        some["items"] == [r for r in full["items"] if r["queue"] != "timing"] and \
        some["calib"] == [c for c in full["calib"] if c["queue"] != "timing"] and \
        some["keys"] == [k for k in full["keys"] if not k.startswith(("timestamp\t", "older\t"))], (
            "--queues changed what the queues drawn are given, or drew a queue it does not name")
    every = BP.draw(pools, ledger, info, (), seed=7, as_of=at, groups=1, groups_of={"tag": None})
    assert [(g["queue"], g["label"]) for g in every["groups"]] == [
        ("timing", "2026 recordings"), ("topic", "Bills of 2023-2024"), ("tag", "Medicaid"), ("tag", "Housing"),
        ("tag", "Veterans"), ("tag", "Water")], every["groups"]
    big = {"tag": [{**pools["tag"][1], "key": f"tag|medicaid|other|2025-2026/SB{1000 + i}"}
                   for i in range(BP.GROUP_SPAN + 1)]}
    try:
        BP.draw(big, [], info, (), seed=7, per={"tag": BP.GROUP_SPAN + 1})
    except SystemExit as e:
        assert "do not fit" in str(e), e
    else:
        raise AssertionError("a group bigger than a pack's numbering was numbered into the next")
    # A PACK TOO BIG FOR ONE KEYS LINE (23 November 2026): on one line, a draw of every tag's keys
    # was over D1's limit on a line, and the pack was refused. They take as many lines as they
    # need now, each under it, and pack_files reads every one back, however far down they reach.
    assert BP.keys_lines([]) == ["-- keys: []"], BP.keys_lines([])
    five = BP.keys_lines(["aaaa", "bbbb", "cccc", "dddd", "eeee"], most=25)     # lines of 25 exactly, and one less
    assert five == ['-- keys: ["aaaa", "bbbb"]', '-- keys: ["cccc", "dddd"]', '-- keys: ["eeee"]'], five
    over = BP.keys_lines(["aaaa", "bbbbb"], most=25)                           # together they would be 26
    assert over == ['-- keys: ["aaaa"]', '-- keys: ["bbbbb"]'], over
    many = [f"tag\ttag|{'x' * 40}|title|2025-2026/SB{i}" for i in range(20_000)]
    huge = {**full, "keys": many, "queues": [], "groups": [], "items": [], "calib": [], "elsewhere": []}
    big = Path(tempfile.mkdtemp(prefix="gr-bigpack-"))
    try:
        p = big / "2026-11-23.sql"
        try:
            p.write_text(BP.to_sql(huge, p.stem, "graniterecord-bench-preview", p, 7, "a fixture"), encoding="utf-8",
                         newline="\n")
        except SystemExit as e:
            raise AssertionError(f"a pack of {len(many):,} keys was refused: {str(e)[:160]}")
        keyed = [x for x in p.read_text(encoding="utf-8").splitlines() if x.startswith("-- keys: ")]
        read = BP.pack_files(big)
    finally:
        shutil.rmtree(big, ignore_errors=True)
    assert len(keyed) > 12 and all(len(x.encode("utf-8")) <= BP.STATEMENT_MOST for x in keyed), (
        len(keyed), max(len(x) for x in keyed))
    assert len(read) == 1 and read[0][1] == many, (
        f"a pack's keys over {len(keyed)} lines read back as {len(read[0][1]) if read else 0:,} of {len(many):,}")

    node = shutil.which("node") or shutil.which("node.exe")
    tmp = Path(tempfile.mkdtemp(prefix="gr-grow-"))
    here = os.getcwd()
    saved = (BP.Info, sys.argv[:], {k: RV.KINDS[k]["sample"] for k in ("timestamp", "topic", "tag")})
    try:
        (tmp / "pools").mkdir()
        for kind, items in pools.items():
            (tmp / "pools" / f".pool-{kind}.json").write_text(json.dumps(items), encoding="utf-8")
        _ledger(tmp / "copy" / "checked.jsonl", ledger)
        kept = {p.as_posix(): p.read_bytes() for p in tmp.rglob("*") if p.is_file()}
        BP.Info = lambda root=".": info
        os.chdir(tmp)

        def run(*args):
            sys.argv = ["bench_pack.py", "--preview", "--seed", "7", "--pools", "pools", "--ledger",
                        "copy/checked.jsonl", "--out", "packs", *args]
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = BP.main()
                except SystemExit as e:
                    code = str(e)
            return code, out.getvalue()

        code, said = run("--groups", "1")
        assert code == 0 and "the first pack in packs" in said, (code, said)
        (p1, _k1), = BP.pack_files("packs")
        code, said = run("--queues", "tag,topic", "--groups-of", "tag=all")
        assert code == 0 and "served after the items of the 1 earlier pack(s)" in said, (code, said)
        p2 = next(p for p, _k in BP.pack_files("packs") if p != p1)
        # THE COPY WRANGLER LOADS (24 November 2026): D1's import counted a pack's leading comments
        # as part of its first statement, and refused a pack of every tag (SQLITE_TOOBIG). Beside
        # each pack, its statements alone; the load command names that copy; and a copy, having no
        # keys, is never counted as a pack.
        for p in (p1, p2):
            lp = BP.load_path(p)
            body = lp.read_text(encoding="utf-8").splitlines()
            want = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip() and not x.lstrip().startswith("--")]
            assert body and body == want and not any(x.lstrip().startswith("--") for x in body), (
                f"{lp.name} is not the pack's statements alone")
            assert all(len(x.encode("utf-8")) <= BP.STATEMENT_MOST for x in body), f"{lp.name} has a statement over D1's limit"
        assert sorted(p.name for p, _k in BP.pack_files("packs")) == sorted([p1.name, p2.name]), (
            f"a load copy was counted as a pack: {[p.name for p, _k in BP.pack_files('packs')]}")
        assert f"--file {BP.load_path(p2).as_posix()} --yes" in said, f"the load command names the pack, not its copy: {said[-240:]}"
        sql2 = p2.read_text(encoding="utf-8")
        assert "VALUES ('timing'" not in sql2 and "VALUES ('topic'" in sql2 and "'timestamp', 'V" not in sql2, (
            "a queue --queues does not name was written into the pack")
        assert not (tmp / "review").exists(), "a pack drawn with --pools and --ledger wrote in review/"
        assert all(Path(p).read_bytes() == b for p, b in kept.items()), "the pools or the ledger's copy changed"
        for args, words in ((("--queues", "nope"), "--queues"), (("--groups-of", "tag=0"), "--groups-of"),
                            (("--queues", "tag", "--groups-of", "topic=2"), "not drawn"),
                            (("--ledger", "nowhere.jsonl"), "no such file")):
            code, _said = run(*args)
            assert isinstance(code, str) and words in code, (args, code)
        for k, items in pools.items():
            RV.KINDS[k]["sample"] = (lambda got: lambda: got)(items)
        code, said = run("--refresh", "--pools", "fresh", "--queues", "tag", "--out", "other")
        assert code == 0 and sorted(p.name for p in (tmp / "fresh").iterdir()) == [".pool-tag.json"] and \
            not (tmp / "review").exists(), "--refresh wrote a pool not drawn, or wrote in review/"
        if not node:
            return "skip", "node is not on PATH: the two packs were drawn and written, and not served"
        r = _run([node, "--disable-warning=ExperimentalWarning", str(_paths.ROOT / "tests/bench/apply_pack.js"),
                  str(p1), str(p2)], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
        got = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        os.chdir(here)
        BP.Info, sys.argv = saved[0], saved[1]
        for k, fn in saved[2].items():
            RV.KINDS[k]["sample"] = fn
        shutil.rmtree(tmp, ignore_errors=True)
    served = got["served"]
    want = {"timing": [p1.stem] * 6, "topic": [p1.stem] * 4 + [p2.stem] * 6, "tag": [p1.stem] * 3 + [p2.stem] * 6}
    assert {q: [p for p, _g in v] for q, v in served.items()} == want, served
    for q, v in served.items():
        runs = [g for i, (_p, g) in enumerate(v) if i == 0 or v[i - 1][1] != g]
        assert len(runs) == len(set(runs)), f"{q}: a group's items were not served together: {runs}"
    assert [x[0] for x in got["queues"]] == ["timing", "topic", "tag"], got["queues"]
    return "ok", (f"draw()'s defaults as before, a base moving items and groups alone, --queues and --groups-of "
                  f"drawing only what they name; {len(many):,} keys over {len(keyed)} lines, each under "
                  f"{BP.STATEMENT_MOST:,} bytes, read back whole; two packs from main() in a tree with no "
                  f"review/, the second numbered from {BP.PACK_BASE:,} and served after the first, group by group "
                  f"({sum(len(v) for v in served.values())} items); --refresh wrote the one pool drawn into --pools")


# ---- the owner's list: her Your input tab ----------------------------------------------

def _asks_fixture():
    """A list in its format (format 1): five sections, entries in an order that is not the
    sections', one with three links, one with a single answer, a tab and a CRLF in `what`, and a
    withdrawn key."""
    return {"format": 1, "updated": "2026-11-23T18:00:00Z",
            "sections": [{"id": "release", "label": "In the update waiting for your word"},
                         {"id": "design", "label": "Designs waiting for your choice"},
                         {"id": "decision", "label": "Decisions"},
                         {"id": "yours", "label": "Steps only you can take"},
                         {"id": "notes", "label": "Anything else"}],
            "asks": [
                {"key": "votes-layout", "section": "design", "title": "The votes search: which layout?",
                 "what": "Two layouts.\r\n\r\nA keeps the filters on the left;\tB puts them on top.",
                 "where": [{"label": "The two layouts", "url": "https://claude.ai/artifact/AAAAAAAAAAAAAAAAAAAAAA"}],
                 "question": "Go with layout A?", "answers": {"yes": "Go with A", "no": "Something else",
                                                              "unsure": "Let’s discuss"},
                 "recommended": "yes", "added": "2026-11-22"},
                {"key": "nav-section-rows", "section": "release",
                 "title": "Navigation: each section's pages in a second row",
                 "what": "Each section's pages now sit in a second row.\n\nOn a phone the row scrolls.",
                 "where": [{"label": "The home page on the preview", "url": "https://dry-run.graniterecord.pages.dev/"},
                           {"label": "A bill on the preview",
                            "url": "https://dry-run.graniterecord.pages.dev/bill/2026/hb1#votes"},
                           {"label": "The site as it is", "url": "https://graniterecord.org/"}],
                 "question": "Does the new navigation read right on a computer and on a phone?",
                 "answers": {"yes": "Looks right", "no": "Needs changes", "unsure": "Let’s discuss"},
                 "recommended": "yes", "added": "2026-11-23"},
                {"key": "map-dots", "section": "release", "title": "Map dots", "question": "Do the dots read right?",
                 "answers": {"yes": "Looks right", "no": "Needs changes"}, "recommended": None, "added": "2026-11-23"},
                {"key": "run-pack", "section": "yours", "title": "Load the list on the preview",
                 "what": "At the cmd prompt:\npython3 src/checks/bench_pack.py --asks private/asks/asks.json --only-asks",
                 "question": "Done?", "answers": {"yes": "Done", "no": "Not yet"}, "added": "2026-11-23"},
                {"key": "anything-else", "section": "notes", "title": "Anything else",
                 "question": "Anything the list has missed?", "answers": {"yes": "Save the note"}, "added": "2026-11-23"}],
            "withdrawn": ["an-old-key"]}


_ASK_E1 = "entry 1 (votes-layout)"


def _ask_link(url, label="A link"):
    return lambda d: d["asks"][0].update(where=[{"label": label, "url": url}])


# Each rule of the list's format broken once: (what is broken, how, where the refusal must say it is).
_ASK_BROKEN = [
    ("its format", lambda d: d.update(format=2), "field 'format'"),
    ("a field the format has not", lambda d: d.update(extra=1), "field 'extra'"),
    ("its moment", lambda d: d.update(updated="yesterday"), "field 'updated'"),
    ("its moment ending in a line break", lambda d: d.update(updated="2026-11-23T18:00:00Z\n"), "field 'updated'"),
    ("no sections", lambda d: d.update(sections=[]), "field 'sections'"),
    ("a section's id twice", lambda d: d["sections"].append({"id": "notes", "label": "Again"}), "section 6, field 'id'"),
    ("a section's id ending in a line break", lambda d: d["sections"][0].update(id="release\n"), "section 1, field 'id'"),
    ("a section's label as markup", lambda d: d["sections"][0].update(label="<b>Release</b>"), "section 1, field 'label'"),
    ("a key", lambda d: d["asks"][0].update(key="Votes_Layout"), "entry 1 (Votes_Layout), field 'key'"),
    ("a key twice", lambda d: d["asks"][1].update(key="votes-layout"), "entry 2 (votes-layout), field 'key'"),
    # The store refuses a key ending in a line break (store.js ASK_KEY.test), so the pack does.
    ("a key ending in a line break", lambda d: d["asks"][0].update(key="votes-layout\n"), "entry 1, field 'key'"),
    ("a section no entry may name", lambda d: d["asks"][0].update(section="later"), f"{_ASK_E1}, field 'section'"),
    ("a section as a list", lambda d: d["asks"][0].update(section=["design"]), f"{_ASK_E1}, field 'section'"),
    ("a section as an object", lambda d: d["asks"][0].update(section={"id": "design"}), f"{_ASK_E1}, field 'section'"),
    ("a title empty", lambda d: d["asks"][0].update(title=" "), f"{_ASK_E1}, field 'title'"),
    ("a title of 91", lambda d: d["asks"][0].update(title="x" * 91), f"{_ASK_E1}, field 'title'"),
    ("a title of HTML", lambda d: d["asks"][0].update(title="<img src=x onerror=alert(1)>"), f"{_ASK_E1}, field 'title'"),
    ("a title of two lines", lambda d: d["asks"][0].update(title="one\ntwo"), f"{_ASK_E1}, field 'title'"),
    ("what of 1,501", lambda d: d["asks"][0].update(what="x" * 1501), f"{_ASK_E1}, field 'what'"),
    ("what in bold", lambda d: d["asks"][0].update(what="It is **bold**."), f"{_ASK_E1}, field 'what'"),
    ("what with a Markdown link", lambda d: d["asks"][0].update(what="See [this](https://claude.ai/x)."),
     f"{_ASK_E1}, field 'what'"),
    ("what with a heading", lambda d: d["asks"][0].update(what="Intro\n# Heading"), f"{_ASK_E1}, field 'what'"),
    ("what with code", lambda d: d["asks"][0].update(what="Run `this`."), f"{_ASK_E1}, field 'what'"),
    ("what with an entity", lambda d: d["asks"][0].update(what="a &amp; b"), f"{_ASK_E1}, field 'what'"),
    ("what with a control character", lambda d: d["asks"][0].update(what="a\x07b"), f"{_ASK_E1}, field 'what'"),
    ("a question empty", lambda d: d["asks"][0].update(question=""), f"{_ASK_E1}, field 'question'"),
    ("a question of 201", lambda d: d["asks"][0].update(question="x" * 201), f"{_ASK_E1}, field 'question'"),
    ("seven links", lambda d: d["asks"][0].update(where=[{"label": "x", "url": "https://claude.ai/"}] * 7),
     f"{_ASK_E1}, field 'where'"),
    ("a link with no label", _ask_link("https://claude.ai/", ""), f"{_ASK_E1}, field 'where', link 1, its label"),
    ("a link's label of 61", _ask_link("https://claude.ai/", "x" * 61), f"{_ASK_E1}, field 'where', link 1, its label"),
    ("http", _ask_link("http://graniterecord.org/"), f"{_ASK_E1}, field 'where', link 1, its url"),
    ("javascript:", _ask_link("javascript:alert(1)"), f"{_ASK_E1}, field 'where', link 1, its url"),
    ("data:", _ask_link("data:text/html,x"), f"{_ASK_E1}, field 'where', link 1, its url"),
    ("another host", _ask_link("https://example.org/"), f"{_ASK_E1}, field 'where', link 1, its url"),
    ("a host ending as ours", _ask_link("https://graniterecord.org.example.org/"),
     f"{_ASK_E1}, field 'where', link 1, its url"),
    ("user:password@", _ask_link("https://user:pw@claude.ai/"), f"{_ASK_E1}, field 'where', link 1, its url"),
    ("a port", _ask_link("https://claude.ai:8443/"), f"{_ASK_E1}, field 'where', link 1, its url"),
    ("pages.dev, not a subdomain of it", _ask_link("https://graniterecord.pages.dev/"),
     f"{_ASK_E1}, field 'where', link 1, its url"),
    ("no answers", lambda d: d["asks"][0].update(answers={}), f"{_ASK_E1}, field 'answers'"),
    ("an answer the format has not", lambda d: d["asks"][0].update(answers={"partly": "Partly"}),
     f"{_ASK_E1}, field 'answers'"),
    ("an answer's words of 33", lambda d: d["asks"][0].update(answers={"yes": "x" * 33}),
     f"{_ASK_E1}, field 'answers', yes"),
    ("an answer with no words", lambda d: d["asks"][0].update(answers={"yes": ""}), f"{_ASK_E1}, field 'answers', yes"),
    ("a recommendation it does not offer", lambda d: d["asks"][2].update(recommended="unsure"),
     "entry 3 (map-dots), field 'recommended'"),
    ("a recommendation as a list", lambda d: d["asks"][0].update(recommended=["yes"]), f"{_ASK_E1}, field 'recommended'"),
    ("a recommendation as an object", lambda d: d["asks"][0].update(recommended={"yes": 1}),
     f"{_ASK_E1}, field 'recommended'"),
    ("a day in words", lambda d: d["asks"][0].update(added="23 November 2026"), f"{_ASK_E1}, field 'added'"),
    ("a day that is not", lambda d: d["asks"][0].update(added="2026-02-30"), f"{_ASK_E1}, field 'added'"),
    ("a field an entry has not", lambda d: d["asks"][0].update(recomended="yes"), f"{_ASK_E1}, field 'recomended'"),
    ("a withdrawn key that is no key", lambda d: d.update(withdrawn=["Old key"]), "field 'withdrawn', key 1"),
    ("a withdrawn key ending in a line break", lambda d: d.update(withdrawn=["an-old-key\n"]), "field 'withdrawn', key 1"),
    ("a key both withdrawn and asked", lambda d: d.update(withdrawn=["map-dots"]), "field 'withdrawn', key 1"),
    ("401 entries", lambda d: d.update(asks=[{**d["asks"][4], "key": f"entry-{i:03d}"} for i in range(401)]),
     "field 'asks'"),
]

# Addresses for the link rule's two halves: (address, whether the format takes it).
_ASK_URLS = [
    ("https://graniterecord.org", True), ("https://graniterecord.org/", True),
    ("https://graniterecord.org/bill/2026/hb1?x=1#votes", True), ("https://dry-run.graniterecord.pages.dev/", True),
    ("https://a.b-c.graniterecord.pages.dev/x", True), ("https://claude.ai/artifact/AAAAAAAAAAAAAAAAAAAAAA", True),
    ("http://graniterecord.org/", False), ("https://graniterecord.pages.dev/", False), ("https://claude.ai:443/", False),
    ("https://user:pw@claude.ai/", False), ("https://claude.ai.example.org/", False), ("https://Claude.ai/", False),
    ("https://www.graniterecord.org/", False), ("https://-x.graniterecord.pages.dev/", False),
    ("javascript:alert(1)", False), ("data:text/html,x", False), ("//claude.ai/", False), ("https://claude.ai/ x", False),
    ("https://claude.ai/\"><b>", False), ("https://claude.ai\\@example.org/", False), ("https://claude.ai/\n", False),
    (" https://claude.ai/", False), ("https://claude.ai?x", False),
]


@check("build", "the owner's list for her Your input tab: every rule of its format refused once, naming the "
                "entry and the field; the page's link rule is the pack's; and the packs that carry it load into "
                "a database made before its tables, a revised entry keeping her answers and a withdrawn one hidden",
       needs=("bench_pack",))
def _bench_asks_pack(BP):
    """THE OWNER'S LIST (the owner, 23 November 2026: "a separate category for me giving feedback
    on new features or visual changes that need my input"), bench_pack.py --asks and --only-asks,
    on a fixture of the format (S/helpers/bench-input/ASKS_FORMAT.md, format 1). Held: the list
    read, each entry's order its section's place and then the list's, its card the entry with its
    section's label and `what`'s CRLF made a line break; each rule of the format broken once and
    refused, the refusal naming the entry and the field (_ASK_BROKEN, 52 of them: a key, a
    withdrawn key, a section's id or the moment ending in a line break among them, and a list or
    an object where a section or a recommendation is named), and 400
    entries taken; the page's LINK_RULE (workers/bench/page.js) the same text as the pack's, and
    the two engines agreeing on every address of _ASK_URLS (tests/bench/apply_asks.js --rule);
    a pack of items with the list carrying its count in its header beside its keys line, the
    schema's two CREATE TABLE statements and then the entries; a pack of the list alone with no
    keys line, so no later pack of items counts it; the three loaded one after another in node
    into a database made before the list's tables, as the owner loads them, with her answers
    between them: the list served in order, a revised entry's new words with her answers kept,
    a withdrawn one hidden and asked again open, the tables made with the schema's columns, and
    every answer kept; and main() --only-asks in an empty folder, reading no pools, ledger or
    data, and refusing a broken list or no list."""
    import contextlib
    import copy
    import os
    base = _asks_fixture()
    got = BP.asks_from(copy.deepcopy(base), "asks.json")
    assert [(r["key"], r["ord"]) for r in got["rows"]] == [
        ("votes-layout", 1000), ("nav-section-rows", 1), ("map-dots", 2), ("run-pack", 3003),
        ("anything-else", 4004)], got["rows"]
    first = got["rows"][0]["card"]
    assert first == {"section": "Designs waiting for your choice", "title": "The votes search: which layout?",
                     "what": "Two layouts.\n\nA keeps the filters on the left;\tB puts them on top.",
                     "where": base["asks"][0]["where"], "question": "Go with layout A?",
                     "answers": base["asks"][0]["answers"], "recommended": "yes", "added": "2026-11-22"}, first
    assert got["withdrawn"] == ["an-old-key"] and len(got["sections"]) == 5
    bare = copy.deepcopy(base)
    for k in ("updated", "withdrawn"):
        bare.pop(k)
    assert BP.asks_from(bare)["withdrawn"] == []
    assert len(BP.asks_from({**copy.deepcopy(base), "asks": [{**base["asks"][4], "key": f"entry-{i:03d}"}
                                                              for i in range(400)]})["rows"]) == 400
    for what, how, where in _ASK_BROKEN:
        d = copy.deepcopy(base)
        how(d)
        try:
            BP.asks_from(d, "asks.json")
        except SystemExit as e:
            assert str(e).startswith(f"asks.json: {where}: "), (what, str(e))
        else:
            raise AssertionError(f"a list with {what} was taken")
    page = _source(_paths.ROOT / "workers" / "bench" / "page.js")
    m = re.search(r"export const LINK_RULE = String\.raw`([^`]*)`;", page)
    assert m and m.group(1) == BP.LINK_RULE, "the page's link rule is not the pack's: change both, in one commit"
    py = [bool(BP.LINK.fullmatch(u)) for u, _ok in _ASK_URLS]
    assert py == [ok for _u, ok in _ASK_URLS], [u for (u, ok), p in zip(_ASK_URLS, py) if ok != p]

    node = shutil.which("node") or shutil.which("node.exe")
    tmp = Path(tempfile.mkdtemp(prefix="gr-asks-"))
    here = os.getcwd()
    saved = sys.argv[:]
    try:
        revised = copy.deepcopy(base)
        revised["asks"][1]["title"] = "Navigation: a second row for each section"
        revised["asks"][2:3] = [{"key": "new-one", "section": "decision", "title": "A new question",
                                 "question": "Yes or no?", "answers": {"yes": "Yes", "no": "No"}, "added": "2026-11-24"}]
        revised["withdrawn"] = ["an-old-key", "map-dots"]
        again = copy.deepcopy(base)
        again["withdrawn"] = []
        pools, ledger, info = _grow_fixture()
        pack = BP.draw(pools, ledger, info, (), seed=7, groups=1, as_of="2026-11-23T10:00:00Z")
        p1, p2, p3 = tmp / "2026-11-23.sql", tmp / "2026-11-23-asks.sql", tmp / "2026-11-24-asks.sql"
        p1.write_text(BP.to_sql(pack, p1.stem, "graniterecord-bench-preview", p1, 7, "a fixture", got), encoding="utf-8")
        p2.write_text(BP.asks_only_sql(BP.asks_from(revised), p2.stem, "graniterecord-bench-preview", p2,
                                       "2026-11-23T19:00:00Z", "asks.json"), encoding="utf-8")
        p3.write_text(BP.asks_only_sql(BP.asks_from(again), p3.stem, "graniterecord-bench-preview", p3,
                                       "2026-11-24T19:00:00Z", "asks.json"), encoding="utf-8")
        head1 = p1.read_text(encoding="utf-8").splitlines()[:12]
        head2 = p2.read_text(encoding="utf-8").splitlines()[:12]
        assert "-- 5 asks for the owner's Your input tab, and 1 withdrawn." in head1 and \
            any(x.startswith("-- keys: ") for x in head1), head1
        assert "-- 5 asks for the owner's Your input tab, and 2 withdrawn." in head2 and \
            not any(x.startswith("-- keys: ") for x in head2), head2
        assert [p for p, _k in BP.pack_files(tmp)] == [p1], "a pack of the list alone counts as a pack of items"
        sql1 = p1.read_text(encoding="utf-8")
        assert sql1.count("CREATE TABLE IF NOT EXISTS") == 2 and \
            sql1.index("CREATE TABLE IF NOT EXISTS asks") > sql1.rindex("INSERT OR IGNORE INTO items") and \
            sql1.index("CREATE TABLE IF NOT EXISTS ask_answers") < sql1.index("INSERT INTO asks"), (
                "the list's tables are not made before its entries, after the pack's items")
        assert "-- 0 asks for the owner's Your input tab: her list is left as it is." in \
            BP.to_sql(pack, "x", "db", p1, 7, "").splitlines()[:12], "a pack without the list says nothing of it"
        cases = tmp / "cases.json"
        cases.write_text(json.dumps([u for u, _ok in _ASK_URLS]), encoding="utf-8")
        answers = tmp / "answers.json"
        answers.write_text(json.dumps([[0, "nav-section-rows", "no", "It wraps."], [0, "map-dots", "yes", ""],
                                       [1, "nav-section-rows", "yes", "Fine now."]]), encoding="utf-8")

        # main(), in a folder holding the list and nothing else: no pools, no ledger, no data.
        (tmp / "run").mkdir()
        (tmp / "run" / "list.json").write_text(json.dumps(base), encoding="utf-8")
        os.chdir(tmp / "run")

        def run(*args):
            sys.argv = ["bench_pack.py", "--preview", "--out", "packs", *args]
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = BP.main()
                except SystemExit as e:
                    code = str(e)
            return code, out.getvalue()

        code, said = run("--asks", "list.json", "--only-asks")
        made = sorted(p.name for p in (tmp / "run" / "packs").glob("*.sql") if not p.name.endswith(".load.sql"))
        assert BP.load_path(tmp / "run" / "packs" / made[0]).is_file() if made else True, "a list's pack has no load copy"
        assert code == 0 and len(made) == 1 and made[0].endswith("-asks.sql") and "5 asks" in said, (code, said, made)
        assert BP.pack_files("packs") == [] and sorted(p.name for p in (tmp / "run").iterdir()) == ["list.json", "packs"], (
            "a pack of the list alone read or wrote something but the list and its pack")
        bad = copy.deepcopy(base)
        bad["asks"][1]["where"][0]["url"] = "http://graniterecord.org/"
        (tmp / "run" / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
        for args, words in ((("--asks", "bad.json", "--only-asks"), "bad.json: entry 2 (nav-section-rows), field 'where'"),
                            (("--only-asks",), "--asks FILE"), (("--asks", "none.json", "--only-asks"), "no such file")):
            code, _said = run(*args)
            assert isinstance(code, str) and words in code, (args, code)
        assert len([p for p in (tmp / "run" / "packs").glob("*.sql") if not p.name.endswith(".load.sql")]) == 1, (
            "a refused list wrote a pack")
        assert len(list((tmp / "run" / "packs").glob("*.load.sql"))) == 1, "a refused list wrote a load copy"
        if not node:
            return "skip", "node is not on PATH: the list was read and written, and not served"
        rule = _run([node, "--disable-warning=ExperimentalWarning", str(_paths.ROOT / "tests/bench/apply_asks.js"),
                     "--rule", str(cases)], capture_output=True, text=True, timeout=120)
        assert rule.returncode == 0, (rule.stdout + rule.stderr)[-600:]
        js = json.loads(rule.stdout.strip().splitlines()[-1])
        r = _run([node, "--disable-warning=ExperimentalWarning", str(_paths.ROOT / "tests/bench/apply_asks.js"),
                  str(answers), str(p1), str(p2), str(p3)], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
        served = json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        os.chdir(here)
        sys.argv = saved
        shutil.rmtree(tmp, ignore_errors=True)
    assert js == py, [u for (u, _ok), a, b in zip(_ASK_URLS, js, py) if a != b]
    assert "asks" not in served["before"] and "ask_answers" not in served["before"], served["before"]
    s1, s2, s3 = served["steps"]
    assert [x["key"] for x in s1["list"]] == ["nav-section-rows", "map-dots", "votes-layout", "run-pack",
                                              "anything-else"] and s1["waiting"] == 3 and \
        all(x["ok"] for x in s1["said"]) and s1["list"][2]["section"] == "Designs waiting for your choice", s1
    assert [x["key"] for x in s2["list"]] == ["nav-section-rows", "votes-layout", "new-one", "run-pack",
                                              "anything-else"], s2
    nav = s2["list"][0]
    assert nav["title"] == "Navigation: a second row for each section" and nav["answer"] == "yes" and \
        nav["note"] == "Fine now.", nav
    back = next(x for x in s3["list"] if x["key"] == "map-dots")
    assert back["answer"] == "yes" and s3["list"][0]["title"] == base["asks"][1]["title"], s3
    assert served["columns"] == {t: BENCH_COLUMNS[t] for t in ("asks", "ask_answers")}, served["columns"]
    assert served["answers"] == [["nav-section-rows", "no", "It wraps."], ["map-dots", "yes", ""],
                                 ["nav-section-rows", "yes", "Fine now."]] and served["items"] == len(pack["items"]), served
    return "ok", (f"{len(_ASK_BROKEN)} broken lists refused, each naming its entry and field, and 400 entries taken; "
                  f"the page's link rule the pack's, the two agreeing on {len(_ASK_URLS)} addresses; three packs "
                  "loaded into a database made before the list's tables, in order, a revised entry keeping her "
                  "answers and a withdrawn one hidden, then asked again; --only-asks read nothing but the list")


# A claude.ai artifact's address, as a link (/artifact/<id>, /code/artifact/<uuid>) or written
# escaped in a pattern or JSON (claude\.ai\/artifact\/<id>), the host in any case.
_ARTIFACT = re.compile(r"claude\\?\.ai\\?/(?:code\\?/)?artifact\\?/([A-Za-z0-9_-]+)", re.I)


def _real_artifacts(text):
    """The ids of the claude.ai artifacts `text` names that are not made up. A made-up id is one
    character over and over (a uuid's dashes aside), which no real one is."""
    return [m.group(1) for m in _ARTIFACT.finditer(text) if len(set(m.group(1).replace("-", ""))) != 1]


@check("files", "no tracked file names one of the owner's claude.ai artifacts: her designs, and the list "
                "that links them, stay out of the public repository, and a test's artifact is made up")
def _no_artifact_links():
    """THE OWNER'S LINKS STAY HERS (23 November 2026). Her designs are claude.ai artifacts, and the
    list of what waits on her word links them (private/asks/asks.json, never in the repository).
    One of those links went into the tests of the Your input tab, copied from the list format's
    example: committed to a public repository, it would point anyone reading the tests at her
    private design, and stay in the history once pushed. Held over every tracked file (git grep,
    as it stands in the working tree): an artifact named there, as a link or escaped in a
    pattern, has a made-up id -- one character over and over, as the tests' AAAA... is. The
    failure names the file and line, never the id, since the night's log is public."""
    real = "q7Lm2Zr9TwXc4BvN8kPd1s"     # the shape of a real id, made up, and joined here at run time
    for text, n in ((f"https://claude.ai/artifact/{real}", 1), (f"https:\\/\\/claude\\.ai\\/artifact\\/{real}", 1),
                    (f"https://Claude.AI/artifact/{real}?x=1", 1),
                    ("https://claude.ai/code/artifact/" + "1b4e28ba-2fa1-11d2-883f-0016d3cca427", 1),
                    ("https://claude.ai/artifact/AAAAAAAAAAAAAAAAAAAAAA", 0),
                    ("https://claude.ai/code/artifact/" + "00000000-0000-0000-0000-000000000000", 0),
                    ("https://claude.ai/artifact/<id>", 0), ("https://claude.ai/x?y=1", 0), ("a GitHub artifact", 0)):
        assert len(_real_artifacts(text)) == n, f"the reader of an artifact's link reads {text!r} wrongly"
    try:
        r = _run(["git", "grep", "-I", "-n", "-F", "-i", "-e", "artifact"], cwd=str(_paths.ROOT),
                 capture_output=True, text=True, timeout=120)
    except OSError as e:
        return "skip", f"git would not search the tracked files ({e})"
    if r.returncode not in (0, 1):
        return "skip", "git would not search the tracked files: " + (r.stderr or "").strip()[:200]
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    bad, named = [], 0
    for ln in lines:
        where, _, text = ln.partition(":")
        num, _, text = text.partition(":")
        named += len(_ARTIFACT.findall(text))
        if _real_artifacts(text):
            bad.append(f"{where}:{num}")
    assert not bad, ("a claude.ai artifact of the owner's is named in a tracked file, and the repository is public: "
                     + ", ".join(bad[:12]) + ". Give a test a made-up id (one letter over and over, as "
                     "AAAAAAAAAAAAAAAAAAAAAA), and keep her links in private/asks/asks.json")
    return "ok", (f"{len(lines)} tracked line(s) say artifact, with {named} claude.ai artifact link(s) among them, "
                  "every one made up")


# ---- the merge ----------------------------------------------------------------------

@check("build", "the merge: a pull looks and merges nothing, notes pass compile_reports' screen, "
                "--approve appends a link's answers as link:<id> (hers as hand) once, marks them merged and "
                "never the preview's, --withdraw is one appended line, and the owner's link keeps only a hash",
       needs=("bench_pull", "bench_pack", "bench_ledger", "review"))
def _bench_pull(PL, BP, BL, RV):
    """src/checks/bench_pull.py (step 6 of the shared bench, approved 17 November 2026), run
    as the owner runs it but with the database answered in node: a pack drawn from
    _pack_fixture is loaded into the bench's schema, answers are given through the bench's
    own store (tests/bench/pull_rows.js), and bench_pull's own query pulls them -- so the
    query is held to the schema. wrangler is never run: its one function is stood in for
    and every call it is given is kept. Held: a pull writes no ledger line, prints each
    link's answers by its name and holds a note compile_reports.screen holds, without its
    words; --approve on the preview merges nothing; --approve sam appends Sam's three
    answers, by "link:sam234" and never the name, with the moment each was given, the
    item as drawn, the time marked in the ledger's words, "via" "bench" and a bench_id,
    the held note as no note, and then marks exactly those merged and raises each queue's
    judged count in one SQL file; a second --approve appends nothing; --approve me appends
    hers as "hand"; an answer taken back is never pulled; --withdraw is one line that every
    reader then honours; and --owner-link sends the database the token's SHA-256 and not
    the token, turning off any earlier link of hers."""
    import contextlib
    import hashlib
    import os
    import subprocess
    pools, ledger, info = _pack_fixture()
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not on PATH, so no answer could be given through the bench's store"
    tmp = Path(tempfile.mkdtemp(prefix="gr-pull-"))
    here, calls = os.getcwd(), []
    saved = (PL.wrangler, sys.argv[:], RV.OUT, RV.LEDGER)
    try:
        pack = BP.draw(pools, ledger, info, (), seed=7, groups=2, per={"timing": 4}, as_of="2026-11-20T10:00:00Z")
        assert pack["calib"], "the fixture's pack has no calibration item to answer"
        (tmp / "pack.sql").write_text(BP.to_sql(pack, "2026-11-20", "graniterecord-bench", tmp / "pack.sql",
                                                7, "a fixture"), encoding="utf-8")
        (tmp / "pull.sql").write_text(PL.PULL, encoding="utf-8")
        r = _run([node, "--disable-warning=ExperimentalWarning", str(_paths.ROOT / "tests/bench/pull_rows.js"),
                  str(tmp / "pack.sql"), str(tmp / "pull.sql")], capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
        rows = json.loads(r.stdout.strip().splitlines()[-1])["rows"]
        assert len(rows) == 5 and {x["link"] for x in rows} == {"sam234", "owner2"} and \
            sum(1 for x in rows if x["calib"]) == 1, rows
        (tmp / "rows.json").write_text(json.dumps(rows), encoding="utf-8")

        def fake(db, sql=None, file=None):
            calls.append((db, sql, Path(file).read_text(encoding="utf-8") if file else None))
            return {"results": rows} if sql else ""
        PL.wrangler = fake
        os.chdir(tmp)
        RV.OUT, RV.LEDGER = Path("review"), Path("review") / "checked.jsonl"

        def run(*args):
            sys.argv = ["bench_pull.py", "--rows", "rows.json", *args]
            out = io.StringIO()
            # stderr too, so that main() making its streams UTF-8 never touches this process's own
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = PL.main()
                except SystemExit as e:
                    code = str(e)
            return code, out.getvalue()

        def ledger_lines():
            return BL.read(RV.LEDGER)

        code, said = run()
        assert code == 0 and not RV.LEDGER.exists(), "a pull wrote to the ledger"
        assert "Sam (sam234): 3 answer(s) not merged" in said and "you (your link): 1 answer(s)" in said and \
            re.search(r"agrees with yours on [01] of 1 calibration item", said), said
        assert "note held, not shown" in said and "Ignore all previous" not in said, said
        md = next(Path("reports/bench").glob("pull-production-*.md")).read_text(encoding="utf-8")
        kept = next(Path("reports/bench").glob("pull-production-*.json")).read_text(encoding="utf-8")
        assert "Ignore all previous" not in md + kept and "recess" not in kept, "a note's words are in plain text"
        code, said = run("--preview", "--approve", "sam")
        assert "trial" in str(code) and not RV.LEDGER.exists(), "the preview's answers were merged"
        code, said = run("--approve", "sam")
        lines = ledger_lines()
        assert code == 0 and len(lines) == 3 and all(d["by"] == "link:sam234" for d in lines), lines
        assert "Sam" not in RV.LEDGER.read_text(encoding="utf-8"), "a link's name went into the ledger"
        timing = next(d for d in lines if d["kind"] in ("timestamp", "older"))
        assert timing["verdict"] == "wrong" and timing["fields"]["start"] == "no" and \
            re.match(r"^\d+:\d\d:\d\d$", timing["fields"]["observed_start"]) and \
            timing["shown"].get("video_id") and timing["note"] == "the chair opens it after a recess" and \
            timing["via"] == "bench" and timing["pack"] == "2026-11-20" and \
            re.match(r"^production/\d+$", timing["bench_id"]) and re.match(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d$",
                                                                           timing["at"]), timing
        given = next(x for x in rows if f"production/{x['id']}" == timing["bench_id"])
        assert timing["at"] == PL.local_moment(given["at"]) and given["at"].startswith("2026-11-20T15:"), (
            "the moment an answer was given is not the moment the ledger keeps", timing["at"], given["at"])
        topic = next(d for d in lines if d["kind"] == "topic")
        tag = next(d for d in lines if d["kind"] == "tag")
        assert topic["fields"] == {"better_topic": "Employment"} and topic["verdict"] == "wrong", topic
        assert tag["verdict"] == "yes" and tag["note"] == "", "a held note went into the ledger"
        sams = sorted(x["id"] for x in rows if x["link"] == "sam234" and not x["calib"])
        mark = calls[-1][2]
        assert calls[-1][0] == "graniterecord-bench" and \
            f"UPDATE judgments SET state = 'merged' WHERE state = 'kept' AND id IN ({', '.join(map(str, sams))});" \
            in mark and "UPDATE queues SET judged = judged + 1 WHERE queue = 'timing';" in mark, mark
        code, said = run("--approve", "sam")
        assert len(ledger_lines()) == 3 and "already" in said, "a second --approve appended again"
        code, said = run("--approve", "me")
        hers = ledger_lines()[3:]
        assert len(hers) == 1 and hers[0]["by"] == "hand" and hers[0]["kind"] == "topic", hers
        assert len(BL.judged(RV.LEDGER)) == 4
        code, said = run("--withdraw", "sam234")
        lines = ledger_lines()
        assert lines[-1]["kind"] == "withdraw" and lines[-1]["link"] == "sam234" and lines[-1]["by"] == "hand"
        assert [k for k, v in BL.judged(RV.LEDGER).items()] == [(hers[0]["kind"], hers[0]["key"])], (
            "a withdrawn link's lines are still read")
        code, said = run("--owner-link")
        token = re.search(r"/bench#([A-Za-z0-9_-]{43})", said).group(1)
        sent = calls[-1][2]
        assert hashlib.sha256(token.encode()).hexdigest() in sent and token not in sent and \
            sent.startswith("UPDATE links SET state = 'off' WHERE role = 'owner';") and \
            "https://graniterecord.org/bench#" in said, sent
        assert not list(Path("reports/bench").glob("owner-*.sql")), "the owner's link's SQL was left on disk"
    finally:
        os.chdir(here)
        PL.wrangler, sys.argv, RV.OUT, RV.LEDGER = saved[0], saved[1], saved[2], saved[3]
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("4 answers and a calibration answer given through the store on a fixture's pack and "
                  "pulled by bench_pull's own query; a pull merged nothing and held a note unread; "
                  "--approve appended Sam's 3 as link:sam234 once (not the calibration answer) and marked "
                  "them merged, never the preview's, hers as hand; a withdrawal honoured; the owner's "
                  "link sent as a hash")


@check("build", "the pull of her answers on the Your input tab: each appended once to "
                "private/asks/answers.jsonl in the list's format, printed, and only then marked pulled; "
                "nothing else written, and review/checked.jsonl never touched",
       needs=("bench_pull", "bench_pack"))
def _bench_asks_pull(PL, BP):
    """bench_pull.py --asks (23 November 2026), run as the owner runs it but with the database
    answered in node: the list of _asks_fixture loaded by a pack into a database made before its
    tables, her answers given through the store (one of them withdrawn after, one a note of two
    lines), and bench_pull's own ASKS_PULL query reading them (tests/bench/apply_asks.js
    --query), so the query is held to the schema. wrangler is never run: its one function is
    stood in for, answering ASKS_PULL with those rows, and each call it is given kept with what
    answers.jsonl held at that moment. Held, in a folder with nothing else in it: one line
    each, in the order given, with the format's fields alone -- the entry's title and the words
    of the button she chose, her note whole, the database's name; the title, the words and
    each line of the note printed; the answers marked pulled by id in one statement made only
    after the file held them all; no file written but private/asks/answers.jsonl, and no
    review/ made; a second pull of the same rows appending nothing twice and marking them, the
    preview's appending its own; --rows a look, appending and marking nothing and asking no
    database, the statement it would send printed; an id the file holds for another answer
    (the database's answers numbered again) stopping the pull with nothing written or marked;
    an answer the file does not hold after appending left unmarked; a torn last line (cut off
    inside a character) ended first, each answer after it a line that reads, all marked; a
    database that will not mark them saying so, the lines kept; a note with an emoji printed to a cp1252 console and
    marked pulled after it; nothing to pull saying that; and --asks beside --approve refused."""
    import contextlib
    import copy
    import os
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not on PATH, so no answer could be given through the bench's store"
    tmp = Path(tempfile.mkdtemp(prefix="gr-askpull-"))
    here, calls = os.getcwd(), []
    saved = (PL.wrangler, sys.argv[:])
    try:
        pack = tmp / "list.sql"
        pack.write_text(BP.asks_only_sql(BP.asks_from(copy.deepcopy(_asks_fixture())), "2026-11-23-asks",
                                         "graniterecord-bench", pack, "2026-11-23T18:00:00Z", "asks.json"),
                        encoding="utf-8")
        withdraw = tmp / "withdraw.sql"
        withdraw.write_text("UPDATE asks SET state = 'withdrawn' WHERE key = 'map-dots';\n", encoding="utf-8")
        pulled = tmp / "pulled.sql"
        pulled.write_text("UPDATE ask_answers SET pulled = 1 WHERE key = 'run-pack';\n", encoding="utf-8")
        (tmp / "answers.json").write_text(json.dumps([
            [0, "nav-section-rows", "no", "The second row wraps on my phone.\nOtherwise fine."],
            [0, "map-dots", "yes", ""], [0, "anything-else", "yes", "Ask me about the map, too."],
            [1, "votes-layout", "unsure", "Let us talk on Friday."], [1, "run-pack", "yes", "Pulled before."]]),
            encoding="utf-8")
        (tmp / "pull.sql").write_text(PL.ASKS_PULL, encoding="utf-8")
        r = _run([node, "--disable-warning=ExperimentalWarning", str(_paths.ROOT / "tests/bench/apply_asks.js"),
                  "--query", str(tmp / "pull.sql"), str(tmp / "answers.json"), str(pack), str(withdraw), str(pulled)],
                 capture_output=True, text=True, timeout=120)
        assert r.returncode == 0, (r.stdout + r.stderr)[-600:]
        rows = json.loads(r.stdout.strip().splitlines()[-1])["rows"]
        assert [x["key"] for x in rows] == ["nav-section-rows", "map-dots", "anything-else", "votes-layout"], (
            "the pull's query did not read her answers not pulled yet, and those alone", rows)
        (tmp / "run").mkdir()
        (tmp / "run" / "rows.json").write_text(json.dumps(rows), encoding="utf-8")
        out_file = tmp / "run" / "private" / "asks" / "answers.jsonl"
        fail, served = [], [rows]

        # wrangler, stood in for: ASKS_PULL answered with the rows the store kept (served[0]), and
        # every statement kept with what answers.jsonl held when it was sent.
        def fake(db, sql=None, file=None):
            held = out_file.read_bytes().decode("utf-8", "replace").splitlines() if out_file.is_file() else []
            calls.append((db, sql, file, len(held)))
            if sql == PL.ASKS_PULL:
                return {"results": copy.deepcopy(served[0])}
            if fail:
                raise RuntimeError("wrangler d1 execute failed: 7500")
            return {"results": []}
        PL.wrangler = fake
        os.chdir(tmp / "run")

        def run(*args, console=None):
            sys.argv = ["bench_pull.py", *args]
            out = console or io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                try:
                    code = PL.main()
                except SystemExit as e:
                    code = str(e)
            return code, (out.getvalue() if console is None else "")

        ids = sorted(x["id"] for x in rows)
        mark = "UPDATE ask_answers SET pulled = 1 WHERE pulled = 0 AND id IN (" + ", ".join(map(str, ids)) + ");"
        code, said = run("--asks")
        lines = [json.loads(x) for x in out_file.read_text(encoding="utf-8").splitlines()]
        assert code == 0 and [d["key"] for d in lines] == [x["key"] for x in rows], (code, said, lines)
        assert all(list(d) == ["id", "key", "title", "answer", "words", "note", "at", "db"] for d in lines), lines[0]
        first = lines[0]
        assert first["title"] == "Navigation: each section's pages in a second row" and first["words"] == "Needs changes" \
            and first["note"] == "The second row wraps on my phone.\nOtherwise fine." and \
            first["db"] == "graniterecord-bench" and first["answer"] == "no" and \
            re.match(r"^2026-11-23T18:00:\d\d\.\d{3}Z$", first["at"]), first
        assert [d["words"] for d in lines] == ["Needs changes", "Looks right", "Save the note", "Let’s discuss"], lines
        assert lines[1]["title"] == "Map dots", "an entry withdrawn since lost its title"
        for words in ("Navigation: each section's pages in a second row: Needs changes", "    Otherwise fine.",
                      "Anything else: Save the note", "    Ask me about the map, too."):
            assert words in said, (words, said)
        assert calls == [("graniterecord-bench", PL.ASKS_PULL, None, 0), ("graniterecord-bench", mark, None, 4)], calls
        made = sorted(p.relative_to(tmp / "run").as_posix() for p in (tmp / "run").rglob("*") if p.is_file())
        assert made == ["private/asks/answers.jsonl", "rows.json"], f"the pull wrote {made}"
        code, said = run("--asks")
        assert code == 0 and len(out_file.read_text(encoding="utf-8").splitlines()) == 4 and \
            "each in private/asks/answers.jsonl already" in said and calls[-1][1] == mark, (
                "a second pull appended its lines again, or did not mark them", said, calls[-1])
        code, said = run("--asks", "--preview")
        again = [json.loads(x) for x in out_file.read_text(encoding="utf-8").splitlines()]
        assert len(again) == 8 and {d["db"] for d in again[4:]} == {"graniterecord-bench-preview"}, again
        # --rows is a look: nothing appended, nothing marked, no wrangler at all, and the statement
        # the pull would send printed.
        before, n = out_file.read_bytes(), len(calls)
        code, said = run("--asks", "--rows", "rows.json")
        assert code == 0 and len(calls) == n and out_file.read_bytes() == before and "  " + mark in said and \
            "nothing appended, and nothing marked pulled" in said, (code, said, calls[n:])
        # The database's answers numbered again (made again, say): an id the file holds for another
        # answer stops the pull before anything is written, and nothing is marked pulled.
        served[0] = [{**rows[0], "key": "votes-layout", "at": "2026-11-25T09:00:00.000Z"}] + rows[1:]
        code, said = run("--asks")
        assert code == 1 and "numbered again" in said and out_file.read_bytes() == before and \
            [c[1] for c in calls[n:]] == [PL.ASKS_PULL], (code, said, calls[n:])
        # An answer whose line the file does not hold after appending is not marked pulled.
        served[0] = rows
        out_file.unlink()
        whole = PL.append_asks
        PL.append_asks = lambda got, path=None: whole(got[:-1], path)
        try:
            code, said = run("--asks")
        finally:
            PL.append_asks = whole
        short = "UPDATE ask_answers SET pulled = 1 WHERE pulled = 0 AND id IN (" + ", ".join(map(str, ids[:-1])) + ");"
        assert code == 1 and calls[-1][1] == short and f"id {ids[-1]}" in said and "NOT marked" in said, (
            code, said, calls[-1])
        # A torn last line (a pull cut off mid-line, and mid-character): ended first, so each
        # answer appended after it is a line of its own that reads, and all four are marked.
        out_file.write_bytes(out_file.read_bytes().splitlines(keepends=True)[0]
                             + b'{"id": 99, "key": "map-dots", "note": "caf\xc3')
        code, said = run("--asks")
        kept = out_file.read_bytes().decode("utf-8", "replace").splitlines()
        read = []
        for x in kept:
            try:
                read.append(json.loads(x)["id"])
            except ValueError:
                pass
        assert code == 0 and len(kept) == 5 and read == ids and calls[-1][1] == mark, (code, said, kept, calls[-1])
        fail.append(1)
        out_file.unlink()
        code, said = run("--asks")
        assert code == 1 and "NOT yet marked pulled" in said and \
            len(out_file.read_text(encoding="utf-8").splitlines()) == 4, (code, said)
        fail.clear()
        # A note with a character a cp1252 console has not (an emoji) prints, and is marked pulled
        # after it: main() writes to its console as UTF-8.
        out_file.unlink()
        served[0] = [{**rows[0], "note": "Too faint \U0001F44E on a phone"}]
        console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
        code, _said = run("--asks", console=console)
        console.flush()
        printed = console.buffer.getvalue().decode("utf-8")
        one = f"UPDATE ask_answers SET pulled = 1 WHERE pulled = 0 AND id IN ({rows[0]['id']});"
        assert code == 0 and "    Too faint \U0001F44E on a phone" in printed and calls[-1][1] == one, (
            code, printed, calls[-1])
        served[0] = []
        code, said = run("--asks")
        assert code == 0 and "No answer of yours" in said, said
        code, said = run("--asks", "--approve", "sam")
        assert isinstance(code, str) and "alone" in code, code
        assert not (tmp / "run" / "review").exists() and not (tmp / "run" / "reports").exists(), (
            "a pull of her answers wrote in review/ or reports/")
    finally:
        os.chdir(here)
        PL.wrangler, sys.argv = saved
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("4 answers given through the store and read by bench_pull's own query: each appended once to "
                  "private/asks/answers.jsonl in the format's fields, printed, and only then marked pulled in one "
                  "statement, each only once the file held it; nothing else written and no review/; a second pull "
                  "appended none twice, the preview's its own; --rows a look that wrote and marked nothing; an id "
                  "numbered again stopped the pull; a mark that failed said so and kept the lines; a note with "
                  "an emoji printed to a cp1252 console and marked after")


# ---- what keeps the bench off, unlisted, and keeping nothing ---------------------------

# The bench's routes: the page, and every endpoint under functions/api/bench/.
BENCH_PAGE = "functions/bench.js"
BENCH_API = "functions/api/bench"
# The bench's two databases, and the environment each belongs to (workers/bench/README.md).
BENCH_DBS = {"production": "graniterecord-bench", "preview": "graniterecord-bench-preview"}


def _bench_routes(root=None):
    """{route: path} of every Function of the bench."""
    root = Path(root) if root else _paths.ROOT
    out = {}
    if (root / BENCH_PAGE).is_file():
        out["/bench"] = root / BENCH_PAGE
    for p in sorted((root / BENCH_API).glob("*.js")) if (root / BENCH_API).is_dir() else []:
        out[f"/api/bench/{p.stem}"] = p
    return out


def _switch_problems(src, route):
    """What is wrong with one bench Function's start: it must refuse, with notHere(), wherever
    BENCH_DB is not bound and before it reads a request's method or awaits anything; answer
    through workers/bench/common.js alone (no Response of its own, no console); and a post
    route refuse a GET with 405 "POST only" as the night's probe expects."""
    bad = []
    body = src[src.find("export async function onRequest"):]
    if not body:
        return [f"{route} has no onRequest"]
    gate = body.find("!env.BENCH_DB")
    first = min([i for i in (body.find("request.method"), body.find("await ")) if i >= 0] or [len(body)])
    if gate < 0 or gate > first or "notHere()" not in body[gate:body.find("\n", gate)]:
        bad.append(f"{route} does not answer notHere() without BENCH_DB before anything else")
    if "new Response(" in src or "console." in src:
        bad.append(f"{route} answers or logs other than through workers/bench/common.js")
    if route != "/bench" and not re.search(r'request\.method !== "POST"\)\s*return plain\(405, "POST only', body):
        bad.append(f"{route} does not refuse a GET with 405 POST only")
    return bad


@check("build", "every route of the shared bench answers 404 until BENCH_DB is bound: each Function asks "
                "for it before anything else, the night's probe knows each route as it answers, and "
                "wrangler.toml binds BENCH_DB to the bench's own database alone",
       needs=("nightly",))
def _bench_switch(NI):
    """THE BINDING IS THE SWITCH (the design of 17 November 2026, decision 1: "off until its
    database is bound"). Code deployed without BENCH_DB changes nothing a reader can reach, so
    long as every route of the bench -- functions/bench.js and every file of
    functions/api/bench/ -- refuses, with workers/bench/common.js's notHere(), before it reads
    the request or awaits anything, wherever env.BENCH_DB is absent. Held, for each: that
    start; no Response or console of its own; a post route's 405 to a GET; the night's
    FUNCTION_PROBES naming it with BENCH_DB and the kind it answers as (the page a page, the
    rest posts -- a kind _night_functions_probe does not hold); and wrangler.toml binding
    BENCH_DB, wherever it does, to that environment's own bench database and to no
    database of the reports' or the follows', and no bench database under another name."""
    import tomllib
    routes = _bench_routes()
    if not routes:
        return "skip", "no functions/bench.js or functions/api/bench/ here"
    sample = ('export async function onRequest({ request, env }) {\n'
              '  if (!env.BENCH_DB || !rightPlace(request, env, PATH)) return notHere();\n'
              '  if (request.method !== "POST") return plain(405, "POST only\\n", { Allow: "POST" });\n')
    assert not _switch_problems(sample, "/api/bench/x"), _switch_problems(sample, "/api/bench/x")
    for planted, words in ((sample.replace("!env.BENCH_DB || ", ""), "without BENCH_DB"),
                           (sample.replace("  if (!env.BENCH_DB", "  const b = await request.json();\n"
                                           "  if (!env.BENCH_DB"), "without BENCH_DB"),
                           (sample + "  return new Response('x');\n", "other than through"),
                           (sample.replace('"POST only', '"Not this'), "405 POST only")):
        got = _switch_problems(planted, "/api/bench/x")
        assert any(words in g for g in got), f"the reader of a bench Function's start missed: {words} ({got})"
    bad = []
    for route, p in routes.items():
        bad += _switch_problems(_source(p), route)
    probes = {p: (needs, kind) for p, needs, kind in NI.FUNCTION_PROBES if p == "/bench" or p.startswith("/api/bench/")}
    want = {r: ("BENCH_DB", "page" if r == "/bench" else "post") for r in routes}
    if probes != want:
        bad.append(f"the night's FUNCTION_PROBES give the bench's routes {probes}, not {want}")
    conf = tomllib.loads(_source(_paths.ROOT / "wrangler.toml"))
    envs = [("top level", conf)] + [(n, e) for n, e in (conf.get("env") or {}).items()]
    bound = []
    others = {"graniterecord-reports", "graniterecord-reports-preview", "graniterecord-follow",
              "graniterecord-follow-preview"}
    for name, e in envs:
        for d in e.get("d1_databases") or []:
            if d.get("binding") == "BENCH_DB":
                bound.append(name)
                if d.get("database_name") != BENCH_DBS.get(name) or d.get("database_name") in others:
                    bad.append(f"wrangler.toml's {name} binds BENCH_DB to {d.get('database_name')}, not "
                               f"{BENCH_DBS.get(name, 'the bench database of an environment that has one')}")
            elif d.get("database_name") in BENCH_DBS.values():
                bad.append(f"wrangler.toml's {name} binds the bench's {d.get('database_name')} as {d.get('binding')}")
    assert not bad, "; ".join(bad)
    return "ok", (f"{len(routes)} routes of the bench, each a 404 of its own until BENCH_DB is bound, before "
                  "anything else; the night asks each as it answers; BENCH_DB "
                  + (f"bound in {', '.join(bound)}, to the bench's own database" if bound else
                     "bound nowhere yet, so every route answers 404"))


# The columns of the bench's database, as the design keeps them: of a person, the link's name
# and two days. A column added here is a decision about the page's promise ("nothing else
# about you is"), and is made in the schema and here together.
BENCH_COLUMNS = {
    "links": ["id", "name", "token_hash", "role", "queues", "state", "made_on", "last_on", "daily_cap"],
    "queues": ["queue", "label", "pool", "judged", "as_of", "options", "ord"],
    "groups": ["grp", "queue", "label", "ord"],
    "items": ["kind", "key", "queue", "pack", "grp", "ord", "card", "shown", "state", "held_by", "held_until"],
    "calib": ["kind", "key", "queue", "card", "hers", "ord"],
    "calib_holds": ["link", "kind", "key", "held_until"],
    "judgments": ["id", "kind", "key", "link", "verdict", "fields", "note", "hidden", "side", "at", "calib", "state"],
    "link_days": ["link", "day", "n"],
    # The owner's Your input tab (23 November 2026): her list, and her answers to it.
    "asks": ["key", "section", "ord", "card", "pack", "state", "added_on"],
    "ask_answers": ["id", "key", "link", "answer", "note", "hidden", "at", "pulled"],
}
_PERSON = re.compile(r"(^|_)(ip|email|e_?mail|mail|address|addr|cookie|agent|device|browser|referr?er|"
                     r"session|phone|token|user|person|who)(_|$)")


def _schema_columns(text):
    """{table: [column]} of a schema's CREATE TABLE statements, in order."""
    out = {}
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", text, re.S):
        cols = []
        for line in m.group(2).splitlines():
            line = line.split("--")[0].strip()
            w = re.match(r"^(\w+)\s+(TEXT|INTEGER|REAL|BLOB)\b", line)
            if w:
                cols.append(w.group(1))
        out[m.group(1)] = cols
    return out


@check("build", "the shared bench keeps of a person the link's name and two days, and nothing else: "
                "every column of its schema is the design's, and none is an address, a device or a token")
def _bench_keeps_nothing():
    """The design's promise, which the page prints under every item: "Your answers are kept
    with this link, and nothing else about you is." Held on workers/bench/schema.sql, read
    here without node: every table and column is BENCH_COLUMNS's, in order; "name" is a
    column of links alone; no column is named for an IP, an email or an address, a cookie,
    a device or a browser, a referrer, a session, a phone, a user or a token (a token's
    hash is token_hash, and the token itself is never kept)."""
    p = _paths.ROOT / "workers" / "bench" / "schema.sql"
    if not p.is_file():
        return "skip", "no workers/bench/schema.sql here"
    planted = _schema_columns("CREATE TABLE IF NOT EXISTS t (\n  a  TEXT,\n  ip_hash TEXT -- x\n);")
    assert planted == {"t": ["a", "ip_hash"]}, planted
    assert all(_PERSON.search(c) for c in ("ip_hash", "email", "user_agent", "device", "referer", "token")) and \
        not any(_PERSON.search(c) for c in ("made_on", "link", "held_by", "hidden", "key")), (
            "the reader of a column about a person reads a name wrongly")
    cols = _schema_columns(_source(p))
    assert cols == BENCH_COLUMNS, f"the bench's schema has {cols}, and the design keeps {BENCH_COLUMNS}"
    names = [t for t, cs in cols.items() if "name" in cs]
    assert names == ["links"], f"a name is kept in {names}"
    person = [f"{t}.{c}" for t, cs in cols.items() for c in cs if c != "token_hash" and _PERSON.search(c)]
    assert not person, "a column about a person: " + ", ".join(person)
    return "ok", (f"{len(cols)} tables, {sum(len(c) for c in cols.values())} columns, every one the design's; "
                  "of a person, links.name and the days made and last used")


@check("build", "the shared bench is linked from nowhere and answers unindexed and uncached: no page or "
                "builder names /bench, no built site holds it or lists it, and every answer says noindex "
                "and no-store")
def _bench_unlisted():
    """The design's address (decision 3): /bench#<token>, "unlisted: linked from nowhere, not in
    the sitemap, noindex, and not named in robots.txt, which would advertise it", and
    answered by a Function, so that site/ is the same with the bench as without it. Held: no
    file under src/pages/ -- every page, the sitemap and robots.txt are written there -- names
    /bench; workers/bench/common.js heads every answer no-store and noindex and the page also
    frame-ancestors 'none'; the page carries <meta name="robots" content="noindex">; and, where a
    built site is here, it holds no bench file and its sitemap and robots.txt do not name it
    (a data check: a bare clone has no site/)."""
    pages = _paths.ROOT / "src" / "pages"
    if not pages.is_dir():
        return "skip", "no src/pages here"
    named = sorted(p.relative_to(_paths.ROOT).as_posix() for p in pages.rglob("*")
                   if p.is_file() and p.suffix in (".py", ".js", ".html", ".css", ".json", ".txt")
                   and re.search(r"/bench\b", _source(p, errors="replace")))
    assert not named, "these name the bench, which is linked from nowhere: " + ", ".join(named)
    common = _source(_paths.ROOT / "workers" / "bench" / "common.js")
    base = re.search(r"const BASE = \{(.*?)\};", common, re.S)
    assert base and '"Cache-Control": "no-store"' in base.group(1) and '"X-Robots-Tag": "noindex"' in base.group(1), (
        "workers/bench/common.js's answers are not all no-store and noindex")
    assert re.search(r"pageResponse\(status, body, nonce\) \{\s*return new Response\(body, \{ status, headers: \{\s*"
                     r"\.\.\.BASE", common) and "frame-ancestors 'none'" in common, (
        "the bench's page is not headed as every other answer, or may be framed")
    assert '<meta name="robots" content="noindex">' in _source(_paths.ROOT / "workers" / "bench" / "page.js")
    site = _paths.ROOT / "site"
    if not (site / "index.html").is_file():
        return "ok", ("no page or builder names /bench, and every answer is no-store and noindex; no built "
                      "site here to read")
    held = [p.name for p in site.glob("bench*")]
    listed = [n for n in ("sitemap.xml", "robots.txt") if (site / n).is_file()
              and re.search(r"/bench\b", (site / n).read_text(encoding="utf-8", errors="replace"))]
    assert not held and not listed, f"the built site holds {held} and lists the bench in {listed}"
    return "ok", ("no page or builder names /bench, every answer is no-store and noindex, and the built site "
                  "neither holds nor lists it")


# The ledger's writers: the laptop's bench, and the merge of the hosted bench's answers.
LEDGER_WRITERS = {"src/checks/review.py", "src/checks/bench_pull.py"}
_RECORDS = re.compile(r"\b(?:review|RV)\.record\s*\(")
_OPENS = re.compile(r"open\s*\([^)\n]*checked\.jsonl[^)\n]*[\"'][aw]")
_NAMED = re.compile(r"^[ \t]*([A-Za-z_]\w*)[ \t]*=[^=\n]*[\"']checked\.jsonl[\"']", re.M)


def _writes_ledger(src):
    """Whether a script writes review/checked.jsonl: through review's record(); by opening the
    file's name for writing; or through a name a line of its own gives that file (LEDGER =
    OUT / "checked.jsonl", then LEDGER.open("a")). Another file's LEDGER -- compile_reports'
    handled.jsonl -- is not it, and a script that only names the file is not a writer."""
    if _RECORDS.search(src) or _OPENS.search(src):
        return True
    for name in set(_NAMED.findall(src)):
        n = re.escape(name)
        if re.search(rf"\b{n}\s*\.\s*(?:open\s*\(\s*(?:mode\s*=\s*)?[\"'][aw]|write_text\s*\(|write_bytes\s*\()"
                     rf"|\bopen\s*\(\s*{n}\s*,\s*(?:mode\s*=\s*)?[\"'][aw]", src):
            return True
    return False


@check("files", "the bench's ledger has two writers, review.py and bench_pull.py: no other script "
                "appends to review/checked.jsonl or calls review.record")
def _bench_ledger_writers():
    """review/checked.jsonl is the owner's (corrections/ and review/ are a person's, and
    _record_untouched holds no build_ or fetch_ script names it). Since the shared bench
    there are two ways a line arrives: her own judgment on the laptop's bench (review.py,
    which defines record()), and her approval of answers from the hosted bench (bench_pull.py,
    which appends through that record()). Held over every code file but the suite's: none
    else calls review.record, opens the ledger's name for writing, or appends through a
    LEDGER it names -- bench_pack.py reads it and writes SQL, and the Functions never see
    it."""
    for text, writes in (('import review\nreview.record({"kind": "x"})', True),
                         ('import review as RV\nRV.record(e)', True),
                         ('open("review/checked.jsonl", "a")', True),
                         ('LEDGER = OUT / "checked.jsonl"\nwith LEDGER.open("a", encoding="utf-8") as fh:', True),
                         ('LEDGER = OUT / "handled.jsonl"\nwith LEDGER.open("a", encoding="utf-8") as fh:', False),
                         ('lines = BL.read(BL.LEDGER)', False),
                         ('"""Each tells review/checked.jsonl what it said."""\nOUT.write_text(t)', False),
                         ('BENCH = Path("review") / "checked.jsonl"\nPath("x.json").write_text(t)', False),
                         ('p = Path("review") / "checked.jsonl"\nfor line in p.read_text().splitlines():', False)):
        assert _writes_ledger(text) == writes, f"the reader of the ledger's writers reads {text!r} wrongly"
    files = [f for f in _paths.code_files("*.py") if not _in_suite(f)]
    found = sorted(f.relative_to(_paths.ROOT).as_posix() for f in files
                   if _writes_ledger(_source(f, errors="replace")))
    assert set(found) <= LEDGER_WRITERS, "these write the bench's ledger: " + ", ".join(sorted(set(found) - LEDGER_WRITERS))
    assert set(found) == LEDGER_WRITERS, f"the ledger's writers are {found}: the reader no longer finds them"
    return "ok", f"{len(files)} code files read: the ledger's writers are {', '.join(found)} alone"


# ---- the shared bench's own tests -------------------------------------------------

BENCH_TESTS = Path("tests/bench/index.js")


@check("build", "the shared bench's own tests pass, every one: node --test runs tests/bench/index.js, "
                "which imports every test file in tests/bench/")
def _bench_tests():
    """tests/bench/ is the shared bench's test suite (workers/bench/, the Functions
    functions/bench.js and functions/api/bench/), standard library only, on the
    follow tests' fake D1 (tests/follow/fake_d1.js) given the bench's own
    schema. Run here whole, as _follow_tests runs tests/follow/: index.js by
    name, every *.test.js of the folder imported there, the counts read off
    TAP. What they hold, in their own words: an item served once and held two
    at a time; holds that lapse unless renewed; an answer kept in the
    ledger's words with its item judged in one batch; the cap, one answer a
    second, undo, calibration one in twenty-five; the Links page's calls; and,
    as the Functions and the page come, every route a 404 without BENCH_DB."""
    index = BENCH_TESTS
    if not index.is_file():
        return "skip", "tests/bench/index.js is not here"
    imported = re.findall(r'^import\s+"\./([^"]+)";', _source(index), re.M)
    files = sorted(p.name for p in index.parent.glob("*.test.js"))
    missing = [f for f in files if f not in imported]
    assert not missing, (f"tests/bench/index.js does not import {', '.join(missing)}, so node --test "
                         "never runs it: add an import line for each")
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", f"node is not on PATH, so the {len(files)} test files in tests/bench/ did not run"
    r = _run([node, "--disable-warning=ExperimentalWarning", "--test", "--test-reporter=tap",
              index.as_posix()], capture_output=True, text=True, timeout=300)
    out = (r.stdout or "") + (r.stderr or "")
    count = {k: int(v) for k, v in re.findall(r"^# (tests|pass|fail|cancelled|skipped|todo) (\d+)$",
                                               out, re.M)}
    fails = _tap_failures(out)
    assert not fails, (
        f"tests/bench/ fails {len(fails)} of {count.get('tests', '?')}: "
        + "; ".join(f"{n!r} ({s})" if s else repr(n) for n, s in fails[:6])
        + (f" (+{len(fails) - 6} more)" if len(fails) > 6 else "")
        + f". `node --test {index.as_posix()}` shows each in full")
    assert r.returncode == 0 and count.get("pass", 0) > 0 and not count.get("fail") \
        and not count.get("cancelled"), (
        f"node --test {index.as_posix()} exited {r.returncode} with {count or 'no count'}: "
        + out.strip()[-500:])
    return "ok", (f"tests/bench: {count['pass']} passed of {count.get('tests')}, from "
                  f"{len(files)} test files, every one imported by index.js")
