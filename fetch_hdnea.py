import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import requests
from requests.adapters import HTTPAdapter

JSON_URL = "https://raw.githubusercontent.com/appscreator92-coder/index/refs/heads/main/jnew7.json"
PLAY_API_URL = "https://b4uplay.com/api/vizha/play.php"
OUTPUT_FILE = Path("hdnea_tokens.json")

MAX_WORKERS = 16
REQUEST_TIMEOUT = 10
REQUEST_DELAY = 0.05  # small jitter/pacing per worker in seconds

HEADERS = {
    "accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/jxl,"
        "image/avif,image/webp,image/apng,*/*;q=0.8,"
        "application/signed-exchange;v=b3;q=0.7"
    ),
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-US,en;q=0.9",
    "connection": "keep-alive",
    "host": "b4uplay.com",
    "referer": "https://bhoomtv.me/",
    "sec-ch-ua": '"Chromium";v="158", "Not.A/Brand";v="24", "Google Chrome";v="158"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "iframe",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "cross-site",
    "sec-fetch-storage-access": "active",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/158.0.0.0 Safari/537.36"
    ),
}

STREAM_URL_VAR_RE = re.compile(
    r"""const\s+STREAM_URL\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
HDNEA_VAR_RE = re.compile(
    r"""const\s+hdneaToken\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
FETCH_ERROR_VAR_RE = re.compile(
    r"""const\s+fetchError\s*=\s*["']([^"']*)["']""",
    re.IGNORECASE,
)
HDNEA_PARAM_RE = re.compile(
    r"""(__hdnea__=[^&"'\s\\<>]+)""",
    re.IGNORECASE,
)

_thread_local = threading.local()


def get_session() -> requests.Session:
    """Create a dedicated requests.Session with a pooled adapter per worker thread."""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=32, pool_maxsize=32)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _thread_local.session = session
    return session


def extract_stream_info(body: str) -> tuple[str | None, str | None, str | None]:
    """Extract (final_url, hdnea_token, page_error) from the player HTML."""
    stream_match = STREAM_URL_VAR_RE.search(body)
    hdnea_match = HDNEA_VAR_RE.search(body)
    err_match = FETCH_ERROR_VAR_RE.search(body)

    stream_url = stream_match.group(1).strip() if stream_match else None
    hdnea_token = hdnea_match.group(1).strip() if hdnea_match else None
    page_error = err_match.group(1).strip() if err_match else None

    if stream_url:
        stream_url = stream_url.replace("\\/", "/")

    if not hdnea_token:
        search_target = unquote(stream_url or body)
        m = HDNEA_PARAM_RE.search(search_target)
        if m:
            token_val = m.group(1)
            hdnea_token = (
                token_val
                if token_val.startswith("__hdnea__=")
                else f"__hdnea__={token_val}"
            )

    if stream_url and hdnea_token and "__hdnea__" not in unquote(stream_url):
        sep = "&" if "?" in stream_url else "?"
        token_clean = (
            hdnea_token
            if hdnea_token.startswith("__hdnea__=")
            else f"__hdnea__={hdnea_token}"
        )
        stream_url = f"{stream_url}{sep}{token_clean}"

    return stream_url, hdnea_token, page_error


def load_channel_entries(url: str) -> list[dict]:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict) and "id" in item]
    if isinstance(data, dict):
        for key in ("channels", "data", "items", "list"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict) and "id" in item]
    raise ValueError("Unexpected JSON structure in jnew7.json")


def fetch_one(index: int, entry: dict) -> tuple[int, str, dict]:
    """Fetch and parse a single channel entry."""
    channel_id = str(entry["id"]).strip()
    channel_name = str(entry.get("name", "")).strip()

    if REQUEST_DELAY > 0:
        time.sleep(REQUEST_DELAY)

    try:
        session = get_session()
        resp = session.get(
            PLAY_API_URL,
            params={"id": channel_id},
            headers=HEADERS.copy(),
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        body = resp.text
        final_url, hdnea_token, page_error = extract_stream_info(body)

        has_token = bool(hdnea_token) or (
            bool(final_url) and "__hdnea__" in unquote(final_url)
        )

        if resp.ok and final_url and has_token:
            return index, "success", {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "success",
                "http_code": resp.status_code,
                "final_url": final_url,
            }

        reason = (
            page_error
            or (
                "Empty STREAM_URL in player HTML"
                if not final_url
                else "Missing __hdnea__ token in player HTML"
            )
        )
        return index, "failed", {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": resp.status_code,
            "error": reason,
            "final_url": final_url,
        }

    except requests.RequestException as exc:
        return index, "failed", {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "http_code": None,
            "error": str(exc),
        }


def main() -> None:
    start_time = time.perf_counter()
    raw_entries = load_channel_entries(JSON_URL)
    entries = [
        (idx, item)
        for idx, item in enumerate(raw_entries)
        if str(item.get("id", "")).strip()
    ]

    ordered_success: list[tuple[int, dict]] = []
    ordered_failed: list[tuple[int, dict]] = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [
            executor.submit(fetch_one, idx, item) for idx, item in entries
        ]
        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            idx, outcome, record = future.result()
            completed += 1
            if outcome == "success":
                ordered_success.append((idx, record))
            else:
                ordered_failed.append((idx, record))

            if completed % 100 == 0 or completed == total:
                elapsed = time.perf_counter() - start_time
                print(f"Progress: {completed}/{total} ({elapsed:.1f}s)")

    ordered_success.sort(key=lambda pair: pair[0])
    ordered_failed.sort(key=lambda pair: pair[0])

    successful_results = [rec for _, rec in ordered_success]
    failed_results = [rec for _, rec in ordered_failed]

    output_data = {
        "source_url": JSON_URL,
        "total_channels": len(successful_results) + len(failed_results),
        "successful_channels": len(successful_results),
        "failed_channels": len(failed_results),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "successful_results": successful_results,
        "failed_results": failed_results,
    }

    OUTPUT_FILE.write_text(json.dumps(output_data, indent=4), encoding="utf-8")
    elapsed = time.perf_counter() - start_time
    print(
        f"Done in {elapsed:.1f}s: {len(successful_results)} succeeded, "
        f"{len(failed_results)} failed -> {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
