
import json
import re
import time
import ast
import threading
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs

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

API_URL = "https://b4uplay.com/api/vizha/play.php"

OUTPUT_FILE = "hdnea_tokens.json"

MAX_WORKERS = 12
TIMEOUT = 30
MAX_RETRIES = 3

thread_local = threading.local()


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
    "Upgrade-Insecure-Requests": "1",
}


# =========================================================
# REGEX
# =========================================================

JS_STRING = r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')"""

STREAM_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+STREAM_URL\s*=\s*"
    + JS_STRING,
    re.IGNORECASE | re.DOTALL
)

TOKEN_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+hdneaToken\s*=\s*"
    + JS_STRING,
    re.IGNORECASE | re.DOTALL
)

ERROR_PATTERN = re.compile(
    r"\b(?:const|let|var)\s+fetchError\s*=\s*"
    + JS_STRING,
    re.IGNORECASE | re.DOTALL
)


# =========================================================
# THREAD SESSION
# =========================================================

def get_session():

    if not hasattr(thread_local, "session"):

        session = requests.Session()

        retry = Retry(
            total=MAX_RETRIES,
            connect=MAX_RETRIES,
            read=MAX_RETRIES,
            status=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
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
# DECODE JAVASCRIPT STRING
# =========================================================

def decode_js_string(value):

    try:
        return ast.literal_eval(value)

    except Exception:
        return value[1:-1]


# =========================================================
# EXTRACT JAVASCRIPT VARIABLE
# =========================================================

def extract_variable(pattern, html):

    match = pattern.search(html)

    if not match:
        return ""

    return decode_js_string(match.group(1)).strip()


# =========================================================
# EXTRACT STREAM AND TOKEN
# =========================================================

def extract_stream(html):

    stream_url = extract_variable(
        STREAM_PATTERN, html
    )

    hdnea_token = extract_variable(
        TOKEN_PATTERN, html
    )

    fetch_error = extract_variable(
        ERROR_PATTERN, html
    )

    stream_url = stream_url.replace("\\/", "/")

    # If the URL already has the token, preserve it.

    if stream_url and "__hdnea__=" in stream_url:
        return stream_url, hdnea_token, fetch_error

    # Otherwise append the separately extracted token.

    if stream_url and hdnea_token:

        token = hdnea_token

        if not token.startswith("__hdnea__="):
            token = "__hdnea__=" + token

        separator = "&" if "?" in stream_url else "?"

        stream_url += separator + token

    # Last fallback: obtain token from URL query.

    if stream_url and "__hdnea__=" in stream_url:

        return stream_url, hdnea_token, fetch_error

    return stream_url, hdnea_token, fetch_error


# =========================================================
# LOAD CHANNELS FROM jnew7.json
# =========================================================

def load_channels():

    print("Downloading channel JSON...")

    response = requests.get(
        SOURCE_URL,
        timeout=TIMEOUT,
        headers={"User-Agent": HEADERS["User-Agent"]}
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        channels = data

    elif isinstance(data, dict):

        channels = None

        for key in ("channels", "data", "items", "list"):

            if isinstance(data.get(key), list):
                channels = data[key]
                break

        if channels is None:
            raise ValueError(
                "Could not find channel list in jnew7.json"
            )

    else:
        raise ValueError("Invalid JSON format")

    valid = []

    for channel in channels:

        if not isinstance(channel, dict):
            continue

        channel_id = str(channel.get("id", "")).strip()

        if not channel_id:
            continue

        valid.append({
            "id": channel_id,
            "name": str(
                channel.get("name", channel_id)
            ).strip()
        })

    print("Channels found:", len(valid))

    return valid


# =========================================================
# FETCH ONE CHANNEL
# =========================================================

def fetch_channel(index, channel):

    channel_id = channel["id"]
    channel_name = channel["name"]

    try:

        session = get_session()

        response = session.get(
            API_URL,
            params={"id": channel_id},
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        response.raise_for_status()

        html = response.text

        stream_url, token, fetch_error = extract_stream(html)

        # A valid result must contain a complete stream URL
        # with an HDNEA token.

        has_token = (
            bool(token)
            or (
                bool(stream_url)
                and "__hdnea__=" in stream_url
            )
        )

        if stream_url and has_token:

            if "__hdnea__=" not in stream_url:
                raise ValueError(
                    "Token was found but URL has no HDNEA parameter"
                )

            return index, True, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "success",
                "http_code": response.status_code,
                "final_url": stream_url,
            }

        # Print diagnostics for the first few failed responses.

        if index < 3:

            print("\n========== RESPONSE DEBUG ==========")
            print("Channel:", channel_name)
            print("ID:", channel_id)
            print("HTTP:", response.status_code)
            print(
                "Content-Type:",
                response.headers.get("Content-Type")
            )
            print("Response length:", len(html))
            print("Final response URL:", response.url)
            print("Response preview:")
            print(html[:1000])
            print("====================================\n")

        error = fetch_error or (
            "STREAM_URL not found in API response"
            if not stream_url
            else "HDNEA token not found"
        )

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": response.status_code,
            "error": error,
            "final_url": stream_url or None,
        }

    except Exception as exc:

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
        }


# =========================================================
# MAIN
# =========================================================

def main():

    start = time.time()

    channels = load_channels()

    total = len(channels)

    successful = []
    failed = []

    print("\nStarting token extraction...")
    print("Workers:", MAX_WORKERS)
    print("Total:", total)

    results = []

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

            index, success, result = future.result()

            results.append((index, success, result))

            completed += 1

            print(
                f"[{completed}/{total}] "
                f"{result['channel_name']} - "
                f"{result['status']}"
            )

    # Keep original JSON channel order.

    results.sort(key=lambda item: item[0])

    for _, success, result in results:

        if success:
            successful.append(result)
        else:
            failed.append(result)

    output = {
        "source_url": SOURCE_URL,
        "total_channels": total,
        "successful_channels": len(successful),
        "failed_channels": len(failed),
        "timestamp": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": successful,
        "failed_results": failed,
    }

    # Write JSON atomically.

    temp_file = OUTPUT_FILE + ".tmp"

    with open(temp_file, "w", encoding="utf-8") as file:

        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )

    Path(temp_file).replace(OUTPUT_FILE)

    elapsed = time.time() - start

    print("\n========== SUMMARY ==========")
    print("Total channels:", total)
    print("Successful:", len(successful))
    print("Failed:", len(failed))
    print("Time taken:", round(elapsed, 2), "seconds")
    print("Output:", OUTPUT_FILE)
    print("=============================")


if __name__ == "__main__":
    main()
