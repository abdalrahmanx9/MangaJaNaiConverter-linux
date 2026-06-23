# MangaJaNai Converter

AMD ROCm and NVIDIA CUDA GPU-accelerated manga upscaling for Windows and Linux.
Original project: [MangaJaNaiConverterGui](https://github.com/the-database/MangaJaNaiConverterGui)

## Features

- **Cross-Platform** — works on Windows 10/11 and Linux
- **ROCm and CUDA** — detects and uses AMD GPUs (RX 6000/7000 series) via ROCm/HIP (Linux), or NVIDIA GPUs via CUDA (Windows & Linux)
- **4× upscaling** — ESRGAN-based models for grayscale (MangaJaNai) and color (IllustrationJaNai) pages
- **CBZ/CBR archive support** — reads manga chapters, upscales images, repacks as CBZ
- **Configurable chains** — auto-selects model and settings based on image resolution and type
- **Model caching** — keeps grayscale and color models concurrently in VRAM to avoid reload cost
- **Standalone** — self-contained project with an automated Setup Wizard

## Requirements

| Component | Windows | Linux |
|-----------|---------|-------|
| OS | Windows 10 / 11 | Linux Mint 22.x / Ubuntu 24.04 |
| GPU | NVIDIA RTX 2000+ | AMD RDNA2+ (RX 6000+) or NVIDIA RTX 2000+ |
| Drivers | NVIDIA Driver with CUDA 12.1+ | ROCm 7.2.4+ **or** NVIDIA 535+ with CUDA 12.1+ |
| System deps | None | libvips, libxcb-cursor0, curl, wget |

*Note: Python, PyTorch, and `uv` are automatically installed by the built-in Setup Wizard.*

## Quick Start

1. Download the latest release from [Releases](https://github.com/abdalrahmanx9/MangaJaNaiConverter-linux/releases) for your platform.
2. Extract the archive.
3. Run the executable (`MangaJaNaiConverter` on Linux, `MangaJaNaiConverter.exe` on Windows).

On first launch, the Setup Wizard will automatically download Python, PyTorch, and all required dependencies.

## Building from Source

**Prerequisites:** [Node.js](https://nodejs.org/) 20+ and [Rust](https://rustup.rs/).

**Linux** also needs system libraries for Tauri:
```bash
sudo apt install -y libwebkit2gtk-4.1-dev build-essential file libssl-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev
```

**Windows** needs [Visual Studio C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).

**Build steps:**
```bash
cd gui
npm ci
npm run tauri dev     # development with hot-reload
npm run tauri build   # production binary in target/release/
```

## Project Structure

```text
├── backend/
│   ├── models/              # ESRGAN model files (downloaded via GUI)
│   ├── src/
│   │   ├── python-runtime/  # Isolated Python environment created by Setup Wizard
│   │   ├── run_upscale.py   # CLI upscaler entry point
│   │   ├── nodes/           # Inference, tiling, image processing
│   │   └── pyproject.toml   # uv project configuration
├── gui/                     # Tauri GUI (TypeScript + Vite)
│   ├── src/                 # Frontend code
│   └── src-tauri/           # Rust backend bridging Python script & GUI
└── README.md
```

## Troubleshooting

**Linux: Slow performance / low power draw (MCLK stuck at 96Mhz) on AMD:**
A known AMD ROCm bug on Linux can cause the GPU Memory Clock (MCLK) to get permanently stuck at 96MHz instead of boosting during AI workloads.
To fix this, force the GPU into its high-performance power state:
```bash
echo "high" | sudo tee /sys/class/drm/card0/device/power_dpm_force_performance_level
```
*(Change `card0` to `card1` if you have an integrated graphics chip).*

## License

Community fork optimized for Tauri and cross-platform support. See the [original project](https://github.com/the-database/MangaJaNaiConverterGui) for license details.
