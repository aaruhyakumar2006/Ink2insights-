"""
Check current Groq models - need vision models for image processing
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv('backend/.env')

api_key = os.getenv('GROQ_API_KEY')

# Current working Groq models (November 2026)
WORKING_MODELS = [
    "llama-3.2-90b-vision-preview",  # Vision model
    "llama-3.2-11b-vision-preview",  # Vision model (if available)
    "llama-3.3-70b-specdec",  # Vision model
    "llama-3.3-70b-versatile",  # Text model
    "mixtral-8x7b-32768",  # Text model
    "gemma2-9b-it",  # Text model
]

print("\n" + "="*70)
print("  CURRENT GROQ MODEL STATUS")
print("="*70)

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

for model in WORKING_MODELS:
    try:
        data = {
            "model": model,
            "messages": [{"role": "user", "content": "Say 'OK'"}],
            "max_tokens": 5,
            "temperature": 0.1
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            print(f"✅ {model}: ACTIVE")
            result = response.json()
            print(f"   Response: {result['choices'][0]['message']['content']}")
        elif response.status_code == 404:
            print(f"❌ {model}: NOT FOUND")
        elif "decommissioned" in response.text:
            print(f"🚫 {model}: DECOMMISSIONED")
        else:
            print(f"⚠️  {model}: Error {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  {model}: Failed - {str(e)[:50]}")

print("\n" + "="*70)
print("  RECOMMENDED FOR I2I:")
print("="*70)
print("\nSince we need VISION models for form scanning:")
print("✅ Try: llama-3.2-90b-vision-preview")
print("✅ Or: llama-3.3-70b-specdec (vision capable)")
print("\nChange in backend/.env:")
print("GROQ_MODEL=llama-3.2-90b-vision-preview")
print("(This should be the latest vision model)")
print("="*70)