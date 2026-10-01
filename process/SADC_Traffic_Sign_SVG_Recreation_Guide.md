# SADC / South African Traffic Sign SVG Recreation Guide

**Purpose**  
This document is a complete, agent-executable guide for recreating South African and SADC traffic signs as clean, pixel-accurate SVGs.

---

## 1. Dependencies

```bash
pip install pillow numpy requests cairosvg
apt-get update && apt-get install -y imagemagick
```

---

## 2. Repository Structure

```
sadc-traffic-signs-svg/
├── README.md
├── requirements.txt
├── reference_images/
├── source_svgs/
├── components/
├── generated_signs/
├── scripts/
└── process/
    └── SADC_Traffic_Sign_SVG_Recreation_Guide.md
```

---

## 3. Core Principle

> **Stop guessing. Measure every coordinate and colour directly from the reference image.**
> **One SVG unit = one reference pixel.**

---

## 4. Step-by-Step Process

### Step 1 – Establish the Coordinate System
- Open the reference image and record its exact pixel size.
- Create the SVG with exactly that size as `viewBox`, `width` and `height`.

### Step 2 – Sample True Colours
- Never invent a hex value.
- Sample flat areas of the image and use the real colours.

### Step 3 – Measure Every Geometric Element
- Record bounding boxes, stroke widths, radii, and path points.

### Step 4 – Build the SVG from Simple Primitives Only
**Allowed:** `rect`, `circle`, `path`, `g`  
**Forbidden:** `<text>`, fonts, embedded images

Construction order (back to front):
1. White page background
2. Sign body (blue or red)
3. White rings / borders
4. Digits as pure geometry
5. Vehicle / symbol
6. Cut-outs painted in the background colour

### Step 5 – Render → Overlay → Measure Loop
1. Render the SVG to PNG at the exact reference size
2. Create a 50% overlay with the reference photo
3. Adjust until only anti-aliasing differences remain

### Step 6 – Final Clean-up
- No fonts or `<text>`
- All colours are sampled values
- Save into `generated_signs/`

---

## 5. Extracting Reusable Components

1. Download the Commons SVG into `source_svgs/`
2. Isolate the desired path or group
3. Recolour the main body to pure white (`#FFFFFF`)
4. Save the clean fragment into `components/`

---

## 6. Quality Gate

- Mean absolute pixel difference < 8
- No doubled edges on the overlay
- No fonts or external references
