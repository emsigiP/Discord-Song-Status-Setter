import sys
import os
import ctypes

def hide_console():
    if os.name == 'nt':
        whnd = ctypes.windll.kernel32.GetConsoleWindow()
        if whnd != 0:
            ctypes.windll.user32.ShowWindow(whnd, 0) # SW_HIDE = 0

# Hide the console window immediately
hide_console()

# Redirect stdout and stderr to devnull in headless/noconsole mode to prevent crashes from prints
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import time
import threading
import webbrowser
import subprocess
from flask import Flask, jsonify, request, render_template, send_file
from dotenv import load_dotenv

import main  # Imports main.py which holds the shared state and sync loop controls

# Helper to get the absolute path to the .env file
def get_env_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), '.env')
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, '.env')

# Helper to send native Windows tray notifications silently
def send_startup_notification():
    if getattr(sys, 'frozen', False):
        target_path = os.path.abspath(sys.executable)
    else:
        target_path = os.path.abspath(__file__)
        
    ps_script = f"""
    $shortcutDir = "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs"
    $shortcutPath = Join-Path $shortcutDir "Spotify Lyrics Sync.lnk"
    $targetPath = "{target_path}"
    
    # Create or update shortcut if needed
    if (!(Test-Path $shortcutPath) -or (Get-Item $shortcutPath).Length -eq 0) {{
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $shortcut.TargetPath = $targetPath
        $shortcut.IconLocation = "$targetPath,0"
        $shortcut.Save()
        
        # Write PKEY_AppUserModel_ID to shortcut properties using C# ShellLink helper
        $helper = @"
        using System;
        using System.Runtime.InteropServices;
        using System.Runtime.InteropServices.ComTypes;

        public class ShellLink {{
            [ComImport, Guid("00021401-0000-0000-C000-000000000046")]
            public class CShellLink {{}}

            [ComImport, InterfaceType(ComInterfaceType.InterfaceIsIUnknown), Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99")]
            interface IPropertyStore {{
                void GetCount(out uint cProps);
                void GetAt(uint iProp, out PropertyKey pkey);
                void GetValue(ref PropertyKey pkey, out PropVariant pv);
                void SetValue(ref PropertyKey pkey, ref PropVariant pv);
                void Commit();
            }}

            [StructLayout(LayoutKind.Sequential, Pack = 4)]
            public struct PropertyKey {{
                public Guid fmtid;
                public uint pid;
                public PropertyKey(Guid guid, uint id) {{
                    fmtid = guid;
                    pid = id;
                }}
            }}

            [StructLayout(LayoutKind.Explicit)]
            public struct PropVariant {{
                [FieldOffset(0)] public ushort vt;
                [FieldOffset(8)] public IntPtr ptr;
                
                public static PropVariant FromString(string val) {{
                    var pv = new PropVariant();
                    pv.vt = 31;
                    pv.ptr = Marshal.StringToCoTaskMemUni(val);
                    return pv;
                }}
            }}

            public static void SetAppId(string shortcutPath, string appId) {{
                CShellLink link = new CShellLink();
                ((IPersistFile)link).Load(shortcutPath, 0);
                IPropertyStore store = (IPropertyStore)link;
                PropertyKey key = new PropertyKey(new Guid("9F4C2855-0379-4D8E-A758-312FC8F0CF43"), 5);
                PropVariant val = PropVariant.FromString(appId);
                store.SetValue(ref key, ref val);
                store.Commit();
                ((IPersistFile)link).Save(shortcutPath, true);
            }}
        }}
"@
        Add-Type -TypeDefinition $helper -ErrorAction SilentlyContinue
        [ShellLink]::SetAppId($shortcutPath, "SpotifyLyricsSync")
    }}

    # Send UWP Toast notification
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
    $toastXml = [xml]$template.GetXml()
    $toastXml.GetElementsByTagName('text')[0].AppendChild($toastXml.CreateTextNode('Spotify Lyrics Sync')) | Out-Null
    $toastXml.GetElementsByTagName('text')[1].AppendChild($toastXml.CreateTextNode('Sync service started. Control panel is open at http://127.0.0.1:5000')) | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($toastXml.OuterXml)
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('SpotifyLyricsSync').Show($toast)
    """
    try:
        subprocess.Popen(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script],
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    except Exception as e:
        print(f"Failed to send notification: {e}")

# Resolve templates folder for PyInstaller bundle compatibility
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
else:
    template_folder = 'templates'

app = Flask(__name__, template_folder=template_folder)

# Disable caching for local development and hot-reloads
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Helper to load settings from .env file
def get_current_settings():
    load_dotenv(get_env_path(), override=True)
    return {
        "DISCORD_TOKEN": os.getenv("DISCORD_TOKEN", ""),
        "STATUS_EMOJI": os.getenv("STATUS_EMOJI", "🎵"),
        "CHECK_INTERVAL_SECONDS": os.getenv("CHECK_INTERVAL_SECONDS", "0.2"),
        "CLEAR_ON_PAUSE": os.getenv("CLEAR_ON_PAUSE", "True"),
        "FALLBACK_STATUS": os.getenv("FALLBACK_STATUS", ""),
        "LATENCY_COMPENSATION": os.getenv("LATENCY_COMPENSATION", "0.25")
    }

# Helper to save settings back to .env
def save_settings_to_env(settings):
    env_path = get_env_path()
    lines = []
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            pass
            
    keys_written = set()
    new_lines = []
    
    for line in lines:
        line_strip = line.strip()
        # Preserve comments and empty lines
        if not line_strip or line_strip.startswith("#"):
            new_lines.append(line)
            continue
        parts = line_strip.split("=", 1)
        if len(parts) == 2:
            key = parts[0].strip()
            if key in settings:
                new_lines.append(f"{key}={settings[key]}\n")
                keys_written.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
            
    for key, val in settings.items():
        if key not in keys_written:
            new_lines.append(f"{key}={val}\n")
            
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

@app.route("/")
def index():
    """
    Renders the web dashboard.
    """
    return render_template("index.html")

@app.route("/api/status", methods=["GET"])
def api_status():
    """
    Returns the real-time shared state of the sync background thread.
    """
    # Return thread info and logs
    with main.state_lock:
        state = dict(main.shared_state)
    return jsonify(state)

@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    """
    GET: Retrieves the current configuration parameters from .env.
    POST: Updates configuration parameters and saves them to .env.
    """
    if request.method == "POST":
        data = request.json
        if not data:
            return jsonify({"success": False, "error": "Invalid JSON data"}), 400
            
        settings = {
            "DISCORD_TOKEN": data.get("DISCORD_TOKEN", "").strip(),
            "STATUS_EMOJI": data.get("STATUS_EMOJI", "🎵").strip(),
            "CHECK_INTERVAL_SECONDS": str(data.get("CHECK_INTERVAL_SECONDS", "0.2")),
            "CLEAR_ON_PAUSE": "True" if data.get("CLEAR_ON_PAUSE") else "False",
            "FALLBACK_STATUS": data.get("FALLBACK_STATUS", "").strip(),
            "LATENCY_COMPENSATION": str(data.get("LATENCY_COMPENSATION", "0.25"))
        }
        
        if not settings["DISCORD_TOKEN"]:
            return jsonify({"success": False, "error": "Discord token is required"}), 400
            
        try:
            save_settings_to_env(settings)
            main.log_message("[System] Settings updated from Web UI.")
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to save settings: {e}"}), 500
            
    else:
        # GET request
        return jsonify(get_current_settings())

@app.route("/api/control", methods=["POST"])
def api_control():
    """
    Toggles the background synchronizer on or off.
    """
    data = request.json
    if not data or "action" not in data:
        return jsonify({"success": False, "error": "Action required"}), 400
        
    action = data["action"].lower()
    
    if action == "start":
        # Check settings first
        settings = get_current_settings()
        if not settings["DISCORD_TOKEN"]:
            return jsonify({"success": False, "error": "Discord token is missing. Please save settings first."}), 400
            
        started = main.start_sync()
        if started:
            main.log_message("[System] Sync service started from Web UI.")
            return jsonify({"success": True, "running": True})
        else:
            return jsonify({"success": False, "error": "Service is already running"}), 400
            
    elif action == "stop":
        stopped = main.stop_sync()
        if stopped:
            main.log_message("[System] Sync service stopped from Web UI.")
            return jsonify({"success": True, "running": False})
        else:
            return jsonify({"success": False, "error": "Service is not running"}), 400
            
    else:
        return jsonify({"success": False, "error": "Invalid action"}), 400

@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """
    Shuts down the Flask server and terminates the application process.
    """
    main.log_message("[System] Shutdown requested from Web UI. Terminating process...")
    # Stop background sync thread cleanly
    main.stop_sync()
    
    # Run process exit after a brief sleep to allow the response to return to the browser
    def kill_process():
        time.sleep(1.0)
        os._exit(0)
        
    threading.Thread(target=kill_process, daemon=True).start()
    return jsonify({"success": True, "message": "Server is shutting down..."})

if __name__ == "__main__":
    # Start the local browser automatically after a short delay and send notification
    def open_browser():
        time.sleep(1.2)
        webbrowser.open("http://127.0.0.1:5000")
        send_startup_notification()
        
    # Check if we should autostart the sync thread on app launch
    # If a valid token is already saved, we can autostart the service to be user-friendly
    settings = get_current_settings()
    if settings["DISCORD_TOKEN"]:
        main.start_sync()
        main.log_message("[System] Autostarted sync service on app launch.")

    # Start browser thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Run Flask server locally
    print("[Server] Starting local Flask control panel at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
