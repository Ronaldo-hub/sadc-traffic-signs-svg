#!/usr/bin/env python3
"""
Extract the central symbol from SADC / road-traffic-sign SVGs.

For every .svg in the input folder (default ./source_svgs) this removes the
sign's frame (outer ring, white inner disc, borders, background panels) and
saves only the symbol artwork to the output folder (default ./extracted_symbols)
as  symbol_<original name>.svg  so it can be reused to build other signs.

How it decides what is "frame" and what is "symbol"
---------------------------------------------------
* Every drawable shape (path, rect, circle, ellipse, polygon, polyline) is
  measured in *final canvas coordinates*, i.e. with all parent <g> transforms
  applied (Inkscape layers almost always carry a translate()).
* Any shape that spans >= `frame_threshold` (default 75%) of the sign's overall
  width AND height is treated as frame/background and dropped.
* Tiny specks are dropped as noise.
* Everything else is kept, in the original drawing order, so white "cut-out"
  shapes inside a symbol (e.g. the hole in a 0) are preserved.
* The result is moved to the origin, so every symbol file has a clean
  viewBox of "0 0 w h" (plus padding), ready to be placed/scaled in new signs.

Dependency:  pip install svgpathtools
"""
import argparse
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from svgpathtools import parse_path

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

SHAPE_TAGS = {"path", "rect", "circle", "ellipse", "polygon", "polyline"}
SKIP_TAGS = {"defs", "metadata", "namedview", "clipPath", "mask", "pattern",
             "symbol", "marker", "title", "desc", "style", "script"}
# CSS properties that children inherit from parent groups
INHERITED_PROPS = {
    "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width",
    "stroke-opacity", "stroke-linecap", "stroke-linejoin",
    "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset",
}

IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


# --------------------------------------------------------------------------
# small helpers: transforms, styles, lengths
# --------------------------------------------------------------------------
def local(tag):
    return tag.split("}")[-1] if "}" in tag else tag


def num(value, default=0.0):
    """Parse '12.5', '12.5px', '1e3' ... into a float."""
    if value is None:
        return default
    m = re.match(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)", value)
    return float(m.group(1)) if m else default


def mat_mul(m1, m2):
    """Return m1 * m2 (m2 is applied first)."""
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def parse_transform(text):
    """Parse an SVG transform attribute into a 6-tuple matrix."""
    m = IDENTITY
    if not text:
        return m
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", text):
        v = [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", args)]
        if name == "matrix" and len(v) == 6:
            t = tuple(v)
        elif name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            a = math.radians(v[0])
            ca, sa = math.cos(a), math.sin(a)
            t = (ca, sa, -sa, ca, 0, 0)
            if len(v) == 3:
                cx, cy = v[1], v[2]
                t = mat_mul(mat_mul((1, 0, 0, 1, cx, cy), t), (1, 0, 0, 1, -cx, -cy))
        elif name == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            continue
        m = mat_mul(m, t)
    return m


def apply(m, x, y):
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def style_dict(elem):
    """Presentation attributes + style="" merged (style wins)."""
    d = {}
    for k, v in elem.attrib.items():
        if k in INHERITED_PROPS or k in ("display", "visibility", "opacity"):
            d[k] = v
    for part in elem.get("style", "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def matrix_scale(m):
    a, b, c, d, _, _ = m
    return math.sqrt(abs(a * d - b * c))


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------
def shape_points(elem, tag, m):
    """Sample points of a shape, in final canvas coordinates."""
    pts = []
    if tag == "path":
        d = elem.get("d")
        if not d:
            return pts
        for seg in parse_path(d):
            n = 2 if type(seg).__name__ == "Line" else 40
            for i in range(n):
                p = seg.point(i / (n - 1))
                pts.append(apply(m, p.real, p.imag))
    elif tag == "rect":
        x, y = num(elem.get("x")), num(elem.get("y"))
        w, h = num(elem.get("width")), num(elem.get("height"))
        for px, py in ((x, y), (x + w, y), (x + w, y + h), (x, y + h)):
            pts.append(apply(m, px, py))
    elif tag in ("circle", "ellipse"):
        cx, cy = num(elem.get("cx")), num(elem.get("cy"))
        if tag == "circle":
            rx = ry = num(elem.get("r"))
        else:
            rx, ry = num(elem.get("rx")), num(elem.get("ry"))
        for i in range(96):
            a = 2 * math.pi * i / 96
            pts.append(apply(m, cx + rx * math.cos(a), cy + ry * math.sin(a)))
    elif tag in ("polygon", "polyline"):
        nums = [float(x) for x in re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?",
                                              elem.get("points", ""))]
        for i in range(0, len(nums) - 1, 2):
            pts.append(apply(m, nums[i], nums[i + 1]))
    return pts


def bbox_of(points, inflate=0.0):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs) - inflate, min(ys) - inflate, max(xs) + inflate, max(ys) + inflate)


# --------------------------------------------------------------------------
# SVG walking
# --------------------------------------------------------------------------
def collect_shapes(node, ctm, inherited, out):
    """
    Depth-first walk in document order. Appends dicts:
      elem, bbox, parent_ctm, inherited
    """
    for child in node:
        if not isinstance(child.tag, str):
            continue
        tag = local(child.tag)
        if tag in SKIP_TAGS:
            continue

        st = style_dict(child)
        if st.get("display") == "none" or st.get("visibility") == "hidden":
            continue

        if tag == "g" or tag == "svg" or tag == "a":
            child_ctm = mat_mul(ctm, parse_transform(child.get("transform")))
            child_inh = dict(inherited)
            child_inh.update({k: v for k, v in st.items() if k in INHERITED_PROPS})
            collect_shapes(child, child_ctm, child_inh, out)
        elif tag in SHAPE_TAGS:
            full_ctm = mat_mul(ctm, parse_transform(child.get("transform")))
            try:
                pts = shape_points(child, tag, full_ctm)
            except Exception as exc:  # malformed path data etc.
                print(f"  ! skipping unreadable <{tag}> ({exc})")
                continue
            if not pts:
                continue
            eff = dict(inherited)
            eff.update({k: v for k, v in st.items() if k in INHERITED_PROPS})
            stroke = eff.get("stroke", "none")
            inflate = 0.0
            if stroke not in ("none", "") :
                inflate = num(eff.get("stroke-width"), 1.0) * matrix_scale(full_ctm) / 2
            out.append({
                "elem": child,
                "tag": tag,
                "bbox": bbox_of(pts, inflate),
                "parent_ctm": ctm,
                "inherited": inherited,
            })
        elif tag == "text":
            print("  ! <text> found - convert text to paths in Inkscape "
                  "(Path > Object to Path) so it can be extracted")


def clean_copy(elem):
    """Copy a shape, dropping inkscape/sodipodi attributes (keeps xlink)."""
    attrs = {k: v for k, v in elem.attrib.items()
             if not k.startswith("{") or k.startswith("{" + XLINK_NS + "}")}
    new = ET.Element(elem.tag, attrs)
    new.text = elem.text
    return new


def fmt(x):
    return f"{x:.3f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------
# main extraction
# --------------------------------------------------------------------------
def extract_symbol_from_svg(input_path: Path, output_path: Path,
                            padding: float = 15.0,
                            frame_threshold: float = 0.75,
                            noise_fraction: float = 0.005) -> bool:
    try:
        root = ET.parse(input_path).getroot()
    except ET.ParseError:
        print(f"Skipping invalid XML: {input_path.name}")
        return False

    shapes = []
    collect_shapes(root, IDENTITY, {}, shapes)
    if not shapes:
        print(f"No drawable shapes found in: {input_path.name}")
        return False

    # Overall extent of the sign = union of everything drawn
    sx0 = min(s["bbox"][0] for s in shapes)
    sy0 = min(s["bbox"][1] for s in shapes)
    sx1 = max(s["bbox"][2] for s in shapes)
    sy1 = max(s["bbox"][3] for s in shapes)
    sign_w, sign_h = sx1 - sx0, sy1 - sy0

    kept = []
    for s in shapes:
        x0, y0, x1, y1 = s["bbox"]
        w, h = x1 - x0, y1 - y0
        if w >= frame_threshold * sign_w and h >= frame_threshold * sign_h:
            continue  # border ring / inner disc / background panel
        if w < noise_fraction * sign_w and h < noise_fraction * sign_h:
            continue  # speck
        kept.append(s)

    if not kept:
        print(f"No isolated symbols detected in: {input_path.name}")
        return False

    x_min = min(s["bbox"][0] for s in kept)
    y_min = min(s["bbox"][1] for s in kept)
    x_max = max(s["bbox"][2] for s in kept)
    y_max = max(s["bbox"][3] for s in kept)
    view_w = (x_max - x_min) + 2 * padding
    view_h = (y_max - y_min) + 2 * padding

    new_root = ET.Element(f"{{{SVG_NS}}}svg", {
        "viewBox": f"0 0 {fmt(view_w)} {fmt(view_h)}",
        "width": fmt(view_w),
        "height": fmt(view_h),
    })
    # Moves the symbol to the origin (+padding)
    outer = ET.SubElement(new_root, f"{{{SVG_NS}}}g", {
        "transform": f"translate({fmt(padding - x_min)} {fmt(padding - y_min)})"
    })

    for s in kept:
        # Wrapper re-applies the parent groups' transform and inherited
        # fill/stroke, so the shape looks identical outside its original tree.
        wrap_attrs = {}
        m = s["parent_ctm"]
        if m != IDENTITY:
            wrap_attrs["transform"] = "matrix(" + " ".join(fmt(v) for v in m) + ")"
        if s["inherited"]:
            wrap_attrs["style"] = ";".join(f"{k}:{v}" for k, v in s["inherited"].items())
        wrapper = ET.SubElement(outer, f"{{{SVG_NS}}}g", wrap_attrs)
        wrapper.append(clean_copy(s["elem"]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(new_root)
    ET.indent(tree, space="  ")
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"Extracted {len(kept)} symbol shapes "
          f"(dropped {len(shapes) - len(kept)} frame/noise): "
          f"{input_path.name} -> {output_path.name}")
    return True


def batch_process_directory(input_dir: str, output_dir: str, **kwargs):
    input_folder = Path(input_dir)
    output_folder = Path(output_dir)

    if not input_folder.is_dir():
        print(f"Input folder not found: {input_folder}")
        return 1

    svg_files = sorted(p for p in input_folder.iterdir()
                       if p.is_file() and p.suffix.lower() == ".svg")
    if not svg_files:
        print(f"No SVG files found in {input_dir}")
        return 1

    print(f"Processing {len(svg_files)} SVG files...")
    ok = 0
    for svg_file in svg_files:
        out_file = output_folder / f"symbol_{svg_file.name}"
        if extract_symbol_from_svg(svg_file, out_file, **kwargs):
            ok += 1
    print(f"Done: {ok}/{len(svg_files)} files extracted -> {output_folder}")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Extract centre symbols from traffic sign SVGs.")
    ap.add_argument("input_dir", nargs="?", default="./source_svgs")
    ap.add_argument("output_dir", nargs="?", default="./extracted_symbols")
    ap.add_argument("--padding", type=float, default=15.0,
                    help="space around the symbol in px (default 15)")
    ap.add_argument("--frame-threshold", type=float, default=0.75,
                    help="shapes covering this fraction of the sign in both "
                         "width and height are treated as frame (default 0.75)")
    args = ap.parse_args()
    sys.exit(batch_process_directory(args.input_dir, args.output_dir,
                                     padding=args.padding,
                                     frame_threshold=args.frame_threshold))
