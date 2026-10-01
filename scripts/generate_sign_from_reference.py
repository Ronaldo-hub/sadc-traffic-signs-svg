#!/usr/bin/env python3
'''
SADC Traffic Sign Automation Pipeline
-------------------------------------
Helps automate the creation of SVG traffic signs from reference images.
Follows the measurement-based process defined in:
process/SADC_Traffic_Sign_SVG_Recreation_Guide.md
'''

import subprocess
import sys
from collections import Counter
from pathlib import Path

try:
    import cairosvg
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "cairosvg"], check=True)
    import cairosvg

import numpy as np
from PIL import Image

REFERENCE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def render_svg_to_png(svg_path, png_path, size=None):
    '''Render an SVG to PNG on a white background (optionally at an exact size).'''
    kwargs = {"url": str(svg_path), "write_to": str(png_path), "background_color": "white"}
    if size:
        kwargs["output_width"], kwargs["output_height"] = size
    cairosvg.svg2png(**kwargs)


def get_dominant_colors(img, n=5):
    '''Dominant colours as hex strings (near-identical shades are grouped together).'''
    arr = np.array(img.convert("RGB").resize((150, 150))).reshape(-1, 3)
    counts = Counter(map(tuple, (arr // 8) * 8 + 4))
    return ["#{:02x}{:02x}{:02x}".format(r, g, b) for (r, g, b), _ in counts.most_common(n)]


def pick_sign_colour(colours):
    '''First dominant colour that is not near-white or near-black (used for the fallback draft).'''
    for c in colours:
        r, g, b = (int(c[i:i + 2], 16) for i in (1, 3, 5))
        if 40 < (r + g + b) / 3 < 235:
            return c
    return "#0D5798"


def image_similarity(img1, img2):
    '''Mean absolute pixel difference on a 200x200 version (lower = more similar).'''
    a = np.array(img1.convert("RGB").resize((200, 200))).astype(float)
    b = np.array(img2.convert("RGB").resize((200, 200))).astype(float)
    return float(np.mean(np.abs(a - b)))


def needs_render(svg, png):
    return (not png.exists()) or png.stat().st_mtime < svg.stat().st_mtime


def main():
    print("=== SADC Sign Automation Pipeline ===")

    source_dir = Path("source_svgs")
    render_dir = Path("renders")
    overlay_dir = Path("overlays")
    generated_dir = Path("generated_signs")
    reference_dir = Path("reference_images")

    for directory in [source_dir, render_dir, overlay_dir, generated_dir, reference_dir]:
        directory.mkdir(exist_ok=True)

    print("\n>>> Rendering source SVGs to PNG...")
    sources = sorted(source_dir.glob("*.svg"))
    for svg in sources:
        png_path = render_dir / (svg.stem + ".png")
        if needs_render(svg, png_path):
            try:
                render_svg_to_png(svg, png_path)
                print("  OK  " + svg.name)
            except Exception as exc:
                print("  FAIL " + svg.name + ": " + str(exc))

    # 2. Find all supported reference images. The filename stem is the sign ID.
    references = sorted(
        path for path in reference_dir.iterdir()
        if path.is_file() and path.suffix.lower() in REFERENCE_EXTENSIONS
    )
    if not references:
        print("No .jpg, .jpeg, or .png references found in reference_images/")
        return

    identifiers = [path.stem.casefold() for path in references]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Reference images must have unique filenames, ignoring extension and case")

    # 3. Prepare an initial candidate and comparison overlay for each reference.
    for ref_path in references:
        sign_id = ref_path.stem.upper()
        ref_img = Image.open(ref_path).convert("RGB")
        ref_size = ref_img.size
        ref_colors = get_dominant_colors(ref_img)

        print("\n=== Reference Image Analysis: {} ===".format(sign_id))
        print("File           : " + ref_path.name)
        print("Size           : {} x {}".format(*ref_size))
        print("Dominant colors: " + str(ref_colors))

        print("\n>>> Ranking source SVG candidates...")
        best_score = float("inf")
        best_svg = None

        for svg in sources:
            png = render_dir / (svg.stem + ".png")
            if not png.exists():
                continue
            try:
                score = image_similarity(ref_img, Image.open(png))
            except Exception:
                continue
            if score < best_score:
                best_score, best_svg = score, svg

        print("Top candidate  : " + (best_svg.name if best_svg else "None"))
        if best_svg:
            print("Similarity     : {:.1f} (lower is closer; inspect manually)".format(best_score))

        draft_path = generated_dir / (sign_id + "_draft.svg")
        if best_svg:
            draft_path.write_text(best_svg.read_text(encoding="utf-8"), encoding="utf-8")
            print("Draft source   : " + best_svg.name)
        else:
            w, h = ref_size
            blue = pick_sign_colour(ref_colors)
            minimal = "\n".join([
                '<?xml version="1.0" encoding="UTF-8"?>',
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'.format(w=w, h=h),
                '  <rect width="100%" height="100%" fill="#FFFFFF"/>',
                '  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>'.format(cx=w / 2, cy=h / 2, r=max(1, min(w, h) * 0.35), c=blue),
                '</svg>',
            ])
            draft_path.write_text(minimal, encoding="utf-8")
            print("Draft source   : generic color-and-circle placeholder")

        draft_png = overlay_dir / (sign_id + "_draft.png")
        overlay_path = overlay_dir / (sign_id + "_overlay.png")
        render_svg_to_png(draft_path, draft_png, size=ref_size)
        draft_img = Image.open(draft_png).convert("RGB")
        Image.blend(ref_img, draft_img, 0.5).save(overlay_path)

        print("Draft SVG      : " + str(draft_path))
        print("Draft PNG      : " + str(draft_png))
        print("Overlay        : " + str(overlay_path))

    print("\nInitial drafts created. Review each overlay and reconstruct/verify final SVGs manually.")
if __name__ == "__main__":
    main()
