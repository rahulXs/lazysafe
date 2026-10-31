"""CLI entry point: argument parsing and text output."""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from lazysafe._version import __version__
from lazysafe.apply.plan import plan_keyword
from lazysafe.config import load_config
from lazysafe.discovery import scan_directory
from lazysafe.measure import BUDGET_UNAVAILABLE, measure, result_to_dict
from lazysafe.probe import probe
from lazysafe.report import write_analysis_report
from lazysafe.static import run_static
from lazysafe.static.classify import classify_all
from lazysafe.verify import verify

_INVALID_TARGET_HELP = {
    "not-found": "no such file or directory",
    "not-a-directory": "not a directory; pass a directory to scan",
}

# Options that moved in 0.7.0. argparse would only call them unknown, so they
# get a diagnostic that names the replacement.
_MOVED_OPTIONS = {
    "measure": {
        "--python": "name the executable after `--`, e.g. `lazysafe measure -- python -m pytest`",
    },
    "verify": {
        "--python": "name the executable after `--`, e.g. `lazysafe verify -- python -m pytest`",
        "--lazy-python": (
            "both runs now use the one executable after `--`; lazysafe checks that it "
            "defers imports itself"
        ),
    },
}

# A command must start with an executable, so a leading -c or -m means the
# executable is missing.
_LEADING_FLAGS = {"-c", "-m"}


def _load_config(project_root, json_output=False):
    """load config, converting validation failures into a clean usage error."""
    try:
        return load_config(project_root)
    except ValueError as exc:
        from lazysafe.report import error_report

        if json_output:
            print(json.dumps(error_report("invalid_config", str(exc)), allow_nan=False))
        print(f"  error: {exc}\n", file=sys.stderr)
        sys.exit(2)


def _command_name(argv):
    """The subcommand, which is the first token that is not an option."""
    for token in argv:
        if not token.startswith("-"):
            return token
    return None


def _check_command_line(argv):
    """Reject the old spellings before argparse reports them as unknown."""
    command = _command_name(argv)
    if command is None:
        return

    for flag, hint in _MOVED_OPTIONS.get(command, {}).items():
        if flag in argv:
            print(
                f"  error: {flag} was removed from `lazysafe {command}`.\n         {hint}\n",
                file=sys.stderr,
            )
            sys.exit(2)

    rest = argv[argv.index(command) + 1 :]
    for token in rest:
        if token == "--":
            break
        if token in _LEADING_FLAGS:
            print(
                f"  error: `lazysafe {command}` needs the executable before {token}.\n"
                f"         example: lazysafe {command} -- python {token} <args>\n",
                file=sys.stderr,
            )
            sys.exit(2)


def _literal_command(rest):
    """Strip the `--` delimiter, require an executable, and resolve it once.

    Resolving here means later working-directory changes cannot change which
    program runs.
    """
    if rest and rest[0] == "--":
        rest = rest[1:]

    if not rest:
        print(
            "  error: no command given.\n"
            "         example: lazysafe measure -- python -c 'import json'\n",
            file=sys.stderr,
        )
        sys.exit(2)

    resolved = shutil.which(rest[0])
    if resolved:
        return [resolved, *rest[1:]]

    return list(rest)


def _read_source_for_analysis(node, model):
    """Re-read an already-scanned file; records a coverage gap on failure."""
    try:
        return Path(node.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        node.coverage_gaps.append("source unreadable during analysis")
        model.skipped.append({"path": node.file, "reason": "unreadable"})
        return None


def _cmd_analyze(args):
    config = _load_config(Path.cwd(), getattr(args, "json", False))
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
    result = report.get("result", report)

    _print_analysis_table(report, args)

    invalid = [s for s in result["skipped"] if s["reason"] in _INVALID_TARGET_HELP]
    if invalid:
        for entry in invalid:
            print(
                f"  error: {entry['path']}: {_INVALID_TARGET_HELP[entry['reason']]}\n",
                file=sys.stderr,
            )
        sys.exit(2)

    if result["stats"]["files_scanned"] == 0:
        print("  no modules examined; no safety claim made.\n", file=sys.stderr)
        sys.exit(1)


def _print_analysis_table(report, args):
    result = report.get("result", report)
    if args.json:
        print(json.dumps(report, indent=2, allow_nan=False))
        return

    stats = result["stats"]
    print(f"\nscanned {stats['files_scanned']} files, {stats['top_level_imports']} imports")
    print(
        f"classified: {stats['by_class']['safe']} safe, "
        f"{stats['by_class']['risky']} risky, "
        f"{stats['by_class']['unsafe']} unsafe, "
        f"{stats['by_class']['unknown']} unknown"
    )

    skipped = [s for s in result["skipped"] if s["reason"] not in _INVALID_TARGET_HELP]

    has_findings = any(mod["reasons"] for mod in result["modules"])
    if not result["modules"]:
        _print_skipped(skipped)
        return

    if not has_findings and not args.all:
        print(
            f"\n  no side effects detected in {stats['files_scanned']} examined "
            "file(s) (heuristic, not proof). use --all to see every module.\n"
        )
        _print_skipped(skipped)
        return

    for mod in result["modules"]:
        cls = mod["class"]
        if cls == "safe" and not args.all:
            continue

        symbol = {"safe": "+", "risky": "?", "unsafe": "!", "unknown": "?"}.get(cls, "?")
        imports = mod["imports_top_level"]
        import_str = f" ({len(imports)} imports)" if imports else ""
        print(f"  {symbol} {mod['module']} ({mod['origin']}) [{cls}]{import_str}")
        for reason in mod["reasons"]:
            print(f"    {reason['rule']}@{reason['lineno']}: {reason['evidence']}")

    print()
    _print_skipped(skipped)


def _print_skipped(skipped):
    if not skipped:
        return
    print(f"  skipped {len(skipped)} file(s):")
    for entry in skipped[:10]:
        print(f"    {entry['path']}: {entry['reason']}")
    print()


def _cmd_measure(args):
    config = _load_config(Path.cwd(), getattr(args, "json", False))
    budget = args.budget if args.budget is not None else config.budget_ms
    if budget is not None:
        print(f"  error: {BUDGET_UNAVAILABLE}\n", file=sys.stderr)
        sys.exit(2)

    try:
        result = measure(
            _literal_command(args.command_argv),
            runs=args.runs if args.runs is not None else config.measure_runs,
            warmup=args.warmup if args.warmup is not None else config.measure_warmup,
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
        warmup = report["runs"]["warmup"]
        measured = report["runs"]["measured"]
        print(f"  runs:    {warmup} warmup + {measured} measured")
        print("  metric:  import-profile data (-X importtime), not command duration\n")
        print(f"  p50:     {stats['p50']}ms")
        print(f"  min:     {stats['min']}ms")
        print(f"  max:     {stats['max']}ms")
        print(f"  stdev:   {stats['stdev']}ms")

        if report["per_module_top"]:
            print("\n  top modules:")
            for mod in report["per_module_top"][:10]:
                cum = mod["cumulative_ms"]
                self_ms = mod["self_ms"]
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


def _print_probe_profile(profile):
    verdict = profile["verdict"]
    symbol = {"safe": "+", "risky": "?", "unsafe": "!", "error": "x"}.get(verdict, "?")
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


def _cmd_probe(args):
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


def _build_apply_model(args):
    config = _load_config(Path.cwd(), getattr(args, "json", False))
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


def _cmd_apply(args):
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


def _cmd_verify(args):
    result = verify(_literal_command(args.command_argv))

    if result.error:
        print(f"  error: {result.error}\n", file=sys.stderr)
        if args.json:
            print(json.dumps({"equivalent": False, "error": result.error}, indent=2))
        sys.exit(2)

    if args.json:
        print(
            json.dumps(
                {
                    "equivalent": result.equivalent,
                    "eager_exit": result.eager.exit_code,
                    "lazy_exit": result.lazy.exit_code,
                    "diffs": result.diffs,
                },
                indent=2,
            )
        )
    else:
        status = "EQUIVALENT" if result.equivalent else "DIVERGENT"
        print("\n  experimental: compares one command under two interpreter-wide")
        print("  modes. it does not check a source edit.\n")
        print(f"  verdict: {status}")
        print(f"  eager exit: {result.eager.exit_code}")
        print(f"  lazy exit:  {result.lazy.exit_code}")

        if result.diffs:
            print("\n  diffs:")
            for d in result.diffs:
                print(f"    - {d}")
        print()

    if not result.equivalent:
        sys.exit(1)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        prog="lazysafe",
        description="safely adopt python 3.15 lazy imports.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_analyze = sub.add_parser("analyze", help="analyze imports for side effects")
    p_analyze.add_argument("targets", nargs="*", help="directories to scan")
    p_analyze.add_argument("--json", action="store_true", help="output as JSON")
    p_analyze.add_argument("--all", action="store_true", help="show safe modules too")

    p_measure = sub.add_parser(
        "measure",
        help="measure import-profile timing for a literal command",
        epilog="example: lazysafe measure -- python -c 'import json'",
    )
    p_measure.add_argument(
        "command_argv",
        nargs=argparse.REMAINDER,
        help="literal executable and arguments, after `--`",
    )
    p_measure.add_argument("--runs", type=int, help="number of measured runs")
    p_measure.add_argument("--warmup", type=int, help="number of warmup runs")
    p_measure.add_argument("--budget", type=float, help="budget gating (currently unavailable)")
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
    p_apply.add_argument(
        "--include-unsafe", action="store_true", help="also rewrite RISKY/UNSAFE modules"
    )

    p_verify = sub.add_parser(
        "verify",
        help="experimental: compare one command eager vs lazy (not a source-edit check)",
        epilog="example: lazysafe verify -- python -m pytest -q",
    )
    p_verify.add_argument(
        "command_argv",
        nargs=argparse.REMAINDER,
        help="literal executable and arguments, after `--`",
    )
    p_verify.add_argument("--json", action="store_true", help="output as JSON")

    _check_command_line(argv)

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

    commands[args.command](args)
