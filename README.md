# lazysafe

safely adopt python 3.15 lazy imports.

## why it exists

python 3.15 ships [PEP 810](https://peps.python.org/pep-0810/) explicit lazy
imports. `lazy import json` defers loading until first use. reported wins: ~2.9x
faster startup for import-heavy applications.

the catch: laziness changes *when* import-time side effects run. some libraries
depend on them. under lazy mode, programs break in confusing ways.

lazysafe answers that question empirically.

## install

```
pip install lazysafe
```

## quickstart

```bash
# see which imports are safe to make lazy
lazysafe analyze src/

# show all modules including safe ones
lazysafe analyze src/ --all

# measure import-profile data (not command duration)
lazysafe measure --runs 3 -- python -m myapp

# probe modules for runtime side effects
# NOTE: probing imports the target in a child process running with your
# permissions. it is not a sandbox, and results are never cached.
lazysafe probe requests flask yaml

# preview lazy import rewrites (experimental preview only; writes disabled)
lazysafe apply src/ --dry-run
# NOTE: `lazysafe apply` without --dry-run exits nonzero without modifying
# files. source writes stay disabled until verified backup, transaction, and
# recovery support is available.

# verify eager vs lazy equivalence
lazysafe verify -- python -m pytest -q
```

## what it does

lazysafe scans your Python source files and classifies every import statement
by its side-effect risk:

| finding | meaning | action |
|---------|---------|--------|
| SAFE | no side effects detected | safe to make lazy |
| RISKY | might have side effects | investigate before lazy |
| UNSAFE | side effect detected | keep eager |
| UNKNOWN | can't determine statically | needs further investigation |

### side-effect rules

| code | what it detects | confidence |
|------|-----------------|------------|
| SE01 | module-level function calls | 0.6 |
| SE02 | foreign attribute assignment (monkeypatching) | 0.9 |
| SE03 | sys.path / sys.modules / os.environ mutation | 0.95 |
| SE04 | atexit / signal / logging registration | 0.85-0.9 |
| SE05 | module-level file I/O | 0.8 |
| SE06 | framework registration decorators (2+) | 0.5 |
| SE07 | importlib.import_module with computed names | 0.9 |
| SE08 | try/except ImportError with fallback patches | 0.7 |

## what it does not do

- runtime lazy-loading for older pythons (no backport of PEP 810)
- patching third-party packages' code
- general linting/formatting (use [ruff](https://docs.astral.sh/ruff/))

## requirements

- python >= 3.11 (host running lazysafe)
- target programs using lazy import semantics require python >= 3.15
- linux, macos, windows

### native lazy qualification

lazysafe never infers lazy support from a version string or a successful launch.
CPython 3.14 accepts `-X lazy_imports=all` and then imports eagerly anyway, so a
clean start is not evidence that anything was deferred.

qualification therefore runs real behavior in a child process on the selected
interpreter: an explicit `lazy import` must bind the name without executing the
module, and first use must then execute it. the CI job for python 3.15 is
required, prints the exact interpreter build, and fails if that behavior is not
observed rather than skipping.

what this does and does not cover:

- native lazy behavior is qualified on ubuntu with the 3.15 build CI selects;
  the job does not qualify the Windows or macOS paths
- the modes `-X lazy_imports=normal` and `-X lazy_imports=all` are exercised.
  lazysafe does not rely on any other mode
- the 3.11-3.14 jobs still run the rest of the suite and do not claim lazy support

## links

- [changelog](https://github.com/rahulxs/lazysafe/blob/main/CHANGELOG.md)
- [issue tracker](https://github.com/rahulxs/lazysafe/issues)

## license

MIT
