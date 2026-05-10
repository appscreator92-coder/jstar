import os
import re
import requests
import json
import shutil

# Configuration
M3U_URL = "https://raw.githubusercontent.com/rkdyiptv/Playlist/refs/heads/main/Playlist/Cricket.m3u/index.html"
OUTPUT_DIR = "Channel"

if os.path.exists(OUTPUT_DIR):
    shutil.rmtree(OUTPUT_DIR)
os.makedirs(OUTPUT_DIR)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{CHANNEL_TITLE} ({TVG_ID})</title>
<meta name="referrer" content="no-referrer">
<script src="https://cdn.jsdelivr.net/npm/shaka-player@4.16.2/dist/shaka-player.ui.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/shaka-player@4.16.2/dist/controls.css"/>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;background:#000;overflow:hidden;font-family:sans-serif}
.shaka-video-container{position:fixed;inset:0;background:#000;display:flex;align-items:center;justify-content:center}
video{width:100%;height:100%;object-fit:contain}
</style>
</head>
<body>
<div class="shaka-video-container" id="player-container">
<video id="video" autoplay muted playsinline></video>
</div>
<script>
(async () => {
    shaka.polyfill.installAll();
    const video = document.getElementById('video');
    const player = new shaka.Player(video);
    const ui = new shaka.ui.Overlay(player, document.getElementById('player-container'), video);

    const drmConfig = ("{KEY_ID}" && "{KEY}") ? {clearKeys:{"{KEY_ID}":"{KEY}"}} : {};
    player.configure({ drm: drmConfig });

    player.getNetworkingEngine().registerRequestFilter((type, request) => {
        request.headers["Referer"] = "https://www.jiotv.com/";
        request.headers["User-Agent"] = "plaYtv/7.1.5 (Linux;Android 13) ExoPlayerLib/2.11.6";
        const cookie = "{COOKIE}";
        if(cookie) request.headers["Cookie"] = cookie;
    });

    try {
        await player.load("{STREAM_URL}");
    } catch (e) { console.error("Load failed", e); }
})();
</script>
</body>
</html>"""

def generate():
    print(f"Fetching playlist...")
    try:
        response = requests.get(M3U_URL)
        content = response.text
    except Exception as e:
        print(f"Error: {e}")
        return

    lines = content.splitlines()
    channels = []
    
    current_tvg_id = ""
    current_key_id = ""
    current_key = ""
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        # 1. Extract tvg-id from #EXTINF line
        if line.startswith("#EXTINF"):
            tvg_match = re.search(r'tvg-id="([^"]+)"', line)
            current_tvg_id = tvg_match.group(1) if tvg_match else "N/A"
        
        # 2. Extract DRM Keys
        elif 'adaptive.license_key=' in line:
            parts = line.split('adaptive.license_key=')
            if len(parts) > 1:
                keys = parts[1].strip().split(':')
                if len(keys) >= 2:
                    current_key_id, current_key = keys[0], keys[1]
        
        # 3. Extract URL and finalize channel object
        elif line.startswith("https://") and ".mpd" in line:
            parts = line.split('|cookie=')
            url = parts[0].strip()
            cookie = parts[1].strip() if len(parts) > 1 else ""
            
            # Identify name from URL
            match = re.search(r'/bpk-tv/([^/]+)/', url)
            ch_name = match.group(1) if match else "Channel"

            channels.append({
                "name": ch_name,
                "tvg_id": current_tvg_id, # Added this
                "url": url,
                "keyId": current_key_id,
                "key": current_key,
                "cookie": cookie
            })

    for ch in channels:
        safe_name = ch['name'].replace(' ', '_')
        file_path = os.path.join(OUTPUT_DIR, f"{safe_name}.html")
        
        content = HTML_TEMPLATE.replace("{CHANNEL_TITLE}", ch['name'].replace('_', ' ')) \
                               .replace("{TVG_ID}", ch['tvg_id']) \
                               .replace("{STREAM_URL}", ch['url']) \
                               .replace("{KEY_ID}", ch['keyId']) \
                               .replace("{KEY}", ch['key']) \
                               .replace("{COOKIE}", ch['cookie'])
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    with open(os.path.join(OUTPUT_DIR, "channels.json"), "w") as f:
        json.dump(channels, f, indent=2)
    
    print(f"Done! Processed {len(channels)} channels with TVG IDs.")

if __name__ == "__main__":
    generate()
