#!/usr/bin/env python3
"""wf20: take the 15 misfiled House journal keys out of the bucket's kit.

Run on the laptop from the repository root, AFTER the files have been moved
on the laptop and `cloud.py seed-kit` has sent their new paths:

    python3 %USERPROFILE%\\wf20_remove_keys.py --when         (may the kit be written now?)
    python3 %USERPROFILE%\\wf20_remove_keys.py --dry-run      (reads the bucket, writes nothing)
    python3 %USERPROFILE%\\wf20_remove_keys.py                (does it)

No command of src/ops/cloud.py removes a file the laptop owns from kit/: seed-kit
leaves "in the bucket's kit and not here" alone (cloud.py:1432, 1441) and kit-up
removes only the night's own (cloud.py:1733-1734). This does it with cloud.py's
own pieces, as kit-up does for a night's file: each object is copied to
replaced/<day>/kit/<path> first (cloud.Replacer, kept 30 days), and the kit
manifest is merged as it stands now and its old copy kept (cloud.write_manifest).
The manifest is written FIRST, so a kit-down never sees an entry whose object is
gone; run again, it finishes what an interrupted run left.

It refuses: inside GitHub's night window or before the night's verdict is in
(cloud.send_night_late, cloud.night_unfinished, as send-night does); while an
old path, or the PDF beside it, is still on the laptop (seed-kit or
extract_calendar_text would bring it back); and unless every new path is in
kit/ and the manifest with the same sha256 as the old one.

--local-bucket=FOLDER is for a test against a folder, never the real bucket.
"""
import sys
from argparse import Namespace
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd().resolve()
sys.path.insert(0, str(ROOT / "src" / "ops"))
import cloud  # noqa: E402

COPIES = [6, 9, 10, 13, 18, 19, 20, 21, 22, 23, 24, 25]
ORG = "Daily Journal #1, 12-1-10, Organization Day Final.txt"
PAIRS = ([(f"journals/2010/HJ{n:03d}.txt", f"journals/2011/HJ{n:03d}.txt") for n in COPIES]
         + [(f"journals/2010/{ORG}", f"journals/2011/{ORG}"),
            ("journals/2000/HJ025.txt", "journals/1999/HJ025.txt"),
            ("journals/2000/HJ026.txt", "journals/1999/HJ026.txt")])
BY = "by hand: wf20, the 15 misfiled House journals"


def stop(msg):
    print(f"wf20: STOPPED, nothing written: {msg}", file=sys.stderr)
    sys.exit(1)


def main(argv):
    dry = "--dry-run" in argv
    folder = next((a.split("=", 1)[1] for a in argv if a.startswith("--local-bucket=")), None)
    if not (ROOT / "cloud_kit.json").exists():
        stop(f"{ROOT} is not the repository root (no cloud_kit.json)")
    if "--when" in argv:                    # only: may a kit write be made now?
        b = cloud.open_bucket(Namespace(local_bucket=folder, workers=8, dry_run=True))
        why = [w for w in (cloud.send_night_late(ROOT), cloud.night_unfinished(b)) if w]
        print(f"wf20: not now: {why[0]}" if why else
              "wf20: clear: GitHub's night window is closed, the last night has sent its "
              "verdict or run out its time, and no build or nightly is writing here")
        return 1 if why else 0
    kit = cloud.load_kit(ROOT)
    for old, new in PAIRS:
        for p in (old, new):
            if cloud.owner_of(kit, p) != "laptop":
                stop(f"{p} is not the laptop's in cloud_kit.json")
    here = [p for old, _ in PAIRS for p in (old, old[:-4] + ".pdf") if cloud.local(ROOT, p).exists()]
    if here:
        stop(f"{len(here)} old path(s) still on this laptop, which seed-kit or "
             f"extract_calendar_text would bring back: {', '.join(here[:4])}")
    b = cloud.open_bucket(Namespace(local_bucket=folder, workers=8, dry_run=dry))
    man, _ = cloud.read_manifest(b, "kit")
    if man is None:
        stop(f"{b.describe()} has no kit manifest")
    files, remote = man["files"], b.list("kit/")
    todo = []
    for old, new in PAIRS:
        if new not in files or f"kit/{new}" not in remote:
            stop(f"{new} is not in kit/ and its manifest yet: run seed-kit first")
        if old not in files and f"kit/{old}" not in remote:
            continue                        # already done
        if old in files and files[old]["sha256"] != files[new]["sha256"]:
            stop(f"{old} and {new} are not the same bytes; look before removing it")
        todo.append(old)
    print(f"wf20: {b.describe()}: {len(todo)} of {len(PAIRS)} old keys to remove "
          f"(each copied to replaced/ first); the {len(PAIRS)} new paths are in kit/")
    for p in todo:
        print(f"    kit/{p}" + ("" if p in files else "   (object only; not in the manifest)"))
    why = [w for w in (cloud.send_night_late(ROOT), cloud.night_unfinished(b)) if w]
    if dry:
        for w in why:
            print(f"wf20: would refuse now: {w}")
        print("wf20: --dry-run: nothing written")
        return 0
    if why:
        stop(why[0])
    if not todo:
        print("wf20: nothing to do")
        return 0
    with cloud.machine_lock(ROOT):
        rep = cloud.Replacer(b, f"{datetime.now():%Y-%m-%d}")
        gone = [p for p in todo if p in files]
        doc = cloud.write_manifest(b, "kit", {}, gone, BY, rep)
        for p in todo:
            if f"kit/{p}" in remote:
                rep.keep(f"kit/{p}")
                b.delete(f"kit/{p}")
    after, _ = cloud.read_manifest(b, "kit")
    left = b.list("kit/")
    bad = ([f"{o} still in the manifest" for o, _ in PAIRS if o in after["files"]]
           + [f"kit/{o} still in the bucket" for o, _ in PAIRS if f"kit/{o}" in left]
           + [f"{n} missing" for _, n in PAIRS
              if n not in after["files"] or f"kit/{n}" not in left])
    print(f"wf20: removed {len(todo)} keys; {rep.n} copies kept under replaced/{rep.day}/; "
          f"kit manifest {doc['count']:,} files")
    if bad:
        stop("read back wrong: " + "; ".join(bad[:4]))
    print("wf20: read back: no old path in kit/ or its manifest; every new path in both")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
