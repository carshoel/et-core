"""数据存储器"""
from typing import Dict
from Core.Interpreter.model.ae_var import AEValue
from Core.Tool.id_make import IdGenerator


class VarContainer(object):
    def __init__(self, log=None):
        self.values: Dict[str, AEValue] = {}
        self.idGenerator: IdGenerator = IdGenerator()
        self.setup_log_print(log)

    def setup_log_print(self, log_print_f):
        self.log_print = log_print_f or (lambda *args, **kwargs: None)

    def clear(self):
        self.log_print(f"清空内存数据{len(self.values.keys())}粒")
        self.values.clear()

    def put_var(self, v: object):
        in_v = AEValue(v, self.idGenerator.get_next_key(self.values.keys()))
        self.values[in_v.k] = in_v
        return in_v.k

    def unuse_var(self, v_id: str):
        if v_id not in self.values.keys():
            raise KeyError(f"unuse_var指针:{v_id}不存在!")
        v = self.values[v_id]
        v.ref_count -= 1
        if v.ref_count <= 0:
            self.log_print(f"注销数据 {v.k}:{v.v}")
            self.values.pop(v.k)
        return v.ref_count

    def reuse_var(self, v_id: str):
        if v_id not in self.values.keys():
            raise KeyError(f"reuse_var指针:{v_id}不存在!")
        v = self.values[v_id]
        v.ref_count += 1
        return v.ref_count

    def change_value(self, v_id: str, new_v: object):
        if v_id not in self.values.keys():
            raise KeyError(f"change_var指针:{v_id}不存在!")
        self.values[v_id].v = new_v

    def get_value(self, v_id: str):
        if v_id not in self.values.keys():
            raise KeyError(f"get_value指针:{v_id}不存在!")
        return self.values[v_id].v


