#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.22
"""
preflight's checks of the repository's guards: stamps, addresses, secrets, the scripts as scripts, the suite itself.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import _paths

from pf_core import (CHECKS, _ManifestPrints, _SOURCES, _SWITCHED, _THIS_RUN, _answer,
                     _check_outcome, _in_order, _in_suite, _manifest_text, _map_kept,
                     _map_read, _parse_in_pieces,
                     _parse_whole, _parsed, _parsed_warned, _piece_cuts, _reaching, _run,
                     _sealed_run, _settle, _source, _suite_files, _suite_namespaces, check, imp)
from pf_fixture import (_EARLY, _EARLY_TAKEN_BY, _early_wanted, _once_a_run,
                        _start_early_builds)
from pf_runner import (_MAP_ON, _MapRecorder, _changed_choice, _early_for_run, main)
from pf_shared import (_RUNNERS, _json_rows, _plant, _published_harnesses, _runner_names)


def _tracked():
    """What git tracks, listed and read once a run for the two checks that
    search every tracked file -- _one_address and _no_secrets, each of which
    asked git for the list and read all of it. (names, {name: its text}): a
    file over 4 MB, or not here, or that will not read, is among the names
    and has no text, as neither check read one. (None, why) where git will
    not say what it tracks."""
    def make():
        try:
            out = _run(["git", "ls-files"], capture_output=True,
                       text=True, timeout=60)
        except (OSError, subprocess.SubprocessError) as e:
            return None, f"git would not list the tracked files ({e})"
        if out.returncode != 0:
            return None, "not a git repository"
        names = [n for n in out.stdout.splitlines() if n.strip()]
        text = {}
        for n in names:
            f = Path(n)
            if not f.exists() or f.stat().st_size > 4_000_000:
                continue
            try:
                text[n] = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        return names, text
    return _once_a_run("the tracked files", make)


@check("files", "one contact address, and it is the working one")
def _one_address():
    """Thirty occurrences across twenty-seven files, and they must agree.

    The address is published to readers on every page and, more importantly,
    sent to the General Court in the User-Agent of every fetch script. Those
    are the people who have blocked this address twice; if they ever want to
    say why, the address in their logs is how they would do it, and for a
    while it was one that does not receive mail.

    Thirty copies is the real defect, but they sit inside User-Agent strings in
    twenty scripts and inside HTML in three more, and a constant threaded
    through all of them would save only a find-and-replace. What is not
    acceptable is the copies silently disagreeing: one address at
    graniterecord.org, everywhere, and it is the one that works.
    """
    import re
    CORRECT = "contact@graniterecord.org"
    names, text = _tracked()
    if names is None:
        return "skip", text
    rx = re.compile(r"[A-Za-z0-9._%+-]+@graniterecord\.org")
    found, wrong = 0, {}
    for n, body in text.items():
        for m in rx.finditer(body):
            found += 1
            if m.group(0) != CORRECT:
                line = body[:m.start()].count(chr(10)) + 1
                wrong.setdefault(m.group(0), []).append(f"{n}:{line}")
    assert not wrong, (
        "an address at graniterecord.org that is not " + CORRECT + ": "
        + "; ".join(f"{a} at {', '.join(v[:3])}" for a, v in wrong.items()))
    return "ok", (f"{found} occurrences of {CORRECT} across the tracked "
                  "files, and no other address at that domain")


@check("files", "every commit in the history was made by the project address")
def _history_addresses():
    """WHAT GIT PUBLISHES IS NOT ONLY THE FILES.

    An author or committer field can carry an address that no reading of the
    working tree would ever see, and the two checks either side of this one
    read `git ls-files`, which is the tree at HEAD: the address check matches
    only addresses AT graniterecord.org, and the credential check matches key
    shapes and has no pattern for an email at all.

    A .mailmap does NOT fix a wrong address and must not be mistaken for a fix:
    mailmap changes how `git log` DISPLAYS one, and the raw commit object still
    carries it for anyone who reads the objects. The fix is a history rewrite,
    which costs nothing while no remote exists and costs a force-push and every
    clone anyone has taken once one does.

    So: every author and every committer in the history being built is the
    project's own address.

    THE HISTORY BEING BUILT, NOT EVERY REF (30 October 2026). This read
    `git log --all`, and GitHub's night checks out with fetch-depth 0, so it
    held every branch on GitHub: one merge pushed to an unmerged side branch
    under another address stopped dry run 157 at preflight, and would have
    stopped the live night from main with it. A branch nobody is building
    must not decide whether the site is built. What the night builds, and
    what reaches main, is HEAD's history, and that is what is read.
    """
    import subprocess
    CORRECT = "contact@graniterecord.org"
    try:
        out = _run(["git", "log", "HEAD", "--format=%ae%n%ce"],
                   capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return "skip", f"git would not read the history ({e})"
    if out.returncode != 0:
        return "skip", "not a git repository"
    seen = [a.strip() for a in out.stdout.splitlines() if a.strip()]
    if not seen:
        return "skip", "no commits"
    from collections import Counter
    other = Counter(a for a in seen if a != CORRECT)
    assert not other, (
        "the history carries an address that is not " + CORRECT + ": "
        + ", ".join(f"{a} ({n})" for a, n in other.most_common(4))
        + ".\n  Publishing the repository publishes it. A .mailmap will not do "
          "it -- the raw commit object keeps the address.\n  Rewrite with "
          "`git filter-branch --env-filter` over --all, then delete "
          "refs/original, expire the reflog and gc --prune=now.")
    return "ok", (f"{len(seen):,} author and committer fields in the history being "
                  f"built (HEAD), every one {CORRECT}")


@check("files", "no tracked file carries a credential")
def _no_secrets():
    """What git would publish, checked before git publishes it.

    This repository is meant to be shared. A key committed once is in the
    history forever, and rewriting published history is not a thing anybody
    does calmly at the moment they notice. secrets.json is gitignored and
    keys.py reads it; this is what makes that arrangement true rather than
    merely intended.

    The General Court's database host, user and password are deliberately NOT
    matched here. They are published at gc.nh.gov/downloads in "ODBC and Data
    Table Structure.pdf" for public use against a read-only account, they are
    documented as such in probe_db.py, and hiding a published credential would
    protect nothing while stopping somebody reproducing this work.
    """
    names, text = _tracked()
    if names is None:
        return "skip", text
    if not names:
        return "skip", "git tracks nothing here"

    # Shapes that are a credential and nothing else. Deliberately narrow: a
    # pattern loose enough to catch "password = " would fire on prose and on
    # probe_db.py, and a check that cries wolf gets silenced.
    import re
    SHAPES = [
        ("a Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
        ("an OpenAI key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
        ("a GitHub token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
        ("a Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
        ("an AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
        ("a private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
        ("a Cloudflare token", re.compile(r"CLOUDFLARE_API_TOKEN\s*[:=]\s*"
                                          r"[\"\']?[A-Za-z0-9_\-]{20,}")),
    ]
    found = []
    for n, body in text.items():
        for what, rx in SHAPES:
            m = rx.search(body)
            if m:
                line = body[:m.start()].count(chr(10)) + 1
                found.append(f"{n}:{line} looks like {what}")
    # A check signals failure by raising, which the runner turns into FAIL.
    # Returning "fail" is not a status it knows and crashed it on a KeyError
    # the first time one of these actually tripped.
    assert not found, (f"{len(found)} tracked file(s) carry something shaped "
                       "like a credential, and this repository is meant to be "
                       "shared: " + "; ".join(found[:4]))
    return "ok", (f"{len(names)} tracked files, none carrying a key. "
                  "secrets.json is gitignored; probe_db.py's published "
                  "credentials are public by design.")


@check("files", "the project's plans and private instructions stay out of git")
def _private_untracked():
    """On 30 September 2026 the person decided the public repository holds the
    code and the documents that explain how the code and the data work, and
    nothing of the project's planning: launch and development plans, design
    briefs and reviews, the triage rules and ledger, the launch register, and
    the instructions for this project's own Claude sessions that are about
    its plans (CLAUDE.local.md, beside the public CLAUDE.md). They moved to
    private/ or stayed where scripts read them, untracked.

    .gitignore stops a `git add .` and not a `git add -f`, so this asks git
    what it tracks. Their earlier copies stay in the history, as decided."""
    import subprocess
    PRIVATE = ["CLAUDE.local.md", "private", "launch_register.json",
               "reports/TRIAGE.md", "reports/handled.jsonl",
               "LAUNCH.md", "HANDOFF.md", "DESIGN.md", "ROADMAP.md",
               "ARCHIVE_PLAN.md", "ARCHIVE_SESSION_PROMPT.md",
               "PROPOSAL-civics.md", "FOLLOW.md", "design"]
    ignore = _source(".gitignore")
    for line in ("/CLAUDE.local.md", "/private/", "/launch_register.json", "reports/*"):
        assert line in ignore.splitlines(), f".gitignore no longer has {line}"
    assert "!reports/TRIAGE.md" not in ignore and "!reports/handled.jsonl" not in ignore, \
        ".gitignore tracks the triage rules or ledger again"
    try:
        tracked = _run(["git", "ls-files", "--", *PRIVATE], capture_output=True,
                       text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as e:
        return "skip", f"git would not say what it tracks ({e})"
    if tracked.returncode != 0:
        return "skip", "not a git repository"
    held = tracked.stdout.split()
    assert not held, (
        f"git tracks {', '.join(held[:6])}, and the next push would publish the project's "
        f"plans: `git rm --cached` keeps each file and stops tracking it")
    return "ok", "CLAUDE.local.md, private/, the triage rules and ledger and the launch register are untracked"


@check("files", "the Clerks' corrections list stays out of git and out of its history")
def _clerk_list_untracked():
    """The list of errors in the General Court's own record is the person's to
    take to the Clerks' offices, and on 24 September they chose to keep it out
    of GitHub so that the Clerks hear of each error from them first.

    The first version of it was committed all the same, ten minutes before
    that answer, and a merge would have carried it into the history, where
    deleting the file later does not take it back out. .gitignore stops a
    `git add .` and not a `git add -f`, so this asks git what it tracks and
    whether any commit on any ref has ever held the file."""
    import subprocess
    NAME = "CLERK_CORRECTIONS.md"
    assert "/" + NAME in _source(".gitignore"), \
        f".gitignore no longer keeps {NAME} out of the repository"
    try:
        tracked = _run(["git", "ls-files", "--", NAME], capture_output=True,
                       text=True, timeout=30)
        history = _run(["git", "log", "--all", "--format=%h", "--", NAME],
                       capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return "skip", f"git would not say what it tracks ({e})"
    if tracked.returncode != 0 or history.returncode != 0:
        return "skip", "not a git repository"
    assert not tracked.stdout.strip(), (
        f"git tracks {NAME}, and the next push would publish the Clerks' list: "
        f"`git rm --cached {NAME}` keeps the file and stops tracking it")
    commits = history.stdout.split()
    assert not commits, (
        f"{len(commits)} commit(s) reachable from a ref hold {NAME} "
        f"({', '.join(commits[:4])}); pushing any of them publishes the list, "
        "so rewrite that branch before it is merged or pushed")
    return "ok", f"{NAME} is gitignored, untracked, and in no commit on any ref"


_PIECES_SAMPLE = '''import os


@check('a')
def one():
    return 1


BIG = """text

def inside_a_string():
    pass

@check('b')
"""


@check('c')
def two(x):
    return x + 1


class K:
    def m(self):
        return '\\d+'


@check('d')
@other
def three():
    pass
'''


def _pieces_are_the_whole():
    """_parse_in_pieces gives what one ast.parse gives (above it says why it
    is there): the same tree, every attribute and line number, and the same
    warnings at the same lines, on a source cut every few lines and on a real
    script cut every few hundred; a cut that would land in a string is made
    again further on; and a syntax error is raised as ever."""
    src = _PIECES_SAMPLE
    texts = [src, src * 7, "x = 1\n\n\ndef f():\n    return 2\n"]
    real = _paths.locate("build_pages.py")
    if real.exists():
        texts.append(_source(real, errors="replace"))
    for text in texts:
        for every in (1, 4, 300):
            whole, said = _parse_whole(text)
            tree, got = _parse_in_pieces(text, every=every, floor=0)
            assert ast.dump(tree, include_attributes=True) == ast.dump(whole, include_attributes=True), (
                f"a script parsed in pieces (every {every} lines) is not the tree one parse gives")
            assert [(l, str(m), c) for l, m, c, _n in got] == [(l, str(m), c) for l, m, c, _n in said], (
                f"a script parsed in pieces (every {every} lines) warns otherwise than one parse does")
    assert any("\\d" in str(m) for _l, m, _c, _n in _parse_whole(src)[1]), (
        "the sample's invalid escape gave no warning, so the warnings above held nothing")
    assert len(_piece_cuts((src * 7).split("\n"))) > 3, "the sample is not cut into pieces"
    try:
        _parse_in_pieces(src + "def broken(:\n", every=4, floor=0)
    except SyntaxError:
        pass
    else:
        raise AssertionError("a syntax error in a script parsed in pieces was not raised")
    return len(texts)




@check("files", "every stamped script parses", needs=("inventory",))
def _parse_all(inventory):
    _pieces_are_the_whole()
    names = [n for n in inventory.registry() if n.endswith(".py")]
    bad = []
    for n in names:
        p = _paths.locate(n)
        if not p.exists():
            continue
        try:
            _parsed(p)
        except SyntaxError as e:
            bad.append(f"{n}:{e.lineno} {e.msg}")
    present = sum(1 for n in names if _paths.locate(n).exists())
    assert not bad, "; ".join(bad)
    return "ok", f"{present} of {len(names)} present, all parse"


# What is the record and not the source: the five folders of the data git
# keeps (README.md, "What's where"), and what a build writes.
_DATA_FOLDERS = ("corrections/", "review/", "records/", "collected/", "generated/", "data/", "site/")


def _source_reads(tree, tracked, text=None):
    """[(definition, line, the read)] of every place in `tree` (a module's
    parse; `text` its source, to pass over the definitions that read
    nothing) that reads a source file of the repository by naming it, other
    than through _source: X.read_text(encoding="utf-8"), with errors= or
    without, where X is Path("<file>"), _paths.locate, script or
    find("<file>"), _paths.ROOT / "<file>", Path(<module>.__file__), or a
    name its definition binds once to one of those -- alone or in a tuple
    assigned at once, or as the one name a loop takes through a literal
    tuple or list of them, and never also as an argument, in a with, by an
    augmented assignment or a loop over anything else -- or Path(n),
    _paths.locate(n) where n is a name so bound to literal files only.
    `tracked` is git's list of files; a file under _DATA_FOLDERS, or
    untracked, is not source, and nor is the module's own file,
    Path(__file__)."""
    tracked = set(tracked)
    bare = {}
    for t in tracked:
        bare.setdefault(t.rsplit("/", 1)[-1], []).append(t)
    lines = text.split("\n") if text is not None else None

    def source(s):
        full = s if s in tracked else (bare[s][0] if "/" not in s and len(bare.get(s, ())) == 1 else None)
        return full is not None and not full.startswith(_DATA_FOLDERS)

    def lit(n):
        return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None

    def named(e):
        if isinstance(e, ast.Call) and isinstance(e.func, ast.Name) and e.func.id == "Path" \
                and len(e.args) == 1 and not e.keywords:
            a = e.args[0]
            if lit(a) is not None:
                return source(lit(a))
            return isinstance(a, ast.Attribute) and a.attr == "__file__" and isinstance(a.value, ast.Name)
        if isinstance(e, ast.Call) and ast.unparse(e.func) in ("_paths.locate", "_paths.script",
                                                                "_paths.find") \
                and len(e.args) == 1 and not e.keywords:
            return lit(e.args[0]) is not None and source(lit(e.args[0]))
        if isinstance(e, ast.BinOp) and isinstance(e.op, ast.Div):
            parts, x = [], e
            while isinstance(x, ast.BinOp) and isinstance(x.op, ast.Div):
                parts.insert(0, lit(x.right))
                x = x.left
            return ast.unparse(x) in ("_paths.ROOT", "ROOT") and None not in parts \
                and source("/".join(parts))
        return False

    found = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign)):
            continue
        name = node.name if hasattr(node, "name") else ast.unparse(node.targets[0])
        if name == "_source" or (lines is not None and not any(
                "read_text" in ln for ln in lines[node.lineno - 1:node.end_lineno])):
            continue
        reads = [c for c in ast.walk(node) if isinstance(c, ast.Call)
                 and isinstance(c.func, ast.Attribute) and c.func.attr == "read_text"]
        if not reads:
            continue
        once, loops, unclean = {}, {}, set()
        for a in ast.walk(node):
            if isinstance(a, ast.Assign):
                for t in a.targets:
                    if isinstance(t, ast.Name):
                        once.setdefault(t.id, []).append(a.value)
                    elif isinstance(t, (ast.Tuple, ast.List)) and isinstance(a.value, (ast.Tuple, ast.List)) \
                            and len(t.elts) == len(a.value.elts) \
                            and not any(isinstance(x, ast.Starred) for x in t.elts + a.value.elts):
                        for te, ve in zip(t.elts, a.value.elts):
                            if isinstance(te, ast.Name):
                                once.setdefault(te.id, []).append(ve)
                            else:
                                unclean |= {x.id for x in ast.walk(te) if isinstance(x, ast.Name)}
                    else:
                        unclean |= {x.id for x in ast.walk(t) if isinstance(x, ast.Name)}
            elif isinstance(a, ast.AnnAssign) and isinstance(a.target, ast.Name):
                once.setdefault(a.target.id, []).append(a.value)
            elif isinstance(a, (ast.For, ast.AsyncFor, ast.comprehension)):
                if isinstance(a.target, ast.Name) and isinstance(a.iter, (ast.Tuple, ast.List)) \
                        and a.iter.elts and not any(isinstance(x, ast.Starred) for x in a.iter.elts):
                    loops.setdefault(a.target.id, []).append(a.iter.elts)
                else:
                    unclean |= {x.id for x in ast.walk(a.target) if isinstance(x, ast.Name)}
            elif isinstance(a, ast.AugAssign):
                unclean |= {x.id for x in ast.walk(a.target) if isinstance(x, ast.Name)}
            elif isinstance(a, ast.withitem) and a.optional_vars is not None:
                unclean |= {x.id for x in ast.walk(a.optional_vars) if isinstance(x, ast.Name)}
            elif isinstance(a, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                g = a.args
                unclean |= {x.arg for x in g.posonlyargs + g.args + g.kwonlyargs}
                unclean |= {x.arg for x in (g.vararg, g.kwarg) if x}
            elif isinstance(a, ast.NamedExpr):
                once.setdefault(a.target.id, []).append(a.value)
            elif isinstance(a, (ast.Global, ast.Nonlocal)):
                unclean |= set(a.names)
            elif isinstance(a, ast.ExceptHandler) and a.name:
                unclean.add(a.name)
        for c in reads:
            kw = {k.arg: k.value for k in c.keywords}
            enc = c.args[0] if c.args else kw.get("encoding")
            if len(c.args) > 1 or set(kw) - {"encoding", "errors"} or (c.args and "encoding" in kw) \
                    or lit(enc) not in ("utf-8", "utf8"):
                continue
            r = c.func.value

            def values(n):
                # What the name n stands for where it is bound once: [its value], or the
                # elements of the one literal tuple or list a loop takes it through.
                if n in unclean or len(once.get(n, ())) + len(loops.get(n, ())) != 1:
                    return None
                return [once[n][0]] if once.get(n) else list(loops[n][0])
            if named(r) or (isinstance(r, ast.Name) and values(r.id)
                            and all(named(v) for v in values(r.id))) \
                    or (isinstance(r, ast.Call) and len(r.args) == 1 and not r.keywords
                        and isinstance(r.args[0], ast.Name)
                        and ast.unparse(r.func) in ("Path", "_paths.locate", "_paths.script",
                                                    "_paths.find")
                        and values(r.args[0].id)
                        and all(lit(v) is not None and source(lit(v)) for v in values(r.args[0].id))):
                found.append((name, c.lineno, ast.unparse(c)))
    return found


@check("files", "a check reads a source file of the repository through _source, so that code moved "
                "between files changes a table and not the checks")
def _sources_read_in_one_place():
    """ONE READER FOR THE REPOSITORY'S OWN FILES (the refactor's stage 1; see
    _source). Every read of a source file a check names goes through
    _source, so that a later step which moves code between files edits
    _SOURCES, and not the checks that read the file the code left. Held:

      _source gives what Path.read_text gives -- a file of the repository
      once a run and again when it moves, a file outside it as asked every
      time, errors= as read_text takes it, a missing file's own error --
      and a path _SOURCES names is its files, joined;
      the reader of reads (_source_reads) finds, on a sample, a read by
      Path, _paths.locate, _paths.ROOT, a module's __file__, a name bound
      once to one of them, alone or in a tuple, and a name a loop takes
      through literal files, with errors= and without, and passes over a
      data file, a fixture's path, a loop over anything else, a read in
      another encoding and _source itself;
      and in this file no check reads a source file by naming it but
      through _source. One that does is moved onto it as
      `_source(<what it named>)`, the same text.
    """
    real = _paths.locate("_paths.py")
    with open(real, encoding="utf-8") as fh:
        want = fh.read()
    got = _source(real)
    assert got == want, "_source does not give what read_text gives"
    assert _source(real) is got, "_source read the file again with nothing moved"
    tmp = Path(tempfile.mkdtemp(prefix="gr-source-"))
    try:
        out = tmp / "outside.txt"
        out.write_text("one", encoding="utf-8")
        assert _source(out) == "one"
        out.write_text("two, longer", encoding="utf-8")
        assert _source(out) == "two, longer", "a file outside the repository was not read as asked"
        root = _plant(tmp / "root", {"a.js": "A\n", "b.js": "B\n"})
        (root / "bad.txt").write_bytes(b"x\xffy")
        first = _source(root / "a.js", root=root)
        assert first == "A\n" and _source(root / "a.js", root=root) is first, (
            "a file of the repository was not read once")
        (root / "a.js").write_text("A, longer\n", encoding="utf-8")
        assert _source(root / "a.js", root=root) == "A, longer\n", "a file that moved was not read again"
        _SOURCES["gr-whole.js"] = ("a.js", "b.js")
        try:
            assert _source(root / "gr-whole.js", root=root) == "A, longer\nB\n", (
                "a path _SOURCES names is not its files joined")
        finally:
            _SOURCES.pop("gr-whole.js", None)
        assert _source(root / "bad.txt", errors="replace", root=root) == "x�y"
        try:
            _source(root / "bad.txt", root=root)
        except UnicodeDecodeError:
            pass
        else:
            raise AssertionError("_source read a byte that is not UTF-8 without read_text's error")
        try:
            _source(root / "gone.js", root=root)
        except FileNotFoundError as e:
            try:
                (root / "gone.js").read_text(encoding="utf-8")
            except FileNotFoundError as own:
                assert str(e) == str(own), f"a missing file's error is not read_text's: {e}"
        else:
            raise AssertionError("_source read a missing file")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    sample = ("\ndef reads(B, here, files):\n"
              "    a = Path(\"src/pages/app.js\").read_text(encoding=\"utf-8\")\n"
              "    b = _paths.locate(\"build_pages.py\").read_text(encoding=\"utf-8\", errors=\"replace\")\n"
              "    c = (_paths.ROOT / \"CONTRIBUTING.md\").read_text(encoding=\"utf-8\")\n"
              "    d = Path(B.__file__).read_text(encoding=\"utf-8\")\n"
              "    css = Path(\"src/pages/app.css\")\n"
              "    e = css.read_text(encoding=\"utf-8\")\n"
              "    f = Path(\"generated/careers.json\").read_text(encoding=\"utf-8\")\n"
              "    g = (Path(here) / \"src/pages/app.js\").read_text(encoding=\"utf-8\")\n"
              "    for p in files:\n"
              "        h = p.read_text(encoding=\"utf-8\")\n"
              "    i = Path(\"src/pages/app.js\").read_text(encoding=\"utf-8-sig\")\n"
              "    j = Path(__file__).read_text(encoding=\"utf-8\")\n"
              "    k = _source(\"src/pages/app.js\")\n"
              "    js, stub = Path(\"src/pages/app.js\"), Path(\"tests/dom_stub.js\")\n"
              "    l = js.read_text(encoding=\"utf-8\")\n"
              "    for n in (\"src/pages/app.js\", \"src/pages/app.css\"):\n"
              "        m = Path(n).read_text(encoding=\"utf-8\")\n"
              "    for n2 in (\"src/pages/app.js\", \"generated/careers.json\"):\n"
              "        o = Path(n2).read_text(encoding=\"utf-8\")\n\n\n"
              "def _source(path):\n"
              "    return Path(\"src/pages/app.js\").read_text(encoding=\"utf-8\")\n")
    named = ["src/pages/app.js", "src/pages/build_pages.py", "CONTRIBUTING.md", "src/pages/app.css",
             "generated/careers.json", "tests/dom_stub.js"]
    got = [line for _d, line, _t in _source_reads(ast.parse(sample), named, sample)]
    assert got == [3, 4, 5, 6, 8, 17, 19], (
        f"the reader of reads found lines {got} of the sample, not the seven reads of a source file "
        "it names (3, 4, 5, 6, 8, 17 and 19)")
    names, why = _tracked()
    if names is None:
        return "skip", why
    found = [r for f in _suite_files() for r in _source_reads(_parsed(f), names, _source(f))]
    assert not found, (
        f"{len(found)} reads of a source file by its name, not through _source: "
        + "; ".join(f"{d} line {n}: {t[:80]}" for d, n, t in found[:6])
        + ". Read it as _source(<what it named>): a later move of code changes _SOURCES, not the check")
    return "ok", ("no check here reads a source file by naming it but through _source, which reads "
                  "each once a run, again when it moves, and a fixture's as asked")


def _self_references(tree, allowed=()):
    """[(definition, line, what)] of each place in `tree` (a module of the
    suite) where a definition speaks of one file rather than of the suite: a
    call of globals(), a `global` statement, the name __file__, a comparison
    with __name__, or a file a loop takes, compared by its name with
    "preflight.py". The suite's own words (_suite_files, _in_suite,
    _suite_namespaces) and the definitions named in `allowed` are passed
    over. In the order of the lines."""
    own = {"_suite_files", "_in_suite", "_suite_namespaces"} | set(allowed)
    found = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                or node.name in own:
            continue
        looped = {x.id for a in ast.walk(node) if isinstance(a, (ast.For, ast.AsyncFor, ast.comprehension))
                  for x in ast.walk(a.target) if isinstance(x, ast.Name)}
        for a in ast.walk(node):
            what = None
            if isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id == "globals":
                what = "globals()"
            elif isinstance(a, ast.Global):
                what = "global " + ", ".join(a.names)
            elif isinstance(a, ast.Name) and a.id == "__file__":
                what = "__file__"
            elif isinstance(a, ast.Compare):
                sides = [a.left] + a.comparators
                if any(isinstance(s, ast.Name) and s.id == "__name__" for s in sides):
                    what = "a comparison with __name__"
                elif isinstance(a.left, ast.Attribute) and a.left.attr == "name" \
                        and isinstance(a.left.value, ast.Name) and a.left.value.id in looped \
                        and any(isinstance(c, ast.Constant) and c.value == "preflight.py"
                                for s in a.comparators for c in ast.walk(s)):
                    what = f'{ast.unparse(a.left)} compared with "preflight.py"'
            if what:
                found.append((node.name, a.lineno, what))
    return sorted(found, key=lambda x: x[1])


@check("files", "the checks speak of the suite, not of this file: no globals(), no `global` switch, "
                "no __file__ and no preflight.py named in a scan, but through the suite's own words")
def _suite_speaks_of_itself():
    """THE CHECKS' WORD FOR THEMSELVES IS THE SUITE'S (the refactor's stage 1,
    step 3; see _suite_files). Once the checks are modules of a package, a
    check that read this file by its name or its __file__, walked
    globals(), or rebound a switch with `global` would read one module and
    pass while reading less, as nine scanners' exemptions of preflight.py by
    name, the self-reads, the two walks and the three switches did until 16
    November 2026. Held:

      _in_suite is preflight.py and src/checks/suite/pf_<area>.py, by name,
      and nothing else; _suite_files() is preflight.py and the modules of
      src/checks/suite/, and _suite_namespaces() the module of every
      registered check and of each of those files, once; _SWITCHED's
      switches stand unset between checks;
      the reader of self-references (_self_references) finds each of its
      five forms on a sample, in line order, and passes over a string, an
      attribute named __file__, a name compared that no loop takes, and
      the suite's own words;
      and in the suite's files no definition speaks of one file.
    """
    for path, want in (("preflight.py", True), ("src/checks/suite/pf_votes.py", True),
                       ("src/checks/check_select.py", False), ("src/checks/suite/votes.py", False),
                       ("src/checks/pf_votes.py", False), ("tests/pf_x.py", False)):
        assert _in_suite(_paths.ROOT / path) is want, f"_in_suite says {not want} of {path}"
    files = _suite_files()
    assert files[0] == (_paths.ROOT / "preflight.py").resolve() and all(
        _in_suite(f) and f.parent == (_paths.ROOT / "src/checks/suite").resolve() for f in files[1:]), (
        f"the suite's files are not preflight.py and the modules of src/checks/suite/: {files}")
    spaces = _suite_namespaces()
    homes = [Path(s.get("__file__") or ".").resolve() for _n, s in spaces]
    assert {id(c["fn"].__globals__) for c in CHECKS} <= {id(s) for _n, s in spaces} \
        and all(h in files for h in homes) and len({id(s) for _n, s in spaces}) == len(spaces), (
        "the suite's namespaces are not the module of every registered check and of the suite's "
        f"files, each once: {[n for n, _s in spaces]}")
    assert (_SWITCHED.published_scripts, _SWITCHED.testify_log, _SWITCHED.workflow_dir) == (
        False, None, Path(".github/workflows")), (
        f"a switch was left set by a check before this one: {vars(_SWITCHED)}")
    sample = ("def a(files):\n"
              "    for f in files:\n"
              "        if f.name == \"preflight.py\":\n"
              "            continue\n"
              "    g = globals()\n"
              "    return Path(__file__)\n\n\n"
              "def b():\n"
              "    global X\n"
              "    X = 1\n"
              "    return f.__module__ == __name__\n\n\n"
              "def c(cmd, m):\n"
              "    return Path(cmd).name == \"preflight.py\", m.__file__, \"__file__\", \"globals()\"\n\n\n"
              "def _suite_files():\n"
              "    return [Path(__file__)]\n")
    got = [(d, n) for d, n, _w in _self_references(ast.parse(sample))]
    assert got == [("a", 3), ("a", 5), ("a", 6), ("b", 10), ("b", 12)], (
        f"the reader of self-references found {got} in the sample, not its five")
    found = [x for f in _suite_files() for x in _self_references(_parsed(f))]
    assert not found, (
        f"{len(found)} places speak of this file rather than the suite: "
        + "; ".join(f"{d} line {n}: {w}" for d, n, w in found[:6])
        + ". Use _suite_files(), _in_suite(), _suite_namespaces() or _SWITCHED")
    return "ok", (f"no definition of the suite's {len(files)} file(s) walks globals(), rebinds a "
                  "switch, names __file__ or exempts preflight.py by name, but the suite's own words")


@check("files", "the registry, the runner and the helpers the checks share are modules of "
                "src/checks/suite/, in layers, which preflight.py imports and every reader of the "
                "suite reads")
def _suite_is_a_package():
    """THE RUNNER OUT OF THE SCRIPT (16 November 2026, the refactor's stage 1,
    step 4). The registry was a list in preflight.py, so while a run went on it
    was __main__'s, and a module that imported preflight would have had a
    second one, empty; and the checks could not move into modules of their own
    while the registry and the code they share were the script's. Held:

      src/checks/suite/ is a code folder (_paths.SRC_DIRS), and pf_core,
      pf_fixture, pf_harness and pf_runner are files of the suite;
      the registry is pf_core's, with check, imp and the reader of an
      answer, and main is pf_runner's: preflight.py defines none of them
      and imports each, and every check is defined in a file of the suite;
      each module uses only those below it -- pf_core no other of the
      suite's, pf_fixture and pf_harness pf_core, pf_runner those -- and
      none imports preflight;
      the walk of the suite reads the modules: _suite_namespaces names each,
      and a check that runs a page's script only through a helper of
      pf_harness is found to (_reaching);
      and the build reads a module of the suite, as it reads preflight.py,
      only for data.html's two counts (front_end.is_fact_source).
    """
    import front_end
    import pf_core
    import pf_fixture
    import pf_harness
    import pf_runner
    layers = [("pf_core", pf_core), ("pf_fixture", pf_fixture), ("pf_harness", pf_harness),
              ("pf_runner", pf_runner)]
    assert "src/checks/suite" in _paths.SRC_DIRS, (
        "src/checks/suite is not on _paths.SRC_DIRS, so no guard that reads the code folders "
        "reads the suite's modules")
    files = _suite_files()
    assert {f"{m}.py" for m, _mod in layers} <= {f.name for f in files}, (
        f"the suite's files are {[f.name for f in files]}")
    assert CHECKS is pf_core.CHECKS and check is pf_core.check and imp is pf_core.imp \
        and _answer is pf_core._answer and main is pf_runner.main, (
            "the registry, check, imp, _answer or main is not the suite's module's")
    tree = _parsed(files[0])
    own = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))} | {
        t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets
        if isinstance(t, ast.Name)}
    runner = {"CHECKS", "check", "imp", "_answer", "_settle", "_in_order", "_run", "main",
              "_changed_choice", "_start_early_builds", "_suite_files", "_SWITCHED"}
    assert not own & runner, (f"preflight.py defines {', '.join(sorted(own & runner))} itself, "
                              "beside the suite's modules")
    outside = [c["fn"].__name__ for c in CHECKS
               if Path(c["fn"].__code__.co_filename).resolve() not in files]
    assert not outside, f"{len(outside)} checks are defined outside the suite's files: {outside[:5]}"
    for i, (m, mod) in enumerate(layers):
        mt = _parsed(Path(mod.__file__))
        took = {a.name.split(".")[0] for n in ast.walk(mt) if isinstance(n, ast.Import)
                for a in n.names} | {n.module.split(".")[0] for n in ast.walk(mt)
                                     if isinstance(n, ast.ImportFrom) and n.module}
        theirs = {x for x in took if x.startswith("pf_") or x == "preflight"}
        assert theirs <= {n for n, _mod in layers[:i]}, (
            f"{m} imports {', '.join(sorted(theirs - {n for n, _mod in layers[:i]}))}, which is "
            "not below it")
    spaces = {n for n, _s in _suite_namespaces()}
    assert {m for m, _mod in layers} <= spaces, (
        f"the suite's namespaces are {sorted(spaces)}: a walk of the suite misses its modules")
    direct = {"_with_components", "_node_app"}
    callers = [c for c in CHECKS if "_app_js" in c["fn"].__code__.co_names]
    found = {id(c) for c in _reaching(direct)}
    missed = [c["fn"].__name__ for c in callers if id(c) not in found]
    assert callers and not missed, (
        f"{len(missed)} of the {len(callers)} checks that call _app_js, pf_harness's harness of "
        "app.js, are not found to run a page's script: the walk of the suite does not follow its "
        "modules' functions (" + ", ".join(missed[:4]) + ")")
    for path, want in (("preflight.py", True), ("src/checks/suite/pf_core.py", True),
                       ("src/checks/suite/pf_votes.py", True), ("src/checks/check_select.py", False),
                       ("src/checks/suite/README.md", False)):
        assert front_end.is_fact_source(path) is want, (
            f"the fast path takes {path} as {'no ' if want else ''}file read only for data.html's counts")
    return "ok", (f"{len(layers)} modules of src/checks/suite/ in layers, the registry pf_core's and "
                  f"main pf_runner's; {len(CHECKS)} checks in the suite's files; all {len(callers)} "
                  "that call pf_harness's _app_js found to run a page's script; a module of the "
                  "suite is a count's source to the fast path")


@check("files", "changed modules import")
def _import_all():
    """EVERY MODULE A CHECK NEEDS, NOT A LIST KEPT BY HAND (1 October 2026).

    A check whose `needs=` module will not import is SKIPPED: main() says
    "x.py will not import" among the skips, the run stays green, and every
    assertion in that check has stopped guarding anything. This was the one
    place an import error failed, and it named nine modules by hand while the
    checks had come to need seventy-six -- so an error importing nightly.py
    would have skipped the fifteen checks that need it and failed none. The
    list is read off the checks themselves now: every module named in any
    `needs=`, and the two the old list named that checks import for
    themselves. A module a check needs that is not here at all fails too:
    its checks can never run.

    It is also the alarm for a moved file. The refactor's last phase moves
    the scripts into folders, and a module left behind by a move shows up
    here as a failure, where it would otherwise show up as a longer list of
    skips that nobody reads.

    AND EVERY SCRIPT THAT RUNS UNATTENDED, WHETHER A CHECK NEEDS IT OR NOT
    (the review of the above, the same day). The checks' needs= is what the
    checks import, not what the night runs: twenty-two scripts that
    build_all.py, nightly.py, the laptop's evening job and the lane name
    were in no check's needs= -- fetch_lsrs.py, check_site.py and
    build_calendar.py among them -- so an import error in one, or a move
    that left one behind, stayed green here and failed at four in the
    morning. So the list is read off the runners as well (_scripts_run):
    each script one of them names is imported, and one that build_all.py,
    nightly.py or the lane names and that is not here fails by name. (The
    laptop's evening job was one of them until it was retired on 10 October
    2026.)
    """
    ALSO = ("floor_markers", "apply_markers")
    mods = sorted({n for c in CHECKS for n in c["needs"]} | set(ALSO))
    # A floor, so that this cannot pass by reading no list at all.
    assert len(mods) >= 70, (
        f"only {len(mods)} modules are named in the checks' needs=; there were 76 when this "
        "was written, so the list is not being read")
    runs, gone = _scripts_run()
    assert len(runs) >= 55, (
        f"only {len(runs)} scripts are named by {', '.join(_RUNNERS)}; there were 68 when "
        "this was written, so the runners are not being read")
    bad = [f"{n}: {src} names {n}.py and it is not here" for n, src in sorted(gone.items())]
    for m in mods + sorted(set(runs) - set(mods)):
        if _paths.find(m + ".py") is None:
            bad.append(f"{m}: a check needs it and {m}.py is in no code folder")
            continue
        try:
            __import__(m)
        except Exception as e:                                  # noqa: BLE001
            bad.append(f"{m}: {type(e).__name__}: {str(e)[:90]}"
                       + (f" ({runs[m]} runs it)" if m not in mods else ""))
    assert not bad, (f"{len(bad)} module(s) the checks need or the night runs will not "
                     "import -- a check that needs one would be skipped, not failed, and "
                     "a step that runs one fails where nobody is watching: " + "; ".join(bad))
    return "ok", (f"all {len(mods)} modules the checks need import, and the "
                  f"{len(set(runs) - set(mods))} more that only the build, the night or the "
                  "lane run")


def _scripts_run():
    """({module: the runner that names it}, {module: runner} for one a runner
    names that is not in this folder). preflight itself is left out: it is
    the script doing the asking."""
    here, gone = {}, {}
    for src in _RUNNERS:
        f = _paths.locate(src)
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        code = src.endswith(".py")
        pat = r"""["']([A-Za-z_]\w*)\.py["']""" if code else r"(?<![\w/.-])([A-Za-z_]\w*)\.py\b"
        for n in sorted(set(re.findall(pat, text)) - {"preflight"}):
            if _paths.find(n + ".py") is not None:
                here.setdefault(n, src)
            elif code:
                gone.setdefault(n, src)
    return here, gone


# ====================================================== files: where the code lives ==
#
# THE CODE IS MOVING INTO src/ (6 October 2026; src/README.md, and the stages
# of the folder map). Every import, build_all step, lane line and launch finds
# a file by its bare name through _paths.py, so a file can move between code
# folders without anything that names it changing. What keeps that true while
# files move is below: a name two folders share, a script that does not
# bootstrap, a name a runner uses that finds no file, a file in the folder of
# a network it does not ask (or asking one its folder does not allow), and a
# code path git cannot see. Each reads the folders rather than a list of
# files, so it holds before, during and after the move. The guards that read
# every script -- refusal, the hand-made files, committee_details, the shared
# files -- carry floors of their own: what they read on 6 October, before any
# file moved, so that one reading only the root after a move fails rather
# than passing on nothing.

def _code_name_clashes(root=None):
    """{bare name: [its paths]} for every name two code files share: any
    file under src/ but a README.md, and every .py of the root, watchers/ and
    tests/ (which also hold data, whose names are not the question), and every
    browser's file there (_paths.BROWSER), which _paths.locate finds by its
    bare name as it finds a script: dom_stub.js is in tests/."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    seen = {}
    for d in _paths.code_dirs(base):
        in_src = d != base and d.relative_to(base).parts[0] == "src"
        for f in sorted(d.iterdir()):
            if f.is_file() and f.name != "README.md" and (
                    in_src or f.suffix == ".py" or f.suffix in _paths.BROWSER):
                seen.setdefault(f.name, []).append(f.relative_to(base).as_posix())
    return {n: ps for n, ps in sorted(seen.items()) if len(ps) > 1}


def _code_dirs_unlisted(root=None):
    """Folders under src/ that hold code -- a script, or a browser's file
    (_paths.BROWSER) -- and are not on _paths.SRC_DIRS: what is in one is on
    nobody's import path, and no guard that reads every script (SCRIPT_DIRS)
    reads it. A folder that holds data a module reads by its own path, as
    components.py reads src/pages/words/ (9 October 2026), holds no code, is
    imported by nobody, and is not one. Nor is a builder's inline/ folder
    beside a code folder (inline_js, 20 November 2026): scripts its builder
    reads by their path and writes into its pages, and nothing imports."""
    import inline_js as IJ
    base = Path(root).resolve() if root is not None else _paths.ROOT
    listed = {(base / d).resolve() for d in _paths.SRC_DIRS}
    src = base / "src"
    if not src.is_dir():
        return []

    def inline(d):
        return d.name == IJ.FOLDER and d.parent.resolve() in listed and all(
            f.suffix == ".js" for f in d.iterdir() if f.is_file())
    return [d.relative_to(base).as_posix()
            for d in sorted(p for p in src.rglob("*") if p.is_dir() and p.name != "__pycache__")
            if d.resolve() not in listed and not inline(d)
            and any(f.is_file() and (f.suffix == ".py" or f.suffix in _paths.BROWSER)
                    for f in d.iterdir())]


def _src_dirs_off_list(code_dirs, src_dirs):
    """The folders under src/ on CODE_DIRS that are not on SRC_DIRS. Such a
    folder is on the import path and yet unread by the refusal, hand-made-file
    and merge-not-replace guards, which read SCRIPT_DIRS, the root and
    SRC_DIRS: put a fetcher there and nothing asks whether it calls
    refusal.check()."""
    return [d for d in code_dirs if d.startswith("src/") and d not in src_dirs]


@check("files", "a bare name finds one file: no two code files share a name, and every "
                "folder under src/ that holds code is on _paths.SRC_DIRS")
def _code_names_unique():
    """Every import and every launch here is by bare name, and _paths puts
    every code folder on the path, so two files of one name would be one
    import shadowing the other in whichever order the folders happen to be
    read -- and _paths.script refuses to choose. A README.md in each folder
    is the one name allowed to repeat. A folder under src/ that is not on
    _paths.SRC_DIRS is on nobody's path, and its files would not import; one
    put on CODE_DIRS by hand rather than through SRC_DIRS would import and be
    read by none of the guards that read SCRIPT_DIRS."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-names-"))
    try:
        _plant(tmp, {"_paths.py": "", "a.py": "", "src/parse/a.py": "", "src/parse/README.md": "",
                     "src/pages/README.md": "", "src/pages/b.js": "", "tests/b.js": "",
                     "watchers/c.py": "", "tests/c.py": "", "notes.json": "",
                     "tests/notes.json": "", "src/extra/d.py": "", "src/web/e.js": "",
                     "src/pages/words/w.json": "", "src/pages/words/README.md": "",
                     "src/pages/inline/b.js": "", "src/parse/inline/f.py": ""})
        got = _code_name_clashes(tmp)
        assert got == {"a.py": ["a.py", "src/parse/a.py"], "b.js": ["src/pages/b.js", "tests/b.js"],
                       "c.py": ["watchers/c.py", "tests/c.py"]}, \
            f"the reader of names found {got} in a tree made to share three"
        assert _code_dirs_unlisted(tmp) == ["src/extra", "src/parse/inline", "src/web"], \
            _code_dirs_unlisted(tmp)
        off = _src_dirs_off_list(("", "src/parse", "src/extra", "watchers"), ("src/parse",))
        assert off == ["src/extra"], f"the reader of the lists found {off}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    clashes = _code_name_clashes()
    assert not clashes, ("these names are used by more than one code file, so a bare name "
                         "finds two: " + "; ".join(f"{n} ({', '.join(ps)})"
                                                    for n, ps in clashes.items()))
    off = _src_dirs_off_list(_paths.CODE_DIRS, _paths.SRC_DIRS)
    assert not off, ("these folders under src/ are on _paths.CODE_DIRS and not SRC_DIRS, so "
                     "they import and no guard that reads every script reads them: "
                     + ", ".join(off) + ". Put each on SRC_DIRS, which CODE_DIRS is made from.")
    unlisted = _code_dirs_unlisted()
    assert not unlisted, ("these folders under src/ hold code and are not on "
                          "_paths.SRC_DIRS, so nothing can import what is in them: "
                          + ", ".join(unlisted) + ". Add each to SRC_DIRS.")
    n = len(_paths.code_files("*.py"))
    assert n >= 160, f"only {n} scripts were read in the code folders; there were 165 on 6 October"
    return "ok", f"{n} scripts across {len(_paths.code_dirs())} code folders, each name once"


# A BUILDER'S OWN SCRIPTS ARE FILES (20 November 2026, the refactor's finding 5).
# What were JavaScript strings in a builder are .js files in inline/ beside it,
# which inline_js reads and the builder writes into its page as the string was
# (src/pages/README.md). A script's marks, in a string of a builder that has
# moved its scripts: a function, an arrow, a listener, the page or the window,
# a declaration.
_INLINE_MARK = re.compile(r"\bfunction\s*\w*\s*\(|=>|\baddEventListener\s*\(|\bdocument\.\w"
                          r"|\bwindow\.\w|\b(?:var|let|const)\s+\w+\s*=")
# Kept in a builder that has moved its scripts, each (module, the name assigned)
# with its reason.
_INLINE_KEPT = {
    # The Calendar's picker in Spanish: pairs of (a piece of the English script,
    # what replaces it), put over inline/calendar_documents.picker.js by
    # picker_js(). A patch of pieces, not a script; each piece is checked to
    # be in the script once, as it is applied.
    ("calendar_documents", "PICKER_ES"),
    # The head of the file the build writes from app.js's BILLMATCH regions
    # for find.js (bill_matcher_js): three lines around app.js's own code,
    # starting a file of its own in site/, and no page's script.
    ("build_pages", "BILLMATCH_HEAD"),
    # The Calendar's script in Spanish: pairs of (a piece of the English script,
    # what replaces it), put over inline/build_calendar.js by week_js(), as
    # PICKER_ES is over the picker's. Each piece is checked to be in the
    # script once, as it is applied.
    ("build_calendar", "WEEK_ES"),
}


def _inline_faults(trees, names):
    """What is wrong with the builders' inline scripts, as sentences.
    `trees` is {module: its parse} of the code files (the suite's left out),
    `names` the inline scripts there are (inline_js.files()). A script read
    by no module or by more than one, or by a module that is not the builder
    its name begins with; a script read that is not there; a call that does
    not write its script's name out; a module but inline_js and the
    translation audit naming an inline/ path itself; and a builder that has
    scripts in inline/ and still holds one in a string of three lines or
    more (_INLINE_MARK), but for _INLINE_KEPT."""
    faults, readers = [], {}
    for mod, tree in sorted(trees.items()):
        alias = {a.asname or a.name for n in ast.walk(tree) if isinstance(n, ast.Import)
                 for a in n.names if a.name == "inline_js"}
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "script" \
                    and isinstance(n.func.value, ast.Name) and n.func.value.id in alias:
                arg = n.args[0] if n.args else None
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    readers.setdefault(arg.value, []).append(mod)
                else:
                    faults.append(f"{mod}:{n.lineno} reads a script whose name is not written out")
            elif mod not in ("inline_js", "translation_audit") and isinstance(n, ast.Constant) \
                    and isinstance(n.value, str) and id(n) not in docs \
                    and re.search(r"(?:^|[/\\])inline[/\\]", n.value):
                faults.append(f"{mod}:{n.lineno} reads inline/ itself, not through inline_js")
    for name in sorted(names):
        got, own = readers.get(name, []), name.split(".")[0]
        if len(got) != 1:
            faults.append(f"inline/{name}.js is read by {len(got)} modules "
                          f"({', '.join(got) or 'none'}), not by its builder alone")
        elif got[0] != own:
            faults.append(f"inline/{name}.js is read by {got[0]}, not by {own}")
    faults += [f"{', '.join(readers[n])} reads inline/{n}.js, which is not there"
               for n in sorted(set(readers) - set(names))]
    for mod in sorted({n.split(".")[0] for n in names} & set(trees)):
        tree = trees[mod]
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and n.body and isinstance(n.body[0], ast.Expr)}
        kept = {id(c) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(x, ast.Name) and (mod, x.id) in _INLINE_KEPT for x in n.targets)
                for c in ast.walk(n.value)}
        parts = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
        for n in ast.walk(tree):
            if id(n) in docs or id(n) in kept or id(n) in parts \
                    or getattr(n, "end_lineno", None) is None:
                continue
            if isinstance(n, ast.JoinedStr):
                text = "".join(v.value for v in n.values if isinstance(v, ast.Constant))
            elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                text = n.value
            else:
                continue
            m = _INLINE_MARK.search(text) if n.end_lineno - n.lineno >= 2 else None
            if m:
                faults.append(f"{mod}:{n.lineno} still holds a script in a string ({m.group(0)!r}); "
                              "its scripts are in inline/")
    return faults


@check("files", "a builder's own scripts are files in inline/ beside it, each read by that builder "
                "alone through inline_js, which refuses a hole left empty or a value with no hole; "
                "and a builder that has them holds no script in a string")
def _inline_scripts_read_once():
    """The scripts a builder writes into its pages are .js files in inline/
    beside it (inline_js, 20 November 2026), so that a JavaScript tool, the
    search for dead code and a check of a twin can read them, and the page
    is the same to the byte. Held here:

      the reader: a hole (__NAME__) with no value, a value with no hole and
      a value that is not a string are refused; a hole is filled in one pass
      and JavaScript's own braces and __proto__ are not holes; a name that is
      not <builder> or <builder>.<what>, or names no builder, is refused;
      every file is where its name says, inline/ beside its builder;
      the rule (_inline_faults), on planted code that breaks each part of
      it, and on the code: each script read by its builder alone and by
      name, none read from inline/ but through inline_js, and no builder
      that has scripts there holding one in a string but _INLINE_KEPT's.
    """
    import inline_js as IJ
    for text, values, why in (("a __A__ b", {}, "a hole no value fills"),
                              ("a b", {"A": "1"}, "a value no hole takes"),
                              ("a __A__", {"A": 1}, "a value that is not a string")):
        try:
            IJ.fill(text, values)
        except ValueError:
            continue
        raise AssertionError(f"inline_js.fill took {why}")
    got = IJ.fill("x=__A__;y=__proto__;f(){return {a:1}};__A__", {"A": "__B__"})
    assert got == "x=__B__;y=__proto__;f(){return {a:1}};__B__", f"inline_js.fill gave {got!r}"
    for bad in ("../app", "Build_civics", "build_civics.a.b", "", "build_civics/otp"):
        try:
            IJ.path(bad)
        except ValueError:
            continue
        raise AssertionError(f"inline_js took {bad!r} for a script's name")
    try:
        IJ.path("no_builder_has_this_name.x")
        raise AssertionError("inline_js found a script for a builder that is not there")
    except LookupError:
        pass
    # The rule, on planted code.
    ok = {"build_a": ast.parse('import inline_js as IJ\nJS = "<script>\\n" + IJ.script("build_a") '
                               '+ "</script>"\n')}
    assert _inline_faults(ok, {"build_a"}) == [], _inline_faults(ok, {"build_a"})
    planted = {
        "build_a": ast.parse('import inline_js as IJ\nJS = IJ.script("build_a")\n'
                             'OLD = """<script>\n(function(){\n  document.title="x";\n})();\n</script>"""\n'
                             'KEEP = """a\nb\nc"""\n'),
        "build_b": ast.parse('import inline_js as J\nX = J.script("build_a")\nY = J.script(NAME)\n'
                             'Z = J.script("build_b.gone")\nW = open("src/pages/inline/build_b.x.js").read()\n'),
    }
    got = _inline_faults(planted, {"build_a", "build_b.x"})
    want = ("build_b:3 reads a script whose name is not written out",
            "build_b:5 reads inline/ itself", "inline/build_a.js is read by 2 modules",
            "inline/build_b.x.js is read by 0 modules", "reads inline/build_b.gone.js, which is not there",
            "build_a:3 still holds a script in a string")
    missed = [w for w in want if not any(w in g for g in got)]
    assert not missed and len(got) == len(want), (
        f"the rule missed {missed} in planted code, or found more: {got}")
    # The code.
    names = IJ.files()
    for name, p in names.items():
        assert p == IJ.path(name), f"{p} is not where its name says: {IJ.path(name)}"
    trees = {f.stem: _parsed(f) for f in _paths.code_files("*.py") if not _in_suite(f)}
    faults = _inline_faults(trees, set(names))
    assert not faults, f"{len(faults)} faults in the builders' inline scripts: " + "; ".join(faults[:6])
    builders = sorted({n.split(".")[0] for n in names})
    assert len(names) >= 32 and len(builders) >= 16, (
        f"only {len(names)} inline scripts of {len(builders)} builders: there were 32 of 16 on "
        "20 November 2026")
    return "ok", (f"{len(names)} scripts in inline/ of {len(builders)} builders, each read by its own "
                  "builder alone, by name, through inline_js; none of those builders holds a script "
                  "in a string but the Spanish patches of the picker and the Calendar and the bill "
                  "matcher's head; the reader "
                  "refuses a hole left empty, a value with no hole and a value that is not a string")


def _import_graph(files=None):
    """{module: {the project's modules it imports}} of every code file (or of
    `files`), by bare name, counting an import anywhere in a file: at the top,
    inside a function, under __main__. An import by a string (imp(), needs=)
    is not counted: it is the suite's, and imports nothing at load."""
    files = _paths.code_files("*.py") if files is None else files
    names = {Path(f).stem for f in files}
    graph = {}
    for f in files:
        own = Path(f).stem
        out = graph.setdefault(own, set())
        for n in ast.walk(_parsed(f)):
            if isinstance(n, ast.Import):
                out |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
                out.add(n.module.split(".")[0])
        out &= names - {own}
    return graph


def _import_cycles(graph):
    """The import cycles of `graph`, as sorted tuples of the modules each ties
    together (the strongly connected parts of more than one module), largest
    first. Tarjan's, without recursion."""
    index, low, on, stack, out = {}, {}, set(), [], []
    for root in sorted(graph):
        if root in index:
            continue
        work = [(root, iter(sorted(graph.get(root, ()))))]
        index[root] = low[root] = len(index)
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            w = next(it, None)
            if w is not None:
                if w not in index:
                    index[w] = low[w] = len(index)
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(graph.get(w, ())))))
                elif w in on:
                    low[v] = min(low[v], index[w])
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    x = stack.pop()
                    on.discard(x)
                    comp.append(x)
                    if x == v:
                        break
                if len(comp) > 1:
                    out.append(tuple(sorted(comp)))
    return sorted(out, key=lambda c: (-len(c), c))


# THE IMPORT CYCLES THERE ARE, AND NO MORE (the refactor's stage 3, 19 November 2026). On
# 16 November thirty modules of src/pages imported one another in one knot, and two things
# held it: i18n's translation audit, which read the builders' word lists from the module every
# builder imports, and builders used as libraries by other builders. Each was cut by moving
# code, not by rewriting it (reports/refactor/stage0-code.md, section 9, step 3). These are
# the cycles left; a change that ties a new one, or grows one of these, fails here.
_IMPORT_CYCLES_KNOWN = {
    ("cloud", "livestreams", "refusal", "state_sources"),
    ("past_roster", "past_sponsors", "text_sponsors"),
    ("api_db", "api_schema"),
    ("build_elections", "build_member_elections"),
    ("build_lsrs", "request_topics"),
    ("build_past_roster", "past_roll"),
    ("caption_span", "segment_markers"),
    ("civics", "legislative_year"),
    ("parse_sos_primary_offices", "parse_sos_primary_results"),
    ("proceedings", "terms"),
}
# The imports those moves cut, (importer, what it imported): each piece lives now where the
# comment says, and the importer takes it from there.
_IMPORTS_CUT = {
    ("i18n", "guides"), ("i18n", "build_civics"), ("i18n", "officials_tabs"),
    ("i18n", "build_pages"), ("i18n", "legislative_year"),      # translation_audit.py
    ("build_calendar", "build_pages"), ("build_live", "build_pages"),
    ("latest_activity", "build_pages"), ("officials_tabs", "build_pages"),
    ("officials_tabs", "build_site_v2"), ("officials_tabs", "build_town_pages"),
    ("build_town_pages", "build_pages"), ("build_pages", "build_town_pages"),   # parts.py
    ("live_hook", "build_live"),                                # live_hook.past_stems
    ("request_topics", "build_site_v2"),                        # topic_vocabulary.py
    ("archive_text", "fetch_legislation"), ("build_data", "fetch_legislation"),
    ("past_sponsors", "fetch_legislation"), ("referrals", "fetch_legislation"),
    ("text_sponsors", "fetch_legislation"),                     # legislation_text.py
    ("extract_amendments", "fetch_committee_reports"),
    ("interim_statements", "fetch_committee_reports"),          # committee_report_text.py
    ("docket_vocab", "narrative"),                              # docket_lines.py
}


@check("files", "the code's import cycles are the known ones and no more: i18n, which every "
                "page imports, imports none of the builders, and no builder is in a cycle")
def _import_cycles_cut():
    """A module that every builder imports and that imports a builder ties
    the whole folder into one cycle: i18n's translation audit did, until it
    became translation_audit.py. A cycle works while each side uses the
    other's names only at call time, and stops working when code moves
    across the line that imports, so the cycles there are are listed here
    (_IMPORT_CYCLES_KNOWN), and a new one or a bigger one fails. A cycle
    taken apart comes off the list in the same commit."""
    planted = {"a": {"b"}, "b": {"c"}, "c": {"a"}, "d": {"a", "e"}, "e": {"d"}, "f": set()}
    got = _import_cycles(planted)
    assert got == [("a", "b", "c"), ("d", "e")], f"the cycle reader found {got} in a planted graph"
    graph = _import_graph()
    assert len(graph) >= 160 and "i18n" in graph and "build_pages" in graph, len(graph)
    cycles = set(_import_cycles(graph))
    tied = [c for c in cycles if "i18n" in c or "translation_audit" in c]
    assert not tied, f"i18n is in an import cycle again: {tied}"
    # The builders that took a helper from another builder take it from parts.py
    # (19 November 2026): none of the knot's builders is in a cycle again.
    builders = {"build_pages", "build_calendar", "build_live", "build_town_pages", "build_site_v2",
                "build_committees", "build_session_pages", "officials_tabs", "latest_activity",
                "live_hook", "parts"}
    tied = [c for c in cycles if builders & set(c)]
    assert not tied, ("a builder is in an import cycle again; take what two builders share "
                      f"from parts.py rather than from either: {tied}")
    # And the imports that were cut stay cut, cycle or not: each was one module
    # reaching into another for a piece that is now a module of its own.
    back = sorted(f"{a} -> {b}" for a, b in _IMPORTS_CUT if b in graph.get(a, ()))
    assert not back, ("an import cut on 19 November 2026 is back; take the piece from where "
                      "it lives now (_IMPORTS_CUT says where): " + ", ".join(back))
    new = sorted(cycles - _IMPORT_CYCLES_KNOWN)
    gone = sorted(_IMPORT_CYCLES_KNOWN - cycles)
    assert not new, ("an import cycle that is not on _IMPORT_CYCLES_KNOWN, new or grown: "
                     + "; ".join(" <-> ".join(c) for c in new)
                     + ". Import the shared piece from a module both can import instead.")
    assert not gone, ("these cycles on _IMPORT_CYCLES_KNOWN are gone: take them off the list "
                      "so they cannot come back unseen: "
                      + "; ".join(" <-> ".join(c) for c in gone))
    return "ok", (f"{len(graph)} modules, {len(cycles)} import cycles, all known (the largest "
                  f"{max(map(len, cycles), default=0)} modules); i18n and the page builders in none")


# THE MODULES build_site_v2.py IS SPLIT INTO (the refactor's finding 4, 20 November 2026), each
# with the names it took. build_site_v2 imports each back under its name, so build_site_v2.<name>
# answers for every caller as it did; the checks below hold each move made whole and not undone.
_SPLIT_FROM_SITE = {
    "parts": ("BILL_OF_INTENT", "SINGLE_CHAMBER", "NO_GOVERNOR", "bill_prefix", "CHIP_WORDS",
              "BECAME_LAW", "DIED", "INTERIM_STUDY", "TABLED", "VETOED", "WITHDRAWN", "SIGNED_RE",
              "REFERENDUM", "docket_line", "TABLE_DEATH"),
    "conferences": ("CONF_REPORT", "CONF_FAILED", "NEW_CONF", "NEXT_MOTION", "CONF_REJECTED",
                    "CONF_UNABLE", "CONF_UNABLE_RE", "CHAMBERS_APART", "ENDED_AS",
                    "CONF_UNSIGNED_RE", "CONF_LATE_RE", "FAILURE_RANK", "_failure_how",
                    "conference_failure", "conferees_disagreed", "_conference_vote",
                    "conference_outcome", "concurrence_outcome", "BEFORE_CONFERENCE",
                    "BEFORE_CONCURRENCE", "BEFORE_UNABLE", "CONFERENCE_ROW", "between_chambers",
                    "CONF_NOT_TAKEN_UP", "conference_not_taken_up"),
    "journey": tuple(("J_ACTS J_AMENDED J_AMEND_ADOPTED J_AMEND_LIST J_AMEND_SUBJ "
                      "J_BARE_REFERRAL J_CHAPTERED J_CHAPTER_THEN_DAY J_CLAUSE_DAY "
                      "J_CONF J_DAY J_DIVIDED_OUT J_DONE_VERB J_EFF_ANY J_EFF_MORE "
                      "J_EFF_PART J_EFF_PROVIDED J_EFF_SEVERAL J_EFF_WHAT J_ENDING "
                      "J_FILED J_FROM_REPORT J_IF_PASSED J_INTRO_ROW J_MARK J_MON "
                      "J_MONTH_DAY J_NEW_CONFERENCE J_NOT_FLOOR J_NOT_VOTED J_NO_CODE "
                      "J_NO_WORD J_ON_THE_TABLE J_OTHER_BILL J_OUTCOME_ONLY J_PASSING "
                      "J_RC_BARE J_RECONSIDER J_RECON_END J_RECON_NAMES J_RECON_NOT "
                      "J_REFERRED_TO J_REF_TALLY J_REMAINING J_ROW_DAY "
                      "J_SECOND_COMMITTEE J_SIGNED J_SKIP J_SUSPEND J_SUSPENDED "
                      "J_SUSP_CODE J_SUSP_REFERRAL J_SUSP_VOTE J_SUSP_WORD "
                      "J_TAKES_OUTCOME J_TALLY J_TALLY_TAIL J_THIRD J_UNSIGNED "
                      "J_VETOED J_VETO_VOTE J_VOICE J_WAIVED J_WRAPPED_TALLY "
                      "J_YES_CODE J_YES_WORD ONE_CHAMBER OWN_CHAMBER RAIL_ACT "
                      "RAIL_DEAD_TABLE RAIL_MARK_OF_CHIP RAIL_REFINES RAIL_SAY "
                      "STAGES_FROM _STAGE_END _j_act _j_act_sections _j_amended_on "
                      "_j_answers_after _j_chaptered _j_clauses _j_days _j_decide "
                      "_j_effective _j_effective_parts _j_gov_more _j_has_outcome "
                      "_j_in_recess _j_in_term _j_introduced _j_iso _j_merge _j_motion "
                      "_j_motions _j_outcome _j_prose_date _j_reconsidered "
                      "_j_roll_call _j_row_day _j_rows _j_second_committee _j_sections "
                      "_j_segments _j_settle _j_stated_day _j_suspension_failed "
                      "_j_tally _j_unfile _j_unsuspend _j_untold _j_vote_words "
                      "_j_words _j_year_slip _journey_rail journey journey_rail "
                      "journey_state law_day law_in_stages law_line_dated passage").split()),
    "status": tuple(("CLOSING CONF_NEVER_REPORTED CONF_REPORT_NOT_TAKEN_UP "
                     "CONF_UNABLE_CLOSING DISPOSED ENDED_UNFINISHED ENDED_UNVOTED "
                     "ENDING_UNTOLD JOURNAL_SOURCE NEVER_INTRODUCED NOT_INTRODUCED "
                     "ONE_CHAMBER_DONE PROPOSED_ONLY RECONSIDER_CARRIED RETURNED_ROW "
                     "SESSION_ENDED_AFTER_FAILED SESSION_ENDED_AFTER_VOTES "
                     "SESSION_ENDED_PLAINLY STATED UNTOLD_FOR WITHDRAWN_ACT "
                     "WITHDRAWN_PRIOR _long_date classify classify_stated "
                     "closing_stage docket_outcome floor_disposed for_bill_kind "
                     "journal_not_introduced last_decision next_step untold_ending "
                     "veto_outcome veto_votes").split()),
}


def _top_names(tree):
    """{name: "defined" | "imported"} of what a module's own top level binds."""
    out = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[n.name] = "defined"
        elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                for x in ast.walk(t):
                    if isinstance(x, ast.Name):
                        out[x.id] = "defined"
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                out.setdefault(a.asname or a.name, "imported")
    return out


def _split_out(site, mod, names):
    """What is wrong with `names` having moved out of build_site_v2 (`site`) into the module
    `mod`, as strings: a name the module does not define itself, one build_site_v2 defines
    again rather than imports, and one build_site_v2 answers with something else than the
    module's. Read from the two files as they stand and from the two modules imported."""
    module = mod.__name__
    mine, theirs = _top_names(_parsed(mod.__file__)), _top_names(_parsed(site.__file__))
    bad = [f"{module}.py does not define {n}" for n in names if mine.get(n) != "defined"]
    bad += [f"build_site_v2.py defines {n} again; it imports it from {module}" for n in names
            if theirs.get(n) == "defined"]
    bad += [f"build_site_v2.{n} is not {module}.{n}" for n in names
            if getattr(site, n, None) is not getattr(mod, n, object())]
    return bad


@check("files", "the pieces of build_site_v2 its split modules share are parts.py's, defined there "
                "and imported back, so build_site_v2.<name> is parts.<name>",
       needs=("build_site_v2", "parts"))
def _site_shares_from_parts(B, PARTS):
    """What a bill of each kind has to clear, bill_prefix, the chip's six words, SIGNED_RE,
    REFERENDUM, docket_line and TABLE_DEATH moved from build_site_v2 to parts.py on 20
    November 2026 (the refactor's finding 4), as they stood, so that a module split out of
    build_site_v2 can read them without importing it back (_import_cycles_cut). Undone, half done, or copied back
    into build_site_v2 beside parts' own, this says which name."""
    names = _SPLIT_FROM_SITE["parts"]
    bad = _split_out(B, PARTS, names)
    assert not bad, "; ".join(bad)
    return "ok", (f"{len(names)} names defined in parts.py, none in build_site_v2.py, each "
                  "build_site_v2.<name> parts' own")


@check("files", "what the two chambers did with each other's version is conferences.py's, every "
                "name of it imported back into build_site_v2",
       needs=("build_site_v2", "conferences"))
def _site_conferences_moved(B, CF):
    """build_site_v2's section on what the two chambers did with each other's version --
    concurrences, committees of conference, conferees who could not agree -- moved to
    conferences.py on 20 November 2026 (the refactor's finding 4), as it stood, because the
    journey reads conference_failure and is a module of its own; and conference_not_taken_up,
    which the status reads, after it. Every name of them is held to be conferences.py's,
    defined nowhere in build_site_v2.py, and build_site_v2.<name> the same object."""
    names = _SPLIT_FROM_SITE["conferences"]
    bad = _split_out(B, CF, names)
    assert not bad, "; ".join(bad)
    return "ok", (f"{len(names)} names defined in conferences.py and nowhere in build_site_v2.py, "
                  "each build_site_v2.<name> conferences' own")


@check("files", "the passage rail and the journey are journey.py's, every name of them imported back "
                "into build_site_v2, and build_site_v2 defines no _j_ reader of its own",
       needs=("build_site_v2", "journey"))
def _site_journey_moved(B, J):
    """build_site_v2's largest subsystem -- passage, the four stops a bill passes, and the
    journey, what each chamber decided and when, with every _j_ reader and J_ pattern, RAIL_SAY
    and J_ENDING -- moved to journey.py on 20 November 2026 (the refactor's finding 4), as it
    stood. Every name it took is held to be journey.py's, defined nowhere in build_site_v2.py,
    and build_site_v2.<name> the same object, so the callers of build_site_v2.journey, its
    checks among them, read the one journey. And no _j_ reader is defined in build_site_v2.py:
    a new one goes beside the others, where the journey can call it. (J_DECIDED_ACT stays in
    build_site_v2 with journal_decided_story, the one reader of it.)"""
    names = _SPLIT_FROM_SITE["journey"]
    bad = _split_out(B, J, names)
    own = sorted(n for n, how in _top_names(_parsed(B.__file__)).items()
                 if how == "defined" and n.startswith("_j_"))
    if own:
        bad.append("build_site_v2.py defines journey readers of its own: " + ", ".join(own))
    assert not bad, "; ".join(bad[:8])
    return "ok", (f"{len(names)} names defined in journey.py and nowhere in build_site_v2.py, "
                  "each build_site_v2.<name> the journey's own; no _j_ reader left in build_site_v2")


@check("files", "a bill's status -- the status vocabulary and classify, closing_stage and next_step -- "
                "is status.py's, every name of it imported back into build_site_v2",
       needs=("build_site_v2", "status"))
def _site_status_moved(B, STA):
    """build_site_v2's status classification moved to status.py on 20 November 2026 (the
    refactor's finding 4), as it stood, from three places in the file: the status vocabulary
    (for_bill_kind, STATED and the statuses of a bill never introduced), journal_not_introduced,
    and classify_stated to next_step -- classify, docket_outcome, closing_stage and the endings
    the docket does not tell among them. Every name of them is held to be status.py's, defined
    nowhere in build_site_v2.py, and build_site_v2.<name> the same object, so bill_disposition,
    build_bills and the checks that ask build_site_v2.classify read the one classification."""
    names = _SPLIT_FROM_SITE["status"]
    bad = _split_out(B, STA, names)
    assert not bad, "; ".join(bad[:8])
    return "ok", (f"{len(names)} names defined in status.py and nowhere in build_site_v2.py, "
                  "each build_site_v2.<name> the status's own")


def _readme_unlisted(folder, root=None):
    """The modules (.py files but for __init__) of `folder` that its README.md
    does not name as `name` or `name.py` in backticks."""
    root = Path(root) if root else _paths.ROOT
    text = (root / folder / "README.md").read_text(encoding="utf-8")
    return [p.stem for p in sorted((root / folder).glob("*.py"))
            if p.stem != "__init__" and f"`{p.stem}`" not in text and f"`{p.name}`" not in text]


@check("files", "the READMEs of src/lib, src/ops, src/pages, src/parse and src/hearings name "
                 "every module in their folder, and src/pages's every browser file; src/TWINS.md "
                 "names checks and files that are there")
def _shared_folder_readmes_list_every_module():
    """The audit of 14 November 2026 found src/lib/README.md leaving out
    people, spellings and state_settings, and src/ops/README.md leaving out
    person_numbers, record_moves and five more: a folder README that lists
    some of its modules reads as the whole list.

    The refactor's stage 1 (19 November 2026) gave src/pages, src/parse and
    src/hearings the same: src/pages/README.md named 20 of its 72 code files,
    src/parse's 63 of 76 and src/hearings's 9 of 13. src/pages's browser
    files (.js, .css, .html) are held too, since the folder is flat and its
    README is the only map of it. And src/TWINS.md, the register of the
    twins written the same day, is held to the suite and the tree it names."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-readme-"))
    try:
        _plant(tmp, {"src/lib/README.md": "`a` and `b.py`", "src/lib/a.py": "", "src/lib/b.py": "",
                     "src/lib/c.py": "", "src/lib/__init__.py": ""})
        assert _readme_unlisted("src/lib", tmp) == ["c"], _readme_unlisted("src/lib", tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    folders = ("src/lib", "src/ops", "src/pages", "src/parse", "src/hearings")
    said = {f: _readme_unlisted(f) for f in folders}
    pages = _source("src/pages/README.md")
    said["src/pages"] += [p.name for p in sorted((_paths.ROOT / "src/pages").glob("*"))
                          if p.suffix in (".js", ".css", ".html") and f"`{p.name}`" not in pages]
    assert not any(said.values()), "a folder's README leaves out modules: " + "; ".join(
        f"{f}: {', '.join(m)}" for f, m in said.items() if m)
    # src/TWINS.md, the register of the rules written in Python and in JavaScript (the same
    # day), names the check that holds each pair: a check renamed or gone leaves a row that
    # sends a reader to nothing, so every suite name it cites is one, and every path a file.
    twins = _source("src/TWINS.md")
    suite = set()
    for f in _suite_files():
        for n in _parsed(f).body:
            if isinstance(n, ast.FunctionDef):
                suite.add(n.name)
            elif isinstance(n, ast.Assign):
                suite |= {t.id for t in n.targets if isinstance(t, ast.Name)}
    cited = set(re.findall(r"`(_[a-z][a-z0-9_]+|_[A-Z][A-Z_]+)`", twins))
    gone = sorted(c for c in cited if c not in suite)
    paths = set(re.findall(r"`((?:src|workers|functions|tests)/[\w./-]+)`", twins))
    lost = sorted(p for p in paths if not (_paths.ROOT / p).exists())
    assert cited and not gone and not lost, (
        f"src/TWINS.md names {gone or 'no'} check that is not in the suite and {lost or 'no'} file "
        "that is not here: put each row right")
    return "ok", (f"{', '.join(folders)}: every module named in its README, and every browser "
                  f"file of src/pages; src/TWINS.md's {len(cited)} suite names and {len(paths)} "
                  "paths are all there")


def _project_modules(root=None):
    """The bare module names of every script and module in the code folders."""
    return {f.stem for f in _paths.code_files("*.py", root=root)}


def _bootstrap_problem(src, project, tree=None):
    """What is wrong with a runnable script's start, or "": it carries
    _paths.BOOTSTRAP word for word, and imports _paths before any module of
    this project, at the top level or inside a statement there. `tree` is
    the run's parse of the same text (_parsed), where the caller has one."""
    text = src.replace("\r\n", "\n")
    if _paths.BOOTSTRAP not in text:
        return "does not carry the bootstrap (_paths.BOOTSTRAP)"
    for node in (tree or ast.parse(text)).body:
        names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
        if "_paths" in names:
            return ""
        for n in ast.walk(node):
            mods = ([a.name for a in n.names] if isinstance(n, ast.Import) else
                    [n.module] if isinstance(n, ast.ImportFrom) and n.module and not n.level
                    else [])
            hit = sorted(m.split(".")[0] for m in mods if m.split(".")[0] in project - {"_paths"})
            if hit:
                return f"imports {hit[0]} before _paths"
    return "never imports _paths"


def _runnable(tree):
    """Whether a parsed module is run as a script: a top-level
    `if __name__ == "__main__":`."""
    return any(isinstance(n, ast.If) and "__name__" in ast.unparse(n.test)
               and "__main__" in ast.unparse(n.test) for n in tree.body)


@check("files", "every runnable script imports _paths, found above its own file, before "
                "any module of this project")
def _bootstrap_first():
    """A script imports its neighbours by bare name. At the root that worked
    because the root was the script's own folder; under src/parse/ the script's
    folder is src/parse/, and `import proceedings` would fail unless something
    had put src/lib/ on the path first. That something is the bootstrap at the
    top of every runnable script (_paths.BOOTSTRAP): it walks up from the
    script's own file to the folder holding _paths.py and imports it, so a
    script one folder deep and one three deep start the same way, from any
    working directory. A script is runnable when it has a __main__ block or a
    runner starts it (watchers/rest.py has no block and the lane runs it).
    The bootstrap is also run, under src/ and at the root of a scratch tree,
    to see every code folder come out on the path once and ahead of the
    standard library, the root included."""
    project = _project_modules()
    good = _paths.BOOTSTRAP
    probes = {
        "a script with no bootstrap": ("import json\nimport narrative\n", "does not carry"),
        "a project module imported first": ("import narrative\n" + good, "imports narrative"),
        "one imported inside a try first": ("try:\n    import child\nexcept Exception:\n"
                                            "    pass\n" + good, "imports child"),
        "the bootstrap, then the rest": ('"""Doc."""\n' + good + "\nimport narrative\n", ""),
    }
    for what, (src, want) in probes.items():
        got = _bootstrap_problem(src, project | {"narrative", "child"})
        assert (want in got if want else got == ""), f"the reader got {what} wrong: {got!r}"
    # What the bootstrap does, run from a script two folders down and one at
    # the root of a tree holding this _paths.py: every code folder on the path
    # once, ahead of the standard library and site-packages. The root is the
    # one to watch: the bootstrap appends it behind site-packages, where an
    # installed package of a root module's name would win, and _paths must
    # bring it forward.
    # Resolved, because _paths resolves every root it is given: GitHub's machine
    # names its temporary folder C:\Users\RUNNER~1\..., which resolves to
    # C:\Users\runneradmin\..., and comparing the one with the other raised a
    # ValueError on the dry run of 7 October 2026 that no laptop could show.
    tmp = Path(tempfile.mkdtemp(prefix="gr-boot-")).resolve()
    try:
        shutil.copy2(_paths.ROOT / "_paths.py", tmp / "_paths.py")
        show = ('import json, os\nprint(json.dumps({"path": sys.path, '
                '"lib": os.path.dirname(os.__file__)}))\n')
        _plant(tmp, {"src/parse/deep.py": '"""Doc."""\n' + good + show,
                     "top.py": '"""Doc."""\n' + good + show,
                     "src/lib/README.md": "", "tests/README.md": ""})

        def norm(p):
            return os.path.normcase(str(Path(p).resolve())) if p else ""
        for script in ("src/parse/deep.py", "top.py"):
            r = _run([sys.executable, "-B", str(tmp / script)], cwd=str(tmp),
                     capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, f"{script} would not start: {(r.stderr or r.stdout)[-300:]}"
            got = json.loads(r.stdout)
            keys = [norm(p) for p in got["path"]]
            lib = keys.index(norm(got["lib"]))
            for d in _paths.code_dirs(tmp):
                n, where = keys.count(norm(d)), d.relative_to(tmp).as_posix()
                where = "the root" if where == "." else where
                assert n == 1 and keys.index(norm(d)) < lib, (
                    f"run as {script}, the bootstrap left {where} on sys.path {n} times"
                    + (f", behind the standard library (at {keys.index(norm(d))}, the "
                       f"library at {lib})" if n and keys.index(norm(d)) > lib else "")
                    + ", where it should be once and ahead of it")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    started = {Path(n).name for names in _runner_names().values() for n, _ in names}
    bad, n = [], 0
    for f in _paths.code_files("*.py"):
        if f.name == "_paths.py":
            continue
        src = f.read_text(encoding="utf-8")
        if not (f.name in started or _runnable(_parsed(f))):
            continue
        n += 1
        why = _bootstrap_problem(src, project, _parsed(f))
        if why:
            bad.append(f"{f.relative_to(_paths.ROOT).as_posix()} {why}")
    assert n >= 145, f"only {n} runnable scripts were read; there were 147 on 6 October"
    assert not bad, ("these scripts would not find their imports once they, or what they "
                     "import, sit under src/: " + "; ".join(bad))
    return "ok", f"{n} runnable scripts start with the bootstrap, before any import of ours"


# THE OTHER TWO RULES FOR A SCRIPT (CONTRIBUTING.md, "Where new code goes").
# The first two, a unique name and the bootstrap, have checks of their own above.
# These hold the last two: a path is found from _paths.ROOT, and a script is
# started through _paths.script. Each was a trap the plan counted -- keys.py's
# secrets.json, repo_facts' sentence on data.html, the laptop's evening probe
# path -- and each comes back without a word in a new or edited file: the
# file works at the root and loses its way the day it moves.
_FROM_OWN_FILE = ("parent", "parents", "with_name", "with_stem", "with_suffix")


def _launch_target(lst):
    """The element of a launch list that names the script -- [sys.executable
    (or "python3"), its flags, the script, ...] -- or None for any other list,
    and for a -m or -c run."""
    if not lst.elts:
        return None
    head = lst.elts[0]
    if ast.unparse(head) != "sys.executable" and not (
            isinstance(head, ast.Constant) and head.value in ("python", "python3", "py")):
        return None
    for el in lst.elts[1:]:
        if isinstance(el, ast.Constant) and isinstance(el.value, str) and el.value.startswith("-"):
            if el.value in ("-m", "-c"):
                return None
            continue
        return None if isinstance(el, ast.Starred) else el
    return None


def _hand_made(node):
    """Whether an expression makes a script's path by hand: it names a .py
    file or joins a path (with / or os.path.join), and goes through neither
    _paths.script, find or locate nor the file's own __file__."""
    said = ast.unparse(node)
    if "__file__" in said or re.search(r"_paths\.(?:script|find|locate)\(", said):
        return False
    return any((isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.endswith(".py"))
               or (isinstance(c, ast.BinOp) and isinstance(c.op, ast.Div))
               or (isinstance(c, ast.Call) and ast.unparse(c.func).endswith("path.join"))
               for c in ast.walk(node))


def _without_bootstrap(f, text):
    """What ast.parse gives of `text` (the file `f`, as read) with the
    bootstrap blanked out, from the run's one parse of the file (_parsed)
    rather than a second: that parse itself where the bootstrap is not in
    it, and otherwise a module of its statements less the bootstrap's four.
    None where those would not be the same tree -- the bootstrap there more
    than once, not at the start of a line, or not as whole statements of the
    module's own -- and the caller then blanks it and parses, as it always
    did. (9 October 2026: this file is nearly eighty thousand lines, and a
    parse of it was one of four a run made.)"""
    n = text.count(_paths.BOOTSTRAP)
    if n == 0:
        return _parsed(f)
    at = text.find(_paths.BOOTSTRAP)
    if n != 1 or (at and text[at - 1] != "\n"):
        return None
    first = text.count("\n", 0, at) + 1
    last = first + _paths.BOOTSTRAP.count("\n") - 1
    tree = _parsed(f)
    inside = {id(s) for s in tree.body if first <= s.lineno <= last}
    if len(inside) != 4 or any(s.lineno < first <= s.end_lineno or
                               (id(s) in inside and s.end_lineno > last) for s in tree.body):
        return None
    return ast.Module(body=[s for s in tree.body if id(s) not in inside], type_ignores=[])


def _root_and_launch_problems(root=None):
    """([sentence], files read): every place a code file finds a folder from
    a file's own path -- `.parent`, `.parents` or a sibling (`with_name`) of
    something built from __file__, or `os.path.dirname` of it -- outside
    _paths.py, which is the one place that may; and every launch whose script
    is a name relative to the working folder or a path made by hand rather
    than by _paths.script, _paths.find or _paths.locate, read in the launch
    itself or, for a script held in a variable, in what the file assigns to
    it. A script launching its own __file__ is itself wherever it sits, and
    passes; a variable filled some other way (an argument, a loop) cannot be
    read here, and passes too. preflight is held to the first rule and not
    the second: the scripts it starts by a bare name are copies it wrote into
    a fixture folder and runs there, and a repository script it started by a
    stale path would fail preflight itself, at once."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    found, files = {}, _paths.code_files("*.py", root=base)
    blank = "\n" * _paths.BOOTSTRAP.count("\n")
    for f in files:
        if f.name == "_paths.py":
            continue
        rel = f.relative_to(base).as_posix()
        text = f.read_text(encoding="utf-8").replace("\r\n", "\n")
        tree = _without_bootstrap(f, text) or ast.parse(text.replace(_paths.BOOTSTRAP, blank))
        given = {}
        for a in ast.walk(tree):
            if isinstance(a, (ast.Assign, ast.AnnAssign)) and a.value is not None:
                for t in (a.targets if isinstance(a, ast.Assign) else [a.target]):
                    if isinstance(t, ast.Name):
                        given.setdefault(t.id, []).append(a.value)
        for n in ast.walk(tree):
            if isinstance(n, ast.Attribute) and n.attr in _FROM_OWN_FILE \
                    and "__file__" in ast.unparse(n.value):
                found.setdefault((rel, n.lineno), (
                    f"{rel}:{n.lineno} finds a folder from __file__ ({ast.unparse(n)}), the "
                    "root only while the file sits there: use _paths.ROOT"))
            elif isinstance(n, ast.Call) and ast.unparse(n.func).split(".")[-1] in ("dirname", "split") \
                    and any("__file__" in ast.unparse(a) for a in n.args):
                found.setdefault((rel, n.lineno), (
                    f"{rel}:{n.lineno} finds a folder from __file__ ({ast.unparse(n)}), the "
                    "root only while the file sits there: use _paths.ROOT"))
            elif not _in_suite(f) and isinstance(n, ast.List):
                target = _launch_target(n)
                if target is None:
                    continue
                said = ast.unparse(target)
                if "__file__" in said or re.search(r"_paths\.(?:script|find|locate)\(", said):
                    continue
                made = [said] if _hand_made(target) else [
                    f"{v.id} = {ast.unparse(x)}" for v in ast.walk(target)
                    if isinstance(v, ast.Name) for x in given.get(v.id, ()) if _hand_made(x)]
                if made:
                    how = f" ({made[0]})" if made[0] != said else ""
                    found.setdefault((rel, n.lineno), (
                        f"{rel}:{n.lineno} starts {said} by a path of its own making{how}, "
                        "which finds it only while it sits there: start it through "
                        "_paths.script"))
    return [found[k] for k in sorted(found)], len(files)


@check("files", "a script finds the repository through _paths.ROOT and starts another "
                "through _paths.script, never from its own file's folder")
def _root_and_launch_rules():
    """CONTRIBUTING.md gives a new script four rules and says preflight holds
    them. The name and bootstrap checks hold the first two; this holds the
    third and the fourth, read from what each file does so that they hold
    wherever it sits. Path(__file__).parent was the root while every script
    sat there, and is src/parse/ once one moves: keys.py would have looked
    for secrets.json there, and build_exports would have counted no checks
    for data.html. A launch of "narrative.py", or of HERE / "narrative.py",
    finds the file only while it sits beside the working folder or HERE."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-rules-"))
    try:
        launch = "import subprocess, sys\nrun = subprocess.run\n"
        _plant(tmp, {
            "_paths.py": "HERE = Path(__file__).resolve().parent\n",
            "src/parse/hand.py": (launch + "HERE = Path(__file__).resolve().parent\n"
                                  'run([sys.executable, str(HERE / "other.py")])\n'),
            "src/parse/bare.py": launch + 'run([sys.executable, "-u", "other.py", "--x"])\n',
            "src/parse/up.py": "import os\nD = os.path.dirname(os.path.abspath(__file__))\n",
            "src/lib/beside.py": 'K = Path(__file__).with_name("secrets.json")\n',
            "src/pages/py.py": launch + 'run(["python3", "other.py"])\n',
            "src/parse/held.py": launch + 'tool = Path("other.py")\nrun([sys.executable, str(tool)])\n',
            "src/parse/joined.py": (launch + "HERE = _paths.ROOT\n"
                                    "run([sys.executable, str(HERE / argv[0]), *argv[1:]])\n"),
            "src/parse/fine.py": (_paths.BOOTSTRAP + launch +
                                  'run([sys.executable, _paths.script("other.py"), "--x"])\n'
                                  'run([sys.executable, __file__, "--child"])\n'
                                  'run([sys.executable, "-m", "yt_dlp", "x.py"])\n'
                                  'run([sys.executable, "-c", "print(1)"])\n'
                                  "script = _paths.script(argv[0])\n"
                                  "run([sys.executable, script])\n"
                                  "run([sys.executable] + args)\n"
                                  "for g in given:\n    run([sys.executable, str(g)])\n"
                                  'SRC = Path(__file__).resolve().read_text()\n'
                                  'K = _paths.ROOT / "secrets.json"\n'),
            "preflight.py": launch + 'run([sys.executable, "copy.py"], cwd=tmp)\n'})
        got, _ = _root_and_launch_problems(tmp)
        want = ["src/parse/hand.py:3 finds", "src/parse/hand.py:4 starts", "src/parse/bare.py:3",
                "src/parse/up.py:2", "src/lib/beside.py:1", "src/pages/py.py:3",
                "src/parse/held.py:4", "src/parse/joined.py:4"]
        assert len(got) == len(want) and all(any(g.startswith(w) for g in got) for w in want), \
            f"the reader of paths and launches found {got} in a tree made to break eight ways"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad, n = _root_and_launch_problems()
    assert n >= 160, f"only {n} scripts were read; there were 165 on 6 October"
    assert not bad, ("these find the repository or start a script from where the file sits "
                     "today, which stops being true when it moves: " + "; ".join(bad))
    return "ok", (f"{n} scripts read: none finds a folder from its own file but _paths.py, and "
                  "every launch whose script can be read goes through _paths")


# A `python3 -c` program, written in a docstring for a person to type or in a
# list for a check to run, starts with only the working folder on its path:
# the root while every module sits there, and none of src/ once they move.
_DASH_C = re.compile(r"""-c\s+(["'])(.+?)\1""")


def _dash_c_problem(code, project):
    """What is wrong with a -c program, or "": it imports _paths before any
    module of this project."""
    for stmt in re.split(r"[;\n]", code):
        stmt = stmt.strip()
        if stmt.startswith("import "):
            mods = [p.split()[0].split(".")[0] for p in stmt[7:].split(",") if p.strip()]
        elif stmt.startswith("from ") and " import " in stmt:
            mods = [stmt[5:].split()[0].split(".")[0]]
        else:
            continue
        for m in mods:
            if m == "_paths":
                return ""
            if m in project:
                return f"imports {m} before _paths"
    return ""


def _dash_c_programs(f):
    """(line, program) for every -c program a file writes: after a -c and a
    space in prose, a docstring or a shell line, and, in Python, as the string
    that follows a "-c" in a list (an f-string's fields read as X)."""
    text = f.read_text(encoding="utf-8", errors="replace")
    out = [(text.count("\n", 0, m.start()) + 1, m.group(2)) for m in _DASH_C.finditer(text)]
    if f.suffix == ".py":
        for n in ast.walk(_parsed(f)):
            if not isinstance(n, ast.List):
                continue
            for a, b in zip(n.elts, n.elts[1:]):
                if not (isinstance(a, ast.Constant) and a.value == "-c"):
                    continue
                if isinstance(b, ast.Constant) and isinstance(b.value, str):
                    out.append((b.lineno, b.value))
                elif isinstance(b, ast.JoinedStr):
                    out.append((b.lineno, "".join(v.value if isinstance(v, ast.Constant) else "X"
                                                  for v in b.values)))
    return out


def _dash_c_problems(root=None):
    """[sentence] for each -c program in the code, its READMEs and docs, the
    workflows and the .bat files that imports a module of ours before _paths."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    project = _project_modules(base)
    files = (_paths.code_files("*.py", root=base) + _paths.code_files("*.md", root=base)
             + sorted((base / ".github" / "workflows").glob("*.y*ml")) + sorted(base.glob("*.bat")))
    bad = []
    for f in files:
        for line, code in _dash_c_programs(f):
            why = _dash_c_problem(code, project)
            if why:
                bad.append(f"{f.relative_to(base).as_posix()}:{line} runs a -c program that {why}")
    return bad, len(files)


# A command that names a script without its folder -- `python3 x.py`, or in a
# document a backticked `x.py --flag` -- is typed from the root, where the
# script stops being once it moves under src/. Bare names, so that a path
# (src/parse/x.py, watchers\gc_lane.py) is never read as one.
_BARE_PY3 = re.compile(r"\bpython3?(?:\.exe)?[ \t]+(?:-[A-Za-z]+[ \t]+)*([A-Za-z0-9_]+\.py)\b")
_BARE_TICK = re.compile(r"`(?:python3?[ \t]+)?([A-Za-z0-9_]+\.py)[ \t]+-[^`\n]*`")
# The other tracked kinds a person reads a command off: a fixture's _about, a
# page's or a script's comment, a config file's note. Stage 3 left
# tests/search_cases.json telling the reader to run `python3
# build_search_index.py --fixture`, which a reader of .py, .md, .bat and the
# workflows alone did not see. Not the data tables (.txt, .csv, .pdf), which
# are the General Court's or a build's; not the bench's append-only .jsonl;
# and not the lane's queue, whose lines name each script bare on purpose and
# whose text never changes.
_BARE_ALSO = (".json", ".js", ".html", ".css", ".toml", ".sql", ".webmanifest")


def _bare_command_problems(root=None):
    """([sentence], files read) for each command the repository writes that
    names a script under src/ by its bare name: `python3 x.py` in any tracked
    script, document, workflow, .bat file or file of _BARE_ALSO's kinds, and
    in a document a backticked `x.py --flag`, where x.py is no longer at the
    root. None without git.

    Tracked files only: the laptop's root also holds
    STATE.md, CLAUDE.local.md and other files git does not carry, and a
    command in one of those is not the repository's. CLAUDE.md is the
    person's file and is left out too: its lines are drafted for the person
    at each stage of the folder move rather than edited. A script's own
    docstring may name another by its bare name in backticks as a reference
    (`fetch_sponsors_by_member.py --members` writes it); only a python3 line
    there is a command."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    try:
        r = _run(["git", "-C", str(base), "ls-files", "-z"], capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    rels = sorted(p for p in (r.stdout or "").split("\0")
                  if p and p != "CLAUDE.md"
                  and (p.endswith((".py", ".md", ".bat") + _BARE_ALSO)
                       or (p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml")))))
    bad, seen, n = [], set(), 0
    for rel in rels:
        f = base / rel
        if not f.is_file():
            continue
        n += 1
        text = f.read_text(encoding="utf-8", errors="replace")
        for rx in (_BARE_PY3, _BARE_TICK) if rel.endswith(".md") else (_BARE_PY3,):
            for m in rx.finditer(text):
                name = m.group(1)
                try:
                    hit = _paths.find(name, root=base)
                except LookupError:
                    continue            # two files of one name: _code_names_unique says so
                line = text.count("\n", 0, m.start()) + 1
                if hit is None or hit.parent == base or (rel, line, name) in seen:
                    continue
                seen.add((rel, line, name))
                where = hit.relative_to(base).as_posix()
                bad.append(f"{rel}:{line} gives `{m.group(0).strip('`')[:60]}`, and {name} is "
                           f"{where} now: python3 {where}")
    return bad, n


@check("files", "a command the code or the docs write still runs from the root once a script "
                "moves: a python -c program imports _paths before any module of this "
                "project, and a script named without its folder is at the root")
def _dash_c_imports_paths():
    """A bare -c puts only the working folder on the path. Run from the root
    that finds a root module today and nothing once the module sits under
    src/: freeze_term's docstring gave the person a -c program importing
    snapshot_gencourt to run at the 2 December switch, and stage 4 moves
    snapshot_gencourt into src/fetch/gc_web/ before then. Importing _paths
    first puts every code folder on the path, before and after the move.

    The same move breaks a command that names a script without its folder.
    Stage 2 of the folder move left ARCHITECTURE.md giving
    `calendar_meetings.py --check` after the script had gone to
    src/hearings/, where typed from the root it answers "can't open file";
    the stages' own rule rewrote every `python3 <name>` and held it by grep,
    which read no backticked one and holds nothing for the stages after. So
    every tracked command naming a script that is no longer at the root
    fails here with the path to give (_bare_command_problems). It is part of
    this check rather than one of its own so that the folder move leaves the
    site's count of checks as it was."""
    dash = "-c"
    tmp = Path(tempfile.mkdtemp(prefix="gr-dashc-"))
    try:
        _plant(tmp, {
            "_paths.py": "", "other.py": "",
            "README.md": (f'python3 {dash} "import other; other.go()"\n'
                          f'python3 {dash} "import _paths, other as O; O.go()"\n'
                          f"python3 {dash} 'import json; print(1)'\n"),
            "src/parse/runs.py": (f'R = [sys.executable, "{dash}", "from other import go; go()"]\n'
                                  f'S = [sys.executable, "{dash}", f"import sys; '
                                  f'sys.path.insert(0, {{h!r}}); import _paths; import other"]\n'
                                  f'G = ["git", "{dash}", "user.name=x"]\n'),
            "src/parse/README.md": f'Run `python3 {dash} "import json, other"`.\n',
            ".github/workflows/w.yml": f'run: python {dash} "import other"\n',
            "publish.bat": f'python3 {dash} "import _paths; import other"\n'})
        got, _ = _dash_c_problems(tmp)
        want = ["README.md:1 runs", "src/parse/runs.py:1 runs", "src/parse/README.md:1 runs",
                ".github/workflows/w.yml:1 runs"]
        assert len(got) == len(want) and all(any(g.startswith(w) for g in got) for w in want), \
            f"the reader of -c programs found {got} in a tree made to hold four"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad, n = _dash_c_problems()
    assert n >= 160, f"only {n} files were read for -c programs"
    assert not bad, ("these -c programs import a module of ours before _paths, so they find "
                     "it only while it sits at the root; put `import _paths` first: "
                     + "; ".join(bad))
    said = f"{n} files read; every -c program that imports a module of ours imports _paths first"

    # A script named without its folder, in a tree git tracks: six commands
    # that would answer "can't open file" from the root, and seven that would
    # not or are not read: the repository's, a data table's, the lane's.
    mover = "planted_mover.py"
    tmp = Path(tempfile.mkdtemp(prefix="gr-bare-"))
    try:
        if _run(["git", "init", "-q", str(tmp)], capture_output=True, timeout=60).returncode != 0:
            said += "; git is not here to prove the reader of bare script names on"
        else:
            tree = {
                "_paths.py": "", "planted_still.py": "", f"src/parse/{mover}": "",
                "README.md": (f"Run `{mover} --check` to see.\n"
                              f"python3 {mover} --all\n"
                              f"python3 src/parse/{mover} --all\n"
                              "`planted_still.py --y`, and python3 planted_still.py\n"
                              f"`{mover}` alone is a name, and python3 {dash} \"print(1)\" none.\n"),
                "src/parse/hint.py": (f'print("then: python3 {mover} --all")\n'
                                      f'"""`{mover} --doc` is a reference here."""\n'),
                "publish.bat": f"python3 -u {mover} --site site\n",
                ".github/workflows/w.yml": f"run: python {mover}\n",
                "tests/cases.json": f'{{"_about": ["python3 {mover} --fixture tests/cases.json"]}}\n',
                "Docket.txt": f"python3 {mover}\n",
                "watchers/gc_lane.queue": f"# python3 {mover} --all\n{mover} --all\n",
                "CLAUDE.md": f"python3 {mover}\n"}
            _plant(tmp, dict(tree, **{"notes.md": f"python3 {mover}\n"}))
            _run(["git", "-C", str(tmp), "add", "--", *tree], capture_output=True, timeout=60)
            got = _bare_command_problems(tmp)
            want = ["README.md:1 gives", "README.md:2 gives", "src/parse/hint.py:1 gives",
                    "publish.bat:1 gives", ".github/workflows/w.yml:1 gives",
                    "tests/cases.json:1 gives"]
            assert got is not None and len(got[0]) == len(want) and all(
                any(g.startswith(w) for g in got[0]) for w in want), \
                f"the reader of bare script names found {got} in a tree made to hold six"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    got = _bare_command_problems()
    if got is None:
        return "ok", said + "; not a git checkout, so no command was read for a bare script name"
    bad, m = got
    assert m >= 220, (f"only {m} tracked files were read for commands; 227 were on 7 October, "
                      "the JSON, JavaScript, HTML and config files among them")
    assert not bad, ("these commands name a script by its bare name, and it is no longer at "
                     "the root, so typed there they answer \"can't open file\"; give the "
                     "path: " + "; ".join(bad))
    return "ok", (said + f"; {m} tracked files read, and every command that names a script "
                  "without its folder finds it at the root")


# THE NETWORK LINES, BY FOLDER (src/fetch/README.md). Read from what a file
# does, so that they hold wherever it sits. The root is allowed all of them:
# it holds the entry points that ask (nightly, netcheck); the refusal guard
# holds every script there to refusal.check() all the same. src/ops/ asks the
# services it operates -- R2 through boto3 and the reports database through
# wrangler, which these patterns do not read -- and its livestreams.py is the
# one script outside src/fetch/youtube/ that asks YouTube, as it was while it
# sat at the root.
_GC_HOST = re.compile(r"""["']https?://gc\.nh\.gov""")
_SQL = re.compile(r"^\s*(?:import probe_db\b|from probe_db import)", re.M)
_YOUTUBE = re.compile(r"yt_dlp|googleapis\.com/youtube|youtube/v3")
_ASKS = re.compile(r"urlopen|urlretrieve|urllib\.request\.Request|requests\.(?:get|post)"
                   r"|http\.client")
_URL = re.compile(r"""["'](https?://[^/"'\s]+)""")


# The night's livestream step: the one script outside src/fetch/youtube/ that
# asks YouTube (src/fetch/youtube/README.md).
_LIVESTREAMS = "src/ops/livestreams.py"


def _calls_refusal_check(tree):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "check" and isinstance(n.func.value, ast.Name)
               and n.func.value.id == "refusal" for n in ast.walk(tree))


def _boundary_problems(root=None, dirs=_paths.CODE_DIRS):
    """[sentence] for each file under src/ (and watchers/, tests/) on the
    wrong side of a network line:
      - every file in src/fetch/gc_web/ calls refusal.check(), and no other
        file under src/ does;
      - only src/fetch/gc_db/ (and, at the root, nightly and preflight; and
        tests/rehearse_turn.py) open the General Court's SQL host, through
        probe_db;
      - only src/fetch/youtube/ (and src/ops/livestreams.py, the night's
        livestream step) use yt-dlp or the YouTube API;
      - src/checks asks only graniterecord.org, and every other folder under
        src/ that is not in src/fetch/ asks nobody.
    The last is by default, not by a list of folders, so that a folder added
    to _paths.SRC_DIRS is held to it the day it is listed: a list here would
    have let a request from the new folder through until somebody remembered
    to add it."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    bad = []
    for f in _paths.code_files("*.py", root=base, dirs=dirs):
        rel = f.relative_to(base).as_posix()
        folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
        if not folder or _in_suite(f):
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        tree = _parsed(f)
        checks = _calls_refusal_check(tree)
        if folder == "src/fetch/gc_web" and not checks:
            bad.append(f"{rel} is in src/fetch/gc_web/ and never calls refusal.check()")
        if folder.startswith("src/") and folder != "src/fetch/gc_web" and checks:
            bad.append(f"{rel} calls refusal.check(), so it asks gc.nh.gov: it belongs in "
                       "src/fetch/gc_web/")
        if folder.startswith("src/") and folder != "src/fetch/gc_web" and _GC_HOST.search(src) \
                and _ASKS.search(src):
            bad.append(f"{rel} asks a gc.nh.gov address: it belongs in src/fetch/gc_web/")
        if (_SQL.search(src) or f.name == "probe_db.py") and folder != "src/fetch/gc_db" \
                and rel != "tests/rehearse_turn.py":
            bad.append(f"{rel} opens the General Court's SQL host: it belongs in src/fetch/gc_db/")
        if _YOUTUBE.search(src) and folder != "src/fetch/youtube" and rel != _LIVESTREAMS:
            bad.append(f"{rel} uses yt-dlp or the YouTube API: it belongs in src/fetch/youtube/")
        if folder.startswith("src/") and not folder.startswith("src/fetch/") \
                and folder != "src/checks" and rel != _LIVESTREAMS and _ASKS.search(src):
            bad.append(f"{rel} makes a request, and {folder}/ asks nobody")
        if folder == "src/checks" and _ASKS.search(src):
            hosts = {u for u in _URL.findall(src)
                     if not re.match(r"https?://(?:www\.)?graniterecord\.org$|https?://"
                                     r"(?:127\.0\.0\.1|localhost)(?::\d+)?$", u)}
            if hosts:
                bad.append(f"{rel} asks {', '.join(sorted(hosts))}, and src/checks/ asks only "
                           "graniterecord.org")
    return bad


@check("files", "each network has its folder: gc.nh.gov's fetchers in src/fetch/gc_web/ and "
                "nowhere else, the SQL host's in gc_db/, YouTube's in youtube/, and every "
                "folder under src/ outside fetch/ and checks/ asks nobody")
def _network_boundaries():
    """The folders under src/fetch/ are by whose server a script asks, because
    that decides what can go wrong: gc.nh.gov's web server has blocked this
    address twice, its SQL host is somebody else's server too, and YouTube
    refuses GitHub's machines and has refused the laptop. A fetcher filed in
    the wrong folder is a request nobody expects from it. So each line is
    read from what a file does -- refusal.check(), probe_db, yt-dlp, a
    request -- and held against where it sits, which is why it needs no edit
    as files move. Asking nobody is the default for a folder under src/
    outside fetch/, so a folder listed later is held to it from the start."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-lines-"))
    try:
        ask = "import urllib.request\nurllib.request.urlopen(U)\n"
        _plant(tmp, {
            "_paths.py": "",
            "src/fetch/gc_web/fine.py": "import refusal\nrefusal.check('x')\n",
            "src/fetch/gc_web/unchecked.py": 'U = "https://gc.nh.gov/x"\n' + ask,
            "src/parse/checked.py": "import refusal\nrefusal.check('x')\n",
            "src/fetch/other/sql.py": "import probe_db\n",
            "src/fetch/gc_db/fine_sql.py": "import probe_db\n",
            "src/hearings/yt.py": "import yt_dlp\n",
            "src/pages/asks.py": 'U = "https://example.org"\n' + ask,
            "src/checks/live.py": 'U = "https://graniterecord.org"\n' + ask,
            "src/checks/away.py": 'U = "https://example.org"\n' + ask,
            "src/fetch/other/sos.py": 'U = "https://app.sos.nh.gov"\n' + ask,
            "src/later/new.py": 'U = "https://app.sos.nh.gov"\n' + ask,
            "src/ops/livestreams.py": 'import yt_dlp\nU = "https://www.googleapis.com/youtube/v3"\n' + ask,
            "src/ops/elsewhere.py": "import yt_dlp\n",
            "nightly.py": "import probe_db\nimport yt_dlp\n"})
        # src/later stands for a folder listed after this check was written.
        got = _boundary_problems(tmp, dirs=_paths.CODE_DIRS + ("src/later",))
        want = ["unchecked.py is in src/fetch/gc_web/ and never calls",
                "checked.py calls refusal.check()", "sql.py opens", "yt.py uses yt-dlp",
                "asks.py makes a request", "away.py asks https://example.org",
                "new.py makes a request, and src/later/ asks nobody",
                "elsewhere.py uses yt-dlp"]
        assert len(got) == len(want) and all(any(w in g for g in got) for w in want), \
            f"the reader of the network lines found {got} in a tree made to cross eight"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = _boundary_problems()
    assert not bad, "; ".join(bad)
    placed = sum(1 for f in _paths.code_files("*.py", dirs=_paths.SRC_DIRS))
    return "ok", (f"{placed} scripts under src/, each on its side of the network lines; the "
                  "root's are held by the refusal guard")


def _git_hidden(root=None):
    """(tracked code paths a .gitignore line matches, files under src/ git
    does not track), or None without git. Code is anything under src/,
    watchers/, tests/, functions/ or workers/, and every .py, .js, .css,
    .html, .bat, .toml and .yml file. __pycache__ is not code."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    try:
        caught = _run(["git", "-C", str(base), "ls-files", "-ci", "--exclude-standard", "-z"],
                      capture_output=True, timeout=60)
        loose = _run(["git", "-C", str(base), "ls-files", "-o", "-z", "--", "src"],
                     capture_output=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if caught.returncode != 0 or loose.returncode != 0:
        return None
    code = re.compile(r"^(?:src|watchers|tests|functions|workers)/|"
                      r"\.(?:py|js|mjs|css|html|bat|cmd|ps1|toml|ya?ml)$")
    hidden = [p for p in caught.stdout.split("\0") if p and code.search(p)]
    untracked = [p for p in loose.stdout.split("\0")
                 if p and "__pycache__/" not in p and not p.endswith(".pyc")]
    return hidden, untracked


@check("files", "no Python file holds an escape a future Python will refuse")
def _no_invalid_escapes():
    """A backslash before a letter Python gives no meaning, inside a string that
    is not raw, is kept as it stands today and is a SyntaxWarning that a later
    Python turns into an error. build_full_sessions.py carried two, in the
    JavaScript its SCRIPT writes (/[^\\w-]/ and /^#day-(\\d{4}...)$/), and
    every build printed the warning to a log nobody reads (16 October 2026).
    Doubled, the string is the same; compiled here, every code file is held to
    it, so the next one fails here rather than on the night Python moves."""
    import warnings
    bad = []
    for f in _paths.code_files():
        # Read as compile() was given it, so a file that is not UTF-8 still
        # stops the check; the tree is the run's one parse of it (_parsed),
        # with the warnings that parse gave, and the compiler's come from
        # compiling that tree: the two together are what compiling the text
        # gives.
        f.read_text(encoding="utf-8")
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            try:
                tree, said = _parsed_warned(f)
                compile(tree, str(f), "exec")
            except SyntaxError as e:
                bad.append(f"{f.name}:{e.lineno}: {e.msg}")
                continue
        said = list(said)
        said += [x for x in ((w.lineno, str(w.message)) for w in seen
                             if issubclass(w.category, SyntaxWarning)) if x not in said]
        bad += [f"{f.name}:{line}: {msg}" for line, msg in said]
    assert not bad, "; ".join(bad[:6])
    return "ok", "every code file compiles without a SyntaxWarning"


@check("files", "git sees all the code: no tracked code path is caught by .gitignore, and "
                "nothing under src/ is untracked")
def _code_not_ignored():
    """`.gitignore` line 19 is `site/`, which matches a folder named site at
    any depth: a page builder under src/site/ would have been left out of
    every commit without a word, which is why the pages' folder is
    src/pages/. And `_*.py`, there for patch scripts, caught _paths.py itself
    the day it was written. So a code path git ignores fails here, and so
    does any file under src/ git does not track -- it would be on the laptop
    and nowhere else."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-ignored-"))
    try:
        if _run(["git", "init", "-q", str(tmp)], capture_output=True, timeout=60).returncode != 0:
            return "skip", "git is not here to make a repository with"
        _plant(tmp, {".gitignore": "site/\n_*.py\n", "src/site/page.py": "",
                     "src/pages/ok.py": "", "src/pages/new.py": "", "_paths.py": ""})
        g = ["git", "-C", str(tmp), "-c", "user.name=preflight",
             "-c", "user.email=preflight@example.invalid"]
        _run(g + ["add", "-f", "src/site/page.py", "src/pages/ok.py", "_paths.py"],
             capture_output=True, timeout=60)
        got = _git_hidden(tmp)
        assert got == (["_paths.py", "src/site/page.py"], ["src/pages/new.py"]), \
            f"the reader of what git does not see found {got}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    got = _git_hidden()
    if got is None:
        return "skip", "not a git repository"
    hidden, untracked = got
    assert not hidden, ("these tracked code files match a .gitignore line, so a copy of "
                        "them made new would not be committed: " + ", ".join(hidden))
    assert not untracked, ("these files under src/ are not in git, so the night and every "
                           "clone run without them: " + ", ".join(untracked))
    return "ok", "every tracked code path is outside .gitignore, and src/ holds nothing untracked"


@check("files", "the kit carries no pickle: the build's cache of the sitting days stays on the "
       "machine that wrote it")
def _kit_carries_no_pickle():
    """session_days keeps a pickle in .build_cache (_session_days_cache).
    Unpickling runs code, so a pickle must never come back from the bucket:
    no path or glob of cloud_kit.json may take one (the manager, 29 October
    2026)."""
    import fnmatch
    kit = json.loads(_source("cloud_kit.json"))
    probe = [".build_cache/session_days.pkl.gz", ".build_cache/x.pkl", "x.pickle"]
    pats = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("globs", "paths") and isinstance(v, list):
                    pats.extend(x for x in v if isinstance(x, str))
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    # What the bucket is sent: the kit, the state, the logs and a dry run's.
    # The laptop's backup sends everything git does not track except what it
    # leaves out, so there a pickle must be left out.
    for part in ("kit", "state", "logs", "dry_run"):
        walk(kit.get(part))
    takes = lambda g, p: fnmatch.fnmatch(p, g.replace("**/", "*").replace("**", "*"))
    bad = [f"{g} takes {p}" for g in pats for p in probe if takes(g, p)]
    left = [g for e in (kit.get("backup") or {}).get("leave_out", [])
            for g in e.get("globs", [])]
    bad += [f"the backup takes {p}" for p in probe[:2] if not any(takes(g, p) for g in left)]
    assert pats and not bad, "the kit would carry a pickle: " + "; ".join(bad or ["no globs read"])
    return "ok", (f"none of the {len(pats)} paths and globs sent takes a pickle, and the "
                  "backup leaves .build_cache out")


@check("pipeline", "inventory no longer offers a live file for deletion",
       needs=("inventory",))
def _stale(inventory):
    assert "bill_titles.json" not in inventory.STALE, \
        "build_data.py still reads bill_titles.json"
    return "ok", f"STALE lists {len(inventory.STALE)}, none of them read"


@check("files", "inventory --bump raises a file's stamp, keeps the date and the line endings, "
                "--bump-changed bumps a file once, and the registry follows the files",
       needs=("inventory",))
def _inventory_bump(inventory):
    """The two edits every change to a stamped file needs, made by one command
    (src/ops/inventory.py --bump, 23 October 2026). In a scratch git repository:
    a CRLF file is bumped with its endings kept; the date stays; the registry,
    read off the files, moves with it (versions.json is no longer edited, 11
    November 2026); and --bump-changed, run twice on the same change, bumps
    once."""
    import subprocess
    d = Path(tempfile.mkdtemp())
    try:
        def git(*a):
            subprocess.run(["git", "-C", str(d), *a], check=True, capture_output=True)
        git("init", "-q")
        (d / "a.py").write_bytes(b"#!/usr/bin/env python3\r\n# GRANITE_VERSION: 2026-01-02.3\r\nx = 1\r\n")
        git("add", "-A")
        git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "t")
        (d / "a.py").write_bytes((d / "a.py").read_bytes() + b"y = 2\r\n")
        todo, _bare = inventory.changed_since(d, "HEAD")
        assert todo == ["a.py"], todo
        inventory.bump(todo, d)
        raw = (d / "a.py").read_bytes()
        assert b"GRANITE_VERSION: 2026-01-02.4\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""), raw
        assert inventory.registry(d) == {"a.py": "2026-01-02.4"}, inventory.registry(d)
        assert inventory.changed_since(d, "HEAD")[0] == [], "a bumped file was offered again"
        # A stamp taken down is seen against the base; a raised one is not.
        assert inventory.backwards(d, "HEAD") == [], "a raised stamp was called backwards"
        (d / "a.py").write_bytes((d / "a.py").read_bytes().replace(b".4", b".2"))
        assert inventory.backwards(d, "HEAD") == ["a.py"], "a stamp gone backwards was missed"
        inventory.bump(["a.py"], d)
        inventory.bump(["a.py"], d)
        # A file new since the base keeps its first stamp, however often it runs.
        (d / "b.py").write_bytes(b"#!/usr/bin/env python3\n# GRANITE_VERSION: 2026-10-23.1\n")
        assert inventory.changed_since(d, "HEAD")[0] == [], "a new file's first stamp was bumped"
        # A file outside the code folders is keyed by its path; versions.json is
        # the registry written out, and what it holds is what the files say.
        (d / "docs").mkdir()
        (d / "docs" / "t.js").write_bytes(b"// GRANITE_VERSION: 2026-02-03.5\n")
        inventory.bump(["docs/t.js"], d)
        want = {"a.py": "2026-01-02.4", "b.py": "2026-10-23.1", "docs/t.js": "2026-02-03.6"}
        got = inventory.write_registry(d)
        assert got == want and json.loads((d / "versions.json").read_text())["files"] == want, got
        return "ok", ("2026-01-02.3 -> .4 in the file alone, CRLF kept, once only; a new file keeps "
                      "its first stamp; a stamp gone backwards is seen; the registry and the "
                      "versions.json written from it follow the files")
    finally:
        shutil.rmtree(d, ignore_errors=True)


@check("files", "a check marked as expected to fail is reported as one, and once it passes it "
                "fails and says to take the mark off")
def _expected_failures_settle():
    """check(expect_fail=) and _settle(): a check written ahead of its change
    is reported honestly -- run, its findings printed, counted apart from
    the passes, the failures and the skips -- and cannot outlive the change,
    because the run in which it passes is a failure that says so. A crash
    stays an ERROR: it has not found the failure it expects."""
    assert _settle("FAIL", "x", None) == ("FAIL", "x") and _settle("ok", "y", None) == ("ok", "y")
    st, msg = _settle("FAIL", "found it", "the change lands")
    assert st == "xfail" and "until the change lands" in msg and "found it" in msg, (st, msg)
    st, msg = _settle("ok", "holds", "the change lands")
    assert st == "FAIL" and "take the expect_fail mark off" in msg and "holds" in msg, (st, msg)
    assert _settle("ERROR", "KeyError: x", "it lands") == ("ERROR", "KeyError: x")
    assert _settle("skip", "not here", "it lands") == ("skip", "not here")
    marked = [c for c in CHECKS if c.get("expect_fail")]
    return "ok", (f"{len(marked)} checks marked as expected to fail"
                  + (": " + "; ".join(f"{c['group']}/{c['name'][:50]}..." for c in marked)
                     if marked else ""))


@check("files", "every check answers (status, words) or raises: a bare None or a status nobody "
                "reads is an ERROR that says so, and \"fail\" is read as FAIL")
def _checks_answer():
    """_answer(), which main() and _check_outcome read every check's answer through. A check
    that answered None when it passed ran clean on its own, where the runner called nothing a
    pass, and stopped the night of 13 November 2026 at its first gate with "cannot unpack
    non-iterable NoneType object"; three others answered "fail", which main() met only at the
    line that prints the mark, as a KeyError that would have ended the whole run."""
    assert _answer(("ok", "m")) == ("ok", "m") and _answer(["skip", "s"]) == ("skip", "s")
    assert _answer(("fail", "x")) == ("FAIL", "x") and _answer(("FAIL", "y")) == ("FAIL", "y")
    for bad in (None, ("warn", "x"), ("ok",), "ok", ("ok", "m", 3), (None, "m")):
        try:
            _answer(bad)
        except TypeError as e:
            assert "a check answers (status, words)" in str(e), str(e)
        else:
            raise AssertionError(f"{bad!r} was taken as a check's answer")
    import inspect
    reads = 'status, msg = _answer(c["fn"](*mods))'
    assert reads in inspect.getsource(main), "main() reads a check's answer without _answer"
    assert 'return _answer(c["fn"](*mods))' in inspect.getsource(_check_outcome), (
        "_check_outcome reads a check's answer without _answer")
    return "ok", ("None, an unknown status and a tuple of the wrong length are ERRORs that say "
                  "so; \"fail\" reads as FAIL; main() and _check_outcome read every answer "
                  "through _answer")


@check("files", "the registry of stamps is the files' own; a changed file's stamp is raised, "
                "none went backwards, and versions.json is not tracked", needs=("inventory",))
def _stamps(inventory):
    """The stamp in the file is the only place a version is kept; the registry
    (inventory.registry) is read off the files, and versions.json, if a person
    wrote one out, is ignored by git (11 November 2026). What this holds:

      the registry equals an independent read of every tracked file's stamp,
      and a stamp that is malformed or too far down to be read is named;
      a file changed since HEAD has a stamp that moved, and none moved back
      (the half-applied edit this check was written for);
      versions.json is not a tracked file, which is what made it a merge
      conflict for every parallel branch.

    Before, the list was kept by hand beside the files, and it caught three
    silently half-applied edits.

    Six files shipped with the right code and last week's stamp, because the
    bump was `t.replace(old, new)` with no assertion: str.replace returns the
    string unchanged when the pattern is absent, so a bump that matched nothing
    printed success and did nothing. The first one failed, and every later bump
    looked for a version the file had never reached, so they all failed after
    it. inventory.py then told the truth -- out of date -- about files whose
    code was current, and the only visible symptom was a re-download that
    changed nothing.
    """
    from datetime import datetime
    reg = inventory.registry()
    listed = {}
    for k, v in reg.items():
        listed[_paths.locate(k).resolve()] = v
    assert len(listed) == len(reg), "two registry names are one file"
    # AND EVERY STAMPED FILE IS LISTED. bill_order.py was written on 24
    # September with its own stamp and no line here, so this check -- which
    # reads the manifest's list -- never looked at it, and its first edit went
    # out unbumped.
    r = _run(["git", "ls-files", "*.py", "*.js", "*.css", "*.html", "*.bat", "*.sql", "*.toml"],
             capture_output=True, text=True)
    tracked = (r.stdout or "").split()
    if not tracked:
        return "skip", "no git history here"
    bad, scanned = [], {}
    for name in tracked:
        if not inventory.is_code_path(name) or not Path(name).exists():
            continue
        raw = Path(name).read_bytes()
        if not re.search(r"GRANITE_VERSION:\s*[0-9]", raw[:3000].decode("utf-8", "replace")):
            continue
        m = inventory.FULL_STAMP.search(raw[:800].decode("utf-8", "replace"))
        if not m:
            bad.append(f"{name}: a stamp that is not YYYY-MM-DD.N, or past the first 800 bytes")
            continue
        try:
            datetime.strptime(m.group(1).split(".")[0], "%Y-%m-%d")
        except ValueError:
            bad.append(f"{name}: {m.group(1)} is not a date")
        scanned[Path(name).resolve()] = m.group(1)
    assert not bad, "; ".join(bad[:4])
    assert scanned == listed, (
        "the registry and the files disagree: "
        + "; ".join(f"{p.name} {scanned.get(p)} vs {listed.get(p)}"
                    for p in sorted(set(scanned) | set(listed))
                    if scanned.get(p) != listed.get(p))[:300])
    # Against git: a changed file whose stamp did not move, or moved back.
    unmoved, back = [], []
    try:
        unmoved = inventory.changed_since(_paths.ROOT, "HEAD")[0]
        back = inventory.backwards(_paths.ROOT, "HEAD")
    except Exception:                                           # noqa: BLE001
        pass
    assert not unmoved, ("changed since HEAD with the stamp unmoved (run src/ops/inventory.py "
                         "--bump-changed): " + ", ".join(unmoved[:6]))
    assert not back, "stamp lower than at HEAD: " + ", ".join(back[:6])
    t = _run(["git", "ls-files", "versions.json"], capture_output=True, text=True)
    assert not (t.stdout or "").strip(), (
        "versions.json is tracked again: it is generated (inventory.py --write) and git ignores it, "
        "so that two branches never conflict over it")
    return "ok", f"{len(scanned)} stamped files; the registry is theirs, and none changed unraised"


@check("files", "no generator writes a file a person made by hand")
def _record_untouched():
    """The files nobody can regenerate, and nothing may overwrite.

    The 35 hand-marked times are the only measurement of this system a person
    made, and they were lost twice while they lived as two columns in a file
    that rebuilds overwrite. They live in review/ground_truth.csv now, which a
    person edits and every generator only reads.

    The list has grown since, and each addition is a file that cost somebody
    an evening and cannot be rebuilt from anything:

      review/ground_truth.csv        35 proceedings timed with a stopwatch
      review/checked.jsonl           the bench's judgments, append-only
      corrections/bill_notes.json    written explanations of bills that recur
                                     under one number every term, like the budget
      corrections/officials.json     offices filled by hand from four official
                                     sources
      corrections/member_corrections.json  a name a generator got wrong, and
                                     the evidence
      corrections/place_corrections.json   a polling place the Secretary of
                                     State's own list states wrongly, and the
                                     second source
      corrections/docket_corrections.json  a date the docket states wrongly,
                                     and the journal and roll call that settle it
      corrections/ballot_results.json      the voters' answer on each amendment
      corrections/status/            the session's state, which no published
                                     file gives

    Naming only the first one meant the check grew stale as quietly as the
    thing it guards against: most of these had no guard at all. So since the
    root tidy (8 October 2026) the list is two folders, read as they stand:
    corrections/, what a person corrects or adds to the record by hand, and
    review/, a person's checks of the site's own work. A file put in either
    is guarded the day it is put there, with no list here to remember to
    grow; launch_register.json, the person's own and untracked, stays where
    the morning triage reads it and is named beside them. A build_ or fetch_
    script that so much as writes into either folder fails too, whatever
    file it names.

    THE BENCH'S RECORD IS HELD TO MORE, in the same reading of the scripts
    (2 October 2026; a check of its own until then, "no generator writes the
    bench's record"). It appends and never rewrites a line: a later look at
    the same item is a second judgment rather than a correction of the first.
    So a build_ or fetch_ script may not so much as name checked.jsonl,
    where the other files here may be read by one. And the bench stays off
    the network: it shows unpublished judgments about named people, and it
    binds the loopback address for that reason.
    """
    HANDMADE_DIRS = ("corrections", "review")
    HANDMADE = sorted(f.relative_to(_paths.ROOT).as_posix()
                      for d in HANDMADE_DIRS if (_paths.ROOT / d).is_dir()
                      for f in (_paths.ROOT / d).rglob("*")
                      if f.is_file() and f.name != "README.md" and not f.name.startswith("."))
    # A FLOOR for the folders: the ten tracked files they took on 8 October
    # 2026. Read from nowhere, the list would be empty and pass.
    assert len(HANDMADE) >= 10, (
        f"only {len(HANDMADE)} hand-made files were found in {' and '.join(HANDMADE_DIRS)}/, "
        "and ten were there on 8 October 2026: the folders are not being read")
    HANDMADE.append("launch_register.json")
    # Writing into either folder at all, by its name in a path: "corrections/x"
    # in one string, or "corrections" as a part of its own (ROOT / "review" /
    # ...), opened with "w" or written through a Path.
    dirs = "|".join(HANDMADE_DIRS)
    INTO = re.compile(r'open\s*\([^)]*["\'](?:%s)(?:[/\\]|["\'])[^)]*["\']w|'
                      r'["\'](?:%s)(?:[/\\][^"\'\n]*)?["\'][^\n]{0,60}\.write_(?:text|bytes)'
                      % (dirs, dirs))
    # ... or through a name a line of its own gives such a path, which is how
    # most scripts here name what they write (OUT = ROOT / "corrections" /
    # "x.json", and OUT.write_text(...) further down): written, opened for
    # writing, or put there whole by a rename or a copy, the way a careful
    # writer finishes (os.replace(tmp, OUT)). The review of 8 October 2026
    # planted both shapes in a build_ script and the reader above passed them.
    HELD = re.compile(r'^[ \t]*([A-Za-z_]\w*)[ \t]*(?::[^=\n]*)?=[^=\n][^\n]*'
                      r'["\'](?:%s)(?:[/\\][^"\'\n]*)?["\']' % dirs, re.M)

    def writes_into(src):
        if INTO.search(src):
            return True
        for held in set(HELD.findall(src)):
            n = re.escape(held)
            if re.search(r'\b%s\s*\.\s*(?:write_text|write_bytes)\s*\('
                         r'|\b%s\s*\.\s*open\s*\(\s*(?:mode\s*=\s*)?["\'][wax]'
                         r'|\bopen\s*\(\s*%s\s*,\s*(?:mode\s*=\s*)?["\'][wax]'
                         r'|\.(?:replace|rename)\s*\(\s*%s\s*\)'
                         r'|\b(?:os\.replace|os\.rename|shutil\.(?:copy\w*|move))'
                         r'\s*\([^)\n]*,\s*%s\s*\)' % (n, n, n, n, n), src):
                return True
        return False

    for text, writes in (('open("corrections/x.json", "w")', True),
                         ('open(ROOT / "corrections" / "x.json", "w", encoding="utf-8")', True),
                         ('Path("review/ground_truth.csv").write_text(t)', True),
                         ('(Path("review") / "a.csv").write_text(t)', True),
                         ('OUT = ROOT / "corrections" / "x.json"\nOUT.write_text(t)', True),
                         ('T = Path("review") / "a.csv"\nos.replace(tmp, T)', True),
                         ('NOTES: Path = Path("corrections/n.json")\nwith NOTES.open("w") as fh:', True),
                         ('json.loads(Path("corrections/bill_notes.json").read_text())', False),
                         ('open(ROOT / "corrections" / "x.json", encoding="utf-8")', False),
                         ('gt = Path("review/ground_truth.csv")\nrows = read_any(gt)\n'
                          'with open(gt, encoding="ascii") as fh:', False),
                         ('Path("site/review.json").write_text(t)', False)):
        assert writes_into(text) == writes, (
            f"the reader of writes into {' and '.join(HANDMADE_DIRS)}/ reads {text!r} as "
            + ("no write" if writes else "a write"))
    bad, names = [], []
    scanned = _paths.code_files("build_*.py") + _paths.code_files("fetch_*.py")
    for f in scanned:
        src = f.read_text(encoding="utf-8", errors="replace")
        if "checked.jsonl" in src:
            names.append(f.name)
        if writes_into(src):
            bad.append(f"{f.name} writes into {' or '.join(d + '/' for d in HANDMADE_DIRS)}")
        for name in HANDMADE:
            # Bounded on the left, so that status.txt is not bill_status.txt
            # and officials.json is not town_officials.json.
            stem = r"(?<![\w-])" + re.escape(name.split("/")[-1])
            if not re.search(stem, src):
                continue
            # Opened for writing, written through a Path, or through a
            # module-level constant that names it.
            if re.search(r'open\s*\([^)]*' + stem + r'[^)]*["\']w', src) or \
               re.search(stem + r'[^\n]{0,40}write_text', src) or \
               re.search(r'(?:TRUTH|LEDGER|NOTES|OFFICIALS)\s*\.\s*'
                         r'open\s*\(\s*["\']w', src):
                bad.append(f"{f.name} writes {name}")
    # Each of the three in its own words, and all that fail said together:
    # they were two checks, and one failing did not hide the other.
    said = []
    if names:
        said.append("these name the bench's record and must not: " + ", ".join(names))
    if bad:
        said.append("these write a hand-made file: " + "; ".join(bad))

    rv = _paths.locate("review.py")
    if rv.exists():
        src = _source(rv, errors="replace")
        # The BIND, not the file: the first version of this check read the
        # whole source and failed on the comment explaining why the bind is
        # what it is.
        binds = re.findall(r"HTTPServer\(\s*\(\s*[\"']([\d.]+)[\"']", src)
        if not binds:
            said.append("review.py no longer opens an HTTPServer")
        elif not all(b.startswith("127.") for b in binds):
            said.append("review.py binds " + ", ".join(binds)
                        + "; it must stay on the loopback address")
    # A FLOOR: the build_ and fetch_ scripts this read on 6 October 2026,
    # before any file moved. Read from the root alone after a move, it would
    # read none and pass. A script retired on purpose lowers it, in the same
    # commit: 57 then, 56 since fetch_testimony.py was retired on 7 October,
    # 55 since fetch_leadership.py was deleted on 23 October.
    if len(scanned) < 55:
        said.append(f"only {len(scanned)} build_ and fetch_ scripts were read, and 55 were "
                    "on 23 October: the code folders are not being read (_paths.code_files)")
    assert not said, "; and ".join(said)
    present = [n for n in HANDMADE if (_paths.ROOT / n).exists()]
    return "ok", (f"{len(present)} hand-made file(s) here, in corrections/ and review/, and "
                  "only a person writes them: " + ", ".join(present) + "; no generator "
                  "names the bench's record or writes into either folder, and the bench "
                  "is not on the network")


@check("files", "every pair the owner confirmed as one person is one person in the register, "
                "as the site joins their pages")
def _same_person_one_person():
    """corrections/member_corrections.json's same_person entries with a date
    in "confirmed" are the pairs the owner settled as one person (2 November
    2026); build_site_v2.former_movers joins each pair's pages. The register
    (generated/person_numbers.json), which people.json follows, must say the
    same, or the public data gives one person as two, the second with no
    name and no page (the deep walk of 6 November 2026).

    A pair names site ids, a PersonID or an employee number. Each is found
    in the register as a person or as a number someone holds, and followed
    through replaced_by to the person it is now; both must be found, and be
    the same person. A pair answered "no, two people" is not looked at."""
    mc = _paths.ROOT / "corrections" / "member_corrections.json"
    reg_path = _paths.ROOT / "generated" / "person_numbers.json"
    if not mc.exists() or not reg_path.exists():
        return "skip", "member_corrections.json or the register is not here"
    pairs = [e for e in json.loads(mc.read_text(encoding="utf-8")).get("same_person") or []
             if isinstance(e, dict) and re.match(r"\d{4}-\d{2}-\d{2}", str(e.get("confirmed") or ""))]
    people = json.loads(reg_path.read_text(encoding="utf-8")).get("people") or []
    persons = {e["person"]: e for e in people}
    holder = {str(n): e["person"] for e in people if not e.get("replaced_by")
              for n in e.get("numbers") or []}

    def now(x):
        p = holder.get(str(x)) or (str(x) if str(x) in persons else None)
        seen = set()
        while p and persons.get(p, {}).get("replaced_by") and p not in seen:
            seen.add(p)
            p = str(persons[p]["replaced_by"])
        return p

    bad = []
    for e in pairs:
        h, s = now(e.get("house")), now(e.get("senate"))
        if not (h and s):
            bad.append(f"{e.get('name')}: {e.get('house') if not h else e.get('senate')} is no "
                       "person or number in the register")
        elif h != s:
            bad.append(f"{e.get('name')}: two people, {h} and {s}")
    assert not bad, (f"{len(bad)} of {len(pairs)} pairs the owner confirmed are not one person in "
                     "the register (merge them: person_numbers.py says how): " + "; ".join(bad[:5]))
    return "ok", f"all {len(pairs)} pairs the owner confirmed are one person in the register"


@check("files", "only record_moves.py writes the former addresses kept for a 301, and they only grow")
def _moved_addresses():
    """generated/moved_addresses.json keeps every address a former member's
    page has moved from, so each answers with a 301 for good (the manager, 5
    November 2026: old emails link through them). The build reads it
    (build_site_v2.keep_moved) and src/ops/record_moves.py, which a person
    runs, merges into it. Held: no other code file writes it; each entry is a
    /legislator/ address and a member id; and nothing recorded on dev is
    gone or pointed at another member."""
    stem = r"moved_addresses\.json"
    bad = []
    for f in _paths.code_files("*.py"):
        if f.name == "record_moves.py" or _in_suite(f):
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r'open\s*\([^)]*' + stem + r'[^)]*["\'][wax]', src) or \
           re.search(stem + r'[^\n]{0,60}\.write_(?:text|bytes)', src) or \
           re.search(r'MOVED_ADDRESSES\s*\.\s*(?:write_text|write_bytes|open)\s*\(', src):
            bad.append(f.name)
    assert not bad, "these write the kept former addresses, which only record_moves.py may: " + \
        ", ".join(bad)
    f = _paths.ROOT / "generated" / "moved_addresses.json"
    if not f.exists():
        return "ok", "no other code file writes it; none recorded yet"
    now = json.loads(f.read_text(encoding="utf-8"))
    odd = [f"{k} -> {v}" for k, v in now.items()
           if not (isinstance(k, str) and k.startswith("/legislator/") and isinstance(v, str) and v)]
    assert not odd, "entries that are not an address and a member id: " + "; ".join(odd[:4])
    r = _run(["git", "show", "origin/dev:generated/moved_addresses.json"],
             capture_output=True, text=True)
    if r.returncode == 0 and r.stdout.strip():
        then = json.loads(r.stdout)
        lost = [f"{k} ({v})" for k, v in then.items() if now.get(k) != v]
        assert not lost, "recorded addresses gone or re-pointed against dev's: " + "; ".join(lost[:5])
    return "ok", f"{len(now):,} former address(es) kept, only ever added to"


# =============================================================== build chain ==



@check("files", "no child process is read in an unnamed encoding")
def _child_encoding():
    """text=True decodes in whatever the console happens to speak.

    A Python child on Windows writes its pipe in the console code page,
    where an em dash is the single byte 0x97, and a parent reading it as
    UTF-8 loses the whole stream: the reader thread raises, dies, and hands
    back None. This was found twice in one day -- silently in this file,
    where seven checks ran children and got nothing under a line that said
    77 passed, and loudly in build_all.py, where the pipeline stopped at
    step 3 of 21 with an AttributeError three frames from the punctuation
    that caused it.

    So the rule is repository-wide and mechanical: a call that decodes a
    child's output must say in what. child.run and child.popen do; anything
    passing text=True without an encoding does not.
    """
    out = _run(["git", "ls-files", "*.py"], capture_output=True, timeout=60)
    if out.returncode != 0:
        return "skip", "not a git repository"
    bad, n = [], 0
    for f in out.stdout.split():
        if not Path(f).exists():
            continue
        try:
            tree = _parsed(f)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in ("run", "Popen", "check_output",
                                           "call", "check_call")):
                continue
            n += 1
            kw = {k.arg for k in node.keywords if k.arg}
            texty = any(k.arg in ("text", "universal_newlines")
                        and getattr(k.value, "value", None) is True
                        for k in node.keywords)
            if texty and "encoding" not in kw:
                bad.append(f"{f}:{node.lineno}")
    assert not bad, ("these read a child's output without naming an "
                     "encoding, so one em dash empties the stream: "
                     + ", ".join(bad))
    return "ok", f"{n} direct subprocess calls, every text one names its encoding"


@check("files", "a list too large to load whole is read a row at a time, every row once")
def _rows_one_at_a_time():
    """_json_rows is how the checks read data/member_votes.json, 2.3 million
    ballots, without holding it: three data checks count what it hands them,
    and a reader that dropped a row at the seam between two pieces of the
    file, or stopped early, would leave all three passing on fewer ballots.
    So it is held to json.loads on a list written to exercise the seams --
    brackets, commas and quotes inside strings, nested lists, numbers, a row
    of every length -- with the pieces cut at every size from one character
    up; and a file that ends inside its list, or is not a list, has to raise."""
    rows = [{"bill": "HB1", "name": 'Smith, "Al" [R], {x}', "n": [1, [2, 3], {"a": "]"}]},
            {}, {"bill": "", "year": None, "note": "café \\ ] , ["},
            {"k": "v" * 70}, [1, 2, {"three": 3}], "a string, with ] in it", 12345, 6.5, None,
            {"last": True}]
    tmp = Path(tempfile.mkdtemp(prefix="gr-rows-"))
    try:
        for name, text in (("tight.json", json.dumps(rows, separators=(",", ":"))),
                           ("loose.json", " \n" + json.dumps(rows, indent=1) + "\n"),
                           ("empty.json", "[]"), ("one.json", '[{"a": 1}]')):
            p = tmp / name
            p.write_text(text, encoding="utf-8")
            want = json.loads(text)
            for chunk in list(range(1, 41)) + [len(text), len(text) + 1, 1 << 16]:
                got = list(_json_rows(p, chunk))
                assert got == want, (f"{name} read {chunk} characters at a time gave "
                                     f"{len(got)} rows of {len(want)}, or other rows")
        whole = json.dumps(rows)
        for name, text, why in (("cut.json", whole[:len(whole) // 2], "ends inside its list"),
                                ("open.json", whole[:-1], "ends inside its list"),
                                ("dict.json", '{"a": [1, 2]}', "is not a list"),
                                ("none.json", "", "is not a list")):
            p = tmp / name
            p.write_text(text, encoding="utf-8")
            for chunk in (3, 1 << 16):
                try:
                    got = list(_json_rows(p, chunk))
                except ValueError:
                    continue
                raise AssertionError(f"{name}, which {why}, was read as {len(got)} rows")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", ("every row once and in order, with the file cut into pieces of 1 to 40 "
                  "characters and whole; a file that ends inside its list, or is not one, raises")


@check("files", "committee_details.json has one writer, fetch_committee_details.py, and it is the laptop's")
def _committee_details_one_writer():
    """committees.json is fetch_committees.py's, swapped in whole by GitHub's
    weekly job, and the night's in the kit. committee_details.json is
    fetch_committee_details.py's, run on the laptop at a person's word, and
    the laptop's in the kit. cloud_kit.json's rule is one writer per file,
    because two is how the older copy wins -- and the reason the details have
    their own file is that the second writer of committees.json was going to
    lose to the first every Sunday.

    So: no build_ or fetch_ script but fetch_committee_details.py writes
    committee_details.json, or calls the one function that does; neither does
    the night; fetch_committee_details.py no longer writes the committees it
    reads; and the kit gives the two files the owners they have.
    """
    mine = _paths.locate("fetch_committee_details.py")
    if not mine.exists() or not _paths.locate("committee_details.py").exists():
        return "skip", "fetch_committee_details.py or committee_details.py not here"
    stem = re.escape("committee_details.json")
    bad = []
    scanned = (_paths.code_files("build_*.py") + _paths.code_files("fetch_*.py")
            + [_paths.locate("nightly.py")])
    for f in scanned:
        if f.name == mine.name or not f.exists():
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        if re.search(r"\bwrite_details\s*\(", src) or \
           re.search(r'open\s*\([^)]*' + stem + r'[^)]*["\'][wa]', src) or \
           re.search(stem + r'[^\n]{0,60}(?:write_text|write_bytes|json\.dump)', src) or \
           re.search(r'(?:write_text|json\.dump)[^\n]{0,60}' + stem, src):
            bad.append(f.name)
    assert not bad, (f"these write committee_details.json, which is "
                     f"fetch_committee_details.py's alone: {', '.join(bad)}")
    # A floor, as the hand-made files' guard has: 57 build_ and fetch_ scripts
    # and the night were read on 6 October, before any file moved, and one
    # fewer since fetch_testimony.py was retired on 7 October; one fewer again
    # since fetch_leadership.py was deleted on 23 October.
    assert len(scanned) >= 56, (
        f"only {len(scanned)} scripts were read for writers of committee_details.json, "
        "and 56 were on 23 October: the code folders are not being read")
    src = _source(mine)
    assert re.search(r"\bCD\.write_details\s*\(", src), (
        "fetch_committee_details.py no longer writes committee_details.json "
        "through committee_details.write_details, so this check reads nothing")
    assert not re.search(r"json\.dumps?\(\s*book\b", src), (
        "fetch_committee_details.py writes the committees.json it reads again, "
        "which GitHub's weekly job swaps in whole")
    kit = json.loads(_source("cloud_kit.json")) \
        if Path("cloud_kit.json").exists() else {"kit": []}
    owner = {p: e.get("owner") for e in kit.get("kit", []) for p in e.get("paths", [])}
    if owner:
        assert owner.get("committee_details.json") == "laptop", (
            "cloud_kit.json does not carry committee_details.json as the laptop's: "
            f"{owner.get('committee_details.json')!r}")
        assert owner.get("committees.json") == "night", (
            f"committees.json is {owner.get('committees.json')!r} in the kit, not the night's")
    return "ok", ("committee_details.json: written by fetch_committee_details.py alone, "
                  "the laptop's in the kit; committees.json the night's")


@check("code", "the assistant guard stops what needs the person's word and what no assistant "
               "may do, lets ordinary work through, is wired to every tool that could do harm, "
               "and starts")
def _assistant_guard():
    """The person, 26 October 2026: make sure this development "will avoid
    the mistakes of other AI agents who have deleted codebases or ones that
    have gained unapproved access to the backend of websites it wasn't
    supposed to." .claude/hooks/guard.py is the answer, run by Claude Code
    before every shell command, file write, web fetch and GitHub call any
    session or helper agent makes here. A hook that fails to start lets the
    call through, so this check starts it as Claude Code does.

    THE TABLE IS THE POLICY. Each row is a call and what the guard must say
    to it. Taking a row out, or turning a "deny" into an "allow", is a
    decision for the person, not an edit to make a build pass. Every script
    that calls refusal.check() -- every one that asks the General Court --
    is added to the table as it stands, so a new fetcher is held from the
    day it is written."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("guard", ".claude/hooks/guard.py")
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    B = lambda c: ("Bash", {"command": c})                        # noqa: E731
    table = [
        # The General Court, never from an ad-hoc command or a fetch tool.
        (B("curl -s https://gc.nh.gov/bill_status/"), "deny"),
        (B("wget http://www.gencourt.state.nh.us/rsa/html/"), "deny"),
        (B("python3 -c \"import urllib.request as u; u.urlopen('https://gc.nh.gov/x')\""), "deny"),
        (("WebFetch", {"url": "https://gc.nh.gov/house/"}), "deny"),
        (B("sqlcmd -S 66.211.150.69 -Q 'select 1'"), "deny"),
        # Its scripts, and what goes live, only on the person's word.
        (B("python3 build_all.py"), "ask"),
        (B("python3 refusal.py --clear"), "ask"),
        (B("python3 src/ops/cloud.py push"), "ask"),
        (B("python3 src/ops/cloud.py seed-kit"), "ask"),
        (B("publish"), "ask"),
        (B("cmd /c publish.bat"), "ask"),
        (B("npx wrangler d1 execute follow --remote --command 'select 1'"), "ask"),
        (B("curl -X DELETE https://api.cloudflare.com/client/v4/accounts/x"), "ask"),
        (B("git push origin HEAD:main"), "ask"),
        (B("gh pr merge 12"), "ask"),
        (("mcp__github__merge_pull_request", {}), "ask"),
        (("mcp__github__push_files", {"branch": "main"}), "ask"),
        (("mcp__github__actions_run_trigger", {}), "ask"),
        (("Edit", {"file_path": ".github/workflows/nightly.yml"}), "ask"),
        (("Edit", {"file_path": ".claude/hooks/guard.py"}), "ask"),
        (("Write", {"file_path": "corrections/officials.json"}), "ask"),
        (B("cat .dev.vars"), "ask"),
        (B("echo $CLOUDFLARE_API_TOKEN"), "ask"),
        # What cannot be undone.
        (B("git push --force origin dev"), "deny"),
        (B("git push -f"), "deny"),
        (B("git push origin +guides"), "deny"),
        (B("git clean -fdx"), "deny"),
        (B("git filter-branch --env-filter 'x' HEAD"), "deny"),
        (B("git branch -D dev"), "deny"),
        (B("rm -rf work"), "deny"),
        (B("rm -r db/"), "deny"),
        (B("rm -rf ."), "deny"),
        (B("rm -rf src"), "deny"),
        (B("rm -rf .git"), "deny"),
        (B("echo '[]' > corrections/bill_notes.json"), "deny"),
        (("Write", {"file_path": "STATE.md"}), "deny"),
        (("Edit", {"file_path": "review/ground_truth.csv"}), "deny"),
        (("Edit", {"file_path": "review/checked.jsonl"}), "deny"),
        # Ordinary work, which a guard that cried wolf would teach people to wave through.
        (B("python3 preflight.py --code"), "allow"),
        (B("python3 build_all.py --local"), "allow"),
        (B("python3 src/ops/inventory.py --bump-changed"), "allow"),
        (B("python3 src/hearings/probe_alignment.py --truth"), "allow"),
        (B("grep -rn 'gc.nh.gov' src/pages"), "allow"),
        (B("git push -u origin guides && git push origin HEAD:dev"), "allow"),
        (B("rm -rf site/es .build_cache"), "allow"),
        (B("git branch -d worktree-agent-x >/dev/null"), "allow"),
        (B("rm -rf /tmp/scratch-build"), "allow"),
        (B("python3 src/ops/cloud.py pull"), "allow"),
        (("Edit", {"file_path": "src/pages/guides.py"}), "allow"),
        (("Edit", {"file_path": "corrections/officials.json"}), "allow"),
    ]
    for f in sorted(Path(".").rglob("*.py")):
        if ".claude" in f.parts or f.name in guard.NOT_FETCHERS:
            continue
        try:
            if "refusal.check(" in f.read_text(encoding="utf-8", errors="replace"):
                table.append((B(f"python3 {f.as_posix()}"), "ask"))
        except OSError:
            continue
    wrong = [f"{tool} {inp}: wants {want}, says {got[0]}" for (tool, inp), want in table
             if (got := guard.decide(tool, inp)) and got[0] != want]
    assert not wrong, f"{len(wrong)} of {len(table)} calls answered wrongly: " + "; ".join(wrong[:6])

    cfg = json.loads(_source(".claude/settings.json"))
    wired = [h for e in cfg.get("hooks", {}).get("PreToolUse", [])
             for h in e.get("hooks", []) if "guard.py" in h.get("command", "")
             and all(re.search(e.get("matcher", ""), t) for t in
                     ("Bash", "PowerShell", "Edit", "Write", "NotebookEdit", "WebFetch",
                      "mcp__github__merge_pull_request"))]
    assert wired, ".claude/settings.json does not run guard.py before every tool that could do harm"

    out = _sealed_run([sys.executable, ".claude/hooks/guard.py"], capture_output=True,
                      timeout=30, input=json.dumps(
                             {"tool_name": "Bash", "tool_input": {"command": "git clean -fdx"}}))
    assert '"permissionDecision": "deny"' in out.stdout, (
        f"guard.py does not start and answer as Claude Code runs it: {out.stdout or out.stderr}")
    return "ok", f"{len(table)} calls answered as the policy says, and the hook is wired and starts"


@check("code", "guide_sources names each of its lists once, so no list of pages silently "
               "replaces another")
def _guide_sources_keys():
    """25 October 2026: SOURCES named "medicare_and_disability" twice, and a
    dict literal keeps only the later, so the Department of Health and Human
    Services' and the Department of Education's pages in the first were in no
    list, and every guide citing them would have been held back as citing a
    page nobody reads. Read off the file's own syntax, since the loaded dict
    has already lost the evidence."""
    import ast
    path = Path("src/fetch/other/guide_sources.py")
    tree = ast.parse(_source(path))
    twice = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            twice += sorted({k for k in keys if keys.count(k) > 1})
    assert not twice, f"{path} names a list twice: {', '.join(twice)}"
    return "ok", "every list in guide_sources named once"


@check("files", "a preview deployment's reports never land among real ones")
def _report_databases():
    """wrangler.toml names a database for production and a different one for
    previews, so a test report sent to a preview is never among real readers'
    reports -- and a report the nightly reads is never a test."""
    p = Path("wrangler.toml")
    if not p.exists():
        return "skip", "no wrangler.toml here"
    t = _source(p)
    def ids(section):
        block = re.search(rf"\[\[{re.escape(section)}d1_databases\]\](.*?)(?=\n\[|\Z)", t, re.S)
        assert block, f"no [[{section}d1_databases]] in wrangler.toml"
        assert re.search(r'binding = "DB"', block.group(1)), f"{section or 'top'} binding is not DB"
        return re.search(r'database_id = "([^"]+)"', block.group(1)).group(1)
    prod, prev = ids("env.production."), ids("env.preview.")
    assert prod != prev, "previews write to the production database"
    assert ids("") == prod, "the top-level database is not production's"
    assert re.search(r'^pages_build_output_dir = "site"', t, re.M)
    return "ok", "production and previews each write to their own database"


@check("files", "the triage rules keep a person between a report and a substantial change")
def _triage_rules():
    """reports/TRIAGE.md is what the triage session follows, and this holds it
    to the rules: a report is a claim and never an instruction, nothing is
    fetched or run because a report says so, held reports are not read by the
    session, and anything bigger than a small reproduced fix is a proposal that
    waits. No report can change it."""
    p = Path("reports/TRIAGE.md")
    if not p.exists():
        return "skip", "no reports/TRIAGE.md here"
    t = " ".join(p.read_text(encoding="utf-8").split())     # a wrapped line is one sentence
    for must in ("never an instruction", "Never** run a command", "Do not fetch from the General Court",
                 "Held reports are not yours", "Everything else is a proposal, and waits for the person",
                 "compile_reports.py", "this file", "never published", "ALL of these hold"):
        assert must in t, f"reports/TRIAGE.md no longer says: {must}"
    return "ok", "claim-not-instruction, no fetch, held reports unread, proposals wait"


@check("files", "a writer of a shared file reads it before writing it")
def _writers_merge():
    """former_members.json went from 675 entries to 3 on 7 September.

    fetch_members_db.py fills it from the General Court's legislators table in
    one SELECT; resolve_members.py deduces the handful that table has no row
    for, from the roll call pages. The second wrote its own results over the
    whole file. Everything the first had found was gone, and the only reason
    it was recoverable is that the SELECT can be run again.

    This is the same failure as the manifest losing its 35 hand-marked times,
    twice, and it is worth a structural check rather than a memory: a script
    that WRITES one of these files must also READ it. Reading is not proof of
    merging, but not reading is proof of replacing, and that is the case that
    has actually happened three times.
    """
    shared = ("former_members.json", "bill_status.json", "bill_text.json",
              "testimony_db.json", "narratives.json", "rollcalls.json")
    bad = []
    scanned = _paths.code_files("*.py", dirs=_paths.SCRIPT_DIRS)
    for f in scanned:
        if f.name.startswith(("probe_", "test_")):
            continue
        src = f.read_text(encoding="utf-8", errors="replace")
        for name in shared:
            if name not in src:
                continue
            # Crude on purpose: the question is whether the file is opened for
            # reading anywhere in the script, not how.
            writes = ("write_text" in src or "json.dump" in src
                      or 'open(' in src and '"w"' in src)
            reads = ("read_text" in src or "json.load" in src
                     or ".exists()" in src)
            if writes and not reads:
                bad.append(f"{f.name} writes {name} and never reads it")
    assert not bad, "; ".join(bad)
    # A floor: the scripts of the root and src/ read on 6 October 2026, before
    # any file moved (161), less fetch_testimony.py, retired on 7 October, and
    # fetch_leadership.py, deleted on 23 October.
    assert len(scanned) >= 159, (
        f"only {len(scanned)} scripts were read for writers of the shared files, and 159 "
        "were on 23 October: the code folders are not being read")
    return "ok", f"{len(shared)} shared files, every writer of one reads it first"


# TWO CHECKS RETIRED ON 23 OCTOBER 2026, when every page began loading app.css
# whole: _find_classes_shared (every class the header search draws is styled
# in what style.css took) and _nothing_stranded (audit_css.py's STRANDED list).
# Both guarded the cut of app.css the five build_pages pages loaded, and with
# no cut there is nothing to strand; _one_stylesheet_linked holds every page
# to the one file instead, and audit_css.py still lists dead rules.


@check("files", "every place has exactly one district of its own, and every floterial is laid over them")
def _floterials_overlay():
    """Hillsborough 42 and 43 were labelled floterial and were not.

    A FLOTERIAL DISTRICT IS AN OVERLAY. It is laid exactly over two or more
    whole districts of its county and elects further members across their
    combined population -- so a resident of one is genuinely in two House
    districts at once. It is laid over DISTRICTS, not over towns that each
    elect their own member: Belknap 8 lies over Belknap 3, where Sanbornton and
    Tilton share one seat, so Sanbornton has no member of its own. (This
    docstring said otherwise until 23 September, in the same words the Learn
    page used, and both were corrected together.)

    ONE INVARIANT CATCHES BOTH WAYS THE LABEL CAN BE WRONG: every town or ward
    sits in exactly one district that is not floterial.

      NONE means a base district is wearing the floterial label, so its towns
      have been left with no district of their own. That is Hillsborough 42
      and 43, below.

      TWO OR MORE means a floterial has LOST its label, so it is counted as a
      base district and every town under it appears to have two. Until 23
      September nothing caught this half -- the check tested only that places
      in a labelled floterial had a home -- so a floterial whose "(Floterial)"
      marker fell out of districts/house.txt would have passed, and the site
      would have told every resident under it that their extra members were
      their own district's.

    Where it finds a place with two, it names the culprit: of the districts
    that place sits in, the one laid over another whole district is the
    floterial that has lost its label.

    districts/house.txt had Hillsborough 43 as a floterial covering Milford
    and nothing else, and Hillsborough 42 as a floterial covering
    Lyndeborough, Mont Vernon and New Boston, which appeared nowhere else
    either. Taken literally that said four towns had no base district at all,
    which cannot happen: every town in New Hampshire sits in exactly one.
    Both were base districts wearing the wrong label.

    It survived because every other number stayed right. The file still held
    203 districts and still totalled 400 seats, the town lists still lined up,
    and parse_districts.py rebuilt site/districts.json without complaint --
    the flag is carried through to the reader untested. What it changed was
    what the site told residents of those four towns about their own
    representation, which is the kind of error this project fixes first.

    Corrected, the count reconciles with the geometry the state publishes:
    164 base and 39 floterial districts, which is exactly what NH GRANIT's
    NHHouseDistricts2022_Base and _Float shapefiles contain.

    A SINGLE-PLACE FLOTERIAL is called out separately because it is the same
    error in its most obvious form and a reader of the failure deserves to be
    told which kind they have.
    """
    src = Path("records/districts/house.txt")
    if not src.exists():
        return "skip", "no records/districts/house.txt here"

    head = re.compile(r"^([A-Za-z]+) County District (\d+)(.*)$")
    districts, cur = [], None
    for raw in src.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = head.match(line)
        if m:
            cur = {"name": f"{m.group(1)} County District {m.group(2)}",
                   "floterial": "(Floterial)" in m.group(3), "places": []}
            districts.append(cur)
        elif cur is not None:
            cur["places"].extend(x.strip() for x in line.split(",") if x.strip())

    assert districts, "districts/house.txt parsed to nothing"

    # Every district that is not floterial each place sits in. The invariant is
    # that this list has exactly one entry for every place in the file.
    homes = {}
    for d in districts:
        if not d["floterial"]:
            for p in d["places"]:
                homes.setdefault(p, []).append(d)

    bad = []
    # NONE: a base district wearing the floterial label.
    for d in districts:
        if not d["floterial"]:
            continue
        if len(d["places"]) == 1:
            bad.append(f'{d["name"]} is floterial but covers only '
                       f'{d["places"][0]}')
            continue
        orphan = [x for x in d["places"] if x not in homes]
        if orphan:
            # Blame this district only when EVERY town in it is homeless, as
            # with Hillsborough 42. When only some are, this is a true
            # floterial and the fault lies in a district beneath it that has
            # been given the label -- which the single-place line above, or
            # another line of this list, names. Saying "wrong label" here then
            # would point the reader at the one district that is right.
            verb, own = (("belongs", "its") if len(orphan) == 1
                         else ("belong", "their"))
            blame = (" -- it is a base district carrying the wrong label"
                     if len(orphan) == len(d["places"]) else "")
            bad.append(f'{d["name"]} is floterial, but '
                       + ", ".join(orphan)
                       + f" {verb} to no district of {own} own{blame}")

    # TWO OR MORE: a floterial that has lost its label. The culprit is the
    # district among a doubled place's homes that is laid over another whole
    # one; reported once per culprit rather than once per town under it.
    culprits, unexplained = {}, []
    for p, ds in sorted(homes.items()):
        if len(ds) < 2:
            continue
        over = [a for a in ds if any(b is not a and set(b["places"]) < set(a["places"])
                                     for b in ds)]
        if over:
            for a in over:
                culprits.setdefault(a["name"], a)
        else:
            unexplained.append(f'{p} sits in ' + " and ".join(x["name"] for x in ds)
                               + ", none of them laid over the other")
    for name, a in sorted(culprits.items()):
        under = sorted({b["name"] for p in a["places"] for b in homes.get(p, [])
                        if b is not a})
        bad.append(f'{name} is not labelled floterial, but it is laid over '
                   + ", ".join(under) + " -- it is a floterial that has lost "
                   "its label, so every town under it appears to have two "
                   "districts of its own")
    bad.extend(unexplained)

    assert not bad, (
        "every town and ward sits in exactly one House district that is not "
        "floterial, and these break that. The site would tell residents the "
        "wrong thing about their own representation:\n  " + "\n  ".join(bad))

    flot = sum(1 for d in districts if d["floterial"])
    return "ok", (f"{len(districts) - flot} base and {flot} floterial "
                  f"districts; all {len(homes)} places sit in exactly one "
                  f"district of their own")


@check("files", "every county has its eight elected officers, and none carries a home address")
def _county_officers_sane():
    """RSA 655:9 gives each county a sheriff, a county attorney, a treasurer,
    a register of deeds, a register of probate and three commissioners by
    district. Eighty seats, from the Secretary of State's own roster.

    Two things went wrong while the parser was being written, and both are
    the kind that pass silently:

    Carroll and Sullivan write the commissioner heading "County Commissioner,
    1st District" where the other eight write "District 1". Unrecognised, it
    left the Register of Probate heading in force, and each of those counties
    came out with four registers of probate and no commissioners.

    And the roster prints each candidate's street address. The first run read
    the address column's edge from the word "Address" instead of the
    "Candidate" before it, so street numbers landed in the domicile and
    "Conway 643 Stark Road" was about to be published as a town. A home
    address is the one thing that file promises never to carry.

    Both are properties of the output, so they are checked here whatever the
    parser becomes.
    """
    p = Path("collected/county_officials.json")
    if not p.exists():
        return "skip", "no county_officials.json here"
    recs = json.loads(p.read_text(encoding="utf-8"))["officers"]
    import collections as _c
    want = {"Sheriff": 1, "County Attorney": 1, "County Treasurer": 1,
            "Register of Deeds": 1, "Register of Probate": 1,
            "County Commissioner": 3}
    bad = []
    seats = _c.Counter((r["county"], r["office"]) for r in recs)
    counties = sorted({r["county"] for r in recs})
    if len(counties) != 10:
        bad.append(f"{len(counties)} counties, not ten")
    for c in counties:
        for office, n in want.items():
            if seats[(c, office)] != n:
                bad.append(f"{c} has {seats[(c, office)]} {office}, not {n}")
        d = sorted(r.get("district") for r in recs
                   if r["county"] == c and r["office"] == "County Commissioner")
        if d != ["1", "2", "3"]:
            bad.append(f"{c}'s commissioners sit for districts {d}, not 1-3")
    for r in recs:
        for f in ("name", "office", "county", "source_url", "read_on",
                  "method", "status"):
            if not r.get(f):
                bad.append(f"{r.get('name')!r} has no {f}")
        # Independent of the parser's own guard: a town has no digits and no
        # street in it.
        if re.search(r"\d|\bP\.?O\.?\b|\bBox\b|\b(Rd|Road|St|Street|Ave|"
                     r"Avenue|Dr|Drive|Ln|Lane|Way|Hwy)\b", r.get("domicile", "")):
            bad.append(f"{r['name']!r}'s domicile {r['domicile']!r} carries "
                       f"an address")
        for k in r:
            if k.lower() in ("address", "street", "zip", "city_state_zip"):
                bad.append(f"{r['name']!r} carries a field called {k!r}")
    assert not bad, "\n  ".join(bad[:20])
    return "ok", (f"{len(recs)} officers across {len(counties)} counties, every "
                  f"seat filled once and no address carried")


@check("files", "the turn's rehearsal runs the checks of the built site on its 2027-2028 builds, "
       "and fails where one that holds a night fails")
def _rehearsal_runs_built_checks():
    """private/UNATTENDED_AUDIT_2026-10-18.md, section 4.3.4: preflight
    --built came to the night on 15 October, after the turn was rehearsed on
    5 and 6 October, and tests/rehearse_turn.py answered every preflight.py
    the night started with exit 0 and no record -- so no check of the built
    site had met a 2027-2028 build, and the November rehearsal would not have
    run one either. Held here, by its source: a `preflight.py --built` the
    night starts on a night built in full runs in the copy, and NT and A1
    each hold that the checks ran and none of the hold tier failed. And
    built_checks_held itself, run on four made-up verdicts (the review of
    18 October 2026: a substring of its source was the whole guard, and
    `note(True or ...)` kept it): a hold-tier failure, checks that did not
    run and a verdict with none fail it, and warnings alone pass it."""
    import contextlib
    import importlib.util
    import io
    path = _paths.locate("tests/rehearse_turn.py")
    spec = importlib.util.spec_from_file_location("_rehearse_turn_for_preflight", path)
    RT = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RT)
    held = {}
    for what, b in (("a hold-tier failure", {"ran": True, "hold": ["_x"], "warn": []}),
                    ("checks that did not run", {"ran": False}),
                    ("no record of the checks", None),
                    ("warnings alone", {"ran": True, "hold": [], "warn": ["_y"]})):
        del RT.RESULTS["failed"][:]
        with contextlib.redirect_stdout(io.StringIO()):
            RT.built_checks_held({"built_checks": b} if b is not None else {}, "NT")
        held[what] = not RT.RESULTS["failed"]
    assert held == {"a hold-tier failure": False, "checks that did not run": False,
                    "no record of the checks": False, "warnings alone": True}, (
        f"built_checks_held passes these, by kind of verdict: {held}")
    src = _source(path)
    i = src.find('if name == "preflight.py":')
    assert i != -1, "rehearse_turn no longer answers the night's preflight.py"
    branch = src[i:src.find("elif name ==", i)]
    assert 'sh(["preflight.py"]' in branch and '"--built" in args' in branch and \
        'self.state["build"] == "real"' in branch, (
            "rehearse_turn answers the night's preflight.py --built without running it on a full build")
    for label in ("NT", "A1"):
        assert f'built_checks_held(v, "{label}")' in src, (
            f"the rehearsal's {label} does not hold that the checks of its built site passed")
    return "ok", ("the night's preflight.py --built runs in the copy on a full build, and NT and A1 "
                  "fail on a hold-tier failure or checks that did not run, as built_checks_held "
                  "does on made-up verdicts")


def _rehearsal_unanswered(night_tree, rehearse_tree):
    """(the scripts nightly.py can start outside weekly(), those
    tests/rehearse_turn.py's Nights.fake answers, those it does not, and
    whether a script it does not answer still stops it). A script the night
    starts is every bare `name.py` string in nightly.py -- a list it runs,
    TERM_FILES, an EXITS key -- but for a path built with `/`, and none
    within weekly(), whose steps the rehearsal never takes."""
    parent = {c: p for p in ast.walk(night_tree) for c in ast.iter_child_nodes(p)}

    def in_weekly(n):
        while n in parent:
            n = parent[n]
            if isinstance(n, ast.FunctionDef) and n.name == "weekly":
                return True
        return False
    started = {n.value for n in ast.walk(night_tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, str)
               and re.fullmatch(r"\w+\.py", n.value)
               and not isinstance(parent.get(n), ast.BinOp) and not in_weekly(n)}
    fake = next((f for c in ast.walk(rehearse_tree) if isinstance(c, ast.ClassDef)
                 and c.name == "Nights" for f in c.body
                 if isinstance(f, ast.FunctionDef) and f.name == "fake"), None)
    assert fake is not None, "tests/rehearse_turn.py has no Nights.fake"
    answered = set()
    for n in ast.walk(fake):
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == "name":
            for op, right in zip(n.ops, n.comparators):
                vals = right.elts if isinstance(op, ast.In) and isinstance(
                    right, (ast.Tuple, ast.List, ast.Set)) else [right] if isinstance(
                    op, ast.Eq) else []
                answered |= {v.value for v in vals if isinstance(v, ast.Constant)}
    stops = any(isinstance(n, ast.Raise) and "does not " in ast.unparse(n)
                and "stand in for" in ast.unparse(n) for n in ast.walk(fake))
    return started, answered, sorted(started - answered), stops


@check("files", "the turn's rehearsal stands in for every script an ordinary or a New term "
       "night can start")
def _rehearsal_answers_every_night_step():
    """THE REHEARSAL HAD NOT RUN SINCE 16 OCTOBER (18 November 2026). ceed854c
    gave the night three fetches of the current term from the database
    (TERM_FILES: fetch_reports_db.py, fetch_testimony_db.py and
    fetch_status_db.py, through take_term_data), and Nights.fake, which stops
    the rehearsal at any step it does not stand in for, had no answer for
    them: the first night of the November rehearsal stopped on
    fetch_reports_db.py, and nothing had said so for a month. Held here: every
    script nightly.py names outside weekly() is answered by Nights.fake, by
    `name == ...` or `name in (...)`, and a script it does not answer still
    stops the rehearsal rather than run."""
    started, answered, missing, stops = _rehearsal_unanswered(
        _parsed(_paths.locate("nightly.py")), _parsed(_paths.locate("tests/rehearse_turn.py")))
    assert len(started) >= 15, f"only {len(started)} scripts read off nightly.py: {sorted(started)}"
    assert not missing, ("nightly.py can start " + ", ".join(missing) + ", which "
                         "tests/rehearse_turn.py's Nights.fake does not stand in for: the rehearsal "
                         "stops on its first night. Answer each there")
    assert stops, "Nights.fake no longer stops the rehearsal at a step it does not stand in for"
    # And its fetch_archive_db.py writes the columns beside the views, which
    # take_views holds every view to: without them nothing was ever taken.
    rt = _parsed(_paths.locate("tests/rehearse_turn.py"))
    study = next((ast.unparse(f) for f in ast.walk(rt) if isinstance(f, ast.FunctionDef)
                  and f.name == "study"), "")
    assert '"_columns.json"' in study or "'_columns.json'" in study, (
        "the rehearsal's fetch_archive_db.py (Nights.study) leaves no db/_columns.json beside the "
        "views, so take_views refuses every one of them")
    return "ok", (f"all {len(started)} scripts nightly.py can start outside weekly() are answered "
                  f"by the rehearsal's Nights.fake, any other stops it, and its database views "
                  f"come with their columns")


@check("files", "the turn's rehearsal moves its continuing member into a seat that exists, and its "
       "two files say the same of the seat and the party")
def _rehearsal_moves_into_a_real_seat():
    """THE REHEARSAL OF 19 NOVEMBER 2026 held its first post-turn build on
    two findings that were the harness's own: tests/rehearse_turn.new_roster
    moved Rep. Katherine Prudhomme-O'Brien from Rockingham 13 to "Rockingham
    53", the old district plus 40, which no map and no district table holds,
    so the map counted 381 members against the Legislators tab's 382 and
    entities' tenure of 903 named a district not in the model. The General
    Court's roster names only real seats, and a seat one member leaves is
    another's. Held here on a six-member roster: the mover lands in a
    district of their own county that a newcomer held, the newcomer takes
    the mover's, no district's count of members moves, and Members.txt
    carries the same seat and party as legislators.txt."""
    import importlib.util
    path = _paths.locate("tests/rehearse_turn.py")
    spec = importlib.util.spec_from_file_location("_rehearse_turn_roster", path)
    RT = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(RT)
    seats = [("10", "D"), ("13", "R"), ("13", "D"), ("10", "R"), ("13", "R"), ("10", "D")]
    leg = [f"{100 + i}|Last{i}|First{i}||H|{1000 + i}|8|{d}|{p}|a|b|c|NH|03301|m{i}@gc.nh.gov"
           for i, (d, p) in enumerate(seats)]
    mem = ["LastName\tFirstName\tCounty\tDistrict\tWorkEmail\tparty"] + [
        f"Last{i}\tFirst{i}\tRockingham\t{d}\tm{i}@gc.nh.gov\t{p}" for i, (d, p) in enumerate(seats)]
    L, M, swapped, moved = RT.new_roster(RT.join(leg), RT.join(mem))
    rows = [ln.split("|") for ln in RT.lines(L)]
    count = lambda rs: sorted((f[6], f[7]) for f in rs)
    assert count(rows) == count([ln.split("|") for ln in leg]), (
        f"the fake roster changed a district's count of members: {count(rows)}")
    dist = {k: v for k, v in moved.items() if v[0] == "district"}
    assert dist and all(now in {d for d, _p in seats} and now != was
                        for _f, was, now in dist.values()), (
        f"the fake roster moves a member to a district its county does not have: {dist}")
    by_mail = {f[14].lower(): (f[7], f[8]) for f in rows}
    mrows = [r.split("\t") for r in RT.lines(M)[1:]]
    off = [r for r in mrows if by_mail.get(r[4].lower()) != (r[3], r[5])]
    assert not off, f"Members.txt and legislators.txt disagree on a seat or a party: {off}"
    return "ok", (f"the mover goes {next(iter(dist.values()))[1]} -> "
                  f"{next(iter(dist.values()))[2]} of the same county, a newcomer taking their "
                  f"seat; {len(swapped)} newcomers, every district's count kept, both files agree")


# ---- a run for a change, and the fast path's checks (9 October 2026) ----------
#
# AFTER main() ON PURPOSE: six branches were adding checks above it the
# evening these were written. A check registers wherever it is defined, so
# these run last, each in the group its decorator names.



@check("files", "--changed runs the core and what a change can reach, and nothing it cannot")
def _changed_selects():
    """preflight.py --changed (check_select.py) runs only the checks the
    files changed since a commit can reach, at the person's request of 9
    October 2026. A selection that dropped a check a change could break
    would turn the run green on a broken tree, so this holds the reader to
    known answers on the real checks:

      every name in check_select.CORE is a check (a renamed guard would
      otherwise drop out of every --changed run without a word), and each
      is chosen for any change;
      a change to app.css alone chooses _app_css_published and _chain (each
      reads it, the second through the fixture's CHAIN_NEEDS) and not
      _rows_one_at_a_time, and fewer than half of the checks;
      a change to narrative.py chooses a check that needs it and _chain,
      whose fixture build_site_v2 builds, which imports it;
      a change to a builder's own script in inline/ chooses what a change
      to the builder does: chrome's language script, _language_choice;
      a change to a check's own lines chooses it, and a change to main's,
      or to _in_order's, chooses every check, whichever file of the suite
      holds them; and on two files planted as a suite, the lines a change
      moved in each are read against that file's own definitions;
      comments and docstrings are not read as imports or launches;
      the files and lines a change moved are read off git: a commit, an
      edit to it and a file git does not track; and
      what a run that chose builds and runs again (the refactor's stage 1,
      step 2): the early builds a chosen check takes and no other -- the
      no-logo one for _links_resolve, the one with a day stated for
      _build_date_stated, the shared one for the fifty and more that read
      it, none for the core -- every one for a run of the suite or of the
      code, none for --built or --data, and main() starts what that says;
      and the published pass runs again every harness, or in a run that
      chose its checks the harnesses it chose.
    """
    import argparse
    import inspect
    import check_select as CS
    names = [c["fn"].__name__ for c in CHECKS]
    missing = [n for n in CS.CORE if n not in names]
    assert not missing, ("check_select.CORE names " + ", ".join(missing) + ", no longer a "
                         "check: a renamed guard drops out of every --changed run")
    suite = _suite_files()

    def chosen(changed, lines=None):
        got = CS.choose(CHECKS, suite, changed=changed, lines=lines or {}, parse=_parsed,
                        root=_paths.ROOT)
        return {names[i] for i in got["run"]}
    css = chosen(["src/pages/app.css"])
    assert set(CS.CORE) <= css, "a change to app.css left out the core: " + ", ".join(
        sorted(set(CS.CORE) - css))
    assert {"_app_css_published", "_chain"} <= css and "_rows_one_at_a_time" not in css, (
        "a change to app.css chose " + ", ".join(sorted({"_app_css_published", "_chain"} - css))
        + " wrongly left out, or _rows_one_at_a_time, which reads no such file")
    assert len(css) < len(CHECKS) / 2, (f"a change to app.css alone chose {len(css)} of "
                                        f"{len(CHECKS)} checks")
    narr = chosen(["src/parse/narrative.py"])
    needs_it = sorted(names[i] for i, c in enumerate(CHECKS) if "narrative" in c["needs"])
    assert needs_it and set(needs_it) <= narr and "_chain" in narr, (
        "a change to narrative.py left out " + ", ".join(
            (sorted(set(needs_it) - narr) + ([] if "_chain" in narr else ["_chain"]))[:5]))
    assert "_rows_one_at_a_time" not in narr, "a change to narrative.py chose a check of JSON rows"
    lang = chosen(["src/pages/inline/chrome.lang_head.js"])
    assert "_language_choice" in lang and "_rows_one_at_a_time" not in lang, (
        "a change to chrome's language script in inline/ did not choose _language_choice, "
        "which runs it, or chose a check of JSON rows")
    index = CS._Index([(p.relative_to(_paths.ROOT).as_posix(), _parsed(p)) for p in suite])

    def moved(name, line=None):
        # A change to `name`'s lines -- all of them, or the one `line` lines in --
        # in the file of the suite that holds it.
        i = index.info[name]
        a, b = i["span"]
        return chosen([i["file"]], {i["file"]: [(a + line, a + line) if line is not None else (a, b)]})
    own = moved("_rows_one_at_a_time", 3)
    assert "_rows_one_at_a_time" in own and "_app_css_published" not in own, (
        "a change inside _rows_one_at_a_time's own lines did not choose it alone among "
        "the two")
    assert len(moved("main")) == len(CHECKS), "a change to main() did not choose every check"
    assert "CS.choose(CHECKS, _suite_files()," in inspect.getsource(_changed_choice), (
        "--changed no longer hands check_select every file of the suite")
    assert len(moved("_in_order")) == len(CHECKS), (
        "a change to _in_order, the order main() runs the checks in, did not choose every check")
    imports, strings = CS._code_of('"""import narrative, "narrative.py"."""\n'
                                   '# run("build_x.py")\nimport child\nrun("a.py")\n')
    assert imports == ["import child"] and strings == ['"a.py"'], (
        f"the reader of code took prose for code: {imports}, {strings}")
    tmp = Path(tempfile.mkdtemp(prefix="gr-changed-"))
    try:
        def git(*args):
            r = _run(["git", "-c", "user.name=preflight",
                      "-c", "user.email=preflight@example.invalid", *args],
                     cwd=tmp, capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, f"git {args[0]}: {(r.stderr or r.stdout)[-200:]}"
            return r.stdout
        git("init", "-q", ".")
        _plant(tmp, {"a.py": "one = 1\ntwo = 2\nthree = 3\n", "b.txt": "b\n"})
        git("add", "a.py", "b.txt")
        git("commit", "-q", "-m", "one")
        base = git("rev-parse", "HEAD").strip()
        _plant(tmp, {"a.py": "one = 1\ntwo = 2\nthree = 4\n", "c.css": "x{}\n"})
        got = CS.changed_files(base, tmp)
        assert got == ["a.py", "c.css"], f"the files changed since a commit read as {got}"
        assert CS.changed_lines(base, "a.py", tmp) == [(3, 3)], (
            f"the lines changed read as {CS.changed_lines(base, 'a.py', tmp)}")
        assert CS.merge_base("HEAD", tmp) == base, "the base named was not the commit"
        # Two files planted as a suite: each change read against its own file's lines.
        import types
        two = _plant(tmp / "two", {
            "preflight.py": "def _a():\n    return helper()\n\n\ndef _b():\n    return 2\n",
            "src/checks/suite/pf_x.py": "def helper():\n    return 1\n\n\ndef main():\n    return 0\n"})
        fake = [{"fn": types.SimpleNamespace(__name__=n), "needs": ()} for n in ("_a", "_b")]
        files = [two / "preflight.py", two / "src" / "checks" / "suite" / "pf_x.py"]

        def picked(lines):
            got = CS.choose(fake, files, changed=["src/checks/suite/pf_x.py"], lines=lines, root=two)
            return sorted(fake[i]["fn"].__name__ for i in got["run"])
        pf_x = "src/checks/suite/pf_x.py"
        assert picked({pf_x: [(2, 2)]}) == ["_a"] and picked({pf_x: [(5, 6)]}) == ["_a", "_b"] \
            and picked({"preflight.py": [(5, 5)]}) == ["_b"] and picked({}) == [], (
            "on a suite of two files, the lines a change moved were not read against the "
            "definitions of the file it moved them in")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # What a run that chose builds beside its checks, and runs again.
    takes = {what: {c["fn"].__name__ for c in _reaching({by})} for what, by in _EARLY_TAKEN_BY.items()}
    assert "_links_resolve" in takes["nobrand"] and "_build_date_stated" in takes["stated"] \
        and len(takes["shared"]) >= 50, (
            "the checks that take an early build read as "
            + ", ".join(f"{w} {len(who)}" for w, who in takes.items()) + ": _early_wanted is not "
            "finding the fixture's takers")
    by_name = {c["fn"].__name__: c for c in CHECKS}
    assert _early_wanted([by_name[n] for n in CS.CORE]) == set(), (
        "a run of the core alone would build a fixture site: "
        + ", ".join(sorted(_early_wanted([by_name[n] for n in CS.CORE]))))
    for what, picked in (("app.css", css), ("narrative.py", narr), ("a check's own lines", own),
                         ("_links_resolve alone", {"_links_resolve"})):
        want = {w for w, who in takes.items() if who & picked}
        got = _early_wanted([by_name[n] for n in picked])
        assert got == want and ("nobrand" in got) == ("_links_resolve" in picked), (
            f"for a change to {what} the early builds wanted read as {sorted(got)}, not {sorted(want)}")
    run = argparse.Namespace
    chose = {"run": {i: "" for i, c in enumerate(CHECKS) if c["fn"].__name__ in css}}
    assert _early_for_run(run(built=False, data=False), None) is None \
        and _early_for_run(run(built=True, data=False), None) == set() \
        and _early_for_run(run(built=False, data=True), None) == set() \
        and _early_for_run(run(built=False, data=True), chose) == set() \
        and _early_for_run(run(built=False, data=False), chose) == _early_wanted(
            [by_name[n] for n in css]), (
        "the early builds a run starts are not every one for the suite, none for --built or "
        "--data, and what its chosen checks take for --changed")
    was = dict(_EARLY)
    _start_early_builds(set())
    assert _EARLY == was, "a run that chose no early build started one"
    src = inspect.getsource(main)
    assert "_start_early_builds(_early_for_run(a, chosen))" in src and "_THIS_RUN.chosen = " in src, (
        "main() no longer starts the early builds _early_for_run names, or no longer says what "
        "the run chose")
    published = next(c["fn"] for c in CHECKS if c["fn"].__name__ == "_published_scripts_run_the_same")
    assert "= _published_harnesses()" in inspect.getsource(published), (
        "the published pass no longer takes its harnesses from _published_harnesses, which keeps "
        "to the checks the run chose")
    was = _THIS_RUN.chosen
    try:
        _THIS_RUN.chosen = None
        found, again = _published_harnesses()
        assert len(found) >= 20 and again == found, (
            f"a run of the suite runs {len(again)} of {len(found)} harnesses again on the published copy")
        _THIS_RUN.chosen = set(css)
        _found, again = _published_harnesses()
        theirs = [c for c in found if c["fn"].__name__ in css]
        assert again == theirs and 0 < len(theirs) < len(found), (
            f"a run that chose app.css's {len(css)} checks runs {len(again)} harnesses again on the "
            f"published copy, not the {len(theirs)} of the {len(found)} it chose")
    finally:
        _THIS_RUN.chosen = was
    return "ok", (f"core of {len(CS.CORE)}; app.css alone chooses {len(css)} of {len(CHECKS)}, "
                  f"narrative.py {len(narr)}; a check's own lines choose it, main's choose all; "
                  f"app.css's builds beside it {', '.join(sorted(_early_wanted([by_name[n] for n in css])))} "
                  f"and runs {len(theirs)} of {len(found)} harnesses again on the published copy")


@check("files", "--manifest lists every registered check in the order a run takes them, with "
                "fingerprints that two runs agree on, and runs none")
def _manifest_lists_the_registry():
    """`preflight.py --manifest FILE` (above) is the proof every later step
    of moving the checks rests on, so it is held to what it says:

      on a small module, a check's own print stays when only its docstring
      or its line numbers change and moves with its body; its reach moves
      when a helper it uses changes, or when its name comes to mean
      another helper defined later, and not when a definition it does not
      reach changes;
      it lists every registered check once, in the order main() runs them,
      with the registry's group, words, needs and marks, and a print of
      each that no other check shares;
      run as a script, under a hash seed other than this run's, it writes
      byte for byte what this run makes of the same file, writes nothing
      else in its folder, and runs no check; and with --code it refuses,
      since it runs none to leave out.
    """
    sample = ("import os\n\n\n@check('g', 'one')\ndef one():\n    '''Its words.'''\n"
              "    return helper() + K\n\n\ndef helper():\n    return 1\n\n\nK = 2\n\n\n"
              "def other():\n    return 3\n")

    def of(text):
        return _ManifestPrints([ast.parse(text)]).of("one")
    own, reach, n = of(sample)
    assert n == 2, f"the sample's check reaches {n} definitions, not helper and K"
    same = {"its docstring changed": sample.replace("Its words.", "Other words, longer."),
            "its lines moved": "\n\n# a comment\n" + sample,
            "a definition it does not reach changed": sample.replace("return 3", "return 4")}
    for why, text in same.items():
        assert of(text) == (own, reach, n), f"a check's prints moved when {why}"
    body = of(sample.replace("helper() + K", "helper() - K"))
    assert body[0] != own and body[1] != reach, "a check's prints held when its own body changed"
    for why, text in {"a helper it uses changed": sample.replace("return 1", "return 5"),
                      "its helper's name came to mean a later definition":
                          sample + "\n\ndef helper():\n    return 1 + 0\n"}.items():
        got = of(text)
        assert got[0] == own and got[1] != reach, (
            f"when {why} the check's own print should hold and its reach move: {got} after "
            f"{(own, reach, n)}")
    made = _manifest_text()
    m = json.loads(made)
    order = _in_order(CHECKS)
    assert [e["fn"] for e in m["checks"]] == [c["fn"].__name__ for c in order], (
        "the manifest's checks are not the registry's, in the order main() runs them")
    wrong = [e["fn"] for e, c in zip(m["checks"], order)
             if (e["group"], e["words"], e["needs"], e["expect_fail"], e["last"])
             != (c["group"], c["name"], list(c["needs"]), bool(c.get("expect_fail")),
                 bool(c.get("last")))]
    assert not wrong, f"the manifest misstates the registry for {', '.join(wrong[:5])}"
    assert len({e["own"] for e in m["checks"]}) == len(m["checks"]), (
        "two checks share an own print: the prints are not of their code")
    tmp = Path(tempfile.mkdtemp(prefix="gr-manifest-"))
    try:
        seed = "1" if os.environ.get("PYTHONHASHSEED") == "0" else "0"
        r = _run([sys.executable, _paths.script("preflight.py"), "--manifest", "m.json"], cwd=tmp,
                 capture_output=True, text=True, timeout=900,
                 env={**os.environ, "PYTHONHASHSEED": seed})
        assert r.returncode == 0, f"--manifest: {(r.stderr or r.stdout)[-400:]}"
        assert (tmp / "m.json").read_bytes() == made.encode("utf-8"), (
            f"a run of --manifest under PYTHONHASHSEED={seed} wrote another manifest than this run "
            "makes of the same file")
        left = sorted(p.name for p in tmp.iterdir())
        assert left == ["m.json"], f"--manifest left more than its file: {left}"
        assert "[  ok  ]" not in r.stdout and " passed, " not in r.stdout, (
            f"--manifest ran checks: {r.stdout[-300:]}")
        r = _run([sys.executable, _paths.script("preflight.py"), "--manifest", "m2.json", "--code"],
                 cwd=tmp, capture_output=True, text=True, timeout=300)
        assert r.returncode == 2 and not (tmp / "m2.json").exists(), (
            f"--manifest with --code did not refuse: {(r.stderr or r.stdout)[-300:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(m['checks'])} checks listed in run order with the registry's words, needs "
                  f"and marks; a run under PYTHONHASHSEED={seed} wrote the same bytes and nothing "
                  "else; the prints hold for a moved line or docstring and move with a body, a "
                  "helper, or a name rebound")


# ---- the map: what each check read and ran (19 November 2026) ----------------
#
# The map (pf_runner, "the map"; the refactor's stage 1, step 8) is a record,
# and two things hold it to being one: that it records what a check did, on a
# check whose every read and run is known (_map_probe), and that a check
# recorded answers as it does unrecorded, on the probe and on two real checks
# whose answers rest on what their children are handed.


def _map_probe(tmp, record):
    """Three small checks, run as main() runs a check, in the planted tree `tmp`:
    probe_a imports a module of the tree and runs one of its three functions,
    reads a file, lists a folder, does a once-a-run helper's work (a read under
    _map_kept), and starts a child that runs a script of the tree, which runs
    another of them, a sealed one, and one handed no environment; probe_b only
    takes the helper's work; probe_c runs again the function probe_a ran.
    `record`: under a map rooted at `tmp`, or with no map watching at all.
    ({name: its answer}, {name: what the map saw of it} or None, the module's
    name)."""
    mod = f"gr_map_probe_{os.getpid()}"
    _plant(tmp, {
        f"{mod}.py": ("def ran():\n    return 1\n\n\ndef kid_ran():\n    return 3\n\n\n"
                      "def not_ran():\n    return 2\n"),
        "data.txt": "one\n", "kept.txt": "kept\n", "folder/a.txt": "a\n", "kid.txt": "kid\n",
        "sealed.txt": "sealed\n", "kid.py": (
            "import os\nimport sys\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
            f"import {mod}\n{mod}.kid_ran()\n"
            "with open('kid.txt', encoding='utf-8') as fh:\n    fh.read()\n"
            "print(os.environ.get('PYTHONPATH', '-'), os.environ.get('GRANITE_CHECK_MAP', '-'),"
            " any('gr-map-' in p for p in sys.path), sys.argv[1:])\n"),
        "sealed.py": "with open('sealed.txt', encoding='utf-8') as fh:\n    print(fh.read().strip())\n"})
    made, key = {}, f"the probe's work {os.getpid()}"

    def take():
        with _map_kept(key):
            if key not in made:
                made[key] = (tmp / "kept.txt").read_text(encoding="utf-8").strip()
        return made[key]

    def probe_a():
        sys.path.insert(0, str(tmp))
        try:
            got = __import__(mod).ran()
        finally:
            sys.path.remove(str(tmp))
        with open(tmp / "data.txt", encoding="utf-8") as fh:
            one = fh.read().strip()
        listed = sorted(os.listdir(tmp / "folder"))
        kid = _run([sys.executable, str(tmp / "kid.py"), "x"], cwd=str(tmp), capture_output=True,
                   timeout=60)
        sealed = _sealed_run([sys.executable, str(tmp / "sealed.py")], cwd=str(tmp),
                             capture_output=True, timeout=60)
        bare = subprocess.run([sys.executable, "-c", "pass"], timeout=60).returncode
        return "ok", (f"{got} {one} {listed} {take()} | {kid.stdout.strip()} {kid.stderr.strip()} | "
                      f"{sealed.stdout.strip()} | {bare}")

    def probe_b():
        return "ok", take()

    def probe_c():
        return "ok", str(sys.modules[mod].ran())

    was_map, rec = _THIS_RUN.map, None
    if record:
        rec = _MapRecorder(root=tmp).start()
    else:
        quiet = _MapRecorder(root=tmp)      # never started: every event comes to it and stops
        _MAP_ON.append(quiet)
    _THIS_RUN.map = rec
    answers = {}
    try:
        for fn in (probe_a, probe_b, probe_c):
            if rec is not None:
                rec.begin(fn.__name__)
            try:
                answers[fn.__name__] = _answer(fn())
            finally:
                if rec is not None:
                    rec.end()
    finally:
        _THIS_RUN.map = was_map
        sys.modules.pop(mod, None)
        if rec is not None:
            rec.stop()
        else:
            _MAP_ON.remove(quiet)
    seen = None if rec is None else {n: rec.seen(n) for n in answers}
    return answers, seen, mod


@check("files", "the map records the files a check read, listed and started and the functions it "
                "ran, its children's with its own, and what a once-a-run helper did for it")
def _map_records_what_a_check_ran():
    """The map (pf_runner, "the map") is what a later step would choose a
    change's checks by, so what it records of a check is held on one whose
    every read and run is known (_map_probe): the check's own read, the folder
    it listed, the module it imported (as an import, not a read) and the one
    of its functions it ran (not the others); what its child read and ran, and
    its sealed child's, and the scripts it started; the child it started with
    no environment of its own, counted as one the map could not follow; the
    once-a-run work, among the reads of the check that did it and of the check
    that only took it, and nothing else of the first among the second's; a
    function an earlier check ran, told again for the next check that runs it;
    and the child handed back its own environment and path, with no word of
    the map in either."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-probe-map-")).resolve()
    try:
        answers, seen, mod = _map_probe(tmp, record=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    a, b = seen["probe_a"], seen["probe_b"]
    assert answers["probe_a"][0] == "ok" and answers["probe_b"] == ("ok", "kept") \
            and answers["probe_c"] == ("ok", "1"), (
        f"the probe itself did not run: {answers}")
    want = {"reads": {"data.txt", "kept.txt", "kid.txt", "sealed.txt"}, "lists": {"folder"},
            "imports": {f"{mod}.py"}, "starts": {"kid.py", "sealed.py"},
            "funcs": {f"{mod}.py:ran", f"{mod}.py:kid_ran", "kid.py:<module>",
                      "sealed.py:<module>"}}
    for kind, names in want.items():
        assert names <= a[kind], (f"the map's {kind} of a check left out "
                                  f"{', '.join(sorted(names - a[kind]))}: it saw {sorted(a[kind])[:12]}")
    assert f"{mod}.py:not_ran" not in a["funcs"] and f"{mod}.py" not in a["reads"] \
        and a["untraced"] == 1, (
            f"the map says the check ran a function it never called, or read the module it "
            f"imported as text, or followed {a['untraced']} children handed no environment, "
            "not the one")
    assert seen["probe_c"]["funcs"] == {f"{mod}.py:ran"}, (
        f"a function the check before had run was recorded for the next as "
        f"{sorted(seen['probe_c']['funcs'])}: the map does not turn its functions on again")
    assert b["reads"] == {"kept.txt"} and not b["funcs"] and not b["starts"], (
        f"the check that only took the once-a-run work was recorded as reading {sorted(b['reads'])} "
        f"and running {sorted(b['funcs'])[:6]}, not the work's one read")
    assert a["kept"] == b["kept"] and len(a["kept"]) == 1, (
        f"the once-a-run work is not among both checks' takes: {a['kept']}, {b['kept']}")
    kid = answers["probe_a"][1].split(" | ")[1]
    assert "gr-map-" not in kid and "False ['x']" in kid, (
        f"the map's words reached the child it watched: {kid}")
    return "ok", (f"a check's read, listing, import, starts and the one function it ran, its "
                  f"child's and its sealed child's reads and code, one child it could not follow, "
                  f"and once-a-run work given to both checks: {len(a['funcs'])} functions, "
                  f"{len(a['reads'])} reads")


@check("files", "a check recorded by the map answers as it does unrecorded")
def _map_changes_no_answer():
    """RECORDS ONLY (pf_runner, "the map"): a check run while the map watches
    it must answer what it answers with nothing watching, or the map would
    change the run it describes. Held on the probe of _map_records_what_a_check_ran,
    whose child prints the path and environment it was handed, and on two real
    checks whose answers rest on what their children are handed:
    _children_sealed, whose sealed children and their children must carry the
    seal (the map's sitecustomize.py stands in front of the seal's and must
    hand over to it), and _bootstrap_first, whose children report their
    sys.path. Each runs with no map at all and under a map, and the answers are
    the same once digits and temporary folders are masked; the map saw each run."""
    def words(answer):
        return re.sub(r"(?:gr-|tmp)[\w.-]+|\d+", "#", f"{answer[0]}: {answer[1]}")
    tmp = Path(tempfile.mkdtemp(prefix="gr-probe-same-")).resolve()
    try:
        plain, _seen, _mod = _map_probe(tmp / "plain", record=False)
        mapped, seen, _mod = _map_probe(tmp / "mapped", record=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    differ = [n for n in plain if words(plain[n]) != words(mapped[n])]
    assert not differ, ("the probe answered otherwise under the map: "
                        + "; ".join(f"{plain[n]} / {mapped[n]}" for n in differ))
    by = {c["fn"].__name__: c for c in CHECKS}
    real = [n for n in ("_children_sealed", "_bootstrap_first") if n in by]
    assert len(real) == 2, f"the real checks this holds are gone: {real}"
    for name in real:
        quiet = _MapRecorder()
        _MAP_ON.append(quiet)
        try:
            off = _check_outcome(by[name])
        finally:
            _MAP_ON.remove(quiet)
        rec, was = _MapRecorder().start(), _THIS_RUN.map
        _THIS_RUN.map = rec
        try:
            rec.begin(name)
            on = _check_outcome(by[name])
            rec.end()
        finally:
            _THIS_RUN.map = was
            rec.stop()
        assert words(off) == words(on), (f"{name} answered otherwise under the map: {off[0]} "
                                         f"{str(off[1])[:200]} / {on[0]} {str(on[1])[:200]}")
        got = rec.seen(name)
        assert got["funcs"] and got["reads"] | got["imports"] | got["starts"], (
            f"the map saw nothing of {name} while it ran")
    return "ok", (f"the probe and {', '.join(real)} answer the same with the map and without, "
                  "and the map saw each")


@check("files", "the replay of past commits reads which definitions a change moved, and chooses by "
                "the map's rule and by --changed's")
def _map_replay_rules():
    """src/checks/map_replay.py makes the table step 9 is to be decided on:
    for each commit since a day, what the map's rule would have chosen beside
    what --changed chooses. Held on known answers:

      which definitions a change moved, read off a script's lines: a
      function's body or its decorator moves the function, a method's its
      class and name, a line of a class outside its methods the class's
      body, a constant its name, an import the imports, and a comment
      between definitions nothing; a script that will not parse, all of it;
      on a planted suite and map of three checks: a change inside a
      function chooses the check that ran it and not the one that ran
      another function of the file, a comment chooses none, a constant every
      check that ran any function of the file; a data file changed chooses
      its reader, one added the check that listed its folder; a helper of
      the suite moved, the check whose code reaches it; the runner moved,
      every check; and check_select.choose takes the suite's definitions a
      change moved by name (`moved`), as the replay hands them over.
    """
    import types
    import check_select as CS
    import map_replay as MR
    text = ("import os\n\nK = 1\n\n\n@deco\ndef f():\n    return 1\n\n# a comment\n\n\n"
            "class C:\n    X = 2\n\n    def m(self):\n        return 3\n")
    u = MR.units(text)
    want = {(8,): {("f", "def")}, (6,): {("f", "def")}, (10, 11): set(), (14,): {("C", "class")},
            (17,): {("C.m", "method")}, (3,): {("K", "assign")}, (1,): {("<import>", "import")}}
    for lines, names in want.items():
        got = MR.moved_units(u, list(lines))
        assert got == names, f"a change to line(s) {lines} of the sample moved {got}, not {names}"
    assert MR.moved_units(None, [1]) == {("<module>", "other")}, (
        "a change to a script that will not parse did not move the whole of it")
    tmp = Path(tempfile.mkdtemp(prefix="gr-replay-")).resolve()
    try:
        _plant(tmp, {"preflight.py": ("def _a():\n    return helper()\n\n\ndef _b():\n    return 2\n"
                                      "\n\ndef _c():\n    return 3\n\n\ndef main():\n    return 0\n"),
                     "src/checks/suite/pf_x.py": "def helper():\n    return 1\n"})
        suite = [tmp / "preflight.py", tmp / "src" / "checks" / "suite" / "pf_x.py"]
        row = {"needs": [], "seconds": 1, "kept": [], "reads": [], "imports": [], "lists": [],
               "starts": [], "funcs": []}
        m = {"format": 1, "files": [["src/lib/x.py", ""], ["src/pages/words/w.json", ""],
                                    ["src/pages/words", "dir"]],
             "funcs": ["src/lib/x.py:f", "src/checks/suite/pf_x.py:helper"],
             "checks": [dict(row, fn="_a", funcs=[0, 1]), dict(row, fn="_b", reads=[1]),
                        dict(row, fn="_c", lists=[2])]}
        rules = MR.Rules(m, root=tmp, suite=suite)

        def chose(path, moved, status="M"):
            files = {path: {"status": status, "old": "", "new": "", "minus": [], "plus": []}}
            return sorted(rules.names[i] for i in rules.by_map(files, {path: moved}))
        cases = [("a function the check ran", "src/lib/x.py", {("f", "def")}, "M", ["_a"]),
                 ("a function no check ran", "src/lib/x.py", {("g", "def")}, "M", []),
                 ("a comment", "src/lib/x.py", set(), "M", []),
                 ("a constant", "src/lib/x.py", {("K", "assign")}, "M", ["_a"]),
                 ("a data file read", "src/pages/words/w.json", set(), "M", ["_b"]),
                 ("a data file added", "src/pages/words/new.json", set(), "A", ["_c"]),
                 ("a helper of the suite", "src/checks/suite/pf_x.py", {("helper", "def")}, "M", ["_a"]),
                 ("the runner", "preflight.py", {("main", "def")}, "M", ["_a", "_b", "_c"])]
        for what, path, moved, status, names in cases:
            got = chose(path, moved, status)
            assert got == names, f"the map's rule chose {got} for {what}, not {names}"
        fake = [{"fn": types.SimpleNamespace(__name__=n), "needs": ()} for n in ("_a", "_b", "_c")]
        by_name = CS.choose(fake, suite, changed=["src/checks/suite/pf_x.py"], lines={},
                            moved={"helper"}, root=tmp)
        none = CS.choose(fake, suite, changed=["src/checks/suite/pf_x.py"], lines={}, root=tmp)
        assert sorted(fake[i]["fn"].__name__ for i in by_name["run"]) == ["_a"] and not none["run"], (
            "check_select.choose did not take the suite's moved definitions by name: "
            f"{sorted(by_name['run'])} with, {sorted(none['run'])} without")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return "ok", (f"{len(want)} kinds of line read as the definition they move; {len(cases)} changes "
                  "chosen by the map's rule as they should be; check_select takes moved names")


@check("files", "the state settings file loads with every key, and no second literal county list stands outside it")
def _state_settings_one_place():
    """src/lib/state_settings.json holds the facts about the state that a fork edits
    (its "_about" key says what a fork still changes besides). Two things hold it to
    its job: every key the loader names is there, and no code file keeps its own
    list of the ten counties -- the survey found ten copies, each a place a fork
    would have missed. A list is two county names quoted close together, or two
    joined as an alternation; this file and the tests that name counties to check
    something else are not the code."""
    import state_settings as ST
    for key, subs in ST.REQUIRED.items():
        assert key in ST.SETTINGS, f"state_settings.json has no {key!r}"
        for sub in subs:
            assert sub in ST.SETTINGS[key], f"state_settings.json has no {key!r}/{sub!r}"
    assert len(ST.COUNTIES) == len(set(ST.COUNTIES)) and ST.COUNTIES, "the county list is empty or repeats a county"
    for k in ("county_abbreviations", "county_codes"):
        assert set(ST.SETTINGS[k]) == set(ST.COUNTIES), f"{k} does not name exactly the counties"
    assert set(ST.BILL_PREFIXES["house"]).isdisjoint(ST.BILL_PREFIXES["senate"]), "a bill prefix is in both chambers"
    pair = re.compile(r"""["']belknap["'][^\n]{0,30}["']carroll|belknap\|carroll""", re.I)
    seen = []
    for p in _paths.code_files("*.py"):
        if p.name == "state_settings.py" or _in_suite(p):
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        for m in pair.finditer(t):
            seen.append(f"{p.relative_to(_paths.ROOT)}:{t.count(chr(10), 0, m.start()) + 1}")
    assert not seen, ("a county list stands outside src/lib/state_settings.json; read ST.COUNTIES, "
                      "ST.COUNTY_ABBR or ST.COUNTY_CODE instead: " + ", ".join(seen))
    return "ok", f"{len(ST.COUNTIES)} counties and every key present; no second list in the code"
