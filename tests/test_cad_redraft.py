from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = REPO_ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from cad_engine import CadDrawing, IsoProj, PAL  # noqa: E402
from verify_cad_svg import verify_and_render  # noqa: E402


def test_cad_redraft_end_to_end(tmp_path: Path):
    book = tmp_path / "sample-math-book"
    (book / "figures").mkdir(parents=True)
    (book / "src").mkdir(parents=True)

    # Create dummy original PNGs (cover-crop.png + txt-fig001.png) using fitz via CadDrawing
    d_orig = CadDrawing("orig_seed", scale=60.0, title="Seed scan")
    d_orig.circle((0.0, 0.0), 1.0)
    seed_svg = tmp_path / "seed.svg"
    seed_svg.write_text(d_orig.to_svg(), encoding="utf-8")
    verify_and_render([seed_svg], png_out_dir=tmp_path, write_png=True)
    seed_png_bytes = (tmp_path / "seed.png").read_bytes()

    (book / "figures" / "cover-crop.png").write_bytes(seed_png_bytes)
    (book / "figures" / "txt-fig001.png").write_bytes(seed_png_bytes)
    (book / "src" / "01-chapter.md").write_text(
        '# Chapter 1\n\n<img src="figures/cover-crop.png" alt="Cover">\n'
        '<p align="center"><img src="figures/txt-fig001.png" alt="Fig. 1" width="320"></p>\n',
        encoding="utf-8",
    )
    (book / "FIGURES.md").write_text(
        "# Figures\n\n| Figure | Source | Chapter | Description |\n|---|---|---|---|\n"
        "| [Front cover](figures/cover-crop.png) | cover | 00 | Cover |\n"
        "| [Fig. 1](figures/txt-fig001.png) | p. 5 | 01 | Unit circle and vector |\n",
        encoding="utf-8",
    )

    # 1. Backup originals
    res = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(TOOLS_DIR / "cad_redraft.py"), "backup-orig", str(book)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "copied 1 new" in res.stdout
    assert (book / "figures" / "orig" / "txt-fig001.png").exists()
    assert not (book / "figures" / "orig" / "cover-crop.png").exists()

    # 2. Author a redrafted 2D/3D math CAD SVG
    d = CadDrawing("txt-fig001", scale=70.0, title="Fig. 1 — Unit circle and vector")
    d.axes((-1.4, 1.6), (-1.4, 1.6), x_ticks=[(1.0, "1")], y_ticks=[(1.0, "1")])
    d.circle((0.0, 0.0), 1.0, style="blue", fill=PAL["blue_fill"], fill_opacity=0.25)
    d.arrow((0.0, 0.0), (0.8, 0.6), style="crimson")
    d.label((0.45, 0.42), r"\vec{r}_0", dx_px=-14.0, dy_px=-8.0, color=PAL["crimson"])
    d.frac((-0.9, 1.15), "*dy*", "*dx*", size=11.5, color=PAL["blue"])
    proj = IsoProj.cavalier(ox=2.2, oy=-0.4, scale=0.7)
    d.box3d(proj, 0.0, 0.0, 0.0, 1.0, 0.8, 1.0, style="blue")
    d.save(book)

    # 3. Apply SVGs, simulate chapter build, and run check
    subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(TOOLS_DIR / "cad_redraft.py"), "apply-svgs", str(book)],
        check=True,
    )
    src_txt = (book / "src" / "01-chapter.md").read_text(encoding="utf-8")
    assert 'figures/cover-crop.png' in src_txt
    assert 'figures/txt-fig001.svg' in src_txt
    (book / "01-chapter.md").write_text(src_txt, encoding="utf-8")

    figs_txt = (book / "FIGURES.md").read_text(encoding="utf-8")
    assert "[Fig. 1](figures/txt-fig001.svg) · [original](figures/orig/txt-fig001.png)" in figs_txt
    assert "data-trace-difficulty=" in (book / "figures" / "txt-fig001.svg").read_text(encoding="utf-8")
    assert (book / "cad" / "trace_difficulty.json").exists()

    subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(TOOLS_DIR / "cad_redraft.py"), "check", str(book)],
        check=True,
    )


def test_workflow_docs_include_svg_redraft_and_math_section_rules():
    wf = (REPO_ROOT / "src" / "books_mcp" / "books" / "01_workflow.md").read_text(encoding="utf-8")
    wb = (REPO_ROOT / "src" / "books_mcp" / "books" / "04_website.md").read_text(encoding="utf-8")
    sk = (REPO_ROOT / ".claude" / "skills" / "books-process" / "SKILL.md").read_text(encoding="utf-8")
    assert "cad_redraft.py" in wf and "figures/orig/" in wf
    assert "Math" in wb and "figures/orig/" in wb
    assert "cad_redraft.py" in sk
