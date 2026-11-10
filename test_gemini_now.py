"""
Quick test to verify Gemini API is working
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from services.gemini_service import GeminiService

def test_gemini():
    print("Testing Gemini API...")
    api_key = os.getenv('GEMINI_API_KEY', 'NOT SET')
    print(f"API Key: {api_key[:20]}...")
    
    # Test using google.generativeai directly
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content("Say 'Hello from Gemini!' if you can read this.")
        
        print("\n✅ SUCCESS! Gemini API is working!")
        print(f"Response: {response.text[:200]}")
        return True
        
    except Exception as e:
        print(f"\n❌ FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv('backend/.env')
    
    success = test_gemini()
    sys.exit(0 if success else 1)
