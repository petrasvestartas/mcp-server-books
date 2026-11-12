# Books

Scanned book -> English Markdown -> R2 -> Teaching website.

1. Scan: PDF in `Books/RAW/`.
2. OCR: `tools/mistral_ocr.py`.
3. Translate + proofread: agent with `tools/TRANSLATE_BRIEF.md`, `tools/PROOF_BRIEF.md`.
4. Figures: `tools/figcrop.py`, `tools/structlabels.py`.
5. Upload: `tools/upload-books.sh`.
6. Website: `PROCESSED.md` row, `tools/r2_library_map.sh --upload`.
