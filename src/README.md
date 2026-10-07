# src/

All of Granite Record's code that is not an entry point. The scripts at the
repository root are what people, workflows and schedulers run by name;
everything they call is here.

```
(root)            entry points, config, docs and all data
_paths.py         puts every code folder on the import path
src/
  fetch/          asks other servers, one folder per whose server
    gc_web/       gc.nh.gov's web server; refusal.check() applies
    gc_db/        the General Court's SQL host
    youtube/      YouTube
    other/        anyone else
  parse/          decides the record from what is already on disk
  hearings/       proceedings, their recordings, timestamps and the scorer
  pages/          writes what a reader gets in site/
  checks/         looks at something and reports
  lib/            the few modules every stage shares
functions/        Cloudflare Pages Functions (must stay at the root)
workers/          Cloudflare Workers deployed on their own
watchers/         the General Court fetch lane
tests/            tests and their fixtures
obsolete/         retired code, kept for its reasoning
```

`fetch/` asks other servers (one folder per whose server, because that
decides what can go wrong); `parse/` decides the record from what is on
disk; `hearings/` finds and times proceedings in their recordings; `pages/`
writes what a reader gets in `site/`; `checks/` looks and reports; `lib/`
holds the few modules every stage shares. Each folder's README says what is
in it, what runs it, and what does not belong there.

**The move is in stages.** Stage 0 made the code able to live here and moved
nothing, so for now most of these folders hold only their README and the
scripts they describe are still at the root. Each later stage moves a group
of files without changing a line that names them.

## How a script here is run, and imports

Run a script from the repository root: `python3 src/parse/narrative.py`.
Names are unique across these folders, the root, `watchers/` and `tests/`,
and every import is by bare name: `_paths.py` puts each folder on the path,
so moving a file between folders changes no import. Every runnable script
starts, after its docstring, with the same five lines (`_paths.BOOTSTRAP`),
which find `_paths.py` above the script's own file and import it before any
other module of this project. Anything that starts a script as a process --
`build_all.py`'s steps, `nightly.py`, the laptop's evening job, the lane --
finds it by its bare name through `_paths.script`, so a lane line or a build
step never changes when a file moves.

The order the build runs things in is `build_all.py`'s `plan()`, not the
folder order: `python3 build_all.py --dry-run`.

## Where a new file goes

A script goes at the root only if something outside the repository has to
name it -- a workflow, Task Scheduler, a scheduled task, `publish.bat`, the
session's first commands -- or the person chose it. Everything else goes here:

- **A data source.** Its fetcher goes in `fetch/<whose server>/` and saves raw
  files; its reader goes in `parse/`. It gets one `Step()` in
  `build_all.plan()`, and a `cloud_kit.json` entry if the night needs what it
  saved. If it asks gc.nh.gov it calls `refusal.check()` straight after its
  arguments.
- **A build step.** `parse/` if it decides a fact, `hearings/` if it is about
  a proceeding or a recording, `pages/` if it writes what a reader gets.
- **A page.** `pages/build_<page>.py` on `shell.py`, plus a `Step()`.
- **A report.** `checks/`. A guard that must fail the night is a check in
  `preflight.py`.
- **Cloudflare code.** A request handler on graniterecord.org goes in
  `functions/api/`; anything deployed on its own goes in `workers/<name>/`.
- **A helper.** Beside its users; `lib/` only once several folders import it
  and it belongs to none of them.

Copy the bootstrap from any runnable script, give the file a name no other
code file has, and give it a version stamp and a line in `versions.json` under
its bare name, as the root's scripts have. A new folder under `src/` goes on
`_paths.CODE_DIRS` in the same commit.

## What preflight holds this to

`python3 preflight.py --code` fails when two code files share a name, when a
runnable script does not start with the bootstrap, when a script finds a
folder from its own `__file__` rather than `_paths.ROOT` or starts another by
a path it made rather than through `_paths.script`, when a `python3 -c` in
the code or the docs imports a module of ours before `_paths`, when a name
`build_all`, the night, the lane, the evening job, a workflow or `publish.bat`
uses finds no file or two, when a file sits in the folder of a network it
does not ask (a `refusal.check()` outside `fetch/gc_web/`, the SQL host
outside `fetch/gc_db/`, yt-dlp outside `fetch/youtube/`, a request from any
folder outside `fetch/` but one from `checks/` to graniterecord.org), and
when git cannot see a file of code. Asking nobody is the default: a new
folder outside `fetch/` is held to it the day it is listed.
