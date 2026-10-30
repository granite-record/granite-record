#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-09.33
"""
One refusal stops the fetch lane, not just the run that was refused.

EVERY FETCHER, BOTH HALVES. Every script that asks gc.nh.gov calls check()
straight after its arguments (preflight's _every_fetcher_checks_refusal), and
since 7 October 2026 every one that calls check() also calls note() on a
refusal it meets -- one, a second dropped connection, or the firewall's block
page served as a 200, as classify() reads them -- and stops with status 2
(_every_fetcher_notes_refusal, which reads that from the code and drives the
fifteen that did not on fake answers, fourteen since fetch_testimony.py was
retired). build_all.py and watchers/gc_lane.py
honour it too, which is what makes the scheduled path safe.

    import refusal
    refusal.check("fetch_archive_docket")      # exits if the last run was refused
    refusal.note("calendars", "HTTPError: 403")  # when a run stops on one

WHY THIS EXISTS

A calendar drain was answered with two HTTP 403s and stopped itself, correctly.
Fifty-four seconds later a chained run started asking the same address for
another docket, because it was waiting on the lock and the lock had cleared: it
had no way to tell a run that finished from a run that was refused. Each
fetcher had a stop-loss and honoured it; what was missing was that a refusal is
a fact about the ADDRESS, so it has to outlive the process that discovered it.

HOW IT BEHAVES

note() writes archive/refused.json. check() reads it and stops the caller dead
while it is less than QUIET hours old, printing when the refusal came, what it
said, and how to clear it. The file is small, plain and meant to be read.

AT ANY AGE, FOR ONE GITHUB'S MACHINE MET (29 October 2026, design_final
2.10). A record GitHub's machine wrote that says what kind it was (any_age)
stops check() for as long as it is on file, not for QUIET hours: GitHub's
night may be testing it itself, and only the bucket's copy is lifted or
cleared there, so a copy here a day old that let a hand fetch through would
be a second machine asking beside the test. Every other record -- one met
here, and every one that says nothing of its kind -- keeps its QUIET hours.

Clearing it is a person's decision, deliberately: `python3 refusal.py --clear`,
after netcheck.py has said what kind of refusal it was. Nothing clears a
person's refusal automatically, because "wait a bit and try again" is the
behaviour that earns a longer block. One kind is the night's to test, with
one request at a time at most: THE NIGHT'S KNOCK, below.

WHAT KIND IT WAS (29 October 2026). The record says what it was, so that a
reader can tell a dropped connection from the address saying no: `kind` is
"dropped" (two dropped connections or timeouts), "unavailable" (an HTTP 503
whose body is not the firewall's page, unavailable() below, with the
server's Retry-After as `retry_after` when it named one) or "refused"
(everything else that ends a run: a 403, a 429, the block page, a
Retry-After on any other answer). Beside it: `machine` ("github" on GitHub's
machine, else "laptop"), `ref` (GITHUB_REF), `dry` (a dry run, or any ref
but MAIN_REF exactly) and `run_id`. Only the snapshot and the committee
pages fetch pass a kind; a record without one -- every other fetcher's, and
every record written before this -- says nothing about what it was. whose()
reads the fields, and is the one reader of who a record belongs to: every
record is a person's, as it always was, unless it is a kind GitHub's own
night on main met (RESUMABLE) and the person has switched the night's own
testing on (knock_on()). archive/knocks.json, beside the record, keeps the
chain such a test follows -- the ladder, below: every knock, written
down before it is made, and every record a knock lifted, kept whole. What
reads the lifts: drops_allowed(), which is 1 for a week after one, and
cloud.py (THE BUCKET KNOWS A LIFT there), which carries a lift to the bucket
and tells the laptop of one. whose() takes a record's bytes, never its dict
(_record), because knocks.json names a record by the sha of its bytes.

THE NIGHT'S KNOCK (29 October 2026, the person's decision). A record the
night may test (whose() "night") is not left for a person: GitHub asks the
General Court one small file for it, one request at a time, whenever a
knock is due on the ladder below -- the night once at its start
(nightly.knock), and .github/workflows/knock.yml at HOURLY_MINUTE past each
hour outside the night's hours -- and a knock answered with the file lifts
it -- moved, whole, into knocks.json, and out of the bucket by the state-up
that follows (cloud.lift_refusal). The night says once, by its own check,
when the hourly knock has fallen silent (hourly_silent). A knock the address
answers no to, a fourth relapse, KNOCK_DAYS, an answer that never reached the
bucket or was never written down, the switch turned off or a setting typed
wrong: the record is a
person's, as every other always was, and the "a refusal is yours" check is
told. Every request it makes is one knock_gate() let go.

THE KNOCK'S GATE (29 October 2026). The knock itself is `python3
src/fetch/gc_web/snapshot_gencourt.py --knock`, one request for one small
file, which asks check(knock=True) first. That gate is knock_gate(), the one
for every knock: GitHub's machine, main's own run and no dry run, a
record on file the night may test (whose()), a knock due on the ladder, and
the hours of the caller GRANITE_KNOCK_BY names -- "night", at the night's
start, from its window's opening to KNOCK_LATEST; "hourly", the knock
workflow's, outside every window and its margin, and only for a record noted
KNOCK_SETTLE_MINUTES before the last window closed, so that every laptop
that may ask has pulled it. A gate that says no exits KNOCK_NOT_NOW (4),
"not asked"; 2 stays a refusal that is a person's. The workflow's steps
around the knock are options here: --knock-look (whether one may go this
hour), --knock-claim (the claim the bucket holds before the request),
--knock-unclaim (a claim no knock took up is "not asked") and --person-line
(the "a refusal is yours" sentence, person_line(); with --knock-rc 2, the
knock's exit, a person's even where the answer was not written down).

ON GITHUB'S MACHINE (25 September 2026) it is the same file. GitHub's
machines start empty every night, so the record has to outlive the machine:
`cloud.py state-down` brings R2's state/refused.json down as archive/refused.json
before the night, and the workflow sends it back with `cloud.py state-up` the
moment one is on file. Every script reads it where it always has.

THE STAND-DOWN. Once GitHub runs the nightly, the laptop must not run it as
well: two writers of the same files, and two machines asking the General Court
for the same things. archive/runs-in-the-cloud.json says the laptop has handed
it over, and stand_down() is what the nightly, the daily snapshot, publish.bat
and the fetchers whose files GitHub now owns call to refuse, saying why.
`python3 refusal.py --stand-down` writes it; deleting it is moving back, a
person's decision. It never applies on GitHub's own machine.

ONE FETCH AT A TIME, ACROSS BOTH MACHINES (26 September 2026). A stood-down
laptop still runs General Court fetches of its own -- the lane, the bill
text, the archive -- and GitHub's night asks the same address every morning.
So on a stood-down laptop, and only there:

  - no General Court request starts inside GitHub's night window
    (NIGHT_WINDOWS, the one definition, in UTC because GitHub's cron is), or
    in the START_MARGIN_MINUTES before it opens: check() exits STOOD_DOWN (4)
    with a sentence naming the window in Eastern time and when it ends;
    watchers/gc_lane.py asks gc_turn() before each step; probe_db asks
    window_check() before every query of the SQL host, which the night and
    the weekly query too;
  - a run already going when the window opens stops at its next request if
    it asks hold().still() before each one, as the fetchers that hold
    archive/.lock do -- and the hold remembers it, so the run cannot end
    as though it had finished: a `with hold(...)` block left normally, or
    by sys.exit(0), leaves by SystemExit(STOOD_DOWN) instead, and under the
    lane still() also writes the file WINDOW_STOP_ENV names, which is how
    the lane learns a step was cut short whatever status it ended with;
  - no request starts until this laptop has read the bucket's refusal record
    (`cloud.py pull`, which records when, and from which bucket: a read of a
    --local-bucket folder never counts) since the last window ended, which
    is never more than 24 hours ago: a refusal the night met is recorded in
    the bucket, not here, and would otherwise be invisible;
  - nor since a person last cleared a refusal here (29 October 2026, the
    red team's first finding): `refusal.py --clear` writes
    archive/refusal-cleared.json, and a read of the bucket from before it is
    no read (refusal_read), so the next request waits for a pull, which
    brings the bucket's refusal back if it still stands -- a clear here
    alone never lets this laptop ask beside a test GitHub is making;
  - a refusal recorded here is sent to the bucket's state/refused.json when
    the bucket holds none, so the night stops too (note(), through
    cloud.send_refusal) -- from the repository that holds secrets.json only;
    a test folder's refusal needs a folder bucket (CLOUD_BUCKET). Where the
    bucket holds one the night's knock lifted, or one GitHub's night may
    lift itself (cloud.waits_behind), this one takes its place, the old one
    kept under replaced/: waiting behind a record a machine may lift would
    keep nothing stopped. If the bucket cannot be reached, or holds another
    refusal only a person can lift, which this one waits behind, it says so
    loudly and leaves archive/cloud/refusal-unsent.json, which pull,
    state-up and preflight report until the bucket holds this refusal or a
    person lifts it here. note() itself never fails for it: the refusal is
    on file here first.

Exit 4, not 2: 2 is "refused", and the lane and every fetcher read it as the
address saying no. Waiting for the other machine's turn is the stand-down's
arrangement, so it takes the stand-down's status -- and so does the knock's
"not now" (KNOCK_NOT_NOW).
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import os
import re
import time

MARK = Path("archive/refused.json")
QUIET_HOURS = 24

# Tests only: a folder standing in for the bucket when note() sends a refusal
# (cloud.py's --local-bucket). None is the real one, through keys.r2().
CLOUD_BUCKET = None

# WHAT KIND IT WAS (the docstring). The kinds a record can name, and the two
# that are not the address saying no: the night's own to test, once the
# person has switched that on (knock_on), and only when GitHub's night on
# main met them.
KINDS = ("dropped", "unavailable", "refused")
RESUMABLE = ("dropped", "unavailable")
# Main is this exactly, as nightly.MAIN_REF and cloud.MAIN_REF read it: a
# missing ref is not, and nor is refs/heads/Main.
MAIN_REF = "refs/heads/main"
HOUR = 3600
# A 503's Retry-After longer than this is "go away for a week": a person's.
RETRY_AFTER_MOST = 160 * HOUR
# The person's switch, and whether the third Healthchecks check -- the one
# that emails "a refusal is yours" -- exists: the workflow hands only "set"
# or "none", never its address. Both exact, or the night tests nothing.
KNOCK_ENV = "NIGHT_KNOCK"
PERSON_CHECK_ENV = "NIGHT_PERSON_CHECK"


def note(where, why, kind=None, retry_after=None):
    """Record that this address was refused. Called as a run gives up.

    `kind` is one of KINDS when the caller can say (the docstring's WHAT KIND
    IT WAS); `retry_after`, seconds, only for "unavailable" when the server
    named them. The record also says which machine wrote it, for which ref,
    whether that was a dry run, and the run: whose() reads them.

    On a stood-down laptop the refusal also goes to the bucket, so GitHub's
    night stops at it too -- after it is on file here, and without ever
    making this call fail (tell_the_bucket)."""
    ref = os.environ.get("GITHUB_REF", "")
    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epoch": time.time(),
        "where": where,
        "why": str(why)[:300],
    }
    if kind is not None:
        rec["kind"] = str(kind)
    rec.update(machine="github" if os.environ.get("GITHUB_ACTIONS") == "true" else "laptop",
               ref=ref, dry=os.environ.get("DRY_RUN") == "true" or ref != MAIN_REF,
               run_id=os.environ.get("GITHUB_RUN_ID", ""))
    if kind == "unavailable" and retry_after:
        rec["retry_after"] = int(retry_after)
    MARK.parent.mkdir(exist_ok=True)
    MARK.write_text(json.dumps(rec, indent=1), encoding="utf-8")
    if os.environ.get("GITHUB_ACTIONS") == "true" and _its_own(rec)[0]:
        _start_chain(rec)
    if _governing() is not None:
        tell_the_bucket()


def unsent_marker():
    """archive/cloud/refusal-unsent.json, beside the refusal record it is about."""
    return MARK.parent / "cloud" / "refusal-unsent.json"


def tell_the_bucket():
    """Send the refusal on file here to the bucket's state/refused.json.
    True when nothing is left to send (sent, the bucket already holds this
    one, or a person cleared this one from it); False, loudly, when it could
    not be sent, or waits behind another refusal the bucket holds.

    The marker is written BEFORE the send and removed by cloud.send_refusal
    only once the bucket holds THIS refusal, so an interrupted or crashed
    send, or one that found the bucket holding an older refusal, still
    leaves it for pull, state-up and preflight to report. Nothing here
    raises: note() is called as a run gives up, and a refusal already on file
    must not be lost to a network error on the way to the bucket.
    """
    marker = unsent_marker()

    def mark(why):
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(json.dumps({
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "epoch": time.time(),
                "refusal": str(MARK), "why": str(why)[:300]}, indent=1), encoding="utf-8")
        except OSError:
            pass
    mark("being sent to the bucket")
    try:
        import cloud
        done, said = cloud.send_refusal(MARK.resolve().parent.parent,
                                        local_bucket=CLOUD_BUCKET)
    except (Exception, SystemExit) as e:                        # noqa: BLE001
        why = f"{type(e).__name__}: {e}"
        try:
            import cloud
            why = cloud.scrub(why)
        except Exception:                                       # noqa: BLE001
            pass
        mark(why)
        print(f"\nTHE BUCKET HAS NOT BEEN TOLD. This refusal is on file here ({MARK}), "
              f"but it could not be sent to the bucket's state/refused.json:\n  {why}\n"
              "GitHub's night reads the bucket's refusal record, not this one, so it would "
              f"still ask the General Court. {marker} says so until it is sent:\n"
              "  python3 src/ops/cloud.py send-refusal\n", file=sys.stderr)
        return False
    if done:
        print(f"\nThe refusal went to the bucket as well: {said}", file=sys.stderr)
        return True
    # The bucket holds another refusal, and send_refusal has written why into
    # the marker: this one is not lost, it waits.
    print(f"\nTHE BUCKET HAS NOT TAKEN THIS REFUSAL. It is on file here ({MARK}), but "
          f"{said}.\n{marker} says so until the bucket holds this refusal or a person "
          "lifts it here.\n", file=sys.stderr)
    return False


def hours_left(d, now=None):
    """Hours the refusal record `d` still stops check() for by its age, or
    None once it is older than QUIET_HOURS. standing() is this, for the
    record on file, with any_age() beside it: a record GitHub's machine met
    that names its kind stops check() at any age."""
    age = ((time.time() if now is None else now) - float((d or {}).get("epoch") or 0)) / 3600
    return None if age > QUIET_HOURS else QUIET_HOURS - age


def any_age(d):
    """Whether check() stops at refusal record `d` -- its fields, a dict --
    for as long as it is on file rather than for QUIET_HOURS: GitHub's
    machine met it (machine "github") and it says what kind it was (the
    docstring's AT ANY AGE). Every other record keeps its QUIET_HOURS: one
    met here, and every one that names no kind."""
    return isinstance(d, dict) and d.get("machine") == "github" and d.get("kind") is not None


def force(d, now=None, lift=None):
    """What a refusal record held in the bucket stops, in the words pull and
    clear-refusal print. Three things read one, each its own way: check(),
    which every hand-started fetch calls, for QUIET_HOURS -- or at any age
    for a record GitHub's machine met that names its kind (any_age); the
    lane, which stops at any archive/refused.json; and GitHub's night, which
    stops at any state/refused.json in the bucket until a person lifts it --
    or, for a record of a kind GitHub's own night on main met (whose()
    conditions 1 to 5), until its own knock lifts it, when the person has
    switched that on. Off GitHub the switch cannot be read, so for such a
    record this says the night decides, and its run page says what it
    decided. `lift`, knocks.json's "lifted" entry for this record, says who
    lifted it and when, and what a copy still on file here stops: the lane
    and every fetch here, at any age, until a person clears it here."""
    if lift:
        return (lift_line(lift) + ". A copy on file here still stops the lane and every fetch "
                "here until python3 refusal.py --clear")
    if _its_own(d or {})[0]:
        return ("in force for every General Court fetch here and the lane here, at any age, "
                "until a person lifts it here (python3 refusal.py --clear). GitHub's night met it "
                f"(a {d.get('kind')} on {MAIN_REF}) and decides whether it tests it itself, one "
                "request at a time; its run page says")
    if any_age(d or {}):
        return ("in force for every General Court fetch here and the lane here, at any age, "
                f"because GitHub's machine met it (a {d.get('kind')}), until a person lifts it "
                "here (python3 refusal.py --clear); and GitHub's night stops at it until python3 "
                "src/ops/cloud.py clear-refusal")
    left = hours_left(d, now)
    if left is not None:
        return (f"in force for {left:.1f} more hours: every General Court fetch here stops at "
                "it until then, and the lane and GitHub's night stop at it until a person "
                "lifts it")
    return (f"older than {QUIET_HOURS} hours: hand fetches here are not stopped by it, the "
            "lane is (it stops at any archive/refused.json), and GitHub's night stops at "
            "it until python3 src/ops/cloud.py clear-refusal")


def lift_line(lift):
    """A lift, from its knocks.json "lifted" entry: who, when, and why."""
    return (f"lifted by GitHub's knock at {lift.get('utc')} ({_lifter(lift)}), after one "
            "request was answered")


def _lifter(lift):
    """Who lifted a record, from its "lifted" entry: the hourly knock or the
    night's own."""
    return {"hourly": "the hourly knock", "night": "the night's own knock"}.get(
        str(lift.get("by") or ""), "a knock")


def standing():
    """The refusal still in force for check(), (record, hours old), or None:
    one less than QUIET_HOURS old, or one any_age() keeps at any age."""
    if not MARK.exists():
        return None
    try:
        d = json.loads(MARK.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    hours = (time.time() - float(d.get("epoch") or 0)) / 3600
    return None if hours > QUIET_HOURS and not any_age(d) else (d, hours)


def check(who="", knock=False):
    """Stop the caller if this address was refused recently -- and, on a
    stood-down laptop, while GitHub's night may be running, in the half hour
    before it, or until this laptop has read the bucket's refusal record since
    the last one (gc_turn).

    knock=True is the knock's, and only the knock's: snapshot_gencourt.py
    --knock is the one caller that may pass it (preflight reads every other
    call). It turns the rule round. The knock asks only while a refusal is on
    file -- one the night may test, at any age, never through standing() --
    and only when knock_gate() lets the caller GRANITE_KNOCK_BY names ask now;
    anything else exits KNOCK_NOT_NOW (4), "not asked", having asked
    nothing. Never 2: that is "refused", which the knock's callers read as a
    refusal that has become a person's, and a gate that only says "not now"
    would otherwise tell the person a refusal was theirs whenever the
    night's window opened."""
    if knock:
        ok, why = knock_gate(os.environ.get(KNOCK_BY_ENV))
        if not ok:
            print(f"\n{who or 'The knock'} is not asked: {why}.{_clock_note()}\n",
                  file=sys.stderr)
            sys.exit(KNOCK_NOT_NOW)
        return
    s = standing()
    if not s:
        turn = gc_turn()
        if turn:
            print(f"\n{who or 'This fetch'} is not starting. {turn[1]}\n", file=sys.stderr)
            sys.exit(STOOD_DOWN)
        soon = window_soon()
        if soon:
            print(f"\nNote: {soon}\n", file=sys.stderr)
        return
    d, hours = s
    # GitHub's machine met it, so it stops a hand fetch at any age (the
    # docstring's AT ANY AGE): said, whatever its age, with what clears it.
    github = ""
    if any_age(d):
        github = (f"GitHub's machine met this refusal (a {d.get('kind')}), so a copy on file "
                  f"here stops every fetch here at any age, not only for {QUIET_HOURS} hours"
                  + (": GitHub may be testing it itself, once an hour, and lifts the bucket's "
                     "copy when one is answered. To check or clear it sooner yourself, first "
                     "set the GitHub variable NIGHT_KNOCK to off, or disable the knock "
                     "workflow: two machines asking at once is how the second block happened"
                     if _its_own(d)[0] else "")
                  + ". python3 src/ops/cloud.py pull says whether the bucket's still stands.\n\n")
    # Status 2, which every fetcher and the lane read as "refused".
    print(
        f"\nThis address was refused {hours:.1f} hours ago and nothing has "
        f"asked it since.\n"
        f"  when   {d.get('at')}\n"
        f"  who    {d.get('where')}\n"
        f"  what   {d.get('why')}\n\n"
        f"{who or 'This fetch'} is stopping. A refusal is a fact about the "
        "address, not about\nthe run that found it, so it applies to every "
        "fetch and not only that one.\n\n"
        + github +
        "  python3 netcheck.py          what kind of refusal it was\n"
        "  python3 refusal.py --clear   when a person has decided to go on\n",
        file=sys.stderr)
    sys.exit(2)


# ---- what an answer means --------------------------------------------------
#
# One reading of an answer, for every fetcher. The docket fetch matched
# refusals by substring of the error's text, and urllib wraps a reset at
# connect time as "<urlopen error [WinError 10054] ...>", which contains
# neither "RemoteDisconnected" nor "ConnectionReset": a connection being
# refused was counted as an ordinary failure, with no cool-off, no stop and
# no record. And neither fetch knew that a server shedding load says 503 with
# a Retry-After, which is a request to go away, not a flaky link.

BLOCKED = re.compile(r"Web Page Blocked|Attack ID", re.I)
BROKEN = re.compile(r"Runtime Error|Server Error in|Service Unavailable", re.I)


def classify(err=None, body=None):
    """"refused", "dropped", "missing", "failed", or None for a fine answer.

    refused  -- 403, 429, 503, a Retry-After, or the firewall's block page:
                the address saying no. One ends a run.
    dropped  -- accepted and closed without an answer, reset, aborted or
                timed out, at connect or mid-read: this address's usual
                sign of refusing. Two end a run.
    missing  -- 404 or 410: no such document.
    failed   -- anything else that is not a page.
    """
    import http.client
    import socket
    import ssl
    import urllib.error
    if err is not None:
        if isinstance(err, urllib.error.HTTPError):
            if err.code in (403, 429, 503) or (err.headers or {}).get("Retry-After"):
                return "refused"
            try:
                head = err.read(4000).decode("utf-8", "replace")
            except Exception:
                head = ""
            if BLOCKED.search(head):
                return "refused"
            return "missing" if err.code in (404, 410) else "failed"
        inner = err.reason if isinstance(err, urllib.error.URLError) else err
        if isinstance(inner, (http.client.RemoteDisconnected, ConnectionResetError,
                              ConnectionAbortedError, ConnectionRefusedError,
                              TimeoutError, socket.timeout, ssl.SSLEOFError)):
            return "dropped"
        if isinstance(inner, str) and "timed out" in inner:
            return "dropped"
        return "failed"
    if body is not None:
        head = body[:4000] if isinstance(body, str) else ""
        if BLOCKED.search(head):
            return "refused"
    return None


def no_redirect_opener():
    """An opener with urlopen's handlers for http and https but no
    HTTPRedirectHandler (nor a subclass of one): a 3xx comes back as an
    HTTPError (redirected(), below), and nothing follows it -- one request,
    to the address asked and no other. The night's fetchers keep one as
    _OPENER (snapshot_gencourt, fetch_committees, fetch_lsrs and
    fetch_calendar_archive), the name a check stands a fake in for; netcheck
    keeps its open as URLOPEN."""
    import urllib.request
    o = urllib.request.OpenerDirector()
    for h in (urllib.request.ProxyHandler(), urllib.request.UnknownHandler(),
              urllib.request.HTTPHandler(), urllib.request.HTTPSHandler(),
              urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPErrorProcessor()):
        o.add_handler(h)
    return o


def redirected(err):
    """Whether `err` is an HTTPError whose status is a redirect (3xx), as an
    opener without a redirect handler raises one. The night's fetchers read
    it as "refused", the address saying no, and a person's: a data file's
    address that answers with another address is not the file, and
    following it would be a request to a target nobody chose. classify() is
    unchanged, so a fetch that wants a 3xx as an ordinary failure
    (fetch_legislation, which keeps its own opener) still has one."""
    import urllib.error
    return isinstance(err, urllib.error.HTTPError) and 300 <= err.code < 400


def unavailable(err, head=None):
    """The seconds a 503 asks us to wait, when the error is an HTTP 503 whose
    body is not the firewall's page: 0 when it names no Retry-After. None for
    anything else -- a 429, a 403, a 503 carrying the block page, and a 503
    whose Retry-After reads as neither seconds nor a date, which is taken as
    the worst answer.

    classify() calls every 503 "refused" before it reads the body, and still
    does, so a 503 still ends a run at once; this is what names the kind
    ("unavailable", the server's own "not now") for the record. `head`, the
    body's first 4,000 characters, for a caller that has read them already
    (the knock, which reads an answer once): the body is not read again."""
    import urllib.error
    if not isinstance(err, urllib.error.HTTPError) or err.code != 503:
        return None
    if head is None:
        try:
            head = err.read(4000).decode("utf-8", "replace")
        except Exception:                                       # noqa: BLE001
            head = ""
    if BLOCKED.search(head):
        return None
    raw = str((err.headers or {}).get("Retry-After") or "").strip()
    if not raw:
        return 0
    if raw.isascii() and raw.isdigit():
        return int(raw)
    try:
        from email.utils import parsedate_to_datetime
        then = parsedate_to_datetime(raw)
    except (TypeError, ValueError, IndexError):
        return None
    if then is None:
        return None
    if then.tzinfo is None:
        from datetime import timezone
        then = then.replace(tzinfo=timezone.utc)
    return max(0, int(then.timestamp() - time.time()))


# ---- whose a refusal is ------------------------------------------------------
#
# One rule, one answer. Every record is a person's to clear, as it always
# was, except one GitHub's own night on main met and could not tell from a
# passing outage -- RESUMABLE -- while the person has switched the night's
# testing on. It is the one gate the night's own test of a refusal opens
# through: the night's knock (knock_gate, nightly.knock) asks it, and
# refusal.py's status says it; anything else a reader needs to know about a
# record it says in `why`.

def knock_on():
    """Whether the person has switched the night's own testing of a refusal
    on: NIGHT_KNOCK exactly "on", and NIGHT_PERSON_CHECK exactly "set" (the
    workflow's word that the "a refusal is yours" check exists, so the email
    that says a record has become a person's can always be sent). Anything
    else -- unset, "ON", "on " -- is off: the safe direction. And the three
    settings must read (knock_settings): a setting typed wrong is off too."""
    return (os.environ.get(KNOCK_ENV) == "on" and os.environ.get(PERSON_CHECK_ENV) == "set"
            and not knock_settings()[3])


def _record(d):
    """(the record as a dict, its exact bytes) from refused.json's bytes, or
    None for the one on file (({}, None) when none is).

    BYTES OR NOTHING (29 October 2026). Whose a record is turns on
    knocks.json as well as its fields, and knocks.json names its record by
    the sha of refused.json's exact bytes. A dict has no bytes, so read as
    one a record could never be named: a knock that made it a person's, a
    fourth relapse, an answer that never reached the bucket and the chain's
    start would all be passed over, and the record read as the night's. So
    a dict -- or anything else -- is refused here, TypeError, for whose(),
    chain(), knock_due() and knock_schedule() alike. A caller holding only
    the fields asks _its_own(), which says what the fields alone can."""
    if d is None:
        try:
            d = MARK.read_bytes()
        except OSError:
            return {}, None
    if not isinstance(d, (bytes, bytearray)):
        raise TypeError(f"a refusal record is read from refused.json's bytes, or None for the "
                        f"one on file, not a {type(d).__name__}: whose it is turns on "
                        "knocks.json, which names a record by the sha of its bytes "
                        "(_its_own reads the fields alone)")
    raw = bytes(d)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        doc = None
    return (doc if isinstance(doc, dict) else {"unreadable": True}), raw


def whose(d=None, k=None, now=None):
    """("night" | "person", why) for a refusal record -- refused.json's
    bytes, or None for the one on file; never a dict (_record: TypeError) --
    or ("none", why) when no record is on file. `k` is knocks.json's document
    (None, the one on file), whose "current" counts only when it names this
    record by sha. "night" only when all hold:

      1. its kind is one of RESUMABLE;
      2. GitHub's machine wrote it (machine "github");
      3. for MAIN_REF exactly;
      4. not a dry run (dry is False);
      5. it names no Retry-After longer than RETRY_AFTER_MOST;
      6. no knock has made it a person's (`person`), it is younger than
         KNOCK_DAYS days from the chain's start (`since`), it has relapsed
         fewer than RELAPSES_MOST times, and no knock's answer is lost --
         an entry still "claimed" KNOCK_JOB_MINUTES after it was made,
         other than this run's own, whose answer never reached the bucket;
         or one still "no answer" that long after it was made, whose answer
         was never written down (THE ANSWER NOT WRITTEN DOWN, below);
      7. knock_on(), its three settings reading.

    Anything else is a person's: every record without a kind, the ones
    written before records said what they were among them.

    THE ANSWER NOT WRITTEN DOWN (the reviewers of 30 October 2026). knocking()
    writes "no answer" before the request, and the answer replaces it within
    the knock's KNOCK_MINUTES: knocked() by the child, or, for a knock killed
    with no answer, "dropped" by the child's own kill or by the night that
    killed it. One still "no answer" KNOCK_JOB_MINUTES on is a knock whose
    answer was lost -- a 403 among the possibilities -- and a 403 read as a
    failed knock would be asked again an hour later. So it is the worst
    answer, as a lost claim is: a person's, the third check told, and no
    knock ever due again."""
    doc, raw = _record(d)
    if d is None and raw is None:
        return "none", "no refusal is on file"
    ok, why = _its_own(doc)
    if not ok:
        return "person", why
    t = _utc(now).timestamp()
    hourly, every, days, bad = knock_settings()
    c = chain(raw, k)
    if c is None:
        return "person", f"{knocks_file()} does not read"
    if c["person"]:
        return "person", str(c["person"].get("why") or "a knock made it a person's")
    if t >= c["since"] + days * DAY:
        return "person", (f"it has stood since {_stamp(c['since'])}: the night tests a refusal "
                          f"for {days} days at most")
    if c["relapses"] >= RELAPSES_MOST:
        return "person", (f"the website answered a knock and then dropped the night's export "
                          f"{c['relapses']} times in this chain")
    lost = [x for x in c["counted"] if x.get("answer") in ("claimed", "no answer")
            and t - float(x.get("epoch") or 0) > KNOCK_JOB_MINUTES * 60]
    if lost:
        x = lost[-1]
        if x.get("answer") == "claimed":
            return "person", (f"the answer to the knock claimed at {x.get('utc')} (run "
                              f"{x.get('run_id')}) never reached the bucket, so it is taken as "
                              "the worst answer")
        return "person", (f"the answer to the knock made at {x.get('utc')} (run "
                          f"{x.get('run_id')}) was never written down, so it is taken as the "
                          "worst answer")
    if bad:
        return "person", bad
    if not knock_on():
        return "person", (f"the night's own testing is off ({KNOCK_ENV} is "
                          f"{os.environ.get(KNOCK_ENV)!r}, {PERSON_CHECK_ENV} is "
                          f"{os.environ.get(PERSON_CHECK_ENV)!r})")
    return "night", (f"a refusal of the kind {doc.get('kind')!r} GitHub's night on main met: "
                     "the night's to test")


def _its_own(doc):
    """(True, "") when a record's own fields make it one the night may test
    -- whose() conditions 1 to 5 -- else (False, why)."""
    if doc.get("unreadable"):
        return False, "the refusal record does not read"
    kind = doc.get("kind")
    if kind not in RESUMABLE:
        return False, ("it does not say what kind of refusal it was" if kind is None else
                       f"it is a refusal of the kind {kind!r}: the address said no")
    if doc.get("machine") != "github":
        return False, "it was met on the laptop, not by GitHub's night"
    if doc.get("ref") != MAIN_REF:
        return False, f"it was met by a run of {doc.get('ref') or 'no ref'}, not {MAIN_REF}"
    if doc.get("dry") is not False:
        return False, "it was met by a dry run"
    ra = doc.get("retry_after")
    if ra is not None:
        try:
            ra = float(ra)
        except (TypeError, ValueError):
            return False, f"its Retry-After ({ra!r}) does not read"
        if ra > RETRY_AFTER_MOST:
            return False, (f"the server asked for {ra / HOUR:.0f} hours, longer than "
                           f"{RETRY_AFTER_MOST // HOUR}")
    return True, ""


# ---- the night's knock: the ladder and its state (29 October 2026) -----------
#
# A record the night may test (whose() == "night") is tested by one request
# at a time, on a ladder: a rung an hour for the first KNOCK_HOURLY_HOURS
# after the chain began, then a rung every KNOCK_EVERY_HOURS, until
# KNOCK_DAYS days, when the record is a person's. The rungs are aligned to
# the UTC clock at knock_anchor() -- the daily window's start less its
# START_MARGIN_MINUTES, 07:30 UTC today -- not to the record, so the span the
# night's own window covers is one rung of its own. knocks.json, beside the
# record and written only here, keeps the chain: every knock, each written
# down BEFORE it is made (knocking) and answered after (knocked), and every
# record a knock lifted, its exact text kept, never pruned. GitHub's night
# knocks on it (nightly.knock), and so does its second caller, the hourly
# knock (.github/workflows/knock.yml), each in its own hours.

KNOCKS = Path("archive/knocks.json")
DAY = 24 * HOUR
# A record noted within this long of a lift carries the lifted record's
# chain: its knocks, its start and one more relapse. For the same week one
# dropped connection ends an export (drops_allowed).
RELAPSE_HOURS = 168
# The fourth relapse in a chain -- a knock answered, then the night's export
# dropped -- makes the record a person's: the bound on a flapping server.
RELAPSES_MOST = 4
# How long a knock may take: the child's own limit, and the knock job's
# timeout-minutes, which preflight will hold equal to this.
KNOCK_MINUTES = 2
KNOCK_JOB_MINUTES = 15
# Who is knocking, "night" or "hourly", in the knock child's environment.
KNOCK_BY_ENV = "GRANITE_KNOCK_BY"
# What a knock's answer can be, as knocked() is told it: "whole" lifts the
# record, "refused" makes it a person's, every other one is a failed knock.
KNOCK_ANSWERS = ("whole", "refused", "dropped", "unavailable", "missing", "failed", "page")
# THE KNOCK'S GATE (knock_gate). The night knocks only from its daily
# window's start to this, UTC: nightly.ASK_UNTIL, 12:00, less the knock's
# KNOCK_MINUTES and the forty minutes of the export a lift opens -- the
# child's own copy of the night's asking_left(42), so that a change that
# lost the night's gate still asks nothing after 11:18.
KNOCK_LATEST = (11, 18)
# An hourly knock tests only a record noted at least this long before the
# last night window closed: every laptop gc_turn() lets ask has pulled the
# bucket since, so holds the record, and stops at it. A margin over the
# minutes a drop night runs after its record, not a measurement.
KNOCK_SETTLE_MINUTES = 60
# The hourly claim asks the gate at this much later too, so that the child,
# seconds after it, does not decline on the clock or the rung.
CLAIM_SLACK_MINUTES = 5
# WHEN THE HOURLY KNOCK FALLS SILENT (the red team's fifth finding,
# hourly_silent): the minute past each hour the knock workflow runs at --
# .github/workflows/knock.yml's cron, which preflight holds to this -- and
# how many of those minutes, open to an hourly knock that was due, may pass
# with no trace of it before the night says it has stopped. Ten allows for
# GitHub's scheduler running five to seven hours late, as it did in October.
HOURLY_MINUTE = 47
HOURLY_SILENT_HOURS = 10


def knock_settings():
    """(hourly_h, every_h, days, why): the three repository variables, as the
    workflows pass them. Unset or empty is the default; anything else that is
    not a plain decimal in range -- "48h", " 48", "-1", 17 days, 5 or 7 hours a
    rung -- gives `why`, a sentence naming the variable and its value, and
    the defaults beside it. knock_on() is then False: every record is a
    person's, as with the switch off. The only place the numbers live."""
    table = (("KNOCK_HOURLY_HOURS", 48, "a whole number of hours from 0 to 384",
              lambda n: 0 <= n <= 384),
             ("KNOCK_EVERY_HOURS", 6, "1, 2, 3, 4, 6, 8, 12 or 24 (a rung must divide a day)",
              lambda n: n in (1, 2, 3, 4, 6, 8, 12, 24)),
             ("KNOCK_DAYS", 16, "a whole number of days from 1 to 16", lambda n: 1 <= n <= 16))
    out, bad = [], []
    for name, default, allowed, fits in table:
        raw = os.environ.get(name)
        if raw is None or raw == "":
            out.append(default)
        elif re.fullmatch(r"[0-9]+", raw) and fits(int(raw)):
            out.append(int(raw))
        else:
            out.append(default)
            bad.append(f"{name} is {raw!r}, which is not {allowed}")
    why = ("; ".join(bad) + ": the night's own testing is off until it reads") if bad else ""
    return out[0], out[1], out[2], why


def knock_anchor():
    """KNOCK_ANCHOR, as an epoch: the daily window's start in NIGHT_WINDOWS
    less START_MARGIN_MINUTES (07:30 UTC today), on 1 January 2026. Every
    rung size divides a day, so any day's would do. Read from the window
    each time, so that it moves with it."""
    from datetime import datetime, timedelta, timezone
    sh, sm = next(start for wd, start, _, _ in NIGHT_WINDOWS if wd is None)
    return (datetime(2026, 1, 1, sh, sm, tzinfo=timezone.utc)
            - timedelta(minutes=START_MARGIN_MINUTES)).timestamp()


def knocks_file():
    """KNOCKS, beside the refusal record: a test that points MARK at a folder
    of its own keeps its knocks there too."""
    return MARK.parent / KNOCKS.name


def _sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def _stamp(epoch):
    from datetime import datetime, timezone
    return f"{datetime.fromtimestamp(float(epoch), timezone.utc):%Y-%m-%d %H:%M} UTC"


def read_knocks():
    """(knocks.json's document, True), the empty one when there is none; or
    (the empty one, False) when it does not read -- which no writer here
    overwrites, so that what it holds of past lifts is never lost."""
    empty = {"current": None, "lifted": []}
    try:
        raw = knocks_file().read_bytes()
    except FileNotFoundError:
        return empty, True
    except OSError:
        return empty, False
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return empty, False
    if not isinstance(doc, dict) or not isinstance(doc.get("lifted", []), list) \
            or not isinstance(doc.get("current"), (dict, type(None))):
        return empty, False
    doc.setdefault("current", None)
    doc.setdefault("lifted", [])
    return doc, True


def _write_knocks(doc):
    """knocks.json, whole: a part file, then a rename."""
    p = knocks_file()
    p.parent.mkdir(exist_ok=True)
    tmp = p.with_name(p.name + ".part")
    tmp.write_text(json.dumps(doc, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def _own_claim(x):
    """Whether knock entry `x` is this run's own claim, which this run does
    not count against itself (same GITHUB_RUN_ID and GITHUB_RUN_ATTEMPT)."""
    rid = os.environ.get("GITHUB_RUN_ID", "")
    return (bool(rid) and x.get("answer") == "claimed" and str(x.get("run_id")) == rid
            and str(x.get("attempt") or "") == os.environ.get("GITHUB_RUN_ATTEMPT", ""))


def chain(d=None, k=None):
    """The ladder's state for a record -- refused.json's bytes, or None for
    the one on file; a dict is refused (_record: TypeError) -- and
    knocks.json's document (None, the one on file): {"sha", "epoch",
    "retry_after", "since", "knocks", "counted", "relapses", "person",
    "carried_from", "named"}. The document's "current" counts only when it
    names this record by the sha of its bytes ("named"); otherwise the chain
    starts at the record itself, with no knocks, no `person` and its own
    epoch as `since`. `counted` is every knock but one marked "not asked"
    and this run's own claim. None when knocks.json does not read, or there
    is no record."""
    doc, raw = _record(d)
    if raw is None:
        return None
    if k is None:
        k, ok = read_knocks()
        if not ok:
            return None
    sha = _sha(raw)
    cur = k.get("current") if isinstance(k, dict) else None
    named = isinstance(cur, dict) and cur.get("refusal") == sha
    if not named:
        cur = {}
    knocks = [x for x in cur.get("knocks") or [] if isinstance(x, dict)]
    return {"sha": sha, "epoch": float(doc.get("epoch") or 0),
            "retry_after": doc.get("retry_after"),
            "since": float(cur.get("since") or doc.get("epoch") or 0),
            "knocks": knocks,
            "counted": [x for x in knocks if x.get("answer") != "not asked" and not _own_claim(x)],
            "relapses": int(cur.get("relapses") or 0), "person": cur.get("person"),
            "carried_from": cur.get("carried_from"), "named": named}


def knock_due(d=None, k=None, now=None):
    """(due, due_epoch): whether a knock is due now for a record (as chain()
    reads `d` and `k`), and the earliest time one is. Due when all hold:

      1. now is before the chain's start plus KNOCK_DAYS days (the cap);
      2. now is at least the last failed request plus its Retry-After, when
         that request -- the record's or the last knock's -- carried one;
      3. now is in a later rung than the last failed request, both measured
         in the rung size that applies NOW: an hour while now is within
         KNOCK_HOURLY_HOURS of the start, KNOCK_EVERY_HOURS after;
      4. now is at least half a rung after it;
      5. no other run's claim younger than KNOCK_JOB_MINUTES is in flight.

    The last failed request is the latest of the record and every counted
    knock (chain()). due_epoch is None once the cap comes first, and for any
    record whose() does not call the night's -- a knock that made it a
    person's, a fourth relapse, a lost answer, the switch off, its own fields:
    no knock is ever due for a person's record, whoever asks. The hours a
    caller may knock in are the caller's, not this function's."""
    hourly, every, days, _ = knock_settings()
    if whose(d, k, now)[0] != "night":
        return False, None
    c = chain(d, k)
    if c is None:
        return False, None
    t = _utc(now).timestamp()
    last, wait = c["epoch"], c["retry_after"]
    for x in c["counted"]:
        if float(x.get("epoch") or 0) >= last:
            last, wait = float(x.get("epoch") or 0), x.get("retry_after")
    try:
        wait = float(wait or 0)
    except (TypeError, ValueError):
        return False, None
    cap, switch, anchor = c["since"] + days * DAY, c["since"] + hourly * HOUR, knock_anchor()
    best = None
    for start, end, size in ((c["since"], min(switch, cap), HOUR),
                             (max(c["since"], switch), cap, every * HOUR)):
        if end <= start:
            continue
        rung_after = anchor + ((last - anchor) // size + 1) * size
        at = max(t, start, last + wait, rung_after, last + size / 2)
        if at < end:
            best = at
            break
    if best is None:
        return False, None
    flying = [float(x.get("epoch") or 0) + KNOCK_JOB_MINUTES * 60 for x in c["counted"]
              if x.get("answer") == "claimed"
              and t - float(x.get("epoch") or 0) < KNOCK_JOB_MINUTES * 60]
    if flying:
        best = max([best] + flying)
    return best <= t, best


def knock_schedule(d=None, k=None):
    """When knocks may come for a record, if each fails, in words, for the
    day-0 email and the run's page: the pattern, not a list of dates."""
    from datetime import datetime, timedelta, timezone
    hourly, every, days, _ = knock_settings()
    c = chain(d, k)
    if c is None:
        return ""
    cap, switch = c["since"] + days * DAY, c["since"] + hourly * HOUR

    def hm(t):
        return f"{t:%H:%M}"
    quiet = []
    for wd, (sh, sm), (eh, em), _ in NIGHT_WINDOWS:
        s = datetime(2026, 1, 1, sh, sm, tzinfo=timezone.utc) - timedelta(minutes=START_MARGIN_MINUTES)
        e = datetime(2026, 1, 1, eh, em, tzinfo=timezone.utc)
        quiet.append(f"{hm(s)}-{hm(e)} UTC" + ("" if wd is None else " on a "
                                                + ("Monday Tuesday Wednesday Thursday Friday "
                                                   "Saturday Sunday").split()[wd]))
    out = []
    if switch > c["since"]:
        out.append(f"one request an hour outside {' and '.join(quiet)} until {_stamp(min(switch, cap))}")
    if switch < cap:
        a = datetime.fromtimestamp(knock_anchor(), timezone.utc)
        starts = [hm(a + timedelta(hours=every * i)) for i in range(int(DAY // (every * HOUR)))]
        out.append(("then " if out else "")
                   + (f"one in each {every}-hour span from {', '.join(starts)} UTC"
                      if len(starts) > 1 else f"one a day from {starts[0]} UTC"))
    out.append(f"until {_stamp(cap)}, when the record is yours")
    return ", ".join(out) + "; and one from the night itself at its start, whenever its span allows"


def hourly_silent(d=None, k=None, now=None):
    """The sentence that says the hourly knock has stopped, or "" (the
    addendum's 6.1). The knock workflow leaves no trace of an hour it found
    nothing to do, so the only sign of it running is an entry `by` "hourly" in
    knocks.json -- a knock, a claim, or a claim marked "not asked". A
    sentence only when the refusal on file (`d`, refused.json's bytes, or
    None for the one on file) is the night's to test (whose()), and in the
    eighteen hours from the last daily window's close to its next start less
    its margin -- 13:30 to 07:30 UTC today, the span before `now`'s morning
    -- at least HOURLY_SILENT_HOURS of the HOURLY_MINUTE minutes were open to
    an hourly knock that was due (knock_due() then, with only the knocks made
    by then; knock_hours("hourly"); the settle rule, by the record's own
    time), and no hourly entry of any answer falls in those eighteen hours.
    A record the settle rule holds, a Retry-After, and a person's record give
    fewer open hours, so nothing is said."""
    from datetime import datetime, timedelta, timezone
    doc, raw = _record(d)
    if raw is None:
        return ""
    if k is None:
        k, ok = read_knocks()
        if not ok:
            return ""
    u = _utc(now)
    if whose(raw, k, u)[0] != "night":
        return ""
    c = chain(raw, k)
    if c is None:
        return ""
    # The span: from the daily window's close the day before this morning's
    # anchor (knock_anchor's time of day) to that anchor.
    a = datetime.fromtimestamp(knock_anchor(), timezone.utc)
    anchor = u.replace(hour=a.hour, minute=a.minute, second=0, microsecond=0)
    if anchor > u:
        anchor -= timedelta(days=1)
    eh, em = next(end for wd, _s, end, _w in NIGHT_WINDOWS if wd is None)
    start = (anchor - timedelta(days=1)).replace(hour=eh, minute=em)
    lo, hi = start.timestamp(), anchor.timestamp()
    hourly = [x for x in c["knocks"] if x.get("by") == "hourly"]
    if any(lo <= float(x.get("epoch") or 0) < hi for x in hourly):
        return ""
    cur = k.get("current") if c["named"] else None
    t = start.replace(minute=HOURLY_MINUTE)
    if t < start:
        t += timedelta(hours=1)
    opened = 0
    while t < anchor:
        te = t.timestamp()
        # The ladder as it stood then: only the knocks made by then.
        kt = k if cur is None else dict(k, current=dict(cur, knocks=[
            x for x in cur.get("knocks") or [] if isinstance(x, dict)
            and float(x.get("epoch") or 0) <= te]))
        if knock_due(raw, kt, te)[0] and knock_hours("hourly", te)[0] and \
                _settled(doc.get("epoch") or 0, te)[0]:
            opened += 1
        t += timedelta(hours=1)
    if opened < HOURLY_SILENT_HOURS:
        return ""
    last = max((float(x.get("epoch") or 0) for x in hourly), default=0)
    return (f"the hourly knock has not run since "
            + (f"{_stamp(last)}, its last entry" if last else
               f"the refusal began, {_stamp(c['since'])}")
            + f": none in the {opened} hours before this morning it could have knocked. "
            ".github/workflows/knock.yml may be disabled, paused by GitHub, or without its "
            "read-only R2 key; the night still knocks once each morning")


def _start_chain(rec):
    """note()'s, on GitHub, for a record whose own fields the night may test:
    knocks.json's "current" for it. Within RELAPSE_HOURS of the last lift it
    carries that chain -- its knocks, the answered one included, its start,
    and one more relapse -- so the ladder goes on where it was and the
    KNOCK_DAYS count from the first drop. Never raises: note() is called as a
    run gives up, and the record is on file already."""
    try:
        raw = MARK.read_bytes()
        k, ok = read_knocks()
        if not ok:
            raise ValueError(f"{knocks_file()} does not read, and is not written over")
        last = k["lifted"][-1] if k["lifted"] else None
        new = {"refusal": _sha(raw), "since": float(rec["epoch"]), "knocks": [],
               "person": None, "carried_from": None, "relapses": 0}
        if isinstance(last, dict) and \
                float(rec["epoch"]) - float(last.get("epoch") or 0) < RELAPSE_HOURS * HOUR:
            new.update(since=float(last.get("since") or rec["epoch"]),
                       knocks=list(last.get("knocks") or []), carried_from=last.get("refusal"),
                       relapses=int(last.get("relapses") or 0) + 1)
        k["current"] = new
        _write_knocks(k)
    except Exception as e:                                      # noqa: BLE001
        print(f"\nTHE KNOCKS' RECORD WAS NOT STARTED for this refusal ({type(e).__name__}: "
              f"{e}). The refusal is on file; the night will count its chain from the record "
              "itself.\n", file=sys.stderr)


def knocking(url):
    """Write a knock down BEFORE it is made: an entry answering "no answer"
    in knocks.json's "current" -- started from the record on file when it
    names another -- so that a knock killed mid-request still counts.
    Returns the entry. Raises, and so asks nothing, when there is no record
    on file or knocks.json will not read. Whatever kills a knock with no
    answer writes "dropped" over it (knocked); an entry still "no answer"
    KNOCK_JOB_MINUTES on is an answer lost, and a person's (whose()).

    THIS RUN'S OWN CLAIM IS THE KNOCK (the addendum's 1.6, rule 4). The
    hourly caller sent a "claimed" entry to the bucket before this
    (--knock-claim); when the last entry is this run's own claim (_own_claim:
    the same run and attempt), it becomes the knock -- "no answer", at this
    moment, with its address -- rather than a second entry beside it, which
    would count two knocks for one request. So an entry still "claimed"
    after the child has gone was never asked (--knock-unclaim)."""
    raw = MARK.read_bytes()
    sha = _sha(raw)
    k, ok = read_knocks()
    if not ok:
        raise RuntimeError(f"{knocks_file()} does not read, so the knock cannot be written "
                           "down first, and is not made")
    cur = k.get("current")
    if not (isinstance(cur, dict) and cur.get("refusal") == sha):
        doc = _record(raw)[0]
        cur = {"refusal": sha, "since": float(doc.get("epoch") or 0), "knocks": [],
               "person": None, "carried_from": None, "relapses": 0}
        k["current"] = cur
    t = _utc().timestamp()
    entry = {"utc": _stamp(t), "epoch": t, "run_id": os.environ.get("GITHUB_RUN_ID", ""),
             "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
             "by": os.environ.get(KNOCK_BY_ENV, ""), "url": url, "answer": "no answer",
             "said": "", "retry_after": None}
    knocks = cur.setdefault("knocks", [])
    if knocks and isinstance(knocks[-1], dict) and _own_claim(knocks[-1]):
        entry["claimed"] = knocks[-1].get("utc")
        knocks[-1] = entry
    else:
        knocks.append(entry)
    _write_knocks(k)
    return entry


def knocked(answer, said, retry_after=None):
    """What the knock knocking() wrote down was answered: one of
    KNOCK_ANSWERS. Returns what became of the record:

      "lifted"  answer "whole": the record's exact text goes into
                knocks.json's "lifted" with the sha of the bytes the knock
                was for, knocks.json is written, and only then is the record
                removed -- moved, never lost;
      "person"  answer "refused", or "unavailable" asking longer than
                RETRY_AFTER_MOST: the chain's `person` is set, for good;
      "failed"  any other answer: the next rung;
      "kept"    "whole", but the record on file is not the one the knock was
                for: nothing is lifted.

    Raises when there is no knock of this run's written down to answer."""
    if answer not in KNOCK_ANSWERS:
        raise ValueError(f"{answer!r} is not a knock's answer ({', '.join(KNOCK_ANSWERS)})")
    k, ok = read_knocks()
    cur = k.get("current") if ok else None
    last = (cur.get("knocks") or [None])[-1] if isinstance(cur, dict) else None
    if not isinstance(last, dict) or last.get("answer") != "no answer" \
            or str(last.get("run_id")) != os.environ.get("GITHUB_RUN_ID", ""):
        raise RuntimeError("no knock of this run's is written down to answer")
    t = _utc().timestamp()
    last.update(answer=answer, said=str(said)[:300], retry_after=retry_after)
    if answer == "whole":
        try:
            raw = MARK.read_bytes()
        except OSError:
            raw = None
        if raw is None or _sha(raw) != cur.get("refusal"):
            last["said"] = (last["said"] + "; nothing lifted: the refusal on file is not the "
                            "one this knock was for")[:300]
            _write_knocks(k)
            return "kept"
        k["lifted"].append({"refusal": cur["refusal"], "utc": _stamp(t), "epoch": t,
                            "run_id": last.get("run_id"), "attempt": last.get("attempt"),
                            "by": last.get("by"), "said": str(said)[:300],
                            "text": raw.decode("utf-8"), "knocks": cur.get("knocks") or [],
                            "since": cur.get("since"), "relapses": cur.get("relapses") or 0,
                            "carried_from": cur.get("carried_from")})
        k["current"] = None
        _write_knocks(k)
        MARK.unlink()
        return "lifted"
    if answer == "refused" or (answer == "unavailable" and retry_after is not None
                               and float(retry_after) > RETRY_AFTER_MOST):
        cur["person"] = {"utc": _stamp(t), "epoch": t,
                         "why": f"the knock at {last.get('utc')} was answered: {str(said)[:200]}"}
        _write_knocks(k)
        return "person"
    _write_knocks(k)
    return "failed"


def lifted_entry(raw, k=None):
    """knocks.json's "lifted" entry for a record's exact bytes, or None."""
    if raw is None:
        return None
    if k is None:
        k, ok = read_knocks()
        if not ok:
            return None
    sha = _sha(raw)
    return next((x for x in reversed(k.get("lifted") or [])
                 if isinstance(x, dict) and x.get("refusal") == sha), None)


def drops_allowed(now=None):
    """How many dropped connections end a fetch: 1 within RELAPSE_HOURS of
    the last lift, when a drop is evidence and not bad luck, else 2. 1 too
    when knocks.json will not read: the stricter way."""
    k, ok = read_knocks()
    if not ok:
        return 1
    last = k["lifted"][-1] if k["lifted"] else None
    if not isinstance(last, dict):
        return 2
    age = _utc(now).timestamp() - float(last.get("epoch") or 0)
    return 1 if age < RELAPSE_HOURS * HOUR else 2


# ---- the knock's gate (29 October 2026) -------------------------------------
#
# One gate for every knock, whoever asks: knock_gate(). Its callers are two,
# each named by GRANITE_KNOCK_BY (KNOCK_BY_ENV) in the knock child's
# environment: "night", the night's own knock at its start, and "hourly",
# the knock workflow outside the night's hours. Their hours are disjoint --
# the night's inside its daily window, the hourly ones outside every window
# and its margin -- so a caller named wrongly by a mistake refuses; it never
# asks at an hour that is not its own. The night's caller is nightly.knock(),
# at the night's start; the hourly one is .github/workflows/knock.yml's knock
# job, which claims the knock in the bucket before it asks.
# snapshot_gencourt.py --knock is the knock, and check(knock=True) the gate
# it asks first. The workflow's three steps around it are refusal.py's own
# options (main): --knock-look, --knock-claim and --knock-unclaim, and
# --person-line for the sentence the "a refusal is yours" check is sent.

KNOCK_BY = ("night", "hourly")


def knock_hours(by, now=None):
    """(True, "") when the clock alone lets `by` knock at `now`; else
    (False, why).

      night   inside the daily night window (NIGHT_WINDOWS' window for every
              day, from its start that day) and before KNOCK_LATEST, UTC;
      hourly  neither `now` nor the end of the knock's KNOCK_MINUTES falls
              in a night window or the START_MARGIN_MINUTES before one
              (_window_or_soon), the one definition the laptop is held by
              too: never 07:30 to 13:30 UTC today, nor 03:30 to 06:30 on a
              Monday;
      else    never.

    The settle rule, which the hourly caller also needs, turns on the record
    as well as the clock: knock_gate() applies it."""
    from datetime import timedelta
    u = _utc(now)
    if by == "night":
        daily = next(w for w in NIGHT_WINDOWS if w[0] is None)
        (sh, sm), latest = daily[1], KNOCK_LATEST
        start = u.replace(hour=sh, minute=sm, second=0, microsecond=0)
        until = u.replace(hour=latest[0], minute=latest[1], second=0, microsecond=0)
        w = night_window(u)
        if w and daily[3] in w[2] and start <= u < until:
            return True, ""
        return False, (f"it is {u:%H:%M} UTC, and the night knocks only from {sh:02d}:{sm:02d} "
                       f"to {latest[0]:02d}:{latest[1]:02d} UTC, inside its own window, so that "
                       "the knock and the export a lift opens both end before the night stops "
                       "asking")
    if by == "hourly":
        for t in (u, u + timedelta(minutes=KNOCK_MINUTES)):
            hit = _window_or_soon(t)
            if hit:
                kind, s, e, what = hit
                return False, (f"it is {u:%H:%M} UTC, and the hourly knock asks nothing "
                               + (f"inside a night window" if kind == "window" else
                                  f"in the {START_MARGIN_MINUTES} minutes before one")
                               + f" ({s:%H:%M} to {e:%H:%M} UTC, for {what}), for any of "
                               f"its {KNOCK_MINUTES} minutes")
        return True, ""
    return False, (f"{KNOCK_BY_ENV} is {by!r}, not one of {', '.join(KNOCK_BY)}: only the "
                   "night's knock and the hourly one ask, each in its own hours")


def _settled(epoch, now=None):
    """(True, "") when a record noted at `epoch` was noted at least
    KNOCK_SETTLE_MINUTES before the last night window to close by `now`
    (the hourly caller's settle rule); else (False, why).

    WHY (the red team of 29 October 2026, its first finding). A stood-down
    laptop starts a General Court request outside the windows only once its
    pull read the bucket after the last window closed (gc_turn). A record
    in the bucket before that is on every laptop that may ask, and stops it
    there. A record a late night noted after it -- GitHub has started nights
    past 12:30 UTC -- may not be, and an hourly knock beside such a laptop is
    two machines asking at once. So the record's own `epoch`, the drop or
    the relapse that wrote it and not the chain's start, is what is judged;
    and such a record waits for the next morning's night knock, which asks
    inside a window, where the laptop asks nothing."""
    end = last_window_end(now)
    if end is not None and float(epoch) <= end.timestamp() - KNOCK_SETTLE_MINUTES * 60:
        return True, ""
    return False, (f"the refusal was noted at {_stamp(epoch)}, less than {KNOCK_SETTLE_MINUTES} "
                   f"minutes before the last night window closed"
                   + (f" ({_stamp(end.timestamp())})" if end is not None else "")
                   + ", so a laptop that may ask now may not hold it yet: the next morning's "
                   "night knocks, and the hourly knock after the next window closes")


def knock_gate(by, now=None):
    """(True, "") when a knock by `by` ("night" or "hourly") may go now;
    else (False, why), in this project's words. All must hold:

      1. GitHub's machine (GITHUB_ACTIONS "true");
      2. not a dry run: DRY_RUN not "true", and GITHUB_REF MAIN_REF exactly;
      3. a refusal record on file that reads, at any age;
      4. whose() says it is the night's to test (its kind, machine, ref and
         run, the chain in knocks.json, the switch and the settings);
      5. knock_due() says a knock is due now;
      6. the clock lets `by` ask (knock_hours);
      7. for "hourly", the record settled (_settled), by its own epoch;
      8. for "night", nothing asked by the night since today's window
         opened: no knock by the night in the chain, and not the request
         that met this refusal (ONE NIGHT KNOCK A MORNING, below).

    ONE NIGHT KNOCK A MORNING (the reviewers of 30 October 2026). The
    ceiling the owner was given -- 96 requests a chain, at most 19 in a UTC
    day -- counts the night's knock once a morning. Nothing held it there:
    in the hourly phase every main night run between the window's start and
    KNOCK_LATEST knocked in a rung of its own -- a re-run, a run by hand, the
    double night the 'started' job allows -- 100 knocks a chain (102
    requests) and 22 in a day at the worst the reviewers found. So the
    night's caller knocks once in a daily window, the knock answered or not;
    a second night that morning asks nothing. And the morning of the drop
    the night has asked already: a refusal noted since the window opened
    was met by a night that morning (only GitHub's nights on main ask
    then), and a second night knocking after it would be a knock the
    ceiling never counted -- 95 in the ladder, not 94.

    check(knock=True), --knock-claim and --knock-look are its callers."""
    if by not in KNOCK_BY:
        return knock_hours(by, now)
    if os.environ.get("GITHUB_ACTIONS") != "true":
        return False, "only GitHub's machine knocks, and this is not it"
    ref = os.environ.get("GITHUB_REF", "")
    if os.environ.get("DRY_RUN") == "true" or ref != MAIN_REF:
        return False, (f"a dry run knocks nothing (DRY_RUN {os.environ.get('DRY_RUN')!r}, a run "
                       f"of {ref or 'no ref'}): only main's own run may")
    try:
        raw = MARK.read_bytes()
    except OSError:
        return False, "no refusal is on file, so there is nothing to knock for"
    doc = _record(raw)[0]
    who, why = whose(raw, now=now)
    if who != "night":
        return False, f"the refusal on file is a person's to clear, not the night's to test: {why}"
    due, at = knock_due(raw, now=now)
    if not due:
        return False, ("no knock is due" + (f": the next is due from {_stamp(at)}" if at else ""))
    ok, why = knock_hours(by, now)
    if not ok:
        return False, why
    if by == "hourly":
        ok, why = _settled(doc.get("epoch") or 0, now)
        if not ok:
            return False, why
    if by == "night":
        daily = next(w for w in NIGHT_WINDOWS if w[0] is None)
        opened = _utc(now).replace(hour=daily[1][0], minute=daily[1][1], second=0, microsecond=0)
        done = [x for x in (chain(raw) or {}).get("knocks", []) if x.get("by") == "night"
                and float(x.get("epoch") or 0) >= opened.timestamp()]
        met = float(doc.get("epoch") or 0) >= opened.timestamp()
        if done or met:
            return False, ((f"the night knocked at {done[-1].get('utc')}" if done else
                            f"a night met this refusal at {_stamp(float(doc.get('epoch')))}")
                           + f", since its window opened at {opened:%H:%M} UTC today: one night "
                           "knock a morning, however many nights run")
    return True, ""


def knock_claim(now=None):
    """--knock-claim, the hourly caller's: (claimed, why). The gate, for the
    caller GRANITE_KNOCK_BY names, at `now` and again CLAIM_SLACK_MINUTES
    later, with the same knocks.json; only when both pass is a "claimed"
    entry of this run's appended to the chain, which the workflow then sends
    to the bucket BEFORE the knock step may run (the addendum's 1.6). An
    answer the bucket never hears of is then a person's, not a knock asked
    again: a claim older than KNOCK_JOB_MINUTES that no answer replaced makes
    the record a person's (whose(), condition 6). The claim names no address
    -- this file names none of the General Court's -- and the knock writes its
    own into the entry it takes over (knocking)."""
    from datetime import timedelta
    by = os.environ.get(KNOCK_BY_ENV)
    u = _utc(now)
    for t in (u, u + timedelta(minutes=CLAIM_SLACK_MINUTES)):
        ok, why = knock_gate(by, now=t)
        if not ok:
            return False, (why if t == u else f"{CLAIM_SLACK_MINUTES} minutes from now, {why}")
    raw = MARK.read_bytes()
    k, ok = read_knocks()
    if not ok:
        return False, f"{knocks_file()} does not read, and is not written over"
    sha = _sha(raw)
    cur = k.get("current")
    if not (isinstance(cur, dict) and cur.get("refusal") == sha):
        doc = _record(raw)[0]
        cur = {"refusal": sha, "since": float(doc.get("epoch") or 0), "knocks": [],
               "person": None, "carried_from": None, "relapses": 0}
        k["current"] = cur
    t = u.timestamp()
    cur.setdefault("knocks", []).append({
        "utc": _stamp(t), "epoch": t, "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""), "by": by, "url": "",
        "answer": "claimed", "said": "", "retry_after": None})
    _write_knocks(k)
    return True, f"claimed at {_stamp(t)}: the claim goes to the bucket before the knock"


def knock_unclaim():
    """--knock-unclaim: this run's own entries that still read "claimed"
    become "not asked" ("the knock step ended before its request"); any
    other entry is left as it is. knocking() turns a claim into the knock
    BEFORE the request, so a claim still standing once the knock step has
    ended -- the gate declined, the lock was held, a crash, the step's kill
    before knocking() -- asked nothing, and counts nowhere once marked
    (chain(): "not asked" is not counted). Returns how many were marked; 0
    is nothing to do. Raises when knocks.json does not read: it is never
    written over, and a claim left standing becomes a person's, the safe
    way."""
    k, ok = read_knocks()
    if not ok:
        raise RuntimeError(f"{knocks_file()} does not read, so no claim in it can be marked")
    cur = k.get("current")
    marked = 0
    for x in (cur.get("knocks") or []) if isinstance(cur, dict) else []:
        if isinstance(x, dict) and _own_claim(x):
            x.update(answer="not asked", said="the knock step ended before its request")
            marked += 1
    if marked:
        _write_knocks(k)
    return marked


def person_line(d=None, k=None, now=None, tested=False, said_no=""):
    """The one sentence that says a refusal is a person's: "" when no record
    is on file or the night may test it (whose()), else the record, why it
    is a person's, and what clears it, in this project's words and none of a
    server's. For a block-type answer -- a record of the kind "refused", or a
    knock answered that way -- it says the IT office or the Clerk's office may
    need a message. The night sends it to the "a refusal is yours" check
    (nightly.person_alerts_of), and so do the knock workflow's two pingers.

    `tested`: only a record the night was testing -- knocks.json's "current"
    names it -- for the knock workflow, which reports the records it tests
    and leaves every other to the night.

    `said_no`: why a knock its caller ran was answered no although the
    chain may not say so -- the child exited 2, a block-type answer, and the
    answer could not be written down (snapshot_gencourt.knock). The record is
    then a person's whatever whose() says, for that reason: the knock's
    caller hears it at once, and whose() only KNOCK_JOB_MINUTES later."""
    doc, raw = _record(d)
    if raw is None:
        return ""
    who, why = whose(raw, k, now)
    if who != "person":
        if not said_no:
            return ""
        why = said_no
    c = chain(raw, k)
    if tested and not (c and c["named"]):
        return ""
    told_no = doc.get("kind") == "refused" or bool(c and c.get("person")) or bool(said_no)
    epoch = doc.get("epoch")
    try:
        when = _stamp(float(epoch))
    except (TypeError, ValueError):
        when = "an unknown time"
    return (f"A REFUSAL IS YOURS: the General Court refusal met by {doc.get('where') or 'a fetch'} "
            f"at {when} is a person's to clear: {why}. Nothing asks the General Court's website "
            "or its database for it until a person does: python3 netcheck.py on the laptop says "
            "what kind it was (read its table, not its last line), then python3 "
            "src/ops/cloud.py clear-refusal, and python3 refusal.py --clear where a copy is on "
            "file."
            + (" The address was told no: the General Court's IT office or the Clerk's office "
               "may need a message before anything asks again." if told_no else ""))


def knock_look(now=None):
    """--knock-look, the hourly workflow's look: {"go", "until", "why"}.

    go     True only when knock_gate("hourly") passes now -- GitHub, main,
           not a dry run, a record the night tests, a knock due, the hourly
           hours and the settle rule -- and the knock job may still end
           before the night's hours: now is no later than `until`;
    until  the next window's start, less its START_MARGIN_MINUTES, the knock
           job's KNOCK_JOB_MINUTES and the knock's KNOCK_MINUTES, as an
           epoch: the quiet job queues no knock after it;
    why    one line, for the run's log and its dry runs' proof: whose the
           record is, when its next knock is due, the settings, and why not.
    """
    from datetime import timedelta
    u = _utc(now)
    hourly, every, days, bad = knock_settings()
    n = next_window(u)
    until = (n[0] - timedelta(minutes=START_MARGIN_MINUTES + KNOCK_JOB_MINUTES + KNOCK_MINUTES)
             if n else None)
    ok, gate = knock_gate("hourly", now=u)
    go = ok and until is not None and u <= until
    said = []
    try:
        raw = MARK.read_bytes()
    except OSError:
        raw = None
    if raw is None:
        said.append("no refusal is on file")
    else:
        who, why = whose(raw, now=u)
        said.append(f"the refusal on file is {'the night' if who == 'night' else 'a person'}'s"
                    f": {why}")
        if who == "night":
            due, at = knock_due(raw, now=u)
            said.append("a knock is due now" if due else
                        f"the next knock is due from {_stamp(at)}" if at else "no knock is due")
    said.append(bad or f"the settings: one an hour for {hourly} hours from the refusal, then one "
                       f"in each {every}-hour span, for {days} days")
    if go:
        said.append(f"the hourly knock may go now, its job ending by {_stamp(until.timestamp())}")
    elif ok:
        said.append("but the knock job could not end before the night's hours")
    else:
        said.append(f"no hourly knock now: {gate}")
    return {"go": go, "until": int(until.timestamp()) if until is not None else "",
            "why": "; ".join(s.replace("\n", " ") for s in said)}


# ---- one worker ------------------------------------------------------------
#
# archive/.lock says a fetch from the General Court is running. Only three
# fetchers ever looked at it, one of them deleted any lock more than an hour
# old, and nothing refreshed one while it ran -- so any run longer than an hour
# could be joined by a second worker, which is how this address was blocked
# the second time. hold() is the rule in one place: take the lock, or run
# under the lane that holds it (watchers/gc_lane.py, whose pid is in the lock
# and who is this process's parent), or do not run at all.

LOCK = Path("archive/.lock")

# The file a run's hold writes when GitHub's night window stops it, named by
# whoever started the run -- watchers/gc_lane.py, for each step. A fetch cut
# short by the window used to end 0 (fetch_senate_calendars and
# fetch_sponsors_by_member return 0 from a loop that stopped early), 1 or 3,
# and the lane recorded a step that had not finished as done, or a day's
# step as run. The status cannot carry it for every script; this file does.
WINDOW_STOP_ENV = "GRANITE_WINDOW_STOP"


class hold:
    """with refusal.hold("fetch_legislation"): ... -- one worker, or none.

    `window` is the night window that stopped this run, once still() has
    said so, and None until then. A block that ends normally, or by
    sys.exit(0), after that leaves by SystemExit(STOOD_DOWN): a run the
    window cut short did not finish, and must not say it did. Any other
    ending -- a refusal's 2, a lost lock's 3, an exception -- goes on as it
    was. release() lets go of the lock without that, for a caller that
    registers it with atexit, where a SystemExit is only printed."""

    def __init__(self, who):
        self.who, self.mine, self._stop, self._told = who, False, None, False
        self.window = None

    def __enter__(self):
        import os
        import threading
        if LOCK.exists():
            held = LOCK.read_text(encoding="utf-8", errors="replace").strip()
            if held.isdigit() and int(held) == os.getppid():
                return self            # the lane that started us holds it
            print(f"\narchive/.lock is held (pid {held or '?'}): another "
                  f"fetch from the General Court is running, and {self.who} "
                  "will not be a second one. If nothing is running, a "
                  "person may remove the lock.\n", file=sys.stderr)
            sys.exit(3)
        LOCK.parent.mkdir(exist_ok=True)
        LOCK.write_text(str(os.getpid()), encoding="utf-8")
        self.mine = True
        # Touched every minute, so no rule about a lock's age can mistake a
        # long run for an abandoned one.
        self._stop = threading.Event()

        def beat():
            while not self._stop.wait(60):
                try:
                    os.utime(LOCK, None)
                except OSError:
                    pass
        threading.Thread(target=beat, daemon=True).start()
        return self

    def still(self):
        """Whether this run may still ask for anything. Before every request.

        A run that took the lock keeps it fresh itself. A run under the lane
        relies on the lane's heartbeat, so it checks that the lane is still
        there: the lock present, naming our parent, touched within three
        minutes. A lane killed hard leaves its child fetching with nobody
        refreshing the lock, and a lock nobody refreshes is one any other
        fetcher may decide is abandoned.

        And on a stood-down laptop, False from the moment GitHub's night
        window opens, whoever holds the lock: check() lets nothing start in
        the half hour before it, but a run started earlier would otherwise go
        on asking the General Court beside the night. It says so once, and
        remembers it (`window`, and the WINDOW_STOP_ENV file when one is
        named), so the run cannot end as though it had finished."""
        import os
        w = night_window() if _governing() is not None else None
        if w:
            if not self._told:
                self._told = True
                self.window = w
                _tell_the_starter(self.who, w)
                s, e, what = w
                print(f"\n{self.who} stops before its next request: GitHub's night window "
                      f"opened at {_clock(s)} -- {describe_window(s, e, what)} -- and no General "
                      "Court request is made on this laptop inside it, one fetch at a time "
                      f"across both machines. Start it again after {_clock(e)}.{_clock_note()} "
                      "Whatever this run says next about archive/.lock, this is why it "
                      "stopped.\n", file=sys.stderr, flush=True)
            return False
        if self.mine:
            return True
        try:
            held = LOCK.read_text(encoding="utf-8", errors="replace").strip()
            fresh = time.time() - LOCK.stat().st_mtime < 180
        except OSError:
            return False
        return held.isdigit() and int(held) == os.getppid() and fresh

    def release(self):
        """Let go of the lock, if this run took it. Nothing else."""
        if self.mine:
            self.mine = False
            self._stop.set()
            # Only our own lock. Another worker's is not ours to remove.
            try:
                if LOCK.read_text(encoding="utf-8").strip() == str(__import__("os").getpid()):
                    LOCK.unlink(missing_ok=True)
            except OSError:
                pass

    def __exit__(self, kind, value, tb):
        self.release()
        finished = kind is None or (kind is SystemExit and getattr(value, "code", None) in (0, None))
        if self.window and finished:
            s, e, _ = self.window
            print(f"{self.who} ends with status {STOOD_DOWN}, the stand-down's, not as finished: "
                  f"GitHub's night window, open since {_clock(s)}, stopped it before it was "
                  f"done. Start it again after {_clock(e)}.{_clock_note()}",
                  file=sys.stderr, flush=True)
            raise SystemExit(STOOD_DOWN)
        return False


def _tell_the_starter(who, w):
    """Write the file WINDOW_STOP_ENV names, when the process that started
    this one named one: the lane reads it after the step, whatever status the
    step ends with. Never raises -- the run is stopping either way."""
    p = os.environ.get(WINDOW_STOP_ENV, "").strip()
    if not p:
        return
    try:
        s, e, what = w
        Path(p).write_text(json.dumps({
            "who": who, "pid": os.getpid(), "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "window": f"{s:%Y-%m-%dT%H:%M}Z to {e:%Y-%m-%dT%H:%M}Z"}, indent=1),
            encoding="utf-8")
    except (OSError, TypeError, ValueError):
        pass


# ---- the stand-down ---------------------------------------------------------
#
# The file that says this machine has handed the nightly and publishing to
# GitHub. It is read here rather than in each script so that "does this run on
# the laptop any more" has one answer, and so that GitHub's own machine can
# never be stood down by a copy of the file arriving there by mistake.

STANDDOWN = Path("archive/runs-in-the-cloud.json")
STOOD_DOWN = 4          # the exit status of a job this machine has handed over
# The knock's "not asked" (check(knock=True)): the stand-down's status, for
# the same reason -- waiting for a turn is not the address saying no.
KNOCK_NOT_NOW = STOOD_DOWN


def stood_down():
    """What the stand-down file says, or None when this machine may run it.

    None on GitHub's machine whatever is on disk: GITHUB_ACTIONS is "true"
    there, and the stand-down is about the laptop.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true" or not STANDDOWN.exists():
        return None
    try:
        d = json.loads(STANDDOWN.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        d = {}
    return d if isinstance(d, dict) else {}


def stand_down(who, instead=""):
    """Stop the caller on a machine that has handed its job to GitHub."""
    d = stood_down()
    if d is None:
        return
    print(f"\n{who} does not run on this machine any more: GitHub runs it, "
          f"since {d.get('since') or '(no date given)'}. {STANDDOWN} says so.\n"
          + (f"{instead}\n" if instead else "")
          + f"Moving it back is deleting {STANDDOWN}: a person's decision, made "
          "after this machine's copy of the data has been brought up to date "
          "from R2.\n", file=sys.stderr)
    sys.exit(STOOD_DOWN)


# ---- GitHub's night window ---------------------------------------------------
#
# The one definition of when GitHub's machine may be asking the General Court,
# in UTC because GitHub's cron has no time zone. The nightly starts at 08:17
# and asks the General Court only in its first part: the day's files, and when
# they come back empty its database at once (since 2 October 2026) and, only
# if that cannot be used, the same files once more half an hour later
# (nightly.TRIES_AFTER_DB), so a scheduled night waits half an hour at most
# while it asks. The window was drawn for the nights before that, which asked
# every half hour, up to six tries in all (nightly.EMPTY_TRIES), and had
# stopped by about 11:15 on the worst night and 12:15 with an hour's late
# start; a New term run, which a person starts by hand, still asks that
# way, and preflight holds the six tries inside the window. It runs to
# 13:30 because GitHub often starts a scheduled run late. It started at
# 06:17 until 27 September 2026, and moving it did not stop the night meeting
# half-written files (.github/workflows/nightly.yml has the evidence); it
# moves with the workflow's cron line. The weekly starts at 04:17 on
# Monday and is allowed two hours, so a Monday has two windows, 04:00 to 06:30
# and 08:00 to 13:30, and a fetch may start here between them, from 06:30 to
# the half hour before the second. A start later than an hour past 08:17 is
# still the known weakness, and so, on a Monday, is a weekly started late
# enough to run past 06:30, which the night's window no longer covers since
# it moved; HANDOFF.md says so.

NIGHT_WINDOWS = (
    # (weekday or None for every day, start, end, what), UTC; weekday 0 is Monday
    (None, (8, 0), (13, 30), "the nightly, which GitHub starts at 08:17 UTC, often late, "
                             "and allows four hours"),
    (0, (4, 0), (6, 30), "Monday's weekly job, which GitHub starts at 04:17 UTC and "
                         "allows two hours"),
)

# No General Court request STARTS in this many minutes before a window opens,
# so that none started just before it is still asking inside it. A run that
# asks hold().still() before each request stops at the window's start anyway;
# this is for the ones that do not, and for the SQL host, whose bridges
# cannot be stopped halfway through a query.
START_MARGIN_MINUTES = 30

# Tests only: the time the window is judged at, as ISO 8601 UTC, for a test
# that runs a script as a child and cannot hand it a clock. Every sentence
# the guards print says so when it is set.
CLOCK_ENV = "GRANITE_CLOCK_UTC"

# How soon before a window check() mentions it, between this and
# START_MARGIN_MINUTES, when it still lets a fetch start.
SOON_MINUTES = 60


def _governing():
    """The stand-down that governs MARK -- the file beside it -- or None.

    In the working folder that is stood_down()'s answer exactly: MARK is
    archive/refused.json and the stand-down archive/runs-in-the-cloud.json. A
    test that points MARK at a folder of its own is governed by that folder,
    never by the machine running it -- the guards below exit and send, and a
    check that drives a fetcher on the stood-down laptop at 08:30 UTC must not
    fail for the time of day, or send its made-up refusal to the real bucket.
    Never on GitHub's machine.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return None
    p = MARK.parent / STANDDOWN.name
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        d = {}
    return d if isinstance(d, dict) else {}


def _utc(now=None):
    """An aware UTC datetime: `now` as given (aware, naive-as-UTC, or an epoch),
    or GRANITE_CLOCK_UTC when set, or the clock."""
    from datetime import datetime, timezone
    if now is None:
        raw = os.environ.get(CLOCK_ENV, "").strip()
        if raw:
            try:
                now = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                print(f"{CLOCK_ENV}={raw!r} is not an ISO time; the real clock is used",
                      file=sys.stderr)
                now = None
        if now is None:
            return datetime.now(timezone.utc)
    if isinstance(now, (int, float)):
        return datetime.fromtimestamp(now, timezone.utc)
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def _spans(now):
    """GitHub's windows from two days before `now` to two after, merged where
    they overlap or touch: [(start, end, [what, ...])], sorted."""
    from datetime import datetime, timedelta, timezone
    out = []
    for k in range(-2, 3):
        d = now.date() + timedelta(days=k)
        for wd, (sh, sm), (eh, em), what in NIGHT_WINDOWS:
            if wd is not None and d.weekday() != wd:
                continue
            s = datetime(d.year, d.month, d.day, sh, sm, tzinfo=timezone.utc)
            e = datetime(d.year, d.month, d.day, eh, em, tzinfo=timezone.utc)
            out.append((s, e if e > s else e + timedelta(days=1), what))
    merged = []
    for s, e, what in sorted(out, key=lambda x: (x[0], x[1])):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
            merged[-1][2].append(what)
        else:
            merged.append([s, e, [what]])
    return [(s, e, w) for s, e, w in merged]


def night_window(now=None):
    """(start, end, what) of the window `now` falls in -- start <= now < end --
    or None. Anywhere: whether it applies is gc_turn()'s question."""
    now = _utc(now)
    for s, e, w in _spans(now):
        if s <= now < e:
            return s, e, ", and then ".join(w)
    return None


def last_window_end(now=None):
    """When the most recent window that has closed by `now` closed."""
    now = _utc(now)
    ends = [e for _, e, _ in _spans(now) if e <= now]
    return max(ends) if ends else None


def next_window(now=None):
    """(start, end, what) of the next window to open after `now`."""
    now = _utc(now)
    later = [(s, e, ", and then ".join(w)) for s, e, w in _spans(now) if s > now]
    return min(later) if later else None


def eastern(dt):
    """(wall-clock time, "EDT" or "EST") in New Hampshire for an aware time.

    By hand, because Python on Windows has no time zone database here: daylight
    time from 2 a.m. on the second Sunday of March (07:00 UTC) to 2 a.m. on
    the first Sunday of November (06:00 UTC), the US rule since 2007.
    """
    from datetime import date, datetime, timedelta, timezone
    dt = _utc(dt)

    def sunday(month, nth):
        d = date(dt.year, month, 1)
        return d + timedelta(days=(6 - d.weekday()) % 7 + 7 * (nth - 1))
    on = datetime.combine(sunday(3, 2), datetime.min.time(), timezone.utc) + timedelta(hours=7)
    off = datetime.combine(sunday(11, 1), datetime.min.time(), timezone.utc) + timedelta(hours=6)
    hours, zone = (4, "EDT") if on <= dt < off else (5, "EST")
    return (dt - timedelta(hours=hours)).replace(tzinfo=None), zone


def _clock(dt, weekday=False):
    t, zone = eastern(dt)
    h = t.hour % 12 or 12
    return (f"{t:%A} " if weekday else "") + f"{h}:{t.minute:02d} " \
        + ("a.m." if t.hour < 12 else "p.m.") + f" {zone}"


def _until(then, now):
    mins = max(0, int((then - now).total_seconds() // 60))
    return f"{mins // 60} h {mins % 60:02d} min" if mins >= 60 else f"{mins} min"


def describe_window(s, e, what):
    """The window in the words a person in New Hampshire reads it in."""
    same_day = eastern(s)[0].date() == eastern(e)[0].date()
    return (f"{_clock(s, weekday=True)} to {_clock(e, weekday=not same_day)} "
            f"({s:%H:%M} to {e:%H:%M} UTC), for {what}")


def _clock_note():
    raw = os.environ.get(CLOCK_ENV, "").strip()
    return f" (The time is {CLOCK_ENV}'s, {raw}, not the clock's.)" if raw else ""


def _pull_read():
    """When `cloud.py pull` last read the REAL bucket's refusal record, as an
    epoch, or None: it records that in archive/cloud/pull.json, with the
    kind of bucket it read. Only a read of R2 counts. A pull from a
    --local-bucket folder is a test, and a folder cannot know of a refusal
    the night met, so a read of one freeing this laptop's fetches would be
    trusting it about something it could not know."""
    try:
        d = json.loads((MARK.parent / "cloud" / "pull.json").read_text(encoding="utf-8"))
        r = d.get("refusal") or {}
        if r.get("kind") != "r2":
            return None
        return float(r.get("read") or 0) or None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


# A REFUSAL CLEARED HERE IS READ AGAIN FROM THE BUCKET FIRST (29 October
# 2026, the hourly addendum's 7, item 2). On a stood-down laptop --clear
# writes this, beside the record, and a read of the bucket from before it is
# no read: the next General Court request here waits for a pull, which
# brings the bucket's refusal back if it still stands. cloud.py's pull.json
# stays cloud.py's alone.
CLEARED = Path("archive/refusal-cleared.json")


def cleared_file():
    """CLEARED, beside the refusal record it is about."""
    return MARK.parent / CLEARED.name


def cleared_at():
    """When a person last cleared a refusal on this stood-down laptop, as an
    epoch, or None when none is recorded; infinity when the record of it
    does not read, the stricter way: the next fetch pulls first."""
    try:
        raw = cleared_file().read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return float("inf")
    try:
        return float(json.loads(raw)["epoch"])
    except (ValueError, KeyError, TypeError):
        return float("inf")


def refusal_read():
    """When this machine last read the REAL bucket's refusal record, as an
    epoch, or None (_pull_read): None too while a person has cleared a
    refusal here since that read (cleared_at), so that the clear is never
    taken for the bucket's word."""
    read, cleared = _pull_read(), cleared_at()
    if read is not None and cleared is not None and cleared >= read:
        return None
    return read


def _window_or_soon(now):
    """("window", start, end, what) when `now` is inside a window, ("soon", ...)
    for the next one when it opens within START_MARGIN_MINUTES, or None."""
    w = night_window(now)
    if w:
        return ("window",) + tuple(w)
    n = next_window(now)
    if n and (n[0] - now).total_seconds() <= START_MARGIN_MINUTES * 60:
        return ("soon",) + tuple(n)
    return None


def gc_turn(now=None):
    """None when this machine may start a General Court request now; otherwise
    (kind, sentence), kind "window", "soon" or "pull". Only a stood-down
    laptop is ever held: GitHub's own machine and a laptop that has not handed
    the night over are never, whatever the time."""
    if _governing() is None:
        return None
    now = _utc(now)
    hit = _window_or_soon(now)
    if hit and hit[0] == "window":
        _, s, e, what = hit
        return "window", (
            f"GitHub's night may be asking the General Court now: its window is "
            f"{describe_window(s, e, what)}, and no General Court request starts on this "
            f"laptop inside it -- one fetch at a time, across both machines. It ends at "
            f"{_clock(e)}, in {_until(e, now)}; start this again then." + _clock_note())
    if hit:
        _, s, e, what = hit
        return "soon", (
            f"GitHub's night window opens at {_clock(s)}, in {_until(s, now)}: it is "
            f"{describe_window(s, e, what)}, and no General Court request starts on this "
            f"laptop in the {START_MARGIN_MINUTES} minutes before it, so that none is still "
            f"asking when it opens. Start this again after {_clock(e)}." + _clock_note())
    closed = last_window_end(now)
    read, pulled = refusal_read(), _pull_read()
    if read is None or _utc(read) < closed:
        cleared = cleared_at()
        when = ((f"had a refusal cleared by hand (python3 refusal.py --clear) "
                 + (f"at {_clock(_utc(cleared), weekday=True)} " if cleared != float("inf") else
                    f"({cleared_file()} does not say when) ")
                 + f"after it last read that record, at {_clock(_utc(pulled), weekday=True)}: "
                   "the bucket's may still stand, and the pull brings it back if it does")
                if read is None and pulled is not None else
                "has never read that record from the real bucket (a --local-bucket "
                "pull does not count)" if read is None else
                f"last read that record at {_clock(_utc(read), weekday=True)} "
                f"({_utc(read):%Y-%m-%d %H:%M} UTC), before the last night window closed "
                f"at {_clock(closed, weekday=True)}")
        return "pull", (
            f"GitHub's night records a refusal it meets in the bucket's state/refused.json, "
            f"not here, and this laptop {when}. A refusal the night met would be "
            f"invisible to this fetch. Read it first:\n"
            f"  python3 src/ops/cloud.py pull --changes-only     (or a full pull)\n"
            f"and start this again." + _clock_note())
    return None


def window_check(who=""):
    """Stop the caller inside GitHub's night window on a stood-down laptop,
    or in the START_MARGIN_MINUTES before it.

    The window alone: for the General Court's SQL host, which the night and the
    weekly query too (the study committees' views, the rosters), but whose
    refusals are a different problem from the web server's, so neither the
    refusal record nor the pull governs it. probe_db calls this before every
    query, and the half hour before counts because a query, once started,
    cannot be stopped at the window's edge the way hold().still() stops a
    fetch between requests."""
    if _governing() is None:
        return
    now = _utc()
    hit = _window_or_soon(now)
    if not hit:
        return
    kind, s, e, what = hit
    print(f"\n{who or 'This query'} is not starting: "
          + (f"GitHub's night may be querying the General Court's database now. Its window "
             f"is {describe_window(s, e, what)}, and it ends at {_clock(e)}, in "
             f"{_until(e, now)}; start this again then." if kind == "window" else
             f"GitHub's night window opens at {_clock(s)}, in {_until(s, now)} -- "
             f"{describe_window(s, e, what)} -- and no query starts in the "
             f"{START_MARGIN_MINUTES} minutes before it. Start this again after {_clock(e)}.")
          + _clock_note() + "\n", file=sys.stderr)
    sys.exit(STOOD_DOWN)


def window_soon(now=None):
    """A sentence when a window opens within SOON_MINUTES on a stood-down
    laptop, but more than START_MARGIN_MINUTES away (inside that, gc_turn
    refuses), or ""."""
    if _governing() is None:
        return ""
    now = _utc(now)
    n = next_window(now)
    if not n or (n[0] - now).total_seconds() > SOON_MINUTES * 60:
        return ""
    s, e, what = n
    return (f"GitHub's night window opens at {_clock(s)}, in {_until(s, now)}. A fetch that asks "
            "refusal.hold() before each request stops at its first one inside it; one that "
            f"does not keeps asking. A long one belongs after {_clock(e)}." + _clock_note())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true",
                    help="lift the standing refusal; a person's decision")
    ap.add_argument("--stand-down", action="store_true",
                    help="hand the nightly and publishing to GitHub: write "
                         f"{STANDDOWN}; a person's decision")
    # The knock workflow's steps (THE KNOCK'S GATE): each prints what the
    # step's outputs are, key=value lines for GITHUB_OUTPUT, on stdout, and
    # its sentence on stderr, for the log. None asks anything of anyone.
    ap.add_argument("--knock-look", action="store_true",
                    help="whether an hourly knock may go now: go=, until= and why= lines")
    ap.add_argument("--knock-claim", action="store_true",
                    help="claim the knock for this run, if the gate lets it go now and "
                         f"{CLAIM_SLACK_MINUTES} minutes from now: claimed= and why= lines")
    ap.add_argument("--knock-unclaim", action="store_true",
                    help="mark this run's claim that no knock took up as not asked")
    ap.add_argument("--person-line", action="store_true",
                    help="write the \"a refusal is yours\" sentence for a refusal the night "
                         "was testing, or nothing, to --person-file")
    ap.add_argument("--person-file", metavar="PATH",
                    help="where --person-line and --knock-look write that sentence: "
                         "logs/alert-person.txt, the body of the third check's /fail")
    ap.add_argument("--knock-rc", metavar="STATUS", default="",
                    help="with --person-line: the knock step's exit status. 2, a block-type "
                         "answer, is a person's even where its answer could not be written down "
                         "(then the sentence says so, and this exits 1)")
    a = ap.parse_args()
    if a.knock_look or a.knock_claim or a.knock_unclaim or a.person_line:
        return knock_step(a)
    if a.stand_down:
        if STANDDOWN.exists():
            print(f"{STANDDOWN} is already on file: this machine is stood down.")
            return 0
        STANDDOWN.parent.mkdir(exist_ok=True)
        STANDDOWN.write_text(json.dumps({
            "since": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "what": "GitHub's workflows run the nightly, the weekly fetches and "
                    "publishing. This machine keeps the one-off jobs.",
        }, indent=1), encoding="utf-8")
        print(f"wrote {STANDDOWN}. The nightly, the daily snapshot, publish and "
              "the fetchers GitHub owns now refuse here. Deleting it moves back.")
        return 0
    if stood_down() is not None:
        print(f"stood down: {STANDDOWN} hands the nightly and publishing to GitHub.")
        w, n = night_window(), next_window()
        if w:
            print(f"GitHub's night window is open: {describe_window(*w)}.{_clock_note()}")
        elif n:
            print(f"GitHub's night window is closed; the next is {describe_window(*n)}."
                  + _clock_note())
        read, pulled, turn = refusal_read(), _pull_read(), gc_turn()
        print("the bucket's refusal record "
              + ("has never been read here from the real bucket" if pulled is None else
                 f"was last read here at {_clock(_utc(pulled), weekday=True)}"
                 + (", before a refusal was cleared here by hand" if read is None else ""))
              + ("; General Court fetches here wait for python3 src/ops/cloud.py pull --changes-only"
                 if turn and turn[0] == "pull" else
                 f"; nothing starts in the {START_MARGIN_MINUTES} minutes before the window"
                 if turn and turn[0] == "soon" else
                 "; General Court fetches here may start outside the window" if not w else ""))
        if unsent_marker().exists():
            try:
                why = json.loads(unsent_marker().read_text(encoding="utf-8")).get("why") or ""
            except (OSError, ValueError, AttributeError):
                why = ""
            print(f"{unsent_marker()} is on file: a refusal met here is not in the bucket"
                  + (f" ({why})" if why else "")
                  + ". python3 src/ops/cloud.py send-refusal sends it when the bucket holds none.")
    s = standing()
    if not a.clear:
        say_whose()
    if a.clear:
        # ON A STOOD-DOWN LAPTOP THE NEXT FETCH PULLS FIRST (CLEARED): written
        # before the record goes, so that a clear whose note cannot be
        # written clears nothing.
        governed = _governing() is not None
        if governed:
            try:
                t = _utc().timestamp()
                cleared_file().parent.mkdir(exist_ok=True)
                cleared_file().write_text(json.dumps({"utc": _stamp(t), "epoch": t}, indent=1),
                                          encoding="utf-8")
            except OSError as e:
                print(f"nothing cleared: {cleared_file()}, which makes the next fetch here read "
                      f"the bucket first, could not be written ({type(e).__name__}: {e}).",
                      file=sys.stderr)
                return 1
        if MARK.exists():
            MARK.unlink()
            print("refusal cleared here. " + (
                "The next General Court request here waits for python3 src/ops/cloud.py pull "
                "--changes-only, which brings the bucket's refusal back if it still stands: "
                "clear that one first with python3 src/ops/cloud.py clear-refusal."
                if governed else "Fetches on this machine may run again."))
        else:
            print("there was no refusal on record here."
                  + (" The next General Court request here waits for python3 src/ops/cloud.py "
                     "pull --changes-only all the same." if governed else ""))
        # A refusal lifted by a person needs no sending: the marker that says
        # the bucket was never told of it goes with it.
        if unsent_marker().exists():
            unsent_marker().unlink()
            print(f"{unsent_marker()} removed with it: the bucket need not be told of a "
                  "refusal a person has lifted.")
        # THE NIGHTLY'S COPY IS THE BUCKET'S. GitHub's machine starts empty and
        # takes its refusal record from R2's state/refused.json, so clearing
        # this file leaves that one stopping every night until it is lifted
        # too -- and cloud.py, which talks to the bucket, is what lifts it.
        if governed:
            print("The nightly runs on GitHub and takes its refusal record from the "
                  "bucket's state/refused.json, not this one: python3 src/ops/cloud.py "
                  "clear-refusal lifts that one.")
        return 0
    if not s:
        print("no refusal on file." if not MARK.exists() else
              f"the recorded refusal is older than {QUIET_HOURS}h: hand fetches here are no "
              "longer stopped by it, but the lane and GitHub's night still are, for as long as "
              "it is on file.")
        return 0
    d, hours = s
    print(f"refused {hours:.1f}h ago by {d.get('where')}: {d.get('why')}")
    print("every fetch is stopped until: python3 refusal.py --clear")
    return 0


def knock_step(a):
    """The knock workflow's steps, one per option: --knock-look, then
    --knock-claim, --knock-unclaim, and --person-line, each optionally with
    --person-file. Exit 0 whatever the answer; 1 only for what went wrong
    (an unclaim that cannot read knocks.json, or --person-line --knock-rc 2
    where the knock's answer was not written down), so a step fails visibly
    rather than saying nothing."""
    def out(**kv):
        for key, value in kv.items():
            print(f"{key}={str(value).replace(chr(10), ' ')}", flush=True)

    def person(text):
        if a.person_file:
            p = Path(a.person_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text + ("\n" if text else ""), encoding="utf-8")
    if a.knock_look:
        look = knock_look()
        out(go="true" if look["go"] else "false", until=look["until"], why=look["why"])
        print(f"the knock's look: {look['why']}.{_clock_note()}", file=sys.stderr)
        # Only outside the night's hours: inside them the bucket the look
        # read can be minutes behind the night, which reports its own record.
        line = person_line(tested=True) if knock_hours("hourly")[0] else ""
        person(line)
        if line:
            print(line, file=sys.stderr)
        return 0
    if a.knock_claim:
        claimed, why = knock_claim()
        out(claimed="true" if claimed else "false", why=why)
        print(f"the knock's claim: {why}.{_clock_note()}", file=sys.stderr)
        return 0
    if a.knock_unclaim:
        try:
            n = knock_unclaim()
        except RuntimeError as e:
            print(f"the knock's claim could not be marked: {e}. A claim still standing in the "
                  f"bucket becomes a person's after {KNOCK_JOB_MINUTES} minutes, and the "
                  "\"a refusal is yours\" check is told.", file=sys.stderr)
            return 1
        print(f"this run's claim, which no knock took up, is marked not asked ({n})." if n else
              "no claim of this run's stands unanswered: nothing to mark.", file=sys.stderr)
        return 0
    line = person_line(tested=True)
    # THE ANSWER NOT WRITTEN DOWN (whose()): the knock exited 2, the address
    # said no, but the chain does not say so yet. A person's now, and the
    # step fails, so the run is red as well as the email sent.
    lost = str(a.knock_rc).strip() == "2" and not line
    if lost:
        line = person_line(tested=True, said_no=(
            "this run's knock exited 2 -- the address said no -- and its answer could not be "
            "written down; the bucket holds it as \"no answer\", which every reader takes as the "
            f"worst answer {KNOCK_JOB_MINUTES} minutes after it was made"))
    person(line)
    print(line or "no refusal the night was testing has become a person's.", file=sys.stderr)
    return 1 if lost else 0


def say_whose(now=None):
    """refusal.py's status: whose the record on file is, and, for one the
    night is testing, when the next knock is due; for one a knock lifted,
    who lifted it and when."""
    try:
        raw = MARK.read_bytes()
    except OSError:
        return
    lift = lifted_entry(raw)
    if lift:
        print(f"this refusal was {force({}, now, lift)}.")
        return
    who, why = whose(raw, now=now)
    if who == "night":
        due, at = knock_due(raw, now=now)
        print(f"the night is testing this refusal itself: {why}. "
              + ("A knock is due now." if due else
                 f"The next knock is due from {_stamp(at)}." if at else "")
              + f" If each fails: {knock_schedule(raw)}.")
    elif _its_own(_record(raw)[0])[0] and os.environ.get("GITHUB_ACTIONS") != "true":
        print("GitHub's night met this refusal, and decides whether it tests it itself; its "
              "run page says. A copy on file here stops every fetch here, at any age, and is a "
              "person's to clear: python3 refusal.py --clear.")
    else:
        print(f"this refusal is a person's to clear: {why}.")


if __name__ == "__main__":
    sys.exit(main())
