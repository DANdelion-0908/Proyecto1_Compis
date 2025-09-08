from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

class Visitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = {}

    def visitVariableDeclaration(self, ctx:CompiscriptParser.VariableDeclarationContext):
        var_name = ctx.Identifier().getText()

        if var_name in self.symbol_table:
            raise Exception(f"Variable '{var_name}' already declared.")
        
        else:
            self.symbol_table[var_name] = "unknown"

        return self.visitChildren(ctx)

    def visitAssignment(self, ctx:CompiscriptParser.AssignmentContext):
        var_name = ctx.Identifier().getText()

        if var_name not in self.symbol_table:
            raise Exception(f"Variable '{var_name}' not declared.")
        
        return self.visitChildren(ctx)

    def visitExpressionStatement(self, ctx:CompiscriptParser.ExpressionStatementContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            operator = ctx.getChild(1).getText()
            right = self.visit(ctx.getChild(2))

            if operator in ['+', '-', '*', '/']:
                if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                    if operator == '+':
                        return left + right
                    elif operator == '-':
                        return left - right
                    elif operator == '*':
                        return left * right
                    elif operator == '/':
                        if right != 0:
                            return left / right
                        else:
                            raise Exception("Division by zero.")
                else:
                    raise Exception("Type error: Operands must be numbers.")
            else:
                raise Exception(f"Unknown operator '{operator}'.")

    def visitAdditiveExpr(self, ctx:CompiscriptParser.AdditiveExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            operator = ctx.getChild(1).getText()

            if left in ['integer', 'float'] and right in ['integer', 'float']:
                return 'float' if 'float' in (left, right) else 'integer'
            
            else:
                raise Exception(f"Type error while evaluating {left} {operator} {right}")

        else:
            return self.visit(ctx.getChild(0))

    def visitLogicalAndExpr(self, ctx:CompiscriptParser.LogicalAndExprContext):
        left_type = self.visit(ctx.equalityExpr(0)) 
        for i in range(1, len(ctx.equalityExpr())):
            right_type = self.visit(ctx.equalityExpr(i))
            if left_type != "boolean":
                print(f"Error: operador lógico con tipo no booleano: {left_type}")
                return "error"
            if right_type != "boolean":
                print(f"Error: operador lógico con tipo no booleano: {right_type}")
                return "error"
            left_type = right_type
        return "boolean"


    def visitLogicalOrExpr(self, ctx:CompiscriptParser.LogicalOrExprContext):
        left_type = self.visit(ctx.equalityExpr(0))
        for i in range(1, len(ctx.equalityExpr())):
            right_type = self.visit(ctx.equalityExpr(i))
            if left_type != "boolean":
                print(f"Error: operador lógico con tipo no booleano: {left_type}")
                return "error"
            if right_type != "boolean":
                print(f"Error: operador lógico con tipo no booleano: {right_type}")
                return "error"
            left_type = right_type
        return "boolean"
    