from Core.Tool.id_make import VarKeyGenerator
from typing import List

from Core.Interpreter.model.ae_block import AEBlock
from Core.Interpreter.model.ae_sel import AESel
from Core.Interpreter.model.ae_var import AEArg, AEData
from Core.Compiler.parser import (
    ASTNode, Assignment, BinaryOp, BreakStatement, CompoundAssignment,
    ContinueStatement, DictLiteral, ForStatement, FunctionCall,
    FunctionDefinition, Identifier, IfStatement, ListLiteral, Literal,
    MemberAccess, Parameter, ReturnStatement, SetLiteral, Subscript,
    TernaryOp, TryStatement, TupleLiteral, UnaryOp, WhileStatement,
)


class CodeGenerator(object):

    def __init__(self):
        self.varKeyGenerator = VarKeyGenerator()

    def _temp_data(self, node, sel_list):
        node_sel = self.routeASTNodeHandleFunction(node)(node, sel_list)
        sel_list.append(node_sel)
        name = self.varKeyGenerator.get_next_key()
        node_sel.back_var = name
        return AEData(name, AEData.AE_VAR_TYPE_VAR)

    def _arg_temp_data(self, node, sel_list):
        # 指定参数和默认值先取序号，再递归处理操作数。
        name = self.varKeyGenerator.get_next_key()
        node_sel = self.routeASTNodeHandleFunction(node)(node, sel_list)
        sel_list.append(node_sel)
        node_sel.back_var = name
        return AEData(name, AEData.AE_VAR_TYPE_VAR)

    def _operand_data(self, node, sel_list, temp=None):
        if isinstance(node, Identifier):
            return AEData(node.name, AEData.AE_VAR_TYPE_VAR)
        if isinstance(node, Literal):
            self.format_literal_value(node)
            return AEData(node.value)
        return (temp or self._temp_data)(node, sel_list)

    def _condition_block(self, condition, label):
        condition_sel_list = []
        if isinstance(condition, (Identifier, Literal)):
            condition = FunctionCall(Identifier("bool"), [condition])
        condition_sel = self.routeASTNodeHandleFunction(condition)(condition, condition_sel_list)
        condition_sel_list.append(condition_sel)
        return_value_name = self.varKeyGenerator.get_next_key()
        condition_sel.back_var = return_value_name
        return_sel = AESel("return", [AEData(return_value_name, AEData.AE_VAR_TYPE_VAR)])
        condition_sel_list.append(return_sel)
        condition_block = AEBlock(condition_sel_list, label)
        condition_block.type = AEBlock.BLOCK_TYPE_BODY
        return condition_block

    def handleFunctionCall(self, f_call: FunctionCall, sel_list: list) -> AESel:
        f_name = None
        if isinstance(f_call.func, Identifier):
            f_name = f_call.func.name
        else:
            astHandleFunc = self.routeASTNodeHandleFunction(f_call.func)
            f_name_sel = astHandleFunc(f_call.func, sel_list)
            sel_list.append(f_name_sel)
            f_name = self.varKeyGenerator.get_next_key()
            f_name_sel.back_var = f_name
        f_args = None
        if f_call.arguments:
            f_args = []
            for arg in f_call.arguments:
                if isinstance(arg, Assignment):  # 指定参数
                    if isinstance(arg.target, Identifier):
                        a_name = arg.target.name
                    else:
                        raise TypeError(f"指定参数名称限制为标识符:{arg}")
                    a_value = self._operand_data(arg.value, sel_list, self._arg_temp_data)
                    f_args.append(AEData(AEArg(a_name, a_value)))
                else:
                    f_args.append(self._operand_data(arg, sel_list, self._arg_temp_data))

        sel = AESel(f_name, f_args)
        return sel

    def handleAssignment(self, astNode: Assignment, sel_list: list) -> AESel:
        f_name = "="
        f_args = []

        # 数组字典设值
        # index set dict["name"] list[2]
        if isinstance(astNode.target, Subscript):
            f_name = "[ik]="
            arg1 = astNode.target.array
            if isinstance(arg1, Literal):
                raise TypeError(f"字面量不能修改{arg1}")
            f_args.append(self._operand_data(arg1, sel_list))

            arg2 = astNode.target.index
            f_args.append(self._operand_data(arg2, sel_list))

            f_args.append(self._operand_data(astNode.value, sel_list))
            return AESel(f_name, f_args)

        # 点赋值
        if isinstance(astNode.target, MemberAccess):
            f_name = ".="
            f_args = []
            arg_list = [astNode.target.object, Literal(astNode.target.member), astNode.value]
            arg1 = None
            for v in arg_list:
                if isinstance(v, Literal) and arg1 is None:
                    raise TypeError(f"无法访问修改的成员变量属性: {arg1}")
                aev = self._operand_data(v, sel_list)
                f_args.append(aev)
                if not arg1: arg1 = aev
            return AESel(f_name, f_args)

        # 普通赋值
        if isinstance(astNode.target, Identifier):
            f_args.append(AEData(astNode.target.name, AEData.AE_VAR_TYPE_VAR))
        else:
            f_args.append(self._temp_data(astNode.target, sel_list))
        f_args.append(self._operand_data(astNode.value, sel_list))
        sel = AESel(f_name, f_args)
        return sel

    def handleMemberAccess(self, astNode: MemberAccess, sel_list: list) -> AESel:
        f_name = "."
        f_args = []
        ast_list = [astNode.object, Literal(astNode.member)]
        for v in ast_list:
            aev = self._operand_data(v, sel_list)
            f_args.append(aev)
        return AESel(f_name, f_args)

    def _emit_logical_operand(self, node, sel_list, target):
        # Store either operand in the same slot; only the selected value survives.
        if isinstance(node, (Identifier, Literal)):
            sel_list.append(AESel("=", [AEData(target, AEData.AE_VAR_TYPE_VAR),
                                       self._operand_data(node, sel_list)]))
        else:
            sel = self.routeASTNodeHandleFunction(node)(node, sel_list)
            sel_list.append(sel)
            sel.back_var = target

    def _handle_logical(self, astNode: BinaryOp, sel_list: list) -> AESel:
        target = self.varKeyGenerator.get_next_key()
        self._emit_logical_operand(astNode.left, sel_list, target)
        result = AESel("#logical_value", [AEData(target, AEData.AE_VAR_TYPE_VAR)])
        sel_list.append(AESel("#logical_guard", [AEData(target, AEData.AE_VAR_TYPE_VAR),
                                                 AEData(astNode.operator), AEData(result)]))
        self._emit_logical_operand(astNode.right, sel_list, target)
        return result

    def handleBinaryOp(self, astNode: BinaryOp, sel_list: list) -> AESel:
        if astNode.operator in ("&&", "||"):
            return self._handle_logical(astNode, sel_list)
        f_name = astNode.operator
        f_args = []
        if astNode.left:
                f_args.append(self._operand_data(astNode.left, sel_list))
        if astNode.right:
                f_args.append(self._operand_data(astNode.right, sel_list))
        sel = AESel(f_name, f_args)
        return sel

    def handleUnaryOp(self, astNode: UnaryOp, sel_list: list) -> AESel:
        f_name = astNode.operator
        f_args = []
        if f_name in ['-', '+', '!', '~']:
            if f_name in ['-', '+']:
                f_args.append(AEData(0))
            right_v = astNode.operand
            f_args.append(self._operand_data(right_v, sel_list))

            # 处理！非运算
            if f_name in ['!']:
                sel = AESel("bool", f_args)
                sel.back_var = self.varKeyGenerator.get_next_key()
                sel_list.append(sel)
                f_name = "=="
                f_args = [AEData(sel.back_var, AEData.AE_VAR_TYPE_VAR), AEData(False)]

        elif f_name in ["++", "--"]:  # 处理值左右顺序
            v = self._operand_data(astNode.operand, sel_list)
            if astNode.is_postfix:
                f_args.append(v)
                f_args.append(AEData(None))
            else:
                f_args.append(AEData(None))
                f_args.append(v)
        else:
            raise TypeError(f"请手动完成未支持的单目运算: {f_name}")
        sel = AESel(f_name, f_args)
        return sel

    def handleTernaryOp(self, astNode: TernaryOp, sel_list: list) -> AESel:
        f_name = "?"
        f_args = []
        f_args.append(AEData(self._condition_block(astNode.condition, "?-condition")))

        if astNode.true_expr:
            true_expr_sel_list = self.handle([astNode.true_expr])
            true_expr_block = AEBlock(true_expr_sel_list, "?-true")
            true_expr_block.type = AEBlock.BLOCK_TYPE_BODY
            f_args.append(AEData(true_expr_block))
        else:
            raise TypeError(f"{astNode.row}行， 三目运算?错误: 缺少真值")
        if astNode.false_expr:
            false_expr_sel_list = self.handle([astNode.false_expr])
            false_expr_block = AEBlock(false_expr_sel_list, "?-false")
            false_expr_block.type = AEBlock.BLOCK_TYPE_BODY
            f_args.append(AEData(false_expr_block))
        else:
            raise TypeError(f"{astNode.row}行， 三目运算?错误: 缺少假值")

        sel = AESel(f_name, f_args)
        return sel

    def handleCompoundAssignment(self, astNode: CompoundAssignment, sel_list: list) -> AESel:
        f_name = astNode.operator
        f_args = []
        # f_name = f_name + "="
        f_args.append(AEData(astNode.target.name, AEData.AE_VAR_TYPE_VAR))

        right_v = astNode.value
        f_args.append(self._operand_data(right_v, sel_list))

        sel = AESel(f_name, f_args, back_var=astNode.target.name)
        return sel

    def handleIdentifier(self, astNode: Identifier, sel_list: list) -> AESel:
        f_name = "return"
        f_args = [AEData(astNode.name, AEData.AE_VAR_TYPE_VAR)]
        sel = AESel(f_name, f_args)
        return sel

    def handleLiteral(self, astNode: Literal, sel_list: list) -> AESel:
        f_name = "return"
        f_args = [AEData(astNode.value, AEData.AE_VAR_TYPE_VAL)]
        sel = AESel(f_name, f_args)
        return sel

    def handleReturnStatement(self, astNode: ReturnStatement, sel_list: list) -> AESel:
        f_name = "return"
        f_args = []
        if astNode.value:
            f_args.append(self._operand_data(astNode.value, sel_list))
        sel = AESel(f_name, f_args)
        return sel

    def handleContinueStatement(self, astNode: ContinueStatement, sel_list: list) -> AESel:
        return AESel("continue", [])

    def handleBreakStatement(self, astNode: BreakStatement, sel_list: list) -> AESel:
        return AESel("break", [])

    def handleIfStatement(self, astNode: IfStatement, sel_list: list) -> AESel:
        f_name = "if"
        f_args = []
        f_args.append(AEData(self._condition_block(astNode.condition, "if-condition")))

        if astNode.body:
            body_sel_list = self.handle(astNode.body)
            body_block = AEBlock(body_sel_list, "if-body")
            body_block.type = AEBlock.BLOCK_TYPE_BODY
            f_args.append(AEData(body_block))

        if astNode.else_body:
            else_sel_list = self.handle(astNode.else_body)
            else_block = AEBlock(else_sel_list, "else-body")
            else_block.type = AEBlock.BLOCK_TYPE_BODY
            f_args.append(AEData(else_block))

        return AESel(f_name, f_args)

    def handleWhileStatement(self, astNode: WhileStatement, sel_list: list) -> AESel:
        f_name = "while"
        f_args = []
        f_args.append(AEData(self._condition_block(astNode.condition, "while-condition")))

        if astNode.body:
            body_sel_list = self.handle(astNode.body)
            body_block = AEBlock(body_sel_list, "while-body")
            body_block.type = AEBlock.BLOCK_TYPE_BODY
            f_args.append(AEData(body_block))

        return AESel(f_name, f_args)

    def handleForStatement(self, astNode: ForStatement, sel_list: list) -> AESel:
        raise TypeError(f"第{astNode.row}行：普通 for 不是支持的语法，请使用 while 或 forin")

    def handleFunctionDefinition(self, astNode: FunctionDefinition, sel_list: list) -> AESel:
        f_name = astNode.name
        f_args = None
        if astNode.parameters:
            f_args = []
            for i in astNode.parameters:
                if not isinstance(i, Parameter):
                    raise TypeError(f"定义函数参数类型错误: {i}")
                if not i.default_value:
                    iv = AEData(i.default_value)
                else:
                    iv = self._operand_data(i.default_value, sel_list, self._arg_temp_data)
                a = AEArg(i.name, iv)
                f_args.append(a)

        f_body = self.handle(astNode.body)
        f = AEBlock(f_body, f_name, f_args)
        f.type = AEBlock.BLOCK_TYPE_SEL
        sel = AESel("=def", [AEData(f_name, AEData.AE_VAR_TYPE_VAR), AEData(f)])
        return sel

    def handleTryStatement(self, astNode: TryStatement, sel_list: list) -> AESel:
        f_name = "try"
        f_args = []
        if astNode.try_block:
            body_sel_list = self.handle(astNode.try_block)
            body_block = AEBlock(body_sel_list, "try-body")
            body_block.type = AEBlock.BLOCK_TYPE_BODY
            f_args.append(AEData(body_block))
        else:
            f_args.append(AEData(None)) # 占位

        if astNode.except_clauses:
            except_bodys = []
            for e in astNode.except_clauses:
                except_sel_list = self.handle(e.body)
                except_block = AEBlock(except_sel_list, "except-body")
                except_block.type = AEBlock.BLOCK_TYPE_BODY
                if e.exception_name:
                    except_block.args = [AEArg(e.exception_name, AEData(None))]
                except_bodys.append(except_block)
            f_args.append(AEData(except_bodys))
        else:
            f_args.append(AEData(None))

        if astNode.finally_block is not None:
            finally_sel_list = self.handle(astNode.finally_block)
            finally_block = AEBlock(finally_sel_list, "finally-body")
            finally_block.type = AEBlock.BLOCK_TYPE_BODY
            f_args.append(AEData(finally_block))

        return AESel(f_name, f_args)

    def handleDictLiteral(self, astNode: DictLiteral, sel_list: list) -> AESel:
        f_name = "{}"
        f_args = []
        for k in astNode.elements.keys():
            v = astNode.elements[k]
            if isinstance(k, Literal):
                self.format_literal_value(k)
                k_name = k.value
            else:
                raise TypeError(f"字典key声明，只支持字面量!: {k}")
            aev = self._operand_data(v, sel_list)
            f_args.append(AEData(AEArg(k_name, aev)))
        return AESel(f_name, f_args)

    def _collection_args(self, elements, sel_list):
        args = []
        for value in elements:
            if not isinstance(value, (Literal, Identifier)) and value == None:
                continue
            args.append(self._operand_data(value, sel_list))
        return args

    def handleListLiteral(self, astNode: ListLiteral, sel_list: list) -> AESel:
        return AESel("[]", self._collection_args(astNode.elements, sel_list))

    def handleTupleLiteral(self, astNode: TupleLiteral, sel_list: list) -> AESel:
        return AESel("()", self._collection_args(astNode.elements, sel_list))

    def handleSetLiteral(self, astNode: SetLiteral, sel_list: list) -> AESel:
        return AESel("{set}", self._collection_args(astNode.elements, sel_list))

    def handleSubscript(self, astNode: Subscript, sel_list: list) -> AESel:
        f_name = "[ik]"  # index or key
        f_args = []
        ast_list = [astNode.array, astNode.index]
        for v in ast_list:
            aev = self._operand_data(v, sel_list)
            f_args.append(aev)
        return AESel(f_name, f_args)

    def format_literal_value(self, literal: Literal):
        if literal.value == "null":
            literal.value = None
        elif literal.value == "true":
            literal.value = True
        elif literal.value == "false":
            literal.value = False

    def routeASTNodeHandleFunction(self, astNode):
        if isinstance(astNode, FunctionCall):
            return self.handleFunctionCall
        elif isinstance(astNode, Assignment):
            return self.handleAssignment
        elif isinstance(astNode, BinaryOp):
            return self.handleBinaryOp
        elif isinstance(astNode, TernaryOp):
            return self.handleTernaryOp
        elif isinstance(astNode, FunctionDefinition):
            return self.handleFunctionDefinition
        elif isinstance(astNode, ReturnStatement):
            return self.handleReturnStatement
        elif isinstance(astNode, IfStatement):
            return self.handleIfStatement
        elif isinstance(astNode, WhileStatement):
            return self.handleWhileStatement
        elif isinstance(astNode, ForStatement):
            return self.handleForStatement
        elif isinstance(astNode, ContinueStatement):
            return self.handleContinueStatement
        elif isinstance(astNode, BreakStatement):
            return self.handleBreakStatement
        elif isinstance(astNode, ListLiteral):
            return self.handleListLiteral
        elif isinstance(astNode, DictLiteral):
            return self.handleDictLiteral
        elif isinstance(astNode, Subscript):
            return self.handleSubscript
        elif isinstance(astNode, MemberAccess):
            return self.handleMemberAccess
        elif isinstance(astNode, UnaryOp):
            return self.handleUnaryOp
        elif isinstance(astNode, TryStatement):
            return self.handleTryStatement
        elif isinstance(astNode, CompoundAssignment):
            return self.handleCompoundAssignment
        elif isinstance(astNode, Identifier):
            return self.handleIdentifier
        elif isinstance(astNode, Literal):
            return self.handleLiteral
        elif isinstance(astNode, TupleLiteral):
            return self.handleTupleLiteral
        elif isinstance(astNode, SetLiteral):
            return self.handleSetLiteral
        else:
            raise TypeError(f"暂未处理的类型:{astNode}")

    def handle(self, ast_list: List[ASTNode], file_path=None) -> list[AESel]:
        all_sels: list[AESel] = []
        for row in ast_list:
            row_sels: list[AESel] = []
            astHandleFunc = self.routeASTNodeHandleFunction(row)
            sel: AESel = astHandleFunc(row, row_sels)
            row_sels.append(sel)
            for v in row_sels:
                v.which_line = row.row
            all_sels.extend(row_sels)
        if file_path:

            def add_file_path(sel_list):
                for v in sel_list:
                    v.file_path = file_path

                    for a in v.args if v.args else []:
                        if isinstance(a, AEData) and isinstance(a.var, AEBlock):
                            add_file_path(a.var.sel_list)
            add_file_path(all_sels)
        return all_sels


