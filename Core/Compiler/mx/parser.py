"""Matrix-based ET token-to-AST frontend; IR remains CodeGenerator's responsibility."""
from Core.Compiler.lexer import TokenType as T
from Core.Compiler.parser import (
    Program, Block, TernaryOp, BinaryOp, UnaryOp, Assignment, CompoundAssignment,
    Parameter, FunctionDefinition, FunctionCall, MemberAccess, IfStatement,
    WhileStatement, ForStatement, ReturnStatement, BreakStatement, ContinueStatement,
    TryStatement, ExceptClause, ListLiteral, TupleLiteral, DictLiteral, SetLiteral,
    Subscript, Literal, Identifier, missing_expression_start_message,
)

# One integer row per token: kind, interned value, line, column, nesting depth, mate.
KIND, VALUE, LINE, COLUMN, DEPTH, MATE = range(6)
TOKEN_TYPES = tuple(T)
TYPE_IDS = {kind: i for i, kind in enumerate(TOKEN_TYPES)}
OPEN = {T.LPAREN: T.RPAREN, T.LBRACKET: T.RBRACKET, T.LBRACE: T.RBRACE}
CLOSE = {v: k for k, v in OPEN.items()}
COMPOUND = {
    T.PLUS_ASSIGN: '+', T.MINUS_ASSIGN: '-', T.MULTIPLY_ASSIGN: '*',
    T.DIVIDE_ASSIGN: '/', T.MODULO_ASSIGN: '%', T.POWER_ASSIGN: '**',
    T.LSHIFT_ASSIGN: '<<', T.RSHIFT_ASSIGN: '>>',
    T.BITAND_ASSIGN: '&', T.BITOR_ASSIGN: '|', T.BITXOR_ASSIGN: '^',
}
# Larger binding power binds tighter. Equal power reduces left first, except assignment.
LEVELS = (
    (T.OR,), (T.AND,), (T.EQ, T.NEQ), (T.LT, T.GT, T.LTE, T.GTE),
    (T.BITOR,), (T.BITXOR,), (T.BITAND,),
    (T.LSHIFT, T.RSHIFT), (T.PLUS, T.MINUS),
    (T.MULTIPLY, T.DIVIDE, T.MODULO), (T.POWER,),
)
# Operator matrix columns are (left binding power, right binding power).
# The numeric relation right > left reduces left-associatively; equality is
# right-associative (assignment and the false arm of ?:).
OPERATOR_MATRIX = {kind: (i + 3, i + 4)
                   for i, group in enumerate(LEVELS) for kind in group}
OPERATOR_MATRIX.update({kind: (1, 1) for kind in (T.ASSIGN, *COMPOUND)})
OPERATOR_MATRIX[T.QUESTION] = (2, 2)
ASSIGN_POWER = 1
TERNARY_POWER = 2
UNARY_POWER = OPERATOR_MATRIX[T.POWER][1]
POSTFIX_POWER = UNARY_POWER + 1
# Keyword-to-structure rule table; block/definition ambiguity uses MATE below.
STATEMENT_RULES = {
    T.IF: "if", T.WHILE: "while", T.FOR: "for", T.RETURN: "return",
    T.BREAK: "break", T.CONTINUE: "continue", T.TRY: "try",
}


class FeatureMatrix:
    """Numeric features and bracket pairing computed once, without altering Tokens."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.values = []
        self.rows = []
        value_ids = {}
        stack = []
        for index, token in enumerate(tokens):
            # Values can be int, float or str: preserve their distinct types in the table.
            key = (type(token.value), token.value)
            if key not in value_ids:
                value_ids[key] = len(self.values)
                self.values.append(token.value)
            value_id = value_ids[key]
            depth = len(stack)
            self.rows.append([TYPE_IDS[token.type], value_id,
                              token.line, token.column, depth, -1])
            if token.type in OPEN:
                stack.append(index)
            elif token.type in CLOSE and stack and tokens[stack[-1]].type == CLOSE[token.type]:
                start = stack.pop()
                self.rows[start][MATE] = index
                self.rows[index][MATE] = start


class MatrixParser:
    """Statement rules dispatch on feature rows; expressions reduce by binding matrix."""

    def __init__(self, tokens):
        self.matrix = FeatureMatrix(tokens)
        self.tokens = tokens
        self.pos = 0

    def token(self):
        return self.tokens[self.pos]

    def kind(self):
        return TOKEN_TYPES[self.matrix.rows[self.pos][KIND]]

    def at(self, *kinds):
        return self.kind() in kinds and self.kind() != T.EOF

    def take(self, *kinds):
        if self.at(*kinds):
            token = self.token()
            self.pos += 1
            return token
        return None

    def expect(self, kind, message):
        token = self.take(kind)
        if token is None:
            self.error(message)
        return token

    def error(self, message):
        token = self.token()
        raise SyntaxError(f"错误行：{token.line}\n详情：列{token.column}, {message}")

    def required_operand(self, operand):
        if operand is None:
            self.error("缺少操作数")
        return operand

    def line_end(self):
        if self.take(T.SEMICOLON) or self.at(T.RBRACE) or self.kind() == T.EOF:
            return
        # Adjacent statements need no semicolon, including on the same line.

    def parse(self):
        first = self.token().line if self.kind() != T.EOF else 0
        statements = []
        while self.kind() != T.EOF:
            before = self.pos
            statement = self.statement()
            if statement is not None:
                statements.append(statement)
            if self.pos == before:
                self.error(f"无法识别的语句: '{self.token().value}'")
        return Program(statements, row=first)

    def block(self):
        statements = []
        while not self.at(T.RBRACE) and self.kind() != T.EOF:
            before = self.pos
            statement = self.statement()
            if statement is not None:
                statements.append(statement)
            if before == self.pos:
                self.error(f"无法识别的语句: '{self.token().value}'")
        self.expect(T.RBRACE, "期待 '}'")
        return statements

    def brace_is_literal(self):
        start = self.pos
        end = self.matrix.rows[start][MATE]
        if end == start + 1:
            return True
        if end < 0:
            end = len(self.tokens)
        for i in range(start + 1, end):
            row = self.matrix.rows[i]
            if row[DEPTH] == self.matrix.rows[start][DEPTH] + 1:
                if self.tokens[i].type in (T.COLON, T.COMMA):
                    return True
                if self.tokens[i].type == T.SEMICOLON:
                    return False
        # Probe one complete brace literal without consuming statement tokens.
        saved = self.pos
        try:
            literal = self.primary()
            consumed = self.pos
        except (SyntaxError, RecursionError):
            return False
        finally:
            self.pos = saved
        return (consumed == end + 1 and isinstance(literal, SetLiteral)
                and len(literal.elements) == 1
                and not isinstance(literal.elements[0], (Assignment, CompoundAssignment)))

    def is_function(self):
        if not self.at(T.IDENTIFIER) or self.pos + 1 >= len(self.tokens):
            return False
        if self.tokens[self.pos + 1].type != T.LPAREN:
            return False
        mate = self.matrix.rows[self.pos + 1][MATE]
        return mate >= 0 and mate + 1 < len(self.tokens) and self.tokens[mate + 1].type == T.LBRACE

    def statement(self):
        token = self.token()
        kind = self.kind()
        rule = STATEMENT_RULES.get(kind)
        if rule == "if":
            self.take(kind)
            return self.conditional(token.line)
        if rule == "while":
            self.take(kind)
            self.expect(T.LPAREN, "期待 '('")
            cond = self.expression()
            self.expect(T.RPAREN, "期待 ')'")
            self.expect(T.LBRACE, "期待 '{'")
            return WhileStatement(cond, self.block(), row=token.line)
        if rule == "for":
            self.take(kind)
            self.expect(T.LPAREN, "期待 '('")
            init = self.statement() if not self.at(T.SEMICOLON) else self.take(T.SEMICOLON)
            cond = self.expression() if not self.at(T.SEMICOLON) else None
            self.expect(T.SEMICOLON, "期待 ';'")
            update = self.expression() if not self.at(T.RPAREN) else None
            self.expect(T.RPAREN, "期待 ')'")
            self.expect(T.LBRACE, "期待 '{'")
            return ForStatement(init, cond, update, self.block(), row=token.line)
        if rule == "return":
            self.take(kind)
            previous = self.tokens[self.pos - 1]
            end = self.at(T.SEMICOLON, T.RBRACE) or self.kind() == T.EOF or self.token().line > previous.line
            value = None if end else self.expression()
            self.line_end()
            return ReturnStatement(value, row=token.line)
        if rule in ("break", "continue"):
            self.take(kind)
            self.line_end()
            return (BreakStatement if rule == "break" else ContinueStatement)(row=token.line)
        if rule == "try":
            self.take(kind)
            return self.try_statement(token.line)
        if kind == T.LBRACE and not self.brace_is_literal():
            self.take(kind)
            return Block(self.block(), row=token.line)
        if self.is_function():
            return self.function()
        expression = self.expression()
        if expression is not None:
            self.line_end()
            return expression
        if self.take(T.SEMICOLON):
            return None
        self.error(f"无法识别的语句: '{self.token().value}'")

    def conditional(self, row):
        self.expect(T.LPAREN, "期待 '('")
        cond = self.expression()
        self.expect(T.RPAREN, "期待 ')'")
        self.expect(T.LBRACE, "期待 '{'")
        body = self.block()
        else_body = None
        if self.take(T.ELSE):
            next_if = self.take(T.IF)
            if next_if:
                else_body = [self.conditional(next_if.line)]
            else:
                self.expect(T.LBRACE, "期待 '{'")
                else_body = self.block()
        return IfStatement(cond, body, else_body, row=row)

    def try_statement(self, row):
        self.expect(T.LBRACE, "期待 '{'")
        body = self.block()
        clauses = []
        exception = self.take(T.EXCEPT)
        if exception:
            name = None
            if self.take(T.LPAREN):
                name = self.expect(T.IDENTIFIER, "期待异常变量名").value
                self.expect(T.RPAREN, "期待 ')'")
            self.expect(T.LBRACE, "期待 '{'")
            clauses.append(ExceptClause(name, self.block(), row=exception.line))
        final = None
        if self.take(T.FINALLY):
            self.expect(T.LBRACE, "期待 '{'")
            final = self.block()
        if not clauses and final is None:
            self.error("try 语句必须包含 except 或 finally 块")
        return TryStatement(body, clauses, final, row=row)

    def function(self):
        name = self.take(T.IDENTIFIER)
        self.expect(T.LPAREN, "期待 '('")
        parameters = []
        if not self.at(T.RPAREN):
            while True:
                token = self.expect(T.IDENTIFIER, "期待参数名")
                default = self.expression() if self.take(T.ASSIGN) else None
                parameters.append(Parameter(token.value, default, row=token.line))
                if not self.take(T.COMMA):
                    break
        self.expect(T.RPAREN, "期待 ')'")
        self.expect(T.LBRACE, "期待 '{'")
        return FunctionDefinition(name.value, parameters, self.block(), row=name.line)

    def expression(self, minimum=ASSIGN_POWER, operand_context=False):
        """Parse expressions using the operator binding-power matrix."""
        token = self.token()
        message = missing_expression_start_message(self.kind())
        if message:
            self.error("缺少操作数" if operand_context and self.kind() == T.QUESTION else message)
        if self.at(T.INCREMENT, T.DECREMENT, T.NOT, T.MINUS, T.BITNOT):
            self.take(self.kind())
            operand = self.expression(UNARY_POWER, operand_context=True)
            if operand is None:
                self.error("缺少操作数")
            if token.type in (T.INCREMENT, T.DECREMENT) and not self.lvalue(operand):
                self.error(f"前置运算符 '{token.value}' 需要左值")
            left = UnaryOp(token.value, operand, row=token.line)
        else:
            left = self.primary()
        if left is None:
            return None
        postfix_done = False
        while True:
            kind = self.kind()
            if not postfix_done and POSTFIX_POWER >= minimum and kind in (T.LPAREN, T.LBRACKET, T.DOT):
                if self.take(T.LPAREN):
                    args = []
                    if not self.at(T.RPAREN):
                        while True:
                            args.append(self.required_operand(self.expression()))
                            if not self.take(T.COMMA):
                                break
                    self.expect(T.RPAREN, "期待 ')'")
                    left = FunctionCall(left, args, row=left.row)
                elif self.take(T.LBRACKET):
                    index = self.required_operand(self.expression())
                    self.expect(T.RBRACKET, "期待 ']'")
                    left = Subscript(left, index, row=left.row)
                else:
                    self.take(T.DOT)
                    member = self.expect(T.IDENTIFIER, "期待成员名")
                    left = MemberAccess(left, member.value, row=left.row)
                continue
            if not postfix_done and kind in (T.INCREMENT, T.DECREMENT) and POSTFIX_POWER >= minimum:
                # Postfix binds only on the same line as its operand.
                if self.token().line == self.tokens[self.pos - 1].line:
                    op = self.take(kind)
                    if not self.lvalue(left):
                        self.error(f"后置运算符 '{op.value}' 只能用于左值")
                    left = UnaryOp(op.value, left, is_postfix=True, row=left.row)
                    postfix_done = True
                    continue  # Binary operators still bind outside the postfix expression.
                break
            if kind == T.QUESTION and TERNARY_POWER >= minimum:
                op = self.take(kind)
                yes = self.expression()
                if yes is None:
                    self.error("缺少真值")
                self.expect(T.COLON, "期待 ':'")
                no = self.expression(OPERATOR_MATRIX[T.QUESTION][1])
                if no is None:
                    self.error("缺少假值")
                left = TernaryOp(left, yes, no, row=op.line)
                continue
            left_power, right_power = OPERATOR_MATRIX.get(kind, (-1, -1))
            if left_power < minimum:
                break
            op = self.take(kind)
            if kind == T.ASSIGN or kind in COMPOUND:
                if not self.lvalue(left):
                    self.error("赋值目标必须是左值" if kind == T.ASSIGN else "复合赋值目标必须是左值")
                right = self.required_operand(self.expression(right_power))
                left = (Assignment(left, right, row=token.line) if kind == T.ASSIGN else
                        CompoundAssignment(left, COMPOUND[kind], right, row=token.line))
            else:
                right = self.required_operand(self.expression(right_power, operand_context=True))
                left = BinaryOp(left, op.value, right, row=op.line)
        return left

    @staticmethod
    def lvalue(node):
        return isinstance(node, (Identifier, MemberAccess, Subscript))

    def primary(self):
        token = self.token()
        if self.at(T.NUMBER, T.STRING, T.TRUE, T.FALSE, T.NULL):
            self.take(token.type)
            return Literal(token.value, row=token.line)
        if self.take(T.IDENTIFIER):
            return Identifier(token.value, row=token.line)
        if self.take(T.LPAREN):
            if self.take(T.RPAREN):
                return TupleLiteral([], row=token.line)
            first = self.expression()
            if self.take(T.COMMA):
                elements = [self.required_operand(first)]
                if not self.at(T.RPAREN):
                    while True:
                        elements.append(self.required_operand(self.expression()))
                        if not self.take(T.COMMA) or self.at(T.RPAREN):
                            break
                self.expect(T.RPAREN, "期待 ')'")
                return TupleLiteral(elements, row=token.line)
            self.expect(T.RPAREN, "期待 ')'")
            return first
        if self.take(T.LBRACKET):
            elements = []
            if not self.at(T.RBRACKET):
                while True:
                    if self.at(T.RBRACKET) and elements:
                        break
                    elements.append(self.required_operand(self.expression()))
                    if not self.take(T.COMMA):
                        break
            self.expect(T.RBRACKET, "期待 ']'")
            return ListLiteral(elements, row=token.line)
        if self.take(T.LBRACE):
            if self.take(T.RBRACE):
                return DictLiteral({}, row=token.line)
            first = self.expression()
            if self.take(T.COLON):
                elements = {self.required_operand(first): self.required_operand(self.expression())}
                while self.take(T.COMMA):
                    if self.at(T.RBRACE):
                        break
                    key = self.required_operand(self.expression())
                    self.expect(T.COLON, "期待 ':'")
                    elements[key] = self.required_operand(self.expression())
                self.expect(T.RBRACE, "期待 '}'")
                return DictLiteral(elements, row=token.line)
            elements = [self.required_operand(first)]
            while self.take(T.COMMA):
                if self.at(T.RBRACE):
                    break
                elements.append(self.required_operand(self.expression()))
            self.expect(T.RBRACE, "期待 '}'")
            return SetLiteral(elements, row=token.line)
        return None
