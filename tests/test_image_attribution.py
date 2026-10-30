"""Attribution captions use only fields the provider returned."""

from jarvis.infrastructure.images.attribution import (
    GENERATED_IMAGE_CAPTION,
    SOURCE_UNKNOWN,
    format_image_attribution,
)


def test_caption_links_the_source_and_includes_a_known_license():
    caption = format_image_attribution(
        title="The Starry Night",
        page_url="https://commons.wikimedia.org/wiki/File:Starry.jpg",
        source="Wikimedia Commons",
        license_name="CC BY-SA 4.0",
    )
    assert caption == (
        "The Starry Night · "
        "[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Starry.jpg)"
        " · License: CC BY-SA 4.0"
    )


def test_caption_omits_a_missing_license():
    caption = format_image_attribution(
        title="The Starry Night",
        page_url="https://commons.wikimedia.org/wiki/File:Starry.jpg",
        source="Wikimedia Commons",
    )
    assert "License:" not in caption
    assert caption.endswith(
        "[Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Starry.jpg)"
    )


def test_missing_metadata_is_source_unknown():
    assert format_image_attribution() == SOURCE_UNKNOWN
    assert (
        format_image_attribution(title="  ", page_url="not a url", source="")
        == SOURCE_UNKNOWN
    )


def test_source_name_without_a_page_stays_plain_text():
    caption = format_image_attribution(source="Example Museum")
    assert caption == "Example Museum"
    assert "http" not in caption
    assert "License:" not in caption


def test_title_brackets_do_not_break_the_link():
    caption = format_image_attribution(
        title="Night [detail]",
        page_url="https://example.com/night",
        source="Example",
    )
    assert caption == "Night (detail) · [Example](https://example.com/night)"


def test_generated_caption_is_not_a_license():
    assert GENERATED_IMAGE_CAPTION == "Generated image"
    assert "license" not in GENERATED_IMAGE_CAPTION.lower()
