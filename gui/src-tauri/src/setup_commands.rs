use std::process::{Command, Stdio};
use std::io::{BufRead, BufReader, Read, Write};
use std::fs::{File, OpenOptions};
use std::path::PathBuf;
use tauri::{AppHandle, Emitter};

fn download_file(url: &str, dest: &std::path::Path, app: &AppHandle, name: &str) -> Result<(), String> {
    let mut existing_bytes = if dest.exists() {
        dest.metadata().map(|m| m.len()).unwrap_or(0)
    } else {
        0
    };

    let client = reqwest::blocking::Client::new();

    if let Ok(head_resp) = client.head(url).send() {
        if let Some(length) = head_resp.content_length() {
            if existing_bytes == length {
                let _ = app.emit("setup-log", format!("{} already downloaded, skipping.", name));
                return Ok(());
            } else if existing_bytes > length {
                existing_bytes = 0;
                let _ = std::fs::remove_file(dest);
            }
        }
    }

    let mut req = client.get(url);
    if existing_bytes > 0 {
        let _ = app.emit("setup-log", format!("Resuming {} from {}MB...", name, existing_bytes / (1024 * 1024)));
        req = req.header("Range", format!("bytes={}-", existing_bytes));
    } else {
        let _ = app.emit("setup-log", format!("Downloading {}...", name));
    }

    let mut response = req.send().map_err(|e| format!("Failed to connect to download {}: {}", name, e))?;

    let status = response.status();
    let (mut dest_file, mut downloaded) = if status == reqwest::StatusCode::PARTIAL_CONTENT {
        let f = OpenOptions::new().append(true).open(dest)
            .map_err(|e| format!("Failed to open {} for resume: {}", name, e))?;
        (f, existing_bytes)
    } else {
        if existing_bytes > 0 {
            let _ = app.emit("setup-log", format!("Server does not support resume, restarting {} download...", name));
        }
        let f = File::create(dest).map_err(|e| format!("Failed to create {}: {}", name, e))?;
        (f, 0u64)
    };

    let total_bytes = response.content_length().map(|cl| cl + downloaded).unwrap_or(0);
    let mut last_reported_mb = downloaded / (1024 * 1024);
    let mut buf = [0u8; 65536];

    loop {
        let n = response.read(&mut buf).map_err(|e| format!("Read error: {}", e))?;
        if n == 0 { break; }
        dest_file.write_all(&buf[..n]).map_err(|e| format!("Write error: {}", e))?;
        downloaded += n as u64;

        let current_mb = downloaded / (1024 * 1024);
        if current_mb != last_reported_mb {
            last_reported_mb = current_mb;
            let msg = if total_bytes > 0 {
                let total_mb = total_bytes / (1024 * 1024);
                let pct = downloaded * 100 / total_bytes;
                format!("  {} — {}MB / {}MB ({}%)", name, current_mb, total_mb, pct)
            } else {
                format!("  {} — {}MB downloaded", name, current_mb)
            };
            let _ = app.emit("setup-log", msg);
        }
    }

    let _ = app.emit("setup-log", format!("{} download complete.", name));
    Ok(())
}

fn extract_tar_gz(src: &std::path::Path, dest: &std::path::Path, app: &AppHandle, name: &str) -> Result<(), String> {
    let _ = app.emit("setup-log", format!("Extracting {}...", name));
    let tar_gz = File::open(src).map_err(|e| e.to_string())?;
    let tar = flate2::read::GzDecoder::new(tar_gz);
    let mut archive = tar::Archive::new(tar);
    archive.unpack(dest).map_err(|e| e.to_string())?;
    Ok(())
}

fn extract_zip(src: &std::path::Path, dest: &std::path::Path, app: &AppHandle, name: &str) -> Result<(), String> {
    let _ = app.emit("setup-log", format!("Extracting {}...", name));
    let file = File::open(src).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;
    archive.extract(dest).map_err(|e| e.to_string())?;
    Ok(())
}

fn get_base_dir() -> PathBuf {
    let mut root = std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    if root.ends_with("src-tauri") {
        root = root.parent().unwrap().to_path_buf();
    }
    if root.ends_with("gui") {
        root = root.parent().unwrap().to_path_buf();
    }
    root.join("backend").join("src")
}

/// Runs a command, streams stdout/stderr to the frontend, and returns true if it succeeded.
fn run_streamed(cmd: &mut Command, app: &AppHandle) -> bool {
    let mut child = match cmd.stdout(Stdio::piped()).stderr(Stdio::piped()).spawn() {
        Ok(c) => c,
        Err(e) => { let _ = app.emit("setup-log", format!("Failed to run command: {}", e)); return false; }
    };
    let h1 = child.stdout.take().map(|stdout| {
        let app_clone = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stdout).lines().flatten() {
                let _ = app_clone.emit("setup-log", line);
            }
        })
    });
    let h2 = child.stderr.take().map(|stderr| {
        let app_clone = app.clone();
        std::thread::spawn(move || {
            for line in BufReader::new(stderr).lines().flatten() {
                let _ = app_clone.emit("setup-log", line);
            }
        })
    });
    let status = child.wait().map(|s| s.success()).unwrap_or(false);
    if let Some(h) = h1 { let _ = h.join(); }
    if let Some(h) = h2 { let _ = h.join(); }
    status
}

/// Scan the uv python install dir to find the actual python3 binary.
fn find_python_in_dir(python_install_dir: &std::path::Path) -> Option<PathBuf> {
    let entries = std::fs::read_dir(python_install_dir).ok()?;
    for entry in entries.flatten() {
        let name = entry.file_name();
        let name = name.to_string_lossy();
        if name.starts_with("cpython-3.12") {
            let candidate = if cfg!(target_os = "windows") {
                entry.path().join("python.exe")
            } else {
                entry.path().join("bin").join("python3")
            };
            if candidate.exists() { return Some(candidate); }
        }
    }
    None
}

#[tauri::command]
pub fn check_env_exists() -> bool {
    let backend_src = get_base_dir();
    backend_src.join("python-runtime").join(".setup_complete").exists()
}

#[tauri::command]
pub fn run_setup_wizard(app: AppHandle, os_type: String, gpu_type: String) -> Result<(), String> {
    let backend_src = get_base_dir();

    std::thread::spawn(move || {
        let emit_log = |msg: &str| {
            let _ = app.emit("setup-log", msg);
        };

        let runtime_dir = backend_src.join("python-runtime");
        std::fs::create_dir_all(&runtime_dir).unwrap();

        // === Step 1: Download uv binary ===
        let uv_exe = runtime_dir.join(if cfg!(target_os = "windows") { "uv.exe" } else { "uv" });

        if uv_exe.exists() {
            emit_log("uv already installed, skipping.");
        } else {
            let uv_url = if cfg!(target_os = "windows") {
                "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
            } else {
                "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"
            };

            let uv_archive = runtime_dir.join(if cfg!(target_os = "windows") { "uv.zip" } else { "uv.tar.gz" });
            if let Err(e) = download_file(uv_url, &uv_archive, &app, "uv") {
                emit_log(&e); return;
            }

            let result = if cfg!(target_os = "windows") {
                extract_zip(&uv_archive, &runtime_dir, &app, "uv")
            } else {
                extract_tar_gz(&uv_archive, &runtime_dir, &app, "uv")
            };

            if let Err(e) = result {
                let _ = std::fs::remove_file(&uv_archive);
                emit_log(&format!("uv extraction failed: {}. Please restart.", e)); return;
            }

            let _ = std::fs::remove_file(&uv_archive);

            // uv tar.gz extracts into a subdirectory — move the binary to runtime_dir root
            let nested_uv = runtime_dir.join("uv-x86_64-unknown-linux-gnu").join("uv");
            if nested_uv.exists() {
                let _ = std::fs::rename(&nested_uv, &uv_exe);
                let _ = std::fs::remove_dir_all(runtime_dir.join("uv-x86_64-unknown-linux-gnu"));
            }

            #[cfg(target_family = "unix")]
            {
                use std::os::unix::fs::PermissionsExt;
                if let Ok(mut perms) = std::fs::metadata(&uv_exe).map(|m| m.permissions()) {
                    perms.set_mode(0o755);
                    let _ = std::fs::set_permissions(&uv_exe, perms);
                }
            }

            emit_log("uv installed.");
        }

        // === Step 2: Python runtime via uv ===
        let python_install_dir = runtime_dir.join("python");
        std::fs::create_dir_all(&python_install_dir).unwrap();

        let python_exe = if let Some(p) = find_python_in_dir(&python_install_dir) {
            emit_log(&format!("Python already installed at: {}", p.display()));
            p
        } else {
            emit_log("Installing Python 3.12 via uv...");
            run_streamed(
                Command::new(&uv_exe)
                    .args(&["python", "install", "3.12"])
                    .env("UV_PYTHON_INSTALL_DIR", &python_install_dir),
                &app,
            );
            match find_python_in_dir(&python_install_dir) {
                Some(p) => { emit_log(&format!("Python installed at: {}", p.display())); p }
                None => { emit_log("Python installation failed. Please restart."); return; }
            }
        };



        // === Step 4: PyTorch ===
        let backend_dir = backend_src.parent().unwrap(); // backend/

        if gpu_type == "AMD" && os_type == "Linux" {
            // Download AMD ROCm wheels with their real canonical filenames
            let rocm_wheels_dir = backend_dir.join("rocm-wheels");
            std::fs::create_dir_all(&rocm_wheels_dir).unwrap();

            let wheels = [
                ("https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.4/triton-3.6.0%2Brocm7.2.4.git4ed88892-cp312-cp312-linux_x86_64.whl",
                 "triton-3.6.0+rocm7.2.4.git4ed88892-cp312-cp312-linux_x86_64.whl",
                 "Triton (ROCm 7.2.4)"),
                ("https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.4/torch-2.10.0%2Brocm7.2.4.lw.git3d3aa833-cp312-cp312-linux_x86_64.whl",
                 "torch-2.10.0+rocm7.2.4.lw.git3d3aa833-cp312-cp312-linux_x86_64.whl",
                 "PyTorch 2.10 (ROCm 7.2.4)"),
                ("https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.4/torchvision-0.25.0%2Brocm7.2.4.git82df5f59-cp312-cp312-linux_x86_64.whl",
                 "torchvision-0.25.0+rocm7.2.4.git82df5f59-cp312-cp312-linux_x86_64.whl",
                 "TorchVision (ROCm 7.2.4)"),
            ];

            for (url, filename, label) in &wheels {
                let wheel_path = rocm_wheels_dir.join(filename);
                if let Err(e) = download_file(url, &wheel_path, &app, label) {
                    emit_log(&e); return;
                }
            }

            // Use `uv sync` from backend/ — picks up pyproject.toml which points uv.sources to our local wheels
            emit_log("Installing all dependencies via uv sync...");
            if !run_streamed(
                Command::new(&uv_exe)
                    .args(&["sync", "--python", &python_exe.to_string_lossy()])
                    .env("UV_PYTHON_INSTALL_DIR", &python_install_dir)
                    .current_dir(backend_dir),
                &app,
            ) {
                emit_log("Dependency installation failed. Please restart."); return;
            }
        } else {
            // NVIDIA (Linux/Windows)
            let cuda_wheels_dir = backend_dir.join("cuda-wheels");
            std::fs::create_dir_all(&cuda_wheels_dir).unwrap();

            let wheels = if os_type == "Windows" {
                vec![
                    ("https://download.pytorch.org/whl/cu121/torch-2.5.1%2Bcu121-cp312-cp312-win_amd64.whl",
                     "torch-2.5.1+cu121-cp312-cp312-win_amd64.whl",
                     "PyTorch 2.5.1 (CUDA 12.1)"),
                    ("https://download.pytorch.org/whl/cu121/torchvision-0.20.1%2Bcu121-cp312-cp312-win_amd64.whl",
                     "torchvision-0.20.1+cu121-cp312-cp312-win_amd64.whl",
                     "TorchVision 0.20.1 (CUDA 12.1)"),
                ]
            } else {
                vec![
                    ("https://download.pytorch.org/whl/cu121/torch-2.5.1%2Bcu121-cp312-cp312-linux_x86_64.whl",
                     "torch-2.5.1+cu121-cp312-cp312-linux_x86_64.whl",
                     "PyTorch 2.5.1 (CUDA 12.1)"),
                    ("https://download.pytorch.org/whl/cu121/torchvision-0.20.1%2Bcu121-cp312-cp312-linux_x86_64.whl",
                     "torchvision-0.20.1+cu121-cp312-cp312-linux_x86_64.whl",
                     "TorchVision 0.20.1 (CUDA 12.1)"),
                ]
            };

            for (url, filename, label) in &wheels {
                let wheel_path = cuda_wheels_dir.join(filename);
                if let Err(e) = download_file(url, &wheel_path, &app, label) {
                    emit_log(&e); return;
                }
            }

            let mut install_args = vec![
                "pip".to_string(), "install".to_string(), "--no-config".to_string(), "--python".to_string(),
                python_exe.to_string_lossy().to_string(), "--break-system-packages".to_string(),
            ];
            for (_, filename, _) in &wheels {
                install_args.push(cuda_wheels_dir.join(filename).to_string_lossy().to_string());
            }

            emit_log("Installing PyTorch (CUDA) via uv...");
            if !run_streamed(
                Command::new(&uv_exe)
                    .args(&install_args)
                    .current_dir(backend_dir),
                &app,
            ) {
                emit_log("PyTorch installation failed. Please restart."); return;
            }

            // Install remaining deps from pyproject.toml (excluding torch/torchvision which use uv.sources on AMD only)
            emit_log("Installing remaining dependencies via uv pip...");
            if !run_streamed(
                Command::new(&uv_exe)
                    .args(&["pip", "install", "--no-config", "--no-sources", "--python", &python_exe.to_string_lossy(), "--break-system-packages", "."])
                    .current_dir(backend_dir),
                &app,
            ) {
                emit_log("Dependency installation failed. Please restart."); return;
            }
        }

        // === Optional Warning for AMD Linux ===
        if gpu_type == "AMD" && os_type == "Linux" {
            emit_log("\n=======================================================");
            emit_log("               IMPORTANT: AMD GPU PERFORMANCE                 ");
            emit_log("=======================================================");
            emit_log("If generation is very slow, your GPU memory clock (MCLK)");
            emit_log("might be stuck at 96MHz due to a known AMD Linux bug.");
            emit_log("");
            emit_log("To fix this, open your terminal and run:");
            emit_log("echo \"high\" | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level");
            emit_log("(If you have an integrated GPU, you might need card1 instead of card0)");
            emit_log("=======================================================\n");
        }

        // === Cleanup Temporary Files ===
        let rocm_wheels_dir = backend_dir.join("rocm-wheels");
        if rocm_wheels_dir.exists() {
            let _ = std::fs::remove_dir_all(&rocm_wheels_dir);
        }
        let cuda_wheels_dir = backend_dir.join("cuda-wheels");
        if cuda_wheels_dir.exists() {
            let _ = std::fs::remove_dir_all(&cuda_wheels_dir);
        }
        emit_log("Cleaned up temporary installation files.");

        // Mark setup as fully complete — only reached if ALL steps succeeded
        let _ = std::fs::write(runtime_dir.join(".setup_complete"), "ok");
        emit_log("SETUP_COMPLETE");
    });

    Ok(())
}
