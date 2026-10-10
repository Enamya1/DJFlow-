import hashlib
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional

import requests

from app.services.folder_templates import unique_destination

logger = logging.getLogger(__name__)

HISTORY_PATH = Path("data") / "download_history.json"


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DownloadItem:
    url: str
    destination: str
    title: str = ""
    artist: str = ""
    source: str = ""
    status: str = DownloadStatus.QUEUED.value
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed: float = 0.0
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    supports_resume: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class DownloadHistory:
    def __init__(self, path: Optional[str] = None):
        self._path = Path(path) if path else HISTORY_PATH

    def load(self) -> List[dict]:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Download history corrupted, resetting: %s", e)
        return []

    def save(self, items: List[dict]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
            os.replace(tmp, self._path)
        except OSError as e:
            logger.error("Failed to save download history: %s", e)

    def is_url_downloaded(self, url: str) -> Optional[str]:
        for item in self.load():
            if item.get("url") == url and item.get("status") == DownloadStatus.COMPLETED.value:
                return item.get("destination")
        return None


class DownloadManager:
    def __init__(self, history: Optional[DownloadHistory] = None):
        self._history = history or DownloadHistory()
        self._queue: List[DownloadItem] = []
        self._lock = threading.Lock()
        self._current: Optional[DownloadItem] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._progress_cb: Optional[Callable[[DownloadItem], None]] = None
        self._finished_cb: Optional[Callable[[DownloadItem], None]] = None
        self._session = requests.Session()

    @property
    def queue(self) -> List[DownloadItem]:
        with self._lock:
            return list(self._queue)

    @property
    def current(self) -> Optional[DownloadItem]:
        return self._current

    def set_callbacks(self, progress_cb=None, finished_cb=None) -> None:
        self._progress_cb = progress_cb
        self._finished_cb = finished_cb

    def add(self, item: DownloadItem) -> bool:
        existing = self._history.is_url_downloaded(item.url)
        if existing:
            logger.info("URL already downloaded to %s", existing)
            item.destination = existing
            item.status = DownloadStatus.COMPLETED.value
            if self._finished_cb:
                self._finished_cb(item)
            return False

        with self._lock:
            self._queue.append(item)
        self._start_worker()
        return True

    def cancel_all(self) -> None:
        self._stop_event.set()
        with self._lock:
            for item in self._queue:
                item.status = DownloadStatus.CANCELLED.value
        self._queue.clear()

    def pause(self) -> None:
        self._pause_event.set()

    def resume(self) -> None:
        self._pause_event.clear()

    def _start_worker(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if not self._queue:
                    break
                item = self._queue.pop(0)
            self._current = item
            try:
                self._download(item)
            except Exception as e:
                item.status = DownloadStatus.FAILED.value
                item.error = str(e)
                logger.exception("Download failed for %s", item.url)
            finally:
                self._persist(item)
                self._current = None
                if self._finished_cb:
                    self._finished_cb(item)

    def _download(self, item: DownloadItem) -> None:
        item.status = DownloadStatus.DOWNLOADING.value
        dest_path = Path(item.destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")

        headers = {}
        resume_from = 0
        if item.supports_resume and tmp_path.exists():
            resume_from = tmp_path.stat().st_size
            headers["Range"] = f"bytes={resume_from}-"

        for attempt in range(item.max_retries + 1):
            if self._stop_event.is_set():
                item.status = DownloadStatus.CANCELLED.value
                return
            try:
                with self._session.get(item.url, headers=headers, stream=True, timeout=30) as resp:
                    resp.raise_for_status()
                    item.total_bytes = int(resp.headers.get("Content-Length", 0)) + resume_from
                    item.supports_resume = resp.headers.get("Accept-Ranges") == "bytes"

                    mode = "ab" if resume_from > 0 else "wb"
                    with open(tmp_path, mode) as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if self._stop_event.is_set():
                                item.status = DownloadStatus.CANCELLED.value
                                return
                            while self._pause_event.is_set():
                                if self._stop_event.is_set():
                                    item.status = DownloadStatus.CANCELLED.value
                                    return
                                time.sleep(0.2)
                            if chunk:
                                f.write(chunk)
                                item.downloaded_bytes += len(chunk)
                                if item.total_bytes:
                                    item.progress = min(100.0, item.downloaded_bytes / item.total_bytes * 100)
                                if self._progress_cb:
                                    self._progress_cb(item)
                break
            except requests.RequestException as e:
                item.retries += 1
                item.error = str(e)
                if attempt >= item.max_retries:
                    item.status = DownloadStatus.FAILED.value
                    return
                time.sleep(min(2 ** attempt, 10))

        if not self._verify(tmp_path):
            item.status = DownloadStatus.FAILED.value
            item.error = "File verification failed"
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
            return

        final_dest = unique_destination(str(dest_path))
        os.replace(tmp_path, final_dest)
        item.destination = final_dest
        item.status = DownloadStatus.COMPLETED.value
        item.progress = 100.0
        item.completed_at = time.time()

    def _verify(self, path: Path) -> bool:
        try:
            if not path.exists():
                return False
            size = path.stat().st_size
            if size == 0:
                return False
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
            item = self._current
            if item and item.total_bytes and size != item.total_bytes:
                return False
            return True
        except OSError:
            return False

    def _persist(self, item: DownloadItem) -> None:
        history = self._history.load()
        history.append(item.to_dict())
        history = history[-500:]
        self._history.save(history)
