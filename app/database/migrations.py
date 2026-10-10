import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 1

_MIGRATIONS = [
    """
    CREATE TABLE IF NOT EXISTS tracks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        artist TEXT,
        album TEXT,
        genre TEXT,
        duration_seconds REAL,
        bpm REAL,
        musical_key TEXT,
        camelot_key TEXT,
        bitrate INTEGER,
        sample_rate INTEGER,
        file_format TEXT,
        file_path TEXT NOT NULL UNIQUE,
        file_hash TEXT,
        artwork_path TEXT,
        rating INTEGER DEFAULT 0,
        favorite INTEGER DEFAULT 0,
        user_tags TEXT DEFAULT '',
        date_added TEXT NOT NULL,
        date_modified TEXT,
        last_played TEXT
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT DEFAULT '',
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS playlist_tracks (
        playlist_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        position INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (playlist_id, track_id),
        FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
        FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
    CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
    CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album);
    CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
    CREATE INDEX IF NOT EXISTS idx_tracks_file_format ON tracks(file_format);
    CREATE INDEX IF NOT EXISTS idx_tracks_file_hash ON tracks(file_hash);
    CREATE INDEX IF NOT EXISTS idx_tracks_favorite ON tracks(favorite);
    CREATE INDEX IF NOT EXISTS idx_tracks_date_added ON tracks(date_added);
    """,
]


class Database:
    _instance: Optional["Database"] = None
    _lock = threading.Lock()

    def __init__(self, db_path: str):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._write_lock = threading.Lock()

    @classmethod
    def initialize(cls, db_path: str) -> "Database":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
                cls._instance._run_migrations()
            return cls._instance

    @classmethod
    def get(cls) -> "Database":
        if cls._instance is None:
            raise RuntimeError("Database has not been initialized. Call Database.initialize() first.")
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                cls._instance._conn.close()
                cls._instance = None

    def _run_migrations(self) -> None:
        try:
            with self._write_lock:
                for migration in _MIGRATIONS:
                    self._conn.executescript(migration)
                self._conn.commit()
            logger.info("Database migrations applied (schema version %d).", SCHEMA_VERSION)
        except sqlite3.Error:
            logger.exception("Failed to apply database migrations.")
            raise

    def connection(self) -> sqlite3.Connection:
        return self._conn

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._write_lock:
            cursor = self._conn.execute(query, params)
            return cursor

    def executemany(self, query: str, params_list) -> sqlite3.Cursor:
        with self._write_lock:
            cursor = self._conn.executemany(query, params_list)
            return cursor

    def commit(self) -> None:
        with self._write_lock:
            self._conn.commit()

    def close(self) -> None:
        with self._write_lock:
            self._conn.close()

    @property
    def path(self) -> str:
        return self._db_path
