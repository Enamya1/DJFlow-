import sqlite3

from app.database.migrations import Database


def test_database_initialization_creates_tables(tmp_db):
    cursor = tmp_db.connection().execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = {row["name"] for row in cursor.fetchall()}
    assert "tracks" in tables
    assert "playlists" in tables
    assert "playlist_tracks" in tables
    assert "settings" in tables


def test_database_schema_has_required_columns(tmp_db):
    cursor = tmp_db.connection().execute("PRAGMA table_info(tracks)")
    columns = {row["name"] for row in cursor.fetchall()}
    required = {
        "id", "title", "artist", "album", "genre", "duration_seconds", "bpm",
        "musical_key", "camelot_key", "bitrate", "sample_rate", "file_format",
        "file_path", "file_hash", "artwork_path", "rating", "favorite",
        "user_tags", "date_added", "date_modified", "last_played",
    }
    assert required.issubset(columns)


def test_file_path_is_unique(tmp_db):
    from app.database.models import Track
    from app.database.repository import TrackRepository

    repo = TrackRepository(tmp_db)
    t = Track(title="A", file_path="/music/a.mp3", file_format="MP3")
    repo.insert(t)
    dup = Track(title="B", file_path="/music/a.mp3", file_format="MP3")
    result = repo.insert(dup)
    assert result is None
    assert repo.count() == 1


def test_foreign_keys_enabled(tmp_db):
    cursor = tmp_db.connection().execute("PRAGMA foreign_keys")
    assert cursor.fetchone()[0] == 1
