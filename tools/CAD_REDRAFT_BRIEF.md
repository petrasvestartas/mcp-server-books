# Parametric 2D & 3D CAD Figure Redrafting Brief (`tools/cad_engine.py`)

Every processed book in the BRG library MUST display **both** a crisp, mathematically exact **redrafted parametric SVG** (`figures/<stem>.svg`) AND an interactive toggle (`Digital · Show original`) back to the **original cropped book scan** (`figures/orig/<stem>.png`). Only photographic front covers (`cover.jpg`, `figures/cover-crop.png`) stay pure raster images.

## End-to-End Redrafting Workflow

1. **Preserve Original Cropped Scans First**:
   ```bash
   python3 -B -X utf8 tools/cad_redraft.py backup-orig <book_dir>
   ```
   Copies every non-cover `figures/<stem>.png` to `figures/orig/<stem>.png` without ever overwriting an existing original backup.

2. **Inspect Every Original Scan Image + Chapter Prose Before Coding**:
   - Open `figures/orig/<stem>.png` directly before authoring its CAD geometry, and read the corresponding section in `src/*.md`.
   - **Never draw from `FIGURES.md` descriptions alone**: always verify every curve, point letter, arrow, angle arc, right-angle symbol, hatch, and label against the actual scan image, and fix any inaccurate `FIGURES.md` or `alt="..."` description discovered during inspection.

3. **Author Parametric 2D/3D CAD SVGs (`tools/cad_engine.py`)**:
   - World coordinates `(x, y)` have **`y` pointing UP**; `scale` converts `1.0` world unit to SVG pixels (target width `260–680 px` matching chapter `<img width="...">` so `12–13.5 px` typography renders at 1:1 crispness).
   - Use exact analytic geometry (`intersect_lines_2d`, `line_circle_intersect`, `circle_circle_intersect`, `d.plot_func`, `d.fill_under_func`, `d.fill_between_funcs`, `d.hatch_polygon`, `d.right_angle`, `d.angle_arc`, `d.dim`, `IsoProj`, `d.box3d`).
   - Translate all non-English figure labels into idiomatic English matching `src/*.md`, use decimal points (`0.5` rather than `0,5`), italicize single-letter variables (`*x*`, `*y*`, `*P*_1`), and use `r"\vec{r}"`, `r"\bar{x}"`, `d.frac(...)` for vectors, overbars, and stacked fractions.
   - Omit redundant standalone bottom figure numbers (`Fig. 5`) when an image contains a single figure (the Markdown caption right underneath already carries `Fig. 5`); retain sub-figure labels (`Fig. 5` / `Fig. 6`, `(a)` / `(b)`, `n = 1 .. 5`) on multi-panel figures.
   - Never mention AI, LLMs, models, or agents in `<title>` or comments.

4. **Verify `0 issues`, Apply SVGs, Rebuild Chapters & Inspect Side-by-Side**:
   ```bash
   python3 -B -X utf8 tools/verify_cad_svg.py --png-dir <book_dir>/.checks/cad_png <book_dir>/figures/*.svg
   python3 -B -X utf8 tools/cad_redraft.py apply-svgs <book_dir>
   python3 -B -X utf8 <book_dir>/src/build.py
   python3 -B -X utf8 tools/cad_redraft.py compare-sheets <book_dir>
   python3 -B -X utf8 tools/cad_redraft.py check <book_dir>
   ```
   - `verify_cad_svg.py` enforces well-formed XML, zero `<tspan dy=...>` tags, zero `viewBox` label overflows, and zero text-text collisions.
   - Visually inspect the rendered PNGs / contact sheets against `figures/orig/<stem>.png` and refine any label overlapping a curve, line, or arrowhead before uploading.
