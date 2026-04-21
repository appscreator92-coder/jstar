import requests
import re
import datetime

url = "https://freelivtv.xyz/cookie.php"

def fetch_expiry():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # This regex looks for 'Expiry (IST):' and captures everything after it 
        # until the end of the line or an HTML tag starts.
        # \s* matches any whitespace. (.*?) captures the actual content.
        match = re.search(r"Expiry \(IST\):\s*(.*)", response.text)
        
        if match:
            expiry_data = match.group(1).strip()
            # Clean up HTML tags if they exist (like </div> or <br>)
            expiry_data = re.sub('<[^<]+?>', '', expiry_data)
            
            with open("expiry_status.txt", "w", encoding="utf-8") as f:
                f.write(f"Last Checked: {datetime.datetime.now()}\n")
                f.write(f"Expiry Info: {expiry_data}")
            
            print(f"Success! Expiry found: {expiry_data}")
        else:
            print("Could not find 'Expiry (IST):' text on the page.")
            
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    fetch_expiry()
