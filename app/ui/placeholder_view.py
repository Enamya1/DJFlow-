from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame


class PlaceholderView(QWidget):
    def __init__(self, title: str, description: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 48, 48, 48)
        layout.setSpacing(16)

        card = QFrame()
        card.setObjectName("Panel")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 32, 32, 32)
        card_layout.setSpacing(12)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")

        subtitle = QLabel(description)
        subtitle.setObjectName("SectionSubtitle")
        subtitle.setWordWrap(True)

        coming = QLabel("Coming in a future phase.")
        coming.setStyleSheet("color: #06b6d4; font-size: 12px;")

        card_layout.addWidget(title_label)
        card_layout.addWidget(subtitle)
        card_layout.addWidget(coming)
        card_layout.addStretch()

        layout.addWidget(card)
        layout.addStretch()
