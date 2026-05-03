import requests
import re
import json
from datetime import datetime

# Source URL
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_report():
    print("Fetching source with full metadata (including cookies)...")
    try:
        # Use a browser-like User-Agent to ensure the source doesn't block us
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(M3U_URL, headers=headers, timeout=20)
        response.raise_for_status()
        lines = response.text.splitlines()
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    failed_results = []
    
    for i in range(len(lines)):
        line = lines[i].strip()
        
        # Look for the info line
        if line.startswith("#EXTINF"):
            # Extract Channel Name (text after the last comma)
            channel_name = line.split(",")[-1].strip()
            
            # Extract ID (numeric value of tvg-id)
            id_match = re.search(r'tvg-id="(\d+)"', line)
            channel_id = id_match.group(1) if id_match else "0"
            
            # Look for the URL on the very next line
            if i + 1 < len(lines):
                potential_url = lines[i+1].strip()
                if potential_url.startswith("http"):
                    # CRITICAL FIX: We do NOT split by '|'. 
                    # We take the whole line to keep the |cookie= part.
                    full_final_url = potential_url
                    
                    failed_results.append({
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "status": "failed",
                        "error_details": {
                            "http_code": 450,
                            "error": "",
                            "final_url": full_final_url
                        }
                    })

    # Build the final JSON structure
    output_data = {
        "total_channels": len(failed_results),
        "successful_channels": 0,
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": [],
        "failed_results": failed_results
    }

    # Save output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"Success! {len(failed_results)} channels captured with full |cookie= data.")

if __name__ == "__main__":
    generate_report()
