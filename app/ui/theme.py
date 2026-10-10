DARK_STYLESHEET = """
QWidget {
    background-color: #1a1a1f;
    color: #e4e4e7;
    font-family: "Segoe UI", "Inter", "Arial", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1a1a1f;
}

/* Sidebar */
#Sidebar {
    background-color: #141418;
    border-right: 1px solid #27272f;
}

#SidebarTitle {
    color: #22d3ee;
    font-size: 18px;
    font-weight: 700;
    padding: 16px 16px 8px 16px;
    letter-spacing: 1px;
}

#SidebarSubtitle {
    color: #71717a;
    font-size: 11px;
    padding: 0 16px 16px 16px;
}

QListWidget#NavList {
    background-color: #141418;
    border: none;
    padding: 8px;
    outline: none;
}

QListWidget#NavList::item {
    color: #a1a1aa;
    padding: 10px 14px;
    margin: 2px 4px;
    border-radius: 8px;
    font-size: 13px;
}

QListWidget#NavList::item:hover {
    background-color: #27272f;
    color: #e4e4e7;
}

QListWidget#NavList::item:selected {
    background-color: #0e7490;
    color: #ffffff;
}

/* Content area */
#ContentArea {
    background-color: #1a1a1f;
}

/* Status bar */
QStatusBar {
    background-color: #141418;
    color: #71717a;
    border-top: 1px solid #27272f;
}

/* Labels */
QLabel#SectionTitle {
    color: #ffffff;
    font-size: 24px;
    font-weight: 700;
}

QLabel#SectionSubtitle {
    color: #71717a;
    font-size: 13px;
}

QLabel#CardTitle {
    color: #a1a1aa;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

QLabel#CardValue {
    color: #ffffff;
    font-size: 30px;
    font-weight: 700;
}

/* Cards */
QFrame#StatCard {
    background-color: #24242b;
    border: 1px solid #2f2f38;
    border-radius: 12px;
}

QFrame#AccentCard {
    background-color: #164e63;
    border: 1px solid #0e7490;
    border-radius: 12px;
}

QFrame#Panel {
    background-color: #24242b;
    border: 1px solid #2f2f38;
    border-radius: 10px;
}

/* Buttons */
QPushButton {
    background-color: #27272f;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #0e7490;
}

QPushButton:disabled {
    color: #52525b;
    background-color: #1f1f25;
    border-color: #27272f;
}

QPushButton#PrimaryButton {
    background-color: #0891b2;
    border-color: #06b6d4;
    color: #ffffff;
}

QPushButton#PrimaryButton:hover {
    background-color: #06b6d4;
}

QPushButton#AccentButton {
    background-color: #6d28d9;
    border-color: #8b5cf6;
    color: #ffffff;
}

QPushButton#AccentButton:hover {
    background-color: #8b5cf6;
}

QPushButton#DangerButton {
    background-color: #7f1d1d;
    border-color: #b91c1c;
    color: #ffffff;
}

QPushButton#DangerButton:hover {
    background-color: #b91c1c;
}

/* Line edits */
QLineEdit {
    background-color: #141418;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 8px 12px;
    color: #e4e4e7;
    selection-background-color: #0e7490;
}

QLineEdit:focus {
    border-color: #06b6d4;
}

QLineEdit:disabled {
    color: #52525b;
    background-color: #1f1f25;
}

/* Combo boxes */
QComboBox {
    background-color: #141418;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 6px 12px;
    color: #e4e4e7;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #52525b;
}

QComboBox:focus {
    border-color: #06b6d4;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1f1f25;
    border: 1px solid #3f3f46;
    selection-background-color: #0e7490;
    color: #e4e4e7;
    outline: none;
}

/* Table */
QTableView {
    background-color: #1a1a1f;
    alternate-background-color: #1f1f25;
    border: 1px solid #2f2f38;
    border-radius: 8px;
    gridline-color: #27272f;
    selection-background-color: #0e7490;
    selection-color: #ffffff;
    outline: none;
}

QHeaderView::section {
    background-color: #24242b;
    color: #a1a1aa;
    border: none;
    border-right: 1px solid #2f2f38;
    border-bottom: 1px solid #2f2f38;
    padding: 10px 8px;
    font-weight: 600;
}

QHeaderView::section:hover {
    background-color: #2f2f38;
    color: #ffffff;
}

QTableCornerButton::section {
    background-color: #24242b;
    border: none;
}

/* Scrollbars */
QScrollBar:vertical {
    background-color: #1a1a1f;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #3f3f46;
    border-radius: 5px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background-color: #52525b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background-color: #1a1a1f;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: #3f3f46;
    border-radius: 5px;
    min-width: 30px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #52525b;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* Spin boxes */
QSpinBox, QDoubleSpinBox {
    background-color: #141418;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 6px 8px;
    color: #e4e4e7;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #06b6d4;
}

/* Progress bar */
QProgressBar {
    background-color: #141418;
    border: 1px solid #2f2f38;
    border-radius: 6px;
    text-align: center;
    color: #e4e4e7;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0891b2;
    border-radius: 5px;
}

/* Tooltips */
QToolTip {
    background-color: #1f1f25;
    color: #e4e4e7;
    border: 1px solid #3f3f46;
    padding: 6px 10px;
    border-radius: 6px;
}

/* Checkbox */
QCheckBox {
    color: #e4e4e7;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #3f3f46;
    background-color: #141418;
}

QCheckBox::indicator:checked {
    background-color: #0891b2;
    border-color: #06b6d4;
}

/* Splitter */
QSplitter::handle {
    background-color: #27272f;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

/* Menu */
QMenu {
    background-color: #1f1f25;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0e7490;
}
"""
