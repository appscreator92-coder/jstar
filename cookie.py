import json
import re
from datetime import datetime
import requests

def save_hdnea_cookie():
    url = "https://jio.shoeblivesite.dpdns.org/"
    output_file = "cookie.json"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        playlist_content = response.text
        
        # Search for the __hdnea__ token in the fetched playlist
        match = re.search(r'(__hdnea__=[^\s"]+)', playlist_content)
        
        if match:
            hdnea_value = match.group(1)
            current_time = datetime.now().strftime("%H:%M %d-%m-%Y")
            
            data_to_save = [
                {"last_updated": current_time},
                {"cookie": hdnea_value}
            ]
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2)
            print(f"[+] Successfully updated {output_file}")
        else:
            print("[-] Token not found in response content.")
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    save_hdnea_cookie()
