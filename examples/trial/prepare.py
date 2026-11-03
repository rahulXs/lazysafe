"""Prepare the trial example trees."""

import argparse
from pathlib import Path

PACKAGE_INIT = "VALUE = 1\n"
ORIGINAL_MAIN = """import json
import sys


def main():
    with open(sys.argv[-1], encoding="utf-8") as f:
        items = json.load(f)
    total = sum(item["price"] for item in items)
    print(f"books {total:.2f}")


if __name__ == "__main__":
    main()
"""
CANDIDATE_MAIN = ORIGINAL_MAIN.replace("import json\n", "lazy import json\n", 1)
BROKEN_MAIN = ORIGINAL_MAIN.replace(
    "import json\n",
    "lazy import json\nimport os\nos._exit(0)\n",
    1,
)


def make_tree(root, main_source):
    src = root / "src" / "demo_cli"
    src.mkdir(parents=True)
    (src / "__init__.py").write_text(PACKAGE_INIT, encoding="utf-8")
    (src / "main.py").write_text(main_source, encoding="utf-8")
    fixtures = root / "fixtures"
    fixtures.mkdir()
    (fixtures / "items.json").write_text(
        '[{"title":"Book A","price":4.5},{"title":"Tool B","price":3.5}]',
        encoding="utf-8",
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    out = Path(args.output)
    if out.exists():
        raise SystemExit(f"refusing existing destination: {out}")
    out.mkdir(parents=True)
    make_tree(out / "original", ORIGINAL_MAIN)
    make_tree(out / "lazy-candidate", CANDIDATE_MAIN)
    make_tree(out / "broken-registration", BROKEN_MAIN)
    make_tree(out / "unchanged-control", ORIGINAL_MAIN)
    print(f"prepared trees in {out}")


if __name__ == "__main__":
    main()
