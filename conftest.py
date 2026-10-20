"""
Pytest configuration for Smart ICU Guardian.
Adds project root to sys.path so tests in any directory can import project modules.
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
