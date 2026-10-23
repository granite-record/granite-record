#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.1
"""
Answers a build step worked out before, kept by what they were worked out from.

    import build_cache as BC
    sig = BC.signature("build_bill_versions.py", "bill_blocks.py")
    kept = BC.load("bill_versions", sig)          # {key: answer}, or {}
    key = BC.digest(sig, text_a, text_b)          # what the answer depends on
    answer = kept.get(key)                        # None: work it out
    BC.save("bill_versions", sig, {key: answer, ...})

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
    for a file that is not there, will not read, or is another signature's."""
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
            # mtime=0: the same answers make the same bytes, so a night whose
            # answers did not change sends the kit nothing new.
            with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=6, mtime=0) as gz:
                gz.write(raw.encode("utf-8"))
        os.replace(tmp, p)
        return True
    except (OSError, ValueError, TypeError):
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


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
