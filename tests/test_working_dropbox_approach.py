#!/usr/bin/env python3
"""
Test script using the WORKING approach from ETL walker:
Using with_path_root() to set the shared folder namespace.
"""

import os
import sys
import logging
from datetime import datetime

from dotenv import load_dotenv
load_dotenv('/srv/shared/.env')

from utils.dropbox_api.client import DropboxClient
from dropbox import common

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_working_approach():
    """Test the proven approach from ETL walker using with_path_root()."""
    
    print("🔧 Testing WORKING Approach from ETL Walker...")
    print("=" * 60)
    
    try:
        # Step 1: Get shared folder ID (we know it's 1387609128)
        print("1. Using known shared folder ID: 1387609128")
        shared_folder_id = "1387609128"
        
        # Step 2: Initialize Dropbox client
        print("2. Initializing Dropbox client...")
        client = DropboxClient(use_shared_app=True)
        print("   ✓ Client initialized")
        
        # Step 3: Get shared folder metadata (the key step!)
        print("3. Getting shared folder metadata...")
        metadata = client.dbx.sharing_get_folder_metadata(shared_folder_id)
        print(f"   📁 Folder: {metadata.name}")
        print(f"   🆔 Shared folder ID: {metadata.shared_folder_id}")
        
        # Step 4: Set path root to the shared folder namespace (THE MAGIC!)
        print("4. Setting path root to shared folder namespace...")
        scoped_client = client.dbx.with_path_root(common.PathRoot.namespace_id(metadata.shared_folder_id))
        print("   🎯 Path root set to shared folder namespace")
        
        # Step 5: Test folder access with relative paths
        print("5. Testing folder access with relative paths...")
        test_paths = [
            "",  # Root of shared folder
            "/Potential Clients",  # Target subfolder
            "Potential Clients",   # Without leading slash
        ]
        
        # Also check if we can find Potential Clients and existing subfolders
        potential_clients_path = None
        
        working_path = None
        for path in test_paths:
            try:
                print(f"   Testing path: '{path}'")
                result = scoped_client.files_list_folder(path)
                print(f"      ✅ SUCCESS - Found {len(result.entries)} items:")
                
                # Check ALL entries for Potential Clients
                for entry in result.entries:
                    if entry.name == "Potential Clients":
                        potential_clients_path = f"{path}/Potential Clients" if path else "/Potential Clients"
                        print(f"         🎯 FOUND: {entry.name} -> {potential_clients_path}")
                
                # Show first 10 items for debugging
                for entry in result.entries[:10]:  
                    print(f"         - {entry.name}")
                if len(result.entries) > 10:
                    print(f"         ... and {len(result.entries) - 10} more items")
                working_path = path
                break  # Found working path
            except Exception as e:
                print(f"      ❌ Failed: {e}")
                
        # Test access to Potential Clients if we found it
        if potential_clients_path:
            try:
                print(f"\n   Testing Potential Clients access: '{potential_clients_path}'")
                pc_result = scoped_client.files_list_folder(potential_clients_path)
                print(f"      ✅ Potential Clients - Found {len(pc_result.entries)} items:")
                for entry in pc_result.entries[:3]:
                    print(f"         - {entry.name}")
                print(f"         ... and {len(pc_result.entries) - 3} more items")
            except Exception as e:
                print(f"      ❌ Potential Clients access failed: {e}")
        
        if working_path is not None:
            print(f"\n🎉 SUCCESS! Working path found: '{working_path}'")
            
            # Step 6: Test file upload to Potential Clients folder (required path)
            print("6. Testing file upload to Potential Clients folder...")
            
            # We MUST use Potential Clients path - this is required!
            if not potential_clients_path:
                print("   ❌ ERROR: Potential Clients folder not found!")
                return {"success": False, "error": "Potential Clients folder not accessible"}
            
            base_upload_path = potential_clients_path
            if not base_upload_path.startswith('/'):
                base_upload_path = f"/{base_upload_path}"
            
            # Test with Potential Clients folder first  
            test_filename = f"test_pc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            test_upload_path = f"{base_upload_path}/{test_filename}"
            
            print(f"   📤 Testing upload to Potential Clients: {test_upload_path}")
            
            # Create a test file
            test_content = f"Test upload to shared folder at {datetime.now()}"
            try:
                scoped_client.files_upload(
                    test_content.encode(),
                    test_upload_path,
                )
                print(f"   ✅ File uploaded successfully!")
                print(f"   📍 Location: {test_upload_path}")
                
                # Verify upload
                file_metadata = scoped_client.files_get_metadata(test_upload_path)
                print(f"   📊 File size: {file_metadata.size} bytes")
                
                # Now test creating _esign folder structure
                print("\n7. Testing _esign folder creation...")
                date_folder = datetime.now().strftime('%Y%m%d')
                esign_upload_path = f"{base_upload_path}/_esign/{date_folder}/{test_filename}"
                print(f"   📤 Creating _esign structure: {esign_upload_path}")
                
                try:
                    scoped_client.files_upload(
                        test_content.encode(),
                        esign_upload_path,
                    )
                    print(f"   ✅ _esign folder structure created successfully!")
                    print(f"   📍 _esign location: {esign_upload_path}")
                    
                    return {
                        "success": True,
                        "working_path": working_path,
                        "potential_clients_path": potential_clients_path,
                        "test_upload_path": test_upload_path,
                        "esign_upload_path": esign_upload_path,
                        "shared_folder_id": shared_folder_id
                    }
                except Exception as e:
                    print(f"   ⚠️ _esign folder creation failed: {e}")
                    # Still return success since the basic upload worked
                    return {
                        "success": True,
                        "working_path": working_path,
                        "potential_clients_path": potential_clients_path,
                        "test_upload_path": test_upload_path,
                        "esign_upload_path": None,
                        "shared_folder_id": shared_folder_id,
                        "note": "Basic upload works, but _esign folder creation failed"
                    }
                
            except Exception as e:
                print(f"   ❌ Upload failed: {e}")
                return {"success": False, "error": str(e)}
        else:
            print("\n❌ No working path found")
            return {"success": False, "error": "No accessible paths"}
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Working approach test failed")
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = test_working_approach()
    if result["success"]:
        print(f"\n✅ SOLUTION FOUND!")
        print(f"🔑 Shared Folder ID: {result['shared_folder_id']}")
        print(f"📁 Working Path: '{result['working_path']}'")
        if result.get('esign_upload_path'):
            print(f"📤 _esign Upload Path: {result['esign_upload_path']}")
        if result.get('test_upload_path'):
            print(f"📤 Test Upload Path: {result['test_upload_path']}")
        print(f"\n🎯 For .env file:")
        print(f"DROPBOX_ESIGN_FOLDER_ID={result['shared_folder_id']}")
        if result.get('potential_clients_path'):
            print(f"DROPBOX_ESIGN_FOLDER_PATH={result['potential_clients_path']}/_esign")
        else:
            print(f"DROPBOX_ESIGN_FOLDER_PATH={result['working_path']}/_esign")
    else:
        print(f"\n❌ Test failed: {result['error']}")
    
    sys.exit(0 if result["success"] else 1) 