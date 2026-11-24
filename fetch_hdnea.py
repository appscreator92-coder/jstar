
import json
import re
import ast
import time
import threading

from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# CONFIGURATION
# =========================================================

SOURCE_URL = (
    "https://raw.githubusercontent.com/"
    "appscreator92-coder/index/refs/heads/main/jnew7.json"
)

PROXY_BASE = (
    "https://master-proxy.wispy-boat-fc77.workers.dev/"
)

TARGET_API = (
    "https://b4uplay.com/api/vizha/play.php"
)

OUTPUT_FILE = Path("hdnea_tokens.json")

MAX_WORKERS = 4
TIMEOUT = 30
MAX_RETRIES = 2


# =========================================================
# HEADERS
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/158.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bhoomtv.me/",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


# =========================================================
# THREAD-LOCAL SESSION
# =========================================================

thread_local = threading.local()


def get_session():

    if not hasattr(thread_local, "session"):

        session = requests.Session()

        retry = Retry(
            total=MAX_RETRIES,
            connect=MAX_RETRIES,
            read=MAX_RETRIES,
            status=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[
                429, 500, 502, 503, 504
            ],
            allowed_methods=["GET"],
            respect_retry_after_header=True,
        )

        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=MAX_WORKERS,
            pool_maxsize=MAX_WORKERS,
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        thread_local.session = session

    return thread_local.session


# =========================================================
# BUILD PROXY REQUEST
# =========================================================

def build_api_request(channel_id):

    target_url = (
        TARGET_API
        + "?id="
        + quote(str(channel_id), safe="")
    )

    return PROXY_BASE, {
        "url": target_url
    }


# =========================================================
# JAVASCRIPT STRING EXTRACTION
# =========================================================

JS_STRING = (
    r'("(?:\\.|[^"\\])*"|'
    r"'(?:\\.|[^'\\])*')"
)


def decode_js_string(value):

    if not value:
        return None

    try:

        if value.startswith('"'):
            result = json.loads(value)
        else:
            result = ast.literal_eval(value)

        if isinstance(result, str):
            return result.strip()

    except (ValueError, SyntaxError, json.JSONDecodeError):
        pass

    return None


def extract_js_string(html, variable):

    pattern = re.compile(
        r"\b(?:const|let|var)\s+"
        + re.escape(variable)
        + r"\s*=\s*"
        + JS_STRING,
        re.IGNORECASE | re.DOTALL
    )

    match = pattern.search(html)

    if not match:
        return None

    return decode_js_string(match.group(1))


# =========================================================
# GEO FLAG
# =========================================================

def extract_geo_flag(html):

    pattern = re.compile(
        r"\b(?:const|let|var)\s+"
        r"IS_GEO_BLOCKED\s*=\s*"
        r"(true|false)\b",
        re.IGNORECASE
    )

    match = pattern.search(html)

    if not match:
        return None

    return match.group(1).lower() == "true"


# =========================================================
# EXTRACT PLAYER DATA
# =========================================================

def extract_player_data(html):

    stream_url = extract_js_string(
        html, "STREAM_URL"
    )

    token = extract_js_string(
        html, "hdneaToken"
    )

    fetch_error = extract_js_string(
        html, "fetchError"
    )

    geo_blocked = extract_geo_flag(html)

    if stream_url:
        stream_url = stream_url.replace("\\/", "/")

    if token:
        token = token.replace("\\/", "/")

    return {
        "stream_url": stream_url or "",
        "hdnea_token": token or "",
        "fetch_error": fetch_error or "",
        "geo_blocked": geo_blocked,
    }


# =========================================================
# CLOUDFLARE DETECTION
# =========================================================

def inspect_response(response):

    html = response.text or ""
    lower = html.lower()

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        re.IGNORECASE | re.DOTALL
    )

    title = ""

    if title_match:

        title = re.sub(
            r"\s+", " ",
            title_match.group(1)
        ).strip()

    indicators = [
        "you have been blocked",
        "sorry, you have been blocked",
        "attention required",
        "why have i been blocked",
        "cf-chl-",
        "just a moment",
    ]

    blocked = any(
        item in lower for item in indicators
    )

    return {
        "blocked": blocked,
        "title": title,
        "ray_id": response.headers.get("CF-RAY", ""),
        "content_type": response.headers.get("Content-Type", ""),
        "response_length": len(html),
    }


# =========================================================
# BUILD FINAL STREAM URL
# =========================================================

def build_final_url(stream_url, token):

    if not stream_url:
        return None

    if not stream_url.startswith(
        ("https://", "http://")
    ):
        return None

    # Already contains HDNEA token.

    if "__hdnea__=" in stream_url:
        return stream_url

    # Separate token is required otherwise.

    if not token:
        return None

    if not token.startswith("__hdnea__="):

        token = "__hdnea__=" + token.lstrip("?&")

    separator = (
        "&" if "?" in stream_url else "?"
    )

    return stream_url + separator + token


# =========================================================
# LOAD SOURCE JSON
# =========================================================

def load_channels():

    print("Downloading source channel JSON...")

    response = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "application/json",
        },
        timeout=TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):

        channels = data

    elif isinstance(data, dict):

        channels = None

        for key in (
            "channels",
            "data",
            "items",
            "list"
        ):

            if isinstance(data.get(key), list):
                channels = data[key]
                break

        if channels is None:
            raise ValueError(
                "Channel array not found in source JSON"
            )

    else:

        raise ValueError(
            "Unexpected source JSON structure"
        )

    valid_channels = []

    for item in channels:

        if not isinstance(item, dict):
            continue

        channel_id = str(
            item.get("id", "")
        ).strip()

        if not channel_id:
            continue

        channel_name = str(
            item.get("name", channel_id)
        ).strip()

        valid_channels.append({
            "id": channel_id,
            "name": channel_name,
        })

    print("Total channels:", len(valid_channels))

    return valid_channels


# =========================================================
# FETCH ONE CHANNEL
# =========================================================

def fetch_channel(index, channel):

    channel_id = channel["id"]
    channel_name = channel["name"]

    try:

        session = get_session()

        proxy_url, proxy_params = build_api_request(
            channel_id
        )

        response = session.get(
            proxy_url,
            params=proxy_params,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        http_code = response.status_code
        html = response.text or ""

        diagnostics = inspect_response(response)

        # Cloudflare challenge.

        if diagnostics["blocked"]:

            error = "Cloudflare blocked the request"

            if diagnostics["ray_id"]:
                error += (
                    " (Ray ID: "
                    + diagnostics["ray_id"]
                    + ")"
                )

            return index, False, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": http_code,
                "error": error,
                "final_url": None,
            }

        response.raise_for_status()

        # Extract JavaScript values.

        player = extract_player_data(html)

        # Explicit geo restriction.

        if player["geo_blocked"] is True:

            return index, False, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": http_code,
                "error": "IS_GEO_BLOCKED is true",
                "final_url": None,
            }

        # Build stream URL.

        final_url = build_final_url(
            player["stream_url"],
            player["hdnea_token"]
        )

        if final_url:

            return index, True, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "success",
                "http_code": http_code,
                "final_url": final_url,
            }

        # Classify errors.

        if player["fetch_error"]:

            error = player["fetch_error"]

        elif not player["stream_url"]:

            error = "STREAM_URL not found"

        elif (
            not player["hdnea_token"]
            and "__hdnea__=" not in player["stream_url"]
        ):

            error = "HDNEA token not found"

        else:

            error = "Invalid stream URL"

        # Diagnostics for first three channels.

        if index < 3:

            print(
                "\n========== DIAGNOSTICS =========="
            )

            print("Channel:", channel_name)
            print("ID:", channel_id)
            print("HTTP status:", http_code)
            print("Response URL:", response.url)
            print("Page title:", diagnostics["title"])
            print(
                "Content-Type:",
                diagnostics["content_type"]
            )
            print(
                "Response length:",
                diagnostics["response_length"]
            )
            print(
                "Cloudflare Ray ID:",
                diagnostics["ray_id"]
            )
            print(
                "Geo flag:",
                player["geo_blocked"]
            )
            print(
                "STREAM_URL found:",
                bool(player["stream_url"])
            )
            print(
                "HDNEA token found:",
                bool(player["hdnea_token"])
            )
            print(
                "fetchError:",
                player["fetch_error"]
            )

            print(
                "================================\n"
            )

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": http_code,
            "error": error,
            "final_url": player["stream_url"] or None,
        }

    except requests.HTTPError as exc:

        status = (
            exc.response.status_code
            if exc.response is not None
            else None
        )

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": status,
            "error": str(exc),
            "final_url": None,
        }

    except requests.RequestException as exc:

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
            "final_url": None,
        }

    except Exception as exc:

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
            "final_url": None,
        }


# =========================================================
# SAVE JSON ATOMICALLY
# =========================================================

def save_json(output):

    temp_file = OUTPUT_FILE.with_suffix(".tmp")

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )

    temp_file.replace(OUTPUT_FILE)


# =========================================================
# MAIN
# =========================================================

def main():

    start_time = time.time()

    channels = load_channels()

    total = len(channels)

    results = []

    print("\nStarting channel extraction...")
    print("Proxy:", PROXY_BASE)
    print("Target API:", TARGET_API)
    print("Workers:", MAX_WORKERS)
    print("Total channels:", total)

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                fetch_channel,
                index,
                channel
            )
            for index, channel in enumerate(channels)
        ]

        completed = 0

        for future in as_completed(futures):

            index, success, record = future.result()

            results.append(
                (index, success, record)
            )

            completed += 1

            print(
                f"[{completed}/{total}] "
                f"{record['channel_name']} - "
                f"{record['status']}"
            )

    # Preserve original source order.

    results.sort(
        key=lambda item: item[0]
    )

    successful_results = []
    failed_results = []

    for _, success, record in results:

        if success:
            successful_results.append(record)
        else:
            failed_results.append(record)

    output = {
        "source_url": SOURCE_URL,
        "total_channels": total,
        "successful_channels": len(successful_results),
        "failed_channels": len(failed_results),
        "timestamp": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": successful_results,
        "failed_results": failed_results,
    }

    save_json(output)

    elapsed = time.time() - start_time

    print("\n========== FINAL SUMMARY ==========")
    print("Total channels:", total)
    print("Successful:", len(successful_results))
    print("Failed:", len(failed_results))
    print("Time taken:", round(elapsed, 2), "seconds")
    print("Output:", OUTPUT_FILE)
    print("===================================")


if __name__ == "__main__":
    main()
