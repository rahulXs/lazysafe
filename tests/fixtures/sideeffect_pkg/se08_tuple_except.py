"""fixture for testing tuple exception handlers."""

try:
    import json
except (ImportError, ModuleNotFoundError):
    json = None
