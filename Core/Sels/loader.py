from Core.Sels.mgr import AEBaseSelMgr


class AESelLoader(object):

    cache_f_list = None

    @classmethod
    def load_function(cls) -> dict:
        """给解释器注入函数"""
        cls.cache_f_list = AEBaseSelMgr.get_function_list()
        return cls.cache_f_list

    @classmethod
    def all_models(cls):
        """所有模块类，便于类监听解释器运行控制流程"""
        return AEBaseSelMgr.model_list

    @classmethod
    def document(cls) -> dict:
        """ide调用 获取文档"""
        return AEBaseSelMgr.mode_func_document()

    @classmethod
    def sys_words(cls) -> list:
        """获取系统函数名"""
        return AEBaseSelMgr.sys_words
