import httpx
import pytest

from books_mcp.library import PublicBooks

LIBRARY = """# Library map
## `example-book/` — Example book, Author, 1886
1 files
  - `01-chapter.md` **Funicular polygons** (pp. 12–14) — Equilibrium and reciprocal diagrams.
## `modern-notes/` — Modern notes, 2020
1 files
  - `01-notes.md` **Reciprocal diagrams** Equilibrium of a funicular polygon, after Lévy.
"""


def make_books():
    requests = []

    def handle(request):
        requests.append(request)
        assert "authorization" not in request.headers
        if request.url.path == "/LIBRARY.md":
            return httpx.Response(200, text=LIBRARY)
        if request.url.path == "/example-book/01-chapter.md":
            return httpx.Response(200, text="First line\nSecond line\nThird line\n")
        if request.url.path == "/example-book/src/01-chapter.md":
            return httpx.Response(200, text="Exact source formula: $`EI`$\n")
        if request.url.path == "/example-book/figures/fig001.png":
            return httpx.Response(200, content=b"\x89PNG")
        if request.url.path == "/example-book/GRAPHIC-STATICS-NOTATION.md":
            return httpx.Response(200, text="Roman numerals label nodes.\n")
        return httpx.Response(404)

    return PublicBooks("https://example.test", transport=httpx.MockTransport(handle)), requests


def test_discover_search_fetch_and_cache():
    books, requests = make_books()
    assert books.list_books()[0]["section_count"] == 1
    matches = books.search("reciprocal equilibrium")
    assert matches[0]["summary"].startswith("(pp. 12–14)")
    assert len(requests) == 1  # Searching uses only the small library map.
    result = books.read("example-book", matches[0]["section"], 2, 1)
    assert result["text"] == "Second line"
    assert result["next_start_line"] == 3
    assert result["url"] == "https://example.test/example-book/01-chapter.md"
    books.read("example-book", "01-chapter.md")
    assert len(requests) == 2


def test_unknown_books_paths_and_limits():
    books, requests = make_books()
    for section in ["../secret.md", "https://other.test/file.md", "missing.md"]:
        with pytest.raises(ValueError):
            books.read("example-book", section)
    with pytest.raises(ValueError, match="Unknown book"):
        books.sections("missing")
    with pytest.raises(ValueError):
        books.search("test", limit=100)
    with pytest.raises(ValueError):
        books.read("example-book", "01-chapter.md", line_count=0)
    assert len(requests) == 1
    assert books.search("  ") == []


def test_library_map_notation_and_source_representation():
    books, requests = make_books()
    assert books.library_map()["text"] == LIBRARY
    notation = books.read("example-book", "GRAPHIC-STATICS-NOTATION.md")
    assert "Roman numerals" in notation["text"]
    source = books.read("example-book", "01-chapter.md", representation="source")
    assert "$`EI`$" in source["text"]
    assert source["url"].endswith("/example-book/src/01-chapter.md")
    assert source["representation"] == "source"
    with pytest.raises(ValueError, match="indexed chapters"):
        books.read("example-book", "GLOSSARY.md", representation="source")
    with pytest.raises(ValueError, match="representation"):
        books.read("example-book", "01-chapter.md", representation="../../")
    assert len(requests) == 3


@pytest.mark.parametrize("status", [301, 401, 404, 429, 500])
def test_storage_errors_are_explicit(status):
    books = PublicBooks("https://example.test", transport=httpx.MockTransport(
        lambda _: httpx.Response(status, headers={"Location": "https://other.test"})
    ))
    with pytest.raises(ValueError, match=f"HTTP {status}"):
        books.list_books()


def test_document_size_limit():
    books = PublicBooks("https://example.test", transport=httpx.MockTransport(
        lambda _: httpx.Response(200, content=b"x" * 2_000_001)
    ))
    with pytest.raises(ValueError, match="2 MB"):
        books.list_books()


def test_library_schema_errors():
    books = PublicBooks("https://example.test", transport=httpx.MockTransport(
        lambda _: httpx.Response(200, text="unexpected index format")
    ))
    with pytest.raises(ValueError, match="No book sections"):
        books.list_books()


def test_search_ranks_historical_books_first_and_ignores_accents():
    books, _ = make_books()
    # the modern chapter has both words in its title, but the 1886 book comes first
    assert [(hit["book"], hit["historical"]) for hit in books.search("reciprocal diagrams")] == [
        ("example-book", True), ("modern-notes", False)]
    assert books.search("lévy")[0]["book"] == "modern-notes"   # "Lévy" in a summary, typed with or without accent
    assert books.search("levy funicul", book="modern-notes")[0]["section"] == "01-notes.md"
    with pytest.raises(ValueError, match="Unknown book"):
        books.search("x", book="missing")


def test_figure_only_from_the_library():
    books, _ = make_books()
    assert books.figure("example-book/figures/fig001.png") == (b"\x89PNG", "png")
    assert books.figure("https://example.test/example-book/figures/fig001.png")[1] == "png"
    for url in ("https://other.test/example-book/figures/fig001.png", "example-book/01-chapter.md", "../x.png"):
        with pytest.raises(ValueError):
            books.figure(url)


def test_fastmcp_v4_server_tools_and_prompts(monkeypatch):
    import asyncio

    import fastmcp
    from fastmcp import Client

    import books_mcp.server as srv

    assert int(fastmcp.__version__.split(".")[0]) >= 4
    mock_books, _ = make_books()
    monkeypatch.setattr(srv, "books", mock_books)

    async def run_checks():
        async with Client(srv.mcp) as client:
            tools = await client.list_tools()
            tool_names = {t.name for t in tools}
            assert {"command", "get_book_guide", "list_books", "list_book_sections", "search_books", "read_book_section", "look_at_figure"} <= tool_names

            prompts = await client.list_prompts()
            prompt_names = {p.name for p in prompts}
            assert {"books", "books_workflow", "books_guide", "books_upload", "books_website", "books_process"} <= prompt_names

            wf = await client.call_tool("command", {"name": "mcp_books_workflow"})
            assert "mistral_ocr.py" in str(wf)
            assert "photos_to_pdf.py" in str(wf)

            guide = await client.call_tool("get_book_guide", {"include_library_map": True})
            assert "Example book" in str(guide)

            fig = await client.call_tool("look_at_figure", {"url": "example-book/figures/fig001.png"})
            assert any(getattr(item, "type", "") == "image" for item in fig.content)

            pr = await client.get_prompt("books_process", {"source": "/tmp/photos"})
            assert "photos_to_pdf.py" in str(pr)

    asyncio.run(run_checks())
