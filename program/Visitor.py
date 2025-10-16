from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor
from CodeFragment import CodeFragment
from CodeGenerator import CodeGenerator

class Visitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = {}
        self.errors = []  # List to store semantic errors
        self.loop_depth = 0  # Track loop depth for break/continue statements
        self.function_stack = []  # Track function context for return type checking
        self.cg = CodeGenerator()  # Generation of temporal code with format t or L

    def add_error(self, message, ctx):
        # Add an error message with line information to the errors list
        line = ctx.start.line if ctx and ctx.start else "unknown"
        self.errors.append(f"Error at line {line}: {message}")

    # ************************
    # *** Variable Methods ***
    # ************************

    def visitIdentifierExpr(self, ctx:CompiscriptParser.IdentifierExprContext):
        # Handle variable identifier expressions
        var_name = ctx.Identifier().getText()

        # Check if the variable is declared
        if var_name not in self.symbol_table:
            self.add_error(f"Variable '{var_name}' not declared", ctx)
            return CodeFragment([], None, "unknown")
        
        var_type = self.symbol_table[var_name]["type"]
        
        # Return the type of the variable
        return CodeFragment([], var_name, var_type)

    def visitLiteralExpr(self, ctx:CompiscriptParser.LiteralExprContext):
        # Handle literal expressions (numbers, strings, booleans, arrays)
        text = ctx.getText()

        # Check for array literal and delegate to visitArrayLiteral
        if ctx.arrayLiteral():
            return self.visitArrayLiteral(ctx.arrayLiteral())

        # Determine the type of the literal
        if text.isdigit():
            return CodeFragment([], text, "integer")
        elif text.replace('.', '', 1).isdigit() and text.count('.') < 2:
            return CodeFragment([], text, "float")
        elif text.startswith('"') and text.endswith('"'):
            return CodeFragment([], text, "string")
        elif text in ["true", "false"]:
            return CodeFragment([], text, "boolean")
        else:
            self.add_error(f"Unknown literal: {text}", ctx)
        return CodeFragment([], None, "unknown")

    def visitVariableDeclaration(self, ctx:CompiscriptParser.VariableDeclarationContext):
        # Handle variable declarations
        var_name = ctx.Identifier().getText()

        # Check if variable already declared
        if var_name in self.symbol_table:
            self.add_error(f"Variable '{var_name}' already declared.", ctx)
            return self.visitChildren(ctx)

        declared_type = ctx.typeAnnotation().getText().replace(":", "").strip()

        # Check initializer type and compare with declared type
        if ctx.initializer():
            expression: CodeFragment = self.visit(ctx.initializer().expression())

            if declared_type and declared_type != expression.type:
                # Handle arrays specifically
                if declared_type.endswith("[]") and expression.type.endswith("[]"):
                    elem_decl = declared_type.replace("[]", "")
                    elem_init = expression.type.replace("[]", "")
                    if elem_decl != elem_init:
                        self.add_error(f"Type error: variable '{var_name}' declared as {declared_type} but initialized with {expression.type}", ctx)
                # Handle type errors
                elif declared_type != expression.type:
                    self.add_error(f"Type error: variable '{var_name}' declared as {declared_type} but initialized with {expression.type}", ctx)

            # Use initializer type if no declared type
            declared_type = declared_type or expression.type

        # Store variable in symbol table
        self.symbol_table[var_name] = {
            "type": declared_type or "unknown",
            "const": False
        }

        if expression:
            code = expression.code + [f"{var_name} = {expression.place}"]
        
        return CodeFragment(code, var_name, expression.type)

    def visitConstantDeclaration(self, ctx:CompiscriptParser.ConstantDeclarationContext):
        # Handle constant declarations
        const_name = ctx.Identifier().getText()

        if const_name in self.symbol_table:
            self.add_error(f"Identifier '{const_name}' already declared.", ctx)
            return self.visitChildren(ctx)

        declared_type = ctx.typeAnnotation().type_().getText() if ctx.typeAnnotation() else None

        init_type = self.visit(ctx.expression())

        # Check type consistency for constants
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
        # Handle assignment statements
        var_name = ctx.Identifier().getText()

        if var_name not in self.symbol_table:
            self.add_error(f"Variable '{var_name}' not declared", ctx)
            return CodeFragment([], None, "unknown")

        var_info = self.symbol_table[var_name]

        # Prevent reassignment to constants
        if var_info.get("const", False):
            self.add_error(f"Reassignment to constant '{var_name}' is not allowed.", ctx)
            return CodeFragment([], None, "unknown")

        expression: CodeFragment = self.visit(ctx.expression())

        if expression.type != var_info["type"]:
            self.add_error(f"Type mismatch: variable '{var_name}' declared as {var_info["type"]} but initialized with {expression.type}")

        code = expression.code + [f"{var_name} = {expression.place}"]
        return CodeFragment(code, var_name, expression.type)
    
    # **************************
    # *** Expression Methods ***
    # **************************

    def visitExpressionStatement(self, ctx:CompiscriptParser.ExpressionStatementContext):
        # Handle expression statements
        return self.visit(ctx.expression())

    # Arithmetic methods

    def visitAdditiveExpr(self, ctx:CompiscriptParser.AdditiveExprContext):
        # Handle additive expressions (+, -)
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            operator = ctx.getChild(1).getText()

            if isinstance(left, str):
                left = CodeFragment([], left, left)
            
            if isinstance(right, str):
                right = CodeFragment([], right, right)

            # Allow operations between integers and floats
            if left.type in ["integer", "float"] and right.type in ["integer", "float"]:
                result_type = "float" if "float" in (left.type, right.type) else "integer"
            
            else:
                self.add_error(f"Type error while evaluating {left.type} {operator} {right.type}", ctx)
                return CodeFragment([], None, "unknown")
            
            temp = self.cg.new_temp()
            code = left.code + right.code + [f"{temp} = {left.place} {operator} {right.place}"]
            return CodeFragment(code, temp, result_type)
            
        else:
            return self.visit(ctx.getChild(0))

    def visitMultiplicativeExpr(self, ctx:CompiscriptParser.MultiplicativeExprContext):
        # Handle multiplicative expressions (*, /, %)
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))
            operator = ctx.getChild(1).getText()

            if isinstance(left, str):
                left = CodeFragment([], left, left)
            
            if isinstance(right, str):
                right = CodeFragment([], right, right)

            # Allow operations between integers and floats
            if left.type in ["integer", "float"] and right.type in ["integer", "float"]:
                result_type = "float" if "float" in (left, right) else "integer"

            else:
                self.add_error(f"Type error: cannot apply {operator} to {left.type} and {right.type}", ctx)
                return CodeFragment([], None, "unknown")
            
            temp = self.cg.new_temp()
            code = left.code + right.code + [f"{temp} = {left.place} {operator} {right.place}"]
            return CodeFragment(code, temp, result_type)
        
        else:
            return self.visit(ctx.getChild(0))

    # Logical methods

    def visitLogicalAndExpr(self, ctx:CompiscriptParser.LogicalAndExprContext):
        # Handle logical AND expressions (&&)
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))

            # Check both sides are boolean
            if left == right == "boolean":
                return "boolean"
            
            self.add_error(f"Type error: logical operator requires booleans, got {left} and {right}", ctx)
            return "unknown"

        return self.visit(ctx.getChild(0)) or "boolean"

    def visitLogicalOrExpr(self, ctx:CompiscriptParser.LogicalOrExprContext):
        # Handle logical OR expressions (||)
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            right = self.visit(ctx.getChild(2))


            if left == right == "boolean":
                return "boolean"
            
            self.add_error(f"Type error: logical operator requires booleans, got {left} and {right}", ctx)
            
            return "unknown"
        
        return self.visit(ctx.getChild(0)) or "boolean"

    def visitUnaryExpr(self, ctx:CompiscriptParser.UnaryExprContext):
        # Handle unary expressions (-, !)
        if ctx.getChildCount() == 2:
            operator = ctx.getChild(0).getText()
            operand = self.visit(ctx.getChild(1)) or "unknown"

            # Allow negation for numbers
            if operator == "-" and operand in ["integer", "float"]:
                return operand
            
            # Allow ! for booleans
            elif operator == "!" and operand == "boolean":
                return "boolean"
            
            else:
                self.add_error(f"Type error: operator {operator} not valid for {operand}", ctx)
                return "unknown"
        
        return self.visit(ctx.getChild(0)) or "boolean"
    
    # Comparison methods

    def visitEqualityExpr(self, ctx:CompiscriptParser.EqualityExprContext):
        # Handle equality expressions (==, !=, ===, !==)
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0))
            operator = ctx.getChild(1).getText()
            right = self.visit(ctx.getChild(2))
    
            # Handle equality and strict equality. Based in JavaScript xd
            if operator in ["==", "!=", "===", "!=="]:
                # Allow equality between same types
                if left == right:
                    return "boolean"
                
                # Allow equality between integers and floats
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
        # Handle relational expressions (<, >, <=, >=)
        if ctx.getChildCount() == 3:
            left = self.visit(ctx.getChild(0)) or "unknown"
            right = self.visit(ctx.getChild(2)) or "unknown"
            operator = ctx.getChild(1).getText()

            # Handle relational/comparison operators
            if operator in ["<", ">", "<=", ">="]:
                # Allow comparisons between integers and floats
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
        # Handle array literal expressions
        if ctx.getChildCount() == 2:
            return "unknown[]"

        # Get types of all elements in the array
        element_types = [self.visit(expr) for expr in ctx.expression()]

        # Check for consistent element types
        first_type = element_types[0]

        # If any type is unknown, return unknown[]
        for t in element_types[1:]:
            if t != first_type:
                self.add_error(f"Type error: inconsistent types in array literal: {first_type} vs {t}", ctx)
                return "unknown[]"

        return f"{first_type}[]"
    
    def visitIndexExpr(self, ctx:CompiscriptParser.IndexExprContext):
        # Handle array indexing expressions
        base = ctx.parentCtx.getChild(0)

        array_type = self.visit(base) or "unknown"
        index_type = self.visit(ctx.expression()) or "unknown"

        # Check if base is an array
        if not array_type.endswith("[]"):
            self.add_error(f"Type error: trying to index non-array type '{array_type}'", ctx)
            return "unknown"

        # Check if index is an integer
        if index_type != "integer":
            self.add_error(f"Type error: array index must be integer, got {index_type}", ctx)

        # Return the element type of the array, removing one level of array
        return array_type.replace("[]", "", 1)

    # **********************************
    # *** Control Structures Methods ***
    # **********************************

    def visitIfStatement(self, ctx:CompiscriptParser.IfStatementContext):
        # Handle if statements
        cond_type = self.visit(ctx.expression())

        # Allow only boolean conditions
        if cond_type != "boolean":
            self.add_error("Condition in 'if' must be boolean", ctx)
        
        self.visit(ctx.block(0))  
        if ctx.block(1):          
            self.visit(ctx.block(1))

    def visitWhileStatement(self, ctx:CompiscriptParser.WhileStatementContext):
        # Handle while statements
        # Increase loop depth
        self.loop_depth += 1

        cond_type = self.visit(ctx.expression())
        
        # Allow only boolean conditions
        if cond_type != "boolean":
            self.add_error("Condition in 'while' must be boolean", ctx)
    
        self.visit(ctx.block())
        
        # Decrease loop depth
        self.loop_depth -= 1

    def visitDoWhileStatement(self, ctx:CompiscriptParser.DoWhileStatementContext):
        # Handle do-while statements
        # Increase loop depth
        self.loop_depth += 1

        self.visit(ctx.block())
        
        cond_type = self.visit(ctx.expression())
        
        # Allow only boolean conditions
        if cond_type != "boolean":
            self.add_error("Condition in 'do-while' must be boolean", ctx)
        
        # Decrease loop depth
        self.loop_depth -= 1

    def visitForStatement(self, ctx:CompiscriptParser.ForStatementContext):
        # Handle for statements
        # Increase loop depth
        self.loop_depth += 1

        # Check initializer
        if ctx.variableDeclaration():
            self.visit(ctx.variableDeclaration())

        # Check assignment
        elif ctx.assignment():
            self.visit(ctx.assignment())

        # Check condition
        if ctx.expression(0):
            cond_type = self.visit(ctx.expression(0))

            # Allow only boolean conditions
            if cond_type != "boolean":
                self.add_error("Condition in 'for' must be boolean", ctx)

        # Check increment/decrement
        if ctx.expression(1):
            self.visit(ctx.expression(1))

        self.visit(ctx.block())

        # Decrease loop depth
        self.loop_depth -= 1

    def visitForeachStatement(self, ctx:CompiscriptParser.ForeachStatementContext):
        # Handle foreach statements
        # Increase loop depth
        self.loop_depth += 1
        
        iterable_type = self.visit(ctx.expression())
        
        # Check if iterable is an array
        if not iterable_type.endswith("[]"):
            self.add_error("Foreach requires an array to iterate over", ctx)
            elem_type = "unknown"
        
        else:
            elem_type = iterable_type.replace("[]", "", 1)

        var_name = ctx.Identifier().getText()

        self.symbol_table[var_name] = elem_type
        
        self.visit(ctx.block())
        
        # Remove loop variable from symbol table
        del self.symbol_table[var_name]
        
        # Decrease loop depth
        self.loop_depth -= 1

    def visitBreakStatement(self, ctx):
        # Handle break statements
        if self.loop_depth == 0: # If we are not inside a loop
            self.add_error("'break' used outside of loop", ctx)

    def visitContinueStatement(self, ctx):
        # Handle continue statements
        if self.loop_depth == 0: # If we are not inside a loop
            self.add_error("'continue' used outside of loop", ctx)

    # *************************
    # *** Functions Methods ***
    # *************************

    def visitFunctionDeclaration(self, ctx:CompiscriptParser.FunctionDeclarationContext):
        # Handle function declarations
        func_name = ctx.Identifier().getText()
        if func_name in self.symbol_table:
            self.add_error(f"Function '{func_name}' already declared", ctx)
            return self.visitChildren(ctx)

        # Get return type
        return_type = ctx.type_().getText() if ctx.type_() else "unknown"

        # Get parameter types
        param_types = {}
        if ctx.parameters():
            for param in ctx.parameters().parameter():
                pname = param.Identifier().getText()
                ptype = param.type_().getText() if param.type_() else "unknown"

                # Check for duplicate parameter names
                if pname in param_types:
                    self.add_error(f"Parameter '{pname}' already declared in function '{func_name}'", ctx)
                
                else:
                    param_types[pname] = ptype
        
        # Check for duplicate function names
        if func_name in self.symbol_table:
            self.add_error(f"Function '{func_name}' already declared", ctx)
            return self.visitChildren(ctx)

        self.symbol_table[func_name] = {
            "type": return_type,
            "params": param_types,
            "const": True
        }

        # Create new scope for function parameters
        old_symbols = self.symbol_table.copy()
        for pname, ptype in param_types.items():
            self.symbol_table[pname] = {"type": ptype, "const": False}

        # Push function return type to stack
        self.function_stack.append(return_type)

        self.visit(ctx.block())

        # Restore previous scope and function stack
        self.symbol_table = old_symbols
        self.function_stack.pop()

    def visitReturnStatement(self, ctx:CompiscriptParser.ReturnStatementContext):
        # Handle return statements
        if not self.function_stack:
            self.add_error("'return' used outside of function", ctx)
            return "unknown"

        expected_type = self.function_stack[-1]
        expr_type = self.visit(ctx.expression()) if ctx.expression() else "void"

        # Check return type consistency
        if expected_type != "unknown" and expr_type != expected_type:
            self.add_error(
                f"Type error: function expects {expected_type} but got {expr_type}", ctx
            )
        return expr_type

    def visitCallExpr(self, ctx:CompiscriptParser.CallExprContext):
        # Handle function call expressions
        # Get the function name from the parent context (primaryAtom)
        function_name = ctx.parentCtx.getChild(0).getText()
        
        # Check if the function is declared
        if function_name not in self.symbol_table:
            self.add_error(f"Function '{function_name}' not declared", ctx)
            return "unknown"
        
        func_info = self.symbol_table[function_name]
        
        # Check if it's actually a function
        if "params" not in func_info:
            self.add_error(f"'{function_name}' is not a function", ctx)
            return "unknown"
        
        # Get expected parameters
        expected_params = func_info["params"]
        expected_param_count = len(expected_params)
        
        # Get actual arguments
        actual_args = []
        if ctx.arguments():
            actual_args = [self.visit(arg) for arg in ctx.arguments().expression()]
        actual_arg_count = len(actual_args)
        
        # Check parameter count
        if actual_arg_count != expected_param_count:
            self.add_error(
                f"Function '{function_name}' expects {expected_param_count} arguments but got {actual_arg_count}", 
                ctx
            )
            return func_info["type"]
        
        # Check parameter types
        expected_param_types = list(expected_params.values())
        for i, (expected_type, actual_type) in enumerate(zip(expected_param_types, actual_args)):
            if expected_type != actual_type:
                self.add_error(
                    f"Type error in argument {i+1}: expected {expected_type} but got {actual_type}", 
                    ctx
                )
        
        # Return the function's return type. Just in case.
        return func_info["type"]
    
    def visitProgram(self, ctx:CompiscriptParser.ProgramContext):
        print("Aquí estamos")
        code = []
        
        for stmt in ctx.statement():
            frag = self.visit(stmt)

            if isinstance(frag, CodeFragment):
                code.extend(frag.code)

        print("\n".join(code))