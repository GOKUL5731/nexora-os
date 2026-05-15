import requests
import json

url = "http://localhost:11434/api/generate"

data = {
    "model": "llama3.2",
    "prompt": "Hello Jarvis, introduce yourself briefly.",
    "stream": False
}

print("Connecting to JARVIS brain (Ollama)...")
try:
    response = requests.post(url, json=data)
    response.raise_for_status()
    result = response.json()
    print("\nJARVIS Response:")
    print("-" * 20)
    print(result["response"])
    print("-" * 20)
except Exception as e:
    print(f"\nError: Could not connect to Ollama. Make sure the Ollama app is running.")
    print(f"Details: {e}")
