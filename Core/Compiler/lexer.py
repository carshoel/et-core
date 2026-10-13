import enum
from typing import List, Optional, Any


# 词法单元类型
class TokenType(enum.Enum):
    # 标识符和字面量
    IDENTIFIER = "IDENTIFIER"
    STRING = "STRING"
    NUMBER = "NUMBER"

    # 关键字
    IF = "IF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"
    RETURN = "RETURN"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NULL = "NULL"
    BREAK = "BREAK"
    CONTINUE = "CONTINUE"
    TRY = "TRY"
    EXCEPT = "EXCEPT"
    FINALLY = "FINALLY"

    # 运算符
    ASSIGN = "ASSIGN"  # =
    PLUS = "PLUS"  # +
    MINUS = "MINUS"  # -
    MULTIPLY = "MULTIPLY"  # *
    DIVIDE = "DIVIDE"  # /
    MODULO = "MODULO"  # %
    DOT = "DOT"  # .
    POWER = "POWER"  # **
    INCREMENT = "INCREMENT"  # ++
    DECREMENT = "DECREMENT"  # --
    LSHIFT = "LSHIFT"  # <<
    RSHIFT = "RSHIFT"  # >>
    BITAND = "BITAND"  # &
    BITOR = "BITOR"  # |
    BITXOR = "BITXOR"  # ^
    BITNOT = "BITNOT"  # ~
    QUESTION = "QUESTION"  # ?

    # 复合赋值运算符
    PLUS_ASSIGN = "PLUS_ASSIGN"  # +=
    MINUS_ASSIGN = "MINUS_ASSIGN"  # -=
    MULTIPLY_ASSIGN = "MULTIPLY_ASSIGN"  # *=
    DIVIDE_ASSIGN = "DIVIDE_ASSIGN"  # /=
    MODULO_ASSIGN = "MODULO_ASSIGN"  # %=
    POWER_ASSIGN = "POWER_ASSIGN"  # **=
    LSHIFT_ASSIGN = "LSHIFT_ASSIGN"  # <<=
    RSHIFT_ASSIGN = "RSHIFT_ASSIGN"  # >>=
    BITAND_ASSIGN = "BITAND_ASSIGN"  # &=
    BITOR_ASSIGN = "BITOR_ASSIGN"  # |=
    BITXOR_ASSIGN = "BITXOR_ASSIGN"  # ^=

    # 比较运算符
    EQ = "EQ"  # ==
    NEQ = "NEQ"  # !=
    LT = "LT"  # <
    GT = "GT"  # >
    LTE = "LTE"  # <=
    GTE = "GTE"  # >=

    # 逻辑运算符
    AND = "AND"  # &&
    OR = "OR"  # ||
    NOT = "NOT"  # !

    # 标点符号
    LPAREN = "LPAREN"  # (
    RPAREN = "RPAREN"  # )
    LBRACE = "LBRACE"  # {
    RBRACE = "RBRACE"  # }
    LBRACKET = "LBRACKET"  # [
    RBRACKET = "RBRACKET"  # ]
    COMMA = "COMMA"  # ,
    COLON = "COLON"  # :
    SEMICOLON = "SEMICOLON"  # ;

    # 特殊
    COMMENT = "COMMENT"
    EOF = "EOF"


# 词法单元类
class Token:
    def __init__(self, type: TokenType, value: str, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type}, '{self.value}', line={self.line}, col={self.column})"


# 词法分析器
class Lexer:
    def __init__(self, source_code: str, log):
        self.log = log
        self.source_code = source_code
        self.position = 0
        self.line = 1
        self.column = 1
        self.tokens = []

        # 关键字映射
        self.keywords = {
            'if': TokenType.IF,
            'else': TokenType.ELSE,
            'while': TokenType.WHILE,
            'for': TokenType.FOR,
            'return': TokenType.RETURN,
            'true': TokenType.TRUE,
            'false': TokenType.FALSE,
            'null': TokenType.NULL,
            'break': TokenType.BREAK,
            'continue': TokenType.CONTINUE,
            'try': TokenType.TRY,
            'except': TokenType.EXCEPT,
            'catch': TokenType.EXCEPT,
            'finally': TokenType.FINALLY
        }

    def tokenize(self) -> List[Token]:
        while self.position < len(self.source_code):
            char = self.source_code[self.position]

            # 跳过空白字符
            if char in ' \t\r':
                self.advance()
                continue

            # 换行处理
            if char == '\n':
                self.line += 1
                self.column = 1
                self.position += 1  # 直接增加position，不调用advance()
                continue

            # 注释处理 - 直接跳过，不生成token
            if char == '/' and self.peek() == '/':
                self.handle_comment()
                continue

            # 字符串处理
            if char == '"':
                self.handle_string()
                continue

            # 标识符和关键字
            if char.isalpha() or char == '_':
                self.handle_identifier()
                continue

            # 数字处理
            if char.isdigit():
                self.handle_number()
                continue

            # 符号处理
            if self.handle_operators_and_punctuation():
                continue

            raise SyntaxError(f"第{self.line}行第{self.column}列：无法识别的字符 {char!r}")

        self.add_token(TokenType.EOF, '')
        self.print_tokens(self.tokens)
        return self.tokens

    def handle_operators_and_punctuation(self) -> bool:
        char = self.source_code[self.position]
        two_chars = self.source_code[self.position:self.position + 2]
        three_chars = self.source_code[self.position:self.position + 3]

        # 三字符运算符
        if three_chars == '**=':
            self.add_token(TokenType.POWER_ASSIGN, '**=')
            self.advance(3)
            return True
        elif three_chars == '<<=':
            self.add_token(TokenType.LSHIFT_ASSIGN, '<<=')
            self.advance(3)
            return True
        elif three_chars == '>>=':
            self.add_token(TokenType.RSHIFT_ASSIGN, '>>=')
            self.advance(3)
            return True

        # 双字符运算符
        if two_chars == '**':
            self.add_token(TokenType.POWER, '**')
            self.advance(2)
            return True
        elif two_chars == '++':
            self.add_token(TokenType.INCREMENT, '++')
            self.advance(2)
            return True
        elif two_chars == '--':
            self.add_token(TokenType.DECREMENT, '--')
            self.advance(2)
            return True
        elif two_chars == '<<':
            self.add_token(TokenType.LSHIFT, '<<')
            self.advance(2)
            return True
        elif two_chars == '>>':
            self.add_token(TokenType.RSHIFT, '>>')
            self.advance(2)
            return True
        elif two_chars == '+=':
            self.add_token(TokenType.PLUS_ASSIGN, '+=')
            self.advance(2)
            return True
        elif two_chars == '-=':
            self.add_token(TokenType.MINUS_ASSIGN, '-=')
            self.advance(2)
            return True
        elif two_chars == '*=':
            self.add_token(TokenType.MULTIPLY_ASSIGN, '*=')
            self.advance(2)
            return True
        elif two_chars == '/=':
            self.add_token(TokenType.DIVIDE_ASSIGN, '/=')
            self.advance(2)
            return True
        elif two_chars == '%=':
            self.add_token(TokenType.MODULO_ASSIGN, '%=')
            self.advance(2)
            return True
        elif two_chars == '==':
            self.add_token(TokenType.EQ, '==')
            self.advance(2)
            return True
        elif two_chars == '!=':
            self.add_token(TokenType.NEQ, '!=')
            self.advance(2)
            return True
        elif two_chars == '<=':
            self.add_token(TokenType.LTE, '<=')
            self.advance(2)
            return True
        elif two_chars == '>=':
            self.add_token(TokenType.GTE, '>=')
            self.advance(2)
            return True
        elif two_chars == '&=':
            self.add_token(TokenType.BITAND_ASSIGN, '&=')
            self.advance(2)
            return True
        elif two_chars == '|=':
            self.add_token(TokenType.BITOR_ASSIGN, '|=')
            self.advance(2)
            return True
        elif two_chars == '^=':
            self.add_token(TokenType.BITXOR_ASSIGN, '^=')
            self.advance(2)
            return True
        elif two_chars == '&&':
            self.add_token(TokenType.AND, '&&')
            self.advance(2)
            return True
        elif two_chars == '||':
            self.add_token(TokenType.OR, '||')
            self.advance(2)
            return True

        # 单字符运算符和标点
        single_char_tokens = {
            '=': TokenType.ASSIGN,
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.MULTIPLY,
            '/': TokenType.DIVIDE,
            '%': TokenType.MODULO,
            '&': TokenType.BITAND,
            '|': TokenType.BITOR,
            '^': TokenType.BITXOR,
            '~': TokenType.BITNOT,
            '<': TokenType.LT,
            '>': TokenType.GT,
            '!': TokenType.NOT,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            ',': TokenType.COMMA,
            ':': TokenType.COLON,
            ';': TokenType.SEMICOLON,
            '?': TokenType.QUESTION,
            '.': TokenType.DOT
        }

        if char in single_char_tokens:
            self.add_token(single_char_tokens[char], char)
            self.advance()
            return True

        return False

    def handle_comment(self):
        """处理单行注释，只跳过注释内容，不处理换行符"""
        # 跳过两个斜杠
        self.position += 2
        self.column += 2

        # 跳过注释内容（不包括换行符）
        while self.position < len(self.source_code) and self.source_code[self.position] != '\n':
            self.column += 1
            self.position += 1

    def handle_string(self):
        # 保存字符串开始的位置
        start_line = self.line
        start_column = self.column

        self.advance()  # 跳过开头的 "
        escaped = False
        result_chars = []

        while self.position < len(self.source_code):
            char = self.source_code[self.position]

            if escaped:
                # 处理转义字符
                if char == 'n':
                    result_chars.append('\n')
                elif char == 't':
                    result_chars.append('\t')
                elif char == 'r':
                    result_chars.append('\r')
                elif char == '"':
                    result_chars.append('"')
                elif char == '\\':
                    result_chars.append('\\')
                elif char == 'b':
                    result_chars.append('\b')
                elif char == 'f':
                    result_chars.append('\f')
                else:
                    # 未知转义序列，保持原样（包括反斜杠）
                    result_chars.append('\\')
                    result_chars.append(char)
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                break
            else:
                result_chars.append(char)

            self.advance()

        if self.position >= len(self.source_code):
            raise SyntaxError(f"第{start_line}行第{start_column}列：字符串未闭合")

        # 构建最终的字符串值
        string_value = ''.join(result_chars)
        # 使用字符串开始的位置创建token
        self.add_token_with_position(TokenType.STRING, string_value, start_line, start_column)
        self.advance()  # 跳过结尾的 "

    def handle_identifier(self):
        # 保存标识符开始的位置
        start_line = self.line
        start_column = self.column

        start = self.position
        while self.position < len(self.source_code) and (
                self.source_code[self.position].isalnum() or self.source_code[self.position] == '_'):
            self.advance()

        identifier = self.source_code[start:self.position]

        # 检查是否是关键字
        if identifier in self.keywords:
            # 使用标识符开始的位置创建token
            self.add_token_with_position(self.keywords[identifier], identifier, start_line, start_column)
        else:
            # 使用标识符开始的位置创建token
            self.add_token_with_position(TokenType.IDENTIFIER, identifier, start_line, start_column)

    def handle_number(self):
        # 保存数字开始的位置
        start_line = self.line
        start_column = self.column

        start = self.position
        while self.position < len(self.source_code) and self.source_code[self.position].isdigit():
            self.advance()

        # 检查浮点数
        if self.position < len(self.source_code) and self.source_code[self.position] == '.':
            self.advance()
            while self.position < len(self.source_code) and self.source_code[self.position].isdigit():
                self.advance()
            number = self.source_code[start:self.position]
            # 使用数字开始的位置创建token
            self.add_token_with_position(TokenType.NUMBER, float(number), start_line, start_column)
        else:
            number = self.source_code[start:self.position]
            # 使用数字开始的位置创建token
            self.add_token_with_position(TokenType.NUMBER, int(number), start_line, start_column)

    def peek(self, offset=1) -> Optional[str]:
        if self.position + offset < len(self.source_code):
            return self.source_code[self.position + offset]
        return None

    def advance(self, steps=1):
        for _ in range(steps):
            if self.position < len(self.source_code):
                if self.source_code[self.position] == '\n':
                    self.line += 1
                    self.column = 1
                else:
                    self.column += 1
                self.position += 1

    def add_token(self, token_type: TokenType, value: Any):
        """使用当前位置创建 token。"""
        token = Token(token_type, value, self.line, self.column)
        self.tokens.append(token)

    def add_token_with_position(self, token_type: TokenType, value: Any, line: int, column: int):
        """使用调用方记录的起始位置创建 token。"""
        token = Token(token_type, value, line, column)
        self.tokens.append(token)

    def print_tokens(self, tokens):
        if not self.log:
            return
        self.log("=== 词法分析结果 ===")
        for i, token in enumerate(tokens):
            self.log(f"{i}: {token}")
