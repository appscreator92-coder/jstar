from datetime import datetime
import json
import re
import pytz
import requests

# URL of the M3U playlist
url = "https://premiumplugx.com/htt/hot.php?playlist=1"

try:
  # Fetch the playlist content
  response = requests.get(url)
  response.raise_for_status()
  content = response.text

  # Search for the cookie string in the playlist data
  cookie_match = re.search(r"(?:http-cookie=|cookie=)([^&\n\r]+)", content)

  if cookie_match:
    cookie_value = cookie_match.group(1).strip()

    # Get current time in Indian Standard Time (IST)
    ist_timezone = pytz.timezone("Asia/Kolkata")
    current_time_ist = datetime.now(ist_timezone).strftime("%H:%M %d-%m-%Y")

    # JSON structure matching your target format
    data = [{"last_updated": current_time_ist}, {"cookie": cookie_value}]

    # Save to hot.json
    with open("hot.json", "w") as f:
      json.dump(data, f, indent=2)

    print("Successfully updated hot.json with IST time")
  else:
    print("Cookie could not be found in the playlist.")

except Exception as e:
  print(f"An error occurred: {e}")
