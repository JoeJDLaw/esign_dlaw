#!/usr/bin/env python3
"""
Debug script to list all folders visible to sf_integrations account
to understand the correct path format for team folders.
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

def debug_folder_structure():
    """Debug the actual folder structure visible to sf_integrations account."""
    
    print("🔍 Debugging Dropbox Folder Structure...")
    print("=" * 60)
    
    try:
        # Initialize Dropbox client
        print("1. Initializing Dropbox client...")
        client = DropboxClient(use_shared_app=True)
        print("   ✓ Client initialized")
        
        print("\n2. Listing root folders...")
        try:
            result = client.dbx.files_list_folder("")
            print(f"   📁 Root folder contains {len(result.entries)} items:")
            for entry in result.entries:
                print(f"      - {entry.name} ({type(entry).__name__})")
        except Exception as e:
            print(f"   ❌ Cannot list root: {e}")
            
        print("\n3. Checking team folders and shared folders...")
        try:
            # Try to get shared folders
            shared_folders = client.dbx.sharing_list_folders()
            print(f"   📁 Found {len(shared_folders.entries)} shared folders:")
            for folder in shared_folders.entries:
                print(f"      - {folder.name} (ID: {folder.shared_folder_id})")
                print(f"        Path: {getattr(folder, 'path_lower', 'N/A')}")
                print(f"        Access: {folder.access_type}")
        except Exception as e:
            print(f"   ⚠️ Cannot list shared folders: {e}")
            
        try:
            # Check if there are any mounted folders
            result = client.dbx.files_list_folder("", include_mounted_folders=True)
            print(f"   📁 Root with mounted folders: {len(result.entries)} items:")
            for entry in result.entries:
                print(f"      - {entry.name} ({type(entry).__name__})")
                if hasattr(entry, 'sharing_info'):
                    print(f"        Sharing: {entry.sharing_info}")
        except Exception as e:
            print(f"   ⚠️ Cannot list with mounted folders: {e}")
            
        print("\n4. Using team folders API (the correct approach)...")
        try:
            # Import the team folders functionality
            import dropbox
            
            # Create team client (not regular client)
            team_client = dropbox.DropboxTeam(
                app_key=os.getenv("DROPBOX_SHARED_APP_KEY"),
                app_secret=os.getenv("DROPBOX_SHARED_APP_SECRET"),
                oauth2_refresh_token=os.getenv("DROPBOX_SHARED_REFRESH_TOKEN")
            )
            
            print("   📋 Listing all team folders...")
            result = team_client.team_team_folder_list()
            print(f"   📁 Found {len(result.team_folders)} team folders:")
            
            target_folder_id = None
            for folder in result.team_folders:
                print(f"      - {folder.name} (ID: {folder.team_folder_id}, Status: {folder.status._tag})")
                if folder.name == "DavtyanLaw Team Folder (1)":
                    target_folder_id = folder.team_folder_id
                    print(f"        🎯 FOUND TARGET FOLDER!")
                    
        except Exception as e:
            print(f"   ❌ Team folders API failed: {e}")
            target_folder_id = None
            
        print("\n5. Testing direct team member access to team folder...")
        if target_folder_id:
            try:
                # Use the team client's as_user method to access the team folder directly
                member_id = os.getenv("DROPBOX_SHARED_TEAM_MEMBER_ID")
                print(f"   Using team member ID: {member_id}")
                
                # Create user client from team client
                user_client = team_client.as_user(member_id)
                
                # Test paths using the team member's direct access
                test_paths = [
                    f"ns:{target_folder_id}",
                    f"/ns:{target_folder_id}",
                    f"ns:{target_folder_id}/Potential Clients",
                    f"/ns:{target_folder_id}/Potential Clients",
                ]
                
                for path in test_paths:
                    try:
                        print(f"   Testing path with team member client: {path}")
                        result = user_client.files_list_folder(path)
                        print(f"      ✅ SUCCESS - Found {len(result.entries)} items")
                        for entry in result.entries[:3]:  # Show first 3 items
                            print(f"         - {entry.name}")
                        if len(result.entries) > 3:
                            print(f"         ... and {len(result.entries) - 3} more items")
                        print(f"      🎯 WORKING PATH FOUND: {path}")
                        break  # Found working path
                    except Exception as e:
                        print(f"      ❌ Failed: {e}")
                        
            except Exception as e:
                print(f"   ❌ Team member access failed: {e}")
        else:
            print("   ⚠️ No target folder ID found")
                
        print("\n6. FINAL ATTEMPT: Try sharing API direct access...")
        try:
            # Try to access using sharing API directly
            shared_folder_id = "1387609128"  # From the sharing list
            print(f"   Attempting to list shared folder contents directly: {shared_folder_id}")
            
            # Use sharing API to list folder contents
            folder_info = client.dbx.sharing_get_folder_metadata(shared_folder_id)
            print(f"   📁 Shared folder: {folder_info.name}")
            
            # Try to get the sharing link and access pattern
            print(f"   Trying to find the correct access pattern...")
            
            # Check if we can access via sharing link conversion
            try:
                # This sometimes works - convert shared folder to a path
                shared_link = client.dbx.sharing_create_shared_link_with_settings(shared_folder_id)
                print(f"   📎 Created shared link: {shared_link.url}")
            except Exception as e:
                print(f"   ⚠️ Shared link creation failed: {e}")
                
        except Exception as e:
            print(f"   ❌ Sharing API access failed: {e}")
            
        print("\n7. SOLUTION RECOMMENDATION:")
        print("   🔄 Team folders require explicit mounting to be accessible via Files API")
        print("   💡 OPTION 1: Mount the folder (one-time setup)")
        print("      - Log in to Dropbox as sf_integrations@d.law")
        print("      - Navigate to 'DavtyanLaw Team Folder (1)'")
        print("      - Click 'Add to my Dropbox' or 'Sync'")
        print("      - Folder will then be accessible at: /DavtyanLaw Team Folder (1)/...")
        print("   💡 OPTION 2: Use a different Dropbox account/app setup")
        print("   💡 OPTION 3: Use personal space (current working approach)")
        print("   📋 Current working path: /esign/ (personal space)")
        print("   🤔 Would you prefer to use personal space or mount the team folder?")
                
        return True
    except Exception as e:
        print(f"\n❌ Debug failed: {e}")
        return False

if __name__ == "__main__":
    debug_folder_structure() 