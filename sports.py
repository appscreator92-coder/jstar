import requests
import re
import json

def extract():
    url = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u"
    
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        print(f"Error fetching data: {e}")
        return

    playlist = []
    entries = content.split("#EXTINF")
    
    for entry in entries:
        if not entry.strip() or entry.startswith("#EXTM3U"):
            continue

        # Attributes
        tvg_id = re.search(r'tvg-id="([^"]*)"', entry)
        logo = re.search(r'tvg-logo="([^"]*)"', entry)
        name = re.search(r',([^,\n\r]+)(?:\r?\n|$)', entry)
        
        # DRM/Clearkey
        key_info = re.search(r'license_key=["\']?([^:"\'\s\n]*):([^"\'\s\n]*)["\']?', entry)
        
        # Stream Link
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

    # Only write to file if data was actually found
    if playlist:
        with open("sports.json", "w", encoding='utf-8') as f:
            json.dump(playlist, f, indent=4, ensure_ascii=False)
        print(f"Extraction successful: {len(playlist)} channels saved.")
    else:
        print("No data extracted. File not updated.")

if __name__ == "__main__":
    extract()
