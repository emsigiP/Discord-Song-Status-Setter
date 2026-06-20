import requests

DISCORD_SETTINGS_URL = "https://discord.com/api/v9/users/@me/settings"

def update_status(token, text, emoji_name=None):
    """
    Sends a PATCH request to update the user's Discord custom status.
    """
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "custom_status": {
            "text": text,
            "emoji_name": emoji_name if emoji_name else "",
            "expires_at": None
        }
    }
    
    try:
        response = requests.patch(DISCORD_SETTINGS_URL, json=payload, headers=headers)
        if response.status_code == 200:
            return True
        elif response.status_code == 429:
            retry_after = response.json().get("retry_after", 5)
            print(f"[Discord Error] Rate limited. Retry after {retry_after}s.")
            return False
        else:
            print(f"[Discord Error] Failed to update status. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"[Discord Error] Request exception: {e}")
        return False

def clear_status(token):
    """
    Sends a PATCH request to clear the custom status.
    """
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "custom_status": None
    }
    
    try:
        response = requests.patch(DISCORD_SETTINGS_URL, json=payload, headers=headers)
        if response.status_code == 200:
            return True
        else:
            print(f"[Discord Error] Failed to clear status. Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        print(f"[Discord Error] Request exception: {e}")
        return False
