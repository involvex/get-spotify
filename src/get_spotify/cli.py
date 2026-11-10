"""Command-line entry point for get-spotify."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from get_spotify import __version__
from get_spotify.download import DownloadError, build_filename, download_file
from get_spotify.embed import (
    EmbedError,
    EmbedResult,
    MediaCandidate,
    fetch_embed,
)
from get_spotify.urls import SpotifyRef, UrlError, parse_spotify_url


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="get-spotify",
        description=(
            "Download mp3/mp4 media URLs exposed by Spotify embed pages. "
            "Works best for podcasts/episodes with passthrough media; "
            "full music tracks are usually DRM-protected and will fail."
        ),
    )
    parser.add_argument(
        "url",
        help="Spotify episode, track, show, or embed URL (or spotify: URI)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=".",
        help="Output directory (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List discovered media URLs without downloading",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print extra diagnostics",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message, file=sys.stderr)


def _is_full_media(media: list[MediaCandidate]) -> bool:
    return any(item.kind != "preview" for item in media)


def _merge_media(
    existing: list[MediaCandidate],
    incoming: list[MediaCandidate],
) -> list[MediaCandidate]:
    bucket = {item.url: item for item in existing}
    for item in incoming:
        prev = bucket.get(item.url)
        if prev is None or (
            item.kind != "preview" and prev.kind == "preview"
        ):
            bucket[item.url] = item
    merged = list(bucket.values())
    if _is_full_media(merged):
        return [item for item in merged if item.kind != "preview"]
    return merged


def _discover_for_ref(
    ref: SpotifyRef,
    *,
    verbose: bool,
) -> tuple[EmbedResult | None, list[MediaCandidate]]:
    last_result: EmbedResult | None = None
    media: list[MediaCandidate] = []
    for page_url in ref.embed_candidates():
        _log(verbose, f"Fetching embed: {page_url}")
        result = fetch_embed(page_url)
        last_result = result
        if result.media:
            media = _merge_media(media, result.media)
            if _is_full_media(media):
                return result, media
            _log(verbose, f"Only preview media in {page_url}; trying next")
        else:
            _log(verbose, f"No media in {page_url}")
    return last_result, media


def _resolve_media(
    ref: SpotifyRef,
    *,
    verbose: bool,
) -> tuple[SpotifyRef, EmbedResult | None, list[MediaCandidate]]:
    result, media = _discover_for_ref(ref, verbose=verbose)
    if media:
        return ref, result, media

    # Show pages: try the first linked episode.
    if ref.type == "show" and result and result.episode_ids:
        episode_id = result.episode_ids[0]
        _log(verbose, f"Show has no direct media; trying episode {episode_id}")
        episode_ref = SpotifyRef(type="episode", id=episode_id)
        episode_result, episode_media = _discover_for_ref(
            episode_ref,
            verbose=verbose,
        )
        return episode_ref, episode_result, episode_media

    return ref, result, []


def _preview_only(media: list[MediaCandidate]) -> bool:
    return bool(media) and all(item.kind == "preview" for item in media)


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ref = parse_spotify_url(args.url)
    except UrlError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        active_ref, result, media = _resolve_media(ref, verbose=args.verbose)
    except EmbedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    title = result.title if result else None
    if args.verbose and title:
        _log(True, f"Title: {title}")

    if not media:
        if ref.type == "track":
            print(
                "error: no downloadable mp3/mp4 found for this track. "
                "Spotify music is usually DRM-protected; only short "
                "previews (or nothing) appear in the public embed.",
                file=sys.stderr,
            )
        else:
            print(
                "error: no downloadable mp3/mp4 found in the Spotify embed. "
                "This episode may be DRM-protected or lack passthrough media "
                '(passthrough: "NONE").',
                file=sys.stderr,
            )
        return 1

    if _preview_only(media):
        if active_ref.type == "track":
            print(
                "note: only a short Spotify preview was found for this track "
                "(full songs are not available via embed).",
                file=sys.stderr,
            )
        else:
            print(
                "note: only preview media was found "
                "(no passthrough/full mp3/mp4 in the embed HTML).",
                file=sys.stderr,
            )

    if args.dry_run:
        for item in media:
            print(f"{item.kind}\t{item.ext}\t{item.url}")
        return 0

    output_dir = Path(args.output)
    saved = 0
    for index, item in enumerate(media, start=1):
        filename = build_filename(
            item,
            title=title,
            resource_id=active_ref.id,
            index=index,
            total=len(media),
        )
        dest = output_dir / filename
        _log(args.verbose, f"Saving {item.kind} -> {dest}")
        try:
            path = download_file(item, dest, progress=True)
        except DownloadError as exc:
            print(f"error: {exc}", file=sys.stderr)
            continue
        print(f"saved: {path}")
        saved += 1

    if saved == 0:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
