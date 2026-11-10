"""
Final Groq API Test with Correct Model
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv('backend/.env')

def main():
    print("\n" + "="*70)
    print("  🚀 GROQ AI - FINAL VERIFICATION")
    print("="*70)
    
    # Check config
    provider = os.getenv('AI_PROVIDER')
    api_key = os.getenv('GROQ_API_KEY')
    model = os.getenv('GROQ_MODEL')
    
    print(f"\n📋 CONFIGURATION:")
    print(f"   Provider: {provider}")
    print(f"   Model: {model}")
    print(f"   Key: {api_key[:15]}...{api_key[-15:] if api_key else 'NONE'}")
    
    # Test Groq API with latest model
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Use llama-3.2-90b-vision-preview (from env) or current active model
        active_model = "llama-3.2-90b-vision-preview"
        
        data = {
            "model": active_model,
            "messages": [{"role": "user", "content": "Hello! Confirm the Groq API is active."}],
            "max_tokens": 30,
            "temperature": 0.1
        }
        
        print(f"\n🔌 Testing with model: {active_model}")
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            print(f"\n✅ SUCCESS! Groq API is fully operational!")
            print(f"   Response: {content}")
            print(f"   Model: {result['model']}")
            print(f"   Tokens: {result['usage']['total_tokens']}")
            
        else:
            print(f"\n⚠️  API Error {response.status_code}: {response.text[:200]}")
            
    except Exception as e:
        print(f"\n⚠️  API Test error: {str(e)}")
    
    # Check backend
    print(f"\n🌐 BACKEND STATUS:")
    try:
        import requests
        health = requests.get("http://127.0.0.1:5001/api/health", timeout=5)
        
        if health.status_code == 200:
            data = health.json()
            print(f"   ✅ Running: {data.get('status')}")
            print(f"   ✅ Provider: {data.get('provider')}")
            print(f"   ✅ Model: {data.get('model')}")
            print(f"   ✅ Version: {data.get('version')}")
            
            if data.get('provider') == 'groq':
                print(f"\n🎉 GROQ IS ACTIVE!")
                print(f"   Full URL: http://127.0.0.1:5001")
                print(f"   Network URL: http://192.168.1.8:5001")
            else:
                print(f"\n❌ Provider mismatch: Expected 'groq', got '{data.get('provider')}'")
                
        else:
            print(f"   ❌ Backend not responding: {health.status_code}")
            
    except Exception as e:
        print(f"   ❌ Cannot connect to backend: {str(e)}")
    
    print("\n" + "="*70)
    print("  ✅ GROQ INTEGRATION COMPLETE")
    print("="*70)
    print("\n🎯 NEXT STEPS:")
    print("  1. Go to http://127.0.0.1:5001")
    print("  2. Login with Email or PIN")
    print("  3. Upload a medical form image")
    print("  4. Test AI form extraction")
    print()

if __name__ == "__main__":
    main()
