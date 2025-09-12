from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor

class Visitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = {}
        self.errors = []  # Add errors list
        self.loop_depth = 0  # Track loop depth for break/continue

    def add_error(self, message, ctx):
        line = ctx.start.line if ctx and ctx.start else "unknown"
        self.errors.append(f"Error at line {line}: {message}")

    # ************************
    # *** Variable Methods ***
    # ************************

    def visitIdentifierExpr(self, ctx:CompiscriptParser.IdentifierExprContext):
        var_name = ctx.Identifier().getText()

        if var_name not in self.symbol_table:
            self.add_error(f"Variable '{var_name}' not declared.", ctx)
            return "unknown"
        return self.symbol_table[var_name]['type']

    def visitLiteralExpr(self, ctx:CompiscriptParser.LiteralExprContext):
        text = ctx.getText()

        if ctx.arrayLiteral():
            return self.visitArrayLiteral(ctx.arrayLiteral())

        if text.isdigit():
            return "integer"
        elif text.replace('.', '', 1).isdigit() and text.count('.') < 2:
            return "float"
        elif text.startswith('"') and text.endswith('"'):
            return "string"
        elif text == "true" or text == "false":
            return "boolean"
        else:
            self.add_error(f"Unknown literal: {text}", ctx)
            return "unknown"

    def visitVariableDeclaration(self, ctx:CompiscriptParser.VariableDeclarationContext):
        var_name = ctx.Identifier().getText()

        if var_name in self.symbol_table:
            self.add_error(f"Variable '{var_name}' already declared.", ctx)
            return self.visitChildren(ctx)

        declared_type = None

        if ctx.typeAnnotation():
            declared_type = ctx.typeAnnotation().getText().replace(":", "").strip()

        if ctx.initializer():
            init_type = self.visit(ctx.initializer().expression())
            if declared_type and declared_type != init_type:
                # Caso especial: comparar arreglos
                if declared_type.endswith("[]") and init_type.endswith("[]"):
                    elem_decl = declared_type.replace("[]", "")
                    elem_init = init_type.replace("[]", "")
                    if elem_decl != elem_init:
                        self.add_error(f"Type error: variable '{var_name}' declared as {declared_type} but initialized with {init_type}", ctx)
                elif declared_type != init_type:
                    self.add_error(f"Type error: variable '{var_name}' declared as {declared_type} but initialized with {init_type}", ctx)

            declared_type = declared_type or init_type

        self.symbol_table[var_name] = {
            "type": declared_type or "unknown",
            "const": False
            }
        
        return self.visitChildren(ctx)

    def visitConstantDeclaration(self, ctx:CompiscriptParser.ConstantDeclarationContext):
        const_name = ctx.Identifier().getText()

        if const_name in self.symbol_table:
            self.add_error(f"Identifier '{const_name}' already declared.", ctx)
            return self.visitChildren(ctx)

        declared_type = ctx.typeAnnotation().type_().getText() if ctx.typeAnnotation() else None

        init_type = self.visit(ctx.expression())

        if declared_type and declared_type != init_type:
                if declared_type in ["integer", "float", "string", "boolean"]:
                    self.add_error(f"Type error: constant '{const_name}' declared as {declared_type} but initialized with a different type.", ctx)
                else:
                    self.add_error(f"Type error: type '{declared_type}' not recognized.", ctx)

        self.symbol_table[const_name] = {
            "type": declared_type if declared_type else init_type,
            "const": True
        }

        return self.visitChildren(ctx)

    def visitAssignment(self, ctx:CompiscriptParser.AssignmentContext):
        var_name = ctx.Identifier().getText()

        if var_name not in self.symbol_table:
            self.add_error(f"Variable '{var_name}' not declared.", ctx)
            return self.visitChildren(ctx)

        var_info = self.symbol_table[var_name]

        if isinstance(var_info, dict) and var_info.get("const", False):
            self.add_error(f"Reassignment to constant '{var_name}' is not allowed.", ctx)
            return self.visitChildren(ctx)

        assigned_type = self.visit(ctx.expression())
        declared_type = var_info["type"] if isinstance(var_info, dict) else var_info

        if declared_type != assigned_type:
            self.add_error(f"Type error: variable '{var_name}' is {declared_type} but assigned {assigned_type}", ctx)

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
                self.add_error(f"Type error while evaluating {left} {operator} {right}", ctx)
                return "unknown"
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
                self.add_error(f"Type error: cannot apply {ctx.getChild(1).getText()} to {left} and {right}", ctx)
                return "unknown"
        return self.visit(ctx.getChild(0))
    
    def visitLogicalAndExpr(self, ctx:CompiscriptParser.LogicalAndExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            if left == right == "boolean":
                return "boolean"
            self.add_error(f"Type error: logical operator requires booleans, got {left} and {right}", ctx)
            return "unknown"

        return self.visit(ctx.getChild(0)) or "boolean"

    # Logical methods

    def visitLogicalOrExpr(self, ctx:CompiscriptParser.LogicalOrExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            if left == right == "boolean":
                return "boolean"
            self.add_error(f"Type error: logical operator requires booleans, got {left} and {right}", ctx)
            return "unknown"
        
        return self.visit(ctx.getChild(0)) or "boolean"

    def visitUnaryExpr(self, ctx:CompiscriptParser.UnaryExprContext):
        if ctx.getChildCount() == 2:
            operator = ctx.getChild(0).getText()
            operand = self.visit(ctx.getChild(1)) or "unknown"

            if operator == "-" and operand in ["integer", "float"]:
                return operand
            elif operator == "!" and operand == "boolean":
                return "boolean"
            else:
                self.add_error(f"Type error: operator {operator} not valid for {operand}", ctx)
                return "unknown"
        return self.visit(ctx.getChild(0)) or "boolean"
    
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
                    self.add_error(f"Type error: cannot apply '{operator}' between {left} and {right}", ctx)
                    return "unknown"
            else:
                self.add_error(f"Unknown equality operator '{operator}'", ctx)
                return "unknown"
        else:    
            return self.visit(ctx.getChild(0)) or "boolean"

    def visitRelationalExpr(self, ctx:CompiscriptParser.RelationalExprContext):
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0)) or "unknown"
            right = self.visit(ctx.getChild(2)) or "unknown"
            operator = ctx.getChild(1).getText()

            if operator in ["<", ">", "<=", ">="]:
                if left in ["integer", "float"] and right in ["integer", "float"]:
                    return "boolean"
                else:
                    self.add_error(f"Type error: cannot compare {left} and {right} with {operator}", ctx)
                    return "unknown"
            else:
                self.add_error(f"Unknown relational operator '{operator}'", ctx)
                return "unknown"

        return self.visit(ctx.getChild(0)) or "boolean"
    
    # **************************
    # *** Structures Methods ***
    # **************************

    def visitArrayLiteral(self, ctx:CompiscriptParser.ArrayLiteralContext):
        if ctx.getChildCount() == 2:
            return "unknown[]"

        element_types = [self.visit(expr) for expr in ctx.expression()]

        first_type = element_types[0]
        for t in element_types[1:]:
            if t != first_type:
                self.add_error(f"Type error: inconsistent types in array literal: {first_type} vs {t}", ctx)
                return "unknown[]"

        return f"{first_type}[]"
    
    def visitIndexExpr(self, ctx:CompiscriptParser.IndexExprContext):
        base = ctx.parentCtx.getChild(0)

        array_type = self.visit(base) or "unknown"
        index_type = self.visit(ctx.expression()) or "unknown"

        if not array_type.endswith("[]"):
            self.add_error(f"Type error: trying to index non-array type '{array_type}'", ctx)
            return "unknown"

        if index_type != "integer":
            self.add_error(f"Type error: array index must be integer, got {index_type}", ctx)

        return array_type.replace("[]", "", 1)

    # **********************************
    # *** Control Structures Methods ***
    # **********************************

    def visitIfStatement(self, ctx:CompiscriptParser.IfStatementContext):
        cond_type = self.visit(ctx.expression())
        if cond_type != "boolean":
            self.add_error("Condition in 'if' must be boolean", ctx)
        self.visit(ctx.block(0))  
        if ctx.block(1):          
            self.visit(ctx.block(1))

    def visitWhileStatement(self, ctx:CompiscriptParser.WhileStatementContext):
        self.loop_depth += 1
        cond_type = self.visit(ctx.expression())
        if cond_type != "boolean":
            self.add_error("Condition in 'while' must be boolean", ctx)
        self.visit(ctx.block())
        self.loop_depth -= 1

    def visitDoWhileStatement(self, ctx:CompiscriptParser.DoWhileStatementContext):
        self.loop_depth += 1
        self.visit(ctx.block())
        cond_type = self.visit(ctx.expression())
        if cond_type != "boolean":
            self.add_error("Condition in 'do-while' must be boolean", ctx)
        self.loop_depth -= 1

    def visitForStatement(self, ctx:CompiscriptParser.ForStatementContext):
        self.loop_depth += 1
        if ctx.variableDeclaration():
            self.visit(ctx.variableDeclaration())
        elif ctx.assignment():
            self.visit(ctx.assignment())

        if ctx.expression(0):
            cond_type = self.visit(ctx.expression(0))
            if cond_type != "boolean":
                self.add_error("Condition in 'for' must be boolean", ctx)

        if ctx.expression(1):
            self.visit(ctx.expression(1))

        self.visit(ctx.block())
        self.loop_depth -= 1

    def visitForeachStatement(self, ctx:CompiscriptParser.ForeachStatementContext):
        self.loop_depth += 1
        iterable_type = self.visit(ctx.expression())
        if not iterable_type.endswith("[]"):
            self.add_error("Foreach requires an array to iterate over", ctx)
            elem_type = "unknown"
        else:
            elem_type = iterable_type.replace("[]", "", 1)

        var_name = ctx.Identifier().getText()
        self.symbol_table[var_name] = elem_type
        self.visit(ctx.block())
        del self.symbol_table[var_name]
        self.loop_depth -= 1

    def visitBreakStatement(self, ctx):
        if self.loop_depth == 0: # If we are not inside a loop
            self.add_error("'break' used outside of loop", ctx)

    def visitContinueStatement(self, ctx):
        if self.loop_depth == 0:
            self.add_error("'continue' used outside of loop", ctx)
