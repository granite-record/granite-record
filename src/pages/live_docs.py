#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-30.3
"""
The live votes file, documented (the live layer's design, section 5, and
build order 7): the "Same Day, Provisional" part of the data page's For
Developers section, and its entry in /data/manifest.json. build_exports.py
places both once workers/live/PATCHES.md 10 is applied (it is the API
session's file); the words are kept here, beside the code they describe.

    import live_docs
    live_docs.developers_html()        # "" until PUBLIC
    live_docs.manifest_entry(origin)   # None until PUBLIC

PUBLIC IS THE PERSON'S SWITCH. The layer is on the site from the 11 November
release, built and unlinked, and the live votes go public with Live Now
(about 9 December, section 7.4). A page or a manifest that documents an
endpoint before it answers sends a program to a 404, so nothing here is
published until PUBLIC is True, which the person sets in the same change
that links Live Now.

EVERY STATEMENT IS THE CODE'S:
- the headers, the codes and the cache times are those of
  functions/api/live/votes/[day].js (MAX_AGE, and the comment at its top);
- the 30 days are workers/live/store.js's KEEP_DAYS and sweep(), which go by
  when a file was last written;
- the fields are workers/live/merge.js's, and the shape is
  schema/session.votes.json;
- the record's copy is build_live_session.py's.
preflight's _live_docs holds the numbers and the addresses here to those
files.

THE LIVE FILE IS NOT REWRITTEN BY THE NIGHT. The night never writes the
bucket (section 4.4): the record's copy is a separate file, and a page that
has both uses the record's roll call wherever its id is in both. So the text
says "superseded", never "replaced".

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
      General Court&#39;s public database every few minutes while the chamber
      sits, and served at <code>/api/live/votes/&lt;YYYY-MM-DD&gt;</code>, one
      file a day. It holds each roll call with its tally, its question as the
      record words it, the members&#39; ballots once they are entered, and the
      clerk&#39;s docket line and outcome once the docket has one. It is part of
      API v1 and is <strong>beta and provisional</strong>: the night&#39;s
      record supersedes it each morning (below), and excused and not excused
      settle in the days after a vote. It carries no video data.</p>
    <dl class="repo">
      <dt>The record&#39;s copy</dt>
      <dd>Each session day&#39;s page has the same day from the night&#39;s
        record at <code>/session/&lt;H|S&gt;/&lt;YYYY-MM-DD&gt;.json</code>, in
        the same shape with <code>"provisional": false</code>. The live file
        is not rewritten: where both hold a roll call&#39;s <code>id</code>,
        use the record&#39;s.</dd>
      <dt>The shape</dt>
      <dd><a href="schema/session.votes.json">schema/session.votes.json</a>
        (JSON Schema) holds both.
        <ul>
          <li>An <code>id</code> is the year, the chamber and the roll
            call&#39;s number: <code>2027-H-14</code>.</li>
          <li>A roll call is filed under the day of its vote. A past day&#39;s
            file can still change: the Senate often saves its roll calls the
            next morning.</li>
          <li>A ballot is one character a member, in the order of that
            chamber&#39;s list, <code>members.H</code> or
            <code>members.S</code>: Y yea, N nay, E excused, X not excused,
            P presiding, and . for none recorded. Each file has its own
            list.</li>
          <li><code>bill</code> is null for a vote on no bill, whose words
            stay in <code>bill_as_recorded</code>.</li>
          <li>A House roll call has the time it was taken
            (<code>taken</code>). The database gives every Senate roll call
            the time midnight, so a Senate roll call has <code>taken</code>
            null and the time it was saved (<code>saved</code>).</li>
          <li><strong>The outcome.</strong> In the live file it is the
            clerk&#39;s docket line (<code>docket.outcome</code>), never worked
            out from a tally. A docket line not yet matched to a roll call
            stands in <code>tallies</code> with <code>rollcall</code> null, and
            is matched only when the match is certain. In the record&#39;s copy
            the outcome is <code>passed</code> and <code>threshold_needed</code>,
            and the docket, the times and <code>first_seen</code> are
            null.</li>
        </ul></dd>
      <dt>Asking for it</dt>
      <dd>GET or HEAD, open to any origin, with its <code>ETag</code>. Send
        <code>If-None-Match</code>, and a file that has not changed answers
        304. Ask at most every {POLL_AT_MOST} seconds: each answer is kept
        {MAX_AGE} seconds, and <code>next_read_by</code> says when the reader
        means to look again. A date with no file answers 404, kept
        {NOT_FOUND_AGE} seconds; a store that cannot be read answers 503, never
        cached. A file is removed {KEEP_DAYS} days after it was last written;
        the record&#39;s copy stays.</dd>
      <dt>What the times say</dt>
      <dd><code>read_at</code> and <code>next_read_by</code> describe the reader
        alone, and say nothing about whether a chamber is sitting.
        <code>next_read_by</code> is null once reading has stopped for the day.
        <code>status.problem</code> says why reading is stopped or failing.</dd>
    </dl>'''


def manifest_entry(origin):
    """The manifest's "live" entry, or None until PUBLIC."""
    if not PUBLIC:
        return None
    return {
        "what": "One sitting day's roll calls as read from the General Court's public database "
                "during the day: beta and provisional. The night's record of each session day is "
                "a separate file in the same shape (record_template), which supersedes it: where "
                "both hold a roll call's id, use the record's. The live file is not rewritten.",
        "status": "beta",
        "url_template": origin + VOTES,
        "record_template": origin + RECORD,
        "schema": origin + SCHEMA,
        "cors": True,
        "etag": True,
        "max_age_seconds": MAX_AGE,
        "poll_at_most_every_seconds": POLL_AT_MOST,
        "kept_days_after_last_written": KEEP_DAYS,
    }
