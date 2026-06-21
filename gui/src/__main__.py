import sys
import os
import json
import traceback

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QIcon

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

    # Modern dark theme
    app.setStyleSheet("""
        * {
            background-color: #1e1e2e;
            color: #cdd6f4;
            font-family: "Segoe UI", "Ubuntu", sans-serif;
            font-size: 13px;
        }
        QMainWindow {
            background-color: #181825;
        }
        QMenuBar {
            background-color: #11111b;
            padding: 2px;
        }
        QMenuBar::item:selected {
            background-color: #45475a;
            border-radius: 4px;
        }
        QMenu {
            background-color: #1e1e2e;
            border: 1px solid #45475a;
            padding: 4px;
        }
        QMenu::item:selected {
            background-color: #45475a;
            border-radius: 4px;
        }
        QPushButton {
            background-color: #45475a;
            border: none;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #585b70;
        }
        QPushButton:pressed {
            background-color: #313244;
        }
        QPushButton:disabled {
            background-color: #313244;
            color: #6c7086;
        }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background-color: #313244;
            border: 1px solid #45475a;
            border-radius: 4px;
            padding: 6px;
        }
        QComboBox::drop-down {
            border: none;
            padding-right: 8px;
        }
        QComboBox QAbstractItemView {
            background-color: #1e1e2e;
            selection-background-color: #45475a;
        }
        QTabWidget::pane {
            border: 1px solid #45475a;
            border-radius: 6px;
            background-color: #1e1e2e;
        }
        QTabBar::tab {
            background-color: #313244;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }
        QTabBar::tab:selected {
            background-color: #45475a;
        }
        QTabBar::tab:hover {
            background-color: #585b70;
        }
        QGroupBox {
            border: 1px solid #45475a;
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 6px;
            color: #89b4fa;
        }
        QProgressBar {
            background-color: #313244;
            border: none;
            border-radius: 4px;
            height: 10px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #89b4fa;
            border-radius: 4px;
        }
        QScrollBar:vertical {
            background-color: #1e1e2e;
            width: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background-color: #45475a;
            border-radius: 5px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #585b70;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar:horizontal {
            background-color: #1e1e2e;
            height: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:horizontal {
            background-color: #45475a;
            border-radius: 5px;
            min-width: 30px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            width: 0px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #45475a;
            border-radius: 4px;
            background-color: #313244;
        }
        QCheckBox::indicator:checked {
            background-color: #89b4fa;
            border-color: #89b4fa;
        }
        QSplitter::handle {
            background-color: #45475a;
            width: 2px;
        }
        QLabel#statusLabel {
            color: #a6adc8;
        }
        QFrame[frameShape="4"] {
            color: #45475a;
        }
    """)

    settings = QSettings()

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
