import requests
import re
import json
from datetime import datetime

# Configuration
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def parse_m3u(content):
    channels = []
    # Regular expression to find channel name, id, and the following URL
    # Matches #EXTINF followed by tvg-id and the channel name, then the URL on the next line
    pattern = re.compile(r'#EXTINF:.*tvg-id="([^"]*)".*,(.*)\n(https?://[^\s|]+)', re.MULTILINE)
    
    matches = pattern.findall(content)
    for match in matches:
        channels.append({
            "channel_id": match[0],
            "channel_name": match[1].strip(),
            "url": match[2]
        })
    return channels

def validate_channels(channels):
    successful_results = []
    failed_results = []

    for ch in channels:
        print(f"Checking: {ch['channel_name']}...", end="\r")
        try:
            # We use a HEAD request to check availability quickly without downloading the stream
            response = requests.head(ch['url'], timeout=5)
            status_code = response.status_code
            
            # Logic: Consider 200-299 as success, everything else as failed
            result_item = {
                "channel_id": ch['channel_id'],
                "channel_name": ch['channel_name'],
                "status": "success" if 200 <= status_code < 300 else "failed",
                "error_details": {
                    "http_code": status_code,
                    "error": "" if 200 <= status_code < 300 else "Access Denied or Not Found",
                    "final_url": ch['url']
                }
            }

            if result_item["status"] == "success":
                successful_results.append(result_item)
            else:
                failed_results.append(result_item)

        except Exception as e:
            failed_results.append({
                "channel_id": ch['channel_id'],
                "channel_name": ch['channel_name'],
                "status": "failed",
                "error_details": {
                    "http_code": 0,
                    "error": str(e),
                    "final_url": ch['url']
                }
            })

    return successful_results, failed_results

def generate_detailed_json():
    print(f"Fetching M3U from source...")
    try:
        response = requests.get(M3U_URL, timeout=30)
        response.raise_for_status()
        m3u_content = response.text
    except Exception as e:
        print(f"Failed to fetch M3U: {e}")
        return

    channels = parse_m3u(m3u_content)
    total_count = len(channels)
    
    print(f"Found {total_count} channels. Validating status...")
    success_list, fail_list = validate_channels(channels)

    output = {
        "total_channels": total_count,
        "successful_channels": len(success_list),
        "failed_channels": len(fail_list),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": success_list,
        "failed_results": fail_list
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)
    
    print(f"\nProcessing complete. Results saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_detailed_json()
