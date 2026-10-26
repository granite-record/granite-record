# Proposed wording for CLAUDE.md's fetch section

CLAUDE.md is the person's file, so this was written beside it rather than
into it (26 October 2026, with the night's calendars and journals). Nothing
here takes effect until the person copies it in. Each block says where it
would go. The wording follows the code on `feat/night-documents`; if a
number below has moved by the time this is read, the code is right and this
is not.

Why CLAUDE.md needs it: today it says what the laptop must never run, and
that GitHub's night runs the nightly, but not what the night itself asks the
General Court for. Once `NIGHT_DOCUMENTS` is a number, a session on the
laptop that drains this year's calendars, or fetches this year's House
calendars for the committee reports, is asking for files the night already
asked for. The scripts stand down by themselves; the words are for the
session that reads CLAUDE.md before it reads them.

---

## 1. In "Never run these without asking", after "Before assuming nothing is running"

> **What GitHub's night asks, and when.** The nightly runs on GitHub, not
> here (`.github/workflows/nightly.yml`, `nightly.py --runner`), under the
> same refusal record. It asks the General Court's web server for the
> downloads page and the fourteen day files; then next session's bill
> requests (at most three requests) and the two index pages' lists of
> calendars and journals (four requests, eight around New Year). Those two,
> and anything after them, start only if they can finish by 12:00 UTC --
> 8 a.m. Eastern in summer, 7 a.m. in winter -- and otherwise wait for the
> next night (`nightly.asking_left`). The night's verdict says what it asked
> (`gc_requests`), and so does a line on the run's page. The one-liner in
> `watchers/README.md` lists this machine only; GitHub's night is on the
> repository's Actions tab.
>
> **The night's calendars and journals.** The repository variable
> `NIGHT_DOCUMENTS` (Settings → Secrets and variables → Actions → Variables)
> is the switch. Unset or `off`: the night asks only what is listed above.
> `shadow`: it says what it would fetch and fetches nothing. A number from 1
> to 8: after the lists, it fetches at most that many newly listed calendars
> and journals, about 20 seconds apart, stopping at the first refusal, the
> first other failure or the second "not found". It makes their text itself,
> with a pinned `pdftotext` that `tests/documents/` must first prove makes
> the laptop's text byte for byte, and keeps each PDF in the bucket's
> `docs/`. Turning it on and off is the person's decision; the variable
> needs no commit.

## 2. In "Never run these without asking", after "A refusal outlives the run that met it"

> **Once the night fetches them, this year's and last year's calendars and
> journals are the night's.** When the night's own verdict, as
> `python3 src/ops/cloud.py pull` brings it, says `NIGHT_DOCUMENTS` is a
> number, `fetch_calendar_archive.py`'s drain on this laptop leaves those
> years' documents to the night, and `fetch_committee_reports.py` does not
> ask for those years' House calendars. Bring the night's PDFs here with
> `python3 src/ops/cloud.py docs-down` (it reads the bucket and asks nobody),
> then run `src/fetch/gc_web/fetch_committee_reports.py --year YEAR --offline`.
> A document the night will not ask for again -- a refusal recorded against
> it, three tries, or gone from its list -- is a person's: the drain takes it
> when a person runs it. A text the night could not use is listed in its verdict
> (`documents_untexted`); make it here with
> `python3 src/parse/extract_calendar_text.py` from the PDF `docs-down`
> brought, and send it with `seed-kit`. The drain with `--night` never runs
> here.

## 3. In "Branches, the nightly and the kit", after the paragraph on the kit

> The night's one tool from outside Python is `pdftotext`: a poppler build
> for Windows pinned by the sha256 of its zip in `nightly.yml`, installed
> only when `NIGHT_DOCUMENTS` is not `off`. If its download fails or its
> bytes differ, nothing is installed, the night fetches no documents, and the
> run's page says so.

## 4. Optional: at the top, after "That is why they are acceptable ... and why another needs asking first."

> One more may be asked for one day: the person has said the site may need to
> move faster than the nightly on session days, for the votes as they are
> taken (26 October 2026). Nothing does that yet; it would be its own run,
> under the same refusal record and the same one-fetch-at-a-time rule, and
> its own decision.
