"""
Pytest configuration and fixtures.
Adds the project root to sys.path so modules are discoverable.
"""

import sys
from pathlib import Path

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))
