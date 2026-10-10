import hashlib
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".aiff", ".aif",
}

SUPPORTED_EXTENSIONS = sorted(SUPPORTED_FORMATS)


def get_file_extension(file_path: str) -> str:
    return Path(file_path).suffix.lower()


def is_supported_audio(file_path: str) -> bool:
    return get_file_extension(file_path) in SUPPORTED_FORMATS


def format_label(file_path: str) -> Optional[str]:
    ext = get_file_extension(file_path)
    mapping = {
        ".mp3": "MP3",
        ".wav": "WAV",
        ".flac": "FLAC",
        ".aac": "AAC",
        ".m4a": "M4A",
        ".ogg": "OGG",
        ".aiff": "AIFF",
        ".aif": "AIFF",
    }
    return mapping.get(ext)


def validate_path(file_path: str) -> bool:
    if not file_path:
        return False
    p = Path(file_path)
    try:
        if not p.exists():
            return False
        if not p.is_file():
            return False
        if not os.access(str(p), os.R_OK):
            return False
        return True
    except (OSError, ValueError):
        return False


def validate_directory(dir_path: str) -> bool:
    if not dir_path:
        return False
    p = Path(dir_path)
    try:
        return p.exists() and p.is_dir() and os.access(str(p), os.R_OK)
    except (OSError, ValueError):
        return False


def scan_audio_files(directory: str, recursive: bool = True) -> List[str]:
    if not validate_directory(directory):
        return []
    result = []
    root = Path(directory)
    iterator = root.rglob("*") if recursive else root.glob("*")
    for entry in iterator:
        try:
            if entry.is_file() and is_supported_audio(str(entry)):
                result.append(str(entry))
        except (OSError, PermissionError) as e:
            logger.warning("Skipping unreadable entry %s: %s", entry, e)
    return result


def compute_file_hash(file_path: str, chunk_size: int = 65536) -> Optional[str]:
    if not validate_path(file_path):
        return None
    try:
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                sha.update(chunk)
        return sha.hexdigest()
    except (OSError, IOError) as e:
        logger.warning("Failed to hash %s: %s", file_path, e)
        return None


def filename_without_extension(file_path: str) -> str:
    return Path(file_path).stem


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "--:--"
    try:
        total = int(round(float(seconds)))
    except (TypeError, ValueError):
        return "--:--"
    if total < 0:
        total = 0
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"
