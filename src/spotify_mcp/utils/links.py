import re
from urllib.parse import urlparse

TYPES = {"track", "playlist", "album", "artist"}
_ID_RE = re.compile(r"[A-Za-z0-9]{22}")


def parse_ref(
    ref: str, expect: str | None = None, *, bare_type: str | None = None
) -> tuple[str, str]:
    """Parse a Spotify URL, URI, or bare ID into ``(type, id)``.

    ``expect`` asserts the parsed type (and doubles as the type for bare IDs).
    ``bare_type`` sets the type for bare IDs without asserting parsed forms.
    """
    ref = ref.strip()
    if not ref:
        raise ValueError("Empty Spotify reference")

    if ref.startswith("spotify:"):
        parts = ref.split(":")
        if len(parts) != 3:
            raise ValueError(f"Invalid Spotify URI: {ref!r}")
        kind, spotify_id = parts[1], parts[2]
    else:
        parsed = urlparse(ref)
        if parsed.netloc:
            if parsed.netloc != "open.spotify.com":
                raise ValueError(f"Not a Spotify URL: {ref!r}")
            segments = [s for s in parsed.path.split("/") if s and not s.startswith("intl-")]
            if len(segments) != 2:
                raise ValueError(f"Unrecognized Spotify URL: {ref!r}")
            kind, spotify_id = segments
        elif expect or bare_type:
            kind, spotify_id = (bare_type or expect or ""), ref
        else:
            raise ValueError(
                f"Bare ID {ref!r} needs an explicit type (one of {', '.join(sorted(TYPES))})"
            )

    if kind not in TYPES:
        raise ValueError(f"Unsupported Spotify type {kind!r} in {ref!r}")
    if expect and kind != expect:
        raise ValueError(f"Expected a {expect} reference, got a {kind}: {ref!r}")
    if not _ID_RE.fullmatch(spotify_id):
        raise ValueError(f"Invalid Spotify ID in {ref!r}")
    return kind, spotify_id


def to_uri(kind: str, spotify_id: str) -> str:
    return f"spotify:{kind}:{spotify_id}"
