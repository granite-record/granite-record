#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-19.1
"""
What the map of a run would have chosen for each past commit, beside what
`preflight.py --changed` (check_select.py) chooses for it today.

    python3 src/checks/map_replay.py --map logs/check-map-all.json.gz
    python3 src/checks/map_replay.py --map M --since 2026-11-01 --ref HEAD \\
        --csv replay.csv --table replay.md
    python3 src/checks/map_replay.py --map M --limit 20    # the newest 20 commits only

THE QUESTION (the refactor's stage 1, step 8; reports/refactor/stage0-checks.md,
sections 5, 6 and 9). Step 9 would choose a change's checks by the map --
what each check was seen to read and run in a full run (preflight's runner,
"the map") -- in place of check_select's reading of their code. Whether that
is worth doing is a number, and this works it out before anything depends on
it: every commit since a day (the non-merge commits of REF, each against its
first parent), the checks each rule chooses, and the seconds those took in
the map's own run.

THE MAP'S RULE, as section 6 states it and as a replay can apply it:
  the core (check_select.CORE), always;
  the scanners (check_select's "reads every code file") when a file of code
    changed, as today;
  a file of the suite (preflight.py, src/checks/suite/pf_*.py): every check
    whose code reaches a top-level definition the change moved, by name, as
    the manifest's second fingerprint reads reach, and every check seen to
    run it; a change to the runner (check_select.RUNNER) or to a statement
    at the top of a suite file that is not an import, every check;
  any other file of Python: every check seen to run a function the change
    moved (a method by its class and name; a function inside another by the
    outer one); and where the change is to the module's own code (outside
    every function: an import, a constant, a class's body), or the file was
    added or removed, every check seen to run any function of it or to
    import it, and every check whose own code names the module or the file
    (check_select's rule without its reach through importers); a change to
    comments or blank lines between definitions moves no function;
  every check seen to read the file as text, for a file of any kind, Python
    included -- the checks that hold a script's words;
  a file added or removed: every check seen to list its folder.

WHAT A REPLAY CANNOT DO. It uses one map, and today's checks and suite, for
every past commit -- as section 5's replay used today's module graph -- so a
check renamed since is not in it, and a check added since is chosen only as
its own code is. Both rules are applied to the checks the map holds; a map of
part of the suite (run_checks_safe.py on a few areas) answers for that part
and says so. The fixture's checks are chosen by any change to a builder
function the fixture's build ran, since a replay builds no fixture; step 9's
"only the checks that read a fixture file whose sha256 changed" would choose
fewer. The seconds are the map's run's, plus check_select's index (10 s) and
one fixture chain (31 s) where a chosen check took the fixture, as section 5
estimated them; a check the map timed under another check's early build is
cheap here and dear alone.

Standard library only. Nothing here asks the network or runs a check; it
reads git and the map, and writes only --csv, --table and its cache of each
script's definitions (--cache, under logs/ by default), keyed by git's blob id.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import ast
import bisect
import csv
import functools
import gzip
import json
import os
import re
import types

import check_select as CS
import child
from pf_core import _PIECE_FROM, _in_suite, _parse_in_pieces, _piece_cuts

INDEX_SECONDS = 10      # check_select's index of the suite, before the first check
CHAIN_SECONDS = 31      # one fixture chain, where a chosen check takes the fixture
FIXTURE_KEPT = ("the early builds", "every builder over the fixture",
                "build_site_v2.py over the fixture")
CACHE = Path("logs/map-replay-units.json.gz")


def _git(args, root):
    r = child.run(["git", *args], cwd=root, capture_output=True, timeout=600)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args[:3])}: {(r.stderr or r.stdout).strip()[:200]}")
    return r.stdout or ""


def load_map(path):
    """The map preflight wrote (pf_runner._map_write): gzip'd JSON, or plain."""
    p = Path(path)
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rt", encoding="utf-8") as fh:
        m = json.load(fh)
    if m.get("format") != 1:
        raise SystemExit(f"{p}: a map of format {m.get('format')!r}, and this reads format 1")
    return m


# ---- a script's definitions, and which of them a change moved ----------------

def units(text):
    """[(first, last, name, kind)] of the top-level statements of a script,
    decorators included, in order; kind is def, class, assign, import or
    other, and a class's methods follow it as (first, last, "Class.m",
    "method"). None where the text will not parse."""
    try:
        tree = _parse_in_pieces(text)[0]
    except SyntaxError:
        return None
    return _units_of(tree.body)


def _units_of(body, at=0):
    """units() of the top-level statements `body`, each `at` lines further on."""
    out = []
    for node in body:
        first = at + min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        last = at + node.end_lineno
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append((first, last, node.name, "def"))
        elif isinstance(node, ast.ClassDef):
            out.append((first, last, node.name, "class"))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    a = at + min([sub.lineno] + [d.lineno for d in sub.decorator_list])
                    out.append((a, at + sub.end_lineno, f"{node.name}.{sub.name}", "method"))
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [t.id for t in targets if isinstance(t, ast.Name)]
            out.append((first, last, ",".join(names) or "<module>", "assign" if names else "other"))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            out.append((first, last, "<import>", "import"))
        else:
            out.append((first, last, "<module>", "other"))
    return out


def units_near(text, lines):
    """units() of the statements that hold `lines`: of the whole text where it
    is short, and where it is long (the suite's one file was 8 MB, and a
    parse of it four seconds) of the pieces around those lines only, cut
    where pf_core cuts a long script, each widened until it parses. None
    where the text will not parse."""
    if len(text) < _PIECE_FROM:
        return units(text)
    every = text.split("\n")
    cuts = [0] + _piece_cuts(every) + [len(every)]
    out, done = [], set()
    for ln in sorted(set(lines)):
        i = bisect.bisect_right(cuts, ln - 1) - 1
        a, b = max(0, min(i, len(cuts) - 2)), max(1, min(i + 1, len(cuts) - 1))
        if any(x <= ln - 1 < y for x, y in done):
            continue
        while True:
            try:
                body = ast.parse("\n".join(every[cuts[a]:cuts[b]]) + "\n").body
                break
            except SyntaxError:
                if a == 0 and b == len(cuts) - 1:
                    return None
                a, b = max(0, a - 1), min(len(cuts) - 1, b + 1)
        done.add((cuts[a], cuts[b]))
        out += _units_of(body, cuts[a])
    return sorted(set(out), key=lambda u: (u[0], u[3] == "method"))


def moved_units(defs, lines):
    """{(name, kind)} of `defs` (units()) that hold one of `lines`; a line in
    no top-level statement is a comment or a blank line, and moves none. A
    line of a class outside its methods is the class's body ("class")."""
    if defs is None:
        return {("<module>", "other")} if lines else set()
    tops = [u for u in defs if u[3] != "method"]
    starts = [u[0] for u in tops]
    out = set()
    for ln in lines:
        i = bisect.bisect_right(starts, ln) - 1
        if i < 0 or not tops[i][0] <= ln <= tops[i][1]:
            continue
        top = tops[i]
        if top[3] == "class":
            meth = [u for u in defs if u[3] == "method" and u[2].startswith(top[2] + ".")
                    and u[0] <= ln <= u[1]]
            out.add((meth[0][2], "method") if meth else (top[2], "class"))
        else:
            out.add((top[2], top[3]))
    return out


class Units:
    """units() of a blob, by git's id, read once and kept (--cache)."""

    def __init__(self, root, cache=None):
        self.root, self.cache = root, Path(cache) if cache else None
        self.known = {}
        if self.cache and self.cache.is_file():
            try:
                with gzip.open(self.cache, "rt", encoding="utf-8") as fh:
                    self.known = {k: (None if v is None else [tuple(u) for u in v])
                                  for k, v in json.load(fh).items()}
            except (OSError, ValueError):
                self.known = {}
        self.new = 0

    def near(self, blob, lines):
        """units_near() of the blob for `lines`: a short script's whole, kept
        by its id; a long one's pieces, worked out each time."""
        if not blob or set(blob) == {"0"} or not lines:
            return []
        if blob in self.known:
            return self.known[blob]
        text = _git(["cat-file", "-p", blob], self.root)
        if len(text) < _PIECE_FROM:
            self.known[blob] = units(text)
            self.new += 1
            return self.known[blob]
        return units_near(text, lines)

    def save(self):
        if self.cache and self.new:
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            part = self.cache.with_name(self.cache.name + ".part")
            with gzip.open(part, "wt", encoding="utf-8") as fh:
                json.dump(self.known, fh, separators=(",", ":"))
            os.replace(part, self.cache)


# ---- the commits, and what each changed ---------------------------------------

def commits(root, ref, since, limit=None):
    """[(sha, date, subject)] of the non-merge commits of `ref` since `since`,
    oldest first."""
    out = _git(["log", "--no-merges", f"--since={since}", "--reverse",
                "--format=%H%x00%cI%x00%s", ref], root)
    rows = [tuple(ln.split("\0", 2)) for ln in out.splitlines() if ln.count("\0") >= 2]
    return rows[-limit:] if limit else rows


HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def changes(root, sha):
    """{path: {"status", "old", "new", "minus": [line], "plus": [line]}} of
    the commit `sha` against its first parent: each file's status (A, M, D),
    its blobs before and after, and for a script the lines the change moved
    on each side."""
    raw = _git(["diff-tree", "-r", "-z", "--raw", "--no-renames", "--no-commit-id", "--root",
                sha], root)
    parts = raw.split("\0")
    files, i = {}, 0
    while i < len(parts) - 1:
        head = parts[i]
        if not head.startswith(":"):
            i += 1
            continue
        _om, _nm, old, new, status = head[1:].split()[:5]
        files[parts[i + 1]] = {"status": status[0], "old": old, "new": new, "minus": [], "plus": []}
        i += 2
    py = [p for p in files if p.endswith(".py")]
    if py:
        parent = _git(["rev-list", "--parents", "-n", "1", sha], root).split()
        base = parent[1] if len(parent) > 1 else "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
        text = _git(["diff", "-U0", "--no-renames", "--no-color", "--no-ext-diff", base, sha,
                     "--", *py], root)
        path = None
        for ln in text.splitlines():
            if ln.startswith("diff --git "):
                path = None
            elif ln.startswith("+++ "):
                name = ln[4:]
                path = name[2:] if name.startswith("b/") else None
            elif ln.startswith("--- ") and path is None:
                name = ln[4:]
                path = name[2:] if name.startswith("a/") else None
            m = HUNK.match(ln)
            if m and path in files:
                a, b = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
                c, d = int(m.group(3)), int(m.group(4) if m.group(4) is not None else 1)
                files[path]["minus"] += range(a, a + b)
                files[path]["plus"] += range(c, c + d)
    return files


# ---- the two rules ------------------------------------------------------------

class Rules:
    """Both rules over the checks the map holds: the suite's files are those
    of `root` (the repository's), or `suite` where a caller names them."""

    def __init__(self, m, root=None, suite=None):
        root = Path(root or _paths.ROOT)
        self.m, self.root = m, root
        self.rows = m["checks"]
        self.names = [r["fn"] for r in self.rows]
        files = [f[0] for f in m["files"]]
        funcs = m["funcs"]
        inv = {k: {} for k in ("reads", "imports", "lists", "starts", "funcs", "func_file", "suite")}
        for i, r in enumerate(self.rows):
            for k in ("reads", "imports", "lists", "starts"):
                for j in r.get(k, ()):
                    inv[k].setdefault(files[j], set()).add(i)
            for j in r.get("funcs", ()):
                key = funcs[j]
                path, _, name = key.partition(":")
                inv["funcs"].setdefault(key, set()).add(i)
                inv["func_file"].setdefault(path, set()).add(i)
                if _in_suite(path):
                    inv["suite"].setdefault(name.split(".", 1)[0], set()).add(i)
        self.inv = inv
        self.everyone = set(range(len(self.rows)))
        self.core = {i for i, n in enumerate(self.names) if n in CS.CORE}
        # The suite today, indexed as check_select indexes it.
        suite = [Path(p) for p in suite] if suite else [root / "preflight.py"] + sorted(
            (root / "src" / "checks" / "suite").glob("pf_*.py"))
        self.suite = suite
        self._trees = {}
        trees = [(os.path.relpath(p.resolve(), root.resolve()).replace(os.sep, "/"), self.parse(p))
                 for p in suite]
        self.index = CS._Index(trees)
        self.index.closure = functools.lru_cache(maxsize=None)(self.index.closure)
        # check_select.choose finds this index under these trees, and so reads
        # each check's reach once for every commit, not once a commit.
        CS._INDEXES.clear()
        CS._INDEXES[tuple(id(t) for _r, t in trees)] = (trees, self.index)
        reach, mods, named, self.scans = {}, {}, {}, set()
        for i, n in enumerate(self.names):
            near = self.index.closure(n) if n in self.index.info else {n}
            for x in near:
                reach.setdefault(x, set()).add(i)
                info = self.index.info.get(x)
                if info:
                    for mo in info["mods"]:
                        mods.setdefault(mo, set()).add(i)
                    for f in info["files"]:
                        named.setdefault(f, set()).add(i)
                    if info["scans"]:
                        self.scans.add(i)
            for mo in self.rows[i].get("needs", ()):
                mods.setdefault(mo, set()).add(i)
        self.reach, self.mods, self.named = reach, mods, named
        self.fake = [{"fn": types.SimpleNamespace(__name__=n), "needs": tuple(r.get("needs", ()))}
                     for n, r in zip(self.names, self.rows)]
        self.fixture = {i for i, r in enumerate(self.rows) if set(r.get("kept", ())) & set(FIXTURE_KEPT)}

    def parse(self, p):
        key = str(p)
        if key not in self._trees:
            self._trees[key] = _parse_in_pieces(Path(p).read_text(encoding="utf-8",
                                                                  errors="replace"))[0]
        return self._trees[key]

    def static(self, files, suite_names):
        """check_select.choose, as --changed runs it, for the commit's files
        and the suite's definitions it moved (by name)."""
        got = CS.choose(self.fake, self.suite, changed=sorted(files), lines={},
                        moved=suite_names, parse=self.parse, root=self.root)
        return set(got["run"])

    def by_map(self, files, moved, script_text=True):
        """{check index: why} of the map's rule (the module's docstring), for
        the commit's `files` (changes()) and `moved` ({path: {(name, kind)}}).
        `script_text` False reads a script read as text as one imported: chosen
        by a change to its own code, not by one inside a function the check
        never ran -- the rule as it would be were the readers of every code
        file (build_exports.repo_facts counting the checks for data.html, in
        the fixture's build) told apart from the readers of one."""
        inv, why = self.inv, {}

        def add(ids, reason):
            for i in ids:
                why.setdefault(i, reason)
        add(self.core, "core")
        if any(p.endswith(CS.CODE_KINDS) for p in files):
            add(self.scans, "reads every code file")
        for p, f in files.items():
            name = p.rsplit("/", 1)[-1]
            st = f["status"]
            if _in_suite(p):
                tops = moved.get(p, set())
                if {n for n, _k in tops} & CS.RUNNER or any(k == "other" for _n, k in tops):
                    add(self.everyone, f"the runner or a suite file's own code ({name})")
                for n, k in tops:
                    if k == "import":
                        continue
                    for one in n.split(".", 1)[0].split(","):
                        add(self.reach.get(one, ()), f"reaches {one}")
                        add(inv["suite"].get(one, ()), f"ran {one}")
                continue
            if script_text or not p.endswith(".py"):
                add(inv["reads"].get(p, ()), f"read {name}")
            if not p.endswith(".py"):
                add(inv["starts"].get(p, ()), f"started {name}")
            else:
                tops = moved.get(p, set())
                whole = st in "AD" or any(k in ("other", "assign", "import", "class") for _n, k in tops)
                for n, k in tops:
                    if k in ("def", "method"):
                        add(inv["funcs"].get(f"{p}:{n}", ()), f"ran {name}:{n}")
                if whole:
                    stem = name[:-3]
                    add(inv["func_file"].get(p, ()), f"ran {name}, whose own code changed")
                    add(inv["imports"].get(p, ()), f"imported {name}")
                    if not script_text:
                        add(inv["reads"].get(p, ()), f"read {name}")
                    add(inv["starts"].get(p, ()), f"started {name}")
                    add(self.mods.get(stem, ()), f"names {stem}")
                    add(self.named.get(p, set()) | self.named.get(name, set()), f"names {name}")
            if st in "AD":
                folder = p.rsplit("/", 1)[0] if "/" in p else "."
                add(inv["lists"].get(folder, ()), f"lists {folder}")
        return why

    def seconds(self, ids):
        s = sum(float(self.rows[i].get("seconds") or 0) for i in ids) + INDEX_SECONDS
        return s + (CHAIN_SECONDS if ids & self.fixture else 0)


def replay(m, root, ref="HEAD", since="2026-11-01", limit=None, cache=CACHE, say=print):
    """[row] of every commit (commits()): each rule's checks and seconds."""
    rules = Rules(m, root)
    known = Units(root, cache)
    out = []
    todo = commits(root, ref, since, limit)
    for n, (sha, date, subject) in enumerate(todo, 1):
        files = changes(root, sha)
        moved = {}
        for p, f in files.items():
            if p.endswith(".py"):
                moved[p] = moved_units(known.near(f["old"], f["minus"]), f["minus"]) | moved_units(
                    known.near(f["new"], f["plus"]), f["plus"])
        suite_names = set()
        for p, tops in moved.items():
            if _in_suite(p):
                suite_names |= {one for nm, k in tops if k != "import"
                                for one in nm.split(".", 1)[0].split(",")}
        static = rules.static(files, suite_names)
        why = rules.by_map(files, moved)
        mp = set(why)
        mq = set(rules.by_map(files, moved, script_text=False))
        kinds = {}
        for reason in why.values():
            k = "reads every code file" if reason == "reads every code file" else reason.split(" ", 1)[0]
            kinds[k] = kinds.get(k, 0) + 1
        out.append({"commit": sha[:10], "date": date[:10], "subject": subject[:90],
                    "files": len(files), "suite": any(_in_suite(p) for p in files),
                    "static": len(static), "map": len(mp),
                    "static_s": round(rules.seconds(static)), "map_s": round(rules.seconds(mp)),
                    "map_code": len(mq), "map_code_s": round(rules.seconds(mq)),
                    "map_only": len(mp - static), "static_only": len(static - mp),
                    "map_why": "; ".join(f"{k} {v}" for k, v in sorted(kinds.items(),
                                                                        key=lambda x: -x[1])),
                    "map_only_names": " ".join(sorted(rules.names[i] for i in mp - static)[:8])})
        if n % 25 == 0:
            say(f"  {n} of {len(todo)} commits")
            known.save()
    known.save()
    return rules, out


def _pct(xs, q):
    """The nearest-rank percentile `q` of `xs`."""
    import math
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, math.ceil(q * len(xs)) - 1))] if xs else 0


def table(rules, rows, m):
    """The summary, as markdown: section 5's table, for each rule."""
    n = len(rules.rows)
    whole = sum(float(r.get("seconds") or 0) for r in rules.rows)
    lines = [f"Map: {m.get('kind')} run at {str(m.get('commit'))[:10]}, {m.get('finished')}; "
             f"{n} checks, {whole:.0f} s of checks in all"
             + ("" if not m.get("dirty") else f"; {len(m['dirty'])} files changed in its tree")
             + ".", "",
             f"Commits: {len(rows)} non-merge, "
             f"{rows[0]['date'] if rows else '-'} to {rows[-1]['date'] if rows else '-'}.", "",
             "| commits | rule | chosen, median / p75 / p90 | est. seconds, median / p75 / p90 "
             "| over half the checks | under 3 min | under 5 min |",
             "|---|---|---|---|---|---|---|"]
    for label, part in (("all", rows), ("touching the suite", [r for r in rows if r["suite"]]),
                        ("not touching it", [r for r in rows if not r["suite"]])):
        if not part:
            continue
        for rule, k in (("today's (check_select)", "static"), ("the map's", "map"),
                        ("the map's, a script read as text as its code", "map_code")):
            ch, sec = [r[k] for r in part], [r[k + "_s"] for r in part]
            lines.append(
                f"| {label} ({len(part)}) | {rule} | {_pct(ch, .5)} / {_pct(ch, .75)} / {_pct(ch, .9)} "
                f"| {_pct(sec, .5)} / {_pct(sec, .75)} / {_pct(sec, .9)} "
                f"| {sum(1 for c in ch if c > n / 2)} | {sum(1 for s in sec if s < 180)} "
                f"| {sum(1 for s in sec if s < 300)} |")
    more = [r for r in rows if r["map_only"]]
    lines += ["", f"The map chose a check today's rule did not in {len(more)} of {len(rows)} commits "
              f"(median {_pct([r['map_only'] for r in more], .5) if more else 0} such checks); today's "
              f"chose one the map did not in {sum(1 for r in rows if r['static_only'])}."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--map", required=True, help="the map a full run wrote (logs/check-map-all.json.gz)")
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--since", default="2026-11-01")
    ap.add_argument("--limit", type=int, help="only the newest N commits")
    ap.add_argument("--csv", help="write each commit's row here")
    ap.add_argument("--table", help="write the summary (markdown) here")
    ap.add_argument("--cache", default=str(CACHE), help="each script's definitions, by blob id")
    a = ap.parse_args()
    m = load_map(a.map)
    root = _paths.ROOT
    rules, rows = replay(m, root, a.ref, a.since, a.limit, a.cache,
                         say=lambda s: print(s, file=sys.stderr))
    text = table(rules, rows, m)
    if a.csv:
        with open(a.csv, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["commit"])
            w.writeheader()
            w.writerows(rows)
    if a.table:
        Path(a.table).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
