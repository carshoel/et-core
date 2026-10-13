# ET 语法与编写指南

本文面向 ET 代码的读者和生成 ET 代码的 AI。语法说明以 ET Core 为基础；产品宿主提供的 RPA、网页等函数需另外确认。另见 [demo.et](../demo/demo.et)。

## 基本规则

脚本是 UTF-8 编码的 `.et` 文件。语句末尾不需要加分号，建议一行一条语句；解析器虽支持用 `;` 分隔语句，日常脚本不必使用。代码块必须有 `{}`，缩进不能代替花括号。`//` 注释到行尾；暂不支持多行注释。字符串只用双引号，支持 `\n`、`\t`、`\r`、`\"`、`\\`、`\b`、`\f` 转义；单引号及三引号字符串不支持。Windows 路径建议写成 `C:/work/test.et`，避免反斜杠被当作转义。

```et
double(x) {
    return x * 2
}
answer = double(21)
return answer
```

保存为 `example.et`，从仓库根目录调用 `Core.core.run("example.et")`，返回 `42`。

## 值、容器和运算

`true`、`false`、`null` 对应 Python 的 `True`、`False`、`None`。数字包括整数和小数。`[]` 是列表，`(x)` 是分组，`(x,)` 是单元素元组，`{}` 是空字典，`{1}` 是集合，`{"k": 1}` 是字典。字典声明的键必须是字面量。变量无需声明；读取未定义变量报错。

```et
items = [10, 20]
record = {"name": "ET", "count": 3}
second = items[1]
record["count"] = 4
label = record.name
```

点号先读对象属性，缺少属性时尝试按键读取；字典键与方法同名时用 `record["name"]`。支持算术 `+ - * / % **`、比较 `== != < <= > >=`、逻辑 `! && ||`、位运算 `~ & | ^ << >>`、三目 `条件 ? 真值 : 假值`。`&&` 和 `||` **短路求值**：`a = null` 时，`a && a.b` 不会读取 `a.b`。旧版文档关于不短路的描述已过时。字符串参与 `+` 时另一侧会转换为字符串。不要用 Python 的 `and`、`or`、`not`。

二元运算优先级由低到高：赋值；`? :`；`||`；`&&`；`== !=`；`< > <= >=`；`|`；`^`；`&`；`<< >>`；`+ -`；`* / %`；`**`。同级普通二元运算从左到右结合，赋值和三目从右到左结合。`2 ** 3 ** 2` 得到 `64`；不确定时加括号。一元 `+` 不支持。

支持 `=`、`+= -= *= /= %= **= <<= >>= &= |= ^=` 和前后置 `++ --`。每次赋值左侧只能有一个目标；不支持 `a, b = values` 等多目标解构。多值应先用列表接收，再分别读取元素：`values = get_values()`、`a = values[0]`、`b = values[1]`。复合赋值当前只支持简单变量名；普通赋值还支持成员和索引。`a[2] += 1` 当前会报 `'Subscript' object has no attribute 'name'`，应写成 `a[2] = a[2] + 1`。自增/自减目标必须可赋值。

## 容器、字符串与常用方法

ET 的列表、字典和字符串可调用底层 Python 对象的方法，例如 `items.append(3)`、`items.pop()`、`record.get("name")`、`record.keys()`、`text.lower()`、`text.startswith("ET")`、`text.replace("a", "b")`、`text.split(",")`、`",".join(items)`。`len(items)` 可获取长度。`[]` 不支持列表推导式；索引支持 `items[0]`，但不支持 Python 的 `items[1:3]` 切片语法。

```et
names = ["a", "b"]
names.append("c")
text = ",".join(names)
return text
```

列表和字符串切片不能写 `items[1:3]` 或 `text[1:3]`，会报语法错误。若宿主提供了 `cut_index`、`cut_pattern`，可按宿主接口使用；它们与旧文档提到的 `is_in` 在本仓库 Core 中**没有实现**，使用前须确认宿主是否通过 `fs` 提供，不要凭名称假设可调用。

空集合可写 `set()`，`{}` 是空字典。列表的 `append`、`insert`、`sort`、`reverse`，字典的 `get`、`keys`、`values`、`items` 等遵循对应 Python 对象的方法签名。`forin` 也可遍历字符串，第二个变量为下标；遍历字典时第一个变量是值、第二个是键。

## 条件和循环

`if (条件) {...} else if (条件) {...} else {...}` 和 `while (条件) {...}` 均要求圆括号条件及花括号主体。`break` 结束循环，`continue` 进入下一轮。`null`、`false`、`0`、空字符串和空容器在条件里为假；可写 `if (!value) {...}`。自增自减也可用于条件，如 `while (--count) {...}`；`while (count++) {...}` 判断的是递增前的值。

`if (ratio)` 只判断真假值；只有业务已保证 `ratio` 不会为负数时，才可将 `if (ratio != null && ratio > 0)` 简化为 `if (ratio)`。否则负数在简写形式中也为真。`&&` 已支持短路。

```et
numbers = [3, 4]
total = 0
forin(value, index, source=numbers) {
    if (value > 0) { total += value }
}
return total
```

`forin` 是特殊函数定义形式，恰好三个形参：值、下标或键、用默认值指定的来源。列表下标从 0 开始，字典提供键；循环体支持 `break`、`continue`、`return`。普通 `for` **不支持**，条件循环请用 `while`。

## 函数、作用域和返回

函数写 `name(args){...}`，不用 `def`、`function` 或 Python 的 `lambda` 表达式。支持位置与命名实参，位置参数放在命名参数之前。漏传形参时当前实现将其初始化为 `null`，不自动报错。默认值在定义函数时求值，调用时尝试复制；不可复制的对象保持原引用。未绑定变量沿调用位置的作用域链查找；要固定定义时的值，可用默认参数：

```et
make(prefix) {
    inner(text, saved=prefix) { return saved + text }
    return inner
}
f = make("ET: ")
return f("ready")
```

`return value` 结束当前流程并返回值；`return` 返回 `null`。建议始终显式写 `return`：独立作为语句的变量名或字面量会被编译为 `return`，可能提前结束脚本；没有显式返回时，主脚本和函数通常会返回最后一条指令结果。例如只有 `a = 34` 的脚本，`run()` 返回 `34`，但编译器并未追加 `return a`。

## 作用域

读取变量时沿当前执行块向上查找。赋值时先修改可访问的已有同名变量，否则在当前作用域创建；函数边界会限制赋值向上查找，所以函数内对同名变量赋值通常不会修改函数外变量。

`if`、`else`、`while`、`forin` 和异常处理块内新建的变量随块结束而消失；在块外读取会报变量未定义。这与 Python 的 `if`/`while` 不创建独立局部作用域不同，**不要在块内首次定义要给块外使用的变量**。例如下面的 `print(result)` 会报未定义：

```et
if (true) {
    result = 42
}
print(result) // 错误：result 只在 if 块内定义
```

需要在块外读取或更新时，先在外层赋初值：

```et
result = null
if (true) {
    result = 42
}
return result
```

函数的自由变量按**调用位置**的作用域链查找，不能直接等同于 Python 的词法闭包。跨函数保留定义时的值时，使用上文的默认参数捕获方式。`return a, b` 不支持；多个值可写 `return [a, b]` 或 `return (a, b)`，调用方再按索引取值。

## 异常与宿主调用

`try {...} catch(err) {...} finally {...}` 可以捕获异常；`catch` 和 `except` 等价。不需要异常对象时必须连括号一起省略，写 `catch {...}` 或 `except {...}`；`catch()` 和 `except()` 不是合法语法，会报“期待异常变量名”。`try` 至少要有 `catch`/`except` 或 `finally`。`finally` 总会执行，也可以改变已有控制流。`raise_err("message")` 是 Core 内置调用，不是关键字。

```et
try {
    raise_err("failed")
} catch(err) {
    print(err)
} finally {
    print("done")
}
```

Python 宿主可用 `run(path, fs={"double": python_function})` 注入函数，ET 再调用 `double(21)`。Python 内置函数如 `print` 也能被运行时解析。Core 包含 `include(path)`、`import(...)`、`pip(...)`、`get_sys_func(...)`、`set_sys_func(...)`、`restart()`、`close(...)` 等函数；这些能力不是安全沙箱。`wait_time`、`run_pycode` 和 RPA 函数**不是**本仓库 Core 内置能力，使用前须由宿主提供。

ET 代码不支持 Python 的 `with ... as ...`；编写 ET 业务逻辑时不要借助宿主的 `run_pycode` 绕过 ET，除非用户明确要求或确有 ET 无法完成的必要操作。

使用宿主提供的 Tkinter 开发界面时，`Button` 的 `command` 和 `bind` 等回调不要直接绑定 ET 函数；可优先使用 Tcl 命令（如 `command="set et_event clicked"`）写入事件变量，再在 ET 主线程中轮询 `root.getvar("et_event")` 并处理业务。此模式须在实际宿主中验证事件循环、轮询间隔及窗口关闭行为；纯 Core 不提供 Tkinter 集成。

## 引入文件、模块与后台任务

`include(path)` 可以理解为**运行到这一句时才进行的一次编译**：解释器此时读取并编译 `path` 指向的 ET 文件，把得到的指令插入 `include` 所在的当前执行流位置，然后接着执行，并非启动一个独立脚本或创建独立作用域。被包含代码与调用处**共享当前上下文**：它可以读取和更新调用处已有变量，在该上下文中新建的变量、函数也能由 `include` 后续的代码直接使用。如果 `include` 写在某个函数或代码块内，共享的是该调用位置的上下文，不会让块内新变量自动变成全局变量。

例如，`config.et` 内容为：

```et
count = count + 1
message = "ready"
```

主脚本可以写：

```et
count = 0
include("C:/work/config.et")
print(count)   // 1
print(message) // ready
```

由于不是独立调用，被包含文件中的顶层 `return` 会结束当前执行流程，`include` 后的语句不会继续执行。路径推荐使用绝对路径：相对路径并不固定相对当前脚本；若当前工作目录没有该文件，会回退到 `ET_EXE_DIR` / `ET_ROOT_DIR` 或内核目录。

`import("json")` 导入模块并自动绑定变量 `json`；`import("matplotlib.pyplot")` 自动绑定末段名称 `pyplot`，也可显式写 `pd = import("pandas")`。不支持 Python 的 `from ... import ...` 语法。`import` 可传模块名、pip 包名、是否自动安装、项目路径、是否重新加载和镜像地址；**未指定时自动安装默认开启**。不希望脚本安装包时传 `import("json", "", false)`。`pip("package")` 可调用当前 Python 环境的 pip 安装依赖；使用这些能力前须确认部署环境和权限。

`backrun(n="job", i=1){...}` 是定义即注册的后台任务，不是先定义再调用的普通函数。第一个参数指定任务名，第二个（可省略）指定周期秒数；**当前 Core 最多允许两个形参**，旧文档里“可继续传第三个参数”的说明不适用。同名任务会先尝试关闭旧任务，`close("job")` 关闭指定任务，`close()` 请求关闭所有任务。任务内 `return` 停止当前任务；主脚本运行完毕后仍会等待注册的后台任务全部退出。任务参数会在多轮执行间保留，且与主流程共享外层对象时需考虑线程并发。

## 类与继承

类沿用函数式定义：`类名(构造参数){...}`。类体中用 `this()` 创建当前实例，再以 `this.属性 = 值` 初始化属性；类体内定义的方法可以通过实例调用，在方法中用 `this.属性` 读取实例属性。继承时在子类体中写 `this = 父类(参数)`，先取得父类实例，再设置子类属性和定义子类方法。不使用 Python 的 `class`、`def` 语法。**纯 Core 不内置 `this()`**；运行下面的例子前，宿主必须通过 `fs` 注入可创建支持弱引用的实例的函数或类，例如 `run(path, fs={"this": This})`，其中 `class This: pass`。实际产品宿主可以提供自己的实例类型。

```et
Dog(name="", age=0){ // 定义类
    this() // 创建实例
    this.name = name
    this.age = age
    run(){
        print("{} - {} start run".format(this.name, this.age))
    }
}

ADog(name, age, lev){
    this = Dog(name, age) // 继承 Dog
    this.lev = lev
    des(arg1){
        print("my lev is {}, arg1={}".format(this.lev, arg1))
    }
}

a = ADog("xiaoA", 22, 8)
a.run()
a.des("hello")
```

预期输出：

```text
xiaoA - 22 start run
my lev is 8, arg1=hello
```

`this()` 和 `this = Dog(...)` 是类定义的关键写法；普通函数定义不需要 `this`。

## AI 生成代码检查清单

1. 使用双引号字符串、`//` 注释、花括号代码块和圆括号条件；不用 Python 的 `def`、`in`、`and`、`or`、`not`。
2. 遍历写 `forin(value, index, source=items){...}`，不用普通 `for`。
3. 要确定返回结果就显式 `return`；不要在中途独立写变量名或字面量语句。
4. 确认宿主注入的函数清单；先用 `Core.core.run_compile(path)` 检查编译，再用 `run(path, fs=...)` 实测。编译检查不会验证宿主函数是否可用。
5. 不用 `with ... as ...`、`lambda`、多目标赋值或 `[:]`；索引位置更新写 `items[i] = items[i] + 1`，不要写 `items[i] += 1`。
6. 业务逻辑优先用 ET 编写；`cut_index`、`cut_pattern`、`run_pycode` 和 Tkinter 事件桥接都须确认宿主是否提供及其具体用法。
7. 写类时在类体中使用 `this()`；继承时用 `this = 父类(...)`，方法通过实例调用并用 `this` 访问属性。纯 Core 运行前先确认宿主已注入 `this`。
8. `if`、`else`、`while`、`forin` 等块内新建的变量不能在块外读取；若后续需要使用，先在块外初始化，勿照搬 Python 的写法。
