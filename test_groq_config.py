"""
Test Groq API Configuration and Connection
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv('backend/.env')

def test_config():
    print("\n" + "="*70)
    print("  GROQ CONFIGURATION CHECK")
    print("="*70)
    
    provider = os.getenv('AI_PROVIDER')
    api_key = os.getenv('GROQ_API_KEY')
    model = os.getenv('GROQ_MODEL')
    
    print(f"\n📋 Environment Variables:")
    print(f"   ✅ AI_PROVIDER: {provider}")
    print(f"   ✅ GROQ_API_KEY: {'Set ✓' if api_key and api_key != 'PASTE_YOUR_GROQ_KEY_HERE' else '❌ NOT SET'}")
    print(f"   ✅ GROQ_MODEL: {model}")
    
    if provider != 'groq':
        print(f"\n❌ CRITICAL: AI_PROVIDER should be 'groq' but is '{provider}'")
        print("   Edit backend/.env and change AI_PROVIDER=gemini to AI_PROVIDER=groq")
        return False
    
    if not api_key or api_key == 'PASTE_YOUR_GROQ_KEY_HERE':
        print(f"\n❌ CRITICAL: GROQ_API_KEY is not set properly")
        print("   Edit backend/.env and add: GROQ_API_KEY=gsk_...your_key_here...")
        return False
    
    print(f"\n✅ Configuration is CORRECT!")
    print(f"   System is configured to use Groq AI")
    return True

def test_api():
    print("\n" + "="*70)
    print("  GROQ API CONNECTION TEST")
    print("="*70)
    
    api_key = os.getenv('GROQ_API_KEY')
    
    try:
        import requests
        
        # Test Groq API directly
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [{"role": "user", "content": "Say 'Groq API is working'"}],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        print(f"\n🔌 Testing Groq API connection...")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            print(f"\n✅ SUCCESS! Groq API is responding!")
            print(f"   Response: {content}")
            print(f"   Model: {result['model']}")
            print(f"   Tokens: {result['usage']['total_tokens']}")
            return True
        else:
            print(f"\n❌ API Error: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        return False

def test_pipeline():
    print("\n" + "="*70)
    print("  AI PIPELINE INTEGRATION TEST")
    print("="*70)
    
    try:
        from backend.services.ai_service import get_ai_provider
        
        ai = get_ai_provider()
        
        print(f"\n🔧 AI Service Status:")
        print(f"   ✅ Provider: {ai.provider_name()}")
        print(f"   ✅ Configured: {ai.is_configured()}")
        print(f"   ✅ Model: {ai.model_name}")
        
        if ai.provider_name().lower() != 'groq':
            print(f"\n❌ ERROR: Pipeline is using '{ai.provider_name()}' instead of 'groq'")
            return False
        
        if not ai.is_configured():
            print(f"\n❌ ERROR: Groq provider is not properly configured")
            return False
        
        print(f"\n✅ AI Pipeline is CORRECTLY integrated with Groq!")
        return True
        
    except Exception as e:
        print(f"\n❌ Pipeline test failed: {str(e)}")
        return False

def test_backend_health():
    print("\n" + "="*70)
    print("  BACKEND HEALTH CHECK")
    print("="*70)
    
    import requests
    
    try:
        response = requests.get("http://127.0.0.1:5001/api/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"\n✅ Backend is running!")
            print(f"   Status: {data.get('status')}")
            print(f"   Provider: {data.get('provider')}")
            print(f"   Model: {data.get('model')}")
            print(f"   Database: {data.get('database')}")
            
            if data.get('provider') != 'groq':
                print(f"\n❌ WARNING: Backend health shows provider as '{data.get('provider')}'")
                print("   Restart backend with: cd backend && python app.py")
            
            return True
        else:
            print(f"\n❌ Backend not responding: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"\n❌ Cannot connect to backend: {str(e)}")
        print("   Make sure backend is running on port 5001")
        return False

def main():
    print("\n" + "="*70)
    print("  🚀 COMPLETE GROQ INTEGRATION TEST")
    print("="*70)
    
    results = {
        "Configuration": test_config(),
        "API Connection": test_api(),
        "Pipeline Integration": test_pipeline(),
        "Backend Health": test_backend_health()
    }
    
    print("\n" + "="*70)
    print("  📊 FINAL STATUS")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, status in results.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {test_name}")
    
    print("\n" + "="*70)
    if passed == total:
        print(f"  🎉 ALL TESTS PASSED!")
        print(f"  ✅ Groq is fully configured and integrated")
        print(f"  ✅ Backend running on http://127.0.0.1:5001")
        print(f"  ✅ AI features are operational")
    else:
        print(f"  ⚠️  {total - passed} test(s) failed")
    print("="*70)
    
    print("\n🎯 NEXT ACTIONS:")
    if passed == total:
        print("  1. Test form scanning with AI extraction")
        print("  2. Upload a medical form image")
        print("  3. Verify AI can extract patient data")
    else:
        print("  Fix the failed tests above first")
    print()

if __name__ == "__main__":
    main()
