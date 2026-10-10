import os
from typing import List

from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QStackedWidget, QLabel, QStatusBar, QProgressBar, QPushButton, QFileDialog,
    QMessageBox, QStyle,
)

from app.config import AppConfig
from app.database.migrations import Database
from app.database.repository import SettingsRepository
from app.services.library_service import LibraryService, BackgroundScanner
from app.services.download_service import DownloadManager
from app.utils.file_utils import is_supported_audio

from .theme import DARK_STYLESHEET
from .dashboard import DashboardView
from .library_view import LibraryView
from .settings_view import SettingsView
from .placeholder_view import PlaceholderView
from .discover_view import DiscoverView
from .downloads_view import DownloadsView
from .analysis_view import AnalysisView


DB_PATH = os.path.join("data", "djflow.db")

NAV_ITEMS = [
    ("Dashboard", "Dashboard", "Overview of your music library"),
    ("My Library", "My Library", "Browse, search, and manage your tracks"),
    ("Discover Music", "Discover Music", "Find new music from Jamendo and MusicBrainz"),
    ("Downloads", "Downloads", "Track and manage your music downloads"),
    ("Playlists", "Playlists", "Create and manage playlists (coming soon)"),
    ("Audio Analysis", "Audio Analysis", "BPM and musical key detection"),
    ("Favorites", "Favorites", "Your favorite tracks (coming soon)"),
    ("Settings", "Settings", "Configure DJFlow Studio"),
]


class ScanSignals(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    cancelled = Signal()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DJFlow Studio")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 640)

        self.setStyleSheet(DARK_STYLESHEET)

        self._config = AppConfig.instance()
        self._db = Database.initialize(DB_PATH)
        self._library_service = LibraryService(self._db)
        self._scanner = BackgroundScanner(self._library_service)
        self._download_manager = DownloadManager()
        self._scan_signals = ScanSignals()
        self._scan_signals.progress.connect(self._on_scan_progress)
        self._scan_signals.finished.connect(self._on_scan_finished)

        self._build_ui()
        self._build_status_bar()

        self._nav_list.setCurrentRow(0)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(230)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 16)
        sidebar_layout.setSpacing(0)

        title = QLabel("DJFLOW")
        title.setObjectName("SidebarTitle")
        subtitle = QLabel("STUDIO")
        subtitle.setObjectName("SidebarSubtitle")
        sidebar_layout.addWidget(title)
        sidebar_layout.addWidget(subtitle)

        self._nav_list = QListWidget()
        self._nav_list.setObjectName("NavList")
        self._nav_list.setSpacing(2)
        for name, _, _ in NAV_ITEMS:
            item = QListWidgetItem(name)
            item.setSizeHint(item.sizeHint().expandedTo(self._nav_list.sizeHint()))
            self._nav_list.addItem(item)
        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        sidebar_layout.addWidget(self._nav_list, 1)

        layout.addWidget(sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("ContentArea")

        self.dashboard = DashboardView(
            self._db,
            on_import_folder=self._import_folder_dialog,
            on_open_library=lambda: self._nav_list.setCurrentRow(1),
            on_open_settings=lambda: self._nav_list.setCurrentRow(7),
        )
        self.library = LibraryView(self._db)
        self.library.import_requested.connect(self._handle_import_paths)
        self.library.btn_import.clicked.connect(self._import_folder_dialog)
        self.library.btn_rescan.clicked.connect(self._rescan_library)

        self.discover = DiscoverView(self._config, self._download_manager)
        self.discover.download_added.connect(
            lambda: self._nav_list.setCurrentRow(3)
        )
        self.downloads = DownloadsView(self._download_manager)
        self.playlists = PlaceholderView("Playlists", "Organize tracks into custom playlists.")
        self.analysis = AnalysisView(self._config)
        self.favorites = PlaceholderView("Favorites", "View all your favorite tracks in one place.")

        self.settings = SettingsView(
            self._config,
            on_import_files=self._import_files,
            on_import_folder=self._import_folder,
            on_rescan=self._rescan_library,
            on_settings_changed=self._on_settings_changed,
        )

        for view in (self.dashboard, self.library, self.discover, self.downloads,
                     self.playlists, self.analysis, self.favorites, self.settings):
            self._stack.addWidget(view)

        layout.addWidget(self._stack, 1)

    def _build_status_bar(self) -> None:
        self._status = QStatusBar()
        self.setStatusBar(self._status)

        self._status_label = QLabel("Ready")
        self._status.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(220)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%v/%m files")
        self._progress.hide()
        self._status.addPermanentWidget(self._progress)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("DangerButton")
        self._cancel_btn.setCursor(Qt.PointingHandCursor)
        self._cancel_btn.clicked.connect(self._cancel_scan)
        self._cancel_btn.hide()
        self._status.addPermanentWidget(self._cancel_btn)

    def _on_nav_changed(self, row: int) -> None:
        if 0 <= row < self._stack.count():
            self._stack.setCurrentIndex(row)
            if row == 0:
                self.dashboard.refresh()
            elif row == 1:
                self.library.refresh()
            elif row == 3:
                self.downloads.refresh()

    def _on_settings_changed(self) -> None:
        if hasattr(self, "discover"):
            self.discover.on_settings_changed()

    def _import_folder_dialog(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Import Music Folder")
        if directory:
            recursive = self.settings.is_recursive()
            self._import_folder(directory, recursive)

    def _import_files(self, files: List[str]) -> None:
        supported = [f for f in files if is_supported_audio(f)]
        if not supported:
            QMessageBox.information(self, "Import", "No supported audio files were selected.")
            return
        if self._scanner.is_running():
            QMessageBox.information(self, "Import", "A scan is already in progress.")
            return
        self._progress.show()
        self._cancel_btn.show()
        self._progress.setRange(0, 0)
        self._status_label.setText(f"Importing {len(supported)} file(s)…")
        self._scanner.scan_files(
            supported,
            progress_cb=lambda cur, total, path: self._scan_signals.progress.emit(cur, total, path),
            finished_cb=lambda result: self._scan_signals.finished.emit(result),
        )

    def _import_folder(self, directory: str, recursive: bool = True) -> None:
        if self._scanner.is_running():
            QMessageBox.information(self, "Import", "A scan is already in progress.")
            return
        self._progress.show()
        self._cancel_btn.show()
        self._progress.setRange(0, 0)
        self._status_label.setText(f"Scanning {directory}…")
        self._scanner.scan_folder(
            directory, recursive=recursive,
            progress_cb=lambda cur, total, path: self._scan_signals.progress.emit(cur, total, path),
            finished_cb=lambda result: self._scan_signals.finished.emit(result),
        )

    def _handle_import_paths(self, paths: List[str]) -> None:
        files = []
        for p in paths:
            if os.path.isdir(p):
                from app.utils.file_utils import scan_audio_files
                files.extend(scan_audio_files(p, recursive=True))
            elif os.path.isfile(p) and is_supported_audio(p):
                files.append(p)
        if not files:
            QMessageBox.information(self, "Import", "No supported audio files found.")
            return
        if self._scanner.is_running():
            QMessageBox.information(self, "Import", "A scan is already in progress.")
            return
        self._progress.show()
        self._cancel_btn.show()
        self._progress.setRange(0, 0)
        self._status_label.setText(f"Importing {len(files)} file(s)…")
        self._scanner.scan_folder(
            os.path.dirname(files[0]), recursive=True,
            progress_cb=lambda cur, total, path: self._scan_signals.progress.emit(cur, total, path),
            finished_cb=lambda result: self._scan_signals.finished.emit(result),
        )

    def _rescan_library(self) -> None:
        if self._scanner.is_running():
            QMessageBox.information(self, "Rescan", "A scan is already in progress.")
            return
        self._progress.show()
        self._cancel_btn.show()
        self._progress.setRange(0, 0)
        self._status_label.setText("Rescanning library…")
        self._scanner.rescan_library(
            progress_cb=lambda cur, total, path: self._scan_signals.progress.emit(cur, total, path),
            finished_cb=lambda result: self._scan_signals.finished.emit(result),
        )

    def _cancel_scan(self) -> None:
        self._scanner.cancel()
        self._status_label.setText("Cancelling…")

    def _on_scan_progress(self, current: int, total: int, path: str) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(current)
        self._status_label.setText(f"Processing {current}/{total}: {os.path.basename(path)}")

    def _on_scan_finished(self, result) -> None:
        self._progress.hide()
        self._cancel_btn.hide()
        self._progress.setValue(0)

        msg = (
            f"Import complete.\n"
            f"Imported: {result.imported}\n"
            f"Skipped (duplicates): {result.skipped_duplicates}\n"
            f"Failed: {result.failed}"
        )
        self._status_label.setText(
            f"Done — imported {result.imported}, skipped {result.skipped_duplicates}, failed {result.failed}"
        )

        if result.errors:
            msg += "\n\nErrors (first 5):\n" + "\n".join(result.errors[:5])

        self.library.refresh()
        self.dashboard.refresh()

        QMessageBox.information(self, "Scan Complete", msg)

    def closeEvent(self, event):
        if self._scanner.is_running():
            self._scanner.cancel()
            self._scanner.join(timeout=2.0)
        super().closeEvent(event)
