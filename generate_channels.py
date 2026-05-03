import os
import re
import requests
import json
from datetime import datetime

# Configuration
M3U_URL = "https://raw.githubusercontent.com/sportlive18/Jio-Auto-Update-m3u-playlist/refs/heads/main/jiotv.m3u"
OUTPUT_FILE = "cookie.json"

def generate_simple_json():
    print(f"Fetching M3U and extracting data...", flush=True)
    try:
        response = requests.get(M3U_URL, timeout=30)
        response.raise_for_status()
        lines = response.text.splitlines()
    except Exception as e:
        print(f"Error fetching M3U: {e}")
        return

    extracted_cookie = ""
    
    # Logic to find the first available cookie in the M3U
    for line in lines:
        if "https://" in line and "|cookie=" in line:
            parts = line.split("|")
            for part in parts:
                if part.startswith("cookie="):
                    extracted_cookie = part.replace("cookie=", "").strip()
                    break
            if extracted_cookie:
                break

    # Format current time: HH:mm DD-MM-YYYY
    current_time = datetime.now().strftime("%H:%M %d-%m-%Y")

    # Construct the specific list structure requested
    output_data = [
        {
            "last_updated": current_time
        },
        {
            "cookie": extracted_cookie
        }
    ]

    # Save to file
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2)
        print(f"Successfully generated {OUTPUT_FILE}")
        # Print to console for immediate verification
        print(json.dumps(output_data, indent=2))
    except Exception as e:
        print(f"Error saving JSON: {e}")

if __name__ == "__main__":
    generate_simple_json()
