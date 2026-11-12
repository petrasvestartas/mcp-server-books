# mcp-server-books

MCP for scanned books. Read library. Process scans. OCR (Mistral). Translate. Upload Cloudflare R2. Show on Teaching website.

Server reads only. Processing done by your agent (Claude Code) with `tools/`.

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

## Mistral OCR

Key from https://console.mistral.ai, about $0.001 per page.

    mkdir -p ~/.config/mistral
    echo '<key>' > ~/.config/mistral/api_key
    chmod 600 ~/.config/mistral/api_key

Test:

    python3 -I tools/pdf_render.py scan.pdf pages/ 1 2
    python3 -I tools/mistral_ocr.py ocr/ pages/p0001.jpg

## Cloudflare R2

Cloudflare dashboard, R2, your bucket (`B` below), Manage API tokens, create token "Object Read & Write" for this bucket.
Gives key id (32 hex) and secret (64 hex). Endpoint: `https://<account id>.r2.cloudflarestorage.com`.

    aws configure --profile r2-books          # key id, secret, region: auto, output: json
    B=<bucket>
    E=https://<account id>.r2.cloudflarestorage.com
    aws --profile r2-books --region auto --endpoint-url $E s3 ls s3://$B/

`SignatureDoesNotMatch` = secret pasted wrong.

Upload (preview first, never deletes):

    bash tools/upload-books.sh $B $E out/<book>
    bash tools/upload-books.sh $B $E out/<book> --upload

Public read URL (default of server, change with `BOOKS_URL`):

    https://pub-c082064d3c234b25bcb6abd4240e637c.r2.dev/LIBRARY.md

## Teaching website

Website reads R2. Book visible only when `done` in R2 `PROCESSED.md`.

Need push access to the website repo:

    git clone git@github.com:<org>/<website>.git ~/website

After book upload:

    # add row "| `<book>/` | 2026-11-12 | done |" to PROCESSED.md, then
    aws --profile r2-books --region auto --endpoint-url $E s3 cp PROCESSED.md s3://$B/PROCESSED.md
    bash tools/r2_library_map.sh --upload
    cd ~/website && git commit --allow-empty -m "Pages: rebuild <book>" && git push

## Workflow short

    Books/RAW/<scan>.pdf
      -> tools/pdf_render.py, tools/scan_split.py     pages
      -> tools/mistral_ocr.py                          OCR markdown + LaTeX
      -> agent + tools/TRANSLATE_BRIEF.md              English chapters
      -> agent + tools/PROOF_BRIEF.md                  proofread
      -> tools/mistral_compare.py, mistral_textcheck.py  re-check
      -> tools/figcrop.py, structlabels.py             figures
      -> tools/fix_anchors.py, merge_index.py          INDEX, anchors
      -> tools/upload-books.sh --upload                R2
      -> PROCESSED.md + r2_library_map.sh --upload     website

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
