---
name: books-process
description: Process a scanned book (local PDF or HTTPS URL) into English Markdown chapters, figures and library indexes, then publish to R2.
---

Input: $ARGUMENTS

- Call `get_book_guide(include_library_map=false)` of the `books` MCP server and follow `processing_workflow` and `guide`.
- Without MCP: read `src/books_mcp/books/01_workflow.md` and `02_guide.md` of this repo.
- Tools are in `tools/`. Stay local unless the user asks to publish.
