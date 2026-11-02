# State sources: the laptop runbook

How the state's documents get from the state's websites to the sessions that
write the guides, the Learn pages and the budget page. The design and why
are in `docs/design/state-sources/DESIGN.md`; this is what to do.

**In one line:** each week, a Claude session on the laptop opens what is due
in the owner's own Chrome, saves it into `sources/`, and sends it to the
bucket; every other session takes it from there.

The owner approved this on 30 October 2026, after a test that day: with
Claude in Chrome on the laptop, the Secretary of State's register-to-vote page
and the DAS budget page both opened.

---

## The rules, always

1. **Never open gc.nh.gov.** Not a page, not a PDF, not a link that leads
   there. The General Court's firewall has blocked this project twice. The
   LBA's documents are on gc.nh.gov, so the owner saves them by hand. The
   registry marks them `owner-only`, and `due` never lists them.
2. **Open only what `due` lists**, plus the list of documents on a page the
   registry already names (step 4 below). No searching, no following links
   for interest. A link that leads to gc.nh.gov is never opened, wherever it
   appears; the DAS budget page may well carry some.
3. **One page at a time**, a few seconds apart, each once. Nothing is retried.
4. **A refusal ends the run.** A page that says "Access Denied", shows a 403,
   a challenge or a CAPTCHA, or asks to prove you are human, or a PDF whose
   download Chrome lists as failed ("Failed - Forbidden" or the like): stop at once,
   open nothing more, and say which address and when. Never try another way
   in. That is the owner's decision, and the rule is the project's: it will
   not pretend to be anything it is not.
5. **Read only.** Never fill in a form, sign in, search a lookup or press a
   button that submits anything. For an `app` row (a lookup or an online
   service), read its front page and nothing else.
6. **Save what the page says, not what you make of it.** A page's text is
   saved as the browser gives it, unedited: no summary, no header, no
   cleaning-up. The guides cite the words, so the words are the evidence.
   The text passes through the session on its way to the file, and nothing
   proves it arrived word for word. So a saved `.txt` tells the guides session
   that a page changed and what it now says. Where a guide rests a claim on a
   page, a printout or the page itself settles it. Whether a text reading can
   stand in for a printout is the guides session's and the owner's decision.

---

## One-time setup (the owner)

1. **Claude in Chrome**: installed in the owner's Chrome and signed in (done
   on 30 October).
2. **Chrome saves PDFs rather than opening them.** Chrome, Settings, Privacy
   and security, Site settings, Additional content settings, PDF documents:
   choose "Download PDFs". Then opening a PDF's address saves it to Downloads.
3. **Chrome saves to Downloads without asking.** Settings, Downloads: "Ask
   where to save each file before downloading" off.
4. **Site permissions.** The first time the extension opens each state site
   it asks; allow it. There are 32 such sites in the registry, so the first
   run asks most often.
5. **The weekly task** in the Claude desktop app, with the prompt in *The
   weekly task's prompt* below, working in the repository folder. Suggested
   time: Sunday at 6:40 pm, clear of the 7:30 pm captions task. Any time the
   laptop is usually on and awake will do.

`secrets.json` already holds the bucket's keys on the laptop (`cloud.py`
reads them), so nothing else is needed.

---

## The weekly run (what the session does)

From the repository folder on the laptop.

1. **What is due.**
   ```
   python3 src/ops/state_sources.py due
   ```
   It lists every registered document a browser reads that has never been
   read or is past its interval, with its address. The General Court's rows
   and the wanted rows are counted at the end and never listed.

2. **Pages** (`kind` page or app). Open the address in a new tab. Read the
   page's text and save it, unedited, to
   `sources/<id>/<YYYY-MM-DD>.txt`, with today's date. If a page has sections
   that open one at a time (some DMV pages do), save the text as the page
   first shows it; do not open the sections.

3. **PDFs** (`kind` pdf). Open the address in a new tab. Chrome saves the
   file to Downloads (setup step 2). Do not rename or move it. Then look at
   Chrome's downloads list (chrome://downloads): a download marked failed is
   a refusal (rule 4).

4. **Pages that list documents.** On a page the registry names as some row's
   `owner_page` (`das.nh.gov/budget/` is one), list every PDF link on it
   whose address is not in the registry. **Report them; do not open them**,
   unless the owner has said to for that page (the first job below says so
   for DAS, and for das.nh.gov addresses only).

5. **File the downloads.**
   ```
   python3 src/ops/state_sources.py file ~/Downloads
   ```
   It copies each document it can place into `sources/`, placed by the
   address Windows recorded for the download, or else by its file name. It
   never moves or deletes anything in Downloads, and it leaves alone a
   document filed before. A state document it cannot place is listed with the
   registry row it would need, and `file` then ends in a failure. That is
   expected: it means "tell the manager". Go on to step 6 all the same, since
   what could be filed was. A document read again and found unchanged is filed
   under today's date like any other, and `up` records it as a check, so `due`
   moves on. To file one file by hand:
   `python3 src/ops/state_sources.py file "~/Downloads/<name>.pdf" --as <id>`.

6. **Check and send.**
   ```
   python3 src/ops/state_sources.py check
   python3 src/ops/cloud.py sources-up
   ```
   `check` fails on any file in `sources/` that is not filed under the
   registry; fix that first. `sources-up` sends each new version, records a
   reading that has not changed as a check, and prints the change report.
   The bucket keeps the report under `sources/reports/`.

7. **Report**, in the session's last message, in plain words:
   - what changed (the CHANGED lines) and what was read for the first time
     (NEW);
   - any refusal: the address, and the time;
   - any download not placed, with its suggested row;
   - any new document found on a page that lists them;
   - anything due that was not read, and why.

---

## The weekly task's prompt

Paste this as the scheduled task's prompt in the Claude desktop app:

> Weekly state sources run for Granite Record. Work in the Granite Record
> repository folder on this laptop. Read `docs/STATE_SOURCES_RUNBOOK.md`
> first and follow it exactly, including *The rules, always*. In short: run
> `python3 src/ops/state_sources.py due`. Open each listed address in a new
> Chrome tab with Claude in Chrome, one at a time, a few seconds apart. Save
> each page's text unedited to `sources/<id>/<today>.txt`, and let each PDF
> download. Then run `python3 src/ops/state_sources.py file ~/Downloads`,
> `python3 src/ops/state_sources.py check` and
> `python3 src/ops/cloud.py sources-up`. Never open gc.nh.gov or any address
> `due` did not list, and never a link to gc.nh.gov. Never fill in a form,
> sign in or submit anything. If any page refuses (Access Denied, 403, a
> challenge, a CAPTCHA), or a PDF's download fails in Chrome's downloads
> list, stop at once, open nothing more, and report it. If `file` says some
> document could not be placed, still run `check` and `sources-up`, and list
> those documents in the report. Do not pull, edit the registry, commit, or
> push. End with a short plain report: what changed, what was new, any
> refusal, anything not placed, any new documents found, and anything due
> that was not read.

---

## When the owner asks for one document now

"Read the DAS budget page now" is the same run with a shorter list:
`python3 src/ops/state_sources.py due --used-by learn:state-budget` gives the
budget page's documents, and steps 2 to 7 follow. A document read on request
is read whether or not it is due.

---

## When the session cannot run (the manual mode)

The laptop was asleep, Chrome was closed, or a site refused the session. The
owner can do the same by hand:

1. `python3 src/ops/state_sources.py due`: the list.
2. Open each address in Chrome. A PDF downloads by itself. For a page, use
   Print, then Save as PDF, into Downloads, as now.
3. `python3 src/ops/state_sources.py file ~/Downloads`. A printed page has no
   address recorded and a name of Chrome's choosing, so `file` will not place
   it. File each one by hand:
   `python3 src/ops/state_sources.py file "<the PDF>" --as <id>`.
4. `python3 src/ops/cloud.py sources-up`.

Ten to twenty minutes, for what is due rather than for everything.

---

## The LBA's documents (the owner, by hand)

Save them from gc.nh.gov in Chrome as now. If the registry has a row for the
document (`owner-only`), `file` places it like any other. If not, its
suggested row goes to the manager to add. No session opens these.

---

## Adding a row to the registry

`records/sources/REGISTRY.csv` is kept by hand, and the weekly session never
edits it. A new row (a document `file` could not place, or one found on a
listing page) goes to the manager with the suggested row `file` printed, and
who uses it. The manager's session adds it on a branch, `check` and
preflight hold it to the registry's shape, and it reaches the laptop with the
next pull of `dev`. Every General Court address must say `owner-only`, and
`check` refuses one that does not.

---

## The first job: the budget page's documents

The budget session needs, from das.nh.gov:

1. `python3 src/ops/state_sources.py due --used-by learn:state-budget` lists
   four: the DAS budget page, the two capital budget presentations, and the
   FY28-29 Final Statewide Agency Budget Book.
2. Read them as in the weekly run.
3. On the DAS budget page (`https://www.das.nh.gov/budget/`), list every PDF
   link on it. **For this page the owner has said to download them**: "anything
   else of theirs on das.nh.gov". Open each one on das.nh.gov, one at a time, so
   it downloads, and none on any other host: a link to gc.nh.gov is the LBA's
   and stays the owner's.
   Two of these the owner saved before without their addresses (the FY28-29
   agency budget submissions, total funds, and the department name and number
   crosswalk); their addresses are the point.
4. `file ~/Downloads`. The four registered ones are placed. Every other one is
   listed as not placed, with a suggested row. Send that list to the manager,
   so the rows can be added, and run `file` and `sources-up` again after the
   next pull of `dev`.
5. The LBA's two documents stay the owner's to save by hand.

---

## When something goes wrong

| What | What to do |
|---|---|
| A page refuses | Stop the run. Report the address and time. Do not retry; the owner decides. |
| `file` says "Nothing new to file" when PDFs were due | Chrome saved elsewhere, or more than 14 days ago (`--all` reads every file). File by hand with `--as` if need be. |
| `file` says documents could not be placed | Expected for a new document: send the suggested rows to the manager. Go on with `check` and `sources-up`. |
| `check` names a file not filed | It is in `sources/` under a name or id the registry lacks. Move it out, or ask for the row. |
| `up` says a reading is "never replaced" | A file was changed after it was sent. Name the new one `<day>-2.<ext>`. |
| `up` says an older reading cannot be a newer version | An old download was filed late. Move it out of `sources/`. |
| `up` says the manifest changed while it ran | Another send ran at the same time. Run it again. |
| A page reads "changed" every week with nothing new in it | Its text carries something that changes each visit, a date or a counter. Tell the manager. |
