import requests
import re
import json
from datetime import datetime

# Configuration
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_channel_report():
    print(f"Connecting to source...")
    
    try:
        # Fetching raw content
        response = requests.get(M3U_URL, timeout=15)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Error: Could not retrieve M3U file. {e}")
        return

    # Regex to capture: tvg-id, channel name, and the URL
    # This handles the specific format found in IPTV playlists
    pattern = re.compile(r'#EXTINF:.*tvg-id="([^"]*)".*?,(.*?)\n(https?://[^\s|]+)', re.MULTILINE)
    matches = pattern.findall(content)

    successful_results = []
    failed_results = []
    
    print(f"Processing {len(matches)} channels...")

    for channel_id, name, url in matches:
        channel_name = name.strip()
        
        try:
            # We use a HEAD request to check the stream status without downloading data
            # Added a common User-Agent to mimic a real player
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            res = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            status_code = res.status_code
        except Exception:
            status_code = 450  # Fallback error code for connection failures

        result_item = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "success" if 200 <= status_code < 300 else "failed",
            "error_details": {
                "http_code": status_code,
                "error": "" if 200 <= status_code < 300 else "Access Denied",
                "final_url": url
            }
        }

        if result_item["status"] == "success":
            successful_results.append(result_item)
        else:
            failed_results.append(result_item)

    # Compile the final dictionary
    output_data = {
        "total_channels": len(matches),
        "successful_channels": len(successful_results),
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": successful_results,
        "failed_results": failed_results
    }

    # Write to JSON
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"Report generated: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_channel_report()
