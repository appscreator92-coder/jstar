import requests
import re
import json
from datetime import datetime

# Configuration
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_full_url_report():
    print(f"Fetching data with full tokens...", flush=True)
    
    try:
        response = requests.get(M3U_URL, timeout=20)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Error: {e}")
        return

    # Updated Regex:
    # 1. Captures ID from tvg-id
    # 2. Captures Name after the comma
    # 3. Captures the ENTIRE URL including the token
    pattern = re.compile(r'#EXTINF:.*?tvg-id="(\d+)".*?,(.*?)\n(https?://[^\s]+)')
    matches = pattern.findall(content)

    failed_results = []
    
    for match in matches:
        channel_id, channel_name, full_url = match
        
        failed_results.append({
            "channel_id": channel_id,
            "channel_name": channel_name.strip(),
            "status": "failed",
            "error_details": {
                "http_code": 450,
                "error": "",
                "final_url": full_url.strip() # This now includes the ?__hdnea__ token
            }
        })

    output_data = {
        "total_channels": len(failed_results),
        "successful_channels": 0,
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": [],
        "failed_results": failed_results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"Done! {len(failed_results)} channels saved with full tokens.")

if __name__ == "__main__":
    generate_full_url_report()
