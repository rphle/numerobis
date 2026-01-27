# Numerobis Programming Language

> [!WARNING]
> The language itself and especially its documentation is unfinished and while usable, it is not recommended to use it for production code.
> This documentation is work in progress.
> Only Linux is supported at the moment.


Install the Python package locally (editable):
```bash
make build
```

After installation, the `nbis` CLI entry point is available (see CLI usage below).


## Runtime & system dependencies

System dependencies (required for compilation and runtime linking):
- `pkg-config` (to discover `glib-2.0` and `bdw-gc`)
- `libglib2.0` development headers (commonly `libglib2.0-dev` on Debian/Ubuntu)
- `libgc` (Boehm GC) development headers (`libgc-dev` or `libgc1c2` + dev)
- C toolchain (gcc/clang), `ar` and `make` tools

- `ccache` and `mold` for runnning tests

Note: The build scripts use `pkg-config` to obtain correct compiler and linker flags for `glib-2.0` and `bdw-gc`.

```bash
sudo apt install -y \
  pkg-config \
  libglib2.0-dev \
  libgc-dev \
  build-essential \
  ccache \
  mold

```

## Running tests:
- The repository includes a simple runner used by the `Makefile`:
```bash
make test
# or
python3 run.py --verbose
```

Tests are .nbis files under `tests/`. The test runner executes them, checks outputs and expected behaviors (some tests include expected error codes).


## CLI (nbis)

The command line interface is available as the `nbis` entry point (installed by the package). Two primary subcommands are `build` and `view`:

- `nbis build SOURCE [-o OUTPUT] [--run] [--no-quiet] [--debug/--no-debug] -O {0,1,2,3,s}`
- `nbis view SOURCE [--output FILE] [--theme THEME] [--no-line-numbers]`

Run `nbis --help` for more information.


Examples:
- Compile `hello.nbis` into `hello`:
```bash
nbis build hello.nbis
```
- Compile and immediately run:
```bash
nbis build hello.nbis --run
```
- Show generated C (syntax-highlighted) without compiling:
```bash
nbis view hello.nbis
```


## Language & Syntax Reference

This section is WIP.

For concise examples, see the test-suite under `tests/` (these files serve as canonical examples and tests).

Summary:
- Comments: `# comment`
- Variables & type annotations: `x: Type = expr`
- Function definitions: `name!(arg, ...) = expr`
- Lists: `[a, b, c]`
- Indexing: `lst[0]`, `lst[1:]`
- Units: `unit NAME : Dimension = expression` or `unit NAME = expression`
- Conversions: `value -> target_unit`
- Arithmetic: `+ - * / ^`
- Logical: `and`, `or`, `not`, comparisons `==`, `!=`, `<`, `>`, `<=`, `>=`
- If expressions: `if cond then expr else expr`


## Examples

- The `examples/` directory contains small programs:
  - `examples/factorial.nbis` — recursive factorial
  - `examples/caesar.nbis` — simple caesar cipher implementation
  - `examples/guessing.nbis` — number guessing game
  - `examples/sieve.nbis` — sieve of Eratosthenes


## Project layout

- `src/numerobis/` — Python package containing compiler front-end, module system, CLI
- `runtime/` — C runtime sources; built into `libruntime.a`
- `tests/` — language tests and examples
- `examples/` — small example programs
- `scripts/` — helper scripts
