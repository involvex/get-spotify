import pytest

from get_spotify.urls import UrlError, parse_spotify_url


def test_parse_episode_open_url():
    ref = parse_spotify_url(
        "https://open.spotify.com/episode/1TzHqdEz21lHPS9Akc9vRl"
        "?go=1&si=ea36901ce2f44e43"
    )
    assert ref.type == "episode"
    assert ref.id == "1TzHqdEz21lHPS9Akc9vRl"
    assert ref.embed_url() == (
        "https://open.spotify.com/embed/episode/1TzHqdEz21lHPS9Akc9vRl"
    )
    assert ref.embed_candidates() == [
        "https://open.spotify.com/embed/episode/1TzHqdEz21lHPS9Akc9vRl",
        "https://open.spotify.com/embed/episode/1TzHqdEz21lHPS9Akc9vRl/video",
    ]


def test_parse_video_embed_url():
    ref = parse_spotify_url(
        "https://open.spotify.com/embed/episode/1TzHqdEz21lHPS9Akc9vRl/video"
        "?utm_source=generator"
    )
    assert ref.video is True
    assert ref.embed_url() == (
        "https://open.spotify.com/embed/episode/1TzHqdEz21lHPS9Akc9vRl/video"
    )
    assert ref.embed_candidates()[0].endswith("/video")


def test_parse_track_and_uri():
    track = parse_spotify_url("https://open.spotify.com/track/11dFghVXANMlKmJXsNCbNl")
    assert track.type == "track"
    assert track.embed_candidates() == [
        "https://open.spotify.com/embed/track/11dFghVXANMlKmJXsNCbNl"
    ]

    uri = parse_spotify_url("spotify:show:2IyZviDs8WLsVzCNamqhc2")
    assert uri.type == "show"
    assert uri.id == "2IyZviDs8WLsVzCNamqhc2"


def test_reject_bad_urls():
    with pytest.raises(UrlError):
        parse_spotify_url("")
    with pytest.raises(UrlError):
        parse_spotify_url("https://example.com/episode/abc")
    with pytest.raises(UrlError):
        parse_spotify_url("https://open.spotify.com/playlist/abc")
