from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

class Visitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table_stack = [{}]
        self.error_list = []

    # ************************
    # *** Variable Methods ***
    # ************************

    def visitIdentifierExpr(self, ctx:CompiscriptParser.IdentifierExprContext):
        var_name = ctx.Identifier().getText()
        var_info = self.resolve_symbol(ctx, var_name)  # 🔹 usar resolve_symbol
        return var_info["type"]

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
            self.report_error(ctx, f"Unknown literal: {text}")

    def visitVariableDeclaration(self, ctx:CompiscriptParser.VariableDeclarationContext):
        var_name = ctx.Identifier().getText()

        declared_type = None
        if ctx.typeAnnotation():
            declared_type = ctx.typeAnnotation().getText().replace(":", "").strip()

        if ctx.initializer():
            init_type = self.visit(ctx.initializer().expression())
            if declared_type and declared_type != init_type:
                self.report_error(ctx, f"Type error: variable '{var_name}' declared as {declared_type} but initialized with {init_type}")
            declared_type = declared_type or init_type

        self.declare_symbol(ctx, var_name, {  # 🔹 usar declare_symbol
            "type": declared_type or "unknown",
            "const": False
        })

        return self.visitChildren(ctx)

    def visitConstantDeclaration(self, ctx:CompiscriptParser.ConstantDeclarationContext):
        const_name = ctx.Identifier().getText()
        declared_type = ctx.typeAnnotation().type_().getText() if ctx.typeAnnotation() else None

        init_type = self.visit(ctx.expression())
        if declared_type and declared_type != init_type:
            self.report_error(ctx, f"Type error: constant '{const_name}' declared as {declared_type} but initialized with {init_type}")

        self.declare_symbol(ctx, const_name, {  # 🔹 usar declare_symbol
            "type": declared_type if declared_type else init_type,
            "const": True
        })

        return self.visitChildren(ctx)

    def visitAssignment(self, ctx:CompiscriptParser.AssignmentContext):
        var_name = ctx.Identifier().getText()
        var_info = self.resolve_symbol(ctx, var_name)  # 🔹 usar resolve_symbol

        if var_info.get("const", False):
            self.report_error(ctx, f"Reassignment to constant '{var_name}' is not allowed.")

        assigned_type = self.visit(ctx.expression())
        declared_type = var_info["type"]

        if declared_type != assigned_type:
            self.report_error(ctx, f"Type error: variable '{var_name}' is {declared_type} but assigned {assigned_type}")

        return self.visitChildren(ctx)
    
    # **************************
    # *** Expression Methods ***
    # **************************

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
                self.report_error(ctx, f"Type error while evaluating {left} {operator} {right}")
        else:
            return self.visit(ctx.getChild(0))
        
    # Arithmetic methods

    def visitMultiplicativeExpr(self, ctx:CompiscriptParser.MultiplicativeExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            if left in ["integer", "float"] and right in ["integer", "float"]:
                return "float" if "float" in (left, right) else "integer"
            else:
                self.report_error(ctx, f"Type error: cannot apply {ctx.getChild(1).getText()} to {left} and {right}")
        return self.visit(ctx.getChild(0))
    
    def visitLogicalAndExpr(self, ctx:CompiscriptParser.LogicalAndExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            if left == right == "boolean":
                return "boolean"
            self.report_error(ctx, f"Type error: logical operator requires booleans, got {left} and {right}")
        return self.visit(ctx.getChild(0))

    # Logical methods

    def visitLogicalOrExpr(self, ctx:CompiscriptParser.LogicalOrExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            if left == right == "boolean":
                return "boolean"
            self.report_error(ctx, f"Type error: logical operator requires booleans, got {left} and {right}")
        return self.visit(ctx.getChild(0))

    def visitUnaryExpr(self, ctx:CompiscriptParser.UnaryExprContext):
        if ctx.getChildCount() == 2:
            operator = ctx.getChild(0).getText()
            operand = self.visit(ctx.getChild(1))
            if operator == "-" and operand in ["integer", "float"]:
                return operand
            elif operator == "!" and operand == "boolean":
                return "boolean"
            else:
                self.report_error(ctx, f"Type error: operator {operator} not valid for {operand}")
        return self.visit(ctx.getChild(0))
    
    # Comparison methods

    def visitEqualityExpr(self, ctx:CompiscriptParser.EqualityExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            operator = ctx.getChild(1).getText()
            right = self.visit(ctx.getChild(2))
    
            if operator in ["==", "!=", "===", "!=="]:
                if left == right:
                    return "boolean"
                elif left in ["integer", "float"] and right in ["integer", "float"]:
                    return "boolean"
                else:
                    self.report_error(ctx, f"Type error: cannot apply '{operator}' between {left} and {right}")
            else:
                self.report_error(ctx, f"Unknown equality operator '{operator}'")
        else:    
            return self.visit(ctx.getChild(0))

    def visitRelationalExpr(self, ctx:CompiscriptParser.RelationalExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            operator = ctx.getChild(1).getText()

            if operator in ["<", ">", "<=", ">="]:
                if left == right:
                    return "boolean"
                elif left in ["integer", "float"] and right in ["integer", "float"]:
                    return "boolean"
                else:
                    self.report_error(ctx, f"Type error: cannot compare {left} and {right} with {operator}")
            else:
                self.report_error(ctx, f"Unknown relational operator '{operator}'")

        return self.visit(ctx.getChild(0))
    
    # *********************
    # *** Scope Methods ***
    # *********************

    def current_scope(self):
        """Devuelve el scope actual (el más interno)."""
        return self.symbol_table_stack[-1]

    def enter_scope(self):
        """Entra a un nuevo scope (bloque o función)."""
        self.symbol_table_stack.append({})

    def exit_scope(self):
        """Sale del scope actual."""
        self.symbol_table_stack.pop()

    def declare_symbol(self, ctx, name, info):
        scope = self.current_scope()
        if name in scope:
            self.report_error(ctx, f"Identifier '{name}' already declared in this scope.")
        scope[name] = info


    def resolve_symbol(self, ctx, name):
        """Busca un símbolo recorriendo scopes de adentro hacia afuera."""
        for scope in reversed(self.symbol_table_stack):
            if name in scope:
                return scope[name]
        self.report_error(ctx, f"Variable '{name}' not declared.")

    # **************************
    # *** Errors Methods ***
    # **************************

    def visitProgram(self, ctx:CompiscriptParser.ProgramContext):
        self.visitChildren(ctx)
        if self.error_list:
            for error in self.error_list:
                print(f"Error at line {error['Line']}: {error['Error']}")
        else:
            print("No semantic errors found.")
        return None

    def report_error(self, ctx, message):
        self.error_list.append({
            "Line": ctx.start.line,
            "Error": Exception(message)})
        