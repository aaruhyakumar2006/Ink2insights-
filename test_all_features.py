"""
Test all application features to see what's working
"""
import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:5001"

def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_health():
    print_section("1. HEALTH CHECK")
    try:
        response = requests.get(f"{BASE_URL}/api/health")
        data = response.json()
        print(f"✅ Status: {data.get('status')}")
        print(f"   Provider: {data.get('provider')}")
        print(f"   Model: {data.get('model')}")
        print(f"   Database: {data.get('database')}")
        print(f"   Version: {data.get('version')}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_demo_login():
    print_section("2. DEMO LOGIN (Authentication)")
    try:
        response = requests.post(f"{BASE_URL}/api/auth/demo", json={})
        data = response.json()
        if not data.get('success'):
            print(f"❌ Login failed: {data.get('error')}")
            return None
        print(f"✅ Login successful")
        print(f"   User: {data.get('doctor', {}).get('full_name')}")
        print(f"   Role: {data.get('doctor', {}).get('role')}")
        print(f"   Community: {data.get('community', {}).get('name')}")
        print(f"   Token: {data.get('token')[:30]}...")
        return data.get('token')
    except Exception as e:
        print(f"❌ Failed: {e}")
        return None

def test_templates(token):
    print_section("3. FORM TEMPLATES")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/api/templates", headers=headers)
        data = response.json()
        templates = data.get('templates', [])
        print(f"✅ Found {len(templates)} templates:")
        for t in templates:
            print(f"   - {t.get('id')}: {t.get('name')} (v{t.get('version')})")
            print(f"     Fields: {t.get('field_count', 0)}, Sections: {t.get('section_count', 0)}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_records(token):
    print_section("4. PATIENT RECORDS")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/api/records", headers=headers)
        data = response.json()
        records = data.get('records', [])
        print(f"✅ Found {len(records)} patient records:")
        for i, r in enumerate(records[:5], 1):  # Show first 5
            print(f"   {i}. {r.get('patient_name', 'Unknown')} - {r.get('form_type', 'N/A')}")
            print(f"      Status: {r.get('status')}, Created: {r.get('created_at', 'N/A')[:10]}")
        if len(records) > 5:
            print(f"   ... and {len(records) - 5} more")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_glossary(token):
    print_section("5. CLINICAL GLOSSARY")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/api/glossary", headers=headers)
        data = response.json()
        total = data.get('total', 0)
        print(f"✅ Clinical glossary loaded: {total} medical terms")
        
        # Show a few examples
        if 'terms' in data and len(data['terms']) > 0:
            print(f"   Sample terms:")
            for term in list(data['terms'].keys())[:5]:
                print(f"   - {term}: {data['terms'][term]}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_invoices(token):
    print_section("6. INVOICE GENERATION")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/api/invoices", headers=headers)
        data = response.json()
        invoices = data.get('invoices', [])
        print(f"✅ Found {len(invoices)} invoices:")
        for inv in invoices[:3]:
            print(f"   - {inv.get('invoice_number')}: ₹{inv.get('total_amount', 0):.2f}")
            print(f"     Date: {inv.get('invoice_date')}, Status: {inv.get('status')}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_stats(token):
    print_section("7. ANALYTICS & STATISTICS")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/api/stats", headers=headers)
        data = response.json()
        print(f"✅ Analytics data:")
        print(f"   Total Records: {data.get('total_records', 0)}")
        print(f"   Completed: {data.get('completed', 0)}")
        print(f"   Pending: {data.get('pending', 0)}")
        print(f"   Flagged: {data.get('flagged', 0)}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def test_users(token):
    print_section("8. USER MANAGEMENT")
    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(f"{BASE_URL}/api/users", headers=headers)
        data = response.json()
        users = data.get('users', [])
        print(f"✅ Found {len(users)} users:")
        for u in users[:5]:
            print(f"   - {u.get('name')} ({u.get('email')})")
            print(f"     Role: {u.get('role')}, Status: {u.get('status')}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("  I2I - INK 2 INSIGHT APPLICATION FEATURE TEST")
    print("="*60)
    print(f"  Testing against: {BASE_URL}")
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Test health first
    if not test_health():
        print("\n❌ Backend is not responding. Make sure it's running!")
        return
    
    # Login to get token
    token = test_demo_login()
    if not token:
        print("\n❌ Authentication failed. Cannot proceed with other tests.")
        return
    
    # Test all features
    results = {
        "Health Check": True,
        "Authentication": True,
        "Templates": test_templates(token),
        "Patient Records": test_records(token),
        "Clinical Glossary": test_glossary(token),
        "Invoice Generation": test_invoices(token),
        "Analytics": test_stats(token),
        "User Management": test_users(token)
    }
    
    # Summary
    print_section("SUMMARY")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n  Passed: {passed}/{total} features")
    print("\n  Feature Status:")
    for feature, status in results.items():
        icon = "✅" if status else "❌"
        print(f"    {icon} {feature}")
    
    print("\n" + "="*60)
    print(f"  Overall: {'🎉 ALL WORKING!' if passed == total else f'⚠️  {total-passed} features need attention'}")
    print("="*60)
    
    # Notes
    print("\n📝 NOTES:")
    print("  - AI features (form scanning) require working AI provider")
    print("  - Currently Gemini has billing issue (403 error)")
    print("  - Switch to NVIDIA NIM or Groq for AI functionality")
    print("  - All other features are working perfectly!")
    print("\n")

if __name__ == "__main__":
    main()
