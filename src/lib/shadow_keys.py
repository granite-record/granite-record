#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.1
"""
What a cache would have done tonight, with nothing taken from one.

    python3 build_all.py --local                # works the keys out (logs/shadow-keys.json.gz)
    python3 src/lib/shadow_keys.py              # this build's against the night's kept ones
    python3 src/lib/shadow_keys.py --why        # ... and why each unit would have rebuilt

THE SHADOW (16 November 2026, the refactor's build design, step S3, and the
owner's yes to its question 5: no cache restores anything until a week of
real nights shows no mismatch). Each step the design names as cacheable
(STEPS, its section 2.4) has its key worked out after it runs, as a cache
would key it, and the hash of what it made: for each finished term it holds
a part of (a unit), and for the step whole. The keys go to THIS, the night
keeps them as KEPT (a state file, cloud_kit.json), and the next build
compares its own with them, unit by unit:

  taken      the key is last night's: a cache would have restored the unit;
  rebuilt    the key moved, and the record says which of its parts did;
  new        no earlier key to compare with;
  mismatch   the key is last night's and the output is not -- the key misses
             something the unit depends on. Named in site/build.json's
             "shadow_keys", the build's output and the night's verdict
             ("shadow_keys"); nothing was restored, so the site is as built.

A UNIT'S KEY is a sha256 of (the design's list, 2.4):
  - its code: build_cache.signature of the step's script and of every script
    of this project it ran as a child, which build_io records, with
    requirements.txt;
  - the settings file (src/lib/state_settings.json);
  - its term and the build's sitting term (GRANITE_TERM);
  - the term's frozen manifests (build_all.frozen_manifests);
  - every input it read (build_io.merge's record): a file by its sha256, or by
    its term's part where its top level is keyed by term or year (a {term:
    ...} file), with the part no term owns; a file the step removed by the
    bytes it held before (build_io's "before"); a folder listed by its names; a
    path looked for by whether it is there; a database by its sha256;
  - the day, if the step asked build_date.py for it -- in each of the step's
    units, since the record cannot tell which term's part asked;
  - the GRANITE_ and GITHUB_ settings it read, with their values.
A file the step both read and wrote is its own output -- what it merged into --
and is not an input. A file an earlier keyed step wrote, and no step since has
written or removed (by their records), is keyed by that step's hash of it,
which is how the bill pages' 33,717 inputs, the site data's bill files that
the step removes once read, are known without being hashed twice (Keys.known,
which build_all.py hands a keyed step in build_io.KEYED so that its processes
keep no hash of them either). An input or output belongs to a term by its path (a
folder or name that is a term, a year, or a day) or by its part; one that
belongs to none is in every unit's key, and an output that belongs to none
is said ("kept whole only"). A step whose outputs belong to no term has only
its whole unit, which holds the sitting term and which the design never
caches; its key is kept all the same, for how often it would have held.

The term a path names is read off its shape (term_of): a guess, which the
shadow week is there to test -- a unit whose key repeats while its output
moves is exactly that guess failing.

NOTHING IS RESTORED. This module reads, hashes and compares; build_all.py
calls it between steps, after each named step has run, and the site is the
same with it and without it (build_all.py --no-record works no key out).

Standard library and this project's build_cache, terms and _paths only; it
asks the network nothing.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import gzip
import hashlib
import json
import os
import re
import time

import build_cache as BC
import terms

FORMAT = 1
# This build's keys, and the last real night's, which the night keeps.
THIS = Path("logs/shadow-keys.json.gz")
KEPT = Path("archive/shadow-keys.json.gz")
# A unit that is a whole step, beside its finished terms.
WHOLE = "whole"
# The steps the design names as cacheable (design-build-2026-11-16.md, 2.4),
# by their script and an argument that picks the step out of the plan where a
# script is more than one step, each with what the design calls it.
STEPS = (
    (("build_data.py", "--frozen-terms"), "the frozen-term pass"),
    (("narrate_archive.py",), "the data phase: archived histories"),
    (("journal_motions.py",), "the data phase: Journal motions by year"),
    (("report_check.py",), "the data phase: the report check"),
    (("extract_chapters.py",), "the data phase: chapters"),
    (("rollcall_parser.py",), "the data phase: roll calls"),
    (("build_search_index.py",), "a pure function: the search index per term"),
    (("build_site_v2.py",), "the page phase, as bundles: the site data's bills"),
    (("build_bill_pages.py",), "the page phase, as bundles: bill pages"),
    (("build_session_pages.py",), "the page phase, as bundles: session days"),
)
# How many inputs a unit's rebuilt line names, how long a hash the state keeps
# of each input for saying which moved (the key itself is whole), and how many
# threads hash a step's files.
NAMED = 3
SHORT = 16
HASHERS = 8


def kind(args):
    """What the design calls the step whose arguments are `args`, or None
    for a step it does not name as cacheable."""
    for (script, *flags), what in STEPS:
        if args and args[0] == script and all(f in args for f in flags):
            return what
    return None


# ---- a path's term ------------------------------------------------------------

_YEAR = re.compile(r"(?:19|20)\d\d")
_TERM_IN = re.compile(r"(?:^|[_.-])(\d{4}-\d{4})(?=[_.-]|$)")
_DAY_AT = re.compile(r"^(\d{4}-\d\d-\d\d)(?=[_.]|$)")
_YEAR_IN = re.compile(r"(?:^|[_-])((?:19|20)\d\d)(?=[_.-]|$)")


def term_of(path):
    """The term a path of the working folder belongs to by its shape, or
    None: a folder or a file's stem that is a term ("site/idx/2019-2020.json",
    "frozen/2023-2024/..."); a folder that is a year ("site/bill/2019/HB1.html",
    "journals/2019/..."); a term in a file's name ("Docket_db_2013-2014.txt");
    a day it opens with ("session/H/2019-03-14.html", by Organization Day's
    rule); a year in its name between separators ("RollCallSummary_1999.txt",
    not "HB1999.html")."""
    parts = str(path).replace("\\", "/").split("/")
    folders, name = parts[:-1], parts[-1]
    stem = name.split(".", 1)[0]
    for p in folders + [stem]:
        if terms.is_key(p):
            return p
    for p in folders:
        if _YEAR.fullmatch(p):
            return terms.term_of_year(p)
    m = _TERM_IN.search(name)
    if m and terms.is_key(m.group(1)):
        return m.group(1)
    m = _DAY_AT.match(name)
    if m:
        return terms.key_on(m.group(1)) or None
    m = _YEAR_IN.search(name)
    if m:
        return terms.term_of_year(m.group(1))
    return None


# ---- hashing ------------------------------------------------------------------

def file_sha(p):
    """The sha256 of a file's bytes; "" where it will not read."""
    h = hashlib.sha256()
    try:
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


_WS = re.compile(r"[ \t\n\r]*")
_KEY_YEAR = re.compile(r"(?:19|20)\d\d")
_FIRST_KEY = re.compile(r'﻿?[ \t\n\r]*\{[ \t\n\r]*"((?:[^"\\]|\\.)*)"')


def json_parts(path):
    """{term: sha256 of its part, "": of the part no term owns} of a JSON
    file whose top level is an object keyed, at least in part, by term or by
    year (a year's part is its term's); None for any other file. Each part
    is a sha256 of its keys and their values' bytes as written, in order --
    no value is kept, and one is parsed only to find where it ends. A file
    whose first key is neither a term, a year nor a note ("_about") is not
    read past its head: data/member_votes.json is 560 MB of a list."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(1 << 16).decode("utf-8", "replace")
    except OSError:
        return None
    m = _FIRST_KEY.match(head)
    if not m or not (terms.is_key(m.group(1)) or _KEY_YEAR.fullmatch(m.group(1))
                     or m.group(1).startswith("_")):
        return None
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    dec = json.JSONDecoder()
    i = _WS.match(text, 0).end()
    if i >= len(text) or text[i] != "{":
        return None
    i = _WS.match(text, i + 1).end()
    hashes = {}
    try:
        while i < len(text) and text[i] != "}":
            key, i = json.decoder.scanstring(text, i + 1)
            i = _WS.match(text, i).end()
            if text[i] != ":":
                return None
            i = _WS.match(text, i + 1).end()
            _value, j = dec.raw_decode(text, i)
            t = key if terms.is_key(key) else (terms.term_of_year(key)
                                               if _KEY_YEAR.fullmatch(key) else "")
            h = hashes.get(t)
            if h is None:
                h = hashes[t] = hashlib.sha256()
            h.update(key.encode("utf-8", "surrogatepass") + b"\0")
            h.update(text[i:j].encode("utf-8", "surrogatepass") + b"\0")
            i = _WS.match(text, j).end()
            if i < len(text) and text[i] == ",":
                i = _WS.match(text, i + 1).end()
    except (ValueError, IndexError):
        return None
    if not any(t for t in hashes):
        return None
    return {t: h.hexdigest() for t, h in hashes.items()}


class Keys:
    """This build's shadow keys, step by step, worked out as each named step
    finishes (step), and the document THIS holds (document)."""

    def __init__(self, sitting, frozen, day, root="."):
        self.sitting, self.frozen, self.day = sitting or "", dict(frozen or {}), day
        self.root = Path(root)
        self.settings = file_sha(_paths.locate("src/lib/state_settings.json"))
        self.requirements = file_sha(_paths.ROOT / "requirements.txt")
        self.steps = {}
        self.seconds = 0.0
        self._imports, self._tokens, self._sigs, self._found = {}, {}, {}, {}
        self._parts = {}
        # {path: sha256} of what a keyed step wrote, while no step since has
        # written or removed it (saw): a later step's input by those bytes,
        # hashed once -- the site data's 33,717 bill files, which the bill
        # pages read and remove.
        self.known = {}

    def saw(self, rec):
        """A step's record, every step's in the order they ran, keyed or not:
        what it wrote or removed is no longer what a keyed step wrote."""
        for key in ("wrote", "removed", "made"):
            for rel in rec.get(key) or []:
                self.known.pop(rel, None)

    def known_paths(self):
        """The absolute paths of `known`, as a step's processes name them, for
        them to keep no hash of (build_io.KEYED)."""
        return sorted(os.path.abspath(self.root / rel) for rel in self.known)

    # The code a step runs: build_cache.signature, with each module found, read
    # and parsed once a build however many steps import it (the page steps'
    # closures are about 110 modules each, and nearly the same ones).
    def _find(self, name):
        if name not in self._found:
            self._found[name] = _paths.find(name)
        return self._found[name]

    def _modules(self, names):
        out, todo = {}, [n if n.endswith(".py") else n + ".py" for n in names]
        while todo:
            name = todo.pop()
            if name in out:
                continue
            p = self._find(name)
            if p is None:
                raise LookupError(f"shadow_keys: no code file named {name}")
            out[name] = p
            key = str(p)
            if key not in self._imports:
                self._imports[key] = BC._imports(p)
            todo += [f"{m}.py" for m in self._imports[key]
                     if f"{m}.py" not in out and self._find(f"{m}.py") is not None]
        return dict(sorted(out.items()))

    def signature(self, *names):
        """build_cache.signature(*names), the same sha256."""
        key = tuple(sorted(set(names)))
        if key not in self._sigs:
            h = hashlib.sha256(f"format {BC.FORMAT}\0{sys.version}\0".encode("utf-8"))
            for name, p in self._modules(key).items():
                if str(p) not in self._tokens:
                    self._tokens[str(p)] = BC._tokens(p)
                h.update(f"\0{name}\0".encode("utf-8"))
                h.update(self._tokens[str(p)].encode("utf-8"))
            self._sigs[key] = h.hexdigest()
        return self._sigs[key]

    def _parts_of(self, rel, sha):
        """The term parts of a file of the working folder whose bytes are
        `sha`, where it is a {term: ...} JSON file named for no term; None
        otherwise. Worked out once a build for the same bytes."""
        p = self.root / rel
        if not sha or not rel.endswith(".json") or term_of(rel) is not None or not p.is_file():
            return None
        if sha not in self._parts:
            got = json_parts(p)
            # A part is only of the bytes hashed: the file must not have moved since.
            self._parts[sha] = got if got is not None and file_sha(p) == sha else None
        return self._parts[sha]

    def _shas(self, rels):
        """{path: sha256} of files of the working folder, read by a few
        threads: hashing a step's 30,000 saved pages one at a time took 33 s
        on the laptop, where the opening of each file is most of the cost."""
        if len(rels) < 64:
            return {r: file_sha(self.root / r) for r in rels}
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=HASHERS) as pool:
            return dict(zip(rels, pool.map(lambda r: file_sha(self.root / r), rels)))

    def step(self, name, args, rec):
        """Work out the keys of the named step `name`, which ran with `args`
        and left the record `rec` (build_io.merge's)."""
        t0 = time.time()
        what = kind(args)
        code = BC.digest(self.signature(args[0], *rec.get("scripts") or []), self.requirements)
        wrote = set(rec.get("wrote") or [])
        before = rec.get("before") or {}
        read = [rel for rel in rec.get("read") or [] if rel not in wrote]
        sqlite = [rel for rel in rec.get("sqlite") or {} if rel not in wrote]
        known = {rel: self.known[rel] for rel in read + sqlite if rel in self.known}
        shas = {**known, **self._shas([r for r in read + sqlite if r not in known] + sorted(wrote))}
        # Inputs: (path, the term it belongs to or None, hash, parts or None).
        inputs = []
        for rel in read:
            if shas.get(rel):
                inputs.append((rel, term_of(rel), shas[rel], self._parts_of(rel, shas[rel])))
            else:
                # Gone (the step removed it): the bytes it read, where its process kept them.
                inputs.append((rel, term_of(rel), before.get(rel) or "unknown", None))
        for rel in sqlite:
            inputs.append((rel, term_of(rel), shas.get(rel) or "-", None))
        for rel in rec.get("listed") or []:
            pre = rel.rstrip("/") + "/"
            if rel == "." or any(w.startswith(pre) for w in wrote):
                continue            # the step's own folder, which it wrote into
            try:
                names = sorted(os.listdir(self.root / rel))
            except OSError:
                names = None
            inputs.append((rel + "/", term_of(rel + "/x"), "-" if names is None else
                           BC.digest(*names), None))
        for rel in rec.get("looked") or []:
            inputs.append((rel, term_of(rel), "+" if (self.root / rel).exists() else "-", None))
        outputs = [(rel, term_of(rel), shas.get(rel, ""), self._parts_of(rel, shas.get(rel, "")))
                   for rel in sorted(wrote)]
        env = BC.digest(*[f"{k}\0{v}" for k, v in sorted((rec.get("env") or {}).items())])
        # The day is the step's: the record cannot say which term's part asked for it.
        day = self.day if rec.get("day") else ""
        # A unit is a finished term some output belongs to, by its path or as a part.
        owned = set()
        for _rel, t, _sha, parts in outputs:
            owned |= {t} | set(parts or {})
        finished = sorted(t for t in owned if t and terms.is_key(t) and self.sitting
                          and t < self.sitting)
        units = {}
        for unit in [WHOLE] + finished:
            def mine(t, parts):
                if unit == WHOLE:
                    return True
                return t == unit or (t is None and (not parts or unit in parts or "" in parts))
            ins = {}
            for rel, t, sha, parts in inputs:
                if not mine(t, parts):
                    continue
                if unit == WHOLE or not parts:
                    ins[rel] = sha
                else:
                    ins[rel] = f"{parts.get(unit, '-')}|{parts.get('', '-')}"
            outs = {}
            for rel, t, sha, parts in outputs:
                if unit == WHOLE:
                    outs[rel] = sha
                elif t == unit:
                    outs[rel] = sha
                elif t is None and parts and unit in parts:
                    outs[rel + "#" + unit] = parts[unit]
            keyed = {"code": code, "settings": self.settings, "term": unit, "sitting": self.sitting,
                     "frozen": self.frozen.get(unit, "") if unit != WHOLE else
                     BC.digest(*[f"{t}\0{h}" for t, h in sorted(self.frozen.items())]),
                     "inputs": BC.digest(*[f"{p}\0{h}" for p, h in sorted(ins.items())]),
                     "day": day, "env": env}
            unknown = sorted(p for p, h in ins.items() if "unknown" in h)
            units[unit] = {
                "key": "unknown" if unknown else BC.digest(*[f"{k}={v}" for k, v in sorted(keyed.items())]),
                "out": BC.digest(*[f"{p}\0{h}" for p, h in sorted(outs.items())]),
                "parts": keyed, "inputs": len(ins), "outputs": len(outs),
                **({"unknown": unknown[:NAMED]} if unknown else {})}
        shared = sorted(rel for rel, t, _sha, parts in outputs if t is None and not parts)
        self.saw(rec)
        self.known.update({rel: sha for rel, _t, sha, _p in outputs if sha})
        # Each input once, by a short hash, and a {term: ...} one's parts, for saying which
        # moved: the keys above are of the whole hashes.
        self.steps[name] = {
            "kind": what, "script": args[0], "units": units,
            "inputs": {rel: sha[:SHORT] for rel, _t, sha, _p in inputs},
            "parts": {rel: {t: h[:SHORT] for t, h in sorted(parts.items())}
                      for rel, _t, _s, parts in inputs if parts},
            "shared_out": len(shared), "shared_some": shared[:NAMED]}
        self.seconds += time.time() - t0
        return self.steps[name]

    def document(self, run="", commit=""):
        """What THIS holds: the build's day, sitting term, run and commit, and
        every named step's units."""
        return {"format": FORMAT, "day": self.day, "sitting": self.sitting, "run": str(run or ""),
                "commit": str(commit or ""), "steps": self.steps}


# ---- keeping and comparing ------------------------------------------------------

def write(doc, path=THIS):
    """`doc` gzipped, with no time in its header, written whole and renamed
    into place; its size."""
    raw = gzip.compress(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                        mtime=0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(raw)
    os.replace(tmp, path)
    return len(raw)


def read(path=KEPT):
    """The keys kept at `path`, or None where there are none that read."""
    try:
        doc = json.loads(gzip.decompress(Path(path).read_bytes()).decode("utf-8"))
    except (OSError, ValueError, EOFError):
        return None
    return doc if isinstance(doc, dict) and doc.get("format") == FORMAT else None


def moved(now, was, unit):
    """The inputs of `unit` whose hash differs between two nights' records of
    a step, `now` and `was`: for a finished term, those of its term or of none,
    and of a {term: ...} file its own part and the part no term owns."""
    a, b = now.get("inputs") or {}, (was or {}).get("inputs") or {}
    pa, pb = now.get("parts") or {}, (was or {}).get("parts") or {}
    out = []
    for path in sorted(set(a) | set(b)):
        if unit != WHOLE and (path in pa or path in pb):
            x, y = pa.get(path) or {}, pb.get(path) or {}
            if x.get(unit) != y.get(unit) or x.get("") != y.get(""):
                out.append(path)
            continue
        if unit != WHOLE and term_of(path + "x" if path.endswith("/") else path) not in (unit, None):
            continue
        if a.get(path) != b.get(path):
            out.append(path)
    return out


def compare(doc, kept):
    """{"compared_with", "units", "taken", "rebuilt", "new", "mismatched",
    "steps": {step: {"units", "taken", "rebuilt", "new", "why", "moved",
    "whole"}}} of this build's keys against the kept ones: finished-term
    units counted apart from each step's whole one (WHOLE), which holds the
    sitting term and is said as "whole"."""
    kept_steps = (kept or {}).get("steps") or {}
    out = {"compared_with": ({k: kept.get(k) for k in ("day", "run", "commit")} if kept else None),
           "units": 0, "taken": 0, "rebuilt": 0, "new": 0, "mismatched": [], "steps": {}}
    for step, s in sorted((doc.get("steps") or {}).items()):
        prev = (kept_steps.get(step) or {}).get("units") or {}
        st = {"units": 0, "taken": 0, "rebuilt": 0, "new": 0, "why": {}, "moved": []}
        for unit, u in sorted(s["units"].items()):
            p = prev.get(unit)
            if p is None:
                said = "new"
            elif p.get("key") == u["key"] and u["key"] != "unknown":
                said = "taken"
                if p.get("out") != u["out"]:
                    out["mismatched"].append(f"{step}: {unit}")
                    said = "mismatch"
            else:
                said = "rebuilt"
                why = [k for k, v in sorted(u["parts"].items()) if (p.get("parts") or {}).get(k) != v]
                if u["key"] == "unknown":
                    why = ["unknown"]
                for k in why:
                    st["why"][k] = st["why"].get(k, 0) + 1
                if "inputs" in why:
                    for path in moved(s, kept_steps.get(step), unit):
                        if path not in st["moved"]:
                            st["moved"].append(path)
            if unit == WHOLE:
                st["whole"] = said
                continue
            st["units"] += 1
            st["taken" if said in ("taken", "mismatch") else said] += 1
        st["moved"] = st["moved"][:NAMED]
        out["steps"][step] = st
        for k in ("units", "taken", "rebuilt", "new"):
            out[k] += st[k]
    return out


WHY_WORDS = {"code": "its code changed", "settings": "the settings changed",
             "term": "its term", "sitting": "the sitting term changed",
             "frozen": "a frozen term's manifests changed", "inputs": "its inputs moved",
             "day": "it reads the day", "env": "a setting it reads changed",
             "unknown": "an input's earlier bytes were not kept"}


def said(cmp):
    """The lines the build prints of a comparison: one a step, then each
    mismatch."""
    lines = []
    if cmp["compared_with"] is None:
        lines.append(f"shadow keys: no earlier night's to compare with ({KEPT.as_posix()}); "
                     f"{sum(1 for _ in cmp['steps'])} steps keyed, nothing taken from any cache")
    for step, st in cmp["steps"].items():
        if cmp["compared_with"] is None:
            continue
        head = (f"{st['units']} finished term(s): {st['taken']} would have been taken from a "
                f"cache, {st['rebuilt']} rebuilt" + (f", {st['new']} new" if st["new"] else "")
                if st["units"] else "no finished term's part of its own")
        why = ", ".join(f"{WHY_WORDS.get(k, k)} ({n})" for k, n in sorted(st["why"].items()))
        lines.append(f"shadow: '{step}': {head}; whole, {st.get('whole', 'new')}"
                     + (f"; rebuilt as {why}" if why else "")
                     + (f"; moved: {', '.join(st['moved'])}" if st["moved"] else ""))
    for m in cmp["mismatched"]:
        lines.append(f"SHADOW MISMATCH: {m} kept its key and its output changed: the key misses "
                     "something it depends on. Nothing was taken from a cache, so the site is as "
                     "built; logs/shadow-keys.json.gz holds both nights' parts")
    return lines


def digest(cmp, size, seconds):
    """What site/build.json's "shadow_keys" carries: small, the counts and the
    mismatches."""
    return {"file": THIS.as_posix(), "bytes": size, "seconds": round(seconds, 1),
            "compared_with": cmp["compared_with"], "units": cmp["units"], "taken": cmp["taken"],
            "rebuilt": cmp["rebuilt"], "new": cmp["new"], "mismatched": cmp["mismatched"][:20],
            "steps": {s: {k: v for k, v in st.items() if k != "moved" and v not in ({}, [])}
                      for s, st in cmp["steps"].items()}}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="this build's shadow keys against the night's kept ones")
    ap.add_argument("--this", default=str(THIS))
    ap.add_argument("--kept", default=str(KEPT))
    ap.add_argument("--why", action="store_true", help="each unit that would have rebuilt, and why")
    a = ap.parse_args()
    doc = read(a.this)
    if doc is None:
        print(f"{a.this}: no keys to read")
        return 1
    kept = read(a.kept)
    cmp = compare(doc, kept)
    for line in said(cmp):
        print(line)
    if a.why and kept:
        for step, s in sorted(doc["steps"].items()):
            prev = ((kept.get("steps") or {}).get(step) or {}).get("units") or {}
            for unit, u in sorted(s["units"].items()):
                p = prev.get(unit) or {}
                moved = [k for k, v in sorted(u["parts"].items()) if (p.get("parts") or {}).get(k) != v]
                if p and moved:
                    print(f"  {step} {unit}: {', '.join(moved)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
