import operator


class AEMathematicsSel(object):
    binary_operators = {
        "-": operator.sub, "*": operator.mul, "/": operator.truediv,
        "%": operator.mod, "**": operator.pow,
        "<<": operator.lshift, ">>": operator.rshift,
        "&": operator.and_, "|": operator.or_, "^": operator.xor,
        ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le,
    }
    base_arithmetic_op_list = ["~", "+", "-", "*", "/", "==", ">", ">=", "<", "<=", "!=", "%", "!",
                               "&&", "||", "&", "|", "^", "<<", ">>", "**"]

    @staticmethod
    def handel(l_value: object, r_value: object, operation: str):
        if operation not in AEMathematicsSel.base_arithmetic_op_list:
            raise ValueError(f"错误的或未注册的操作符:{operation}")

        if operation in ["||"]:
            return l_value or r_value
        elif operation in ["&&"]:
            return l_value and r_value
        elif operation in ["!="]:
            if l_value is None or r_value is None:
                return l_value is not r_value
            return l_value != r_value
        elif operation in ["=="]:
            if l_value is None or r_value is None:
                return l_value is r_value
            return l_value == r_value

        if operation == "+":
            if isinstance(l_value, str) or isinstance(r_value, str):
                return f"{l_value}{r_value}"
            return operator.add(l_value, r_value)

        return AEMathematicsSel.binary_operators[operation](l_value, r_value)


def get_sel_list() -> dict:
    sel_dic = {}
    for k in AEMathematicsSel.base_arithmetic_op_list:
        sel_dic[k] = lambda l, r, op=k: AEMathematicsSel.handel(l, r, op)
    sel_dic["~"] = lambda value: ~value
    return sel_dic


if __name__ == '__main__':
    x = "*"
    y = 10

    a = AEMathematicsSel()
    x = "*"
    b = a.handel(y, x, "*")
    print(b)




