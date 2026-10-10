import logging
from pathlib import Path
from typing import Optional, Tuple

from mutagen import File as MutagenFile
from mutagen.flac import FLAC, Picture
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4
from mutagen.oggvorbis import OggVorbis
from mutagen.asf import ASF

from app.database.models import Track
from app.utils.file_utils import (
    filename_without_extension,
    format_label,
    get_file_extension,
)

logger = logging.getLogger(__name__)

ARTWORK_DIR = Path("data/artwork")


def _safe_str(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    try:
        text = str(value).strip()
        return text if text else None
    except Exception:
        return None


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        if not value:
            return None
        value = value[0]
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_artwork(audio, file_path: str) -> Optional[str]:
    data = None
    mime = None

    if isinstance(audio, MP3):
        apic_keys = [k for k in audio.tags.keys() if k.startswith("APIC:")] if audio.tags else []
        for key in apic_keys:
            frame = audio.tags[key]
            data = frame.data
            mime = frame.mime
            break
    elif isinstance(audio, FLAC):
        if audio.pictures:
            pic = audio.pictures[0]
            data = pic.data
            mime = pic.mime
    elif isinstance(audio, MP4):
        if "covr" in audio:
            cover = audio["covr"][0]
            data = bytes(cover)
            mime = "image/png" if getattr(cover, "imageformat", None) == 12 else "image/jpeg"
    elif isinstance(audio, OggVorbis):
        metadata_block_pictures = audio.get("metadata_block_picture", [])
        if metadata_block_pictures:
            try:
                import base64
                pic = Picture(base64.b64decode(metadata_block_pictures[0]))
                data = pic.data
                mime = pic.mime
            except Exception:
                pass

    if not data:
        return None

    try:
        ARTWORK_DIR.mkdir(parents=True, exist_ok=True)
        stem = Path(file_path).stem
        ext = ".png" if mime and "png" in mime else ".jpg"
        artwork_path = ARTWORK_DIR / f"{stem}{ext}"
        if artwork_path.exists():
            try:
                idx = 1
                while True:
                    candidate = ARTWORK_DIR / f"{stem}_{idx}{ext}"
                    if not candidate.exists():
                        artwork_path = candidate
                        break
                    idx += 1
            except Exception:
                pass
        artwork_path.write_bytes(data)
        return str(artwork_path)
    except Exception as e:
        logger.warning("Failed to save artwork for %s: %s", file_path, e)
        return None


def extract_metadata(file_path: str) -> Track:
    """Extract metadata from an audio file. Never fabricates values."""
    track = Track(
        file_path=file_path,
        title=filename_without_extension(file_path),
        file_format=format_label(file_path),
    )

    try:
        audio = MutagenFile(file_path)
    except Exception as e:
        logger.warning("Mutagen could not read %s: %s", file_path, e)
        return track

    if audio is None:
        logger.warning("No audio stream recognized for %s", file_path)
        return track

    try:
        info = getattr(audio, "info", None)
        if info is not None:
            track.duration_seconds = _safe_float(getattr(info, "length", None))
        if track.duration_seconds is None:
            track.duration_seconds = _safe_float(getattr(audio, "length", None))
    except Exception:
        track.duration_seconds = None

    try:
        info = getattr(audio, "info", None)
        if info is not None:
            track.bitrate = _safe_int(getattr(info, "bitrate", None))
            if track.bitrate and track.bitrate > 1000:
                track.bitrate = track.bitrate // 1000
            track.sample_rate = _safe_int(getattr(info, "sample_rate", None))
    except Exception:
        pass

    tags = getattr(audio, "tags", None)

    if tags is not None:
        track.title = _safe_str(tags.get("title")) or track.title
        track.artist = _safe_str(tags.get("artist"))
        track.album = _safe_str(tags.get("album"))
        track.genre = _safe_str(tags.get("genre"))

        bpm = _safe_float(tags.get("bpm"))
        if bpm is None:
            bpm = _safe_float(tags.get("BPM"))
        track.bpm = bpm

        track.musical_key = _safe_str(tags.get("key"))
        if track.musical_key is None:
            track.musical_key = _safe_str(tags.get("initialkey"))

        year = _safe_str(tags.get("date")) or _safe_str(tags.get("year"))
        if year:
            track.date_modified = year[:4]

    track.artwork_path = _extract_artwork(audio, file_path)

    if not track.title:
        track.title = filename_without_extension(file_path)

    return track


def is_file_readable(file_path: str) -> bool:
    try:
        audio = MutagenFile(file_path)
        return audio is not None
    except Exception:
        return False
