#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-12.2
"""
The General Court's own subject code as an archived bill's topic.

No network. It reads db/past/PastLegislation.psv, which fetch_past_db.py dumped.

WHY. data/bills.json carries a subject for 2025-2026 alone, so for eighteen
terms the site showed the topic model's guess although the General Court's own
code is on disk for 31,199 of the 31,504 archived bills that join to a record
(private/DATA_GAPS.md item 4). The person decided on 1 October 2026 that the
code is the authority where there is one, and on 11 November 2026 (Stage 0 of
reports/topics-as-tags-design-2026-11.md) that it be adopted for the archive.

THROUGH THE SITE'S CATEGORIES, NOT AROUND THEM. This module only fills a bill's
subject with the code's OFFICIAL name, exactly as the current term's records
already carry it. Everything after is the path 2025-2026 takes, in
build_site_v2.unify_vocabulary: the five folded categories go to their parents
(topic_model.FOLD), "Regular Meeting" is retired, Housing and Study Committees
are claimed by their title rules (topic_model.remap_gold), and the two renamed
names are worded. So there is ONE mapping for all nineteen terms, and a code the
site dropped is never revived. build_site_v2.vocabulary_of() is that path for
one record, which the table and preflight call.

THE 27 CODES WITH NO NAME ON DISK (PUP, ENW, PRR, ENR, UTI, HIG, EDH, ...) are
older codes the General Court's table no longer lists. They are NOT guessed:
the bill keeps no official subject here, so it stays on whatever the topic model
gave it (merge_guessed_topics). unnamed() lists them with counts and sample
titles for a person to ask the General Court for their names.

ONLY WHERE THE RECORD HAS NO SUBJECT, never in the current term (the General
Court's own labels are already there and the view does not cover it), and not
where the database files the bill's LSR under another bill number (the guard
past_sponsors.join uses).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import json
import re
from collections import Counter, defaultdict

PAST = Path("db/past")
SUBJECTS = Path("data/subjects.json")


def _bill_no(s):
    """"HB  0169" and "HB169" are both HB169."""
    m = re.match(r"^([A-Z]+)0*(\d+)$", re.sub(r"\s+", "", (s or "").upper()))
    return f"{m.group(1)}{int(m.group(2))}" if m else ""


def read_codes(root=PAST):
    """{(lsr year, lsr number): (subject code, bill number)} from PastLegislation.
    Empty where the dump is not on this machine."""
    import past_sponsors as PSP
    root = Path(root)
    if not (root / "_manifest.json").exists() or not (root / "PastLegislation.psv").exists():
        return {}
    out = {}
    for r in PSP.read_view("PastLegislation", root):
        try:
            key = (int(r["SessionYear"]), int(r["LSR"]))
        except (KeyError, ValueError):
            continue
        out[key] = ((r.get("SubjectCode") or "").strip(), _bill_no(r.get("CondensedBillNo")))
    return out


def official_of(rec, bid, codes):
    """The official code of an archived record, or "" -- by its stored LSR, and
    not where the database files that LSR under another bill number."""
    try:
        key = (int(rec.get("lsr_year")), int(rec.get("lsr_num")))
    except (TypeError, ValueError):
        return ""
    code, num = codes.get(key, ("", ""))
    if num and num != bid:
        return ""
    return code


def names_of(subjects):
    """{code: official name} from data/subjects.json's {code: {"name"}}."""
    return {k: (v or {}).get("name", "") for k, v in (subjects or {}).items()}


def adopt(bills, subjects, current="", codes=None):
    """Give every archived bill with no subject the official name of its code, in
    place. Returns a Counter: what was filled, and what was left and why."""
    tally = Counter()
    codes = read_codes() if codes is None else codes
    names = names_of(subjects)
    if not codes:
        tally["no dump on this machine"] += 1
        return tally
    current = current or (max(bills) if bills else "")
    for term, by_bill in bills.items():
        if term == current:
            continue
        for bid, rec in by_bill.items():
            if rec.get("subject"):
                continue
            code = official_of(rec, bid, codes)
            if not code:
                tally["no code in the database"] += 1
            elif code not in names or not names[code]:
                tally["a code with no name on disk"] += 1
            else:
                rec["subject_code"] = code
                rec["subject"] = names[code]
                rec["subject_source"] = "general court"
                tally["filled"] += 1
    return tally


def unnamed(bills, subjects, codes=None, current=""):
    """{code: (count, [three sample "TERM BILL title"])} for the codes with no
    name on disk, over the archived bills that carry one."""
    codes = read_codes() if codes is None else codes
    names = names_of(subjects)
    current = current or (max(bills) if bills else "")
    seen = defaultdict(lambda: [0, []])
    for term, by_bill in bills.items():
        if term == current:
            continue
        for bid, rec in by_bill.items():
            code = official_of(rec, bid, codes)
            if code and not names.get(code):
                s = seen[code]
                s[0] += 1
                if len(s[1]) < 3 and (rec.get("title") or "").strip():
                    s[1].append(f"{term} {bid}: {rec['title'].strip()[:110]}")
    return {k: (v[0], v[1]) for k, v in sorted(seen.items(), key=lambda kv: -kv[1][0])}


if __name__ == "__main__":
    sys.exit("This module is read by build_site_v2.py; it runs nothing itself.")
