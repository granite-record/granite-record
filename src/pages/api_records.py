#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.4
"""
The data API's records, a file each, under /api/.

    import api_records as AR
    rec = AR.Records(rows, site)                # the bill index's rows, before the bill files
    build_exports.bill_files(..., collect=...)  # rec.add_bill is handed every bill record
    rec.text_files(out)                         -> /data/bill-texts-<term>.jsonl.gz's rows
    AR.write(site, out, rec, people=..., person_of=..., base=...)   -> the manifest's api.records

THE OWNER'S WORD OF 16 NOVEMBER 2026 (reports/refactor/stage0-data.md, 5.3):
static files, and nothing new that runs; "format": 1 in every file and no
/v1/ in the path, the rule of 30 October, so a change that cannot be made by
adding becomes a new file name beside the old; a file a record for the
sitting term first, because a file for every bill of every term (33,717)
would not fit the host's 100,000 a deploy. AND THE TEXT (the owner, the same
morning): a law's file carries every section's text, and a bill's every
version its Bill Text tab shows; the 30 October design had left the statutes'
text out by default (Q19), which the owner had never chosen.

WHAT IT WRITES, under site/api/, every file compact JSON with "format": 1:

  index.json                           every resource: its files, how many there
                                       are tonight, and every field with its
                                       stability (api_schema.API_RESOURCES)
  bills/<term>/index.json              every term: each bill's row
  bills/<sitting term>/<BILL>.json     the sitting term alone: each bill's row,
                                       every stable field of its record, and the
                                       text of every version its tab shows
  rollcalls/<term>.json                every term with roll calls: each one's row
  rollcalls/<sitting term>/<roll call>.json   the sitting term alone: its row and
                                       every member's vote
  members/index.json, members/<person>.json   everyone people.json holds, with
                                       their seat where they sit and the bills
                                       they sponsored
  requests/<year>/index.json, requests/<year>/<nnnn>.json   the bill requests the
                                       site lists
  laws/index.json, laws/<chapter>.json each chapter of the statutes: each
                                       section's heading, text and source note as
                                       its page shows them, the session laws that
                                       changed it, the bill each was and the day
                                       it took effect, and the day the text was
                                       taken and where from
  changes/<date>.json                  the last eight nights: the records whose
                                       promised fields changed, and those gone
                                       (THE CHANGE FEED, below)

and under site/data/, beside the bill files, which stay as they were:

  bill-texts-<term>.jsonl.gz           every term: each bill's text, a line a
                                       bill, as its file a record has it -- where
                                       a file a bill cannot go (the file cap)

FROM THE SAME RECORDS AS THE PAGES AND THE DOWNLOADS. A bill's record is the
one its page carries, handed over by build_exports.bill_files as it writes the
bill files (Records.add_bill), and its row the bill index's, as bills.csv's
are; its text is what its Bill Text tab reads (bill_text): the versions
build_bill_versions.py wrote, else the record's own printing, and nothing
where the site holds none. Roll calls, ballots, legislators and sponsors are
read back out of the CSVs build_exports has just written, people from the join
people.json is written from, requests from the bill search's own file of them,
and the laws from the statute table and rsa_citations.json, which the Laws
pages draw, through build_rsa's own readers. So a record cannot say one thing
here and another on its page or in a download.

ONLY STABLE FIELDS. api_schema.API_RESOURCES says what each file holds, field
by field; a field not there, or not marked stable, is not written. A bill's
page record carries its narrative, stages, stations and the rest, which the
page draws and the promise does not cover (api_schema.BILL_FIELDS): none of
them is in a file here. A record whose fields come out otherwise stops the
step (SystemExit) rather than publish an unpromised shape.

THE SITTING TERM AND THE REQUESTS' YEAR are the build's own, never a literal:
the sitting term is the newest term the bill index holds, as the feeds, the
bill pages and the bill search take it (sitting_term), and the requests' year
is meta.json's "requests", which build_lsrs.py writes from the requests
themselves. On the turn to 2027-2028 the new term's bills take the per-record
files the night its first bill is in the index, and 2025-2026's per-bill and
per-roll-call files go: the term keeps its rows.

THE FOLDER IS THIS STEP'S ALONE. Every file under site/api/ is written
tonight or taken away, so a bill that has left the sitting term, a request
no longer listed or a chapter the table no longer holds leaves nothing behind
on a machine whose site/ is not new (the laptop's). The Pages Functions at
/api/live/, /api/report and /api/follow/ are in functions/, not in site/, and
nothing here writes their addresses (RESERVED).

Nothing here asks the network.
"""

import csv
import hashlib
import json
import os
import re
import time
from pathlib import Path

import api_schema as AS
import bill_order as BO
import build_date
import site_read as SR

FORMAT = AS.FORMAT
FOLDER = "api"
# The addresses under /api/ that are the Pages Functions' (functions/api/):
# no file here may stand in one's way.
RESERVED = ("live", "report", "follow")
# A file's name made from a record's key: letters, digits and a hyphen.
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,40}$")
# Cloudflare Pages refuses a file past 25 MiB (build_exports.CAP), and the
# step stops short of 90% of it, as build_exports does (SAFE).
CAP = 25 * 1024 * 1024


def stable(spec):
    """The fields of a spec that a file may carry: those marked stable, in order."""
    return [k for k, (_t, _d, st) in spec.items() if st == AS.S]


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def stamp(dt):
    """A UTC moment as the changes files write one: 2026-11-16T09:02:40Z."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def sitting_term(rows):
    """The term still sitting: the newest term the bill index holds -- the
    rule of build_feeds, build_bill_pages and build_civics.sitting_term."""
    return max((str(r.get("term") or "") for r in rows or ()
                if SR.TERM_FILE.fullmatch(str(r.get("term") or ""))), default="")


def unpromised(obj, spec, inside, where="", depth=0):
    """Every field `obj` carries that `spec` does not mark stable, as
    "where.field": inside the arrays and objects `inside` names too. A
    file's own fields are the promise, so one more is a file not written."""
    if not isinstance(obj, dict):
        return [f"{where or 'the file'}: not an object"]
    ok = set(stable(spec))
    bad = [f"{where}.{k}" if where else k for k in obj if k not in ok]
    for k, v in obj.items():
        if k in ok and k in inside and depth < 4:
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, dict):
                    bad += unpromised(x, inside[k], inside, f"{where}.{k}" if where else k, depth + 1)
    return bad


def held(name, holds, obj, where):
    """obj, if it is what `name`'s file of rows or file a record promises;
    the step stops where it is not, rather than publish another shape."""
    spec, inside = AS.api_file_fields(name, holds)
    bad = unpromised(obj, spec, inside)
    if bad or obj.get("format") != FORMAT:
        raise SystemExit(f"api_records: {where} would carry "
                         + (", ".join(sorted(set(bad))[:6]) if bad else f"format {obj.get('format')!r}")
                         + ", which api_schema does not promise; nothing under /api/ is published "
                         "in a shape it does not describe")
    return obj


# ---------------------------------------------------------------------- bills --

def bill_row(r):
    """A bill's row, as /api/bills/<term>/index.json lists it: bills.csv's
    columns (build_exports.bills), the committees as a list and the numbers
    as numbers."""
    t = str(r.get("term") or "")
    return {"key": f"{t}/{r.get('id')}", "id": r.get("id", ""), "year": r.get("year", ""),
            "term": t, "title": r.get("title", ""), "sponsor": r.get("sponsor", ""),
            "committees": list(r.get("committees") or ([r["committee"]] if r.get("committee") else [])),
            "topic": r.get("topic", ""), "status": r.get("status", ""), "outcome": r.get("kind", ""),
            "passage": r.get("passage", ""), "roll_calls": r.get("nrc", 0) or 0,
            "chapter": r.get("chapter", ""), "chip": r.get("chip", "")}


# The stable fields of a bill's record that its file adds to its row, in
# api_schema.API_BILL's order (BILL_FIELDS'); where the row has one too, the
# row's is kept (API_BILL says why). Its text follows them (bill_text).
RECORD_FIELDS = [k for k in stable(AS.API_BILL)
                 if k not in AS.API_BILL_ROW and k not in AS.API_BILL_TEXT]


def record_day(v):
    """The General Court's "12/04/2025 09:19:35" as 2025-12-04, as the Bill
    Text tab says the day (app.js recordDay); None for what is not that shape."""
    m = re.match(r"\s*(\d{1,2})/(\d{1,2})/(\d{4})\b", str(v or ""))
    return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}" if m else None


def bill_text(site, rec):
    """{"versions", "text_on_file"}: the text of every version the bill's
    Bill Text tab shows, from the files it reads (app.js): for a bill with
    more than one version or with amendments (hasVersionIndex), the versions
    build_bill_versions.py wrote under site/versions/<year>/, each its name
    (title), its day and the text its text_url names; for any other, or one
    whose index is not there, the record's own printing (billtext), whose
    record gives no day. Where neither holds text, none: never made up, and
    never fetched. Also how many versions were listed with no text on file."""
    vers, gaps = [], 0
    year, bid = str(rec.get("year") or ""), str(rec.get("id") or "")
    ix = Path(site) / "versions" / year / f"{bid}.json" if site else None
    if ix is not None and ((rec.get("nver") or 0) > 1 or (rec.get("namd") or 0)) and ix.is_file():
        try:
            index = json.loads(ix.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            index = {}
        for v in index.get("versions") or []:
            p = Path(site) / str(v.get("text_url") or "").lstrip("/") if v.get("text_url") else None
            text = p.read_text(encoding="utf-8") if p is not None and p.is_file() else None
            gaps += text is None
            vers.append({"name": v.get("title") or v.get("label") or "",
                         "date": record_day(v.get("date")), "text": text})
    if not vers:
        bt = rec.get("billtext") if isinstance(rec.get("billtext"), dict) else {}
        if str(bt.get("body") or "").strip():
            vers.append({"name": bt.get("version") or "", "date": None, "text": bt["body"]})
    return {"versions": vers, "text_on_file": any(v["text"] for v in vers)}, gaps


def bill_file(row, rec, text):
    """A bill's own file: its row, every stable field its record has, and its text."""
    out = {"format": FORMAT, **bill_row(row)}
    out.update((k, rec[k]) for k in RECORD_FIELDS if k in rec)
    out.update(text)
    return out


class Records:
    """What build_exports.bill_files hands over, a bill record at a time
    (add_bill), in each term's bill order and a term at a time:

      the sitting term's bills' files, made and held to their promise as
      they pass and kept as bytes -- bill_files lets each term go once it is
      written, and so does this, but for these;
      every term's bills' text, a line a bill, held while the term's bills
      come and packed (gzip -9, no name and no time) once the next term's
      begin, until text_files writes /data/bill-texts-<term>.jsonl.gz.

    `site` is where the versions are read from (site/versions/); None reads
    only the records' own printing. `cache` is the build's own run's folder
    of kept packed files (build_cache.Packed), where a term whose lines were
    packed before is taken whole; False, the default, packs every term."""

    def __init__(self, rows, site=None, cache=False):
        import build_cache as BC
        self.rows = list(rows or ())
        self.site = site
        self.sitting = sitting_term(self.rows)
        self.by = {(str(r.get("term") or ""), str(r.get("id") or "").upper()): r for r in self.rows}
        self.files = {}         # bill id -> its file's bytes, for the sitting term
        self.seen = 0           # every record handed over, of every term
        self.texts = {}         # term -> [its lines, how many with text], while its bills come
        self.packed = {}        # term -> (its file's bytes, lines, with text), once packed
        self.cache = cache
        self.packs = BC.Packed("bill_texts", "gzip-9", cache)
        self.gaps = 0           # versions listed with no text on file
        self.hashes = {}        # term/bill -> its file's hash (record_hash), of every term

    def _pack_open(self):
        """Pack the term whose bills were coming, and let its lines go."""
        for term in list(self.texts):
            lines, with_text = self.texts.pop(term)
            self.packed[term] = (self.packs.pack(lines), len(lines), with_text)

    def add_bill(self, term, rec):
        self.seen += 1
        bid = str(rec.get("id") or "").upper()
        row = self.by.get((term, bid))
        if row is None:
            return
        if term not in self.texts:
            # A TERM AT A TIME, as bill_files hands them: the term before is
            # whole once another begins, and is packed then.
            if term in self.packed:
                raise SystemExit(f"api_records: a bill of {term} came after that term's texts were "
                                 "packed; bill_files hands the records a term at a time")
            self._pack_open()
            self.texts[term] = [[], 0]
        text, gaps = bill_text(self.site, rec)
        self.gaps += gaps
        t = self.texts[term]
        line = {"key": f"{term}/{row.get('id')}", **text}
        t[0].append((json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        t[1] += bool(text["text_on_file"])
        # Every term's bill is hashed as the sitting term's file is made, so
        # the change feed sees a change to a bill of any term, and none at
        # the turn of a term for a bill whose fields did not move.
        f = bill_file(row, rec, text)
        self.hashes[line["key"]] = record_hash("bills", f)
        if term == self.sitting:
            self.files[bid] = dump(held("bills", "record", f, f"bill {term}/{bid}"))

    def text_files(self, out):
        """Write /data/bill-texts-<term>.jsonl.gz for every term the bill
        files wrote, the same bytes for the same texts (no name and no time
        in the gzip header); return their rows for the manifest's "files",
        newest term first, as the bill files' are."""
        import hashlib
        self._pack_open()
        rows = []
        for term in sorted(self.packed, reverse=True):
            data, n, with_text = self.packed[term]
            name = f"bill-texts-{term}.jsonl.gz"
            if len(data) > CAP * 0.9:
                raise SystemExit(f"api_records: {name} is {len(data) / 1e6:.1f} MB, past what the "
                                 "host takes; split it before publishing")
            (Path(out) / name).write_bytes(data)
            rows.append({"path": f"/data/{name}", "kind": "bill_texts", "term": term, "rows": n,
                         "with_text": with_text, "bytes": len(data),
                         "sha256": hashlib.sha256(data).hexdigest(),
                         "encoding": "gzip", "media_type": "application/x-ndjson"})
            print(f"  {name:<28} {n:>9,} bills {len(data) / 1e6:>7.1f} MB, {with_text:,} with text")
        if self.gaps:
            print(f"    WARNING: {self.gaps:,} version(s) a Bill Text tab lists have no text on file; "
                  "their text is null in /api/ and in bill-texts-<term>.jsonl.gz")
        # Every term written: what was packed or taken is what is kept.
        if self.cache is not False:
            self.packs.keep()
            print(f"    bill texts: {self.packs.said()}")
        self.packed = {}
        return rows


# ------------------------------------------------------------------ the CSVs --

def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def typed(row, spec):
    """A CSV row as JSON, by the types `spec` gives its stable fields: an
    integer as a number (an empty cell null), a boolean from 1 and 0, the
    rest as written."""
    out = {}
    for k in stable(spec):
        if k in row:
            v, ty = row[k], spec[k][0]
            out[k] = _int(v) if ty == "integer" else (str(v).strip() == "1") if ty == "boolean" else v
    return out


def read_csv(path):
    """A CSV build_exports wrote tonight, a dict a row; [] where it is not there."""
    p = Path(path)
    if not p.is_file():
        return []
    with p.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------- laws --

TEXT_SOURCE = ("The General Court's statute table (NH_RSA), from its database, as this site's Laws "
               "pages show it.")


def law_files(table, citations, taken=None):
    """({chapter: its file}, the index's rows), from the statute table and
    rsa_citations.json, through build_rsa's own readers: each chapter's name,
    title and official page; each section's heading and its text a paragraph
    a line, as the chapter's page sets it (rsa.paragraphs over the table's
    text, build_rsa.linked_text's own reading), and its source note, both
    none for a repealed section, which the page shows by its heading alone;
    the source note's session laws with the bill each was, and each one's day
    from the note itself (build_rsa.note_days); and the day the table was
    taken (`taken`, build_rsa.taken_day) and the latest year of laws it holds
    (rsa_citations' asof), which the page's lead says."""
    import build_rsa as BR
    import rsa
    enacted = (citations or {}).get("enacted") or {}
    through = _int(((citations or {}).get("asof") or {}).get("laws_through"))
    files, rows = {}, []
    for ch in sorted(table.chapters, key=rsa.chap_key):
        info = table.chapters[ch]
        row = {"chapter": ch, "name": BR.nice(info.get("name") or ""),
               "title_no": info.get("title_no") or "",
               "title": BR.title_label(info.get("title_no"), info.get("title"))[1],
               "repealed": bool(info.get("repealed")), "page": BR.chapter_path(ch)}
        secs = []
        for addr in info["sections"]:
            s = table.sections[addr]
            hist, days = [], {}          # a session law's days, by its year and chapter
            for y, law, b in enacted.get(addr) or []:
                lch, _, lsec = str(law).partition(":")
                if (y, lch) not in days:
                    days[(y, lch)] = (BR.note_days(s.note, y, lch)
                                      if lch.isdigit() and str(y).isdigit() else {})
                d = days[(y, lch)].get(int(lsec)) if lsec.isdigit() else None
                hist.append({"year": _int(y), "law": str(law),
                             "bill": str(b or "").replace(" ", ""),
                             "effective": d.isoformat() if d else None})
            gone = bool(s.repealed)
            secs.append({"section": addr, "heading": s.heading, "repealed": gone,
                         "text": None if gone else "\n".join(rsa.paragraphs(s.text)),
                         "note": None if gone else (s.note or ""), "changed_by": hist})
        rows.append(row)
        files[ch] = {"format": FORMAT, **row, "official": BR.official_page(table, ch),
                     "text_source": TEXT_SOURCE, "text_taken": taken or None,
                     "laws_through": through, "sections": secs}
    return files, rows


# ------------------------------------------------------------ the change feed --
# /api/changes/<date>.json: which records' stable fields changed each night
# (the owner's word of 16 November 2026; stage0-data.md 5.3). Its own folder,
# not a key in /changes/, so the email sender's contract
# (workers/follow/CHANGES_FORMAT.md) does not move.
#
# A RECORD'S HASH is of what the API promises about it: a bill's file as the
# sitting term's are made -- its row, every stable field of its record and its
# text -- for a bill of every term, so a correction to a 1997 bill is listed
# and the turn of a term lists nothing that did not change; a roll call's row,
# and, while its term sits, its ballots apart (BALLOTS), so that the turn does
# not list the old term's roll calls for losing their file a record; a
# member's, a request's and a chapter's file, all but its "format" -- and a
# chapter's all but the day its text was taken (NOT_A_CHANGE), which moves
# every week the statutes are taken again whether a word changed or not. A
# page's field is in none of them, so a page drawn anew lists nothing.
#
# THE HASHES TRAVEL AS THE CENSUS DOES. This build reads archive/api-hashes.json
# (LEDGER) and leaves its own at archive/api-hashes.next.json (CANDIDATE);
# nightly.py keeps it exactly where it writes the census -- a real night the
# gates accept, or a New term run's once its deploy has landed, for which
# cloud.py site-up carries it with the site -- so a stopped night, a dry run or
# a rejected switch changes nothing the next night compares with.
# cloud_kit.json's state list carries it, and a dry night never sends it
# (cloud.DRY_NEVER). The ledger holds the hashes of the last accepted build and
# the eight nights the folder carries, as the first-seen ledger holds its own
# (follow_changes.py), because the night's machine starts empty: each build
# writes all eight files from it.
#
# A SECOND BUILD OF ONE DATE compares with the last accepted build's hashes, and
# its night lists what the first listed and what changed since, so a rerun
# never drops what a published night said. NO LEDGER (the first night, or a
# lost state) lists nothing that night, never every record, and says so in a
# WARNING: the next night lists against this one's.
LEDGER = Path("archive/api-hashes.json")
CANDIDATE = Path("archive/api-hashes.next.json")
LEDGER_FORMAT = 1
KINDS = ("bills", "rollcalls", "members", "laws", "requests")
BALLOTS = "ballots"
NOT_A_CHANGE = {"laws": ("format", "text_taken")}
CHANGES = "changes"                   # under site/api/


def digest(obj):
    """A record's promised fields as one short hash: sha256 of their JSON with
    the keys in order, its first 16 hex digits. Read as the same however a
    record's own fields were ordered."""
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
                     check_circular=False)
    return hashlib.sha256(raw.encode("ascii")).hexdigest()[:16]


def record_hash(kind, obj):
    """The hash of one record's file, less what is no change of it."""
    leave = NOT_A_CHANGE.get(kind, ("format",))
    return digest({k: v for k, v in obj.items() if k not in leave})


def _natural(key):
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", str(key))]


def load_ledger(path=LEDGER, tonight=""):
    """(ledger, why): the last accepted build's hashes and nights, or None and
    why there is none to compare with."""
    p = Path(path)
    if not p.is_file():
        return None, f"no {p.as_posix()}"
    try:
        led = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{p.as_posix()} will not read ({type(e).__name__})"
    if not isinstance(led, dict) or led.get("format") != LEDGER_FORMAT or \
            not isinstance(led.get("hashes"), dict) or not isinstance(led.get("nights"), dict) or \
            not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(led.get("date"))):
        return None, f"{p.as_posix()} is not a ledger of format {LEDGER_FORMAT}"
    if tonight and led["date"] > tonight:
        return None, (f"{p.as_posix()} is of {led['date']}, after tonight's {tonight}: a build dated "
                      "earlier than the last accepted one cannot say what changed since")
    return led, ""


def decide(led, hashes, *, tonight, built):
    """(tonight's ledger, what tonight found new to the last accepted build:
    {"changed": {kind: set}, "removed": {kind: set}})."""
    import follow_changes as FC
    keep = set(FC.window(tonight))
    found = {"changed": {k: set() for k in KINDS}, "removed": {k: set() for k in KINDS}}
    nights = {}
    if led is not None:
        old = led["hashes"]
        for k in KINDS:
            was, now = old.get(k) or {}, hashes.get(k) or {}
            found["changed"][k] = {key for key, h in now.items() if was.get(key) != h}
            found["removed"][k] = set(was) - set(now)
        wb, nb = old.get(BALLOTS) or {}, hashes.get(BALLOTS) or {}
        found["changed"]["rollcalls"] |= {key for key, h in nb.items() if key in wb and wb[key] != h}
        nights = {d: n for d, n in led["nights"].items() if d in keep and isinstance(n, dict)}
    here = nights.get(tonight) or {}
    said = {}
    for side, other in (("changed", "removed"), ("removed", "changed")):
        said[side] = {k: sorted((set((here.get(side) or {}).get(k) or ()) | found[side][k])
                                - found[other][k], key=_natural) for k in KINDS}
    nights[tonight] = {"built": built, **said}
    ledger = {"format": LEDGER_FORMAT,
              "about": ("The data API's change feed's state (src/pages/api_records.py): the hashes of "
                        "every record's promised fields as the last accepted build had them, and the "
                        "eight nights /api/changes/ carries."),
              "date": tonight, "built": built, "hashes": hashes,
              "nights": {d: nights[d] for d in sorted(nights) if d in keep}}
    return ledger, found


def change_files(ledger, tonight, built):
    """{name: object} of the eight nights' files, from the ledger; a night no
    accepted build wrote lists nothing, as /changes/ does."""
    import follow_changes as FC
    empty = {k: [] for k in KINDS}
    files = {}
    for d in FC.window(tonight):
        n = ledger["nights"].get(d) or {}
        files[f"{d}.json"] = {"format": FORMAT, "date": d, "built": n.get("built") or built,
                              "changed": {k: list((n.get("changed") or empty).get(k) or [])
                                          for k in KINDS},
                              "removed": {k: list((n.get("removed") or empty).get(k) or [])
                                          for k in KINDS}}
    return files


# --------------------------------------------------------------------- write --

class Out:
    """One night's files under site/api/: each written once and held to its
    promise, counted and sized by resource, and every path kept, so that
    whatever else is there can go."""

    def __init__(self, root):
        self.root = Path(root)
        self.paths = set()
        self.count, self.bytes = {}, {}
        self.first = {}         # each resource's first file a record, for the /api page

    def put(self, name, holds, rel, obj):
        """Write one file: `obj` an object, held to `name`'s `holds` file
        here, or the bytes of one already held (Records.add_bill)."""
        rel = rel.strip("/")
        if rel.split("/", 1)[0] in RESERVED:
            raise SystemExit(f"api_records: {rel} is a Pages Function's address")
        if rel in self.paths:
            raise SystemExit(f"api_records: {rel} would be written twice")
        data = obj if isinstance(obj, (bytes, str)) else dump(held(name, holds, obj, rel))
        data = data.encode("utf-8") if isinstance(data, str) else data
        if len(data) > CAP * 0.9:
            raise SystemExit(f"api_records: {rel} is {len(data) / 1e6:.1f} MB, past what the host "
                             "takes; split it before publishing")
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        self.paths.add(rel)
        self.count[name] = self.count.get(name, 0) + 1
        self.bytes[name] = self.bytes.get(name, 0) + len(data)
        if holds == "record":
            self.first.setdefault(name, f"/{FOLDER}/{rel}")

    def sweep(self):
        """Take away every file under the folder this night did not write, and
        the folders that leaves empty. Returns how many files went."""
        gone = 0
        if not self.root.is_dir():
            return 0
        for p in sorted(self.root.rglob("*"), key=lambda q: len(q.parts), reverse=True):
            rel = p.relative_to(self.root).as_posix()
            if p.is_file() and rel not in self.paths:
                p.unlink()
                gone += 1
            elif p.is_dir() and not any(p.iterdir()):
                p.rmdir()
        return gone


def request_record(r, num, year):
    """(its row, its own file's fields) for one row of the bill search's file
    of requests, `num` its number ("2027-0001"), `year` the session the site
    lists. The file is the row and, since 17 November 2026, its text
    (api_schema.API_REQUEST_RECORD; the owner: the text "shows as a PDF on the
    lsr search page"): what its page's Bill Text tab shows, read through the
    one reader the page reads it through (build_lsrs.request_text), null until
    the night has read it, and the PDF's address. The card fetches it here."""
    from build_lsrs import request_text
    from terms import term_of_year
    ry = _int(r.get("year")) or year
    intro = str(r.get("introduced") or "").replace(" ", "")
    row = {"lsr": num, "year": ry, "title": r.get("title", ""), "sponsor": r.get("sponsor", ""),
           "cosponsors": list(r.get("cosp") or []), "body": r.get("body", ""),
           "status": r.get("status", ""), "withdrawn": bool(r.get("withdrawn")),
           "bill": f"{term_of_year(ry)}/{intro}" if intro else ""}
    text = request_text(num) if r.get("text_on_file") else ""
    return row, {**row, "text": text or None, "text_pdf": str(r.get("text_pdf") or "")}


def _named(key, what, said):
    """Whether a record's key makes a file's name; said where it does not."""
    if NAME.fullmatch(str(key or "")):
        return True
    said.append(f"    WARNING: {what} {key!r} makes no file name, so it has no file under /api/")
    return False


def write(site, out, rec, *, people=None, person_of=None, base="https://graniterecord.org",
          built="", db="db", citations="rsa_citations.json", table=None, ledger=LEDGER,
          ledger_out=CANDIDATE):
    """Every file under site/api/. `out` is site/data, where build_exports
    has just written the CSVs; `rec` the Records the bill files filled;
    `people` people_join's people (None where there is no join here, and then
    nobody has a file); `person_of` member id -> person; `table` the statute
    table where the caller has it, else read from `db`; `ledger` the hashes
    the change feed compares with and `ledger_out` where tonight's are left.
    Returns (the manifest's api.records, the lines to print)."""
    t0 = time.time()
    site, out = Path(site), Path(out)
    built = built or stamp(build_date.utcnow())
    o = Out(site / FOLDER)
    said = []
    sitting = rec.sitting
    person_of = person_of or {}
    # Each record's hash, by kind, for the change feed (THE CHANGE FEED).
    hashes = {"bills": dict(rec.hashes), "rollcalls": {}, BALLOTS: {}, "members": {}, "laws": {},
              "requests": {}}

    # ---- bills: every term's rows; the sitting term's bills, a file each
    terms = {}
    for r in rec.rows:
        t = str(r.get("term") or "")
        if SR.TERM_FILE.fullmatch(t):
            terms.setdefault(t, []).append(r)
    for t in sorted(terms, reverse=True):
        o.put("bills", "rows", f"bills/{t}/index.json",
              {"format": FORMAT, "term": t,
               "bills": [bill_row(r) for r in sorted(terms[t], key=lambda r: BO.bill_key(r.get("id")))]})
    if not rec.seen:
        # No bill pages at all: a site built without them, as bill_files says.
        said.append(f"    the bills of {sitting or 'no term'} have no file of their own tonight: no "
                    "bill page was read")
    else:
        want = {str(r.get("id") or "").upper() for r in terms.get(sitting, [])}
        missing = sorted(want - set(rec.files), key=BO.bill_key)
        if missing:
            raise SystemExit(f"api_records: {len(missing):,} of {sitting}'s {len(want):,} bills have "
                             f"no record to write ({', '.join(missing[:5])}); the term's files are "
                             "every bill or none")
        for bid in sorted(rec.files, key=BO.bill_key):
            if _named(bid, "the bill", said):
                o.put("bills", "record", f"bills/{sitting}/{bid}.json", rec.files[bid])
    said.append(f"  {'api/bills/':<28} {len(terms):>9,} terms' rows; {len(rec.files):,} bills of "
                f"{sitting or 'no term'}, a file each")

    # ---- roll calls: every term's rows; the sitting term's, with ballots
    by_term, keys = {}, set()
    for r in read_csv(out / "rollcalls.csv"):
        r = typed(r, AS.API_ROLLCALL_ROW)
        if r.get("roll_call") in keys:
            said.append(f"    WARNING: roll call {r['roll_call']} is in rollcalls.csv twice; "
                        "/api/ keeps the first")
            continue
        keys.add(r.get("roll_call"))
        by_term.setdefault(str(r.get("term") or ""), []).append(r)
        hashes["rollcalls"][r.get("roll_call")] = record_hash("rollcalls", r)
    rc_terms = sorted((t for t in by_term if SR.TERM_FILE.fullmatch(t)), reverse=True)
    for t in rc_terms:
        o.put("rollcalls", "rows", f"rollcalls/{t}.json",
              {"format": FORMAT, "term": t, "rollcalls": by_term[t]})
    ballots = {}
    for v in read_csv(out / f"votes-{sitting}.csv") if sitting else []:
        ballots.setdefault(v.get("roll_call"), []).append({
            "member_id": v.get("member_id", ""), "person": person_of.get(str(v.get("member_id")), ""),
            "member": v.get("member", ""), "party": v.get("party", ""), "vote": v.get("vote", "")})
    n_rc = 0
    for r in by_term.get(sitting, []):
        if _named(r.get("roll_call"), "the roll call", said):
            o.put("rollcalls", "record", f"rollcalls/{sitting}/{r['roll_call']}.json",
                  {"format": FORMAT, **r, "ballots": ballots.get(r["roll_call"], [])})
            hashes[BALLOTS][r["roll_call"]] = digest(ballots.get(r["roll_call"], []))
            n_rc += 1
    said.append(f"  {'api/rollcalls/':<28} {len(rc_terms):>9,} terms' rows; {n_rc:,} roll calls of "
                f"{sitting or 'no term'}, a file each, with "
                f"{sum(len(ballots.get(r['roll_call'], ())) for r in by_term.get(sitting, [])):,} "
                "ballots")

    # ---- members: everyone people.json holds
    if people is None:
        said.append(f"  {'api/members/':<28} not written: no people join here (no "
                    f"{db}/Legislators.psv or generated/careers.json)")
    else:
        seats = {}
        for r in read_csv(out / "legislators.csv"):
            if r.get("person"):
                seats[r["person"]] = {**typed(r, AS.API_SEAT), "committees": [
                    c for c in (r.get("committees") or "").split("; ") if c]}
        sponsored = {}
        for r in read_csv(out / "sponsors.csv"):
            if r.get("person"):
                sponsored.setdefault(r["person"], set()).add(
                    (r.get("term", ""), BO.bill_key(r.get("bill")), r.get("bill", ""),
                     r.get("prime") == "1"))
        rows = []
        for p in people:
            who = str(p.get("person") or "")
            if not _named(who, "the person", said):
                continue
            entry = {k: p[k] for k in AS.API_PERSON if k in p}
            rows.append({k: entry[k] for k in AS.API_MEMBER_ROW if k in entry})
            f = {"format": FORMAT, **entry}
            if who in seats:
                f["seat"] = seats[who]
            f["sponsored"] = [{"key": f"{t}/{b}", "prime": prime}
                              for t, _k, b, prime in sorted(sponsored.get(who, ()))]
            o.put("members", "record", f"members/{who}.json", f)
            hashes["members"][who] = record_hash("members", f)
        o.put("members", "rows", "members/index.json", {"format": FORMAT, "members": rows})
        said.append(f"  {'api/members/':<28} {len(rows):>9,} people, a file each; "
                    f"{len(seats):,} with a seat")

    # ---- requests: the session the site lists (meta.json's "requests")
    try:
        meta = json.loads((site / "meta.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        meta = {}
    req = meta.get("requests") if isinstance(meta, dict) and isinstance(meta.get("requests"), dict) else {}
    year = _int(req.get("year"))
    reqs = []
    if req.get("term") and year:
        try:
            reqs = json.loads((site / "idx" / f"{req['term']}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            reqs = []
    if not reqs:
        year = None
        said.append(f"  {'api/requests/':<28} not written: the site lists no bill requests")
    else:
        rows = []
        for r in reqs:
            # Its number is its own page's (build_lsrs, REQUEST_ADDRESS), as
            # build_request_pages reads it: the request/2027-0001 of its address.
            num = str(r.get("address") or "").rsplit("/", 1)[-1]
            nnnn = num.rsplit("-", 1)[-1]
            if not (_named(num, "the request", said) and _named(nnnn, "the request", said)):
                continue
            row, rec = request_record(r, num, year)
            rows.append(row)
            o.put("requests", "record", f"requests/{year}/{nnnn}.json", {"format": FORMAT, **rec})
            # Hashed without the two while they are empty, so a request is
            # changed in the feed the night its text arrives, and not every
            # request the night the fields were added.
            hashes["requests"][num] = record_hash("requests", {
                k: v for k, v in rec.items() if v or k not in ("text", "text_pdf")})
        o.put("requests", "rows", f"requests/{year}/index.json",
              {"format": FORMAT, "year": year, "requests": rows})
        said.append(f"  {'api/requests/':<28} {len(rows):>9,} requests for {year}, a file each")

    # ---- laws: every chapter of the statute table
    if table is None:
        import rsa
        table = rsa.load(Path(db) / "NH_RSA.psv", Path(db) / "_columns.json")
    try:
        cit = json.loads(Path(citations).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cit = None
    if table is None or not isinstance(cit, dict):
        said.append(f"  {'api/laws/':<28} not written: no statute table ({db}/NH_RSA.psv) or no "
                    f"{citations} here")
    else:
        import build_rsa as BR
        files, rows = law_files(table, cit, taken=BR.taken_day(db))
        for ch, f in files.items():
            if _named(ch, "the chapter", said):
                o.put("laws", "record", f"laws/{ch}.json", f)
                hashes["laws"][ch] = record_hash("laws", f)
        o.put("laws", "rows", "laws/index.json", {"format": FORMAT, "chapters": rows})
        said.append(f"  {'api/laws/':<28} {len(files):>9,} chapters, a file each, "
                    f"{sum(len(f['sections']) for f in files.values()):,} sections")

    # ---- the change feed: tonight's hashes against the last accepted build's
    tonight = built[:10]
    led, why = load_ledger(ledger, tonight)
    left, _found = decide(led, hashes, tonight=tonight, built=built)
    nights = change_files(left, tonight, built)
    for name, obj in nights.items():
        o.put("changes", "night", f"{CHANGES}/{name}", obj)
    # The hashes this build leaves, whole or not at all; nightly.py keeps them
    # (nightly.keep_api_hashes) only where it writes the census.
    Path(ledger_out).parent.mkdir(parents=True, exist_ok=True)
    part = Path(ledger_out).with_name(Path(ledger_out).name + ".part")
    part.write_text(json.dumps(left, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n",
                    encoding="utf-8", newline="\n")
    os.replace(part, ledger_out)
    night = left["nights"][tonight]
    said.append(f"  {'api/changes/':<28} {len(nights):>9,} nights; "
                f"{tonight} lists " + ", ".join(f"{len(night['changed'][k]):,} {k}" for k in KINDS)
                + " changed and "
                + f"{sum(len(night['removed'][k]) for k in KINDS):,} gone; the hashes -> "
                + Path(ledger_out).as_posix())
    if led is None:
        said.append(f"    WARNING: the data API's change feed lists nothing tonight: {why}. It "
                    "compares with the hashes nightly.py keeps for a build it accepts, so the next "
                    "night lists against tonight's")

    # ---- the index of it all, last, with tonight's counts
    # The index describes the rest; it is no record, and api_schema's
    # resources are its words.
    o.put("index", "", "index.json", dump(index_file(o, base=base, built=built, sitting=sitting,
                                                      year=year, terms=sorted(terms, reverse=True),
                                                      rc_terms=rc_terms,
                                                      nights=sorted(n[:-5] for n in nights))))
    gone = o.sweep()
    total = sum(o.count.values())
    size = sum(o.bytes.values())
    said.append(f"  {'api/index.json':<28} {total:>9,} files under /api/, {size / 1e6:.1f} MB, in "
                f"{time.time() - t0:.0f} s"
                + (f"; {gone:,} an earlier build left taken away" if gone else ""))
    # What the manifest says of them, under "api", and the /api page reads:
    # each resource's files and bytes, its files of rows by term, and one file
    # a record of it, which the page links.
    summary = {"index": f"{base}/api/index.json", "files": total, "bytes": size,
               "sitting_term": sitting, **({"requests_year": year} if year else {}),
               "resources": [{"name": r["name"], "files": o.count.get(r["name"], 0),
                              "bytes": o.bytes.get(r["name"], 0),
                              **({"terms": len(terms)} if r["name"] == "bills" else
                                 {"terms": len(rc_terms)} if r["name"] == "rollcalls" else {}),
                              **({"example": o.first[r["name"]]} if r["name"] in o.first else {})}
                             for r in AS.API_RESOURCES]}
    return summary, said


def index_file(o, *, base, built, sitting, year, terms, rc_terms, nights=()):
    """/api/index.json: every resource, with its files' addresses filled in
    for tonight, how many files it has, and every field with its stability,
    as schema.json describes them under x-api-records; and the nights the
    change feed carries."""
    fill = {"sitting_term": sitting, "year": str(year or "")}
    res = []
    for r in AS.api_records_schema():
        files = []
        for f in r["files"]:
            path = f["path"]
            for k, v in fill.items():
                path = path.replace("{" + k + "}", v) if v else path
            files.append({**f, "path": path})
        res.append({"name": r["name"], "description": r["description"], "key": r["key"],
                    "files_tonight": o.count.get(r["name"], 0),
                    **({"terms": terms} if r["name"] == "bills" else
                       {"terms": rc_terms} if r["name"] == "rollcalls" else
                       {"year": year} if r["name"] == "requests" and year else
                       {"nights": list(nights)} if r["name"] == "changes" else {}),
                    "files": files})
    return {"format": FORMAT,
            "what": "The New Hampshire General Court's record, a file a record: every bill and "
                    "roll call of the term now sitting, every member, every bill request and every "
                    "chapter of the statutes, beside a file of rows for each, and night by night "
                    "which of them changed. A file holds only the fields promised to stay; "
                    "schema.json describes the same fields.",
            "status": "beta", "stable_from": "2027-02-01", "built": built, "base": base,
            "sitting_term": sitting, **({"requests_year": year} if year else {}),
            "docs": f"{base}/api", "schema": f"{base}/data/schema.json",
            # One wording for every download (api_db.RIGHTS, the owner's).
            "rights": AS.RIGHTS,
            "resources": res}
