import os
from dotenv import load_dotenv

# Load environmental variables from .env file
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
STATUS_EMOJI = os.getenv("STATUS_EMOJI", "🎵")
CHECK_INTERVAL_SECONDS = float(os.getenv("CHECK_INTERVAL_SECONDS", "1.0"))
CLEAR_ON_PAUSE = os.getenv("CLEAR_ON_PAUSE", "True").lower() in ("true", "1", "yes")
FALLBACK_STATUS = os.getenv("FALLBACK_STATUS", "")
LATENCY_COMPENSATION = float(os.getenv("LATENCY_COMPENSATION", "0.25"))

# Simple validation
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is missing from your .env file! Please add it to start.")
