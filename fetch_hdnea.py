
import json
import re
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

# Additional diagnostic channel
TEST_CHANNEL_ID = "673"


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
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bhoomtv.me/",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


# =========================================================
# THREAD LOCAL SESSION
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
# BUILD REQUEST
# =========================================================

def build_api_request(channel_id):

    target_url = (
        TARGET_API + "?id=" + str(channel_id)
    )

    return PROXY_BASE, {
        "url": target_url
    }


# =========================================================
# JAVASCRIPT VARIABLE DIAGNOSTICS
# =========================================================

def extract_variable(html, variable):

    pattern = re.compile(
        r"\b(?:const|let|var)\s+"
        + re.escape(variable)
        + r"\s*=\s*"
        r'("(?:\\.|[^"\\])*"|'
        r"'(?:\\.|[^'\\])*'|"
        r"true|false|null)",
        re.IGNORECASE | re.DOTALL
    )

    match = pattern.search(html)

    if not match:
        return None

    value = match.group(1)

    # Never return actual URL or token values.
    if variable.lower() in ("stream_url", "hdneatoken"):
        return "PRESENT"

    return value


def inspect_player(html):

    variables = {
        "geo_flag": extract_variable(
            html, "IS_GEO_BLOCKED"
        ),
        "stream_url": extract_variable(
            html, "STREAM_URL"
        ),
        "hdnea_token": extract_variable(
            html, "hdneaToken"
        ),
        "fetch_error": extract_variable(
            html, "fetchError"
        ),
    }

    geo_value = variables["geo_flag"]

    if geo_value:
        geo_value = geo_value.lower()

    return variables, geo_value


# =========================================================
# RESPONSE DIAGNOSTICS
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

    cloudflare_indicators = [
        "you have been blocked",
        "sorry, you have been blocked",
        "attention required",
        "cf-chl-",
        "just a moment",
    ]

    cloudflare_blocked = any(
        item in lower
        for item in cloudflare_indicators
    )

    variables, geo_value = inspect_player(html)

    if cloudflare_blocked:
        status = "CLOUDFLARE_BLOCKED"

    elif geo_value == "true":
        status = "GEO_BLOCKED"

    elif geo_value == "false":

        if variables["stream_url"] == "PRESENT":
            status = "STREAM_AVAILABLE"
        elif variables["fetch_error"] not in (None, '""', "''"):
            status = "PLAYER_ERROR"
        else:
            status = "STREAM_NOT_FOUND"

    elif response.status_code != 200:
        status = "HTTP_ERROR"

    elif not html:
        status = "EMPTY_RESPONSE"

    else:
        status = "INVALID_RESPONSE"

    return {
        "status": status,
        "title": title,
        "geo_flag": geo_value,
        "stream_url_found": (
            variables["stream_url"] == "PRESENT"
        ),
        "token_found": (
            variables["hdnea_token"] == "PRESENT"
        ),
        "fetch_error": variables["fetch_error"],
        "response_length": len(html),
        "content_type": response.headers.get(
            "Content-Type", ""
        ),
        "ray_id": response.headers.get(
            "CF-RAY", ""
        ),
    }


# =========================================================
# LOAD CHANNELS
# =========================================================

def load_channels():

    print("Downloading source JSON...")

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
            "channels", "data", "items", "list"
        ):

            if isinstance(data.get(key), list):
                channels = data[key]
                break

        if channels is None:
            raise ValueError(
                "Channel array not found"
            )

    else:
        raise ValueError(
            "Unexpected JSON structure"
        )

    result = []

    for item in channels:

        if not isinstance(item, dict):
            continue

        channel_id = str(
            item.get("id", "")
        ).strip()

        if not channel_id:
            continue

        result.append({
            "id": channel_id,
            "name": str(
                item.get("name", channel_id)
            ).strip()
        })

    print("Total channels:", len(result))

    return result


# =========================================================
# FETCH ONE CHANNEL
# =========================================================

def fetch_channel(index, channel):

    channel_id = channel["id"]
    channel_name = channel["name"]

    try:

        session = get_session()

        proxy_url, params = build_api_request(
            channel_id
        )

        response = session.get(
            proxy_url,
            params=params,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        diagnostics = inspect_response(response)

        record = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": diagnostics["status"],
            "http_code": response.status_code,
            "geo_flag": diagnostics["geo_flag"],
            "stream_url_found": diagnostics["stream_url_found"],
            "token_found": diagnostics["token_found"],
            "fetch_error": diagnostics["fetch_error"],
            "page_title": diagnostics["title"],
            "response_length": diagnostics["response_length"],
            "content_type": diagnostics["content_type"],
            "cloudflare_ray_id": diagnostics["ray_id"],
        }

        if index < 3 or channel_id == TEST_CHANNEL_ID:

            print("\n========== CHANNEL DIAGNOSTICS ==========")
            print("Channel:", channel_name)
            print("ID:", channel_id)
            print("HTTP:", response.status_code)
            print("Status:", diagnostics["status"])
            print("Geo flag:", diagnostics["geo_flag"])
            print("Stream available:", diagnostics["stream_url_found"])
            print("Token present:", diagnostics["token_found"])
            print("Player error:", diagnostics["fetch_error"])
            print("Page title:", diagnostics["title"])
            print("Response length:", diagnostics["response_length"])
            print("Content-Type:", diagnostics["content_type"])
            print("=========================================\n")

        return index, record

    except requests.RequestException as exc:

        return index, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "REQUEST_ERROR",
            "http_code": None,
            "error": str(exc),
        }

    except Exception as exc:

        return index, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "UNKNOWN_ERROR",
            "http_code": None,
            "error": str(exc),
        }


# =========================================================
# SAVE OUTPUT
# =========================================================

def save_output(output):

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

    start = time.time()

    channels = load_channels()

    total = len(channels)

    results = []

    print("\nStarting diagnostics...")
    print("Proxy:", PROXY_BASE)
    print("Target:", TARGET_API)
    print("Workers:", MAX_WORKERS)

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

            index, record = future.result()

            results.append((index, record))

            completed += 1

            print(
                f"[{completed}/{total}] "
                f"{record['channel_name']} - "
                f"{record['status']}"
            )

    results.sort(key=lambda item: item[0])

    records = [
        record for _, record in results
    ]

    summary = {}

    for record in records:

        status = record["status"]

        summary[status] = (
            summary.get(status, 0) + 1
        )

    output = {
        "source_url": SOURCE_URL,
        "total_channels": total,
        "timestamp": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "results": records,
    }

    save_output(output)

    elapsed = time.time() - start

    print("\n========== FINAL SUMMARY ==========")
    print("Total channels:", total)

    for status, count in sorted(summary.items()):
        print(status + ":", count)

    print("Time:", round(elapsed, 2), "seconds")
    print("Output:", OUTPUT_FILE)
    print("===================================")


if __name__ == "__main__":
    main()
