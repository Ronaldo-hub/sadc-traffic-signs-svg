# Traffic Sign Reference-to-SVG Workflow

This guide covers the repeatable workflow for turning a photograph in
`reference_images/` into a clean, standalone SVG in `generated_signs/`. It is
written for both a human/AI coding agent working in the repository and a
notebook running in Google Colab.

## What Is Automatic

The draft script processes every `.jpg`, `.jpeg`, and `.png` file in
`reference_images/`. It renders source SVGs, ranks them as possible visual
starting points, and creates one draft and one 50% comparison overlay per
reference. Adding a file does not execute the script automatically: run it after
uploading the image. No file watcher or CI trigger is configured. Run it from
the repository root:

```bash
python -m pip install -r requirements.txt
python scripts/generate_sign_from_reference.py
```

For an input named `reference_images/R101.jpg`, the script writes:

| Output | Purpose |
| --- | --- |
| `generated_signs/R101_draft.svg` | Starting point copied from the top-ranked source SVG, or a generic placeholder when there are no source SVGs |
| `overlays/R101_draft.png` | Draft rendered to the exact reference-image dimensions |
| `overlays/R101_overlay.png` | 50% blend of the reference and draft render for alignment checks |
| `renders/<source-name>.png` | Cached renders of source SVGs used for ranking |

The script does **not** infer or draw the correct sign symbol from a JPEG. Its
similarity score compares resized raster images and is only a way to suggest a
starting source; it can rank an unrelated sign first. A generic placeholder is
not a finished sign. An agent or person must inspect the image, build or select
the correct vector components, and save the reviewed result as
`generated_signs/<SIGN_ID>.svg` (without `_draft`). The script never writes the
final filename. This review is necessary because a photograph alone does not
reliably encode the exact paths, colors, layers, or geometry of a clean vector
sign.

## Naming Rules

1. Name each reference with its traffic-sign ID, for example `R101.jpg`,
    `R201-120.jpeg`, or `W308.png`.
2. Use one reference image per ID. Duplicate stems with different extensions or
    letter case are rejected because they would overwrite the same draft.
3. Upload/copy the image into `reference_images/`, then run the script from the
    repository root. It processes all supported images in that folder on every
    run.
4. Put reviewed final SVGs in `generated_signs/<SIGN_ID>.svg`. Keep drafts
    separate; do not treat `_draft.svg` or an overlay as a final asset.

## Local Workflow

1. Check the worktree and name the reference file by sign ID:

    ```bash
    git status --short --branch
    ls reference_images
    ```

2. Install the repository dependencies and generate draft/overlay files:

    ```bash
    python -m pip install -r requirements.txt
    python scripts/generate_sign_from_reference.py
    ```

3. Inspect `overlays/<SIGN_ID>_overlay.png` and the original image. The overlay
    is a diagnostic only: doubled edges indicate a difference in size or
    placement, while photo glare/compression can cause differences that should
    not be copied into the vector.

4. Inspect relevant source and component assets. Search by sign code and likely
    symbol name; the repository's extracted symbols live under
    `components/extracted_symbols/`:

    ```bash
    rg --files source_svgs components | rg -i 'R101|R201|symbol'
    ```

    Render candidate SVGs before choosing them. Confirm that the frame geometry,
    border order, colors, and symbol are actually applicable. Do not trust the
    script's top-ranked source without visual inspection.

5. If a source SVG has the right frame but contains a different symbol, use its
    frame geometry and replace the symbol. If the correct symbol exists in
    `components/extracted_symbols/`, copy its drawable geometry into the final
    SVG and scale/position it. Otherwise, extract a candidate from a matching
    source SVG:

    ```bash
    python scripts/symbol_extractor.py source_svgs components/extracted_symbols
    ```

    The extractor uses geometric heuristics to remove large frame/background
    shapes. Inspect its output: some frames overlap symbols, and some SVGs use
    text or complex clipping that the extractor cannot turn into a reusable
    symbol automatically. Convert text to paths in a vector editor before
    extraction, or redraw the needed glyph as paths. Do not assume every
    extracted file is correct just because it was created by the script.

6. Create `generated_signs/<SIGN_ID>.svg` as a standalone SVG. Use the reference
    image's pixel dimensions for `width`, `height`, and `viewBox` so one SVG unit
    corresponds to one reference pixel. Draw back-to-front: background, outer
    frame, inner border(s), sign face, then symbol. Use inline `<path>`,
    `<circle>`, `<rect>`, and `<g>` geometry. Copy/inline reusable paths instead
    of depending on external image or SVG files.

7. Measure the reference instead of guessing. Record the canvas dimensions,
    sign bounds, center, circle/shape radii, border widths, symbol bounds, and
    sampled flat colors. Ignore JPEG edge pixels when sampling colors; use an
    interior pixel away from glare, shadows, and antialiased boundaries. Keep a
    short measurement note while iterating.

8. Render the final SVG at the exact reference dimensions and make a new overlay:

    ```bash
    python -c "import cairosvg; cairosvg.svg2png(url='generated_signs/R101.svg', write_to='/tmp/R101.png', output_width=81, output_height=88, background_color='white')"
    python -c "from PIL import Image; Image.blend(Image.open('reference_images/R101.jpg').convert('RGB'), Image.open('/tmp/R101.png').convert('RGB'), 0.5).save('/tmp/R101_overlay.png')"
    ```

    Replace `R101` and the dimensions with the current sign ID and image size.
    View the overlay, adjust paths/geometry, and repeat. The draft script's
    overlay is based on `_draft.svg`; it is not refreshed automatically after
    editing the final SVG.

9. Check that the final SVG parses, renders, has no `<text>` or embedded raster
    image, has no external dependencies, and visually matches the reference.
    Run `git diff --check`. Keep the final file, source asset, and measurement
    decisions easy to review. Do not commit or push unless requested.

## Google Colab Workflow

Run these cells in order. Upload reference images using their sign IDs, then
download the reviewed final SVG after reconstruction.

```python
!git clone https://github.com/Ronaldo-hub/sadc-traffic-signs-svg.git
%cd /content/sadc-traffic-signs-svg
!pip install -r requirements.txt
```

Upload one or more reference images into the repository's `reference_images/`
directory:

```python
from google.colab import files
from pathlib import Path

uploaded = files.upload()
for filename, contents in uploaded.items():
     target = Path("reference_images") / Path(filename).name
     target.write_bytes(contents)
```

Generate drafts and overlays for all uploaded images:

```python
!python scripts/generate_sign_from_reference.py
```

View/download the overlay and final result as needed:

```python
from IPython.display import display, Image
display(Image(filename="overlays/R101_overlay.png"))
```

After an agent or person creates and verifies `generated_signs/R101.svg`,
download it from Colab:

```python
from google.colab import files
files.download("generated_signs/R101.svg")
```

Colab's local filesystem is temporary. Download the final file or commit/push
it from the notebook only after reviewing the diff and confirming the desired
GitHub credentials are configured. The draft script itself does not commit or
push files.

## Worked Example: R101

The current R101 reference is 81 x 88 pixels. No exact R101 frame or extracted
`50` symbol was available, so the final was constructed from the closest
matching circular mandatory-sign frame and new vector paths for the digits.
The frame proportions were measured against the circular source
`source_svgs/SADC_road_sign_R102.svg`; the source's ring ratio was a starting
point, not a replacement for measuring the R101 photo. The sign center is
approximately `(40.5, 44)`. The final file uses a light outer ring at radius 34,
a white ring at radius 32, and a blue face at radius 30. The blue was sampled
from the reference's flat interior area as approximately `#09479F`. The digits
are white `<path>` shapes, centered inside the blue face. This avoids font
availability and keeps the output self-contained. See
`generated_signs/R101.svg` for the actual path data and layer order.

The first comparison showed the blue face was too small and the source blue was
not a close match. Sampling the reference and scaling the source frame's
blue/outer-radius ratio led to the final face radius and color above. This is
the intended loop for every sign: start from assets where useful, measure the
actual reference, render, overlay, and correct.

## Quality Checklist

- [ ] Input is named `reference_images/<SIGN_ID>.jpg`, `.jpeg`, or `.png`.
- [ ] Draft and overlay are generated; the overlay was visually inspected.
- [ ] Frame and symbol sources were checked visually, not selected only by score.
- [ ] Final SVG is `generated_signs/<SIGN_ID>.svg` and matches the reference's
        pixel dimensions.
- [ ] Geometry, colors, symbol scale, and layering were compared to the photo.
- [ ] SVG contains no `<text>`, embedded raster image, or external dependency.
- [ ] Final SVG parses and renders; `git diff --check` passes.
- [ ] Final changes are reviewed before commit/push.
