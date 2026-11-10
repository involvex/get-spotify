from get_spotify.cli import run
from get_spotify.embed import EmbedResult, MediaCandidate


def test_cli_bad_url_exit_2():
    assert run(["https://example.com/not-spotify"]) == 2


def test_cli_dry_run_lists_media(monkeypatch, capsys):
    media = [
        MediaCandidate(
            url="https://traffic.megaphone.fm/demo.mp3",
            ext="mp3",
            kind="passthrough",
        )
    ]

    def fake_resolve(ref, *, verbose):
        result = EmbedResult(
            page_url=ref.embed_url(),
            title="Demo Episode",
            media=media,
            episode_ids=[],
        )
        return ref, result, media

    monkeypatch.setattr("get_spotify.cli._resolve_media", fake_resolve)
    code = run(
        [
            "https://open.spotify.com/episode/1TzHqdEz21lHPS9Akc9vRl",
            "--dry-run",
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "passthrough" in captured.out
    assert "demo.mp3" in captured.out


def test_cli_no_media_exit_1(monkeypatch, capsys):
    def fake_resolve(ref, *, verbose):
        result = EmbedResult(
            page_url=ref.embed_url(),
            title="Locked",
            media=[],
            episode_ids=[],
        )
        return ref, result, []

    monkeypatch.setattr("get_spotify.cli._resolve_media", fake_resolve)
    code = run(["https://open.spotify.com/track/11dFghVXANMlKmJXsNCbNl"])
    captured = capsys.readouterr()
    assert code == 1
    assert "DRM" in captured.err or "preview" in captured.err.lower()
