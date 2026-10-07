#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-10.1
"""Run a child process and read what it says, whatever it says.

    import child
    r = child.run([sys.executable, "build_data.py"], capture_output=True)

WHY THIS EXISTS

On 10 September the whole pipeline fell over at step 3 of 21 with

    AttributeError: 'NoneType' object has no attribute 'strip'

which is not what it looks like. `build_data.py` printed an em dash. Python
on Windows writes a pipe in the console code page, where an em dash is the
single byte 0x97; the parent was running under -X utf8 and read the pipe as
UTF-8; the reader thread raised UnicodeDecodeError, died, and left
`r.stdout` as None. The traceback that reached the log was the parent
tripping over the None a moment later, three frames and one puzzle away from
the punctuation mark that caused it.

The same defect had been found in `preflight.py` eight hours earlier, where
it was quieter and worse: seven reads failed there under a line that said
"77 passed", because a check that runs a child and gets nothing back cannot
tell that from a child that had nothing to say. Two instances of one bug in
one day, in the two scripts that run every other script, is what this module
is for.

WHAT IT DOES

    PYTHONUTF8=1 in the child's environment, so a Python child writes UTF-8
    encoding="utf-8", errors="replace" in the parent, so nothing a child can
    print will kill the read

Both halves matter. The first makes the common case correct; the second
makes the uncommon case survivable, because a child that is not Python --
node, wrangler, pdftotext -- does not read PYTHONUTF8 and may emit anything.

`text` is accepted and ignored: passing an encoding already implies it, and
leaving the argument alone means call sites convert by changing the function
name and nothing else.
"""

import os
import subprocess

__all__ = ["run", "popen"]


def _kw(kw):
    env = dict(os.environ, PYTHONUTF8="1")
    env.update(kw.pop("env", None) or {})
    kw.pop("text", None)
    kw.pop("universal_newlines", None)
    kw.setdefault("encoding", "utf-8")
    kw.setdefault("errors", "replace")
    kw["env"] = env
    return kw


def run(cmd, **kw):
    """subprocess.run, with the child's output read as UTF-8."""
    return subprocess.run(cmd, **_kw(kw))


def popen(cmd, **kw):
    """subprocess.Popen, for a caller that streams the child's output."""
    return subprocess.Popen(cmd, **_kw(kw))
