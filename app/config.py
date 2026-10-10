import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("data") / "config.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "music_library_folder": "",
    "download_folder": "",
    "download_into_library": False,
    "organize_after_download": True,
    "folder_template": "{genre}/{artist}",
    "file_template": "{title} - {artist}",
    "unknown_bpm_fallback": "Unknown BPM",
    "unknown_key_fallback": "Unknown Key",
    "write_metadata_to_tags": False,
    "create_sidecar_files": True,
    "jamendo_client_id": "",
    "musicbrainz_user_agent": "DJFlowStudio/1.0 (contact@djflow.local)",
    "live_search": True,
    "live_search_debounce_ms": 400,
    "default_download_category": "",
}


class AppConfig:
    _instance: Optional["AppConfig"] = None
    _lock = threading.Lock()

    def __init__(self, path: Optional[str] = None):
        self._path = Path(path) if path else CONFIG_PATH
        self._data: Dict[str, Any] = dict(DEFAULT_CONFIG)
        self._write_lock = threading.Lock()
        self._load()

    @classmethod
    def instance(cls) -> "AppConfig":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    def _load(self) -> None:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    merged = dict(DEFAULT_CONFIG)
                    merged.update(loaded)
                    self._data = merged
                    logger.info("Loaded config from %s", self._path)
                    return
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not load config %s: %s — using defaults.", self._path, e)
        self._data = dict(DEFAULT_CONFIG)

    def save(self) -> None:
        try:
            with self._write_lock:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self._path.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=2, ensure_ascii=False)
                os.replace(tmp, self._path)
        except OSError as e:
            logger.error("Failed to save config: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def update(self, values: Dict[str, Any]) -> None:
        self._data.update(values)
        self.save()

    def as_dict(self) -> Dict[str, Any]:
        return dict(self._data)
