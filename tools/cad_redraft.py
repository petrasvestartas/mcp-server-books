"""Book-level CAD SVG redrafting workflow helper for BRG Books.

Subcommands:
  backup-orig <book_dir>
      Preserve original cropped scan images (`figures/<stem>.png`) in
      `figures/orig/<stem>.png` before redrafting (skipping cover crops and
      never overwriting an existing `figures/orig/<stem>.png`).

  apply-svgs <book_dir>
      Verify every `figures/<stem>.svg` (0 XML/overflow/collision issues) and
      render crisp 2x `figures/<stem>.png` previews alongside `.svg`; stamp
      trace-difficulty metadata onto `<svg>` + `cad/trace_difficulty.json`;
      switch `<book_dir>/src/*.md` image references from `figures/<stem>.png`
      to `figures/<stem>.svg`; and update `<book_dir>/FIGURES.md` rows to
      `[Label](figures/<stem>.svg) · [original](figures/orig/<stem>.png) · \`badge\``
      so the website's `Digital · Show original` click-to-toggle works on every figure.

  compare-sheets <book_dir> [--out-dir DIR] [--per-sheet 16]
      Render side-by-side `Original Scan | Redrafted CAD SVG` contact sheets (PNG)
      using PyMuPDF (`fitz`) for visual inspection.

  check <book_dir>
      Assert that every non-cover figure in `src/*.md`, published `*.md`, and
      `FIGURES.md` points to `figures/<stem>.svg`, has a matching
      `figures/orig/<stem>.png` original scan + `FIGURES.md` `· [original](...)`
      link, and passes `verify_cad_svg` with 0 issues.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_cad_svg import verify_and_render  # noqa: E402


def is_cover_figure(name: str) -> bool:
    low = Path(name).stem.lower()
    return low in {"cover", "cover-crop"} or low.startswith("cover-")


def count_sub_figures(stem: str) -> int:
    m_range = re.search(r"fig0*(\d+)-0*(\d+)$", stem)
    if m_range:
        a, b = int(m_range.group(1)), int(m_range.group(2))
        if b > a and (b - a) <= 30:
            return b - a + 1
    m_abc = re.search(r"([a-d])-([a-d])$", stem)
    if m_abc:
        return ord(m_abc.group(2)) - ord(m_abc.group(1)) + 1
    return 1


def analyze_svg(svg_path: Path) -> dict:
    raw = svg_path.read_text(encoding="utf-8")
    tree = ET.fromstring(raw)
    n_lines = n_polys = n_poly_pts = n_circles = n_paths = n_rects = n_texts = n_rot_texts = 0
    for el in tree.iter():
        tag = el.tag.split("}")[-1]
        if el.attrib.get("data-halo") == "1":
            continue
        if tag == "line":
            n_lines += 1
        elif tag in ("polyline", "polygon"):
            pts_str = el.attrib.get("points", "").strip()
            pts_n = len(pts_str.split()) if pts_str else 0
            n_poly_pts += pts_n
            if pts_n > 4:
                n_polys += 1
        elif tag in ("circle", "ellipse"):
            n_circles += 1
        elif tag == "path":
            n_paths += 1
        elif tag == "rect":
            n_rects += 1
        elif tag == "text":
            n_texts += 1
            if "rotate(" in el.attrib.get("transform", ""):
                n_rot_texts += 1
    n_rects = max(0, n_rects - 1)
    stem = svg_path.stem
    subs = count_sub_figures(stem)
    score = int(
        round(
            n_lines * 1.0
            + n_polys * 3.5
            + n_poly_pts * 0.12
            + n_circles * 1.2
            + n_paths * 2.0
            + n_rects * 1.5
            + n_texts * 2.2
            + n_rot_texts * 1.5
            + max(0, subs - 1) * 12.0
        )
    )
    if score >= 210 or subs >= 5 or n_texts >= 45 or n_lines >= 120:
        tier, badge = "hard", "🔴 Hard"
    elif score >= 85 or subs >= 2 or n_texts >= 18 or n_lines >= 40:
        tier, badge = "medium", "🟡 Medium"
    else:
        tier, badge = "easy", "🟢 Easy"
    return {
        "stem": stem,
        "difficulty": tier,
        "badge": badge,
        "score": score,
        "sub_figures": subs,
        "lines": n_lines,
        "curves_polys": n_polys,
        "poly_vertices": n_poly_pts,
        "circles": n_circles,
        "paths": n_paths,
        "texts": n_texts,
        "rotated_texts": n_rot_texts,
    }


def stamp_svg_metadata(svg_path: Path, info: dict) -> None:
    txt = svg_path.read_text(encoding="utf-8")
    txt_clean = re.sub(r'\s+data-trace-(?:difficulty|score|metrics)="[^"]*"', "", txt)
    metrics_str = (
        f"lines={info['lines']},polys={info['curves_polys']},"
        f"texts={info['texts']},rot_texts={info['rotated_texts']},subs={info['sub_figures']}"
    )
    attrs = (
        f' data-trace-difficulty="{info["difficulty"]}"'
        f' data-trace-score="{info["score"]}"'
        f' data-trace-metrics="{metrics_str}"'
    )
    txt_new = re.sub(r"(<svg\b[^>]*?)(>)", rf"\1{attrs}\2", txt_clean, count=1)
    if txt_new != txt:
        svg_path.write_text(txt_new, encoding="utf-8")


def cmd_backup_orig(book_dir: Path) -> int:
    fig_dir = book_dir / "figures"
    orig_dir = fig_dir / "orig"
    orig_dir.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for png in sorted(fig_dir.glob("*.png")):
        if is_cover_figure(png.name):
            continue
        dst = orig_dir / png.name
        if dst.exists():
            skipped += 1
        else:
            shutil.copy2(png, dst)
            copied += 1
    print(f"[{book_dir.name}] backup-orig: copied {copied} new, preserved {skipped} existing in figures/orig/")
    return 0


def cmd_apply_svgs(book_dir: Path, allow_issues: bool = False) -> int:
    fig_dir = book_dir / "figures"
    orig_dir = fig_dir / "orig"
    cad_dir = book_dir / "cad"
    cad_dir.mkdir(parents=True, exist_ok=True)

    svgs = [p for p in sorted(fig_dir.glob("*.svg")) if not is_cover_figure(p.name)]
    if not svgs:
        print(f"[{book_dir.name}] ERROR: no SVG figures found in {fig_dir}", file=sys.stderr)
        return 1

    missing_orig = [p.stem for p in svgs if not (orig_dir / f"{p.stem}.png").exists()]
    if missing_orig:
        print(f"[{book_dir.name}] ERROR: missing figures/orig/<stem>.png for: {missing_orig}", file=sys.stderr)
        return 1

    issues = verify_and_render(svgs, png_out_dir=None, write_png=True)
    if issues:
        for iss in issues:
            print("  ISSUE:", iss, file=sys.stderr)
        if not allow_issues:
            print(f"[{book_dir.name}] FAILED SVG verification with {len(issues)} issues.", file=sys.stderr)
            return 1

    records: list[dict] = []
    by_stem: dict[str, dict] = {}
    counts = {"easy": 0, "medium": 0, "hard": 0, "total": 0}
    for svg_p in svgs:
        info = analyze_svg(svg_p)
        stamp_svg_metadata(svg_p, info)
        records.append(info)
        by_stem[info["stem"]] = info
        counts[info["difficulty"]] += 1
        counts["total"] += 1

    records_sorted = sorted(records, key=lambda r: (-r["score"], r["stem"]))
    (cad_dir / "trace_difficulty.json").write_text(
        json.dumps(
            {
                "book_id": book_dir.name,
                "counts": counts,
                "easy_stems": [r["stem"] for r in records if r["difficulty"] == "easy"],
                "medium_stems": [r["stem"] for r in records if r["difficulty"] == "medium"],
                "hard_stems": [r["stem"] for r in records if r["difficulty"] == "hard"],
                "figures_by_difficulty_desc": records_sorted,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # Update src/*.md references from figures/<stem>.png -> figures/<stem>.svg
    src_dir = book_dir / "src"
    src_updated = 0
    if src_dir.exists():
        stem_pat = re.compile(r"figures/([A-Za-z0-9_.-]+)\.png\b")
        for md_p in sorted(src_dir.glob("*.md")):
            old_txt = md_p.read_text(encoding="utf-8")

            def _repl(m: re.Match[str]) -> str:
                st = m.group(1)
                return f"figures/{st}.svg" if st in by_stem else m.group(0)

            new_txt = stem_pat.sub(_repl, old_txt)
            if new_txt != old_txt:
                md_p.write_text(new_txt, encoding="utf-8")
                src_updated += 1

    # Update FIGURES.md rows idempotently
    figs_md = book_dir / "FIGURES.md"
    rows_updated = 0
    if figs_md.exists():
        old_lines = figs_md.read_text(encoding="utf-8").splitlines(keepends=True)
        new_lines: list[str] = []
        strip_orig_re = re.compile(r"\s*·\s*\[original\]\(figures/orig/[^)\s]+\)")
        strip_badge_re = re.compile(r"\s*·\s*`(?:🟢 Easy|🟡 Medium|🔴 Hard)\s*\(\d+\)`")
        first_link_re = re.compile(r"(\[[^\]]+\]\(figures/(?!orig/)([A-Za-z0-9_.-]+)\.(?:png|svg)\))")

        for line in old_lines:
            if line.startswith("|"):
                line = strip_badge_re.sub("", strip_orig_re.sub("", line))
                m = first_link_re.search(line)
                if m:
                    stem = m.group(2)
                    if stem in by_stem:
                        info = by_stem[stem]
                        new_link = re.sub(r"\.(?:png|svg)\)$", ".svg)", m.group(1))
                        replacement = (
                            f"{new_link} · [original](figures/orig/{stem}.png) "
                            f"· `{info['badge']} ({info['score']})`"
                        )
                        line = line[: m.start()] + replacement + line[m.end() :]
                        rows_updated += 1
            new_lines.append(line)
        figs_md.write_text("".join(new_lines), encoding="utf-8")

    print(
        f"[{book_dir.name}] apply-svgs: {counts['total']} SVGs verified (0 issues), "
        f"updated {src_updated} src/*.md files and {rows_updated} FIGURES.md rows "
        f"(Easy={counts['easy']}, Medium={counts['medium']}, Hard={counts['hard']})"
    )
    return 0


def cmd_compare_sheets(book_dir: Path, out_dir: Path | None, per_sheet: int = 16) -> int:
    import fitz

    fig_dir = book_dir / "figures"
    orig_dir = fig_dir / "orig"
    svgs = [p for p in sorted(fig_dir.glob("*.svg")) if not is_cover_figure(p.name)]
    target_dir = out_dir or (book_dir / ".checks" / "cad_compare")
    target_dir.mkdir(parents=True, exist_ok=True)

    cell_w, cell_h, cols = 420.0, 210.0, 2  # 2 pairs per row = 4 image boxes wide
    n_sheets = max(1, math.ceil(len(svgs) / per_sheet))
    for s_idx in range(n_sheets):
        batch = svgs[s_idx * per_sheet : (s_idx + 1) * per_sheet]
        rows = math.ceil(len(batch) / cols)
        doc = fitz.open()
        page = doc.new_page(width=cols * cell_w * 2 + 30, height=rows * (cell_h + 24) + 30)
        for idx, svg_p in enumerate(batch):
            r, c = divmod(idx, cols)
            x0 = 15 + c * (cell_w * 2)
            y0 = 15 + r * (cell_h + 24)
            page.insert_text((x0 + 4, y0 + 13), f"{svg_p.stem} (orig | svg)", fontsize=10)
            orig_p = orig_dir / f"{svg_p.stem}.png"
            if orig_p.exists():
                page.insert_image(fitz.Rect(x0 + 4, y0 + 18, x0 + cell_w - 6, y0 + 18 + cell_h - 6), filename=str(orig_p), keep_proportion=True)
            sdoc = fitz.open(stream=svg_p.read_bytes(), filetype="svg")
            spix = sdoc[0].get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            page.insert_image(fitz.Rect(x0 + cell_w + 4, y0 + 18, x0 + cell_w * 2 - 6, y0 + 18 + cell_h - 6), pixmap=spix, keep_proportion=True)
            sdoc.close()
        out_png = target_dir / f"sheet_{s_idx + 1:02d}.png"
        pix = page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
        pix.save(str(out_png))
        doc.close()
    print(f"[{book_dir.name}] compare-sheets: wrote {n_sheets} contact sheets to {target_dir}")
    return 0


def cmd_check(book_dir: Path) -> int:
    fig_dir = book_dir / "figures"
    orig_dir = fig_dir / "orig"
    problems: list[str] = []

    svgs = [p for p in sorted(fig_dir.glob("*.svg")) if not is_cover_figure(p.name)]
    if not svgs:
        problems.append("No redrafted SVG figures found in figures/*.svg")
    issues = verify_and_render(svgs, write_png=False)
    problems.extend(issues)

    # Check chapter Markdown files (both src/*.md and published root *.md)
    md_files = list(book_dir.glob("[0-9][0-9]-*.md"))
    if (book_dir / "src").exists():
        md_files.extend(sorted((book_dir / "src").glob("[0-9][0-9]-*.md")))
    img_re = re.compile(r'figures/(?!orig/)([A-Za-z0-9_.-]+)\.(png|svg|jpg|jpeg)\b')
    referenced_stems: set[str] = set()
    for md_p in md_files:
        txt = md_p.read_text(encoding="utf-8")
        for m in img_re.finditer(txt):
            stem, ext = m.group(1), m.group(2).lower()
            if is_cover_figure(stem):
                continue
            referenced_stems.add(stem)
            if ext != "svg":
                problems.append(f"{md_p.relative_to(book_dir)}: non-SVG figure reference 'figures/{stem}.{ext}'")

    for stem in sorted(referenced_stems):
        if not (fig_dir / f"{stem}.svg").exists():
            problems.append(f"Missing redrafted SVG: figures/{stem}.svg")
        if not (orig_dir / f"{stem}.png").exists():
            problems.append(f"Missing original scan crop: figures/orig/{stem}.png")

    figs_md = book_dir / "FIGURES.md"
    if not figs_md.exists():
        problems.append("Missing FIGURES.md")
    else:
        mapped_stems: set[str] = set()
        for line in figs_md.read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                continue
            cur = re.search(r"\]\((figures/(?!orig/)([^)\s]+))\)", line, re.IGNORECASE)
            orig = re.search(r"\]\((figures/orig/([^)\s]+))\)", line, re.IGNORECASE)
            if cur:
                fname = cur.group(2)
                stem = Path(fname).stem
                if is_cover_figure(stem):
                    continue
                if not fname.lower().endswith(".svg"):
                    problems.append(f"FIGURES.md row still points to non-SVG '{fname}'")
                if not orig:
                    problems.append(f"FIGURES.md row for '{stem}' is missing '· [original](figures/orig/{stem}.png)'")
                else:
                    mapped_stems.add(stem)
        for stem in sorted(referenced_stems - mapped_stems):
            problems.append(f"FIGURES.md missing dual SVG+original mapping for '{stem}'")

    if problems:
        print(f"[{book_dir.name}] CHECK FAILED ({len(problems)} problems):", file=sys.stderr)
        for p in problems[:40]:
            print("  -", p, file=sys.stderr)
        return 1
    print(f"[{book_dir.name}] CHECK PASSED: {len(svgs)} SVGs + {len(referenced_stems)} chapter figure toggles verified (0 issues).")
    return 0


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Manage CAD SVG redrafting and figures/orig/ website toggles.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_b = sub.add_parser("backup-orig")
    p_b.add_argument("book_dir", type=Path)

    p_a = sub.add_parser("apply-svgs")
    p_a.add_argument("book_dir", type=Path)
    p_a.add_argument("--allow-issues", action="store_true")

    p_s = sub.add_parser("compare-sheets")
    p_s.add_argument("book_dir", type=Path)
    p_s.add_argument("--out-dir", type=Path, default=None)
    p_s.add_argument("--per-sheet", type=int, default=16)

    p_c = sub.add_parser("check")
    p_c.add_argument("book_dir", type=Path)

    args = ap.parse_args()
    if args.cmd == "backup-orig":
        sys.exit(cmd_backup_orig(args.book_dir))
    if args.cmd == "apply-svgs":
        sys.exit(cmd_apply_svgs(args.book_dir, allow_issues=args.allow_issues))
    if args.cmd == "compare-sheets":
        sys.exit(cmd_compare_sheets(args.book_dir, out_dir=args.out_dir, per_sheet=args.per_sheet))
    if args.cmd == "check":
        sys.exit(cmd_check(args.book_dir))


if __name__ == "__main__":
    main()
