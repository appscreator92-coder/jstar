
import json
import re
import time
import threading
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =====================================================
# CONFIGURATION
# =====================================================

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


# =====================================================
# HEADERS
# =====================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/158.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bhoomtv.me/",
    "Cache-Control": "no-cache",
}


# =====================================================
# THREAD LOCAL SESSION
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

        thread_local.session = session

    return thread_local.session


# =====================================================
# CORRECT PROXY REQUEST
# =====================================================

def request_channel(channel_id):

    session = get_session()

    target_url = (
        f"{TARGET_API}?id={channel_id}"
    )

    response = session.get(
        PROXY_BASE,
        params={"url": target_url},
        headers=HEADERS,
        timeout=TIMEOUT,
        allow_redirects=True,
    )

    return response


# =====================================================
# EXTRACT VARIABLE STATUS
# =====================================================

def extract_variable(html, name):

    pattern = re.compile(
        r"\b(?:const|let|var)\s+"
        + re.escape(name)
        + r"\s*=\s*"
        r'("(?:\\.|[^"\\])*"|'
        r"'(?:\\.|[^'\\])*'|"
        r"true|false|null)",
        re.IGNORECASE | re.DOTALL
    )

    match = pattern.search(html)

    if not match:
        return None

    return match.group(1)


def inspect_player(html):

    geo = extract_variable(
        html, "IS_GEO_BLOCKED"
    )

    stream = extract_variable(
        html, "STREAM_URL"
    )

    token = extract_variable(
        html, "hdneaToken"
    )

    error = extract_variable(
        html, "fetchError"
    )

    geo_value = (
        geo.lower() if geo else None
    )

    return {
        "geo_blocked": geo_value,
        "stream_found": bool(stream),
        "token_found": bool(token),
        "fetch_error_present": bool(
            error and error not in ('""', "''")
        ),
    }


# =====================================================
# RESPONSE CLASSIFICATION
# =====================================================

def classify_response(response):

    html = response.text or ""

    lower = html.lower()

    if any(x in lower for x in [
        "you have been blocked",
        "attention required",
        "cf-chl-",
        "just a moment",
    ]):
        return {
            "status": "CLOUDFLARE_BLOCKED",
            "http_code": response.status_code,
        }

    if response.status_code != 200:
        return {
            "status": "HTTP_ERROR",
            "http_code": response.status_code,
        }

    player = inspect_player(html)

    geo = player["geo_blocked"]

    if geo == "true":
        status = "GEO_BLOCKED"

    elif geo == "false":

        if player["stream_found"]:
            status = "STREAM_AVAILABLE"
        elif player["fetch_error_present"]:
            status = "PLAYER_ERROR"
        else:
            status = "STREAM_NOT_FOUND"

    else:
        status = "INVALID_RESPONSE"

    return {
        "status": status,
        "http_code": response.status_code,
        "geo_flag": geo,
        "stream_url_found": player["stream_found"],
        "token_present": player["token_found"],
        "fetch_error_present": player["fetch_error_present"],
        "response_length": len(html),
    }


# =====================================================
# LOAD CHANNELS
# =====================================================

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

        channels = next(
            (
                data[key]
                for key in (
                    "channels",
                    "data",
                    "items",
                    "list"
                )
                if isinstance(data.get(key), list)
            ),
            None
        )

        if channels is None:
            raise ValueError(
                "Channel list not found"
            )

    else:
        raise ValueError(
            "Invalid source JSON"
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


# =====================================================
# FETCH ONE CHANNEL
# =====================================================

def fetch_channel(index, channel):

    channel_id = channel["id"]
    channel_name = channel["name"]

    try:

        response = request_channel(channel_id)

        result = classify_response(response)

        record = {
            "channel_id": channel_id,
            "channel_name": channel_name,
            **result
        }

        return index, record

    except requests.RequestException as exc:

        return index, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "REQUEST_ERROR",
            "error": str(exc),
        }

    except Exception as exc:

        return index, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "UNKNOWN_ERROR",
            "error": str(exc),
        }


# =====================================================
# MAIN
# =====================================================

def main():

    start = time.time()

    channels = load_channels()

    results = []

    total = len(channels)

    print("\nStarting extraction diagnostics...")
    print("Proxy:", PROXY_BASE)
    print("Workers:", MAX_WORKERS)

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = [
            executor.submit(
                fetch_channel,
                i,
                channel
            )
            for i, channel in enumerate(channels)
        ]

        for completed, future in enumerate(
            as_completed(futures), 1
        ):

            index, record = future.result()

            results.append((index, record))

            print(
                f"[{completed}/{total}] "
                f"{record['channel_name']} - "
                f"{record['status']}"
            )

    results.sort(key=lambda x: x[0])

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

    temp = OUTPUT_FILE.with_suffix(".tmp")

    with open(
        temp,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=4,
            ensure_ascii=False
        )

    temp.replace(OUTPUT_FILE)

    print("\n========== SUMMARY ==========")
    print("Total:", total)

    for status, count in sorted(summary.items()):
        print(f"{status}: {count}")

    print(
        "Time:",
        round(time.time() - start, 2),
        "seconds"
    )

    print("Output:", OUTPUT_FILE)
    print("=============================")


if __name__ == "__main__":
    main()
