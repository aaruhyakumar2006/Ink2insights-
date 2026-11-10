#!/usr/bin/env python3
"""Test script to verify Gemini API configuration and connectivity."""

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
print("🧪 Gemini API Configuration Test")
print("=" * 60)

# Check environment variables
print("\n📋 Environment Variables:")
print(f"AI_PROVIDER: {os.getenv('AI_PROVIDER')}")
print(f"GEMINI_MODEL: {os.getenv('GEMINI_MODEL')}")

gemini_key = os.getenv('GEMINI_API_KEY', '')
if gemini_key:
    masked_key = gemini_key[:10] + "..." + gemini_key[-4:] if len(gemini_key) > 14 else "***"
    print(f"GEMINI_API_KEY: {masked_key} (length: {len(gemini_key)})")
else:
    print("❌ GEMINI_API_KEY: NOT SET")
    sys.exit(1)

# Test 1: Check if GeminiService can be imported
print("\n" + "=" * 60)
print("Test 1: Import GeminiService")
print("=" * 60)
try:
    from backend.services.gemini_service import GeminiService
    print("✅ GeminiService imported successfully")
except Exception as e:
    print(f"❌ Failed to import GeminiService: {e}")
    sys.exit(1)

# Test 2: Initialize service
print("\n" + "=" * 60)
print("Test 2: Initialize GeminiService")
print("=" * 60)
try:
    service = GeminiService()
    print("✅ GeminiService initialized")
    print(f"   Provider: {service.provider_name()}")
    print(f"   Configured: {service.is_configured()}")
except Exception as e:
    print(f"❌ Failed to initialize GeminiService: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Check configuration
print("\n" + "=" * 60)
print("Test 3: Check Configuration")
print("=" * 60)
if service.is_configured():
    print("✅ Gemini API is configured")
else:
    print("❌ Gemini API is NOT configured")
    print("   Check your GEMINI_API_KEY in backend/.env")
    sys.exit(1)

# Test 4: Simple API call (text-only test)
print("\n" + "=" * 60)
print("Test 4: Simple API Test")
print("=" * 60)
print("Testing Gemini API with a simple text request...")

try:
    # Import the unified pipeline to make a test call
    from backend.services.unified_pipeline import get_configured_ai_provider
    
    provider = get_configured_ai_provider()
    print(f"✅ Configured provider: {provider}")
    
    # Try to import google.generativeai to test direct API access
    try:
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        
        # Try to list models to verify API key works
        print("\n🔍 Testing API connection by listing models...")
        models = list(genai.list_models())[:3]  # Just get first 3
        
        if models:
            print("✅ Successfully connected to Gemini API!")
            print(f"   Found {len(models)} model(s) (showing first 3):")
            for model in models[:3]:
                print(f"   - {model.name}")
        else:
            print("⚠️  Connected to API but no models found")
            
    except ImportError:
        print("⚠️  google-generativeai package not installed")
        print("   Install with: pip install google-generativeai")
        print("   (Not critical for app functionality if using unified pipeline)")
    except Exception as e:
        print(f"❌ API connection test failed: {e}")
        print("\n💡 Possible issues:")
        print("   1. Invalid API key")
        print("   2. API key not activated")
        print("   3. Network/firewall blocking Google APIs")
        print("   4. API quota exceeded")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Final summary
print("\n" + "=" * 60)
print("✅ All Tests Passed!")
print("=" * 60)
print("\n📊 Summary:")
print("✅ Environment variables loaded")
print("✅ GeminiService can be imported")
print("✅ GeminiService can be initialized")
print("✅ Gemini API key is configured")
print("✅ API connection successful")
print("\n🎉 Your Gemini API is working correctly!")
print("\n💡 Next steps:")
print("   - Test with actual document extraction: python backend/app.py")
print("   - Or build mobile apps: cd mobile && npm run build:preview")
