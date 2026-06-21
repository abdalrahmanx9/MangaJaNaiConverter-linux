import subprocess
import os
from typing import Optional, List, Tuple


class GPUInfo:
    name: str = ""
    vram_mb: int = 0
    available: bool = False
    driver_loaded: bool = False
    rocmsmi_available: bool = False


def get_gpu_info() -> GPUInfo:
    """Get GPU information on Linux with ROCm support."""
    gpu = GPUInfo()

    try:
        result = subprocess.run(
            ["rocminfo"], capture_output=True, text=True, timeout=10
        )
        gpu.rocmsmi_available = result.returncode == 0

        if gpu.rocmsmi_available:
            output = result.stdout

            if "AMD Ryzen" in output or "gfx" in output:
                gpu.driver_loaded = True

            lines = output.split("\n")
            for i, line in enumerate(lines):
                if "Marketing Name" in line or "Name:" in line:
                    if "Radeon RX" in line:
                        gpu.name = line.split("Radeon RX")[-1].strip()
                        if "RX" in line:
                            gpu.name = "AMD " + line.split("Radeon ")[-1].strip()
                    elif "AMD Ryzen" not in line and "Processor" not in line:
                        if "gfx10" in line or "gfx11" in line or "gfx12" in line:
                            pass

                if "Max Clock" in line:
                    try:
                        freq = int(line.split("(")[1].split("MHz")[0])
                    except:
                        pass

                if "Size:" in line and "KB" in line:
                    try:
                        size_kb = int(line.split("Size:")[1].split("KB")[0].strip())
                        if size_kb > 1000000:
                            gpu.vram_mb = size_kb // 1024
                    except:
                        pass

    except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as e:
        pass

    try:
        result = subprocess.run(
            ["rocm-smi", "--showtopo"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and "GPU" in result.stdout:
            gpu.available = True
    except:
        pass

    try:
        result = subprocess.run(["lsmod"], capture_output=True, text=True, timeout=5)
        if "amdgpu" in result.stdout:
            gpu.driver_loaded = True
    except:
        pass

    if not gpu.name and gpu.available:
        gpu.name = "AMD GPU"

    return gpu


def get_available_models(models_dir: str) -> List[str]:
    """Get list of available model files."""
    models = []

    if not os.path.exists(models_dir):
        return models

    for f in os.listdir(models_dir):
        if f.endswith((".pth", ".safetensors")):
            models.append(f)

    return sorted(models)


def check_rocminfo() -> Tuple[bool, str]:
    """Check if ROCm is working properly."""
    try:
        result = subprocess.run(
            ["sudo", "rocminfo"], capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            if (
                "gfx10" in result.stdout
                or "gfx11" in result.stdout
                or "gfx12" in result.stdout
            ):
                return True, "ROCm working"
            return True, "ROCm installed but no GPU detected"
        return False, "ROCm not working"
    except Exception as e:
        return False, str(e)


def get_gpu_usage() -> Optional[dict]:
    """Get current GPU usage stats."""
    try:
        result = subprocess.run(
            ["rocm-smi", "--json", "-u"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)
            if data:
                return data[0]
    except:
        pass

    return None
