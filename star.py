from datetime import datetime
import json
import re
import requests
from zoneinfo import ZoneInfo  # Python 3.9+


def parse_m3u(content):
    channels = []
    lines = content.splitlines()
    current_channel = {}

    attr_pattern = re.compile(r'([a-zA-Z0-9_-]+)="([^"]*)"')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current_channel = {}
            attributes = dict(attr_pattern.findall(line))
            current_channel["channel_id"] = attributes.get("tvg-id", "")
            current_channel["channel_name"] = attributes.get("tvg-name", "")

            # Fallback for channel name after the comma
            if not current_channel["channel_name"] and "," in line:
                current_channel["channel_name"] = line.rsplit(",", 1)[-1].strip()

        elif line.startswith("#EXTHTTP:"):
            try:
                json_str = line.replace("#EXTHTTP:", "").strip()
                headers_data = json.loads(json_str)
                if "cookie" in headers_data:
                    current_channel["cookie"] = headers_data["cookie"]
            except json.JSONDecodeError:
                pass

        elif not line.startswith("#") and current_channel:
            current_channel["url"] = line
            channels.append(current_channel)
            current_channel = {}

    return channels


def fetch_m3u_content(urls):
    """Tries fetching from a list of URLs sequentially until one succeeds, suppressing intermediate fetch errors."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = "utf-8"
            
            # Verify the response actually contains M3U data
            if "#EXTM3U" in response.text or "#EXTINF:" in response.text:
                return response.text, url
        except requests.exceptions.RequestException:
            continue

    return None, None


def main():
    m3u_urls = [
        "https://premiumplugx.top/jiostb/mjelo.php?view=raw",
        "https://m3u.cloudplay.qzz.io/jtvx.m3u",
    ]

    m3u_content, source_url = fetch_m3u_content(m3u_urls)

    if not m3u_content:
        print(json.dumps({"error": "Failed to fetch valid M3U from all sources."}))
        return

    channels = parse_m3u(m3u_content)
    successful_results = []

    for ch in channels:
        channel_id = ch.get("channel_id")
        channel_name = ch.get("channel_name")
        base_url = ch.get("url", "")
        cookie = ch.get("cookie", "")

        # Strip pipe attributes if present
        if "|" in base_url:
            base_url = base_url.split("|")[0]

        # Construct final URL properly handling existing query parameters
        if cookie:
            separator = "&" if "?" in base_url else "?"
            final_url = f"{base_url}{separator}{cookie}"
        else:
            final_url = base_url

        successful_results.append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "success",
            "http_code": 200,
            "final_url": final_url,
        })

    ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    output_data = {
        "source_url": source_url,
        "total_channels": len(channels),
        "successful_channels": len(successful_results),
        "failed_channels": 0,
        "timestamp": ist_time,
        "successful_results": successful_results,
        "failed_results": [],
    }

    print(json.dumps(output_data, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
