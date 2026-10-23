#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.14
"""
Every version of a bill, in order, and what each amendment changed.

    python3 src/parse/build_bill_versions.py --check     # report only, writes nothing
    python3 src/parse/build_bill_versions.py --site site

Writes site/versions/<year>/<BILL>.json for every bill with more than one
version. No network: it reads db/LegislationText.psv, db/Legislation.psv and
db/document_versions.json, all already on this disk -- and the same two
views of every term frozen under db/term/<term>/.

A TERM'S VERSIONS OUTLIVE THE DATABASE'S CURRENT VIEWS

LegislationText and Legislation are the database's current-term views. When
the General Court turns them over to 2027-2028, the next dump of them holds
no 2025-2026 bill, and every one of that term's Versions tabs would have gone
with them -- this writes the whole site/versions tree and the manifest from
whatever the dump holds. So the views are frozen before they turn, into
db/term/<term>/ with the _columns.json they were dumped with (a
LegislationID restarts every term, so a term's text is only ever joined to
its own Legislation rows), and read after the current views: a bill-year the
current views hold comes from them, and a frozen term supplies only what
they no longer do. With no frozen term on disk this reads exactly what it
always did.

WHY A SEPARATE FILE

A bill's record travels inside its page now, and the median record is 1.3 KB.
Version texts average 6,796 characters for "Introduced" and 9,970 for "As
Amended by the Senate", so folding four versions into every page would undo
the thing that took the site from 73,086 files to 39,501. These are fetched
when the reader opens the versions tab and not before, and only 1,149 of 2,234
bills have a second version at all.

THE ORDER IS THE RECORD'S, NOT AN ASSUMPTION

PublicNHLMS.DocumentVersion gives every label a SortOrder: Introduced is 20,
As Amended by either chamber is 30, a second committee 35 or 50, adopted by
both bodies 70, OLS Release 80, CHAPTERED FINAL VERSION 120. Guessing that
order from the words would have put OLS Release near the beginning; it is
near the end.

That table cost some trouble worth writing down. db/DocumentVersion.psv holds
54 rows with 16 fields, and db/_columns.json describes it with 10 -- because
the view lives in PublicNHLMS, whose INFORMATION_SCHEMA publicuser cannot
read, so fetch_archive_db fell back to the 13-row view of the same name in
NHLegislatureDB for its column list. Reading the file against those columns
gives nonsense. db/document_versions.json is the same table asked for by
column name, which needs no catalogue.

A LABEL IS NOT UNIQUE WITHIN A BILL

493 bills carry two or more rows with the same label -- SB13 has three OLS
Releases. They are kept, ordered by their timestamp, and the later ones are
marked with their date so a reader can tell them apart. Dropping them would be
deciding which of three the record meant.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import concurrent.futures
import difflib
import json
import os
import re

import bill_blocks
import build_cache

DB = Path("db")

# NOT A VERSION OF THE BILL. "OLS Release" is the text of an AMENDMENT: 1,803
# of its 2,009 rows begin "Amendment to HB 650-FN -- Amend RSA 188-E:24 ... by
# replacing it with the following", and its median length is 2,006 characters
# against 4,445 for Introduced. Every other label is 0% of that shape.
#
# Left in the version sequence it did real harm. HB650 went Introduced (6,947
# chars) to As Amended by the Senate (6,980) to adopted by both bodies (7,021)
# and then to an "OLS Release" of 750, and the diff between them reported
# 1,019 words removed -- telling a reader the bill had been gutted when what
# had actually happened was that the next document was a different kind of
# document.
#
# It is kept, because it is the best thing here: the amendment in the General
# Court's own words, saying which RSA it amends and what it replaces. It is
# shown beside the versions rather than among them.
AMENDMENT_LABELS = {"OLS Release"}
WORD = re.compile(r"\S+\s*")
# Words of unchanged text kept either side of a change.
CONTEXT = 25


def columns(folder=DB):
    return json.loads((folder / "_columns.json").read_text(encoding="utf-8"))


# A term's views as they stood at its end: see the docstring.
FROZEN = DB / "term"


def sources():
    """[(folder, its column lists)]: the current dump, then each frozen term
    holding both views, oldest first."""
    out = [(DB, columns())]
    if FROZEN.is_dir():
        for d in sorted(x for x in FROZEN.iterdir() if x.is_dir()):
            if (d / "Legislation.psv").exists() and (d / "LegislationText.psv").exists():
                out.append((d, columns(d) if (d / "_columns.json").exists() else out[0][1]))
    return out


def bills_by_id(lg, folder=DB):
    out = {}
    i_id, i_no, i_yr = (lg.index("legislationID"), lg.index("CondensedBillNo"),
                        lg.index("sessionyear"))
    for line in (folder / "Legislation.psv").open(encoding="utf-8"):
        f = line.rstrip("\n").split("|")
        if len(f) >= len(lg) and f[i_id].strip():
            out[f[i_id].strip()] = (f[i_no].strip(), f[i_yr].strip())
    return out


def tidy(t):
    """The text as a person would read it: the record's own line breaks kept,
    its column padding taken out."""
    t = t.replace("\r", "")
    t = re.sub(r"[ \t]{2,}", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def runs(a, b):
    """What changed between two texts, as a list of (op, text).

    Word-level rather than line-level: a bill is reprinted with different line
    breaks at every stage, so a line diff calls every line changed and says
    nothing. Words survive reformatting.
    """
    aw, bw = WORD.findall(a), WORD.findall(b)
    out = []
    sm = difflib.SequenceMatcher(None, aw, bw, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(["=", "".join(aw[i1:i2])])
        else:
            if i1 != i2:
                out.append(["-", "".join(aw[i1:i2])])
            if j1 != j2:
                out.append(["+", "".join(bw[j1:j2])])
    # Runs of the same op next to each other read as one change, not two.
    merged = []
    for op, txt in out:
        if merged and merged[-1][0] == op:
            merged[-1][1] += txt
        else:
            merged.append([op, txt])

    # CONTEXT, NOT THE WHOLE BILL AGAIN. An unchanged stretch is kept only at
    # the edges of a change: a reader wants to see what moved and enough
    # around it to know where, not the other 1,400 unchanged words repeated
    # for every one of 53 amendments. HB2 came to 11.4 MB before this.
    #
    # A skipped stretch is not silently dropped -- it becomes a "~" run
    # carrying its own word count, so the page can say "412 words unchanged"
    # and the reader knows the diff is not the whole document.
    out = []
    for i, (op, txt) in enumerate(merged):
        if op != "=":
            out.append([op, txt])
            continue
        words = WORD.findall(txt)
        if len(words) <= CONTEXT * 2 + 8:
            out.append([op, txt])
            continue
        head = "".join(words[:CONTEXT]) if i else ""
        tail = "".join(words[-CONTEXT:]) if i < len(merged) - 1 else ""
        if head:
            out.append(["=", head])
        out.append(["~", str(len(words) - (CONTEXT if head else 0)
                             - (CONTEXT if tail else 0))])
        if tail:
            out.append(["=", tail])
    return out


def compare(a, b):
    """One version against the next: (runs, marks, m_added, m_removed)."""
    r = runs(a["text"], b["text"])
    mk, m_add, m_rem = (bill_blocks.marks(a["blocks"], b["blocks"])
                        if a.get("blocks") and b.get("blocks") else ([], 0, 0))
    return r, mk, m_add, m_rem


# THE FEW VERY LONG PAIRS, AT ONCE (16 October 2026, private/BUILD_SPEED.md).
# A word diff with autojunk off grows with the product of the two lengths,
# and the budget's are of another order: HB 2 of 2025's four longest pairs
# multiply to 3.3 to 8.9 billion, the next pair of the term to 0.27 billion,
# and those four took 302 of the 377 seconds of diffing on the laptop, one
# after another. They are compared first, in processes of their own, longest
# first, by the compare() the loop uses, and the loop takes each result where
# it would have computed it: the same function on the same two versions, so
# the same output by construction, and the scratch build of 16 October was
# byte for byte the build before it. A pair below BIG_PAIR stays in the loop,
# where a process would cost more to start than it saves.
BIG_PAIR = 1_000_000_000
POOL_MOST = 4


def ordered(vs):
    """(versions, amendments) of one bill, as the loop diffs them."""
    amendments = [v for v in vs if v["label"] in AMENDMENT_LABELS]
    vs = [v for v in vs if v["label"] not in AMENDMENT_LABELS]
    vs.sort(key=lambda v: (v["sort"], v["date"]))
    amendments.sort(key=lambda v: v["date"])
    return vs, amendments


def compare_early(per, known=()):
    """{(bill, year, i): compare()} of the pairs whose words multiply past
    BIG_PAIR, computed in a pool; {} where there are fewer than two of them or
    one processor, which the loop does as before. A pair in `known`, whose
    answer was kept (KEPT), is not compared again."""
    big = []
    for key, vs in per.items():
        vs, _ = ordered(vs)
        for i in range(len(vs) - 1):
            if (*key, i) in known:
                continue
            a, b = vs[i]["text"], vs[i + 1]["text"]
            # Characters first: no pair has more words than characters, so a
            # pair short of the mark in characters is short of it in words.
            if len(a) * len(b) < BIG_PAIR:
                continue
            n = len(WORD.findall(a)) * len(WORD.findall(b))
            if n >= BIG_PAIR:
                big.append((n, key, i, vs[i], vs[i + 1]))
    cpus = os.cpu_count() or 1
    if len(big) < 2 or cpus < 2:
        return {}
    big.sort(key=lambda x: -x[0])
    with concurrent.futures.ProcessPoolExecutor(
            max_workers=min(POOL_MOST, len(big), cpus)) as pool:
        futures = {(*key, i): pool.submit(compare, va, vb) for _, key, i, va, vb in big}
        return {k: f.result() for k, f in futures.items()}


# THE PAIRS COMPARED BEFORE, KEPT (23 October 2026; build_cache.py says how).
# Nearly every pair the loop compares is one an earlier night compared,
# printings that have not changed since, and a word diff of the longest takes
# minutes: on GitHub's machine the step was four. compare()'s answer depends
# on the two versions' texts and blocks and on nothing else but the code, so
# it is kept under a sha256 of those and of the code (build_cache.signature
# of this file, which takes in bill_blocks and what else it imports), and a
# pair whose key is kept is not compared again. The answer kept is the one
# compare() gave, as JSON gives it back -- lists where it made lists, which
# is all it makes -- and is written into the step files exactly as a fresh
# one would be. A cache that is not there, will not read or is another
# code's is no cache, and every pair is compared as before.
KEPT = "bill_versions"


def version_key(v):
    """A sha256 of what compare() reads of one version: its text and its
    blocks."""
    return build_cache.digest(v["text"], json.dumps(v.get("blocks") or [],
                                                     separators=(",", ":")))


def kept_answer(x):
    """A kept answer as compare() returns it, or None where it is not of
    compare()'s shape."""
    if (isinstance(x, list) and len(x) == 4 and isinstance(x[0], list)
            and isinstance(x[1], list) and all(type(n) is int for n in x[2:])
            and all(isinstance(r, list) and len(r) == 2 and all(isinstance(t, str) for t in r)
                    for r in x[0])):
        return tuple(x)
    return None


def pair_keys(per, sig):
    """{(bill, year, i): the key compare(vs[i], vs[i + 1]) is kept under}."""
    out = {}
    for key, vs in per.items():
        vs, _ = ordered(vs)
        if len(vs) < 2:
            continue
        ks = [version_key(v) for v in vs]
        for i in range(len(vs) - 1):
            out[(*key, i)] = build_cache.digest(sig, ks[i], ks[i + 1])
    return out


def read_versions(folder, C, order, unknown):
    """{(bill, year): [version]} out of one dump's LegislationText, joined to
    the same dump's Legislation."""
    lt, lg = C["LegislationText"], C["Legislation"]
    bills = bills_by_id(lg, folder)
    i_lid, i_dv, i_txt, i_dt = (lt.index("LegislationID"),
                                lt.index("DocumentVersion"),
                                lt.index("Text"), lt.index("DateTimeStamp"))
    # AND THE COLUMN THE PLAIN ONE WAS FLATTENED FROM. HTMLText carries the
    # Court's own marking of what the bill adds to and removes from existing
    # law -- added matter in bold italics, removed matter struck through --
    # which Text throws away. bill_blocks reads it; this is where it enters
    # the build. Nothing downstream depends on it yet: the blocks file is
    # written BESIDE the .txt and the index gains a field beside text_url, so
    # an app.js that has never heard of either keeps working unchanged.
    i_html = lt.index("HTMLText")
    per = collections.defaultdict(list)
    for line in (folder / "LegislationText.psv").open(encoding="utf-8"):
        f = line.rstrip("\n").split("|")
        if len(f) < len(lt):
            continue
        b = bills.get(f[i_lid].strip())
        if not b:
            continue
        label = f[i_dv].strip()
        if label not in order:
            unknown[label] += 1
        per[b].append({
            "label": label,
            "sort": (order.get(label) or {}).get("sort", 999),
            "date": f[i_dt].strip(),
            "text": tidy(f[i_txt]),
            # Parsed here rather than held as HTML: the source column is
            # 173 MB across the table and the blocks are a third of that.
            # A row whose HTML will not parse gets an empty list and simply
            # has no blocks file, which the index then does not point at.
            "blocks": bill_blocks.blocks(f[i_html]),
        })
    return per


def all_versions(order, unknown, session=None):
    """{(bill, year): [version]} from the current dump and every frozen term.
    The current views first, so a bill-year they hold is theirs -- except a
    finished term's.

    A FINISHED TERM'S BILL-YEARS ARE ITS FREEZE'S (5 October 2026): a frozen
    term older than the session's files' (proceedings.session_term) takes
    every bill-year of its own years from its freeze, and the current views'
    rows of those years are counted and left out, never merged -- the one
    rule for a finished term's rows in new files. A term frozen while it is
    still the session's waits, and is not read: the current views hold it."""
    import proceedings as PR
    session = PR.session_term() if session is None else session
    per = collections.defaultdict(list)
    srcs = sources()
    finished = {d.name for d, _ in srcs[1:] if PR.TERM_RE.match(d.name)
                and session and d.name < session}
    years = {y for t in finished for y in t.split("-")}
    for folder, C in srcs:
        if folder != DB and PR.TERM_RE.match(folder.name) and session \
                and folder.name >= session:
            print(f"  {folder} waits: {folder.name} is still the session's term")
            continue
        mine = read_versions(folder, C, order, unknown)
        if folder == DB and years:
            gone = [k for k in mine if str(k[1]) in years]
            for k in gone:
                del mine[k]
            if gone:
                print(f"  {len(gone):,} bill-years of {', '.join(sorted(finished))} in the "
                      "current views left out: the term is read from its freeze")
        taken = [k for k in mine if k not in per]
        for k in taken:
            per[k] = mine[k]
        if folder != DB:
            print(f"  {folder}: {len(taken):,} bills the current views no longer hold")
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--manifest", default="data/bill_versions.json")
    a = ap.parse_args()

    order = json.loads((DB / "document_versions.json").read_text(encoding="utf-8"))
    unknown = collections.Counter()
    per = all_versions(order, unknown)
    # The pairs an earlier run compared (KEPT), and what each is kept under.
    sig = build_cache.signature("build_bill_versions.py")
    kept = build_cache.load(KEPT, sig)
    keys = pair_keys(per, sig)
    known = {}
    for k, ck in keys.items():
        got = kept_answer(kept.get(ck))
        if got is not None:
            known[k] = got
    del kept
    print(f"  {len(known):,} of {len(keys):,} pairs compared before and kept; "
          f"{len(keys) - len(known):,} to compare")
    used = {}
    # --limit stops the loop part way, so nothing is compared ahead of it.
    early = {} if a.limit else compare_early(per, known)

    out = Path(a.site) / "versions"
    written = steps_total = texts = amds = lone = 0
    blocks_written = 0
    manifest = collections.defaultdict(dict)
    multi = 0
    biggest = ("", 0)
    for (bill, year), vs in sorted(per.items()):
        if len(vs) < 2:
            continue
        multi += 1
        if a.limit and written >= a.limit:
            break
        vs, amendments = ordered(vs)
        if len(vs) < 2:
            # A bill whose only extra documents were amendments still has
            # something worth showing, but nothing to diff.
            lone += 1
            if not amendments:
                continue
        # A label used twice in one bill gets its date, so the two can be told
        # apart on a page that lists them.
        seen = collections.Counter(v["label"] for v in vs)
        for v in vs:
            v["title"] = (f'{v["label"]} ({v["date"].split()[0]})'
                          if seen[v["label"]] > 1 else v["label"])
        steps = []
        for i in range(len(vs) - 1):
            # MARKS BESIDE RUNS, not instead of them. runs is the comparison
            # as an excerpt -- changed passages with context, the unchanged
            # bulk elided. marks is the same comparison expressed as positions
            # in the NEW version's blocks, which is what lets the change be
            # drawn ON the document a reader is already looking at rather than
            # beside it. Both are written until the page is proven against the
            # second, because app.js keeps only x.runs today and a step file
            # carrying marks alone would render an empty diff with no error.
            #
            # added and removed STAY COMPUTED FROM runs. They are read from
            # the INDEX, before any step file is fetched, to draw the bars and
            # the "+N -N words" line; recomputing them from a different stream
            # would change numbers the site already states on 1,149 bills for
            # no reader-visible gain.
            got = known.get((bill, year, i)) or early.pop((bill, year, i), None)
            r, mk, m_add, m_rem = got if got else compare(vs[i], vs[i + 1])
            used[keys[(bill, year, i)]] = [r, mk, m_add, m_rem]
            steps.append({
                "from": i, "to": i + 1,
                "added": sum(len(t.split()) for op, t in r if op == "+"),
                "removed": sum(len(t.split()) for op, t in r if op == "-"),
                "runs": r,
                "marks": mk,
                # The marks' own counts, kept apart from the index's. They
                # differ on purpose: marks diff the stream with the running
                # header, the legend and the rules taken out, and the index's
                # figures come from the plain text with all three in.
                "m_added": m_add, "m_removed": m_rem,
            })
        steps_total += len(steps)
        # THE INDEX AND THE DIFFS HERE; EACH VERSION'S TEXT BESIDE IT. HB2
        # has 54 versions of a very long bill, and one file holding all of
        # them was 11.4 MB. A reader opening the versions tab wants the list
        # and what changed; the full text of one version is a second, small
        # fetch made only when they pick it.
        # ONE FETCH PER THING LOOKED AT. The index carries the list of
        # versions and how much each amendment changed; a version's text and
        # a comparison's detail are each their own file, fetched when the
        # reader picks them.
        #
        # HB2 is why. It is the state budget with 54 versions whose amendments
        # rewrite most of the bill, so its diffs do not compress the way an
        # ordinary bill's do: one file held 11.4 MB, and 6.4 MB even with the
        # unchanged stretches cut to context. Split, its index is 4 KB and no
        # single fetch is more than the one comparison being read.
        rec = {"bill": bill, "year": year,
               # words AS WELL AS chars, because the steps below are counted
               # in words -- added and removed are len(t.split()) -- and a
               # bar drawn against a character count would be a proportion of
               # one thing shown against a total of another. About forty
               # bytes a bill, into a file that already exists.
               "versions": [{"title": v["title"], "label": v["label"],
                             "sort": v["sort"], "date": v["date"],
                             "chars": len(v["text"]),
                             "words": len(v["text"].split()),
                             "text_url": f"/versions/{year}/{bill}.{i}.txt",
                             # ADDED, NOT SUBSTITUTED. text_url never changes
                             # meaning, so app.js's `url.endsWith(".json")`
                             # test keeps giving the answer it always gave --
                             # a rename there would have parsed 3,731 plain
                             # texts as JSON and blanked the Full text view,
                             # which is the default the reader lands on.
                             **({"blocks_url":
                                 f"/versions/{year}/{bill}.{i}.blocks.json"}
                                if v.get("blocks") else {})}
                            for i, v in enumerate(vs)],
               "amendments": [{"date": v["date"], "chars": len(v["text"]),
                               "text_url": f"/versions/{year}/{bill}.a{j}.txt"}
                              for j, v in enumerate(amendments)],
               "steps": [{"from": s["from"], "to": s["to"],
                          "added": s["added"], "removed": s["removed"],
                          "runs_url":
                              f'/versions/{year}/{bill}.{s["from"]}-{s["to"]}.json'}
                         for s in steps]}
        if not a.check:
            (out / year).mkdir(parents=True, exist_ok=True)
            for i, v in enumerate(vs):
                (out / year / f"{bill}.{i}.txt").write_text(
                    v["text"], encoding="utf-8")
                texts += 1
                if v.get("blocks"):
                    (out / year / f"{bill}.{i}.blocks.json").write_text(
                        json.dumps({"blocks": v["blocks"]},
                                   separators=(",", ":"), ensure_ascii=False),
                        encoding="utf-8")
                    blocks_written += 1
            for j, v in enumerate(amendments):
                (out / year / f"{bill}.a{j}.txt").write_text(
                    v["text"], encoding="utf-8")
                amds += 1
            for s in steps:
                (out / year / f'{bill}.{s["from"]}-{s["to"]}.json').write_text(
                    json.dumps({"runs": s["runs"], "marks": s["marks"],
                                "added": s["m_added"], "removed": s["m_removed"]},
                               separators=(",", ":"), ensure_ascii=False),
                    encoding="utf-8")
            p = out / year / f"{bill}.json"
            p.write_text(json.dumps(rec, separators=(",", ":")),
                         encoding="utf-8")
            if p.stat().st_size > biggest[1]:
                biggest = (f"{year}/{bill}", p.stat().st_size)
        manifest[year][bill] = {"versions": len(vs),
                                "amendments": len(amendments),
                                "steps": len(steps)}
        written += 1
    # A pair compared early that the loop never took is a pair whose diff
    # went nowhere: the two lists of versions came out in different orders.
    if early:
        raise SystemExit(f"STOP: {len(early)} pair(s) compared ahead were not met by the "
                         f"loop, e.g. {next(iter(early))}; nothing more is written")
    # Kept for the next run: the answers this one used, and no others, so the
    # cache is the record as it stands. Only by a run over every bill: one
    # stopped by --limit, or --check, which writes nothing, keeps nothing.
    if not a.limit and not a.check:
        if build_cache.save(KEPT, sig, used):
            print(f"  {len(used):,} pairs' comparisons kept for the next run "
                  f"({build_cache.path_of(KEPT)})")

    # A MANIFEST, SO THE PAGE KNOWS BEFORE IT ASKS. Only 1,149 of 2,234 bills
    # have a second version, so a Versions tab on every bill would be a tab
    # that says "there is one version" 1,085 times and a 404 behind each of
    # them. build_site_v2 reads this and stamps the counts onto the record,
    # which is why this step runs before it.
    if not a.check:
        man = Path(a.manifest)
        man.parent.mkdir(parents=True, exist_ok=True)
        man.write_text(json.dumps(manifest, indent=1, sort_keys=True),
                       encoding="utf-8")
        print(f"  manifest of {sum(len(v) for v in manifest.values()):,} bills "
              f"-> {man}")

    print(f"{len(per):,} bills have text; {multi:,} have more than one version")
    print(f"  {written:,} written, {steps_total:,} amendment steps between "
          f"them, {texts:,} version texts and {amds:,} amendment texts "
          "beside them")
    # SAID OUT LOUD, because a step that can write nothing and still exit 0 is
    # how this project has lost work before. A blocks count of zero against a
    # non-zero text count means HTMLText stopped parsing, and it would
    # otherwise be invisible: the index simply omits blocks_url and the page
    # falls back to the plain text exactly as it does today.
    if texts:
        print(f"  {blocks_written:,} of those carry the Court's own marking "
              f"({blocks_written / texts * 100:.0f}%)"
              + ("   <- NONE. HTMLText is not parsing." if not blocks_written
                 else ""))
    if lone:
        print(f"  {lone:,} have one version and an amendment, so nothing to "
              "diff; the amendment is still written")
    if biggest[1]:
        print(f"  largest {biggest[0]} at {biggest[1] / 1024:,.0f} KB")
    if unknown:
        print("  labels with no sort order, filed last: "
              + ", ".join(f"{k!r} x{v}" for k, v in unknown.most_common(4)))
    # Silence is not success.
    if multi and not written and not a.check:
        raise SystemExit("Bills have versions and nothing was written.")
    if a.check:
        print("\n  --check: nothing written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
