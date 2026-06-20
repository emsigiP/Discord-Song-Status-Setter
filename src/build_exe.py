import subprocess
import os
import sys

def build():
    # Make sure we are in the root directory of the project
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(cwd)

    # Check and install PyInstaller
    try:
        import PyInstaller
        print("OK: PyInstaller is already installed")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    # Verify app_icon exists
    icon_path = os.path.join("src", "app_icon.ico")
    if not os.path.exists(icon_path):
        raise FileNotFoundError(f"Icon not found at {icon_path}! Please generate or place the icon first.")

    # Build arguments
    cmd = [
        "pyinstaller",
        "--console",            # Use standard console to avoid antivirus false positives (hidden programmatically on startup)
        "--onefile",            # Compile to single executable
        "--add-data", "src/templates;templates",  # Bundle the templates folder
        "--icon", icon_path,    # Add custom icon
        "--name", "SpotifyLyricsSync",
        "src/app.py"
    ]

    print("\nRunning PyInstaller build command...")
    print(" ".join(cmd))
    
    try:
        subprocess.run(cmd, check=True)
        print("\n====================================================")
        print(" SUCCESS: Build Completed!")
        print(" Executable generated at: dist/SpotifyLyricsSync.exe")
        print("====================================================")
    except subprocess.CalledProcessError as e:
        print(f"\n[Error] PyInstaller build failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    build()
