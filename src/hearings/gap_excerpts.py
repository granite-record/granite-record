#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.1
"""
The few minutes of caption text around each proceeding with no stated
boundary, for a person (or a session) to read.

    python3 src/hearings/gap_excerpts.py                      # the busiest gaps first
    python3 src/hearings/gap_excerpts.py --setting executive --limit 60
    python3 src/hearings/gap_excerpts.py --videos C6YkO_S7nmg LJtnllAy6o4

Writes logs/gap_excerpts.txt (logs/ is not tracked) and nothing else. Asks
nobody: it reads proceedings.csv, candidate_segments.json, data/bills.json
and the caption files under work/.

WHY THIS EXISTS

segment_markers --gaps prints 210 characters around ONE mention of three
bills per recording, to the console. That is enough to notice a phrase and
not enough to decide where a proceeding began: the first mention is often
the chair reading the day's agenda an hour before the item, and the words
that open it are a sentence or two earlier than the number. This keeps,
for every unplaced proceeding on the recordings with the most of them, the
text from 40 seconds before to 30 seconds after up to three separate
mentions of the bill -- the ones between the boundaries the chair did state
either side of it in the docket's order first -- with a time on every line.
Reading those is how a convention the patterns do not know is found; it is
counted afterwards with segment_markers --phrases and scored with
probe_alignment --truth, and nothing read here goes on the site by itself.

A bill counts as unplaced when the candidate file has no boundary for it on
that recording at all; a bill heard in the morning and executed in the
afternoon, with only the hearing found, is not listed. The bills a
committee recording never names (_not_named) and a floor session's consent
calendar (_absent, with --floor) are left out, since there is nothing to read.

THE TEXT IS NOT FOR PUBLISHING. Captions render "HB 1381" as "HP 1381";
CLAUDE.md's "Captions are not quoted on the site" applies to this file.
--max-mb keeps it to a size that can be attached to a message (8 MB by
default, about 6,000 excerpts).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
from collections import Counter, defaultdict

import proceedings as P
import segment_markers as S

SETTINGS = {"hearing": "hearing", "executive": "executive", "work": "work",
            "conference": "conference"}


def hms(t):
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def mentions(words, text, when, bill, title):
    """[(second, how)] where the bill is named: its digits anywhere (the
    comparison all_mentions makes, which reads "HB1 1474" and "hb 1 27"),
    or, where they never occur, its title the way match_bill reads one."""
    d = re.sub(r"[^0-9]", "", bill)
    out = []
    if d:
        rx = re.compile(r"(?<!\d)" + r"[\s,]*".join(d) + r"(?!\d)")
        out = [(when(m.start()), "number") for m in rx.finditer(text)]
    if out or not title:
        return out
    for i in range(0, len(words), 8):
        t0 = words[i][0]
        j = i
        while j < len(words) and words[j][0] - t0 <= 20:
            j += 1
        if j - i >= 4 and S.match_bill(" ".join(w for _, w in words[i:j]), [bill],
                                       {bill: title})[0] == bill:
            out.append((t0, "title"))
    return out


def pick(found, lo, hi, per, apart=90):
    """Up to `per` mentions at least `apart` seconds from each other, those
    inside [lo, hi] -- between the stated boundaries either side -- first."""
    inside = [x for x in found if lo <= x[0] <= hi]
    rest = [x for x in found if not (lo <= x[0] <= hi)]
    got = []
    for t, how in inside + rest:
        if all(abs(t - g[0]) >= apart for g in got):
            got.append((t, how))
        if len(got) >= per:
            break
    return sorted(got)


def excerpt(words, t, before, after, step=10):
    """The words from t-before to t+after, one line about every `step` s."""
    lines, cur, t0 = [], [], None
    for tt, w in words:
        if tt < t - before:
            continue
        if tt > t + after:
            break
        if t0 is None:
            t0 = tt
        cur.append(w)
        if tt - t0 >= step:
            lines.append(f"    {hms(t0)}  {' '.join(cur)}")
            cur, t0 = [], None
    if cur:
        lines.append(f"    {hms(t0)}  {' '.join(cur)}")
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default="work")
    ap.add_argument("--data", default="data")
    ap.add_argument("--candidate", default="candidate_segments.json")
    ap.add_argument("--out", default="logs/gap_excerpts.txt")
    ap.add_argument("--setting", choices=sorted(SETTINGS),
                    help="only proceedings of this kind (the docket's word)")
    ap.add_argument("--committee", help="only committees whose name contains this")
    ap.add_argument("--since", default="", help="only sittings on or after this date")
    ap.add_argument("--videos", nargs="+", help="only these recordings")
    ap.add_argument("--limit", type=int, default=0,
                    help="at most this many recordings, the most unplaced first")
    ap.add_argument("--per", type=int, default=3, help="mentions shown per proceeding")
    ap.add_argument("--before", type=int, default=40)
    ap.add_argument("--after", type=int, default=30)
    ap.add_argument("--max-mb", type=float, default=8.0)
    ap.add_argument("--floor", action="store_true",
                    help="the floor sessions instead: bills debated (not on the consent "
                         "calendar) whose clerk's reading was not found")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cp = Path(a.candidate)
    if not cp.exists():
        sys.exit(f"No {cp}: run python3 src/hearings/segment_markers.py --all first.")
    cs = json.loads(cp.read_text(encoding="utf-8"))
    by_term = S.title_lookup(a.data)
    prows = P.load()
    if not prows:
        sys.exit("No proceedings.csv. Run: python3 src/hearings/build_proceedings.py")
    floor = P.floor_videos(prows)
    # A committee recording's bills it never names (_not_named), and a floor
    # session's consent calendar (_absent): neither has a moment to find.
    unnamed = cs.get("_absent" if a.floor else "_not_named") or {}
    vterm = defaultdict(Counter)
    byvid = defaultdict(list)
    for r in (P.floor_only(prows) if a.floor else P.committee_only(prows)):
        v = r["video_id"]
        if not v or (v in floor) != a.floor or r.get("whole_video"):
            continue
        vterm[v][r["term"]] += 1
        byvid[v].append(r)

    def wanted(r):
        k = (r["kind"] or "").lower()
        return ((not a.setting or SETTINGS[a.setting] in k)
                and (not a.committee or a.committee.lower() in (r["committee"] or "").lower())
                and (r["date"] or "") >= a.since)

    todo = []
    for v, rs in byvid.items():
        if a.videos and v not in a.videos:
            continue
        if not any((Path(a.work) / v / f).exists() for f in S.WORK_FILES):
            continue
        placed = cs.get(v) or {}
        gap = [r for r in rs if wanted(r) and r["bill"] not in placed
               and r["bill"] not in (unnamed.get(v) or [])]
        if gap:
            todo.append((len(gap), v, rs, gap))
    todo.sort(key=lambda x: (-x[0], x[1]))
    if a.limit:
        todo = todo[:a.limit]
    if not todo:
        sys.exit("No unplaced proceeding on a recording with captions here.")

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cap = int(a.max_mb * 1024 * 1024)
    n_rec = n_proc = n_never = size = 0
    with out.open("w", encoding="utf-8") as fh:
        head = ("# gap_excerpts: caption text around proceedings with no stated boundary.\n"
                "# NOT FOR PUBLISHING: captions garble bill numbers. Times are into the recording.\n"
                f"# {len(todo):,} recordings, {sum(x[0] for x in todo):,} unplaced proceedings\n")
        fh.write(head)
        size += len(head.encode())
        for _n, v, rs, gap in todo:
            words = S.read_words(str(Path(a.work) / v))
            if not words:
                continue
            text, when = S._joined(words)
            cands = sorted({r["bill"] for r in rs})
            titles = S.titles_for(by_term, vterm[v], cands)
            placed = cs.get(v) or {}
            # The stated openings in time order, to bound each gap: the
            # docket's order of the day, and where each placed bill began.
            order = sorted(rs, key=lambda r: (r["time"] or "", r["bill"]))
            starts = {b: min(s["start"] for s in ss) for b, ss in placed.items()
                      if isinstance(ss, list) and ss}
            block = [f"\n=== {v}  {rs[0]['date']}  {rs[0]['committee']}  "
                     f"({len(gap)} of {len(rs)} unplaced)"]
            seq = [f"{r['time'] or '--:--'} {r['bill']}"
                   + (f" @{hms(starts[r['bill']])}" if r["bill"] in starts else " -")
                   for r in order]
            block.append("  docket: " + ", ".join(seq))
            never = 0
            for r in gap:
                b = r["bill"]
                # Bounded by the bills noticed for an earlier or a later
                # time only: a House executive session notices forty bills
                # for 10:00, and their order on the docket is the bill
                # numbers', not the day's.
                when_ = r["time"] or ""
                lo = max([starts[x["bill"]] for x in order
                          if x["bill"] in starts and (x["time"] or "") < when_] or [0])
                hi = min([starts[x["bill"]] for x in order
                          if x["bill"] in starts and (x["time"] or "") > when_]
                         or [words[-1][0]])
                if lo > hi:
                    lo, hi = 0, words[-1][0]
                found = mentions(words, text, when, b, titles.get(b, ""))
                block.append(f"\n--- {b}  {r['kind']}  sched {r['time'] or '?'}  "
                             f"\"{(titles.get(b) or '')[:90]}\"")
                block.append(f"    expected between {hms(lo)} and {hms(hi)}; "
                             f"named {len(found)} time(s)")
                never += not found
                for t, how in pick(found, lo, hi, a.per):
                    block.append(f"  > named at {hms(t)} ({how})")
                    block += excerpt(words, t, a.before, a.after)
            chunk = "\n".join(block) + "\n"
            if size + len(chunk.encode()) > cap:
                fh.write(f"\n# stopped at --max-mb {a.max_mb}: {n_rec:,} recordings written\n")
                break
            fh.write(chunk)
            size += len(chunk.encode())
            n_rec += 1
            n_proc += len(gap)
            n_never += never
    print(f"{n_proc:,} unplaced proceedings on {n_rec:,} recordings -> {out} "
          f"({size / 1e6:.1f} MB); {n_never:,} never named by number or title")
    print("Not for publishing: it quotes captions. Attach it to a message, or read it here.")


if __name__ == "__main__":
    main()
