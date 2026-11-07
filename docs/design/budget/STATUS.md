# State budget design: status

**As of 7 November 2026. Written for the laptop manager, who took over on 6
November.** Cloud sessions cannot message it, so this file and the latest
commit message on `design/budget` are the report.

## Where it stands

- **The design is complete for every source on hand.**
  - `DESIGN.md` is the write-up.
  - `mock/` holds the page, drawn in the site's own Learn layout.
  - `screenshots/` holds 390 and 1280, light and dark, on a site built
    from `dev` of 5 November.
- **Three blocks are done** (30 October; 30 October with the owner's five
  PDFs; 5 November). Each has had an adversarial review, and every finding
  is fixed. `preflight --code` was green on the committed tree each time
  (959 passed, 0 failed, on 5 November).
- **Private, as the owner directed.** Nothing is linked or published, and
  nothing is on `dev`. `main` is untouched.

## What it needs next

**The two HB 1 files the old manager reported in the laptop's Downloads:**

- "HB 1 - Chaptered Final Version - 7-1-25.pdf" (saved 29 October)
- "Final HB 1 - Excel 07-22-25.xlsx" (saved 5 November)

These are request A in `DESIGN.md` section 2, almost certainly HB 1's
section 1: what each department may spend, by fund. They fill the page's
biggest placeholder, "Where It Goes" as enacted, with its all-funds total
and federal share.

**How they can reach this session**, either way is enough:

1. **Committed to a branch** under `docs/design/budget/sources/`, with a line
   for each in `sources/README.md` giving where it came from. This is how
   the first five PDFs came, on `sources/budget-pdfs`. Tell me the branch in
   a commit message, or Alice can tell this session.
2. **In the R2 kit** (needs Alice's word, as the old manager said). This
   session's read-only kit-down would then bring them into scratch. Say
   under which path.

**The Excel is preferred.** It can be read cell by cell. The PDF is the
check on it.

**When they arrive, this session will:**
- read every department's appropriation, by fund;
- check every row and column against the file's own printed totals;
- check the revenue side against HB 1's own estimates (140:17);
- draw "Where It Goes" as enacted and reconcile it with the DAS summary's
  fiscal 2027 "adjusted authorized" figures;
- update `DESIGN.md`, the mock and the screenshots, and have it reviewed
  afresh.

## Other requests, less urgent

All are in `DESIGN.md` section 2: the surplus statements (C), the
Governor's recommended budget (B), the compare reports (D), DAS's FY28-29
Statewide Agency Budget Book (F), the exact DAS addresses (G), the Highway
and Fish and Game collections (H), the fiscal 2025 annual financial report
(I), Ways and Means (J), and RSA 77 (K).

## Questions for the owner

1. **The design itself.** Approve, change, or hold? `DESIGN.md` section 5
   lists 21 open questions, each with a recommended default.
2. **Commit identity.** The session's stop hook flags commits by "Alice Wade
   <contact@graniterecord.org>" as "Unverified" and asks for them to be
   rewritten. This session has not rewritten them, because the old
   manager's instructions set that identity and a rewrite changes history.
   Keep as is?
