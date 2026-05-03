import requests
import re
import json
from datetime import datetime

# Configuration
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_report():
    print(f"Fetching M3U source data...")
    
    try:
        response = requests.get(M3U_URL, timeout=20)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Network Error: {e}")
        return

    # Flexible Regex: 
    # 1. Finds #EXTINF
    # 2. Optionally captures tvg-id if it exists
    # 3. Captures everything after the last comma as the Channel Name
    # 4. Captures the URL on the next line
    pattern = re.compile(r'#EXTINF:.*?(?:tvg-id="([^"]*)")?.*?,(.*?)\n(https?://[^\s|]+)')
    matches = pattern.findall(content)

    success_list = []
    fail_list = []
    
    print(f"Found {len(matches)} channels. Validating links...")

    for match in matches:
        raw_id, raw_name, url = match
        
        # Clean up data
        channel_id = raw_id if raw_id else "N/A"
        channel_name = raw_name.strip()

        try:
            # Check the URL status
            # We use a 5-second timeout to keep the script moving
            check = requests.head(url, timeout=5, allow_redirects=True)
            status_code = check.status_code
        except:
            status_code = 450 # Default fail code for JioTV/Network issues

        result = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "success" if 200 <= status_code < 300 else "failed",
            "error_details": {
                "http_code": status_code,
                "error": "" if 200 <= status_code < 300 else "Access Denied",
                "final_url": url
            }
        }

        if result["status"] == "success":
            success_list.append(result)
        else:
            fail_list.append(result)

    # Final JSON Structure
    output = {
        "total_channels": len(matches),
        "successful_channels": len(success_list),
        "failed_channels": len(fail_list),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": success_list,
        "failed_results": fail_list
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4)

    print(f"Success! Created {OUTPUT_FILE} with {len(matches)} entries.")

if __name__ == "__main__":
    generate_report()
