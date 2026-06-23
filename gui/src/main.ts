import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open, confirm } from "@tauri-apps/plugin-dialog";
import { AppSettings, UpscaleWorkflow, UpscaleChain } from "./models";

export let appSettings = new AppSettings();
export let currentWorkflowIndex = 0;
let availableModels: string[] = [];
let isUpscaling = false;

// ponytail: simple CSS-attribute theme, no dependency/theme provider needed
const THEME_KEY = "mangajanai-theme";
function getSavedTheme(): "dark" | "light" {
    try {
        const saved = localStorage.getItem(THEME_KEY);
        return saved === "light" ? "light" : "dark";
    } catch {
        return "dark";
    }
}
function applyTheme(theme: "dark" | "light") {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem(THEME_KEY, theme); } catch {}
    const icon = document.getElementById("theme-toggle-icon");
    if (icon) icon.textContent = theme === "dark" ? "light_mode" : "dark_mode";
}
applyTheme(getSavedTheme());

// DOM Elements: Top Bar
const upscaleBtn = document.getElementById("upscale-btn") as HTMLButtonElement;
const cancelBtn = document.getElementById("cancel-btn") as HTMLButtonElement;
const validationMsg = document.getElementById("validation-message") as HTMLDivElement;



const toggleConsoleBtn = document.getElementById("toggle-console-btn")!;
const elapsedTimeText = document.getElementById("elapsed-time")!;
const totalEtrText = document.getElementById("total-etr")!;
const totalEtaText = document.getElementById("total-eta")!;
const archiveProgress = document.getElementById("archive-progress")!;
const archiveProgressText = document.getElementById("archive-progress-text")!;
const mainProgress = document.getElementById("main-progress")!;
const mainProgressText = document.getElementById("progress-text")!;
const consolePanel = document.getElementById("console-panel")!;
const closeConsoleBtn = document.getElementById("close-console-btn")!;
const consoleOutput = document.getElementById("console-output")!;
const archiveEtrText = document.getElementById("archive-etr")!;

// Form Controls
const workflowNameInput = document.getElementById("workflow-name-input") as HTMLInputElement;
const importWorkflowBtn = document.getElementById("import-workflow-btn") as HTMLButtonElement;
const exportWorkflowBtn = document.getElementById("export-workflow-btn")!;
const resetWorkflowBtn = document.getElementById("reset-workflow-btn")!;
const showAdvancedChk = document.getElementById("show-advanced-settings-chk") as HTMLInputElement;
const advancedSection = document.getElementById("advanced-settings-section")!;
const tabBtns = document.querySelectorAll(".tab-btn");
const tabContents = document.querySelectorAll(".tab-content");

const inputFilePath = document.getElementById("input-file-path") as HTMLInputElement;
const browseInputFileBtn = document.getElementById("browse-input-file-btn")!;
const inputFolderPath = document.getElementById("input-folder-path") as HTMLInputElement;
const browseInputFolderBtn = document.getElementById("browse-input-folder-btn")!;
const upscaleArchivesChk = document.getElementById("upscale-archives-chk") as HTMLInputElement;
const upscaleImagesChk = document.getElementById("upscale-images-chk") as HTMLInputElement;

const outputFolderPath = document.getElementById("output-folder-path") as HTMLInputElement;
const browseOutputFolderBtn = document.getElementById("browse-output-folder-btn")!;
const outputFilename = document.getElementById("output-filename") as HTMLInputElement;
const overwriteFilesChk = document.getElementById("overwrite-files-chk") as HTMLInputElement;

const formatToggles = document.querySelectorAll("#format-toggle-group .toggle-btn");
const losslessContainer = document.getElementById("lossless-container")!;
const useLosslessChk = document.getElementById("use-lossless-chk") as HTMLInputElement;
const lossyQualityContainer = document.getElementById("lossy-quality-container")!;
const lossyQuality = document.getElementById("lossy-quality") as HTMLInputElement;

const upscaleModeToggles = document.querySelectorAll("#upscale-mode-toggle-group .toggle-btn");
const scaleFactorToggles = document.querySelectorAll("#scale-factor-toggle-group .toggle-btn");
const outputWidthVal = document.getElementById("output-width-val") as HTMLInputElement;
const outputHeightVal = document.getElementById("output-height-val") as HTMLInputElement;

const displayDeviceSelect = document.getElementById("display-device-select") as HTMLSelectElement;
const orientationToggles = document.querySelectorAll("#orientation-toggle-group .toggle-btn");
const displayResPreview = document.getElementById("display-resolution-preview")!;

const grayscaleThreshold = document.getElementById("grayscale-threshold") as HTMLInputElement;
const grayscaleThresholdVal = document.getElementById("grayscale-threshold-val")!;
const chainsContainer = document.getElementById("chains-container")!;
const addChainBtn = document.getElementById("add-chain-btn")!;

// Modal Controls
const appSettingsBtn = document.getElementById("app-settings-btn")!;
const settingsModal = document.getElementById("settings-modal")!;
const closeSettingsBtn = document.getElementById("close-settings-btn")!;
const saveSettingsBtn = document.getElementById("save-settings-btn")!;
const settingDevice = document.getElementById("setting-device") as HTMLSelectElement;
const settingFp16 = document.getElementById("setting-fp16") as HTMLInputElement;
const settingModelsDir = document.getElementById("setting-models-dir") as HTMLInputElement;

let totalArchives = 0;
let currentTotalArchives = 0;
let totalArchiveImages = 0;
let currentArchiveImages = 0;
let startTime = 0;

class ETACalculator {
    private startTimeMs: number = 0;
    private currentProgress: number = 0;

    constructor() {}

    reset() {
        this.startTimeMs = Date.now();
        this.currentProgress = 0;
    }

    update(progress: number) {
        this.currentProgress = progress;
        if (this.startTimeMs === 0 && progress > 0) {
            this.startTimeMs = Date.now();
        }
    }

    get ETR_Seconds(): number {
        if (this.currentProgress <= 0 || this.startTimeMs === 0 || this.currentProgress >= 1) {
            return Infinity;
        }
        const elapsedMs = Date.now() - this.startTimeMs;
        const totalEstimatedMs = elapsedMs / this.currentProgress;
        return (totalEstimatedMs - elapsedMs) / 1000;
    }

    get ETAIsAvailable(): boolean {
        return this.startTimeMs !== 0 && this.currentProgress > 0 && (Date.now() - this.startTimeMs) > 2000;
    }
}

const archiveEtaCalc = new ETACalculator();
const totalEtaCalc = new ETACalculator();

let saveTimeout: number | null = null;
async function scheduleSave() {
    if (saveTimeout) clearTimeout(saveTimeout);
    saveTimeout = window.setTimeout(async () => {
        try {
            const json = JSON.stringify(appSettings.toDict(), null, 2);
            await invoke("save_text_file", { path: "/tmp/mangajanai_settings.json", content: json });
        } catch (e) {
            console.error("Auto-save failed", e);
        }
    }, 1000);
}

async function initSetupWizard() {
    const envExists = await invoke<boolean>("check_env_exists");
    if (envExists) {
        return true;
    }
    
    // Show overlay
    const overlay = document.getElementById("setupWizardOverlay")!;
    overlay.style.display = "flex";
    
    const startBtn = document.getElementById("startSetupBtn")!;
    const gpuSelect = document.getElementById("setupGpuSelect") as HTMLSelectElement;

    if (navigator.userAgent.includes("Win")) {
        const amdOption = Array.from(gpuSelect.options).find(o => (o as HTMLOptionElement).value === "AMD");
        if (amdOption) amdOption.remove();
    }

    const step1 = document.getElementById("setupStep1")!;
    const step2 = document.getElementById("setupStep2")!;
    const logsBox = document.getElementById("setupLogsBox")!;
    const statusText = document.getElementById("setupStatusText")!;
    const continueBtn = document.getElementById("setupContinueBtn")!;
    
    listen<string>("setup-log", (e) => {
        if (e.payload === "SETUP_COMPLETE") {
            statusText.innerText = "Installation Complete!";
            statusText.style.color = "var(--success)";
            continueBtn.style.display = "block";
        } else {
            const box = logsBox as HTMLTextAreaElement;
            const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
            box.value += e.payload + "\n";
            if (atBottom) box.scrollTop = box.scrollHeight;
        }
    });
    
    return new Promise<boolean>((resolve) => {
        startBtn.onclick = async () => {
            step1.style.display = "none";
            step2.style.display = "flex";
            const gpu = gpuSelect.value;
            const isWindows = navigator.userAgent.includes("Win");
            const os = isWindows ? "Windows" : "Linux";
            
            (logsBox as HTMLTextAreaElement).value += `Starting Setup for ${os} with ${gpu} GPU...\n`;
            await invoke("run_setup_wizard", { osType: os, gpuType: gpu });
        };
        
        continueBtn.onclick = async () => {
            overlay.style.display = "none";
            resolve(true);
        };
    });
}

export async function init() {
    try {
        await initSetupWizard();
        const gpuInfo: any = await invoke("get_gpu_info");
        appendConsole(`GPU Info: ${gpuInfo.name} (${gpuInfo.vram_mb}MB)`, 'info');
        
        initSelects();
        setupEventListeners();
        
        try {
            const savedStr: string = await invoke("load_settings");
            if (savedStr) {
                const parsed = JSON.parse(savedStr);
                currentWorkflowIndex = appSettings.updateFromDict(parsed);
            }
        } catch (e) {
            // Ignore if no settings to load
        }
        
        await loadModels();
        renderWorkflow();
        
        listen("tauri://drag-drop", (event: any) => {
            const payload = event.payload as any;
            const paths = payload?.paths;
            if (paths && paths.length > 0) {
                const wf = appSettings.workflows[currentWorkflowIndex];
                if (wf.selected_tab_index === 0) wf.input_file_path = paths[0];
                else wf.input_folder_path = paths[0];
                renderWorkflow();
            }
        });
        
        listen("upscale_progress", (event: any) => {
            const msg = event.payload as string;
            handleProgressMsg(msg);
        });
        
        await listen<string>("upscale_finished", (event) => {
            const status = event.payload;
            isUpscaling = false;
            upscaleBtn.disabled = false;
            cancelBtn.disabled = true;
            appendConsole(`Upscale finished: ${status}`, status === "success" ? "success" : "info");
            mainProgress.style.width = status === "success" ? "100%" : "0%";
            if (status === "success") {
                const total = document.getElementById("progress-text")?.textContent?.split(' / ')[1] || '0 total files';
                document.getElementById("progress-text")!.textContent = `${total.replace(' total files', '')} / ${total}`;
            }
        });

        await listen<string>("download_progress", (event) => {
            appendConsole(event.payload);
        });
        
    } catch (e) {
        console.error(e);
        appendConsole(`Init error: ${e}`, 'error');
    }
}

function initSelects() {
    displayDeviceSelect.innerHTML = "";
    appSettings.display_device_map.forEach(d => {
        const opt = document.createElement("option");
        opt.value = d.name;
        opt.textContent = `${d.name} (${d.width}x${d.height})`;
        displayDeviceSelect.appendChild(opt);
    });
}

async function loadModels() {
    try {
        availableModels = await invoke("get_available_models", { modelsDir: appSettings.models_directory });
        if (availableModels.length > 0) {
            appSettings.workflows.forEach(wf => {
                wf.chains.forEach(chain => {
                    if (!chain.model_file_path || !availableModels.includes(chain.model_file_path)) {
                        chain.model_file_path = availableModels[0];
                    }
                });
            });
        }
    } catch (e) {
        console.error("Failed to load models", e);
    }
}

function renderWorkflow() {
    const wf = appSettings.workflows[currentWorkflowIndex];
    
    workflowNameInput.value = wf.workflow_name;
    if (currentWorkflowIndex === 0) {
        document.getElementById("workflow-name-sidebar")!.textContent = wf.workflow_name;
        document.getElementById("header-workflow-name")!.textContent = wf.workflow_name;
    }
    
    showAdvancedChk.checked = wf.show_advanced_settings;
    advancedSection.style.display = wf.show_advanced_settings ? "block" : "none";
    
    // Tabs
    tabBtns.forEach(btn => {
        const isMatch = (btn.getAttribute("data-tab") === "single-file" && wf.selected_tab_index === 0) ||
                        (btn.getAttribute("data-tab") === "batch-folder" && wf.selected_tab_index === 1);
        btn.classList.toggle("active", isMatch);
    });
    tabContents.forEach(content => {
        const isMatch = (content.id === "tab-single-file" && wf.selected_tab_index === 0) ||
                        (content.id === "tab-batch-folder" && wf.selected_tab_index === 1);
        content.classList.toggle("active", isMatch);
    });
    
    // Inputs
    inputFilePath.value = wf.input_file_path;
    inputFolderPath.value = wf.input_folder_path;
    upscaleArchivesChk.checked = wf.upscale_archives;
    upscaleImagesChk.checked = wf.upscale_images;
    
    outputFolderPath.value = wf.output_folder_path;
    outputFilename.value = wf.output_filename;
    overwriteFilesChk.checked = wf.overwrite_existing_files;
    
    // Formats
    formatToggles.forEach(btn => {
        const format = btn.getAttribute("data-format");
        btn.classList.remove("active");
        if (format === "webp" && wf.webp_selected) btn.classList.add("active");
        if (format === "avif" && wf.avif_selected) btn.classList.add("active");
        if (format === "png" && wf.png_selected) btn.classList.add("active");
        if (format === "jpeg" && wf.jpeg_selected) btn.classList.add("active");
    });
    
    useLosslessChk.checked = wf.use_lossless_compression;
    lossyQuality.value = wf.lossy_compression_quality.toString();
    
    if (wf.webp_selected || wf.avif_selected) {
        losslessContainer.style.display = "flex";
    } else {
        losslessContainer.style.display = "none";
    }
    
    if (wf.png_selected || (wf.webp_selected && wf.use_lossless_compression)) {
        lossyQualityContainer.style.display = "none";
    } else {
        lossyQualityContainer.style.display = "flex";
    }

    // Upscale Mode
    upscaleModeToggles.forEach(btn => {
        const m = btn.getAttribute("data-mode");
        btn.classList.remove("active");
        if (m === "scale" && wf.mode_scale_selected) btn.classList.add("active");
        if (m === "width" && wf.mode_width_selected) btn.classList.add("active");
        if (m === "height" && wf.mode_height_selected) btn.classList.add("active");
        if (m === "fit" && wf.mode_fit_to_display_selected) btn.classList.add("active");
    });
    
    document.querySelectorAll(".mode-content").forEach(el => el.classList.remove("active"));
    if (wf.mode_scale_selected) document.getElementById("mode-scale")!.classList.add("active");
    if (wf.mode_width_selected) document.getElementById("mode-width")!.classList.add("active");
    if (wf.mode_height_selected) document.getElementById("mode-height")!.classList.add("active");
    if (wf.mode_fit_to_display_selected) document.getElementById("mode-fit")!.classList.add("active");
    
    scaleFactorToggles.forEach(btn => {
        btn.classList.toggle("active", parseInt(btn.getAttribute("data-scale")!) === wf.upscale_scale_factor);
    });
    
    outputWidthVal.value = wf.resize_width_after_upscale.toString();
    outputHeightVal.value = wf.resize_height_after_upscale.toString();
    
    if (wf.display_device) {
        displayDeviceSelect.value = wf.display_device;
    }
    
    orientationToggles.forEach(btn => {
        const o = btn.getAttribute("data-orientation");
        btn.classList.toggle("active", (o === "portrait" && wf.display_portrait_selected) || (o === "landscape" && !wf.display_portrait_selected));
    });
    
    updateDisplayResPreview(wf);

    // Advanced
    grayscaleThreshold.value = wf.grayscale_detection_threshold.toString();
    grayscaleThresholdVal.textContent = wf.grayscale_detection_threshold.toString();

    // Chains
    renderChains(wf);
    renderSidebarWorkflows();
    
    // Smart Validation
    const errors = [];
    if (wf.selected_tab_index === 0 && !wf.input_file_path) errors.push("Input File is required.");
    if (wf.selected_tab_index === 1 && !wf.input_folder_path) errors.push("Input Folder is required.");
    if (!wf.output_folder_path) errors.push("Output Folder is required.");
    
    upscaleBtn.disabled = errors.length > 0 || isUpscaling;
    
    scheduleSave();
    
    // Convert native titles to custom tooltips
    document.querySelectorAll('.info-icon[title]').forEach(el => {
        el.setAttribute('data-tooltip', el.getAttribute('title')!);
        el.removeAttribute('title');
    });
}

function renderSidebarWorkflows() {
    const container = document.getElementById("custom-workflows-container")!;
    container.innerHTML = "";
    appSettings.workflows.forEach((wf, idx) => {
        if (idx === 0) return;
        const btn = document.createElement("button");
        btn.className = `nav-btn ${idx === currentWorkflowIndex ? "active" : ""}`;
        btn.innerHTML = `<span class="material-icons">bookmark</span> <span>${wf.workflow_name}</span>`;
        btn.addEventListener("click", () => {
            currentWorkflowIndex = idx;
            renderWorkflow();
        });
        container.appendChild(btn);
    });
    document.getElementById("default-workflow-btn")!.classList.toggle("active", currentWorkflowIndex === 0);
}

function updateDisplayResPreview(wf: UpscaleWorkflow) {
    const dev = appSettings.display_device_map.find(d => d.name === wf.display_device) || appSettings.display_device_map[0];
    if (dev) {
        wf.display_device = dev.name;
        wf.display_device_width = wf.display_portrait_selected ? Math.min(dev.width, dev.height) : Math.max(dev.width, dev.height);
        wf.display_device_height = wf.display_portrait_selected ? Math.max(dev.width, dev.height) : Math.min(dev.width, dev.height);
        displayResPreview.textContent = `${wf.display_device_width}px × ${wf.display_device_height}px`;
    }
}

function renderChains(wf: UpscaleWorkflow) {
    chainsContainer.innerHTML = "";
    wf.chains.forEach((chain, idx) => {
        chain.chain_number = (idx + 1).toString();
        
        const card = document.createElement("div");
        card.className = "chain-card";
        
        let modelOptions = `<option value="">-- No Model --</option>`;
        availableModels.forEach(m => {
            const selected = m === chain.model_file_path ? "selected" : "";
            modelOptions += `<option value="${m}" ${selected}>${m}</option>`;
        });
        
        card.innerHTML = `
            <div class="chain-header">
                <h4>Chain ${chain.chain_number}</h4>
                <button class="chain-remove-btn" data-idx="${idx}"><span class="material-icons">remove_circle</span> Remove</button>
            </div>
            <div class="chain-body">
                <div class="chain-sub-section">Activation Condition</div>
                <div class="input-row align-center">
                    <label>Resolution Range (px) <span class="material-icons info-icon" data-tooltip="Range of image resolutions to activate this chain. Select a common resolution from the drop down or type a custom resolution. A dimension value of 0 means any value for that dimension.">help_outline</span></label>
                    <div class="number-input-group"><input type="text" class="chain-min-res" list="common-resolutions" value="${chain.min_resolution}" style="width:100px;"><span>px</span></div>
                    <span style="padding:0 10px;"> - </span>
                    <div class="number-input-group"><input type="text" class="chain-max-res" list="common-resolutions" value="${chain.max_resolution}" style="width:100px;"><span>px</span></div>
                </div>
                <div class="input-row align-center mt-10">
                    <label>Scaling Factor Range (x) <span class="material-icons info-icon" data-tooltip="Range of necessary scaling factor to activate this chain. A maximum scaling factor of 0 means no maximum limit.">help_outline</span></label>
                    <div class="number-input-group"><input type="number" class="chain-min-scale" value="${chain.min_scale_factor}" min="0" style="width:100px;"><span>x</span></div>
                    <span style="padding:0 10px;"> - </span>
                    <div class="number-input-group"><input type="number" class="chain-max-scale" value="${chain.max_scale_factor}" min="0" style="width:100px;"><span>x</span></div>
                </div>
                <div class="checkbox-group mt-10" style="margin-left:0; margin-bottom:10px;">
                    <label class="checkbox-label"><input type="checkbox" class="chain-color" ${chain.is_color ? "checked" : ""}> Is Color Image</label>
                    <label class="checkbox-label"><input type="checkbox" class="chain-gray" ${chain.is_grayscale ? "checked" : ""}> Is Grayscale Image <span class="material-icons info-icon" data-tooltip="Whether the image is color and/or grayscale. Images with faint color due to artifacts are still considered grayscale.">help_outline</span></label>
                </div>
                
                <div class="chain-sub-section mt-20">Upscale Settings</div>
                <div class="checkbox-group mt-10" style="margin-left:0; margin-bottom:10px;">
                    <label class="checkbox-label"><input type="checkbox" class="chain-auto-levels" ${chain.auto_adjust_levels ? "checked" : ""}> Auto Adjust Levels on Grayscale <span class="material-icons info-icon" data-tooltip="Automatically increase the contrast of all grayscale images if necessary. Recommended for faded images.">help_outline</span></label>
                </div>
                <div class="input-row align-center mt-10">
                    <label style="min-width:140px;">Resize Height Before Upscale <span class="material-icons info-icon" data-tooltip="Resize each image to this height before upscaling, set to 0 to disable.">help_outline</span></label>
                    <div class="number-input-group"><input type="number" class="chain-rh" value="${chain.resize_height_before_upscale}" min="0"><span>px</span></div>
                </div>
                <div class="input-row align-center mt-10">
                    <label style="min-width:140px;">Resize Width Before Upscale <span class="material-icons info-icon" data-tooltip="Resize each image to this width before upscaling, set to 0 to disable.">help_outline</span></label>
                    <div class="number-input-group"><input type="number" class="chain-rw" value="${chain.resize_width_before_upscale}" min="0"><span>px</span></div>
                </div>
                <div class="input-row align-center mt-10">
                    <label style="min-width:140px;">Resize Factor Before Upscale <span class="material-icons info-icon" data-tooltip="Resize each image by this factor before upscaling. Ignored if Resize Height is specified.">help_outline</span></label>
                    <div class="number-input-group"><input type="number" class="chain-rf" value="${chain.resize_factor_before_upscale}" min="0"><span>%</span></div>
                </div>
                <div class="input-row align-center mt-10">
                    <label style="min-width:140px;">Model <span class="material-icons info-icon" data-tooltip="The upscaling model to run. Select No Model to skip upscaling for this chain.">help_outline</span></label>
                    <select class="chain-model">${modelOptions}</select>
                    <button class="btn btn-secondary chain-open-models-btn" style="margin-left:5px;"><span class="material-icons">folder_open</span> Open Models Directory</button>
                </div>
                <div class="input-row align-center mt-10">
                    <label style="min-width:140px;">Model Tile Size <span class="material-icons info-icon" title="Tile size to use. Larger is better if VRAM allows. Auto is recommended.">help_outline</span></label>
                    <div class="number-input-group">
                        <select class="chain-tile" style="width:160px;">
                            <option value="Auto (Estimate)" ${chain.model_tile_size === "Auto (Estimate)" ? "selected" : ""}>Auto (Estimate)</option>
                            <option value="128" ${chain.model_tile_size === "128" ? "selected" : ""}>128</option>
                            <option value="256" ${chain.model_tile_size === "256" ? "selected" : ""}>256</option>
                            <option value="512" ${chain.model_tile_size === "512" ? "selected" : ""}>512</option>
                            <option value="1024" ${chain.model_tile_size === "1024" ? "selected" : ""}>1024</option>
                        </select>
                        <span>px</span>
                    </div>
                </div>
            </div>
        `;
        chainsContainer.appendChild(card);
        
        // Listeners for this chain
        card.querySelector(".chain-remove-btn")?.addEventListener("click", () => {
            wf.chains.splice(idx, 1);
            renderWorkflow();
        });
        
        card.querySelector(".chain-min-res")?.addEventListener("change", (e) => wf.chains[idx].min_resolution = (e.target as HTMLInputElement).value);
        card.querySelector(".chain-max-res")?.addEventListener("change", (e) => wf.chains[idx].max_resolution = (e.target as HTMLInputElement).value);
        card.querySelector(".chain-min-scale")?.addEventListener("change", (e) => wf.chains[idx].min_scale_factor = parseInt((e.target as HTMLInputElement).value));
        card.querySelector(".chain-max-scale")?.addEventListener("change", (e) => wf.chains[idx].max_scale_factor = parseInt((e.target as HTMLInputElement).value));
        card.querySelector(".chain-color")?.addEventListener("change", (e) => wf.chains[idx].is_color = (e.target as HTMLInputElement).checked);
        card.querySelector(".chain-gray")?.addEventListener("change", (e) => wf.chains[idx].is_grayscale = (e.target as HTMLInputElement).checked);
        card.querySelector(".chain-auto-levels")?.addEventListener("change", (e) => wf.chains[idx].auto_adjust_levels = (e.target as HTMLInputElement).checked);
        card.querySelector(".chain-rh")?.addEventListener("change", (e) => wf.chains[idx].resize_height_before_upscale = parseInt((e.target as HTMLInputElement).value));
        card.querySelector(".chain-rw")?.addEventListener("change", (e) => wf.chains[idx].resize_width_before_upscale = parseInt((e.target as HTMLInputElement).value));
        card.querySelector(".chain-rf")?.addEventListener("change", (e) => wf.chains[idx].resize_factor_before_upscale = parseFloat((e.target as HTMLInputElement).value));
        card.querySelector(".chain-model")?.addEventListener("change", (e) => wf.chains[idx].model_file_path = (e.target as HTMLSelectElement).value);
        card.querySelector(".chain-open-models-btn")?.addEventListener("click", () => {
            const mPath = appSettings.models_directory === "backend/models" ? "/media/abdalrahman/GAMES/MangaJaNaiConverter-linux/backend/models" : appSettings.models_directory;
            invoke("open_folder", { path: mPath }).catch(e => appendConsole("Failed to open models folder: " + e));
        });
        card.querySelector(".chain-tile")?.addEventListener("change", (e) => wf.chains[idx].model_tile_size = (e.target as HTMLSelectElement).value);
    });
}

function handleProgressMsg(msg: string) {
    if (msg.startsWith("ERROR:")) {
        appendConsole(msg.substring(6), 'error');
    } else {
        appendConsole(msg);
    }
    
    // Parse progress formats
    if (msg.startsWith("PROGRESS=")) {
        const parts = msg.substring(9).split(" ");
        const key = parts[0];
        const val = parts.length > 1 ? parseInt(parts[1]) : 0;
        
        if (key === "batch_total_files") {
            totalArchives = val;
            currentTotalArchives = 0;
        } else if (key === "total_images") {
            totalArchiveImages = val;
            currentArchiveImages = 0;
            archiveEtaCalc.reset();
        } else if (key === "postprocess_worker_zip_image") {
            currentArchiveImages++;
        } else if (key === "postprocess_worker_zip_archive") {
            currentTotalArchives++;
            currentArchiveImages = totalArchiveImages; // max it out
        }

        // Calculate granular progress
        const archiveProgressRatio = totalArchiveImages > 0 ? (currentArchiveImages / totalArchiveImages) : 0;
        const totalProgress = totalArchives > 0 ? ((currentTotalArchives + archiveProgressRatio) / totalArchives) : 0;

        // Update ETA Calculators
        archiveEtaCalc.update(archiveProgressRatio);
        totalEtaCalc.update(totalProgress);

        // Update Archives Progress UI
        if (totalArchives > 0) {
            const pct = Math.min(100, Math.round(totalProgress * 100));
            mainProgress.style.width = `${pct}%`;
            mainProgressText.textContent = `${currentTotalArchives} / ${totalArchives} total files`;
            
            // ETA Total
            if (totalEtaCalc.ETAIsAvailable) {
                const remainingTotal = totalEtaCalc.ETR_Seconds;
                totalEtrText.textContent = `Remaining Time (Total): ${formatTime(remainingTotal)}`;
                const finishTime = new Date(Date.now() + remainingTotal * 1000);
                totalEtaText.textContent = `Estimated Finish Time: ${finishTime.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}`;
            } else {
                totalEtrText.textContent = `Remaining Time (Total): calculating...`;
                totalEtaText.textContent = `Estimated Finish Time: calculating...`;
            }
        }
        
        // Update Current Archive UI
        if (totalArchiveImages > 0) {
            const pct = Math.min(100, Math.round(archiveProgressRatio * 100));
            archiveProgress.style.width = `${pct}%`;
            archiveProgressText.textContent = `${currentArchiveImages} / ${totalArchiveImages} images in current archive`;
            
            // ETA Archive
            if (archiveEtaCalc.ETAIsAvailable) {
                archiveEtrText.textContent = `Remaining Time (Current Archive): ${formatTime(archiveEtaCalc.ETR_Seconds)}`;
            } else {
                archiveEtrText.textContent = `Remaining Time (Current Archive): calculating...`;
            }
        }
        
        return; // Don't print PROGRESS= lines to console
    }
}

function formatTime(secs: number): string {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    const s = Math.floor(secs % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function appendConsole(msg: string, type: string = '') {
    const div = document.createElement("div");
    div.className = `console-line ${type}`;
    
    const timestamp = new Date().toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const timeSpan = document.createElement("span");
    timeSpan.className = "console-time";
    timeSpan.textContent = `[${timestamp}] `;
    
    const msgSpan = document.createElement("span");
    msgSpan.textContent = msg;
    
    div.appendChild(timeSpan);
    div.appendChild(msgSpan);
    
    consoleOutput.appendChild(div);
    consoleOutput.scrollTop = consoleOutput.scrollHeight;
}

function setupEventListeners() {
    workflowNameInput.addEventListener("input", (e) => {
        const val = (e.target as HTMLInputElement).value;
        appSettings.workflows[currentWorkflowIndex].workflow_name = val;
        if (currentWorkflowIndex === 0) {
            document.getElementById("workflow-name-sidebar")!.textContent = val;
            document.getElementById("header-workflow-name")!.textContent = val;
        } else {
            renderSidebarWorkflows();
        }
    });

    showAdvancedChk.addEventListener("change", (e) => {
        appSettings.workflows[currentWorkflowIndex].show_advanced_settings = (e.target as HTMLInputElement).checked;
        renderWorkflow();
    });

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const tab = btn.getAttribute("data-tab");
            appSettings.workflows[currentWorkflowIndex].selected_tab_index = tab === "single-file" ? 0 : 1;
            renderWorkflow();
        });
    });

    // Inputs updates
    inputFilePath.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].input_file_path = (e.target as HTMLInputElement).value);
    inputFolderPath.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].input_folder_path = (e.target as HTMLInputElement).value);
    upscaleArchivesChk.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].upscale_archives = (e.target as HTMLInputElement).checked);
    upscaleImagesChk.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].upscale_images = (e.target as HTMLInputElement).checked);
    outputFolderPath.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].output_folder_path = (e.target as HTMLInputElement).value);
    outputFilename.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].output_filename = (e.target as HTMLInputElement).value);
    overwriteFilesChk.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].overwrite_existing_files = (e.target as HTMLInputElement).checked);

    // Browsing
    browseInputFileBtn.addEventListener("click", async () => {
        const selected = await open({ directory: false, defaultPath: "/media/abdalrahman/GAMES/MangaJaNaiConverter-linux" });
        if (selected) {
            appSettings.workflows[currentWorkflowIndex].input_file_path = selected as string;
            renderWorkflow();
        }
    });
    browseInputFolderBtn.addEventListener("click", async () => {
        const selected = await open({ directory: true, defaultPath: "/media/abdalrahman/GAMES/MangaJaNaiConverter-linux" });
        if (selected) {
            appSettings.workflows[currentWorkflowIndex].input_folder_path = selected as string;
            renderWorkflow();
        }
    });
    browseOutputFolderBtn.addEventListener("click", async () => {
        const selected = await open({ directory: true, defaultPath: "/media/abdalrahman/GAMES/MangaJaNaiConverter-linux" });
        if (selected) {
            appSettings.workflows[currentWorkflowIndex].output_folder_path = selected as string;
            renderWorkflow();
        }
    });

    // Formats
    formatToggles.forEach(btn => {
        btn.addEventListener("click", () => {
            const format = btn.getAttribute("data-format");
            const wf = appSettings.workflows[currentWorkflowIndex];
            wf.webp_selected = format === "webp";
            wf.avif_selected = format === "avif";
            wf.png_selected = format === "png";
            wf.jpeg_selected = format === "jpeg";
            renderWorkflow();
        });
    });

    useLosslessChk.addEventListener("change", (e) => {
        appSettings.workflows[currentWorkflowIndex].use_lossless_compression = (e.target as HTMLInputElement).checked;
        renderWorkflow();
    });
    lossyQuality.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].lossy_compression_quality = parseInt((e.target as HTMLInputElement).value));

    // Upscale Modes
    upscaleModeToggles.forEach(btn => {
        btn.addEventListener("click", () => {
            const mode = btn.getAttribute("data-mode");
            const wf = appSettings.workflows[currentWorkflowIndex];
            wf.mode_scale_selected = mode === "scale";
            wf.mode_width_selected = mode === "width";
            wf.mode_height_selected = mode === "height";
            wf.mode_fit_to_display_selected = mode === "fit";
            renderWorkflow();
        });
    });

    scaleFactorToggles.forEach(btn => {
        btn.addEventListener("click", () => {
            appSettings.workflows[currentWorkflowIndex].upscale_scale_factor = parseInt(btn.getAttribute("data-scale")!);
            renderWorkflow();
        });
    });

    outputWidthVal.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].resize_width_after_upscale = parseInt((e.target as HTMLInputElement).value));
    outputHeightVal.addEventListener("change", (e) => appSettings.workflows[currentWorkflowIndex].resize_height_after_upscale = parseInt((e.target as HTMLInputElement).value));

    displayDeviceSelect.addEventListener("change", (e) => {
        appSettings.workflows[currentWorkflowIndex].display_device = (e.target as HTMLSelectElement).value;
        renderWorkflow();
    });

    orientationToggles.forEach(btn => {
        btn.addEventListener("click", () => {
            appSettings.workflows[currentWorkflowIndex].display_portrait_selected = btn.getAttribute("data-orientation") === "portrait";
            renderWorkflow();
        });
    });

    grayscaleThreshold.addEventListener("input", (e) => {
        const val = (e.target as HTMLInputElement).value;
        grayscaleThresholdVal.textContent = val;
        appSettings.workflows[currentWorkflowIndex].grayscale_detection_threshold = parseInt(val);
    });

    addChainBtn.addEventListener("click", () => {
        appSettings.workflows[currentWorkflowIndex].chains.push(new UpscaleChain());
        renderWorkflow();
    });

    // Workflow Actions
    const handleAddWorkflow = () => {
        const newWf = new UpscaleWorkflow(`Custom Workflow ${appSettings.workflows.length}`);
        appSettings.workflows.push(newWf);
        currentWorkflowIndex = appSettings.workflows.length - 1;
        renderWorkflow();
    };
    
    document.getElementById("sidebar-add-workflow-btn")?.addEventListener("click", handleAddWorkflow);

    importWorkflowBtn.addEventListener("click", async () => {
        const file = await open({ directory: false, filters: [{ name: "JSON", extensions: ["json"] }] });
        if (file) {
            try {
                const content = await invoke("read_text_file", { path: file as string });
                const parsed = JSON.parse(content as string);
                const newWf = new UpscaleWorkflow();
                Object.assign(newWf, parsed);
                appSettings.workflows.push(newWf);
                currentWorkflowIndex = appSettings.workflows.length - 1;
                renderWorkflow();
            } catch (e) {
                alert(`Failed to import workflow: ${e}`);
            }
        }
    });

    exportWorkflowBtn.addEventListener("click", async () => {
        const wf = appSettings.workflows[currentWorkflowIndex];
        const json = JSON.stringify(wf.toDict(), null, 2);
        try {
            const savedPath = await invoke("save_workflow", { jsonContent: json, defaultName: wf.workflow_name });
            if (savedPath) alert(`Workflow exported to ${savedPath}`);
        } catch (e) {
            alert(`Failed to export workflow: ${e}`);
        }
    });

    resetWorkflowBtn.addEventListener("click", async () => {
        if (await confirm("Reset current workflow to default settings?", { title: "Confirm Reset", kind: "warning" })) {
            appSettings.workflows[currentWorkflowIndex] = new UpscaleWorkflow(appSettings.workflows[currentWorkflowIndex].workflow_name, currentWorkflowIndex);
            renderWorkflow();
        }
    });

    // Console
    toggleConsoleBtn.addEventListener("click", () => {
        if (consolePanel.style.display === "flex") {
            consolePanel.style.display = "none";
            toggleConsoleBtn.classList.remove("toggle-active");
        } else {
            consolePanel.style.display = "flex";
            toggleConsoleBtn.classList.add("toggle-active");
        }
    });
    closeConsoleBtn.addEventListener("click", () => {
        consolePanel.style.display = "none";
        toggleConsoleBtn.classList.remove("toggle-active");
    });
    
    const clearConsoleBtn = document.getElementById("clear-console-btn");
    if (clearConsoleBtn) {
        clearConsoleBtn.addEventListener("click", () => {
            consoleOutput.innerHTML = "";
        });
    }

    const floatConsoleBtn = document.getElementById("float-console-btn");
    if (floatConsoleBtn) {
        floatConsoleBtn.addEventListener("click", () => {
            const isFloating = consolePanel.classList.toggle("floating");
            floatConsoleBtn.innerHTML = isFloating 
                ? '<span class="material-icons" style="font-size: 16px;">open_in_browser</span>' 
                : '<span class="material-icons" style="font-size: 16px;">open_in_new</span>';
            floatConsoleBtn.setAttribute("data-tooltip", isFloating ? "Dock Console" : "Float Console");
            
            if (isFloating) {
                // Set explicit top/left so the bottom-right resize handle works natively
                consolePanel.style.left = `${window.innerWidth - 624}px`;
                consolePanel.style.top = `${window.innerHeight - 424}px`;
                consolePanel.style.bottom = "auto";
                consolePanel.style.right = "auto";
            } else {
                consolePanel.style.top = "";
                consolePanel.style.left = "";
                consolePanel.style.bottom = "";
                consolePanel.style.right = "";
                consolePanel.style.width = "";
                consolePanel.style.height = "";
            }
        });

        let isDraggingConsole = false;
        let dragStartX = 0, dragStartY = 0;
        let consoleStartX = 0, consoleStartY = 0;
        const consoleHeader = consolePanel.querySelector(".console-header") as HTMLElement;

        consoleHeader.addEventListener("mousedown", (e) => {
            if (!consolePanel.classList.contains("floating") || (e.target as HTMLElement).closest('.btn-icon')) return;
            isDraggingConsole = true;
            dragStartX = e.clientX;
            dragStartY = e.clientY;
            const rect = consolePanel.getBoundingClientRect();
            consoleStartX = rect.left;
            consoleStartY = rect.top;
            e.preventDefault();
        });

        document.addEventListener("mousemove", (e) => {
            if (!isDraggingConsole) return;
            const dx = e.clientX - dragStartX;
            const dy = e.clientY - dragStartY;
            consolePanel.style.left = `${consoleStartX + dx}px`;
            consolePanel.style.top = `${consoleStartY + dy}px`;
            consolePanel.style.bottom = "auto";
            consolePanel.style.right = "auto";
        });

        document.addEventListener("mouseup", () => {
            isDraggingConsole = false;
        });
    }

    document.getElementById("default-workflow-btn")!.addEventListener("click", () => {
        currentWorkflowIndex = 0;
        renderWorkflow();
    });

    document.getElementById("theme-toggle-btn")!.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
        applyTheme(current === "dark" ? "light" : "dark");
    });

    // Settings Modal
    appSettingsBtn.addEventListener("click", () => {
        settingDevice.value = appSettings.use_cpu ? "cpu" : "gpu";
        settingFp16.checked = appSettings.use_fp16;
        settingModelsDir.value = appSettings.models_directory;
        settingsModal.style.display = "flex";
    });

    closeSettingsBtn.addEventListener("click", () => settingsModal.style.display = "none");
    const browseModelsBtn = document.getElementById("browse-models-btn")!;
    browseModelsBtn.addEventListener("click", async () => {
        const selected = await open({ directory: true, defaultPath: "/media/abdalrahman/GAMES/MangaJaNaiConverter-linux" });
        if (selected) settingModelsDir.value = selected as string;
    });

    saveSettingsBtn.addEventListener("click", async () => {
        appSettings.use_cpu = settingDevice.value === "cpu";
        appSettings.use_fp16 = settingFp16.checked;
        if (appSettings.models_directory !== settingModelsDir.value) {
            appSettings.models_directory = settingModelsDir.value;
            await loadModels();
            renderWorkflow();
        }
        settingsModal.style.display = "none";
    });

    // Upscale Execution
    upscaleBtn.addEventListener("click", async () => {
        if (isUpscaling) return;
        
        const wf = appSettings.workflows[currentWorkflowIndex];
        
        let errors = [];
        if (wf.selected_tab_index === 0 && !wf.input_file_path) errors.push("Input File is required.");
        if (wf.selected_tab_index === 1 && !wf.input_folder_path) errors.push("Input Folder is required.");
        if (!wf.output_folder_path) errors.push("Output Folder is required.");
        
        if (errors.length > 0) {
            errors.push("selected for upscaling. At least one file must be selected.");
            validationMsg.textContent = errors.join(" ");
            return;
        }
        validationMsg.textContent = "";
        
        // Validate models
        const missingModels: string[] = [];
        wf.chains.forEach(chain => {
            if (chain.model_file_path && chain.model_file_path !== "No Model" && !availableModels.includes(chain.model_file_path)) {
                if (!missingModels.includes(chain.model_file_path)) {
                    missingModels.push(chain.model_file_path);
                }
            }
        });
        
        let shouldDownload = false;
        let downloadMessage = "";

        if (availableModels.length === 0) {
            shouldDownload = true;
            downloadMessage = "No models were found in your models directory.\n\nWould you like to automatically download and extract the official MangaJaNai and IllustrationJaNai models now (~2GB)?\nThis might take a while depending on your internet connection.";
        } else if (missingModels.length > 0) {
            shouldDownload = true;
            downloadMessage = `The following models are missing from your models directory:\n\n${missingModels.join("\n")}\n\nWould you like to automatically download and extract them now (~2GB)?\nThis might take a while depending on your internet connection.`;
        }

        if (shouldDownload) {
            if (await confirm(downloadMessage, { title: "Missing Models", kind: "warning" })) {
                consolePanel.style.display = "flex";
                appendConsole("Starting model download...");
                isUpscaling = true;
                upscaleBtn.disabled = true;
                cancelBtn.disabled = true;
                try {
                    await invoke("download_models");
                    appendConsole("Models downloaded and extracted successfully!");
                    availableModels = await invoke("get_available_models", { modelsDir: appSettings.models_directory });
                    await loadModels(); // This auto-assigns availableModels[0] to empty chains!
                    renderWorkflow();
                    isUpscaling = false;
                    upscaleBtn.disabled = false;
                    upscaleBtn.click(); // retry upscale automatically
                } catch (e) {
                    appendConsole(`Failed to download models: ${e}`, 'error');
                    isUpscaling = false;
                    upscaleBtn.disabled = false;
                }
            }
            return;
        }
        
        // Timer
        const timerInt = setInterval(() => {
            if (!isUpscaling) {
                clearInterval(timerInt);
                return;
            }
            elapsedTimeText.textContent = `Elapsed Time: ${formatTime((Date.now() - startTime) / 1000)}`;
        }, 1000);

        try {
            const settingsJson = JSON.stringify(appSettings.toDict(), null, 2);
            const path: string = await invoke("save_settings", { settingsJson });
            appendConsole(`Settings saved to ${path}`);
            
            consolePanel.style.display = "flex";
            toggleConsoleBtn.classList.add("toggle-active");
            appendConsole("Starting upscale process...");
            isUpscaling = true;
            upscaleBtn.disabled = true;
            cancelBtn.disabled = false;
            
            // reset progress
            consoleOutput.innerHTML = "";
            mainProgress.style.width = "0%";
            mainProgressText.textContent = "0 / 0 total files";
            archiveProgress.style.width = "0%";
            archiveProgressText.textContent = "0 / 0 images in current archive";
            elapsedTimeText.textContent = "Elapsed Time: 00:00:00";
            totalEtrText.textContent = "Remaining Time (Total): --:--:--";
            archiveEtrText.textContent = "Remaining Time (Current Archive): --:--:--";
            totalEtaText.textContent = "Estimated Finish Time: --:--:--";
            startTime = Date.now();
            archiveEtaCalc.reset();
            totalEtaCalc.reset();
            
            await invoke("start_upscale", { settingsPath: path });
        } catch (e) {
            console.error(e);
            appendConsole(`Failed to start upscale: ${e}`, 'error');
            isUpscaling = false;
            upscaleBtn.disabled = false;
            cancelBtn.disabled = true;
            clearInterval(timerInt);
        }
    });

    cancelBtn.addEventListener("click", async () => {
        if (!isUpscaling) return;
        appendConsole("Cancelling...", 'info');
        try {
            await invoke("cancel_upscale");
        } catch (e) {
            appendConsole(`Failed to cancel: ${e}`, 'error');
        }
    });
}

// Run Init
window.addEventListener("DOMContentLoaded", () => {
    init();
});
