#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
A built site's sha256 manifest, kept once per commit and compared against.

    python3 src/checks/site_manifest.py record            # after a build: keep its manifest
    python3 src/checks/site_manifest.py compare           # this build against the merge base's
    python3 src/checks/site_manifest.py compare 1a2b3c4   # ... or against any commit's
    python3 src/checks/site_manifest.py list              # the manifests kept here

WHY (9 October 2026, at the person's word). A change meant to leave the site
alone is proved by building before and after and comparing a sha256 of every
file, and the "before" was proved deterministic by building it twice under
two PYTHONHASHSEEDs (CONTRIBUTING.md, "How a change is proven"). Every step
of a piece of work built its own baseline that way: three builds before the
one that mattered, on a laptop where one is forty minutes. The baseline is a
fact about a commit and the data it was built from, not about the step, so
it is kept, and made once:

  record    hashes every file of site/ but build.json (which carries the
            time) and keeps the manifest under logs/site-manifests/, keyed by
            what the build was: the commit it was built from and whether the
            tree was clean (the build's own record, build_inputs.py), the
            day it was stated to be built on, and what it was asked to do. A
            second record of the same build under another PYTHONHASHSEED is
            compared with the first, file by file, and the baseline is then
            proven deterministic -- or every file that moved is named.
  compare   hashes site/ as it stands and compares it with the kept manifest
            of BASE (the merge base with dev, where none is given): the same
            day stated, the same options, the same data under it. It names
            every file added, removed or changed, by folder; exits 0 when
            nothing moved and 1 when something did, 2 when there is no
            baseline to compare with (and says how to make one), 3 when the
            two builds are not comparable (and says why).

THE DATA UNDER THE TWO BUILDS MUST BE THE SAME. What a build reads and does
not write -- the day files, the dumps, the saved pages -- is compared by size
and time of writing, from each build's record; a file one build wrote is the
build's, and is left out, so that a change that moves narratives.json does
not make its own baseline incomparable. A build of a dirty tree is kept too,
under its own key, but only a clean build of a commit is that commit's
baseline.

Nothing here builds, writes outside --cache, or asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import hashlib
import json
from collections import Counter

import build_inputs as BI
import child

CACHE = Path("logs/site-manifests")
SKIP = ("build.json",)          # carries the time the build finished
# What a build was asked to do that changes what it makes. The seed is not
# here: two seeds of one build are what the determinism proof compares.
HOW = ("session", "base", "local", "no_captions", "with_superseded", "date_stated")


def site_hashes(site="site"):
    """{posix path under site/: sha256} for every file but SKIP."""
    site = Path(site)
    out = {}
    for rel, _st in BI.walk(site, skip=False):
        if rel not in SKIP:
            out[rel] = BI.sha256(site / rel)
    return out


def key_of(rec):
    """What makes two builds the same build: commit and clean tree (or the
    code's own digest where it was dirty), the day stated, the options."""
    how = {k: (rec.get("how") or {}).get(k) for k in HOW}
    code = None
    if rec.get("dirty"):
        code = hashlib.sha256(json.dumps(sorted((p, v[2]) for p, v in rec["code"].items()))
                              .encode("utf-8")).hexdigest()
    return {"commit": rec.get("commit"), "clean": rec.get("dirty") == [], "code": code,
            "how": how}


def key_id(key):
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def raw(rec):
    """What the build read and did not write: {path: [size, mtime]}."""
    written = set(rec.get("written") or ())
    return {p: v for p, v in (rec.get("data") or {}).items() if p not in written}


def data_differs(a, b):
    """The files the two builds both read and neither wrote that differ, or
    that one had and the other did not; [] when the data is the same."""
    ra, rb = raw(a), raw(b)
    wrote = set(a.get("written") or ()) | set(b.get("written") or ())
    out = [p for p in set(ra) & set(rb) if ra[p] != rb[p]]
    out += [p for p in set(ra) ^ set(rb) if p not in wrote]
    return sorted(out)


def _this_build(site):
    """The build's record (build_inputs.RECORD), if it describes site/."""
    rec = BI.load()
    if rec is None:
        raise SystemExit(f"no record of a build here ({BI.RECORD}): build_all.py writes one when "
                         "a build ends well, and a manifest is kept only of a build it describes")
    if BI.site_build_sha(site) != rec.get("site_build"):
        raise SystemExit(f"{site}/build.json is not the one the recorded build wrote: site/ is "
                         "not that build's. Build again, then record.")
    if rec.get("fast"):
        raise SystemExit(f"{site}/ has had the fast path's changes put into it since the build "
                         f"({len(rec['fast'])} run(s) of build_all.py --front-end): it is not "
                         "one build's output. Build in full, then record.")
    if not rec.get("usable", False):
        raise SystemExit("the build ran while code changed under it: build again, then record")
    return rec


def _kept(cache):
    out = []
    for f in sorted(Path(cache).glob("*.json")):
        try:
            out.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except (OSError, ValueError):
            continue
    return out


def _diff(old, new):
    changed = sorted(p for p in set(old) & set(new) if old[p] != new[p])
    return changed, sorted(set(new) - set(old)), sorted(set(old) - set(new))


def _by_folder(paths, n=40):
    top = Counter(p.split("/", 1)[0] if "/" in p else "(root)" for p in paths)
    lines = ["    " + ", ".join(f"{k} {v:,}" for k, v in top.most_common(12))]
    lines += [f"    {p}" for p in paths[:n]]
    if len(paths) > n:
        lines.append(f"    ...and {len(paths) - n:,} more")
    return "\n".join(lines)


def cmd_record(a):
    rec = _this_build(a.site)
    key = key_of(rec)
    if not key["how"]["date_stated"]:
        print("WARNING: this build's day was not stated (GRANITE_BUILD_DATE), so its pages "
              "carry today's date and it compares only with a build made today.")
    files = site_hashes(a.site)
    seed = (rec.get("how") or {}).get("hashseed")
    kid = key_id(key)
    cache = Path(a.cache)
    cache.mkdir(parents=True, exist_ok=True)
    out = cache / f"{kid}.seed-{seed if seed is not None else 'random'}.json"
    man = {"key": key, "seed": seed, "finished": rec.get("finished"),
           "data": raw(rec), "written": rec.get("written") or [],
           "files": files, "deterministic": None}
    print(f"{len(files):,} files of {a.site}/ hashed; commit {str(key['commit'])[:10]}"
          f"{'' if key['clean'] else ' (with changes not committed)'}, "
          f"day {key['how']['date_stated'] or 'not stated'}, seed {seed}")
    # THE DETERMINISM PROOF: the same build under another seed.
    for f, other in _kept(cache):
        if f == out or other.get("key") != key or other.get("seed") == seed:
            continue
        if data_differs(other, man):
            continue
        changed, added, gone = _diff(other["files"], files)
        if changed or added or gone:
            man["deterministic"] = False
            print(f"NOT DETERMINISTIC: the same build under seeds {other.get('seed')} and "
                  f"{seed} differs in {len(changed) + len(added) + len(gone):,} files:")
            print(_by_folder(changed + added + gone))
        else:
            man["deterministic"] = sorted({str(other.get("seed")), str(seed)})
            other["deterministic"] = man["deterministic"]
            f.write_text(json.dumps(other), encoding="utf-8")
            print(f"deterministic: all {len(files):,} files identical under PYTHONHASHSEED "
                  f"{other.get('seed')} and {seed}")
        break
    else:
        print(f"kept as {out}. Record the same build under another PYTHONHASHSEED to prove "
              "it deterministic.")
    out.write_text(json.dumps(man), encoding="utf-8")
    return 0


def cmd_compare(a):
    import check_select
    rec = BI.load()
    if rec is None or BI.site_build_sha(a.site) != rec.get("site_build"):
        print(f"no record of the build that made {a.site}/ ({BI.RECORD}); comparing the files "
              "alone, without the check that the data and the options are the same")
        rec = None
    try:
        base = check_select.merge_base(a.base)
    except RuntimeError as e:
        print(str(e))
        return 2
    now_key = key_of(rec) if rec else None
    kept = [(f, m) for f, m in _kept(a.cache)
            if m["key"].get("commit") == base and m["key"].get("clean")]
    if now_key:
        same_how = [(f, m) for f, m in kept if m["key"]["how"] == now_key["how"]]
        if kept and not same_how:
            print(f"NOT COMPARABLE: {base[:10]} has a manifest here, of a build asked for "
                  f"{kept[0][1]['key']['how']}, and this one was asked for {now_key['how']}")
            return 3
        kept = same_how
    if not kept:
        print(f"no manifest of a clean build of {base[:10]} here ({a.cache}). Build it once, "
              "with the day stated, and keep it:\n"
              f"  git switch --detach {base[:10]}\n"
              "  set GRANITE_BUILD_DATE=<a day>  &  set PYTHONHASHSEED=0\n"
              "  python3 build_all.py --local\n"
              "  python3 src/checks/site_manifest.py record\n"
              "(and again with PYTHONHASHSEED=1, to prove it deterministic), then switch back.")
        return 2
    # A baseline proven deterministic first, then one not yet proven; one
    # found not to be, last.
    def rank(m):
        d = m.get("deterministic")
        return 0 if d else 1 if d is None else 2
    kept.sort(key=lambda fm: (rank(fm[1]), fm[1].get("finished") or ""))
    f, man = kept[0]
    if rec is not None:
        differs = data_differs(man, {"data": rec.get("data"), "written": rec.get("written")})
        if differs:
            print(f"NOT COMPARABLE: the data under the two builds differs, in "
                  f"{len(differs):,} file(s) neither build wrote:")
            print(_by_folder(differs, 15))
            return 3
    files = site_hashes(a.site)
    changed, added, gone = _diff(man["files"], files)
    proof = man.get("deterministic")
    print(f"{a.site}/ against the build of {base[:10]} ({f.name}; day "
          f"{man['key']['how'].get('date_stated') or 'not stated'}; "
          + (f"deterministic under seeds {' and '.join(proof)}" if proof else
             "NOT PROVEN DETERMINISTIC: record it under a second seed" if proof is None else
             "NOT DETERMINISTIC") + ")")
    same = len(set(files) & set(man["files"])) - len(changed)
    print(f"  {same:,} files unchanged, {len(changed):,} changed, {len(added):,} added, "
          f"{len(gone):,} removed")
    for what, paths in (("changed", changed), ("added", added), ("removed", gone)):
        if paths:
            print(f"  {what}:")
            print(_by_folder(paths))
    return 0 if not (changed or added or gone) else 1


def cmd_list(a):
    rows = _kept(a.cache)
    if not rows:
        print(f"no manifests in {a.cache}")
    for f, m in rows:
        k = m["key"]
        print(f"{f.name}: commit {str(k.get('commit'))[:10]}"
              f"{'' if k.get('clean') else ' (dirty)'}, day {k['how'].get('date_stated')}, "
              f"seed {m.get('seed')}, {len(m.get('files') or {}):,} files, "
              f"deterministic {m.get('deterministic')}")
    return 0


def main():
    ap = argparse.ArgumentParser(description="a built site's sha256 manifest, kept once per "
                                             "commit and compared against")
    ap.add_argument("--site", default="site")
    ap.add_argument("--cache", default=str(CACHE),
                    help="where manifests are kept (default logs/site-manifests)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("record", help="keep this build's manifest")
    c = sub.add_parser("compare", help="this build against BASE's kept manifest")
    c.add_argument("base", nargs="?", default=None,
                   help="a commit (default: the merge base of HEAD and dev)")
    sub.add_parser("list", help="the manifests kept here")
    a = ap.parse_args()
    sys.exit({"record": cmd_record, "compare": cmd_compare, "list": cmd_list}[a.cmd](a))


if __name__ == "__main__":
    main()
