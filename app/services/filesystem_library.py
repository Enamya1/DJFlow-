import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from app.services import analysis_service
from app.services.metadata_service import extract_metadata
from app.utils.file_utils import scan_audio_files, is_supported_audio

logger = logging.getLogger(__name__)


@dataclass
class TrackInfo:
    file_path: str
    title: str = ""
    artist: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    duration_seconds: Optional[float] = None
    bpm: Optional[float] = None
    musical_key: Optional[str] = None
    camelot_key: Optional[str] = None
    bitrate: Optional[int] = None
    sample_rate: Optional[int] = None
    file_format: Optional[str] = None
    artwork_path: Optional[str] = None
    rating: int = 0
    favorite: bool = False
    user_tags: str = ""
    year: Optional[str] = None
    energy: Optional[float] = None
    analyzed: bool = False
    bpm_confidence: Optional[float] = None
    key_confidence: Optional[float] = None
    bpm_half: Optional[float] = None
    bpm_double: Optional[float] = None

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return asdict(self)


def scan_library(folder: str, recursive: bool = True) -> List[TrackInfo]:
    tracks: List[TrackInfo] = []
    if not folder or not os.path.isdir(folder):
        return tracks
    files = scan_audio_files(folder, recursive=recursive)
    for path in files:
        try:
            tracks.append(load_track(path))
        except Exception as e:
            logger.debug("Skipping %s: %s", path, e)
    return tracks


def load_track(file_path: str) -> TrackInfo:
    meta = extract_metadata(file_path)
    track = TrackInfo(
        file_path=file_path,
        title=meta.title,
        artist=meta.artist,
        album=meta.album,
        genre=meta.genre,
        duration_seconds=meta.duration_seconds,
        bitrate=meta.bitrate,
        sample_rate=meta.sample_rate,
        file_format=meta.file_format,
        artwork_path=meta.artwork_path,
        year=meta.date_modified,
    )

    sidecar = analysis_service.load_sidecar(file_path)
    if sidecar is not None:
        track.analyzed = True
        track.bpm = sidecar.bpm
        track.bpm_confidence = sidecar.bpm_confidence
        track.bpm_half = sidecar.bpm_half
        track.bpm_double = sidecar.bpm_double
        track.musical_key = sidecar.musical_key
        track.camelot_key = sidecar.camelot_key
        track.key_confidence = sidecar.key_confidence
        track.energy = sidecar.energy

    return track
