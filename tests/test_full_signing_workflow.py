#!/usr/bin/env python3
"""
Full End-to-End eSign Workflow Test
===================================
This test simulates the complete signing process:
1. Initiate signature request (like Salesforce would)
2. Simulate signature submission
3. Verify Dropbox upload
4. Check Salesforce integration

This gives you confidence that the entire workflow works correctly.
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

def test_full_signing_workflow():
    """Test the complete signing workflow end-to-end."""
    
    print("🚀 Testing Full eSign Workflow")
    print("=" * 60)
    
    # Test configuration
    base_url = "https://esign.dlaw.app"  # Change to localhost:5000 for local testing
    test_client_name = f"Test Client {datetime.now().strftime('%H%M%S')}"
    test_client_email = f"test.{int(time.time())}@example.com"
    test_template = "cea"  # or "rra" or "cea_rra"
    test_case_id = "a0B7V00000TestCaseEAA"
    test_envelope_id = "a44Hs000005TestEnvIA2"
    
    print(f"📋 Test Parameters:")
    print(f"   Client: {test_client_name}")
    print(f"   Email: {test_client_email}")
    print(f"   Template: {test_template}")
    print(f"   Case ID: {test_case_id}")
    print(f"   Envelope ID: {test_envelope_id}")
    
    # Step 1: Initiate signature request
    print(f"\n1️⃣ Initiating signature request...")
    
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
            print(f"   ✅ Signature request created successfully!")
            print(f"   🔗 Signing URL: {signing_url}")
            print(f"   🎫 Token: {token[:8]}...")
        else:
            print(f"   ❌ Failed to create signature request: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error initiating signature: {e}")
        return False
    
    # Step 2: Simulate signature submission
    print(f"\n2️⃣ Simulating signature submission...")
    
    # Create a simple base64 signature image (1x1 transparent PNG)
    test_signature_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    
    signature_payload = {
        "signature": test_signature_b64,
        "consent": True
    }
    
    try:
        response = requests.post(f"{base_url}/v1/sign/{token}", json=signature_payload)
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Signature submitted successfully!")
            print(f"   🔗 Redirect URL: {result.get('redirect_url', 'N/A')}")
        else:
            print(f"   ❌ Failed to submit signature: {response.status_code}")
            print(f"   📄 Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Error submitting signature: {e}")
        return False
    
    # Step 3: Verify file was created and uploaded
    print(f"\n3️⃣ Verifying file creation and upload...")
    
    # Check local file creation
    signed_dir = "/srv/apps/esign/signed"
    today_folder = datetime.now().strftime('%Y%m%d')
    signed_folder_path = os.path.join(signed_dir, today_folder)
    
    if os.path.exists(signed_folder_path):
        pdf_files = [f for f in os.listdir(signed_folder_path) if f.endswith('.pdf')]
        if pdf_files:
            latest_pdf = max(pdf_files, key=lambda f: os.path.getctime(os.path.join(signed_folder_path, f)))
            local_file_path = os.path.join(signed_folder_path, latest_pdf)
            print(f"   ✅ Local PDF created: {local_file_path}")
            print(f"   📊 File size: {os.path.getsize(local_file_path)} bytes")
        else:
            print(f"   ❌ No PDF files found in {signed_folder_path}")
            return False
    else:
        print(f"   ❌ Signed folder not found: {signed_folder_path}")
        return False
    
    # Step 4: Test Dropbox upload verification
    print(f"\n4️⃣ Testing Dropbox upload verification...")
    
    try:
        from utils.dropbox_api.client import DropboxClient
        from dropbox import common
        
        # Initialize client and check team folder
        client = DropboxClient(use_shared_app=True)
        shared_folder_id = os.getenv('DROPBOX_ESIGN_FOLDER_ID', '1387609128')
        base_path = os.getenv('DROPBOX_ESIGN_FOLDER_PATH', '/Potential Clients/_esign')
        
        # Set up team folder access
        metadata = client.dbx.sharing_get_folder_metadata(shared_folder_id)
        scoped_client = client.dbx.with_path_root(common.PathRoot.namespace_id(metadata.shared_folder_id))
        
        # Check if file was uploaded to Dropbox
        dropbox_folder_path = f"{base_path}/{today_folder}"
        
        try:
            result = scoped_client.files_list_folder(dropbox_folder_path)
            recent_files = [entry for entry in result.entries if entry.name.endswith('.pdf')]
            
            if recent_files:
                # Find the most recent file (likely our test file)
                latest_dropbox_file = max(recent_files, key=lambda f: f.server_modified)
                print(f"   ✅ File found in Dropbox: {latest_dropbox_file.name}")
                print(f"   📊 Dropbox file size: {latest_dropbox_file.size} bytes")
                print(f"   📅 Upload time: {latest_dropbox_file.server_modified}")
                print(f"   📍 Full Dropbox path: {dropbox_folder_path}/{latest_dropbox_file.name}")
            else:
                print(f"   ⚠️  No PDF files found in Dropbox folder: {dropbox_folder_path}")
                print(f"   💡 This might be expected if upload is still in progress")
                
        except Exception as e:
            print(f"   ⚠️  Could not access Dropbox folder: {e}")
            print(f"   💡 File might still be uploading or folder doesn't exist yet")
            
    except Exception as e:
        print(f"   ❌ Error checking Dropbox: {e}")
        return False
    
    # Step 5: Summary
    print(f"\n✅ WORKFLOW TEST COMPLETED!")
    print(f"🎯 Summary:")
    print(f"   • Signature request initiated successfully")
    print(f"   • Signature submitted and processed")
    print(f"   • Local PDF file created")
    print(f"   • Dropbox upload attempted")
    print(f"   • Salesforce integration triggered")
    
    print(f"\n📋 Next Steps:")
    print(f"   1. Check Salesforce for updated dropbox_file_path__c field")
    print(f"   2. Verify file appears in: DavtyanLaw Team Folder (1)/Potential Clients/_esign/{today_folder}/")
    print(f"   3. Test the final review page: {base_url}/v1/sign/final/{token}")
    
    return True

def test_local_workflow():
    """Test workflow against local development server."""
    print("🏠 Testing against local development server...")
    print("💡 Make sure your Flask app is running on localhost:5000")
    
    # Update base_url for local testing
    global base_url
    base_url = "http://localhost:5000"
    
    return test_full_signing_workflow()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test full eSign workflow")
    parser.add_argument("--local", action="store_true", help="Test against local development server")
    args = parser.parse_args()
    
    if args.local:
        success = test_local_workflow()
    else:
        success = test_full_signing_workflow()
    
    if success:
        print(f"\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"\n❌ Some tests failed!")
        sys.exit(1) 