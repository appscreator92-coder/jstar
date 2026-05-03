import requests
import re
import json
from datetime import datetime

# Configuration
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u"
OUTPUT_FILE = "star.json"

def generate_detailed_report():
    print(f"Fetching and parsing M3U data...")
    
    try:
        # Note: Ensure we are hitting the RAW file, not the github.com HTML view
        raw_url = M3U_URL.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        response = requests.get(raw_url, timeout=30)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Error fetching M3U: {e}")
        return

    # Improved Regex: Captures channel name and the URL even if tvg-id is missing
    # Looks for #EXTINF, skips to the comma, grabs the name, then finds the URL on the next line
    pattern = re.compile(r'#EXTINF:.*?,(.*)\n(https?://[^\s|]+)', re.MULTILINE)
    matches = pattern.findall(content)

    successful_results = []
    failed_results = []
    
    print(f"Found {len(matches)} potential channels. Starting validation...")

    for i, (name, url) in enumerate(matches):
        channel_name = name.strip()
        # Extract a numeric ID if present, otherwise use index
        channel_id_match = re.search(r'tvg-id="(\d+)"', content.split(name)[0].split('\n')[-1])
        channel_id = channel_id_match.group(1) if channel_id_match else str(400 + i)

        print(f"[{i+1}/{len(matches)}] Testing: {channel_name}")

        try:
            # We perform a quick check. 
            # Many JioTV links return 450/403 without specific headers.
            res = requests.head(url, timeout=5, allow_redirects=True)
            status_code = res.status_code
        except Exception:
            status_code = 450 # Default fail code for connection issues

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

    # Final Object Construction
    output_data = {
        "total_channels": len(matches),
        "successful_channels": len(successful_results),
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": successful_results,
        "failed_results": failed_results
    }

    # Save to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"\nDone! Generated {OUTPUT_FILE} with {len(matches)} entries.")

if __name__ == "__main__":
    generate_detailed_report()
