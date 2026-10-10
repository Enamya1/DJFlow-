import os
import subprocess
import sys
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableView, QHeaderView, QSplitter, QFrame, QSpinBox,
    QAbstractItemView, QMenu, QDoubleSpinBox, QSizePolicy, QMessageBox,
    QCheckBox,
)

from app.database.migrations import Database
from app.database.models import Track
from app.database.repository import TrackRepository
from app.utils.file_utils import format_duration, is_supported_audio

from .library_model import LibraryTableModel, LibraryProxyModel


class LibraryView(QWidget):
    import_requested = Signal(list)

    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self._db = db
        self._tracks = TrackRepository(db)
        self._selected_track: Optional[Track] = None

        self._model = LibraryTableModel()
        self._proxy = LibraryProxyModel()
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("My Library")
        title.setObjectName("SectionTitle")
        self.count_label = QLabel("")
        self.count_label.setObjectName("SectionSubtitle")
        header_col = QVBoxLayout()
        header_col.setSpacing(2)
        header_col.addWidget(title)
        header_col.addWidget(self.count_label)
        header.addLayout(header_col)
        header.addStretch()
        root.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by title, artist, album, or genre…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(280)
        self.search_input.textChanged.connect(self._on_search)
        toolbar.addWidget(self.search_input)

        toolbar.addWidget(QLabel("Genre:"))
        self.genre_combo = QComboBox()
        self.genre_combo.setMinimumWidth(140)
        self.genre_combo.currentTextChanged.connect(self._on_genre)
        toolbar.addWidget(self.genre_combo)

        toolbar.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.setMinimumWidth(110)
        self.format_combo.currentTextChanged.connect(self._on_format)
        toolbar.addWidget(self.format_combo)

        toolbar.addWidget(QLabel("Min:"))
        self.min_dur = QSpinBox()
        self.min_dur.setRange(0, 9999)
        self.min_dur.setSuffix("s")
        self.min_dur.setSpecialValueText("—")
        self.min_dur.setMinimumWidth(80)
        self.min_dur.valueChanged.connect(self._on_duration)
        toolbar.addWidget(self.min_dur)

        toolbar.addWidget(QLabel("Max:"))
        self.max_dur = QSpinBox()
        self.max_dur.setRange(0, 9999)
        self.max_dur.setSuffix("s")
        self.max_dur.setSpecialValueText("—")
        self.max_dur.setMinimumWidth(80)
        self.max_dur.valueChanged.connect(self._on_duration)
        toolbar.addWidget(self.max_dur)

        self.fav_only = QCheckBox("Favorites")
        self.fav_only.toggled.connect(self._on_favorites_only)
        toolbar.addWidget(self.fav_only)

        toolbar.addStretch()

        self.btn_import = QPushButton("Import")
        self.btn_import.setObjectName("PrimaryButton")
        self.btn_import.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self.btn_import)

        self.btn_rescan = QPushButton("Rescan")
        self.btn_rescan.setCursor(Qt.PointingHandCursor)
        toolbar.addWidget(self.btn_rescan)

        root.addLayout(toolbar)

        splitter = QSplitter(Qt.Horizontal)

        self.table = QTableView()
        self.table.setModel(self._proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        self.table.setAcceptDrops(True)
        self.table.setDragDropMode(QAbstractItemView.DropOnly)
        self.table.dragEnterEvent = self._drag_enter_event
        self.table.dragMoveEvent = self._drag_move_event
        self.table.dropEvent = self._drop_event

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setStretchLastSection(True)

        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 120)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 70)
        self.table.setColumnWidth(7, 80)
        self.table.setColumnWidth(8, 70)

        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._on_double_clicked)

        splitter.addWidget(self.table)

        self.details = self._build_details_panel()
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([700, 320])

        root.addWidget(splitter, 1)

    def _build_details_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Track Details")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        self.artwork_label = QLabel()
        self.artwork_label.setFixedSize(200, 200)
        self.artwork_label.setAlignment(Qt.AlignCenter)
        self.artwork_label.setStyleSheet("background-color: #141418; border-radius: 8px;")
        self.artwork_label.setText("No artwork")
        layout.addWidget(self.artwork_label, 0, Qt.AlignHCenter)

        self.detail_title = QLabel("—")
        self.detail_title.setStyleSheet("color: #ffffff; font-size: 16px; font-weight: 700;")
        self.detail_title.setWordWrap(True)
        layout.addWidget(self.detail_title)

        self.detail_artist = QLabel("")
        self.detail_artist.setStyleSheet("color: #a1a1aa;")
        layout.addWidget(self.detail_artist)

        self.detail_info = QLabel("")
        self.detail_info.setStyleSheet("color: #71717a; font-size: 12px;")
        self.detail_info.setWordWrap(True)
        layout.addWidget(self.detail_info)

        self.detail_tags = QLabel("")
        self.detail_tags.setStyleSheet("color: #06b6d4; font-size: 12px;")
        self.detail_tags.setWordWrap(True)
        layout.addWidget(self.detail_tags)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        self.btn_fav = QPushButton("Favorite")
        self.btn_fav.setCheckable(True)
        self.btn_fav.setCursor(Qt.PointingHandCursor)
        self.btn_fav.clicked.connect(self._toggle_favorite)
        actions_row.addWidget(self.btn_fav)

        self.btn_open_folder = QPushButton("Open Folder")
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_containing_folder)
        actions_row.addWidget(self.btn_open_folder)

        layout.addLayout(actions_row)

        rating_row = QHBoxLayout()
        rating_row.addWidget(QLabel("Rating:"))
        self.rating_combo = QComboBox()
        self.rating_combo.addItems(["0", "1", "2", "3", "4", "5"])
        self.rating_combo.currentTextChanged.connect(self._on_rating_changed)
        rating_row.addWidget(self.rating_combo)
        rating_row.addStretch()
        layout.addLayout(rating_row)

        tags_row = QHBoxLayout()
        tags_row.addWidget(QLabel("Tags:"))
        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("comma-separated tags")
        self.tags_input.editingFinished.connect(self._on_tags_edited)
        tags_row.addWidget(self.tags_input, 1)
        layout.addLayout(tags_row)

        self.btn_remove = QPushButton("Remove from Library")
        self.btn_remove.setObjectName("DangerButton")
        self.btn_remove.setCursor(Qt.PointingHandCursor)
        self.btn_remove.clicked.connect(self._remove_selected)
        layout.addWidget(self.btn_remove)

        layout.addStretch()
        return panel

    def refresh(self) -> None:
        tracks = self._tracks.search(sort_by="title", sort_order="ASC")
        self._model.set_tracks(tracks)
        self._refresh_filters()
        self._update_count()

    def _refresh_filters(self) -> None:
        current_genre = self.genre_combo.currentText()
        current_format = self.format_combo.currentText()

        self.genre_combo.blockSignals(True)
        self.format_combo.blockSignals(True)

        self.genre_combo.clear()
        self.genre_combo.addItem("All Genres")
        for g in self._tracks.all_genres():
            self.genre_combo.addItem(g)

        self.format_combo.clear()
        self.format_combo.addItem("All Formats")
        for f in self._tracks.all_formats():
            self.format_combo.addItem(f)

        gi = self.genre_combo.findText(current_genre)
        if gi >= 0:
            self.genre_combo.setCurrentIndex(gi)
        fi = self.format_combo.findText(current_format)
        if fi >= 0:
            self.format_combo.setCurrentIndex(fi)

        self.genre_combo.blockSignals(False)
        self.format_combo.blockSignals(False)

    def _update_count(self) -> None:
        visible = self._proxy.rowCount()
        total = self._model.rowCount()
        self.count_label.setText(f"{visible} of {total} tracks")

    def _on_search(self, text: str) -> None:
        self._proxy.set_search(text)
        self._update_count()

    def _on_genre(self, text: str) -> None:
        self._proxy.set_genre("" if text == "All Genres" else text)
        self._update_count()

    def _on_format(self, text: str) -> None:
        self._proxy.set_format("" if text == "All Formats" else text)
        self._update_count()

    def _on_duration(self) -> None:
        mn = self.min_dur.value()
        mx = self.max_dur.value()
        min_dur = float(mn) if mn > 0 else None
        max_dur = float(mx) if mx > 0 else None
        self._proxy.set_duration_range(min_dur, max_dur)
        self._update_count()

    def _on_favorites_only(self, checked: bool) -> None:
        if checked:
            self._proxy.set_filter_favorites(True)
        else:
            self._proxy.set_filter_favorites(False)
        self._update_count()

    def _current_track(self) -> Optional[Track]:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        proxy_index = indexes[0]
        source_index = self._proxy.mapToSource(proxy_index)
        return self._model.track_at(source_index.row())

    def _on_selection_changed(self) -> None:
        track = self._current_track()
        self._selected_track = track
        self._update_details(track)

    def _update_details(self, track: Optional[Track]) -> None:
        if track is None:
            self.artwork_label.setPixmap(QPixmap())
            self.artwork_label.setText("No artwork")
            self.detail_title.setText("—")
            self.detail_artist.setText("")
            self.detail_info.setText("")
            self.detail_tags.setText("")
            self.rating_combo.setCurrentText("0")
            self.tags_input.setText("")
            self.btn_fav.setChecked(False)
            self.btn_fav.setText("Favorite")
            return

        if track.artwork_path and os.path.isfile(track.artwork_path):
            pix = QPixmap(track.artwork_path)
            if not pix.isNull():
                self.artwork_label.setPixmap(
                    pix.scaled(200, 200, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                )
                self.artwork_label.setText("")
            else:
                self.artwork_label.setPixmap(QPixmap())
                self.artwork_label.setText("No artwork")
        else:
            self.artwork_label.setPixmap(QPixmap())
            self.artwork_label.setText("No artwork")

        self.detail_title.setText(track.title)
        self.detail_artist.setText(track.artist or "Unknown Artist")

        parts = []
        if track.album:
            parts.append(f"Album: {track.album}")
        if track.genre:
            parts.append(f"Genre: {track.genre}")
        parts.append(f"Duration: {format_duration(track.duration_seconds)}")
        if track.bpm is not None:
            parts.append(f"BPM: {track.bpm:g}")
        if track.musical_key:
            parts.append(f"Key: {track.musical_key}")
        if track.bitrate:
            parts.append(f"Bitrate: {track.bitrate} kbps")
        if track.sample_rate:
            parts.append(f"Sample rate: {track.sample_rate} Hz")
        if track.file_format:
            parts.append(f"Format: {track.file_format}")
        parts.append(f"Path: {track.file_path}")
        self.detail_info.setText("\n".join(parts))

        self.detail_tags.setText(f"Tags: {track.user_tags}" if track.user_tags else "Tags: (none)")

        self.rating_combo.blockSignals(True)
        self.rating_combo.setCurrentText(str(track.rating))
        self.rating_combo.blockSignals(False)

        self.tags_input.blockSignals(True)
        self.tags_input.setText(track.user_tags or "")
        self.tags_input.blockSignals(False)

        self.btn_fav.setChecked(bool(track.favorite))
        self.btn_fav.setText("Unfavorite" if track.favorite else "Favorite")

    def _toggle_favorite(self) -> None:
        track = self._selected_track
        if track is None:
            return
        new_val = not bool(track.favorite)
        self._tracks.set_favorite(track.id, new_val)
        track.favorite = 1 if new_val else 0
        self.btn_fav.setText("Unfavorite" if new_val else "Favorite")
        self._model.dataChanged.emit(
            self._model.index(self._proxy.mapToSource(self.table.currentIndex()).row(), 0),
            self._model.index(self._proxy.mapToSource(self.table.currentIndex()).row(), self._model.columnCount() - 1),
        )

    def _on_rating_changed(self, text: str) -> None:
        track = self._selected_track
        if track is None:
            return
        try:
            rating = int(text)
        except ValueError:
            return
        self._tracks.set_rating(track.id, rating)
        track.rating = rating

    def _on_tags_edited(self) -> None:
        track = self._selected_track
        if track is None:
            return
        tags = self.tags_input.text().strip()
        self._tracks.set_tags(track.id, tags)
        track.user_tags = tags
        self.detail_tags.setText(f"Tags: {tags}" if tags else "Tags: (none)")

    def _open_containing_folder(self) -> None:
        track = self._selected_track
        if track is None or not track.file_path:
            return
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(track.file_path)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-R", track.file_path])
            else:
                subprocess.Popen(["xdg-open", os.path.dirname(track.file_path)])
        except Exception as e:
            QMessageBox.warning(self, "Open Folder", f"Could not open folder:\n{e}")

    def _remove_selected(self) -> None:
        track = self._selected_track
        if track is None:
            return
        reply = QMessageBox.question(
            self, "Remove Track",
            f"Remove '{track.title}' from the library?\nThe original file will NOT be deleted.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._tracks.delete(track.id)
            self.refresh()
            self._update_details(None)

    def _on_double_clicked(self, index) -> None:
        pass

    def _on_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        track = self._current_track()
        if track is None:
            return

        menu = QMenu(self)
        fav_action = QAction("Unfavorite" if track.favorite else "Favorite", self)
        fav_action.triggered.connect(self._toggle_favorite)
        menu.addAction(fav_action)

        open_folder_action = QAction("Open Containing Folder", self)
        open_folder_action.triggered.connect(self._open_containing_folder)
        menu.addAction(open_folder_action)

        menu.addSeparator()
        remove_action = QAction("Remove from Library", self)
        remove_action.triggered.connect(self._remove_selected)
        menu.addAction(remove_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _drag_enter_event(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drag_move_event(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event):
        urls = event.mimeData().urls()
        paths = []
        for url in urls:
            local = url.toLocalFile()
            if local:
                paths.append(local)
        if paths:
            self.import_requested.emit(paths)
            event.acceptProposedAction()
