import json
import re
from datetime import datetime, timezone, timedelta
import requests

def save_hdnea_cookie():
    url = "https://raw.githubusercontent.com/joiptv/jojo/refs/heads/main/Sir.m3u"
    output_file = "cookie.json"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        playlist_content = response.text
        
        # Search specifically for the broad token with acl=\/*
        match = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=\/\\?\*~hmac=[a-fA-F0-9]+)', playlist_content)
        
        if not match:
            # Fallback pattern if the escape slashes vary
            match = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=\/\*~hmac=[a-fA-F0-9]+)', playlist_content)
            
        if match:
            hdnea_value = match.group(1)
            
            # Generate current date and time explicitly set to Indian Standard Time (IST, UTC+5:30)
            IST = timezone(timedelta(hours=5, minutes=30))
            current_time = datetime.now(IST).strftime("%H:%M %d-%m-%Y")
            
            data_to_save = [
                {"last_updated": current_time},
                {"cookie": hdnea_value}
            ]
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, indent=2)
            print(f"[+] Successfully updated {output_file} with the broad token.")
        else:
            print("[-] Specific broad token (acl=/*) not found in response content.")
            
    except Exception as e:
        print(f"[-] Error: {e}")

if __name__ == "__main__":
    save_hdnea_cookie()
