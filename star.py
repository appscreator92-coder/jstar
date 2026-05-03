import requests
import re
import json
from datetime import datetime

# Configuration
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_star_json():
    print(f"Fetching M3U source...", flush=True)
    
    try:
        # Fetching the raw text from the URL
        response = requests.get(M3U_URL, timeout=20)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Error fetching source: {e}")
        return

    # Regex breakdown:
    # 1. Look for tvg-id="VALUE"
    # 2. Look for the name after the comma
    # 3. Look for the URL on the next line
    pattern = re.compile(r'tvg-id="(\d+)".*?,(.*?)\n(https?://[^\s|]+)')
    matches = pattern.findall(content)

    failed_results = []
    
    for match in matches:
        channel_id, channel_name, final_url = match
        
        # Constructing the channel object
        channel_entry = {
            "channel_id": channel_id,
            "channel_name": channel_name.strip(),
            "status": "failed",
            "error_details": {
                "http_code": 450,
                "error": "",
                "final_url": final_url.strip()
            }
        }
        failed_results.append(channel_entry)

    # Building the final structure
    output_data = {
        "total_channels": len(failed_results),
        "successful_channels": 0,
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": [],
        "failed_results": failed_results
    }

    # Saving to file
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=4)
        print(f"Successfully generated {OUTPUT_FILE} with {len(failed_results)} channels.")
    except Exception as e:
        print(f"Error saving file: {e}")

if __name__ == "__main__":
    generate_star_json()
