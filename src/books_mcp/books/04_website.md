# Teaching website

Site reads R2. Book shows only when `done` in `PROCESSED.md`.

1. Add row to R2 root `PROCESSED.md`: `| \`<book>/\` | YYYY-MM-DD | done |` (or `tools/processed_status.py`).
2. Upload it, rebuild map:

       bash tools/r2_library_map.sh --upload

3. Refresh site mirror:

       cd Teaching && git commit --allow-empty -m "Pages: rebuild <book>" && git push

Link: https://brg-teaching.github.io/Teaching/CAS/website/library.html#/b/<book>/README.md
