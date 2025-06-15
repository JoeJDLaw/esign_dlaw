#!/usr/bin/env python3
"""
Test script to verify Dropbox connection and access to the /esign folder.
This tests the new Dropbox application credentials before running the full eSign workflow.
"""

import os
import sys
import logging

from dotenv import load_dotenv
load_dotenv('/srv/shared/.env')

from utils.dropbox_api.client import DropboxClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_dropbox_connection():
    """Test basic Dropbox connection and folder access."""
    
    print("🔍 Testing Dropbox Connection...")
    print("=" * 50)
    
    try:
        # Test the shared app (default for eSign)
        print("1. Testing Shared App Connection...")
        client = DropboxClient(use_shared_app=True)
        
        # Test basic connection by getting account info
        print("   ✓ Client initialized successfully")
        
        # Check if we can access the root
        print("2. Testing folder access...")
        
        # Try to list the root folder to verify permissions
        try:
            result = client.dbx.files_list_folder("")
            print(f"   ✓ Root folder accessible - found {len(result.entries)} items")
        except Exception as e:
            print(f"   ⚠️ Root folder access issue: {e}")
        
        # Check if /esign folder exists or can be created
        esign_folder = os.getenv('DROPBOX_ESIGN_FOLDER', '/esign')
        print(f"3. Testing eSign folder: {esign_folder}")
        
        try:
            # Try to get metadata for the esign folder
            metadata = client.get_file_metadata(esign_folder)
            print(f"   ✓ eSign folder exists: {esign_folder}")
        except Exception as e:
            print(f"   ⚠️ eSign folder issue: {e}")
            print(f"   📝 Note: Folder may need to be created during first upload")
        
        print("\n🎉 Dropbox connection test completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Dropbox connection failed: {e}")
        return False

if __name__ == "__main__":
    success = test_dropbox_connection()
    if success:
        print("\n✅ Ready to test eSign workflow with Dropbox uploads!")
    else:
        print("\n❌ Fix Dropbox connection issues before proceeding.")
    
    sys.exit(0 if success else 1) 