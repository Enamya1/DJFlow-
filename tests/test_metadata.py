from app.services.metadata_service import extract_metadata


def test_extract_metadata_reads_wav_duration(wav_file):
    track = extract_metadata(wav_file)
    assert track.file_path == wav_file
    assert track.title == "test_track"
    assert track.file_format == "WAV"
    assert track.duration_seconds is not None
    assert 1.9 < track.duration_seconds < 2.1


def test_extract_metadata_uses_filename_as_title_fallback(wav_file):
    track = extract_metadata(wav_file)
    assert track.title == "test_track"


def test_extract_metadata_handles_corrupt_file(corrupt_file):
    track = extract_metadata(corrupt_file)
    assert track.file_path == corrupt_file
    assert track.title == "bad"
    assert track.duration_seconds is None


def test_extract_metadata_does_not_fabricate(wav_file):
    track = extract_metadata(wav_file)
    assert track.artist is None
    assert track.album is None
    assert track.genre is None
    assert track.bpm is None
    assert track.musical_key is None
