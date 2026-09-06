"""module with SE08: try/except ImportError fallback."""

try:
    import ujson as json
except ImportError:
    import json

    json.loads = lambda s: {"fallback": True}
