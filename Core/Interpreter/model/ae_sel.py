from Core.Interpreter.model.ae_var import AEData
from typing import List


class AESel(object):
    def __init__(self, name: str, args: List[AEData] = None, back_var: str = None):
        self.name = name
        self.args = args
        self.back_var = back_var  # 要存放或修改的变量名
        self.which_line = -1
        self.file_path = None # 方法所属文件 用于定位bug

    def __repr__(self):
        return f"SEL:{self.name}"

