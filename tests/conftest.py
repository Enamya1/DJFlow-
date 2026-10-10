import os
import sys
import wave
import struct
import tempfile
import shutil

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.migrations import Database


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    Database.reset()
    db = Database.initialize(db_path)
    yield db
    Database.reset()


@pytest.fixture
def wav_file(tmp_path):
    path = tmp_path / "test_track.wav"
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        n_frames = 44100 * 2
        wf.writeframes(b"\x00\x00" * n_frames)
    return str(path)


@pytest.fixture
def wav_file_2(tmp_path):
    path = tmp_path / "second_track.wav"
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        n_frames = 48000 * 3
        wf.writeframes(b"\x00\x00\x00\x00" * n_frames)
    return str(path)


@pytest.fixture
def corrupt_file(tmp_path):
    path = tmp_path / "bad.mp3"
    path.write_bytes(b"this is not a real audio file at all" * 100)
    return str(path)
