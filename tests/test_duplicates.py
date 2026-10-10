from app.database.models import Track
from app.database.repository import TrackRepository
from app.services.library_service import LibraryService
from app.utils.file_utils import compute_file_hash


def test_duplicate_detection_by_path(tmp_db, wav_file):
    service = LibraryService(tmp_db)
    result1 = service.import_file(wav_file)
    assert result1.imported == 1
    result2 = service.import_file(wav_file)
    assert result2.imported == 0
    assert result2.skipped_duplicates == 1


def test_duplicate_detection_by_hash(tmp_db, wav_file, tmp_path):
    service = LibraryService(tmp_db)
    service.import_file(wav_file)

    dup_path = tmp_path / "copy.wav"
    import shutil
    shutil.copy(wav_file, dup_path)

    result = service.import_file(str(dup_path))
    assert result.imported == 0
    assert result.skipped_duplicates == 1


def test_different_files_both_imported(tmp_db, wav_file, wav_file_2):
    service = LibraryService(tmp_db)
    r1 = service.import_file(wav_file)
    r2 = service.import_file(wav_file_2)
    assert r1.imported == 1
    assert r2.imported == 1
    assert TrackRepository(tmp_db).count() == 2
