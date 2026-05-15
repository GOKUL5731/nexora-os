import requests
import json

url = "http://127.0.0.1:7474/status"

print(f"Testing JARVIS API status at {url}...")
try:
    response = requests.post(url, json={})
    response.raise_for_status()
    print("\nAPI Response:")
    print(json.dumps(response.json(), indent=2))
except Exception as e:
    print(f"\nError: Could not connect to JARVIS API.")
    print(f"Details: {e}")
