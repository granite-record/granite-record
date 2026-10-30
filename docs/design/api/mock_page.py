#!/usr/bin/env python3
# Unstamped on purpose: a design aid under docs/, which versions.json (bare names in the code folders) cannot list.
"""
The API documentation mock, drawn in a built site's own shell.

    python3 docs/design/api/mock_page.py SITE

Reads SITE/data.html (a built site's data page), puts mock_body.html where
the data page's body is, and writes SITE/api.html. A design aid for
docs/design/api/DESIGN.md, not a build step: nothing runs it, and it writes
only into the SITE named, which should be a scratch build.

The one new rule is .apicode, a block of example code: the data page has
inline <code> and no block of it, and a copied command must keep its lines.
It is drawn from the tokens .repo code already uses (mono, wash, rule).
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STYLE = """<style>
.apicode{font-family:var(--mono);font-size:var(--t-sm);line-height:1.55;background:var(--wash);
  border:1px solid var(--rule);border-radius:var(--r-out);padding:var(--sp-5) var(--sp-6);
  margin:0 0 var(--sp-6);overflow-x:auto;white-space:pre;color:var(--ink)}
.apicode code{font:inherit;background:none;padding:0}
.dphead p.apibeta{margin-top:var(--sp-5)}
</style>"""


def main():
    site = Path(sys.argv[1])
    page = (site / "data.html").read_text(encoding="utf-8")
    body = (HERE / "mock_body.html").read_text(encoding="utf-8")
    body = re.sub(r"^<!--.*?-->\s*", "", body, flags=re.S)
    start = page.index('<div class="datapage">')
    end = page.index("</section>\n</div>", start) + len("</section>\n</div>")
    page = page[:start] + body + page[end:]
    page = page.replace("</head>", STYLE + "</head>", 1)
    page = re.sub(r"<title>.*?</title>", "<title>The Data API | Granite Record</title>", page, count=1, flags=re.S)
    (site / "api.html").write_text(page, encoding="utf-8")
    print(f"wrote {site / 'api.html'}")


if __name__ == "__main__":
    main()
