
import json
import re
import ast
import time
import threading

from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

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

OUTPUT_FILE = Path("hdnea_tokens.json")

MAX_WORKERS = 12
TIMEOUT = 30
MAX_RETRIES = 3

thread_local = threading.local()


# =========================================================
# BROWSER REQUEST HEADERS
# =========================================================

HEADERS = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/jxl,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),

    "accept-encoding": "gzip, deflate, br, zstd",

    "accept-language": "en-US,en;q=0.9",

    "referer": "https://bhoomtv.me/",

    "sec-ch-ua": (
        '"Chromium";v="158", "Not.A/Brand";v="24", '
        '"Google Chrome";v="158"'
    ),

    "sec-ch-ua-mobile": "?0",

    "sec-ch-ua-platform": '"Windows"',

    "sec-fetch-dest": "iframe",

    "sec-fetch-mode": "navigate",

    "sec-fetch-site": "cross-site",

    "sec-fetch-storage-access": "active",

    "sec-fetch-user": "?1",

    "upgrade-insecure-requests": "1",

    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/158.0.0.0 Safari/537.36"
    ),
}


# =========================================================
# JAVASCRIPT VARIABLE PATTERNS
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
# THREAD-LOCAL REQUEST SESSION
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
# DECODE JAVASCRIPT STRING
# =========================================================

def decode_js_string(value):

    try:
        return ast.literal_eval(value)

    except (ValueError, SyntaxError):

        return value[1:-1]


# =========================================================
# EXTRACT JAVASCRIPT VARIABLE
# =========================================================

def extract_variable(pattern, html):

    match = pattern.search(html)

    if not match:
        return ""

    return decode_js_string(
        match.group(1)
    ).strip()


# =========================================================
# DETECT GEO RESTRICTION
# =========================================================

def is_geo_restricted(html):

    text = html.lower()

    indicators = [
        "geo restricted",
        "geographical restriction",
        "geographic restriction",
        "not available in your region",
        "not available in your country",
        "country is not supported",
    ]

    return any(
        indicator in text
        for indicator in indicators
    )


# =========================================================
# EXTRACT STREAM URL AND TOKEN
# =========================================================

def extract_stream(html):

    stream_url = extract_variable(
        STREAM_PATTERN,
        html
    )

    token = extract_variable(
        TOKEN_PATTERN,
        html
    )

    fetch_error = extract_variable(
        ERROR_PATTERN,
        html
    )

    stream_url = stream_url.replace("\\/", "/")

    token = token.replace("\\/", "/")

    # The supplied player HTML normally already has
    # the complete tokenized STREAM_URL.

    if stream_url and "__hdnea__=" in stream_url:

        return stream_url, token, fetch_error

    # If token is separate, append it to the stream URL.

    if stream_url and token:

        if not token.startswith("__hdnea__="):
            token = "__hdnea__=" + token

        separator = "&" if "?" in stream_url else "?"

        stream_url += separator + token

    return stream_url, token, fetch_error


# =========================================================
# LOAD CHANNELS FROM jnew7.json
# =========================================================

def load_channels():

    print("Downloading jnew7.json...")

    response = requests.get(
        SOURCE_URL,
        headers={
            "User-Agent": HEADERS["user-agent"]
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
                "Channel list not found in jnew7.json"
            )

    else:

        raise ValueError(
            "Unexpected JSON structure"
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
            "name": channel_name
        })

    print("Total valid channels:", len(valid_channels))

    return valid_channels


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
            params={
                "id": channel_id
            },
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

        html = response.text

        # Check for geographic restrictions before parsing.

        if is_geo_restricted(html):

            return index, False, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": response.status_code,
                "error": "Geo Restricted: server denied regional access",
                "final_url": None
            }

        stream_url, token, fetch_error = extract_stream(html)

        # Validate the extracted stream.

        if (
            stream_url
            and "__hdnea__=" in stream_url
            and stream_url.startswith(("http://", "https://"))
        ):

            return index, True, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "success",
                "http_code": response.status_code,
                "final_url": stream_url
            }

        # Diagnostic output for first three failures.

        if index < 3:

            print("\n========== RESPONSE DEBUG ==========")

            print("Channel:", channel_name)
            print("ID:", channel_id)
            print("HTTP:", response.status_code)

            print(
                "Content-Type:",
                response.headers.get("Content-Type")
            )

            print(
                "Response length:",
                len(html)
            )

            print(
                "Response URL:",
                response.url
            )

            print("Response preview:")
            print(html[:1000])

            print("====================================\n")

        error = (
            fetch_error
            or (
                "STREAM_URL not found"
                if not stream_url
                else "HDNEA token not found in stream URL"
            )
        )

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": response.status_code,
            "error": error,
            "final_url": stream_url or None
        }

    except requests.RequestException as exc:

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc)
        }

    except Exception as exc:

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc)
        }


# =========================================================
# MAIN
# =========================================================

def main():

    start_time = time.time()

    channels = load_channels()

    total = len(channels)

    results = []

    print("\nStarting HDNEA extraction...")
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

            index, success, result = future.result()

            results.append(
                (index, success, result)
            )

            completed += 1

            print(
                f"[{completed}/{total}] "
                f"{result['channel_name']} - "
                f"{result['status']}"
            )

    # Restore original JSON order.

    results.sort(
        key=lambda item: item[0]
    )

    successful_results = []
    failed_results = []

    for _, success, result in results:

        if success:
            successful_results.append(result)

        else:
            failed_results.append(result)

    # Final JSON output.

    output = {

        "source_url": SOURCE_URL,

        "total_channels": total,

        "successful_channels": len(successful_results),

        "failed_channels": len(failed_results),

        "timestamp": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),

        "successful_results": successful_results,

        "failed_results": failed_results

    }

    # Save atomically.

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

    elapsed = time.time() - start_time

    print("\n========== SUMMARY ==========")

    print("Total channels:", total)

    print(
        "Successful:",
        len(successful_results)
    )

    print(
        "Failed:",
        len(failed_results)
    )

    print(
        "Time taken:",
        round(elapsed, 2),
        "seconds"
    )

    print("Output:", OUTPUT_FILE)

    print("=============================")


if __name__ == "__main__":
    main()
