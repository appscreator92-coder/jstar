from datetime import datetime
import json
import os
import requests
from zoneinfo import ZoneInfo


def main():
    api_url = "https://pllive.bmera5952.workers.dev/"

    try:
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        channels = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching API data: {e}")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return

    successful_results = []
    failed_results = []
    m3u_lines = ["#EXTM3U"]

    for ch in channels:
        channel_id = ch.get("id")
        channel_name = ch.get("name")
        group = ch.get("group", "General")
        logo = ch.get("logo", "")
        base_url = ch.get("mpd_url")
        license_url = ch.get("license_url")
        user_agent = ch.get("user_agent", "")
        headers = ch.get("headers", {})
        cookie = headers.get("cookie", "")

        if not base_url:
            failed_results.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "reason": "Missing mpd_url"
            })
            continue

        if cookie and "?" in base_url:
            final_url = f"{base_url}&{cookie}"
        elif cookie:
            final_url = f"{base_url}?{cookie}"
        else:
            final_url = base_url

        successful_results.append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "group": group,
            "logo": logo,
            "type": ch.get("type", "dash"),
            "status": "success",
            "http_code": 200,
            "final_url": final_url,
            "license_url": license_url,
            "user_agent": user_agent,
            "headers": headers
        })

        # Generate M3U playlist entry with DRM properties if available
        m3u_lines.append(
            f'#EXTINF:-1 tvg-id="{channel_id}" tvg-logo="{logo}" group-title="{group}",{channel_name}'
        )
        if user_agent:
            m3u_lines.append(f"#EXTVLCOPT:http-user-agent={user_agent}")
        if license_url:
            m3u_lines.append(f"#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            m3u_lines.append(f"#KODIPROP:inputstream.adaptive.license_key={license_url}")
        m3u_lines.append(final_url)

    # Get current time explicitly set to Indian Standard Time (IST)
    ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    output_data = {
        "total_channels": len(channels),
        "successful_channels": len(successful_results),
        "failed_channels": len(failed_results),
        "timestamp": ist_time,
        "successful_results": successful_results,
        "failed_results": failed_results,
    }

    # Save output to JSON file (ideal for GitHub Actions artifact/commit)
    json_filename = "channels.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=4)
    print(f"Successfully saved JSON output to {json_filename}")

    # Save output to M3U playlist file
    m3u_filename = "playlist.m3u"
    with open(m3u_filename, "w", encoding="utf-8") as f:
        f.write("\n".join(m3u_lines))
    print(f"Successfully saved M3U playlist to {m3u_filename}")


if __name__ == "__main__":
    main()
