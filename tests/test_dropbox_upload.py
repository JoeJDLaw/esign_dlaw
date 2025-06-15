#!/usr/bin/env python3
"""
Test script to verify Dropbox file upload using an existing signed PDF.
This tests the upload functionality before running the full eSign workflow.
"""

import os
import sys
import logging
import argparse
from datetime import datetime

from dotenv import load_dotenv
load_dotenv('/srv/shared/.env')

from utils.dropbox_api.client import DropboxClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_folder_access():
    """Smoke test to verify Dropbox folder access."""
    
    print("🔍 Testing Dropbox Folder Access...")
    print("=" * 50)
    
    try:
        # Initialize Dropbox client
        print("1. Initializing Dropbox client...")
        client = DropboxClient(use_shared_app=True)
        print("   ✓ Client initialized")
        
        # Define Dropbox path using complete esign folder path
        esign_folder = os.getenv('DROPBOX_ESIGN_FOLDER', 'DavtyanLaw Team Folder (1)/Potential Clients/esign')
        
        # Smoke test: Check if we can access the esign folder
        print(f"2. Testing access to esign folder: /{esign_folder}")
        try:
            # Try to get metadata or list contents of the esign folder
            try:
                metadata = client.get_file_metadata(f"/{esign_folder}")
                print(f"   ✓ eSign folder exists and is accessible")
                print(f"   📁 Folder type: {type(metadata).__name__}")
            except Exception:
                # If folder doesn't exist, try to list its parent to see if we have access to the team folder
                parent_path = "/".join(esign_folder.split("/")[:-1])
                print(f"   📁 eSign folder doesn't exist yet, checking parent: /{parent_path}")
                result = client.dbx.files_list_folder(f"/{parent_path}")
                print(f"   ✓ Parent folder accessible - found {len(result.entries)} items")
                print(f"   💡 eSign folder will be created automatically on first upload")
        except Exception as e:
            print(f"   ❌ Cannot access folder structure: {e}")
            print(f"   💡 Check team folder permissions for sf_integrations account")
            return False
            
        print(f"\n🎉 Folder access test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Folder access test failed: {e}")
        return False

def test_dropbox_upload():
    """Test uploading an existing signed PDF to Dropbox."""
    
    print("📤 Testing Dropbox Upload...")
    print("=" * 50)
    
    # Find the most recent signed PDF
    signed_dir = "/srv/apps/esign/signed"
    test_file = None
    
    # Look for the most recent file
    for date_dir in sorted(os.listdir(signed_dir), reverse=True):
        date_path = os.path.join(signed_dir, date_dir)
        if os.path.isdir(date_path):
            files = [f for f in os.listdir(date_path) if f.endswith('.pdf')]
            if files:
                # Get the most recent file in this directory
                latest_file = sorted(files)[-1]
                test_file = os.path.join(date_path, latest_file)
                break
    
    if not test_file:
        print("❌ No signed PDF files found for testing")
        return False
    
    print(f"📄 Using test file: {os.path.basename(test_file)}")
    print(f"   Size: {os.path.getsize(test_file)} bytes")
    
    try:
        # Initialize Dropbox client
        print("1. Initializing Dropbox client...")
        client = DropboxClient(use_shared_app=True)
        print("   ✓ Client initialized")
        
        # Define Dropbox path using complete esign folder path
        esign_folder = os.getenv('DROPBOX_ESIGN_FOLDER', 'DavtyanLaw Team Folder (1)/Potential Clients/esign')
        date_folder = datetime.now().strftime('%Y%m%d')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        dropbox_filename = f"test_upload_{timestamp}_{os.path.basename(test_file)}"
        dropbox_path = f"/{esign_folder}/{date_folder}/{dropbox_filename}"
        
        print(f"2. Uploading to Dropbox path: {dropbox_path}")
        
        # Upload the file
        client.upload_file(dropbox_path, test_file)
        print("   ✓ Upload completed successfully!")
        
        # Verify the file exists
        print("3. Verifying upload...")
        metadata = client.get_file_metadata(dropbox_path)
        print(f"   ✓ File verified in Dropbox")
        print(f"   📊 Dropbox file size: {metadata.size} bytes")
        print(f"   📅 Upload time: {metadata.server_modified}")
        
        print(f"\n🎉 Upload test completed successfully!")
        print(f"📍 File location: {dropbox_path}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Upload test failed: {e}")
        logger.exception("Upload test failed")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Dropbox integration for eSign workflow")
    parser.add_argument("--smoke-test", action="store_true", 
                       help="Run only the folder access smoke test")
    
    args = parser.parse_args()
    
    if args.smoke_test:
        # Run only the smoke test
        success = test_folder_access()
        if success:
            print("\n✅ Folder access working! Ready for full upload test.")
        else:
            print("\n❌ Fix folder access issues before proceeding.")
    else:
        # Run the full upload test
        success = test_dropbox_upload()
        if success:
            print("\n✅ Dropbox upload functionality working! Ready for full workflow test.")
        else:
            print("\n❌ Fix upload issues before proceeding to full workflow.")
    
    sys.exit(0 if success else 1) 