#!/usr/bin/env python3
"""List available NVIDIA NIM models."""

import os
import sys
import requests
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

nvidia_key = os.getenv('NVIDIA_API_KEY', '')

if not nvidia_key:
    print("❌ NVIDIA_API_KEY not set")
    sys.exit(1)

print("🔍 Fetching available NVIDIA NIM models...")

# Try common vision models
test_models = [
    "meta/llama-3.2-90b-vision-instruct",
    "meta/llama-4-90b-vision-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "nvidia/nemotron-4-340b-instruct",
    "microsoft/phi-3-vision-128k-instruct",
]

print("\nTesting available models:\n")

for model in test_models:
    try:
        url = "https://integrate.api.nvidia.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {nvidia_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "test"}],
            "max_tokens": 5
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ {model} - AVAILABLE")
        elif response.status_code == 410:
            print(f"❌ {model} - DEPRECATED (end of life)")
        elif response.status_code == 404:
            print(f"⚠️  {model} - NOT FOUND")
        else:
            print(f"❓ {model} - Status {response.status_code}")
            
    except Exception as e:
        print(f"❌ {model} - ERROR: {e}")
