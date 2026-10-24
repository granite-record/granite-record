#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.7
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
#
# READ BY THE PERSON, 12 OCTOBER 2026. Each page below was opened in a browser
# and sent as a PDF; the copies are in guides/sources/2026-10-12/, and the
# addresses are the ones each page ended at, which its PDF's footer prints --
# several moved from the addresses first listed here (absentee ballots, fuel
# assistance, the Department of Revenue's two pages). A form or a lookup
# listed under a page is one that page links, by the address its link gives.
SOURCES = {
    "voting": [
        "https://www.sos.nh.gov/elections/register-vote",
        "https://www.sos.nh.gov/proof-voter-registration-qualifications",
        "https://www.sos.nh.gov/elections/absentee-ballots",
        "https://mm.nh.gov/files/uploads/sos/docs/5-29-26-secretary-of-state-issues-statement-on-hb-1569.pdf",
        # linked from the pages above
        "https://app.sos.nh.gov/",
        "https://app.sos.nh.gov/clerkinformation",
        "https://www.sos.nh.gov/elections/register-vote/registration-deadlines",
        "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/docs/absentee-ballot-application-state-election-eff-9.30.25-3.pdf",
        "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/application-for-a-free-certified-copy-of-a-new-hampshire-vital-record-for-voter-registration.pdf",
    ],
    "vital_records": [
        "https://www.sos.nh.gov/vital-records-0",
        "https://www.sos.nh.gov/vital-records-0/purchasing-correcting-vital-records/request-certificates",
        "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/vital-record-application-2.pdf",
        # linked from the pages above
        "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/inline-documents/sonh/documentary-evidence-required.pdf",
        "https://www.sos.nh.gov/vital-records-0/vital-records-contact-information",
    ],
    "right_to_know": [
        "https://www.doj.nh.gov/resources/forms-publications/right-know",
        "https://www.sos.nh.gov/administration/office-right-know-ombudsman",
        # linked from the Department of Justice's page
        "https://mm.nh.gov/files/uploads/doj/remote-docs/right-to-know.pdf",
    ],
    "energy": [
        "https://www.energy.nh.gov/fap",
        "https://www.energy.nh.gov/consumers/help-energy-and-utility-bills/community-action-agencies",
    ],
    "property_tax": [
        "https://www.btla.nh.gov/jurisdiction/property-tax",
        "https://www.btla.nh.gov/sites/g/files/ehbemt601/files/inline-documents/sonh/abatement.pdf",
        "https://www.revenue.nh.gov/about-dra/municipal-and-property-division/property-bureau/property-tax-abatement-appeal-process",
        "https://www.revenue.nh.gov/resource-center/taxpayer-assistance/low-and-moderate-income-homeowners-property-tax-relief",
        # linked from the pages above
        "https://www.btla.nh.gov/sites/g/files/ehbemt601/files/inline-documents/sonh/appeals.pdf",
        "https://www.btla.nh.gov/sites/g/files/ehbemt601/files/inline-documents/sonh/commonly-asked-questions-pt.pdf",
        "https://gtc.revenue.nh.gov/TAP/_/",
        "https://www.revenue.nh.gov/nhdra-home/resource-center/current-year-forms-instructions",
        "https://www.revenue.nh.gov/resource-center/frequently-asked-questions/low-moderate-property-tax-relief",
    ],
    # Not yet read: the guides these would serve are not written.
    "car": [
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/vehicle-registrations",
        "https://www.dmv.nh.gov/vehicles-boats-or-titles/vehicle-registrations/new-resident-new-hampshire",
        "https://www.dmv.nh.gov/tabbed-content/new-registrations",
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/apply-title",
    ],
    "insurance_appeal": [
        "https://www.insurance.nh.gov/consumers",
        "https://www.insurance.nh.gov/appeals-external-reviews",
    ],
    "start_here": [
        # read 12 October 2026: the Department of Health and Human Services' benefits site
        "https://nheasy.nh.gov/#/",
        "https://www.dhhs.nh.gov/servicelink/contact-servicelink",
        "https://www.dhhs.nh.gov/programs-services/medicaid",
    ],
    # READ IN A BROWSER ON THE LAPTOP, 17 OCTOBER 2026, for the seven guides of
    # that day. The state's host refused a fetch with 403 that day too, so each
    # page was read in the desktop app's browser pane, one at a time. The
    # Vehicle Registrations page in "car" above, NH Easy and the Medicaid page in
    # "start_here", and the Secretary of State's register-to-vote page and clerk
    # finder in "voting" were read again then and are not listed twice. A form or
    # lookup under a page is one that page links, by its link's address; a PDF
    # downloads there rather than displays, so none of the forms was opened.
    "dmv": [
        "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/renew-driver-licensenon-driver-id",
        "https://www.dmv.nh.gov/online-services/online-renewals",
        "https://www.dmv.nh.gov/appointments-and-services",
        "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/licensing-fees",
        "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/real-id",
        "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/transfer-license-another-state",
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/vehicle-registrations/new-resident-new-hampshire",
        # linked from the pages above
        "https://www.dmv.nh.gov/sites/g/files/ehbemt416/files/inline-documents/dsmv450.pdf",
        "https://www.dmv.nh.gov/sites/g/files/ehbemt416/files/inline-documents/sonh/dsmv634a.pdf",
        "https://www.app-support.nh.gov/erealid/",
        "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/non-us-citizen",
        "https://www.dmv.nh.gov/hours-and-locations",
        "https://services.dos.nh.gov/mos/vfchk",
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/temporary-plates",
        "https://www.dmv.nh.gov/sites/g/files/ehbemt416/files/inline-documents/tdmv19a.pdf",
    ],
    "food_and_health": [
        "https://www.dhhs.nh.gov/programs-services/food-meals-assistance/supplemental-nutrition-assistance-program-snap",
        "https://www.dhhs.nh.gov/apply-assistance",
        "https://www.dhhs.nh.gov/programs-services/stay-covered-new-hampshire",
        "https://www.dhhs.nh.gov/doing-business-dhhs/legal-services/administrative-appeals",
        # linked from the pages above
        "https://nheasy.nh.gov/forms/E/800V.pdf",
        "https://www.dhhs.nh.gov/about-dhhs/locations-facilities#locations",
    ],
    "unemployment": [
        "https://www.nhes.nh.gov/individuals/file-unemployment-benefits",
        "https://www.nhes.nh.gov/individuals/unemployment-eligibility",
        "https://www.nhes.nh.gov/individuals/unemployment-appeals",
        # linked from the pages above
        "https://www.nhes.nh.gov/resources/office-locations",
    ],
    # The child care guide's (24 October 2026): listed so the guide can publish
    # once the person has read them; until then its claims on them are unchecked.
    "child_care": [
        "https://www.dhhs.nh.gov/programs-services/childcare-parenting-childbirth/child-development-and-head-start",
        "https://www.dhhs.nh.gov/programs-services/childcare-parenting-childbirth/child-development-and-head-start/child-care",
        "https://www.dhhs.nh.gov/fam_htm/html/901_application_process_fam.htm",
        "https://www.dhhs.nh.gov/fam_htm/html/915_program_criteria_fam.htm",
    ],
    "run_for_office": [
        "https://www.sos.nh.gov/elections/running-office",
        "https://www.sos.nh.gov/elections/qualifications-office",
    ],
}

# NOT STATE AGENCIES, AND NEVER FETCHED. Where a guide sends a reader for help
# a page cannot give -- legal aid, a lawyer, a counsellor -- it may name these,
# which the person chose to cite and sent from a browser on 12 October 2026
# (copies with the rest). This script asks state hosts only; these are here so
# the guides' gate knows they were read.
OTHER = {
    "help": [
        "https://nhcare-c.org/aging-and-disability-resource-center/",
        "https://www.nhla.org",
        "https://www.603legalaid.org/self-help-articles/",
        "https://www.nhbar.org/lawyer-referral-service/",
    ],
    # THE FEDERAL REAL ID PAGE AND ONE CITY'S FILING PAGE, which the person named
    # as sources for the guides of 17 October 2026 and which were read that day:
    # the Transportation Security Administration's page, where the Department
    # of Homeland Security's REAL ID address now sends a reader, and the City of
    # Concord's, the example of how a city takes filings for its own offices.
    "federal_and_city": [
        "https://www.tsa.gov/real-id",
        # The federal child care rules (the person, 24 October 2026: "you can
        # cite federal sources"), read at eCFR that day.
        "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-98/subpart-C/section-98.20",
        "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-98/subpart-C/section-98.21",
        "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-98/subpart-D/section-98.30",
        "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-98/subpart-F/section-98.51",
        "https://concordnh.gov/1088/Filing-for-Office",
    ],
}


# THE GENERAL COURT'S OWN PAGES ARE NOT LISTED HERE (17 October 2026). The
# hearing and testimony guides link the House's and the Senate's online
# sign-in forms, and a reader uses them on the General Court's site; nothing
# in this project fetches them. Their addresses are civics.py's
# (SRC_TESTIFY and SRC_SENATE_TESTIFY), where check_civics_links.py, under
# the refusal guard and only when a person starts it, asks whether they still
# answer, and guides.GENERAL_COURT_LINKS adds them to what a guide may link.
# They are kept out of this file because it makes requests: a fetching script
# that names the General Court's address is held to the refusal guard, and
# this one must never ask that server -- main() refuses its host outright.
GENERAL_COURT_HOST = "gc.nh.gov"


def cited():
    """Every address a guide may cite: the state pages and OTHER."""
    return {u for d in (SOURCES, OTHER) for us in d.values() for u in us}

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
    # The General Court's host ends in nh.gov like any agency's, so it is
    # refused by name: this script never asks that server (17 October 2026).
    court = [u for _g, u in pages if u.split("/")[2].lower().endswith(GENERAL_COURT_HOST)]
    if court:
        raise SystemExit("the General Court's server is never asked from here: " + ", ".join(court))
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
