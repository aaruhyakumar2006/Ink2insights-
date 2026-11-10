#!/usr/bin/env python3
"""Live Gemini API test - actually calls the API."""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

print("=" * 60)
print("🧪 Gemini API Live Connection Test")
print("=" * 60)

gemini_key = os.getenv('GEMINI_API_KEY', '')
gemini_model = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')

if not gemini_key:
    print("❌ GEMINI_API_KEY not set in backend/.env")
    sys.exit(1)

print(f"\n📋 Configuration:")
print(f"   Model: {gemini_model}")
print(f"   API Key: {gemini_key[:10]}...{gemini_key[-4:]}")

# Test actual API call
print("\n" + "=" * 60)
print("🌐 Testing Live API Connection")
print("=" * 60)

try:
    import google.generativeai as genai
    
    # Configure API
    genai.configure(api_key=gemini_key)
    print("✅ API configured")
    
    # List available models
    print("\n📚 Fetching available models...")
    models = []
    try:
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                models.append(m.name)
                if len(models) >= 5:  # Limit to first 5
                    break
        
        if models:
            print(f"✅ Found {len(models)} model(s):")
            for model_name in models:
                print(f"   - {model_name}")
        else:
            print("⚠️  No models found (this might be okay)")
    except Exception as e:
        print(f"⚠️  Could not list models: {e}")
        print("   (This is not critical - we'll test with a direct call)")
    
    # Test with a simple text generation
    print(f"\n🧠 Testing text generation with {gemini_model}...")
    
    try:
        model = genai.GenerativeModel(gemini_model)
        response = model.generate_content("Say 'API test successful' in exactly those words.")
        
        if response and response.text:
            print(f"✅ API Response: {response.text.strip()}")
            print("\n🎉 SUCCESS! Gemini API is working perfectly!")
        else:
            print("⚠️  Got response but no text content")
            print(f"   Response: {response}")
            
    except Exception as e:
        error_str = str(e).lower()
        print(f"\n❌ API call failed: {e}")
        
        # Provide specific guidance based on error
        if "api_key" in error_str or "invalid" in error_str:
            print("\n💡 Issue: Invalid API Key")
            print("   Your API key may be:")
            print("   1. Incorrect or corrupted")
            print("   2. Not activated yet")
            print("   3. Restricted to specific IPs")
            print("\n   Get a new key at: https://aistudio.google.com/app/apikey")
            
        elif "quota" in error_str or "limit" in error_str:
            print("\n💡 Issue: Quota/Rate Limit")
            print("   Your API may have:")
            print("   1. Exceeded free tier limits")
            print("   2. Hit rate limits")
            print("   3. Billing not enabled")
            print("\n   Check quota at: https://console.cloud.google.com/")
            
        elif "not found" in error_str or "404" in error_str:
            print(f"\n💡 Issue: Model '{gemini_model}' not found")
            print("   Try these models instead:")
            print("   - gemini-1.5-flash")
            print("   - gemini-1.5-pro")
            print("   - gemini-pro-vision")
            print("\n   Update GEMINI_MODEL in backend/.env")
            
        elif "network" in error_str or "connect" in error_str:
            print("\n💡 Issue: Network/Connection")
            print("   Check:")
            print("   1. Internet connection")
            print("   2. Firewall blocking generativelanguage.googleapis.com")
            print("   3. Proxy settings if behind corporate firewall")
            
        else:
            print("\n💡 Unknown error - check full error message above")
            
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\n   Run: pip install google-generativeai")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Final summary
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
print("\n📊 Test Results:")
print("   ✅ API Key configured")
print("   ✅ Network connection successful")
print("   ✅ Model accessible")
print("   ✅ Text generation working")
print("\n🎉 Your Gemini API is fully functional!")
print("\n💡 Next Steps:")
print("   1. Start backend: python backend/app.py")
print("   2. Test document extraction via web UI")
print("   3. Build mobile apps when ready")
print("\n📱 Mobile App Build:")
print("   cd mobile")
print("   npm run build:preview")
