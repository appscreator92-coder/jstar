from datetime import datetime, timedelta, timezone
import json
import requests


def transform_jtv_data(json_url):
  try:
    response = requests.get(json_url, timeout=30)
    response.raise_for_status()
    data = response.json()
  except Exception as e:
    print(f"Error fetching data: {e}")
    return None

  channels = data.get("channels", [])
  total_channels = len(channels)
  successful_results = []

  for ch in channels:
    channel_id = ch.get("id")
    channel_name = ch.get("name")
    stream_url = ch.get("stream_url", "")
    cookie = ch.get("cookie", "")

    final_url = f"{stream_url}?{cookie}" if cookie else stream_url

    channel_result = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "status": "success",
        "http_code": 200,
        "final_url": final_url,
    }
    successful_results.append(channel_result)

  # Define Indian Standard Time (IST is UTC +5:30)
  IST = timezone(timedelta(hours=5, minutes=30))
  current_ist_time = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

  output_data = {
      "source_url": json_url,
      "total_channels": total_channels,
      "successful_channels": total_channels,
      "failed_channels": 0,
      "timestamp": current_ist_time,
      "successful_results": successful_results,
  }

  return output_data


if __name__ == "__main__":
  url = "https://sportlink-tv10.pages.dev/jtv2.json"
  transformed_json = transform_jtv_data(url)

  if transformed_json:
    with open("star1.json", "w", encoding="utf-8") as f:
      json.dump(transformed_json, f, indent=4)
    print("Successfully generated star1.json")
