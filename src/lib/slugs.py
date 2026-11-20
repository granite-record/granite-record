#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-20.1
"""
A name made an address, and a town's page key: the one rule.

    import slugs
    slugs.slug("Bean's Grant")            -> "bean-s-grant"
    slugs.town_slug("Manchester", "3")    -> "manchester-ward-3"

ONE HOME SINCE 20 NOVEMBER 2026 (the refactor's finding 8). The page
builders, the town readers and the downloads each wrote slug out for
themselves (fourteen files), and build_town_pages and fetch_town_clerks the
town key; every copy gave the same answer on every real input before it was
pointed here (src/TWINS.md; preflight's _slug_one_home holds them).

A module of its own, not the model's (entities), because a module that
imports entities reads the model, which the build makes last and which only
the readers moved onto it may read; entities takes slug from here.

A reader that folds accents first (election_town_rows, build_civics, a
member's address in build_legislator_pages) folds and then calls slug, so
"Henry Noel" with a diaeresis is "henry-noel" there and "henry-no-l" here.
The clerk readers (parse_clerks, parse_clerks_csv) write a ward's key their
own way, its leading zeros dropped, around this slug.
"""
import re


def slug(text):
    """Lower case, letters and digits, a hyphen between: "Hillsborough" -> "hillsborough",
    "Kelly Ayotte" -> "kelly-ayotte", "r/d" -> "r-d"."""
    return re.sub(r"[^a-z0-9]+", "-", str(text or "").lower()).strip("-")


def town_slug(town, ward):
    """A town's page key: "Bean's Grant", "0" -> "bean-s-grant"; "Manchester", "3" ->
    "manchester-ward-3". A ward of "" or "0" is the whole town, and a ward is
    written as it is given."""
    s = slug(town)
    return f"{s}-ward-{ward}" if ward and str(ward) != "0" else s
