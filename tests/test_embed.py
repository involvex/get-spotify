from pathlib import Path

from get_spotify.embed import (
    extract_episode_ids,
    extract_media,
    extract_title,
    parse_embed,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_extract_passthrough_and_video_skips_images_and_preview():
    html = _load("episode_passthrough.html")
    media = extract_media(html)

    urls = {item.url for item in media}
    kinds = {item.url: item.kind for item in media}

    assert any(url.endswith(".mp3") or ".mp3?" in url for url in urls)
    assert any(url.endswith(".mp4") for url in urls)
    assert not any(
        "favicon" in url or url.endswith(".png") or url.endswith(".jpeg")
        for url in urls
    )
    assert not any("mp3-preview" in url for url in urls)

    passthrough = [item for item in media if item.kind == "passthrough"]
    assert passthrough
    assert kinds[passthrough[0].url] == "passthrough"

    title = extract_title(html)
    assert title == "Sample Podcast Episode"


def test_drm_episode_has_no_media():
    html = _load("episode_drm.html")
    media = extract_media(html)
    assert media == []


def test_show_extracts_episode_ids():
    html = _load("show_with_episodes.html")
    ids = extract_episode_ids(html)
    assert ids == [
        "EpisodeIdOne1111111111111",
        "EpisodeIdTwo2222222222222",
    ]
    result = parse_embed("https://open.spotify.com/embed/show/abc", html)
    assert result.title == "Cool Show"
    assert result.media == []
    assert result.episode_ids == ids


def test_preview_kept_when_only_option():
    html = """
    <html><head><title>Track Preview | Spotify</title></head>
    <body>
      "url":"https://p.scdn.co/mp3-preview/abcdef1234567890abcdef1234567890abcdef12.mp3"
    </body></html>
    """
    media = extract_media(html)
    assert len(media) == 1
    assert media[0].kind == "preview"
    assert media[0].ext == "mp3"


def test_smart_preview_clip_classified_as_preview():
    html = """
    <html><body>
    "videoPreview":{"url":"https://smart-preview-clips.spotifycdn.com/previews/abc/0/clip.mp4"}
    </body></html>
    """
    media = extract_media(html)
    assert len(media) == 1
    assert media[0].kind == "preview"
    assert media[0].ext == "mp4"
