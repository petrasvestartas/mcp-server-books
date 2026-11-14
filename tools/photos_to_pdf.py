"""Pack a folder of page photographs into a compact, EXIF-upright PDF for Books/RAW/ and Cloudflare R2.

    python3 -I tools/photos_to_pdf.py PHOTO_DIR OUT_PDF [--max-side 1800] [--quality 75]
                                      [--greyscale] [--mapping CSV] [--pages-out DIR]

Why: raw phone/camera photographs of a 200-page book easily exceed 500–1000 MB, which wastes Cloudflare R2
storage and triggers paid overages. Downscaling the long side to ~1800 px at JPEG quality 75 (and --greyscale
for black-and-white books) keeps text, subscripts, and diagrams crisp while producing a ~10–30 MiB PDF matching
the rest of s3://brg-books/RAW/.

Options:
  PHOTO_DIR     folder of photographs (.jpg/.jpeg/.png), or folder of canonical pages when --mapping is given
  OUT_PDF       destination PDF path (e.g. Books/RAW/Author_Title_Year.pdf)
  --max-side    maximum pixel length of the longer image side embedded in the PDF (default: 1800)
  --quality     JPEG quality 1..95 inside the PDF (default: 75)
  --greyscale   convert pages to 8-bit greyscale in the PDF (ideal for monochrome text books; halves size)
  --mapping     optional scan_index.py CSV (header: image,kind,label) to embed images in exact CSV order
  --pages-out   optional directory to also save full-resolution EXIF-upright JPEGs for OCR and figure cropping

Exact byte-identical duplicate files (such as 'IMG_0001 (1).JPG' beside 'IMG_0001.JPG') are skipped automatically.
"""
import argparse
import csv
import hashlib
import io
import pathlib
import re
import sys

import pymupdf
from PIL import Image, ImageOps

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def natural_key(path: pathlib.Path):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", path.name)]


def collect_images(photo_dir: pathlib.Path, mapping_csv: str = "") -> list[pathlib.Path]:
    if mapping_csv:
        with open(mapping_csv, encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        seen, out = set(), []
        for r in rows:
            img = r["image"]
            if "/" in img or img in seen:
                continue
            seen.add(img)
            candidates = [photo_dir / f"{img}{ext}" for ext in (".jpg", ".jpeg", ".png", "")]
            found = next((p for p in candidates if p.is_file()), None)
            if not found:
                sys.exit(f"Missing image '{img}' in {photo_dir}")
            out.append(found)
        return out

    files = sorted((p for p in photo_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS), key=natural_key)
    # Prefer canonical names without ' (1)' before copy suffixes when deduplicating by SHA-256
    ordered = sorted(files, key=lambda p: (bool(re.search(r"\(\d+\)$", p.stem)), natural_key(p)))
    seen_hashes = set()
    keep = set()
    for p in ordered:
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        if h in seen_hashes:
            print(f"skip exact duplicate: {p.name}")
            continue
        seen_hashes.add(h)
        keep.add(p)
    return [p for p in files if p in keep]


def encode_page_jpeg(im: Image.Image, max_side: int, quality: int, greyscale: bool) -> tuple[bytes, int, int]:
    im = im.convert("L" if greyscale else "RGB")
    w, h = im.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        w, h = max(1, round(w * scale)), max(1, round(h * scale))
        im = im.resize((w, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    return buf.getvalue(), w, h


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo_dir", type=pathlib.Path)
    ap.add_argument("out_pdf", type=pathlib.Path)
    ap.add_argument("--max-side", type=int, default=1800)
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--greyscale", action="store_true")
    ap.add_argument("--mapping", default="")
    ap.add_argument("--pages-out", type=pathlib.Path, default=None)
    args = ap.parse_args()

    if not args.photo_dir.is_dir():
        sys.exit(f"Not a directory: {args.photo_dir}")

    images = collect_images(args.photo_dir, args.mapping)
    if not images:
        sys.exit(f"No images found in {args.photo_dir}")

    args.out_pdf.parent.mkdir(parents=True, exist_ok=True)
    if args.pages_out:
        args.pages_out.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open()
    for idx, src in enumerate(images, 1):
        with Image.open(src) as raw:
            upright = ImageOps.exif_transpose(raw).convert("RGB")
        if args.pages_out:
            dst_img = args.pages_out / f"p{idx:04d}.jpg"
            if not dst_img.exists():
                upright.save(dst_img, format="JPEG", quality=92, optimize=True)
        jpg_bytes, w, h = encode_page_jpeg(upright, args.max_side, args.quality, args.greyscale)
        # 150 dpi physical page box so PDF viewers open at comfortable book dimensions
        pt_w, pt_h = w * 72.0 / 150.0, h * 72.0 / 150.0
        page = doc.new_page(width=pt_w, height=pt_h)
        page.insert_image(pymupdf.Rect(0, 0, pt_w, pt_h), stream=jpg_bytes)

    doc.save(args.out_pdf, garbage=4, deflate=True)
    doc.close()
    mb = args.out_pdf.stat().st_size / (1024 * 1024)
    print(f"wrote {args.out_pdf} ({len(images)} pages, {mb:.2f} MiB)")


if __name__ == "__main__":
    main()
