import requests
import re
import json
from datetime import datetime

# FIX: Removed "/index.html" to point to the actual raw data
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_report():
    print("Fetching and parsing playlist...")
    try:
        # Use a header to be safe, though GitHub Raw usually doesn't require it
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(M3U_URL, headers=headers, timeout=20)
        response.raise_for_status()
        
        # Split by lines to process the M3U structure
        lines = response.text.splitlines()
    except Exception as e:
        print(f"Network error: {e}")
        return

    failed_results = []
    
    for i in range(len(lines)):
        current_line = lines[i].strip()
        
        # Search for the M3U metadata line
        if current_line.startswith("#EXTINF"):
            # 1. Extract Channel Name (Everything after the last comma)
            name_parts = current_line.split(",")
            channel_name = name_parts[-1].strip() if name_parts else "Unknown"
            
            # 2. Extract tvg-id using regex
            id_match = re.search(r'tvg-id="(\d+)"', current_line)
            channel_id = id_match.group(1) if id_match else "0"
            
            # 3. Look ahead for the URL line
            full_url = ""
            # We check the next 3 lines just in case there are empty lines
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip()
                if next_line.startswith("http"):
                    # This captures the WHOLE line including tokens and cookies
                    full_url = next_line
                    break
            
            if full_url:
                failed_results.append({
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "failed",
                    "error_details": {
                        "http_code": 450,
                        "error": "",
                        "final_url": full_url
                    }
                })

    # Prepare Final JSON
    output_data = {
        "total_channels": len(failed_results),
        "successful_channels": 0,
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": [],
        "failed_results": failed_results
    }

    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"Success: Processed {len(failed_results)} channels into {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_report()
