# mcp-server-books

MCP for scanned books (built on **FastMCP v4**, `fastmcp>=4.2.0,<5`). Read library. Process scans or photo folders. OCR (Mistral). Translate. Upload compact PDFs + books to Cloudflare R2. Show on Teaching website (`https://brg-teaching.github.io/Teaching/CAS/website/library.html`).

Server reads only. Processing done by your agent (Claude Code / MCP client) with `tools/`.

## Install

    git clone https://github.com/petrasvestartas/mcp-server-books.git
    cd mcp-server-books
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv sync --extra tools --extra dev
    uv run pytest

## Run

    uv run books-mcp                 # stdio, waits for chatbot

## Add to Claude Code

    claude mcp add books -- uv --directory $PWD run books-mcp

Skill (slash `/books-process`) ships in `.claude/skills/`. Open Claude Code in this repo, it is there. Elsewhere:

    mkdir -p ~/.claude/skills && cp -r .claude/skills/books-process ~/.claude/skills/

Use:

    /books-process ~/Books/RAW/Author_Title_1890.pdf
    mcp_books                        # list commands
    mcp_books_workflow               # full workflow

## System tools

    sudo apt install awscli poppler-utils     # mac: brew install awscli poppler

## Mistral OCR (required for book OCR)

Always use our Mistral account key (`~/.config/mistral/api_key`) for OCR — about $0.001 per page, returning Markdown + LaTeX formulas and caching per page so reruns cost nothing. Key from https://console.mistral.ai:

    mkdir -p ~/.config/mistral
    echo '<key>' > ~/.config/mistral/api_key
    chmod 600 ~/.config/mistral/api_key

Test:

    python3 -I tools/pdf_render.py scan.pdf pages/ 1 2
    python3 -I tools/mistral_ocr.py ocr/ pages/p0001.jpg

## Camera / phone photo folders -> compact PDF

When a book arrives as a folder of camera or phone photographs instead of a PDF, pack it into a compact EXIF-upright PDF (~10–30 MiB, never raw 500+ MiB photo dumps that trigger R2 storage fees) before uploading to `s3://brg-books/RAW/`:

    python3 -I tools/photos_to_pdf.py /path/to/photos Books/RAW/Author_Title_Year.pdf --greyscale      # monochrome text book
    python3 -I tools/photos_to_pdf.py /path/to/photos Books/RAW/Author_Title_Year.pdf --max-side 1800  # colour diagrams

## Cloudflare R2

Cloudflare dashboard, R2, your bucket, Manage API tokens, create token "Object Read & Write" for this bucket.
Gives key id (32 hex) and secret (64 hex). Endpoint: `https://<account id>.r2.cloudflarestorage.com`.

    aws configure --profile r2-books          # key id, secret, region: auto, output: json
    E=https://<account id>.r2.cloudflarestorage.com
    aws --profile r2-books --region auto --endpoint-url $E s3 ls s3://brg-books/

`SignatureDoesNotMatch` = secret pasted wrong.

Upload (preview first, never deletes):

    bash tools/upload-books.sh brg-books $E out/<book>
    bash tools/upload-books.sh brg-books $E out/<book> --upload

Public read URL (default of server, change with `BOOKS_URL`):

    https://pub-c082064d3c234b25bcb6abd4240e637c.r2.dev/LIBRARY.md

## Teaching website

Website reads R2. Book visible only when `done` in R2 `PROCESSED.md`.

Need push access to the website repo:

    git clone git@github.com:BRG-teaching/Teaching.git ~/brg/code_teaching/Teaching

After book upload (and uploading the compact PDF to `s3://brg-books/RAW/`):

    # 1. Download current R2 PROCESSED.md first, add "| `<book>/` | YYYY-MM-DD | done |", then upload:
    aws --profile r2-books --region auto --endpoint-url $E s3 cp s3://brg-books/PROCESSED.md PROCESSED.md
    # (edit PROCESSED.md to add the new done row)
    aws --profile r2-books --region auto --endpoint-url $E s3 cp PROCESSED.md s3://brg-books/PROCESSED.md
    # 2. Rebuild and upload LIBRARY.md (verify chapter count > 0, never "0 files"):
    python3 -I tools/r2_library_map.py --upload          # or: bash tools/r2_library_map.sh --upload
    # 3. Trigger Teaching GitHub Pages rebuild so the book appears at:
    #    https://brg-teaching.github.io/Teaching/CAS/website/library.html
    cd ~/brg/code_teaching/Teaching && git commit --allow-empty -m "Pages: rebuild <book>" && git push

## Workflow short

    Books/RAW/<scan>.pdf  (or photo folder -> tools/photos_to_pdf.py -> compact PDF in Books/RAW/)
      -> tools/pdf_render.py, tools/scan_split.py     pages
      -> tools/mistral_ocr.py                          Mistral OCR markdown + LaTeX (~$0.001/page)
      -> agent + tools/TRANSLATE_BRIEF.md              English chapters (built with tools/templates/build.py)
      -> agent + tools/PROOF_BRIEF.md                  proofread
      -> tools/mistral_compare.py, mistral_textcheck.py  re-check
      -> tools/figcrop.py, structlabels.py             figures
      -> tools/fix_anchors.py, merge_index.py          INDEX, anchors
      -> tools/upload-books.sh --upload + RAW PDF      Cloudflare R2
      -> PROCESSED.md + r2_library_map.py --upload + Teaching push   live on library.html

Full rules: `src/books_mcp/books/01_workflow.md`, `02_guide.md`.

## Rules

- All text English. Original title beside.
- Published files: no AI, model, agent words.
- Third party copyright: process local, ask before upload. Private books in `Books/private/`.
- Scans to R2 `RAW/`. Page markers link scan page.
- Upload never deletes. Download R2 version before edit.

## Layout

    src/books_mcp/server.py       FastMCP: command, prompts, library tools
    src/books_mcp/library.py      read LIBRARY.md from R2
    src/books_mcp/books/*.md      one page = one command (mcp_books_<page>)
    tools/                        OCR, split, figures, upload, briefs
    .claude/skills/books-process  skill
    missing_pages.md              pages still to rescan
