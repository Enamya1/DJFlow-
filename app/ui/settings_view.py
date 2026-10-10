import os
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFileDialog, QFrame, QMessageBox, QSpinBox, QCheckBox, QGroupBox, QComboBox,
)

from app.config import AppConfig


class SettingsView(QWidget):
    def __init__(self, config: AppConfig,
                 on_import_files: Callable,
                 on_import_folder: Callable,
                 on_rescan: Callable,
                 on_settings_changed: Optional[Callable] = None,
                 parent=None):
        super().__init__(parent)
        self._config = config
        self._on_import_files = on_import_files
        self._on_import_folder = on_import_folder
        self._on_rescan = on_rescan
        self._on_settings_changed = on_settings_changed

        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        group_style = (
            "QGroupBox { color: #a1a1aa; border: 1px solid #2f2f38; border-radius: 10px; "
            "margin-top: 12px; padding: 16px; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
        )

        folders_group = QGroupBox("Folders")
        folders_group.setStyleSheet(group_style)
        fg = QVBoxLayout(folders_group)
        fg.setSpacing(10)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Music library folder:"))
        self.library_dir = QLineEdit()
        self.library_dir.setPlaceholderText("No directory selected")
        self.library_dir.setReadOnly(True)
        row1.addWidget(self.library_dir, 1)
        btn1 = QPushButton("Browse…")
        btn1.setCursor(Qt.PointingHandCursor)
        btn1.clicked.connect(lambda: self._choose_dir(self.library_dir, "music_library_folder"))
        row1.addWidget(btn1)
        fg.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Download folder:"))
        self.download_dir = QLineEdit()
        self.download_dir.setPlaceholderText("No directory selected")
        self.download_dir.setReadOnly(True)
        row2.addWidget(self.download_dir, 1)
        btn2 = QPushButton("Browse…")
        btn2.setCursor(Qt.PointingHandCursor)
        btn2.clicked.connect(lambda: self._choose_dir(self.download_dir, "download_folder"))
        row2.addWidget(btn2)
        fg.addLayout(row2)

        self.download_into_library = QCheckBox("Download directly into library folder")
        self.download_into_library.toggled.connect(
            lambda v: self._save("download_into_library", v)
        )
        fg.addWidget(self.download_into_library)

        root.addWidget(folders_group)

        org_group = QGroupBox("Folder Organization")
        org_group.setStyleSheet(group_style)
        og = QVBoxLayout(org_group)
        og.setSpacing(10)

        self.organize_check = QCheckBox("Organize downloads into subfolders")
        self.organize_check.toggled.connect(lambda v: self._save("organize_after_download", v))
        og.addWidget(self.organize_check)

        tpl_row = QHBoxLayout()
        tpl_row.addWidget(QLabel("Folder template:"))
        self.folder_template = QLineEdit()
        self.folder_template.setPlaceholderText("{genre}/{artist}")
        self.folder_template.editingFinished.connect(
            lambda: self._save("folder_template", self.folder_template.text())
        )
        tpl_row.addWidget(self.folder_template, 1)
        og.addLayout(tpl_row)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("File template:"))
        self.file_template = QLineEdit()
        self.file_template.setPlaceholderText("{title} - {artist}")
        self.file_template.editingFinished.connect(
            lambda: self._save("file_template", self.file_template.text())
        )
        file_row.addWidget(self.file_template, 1)
        og.addLayout(file_row)

        hint = QLabel("Available fields: {genre} {artist} {album} {year} {bpm_range} {musical_key} {title}")
        hint.setStyleSheet("color: #71717a; font-size: 11px;")
        og.addWidget(hint)

        fb_row = QHBoxLayout()
        fb_row.addWidget(QLabel("Unknown BPM fallback:"))
        self.unknown_bpm = QLineEdit()
        self.unknown_bpm.editingFinished.connect(
            lambda: self._save("unknown_bpm_fallback", self.unknown_bpm.text())
        )
        fb_row.addWidget(self.unknown_bpm)
        fb_row.addWidget(QLabel("Unknown Key fallback:"))
        self.unknown_key = QLineEdit()
        self.unknown_key.editingFinished.connect(
            lambda: self._save("unknown_key_fallback", self.unknown_key.text())
        )
        fb_row.addWidget(self.unknown_key)
        og.addLayout(fb_row)

        root.addWidget(org_group)

        api_group = QGroupBox("API Credentials")
        api_group.setStyleSheet(group_style)
        ag = QVBoxLayout(api_group)
        ag.setSpacing(10)

        jam_row = QHBoxLayout()
        jam_row.addWidget(QLabel("Jamendo Client ID:"))
        self.jamendo_id = QLineEdit()
        self.jamendo_id.setPlaceholderText("Enter your Jamendo client ID")
        self.jamendo_id.setEchoMode(QLineEdit.Password)
        self.jamendo_id.editingFinished.connect(
            lambda: self._save("jamendo_client_id", self.jamendo_id.text())
        )
        jam_row.addWidget(self.jamendo_id, 1)
        ag.addLayout(jam_row)

        jam_hint = QLabel("Get a free client ID at https://devportal.jamendo.com/")
        jam_hint.setStyleSheet("color: #71717a; font-size: 11px;")
        ag.addWidget(jam_hint)

        root.addWidget(api_group)

        analysis_group = QGroupBox("Audio Analysis")
        analysis_group.setStyleSheet(group_style)
        ang = QVBoxLayout(analysis_group)
        ang.setSpacing(10)

        self.sidecar_check = QCheckBox("Create sidecar JSON files for analysis results")
        self.sidecar_check.toggled.connect(lambda v: self._save("create_sidecar_files", v))
        ang.addWidget(self.sidecar_check)

        self.write_tags_check = QCheckBox("Write analysis results to audio tags (when supported)")
        self.write_tags_check.toggled.connect(lambda v: self._save("write_metadata_to_tags", v))
        ang.addWidget(self.write_tags_check)

        root.addWidget(analysis_group)

        import_group = QGroupBox("Library Import")
        import_group.setStyleSheet(group_style)
        ig = QVBoxLayout(import_group)
        ig.setSpacing(10)

        btn_row = QHBoxLayout()
        self.btn_import_files = QPushButton("Import Files…")
        self.btn_import_files.setObjectName("PrimaryButton")
        self.btn_import_files.setCursor(Qt.PointingHandCursor)
        self.btn_import_files.clicked.connect(self._import_files)

        self.btn_import_folder = QPushButton("Import Folder…")
        self.btn_import_folder.setCursor(Qt.PointingHandCursor)
        self.btn_import_folder.clicked.connect(self._import_folder)

        self.btn_rescan = QPushButton("Rescan Library")
        self.btn_rescan.setCursor(Qt.PointingHandCursor)
        self.btn_rescan.clicked.connect(self._rescan)

        btn_row.addWidget(self.btn_import_files)
        btn_row.addWidget(self.btn_import_folder)
        btn_row.addWidget(self.btn_rescan)
        btn_row.addStretch()
        ig.addLayout(btn_row)

        self.recursive_check = QCheckBox("Scan folders recursively")
        ig.addWidget(self.recursive_check)

        root.addWidget(import_group)

        about_group = QGroupBox("About")
        about_group.setStyleSheet(group_style)
        al = QVBoxLayout(about_group)
        info = QLabel(
            "DJFlow Studio — Phase 2\n"
            "Music discovery, downloads, and audio analysis for DJs.\n\n"
            "Configuration: data/config.json"
        )
        info.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        info.setWordWrap(True)
        al.addWidget(info)
        root.addWidget(about_group)

        root.addStretch()

    def _load_settings(self) -> None:
        self.library_dir.setText(self._config.get("music_library_folder", "") or "")
        self.download_dir.setText(self._config.get("download_folder", "") or "")
        self.download_into_library.setChecked(self._config.get("download_into_library", False))
        self.organize_check.setChecked(self._config.get("organize_after_download", True))
        self.folder_template.setText(self._config.get("folder_template", "{genre}/{artist}"))
        self.file_template.setText(self._config.get("file_template", "{title} - {artist}"))
        self.unknown_bpm.setText(self._config.get("unknown_bpm_fallback", "Unknown BPM"))
        self.unknown_key.setText(self._config.get("unknown_key_fallback", "Unknown Key"))
        self.jamendo_id.setText(self._config.get("jamendo_client_id", ""))
        self.sidecar_check.setChecked(self._config.get("create_sidecar_files", True))
        self.write_tags_check.setChecked(self._config.get("write_metadata_to_tags", False))
        self.recursive_check.setChecked(True)

    def _save(self, key: str, value) -> None:
        self._config.set(key, value)
        if self._on_settings_changed:
            self._on_settings_changed()

    def _choose_dir(self, line_edit: QLineEdit, config_key: str) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            line_edit.setText(directory)
            self._save(config_key, directory)

    def _import_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Import Audio Files", "",
            "Audio Files (*.mp3 *.wav *.flac *.aac *.m4a *.ogg *.aiff *.aif);;All Files (*)"
        )
        if files:
            self._on_import_files(files)

    def _import_folder(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Import Music Folder")
        if directory:
            self._on_import_folder(directory, self.recursive_check.isChecked())

    def _rescan(self) -> None:
        self._on_rescan()

    def is_recursive(self) -> bool:
        return self.recursive_check.isChecked()
