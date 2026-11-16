#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.1
"""
The registry of preflight's checks, and what every module of the suite shares.

    from pf_core import CHECKS, check, imp, _run     # as preflight.py imports them

THE REGISTRY IS A MODULE'S (16 November 2026, the refactor's stage 1, step 4).
A check registers itself with `check` into CHECKS, and CHECKS is this module's:
defined in the script, it was __main__'s while a run went on, and a module
that imported preflight would have got a second registry, empty. preflight.py
still holds every check, and imports every name here, so that a check -- and
anything that reads preflight's module -- finds each one as it did.

Here: the registry and how a check's answer is read (check, CHECKS, _in_order,
_answer, _settle, imp, _run); the seal on a child that must reach no network
(_Seal); the suite's word for itself and the switches every module reads
(_suite_files, _in_suite, _suite_namespaces, _SWITCHED); the repository's
files read once and its scripts parsed once (_source, _parsed); what a run
came out as and what reaches what (_OUTCOMES, _THIS_RUN, _reaching,
_check_outcome); and the manifest of every check (_manifest). Each is as it
stood in preflight.py, with the comment above it. This module uses no other
module of the suite, and runs no check.
"""

import ast
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import _paths
import child

CHECKS = []


def _run(cmd, **kw):
    """subprocess.run, with the child's output read as UTF-8.

    The reason is child.py's, and _child_encoding holds the whole
    repository to it. This stays as a name because every check calls it.
    """
    return child.run(cmd, **kw)


# ---- a child that cannot reach the network ------------------------------------
#
# SEALED (26 September 2026). Several checks start a fetcher -- or the lane,
# which starts them -- as a real process, and each such check was safe only
# because the fetcher stopped before its first request: a fresh refusal on
# file, a clock inside GitHub's window, a cache that answers every page, a
# get() replaced in a wrapper. A regression in any of those would have sent a
# request from preflight to the General Court, or to YouTube, with nothing to
# say so. So such a child now starts sealed: a sitecustomize.py on its
# PYTHONPATH, in a folder of its own, replaces socket.socket.connect and
# connect_ex, socket.socket.sendto, socket.create_connection and
# socket.getaddrinfo with a raiser that writes a sentinel file before it
# raises; its proxies point at a closed port on the loopback address, with
# NO_PROXY cleared, for anything that reads them rather than Python's
# sockets. It passes to everything the child starts, so the lane's steps are
# sealed too. After each run the sentinel must be absent -- and the seal must
# have loaded in the child, which it records, or "no sentinel" would prove
# nothing.

_SEAL_SITE = r'''# Written by preflight.py: this process may reach nothing on the network.
import os as _os
import socket as _socket

_ASKED = _os.environ.get("GRANITE_SEAL_ASKED", "")
_LOADED = _os.environ.get("GRANITE_SEAL_LOADED", "")


class SealedByPreflight(OSError):
    """What a sealed process gets for any attempt to reach the network."""


def _refuse(name, method):
    def raiser(*args, **kwargs):
        shown = args[1:] if method else args
        try:
            with open(_ASKED, "a", encoding="utf-8") as fh:
                fh.write((f"{_os.getpid()} {name}{shown!r}")[:300] + "\n")
        except OSError:
            pass
        raise SealedByPreflight(f"preflight sealed this process from the network: {name}")
    return raiser


_socket.socket.connect = _refuse("socket.connect", True)
_socket.socket.connect_ex = _refuse("socket.connect_ex", True)
_socket.socket.sendto = _refuse("socket.sendto", True)
_socket.create_connection = _refuse("socket.create_connection", False)
_socket.getaddrinfo = _refuse("socket.getaddrinfo", False)
if _LOADED:
    try:
        with open(_LOADED, "a", encoding="utf-8") as fh:
            fh.write(f"{_os.getpid()}\n")
    except OSError:
        pass
'''

_PROXY_NAMES = ("http_proxy", "https_proxy", "all_proxy", "ftp_proxy", "no_proxy")


class _Seal:
    """A folder holding the sealing sitecustomize.py, and what the children
    started under it recorded: `loaded` for each process the seal was in,
    `asked` for each attempt one made to reach the network."""

    def __init__(self):
        import socket
        self.dir = Path(tempfile.mkdtemp(prefix="gr-seal-"))
        (self.dir / "sitecustomize.py").write_text(_SEAL_SITE, encoding="utf-8")
        self.asked, self.loaded = self.dir / "asked.txt", self.dir / "loaded.txt"
        # A port on the loopback address that nothing listens on: bound to
        # learn one, then closed. Nothing is asked of it -- the seal refuses
        # the connection before it is tried.
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        finally:
            s.close()

    def env(self, base=None):
        """`base` (this process's environment when None), sealed.

        Every proxy variable is SET, never only left out: child.run lays the
        env it is given over this process's own, so one merely missing here
        would come back from os.environ. On Windows the names are upper
        case only -- the environment there ignores case, and two spellings
        of one name in a block is asking for the wrong one to win."""
        base = os.environ if base is None else base
        e = {k: v for k, v in base.items() if k.lower() not in _PROXY_NAMES}
        prior = base.get("PYTHONPATH", os.environ.get("PYTHONPATH", ""))
        e["PYTHONPATH"] = os.pathsep.join([str(self.dir)] + ([prior] if prior else []))
        e["GRANITE_SEAL_ASKED"], e["GRANITE_SEAL_LOADED"] = str(self.asked), str(self.loaded)
        closed = f"http://127.0.0.1:{self.port}"
        for name in _PROXY_NAMES:
            for k in ((name.upper(),) if os.name == "nt" else (name.upper(), name)):
                e[k] = "" if name == "no_proxy" else closed
        e["GRANITE_NO_BUCKET"] = "1"
        return e

    def starts(self):
        try:
            return len(self.loaded.read_text(encoding="utf-8").split())
        except OSError:
            return 0

    def run(self, cmd, env=None, **kw):
        """_run(cmd) sealed; AssertionError when the child tried to reach the
        network, or the seal was not in it."""
        before = self.starts()
        r = _run(cmd, env=self.env(env), **kw)
        what = " ".join(str(c) for c in cmd[1:3])
        if self.asked.exists():
            tried = self.asked.read_text(encoding="utf-8", errors="replace").strip()
            self.asked.unlink(missing_ok=True)
            raise AssertionError(f"{what} TRIED TO REACH THE NETWORK from preflight, and the "
                                 f"seal stopped it: {tried[:300]}")
        assert self.starts() > before, (
            f"{what} ran without the seal preflight puts on a fetcher's process "
            "(sitecustomize.py on PYTHONPATH did not load), so nothing showed whether it "
            "asked the network")
        return r

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _sealed_run(cmd, env=None, **kw):
    """_run for a child that is a fetcher, the lane, or the pipeline that
    starts them: one seal for the one run (_Seal.run)."""
    with _Seal() as seal:
        return seal.run(cmd, env=env, **kw)


def check(group, name, needs=(), expect_fail=None, last=False):
    """Register a check. `needs` names modules that must import for it to run.

    `expect_fail` is for a check written AHEAD of the change that makes it
    pass, and says what that change is. Such a check runs every time; its
    failure is reported as expected (xfail), with its message in full, and
    counted on its own line of the summary rather than with the failures or
    the skips. The day it passes it FAILS, and says to take the mark off: a
    mark that outlived its change would excuse the next regression of what
    the check now holds. An exception other than an assertion is an ERROR
    either way, because a check that crashes has not found the failure it
    expects. See _settle().

    `last` runs it after every check without the mark, wherever in the suite
    it is defined (_in_order): for a check of what the run as a whole left
    behind, which a check added below it later would otherwise escape."""
    def deco(fn):
        CHECKS.append({"group": group, "name": name, "fn": fn, "needs": needs,
                       "expect_fail": expect_fail, "last": last})
        return fn
    return deco


def _in_order(checks):
    """`checks` in the order main() runs them: as defined, but those marked
    `last` after all the rest."""
    return [c for c in checks if not c.get("last")] + [c for c in checks if c.get("last")]


def _settle(status, msg, expect_fail):
    """(status, message) once a check's mark is read: what check() says of
    expect_fail. "xfail" is a failure that was expected; an expected one
    that passed is a FAIL."""
    if not expect_fail:
        return status, msg
    if status == "FAIL":
        return "xfail", f"expected to fail until {expect_fail}:\n{msg}"
    if status == "ok":
        return "FAIL", (f"this check was marked as expected to fail until {expect_fail}, and it "
                        f"passes now: take the expect_fail mark off, so that it holds what it "
                        f"found ({msg})")
    return status, msg


def _answer(got):
    """(status, words) of a check's answer, as main() and _check_outcome read every one.
    A check answers ("ok" | "skip" | "FAIL", words) or raises; "fail" is read as "FAIL".
    Anything else -- a bare None, a status nobody reads, a short tuple -- is a TypeError
    that says so. It used to be "cannot unpack non-iterable NoneType object" (the night of
    13 November 2026, a check that answered None when it passed, which the single runs had
    called a pass), or a KeyError that stopped the whole run where the mark is printed."""
    if isinstance(got, (tuple, list)) and len(got) == 2 and isinstance(got[0], str):
        status = "FAIL" if got[0] == "fail" else got[0]
        if status in ("ok", "skip", "FAIL", "ERROR"):
            return status, got[1]
    raise TypeError(f"the check answered {got!r:.120}: a check answers (status, words), the "
                    "status ok, skip or FAIL, or raises")


def imp(name):
    """Import a project module, or None. Import errors are a finding, not a crash."""
    try:
        return __import__(name)
    except Exception:
        return None


# ---- the suite: what the checks say of themselves (16 November 2026) --------
#
# THE CHECKS SPEAK OF THE SUITE, NOT OF ONE FILE (the refactor's stage 1,
# step 3). The checks are to move out of preflight.py into the modules of
# src/checks/suite/ (pf_<area>.py), some at a time, and a check that reads
# "this file" -- by its name, by __file__, by globals(), or by a switch it
# rebinds with `global` -- would then read one module of the suite and pass
# while reading less. So each reads the suite through these, which name every
# file of it: preflight.py, and the modules of src/checks/suite/ as there come
# to be any (step 4 puts the registry, the runner and the helpers the checks
# share there, and step 5 the checks, by area):
#   _suite_files()       the suite's files, preflight.py first;
#   _in_suite(path)      whether a file is one of them, by its name, so that a
#                        planted tree's preflight.py is one as the real one is;
#   _suite_namespaces()  each of their modules' name and namespace, the
#                        checks' first, for a walk of every definition where
#                        globals() is one module's;
#   _SWITCHED            the switches a check sets for the checks it runs
#                        inside it, on one object every module reads.
# check_select indexes the suite's files together (choose, _Index), and reads
# the lines a change moved in each against that file's own definitions.

def _suite_files():
    """The files of the suite: preflight.py, which every run starts from, and
    the modules of src/checks/suite/ (pf_*.py) -- its registry, its runner
    and the helpers its checks share, and in time the checks themselves --
    as _in_suite names them. preflight.py first, the rest by name, each
    resolved."""
    root = _paths.ROOT
    return [(root / "preflight.py").resolve()] + sorted(
        p.resolve() for p in (root / "src" / "checks" / "suite").glob("pf_*.py") if p.is_file())


def _in_suite(path):
    """Whether `path` is one of the suite's files, by its name: preflight.py,
    or a pf_<area>.py of src/checks/suite/."""
    p = Path(path)
    return p.name == "preflight.py" or (
        p.suffix == ".py" and p.name.startswith("pf_") and p.parent.name == "suite"
        and p.parent.parent.name == "checks")


def _suite_namespaces():
    """[(module name, its namespace)] of each module of the suite: each the
    registered checks are defined in, in the order the registry meets it,
    and then each module of src/checks/suite/ that is imported, by name
    (_suite_files); each once."""
    out, seen = [], set()
    for c in CHECKS:
        space = c["fn"].__globals__
        if id(space) not in seen:
            seen.add(id(space))
            out.append((c["fn"].__module__, space))
    for f in _suite_files()[1:]:
        m = sys.modules.get(f.stem)
        if m is not None and id(vars(m)) not in seen:
            seen.add(id(vars(m)))
            out.append((m.__name__, vars(m)))
    return out


class _Switches:
    """The switches a check sets for the checks it runs inside it, as they
    stand while none is set: published_scripts, True while
    _published_scripts_run_the_same runs every harness again on the scripts
    as the site publishes them; testify_log, a list while
    _testify_email_in_sync keeps every Testify button drawn; and
    workflow_dir, the folder the workflow checks read, which _workflows_gate
    points at a copy. Each was a global rebound with `global`, which another
    module never sees: split, a harness in one module would have read its
    own False, and the published pass run the source twice and passed."""

    def __init__(self):
        self.published_scripts = False
        self.testify_log = None
        self.workflow_dir = Path(".github/workflows")


_SWITCHED = _Switches()


# THE REPOSITORY'S OWN FILES ARE READ IN ONE PLACE (16 November 2026, the
# refactor's stage 1). Over three hundred checks read the text of one of the
# repository's source files -- app.css, app.js, a builder, a workflow, a
# README -- by naming it, so a step that moved code from one file to another
# would have had to edit every check that names the file the code left. They
# read it through _source, keyed by its path from the root, and a step that
# moves code says in _SOURCES which files that path's text is made of now: a
# table changes, and no check. A file is read once a run, and again when its
# size or its time of writing moves; a path outside the repository (a
# fixture's own copy) is read as asked, every time. A check that reads every
# code file in turn, or a fixture's files, reads them itself: no move changes
# what it names. _sources_read_in_one_place holds the rule.
_SOURCES = {}
_SOURCE_TEXT = {}


def _source(path, errors="strict", root=None):
    """The text of the file at `path` (a str or a Path, relative to the
    working folder as Path.read_text takes it), as
    Path(path).read_text(encoding="utf-8", errors=errors) gives it, and
    raising what that raises: from this run's earlier read of the same file
    of the repository (`root`, this one by default) while its size and time
    have not moved. A path _SOURCES names, from the root, is the files it
    lists, each read so and joined in order."""
    p = Path(path)
    base = Path(root).resolve() if root is not None else _paths.ROOT
    try:
        rel = p.resolve().relative_to(base).as_posix()
    except ValueError:
        return p.read_text(encoding="utf-8", errors=errors)
    parts = _SOURCES.get(rel, (rel,))
    texts = []
    for part in parts:
        f = base / part
        try:
            st = f.stat()
        except OSError:
            if parts == (rel,):
                return p.read_text(encoding="utf-8", errors=errors)    # its own error, as before
            raise
        key = (str(base), part, errors)
        seen = _SOURCE_TEXT.get(key)
        if seen is None or seen[0] != (st.st_size, st.st_mtime_ns):
            seen = ((st.st_size, st.st_mtime_ns), f.read_text(encoding="utf-8", errors=errors))
            _SOURCE_TEXT[key] = seen
        texts.append(seen[1])
    return texts[0] if len(texts) == 1 else "".join(texts)


# A SCRIPT IS PARSED ONCE A RUN (2 October 2026). Four checks each parsed
# every script -- _parse_all, _child_encoding, _every_fetcher_checks_refusal
# and, for preflight.py, _children_sealed -- and preflight.py was forty-four thousand
# lines: three parses of it were the largest single cost of the code checks
# that was not a child process. The tree is kept under the file's path, its
# size and the time it was last written, so a file a check changes and reads
# again is parsed again, and a file that will not parse raises for every
# caller as it did for one.
_PARSED = {}


def _parsed(path):
    """ast.parse of the script at `path`, from this run's earlier parse of
    the same bytes if there was one. Read as _parse_all always read it: as
    UTF-8, with a byte that is not UTF-8 replaced. SyntaxError is the caller's."""
    return _parsed_warned(path)[0]


def _parsed_warned(path):
    """(_parsed's tree, [(line, message)] of the SyntaxWarnings its parse
    gave). THE PARSE'S OWN WARNINGS ARE KEPT WITH IT (23 October 2026):
    _no_invalid_escapes compiled every code file again for its warnings --
    a second parse of preflight.py among them, seven to nine seconds of the
    code checks on GitHub's machine -- and an escape Python will refuse is
    a warning of the parse, which a later parse of the same bytes from this
    cache would never give again. So every parse records its own, and that
    check compiles the tree it is handed for the compiler's."""
    p = Path(path)
    st = p.stat()
    key = (str(p.resolve()), st.st_size, st.st_mtime_ns)
    if key not in _PARSED:
        import warnings
        tree, seen = _parse_in_pieces(p.read_text(encoding="utf-8", errors="replace"))
        for line, message, category, name in seen:
            if not issubclass(category, SyntaxWarning):
                warnings.warn_explicit(message, category, name, line)
        _PARSED[key] = (tree, [(line, str(message)) for line, message, category, _n in seen
                               if issubclass(category, SyntaxWarning)])
    return _PARSED[key]


# A BIG SCRIPT IS PARSED IN PIECES (11 November 2026). CPython's parser takes
# time that grows with the square of a file's size, not with its size: on this
# project's 3.14, 0.7 MB takes 0.5 s, 2.9 MB takes 9 s and 5.7 MB takes 34 s,
# and preflight.py is 8 MB, so one ast.parse of it was a hundred seconds and
# _parse_all's 83 of the code checks' 896. Cut into pieces of about 2,500 lines
# and parsed piece by piece it takes a few seconds. The pieces are cut only
# where a top-level statement can begin (a line in column 0 that opens with
# "@check(", "def " or "class ", after a blank line); the pieces' bodies are
# joined, with their line numbers moved to where each stood, into the Module
# ast.parse would give -- held by _pieces_are_the_whole, which _parse_all runs.
# A cut that lands where it cannot (in a string or a bracket) leaves a piece
# that does not parse, and is made again at the next place a statement may
# begin; a file that will not parse is parsed whole, and says what is wrong
# with it as before.
_PIECE_LINES = 2500
_PIECE_FROM = 200_000
_PIECE_OPENS = ("@check(", "def ", "class ")


def _piece_cuts(lines):
    """Line indexes where a top-level statement may begin, for a cut: a line
    in column 0 that opens with _PIECE_OPENS, after a blank one."""
    return [i for i in range(1, len(lines))
            if lines[i].startswith(_PIECE_OPENS) and not lines[i - 1].strip()]


def _parse_whole(text):
    """(ast.parse(text), the parse's warnings as (line, message, category,
    file name))."""
    import warnings
    with warnings.catch_warnings(record=True) as got:
        warnings.simplefilter("always")
        tree = ast.parse(text)
    return tree, [(w.lineno, w.message, w.category, w.filename) for w in got]


def _parse_in_pieces(text, every=_PIECE_LINES, floor=_PIECE_FROM):
    """(the Module ast.parse(text) gives, its warnings as _parse_whole gives
    them), by pieces where the text is long enough to be worth cutting. A
    piece that will not parse is cut again at the next place a statement may
    begin, which takes the cut out of a string or a bracket it had landed in;
    one that runs to the end of the file and will not parse is the file's own
    error, and is raised as the whole parse raises it."""
    if len(text) < floor:
        return _parse_whole(text)
    lines = text.split("\n")
    cuts = _piece_cuts(lines)
    body, seen, start, at = [], [], 0, 0
    while start < len(lines):
        while at < len(cuts) and cuts[at] < start + every:
            at += 1
        while True:
            stop = cuts[at] if at < len(cuts) else len(lines)
            try:
                part, said = _parse_whole("\n".join(lines[start:stop]) + "\n")
                break
            except SyntaxError:
                if stop == len(lines):
                    return _parse_whole(text)
                at += 1
        ast.increment_lineno(part, start)
        body += part.body
        seen += [(line + start, m, c, n) for line, m, c, n in said]
        start = stop
    return ast.Module(body=body, type_ignores=[]), seen


# ---- the manifest: every check, and what its code is (16 November 2026) ------
#
# THE INSTRUMENT FOR MOVING THE CHECKS (the refactor's stage 1, step 0). This
# file is to become a package in steps that each change no check, and a step
# shows it with this: `preflight.py --manifest FILE` writes every check in the
# order main() runs them, with its group, words, needs and marks, and two
# fingerprints read off the code without running any of it -- a sha256 of the
# check's own definition as ast.dump gives it, with no line numbers and no
# docstring, and a sha256 of that together with every helper and constant of
# the file it reaches by name, at any depth, each under its name. Code moved
# as it stands keeps both; an edit to a check changes its own; an edit to a
# helper, or a name that comes to mean another helper, changes the second. A
# step passes where the manifest before it and after it is the same but for
# the fingerprints the step says it changes. It is the format of the
# inventory's baseline (reports/refactor/stage0-checks-manifest.json, made by
# ast at 0c12343d). The fingerprints are ast's, so two manifests are compared
# only when one Python made both: the file says which.
_MANIFEST_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _manifest_tops(trees):
    """{name: the top-level statement that defines it} over the modules
    `trees`, in order: a def or a class by its name, an assignment by each
    plain name it binds. A later definition of a name replaces an earlier
    one, as it does when the module runs."""
    tops = {}
    for tree in trees:
        for node in tree.body:
            if isinstance(node, _MANIFEST_DEFS):
                tops[node.name] = node
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        tops[t.id] = node
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                tops[node.target.id] = node
    return tops


def _manifest_print(node):
    """The sha256 (hex) of `node` as ast.dump gives it without positions,
    and, for a def or a class, without its docstring. The node is not
    changed: the one without its docstring is a copy."""
    import hashlib
    body = getattr(node, "body", None)
    if isinstance(node, _MANIFEST_DEFS) and body and isinstance(body[0], ast.Expr) \
            and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        node = type(node)(**{f: getattr(node, f) for f in node._fields})
        node.body = body[1:] or [ast.Pass()]
    return hashlib.sha256(ast.dump(node, annotate_fields=True, include_attributes=False)
                          .encode("utf-8")).hexdigest()


class _ManifestPrints:
    """The fingerprints of the top-level definitions of some modules, each
    worked out once: what a definition names, what it reaches, and the two
    prints of a check (_manifest)."""

    def __init__(self, trees):
        self.tops = _manifest_tops(trees)
        self._names, self._prints = {}, {}

    def names(self, n):
        """The top-level names the definition of `n` uses, anywhere in it."""
        if n not in self._names:
            self._names[n] = {d.id for d in ast.walk(self.tops[n])
                              if isinstance(d, ast.Name)} & self.tops.keys()
        return self._names[n]

    def print(self, n):
        if n not in self._prints:
            self._prints[n] = _manifest_print(self.tops[n])
        return self._prints[n]

    def reached(self, fn):
        """Every top-level name `fn` reaches through the names it uses, at
        any depth, but itself; sorted."""
        seen, todo = set(), [fn]
        while todo:
            for m in self.names(todo.pop()):
                if m != fn and m not in seen:
                    seen.add(m)
                    todo.append(m)
        return sorted(seen)

    def of(self, fn):
        """(own, reach, how many helpers and constants it reaches) of `fn`,
        each print its first 16 hex digits: own is fn's definition, reach is
        that with every name it reaches, each by name."""
        import hashlib
        reached = self.reached(fn)
        whole = hashlib.sha256("\n".join([self.print(fn)] + [f"{n}:{self.print(n)}" for n in reached])
                               .encode("utf-8")).hexdigest()
        return self.print(fn)[:16], whole[:16], len(reached)


def _manifest(paths=None):
    """The manifest (above) of every registered check: {"source": the files
    read, "python": the Python whose ast made the prints, "checks": in the
    order main() runs them, {i, fn, group, words, needs, expect_fail, last,
    own, reach, helpers}}. `paths` are the files the checks are defined in,
    the suite's (_suite_files) by default. A check that is not a top-level def of them, or a
    function name two checks share, raises: neither can be fingerprinted."""
    import platform
    paths = [Path(p).resolve() for p in (paths or _suite_files())]
    twice = sorted(n for n, k in Counter(c["fn"].__name__ for c in CHECKS).items() if k > 1)
    if twice:
        raise ValueError("two checks share the name " + ", ".join(twice)
                         + ", so the manifest cannot tell them apart")
    prints = _ManifestPrints([_parsed(p) for p in paths])
    out = []
    for i, c in enumerate(_in_order(CHECKS)):
        fn = c["fn"].__name__
        if not isinstance(prints.tops.get(fn), (ast.FunctionDef, ast.AsyncFunctionDef)):
            raise ValueError(f"the check {fn} is not a top-level def of "
                             + ", ".join(p.name for p in paths) + ", so it cannot be fingerprinted")
        own, reach, helpers = prints.of(fn)
        out.append({"i": i, "fn": fn, "group": c["group"], "words": c["name"],
                    "needs": list(c["needs"]), "expect_fail": bool(c.get("expect_fail")),
                    "last": bool(c.get("last")), "own": own, "reach": reach, "helpers": helpers})
    source = ", ".join(p.relative_to(_paths.ROOT).as_posix() if p.is_relative_to(_paths.ROOT)
                       else p.as_posix() for p in paths)
    return {"source": source, "python": platform.python_version(), "checks": out}


def _manifest_text(paths=None):
    """The manifest as --manifest writes it: JSON, one key to a line, the
    same bytes from any run of the same files on the same Python."""
    return json.dumps(_manifest(paths), indent=0) + "\n"


# What each check came out as in this run, by function name, before any
# expect_fail mark is read: main() writes it, _published_scripts_run_the_same
# reads it.
_OUTCOMES = {}


# What main() says of the run it is making, for a check that reads it
# (16 November 2026): `chosen`, the function names of the checks a --changed
# run chose, and None in a run of every check of a kind (the suite, --code,
# --data, --built). _published_scripts_run_the_same runs again only the
# harnesses among them. One object, set and read by its attribute, so that the
# module that runs the checks and the module that holds a check read the same
# one when they are two.
class _ThisRun:
    """The run main() is making (above)."""

    def __init__(self):
        self.chosen = None


_THIS_RUN = _ThisRun()


def _reaching(names, skip=(), checks=None):
    """The checks (CHECKS entries, or those of `checks`) whose code reaches
    one of `names` -- directly, or through any function of the suite's it
    calls, at any depth, each name read where the function that calls it
    reads it -- but those named in `skip`."""
    import types
    suite = {name for name, _space in _suite_namespaces()}

    def codes(co):
        yield co
        for k in co.co_consts:
            if isinstance(k, types.CodeType):
                yield from codes(k)

    def reaches(fn, seen):
        if fn.__name__ in seen:
            return False
        seen.add(fn.__name__)
        for co in codes(fn.__code__):
            for nm in co.co_names:
                if nm in names:
                    return True
                f = fn.__globals__.get(nm)
                if isinstance(f, types.FunctionType) and f.__module__ in suite \
                        and reaches(f, seen):
                    return True
        return False
    return [c for c in (CHECKS if checks is None else checks)
            if c["fn"].__name__ not in skip and reaches(c["fn"], set())]


def _check_outcome(c):
    """(status, message) of one check, as main() reads it before the
    expect_fail mark: "skip" where a module it needs will not import, "FAIL"
    on an assertion, "ERROR" on any other exception."""
    mods = []
    for n in c["needs"]:
        m = imp(n)
        if m is None:
            return "skip", f"{n}.py will not import"
        mods.append(m)
    try:
        return _answer(c["fn"](*mods))
    except AssertionError as e:
        return "FAIL", str(e) or "assertion failed"
    except Exception as e:                                      # noqa: BLE001
        return "ERROR", f"{type(e).__name__}: {e}"
