import re
import requests

def extract_hdnea_from_playlist():
    url = "https://jio.shoeblivesite.dpdns.org/"
    
    try:
        print(f"[*] Fetching playlist from {url}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        playlist_content = response.text
        
        # Regex to find all instances of __hdnea__ parameters in the URLs
        # This will capture the parameter string like: ?__hdnea__=st=...
        hdnea_patterns = re.findall(r'(__hdnea__=[^"\s]+)', playlist_content)
        
        if hdnea_patterns:
            # Grab the unique tokens found
            unique_tokens = list(set(hdnea_patterns))
            print(f"\n[+] Success! Found {len(unique_tokens)} unique __hdnea__ token instance(s):")
            for idx, token in enumerate(unique_tokens, 1):
                print(f"\n--- Token {idx} ---")
                print(token)
        else:
            print("\n[-] No __hdnea__ tokens found in the playlist response.")
            
    except requests.exceptions.RequestException as e:
        print(f"\n[-] Error fetching the URL: {e}")

if __name__ == "__main__":
    extract_hdnea_from_playlist()
