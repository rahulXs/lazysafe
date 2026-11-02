"""Child harness for origin observations."""

import json
import sys


def main():
    print(json.dumps({"loaded": sorted(sys.modules), "argv": sys.argv}))


if __name__ == "__main__":
    main()
