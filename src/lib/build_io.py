#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
What each step of a build reads and writes, recorded while it runs.

    python3 build_all.py --local                 # records every step it runs
    python3 build_all.py --local --no-record     # records none
    python3 src/lib/build_io.py                  # what the last build's record says
    python3 src/lib/build_io.py --step "site data"   # one step's files, in full

WHY (16 November 2026, the refactor's build design, step S2; stage 0's B3).
A step says what it needs (needs=) and what it makes (produces=), and those
lists are written by hand: they order the plan and say when a step may be
skipped, and nothing held them to what the step really does. A cache of a
step's output (stages S5 onward) is keyed by what the step read, and a step
can be kept whole only where no other step writes its files -- so both have
to be known, not written down. This records them.

HOW. build_all.py hands every step it starts a folder in GRANITE_BUILD_IO
(ENV). _paths.py, which every script imports first, starts the recorder in a
process that has one (start), so every process of the step is recorded --
the script, every script of this project it starts as a child (narrate_archive
runs narrative.py once a term), and the workers of a process pool, which import
the script again. Each writes what it saw to the folder as it exits, a file a
process, and build_all.py joins them (merge) once the step is done:

  read      a file opened to read before the step changed it, whose bytes
            are the step's input; one the step wrote first and read back is
            its own, and is not;
  wrote     a file opened to write, made by a rename, or truncated, and still
            there when the step ended; a folder made is under "made";
  removed   a file the step removed and had not made; "temporary" counts what
            it made and removed again;
  listed    a folder listed (os.listdir, os.scandir, and so glob, walk,
            iterdir);
  looked    a path whose existence was asked (os.stat, os.path.exists, isfile,
            isdir and lexists, which Path.exists, is_file and is_dir call), or
            opened and not there, and none of the above;
  sqlite    a database connected to, and whether read-only;
  ran       the commands it started, and "scripts" those of this project;
  day       how often it asked build_date.py for the build's day or moment,
            which raises an audit event of its own for each;
  env       each GRANITE_ or GITHUB_ variable it read, and its value (a name
            that reads like a secret's keeps only a sha256 of it), but the one
            that names this folder. A copy of the whole environment made to
            hand to a child (child.py, subprocess) is not a read: the child's
            own reads are recorded in the child;
  before    for a step build_all.py asks it of (KEYED), the sha256 a file it
            read held before the same process changed or removed it.

Python's audit hook (sys.addaudithook) sees every open, listing, rename,
removal, folder made, database connected and process started; the existence
checks, which raise no event, and os.environ's reads are watched for the
process's length. What is code is left out: a module imported, anything
under __pycache__, and anything under the Python that runs it or a folder on
its path that is not this project's -- the signature (build_cache.signature)
and requirements.txt answer for code. A .py file read as text and never
imported is a read, because something read it for its words.

IT OBSERVES AND CHANGES NOTHING. The hook never raises (a fault in it is
swallowed, and it does nothing while it is itself reading a file), no wrapped
function answers other than it did, and the record is written to the folder
build_all.py made, outside the working folder, after the process's last
statement. _paths.py imports this module through importlib, so it is in no
step's signature: it works nothing out. The site built with the record and
with --no-record is the same, byte for byte (CONTRIBUTING.md, "How a change
is proven"); preflight holds a builder's output to it on the fixture.

WHERE IT GOES. build_all.py writes every step's record, the files two steps
write and what the record says against the steps' declared lists, to LOG
(logs/build-io.json.gz), and a digest -- the counts, the warnings and the
log's sha256 -- to site/build.json's "io" (findings, digest). Paths are the
working folder's, with "/"; one outside it is left out and counted.

Standard library only. Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import os

# The variable build_all.py names a step's folder in. _paths.py reads it by
# this name to start the recorder, and preflight holds the two together.
ENV = "GRANITE_BUILD_IO"
FORMAT = 1
# A file of this name in the folder: also keep the sha256 of each file a
# process read before it changed or removed it ("before"), which a shadow
# key needs and nothing else does -- but of the absolute paths the file lists
# (JSON), whose bytes the build knows already (shadow_keys.Keys.known).
KEYED = "keyed"
# Where build_all.py writes the whole build's record.
LOG = Path("logs/build-io.json.gz")
# The variables whose reads are recorded, and the words that make a name a
# secret's, whose value is kept only as a sha256.
ENV_PREFIXES = ("GRANITE_", "GITHUB_")
SECRET_WORDS = ("TOKEN", "SECRET", "KEY", "PASSWORD", "CREDENTIAL")
# The flags of os.open that write.
_WRITES = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_TRUNC", 0)
# The files of the frames an environment read passes through on its way from
# its caller (os.getenv, Mapping.get), by name or by the name a frozen module
# goes by; and of those that read it to hand it on to a child process.
_ENV_FRAMES = ("os.py", "_collections_abc.py", "<frozen os>", "<frozen _collections_abc>")
_ENV_COPIERS = ("child.py", "subprocess.py")


def _frame_file(f):
    return f.f_code.co_filename.replace("\\", "/").rsplit("/", 1)[-1]

_ON = []        # this process's recorder, once started


class _Recorder:
    """What one process read and wrote (the module's docstring). Each path is
    [as first named, first read, first change, last removal, sha256 before]:
    the times are time.monotonic_ns(), which every process of a machine
    shares, so the processes of a step are put in order when joined."""

    def __init__(self, folder):
        import _thread
        import time
        self.folder = os.path.abspath(folder)
        # KEYED there: keep the bytes of what is read and then changed, but of
        # the paths it lists, whose bytes the build knows already.
        self.keyed, self.skip = False, set()
        try:
            with open(os.path.join(self.folder, KEYED), encoding="utf-8") as fh:
                self.keyed, listed = True, fh.read().strip()
            if listed:
                import json
                self.skip = {os.path.normcase(p) for p in json.loads(listed)}
        except (OSError, ValueError):
            pass
        self.clock = time.monotonic_ns
        self.ident = _thread.get_ident
        self.busy = set()
        self.on = True
        self.paths = {}
        self.listed, self.looked, self.sqlite = {}, {}, {}
        self.ran, self.day, self.env = [], {}, {}
        self.t0 = self.clock()
        self.cwd = os.getcwd()
        # A path as named -> (absolute, its key), worked out once while the
        # working folder stays where it is (os.chdir empties it): on Windows
        # os.path.abspath asks the system, 10 to 15 us a call (measured).
        self.named = {}

    # ---- what an event names ------------------------------------------------
    def _resolved(self, p):
        """(absolute path, its key) of a path as an event or a call names it,
        or None for a descriptor or anything that is not a path."""
        if p is None or isinstance(p, (int, bool)):
            return None
        try:
            s = os.fsdecode(p)
        except (TypeError, ValueError):
            return None
        if not s:
            return None
        got = self.named.get(s)
        if got is None:
            a = os.path.abspath(s)
            got = self.named[s] = (a, os.path.normcase(a))
        return got

    def _abs(self, p):
        got = self._resolved(p)
        return got[0] if got else None

    def _entry(self, a):
        k = self.named[a][1] if a in self.named else os.path.normcase(a)
        e = self.paths.get(k)
        if e is None:
            e = self.paths[k] = [a, 0, 0, 0, None]
        return e

    def moved(self, args):
        """os.chdir's event: a relative path names another file from here on."""
        self.named.clear()

    def _sha(self, a):
        """The sha256 of the file at `a` as it stands, or "" where it will
        not read. Called inside the hook, which skips this thread's events
        meanwhile."""
        import hashlib
        h = hashlib.sha256()
        try:
            with open(a, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            return ""
        return h.hexdigest()

    def _changing(self, e):
        """Before the first change to a path this process read: its sha256,
        where the step asks for them (KEYED) and does not know it already."""
        if self.keyed and e[1] and not e[2] and not e[3] and e[4] is None \
                and os.path.normcase(e[0]) not in self.skip:
            e[4] = self._sha(e[0])

    # ---- the events ---------------------------------------------------------
    def open(self, args):
        a = self._abs(args[0]) if args else None
        if a is None:
            return
        mode = args[1] if len(args) > 1 else None
        flags = args[2] if len(args) > 2 else 0
        if mode is None:
            write = isinstance(flags, int) and bool(flags & _WRITES)
        else:
            write = any(c in str(mode) for c in "wax+")
        e = self._entry(a)
        if write:
            if not e[2]:
                self._changing(e)
                e[2] = self.clock()
        elif not e[1]:
            e[1] = self.clock()

    def rename(self, args):
        if len(args) < 2 or any(x not in (None, -1) for x in args[2:4]):
            return
        src, dst = self._abs(args[0]), self._abs(args[1])
        if src:
            e = self._entry(src)
            self._changing(e)
            e[3] = self.clock()
        if dst:
            e = self._entry(dst)
            self._changing(e)
            if not e[2]:
                e[2] = self.clock()

    def remove(self, args):
        if not args or (len(args) > 1 and args[1] not in (None, -1)):
            return
        a = self._abs(args[0])
        if a:
            e = self._entry(a)
            self._changing(e)
            e[3] = self.clock()

    def rmtree(self, args):
        a = self._abs(args[0]) if args else None
        if a:
            self._entry(a)[3] = self.clock()

    def made(self, args):
        if len(args) > 2 and args[2] not in (None, -1):
            return
        a = self._abs(args[0]) if args else None
        if a:
            e = self._entry(a)
            if not e[2]:
                e[2] = self.clock()

    def truncate(self, args):
        a = self._abs(args[0]) if args else None
        if a:
            e = self._entry(a)
            if not e[2]:
                self._changing(e)
                e[2] = self.clock()

    def listing(self, args):
        p = args[0] if args else None
        a = self._abs("." if p is None else p)
        if a:
            self.listed.setdefault(os.path.normcase(a), a)

    def connect(self, args):
        db = args[0] if args else None
        if db is None or isinstance(db, (int, bool)):
            return
        try:
            s = os.fsdecode(db)
        except (TypeError, ValueError):
            return
        ro = False
        if s.startswith("file:"):
            from urllib.parse import unquote
            path, _, query = s[5:].partition("?")
            ro = "mode=ro" in query or "immutable=1" in query
            path = unquote(path)
            if path.startswith("///"):
                path = path[3:] if os.name == "nt" else path[2:]
            elif path.startswith("//"):
                path = path[2:]
            s = path
        if not s or s == ":memory:":
            return
        a = os.path.abspath(s)
        k = os.path.normcase(a)
        prev = self.sqlite.get(k)
        self.sqlite[k] = [a, ro and (prev is None or prev[1])]

    def popen(self, args):
        """subprocess.Popen's event: (executable, args, cwd, env)."""
        if len(args) > 1:
            self.started(args[1], args[2] if len(args) > 2 else None)

    def spawned(self, args):
        """os.posix_spawn's and os.exec's: (path, argv, env)."""
        if len(args) > 1:
            self.started(args[1], None)

    def started(self, argv, cwd):
        if isinstance(argv, (list, tuple)):
            argv = [os.fsdecode(x) if isinstance(x, (bytes, os.PathLike)) else str(x) for x in argv]
        else:
            argv = os.fsdecode(argv) if isinstance(argv, (bytes, os.PathLike)) else str(argv)
        self.ran.append({"argv": argv, "cwd": self._abs(cwd) if cwd is not None else None})

    def system(self, args):
        if args:
            self.ran.append({"argv": str(args[0]), "cwd": None})

    def asked_day(self, name):
        self.day[name] = self.day.get(name, 0) + 1

    def looked_at(self, p):
        if not self.on or self.ident() in self.busy:
            return
        got = self._resolved(p)
        if got and got[1] not in self.looked:
            self.looked[got[1]] = got[0]

    def env_read(self, key, value):
        """A read of os.environ[key], from a caller found past the frames of
        os and Mapping; one made to hand the environment on to a child is
        not a read (the module's docstring)."""
        if key == ENV or not self.on:
            return
        f = sys._getframe(2)
        while f is not None and _frame_file(f) in _ENV_FRAMES:
            f = f.f_back
        if f is not None and _frame_file(f) in _ENV_COPIERS:
            return
        if value is not None and any(w in key.upper() for w in SECRET_WORDS):
            import hashlib
            value = "sha256:" + hashlib.sha256(value.encode("utf-8", "surrogatepass")).hexdigest()
        self.env[key] = value

    # ---- the record -----------------------------------------------------------
    def write(self):
        """This process's record, into the folder: written whole and then
        renamed into place, after the recording has stopped."""
        self.on = False
        import json
        # Installed code: the Python that runs this, and every folder of
        # installed packages on its path, the user's own among them.
        homes = {os.path.normcase(os.path.abspath(p)) for p in
                 (sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix) if p}
        site = sys.modules.get("site")
        for p in list(sys.path) + [getattr(site, "USER_SITE", None) or ""]:
            if p and os.path.basename(os.path.normpath(p)) in ("site-packages", "dist-packages"):
                homes.add(os.path.normcase(os.path.abspath(p)))
        homes.add(os.path.normcase(self.folder))
        ours = {os.path.normcase(str(d)) for d in _paths.code_dirs()}
        imported = set()
        for m in list(sys.modules.values()):
            f = getattr(m, "__file__", None)
            if isinstance(f, str):
                imported.add(os.path.normcase(os.path.abspath(f)))

        def code(k):
            if k in imported or k.endswith((".pyc", ".pyo", ".pyd")) \
                    or "__pycache__" in k:
                return True
            return any(k == h or k.startswith(h.rstrip(os.sep) + os.sep) for h in homes)

        rec = {"format": FORMAT, "pid": os.getpid(), "ppid": os.getppid(), "argv": list(sys.argv),
               "cwd": self.cwd, "t0": self.t0, "t1": self.clock(), "keyed": self.keyed,
               "paths": [e for k, e in self.paths.items() if not code(k)],
               "listed": sorted(a for k, a in self.listed.items()
                                if not code(k) and k not in ours),
               "looked": sorted(a for k, a in self.looked.items() if not code(k)),
               "sqlite": [v for k, v in self.sqlite.items() if not code(k)],
               "ran": self.ran, "day": self.day, "env": self.env}
        name = os.path.join(self.folder, f"{os.getpid()}-{self.t0}.json")
        try:
            with open(name + ".part", "w", encoding="utf-8") as fh:
                json.dump(rec, fh, separators=(",", ":"))
            os.replace(name + ".part", name)
        except OSError:
            pass


def start(folder):
    """Start recording this process into `folder`, once a process; _paths.py
    calls it where build_all.py has named one (ENV). The recorder of a
    process that is already recording."""
    if _ON:
        return _ON[0]
    import atexit
    rec = _Recorder(folder)
    _ON.append(rec)
    handlers = {
        "open": rec.open, "os.rename": rec.rename, "os.remove": rec.remove,
        "os.rmdir": rec.remove, "shutil.rmtree": rec.rmtree, "os.mkdir": rec.made,
        "os.truncate": rec.truncate, "os.listdir": rec.listing, "os.scandir": rec.listing,
        "sqlite3.connect": rec.connect, "subprocess.Popen": rec.popen,
        "os.posix_spawn": rec.spawned, "os.exec": rec.spawned, "os.system": rec.system,
        "os.chdir": rec.moved,
        "build_date.today": lambda a: rec.asked_day("today"),
        "build_date.now": lambda a: rec.asked_day("now"),
        "build_date.utcnow": lambda a: rec.asked_day("utcnow"),
    }
    busy, ident = rec.busy, rec.ident

    def hook(event, args):
        h = handlers.get(event)
        if h is None or not rec.on:
            return
        t = ident()
        if t in busy:
            return
        busy.add(t)
        try:
            h(args)
        except Exception:                                       # noqa: BLE001
            pass
        finally:
            busy.discard(t)

    sys.addaudithook(hook)

    def watch(owner, name):
        was = getattr(owner, name)

        def watched(path, *a, **k):
            if not k.get("dir_fd"):
                try:
                    rec.looked_at(path)
                except Exception:                               # noqa: BLE001
                    pass
            return was(path, *a, **k)
        watched.__name__ = getattr(was, "__name__", name)
        watched.__qualname__ = getattr(was, "__qualname__", name)
        watched.__doc__ = getattr(was, "__doc__", None)
        watched.__wrapped__ = was
        setattr(owner, name, watched)

    watch(os, "stat")
    for name in ("exists", "isfile", "isdir", "lexists"):
        watch(os.path, name)

    environ = type(os.environ)
    got = environ.__getitem__

    def getitem(self, key):
        try:
            value = got(self, key)
        except KeyError:
            if isinstance(key, str) and key.startswith(ENV_PREFIXES):
                try:
                    rec.env_read(key, None)
                except Exception:                               # noqa: BLE001
                    pass
            raise
        if isinstance(key, str) and key.startswith(ENV_PREFIXES):
            try:
                rec.env_read(key, value)
            except Exception:                                   # noqa: BLE001
                pass
        return value
    environ.__getitem__ = getitem
    atexit.register(rec.write)
    return rec


# ---- joining a step's processes (build_all.py's side) -----------------------

def _rel(a, root):
    """`a` as a path of the working folder `root`, with "/"; None for one
    outside it."""
    k, r = os.path.normcase(a), os.path.normcase(root)
    if k == r:
        return "."
    if not k.startswith(r.rstrip(os.sep) + os.sep):
        return None
    return a[len(root.rstrip(os.sep)) + 1:].replace(os.sep, "/")


class _There:
    """Whether paths are there, and folders, a folder's listing at a time:
    a step that read 30,000 saved pages is forty listings to join, not
    60,000 calls to stat (2 s of the join on the laptop, measured)."""

    def __init__(self):
        self.folders = {}

    def _listing(self, parent):
        k = os.path.normcase(parent)
        if k not in self.folders:
            names = {}
            try:
                with os.scandir(parent) as it:
                    for e in it:
                        try:
                            names[os.path.normcase(e.name)] = e.is_dir()
                        except OSError:
                            names[os.path.normcase(e.name)] = False
            except OSError:
                names = None
            self.folders[k] = names
        return self.folders[k]

    def of(self, a):
        """(whether `a` is there, whether it is a folder)."""
        parent, name = os.path.split(a)
        names = self._listing(parent) if name else None
        if names is None:
            return os.path.lexists(a), os.path.isdir(a)
        k = os.path.normcase(name)
        return k in names, bool(names.get(k))


_PY_TOKEN = None


def _scripts(argv):
    """The scripts of this project a command runs, by their bare names."""
    import re
    global _PY_TOKEN
    if isinstance(argv, str):
        if _PY_TOKEN is None:
            _PY_TOKEN = re.compile(r'"([^"]+\.py)"|(\S+\.py)\b')
        toks = [a or b for a, b in _PY_TOKEN.findall(argv)]
    else:
        toks = [t for t in argv if str(t).endswith(".py")]
    out = []
    for t in toks:
        name = str(t).replace("\\", "/").rsplit("/", 1)[-1]
        try:
            if _paths.find(name) is not None and name not in out:
                out.append(name)
        except LookupError:
            pass
    return out


def merge(folder, root="."):
    """The step's record: every process's file in `folder` joined (the
    module's docstring), with paths of the working folder `root`."""
    import json
    root = os.path.abspath(root)
    recs, unread = [], 0
    for f in sorted(Path(folder).glob("*.json")):
        try:
            recs.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            unread += 1
    paths = {}
    for rec in recs:
        for shown, r, w, x, sha in rec.get("paths") or []:
            k = os.path.normcase(shown)
            change = min((t for t in (w, x) if t), default=0)
            e = paths.get(k)
            if e is None:
                paths[k] = [shown, r, w, x, sha if change else None, change]
                continue
            e[1] = min((t for t in (e[1], r) if t), default=0)
            e[2] = min((t for t in (e[2], w) if t), default=0)
            e[3] = max(e[3], x)
            # The bytes before the step's first change are what the process
            # that changed it first saw, where it kept them.
            if change and (not e[5] or change < e[5]):
                e[4], e[5] = sha, change
    out = {"processes": len(recs), "read": [], "wrote": [], "made": [], "removed": [],
           "listed": [], "looked": [], "sqlite": {}, "ran": [], "scripts": [], "day": {},
           "env": {}, "before": {}, "temporary": 0, "outside": 0}
    if unread:
        out["unread_records"] = unread
    there = _There()
    for k, (shown, r, w, x, sha, _c) in paths.items():
        p = _rel(shown, root)
        if p is None:
            out["outside"] += 1
            continue
        here, folder = there.of(shown)
        if r and (not w or r < w):
            if folder:
                out["listed"].append(p)
            elif here or x:
                out["read"].append(p)
                if sha:
                    out["before"][p] = sha
            else:
                out["looked"].append(p)
        if w:
            if folder:
                out["made"].append(p)
            elif here:
                out["wrote"].append(p)
            else:
                out["temporary"] += 1
        elif x and not here:
            out["removed"].append(p)
    seen = set(out["read"]) | set(out["wrote"]) | set(out["made"]) | set(out["removed"])
    listed, looked = set(out["listed"]), set(out["looked"])
    for rec in recs:
        for a in rec.get("listed") or []:
            p = _rel(a, root)
            if p is not None:
                listed.add(p)
        for a in rec.get("looked") or []:
            p = _rel(a, root)
            if p is not None:
                looked.add(p)
        for a, ro in rec.get("sqlite") or []:
            p = _rel(a, root)
            if p is not None:
                out["sqlite"][p] = "ro" if ro and out["sqlite"].get(p, "ro") == "ro" else "rw"
        for run in rec.get("ran") or []:
            out["ran"].append(run.get("argv"))
            for s in _scripts(run.get("argv") or []):
                if s not in out["scripts"]:
                    out["scripts"].append(s)
        for name, n in (rec.get("day") or {}).items():
            out["day"][name] = out["day"].get(name, 0) + int(n)
        out["env"].update(rec.get("env") or {})
    out["listed"] = sorted(listed)
    out["looked"] = sorted(looked - seen - listed - set(out["sqlite"]))
    for key in ("read", "wrote", "made", "removed"):
        out[key].sort()
    out["scripts"].sort()
    out["env"] = dict(sorted(out["env"].items()))
    return out


def counts(rec):
    """What a step's record comes to, for its line in site/build.json."""
    if rec is None:
        return None
    c = {"processes": rec["processes"], "read": len(rec["read"]), "wrote": len(rec["wrote"])}
    if rec["removed"]:
        c["removed"] = len(rec["removed"])
    if rec["day"]:
        c["day"] = sum(rec["day"].values())
    if rec["env"]:
        c["env"] = sorted(rec["env"])
    if rec["scripts"]:
        c["scripts"] = rec["scripts"]
    return c


def _under(p, paths):
    """Whether `p` -- a path or a folder -- is among `paths` or holds one."""
    pre = p.rstrip("/") + "/"
    return any(q == p or q.startswith(pre) for q in paths)


def _some(paths, n=2):
    shown = ", ".join(sorted(paths)[:n])
    return shown + (f" and {len(paths) - n:,} more" if len(paths) > n else "")


def findings(steps, carried=()):
    """[sentence] of what the record says against the plan, for the log and
    site/build.json; `steps` is [(name, needs, produces, sometimes, record)]
    of the steps that ran, in order, each list of paths of the working
    folder; `carried` the outputs a build reads before it rewrites them
    (build_all.CARRIED), which a step may read before the step that writes
    them runs. Four kinds, each worth a person's look and none a stop:

      - a declared need the step did not read, list, look for or connect to:
        the declaration has outlived the code, or the step reads it some way
        the record cannot see;
      - a declared output the step wrote none of: the copy there is an
        earlier build's, which the step's own check of its outputs passes;
      - a file a step read that a later step of the same build writes, and
        no carried output: it read the last build's copy, and on a machine
        that starts empty it would find none;
      - a file two steps write: neither can be kept whole by a cache, and
        their order is part of what the file says. One sentence for each set
        of writers."""
    out = []
    for name, needs, produces, sometimes, rec in steps:
        if rec is None:
            continue
        if not rec["processes"]:
            out.append(f"'{name}' left no record of what it read and wrote: none of its "
                       "processes wrote one as it ended (killed, os._exit, or no script of ours)")
            continue
        # A folder asked to be made is not reading or writing anything: os.mkdir
        # raises its event before it finds the folder there already.
        touched = (set(rec["read"]) | set(rec["listed"]) | set(rec["looked"])
                   | set(rec["sqlite"]) | set(rec["wrote"]) | set(rec["removed"]))
        for n in needs:
            n = str(n).replace("\\", "/")
            if not _under(n, touched):
                out.append(f"'{name}' declares it needs {n} and read nothing of it: take it off "
                           "the step's needs, or find what reads it")
        for p in produces:
            p = str(p).replace("\\", "/")
            if p not in sometimes and not _under(p, rec["wrote"]):
                out.append(f"'{name}' declares it makes {p} and wrote none of it: the copy "
                           "there is an earlier build's; find why, or take it off the step's "
                           "produces")
    carried = {str(c).replace("\\", "/") for c in carried}
    late = {}
    for i, (name, _n, _p, _s, rec) in enumerate(steps):
        if rec is None:
            continue
        mine = set(rec["read"]) - set(rec["wrote"]) - carried
        for later, _n2, _p2, _s2, rec2 in steps[i + 1:]:
            if rec2 is None:
                continue
            hit = mine & set(rec2["wrote"])
            if hit:
                late.setdefault((name, later), set()).update(hit)
                mine -= hit
    for (name, later), files in late.items():
        out.append(f"'{name}' read {len(files):,} file(s) that '{later}', later in the build, "
                   f"writes ({_some(files)}): it read the last build's copy; run it after "
                   "that step, or name the file in build_all.CARRIED")
    writers = {}
    for name, _n, _p, _s, rec in steps:
        for p in (rec or {}).get("wrote") or []:
            writers.setdefault(p, []).append(name)
    groups = {}
    for p, names in writers.items():
        if len(names) > 1:
            groups.setdefault(tuple(names), []).append(p)
    for names, files in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        out.append(f"{len(files):,} file(s) are written by {len(names)} steps, "
                   + ", ".join(f"'{n}'" for n in names) + f" ({_some(files)}): no cache can "
                   "keep either step whole until one step writes them")
    return out


def shared_writers(steps):
    """{path: [step names]} of the files more than one of `steps` --
    [(name, record)] -- wrote."""
    writers = {}
    for name, rec in steps:
        for p in (rec or {}).get("wrote") or []:
            writers.setdefault(p, []).append(name)
    return {p: names for p, names in sorted(writers.items()) if len(names) > 1}


def write_log(doc, path=LOG):
    """`doc` as gzipped JSON at `path`, with no time in the gzip header;
    (its sha256, its size)."""
    import gzip
    import hashlib
    import json
    raw = gzip.compress(json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
                        .encode("utf-8"), mtime=0)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(raw)
    os.replace(tmp, path)
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main():
    import argparse
    import gzip
    import json
    ap = argparse.ArgumentParser(description="what the last build's record of reads and writes says")
    ap.add_argument("--log", default=str(LOG))
    ap.add_argument("--step", help="one step's files, in full")
    a = ap.parse_args()
    try:
        doc = json.loads(gzip.decompress(Path(a.log).read_bytes()).decode("utf-8"))
    except (OSError, ValueError) as e:
        print(f"{a.log}: no record to read ({type(e).__name__})")
        return 1
    for s in doc.get("steps") or []:
        if a.step and s.get("step") != a.step:
            continue
        rec = s.get("record") or {}
        print(f"{s.get('step')}: {rec.get('processes', 0)} process(es), read {len(rec.get('read') or []):,}, "
              f"wrote {len(rec.get('wrote') or []):,}, removed {len(rec.get('removed') or []):,}, "
              f"listed {len(rec.get('listed') or []):,}, looked for {len(rec.get('looked') or []):,}"
              + (f"; the day asked {sum(rec['day'].values())} time(s)" if rec.get("day") else "")
              + (f"; read {', '.join(rec['env'])}" if rec.get("env") else ""))
        if a.step:
            for key in ("read", "wrote", "made", "removed", "listed", "looked", "sqlite", "scripts"):
                for p in rec.get(key) or []:
                    print(f"  {key:8} {p}")
    for w in doc.get("warnings") or []:
        print(f"WARNING {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
