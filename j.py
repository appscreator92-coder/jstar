def extract_token(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Check if the data is a list
        if isinstance(data, list) and len(data) > 0:
            # Grab the first item in the list, then get the token
            token = data[0].get('token') 
        elif isinstance(data, dict):
            # If it's a dictionary, get it directly
            token = data.get('token')
        else:
            token = None
        
        if token:
            print(f"Token extracted successfully: {token}")
            return token
        else:
            print("Token key not found.")
            return None

    except Exception as e:
        print(f"An error occurred: {e}")
        return None
