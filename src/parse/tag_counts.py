#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.3
"""Counts and samples for the tag registry, so the design's numbers can be redone.

    python3 src/parse/tag_counts.py --root D:/nh --registry reports/tags.draft.json --out D:/nh/reports

Writes, into --out (reports/, which git ignores and nothing commits):

    tags_counts.json   per tag: bills by term and by tier, bills that gain a topic
                       they never had (the "Miscellaneous" ones); and the whole
                       run: bills tagged by title alone, by any tier, tags per
                       bill, the bills over the guide of five
    tags_counts.md     the same as a table to read
    tags_samples.json  per tag the bench's samples (below), so the owner can read
                       what the bench will show before sitting down to it

THE SAMPLES (design 4.4), drawn by a seeded generator so the same registry and
the same bills give the same draw: per tag 10 bills the title attaches and 10
that only the analysis or a dedicated chapter attaches, each set spread over
the three eras (1989-1998, 1999-2012, 2013-2026); 10 bills the tag does not
carry whose full text names its core words three or more times, with the
sentences ("might have been missed"); and the tag's opposite-aim pair.

NOTHING HERE JUDGES. A sample is a list of bills for a person to read; the
bench (src/checks/review.py, kind "tag") puts them in front of one and appends
what they say to review/checked.jsonl. No machine's opinion enters it.

Reads data/bills.json, the two text files and topics_assigned.json under
--root (default: the repository). No network, no writes outside --out.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import collections
import json
import random
import re

import tag_rules as TR

PER_TIER = 10
PER_MISS = 10
MISS_MENTIONS = 3
ERAS = (("1989-1998", 1989, 1998), ("1999-2012", 1999, 2012), ("2013-2026", 2013, 2026))
TEXT_LIMIT = 80000


def era_of(term):
    y = int(term[:4])
    return next(name for name, lo, hi in ERAS if lo <= y <= hi)


def key_of(b):
    return f"{b['term']}/{b['bill']}"


def is_none(topic):
    return not topic or topic == "Miscellaneous"


# ------------------------------------------------------------------ counting

def count(rules, bills, reg):
    """The counts of a run, and every bill's result keyed term/bill."""
    results = TR.tag_all(rules, bills)
    by_tag = {tid: {"name": reg[tid].get("name"), "title": 0, "any": 0, "ta": 0, "best": {"T": 0, "A": 0, "R": 0},
                    "gained_a_topic": 0, "dropped_for_topic": 0, "by_term": {}}
              for tid in rules}
    per_bill = collections.Counter()
    title_bills = any_bills = 0
    over = []
    for b in bills:
        r = results[key_of(b)]
        n = len(r["tags"])
        per_bill[n] += 1
        any_bills += bool(n)
        title_bills += any("T" in v["fired"] for v in r["tags"].values())
        if n > TR.GUIDE_TAGS:
            over.append({"bill": key_of(b), "n": n, "tags": list(r["tags"]), "title": b["title"][:120]})
        for tid, v in r["tags"].items():
            row = by_tag[tid]
            row["any"] += 1
            if "T" in v["fired"] or "A" in v["fired"]:
                row["ta"] += 1
            row["best"][v["tier"]] += 1
            t = row["by_term"].setdefault(b["term"], {"T": 0, "any": 0})
            t["any"] += 1
            if "T" in v["fired"]:
                row["title"] += 1
                t["T"] += 1
            if is_none(b.get("topic")):
                row["gained_a_topic"] += 1
        for tid in r["dropped"]:
            by_tag[tid]["dropped_for_topic"] += 1
    over.sort(key=lambda x: (-x["n"], x["bill"]))
    under = [{"id": tid, "name": r["name"], "title_and_analysis": r["ta"], "any": r["any"],
              "keep_small": reg[tid].get("keep_small") or ""}
             for tid, r in by_tag.items() if r["ta"] < TR.MIN_BILLS]
    return results, {
        "threshold_bills_title_and_analysis": TR.MIN_BILLS, "tags_under_threshold": under,
        "bills": len(bills), "bills_title_tier": title_bills, "bills_any_tier": any_bills,
        "bills_over_guide": len(over), "guide": TR.GUIDE_TAGS,
        "bills_with_no_topic_that_gain_a_tag": sum(
            1 for b in bills if is_none(b.get("topic")) and results[key_of(b)]["tags"]),
        "tags_per_bill": {str(k): v for k, v in sorted(per_bill.items())},
        "over_guide_examples": over[:40], "by_tag": by_tag}


# ------------------------------------------------------------------ samples

def spread(rng, pool, n):
    """n of `pool` (a list), at least one from each era that has any, the rest at random."""
    pool = list(pool)
    rng.shuffle(pool)
    out = []
    for name, _lo, _hi in ERAS:
        first = next((b for b in pool if era_of(b["term"]) == name), None)
        if first is not None and len(out) < n:
            out.append(first)
            pool.remove(first)
    out += pool[:n - len(out)]
    return sorted(out, key=lambda b: (b["term"], b["bill"]))


def sentences(text, rx, limit=3, width=240):
    """Up to `limit` sentences of `text` that `rx` finds, trimmed around the find."""
    out = []
    for m in rx.finditer(text):
        a = max(text.rfind(".", 0, m.start()), text.rfind("\n", 0, m.start())) + 1
        e = [i for i in (text.find(".", m.end()), text.find("\n", m.end())) if i >= 0]
        s = " ".join(text[a:(min(e) + 1 if e else m.end() + 120)].split())
        if len(s) > width:
            lo = max(0, m.start() - a - width // 2)
            s = "..." + s[lo:lo + width] + "..."
        if s and s not in out:
            out.append(s)
        if len(out) >= limit:
            break
    return out


def core_regex(rule):
    """One expression for a tag's plain title phrases, for counting a bill's mentions."""
    parts = []
    for p, rx in rule.title:
        parts.append(f"(?{'i' if rx.flags & re.I else '-i'}:{rx.pattern})")
    return re.compile("|".join(parts)) if parts else None


def needles(rule):
    """Short lower-case strings of which a text must hold at least one to name the
    tag's core words at all: each plain phrase's longest word. A cheap substring test
    before the expressions run; None where a phrase is a regular expression, which
    has none to give."""
    out = set()
    for p, _rx in rule.title:
        if p.startswith("re:"):
            return None
        words = re.findall(r"[a-z0-9]+", p.lower())
        if words:
            out.add(max(words, key=len))
    return tuple(sorted(out))


def draw(reg, rules, bills, results, texts):
    """{tag: {"title": [...], "other": [...], "miss": [...], "pair": [...]}} of bill dicts
    carrying what the bench shows."""
    by_key = {key_of(b): b for b in bills}
    out = {}
    cores = {tid: core_regex(rule) for tid, rule in rules.items()}
    need = {tid: needles(rule) for tid, rule in rules.items()}
    candidates = {}
    texted = [b for b in bills if (texts.get(b["term"], {}).get(b["bill"]) or "")]
    for tid, rule in rules.items():
        attached = [by_key[k] for k, r in results.items() if tid in r["tags"]]
        title = [b for b in attached if results[key_of(b)]["tags"][tid]["tier"] == "T"]
        other = [b for b in attached if results[key_of(b)]["tags"][tid]["tier"] != "T"]

        def item(b, **extra):
            v = (results[key_of(b)]["tags"].get(tid) or {})
            d = {"term": b["term"], "bill": b["bill"], "title": b["title"], "topic": b.get("topic") or "",
                 "analysis": b["analysis"][:900], "chapters": b["chapters"][:8],
                 "tier": v.get("tier", ""), "why": v.get("why", "")}
            d.update(extra)
            return d
        sample = {
            "title": [item(b) for b in spread(random.Random(f"tags|{tid}|title"), title, PER_TIER)],
            "other": [item(b) for b in spread(random.Random(f"tags|{tid}|other"), other, PER_TIER)],
            "miss": [],
            "pair": []}
        # THE POSSIBLE MISSES, found lazily: the bills without the tag in a seeded order, the
        # first PER_MISS whose text names the core words MISS_MENTIONS times or more. A regular
        # expression over every text for every tag took the better part of an hour; this one
        # stops when it has ten, and a rare tag is cut short by the substring test.
        rng = random.Random(f"tags|{tid}|miss")
        order = list(texted)
        rng.shuffle(order)
        found = []
        for b in order:
            r = results[key_of(b)]
            if tid in r["tags"] or tid in r["dropped"] or cores[tid] is None:
                continue
            text = (texts[b["term"]][b["bill"]] or "")[:TEXT_LIMIT]
            if need[tid] is not None:
                low = text.lower()
                if not any(w in low for w in need[tid]):
                    continue
            n = len(cores[tid].findall(text))
            if n >= MISS_MENTIONS:
                found.append((b, n, text))
                if len(found) >= PER_MISS:
                    break
        candidates[tid] = found
        for b, n, text in sorted(found, key=lambda x: (x[0]["term"], x[0]["bill"])):
            sample["miss"].append(item(b, mentions=n, sentences=sentences(text, cores[tid])))
        pair = reg[tid].get("pair")
        if pair:
            for k in pair:
                b = by_key.get(k)
                if b is None:
                    sample["pair"].append({"term": k.split("/")[0], "bill": k.split("/")[1], "title": "(not in the record)",
                                           "topic": "", "analysis": "", "chapters": [], "tier": "", "why": "", "attached": False})
                else:
                    sample["pair"].append(item(b, attached=tid in results[k]["tags"]))
        out[tid] = sample
    return out, {tid: len(candidates[tid]) for tid in rules}


# ------------------------------------------------------------------ the files

def markdown(c, source):
    lines = [f"# Tag counts ({source})", "",
             f"Under {c['threshold_bills_title_and_analysis']} bills at the title and analysis tiers (a reference, "
             "not a rule): " + (", ".join(f"{u['id']} {u['title_and_analysis']}" + (" (kept: " + u["keep_small"] + ")" if u["keep_small"] else "")
                                           for u in c["tags_under_threshold"]) or "none"), "",
             f"{c['bills']:,} bills. Title tier: {c['bills_title_tier']:,}; any tier: {c['bills_any_tier']:,}; "
             f"over the guide of {c['guide']} tags: {c['bills_over_guide']:,}; "
             f"bills with no topic that gain a tag: {c['bills_with_no_topic_that_gain_a_tag']:,}.", "",
             "| tag | title | any | T | A | R | gain a topic | dropped (topic) |", "|---|---|---|---|---|---|---|---|"]
    for tid, r in c["by_tag"].items():
        lines.append(f"| {tid} | {r['title']} | {r['any']} | {r['best']['T']} | {r['best']['A']} | {r['best']['R']} "
                     f"| {r['gained_a_topic']} | {r['dropped_for_topic']} |")
    terms = sorted({t for r in c["by_tag"].values() for t in r["by_term"]})
    lines += ["", "## By term (any tier)", "", "| tag | " + " | ".join(t[2:4] + t[5:] for t in terms) + " |",
              "|---|" + "---|" * len(terms)]
    for tid, r in c["by_tag"].items():
        lines.append(f"| {tid} | " + " | ".join(str(r["by_term"].get(t, {}).get("any", 0)) for t in terms) + " |")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root")
    ap.add_argument("--registry")
    ap.add_argument("--out", default="reports")
    ap.add_argument("--no-samples", action="store_true")
    a = ap.parse_args()
    reg, source = TR.load_registry(a.registry)
    syn = TR.read_doc(a.registry).get("synonyms", {})
    bad = TR.validate(reg, TR.known_topics(a.root), syn)
    for b in bad:
        print("  " + b)
    print(f"registry: {len(reg)} tags, {len(syn)} synonyms, from {source}; {len(bad)} problem(s)")
    rules = TR.compile_registry(reg)
    bills = TR.load_bills(a.root)
    if not bills:
        sys.exit("no bills read: refusing to write counts for nothing")
    results, c = count(rules, bills, reg)
    c["registry"] = source
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "tags_counts.json").write_text(json.dumps(c, indent=1), encoding="utf-8")
    (out / "tags_counts.md").write_text(markdown(c, source), encoding="utf-8")
    table, _conf = TR.synonym_table(reg, syn)
    (out / "tags_synonyms.json").write_text(json.dumps(dict(sorted(table.items())), indent=1, ensure_ascii=False),
                                            encoding="utf-8")
    print(f"{c['bills']:,} bills: {c['bills_title_tier']:,} tagged by title, {c['bills_any_tier']:,} by any tier, "
          f"{c['bills_over_guide']:,} over {c['guide']} tags")
    if not a.no_samples:
        samples, ncand = draw(reg, rules, bills, results, TR.load_texts(a.root))
        for tid, s in samples.items():
            s["candidates_for_misses"] = ncand[tid]
        (out / "tags_samples.json").write_text(json.dumps(samples, indent=1), encoding="utf-8")
        thin = [t for t, s in samples.items() if len(s["title"]) < PER_TIER or len(s["other"]) < PER_TIER]
        print(f"samples written for {len(samples)} tags; {len(thin)} have fewer than {PER_TIER} in a tier")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
