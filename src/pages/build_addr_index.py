#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-24.1
"""
The address box's suggestions: New Hampshire's streets, in small files by
the first two letters a reader types.

    python3 src/pages/build_addr_index.py --site site    # collected/nh_streets.json -> site/addr/<key>.json

WHY (the person, 24 October 2026: "I'd like to make some improvements to the
address search so that it shows you a dropdown of matching addresses around
New Hampshire as you're typing with the zip codes"). The Your town panel
offers "12 Main St, Concord, NH 03301" as a reader types "12 main st conc",
from these files, and only the address they choose goes to the Census
Bureau. find.js fetches one of them when the street has two letters, and
matches in the browser; this site is asked for "/addr/ma.json" and never for
what was typed.

THE KEY is the first two letters or digits of the street as typed, its
spaces left out: "main st" is ma, "n main" nm, "north main" no. A street is
in the file of every way a reader is likely to start it, and each of those
is a FORM: the name as the Census writes it, and

  its first word spelt out or shortened   N Main St    north main st
                                          Mt Vernon St mount vernon st
                                          St John Ln   saint john ln
  without a leading direction             N Main St    main st
                                          (not "E St", whose E is its name)
  a numbered route as people say it       State Rte 16 route 16, rte 16, nh 16, nh rte 16
                                          US Hwy 3     us 3, us rte 3, route 3, rte 3

Every word after the first is matched by find.js against what it
abbreviates (St, street; Rd, road; N, north), so only the first word needs a
form. A row carries the forms that are in its file and are not its name; the
browser matches a form only where its key is the file's, so the two cannot
disagree about which file a street is in.

A FILE is {"k": its key, "t": [the towns in it], "r": rows}, a row
[street, town's place in t, ZIP, house numbers, forms]: the house numbers a
flat list of runs, [lo, hi, lo, hi, ...], each of one parity, the parity of
its ends; the forms there only where there are some.

THE ROWS' ORDER IS THE ORDER A TIE IS OFFERED IN: the towns with the most
streets first, and in a town the street with the most numbers. A street's
own count of numbers was tried alone first, and "107 n ma" offered North
Main Street in eight small towns before Concord's, because a rural road's
numbers run to 1,400 where a city block's stop at 300; how many streets a
town has is the nearer measure of where people live.

WHAT IT WRITES. Every file in site/addr/, and nothing else there: a file
left by an earlier run whose key no street has now is removed. About 450
files, 2 MB in all; check_site watches the site's file count.

WITHOUT THE LIST (collected/nh_streets.json missing -- a fork that has not
read the Census files yet): it says so, removes site/addr/ so no earlier
list is served as this build's, and writes nothing. The box then works as
it did before there were suggestions; find.js asks for a file, is answered
404, and offers none.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re
import shutil
import unicodedata
from collections import Counter, defaultdict

SRC = Path("collected/nh_streets.json")
# Above this many files the site's own count is worth a look before more are
# added: Cloudflare Pages allows 100,000, and check_site warns at 90,000.
MOST_FILES = 700
DIRS = {"n": "north", "s": "south", "e": "east", "w": "west",
        "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest"}
FIRST = {"mt": "mount", "mount": "mt", "st": "saint", "saint": "st", "ft": "fort", "fort": "ft"}
# The last words that say what kind of street it is, as the Census abbreviates
# them: "E St" is a street called E, and "E Main St" is Main Street's east end.
TYPES = {"st", "rd", "ave", "dr", "ln", "way", "hwy", "cir", "ct", "pl", "tpke", "ter",
         "blvd", "trl", "path", "loop", "run", "pkwy", "sq", "xing", "pt", "rdg"}
ROUTE = re.compile(r"^(?:(state|us|nh) )?(?:rte|hwy|route) ([0-9]+[a-z]?)( [nsew])?$")


def norm(s):
    """What find.js's yaNorm makes of the same words: lower case, accents
    and apostrophes gone, anything else not a letter or digit a space."""
    s = unicodedata.normalize("NFKD", str(s).lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"['’]", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def key(form):
    """The file a form is in: its first two letters or digits."""
    k = form.replace(" ", "")[:2]
    return k if len(k) == 2 else None


def forms(name):
    """Every way a reader is likely to start typing a street, the name first."""
    t = norm(name).split()
    if not t:
        return []
    out = [t]
    if t[0] in DIRS and len(t) > 1:
        out.append([DIRS[t[0]]] + t[1:])
        if len(t) > 2 or t[1] not in TYPES:
            out.append(t[1:])
    if t[0] in FIRST and len(t) > 1:
        out.append([FIRST[t[0]]] + t[1:])
    m = ROUTE.match(" ".join(t))
    if m:
        qual, rest = m.group(1), [m.group(2)] + ([m.group(3).strip()] if m.group(3) else [])
        out += [["rte"] + rest, ["route"] + rest]
        if qual == "us":
            out += [["us"] + rest, ["us", "rte"] + rest]
        else:
            out += [["nh"] + rest, ["nh", "rte"] + rest]
    seen, uniq = set(), []
    for f in out:
        s = " ".join(f)
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def runs(text):
    """"1-299 2-298" -> [1, 299, 2, 298]."""
    out = []
    for part in (text or "").split():
        lo, _, hi = part.partition("-")
        out += [int(lo), int(hi or lo)]
    return out


def size(flat):
    return sum((flat[i + 1] - flat[i]) // 2 + 1 for i in range(0, len(flat), 2))


def shards(rows):
    """{key: {"k", "t", "r"}} from the collected rows."""
    streets = Counter(r[1] for r in rows)
    by = defaultdict(list)
    for name, town, zp, numbers in rows:
        fs = forms(name)
        if not fs:
            continue
        own, flat = fs[0], runs(numbers)
        keys = defaultdict(list)
        for f in fs:
            k = key(f)
            if k:
                keys[k].append(f)
        for k, fl in keys.items():
            extra = [f for f in fl if f != own]
            by[k].append((name, town, zp, flat, extra))
    out = {}
    for k, rs in by.items():
        rs.sort(key=lambda r: (-streets[r[1]], r[1], -size(r[3]), r[0], r[2]))
        towns = sorted({r[1] for r in rs})
        at = {t: i for i, t in enumerate(towns)}
        out[k] = {"k": k, "t": towns,
                  "r": [[n, at[t], z, f] + ([x] if x else []) for n, t, z, f, x in rs]}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--site", default="site")
    ap.add_argument("--src", default=str(SRC))
    a = ap.parse_args()
    site, src = Path(a.site), Path(a.src)
    out = site / "addr"
    if not src.is_file():
        if out.exists():
            shutil.rmtree(out)
        print(f"  WARNING: {src} is not here, so the address box offers no suggestions "
              "and works as it did without them. python3 src/towns/parse_tiger_streets.py "
              "writes it from the Census Bureau's files (src/fetch/other/tiger_streets.py).")
        return 0
    doc = json.loads(src.read_text(encoding="utf-8"))
    rows = doc.get("rows") or []
    # Silence is not success: a list read as empty would publish a box that
    # never suggests anything, and nothing would say so.
    if len(rows) < 1:
        raise SystemExit(f"{src} has no rows")
    got = shards(rows)
    out.mkdir(parents=True, exist_ok=True)
    written = set()
    sizes = []
    for k in sorted(got):
        body = json.dumps(got[k], separators=(",", ":"), ensure_ascii=False)
        p = out / f"{k}.json"
        if not p.exists() or p.read_text(encoding="utf-8") != body:
            p.write_text(body, encoding="utf-8", newline="\n")
        written.add(p.name)
        sizes.append(len(body.encode("utf-8")))
    gone = [p for p in out.glob("*.json") if p.name not in written]
    for p in gone:
        p.unlink()
    sizes.sort()
    src_said = doc.get("source") or {}
    print(f"  addr/: {len(got)} files of street suggestions, {sum(sizes) / 1e6:.2f} MB, "
          f"the largest {sizes[-1] / 1e3:.0f} KB, the median {sizes[len(sizes) // 2] / 1e3:.1f} KB, "
          f"from {len(rows):,} streets by town and ZIP ({src_said.get('release', '?')}, "
          f"published {src_said.get('published', '?')})"
          + (f"; {len(gone)} left from an earlier list removed" if gone else ""))
    if len(got) > MOST_FILES:
        print(f"  WARNING: {len(got)} files in addr/, more than the {MOST_FILES} this was "
              "designed for: python3 src/checks/check_site.py says what the site's count is")
    return 0


if __name__ == "__main__":
    sys.exit(main())
