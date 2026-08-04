from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import re
import requests


def parse_m3u(content):
  channels = []
  lines = content.splitlines()
  current_channel = {}
  current_headers = {}

  extinf_pattern = re.compile(
      r'#EXTINF:-1.*?tvg-id="([^"]+)".*?tvg-name="([^"]+)".*?,\s*(.*)$'
  )

  for line in lines:
    line = line.strip()
    if line.startswith("#EXTINF:"):
      current_channel = {}
      current_headers = {}
      match = extinf_pattern.search(line)
      if match:
        current_channel["channel_id"] = match.group(1)
        current_channel["channel_name"] = match.group(2)
    elif line.startswith("#EXTHTTP:"):
      try:
        json_str = line.replace("#EXTHTTP:", "").strip()
        current_headers.update(json.loads(json_str))
      except json.JSONDecodeError:
        pass
    elif line and not line.startswith("#") and current_channel:
      current_channel["url"] = line
      current_channel["headers"] = current_headers
      channels.append(current_channel)
      current_channel = {}
      current_headers = {}

  return channels


def check_channel(ch):
  channel_id = ch["channel_id"]
  channel_name = ch["channel_name"]
  target_url = ch["url"]
  headers = ch.get("headers", {})

  try:
    res = requests.head(
        target_url, headers=headers, timeout=4, allow_redirects=True
    )
    http_code = res.status_code
    final_url = res.url

    if 200 <= http_code < 300:
      return {
          "status": "success",
          "data": {
              "channel_id": channel_id,
              "channel_name": channel_name,
              "status": "success",
              "http_code": http_code,
              "final_url": final_url,
          },
      }
    else:
      return {
          "status": "failed",
          "data": {
              "channel_id": channel_id,
              "channel_name": channel_name,
              "status": "failed",
              "error_details": {
                  "http_code": http_code,
                  "error": "",
                  "final_url": final_url,
              },
          },
      }
  except requests.exceptions.RequestException as e:
    return {
        "status": "failed",
        "data": {
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "error_details": {
                "http_code": 500,
                "error": str(e),
                "final_url": target_url,
            },
        },
    }


def main():
  m3u_url = "https://raw.githubusercontent.com/Sflex0719/m3u/refs/heads/main/Zio.m3u"

  try:
    response = requests.get(m3u_url, timeout=10)
    response.raise_for_status()
    m3u_content = response.text
  except requests.exceptions.RequestException as e:
    print(f"Error fetching M3U file: {e}")
    return

  channels = parse_m3u(m3u_content)
  successful_results = []
  failed_results = []

  with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(check_channel, ch): ch for ch in channels}
    for future in as_completed(futures):
      result = future.result()
      if result["status"] == "success":
        successful_results.append(result["data"])
      else:
        failed_results.append(result["data"])

  output_data = {
      "total_channels": len(channels),
      "successful_channels": len(successful_results),
      "failed_channels": len(failed_results),
      "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
      "successful_results": successful_results,
      "failed_results": failed_results,
  }

  print(json.dumps(output_data, indent=4))


if __name__ == "__main__":
  main()
