#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-02.1
"""
The day a build says it was made, asked for in one place.

    python3 build_all.py --local                     # today, by the clock

    set GRANITE_BUILD_DATE=2026-10-02                # cmd; `export` in a shell
    python3 build_all.py --local                     # 2 October, whatever today is

WHY THIS EXISTS

The day the site was built is written into every page: it is the date a
citation falls back on for a reader without JavaScript (shell.BUILT). The
sitemap dates every address with it, every feed carries it as lastBuildDate,
the bulk downloads' manifest says when it was generated -- and a dozen
builders ask what today is to decide what is still to come: this week's
sittings, the next fortnight's hearings, a committee that "is scheduled to
meet" and not one that "met".

So two builds of the same code over the same data, made on different days,
differ in every page. A change that is meant to leave the site alone is proved
here by building it before and after and comparing a sha256 of every file,
and that comparison could only be made between two builds of the same day.

GRANITE_BUILD_DATE states the day instead. Every builder that asked the clock
asks here, so a build made on Tuesday with Monday's date stated is Monday's
build. A day (2026-10-02) is that day at midnight; a day and a time
(2026-10-02T14:30:00) is that moment, read as the local clock and as UTC
alike, since a stated moment has no zone to convert between. Anything else
stops the build: a mistyped date that fell back on the clock would be a
comparison of two different days that looked like one.

WITHOUT IT NOTHING CHANGES. Each function below returns what the call it
replaced returned: the local day, the local time, the time in UTC.

IT IS FOR COMPARING BUILDS, NOT FOR PUBLISHING ONE. A page built this way
cites a day that is not the day it was built. build_all.py says so when the
date is stated and records it in site/build.json.

WHAT STILL READS THE CLOCK, on purpose: build_all.py's own record of the run
in site/build.json -- when it finished, how long each step took -- which is
about the run and is left out of any comparison; the fetchers' "asked on"
stamps and the lane's, the night's and the bucket's records, which are about
a request or a run and not about a page; and the browser, which puts the
reader's own date in a citation where it can.
"""

import datetime
import os

ENV = "GRANITE_BUILD_DATE"


def stated():
    """The moment the environment states, as a datetime with no zone, or None
    where it states none."""
    raw = os.environ.get(ENV, "").strip()
    if not raw:
        return None
    try:
        when = datetime.datetime.fromisoformat(raw)
    except ValueError:
        when = None
    if when is None or when.tzinfo is not None:
        raise SystemExit(
            f"{ENV}={raw!r} is not a day (2026-10-02) or a day and a time with no zone "
            "(2026-10-02T14:30:00). Nothing was built: a stated date that fell back on "
            "the clock would look like the date that was asked for.")
    return when


def today():
    """The build's day: datetime.date.today(), unless one is stated."""
    when = stated()
    return when.date() if when else datetime.date.today()


def now():
    """The build's moment on the local clock: datetime.datetime.now(), unless
    one is stated."""
    return stated() or datetime.datetime.now()


def utcnow():
    """The build's moment in UTC, zone attached:
    datetime.datetime.now(datetime.timezone.utc), unless one is stated."""
    when = stated()
    return (when.replace(tzinfo=datetime.timezone.utc) if when
            else datetime.datetime.now(datetime.timezone.utc))
