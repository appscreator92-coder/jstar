import requests
import re
import json
from datetime import datetime

# Configuration
# Using the direct RAW content URL is the most reliable method
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_star_report():
    print(f"Scanning source for channel data...", flush=True)
    
    try:
        # Standard headers to prevent being blocked by GitHub
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(M3U_URL, headers=headers, timeout=20)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # STEP 1: Find all streaming URLs in the text
    # This finds the link and stops before any '|' or ' ' 
    url_pattern = re.compile(r'(https?://jiotvpllive\.cdn\.jio\.com/[^\s"|]+)')
    urls = url_pattern.findall(content)

    # STEP 2: Find all Names/IDs
    # This looks for #EXTINF lines specifically
    inf_pattern = re.compile(r'#EXTINF:.*?tvg-id="(\d+)".*?,(.*)')
    inf_matches = inf_pattern.findall(content)

    failed_results = []
    
    # We loop through the URLs found and pair them with names
    # If the counts don't match, it falls back to index-based naming
    for i in range(len(urls)):
        # Try to get the ID and Name from the #EXTINF matches
        if i < len(inf_matches):
            channel_id = inf_matches[i][0]
            channel_name = inf_matches[i][1].strip()
        else:
            channel_id = str(100 + i)
            channel_name = f"Unknown Channel {i+1}"

        failed_results.append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "error_details": {
                "http_code": 450,
                "error": "",
                "final_url": urls[i]
            }
        })

    # Final Object
    output_data = {
        "total_channels": len(failed_results),
        "successful_channels": 0,
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": [],
        "failed_results": failed_results
    }

    # Save and Print
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"SUCCESS: Extracted {len(failed_results)} channels into {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_star_report()
