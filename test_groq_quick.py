#!/usr/bin/env python3
"""Quick Groq API test."""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv('backend/.env')

print("=" * 60)
print("🧪 Groq API Quick Test")
print("=" * 60)

api_key = os.getenv('GROQ_API_KEY')
model = os.getenv('GROQ_MODEL', 'llama-3.2-90b-vision-preview')

print(f"\n📋 Configuration:")
print(f"   Provider: groq")
print(f"   Model: {model}")

if not api_key or api_key == 'PASTE_YOUR_GROQ_KEY_HERE':
    print(f"   API Key: ❌ NOT SET")
    print("\n❌ Please set your Groq API key in backend/.env")
    print("\n📝 Steps:")
    print("   1. Go to: https://console.groq.com/keys")
    print("   2. Create an API key")
    print("   3. Copy the key (starts with gsk_)")
    print("   4. Replace PASTE_YOUR_GROQ_KEY_HERE in backend/.env")
    print("   5. Run this test again")
    sys.exit(1)

print(f"   API Key: {api_key[:10]}...{api_key[-4:]}")

try:
    from groq import Groq
    
    print("\n🌐 Testing API Connection...")
    client = Groq(api_key=api_key)
    
    # Simple text test
    print("📝 Sending test prompt...")
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Say 'Hello! Groq API is working!' and nothing else."}
        ],
        max_tokens=50,
        temperature=0.5
    )
    
    response = completion.choices[0].message.content
    print(f"✅ Response: {response}")
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS! Groq API is working!")
    print("=" * 60)
    print("\n✅ Configuration: CORRECT")
    print("✅ Authentication: SUCCESSFUL")
    print("✅ Model accessible: YES")
    print("✅ API calls: WORKING")
    print("\n🚀 Your backend is ready to use Groq!")
    print("\nNext steps:")
    print("   1. Restart your backend: cd backend && python app.py")
    print("   2. Test form scanning with AI")
    print("   3. Test mobile app connection")
    
except ImportError:
    print("\n❌ Error: groq package not installed")
    print("\n📦 Installing groq package...")
    os.system("pip install groq")
    print("\n✅ Package installed. Run test again:")
    print("   python test_groq_quick.py")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\n💡 Troubleshooting:")
    
    error_str = str(e).lower()
    if 'api key' in error_str or 'authentication' in error_str:
        print("   ❌ Invalid API key")
        print("   Fix: Get a new key from https://console.groq.com/keys")
    elif 'quota' in error_str or 'rate' in error_str:
        print("   ❌ Rate limit exceeded")
        print("   Fix: Wait a minute and try again")
    elif 'model' in error_str:
        print("   ❌ Model not available")
        print("   Fix: Try: llama-3.2-11b-vision-preview")
    else:
        print("   ❌ Unknown error")
        print("   Check: https://console.groq.com")
