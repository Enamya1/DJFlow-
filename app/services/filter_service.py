import logging
from typing import List, Optional

from app.services.filesystem_library import TrackInfo

logger = logging.getLogger(__name__)

CAMELOT_COMPATIBLE = {
    1: [12, 1, 2], 2: [1, 2, 3], 3: [2, 3, 4], 4: [3, 4, 5],
    5: [4, 5, 6], 6: [5, 6, 7], 7: [6, 7, 8], 8: [7, 8, 9],
    9: [8, 9, 10], 10: [9, 10, 11], 11: [10, 11, 12], 12: [11, 12, 1],
}


def camelot_number(camelot: Optional[str]) -> Optional[int]:
    if not camelot:
        return None
    try:
        return int(camelot[:-1])
    except (ValueError, IndexError):
        return None


def is_camelot_compatible(camelot_a: Optional[str], camelot_b: Optional[str]) -> bool:
    na = camelot_number(camelot_a)
    nb = camelot_number(camelot_b)
    if na is None or nb is None:
        return False
    if camelot_a and camelot_b and camelot_a[-1] != camelot_b[-1]:
        return False
    return nb in CAMELOT_COMPATIBLE.get(na, [])


def bpm_match(bpm_a: Optional[float], bpm_b: Optional[float], tolerance: float = 6.0,
              allow_half_double: bool = True) -> bool:
    if bpm_a is None or bpm_b is None:
        return False
    if abs(bpm_a - bpm_b) <= tolerance:
        return True
    if allow_half_double:
        if abs(bpm_a - bpm_b / 2) <= tolerance:
            return True
        if abs(bpm_a - bpm_b * 2) <= tolerance:
            return True
        if abs(bpm_b - bpm_a / 2) <= tolerance:
            return True
        if abs(bpm_b - bpm_a * 2) <= tolerance:
            return True
    return False


class FilterCriteria:
    def __init__(self, bpm_min=None, bpm_max=None, musical_key=None, camelot_key=None,
                 genre=None, artist=None, album=None, duration_min=None, duration_max=None,
                 file_format=None, energy_min=None, energy_max=None, favorite=None,
                 rating_min=None, missing_metadata=None, analyzed=None,
                 compatible_camelot=None, bpm_match_target=None, bpm_tolerance=6.0,
                 allow_half_double=True):
        self.bpm_min = bpm_min
        self.bpm_max = bpm_max
        self.musical_key = musical_key
        self.camelot_key = camelot_key
        self.genre = genre
        self.artist = artist
        self.album = album
        self.duration_min = duration_min
        self.duration_max = duration_max
        self.file_format = file_format
        self.energy_min = energy_min
        self.energy_max = energy_max
        self.favorite = favorite
        self.rating_min = rating_min
        self.missing_metadata = missing_metadata
        self.analyzed = analyzed
        self.compatible_camelot = compatible_camelot
        self.bpm_match_target = bpm_match_target
        self.bpm_tolerance = bpm_tolerance
        self.allow_half_double = allow_half_double


def apply_filters(tracks: List[TrackInfo], criteria: FilterCriteria) -> List[TrackInfo]:
    result = []
    for t in tracks:
        if criteria.bpm_min is not None and (t.bpm is None or t.bpm < criteria.bpm_min):
            continue
        if criteria.bpm_max is not None and (t.bpm is None or t.bpm > criteria.bpm_max):
            continue
        if criteria.musical_key and t.musical_key != criteria.musical_key:
            continue
        if criteria.camelot_key and t.camelot_key != criteria.camelot_key:
            continue
        if criteria.genre and (t.genre or "").lower() != criteria.genre.lower():
            continue
        if criteria.artist and criteria.artist.lower() not in (t.artist or "").lower():
            continue
        if criteria.album and criteria.album.lower() not in (t.album or "").lower():
            continue
        if criteria.duration_min is not None and (t.duration_seconds is None or t.duration_seconds < criteria.duration_min):
            continue
        if criteria.duration_max is not None and (t.duration_seconds is not None and t.duration_seconds > criteria.duration_max):
            continue
        if criteria.file_format and (t.file_format or "").lower() != criteria.file_format.lower():
            continue
        if criteria.energy_min is not None and (t.energy is None or t.energy < criteria.energy_min):
            continue
        if criteria.energy_max is not None and (t.energy is None or t.energy > criteria.energy_max):
            continue
        if criteria.favorite is not None and t.favorite != criteria.favorite:
            continue
        if criteria.rating_min is not None and t.rating < criteria.rating_min:
            continue
        if criteria.analyzed is not None and t.analyzed != criteria.analyzed:
            continue
        if criteria.compatible_camelot and not is_camelot_compatible(t.camelot_key, criteria.compatible_camelot):
            continue
        if criteria.bpm_match_target is not None and not bpm_match(
            t.bpm, criteria.bpm_match_target, criteria.bpm_tolerance, criteria.allow_half_double
        ):
            continue
        if criteria.missing_metadata is not None:
            missing = not all([t.title, t.artist, t.album, t.genre])
            if missing != criteria.missing_metadata:
                continue
        result.append(t)
    return result


def sort_tracks(tracks: List[TrackInfo], field: str = "title", descending: bool = False) -> List[TrackInfo]:
    def key(t):
        val = getattr(t, field, None)
        if val is None:
            return "" if field in ("title", "artist", "album", "genre", "file_format", "musical_key", "camelot_key") else -1
        return val
    return sorted(tracks, key=key, reverse=descending)


SAVED_PRESETS_PATH = None


def save_preset(name: str, criteria: FilterCriteria, path: str) -> None:
    import json
    try:
        data = {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
        data[name] = criteria.__dict__
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        logger.error("Failed to save filter preset: %s", e)


def load_presets(path: str) -> dict:
    import json
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
