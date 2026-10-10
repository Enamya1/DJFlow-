import logging
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from .migrations import Database
from .models import Track, Playlist

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TrackRepository:
    def __init__(self, db: Database):
        self._db = db

    def insert(self, track: Track) -> Optional[int]:
        if not track.title:
            raise ValueError("Track title cannot be empty")
        if not track.file_path:
            raise ValueError("Track file_path cannot be empty")

        if track.date_added is None:
            track.date_added = _now()

        query = """
            INSERT OR IGNORE INTO tracks (
                title, artist, album, genre, duration_seconds, bpm, musical_key,
                camelot_key, bitrate, sample_rate, file_format, file_path, file_hash,
                artwork_path, rating, favorite, user_tags, date_added, date_modified, last_played
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            track.title, track.artist, track.album, track.genre, track.duration_seconds,
            track.bpm, track.musical_key, track.camelot_key, track.bitrate, track.sample_rate,
            track.file_format, track.file_path, track.file_hash, track.artwork_path,
            track.rating, track.favorite, track.user_tags, track.date_added,
            track.date_modified, track.last_played,
        )
        try:
            cursor = self._db.execute(query, params)
            self._db.commit()
            if cursor.rowcount and cursor.rowcount > 0 and cursor.lastrowid:
                track.id = cursor.lastrowid
                return track.id
            return None
        except Exception:
            logger.exception("Failed to insert track %s", track.file_path)
            raise

    def update_metadata(self, track: Track) -> None:
        query = """
            UPDATE tracks SET
                title=?, artist=?, album=?, genre=?, duration_seconds=?, bpm=?,
                musical_key=?, camelot_key=?, bitrate=?, sample_rate=?, file_format=?,
                file_hash=?, artwork_path=?, date_modified=?
            WHERE id=?
        """
        params = (
            track.title, track.artist, track.album, track.genre, track.duration_seconds,
            track.bpm, track.musical_key, track.camelot_key, track.bitrate, track.sample_rate,
            track.file_format, track.file_hash, track.artwork_path, _now(), track.id,
        )
        self._db.execute(query, params)
        self._db.commit()

    def get_by_id(self, track_id: int) -> Optional[Track]:
        cursor = self._db.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        return Track.from_row(cursor.fetchone())

    def get_by_path(self, file_path: str) -> Optional[Track]:
        cursor = self._db.execute("SELECT * FROM tracks WHERE file_path = ?", (file_path,))
        return Track.from_row(cursor.fetchone())

    def get_by_hash(self, file_hash: str) -> Optional[Track]:
        cursor = self._db.execute("SELECT * FROM tracks WHERE file_hash = ? LIMIT 1", (file_hash,))
        return Track.from_row(cursor.fetchone())

    def path_exists(self, file_path: str) -> bool:
        cursor = self._db.execute("SELECT 1 FROM tracks WHERE file_path = ? LIMIT 1", (file_path,))
        return cursor.fetchone() is not None

    def hash_exists(self, file_hash: str) -> bool:
        cursor = self._db.execute("SELECT 1 FROM tracks WHERE file_hash = ? LIMIT 1", (file_hash,))
        return cursor.fetchone() is not None

    def all_paths(self) -> List[str]:
        cursor = self._db.execute("SELECT file_path FROM tracks")
        return [row["file_path"] for row in cursor.fetchall()]

    def delete(self, track_id: int) -> None:
        self._db.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        self._db.commit()

    def set_favorite(self, track_id: int, favorite: bool) -> None:
        self._db.execute("UPDATE tracks SET favorite = ? WHERE id = ?", (1 if favorite else 0, track_id))
        self._db.commit()

    def set_rating(self, track_id: int, rating: int) -> None:
        rating = max(0, min(5, rating))
        self._db.execute("UPDATE tracks SET rating = ? WHERE id = ?", (rating, track_id))
        self._db.commit()

    def set_tags(self, track_id: int, tags: str) -> None:
        self._db.execute("UPDATE tracks SET user_tags = ? WHERE id = ?", (tags, track_id))
        self._db.commit()

    def update_last_played(self, track_id: int) -> None:
        self._db.execute("UPDATE tracks SET last_played = ? WHERE id = ?", (_now(), track_id))
        self._db.commit()

    def count(self) -> int:
        cursor = self._db.execute("SELECT COUNT(*) AS c FROM tracks")
        return cursor.fetchone()["c"]

    def count_analyzed(self) -> int:
        cursor = self._db.execute(
            "SELECT COUNT(*) AS c FROM tracks WHERE bpm IS NOT NULL OR musical_key IS NOT NULL"
        )
        return cursor.fetchone()["c"]

    def count_favorites(self) -> int:
        cursor = self._db.execute("SELECT COUNT(*) AS c FROM tracks WHERE favorite = 1")
        return cursor.fetchone()["c"]

    def recently_added(self, limit: int = 10) -> List[Track]:
        cursor = self._db.execute(
            "SELECT * FROM tracks ORDER BY date_added DESC LIMIT ?", (limit,)
        )
        return [Track.from_row(r) for r in cursor.fetchall()]

    def all_genres(self) -> List[str]:
        cursor = self._db.execute(
            "SELECT DISTINCT genre FROM tracks WHERE genre IS NOT NULL AND genre != '' ORDER BY genre"
        )
        return [r["genre"] for r in cursor.fetchall()]

    def all_formats(self) -> List[str]:
        cursor = self._db.execute(
            "SELECT DISTINCT file_format FROM tracks WHERE file_format IS NOT NULL AND file_format != '' ORDER BY file_format"
        )
        return [r["file_format"] for r in cursor.fetchall()]

    def search(
        self,
        query: str = "",
        genre: Optional[str] = None,
        file_format: Optional[str] = None,
        min_duration: Optional[float] = None,
        max_duration: Optional[float] = None,
        favorite_only: bool = False,
        sort_by: str = "title",
        sort_order: str = "ASC",
    ) -> List[Track]:
        allowed_sort = {
            "title", "artist", "album", "genre", "duration_seconds",
            "bpm", "musical_key", "file_format", "file_path", "date_added", "rating",
        }
        if sort_by not in allowed_sort:
            sort_by = "title"
        sort_order = "DESC" if sort_order.upper() == "DESC" else "ASC"

        sql = "SELECT * FROM tracks WHERE 1=1"
        params: List[Any] = []

        if query:
            like = f"%{query}%"
            sql += " AND (title LIKE ? OR artist LIKE ? OR album LIKE ? OR genre LIKE ?)"
            params.extend([like, like, like, like])

        if genre:
            sql += " AND genre = ?"
            params.append(genre)

        if file_format:
            sql += " AND file_format = ?"
            params.append(file_format)

        if min_duration is not None:
            sql += " AND duration_seconds >= ?"
            params.append(min_duration)

        if max_duration is not None:
            sql += " AND (duration_seconds IS NULL OR duration_seconds <= ?)"
            params.append(max_duration)

        if favorite_only:
            sql += " AND favorite = 1"

        sql += f" ORDER BY {sort_by} COLLATE NOCASE {sort_order}"
        cursor = self._db.execute(sql, tuple(params))
        return [Track.from_row(r) for r in cursor.fetchall()]


class PlaylistRepository:
    def __init__(self, db: Database):
        self._db = db

    def create(self, name: str, description: str = "") -> int:
        cursor = self._db.execute(
            "INSERT INTO playlists (name, description, created_at) VALUES (?, ?, ?)",
            (name, description, _now()),
        )
        self._db.commit()
        return cursor.lastrowid

    def count(self) -> int:
        cursor = self._db.execute("SELECT COUNT(*) AS c FROM playlists")
        return cursor.fetchone()["c"]

    def all(self) -> List[Playlist]:
        cursor = self._db.execute("SELECT * FROM playlists ORDER BY created_at DESC")
        return [Playlist(**dict(r)) for r in cursor.fetchall()]

    def delete(self, playlist_id: int) -> None:
        self._db.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        self._db.commit()


class SettingsRepository:
    def __init__(self, db: Database):
        self._db = db

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        cursor = self._db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self._db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._db.commit()

    def delete(self, key: str) -> None:
        self._db.execute("DELETE FROM settings WHERE key = ?", (key,))
        self._db.commit()

    def all(self) -> Dict[str, str]:
        cursor = self._db.execute("SELECT key, value FROM settings")
        return {r["key"]: r["value"] for r in cursor.fetchall()}
