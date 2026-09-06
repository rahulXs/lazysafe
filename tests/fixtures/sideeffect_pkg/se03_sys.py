"""module with SE03: import-system mutation."""

import sys

sys.modules["fake_module"] = type(sys)("fake_module")
