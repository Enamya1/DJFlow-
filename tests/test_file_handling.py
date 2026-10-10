import os
from app.services.library_service import LibraryService


def test_missing_file_is_not_imported(tmp_db, tmp_path):
    service = LibraryService(tmp_db)
    missing = str(tmp_path / "does_not_exist.mp3")
    result = service.import_file(missing)
    assert result.imported == 0
    assert result.failed == 1
    assert missing in result.unreadable


def test_corrupt_file_reported_as_unreadable(tmp_db, corrupt_file):
    service = LibraryService(tmp_db)
    result = service.import_file(corrupt_file)
    assert result.imported == 0
    assert corrupt_file in result.unreadable


def test_unsupported_extension_skipped(tmp_db, tmp_path):
    service = LibraryService(tmp_db)
    txt = tmp_path / "notes.txt"
    txt.write_text("hello")
    result = service.import_file(str(txt))
    assert result.imported == 0
    assert result.skipped_duplicates == 1


def test_import_folder_recursive(tmp_db, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    import wave
    p1 = tmp_path / "a.wav"
    p2 = sub / "b.wav"
    with wave.open(str(p1), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x00" * 44100)
    with wave.open(str(p2), "w") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(b"\x01\x00\x02\x00" * 48000)

    service = LibraryService(tmp_db)
    result = service.import_folder(str(tmp_path), recursive=True)
    assert result.imported == 2


def test_import_folder_non_recursive(tmp_db, tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    import wave
    p1 = tmp_path / "a.wav"
    p2 = sub / "b.wav"
    for p in (p1, p2):
        with wave.open(str(p), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b"\x00\x00" * 44100)

    service = LibraryService(tmp_db)
    result = service.import_folder(str(tmp_path), recursive=False)
    assert result.imported == 1
