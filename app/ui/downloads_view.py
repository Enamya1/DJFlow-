import os
from typing import List

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QProgressBar, QAbstractItemView, QFrame,
    QMessageBox, QMenu,
)

from app.services.download_service import DownloadManager, DownloadItem, DownloadStatus


class DownloadSignals(QObject):
    updated = Signal()


class DownloadsView(QWidget):
    def __init__(self, download_manager: DownloadManager, parent=None):
        super().__init__(parent)
        self._manager = download_manager
        self._signals = DownloadSignals()
        self._signals.updated.connect(self.refresh)
        self._manager.set_callbacks(
            progress_cb=lambda item: self._signals.updated.emit(),
            finished_cb=lambda item: self._signals.updated.emit(),
        )
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(500)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Downloads")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch()

        self.btn_cancel_all = QPushButton("Cancel All")
        self.btn_cancel_all.setObjectName("DangerButton")
        self.btn_cancel_all.setCursor(Qt.PointingHandCursor)
        self.btn_cancel_all.clicked.connect(self._cancel_all)
        header.addWidget(self.btn_cancel_all)

        self.btn_open_folder = QPushButton("Open Download Folder")
        self.btn_open_folder.setCursor(Qt.PointingHandCursor)
        self.btn_open_folder.clicked.connect(self._open_download_folder)
        header.addWidget(self.btn_open_folder)

        root.addLayout(header)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Title", "Artist", "Status", "Progress", "Speed", "Destination"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 180)
        self.table.setColumnWidth(4, 90)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        root.addWidget(self.table, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("SectionSubtitle")
        root.addWidget(self.status_label)

    def refresh(self) -> None:
        items = self._manager.queue
        current = self._manager.current
        all_items = list(items)
        if current:
            all_items.insert(0, current)

        self.table.setRowCount(len(all_items))
        for row, item in enumerate(all_items):
            self.table.setItem(row, 0, QTableWidgetItem(item.title or os.path.basename(item.destination)))
            self.table.setItem(row, 1, QTableWidgetItem(item.artist))
            status_item = QTableWidgetItem(item.status.capitalize())
            self.table.setItem(row, 2, status_item)

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(item.progress))
            self.table.setCellWidget(row, 3, bar)

            speed = f"{item.speed / 1024:.1f} KB/s" if item.speed else ""
            self.table.setItem(row, 4, QTableWidgetItem(speed))
            self.table.setItem(row, 5, QTableWidgetItem(item.destination))

        completed = sum(1 for i in all_items if i.status == DownloadStatus.COMPLETED.value)
        failed = sum(1 for i in all_items if i.status == DownloadStatus.FAILED.value)
        self.status_label.setText(f"Total: {len(all_items)} | Completed: {completed} | Failed: {failed}")

    def _cancel_all(self) -> None:
        self._manager.cancel_all()
        self.refresh()

    def _on_context_menu(self, pos) -> None:
        index = self.table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        items = self._manager.queue
        current = self._manager.current
        all_items = list(items)
        if current:
            all_items.insert(0, current)
        if row >= len(all_items):
            return
        item = all_items[row]

        menu = QMenu(self)
        if item.status in (DownloadStatus.QUEUED.value, DownloadStatus.DOWNLOADING.value, DownloadStatus.PAUSED.value):
            cancel_action = menu.addAction("Cancel")
            action = menu.exec(self.table.viewport().mapToGlobal(pos))
            if action == cancel_action:
                self._manager.cancel_all()
        elif item.status == DownloadStatus.COMPLETED.value:
            open_action = menu.addAction("Open File Location")
            action = menu.exec(self.table.viewport().mapToGlobal(pos))
            if action == open_action:
                self._open_folder_for(item.destination)

    def _open_folder_for(self, path: str) -> None:
        try:
            if os.name == "nt":
                os.startfile(os.path.dirname(path))
            else:
                import subprocess
                subprocess.Popen(["xdg-open", os.path.dirname(path)])
        except Exception as e:
            QMessageBox.warning(self, "Open Folder", str(e))

    def _open_download_folder(self) -> None:
        from app.config import AppConfig
        folder = AppConfig.instance().get("download_folder", "")
        if folder and os.path.isdir(folder):
            self._open_folder_for(folder)
        else:
            QMessageBox.information(self, "Downloads", "No download folder configured.")
