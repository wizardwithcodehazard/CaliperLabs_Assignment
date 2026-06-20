import os
import requests

def download_filing(url: str, output_path: str, user_agent: str):
    """Downloads the SEC filing."""
    print(f"Downloading filing from {url}...")
    headers = {"User-Agent": user_agent}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(response.text)
    print(f"Saved filing to {output_path}")
