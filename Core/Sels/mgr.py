import inspect
import builtins # 必须引入原始内置模块


def myprint(*args, **kwargs):
    kwargs["flush"] = True
    # 使用 builtins.print 确保调用的是原始的打印函数，避免递归
    builtins.print(*args, **kwargs)


print = myprint


def get_cls_static_methods(cls) -> dict:
    """获取类中所有的静态方法"""
    static_methods = {
        name: attr for name, attr in cls.__dict__.items() if isinstance(attr, staticmethod) and not name.startswith("_")
    }
    return static_methods


class AEBaseSelClass(object):
    """模块函数基类"""
    class_print = myprint
    top_control_mark = None

    @classmethod
    def setup(cls, top_control_mark: dict, class_print=print):
        # 给所有父类设置属性
        for base in cls.__bases__:
            base.top_control_mark = top_control_mark
            if class_print:
                base.class_print = class_print

        cls.top_control_mark = top_control_mark
        if class_print:
            cls.class_print = class_print

    @classmethod
    def get_function_list(cls) -> dict:
        function_list = get_cls_static_methods(cls)
        return function_list


class AEBaseSelMgr(object):

    model_list = []
    func_list = {}
    sys_words = []

    @classmethod
    def clear(cls):
        cls.model_list.clear()
        cls.func_list.clear()
        cls.sys_words.clear()

    @classmethod
    def add_func_model(cls, f_model, mode_name):
        if mode_name not in cls.func_list.keys():
            cls.model_list.append(f_model)
            cls.func_list[mode_name] = f_model.get_function_list()
            cls.sys_words.extend([k for k in f_model.get_function_list().keys()])

    @classmethod
    def get_function_list(cls):
        f_list = {}
        for mode_name in cls.func_list.keys():
            f_list.update(cls.func_list[mode_name])
        return f_list

    @classmethod
    def mode_func_document(cls):
        document = {}
        for m_name in cls.func_list:
            api_str_list = []
            for i_f in cls.func_list[m_name]:
                f_name, f_docu = AEBaseSelMgr.get_function_info(cls.func_list[m_name][i_f])
                if str(f_name).startswith("<built-in function "):
                    f_name = f_name.replace("<built-in function ", "")
                    f_name = f_name.replace(">", "")
                if str(f_name).startswith("<lambda>"):
                    f_name = f_name.replace("<lambda>", i_f)
                api_str_list.append((f_name, f_docu))
            document[m_name] = api_str_list
        return document

    @staticmethod
    def get_function_info(func) -> tuple:
        """获取函数的名称、参数和文档字符串"""
        try:
            func_name = func.__name__
            sig = inspect.signature(func)
            docstring = func.__doc__.strip() if func.__doc__ else ""
        except:
            return (f"{func}", "")
        return (f"{func_name}{sig}", docstring)




