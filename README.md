# SADC Traffic Signs SVG

Clean, reusable SVG library of South African / SADC road traffic signs.

## Folders

| Folder | Purpose |
|--------|---------|
| `source_svgs/` | Original SVGs from Wikimedia Commons |
| `components/` | Extracted reusable symbols |
| `generated_signs/` | Final production-ready signs |
| `reference_images/` | Photographs used for reconstruction |
| `process/` | Full measurement-based recreation guide |

To create per-sign drafts and comparison overlays for images in `reference_images/`,
install the requirements and run:

```bash
python -m pip install -r requirements.txt
python scripts/generate_sign_from_reference.py
```

Run the command after adding images; there is no file watcher or CI trigger.
It creates drafts and overlays; a person or AI agent must inspect the
reference and finish/verify the clean vector artwork. See
`process/SADC_Traffic_Sign_SVG_Recreation_Guide.md` for the complete workflow,
Colab instructions, file naming, asset extraction, and quality checks.
