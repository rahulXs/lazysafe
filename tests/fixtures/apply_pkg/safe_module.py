"""safe module with simple imports."""
import json
import os  # noqa: F401
import pathlib

data = json.dumps({"key": "value"})
path = pathlib.Path(".")
