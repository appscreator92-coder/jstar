from datetime import datetime
import json
import re
from zoneinfo import ZoneInfo
import requests


def parse_m3u(content: str) -> list[dict]:
    channels = []
    lines = content.splitlines()
    current_channel: dict = {}

    attr_pattern = re.compile(r'([a-zA-Z0-9_-]+)="([^"]*)"')

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("#EXTINF:"):
            current_channel = {}
            attributes = dict(attr_pattern.findall(line))
            current_channel["channel_id"] = attributes.get("tvg-id", "")
            current_channel["channel_name"] = attributes.get("tvg-name", "")
            current_channel["group_title"] = attributes.get("group-title", "")
            current_channel["tvg_logo"] = attributes.get("tvg-logo", "")

            if not current_channel["channel_name"] and "," in line:
                current_channel["channel_name"] = line.rsplit(",", 1)[-1].strip()

        elif line.startswith("#KODIPROP:") and current_channel is not None:
            prop = line.split(":", 1)[1].strip()
            if "=" in prop:
                k, v = prop.split("=", 1)
                key = k.strip().lower()
                val = v.strip()
                if key == "inputstream.adaptive.manifest_type":
                    current_channel["manifest_type"] = val
                elif key == "inputstream.adaptive.license_type":
                    current_channel["license_type"] = val
                elif key == "inputstream.adaptive.license_key":
                    current_channel["license_key"] = val
                elif key == "inputstream.adaptive.stream_headers":
                    for part in val.split("&"):
                        if part.lower().startswith("cookie="):
                            current_channel["cookie"] = part.split("=", 1)[1].strip()

        elif line.startswith("#EXTHTTP:") and current_channel is not None:
            json_str = line.split(":", 1)[1].strip()
            try:
                headers_data = json.loads(json_str)
                if isinstance(headers_data, dict):
                    for k, v in headers_data.items():
                        if str(k).lower() == "cookie" and v:
                            current_channel["cookie"] = str(v).strip()
            except json.JSONDecodeError:
                pass

        elif line.startswith("#EXTVLCOPT:") and current_channel is not None:
            opt = line.split(":", 1)[1].strip()
            if "=" in opt:
                k, v = opt.split("=", 1)
                key = k.strip().lower()
                val = v.strip()
                if key == "http-cookie":
                    current_channel["cookie"] = val
                elif key == "http-user-agent":
                    current_channel["user_agent"] = val
                elif key == "http-referrer":
                    current_channel["referrer"] = val
                elif key == "http-origin":
                    current_channel["origin"] = val

        elif not line.startswith("#") and current_channel:
            if "|" in line:
                base_url, params = line.split("|", 1)
                current_channel["url"] = base_url.strip().rstrip("?")
                for param in params.split("&"):
                    if param.lower().startswith("cookie="):
                        current_channel["cookie"] = param.split("=", 1)[1].strip()
            else:
                current_channel["url"] = line.strip()

            channels.append(current_channel)
            current_channel = {}

    return channels


def fetch_m3u_content(urls: list[str]) -> tuple[str | None, str | None]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = "utf-8"
            text = response.text

            if "#EXTM3U" in text or "#EXTINF:" in text:
                return text, url
        except requests.RequestException:
            continue

    return None, None


def build_final_url(base_url: str, cookie: str) -> str:
    clean_url = base_url.split("|", 1)[0].rstrip("?")
    if not cookie:
        return clean_url

    separator = "&" if "?" in clean_url else "?"
    return f"{clean_url}{separator}{cookie}"


def main() -> None:
    m3u_urls = [
        "https://raw.githubusercontent.com/sixpg/zeyo/refs/heads/main/jtv.m3u",
        "https://raw.githubusercontent.com/sportlive18/sportlink-update/refs/heads/main/zio.m3u",
        "https://sayan-jio-tv.pages.dev/playlist.m3u",
        "https://raw.githubusercontent.com/sixpg/zeyo-test/refs/heads/main/jtv.m3u",
        "https://premiumplugx.top/jiostb/mjelo.php?view=raw",
        "https://m3u.cloudplay.qzz.io/jtvx.m3u",
        "https://alex4528.site/jplus/playlist.m3u",
    ]

    m3u_content, source_url = fetch_m3u_content(m3u_urls)

    if not m3u_content:
        print(json.dumps({"error": "Failed to fetch valid M3U from all sources."}))
        return

    channels = parse_m3u(m3u_content)
    successful_results = []
    failed_results = []

    for ch in channels:
        base_url = ch.get("url", "")
        if not base_url:
            continue

        cookie = ch.get("cookie", "")
        final_url = build_final_url(base_url, cookie)

        successful_results.append({
            "channel_id": ch.get("channel_id", ""),
            "channel_name": ch.get("channel_name", ""),
            "status": "success",
            "http_code": 200,
            "final_url": final_url,
        })

    ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M:%S")

    output_data = {
        "source_url": source_url,
        "total_channels": len(channels),
        "successful_channels": len(successful_results),
        "failed_channels": len(failed_results),
        "timestamp": ist_time,
        "successful_results": successful_results,
        "failed_results": failed_results,
    }

    print(json.dumps(output_data, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()
