import asyncio
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager

async def get_spotify_session():
    """
    Finds and returns the active Windows Media Transport Controls session for Spotify.
    """
    try:
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        sessions = manager.get_sessions()
        
        for session in sessions:
            app_id = session.source_app_user_model_id.lower()
            if "spotify" in app_id:
                return session
        return None
    except Exception as e:
        print(f"[Monitor Error] Failed to query media sessions: {e}")
        return None

async def get_track_info(session):
    """
    Retrieves track metadata, playback status, and timeline position from the session.
    """
    if not session:
        return None
    
    try:
        # Retrieve track properties (Title, Artist, Album)
        props = await session.try_get_media_properties_async()
        title = props.title if props else ""
        artist = props.artist if props else ""
        album = props.album_title if props else ""
        
        import datetime
        from datetime import timezone
        
        # Get playback status (4 is playing, 5 is paused)
        playback_info = session.get_playback_info()
        playback_status = playback_info.playback_status if playback_info else 0
        is_playing = (playback_status == 4)
        
        # Get timeline info (Position and Duration)
        timeline = session.get_timeline_properties()
        position = timeline.position.total_seconds() if timeline else 0.0
        duration = timeline.end_time.total_seconds() if timeline else 0.0
        
        if is_playing and timeline:
            now_utc = datetime.datetime.now(timezone.utc)
            lut = timeline.last_updated_time
            if lut.tzinfo is None:
                lut = lut.replace(tzinfo=timezone.utc)
            elapsed = (now_utc - lut).total_seconds()
            elapsed = max(0.0, elapsed)
            position = position + elapsed
            if duration > 0.0:
                position = min(duration, position)
        
        return {
            "title": title,
            "artist": artist,
            "album": album,
            "position": position,
            "duration": duration,
            "is_playing": is_playing,
            "status_code": playback_status
        }
    except Exception as e:
        print(f"[Monitor Error] Failed to read track info: {e}")
        return None
