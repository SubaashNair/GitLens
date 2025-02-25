import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def test_claude_api():
    """Test if the Claude API key is working by making a simple request."""
    
    # Get API key from environment variables
    api_key = os.getenv("API_KEY")
    
    if not api_key:
        return "Error: API_KEY not found in environment variables"
    
    # Claude API endpoint
    url = "https://api.anthropic.com/v1/messages"
    
    # Simple test prompt
    payload = {
        "model": "claude-3-7-sonnet-20250219",
        "max_tokens": 100,
        "messages": [
            {
                "role": "user", 
                "content": "Hi Claude, this is a test message to check if my API key is working. Please respond with a simple confirmation."
            }
        ]
    }
    
    # Headers with API key
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    try:
        print("Sending test request to Claude API...")
        response = requests.post(url, json=payload, headers=headers)
        
        # Check if request was successful
        if response.status_code == 200:
            result = response.json()
            print("\n✅ SUCCESS: Your Claude API key is working!\n")
            print(f"Claude's response: {result['content'][0]['text']}")
            return True
        else:
            print(f"\n❌ ERROR: API request failed with status code {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return False

if __name__ == "__main__":
    test_claude_api()