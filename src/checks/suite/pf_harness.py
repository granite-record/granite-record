#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
The node harnesses: a page's script run in node as a browser runs it.

components.js with its words (_components_js) and a page's script after it
(_with_components), as the site publishes both while
_SWITCHED.published_scripts is set (_stripped); node run on a file rather
than a command line (_node_file); and the harnesses of app.js (_node_app,
_app_js). Moved out of preflight.py as they stood, with the comments above
each (16 November 2026, the refactor's stage 1, step 4). This module uses
pf_core and no other module of the suite.
"""

import json
import shutil
import tempfile
from pathlib import Path

from pf_core import (_SWITCHED, _map_kept, _run, _source)


def _app_js(expr, names=("renderHearings", "archivedNote")):
    """app.js loaded in node against dom_stub.js, and `expr` evaluated with
    `scope` holding `names` -- renderHearings and archivedNote unless a caller
    asks for others. Returns the value as JSON, or None where node, app.js or
    the stub is not here.

    The value is printed after a marker, so anything app.js itself logs while
    it loads cannot be mistaken for it.

    While _SWITCHED.testify_log is a list (_testify_email_in_sync sets it), every
    Testify button drawn is added to it as well (_TESTIFY_LOG_TAIL).
    """
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    if not (js.exists() and stub.exists() and shutil.which("node")):
        return None
    logging = isinstance(_SWITCHED.testify_log, list)
    if logging:
        names = tuple(names) + ("TESTIFY_LOG",)
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js))
                                      + (_TESTIFY_LOG_TAIL if logging else ""), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        (root / "go.js").write_text(
            'require("./stub.js");\n'
            'const src = require("fs").readFileSync("./page.js", "utf8");\n'
            'const scope = (0, eval)(src + "; ({' + ", ".join(names) + '})");\n'
            'const out = (' + expr + ');\n'
            'process.stdout.write("\\n@@" + JSON.stringify('
            + ('{out, log: scope.TESTIFY_LOG}' if logging else 'out') + '));\n',
            encoding="utf-8")
        r = _run(["node", "go.js"], cwd=root, capture_output=True, text=True,
                 timeout=60)
        # The error's own line first: node prints the line that threw and
        # its message above the stack, which is all the last 300 characters
        # held, so a failure read "js/loader:1651:32)" and nothing else.
        said = (r.stderr or r.stdout or "").strip()
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not run under node: " + said[:400]
            + (" ... " + said[-200:] if len(said) > 600 else said[400:]))
        got = json.loads(r.stdout.rsplit("@@", 1)[1])
        if logging:
            _SWITCHED.testify_log.extend(got["log"])
            return got["out"]
        return got
    finally:
        shutil.rmtree(root, ignore_errors=True)
_TESTIFY_LOG_TAIL = r"""
;var TESTIFY_LOG=[];
testifyButton=(drawn=>function(d,b,now){
  const at=now===undefined?new Date():now, day=nhDay(at), html=drawn(d,b,at);
  const said=s=>[s.when,String(s.time||""),testifyBody(s),String(s.committee||"").trim(),
    String(s.venue||""),s.amendment||"",s.amendment_num||""];
  if(d&&typeof d==="object")TESTIFY_LOG.push(JSON.parse(JSON.stringify({rec:d,row:b||null,day,html,
    heard:testifyHearings(d).map(said),moving:testifyMoving(d,b,day)})));
  return html;
})(testifyButton);
"""


def _node_app(harness, files=None, args=()):
    """Run `harness` in node beside page.js (app.js), stub.js (dom_stub.js)
    and `files` ({name: text}); what it printed after "@@", as JSON. None
    where node, app.js or the stub is not here."""
    js, stub = Path("src/pages/app.js"), Path("tests/dom_stub.js")
    node = shutil.which("node") or shutil.which("node.exe")
    if not (js.exists() and stub.exists() and node):
        return None
    root = Path(tempfile.mkdtemp())
    try:
        (root / "page.js").write_text(_with_components(_source(js)), encoding="utf-8")
        (root / "stub.js").write_text(_source(stub), encoding="utf-8")
        for name, text in (files or {}).items():
            (root / name).write_text(text, encoding="utf-8")
        (root / "go.js").write_text(harness, encoding="utf-8")
        r = _run([node, "go.js", *args], cwd=root, capture_output=True, text=True, timeout=120)
        # The error's own line first: node prints the line that threw and
        # its message above the stack, which is all the last 300 characters
        # held, so a failure read "js/loader:1651:32)" and nothing else.
        said = (r.stderr or r.stdout or "").strip()
        assert r.returncode == 0 and "@@" in (r.stdout or ""), (
            "app.js did not run under node: " + said[:400]
            + (" ... " + said[-200:] if len(said) > 600 else said[400:]))
        return json.loads(r.stdout.rsplit("@@", 1)[1])
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _components_js(here="."):
    """components.js as every page loads it in its head before any script of
    its own: the file in src/pages/ with the words of src/pages/words/
    written between its markers, as the build writes it into the site
    (build_pages.with_words). "" where it is not here, so a harness then
    fails on the name it lacks, which says what is missing."""
    p = Path(here) / "src/pages/components.js"
    if not p.exists():
        return ""
    import build_pages as BP
    return BP.with_words(p.read_text(encoding="utf-8"))


# THE HARNESSES RUN THE SOURCE, AND ONCE A RUN THE PUBLISHED COPY (23 October
# 2026). The site publishes every script without its comments (strip_js.py);
# while the switch is set, _with_components hands node that copy of components.js
# and of the page's script instead of the source. Only
# _published_scripts_run_the_same sets it, around a second run of every check
# that runs a page's script through _with_components or _node_app, and holds
# each result to the result on the source. _components_js stays the source:
# the checks that read it alone read its lines and its marker comments
# (_components_agree's coverage, _until_by_the_reader's BEHAVIOUR block).
# (The switch is _SWITCHED.published_scripts: the suite's switches are beside _suite_files.)


def _node_file(node, prog, **kw):
    """node run on `prog` from a file rather than with -e: components.js
    with its words is past 32,767 characters since 10 October 2026, which
    Windows refuses as a command line ("The filename or extension is too
    long")."""
    root = Path(tempfile.mkdtemp())
    try:
        (root / "prog.js").write_text(prog, encoding="utf-8")
        return _run([node, str(root / "prog.js")], **kw)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _with_components(js, here="."):
    """A page's script as node is to run it: components.js first, as every
    page loads it, then the script. Both without their comments, as the
    site publishes them, while _SWITCHED.published_scripts is set."""
    if _SWITCHED.published_scripts:
        return _stripped(_components_js(here)) + "\n" + _stripped(js)
    return _components_js(here) + "\n" + js


# EACH SCRIPT IS STRIPPED ONCE A RUN (26 October 2026). The published pass of
# _published_scripts_run_the_same hands node about a hundred harnesses, and
# each stripped components.js and its page's script afresh: 260 calls to
# strip_js.strip, 101 s of a 195 s check, for a few texts. strip() is a pure
# function of its text, so each is stripped once and the answer kept, keyed by
# a sha256 of the text and by the strip() that made it: a check that put
# another strip() in place would not be handed this one's answer. A text
# strip() refuses is refused again on every call, as before.
_STRIPPED = {}


def _stripped(js):
    """strip_js.strip(js), worked out once a run for each text."""
    import hashlib
    import strip_js
    key = (strip_js.strip, hashlib.sha256(js.encode("utf-8")).digest())
    with _map_kept("strip_js.strip of " + key[1].hex()[:16]):
        if key not in _STRIPPED:
            _STRIPPED[key] = strip_js.strip(js)
    return _STRIPPED[key]
