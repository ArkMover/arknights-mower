class LogicExpression:
    def __init__(self, left=None, operator=None, right=None):
        self.operator = operator
        self.left = left
        self.right = right

    def __str__(self):
        return f"({str(self.left)} {self.operator} {str(self.right)})"
