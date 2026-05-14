# Sharpie

Sharpie is a small source-to-source translator that converts a practical subset
of POSIX-style shell scripts into Python.

It focuses on the shell features that appear often in short automation scripts:
variables, `echo`, command-line arguments, tests, loops, simple command
substitution, globbing, redirects, and `case` statements.

## Example

```sh
python3 sharpie.py examples/basic/control-flow.sh
```

Example output:

```python
#!/usr/bin/python3 -u

name = 'Lucius'

if name == 'great':
    print('wrong branch')
elif name == 'Lucius':
    print('elif branch works')
else:
    print('wrong branch again')
```

## Features

- Converts common shell assignments into Python variables.
- Translates `echo`, quoting, comments, and basic variable interpolation.
- Handles `if`, `elif`, `else`, `while`, and `for` blocks.
- Supports common `test` / `[ ... ]` expressions.
- Converts command substitution using backticks and `$(...)`.
- Preserves external commands through `subprocess.run(...)`.
- Handles simple globbing, redirection, and `case` patterns.

## Repository Layout

```txt
sharpie.py             # translator
examples/basic/        # small input scripts
examples/advanced/     # scripts covering trickier shell features
tests/run_examples.sh  # smoke test for all examples
```

## Run

```sh
python3 sharpie.py examples/basic/echo-and-vars.sh
```

Write the generated Python to a file:

```sh
python3 sharpie.py examples/basic/echo-and-vars.sh > translated.py
python3 translated.py
```

Run the smoke tests:

```sh
./tests/run_examples.sh
```

## Scope

Sharpie is intentionally conservative. It is designed for readable short scripts,
not full shell compatibility. Complex quoting, pipelines, shell functions, traps,
arrays, and advanced parameter expansion are outside the current scope.

Course-specific submission files, private test suites, and official materials are
not included in this repository.
