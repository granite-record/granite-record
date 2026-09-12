#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-12.1
"""
Turn the drawn logo and icon into the files a site needs, once.

    python3 build_brand.py            # reads brand/, writes assets/
    python3 build_brand.py --check    # says what is missing, writes nothing

WHY THIS EXISTS AS A BUILD STEP

`site/` is generated and gitignored, so an icon dropped in there disappears on
the next build and is never in the repository. The drawn originals live in
`brand/` and are checked in; this writes the derived files into `assets/`,
which `build_pages.py` copies into `site/` beside the pages. One source, one
copy step, and the originals are recoverable.

The logo is TEMPORARY. It is the person's own drawing, standing in until the
artist whose Old Man of the Mountain we want gives permission, and the whole
point of keeping the originals and this script is that replacing it later is
one command rather than an archaeology exercise.

WHAT IS DERIVED, AND WHY EACH ONE

  mark.svg          the profile alone, tight to its own bounding box, used as
                    a CSS mask so the nav's mark takes the colour of the text
                    beside it and is right in both themes without two files.
  icon.svg          the icon as drawn -- white profile on the black tile --
                    at any size a tab, a bookmark or a pinned shortcut asks
                    for. The framing is measured off the drawn PNG rather
                    than guessed, so it is the same composition.
  icon-32/180/512   PNG fallbacks. Safari wants a PNG for apple-touch-icon
                    and a manifest wants real bitmaps.
  icon-512-pad      the maskable one: Android crops an icon to whatever shape
                    the launcher uses, so the mark sits inside the middle 80%.
  favicon.ico       for the bare /favicon.ico a browser asks for anyway, in
                    the three sizes that file format is actually used at.
  og.png            1200x630 for a shared link's card, the black-on-white
                    lockup padded onto white so the card is seamless rather
                    than a black block inside a white border.

A NOTE ON THE ORIGINALS' NAMES. They arrived as "Logo Black.png" and "Logo
White.png", named for their BACKGROUND: the first is the white wordmark on
black. Checked in here as logo-on-black.png and logo-on-white.png, named for
what they are, because the first draft of this script read the wrong one and
put a black tile in a white frame on every shared link.
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BRAND = ROOT / "brand"
OUT = ROOT / "assets"

# The profile's own bounding box inside the drawing's 210x297 viewBox, read
# with getBBox() in a browser rather than estimated from the path data.
BBOX = (23.805, 15.638, 156.228, 248.628)


def need(p):
    if not p.exists():
        sys.exit(f"missing {p.relative_to(ROOT)} -- put the drawn originals in "
                 f"brand/ first (see this file's docstring)")
    return p


def path_data():
    """The one path out of the drawn SVG, with nothing else it carries."""
    src = need(BRAND / "old-man.svg").read_text(encoding="utf-8")
    paths = re.findall(r'<path\b[^>]*\sd="([^"]+)"', src)
    if len(paths) != 1:
        sys.exit(f"brand/old-man.svg has {len(paths)} paths; this expects one")
    return paths[0]


def write_mark(d):
    x, y, w, h = BBOX
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {w} {h}">'
           f'<path d="{d}"/></svg>')
    (OUT / "mark.svg").write_text(svg, encoding="utf-8")
    return f"mark.svg  {len(svg):,} bytes, viewBox tight to the shape"


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
    """The icon as drawn, as an SVG, at the PNG's own framing."""
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
    pad = Image.new("RGB", (512, 512), (17, 21, 20))
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
        for f in ("old-man.svg", "icon.png", "logo-on-white.png",
                  "logo-on-black.png"):
            p = BRAND / f
            print(f"  {'ok ' if p.exists() else 'MISSING'} brand/{f}")
        return
    OUT.mkdir(exist_ok=True)
    d = path_data()
    said = [write_mark(d)]
    frame = icon_framing()
    said.append(write_icon_svg(d, frame))
    said.append(write_pngs())
    said.append(write_og())
    (OUT / "site.webmanifest").write_text(MANIFEST, encoding="utf-8")
    said.append("site.webmanifest")
    for line in said:
        print("  " + line)
    print(f"  -> {OUT.relative_to(ROOT)}/ ({len(list(OUT.iterdir()))} files); "
          "build_pages.py copies them into site/")


if __name__ == "__main__":
    main()
