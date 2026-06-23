# MangaJaNai Converter — Linux Edition

AMD ROCm and NVIDIA CUDA GPU-accelerated manga upscaling for Debian/Ubuntu Linux.  
Original project: [MangaJaNaiConverterGui](https://github.com/the-database/MangaJaNaiConverterGui)

## Features

- **ROCm and CUDA** — detects and uses AMD GPUs (RX 6000/7000 series) via ROCm/HIP, or NVIDIA GPUs via CUDA
- **4× upscaling** — ESRGAN-based models for grayscale (MangaJaNai) and color (IllustrationJaNai) pages
- **CBZ/CBR archive support** — reads manga chapters, upscales images, repacks as CBZ
- **Configurable chains** — auto-selects model and settings based on image resolution and type
- **Auto-levels** — contrast enhancement for grayscale pages, normalization for color
- **Live progress** — tile-level progress, per-image timing, colored console output
- **Responsive cancel** — non-blocking subprocess reads, SIGTERM cleanup
- **Model caching** — keeps grayscale and color models concurrently in VRAM to avoid reload cost
- **Standalone** — self-contained project, no external dependencies beyond ROCm and system libs

## Requirements

| Component | Version |
|-----------|---------|
| OS | Linux Mint 22.x / Ubuntu 24.04 |
| GPU | AMD RDNA2+ (RX 6000/7000 series) or NVIDIA RTX 2000+ |
| Drivers | ROCm 7.2.4+ **or** NVIDIA 535+ with CUDA 12.1+ |
| Kernel | 6.8+ (HWE kernel recommended) |
| Python | 3.12 |
| PyTorch | 2.10.0+rocm7.2.4 **or** 2.5.1+cu121 |
| System deps | libvips, libxcb-cursor0 |
| Python packages | spandrel, chainner-ext, pyvips, opencv-python, pillow, numpy, psutil, PyQt6 |

## Quick Start

### Prerequisites

```bash
# Verify GPU driver is loaded
lsmod | grep amdgpu      # should show amdgpu
ls /dev/kfd               # must exist

# Verify ROCm is installed
rocminfo                   # should list your GPU
```

### Install ROCm 7.2.4 (if not already installed)

```bash
cd ~
wget https://repo.radeon.com/amdgpu-install/7.2.4/ubuntu/noble/amdgpu-install_7.2.4.70204-1_all.deb
sudo apt install -y ./amdgpu-install_7.2.4.70204-1_all.deb
sudo apt update && sudo apt install -y rocm
sudo usermod -aG render,video $USER
# Reboot, then verify: rocminfo
```

### Setup Python Environment

Choose your GPU vendor:

<details open>
<summary><b>AMD ROCm</b></summary>

The project uses [uv](https://github.com/astral-sh/uv) for fast, reproducible Python environments.

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Install system dependencies
sudo apt install -y libvips libxcb-cursor0

# Create and populate venv
cd backend/src
uv venv --python 3.12
source .venv/bin/activate

# Download PyTorch ROCm wheels (~1.8 GB)
mkdir -p backend/rocm-wheels && cd backend/rocm-wheels
wget https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.4/triton-3.6.0%2Brocm7.2.4.git4ed88892-cp312-cp312-linux_x86_64.whl
wget https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.4/torch-2.10.0%2Brocm7.2.4.lw.git3d3aa833-cp312-cp312-linux_x86_64.whl
wget https://repo.radeon.com/rocm/manylinux/rocm-rel-7.2.4/torchvision-0.25.0%2Brocm7.2.4.git82df5f59-cp312-cp312-linux_x86_64.whl
cd ../src && source .venv/bin/activate

# Install PyTorch ROCm
uv pip install ../rocm-wheels/triton-3.6.0+rocm7.2.4.git4ed88892-cp312-cp312-linux_x86_64.whl
uv pip install ../rocm-wheels/torch-2.10.0+rocm7.2.4.lw.git3d3aa833-cp312-cp312-linux_x86_64.whl
uv pip install ../rocm-wheels/torchvision-0.25.0+rocm7.2.4.git82df5f59-cp312-cp312-linux_x86_64.whl

# Install remaining dependencies
uv pip install chainner_ext opencv-python pyvips rarfile spandrel spandrel_extra_arches \
    sanic pillow packaging pynvml psutil PyQt6

# Verify GPU is detected by PyTorch
python3 -c "import torch; print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

A `pyproject.toml` with `[tool.uv.sources]` is provided — after placing the wheels in `backend/rocm-wheels/`, a fresh environment can be recreated with `uv sync`.

</details>

<details>
<summary><b>NVIDIA CUDA</b></summary>

```bash
# Install NVIDIA drivers and CUDA (if not already installed)
sudo apt install -y nvidia-driver-535 nvidia-cuda-toolkit

# Install system dependencies
sudo apt install -y libvips libxcb-cursor0

# Create and populate venv
cd backend/src
uv venv --python 3.12
source .venv/bin/activate

# Install PyTorch CUDA
uv pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Install remaining dependencies
uv pip install chainner_ext opencv-python pyvips rarfile spandrel spandrel_extra_arches \
    sanic pillow packaging pynvml psutil PyQt6

# Verify GPU is detected by PyTorch
python3 -c "import torch; print('GPU:', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

</details>

### Download Upscale Models

All models (~1 GB total) at **[github.com/the-database/MangaJaNai/releases](https://github.com/the-database/MangaJaNai/releases)**.

```bash
mkdir -p backend/models

# v1.0.0 — MangaJaNai ESRGAN (.pth) + V1 IllustrationJaNai
wget -P /tmp https://github.com/the-database/MangaJaNai/releases/download/1.0.0/MangaJaNai_V1_ModelsOnly.zip
wget -P /tmp https://github.com/the-database/MangaJaNai/releases/download/1.0.0/IllustrationJaNai_V1_ModelsOnly.zip

# v2.0.0 — IllustrationJaNai V2 (.safetensors)
wget -P /tmp https://github.com/the-database/MangaJaNai/releases/download/2.0.0/4x_IllustrationJaNai_V2standard_ModelsOnly.zip
wget -P /tmp https://github.com/the-database/MangaJaNai/releases/download/2.0.0/IllustrationJaNai_V2_DeJPEG_ModelsOnly.zip

# v3.0.0 — IllustrationJaNai V3 (.safetensors)
wget -P /tmp https://github.com/the-database/MangaJaNai/releases/download/3.0.0/IllustrationJaNai_V3denoise.zip
wget -P /tmp https://github.com/the-database/MangaJaNai/releases/download/3.0.0/IllustrationJaNai_V3detail.zip

# Extract all to backend/models/
for zip in /tmp/*.zip; do unzip -o "$zip" -d backend/models/; done
rm /tmp/*.zip
```

### Launch

```bash
bash run.sh
```

## Project Structure

```
├── backend/
│   ├── models/              # ESRGAN model files (~1 GB, gitignored)
│   ├── rocm-wheels/         # ROCm PyTorch wheels (~1.8 GB, gitignored)
│   ├── src/
│   │   ├── .venv/           # Python venv (gitignored)
│   │   ├── run_upscale.py   # CLI upscaler entry point
│   │   ├── nodes/           # Inference, tiling, image processing
│   │   └── packages/        # PyTorch backend, model loading
│   └── pyproject.toml       # uv project configuration
├── current/                 # Runtime directory
│   ├── appstate2.json       # User settings (gitignored)
│   └── backend/
│       ├── src → ../../backend/src      # Symlink to source code
│       └── models → ../../backend/models # Symlink to models
├── gui/                     # PyQt6 GUI
│   ├── launch_gui.py
│   └── src/main_window.py
├── run.sh                   # One-click launch
└── README.md
```

## Performance

Tested on AMD Radeon RX 6700 XT (12 GB), ROCm 7.2.4, PyTorch 2.10:

| Image type | Resolution | Tile size | Tiles | Time |
|-----------|-----------|-----------|-------|------|
| Single page (grayscale) | ~1644×2367 | 256px | 70 | ~10.5 s |
| Single page (grayscale, landscape) | ~1332×1920 | 256px | 40 | ~7.3 s |
| Double page (grayscale) | ~2688×1920 | 256px | 88 | ~14.7 s |
| Color page | ~1650×2379 | 256px | 50 | ~11.0 s |
| Color page (IllustrationJaNai) | ~1332×1920 | 256px | 50 | ~13.5 s |
| **17-page chapter (mixed)** | — | — | — | **~3 min** |
| **20-page chapter (mixed)** | — | — | — | **~3.1 min** |

GPU: 99% utilization, 200-205 W, MCLK 1000 MHz (16 Gbps effective — vBIOS limit for RDNA2 compute).

## Differences from MangaJaNaiConverterGui

This is a Linux-native fork. Key changes:

| Area | Upstream (Windows) | This fork (Linux) |
|------|-------------------|-------------------|
| **GUI** | Avalonia/C# | PyQt6/Python |
| **GPU backend** | NVIDIA CUDA + DirectML | AMD ROCm via HIP + NVIDIA CUDA |
| **Model loading** | Unloads previous model on chain switch | **Keeps all models in VRAM** concurrently |
| **Cancel** | Blocking process reads | Non-blocking `select()` + SIGTERM cleanup |
| **VRAM cleanup** | — | Clears `loaded_models` + GC + `empty_cache` |
| **ROCm env** | — | `HSA_OVERRIDE_GFX_VERSION`, `HIP_VISIBLE_DEVICES`, `HSA_ENABLE_SDMA` |
| **Allocator** | Default | `expandable_segments:True` for reduced fragmentation |
| **channels_last** | Enabled | **Disabled** — NHWC is slower on AMD |
| **Package manager** | Built-in installer | `uv` with local ROCm wheel cache |
| **Project structure** | Monolithic portable | Standalone with `current/` symlinks |

The backend inference engine (`spandrel` + `chaiNNer` PyTorch nodes) is shared with upstream. The tile-based upscaling pipeline (read → preprocess → upscale → encode → zip) is identical.

## Troubleshooting

**GPU not detected / falls back to CPU:**
```bash
rocminfo | grep "Marketing Name"
groups | grep render
sudo chmod 666 /dev/kfd
export HSA_OVERRIDE_GFX_VERSION=10.3.0
python3 -c "import torch; print(torch.cuda.is_available())"
```

**Slow performance / low power draw (MCLK stuck at 96Mhz):**
A known AMD ROCm bug on Linux (especially with RX 6000 series like the 6700 XT) can cause the GPU Memory Clock (MCLK) to get permanently stuck at 96MHz instead of boosting to 2000MHz+ during AI workloads. This starves PyTorch of memory bandwidth, leading to 99% GPU utilization but extremely low power draw (e.g. 45W instead of 200W) and minutes-long generation times.

To fix this, force the GPU into its high-performance power state before upscaling:
```bash
echo "high" | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level
```
*(Note: If you have an integrated graphics chip, your discrete GPU might be `card1` instead of `card0`. Check `rocm-smi` to see which device is your discrete GPU, and change the command accordingly, e.g., `card1`).*

Alternatively, disabling **FreeSync** or lowering your monitor refresh rate to 60Hz/120Hz can also prevent this bug.

**VRAM not cleared after cancel/kill:**
ROCm does not auto-free orphaned GPU allocations from killed processes. VRAM clears on reboot. `sudo rocm-smi --gpureset` may freeze the desktop on some configurations — use with caution.

**GUI won't launch (xcb plugin error):**
```bash
sudo apt install -y libxcb-cursor0
```

**PyTorch wheels cleaned from /tmp:**
The setup instructions save wheels to `backend/rocm-wheels/` inside the project (gitignored). Move them there after downloading.

## License

Community fork optimized for Linux/ROCm. See the [original project](https://github.com/the-database/MangaJaNaiConverterGui) for license details.
