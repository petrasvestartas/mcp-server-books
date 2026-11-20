"""Turn a scan of open-book spreads into straightened, aligned spread images cropped to the paper.

    python3 -I tools/spread_crop.py PDF OUTDIR [--dpi 150] [--first N] [--last N] [--rotate 0|90|-90|180]
                                     [--max-skew 2.0] [--no-deskew] [--jobs 8]

Default for books whose content runs across facing pages (catalogues, plates, joint spreads, atlases):
keep the two facing pages together as one image instead of cutting them at the gutter.

For every PDF page (= one spread):
  1. render at --dpi, optional --rotate;
  2. straighten: the skew is the angle (within ±--max-skew degrees) that makes the horizontal ink profile sharpest
     (text lines, rules and page edges become level); rotation fills with white;
  3. crop to the paper: rows that are mostly paper, then clean white columns (fore-edge page stack, dark scanner
     bed and hands are left out; the gutter shadow is bridged), then rows again inside those columns;
  4. align: crops whose size is far from the book's median (text-only pages, full-colour divider pages, blank
     leaves) take the median paper box instead, so every spread has the same frame; a small inset removes the
     last dark edge.
Writes OUTDIR/sNNN.jpg (NNN = PDF page) and OUTDIR/spreads.csv (page, skew, box, fallback). Spreads already
written are skipped, so a run can be resumed. Needs pdftoppm (poppler), Pillow, numpy.

Use the spreads for figures (one image per spread, e.g. figures/ppLLLL-RRRR.png) and for SCANS.md
(tools/scan_index.py with the spread images; one image may serve two printed pages). Split into single pages only
for OCR (tools/scan_split.py), never for the published figures.
"""
import argparse, csv, pathlib, subprocess, sys, tempfile
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from PIL import Image


def longest_run(mask, gap):
    """Longest run of True, bridging False gaps shorter than `gap`."""
    m = np.asarray(mask, bool).copy(); n = len(m); i = 0
    while i < n:
        if not m[i]:
            j = i
            while j < n and not m[j]:
                j += 1
            if 0 < i and j < n and j - i < gap:
                m[i:j] = True
            i = j
        else:
            i += 1
    best, start = (0, 0), None
    for i, v in enumerate(list(m) + [False]):
        if v and start is None:
            start = i
        if not v and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best


def paper_box(im, s=4):
    """Box (x0, y0, x1, y1) of the paper of both facing pages."""
    g = np.asarray(im.convert("L").resize((max(1, im.width // s), max(1, im.height // s)))).astype(float)
    H, W = g.shape
    r0, r1 = longest_run(np.median(g, 1) > 170, max(2, H // 50))
    core = g[r0 + (r1 - r0) // 6: max(r0 + (r1 - r0) // 6 + 1, r1 - (r1 - r0) // 6)]
    c0, c1 = longest_run(np.percentile(core, 20, axis=0) > 215, max(2, W // 25))
    r0, r1 = longest_run(np.percentile(g[:, c0:c1], 20, axis=1) > 200, max(2, H // 50))
    return (c0 * s, r0 * s, c1 * s, r1 * s)


def skew_angle(im, max_skew=2.0, min_gain=0.10):
    """Angle in degrees that levels the page: maximises the sharpness of the row profile of the ink.
    Returns 0 unless levelling sharpens the profile by at least `min_gain` (blank or full-colour pages stay as they are)."""
    g = im.convert("L")
    g.thumbnail((900, 900))
    a = np.asarray(g).astype(float)
    ink = Image.fromarray(((a < 140) * 255).astype("uint8"))
    if np.asarray(ink).mean() < 1 or np.asarray(ink).mean() > 128:
        return 0.0
    def score(t):
        p = np.asarray(ink.rotate(t, resample=Image.BILINEAR, fillcolor=0)).sum(1).astype(float)
        return np.square(np.diff(p)).sum()
    steps = np.arange(-max_skew, max_skew + 1e-9, 0.25)
    best = max(steps, key=score)
    fine = max(np.clip(np.arange(best - 0.25, best + 0.25 + 1e-9, 0.05), -max_skew, max_skew), key=score)
    return round(float(fine), 2) if score(fine) > (1 + min_gain) * score(0.0) else 0.0


def render(pdf, page, dpi, rot, tmpdir):
    base = pathlib.Path(tmpdir) / f"r{page:04d}"
    if not pathlib.Path(f"{base}.jpg").exists():
        subprocess.run(["pdftoppm", "-r", str(dpi), "-jpeg", "-singlefile", "-f", str(page), "-l", str(page), pdf, str(base)],
                       check=True)
    im = Image.open(f"{base}.jpg").convert("RGB")
    return im.rotate(rot, expand=True) if rot else im


def first_pass(job):
    """Paper box of the spread as scanned."""
    pdf, page, dpi, rot, tmpdir = job
    return page, paper_box(render(pdf, page, dpi, rot, tmpdir))


def second_pass(job):
    """Straighten inside a trusted box, crop to the common frame, save."""
    pdf, page, dpi, rot, tmpdir, box, med_box, W, H, max_skew, deskew, out = job
    im = render(pdf, page, dpi, rot, tmpdir)
    fallback = not (abs(box[2] - box[0] - W) < 0.03 * W and abs(box[3] - box[1] - H) < 0.03 * H)
    region = med_box if fallback else box
    t = skew_angle(im.crop(region), max_skew) if deskew else 0.0
    if t:
        cx, cy = (region[0] + region[2]) / 2, (region[1] + region[3]) / 2
        im = im.rotate(t, resample=Image.BICUBIC, center=(cx, cy), fillcolor=(255, 255, 255))
        if not fallback:
            nb = paper_box(im)
            if abs(nb[2] - nb[0] - W) < 0.03 * W and abs(nb[3] - nb[1] - H) < 0.03 * H:
                region = nb
    cx, cy = (region[0] + region[2]) // 2, (region[1] + region[3]) // 2
    x0, x1, y0, y1 = cx - W // 2, cx + W // 2, cy - H // 2, cy + H // 2
    dx, dy = W // 200, H // 200
    im.crop((x0 + dx, y0 + dy, x1 - dx, y1 - dy)).save(pathlib.Path(out) / f"s{page:03d}.jpg", quality=88)
    return page, t, (x0, y0, x1, y1), int(fallback)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf"); ap.add_argument("outdir")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--first", type=int, default=1); ap.add_argument("--last", type=int, default=0)
    ap.add_argument("--rotate", type=int, default=0)
    ap.add_argument("--max-skew", type=float, default=2.0)
    ap.add_argument("--no-deskew", action="store_true")
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    out = pathlib.Path(a.outdir); out.mkdir(parents=True, exist_ok=True)
    n = int(next(l.split()[-1] for l in subprocess.run(["pdfinfo", a.pdf], capture_output=True, text=True).stdout.splitlines()
                 if l.startswith("Pages:")))
    pages = [p for p in range(a.first, (a.last or n) + 1) if not (out / f"s{p:03d}.jpg").exists()]
    if not pages:
        sys.exit("all spreads already written")
    with tempfile.TemporaryDirectory() as tmp:
        with ProcessPoolExecutor(a.jobs) as ex:
            boxes = dict(ex.map(first_pass, [(a.pdf, p, a.dpi, a.rotate, tmp) for p in pages]))
        sizes = np.array([(b[2] - b[0], b[3] - b[1]) for b in boxes.values()])
        med_w, med_h = np.median(sizes, 0)
        good = [b for b in boxes.values() if abs(b[2] - b[0] - med_w) < 0.03 * med_w and abs(b[3] - b[1] - med_h) < 0.03 * med_h]
        med_box = tuple(int(v) for v in np.median(np.array(good or list(boxes.values())), 0))
        W, H = med_box[2] - med_box[0], med_box[3] - med_box[1]
        with ProcessPoolExecutor(a.jobs) as ex:
            rows = list(ex.map(second_pass, [(a.pdf, p, a.dpi, a.rotate, tmp, boxes[p], med_box, W, H, a.max_skew,
                                               not a.no_deskew, str(out)) for p in pages]))
    with open(out / "spreads.csv", "a", newline="") as f:
        w = csv.writer(f)
        if f.tell() == 0:
            w.writerow(["pdf_page", "skew_deg", "x0", "y0", "x1", "y1", "median_box"])
        for page, t, b, fb in rows:
            w.writerow([page, t, *b, fb])
    print(f"{len(rows)} spreads -> {out} · frame {W}×{H} px · median box used for {sum(r[3] for r in rows)} · "
          f"skew range {min(r[1] for r in rows)}..{max(r[1] for r in rows)}°")


if __name__ == "__main__":
    main()
