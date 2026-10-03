# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.6.0] - 2026-10-03

This release removes guarantees the code did not provide. Anything under
**withdrawn** behaved differently than advertised in 0.5.0; those commands now
fail or say so instead of returning a misleading result. No new capability is
added, and no existing command gained one.

### Withdrawn

- `lazysafe apply` no longer writes source files. when the plan has candidates,
  a write request exits nonzero with an explanation and leaves every byte
  untouched. there is no flag combination that writes. a plan with no candidates
  still exits 0 and says so
- `lazysafe measure --budget MS` is rejected, and so is `budget_ms` in
  `lazysafe.toml`. the reported metric is import-profile data from
  `-X importtime`, not command duration, so it cannot gate a startup budget
- probe result caching is removed. `--refresh` is accepted and does nothing,
  because there is no cache to refresh
- `verify` no longer normalizes output. durations, temporary paths, hex
  addresses, and version strings used to be rewritten before comparison, so two
  runs printing different temporary paths compared equal
- the `--safe-only` flag is removed. it was accepted and never read
- the backup and restore helpers are removed. no command reached them

### Fixed

- `analyze` no longer prints a clean safety summary for an empty, missing, or
  partly unreadable scan. a missing target or a file given as a target exits 2,
  an empty scan exits 1, and skipped files are named
- `analyze` no longer reports a module as `safe` when its source could not be
  read or parsed. incomplete analysis is reported as `unknown`
- `probe` no longer imports the target module in the lazysafe process. target
  resolution and import happen only in the child
- `measure` reports a failed sample as an execution error instead of dropping
  it. a run with any failed sample produces no timing and exits nonzero, so an
  all-failed or mixed run cannot pass
- `verify` no longer reports two runs that both failed as equivalent. both runs
  must exit zero, and an execution error exits 2 rather than 0
- `verify` no longer accepts an interpreter that does not defer imports. it
  imports a module under `-X lazy_imports=all` and checks the module really
  stayed unloaded, because python 3.14 accepts that flag and then imports eagerly

### Added

- a required CI job on python 3.15 that records the exact interpreter build and
  fails, rather than skipping, when the selected build cannot defer an explicit
  `lazy import`. the 3.11-3.14 jobs are unchanged
- the release workflow now runs tests, lint, format, and the native check on the
  tagged revision before building or publishing. a tag push previously bypassed
  CI entirely
- `verify` states in its output that it is an interpreter-wide experiment and
  not a check of a source edit

### Migration

- `lazysafe apply <path>` now exits 2 instead of writing. add `--dry-run` to keep
  previewing
- remove `--budget` from `measure` invocations and from `lazysafe.toml`. it never
  measured command duration, so a passing budget meant nothing
- drop `--refresh` from `probe`; it has done nothing since 0.4.0
- drop `--safe-only` from `apply`; it was ignored
- `verify` exits 2 where it used to exit 0 for the same invocation. treat any
  nonzero exit as failure
- `verify` now requires a python that defers imports. on python 3.11-3.14 it
  exits 2 with an explanation instead of reporting a comparison that proved
  nothing
- arguments after `--` go to the interpreter, so `lazysafe verify -- -m pytest -q`
  is the working form. `lazysafe verify -- python -m pytest -q` never worked; it
  asked python to run a file named `python`
- `--python` and `--lazy-python` still work and are scheduled for removal in
  0.7.0, along with `measure --python`

### Known limitations

- `SAFE` means no rule matched, not that a module is free of import-time side
  effects. an assigned call result, a call inside a class body, a mutation
  inside a conditional, a single registration decorator, and effects inherited
  through imports are not detected yet
- `analyze` collects top-level imports only, and does not propagate findings
  between modules
- `analyze` and `apply` disagree on most projects. module names are recorded
  relative to the scan root, so with a `src` layout they look like
  `src.mypkg.mod` while imports are bare (`json`, `os`). `apply` then matches no
  import to a classification and reports "no safe imports to rewrite" even when
  `analyze` reports safe modules. import resolution is scheduled for 0.11.0
- `apply --include-unsafe` removes RISKY and UNSAFE imports from the skip list
  without rewriting them
- native lazy behavior is qualified on ubuntu with the build CI selects. the
  windows and macOS lazy paths are not qualified
- probe results are not cached and describe one run on one interpreter
- probe observation coverage is partial. descriptor counting is linux-only, and
  `atexit` registration is not observable on this interpreter

## [0.5.0] - 2026-09-13

### Added

- `lazysafe verify` command for behavioral equivalence checking
- runs command in eager and lazy modes, compares exit codes and output
- output normalization (durations, temp paths, hex addresses, Python version)
- auto-revert from backup on divergence
- `--python` and `--lazy-python` flags for interpreter selection
- `--json` flag for JSON output

### Fixed

- `-X lazy_imports` changed to `-X lazy_imports=all` (PEP 810 requires value)

## [0.4.0] - 2026-09-13

### Added

- `lazysafe apply` command to rewrite safe imports to lazy
- keyword mode: rewrites `import X` to `lazy import X` for SAFE modules
- `--dry-run` flag to preview changes without modifying files
- `--safe-only` flag (default) to only rewrite SAFE modules
- `--include-unsafe` flag to also rewrite RISKY/UNSAFE modules
- backup/restore under `.lazysafe/backup/<runid>/`
- plan data structure with change tracking and skip reasons

## [0.3.0] - 2026-09-13

### Added

- `lazysafe probe` dynamic side-effect profiling via subprocess sandbox
- snapshot dimensions: threads, atexit, signal handlers, sys.path, env, cwd, umask, fds, warnings filters
- verdict classification: safe / risky / unsafe / error
- profile cache with automatic invalidation (module + interpreter + mtime key)
- `--python EXE`, `--timeout S`, `--refresh`, `--json` flags
- timeout handling (default 30s)
- subprocess error handling (FileNotFoundError, TimeoutExpired)

## [0.2.1] - 2026-09-10

### Fixed

- SE06 classification: modules with registration decorators now correctly classify as RISKY
- tuple exception handlers: `except (ImportError, ModuleNotFoundError):` now detected
- augmented assignments: `sys.path += [...]` now detected by SE02/SE03
- `--runs 0` / `--warmup 0` now properly handled instead of silently ignored
- subprocess failures in measure now return clear error instead of 0ms false results
- `measure` validates inputs and raises ValueError for invalid runs/warmup
- `TimeoutExpired` and `FileNotFoundError` now caught in measure

## [0.2.0] - 2026-09-09

### Added

- `lazysafe measure` startup timing harness using `-X importtime`
- fresh-process timing with warmup runs
- p50/min/max/stdev statistics
- `--budget MS` flag for CI gating (exit 1 if exceeded)
- `--python EXE` flag for interpreter selection
- JSON report output (`--json` flag)
- per-module timing breakdown (top offenders)

## [0.1.0] - 2026-09-06

### Added

- `lazysafe analyze` static analysis engine with SE01-SE08 side-effect rules
- classification decision tree (SAFE / RISKY / UNSAFE / UNKNOWN)
- JSON report output (`--save`, `--json` flags)
- configuration via `lazysafe.toml` with unknown-key rejection
- fixture corpus for side-effect rule testing
- SE01: module-level call expressions
- SE02: foreign attribute assignment (monkeypatching)
- SE03: sys.path / sys.modules / os.environ mutation
- SE04: atexit / signal / logging registration
- SE05: module-level file I/O
- SE06: framework registration decorators
- SE07: importlib.import_module with computed names
- SE08: try/except ImportError with fallback patches
