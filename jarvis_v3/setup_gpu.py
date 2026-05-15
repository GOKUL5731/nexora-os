"""
JARVIS GPU setup script - installs PyTorch CUDA + faster-whisper + OCR deps.
Run ONCE before first launch: python setup_gpu.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

CUDA_WHEEL_OPTIONS = [
    ("cu128", "CUDA 12.8"),
    ("cu126", "CUDA 12.6"),
    ("cu118", "CUDA 11.8"),
]
SUPPORTED_PYTHON_MIN = (3, 10)
SUPPORTED_PYTHON_MAX = (3, 14)


def run(cmd: str, label: str = "") -> bool:
    print(f"\n>> {label or cmd}")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"  [WARN] Command returned {result.returncode}")
    return result.returncode == 0


def python_supported() -> bool:
    version = (sys.version_info.major, sys.version_info.minor)
    return SUPPORTED_PYTHON_MIN <= version <= SUPPORTED_PYTHON_MAX


def probe_torch(py: str) -> dict:
    probe = """
import json
status = {
    "import_ok": False,
    "torch_version": None,
    "torch_cuda_version": None,
    "cuda_available": False,
    "gpu_name": None,
    "error": None,
}
try:
    import torch
    status["import_ok"] = True
    status["torch_version"] = torch.__version__
    status["torch_cuda_version"] = torch.version.cuda
    status["cuda_available"] = bool(torch.cuda.is_available())
    if status["cuda_available"]:
        status["gpu_name"] = torch.cuda.get_device_name(0)
except Exception as exc:
    status["error"] = str(exc)
print(json.dumps(status))
""".strip()
    result = subprocess.run([py, "-c", probe], capture_output=True, text=True)
    if result.returncode != 0:
        return {
            "import_ok": False,
            "torch_version": None,
            "torch_cuda_version": None,
            "cuda_available": False,
            "gpu_name": None,
            "error": (result.stderr or result.stdout).strip() or "probe failed",
        }
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {
            "import_ok": False,
            "torch_version": None,
            "torch_cuda_version": None,
            "cuda_available": False,
            "gpu_name": None,
            "error": result.stdout.strip() or result.stderr.strip() or "invalid probe output",
        }


def install_torch(py: str) -> tuple[bool, str | None]:
    for index_name, label in CUDA_WHEEL_OPTIONS:
        url = f"https://download.pytorch.org/whl/{index_name}"
        ok = run(
            f'"{py}" -m pip install --upgrade torch torchvision torchaudio '
            f'--index-url {url} --quiet',
            f"Installing PyTorch {label}",
        )
        if not ok:
            continue

        status = probe_torch(py)
        if status["import_ok"] and status["torch_cuda_version"]:
            print(
                f"  [OK] torch {status['torch_version']} "
                f"(runtime CUDA {status['torch_cuda_version']})"
            )
            return True, label

        print("  [WARN] PyTorch installed, but the CUDA build was not detected.")

    return False, None


def update_config(gpu_ready: bool) -> None:
    cfg_path = pathlib.Path("config/config.json")
    if not cfg_path.exists():
        print("[WARN] config/config.json not found; skipping config update")
        return

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        cfg.setdefault("voice", {})
        cfg.setdefault("vision", {})

        if gpu_ready:
            cfg["voice"]["stt_device"] = "cuda"
            cfg["voice"]["stt_compute"] = "float16"
            cfg["vision"]["gpu"] = True
            mode = "GPU"
        else:
            cfg["voice"]["stt_device"] = "cpu"
            cfg["voice"]["stt_compute"] = "int8"
            cfg["vision"]["gpu"] = False
            mode = "CPU fallback"

        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        print(f"[OK] config.json updated for {mode} mode")
    except Exception as exc:
        print(f"[WARN] Config update: {exc}")


def main() -> int:
    print("=" * 55)
    print("  JARVIS GPU Setup - RTX 4050 / Windows")
    print("=" * 55)
    print(f"Python: {sys.version.split()[0]}")

    if not python_supported():
        print(
            "[WARN] PyTorch on Windows currently supports Python 3.10-3.14. "
            "Use one of those versions for GPU setup."
        )
        return 1

    py = sys.executable

    # 1. PyTorch CUDA wheels
    torch_ok, torch_label = install_torch(py)

    # 2. faster-whisper (GPU Whisper when torch CUDA is available)
    run(f'"{py}" -m pip install faster-whisper --quiet', "Installing faster-whisper")

    # 3. NVIDIA stats bindings
    run(f'"{py}" -m pip uninstall -y pynvml', "Removing deprecated pynvml package")
    run(f'"{py}" -m pip install --upgrade nvidia-ml-py --quiet', "Installing NVIDIA NVML bindings")

    # 4. Piper TTS
    run(f'"{py}" -m pip install piper-tts --quiet', "Installing Piper TTS")

    # 5. Vision stack
    vision_packages = "opencv-python Pillow"
    if torch_ok:
        run(
            f'"{py}" -m pip install easyocr {vision_packages} --quiet',
            "Installing vision stack",
        )
    else:
        run(
            f'"{py}" -m pip install {vision_packages} --quiet',
            "Installing basic vision dependencies",
        )
        print("  [WARN] Skipped easyocr because PyTorch CUDA did not install cleanly.")

    # 6. keyboard (hotkey)
    run(f'"{py}" -m pip install keyboard --quiet', "Installing keyboard hotkey")

    # 7. Verify CUDA
    print("\n>> Verifying CUDA...")
    status = probe_torch(py)
    if status["import_ok"]:
        print(f"torch: {status['torch_version']}")
        print(f"torch CUDA runtime: {status['torch_cuda_version'] or 'None'}")
        print(f"CUDA available: {status['cuda_available']}")
        print(f"GPU: {status['gpu_name'] or 'N/A'}")
    else:
        print(f"torch import failed: {status['error']}")

    gpu_ready = bool(status["import_ok"] and status["cuda_available"])

    # 8. Update config to match the verified runtime
    update_config(gpu_ready)

    print("\n" + "=" * 55)
    if gpu_ready:
        print("  GPU setup complete!")
        if torch_label:
            print(f"  PyTorch wheel: {torch_label}")
        print("  Launch: python -X utf8 jarvis_gui.py")
        print("=" * 55)
        return 0

    print("  GPU setup did not complete.")
    print("  PyTorch was not able to access CUDA on this machine.")
    print("  Launch is still possible, but JARVIS will use CPU fallback mode.")
    print("=" * 55)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
