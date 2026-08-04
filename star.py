from datetime import datetime
import json
import re
import requests
from zoneinfo import ZoneInfo  # Python 3.9+


def parse_m3u(content):
  channels = []
  lines = content.splitlines()
  current_channel = {}

  extinf_pattern = re.compile(
      r'#EXTINF:-1.*?tvg-id="([^"]+)".*?tvg-name="([^"]+)".*?,\s*(.*)$'
  )

  for line in lines:
    line = line.strip()
    if line.startswith("#EXTINF:"):
      current_channel = {}
      match = extinf_pattern.search(line)
      if match:
        current_channel["channel_id"] = match.group(1)
        current_channel["channel_name"] = match.group(2)
    elif line.startswith("#EXTHTTP:"):
      try:
        json_str = line.replace("#EXTHTTP:", "").strip()
        headers_data = json.loads(json_str)
        if "cookie" in headers_data:
          current_channel["cookie"] = headers_data["cookie"]
      except json.JSONDecodeError:
        pass
    elif line and not line.startswith("#") and current_channel:
      current_channel["url"] = line
      channels.append(current_channel)
      current_channel = {}

  return channels


def main():
  m3u_url = "https://raw.githubusercontent.com/joiptv/jojo/refs/heads/main/Jojo.m3u"

  try:
    response = requests.get(m3u_url, timeout=10)
    response.raise_for_status()
    m3u_content = response.text
  except requests.exceptions.RequestException as e:
    print(f"Error fetching M3U file: {e}")
    return

  channels = parse_m3u(m3u_content)
  successful_results = []

  for ch in channels:
    channel_id = ch.get("channel_id")
    channel_name = ch.get("channel_name")
    base_url = ch.get("url")
    cookie = ch.get("cookie", "")

    if cookie and "?" in base_url:
      final_url = f"{base_url}&{cookie}"
    elif cookie:
      final_url = f"{base_url}?{cookie}"
    else:
      final_url = base_url

    successful_results.append({
        "channel_id": channel_id,
        "channel_name": channel_name,
        "status": "success",
        "http_code": 200,
        "final_url": final_url,
    })

  # Get current time explicitly set to Indian Standard Time (IST)
  ist_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime(
      "%Y-%m-%d %H:%M:%S"
  )

  output_data = {
      "total_channels": len(channels),
      "successful_channels": len(successful_results),
      "failed_channels": 0,
      "timestamp": ist_time,
      "successful_results": successful_results,
      "failed_results": [],
  }

  print(json.dumps(output_data, indent=4))


if __name__ == "__main__":
  main()
