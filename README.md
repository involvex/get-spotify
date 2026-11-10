# get-spotify

CLI that downloads **mp3/mp4** media URLs exposed by Spotify **embed** pages.

It does **not** bypass DRM. It only downloads direct media links already present
in the public embed HTML (the same approach as feeding an embed URL to
`you-get`'s universal scraper, but with a strict media-only filter so favicons
and images are skipped).

## Install

PyPI: [get-spotify 0.1.0](https://pypi.org/project/get-spotify/0.1.0/)

### From PyPI (recommended)

```bash
pip install get-spotify

# or with uv
uv tool install get-spotify
uvx get-spotify --help
```

### From GitHub

```bash
pip install git+https://github.com/involvex/get-spotify.git
uv tool install git+https://github.com/involvex/get-spotify.git
```

### Local development

With **uv** (recommended):

```bash
uv sync
uv run get-spotify --help
uv run pytest
```

With **pip**:

```bash
python -m pip install -e ".[dev]"
python -m get_spotify --help
pytest
```

## Usage

```bash
get-spotify <spotify-url> [-o DIR] [--dry-run] [-v]
```

Examples:

```bash
# Podcast episode
get-spotify "https://open.spotify.com/episode/1TzHqdEz21lHPS9Akc9vRl"

# Already an embed / video embed URL
get-spotify "https://open.spotify.com/embed/episode/1TzHqdEz21lHPS9Akc9vRl/video"

# List media URLs without downloading
get-spotify "https://open.spotify.com/episode/..." --dry-run

# Track (usually fails or only finds a short preview)
get-spotify "https://open.spotify.com/track/..." -v
```

### Exit codes

| Code | Meaning |
| ---: | --- |
| 0 | At least one file saved (or listed with `--dry-run`) |
| 1 | Valid Spotify URL, but no downloadable mp3/mp4 |
| 2 | Bad URL or network/HTTP failure |

## What works / what does not

| Input | Typical result |
| --- | --- |
| Podcast/episode with publisher passthrough (`passthroughUrl`) | Downloads full mp3 (and mp4 when the video embed exposes it) |
| Episode with DRM / `passthrough: NONE` | Downloads only short preview clips if the embed exposes them; prints a note |
| Music track | Usually preview-only or empty; full songs are DRM-protected |
| Show URL | Tries the show embed, then the first linked episode |

## How it works

1. Normalize the input to `https://open.spotify.com/embed/{type}/{id}`
2. For episodes, also try `.../video` if the audio embed has no media
3. Parse embed HTML for `passthroughUrl`, Open Graph media, and `.mp3`/`.mp4` links
4. Download only those files

## Disclaimer

Use this only for content you have the right to download. Spotify's terms
restrict downloading Spotify-hosted/DRM content. Publisher-hosted podcast files
exposed via passthrough are still subject to the publisher's rights.
