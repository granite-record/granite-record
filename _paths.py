#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-06.2
"""
Where the code lives, so that every script and module is found by its bare name.

    import _paths                        # every code folder on the import path
    _paths.script("narrative.py")        # the one file of that name, to run
    _paths.find("keys.py")               # the same, or None where there is none
    _paths.locate("keys.py")             # the same, or ROOT / name where there is none
    _paths.code_files("fetch_*.py")      # every code file whose name matches
    _paths.ROOT                          # the repository root

THE FOLDERS. Code lives at the root (what people, workflows and schedulers run
by name), under src/ (everything those call: src/README.md says which folder
holds what and where a new file goes), in watchers/ (the General Court lane)
and in tests/. CODE_DIRS lists them. A new folder under src/ goes on that list
in the same commit, and preflight fails until it does.

NAMES ARE UNIQUE ACROSS THEM, and every import and every launch is by bare
name. So moving a file from one code folder to another changes no import, no
build_all step, no lane queue line and no command anything else starts:
`import narrative` and build_all's "narrative.py" find src/parse/narrative.py
exactly as they found ./narrative.py. preflight fails on two files of one
name, and script() refuses to choose between them.

THE BOOTSTRAP. Every runnable script starts with these lines, after its
docstring and before it imports anything of this project's:

    # The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
    import sys
    from pathlib import Path
    sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
    import _paths  # noqa: E402,F401

It walks up from the script's own file to the nearest folder holding this one,
so a script at the root and one three folders down under src/ start the same
way, from any working directory. It appends, so the root lands behind the
standard library and what is installed; the import below then puts every
code folder, the root among them, ahead of both, each once (_on_path). A
module imported later runs its own bootstrap and appends the root again,
behind everything, where it decides nothing. Where no _paths.py is above the
file, nothing is added and `import _paths` fails by name, which is the error
to see. preflight holds every runnable script to BOOTSTRAP, word for word,
and runs it from a folder under src/ to see the root come out in front.

LAUNCHING A SCRIPT. Anything that starts another of this project's scripts as
a process goes through script(): build_all's steps, nightly.run, the laptop's
evening job, the lane, livestreams' and the caption tools' children, and
preflight. script() takes a bare name, or a name with a folder in it as a
lane line has ("watchers/rest.py"), and finds the file by its bare name, so a
line written before a move still finds the file after it. That is why the
lane's queue never has to change: rewriting a line would run it again.

PATHS FOUND FROM A FILE. A module that needs the repository root uses ROOT,
not Path(__file__).parent, which is the root only while the file sits at it.

Nothing here reads data, asks the network or writes anything.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# Every folder that holds code, relative to the root, which is "". Order does
# not decide anything -- names are unique -- but it is the order a person
# reads them in: what is run by name, then src/ as src/README.md lists it,
# then the lane and the tests.
SRC_DIRS = (
    "src/fetch/gc_web",
    "src/fetch/gc_db",
    "src/fetch/youtube",
    "src/fetch/other",
    "src/parse",
    "src/hearings",
    "src/pages",
    "src/checks",
    "src/lib",
)
CODE_DIRS = ("",) + SRC_DIRS + ("watchers", "tests")

# The root and src/: where every script that is neither the lane nor a test
# lives. Before src/ existed they were all at the root, so a guard that read
# the root's *.py reads these, and reads the same files after a move.
SCRIPT_DIRS = ("",) + SRC_DIRS

# The lines every runnable script carries, word for word (see THE BOOTSTRAP).
BOOTSTRAP = (
    "# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.\n"
    "import sys\n"
    "from pathlib import Path\n"
    "sys.path += [str(p) for p in Path(__file__).resolve().parents"
    " if (p / \"_paths.py\").is_file()][:1]\n"
    "import _paths  # noqa: E402,F401\n"
)


def code_dirs(root=None, dirs=CODE_DIRS):
    """The folders of `dirs` that exist under `root` (this repository's by
    default), as absolute paths, in that order."""
    base = Path(root).resolve() if root is not None else ROOT
    return [base / d if d else base for d in dirs if (base / d).is_dir()]


def code_files(pattern="*.py", root=None, dirs=CODE_DIRS):
    """Every file directly in one of `dirs` whose name matches `pattern`,
    sorted by name and then by folder, so that a list read before a move and
    the same list read after it come out in the same order."""
    found = [f for d in code_dirs(root, dirs) for f in d.glob(pattern) if f.is_file()]
    return sorted(found, key=lambda f: (f.name, f.as_posix()))


def find(name, root=None):
    """The one code file named `name` (its folder, if given, is ignored), or
    None where there is none. LookupError where there are two: a name is
    unique across the code folders, and this does not choose."""
    bare = Path(str(name).replace("\\", "/")).name
    hits = [d / bare for d in code_dirs(root) if (d / bare).is_file()]
    if len(hits) > 1:
        base = Path(root).resolve() if root is not None else ROOT
        raise LookupError(
            f"{len(hits)} files are named {bare}: "
            + ", ".join(h.relative_to(base).as_posix() for h in hits)
            + ". A name must be unique across the code folders (_paths.py), "
              "so that a bare name finds one file.")
    return hits[0] if hits else None


def script(name, root=None):
    """The file to run for `name`, as a string for a command line: find(),
    and LookupError where there is no such file, so that a launch never
    falls back to whatever the working directory happens to hold."""
    hit = find(name, root)
    if hit is None:
        raise LookupError(
            f"no script named {Path(str(name).replace(chr(92), '/')).name} in any code "
            f"folder under {Path(root).resolve() if root is not None else ROOT} "
            "(_paths.CODE_DIRS)")
    return str(hit)


def locate(name, root=None):
    """Where the file `name` is: a script or module (.py) by its bare name, in
    whichever code folder holds it; anything else, and a .py that is not
    here, at `name` under the root. For a tool that reads a file and says
    when it is not here, so that it reads the same file before a move and
    after it."""
    n = str(name)
    if n.endswith(".py"):
        hit = find(n, root)
        if hit is not None:
            return hit
    return (Path(root).resolve() if root is not None else ROOT) / n


def _on_path():
    """Every code folder on sys.path ahead of the standard library and what is
    installed, each once, so that a module of ours is never shadowed by an
    installed one of the same name.

    A code folder already ahead of them keeps its place: the script's own,
    which Python puts first, or one a check put first for a fixture. A copy
    behind them goes, and a code folder found only there is put in front with
    the rest. That is the root, for a script under src/: the bootstrap
    appends it, behind site-packages. For a script at the root it is the
    root's second copy, which goes."""
    def key(p):
        return os.path.normcase(str(Path(p).resolve()))
    homes = {key(p) for p in (sys.base_prefix, sys.prefix, sys.base_exec_prefix, sys.exec_prefix)}
    keys = [key(p) if p else "" for p in sys.path]
    # Where the interpreter's own entries start: its standard library's zip,
    # then the library, then site-packages, all inside the folder it was
    # installed in (or the virtual environment's).
    start = next((i for i, k in enumerate(keys) if k and any(
        k == h or k.startswith(h.rstrip(os.sep) + os.sep) for h in homes)), len(keys))
    ours = {key(d): str(d) for d in code_dirs()}
    ahead = {k for k in keys[:start] if k}
    kept = [p for i, (p, k) in enumerate(zip(sys.path, keys)) if i < start or k not in ours]
    sys.path[:] = [d for k, d in ours.items() if k not in ahead] + kept


_on_path()
