import requests

def scrape_and_truncate():
    url = "https://freelivtv.xyz/cookie.php"
    TARGET_WORD = "Expiry"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        content = response.text

        # Find the position of "Expiry"
        index = content.find(TARGET_WORD)

        if index != -1:
            # Slice content: index + length of "Expiry" (6) to include the word itself
            cleaned_data = content[:index + len(TARGET_WORD)]
            print(f"Successfully truncated after '{TARGET_WORD}'")
        else:
            cleaned_data = content
            print(f"Word '{TARGET_WORD}' not found. Saving full content.")

        with open("scraped_data.txt", "w", encoding="utf-8") as f:
            f.write(cleaned_data)
            
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    scrape_and_truncate()
