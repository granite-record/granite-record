#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-13.2
"""
The address of a town's website, where a person has found that the directories
hold an old one.

    python3 src/towns/town_websites.py            # what the hand file says, and whether it still applies

THE FILE IS THE OWNER'S: `corrections/town_websites.json`, written by hand and
by no generator. This module is its one reader, so that the fetcher
(`town_sites.py`), the parsers (`parse_town_sites.py`, `town_boards.py`) and the
page builder (`build_town_pages.py`) cannot read it four ways.

WHY. A town's address comes from two directories, NHDOT's of September 2025 and
the Secretary of State's clerk list, and neither is told when a town moves. In
November 2026 Effingham was found to have a new website (a reader's email to
the owner, 13 November 2026) while both directories still named the old one,
whose pages go on answering with a roster the town no longer keeps. The rule
for a select board is that the town's own dated page is the source of truth
and the directory is the fallback; that rule needs the town's own CURRENT
page, and for a moved town only a person can say which that is.

THE SHAPE, one entry a town (the key is the town's slug, as in places.json):

    "effingham": {
      "website": "https://www.effingham.nh.gov",
      "directories_say": {"nhdot": "...", "secretary_of_state": "..."},
      "evidence": ["what was read, where, on what day"],
      "checked_on": "2026-11-13"
    }

An entry may also carry the town's own select board and its contact e-mail,
each with evidence and a day of its own (the owner, 13 November 2026):

      "board": {"members": [{"name": "Leo Racine", "role": "Chair"},
                            {"name": "Chris Seamans"}],
                "evidence": [...], "checked_on": "2026-11-13"},
      "email": {"address": "townadmin@effingham.nh.gov",
                "evidence": [...], "checked_on": "2026-11-13"}

A board here outranks NHDOT's for the town, and town_boards.py uses it even
where the town's own page fails the current-and-whole rule; the e-mail is
shown on the town offices card in place of NHDOT's. Members are in the town's
own spelling.

`website` and `checked_on` are required and `evidence` must say something;
`directories_say` is what the file replaces, kept beside the correction so a
later reader can see what was changed, and so that `still_needed` can say when
the directories have caught up and the entry has become redundant.

ABSENT FILE, ABSENT ENTRY, SAME BEHAVIOUR AS BEFORE. Every function here
answers "nothing" for a town the file does not name.

A TEST-ONLY PATH. `GRANITE_TOWN_WEBSITES` names another file to read instead
of corrections/town_websites.json; preflight and a helper's end-to-end run use
it so that nothing needs to be written into corrections/.
"""
# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import json
import os
import re
import urllib.parse

ROOT = _paths.ROOT
PATH = ROOT / "corrections" / "town_websites.json"
ENV = "GRANITE_TOWN_WEBSITES"


EMAIL = re.compile(r"^[A-Za-z0-9._%+'-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def path():
    """The file read: the test path where GRANITE_TOWN_WEBSITES names one,
    else corrections/town_websites.json."""
    env = os.environ.get(ENV)
    return Path(env) if env else PATH


def normalise(url):
    """'https://www.effingham.nh.gov/' as 'https://www.effingham.nh.gov', or
    None where it is no web address (no scheme and host with a dot)."""
    u = (url or "").strip()
    if not re.match(r"^https?://", u, re.I):
        return None
    p = urllib.parse.urlparse(u)
    if not p.netloc or "." not in p.netloc or " " in p.netloc or "@" in p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}"


def host_of(url):
    """The host of an address without a leading www., lower case, or ''."""
    h = urllib.parse.urlparse(url or "").netloc.lower().split("@")[-1]
    return h[4:] if h.startswith("www.") else h


def problems(data):
    """What is wrong with a parsed file, as a list of sentences; [] if it is
    the shape this module reads."""
    bad = []
    if not isinstance(data, dict):
        return ["the file is not an object"]
    towns = data.get("towns")
    if not isinstance(towns, dict):
        return ["no \"towns\" object"]
    for key, e in towns.items():
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key or ""):
            bad.append(f"{key!r} is not a town slug")
        if not isinstance(e, dict):
            bad.append(f"{key}: not an object")
            continue
        if not normalise(e.get("website")):
            bad.append(f"{key}: website {e.get('website')!r} is not an address")
        if not re.fullmatch(r"20\d\d-\d\d-\d\d", str(e.get("checked_on") or "")):
            bad.append(f"{key}: checked_on is not a day")
        ev = e.get("evidence")
        if not (isinstance(ev, list) and ev and all(isinstance(x, str) and x.strip() for x in ev)):
            bad.append(f"{key}: no evidence")
        say = e.get("directories_say")
        if say is not None and not isinstance(say, dict):
            bad.append(f"{key}: directories_say is not an object")
        # The optional board and e-mail, each with its own evidence and day.
        for part in ("board", "email"):
            x = e.get(part)
            if x is None:
                continue
            if not isinstance(x, dict):
                bad.append(f"{key}: {part} is not an object")
                continue
            ev = x.get("evidence")
            if not (isinstance(ev, list) and ev and all(isinstance(s, str) and s.strip() for s in ev)):
                bad.append(f"{key}: {part} has no evidence")
            if not re.fullmatch(r"20\d\d-\d\d-\d\d", str(x.get("checked_on") or "")):
                bad.append(f"{key}: {part} checked_on is not a day")
        b = e.get("board")
        if isinstance(b, dict):
            ms = b.get("members")
            if not (isinstance(ms, list) and ms and all(
                    isinstance(m, dict) and str(m.get("name") or "").strip() for m in ms)):
                bad.append(f"{key}: board has no members with names")
        m = e.get("email")
        if isinstance(m, dict) and not EMAIL.match(str(m.get("address") or "")):
            bad.append(f"{key}: email address {m.get('address')!r} is not an address")
    return bad


def load(p=None):
    """{town slug: entry} from the hand file, with the website normalised; {}
    where the file is absent. A file that does not parse or has a bad entry
    is an error and not an empty answer: a hand file that silently does
    nothing is the failure this project keeps meeting."""
    p = Path(p) if p else path()
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    bad = problems(data)
    if bad:
        raise ValueError(f"{p}: " + "; ".join(bad))
    return {k: dict(e, website=normalise(e["website"]))
            for k, e in data["towns"].items()}


def website(key, p=None):
    """The town's website as the hand file gives it, or None."""
    e = load(p).get(key)
    return e["website"] if e else None


def is_current(key, url, p=None):
    """Whether a saved page of this town's is from its current website: True
    for any page of a town the file does not name, and for a town it names,
    only a page from the host the file gives."""
    e = load(p).get(key)
    return not e or host_of(url) == host_of(e["website"])


def still_needed(entry, nhdot_site, clerk_site):
    """Whether the directories still hold an address other than the entry's:
    False once both name the entry's host, when the entry has done its work
    and a person may take it out."""
    mine = host_of(entry["website"])
    held = [host_of(normalise(s) or ("https://" + str(s).strip()))
            for s in (nhdot_site, clerk_site) if s]
    return any(h and h != mine for h in held)


def main():
    p = path()
    entries = load(p)
    print(f"  {p}: " + (f"{len(entries)} town(s)" if p.exists() else "not on disk; every town keeps the directories' address"))
    root = ROOT / "collected"
    try:
        offs = json.loads((root / "town_officials.json").read_text(encoding="utf-8"))
        clerks = json.loads((root / "town_clerks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        offs, clerks = {}, {}
    for k, e in sorted(entries.items()):
        need = still_needed(e, (offs.get(k) or {}).get("website"),
                            (clerks.get(k) or {}).get("website"))
        print(f"    {k}: {e['website']}  checked {e['checked_on']}; "
              + ("the directories still hold another address" if need
                 else "the directories now agree: the entry can go"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
