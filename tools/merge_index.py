"""Merge per-group index JSON (see tools/INDEX_BRIEF.md) into a book's INDEX.md, GLOSSARY.md, FIGURES.md,
and write each figure's description into the alt text of its <img> tags in src/*.md (so search and grep find it).

    python3 tools/merge_index.py <book-folder> <parts-dir>
"""
import json, pathlib, re, sys

book = pathlib.Path(sys.argv[1]).resolve()
parts = sorted(pathlib.Path(sys.argv[2]).glob("*.json"))
data = {"chapters": [], "symbols": [], "terms": [], "figures": []}
for p in parts:
    d = json.loads(p.read_text(encoding="utf-8"))
    for k in data:
        data[k] += d.get(k, [])

order = [l.split("](")[1].split(")")[0] for l in (book / "README.md").read_text(encoding="utf-8").splitlines()
         if "✅ [" in l and "](" in l]
rank = {f: i for i, f in enumerate(dict.fromkeys(o.split("#")[0] for o in order))}
chap = sorted(data["chapters"], key=lambda c: rank.get(c["file"], 999))
title = (book / "README.md").read_text(encoding="utf-8").splitlines()
esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")

# INDEX.md
out = ["# Index — chapter summaries", "",
       "One paragraph per chapter or note, to find the right file without reading it. "
       "See also [GLOSSARY.md](GLOSSARY.md) (notation and terms) and [FIGURES.md](FIGURES.md).", ""]
for c in chap:
    out += [f"## [{c['title']}]({c['file']})", f"<sub>pp. {c['pages']} · {c['sections']}</sub>", "", c["summary"], ""]
(book / "INDEX.md").write_text("\n".join(out), encoding="utf-8")

# GLOSSARY.md
seen, syms = set(), []
for s in data["symbols"]:
    key = (s["symbol"], s["meaning"].lower()[:40])
    if key not in seen:
        seen.add(key); syms.append(s)
lang = "German" if any("german" in t for t in data["terms"]) else ("Italian" if any("italian" in t for t in data["terms"]) else "French")
orig_of = lambda t: t.get("source") or t.get("german") or t.get("italian") or t.get("french", "")
seen, terms = set(), []
for t in sorted(data["terms"], key=lambda t: orig_of(t).lower()):
    if orig_of(t).lower() not in seen:
        seen.add(orig_of(t).lower()); terms.append(t)
out = ["# Glossary — notation and terminology", "",
       "The author's own symbols (with clashes against modern usage) and technical terms. "
       "Check here before comparing this book with another author.", "",
       "## Symbols", "", "| Symbol | Meaning in this book | Where | Notes |", "|---|---|---|---|"]
out += [f"| {esc(s['symbol'])} | {esc(s['meaning'])} | {esc(s.get('where',''))} | {esc(s.get('notes',''))} |" for s in syms]
out += ["", "## Terms", "", f"| Original ({lang}) | Translation | Modern term | Where |", "|---|---|---|---|"]
out += [f"| {esc(orig_of(t))} | {esc(t['english'])} | {esc(t.get('modern',''))} | {esc(t.get('where',''))} |" for t in terms]
(book / "GLOSSARY.md").write_text("\n".join(out) + "\n", encoding="utf-8")

# FIGURES.md
figs = sorted(data["figures"], key=lambda f: (rank.get(f["chapter"], 999), f["file"]))
out = ["# Figures", "",
       f"All {len(figs)} figure images, with what each shows. Plate figures and figures printed in the text are "
       "numbered separately by the author. Open the image only when it is relevant.", "",
       "| Figure | Source | Chapter · § | Description |", "|---|---|---|---|"]
for f in figs:
    out.append(f"| [{esc(f['label'])}](figures/{f['file']}) | {esc(f.get('source',''))} | "
               f"[{f['chapter'].removesuffix('.md')}]({f['chapter']}) · {esc(f.get('section',''))} | {esc(f['description'])} |")
(book / "FIGURES.md").write_text("\n".join(out) + "\n", encoding="utf-8")

# alt text in sources
desc = {f["file"]: f["description"] for f in figs}
changed = 0
for src in (book / "src").glob("*.md"):
    t = src.read_text(encoding="utf-8")
    def alt(m):
        name = m.group(1)
        d = desc.get(name)
        if not d:
            return m.group(0)
        lab = re.sub(r" — .*", "", m.group(3))
        return f'{m.group(0).split("alt=")[0]}alt="{lab} — {d.replace(chr(34), chr(39))}"'
    t2 = re.sub(r'src="figures/([^"]+)"([^>]*?)alt="([^"]*)"', alt, t)
    if t2 != t:
        src.write_text(t2, encoding="utf-8"); changed += 1
missing = sorted({m for s in (book / "src").glob("*.md") for m in re.findall(r'figures/([^"]+\.(?:png|svg|jpg))', s.read_text(encoding="utf-8"))} - set(desc))
print(f"chapters {len(chap)}, symbols {len(syms)}, terms {len(terms)}, figures {len(figs)}; "
      f"alt text updated in {changed} files; figures without description: {missing}")
