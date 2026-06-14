import json
import re
import os
import time
import requests
from git import Repo

# --- CONFIGURATION ---
# The URL where your source JSON is hosted
JSON_SOURCE_URL = "https://raw.githubusercontent.com/appscreator92-coder/jstar/refs/heads/main/source.json"

# Dynamic Pathing: Locates the file relative to where this script sits
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Moves up one level from ' and into 'data/'
FILE_TO_UPDATE = os.path.join(BASE_DIR, "../playlist.json")
REPO_PATH = os.path.join(BASE_DIR, "../")

# Cookie settings: Expiry set to 24 hours (86400 seconds) from now
EXPIRY_DURATION = 86400 

def generate_dynamic_cookie():
    """Generates a fresh cookie string with current Unix timestamps."""
    start_time = int(time.time())
    expire_time = start_time + EXPIRY_DURATION
    # Note: hmac is usually static unless your provider changes the key
    cookie = f"__hdnea__=st={start_time}~exp={expire_time}~acl=/*~hmac=3b2fade0d8e83bc55bd75e9bf0db2172709a7dacb8bf3d917ce6a13095e20929"
    return cookie

def update_repo_from_url():
    try:
        # 1. Fetch JSON from remote URL
        print(f"Connecting to: {JSON_SOURCE_URL}")
        response = requests.get(JSON_SOURCE_URL, timeout=15)
        response.raise_for_status()
        data = response.json()

        # 2. Generate and Inject the New Cookie
        new_cookie = generate_dynamic_cookie()
        
        if "#EXTHTTP" in data:
            # Regex targets: "cookie":"ANYTHING_BETWEEN_QUOTES"
            pattern = r'("cookie":\s*")[^"]+(")'
            data["#EXTHTTP"] = re.sub(pattern, rf'\1{new_cookie}\2', data["#EXTHTTP"])
            print(f"Success: New cookie generated (Expires: {time.ctime(time.time() + EXPIRY_DURATION)})")
        else:
            print("Error: Target key '#EXTHTTP' not found in source JSON.")
            return

        # 3. Save modified JSON to the local data folder
        os.makedirs(os.path.dirname(FILE_TO_UPDATE), exist_ok=True)
        with open(FILE_TO_UPDATE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"File updated: {os.path.basename(FILE_TO_UPDATE)}")

        # 4. Git Logic (Commit and Push)
        # This part is handled by the GitHub Action YAML usually, 
        # but including it here for local automation capability.
        try:
            repo = Repo(REPO_PATH)
            if repo.is_dirty(untracked_files=True):
                repo.git.add(FILE_TO_UPDATE)
                print("Changes detected and staged for commit.")
            else:
                print("No changes in data. Skipping Git push.")
        except Exception as git_err:
            print(f"Git status check skipped: {git_err}")

    except requests.exceptions.RequestException as e:
        print(f"Network Error: Could not fetch JSON. {e}")
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    update_repo_from_url()
