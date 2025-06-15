#!/usr/bin/env python3
"""
Test script to verify the new team folder integration works with real signed PDFs.
This tests the updated upload_file_to_team_folder() function.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/srv/shared/.env')

# Add paths for imports
sys.path.insert(0, '/srv/shared')
sys.path.insert(0, '/srv/apps/esign')

from utils.dropbox_api.upload_file import upload_file_to_team_folder

def test_team_folder_integration():
    """Test the new team folder integration with a real signed PDF."""
    
    print("🔧 Testing Team Folder Integration...")
    print("=" * 60)
    
    # Find a real signed PDF to test with
    signed_dir = "/srv/apps/esign/signed"
    test_file = None
    
    print("1. Looking for existing signed PDFs...")
    if os.path.exists(signed_dir):
        # Look for dated folders
        for date_folder in sorted(os.listdir(signed_dir), reverse=True):
            date_path = os.path.join(signed_dir, date_folder)
            if os.path.isdir(date_path):
                # Look for PDF files in this date folder
                for filename in os.listdir(date_path):
                    if filename.endswith('.pdf'):
                        test_file = os.path.join(date_path, filename)
                        print(f"   📄 Found test file: {test_file}")
                        break
                if test_file:
                    break
    
    if not test_file:
        print("   ❌ No signed PDFs found for testing")
        return False
    
    # Test the upload
    print("2. Testing upload to team folder...")
    try:
        # Use a test filename to avoid overwriting
        test_filename = f"test_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(test_file)}"
        
        success, dropbox_path = upload_file_to_team_folder(
            local_path=test_file,
            filename=test_filename
        )
        
        if success:
            print(f"   ✅ Upload successful!")
            print(f"   📍 Dropbox path: {dropbox_path}")
            print(f"   📊 Local file size: {os.path.getsize(test_file)} bytes")
            
            # Show what would be saved to Salesforce
            print(f"\n🎯 Salesforce Integration Preview:")
            print(f"   dropbox_file_path__c: {dropbox_path}")
            print(f"   (This replaces the local path: {test_file})")
            
            return True
        else:
            print(f"   ❌ Upload failed")
            return False
            
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        return False

def test_configuration():
    """Test that the required environment variables are set."""
    
    print("\n3. Testing configuration...")
    
    required_vars = [
        'DROPBOX_ESIGN_FOLDER_ID',
        'DROPBOX_ESIGN_FOLDER_PATH'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"   ✅ {var}: {value}")
        else:
            print(f"   ❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables. Add to .env:")
        print(f"   DROPBOX_ESIGN_FOLDER_ID=1387609128")
        print(f"   DROPBOX_ESIGN_FOLDER_PATH=/Potential Clients/_esign")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting Team Folder Integration Test\n")
    
    config_ok = test_configuration()
    if not config_ok:
        print("\n❌ Configuration test failed")
        sys.exit(1)
    
    integration_ok = test_team_folder_integration()
    
    if integration_ok:
        print(f"\n✅ INTEGRATION TEST PASSED!")
        print(f"🎉 The eSign application is ready to use team folder uploads!")
        print(f"\n📋 Next Steps:")
        print(f"   1. The eSign app will now upload to: DavtyanLaw Team Folder (1)/Potential Clients/_esign/")
        print(f"   2. Salesforce will receive Dropbox paths instead of local paths")
        print(f"   3. Files are organized by date: YYYYMMDD/filename.pdf")
    else:
        print(f"\n❌ Integration test failed")
        sys.exit(1) 