# AGENTS.md — get-spotify

Guidance for coding agents working in this repository.

## What this project is

A small **stdlib-first Python CLI** that:

1. Accepts a Spotify episode / track / show URL (or `spotify:` URI)
2. Rewrites it to the public **embed** page
3. Scrapes **only** `.mp3` / `.mp4` (and `passthroughUrl`) from that HTML
4. Downloads those files

It does **not** wrap `you-get`, use the Spotify Web API, or bypass DRM/Widevine.

## Layout

| Path | Role |
| --- | --- |
| `src/get_spotify/cli.py` | argparse entry, exit codes |
| `src/get_spotify/urls.py` | URL / URI → embed candidates |
| `src/get_spotify/embed.py` | fetch HTML + media extraction |
| `src/get_spotify/download.py` | stream download + safe filenames |
| `tests/` | fixtures + unit tests (no live Spotify required in CI) |
| `pyproject.toml` | hatchling package; console script `get-spotify` |

## Commands

```bash
# Local editable (uv)
uv sync
uv run get-spotify "https://open.spotify.com/episode/..." --dry-run -v
uv run pytest

# Or pip
python -m pip install -e ".[dev]"
pytest
python -m get_spotify "https://open.spotify.com/episode/..." --dry-run
```

Install from GitHub (after the repo is public):

```bash
pip install git+https://github.com/involvex/get-spotify.git
uv tool install git+https://github.com/involvex/get-spotify.git
```

## Invariants

- **Stdlib networking** (`urllib`) unless the user asks for a HTTP library.
- **Media filter only**: never download favicons / png / jpeg / ico as the main result.
- **No DRM circumvention.** If embed HTML has `passthrough: NONE`, preview clips or a clear failure are correct.
- **Exit codes:** `0` success / dry-run list, `1` no media, `2` bad URL or network, `130` interrupt.
- Prefer small diffs. Do not add OAuth, playlist batching, or `you-get` unless requested.

## Good change targets

- Better title / filename extraction from embed JSON
- Clearer messaging when only previews are found
- Extra fixtures for real embed HTML shapes (sanitized, committed under `tests/fixtures/`)

## Avoid

- Committing downloaded `out/`, `*.mp3`, `*.mp4`, or `_tmp.html`
- Printing secrets or Spotify auth tokens (this tool should not need them)
- Claiming full track downloads work for DRM music
