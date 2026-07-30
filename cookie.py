import json
import re
from datetime import datetime
import requests

def save_hdnea_cookie():
    url = "https://jio.shoeblivesite.dpdns.org/"
    output_file = "cookie.json"
    
    try:
        print(f"[*] Fetching playlist from {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        playlist_content = response.text
        
        # Search for the __hdnea__ token in the playlist content
        match = re.search(r'(__hdnea__=[^\s]+)', playlist_content)
        
        if match:
            hdnea_value = match.group(1)
            
            # Get current timestamp in "HH:MM DD-MM-YYYY" format
            current_time = datetime.now().strftime("%H:%M %d-%m-%Y")
            
            # Structure the data as requested
            data_to_save = [
                {"last_updated": current_time},
                {"cookie": hdnea_value}
            ]
            
            # Write to cookie.json
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2)
                
            print(f"[+] Successfully saved token to {output_file} at {current_time}")
            print(json.dumps(data_to_save, indent=2))
        else:
            print("[-] Error: __hdnea__ token not found in the playlist.")
            
    except requests.exceptions.RequestException as e:
        print(f"[-] Network error: {e}")

if __name__ == "__main__":
    save_hdnea_cookie()
