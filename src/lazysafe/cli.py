"""CLI entry point -- argparse wiring only."""

import argparse
import json
import sys
import time
from pathlib import Path

from lazysafe._version import __version__
from lazysafe.config import load_config
from lazysafe.discovery import scan_directory
from lazysafe.report import write_analysis_report
from lazysafe.static import run_static
from lazysafe.static.classify import classify_all


def _cmd_analyze(args: argparse.Namespace) -> None:
    """run static analysis on target directories."""
    config = load_config(Path.cwd())
    targets = args.targets or config.targets

    start = time.monotonic()
    model = scan_directory(targets, Path.cwd())
    duration_ms = (time.monotonic() - start) * 1000

    for node in model.modules:
        if node.file:
            try:
                source = Path(node.file).read_text(encoding="utf-8")
                node.findings = run_static(node, source)
            except (OSError, UnicodeDecodeError):
                pass

    classify_all(model)

    report = write_analysis_report(
        model, targets, duration_ms, output=Path(args.save) if args.save else None
    )

    _print_analysis_table(report, args)


def _print_analysis_table(report: dict, args: argparse.Namespace) -> None:
    """print analysis results as a table."""
    stats = report["stats"]
    print(f"\nscanned {stats['files_scanned']} files, {stats['top_level_imports']} imports")
    print(
        f"classified: {stats['by_class']['safe']} safe, "
        f"{stats['by_class']['risky']} risky, "
        f"{stats['by_class']['unsafe']} unsafe, "
        f"{stats['by_class']['unknown']} unknown"
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return

    has_findings = any(mod["reasons"] for mod in report["modules"])
    if not has_findings and not args.all:
        print("\n  all imports look safe. use --all to see every module.\n")
        return

    for mod in report["modules"]:
        cls = mod["class"]
        if cls == "safe" and not args.all:
            continue

        symbol = {"safe": "+", "risky": "?", "unsafe": "!", "unknown": "?"}.get(
            cls, "?"
        )
        imports = mod["imports_top_level"]
        import_str = f" ({len(imports)} imports)" if imports else ""
        print(f"  {symbol} {mod['module']} ({mod['origin']}) [{cls}]{import_str}")
        for reason in mod["reasons"]:
            print(f"    {reason['rule']}@{reason['lineno']}: {reason['evidence']}")

    print()


def _cmd_version(_args: argparse.Namespace) -> None:
    """show version and capability matrix."""
    print(f"lazysafe {__version__} \xb7 python {sys.version.split()[0]}")
    print()
    print("capabilities:")
    print("  analyze   yes")
    print("  measure   no  (v0.2.0)")
    print("  probe     no  (v0.3.0)")
    print("  apply     no  (v0.4.0)")
    print("  verify    no  (v0.5.0)")


def main(argv: list[str] | None = None) -> None:
    """main entry point."""
    parser = argparse.ArgumentParser(
        prog="lazysafe",
        description="safely adopt python 3.15 lazy imports.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="analyze imports for side effects")
    p_analyze.add_argument("targets", nargs="*", help="directories to scan")
    p_analyze.add_argument("--save", metavar="FILE", help="save JSON report")
    p_analyze.add_argument("--json", action="store_true", help="output as JSON")
    p_analyze.add_argument(
        "--all", action="store_true", help="show safe modules too"
    )

    sub.add_parser("version", help="show capability matrix")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "analyze": _cmd_analyze,
        "version": _cmd_version,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        print(f"command '{args.command}' not yet implemented.")
        sys.exit(1)
