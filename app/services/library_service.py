import logging
import threading
from typing import Callable, List, Optional

from app.database.migrations import Database
from app.database.models import Track, ImportResult
from app.database.repository import TrackRepository
from app.services.metadata_service import extract_metadata, is_file_readable
from app.utils.file_utils import (
    compute_file_hash,
    scan_audio_files,
    validate_path,
    is_supported_audio,
)

logger = logging.getLogger(__name__)


class LibraryService:
    def __init__(self, db: Database):
        self._db = db
        self._tracks = TrackRepository(db)

    @property
    def tracks(self) -> TrackRepository:
        return self._tracks

    def import_file(self, file_path: str) -> ImportResult:
        result = ImportResult()
        result, _ = self._import_one(file_path, result)
        return result

    def import_files(self, file_paths: List[str],
                     progress_cb: Optional[Callable[[int, int, str], None]] = None,
                     cancel_event: Optional[threading.Event] = None) -> ImportResult:
        result = ImportResult()
        total = len(file_paths)
        for i, path in enumerate(file_paths):
            if cancel_event and cancel_event.is_set():
                logger.info("Import cancelled by user.")
                break
            result, _ = self._import_one(path, result)
            if progress_cb:
                try:
                    progress_cb(i + 1, total, path)
                except Exception:
                    pass
        return result

    def _import_one(self, file_path: str, result: ImportResult) -> tuple:
        if not is_supported_audio(file_path):
            result.skipped_duplicates += 1
            return result, None

        if not validate_path(file_path):
            result.unreadable.append(file_path)
            result.failed += 1
            return result, None

        if self._tracks.path_exists(file_path):
            result.skipped_duplicates += 1
            return result, None

        try:
            if not is_file_readable(file_path):
                result.unreadable.append(file_path)
                result.failed += 1
                return result, None
        except Exception as e:
            result.errors.append(f"{file_path}: {e}")
            result.unreadable.append(file_path)
            result.failed += 1
            return result, None

        try:
            track = extract_metadata(file_path)
        except Exception as e:
            result.errors.append(f"{file_path}: metadata error: {e}")
            result.failed += 1
            return result, None

        if track.file_hash is None:
            track.file_hash = compute_file_hash(file_path)

        if track.file_hash and self._tracks.hash_exists(track.file_hash):
            result.skipped_duplicates += 1
            return result, None

        try:
            track_id = self._tracks.insert(track)
            if track_id is None:
                result.skipped_duplicates += 1
            else:
                result.imported += 1
        except Exception as e:
            result.errors.append(f"{file_path}: db error: {e}")
            result.failed += 1

        return result, None

    def import_folder(self, directory: str, recursive: bool = True,
                      progress_cb: Optional[Callable[[int, int, str], None]] = None,
                      cancel_event: Optional[threading.Event] = None) -> ImportResult:
        files = scan_audio_files(directory, recursive=recursive)
        return self.import_files(files, progress_cb=progress_cb, cancel_event=cancel_event)

    def rescan(self, progress_cb=None, cancel_event=None) -> ImportResult:
        existing_paths = self._tracks.all_paths()
        result = ImportResult()
        total = len(existing_paths)
        for i, path in enumerate(existing_paths):
            if cancel_event and cancel_event.is_set():
                break
            try:
                if validate_path(path) and is_file_readable(path):
                    track = extract_metadata(path)
                    existing = self._tracks.get_by_path(path)
                    if existing:
                        track.id = existing.id
                        track.rating = existing.rating
                        track.favorite = existing.favorite
                        track.user_tags = existing.user_tags
                        track.date_added = existing.date_added
                        self._tracks.update_metadata(track)
                        result.imported += 1
                else:
                    result.unreadable.append(path)
                    result.failed += 1
            except Exception as e:
                result.errors.append(f"{path}: {e}")
                result.failed += 1
            if progress_cb:
                try:
                    progress_cb(i + 1, total, path)
                except Exception:
                    pass
        return result


class BackgroundScanner:
    def __init__(self, service: LibraryService):
        self._service = service
        self._cancel_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def cancel(self) -> None:
        self._cancel_event.set()

    def scan_folder(self, directory: str, recursive: bool = True,
                    progress_cb=None, finished_cb=None) -> None:
        if self.is_running():
            logger.warning("A scan is already in progress.")
            return

        self._cancel_event.clear()

        def worker():
            try:
                result = self._service.import_folder(
                    directory, recursive=recursive,
                    progress_cb=progress_cb, cancel_event=self._cancel_event,
                )
            except Exception as e:
                logger.exception("Background scan failed")
                result = ImportResult(errors=[str(e)])
            if finished_cb:
                try:
                    finished_cb(result)
                except Exception:
                    pass

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def scan_files(self, file_paths, progress_cb=None, finished_cb=None) -> None:
        if self.is_running():
            logger.warning("A scan is already in progress.")
            return

        self._cancel_event.clear()

        def worker():
            try:
                result = self._service.import_files(
                    file_paths, progress_cb=progress_cb, cancel_event=self._cancel_event,
                )
            except Exception as e:
                logger.exception("Background file import failed")
                result = ImportResult(errors=[str(e)])
            if finished_cb:
                try:
                    finished_cb(result)
                except Exception:
                    pass

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def rescan_library(self, progress_cb=None, finished_cb=None) -> None:
        if self.is_running():
            return

        self._cancel_event.clear()

        def worker():
            try:
                result = self._service.rescan(
                    progress_cb=progress_cb, cancel_event=self._cancel_event,
                )
            except Exception as e:
                logger.exception("Rescan failed")
                result = ImportResult(errors=[str(e)])
            if finished_cb:
                try:
                    finished_cb(result)
                except Exception:
                    pass

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def join(self, timeout: Optional[float] = None) -> None:
        if self._thread:
            self._thread.join(timeout=timeout)
