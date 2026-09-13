"""CLI entry point -- argparse wiring only."""

import argparse
import json
import sys
import time
from pathlib import Path

from lazysafe._version import __version__
from lazysafe.config import load_config
from lazysafe.discovery import scan_directory
from lazysafe.measure import measure, result_to_dict
from lazysafe.probe import probe
from lazysafe.report import write_analysis_report
from lazysafe.static import run_static
from lazysafe.static.classify import classify_all


def _cmd_analyze(args: argparse.Namespace):
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

    report = write_analysis_report(model, targets, duration_ms)

    _print_analysis_table(report, args)


def _print_analysis_table(report: dict, args: argparse.Namespace):
    if args.json:
        print(json.dumps(report, indent=2))
        return

    stats = report["stats"]
    print(f"\nscanned {stats['files_scanned']} files, {stats['top_level_imports']} imports")
    print(
        f"classified: {stats['by_class']['safe']} safe, "
        f"{stats['by_class']['risky']} risky, "
        f"{stats['by_class']['unsafe']} unsafe, "
        f"{stats['by_class']['unknown']} unknown"
    )

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


def _cmd_measure(args: argparse.Namespace):
    config = load_config(Path.cwd())
    budget = args.budget if args.budget is not None else config.budget_ms

    result = measure(
        args.entry_command,
        runs=args.runs if args.runs is not None else config.measure_runs,
        warmup=args.warmup if args.warmup is not None else config.measure_warmup,
        budget_ms=budget,
        python=args.python,
    )

    report = result_to_dict(result)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        stats = report["total_ms"]
        print(f"\n  command: {' '.join(report['entry_command'])}")
        print(f"  python:  {report['interpreter']}")
        warmup = report['runs']['warmup']
        measured = report['runs']['measured']
        print(f"  runs:    {warmup} warmup + {measured} measured\n")
        print(f"  p50:     {stats['p50']}ms")
        print(f"  min:     {stats['min']}ms")
        print(f"  max:     {stats['max']}ms")
        print(f"  stdev:   {stats['stdev']}ms")

        if report["budget"]:
            b = report["budget"]
            status = "PASS" if b["passed"] else "FAIL"
            print(f"\n  budget:  {b['limit_ms']}ms -> {status}")

        if report["per_module_top"]:
            print("\n  top modules:")
            for mod in report["per_module_top"][:10]:
                cum = mod['cumulative_ms']
                self_ms = mod['self_ms']
                print(f"    {mod['module']:40s} {cum:>8.1f}ms (self {self_ms:.1f}ms)")

        print()

    if report["budget"] and not report["budget"]["passed"]:
        sys.exit(1)


_EFFECT_LABELS = {
    "thread_spawned": lambda e: f"thread spawned: {e['count']}",
    "sys_path_added": lambda e: f"sys.path added: {e['paths']}",
    "signal_handler_changed": lambda e: f"signal handler changed: {e['signal']}",
    "atexit_registered": lambda e: f"atexit registered: {e['count']}",
    "env_changed": lambda e: f"env changed: +{e['added']} -{e['removed']}",
    "cwd_changed": lambda e: f"cwd changed: {e['from']} -> {e['to']}",
    "warnings_filter_changed": lambda e: f"warnings filter changed: {e['count']}",
}


def _print_probe_profile(profile: dict):
    verdict = profile["verdict"]
    symbol = {"safe": "+", "risky": "?", "unsafe": "!", "error": "x"}.get(
        verdict, "?"
    )
    duration = profile.get("duration_ms", 0)
    effects = profile.get("side_effects", [])

    print(f"\n  {symbol} {profile['module']} [{verdict}] ({duration:.0f}ms)")

    if profile.get("error"):
        print(f"    error: {profile['error']}")

    for e in effects:
        label_fn = _EFFECT_LABELS.get(e["kind"])
        label = label_fn(e) if label_fn else f"{e['kind']}: {e}"
        print(f"    {label}")

    imports = profile.get("imports_transitively", [])
    if imports:
        print(f"    imports: {', '.join(imports[:5])}")


def _cmd_probe(args: argparse.Namespace):
    results = probe(
        args.modules,
        python=args.python,
        timeout=args.timeout,
        refresh=args.refresh,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for profile in results:
            _print_probe_profile(profile)
        print()


def main(argv: list[str] | None = None) -> None:
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
    p_analyze.add_argument("--json", action="store_true", help="output as JSON")
    p_analyze.add_argument(
        "--all", action="store_true", help="show safe modules too"
    )

    p_measure = sub.add_parser("measure", help="measure startup time")
    p_measure.add_argument("entry_command", nargs="+", help="command to measure")
    p_measure.add_argument("--runs", type=int, help="number of measured runs")
    p_measure.add_argument("--warmup", type=int, help="number of warmup runs")
    p_measure.add_argument("--budget", type=float, help="max p50 startup time in ms")
    p_measure.add_argument("--python", help="python interpreter to use")
    p_measure.add_argument("--json", action="store_true", help="output as JSON")

    p_probe = sub.add_parser("probe", help="probe modules for runtime side effects")
    p_probe.add_argument("modules", nargs="+", help="modules to probe")
    p_probe.add_argument("--python", help="python interpreter to use")
    p_probe.add_argument("--timeout", type=float, default=30.0, help="timeout in seconds")
    p_probe.add_argument("--refresh", action="store_true", help="ignore cache")
    p_probe.add_argument("--json", action="store_true", help="output as JSON")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "analyze": _cmd_analyze,
        "measure": _cmd_measure,
        "probe": _cmd_probe,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        print(f"command '{args.command}' not yet implemented.")
        sys.exit(1)
