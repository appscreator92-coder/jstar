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

STREAM_URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>\\]+?(?:\.m3u8|\.mpd)(?:\?[^\s\"'<>\\]*)?",
    re.IGNORECASE,
)


def resolve_final_url(response: requests.Response, body: str) -> str | None:
    """Return the final stream/resolved URL containing __hdnea__ if present."""
    candidates = [resp.url for resp in response.history] + [response.url]
    for url in candidates:
        if "__hdnea__" in unquote(url):
            return url

    for match in STREAM_URL_PATTERN.finditer(body):
        candidate = match.group(0).replace("\\/", "/")
        if "__hdnea__" in unquote(candidate):
            return candidate

    for match in STREAM_URL_PATTERN.finditer(body):
        return match.group(0).replace("\\/", "/")

    if response.url and response.url != f"{PLAY_API_URL}?id=":
        return response.url

    return None


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
            final_url = resolve_final_url(resp, body)

            if resp.ok and final_url and "__hdnea__" in unquote(final_url):
                successful_results.append({
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "success",
                    "http_code": resp.status_code,
                    "final_url": final_url,
                })
            else:
                failed_results.append({
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "status": "failed",
                    "http_code": resp.status_code,
                    "error": "Missing __hdnea__ token in response or redirect chain",
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
