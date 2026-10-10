import hashlib
import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest

from app.services.download_service import (
    DownloadItem,
    DownloadManager,
    DownloadHistory,
    DownloadStatus,
)


@pytest.fixture
def history_file(tmp_path):
    return str(tmp_path / "history.json")


@pytest.fixture
def manager(history_file):
    hist = DownloadHistory(history_file)
    return DownloadManager(history=hist)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MockStreamResponse:
    def __init__(self, content: bytes, status_code=200, content_length=None, accept_ranges="bytes"):
        self._content = content
        self.status_code = status_code
        self.headers = {
            "Content-Length": str(content_length or len(content)),
            "Accept-Ranges": accept_ranges,
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=8192):
        for i in range(0, len(self._content), chunk_size):
            yield self._content[i:i + chunk_size]


class TestDownloadHistory:
    def test_load_missing_file_returns_empty(self, tmp_path):
        h = DownloadHistory(str(tmp_path / "nope.json"))
        assert h.load() == []

    def test_load_corrupt_file_returns_empty(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json{{{")
        h = DownloadHistory(str(p))
        assert h.load() == []

    def test_save_and_load(self, history_file):
        h = DownloadHistory(history_file)
        items = [{"url": "http://x", "status": "completed", "destination": "/tmp/x.mp3"}]
        h.save(items)
        assert h.load() == items

    def test_is_url_downloaded(self, history_file):
        h = DownloadHistory(history_file)
        h.save([{"url": "http://x", "status": "completed", "destination": "/tmp/x.mp3"}])
        assert h.is_url_downloaded("http://x") == "/tmp/x.mp3"
        assert h.is_url_downloaded("http://y") is None


class TestDownloadManager:
    def test_add_creates_queue_item(self, manager):
        manager._start_worker = lambda: None
        item = DownloadItem(url="http://test/a.mp3", destination="/tmp/a.mp3", title="A")
        assert manager.add(item) is True
        assert item in manager.queue

    def test_add_duplicate_url_marks_completed(self, manager, history_file):
        manager._history.save([
            {"url": "http://dup", "status": DownloadStatus.COMPLETED.value, "destination": "/tmp/dup.mp3"}
        ])
        item = DownloadItem(url="http://dup", destination="/tmp/dup2.mp3")
        assert manager.add(item) is False
        assert item.status == DownloadStatus.COMPLETED.value

    @patch("app.services.download_service.requests.Session.get")
    def test_download_saves_file(self, mock_get, tmp_path):
        content = b"fake audio content" * 100
        mock_get.return_value = MockStreamResponse(content)
        hist = DownloadHistory(str(tmp_path / "h.json"))
        mgr = DownloadManager(history=hist)
        dest = str(tmp_path / "out" / "song.mp3")
        item = DownloadItem(url="http://test/song.mp3", destination=dest, title="song")
        mgr.add(item)
        time.sleep(1.5)
        assert os.path.exists(dest)
        with open(dest, "rb") as f:
            assert f.read() == content
        assert item.status == DownloadStatus.COMPLETED.value
        assert item.progress == 100.0

    @patch("app.services.download_service.requests.Session.get")
    def test_download_uses_temp_file_then_moves(self, mock_get, tmp_path):
        content = b"data" * 50
        mock_get.return_value = MockStreamResponse(content)
        hist = DownloadHistory(str(tmp_path / "h.json"))
        mgr = DownloadManager(history=hist)
        dest = str(tmp_path / "song.mp3")
        item = DownloadItem(url="http://x", destination=dest)
        mgr.add(item)
        time.sleep(1.5)
        assert os.path.exists(dest)
        assert not os.path.exists(dest + ".part")

    @patch("app.services.download_service.requests.Session.get")
    def test_download_verifies_fails_on_empty(self, mock_get, tmp_path):
        mock_get.return_value = MockStreamResponse(b"")
        hist = DownloadHistory(str(tmp_path / "h.json"))
        mgr = DownloadManager(history=hist)
        dest = str(tmp_path / "empty.mp3")
        item = DownloadItem(url="http://x", destination=dest)
        mgr.add(item)
        time.sleep(1.5)
        assert item.status == DownloadStatus.FAILED.value
        assert not os.path.exists(dest)

    @patch("app.services.download_service.requests.Session.get")
    def test_download_unique_destination_on_conflict(self, mock_get, tmp_path):
        dest = tmp_path / "song.mp3"
        dest.write_bytes(b"existing")
        content = b"new content" * 20
        mock_get.return_value = MockStreamResponse(content)
        hist = DownloadHistory(str(tmp_path / "h.json"))
        mgr = DownloadManager(history=hist)
        item = DownloadItem(url="http://x", destination=str(dest))
        mgr.add(item)
        time.sleep(1.5)
        expected = str(tmp_path / "song (1).mp3")
        assert os.path.exists(expected)
        assert item.destination == expected

    @patch("app.services.download_service.requests.Session.get")
    def test_download_persists_history(self, mock_get, tmp_path):
        content = b"abc" * 10
        mock_get.return_value = MockStreamResponse(content)
        hist = DownloadHistory(str(tmp_path / "h.json"))
        mgr = DownloadManager(history=hist)
        dest = str(tmp_path / "song.mp3")
        item = DownloadItem(url="http://x", destination=dest, title="t")
        mgr.add(item)
        time.sleep(1.5)
        records = hist.load()
        assert any(r["url"] == "http://x" and r["status"] == DownloadStatus.COMPLETED.value for r in records)

    @patch("app.services.download_service.requests.Session.get")
    def test_download_network_failure_retries(self, mock_get, tmp_path):
        import requests
        mock_get.side_effect = requests.ConnectionError("fail")
        hist = DownloadHistory(str(tmp_path / "h.json"))
        mgr = DownloadManager(history=hist)
        dest = str(tmp_path / "fail.mp3")
        item = DownloadItem(url="http://x", destination=dest, max_retries=1)
        mgr.add(item)
        time.sleep(2.0)
        assert item.status == DownloadStatus.FAILED.value
        assert "fail" in (item.error or "").lower()
        assert mock_get.call_count >= 2

    def test_cancel_all(self, manager):
        manager.add(DownloadItem(url="http://a", destination="/tmp/a"))
        manager.add(DownloadItem(url="http://b", destination="/tmp/b"))
        manager.cancel_all()
        assert all(i.status == DownloadStatus.CANCELLED.value for i in manager.queue) or len(manager.queue) == 0
