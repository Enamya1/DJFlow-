import os
import threading
from typing import Optional

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QComboBox, QFileDialog, QFrame, QMessageBox, QDoubleSpinBox, QCheckBox,
    QProgressBar, QSpinBox,
)

from app.config import AppConfig
from app.services import analysis_service
from app.services.filesystem_library import load_track, TrackInfo

from .widgets.waveform_widget import WaveformWidget, AudioPlayer


class AnalysisSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class AnalysisView(QWidget):
    def __init__(self, config: AppConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._track: Optional[TrackInfo] = None
        self._signals = AnalysisSignals()
        self._signals.result.connect(self._on_result)
        self._signals.error.connect(self._on_error)
        self._signals.finished.connect(self._on_finished)
        self._player = AudioPlayer()
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Audio Analysis")
        title.setObjectName("SectionTitle")
        header.addWidget(title)
        header.addStretch()
        root.addLayout(header)

        file_row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("Select an audio file to analyze…")
        self.file_input.setReadOnly(True)
        file_row.addWidget(self.file_input, 1)

        self.btn_browse = QPushButton("Browse…")
        self.btn_browse.setCursor(Qt.PointingHandCursor)
        self.btn_browse.clicked.connect(self._browse)
        file_row.addWidget(self.btn_browse)

        self.btn_analyze = QPushButton("Analyze")
        self.btn_analyze.setObjectName("PrimaryButton")
        self.btn_analyze.setCursor(Qt.PointingHandCursor)
        self.btn_analyze.clicked.connect(self._analyze)
        file_row.addWidget(self.btn_analyze)
        root.addLayout(file_row)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("Analyzing…")
        self.progress.hide()
        root.addWidget(self.progress)

        self.track_label = QLabel("")
        self.track_label.setStyleSheet("color: #ffffff; font-weight: 600;")
        root.addWidget(self.track_label)

        results = QFrame()
        results.setObjectName("Panel")
        rl = QVBoxLayout(results)
        rl.setContentsMargins(16, 16, 16, 16)
        rl.setSpacing(10)

        self.bpm_label = QLabel("BPM: —")
        self.bpm_label.setStyleSheet("color: #22d3ee; font-size: 16px; font-weight: 700;")
        rl.addWidget(self.bpm_label)

        self.bpm_detail = QLabel("")
        self.bpm_detail.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        rl.addWidget(self.bpm_detail)

        self.key_label = QLabel("Key: —")
        self.key_label.setStyleSheet("color: #22d3ee; font-size: 16px; font-weight: 700;")
        rl.addWidget(self.key_label)

        self.key_detail = QLabel("")
        self.key_detail.setStyleSheet("color: #a1a1aa; font-size: 12px;")
        rl.addWidget(self.key_detail)

        self.energy_label = QLabel("Energy: —")
        self.energy_label.setStyleSheet("color: #a1a1aa;")
        rl.addWidget(self.energy_label)

        manual_row = QHBoxLayout()
        manual_row.addWidget(QLabel("Manual BPM:"))
        self.manual_bpm = QDoubleSpinBox()
        self.manual_bpm.setRange(0, 300)
        self.manual_bpm.setDecimals(2)
        self.manual_bpm.setSuffix(" BPM")
        manual_row.addWidget(self.manual_bpm)

        manual_row.addWidget(QLabel("Manual Key:"))
        self.manual_key = QComboBox()
        keys = list(analysis_service.KEYS_MAJOR) + list(analysis_service.KEYS_MINOR)
        self.manual_key.addItems([""] + keys)
        manual_row.addWidget(self.manual_key)
        rl.addLayout(manual_row)

        self.btn_save = QPushButton("Save Corrections to Sidecar")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self._save_corrections)
        rl.addWidget(self.btn_save)

        self.write_tags_check = QCheckBox("Also write to audio tags (if supported)")
        self.write_tags_check.setChecked(self._config.get("write_metadata_to_tags", False))
        rl.addWidget(self.write_tags_check)

        root.addWidget(results)

        player_panel = QFrame()
        player_panel.setObjectName("Panel")
        pl = QVBoxLayout(player_panel)
        pl.setContentsMargins(12, 12, 12, 12)
        pl.setSpacing(8)

        controls = QHBoxLayout()
        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("PrimaryButton")
        self.btn_play.setCursor(Qt.PointingHandCursor)
        self.btn_play.clicked.connect(self._toggle_play)
        controls.addWidget(self.btn_play)

        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setCursor(Qt.PointingHandCursor)
        self.btn_stop.clicked.connect(self._stop)
        controls.addWidget(self.btn_stop)
        controls.addStretch()

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setStyleSheet("color: #a1a1aa;")
        controls.addWidget(self.time_label)
        pl.addLayout(controls)

        self.waveform = WaveformWidget()
        self.waveform.seek_requested.connect(self._on_seek)
        pl.addWidget(self.waveform)
        root.addWidget(player_panel)

        root.addStretch()

        self._player.position_changed.connect(self._on_position)
        self._player.duration_changed.connect(self._on_duration)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Audio File", "",
            "Audio Files (*.mp3 *.wav *.flac *.aac *.m4a *.ogg *.aiff *.aif);;All Files (*)"
        )
        if path:
            self.file_input.setText(path)
            self._track = load_track(path)
            self.track_label.setText(f"{self._track.title} — {self._track.artist or 'Unknown'}")
            if self._track.analyzed:
                self._display_result(self._track)
            self.btn_play.setEnabled(True)

    def _analyze(self) -> None:
        if not self._track:
            QMessageBox.information(self, "Analyze", "Please select an audio file first.")
            return
        self.progress.show()
        self.btn_analyze.setEnabled(False)

        def worker():
            try:
                result = analysis_service.analyze_file(self._track.file_path)
                self._signals.result.emit(result)
            except Exception as e:
                self._signals.error.emit(str(e))
            finally:
                self._signals.finished.emit()

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, result) -> None:
        self._track.bpm = result.bpm
        self._track.bpm_confidence = result.bpm_confidence
        self._track.bpm_half = result.bpm_half
        self._track.bpm_double = result.bpm_double
        self._track.musical_key = result.musical_key
        self._track.camelot_key = result.camelot_key
        self._track.key_confidence = result.key_confidence
        self._track.energy = result.energy
        self._track.analyzed = True
        self._display_result(self._track)

        if self._config.get("create_sidecar_files", True):
            analysis_service.save_sidecar(self._track.file_path, result)

    def _display_result(self, track: TrackInfo) -> None:
        bpm_text = f"{track.bpm:.1f} BPM" if track.bpm else "Unknown"
        if track.bpm_confidence is not None:
            bpm_text += f"  (confidence: {track.bpm_confidence:.0%})"
        self.bpm_label.setText(f"BPM: {bpm_text}")
        half = f"{track.bpm_half:.1f}" if track.bpm_half else "—"
        double = f"{track.bpm_double:.1f}" if track.bpm_double else "—"
        uncertain = "" if (track.bpm_confidence is None or track.bpm_confidence > 0.6) else "  ⚠ Uncertain estimate"
        self.bpm_detail.setText(f"Half-time: {half}  |  Double-time: {double}{uncertain}")

        key_text = f"{track.musical_key} ({track.camelot_key})" if track.musical_key else "Unknown"
        if track.key_confidence is not None:
            key_text += f"  (confidence: {track.key_confidence:.0%})"
        self.key_label.setText(f"Key: {key_text}")
        key_uncertain = "" if (track.key_confidence is None or track.key_confidence > 0.5) else "  ⚠ Uncertain estimate"
        self.key_detail.setText(f"Standard: {track.musical_key or 'Unknown'}  |  Camelot: {track.camelot_key or 'Unknown'}{key_uncertain}")

        self.energy_label.setText(f"Energy: {track.energy:.2f}" if track.energy is not None else "Energy: —")

        self.manual_bpm.setValue(track.bpm or 0)
        idx = self.manual_key.findText(track.musical_key or "")
        self.manual_key.setCurrentIndex(idx if idx >= 0 else 0)

    def _save_corrections(self) -> None:
        if not self._track:
            return
        sidecar = analysis_service.load_sidecar(self._track.file_path) or analysis_service.AnalysisResult()
        manual_bpm = self.manual_bpm.value()
        if manual_bpm > 0:
            sidecar.bpm = manual_bpm
            self._track.bpm = manual_bpm
        manual_key = self.manual_key.currentText()
        if manual_key:
            sidecar.musical_key = manual_key
            sidecar.camelot_key = analysis_service.to_camelot(manual_key)
            self._track.musical_key = manual_key
            self._track.camelot_key = sidecar.camelot_key
        sidecar.manually_corrected = True
        analysis_service.save_sidecar(self._track.file_path, sidecar)

        if self.write_tags_check.isChecked():
            self._write_tags(sidecar)

        QMessageBox.information(self, "Saved", "Corrections saved to sidecar file.")
        self._display_result(self._track)

    def _write_tags(self, sidecar) -> None:
        try:
            from mutagen import File as MutagenFile
            audio = MutagenFile(self._track.file_path)
            if audio is None:
                return
            if sidecar.bpm:
                try:
                    audio["bpm"] = str(int(round(sidecar.bpm)))
                except Exception:
                    pass
            if sidecar.musical_key:
                try:
                    audio["key"] = sidecar.musical_key
                except Exception:
                    pass
            audio.save()
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("Could not write tags: %s", e)

    def _on_error(self, msg: str) -> None:
        QMessageBox.warning(self, "Analysis Error", msg)

    def _on_finished(self) -> None:
        self.progress.hide()
        self.btn_analyze.setEnabled(True)

    def _toggle_play(self) -> None:
        if not self._track:
            return
        if not self._player.duration():
            self._player.load(self._track.file_path)
            self._player.generate_waveform(self._track.file_path, callback=self.waveform.set_peaks)
        if self._player.is_playing():
            self._player.pause()
            self.btn_play.setText("Play")
        else:
            self._player.play()
            self.btn_play.setText("Pause")

    def _stop(self) -> None:
        self._player.stop()
        self.btn_play.setText("Play")
        self.waveform.set_progress(0.0)

    def _on_position(self, pos_ms: int) -> None:
        dur = self._player.duration()
        if dur > 0:
            self.waveform.set_progress(pos_ms / dur)
        self.time_label.setText(f"{self._fmt(pos_ms)} / {self._fmt(dur)}")

    def _on_duration(self, dur_ms: int) -> None:
        self.time_label.setText(f"0:00 / {self._fmt(dur_ms)}")

    def _on_seek(self, progress: float) -> None:
        dur = self._player.duration()
        if dur > 0:
            self._player.seek(int(progress * dur))

    def _fmt(self, ms: int) -> str:
        s = ms // 1000
        m = s // 60
        return f"{m}:{s % 60:02d}"
