#!/usr/bin/env python3
"""Extract the dominant colours of the IncreaseNET logo.

Usage:
    python newsletter/extract_palette.py [newsletter/assets/increasenet-logo.png] [--colors 12]

Prints each cluster colour with its pixel share and its WCAG contrast ratio
against white, so you can decide which colours may be used as text (≥ 4.5:1)
and which are decoration only. Copy the validated hex codes into
newsletter/config.yaml → colors.

Requires Pillow (dev-only dependency): pip install pillow
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

DEFAULT_LOGO = Path(__file__).resolve().parent / "assets" / "increasenet-logo.png"


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: tuple[int, int, int], b: tuple[int, int, int] = (255, 255, 255)) -> float:
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def extract(path: Path, n_colors: int = 12, min_share: float = 0.02) -> list[tuple[str, float, float]]:
    """Return [(hex, share, contrast_vs_white)] sorted by share, merged clusters dropped."""
    im = Image.open(path).convert("RGBA")
    # keep opaque, non-white pixels (anti-aliased edges and background excluded)
    pixels = [p[:3] for p in im.getdata() if p[3] > 200 and sum(p[:3]) < 720]
    if not pixels:
        raise SystemExit("No opaque coloured pixels found in the logo.")
    strip = Image.new("RGB", (len(pixels), 1))
    strip.putdata(pixels)
    # MAXCOVERAGE keeps small but distinct hues (median-cut merges light blue + light green)
    q = strip.quantize(colors=n_colors, method=Image.Quantize.MAXCOVERAGE)
    palette = q.getpalette()
    out = []
    for count, idx in sorted(q.getcolors(), reverse=True):
        share = count / len(pixels)
        if share < min_share:
            continue
        rgb = tuple(palette[idx * 3: idx * 3 + 3])
        out.append(("#%02X%02X%02X" % rgb, share, contrast(rgb)))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logo", nargs="?", default=str(DEFAULT_LOGO))
    ap.add_argument("--colors", type=int, default=12)
    args = ap.parse_args()
    print(f"Palette of {args.logo}\n")
    print(f"{'hex':8}  {'share':>6}  {'contrast/white':>14}  usage")
    for hx, share, cr in extract(Path(args.logo), args.colors):
        usage = "text OK (AA)" if cr >= 4.5 else "decoration only"
        print(f"{hx:8}  {share * 100:5.1f}%  {cr:14.2f}  {usage}")


if __name__ == "__main__":
    main()
