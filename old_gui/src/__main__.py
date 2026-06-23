import os
import sys
import traceback

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QMessageBox
from src.main_window import MainWindow


def exception_hook(exc_type, exc_value, exc_traceback):
    """Global exception handler to show errors in a message box."""
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(f"Uncaught exception:\n{error_msg}", file=sys.stderr)
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setWindowTitle("Unexpected Error")
    error_box.setText("An unexpected error occurred:")
    error_box.setDetailedText(error_msg)
    error_box.exec()


def main():
    sys.excepthook = exception_hook

    app = QApplication(sys.argv)
    app.setApplicationName("MangaJaNaiConverter")
    app.setOrganizationName("MangaJaNai")
    app.setOrganizationDomain("mangajanai.com")

    qss_path = os.path.join(os.path.dirname(__file__), "dark_theme.qss")
    if os.path.exists(qss_path):
        with open(qss_path) as f:
            app.setStyleSheet(f.read())

    QSettings()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
