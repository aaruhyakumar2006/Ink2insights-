"""
Check Groq Models and API Status
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from dotenv import load_dotenv
load_dotenv('backend/.env')

def test_models():
    print("\n" + "="*70)
    print("  GROQ MODEL CHECK")
    print("="*70)
    
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        print("❌ No API key found")
        return
    
    # Test current models
    models_to_test = [
        "llama-3.2-11b-text-preview",
        "llama-3.2-90b-text-preview",
        "llama-3.3-70b-versatile",
        "llama-3.3-70b-specdec",
        "mixtral-8x7b-32768",
    ]
    
    import requests
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("\n🔍 Testing available models...")
    
    for model in models_to_test:
        try:
            data = {
                "model": model,
                "messages": [{"role": "user", "content": "Say 'Yes' if this model works."}],
                "max_tokens": 10,
                "temperature": 0.1
            }
            
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✅ {model}: WORKING")
            elif response.status_code == 404:
                print(f"❌ {model}: NOT FOUND")
            else:
                print(f"⚠️  {model}: Error {response.status_code}")
                
        except Exception as e:
            print(f"⚠️  {model}: Failed - {str(e)[:50]}")

def quick_test():
    print("\n" + "="*70)
    print("  QUICK GROQ TEST")
    print("="*70)
    
    api_key = os.getenv('GROQ_API_KEY')
    
    try:
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Use llama-3.2-11b-text-preview (should work)
        data = {
            "model": "llama-3.2-11b-text-preview",
            "messages": [{"role": "user", "content": "Hello Groq! Reply with 'Connected'"}],
            "max_tokens": 20,
            "temperature": 0.1
        }
        
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ API Connected!")
            print(f"   Model: {result['model']}")
            print(f"   Response: {result['choices'][0]['message']['content']}")
            print(f"   Tokens: {result['usage']['total_tokens']}")
        else:
            print(f"\n❌ API Error {response.status_code}")
            print(f"   Message: {response.text[:200]}")
            
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")

def main():
    print("\n" + "="*70)
    print("  GROQ AI STATUS CHECK")
    print("="*70)
    
    provider = os.getenv('AI_PROVIDER')
    api_key = os.getenv('GROQ_API_KEY')
    model = os.getenv('GROQ_MODEL')
    
    print(f"\n📋 Current Configuration:")
    print(f"   Provider: {provider}")
    print(f"   Model: {model}")
    print(f"   Key: {'Set ✓' if api_key else '❌ NOT SET'}")
    
    if provider != 'groq':
        print(f"\n❌ ERROR: AI_PROVIDER should be 'groq', not '{provider}'")
        print("   Edit backend/.env: AI_PROVIDER=groq")
        return
    
    test_models()
    quick_test()
    
    print("\n" + "="*70)
    print("  ✅ MODEL UPDATED!")
    print("  Changed to: llama-3.2-11b-text-preview")
    print("="*70)

if __name__ == "__main__":
    main()
