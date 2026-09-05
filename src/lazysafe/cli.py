"""CLI entry point -- argparse wiring only."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="lazysafe",
        description="safely adopt python 3.15 lazy imports.",
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s 0.1.0"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("analyze", help="analyze imports for side effects")
    sub.add_parser("probe", help="probe third-party modules dynamically")
    sub.add_parser("apply", help="apply lazy import rewrites")
    sub.add_parser("verify", help="verify behavioral equivalence")
    sub.add_parser("measure", help="measure startup time")
    sub.add_parser("version", help="show capability matrix")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "version":
        print(f"lazysafe 0.1.0 \xb7 python {sys.version.split()[0]}")
        return

    print(f"command '{args.command}' not yet implemented.")
    sys.exit(1)
