#!/usr/bin/env python3
"""Test NVIDIA NIM API configuration."""

import os
import sys
import requests
from pathlib import Path

backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

print("=" * 60)
print("🧪 NVIDIA NIM API Test")
print("=" * 60)

nvidia_key = os.getenv('NVIDIA_API_KEY', '')
nvidia_model = os.getenv('NVIDIA_MODEL', 'meta/llama-3.2-11b-vision-instruct')

if not nvidia_key:
    print("❌ NVIDIA_API_KEY not set")
    sys.exit(1)

print(f"\n📋 Configuration:")
print(f"   Model: {nvidia_model}")
print(f"   API Key: {nvidia_key[:10]}...{nvidia_key[-4:]}")

# Test API
print("\n🌐 Testing NVIDIA NIM API Connection...")

try:
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {nvidia_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": nvidia_model,
        "messages": [{"role": "user", "content": "Say 'API test successful' in exactly those words."}],
        "max_tokens": 50,
        "temperature": 0.2
    }
    
    print("   Sending test request...")
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    
    if response.status_code == 200:
        data = response.json()
        message = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f"\n✅ API Response: {message.strip()}")
        print("\n🎉 SUCCESS! NVIDIA NIM API is working!")
        print("\n✅ Your backend can now:")
        print("   - Extract text from clinical forms")
        print("   - Process patient documents")
        print("   - Use AI vision for handwriting recognition")
    else:
        print(f"\n❌ API Error {response.status_code}: {response.text}")
        sys.exit(1)
        
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\n📱 Ready to build mobile apps!")
print("   cd mobile")
print("   npm run build:preview")
