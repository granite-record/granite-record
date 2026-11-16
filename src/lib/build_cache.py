#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.3
"""
Answers a build step worked out before, kept by what they were worked out from.

    import build_cache as BC
    sig = BC.signature("build_bill_versions.py", "bill_blocks.py")
    kept = BC.load("bill_versions", sig)          # {key: answer}, or {}
    key = BC.digest(sig, text_a, text_b)          # what the answer depends on
    answer = kept.get(key)                        # None: work it out
    BC.save("bill_versions", sig, {key: answer, ...})

    packs = BC.Packed("bill_files", "gzip-9", BC.CACHE)   # a packed download
    data = packs.pack(lines)                      # kept where packed before
    packs.keep()                                  # after a run over everything

WHY (23 October 2026, the person's "speed up the scripts and nightly
updates"). The night rebuilds the whole site from an empty machine, and most
of what some steps work out is what they worked out the night before: of the
bill versions' four minutes on GitHub's machine nearly all was diffing pairs
of printings that had not changed, one 2025 HB 2 pair the longest of them,
and the presiding officers were read out of every journal twice, once by the
site data and once by the session pages. Those answers are kept here, in
CACHE, and the kit carries the folder (cloud_kit.json), so a night starts
with the last night's.

AN ANSWER IS KEPT BY EVERYTHING IT DEPENDS ON, and nothing else decides
whether it is used:

  - its inputs, by a sha256 of their bytes (digest, files_digest), never by
    a file's size or time;
  - the code that works it out: signature() is a sha256 of the source of the
    modules named and of every module of this project they import, all the
    way down, read as tokens with the comments left out -- the pattern
    segment_markers.pattern_signature has used since its cache served
    answers the old code gave -- with the Python that runs it. Any change
    that can change an answer changes the signature, and every answer kept
    under the old one is no longer found.

A CACHE NEVER CHANGES WHAT IS BUILT. A file that is not there, will not
read, was written under another signature or holds an answer of the wrong
shape is no cache: load() gives {} and says nothing, and the step works
everything out as it did before there was one. The proof is the build's: the
site built from a cold cache and from a warm one is the same, byte for byte,
as the site built before this module existed (CONTRIBUTING.md, "How a
change is proven").

A RUN ON PART OF THE RECORD WRITES NOTHING HERE. A step saves only after a
run over everything, and saves only the answers that run used, so a cache
holds the record as it now stands and never grows past it.

A COLD BUILD READS NONE OF IT (16 November 2026, the refactor's build
design, step S1). build_all.py --cold -- the New term run's build, which
nightly.py --new-term asks for -- sets GRANITE_COLD for every step, and
then load() gives {} as for a cache that is not there, and session_days
reads no kept sitting days (cold()). What a cold build works out is still
saved, so the next build starts warm.

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import ast
import gzip
import hashlib
import io
import json
import os
import tokenize

# The folder, at the root of the working folder, gitignored, and carried by
# the kit as the night's own (cloud_kit.json).
CACHE = Path(".build_cache")
# The shape of a cache file. A file of any other is no cache.
FORMAT = 1
# Set by build_all.py --cold for every step it runs: a build that reads no
# cache (cold), read here and nowhere else.
COLD = "GRANITE_COLD"


def cold():
    """Whether this process is part of a build that reads no cache
    (build_all.py --cold): GRANITE_COLD set to anything but "" or "0"."""
    return os.environ.get(COLD, "").strip() not in ("", "0")


def _tokens(path):
    """The source of a code file as its tokens, comments and blank lines
    left out, each with its kind, so that two different programs never read
    alike: a comment or a reflowed note does not change it, and anything
    the interpreter reads does."""
    src = Path(path).read_text(encoding="utf-8")
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL):
            continue
        out.append(f"{tok.type}:{tok.string}")
    return "\0".join(out)


def _imports(path):
    """The top-level names of every module a file imports, wherever in the
    file the import is."""
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            names.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            names.add(n.module.split(".")[0])
    return names


def modules(*names):
    """{name: path} of the named code files and every code file of this
    project they import, all the way down."""
    out, todo = {}, [n if n.endswith(".py") else n + ".py" for n in names]
    while todo:
        name = todo.pop()
        if name in out:
            continue
        p = _paths.find(name)
        if p is None:
            raise LookupError(f"build_cache: no code file named {name}")
        out[name] = p
        todo += [f"{m}.py" for m in _imports(p)
                 if f"{m}.py" not in out and _paths.find(f"{m}.py") is not None]
    return dict(sorted(out.items()))


def signature(*names):
    """A sha256 of the code that works an answer out: the named files and
    every module of this project they import, as tokens, and the Python
    that runs them."""
    h = hashlib.sha256(f"format {FORMAT}\0{sys.version}\0".encode("utf-8"))
    for name, p in modules(*names).items():
        h.update(f"\0{name}\0".encode("utf-8"))
        h.update(_tokens(p).encode("utf-8"))
    return h.hexdigest()


def digest(*parts):
    """A sha256 of strings and bytes, each kept apart from the next."""
    h = hashlib.sha256()
    for x in parts:
        # surrogatepass: a text no step could write is still a key, and two
        # different texts are never one.
        b = x if isinstance(x, bytes) else str(x).encode("utf-8", "surrogatepass")
        h.update(len(b).to_bytes(8, "big"))
        h.update(b)
    return h.hexdigest()


def files_digest(paths):
    """A sha256 of files: each one's path as given and its bytes, in the
    order given. A file that will not read is part of the key as such."""
    h = hashlib.sha256()
    for p in paths:
        name = str(p).replace("\\", "/").encode("utf-8")
        h.update(len(name).to_bytes(8, "big"))
        h.update(name)
        try:
            with open(p, "rb") as fh:
                data = fh.read()
        except OSError:
            h.update(b"\xff" * 8)
            continue
        h.update(len(data).to_bytes(8, "big"))
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def path_of(name, folder=None):
    return Path(folder if folder is not None else CACHE) / f"{name}.json.gz"


def load(name, sig, folder=None):
    """{key: answer} kept under `name` by code of signature `sig`, or {} --
    for a file that is not there, will not read, or is another signature's,
    and in a cold build (cold()) whatever is there."""
    if cold():
        return {}
    try:
        with gzip.open(path_of(name, folder), "rt", encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, EOFError, ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(doc, dict) or doc.get("format") != FORMAT or doc.get("sig") != sig \
            or not isinstance(doc.get("entries"), dict):
        return {}
    return doc["entries"]


def save(name, sig, entries, folder=None):
    """Keep `entries` under `name`, whole, in place of what was there. A
    cache that cannot be written is no failure: the next run works it out."""
    p = path_of(name, folder)
    tmp = p.with_name(p.name + f".{os.getpid()}.tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Not sorted: an answer's own objects keep the order of their keys,
        # which is the order a step that writes one out as JSON writes them.
        raw = json.dumps({"format": FORMAT, "sig": sig, "entries": entries},
                         ensure_ascii=False, separators=(",", ":"))
        with open(tmp, "wb") as fh:
            # mtime=0, and no name in the header (it would be the temporary
            # file's, which carries the process id): the same answers make
            # the same bytes, so a night whose answers did not change sends
            # the kit nothing new.
            with gzip.GzipFile(filename="", fileobj=fh, mode="wb", compresslevel=6,
                               mtime=0) as gz:
                gz.write(raw.encode("utf-8"))
        os.replace(tmp, p)
        return True
    except (OSError, ValueError, TypeError):
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


# ---- packed files -------------------------------------------------------------
#
# A FILE PACKED BEFORE IS THE FILE PACKING WOULD MAKE (16 November 2026, the
# refactor's build design, step S4). The downloads pack three kinds of file
# every night: each term's bills (bills-<term>.jsonl.gz) and bill texts
# (bill-texts-<term>.jsonl.gz) at gzip level 9, and the database
# (granite-record.sqlite.xz) at xz preset 6. On the laptop's record on 16
# November 2026 the 38 gzip files took 25.1 s and the database 62.5 s, where a
# night that moved only the sitting term needs 3.5 s of the first and, when
# the database did not move, none of the second. Packing is a function of the
# bytes packed and of the packer alone, so a file is kept by both:
#
#   - by a sha256 of the bytes it packs, as they are handed over;
#   - by the packer (pack_signature): its name and settings, this module's
#     code (signature), the zlib Python was built with and runs against, and
#     the sha256 of a fixed text packed by it -- a library whose output moved
#     moves that text's, and so every key;
#   - and the file is kept under its own sha256, and read back only while its
#     bytes are still that sha256.
#
# One Packed a writer, with its own index (<name>.json.gz, through load and
# save) and its own folder of files (packed/<name>/). A run over everything
# ends with keep(): the index of what that run packed or took, and every
# other file of its folder removed, so the folder never grows past the
# record. A cold build takes nothing and still keeps what it packs. A writer
# handed no folder packs every time and keeps nothing, which is what a caller
# other than the build's own run gets.
PACKED = "packed"


def gzip_bytes(chunks, level):
    """gzip of `chunks`, written one after another, with no name and no time
    in its header: the same chunks, the same bytes."""
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, compresslevel=level, mtime=0) as gz:
        for c in chunks:
            gz.write(c)
    return buf.getvalue()


def xz_bytes(chunks, preset):
    """xz of `chunks` joined, at `preset`. xz writes no time."""
    import lzma
    return lzma.compress(b"".join(chunks), format=lzma.FORMAT_XZ, preset=preset)


# Each packer by its name: how it packs, and its files' ending.
PACKERS = {"gzip-9": (lambda chunks: gzip_bytes(chunks, 9), ".gz"),
           "xz-6": (lambda chunks: xz_bytes(chunks, 6), ".xz")}
# The text each packer is tried on for its signature: a few thousand lines of
# numbers and repeated letters, so that its matches and its literals are both
# a library's own work.
_PROBE = "".join(f"{i} {i * 7919 % 10007:x} {'abcdefghij'[i % 10] * (i % 23)}\n"
                 for i in range(4000)).encode("ascii")
_PACK_SIGS = {}


def pack_signature(how):
    """A sha256 of the packer `how` names: its name, this module's code, the
    zlib Python was built with and runs against, and the sha256 of _PROBE
    packed by it. Once a process."""
    if how not in _PACK_SIGS:
        import zlib
        pack, _ext = PACKERS[how]
        _PACK_SIGS[how] = digest(f"packed {FORMAT}", how, signature("build_cache.py"),
                                 zlib.ZLIB_VERSION, getattr(zlib, "ZLIB_RUNTIME_VERSION", ""),
                                 hashlib.sha256(pack([_PROBE])).hexdigest())
    return _PACK_SIGS[how]


class Packed:
    """One writer's packed files, kept by what they pack (PACKED FILES above).

        packs = Packed("bill_files", "gzip-9", CACHE)
        data = packs.pack(lines)        # bytes: the kept file where these bytes
                                        #   were packed before, else packed now
        packs.keep()                    # after a run over everything, only then

    `folder` is the cache's (CACHE where None); False, the default, is none."""

    def __init__(self, name, how, folder=False):
        self.name, self.how = name, how
        self.pack_with, self.ext = PACKERS[how]
        self.root = None if folder is False else Path(folder if folder is not None else CACHE)
        self.sig = pack_signature(how) if self.root is not None else None
        self.kept = load(name, self.sig, self.root) if self.root is not None else {}
        self.used, self.taken, self.made = {}, 0, 0

    def _file(self, sha):
        return self.root / PACKED / self.name / f"{sha}{self.ext}"

    def _kept(self, key):
        """The kept file packed from bytes of sha256 `key`, while it is still
        the file the index names; None otherwise."""
        want = self.kept.get(key)
        if not (isinstance(want, str) and len(want) == 64):
            return None
        try:
            data = self._file(want).read_bytes()
        except OSError:
            return None
        return data if hashlib.sha256(data).hexdigest() == want else None

    def pack(self, chunks):
        """`chunks` (bytes) packed: the kept file where the same bytes were
        packed by this packer before, and otherwise packed now and kept."""
        chunks = list(chunks)
        if self.root is None:
            self.made += 1
            return self.pack_with(chunks)
        h = hashlib.sha256()
        for c in chunks:
            h.update(c)
        key = h.hexdigest()
        data = self._kept(key)
        if data is not None:
            self.taken += 1
            self.used[key] = self.kept[key]
            return data
        data = self.pack_with(chunks)
        sha = hashlib.sha256(data).hexdigest()
        p = self._file(sha)
        tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(data)
            os.replace(tmp, p)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
        self.made += 1
        self.used[key] = sha
        return data

    def keep(self):
        """Keep what this run packed or took, and nothing else: the index,
        whole (save), and in the folder only the files it names. For the end
        of a run over everything: a run over part of the record calls none,
        and keeps nothing. True where kept."""
        if self.root is None or not save(self.name, self.sig, self.used, self.root):
            return False
        names = {f"{sha}{self.ext}" for sha in self.used.values()}
        try:
            here = list((self.root / PACKED / self.name).iterdir())
        except OSError:
            return True
        for f in here:
            if f.name not in names:
                try:
                    f.unlink()
                except OSError:
                    pass
        return True

    def said(self):
        """What this writer's packing came to, for its step's log."""
        n = self.taken + self.made
        if self.root is None:
            return f"{n} packed"
        return (f"{self.taken} of {n} taken as kept in {(self.root / PACKED / self.name).as_posix()}/ "
                f"(the same bytes packed before), {self.made} packed")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="what the build cache holds")
    ap.add_argument("--folder", default=str(CACHE))
    a = ap.parse_args()
    folder = Path(a.folder)
    files = sorted(folder.glob("*.json.gz")) if folder.is_dir() else []
    if not files:
        print(f"{folder}: no cache here")
        return 0
    for f in files:
        try:
            with gzip.open(f, "rt", encoding="utf-8") as fh:
                doc = json.load(fh)
            print(f"{f.name}: {len(doc.get('entries') or {}):,} answers, signature "
                  f"{str(doc.get('sig'))[:12]}, {f.stat().st_size:,} bytes")
        except (OSError, EOFError, ValueError) as e:
            print(f"{f.name}: will not read ({type(e).__name__}), so it is no cache")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
