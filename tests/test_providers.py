import json
from unittest.mock import patch, MagicMock

import pytest

from app.providers.jamendo import JamendoProvider
from app.providers.musicbrainz import MusicBrainzProvider


class MockResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")


JAMENDO_SAMPLE = {
    "headers": {"status": "success", "code": 0, "error_message": "", "warnings": ""},
    "results": [
        {
            "id": "12345",
            "name": "Test Track",
            "artist_name": "Test Artist",
            "album_name": "Test Album",
            "duration": 180,
            "image": "https://img.jamendo.com/cover.jpg",
            "shareurl": "https://www.jamendo.com/track/12345",
            "audio": "https://mp3l.jamendo.com/?trackid=12345&format=mp32",
            "download_url": "https://mp3d.jamendo.com/?trackid=12345",
            "releasedate": "2023-05-15",
            "musicinfo": {"tags": {"genres": ["Electronic"]}},
            "licenses": [{"name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"}],
        }
    ],
}


class TestJamendoProvider:
    def test_credential_error_when_no_client_id(self):
        p = JamendoProvider("")
        assert p.credential_error() is not None
        assert p.is_available() is False

    def test_no_credential_error_when_configured(self):
        p = JamendoProvider("test-client-id")
        assert p.credential_error() is None
        assert p.is_available() is True

    def test_search_empty_query_returns_empty(self):
        p = JamendoProvider("id")
        assert p.search("") == []
        assert p.search("   ") == []

    @patch("app.providers.jamendo.requests.get")
    def test_search_parses_results(self, mock_get):
        mock_get.return_value = MockResponse(200, JAMENDO_SAMPLE)
        p = JamendoProvider("test-id")
        results = p.search("test")
        assert len(results) == 1
        r = results[0]
        assert r.title == "Test Track"
        assert r.artist == "Test Artist"
        assert r.album == "Test Album"
        assert r.genre == "Electronic"
        assert r.duration_seconds == 180.0
        assert r.download_available is True
        assert r.preview_url is not None
        assert r.license_name == "CC BY 4.0"
        assert r.year == "2023"

    @patch("app.providers.jamendo.requests.get")
    def test_search_handles_api_failure(self, mock_get):
        mock_get.return_value = MockResponse(200, {"headers": {"status": "failed", "error_message": "bad"}})
        p = JamendoProvider("id")
        assert p.search("test") == []

    @patch("app.providers.jamendo.requests.get")
    def test_search_handles_network_error(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("no network")
        p = JamendoProvider("id")
        assert p.search("test") == []

    @patch("app.providers.jamendo.requests.get")
    def test_credential_error_blocks_request(self, mock_get):
        p = JamendoProvider("")
        results = p.search("test")
        mock_get.assert_not_called()
        assert results == []

    @patch("app.providers.jamendo.requests.get")
    def test_search_artist(self, mock_get):
        mock_get.return_value = MockResponse(200, JAMENDO_SAMPLE)
        p = JamendoProvider("id")
        results = p.search_artist("Test Artist")
        assert len(results) == 1
        assert results[0].artist == "Test Artist"

    @patch("app.providers.jamendo.requests.get")
    def test_search_genre(self, mock_get):
        mock_get.return_value = MockResponse(200, JAMENDO_SAMPLE)
        p = JamendoProvider("id")
        results = p.search_genre("Electronic")
        assert len(results) == 1
        assert results[0].genre == "Electronic"

    def test_missing_metadata_unknown(self):
        data = {"headers": {"status": "success"}, "results": [{"id": "1", "name": ""}]}
        p = JamendoProvider("id")
        results = p._parse_tracks(data)
        assert results[0].title == "Unknown"
        assert results[0].artist == "Unknown"
        assert results[0].download_available is False


MB_RECORDING_SAMPLE = {
    "recordings": [
        {
            "id": "mbid-123",
            "title": "MB Track",
            "length": 240000,
            "artist-credit": [{"name": "MB Artist"}],
            "releases": [{"title": "MB Album", "date": "2022-01-01"}],
            "genres": [{"name": "rock", "count": 5}],
        }
    ]
}


class TestMusicBrainzProvider:
    def test_is_always_available(self):
        p = MusicBrainzProvider()
        assert p.is_available() is True
        assert p.credential_error() is None

    @patch("app.providers.musicbrainz.requests.get")
    def test_search_parses_recordings(self, mock_get):
        mock_get.return_value = MockResponse(200, MB_RECORDING_SAMPLE)
        p = MusicBrainzProvider("TestAgent/1.0")
        results = p.search("mb track")
        assert len(results) == 1
        r = results[0]
        assert r.title == "MB Track"
        assert r.artist == "MB Artist"
        assert r.album == "MB Album"
        assert r.duration_seconds == 240.0
        assert r.download_available is False
        assert "musicbrainz.org" in r.source_url

    @patch("app.providers.musicbrainz.requests.get")
    def test_search_empty_query(self, mock_get):
        p = MusicBrainzProvider()
        assert p.search("") == []
        mock_get.assert_not_called()

    @patch("app.providers.musicbrainz.requests.get")
    def test_enrich_metadata(self, mock_get):
        mock_get.return_value = MockResponse(200, MB_RECORDING_SAMPLE)
        p = MusicBrainzProvider("Agent/1.0")
        meta = p.enrich_metadata("MB Track", "MB Artist")
        assert meta is not None
        assert meta["title"] == "MB Track"
        assert meta["artist"] == "MB Artist"
        assert meta["album"] == "MB Album"
        assert meta["year"] == "2022"
        assert meta["genre"] == "rock"

    @patch("app.providers.musicbrainz.requests.get")
    def test_404_returns_none(self, mock_get):
        mock_get.return_value = MockResponse(404, {})
        p = MusicBrainzProvider("Agent/1.0")
        assert p.lookup_recording("bad-mbid") is None

    @patch("app.providers.musicbrainz.requests.get")
    def test_network_error_returns_empty(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError("fail")
        p = MusicBrainzProvider("Agent/1.0")
        assert p.search("test") == []
