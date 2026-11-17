#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.1
"""
A pack for the shared bench: what its contributors are asked next, as SQL to
load into its database with one wrangler command.

    python3 src/checks/bench_pack.py --preview            # a pack for the preview's database
    python3 src/checks/bench_pack.py                       # ... for production's
    python3 src/checks/bench_pack.py --refresh --preview   # the three pools drawn again first
    python3 src/checks/bench_pack.py --groups 3 --seed 7   # more groups; another draw

Writes reports/bench/packs/<preview|production>/<date>.sql and prints the
wrangler command that loads it. Asks nobody and runs nothing: the owner loads
it. Reads review.py's own sample pools (review/.pool-<kind>.json, cached; with
--refresh, review.pool_for draws them again from the data on disk), the
ledger (review/checked.jsonl, through bench_ledger), data/bills.json and the
bills' texts (tag_rules.load_bills) for titles and the drafters' analyses,
and data/subjects.json for the list a better topic is chosen from.

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

Writes the pack file and nothing else; never the ledger, never review/ but
through review.pool_for's own cache when --refresh asks for it.
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


def term_of(year):
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


def draw(pools, ledger, info, packed=(), seed=SEED, groups=2, per=None, as_of=""):
    """The pack, as rows: {"queues", "groups", "items", "calib", "elsewhere", "keys"}.

    pools   {"timestamp": [...], "topic": [...], "tag": [...]}, review.py's items
    ledger  the ledger's lines (bench_ledger.read)
    info    title(term, bill) and analysis(term, bill), each "" when unknown,
            and options() the better topic's list
    packed  ("kind\\tkey") of earlier packs for the same database
    """
    per = {**PER, **(per or {})}
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
        keys = {it["key"] for it in pool_of[q]}
        out["queues"].append({"queue": q, "label": QUEUES[q], "pool": len(keys),
                              "judged": len(keys & done[q]), "as_of": as_of,
                              "options": info.options() if q == "topic" else None, "ord": i})

    def fresh(q, it, kind):
        return it["key"] not in done[q] and f"{kind}\t{it['key']}" not in packed

    # Each queue's groups, in their order: (group id, label, [(kind, item, card)]).
    plans = {q: [] for q in ORDER}
    by_year = {}
    for it in timing_pool:
        if it.get("start") is None or not it.get("video_id"):
            continue
        if fresh("timing", it, timing_kind(it)):
            by_year.setdefault(str(it.get("date") or "")[:4], []).append(it)
    for year in sorted((y for y in by_year if y), reverse=True)[:groups]:
        got = _sample(f"{seed}|timing|{year}", by_year[year], per["timing"])
        plans["timing"].append((f"timing|{year}", f"{year} recordings",
                                [(timing_kind(it), it, moment_card(
                                    it, info.title(term_of(it.get("year")), it.get("bill")))) for it in got]))
    by_term = {}
    for it in topic_pool:
        if (it.get("topic") or "Miscellaneous") == "Miscellaneous":
            continue
        if fresh("topic", it, "topic"):
            by_term.setdefault(str(it.get("term") or ""), []).append(it)
    for term in sorted((t for t in by_term if t), reverse=True)[:groups]:
        got = _sample(f"{seed}|topic|{term}", by_term[term], per["topic"])
        plans["topic"].append((f"topic|{term}", f"Bills of {term}",
                               [("topic", it, topic_card(it, info.analysis(term, it.get("bill")))) for it in got]))
    by_tag = {}
    for it in tag_pool:
        if it.get("sample") not in ("title", "other", "miss"):
            continue
        if fresh("tag", it, "tag"):
            by_tag.setdefault(it.get("tag"), []).append(it)
    for tid in sorted(by_tag, key=lambda t: min(x.get("order", 0) for x in by_tag[t]))[:groups]:
        got = _sample(f"{seed}|tag|{tid}", by_tag[tid], per["tag"])
        plans["tag"].append((f"tag|{tid}", str(got[0].get("tag_name") or tid),
                             [("tag", it, tag_card(it)) for it in got]))

    for q in ORDER:
        for gi, (grp, label, rows) in enumerate(plans[q]):
            out["groups"].append({"grp": grp, "queue": q, "label": label, "ord": gi})
            for i, (kind, it, card) in enumerate(rows):
                out["items"].append({"kind": kind, "key": it["key"], "queue": q, "grp": grp,
                                     "ord": gi * 1000 + i, "card": card, "shown": it})
                out["keys"].append(f"{kind}\t{it['key']}")

    # CALIBRATION: what the owner judged and a contributor's card can show.
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
            card = moment_card(shown, info.title(term_of(shown.get("year")), shown.get("bill")))
            q = "timing"
        elif kind == "topic":
            if verdict not in ("correct", "wrong") or (shown.get("topic") or "Miscellaneous") == "Miscellaneous":
                continue
            card, q = topic_card(shown, info.analysis(shown.get("term"), shown.get("bill"))), "topic"
        elif kind == "tag":
            if verdict not in ("yes", "partly", "no") or shown.get("sample") not in ("title", "other", "miss"):
                continue
            card, q = tag_card(shown), "tag"
        else:
            continue
        cal.append({"kind": kind, "key": key, "queue": q, "card": card,
                    "hers": "yes" if verdict in ("correct", "yes", "partly") else "no"})
    for i, c in enumerate(_sample(f"{seed}|calib", cal, len(cal))):
        out["calib"].append({**c, "ord": i})

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


def packed_keys(folder):
    """("kind\\tkey") of every earlier pack in `folder`, read off its "-- keys:" line."""
    keys = set()
    for p in sorted(Path(folder).glob("*.sql")):
        for line in p.read_text(encoding="utf-8").splitlines()[:12]:
            if line.startswith("-- keys: "):
                keys.update(json.loads(line[len("-- keys: "):]))
    return keys


# ---- the data on disk ----------------------------------------------------------------

def read_pool(kind, refresh=False):
    """review.py's pool of `kind`: its cache, read and never written; with
    `refresh`, review.pool_for draws it again (and keeps its cache, as the
    laptop's bench does)."""
    import review
    if refresh:
        return review.pool_for(kind, refresh=True)
    p = review.OUT / f".pool-{kind}.json"
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


def main():
    ap = argparse.ArgumentParser(description="A pack for the shared bench, as SQL for wrangler to load.")
    ap.add_argument("--preview", action="store_true", help="a pack for the preview's database")
    ap.add_argument("--groups", type=int, default=2, help="groups of each queue (default 2)")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--refresh", action="store_true", help="draw review.py's three pools again first")
    ap.add_argument("--out", default=None, help="the folder for packs (default reports/bench/packs/<db>)")
    a = ap.parse_args()
    which = "preview" if a.preview else "production"
    db = DB[which]
    folder = Path(a.out) if a.out else OUT / which
    pools = {k: read_pool(k, a.refresh) for k in ("timestamp", "topic", "tag")}
    as_of = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    pack = draw(pools, BL.read(BL.LEDGER), Info("."), packed_keys(folder), a.seed, a.groups, as_of=as_of)
    folder.mkdir(parents=True, exist_ok=True)
    day = as_of[:10]
    path = folder / f"{day}.sql"
    n = 2
    while path.exists():
        path = folder / f"{day}-{n}.sql"
        n += 1
    sources = ", ".join(f"review/.pool-{k}.json ({len(v):,})" for k, v in pools.items()) + \
        f", the ledger ({len(BL.read(BL.LEDGER)):,} lines)"
    path.write_text(to_sql(pack, path.stem, db, path, a.seed, sources), encoding="utf-8", newline="\n")
    print(f"{path.as_posix()}: {len(pack['items'])} items for {db}")
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
