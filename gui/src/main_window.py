import os
import sys
import json
import subprocess
import time
import shutil
import signal
import select
from typing import Optional, List
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QProgressBar,
    QMessageBox,
    QScrollArea,
    QFrame,
    QTextEdit,
    QFormLayout,
    QRadioButton,
    QInputDialog,
    QSizePolicy,
    QSlider,
    QTabWidget,
    QToolButton,
    QGroupBox,
    QCompleter,
    QDockWidget,
    QStackedWidget,
    QApplication,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMimeData, QSize, QTimer
from PyQt6.QtGui import QFont, QColor, QDragEnterEvent, QDropEvent

from src.models import AppSettings, UpscaleWorkflow, UpscaleChain, ReaderDevice
from src.gpu_detection import get_gpu_info, get_available_models

COMMON_RESOLUTIONS = [
    "0x0",
    "0x480",
    "0x600",
    "0x720",
    "0x768",
    "0x800",
    "0x900",
    "0x1024",
    "0x1080",
    "0x1200",
    "0x1250",
    "0x1280",
    "0x1300",
    "0x1350",
    "0x1400",
    "0x1440",
    "0x1450",
    "0x1500",
    "0x1536",
    "0x1550",
    "0x1600",
    "0x1760",
    "0x1761",
    "0x1800",
    "0x1920",
    "0x1984",
    "0x2048",
    "0x2160",
    "0x2560",
    "0x2880",
    "0x3072",
    "0x3840",
]


class HelpLabel(QLabel):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setWordWrap(True)
        self.setProperty("class", "HelpLabel")
        self.setMaximumWidth(700)
        self.setMinimumWidth(400)


class BorderFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setProperty("class", "BorderFrame")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(12)

    def layout(self):
        return self._layout


class ToggleButton(QPushButton):
    def __init__(self, text, checked=False, parent=None):
        super().__init__(text, parent)
        self.setProperty("class", "ToggleButton")
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedHeight(32)
        self.setMinimumWidth(90)


class DropLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "DropLineEdit")
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.setText(url.toLocalFile())
                break


class UpscaleWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, python_path, script_path, settings_path):
        super().__init__()
        self.python_path = python_path
        self.script_path = script_path
        self.settings_path = settings_path
        self._stop_requested = False
        self.process = None

    def stop(self):
        self._stop_requested = True
        if self.process:
            self.process.terminate()

    def run(self):
        try:
            self.progress.emit("Starting upscaler...")
            cmd = [self.python_path, self.script_path, "--settings", self.settings_path]
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            # Use non-blocking reads so we can check _stop_requested
            fd = self.process.stdout.fileno()
            import fcntl, os
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

            buf = ""
            while True:
                if self._stop_requested:
                    self._kill_process()
                    self.finished.emit(False, "Cancelled by user")
                    return

                # Check if process ended
                if self.process.poll() is not None:
                    # Read any remaining output
                    try:
                        chunk = self.process.stdout.read()
                        if chunk:
                            for line in chunk.splitlines():
                                self.progress.emit(line)
                    except Exception:
                        pass
                    break

                # Non-blocking read
                try:
                    ready, _, _ = select.select([fd], [], [], 0.5)
                    if ready:
                        data = os.read(fd, 4096)
                        if data:
                            buf += data.decode("utf-8", errors="replace")
                            while "\n" in buf:
                                line, buf = buf.split("\n", 1)
                                self.progress.emit(line.strip())
                    else:
                        # No output available, loop back and check stop flag
                        pass
                except Exception:
                    time.sleep(0.1)

            rc = self.process.wait()
            if rc == 0:
                self.finished.emit(True, "Upscale completed successfully")
            else:
                self.finished.emit(False, f"Upscale failed with code {rc}")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

    def _kill_process(self):
        if self.process:
            killed = False
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                    killed = True
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                    killed = True
            except Exception:
                pass
            if killed:
                self._reset_gpu()

    def _reset_gpu(self):
        self.progress.emit("GPU VRAM may still be in use (ROCm limitation) — ")
        self.progress.emit("stuck VRAM clears on reboot, or run: sudo rocm-smi --gpureset --gpu 0")
        self.progress.emit("Warning: gpureset may freeze your desktop")


class ChainWidget(QWidget):
    def __init__(self, chain, models, chain_num, is_default=False, parent=None):
        super().__init__(parent)
        self.chain = chain
        self.models = models
        self.chain_num = chain_num
        self.is_default = is_default
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(5)

        header = QHBoxLayout()
        title = QLabel(f"Chain {self.chain_num}")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        if not self.is_default:
            self.remove_btn = QPushButton("Remove Chain")
            self.remove_btn.setObjectName("removeChainBtn")
            header.addWidget(self.remove_btn)
        main_layout.addLayout(header)

        act_group = BorderFrame()
        act_layout = act_group.layout()
        act_layout.setSpacing(8)

        act_label = QLabel("Activation Condition")
        act_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        act_layout.addWidget(act_label)

        res_layout = QHBoxLayout()
        res_layout.addWidget(QLabel("Resolution Range"))
        self.min_res = QComboBox()
        self.min_res.setEditable(True)
        self.min_res.addItems(COMMON_RESOLUTIONS)
        self.min_res.setEditText(self.chain.min_resolution)
        self.min_res.setFixedWidth(120)
        res_layout.addWidget(self.min_res)
        res_layout.addWidget(QLabel("px"))
        res_layout.addWidget(QLabel(" - "))
        self.max_res = QComboBox()
        self.max_res.setEditable(True)
        self.max_res.addItems(COMMON_RESOLUTIONS)
        self.max_res.setEditText(self.chain.max_resolution)
        self.max_res.setFixedWidth(120)
        res_layout.addWidget(self.max_res)
        res_layout.addWidget(QLabel("px"))
        res_layout.addStretch()
        res_layout.addWidget(
            HelpLabel(
                "Range of image resolutions to activate this chain. 0 means any value."
            )
        )
        act_layout.addLayout(res_layout)

        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scaling Factor Range"))
        self.min_scale = QSpinBox()
        self.min_scale.setRange(0, 999)
        self.min_scale.setValue(self.chain.min_scale_factor)
        self.min_scale.setFixedWidth(80)
        scale_layout.addWidget(self.min_scale)
        scale_layout.addWidget(QLabel("x  -  "))
        self.max_scale = QSpinBox()
        self.max_scale.setRange(0, 999)
        self.max_scale.setValue(self.chain.max_scale_factor)
        self.max_scale.setFixedWidth(80)
        scale_layout.addWidget(self.max_scale)
        scale_layout.addWidget(QLabel("x"))
        scale_layout.addStretch()
        scale_layout.addWidget(
            HelpLabel(
                "Range of scaling factors to activate this chain. 0 means no limit."
            )
        )
        act_layout.addLayout(scale_layout)

        type_layout = QHBoxLayout()
        self.is_color = QCheckBox("Is Color Image")
        self.is_color.setChecked(self.chain.is_color)
        type_layout.addWidget(self.is_color)
        self.is_grayscale = QCheckBox("Is Grayscale Image")
        self.is_grayscale.setChecked(self.chain.is_grayscale)
        type_layout.addWidget(self.is_grayscale)
        type_layout.addStretch()
        type_layout.addWidget(
            HelpLabel(
                "Images that appear grayscale but have faint color due to JPEG artifacts are still considered grayscale."
            )
        )
        act_layout.addLayout(type_layout)

        main_layout.addWidget(act_group)

        upscale_group = BorderFrame()
        upscale_layout = upscale_group.layout()
        upscale_layout.setSpacing(8)

        upscale_label = QLabel("Upscale Settings")
        upscale_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        upscale_layout.addWidget(upscale_label)

        self.auto_levels = QCheckBox("Auto Adjust Levels on Grayscale Images")
        self.auto_levels.setChecked(self.chain.auto_adjust_levels)
        upscale_layout.addWidget(self.auto_levels)
        upscale_layout.addWidget(
            HelpLabel(
                "Automatically increase contrast of grayscale images if necessary. Recommended for faded images. No effect on color images."
            )
        )

        rh_layout = QHBoxLayout()
        rh_layout.addWidget(QLabel("Resize Height Before Upscale"))
        self.resize_h = QSpinBox()
        self.resize_h.setRange(0, 99999)
        self.resize_h.setValue(self.chain.resize_height_before_upscale)
        self.resize_h.setFixedWidth(100)
        rh_layout.addWidget(self.resize_h)
        rh_layout.addWidget(QLabel("px"))
        rh_layout.addStretch()
        rh_layout.addWidget(
            HelpLabel(
                "Resize each image to this height before upscaling. Set to 0 to disable."
            )
        )
        upscale_layout.addLayout(rh_layout)

        rw_layout = QHBoxLayout()
        rw_layout.addWidget(QLabel("Resize Width Before Upscale"))
        self.resize_w = QSpinBox()
        self.resize_w.setRange(0, 99999)
        self.resize_w.setValue(self.chain.resize_width_before_upscale)
        self.resize_w.setFixedWidth(100)
        rw_layout.addWidget(self.resize_w)
        rw_layout.addWidget(QLabel("px"))
        rw_layout.addStretch()
        rw_layout.addWidget(
            HelpLabel(
                "Resize each image to this width before upscaling. Set to 0 to disable."
            )
        )
        upscale_layout.addLayout(rw_layout)

        rf_layout = QHBoxLayout()
        rf_layout.addWidget(QLabel("Resize Factor Before Upscale"))
        self.resize_f = QDoubleSpinBox()
        self.resize_f.setRange(0, 1000)
        self.resize_f.setValue(self.chain.resize_factor_before_upscale)
        self.resize_f.setFixedWidth(100)
        rf_layout.addWidget(self.resize_f)
        rf_layout.addWidget(QLabel("%"))
        rf_layout.addStretch()
        rf_layout.addWidget(
            HelpLabel(
                "Resize each image by this factor before upscaling. Ignored if Resize Height is specified."
            )
        )
        upscale_layout.addLayout(rf_layout)

        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model"))
        self.model_combo = QComboBox()
        self.model_combo.addItems([""] + self.models)
        idx = self.model_combo.findText(self.chain.model_file_path)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.setFixedWidth(400)
        model_layout.addWidget(self.model_combo)
        open_models_btn = QPushButton("📂 Open Models Dir")
        open_models_btn.clicked.connect(self._open_models_dir)
        model_layout.addWidget(open_models_btn)
        model_layout.addStretch()
        model_layout.addWidget(
            HelpLabel(
                "The upscaling model to run. Add PyTorch (.pth) model files to the models directory to add more options."
            )
        )
        upscale_layout.addLayout(model_layout)

        tile_layout = QHBoxLayout()
        tile_layout.addWidget(QLabel("Model Tile Size"))
        self.tile_size = QComboBox()
        self.tile_size.setEditable(True)
        self.tile_size.addItems(["Auto (Estimate)", "256", "512", "1024", "2048"])
        idx = self.tile_size.findText(self.chain.model_tile_size)
        if idx >= 0:
            self.tile_size.setCurrentIndex(idx)
        self.tile_size.setFixedWidth(160)
        tile_layout.addWidget(self.tile_size)
        tile_layout.addWidget(QLabel("px"))
        tile_layout.addStretch()
        tile_layout.addWidget(
            HelpLabel(
                "Tile size for upscaling. Image is cut into tiles to avoid VRAM limits. Larger is better when GPU has enough VRAM. Auto estimates the largest usable size."
            )
        )
        upscale_layout.addLayout(tile_layout)

        main_layout.addWidget(upscale_group)

    def _open_models_dir(self):
        models_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        )
        models_dir = os.path.join(models_dir, "current", "backend", "models")
        if os.path.exists(models_dir):
            if sys.platform == "linux":
                subprocess.Popen(["xdg-open", models_dir])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", models_dir])
            else:
                os.startfile(models_dir)

    def get_chain(self):
        self.chain.min_resolution = self.min_res.currentText()
        self.chain.max_resolution = self.max_res.currentText()
        self.chain.min_scale_factor = self.min_scale.value()
        self.chain.max_scale_factor = self.max_scale.value()
        self.chain.is_color = self.is_color.isChecked()
        self.chain.is_grayscale = self.is_grayscale.isChecked()
        self.chain.auto_adjust_levels = self.auto_levels.isChecked()
        self.chain.resize_height_before_upscale = self.resize_h.value()
        self.chain.resize_width_before_upscale = self.resize_w.value()
        self.chain.resize_factor_before_upscale = self.resize_f.value()
        self.chain.model_file_path = self.model_combo.currentText()
        self.chain.model_tile_size = self.tile_size.currentText()
        return self.chain


class AppSettingsWidget(QWidget):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("App Settings")
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(15)

        header = QHBoxLayout()
        title = QLabel("App Settings")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()
        close_btn = QPushButton("✕ Close")
        close_btn.setFixedWidth(90)
        close_btn.setObjectName("closeBtn")
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        main_layout.addLayout(header)

        device_group = BorderFrame()
        device_layout = device_group.layout()
        device_layout.setSpacing(12)

        dev_label = QLabel("Device")
        dev_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        device_layout.addWidget(dev_label)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["CPU", "GPU (AMD ROCm)"])
        if self.settings.use_cpu:
            self.device_combo.setCurrentIndex(0)
        else:
            self.device_combo.setCurrentIndex(1)
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(
            HelpLabel(
                "Which device to use for upscaling. CPU is much slower than GPU and should be avoided unless no GPU is available."
            )
        )

        self.fp16_check = QCheckBox("FP16 Mode")
        self.fp16_check.setChecked(self.settings.use_fp16)
        device_layout.addWidget(self.fp16_check)
        device_layout.addWidget(
            HelpLabel(
                "Runs upscaling in FP16 mode for less VRAM usage and speedup on supported GPUs."
            )
        )

        main_layout.addWidget(device_group)

        models_group = BorderFrame()
        models_layout = models_group.layout()
        models_layout.setSpacing(12)

        models_label = QLabel("Models Directory")
        models_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        models_layout.addWidget(models_label)

        models_row = QHBoxLayout()
        self.models_path = QLineEdit(self.settings.models_directory)
        models_row.addWidget(self.models_path)
        browse_models_btn = QPushButton("Browse")
        browse_models_btn.clicked.connect(self._browse_models)
        models_row.addWidget(browse_models_btn)
        models_layout.addLayout(models_row)

        main_layout.addWidget(models_group)

        apply_btn = QPushButton("Apply Changes")
        apply_btn.setObjectName("applyBtn")
        apply_btn.clicked.connect(self._apply_and_close)
        main_layout.addWidget(apply_btn, alignment=Qt.AlignmentFlag.AlignRight)

        main_layout.addStretch()

    def _browse_models(self):
        path = QFileDialog.getExistingDirectory(self, "Select Models Directory")
        if path:
            self.models_path.setText(path)

    def _apply_and_close(self):
        self.settings.use_cpu = self.device_combo.currentIndex() == 0
        self.settings.selected_device_index = 1 if not self.settings.use_cpu else 0
        self.settings.use_fp16 = self.fp16_check.isChecked()
        self.settings.models_directory = self.models_path.text()
        self.hide()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = None
        self.models = []
        self.devices = []
        self.worker = None
        self.start_time = None
        self.total_files = 0
        self.processed_files = 0
        self._setup_ui()
        self._load_settings()
        self._detect_gpu()

    def _setup_ui(self):
        self.setWindowTitle("MangaJaNaiConverterGui")
        self.resize(1600, 1050)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.app_settings_widget = None

        self._setup_sidebar(main_layout)
        self._setup_main_area(main_layout)

    def _setup_sidebar(self, layout):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 0)

        default_label = QLabel("Default Workflows")
        default_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        content_layout.addWidget(default_label)

        self.workflow_buttons = []
        self.default_workflow_btn = QPushButton("📖 Upscale Manga (Default)")
        self.default_workflow_btn.setCheckable(True)
        self.default_workflow_btn.setChecked(True)
        self.default_workflow_btn.setProperty("workflow_index", 0)
        self.default_workflow_btn.setProperty("class", "SidebarBtn")
        self.default_workflow_btn.clicked.connect(lambda: self._select_workflow(0))
        self.workflow_buttons.append(self.default_workflow_btn)
        content_layout.addWidget(self.default_workflow_btn)

        custom_header = QHBoxLayout()
        custom_label = QLabel("Custom Workflows")
        custom_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        custom_header.addWidget(custom_label)
        custom_header.addStretch()
        add_custom_btn = QPushButton("＋ Add")
        add_custom_btn.setFixedWidth(80)
        add_custom_btn.setFixedHeight(30)
        add_custom_btn.setToolTip("Add custom workflow")
        add_custom_btn.setObjectName("addCustomBtn")
        add_custom_btn.clicked.connect(self._add_workflow)
        custom_header.addWidget(add_custom_btn)
        content_layout.addLayout(custom_header)

        self.custom_workflows_list = QVBoxLayout()
        content_layout.addLayout(self.custom_workflows_list)
        content_layout.addStretch()
        sidebar_layout.addWidget(content)

        self.app_settings_btn = QPushButton("⚙ App Settings")
        self.app_settings_btn.setObjectName("appSettingsBtn")
        self.app_settings_btn.clicked.connect(self._show_app_settings)
        sidebar_layout.addWidget(self.app_settings_btn)

        layout.addWidget(sidebar)

    def _populate_sidebar_workflows(self):
        """Populate sidebar with all workflows from settings."""
        # Clear existing custom workflow buttons
        for i in reversed(range(self.custom_workflows_list.count())):
            widget = self.custom_workflows_list.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self.workflow_buttons = [self.default_workflow_btn]

        if not self.settings:
            return

        for i, wf in enumerate(self.settings.workflows):
            if wf.workflow_name == "Upscale Manga (Default)":
                continue

            btn = QPushButton(f"⚙ {wf.workflow_name}")
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.setProperty("workflow_index", i)
            btn.setProperty("class", "SidebarBtn")
            btn.clicked.connect(lambda checked, idx=i: self._select_workflow(idx))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, b=btn: self._show_workflow_context_menu(pos, b)
            )
            self.custom_workflows_list.addWidget(btn)
            self.workflow_buttons.append(btn)

    def _show_workflow_context_menu(self, pos, btn):
        """Show context menu for workflow rename/delete."""
        from PyQt6.QtGui import QAction

        menu = self.contextMenu() if hasattr(self, "contextMenu") else None
        if menu is None:
            menu = type("", (), {"exec": lambda self, p: None})()

        idx = btn.property("workflow_index")

        rename_action = QAction("Rename", self)
        rename_action.triggered.connect(lambda: self._rename_workflow(idx))

        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(lambda: self._delete_workflow(idx))

        menu = type(
            "", (), {"exec": lambda self, p: None, "addAction": lambda self, a: None}
        )()

        # Use QMenu properly
        from PyQt6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.addAction(rename_action)
        menu.addAction(delete_action)
        menu.exec(btn.mapToGlobal(pos))

    def _rename_workflow(self, index):
        """Rename a workflow."""
        if not self.settings or index >= len(self.settings.workflows):
            return

        wf = self.settings.workflows[index]
        new_name, ok = QInputDialog.getText(
            self, "Rename Workflow", "Workflow name:", text=wf.workflow_name
        )
        if ok and new_name.strip():
            wf.workflow_name = new_name.strip()
            self._populate_sidebar_workflows()
            # Re-select the renamed workflow
            for btn in self.workflow_buttons:
                if btn.property("workflow_index") == index:
                    btn.setChecked(True)
                    break

    def _delete_workflow(self, index):
        """Delete a workflow."""
        if not self.settings or index >= len(self.settings.workflows):
            return

        wf = self.settings.workflows[index]
        reply = QMessageBox.question(
            self,
            "Delete Workflow",
            f"Delete '{wf.workflow_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.settings.workflows.pop(index)
            self._populate_sidebar_workflows()
            # Select default workflow
            self._select_workflow(0)

    def _setup_main_area(self, layout):
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.setHandleWidth(4)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        main_area = QWidget()
        main_area_layout = QVBoxLayout(main_area)
        main_area_layout.setContentsMargins(20, 10, 20, 10)
        main_area_layout.setSpacing(10)

        self._setup_workflow_header(main_area_layout)
        self._setup_input_output(main_area_layout)
        self._setup_upscaling(main_area_layout)
        self._setup_advanced(main_area_layout)

        scroll_area.setWidget(main_area)
        self.main_splitter.addWidget(scroll_area)

        self._setup_console_panel()
        self._setup_bottom_bar()

        self.main_splitter.setSizes([600, 300, 50])
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setStretchFactor(2, 0)

        layout.addWidget(self.main_splitter, 1)

    def _setup_console_panel(self):
        console_panel = QWidget()
        console_layout = QVBoxLayout(console_panel)
        console_layout.setContentsMargins(10, 5, 10, 5)
        console_layout.setSpacing(5)

        console_header = QHBoxLayout()
        console_title = QLabel("Console")
        console_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        console_header.addWidget(console_title)
        console_header.addStretch()

        self.show_console_btn = QPushButton("Show/Hide")
        self.show_console_btn.setCheckable(True)
        self.show_console_btn.setChecked(True)
        self.show_console_btn.setObjectName("showConsoleBtn")
        self.show_console_btn.clicked.connect(
            lambda: self.console_section.setVisible(self.show_console_btn.isChecked())
        )
        console_header.addWidget(self.show_console_btn)

        close_console = QPushButton("✕")
        close_console.setFixedWidth(30)
        close_console.setObjectName("closeConsoleBtn")
        close_console.clicked.connect(lambda: self.console_section.hide())
        console_header.addWidget(close_console)

        console_layout.addLayout(console_header)

        self.console_section = QWidget()
        console_inner = QVBoxLayout(self.console_section)
        console_inner.setContentsMargins(0, 0, 0, 0)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Consolas", 10))
        self.console.setObjectName("console")
        console_inner.addWidget(self.console)

        console_layout.addWidget(self.console_section)

        self.main_splitter.addWidget(console_panel)

    def _setup_bottom_bar(self):
        bottom = QWidget()
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(10, 5, 10, 5)

        self.upscale_btn = QPushButton("▶ Upscale")
        self.upscale_btn.setObjectName("upscaleBtn")
        self.upscale_btn.clicked.connect(self._start_upscale)
        bottom_layout.addWidget(self.upscale_btn)

        self.cancel_btn = QPushButton("⏹ Cancel")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_upscale)
        bottom_layout.addWidget(self.cancel_btn)

        bottom_layout.addStretch()

        self.status_left = QLabel("Ready")
        bottom_layout.addWidget(self.status_left)

        self.elapsed_label = QLabel("Elapsed: 00:00:00")
        bottom_layout.addWidget(self.elapsed_label)

        self.etr_label = QLabel("ETR: --:--:--")
        bottom_layout.addWidget(self.etr_label)

        self.eta_label = QLabel("ETA: --:--:--")
        bottom_layout.addWidget(self.eta_label)

        self.archive_progress = QProgressBar()
        self.archive_progress.setFixedWidth(250)
        self.archive_progress.setRange(0, 100)
        self.archive_progress.setValue(0)
        self.archive_progress.setTextVisible(True)
        self.archive_progress.setFormat("%v / %m images")
        bottom_layout.addWidget(self.archive_progress)

        self.total_progress = QProgressBar()
        self.total_progress.setFixedWidth(250)
        self.total_progress.setRange(0, 100)
        self.total_progress.setValue(0)
        self.total_progress.setTextVisible(True)
        self.total_progress.setFormat("%v / %m total")
        self.total_progress.setObjectName("totalProgress")
        bottom_layout.addWidget(self.total_progress)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._update_timer)

        self.main_splitter.addWidget(bottom)

    def _update_timer(self):
        if self.start_time:
            elapsed = time.time() - self.start_time
            self.elapsed_label.setText(f"Elapsed: {timedelta(seconds=int(elapsed))}")

            if self.processed_files > 0 and self.total_files > 0:
                rate = self.processed_files / elapsed
                remaining = (self.total_files - self.processed_files) / rate
                if remaining > 0:
                    self.etr_label.setText(f"ETR: {timedelta(seconds=int(remaining))}")
                    eta = datetime.now() + timedelta(seconds=int(remaining))
                    self.eta_label.setText(f"ETA: {eta.strftime('%H:%M:%S')}")

    def _setup_workflow_header(self, layout):
        header = QHBoxLayout()
        header.addWidget(QLabel("Workflow Name"))
        self.wf_name = QLineEdit()
        self.wf_name.setFixedWidth(500)
        header.addWidget(self.wf_name)
        header.addStretch()

        btn_layout = QHBoxLayout()
        self.import_btn = QPushButton("📥 Import Workflow")
        self.import_btn.clicked.connect(self._import_workflow)
        btn_layout.addWidget(self.import_btn)

        self.export_btn = QPushButton("📤 Export Workflow")
        self.export_btn.clicked.connect(self._export_workflow)
        btn_layout.addWidget(self.export_btn)

        self.reset_btn = QPushButton("🔄 Reset Workflow")
        self.reset_btn.setToolTip(
            "Reset to official default settings from the MangaJaNaiConverterGui repository"
        )
        self.reset_btn.clicked.connect(self._reset_workflow)
        btn_layout.addWidget(self.reset_btn)

        header.addLayout(btn_layout)
        layout.addLayout(header)

    def _setup_input_output(self, layout):
        io_header = QHBoxLayout()
        io_title = QLabel("Input and Output")
        io_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        io_header.addWidget(io_title)
        io_header.addStretch()

        self.advanced_toggle = QCheckBox("Show Advanced Settings")
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.toggled.connect(self._toggle_advanced)
        io_header.addWidget(self.advanced_toggle)
        layout.addLayout(io_header)

        io_section = BorderFrame()
        io_layout = io_section.layout()
        io_layout.setSpacing(10)

        tabs = QTabWidget()

        single_tab = QWidget()
        single_layout = QVBoxLayout(single_tab)
        single_border = BorderFrame()
        single_inner = QVBoxLayout()
        sf_layout = QHBoxLayout()
        sf_layout.addWidget(QLabel("Input File"))
        self.input_file = DropLineEdit()
        self.input_file.setFixedWidth(600)
        self.input_file.setToolTip(
            "Path of the image or archive file (such as zip or cbz) to upscale."
        )
        sf_layout.addWidget(self.input_file)
        select_file_btn = QPushButton("Select File")
        select_file_btn.clicked.connect(self._browse_input_file)
        sf_layout.addWidget(select_file_btn)
        single_inner.addLayout(sf_layout)
        single_inner.addWidget(
            HelpLabel(
                "Path of the image or archive file (such as zip or cbz) to upscale. If an archive file is selected, each image in the archive will be upscaled and saved to a new archive."
            )
        )
        single_border.layout().addLayout(single_inner)
        single_layout.addWidget(single_border)
        tabs.addTab(single_tab, "📄 Single File Upscale")

        batch_tab = QWidget()
        batch_layout = QVBoxLayout(batch_tab)
        batch_border = BorderFrame()
        batch_inner = QVBoxLayout()
        bf_layout = QHBoxLayout()
        bf_layout.addWidget(QLabel("Input Folder"))
        self.input_folder = DropLineEdit()
        self.input_folder.setFixedWidth(600)
        self.input_folder.setToolTip("Path of the folder to upscale.")
        bf_layout.addWidget(self.input_folder)
        select_folder_btn = QPushButton("Select Folder")
        select_folder_btn.clicked.connect(self._browse_input_folder)
        bf_layout.addWidget(select_folder_btn)
        batch_inner.addLayout(bf_layout)

        checks = QHBoxLayout()
        self.upscale_archives = QCheckBox("Upscale Archives")
        self.upscale_archives.setChecked(True)
        self.upscale_archives.setToolTip(
            "Upscale Archive files (*.zip, *.cbz, *.rar, *.cbr)"
        )
        checks.addWidget(self.upscale_archives)
        self.upscale_images = QCheckBox("Upscale Images")
        self.upscale_images.setToolTip(
            "Upscale Image files (*.png, *.jpg, *.jpeg, *.webp, *.bmp)"
        )
        checks.addWidget(self.upscale_images)
        checks.addWidget(
            HelpLabel(
                "Whether to upscale Image files and/or Archive files in the selected Input Folder."
            )
        )
        batch_inner.addLayout(checks)
        batch_border.layout().addLayout(batch_inner)
        batch_layout.addWidget(batch_border)
        tabs.addTab(batch_tab, "📁 Batch Folder Upscale")

        io_layout.addWidget(tabs)

        of_border = BorderFrame()
        of_layout = of_border.layout()
        of_layout.setSpacing(10)

        of_row = QHBoxLayout()
        of_row.addWidget(QLabel("Output Folder"))
        self.output_folder = DropLineEdit()
        self.output_folder.setFixedWidth(600)
        self.output_folder.setToolTip(
            "Path of the folder to save the upscaled image(s) or archive(s)."
        )
        of_row.addWidget(self.output_folder)
        select_out_btn = QPushButton("Select Folder")
        select_out_btn.clicked.connect(self._browse_output_folder)
        of_row.addWidget(select_out_btn)
        of_layout.addLayout(of_row)
        of_layout.addWidget(
            HelpLabel("Path of the folder to save the upscaled image(s) or archive(s).")
        )

        fn_row = QHBoxLayout()
        fn_row.addWidget(QLabel("Output Filename"))
        self.output_filename = QLineEdit("%filename%-mangajanai")
        self.output_filename.setFixedWidth(600)
        fn_row.addWidget(self.output_filename)
        of_layout.addLayout(fn_row)
        of_layout.addWidget(
            HelpLabel(
                "The filename of the upscaled image(s) or archive(s), without the file extension. %filename% is the input filename without extension."
            )
        )

        ow_row = QHBoxLayout()
        self.overwrite = QCheckBox("Allow Files in Output Path to be Overwritten")
        ow_row.addWidget(self.overwrite)
        ow_row.addWidget(
            HelpLabel(
                "If unchecked, upscaling will be skipped for files that already exist. If checked, existing files will be overwritten without warning."
            )
        )
        of_layout.addLayout(ow_row)

        io_layout.addWidget(of_border)

        fmt_border = BorderFrame()
        fmt_layout = fmt_border.layout()
        fmt_layout.setSpacing(10)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Output Image Format"))
        self.webp_btn = ToggleButton("WebP", True)
        self.avif_btn = ToggleButton("AVIF", False)
        self.png_btn = ToggleButton("PNG", False)
        self.jpeg_btn = ToggleButton("JPEG", False)
        self.webp_btn.clicked.connect(lambda: self._set_format("webp"))
        self.avif_btn.clicked.connect(lambda: self._set_format("avif"))
        self.png_btn.clicked.connect(lambda: self._set_format("png"))
        self.jpeg_btn.clicked.connect(lambda: self._set_format("jpeg"))
        fmt_row.addWidget(self.webp_btn)
        fmt_row.addWidget(self.avif_btn)
        fmt_row.addWidget(self.png_btn)
        fmt_row.addWidget(self.jpeg_btn)
        fmt_layout.addLayout(fmt_row)
        fmt_layout.addWidget(
            HelpLabel(
                "WebP: Modern format recommended for good quality and efficient filesize.\n"
                "AVIF: Better lossy compression than WebP, but slower and less widely supported.\n"
                "PNG: Lossless with excellent compatibility, but larger files than WebP.\n"
                "JPEG: Lossy with excellent compatibility, but worse compression than WebP/AVIF."
            )
        )

        self.lossless = QCheckBox("Use Lossless Compression")
        fmt_layout.addWidget(self.lossless)
        fmt_layout.addWidget(
            HelpLabel(
                "Use lossless compression. Usually not recommended due to producing much larger files with little visual benefit."
            )
        )

        qual_row = QHBoxLayout()
        qual_row.addWidget(QLabel("Lossy Compression Quality"))
        self.quality = QSpinBox()
        self.quality.setRange(0, 100)
        self.quality.setValue(95)
        self.quality.setFixedWidth(120)
        qual_row.addWidget(self.quality)
        qual_row.addWidget(QLabel("%"))
        qual_row.addWidget(
            HelpLabel(
                "Quality level for compression. Note that a quality level of 100 is still lossy."
            )
        )
        fmt_layout.addLayout(qual_row)

        io_layout.addWidget(fmt_border)
        layout.addWidget(io_section)

    def _setup_upscaling(self, layout):
        up_title = QLabel("Upscaling")
        up_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(up_title)

        up_section = BorderFrame()
        up_layout = up_section.layout()
        up_layout.setSpacing(10)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Upscale Mode"))
        self.mode_scale = ToggleButton("Scale", True)
        self.mode_width = ToggleButton("Width", False)
        self.mode_height = ToggleButton("Height", False)
        self.mode_display = ToggleButton("Fit to Display", False)
        mode_row.addWidget(self.mode_scale)
        mode_row.addWidget(self.mode_width)
        mode_row.addWidget(self.mode_height)
        mode_row.addWidget(self.mode_display)
        up_layout.addLayout(mode_row)
        up_layout.addWidget(
            HelpLabel(
                "Scale: All images upscaled by the specified factor (e.g. 2x doubles width and height).\n"
                "Width: All images upscaled to specified width, maintaining aspect ratio.\n"
                "Height: All images upscaled to specified height, maintaining aspect ratio.\n"
                "Fit to Display: All images upscaled to fit within the specified display device."
            )
        )

        self.mode_scale.clicked.connect(lambda: self._set_mode(0))
        self.mode_width.clicked.connect(lambda: self._set_mode(1))
        self.mode_height.clicked.connect(lambda: self._set_mode(2))
        self.mode_display.clicked.connect(lambda: self._set_mode(3))

        self.scale_panel = QWidget()
        scale_r = QHBoxLayout()
        scale_r.addWidget(QLabel("Scale Factor"))
        self.s1x = ToggleButton("1x", False)
        self.s2x = ToggleButton("2x", False)
        self.s3x = ToggleButton("3x", False)
        self.s4x = ToggleButton("4x", True)
        scale_r.addWidget(self.s1x)
        scale_r.addWidget(self.s2x)
        scale_r.addWidget(self.s3x)
        scale_r.addWidget(self.s4x)
        self.scale_panel.setLayout(scale_r)
        up_layout.addWidget(self.scale_panel)

        self.s1x.clicked.connect(lambda: self._set_scale(1))
        self.s2x.clicked.connect(lambda: self._set_scale(2))
        self.s3x.clicked.connect(lambda: self._set_scale(3))
        self.s4x.clicked.connect(lambda: self._set_scale(4))

        self.height_panel = QWidget()
        h_r = QHBoxLayout()
        h_r.addWidget(QLabel("Output Height"))
        self.out_height = QSpinBox()
        self.out_height.setRange(1, 99999)
        self.out_height.setValue(2160)
        self.out_height.setFixedWidth(120)
        h_r.addWidget(self.out_height)
        h_r.addWidget(QLabel("px"))
        self.height_panel.setLayout(h_r)
        self.height_panel.hide()
        up_layout.addWidget(self.height_panel)

        self.width_panel = QWidget()
        w_r = QHBoxLayout()
        w_r.addWidget(QLabel("Output Width"))
        self.out_width = QSpinBox()
        self.out_width.setRange(1, 99999)
        self.out_width.setValue(3840)
        self.out_width.setFixedWidth(120)
        w_r.addWidget(self.out_width)
        w_r.addWidget(QLabel("px"))
        self.width_panel.setLayout(w_r)
        self.width_panel.hide()
        up_layout.addWidget(self.width_panel)

        self.display_panel = QWidget()
        d_layout = QVBoxLayout(self.display_panel)
        d_layout.setSpacing(10)

        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Tablet Device or Display"))
        self.device_combo = QComboBox()
        self.device_combo.setEditable(True)
        self.device_combo.setFixedWidth(400)
        dev_row.addWidget(self.device_combo)
        d_layout.addLayout(dev_row)
        d_layout.addWidget(
            HelpLabel(
                "The name of the tablet or display device. Start typing to search."
            )
        )

        ori_row = QHBoxLayout()
        ori_row.addWidget(QLabel("Display Orientation"))
        self.portrait_btn = ToggleButton("Portrait", True)
        self.landscape_btn = ToggleButton("Landscape", False)
        self.portrait_btn.clicked.connect(lambda: self._set_orientation(True))
        self.landscape_btn.clicked.connect(lambda: self._set_orientation(False))
        ori_row.addWidget(self.portrait_btn)
        ori_row.addWidget(self.landscape_btn)
        d_layout.addLayout(ori_row)
        d_layout.addWidget(
            HelpLabel(
                "Whether the display will be used in portrait/vertical mode or landscape/horizontal mode."
            )
        )

        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Display Resolution"))
        self.display_res_label = QLabel("0px × 0px")
        self.display_res_label.setFont(QFont("Consolas", 11))
        res_row.addWidget(self.display_res_label)
        d_layout.addLayout(res_row)
        d_layout.addWidget(
            HelpLabel(
                "Actual resolution of the selected display with the selected orientation."
            )
        )

        self.display_panel.hide()
        up_layout.addWidget(self.display_panel)

        layout.addWidget(up_section)

    def _setup_advanced(self, layout):
        self.advanced_section = QWidget()
        adv_layout = QVBoxLayout(self.advanced_section)
        adv_layout.setSpacing(10)

        adv_title_row = QHBoxLayout()
        adv_title = QLabel("Advanced Settings")
        adv_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        adv_title.setToolTip(
            "Advanced settings allow you to select different settings based on the image.\n\n"
            "A chain is a set of conditions and settings to apply when those conditions are met.\n"
            "If an image matches multiple chains, only the highest matching chain is applied.\n"
            "If no chain matches, no processing is applied to that image."
        )
        adv_title_row.addWidget(adv_title)
        help_icon = QLabel("❓")
        help_icon.setToolTip(
            "Advanced settings allow you to select different settings based on the image.\n\n"
            "A chain is a set of conditions and settings to apply when those conditions are met.\n"
            "If an image matches multiple chains, only the highest matching chain is applied.\n"
            "If no chain matches, no processing is applied to that image."
        )
        adv_title_row.addWidget(help_icon)
        adv_layout.addLayout(adv_title_row)

        gs_border = BorderFrame()
        gs_layout = gs_border.layout()
        gs_layout.addWidget(QLabel("Grayscale Detection Threshold"))
        gs_inner = QHBoxLayout()
        self.gs_threshold = QSlider(Qt.Orientation.Horizontal)
        self.gs_threshold.setRange(0, 24)
        self.gs_threshold.setValue(12)
        self.gs_threshold.setFixedWidth(500)
        gs_inner.addWidget(self.gs_threshold)
        self.gs_label = QLabel("12")
        self.gs_label.setFixedWidth(40)
        gs_inner.addWidget(self.gs_label)
        gs_inner.addStretch()
        gs_layout.addLayout(gs_inner)
        gs_layout.addWidget(
            HelpLabel(
                "The threshold for which an image is considered grayscale. Default value of 12 considers "
                "images with slight color as grayscale, because some grayscale images have slight color "
                "due to artifacts. Set to 0 for strictly grayscale only."
            )
        )
        self.gs_threshold.valueChanged.connect(lambda v: self.gs_label.setText(str(v)))
        adv_layout.addWidget(gs_border)

        self.chains_border = BorderFrame()
        self.chains_layout_inner = self.chains_border.layout()
        self.chain_widgets = []
        adv_layout.addWidget(self.chains_border)

        add_chain_row = QHBoxLayout()
        self.add_chain_btn = QPushButton("➕ Add Chain")
        self.add_chain_btn.setObjectName("addChainBtn")
        self.add_chain_btn.clicked.connect(self._add_chain)
        add_chain_row.addWidget(self.add_chain_btn)
        add_chain_row.addWidget(
            HelpLabel(
                "A chain is a set of upscale settings activated based on conditions such as image resolution "
                "and whether the image is color or grayscale. This allows different models for different image types."
            )
        )
        adv_layout.addLayout(add_chain_row)

        layout.addWidget(self.advanced_section)
        self.advanced_section.setVisible(False)

    def _toggle_advanced(self, checked):
        self.advanced_section.setVisible(checked)

    def _set_orientation(self, portrait):
        self.portrait_btn.setChecked(portrait)
        self.landscape_btn.setChecked(not portrait)

    def _set_mode(self, idx):
        self.mode_scale.setChecked(idx == 0)
        self.mode_width.setChecked(idx == 1)
        self.mode_height.setChecked(idx == 2)
        self.mode_display.setChecked(idx == 3)
        self.scale_panel.setVisible(idx == 0)
        self.width_panel.setVisible(idx == 1)
        self.height_panel.setVisible(idx == 2)
        self.display_panel.setVisible(idx == 3)

    def _set_scale(self, factor):
        self.s1x.setChecked(factor == 1)
        self.s2x.setChecked(factor == 2)
        self.s3x.setChecked(factor == 3)
        self.s4x.setChecked(factor == 4)

    def _set_format(self, fmt):
        self.webp_btn.setChecked(fmt == "webp")
        self.avif_btn.setChecked(fmt == "avif")
        self.png_btn.setChecked(fmt == "png")
        self.jpeg_btn.setChecked(fmt == "jpeg")

    def _browse_input_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Input File",
            "",
            "Images and Archives (*.png *.jpg *.jpeg *.webp *.bmp *.cbz *.cbr *.zip *.rar)",
        )
        if path:
            self.input_file.setText(path)

    def _browse_input_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Input Folder")
        if path:
            self.input_folder.setText(path)

    def _browse_output_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if path:
            self.output_folder.setText(path)

    def _detect_gpu(self):
        gpu = get_gpu_info()
        if gpu.available:
            self.status_left.setText(f"GPU: {gpu.name} (ROCm)")
        elif gpu.driver_loaded:
            self.status_left.setText(f"GPU: {gpu.name} (Driver loaded)")
        else:
            self.status_left.setText("GPU: Not detected")

    def _load_settings(self, filepath=None):
        if filepath is None:
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            filepath = os.path.join(base_dir, "current", "appstate2.json")

        if not os.path.exists(filepath):
            self.status_left.setText(f"Settings not found: {filepath}")
            return

        if os.path.getsize(filepath) == 0:
            self.status_left.setText("Settings file is empty - restore from backup")
            QMessageBox.warning(
                self,
                "Empty Settings File",
                f"The settings file is empty.\n\nPath: {filepath}\n\nPlease restore from backup.",
            )
            return

        try:
            self.settings = AppSettings.load_from_file(filepath)
            self.models = get_available_models(self.settings.models_directory)
            self.devices = self.settings.display_device_map

            self.device_combo.addItems([d.name for d in self.devices])

            if not self.models:
                self.status_left.setText(
                    f"No models found in: {self.settings.models_directory}"
                )
                QMessageBox.warning(
                    self,
                    "No Models Found",
                    f"No model files found in:\n{self.settings.models_directory}",
                )
            else:
                self.status_left.setText(
                    f"Loaded {len(self.models)} models, {len(self.settings.workflows)} workflows"
                )

            for wf in self.settings.workflows:
                if wf.workflow_name == "Upscale Manga (Default)":
                    self._populate_workflow(wf)
                    break

            # Populate sidebar with all workflows
            self._populate_sidebar_workflows()

        except Exception as e:
            self.status_left.setText(f"Error loading settings: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load settings:\n{str(e)}")

    def _populate_workflow(self, wf):
        self.wf_name.setText(wf.workflow_name)
        self.input_file.setText(wf.input_file_path)
        self.input_folder.setText(wf.input_folder_path)
        self.output_folder.setText(wf.output_folder_path)
        self.output_filename.setText(wf.output_filename)
        self.overwrite.setChecked(wf.overwrite_existing_files)
        self.upscale_images.setChecked(wf.upscale_images)
        self.upscale_archives.setChecked(wf.upscale_archives)
        self.webp_btn.setChecked(wf.webp_selected)
        self.avif_btn.setChecked(wf.avif_selected)
        self.png_btn.setChecked(wf.png_selected)
        self.jpeg_btn.setChecked(wf.jpeg_selected)
        self.lossless.setChecked(wf.use_lossless_compression)
        self.quality.setValue(wf.lossy_compression_quality)
        self.out_height.setValue(wf.resize_height_after_upscale)
        self.out_width.setValue(wf.resize_width_after_upscale)
        self.gs_threshold.setValue(wf.grayscale_detection_threshold)

        if wf.mode_scale_selected:
            self.mode_scale.setChecked(True)
        elif wf.mode_width_selected:
            self.mode_width.setChecked(True)
        elif wf.mode_height_selected:
            self.mode_height.setChecked(True)
        elif wf.mode_fit_to_display_selected:
            self.mode_display.setChecked(True)

        if wf.upscale_scale_factor == 1:
            self.s1x.setChecked(True)
        elif wf.upscale_scale_factor == 2:
            self.s2x.setChecked(True)
        elif wf.upscale_scale_factor == 3:
            self.s3x.setChecked(True)
        elif wf.upscale_scale_factor == 4:
            self.s4x.setChecked(True)

        if wf.display_device:
            idx = self.device_combo.findText(wf.display_device)
            if idx >= 0:
                self.device_combo.setCurrentIndex(idx)
        self.portrait_btn.setChecked(wf.display_portrait_selected)

        self._populate_chains(
            wf.chains, is_default=(wf.workflow_name == "Upscale Manga (Default)")
        )

    def _populate_chains(self, chains, is_default=False):
        for w in self.chain_widgets:
            w.deleteLater()
        self.chain_widgets.clear()

        for i, chain in enumerate(chains):
            w = ChainWidget(chain, self.models, i + 1, is_default=is_default)
            if not is_default and hasattr(w, "remove_btn"):
                idx = i
                w.remove_btn.clicked.connect(
                    lambda checked, i=idx: self._remove_chain(i)
                )
            self.chain_widgets.append(w)
            self.chains_layout_inner.addWidget(w)

            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.HLine)
            self.chains_layout_inner.addWidget(sep)

    def _add_chain(self):
        new_chain = UpscaleChain(
            chain_number=str(len(self.chain_widgets) + 1),
            model_file_path=self.models[0] if self.models else "",
        )
        w = ChainWidget(
            new_chain, self.models, len(self.chain_widgets) + 1, is_default=False
        )
        idx = len(self.chain_widgets)
        w.remove_btn.clicked.connect(lambda checked, i=idx: self._remove_chain(i))
        self.chain_widgets.append(w)
        self.chains_layout_inner.insertWidget(self.chains_layout_inner.count() - 1, w)

    def _remove_chain(self, index):
        if 0 <= index < len(self.chain_widgets):
            self.chain_widgets[index].deleteLater()
            self.chain_widgets.pop(index)

    def _import_workflow(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Workflow", "", "JSON Files (*.json)"
        )
        if path:
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                wf = UpscaleWorkflow.from_dict(data)
                self._populate_workflow(wf)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to import: {str(e)}")

    def _export_workflow(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Workflow", "", "JSON Files (*.json)"
        )
        if path:
            try:
                wf = self._get_current_workflow()
                with open(path, "w") as f:
                    json.dump(wf.to_dict(), f, indent=2)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export: {str(e)}")

    def _reset_workflow(self):
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "default_settings.json",
        )

        reply = QMessageBox.question(
            self,
            "Reset to Default",
            "Reset to official default settings?\n\nThis will load the default 'Upscale Manga (Default)' workflow from the MangaJaNaiConverterGui repository.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._load_settings(default_path)

    def _get_current_workflow(self):
        wf = UpscaleWorkflow()
        wf.workflow_name = self.wf_name.text()
        wf.input_file_path = self.input_file.text()
        wf.input_folder_path = self.input_folder.text()
        wf.output_folder_path = self.output_folder.text()
        wf.output_filename = self.output_filename.text()
        wf.overwrite_existing_files = self.overwrite.isChecked()
        wf.upscale_images = self.upscale_images.isChecked()
        wf.upscale_archives = self.upscale_archives.isChecked()
        wf.webp_selected = self.webp_btn.isChecked()
        wf.avif_selected = self.avif_btn.isChecked()
        wf.png_selected = self.png_btn.isChecked()
        wf.jpeg_selected = self.jpeg_btn.isChecked()
        wf.use_lossless_compression = self.lossless.isChecked()
        wf.lossy_compression_quality = self.quality.value()
        wf.resize_height_after_upscale = self.out_height.value()
        wf.resize_width_after_upscale = self.out_width.value()
        wf.grayscale_detection_threshold = self.gs_threshold.value()
        wf.mode_scale_selected = self.mode_scale.isChecked()
        wf.mode_width_selected = self.mode_width.isChecked()
        wf.mode_height_selected = self.mode_height.isChecked()
        wf.mode_fit_to_display_selected = self.mode_display.isChecked()
        wf.display_device = self.device_combo.currentText()
        wf.display_portrait_selected = self.portrait_btn.isChecked()

        if self.s1x.isChecked():
            wf.upscale_scale_factor = 1
        elif self.s2x.isChecked():
            wf.upscale_scale_factor = 2
        elif self.s3x.isChecked():
            wf.upscale_scale_factor = 3
        else:
            wf.upscale_scale_factor = 4

        wf.chains = [w.get_chain() for w in self.chain_widgets]
        return wf

    def _start_upscale(self):
        wf = self._get_current_workflow()
        if not wf.input_file_path and not wf.input_folder_path:
            QMessageBox.warning(
                self, "Warning", "Please select an input file or folder"
            )
            return
        if not wf.output_folder_path:
            QMessageBox.warning(self, "Warning", "Please select an output folder")
            return

        if self.settings:
            self.settings.workflows = [wf]
            self.settings.selected_device_index = 1
            self.settings.use_cpu = False
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            settings_path = os.path.join(base_dir, "current", "appstate2.json")
            self.settings.save_to_file(settings_path)
        else:
            QMessageBox.warning(self, "Warning", "No settings loaded")
            return

        venv_python = os.path.join(
            base_dir, "current", "backend", "src", ".venv", "bin", "python3"
        )
        script_path = os.path.join(
            base_dir, "current", "backend", "src", "run_upscale.py"
        )
        if not os.path.exists(venv_python):
            venv_python = "python3"

        self.console.clear()
        self.upscale_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.start_time = time.time()
        self.timer.start(1000)
        self.total_progress.setValue(0)
        self.archive_progress.setValue(0)

        self.worker = UpscaleWorker(venv_python, script_path, settings_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_upscale_finished)
        self.worker.start()

    def _cancel_upscale(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.console.append("\n--- Cancelling... ---")

    def _on_progress(self, message):
        # Color-code console messages
        if "Error" in message or "Traceback" in message or "failed" in message.lower():
            self.console.setTextColor(QColor("#f7768e"))
        elif "WARNING" in message or "Warning" in message or "FutureWarning" in message:
            self.console.setTextColor(QColor("#e0af68"))
        elif "save image to zip" in message or "completed" in message.lower():
            self.console.setTextColor(QColor("#9ece6a"))
        elif "read image" in message or "Matched Chain" in message:
            self.console.setTextColor(QColor("#565f89"))
        elif "Elapsed time" in message:
            self.console.setTextColor(QColor("#9ece6a"))
        else:
            self.console.setTextColor(QColor("#565f89"))

        self.console.append(message)
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum()
        )

        # Parse image count for progress bars
        if message.startswith("PROGRESS=total_images "):
            try:
                total = int(message.split()[-1])
                self.total_files = total
                self.processed_files = 0
                self.archive_progress.setMaximum(total)
                self.archive_progress.setValue(0)
                self.total_progress.setMaximum(total)
                self.total_progress.setValue(0)
            except Exception:
                pass

        if "save image to zip:" in message:
            self.processed_files += 1
            self.archive_progress.setValue(self.archive_progress.value() + 1)
            self.total_progress.setValue(self.total_progress.value() + 1)

    def _on_upscale_finished(self, success, message):
        self.timer.stop()
        self.upscale_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.status_left.setText(message)
        self.total_progress.setValue(self.total_progress.maximum())
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.warning(self, "Error", message)

    def _select_workflow(self, idx):
        """Switch to a specific workflow and populate the UI."""
        if not self.settings or idx >= len(self.settings.workflows):
            return

        # Update sidebar button states
        for btn in self.workflow_buttons:
            btn.setChecked(btn.property("workflow_index") == idx)

        # Populate the workflow in the main UI
        wf = self.settings.workflows[idx]
        self._populate_workflow(wf)

    def _add_workflow(self):
        """Add a new custom workflow."""
        if not self.settings:
            self.settings = AppSettings()
            self.settings.display_device_map = ReaderDevice.default_devices()
            self.devices = self.settings.display_device_map

        new_idx = len(self.settings.workflows)
        wf = UpscaleWorkflow(
            workflow_name=f"Custom Workflow {new_idx}",
            chains=[
                UpscaleChain(
                    chain_number="1",
                    model_file_path=self.models[0] if self.models else "",
                )
            ],
        )
        self.settings.workflows.append(wf)
        self._populate_sidebar_workflows()
        self._select_workflow(new_idx)

    def _show_app_settings(self):
        if not self.settings:
            return

        if self.app_settings_widget is None:
            self.app_settings_widget = AppSettingsWidget(self.settings)
            self.app_settings_widget.setMinimumWidth(500)
            self.app_settings_widget.setMinimumHeight(400)
            self.app_settings_widget.hide()

        self.app_settings_widget.show()
        self.app_settings_widget.raise_()
        self.app_settings_widget.activateWindow()
