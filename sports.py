import requests
import re
import json

def extract_m3u_to_json(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        content = response.text
    except Exception as e:
        return f"Error fetching URL: {e}"

    playlist = []
    # Split by #EXTINF to process each channel block
    entries = content.split("#EXTINF")
    
    for entry in entries:
        if not entry.strip() or entry.startswith("#EXTM3U"):
            continue

        # Standard Attributes
        tvg_id = re.search(r'tvg-id="([^"]*)"', entry)
        logo = re.search(r'tvg-logo="([^"]*)"', entry)
        name = re.search(r',(.*)\n', entry)
        
        # Key and KeyID (Commonly found in #KODIPROP or inline attributes)
        # This regex looks for the pattern keyid:key or specific license_key tags
        key_info = re.search(r'license_key="([^:]*):([^"]*)"', entry)
        # Alternative: look for KODIPROP lines if they exist in the entry
        kodiprop_key = re.search(r'license_key=([^:\s\n]*):([^\s\n]*)', entry)

        # Extracting the link (the last non-empty line)
        lines = [line.strip() for line in entry.split('\n') if line.strip()]
        stream_link = lines[-1] if lines else ""

        # Determine KeyID and Key
        k_id, k_val = "", ""
        if key_info:
            k_id, k_val = key_info.groups()
        elif kodiprop_key:
            k_id, k_val = kodiprop_key.groups()

        channel_data = {
            "tvg_id": tvg_id.group(1) if tvg_id else "",
            "name": name.group(1).strip() if name else "Unknown",
            "logo": logo.group(1) if logo else "",
            "keyId": k_id,
            "key": k_val,
            "link": stream_link
        }
        playlist.append(channel_data)

    return json.dumps(playlist, indent=4)

url = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u"
print(extract_m3u_to_json(url))
