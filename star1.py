from datetime import datetime
import json
import requests
from zoneinfo import ZoneInfo  # Python 3.9+


def main():
    api_url = "https://pllive.bmera5952.workers.dev/"

    try:
        response = requests.get(api_url, timeout=10)
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

    for ch in channels:
        channel_id = ch.get("id")
        channel_name = ch.get("name")
        base_url = ch.get("mpd_url")
        license_url = ch.get("license_url")
        user_agent = ch.get("user_agent")
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
            "group": ch.get("group"),
            "logo": ch.get("logo"),
            "type": ch.get("type"),
            "status": "success",
            "http_code": 200,
            "final_url": final_url,
            "license_url": license_url,
            "user_agent": user_agent,
            "headers": headers
        })

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

    print(json.dumps(output_data, indent=4))


if __name__ == "__main__":
    main()
