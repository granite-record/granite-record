#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-11.25
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
        # the person's printout of 26 October 2026, at the address they gave
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/vehicle-registrations/vanity-plates",
        "https://www.dmv.nh.gov/tabbed-content/new-registrations",
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/apply-title",
    ],
    # Not yet read, 26 October 2026: the motorcycle guide's DMV pages, which
    # refuse a cloud session; its claims on them wait for the person's printouts.
    "motorcycle": [
        "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/motorcycle-license-endorsement",
        "https://www.dmv.nh.gov/drivers-licensenon-driver-ids/motorcycle-rider-training-program",
        "https://www.dmv.nh.gov/motorcycle-endorsement-frequently-asked-questions",
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
    # Your rights at work: getting paid (25 October 2026). The New Hampshire
    # Department of Labor's page, from the person's printouts; the U.S.
    # Department of Labor's overtime page, read that day.
    "wages": [
        "https://www.dol.nh.gov/",
        # the online wage claim form, its address as the person gave it (26 October 2026)
        "https://www.dol.nh.gov/online-forms/file-online-wage-claim",
        "https://www.dol.gov/agencies/whd/overtime",
    ],
    # The child care guide's, read in the PDFs the person printed and sent on
    # 24 October 2026.
    "child_care": [
        "https://www.dhhs.nh.gov/programs-services/childcare-parenting-childbirth/child-development-and-head-start",
        "https://www.dhhs.nh.gov/programs-services/childcare-parenting-childbirth/child-development-and-head-start/child-care",
        "https://www.dhhs.nh.gov/fam_htm/html/901_application_process_fam.htm",
    ],
    # Read in the person's PDFs of 24 October 2026: the court's and the
    # Attorney General's pages for the domestic violence guide, and the state
    # pages the homelessness guide rests on.
    "domestic_violence": [
        "https://www.courts.nh.gov/self-help/restraining-orders",
        "https://www.doj.nh.gov/bureaus/office-victimwitness-assistance/address-confidentiality-program",
    ],
    # The guide to discrimination (25 October 2026): the Commission for Human
    # Rights' own page, from the person's printout.
    "discrimination": [
        "https://www.humanrights.nh.gov/",
    ],
    "trash": [
        "https://www.des.nh.gov/sites/g/files/ehbemt341/files/documents/hhw-collection-contacts.pdf",
    ],
    # Scams and consumer complaints (25 October 2026): the Attorney General's
    # pages, from the person's printouts.
    "consumer": [
        "https://www.doj.nh.gov/bureaus/consumer-protection-antitrust-bureau",
        "https://www.doj.nh.gov/consumer/complaints",
    ],
    "emergencies": [
        "https://www.desc.dos.nh.gov/resources/nh-alerts",
        "https://www.readynh.gov/",
    ],
    # When you need a building permit (25 October 2026), from the person's
    # printouts.
    "building_permits": [
        "https://www.firemarshal.dos.nh.gov/laws-rules-regulatory/state-building-code",
        "https://www.oplc.nh.gov/electricians-board",
        "https://www.des.nh.gov/land/waterfront-development/protected-shoreland",
        "https://des.nh.gov/water/wetlands/permit-assistance",
    ],
    "homelessness": [
        "https://www.dhhs.nh.gov/programs-services/homeless-services",
        "https://www.courts.nh.gov/our-courts/circuit-court/district-division/landlordtenant",
        "https://www.education.nh.gov/who-we-are/division-of-learner-support/bureau-of-instructional-support/ehcy",
    ],
    # Reporting a road problem (25 October 2026): the Department of
    # Transportation's pages, from the person's printouts.
    "road_problems": [
        "https://www.dot.nh.gov/doing-business-nhdot/general-public",
        "https://www.dot.nh.gov/about-nh-dot/contact-us",
    ],
    "run_for_office": [
        "https://www.sos.nh.gov/elections/running-office",
        "https://www.sos.nh.gov/elections/qualifications-office",
    ],
    # The election worker guide (26 October 2026): the Secretary of State's
    # recount and audit procedures, from the person's copies, at the addresses
    # the person gave.
    "election_worker": [
        "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/documents/2024-09/2024-recount-procedures-primary.pdf",
        "https://www.sos.nh.gov/sites/g/files/ehbemt561/files/documents/2024-10/audit-procedures-top-of-ticket.pdf",
    ],
    # The Medicare and disability guides (25 October 2026), from the
    # person's printouts. Its own key: under "medicare_and_disability", the
    # name of the list below, the later list replaced this one.
    "medicare_and_disability_state": [
        "https://www.dhhs.nh.gov/programs-services/medicaid/nh-medicaid-medical-assistance-eligibility/medicare-beneficiaries",
        "https://www.dhhs.nh.gov/programs-services/disability-care/aid-permanently-totally-disabled",
        "https://www.dhhs.nh.gov/programs-services/disability-care/developmental-services",
        "https://www.education.nh.gov/who-we-are/deputy-commissioner/bureau-vocational-rehabilitation/programs-and-services/vocational-rehabilitation-services",
    ],
    # The guide to who to contact (25 October 2026), from the person's printouts.
    "who_to_contact": [
        "https://www.council.nh.gov/about-us",
        "https://www.council.nh.gov/contact-us",
        "https://www.governor.nh.gov/contact-governor-ayotte",
    ],
    # The private health insurance guide (26 October 2026): the Insurance
    # Department's pages, addresses from a web search, waiting for the
    # person's printouts.
    "insurance_health": [
        "https://www.insurance.nh.gov/",
        "https://www.insurance.nh.gov/consumers/health-insurance/independent-external-review",
        "https://www.insurance.nh.gov/consumers/health-insurance/healthcare-and-long-term-care-appeals",
    ],
    # Fishing, hunting and boating: printed by the person, 25 October 2026.
    "outdoors": [
        "https://www.wildlife.nh.gov/licenses-and-permits/nh-license-requirements",
        "https://www.wildlife.nh.gov/fishing-new-hampshire/licenses-and-permits",
        "https://www.wildlife.nh.gov/fishing-new-hampshire/free-fishing-days-new-hampshire",
        "https://www.wildlife.nh.gov/saltwater-fisheries-new-hampshire/marine-licenses-and-permits",
        "https://www.wildlife.nh.gov/licenses-and-permits/senior-and-milestone-licenses",
        "https://www.wildlife.nh.gov/hunting-nh/hunter-education/hunter-education-frequently-asked-questions",
        "https://www.wildlife.nh.gov/licenses-and-permits/national-migratory-bird-harvest-information-program-hip",
        "https://www.nhsp.dos.nh.gov/our-services/field-operations-bureau/marine-patrol/boating-education/boating-education-faqs",
        "https://www.nhsp.dos.nh.gov/our-services/field-operations-bureau/marine-patrol/boating-education/14-day-temporary-safe-boating",
        "https://www.dmv.nh.gov/vehicles-boats-and-titles/boat-registrations",
        "https://www.wildlife.nh.gov/saltwater-fisheries-new-hampshire/saltwater-fishing-faqs",
    ],
    # The Insurance Department's consumer pages for the car, renters and
    # homeowners insurance guides (26 October 2026): addresses from a web
    # search, each refusing a cloud session, waiting for the person's printouts.
    "insurance_property": [
        "https://www.insurance.nh.gov/consumers/automobile-insurance",
        "https://www.insurance.nh.gov/consumers/homeowners-and-renters-insurance",
        "https://www.insurance.nh.gov/consumers/filing-complaint",
        # The Department's Auto Insurance Consumer Guide, its address the person's.
        "https://mm.nh.gov/files/uploads/nhid/documents/nh-auto-guide.pdf",
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
    # The guide to help after domestic and sexual violence (24 October 2026):
    # the statewide coalition of the crisis centers, not a state agency,
    # approved as a source by the person that day.
    "domestic_violence": [
        "https://www.nhcadsv.org/",
        "https://www.nhcadsv.org/member-programs.html",
        "https://www.nhcadsv.org/safety-planning1.html",
        "https://www.nhcadsv.org/medicalforensic-exams.html",
        "https://www.nhcadsv.org/legal-resources.html",
        "https://www.nhcadsv.org/support-services--programs.html",
    ],
    # The guide to discrimination (25 October 2026): the U.S. Equal Employment
    # Opportunity Commission's page on filing a charge, read that day.
    "discrimination": [
        "https://www.eeoc.gov/how-file-charge-employment-discrimination",
    ],
    # The homelessness guide (24 October 2026): 211 New Hampshire, which the
    # Department of Health and Human Services sends readers to; New Hampshire
    # Housing, the public housing finance authority, at its own .org address;
    # and the federal law on homeless students' schooling.
    # The storms and emergencies guide (24 October 2026): FEMA's Ready.gov
    # and the National Weather Service.
    # The trash and recycling guide (24 October 2026): the EPA.
    "trash": [
        "https://www.epa.gov/hw/household-hazardous-waste-hhw",
        "https://www.epa.gov/recycle/composting-home",
    ],
    "emergencies": [
        "https://www.ready.gov/kit",
        "https://www.ready.gov/power-outages",
        "https://www.ready.gov/winter-weather",
        "https://www.weather.gov/safety/winter-ww",
    ],
    "homelessness": [
        "https://211nh.org/",
        "https://www.nhhousing.org/rental-assistance/apply/",
        "https://www.nhhousing.org/resources/resources-for-renters/",
        "https://www.govinfo.gov/content/pkg/USCODE-2024-title42/html/USCODE-2024-title42-chap119-subchapVI-partB-sec11432.htm",
    ],
    "federal_and_city": [
        "https://www.tsa.gov/real-id",
        # The federal child care rules (the person, 24 October 2026: "you can
        # cite federal sources"), read at eCFR that day.
        "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-98/subpart-C/section-98.21",
        "https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-A/part-98/subpart-D/section-98.30",
        "https://concordnh.gov/1088/Filing-for-Office",
    ],
    # The passport guide (25 October 2026): the Department of State's pages,
    # from the person's printouts, as travel.state.gov refuses a cloud
    # session; the Postal Service's page and the federal rules, read that day.
    "passport": [
        "https://travel.state.gov/en/passports/apply/adults.html",
        "https://travel.state.gov/en/passports/renew-replace/online.html",
        "https://travel.state.gov/en/passports/renew-replace/mail.html",
        "https://travel.state.gov/en/passports/apply/child/under-16.html",
        "https://travel.state.gov/en/passports/apply/get-fast.html",
        "https://travel.state.gov/en/passports/apply/get-fast/make-appointment.html",
        "https://www.usps.com/international/passports.htm",
        "https://www.ecfr.gov/current/title-22/chapter-I/subchapter-F/part-51/subpart-A/section-51.4",
        "https://www.ecfr.gov/current/title-22/chapter-I/subchapter-F/part-51/subpart-B/section-51.21",
        "https://www.ecfr.gov/current/title-22/chapter-I/subchapter-F/part-51/subpart-B/section-51.22",
        "https://www.ecfr.gov/current/title-22/chapter-I/subchapter-F/part-51/subpart-B/section-51.28",
        "https://www.ecfr.gov/current/title-22/chapter-I/subchapter-F/part-51/subpart-C/section-51.42",
    ],
    # The Medicare and Social Security guide and the disability guide (25
    # October 2026): medicare.gov and USA.gov, read that day; the federal
    # rules at eCFR, read that day; Social Security's pages, from the
    # person's printouts.
    "medicare_and_disability": [
        "https://www.medicare.gov/basics/get-started-with-medicare/sign-up/when-does-medicare-coverage-start",
        "https://www.medicare.gov/basics/get-started-with-medicare/sign-up/how-do-i-sign-up-for-medicare",
        "https://www.medicare.gov/basics/get-started-with-medicare/sign-up/ready-to-sign-up-for-part-a-part-b",
        "https://www.medicare.gov/basics/get-started-with-medicare/get-more-coverage/joining-a-plan",
        "https://www.medicare.gov/basics/costs/help/medicare-savings-programs",
        "https://www.medicare.gov/basics/costs/help/drug-costs",
        "https://www.medicare.gov/talk-to-someone",
        # the person's printout of 26 October 2026
        "https://www.medicare.gov/basics/get-started-with-medicare/medicare-basics/parts-of-medicare",
        "https://www.medicare.gov/basics/costs/medicare-costs",
        "https://www.usa.gov/agencies/social-security-administration",
        "https://www.ssa.gov/apply",
        "https://www.ssa.gov/medicare/sign-up",
        "https://www.ssa.gov/myaccount/",
        "https://www.ssa.gov/ssi/eligibility",
        "https://www.ecfr.gov/current/title-20/section-404.310",
        "https://www.ecfr.gov/current/title-20/section-404.315",
        "https://www.ecfr.gov/current/title-20/section-404.909",
        "https://www.ecfr.gov/current/title-20/section-404.1505",
        "https://www.ecfr.gov/current/title-20/section-416.202",
    ],
    # The guide to who to contact (25 October 2026): USA.gov, the two chambers'
    # finders, a New Hampshire senator's and representative's casework pages,
    # and the federal Privacy Act at govinfo, read that day.
    "who_to_contact": [
        "https://www.usa.gov/elected-officials",
        "https://www.senate.gov/senators/senators-contact.htm",
        "https://www.house.gov/representatives/find-your-representative",
        "https://www.hassan.senate.gov/services/help-with-a-federal-agency",
        "https://goodlander.house.gov/services/help-federal-agency/",
        "https://www.govinfo.gov/content/pkg/USCODE-2024-title5/html/USCODE-2024-title5-partI-chap5-subchapII-sec552a.htm",
    ],
    # The private health insurance guide (26 October 2026): HealthCare.gov,
    # the Marketplace's official site, read that day.
    "insurance_health": [
        "https://www.healthcare.gov/quick-guide/dates-and-deadlines/",
        "https://www.healthcare.gov/coverage-outside-open-enrollment/special-enrollment-period/",
        "https://www.healthcare.gov/apply-and-enroll/how-to-apply/",
        "https://www.healthcare.gov/lower-costs/",
        "https://www.healthcare.gov/have-job-based-coverage/options/",
        "https://www.healthcare.gov/young-adults/children-under-26/",
        "https://www.healthcare.gov/appeal-insurance-company-decision/external-review/",
        "https://www.healthcare.gov/marketplace-in-your-state/",
    ],
    # Fishing, hunting and boating (25 October 2026). Fish and Game's online
    # license system is the state's own, at a .com address rather than nh.gov
    # (its footer: nh.gov, 11 Hazen Drive, Concord), so it is listed here for the
    # person to confirm; and the federal Duck Stamp page.
    "outdoors": [
        "https://www.nhfishandgame.com/",
        "https://www.fws.gov/service/buy-duck-stamp-or-e-stamp",
    ],
    # FEMA's flood insurance page for the homeowners insurance guide, read by
    # a cloud session on 26 October 2026, where it answered.
    "insurance_property": [
        "https://www.floodsmart.gov/get-insured/eligibility",
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
