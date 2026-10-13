import os

from Core.Compiler.ast_to_code import CodeGenerator
from Core.Compiler.lexer import Lexer
from Core.Compiler.mx import MatrixParser
from Core.Interpreter.model.ae_block import AEBlock
from Core.Interpreter.model.ae_sel import AESel
from Core.Interpreter.model.ae_var import AEData


def replace_ddxx(sel_list: list[AESel], gener: CodeGenerator):
    """处理++ --运算"""
    index = 0
    while index < len(sel_list):
        sel = sel_list[index]
        if sel.name in ["++", "--"]:  # 拆解
            try:
                sel_list.pop(index)
                left_arg = sel.args[0]
                right_arg = sel.args[1]
                if left_arg.var_type == AEData.AE_VAR_TYPE_VAL:
                    if left_arg.var is None:
                        sel_list.insert(index, AESel("=", args=[AEData(sel.back_var), right_arg]))
                        sel_list.insert(index, AESel(sel.name[0], args=[right_arg, AEData(1)], back_var=right_arg.var))
                    else:
                        raise ValueError(f"语法错误:{sel.name}为前置单目运算, 左值当为空")
                else:
                    if right_arg.var is None:
                        if sel.back_var:
                            b = AEData(sel.back_var, AEData.AE_VAR_TYPE_VAR)
                        else:
                            b = AEData(gener.varKeyGenerator.get_next_key(sel_list), AEData.AE_VAR_TYPE_VAR)
                        s1 = AESel("=", args=[b, left_arg])
                        s2 = AESel(sel.name[0], args=[left_arg, AEData(1)], back_var=left_arg.var)
                        s3 = AESel("=", args=[b, b])
                        sel_list.insert(index, s3)
                        sel_list.insert(index, s2)
                        sel_list.insert(index, s1)
                    else:
                        raise ValueError(f"语法错误:{sel.name}为后置单目运算, 右值当为空")
            except Exception as e:
                raise ValueError(f"代码优化异常:{e}")

        for arg in sel.args or []:
            if arg.var_type == AEData.AE_VAR_TYPE_VAL and isinstance(arg.var, AEBlock):
                replace_ddxx(arg.var.sel_list, gener)

        index += 1


def compile(file_path, log=None) -> AEBlock:
    from pathlib import Path
    file_path = os.path.abspath(file_path)  # 转换为全路径
    file_path = Path(file_path).as_posix()  # 转换为正斜杠

    try:
        with open(file_path, encoding="utf-8") as file:
            code = file.read()
    except Exception as e:
        raise ValueError(f"编译错误：\n文件:{file_path}\n类型：打开异常\n{e}")

    try:
        lexer = Lexer(code, log)
        tokens = lexer.tokenize()
    except Exception as e:
        raise ValueError(f"编译错误：\n文件:{file_path}\n类型：词法错误\n{e}")

    try:
        program = MatrixParser(tokens).parse()
    except Exception as e:
        raise ValueError(f"编译错误：\n文件:{file_path}\n类型：语法错误\n{e}")

    try:
        gener = CodeGenerator()
        sel_list = gener.handle(program.statements, file_path)
    except Exception as e:
        raise ValueError(f"编译错误：\n文件:{file_path}\n类型：代码生成错误\n{e}")

    replace_ddxx(sel_list, gener)

    return AEBlock(sel_list, os.path.basename(file_path))

