import json
import os
import wave
import struct
import math

import numpy as np
import pytest

from app.services.analysis_service import (
    AnalysisResult,
    to_camelot,
    estimate_bpm,
    estimate_key,
    estimate_energy,
    analyze_file,
    sidecar_path,
    load_sidecar,
    save_sidecar,
    move_sidecar,
)


def _make_tone_wav(path: str, freq: float = 440.0, duration: float = 3.0, sr: int = 22050, beats: bool = True):
    n = int(sr * duration)
    t = np.linspace(0, duration, n, endpoint=False)
    y = 0.3 * np.sin(2 * np.pi * freq * t)
    if beats:
        bpm = 128.0
        beat_interval = 60.0 / bpm
        envelope = np.zeros_like(y)
        for i in range(n):
            phase = (i / sr) % beat_interval
            if phase < 0.05:
                envelope[i] = 1.0
            else:
                envelope[i] = 0.05
        y = y * envelope
    y = np.clip(y, -1.0, 1.0)
    samples = (y * 32767).astype(np.int16)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(samples.tobytes())


@pytest.fixture
def tone_wav(tmp_path):
    path = str(tmp_path / "tone.wav")
    _make_tone_wav(path)
    return path


@pytest.fixture
def silent_wav(tmp_path):
    path = str(tmp_path / "silent.wav")
    _make_tone_wav(path, freq=0, duration=2.0, beats=False)
    return path


class TestToCamelot:
    def test_major_keys(self):
        assert to_camelot("C") == "8B"
        assert to_camelot("G") == "9B"
        assert to_camelot("A") == "11B"

    def test_minor_keys(self):
        assert to_camelot("Am") == "8A"
        assert to_camelot("Em") == "9A"

    def test_unknown_returns_none(self):
        assert to_camelot("Z") is None
        assert to_camelot("") is None
        assert to_camelot(None) is None


class TestEstimateBpm:
    def test_returns_float_bpm(self, tone_wav):
        bpm, conf, half, double = estimate_bpm(tone_wav)
        assert bpm is not None
        assert isinstance(bpm, float)
        assert bpm > 0
        assert 0.0 <= conf <= 1.0
        assert half == pytest.approx(bpm / 2.0, rel=0.01)
        assert double == pytest.approx(bpm * 2.0, rel=0.01)

    def test_silent_or_empty(self, silent_wav):
        bpm, conf, half, double = estimate_bpm(silent_wav)
        assert bpm is None or isinstance(bpm, float)

    def test_nonexistent_file(self):
        assert estimate_bpm("/no/such/file.wav") == (None, None, None, None)


class TestEstimateKey:
    def test_returns_key_and_camelot(self, tone_wav):
        key, camelot, conf = estimate_key(tone_wav)
        assert key is not None
        assert isinstance(key, str)
        assert 0.0 <= conf <= 1.0

    def test_camelot_matches_key(self, tone_wav):
        key, camelot, _ = estimate_key(tone_wav)
        if key:
            assert to_camelot(key) == camelot

    def test_nonexistent_file(self):
        assert estimate_key("/no/such/file.wav") == (None, None, None)


class TestEstimateEnergy:
    def test_returns_float(self, tone_wav):
        e = estimate_energy(tone_wav)
        assert e is not None
        assert 0.0 <= e <= 1.0

    def test_silent_low_energy(self, silent_wav):
        e = estimate_energy(silent_wav)
        assert e is not None
        assert e < 0.5


class TestAnalyzeFile:
    def test_full_analysis(self, tone_wav):
        result = analyze_file(tone_wav)
        assert isinstance(result, AnalysisResult)
        assert result.bpm is not None
        assert result.musical_key is not None
        assert result.camelot_key is not None
        assert result.energy is not None
        assert result.analysis_version == "1.0"

    def test_without_energy(self, tone_wav):
        result = analyze_file(tone_wav, include_energy=False)
        assert result.energy is None


class TestSidecar:
    def test_sidecar_path(self, tmp_path):
        audio = str(tmp_path / "song.mp3")
        assert sidecar_path(audio) == str(tmp_path / "song.mp3.djflow.json")

    def test_save_and_load_roundtrip(self, tmp_path):
        audio = str(tmp_path / "song.mp3")
        result = AnalysisResult(bpm=128.0, musical_key="Am", camelot_key="8A", energy=0.7)
        assert save_sidecar(audio, result) is True
        loaded = load_sidecar(audio)
        assert loaded is not None
        assert loaded.bpm == 128.0
        assert loaded.musical_key == "Am"
        assert loaded.camelot_key == "8A"
        assert loaded.energy == 0.7

    def test_load_nonexistent_returns_none(self, tmp_path):
        assert load_sidecar(str(tmp_path / "nope.mp3")) is None

    def test_load_corrupt_returns_none(self, tmp_path):
        audio = str(tmp_path / "song.mp3")
        path = sidecar_path(audio)
        with open(path, "w") as f:
            f.write("{bad json")
        assert load_sidecar(audio) is None

    def test_move_sidecar(self, tmp_path):
        old_audio = str(tmp_path / "old.mp3")
        new_audio = str(tmp_path / "new.mp3")
        save_sidecar(old_audio, AnalysisResult(bpm=100.0))
        move_sidecar(old_audio, new_audio)
        assert os.path.exists(sidecar_path(new_audio))
        assert not os.path.exists(sidecar_path(old_audio))

    def test_move_sidecar_nonexistent_no_error(self, tmp_path):
        move_sidecar(str(tmp_path / "a.mp3"), str(tmp_path / "b.mp3"))
