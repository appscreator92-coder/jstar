import requests
import re
import json
from datetime import datetime

# Configuration - Using the RAW link to ensure we get text, not HTML
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_exact_result():
    print("Connecting to source...")
    try:
        response = requests.get(M3U_URL, timeout=15)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Failed to fetch: {e}")
        return

    # This regex is broader: 
    # 1. Finds #EXTINF
    # 2. Finds the last comma and captures the name
    # 3. Finds the URL on the next line
    # 4. Searches for tvg-id separately to avoid missing lines without IDs
    failed_results = []
    lines = content.splitlines()
    
    for i in range(len(lines)):
        if lines[i].startswith("#EXTINF"):
            # Extract Name (Everything after the last comma)
            name = lines[i].split(",")[-1].strip()
            
            # Extract ID (Look for tvg-id="...")
            id_match = re.search(r'tvg-id="(\d+)"', lines[i])
            channel_id = id_match.group(1) if id_match else "0"
            
            # Extract URL (Usually the very next line)
            if i + 1 < len(lines):
                url_line = lines[i+1].strip()
                # Clean URL (Remove any |cookie= metadata)
                final_url = url_line.split("|")[0]
                
                if final_url.startswith("http"):
                    failed_results.append({
                        "channel_id": channel_id,
                        "channel_name": name,
                        "status": "failed",
                        "error_details": {
                            "http_code": 450,
                            "error": "",
                            "final_url": final_url
                        }
                    })

    # Construct the final JSON object
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

    print(f"Success! {len(failed_results)} channels processed into {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_exact_result()
