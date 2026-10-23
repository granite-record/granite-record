// WRITTEN BY src/pages/follow_site.py FROM THE SITE'S OWN FILES. Do not edit it:
// change the value where the comment above it says it comes from, then run
//     python3 src/pages/follow_site.py
// and commit this file with the change. preflight fails while it differs from
// what that command would write.

// src/pages/app.css, light theme: --ink, --ink-2, --rule, --pine.
export const SITE_PALETTE = {"ink": "#1C2126", "ink2": "#4A5259", "rule": "#D3D6DA", "pine": "#14514C"};
// src/pages/words/chips.json "chip", without its "s-".
export const STATUS_CLASS = {"Became Law": "law", "Died": "done", "Interim Study": "study", "Tabled": "table", "Vetoed": "veto", "Withdrawn": "done"};
// src/pages/app.css, light theme: --st-active and --st-<name> for each name above.
export const STATUS_INK = {"active": "#566290", "law": "#1E5B3C", "done": "#9E2B25", "study": "#B9420B", "table": "#7A5A00", "veto": "#7C2D3A"};
// src/pages/app.css, light theme: --yes and --no, the vote ring's.
export const VOTE_INK = {"yes": "#215C43", "no": "#CE6A62"};
// src/pages/app.js TESTIFY_FORMS, each chamber's online sign-in form.
export const TESTIFY_FORMS = {"H": ["House", "https://gc.nh.gov/house/committees/remotetestimony/"], "S": ["Senate", "https://gc.nh.gov/remotecommittee/senate.aspx"]};
// src/pages/words/study_report.json.
export const STUDY_REPORT = {"head": "Interim study report", "said": {"rec": "recommends future legislation", "not": "does not recommend future legislation", "without": "makes no recommendation"}};
// src/pages/build_brand.py: MAIL_MARK, at MARK_BOX plus MAIL_PAD on every side.
export const MARK_FILE = {"path": "/mail-mark.png", "width": 41, "height": 64};
