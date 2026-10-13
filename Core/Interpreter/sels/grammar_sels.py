import os
import importlib
import inspect
import sys
from Core.Compiler.compiler import compile
import threading
import weakref
from pathlib import Path
from typing import List

from Core.Interpreter.interpret.ae_interpreter import AEInterpreter
from Core.Interpreter.model.ae_block import AEBlock
from Core.Interpreter.model.ae_sel import AESel
from Core.Interpreter.model.ae_var import AEArg, AEData


def sel_return(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    control_mark["return"] = None
    if sel.args:
        return_values = []
        for i in sel.args:
            v = self.get_value_by_var(i, block)
            if isinstance(v, AEArg):
                v = v.value
            return_values.append(v)
        if len(return_values) == 1: return_values = return_values[0]
        control_mark["return"] = return_values
    return control_mark["return"]


def sel_break(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    control_mark[sel.name] = True


def _run_conditional_branch(self: AEInterpreter, condition: AEBlock, body: AEBlock,
                            else_body: AEBlock, block: AEBlock, branch_control_mark: dict):
    condition = self.use_block(condition)
    condition.super_block = block
    try:
        selected = body if self.run(condition, {}) else else_body
        if selected:
            selected = self.use_block(selected)
            selected.super_block = condition
            try:
                return self.run(selected, branch_control_mark)
            finally:
                self.clear_block(selected)
    finally:
        self.clear_block(condition)


# ? 三目运算
def sel_ask(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    condition = None
    body = None
    else_body = None
    for arg in sel.args:
        b: AEBlock = arg.var
        if b.name == '?-condition':
            condition = b
        elif b.name == '?-true':
            body = b
        elif b.name == '?-false':
            else_body = b

    if condition is None:
        raise ValueError(f"? 语句缺少条件参数")

    return _run_conditional_branch(self, condition, body, else_body, block, {})

# if
def sel_if(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    condition = None
    body = None
    else_body = None
    for arg in sel.args:
        b: AEBlock = arg.var
        if b.name == 'if-condition':
            condition = b
        elif b.name == 'if-body':
            body = b
        elif b.name == 'else-body':
            else_body = b

    if condition is None:
        raise ValueError(f"if 语句缺少条件参数")

    return _run_conditional_branch(self, condition, body, else_body, block, control_mark)


# while
def sel_while(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    while_control_mark = {}
    condition = None
    body = None
    for arg in sel.args:
        b: AEBlock = arg.var
        if b.name == 'while-condition':
            condition = b
        elif b.name == 'while-body':
            body = b
    if not condition:
        raise Exception(f"while 语句确实条件参数")
    back = awhile(self, condition, body, block, while_control_mark)
    if "return" in while_control_mark:
        control_mark["return"] = while_control_mark["return"]
    if "restart" in while_control_mark:
        self.top_control_mark["restart"] = while_control_mark["restart"]
    return back


#  --while
def awhile(self: AEInterpreter, condition: AEBlock, body: AEBlock, block: AEBlock, control_mark: dict) -> object:
    condition = self.use_block(condition)
    condition.super_block = block
    try:
        back = None
        while self.run(condition, {}):
            if not body: continue
            new_body = self.use_block(body)
            new_body.super_block = condition
            try:
                self.run(new_body, control_mark)
            finally:
                self.clear_block(new_body)
            # 监控顶层
            if "restart" in self.top_control_mark.keys():
                control_mark["return"] = None
                break
            if "return" in self.top_control_mark.keys():
                control_mark["return"] = None
                back = self.top_control_mark["return"]
                break
            if "break" in control_mark.keys():
                control_mark.pop("break")
                break
            elif "continue" in control_mark.keys():
                control_mark.pop("continue")
                continue
            elif "return" in control_mark.keys():
                return control_mark["return"]
        return back
    finally:
        self.clear_block(condition)


# =
def sel_assignment(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    if len(sel.args) != 2:
        raise Exception(f"赋值语句参数个数错误!")
    value = self.get_value_by_var(sel.args[1], block)
    self.put_value(sel.args[0].var, value, block)
    return value


# def
def sel_def(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    value = self.get_value_by_var(sel.args[1], block)
    if not isinstance(value, AEBlock):
        raise Exception(f"函数类定义，变量赋值错误！")

    if sel.args[0].var == "backrun":
        for item_sel in value.sel_list:
            item_sel.file_path = sel.file_path
        return backrun(self, value, block, control_mark)
    elif sel.args[0].var == "forin":
        for item_sel in value.sel_list:
            item_sel.file_path = sel.file_path
        return forin(self, value, block, control_mark)
    else:
        definition = value
        value = self.use_block(definition)
        value.name = definition.name
        if value.args:
            value.args = [AEArg(arg.name, AEData(arg.value.var, arg.value.var_type))
                          for arg in value.args]
        for item_sel in value.sel_list:
            item_sel.file_path = sel.file_path
        self.handle_def_args(sel, value, block)
        # 判断是否是class
        if isinstance(value, AEBlock) and len(value.sel_list) > 1:
            first_sel = value.sel_list[0]
            if first_sel.name == "this":
                first_sel.back_var = "this"
                aclass(value)
            elif len(value.sel_list) > 1:
                second_sel = value.sel_list[1]
                if second_sel.name == "=" and second_sel.args[0].var == "this":
                    # 说明是继承 把继承类引用进变量
                    if not value.args:
                        value.args = []
                    value.args.append(
                        AEArg(first_sel.name, AEData(self.get_value_by_var_name(first_sel.name, block))))
                    aclass(value)
        value.name = f"[定义版]{value.name}"
        self.put_value(sel.args[0].var, value, block)
        return value


# --forin
def forin(self: AEInterpreter, body: AEBlock, block: AEBlock, control_mark: dict) -> object:
    """自动遍历字典列表里的内容，block 必须3个参数，value, key, tag list or dict"""
    # 处理参数
    if not body.args or len(body.args) != 3:
        raise ValueError("自循环错误，参数必须三个，value, key,list(dict)")
    sel_list = []
    for a in body.args:
        sel = AESel("=", [AEData(a.name, AEData.AE_VAR_TYPE_VAR), a.value])
        sel_list.append(sel)
    arg_block = AEBlock(sel_list, "for_arg", None, block)
    try:
        self.run(arg_block, {})

        body.type = AEBlock.BLOCK_TYPE_BODY
        body.super_block = arg_block
        list_dict = self.get_value_by_var_name(body.args[2].name, arg_block)
        if isinstance(list_dict, dict):
            for k, v in list_dict.items():
                if "return" in self.top_control_mark.keys(): return
                self.put_value(body.args[0].name, v, body)
                self.put_value(body.args[1].name, k, body)
                self.run(body, control_mark)
                if "return" in self.top_control_mark.keys(): return
                if "return" in control_mark.keys(): return
                if "break" in control_mark.keys():
                    control_mark.pop("break")
                    break
                if "continue" in control_mark.keys():
                    control_mark.pop("continue")
            return
        tem_d = list_dict
        if not isinstance(tem_d, list):
            try:
                tem_d = [i for i in list_dict]
            except:
                pass

        if isinstance(tem_d, list):
            i = 0
            while i < len(tem_d):
                if "return" in self.top_control_mark.keys(): return
                v = tem_d[i]
                self.put_value(body.args[0].name, v, body)
                self.put_value(body.args[1].name, i, body)
                self.run(body, control_mark)
                if "return" in self.top_control_mark.keys(): return
                if "return" in control_mark.keys(): return
                if "break" in control_mark.keys():
                    control_mark.pop("break")
                    break
                if "continue" in control_mark.keys():
                    control_mark.pop("continue")
                i += 1
        else:
            raise Exception("遍历对象类型错误，要求是字典or列表")
    finally:
        self.clear_block(body)
        self.clear_block(arg_block)


# --backrun
def backrun(self: AEInterpreter, body: AEBlock, block: AEBlock, control_mark: dict):
    # 处理参数
    if not body.args or len(body.args) > 2:
        raise ValueError("backrun 参数需要任务名和可选间隔")
    sel_list = []
    for a in body.args:
        sel = AESel("=", [AEData(a.name, AEData.AE_VAR_TYPE_VAR), a.value])
        sel_list.append(sel)
    arg_block = AEBlock(sel_list, "backrun_arg", None, block)
    arg_block.type = AEBlock.BLOCK_TYPE_SEL # 把外部同名变量设定到自己作用域
    registered = False
    try:
        self.run(arg_block, {})
        arg_block.type = AEBlock.BLOCK_TYPE_BODY # 归还作用域权限

        thread_name = self.get_value_by_var_name(body.args[0].name, arg_block)
        interval = 1
        if len(body.args) == 2:
            interval = self.get_value_by_var_name(body.args[1].name, arg_block)

        with self.thread_lock:
            previous = self.thread_list.get(thread_name)
            if previous and previous["t"] is threading.current_thread():
                raise RuntimeError(f"backrun[{thread_name}]不能从自身替换线程")
        close(self, thread_name)
        t = threading.Thread(target=worker, args=(self, thread_name, interval))
        thread_dic = {"f": body, "arg_block": arg_block, "control_mark": {}, "stop": threading.Event(), "t": t}
        with self.thread_lock:
            if thread_name in self.thread_list:
                raise RuntimeError(f"backrun[{thread_name}]旧线程仍在登记，无法替换")
            body.super_block = arg_block
            body.type = AEBlock.BLOCK_TYPE_BODY
            body.name = body.name + f"_{thread_name}"
            self.thread_list[thread_name] = thread_dic
            try:
                t.start()
            except BaseException:
                self.thread_list.pop(thread_name)
                raise
            registered = True
        return t
    finally:
        if not registered:
            self.clear_block(arg_block)


# --class
def aclass(value: AEBlock):
    value.type = AEBlock.BLOCK_TYPE_CLASS  # 修改为类 类型
    auto_sel_list = []
    for isel in value.sel_list:
        if isel.name == "=":
            left_v = isel.args[0]
            if left_v.var_type == AEData.AE_VAR_TYPE_VAR and left_v.var != "this":
                auto_sel_list.append(
                    AESel(".=", [AEData("this", AEData.AE_VAR_TYPE_VAR), AEData(left_v.var), isel.args[1]]))
        elif isel.name == "=def":
            method_name = isel.args[0].var
            auto_sel_list.append(
                AESel(".=", [AEData("this", AEData.AE_VAR_TYPE_VAR), AEData(method_name),
                              AEData(method_name, AEData.AE_VAR_TYPE_VAR)]))
            class_sel = isel.args[1]
            if not class_sel.var.args:
                class_sel.var.args = []
            class_sel.var.args.append(AEArg("this", AEData("this", AEData.AE_VAR_TYPE_VAR)))

    value.sel_list.extend(auto_sel_list)
    return_sel = AESel("return", [AEData("this", AEData.AE_VAR_TYPE_VAR)])
    value.sel_list.append(return_sel)


def sel_include(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    if not sel.args:
        return
    file_path = self.get_value_by_var(sel.args[0], block)
    if isinstance(file_path, AEArg):
        file_path = file_path.value
    if not isinstance(file_path, str): return
    if not os.path.exists(file_path) and not os.path.isabs(file_path):
        exe_dir = None
        for env_name in ("ET_EXE_DIR", "ET_ROOT_DIR"):
            candidate = os.environ.get(env_name)
            if candidate and os.path.isabs(candidate) and os.path.isdir(candidate):
                exe_dir = candidate
                break
        if exe_dir is None:
            if getattr(sys, 'frozen', False):
                exe_dir = os.path.dirname(sys.executable)
            else:
                exe_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(exe_dir, file_path)

    try:
        new_block = compile(file_path)
        self.insert_debug(new_block)
    except Exception as e:
        raise ValueError(f"include[{file_path}]异常:{e}")

    sels = new_block.sel_list
    return sels



def sel_get_sys_func(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    if not sel.args:
        raise ValueError(f"get_sys_func参数个数错误!")
    if not sel.back_var:
        raise ValueError(f"get_sys_func必须要有接收对象!")
    arg = self.get_value_by_var(sel.args[0], block)
    try:
        if arg in self.inter_sel_list.keys():
            value = self.inter_sel_list[arg]
        elif arg in self.sys_sel_list.keys():
            value = self.sys_sel_list[arg]
        else:
            raise KeyError(f"get_sys_func: 没有{arg}")
    except Exception as e1:
        try:
            value = eval(arg)
        except Exception as e2:
            raise ValueError(f"get_sys_func:{e1}, {e2}")
    self.put_value(sel.back_var, value, block)
    return value


def sel_set_sys_func(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    if not sel.args or len(sel.args) != 2:
        raise ValueError(f"set_sys_func参数个数错误!")
    arg = self.get_value_by_var(sel.args[0], block)
    fuc = self.get_value_by_var(sel.args[1], block)
    if arg in self.inter_sel_list.keys():
        self.inter_sel_list[arg] = fuc
    else:
        self.sys_sel_list[arg] = fuc


def sel_restart(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    self.top_control_mark[sel.name] = True
    self.top_control_mark["return"] = True
    return sel_return(self, sel, block, control_mark)


def sel_try(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict):
    try_template: AEBlock = self.get_value_by_var(sel.args[0], block)
    except_list: List[AEBlock] = self.get_value_by_var(sel.args[1], block)

    try:
        if try_template is not None:
            try_block = self.use_block(try_template)
            try_block.super_block = block
            try:
                return self.run(try_block, control_mark)
            finally:
                self.clear_block(try_block)
    except Exception as e:
        if not except_list:
            raise
        back = None
        for ex_template in except_list:
            ex_block = self.use_block(ex_template)
            ex_block.super_block = block
            try:
                if ex_template.args:
                    arg = ex_template.args[0]
                    ex_block.args = [AEArg(arg.name, AEData(e))]
                    self.handle_call_args(AESel("tem"), ex_block)
                back = self.run(ex_block, control_mark)
            finally:
                self.clear_block(ex_block)
        return back
    finally:
        if len(sel.args) == 3:
            finally_template: AEBlock = self.get_value_by_var(sel.args[2], block)
            finally_block = self.use_block(finally_template)
            finally_block.super_block = block
            pending = {key: control_mark.pop(key) for key in ("return", "break", "continue")
                       if key in control_mark}
            try:
                self.run(finally_block, control_mark)
            finally:
                self.clear_block(finally_block)
            if not any(key in control_mark for key in ("return", "break", "continue")):
                control_mark.update(pending)

# --线程用
def worker(self, name, delay):
    """线程执行的任务函数"""
    with self.thread_lock:
        thread_dic = self.thread_list[name]
    f: AEBlock = thread_dic["f"]
    control_mark = thread_dic["control_mark"]
    try:
        while not thread_dic["stop"].is_set():
            if "restart" in self.top_control_mark.keys(): break
            if "return" in self.top_control_mark.keys(): break
            self.run(f, control_mark)
            if "return" in control_mark.keys():
                break
            thread_dic["stop"].wait(delay)
    except Exception as e:
        self.log(f"backrun[{name}]发生错误:{e}", "red")
        raise
    finally:
        # Only this worker releases its body and parameter block after execution.
        with self.thread_lock:
            try:
                try:
                    self.clear_block(f)
                finally:
                    self.clear_block(thread_dic["arg_block"])
            finally:
                if self.thread_list.get(name) is thread_dic:
                    self.thread_list.pop(name)


def sel_dic_init(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    ret = {}
    for i in sel.args:
        item = self.get_value_by_var(i, block)
        if isinstance(item, AEArg):
            ret[item.name] = self.get_value_by_var(item.value, block)
        else:
            raise Exception(f"字典初始化时，参数格式错误！")
    if sel.back_var and isinstance(sel.back_var, str):
        # 处理返回值入栈
        self.put_value(sel.back_var, ret, block)
    return ret


def sel_list_init(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    ret = []
    for i in sel.args:
        ret.append(self.get_value_by_var(i, block))
    if sel.back_var and isinstance(sel.back_var, str):
        # 处理返回值入栈
        self.put_value(sel.back_var, ret, block)
    return ret

def sel_tuple_init(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    ret = []
    for i in sel.args:
        ret.append(self.get_value_by_var(i, block))
    if sel.back_var and isinstance(sel.back_var, str):
        self.put_value(sel.back_var, ret, block)
    return tuple(ret)

def sel_set_init(self: AEInterpreter, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    ret = []
    for i in sel.args:
        ret.append(self.get_value_by_var(i, block))
    if sel.back_var and isinstance(sel.back_var, str):
        self.put_value(sel.back_var, ret, block)
    return set(ret)

def sel_index_read(self, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    if len(sel.args) != 2:
        raise Exception(f"角标访问，只限2个参数")
    content = self.get_value_by_var(sel.args[0], block)
    index = self.get_value_by_var(sel.args[1], block)
    if sel.back_var and isinstance(sel.back_var, str):
        # 处理返回值入栈
        self.put_value(sel.back_var, content[index], block)
    return content[index]


def sel_index_set(self, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    if len(sel.args) != 3:
        raise Exception(f"角标赋值，只限3个参数")
    content = self.get_value_by_var(sel.args[0], block)
    index = self.get_value_by_var(sel.args[1], block)
    value = self.get_value_by_var(sel.args[2], block)
    content[index] = value
    return value


def sel_point_read(self, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    if len(sel.args) != 2:
        raise Exception(f"点访问，只限2个参数")
    content = self.get_value_by_var(sel.args[0], block)
    if isinstance(content, weakref.ReferenceType):
        content = content()
    index = self.get_value_by_var(sel.args[1], block)
    # 静态检查只用于区分缺失属性与执行 getter 后抛出的 AttributeError。
    try:
        inspect.getattr_static(content, index)
    except AttributeError:
        try:
            ret = getattr(content, index)
        except AttributeError:
            ret = content[index]
    else:
        ret = getattr(content, index)
    if sel.back_var and isinstance(sel.back_var, str):
        # 处理返回值入栈
        self.put_value(sel.back_var, ret, block)
    return ret


def sel_point_set(self, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    if len(sel.args) != 3:
        raise Exception(f"点访问，只限3个参数")
    content = self.get_value_by_var(sel.args[0], block)
    index = self.get_value_by_var(sel.args[1], block)
    value = self.get_value_by_var(sel.args[2], block)
    # 优先访问
    if isinstance(content, list) or isinstance(content, dict):
        content[index] = value
    else:
        try:
            exec(f"content.{index}=value")
        except Exception as e:
            raise Exception(f"点语法执行失败:{e}")
    return value


def sel_close(self, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    back = close(self, self.get_value_by_var(sel.args[0], block) if sel.args else None)
    if sel.back_var and isinstance(sel.back_var, str):
        # 处理返回值入栈
        self.put_value(sel.back_var, back, block)
    return back


def _pip(args="", timeout: int = None, mirror: str = "", upgrade_pip: bool = False) -> dict:
    """
    内部 pip 调用函数，使用当前 ET 便携 Python 环境执行：python -m pip ...
    """
    import os
    import sys
    import shlex
    import subprocess
    from pathlib import Path

    def norm_path(p):
        try:
            return str(Path(p).resolve())
        except Exception:
            return str(p)

    def split_args(a):
        if a is None:
            return []

        if isinstance(a, (list, tuple)):
            return [str(x) for x in a]

        if not isinstance(a, str):
            return [str(a)]

        a = a.strip()
        if not a:
            return []

        try:
            return shlex.split(a, posix=True)
        except Exception:
            return a.split()

    def run_cmd(cmd, env):
        creationflags = 0
        try:
            if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags = subprocess.CREATE_NO_WINDOW
        except Exception:
            creationflags = 0

        try:
            p = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                env=env,
                creationflags=creationflags,
            )

            return {
                "ok": p.returncode == 0,
                "returncode": p.returncode,
                "cmd": cmd,
                "stdout": p.stdout or "",
                "stderr": p.stderr or "",
                "python": python_exe,
            }
        except subprocess.TimeoutExpired as e:
            stdout = e.stdout or ""
            stderr = e.stderr or ""

            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")

            return {
                "ok": False,
                "returncode": -1,
                "cmd": cmd,
                "stdout": stdout,
                "stderr": "pip 执行超时: " + str(e) + ("\n" + stderr if stderr else ""),
                "python": python_exe,
            }
        except Exception as e:
            return {
                "ok": False,
                "returncode": -2,
                "cmd": cmd,
                "stdout": "",
                "stderr": str(e),
                "python": python_exe,
            }

    python_exe = norm_path(sys.executable)

    et_python_dir = os.environ.get("ET_PYTHON_DIR", "")
    if et_python_dir:
        candidate = Path(et_python_dir) / "python.exe"
        if candidate.exists():
            python_exe = norm_path(candidate)

    python_dir = str(Path(python_exe).resolve().parent)
    scripts_dir = str(Path(python_dir) / "Scripts")
    dlls_dir = str(Path(python_dir) / "DLLs")

    env = os.environ.copy()
    old_path = env.get("PATH", "")
    path_items = []

    for p in [python_dir, scripts_dir, dlls_dir]:
        try:
            if Path(p).exists():
                path_items.append(p)
        except Exception:
            pass

    if old_path:
        path_items.append(old_path)

    env["PATH"] = os.pathsep.join(path_items)

    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)

    pip_args = split_args(args)

    if not pip_args:
        pip_args = ["--version"]

    pip_commands = {
        "install",
        "uninstall",
        "list",
        "show",
        "freeze",
        "check",
        "search",
        "download",
        "wheel",
        "config",
        "cache",
        "index",
        "debug",
        "help",
        "--version",
        "-V",
        "--help",
        "-h",
    }

    if pip_args[0] not in pip_commands:
        pip_args = ["install"] + pip_args

    if mirror:
        if pip_args and pip_args[0] in ["install", "download", "wheel"]:
            has_index = False
            for x in pip_args:
                if x == "-i" or x == "--index-url" or x.startswith("--index-url="):
                    has_index = True
                    break
            if not has_index:
                pip_args.extend(["-i", mirror])

    if upgrade_pip:
        upgrade_cmd = [python_exe, "-m", "pip", "install", "--upgrade", "pip"]
        upgrade_result = run_cmd(upgrade_cmd, env)
        if not upgrade_result.get("ok"):
            return upgrade_result

    cmd = [python_exe, "-m", "pip"] + pip_args
    return run_cmd(cmd, env)



def _builtin_arg(self, sel, block, index, default=None):
    try:
        if hasattr(sel, "args") and len(sel.args) > index:
            return self.get_value_by_var(sel.args[index], block)
    except Exception:
        pass
    return default


def _builtin_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ["1", "true", "yes", "y", "on"]:
            return True
        if v in ["0", "false", "no", "n", "off", "", "none", "null"]:
            return False
    return bool(value)


def sel_pip(self, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    """
    ET 内置 pip 函数。

    ET 用法:
        pip()
            -> python -m pip --version

        pip("requests")
            -> python -m pip install requests

        pip("install requests")
            -> python -m pip install requests

        pip("install requests -U")
            -> python -m pip install requests -U

        pip("list")
            -> python -m pip list

        pip("show requests")
            -> python -m pip show requests

        pip("uninstall requests -y")
            -> python -m pip uninstall requests -y

        pip("install requests", 120)
            -> timeout=120 秒

        pip("install requests", 120, "https://pypi.tuna.tsinghua.edu.cn/simple")
            -> 使用镜像安装

        pip("install requests", 180, "https://pypi.tuna.tsinghua.edu.cn/simple", true)
            -> 先升级 pip，再安装 requests

    参数顺序:
        pip(args, timeout, mirror, upgrade_pip)

    返回:
        dict，可用 r.ok / r.stdout / r.stderr / r.returncode / r.cmd / r.python 访问。
    """

    pip_args = _builtin_arg(self, sel, block, 0, "")
    timeout = _builtin_arg(self, sel, block, 1, None)
    mirror = _builtin_arg(self, sel, block, 2, "")
    upgrade_pip = _builtin_arg(self, sel, block, 3, False)

    try:
        if timeout is not None and timeout != "":
            timeout = int(timeout)
        else:
            timeout = None
    except Exception:
        timeout = None

    mirror = str(mirror) if mirror else ""
    upgrade_pip = _builtin_bool(upgrade_pip, False)

    return _pip(
        args=pip_args,
        timeout=timeout,
        mirror=mirror,
        upgrade_pip=upgrade_pip,
    )


def sel_import(self, sel: AESel, block: AEBlock, control_mark: dict) -> object:
    """
    ET 内置 import 函数，对标 Python import/importlib.import_module。
    变量自动声明规则:
        import("json")
            -> 自动等价 json = import("json")

        import("matplotlib.pyplot")
            -> 自动等价 pyplot = import("matplotlib.pyplot")

        pd = import("pandas")
            -> 显式赋值给 pd，优先使用显式变量

    ET 用法:
        import("json")
            -> import json，自动生成变量 json

        json = import("json")
            -> 显式返回模块对象

        import("matplotlib.pyplot")
            -> import matplotlib.pyplot，自动生成变量 pyplot

        plt = import("matplotlib.pyplot")
            -> 显式赋值为 plt

        cv2 = import("cv2", "opencv-python")
            -> 模块名 cv2，pip 包名 opencv-python

        PIL = import("PIL", "Pillow")
            -> 模块名 PIL，pip 包名 Pillow

        requests = import("requests", "", true)
            -> 导入失败时自动 pip install requests

        pandas = import("pandas", "", false)
            -> 导入失败不自动安装，直接报错

        mymod = import("mymod", "", false, "D:/my_project")
            -> 先把 D:/my_project 加入 sys.path，再导入 mymod

        mymod = import("mymod", "", false, "D:/my_project", true)
            -> 导入后强制 reload，适合调试本地模块

        requests = import("requests", "requests", true, "", false, "https://pypi.tuna.tsinghua.edu.cn/simple")
            -> 使用镜像自动安装

    参数顺序:
        import(module_name, package_name, auto_install, project_dir, reload, mirror)

    参数说明:
        module_name:
            要导入的模块名，如 "json"、"pandas"、"matplotlib.pyplot"、"cv2"。

        package_name:
            pip 包名。模块名和包名不一致时使用，如 cv2 -> opencv-python。

        auto_install:
            导入失败是否自动 pip install。默认 true，用于兼容旧逻辑。

        project_dir:
            本地项目目录。导入本地模块时使用。

        reload:
            是否强制 importlib.reload。

        mirror:
            pip 镜像地址。
    """
    import sys
    import importlib
    from pathlib import Path

    def add_path_front(path):
        if not path:
            return False

        try:
            p = Path(str(path)).resolve()
        except Exception:
            return False

        if not p.exists() or not p.is_dir():
            return False

        p_str = str(p)
        normalized = []

        for x in sys.path:
            try:
                normalized.append(str(Path(x).resolve()))
            except Exception:
                normalized.append(str(x))

        if p_str in normalized:
            idx = normalized.index(p_str)
            old = sys.path[idx]
            try:
                sys.path.remove(old)
            except Exception:
                pass

        sys.path.insert(0, p_str)
        return True

    module_name = _builtin_arg(self, sel, block, 0, None)
    package_name = _builtin_arg(self, sel, block, 1, "")
    auto_install = _builtin_arg(self, sel, block, 2, True)
    project_dir = _builtin_arg(self, sel, block, 3, "")
    reload_module = _builtin_arg(self, sel, block, 4, False)
    mirror = _builtin_arg(self, sel, block, 5, "")

    if not isinstance(module_name, str) or not module_name.strip():
        raise ImportError("import 参数 module_name 必须是非空字符串")

    module_name = module_name.strip()
    package_name = str(package_name).strip() if package_name else ""
    project_dir = str(project_dir).strip() if project_dir else ""
    mirror = str(mirror).strip() if mirror else ""
    auto_install = _builtin_bool(auto_install, True)
    reload_module = _builtin_bool(reload_module, False)

    # 无显式赋值时，以模块末段名称绑定返回值。
    if not sel.back_var:
        if "." in module_name:
            parts = module_name.split(".")
            sel.back_var = parts[len(parts) - 1]
        else:
            sel.back_var = module_name

    if project_dir:
        add_path_front(project_dir)

    try:
        importlib.invalidate_caches()
    except Exception:
        pass

    try:
        module = importlib.import_module(module_name)
        if reload_module:
            module = importlib.reload(module)

        return module

    except Exception as first_err:
        if not auto_install:
            raise ImportError(f"导入模块失败: {module_name}, 错误: {first_err}") from first_err

        pip_package = package_name if package_name else module_name.split(".")[0]

        pip_result = _pip(
            args=["install", pip_package],
            timeout=None,
            mirror=mirror,
            upgrade_pip=False,
        )

        if not isinstance(pip_result, dict) or not pip_result.get("ok"):
            raise ImportError(
                "导入模块失败，自动安装也失败: "
                f"module={module_name}, package={pip_package}, "
                f"import_error={first_err}, pip_result={pip_result}"
            ) from first_err

        try:
            importlib.invalidate_caches()
        except Exception:
            pass

        try:
            module = importlib.import_module(module_name)
            if reload_module:
                module = importlib.reload(module)

            return module

        except Exception as second_err:
            raise ImportError(
                "自动安装成功但仍然导入失败: "
                f"module={module_name}, package={pip_package}, 错误={second_err}"
            ) from second_err


# -- close
def close(self, name=None):
    """关闭指定线程"""
    tem = []
    if not name:
        with self.thread_lock:
            tem = list(self.thread_list)
    elif isinstance(name, list):
        tem.extend(name)
    elif isinstance(name, str):
        tem.append(name)
    close_count = 0
    for t_name in dict.fromkeys(tem):
        with self.thread_lock:
            thread_dic = self.thread_list.get(t_name)
            if thread_dic is None:
                continue
            thread_dic["stop"].set()
            thread = thread_dic["t"]
            if thread is threading.current_thread():
                # Make run() stop before the next instruction in this worker body.
                thread_dic["control_mark"]["return"] = None
        if thread is not threading.current_thread():
            thread.join(timeout=2)
            if thread.is_alive():
                raise TimeoutError(f"backrun[{t_name}]关闭超时，线程仍在运行")
            # Worker clears its owned blocks before unregistering.
        close_count += 1
    return close_count

def sel_raise_err(self, sel: AESel, block: AEBlock, control_mark: dict):
    """抛出错误"""
    if not sel.args:
        return
    err = self.get_value_by_var(sel.args[0], block)
    if isinstance(err, AEArg):
        err = err.value
    raise Exception(err)

def sel_ai_read(self, sel: AESel, block: AEBlock, control_mark: dict):
    """终止程序，抛出信息"""
    if not sel.args:
        return
    msg = self.get_value_by_var(sel.args[0], block)
    if isinstance(msg, AEArg):
        msg = msg.value
    raise Exception("[AI_READ 执行结果]: " + str(msg))


def get_sel_list() -> dict:
    sel_dic = {
        "import": sel_import,
        "pip": sel_pip,
        "close": sel_close,
        "return": sel_return,
        "break": sel_break,
        "continue": sel_break,
        "if": sel_if,
        "while": sel_while,
        "=": sel_assignment,
        "=def": sel_def,
        "include": sel_include,
        "get_sys_func": sel_get_sys_func,
        "set_sys_func": sel_set_sys_func,
        "restart": sel_restart,
        "try": sel_try,
        "{}": sel_dic_init,
        "{set}": sel_set_init,
        "[]": sel_list_init,
        "()": sel_tuple_init,
        "[ik]": sel_index_read,
        "[ik]=": sel_index_set,
        ".": sel_point_read,
        ".=": sel_point_set,
        "?": sel_ask,
        "ai_read": sel_ai_read,
        "raise_err": sel_raise_err,
    }
    return sel_dic



