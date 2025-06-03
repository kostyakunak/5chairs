#!/usr/bin/env python3
import sys
import os
import subprocess

# Set the script name to pass to main.py
sys.argv = ["main.py", "user"]

# Import and run the main function
from main import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("User bot stopped")