#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
What the shared bench's contributors answered: pulled, screened, summed up,
and -- only on the owner's word -- merged into review/checked.jsonl.

    python3 src/checks/bench_pull.py                    # pull and look: nothing merged
    python3 src/checks/bench_pull.py --approve sam      # merge one link's answers (its name or id)
    python3 src/checks/bench_pull.py --approve me       # merge your own answers from your link
    python3 src/checks/bench_pull.py --withdraw b3k9    # take a merged link's lines out of every reader
    python3 src/checks/bench_pull.py --show 123         # one held note's words, for you to read
    python3 src/checks/bench_pull.py --owner-link       # make your own link (its address shown once)
    python3 src/checks/bench_pull.py --preview ...      # the preview's database instead of production's
    python3 src/checks/bench_pull.py --rows FILE ...    # rows from a JSON file: no network

RUN ONLY BY THE OWNER, ON THE LAPTOP. It reads and writes the bench's
database with `wrangler d1 execute` (compile_reports.d1_execute's way, the
same login `publish` uses), and it is the one thing but review.py that
writes the ledger.

WHAT A PULL DOES. Reads every answer not merged yet (judgments 'kept'), with
the link it came through and the item as it was drawn, and passes every note
through compile_reports.screen, the deterministic screen a reader's report
passes: a contributor's note is untrusted, and one the screen holds is not
printed or merged; it is listed, and `--show ID` prints its words for the
owner alone. Prints, link by link, its answers, which way they went, how
often its calibration answers agree with hers, and any clash with an answer
of hers. Keeps the rows, notes encoded, in reports/bench/pull-<db>-<moment>.json
and the summary beside them as .md. Merges nothing.

WHAT --approve DOES. Appends that link's answers to the ledger through
review.record -- each with the moment it was given, "by": "link:<id>" (the
link's id, never its name), or "by": "hand" for the owner's own link,
"via": "bench", the pack it came from, and "bench_id" (<db>/<row>), so a
second --approve appends none twice -- and then marks them merged in the
database, in one SQL file run by wrangler. A held note goes in as no note.
Calibration answers are never merged. Only production's answers are merged:
the preview's are a trial.

WHAT --withdraw DOES. Appends one line, {"kind": "withdraw", "by": "hand",
"link": <id>}: every reader of the ledger (bench_ledger) reads none of that
link's lines from then on, wherever they stand. Nothing is rewritten. Turn
the link off on the Links page as well, if it should answer no more.

WHAT --owner-link DOES. Makes the owner's own link -- the one that opens the
Links tab, whose answers are hers -- turning off any earlier one, and prints
its address once: only its SHA-256 is kept.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import base64
import hashlib
import json
import re
import secrets
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone

import bench_ledger as BL

DB = {"production": "graniterecord-bench", "preview": "graniterecord-bench-preview"}
SITE = {"production": "https://graniterecord.org",
        "preview": "https://dry-run.graniterecord.pages.dev"}
OUT = Path("reports") / "bench"
LINK_ID = re.compile(r"^[a-z2-9]{6}$")
ID_LETTERS = "abcdefghijkmnpqrstuvwxyz23456789"
QUEUE_OF = {"timestamp": "timing", "older": "timing", "topic": "topic", "tag": "tag"}
SIDE = {"yes": "Yes", "no": "No", "unsure": "Not sure"}
# Which way the owner went on an item, from her verdict.
HERS = {"correct": "yes", "yes": "yes", "partly": "yes", "wrong": "no", "no": "no"}

PULL = ("SELECT j.id, j.kind, j.key, j.link, j.verdict, j.fields, j.note, j.hidden, j.side, j.at, j.calib, "
        "j.state, l.name, l.role, i.shown, i.pack, c.hers FROM judgments j JOIN links l ON l.id = j.link "
        "LEFT JOIN items i ON i.kind = j.kind AND i.key = j.key LEFT JOIN calib c ON c.kind = j.kind "
        "AND c.key = j.key AND j.calib = 1 WHERE j.state = 'kept' ORDER BY j.id LIMIT 20000")


def sql_value(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def wrangler(db, sql=None, file=None):
    """One `wrangler d1 execute --remote --json` of a statement (compile_reports.d1_execute,
    with its one retry after a 7403) or of a file; its first result."""
    import compile_reports as CR
    npx = shutil.which("npx")
    if not npx:
        raise SystemExit("npx is not on PATH; wrangler reads the database")
    if sql is not None:
        return CR.d1_execute(npx, db, sql)
    # NO TERMINAL FOR WRANGLER (21 November 2026). The owner ran --owner-link in cmd
    # and it sat until the timeout: wrangler (or npx) asked a question on the
    # captured stdout and waited on her console for an answer she could not see.
    # With stdin closed it runs as it does on GitHub and in an assistant's shell.
    r = subprocess.run([npx, "wrangler", "d1", "execute", db, "--remote", "--json", "--file", str(file)],
                       capture_output=True, text=True, encoding="utf-8", timeout=300,
                       stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError("wrangler d1 execute failed: " + CR._said("\n".join(s for s in (r.stdout, r.stderr) if s)))
    return r.stdout


# ---- reading what was pulled -------------------------------------------------------------

def screened(rows):
    """Each row with its note screened (compile_reports.screen): "held" lists the reasons,
    and a held note's words are kept apart from the rest."""
    import compile_reports as CR
    out = []
    for r in rows:
        r = dict(r)
        note = str(r.get("note") or "")
        r["held"] = CR.screen(note, bool(r.get("hidden"))) if note else []
        out.append(r)
    return out


def ledger_ids(lines):
    """The bench_id of every line already merged."""
    return {d.get("bench_id") for d in lines if d.get("bench_id")}


def mine_by_item(lines):
    """{(kind, key): "yes" | "no"}: which way the owner went on each item she judged."""
    out = {}
    for (kind, key), entries in BL.by_item(lines).items():
        e = entries[-1]
        if BL.who(e) == "hand" and e.get("verdict") in HERS:
            out[(kind, key)] = HERS[e["verdict"]]
    return out


def summary(rows, lines):
    """{link id: {...}}: per link, its name and role, answers, which way they went, calibration
    agreement, clashes with the owner's own judgments, and held notes."""
    hers = mine_by_item(lines)
    per = {}
    for r in rows:
        s = per.setdefault(r["link"], {"name": r.get("name") or "", "role": r.get("role") or "",
                                       "answers": 0, "sides": Counter(), "asked": 0, "agree": 0,
                                       "clash": [], "held": [], "queues": Counter()})
        if r.get("calib"):
            if r.get("side") in ("yes", "no") and r.get("hers"):
                s["asked"] += 1
                s["agree"] += r["side"] == r["hers"]
            continue
        s["answers"] += 1
        s["sides"][r.get("side")] += 1
        s["queues"][QUEUE_OF.get(r.get("kind"), "?")] += 1
        h = hers.get((r.get("kind"), r.get("key")))
        if h and r.get("side") in ("yes", "no") and h != r["side"]:
            s["clash"].append((r, h))
        if r.get("held"):
            s["held"].append(r)
    return per


def report(per, db, rows_file):
    """The summary, as lines: for the screen and for the .md beside the rows."""
    out = [f"# The shared bench: answers not merged yet, {db}", ""]
    if not per:
        return out + ["Nothing waits to be merged."]
    for link, s in sorted(per.items(), key=lambda kv: (kv[1]["role"] == "owner", kv[1]["name"].lower())):
        who = "you (your link)" if s["role"] == "owner" else f"{s['name']} ({link})"
        sides = ", ".join(f"{n} {SIDE.get(k, k)}" for k, n in sorted(s["sides"].items(), key=lambda kv: -kv[1]))
        out.append(f"- {who}: {s['answers']} answer(s) not merged" + (f" ({sides})" if sides else ""))
        if s["queues"]:
            out.append("  " + ", ".join(f"{n} {q}" for q, n in sorted(s["queues"].items())))
        if s["role"] != "owner":
            out.append(f"  agrees with yours on {s['agree']} of {s['asked']} calibration item(s)" if s["asked"]
                       else "  no calibration answer yet")
        for r, h in s["clash"][:12]:
            out.append(f"  clashes with yours: {r['kind']} {r['key']} -- you said {SIDE[h]}, "
                       f"they said {SIDE[r['side']]}")
        for r in s["held"]:
            out.append(f"  note held, not shown (bench_pull.py --show {r['id']}): " + "; ".join(r["held"]))
    out += ["", f"The rows: {rows_file}", "",
            "To merge one link's answers into review/checked.jsonl:",
            "  python3 src/checks/bench_pull.py --approve <name or id>"]
    return out


def encode(rows):
    """The rows as kept on disk: every note encoded, as compile_reports keeps a reader's words,
    so that a search of reports/ does not surface them."""
    out = []
    for r in rows:
        r = dict(r)
        r["note"] = base64.b64encode(str(r.get("note") or "").encode("utf-8")).decode("ascii")
        r["note_encoded"] = True
        out.append(r)
    return out


def decode(rows):
    out = []
    for r in rows:
        r = dict(r)
        if r.pop("note_encoded", False):
            r["note"] = base64.b64decode(r.get("note") or "").decode("utf-8")
        out.append(r)
    return out


# ---- merging -------------------------------------------------------------------------------

def local_moment(at):
    """A moment as the ledger keeps one (review.record): the laptop's own clock, to the second."""
    d = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
    return d.astimezone().strftime("%Y-%m-%dT%H:%M:%S")


def entries(rows, which, lines):
    """The ledger lines one link's rows become, in the order they were given, leaving out
    calibration answers and any row already merged: (lines, ids)."""
    done = ledger_ids(lines)
    out, ids = [], []
    for r in sorted(rows, key=lambda x: x["id"]):
        if r.get("calib"):
            continue
        bid = f"{which}/{r['id']}"
        if bid in done:
            continue
        try:
            fields = json.loads(r.get("fields") or "{}")
        except ValueError:
            fields = {}
        try:
            shown = json.loads(r.get("shown") or "{}")
        except ValueError:
            shown = {}
        e = {"kind": r["kind"], "key": r["key"], "verdict": r["verdict"],
             "note": "" if r.get("held") else str(r.get("note") or ""),
             "by": "hand" if r.get("role") == "owner" else f"link:{r['link']}"}
        if fields:
            e["fields"] = fields
        e.update({"shown": shown, "at": local_moment(r["at"]), "via": "bench", "pack": r.get("pack") or "",
                  "bench_id": bid})
        out.append(e)
        ids.append(r["id"])
    return out, ids


def merge_sql(ids, merged, lines):
    """The statements that follow a merge: the answers marked merged; each queue's judged
    count raised by what the ledger gained; and every item the owner judged on the laptop
    marked elsewhere, so no one is asked it."""
    out = []
    for i in range(0, len(ids), 400):
        out.append("UPDATE judgments SET state = 'merged' WHERE state = 'kept' AND id IN ("
                   + ", ".join(str(int(x)) for x in ids[i:i + 400]) + ");")
    gained = Counter(QUEUE_OF.get(e["kind"]) for e in merged)
    for queue, n in sorted((q, n) for q, n in gained.items() if q):
        out.append(f"UPDATE queues SET judged = judged + {int(n)} WHERE queue = {sql_value(queue)};")
    for d in lines:
        if BL.who(d) == "hand" and d.get("via") != "bench" and d.get("kind") in QUEUE_OF:
            out.append(f"UPDATE items SET state = 'elsewhere', held_by = NULL, held_until = NULL WHERE "
                       f"kind = {sql_value(d['kind'])} AND key = {sql_value(d.get('key'))} AND state = 'open';")
    return "\n".join(out) + "\n"


def owner_link_sql(today):
    """(sql, token, id): the owner's own link, any earlier one turned off."""
    token = secrets.token_urlsafe(32)
    lid = "".join(secrets.choice(ID_LETTERS) for _ in range(6))
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    sql = ("UPDATE links SET state = 'off' WHERE role = 'owner';\n"
           "INSERT INTO links (id, name, token_hash, role, queues, state, made_on, daily_cap) VALUES ("
           f"{sql_value(lid)}, 'You', {sql_value(digest)}, 'owner', '[\"timing\",\"topic\",\"tag\"]', 'active', "
           f"{sql_value(today)}, NULL);\n")
    return sql, token, lid


def find_link(rows, name):
    """The link id `name` means: an id, or a name (any case); "me" is the owner's own."""
    links = {r["link"]: (r.get("name") or "", r.get("role")) for r in rows}
    if name.lower() == "me":
        hits = [k for k, (_n, role) in links.items() if role == "owner"]
    elif name in links:
        hits = [name]
    else:
        hits = [k for k, (n, _r) in links.items() if n.lower() == name.lower()]
    if len(hits) != 1:
        raise SystemExit(f"no one link with answers waiting is called {name!r}: "
                         + (", ".join(f"{n} ({k})" for k, (n, _r) in sorted(links.items())) or "none waits"))
    return hits[0]


def main():
    ap = argparse.ArgumentParser(description="The shared bench's answers: pull, look, and merge on your word.")
    ap.add_argument("--preview", action="store_true", help="the preview's database instead of production's")
    ap.add_argument("--approve", metavar="LINK", help="merge this link's answers (its name, its id, or me)")
    ap.add_argument("--withdraw", metavar="ID", help="take a link's merged lines out of every reader")
    ap.add_argument("--show", metavar="ROW", type=int, help="print one held note's words")
    ap.add_argument("--owner-link", action="store_true", help="make your own link; its address is shown once")
    ap.add_argument("--rows", metavar="FILE", help="answers from a JSON file instead of the database")
    a = ap.parse_args()
    which = "preview" if a.preview else "production"
    db = DB[which]
    import review

    if a.withdraw:
        if not LINK_ID.match(a.withdraw):
            raise SystemExit(f"{a.withdraw!r} is not a link's id (six letters and digits, as the Links page shows)")
        review.record({"kind": BL.WITHDRAW, "by": "hand", "link": a.withdraw})
        print(f"Withdrawn: no reader of {review.LEDGER.as_posix()} reads link {a.withdraw}'s lines from now on.")
        print("Turn the link off on the Links page too, if it should answer no more.")
        return 0

    if a.owner_link:
        sql, token, lid = owner_link_sql(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / f"owner-{which}.sql"
        path.write_text(sql, encoding="utf-8", newline="\n")
        wrangler(db, file=path)
        path.unlink()
        print(f"Your link ({lid}) on {db}, shown this once -- keep it; only its fingerprint is kept:")
        print(f"  {SITE[which]}/bench#{token}")
        if which == "preview":
            print("  (any preview address of the site opens it: the token is the preview database's)")
        return 0

    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    if a.rows:
        rows = json.loads(Path(a.rows).read_text(encoding="utf-8"))
        rows = decode(rows) if isinstance(rows, list) else rows.get("results", [])
    else:
        rows = wrangler(db, sql=PULL)["results"]
    rows = screened(rows)
    lines = BL.read(review.LEDGER)

    if a.show is not None:
        r = next((x for x in rows if x["id"] == a.show), None)
        if not r:
            raise SystemExit(f"no answer {a.show} waits to be merged")
        print(f"Answer {r['id']} ({r.get('name')}, {r['kind']} {r['key']}): its note, as typed:")
        print(r.get("note") or "(no note)")
        return 0

    per = summary(rows, lines)
    OUT.mkdir(parents=True, exist_ok=True)
    rows_file = OUT / f"pull-{which}-{stamp}.json"
    rows_file.write_text(json.dumps(encode(rows), ensure_ascii=False, indent=0), encoding="utf-8")
    said = report(per, db, rows_file.as_posix())
    (OUT / f"pull-{which}-{stamp}.md").write_text("\n".join(said) + "\n", encoding="utf-8")
    print("\n".join(said))

    if not a.approve:
        return 0
    if which != "production":
        raise SystemExit("\nNothing merged: the preview's answers are a trial, and only production's go "
                         "into the ledger.")
    link = find_link(rows, a.approve)
    merged, ids = entries([r for r in rows if r["link"] == link], which, lines)
    if not merged:
        print(f"\nNothing to merge for {per[link]['name'] or link}: every answer is in the ledger already.")
        return 0
    for e in merged:
        review.record(e)
    path = OUT / f"merge-{which}-{stamp}.sql"
    path.write_text(merge_sql(ids, merged, lines + merged), encoding="utf-8", newline="\n")
    print(f"\nAppended {len(merged)} line(s) to {review.LEDGER.as_posix()}, by "
          f"{'hand' if per[link]['role'] == 'owner' else 'link:' + link}.")
    try:
        wrangler(db, file=path)
    except (RuntimeError, SystemExit, subprocess.SubprocessError) as e:
        print(f"They are in the ledger and NOT yet marked merged in the database ({e}). Run "
              f"`npx wrangler d1 execute {db} --remote --file {path.as_posix()}` to finish; a second "
              "--approve appends none of them twice.")
        return 1
    print(f"Marked merged in {db}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
