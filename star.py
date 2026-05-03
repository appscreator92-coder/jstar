import requests
import re
import json
from datetime import datetime

# URL for the M3U source
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_report():
    print("Fetching and parsing playlist...")
    try:
        response = requests.get(M3U_URL, timeout=20)
        response.raise_for_status()
        # Splitting by lines to handle different line ending formats
        lines = response.text.splitlines()
    except Exception as e:
        print(f"Network error: {e}")
        return

    failed_results = []
    
    # Iterate through lines to find #EXTINF and its corresponding URL
    for i in range(len(lines)):
        current_line = lines[i].strip()
        
        if current_line.startswith("#EXTINF"):
            # 1. Extract Channel Name (Everything after the last comma)
            name_parts = current_line.split(",")
            channel_name = name_parts[-1].strip() if name_parts else "Unknown"
            
            # 2. Extract tvg-id using a flexible search
            id_match = re.search(r'tvg-id="(\d+)"', current_line)
            channel_id = id_match.group(1) if id_match else "0"
            
            # 3. Get the URL from the next line(s)
            # We look ahead to find the first line starting with http
            full_url = ""
            for j in range(i + 1, min(i + 4, len(lines))):
                if lines[j].strip().startswith("http"):
                    # Capture everything on this line (Preserves the entire token)
                    full_url = lines[j].strip()
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

    # Final JSON Structure
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

    print(f"Success: Processed {len(failed_results)} channels.")

if __name__ == "__main__":
    generate_report()
