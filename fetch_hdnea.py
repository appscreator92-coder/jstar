
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

MAX_WORKERS = 8
TIMEOUT = 30
MAX_RETRIES = 2


# =========================================================
# REQUEST HEADERS
# IMPORTANT: Define globally before any function uses them.
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/158.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://bhoomtv.me/",
    "Origin": "https://bhoomtv.me",
    "Sec-Fetch-Dest": "iframe",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Upgrade-Insecure-Requests": "1",
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
            status_forcelist=[429, 500, 502, 503, 504],
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
# JAVASCRIPT VARIABLE PATTERNS
# =========================================================

JS_STRING = r"""("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')"""

PATTERNS = {
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
# JAVASCRIPT STRING DECODER
# =========================================================

def decode_js_string(value):

    try:
        return ast.literal_eval(value)

    except (ValueError, SyntaxError):
        return value[1:-1]


# =========================================================
# EXTRACT VARIABLE
# =========================================================

def extract_variable(name, html):

    match = PATTERNS[name].search(html)

    if not match:
        return None

    if name == "IS_GEO_BLOCKED":
        return match.group(1).lower() == "true"

    value = decode_js_string(match.group(1))

    return value.strip() if isinstance(value, str) else ""


# =========================================================
# PARSE PLAYER HTML
# =========================================================

def parse_player_response(html):

    stream_url = extract_variable("STREAM_URL", html)
    hdnea_token = extract_variable("hdneaToken", html)
    fetch_error = extract_variable("fetchError", html)
    geo_blocked = extract_variable("IS_GEO_BLOCKED", html)

    if stream_url:
        stream_url = stream_url.replace("\\/", "/")

    if hdnea_token:
        hdnea_token = hdnea_token.replace("\\/", "/")

    return {
        "stream_url": stream_url or "",
        "hdnea_token": hdnea_token or "",
        "fetch_error": fetch_error or "",
        "geo_blocked": geo_blocked,
    }


# =========================================================
# DETECT CLOUDFLARE BLOCK PAGE
# =========================================================

def detect_cloudflare_block(response):

    html = response.text or ""
    lower_html = html.lower()

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        re.IGNORECASE | re.DOTALL
    )

    title = (
        re.sub(r"\s+", " ", title_match.group(1)).strip()
        if title_match else ""
    )

    indicators = [
        "sorry, you have been blocked",
        "you have been blocked",
        "attention required",
        "why have i been blocked",
        "performance & security by cloudflare",
        "cf-chl-",
    ]

    is_blocked = (
        any(item in lower_html for item in indicators)
        or "cloudflare" in title.lower()
        and response.status_code in (403, 429, 503)
    )

    return {
        "blocked": is_blocked,
        "title": title,
        "ray_id": response.headers.get("CF-RAY", ""),
    }


# =========================================================
# BUILD FINAL STREAM URL
# =========================================================

def build_final_url(stream_url, token):

    if not stream_url:
        return None

    if not stream_url.startswith(("https://", "http://")):
        return None

    # The stream URL may already contain its token.

    if "__hdnea__=" in stream_url:
        return stream_url

    if not token:
        return None

    # Add parameter only if it is not already present.

    if not token.startswith("__hdnea__="):
        token = "__hdnea__=" + token

    separator = "&" if "?" in stream_url else "?"

    return stream_url + separator + token


# =========================================================
# LOAD CHANNEL JSON
# =========================================================

def load_channels():

    print("Downloading jnew7.json...")

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

        for key in ("channels", "data", "items", "list"):

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

        response = session.get(
            API_URL,
            params={"id": channel_id},
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        http_code = response.status_code
        html = response.text or ""

        # Check Cloudflare response first.

        cloudflare = detect_cloudflare_block(response)

        if cloudflare["blocked"]:

            error = "Cloudflare blocked the request"

            if cloudflare["ray_id"]:
                error += " (Ray ID: " + cloudflare["ray_id"] + ")"

            return index, False, {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": http_code,
                "error": error,
                "final_url": None,
            }

        # Check HTTP status.

        response.raise_for_status()

        # Parse player variables.

        player = parse_player_response(html)

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

        # Extract URL and token.

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

        # Determine actual parsing failure.

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

        # Diagnostic output for first three failures.

        if index < 3:

            print("\n========== RESPONSE DEBUG ==========")
            print("Channel:", channel_name)
            print("ID:", channel_id)
            print("HTTP:", http_code)
            print("Final response URL:", response.url)
            print("Content-Type:", response.headers.get("Content-Type"))
            print("Cloudflare Ray:", cloudflare["ray_id"])
            print("Page title:", cloudflare["title"])
            print("Response length:", len(html))
            print("Geo flag:", player["geo_blocked"])
            print("STREAM_URL found:", bool(player["stream_url"]))
            print("Token found:", bool(player["hdnea_token"]))
            print("fetchError:", player["fetch_error"])
            print("Response preview:")
            print(html[:1200])
            print("====================================\n")

        return index, False, {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": http_code,
            "error": error,
            "final_url": None,
        }

    except requests.HTTPError as exc:

        status = (
            exc.response.status_code
            if exc.response is not None else None
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

    # Restore original channel order.

    results.sort(key=lambda item: item[0])

    successful_results = []
    failed_results = []

    for _, success, record in results:

        if success:
            successful_results.append(record)
        else:
            failed_results.append(record)

    # Create output JSON.

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

    # Atomic write.

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
