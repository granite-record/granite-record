#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-16.2
"""
preflight's checks of the GitHub workflows.

Moved out of preflight.py as they stood, with the comments above each (the
refactor's stage 1, step 5); a run takes them in ORDER.json's order. This module
uses pf_core, pf_fixture, pf_harness, pf_runner, pf_shared and itself, and
another area's module only for a check of it that one of these reads.
"""

import json
import re
import shutil
import tempfile
from collections import Counter
from pathlib import Path

import _paths

from pf_core import (_SWITCHED, _run, _source, check)
from pf_shared import (WF_RUNS, _RUNNER_FLOORS, _gh_eval, _gh_render, _gh_unwrap, _plant,
                       _runner_names, _tap_failures, _wf_block, _wf_code, _wf_dry_run_sets,
                       _wf_job_heads, _wf_jobs, _wf_run_ctx, _wf_steps, _wf_value, _workflows)


def _runner_problems(root=None):
    """What a runner names that does not resolve: [sentence]."""
    base = Path(root).resolve() if root is not None else _paths.ROOT
    bad = []
    for runner, names in _runner_names(base).items():
        for name, by_path in names:
            try:
                hit = _paths.find(name, root=base)
            except LookupError as e:
                bad.append(f"{runner} names {name}, and {e}")
                continue
            if hit is None:
                bad.append(f"{runner} names {name}, and no code folder holds it")
            elif by_path and not (base / name).is_file():
                bad.append(f"{runner} runs {name} by its path, and it is not there: it is "
                           f"{hit.relative_to(base).as_posix()}")
    return bad


@check("files", "every script build_all, the night, the lane, the workflows and "
                "publish.bat start resolves to exactly one file")
def _runner_names_resolve():
    """The three runners that start scripts by bare name -- build_all's steps,
    nightly.run and the lane -- find each through
    _paths.script, which fails at four in the morning on a name that finds no
    file or finds two. So each name is resolved here, now. The workflows and
    publish.bat run a script by its path, from the root: those must be where
    they are written. When livestreams.py moved to src/ops/ (the root tidy,
    8 October 2026) the nightly's `Test-Path livestreams.py` moved with it, to
    `Test-Path src/ops/livestreams.py`: left behind, it would have skipped its
    step without a word."""
    tmp = Path(tempfile.mkdtemp(prefix="gr-runners-"))
    try:
        _plant(tmp, {
            "_paths.py": "",
            "build_all.py": 'Step("a", ["moved.py", "--x"])\nStep("b", ["gone.py"] + more)\n',
            "nightly.py": 'run(["twice.py"], "t")\nx = ["moved.py", "y"]\n',
            "watchers/gc_lane.queue": "# c\ndaily 06:00 moved.py --a\nhandover gone.py\n",
            ".github/workflows/nightly.yml": "run: python streams.py\n# python old.py\n",
            "publish.bat": "REM python3 old.py\npython3 checks.py --site site\n",
            "src/parse/moved.py": "", "src/checks/checks.py": "", "src/pages/streams.py": "",
            "src/parse/twice.py": "", "src/pages/twice.py": ""})
        got = _runner_problems(tmp)
        want = ["build_all.py names gone.py", "nightly.py names twice.py",
                "watchers/gc_lane.queue names gone.py", "nightly.yml runs streams.py",
                "publish.bat runs checks.py"]
        assert len(got) == len(want) and all(any(w in g for g in got) for w in want), \
            f"the reader of runners found {got} in a tree made to break five ways"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    names = _runner_names()
    thin = [f"{r} ({len(names.get(r, []))}, was {n})" for r, n in _RUNNER_FLOORS.items()
            if len(names.get(r, [])) < n]
    assert not thin, ("these runners were read as naming fewer scripts than they named on "
                      "6 October, so they are not being read: " + ", ".join(thin))
    bad = _runner_problems()
    assert not bad, "; ".join(bad)
    total = sum(len(v) for v in names.values())
    return "ok", (f"{total} names in {len(names)} runners, each finds one file; the "
                  "workflows' and publish.bat's are where they say")


@check("workflows", "the night's timer starts nightly.yml on main with a scheduled night's boxes at "
                    "the workflow's own cron time, never a second night, and GitHub's cron stands "
                    "down for it")
def _night_timer():
    """workers/night-timer/ (the person, 23 October 2026: "I approve the outside
    timer"): GitHub had begun starting the scheduled night five to seven hours
    late, so a Cloudflare cron starts it at 08:17 UTC, and GitHub's cron is the
    fallback, which stands down when the timer has started tonight's night.
    tests/night-timer.test.js holds the Worker to a GitHub that is a function --
    the boxes it sends, nothing sent when tonight's night has started, a refusal
    not asked again -- and its cron to the workflow's; run here in node."""
    t = Path("tests/night-timer.test.js")
    if not t.is_file():
        return "skip", "tests/night-timer.test.js is not here"
    node = shutil.which("node") or shutil.which("node.exe")
    if not node:
        return "skip", "node is not on PATH"
    r = _run([node, "--test", "--test-reporter=tap", t.as_posix()],
             capture_output=True, text=True, timeout=120)
    out = (r.stdout or "") + (r.stderr or "")
    count = {k: int(v) for k, v in re.findall(r"^# (tests|pass|fail) (\d+)$", out, re.M)}
    fails = _tap_failures(out)
    assert not fails and r.returncode == 0 and count.get("pass", 0) >= 7, (
        f"the night's timer fails {len(fails)}: " + "; ".join(repr(n) for n, _s in fails[:5])
        + f" ({count or out.strip()[-300:]}). `node --test {t.as_posix()}` shows each")
    return "ok", f"{count['pass']} tests of the timer, its cron the workflow's"


@check("build", "a committee page's live hook: outside app.js's root, carrying the Worker's own window "
       "and the very stems /live's schedule gives the committee, on every committee page once placed",
       needs=("live_hook", "build_live"))
def _live_committee(LH, BL):
    """Design section 1.6. live_hook.place() puts the hook directly before
    <div id="results">, which app.js draws into, so no re-render reaches a
    playing stream; its data-window is live_gen.WINDOW, which the Worker's
    clock.js imports through live.gen.js; and its data-match is
    live_hook.stems, the function build_live.match_of calls for a committee,
    so /live and the committee page cannot disagree about whose a stream is.
    build_committees.py and build_study_committees.py place it once
    workers/live/PATCHES.md 11 is applied; until then the patch says how."""
    import html as H
    from collections import namedtuple
    root = Path(".")
    page = ('<html><head></head><body><nav></nav><div id="results"></div>'
            '<script src="app.js"></script></body></html>')
    hist = {"finance": {"house finance division i"}}
    out = LH.place(page, code="H09", chamber="H", name="Finance", history=hist)
    i, j = out.index('id="live-now"'), out.index('<div id="results">')
    assert i < j and out.index("</section>", i) < j, "the hook is not before app.js's root, and outside it"
    assert (out.count('id="live-now"') == 1 and '<script src="/live.js" defer></script>' in out
            and 'href="/live.css"' in out), "the page lacks the hook, live.js or live.css"
    try:
        LH.place(out, code="H09", chamber="H", name="Finance", history=hist)
        raise AssertionError("a page was given a second hook")
    except ValueError:
        pass
    attr = lambda k: H.unescape(re.search(k + r'="([^"]*)"', out).group(1))
    gen = (root / "workers/live/live.gen.js").read_text(encoding="utf-8")
    w = re.search(r"^export const WINDOW = (\{.*\});$", gen, re.M)
    assert w and json.loads(attr("data-window")) == json.loads(w.group(1)), (
        f"the hook's window {attr('data-window')} is not live.gen.js's {w and w.group(1)}")
    clock = (root / "workers/live/clock.js").read_text(encoding="utf-8")
    assert "WINDOW as GEN_WINDOW" in clock and "export const WINDOW = { from:" not in clock, (
        "clock.js keeps a window of its own rather than live.gen.js's")
    Key = namedtuple("Key", "chamber name bill")
    for chamber, name in (("H", "Finance"), ("S", "Judiciary"), ("H", "House Ways and Means"), ("", "Commission on Aging")):
        want = BL.match_of(Key(chamber, name, ""), [{"body": chamber}], "standing", hist)
        got = json.loads(attr("data-match")) if (chamber, name) == ("H", "Finance") else LH.stems(chamber, name, hist)
        assert got == want, f"{chamber} {name}: the hook's stems {got} are not /live's {want}"
    assert json.loads(attr("data-match")) == ["house finance", "finance", "house finance division i"], attr("data-match")
    # A longer committee's stream is never this one's (the review of 30
    # October 2026): the Senate's Education refuses Education Finance's.
    others = [("S", "Education"), ("S", "Education Finance"), ("H", "Education Policy and Administration"),
              ("S", "Finance")]
    assert LH.longer("S", "Education", others) == ["education finance", "senate education finance"], \
        LH.longer("S", "Education", others)
    assert LH.longer("S", "Education Finance", others) == [] and LH.longer("H", "Education", others) == \
        ["education policy and administration", "house education policy and administration"], "longer() by chamber"
    # Placed by the two builders once PATCHES.md 11 is applied (a call, not a
    # mention in a comment): then on every committee page; until then the
    # patch must still say how.
    call = re.compile(r"^[^#\n]*\blive_hook\.place\(", re.M)
    builders = [Path(_paths.locate(f)).read_text(encoding="utf-8")
                for f in ("build_committees.py", "build_study_committees.py")]
    placed = [bool(call.search(b)) for b in builders]
    if not all(placed):
        patches = (root / "workers/live/PATCHES.md").read_text(encoding="utf-8")
        assert "## 11." in patches and "live_hook.place(" in patches, (
            "the committee builders do not place the live hook, and PATCHES.md 11 no longer says how")
    # On a built site: every page carries one hook once placed, and where
    # /live's schedule has the committee, the page's stems are the schedule's.
    site = root / "site"
    built = ""
    if (site / "committee").is_dir() and (site / "live" / "schedule.json").is_file():
        sched = json.loads((site / "live" / "schedule.json").read_text(encoding="utf-8"))
        rows = [r for d in (sched.get("days") or {}).values() for r in d
                if re.fullmatch(r"/committee/[A-Za-z0-9]+", r.get("href") or "")]
        differ = []
        for r in rows:
            f = site / (r["href"].lstrip("/") + ".html")
            if not f.is_file():
                continue
            m = re.search(r'id="live-now"[^>]*data-match="([^"]*)"', f.read_text(encoding="utf-8"))
            if m and json.loads(H.unescape(m.group(1))) != r.get("match"):
                differ.append(f"{r['href']}: page {H.unescape(m.group(1))}, /live {r.get('match')}")
        assert not differ, f"{len(differ)} committee pages and /live disagree on whose stream is whose: " + "; ".join(differ[:3])
        if all(placed):
            # Never two; and one on every page /live's schedule has a meeting
            # for (a retired committee's page has none, by PATCHES.md 11).
            twice = [p.name for p in (site / "committee").glob("*.html")
                     if p.read_text(encoding="utf-8").count('id="live-now"') > 1]
            lacking = sorted({r["href"] for r in rows if (site / (r["href"].lstrip("/") + ".html")).is_file()
                              and 'id="live-now"' not in (site / (r["href"].lstrip("/") + ".html")).read_text(encoding="utf-8")})
            assert not twice and not lacking, (
                f"committee pages with two live hooks {twice[:5]}, or scheduled ones with none {lacking[:5]}")
        built = f"; the built site's {len(rows)} scheduled committees agree with /live"
    return "ok", ("hook before app.js's root, window and stems held to live.gen.js and /live's; "
                  + ("placed by both builders" if all(placed) else "awaiting PATCHES.md 11") + built)


# ---- the workflows ----------------------------------------------------------------
#
# .github/workflows/*.yml run on GitHub, in a public repository, with the
# keys to R2 and to Cloudflare Pages. Their logs are public. These read them
# as text, the way they are written -- jobs two spaces in under `jobs:`, a
# job's keys four, its steps six -- and fail on a file that stops being
# written that way, because a check that cannot find what it checks has
# checked nothing.

# (The folder is _SWITCHED.workflow_dir: the suite's switches are beside _suite_files.)
# The secrets the workflows may name, and nothing else: CLOUD_MOVE.md's list.
WORKFLOW_SECRETS = {"R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET",
                    "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "YOUTUBE_API_KEY",
                    "HEALTHCHECKS_URL", "HEALTHCHECKS_PUBLISH_URL",
                    # The approval check (18 October 2026; a held night alone since
                    # 7 November, nightly.APPROVAL_FILE): optional, and the person's
                    # to create.
                    "HEALTHCHECKS_WARN_URL"}


@check("workflows", "the workflow files parse, pin every action to a commit, and time out")
def _workflows_parse():
    """A workflow that does not parse fails on GitHub, at four in the morning, with
    nobody watching; an action named by a tag runs whatever the tag points at
    tonight. So each file parses -- with PyYAML where it is installed, and by a
    careful read of its indentation where it is not -- and every `uses:` names
    a commit. Every job has a timeout, and the jobs that run nightly.py run on
    a pinned Windows image: the General Court's database bridge is Windows
    PowerShell."""
    files = _workflows()
    if not files:
        return "skip", "no .github/workflows here"
    try:
        import yaml
    except ImportError:
        yaml = None
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert "\t" not in text, f"{f.name} holds a tab, which YAML does not allow for indentation"
        if yaml is not None:
            d = yaml.safe_load(text)
            on = d.get("on", d.get(True)) if isinstance(d, dict) else None   # YAML 1.1 reads `on` as True
            assert isinstance(d, dict) and isinstance(d.get("jobs"), dict) and d["jobs"] and \
                isinstance(on, dict) and on, f"{f.name} parses to no triggers or no jobs"
            for name, job in d["jobs"].items():
                assert isinstance(job, dict) and job.get("runs-on"), f"{f.name}: job {name} has no runs-on"
                assert all(isinstance(s, dict) and (("run" in s) != ("uses" in s))
                           for s in job.get("steps", [])), \
                    f"{f.name}: a step in {name} has both, or neither, of run and uses"
        else:
            for i, ln in enumerate(text.splitlines(), 1):
                if not ln.strip() or ln.lstrip().startswith("#"):
                    continue
                ind = len(ln) - len(ln.lstrip(" "))
                assert ind % 2 == 0, f"{f.name}:{i} is indented {ind} spaces"
            assert re.search(r"^on:\s*$", text, re.M) and re.search(r"^jobs:\s*$", text, re.M), \
                f"{f.name} has no on: or no jobs:"
        for m in re.finditer(r"^\s*(?:-\s+)?uses:\s*(\S+)", text, re.M):
            assert re.fullmatch(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}", m.group(1)), \
                f"{f.name}: {m.group(1)} is not pinned to a full commit"
        # PowerShell continues a line only when the backtick is its very last
        # character; one space after it ends the command there, and the next
        # line runs as a command of its own.
        bad = [i for i, ln in enumerate(text.splitlines(), 1) if re.search(r"`[ \t]+$", ln)]
        assert not bad, f"{f.name}: a line-continuation backtick is followed by a space, line(s) {bad}"
        jobs = _wf_jobs(text)
        assert jobs, f"{f.name}: no jobs where this check reads them (two spaces in, under jobs:)"
        for j, jl in jobs.items():
            code = _wf_code(jl)
            assert any(re.match(r"^    timeout-minutes:\s*\d+\s*$", ln) for ln in code), \
                f"{f.name}: job {j} has no timeout-minutes"
            ro = next((ln.split(":", 1)[1].strip() for ln in code if re.match(r"^    runs-on:", ln)), "")
            assert ro and "latest" not in ro, f"{f.name}: job {j} runs on {ro or 'nothing'}; pin the image"
            if any("nightly.py" in ln for ln in code):
                assert re.fullmatch(r"windows-\d{4}", ro), \
                    f"{f.name}: job {j} runs nightly.py on {ro}, not a pinned Windows image"
    return "ok", (f"{len(files)} workflow(s) " + ("parsed by PyYAML" if yaml else
                  "read by the text check, since PyYAML is not installed")
                  + "; every action pinned to a commit; every job with a timeout")


@check("workflows", "the workflows name only the listed secrets, hand each only to the step that "
       "uses it, and never print one")
def _workflows_secrets():
    """Run logs of a public repository are public. So the workflows name only the
    secrets CLOUD_MOVE.md lists; each reaches a step only as that step's own
    environment (never the job's, never an action's input, never interpolated
    into a script, where a quoting slip prints it); and no line writes out a
    variable that holds one, or dumps the environment. GitHub masks a secret
    it knows in its logs; this is for everything that masking does not see."""
    files = _workflows()
    if not files:
        return "skip", "no .github/workflows here"
    OUT = re.compile(r"\b(echo|printf|print|Write-Output|Write-Host|Write-Information|Out-Host|"
                     r"Out-File|Add-Content|Set-Content|Tee-Object)\b|>>|"
                     r"GITHUB_(OUTPUT|ENV|STEP_SUMMARY)", re.I)
    DUMP = re.compile(r"set\s+-x|Set-PSDebug|printenv|\benv\s*\||"
                      r"(Get-ChildItem|gci|dir|ls)\s+env:|export\s+-p", re.I)
    uses = Counter()
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        code = "\n".join(_wf_code(lines))
        assert not re.search(r"toJSON\(\s*secrets\s*\)", code, re.I), \
            f"{f.name} dumps every secret with toJSON(secrets)"
        assert not re.search(r"secrets\s*\[", code), f"{f.name} reads a secret by a computed name"
        bound = {"GH_TOKEN", "GITHUB_TOKEN"}
        for i, ln in enumerate(lines, 1):
            if ln.lstrip().startswith("#"):
                continue
            for m in re.finditer(r"secrets\.([A-Za-z_][A-Za-z0-9_]*)", ln):
                uses[m.group(1)] += 1
                assert m.group(1) in WORKFLOW_SECRETS, (
                    f"{f.name}:{i} names secrets.{m.group(1)}, which is not one of "
                    f"{', '.join(sorted(WORKFLOW_SECRETS))}")
                e = re.match(r"^ {10}([A-Z][A-Z0-9_]*): \$\{\{ secrets\.[A-Z0-9_]+ \}\}\s*$", ln)
                parent = next((p for p in reversed(lines[:i - 1]) if re.match(r"^ {8}\S", p)), "")
                assert e and parent.strip() == "env:", (
                    f"{f.name}:{i}: a secret may reach a step only as that step's own env "
                    "entry, NAME: ${{ secrets.NAME }}")
                bound.add(e.group(1))
        for i, ln in enumerate(lines, 1):
            if ln.lstrip().startswith("#"):
                continue
            assert not DUMP.search(ln), f"{f.name}:{i} would print the environment, secrets and all"
            held = [n for n in bound if re.search(r"(\$env:|\$\{?|%)" + n + r"\b", ln)]
            assert not (held and OUT.search(ln)), \
                f"{f.name}:{i} writes out {', '.join(held)}, which holds a secret"
    assert uses, "no workflow names any secret, which cannot be right for the nightly"
    return "ok", (f"{sum(uses.values())} uses of {len(uses)} secrets, every one listed, each a "
                  "step's own env entry, none written out")


@check("workflows", "the patch notes reach the run's page through the environment alone: the "
       "Notes box is read once, never into a script, its step runs on a run by hand only, escapes "
       "&, < and > in each subject, and cannot fail the night")
def _workflows_patch_notes():
    """The owner, 13 November 2026: "list the major patch notes within the
    github actions page so I know what pages to specifically look at for
    comparison with the live site". nightly.yml takes them in a Notes box on a
    run by hand, and its step "The patch notes" writes them to the run's page
    with the commits merged since the live site's. Whatever is typed in the
    box is text, never code: GitHub writes ${{ inputs.notes }} into whatever
    line holds it before any shell reads it, so it is read in exactly one
    place, the step's NOTES environment entry, and no script line names it.
    The step ends by exiting 0, inside a try, so a page it cannot write never
    stops a night; and only a run by hand has a box to read, so the step does
    not run on the night's timer (which dispatches with timer true and no
    notes) or on the clock's, read as GitHub reads the line. Each commit
    subject has &, < and > escaped before it goes into the page's Markdown,
    so a <word> in one is shown rather than taken for a tag."""
    f = Path(".github/workflows/nightly.yml")
    if not f.is_file():
        return "skip", "no nightly.yml here"
    text = _source(f)
    lines = text.splitlines()
    code = _wf_code(lines)
    uses = [ln.strip() for ln in code if "inputs.notes" in ln]
    assert uses == ["NOTES: ${{ inputs.notes }}"], (
        f"the Notes box is read {len(uses)} times, or outside the step's environment: {uses}")
    on = _wf_block(lines, "on")
    spec = []
    for i, ln in enumerate(on):
        if ln.strip() == "notes:":
            for nxt in on[i + 1:]:
                if not nxt.startswith("        ") or not nxt.strip():
                    break
                spec.append(nxt.strip())
            break
    assert "type: string" in spec and 'default: ""' in spec and "required: false" in spec, (
        f"the Notes box is {spec}: an optional string, empty unless typed")
    jobs = _wf_jobs(text)
    steps = [st for st in _wf_steps(_wf_code(jobs.get("night", [])))
             if any(ln.strip() == "- name: The patch notes" for ln in st)]
    assert len(steps) == 1, f"the night has {len(steps)} patch notes steps, not one"
    st = "\n".join(steps[0])
    # What the line does, not what it says: evaluated as GitHub evaluates it
    # for every kind of night (WF_RUNS), the step runs exactly on a run by
    # hand that is not the timer's. The night's timer dispatches too, with
    # timer "true" and no notes, and a box of a dispatch may arrive as a
    # boolean or as a string.
    cond = next((ln.strip() for ln in steps[0] if ln.strip().startswith("if:")), "")
    expr = cond[3:].strip()
    assert expr, "the patch notes step has no if"
    seen = 0
    for event, ref, boxes, _dry, title in WF_RUNS["nightly.yml"]:
        forms = [boxes]
        if event == "workflow_dispatch":
            forms.append({k: str(v).lower() for k, v in boxes.items()})
        for bx in forms:
            runs = bool(_gh_eval(expr, _wf_run_ctx(event, ref, bx)))
            want = event == "workflow_dispatch" and not boxes.get("timer")
            assert runs == want, (
                f"the patch notes step {'runs' if runs else 'does not run'} on {title} "
                f"({'strings' if bx is not boxes else 'booleans'}) and should "
                f"{'' if want else 'not '}: {cond}")
            seen += 1
    # A subject is text, not Markdown: <name> would be read as a tag and lost.
    # One line on $log, after the git log it filters and before the 40 are kept,
    # & first so that the entities written for < and > are not escaped again.
    esc = ("$log = @($log | ForEach-Object { $_ -replace '&','&amp;' "
           "-replace '<','&lt;' -replace '>','&gt;' })")
    sl = [ln.strip() for ln in steps[0]]
    gi = next((n for n, ln in enumerate(sl) if "git log --first-parent" in ln), -1)
    ei = [n for n, ln in enumerate(sl) if ln == esc]
    si = next((n for n, ln in enumerate(sl) if "Select-Object -First 40" in ln), -1)
    assert gi >= 0 and si >= 0 and len(ei) == 1 and gi < ei[0] < si, (
        "commit subjects go into the run page without &, < and > escaped on $log "
        "between the git log line and the 40 kept")
    run = st.split("run: |", 1)[1] if "run: |" in st else ""
    assert run and "${{" not in run, "the patch notes step's script has an expression GitHub would write into it"
    assert "$env:NOTES" in run and "GITHUB_STEP_SUMMARY" in run, "the patch notes do not reach the run's page"
    assert run.strip().endswith("exit 0") and "try {" in run and "} catch {" in run, (
        "the patch notes step can fail the night")
    return "ok", (f"one Notes box, read through NOTES alone; its step runs on a run by hand and on none "
                  f"of the timer's or the clock's ({seen} readings of 9 kinds of run, boxes as booleans "
                  "and strings), escapes & < > in each subject, writes the run's page and cannot fail the night")


@check("workflows", "the night takes the whole history only on the runs whose patch notes read it, "
       "the jobs whose checks read it keep it, and every job that installs requirements.txt keeps "
       "pip's downloads under a key of every pin it installs")
def _workflows_checkout_and_pip_cache():
    """THE HISTORY ONLY WHERE IT IS READ and THE PIP CACHE (nightly.yml; the refactor's B16).
    The night job's checkout depth, read as GitHub reads it for every kind of night (WF_RUNS,
    boxes as booleans and strings), is "0" -- every commit, branch and tag -- exactly on the runs
    its patch notes step runs on, the one step of the job that reads the history, and "1" on the
    rest; no other step of the job names git log, a remote branch or a tag. The code checks' job
    and the weekly, which run preflight --code and its readers of the history (every commit's
    address, the Clerks' list on any ref, dev's registers), keep fetch-depth 0. And every
    setup-python of a job that installs requirements.txt says cache: pip, with a
    cache-dependency-path naming requirements.txt, and its own workflow file where the job pins a
    package in its own pip line."""
    files = {f.name: f for f in _workflows()}
    if "nightly.yml" not in files:
        return "skip", "no nightly.yml here"
    jobs = _wf_jobs(_source(files["nightly.yml"]))
    steps = _wf_steps(_wf_code(jobs.get("night", [])))

    def named(name):
        got = [st for st in steps if any(ln.strip() == f"- name: {name}" for ln in st)]
        assert len(got) == 1, f"the night has {len(got)} steps named {name!r}"
        return got[0]
    out = named("Check out main")
    depth = next((ln.split(":", 1)[1].strip() for ln in out if ln.strip().startswith("fetch-depth:")),
                 "")
    assert depth.startswith("${{"), f"the night's checkout depth is {depth!r}, not read per run"
    notes_if = next(ln.strip()[3:].strip() for ln in named("The patch notes")
                    if ln.strip().startswith("if:"))
    seen = 0
    for event, ref, boxes, _dry, title in WF_RUNS["nightly.yml"]:
        forms = [boxes] + ([{k: str(v).lower() for k, v in boxes.items()}]
                           if event == "workflow_dispatch" else [])
        for bx in forms:
            ctx = _wf_run_ctx(event, ref, bx)
            got, notes = str(_gh_eval(depth, ctx)), bool(_gh_eval(notes_if, ctx))
            assert got == ("0" if notes else "1"), (
                f"on {title} the night checks out at depth {got!r}, where its patch notes "
                f"{'run' if notes else 'do not run'}")
            seen += 1
    for st in steps:
        if st is named("The patch notes"):
            continue
        text = "\n".join(st)
        assert not re.search(r"\bgit (log|rev-list|merge-base|describe|fetch)\b|origin/|refs/tags",
                             text), f"a step of the night reads the history: {st[0].strip()}"
    keep = {"nightly.yml:checks": jobs.get("checks", [])}
    if "weekly.yml" in files:
        keep["weekly.yml:weekly"] = _wf_jobs(_source(files["weekly.yml"])).get("weekly", [])
    for where, jl in keep.items():
        assert any(re.fullmatch(r"\s*fetch-depth: 0\s*", ln) for ln in _wf_code(jl)), (
            f"{where} runs preflight --code, whose checks read the whole history, without it")
    cached = []
    for f in files.values():
        for j, jl in _wf_jobs(_source(f)).items():
            code = _wf_code(jl)
            body = "\n".join(code)
            if "-r requirements.txt" not in body:
                continue
            for st in _wf_steps(code):
                if not any("actions/setup-python@" in ln for ln in st):
                    continue
                with_ = [ln.strip() for ln in st]
                assert "cache: pip" in with_, f"{f.name}:{j}'s setup-python keeps no pip cache"
                at = with_.index(next(ln for ln in with_ if ln.startswith("cache-dependency-path:")))
                named_paths = [with_[at].split(":", 1)[1].strip(" |")] + \
                    [ln for ln in with_[at + 1:] if ln and ":" not in ln]
                named_paths = [x for x in named_paths if x]
                assert "requirements.txt" in named_paths, (
                    f"{f.name}:{j}'s pip cache is not keyed by requirements.txt: {named_paths}")
                # A pin of the job's own: a line of its pip install that begins with one.
                if re.search(r"^\s+[\w.-]+==\d", body, re.M):
                    assert f".github/workflows/{f.name}" in named_paths, (
                        f"{f.name}:{j} pins a package in its own pip line and its pip cache is not "
                        f"keyed by {f.name}: {named_paths}")
                cached.append(f"{f.name}:{j}")
    assert {"nightly.yml:night", "nightly.yml:checks"} <= set(cached), cached
    return "ok", (f"depth 0 exactly where the patch notes run ({seen} readings of "
                  f"{len(WF_RUNS['nightly.yml'])} kinds of night), 1 elsewhere, and no other step "
                  f"of the night reads the history; {', '.join(keep)} keep it all; pip cached and "
                  f"keyed by every pin in {', '.join(sorted(cached))}")


@check("workflows", "each workflow's token reads the repository and no more, and nothing a "
       "stranger does can start one")
def _workflows_permissions():
    """The token GitHub gives a run can do whatever its permissions say, and a
    workflow that names none gets the repository's default. So each workflow
    says `contents: read` at the top and nothing more; a job asks for more only
    to re-enable its own schedule (`actions: write`, and then it checks out
    nothing and runs nothing else), or to list the night's own runs
    (`actions: read`, whether the night's timer has started tonight's night),
    or, in the night, this run's own jobs (`actions: read`, one step, for what
    the code checks beside it came to).
    And no workflow is started by a pull
    request, a comment or another workflow: a fork's code must never run with
    these keys in reach."""
    files = _workflows()
    if not files:
        return "skip", "no .github/workflows here"
    ALLOWED = {"workflow_dispatch", "schedule"}
    for f in files:
        lines = f.read_text(encoding="utf-8").splitlines()
        on = _wf_block(lines, "on")
        assert on, f"{f.name} has no top-level on:"
        started = {m.group(1) for ln in on[1:] if (m := re.match(r"^  ([a-z_]+):", ln))}
        assert started and started <= ALLOWED, (
            f"{f.name} is started by {', '.join(sorted(started - ALLOWED)) or 'nothing'}; "
            "only workflow_dispatch and schedule, never a pull request")
        top = _wf_block(lines, "permissions")
        assert top, f"{f.name} sets no top-level permissions, so its token gets the repository's default"
        grants = [ln.strip() for ln in _wf_code(top[1:]) if ln.strip()]
        assert grants == ["contents: read"] or top[0].strip() == "permissions: {}", \
            f"{f.name}'s token asks for {grants or top[0].strip()}; contents: read is all it needs"
        text = "\n".join(_wf_code(lines))
        assert not re.search(r"write-all|read-all|id-token", text), \
            f"{f.name} asks for write-all, read-all or id-token"
        for j, jl in _wf_jobs("\n".join(lines)).items():
            for k, ln in enumerate(jl):
                if not re.match(r"^    permissions:", ln):
                    continue
                asks = []
                for nxt in jl[k + 1:]:
                    if re.match(r"^      \S", nxt):
                        asks.append(nxt.strip())
                    elif nxt.strip() and not nxt.startswith("      "):
                        break
                bad = [x for x in asks if x not in ("contents: read", "actions: write", "actions: read")]
                assert not bad, f"{f.name}: job {j} asks for {', '.join(bad)}"
                # actions: read ONLY TO SEE WHETHER THE TIMER STARTED TONIGHT'S
                # NIGHT (23 October 2026, nightly.yml's job "started"): it lists
                # this workflow's own runs, checks out nothing and runs nothing.
                # AND IN THE NIGHT, TO READ WHAT THE CODE CHECKS CAME TO (16
                # November 2026, nightly.CHECKS_JOB): one step alone is given
                # the token, and it runs nightly.py --checks-result, which GETs
                # this run's own jobs and nothing else; no step runs gh
                # (_workflows_code_checks_beside holds the rest).
                if "actions: read" in asks:
                    body = "\n".join(_wf_code(jl))
                    if "nightly.py --runner --checks-result" in body:
                        given = [st for st in _wf_steps(_wf_code(jl)) if "github.token" in "\n".join(st)]
                        assert len(given) == 1 and \
                            "python nightly.py --runner --checks-result" in "\n".join(given[0]) and \
                            not re.search(r"^\s+gh\s", body, re.M) and asks == ["contents: read", "actions: read"], \
                            f"{f.name}: job {j} holds actions: read and does more than read the code checks' result"
                        continue
                    assert "uses:" not in body and "gh api -X GET" in body \
                        and "actions/workflows/nightly.yml/runs" in body \
                        and not re.search(r"--method|-X (?:POST|PUT|PATCH|DELETE)", body), \
                        f"{f.name}: job {j} holds actions: read and does more than list the night's runs"
                if "actions: write" in asks:
                    body = "\n".join(_wf_code(jl))
                    assert "uses:" not in body and "gh api" in body and "/enable" in body \
                        and "--method PUT" in body, \
                        f"{f.name}: job {j} holds actions: write and does more than re-enable its schedule"
    return "ok", (f"{len(files)} workflow(s): contents: read, actions: write only to re-enable a "
                  "schedule and actions: read only to list the night's runs and, in the night, "
                  "its own jobs for the code checks' result, started only by hand or by the clock")


@check("workflows", "the livestream step runs before the night, only when it fetches, and fails "
       "the night when it fails")
def _workflows_livestreams():
    """livestreams.py asks YouTube, before the build, which reads what it adds.
    It is allowed to carry on past its own failure, so that a night whose
    YouTube key is missing still takes the General Court's files, which cannot
    be taken later -- and so its failure reaches the night only through
    --close, which is told its outcome. Drop that and a night with no
    livestreams for a month is green every morning. yt-dlp, which it fetches
    captions with, is installed pinned, or the step exits 3 every night; and
    the step has a time limit of its own (_livestream_step_limits)."""
    files = _workflows()
    if not files:
        return "skip", "no .github/workflows here"
    found, limits = [], []
    for f in files:
        for j, jl in _wf_jobs(f.read_text(encoding="utf-8")).items():
            code = _wf_code(jl)
            steps = _wf_steps(code)
            at = [k for k, st in enumerate(steps) if any("livestreams.py" in ln for ln in st
                                                         if "python" in ln)]
            if not at:
                continue
            st = "\n".join(steps[at[0]])
            sid = re.search(r"^        id:\s*(\S+)", st, re.M)
            assert sid and re.search(r"^        continue-on-error: true\s*$", st, re.M) and \
                re.search(r"^        if: env\.FETCH == 'true'\s*$", st, re.M), \
                f"{f.name}: job {j}'s livestream step lacks an id, continue-on-error, or its fetch-only if"
            night = [k for k, s in enumerate(steps)
                     if any("nightly.py @flags" in ln for ln in s)]
            assert night and at[0] < night[0], f"{f.name}: job {j} runs the livestreams after the night"
            body = "\n".join(code)
            assert f"livestreams=${{{{ steps.{sid.group(1)}.outcome }}}}" in body, \
                f"{f.name}: job {j} does not tell --close the livestream step's outcome"
            assert re.search(r"\byt-dlp==\d", body), \
                f"{f.name}: job {j} runs livestreams.py and installs no pinned yt-dlp"
            limits.append(_livestream_step_limits(f.name, j, st, body))
            found.append(f"{f.name}:{j}")
    assert found, "no workflow runs livestreams.py, which the nightly is meant to"
    return "ok", (f"{', '.join(found)}: before the night, fetch nights only, outcome to --close, "
                  f"yt-dlp and its solver pinned; {'; '.join(limits)}")


def _livestream_step_limits(name, job, step, body):
    """The livestream step's own time limit, and what it must hold (10
    October 2026, when the night took the captions over from the laptop):

      - the longest run fits it: livestreams.BUDGET minutes of asking, and
        LAST_ASK_MINUTES for the ask that starts just inside that -- its
        pause, both tracks at --timeout and the pause between -- with two
        minutes for the listing; and LAST_ASK_MINUTES is that sum, not a
        guess. Without a limit a hang inside one yt-dlp call ate the night;
        with one too short, the step is killed in an ordinary long run;
      - a scheduled night that spends all of it still asks the General Court
        inside refusal.NIGHT_WINDOWS, started an hour late, and fits the
        job's own timeout-minutes with an hour for the build (the allowances
        of the night's own check: five minutes a try at the export, ten at
        the database);
      - yt-dlp's challenge solver, yt-dlp-ejs, is installed pinned beside
        it, at the version yt-dlp names in its own metadata where the pinned
        yt-dlp is the one installed here."""
    import livestreams as L
    import nightly as NI
    import refusal
    m = re.search(r"^        timeout-minutes:\s*(\d+)\s*$", step, re.M)
    assert m, f"{name}: job {job}'s livestream step has no timeout-minutes of its own"
    limit = int(m.group(1))
    worst = (2 * (L.DELAY + L.JITTER) + len(L.CAPTION_TRACKS) * L.TIMEOUT) / 60
    assert L.LAST_ASK_MINUTES >= worst, \
        f"livestreams.LAST_ASK_MINUTES is {L.LAST_ASK_MINUTES}; the last ask can take {worst:g}"
    need = L.BUDGET + L.LAST_ASK_MINUTES + 2
    assert need <= limit <= 90, (
        f"{name}: the livestream step allows {limit} minutes; its longest run is {need:g} "
        "and it may not take more than an hour and a half of the night")
    TRY, DATABASE, REST, LATE = 5, 10, 60, 60
    asking = NI.DB_AFTER_TRIES * TRY + DATABASE + NI.TRIES_AFTER_DB * (NI.EMPTY_WAIT + TRY)
    wf = _paths.locate(".github/workflows/" + name).read_text(encoding="utf-8")
    cron = re.search(r'^\s+- cron: "(\d+) (\d+) \* \* \*"', wf, re.M)
    jobmax = re.search(r"^  night:\n(?:(?!  \S).*\n)*?    timeout-minutes: (\d+)", wf, re.M)
    if cron and jobmax:
        starts = int(cron.group(2)) * 60 + int(cron.group(1))
        closes = next(w[2] for w in refusal.NIGHT_WINDOWS if w[0] is None)
        assert starts + LATE + limit + asking <= closes[0] * 60 + closes[1], (
            f"{name}: a night started {LATE} minutes late that spends {limit} on captions asks "
            f"the General Court until {starts + LATE + limit + asking} minutes past midnight "
            f"UTC, past refusal.NIGHT_WINDOWS' {closes}")
        assert limit + asking + REST <= int(jobmax.group(1)), (
            f"{name}: {limit} minutes of captions, {asking} of asking and {REST} for the rest "
            f"is past the night job's {jobmax.group(1)}")
    yt = re.search(r"\byt-dlp==([\w.]+)", body)
    ejs = re.search(r"\b" + re.escape(L.SOLVER) + r"==([\w.]+)", body)
    assert ejs, f"{name}: job {job} installs no pinned {L.SOLVER}, which --js-runtimes node needs"
    import importlib.metadata as md
    try:
        here = md.version("yt-dlp")
        wants = [re.search(r"==([\w.]+)", r).group(1) for r in md.requires("yt-dlp") or []
                 if r.startswith(L.SOLVER + "==")]
    except md.PackageNotFoundError:
        here, wants = None, []

    def norm(v):
        return ".".join(str(int(x)) if x.isdigit() else x for x in str(v).split("."))
    if here and yt and norm(here) == norm(yt.group(1)) and wants:
        assert ejs.group(1) in wants, (
            f"{name}: yt-dlp {yt.group(1)} names {L.SOLVER} {wants[0]} in its own metadata, and "
            f"the workflow pins {ejs.group(1)}")
    return (f"its own limit {limit} min for a longest run of {need:g}, inside the night window "
            f"and the job; {L.SOLVER} {ejs.group(1)}")


@check("workflows", "the built site reaches the publish job through the private bucket, never as "
       "a GitHub artifact")
def _workflows_site_handoff():
    """The night builds the site, and the publish job, which waits for the
    person's approval on another machine, deploys it. A GitHub artifact or
    cache of a public repository can be downloaded by anyone signed in to
    GitHub, and the built site carries the licensed logo, which is kept out of
    the repository and its licence. So no workflow uses either, and the site
    goes through the private bucket as one archive: cloud.py site-up in the
    job that builds it, site-down in the job that deploys production, both
    named by the run's own id so that a night can only ever publish the site
    it built."""
    files = _workflows()
    if not files:
        return "skip", "no .github/workflows here"
    up, down = [], []
    for f in files:
        text = f.read_text(encoding="utf-8")
        code = "\n".join(_wf_code(text.splitlines()))
        m = re.search(r"uses:\s*actions/(upload-artifact|download-artifact|cache)@", code)
        assert not m, (f"{f.name} uses actions/{m.group(1)}, which anyone signed in to GitHub "
                       "can download from a public repository")
        for j, jl in _wf_jobs(text).items():
            body = "\n".join(_wf_code(jl))
            for verb, into in (("site-up", up), ("site-down", down)):
                if f"cloud.py {verb}" not in body:
                    continue
                if f.name == "preview.yml":
                    # THE QUICK PREVIEW (11 November 2026) reads the newest real night's
                    # site, to put the browser's files into a copy of it. It publishes
                    # nothing and sends nothing: site-down only, --latest, and no
                    # site-up anywhere in the file.
                    assert verb == "site-down" and re.search(
                        r"python src/ops/cloud\.py site-down --latest\s*$", body, re.M) and \
                        "--run" not in body and "--deploy-to" not in body, (
                        f"{f.name}: job {j} does more with the night's site than read the "
                        "newest one for the quick preview")
                    continue
                assert re.search(rf"python src/ops/cloud\.py {verb} --run \$env:RUN_ID\s*$", body, re.M) \
                    and "RUN_ID: ${{ github.run_id }}" in body, (
                        f"{f.name}: job {j} runs cloud.py {verb} under a name that is not "
                        "the run's own id")
                into.append(f"{f.name}:{j}")
            if f"cloud.py site-down" in body and f.name != "preview.yml":
                assert "--deploy-to production" in body, \
                    f"{f.name}: job {j} takes a night's site down and does not deploy production"
    assert up and down, (f"the site is sent by {up or 'no job'} and taken down by "
                         f"{down or 'no job'}; the publish job would have nothing to deploy")
    return "ok", (f"sent by {', '.join(up)} and taken down by {', '.join(down)} under the run's "
                  "id; no artifact or cache in any workflow")


# The workflows whose every kind of run (WF_RUNS) Healthchecks is held to:
# every workflow that names HEALTHCHECKS_URL, which the check holds too.
WF_PINGS = ("nightly.yml", "weekly.yml")


# The first thing a Healthchecks step's script does: compare the ref with
# main's exactly, which no if can (MAIN IS MAIN_REF EXACTLY, in nightly.py).
HC_REF_GUARD = "          if ($env:GITHUB_REF -cne 'refs/heads/main') {"


@check("workflows", "Healthchecks hears from a scheduled night and a real run by hand of main, "
       "and never from a dry run, by its box or its branch")
def _workflows_healthchecks():
    """HEALTHCHECKS IS THE DEAD-MAN'S SWITCH FOR A NIGHT THAT NEVER RAN (7
    October 2026). Every nightly run pinged it -- /start, then its ending --
    a dry run on dev included; so a dry run that succeeded on a day the
    scheduled night failed to start would have told Healthchecks a night had
    run, and hidden that one. Now each step that names HEALTHCHECKS_URL is
    evaluated, as GitHub would, for every kind of run in WF_RUNS, with the
    job going well and with it failed (a step whose if names no status
    function is success() and its if, as GitHub reads it): it pings for no
    dry run at all, by the box or by the branch, and for every run that is
    not one -- a scheduled night, a run by hand of main with Dry run
    unticked -- in the outcome it is there for, as before. The weekly's ping,
    which tells Healthchecks only of a week that failed, likewise: never for
    a week off main. Every workflow that names HEALTHCHECKS_URL is held. And
    since no if can tell refs/heads/Main from main -- GitHub compares strings
    without case, and nightly.py does not (the review of 7 October 2026) --
    each such step's script compares the ref exactly before it pings
    (HC_REF_GUARD)."""
    files = {f.name: f for f in _workflows()}
    if not files:
        return "skip", "no .github/workflows here"
    naming = sorted(n for n, f in files.items() if "secrets.HEALTHCHECKS_URL" in
                    "\n".join(_wf_code(f.read_text(encoding="utf-8").splitlines())))
    assert set(naming) <= set(WF_PINGS), \
        f"{sorted(set(naming) - set(WF_PINGS))} ping Healthchecks and are not held to the dry-run rule"
    held = []
    for name in WF_PINGS:
        assert name in files, f"{name} is not among the workflows"
        lines = files[name].read_text(encoding="utf-8").splitlines()
        dry_line = _wf_value(lines, "DRY_RUN")
        assert dry_line, f"{name} sets no DRY_RUN in its top-level env, so no step can tell a dry run"
        # ... and nowhere else: a job's or step's own, in any style, would be
        # what these steps' ifs read, not the line evaluated below.
        sets = _wf_dry_run_sets("\n".join(lines))
        assert len(sets) == 1, \
            f"{name} sets DRY_RUN outside its top-level env, which its pings would read: {sets}"
        pings = []
        for jl in _wf_jobs("\n".join(lines)).values():
            for st in _wf_steps(_wf_code(jl)):
                s = "\n".join(st)
                if "secrets.HEALTHCHECKS_URL" not in s:
                    continue
                m = re.search(r"^        if:\s*(.+?)\s*$", s, re.M)
                cond = _gh_unwrap(m.group(1)) if m else "true"
                if not re.search(r"\b(?:always|success|failure)\(\)", cond):
                    cond = f"success() && ({cond})"
                step = re.sub(r"^\s*- name:\s*", "", st[0]).strip()
                # MAIN IS MAIN_REF EXACTLY (the review of 7 October 2026): the
                # if cannot tell refs/heads/Main from main, so the script
                # compares the ref itself, exactly, before it pings.
                guard = [i for i, ln in enumerate(st) if ln.rstrip() == HC_REF_GUARD]
                curl = [i for i, ln in enumerate(st) if "curl" in ln]
                assert guard and curl and guard[0] < curl[0] and \
                    any(ln.strip() == "exit 0" for ln in st[guard[0] + 1:guard[0] + 4]), (
                        f"{name}: {step!r} pings Healthchecks without first comparing the ref "
                        "with main's exactly, so a branch named Main, which its if takes for "
                        "main, pings for a run nightly.py calls a dry run")
                pings.append((step, cond))
        assert pings, f"{name} pings Healthchecks from no step"
        wrong = []
        for event, ref, boxes, dry, _title in WF_RUNS[name]:
            ctx = _wf_run_ctx(event, ref, boxes)
            ctx["env.DRY_RUN"] = _gh_render(dry_line, ctx)
            run = f"{event} of {ref}, {boxes or 'no boxes'}"
            for step, cond in pings:
                when = [failed for failed in (False, True)
                        if _gh_eval(cond, dict(ctx, **{"success()": not failed,
                                                       "failure()": failed}))]
                if dry and when:
                    wrong.append(f"{step!r} pings for a dry run ({run})")
                elif not dry and not when:
                    wrong.append(f"{step!r} never pings for a run that is not a dry run ({run})")
        assert not wrong, f"{name}: " + "; ".join(wrong)
        held.append(f"{name} ({len(pings)} step{'s' if len(pings) > 1 else ''})")
    return "ok", (f"{', '.join(held)}: each ping evaluated for every kind of run; none for a dry "
                  "run, by the box or by the branch, and each for every run that is not one")


# ONE DRY RUN AT A TIME (the review of 7 October 2026): the group every dry
# run waits in, at its workflow's level, before its job joins gc-night.
DRY_RUNS_GROUP = "dry-runs"


@check("workflows", "a dry run, by its box or its branch, waits behind any other dry run before "
       "its job joins gc-night, so a second dry run cannot cancel a scheduled night waiting "
       "there, and a run that is not a dry run never waits for one")
def _workflows_dry_runs_wait():
    """THE REVIEW OF 7 OCTOBER 2026. Every night and weekly job waits in the
    gc-night group (_workflows_production), and GitHub keeps one waiting run
    per group: a run queued while another waits cancels the one waiting. A
    dry run held gc-night, the scheduled night queued behind it, and a second
    dry run, started by hand, cancelled the scheduled night -- and every run
    of dev is a dry run now, which may be started while a night waits. So
    each workflow with a gc-night job puts every dry run first in a group of
    the workflow's own level, DRY_RUNS_GROUP, shared by both workflows and
    never cancelling, from the same words as its DRY_RUN; and a run that is
    not a dry run gets a group of its own, its run's id, so the scheduled
    night and a real run of main never wait there. Evaluated for every kind
    of run in WF_RUNS, as GitHub would. (A dry run started while a real run of
    main holds gc-night can still cancel a night waiting behind that: GitHub
    has no queue longer than one, and the dead-man's switch reports it.)"""
    files = {f.name: f for f in _workflows()}
    if not files:
        return "skip", "no .github/workflows here"
    gated = sorted(n for n, f in files.items()
                   if re.search(r"^      group: gc-night\s*$", f.read_text(encoding="utf-8"), re.M))
    assert gated and set(gated) <= set(WF_RUNS), \
        f"{sorted(set(gated) - set(WF_RUNS))} wait in gc-night and are not held to this"
    held = []
    for name in gated:
        lines = files[name].read_text(encoding="utf-8").splitlines()
        block = _wf_code(_wf_block(lines, "concurrency"))
        group = next((m.group(1) for ln in block
                      for m in [re.match(r"^  group:\s*(.+?)\s*$", ln)] if m), None)
        assert group and "  cancel-in-progress: false" in block, (
            f"{name} puts no dry run in line behind the others before gc-night, or cancels the "
            "one running")
        dry_line = _wf_value(lines, "DRY_RUN")
        wrong = []
        for event, ref, boxes, dry, _title in WF_RUNS[name]:
            # Each run by hand with its boxes as booleans, and as strings
            # (nightly.yml: A BOX MAY ARRIVE AS A STRING, 25 October 2026).
            for bx in [boxes] + ([{k: (str(v).lower() if isinstance(v, bool) else v)
                                   for k, v in boxes.items()}]
                                 if event == "workflow_dispatch" and boxes else []):
                ctx = _wf_run_ctx(event, ref, bx)
                ids = {_gh_render(group, dict(ctx, **{"github.run_id": rid}))
                       for rid in ("101", "102")}
                said = _gh_render(dry_line, ctx) == "true"
                if dry != said or (dry and ids != {DRY_RUNS_GROUP}) or \
                        (not dry and (len(ids) != 2 or DRY_RUNS_GROUP in ids or "gc-night" in ids)):
                    wrong.append(f"{event} of {ref} with {bx or 'no boxes'}: waits in "
                                 f"{sorted(ids)}, and is {'a' if dry else 'not a'} dry run")
        assert not wrong, f"{name}: " + "; ".join(wrong)
        held.append(name)
    return "ok", (f"{', '.join(held)}: every dry run waits in {DRY_RUNS_GROUP!r}, one at a time, "
                  "before gc-night, and every other run in a group of its own")


@check("workflows", "a job after one that can be skipped says always() or !cancelled() in its if, "
                    "so a skipped job before it does not skip it too")
def _workflows_skipped_ancestors():
    """A RUN THE SCHEDULE DID NOT START COULD NOT PUBLISH (25 October 2026).
    nightly.yml's "started" runs only for a scheduled run and is skipped for
    every other: the timer's, and every run by hand. GitHub skips a job whose
    if names no status function when any job before it, however far back, was
    skipped. The night said !cancelled(); the publish job, two jobs after
    "started", did not, so from 23 October only a scheduled run's night could
    be published, and the timer's first night (run 129) and a run by hand
    (run 132) built sites fit for production that nothing published.

    So in every workflow, a job with a job that has an if anywhere before it
    says always() or !cancelled() in its own if. Run on nightly.yml as it
    stood, this fails on the publish job."""
    if not _SWITCHED.workflow_dir.exists():
        return "skip", "no .github/workflows here"
    bad, held = [], []
    for f in sorted(_SWITCHED.workflow_dir.glob("*.yml")):
        heads = {j: _wf_job_heads(jl) for j, jl in _wf_jobs(f.read_text(encoding="utf-8")).items()}

        def before(j, seen):
            for n in heads.get(j, ([], ""))[0]:
                if n not in seen:
                    seen.add(n)
                    before(n, seen)
            return seen
        for j, (_need, cond) in heads.items():
            skippable = sorted(a for a in before(j, set()) if heads.get(a, ([], ""))[1])
            if skippable and not re.search(r"always\(\)|!\s*cancelled\(\)", cond):
                bad.append(f"{f.name}: job {j} comes after {', '.join(skippable)}, which can be "
                           f"skipped, and its if ({cond or 'none'}) names no always() or "
                           "!cancelled(): a skipped job before it would skip it too")
            elif skippable:
                held.append(f"{f.name}:{j}")
    assert not bad, "\n  ".join(bad)
    return "ok", (f"{len(held)} jobs after one that can be skipped, each with a status function: "
                  + ", ".join(held))
