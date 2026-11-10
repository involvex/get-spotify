"""Parse Spotify URLs and normalize them to embed player URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

SUPPORTED_TYPES = frozenset({"episode", "track", "show"})

# open.spotify.com/{embed/}?{type}/{id}[/video]
_OPEN_PATH = re.compile(
    r"^/(?:embed/)?(?P<type>episode|track|show)/(?P<id>[A-Za-z0-9]+)"
    r"(?P<video>/video)?/?$",
    re.IGNORECASE,
)

# spotify:episode:ID / spotify:track:ID / spotify:show:ID
_URI = re.compile(
    r"^spotify:(?P<type>episode|track|show):(?P<id>[A-Za-z0-9]+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SpotifyRef:
    """A normalized Spotify resource reference."""

    type: str
    id: str
    video: bool = False

    def embed_url(self, *, video: bool | None = None) -> str:
        use_video = self.video if video is None else video
        base = f"https://open.spotify.com/embed/{self.type}/{self.id}"
        if use_video and self.type == "episode":
            return f"{base}/video"
        return base

    def embed_candidates(self) -> list[str]:
        """Ordered embed URLs to try (prefer the form the user opened)."""
        if self.type != "episode":
            return [self.embed_url(video=False)]

        primary = self.embed_url(video=self.video)
        secondary = self.embed_url(video=not self.video)
        urls = [primary]
        if secondary not in urls:
            urls.append(secondary)
        return urls


class UrlError(ValueError):
    """Raised when the input is not a supported Spotify URL."""


def parse_spotify_url(raw: str) -> SpotifyRef:
    """Parse an open.spotify.com URL or spotify: URI into a SpotifyRef."""
    text = (raw or "").strip()
    if not text:
        raise UrlError("URL is empty")

    uri_match = _URI.match(text)
    if uri_match:
        return SpotifyRef(
            type=uri_match.group("type").lower(),
            id=uri_match.group("id"),
        )

    if not re.match(r"^https?://", text, re.IGNORECASE):
        text = "https://" + text

    parsed = urlparse(text)
    host = (parsed.hostname or "").lower()
    if host not in {"open.spotify.com", "www.open.spotify.com"}:
        raise UrlError(f"Unsupported host {host!r}; expected open.spotify.com")

    path_match = _OPEN_PATH.match(parsed.path or "")
    if not path_match:
        raise UrlError(
            "Unsupported Spotify path; expected "
            "/episode|/track|/show/{id} (or /embed/...)"
        )

    resource_type = path_match.group("type").lower()
    if resource_type not in SUPPORTED_TYPES:
        raise UrlError(f"Unsupported resource type {resource_type!r}")

    return SpotifyRef(
        type=resource_type,
        id=path_match.group("id"),
        video=bool(path_match.group("video")),
    )
