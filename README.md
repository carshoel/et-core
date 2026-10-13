# ET Core

English | [简体中文](README.zh-CN.md)

ET Core is the compiler and interpreter for the ET language. A Python host can inject functions for RPA, desktop automation, databases, web workflows, or other capabilities by name. ET scripts call those functions directly and use their return values in variables, control flow, and ET functions. Core owns the language semantics and execution flow; the host supplies the domain-specific capabilities.

This repository contains the Core runtime source only. It does not include `et.exe`, the IDE, host RPA implementations, or third-party Python packages. Core is not a sandbox for untrusted scripts. See [demo/demo.et](demo/demo.et) for ET syntax including containers, functions, captured default arguments, and a background task. Its top-level `return` ends the main flow before the two following `while` blocks; the background task may not run its first iteration before that return.

## Quick start

Run this Python code from the repository root. Python 3.10 and 3.13 were used for local development checks; other versions have not been verified. The example needs only the standard library and this repository:

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from Core.core import run


def double(value):
    return value * 2


with TemporaryDirectory() as directory:
    script = Path(directory) / "example.et"
    script.write_text("answer = double(21)\nreturn answer", encoding="utf-8")
    result = run(str(script), fs={"double": double},
                 log=lambda *args, **kwargs: None)
    print(result)  # 42
```

The `fs` dictionary injects Python functions into ET. Calls pass evaluated arguments to Python, Python return values remain usable in ET, and the top-level ET `return` becomes the result of `run()`. `run_pycode` can be supplied by a product host, but it is **not** a built-in function in this Core repository.

## Architecture and layout

ET source passes through `Lexer` into positioned tokens. `MatrixParser` uses a token feature matrix to help build the AST; `CodeGenerator` lowers it to `AESel` instructions and nested `AEBlock` objects, which `AEInterpreter` executes. The production entry point, `Core.Compiler.compiler.compile()`, uses only the matrix parser. `Core/Compiler/parser.py` retains AST types, not a second parser implementation.

- `Core/Compiler/`: lexer, matrix frontend in `mx/`, AST types, instruction generation, and compile entry point.
- `Core/Interpreter/`: instruction models, variable scopes, function calls, control flow, and runtime lifecycle.
- `Core/Sels/`: built-in operations and host registration helpers; host functions are passed through `fs`.
- `Core/Tool/`: internal ID allocation.
- `demo/`: user-authored ET syntax examples, starting with [`demo.et`](demo/demo.et).

See the [ET syntax and writing guide](docs/ET_GUIDE.md) for language examples and host-dependent features. Use `forin` to traverse a list or dictionary, or `while` for a condition-based loop. Ordinary `for` is **not supported**. This source-only release does not include the internal regression suite or compiler test corpora. Packaging and product integration require separate validation; a Core source check does not certify `et.exe` or the IDE.

## License

Copyright 2026 余伟. The ET Core source in this repository is licensed under the [Apache License 2.0](LICENSE). This license does not cover `et.exe`, the IDE, host RPA implementations, or third-party Python packages outside this repository.
