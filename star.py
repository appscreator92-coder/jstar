import requests
import re
import json
from datetime import datetime

# Source M3U
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_report():
    print("Fetching and parsing full-token URLs...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(M3U_URL, headers=headers, timeout=20)
        response.raise_for_status()
        lines = response.text.splitlines()
    except Exception as e:
        print(f"Error: {e}")
        return

    failed_results = []
    
    for i in range(len(lines)):
        line = lines[i].strip()
        
        if line.startswith("#EXTINF"):
            # Extract Name
            channel_name = line.split(",")[-1].strip()
            
            # Extract ID
            id_match = re.search(r'tvg-id="(\d+)"', line)
            channel_id = id_match.group(1) if id_match else "0"
            
            # Extract the URL (look ahead to the next line)
            if i + 1 < len(lines):
                url_line = lines[i+1].strip()
                if url_line.startswith("http"):
                    # We take the ENTIRE line. 
                    # This captures the ?__hdnea__ token AND any |cookie= parameters.
                    full_url = url_line
                    
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

    # Final Output
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

    print(f"Complete. Processed {len(failed_results)} channels with full tokens.")

if __name__ == "__main__":
    generate_report()
