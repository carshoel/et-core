import copy
import weakref
from Core.Interpreter.model.ae_block import AEBlock
from Core.Interpreter.model.ae_sel import AESel
from Core.Interpreter.model.ae_var import AEArg, AEData
from Core.Interpreter.interpret.ae_varcontainer import VarContainer
from Core.Sels.opt_sels import get_sel_list as opt_get_sel_list
import inspect
import threading
import time


class AEInterpreter(object):

    def __init__(self, block: AEBlock, sys_sel_list=None, log_print=print, debug_dic: dict=None):

        # 断点调试
        self.debug_dic = {} if debug_dic is None else debug_dic # key 是文件路径，值为行号到临时调试代码路径的字典


        # 日志系统管理
        self.log = log_print or (lambda *args, **kwargs: None)

        # 内置系统库函数
        from Core.Interpreter.sels.grammar_sels import get_sel_list
        self.inter_sel_list = get_sel_list()
        self.sys_sel_list = opt_get_sel_list()
        if sys_sel_list and isinstance(sys_sel_list, dict):
            self.sys_sel_list.update(sys_sel_list)
        self.version = f"3.0.0"
        self.block = block
        self.top_control_mark = None
        self.thread_list: dict = {}  # 子线程池
        self.thread_lock = threading.RLock()
        self.container = VarContainer(self.log)  # 数据区

    def get_value_by_var(self, var: AEData, block: AEBlock, consume=True):
        if isinstance(var, AEData):
            if var.var_type == AEData.AE_VAR_TYPE_VAR:
                return self.get_value_by_var_name(var.var, block, consume=consume)
            elif var.var_type == AEData.AE_VAR_TYPE_VAL:
                return var.var
            else:
                raise TypeError(f"获取变量值，不支持的变量类型:{var.var_type}")
        else:
            raise TypeError(f"获取变量值时发生类型错误，变量: {var}，类型: {type(var)}")

    def get_block_by_var_name(self, var_name, block: AEBlock, out_stop=False):
        if not block: return None
        if var_name in block.name_space: return block
        if not block.super_block or (out_stop and block.type != AEBlock.BLOCK_TYPE_BODY):
            return None
        return self.get_block_by_var_name(var_name, block.super_block, out_stop)

    def get_value_by_var_name(self, var_name: str, block: AEBlock, consume=True) -> object:
        exist_block = self.get_block_by_var_name(var_name, block)
        if exist_block:
            v_id = exist_block.name_space[var_name]
            v_value = self.container.get_value(v_id)
            if consume and var_name.startswith("#var:"):
                self.container.unuse_var(v_id)
                exist_block.name_space.pop(var_name)
            return v_value
        raise Exception(f"{var_name}: 未定义!")

    def put_value(self, var_name: str, value: object, block: AEBlock):
        exist_block = self.get_block_by_var_name(var_name, block, out_stop=True)
        if exist_block:
            v_id = exist_block.name_space[var_name]
            self.container.unuse_var(v_id)
            exist_block.name_space[var_name] = self.container.put_var(value)
        else:
            block.name_space[var_name] = self.container.put_var(value)

    @staticmethod
    def _copy_flat_sel_list(sel_list):
        """Copy simple flat instructions, or return None for the deepcopy path."""
        if type(sel_list) is not list:
            return None
        copied = []
        seen_args = set()
        seen_arg_lists = set()
        seen_sels = set()
        for sel in sel_list:
            # Reused IR nodes require deepcopy's memo to retain their aliases.
            if id(sel) in seen_sels:
                return None
            seen_sels.add(id(sel))
            if (type(sel) is not AESel or vars(sel).keys() !=
                    {'name', 'args', 'back_var', 'which_line', 'file_path'} or
                    sel.name == 'import' or type(sel.name) is not str or
                    sel.back_var is not None and type(sel.back_var) is not str or
                    type(sel.which_line) is not int or
                    sel.file_path is not None and type(sel.file_path) is not str):
                return None
            if sel.args is None:
                args = None
            elif type(sel.args) is list:
                if id(sel.args) in seen_arg_lists:
                    return None
                seen_arg_lists.add(id(sel.args))
                args = []
                for arg in sel.args:
                    if (type(arg) is not AEData or vars(arg).keys() != {'var', 'var_type'} or
                            type(arg.var) not in (str, int, float, bool, type(None)) or
                            type(arg.var_type) is not int):
                        return None
                    if id(arg) in seen_args:
                        return None
                    seen_args.add(id(arg))
                    args.append(AEData(arg.var, arg.var_type))
            else:
                return None
            new_sel = AESel(sel.name, args, sel.back_var)
            new_sel.which_line = sel.which_line
            new_sel.file_path = sel.file_path
            copied.append(new_sel)
        return copied

    @staticmethod
    def use_block(block: AEBlock):
        sel_list = AEInterpreter._copy_flat_sel_list(block.sel_list)
        if sel_list is None:
            sel_list = copy.deepcopy(block.sel_list)
        new_block = AEBlock(sel_list, f"[call-type]{block.name}", block.args, block.super_block)
        new_block.type = block.type
        return new_block

    def clear_block(self, block: AEBlock):
        self.log(f"释放：{block.name}")
        for k, v in block.name_space.items():
            self.container.unuse_var(v)
        block.name_space.clear()

    def insert_debug(self, tagBlock: AEBlock):
        """注入断点调试"""
        if self.debug_dic and tagBlock.sel_list:
            file_path = None
            for l in tagBlock.sel_list:
                if l.file_path:
                    file_path = l.file_path
                    break
            if file_path in self.debug_dic.keys():
                for i_debug_row in self.debug_dic[file_path].keys():
                    debug_file = self.debug_dic[file_path][i_debug_row]
                    tag_row = int(i_debug_row)
                    _index = -2
                    for i_sel in tagBlock.sel_list:
                        _index += 1
                        if i_sel.which_line == tag_row:
                            # 判断上一个位置是否已经添加了
                            if _index >= 0:
                                front_sel = tagBlock.sel_list[_index]
                                if front_sel.which_line == -1 and front_sel.name == "include" and front_sel.args[0].var == debug_file:
                                        break
                            debug_sel = AESel("include",
                                              [AEData(debug_file, AEData.AE_VAR_TYPE_VAL)])
                            tagBlock.sel_list.insert(tagBlock.sel_list.index(i_sel), debug_sel)


    def start(self, control_mark=None) -> object:
        """外部调用入口"""
        if control_mark is None:
            control_mark = {}
        self.top_control_mark = control_mark
        try:
            back = self.run(self.block, self.top_control_mark)
        except Exception as e:
            try:
                self.container.clear()
                del self.container
                del self.block
            except : pass
            raise e
        # 等待线程结束
        while self.thread_list.keys():
            time.sleep(1)

        if "restart" in self.top_control_mark.keys() and "off" not in self.top_control_mark.keys():
            del back
            self.container.clear()
            self.top_control_mark.clear()
            self.log("正在执行重启！", "yellow")
            return self.start(self.top_control_mark)
        self.container.clear()
        del self.container
        del self.block
        return back

    def run(self, tagBlock: AEBlock = None, control_mark=None) -> object:
        if control_mark is None:
            control_mark = {}
        if not isinstance(tagBlock, AEBlock):
            self.log(f"解释对象不合规")
            return

        self.insert_debug(tagBlock)

        def handle_sel_list(sel_list):
            back = None
            index = 0
            active_logical_temps = set()

            def release_logical_temps():
                for name in active_logical_temps:
                    owner = self.get_block_by_var_name(name, tagBlock)
                    if owner is not None:
                        self.container.unuse_var(owner.name_space.pop(name))
                active_logical_temps.clear()
            while index < len(sel_list):
                sel = sel_list[index]
                index += 1
                try:
                    if sel.name == "#logical_guard":
                        # Peek: #logical_value consumes the selected temporary once.
                        active_logical_temps.add(sel.args[0].var)
                        value = self.get_value_by_var(sel.args[0], tagBlock, consume=False)
                        operator = sel.args[1].var
                        if (operator == "&&" and not value) or (operator == "||" and value):
                            target = sel.args[2].var
                            if not isinstance(target, AESel):
                                raise ValueError("逻辑跳转目标无效")
                            try:
                                index = next(i for i in range(index, len(sel_list)) if sel_list[i] is target)
                            except StopIteration:
                                raise ValueError("逻辑跳转目标不在当前指令块") from None
                        back = value
                    elif sel.name == "#logical_value":
                        back = self.get_value_by_var(sel.args[0], tagBlock)
                        active_logical_temps.discard(sel.args[0].var)
                        if sel.back_var and isinstance(sel.back_var, str):
                            self.put_value(sel.back_var, back, tagBlock)
                    else:
                        back = self.handle_sel(sel, tagBlock, control_mark)
                    if sel.name == "include":
                        back = handle_sel_list(back)

                except Exception as e:
                    release_logical_temps()
                    arg = ""
                    try:
                        for ia in sel.args:
                            arg = f"{arg}{', ' if arg else ''}{ia.var}"
                    except:
                        pass
                    raise ValueError(
                        f"\n文件：{sel.file_path}\n错误行：{sel.which_line}\n函数名称:{sel.name}, 参数:{arg if arg else '无'}\n详情:{e}")
                if "return" in control_mark.keys():
                    back = control_mark["return"]
                    break
                elif "break" in control_mark.keys():
                    break
                elif "continue" in control_mark.keys():
                    break  # 没错
            release_logical_temps()
            return back

        return handle_sel_list(tagBlock.sel_list)



    def handle_sel(self, sel, block, control_mark) -> object:
        at_block = self.get_block_by_var_name(sel.name, block)
        if at_block:
            f = self.container.get_value(at_block.name_space[sel.name])
            if not isinstance(f, AEBlock) and not callable(f):
                raise TypeError(f"非法调用，不可执行的变量：{sel.name}")
        elif sel.name in self.inter_sel_list.keys():
            f = self.inter_sel_list[sel.name]
        elif sel.name in self.sys_sel_list.keys():
            f = self.sys_sel_list[sel.name]
        else:
            try:
                f = eval(sel.name)
            except Exception as e:
                raise ValueError(f"未定义函数:{sel.name}")
        if not f:
            raise ValueError(f"{sel.name}函数未定义!")

        if isinstance(f, AEBlock):
            back = self.call_ae_block(sel, f, block)
        elif f in self.inter_sel_list.values():
            back = self.call_inter_sel(sel, f, block, control_mark)
        elif f in self.sys_sel_list.values():
            back = self.call_sys_sel(sel, f, block, control_mark)
        else:
            back = self.call_notsys_sel(sel, f, block)

        if sel.back_var and isinstance(sel.back_var, str):
            # 处理返回值入栈
            self.put_value(sel.back_var, back, block)
        return back

    def handle_def_args(self, sel: AESel, f_block: AEBlock, block: AEBlock):
        """处理好定义时默认参数"""
        if not f_block.args:
            return
        for i in f_block.args:  # 定义参
            if not isinstance(i, AEArg) or not i.name:
                raise TypeError(f"解析自定义函:{sel.name},参:{i},错误!")
            if i.value.var_type == AEData.AE_VAR_TYPE_VAR:
                v = self.get_value_by_var(i.value, block)
                if block.type == AEBlock.BLOCK_TYPE_CLASS and i.name == "this":
                    i.value.var = weakref.ref(v)
                else:
                    i.value.var = v
                i.value.var_type = AEData.AE_VAR_TYPE_VAL

    @staticmethod
    def _copy_call_default(value, memo):
        """Return this call's default value and memo after a successful copy."""
        # Isolate each attempt so a failed __deepcopy__ cannot leave partial entries.
        # deepcopy keeps references under id(memo); copy that list for this attempt too.
        attempt_memo = memo.copy()
        keepalive = attempt_memo.pop(id(memo), None)
        if keepalive is not None:
            attempt_memo[id(attempt_memo)] = keepalive.copy()
        try:
            copied = copy.deepcopy(value, attempt_memo)
        except Exception:
            return value, memo
        return copied, attempt_memo

    def handle_call_args(self, sel: AESel, f_block: AEBlock):
        """函数调用前参数入栈"""
        if not f_block.args:
            if sel and sel.args:
                raise ValueError(f"函数 {sel.name} 参数过多")
            return
        f_key_list = []
        default_memo = {}  # Shared only by defaults within this invocation.
        for i in f_block.args:  # 形参
            if not isinstance(i, AEArg):
                raise TypeError(f"解析自定义函:{sel.name},{i}, 参数类型错误!")
            if i.value.var_type == AEData.AE_VAR_TYPE_VAR:
                raise TypeError(f"仅限静态参数:{sel.name},参:{i.name},错误!")
            elif i.value.var_type == AEData.AE_VAR_TYPE_VAL:
                if not i.name:
                    raise TypeError(f"解析自定义函:{sel.name},{i}, 参数必须带名字!")
                v, default_memo = self._copy_call_default(i.value.var, default_memo)
                self.put_value(i.name, v, f_block)
                f_key_list.append(i.name)
            else:
                raise TypeError(f"解析自定义函:{sel.name},参:{i},不支持的类型错!")

        # 实参
        if not sel or not sel.args: return
        index = 0
        bound = set()
        for i in sel.args:
            real_arg = self.get_value_by_var(i, f_block.super_block)
            if isinstance(real_arg, AEArg):
                index = -1
                if real_arg.name not in f_key_list or real_arg.name in bound:
                    raise ValueError(f"函数 {sel.name} 参数无效或重复: {real_arg.name}")
                real_value = self.get_value_by_var(real_arg.value, f_block.super_block)
                self.put_value(real_arg.name, real_value, f_block)
                bound.add(real_arg.name)
            else:
                if index == -1:
                    raise Exception(f"实参传递错误!无名参数要在带名参数前面")
                if index >= len(f_key_list):
                    raise ValueError(f"函数 {sel.name} 参数过多")
                self.put_value(f_key_list[index], real_arg, f_block)
                bound.add(f_key_list[index])
                index += 1

    def call_ae_block(self, sel: AESel, f: AEBlock, block: AEBlock) -> object:
        newf = self.use_block(f)
        newf.super_block = block
        try:
            self.handle_call_args(sel, newf)
            #  调用自定义函数
            return self.run(newf, {})
        finally:
            self.clear_block(newf)

    def call_inter_sel(self, sel: AESel, f: type(print), block: AEBlock, control_mark: dict) -> object:
        return f(self, sel, block, control_mark)

    def call_sys_sel(self, sel: AESel, f: type(print), block: AEBlock, control_mark: dict) -> object:
        # 提取参数值
        args, kwargs = self._extract_arguments(sel, f, block)
        # 动态调用
        return self._dynamic_call(f, args, kwargs)

    def call_notsys_sel(self, sel: AESel, f: type(print), block: AEBlock) -> object:
        # 提取参数值
        args, kwargs = self._extract_arguments(sel, f, block)
        # 动态调用
        return self._dynamic_call(f, args, kwargs)

    def _extract_arguments(self, sel, f, block):
        """提取参数并处理命名/位置参数"""
        args = []
        kwargs = {}

        if not sel.args:
            return args, kwargs

        try:
            parameters = list(inspect.signature(f).parameters.values())
        except (TypeError, ValueError):
            parameters = []
        positional = [p for p in parameters if p.kind in
                      (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        has_varargs = any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in parameters)
        current_index = 0
        values = []
        explicit_names = set()
        for arg_expr in sel.args:
            value = self.get_value_by_var(arg_expr, block)
            if isinstance(value, AEArg):
                if not isinstance(value.value, AEData):
                    raise ValueError("命名参数的值必须是AEVar类型")
                explicit_names.add(value.name)
                values.append((value.name, self.get_value_by_var(value.value, block)))
            else:
                values.append((None, value))
        extra = []

        for name, arg_value in values:
            if name is not None:
                kwargs[name] = arg_value
                continue

            while (current_index < len(positional) and
                   positional[current_index].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and
                   positional[current_index].name in explicit_names):
                current_index += 1
            if current_index < len(positional):
                param = positional[current_index]
                if param.kind == inspect.Parameter.POSITIONAL_ONLY:
                    args.append(arg_value)
                else:
                    kwargs[param.name] = arg_value
                current_index += 1
            elif has_varargs:
                extra.append(arg_value)
            else:
                args.append(arg_value)

        if extra:
            # *args requires filling the positional prefix, including named or
            # defaulted slots preceding the variadic parameter.
            prefix = positional[len(args):]
            for param in prefix:
                if param.name in kwargs:
                    args.append(kwargs.pop(param.name))
                elif param.default is not inspect.Parameter.empty:
                    args.append(param.default)
                else:
                    break
            args.extend(extra)
        return args, kwargs

    @staticmethod
    def _dynamic_call(func, args, kwargs):
        """Call exactly once; a TypeError from inside the function is not a binding error."""
        return func(*args, **kwargs)

def get_inner_sys_words():
    """获取系统函数名称"""
    from Core.Interpreter.sels.grammar_sels import get_sel_list
    return get_sel_list().keys()







