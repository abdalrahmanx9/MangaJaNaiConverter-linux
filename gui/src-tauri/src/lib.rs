use serde::Serialize;
use std::process::{Command, Stdio, Child};
use std::sync::{Arc, Mutex};
use std::io::{BufRead, BufReader};
use tauri::{AppHandle, Emitter, State};
use std::path::PathBuf;
use std::fs;

mod setup_commands;

struct UpscaleState {
    process: Option<Child>,
}

#[derive(Serialize)]
struct GpuInfo {
    name: String,
    vram_mb: u32,
    available: bool,
    driver_loaded: bool,
    rocmsmi_available: bool,
}

#[tauri::command]
fn get_gpu_info() -> GpuInfo {
    let mut info = GpuInfo {
        name: String::new(),
        vram_mb: 0,
        available: false,
        driver_loaded: false,
        rocmsmi_available: false,
    };
    
    if let Ok(output) = Command::new("rocminfo").output() {
        if output.status.success() {
            info.rocmsmi_available = true;
            let stdout = String::from_utf8_lossy(&output.stdout);
            if stdout.contains("AMD Ryzen") || stdout.contains("gfx") {
                info.driver_loaded = true;
            }
            
            for line in stdout.lines() {
                if line.contains("Marketing Name") || line.contains("Name:") {
                    if line.contains("Radeon RX") {
                        if let Some(idx) = line.find("Radeon RX") {
                            info.name = line[idx + "Radeon ".len()..].trim().to_string();
                            if info.name.contains("RX") {
                                info.name = format!("AMD {}", info.name);
                            }
                        }
                    }
                }
                if line.contains("Size:") && line.contains("KB") {
                    if let Some(idx1) = line.find("Size:") {
                        if let Some(idx2) = line.find("KB") {
                            let size_str = &line[idx1 + 5..idx2].trim();
                            if let Ok(size_kb) = size_str.parse::<u32>() {
                                if size_kb > 1000000 {
                                    info.vram_mb = size_kb / 1024;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    if let Ok(output) = Command::new("rocm-smi").arg("--showtopo").output() {
        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            if stdout.contains("GPU") {
                info.available = true;
            }
        }
    }
    
    if let Ok(output) = Command::new("lsmod").output() {
        if String::from_utf8_lossy(&output.stdout).contains("amdgpu") {
            info.driver_loaded = true;
        }
    }
    
    if info.name.is_empty() && info.available {
        info.name = "AMD GPU".to_string();
    }
    info
}

#[tauri::command]
fn get_available_models(models_dir: String) -> Vec<String> {
    let mut models = Vec::new();
    let mut root = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if root.ends_with("src-tauri") {
        root = root.parent().unwrap().to_path_buf();
    }
    if root.ends_with("gui") {
        root = root.parent().unwrap().to_path_buf();
    }
    let target_dir = root.join(&models_dir);
    if let Ok(entries) = fs::read_dir(&target_dir) {
        for entry in entries.flatten() {
            if let Ok(meta) = fs::metadata(entry.path()) {
                if meta.is_file() {
                    let name = entry.file_name().to_string_lossy().into_owned();
                    if name.ends_with(".pth") || name.ends_with(".safetensors") {
                        models.push(name);
                    }
                }
            }
        }
    }
    models.sort();
    models
}

#[tauri::command]
fn start_upscale(app: AppHandle, settings_path: String, state: State<'_, Arc<Mutex<UpscaleState>>>) -> Result<(), String> {
    let mut root = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if root.ends_with("src-tauri") {
        root = root.parent().unwrap().to_path_buf();
    }
    if root.ends_with("gui") {
        root = root.parent().unwrap().to_path_buf();
    }
    let backend_src = root.join("backend").join("src");
    let runtime_dir = backend_src.join("python-runtime");
    let python_install_dir = runtime_dir.join("python");
    let uv_exe = runtime_dir.join(if cfg!(target_os = "windows") { "uv.exe" } else { "uv" });
    let script_path = backend_src.join("run_upscale.py");

    // Resolve the actual python path via uv
    let python_exe = if uv_exe.exists() {
        let output = Command::new(&uv_exe)
            .args(&["python", "find", "3.12"])
            .env("UV_PYTHON_INSTALL_DIR", &python_install_dir)
            .current_dir(&backend_src)
            .output()
            .ok();
        output
            .filter(|o| o.status.success())
            .map(|o| PathBuf::from(String::from_utf8_lossy(&o.stdout).trim().to_string()))
            .unwrap_or_else(|| PathBuf::from(if cfg!(target_os = "windows") { "python" } else { "python3" }))
    } else {
        PathBuf::from(if cfg!(target_os = "windows") { "python" } else { "python3" })
    };

    let mut cmd = Command::new(&python_exe);

    let mut child = cmd
        .current_dir(&root)
        .arg(&script_path)
        .arg("--settings")
        .arg(&settings_path)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to spawn upscaler: {}", e))?;
        
    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();
    
    {
        let mut state_lock = state.lock().unwrap();
        state_lock.process = Some(child);
    }
    
    let app_clone = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(l) = line {
                app_clone.emit("upscale_progress", l).unwrap_or(());
            }
        }
    });
    
    let app_clone2 = app.clone();
    std::thread::spawn(move || {
        let reader = BufReader::new(stderr);
        for line in reader.lines() {
            if let Ok(l) = line {
                app_clone2.emit("upscale_progress", format!("ERROR: {}", l)).unwrap_or(());
            }
        }
    });
    
    let app_clone3 = app.clone();
    let state_clone = state.inner().clone();
    std::thread::spawn(move || {
        loop {
            let status = {
                let mut state_lock = state_clone.lock().unwrap();
                if let Some(child) = state_lock.process.as_mut() {
                    child.try_wait().unwrap_or(None)
                } else {
                    None // Could be cancelled
                }
            };
            
            if let Some(s) = status {
                // Remove from state
                {
                    let mut state_lock = state_clone.lock().unwrap();
                    state_lock.process.take();
                }
                
                if s.success() {
                    app_clone3.emit("upscale_finished", "success").unwrap_or(());
                } else {
                    app_clone3.emit("upscale_finished", "failed").unwrap_or(());
                }
                break;
            }
            
            let is_none = {
                let state_lock = state_clone.lock().unwrap();
                state_lock.process.is_none()
            };
            if is_none {
                break; // Handled by cancel_upscale
            }
            
            std::thread::sleep(std::time::Duration::from_millis(500));
        }
    });
    
    Ok(())
}

#[tauri::command]
async fn download_models(app: AppHandle) -> Result<(), String> {
    let mut root = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if root.ends_with("src-tauri") {
        root = root.parent().unwrap().to_path_buf();
    }
    if root.ends_with("gui") {
        root = root.parent().unwrap().to_path_buf();
    }
    let models_dir = root.join("backend").join("models");
    
    let _ = fs::create_dir_all(&models_dir);
    
    // Remove broken symlinks just in case
    if let Ok(entries) = fs::read_dir(&models_dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if let Ok(meta) = fs::symlink_metadata(&path) {
                if meta.file_type().is_symlink() && !path.exists() {
                    let _ = fs::remove_file(&path);
                }
            }
        }
    }
    
    let urls = vec![
        "https://github.com/the-database/MangaJaNai/releases/download/1.0.0/MangaJaNai_V1_ModelsOnly.zip",
        "https://github.com/the-database/MangaJaNai/releases/download/3.0.0/IllustrationJaNai_V3denoise.zip",
        "https://github.com/the-database/MangaJaNai/releases/download/3.0.0/IllustrationJaNai_V3detail.zip"
    ];
    
    for url in urls {
        let name = url.split('/').last().unwrap().to_string();
        app.emit("download_progress", format!("Downloading {}...", name)).unwrap_or(());
        let zip_path = models_dir.join("temp_models.zip");
        
        let mut child = Command::new("wget")
            .arg("-q")
            .arg("--show-progress")
            .arg("-O")
            .arg(&zip_path)
            .arg(url)
            .stderr(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn wget: {}", e))?;
            
        let stderr = child.stderr.take().unwrap();
        let app_clone = app.clone();
        let name_clone = name.clone();
        
        std::thread::spawn(move || {
            let reader = BufReader::new(stderr);
            for mut line in reader.lines().flatten() {
                line = line.trim().to_string();
                if !line.is_empty() {
                    app_clone.emit("download_progress", format!("[{}] {}", name_clone, line)).unwrap_or(());
                }
            }
        });
        
        let status = child.wait().map_err(|e| format!("Failed to wait for wget: {}", e))?;
        if !status.success() {
            return Err(format!("wget failed to download {}", url));
        }
        
        app.emit("download_progress", format!("Extracting {}...", name)).unwrap_or(());
        
        let mut unzip_child = Command::new("unzip")
            .arg("-o")
            .arg(&zip_path)
            .arg("-d")
            .arg(&models_dir)
            .stdout(Stdio::piped())
            .spawn()
            .map_err(|e| format!("Failed to spawn unzip: {}", e))?;
            
        let stdout = unzip_child.stdout.take().unwrap();
        let app_clone = app.clone();
        
        std::thread::spawn(move || {
            let reader = BufReader::new(stdout);
            for line in reader.lines().flatten() {
                app_clone.emit("download_progress", format!("unzip: {}", line)).unwrap_or(());
            }
        });
        
        let unzip_status = unzip_child.wait().map_err(|e| format!("Failed to wait for unzip: {}", e))?;
        if !unzip_status.success() {
            return Err("unzip failed to extract models".to_string());
        }
        
        let _ = fs::remove_file(&zip_path);
    }
    
    app.emit("download_progress", "Download complete!").unwrap_or(());
    Ok(())
}

#[tauri::command]
fn cancel_upscale(app: AppHandle, state: State<'_, Arc<Mutex<UpscaleState>>>) -> Result<(), String> {
    let mut state_lock = state.lock().unwrap();
    if let Some(mut child) = state_lock.process.take() {
        let _ = child.kill();
        let _ = child.wait();
        app.emit("upscale_finished", "cancelled").unwrap_or(());
        Ok(())
    } else {
        Err("No process running".to_string())
    }
}

#[tauri::command]
fn save_settings(settings_json: String) -> Result<String, String> {
    let temp_dir = std::env::temp_dir();
    let file_path = temp_dir.join("mangajanai_settings.json");
    fs::write(&file_path, settings_json).map_err(|e| format!("Failed to write settings: {}", e))?;
    Ok(file_path.to_string_lossy().to_string())
}


#[tauri::command]
fn load_settings() -> Result<String, String> {
    let temp_dir = std::env::temp_dir();
    let file_path = temp_dir.join("mangajanai_settings.json");
    if file_path.exists() {
        fs::read_to_string(&file_path).map_err(|e| format!("Failed to read settings: {}", e))
    } else {
        Err("No settings found".to_string())
    }
}

#[tauri::command]
fn read_text_file(path: String) -> Result<String, String> {
    fs::read_to_string(&path).map_err(|e| e.to_string())
}

#[tauri::command]
fn save_workflow(app: tauri::AppHandle, json_content: String, default_name: String) -> Result<String, String> {
    use tauri_plugin_dialog::DialogExt;
    let (tx, rx) = std::sync::mpsc::channel();
    app.dialog()
        .file()
        .set_file_name(&format!("{}.json", default_name))
        .add_filter("JSON", &["json"])
        .save_file(move |file_path| {
            if let Some(path) = file_path {
                let p = path.into_path().unwrap();
                match fs::write(&p, json_content) {
                    Ok(_) => tx.send(Ok(p.to_string_lossy().to_string())).unwrap(),
                    Err(e) => tx.send(Err(e.to_string())).unwrap(),
                }
            } else {
                tx.send(Ok("".to_string())).unwrap()
            }
        });
    rx.recv().unwrap()
}

#[tauri::command]
fn open_folder(path: String) -> Result<(), String> {
    #[cfg(target_os = "windows")]
    {
        let win_path = path.replace("/", "\\");
        std::process::Command::new("explorer")
            .arg(&win_path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    #[cfg(target_os = "linux")]
    {
        std::process::Command::new("xdg-open")
            .arg(&path)
            .spawn()
            .map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(Arc::new(Mutex::new(UpscaleState { process: None })))
        .invoke_handler(tauri::generate_handler![
            get_gpu_info,
            get_available_models,
            start_upscale,
            cancel_upscale,
            save_settings,
            load_settings,
            read_text_file,
            save_workflow,
            download_models,
            open_folder,
            setup_commands::check_env_exists,
            setup_commands::run_setup_wizard
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
