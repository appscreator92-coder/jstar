import requests
import re
import json
from datetime import datetime

# Target M3U Source
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_FILE = "star.json"

def generate_report():
    print("Fetching source and preserving full cookie metadata...")
    try:
        # Standard headers to ensure access
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(M3U_URL, headers=headers, timeout=20)
        response.raise_for_status()
        # Split into lines to process each channel block
        lines = response.text.splitlines()
    except Exception as e:
        print(f"Failed to connect: {e}")
        return

    failed_results = []
    
    for i in range(len(lines)):
        line = lines[i].strip()
        
        # Identify the start of a channel block
        if line.startswith("#EXTINF"):
            # Extract Channel Name (text after the last comma)
            channel_name = line.split(",")[-1].strip()
            
            # Extract Numeric ID from tvg-id="123"
            id_match = re.search(r'tvg-id="(\d+)"', line)
            channel_id = id_match.group(1) if id_match else "0"
            
            # Check the next line for the URL
            if i + 1 < len(lines):
                url_line = lines[i+1].strip()
                if url_line.startswith("http"):
                    # We capture the line EXACTLY as is.
                    # This preserves the |cookie=__hdnea__=... section.
                    final_full_url = url_line
                    
                    failed_results.append({
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "status": "failed",
                        "error_details": {
                            "http_code": 450,
                            "error": "",
                            "final_url": final_full_url
                        }
                    })

    # Assemble the final JSON object
    output_data = {
        "total_channels": len(failed_results),
        "successful_channels": 0,
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": [],
        "failed_results": failed_results
    }

    # Write to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)

    print(f"Successfully processed {len(failed_results)} channels with full cookie strings.")

if __name__ == "__main__":
    generate_report()
