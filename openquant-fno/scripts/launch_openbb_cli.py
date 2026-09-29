"""
OpenQuant-FNO: OpenBB Platform API & CLI Interactive Launcher
============================================================
Automates spawning the OpenBB Platform REST API backend server on port 6900
via subprocess and attaches an interactive research terminal session.
"""

import os
import sys
import time
import socket
import subprocess
import shutil
import urllib.request
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config

API_HOST = config.OPENBB_API_HOST
API_PORT = config.OPENBB_API_PORT


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a TCP port is currently open and accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


def start_openbb_api_server() -> subprocess.Popen:
    """Spins up the OpenBB REST API server in a background daemon subprocess."""
    print(f"[*] Checking OpenBB REST API server status on {API_HOST}:{API_PORT}...")
    
    if is_port_in_use(API_PORT, API_HOST):
        print(f"[✓] OpenBB API server is ALREADY ACTIVE and listening on port {API_PORT}.")
        return None

    # Determine command to launch OpenBB API
    # OpenBB Platform provides `openbb-api` or `uvicorn openbb_platform.api:app`
    api_cmd = None
    if shutil.which("openbb-api"):
        api_cmd = ["openbb-api", "--host", API_HOST, "--port", str(API_PORT)]
    elif shutil.which("uvicorn"):
        api_cmd = ["uvicorn", "openbb_platform.api:app", "--host", API_HOST, "--port", str(API_PORT)]
    else:
        # Fallback to python module execution
        api_cmd = [sys.executable, "-m", "openbb_platform.api", "--host", API_HOST, "--port", str(API_PORT)]

    print(f"[*] Launching background OpenBB API Server: {' '.join(api_cmd)}")
    try:
        proc = subprocess.Popen(
            api_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True
        )
        # Wait up to 5 seconds for the socket to bind
        for _ in range(10):
            time.sleep(0.5)
            if is_port_in_use(API_PORT, API_HOST):
                print(f"[✓] OpenBB REST API backend successfully initialized on http://{API_HOST}:{API_PORT}")
                return proc

        print(f"[!] OpenBB server starting (socket initializing)... Proceeding.")
        return proc
    except Exception as exc:
        print(f"[!] Warning: Could not spawn openbb-api directly ({exc}).")
        print("    You can install it via: pip install openbb[all] openbb-cli")
        return None


def launch_openbb_cli():
    """Opens interactive OpenBB CLI terminal interface."""
    print("\n" + "=" * 70)
    print("      OPENQUANT-FNO: OPENBB INTERACTIVE RESEARCH TERMINAL")
    print("=" * 70)
    print(f"Connected to API Server: http://{API_HOST}:{API_PORT}")
    print("Launching OpenBB CLI interface...\n")

    cli_cmd = shutil.which("openbb") or shutil.which("openbb-cli")
    if cli_cmd:
        try:
            subprocess.run([cli_cmd], check=False)
        except KeyboardInterrupt:
            print("\nExiting OpenBB CLI.")
    else:
        print("[!] OpenBB CLI binary ('openbb' or 'openbb-cli') was not detected in PATH.")
        print("    To install the full quantitative research station:")
        print("      pip install openbb openbb-cli")
        print("\n    Launching Python-based OpenBB SDK REPL instead:")
        try:
            subprocess.run([
                sys.executable, "-i", "-c",
                "print('=== OpenBB Platform SDK Interactive Mode ==='); "
                "from quant_suite.openbb_service import OpenBBMarketService; "
                "service = OpenBBMarketService(); "
                "print('Market Service available as `service`. Try: service.get_index_spot(\"NIFTY\")');"
            ])
        except KeyboardInterrupt:
            pass


def main():
    api_proc = start_openbb_api_server()
    try:
        launch_openbb_cli()
    finally:
        if api_proc:
            print("[*] Terminating background OpenBB API server process...")
            api_proc.terminate()
            print("[✓] OpenBB API server terminated.")


if __name__ == "__main__":
    main()
