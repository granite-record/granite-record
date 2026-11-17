#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.4
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
from contextlib import redirect_stdout
from pathlib import Path

import _paths

from pf_core import _run, _source, check
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
       needs=("bench_pack", "bench_ledger"))
def _bench_pack(BP, BL):
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
            with contextlib.redirect_stdout(out):
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
