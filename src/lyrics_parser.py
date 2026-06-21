import re

def parse_lrc(lrc_text):
    """
    Parses an LRC format string into a list of tuples: (time_in_seconds, lyric_line)
    Example input line: [01:23.45] Some lyric text
    """
    if not lrc_text:
        return []
    
    parsed = []
    # Regex to match [minutes:seconds.centiseconds/milliseconds]
    pattern = re.compile(r'^\[(\d+):(\d+(?:\.\d+)?)\](.*)$')
    
    for line in lrc_text.splitlines():
        line = line.strip()
        match = pattern.match(line)
        if match:
            try:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                text = match.group(3).strip()
                # Remove extra formatting if any
                total_seconds = minutes * 60 + seconds
                parsed.append((total_seconds, text))
            except ValueError:
                continue
                
    # Sort lyric lines chronologically just in case
    parsed.sort(key=lambda x: x[0])
    return parsed

def get_lyric_for_time(parsed_lyrics, current_time):
    """
    Returns the lyric line corresponding to the current_time (in seconds).
    Finds the last lyric line whose timestamp is <= current_time.
    """
    if not parsed_lyrics:
        return ""
    
    active_lyric = ""
    for timestamp, text in parsed_lyrics:
        if timestamp <= current_time:
            active_lyric = text
        else:
            break
            
    return active_lyric

def is_fake_sync(parsed_lines):
    """
    Detects if a synced lyric file is bot-generated (evenly spaced or fake).
    Returns True if it is fake, False otherwise.
    """
    if len(parsed_lines) < 10:
        return False
    
    diffs = []
    for i in range(len(parsed_lines) - 1):
        diff = round(parsed_lines[i+1][0] - parsed_lines[i][0], 3)
        diffs.append(diff)
        
    consecutive_matches = 0
    max_consecutive = 0
    for i in range(len(diffs) - 1):
        if abs(diffs[i] - diffs[i+1]) < 0.05:
            consecutive_matches += 1
            if consecutive_matches > max_consecutive:
                max_consecutive = consecutive_matches
        else:
            consecutive_matches = 0
            
    # Calculate percentage of identical intervals
    identical_count = 0
    for i in range(len(diffs)):
        for j in range(i + 1, len(diffs)):
            if abs(diffs[i] - diffs[j]) < 0.05:
                identical_count += 1
                break
    pct_identical = identical_count / len(diffs) if diffs else 0
    
    # Calculate variance
    mean_diff = sum(diffs) / len(diffs)
    variance = sum((d - mean_diff) ** 2 for d in diffs) / len(diffs)
    
    # A song is fake sync if it has a large number of consecutive identical intervals (e.g. >= 8)
    # or if the variance is extremely small (e.g. < 0.15) and a high percentage of intervals match
    if max_consecutive >= 8:
        return True
    if variance < 0.15 and pct_identical > 0.6:
        return True
        
    return False
