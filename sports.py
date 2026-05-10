import requests
import re
import json

def extract():
    url = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Error: {e}")
        return

    playlist = []
    # Split by #EXTINF
    entries = content.split("#EXTINF")
    
    for entry in entries:
        if not entry.strip() or entry.startswith("#EXTM3U"):
            continue

        # Extraction Logic
        tvg_id = re.search(r'tvg-id="([^"]*)"', entry)
        logo = re.search(r'tvg-logo="([^"]*)"', entry)
        name = re.search(r',(.*)\n', entry)
        
        # Capture Clearkey/License info
        key_info = re.search(r'license_key="?([^:"\s\n]*):([^"\s\n]*)"?', entry)
        
        lines = [line.strip() for line in entry.split('\n') if line.strip()]
        link = lines[-1] if lines else ""

        k_id, k_val = "", ""
        if key_info:
            k_id, k_val = key_info.groups()

        playlist.append({
            "tvg_id": tvg_id.group(1) if tvg_id else "",
            "name": name.group(1).strip() if name else "Unknown",
            "logo": logo.group(1) if logo else "",
            "keyId": k_id,
            "key": k_val,
            "link": link
        })

    with open("sports.json", "w") as f:
        json.dump(playlist, f, indent=4)

if __name__ == "__main__":
    extract()
