import os
import sys

# Add the application root to Python path
sys.path.insert(0, "/srv/apps/esign")

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "debug"

# Worker configuration
workers = 3
worker_class = "sync"
timeout = 60

# Path handling
forwarded_allow_ips = "*"
proxy_protocol = True
proxy_allow_ips = "*"

# Error handling
capture_output = True
enable_stdio_inheritance = True
reload = True  # Enable auto-reload for development

# Create logs directory if it doesn't exist
os.makedirs("/srv/apps/esign/logs", exist_ok=True)
