
import json
import re
import ast
import time
import threading

from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

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
MAX_RETRIES = 2

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
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/158.0.0.0 Safari/537.36"
    ),
}

# Host, Connection and browser-only storage-access metadata
# are not manually overridden.


# =========================================================
# JAVASCRIPT VARIABLE PATTERNS
# =========================================================

JS_STRING = r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')"""

VARIABLE_PATTERNS = {
    "STREAM_URL": re.compile(
        r"\b(?:const|let|var)\s+STREAM_URL\s*=\s*"
        + JS_STRING,
        re.IGNORECASE | re.DOTALL
    ),

    "hdneaToken": re.compile(
        r"\b(?:const|let|var)\s+hdneaToken\s*=\s*"
        + JS_STRING,
        re.IGNORECASE | re.DOTALL
    ),

    "fetchError": re.compile(
        r"\b(?:const|let|var)\s+fetchError\s*=\s*"
        + JS_STRING,
        re.IGNORECASE | re.DOTALL
    ),

    "IS_GEO_BLOCKED": re.compile(
        r"\b(?:const|let|var)\s+IS_GEO_BLOCKED\s*=\s*"
        r"(true|false)\b",
        re.IGNORECASE
    ),
}


# =========================================================
# THREAD-LOCAL SESSION
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
# DECODE JAVASCRIPT STRINGS
# =========================================================

def decode_js_string(value):

    try:
        return ast.literal_eval(value)

    except (ValueError, SyntaxError):
        return value[1:-1]


# =========================================================
# EXTRACT JAVASCRIPT VARIABLES
# =========================================================

def extract_variable(name, html):

    pattern = VARIABLE_PATTERNS[name]

    match = pattern.search(html)

    if not match:
        return None

    if name == "IS_GEO_BLOCKED":
        return match.group(1).lower() == "true"

    return decode_js_string(
        match.group(1)
    ).strip()


# =========================================================
# PARSE PLAYER RESPONSE
# =========================================================

def parse_player_response(html):

    geo_blocked = extract_variable(
        "IS_GEO_BLOCKED", html
    )

    stream_url = extract_variable(
        "STREAM_URL", html
    )

    hdnea_token = extract_variable(
        "hdneaToken", html
    )

    fetch_error = extract_variable(
        "fetchError", html
    )

    if stream_url:
        stream_url = stream_url.replace("\\/", "/")

    if hdnea_token:
        hdnea_token = hdnea_token.replace("\\/", "/")

    return {
        "geo_blocked": geo_blocked,
        "stream_url": stream_url or "",
        "hdnea_token": hdnea_token or "",
        "fetch_error": fetch_error or "",
    }


# =========================================================
# VALIDATE AND COMPLETE STREAM URL
# =========================================================

def build_final_url(stream_url, token):

    if not stream_url:
        return None

    if not stream_url.startswith(("https://", "http://")):
        return None

    # Preserve the original URL if it already contains
    # the HDNEA parameter.

    if "__hdnea__=" in stream_url:
        return stream_url

    # Append the separately supplied token only when
    # the URL does not already contain it.

    if token:

        if not token.startswith("__hdnea__="):
            token = "__hdnea__=" + token

        separator = "&" if "?" in stream_url else "?"

        return stream_url + separator + token

    return None


# =========================================================
# LOAD CHANNELS
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

        for key in ("channels", "data", "items", "list"):

            if isinstance(data.get(key), list):
                channels = data[key]
                break

        if channels is None:
            raise ValueError(
                "Channel array not found in JSON"
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

        response = session.get(
            API_URL,
            params={"id": channel_id},
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        http_code = response.status_code
        html = response.text

        # Detect geographic restriction pages.

        page_title = re.search(
            r"<title[^>]*>(.*?)</title>",
            html,
            re.IGNORECASE | re.DOTALL
        )

        title = (
            page_title.group(1).strip()
            if page_title else ""
        )

        if (
            "geo restricted" in title.lower()
            or "geo restricted" in html.lower()
        ):

            return index, False, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": http_code,
                "error": "Geo Restricted response",
                "final_url": None
            }

        response.raise_for_status()

        # Parse the actual player HTML.

        player = parse_player_response(html)

        # Check explicit geo flag.

        if player["geo_blocked"] is True:

            return index, False, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": http_code,
                "error": "IS_GEO_BLOCKED is true",
                "final_url": None
            }

        # Extract complete tokenized URL.

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
                "final_url": final_url
            }

        # Classify parsing failures.

        if player["fetch_error"]:

            error = player["fetch_error"]

        elif player["geo_blocked"] is None:

            error = "IS_GEO_BLOCKED variable not found"

        elif not player["stream_url"]:

            error = "STREAM_URL not found"

        elif not player["hdnea_token"]:

            error = "HDNEA token not found"

        else:

            error = "Invalid stream URL"

        # Print diagnostics for the first three failures.

        if index < 3:

            print("\n========== DEBUG ==========")
            print("Channel:", channel_name)
            print("ID:", channel_id)
            print("HTTP:", http_code)
            print("Title:", title or "Not found")
            print("Content-Type:", response.headers.get("Content-Type"))
            print("Response length:", len(html))
            print("Geo flag:", player["geo_blocked"])
            print("STREAM_URL found:", bool(player["stream_url"]))
            print("Token found:", bool(player["hdnea_token"]))
            print("fetchError:", player["fetch_error"])
            print("Response preview:")
            print(html[:1200])
            print("===========================\n")

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": http_code,
            "error": error,
            "final_url": None
        }

    except requests.RequestException as exc:

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
            "final_url": None
        }

    except Exception as exc:

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
            "final_url": None
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
    print("API:", API_URL)
    print("Workers:", MAX_WORKERS)
    print("Total:", total)

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

    # Preserve original channel order.

    results.sort(key=lambda item: item[0])

    successful_results = []
    failed_results = []

    for _, success, record in results:

        if success:
            successful_results.append(record)
        else:
            failed_results.append(record)

    # Required JSON structure.

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

    # Atomic JSON write.

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

    print("\n========== FINAL SUMMARY ==========")
    print("Total channels:", total)
    print("Successful:", len(successful_results))
    print("Failed:", len(failed_results))
    print("Time taken:", round(elapsed, 2), "seconds")
    print("Output file:", OUTPUT_FILE)
    print("===================================")


if __name__ == "__main__":
    main()
