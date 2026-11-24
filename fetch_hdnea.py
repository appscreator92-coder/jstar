
import re
import requests
from urllib.parse import quote

PROXY = "https://master-proxy.wispy-boat-fc77.workers.dev/"
TARGET = "https://b4uplay.com/api/vizha/play.php?id=673"

# Match the browser URL structure
request_url = PROXY + "?url=" + TARGET.rsplit("=", 1)[0] + "?id=" + quote("673")

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/158.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": "https://bhoomtv.me/",
}

response = requests.get(
    request_url,
    headers=headers,
    timeout=30
)

html = response.text

print("HTTP:", response.status_code)
print("Response length:", len(html))
print("Content type:", response.headers.get("Content-Type"))

# Extract JavaScript variables
patterns = {
    "IS_GEO_BLOCKED": r'const\s+IS_GEO_BLOCKED\s*=\s*(true|false)',
    "STREAM_URL": r'const\s+STREAM_URL\s*=\s*["\']([^"\']*)',
    "hdneaToken": r'const\s+hdneaToken\s*=\s*["\']([^"\']*)',
    "fetchError": r'const\s+fetchError\s*=\s*["\']([^"\']*)',
}

for name, pattern in patterns.items():
    match = re.search(pattern, html, re.I)
    if name in ("STREAM_URL", "hdneaToken"):
        value = "FOUND" if match else "NOT FOUND"
    else:
        value = match.group(1) if match else "NOT FOUND"

    print(name, ":", value)

# Save response for comparison
with open("python_response.html", "w", encoding="utf-8") as f:
    f.write(html)

print("Saved: python_response.html")
