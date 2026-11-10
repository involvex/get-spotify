"""Fetch Spotify embed HTML and extract mp3/mp4 media URLs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

PREVIEW_HINTS = (
    "p.scdn.co/mp3-preview/",
    "smart-preview-clips.spotifycdn.com",
    "/previews/",
)
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp")
_NAME_RE = re.compile(r'"name"\s*:\s*"((?:\\.|[^"\\])*)"')

_TITLE_RE = re.compile(r"<title[^>]*>([^<]*)</title>", re.IGNORECASE | re.DOTALL)
_OG_VIDEO_RE = re.compile(
    r'<meta[^>]+property=["\']og:video(?::url)?["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_VIDEO_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:video(?::url)?["\']',
    re.IGNORECASE,
)
_OG_AUDIO_RE = re.compile(
    r'<meta[^>]+property=["\']og:audio(?::url)?["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_OG_AUDIO_RE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:audio(?::url)?["\']',
    re.IGNORECASE,
)
_PASSTHROUGH_RE = re.compile(
    r'"passthroughUrl"\s*:\s*"(https?://[^"\\]+)"',
    re.IGNORECASE,
)
_MEDIA_URL_RE = re.compile(
    r'https?://[^\s"\'<>\\]+?\.(?:mp3|mp4)(?:\?[^\s"\'<>\\]*)?',
    re.IGNORECASE,
)
_EPISODE_LINK_RE = re.compile(
    r"https?://open\.spotify\.com/(?:embed/)?episode/([A-Za-z0-9]+)",
    re.IGNORECASE,
)
_ESCAPED_MEDIA_RE = re.compile(
    r'https?:\\+/\\+/[^\s"\'<>]+?\.(?:mp3|mp4)(?:\\?[^"\'\\]*)?',
    re.IGNORECASE,
)


@dataclass(frozen=True)
class MediaCandidate:
    """A downloadable media URL discovered in an embed page."""

    url: str
    ext: str
    kind: str  # passthrough | video | preview | unknown


@dataclass(frozen=True)
class EmbedResult:
    """Parsed result from one embed page fetch."""

    page_url: str
    title: str | None
    media: list[MediaCandidate]
    episode_ids: list[str]


class EmbedError(RuntimeError):
    """Raised when an embed page cannot be fetched."""


def fetch_html(url: str, *, timeout: float = 30.0) -> str:
    """GET a URL and return decoded HTML text."""
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except HTTPError as exc:
        raise EmbedError(f"HTTP {exc.code} fetching {url}") from exc
    except URLError as exc:
        raise EmbedError(f"Network error fetching {url}: {exc.reason}") from exc


def extract_title(html: str) -> str | None:
    match = _TITLE_RE.search(html)
    if match:
        title = unescape(match.group(1)).strip()
        title = re.sub(r"\s*\|\s*Spotify\s*$", "", title, flags=re.IGNORECASE)
        if title:
            return title

    # Embed pages often ship an empty <title>; fall back to JSON "name".
    for match in _NAME_RE.finditer(html):
        raw = match.group(1)
        try:
            name = json.loads(f'"{raw}"')
        except json.JSONDecodeError:
            name = unescape(raw)
        name = str(name).strip()
        if name and name.lower() != "spotify":
            return name
    return None


def _ext_from_url(url: str) -> str:
    path = url.split("?", 1)[0].lower()
    if path.endswith(".mp4"):
        return "mp4"
    if path.endswith(".mp3"):
        return "mp3"
    # Preview hosts sometimes omit a real extension in path segments.
    if "mp3-preview" in path:
        return "mp3"
    return "mp3"


def _is_preview_url(url: str) -> bool:
    lower = url.lower()
    return any(hint in lower for hint in PREVIEW_HINTS)


def _kind_for(url: str, *, forced: str | None = None) -> str:
    if forced == "passthrough":
        return "passthrough"
    if forced == "preview" or _is_preview_url(url):
        return "preview"
    if forced:
        return forced
    if url.lower().split("?", 1)[0].endswith(".mp4"):
        return "video"
    return "unknown"


def _is_image_url(url: str) -> bool:
    path = url.split("?", 1)[0].lower()
    return any(path.endswith(ext) for ext in IMAGE_EXT)


def _normalize_url(url: str) -> str:
    url = unescape(url.strip())
    url = url.replace("\\/", "/")
    url = url.replace("\\u0026", "&")
    return url


def _add_candidate(
    bucket: dict[str, MediaCandidate],
    url: str,
    *,
    kind: str | None = None,
) -> None:
    url = _normalize_url(url)
    if not url.startswith("http"):
        return
    if _is_image_url(url):
        return
    ext = _ext_from_url(url)
    if ext not in {"mp3", "mp4"}:
        return
    candidate = MediaCandidate(
        url=url,
        ext=ext,
        kind=_kind_for(url, forced=kind),
    )
    existing = bucket.get(url)
    if existing is None:
        bucket[url] = candidate
        return
    # Prefer more specific kinds over unknown/preview.
    rank = {
        "passthrough": 3,
        "video": 2,
        "unknown": 1,
        "preview": 0,
    }
    if rank.get(candidate.kind, 0) > rank.get(existing.kind, 0):
        bucket[url] = candidate


def _walk_json(node: object) -> Iterable[tuple[str, str | None]]:
    """Yield (url, kind_hint) pairs from nested JSON-like structures."""
    if isinstance(node, dict):
        passthrough = node.get("passthroughUrl")
        if isinstance(passthrough, str) and passthrough:
            yield passthrough, "passthrough"

        audio_preview = node.get("audioPreview")
        if isinstance(audio_preview, dict):
            preview_url = audio_preview.get("url")
            if isinstance(preview_url, str) and preview_url:
                yield preview_url, "preview"

        audio = node.get("audio")
        if isinstance(audio, dict):
            items = audio.get("items") or []
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_url = item.get("url")
                    if not isinstance(item_url, str) or not item_url:
                        continue
                    if item.get("externallyHosted"):
                        yield item_url, "passthrough"
                    elif ".mp3" in item_url.lower() or ".mp4" in item_url.lower():
                        yield item_url, None

        for value in node.values():
            yield from _walk_json(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk_json(item)


def _extract_json_blobs(html: str) -> list[object]:
    blobs: list[object] = []
    # Common embed payload markers.
    patterns = [
        r'<script[^>]+id="__NEXT_DATA__"[^>]*>(\{.*?\})</script>',
        r"Spotify\.Entity\s*=\s*(\{.*?\});",
        r'"props"\s*:\s*(\{.*?\})\s*,\s*"page"',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, html, re.DOTALL):
            raw = match.group(1)
            try:
                blobs.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return blobs


def extract_media(html: str) -> list[MediaCandidate]:
    """Extract mp3/mp4 candidates from embed HTML."""
    bucket: dict[str, MediaCandidate] = {}

    for match in _PASSTHROUGH_RE.finditer(html):
        _add_candidate(bucket, match.group(1), kind="passthrough")

    for blob in _extract_json_blobs(html):
        for url, kind in _walk_json(blob):
            _add_candidate(bucket, url, kind=kind)

    # Also try to parse large JSON-looking substrings that include passthrough.
    for match in re.finditer(r"\{[^{}]*passthroughUrl[^{}]*\}", html):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        for url, kind in _walk_json(obj):
            _add_candidate(bucket, url, kind=kind)

    for regex in (_OG_VIDEO_RE, _OG_VIDEO_RE_ALT):
        for match in regex.finditer(html):
            _add_candidate(bucket, match.group(1), kind="video")

    for regex in (_OG_AUDIO_RE, _OG_AUDIO_RE_ALT):
        for match in regex.finditer(html):
            _add_candidate(bucket, match.group(1), kind=None)

    for match in _MEDIA_URL_RE.finditer(html):
        _add_candidate(bucket, match.group(0), kind=None)

    for match in _ESCAPED_MEDIA_RE.finditer(html):
        _add_candidate(bucket, match.group(0), kind=None)

    return _rank_media(list(bucket.values()))


def _rank_media(media: list[MediaCandidate]) -> list[MediaCandidate]:
    """Prefer passthrough/full media over short previews when both exist."""
    rank = {
        "passthrough": 0,
        "video": 1,
        "unknown": 2,
        "preview": 3,
    }
    sorted_media = sorted(
        media,
        key=lambda m: (rank.get(m.kind, 9), m.ext != "mp3", m.url),
    )
    has_full = any(m.kind in {"passthrough", "video", "unknown"} for m in sorted_media)
    if has_full:
        return [m for m in sorted_media if m.kind != "preview"]
    return sorted_media


def extract_episode_ids(html: str) -> list[str]:
    """Collect episode ids linked from a show embed page."""
    seen: set[str] = set()
    ordered: list[str] = []
    for match in _EPISODE_LINK_RE.finditer(html):
        episode_id = match.group(1)
        if episode_id not in seen:
            seen.add(episode_id)
            ordered.append(episode_id)
    return ordered


def parse_embed(page_url: str, html: str) -> EmbedResult:
    return EmbedResult(
        page_url=page_url,
        title=extract_title(html),
        media=extract_media(html),
        episode_ids=extract_episode_ids(html),
    )


def fetch_embed(page_url: str, *, timeout: float = 30.0) -> EmbedResult:
    html = fetch_html(page_url, timeout=timeout)
    return parse_embed(page_url, html)
