from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QListWidget, QListWidgetItem, QScrollArea, QSizePolicy,
)

from app.database.migrations import Database
from app.database.repository import TrackRepository, PlaylistRepository
from app.utils.file_utils import format_duration


class StatCard(QFrame):
    def __init__(self, title: str, value: str, accent: bool = False, parent=None):
        super().__init__(parent)
        self.setObjectName("AccentCard" if accent else "StatCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("CardValue")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class DashboardView(QWidget):
    def __init__(self, db: Database,
                 on_import_folder: Callable,
                 on_open_library: Callable,
                 on_open_settings: Callable,
                 parent=None):
        super().__init__(parent)
        self._db = db
        self._tracks = TrackRepository(db)
        self._playlists = PlaylistRepository(db)
        self._on_import_folder = on_import_folder
        self._on_open_library = on_open_library
        self._on_open_settings = on_open_settings

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(20)

        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Overview of your music library")
        subtitle.setObjectName("SectionSubtitle")
        header_col = QVBoxLayout()
        header_col.setSpacing(2)
        header_col.addWidget(title)
        header_col.addWidget(subtitle)
        header.addLayout(header_col)
        header.addStretch()
        root.addLayout(header)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)

        self.card_tracks = StatCard("Total Tracks", "0", accent=True)
        self.card_analyzed = StatCard("Analyzed", "0")
        self.card_playlists = StatCard("Playlists", "0")
        self.card_favorites = StatCard("Favorites", "0")

        for card in (self.card_tracks, self.card_analyzed, self.card_playlists, self.card_favorites):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            stats_row.addWidget(card)

        root.addLayout(stats_row)

        body = QHBoxLayout()
        body.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(16)

        quick_title = QLabel("Quick Actions")
        quick_title.setObjectName("CardTitle")
        left_col.addWidget(quick_title)

        self.btn_import = QPushButton("Import Music Folder")
        self.btn_import.setObjectName("PrimaryButton")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        self.btn_import.clicked.connect(self._on_import_folder)

        self.btn_library = QPushButton("Open My Library")
        self.btn_library.setCursor(Qt.PointingHandCursor)
        self.btn_library.clicked.connect(self._on_open_library)

        self.btn_settings = QPushButton("Open Settings")
        self.btn_settings.setCursor(Qt.PointingHandCursor)
        self.btn_settings.clicked.connect(self._on_open_settings)

        for btn in (self.btn_import, self.btn_library, self.btn_settings):
            btn.setMinimumHeight(42)
            left_col.addWidget(btn)

        left_col.addStretch()
        body.addLayout(left_col, 1)

        right_col = QVBoxLayout()
        right_col.setSpacing(8)

        recent_title = QLabel("Recently Imported Tracks")
        recent_title.setObjectName("CardTitle")
        right_col.addWidget(recent_title)

        self.recent_list = QListWidget()
        self.recent_list.setObjectName("NavList")
        self.recent_list.setStyleSheet(
            "QListWidget { background-color: #24242b; border: 1px solid #2f2f38; border-radius: 10px; padding: 6px; }"
            "QListWidget::item { padding: 8px 12px; border-radius: 6px; color: #e4e4e7; }"
            "QListWidget::item:hover { background-color: #2f2f38; }"
        )
        right_col.addWidget(self.recent_list, 1)

        fav_title = QLabel("Favorite Tracks")
        fav_title.setObjectName("CardTitle")
        right_col.addWidget(fav_title)

        self.fav_list = QListWidget()
        self.fav_list.setObjectName("NavList")
        self.fav_list.setStyleSheet(self.recent_list.styleSheet())
        right_col.addWidget(self.fav_list, 1)

        body.addLayout(right_col, 2)
        root.addLayout(body, 1)

    def refresh(self) -> None:
        try:
            self.card_tracks.set_value(str(self._tracks.count()))
            self.card_analyzed.set_value(str(self._tracks.count_analyzed()))
            self.card_playlists.set_value(str(self._playlists.count()))
            self.card_favorites.set_value(str(self._tracks.count_favorites()))

            self.recent_list.clear()
            for t in self._tracks.recently_added(10):
                artist = t.artist or "Unknown Artist"
                duration = format_duration(t.duration_seconds)
                item = QListWidgetItem(f"{t.title}  —  {artist}   [{duration}]")
                item.setToolTip(t.file_path)
                self.recent_list.addItem(item)

            self.fav_list.clear()
            favs = self._tracks.search(favorite_only=True, sort_by="date_added", sort_order="DESC")
            for t in favs[:10]:
                artist = t.artist or "Unknown Artist"
                item = QListWidgetItem(f"{t.title}  —  {artist}")
                item.setToolTip(t.file_path)
                self.fav_list.addItem(item)
        except Exception:
            pass
