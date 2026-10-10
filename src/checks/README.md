# src/checks/

Scripts that write no record and no page, only a verdict or a report:

- the built site before it ships (`check_site`), and the live site after
  (`check_live`, which asks graniterecord.org and nothing else);
- what the General Court changed overnight (`gc_changes`);
- how complete the archive is (`archive_status`);
- how near launch is (`readiness`);
- dead CSS (`audit_css`);
- the bench (`review.py`), where a person judges one sample at a time and
  `review/checked.jsonl` grows;
- a built site against the kept manifest of a commit's build
  (`site_manifest`: `record` after a build, `compare` after a change), so a
  "nothing moved" proof builds its baseline once a commit;
- which of preflight's checks a change can reach (`check_select`, which
  `preflight.py --changed` runs on).

Run by: the night (`check_site`, `check_live`, `gc_changes`), `publish.bat`
(`check_site`, `check_live`), and a person.

Does not belong here: `preflight.py`, the test suite, which stays at the
root; the timestamp scorer, which sits in `hearings/` beside the method it
scores.

The files moved here in stages 1 and 4 (`src/README.md`). `publish.bat`
names `check_site` and `check_live` by their paths
(`python3 src/checks/check_site.py --site site --base %BASE%`), so its two
lines changed in the commit that moved them.
