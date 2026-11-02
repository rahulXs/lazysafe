# lazysafe

Safely adopt Python 3.15 lazy imports.

## Why it exists

Python 3.15 ships [PEP 810](https://peps.python.org/pep-0810/) explicit lazy
imports. `lazy import json` defers loading until first use.

The catch: laziness changes *when* import-time side effects run. Some libraries
depend on them, and under lazy mode programs break in confusing ways.

lazysafe answers that question empirically.

## Install

```bash
pip install lazysafe
```

## Quickstart

```bash
# classify imports by side-effect risk
lazysafe analyze src/

# show every module, including safe ones
lazysafe analyze src/ --all

# time a real command
lazysafe measure --runs 3 -- python -m myapp
```

In this release, `verify`, `probe`, and `apply` are unavailable and exit 2 with
`command_unavailable`.

### Literal commands

`measure` takes one literal command: everything after `--` is the executable and
its arguments, run directly with no shell and no interpreter added by lazysafe.

```bash
lazysafe measure -- python -c 'import json'
lazysafe measure -- ./scripts/start.sh --port 8080
```

Paths with spaces, Unicode arguments, and shell metacharacters such as `*` or
`$HOME` reach the program unchanged. Name the interpreter yourself; there is no
`--python` for `measure`.

## Configuration

`analyze` and `apply` read `lazysafe.toml` from the current directory. Supported
keys: `targets`, `budget_ms`, `measure_runs`, `measure_warmup`, and
`timeout_seconds`. `allowlist` is removed. Unknown keys are an error. Invalid
TOML or value types exit 2 without a traceback.

## What it does

lazysafe scans Python source and classifies each top-level import by side-effect
risk:

| Finding | Meaning | Action |
|---|---|---|
| SAFE | no rule matched | candidate to investigate |
| RISKY | might have side effects | investigate before lazy |
| UNSAFE | side effect detected | keep eager |
| UNKNOWN | cannot determine statically | needs further investigation |

A clean scan with no findings is `unknown`, not `safe`. `SAFE` means no rule
matched, not that a module is side-effect free.

### Side-effect rules

| Code | Detects | Confidence |
|---|---|---|
| SE01 | module-level function calls | 0.6 |
| SE02 | foreign attribute assignment | 0.9 |
| SE03 | `sys.path`, `sys.modules`, `os.environ` mutation | 0.95 |
| SE04 | atexit, signal, or logging registration | 0.85-0.9 |
| SE05 | module-level file I/O | 0.8 |
| SE06 | framework registration decorators (2+) | 0.5 |
| SE07 | `importlib.import_module` with computed names | 0.9 |
| SE08 | `try/except ImportError` with fallback patches | 0.7 |

## What it does not do

- Runtime lazy-loading for older Pythons (no backport of PEP 810)
- Patching third-party packages
- General linting or formatting (use [ruff](https://docs.astral.sh/ruff/))
- Modifying source files. `apply` previews only and cannot be made to write.

## Requirements

- Python >= 3.11 to run lazysafe
- Python >= 3.15 for lazy import semantics in target programs
- Linux, macOS, Windows

### Native lazy qualification

lazysafe never infers lazy support from a version string or a successful
launch. CPython 3.14 accepts `-X lazy_imports=all` and then imports eagerly
anyway, so qualification runs real behavior in a child process on the selected
interpreter.

## Links

- [Changelog](https://github.com/rahulxs/lazysafe/blob/main/CHANGELOG.md)
- [Issue tracker](https://github.com/rahulxs/lazysafe/issues)

## License

MIT
