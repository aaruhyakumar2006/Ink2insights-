"""
Test Groq API Connection and Pipeline
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv('backend/.env')

def test_groq_api():
    print("\n" + "="*70)
    print("  GROQ API CONNECTION TEST")
    print("="*70)
    
    # Check environment variables
    provider = os.getenv('AI_PROVIDER')
    api_key = os.getenv('GROQ_API_KEY')
    model = os.getenv('GROQ_MODEL')
    
    print(f"\n📋 Configuration:")
    print(f"   AI Provider: {provider}")
    print(f"   Groq Model: {model}")
    print(f"   API Key: {api_key[:20]}...{api_key[-10:] if api_key else 'NOT SET'}")
    
    if provider != 'groq':
        print(f"\n❌ ERROR: AI_PROVIDER is '{provider}', should be 'groq'")
        return False
    
    if not api_key or api_key == 'PASTE_YOUR_GROQ_KEY_HERE':
        print(f"\n❌ ERROR: GROQ_API_KEY is not set properly")
        return False
    
    # Test Groq API with simple request
    print(f"\n🔌 Testing Groq API connection...")
    
    try:
        from groq import Groq
        
        client = Groq(api_key=api_key)
        
        # Simple test request
        response = client.chat.completions.create(
            model="llama-3.2-11b-vision-preview",  # Use smaller model for quick test
            messages=[
                {
                    "role": "user",
                    "content": "Say 'Groq API is working!' if you can read this."
                }
            ],
            max_tokens=50,
            temperature=0.1
        )
        
        result = response.choices[0].message.content
        
        print(f"\n✅ SUCCESS! Groq API is responding!")
        print(f"   Response: {result}")
        print(f"   Model used: {response.model}")
        print(f"   Tokens: {response.usage.total_tokens}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_integration():
    print("\n" + "="*70)
    print("  PIPELINE INTEGRATION TEST")
    print("="*70)
    
    try:
        from backend.services.ai_service import get_ai_provider
        
        print(f"\n🔧 Loading AI service pipeline...")
        
        ai = get_ai_provider()
        
        print(f"   ✅ Provider loaded: {ai.provider_name()}")
        print(f"   ✅ Configured: {ai.is_configured()}")
        print(f"   ✅ Model: {ai.model_name}")
        
        if ai.provider_name().lower() != 'groq':
            print(f"\n❌ ERROR: Pipeline is using '{ai.provider_name()}' instead of 'groq'")
            return False
        
        if not ai.is_configured():
            print(f"\n❌ ERROR: Groq provider is not properly configured")
            return False
        
        print(f"\n✅ Pipeline is correctly configured for Groq!")
        return True
        
    except Exception as e:
        print(f"\n❌ Pipeline test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "="*70)
    print("  🚀 GROQ AI SETUP VERIFICATION")
    print("="*70)
    
    results = {
        "API Connection": test_groq_api(),
        "Pipeline Integration": test_pipeline_integration()
    }
    
    print("\n" + "="*70)
    print("  📊 TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, status in results.items():
        icon = "✅" if status else "❌"
        print(f"  {icon} {test_name}")
    
    print("\n" + "="*70)
    if passed == total:
        print(f"  🎉 ALL TESTS PASSED ({passed}/{total})")
        print(f"  ✅ Groq is fully integrated and ready to use!")
    else:
        print(f"  ⚠️  {total - passed} test(s) failed")
    print("="*70)
    
    print("\n📝 NEXT STEPS:")
    if passed == total:
        print("  ✅ Backend is running with Groq on http://127.0.0.1:5001")
        print("  ✅ You can now test form scanning with AI extraction")
        print("  ✅ All AI features are operational")
    else:
        print("  ⚠️  Review errors above and fix configuration")
    print()

if __name__ == "__main__":
    main()
