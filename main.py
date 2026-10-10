import sys
import os

from app.utils.logging_config import setup_logging


def main() -> int:
    setup_logging()

    os.environ.setdefault("QT_QPA_PLATFORM", "windows")

    from PySide6.QtWidgets import QApplication

    from app.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("DJFlow Studio")
    app.setOrganizationName("DJFlow")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
