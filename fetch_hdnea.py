
import json
import re
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ---------------- CONFIGURATION ----------------

SOURCE_URL = (
    "https://raw.githubusercontent.com/appscreator92-coder/"
    "index/refs/heads/main/jnew7.json"
)

PROXY_URL = "https://allinborn-proxy.asifansaribr.workers.dev/"
API_URL = "https://b4uplay.com/api/vizha/play.php"

OUTPUT_FILE = "hdnea_tokens.json"

MAX_WORKERS = 5
REQUEST_TIMEOUT = 30
RETRY_COUNT = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}

# ---------------- HELPERS ----------------

session = requests.Session()
session.headers.update(HEADERS)


def get_source_channels():
    response = session.get(SOURCE_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list):
        raise ValueError("Source JSON must contain a list of channels.")

    channels = []

    for item in data:
        if not isinstance(item, dict):
            continue

        channel_id = str(item.get("id", "")).strip()
        channel_name = str(item.get("name", channel_id)).strip()

        if channel_id:
            channels.append({
                "id": channel_id,
                "name": channel_name
            })

    return channels


def extract_variable(html, variable):
    patterns = [
        rf'\b{variable}\s*=\s*["\']([^"\']*)["\']',
        rf'\b{variable}\s*:\s*["\']([^"\']*)["\']',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def extract_boolean(html, variable):
    match = re.search(
        rf'\b{variable}\s*[:=]\s*(true|false)',
        html,
        re.IGNORECASE
    )

    if match:
        return match.group(1).lower() == "true"

    return None


def fetch_channel(channel):
    channel_id = channel["id"]
    channel_name = channel["name"]

    target_url = f"{API_URL}?id={channel_id}"

    for attempt in range(RETRY_COUNT + 1):
        try:
            response = session.get(
                PROXY_URL,
                params={"url": target_url},
                timeout=REQUEST_TIMEOUT
            )

            http_code = response.status_code
            response.raise_for_status()

            html = response.text

            geo_blocked = extract_boolean(
                html, "IS_GEO_BLOCKED"
            )

            stream_url = extract_variable(
                html, "STREAM_URL"
            )

            fetch_error = extract_variable(
                html, "fetchError"
            )

            # Never report geo-blocked streams as successful.
            if geo_blocked is True:
                return {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "failed",
                    "http_code": http_code,
                    "error": fetch_error or "Geo restricted"
                }

            if not stream_url:
                return {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "failed",
                    "http_code": http_code,
                    "error": fetch_error or "Stream URL not found"
                }

            if not stream_url.startswith(("http://", "https://")):
                return {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "failed",
                    "http_code": http_code,
                    "error": "Invalid stream URL"
                }

            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "success",
                "http_code": http_code,
                "final_url": stream_url
            }

        except requests.RequestException as error:
            if attempt < RETRY_COUNT:
                time.sleep(2)
                continue

            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": getattr(
                    getattr(error, "response", None),
                    "status_code",
                    0
                ),
                "error": str(error)
            }

        except Exception as error:
            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": 0,
                "error": str(error)
            }


# ---------------- MAIN ----------------

def main():
    print("Fetching channel list...")

    channels = get_source_channels()
    total = len(channels)

    print(f"Total channels: {total}")

    successful_results = []
    failed_results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(fetch_channel, channel): channel
            for channel in channels
        }

        completed = 0

        for future in as_completed(futures):
            result = future.result()
            completed += 1

            if result["status"] == "success":
                successful_results.append(result)
                print(
                    f"[{completed}/{total}] SUCCESS: "
                    f"{result['channel_name']}"
                )
            else:
                failed_results.append(result)
                print(
                    f"[{completed}/{total}] FAILED: "
                    f"{result['channel_name']} - "
                    f"{result.get('error', 'Unknown error')}"
                )

    # Keep results in the same order as the source channel list.
    source_order = {
        channel["id"]: index
        for index, channel in enumerate(channels)
    }

    successful_results.sort(
        key=lambda x: source_order.get(x["channel_id"], 999999)
    )

    failed_results.sort(
        key=lambda x: source_order.get(x["channel_id"], 999999)
    )

    output = {
        "source_url": SOURCE_URL,
        "total_channels": total,
        "successful_channels": len(successful_results),
        "failed_channels": len(failed_results),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": successful_results,
        "failed_results": failed_results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("\n---------------- SUMMARY ----------------")
    print(f"Total:      {total}")
    print(f"Successful: {len(successful_results)}")
    print(f"Failed:     {len(failed_results)}")
    print(f"Output:     {OUTPUT_FILE}")
    print("------------------------------------------")


if __name__ == "__main__":
    main()
