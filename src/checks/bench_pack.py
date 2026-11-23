#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.5
"""
A pack for the shared bench: what its contributors are asked next, as SQL to
load into its database with one wrangler command.

    python3 src/checks/bench_pack.py --preview            # a pack for the preview's database
    python3 src/checks/bench_pack.py                       # ... for production's
    python3 src/checks/bench_pack.py --refresh --preview   # the three pools drawn again first
    python3 src/checks/bench_pack.py --refresh --tags reports/tags.draft.json --preview
                                                           # ... the tags from a draft registry
    python3 src/checks/bench_pack.py --groups 3 --seed 7   # more groups; another draw
    python3 src/checks/bench_pack.py --queues tag,topic --groups-of tag=all
                                                           # only those queues; every tag
    python3 src/checks/bench_pack.py --pools P --ledger L --out O
                                                           # pools, ledger and packs elsewhere

Writes reports/bench/packs/<preview|production>/<date>.sql (or into --out) and
prints the wrangler command that loads it. Asks nobody and runs nothing: the
owner loads it. Reads review.py's own sample pools (review/.pool-<kind>.json,
or in --pools, cached; with --refresh, drawn again by review.py's own samplers
from the data on disk, a draw that comes back empty leaving the cached pool as
it was), the ledger (review/checked.jsonl, or the copy --ledger names, through
bench_ledger), data/bills.json and the bills' texts (tag_rules.load_bills) for
titles and the drafters' analyses, and data/subjects.json for the list a
better topic is chosen from.

WHAT A PACK HOLDS (the design of 17 November 2026, approved):

  timings   hearing timings, start and end: the timestamp pool, drawn as one
            queue (the "older" pool is its pre-2025 part, so no key is asked
            twice), 50 to a group, a year a group, newest first; an item
            before 2025 goes to the ledger as "older", else "timestamp"
  topics    a topic the model placed (not Miscellaneous, which needs a
            choose-one card, later), 50 to a group, a term a group, newest
            first; a No may choose a better one from the site's list
  tags      one bill at a time, a tag a group (its title, analysis-or-chapter
            and possible-miss samples, up to its 30), in the registry's
            order, asked blind: the card never says how the rule attached it

  Each group is a seeded draw (--seed), as the related bills' strata are, so
  the same pools, ledger and earlier packs give the same pack. It leaves out
  every key already in the ledger, whoever judged it, and every key an
  earlier pack for the same database holds (read off their "-- keys:"
  lines), so nothing is asked twice.

  WHICH QUEUES, HOW MANY GROUPS: two groups of each queue unless --groups
  says otherwise, and --groups-of QUEUE=N (a number, or all) for one queue;
  --queues draws only the queues it names, reads only their pools and writes
  only their rows, and leaves the others in the database as they are.

  A LATER PACK FOLLOWS THE EARLIER ONES (23 November 2026). The bench serves
  an item by its order (store.js claimOne, ORDER BY ord), and every pack
  numbered its own from 0, so a second pack's items came between the first's.
  Now each item's and group's order starts from PACK_BASE times the number of
  earlier packs for that database (the folder's packs, read as packed_keys
  reads them), so a new pack is served after everything loaded before it,
  group by group. A calibration item's order is its own, as before.

  CALIBRATION: every item the owner judged herself that a contributor's card
  can show (a timing graded against a published time, a placed topic, a
  tag's single-bill sample), with which way she went, built from what she
  was shown. The bench gives a contributor one in 25 (store.js
  CALIB_EVERY), never one that link has answered, and keeps the answer
  beside hers; it is never merged.

  HOW FAR ALONG: each queue's whole pool and how many of it the ledger has
  judged, as of the pack.

  JUDGED ON THE LAPTOP SINCE: an item packed before and judged by her on the
  laptop's bench since is marked "elsewhere", and no longer asked.

Writes the pack file and nothing else; never the ledger, and only the pools'
own cache, when --refresh draws a pool that is not empty -- in review/, or in
the folder --pools names, so that a draw in a scratch tree with a copy of the
ledger writes nothing in the owner's review/.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import random
import re
from datetime import datetime, timezone

import bench_ledger as BL

DB = {"production": "graniterecord-bench", "preview": "graniterecord-bench-preview"}
OUT = Path("reports") / "bench" / "packs"
SEED = 20261117
PER = {"timing": 50, "topic": 50, "tag": 30}
QUEUES = {"timing": "Hearing times", "topic": "Topics", "tag": "Tags"}
ORDER = ["timing", "topic", "tag"]
# The pool each queue is drawn from (review.py's kinds).
POOL_OF = {"timing": "timestamp", "topic": "topic", "tag": "tag"}
# A pack's items are numbered from this times the earlier packs for its database, so a
# later pack is served after every earlier one; within a pack, a group's items from
# 1,000 times its place among its queue's groups.
PACK_BASE = 1_000_000
GROUP_SPAN = 1000
# The ledger's kinds each queue's keys are judged under.
JUDGED_AS = {"timing": ("timestamp", "older", "late"), "topic": ("topic",), "tag": ("tag",)}
CLAIMS = {"yes": "correct", "no": "wrong", "unsure": "unsure"}
TAGS = {"yes": "yes", "no": "no", "unsure": "unsure"}
BODY_MOST = 3000          # characters of an analysis on a card
STATEMENT_MOST = 90_000   # bytes of one statement; D1's own limit is 100 KB
ANALYSIS = "The drafters’ analysis"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


# ---- what a card says ---------------------------------------------------------------

def bill_label(bill):
    """HB1062 -> HB 1062."""
    m = re.match(r"^([A-Z]+)(\d+)$", str(bill or ""))
    return f"{m.group(1)} {m.group(2)}" if m else str(bill or "")


def long_date(day):
    """2026-02-03 -> 3 February 2026."""
    m = re.match(r"^(\d{4})-(\d\d)-(\d\d)$", str(day or ""))
    return f"{int(m.group(3))} {MONTHS[int(m.group(2)) - 1]} {m.group(1)}" if m else str(day or "")


def bill_term(year):
    """The term a bill's page year is in (terms.term_of_year, the one home of the rule), or ""."""
    import terms
    try:
        return terms.term_of_year(str(year))
    except ValueError:
        return ""


def cut(text, most=BODY_MOST):
    t = str(text or "").strip()
    return t if len(t) <= most else t[:most - 1].rstrip() + "…"


def moment_card(it, title=""):
    """A timing: the recording, and a step for each published time."""
    bill = bill_label(it.get("bill"))
    proc = str(it.get("proceeding") or "")
    floor = "floor" in proc.lower()
    meta = " · ".join(x for x in (str(it.get("committee") or ""), long_date(it.get("date"))) if x)

    def step(field, at):
        if field == "end":
            return {"field": "end", "at": round(float(at), 1), "label": "the end",
                    "q": f"Does {bill} end at {{t}}?", "mark": "Mark end", "lost": "Can’t find it",
                    "find": f"Play or skip to where {bill} really ends, then mark it. The site said {{t}}."}
        return {"field": "start", "at": round(float(at), 1), "label": "the start",
                "q": (f"Is {bill} taken up at {{t}}?" if floor else f"Does the chair open {bill} at {{t}}?"),
                "mark": "Mark start", "lost": "Can’t find it",
                "find": (f"Play or skip to where {bill} is really taken up, then mark it. The site said {{t}}."
                         if floor else
                         f"Play or skip to where the chair really opens {bill}, then mark it. The site said {{t}}.")}
    steps = [step("start", it["start"])] + ([step("end", it["end"])] if it.get("end") is not None else [])
    return {"type": "moment", "head": f"{bill} · {proc}", "meta": meta, "title": title, "what": proc,
            "player": {"host": "youtube", "id": it["video_id"]}, "steps": steps, "words": CLAIMS}


def topic_card(it, analysis=""):
    """A placed topic: the bill, and whether its topic is a fair one."""
    return {"type": "claim", "head": f"{bill_label(it.get('bill'))} · {it.get('term')}",
            "title": str(it.get("title") or ""), "what": "topic", "label": ANALYSIS, "body": cut(analysis),
            "q": "Is {claim} a fair topic for it?", "claim": str(it.get("topic") or ""), "words": CLAIMS,
            "better": {"field": "better_topic", "label": "A better topic? (if you know one)",
                       "none": "Leave it — just say No", "from": "The site’s own list of topics."}}


def tag_card(it):
    """One bill and one tag, asked blind: nothing says how the rule attached it."""
    chapters = ", ".join("RSA " + c for c in it.get("chapters") or [])
    label, body = ((ANALYSIS, cut(it.get("analysis"))) if it.get("analysis") else
                   ("The laws it amends", chapters) if chapters else ("", ""))
    return {"type": "claim", "head": f"{bill_label(it.get('bill'))} · {it.get('term')}",
            "title": str(it.get("title") or ""), "what": "tag", "label": label, "body": body,
            "q": "Is this bill about {claim}?", "claim": str(it.get("tag_name") or ""),
            "def": str(it.get("definition") or ""), "words": TAGS}


# ---- the draw -----------------------------------------------------------------------

def timing_kind(it):
    """The ledger's kind for a timing: "older" before 2025, as review.py's pools split it."""
    return "older" if str(it.get("date") or "9999")[:4] < "2025" else "timestamp"


def _sample(rng_key, candidates, n):
    """`n` of `candidates`, a seeded draw, in a fixed order of their keys."""
    pop = sorted(candidates, key=lambda x: x["key"])
    return random.Random(rng_key).sample(pop, min(n, len(pop)))


def draw(pools, ledger, info, packed=(), seed=SEED, groups=2, per=None, as_of="", queues=None,
         groups_of=None, base=0):
    """The pack, as rows: {"queues", "groups", "items", "calib", "elsewhere", "keys"}.

    pools      {"timestamp": [...], "topic": [...], "tag": [...]}, review.py's items
    ledger     the ledger's lines (bench_ledger.read)
    info       title(term, bill) and analysis(term, bill), each "" when unknown,
               and options() the better topic's list
    packed     ("kind\\tkey") of earlier packs for the same database
    groups     how many groups of each queue; groups_of {queue: n, or None for all}
               for one queue
    queues     the queues drawn (default every one): a queue left out has no row,
               no group, no item and no calibration item in the pack
    base       where the pack's items and groups are numbered from: PACK_BASE
               times the earlier packs for its database (pack_files)
    """
    per = {**PER, **(per or {})}
    want = [q for q in ORDER if queues is None or q in queues]
    many = {q: (groups_of or {}).get(q, groups) for q in ORDER}
    lines = BL.judgments(ledger)
    judged = {}
    for d in lines:
        judged.setdefault(d.get("kind"), set()).add(d.get("key"))
    done = {q: set().union(*(judged.get(k, set()) for k in JUDGED_AS[q])) for q in ORDER}
    packed = set(packed)
    out = {"queues": [], "groups": [], "items": [], "calib": [], "elsewhere": [], "keys": [], "as_of": as_of}

    timing_pool = pools.get("timestamp") or []
    topic_pool = pools.get("topic") or []
    tag_pool = pools.get("tag") or []
    pool_of = {"timing": timing_pool, "topic": topic_pool, "tag": tag_pool}
    for i, q in enumerate(ORDER):
        if q not in want:
            continue
        keys = {it["key"] for it in pool_of[q]}
        out["queues"].append({"queue": q, "label": QUEUES[q], "pool": len(keys),
                              "judged": len(keys & done[q]), "as_of": as_of,
                              "options": info.options() if q == "topic" else None, "ord": i})

    def fresh(q, it, kind):
        return it["key"] not in done[q] and f"{kind}\t{it['key']}" not in packed

    # Each queue's groups, in their order: (group id, label, [(kind, item, card)]).
    plans = {q: [] for q in ORDER}
    by_year = {}
    for it in timing_pool if "timing" in want else ():
        if it.get("start") is None or not it.get("video_id"):
            continue
        if fresh("timing", it, timing_kind(it)):
            by_year.setdefault(str(it.get("date") or "")[:4], []).append(it)
    for year in sorted((y for y in by_year if y), reverse=True)[:many["timing"]]:
        got = _sample(f"{seed}|timing|{year}", by_year[year], per["timing"])
        plans["timing"].append((f"timing|{year}", f"{year} recordings",
                                [(timing_kind(it), it, moment_card(
                                    it, info.title(bill_term(it.get("year")), it.get("bill")))) for it in got]))
    by_term = {}
    for it in topic_pool if "topic" in want else ():
        if (it.get("topic") or "Miscellaneous") == "Miscellaneous":
            continue
        if fresh("topic", it, "topic"):
            by_term.setdefault(str(it.get("term") or ""), []).append(it)
    for term in sorted((t for t in by_term if t), reverse=True)[:many["topic"]]:
        got = _sample(f"{seed}|topic|{term}", by_term[term], per["topic"])
        plans["topic"].append((f"topic|{term}", f"Bills of {term}",
                               [("topic", it, topic_card(it, info.analysis(term, it.get("bill")))) for it in got]))
    by_tag = {}
    for it in tag_pool if "tag" in want else ():
        if it.get("sample") not in ("title", "other", "miss"):
            continue
        if fresh("tag", it, "tag"):
            by_tag.setdefault(it.get("tag"), []).append(it)
    for tid in sorted(by_tag, key=lambda t: min(x.get("order", 0) for x in by_tag[t]))[:many["tag"]]:
        got = _sample(f"{seed}|tag|{tid}", by_tag[tid], per["tag"])
        plans["tag"].append((f"tag|{tid}", str(got[0].get("tag_name") or tid),
                             [("tag", it, tag_card(it)) for it in got]))

    for q in ORDER:
        for gi, (grp, label, rows) in enumerate(plans[q]):
            if len(rows) > GROUP_SPAN or (gi + 1) * GROUP_SPAN > PACK_BASE:
                raise SystemExit(f"{QUEUES[q]}: {len(plans[q])} groups of up to {len(rows)} items do not fit "
                                 f"one pack's numbering ({PACK_BASE:,} places, {GROUP_SPAN:,} a group)")
            out["groups"].append({"grp": grp, "queue": q, "label": label, "ord": base + gi})
            for i, (kind, it, card) in enumerate(rows):
                out["items"].append({"kind": kind, "key": it["key"], "queue": q, "grp": grp,
                                     "ord": base + gi * GROUP_SPAN + i, "card": card, "shown": it})
                out["keys"].append(f"{kind}\t{it['key']}")

    # CALIBRATION: what the owner judged and a contributor's card can show. Shuffled as
    # one list whatever is drawn, so a calibration item's order is the same in a pack
    # of some queues as in a pack of all three; a card is made only for a queue drawn.
    mine = {}
    for d in lines:
        if BL.who(d) == "hand":
            mine[(d.get("kind"), d.get("key"))] = d
    cal = []
    for (kind, key), d in mine.items():
        shown, verdict = d.get("shown") or {}, d.get("verdict")
        if kind in ("timestamp", "older"):
            if verdict not in ("correct", "wrong") or shown.get("start") is None or not shown.get("video_id"):
                continue
            q = "timing"
        elif kind == "topic":
            if verdict not in ("correct", "wrong") or (shown.get("topic") or "Miscellaneous") == "Miscellaneous":
                continue
            q = "topic"
        elif kind == "tag":
            if verdict not in ("yes", "partly", "no") or shown.get("sample") not in ("title", "other", "miss"):
                continue
            q = "tag"
        else:
            continue
        cal.append({"kind": kind, "key": key, "queue": q, "shown": shown,
                    "hers": "yes" if verdict in ("correct", "yes", "partly") else "no"})
    for i, c in enumerate(_sample(f"{seed}|calib", cal, len(cal))):
        if c["queue"] not in want:
            continue
        shown = c.pop("shown")
        card = (moment_card(shown, info.title(bill_term(shown.get("year")), shown.get("bill")))
                if c["queue"] == "timing" else
                topic_card(shown, info.analysis(shown.get("term"), shown.get("bill")))
                if c["queue"] == "topic" else tag_card(shown))
        out["calib"].append({"kind": c["kind"], "key": c["key"], "queue": c["queue"], "card": card,
                             "hers": c["hers"], "ord": i})

    # Packed before, judged on the laptop since: asked no more.
    for k in sorted(packed):
        kind, _, key = k.partition("\t")
        if key in judged.get(kind, set()):
            out["elsewhere"].append((kind, key))
    return out


# ---- the SQL ------------------------------------------------------------------------

def q(v):
    """A SQL value: NULL, a number, or a string quoted."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def j(v):
    return q(json.dumps(v, ensure_ascii=False, separators=(",", ":")))


def to_sql(pack, name, db, path, seed, sources):
    """The pack as statements, with a header that says what it is and how to load it."""
    out = [f"-- A pack for the shared bench (src/checks/bench_pack.py), for {db}.",
           f"-- Drawn {pack['as_of']} with seed {seed}, from: {sources}.",
           f"-- {len(pack['items'])} items in {len(pack['groups'])} groups, {len(pack['calib'])} calibration items, "
           f"{len(pack['elsewhere'])} judged on the laptop since they were packed.",
           "-- Load it with:",
           f"--   npx wrangler d1 execute {db} --remote --file {Path(path).as_posix()}",
           "-- keys: " + json.dumps(pack["keys"], ensure_ascii=True), ""]
    for r in pack["queues"]:
        out.append("INSERT INTO queues (queue, label, pool, judged, as_of, options, ord) VALUES ("
                   f"{q(r['queue'])}, {q(r['label'])}, {r['pool']}, {r['judged']}, {q(r['as_of'])}, "
                   f"{j(r['options']) if r['options'] is not None else 'NULL'}, {r['ord']}) "
                   "ON CONFLICT(queue) DO UPDATE SET label = excluded.label, pool = excluded.pool, "
                   "judged = excluded.judged, as_of = excluded.as_of, options = excluded.options, "
                   "ord = excluded.ord;")
    for r in pack["groups"]:
        out.append(f"INSERT INTO groups (grp, queue, label, ord) VALUES ({q(r['grp'])}, {q(r['queue'])}, "
                   f"{q(r['label'])}, {r['ord']}) ON CONFLICT(grp) DO UPDATE SET label = excluded.label;")
    for r in pack["items"]:
        out.append("INSERT OR IGNORE INTO items (kind, key, queue, pack, grp, ord, card, shown) VALUES ("
                   f"{q(r['kind'])}, {q(r['key'])}, {q(r['queue'])}, {q(name)}, {q(r['grp'])}, {r['ord']}, "
                   f"{j(r['card'])}, {j(r['shown'])});")
    for r in pack["calib"]:
        out.append("INSERT INTO calib (kind, key, queue, card, hers, ord) VALUES ("
                   f"{q(r['kind'])}, {q(r['key'])}, {q(r['queue'])}, {j(r['card'])}, {q(r['hers'])}, {r['ord']}) "
                   "ON CONFLICT(kind, key) DO UPDATE SET card = excluded.card, hers = excluded.hers, "
                   "ord = excluded.ord;")
    for kind, key in pack["elsewhere"]:
        out.append(f"UPDATE items SET state = 'elsewhere', held_by = NULL, held_until = NULL "
                   f"WHERE kind = {q(kind)} AND key = {q(key)} AND state = 'open';")
    long = [s[:80] for s in out if len(s.encode("utf-8")) > STATEMENT_MOST]
    if long:
        raise SystemExit(f"{len(long)} statement(s) over {STATEMENT_MOST:,} bytes, which D1 refuses: {long[0]}")
    return "\n".join(out) + "\n"


def pack_files(folder):
    """[(path, keys)] of every earlier pack in `folder`, in the order of their names: each
    .sql file whose first lines carry its "-- keys:" line, with the "kind\\tkey" it holds."""
    out = []
    for p in sorted(Path(folder).glob("*.sql")):
        keys = [json.loads(line[len("-- keys: "):]) for line in p.read_text(encoding="utf-8").splitlines()[:12]
                if line.startswith("-- keys: ")]
        if keys:
            out.append((p, [k for ks in keys for k in ks]))
    return out


def packed_keys(folder):
    """("kind\\tkey") of every earlier pack in `folder`, read off its "-- keys:" line."""
    return {k for _p, keys in pack_files(folder) for k in keys}


# ---- the data on disk ----------------------------------------------------------------

def read_pool(kind, refresh=False, folder=None):
    """review.py's pool of `kind`: its cache, read and never written; with
    `refresh`, drawn again by review.py's own sampler and kept in that cache
    as review.pool_for keeps it -- BUT A DRAW THAT COMES BACK EMPTY LEAVES THE
    CACHE AS IT WAS. pool_for deletes the cache then, and the tag pool comes
    back empty whenever the tag registry is not found: corrections/tags.json
    is not on the laptop, and the owner draws tags from a draft named by
    --tags (GRANITE_TAGS), so a refresh without it would have thrown her tag
    pool away. The cache is review.py's own (review/.pool-<kind>.json), or
    the same name in `folder` (--pools), read there and written there alone."""
    import review
    p = (Path(folder) if folder else review.OUT) / f".pool-{kind}.json"
    if refresh:
        items = review.KINDS[kind]["sample"]()
        if items:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(items), encoding="utf-8")
            return items
        print(f"  {kind}: drawn again and empty"
              + (" (no tag registry: pass --tags with the draft review.py --tags reads)" if kind == "tag" else "")
              + "; the pool kept from before is used", file=sys.stderr)
    if not p.exists():
        raise SystemExit(f"{p.as_posix()} is not here: run with --refresh to draw the pools")
    return json.loads(p.read_text(encoding="utf-8"))


class Info:
    """A bill's title and the drafters' analysis, read once and only if asked."""

    def __init__(self, root="."):
        self.root = Path(root)
        self._titles = None
        self._analyses = None

    def title(self, term, bill):
        if self._titles is None:
            import topic_model as TM
            bills = json.loads((self.root / "data" / "bills.json").read_text(encoding="utf-8"))
            self._titles = {(t, b): TM.NEWTITLE.sub("", (r or {}).get("title") or "")
                            for t, byb in bills.items() if isinstance(byb, dict) for b, r in byb.items()}
        return self._titles.get((term, bill), "")

    def analysis(self, term, bill):
        if self._analyses is None:
            import tag_rules as TR
            self._analyses = {(b["term"], b["bill"]): b["analysis"] for b in TR.load_bills(self.root)}
        return self._analyses.get((term, bill), "")

    def options(self):
        import review
        return review.topic_options()


def queues_named(text):
    """The queues --queues names (comma-separated), in the pack's order; every one when
    it names none."""
    if text is None:
        return list(ORDER)
    got = [x.strip() for x in str(text).split(",") if x.strip()]
    bad = [x for x in got if x not in ORDER]
    if bad or not got:
        raise SystemExit(f"--queues {text!r}: name one or more of {', '.join(ORDER)}, with commas between")
    return [q for q in ORDER if q in got]


def groups_named(given, queues):
    """{queue: n, or None for all} from --groups-of QUEUE=N, each a queue drawn and N a
    number of groups or "all"."""
    out = {}
    for s in given or ():
        q, sep, n = str(s).partition("=")
        q, n = q.strip(), n.strip()
        if not sep or q not in ORDER:
            raise SystemExit(f"--groups-of {s!r}: write QUEUE=N, QUEUE one of {', '.join(ORDER)}")
        if q not in queues:
            raise SystemExit(f"--groups-of {s!r}: {q} is not drawn (--queues {','.join(queues)})")
        if n == "all":
            out[q] = None
        elif n.isdigit() and int(n) > 0:
            out[q] = int(n)
        else:
            raise SystemExit(f"--groups-of {s!r}: N is a number of groups, 1 or more, or all")
    return out


def main():
    ap = argparse.ArgumentParser(description="A pack for the shared bench, as SQL for wrangler to load.")
    ap.add_argument("--preview", action="store_true", help="a pack for the preview's database")
    ap.add_argument("--groups", type=int, default=2, help="groups of each queue (default 2)")
    ap.add_argument("--groups-of", action="append", default=[], metavar="QUEUE=N",
                    help="groups of one queue, N a number or all, in place of --groups for it (again for another)")
    ap.add_argument("--queues", default=None, metavar="Q,Q",
                    help="draw only these queues, of timing, topic, tag (default all three)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--refresh", action="store_true", help="draw review.py's pools again first")
    ap.add_argument("--tags", help="the tag registry to draw tags from (a draft in reports/), as "
                                   "review.py --tags takes it, where corrections/tags.json is not")
    ap.add_argument("--pools", default=None, metavar="DIR",
                    help="where review.py's pool caches are read, and with --refresh written (default review/)")
    ap.add_argument("--ledger", default=None, metavar="FILE",
                    help="the ledger to read, such as a copy (default review/checked.jsonl)")
    ap.add_argument("--out", default=None, help="the folder for packs (default reports/bench/packs/<db>)")
    a = ap.parse_args()
    if a.groups < 1:
        raise SystemExit("--groups is a number of groups, 1 or more")
    queues = queues_named(a.queues)
    groups_of = groups_named(a.groups_of, queues)
    if a.tags:
        import os
        os.environ["GRANITE_TAGS"] = a.tags
    which = "preview" if a.preview else "production"
    db = DB[which]
    folder = Path(a.out) if a.out else OUT / which
    pools = {POOL_OF[q]: read_pool(POOL_OF[q], a.refresh, a.pools) for q in queues}
    ledger_path = Path(a.ledger) if a.ledger else BL.LEDGER
    if a.ledger and not ledger_path.is_file():
        raise SystemExit(f"--ledger {a.ledger}: no such file")
    ledger = BL.read(ledger_path)
    earlier = pack_files(folder) if folder.is_dir() else []
    base = len(earlier) * PACK_BASE
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pack = draw(pools, ledger, Info("."), {k for _p, keys in earlier for k in keys}, a.seed, a.groups,
                as_of=as_of, queues=queues, groups_of=groups_of, base=base)
    folder.mkdir(parents=True, exist_ok=True)
    day = as_of[:10]
    path = folder / f"{day}.sql"
    n = 2
    while path.exists():
        path = folder / f"{day}-{n}.sql"
        n += 1
    where = Path(a.pools).as_posix() if a.pools else "review"
    sources = ", ".join(f"{where}/.pool-{k}.json ({len(v):,})" for k, v in pools.items()) + \
        (f", the ledger ({len(ledger):,} lines)" if not a.ledger else
         f", the ledger's copy {ledger_path.as_posix()} ({len(ledger):,} lines)")
    path.write_text(to_sql(pack, path.stem, db, path, a.seed, sources), encoding="utf-8", newline="\n")
    print(f"{path.as_posix()}: {len(pack['items'])} items for {db}")
    print(f"  served after the items of the {len(earlier)} earlier pack(s) in {folder.as_posix()}"
          if earlier else f"  the first pack in {folder.as_posix()}")
    for r in pack["groups"]:
        n = sum(1 for x in pack["items"] if x["grp"] == r["grp"])
        print(f"  {QUEUES[r['queue']]:14} {r['label']:40} {n:3}")
    print(f"  {len(pack['calib'])} calibration items (one in 25 a contributor is given); "
          f"{len(pack['elsewhere'])} judged on the laptop since an earlier pack")
    for r in pack["queues"]:
        print(f"  how far along: {r['label']:14} {r['judged']:,} of {r['pool']:,}")
    print("Load it with:")
    print(f"  npx wrangler d1 execute {db} --remote --file {path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
