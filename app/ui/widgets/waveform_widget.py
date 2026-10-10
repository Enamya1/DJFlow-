import logging
import threading
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QPainter, QColor, QPen, QBrush
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class WaveformWidget(QWidget):
    seek_requested = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._peaks: Optional[np.ndarray] = None
        self._progress = 0.0
        self.setMinimumHeight(80)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)

    def set_peaks(self, peaks: np.ndarray) -> None:
        self._peaks = peaks
        self.update()

    def set_progress(self, progress: float) -> None:
        self._progress = max(0.0, min(1.0, progress))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        painter.fillRect(self.rect(), QColor("#141418"))

        if self._peaks is None or len(self._peaks) == 0:
            painter.setPen(QColor("#3f3f46"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No waveform")
            return

        mid = h / 2
        n = len(self._peaks)
        bar_width = max(1, w // n)
        progress_x = int(self._progress * w)

        for i in range(n):
            peak = float(self._peaks[i])
            bar_h = int(peak * (h * 0.45))
            x = int(i * w / n)
            color = QColor("#22d3ee") if x < progress_x else QColor("#3f3f46")
            painter.setPen(QPen(color))
            painter.drawLine(x, int(mid - bar_h), x, int(mid + bar_h))

        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawLine(progress_x, 0, progress_x, h)

    def mousePressEvent(self, event):
        if self._peaks is None:
            return
        progress = event.position().x() / max(1, self.width())
        self.seek_requested.emit(max(0.0, min(1.0, progress)))


class AudioPlayer(QObject):
    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)
        self._audio.setVolume(0.8)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.errorOccurred.connect(self._on_error)
        self._waveform_thread: Optional[threading.Thread] = None

    def _on_error(self, error, error_string):
        self.error_occurred.emit(str(error_string))

    def _on_position_changed(self, position):
        self.position_changed.emit(int(position))

    def _on_duration_changed(self, duration):
        self.duration_changed.emit(int(duration))

    def _on_state_changed(self, state):
        self.state_changed.emit(state)

    def load(self, source: str) -> None:
        url = QUrl(source) if source.startswith(("http://", "https://")) else QUrl.fromLocalFile(source)
        self._player.setSource(url)

    def play(self) -> None:
        self._player.play()

    def pause(self) -> None:
        self._player.pause()

    def stop(self) -> None:
        self._player.stop()

    def seek(self, position_ms: int) -> None:
        self._player.setPosition(max(0, position_ms))

    def set_volume(self, volume: float) -> None:
        self._audio.setVolume(max(0.0, min(1.0, volume)))

    def volume(self) -> float:
        return self._audio.volume()

    def position(self) -> int:
        return self._player.position()

    def duration(self) -> int:
        return self._player.duration()

    def is_playing(self) -> bool:
        return self._player.playbackState() == QMediaPlayer.PlayingState

    def generate_waveform(self, file_path: str, bins: int = 300, callback=None) -> None:
        def worker():
            try:
                import librosa
                y, sr = librosa.load(file_path, sr=None, mono=True)
                if len(y) == 0:
                    peaks = np.zeros(bins)
                else:
                    hop = max(1, len(y) // bins)
                    peaks = np.array([
                        float(np.max(np.abs(y[i:i + hop]))) if i < len(y) else 0.0
                        for i in range(0, len(y), hop)
                    ])
                    if len(peaks) != bins:
                        peaks = np.resize(peaks, bins)
                    max_peak = peaks.max() if peaks.max() > 0 else 1.0
                    peaks = peaks / max_peak
                if callback:
                    callback(peaks)
            except Exception as e:
                logger.warning("Waveform generation failed: %s", e)
                if callback:
                    callback(None)

        self._waveform_thread = threading.Thread(target=worker, daemon=True)
        self._waveform_thread.start()
