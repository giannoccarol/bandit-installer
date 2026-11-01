#!/usr/bin/env python3
"""Android installer for the Nokia Lumia 1520 (bandit). Windows and Linux."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bandit_installer.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(__file__, sys.argv[1:]))
