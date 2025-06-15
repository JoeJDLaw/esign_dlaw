#!/usr/bin/env python3
"""
Generate Test Signing URL for Manual UI Testing
===============================================
This script creates a real signing URL that you can click through manually
to test the UI without writing to Salesforce (uses fake IDs).
"""

import os
import sys
import json
import time
import hmac
import hashlib
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/srv/shared/.env')

# Add paths for imports
sys.path.insert(0, '/srv/shared')
sys.path.insert(0, '/srv/apps/esign')

def generate_hmac_signature(body: str, timestamp: str) -> str:
    """Generate HMAC signature for API authentication."""
    sf_secret_key = os.environ["SF_SECRET_KEY"].encode()
    message = f"{timestamp}{body}".encode()
    return hmac.new(sf_secret_key, message, hashlib.sha256).hexdigest()

def generate_test_signing_url():
    """Generate a real signing URL for manual testing."""
    
    print("🔗 Generating Test Signing URL for Manual UI Testing")
    print("=" * 60)
    print("💡 This creates a real signing URL but uses fake Salesforce IDs")
    print("💡 Safe to test - won't write to real Salesforce records")
    
    # Test configuration
    base_url = "https://esign.dlaw.app"  # Change to localhost:5000 for local testing
    test_client_name = f"UI Test User {datetime.now().strftime('%H%M%S')}"
    test_client_email = f"ui.test.{int(time.time())}@example.com"
    test_template = "cea"  # or "rra" or "cea_rra"
    # Use fake IDs that won't exist in Salesforce
    test_case_id = "a0B7V00000UITestCaseEAA"
    test_envelope_id = "a44Hs000005UITestEnvIA2"
    
    print(f"\n📋 Test Parameters:")
    print(f"   Client: {test_client_name}")
    print(f"   Email: {test_client_email}")
    print(f"   Template: {test_template}")
    print(f"   Case ID: {test_case_id} (fake - won't exist in SF)")
    print(f"   Envelope ID: {test_envelope_id} (fake - won't exist in SF)")
    
    # Create signature request
    print(f"\n1️⃣ Creating signature request...")
    
    timestamp = str(int(time.time()))
    body = json.dumps({
        "template_type": test_template,
        "client_name": test_client_name,
        "client_email": test_client_email,
        "salesforce_case_id": test_case_id,
        "envelope_document_id": test_envelope_id
    })
    
    signature = generate_hmac_signature(body, timestamp)
    
    headers = {
        "Content-Type": "application/json",
        "X-Timestamp": timestamp,
        "X-Signature": signature
    }
    
    try:
        response = requests.post(f"{base_url}/api/v1/initiate", headers=headers, data=body)
        
        if response.status_code == 201:
            result = response.json()
            signing_url = result["signing_url"]
            token = result["token"]
            expires_at = result["expires_at"]
            
            print(f"   ✅ Signature request created successfully!")
            print(f"   🎫 Token: {token[:8]}...")
            print(f"   📅 Expires: {expires_at}")
            
            print(f"\n🔗 **SIGNING URL FOR MANUAL TESTING:**")
            print(f"   {signing_url}")
            print(f"\n📋 **TESTING INSTRUCTIONS:**")
            print(f"   1. Click the URL above")
            print(f"   2. Review the document preview")
            print(f"   3. Check the consent checkbox")
            print(f"   4. Draw a signature")
            print(f"   5. Click 'Sign Document'")
            print(f"   6. Wait for processing (PDF generation, Dropbox upload)")
            print(f"   7. Review the final document page")
            print(f"   8. Test the 'Download PDF' button")
            print(f"   9. Test the 'Finish' button and modal")
            print(f"   10. Verify redirect to https://d.law")
            
            print(f"\n⚠️  **WHAT HAPPENS DURING TESTING:**")
            print(f"   ✅ PDF will be generated and saved locally")
            print(f"   ✅ File will be uploaded to Dropbox team folder")
            print(f"   ⚠️  Salesforce updates will fail gracefully (expected)")
            print(f"   ✅ Webhook notifications will be sent (if enabled)")
            print(f"   ✅ Complete audit trail will be recorded")
            
            print(f"\n🎯 **UI ELEMENTS TO TEST:**")
            print(f"   • Document preview iframe")
            print(f"   • Signature pad functionality")
            print(f"   • Button states (disabled during processing)")
            print(f"   • Loading message display")
            print(f"   • Final review page layout")
            print(f"   • Download button functionality")
            print(f"   • Thank you modal appearance")
            print(f"   • Mobile responsiveness")
            
            return signing_url
            
        else:
            print(f"   ❌ Failed to create signature request: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error creating signature request: {e}")
        return None

if __name__ == "__main__":
    generate_test_signing_url() 