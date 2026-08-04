from datetime import datetime
import json
import re
import requests


def parse_m3u(content):
  """Parses the specific M3U content format with EXTINF, EXTHTTP, and URLs."""
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
      # Reset for a new channel entry
      current_channel = {}
      current_headers = {}
      match = extinf_pattern.search(line)
      if match:
        current_channel["channel_id"] = match.group(1)
        current_channel["channel_name"] = match.group(2)

    elif line.startswith("#EXTHTTP:"):
      try:
        # Extract cookie or json data if present in EXTHTTP
        json_str = line.replace("#EXTHTTP:", "").strip()
        headers_data = json.loads(json_str)
        current_headers.update(headers_data)
      except json.JSONDecodeError:
        pass

    elif line and not line.startswith("#") and current_channel:
      # This is the stream URL line
      current_channel["url"] = line
      current_channel["headers"] = current_headers
      channels.append(current_channel)
      current_channel = {}
      current_headers = {}

  return channels


def main():
  m3u_url = "https://raw.githubusercontent.com/Sflex0719/m3u/refs/heads/main/Zio.m3u"

  try:
    response = requests.get(m3u_url, timeout=15)
    response.raise_for_status()
    m3u_content = response.text
  except requests.exceptions.RequestException as e:
    print(f"Error fetching M3U file: {e}")
    return

  channels = parse_m3u(m3u_content)

  successful_results = []
  failed_results = []

  # Process and check each parsed channel
  for ch in channels:
    channel_id = ch["channel_id"]
    channel_name = ch["channel_name"]
    target_url = ch["url"]
    headers = ch.get("headers", {})

    try:
      # Use HEAD or GET with appropriate headers (like cookies) to test stream availability
      # Some CDN endpoints require headers/cookies to return proper status codes instead of 450/403
      res = requests.head(
          target_url, headers=headers, timeout=5, allow_redirects=True
      )
      http_code = res.status_code
      final_url = res.url

      # Consider 200-299 as success status codes
      if 200 <= http_code < 300:
        successful_results.append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "success",
            "http_code": http_code,
            "final_url": final_url,
            "playlist_data": "API failed: invalid response",  # Preserved as per your layout structure
        })
      else:
        failed_results.append({
            "channel_id": channel_id,
            "channel_name": channel_name,
            "status": "failed",
            "error_details": {
                "http_code": http_code,
                "error": "",
                "final_url": final_url,
            },
        })
    except requests.exceptions.RequestException as e:
      failed_results.append({
          "channel_id": channel_id,
          "channel_name": channel_name,
          "status": "failed",
          "error_details": {
              "http_code": 500,
              "error": str(e),
              "final_url": target_url,
          },
      })

  output_data = {
      "total_channels": len(channels),
      "successful_channels": len(successful_results),
      "failed_channels": len(failed_results),
      "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
      "successful_results": successful_results,
      "failed_results": failed_results,
  }

  # Print JSON formatted to match your target template layout
  print(json.dumps(output_data, indent=4))


if __name__ == "__main__":
  main()
