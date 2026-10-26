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
// src/pages/words/follow_beta.json: the beta line, and the day it is no longer said.
export const FOLLOW_BETA = {"note": "Email following is in beta until the webinar on November 10: it is live, but details may change from day to day.", "until": "2026-11-11"};
// src/pages/build_brand.py: MAIL_MARK, at MARK_BOX plus MAIL_PAD on every side.
export const MARK_FILE = {"path": "/mail-mark.png", "width": 41, "height": 64};
// src/pages/app.css, light :root and dark :root[data-theme="dark"]: the manage page's colours, --brick-soft from --st-done-bg.
export const PAGE_PALETTE = {"light": {"paper": "#E9EAEC", "surface": "#FBFBFC", "wash": "#DFE1E4", "ink": "#1C2126", "ink-2": "#4A5259", "rule": "#D3D6DA", "edge": "#767E86", "pine": "#14514C", "pine-soft": "#DFEBEA", "on-pine": "#FFFFFF", "brick": "#9E2B25", "brick-soft": "#FAE7E5"}, "dark": {"paper": "#171B1C", "surface": "#21282A", "wash": "#2C3436", "ink": "#E6E9E8", "ink-2": "#A7B0B0", "rule": "#3D4547", "edge": "#7C8687", "pine": "#7FB9B1", "pine-soft": "#1B302E", "on-pine": "#0F1414", "brick": "#E4877E", "brick-soft": "#43211F"}};
