import asyncio
import sys
import requests
import time
import threading
import os
from dotenv import load_dotenv

from lyrics_parser import parse_lrc, get_lyric_for_time, is_fake_sync
from spotify_monitor import get_spotify_session, get_track_info
from discord_client import update_status, clear_status

# Reconfigure stdout to use utf-8 to avoid encoding errors in the terminal if stdout exists
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')

# Helper to get the absolute path to the .env file
def get_env_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), '.env')
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_dir, '.env')

# Shared state between Flask and the background sync thread
shared_state = {
    "running": False,
    "spotify_active": False,
    "track_info": None,
    "active_lyric": "",
    "lyrics_state": "NOT_FOUND",
    "logs": []
}

# Lock for logs and state access safety
state_lock = threading.Lock()
sync_thread = None

# Async Discord Custom Status update target state
discord_target_status = None
discord_target_emoji = None
discord_current_status = None

def set_target_discord_status(status, emoji):
    global discord_target_status, discord_target_emoji
    discord_target_status = status
    discord_target_emoji = emoji

def log_message(msg):
    """
    Logs messages to stdout and appends them to the shared state logs.
    """
    timestamp = time.strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted)
    with state_lock:
        shared_state["logs"].append(formatted)
        if len(shared_state["logs"]) > 50:
            shared_state["logs"].pop(0)

def fetch_artwork_url(artist, title):
    """
    Fetches cover art image URL from iTunes Search API.
    """
    import re
    clean_artist = re.sub(r'[\(\[].*?[\)\]]', '', artist).strip()
    clean_title = re.sub(r'[\(\[].*?[\)\]]', '', title).strip()
    
    query = f"{clean_artist} {clean_title}"
    url = "https://itunes.apple.com/search"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        response = requests.get(url, params={"term": query, "entity": "song", "limit": 1}, headers=headers, timeout=3)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                art_url = results[0].get("artworkUrl100", "")
                if art_url:
                    return art_url.replace("100x100bb.jpg", "200x200bb.jpg")
    except Exception as e:
        print(f"[Artwork Error] Failed to fetch cover art: {e}")
    return ""

def fetch_lyrics(artist, title, album, duration):
    """
    Fetches synced lyrics from the configured provider using syncedlyrics.
    """
    import syncedlyrics
    
    # Reload settings from env to dynamically respect provider choice
    load_dotenv(get_env_path(), override=True)
    
    # Load the configured provider from env
    provider_setting = os.getenv("LYRICS_PROVIDER", "auto").lower()
    
    if provider_setting == "musixmatch":
        providers = ["musixmatch"]
    elif provider_setting == "lrclib":
        providers = ["lrclib"]
    elif provider_setting == "netease":
        providers = ["netease"]
    else:  # auto
        providers = ["musixmatch", "lrclib", "netease"]
        
    query = f"{artist} {title}"
    
    try:
        # Request search via syncedlyrics
        lrc_text = syncedlyrics.search(query, providers=providers)
        if lrc_text:
            parsed = parse_lrc(lrc_text)
            if not parsed:
                log_message(f"[Lyrics] Found lyrics for '{title}', but no timestamp sync data. Skipping.")
                return ("NOT_FOUND", None)
                
            if is_fake_sync(parsed):
                log_message(f"[Lyrics] Rejected fake sync pattern for '{title}'. Falling back.")
                return ("NOT_FOUND", None)
                
            log_message(f"[Lyrics] Synced lyrics matched successfully for '{title}' (Provider: {provider_setting})")
            return ("SUCCESS", lrc_text)
        else:
            log_message(f"[Lyrics] No synced lyrics found for '{title}' using {provider_setting}")
            return ("NOT_FOUND", None)
            
    except Exception as e:
        log_message(f"[Lyrics Error] Fetch failed: {e}")
        return ("FAILED", None)

async def fetch_track_resources(artist, title, album, duration):
    """
    Asynchronously fetches track cover art and lyrics in background threads.
    """
    try:
        # Start fetching artwork URL instantly in a thread
        artwork_task = asyncio.to_thread(fetch_artwork_url, artist, title)
        
        # Debounce the lyrics lookup by waiting 0.4 seconds non-blockingly
        await asyncio.sleep(0.4)
        
        # Start fetching lyrics in a thread
        lyrics_task = asyncio.to_thread(fetch_lyrics, artist, title, album, duration)
        
        # Wait for both to complete
        artwork_url = await artwork_task
        
        # Update shared state with artwork if the track is still current
        with state_lock:
            track_info = shared_state["track_info"]
            if track_info and track_info["title"] == title and track_info["artist"] == artist:
                track_info["artwork_url"] = artwork_url
                
        state, lrc_text = await lyrics_task
        return state, lrc_text
        
    except asyncio.CancelledError:
        raise
    except Exception as e:
        log_message(f"[Fetch Error] Background task failed: {e}")
        return "FAILED", None

async def discord_status_updater(discord_token):
    """
    Asynchronous background task to patch status changes without blocking the sync loop.
    """
    global discord_target_status, discord_target_emoji, discord_current_status
    discord_current_status = ""  # Force initial update
    
    while True:
        try:
            if discord_target_status != discord_current_status:
                status_to_set = discord_target_status
                emoji_to_set = discord_target_emoji
                
                if status_to_set is None:
                    # Clear status
                    success = await asyncio.to_thread(clear_status, discord_token)
                else:
                    # Update status
                    success = await asyncio.to_thread(update_status, discord_token, status_to_set, emoji_to_set)
                
                if success:
                    discord_current_status = status_to_set
                else:
                    # Sleep 1s on failure/rate-limit before retrying
                    await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(0.05)  # Fast check interval
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Discord Updater Exception] {e}")
            await asyncio.sleep(1.0)

async def sync_loop():
    """
    Core sync loop running in background.
    """
    # Reload settings from .env file at thread start
    load_dotenv(get_env_path(), override=True)
    
    discord_token = os.getenv("DISCORD_TOKEN")
    status_emoji = os.getenv("STATUS_EMOJI", "🎵")
    check_interval = float(os.getenv("CHECK_INTERVAL_SECONDS", "0.2"))
    clear_on_pause = os.getenv("CLEAR_ON_PAUSE", "True").lower() in ("true", "1", "yes")
    fallback_status_pattern = os.getenv("FALLBACK_STATUS", "")
    latency_compensation = float(os.getenv("LATENCY_COMPENSATION", "0.25"))

    if not discord_token:
        log_message("[Error] DISCORD_TOKEN is missing. Cannot start synchronizer.")
        with state_lock:
            shared_state["running"] = False
        return

    log_message("==================================================")
    log_message(" Spotify Lyrics Status Sync loop started (Async)")
    log_message(f" Polling interval: {check_interval}s | Latency comp: {latency_compensation}s")
    log_message("==================================================")

    last_track_title = ""
    last_track_artist = ""
    last_set_status = None
    current_artwork_url = ""
    
    parsed_lyrics = []
    current_fetch_task = None
    last_retry_time = 0.0
    
    session = None
    
    # Set thread running state
    with state_lock:
        shared_state["running"] = True
        shared_state["active_lyric"] = ""
        shared_state["lyrics_state"] = "NOT_FOUND"

    # Start the async Discord status updater worker
    updater_task = asyncio.create_task(discord_status_updater(discord_token))

    while True:
        # Check if thread should terminate
        with state_lock:
            if not shared_state["running"]:
                break
                
        try:
            # Re-evaluate session if we don't have one
            if not session:
                session = await get_spotify_session()
                if not session:
                    with state_lock:
                        shared_state["spotify_active"] = False
                        shared_state["track_info"] = None
                    if last_set_status is not None:
                        log_message("[System] Spotify not found. Clearing Discord status...")
                        set_target_discord_status(None, None)
                        last_set_status = None
                    await asyncio.sleep(2.0)
                    continue
            
            # Fetch current track details
            track_info = await get_track_info(session)
            if not track_info:
                session = None
                with state_lock:
                    shared_state["spotify_active"] = False
                    shared_state["track_info"] = None
                continue
                
            title = track_info["title"]
            artist = track_info["artist"]
            album = track_info["album"]
            position = track_info["position"]
            duration = track_info["duration"]
            is_playing = track_info["is_playing"]
            
            # Check if background lyrics fetch has completed
            if current_fetch_task and current_fetch_task.done():
                try:
                    if not current_fetch_task.cancelled():
                        state, lrc_text = current_fetch_task.result()
                        with state_lock:
                            shared_state["lyrics_state"] = state
                        if state == "SUCCESS" and lrc_text:
                            parsed_lyrics = parse_lrc(lrc_text)
                        elif state == "FAILED":
                            last_retry_time = time.time()
                except Exception as e:
                    log_message(f"[Fetch Result Error] {e}")
                current_fetch_task = None

            # Detect track change
            if title != last_track_title or artist != last_track_artist:
                log_message(f"[Track Changed] Now Playing: '{title}' by '{artist}'")
                last_track_title = title
                last_track_artist = artist
                current_artwork_url = ""
                
                # Cancel existing fetch task if active
                if current_fetch_task and not current_fetch_task.done():
                    current_fetch_task.cancel()
                
                # Enter debounce/pending state and spawn non-blocking fetcher
                with state_lock:
                    shared_state["lyrics_state"] = "PENDING"
                    shared_state["active_lyric"] = ""
                parsed_lyrics = []
                last_set_status = None
                
                current_fetch_task = asyncio.create_task(
                    fetch_track_resources(artist, title, album, duration)
                )

            # Retrieve background-loaded artwork URL if populated
            with state_lock:
                if shared_state["track_info"] and shared_state["track_info"].get("artwork_url"):
                    current_artwork_url = shared_state["track_info"]["artwork_url"]
            track_info["artwork_url"] = current_artwork_url

            with state_lock:
                shared_state["spotify_active"] = True
                shared_state["track_info"] = track_info

            # If paused or stopped
            if not is_playing:
                if clear_on_pause and last_set_status is not None:
                    log_message(f"[System] Playback paused. Clearing Discord status...")
                    set_target_discord_status(None, None)
                    last_set_status = None
                    with state_lock:
                        shared_state["active_lyric"] = ""
                await asyncio.sleep(check_interval)
                continue
                
            state_now = shared_state["lyrics_state"]
            
            # Retry fetching lyrics on failure
            if state_now == "FAILED" and (time.time() - last_retry_time >= 10.0) and not current_fetch_task:
                log_message(f"[Retry] Retrying lyrics fetch for '{title}'...")
                with state_lock:
                    shared_state["lyrics_state"] = "PENDING"
                current_fetch_task = asyncio.create_task(
                    fetch_track_resources(artist, title, album, duration)
                )
                
            # Read state again
            state_now = shared_state["lyrics_state"]
            
            # Update status
            if state_now == "SUCCESS" and parsed_lyrics:
                active_lyric = get_lyric_for_time(parsed_lyrics, position + latency_compensation)
                with state_lock:
                    shared_state["active_lyric"] = active_lyric
                    
                if active_lyric and active_lyric != last_set_status:
                    log_message(f"[Sync] {active_lyric}")
                    set_target_discord_status(active_lyric, status_emoji)
                    last_set_status = active_lyric
            elif state_now == "PENDING":
                fallback_text = f"{title} - {artist}"
                if len(fallback_text) > 128:
                    fallback_text = fallback_text[:125] + "..."
                with state_lock:
                    shared_state["active_lyric"] = fallback_text
                    
                if fallback_text != last_set_status:
                    log_message(f"[Sync Fallback] {fallback_text}")
                    set_target_discord_status(fallback_text, status_emoji)
                    last_set_status = fallback_text
            else:
                # FAILED or NOT_FOUND
                fallback_text = fallback_status_pattern if fallback_status_pattern else f"{title} - {artist}"
                if len(fallback_text) > 128:
                    fallback_text = fallback_text[:125] + "..."
                with state_lock:
                    shared_state["active_lyric"] = fallback_text
                    
                if fallback_text != last_set_status:
                    log_message(f"[Sync Fallback] {fallback_text}")
                    set_target_discord_status(fallback_text, status_emoji)
                    last_set_status = fallback_text
                        
            await asyncio.sleep(check_interval)
            
        except Exception as e:
            log_message(f"[Loop Error] {e}")
            session = None
            await asyncio.sleep(3.0)

    # Clean up status on loop exit
    log_message("[System] Loop stopped. Clearing Discord status...")
    try:
        updater_task.cancel()
        await updater_task
    except Exception:
        pass
    try:
        clear_status(discord_token)
    except Exception:
        pass
    log_message("[System] Synchronizer stopped.")

def thread_entry():
    """
    Entry point for the thread to run the asyncio loop.
    """
    asyncio.run(sync_loop())

def start_sync():
    """
    Starts the sync service in a background thread.
    """
    global sync_thread
    with state_lock:
        if shared_state["running"]:
            return False
        shared_state["running"] = True
        
    sync_thread = threading.Thread(target=thread_entry, daemon=True)
    sync_thread.start()
    return True

def stop_sync():
    """
    Stops the sync service.
    """
    with state_lock:
        if not shared_state["running"]:
            return False
        shared_state["running"] = False
    return True

if __name__ == "__main__":
    try:
        asyncio.run(sync_loop())
    except KeyboardInterrupt:
        print("\n[System] Exiting. Clearing Discord status...")
        token = os.getenv("DISCORD_TOKEN")
        if token:
            try:
                clear_status(token)
            except Exception:
                pass
        print("[System] Goodbye!")
