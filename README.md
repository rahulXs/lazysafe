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

# save a JSON report
lazysafe analyze src/ --save report.json
```

## what it does

lazysafe scans your Python source files and classifies every import statement
by its side-effect risk:

| finding | meaning | action |
|---------|---------|--------|
| SAFE | no side effects detected | safe to make lazy |
| RISKY | might have side effects | investigate before lazy |
| UNSAFE | side effect detected | keep eager |
| UNKNOWN | can't determine statically | needs probing (v0.3.0) |

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
- function-level profiling (use [Tachyon](https://docs.python.org/3.15/whatsnew/3.15.html#tachyon) in 3.15)
- general linting/formatting (use [ruff](https://docs.astral.sh/ruff/))

## requirements

- python >= 3.11 (host running lazysafe)
- target programs using lazy import semantics require python >= 3.15
- linux, macos, windows

## links

- [changelog](https://github.com/rahulxs/lazysafe/blob/main/CHANGELOG.md)
- [issue tracker](https://github.com/rahulxs/lazysafe/issues)

## license

MIT
