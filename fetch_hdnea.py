import argparse
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

# ---------------- CONFIGURATION ----------------

SOURCE_URL = os.getenv(
    "SOURCE_URL",
    (
        "https://raw.githubusercontent.com/appscreator92-coder/"
        "index/refs/heads/main/jnew7.json"
    ),
)

PROXY_URL = os.getenv(
    "PROXY_URL",
    "https://allinborn-proxy.asifansaribr.workers.dev/",
)
INDIA_PROXY_URL = os.getenv("INDIA_PROXY_URL", "").strip()
DIRECT_MODE = os.getenv("DIRECT_MODE", "").strip().lower() in ("1", "true", "yes")

OUTPUT_FILE = os.getenv("OUTPUT_FILE", "hdnea_tokens.json")
IST_TZ = ZoneInfo("Asia/Kolkata")

MAX_WORKERS = int(os.getenv("MAX_WORKERS", "5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
RETRY_COUNT = int(os.getenv("RETRY_COUNT", "2"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}

_thread_local = threading.local()


def get_session() -> requests.Session:
    if not hasattr(_thread_local, "session"):
        sess = requests.Session()
        sess.headers.update(HEADERS)
        _thread_local.session = sess
    return _thread_local.session


def close_all_sessions():
    if hasattr(_thread_local, "session"):
        _thread_local.session.close()


def get_ist_timestamp() -> str:
    return datetime.now(IST_TZ).strftime("%Y-%m-%d %H:%M:%S IST")


# ---------------- HELPERS ----------------

def get_source_channels():
    response = requests.get(SOURCE_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
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
                "name": channel_name,
            })

    return channels


def extract_variable(content: str, variable: str) -> str:
    patterns = [
        rf'\b{re.escape(variable)}\s*=\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
        rf"\b{re.escape(variable)}\s*=\s*'([^'\\]*(?:\\.[^'\\]*)*)'",
        rf'\b{re.escape(variable)}\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"',
        rf"\b{re.escape(variable)}\s*:\s*'([^'\\]*(?:\\.[^'\\]*)*)'",
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1).strip()

    return ""


def extract_boolean(content: str, variable: str):
    match = re.search(
        rf"\b{re.escape(variable)}\s*[:=]\s*(true|false)\b",
        content,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).lower() == "true"
    return None


def request_via_endpoint(target_url: str, proxy_endpoint: str, direct: bool) -> requests.Response:
    session = get_session()
    if direct or not proxy_endpoint:
        return session.get(target_url, timeout=REQUEST_TIMEOUT)
    return session.get(proxy_endpoint, params={"url": target_url}, timeout=REQUEST_TIMEOUT)


def evaluate_response(channel: dict, response: requests.Response) -> dict:
    channel_id = channel["id"]
    channel_name = channel["name"]
    http_code = response.status_code
    body = response.text

    geo_blocked = extract_boolean(body, "IS_GEO_BLOCKED")
    stream_url = extract_variable(body, "STREAM_URL")
    fetch_error = extract_variable(body, "fetchError")

    if geo_blocked is True:
        return {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "geo_blocked",
            "http_code": http_code,
            "error": fetch_error or "Geo restricted",
        }

    if not stream_url:
        return {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": http_code,
            "error": fetch_error or "Stream URL not found",
        }

    if not stream_url.startswith(("http://", "https://")):
        return {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": http_code,
            "error": "Invalid stream URL",
        }

    return {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "status": "success",
        "http_code": http_code,
        "final_url": stream_url,
    }


def fetch_with_retries(channel: dict, target_url: str, proxy_endpoint: str, direct: bool) -> dict:
    channel_id = channel["id"]
    channel_name = channel["name"]

    for attempt in range(RETRY_COUNT + 1):
        try:
            response = request_via_endpoint(target_url, proxy_endpoint, direct)
            response.raise_for_status()
            return evaluate_response(channel, response)

        except requests.RequestException as error:
            if attempt < RETRY_COUNT:
                time.sleep(2 ** attempt)
                continue

            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": getattr(
                    getattr(error, "response", None),
                    "status_code",
                    0,
                ),
                "error": str(error),
            }

        except Exception as error:
            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": 0,
                "error": str(error),
            }


def fetch_channel(channel: dict, india_proxy: str, direct: bool) -> dict:
    target_url = f"https://b4uplay.com/api/vizha/play.php?id={channel['id']}"
    result = fetch_with_retries(channel, target_url, PROXY_URL, direct)

    if result["status"] == "geo_blocked" and india_proxy:
        fallback_result = fetch_with_retries(channel, target_url, india_proxy, direct=False)
        fallback_result["used_india_fallback"] = True
        return fallback_result

    return result


# ---------------- MAIN ----------------

def parse_args():
    parser = argparse.ArgumentParser(description="Fetch channel stream URLs.")
    parser.add_argument(
        "--direct",
        action="store_true",
        default=DIRECT_MODE,
        help="Call target URL directly instead of using PROXY_URL (useful when running locally on an Indian IP).",
    )
    parser.add_argument(
        "--india-proxy",
        default=INDIA_PROXY_URL,
        help="Fallback proxy endpoint routed through India for geo-blocked channels.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("Fetching channel list...")
    channels = get_source_channels()
    total = len(channels)
    print(f"Total channels: {total}")
    print(f"Mode: {'DIRECT' if args.direct else 'PROXY'} | India fallback configured: {bool(args.india_proxy)}")

    successful_results = []
    geo_blocked_results = []
    failed_results = []

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(fetch_channel, channel, args.india_proxy, args.direct): channel
                for channel in channels
            }

            completed = 0
            for future in as_completed(futures):
                result = future.result()
                completed += 1
                status = result["status"]

                if status == "success":
                    successful_results.append(result)
                    print(f"[{completed}/{total}] SUCCESS: {result['channel_name']}")
                elif status == "geo_blocked":
                    geo_blocked_results.append(result)
                    print(
                        f"[{completed}/{total}] GEO_BLOCKED: {result['channel_name']} - "
                        f"{result.get('error', 'Geo restricted')}"
                    )
                else:
                    failed_results.append(result)
                    print(
                        f"[{completed}/{total}] FAILED: {result['channel_name']} - "
                        f"{result.get('error', 'Unknown error')}"
                    )
    finally:
        close_all_sessions()

    source_order = {
        channel["id"]: index
        for index, channel in enumerate(channels)
    }

    successful_results.sort(key=lambda x: source_order.get(x["channel_id"], 999999))
    geo_blocked_results.sort(key=lambda x: source_order.get(x["channel_id"], 999999))
    failed_results.sort(key=lambda x: source_order.get(x["channel_id"], 999999))

    ist_now = get_ist_timestamp()

    output = {
        "source_url": SOURCE_URL,
        "total_channels": total,
        "successful_channels": len(successful_results),
        "geo_blocked_channels": len(geo_blocked_results),
        "failed_channels": len(failed_results),
        "timestamp": ist_now,
        "successful_results": successful_results,
        "geo_blocked_results": geo_blocked_results,
        "failed_results": failed_results,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(output, file, indent=4, ensure_ascii=False)

    print("\n---------------- SUMMARY ----------------")
    print(f"Timestamp:   {ist_now}")
    print(f"Total:       {total}")
    print(f"Successful:  {len(successful_results)}")
    print(f"Geo Blocked: {len(geo_blocked_results)}")
    print(f"Failed:      {len(failed_results)}")
    print(f"Output:      {OUTPUT_FILE}")
    print("------------------------------------------")


if __name__ == "__main__":
    main()
