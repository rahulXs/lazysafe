"""module with mixed imports."""
import json
import os  # noqa: F401
import sys

data = json.dumps({"key": "value"})
sys.path.append("/opt")
