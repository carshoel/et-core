# ET Core

[English](README.md) | 简体中文

ET Core 是 ET 语言的编译器与解释器内核。宿主可以用 Python 封装 RPA、桌面、数据库、网页等能力，按名称注入解释器；ET 脚本可直接调用这些函数，并在变量、条件、循环和自定义函数中使用返回值。Core 负责语言语义与控制流，具体自动化能力由宿主提供。

本仓库只包含 Core 运行源码，不包含 `et.exe`、IDE、宿主 RPA 实现或第三方 Python 包。Core 不是运行不可信脚本的安全沙箱。[demo/demo.et](demo/demo.et) 展示容器、函数、用默认参数固定的局部值和后台任务。顶层 `return` 会在后面两段 `while` 前结束主流程；后台任务是否来得及执行首轮取决于调度。

## 快速开始

从仓库根目录运行下列 Python 代码。Python 3.10 和 3.13 已用于本地开发核对，其他版本尚未验证。代码仅使用标准库和本仓库的 Core：

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

`fs` 将 Python 函数注入 ET；调用时传入已求值的参数，Python 返回值可继续在 ET 中使用，顶层 `return` 值由 `run()` 返回。`run_pycode` 是产品宿主可额外提供的函数，**不是**此仓库 Core 的内置能力。

## 架构与目录

`.et` 源码经过 `Lexer` 生成 Token，`MatrixParser` 根据特征矩阵辅助解析为 AST；`CodeGenerator` 生成 `AESel` 指令及嵌套 `AEBlock`，最后由 `AEInterpreter` 执行。生产编译入口为 `Core.Compiler.compiler.compile()`，只使用矩阵解析器；`Core/Compiler/parser.py` 保留 AST 类型，不是第二套解析器。

- `Core/Compiler/`：词法分析、`mx/` 矩阵前端、AST 类型、指令生成与编译入口。
- `Core/Interpreter/`：指令模型、变量作用域、函数调用、控制流和运行生命周期。
- `Core/Sels/`：内核运算及宿主函数注册辅助接口；宿主函数通过 `fs` 注入。
- `Core/Tool/`：内部 ID 分配工具。
- `demo/`：用户编写的 ET 语法示例，从 [`demo.et`](demo/demo.et) 开始。

语法示例与宿主依赖说明见 [ET 语法与编写指南](docs/ET_GUIDE.md)。ET 用 `forin` 遍历列表或字典，也可用 `while` 循环；普通 `for` **不受支持**。本次源码发布不包含内部回归测试或编译器测试语料。打包与产品集成须单独验证；Core 源码核对不等于 `et.exe` 或 IDE 验收。

## 许可证

Copyright 2026 余伟。本仓库的 ET Core 源码采用 [Apache License 2.0](LICENSE)。此许可不涵盖仓库外的 `et.exe`、IDE、宿主 RPA 实现或第三方 Python 包。
