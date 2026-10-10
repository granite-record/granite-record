# src/checks/

Scripts that write no record and no page, only a verdict or a report:

- the built site before it ships (`check_site`), and the live site after
  (`check_live`, which asks graniterecord.org and nothing else);
- the built site as a reader's browser draws it (`rendered_sweep`, which
  drives headless Chrome through `sweep_browser.js`): text sizes, contrast,
  sideways overflow and text drawn over other text on a fixed list of page
  types, at three widths, in both themes, in forced colours and at a 24px
  browser text size, with a screenshot of each (drawn at the text size it
  measured) and one JSON report;
- what the General Court changed overnight (`gc_changes`);
- how complete the archive is (`archive_status`);
- how near launch is (`readiness`);
- dead CSS (`audit_css`);
- what the browser draws on a built site's record pages, tab by tab, and on
  the pages that draw part of themselves (`drawn_pages`, which runs each
  page's scripts in node against `tests/dom_stub.js`), so that two builds
  meant to look the same are compared by what a reader is shown;
- the bench (`review.py`), where a person judges one sample at a time and
  `review/checked.jsonl` grows;
- a built site against the kept manifest of a commit's build
  (`site_manifest`: `record` after a build, `compare` after a change), so a
  "nothing moved" proof builds its baseline once a commit;
- which of preflight's checks a change can reach (`check_select`, which
  `preflight.py --changed` runs on).

Run by: the night (`check_site`, `check_live`, `gc_changes`), `publish.bat`
(`check_site`, `check_live`), and a person (`rendered_sweep` before a front-end
release, since preflight has no browser).

What they ask: `check_live` asks graniterecord.org. `rendered_sweep` serves the
site itself on the loopback address, and its browser can reach that and Google
Fonts, so the real faces load, and nothing else; preflight holds the browser's
host rules to those names.

Does not belong here: `preflight.py`, the test suite, which stays at the
root; the timestamp scorer, which sits in `hearings/` beside the method it
scores.

The files moved here in stages 1 and 4 (`src/README.md`). `publish.bat`
names `check_site` and `check_live` by their paths
(`python3 src/checks/check_site.py --site site --base %BASE%`), so its two
lines changed in the commit that moved them.
