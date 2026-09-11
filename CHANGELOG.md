# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.1] - 2026-09-10

### fixed

- SE06 classification: modules with registration decorators now correctly classify as RISKY
- tuple exception handlers: `except (ImportError, ModuleNotFoundError):` now detected
- augmented assignments: `sys.path += [...]` now detected by SE02/SE03
- `--runs 0` / `--warmup 0` now properly handled instead of silently ignored
- subprocess failures in measure now return clear error instead of 0ms false results
- `measure` validates inputs and raises ValueError for invalid runs/warmup
- `TimeoutExpired` and `FileNotFoundError` now caught in measure

## [0.2.0] - 2026-09-09

### added

- `lazysafe measure` startup timing harness using `-X importtime`
- fresh-process timing with warmup runs
- p50/min/max/stdev statistics
- `--budget MS` flag for CI gating (exit 1 if exceeded)
- `--python EXE` flag for interpreter selection
- JSON report output (`--json` flag)
- per-module timing breakdown (top offenders)

## [0.1.0] - 2026-09-06

### added

- `lazysafe analyze` static analysis engine with SE01-SE08 side-effect rules
- classification decision tree (SAFE / RISKY / UNSAFE / UNKNOWN)
- JSON report output (`--save`, `--json` flags)
- `lazysafe version` command with capability matrix
- configuration via `lazysafe.toml` with unknown-key rejection
- fixture corpus for side-effect rule testing

### side-effect rules

- SE01: module-level call expressions
- SE02: foreign attribute assignment (monkeypatching)
- SE03: sys.path / sys.modules / os.environ mutation
- SE04: atexit / signal / logging registration
- SE05: module-level file I/O
- SE06: framework registration decorators
- SE07: importlib.import_module with computed names
- SE08: try/except ImportError with fallback patches
