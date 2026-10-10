import logging
import os
import threading
from typing import List, Optional

from PySide6.QtCore import Qt, Signal, QTimer, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QFileDialog, QMessageBox, QFrame, QSizePolicy, QSlider, QSpinBox,
    QAbstractItemView, QSplitter, QCheckBox, QInputDialog,
)
from PySide6.QtGui import QPixmap, QIcon, QColor

from app.config import AppConfig
from app.providers.base import MusicProvider, SearchResult
from app.providers.jamendo import JamendoProvider
from app.providers.musicbrainz import MusicBrainzProvider
from app.services.download_service import DownloadManager, DownloadItem, DownloadStatus
from app.services.folder_templates import resolve_destination, unique_destination
from app.utils.file_utils import format_duration

from .widgets.waveform_widget import WaveformWidget, AudioPlayer

logger = logging.getLogger(__name__)


class SearchSignals(QObject):
    results = Signal(list)
    error = Signal(str)
    finished = Signal()


class DiscoverView(QWidget):
    download_added = Signal()

    def __init__(self, config: AppConfig, download_manager: DownloadManager, parent=None):
        super().__init__(parent)
        self._config = config
        self._download_manager = download_manager
        self._providers: dict[str, MusicProvider] = {}
        self._results: List[SearchResult] = []
        self._search_signals = SearchSignals()
        self._search_signals.results.connect(self._on_results)
        self._search_signals.error.connect(self._on_search_error)
        self._search_signals.finished.connect(self._on_search_finished)
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._do_search)
        self._artwork_cache = {}

        self._player = AudioPlayer()
        self._current_preview_url: Optional[str] = None

        self._build_ui()
        self._refresh_providers()

    def _refresh_providers(self) -> None:
        jamendo_id = self._config.get("jamendo_client_id", "")
        self._providers["Jamendo"] = JamendoProvider(jamendo_id)
        self._providers["MusicBrainz"] = MusicBrainzProvider(
            self._config.get("musicbrainz_user_agent", "DJFlowStudio/1.0")
        )
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.source_combo.addItems(list(self._providers.keys()))
        self.source_combo.blockSignals(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        header = QVBoxLayout()
        title = QLabel("Discover Music")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Search Jamendo and MusicBrainz for new tracks")
        subtitle.setObjectName("SectionSubtitle")
        header.addWidget(title)
        header.addWidget(subtitle)
        root.addLayout(header)

        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(140)
        search_row.addWidget(self.source_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search for a song, artist, or genre…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input, 1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("PrimaryButton")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self.search_btn)

        root.addLayout(search_row)

        options_row = QHBoxLayout()
        self.live_check = QCheckBox("Live search")
        self.live_check.setChecked(self._config.get("live_search", True))
        self.live_check.toggled.connect(self._toggle_live_search)
        options_row.addWidget(self.live_check)
        options_row.addStretch()
        root.addLayout(options_row)

        self.search_input.textChanged.connect(self._on_text_changed)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Searching…")
        self.progress.hide()
        root.addWidget(self.progress)

        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels([
            "Artwork", "Title", "Artist", "Album", "Genre",
            "Duration", "Download", "License", "Preview", "Actions",
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.Interactive)
        header_view.setStretchLastSection(False)
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 160)
        self.table.setColumnWidth(3, 160)
        self.table.setColumnWidth(4, 110)
        self.table.setColumnWidth(5, 80)
        self.table.setColumnWidth(6, 90)
        self.table.setColumnWidth(7, 160)
        self.table.setColumnWidth(8, 90)
        self.table.setColumnWidth(9, 160)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        splitter.addWidget(self.table)

        preview_panel = self._build_preview_panel()
        splitter.addWidget(preview_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([500, 200])

        root.addWidget(splitter, 1)

    def _build_preview_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("Panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.preview_title = QLabel("Select a track to preview")
        self.preview_title.setStyleSheet("color: #ffffff; font-weight: 600;")
        top.addWidget(self.preview_title, 1)

        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("PrimaryButton")
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self._toggle_play)
        top.addWidget(self.btn_play)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop_preview)
        top.addWidget(self.btn_stop)
        layout.addLayout(top)

        self.waveform = WaveformWidget()
        self.waveform.seek_requested.connect(self._on_waveform_seek)
        layout.addWidget(self.waveform)

        bottom = QHBoxLayout()
        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: #a1a1aa;")
        bottom.addWidget(self.time_label)
        bottom.addStretch()
        bottom.addWidget(QLabel("Volume:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(120)
        self.volume_slider.valueChanged.connect(
            lambda v: self._player.set_volume(v / 100.0)
        )
        bottom.addWidget(self.volume_slider)
        layout.addLayout(bottom)

        self._player.position_changed.connect(self._on_position_changed)
        self._player.duration_changed.connect(self._on_duration_changed)
        self._player.error_occurred.connect(
            lambda e: QMessageBox.warning(self, "Preview Error", e)
        )

        return panel

    def _toggle_live_search(self, checked: bool) -> None:
        self._config.set("live_search", checked)

    def _on_text_changed(self, text: str) -> None:
        if self.live_check.isChecked():
            debounce = int(self._config.get("live_search_debounce_ms", 400))
            self._debounce_timer.start(debounce)

    def _on_search(self) -> None:
        self._debounce_timer.stop()
        self._do_search()

    def _do_search(self) -> None:
        query = self.search_input.text().strip()
        if not query:
            return
        provider_name = self.source_combo.currentText()
        provider = self._providers.get(provider_name)
        if not provider:
            return
        if not provider.is_available():
            err = provider.credential_error() or "Provider not available."
            self._search_signals.error.emit(err)
            return

        self.progress.show()
        self.search_btn.setEnabled(False)

        def worker():
            try:
                results = provider.search(query)
                self._search_signals.results.emit(results)
            except Exception as e:
                self._search_signals.error.emit(str(e))
            finally:
                self._search_signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _on_results(self, results: list) -> None:
        self._results = results
        self.table.setRowCount(len(results))
        for row, r in enumerate(results):
            self._populate_row(row, r)

    def _populate_row(self, row: int, r: SearchResult) -> None:
        art_item = QTableWidgetItem()
        if r.artwork_url:
            art_item.setIcon(self._load_artwork_icon(r.artwork_url))
        self.table.setItem(row, 0, art_item)
        self.table.setItem(row, 1, QTableWidgetItem(r.title))
        self.table.setItem(row, 2, QTableWidgetItem(r.artist or "Unknown"))
        self.table.setItem(row, 3, QTableWidgetItem(r.album or "Unknown"))
        self.table.setItem(row, 4, QTableWidgetItem(r.genre or "Unknown"))
        self.table.setItem(row, 5, QTableWidgetItem(format_duration(r.duration_seconds)))
        dl_text = "Yes" if r.download_available else "No"
        dl_item = QTableWidgetItem(dl_text)
        dl_item.setForeground(QColor("#22d3ee") if r.download_available else QColor("#71717a"))
        self.table.setItem(row, 6, dl_item)
        self.table.setItem(row, 7, QTableWidgetItem(r.license_name or "Unknown"))

        preview_btn = QPushButton("Preview" if r.preview_url else "—")
        preview_btn.setEnabled(bool(r.preview_url))
        preview_btn.setCursor(Qt.PointingHandCursor if r.preview_url else Qt.ArrowCursor)
        if r.preview_url:
            preview_btn.clicked.connect(lambda _, res=r: self._start_preview(res))
        self.table.setCellWidget(row, 8, preview_btn)

        actions = QWidget()
        al = QHBoxLayout(actions)
        al.setContentsMargins(4, 2, 4, 2)
        al.setSpacing(4)

        dl_btn = QPushButton("Download")
        dl_btn.setEnabled(r.download_available)
        dl_btn.setCursor(Qt.PointingHandCursor if r.download_available else Qt.ArrowCursor)
        if r.download_available:
            dl_btn.clicked.connect(lambda _, res=r: self._download_track(res))
        al.addWidget(dl_btn)

        src_btn = QPushButton("Source")
        src_btn.setCursor(Qt.PointingHandCursor)
        src_btn.clicked.connect(lambda _, res=r: self._open_source(res))
        al.addWidget(src_btn)

        self.table.setCellWidget(row, 9, actions)

    def _load_artwork_icon(self, url: str) -> QIcon:
        if url in self._artwork_cache:
            return self._artwork_cache[url]
        icon = QIcon()
        try:
            import requests
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                pix = QPixmap()
                pix.loadFromData(resp.content)
                if not pix.isNull():
                    icon = QIcon(pix.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation))
        except Exception:
            pass
        self._artwork_cache[url] = icon
        return icon

    def _on_search_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Search Error", msg)

    def _on_search_finished(self) -> None:
        self.progress.hide()
        self.search_btn.setEnabled(True)

    def _on_row_double_clicked(self, index) -> None:
        row = index.row()
        if 0 <= row < len(self._results):
            self._start_preview(self._results[row])

    def _start_preview(self, result: SearchResult) -> None:
        if not result.preview_url:
            QMessageBox.information(self, "Preview", "No preview available for this track.")
            return
        self._current_preview_url = result.preview_url
        self.preview_title.setText(f"{result.title} — {result.artist}")
        self._player.load(result.preview_url)
        self._player.play()
        self.btn_play.setText("Pause")
        self.waveform.set_peaks(None)

    def _toggle_play(self) -> None:
        if not self._current_preview_url:
            return
        if self._player.is_playing():
            self._player.pause()
            self.btn_play.setText("Play")
        else:
            self._player.play()
            self.btn_play.setText("Pause")

    def _stop_preview(self) -> None:
        self._player.stop()
        self.btn_play.setText("Play")
        self.waveform.set_progress(0.0)

    def _on_position_changed(self, pos_ms: int) -> None:
        dur = self._player.duration()
        if dur > 0:
            self.waveform.set_progress(pos_ms / dur)
        self.time_label.setText(f"{format_duration(pos_ms / 1000)} / {format_duration(dur / 1000)}")

    def _on_duration_changed(self, dur_ms: int) -> None:
        self.time_label.setText(f"0:00 / {format_duration(dur_ms / 1000)}")

    def _on_waveform_seek(self, progress: float) -> None:
        dur = self._player.duration()
        if dur > 0:
            self._player.seek(int(progress * dur))

    def _open_source(self, result: SearchResult) -> None:
        if result.source_url:
            from PySide6.QtGui import QDesktopServices
            from PySide6.QtCore import QUrl
            QDesktopServices.openUrl(QUrl(result.source_url))
        else:
            QMessageBox.information(self, "Source", "No source URL available.")

    def _download_track(self, result: SearchResult) -> None:
        if not result.download_available or not result.download_url:
            QMessageBox.information(self, "Download", "This track is not available for download.")
            return

        default_dir = self._config.get("download_folder", "") or self._config.get("music_library_folder", "")
        directory = QFileDialog.getExistingDirectory(
            self, "Choose Download Destination", default_dir or os.path.expanduser("~")
        )
        if not directory:
            return

        category = ""
        if self._config.get("organize_after_download", True):
            category, ok = QInputDialog.getText(
                self, "Category Folder",
                "Optional category subfolder (e.g. House, Techno):\nLeave empty to skip.",
            )
            if not ok:
                return
            category = category.strip()

        ext = "mp3"
        fields = {
            "title": result.title,
            "artist": result.artist,
            "album": result.album,
            "genre": result.genre or category,
            "year": result.year,
            "bpm_range": None,
            "musical_key": None,
        }
        folder_template = self._config.get("folder_template", "{genre}/{artist}")
        if category:
            folder_template = f"{category}/{folder_template}"
        file_template = self._config.get("file_template", "{title} - {artist}")
        dest = resolve_destination(
            fields, directory, folder_template, file_template, ext,
            self._config.get("unknown_bpm_fallback", "Unknown BPM"),
            self._config.get("unknown_key_fallback", "Unknown Key"),
        )
        dest = unique_destination(dest)

        item = DownloadItem(
            url=result.download_url,
            destination=dest,
            title=result.title,
            artist=result.artist or "",
            source=result.source,
        )
        self._download_manager.add(item)
        QMessageBox.information(
            self, "Download Started",
            f"Downloading '{result.title}' to:\n{dest}"
        )
        self.download_added.emit()

    def on_settings_changed(self) -> None:
        self._refresh_providers()
