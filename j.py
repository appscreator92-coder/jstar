import requests

def extract_token(url):
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Extract the token (adjust the key 'token' if the JSON structure is different)
        # For example, if it's nested: data['data']['token']
        token = data.get('token')
        
        if token:
            print(f"Token extracted successfully: {token}")
            return token
        else:
            print("Token key not found in the JSON response.")
            print("Full JSON content:", data) # Debugging: see the actual structure
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None

# The URL provided
target_url = "https://allinonereborn.online/jstrweb2/jstr.json"

# Execute the function
extract_token(target_url)
