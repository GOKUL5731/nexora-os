"""
NEXORA One-Click Launcher
Starts NEXORA with all features enabled in a desktop application
"""
import subprocess
import sys
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 7474

def kill_port_process(port: int) -> None:
    """Kill any process running on the given port on Windows."""
    try:
        output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True, text=True)
        for line in output.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                match = re.search(r'LISTENING\s+(\d+)', line)
                if match:
                    pid = match.group(1)
                    print(f"[*] Killing existing NEXORA process (PID {pid}) on port {port}...")
                    subprocess.run(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        pass  # Port not in use or findstr failed

def main() -> int:
    """Launch NEXORA desktop application and services"""
    print("Starting NEXORA OS...")
    print("=" * 50)
    
    # 1. Ensure no existing NEXORA instance is hogging the port
    kill_port_process(PORT)
    
    # 2. Start the updated NEXORA LLM (Ollama) in the background
    print("[OK] Starting NEXORA LLM (Ollama) in background...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        time.sleep(1) # Give it a moment to initialize
    except FileNotFoundError:
        print("[!] Ollama not found. The LLM will remain offline. Please install Ollama or make sure it's in your PATH.")

    # 3. Start Desktop App (this opens the UI and spins up the backend)
    print("[OK] Launching NEXORA Desktop Command Center...")
    try:
        desktop_process = subprocess.Popen(
            [sys.executable, str(ROOT / "nexora_os" / "desktop_app.py")],
            cwd=ROOT,
        )
        desktop_process.wait()
    except KeyboardInterrupt:
        print("\nStopping NEXORA...")
        desktop_process.terminate()
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
