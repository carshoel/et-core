from Core.Interpreter.interpret.ae_interpreter import AEInterpreter, get_inner_sys_words
from Core.Compiler.compiler import compile
from Core.Sels.mgr import AEBaseSelMgr, AEBaseSelClass
from pathlib import Path

def run(file_path, fs={}, log=None, compile_log=None, debug_dic=None):
    """
    解释执行文件夹代码
    run 和 include 会对file_path转成完整的正斜杠路径
    debug_dic: 用于断点调试 2维字典，外层的key是要执行的文件的绝对路径，连接符统一用正斜杠。value是又是一个字典，key是断点所在行，value是断点要inlcude的临时文件
    """
    block = compile(file_path, compile_log)
    if block:
        it = AEInterpreter(block, fs, log_print=log, debug_dic=debug_dic)
        try:
            ret = it.start({})
            return ret
        except Exception as e:
            if "[AI_READ 执行结果]:" in str(e):
                ValueError(f"{e}")
            else:
                raise ValueError(f"运行时发生错误:{e}")

def run_compile(file_path):
    """检测代码正确性，编译代码"""
    block = compile(file_path)
    return block

def get_words():
    """获取系统函数名"""
    return get_inner_sys_words()

