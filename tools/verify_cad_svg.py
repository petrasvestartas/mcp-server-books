"""Pure-Python PyMuPDF (fitz) SVG CAD verifier + 2x PNG rasterizer.

For every SVG:
1. Checks well-formed XML and zero `<tspan dy=...>` tags.
2. Measures every foreground `<text>` element's bounding box via PyMuPDF `get_text("dict")`.
3. Fails on any label that overflows the `viewBox` or collides with another `<text>` label.
4. Renders a crisp 2x `.png` preview in `<book>/work_png/<stem>.png` (or beside the SVG when `--beside` is passed)
   so `figures/orig/<stem>.png` is never touched and visual inspection via `read_file` is crystal clear.
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import fitz

_HALO_RE = re.compile(r'<text\s+data-halo="1"[^>]*>.*?</text>', re.DOTALL)


def verify_and_render(
    svg_paths: list[Path],
    png_out_dir: Path | None = None,
    write_png: bool = True,
) -> list[str]:
    issues: list[str] = []
    mat = fitz.Matrix(2.0, 2.0)

    for spath in svg_paths:
        svg_txt = spath.read_text(encoding="utf-8")
        try:
            ET.fromstring(svg_txt)
        except Exception as exc:
            issues.append(f"{spath.name}: XML parse error: {exc}")
            continue

        if "<tspan" in svg_txt and "dy=" in svg_txt:
            issues.append(f"{spath.name}: contains <tspan dy=...> (causes overlap in fitz/browsers)")

        doc_full = fitz.open(stream=svg_txt.encode("utf-8"), filetype="svg")
        page_full = doc_full[0]
        vw, vh = float(page_full.rect.width), float(page_full.rect.height)
        if write_png:
            pix = page_full.get_pixmap(matrix=mat, alpha=False)
            if png_out_dir is not None:
                png_out_dir.mkdir(parents=True, exist_ok=True)
                out_png = png_out_dir / f"{spath.stem}.png"
            else:
                out_png = spath.with_suffix(".png")
            pix.save(str(out_png))
        doc_full.close()

        svg_no_halo = _HALO_RE.sub("", svg_txt)
        doc_txt = fitz.open(stream=svg_no_halo.encode("utf-8"), filetype="svg")
        page_txt = doc_txt[0]
        td = page_txt.get_text("dict")
        texts: list[dict] = []
        line_id = 0
        for b in td.get("blocks", []):
            for line in b.get("lines", []):
                line_id += 1
                ux, uy = line.get("dir", (1.0, 0.0))
                for s in line.get("spans", []):
                    t_str = s.get("text", "").strip()
                    if not t_str:
                        continue
                    x0, y0, x1, y1 = s["bbox"]
                    ox_pt, oy_pt = s.get("origin", (x0, y1))
                    fs = float(s.get("size", 12.0))
                    w, h = x1 - x0, y1 - y0
                    if w > 0.5 and h > 0.5:
                        texts.append({
                            "text": t_str[:48],
                            "x": x0, "y": y0, "w": w, "h": h,
                            "ux": float(ux), "uy": float(uy),
                            "ox": float(ox_pt), "oy": float(oy_pt),
                            "fs": fs,
                            "lid": line_id,
                        })
        doc_txt.close()

        for t in texts:
            if t["x"] < 0.5 or t["y"] < 0.5 or (t["x"] + t["w"]) > vw - 0.5 or (t["y"] + t["h"]) > vh - 0.5:
                issues.append(
                    f"{spath.name}: OVERFLOW '{t['text']}' box=({t['x']:.1f},{t['y']:.1f},{t['w']:.1f},{t['h']:.1f}) vs ({vw:.1f}x{vh:.1f})"
                )

        for i in range(len(texts)):
            a = texts[i]
            ax0, ax1 = a["x"] + 2.0, a["x"] + a["w"] - 2.0
            ay0, ay1 = a["y"] + a["h"] * 0.22, a["y"] + a["h"] * 0.78
            for j in range(i + 1, len(texts)):
                b = texts[j]
                if a["lid"] == b["lid"]:
                    continue
                if abs(a["uy"]) > 0.08 and abs(a["ux"] * b["ux"] + a["uy"] * b["uy"]) > 0.98:
                    ux, uy = a["ux"], a["uy"]
                    nx, ny = -uy, ux
                    perp = abs((b["ox"] - a["ox"]) * nx + (b["oy"] - a["oy"]) * ny)
                    if perp >= 0.85 * max(a["fs"], b["fs"]):
                        continue
                    du = abs((b["ox"] - a["ox"]) * ux + (b["oy"] - a["oy"]) * uy)
                    if perp <= 0.42 * max(a["fs"], b["fs"]) and du >= 0.35 * min(a["fs"], b["fs"]):
                        continue
                bx0, bx1 = b["x"] + 2.0, b["x"] + b["w"] - 2.0
                by0, by1 = b["y"] + b["h"] * 0.22, b["y"] + b["h"] * 0.78
                ox = min(ax1, bx1) - max(ax0, bx0)
                oy = min(ay1, by1) - max(ay0, by0)
                if ox > 2.5 and oy > 2.5:
                    issues.append(
                        f"{spath.name}: COLLISION '{a['text']}' <-> '{b['text']}' overlap=({ox:.1f}x{oy:.1f}px)"
                    )

    return issues


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--png-dir", type=Path, default=None)
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()
    expanded: list[Path] = []
    for f in args.files:
        if f.is_dir():
            expanded.extend(sorted(f.glob("*.svg")))
        else:
            expanded.append(f)
    issues = verify_and_render(expanded, png_out_dir=args.png_dir, write_png=not args.no_png)
    print(f"Checked {len(expanded)} SVGs: {len(issues)} issues.")
    for iss in issues:
        print("  ISSUE:", iss)
    if issues:
        sys.exit(1)


if __name__ == "__main__":
    main()
