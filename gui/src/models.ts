export class ReaderDevice {
    constructor(
        public name: string,
        public brand: string,
        public year: string,
        public width: number,
        public height: number
    ) {}

    static defaultDevices(): ReaderDevice[] {
        return [
            new ReaderDevice("Kobo Elipsa 2E (2023)", "Kobo", "2023", 1404, 1872),
            new ReaderDevice("Samsung Galaxy Tab S9 Ultra (2023)", "Samsung", "2023", 1848, 2950),
            new ReaderDevice("Apple iPad Pro 13-inch (2024)", "Apple", "2024", 2064, 2752),
            new ReaderDevice("Generic PC Monitor 4K UHD", "Generic", "", 2160, 3840),
        ];
    }
}

export class UpscaleChain {
    constructor(
        public chain_number: string = "1",
        public min_resolution: string = "0x0",
        public max_resolution: string = "0x0",
        public is_grayscale: boolean = true,
        public is_color: boolean = false,
        public min_scale_factor: number = 0,
        public max_scale_factor: number = 0,
        public model_file_path: string = "",
        public model_tile_size: string = "Auto (Estimate)",
        public auto_adjust_levels: boolean = true,
        public resize_height_before_upscale: number = 0,
        public resize_width_before_upscale: number = 0,
        public resize_factor_before_upscale: number = 100.0
    ) {}

    static defaultChains(): UpscaleChain[] {
        return [
            new UpscaleChain("1", "0x0", "0x0", false, true, 0, 2, "2x_IllustrationJaNai_V3denoise_FDAT_M_unshuffle_30k_fp16.safetensors", "256", false),
            new UpscaleChain("2", "0x0", "0x0", false, true, 2, 0, "4x_IllustrationJaNai_V3denoise_FDAT_M_47k_fp16.safetensors", "256", false),
            new UpscaleChain("3", "0x0", "0x1250", true, false, 0, 2, "2x_MangaJaNai_1200p_V1_ESRGAN_70k.pth", "Auto (Estimate)", true),
            new UpscaleChain("4", "0x0", "0x1250", true, false, 2, 0, "4x_MangaJaNai_1200p_V1_ESRGAN_70k.pth", "Auto (Estimate)", true),
            new UpscaleChain("5", "0x1251", "0x1350", true, false, 0, 2, "2x_MangaJaNai_1300p_V1_ESRGAN_75k.pth", "Auto (Estimate)", true),
            new UpscaleChain("6", "0x1251", "0x1350", true, false, 2, 0, "4x_MangaJaNai_1300p_V1_ESRGAN_75k.pth", "Auto (Estimate)", true),
            new UpscaleChain("7", "0x1351", "0x1450", true, false, 0, 2, "2x_MangaJaNai_1400p_V1_ESRGAN_70k.pth", "Auto (Estimate)", true),
            new UpscaleChain("8", "0x1351", "0x1450", true, false, 2, 0, "4x_MangaJaNai_1400p_V1_ESRGAN_105k.pth", "Auto (Estimate)", true),
            new UpscaleChain("9", "0x1451", "0x1550", true, false, 0, 2, "2x_MangaJaNai_1500p_V1_ESRGAN_90k.pth", "Auto (Estimate)", true),
            new UpscaleChain("10", "0x1451", "0x1550", true, false, 2, 0, "4x_MangaJaNai_1500p_V1_ESRGAN_105k.pth", "Auto (Estimate)", true),
            new UpscaleChain("11", "0x1551", "0x1760", true, false, 0, 2, "2x_MangaJaNai_1600p_V1_ESRGAN_90k.pth", "Auto (Estimate)", true),
            new UpscaleChain("12", "0x1551", "0x1760", true, false, 2, 0, "4x_MangaJaNai_1600p_V1_ESRGAN_70k.pth", "Auto (Estimate)", true),
            new UpscaleChain("13", "0x1761", "0x1984", true, false, 0, 2, "2x_MangaJaNai_1920p_V1_ESRGAN_70k.pth", "Auto (Estimate)", true),
            new UpscaleChain("14", "0x1761", "0x1984", true, false, 2, 0, "4x_MangaJaNai_1920p_V1_ESRGAN_105k.pth", "Auto (Estimate)", true),
            new UpscaleChain("15", "0x1985", "0x0", true, false, 0, 2, "2x_MangaJaNai_2048p_V1_ESRGAN_95k.pth", "Auto (Estimate)", true),
            new UpscaleChain("16", "0x1985", "0x0", true, false, 2, 0, "4x_MangaJaNai_2048p_V1_ESRGAN_70k.pth", "Auto (Estimate)", true),
        ];
    }

    toDict(): any {
        return {
            "$type": "MangaJaNaiConverterGui.ViewModels.UpscaleChain, MangaJaNaiConverterGui",
            "ChainNumber": this.chain_number,
            "MinResolution": this.min_resolution,
            "MaxResolution": this.max_resolution,
            "IsGrayscale": this.is_grayscale,
            "IsColor": this.is_color,
            "MinScaleFactor": this.min_scale_factor,
            "MaxScaleFactor": this.max_scale_factor,
            "ModelFilePath": this.model_file_path,
            "ModelTileSize": this.model_tile_size,
            "AutoAdjustLevels": this.auto_adjust_levels,
            "ResizeHeightBeforeUpscale": this.resize_height_before_upscale,
            "ResizeWidthBeforeUpscale": this.resize_width_before_upscale,
            "ResizeFactorBeforeUpscale": this.resize_factor_before_upscale,
        };
    }
}

export class UpscaleWorkflow {
    constructor(
        public workflow_name: string = "New Workflow",
        public workflow_index: number = 0,
        public selected_tab_index: number = 0,
        public input_file_path: string = "",
        public input_folder_path: string = "",
        public output_filename: string = "%filename%-mangajanai",
        public output_folder_path: string = "",
        public overwrite_existing_files: boolean = false,
        public upscale_images: boolean = true,
        public upscale_archives: boolean = true,
        public resize_height_after_upscale: number = 2160,
        public resize_width_after_upscale: number = 3840,
        public webp_selected: boolean = true,
        public avif_selected: boolean = false,
        public png_selected: boolean = false,
        public jpeg_selected: boolean = false,
        public use_lossless_compression: boolean = false,
        public lossy_compression_quality: number = 80,
        public show_lossy_settings: boolean = true,
        public mode_scale_selected: boolean = true,
        public upscale_scale_factor: number = 4,
        public mode_width_selected: boolean = false,
        public mode_height_selected: boolean = false,
        public mode_fit_to_display_selected: boolean = false,
        public display_device: string | null = null,
        public display_device_width: number = 0,
        public display_device_height: number = 0,
        public display_portrait_selected: boolean = true,
        public show_advanced_settings: boolean = false,
        public grayscale_detection_threshold: number = 12,
        public chains: UpscaleChain[] = UpscaleChain.defaultChains()
    ) {}

    toDict(): any {
        return {
            "$type": "MangaJaNaiConverterGui.ViewModels.UpscaleWorkflow, MangaJaNaiConverterGui",
            "WorkflowName": this.workflow_name,
            "WorkflowIndex": this.workflow_index,
            "SelectedTabIndex": this.selected_tab_index,
            "InputFilePath": this.input_file_path,
            "InputFolderPath": this.input_folder_path,
            "OutputFilename": this.output_filename,
            "OutputFolderPath": this.output_folder_path,
            "OverwriteExistingFiles": this.overwrite_existing_files,
            "UpscaleImages": this.upscale_images,
            "UpscaleArchives": this.upscale_archives,
            "ResizeHeightAfterUpscale": this.resize_height_after_upscale,
            "ResizeWidthAfterUpscale": this.resize_width_after_upscale,
            "WebpSelected": this.webp_selected,
            "AvifSelected": this.avif_selected,
            "PngSelected": this.png_selected,
            "JpegSelected": this.jpeg_selected,
            "UseLosslessCompression": this.use_lossless_compression,
            "LossyCompressionQuality": this.lossy_compression_quality,
            "ShowLossySettings": this.show_lossy_settings,
            "ModeScaleSelected": this.mode_scale_selected,
            "UpscaleScaleFactor": this.upscale_scale_factor,
            "ModeWidthSelected": this.mode_width_selected,
            "ModeHeightSelected": this.mode_height_selected,
            "ModeFitToDisplaySelected": this.mode_fit_to_display_selected,
            "DisplayDevice": this.display_device,
            "DisplayDeviceWidth": this.display_device_width,
            "DisplayDeviceHeight": this.display_device_height,
            "DisplayPortraitSelected": this.display_portrait_selected,
            "ShowAdvancedSettings": this.show_advanced_settings,
            "GrayscaleDetectionThreshold": this.grayscale_detection_threshold,
            "Chains": {
                "$type": "Avalonia.Collections.AvaloniaList`1[[MangaJaNaiConverterGui.ViewModels.UpscaleChain, MangaJaNaiConverterGui]], Avalonia.Base",
                "$values": this.chains.map(c => c.toDict())
            }
        };
    }
}

export class AppSettings {
    constructor(
        public models_directory: string = "backend/models",
        public display_device_map: ReaderDevice[] = ReaderDevice.defaultDevices(),
        public auto_update_enabled: boolean = true,
        public selected_device_index: number = 1,
        public use_cpu: boolean = false,
        public use_fp16: boolean = true,
        public workflows: UpscaleWorkflow[] = [new UpscaleWorkflow("Upscale Manga (Default)", 0)]
    ) {}

    toDict(): any {
        let deviceMap: any = {};
        for (let d of this.display_device_map) {
            deviceMap[d.name] = {
                "$type": "MangaJaNaiConverterGui.ViewModels.ReaderDevice, MangaJaNaiConverterGui",
                "Name": d.name,
                "Brand": d.brand,
                "Year": d.year,
                "Width": d.width,
                "Height": d.height
            };
        }

        return {
            "$type": "MangaJaNaiConverterGui.ViewModels.MainWindowViewModel, MangaJaNaiConverterGui",
            "ModelsDirectory": this.models_directory,
            "DisplayDeviceMap": {
                "$type": "Avalonia.Collections.AvaloniaDictionary`2[[System.String, System.Private.CoreLib],[MangaJaNaiConverterGui.ViewModels.ReaderDevice, MangaJaNaiConverterGui]], Avalonia.Base",
                ...deviceMap
            },
            "AutoUpdateEnabled": this.auto_update_enabled,
            "SelectedDeviceIndex": this.selected_device_index,
            "SelectedWorkflowIndex": 0,
            "UseCpu": this.use_cpu,
            "UseFp16": this.use_fp16,
            "Workflows": {
                "$type": "Avalonia.Collections.AvaloniaList`1[[MangaJaNaiConverterGui.ViewModels.UpscaleWorkflow, MangaJaNaiConverterGui]], Avalonia.Base",
                "$values": this.workflows.map(wf => wf.toDict())
            }
        };
    }

    updateFromDict(obj: any) {
        if (obj.ModelsDirectory !== undefined) {
            if (obj.ModelsDirectory === "models") {
                this.models_directory = "backend/models";
            } else {
                this.models_directory = obj.ModelsDirectory;
            }
        }
        if (obj.SelectedDeviceIndex !== undefined) this.selected_device_index = obj.SelectedDeviceIndex;
        if (obj.UseCpu !== undefined) this.use_cpu = obj.UseCpu;
        if (obj.UseFp16 !== undefined) this.use_fp16 = obj.UseFp16;

        if (obj.Workflows && obj.Workflows.$values && obj.Workflows.$values.length > 0) {
            this.workflows = obj.Workflows.$values.map((wObj: any) => {
                const wf = new UpscaleWorkflow(wObj.WorkflowName || "Loaded Workflow", wObj.WorkflowIndex || 0);
                if (wObj.SelectedTabIndex !== undefined) wf.selected_tab_index = wObj.SelectedTabIndex;
                if (wObj.InputFilePath !== undefined) wf.input_file_path = wObj.InputFilePath;
                if (wObj.InputFolderPath !== undefined) wf.input_folder_path = wObj.InputFolderPath;
                if (wObj.OutputFilename !== undefined) wf.output_filename = wObj.OutputFilename;
                if (wObj.OutputFolderPath !== undefined) wf.output_folder_path = wObj.OutputFolderPath;
                if (wObj.OverwriteExistingFiles !== undefined) wf.overwrite_existing_files = wObj.OverwriteExistingFiles;
                if (wObj.UpscaleImages !== undefined) wf.upscale_images = wObj.UpscaleImages;
                if (wObj.UpscaleArchives !== undefined) wf.upscale_archives = wObj.UpscaleArchives;
                if (wObj.ResizeHeightAfterUpscale !== undefined) wf.resize_height_after_upscale = wObj.ResizeHeightAfterUpscale;
                if (wObj.ResizeWidthAfterUpscale !== undefined) wf.resize_width_after_upscale = wObj.ResizeWidthAfterUpscale;
                if (wObj.WebpSelected !== undefined) wf.webp_selected = wObj.WebpSelected;
                if (wObj.AvifSelected !== undefined) wf.avif_selected = wObj.AvifSelected;
                if (wObj.PngSelected !== undefined) wf.png_selected = wObj.PngSelected;
                if (wObj.JpegSelected !== undefined) wf.jpeg_selected = wObj.JpegSelected;
                if (wObj.UseLosslessCompression !== undefined) wf.use_lossless_compression = wObj.UseLosslessCompression;
                if (wObj.LossyCompressionQuality !== undefined) wf.lossy_compression_quality = wObj.LossyCompressionQuality;
                if (wObj.ModeScaleSelected !== undefined) wf.mode_scale_selected = wObj.ModeScaleSelected;
                if (wObj.UpscaleScaleFactor !== undefined) wf.upscale_scale_factor = wObj.UpscaleScaleFactor;
                if (wObj.ModeWidthSelected !== undefined) wf.mode_width_selected = wObj.ModeWidthSelected;
                if (wObj.ModeHeightSelected !== undefined) wf.mode_height_selected = wObj.ModeHeightSelected;
                if (wObj.ModeFitToDisplaySelected !== undefined) wf.mode_fit_to_display_selected = wObj.ModeFitToDisplaySelected;
                if (wObj.DisplayDevice !== undefined) wf.display_device = wObj.DisplayDevice;
                if (wObj.DisplayPortraitSelected !== undefined) wf.display_portrait_selected = wObj.DisplayPortraitSelected;
                if (wObj.ShowAdvancedSettings !== undefined) wf.show_advanced_settings = wObj.ShowAdvancedSettings;
                if (wObj.GrayscaleDetectionThreshold !== undefined) wf.grayscale_detection_threshold = wObj.GrayscaleDetectionThreshold;

                if (wObj.Chains && wObj.Chains.$values) {
                    wf.chains = wObj.Chains.$values.map((cObj: any) => {
                        const c = new UpscaleChain();
                        if (cObj.ChainNumber !== undefined) c.chain_number = cObj.ChainNumber;
                        if (cObj.MinResolution !== undefined) c.min_resolution = cObj.MinResolution;
                        if (cObj.MaxResolution !== undefined) c.max_resolution = cObj.MaxResolution;
                        if (cObj.IsGrayscale !== undefined) c.is_grayscale = cObj.IsGrayscale;
                        if (cObj.IsColor !== undefined) c.is_color = cObj.IsColor;
                        if (cObj.MinScaleFactor !== undefined) c.min_scale_factor = cObj.MinScaleFactor;
                        if (cObj.MaxScaleFactor !== undefined) c.max_scale_factor = cObj.MaxScaleFactor;
                        if (cObj.ModelFilePath !== undefined) c.model_file_path = cObj.ModelFilePath;
                        if (cObj.ModelTileSize !== undefined) c.model_tile_size = cObj.ModelTileSize;
                        if (cObj.AutoAdjustLevels !== undefined) c.auto_adjust_levels = cObj.AutoAdjustLevels;
                        if (cObj.ResizeHeightBeforeUpscale !== undefined) c.resize_height_before_upscale = cObj.ResizeHeightBeforeUpscale;
                        if (cObj.ResizeWidthBeforeUpscale !== undefined) c.resize_width_before_upscale = cObj.ResizeWidthBeforeUpscale;
                        if (cObj.ResizeFactorBeforeUpscale !== undefined) c.resize_factor_before_upscale = cObj.ResizeFactorBeforeUpscale;
                        return c;
                    });
                }
                return wf;
            });
        }
        return obj.SelectedWorkflowIndex || 0;
    }
}
