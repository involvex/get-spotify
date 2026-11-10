"""Stream-download media files with safe filenames."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from get_spotify.embed import USER_AGENT, MediaCandidate

_WINDOWS_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_SPACE = re.compile(r"\s+")


class DownloadError(RuntimeError):
    """Raised when a media file cannot be downloaded."""


def sanitize_filename(name: str, *, max_len: int = 120) -> str:
    """Make a string safe for Windows and POSIX filenames."""
    cleaned = _WINDOWS_BAD.sub("", name)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ")
    cleaned = _MULTI_SPACE.sub(" ", cleaned).strip(" .")
    if not cleaned:
        cleaned = "spotify-media"
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" .")
    return cleaned


def build_filename(
    candidate: MediaCandidate,
    *,
    title: str | None,
    resource_id: str,
    index: int,
    total: int,
) -> str:
    base = sanitize_filename(title) if title else sanitize_filename(resource_id)
    if total > 1:
        base = f"{base}-{index}"
    if candidate.kind == "preview" and "preview" not in base.lower():
        base = f"{base}-preview"
    return f"{base}.{candidate.ext}"


def _content_ok(content_type: str | None, ext: str) -> bool:
    if not content_type:
        return True
    ctype = content_type.split(";", 1)[0].strip().lower()
    if ctype in {"application/octet-stream", "binary/octet-stream"}:
        return True
    if ext == "mp3":
        return ctype in {"audio/mpeg", "audio/mp3", "audio/mpeg3", "audio/x-mpeg"}
    if ext == "mp4":
        return ctype in {
            "video/mp4",
            "audio/mp4",
            "application/mp4",
            "video/mpeg",
        }
    return False


def download_file(
    candidate: MediaCandidate,
    dest: Path,
    *,
    timeout: float = 60.0,
    progress: bool = True,
) -> Path:
    """Download one media URL to dest. Returns the final path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        candidate.url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Referer": "https://open.spotify.com/",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type")
            if not _content_ok(content_type, candidate.ext):
                raise DownloadError(
                    f"Skipping {candidate.url}: unexpected Content-Type "
                    f"{content_type!r}"
                )
            total = response.headers.get("Content-Length")
            total_bytes = int(total) if total and total.isdigit() else None
            tmp = dest.with_suffix(dest.suffix + ".part")
            downloaded = 0
            with tmp.open("wb") as handle:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    downloaded += len(chunk)
                    if progress:
                        _print_progress(dest.name, downloaded, total_bytes)
            tmp.replace(dest)
            if progress:
                sys.stderr.write("\n")
                sys.stderr.flush()
            return dest
    except HTTPError as exc:
        raise DownloadError(f"HTTP {exc.code} downloading {candidate.url}") from exc
    except URLError as exc:
        raise DownloadError(
            f"Network error downloading {candidate.url}: {exc.reason}"
        ) from exc


def _print_progress(name: str, downloaded: int, total: int | None) -> None:
    if total:
        pct = min(100.0, downloaded * 100.0 / total)
        msg = f"\rDownloading {name}: {pct:5.1f}% ({downloaded}/{total} bytes)"
    else:
        msg = f"\rDownloading {name}: {downloaded} bytes"
    sys.stderr.write(msg)
    sys.stderr.flush()
