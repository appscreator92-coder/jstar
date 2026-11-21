import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

import requests

JSON_URL = "https://raw.githubusercontent.com/appscreator92-coder/index/refs/heads/main/jnew7.json"
PLAY_API_URL = "https://b4uplay.com/api/vizha/play.php"
OUTPUT_FILE = Path("hdnea_tokens.json")

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
            hdnea_token = token_val if token_val.startswith("__hdnea__=") else f"__hdnea__={token_val}"

    if stream_url and hdnea_token and "__hdnea__" not in unquote(stream_url):
        sep = "&" if "?" in stream_url else "?"
        token_clean = hdnea_token if hdnea_token.startswith("__hdnea__=") else f"__hdnea__={hdnea_token}"
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


def main() -> None:
    entries = load_channel_entries(JSON_URL)
    successful_results: list[dict] = []
    failed_results: list[dict] = []

    session = requests.Session()

    for entry in entries:
        channel_id = str(entry["id"]).strip()
        channel_name = str(entry.get("name", "")).strip()
        if not channel_id:
            continue

        try:
            resp = session.get(
                PLAY_API_URL,
                params={"id": channel_id},
                headers=HEADERS.copy(),
                timeout=20,
                allow_redirects=True,
            )
            body = resp.text
            final_url, hdnea_token, page_error = extract_stream_info(body)

            has_token = bool(hdnea_token) or (bool(final_url) and "__hdnea__" in unquote(final_url))

            if resp.ok and final_url and has_token:
                successful_results.append({
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "success",
                    "http_code": resp.status_code,
                    "final_url": final_url,
                })
            else:
                reason = (
                    page_error
                    or ("Empty STREAM_URL in player HTML" if not final_url else "Missing __hdnea__ token in player HTML")
                )
                failed_results.append({
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "failed",
                    "http_code": resp.status_code,
                    "error": reason,
                    "final_url": final_url,
                })

        except requests.RequestException as exc:
            failed_results.append({
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "failed",
                "http_code": None,
                "error": str(exc),
            })

        time.sleep(0.5)

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
    print(
        f"Done: {len(successful_results)} succeeded, "
        f"{len(failed_results)} failed -> {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
