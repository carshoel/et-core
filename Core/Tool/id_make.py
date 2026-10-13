import threading


class IdMaker(object):
    def __init__(self, key_format: str = "#{count}", max_num=-1):
        self.counter = 0
        self.lock = threading.Lock()
        self.max_num = max_num
        self.key_format = key_format

    def get_next_key(self, exist_keys=None) -> str:
        with self.lock:
            attempts = 0
            while True:
                if self.max_num != -1 and self.counter > self.max_num:
                    self.counter = 0
                key = self.key_format.format(count=self.counter)
                self.counter += 1
                if not exist_keys or key not in exist_keys:
                    return key
                attempts += 1
                if self.max_num != -1 and attempts > self.max_num:
                    raise ValueError("没有可用的 ID")
                if self.max_num == -1 and attempts > len(exist_keys):
                    raise ValueError("没有可用的 ID")


class IdGenerator(IdMaker):
    """生成ip地址"""

    def __init__(self, key_format: str = "#id:{count:07d}", max_num=9999999):
        super().__init__(key_format, max_num)


class VarKeyGenerator(IdMaker):
    """生成变量名"""

    def __init__(self, key_format: str = "#var:{count:03d}", max_num=-1):
        super().__init__(key_format, max_num)
