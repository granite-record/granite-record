#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-09.1
"""
Which of preflight's checks a change can reach: `preflight.py --changed`.

    python3 preflight.py --changed            # since the merge base with dev
    python3 preflight.py --changed HEAD~1     # since any commit
    python3 preflight.py --changed --code     # the code checks among them

THE PERSON'S ASK (9 October 2026): stop waiting on checks a change cannot
reach. A run of every check is minutes on the laptop, most of them about
files the change never touched. This chooses the checks a change can reach
and runs those, and says plainly that it is not the full suite: the full
suite is still what goes before a merge into dev, and the default run of
preflight is still all of it.

WHAT IS CHOSEN. The files changed since BASE -- `git diff BASE` with the
working tree, and the files git sees that it does not track -- and then:

  1. THE CORE, always (CORE below, said by name in every run): the guards of
     the repository as a whole -- the version stamps, the control bytes, the
     credential, address and history checks, the private files kept out of
     git, the refusal guards, the hand-made-files guard, the scripts that
     must parse, import, carry the bootstrap and start one another by name,
     the child processes' encoding and seal, the licensed logo, the triage
     rules and the running-fetch one-liner. None reads one file a change
     names; each reads every file of a kind, so any change can break it.
  2. A CHECK THAT READS EVERY CODE FILE (a scanner: what it runs walks the
     code folders, git's list, or a glob of the tree) wherever a file of code
     or a document changed.
  3. A CHECK RELATED TO WHAT CHANGED: one whose `needs=` names a module the
     change reaches, or whose code -- with every helper of preflight's it
     calls, and the helpers they call -- names such a module ("x.py",
     imp("x"), import x) or a changed file by its name or its path. A module
     is reached by a change to itself, or to a module it imports, however
     far down; and one hop of a launch ("x.py" in a script that starts it).
     Docstrings are not read: they are prose, and name half the repository.
  4. A CHECK WHOSE OWN LINES MOVED, or those of a helper it calls, where
     preflight.py itself changed. A change to the runner (main, check, imp)
     runs every check.

What it cannot see: a check that reaches a file without naming it -- a
fixture laid out by a helper that walks a folder, a builder another builder
starts. The scanners and the fixture's helpers (which name every builder)
are most of those; the rest is why the full suite still runs before a merge.

Nothing here runs a check, writes a file or asks the network.
"""

import ast
import os
import re
import subprocess
from pathlib import Path

import _paths
import child

# The always-run guards, by function name. Each is a check of the repository
# as a whole; preflight's _changed_selects fails when one of these names is no
# longer a check, so a rename cannot drop one from every --changed run.
CORE = (
    "_one_address", "_history_addresses", "_no_secrets", "_private_untracked",
    "_clerk_list_untracked",                        # credentials, addresses, private files
    "_parse_all", "_import_all", "_code_names_unique", "_runner_names_resolve",
    "_bootstrap_first", "_root_and_launch_rules", "_dash_c_imports_paths",
    "_network_boundaries", "_code_not_ignored",     # the scripts as scripts
    "_stamps",                                      # the version stamps
    "_record_untouched",                            # the hand-made files
    "_no_control_bytes",                            # control bytes
    "_child_encoding", "_children_sealed",          # children: encoding, the seal
    "_every_fetcher_checks_refusal", "_every_fetcher_notes_refusal",   # the refusal guards
    "_logo_licence", "_triage_rules", "_running_oneliner",
)

# What a scanner calls, or names: the code folders, a walk of the tree,
# git's list of it, and preflight's own readers of all of them.
SCAN_CALLS = {"_paths.code_files", "_paths.code_dirs", "os.walk", "_tracked",
              "_project_modules", "_runner_names", "_scripts_run"}
SCAN_WORDS = ("ls-files",)
# Whose change is a change to the runner itself.
RUNNER = {"main", "check", "imp", "_run", "CHECKS"}

FILE_RX = re.compile(r"[\w./-]*?[\w-]+\.(?:py|js|css|html|json|jsonl|csv|psv|txt|md|yml|yaml"
                     r"|bat|toml|xml|webmanifest)\b")
IMPORT_RX = re.compile(r"^[ \t]*(?:from[ \t]+([A-Za-z_]\w*)|import[ \t]+([A-Za-z_][\w \t,.]*))",
                       re.M)
NAMED_RX = re.compile(r"""(?:__import__|imp)\(\s*["']([A-Za-z_]\w*)["']""")
LAUNCH_RX = re.compile(r"""["']([A-Za-z_]\w*)\.py["']""")
CODE_KINDS = (".py", ".js", ".css", ".html", ".md", ".bat", ".yml", ".yaml", ".toml")


def _git(args, root):
    r = child.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(r.stderr or r.stdout).strip()[:200]}")
    return r.stdout or ""


def merge_base(base, root="."):
    """The commit the change is measured from: BASE, or where none is given
    the merge base of HEAD and dev (origin/dev where there is no local dev)."""
    if base:
        return _git(["rev-parse", "--verify", base + "^{commit}"], root).strip()
    for ref in ("dev", "origin/dev"):
        try:
            return _git(["merge-base", "HEAD", ref], root).strip()
        except RuntimeError:
            continue
    raise RuntimeError("no BASE given, and no dev or origin/dev to take the merge base with")


def changed_files(base, root="."):
    """Every path changed since `base` (a commit), in the working tree as it
    stands -- added, changed, removed -- and every file git sees that it does
    not track, sorted."""
    out = set(n for n in _git(["diff", "--name-only", "-z", "--no-renames", base], root)
              .split("\0") if n)
    out |= set(n for n in _git(["ls-files", "-z", "--others", "--exclude-standard"], root)
               .split("\0") if n)
    return sorted(out)


def changed_lines(base, path, root="."):
    """[(first, last)] of the lines of `path` as it stands that differ from
    `base`; a removal is the line it was removed before."""
    text = _git(["diff", "-U0", "--no-renames", base, "--", path], root)
    spans = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", text, re.M):
        start, n = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
        spans.append((start, start + max(n, 1) - 1))
    return spans


def _code_of(text):
    """(import statements, strings) of a script's code, read by its tokens:
    comments and docstrings left out, because they name half the repository
    ("_paths.script("narrative.py")" in _paths.py's own docstring made every
    change to narrative.py reach every check that uses _paths)."""
    import io
    import tokenize
    imports, strings = [], []
    start, stmt = True, None
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            kind, s = tok.type, tok.string
            if kind in (tokenize.COMMENT, tokenize.NL, tokenize.ENCODING):
                continue
            if kind in (tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT) or s == ";":
                if stmt:
                    imports.append(" ".join(stmt))
                start, stmt = True, None
                continue
            if kind == tokenize.STRING:
                if not start:
                    strings.append(s)
            elif start and kind == tokenize.NAME and s in ("import", "from"):
                stmt = [s]
            elif stmt is not None:
                stmt.append(s)
            start = False
    except (tokenize.TokenError, SyntaxError, IndentationError):
        pass
    return imports, strings


_EDGES, _INDEXES = {}, {}


def _module_edges(files):
    """{module: (imports, launches)} for every code file: what its import
    statements, imp("x") and __import__("x") name, and the scripts it names
    as "x.py" -- in its code, not its comments or docstrings. Read once a
    process for the same files as they stand."""
    stamp = []
    for f in files:
        try:
            st = f.stat()
            stamp.append((str(f), st.st_size, st.st_mtime_ns))
        except OSError:
            pass
    stamp = tuple(stamp)
    if stamp not in _EDGES:
        _EDGES.clear()
        _EDGES[stamp] = _read_edges(files)
    return _EDGES[stamp]


def _read_edges(files):
    names = {f.stem for f in files}
    edges = {}
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stmts, strings = _code_of(text)
        imports = set()
        for st in stmts:
            words = st.replace(",", " ").split()
            if words[0] == "from" and len(words) > 1:
                imports.add(words[1].split(".")[0])
            elif words[0] == "import":
                skip = False
                for w in words[1:]:
                    if skip:
                        skip = False
                        continue
                    if w == "as":
                        skip = True
                        continue
                    imports.add(w.split(".")[0])
        code = "\n".join(strings)
        imports |= set(NAMED_RX.findall(text)) & {m for s in strings
                                                  for m in re.findall(r"[A-Za-z_]\w*", s)}
        launches = set(LAUNCH_RX.findall(code))
        edges[f.stem] = ((imports & names) - {f.stem}, (launches & names) - {f.stem})
    return edges


def reached(changed_modules, edges):
    """Every module a change to `changed_modules` reaches: the modules
    themselves, every module that imports one of them however far down, and
    one launch hop from any of those (a script that starts one)."""
    importers, launchers = {}, {}
    for m, (imps, lnch) in edges.items():
        for x in imps:
            importers.setdefault(x, set()).add(m)
        for x in lnch:
            launchers.setdefault(x, set()).add(m)
    seen, todo = set(changed_modules), list(changed_modules)
    while todo:
        m = todo.pop()
        for up in importers.get(m, ()):
            if up not in seen:
                seen.add(up)
                todo.append(up)
    return seen | {up for m in seen for up in launchers.get(m, ())}


class _Index:
    """preflight.py's top-level definitions, read once: for each name its
    span of lines (decorators included), the modules and files its code
    names (its strings, docstrings left out, and its imports), whether it
    walks the code (SCAN_CALLS), and the top-level names it uses."""

    def __init__(self, tree):
        self.tops = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names = [node.name]
            elif isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            else:
                continue
            for n in names:
                self.tops[n] = node
        self.info = {n: self._read(node) for n, node in self.tops.items()}

    def _read(self, node):
        prose = set()
        for d in ast.walk(node):
            if isinstance(d, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and d.body:
                first = d.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                        and isinstance(first.value.value, str):
                    prose.add(id(first.value))
        strings, imports, names, calls = [], set(), set(), set()
        for d in ast.walk(node):
            if isinstance(d, ast.Constant) and isinstance(d.value, str) and id(d) not in prose:
                strings.append(d.value)
            elif isinstance(d, ast.Import):
                imports |= {a.name.split(".")[0] for a in d.names}
            elif isinstance(d, ast.ImportFrom) and d.module:
                imports.add(d.module.split(".")[0])
            elif isinstance(d, ast.Name):
                names.add(d.id)
            elif isinstance(d, ast.Attribute) and isinstance(d.value, ast.Name):
                calls.add(f"{d.value.id}.{d.attr}")
        start = min([node.lineno] + [x.lineno for x in getattr(node, "decorator_list", [])])
        mods, files = _tokens(strings)
        return {"span": (start, node.end_lineno), "mods": mods | imports, "files": files,
                "scans": bool((calls | names) & SCAN_CALLS
                              or any(w in s for s in strings for w in SCAN_WORDS)),
                "names": names}

    def closure(self, name):
        """`name` and every top-level name it reaches by using it."""
        seen, todo = set(), [name]
        while todo:
            n = todo.pop()
            if n in seen or n not in self.info:
                continue
            seen.add(n)
            todo += [x for x in self.info[n]["names"] if x in self.info]
        return seen


def _tokens(strings):
    """(modules named as "x.py" or by a bare name, files named by name or
    path) in a list of strings."""
    mods, files = set(), set()
    for s in strings:
        if re.fullmatch(r"[A-Za-z_]\w*", s):
            mods.add(s)
        for m in FILE_RX.findall(s):
            p = m.lstrip("./") if m.startswith("./") else m
            files.add(p)
            files.add(p.rsplit("/", 1)[-1])
            if p.endswith(".py"):
                mods.add(p.rsplit("/", 1)[-1][:-3])
    return mods, files


def choose(checks, source, base=None, parse=None, root=".", changed=None, lines=None):
    """{"base", "changed", "run": {index: reason}, "core_missing": [...]}:
    which of `checks` (preflight's CHECKS, in order) a change since `base`
    can reach. `source` is preflight.py; `parse(path)` its parse (preflight
    hands its own, so that the run parses the file once). `changed` and
    `lines` stand in for git where a caller already knows them."""
    root = Path(root)
    parse = parse or (lambda p: ast.parse(Path(p).read_text(encoding="utf-8",
                                                             errors="replace")))
    commit = None
    if changed is None:
        commit = merge_base(base, root)
        changed = changed_files(commit, root)
    src_rel = os.path.relpath(Path(source).resolve(), root.resolve()).replace(os.sep, "/")
    if lines is None:
        lines = changed_lines(commit, src_rel, root) if src_rel in changed and commit else []
    code = [f for f in _paths.code_files("*.py", root=root) if f.name != Path(source).name]
    edges = _module_edges(code)
    project = set(edges) | {Path(source).stem}
    mods_changed = {Path(p).stem for p in changed if p.endswith(".py")} & project
    reach = reached(mods_changed - {Path(source).stem}, edges)
    names_changed = set(changed) | {p.rsplit("/", 1)[-1] for p in changed}
    any_code = any(p.endswith(CODE_KINDS) for p in changed)

    tree = parse(source)
    if id(tree) not in _INDEXES:
        _INDEXES.clear()
        _INDEXES[id(tree)] = (tree, _Index(tree))
    index = _INDEXES[id(tree)][1]
    moved_tops = {n for n, i in index.info.items()
                  if any(a <= i["span"][1] and i["span"][0] <= b for a, b in lines)}
    runner = sorted(moved_tops & RUNNER)

    run = {}
    for i, c in enumerate(checks):
        fn = c["fn"].__name__
        if runner:
            run[i] = f"preflight's runner changed ({', '.join(runner)})"
            continue
        if fn in CORE:
            run[i] = "core"
            continue
        near = index.closure(fn)
        mods, files, scans = set(c["needs"]), set(), False
        for n in near:
            mods |= index.info[n]["mods"]
            files |= index.info[n]["files"]
            scans = scans or index.info[n]["scans"]
        mods &= project
        why = []
        if near & moved_tops:
            why.append("its lines in preflight.py moved: " + ", ".join(sorted(near & moved_tops)[:3]))
        hit = sorted(mods & reach)
        if hit:
            why.append("reaches " + ", ".join(m + ".py" for m in hit[:3]))
        named = sorted(files & names_changed)
        if named:
            why.append("names " + ", ".join(named[:3]))
        if any_code and scans:
            why.append("reads every code file")
        if why:
            run[i] = "; ".join(why)
    present = {c["fn"].__name__ for c in checks}
    return {"base": commit, "changed": changed, "run": run,
            "core_missing": [n for n in CORE if n not in present]}
