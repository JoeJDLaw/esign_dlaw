#!/usr/bin/env python3
"""
Script to clean up old prefilled PDFs.
This can be run manually or via cron job.
"""

import os
import sys
import argparse
from datetime import datetime

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.routes_signing import cleanup_prefilled_pdfs
from shared.log_utils.logging_config import configure_logging

logger = configure_logging("apps.esign.cleanup", "esign.log")

def main():
    parser = argparse.ArgumentParser(description="Clean up old prefilled PDFs")
    parser.add_argument(
        "--max-age",
        type=int,
        default=24,
        help="Maximum age of files in hours before deletion (default: 24)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be deleted without actually deleting"
    )
    
    args = parser.parse_args()
    
    logger.info(f"Starting cleanup of prefilled PDFs older than {args.max_age} hours")
    logger.info(f"Dry run: {args.dry_run}")
    
    try:
        if args.dry_run:
            # In dry run mode, we'll just log what would be deleted
            logger.info("Dry run mode - no files will be deleted")
            # TODO: Implement dry run functionality if needed
        else:
            deleted, skipped = cleanup_prefilled_pdfs(max_age_hours=args.max_age)
            logger.info(f"Cleanup completed. Deleted: {deleted}, Skipped: {skipped}")
            
    except Exception as e:
        logger.exception("Error during cleanup")
        sys.exit(1)

if __name__ == "__main__":
    main() 