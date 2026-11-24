# Process a scanned book

Input: a local PDF path, a local folder of page photographs, or an HTTPS URL supplied by the user.

## Start

- Accept a quoted local PDF path, local folder of page photographs, or HTTPS URL. Ask for the source only if missing.
- Use `get_book_guide(include_library_map=false)` for conventions; without MCP,
  read `src/books_mcp/books/02_guide.md` from this checkout.
- Find the existing Books workspace from the supplied path, `BRG_BOOKS_DIR`, or a
  sibling `Books/` directory. Otherwise create a separate local workspace beside
  the PDF, or ask for a location when the input is a URL. Keep PDFs outside this code repo.
- The workspace `tools/` folder is this repo's `tools/` (symlink it: `ln -s <repo>/tools <Books>/tools`);
  `tools/templates/` holds `build.py`, example per-book briefs, and a `PROCESSING.md` from a finished book.
- Check PDF/image tooling and the workspace's trusted conversion scripts/briefs.
  If required tools are missing, report the exact missing dependency and complete
  any feasible scan/contents inspection; do not pretend conversion was completed.
- Preserve the input source unchanged. Download remote PDFs into workspace `RAW/`.
  When the input is a folder of camera/phone photographs, pack them into a **compact PDF** in `RAW/<Author_Title_Year>.pdf`
  using `tools/photos_to_pdf.py` (`--max-side 1800 --quality 75`, plus `--greyscale` for monochrome books so a 200-page book
  stays ~15–30 MiB and a 50-page colour book ~8–15 MiB — never upload multi-hundred-MB raw photo dumps to R2).
- Infer title, author, source language, and a stable author-title folder ID from
  the scan. Default output to English. Ask only when identity or destination is ambiguous.

## Process

1. Check pages, scan quality, contents, and errata. Save scope/progress in the book's `PROCESSING.md`.
   Spread scans (default): run `tools/spread_crop.py PDF WORK/<id>/spreads` first. It straightens every spread, crops it to the
   paper of both facing pages (no scanner bed, hands or fore-edge stack) and gives all spreads one aligned frame
   (median paper box for text-only, full-colour or blank spreads). Check a contact sheet of a sample before going on.
   Keep facing pages together ONLY for catalogue/plate books whose drawings run across the gutter (figures are one image
   per spread, `figures/ppLLLL-RRRR.png`, and SCANS.md uses the spread images). **For all prose textbooks, monographs,
   and handbooks: NEVER embed full-page or full-spread scans containing source-language prose as figures** — translate all
   prose and tables into English Markdown and crop **only** the individual figures, diagrams, charts, or photographs from
   each page (`tools/pagetool.py` or the `<stem>.images.json` bounding boxes saved by `tools/mistral_ocr.py`). Full-page
   scans belong exclusively in `scans/` + `SCANS.md`. Split into single pages (`tools/scan_split.py`, check one spread's
   rotation first) as OCR input and for single-page figure cropping. Better: `tools/spread_crop.py ... --split WORK/<id>/pages`
   cuts the straightened spreads exactly at the fold; OCR those pages. Pages cut from the raw scan keep a strip of the
   facing page, and the OCR then reads cut-off words ("This no", "demar") into the text.
   Clean the OCR before building (`tools/ocr_clean.py clean`, or `clean_text()` from a builder): running heads and their
   misreadings, step labels (A1, B2, A+B, 2x), page numbers, letter debris, icon marks, empty tables and layout JSON
   invented on blank pages; `--no-math` for books without formulas (OCR invents formulas on drawing-only pages);
   `--kanji` corrects look-alike Japanese characters only where the romanised reading confirms them.
   Before every upload run `tools/ocr_clean.py check <book>` and fix every reported line at its cause in the builder.
   Catalogue books (joints, details, plates: one item per spread) are published compactly: one entry per item —
   `## <name>`, its type, its names in the other languages, the spread image, one line with the pages and the scan
   link — and no other OCR text from those pages. Glossary-like definition pages become one entry per term
   (term, translations, definition as one paragraph). Builders that use multiprocessing must keep every write step
   under `if __name__ == "__main__":` (Python 3.14 workers re-import the script).
   Photo folders: EXIF-transpose upright JPEGs for OCR/cropping and build the compact `RAW/<Author_Title_Year>.pdf` via `tools/photos_to_pdf.py`.
   OCR: **always** use our Mistral account via `tools/mistral_ocr.py` (Markdown with LaTeX equations, equation numbers,
   and per-page figure bounding boxes saved to `<stem>.images.json` at zero extra cost, about $0.001/page; key in
   `~/.config/mistral/api_key` or `MISTRAL_API_KEY`). Render PDF pages first with
   `tools/pdf_render.py` (200 dpi, `p####.jpg` = PDF page) or pass upright page JPEGs directly, and run several shards in parallel;
   the per-page cache means a rerun never pays twice. Keep the cache until the book is published. Report pages billed and the running cost
   (pages × $0.001) in every progress update. Fall back to `tools/scan_ocr.sh` (tesseract) only without a key or for
   material that must not leave the machine, and say so.
   Map printed pages, detect duplicate scans (same printed number / near-identical image) and gaps with Python, not by reading.
   Cost: translation and proofread sub-agents run on Sonnet, ≤ 12 printed pages per job, working from the OCR draft and
   cropped equation/figure zones (never whole spreads in bulk). Sonnet proofreaders list doubtful pages under FLAGS;
   one Opus pass checks only those pages. Run automatic checks first (KaTeX compiles; every number, equation, figure
   and § number of the OCR appears in the translation; page markers complete).
2. Read workspace `tools/TRANSLATE_BRIEF.md` (or `AGENT_BRIEF.md`; ETH variant for course material);
   follow the shared guide. Work in chapter-sized units and resume existing work without overwriting it.
3. Transcribe/translate to `src/` with exact formulas, printed page/section markers,
   footnoted uncertainty, and original cropped figures (`tools/pagetool.py`). All text in English.
   Merge continuation parts with `tools/merge_parts.py`. Build published chapters.
4. Check every equation against the scan; run a separate page-by-page proofread (`tools/PROOF_BRIEF.md`)
   and log it in `REVIEW-*.md`. Then one book-wide consistency pass (terms, notation, title line)
   and `tools/fix_anchors.py`. Claim independent review only if a separate reviewer actually performed it.
5. Label structural figures (`tools/structlabels.py` as a first pass). Create README, INDEX, GLOSSARY,
   and FIGURES; follow the guide's construction rules.
   **Redraft all diagram/picture figures into parametric SVGs alongside original scans (mandatory rule):**
   - Preserve every cropped original scan in `figures/orig/<stem>.png` (`python3 -B -X utf8 tools/cad_redraft.py backup-orig <book>`, skipping photographic covers `cover.jpg` / `figures/cover-crop.png`).
   - Inspect every `figures/orig/<stem>.png` scan alongside `src/*.md` (never draw from `FIGURES.md` text alone; fix any inaccurate `FIGURES.md` or `alt` descriptions spotted) and author clean parametric 2D/3D CAD SVGs at `figures/<stem>.svg` (`tools/cad_engine.py` + `tools/CAD_REDRAFT_BRIEF.md`), translating source-language figure labels to English.
   - Verify `0 issues` (`tools/verify_cad_svg.py`), apply SVG references + `· [original](figures/orig/<stem>.png)` dual links in `src/*.md` and `FIGURES.md` (`python3 -B -X utf8 tools/cad_redraft.py apply-svgs <book>`), rebuild published chapters via `<book>/src/build.py`, inspect side-by-side contact sheets (`compare-sheets`), and pass `python3 -B -X utf8 tools/cad_redraft.py check <book>` so clicking any figure on `library.html` toggles `Digital · Show original` ↔ `Original · Show digital`.
   `INDEX.md` is the chapter list, one `## [Chapter title](NN-file.md)` heading
   plus a summary per published chapter (`tools/merge_index.py`): LIBRARY.md and the website read chapters only
   from it, so a book without these headings is listed as "0 files" and hidden. Start each summary directly with English
   prose (put `(pp. a–b)` at the end, never `*pp. a–b.*` at the start, because `library_map.py` takes the first sentence
   up to the first period). The book's own subject index is a
   chapter file (`NN-index.md`, as in `graphic-statics-foeppl/08-index.md`), never INDEX.md. Publish the scanned pages with `tools/scan_index.py`
   (`scans/` images + `SCANS.md`, printed page → scan) and link SCANS.md from README, so every page can be checked.
   Add `cover.jpg` for the library shelf: the front cover (for a dust jacket, only its front panel, not back or spine),
   else the title page; ≈600 px wide, straightened, cropped to the cover edge, with library stamps, barcode stickers,
   shelf marks and dust removed (look at the result).
6. Upload the compact PDF to `s3://brg-books/RAW/<Author_Title_Year>.pdf` and upload the clean book folder (including `figures/*.svg` with `Content-Type: image/svg+xml`, `figures/*.png`, `figures/orig/*.png`, and `cad/*.json`; without `.eqpng/`,
   `.checks/`, or `src/parts/`) to `s3://brg-books/<id>/` without remote deletions. Download the current R2 `PROCESSED.md`, add
   `| \`<id>/\` | YYYY-MM-DD | done |` (only `done` entries appear in `LIBRARY.md` and on the course website, with that date),
   upload `PROCESSED.md`, then regenerate and upload `LIBRARY.md` (`python3 -I tools/r2_library_map.py --upload` or
   `bash tools/r2_library_map.sh --upload`). Unfinished books get no `done` row.
   Check the book's block in the new `LIBRARY.md`: it must list every chapter, never "0 files".
   Verify the book's subject section in `BRG-teaching/Teaching` (`website/src/useLibrary.js` `SUBJECTS`: `Graphic statics`, `Form finding`, `Thrust networks & masonry`, `Materialization`, `Math`, `Computation`, `Structural design & history` — e.g. mathematics books belong in `Math`, never misclassified under `Computation`).
   Finally, trigger a GitHub Pages rebuild on `BRG-teaching/Teaching` (`git commit --allow-empty -m "Pages: rebuild <id>" && git push`)
   and verify the book, its subject chip, and the `Digital · Show original` figure toggle are live on `https://brg-teaching.github.io/Teaching/CAS/website/library.html`.
7. Record what is still missing or unreadable (pages, plates, sources) in the repo's
   `docs/books/books_missing_pages.md`: a short needs-only list; remove items once resolved and books once complete.

## Re-check a published book against the Mistral OCR

Use after translating (step 4) and for books already in R2. Do not reprocess or re-upload the whole book.
1. Download the book's current `*.md` and `src/` from R2; confirm `src/build.py` (or the shared one) rebuilds the
   published files byte for byte before editing anything.
2. Render the scan (`tools/pdf_render.py`), verify the printed-page offset on one page, OCR it (`tools/mistral_ocr.py`).
3. `tools/mistral_compare.py SRC OCR OFFSET OUT --jobs` → `MISMATCHES.md` and job files. Tune nothing by reading pages;
   if noise dominates, fix the normalisation in the script.
4. One Sonnet job per job file with `tools/CHECK_BRIEF.md` (≤ 12 pages, cropped zones only). Re-check every
   `OURS_WRONG`, `AUTHOR_MISPRINT`, `UNCLEAR` and every hedged `OK` on the scan yourself before editing;
   one Opus pass only for what stays unclear.
5. Fix `src/` (author misprints kept as printed with an "as printed" footnote), rebuild only the changed chapters,
   `tools/fix_anchors.py`, check that no new equation images are missing on R2, upload only the changed files to the
   same keys (delete nothing), and append a neutral note to the book's REVIEW log (or the README "Review status"):
   "Equations and numbers re-checked against a second OCR of the scan, <month year>" with the corrections listed.
   Text: `tools/mistral_textcheck.py SRC OCR OFFSET OUT --jobs` flags pages whose English length departs from the
   source (omissions, additions); check them with `tools/TEXT_CHECK_BRIEF.md` (Sonnet, ≤ 12 pages) and verify every
   OURS_WRONG against the source yourself before fixing.
6. Report per book: pages OCR'd, pages billed and cost, mismatches, fixes (page + what), unclear items, files uploaded.
   Delete local work files afterwards.

## Rescans and photographs

- Copy the originals to `RAW/rescans/<book>-<date>/`; identify the pages with `tools/photo_sheet.py`.
- Update only the affected cells/lines in `src/`, rewrite the footnotes ("read from a photograph of the
  printed page"), keep author misprints as printed, rebuild, append to the REVIEW log, upload the changed files.
- If a detail is hidden in the binding in every photo, say so and close the item instead of asking again.

## Finish

- Report output folder, completed chapters, review status, and remaining issues in short bullets.
- Default to local processing. Upload only if the user's invocation also requests
  publishing; use existing local R2 credentials and the upload helper, without exposing keys.
- Do not commit, push, delete originals, or replace existing published content unless requested.
  When updating published content, download the current R2 version first and change only what is needed.
- Published files never mention AI tools, models, or agents; review notes use neutral wording.
- This skill guides the host agent's local tools; MCP itself supplies read-only retrieval.
