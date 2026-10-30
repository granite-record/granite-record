#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.4
"""
The site's colours and words the email sender draws with, written into
workers/follow/site.gen.js from the files the site itself draws them from.

    python3 src/pages/follow_site.py            # write it
    python3 src/pages/follow_site.py --check    # say whether it is current; write nothing

ONE SOURCE EACH (the person, 23 October 2026: code "easily adjustable for
future development so we don't have to keep going back and redo work done in
a previous session"). An email is drawn in the site's colours and says some
things in the site's words, and mail.js held each as a copy typed by hand,
with a preflight check of its own to catch the copy falling behind. Now each
value is read here from where the site keeps it, and written into one file
that mail.js imports:

    SITE_PALETTE    app.css, light theme: --ink, --ink-2, --rule, --pine
    STATUS_CLASS    chips.json "chip", without its "s-": the word a status
                    chip is coloured by, and the colour's name
    STATUS_INK      app.css, light theme: --st-active and --st-<name> for
                    every name in STATUS_CLASS
    VOTE_INK        app.css, light theme: --yes and --no, the vote ring's
    TESTIFY_FORMS   app.js TESTIFY_FORMS, each chamber's online sign-in form
    STUDY_REPORT    study_report.json, an interim study report's words
    MARK_FILE       build_brand.py: mail-mark.png, at MARK_BOX plus MAIL_PAD
                    on every side
    PAGE_PALETTE    app.css, light and dark: the colours the manage, confirm
                    and unsubscribe pages (page.js) are drawn in. The brick's
                    soft ground is --st-done-bg, the one the site draws its
                    own brick-red chip on; app.css has no --brick-soft.
    FOLLOW_BETA     follow_beta.json: the line that says email following is
                    in beta, and the day it is no longer said (26 October
                    2026), which the Follow by email pane says too
    CHIP_WORDS      chips.json "short", "short_prefix" and "capitals", and
                    meeting_kinds.json "small": what a bill card's chip says
                    for where a bill stands (components.card_word), so that
                    an email's "Now" says "In Committee" where the site's
                    chip does, not the record's "In committee" (the email
                    pass, 29 October 2026)

What is the email's own and not the site's stays in mail.js: the white
ground, the mark's empty alt, every other sentence. What is the manage page's own
stays in page.js: its font stacks, which name the site's fonts and then the
system's, since the page loads no font from anywhere.

WHAT A CHANGE TAKES. Change the value where the site keeps it, run this, and
commit workers/follow/site.gen.js with the change. preflight fails while the
file differs from what this would write, and names this command.

WHY A WRITTEN FILE, AND NOT THE WORKER IMPORTING THE SOURCES. Two of them
are not data a bundler can import -- app.css's custom properties and app.js's
TESTIFY_FORMS -- and the Worker is bundled by wrangler on the person's own
machine, from what git holds, with no build step before it. A plain
JavaScript module beside mail.js is read the same way by node's tests, by
wrangler's bundler and by the Pages Functions that import mail.js, and needs
nothing outside workers/follow/. An import of src/pages/words/*.json would
have asked each of them for JSON modules -- Node 22 loads one only with
`with { type: "json" }`, and whether the laptop's wrangler bundles that was
never tried -- and would break the README's fallback of copying the folder
under functions/.

Every colour is said as six-digit hex in capitals, which is how the emails'
tests read a colour back out of an email; a source that says one another way
stops this with its name rather than writing something the email cannot use.
Nothing here asks the network.
"""

# The bootstrap: _paths.py, found above this file, puts every code folder on the import path.
import sys
from pathlib import Path
sys.path += [str(p) for p in Path(__file__).resolve().parents if (p / "_paths.py").is_file()][:1]
import _paths  # noqa: E402,F401

import argparse
import json
import re

OUT = Path("workers/follow/site.gen.js")
COMMAND = "python3 src/pages/follow_site.py"

APP_CSS = Path("src/pages/app.css")
APP_JS = Path("src/pages/app.js")
CHIPS = Path("src/pages/words/chips.json")
STUDY = Path("src/pages/words/study_report.json")
BETA = Path("src/pages/words/follow_beta.json")
KINDS = Path("src/pages/words/meeting_kinds.json")
BRAND = Path("src/pages/build_brand.py")    # imported, for the mark
# Every file the written one is made from.
SOURCES = (APP_CSS, APP_JS, CHIPS, STUDY, BETA, KINDS, BRAND)

HEX = re.compile(r"#[0-9A-Fa-f]{6}")


class SourceError(ValueError):
    """A source no longer says a value where, or how, this reads it."""


def _base(root):
    return Path(root) if root is not None else _paths.ROOT


DARK = ':root[data-theme="dark"]'


def light_tokens(css):
    """{name: value} of every custom property app.css declares in a rule whose
    selector is :root alone, at the top level: the light theme. A dark block
    is under a media query or a [data-theme] selector, so it is not read; a
    later :root rule overrides an earlier one, as in the browser."""
    return root_tokens(css, ":root")


def dark_tokens(css):
    """The dark theme's: the light theme's, with what app.css's top-level
    :root[data-theme="dark"] rule declares over them. Its twin under
    prefers-color-scheme says the same (preflight holds the two together),
    so the one without a media query is the one read."""
    return {**light_tokens(css), **root_tokens(css, DARK)}


def root_tokens(css, selector):
    """{name: value} of every custom property declared in a top-level rule
    whose selector is `selector` alone, a later rule over an earlier one."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    out, depth, start, sel, quote = {}, 0, 0, None, ""
    for i, ch in enumerate(css):
        if quote:
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            if depth == 0:
                sel, start = css[start:i].strip(), i + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                if sel == selector:
                    for name, value in re.findall(r"--([\w-]+)\s*:\s*([^;]+)", css[start:i]):
                        out[name] = value.strip()
                start = i + 1
            elif depth < 0:
                raise SourceError("app.css closes a brace it never opened")
        elif ch == ";" and depth == 0:
            start = i + 1               # an @import or @charset line
    return out


def _ink(tokens, name, theme="light :root"):
    value = tokens.get(name)
    if value is None:
        raise SourceError(f"app.css's {theme} declares no --{name}, which the emails draw with")
    if not HEX.fullmatch(value):
        raise SourceError(f"app.css's --{name} is {value!r}; the emails need it as six-digit hex")
    return value.upper()


# THE MANAGE PAGE'S COLOURS (page.js), each {its name on the page: app.css's}.
# The page was drawn from a copy of these typed by hand, and the copy had
# drifted: its dark brick was #F0938C where the site's is #E4877E.
PAGE_TOKENS = {"paper": "paper", "surface": "surface", "wash": "wash", "ink": "ink",
               "ink-2": "ink-2", "rule": "rule", "edge": "edge", "pine": "pine",
               "pine-soft": "pine-soft", "on-pine": "on-pine", "brick": "brick",
               "brick-soft": "st-done-bg"}


def _page_ink(tokens, name, theme):
    """A page colour: six-digit hex, or #fff, which app.css says --on-pine is."""
    value = tokens.get(name)
    if value is not None and re.fullmatch(r"#[0-9A-Fa-f]{3}", value):
        value = "#" + "".join(c * 2 for c in value[1:])
    return _ink({name: value} if value is not None else {}, name, theme)


def testify_forms(js):
    """app.js's TESTIFY_FORMS: {chamber letter: [chamber, form's address]}."""
    m = re.search(r"\bconst TESTIFY_FORMS\s*=\s*\{(.*?)\};", js, re.S)
    if not m:
        raise SourceError("app.js has no `const TESTIFY_FORMS={...};` to read the forms from")
    pair = r'(\w+)\s*:\s*\[\s*"([^"\\]*)"\s*,\s*"([^"\\]*)"\s*\]'
    forms = {k: [house, url] for k, house, url in re.findall(pair, m.group(1))}
    rest = re.sub(pair, "", m.group(1)).replace(",", "").strip()
    if rest or set(forms) != {"H", "S"} or not all(u.startswith("https://") for _, u in forms.values()):
        raise SourceError("app.js's TESTIFY_FORMS is not H and S, each [chamber, https address], "
                          f"as this reads it: {m.group(0)[:200]!r}")
    return {k: forms[k] for k in ("H", "S")}


def values(root=None):
    """{export name: (where it comes from, value)}, in the file's order."""
    base = _base(root)
    css = (base / APP_CSS).read_text(encoding="utf-8")
    tokens, dark = light_tokens(css), dark_tokens(css)
    chip = json.loads((base / CHIPS).read_text(encoding="utf-8")).get("chip")
    if not isinstance(chip, dict) or not chip:
        raise SourceError('chips.json has no "chip" map of a status\'s words to its colour')
    classes = {}
    for words, cls in chip.items():
        if not (isinstance(cls, str) and cls.startswith("s-")):
            raise SourceError(f'chips.json colours "{words}" with {cls!r}, not an "s-" class')
        classes[words] = cls[2:]
    names = ["active"] + [c for c in dict.fromkeys(classes.values()) if c != "active"]
    study = json.loads((base / STUDY).read_text(encoding="utf-8"))
    said = study.get("said") or {}
    if not isinstance(study.get("head"), str) or set(said) != {"rec", "not", "without"}:
        raise SourceError('study_report.json has no "head", or its "said" is not rec, not and without')
    beta = json.loads((base / BETA).read_text(encoding="utf-8"))
    if not (isinstance(beta.get("note"), str) and beta["note"].strip()
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(beta.get("until") or ""))):
        raise SourceError('follow_beta.json has no "note", or no "until" as YYYY-MM-DD')
    chips = json.loads((base / CHIPS).read_text(encoding="utf-8"))
    small = json.loads((base / KINDS).read_text(encoding="utf-8")).get("small")
    if not (isinstance(chips.get("short"), dict) and isinstance(chips.get("short_prefix"), list)
            and isinstance(chips.get("capitals"), list) and isinstance(small, list)):
        raise SourceError('chips.json has no "short", "short_prefix" or "capitals", or '
                          'meeting_kinds.json no "small"')
    import build_brand as BB
    mark = {"path": f"/{BB.MAIL_MARK}", "width": BB.MARK_BOX[0] + 2 * BB.MAIL_PAD,
            "height": BB.MARK_BOX[1] + 2 * BB.MAIL_PAD}
    return {
        "SITE_PALETTE": ("src/pages/app.css, light theme: --ink, --ink-2, --rule, --pine",
                         {"ink": _ink(tokens, "ink"), "ink2": _ink(tokens, "ink-2"),
                          "rule": _ink(tokens, "rule"), "pine": _ink(tokens, "pine")}),
        "STATUS_CLASS": ('src/pages/words/chips.json "chip", without its "s-"', classes),
        "STATUS_INK": ("src/pages/app.css, light theme: --st-active and --st-<name> for each name above",
                       {n: _ink(tokens, f"st-{n}") for n in names}),
        "VOTE_INK": ("src/pages/app.css, light theme: --yes and --no, the vote ring's",
                     {"yes": _ink(tokens, "yes"), "no": _ink(tokens, "no")}),
        "TESTIFY_FORMS": ("src/pages/app.js TESTIFY_FORMS, each chamber's online sign-in form",
                          testify_forms((base / APP_JS).read_text(encoding="utf-8"))),
        "STUDY_REPORT": ("src/pages/words/study_report.json",
                         {"head": study["head"], "said": {k: said[k] for k in ("rec", "not", "without")}}),
        "FOLLOW_BETA": ("src/pages/words/follow_beta.json: the beta line, and the day it is no longer said",
                        {"note": beta["note"], "until": beta["until"]}),
        "CHIP_WORDS": ('src/pages/words/chips.json "short", "short_prefix" and "capitals", and '
                       'meeting_kinds.json "small": a bill card\'s chip words (components.card_word)',
                       {"short": chips["short"], "short_prefix": chips["short_prefix"],
                        "capitals": chips["capitals"], "small": small}),
        "MARK_FILE": ("src/pages/build_brand.py: MAIL_MARK, at MARK_BOX plus MAIL_PAD on every side", mark),
        "PAGE_PALETTE": ("src/pages/app.css, light :root and dark :root[data-theme=\"dark\"]: the manage "
                         "page's colours, --brick-soft from --st-done-bg",
                         {theme: {page: _page_ink(toks, css, label) for page, css in PAGE_TOKENS.items()}
                          for theme, toks, label in (("light", tokens, "light :root"),
                                                     ("dark", dark, DARK))}),
    }


def render(root=None):
    """The text of workers/follow/site.gen.js, from the sources as they stand."""
    lines = [
        "// WRITTEN BY src/pages/follow_site.py FROM THE SITE'S OWN FILES. Do not edit it:",
        "// change the value where the comment above it says it comes from, then run",
        f"//     {COMMAND}",
        "// and commit this file with the change. preflight fails while it differs from",
        "// what that command would write.",
        "",
    ]
    for name, (source, value) in values(root).items():
        lines += [f"// {source}.", f"export const {name} = {json.dumps(value, ensure_ascii=False)};"]
    return "\n".join(lines) + "\n"


def current(root=None):
    """(whether the committed file is what render() writes, the reason if not)."""
    path = _base(root) / OUT
    if not path.is_file():
        return False, f"{OUT.as_posix()} is not there"
    # read_text reads a checkout's CRLF as LF: autocrlf is on for the laptop.
    if path.read_text(encoding="utf-8") == render(root):
        return True, ""
    return False, f"{OUT.as_posix()} is not what the site's files say now"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0].strip())
    ap.add_argument("--check", action="store_true", help="say whether the file is current; write nothing")
    a = ap.parse_args()
    try:
        text = render()
    except SourceError as e:
        print(f"follow_site: {e}", file=sys.stderr)
        return 2
    path = _paths.ROOT / OUT
    if a.check:
        ok, why = current()
        print(f"{OUT.as_posix()} is current" if ok else f"{why}: run {COMMAND}")
        return 0 if ok else 1
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        print(f"{OUT.as_posix()} is current; nothing written")
        return 0
    path.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.as_posix()}: {', '.join(values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
