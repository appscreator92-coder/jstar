import requests
import os

def generate_playlist():
    json_url = os.environ.get("RKDY_CRIC")
    if not json_url:
        return

    try:
        response = requests.get(json_url)
        data = response.json()
        
        # 1. Redirect Script (Browser ke liye)
        content = "<script>\nwindow.location.href = \"https://telegram.me/rkdyiptv\";\n</script>\n"
        
        # 2. Credit line (Aage # lagaya hai taaki player error na de)
        content += "#Credit: RKDYIPTV\n\n"
        
        # 3. Playlist Start
        content += "#EXTM3U\n"

        for channel in data:
            name = channel.get("channel_name", "Unknown")
            logo = channel.get("channel_logo", "")
            cid = channel.get("channel_id", "")
            genre = channel.get("channel_genre", "Sports")
            base_url = channel.get("channel_url")
            cookie = channel.get("cookie", "")
            keyId = channel.get("keyId", "")
            key = channel.get("key", "")

            if base_url and str(base_url).lower() != "none":
                # Kodi Standard Format
                content += f'#EXTINF:-1 tvg-id="{cid}" tvg-logo="{logo}" group-title="{genre}",{name}\n'
                content += '#KODIPROP:inputstream.adaptive.license_type=clearkey\n'
                content += f'#KODIPROP:inputstream.adaptive.license_key={keyId}:{key}\n'
                # Link format
                content += f"{base_url}|cookie={cookie}\n\n"

        # Folder setting
        target_dir = "Playlist/Cricket.m3u"
        os.makedirs(target_dir, exist_ok=True)
        
        # Saving as index.html
        with open(f"{target_dir}/index.html", "w", encoding="utf-8") as f:
            f.write(content)
            
    except Exception:
        pass

if __name__ == "__main__":
    generate_playlist()
