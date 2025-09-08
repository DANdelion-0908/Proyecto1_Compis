from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

class Visitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = {}

    def visitIdentifierExpr(self, ctx:CompiscriptParser.IdentifierExprContext):
        var_name = ctx.Identifier().getText()

        if var_name not in self.symbol_table:
            raise Exception(f"Variable '{var_name}' not declared.")

        return self.symbol_table[var_name]

    def visitLiteralExpr(self, ctx:CompiscriptParser.LiteralExprContext):
        text = ctx.getText()

        if text.isdigit():
            return "integer"
        elif text.replace('.', '', 1).isdigit() and text.count('.') < 2:
            return "float"
        elif text.startswith('"') and text.endswith('"'):
            return "string"
        elif text == "true" or text == "false":
            return "boolean"
        else:
            raise Exception(f"Unknown literal: {text}")

    def visitVariableDeclaration(self, ctx:CompiscriptParser.VariableDeclarationContext):
        var_name = ctx.Identifier().getText()

        if var_name in self.symbol_table:
            raise Exception(f"Variable '{var_name}' already declared.")

        declared_type = None
        if ctx.typeAnnotation():
            declared_type = ctx.typeAnnotation().getText().replace(":", "").strip()

        if ctx.initializer():
            init_type = self.visit(ctx.initializer().expression())
            if declared_type and declared_type != init_type:
                if declared_type in ["integer", "float", "string", "boolean"]:
                    raise Exception(f"Type error: variable '{var_name}' declared as {declared_type} but initialized with a different type.")
                else:
                    raise Exception(f"Type error: type '{declared_type}' not recognized.")
                
            declared_type = declared_type or init_type

        self.symbol_table[var_name] = declared_type or "unknown"
        return self.visitChildren(ctx)

    def visitConstantDeclaration(self, ctx:CompiscriptParser.ConstantDeclarationContext):
        const_name = ctx.Identifier().getText()

        if const_name in self.symbol_table:
            raise Exception(f"Identifier '{const_name}' already declared.")

        declared_type = ctx.typeAnnotation().type_().getText() if ctx.typeAnnotation() else None

        init_type = self.visit(ctx.expression())

        if declared_type and declared_type != init_type:
                if declared_type in ["integer", "float", "string", "boolean"]:
                    raise Exception(f"Type error: constant '{const_name}' declared as {declared_type} but initialized with a different type.")
                else:
                    raise Exception(f"Type error: type '{declared_type}' not recognized.")

        self.symbol_table[const_name] = {
            "type": declared_type if declared_type else init_type,
            "const": True
        }

        return None

    def visitAssignment(self, ctx:CompiscriptParser.AssignmentContext):
        var_name = ctx.Identifier().getText()

        if var_name not in self.symbol_table:
            raise Exception(f"Variable '{var_name}' not declared.")

        var_info = self.symbol_table[var_name]

        if isinstance(var_info, dict) and var_info.get("const", False):
            raise Exception(f"Reassignment to constant '{var_name}' is not allowed.")

        assigned_type = self.visit(ctx.expression())
        declared_type = var_info["type"] if isinstance(var_info, dict) else var_info

        if declared_type != assigned_type:
            raise Exception(f"Type error: variable '{var_name}' is {declared_type} but assigned {assigned_type}")

        return None


    def visitExpressionStatement(self, ctx:CompiscriptParser.ExpressionStatementContext):
        return self.visit(ctx.expression())

    def visitAdditiveExpr(self, ctx:CompiscriptParser.AdditiveExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            operator = ctx.getChild(1).getText()

            if left in ["integer", "float"] and right in ["integer", "float"]:
                return "float" if "float" in (left, right) else "integer"
            else:
                raise Exception(f"Type error while evaluating {left} {operator} {right}")
        else:
            return self.visit(ctx.getChild(0))
