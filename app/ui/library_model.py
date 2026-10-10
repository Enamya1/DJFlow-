import os
from typing import List, Optional

from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel, QSize
from PySide6.QtGui import QPixmap, QColor, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableView, QHeaderView, QSplitter, QFrame, QSpinBox,
    QAbstractItemView, QMenu, QDoubleSpinBox, QSizePolicy, QScrollArea,
)

from app.database.migrations import Database
from app.database.models import Track
from app.database.repository import TrackRepository
from app.utils.file_utils import format_duration

COLUMNS = [
    "Artwork", "Title", "Artist", "Album", "Genre",
    "Duration", "BPM", "Key", "Format", "Location",
]


class LibraryTableModel(QAbstractTableModel):
    def __init__(self, tracks: Optional[List[Track]] = None, parent=None):
        super().__init__(parent)
        self._tracks: List[Track] = tracks or []
        self._artwork_cache = {}

    def set_tracks(self, tracks: List[Track]) -> None:
        self.beginResetModel()
        self._tracks = tracks
        self._artwork_cache.clear()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._tracks)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return COLUMNS[section]
        return None

    def _get_artwork(self, track: Track) -> QPixmap:
        if track.id in self._artwork_cache:
            return self._artwork_cache[track.id]
        pix = QPixmap(40, 40)
        pix.fill(QColor("#27272f"))
        if track.artwork_path and os.path.isfile(track.artwork_path):
            loaded = QPixmap(track.artwork_path)
            if not loaded.isNull():
                pix = loaded.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self._artwork_cache[track.id] = pix
        return pix

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        track = self._tracks[index.row()]
        col = index.column()

        if role == Qt.UserRole:
            return track

        if role == Qt.DecorationRole and col == 0:
            return self._get_artwork(track)

        if role == Qt.DisplayRole:
            if col == 0:
                return None
            if col == 1:
                return track.title
            if col == 2:
                return track.artist or ""
            if col == 3:
                return track.album or ""
            if col == 4:
                return track.genre or ""
            if col == 5:
                return format_duration(track.duration_seconds)
            if col == 6:
                if track.bpm is not None:
                    return f"{track.bpm:g}"
                return "Unknown"
            if col == 7:
                return track.musical_key or "Unknown"
            if col == 8:
                return track.file_format or ""
            if col == 9:
                return track.file_path

        if role == Qt.ToolTipRole and col == 9:
            return track.file_path

        if role == Qt.ForegroundRole:
            if track.favorite:
                return QColor("#22d3ee")

        return None

    def track_at(self, row: int) -> Optional[Track]:
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None


class LibraryProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._genre = ""
        self._format = ""
        self._min_duration: Optional[float] = None
        self._max_duration: Optional[float] = None
        self._favorites_only = False

    def set_search(self, text: str) -> None:
        self._search_text = text.strip().lower()
        self.invalidateFilter()

    def set_genre(self, genre: str) -> None:
        self._genre = genre
        self.invalidateFilter()

    def set_format(self, fmt: str) -> None:
        self._format = fmt
        self.invalidateFilter()

    def set_duration_range(self, min_dur: Optional[float], max_dur: Optional[float]) -> None:
        self._min_duration = min_dur
        self._max_duration = max_dur
        self.invalidateFilter()

    def set_filter_favorites(self, only: bool) -> None:
        self._favorites_only = only
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        model = self.sourceModel()
        if not isinstance(model, LibraryTableModel):
            return True
        track = model.track_at(source_row)
        if track is None:
            return False

        if self._search_text:
            haystack = " ".join(filter(None, [
                track.title, track.artist, track.album, track.genre,
            ])).lower()
            if self._search_text not in haystack:
                return False

        if self._genre and track.genre != self._genre:
            return False

        if self._format and track.file_format != self._format:
            return False

        if self._min_duration is not None:
            if track.duration_seconds is None or track.duration_seconds < self._min_duration:
                return False
        if self._max_duration is not None:
            if track.duration_seconds is not None and track.duration_seconds > self._max_duration:
                return False

        if self._favorites_only and not track.favorite:
            return False

        return True

    def lessThan(self, left: QModelIndex, right: QModelIndex) -> bool:
        col = left.column()
        model = self.sourceModel()
        if not isinstance(model, LibraryTableModel):
            return super().lessThan(left, right)
        left_track = model.track_at(left.row())
        right_track = model.track_at(right.row())
        if left_track is None or right_track is None:
            return super().lessThan(left, right)

        if col == 5:
            lv = left_track.duration_seconds or -1
            rv = right_track.duration_seconds or -1
            return lv < rv
        if col == 6:
            lv = left_track.bpm or -1
            rv = right_track.bpm or -1
            return lv < rv

        lv = str(model.data(left, Qt.DisplayRole) or "")
        rv = str(model.data(right, Qt.DisplayRole) or "")
        return lv.lower() < rv.lower()
