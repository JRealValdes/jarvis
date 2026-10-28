"""Image search shaping and the inline-image tool contract."""

from __future__ import annotations

from jarvis.infrastructure.web.search import search_public_images
from jarvis.tools.builtins.web_image_search import web_image_search_tool


def test_search_public_images_keeps_direct_urls_and_prefers_wikimedia():
    raw = [
        {
            "title": "Blog photo",
            "image": "https://cdn.example/photo.jpg",
            "url": "https://blog.example/post",
            "source": "Example",
        },
        {
            "title": "Painting",
            "image": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night.jpg",
            "url": "https://commons.wikimedia.org/wiki/File:Van_Gogh_-_Starry_Night.jpg",
            "source": "Wikimedia Commons",
        },
        {
            "title": "HTML page, not an image",
            "image": "https://example.com/starry-night",
            "url": "https://example.com/starry-night",
            "source": "Example",
        },
        {
            "title": "Duplicate",
            "image": "https://cdn.example/photo.jpg",
            "url": "https://blog.example/post",
            "source": "Example",
        },
    ]

    def fake_search(query: str, max_results: int) -> list[dict]:
        assert query == "Van Gogh The Starry Night"
        assert max_results == 3
        return raw

    results = search_public_images(
        "Van Gogh The Starry Night",
        search_fn=fake_search,
    )
    assert [item["image_url"] for item in results] == [
        "https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/Van_Gogh_-_Starry_Night.jpg",
        "https://cdn.example/photo.jpg",
    ]
    assert results[0]["page_url"].startswith("https://commons.wikimedia.org/")
    assert results[0]["source"] == "Wikimedia Commons"


def test_search_public_images_rejects_empty_query():
    try:
        search_public_images("  ")
    except ValueError as exc:
        assert "empty" in str(exc).lower()
    else:
        raise AssertionError("expected ValueError")


def test_image_tool_empty_candidates_forbid_invented_urls(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_image_search.search_public_images",
        lambda query, max_results=3: [],
    )
    text = web_image_search_tool.invoke({"query": "nothing visual"})
    assert "No image candidates" in text
    assert "Do not invent an image URL" in text
    assert "![" not in text


def test_image_tool_lists_exact_urls_and_one_image_cap(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_image_search.search_public_images",
        lambda query, max_results=3: [
            {
                "title": "The Starry Night",
                "image_url": "https://upload.wikimedia.org/starry.jpg",
                "page_url": "https://commons.wikimedia.org/wiki/File:Starry.jpg",
                "source": "Wikimedia Commons",
            }
        ],
    )
    text = web_image_search_tool.invoke({"query": "The Starry Night"})
    assert "https://upload.wikimedia.org/starry.jpg" in text
    assert "at most 1 image" in text
    assert "Never invent" in text
    assert "Source page:" in text


def test_image_tool_requires_a_query():
    text = web_image_search_tool.invoke({"query": "  "})
    assert "Provide an image search query" in text
    assert "do not invent" in text.lower()
