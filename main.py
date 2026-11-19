#!/usr/bin/env python3
"""OnlineFix Launcher entry point."""

import faulthandler
import os
import sys

faulthandler.enable()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from oflauncher.app import main

if __name__ == "__main__":
    sys.exit(main())
