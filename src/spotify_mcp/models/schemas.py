from typing import Any

from pydantic import BaseModel, Field

from spotify_mcp.utils.links import to_uri


class User(BaseModel):
    id: str
    display_name: str | None = None


class Track(BaseModel):
    id: str | None = None
    uri: str = ""
    name: str = ""
    artists: list[str] = Field(default_factory=list)
    album: str | None = None
    duration_ms: int = 0
    is_local: bool = False

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "Track":
        track_id = item.get("id")
        return cls(
            id=track_id,
            uri=item.get("uri") or (to_uri("track", track_id) if track_id else ""),
            name=item.get("name") or "",
            artists=[a.get("name") or "" for a in item.get("artists") or []],
            album=(item.get("album") or {}).get("name"),
            duration_ms=item.get("duration_ms") or 0,
            is_local=bool(item.get("is_local")),
        )


class Playlist(BaseModel):
    id: str
    uri: str
    name: str = ""
    owner_id: str = ""
    public: bool | None = None
    collaborative: bool = False
    total_tracks: int = 0
    description: str | None = None

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "Playlist":
        return cls(
            id=item["id"],
            uri=item.get("uri") or to_uri("playlist", item["id"]),
            name=item.get("name") or "",
            owner_id=(item.get("owner") or {}).get("id") or "",
            public=item.get("public"),
            collaborative=bool(item.get("collaborative")),
            total_tracks=(item.get("tracks") or {}).get("total") or 0,
            description=item.get("description") or None,
        )
