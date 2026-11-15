# Teaching website

Site (`https://brg-teaching.github.io/Teaching/CAS/website/library.html`) reads R2. Book shows only when `done` in `PROCESSED.md` and indexed in `LIBRARY.md`.

1. Download R2 root `PROCESSED.md` first, add row `| \`<book>/\` | YYYY-MM-DD | done |` (or `tools/processed_status.py`), and upload `s3://brg-books/PROCESSED.md`.
2. Rebuild and upload `LIBRARY.md` (verify the book shows its chapter files, never `0 files`):

       python3 -I tools/r2_library_map.py --upload     # or: bash tools/r2_library_map.sh --upload

3. Check the book's subject section and interactive figure toggle in `BRG-teaching/Teaching` (`website/src/useLibrary.js`):
   - `SUBJECTS` classifies books into `Graphic statics`, `Form finding`, `Thrust networks & masonry`, `Materialization`, `Math`, `Computation`, and `Structural design & history` (mathematics books must match `Math`, never fall through to `Computation`).
   - `linkOrigFigures` reads `FIGURES.md` rows formatted as `| [Fig. 1](figures/<stem>.svg) · [original](figures/orig/<stem>.png) | ... |` (`tools/cad_redraft.py check <book>`) to wrap every chapter figure in the `Digital · Show original` click-to-toggle button.
4. Refresh `BRG-teaching/Teaching` GitHub Pages mirror:

       cd Teaching && git commit --allow-empty -m "Pages: rebuild <book>" && git push

Link: https://brg-teaching.github.io/Teaching/CAS/website/library.html#/b/<book>/README.md
