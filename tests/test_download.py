from get_spotify.download import build_filename, sanitize_filename
from get_spotify.embed import MediaCandidate


def test_sanitize_filename_strips_windows_chars():
    assert sanitize_filename('a<>:"/\\|?*b') == "ab"
    assert sanitize_filename("   ") == "spotify-media"
    assert sanitize_filename("hello.world.") == "hello.world"


def test_build_filename_preview_and_index():
    candidate = MediaCandidate(
        url="https://p.scdn.co/mp3-preview/x.mp3",
        ext="mp3",
        kind="preview",
    )
    name = build_filename(
        candidate,
        title="My Track",
        resource_id="abc",
        index=1,
        total=1,
    )
    assert name == "My Track-preview.mp3"

    multi = build_filename(
        MediaCandidate(
            url="https://cdn.example.com/a.mp4",
            ext="mp4",
            kind="video",
        ),
        title="Episode",
        resource_id="id",
        index=2,
        total=2,
    )
    assert multi == "Episode-2.mp4"
