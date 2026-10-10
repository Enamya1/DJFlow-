import logging
import time
from typing import List, Optional

import requests

from app.providers.base import MusicProvider, SearchResult

logger = logging.getLogger(__name__)

MB_BASE = "https://musicbrainz.org/ws/2"
MIN_REQUEST_INTERVAL = 1.0


class MusicBrainzProvider(MusicProvider):
    name = "MusicBrainz"

    def __init__(self, user_agent: str = "DJFlowStudio/1.0 (contact@djflow.local)"):
        self._user_agent = user_agent
        self._last_request = 0.0

    def credential_error(self) -> Optional[str]:
        return None

    def is_available(self) -> bool:
        return True

    def _request(self, path: str, params: dict) -> Optional[dict]:
        elapsed = time.time() - self._last_request
        if elapsed < MIN_REQUEST_INTERVAL:
            time.sleep(MIN_REQUEST_INTERVAL - elapsed)
        url = f"{MB_BASE}{path}"
        params = dict(params)
        params.setdefault("fmt", "json")
        headers = {"User-Agent": self._user_agent}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=15)
            self._last_request = time.time()
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.warning("MusicBrainz request failed: %s", e)
            return None

    def search(self, query: str, limit: int = 20) -> List[SearchResult]:
        if not query.strip():
            return []
        data = self._request("/recording", {"query": query, "limit": limit})
        return self._parse_recordings(data)

    def lookup_recording(self, mbid: str) -> Optional[dict]:
        return self._request(f"/recording/{mbid}", {"inc": "artists releases genres"})

    def search_artist(self, artist: str, limit: int = 20) -> List[SearchResult]:
        if not artist.strip():
            return []
        data = self._request("/recording", {"query": f"artist:{artist}", "limit": limit})
        return self._parse_recordings(data)

    def search_genre(self, genre: str, limit: int = 20) -> List[SearchResult]:
        if not genre.strip():
            return []
        data = self._request("/recording", {"query": f"genre:{genre}", "limit": limit})
        return self._parse_recordings(data)

    def enrich_metadata(self, title: str, artist: str = "") -> Optional[dict]:
        query = title
        if artist:
            query = f"{title} AND artist:{artist}"
        data = self._request("/recording", {"query": query, "limit": 5})
        recordings = (data or {}).get("recordings", [])
        if not recordings:
            return None
        rec = recordings[0]
        result = {
            "title": rec.get("title"),
            "artist": None,
            "album": None,
            "genre": None,
            "year": None,
        }
        credits = rec.get("artist-credit") or []
        if credits:
            names = [c.get("name", "") for c in credits if isinstance(c, dict)]
            result["artist"] = " & ".join(filter(None, names)) or None
        releases = rec.get("releases") or []
        if releases:
            result["album"] = releases[0].get("title")
            date = releases[0].get("date")
            if date:
                result["year"] = str(date)[:4]
        genres = rec.get("genres") or []
        if genres:
            top = sorted(genres, key=lambda g: g.get("count", 0), reverse=True)
            result["genre"] = top[0].get("name")
        return result

    def _parse_recordings(self, data: Optional[dict]) -> List[SearchResult]:
        results: List[SearchResult] = []
        if not data:
            return results
        for rec in data.get("recordings", []):
            try:
                artist = None
                credits = rec.get("artist-credit") or []
                if credits:
                    names = [c.get("name", "") for c in credits if isinstance(c, dict)]
                    artist = " & ".join(filter(None, names)) or None
                album = None
                releases = rec.get("releases") or []
                if releases:
                    album = releases[0].get("title")
                duration = rec.get("length")
                results.append(SearchResult(
                    source="MusicBrainz",
                    track_id=rec.get("id", ""),
                    title=rec.get("title") or "Unknown",
                    artist=artist or "Unknown",
                    album=album,
                    duration_seconds=float(duration) / 1000.0 if duration else None,
                    source_url=f"https://musicbrainz.org/recording/{rec.get('id', '')}" if rec.get("id") else None,
                    download_available=False,
                ))
            except Exception as e:
                logger.debug("Skipping malformed MusicBrainz recording: %s", e)
        return results
