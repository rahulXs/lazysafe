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

```
$ lazysafe analyze src/
$ lazysafe probe requests flask
$ lazysafe apply --dry-run
$ lazysafe verify
$ lazysafe measure -- python -m myapp
```

## what it does

| capability | command |
|---|---|
| static side-effect analysis (SE01-SE08) | `lazysafe analyze` |
| dynamic probing of third-party modules | `lazysafe probe` |
| apply `lazy import` / `__lazy_modules__` rewrites | `lazysafe apply` |
| verify behavioral equivalence (eager vs lazy) | `lazysafe verify` |
| measure startup improvement, budget gating | `lazysafe measure` |

## what it does not do

- runtime lazy-loading for older pythons (no backport of PEP 810)
- patching third-party packages' code
- function-level profiling (use [Tachyon](https://docs.python.org/3.15/whatsnew/3.15.html#tachyon) in 3.15)
- general linting/formatting (use [ruff](https://docs.astral.sh/ruff/))

## requirements

- python >= 3.11 (host running lazysafe)
- target programs using lazy import semantics require python >= 3.15
- linux, macos, windows (full support; fd/proc probe dimensions documented)

## links

- [changelog](https://github.com/rahulxs/lazysafe/blob/main/CHANGELOG.md)
- [issue tracker](https://github.com/rahulxs/lazysafe/issues)

## license

MIT
