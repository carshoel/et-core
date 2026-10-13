
class AEData(object):
    """调用时函数参数"""
    AE_VAR_TYPE_VAL = 1  # 值量
    AE_VAR_TYPE_VAR = 2  # 标识符

    def __init__(self, var, var_type=AE_VAR_TYPE_VAL):
        self.var = var
        self.var_type = var_type

    def __repr__(self):
        return f"Data:{self.var}"


class AEArg(object):
    """定义时函数参数"""
    def __init__(self, name: str, value: AEData):
        self.name = name
        self.value: AEData = value

    def __repr__(self):
        return f"ARG:{self.name}"


class AEValue(object):
    """运行时内存值"""
    def __init__(self, v: object, k: str):
        self.v: object = v
        self.k: str = k
        self.ref_count: int = 1



