import json
from dataclasses import dataclass, field
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal


@dataclass
class ReaderDevice:
    name: str
    brand: str
    year: str
    width: int
    height: int

    def __str__(self):
        return f"{self.name} ({self.width}x{self.height})"

    @staticmethod
    def default_devices() -> List["ReaderDevice"]:
        return [
            ReaderDevice("Kobo Elipsa 2E (2023)", "Kobo", "2023", 1404, 1872),
            ReaderDevice(
                "Samsung Galaxy Tab S9 Ultra (2023)", "Samsung", "2023", 1848, 2950
            ),
            ReaderDevice("Apple iPad Pro 13-inch (2024)", "Apple", "2024", 2064, 2752),
            ReaderDevice("Generic PC Monitor 4K UHD", "Generic", "", 2160, 3840),
        ]


@dataclass
class UpscaleChain:
    chain_number: str = "1"
    min_resolution: str = "0x0"
    max_resolution: str = "0x0"
    is_grayscale: bool = True
    is_color: bool = False
    min_scale_factor: int = 0
    max_scale_factor: int = 0
    model_file_path: str = ""
    model_tile_size: str = "Auto (Estimate)"
    auto_adjust_levels: bool = True
    resize_height_before_upscale: int = 0
    resize_width_before_upscale: int = 0
    resize_factor_before_upscale: float = 100.0

    def to_dict(self):
        return {
            "$type": "MangaJaNaiConverterGui.ViewModels.UpscaleChain, MangaJaNaiConverterGui",
            "ChainNumber": self.chain_number,
            "MinResolution": self.min_resolution,
            "MaxResolution": self.max_resolution,
            "IsGrayscale": self.is_grayscale,
            "IsColor": self.is_color,
            "MinScaleFactor": self.min_scale_factor,
            "MaxScaleFactor": self.max_scale_factor,
            "ModelFilePath": self.model_file_path,
            "ModelTileSize": self.model_tile_size,
            "AutoAdjustLevels": self.auto_adjust_levels,
            "ResizeHeightBeforeUpscale": self.resize_height_before_upscale,
            "ResizeWidthBeforeUpscale": self.resize_width_before_upscale,
            "ResizeFactorBeforeUpscale": self.resize_factor_before_upscale,
        }

    @staticmethod
    def from_dict(d: dict) -> "UpscaleChain":
        return UpscaleChain(
            chain_number=d.get("ChainNumber", "1"),
            min_resolution=d.get("MinResolution", "0x0"),
            max_resolution=d.get("MaxResolution", "0x0"),
            is_grayscale=d.get("IsGrayscale", True),
            is_color=d.get("IsColor", False),
            min_scale_factor=d.get("MinScaleFactor", 0),
            max_scale_factor=d.get("MaxScaleFactor", 0),
            model_file_path=d.get("ModelFilePath", ""),
            model_tile_size=d.get("ModelTileSize", "Auto (Estimate)"),
            auto_adjust_levels=d.get("AutoAdjustLevels", True),
            resize_height_before_upscale=d.get("ResizeHeightBeforeUpscale", 0),
            resize_width_before_upscale=d.get("ResizeWidthBeforeUpscale", 0),
            resize_factor_before_upscale=d.get("ResizeFactorBeforeUpscale", 100.0),
        )


@dataclass
class UpscaleWorkflow:
    workflow_name: str = "New Workflow"
    workflow_index: int = 0
    selected_tab_index: int = 0
    input_file_path: str = ""
    input_folder_path: str = ""
    output_filename: str = "%filename%-mangajanai"
    output_folder_path: str = ""
    overwrite_existing_files: bool = False
    upscale_images: bool = True
    upscale_archives: bool = True
    resize_height_after_upscale: int = 2160
    resize_width_after_upscale: int = 3840
    webp_selected: bool = True
    avif_selected: bool = False
    png_selected: bool = False
    jpeg_selected: bool = False
    use_lossless_compression: bool = False
    lossy_compression_quality: int = 95
    show_lossy_settings: bool = True
    mode_scale_selected: bool = True
    upscale_scale_factor: int = 4
    mode_width_selected: bool = False
    mode_height_selected: bool = False
    mode_fit_to_display_selected: bool = False
    display_device: Optional[str] = None
    display_device_width: int = 0
    display_device_height: int = 0
    display_portrait_selected: bool = True
    show_advanced_settings: bool = True
    grayscale_detection_threshold: int = 12
    chains: List[UpscaleChain] = field(default_factory=list)

    def to_dict(self):
        return {
            "$type": "MangaJaNaiConverterGui.ViewModels.UpscaleWorkflow, MangaJaNaiConverterGui",
            "WorkflowName": self.workflow_name,
            "WorkflowIndex": self.workflow_index,
            "SelectedTabIndex": self.selected_tab_index,
            "InputFilePath": self.input_file_path,
            "InputFolderPath": self.input_folder_path,
            "OutputFilename": self.output_filename,
            "OutputFolderPath": self.output_folder_path,
            "OverwriteExistingFiles": self.overwrite_existing_files,
            "UpscaleImages": self.upscale_images,
            "UpscaleArchives": self.upscale_archives,
            "ResizeHeightAfterUpscale": self.resize_height_after_upscale,
            "ResizeWidthAfterUpscale": self.resize_width_after_upscale,
            "WebpSelected": self.webp_selected,
            "AvifSelected": self.avif_selected,
            "PngSelected": self.png_selected,
            "JpegSelected": self.jpeg_selected,
            "UseLosslessCompression": self.use_lossless_compression,
            "LossyCompressionQuality": self.lossy_compression_quality,
            "ShowLossySettings": self.show_lossy_settings,
            "ModeScaleSelected": self.mode_scale_selected,
            "UpscaleScaleFactor": self.upscale_scale_factor,
            "ModeWidthSelected": self.mode_width_selected,
            "ModeHeightSelected": self.mode_height_selected,
            "ModeFitToDisplaySelected": self.mode_fit_to_display_selected,
            "DisplayDevice": self.display_device,
            "DisplayDeviceWidth": self.display_device_width,
            "DisplayDeviceHeight": self.display_device_height,
            "DisplayPortraitSelected": self.display_portrait_selected,
            "ShowAdvancedSettings": self.show_advanced_settings,
            "GrayscaleDetectionThreshold": self.grayscale_detection_threshold,
            "Chains": {
                "$type": "Avalonia.Collections.AvaloniaList`1[[MangaJaNaiConverterGui.ViewModels.UpscaleChain, MangaJaNaiConverterGui]], Avalonia.Base",
                "$values": [c.to_dict() for c in self.chains],
            },
        }

    @staticmethod
    def from_dict(d: dict) -> "UpscaleWorkflow":
        chains_data = d.get("Chains", {}).get("$values", [])
        chains = [UpscaleChain.from_dict(c) for c in chains_data]

        return UpscaleWorkflow(
            workflow_name=d.get("WorkflowName", "New Workflow"),
            workflow_index=d.get("WorkflowIndex", 0),
            selected_tab_index=d.get("SelectedTabIndex", 0),
            input_file_path=d.get("InputFilePath", ""),
            input_folder_path=d.get("InputFolderPath", ""),
            output_filename=d.get("OutputFilename", "%filename%-mangajanai"),
            output_folder_path=d.get("OutputFolderPath", ""),
            overwrite_existing_files=d.get("OverwriteExistingFiles", False),
            upscale_images=d.get("UpscaleImages", True),
            upscale_archives=d.get("UpscaleArchives", True),
            resize_height_after_upscale=d.get("ResizeHeightAfterUpscale", 2160),
            resize_width_after_upscale=d.get("ResizeWidthAfterUpscale", 3840),
            webp_selected=d.get("WebpSelected", True),
            avif_selected=d.get("AvifSelected", False),
            png_selected=d.get("PngSelected", False),
            jpeg_selected=d.get("JpegSelected", False),
            use_lossless_compression=d.get("UseLosslessCompression", False),
            lossy_compression_quality=d.get("LossyCompressionQuality", 95),
            show_lossy_settings=d.get("ShowLossySettings", True),
            mode_scale_selected=d.get("ModeScaleSelected", True),
            upscale_scale_factor=d.get("UpscaleScaleFactor", 4),
            mode_width_selected=d.get("ModeWidthSelected", False),
            mode_height_selected=d.get("ModeHeightSelected", False),
            mode_fit_to_display_selected=d.get("ModeFitToDisplaySelected", False),
            display_device=d.get("DisplayDevice"),
            display_device_width=d.get("DisplayDeviceWidth", 0),
            display_device_height=d.get("DisplayDeviceHeight", 0),
            display_portrait_selected=d.get("DisplayPortraitSelected", True),
            show_advanced_settings=d.get("ShowAdvancedSettings", True),
            grayscale_detection_threshold=d.get("GrayscaleDetectionThreshold", 12),
            chains=chains,
        )


class AppSettings(QObject):
    models_directory: str = ""
    display_device_map: List[ReaderDevice] = []
    auto_update_enabled: bool = True
    selected_device_index: int = 1
    use_cpu: bool = False
    use_fp16: bool = True
    workflows: List[UpscaleWorkflow] = []

    settings_changed = pyqtSignal()

    def to_dict(self):
        device_map = {}
        for device in self.display_device_map:
            device_map[device.name] = {
                "$type": "MangaJaNaiConverterGui.ViewModels.ReaderDevice, MangaJaNaiConverterGui",
                "Name": device.name,
                "Brand": device.brand,
                "Year": device.year,
                "Width": device.width,
                "Height": device.height,
            }

        return {
            "$type": "MangaJaNaiConverterGui.ViewModels.MainWindowViewModel, MangaJaNaiConverterGui",
            "ModelsDirectory": self.models_directory,
            "DisplayDeviceMap": {
                "$type": "Avalonia.Collections.AvaloniaDictionary`2[[System.String, System.Private.CoreLib],[MangaJaNaiConverterGui.ViewModels.ReaderDevice, MangaJaNaiConverterGui]], Avalonia.Base",
                **device_map,
            },
            "AutoUpdateEnabled": self.auto_update_enabled,
            "SelectedDeviceIndex": self.selected_device_index,
            "SelectedWorkflowIndex": 0,
            "UseCpu": self.use_cpu,
            "UseFp16": self.use_fp16,
            "Workflows": {
                "$type": "Avalonia.Collections.AvaloniaList`1[[MangaJaNaiConverterGui.ViewModels.UpscaleWorkflow, MangaJaNaiConverterGui]], Avalonia.Base",
                "$values": [wf.to_dict() for wf in self.workflows],
            },
        }

    def save_to_file(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @staticmethod
    def load_from_file(filepath: str) -> "AppSettings":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        settings = AppSettings()
        settings.models_directory = data.get("ModelsDirectory", "")

        device_map = data.get("DisplayDeviceMap", {})
        settings.display_device_map = []
        for name, device_data in device_map.items():
            if not isinstance(device_data, dict):
                continue
            settings.display_device_map.append(
                ReaderDevice(
                    name=device_data.get("Name", name),
                    brand=device_data.get("Brand", ""),
                    year=device_data.get("Year", ""),
                    width=device_data.get("Width", 0),
                    height=device_data.get("Height", 0),
                )
            )

        settings.auto_update_enabled = data.get("AutoUpdateEnabled", True)
        settings.selected_device_index = data.get("SelectedDeviceIndex", 1)
        settings.use_cpu = data.get("UseCpu", False)
        settings.use_fp16 = data.get("UseFp16", True)

        workflows_data = data.get("Workflows", {}).get("$values", [])
        settings.workflows = [UpscaleWorkflow.from_dict(w) for w in workflows_data]

        return settings
