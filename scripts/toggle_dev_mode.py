#!/usr/bin/env python3
"""
Script to toggle AI development mode on/off.
When dev mode is on, the app will use mock images instead of calling the OpenAI API.
This helps avoid API costs during development and testing.
"""

import os
import sys
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent.parent / "app"
sys.path.insert(0, str(app_dir))

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.conf import settings

def toggle_dev_mode():
    """Toggle AI development mode and show current status"""
    current_mode = getattr(settings, "AI_DEV_MODE", False)
    outpaint_mode = getattr(settings, "USE_OUTPAINT_METHOD", True)
    
    print(f"Current AI Development Mode: {'ON' if current_mode else 'OFF'}")
    print(f"Current Outpainting Method: {'ON' if outpaint_mode else 'OFF'}")
    print()
    
    if current_mode:
        print("✅ Development mode is ON - using mock images (no API costs)")
        print("   To turn OFF and use real OpenAI API calls:")
        print("   export AI_DEV_MODE=false")
    else:
        print("⚠️  Development mode is OFF - using real OpenAI API calls")
        print("   To turn ON and use mock images (no API costs):")
        print("   export AI_DEV_MODE=true")
    
    print()
    if outpaint_mode:
        print("✅ Outpainting method is ON - square image extended to other aspect ratios")
        print("   Images will look consistent across all aspect ratios")
        print("   To turn OFF and generate separate images for each aspect ratio:")
        print("   export USE_OUTPAINT_METHOD=false")
    else:
        print("⚠️  Outpainting method is OFF - generating separate images for each aspect ratio")
        print("   Images may look different across aspect ratios")
        print("   To turn ON and use consistent outpainting:")
        print("   export USE_OUTPAINT_METHOD=true")
    
    print()
    print("Note: You need to restart the Django server after changing these settings.")

if __name__ == "__main__":
    toggle_dev_mode()
