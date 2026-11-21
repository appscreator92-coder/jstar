
import json
import re
import time
import random
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

JSON_URL = (
    "https://raw.githubusercontent.com/"
    "appscreator92-coder/index/refs/heads/main/jnew7.json"
)

PLAY_API_URL = "https://b4uplay.com/api/vizha/play.php"

OUTPUT_FILE = Path("hdnea_tokens.json")

MAX_WORKERS = 16
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3

# =====================================================
# REQUEST HEADERS
# =====================================================

HEADERS = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/jxl,image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "connection": "keep-alive",
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


# =====================================================
# REGEX PATTERNS
# =====================================================

STREAM_URL_RE = re.compile(
    r"""const\s+STREAM_URL\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE
)

HDNEA_TOKEN_RE = re.compile(
    r"""const\s+hdneaToken\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE
)

FETCH_ERROR_RE = re.compile(
    r"""const\s+fetchError\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE
)

HDNEA_PARAM_RE = re.compile(
    r"""__hdnea__=[^&"'\s\\<>]+""",
    re.IGNORECASE
)


# =====================================================
# THREAD LOCAL SESSION
# =====================================================

thread_local = threading.local()


def get_session():

    session = getattr(thread_local, "session", None)

    if session is None:

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
            pool_connections=4,
            pool_maxsize=4,
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        thread_local.session = session

    return session


# =====================================================
# LOAD CHANNEL JSON
# =====================================================

def load_channels():

    print("Downloading jnew7.json...")

    response = requests.get(
        JSON_URL,
        timeout=30
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
            raise ValueError("Channel list not found in JSON")

    else:

        raise ValueError("Invalid JSON structure")

    channels = [
        item for item in channels
        if isinstance(item, dict)
        and str(item.get("id", "")).strip()
    ]

    print(f"Total valid channels: {len(channels)}")

    return channels


# =====================================================
# EXTRACT STREAM URL AND HDNEA TOKEN
# =====================================================

def extract_stream_info(html):

    stream_match = STREAM_URL_RE.search(html)
    token_match = HDNEA_TOKEN_RE.search(html)
    error_match = FETCH_ERROR_RE.search(html)

    stream_url = (
        stream_match.group(1).strip()
        if stream_match else None
    )

    hdnea_token = (
        token_match.group(1).strip()
        if token_match else None
    )

    fetch_error = (
        error_match.group(1).strip()
        if error_match else None
    )

    if stream_url:

        stream_url = stream_url.replace("\\/", "/")

    # Fallback: Extract token from STREAM_URL or HTML.

    if not hdnea_token:

        search_target = stream_url or html

        match = HDNEA_PARAM_RE.search(
            requests.utils.unquote(search_target)
        )

        if match:
            hdnea_token = match.group(0)

    # Use STREAM_URL directly when it already contains token.

    if stream_url and hdnea_token:

        if "__hdnea__" not in requests.utils.unquote(stream_url):

            token = hdnea_token

            if not token.startswith("__hdnea__="):
                token = "__hdnea__=" + token

            separator = "&" if "?" in stream_url else "?"

            stream_url = stream_url + separator + token

    return stream_url, hdnea_token, fetch_error


# =====================================================
# FETCH SINGLE CHANNEL
# =====================================================

def fetch_channel(index, channel):

    channel_id = str(channel["id"]).strip()

    channel_name = str(
        channel.get("name", "")
    ).strip()

    try:

        time.sleep(random.uniform(0.05, 0.20))

        session = get_session()

        response = session.get(
            PLAY_API_URL,
            params={"id": channel_id},
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        response.raise_for_status()

        stream_url, hdnea_token, fetch_error = (
            extract_stream_info(response.text)
        )

        # Successful only when a stream URL and token exist.

        has_token = bool(
            hdnea_token
            or (
                stream_url
                and "__hdnea__" in requests.utils.unquote(
                    stream_url
                )
            )
        )

        if stream_url and has_token:

            return index, "success", {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "success",
                "http_code": response.status_code,
                "final_url": stream_url,
            }

        reason = (
            fetch_error
            or (
                "STREAM_URL not found"
                if not stream_url
                else "HDNEA token not found"
            )
        )

        return index, "failed", {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": response.status_code,
            "error": reason,
            "final_url": stream_url,
        }

    except requests.RequestException as exc:

        return index, "failed", {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
        }

    except Exception as exc:

        return index, "failed", {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
        }


# =====================================================
# MAIN FUNCTION
# =====================================================

def main():

    start_time = time.perf_counter()

    channels = load_channels()

    total = len(channels)

    results = []

    print("\nStarting HDNEA token extraction...\n")

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

            index, status, record = future.result()

            results.append((index, status, record))

            completed += 1

            print(
                f"[{completed}/{total}] "
                f"{record['channel_name']} : {status}"
            )

    # Restore original channel order.

    results.sort(key=lambda item: item[0])

    successful_results = [
        record
        for _, status, record in results
        if status == "success"
    ]

    failed_results = [
        record
        for _, status, record in results
        if status == "failed"
    ]

    # Final JSON structure.

    output_data = {

        "source_url": JSON_URL,

        "total_channels": total,

        "successful_channels": len(successful_results),

        "failed_channels": len(failed_results),

        "timestamp": datetime.now(
            timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S"),

        "successful_results": successful_results,

        "failed_results": failed_results,

    }

    # Save output.

    OUTPUT_FILE.write_text(
        json.dumps(
            output_data,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    elapsed = time.perf_counter() - start_time

    print("\n========== FETCH COMPLETED ==========")

    print(f"Total channels     : {total}")
    print(f"Successful         : {len(successful_results)}")
    print(f"Failed             : {len(failed_results)}")
    print(f"Time taken         : {elapsed:.2f} seconds")
    print(f"Output file        : {OUTPUT_FILE}")

    print("======================================")


if __name__ == "__main__":
    main()
