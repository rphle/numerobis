# Numerobis

A compiled, statically-typed programming language that treats physical units and dimensions as first-class citizens of the type system. Dimension and unit errors are caught **before execution** — and unit conversions happen **automatically**.

> [!WARNING]
> The language and its documentation are unfinished. While usable, Numerobis is not recommended for production code yet. Only Linux is supported at the moment.

---

## Why?

In most programming languages, physical quantities are plain numbers. Units exist only as informal convention, and there is no way to automatically detect unit inconsistencies — the kind of mistake that caused the [loss of the Mars Climate Orbiter](https://en.wikipedia.org/wiki/Mars_Climate_Orbiter) in 1999.

Numerobis integrates units and dimensions directly into its type system:

- **Dimension errors are caught at compile time** — adding a length to a mass is a type error.
- **Unit conversions are automatic** — you never write conversion factors by hand.
- **Non-multiplicative units are supported natively** — including affine units like °C and °F, and logarithmic units like dBm and pH.

Numerobis compiles to C99, giving it a significant performance advantage over interpreted languages.

---

## Installation

Install the Python package locally (editable):

```bash
make install
```

Build the runtime library and compiler:

```bash
make build
```

After installation, the `nbis` CLI entry point is available.

### System dependencies

```bash
sudo apt install -y \
  pkg-config \
  libglib2.0-dev \
  libgc-dev \
  build-essential \
  ccache \
  mold
```

- `pkg-config` — discovers `glib-2.0` and `bdw-gc`
- `libglib2.0-dev` — dynamic lists and strings
- `libgc-dev` — Boehm–Demers–Weiser garbage collector
- `build-essential` — C toolchain
- `ccache` + `mold` — C compiler cache and faster linker

In case you want to run benchmarks, you also need to install `hyperfine` for precise timing:
```bash
sudo apt install hyperfine
```

---

## CLI

```
nbis build SOURCE [-o OUTPUT] [--run] [--quiet] [--debug/--no-debug] [-O {0,1,2,3,s}] [--cc COMPILER]
nbis view  SOURCE [-o OUTPUT] [--theme THEME] [--line-numbers/--no-line-numbers]
```

### `nbis build`

| Flag | Default | Description |
|---|---|---|
| `-o`, `--output` | source filename | Output binary path |
| `--run` / `--no-run` | off | Execute the binary immediately after building |
| `--quiet` | off | Suppress the build summary line |
| `--debug` / `--no-debug` | on | Emit debug info (`-g`) |
| `-O {0,1,2,3,s}` | `0` | Optimization level passed to the C compiler |
| `--cc` | `gcc` | C compiler to use (e.g. `--cc clang`) |


### `nbis view`

| Flag | Default | Description |
|---|---|---|
| `-o`, `--output` | _(print to terminal)_ | Write generated C code to a file instead of printing |
| `--theme` | `monokai` | Syntax highlighting theme |
| `--line-numbers` / `--no-line-numbers` | on | Show line numbers |

### Make Targets

| Target | Description |
|---|---|
| `make install` | Install the Python package (editable) |
| `make build` | Build the compiler and runtime library |
| `make test` | Run the full test suite |
| `make benchmark` | Run performance benchmarks against Python and C |
| `make runtimelib` | Rebuild the static runtime library (`libruntime.a`) only |
| `make graph` | Generate class/package diagrams into `assets/` |
| `make help` | List all available targets |

You can pass flags to the test runner directly:

```bash
make test -- --verbose
make test CC=clang
```

---

## Language Reference

> For concise examples, browse the `tests/` directory (canonical examples) and `examples/`.

### Comments

```python
# single-line comment

#[ multi-line
   comment ]#
```

### Variables & Type Annotations

Type and dimension annotations are optional — the compiler infers them bidirectionally.

```python
x: Type = expr
x: Mass = 1000       # dimension annotation

i: Int   = 10
f: Float = 3.14
m: Int[Length] = 10 m
s: Str  = "hello"
b: Bool = true
l0: List        = [1, 2, 3]
l1: List[Int]   = [1, 2, 3]
l2: List[Mass]  = [1 kg, 2 kg, 3 kg]
fn: ![[s: Str, n: Int], Str] = !(s: Str, n: Int): Str = s * n
```

### Functions

Functions support default arguments and optional type annotations. The body can be a single expression or a block.

```python
greet!(name: Str, times: Int = 1): Str = name * times

fibonacci!(n: Int): Int = {
    if n <= 1 then
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
}

echo(fibonacci(20))
```

### Control Flow

```python
# if / else
if a < b then echo("small")
else {
    if a > 15 then echo("large") else echo("medium")
}

# for over a range
for i in 0..10 do echo(i)

# for over a list
for item in [1, 2, 3] do echo(item)

# while
i = 0
while i < 10 do {
    echo(i)
    i = i + 1
}
```

### Lists & Indexing

Lists are ordered and homogeneous. Indexing is zero-based and follows Python conventions (negative indices, slices).

```python
lst = [10, 20, 30]
lst[0]   # 10
lst[-1]  # 30
lst[1:]  # [20, 30]
```

---

## Units & Dimensions

### Defining Dimensions and Units

```python
dimension Length             # base dimension
dimension Volume = Length^3  # derived dimension

unit m: Length               # base unit for Length
unit km = 1000 m             # derived unit (dimension inferred)
unit L  = (0.1 m)^3          # volume in litres

unit taco;                   # shorthand: creates dimension "Taco" and base unit "taco"
```

### Unit Suffixes on Literals

Units are **suffixes on number literals**, not standalone values. This avoids naming conflicts (e.g. `m` can still be used as a variable name).

```python
m = 410 kg         # 'm' is a variable, 'kg' is a unit suffix — no conflict
```

A unit suffix extends up to one space from the number, or arbitrarily far inside parentheses:

```python
# "5 metres divided by variable s"
5 m / s
5m / s

# "5 metres per second"
5m/s
5 m/s
5(m / s)
```

Allowed operators **inside suffixes**: `*`, `/`, `^`

### Affine Units (e.g. Temperature)

```python
unit °C: Temperature = _ K + 273.15
unit °F = (5/9) * (_ K + 459.67)

echo(0°C -> K)    # 273.15 K
echo(0°C -> °F)   # 32 °F
```

The underscore `_` is the placeholder for the input value. Every unit definition is a function that maps a value to its base unit.

### Logarithmic Units (e.g. Decibels)

```python
unit mW  = 0.001 W
unit dBm = 10^(_ mW / 10mW)

echo(2 * 60dBm)          # 63.0103 dBm
echo(60dBm |+| 60dBm)    # 120 dBm      (raw number addition, ignores unit)
```

### The Delta Operator

For affine and logarithmic units, plain `+` and `-` are semantically restricted. The delta operators `|+|` and `|-|` operate on raw values and reattach the unit afterwards:

```python
0°C |-| 32°F    # 0 °C
10dB |+| 5dB    # 15 dB
```

### Unit Conversions

Use `->` to convert between compatible units or between types:

```python
500 m -> km          # 0.5 km
1 gallon -> L        # 3.78541 L
"1234" -> Int        # 1234 (type conversion)
("1234" -> Int) + 1  # 1235
```

Conversions between incompatible dimensions are caught at compile time.

### Imports

Import with the `@` prefix to distinguish units/dimensions from regular names:

```python
from mymodule import name, @myunit, @MyDimension
from imperial import @gallon

# grouped import shorthand
from si       import @(kg, m, km, s, K, J, kJ, kW, h)
```

---

## Type System

### Dimension Annotations

```python
x: Length = 42 m
y: Float[Mass] = 3.14 kg
l: List[Length] = [x, 6 m, 7 km]
```

### Compile-Time Errors

```
'm' declared as [Mass] but has dimension [Length]
m: Mass = 2m
```

```
Incompatible dimensions in addition: [Mass·Length²·Time⁻³] vs [Mass·Length²·Time⁻²]
42 watt + 3.14 joule
```

### Interop with C

External C functions can be declared and called from Numerobis using the `extern` keyword:

```python
extern echo!(value, end: Str = "\n"): None;
```

---

## Examples

### Energy to Boil a Gallon of Water

```python
from si       import @(kg, L, g, K, kJ, kW, h, J)
from imperial import @gallon

unit °F  = (5/9) * (_ K + 459.67)
unit cal = 4.184 J
unit kWh = kW * h

density_water = 1 (kg / L)
mass_water    = 1 gallon * density_water
c_water       = 1 (cal / (g * K))
ΔT            = (212°F -> K) - (70°F -> K)
heat          = mass_water * c_water * ΔT

echo(heat -> kJ)    # 1249.45 kJ
echo(heat -> kWh)   # 0.347071 kWh
```

### Logarithmic Unit Addition

```python
unit mW  = 0.001 W
unit dBm = 10^(_ mW / 10mW)

echo(2 * 60dBm)         # 63.0103 dBm
echo(60dBm |+| 60dBm)   # 120 dBm
```

### Affine Temperature Conversions

```python
unit °C: Temperature = _ K + 273.15
unit °F = (5/9) * (_ K + 459.67)

echo(5°C)           # 5 °C
echo(0°C -> K)      # 273.15 K
echo(0°C -> °F)     # 32 °F
echo(0°C |-| 32°F)  # 0 °C
```

---

## Running Tests

```bash
make test
# or
python3 run.py --verbose
```

Tests are `.nbis` files under `tests/`. The runner executes them and checks outputs and expected error codes. The test suite currently contains 1,128 unit tests.

---

## Project Layout

```
src/numerobis/
  analysis/      — dimension checker, unit simplifier, inversion
  cli/           — nbis command-line entry point
  compiler/      — codegen, linker, scoping, C emission
  lexer/         — tokeniser
  nodes/         — AST node definitions
  parser/        — recursive-descent parser + unit expression parser
  typechecker/   — type inference, dimension algebra, operator rules
  stdlib/        — built-in modules
runtime/         — C runtime sources, built into libruntime.a
tests/           — language tests, benchmarking
examples/        — small example programs
scripts/         — build helpers
assets/          — generated diagrams
```


![Package diagram](assets/packages.png)
