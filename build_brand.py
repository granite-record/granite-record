#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.8
"""
Turn the drawn logo and icon into the files a site needs, once.

    python3 build_brand.py            # reads brand/, writes assets/
    python3 build_brand.py --check    # says what is missing, writes nothing

WHY THIS EXISTS AS A BUILD STEP

`site/` is generated and gitignored, so an icon dropped in there disappears on
the next build. The drawn originals live in `brand/`; this writes the derived
files into `assets/`, which `build_pages.py` copies into `site/` beside the
pages. One source, one copy step.

NONE OF THE PICTURES IS IN THE REPOSITORY. This script is MIT like the rest of
the code; what it reads and what it draws are not. The project's originals are
a bought clipart Old Man of the Mountain and an artist's licensed drawing, and
on 30 September 2026 the person took the clipart out of git as the drawing
already was: brand/ and the images in assets/ are gitignored, they live on the
machine that builds the site, and GitHub's nightly gets assets/ from the
private kit (cloud_kit.json). DATA.md has the terms. So on a clone brand/ is
empty and this stops at the first missing original, saying what a fork should
put there to draw its own (need(), below).

The clipart below is the SMALL mark. Since 24 September the logo proper is
Debra Caplan's drawing (see write_licensed): her lockups draw the home page's
heading and the link cards, and since 1 October her drawing alone is the
header's mark, all into assets/licensed/, which build_pages.py lays over
these. The favicon and the tab icons stay this clipart, which reads at 16 to
32 pixels where the detailed drawing does not.

WHAT IS DERIVED, AND WHY EACH ONE

  icon.svg          the profile on a dark tile, at any size a tab, a bookmark
                    or a pinned shortcut asks for. The framing is measured off
                    the drawn PNG rather than guessed, so the composition is
                    the same; the colours are not. This is #F4F5F3 on #111514,
                    the site's own ink and ground, while the drawing and every
                    PNG below it are pure white on pure black -- so a browser
                    that takes the SVG and one that falls back to a PNG show
                    slightly different grounds.
  icon-32/180/512   PNG fallbacks. Safari wants a PNG for apple-touch-icon
                    and a manifest wants real bitmaps.
  icon-512-pad      the maskable one: Android crops an icon to whatever shape
                    the launcher uses, so the mark sits inside the middle 80%.
  favicon.ico       for the bare /favicon.ico a browser asks for anyway, in
                    the three sizes that file format is actually used at.
  og.png            1200x630 for a shared link's card, the black-on-white
                    lockup padded onto white so the card is seamless rather
                    than a black block inside a white border.
  og-<kind>.png     the same card per kind of page -- bill, legislator,
                    committee, learn, town -- with the kind named under the
                    lockup, so a shared bill and a shared legislator do not
                    unfurl identically. OG_SECTIONS below is the list.
  lockup.png        the profile and "Granite Record" together, as the home
                    page's heading: the black-on-white lockup turned into an
                    alpha mask (ink opaque, paper clear) and cut to the ink's
                    own box. Used as a CSS mask over the text colour, like
                    the header's mark, so one file is right in both themes --
                    the two drawn lockups carry a solid black or white ground,
                    which would sit on the page as a box in either.
  licensed/mark.png the header's mark, from the artist's drawing: see
                    write_licensed. There is no clipart twin since 1 October
                    (mark.svg is no longer drawn), because a header without
                    the drawing is the wordmark alone, on purpose.

A NOTE ON THE ORIGINALS' NAMES. They arrived as "Logo Black.png" and "Logo
White.png", named for their BACKGROUND: the first is the white wordmark on
black. brand/ holds them as logo-on-black.png and logo-on-white.png, named for
what they are, because the first draft of this script read the wrong one and
put a black tile in a white frame on every shared link. The arrival names may
still sit at the root of the person's own folder as byte-identical copies,
untracked like brand/; this script reads brand/ only.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BRAND = ROOT / "brand"
OUT = ROOT / "assets"

# The profile's own bounding box inside the drawing's 210x297 viewBox, read
# with getBBox() in a browser rather than estimated from the path data. It is
# the project's clipart's: a fork with its own old-man.svg measures its own.
BBOX = (23.805, 15.638, 156.228, 248.628)

# What a fork puts in brand/ to draw its own icons, said once and printed by
# need() and --check. The project's own are not in the repository.
ORIGINALS = (
    ("old-man.svg", "the mark as an SVG with exactly one <path> (and BBOX in "
                    "this file set to that path's own box)"),
    ("icon.png", "the mark, light on a flat dark square"),
    ("logo-on-white.png", "the mark with the site's name, dark ink on white"),
)


def need(p):
    if not p.exists():
        sys.exit(
            f"missing {p.relative_to(ROOT).as_posix()}.\n"
            "The project's logo and icons are not in the repository: they are "
            "used under licence and are not part of the open-source release "
            "(DATA.md).\nTo draw your own, put these in brand/ and run this "
            "again:\n"
            + "".join(f"  brand/{name:<18} {what}\n" for name, what in ORIGINALS)
            + "or skip this script and put finished files in assets/ under the "
            "names build_pages.BRAND_FILES lists.")
    return p


def path_data():
    """The one path out of the drawn SVG, with nothing else it carries."""
    src = need(BRAND / "old-man.svg").read_text(encoding="utf-8")
    paths = re.findall(r'<path\b[^>]*\sd="([^"]+)"', src)
    if len(paths) != 1:
        sys.exit(f"brand/old-man.svg has {len(paths)} paths; this expects one")
    return paths[0]


def icon_framing():
    """Where the drawn icon puts the shape in its square, measured.

    Returns the shape's box inside a 1000x1000 icon as fractions, so the SVG
    is the same composition as the PNG rather than a fresh guess at it.
    """
    from PIL import Image
    im = Image.open(need(BRAND / "icon.png")).convert("L")
    W, H = im.size
    px = im.load()
    # The drawing is a white shape on a black tile; anything bright is shape.
    minx, miny, maxx, maxy = W, H, -1, -1
    for j in range(H):
        for i in range(W):
            if px[i, j] > 127:
                if i < minx: minx = i
                if j < miny: miny = j
                if i > maxx: maxx = i
                if j > maxy: maxy = j
    if maxx < 0:
        sys.exit("brand/icon.png has no light pixels; is it the icon?")
    return (minx / W, miny / H, (maxx - minx + 1) / W, (maxy - miny + 1) / H)


def write_icon_svg(d, frame):
    """The icon as an SVG: the drawn PNG's framing, the site's own colours."""
    fx, fy, fw, fh = frame
    S = 1000
    bx, by, bw, bh = BBOX
    # Fit the shape's bounding box into the measured frame. The frame is taken
    # from the PNG, so its aspect is the shape's aspect; scale on height and
    # centre horizontally to absorb the rounding either way.
    scale = (fh * S) / bh
    tx = fx * S + (fw * S - bw * scale) / 2 - bx * scale
    ty = fy * S - by * scale
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {S} {S}">'
           f'<rect width="{S}" height="{S}" fill="#111514"/>'
           f'<g transform="translate({tx:.2f} {ty:.2f}) scale({scale:.4f})">'
           f'<path d="{d}" fill="#F4F5F3"/></g></svg>')
    (OUT / "icon.svg").write_text(svg, encoding="utf-8")
    return (f"icon.svg  {len(svg):,} bytes, shape at "
            f"{fx*100:.1f}%,{fy*100:.1f}% {fw*100:.1f}x{fh*100:.1f}%")


def write_pngs():
    from PIL import Image
    src = Image.open(need(BRAND / "icon.png")).convert("RGB")
    said = []
    for n in (32, 180, 512):
        im = src.resize((n, n), Image.LANCZOS)
        im.save(OUT / f"icon-{n}.png", optimize=True)
        said.append(f"icon-{n}.png")
    # MASKABLE: Android crops to the launcher's shape, so the mark has to sit
    # inside the middle 80% or the chin comes off.
    #
    # THE PAD TAKES ITS COLOUR FROM THE SOURCE, and used to be the literal
    # (17, 21, 20). brand/icon.png's ground is pure black, so the padded border
    # was #111514 around a #000000 square and the icon carried a visible seam --
    # on a launcher that reads as a box drawn around the logo, which is the one
    # thing a maskable icon exists to avoid.
    #
    # Sampled rather than corrected to another constant, so it stays right if
    # the brand asset is ever redrawn. The four corners are checked against each
    # other first: if they disagree the mark reaches the edge, this is not a
    # flat ground, and padding it with any single colour would be wrong.
    w, h = src.size
    corners = [src.getpixel(p) for p in
               ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))]
    if len(set(corners)) != 1:
        sys.exit(f"brand/icon.png's corners are not one colour ({corners}), so "
                 "the maskable icon cannot be padded without inventing a "
                 "background. Redraw it with a flat ground, or pad it by hand.")
    pad = Image.new("RGB", (512, 512), corners[0])
    inner = src.resize((410, 410), Image.LANCZOS)
    pad.paste(inner, (51, 51))
    pad.save(OUT / "icon-512-pad.png", optimize=True)
    said.append("icon-512-pad.png")
    src.resize((48, 48), Image.LANCZOS).save(
        OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    said.append("favicon.ico")
    return "pngs     " + ", ".join(said)


def write_og():
    """1200x630, the shape a link card is cropped to."""
    from PIL import Image
    src = Image.open(need(BRAND / "logo-on-white.png")).convert("RGB")
    W, H = 1200, 630
    card = Image.new("RGB", (W, H), (255, 255, 255))
    # Fit inside 88% of the card so nothing is against an edge.
    sw, sh = src.size
    k = min(W * 0.88 / sw, H * 0.88 / sh)
    im = src.resize((int(sw * k), int(sh * k)), Image.LANCZOS)
    card.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    card.save(OUT / "og.png", optimize=True)
    return f"og.png    {W}x{H}, logo at {im.width}x{im.height}"


# ONE CARD PER KIND OF PAGE, rather than one card for everything or one for
# each record. The drawing og.png carries, a little smaller, with the kind of
# page named under it in the site's small capitals, so a shared bill and a
# shared legislator do not unfurl identically.
OG_SECTIONS = {
    "og-bill.png": "BILLS  \u00b7  VOTES  \u00b7  HEARINGS",
    "og-legislator.png": "LEGISLATORS  \u00b7  VOTING RECORDS",
    "og-committee.png": "COMMITTEES  \u00b7  HEARINGS",
    "og-learn.png": "HOW NEW HAMPSHIRE WORKS",
    "og-town.png": "WHO REPRESENTS YOUR TOWN",
}
# A bold sans for the label, wherever this runs. The cards are kept in
# assets/ on the machine that has them, so this is needed only when they are
# drawn again.
LABEL_FONTS = ("C:/Windows/Fonts/arialbd.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/System/Library/Fonts/Supplemental/Arial Bold.ttf")


def write_og_sections():
    """og-<kind>.png, 1200x630: the logo above, the kind of page below."""
    from PIL import Image
    grey = Image.open(need(BRAND / "logo-on-white.png")).convert("L")
    box = grey.point(lambda v: 255 - v).getbbox()
    src = Image.open(BRAND / "logo-on-white.png").convert("RGB").crop(box)
    _section_cards(src, OUT)
    return "section cards: " + ", ".join(OG_SECTIONS)


def _section_cards(src, out):
    """Draw every og-<kind>.png from one ink-on-white logo into out."""
    import os
    from PIL import Image, ImageDraw, ImageFont
    font_path = next((f for f in LABEL_FONTS if os.path.exists(f)), None)
    if not font_path:
        sys.exit("No bold sans font for the section cards' labels: add one to LABEL_FONTS.")
    font = ImageFont.truetype(font_path, 30)
    W, H = 1200, 630
    k = min(W * 0.78 / src.width, H * 0.60 / src.height)
    im = src.resize((int(src.width * k), int(src.height * k)), Image.LANCZOS)
    top = int((H - im.height - 30 - 58) / 2)
    for name, label in OG_SECTIONS.items():
        card = Image.new("RGB", (W, H), (255, 255, 255))
        card.paste(im, ((W - im.width) // 2, top))
        draw = ImageDraw.Draw(card)
        widths = [draw.textlength(ch, font=font) for ch in label]
        x = (W - (sum(widths) + 3 * (len(label) - 1))) / 2
        for ch, w in zip(label, widths):
            draw.text((x, top + im.height + 58), ch, font=font, fill=(70, 74, 72))
            x += w + 3
        card.save(out / name, optimize=True)


def write_lockup():
    """The lockup as an alpha mask, cut to the ink: see the docstring."""
    from PIL import Image
    grey = Image.open(need(BRAND / "logo-on-white.png")).convert("L")
    # Ink is dark on the white original, so opacity is how far from white a
    # pixel is. The drawing's anti-aliased edge keeps its in-between values,
    # which is what keeps the mask's edge smooth.
    alpha = grey.point(lambda v: 255 - v)
    box = alpha.getbbox()
    if not box:
        sys.exit("brand/logo-on-white.png has no ink; is it the lockup on white?")
    alpha = alpha.crop(box)
    im = Image.new("LA", alpha.size, 0)
    im.putalpha(alpha)
    im.save(OUT / "lockup.png", optimize=True)
    return f"lockup.png {alpha.width}x{alpha.height}, cut to the ink"


# THE ARTIST'S LOGO (24 September 2026). Debra Caplan of Peterborough drew the
# mark; her two lockups -- the drawing with "Granite Record" on one line, and
# stacked -- are licensed to the project. The person asked that her files never
# be in the public repository, so they live in brand/licensed/ and everything
# drawn from them goes to assets/licensed/, and both are gitignored.
# build_pages.py lays assets/licensed/ over assets/ when it is there.
#
# WHAT THE DRAWING IS USED FOR, AND WHAT IT IS NOT. The home page's heading
# (the stacked lockup, in the narrow middle column), the link cards (the
# one-line lockup, which fits a 1200x630 card) and, since 1 October, the
# header's mark (the drawing alone). The favicon and the tab icons stay the
# clipart above: the detailed drawing does not read at 16 to 32 pixels.
#
# THE HEADER'S MARK. At the old mark's 15x24 the drawing is a grey fleck --
# its ink covers 27% of its own box where the clipart's covered 83% -- so the
# person chose, from a rendered comparison, the whole drawing in a 33x56 box
# beside the live-text wordmark, and accepted a taller bar for it. The file
# is the ink as an alpha mask at MARK_SCALE times that box: 2x is a laptop,
# 3x is most phones, and at 99x168 the file is about 9 KB, fetched once for
# every page. app.css draws it (its MARK region) and build_pages.py keeps
# that rule only where this file exists; preflight ties the three together.
LICENSED = BRAND / "licensed"
LICENSED_OUT = OUT / "licensed"
HEADER_MARK = "mark.png"      # build_pages.HEADER_MARK
MARK_BOX = (33, 56)           # CSS pixels: app.css, MARK region
MARK_SCALE = 3


def _licensed(stem):
    return next((LICENSED / f"{stem}{ext}" for ext in (".png", ".webp")
                 if (LICENSED / f"{stem}{ext}").exists()), None)


def _ink(path):
    """The ink of a lockup as an alpha channel, cut to the ink's own box.

    Her lockups arrive as black ink on a transparent ground, so the alpha is
    already the ink; a copy on a white ground is read by darkness instead, the
    way write_lockup reads the clipart.
    """
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    alpha = im.getchannel("A")
    if alpha.getextrema()[0] == 255:
        alpha = im.convert("L").point(lambda v: 255 - v)
    box = alpha.getbbox()
    if not box:
        sys.exit(f"{path.relative_to(ROOT)} has no ink")
    return alpha.crop(box)


def write_header_mark(drawing):
    """The drawing as the header's mark: its ink, fitted to MARK_BOX at
    MARK_SCALE, as an alpha mask the stylesheet colours."""
    from PIL import Image
    a = _ink(drawing)
    w, h = MARK_BOX[0] * MARK_SCALE, MARK_BOX[1] * MARK_SCALE
    k = min(w / a.width, h / a.height)
    a = a.resize((max(1, round(a.width * k)), max(1, round(a.height * k))),
                 Image.LANCZOS)
    im = Image.new("LA", a.size, 0)
    im.putalpha(a)
    im.save(LICENSED_OUT / HEADER_MARK, optimize=True)
    return (f"{HEADER_MARK} {a.width}x{a.height} (the drawing, {MARK_SCALE}x "
            f"the header's {MARK_BOX[0]}x{MARK_BOX[1]} box)")


def write_licensed():
    """The home page's lockup, the link cards and the header's mark, from the
    artist's files."""
    from PIL import Image
    stacked, wide = _licensed("lockup-stacked"), _licensed("lockup-wide")
    drawing = _licensed("drawing")
    if not (stacked and wide):
        return None
    LICENSED_OUT.mkdir(parents=True, exist_ok=True)
    mark = (write_header_mark(drawing) if drawing else
            f"NO {HEADER_MARK} (brand/licensed/ holds no drawing), so the "
            "header is the wordmark alone")
    a = _ink(stacked)
    im = Image.new("LA", a.size, 0)
    im.putalpha(a)
    im.save(LICENSED_OUT / "lockup.png", optimize=True)
    # The link cards want ink on white, so the one-line lockup's alpha is
    # painted black onto a white card.
    aw = _ink(wide)
    ink = Image.new("RGB", aw.size, (255, 255, 255))
    ink.paste((0, 0, 0), (0, 0), aw)
    W, H = 1200, 630
    card = Image.new("RGB", (W, H), (255, 255, 255))
    k = min(W * 0.84 / ink.width, H * 0.70 / ink.height)
    big = ink.resize((int(ink.width * k), int(ink.height * k)), Image.LANCZOS)
    card.paste(big, ((W - big.width) // 2, (H - big.height) // 2))
    card.save(LICENSED_OUT / "og.png", optimize=True)
    _section_cards(ink, LICENSED_OUT)
    return (f"licensed: lockup.png {a.width}x{a.height} (stacked), og.png and "
            f"{len(OG_SECTIONS)} section cards (one line), {mark} "
            "-> assets/licensed/")

MANIFEST = """{
  "name": "Granite Record",
  "short_name": "Granite Record",
  "description": "Every bill, vote, hearing and floor debate of the New Hampshire General Court.",
  "start_url": "/",
  "scope": "/",
  "display": "browser",
  "background_color": "#F4F5F3",
  "theme_color": "#111514",
  "icons": [
    {"src": "/icon.svg", "type": "image/svg+xml", "sizes": "any"},
    {"src": "/icon-180.png", "type": "image/png", "sizes": "180x180"},
    {"src": "/icon-512.png", "type": "image/png", "sizes": "512x512"},
    {"src": "/icon-512-pad.png", "type": "image/png", "sizes": "512x512", "purpose": "maskable"}
  ]
}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="say what is missing and write nothing")
    a = ap.parse_args()
    if a.check:
        for f, what in ORIGINALS:
            p = BRAND / f
            print(f"  {'ok ' if p.exists() else 'MISSING'} brand/{f}"
                  + ("" if p.exists() else f"   <- {what}"))
        for stem in ("lockup-stacked", "lockup-wide", "drawing"):
            print(f"  {'ok ' if _licensed(stem) else 'none   '} brand/licensed/{stem}"
                  "   (the project's licensed logo; a fork has none)")
        return
    OUT.mkdir(exist_ok=True)
    d = path_data()
    frame = icon_framing()
    said = [write_icon_svg(d, frame)]
    said.append(write_pngs())
    said.append(write_og())
    said.append(write_og_sections())
    said.append(write_lockup())
    said.append(write_licensed() or "licensed: brand/licensed/ does not hold "
                "the artist's two lockups, so nothing was written to "
                "assets/licensed/: the heading and the cards are the ones above "
                "and the header is the wordmark alone")
    (OUT / "site.webmanifest").write_text(MANIFEST, encoding="utf-8")
    said.append("site.webmanifest")
    for line in said:
        print("  " + line)
    print(f"  -> {OUT.relative_to(ROOT)}/ ({len(list(OUT.iterdir()))} files); "
          "build_pages.py copies them into site/")


if __name__ == "__main__":
    main()
