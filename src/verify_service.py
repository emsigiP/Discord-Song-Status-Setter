import sys
from lyrics_parser import parse_lrc, get_lyric_for_time

# Reconfigure stdout to use utf-8 to avoid encoding errors in the terminal if stdout exists
if sys.stdout is not None:
    sys.stdout.reconfigure(encoding='utf-8')

def run_tests():
    print("Running automated verification tests...")
    
    # 1. Test LRC parsing
    sample_lrc = """
    [ti:Test Song]
    [ar:Test Artist]
    [00:01.00]First lyric line
    [00:05.50]Second lyric line with millisecond centiseconds
    [01:10.00]Third lyric line at one minute ten seconds
    """
    
    parsed = parse_lrc(sample_lrc)
    assert len(parsed) == 3, f"Expected 3 parsed lines, got {len(parsed)}"
    
    assert parsed[0] == (1.0, "First lyric line")
    assert parsed[1] == (5.5, "Second lyric line with millisecond centiseconds")
    assert parsed[2] == (70.0, "Third lyric line at one minute ten seconds")
    print("✓ LRC Parsing Test Passed")
    
    # 2. Test lyric matching logic
    assert get_lyric_for_time(parsed, 0.0) == ""
    assert get_lyric_for_time(parsed, 1.0) == "First lyric line"
    assert get_lyric_for_time(parsed, 4.0) == "First lyric line"
    assert get_lyric_for_time(parsed, 5.5) == "Second lyric line with millisecond centiseconds"
    assert get_lyric_for_time(parsed, 50.0) == "Second lyric line with millisecond centiseconds"
    assert get_lyric_for_time(parsed, 70.0) == "Third lyric line at one minute ten seconds"
    assert get_lyric_for_time(parsed, 100.0) == "Third lyric line at one minute ten seconds"
    print("✓ Lyric Matching Logic Test Passed")
    
    # 3. Test dependencies loading
    try:
        import config
        print("✓ config.py loaded and validated successfully")
    except Exception as e:
        print(f"✗ config.py failed to load: {e}")
        return False
        
    try:
        import spotify_monitor
        print("✓ spotify_monitor.py loaded successfully")
    except Exception as e:
        print(f"✗ spotify_monitor.py failed to load: {e}")
        return False
        
    try:
        import discord_client
        print("✓ discord_client.py loaded successfully")
    except Exception as e:
        print(f"✗ discord_client.py failed to load: {e}")
        return False
        
    print("\nAll verification tests passed successfully!")
    return True

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
