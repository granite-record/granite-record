#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.6
"""
Every version of a bill, in order, and what each amendment changed.

    python3 build_bill_versions.py --check     # report only, writes nothing
    python3 build_bill_versions.py --site site

Writes site/versions/<year>/<BILL>.json for every bill with more than one
version. No network: it reads db/LegislationText.psv, db/Legislation.psv and
db/document_versions.json, all already on this disk.

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

import argparse
import collections
import difflib
import json
import re
from pathlib import Path

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


def columns():
    return json.loads((DB / "_columns.json").read_text(encoding="utf-8"))


def bills_by_id(lg):
    out = {}
    i_id, i_no, i_yr = (lg.index("legislationID"), lg.index("CondensedBillNo"),
                        lg.index("sessionyear"))
    for line in (DB / "Legislation.psv").open(encoding="utf-8"):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--manifest", default="data/bill_versions.json")
    a = ap.parse_args()

    C = columns()
    lt, lg = C["LegislationText"], C["Legislation"]
    bills = bills_by_id(lg)
    order = json.loads((DB / "document_versions.json").read_text(encoding="utf-8"))

    i_lid, i_dv, i_txt, i_dt = (lt.index("LegislationID"),
                                lt.index("DocumentVersion"),
                                lt.index("Text"), lt.index("DateTimeStamp"))
    per = collections.defaultdict(list)
    unknown = collections.Counter()
    for line in (DB / "LegislationText.psv").open(encoding="utf-8"):
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
        })

    out = Path(a.site) / "versions"
    written = steps_total = texts = amds = lone = 0
    manifest = collections.defaultdict(dict)
    multi = 0
    biggest = ("", 0)
    for (bill, year), vs in sorted(per.items()):
        if len(vs) < 2:
            continue
        multi += 1
        if a.limit and written >= a.limit:
            break
        amendments = [v for v in vs if v["label"] in AMENDMENT_LABELS]
        vs = [v for v in vs if v["label"] not in AMENDMENT_LABELS]
        if len(vs) < 2:
            # A bill whose only extra documents were amendments still has
            # something worth showing, but nothing to diff.
            lone += 1
            if not amendments:
                continue
        vs.sort(key=lambda v: (v["sort"], v["date"]))
        amendments.sort(key=lambda v: v["date"])
        # A label used twice in one bill gets its date, so the two can be told
        # apart on a page that lists them.
        seen = collections.Counter(v["label"] for v in vs)
        for v in vs:
            v["title"] = (f'{v["label"]} ({v["date"].split()[0]})'
                          if seen[v["label"]] > 1 else v["label"])
        steps = []
        for i in range(len(vs) - 1):
            r = runs(vs[i]["text"], vs[i + 1]["text"])
            steps.append({
                "from": i, "to": i + 1,
                "added": sum(len(t.split()) for op, t in r if op == "+"),
                "removed": sum(len(t.split()) for op, t in r if op == "-"),
                "runs": r,
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
                             "text_url": f"/versions/{year}/{bill}.{i}.txt"}
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
            for j, v in enumerate(amendments):
                (out / year / f"{bill}.a{j}.txt").write_text(
                    v["text"], encoding="utf-8")
                amds += 1
            for s in steps:
                (out / year / f'{bill}.{s["from"]}-{s["to"]}.json').write_text(
                    json.dumps({"runs": s["runs"]}, separators=(",", ":")),
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
