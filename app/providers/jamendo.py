import logging
from typing import List, Optional

import requests

from app.providers.base import MusicProvider, SearchResult

logger = logging.getLogger(__name__)

JAMENDO_BASE = "https://api.jamendo.com/v3.0"
DEFAULT_LIMIT = 20


class JamendoProvider(MusicProvider):
    name = "Jamendo"

    def __init__(self, client_id: str = ""):
        self._client_id = client_id

    def credential_error(self) -> Optional[str]:
        if not self._client_id:
            return "Jamendo client ID is not configured. Add it in Settings."
        return None

    def is_available(self) -> bool:
        return bool(self._client_id)

    def _request(self, endpoint: str, params: dict) -> Optional[dict]:
        if not self.is_available():
            return None
        url = f"{JAMENDO_BASE}{endpoint}"
        params = dict(params)
        params["client_id"] = self._client_id
        params.setdefault("format", "json")
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("Jamendo request failed: %s", e)
            return None

    def search(self, query: str, limit: int = DEFAULT_LIMIT) -> List[SearchResult]:
        if not query.strip():
            return []
        data = self._request("/tracks", {
            "namesearch": query,
            "limit": limit,
            "include": "musicinfo licenses",
        })
        return self._parse_tracks(data)

    def search_artist(self, artist: str, limit: int = DEFAULT_LIMIT) -> List[SearchResult]:
        if not artist.strip():
            return []
        data = self._request("/tracks", {
            "artist_name": artist,
            "limit": limit,
            "include": "musicinfo licenses",
        })
        return self._parse_tracks(data)

    def search_genre(self, genre: str, limit: int = DEFAULT_LIMIT) -> List[SearchResult]:
        if not genre.strip():
            return []
        data = self._request("/tracks", {
            "tags": genre,
            "limit": limit,
            "include": "musicinfo licenses",
        })
        return self._parse_tracks(data)

    def _parse_tracks(self, data: Optional[dict]) -> List[SearchResult]:
        results: List[SearchResult] = []
        if not data:
            return results
        headers = data.get("headers", {})
        if headers.get("status") == "failed":
            logger.warning("Jamendo API error: %s", headers.get("error_message"))
            return results
        for item in data.get("results", []):
            try:
                results.append(self._track_to_result(item))
            except Exception as e:
                logger.debug("Skipping malformed Jamendo track: %s", e)
        return results

    def _track_to_result(self, item: dict) -> SearchResult:
        musicinfo = item.get("musicinfo", {}) or {}
        tags = musicinfo.get("tags", {}) or {}
        genre = None
        if isinstance(tags, dict):
            genre = tags.get("genres") or tags.get("genre")
            if isinstance(genre, list):
                genre = genre[0] if genre else None

        audio = item.get("audio")
        download_available = bool(item.get("download_url"))
        license_name = None
        license_url = None
        licenses = item.get("licenses") or []
        if isinstance(licenses, list) and licenses:
            lic = licenses[0] if isinstance(licenses[0], dict) else {}
            license_name = lic.get("name")
            license_url = lic.get("url")

        return SearchResult(
            source="Jamendo",
            track_id=str(item.get("id", "")),
            title=item.get("name") or "Unknown",
            artist=item.get("artist_name") or "Unknown",
            album=item.get("album_name"),
            genre=genre,
            duration_seconds=float(item["duration"]) if item.get("duration") is not None else None,
            artwork_url=item.get("image") or item.get("album_image"),
            source_url=item.get("shareurl") or item.get("url"),
            preview_url=audio,
            download_url=item.get("download_url"),
            download_available=download_available,
            license_name=license_name,
            license_url=license_url,
            year=str(item.get("releasedate"))[:4] if item.get("releasedate") else None,
        )
