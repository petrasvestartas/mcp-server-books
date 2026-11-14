---
name: books-process
description: Process a scanned book (local PDF, folder of page photographs, or HTTPS URL) with Mistral OCR into English Markdown chapters, compact PDF, figures, and library indexes, then publish to Cloudflare R2 and the Teaching website.
---

Input: $ARGUMENTS

- Call `get_book_guide(include_library_map=false)` of the `books` MCP server and follow `processing_workflow` and `guide`.
- Without MCP: read `src/books_mcp/books/01_workflow.md`, `02_guide.md`, `03_upload.md`, and `04_website.md` of this repo.
- Always use Mistral OCR (`tools/mistral_ocr.py` with `~/.config/mistral/api_key`). If the source is a folder of photos, pack a compact PDF (`~10–30 MiB`) into `RAW/` with `tools/photos_to_pdf.py`.
- Tools are in `tools/` (`tools/templates/build.py` builds published chapters). Stay local unless the user asks to publish to R2 / `library.html`.
