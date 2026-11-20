"""Clean OCR Markdown of scanned books, and check a built book for text that makes no sense.

    python3 -I tools/ocr_clean.py clean OCR_DIR OUT_DIR [--heads "Chapter,Section,..."] [--no-math] [--kanji]
    python3 -I tools/ocr_clean.py check BOOK_DIR [--max 40]        # report suspicious lines, exit 1 if any

clean   rewrites every OCR_DIR/*.md into OUT_DIR, block by block (blank-line separated):
        - running heads and their misreadings ("Suction" for "Section", "T-Jeints"), matched fuzzily against --heads;
          a "# Heading" line is only dropped when it is a running head, never a real heading;
        - step / drawing labels (A1, B2, A+B, 2x, A×B, BC1 ...), bare page numbers, scanner stickers (ETH-...);
        - letter debris (lines of one or two letters left by coloured strips or page edges);
        - icon marks read as [16] or ∞, "[No text detected]", "[Non-Text]";
        - invented content on drawing-only or blank pages: empty tables (序号 ...), leaked layout JSON (box_2d);
          with --no-math also every formula (OCR invents "\\( \\therefore m = \\frac{3}{11} \\)" on drawing pages);
        - headings wrapped over two lines are joined;
        - with --kanji, look-alike Japanese characters (継 矧 蟻 枘) are corrected where the romanised reading in the same
          block confirms them.
        Real prose is never rewritten; only whole blocks or debris lines are removed.

check   scans BOOK_DIR/[0-9]*.md (published chapters) for the same kinds of nonsense plus very short fragment lines
        (cut-off words from a facing-page strip, e.g. "This no", "demar") and prints them with file:line. Run it before
        every upload; fix the cause in the builder, not by hand.

Library use from a book builder: `from ocr_clean import clean_text, check_lines`.
"""
import argparse, difflib, pathlib, re, sys

DEFAULT_HEADS = ["Chapter", "Section", "Contents", "Introduction", "Glossary", "Appendix", "Index"]
STEP = re.compile(r"^(?:\d{1,3}\s*[x×+]|[A-E]{1,3}\d{0,2}[*Å]?(?:\s*[+×x*v>\-]?\s*[A-E]{1,3}\d{0,2})*|[A-Z]?\d{1,3}"
                  r"|S\d{2}|\[Non-Text\]|\[No text detected\]|[①-⑳]+|•)$")
CJK = re.compile(r"[぀-ヿ㐀-鿿]")
MATH = re.compile(r"^\s*(\\\(|\\\[|\$)|\\frac|\\therefore")
LOOKALIKE = [("tsugi", "蹴縦繼總穎綫縫緻撞", "継"), ("hagi", "刚初別刈列剣殒翔刺刷", "矧"),
             ("ari", "蠟嬉矯蛾較蠕鱶嬢蟹", "蟻"), ("hozo", "柄枋杓朽枸", "枘")]


def near(s, names, r=0.72):
    s = re.sub(r"^[\d\s|]+|[\s\d|]+$", "", s).strip().lower()
    return bool(s) and len(s) <= 40 and any(difflib.SequenceMatcher(None, s, n.lower()).ratio() >= r for n in names)


def fix_kanji(text):
    for reading, bad, good in LOOKALIKE:
        if reading in text:
            text = re.sub(f"[{bad}]", good, text)
    return text


def blocks_of(t):
    out = []
    for b in re.split(r"\n\s*\n", t):
        lines = [l.rstrip() for l in b.strip().splitlines() if l.strip()]
        if lines and lines[0].startswith("#"):
            lines = [" ".join([lines[0]] + [l.strip() for l in lines[1:]])]
        if lines:
            out.append("\n".join(lines))
    return out


def keep_block(b, heads, no_math):
    s = b.strip()
    if s.startswith("![img-") or "序号" in s or "box_2d" in s:
        return False
    if no_math and MATH.search(s):
        return False
    if "\n" not in s:
        if STEP.match(s) or s.startswith(("ETH-", "ETH ")) or re.fullmatch(r"[A-Za-z:•]{1,2}", s):
            return False
        bare = s.lstrip("# ")
        if near(bare, heads, 0.72 if not s.startswith("#") else 0.92):
            return False
    return True


def clean_text(t, heads=DEFAULT_HEADS, no_math=False, kanji=False):
    out = []
    for b in blocks_of(t):
        if not keep_block(b, heads, no_math):
            continue
        b = "\n".join(l for l in b.splitlines() if not re.fullmatch(r"\s*[A-Za-z:•]{1,2}\s*", l))
        b = re.sub(r"\s*\[\d+\]", "", b).replace("(∞)", "").replace("∞", "")
        b = re.sub(r"[ \t]+", " ", b).strip()
        if kanji and CJK.search(b):
            b = fix_kanji(b)
        if b:
            out.append(b)
    return "\n\n".join(out) + "\n"


def check_lines(text):
    """Yield (line number, reason, line) for text that makes no sense in a published chapter."""
    for i, l in enumerate(text.splitlines(), 1):
        s = l.strip()
        if not s or s.startswith(("<", "|", "![", "*", "**", "- **", "#")) and not s.startswith("# "):
            if not s.startswith("#"):
                continue
        body = s.lstrip("#").strip()
        if MATH.search(s):
            yield i, "formula", s
        elif STEP.match(body):
            yield i, "label / page number", s
        elif re.fullmatch(r"[A-Za-z:]{1,2}\.?", body):
            yield i, "letter debris", s
        elif "box_2d" in s or "[No text" in s or "[Non-Text" in s or "序号" in s:
            yield i, "OCR artefact", s
        elif not s.startswith("#") and len(body) <= 12 and body[:1].islower() and " " in body:
            yield i, "fragment", s
        elif not s.startswith("#") and re.fullmatch(r"[a-z]{2,6}", body):
            yield i, "fragment", s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("clean"); c.add_argument("ocr"); c.add_argument("out")
    c.add_argument("--heads", default=""); c.add_argument("--no-math", action="store_true"); c.add_argument("--kanji", action="store_true")
    k = sub.add_parser("check"); k.add_argument("book"); k.add_argument("--max", type=int, default=40)
    a = ap.parse_args()
    if a.cmd == "clean":
        heads = DEFAULT_HEADS + [h.strip() for h in a.heads.split(",") if h.strip()]
        out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
        files = sorted(pathlib.Path(a.ocr).glob("*.md"))
        for f in files:
            (out / f.name).write_text(clean_text(f.read_text(encoding="utf-8"), heads, a.no_math, a.kanji), encoding="utf-8")
        print(f"cleaned {len(files)} pages -> {out}")
    else:
        n = 0
        for f in sorted(pathlib.Path(a.book).glob("[0-9]*.md")):
            for i, why, s in check_lines(f.read_text(encoding="utf-8")):
                n += 1
                if n <= a.max:
                    print(f"{f.name}:{i}: {why}: {s[:100]}")
        print(f"{n} suspicious lines")
        sys.exit(1 if n else 0)


if __name__ == "__main__":
    main()
