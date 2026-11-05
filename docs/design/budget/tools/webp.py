"""The mock's full-page screenshots as lossless WebP, each in parts under
WebP's 16,383-pixel limit. Args: shots folder, output folder. Overwrites the
state-budget-*.webp files it writes; leaves anything else alone."""
import math, sys
from pathlib import Path
from PIL import Image

shots, out = Path(sys.argv[1]), Path(sys.argv[2])
for old in out.glob("state-budget-*.webp"):
    old.unlink()
for n in ("390-light", "390-dark", "1280-light", "1280-dark"):
    im = Image.open(shots / f"budget-{n}.png")
    w, h = im.size
    k = math.ceil(h / 12000)
    step = math.ceil(h / k)
    for i in range(k):
        im.crop((0, i * step, w, min(h, (i + 1) * step))).save(
            out / f"state-budget-{n}-{i + 1}.webp", lossless=True, method=6)
    print(n, h, k)
