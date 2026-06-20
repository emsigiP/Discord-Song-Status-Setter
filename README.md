# Spotify Lyrics Discord Status Synchronizer

A lightweight Windows tool that connects your local Spotify playback to your Discord account, updating your custom status with the currently playing lyric line in real-time.

Features a **frosted-glass Web Control Panel & Dashboard** to easily enter settings, save configurations, and monitor playback stats/logs in real-time.

---

## Features
*   **Real-time Synced Lyrics:** Tracks Spotify progress and updates status immediately when the singer sings.
*   **Latency Compensation:** Pre-empts network delay to Discord servers, aligning lyric updates perfectly.
*   **Fake/Lazy Sync Filtering:** Detects and filters out bot-generated, evenly-spaced lyrics from LRCLIB, falling back to a clean track title display instead.
*   **API Debounce & Timeout Recovery:** Prevents rate-limiting when replaying or skipping songs, and retries automatically if queries time out.
*   **Clean Settings UI:** Save your token, emoji, and intervals directly from a local browser dashboard.

---

## Prerequisites
*   **Operating System:** Windows 10 or Windows 11 (uses Windows Runtime APIs to monitor local media controls).
*   **Python:** Python 3.10 or higher.

---

## How to Run

1.  **Start the app:** Double-click **`run.bat`** in the main folder. (It will check and automatically install all needed libraries on first launch).
2.  **Open Dashboard:** A browser window will open automatically at `http://127.0.0.1:5000`.
3.  **Get Discord Token:**
    *   Open Discord in a web browser and press `F12` (or `Ctrl+Shift+I`) to open Developer Tools.
    *   Select the **Network** tab and filter by `/api`.
    *   Click on any channel/server in Discord to trigger a request (e.g. `science`, `profile`, `settings`).
    *   Select the request, scroll down to **Request Headers**, and copy the value of the **`Authorization`** header.
4.  **Save & Sync:** Paste the token into the Web UI settings, configure your preferences (Emoji, delay offset), and click **Start Syncing**.
5.  **Listen:** Open Spotify on Windows and play a song!

---

## Configuration Settings
*   **Status Emoji:** The emoji displayed next to your lyrics (default: `🎵`).
*   **Polling Interval:** How frequently the script checks Spotify's time (default: `0.2s` for fluid tracking).
*   **Latency Compensation:** Adjusts the lyric time offset to cancel out internet delay when sending updates to Discord (default: `0.25s` ahead).
*   **Clear on Pause:** Automatically clears your Discord status when Spotify is paused.
*   **Fallback Status:** The status text shown if no synced lyrics are found on LRCLIB (default: `Song Title - Artist Name`).

---

## Directory Structure
*   `src/` - Contains core python modules (monitoring, parsing, Discord client, server).
*   `requirements.txt` - Python dependency declarations.
*   `run.bat` - Windows launcher script.
*   `LICENSE` - License terms.
*   `.env` - Local configuration (ignored by Git for security).

---

## Warning & Terms of Service
Using user tokens to automate account features (self-botting) violates **Discord's Terms of Service**. Use this tool at your own risk. **Never share your Discord token with anyone.**
