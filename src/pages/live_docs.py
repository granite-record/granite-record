#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.1
"""
The live votes file, documented (the live layer's design, section 5, and
build order 7): the "Same Day, Provisional" part of the data page's For
Developers section, and its entry in /data/manifest.json. build_exports.py
places both; the words are kept here, beside the code they describe.

    import live_docs
    live_docs.developers_html()        # "" until PUBLIC
    live_docs.manifest_entry(origin)   # None until PUBLIC

PUBLIC IS THE PERSON'S SWITCH. The layer is on the site from the 11 November
release, built and unlinked, and the live votes go public with Live Now
(about 9 December, section 7.4). A page or a manifest that documents an
endpoint before it answers sends a program to a 404, so nothing here is
published until PUBLIC is True, which the person sets in the same change
that links Live Now.

EVERY STATEMENT IS THE CODE'S. The headers, the codes and the cache times are
functions/api/live/votes/[day].js's (MAX_AGE and the comment at its top); the
30 days are workers/live/store.js's KEEP_DAYS; the shape is
schema/session.votes.json; the record's copy is build_live_session.py's.
preflight's _live_docs holds the numbers here to those files.

Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

# The person's switch: True in the change that links Live Now.
PUBLIC = False

# The numbers the text states, each held to its source by preflight.
MAX_AGE = 15          # functions/api/live/votes/[day].js MAX_AGE
NOT_FOUND_AGE = 60    # the same file's notFound(60, ...)
KEEP_DAYS = 30        # workers/live/store.js KEEP_DAYS
POLL_AT_MOST = 30     # design section 5: clients poll at most every 30 seconds

VOTES = "/api/live/votes/{date}"
RECORD = "/session/{body}/{date}.json"
SCHEMA = "/schema/session.votes.json"


def developers_html():
    """The section's HTML, or "" until PUBLIC."""
    if not PUBLIC:
        return ""
    return f'''<h3 class="dph3">Same Day, Provisional</h3>
    <p>On a day the House or the Senate sits, the roll calls are read from the
      General Court&#39;s public database as they are entered, and served at
      <code>/api/live/votes/&lt;YYYY-MM-DD&gt;</code>, one file a day: each roll
      call with its tally, its question as the record words it, the members&#39;
      ballots once they are entered, and the clerk&#39;s docket line and outcome
      once the docket has one. It is part of API v1 and is
      <strong>beta and provisional</strong>: the night&#39;s record replaces it
      every morning, and excused and not excused settle in the days after a
      vote. It carries no video data.</p>
    <dl class="repo">
      <dt>The record&#39;s copy</dt>
      <dd>Each session day&#39;s page has the same roll calls from the night&#39;s
        record at <code>/session/&lt;H|S&gt;/&lt;YYYY-MM-DD&gt;.json</code>, in the
        same shape with <code>"provisional": false</code>. Where both hold a roll
        call&#39;s <code>id</code>, the record&#39;s is the one to use.</dd>
      <dt>The shape</dt>
      <dd><a href="schema/session.votes.json">schema/session.votes.json</a>
        (JSON Schema) holds both. A ballot is one character a member, in the
        order of <code>members</code>: Y yea, N nay, E excused, X not excused,
        P presiding, and . for none recorded. <code>bill</code> is null for a
        vote on no bill, whose words stay in <code>bill_as_recorded</code>.
        The outcome is the clerk&#39;s, from the docket; this file never works
        one out from a tally.</dd>
      <dt>Asking for it</dt>
      <dd>Open to any origin, with its <code>ETag</code>; send
        <code>If-None-Match</code> and a file that has not changed answers 304.
        Ask at most every {POLL_AT_MOST} seconds: each answer is kept
        {MAX_AGE} seconds, and <code>next_read_by</code> says when the reader
        means to look again. A date with no file answers 404, kept
        {NOT_FOUND_AGE} seconds. Files older than {KEEP_DAYS} days are
        removed; the record&#39;s copy stays.</dd>
      <dt>What the times say</dt>
      <dd><code>read_at</code> and <code>next_read_by</code> describe the reader
        alone, and say nothing about whether a chamber is sitting.
        <code>status.problem</code> names why the last read did not happen.</dd>
    </dl>'''


def manifest_entry(origin):
    """The manifest's "live" entry, or None until PUBLIC."""
    if not PUBLIC:
        return None
    return {
        "what": "One sitting day's roll calls as read from the General Court's public database "
                "during the day: beta and provisional, replaced by the night's record every "
                "morning. The record's copy of each session day is in the same shape. Where both "
                "hold a roll call's id, the record's wins.",
        "status": "beta",
        "url_template": origin + VOTES,
        "record_template": origin + RECORD,
        "schema": origin + SCHEMA,
        "cors": True,
        "etag": True,
        "max_age_seconds": MAX_AGE,
        "poll_at_most_every_seconds": POLL_AT_MOST,
        "kept_days": KEEP_DAYS,
    }
