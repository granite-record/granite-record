#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.2
"""
The official pages the how-to guides cite, onto this disk, to check them by.

    python src/fetch/other/guide_sources.py            # fetch every page in SOURCES
    python src/fetch/other/guide_sources.py --list     # what it would ask, asking nothing
    python src/ops/cloud.py backup             # then: the pages reach the bucket

WHY THE LAPTOP. The state's web host (Akamai, in front of sos.nh.gov, dmv.nh.gov,
doj.nh.gov, energy.nh.gov and the rest) answers a data centre's address with
"Access Denied" -- GitHub's machine and a cloud session alike, tried 11
October 2026. A guide states nothing its official page was not read to say
(the person's resources plan: "ensure accuracy and refer people to official
pages"), so the pages are read from here, where they answer, and the backup
carries them to the bucket for the session that writes the guides.

IT DOES NOT WORK, AND IS KEPT FOR WHAT IT RECORDS (12 October 2026). The
person ran it on the laptop: every page answered 403 with 0 bytes. The state's
web host refuses a script that says it is one, from a home connection as
from a data centre, and this file will not pretend to be a browser. The pages
are read in a real browser instead: a session on the laptop that browses, or
a person saving each page. SOURCES stays the list of what the guides cite.

WHAT IT ASKS. State agencies' public pages only, never the General Court's
(gc.nh.gov: the statutes are on disk as db/NH_RSA.psv). One page at a time,
SPACING seconds apart, each once. Nothing is retried.

WHAT IT WRITES. guides/sources/<n>.<html|pdf> and guides/sources/index.json:
for each page, the address asked, the address it ended at, the status, the
content type, the size and when it was read. A page that did not answer is in
the index with its status and no file. Nothing else is touched.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

OUT = _paths.ROOT / "guides" / "sources"
SPACING = 3
AGENT = "GraniteRecord/1.0 (graniterecord.org; checking a guide against its official page)"
STATE_HOSTS = ("nh.gov",)          # every host below must end with one of these

# Grouped by the guide that cites them. A page added here must be a state
# agency's own; anything else is the person's decision first.
SOURCES = {
    "voting": [
        "https://www.sos.nh.gov/elections/register-vote",
        "https://www.sos.nh.gov/elections/frequently-asked-questions/how-register-vote",
        "https://www.sos.nh.gov/proof-voter-registration-qualifications",
        "https://www.sos.nh.gov/elections/register-vote/town-or-city-clerks-office",
        "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/docs/registering-to-vote-in-new-hampshire-6.3.2026.final_.pdf",
        "https://mm.nh.gov/files/uploads/sos/docs/5-29-26-secretary-of-state-issues-statement-on-hb-1569.pdf",
        "https://www.sos.nh.gov/elections/voters/absentee-ballots",
        "https://app.sos.nh.gov/viphome",
        "https://app.sos.nh.gov/statelistclerkandpolling",
        "https://app.sos.nh.gov/clerkinformation",
        "https://app.sos.nh.gov/pollingplacesampleballot",
    ],
    "car": [
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/vehicle-registrations",
        "https://www.dmv.nh.gov/vehicles-boats-or-titles/vehicle-registrations/new-resident-new-hampshire",
        "https://www.dmv.nh.gov/tabbed-content/new-registrations",
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/apply-title",
        "https://www.doj.nh.gov/news-and-media/public-guidance-vehicle-inspection-program-status",
    ],
    "town_clerk": [
        "https://www.sos.nh.gov/vital-records-0/purchasing-correcting-vital-records/request-certificates",
        "https://www.sos.nh.gov/vital-records",
    ],
    "right_to_know": [
        "https://www.doj.nh.gov/resources/forms-publications/right-know",
        "https://mm.nh.gov/files/uploads/doj/remote-docs/right-to-know.pdf",
        "https://www.sos.nh.gov/administration/office-right-know-ombudsman",
    ],
    "energy": [
        "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills",
        "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/fuel-assistance-program",
        "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/community-action-agencies",
    ],
    "insurance_appeal": [
        "https://www.insurance.nh.gov/consumers",
        "https://www.insurance.nh.gov/appeals-external-reviews",
    ],
    "property_tax": [
        "https://www.revenue.nh.gov/assistance/low-and-moderate-income-homeowners-property-tax-relief",
        "https://www.revenue.nh.gov/municipal-and-property-division/property-tax-abatements-and-exemptions",
    ],
    "start_here": [
        "https://nheasy.nh.gov/",
        "https://www.dhhs.nh.gov/servicelink/contact-servicelink",
        "https://www.dhhs.nh.gov/programs-services/medicaid",
    ],
}


def state_host(url):
    host = url.split("/")[2].lower()
    return any(host == h or host.endswith("." + h) for h in STATE_HOSTS)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.geturl(), r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, url, e.headers.get("Content-Type", "") if e.headers else "", b""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, url, type(e).__name__, b""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--list", action="store_true", help="print what would be asked, ask nothing")
    a = ap.parse_args()
    pages = [(g, u) for g, us in SOURCES.items() for u in us]
    bad = [u for _g, u in pages if not state_host(u)]
    if bad:
        raise SystemExit("not a state agency's page: " + ", ".join(bad))
    if a.list:
        for g, u in pages:
            print(f"{g:16} {u}")
        print(f"\n{len(pages)} pages; nothing was asked.")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for n, (g, u) in enumerate(pages, 1):
        status, final, ctype, body = fetch(u)
        kind = "pdf" if "pdf" in ctype.lower() or body[:4] == b"%PDF" else "html"
        name = f"{n:03d}.{kind}" if body and status == 200 else ""
        if name:
            (OUT / name).write_bytes(body)
        index.append({"n": n, "guide": g, "asked": u, "url": final, "status": status, "type": ctype,
                      "bytes": len(body), "file": name,
                      "read": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
        print(f"  {n:3} {status:3} {len(body):>9,} bytes  {u}" + (f"\n        -> {final}" if final != u else ""))
        time.sleep(SPACING)
    (OUT / "index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    ok = sum(1 for i in index if i["file"])
    print(f"\n{ok} of {len(index)} pages saved in {OUT}; now run: python src/ops/cloud.py backup")
    # SILENCE IS NOT SUCCESS: a run that read nothing says so in its exit code.
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
