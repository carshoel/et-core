from typing import List

from Core.Interpreter.model.ae_sel import AESel
from Core.Interpreter.model.ae_var import AEArg


class AEBlock(object):
    BLOCK_TYPE_MODEL = 0
    BLOCK_TYPE_SEL = 1
    BLOCK_TYPE_CLASS = 2
    BLOCK_TYPE_BODY = 3

    def __init__(self, sel_list: list[AESel] = None, name: str = None, args: List[AEArg] = None, super_block: "AEBlock" = None):
        self.sel_list: list[AESel] = [] if sel_list is None else sel_list
        self.name = name
        self.args = args
        self.super_block = super_block
        self.name_space = {}
        self.type = self.BLOCK_TYPE_BODY

    def __repr__(self):
        return f"BLOCK:{self.name}"




