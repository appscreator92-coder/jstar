
import ast
import json
import re
import time
import threading

from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =====================================================
# CONFIGURATION
# =====================================================

SOURCE_URL = (
    "https://sportlink-tv10.pages.dev/jtvplus3.json"
)

PROXY_URL = (
    "https://master-proxy.wispy-boat-fc77.workers.dev/"
)

API_URL = (
    "https://b4uplay.com/api/vizha/play.php"
)

OUTPUT_FILE = Path("hdnea_tokens.json")

MAX_WORKERS = 4
TIMEOUT = 30
MAX_RETRIES = 2


# =====================================================
# HEADERS
# =====================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/158.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml,"
        "*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bhoomtv.me/",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


# =====================================================
# THREAD-LOCAL SESSION
# =====================================================

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


# =====================================================
# LOAD SOURCE CHANNELS
# =====================================================

def load_channels():

    print("Downloading channel JSON...")

    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
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
            "list",
            "results"
        ):

            if isinstance(data.get(key), list):
                channels = data[key]
                break

        if channels is None:
            raise ValueError(
                "Channel array not found in source JSON"
            )

    else:
        raise ValueError("Invalid source JSON")

    result = []

    for item in channels:

        if not isinstance(item, dict):
            continue

        channel_id = str(
            item.get(
                "id",
                item.get("channel_id", "")
            )
        ).strip()

        channel_name = str(
            item.get(
                "name",
                item.get(
                    "channel_name",
                    channel_id
                )
            )
        ).strip()

        if not channel_id:
            continue

        result.append({
            "id": channel_id,
            "name": channel_name
        })

    if not result:
        raise ValueError(
            "No valid channels found in source JSON"
        )

    print("Total channels:", len(result))

    return result


# =====================================================
# JAVASCRIPT VARIABLE EXTRACTION
# =====================================================

JS_STRING = (
    r'("(?:\\.|[^"\\])*"|'
    r"'(?:\\.|[^'\\])*')"
)


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
        return ""

    try:

        value = ast.literal_eval(
            match.group(1)
        )

        if isinstance(value, str):
            return value.strip()

    except (ValueError, SyntaxError):
        pass

    return ""


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

    stream_url = stream_url.replace("\\/", "/")
    token = token.replace("\\/", "/")

    return {
        "stream_url": stream_url,
        "hdnea_token": token,
        "fetch_error": fetch_error,
        "geo_blocked": geo_blocked
    }


# =====================================================
# BUILD FINAL URL
# =====================================================

def build_final_url(stream_url, token):

    if not stream_url:
        return None

    if not stream_url.startswith(
        ("https://", "http://")
    ):
        return None

    # The stream URL may already contain the token.

    if "__hdnea__=" in stream_url:
        return stream_url

    if not token:
        return stream_url

    if not token.startswith("__hdnea__="):
        token = "__hdnea__=" + token

    separator = (
        "&" if "?" in stream_url else "?"
    )

    return stream_url + separator + token


# =====================================================
# REQUEST PLAYER THROUGH PROXY
# =====================================================

def request_player(channel_id):

    session = get_session()

    target_url = (
        f"{API_URL}?id={channel_id}"
    )

    # Important: encode the complete target URL
    # as the Worker's "url" parameter.

    response = session.get(
        PROXY_URL,
        params={
            "url": target_url
        },
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True
    )

    return response


# =====================================================
# FETCH ONE CHANNEL
# =====================================================

def fetch_channel(index, channel):

    channel_id = channel["id"]
    channel_name = channel["name"]

    base_record = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "status": "failed",
        "http_code": None,
        "final_url": None
    }

    try:

        response = request_player(channel_id)

        base_record["http_code"] = (
            response.status_code
        )

        response.raise_for_status()

        html = response.text or ""

        if not html:
            raise ValueError("Empty player response")

        player = extract_player_data(html)

        # Do not mark geo-restricted responses
        # as successful.

        if player["geo_blocked"] is True:

            base_record["error"] = (
                "IS_GEO_BLOCKED is true"
            )

            return index, False, base_record

        if player["geo_blocked"] is None:

            base_record["error"] = (
                "IS_GEO_BLOCKED variable not found"
            )

            return index, False, base_record

        if player["fetch_error"]:

            base_record["error"] = (
                player["fetch_error"]
            )

            return index, False, base_record

        if not player["stream_url"]:

            base_record["error"] = (
                "STREAM_URL not found"
            )

            return index, False, base_record

        final_url = build_final_url(
            player["stream_url"],
            player["hdnea_token"]
        )

        if not final_url:

            base_record["error"] = (
                "Invalid stream URL"
            )

            return index, False, base_record

        # Successful response.

        success_record = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "success",
            "http_code": response.status_code,
            "final_url": final_url
        }

        return index, True, success_record

    except requests.HTTPError as exc:

        base_record["error"] = str(exc)

        return index, False, base_record

    except requests.RequestException as exc:

        base_record["error"] = str(exc)

        return index, False, base_record

    except Exception as exc:

        base_record["error"] = str(exc)

        return index, False, base_record


# =====================================================
# MAIN
# =====================================================

def main():

    start_time = time.time()

    channels = load_channels()

    total = len(channels)

    results = []

    print("\nStarting channel processing...")
    print("Proxy:", PROXY_URL)
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

    # Original requested JSON structure.

    output = {
        "source_url": SOURCE_URL,
        "total_channels": total,
        "successful_channels": len(
            successful_results
        ),
        "failed_channels": len(
            failed_results
        ),
        "timestamp": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),
        "successful_results": successful_results,
        "failed_results": failed_results
    }

    # Atomic JSON writing.

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
    print("===================================")


if __name__ == "__main__":
    main()
