#!/usr/bin/env python3
"""
Quick start script for AI Resume Analyzer Backend
Installs dependencies and starts the Flask server
"""

import subprocess
import sys
import os
from pathlib import Path

def run_command(cmd, description=""):
    """Run a command and return success status"""
    if description:
        print("[*] " + description + "...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print("[ERROR] " + (e.stderr or e.stdout))
        return False

def main():
    backend_dir = Path(__file__).parent
    os.chdir(backend_dir)
    
    print("\n" + "="*60)
    print("[STARTUP] AI Resume Analyzer - Backend")
    print("="*60)
    
    # Step 1: Check Python version
    print("[OK] Python " + sys.version.split()[0] + " detected")
    
    # Step 2: Upgrade pip
    print("[*] Upgrading pip...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    
    # Step 3: Install requirements
    requirements_file = backend_dir / "requirements.txt"
    if requirements_file.exists():
        print("[*] Installing dependencies from " + requirements_file.name + "...")
        if not run_command(sys.executable + " -m pip install -r requirements.txt"):
            print("[WARNING] Some dependencies failed to install, continuing anyway...")
    else:
        print("[WARNING] " + str(requirements_file) + " not found, skipping dependency installation")
    
    # Step 4: Check .env file
    env_file = backend_dir / ".env"
    if env_file.exists():
        print("[OK] .env file found")
    else:
        print("[WARNING] .env file not found. Creating template...")
        example_file = backend_dir / ".env.example"
        template = "GEMINI_API_KEY=your_api_key_here\n"
        if example_file.exists():
            template = example_file.read_text(encoding="utf-8")
        env_file.write_text(template, encoding="utf-8")
        print("    Created " + str(env_file))
        print("    [IMPORTANT] Add your Gemini API key to " + str(env_file))
    
    # Step 5: Check if app.py exists
    app_file = backend_dir / "app.py"
    if not app_file.exists():
        print("[ERROR] app.py not found in " + str(backend_dir))
        sys.exit(1)
    
    # Step 6: Start the server
    print("\n" + "="*60)
    print("[STARTUP] Starting Flask Server...")
    print("="*60)
    print("\n[URL] Backend: http://127.0.0.1:5000")
    print("[URL] Health: http://127.0.0.1:5000/health")
    print("\n[TIP] Open index.html in your browser while this server is running")
    print("[TIP] Press Ctrl+C to stop the server\n")
    
    try:
        # Run the Flask app
        subprocess.run([sys.executable, "app.py"], check=False)
    except KeyboardInterrupt:
        print("\n[INFO] Server stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main()
