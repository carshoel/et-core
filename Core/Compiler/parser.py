from Core.Compiler.lexer import TokenType
from typing import List, Optional, Dict


_BINARY_START_TOKENS = frozenset((
    TokenType.OR, TokenType.AND, TokenType.EQ, TokenType.NEQ,
    TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE,
    TokenType.BITOR, TokenType.BITXOR, TokenType.BITAND,
    TokenType.LSHIFT, TokenType.RSHIFT, TokenType.PLUS,
    TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO, TokenType.POWER,
))


def missing_expression_start_message(kind):
    if kind == TokenType.QUESTION:
        return "缺少条件"
    if kind in _BINARY_START_TOKENS:
        return "缺少操作数"
    return None


# --- AST 节点类 ---
class ASTNode:
    def __init__(self, row: int = 0):
        self.row = row


class Program(ASTNode):
    def __init__(self, statements: List[ASTNode], row: int = 0):
        super().__init__(row)
        self.statements = statements

    def __repr__(self): return f"Program(row={self.row}, {self.statements})"


class Block(ASTNode):
    def __init__(self, statements: List[ASTNode], row: int = 0):
        super().__init__(row)
        self.statements = statements

    def __repr__(self): return f"Block(row={self.row}, {self.statements})"


class Expression(ASTNode): pass


class TernaryOp(Expression):
    def __init__(self, condition: Expression, true_expr: Expression, false_expr: Expression, row: int = 0):
        super().__init__(row)
        self.condition = condition
        self.true_expr = true_expr
        self.false_expr = false_expr

    def __repr__(self):
        return f"TernaryOp(row={self.row}, {self.condition} ? {self.true_expr} : {self.false_expr})"


class BinaryOp(Expression):
    def __init__(self, left: Expression, operator: str, right: Expression, row: int = 0):
        super().__init__(row)
        self.left = left
        self.operator = operator
        self.right = right

    def __repr__(self): return f"BinaryOp(row={self.row}, {self.left}, '{self.operator}', {self.right})"


class UnaryOp(Expression):
    def __init__(self, operator: str, operand: Expression, is_postfix: bool = False, row: int = 0):
        super().__init__(row)
        self.operator = operator
        self.operand = operand
        self.is_postfix = is_postfix

    def __repr__(self):
        return f"UnaryOp(row={self.row}, '{self.operator}', {self.operand}{', postfix=True' if self.is_postfix else ''})"


class Assignment(ASTNode):
    def __init__(self, target: Expression, value: Expression, row: int = 0):
        super().__init__(row)
        self.target = target
        self.value = value

    def __repr__(self): return f"Assignment(row={self.row}, {self.target}, {self.value})"


class CompoundAssignment(ASTNode):
    def __init__(self, target: Expression, operator: str, value: Expression, row: int = 0):
        super().__init__(row)
        self.target = target
        self.operator = operator
        self.value = value

    def __repr__(self): return f"CompoundAssignment(row={self.row}, {self.target}, '{self.operator}=', {self.value})"


class Parameter(ASTNode):
    def __init__(self, name: str, default_value: Optional[Expression] = None, row: int = 0):
        super().__init__(row)
        self.name = name
        self.default_value = default_value

    def __repr__(
            self): return f"Parameter(row={self.row}, {self.name}{f', default={self.default_value}' if self.default_value else ''})"


class FunctionDefinition(ASTNode):
    def __init__(self, name: str, parameters: List[Parameter], body: List[ASTNode], row: int = 0):
        super().__init__(row)
        self.name = name
        self.parameters = parameters
        self.body = body

    def __repr__(self): return f"FunctionDefinition(row={self.row}, {self.name}, {self.parameters}, {self.body})"


class FunctionCall(Expression):
    def __init__(self, func: Expression, arguments: List[Expression], row: int = 0):
        super().__init__(row)
        self.func = func
        self.arguments = arguments

    def __repr__(self): return f"FunctionCall(row={self.row}, {self.func}, {self.arguments})"


class MemberAccess(Expression):
    def __init__(self, object: Expression, member: str, row: int = 0):
        super().__init__(row)
        self.object = object
        self.member = member

    def __repr__(self): return f"MemberAccess(row={self.row}, {self.object}, '{self.member}')"


class IfStatement(ASTNode):
    def __init__(self, condition: Expression, body: List[ASTNode], else_body: Optional[List[ASTNode]] = None,
                 row: int = 0):
        super().__init__(row)
        self.condition = condition
        self.body = body
        self.else_body = else_body

    def __repr__(self): return f"IfStatement(row={self.row}, {self.condition}, {self.body}, else={self.else_body})"


class WhileStatement(ASTNode):
    def __init__(self, condition: Expression, body: List[ASTNode], row: int = 0):
        super().__init__(row)
        self.condition = condition
        self.body = body

    def __repr__(self): return f"WhileStatement(row={self.row}, {self.condition}, {self.body})"


class ForStatement(ASTNode):
    def __init__(self, init: Optional[ASTNode], condition: Optional[Expression], update: Optional[Expression],
                 body: List[ASTNode], row: int = 0):
        super().__init__(row)
        self.init = init
        self.condition = condition
        self.update = update
        self.body = body

    def __repr__(
            self): return f"ForStatement(row={self.row}, {self.init}, {self.condition}, {self.update}, {self.body})"


class ReturnStatement(ASTNode):
    def __init__(self, value: Optional[Expression] = None, row: int = 0):
        super().__init__(row)
        self.value = value

    def __repr__(self): return f"ReturnStatement(row={self.row}, {self.value})"


class BreakStatement(ASTNode):
    def __init__(self, row: int = 0): super().__init__(row)

    def __repr__(self): return f"BreakStatement(row={self.row})"


class ContinueStatement(ASTNode):
    def __init__(self, row: int = 0): super().__init__(row)

    def __repr__(self): return f"ContinueStatement(row={self.row})"


class TryStatement(ASTNode):
    def __init__(self, try_block: List[ASTNode], except_clauses: List['ExceptClause'], finally_block: Optional[List[ASTNode]] = None, row: int = 0):
        super().__init__(row)
        self.try_block = try_block
        self.except_clauses = except_clauses
        self.finally_block = finally_block

    def __repr__(self):
        return f"TryStatement(row={self.row}, try={self.try_block}, except={self.except_clauses}, finally={self.finally_block})"


class ExceptClause(ASTNode):
    def __init__(self, exception_name: Optional[str] = None, body: List[ASTNode] = None, row: int = 0):
        super().__init__(row)
        self.exception_name = exception_name
        self.body = body or []

    def __repr__(self): return f"ExceptClause(row={self.row}, {self.exception_name}, {self.body})"


class ListLiteral(Expression):
    def __init__(self, elements: List[Expression], row: int = 0):
        super().__init__(row)
        self.elements = elements

    def __repr__(self): return f"ListLiteral(row={self.row}, {self.elements})"


class TupleLiteral(Expression):
    def __init__(self, elements: List[Expression], row: int = 0):
        super().__init__(row)
        self.elements = elements

    def __repr__(self): return f"TupleLiteral(row={self.row}, {self.elements})"


class DictLiteral(Expression):
    def __init__(self, elements: Dict[Expression, Expression], row: int = 0):
        super().__init__(row)
        self.elements = elements

    def __repr__(self): return f"DictLiteral(row={self.row}, {self.elements})"


class SetLiteral(Expression):
    def __init__(self, elements: List[Expression], row: int = 0):
        super().__init__(row)
        self.elements = elements

    def __repr__(self): return f"SetLiteral(row={self.row}, {self.elements})"


class Subscript(Expression):
    def __init__(self, array: Expression, index: Expression, row: int = 0):
        super().__init__(row)
        self.array = array
        self.index = index

    def __repr__(self): return f"Subscript(row={self.row}, {self.array}, {self.index})"


class Literal(Expression):
    def __init__(self, value, row: int = 0):
        super().__init__(row)
        self.value = value

    def __repr__(self): return f"Literal(row={self.row}, {self.value})"


class Identifier(Expression):
    def __init__(self, name: str, row: int = 0):
        super().__init__(row)
        self.name = name

    def __repr__(self): return f"Identifier(row={self.row}, {self.name})"
