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

DRAFT_NAME = "R101_draft"


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

    for d in [source_dir, render_dir, overlay_dir, generated_dir, reference_dir]:
        d.mkdir(exist_ok=True)

    # 1. Render all source SVGs (re-render if the SVG changed)
    print("\n>>> Rendering source SVGs to PNG...")
    sources = sorted(source_dir.glob("*.svg"))
    for svg in sources:
        png_path = render_dir / (svg.stem + ".png")
        if needs_render(svg, png_path):
            try:
                render_svg_to_png(svg, png_path)
                print("  OK  " + svg.name)
            except Exception as e:
                print("  FAIL " + svg.name + ": " + str(e))

    # 2. Load reference image
    ref_candidates = sorted(reference_dir.glob("R101*"))
    if not ref_candidates:
        raise FileNotFoundError("Please put R101.jpg (or R101.png) in reference_images/")

    ref_path = ref_candidates[0]
    ref_img = Image.open(ref_path).convert("RGB")
    ref_size = ref_img.size
    ref_colors = get_dominant_colors(ref_img)

    print("\n=== Reference Image Analysis ===")
    print("File           : " + ref_path.name)
    print("Size           : {} x {}".format(*ref_size))
    print("Dominant colors: " + str(ref_colors))

    # 3. Find best matching base SVG (only real source SVGs, never earlier drafts)
    print("\n>>> Searching for best matching base SVG...")
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

    print("Best match     : " + (best_svg.name if best_svg else "None"))
    if best_svg:
        print("Similarity     : {:.1f} (lower is better)".format(best_score))

    # 4. Create initial draft
    print("\n>>> Creating initial draft SVG...")
    draft_path = generated_dir / (DRAFT_NAME + ".svg")

    if best_svg:
        draft_path.write_text(best_svg.read_text(encoding="utf-8"), encoding="utf-8")
        print("  Draft created from: " + best_svg.name)
    else:
        w, h = ref_size
        blue = pick_sign_colour(ref_colors)
        minimal = "\n".join([
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'.format(w=w, h=h),
            '  <rect width="100%" height="100%" fill="#FFFFFF"/>',
            '  <circle cx="{cx}" cy="{cy}" r="{r}" fill="{c}"/>'.format(cx=w // 2, cy=h // 2, r=min(w, h) // 2 - 20, c=blue),
            '  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#FFFFFF" stroke-width="18"/>'.format(cx=w // 2, cy=h // 2, r=min(w, h) // 2 - 40),
            '</svg>',
        ])
        draft_path.write_text(minimal, encoding="utf-8")
        print("  Created minimal draft (no source SVGs to match against)")

    # 5. Render draft + create 50% overlay (draft PNG lives outside renders/)
    print("\n>>> Creating overlay for visual comparison...")
    draft_png = overlay_dir / (DRAFT_NAME + ".png")
    overlay_path = overlay_dir / "R101_overlay.png"

    render_svg_to_png(draft_path, draft_png, size=ref_size)
    draft_img = Image.open(draft_png).convert("RGB")
    Image.blend(ref_img, draft_img, 0.5).save(overlay_path)

    print("  Draft SVG    : " + str(draft_path))
    print("  Draft PNG    : " + str(draft_png))
    print("  Overlay      : " + str(overlay_path))

    print("\n=== NEXT STEPS ===")
    print("1. Open overlays/R101_overlay.png")
    print("2. Tell the AI what still looks wrong")
    print("3. Iterate using the Render -> Overlay -> Measure loop")
    print("==================")


if __name__ == "__main__":
    main()
