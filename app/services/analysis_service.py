import json
import logging
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    bpm: Optional[float] = None
    bpm_confidence: Optional[float] = None
    bpm_half: Optional[float] = None
    bpm_double: Optional[float] = None
    musical_key: Optional[str] = None
    camelot_key: Optional[str] = None
    key_confidence: Optional[float] = None
    energy: Optional[float] = None
    analysis_version: str = "1.0"
    manually_corrected: bool = False


KEYS_MAJOR = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
KEYS_MINOR = ["Am", "A#m", "Bm", "Cm", "C#m", "Dm", "D#m", "Em", "Fm", "F#m", "Gm", "G#m"]

CAMELOT_MAJOR = {
    "C": "8B", "C#": "3B", "D": "10B", "D#": "5B", "E": "12B", "F": "7B",
    "F#": "2B", "G": "9B", "G#": "4B", "A": "11B", "A#": "6B", "B": "1B",
}
CAMELOT_MINOR = {
    "Am": "8A", "A#m": "3A", "Bm": "10A", "Cm": "5A", "C#m": "12A", "Dm": "7A",
    "D#m": "2A", "Em": "9A", "Fm": "4A", "F#m": "11A", "Gm": "6A", "G#m": "1A",
}

PROFILE_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
PROFILE_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def to_camelot(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    key = key.strip()
    if key in CAMELOT_MAJOR:
        return CAMELOT_MAJOR[key]
    if key in CAMELOT_MINOR:
        return CAMELOT_MINOR[key]
    minor_alt = key.replace("min", "m").replace("minor", "m")
    if minor_alt in CAMELOT_MINOR:
        return CAMELOT_MINOR[minor_alt]
    return None


def estimate_bpm(file_path: str) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    try:
        import librosa
        y, sr = librosa.load(file_path, sr=None, mono=True)
        if len(y) == 0:
            return None, None, None, None
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo) if np.isscalar(tempo) else float(tempo[0])
        if beat_frames is not None and len(beat_frames) > 1:
            intervals = np.diff(beat_frames)
            conf = float(np.std(intervals)) if len(intervals) > 0 else 0.0
            confidence = 1.0 / (1.0 + conf / 10.0)
        else:
            confidence = 0.3
        half = bpm / 2.0 if bpm else None
        double = bpm * 2.0 if bpm else None
        return round(bpm, 2), round(confidence, 3), round(half, 2) if half else None, round(double, 2) if double else None
    except Exception as e:
        logger.warning("BPM estimation failed for %s: %s", file_path, e)
        return None, None, None, None


def estimate_key(file_path: str) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    try:
        import librosa
        y, sr = librosa.load(file_path, sr=None, mono=True)
        if len(y) == 0:
            return None, None, None
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        correlations_major = []
        correlations_minor = []
        for i in range(12):
            shifted_major = np.roll(PROFILE_MAJOR, i)
            shifted_minor = np.roll(PROFILE_MINOR, i)
            correlations_major.append(float(np.corrcoef(chroma_avg, shifted_major)[0, 1]))
            correlations_minor.append(float(np.corrcoef(chroma_avg, shifted_minor)[0, 1]))

        max_major = max(correlations_major)
        max_minor = max(correlations_minor)
        if max_major >= max_minor:
            idx = correlations_major.index(max_major)
            key = KEYS_MAJOR[idx]
            confidence = max_major
        else:
            idx = correlations_minor.index(max_minor)
            key = KEYS_MINOR[idx]
            confidence = max_minor

        confidence = max(0.0, min(1.0, float(confidence)))
        camelot = to_camelot(key)
        return key, camelot, round(confidence, 3)
    except Exception as e:
        logger.warning("Key estimation failed for %s: %s", file_path, e)
        return None, None, None


def estimate_energy(file_path: str) -> Optional[float]:
    try:
        import librosa
        y, sr = librosa.load(file_path, sr=None, mono=True)
        if len(y) == 0:
            return None
        rms = librosa.feature.rms(y=y)[0]
        energy = float(np.mean(rms))
        return round(min(1.0, energy * 10.0), 3)
    except Exception as e:
        logger.warning("Energy estimation failed for %s: %s", file_path, e)
        return None


def analyze_file(file_path: str, include_energy: bool = True) -> AnalysisResult:
    bpm, conf, half, double = estimate_bpm(file_path)
    key, camelot, key_conf = estimate_key(file_path)
    result = AnalysisResult(
        bpm=bpm, bpm_confidence=conf, bpm_half=half, bpm_double=double,
        musical_key=key, camelot_key=camelot, key_confidence=key_conf,
    )
    if include_energy:
        result.energy = estimate_energy(file_path)
    return result


def sidecar_path(audio_path: str) -> str:
    p = Path(audio_path)
    return str(p.with_suffix(p.suffix + ".djflow.json"))


def load_sidecar(audio_path: str) -> Optional[AnalysisResult]:
    path = sidecar_path(audio_path)
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AnalysisResult(**{k: v for k, v in data.items() if k in AnalysisResult.__dataclass_fields__})
    except (json.JSONDecodeError, OSError, TypeError) as e:
        logger.warning("Failed to load sidecar %s: %s", path, e)
        return None


def save_sidecar(audio_path: str, result: AnalysisResult) -> bool:
    path = sidecar_path(audio_path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2)
        return True
    except OSError as e:
        logger.error("Failed to save sidecar %s: %s", path, e)
        return False


def move_sidecar(old_audio_path: str, new_audio_path: str) -> None:
    old_sidecar = sidecar_path(old_audio_path)
    if os.path.exists(old_sidecar):
        new_sidecar = sidecar_path(new_audio_path)
        try:
            os.replace(old_sidecar, new_sidecar)
        except OSError as e:
            logger.warning("Failed to move sidecar: %s", e)
