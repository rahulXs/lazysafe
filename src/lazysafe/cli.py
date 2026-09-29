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

_INVALID_TARGET_HELP = {
    "not-found": "no such file or directory",
    "not-a-directory": "not a directory; pass a directory to scan",
}


def _read_source_for_analysis(node, model):
    """Re-read an already-scanned file; records a coverage gap on failure."""
    try:
        return Path(node.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        node.coverage_gaps.append("source unreadable during analysis")
        model.skipped.append({"path": node.file, "reason": "unreadable"})
        return None


def _cmd_analyze(args: argparse.Namespace):
    config = load_config(Path.cwd())
    targets = args.targets or config.targets

    start = time.monotonic()
    model = scan_directory(targets, Path.cwd())
    duration_ms = (time.monotonic() - start) * 1000

    for node in model.modules:
        if node.file:
            source = _read_source_for_analysis(node, model)
            if source is not None:
                node.findings = run_static(node, source)

    classify_all(model)

    report = write_analysis_report(model, targets, duration_ms)

    _print_analysis_table(report, args)

    invalid = [s for s in report["skipped"] if s["reason"] in _INVALID_TARGET_HELP]
    if invalid:
        for entry in invalid:
            print(
                f"  error: {entry['path']}: {_INVALID_TARGET_HELP[entry['reason']]}\n",
                file=sys.stderr,
            )
        sys.exit(2)

    if report["stats"]["files_scanned"] == 0:
        print("  no modules examined; no safety claim made.\n", file=sys.stderr)
        sys.exit(1)


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

    skipped = [s for s in report["skipped"] if s["reason"] not in _INVALID_TARGET_HELP]

    has_findings = any(mod["reasons"] for mod in report["modules"])
    if not report["modules"]:
        _print_skipped(skipped)
        return

    if not has_findings and not args.all:
        print(
            f"\n  no side effects detected in {stats['files_scanned']} examined "
            "file(s) (heuristic, not proof). use --all to see every module.\n"
        )
        _print_skipped(skipped)
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
    _print_skipped(skipped)


def _print_skipped(skipped: list) -> None:
    if not skipped:
        return
    print(f"  skipped {len(skipped)} file(s):")
    for entry in skipped[:10]:
        print(f"    {entry['path']}: {entry['reason']}")
    print()


def _cmd_measure(args: argparse.Namespace):
    from lazysafe.measure import BUDGET_UNAVAILABLE

    config = load_config(Path.cwd())
    budget = args.budget if args.budget is not None else config.budget_ms
    if budget is not None:
        print(f"  error: {BUDGET_UNAVAILABLE}\n", file=sys.stderr)
        sys.exit(2)

    try:
        result = measure(
            args.entry_command,
            runs=args.runs if args.runs is not None else config.measure_runs,
            warmup=args.warmup if args.warmup is not None else config.measure_warmup,
            python=args.python,
        )
    except ValueError as exc:
        print(f"  error: {exc}\n", file=sys.stderr)
        sys.exit(2)

    report = result_to_dict(result)

    if not result.ok:
        if args.json:
            print(json.dumps(report, indent=2))
        failed = report["runs"]["failed"]
        kinds = sorted({e["kind"] for e in report["errors"]})
        print(
            f"  error: {failed} sample(s) failed ({', '.join(kinds)}); no timing to report.\n",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        stats = report["total_ms"]
        print(f"\n  command: {' '.join(report['entry_command'])}")
        print(f"  python:  {report['interpreter']}")
        warmup = report['runs']['warmup']
        measured = report['runs']['measured']
        print(f"  runs:    {warmup} warmup + {measured} measured")
        print("  metric:  import-profile data (-X importtime), not command duration\n")
        print(f"  p50:     {stats['p50']}ms")
        print(f"  min:     {stats['min']}ms")
        print(f"  max:     {stats['max']}ms")
        print(f"  stdev:   {stats['stdev']}ms")

        if report["per_module_top"]:
            print("\n  top modules:")
            for mod in report["per_module_top"][:10]:
                cum = mod['cumulative_ms']
                self_ms = mod['self_ms']
                print(f"    {mod['module']:40s} {cum:>8.1f}ms (self {self_ms:.1f}ms)")

        print()


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


def _build_apply_model(args: argparse.Namespace):
    from lazysafe.config import load_config

    config = load_config(Path.cwd())
    targets = args.targets or config.targets
    project_root = Path.cwd()

    model = scan_directory(targets, project_root)
    for node in model.modules:
        if node.file:
            source = _read_source_for_analysis(node, model)
            if source is not None:
                node.findings = run_static(node, source)
    classify_all(model)
    return model


_APPLY_WRITES_UNAVAILABLE = (
    "lazysafe apply cannot write source files in this release: "
    "the write path has no verified backup, transaction, or recovery support. "
    "Writes stay disabled until a verified, recoverable write path is available. "
    "Re-run with --dry-run to preview candidates without modifying files."
)


def _cmd_apply(args: argparse.Namespace):
    from lazysafe.apply.plan import plan_keyword

    model = _build_apply_model(args)
    plan = plan_keyword(model, safe_only=not args.include_unsafe)

    if not plan.changes:
        print("\n  no safe imports to rewrite.\n")
        return

    total_rewrites = sum(len(c.rewrites) for c in plan.changes)
    print("\n  experimental preview -- source writes are disabled in this release.\n")
    print(f"  {total_rewrites} import(s) to rewrite in {len(plan.changes)} file(s)\n")

    if plan.skipped:
        print(f"  skipped {len(plan.skipped)} import(s) (not safe):")
        for s in plan.skipped[:10]:
            print(f"    {s.module}: {s.reason}")
        print()

    for change in plan.changes:
        print(f"  {change.path}")
        for rewrite in change.rewrites:
            print(f"    L{rewrite.lineno}: {rewrite.old_line.strip()}")
            print(f"      -> {rewrite.new_line.strip()}")
        print()

    if args.dry_run:
        print("  dry run -- no files modified.\n")
        return

    print(f"  {_APPLY_WRITES_UNAVAILABLE}\n", file=sys.stderr)
    sys.exit(2)


def _cmd_verify(args: argparse.Namespace):
    from lazysafe.verify import verify

    command = args.command_to_run
    result = verify(
        command,
        python=args.python,
        lazy_python=args.lazy_python,
    )

    if args.json:
        print(json.dumps({
            "equivalent": result.equivalent,
            "eager_exit": result.eager.exit_code,
            "lazy_exit": result.lazy.exit_code,
            "diffs": result.diffs,
        }, indent=2))
    else:
        status = "EQUIVALENT" if result.equivalent else "DIVERGENT"
        print(f"\n  verdict: {status}")
        print(f"  eager exit: {result.eager.exit_code}")
        print(f"  lazy exit:  {result.lazy.exit_code}")

        if result.diffs:
            print("\n  diffs:")
            for d in result.diffs:
                print(f"    - {d}")
        print()

    if not result.equivalent:
        sys.exit(1)


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

    p_measure = sub.add_parser("measure", help="measure import-profile timing")
    p_measure.add_argument("entry_command", nargs="+", help="command to measure")
    p_measure.add_argument("--runs", type=int, help="number of measured runs")
    p_measure.add_argument("--warmup", type=int, help="number of warmup runs")
    p_measure.add_argument("--budget", type=float, help="budget gating (currently unavailable)")
    p_measure.add_argument("--python", help="python interpreter to use")
    p_measure.add_argument("--json", action="store_true", help="output as JSON")

    p_probe = sub.add_parser("probe", help="probe modules for runtime side effects")
    p_probe.add_argument("modules", nargs="+", help="modules to probe")
    p_probe.add_argument("--python", help="python interpreter to use")
    p_probe.add_argument("--timeout", type=float, default=30.0, help="timeout in seconds")
    p_probe.add_argument(
        "--refresh", action="store_true", help="no-op: probe results are never cached"
    )
    p_probe.add_argument("--json", action="store_true", help="output as JSON")

    p_apply = sub.add_parser(
        "apply", help="preview lazy import rewrites (experimental; writes disabled)"
    )
    p_apply.add_argument("targets", nargs="*", help="directories to scan")
    p_apply.add_argument(
        "--dry-run",
        action="store_true",
        help="show preview without writing (writes are disabled in this release)",
    )
    p_apply.add_argument("--safe-only", action="store_true", default=True,
                         help="only rewrite SAFE modules (default)")
    p_apply.add_argument("--include-unsafe", action="store_true",
                         help="also rewrite RISKY/UNSAFE modules")

    p_verify = sub.add_parser("verify", help="verify eager vs lazy equivalence")
    p_verify.add_argument("command_to_run", nargs="+", help="command to verify")
    p_verify.add_argument("--python", help="python interpreter for eager mode")
    p_verify.add_argument("--lazy-python", help="python 3.15+ for lazy mode")
    p_verify.add_argument("--json", action="store_true", help="output as JSON")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    commands = {
        "analyze": _cmd_analyze,
        "measure": _cmd_measure,
        "probe": _cmd_probe,
        "apply": _cmd_apply,
        "verify": _cmd_verify,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        print(f"command '{args.command}' not yet implemented.")
        sys.exit(1)
