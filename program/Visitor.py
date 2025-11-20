from CompiscriptParser import CompiscriptParser
from CompiscriptVisitor import CompiscriptVisitor
from CodeFragment import CodeFragment
from CodeGenerator import CodeGenerator
from MIPSGenerator import MIPSGenerator

class Visitor(CompiscriptVisitor):
    def __init__(self):
        self.symbol_table = {}
        self.errors = []  # List to store semantic errors
        self.loop_depth = 0  # Track loop depth for break/continue statements
        self.function_stack = []  # Track function context for return type checking
        self.cg = CodeGenerator()  # Generation of temporal code with format t or L
        self.mips_gen = MIPSGenerator()  # Generation of MIPS assembly code

    def add_error(self, message, ctx):
        # Add an error message with line information to the errors list
        line = ctx.start.line if ctx and ctx.start else "unknown"
        self.errors.append(f"Error at line {line}: {message}")

    def visitPrimaryExpr(self, ctx: CompiscriptParser.PrimaryExprContext):
        # Caso 1: literal (número, string, etc.)
        if ctx.literalExpr():
            return self.visit(ctx.literalExpr())

        # Caso 2: variable o llamada (identificador)
        elif ctx.leftHandSide():
            result = self.visit(ctx.leftHandSide())
            if not isinstance(result, CodeFragment):
                result = CodeFragment([], str(result), "unknown_left")
            return result

        # Caso 3: subexpresión entre paréntesis ( (expr) )
        elif ctx.expression():
            result = self.visit(ctx.expression())
            if not isinstance(result, CodeFragment):
                result = CodeFragment([], str(result), "unknown_expr")
            return result

        # Si no entra en ningún caso
        return CodeFragment([], "None", "unknown_primary")
    
    def visitLeftHandSide(self, ctx: CompiscriptParser.LeftHandSideContext):
        # Obtener el base (primaryAtom)
        if not ctx.primaryAtom():
            return CodeFragment([], None, "unknown")

        base_result = self.visit(ctx.primaryAtom())
        if not isinstance(base_result, CodeFragment):
            base_result = CodeFragment([], str(base_result), "unknown")

        # Si no hay suffixOp, devolver el base
        if not ctx.suffixOp() or len(ctx.suffixOp()) == 0:
            return base_result

        # Procesar la cadena de suffixOp
        current = base_result
        for suffix in ctx.suffixOp():
            suffix_type = suffix.__class__.__name__

            if 'PropertyAccessExpr' in suffix_type:
                # Acceso a propiedad: objeto.propiedad
                prop_name = suffix.Identifier().getText()

                # Verificar que el base sea un objeto
                if current.type in self.symbol_table and self.symbol_table[current.type].get('type') == 'class':
                    class_info = self.symbol_table[current.type]

                    # Verificar si es un método o atributo
                    if prop_name in class_info.get('methods', {}):
                        # Es un método - crear referencia para llamada posterior
                        current = CodeFragment(current.code, f"{current.place}.{prop_name}", current.type)
                    elif prop_name in class_info.get('attributes', {}):
                        # Es un atributo
                        attr_type = class_info['attributes'][prop_name]
                        current = CodeFragment(current.code, f"{current.place}.{prop_name}", attr_type)
                    else:
                        self.add_error(f"Class '{current.type}' has no member '{prop_name}'", suffix)
                        current = CodeFragment(current.code, f"{current.place}.{prop_name}", "unknown")
                else:
                    self.add_error(f"Cannot access property of non-object type '{current.type}'", suffix)
                    current = CodeFragment(current.code, f"{current.place}.{prop_name}", "unknown")

            elif 'CallExpr' in suffix_type:
                # Llamada a función/método
                # Si current.place contiene '.', es una llamada a método
                if '.' in current.place:
                    parts = current.place.split('.')
                    obj_name = parts[0]
                    method_name = parts[1]

                    # Obtener información del objeto
                    obj_symbol = self.symbol_table.get(obj_name)
                    if obj_symbol and obj_symbol['type'] in self.symbol_table:
                        class_info = self.symbol_table[obj_symbol['type']]
                        method_info = class_info.get('methods', {}).get(method_name)

                        if method_info:
                            # Procesar argumentos
                            args = []
                            if suffix.arguments():
                                for arg_expr in suffix.arguments().expression():
                                    arg = self.visit(arg_expr)
                                    if isinstance(arg, CodeFragment):
                                        args.append(arg)

                            # Generar código para llamada a método
                            code = current.code.copy()

                            # Agregar el objeto como primer parámetro (this)
                            code.append(f"param {obj_name}")

                            # Agregar argumentos
                            for arg in args:
                                code.extend(arg.code)
                                code.append(f"param {arg.place}")

                            # Llamar al método calificado
                            qualified_name = f"{obj_symbol['type']}_{method_name}"
                            result_temp = self.cg.new_temp()
                            code.append(f"{result_temp} = call {qualified_name}, {len(args) + 1}")

                            return CodeFragment(code, result_temp, method_info['type'])

                # Si no es método, es función normal
                return self.visit(suffix)

            elif 'IndexExpr' in suffix_type:
                # Acceso a array
                return self.visit(suffix)

        return current
        
    def visitLiteralExpr(self, ctx: CompiscriptParser.LiteralExprContext):
        value = ctx.getText()

        if value.isdigit():
            return CodeFragment([], value, "integer")
        elif value.replace('.', '', 1).isdigit():
            return CodeFragment([], value, "float")
        elif value.startswith('"') and value.endswith('"'):
            return CodeFragment([], value, "string")
        elif value in ("true", "false"):
            return CodeFragment([], value, "boolean")
        elif value == "null":
            return CodeFragment([], "null", "null")
        else:
            return CodeFragment([], value, "unknown_literal")

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

        declared_type = ctx.typeAnnotation().getText().replace(":", "").strip() if ctx.typeAnnotation() else None
        expression = self.visit(ctx.initializer().expression())

        if isinstance(expression, str):
            expression: CodeFragment = CodeFragment([], expression, expression)

        # Check initializer type and compare with declared type
        if ctx.initializer():
            if expression and declared_type and declared_type != expression.type:
                decl_t = declared_type if isinstance(declared_type, str) else None
                expr_t = expression.type if isinstance(expression.type, str) else None

                if decl_t and expr_t and decl_t.endswith("[]") and expr_t.endswith("[]"):
                    elem_decl = decl_t.replace("[]", "")
                    elem_init = expr_t.replace("[]", "")
                    if elem_decl != elem_init:
                        self.add_error(f"Type error: variable '{var_name}' declared as {declared_type} but initialized with {expression.type}", ctx)
                # Handle type errors
                elif declared_type != expression.type:
                    self.add_error(f"Type error: variable '{var_name}' declared as {declared_type} but initialized with {expression.type}", ctx)

            else:
                declared_type = expression.type

        # Store variable in symbol table
        self.symbol_table[var_name] = {
            "type": declared_type or "unknown",
            "const": False
        }

        if expression:
            # Use initializer type if no declared type
            code = expression.code + [f"{var_name} = {expression.place if expression.place else declared_type}"]
            return CodeFragment(code, var_name, expression.type if expression.type else declared_type)
        
        return CodeFragment([], None, "unknown")

    def visitConstantDeclaration(self, ctx:CompiscriptParser.ConstantDeclarationContext):
        # Handle constant declarations
        const_name = ctx.Identifier().getText()

        if const_name in self.symbol_table:
            self.add_error(f"Identifier '{const_name}' already declared.", ctx)
            return self.visitChildren(ctx)

        declared_type = ctx.typeAnnotation().type_().getText() if ctx.typeAnnotation() else None

        expression: CodeFragment = self.visit(ctx.expression())

        # Check type consistency for constants
        if expression and declared_type and declared_type != expression.type:
                if declared_type in ["integer", "float", "string", "boolean"]:
                    self.add_error(f"Type error: constant '{const_name}' declared as {declared_type} but initialized with {expression.type}.", ctx)
                else:
                    self.add_error(f"Type error: type '{declared_type}' not recognized.", ctx)

        self.symbol_table[const_name] = {
            "type": declared_type if declared_type else expression.type,
            "const": True
        }

        if expression:
            code = expression.code + [f"{const_name} = {expression.place}"]
            return CodeFragment(code, const_name, expression.type)
        
        return CodeFragment([], None, "unknown")

    def visitAssignment(self, ctx):
        var_name = ctx.getChild(0).getText()
        expr = self.visit(ctx.getChild(2))

        symbol = self.symbol_table.get(var_name)
        if not symbol:
            self.add_error(f"Variable '{var_name}' not declared", ctx)
            return CodeFragment([], None, "unknown")

        if expr and symbol['type'] != expr.type:
            self.add_error(f"Type mismatch: variable '{var_name}' declared as {symbol['type']} but initialized with {expr.type}", ctx)

        code = expr.code + [f"{var_name} = {expr.place}"]
        return CodeFragment(code, var_name, symbol['type'])
    
    # **************************
    # *** Expression Methods ***
    # **************************

    def visitExpressionStatement(self, ctx:CompiscriptParser.ExpressionStatementContext):
        # Handle expression statements
        return self.visit(ctx.expression())

    # Arithmetic methods

    def visitAdditiveExpr(self, ctx:CompiscriptParser.AdditiveExprContext):
        # Handle additive expressions (+, -)
        # Start with the first multiplicativeExpr
        result = self.visit(ctx.getChild(0))

        if not isinstance(result, CodeFragment):
            result = CodeFragment([], str(result), "unknown")

        # Process each additional operator and operand pair
        i = 1
        while i < ctx.getChildCount():
            operator = ctx.getChild(i).getText()
            right = self.visit(ctx.getChild(i + 1))

            if isinstance(right, str):
                right = CodeFragment([], right, right)

            # Allow operations between integers and floats
            if result.type in ["integer", "float"] and right.type in ["integer", "float"]:
                result_type = "float" if "float" in (result.type, right.type) else "integer"
            else:
                self.add_error(f"Type error while evaluating {result.type} {operator} {right.type}", ctx)
                result_type = "unknown"

            temp = self.cg.new_temp()
            code = result.code + right.code + [f"{temp} = {result.place} {operator} {right.place}"]
            result = CodeFragment(code, temp, result_type)

            i += 2  # Move to next operator

        return result

    def visitMultiplicativeExpr(self, ctx:CompiscriptParser.MultiplicativeExprContext):
        # Handle multiplicative expressions (*, /, %)
        # Start with the first unaryExpr
        result = self.visit(ctx.getChild(0))

        if not isinstance(result, CodeFragment):
            result = CodeFragment([], str(result), "unknown")

        # Process each additional operator and operand pair
        i = 1
        while i < ctx.getChildCount():
            operator = ctx.getChild(i).getText()
            right = self.visit(ctx.getChild(i + 1))

            if isinstance(right, str):
                right = CodeFragment([], right, right)

            # Validar tipos
            if result.type in ["integer", "float"] and right.type in ["integer", "float"]:
                result_type = "float" if "float" in (result.type, right.type) else "integer"
            else:
                self.add_error(f"Type error: cannot apply {operator} to {result.type} and {right.type}", ctx)
                result_type = "unknown"

            temp = self.cg.new_temp()
            code = result.code + right.code + [f"{temp} = {result.place} {operator} {right.place}"]
            result = CodeFragment(code, temp, result_type)

            i += 2  # Move to next operator

        return result

    # Logical methods

    def visitLogicalAndExpr(self, ctx:CompiscriptParser.LogicalAndExprContext):
        # Handle logical AND expressions (&&)
        # Start with the first equalityExpr
        result = self.visit(ctx.getChild(0))

        if isinstance(result, str):
            result = CodeFragment([], result, result)

        # Process each additional && operator and operand pair
        i = 1
        while i < ctx.getChildCount():
            operator = ctx.getChild(i).getText()  # Should be '&&'
            right = self.visit(ctx.getChild(i + 1))

            if isinstance(right, str):
                right = CodeFragment([], right, right)

            # Check both sides are boolean
            if result.type != "boolean" or right.type != "boolean":
                self.add_error(f"Type error: logical operator requires booleans, got {result.type} and {right.type}", ctx)
                result = CodeFragment([], None, "unknown")
                break

            temp = self.cg.new_temp()
            code = result.code + right.code + [f"{temp} = {result.place} && {right.place}"]
            result = CodeFragment(code, temp, "boolean")

            i += 2  # Move to next operator

        return result

    def visitLogicalOrExpr(self, ctx:CompiscriptParser.LogicalOrExprContext):
        # Handle logical OR expressions (||)
        # Start with the first logicalAndExpr
        result = self.visit(ctx.getChild(0))

        if isinstance(result, str):
            result = CodeFragment([], result, result)

        # Process each additional || operator and operand pair
        i = 1
        while i < ctx.getChildCount():
            operator = ctx.getChild(i).getText()  # Should be '||'
            right = self.visit(ctx.getChild(i + 1))

            if isinstance(right, str):
                right = CodeFragment([], right, right)

            if result.type != "boolean" or right.type != "boolean":
                self.add_error(f"Type error: logical operator requires booleans, got {result.type} and {right.type}", ctx)
                result = CodeFragment([], None, "unknown")
                break

            temp = self.cg.new_temp()
            code = result.code + right.code + [f"{temp} = {result.place} || {right.place}"]
            result = CodeFragment(code, temp, "boolean")

            i += 2  # Move to next operator

        return result

    def visitUnaryExpr(self, ctx:CompiscriptParser.UnaryExprContext):
        # Handle unary expressions (-, !)
        if ctx.getChildCount() == 2:
            operator = ctx.getChild(0).getText()
            operand = self.visit(ctx.getChild(1))

            if isinstance(operand, str):
                operand = CodeFragment([], operand, operand)

            # Allow negation for numbers
            if operator == "-" and operand.type in ["integer", "float"]:
                temp = self.cg.new_temp()
                code = operand.code + [f"{temp} = -{operand.place}"]
                return CodeFragment(code, temp, operand.type)
            
            # Allow ! for booleans
            elif operator == "!" and operand.type == "boolean":
                temp = self.cg.new_temp()
                code = operand.code + [f"{temp} = !{operand.place}"]
                return CodeFragment(code, temp, operand.type)
            
            else:
                self.add_error(f"Type error: operator {operator} not valid for {operand.type}", ctx)
                return CodeFragment([], None, "unknown")
        
        result = self.visit(ctx.getChild(0))
        if not isinstance(result, CodeFragment):
            result = CodeFragment([], str(result), "unknown")
        return result
    
    # Comparison methods

    def visitEqualityExpr(self, ctx:CompiscriptParser.EqualityExprContext):
        # Handle equality expressions (==, !=, ===, !==)
        # Start with the first relationalExpr
        result = self.visit(ctx.getChild(0))

        if isinstance(result, str):
            result = CodeFragment([], result, result)

        # Process each additional equality operator and operand pair
        i = 1
        while i < ctx.getChildCount():
            operator = ctx.getChild(i).getText()
            right = self.visit(ctx.getChild(i + 1))

            if isinstance(right, str):
                right = CodeFragment([], right, right)

            # Handle equality and strict equality. Based in JavaScript xd
            if operator in ["==", "!=", "===", "!=="]:
                # Allow equality between same types
                if result.type == right.type or (result.type in ["integer", "float"] and right.type in ["integer", "float"]):
                    temp = self.cg.new_temp()
                    code = result.code + right.code + [f"{temp} = {result.place} {operator} {right.place}"]
                    result = CodeFragment(code, temp, "boolean")
                else:
                    self.add_error(f"Type error: cannot apply '{operator}' between {result.type} and {right.type}", ctx)
                    result = CodeFragment([], None, "unknown")
                    break
            else:
                self.add_error(f"Unknown equality operator '{operator}'", ctx)
                result = CodeFragment([], None, "unknown")
                break

            i += 2  # Move to next operator

        return result

    def visitRelationalExpr(self, ctx:CompiscriptParser.RelationalExprContext):
        # Handle relational expressions (<, >, <=, >=)
        # Start with the first additiveExpr
        result = self.visit(ctx.getChild(0))

        if isinstance(result, str):
            result = CodeFragment([], result, result)

        # Process each additional relational operator and operand pair
        i = 1
        while i < ctx.getChildCount():
            operator = ctx.getChild(i).getText()
            right = self.visit(ctx.getChild(i + 1))

            if isinstance(right, str):
                right = CodeFragment([], right, right)

            # Handle relational/comparison operators
            if operator in ["<", ">", "<=", ">="]:
                # Allow comparisons between integers and floats
                if result.type in ["integer", "float"] and right.type in ["integer", "float"]:
                    temp = self.cg.new_temp()
                    code = result.code + right.code + [f"{temp} = {result.place} {operator} {right.place}"]
                    result = CodeFragment(code, temp, "boolean")
                else:
                    self.add_error(f"Type error: cannot compare {result.type} and {right.type} with {operator}", ctx)
                    result = CodeFragment([], None, "unknown")
                    break
            else:
                self.add_error(f"Unknown relational operator '{operator}'", ctx)
                result = CodeFragment([], None, "unknown")
                break

            i += 2  # Move to next operator

        return result
    
    # **************************
    # *** Structures Methods ***
    # **************************

    def visitArrayLiteral(self, ctx:CompiscriptParser.ArrayLiteralContext):
        # Handle array literal expressions
        if ctx.getChildCount() == 2:
            return CodeFragment([], None, "unknown[]")

        # Get types of all elements in the array
        elements = ctx.expression()

        if not elements:
            # Empty array initialization
            temp = self.cg.new_temp()
            return CodeFragment([f"{temp} = []", temp, "unknown[]"])

        # Check for consistent element types
        element_fragments: list[CodeFragment] = [self.visit(expr) for expr in elements]
        first_type = element_fragments[0].type

        # If any type is unknown, return unknown[]
        for element in element_fragments[1:]:
            if element.type != first_type:
                self.add_error(f"Type error: inconsistent types in array literal: found {first_type} instead of {element.type}", ctx)
                return CodeFragment([], None, "unknown[]")
            
        temp = self.cg.new_temp()
        code = [f"{temp} = []"]

        for element in element_fragments:
            code += element.code + [f"push({temp}, {element.place})"]

        return CodeFragment(code, temp, f"{first_type}[]")
    
    def visitIndexExpr(self, ctx:CompiscriptParser.IndexExprContext):
        # Handle array indexing expressions
        base_name = ctx.parentCtx.getChild(0).getText()

        # Check if array is in symbol table
        if base_name not in self.symbol_table:
            self.add_error(f"Variable '{base_name}' not declared", ctx)
            return CodeFragment([], None, "unknown")
        
        base_info = self.symbol_table[base_name]
        base_type = base_info["type"]
        index = self.visit(ctx.expression())

        # Check if base is an array
        if not base_type.endswith("[]"):
            self.add_error(f"Type error: '{base_name}' is not an array", ctx)
            return CodeFragment([], None, "unknown")

        # Check if index is an integer
        if index.type != "integer":
            self.add_error(f"Type error: array index must be integer, got {index.type}", ctx)
            return CodeFragment([], None, "unknown")

        element_type = base_type.replace("[]", "", 1)
        temp = self.cg.new_temp()
        code = index.code + [f"{temp} = {base_name}[{index.place}]"]
        return CodeFragment(code, temp, element_type)

    # **********************************
    # *** Control Structures Methods ***
    # **********************************

    def visitIfStatement(self, ctx:CompiscriptParser.IfStatementContext):
        # Handle if statements
        condition: CodeFragment = self.visit(ctx.expression())

        # Allow only boolean conditions
        if condition.type != "boolean":
            self.add_error("Condition in 'if' must be boolean", ctx)
            return CodeFragment([], None, "unknown")
        
        # Get then and else blocks
        thenBlock: CodeFragment = self.visit(ctx.block(0))
        # Else block can be None
        elseBlock: CodeFragment | None = self.visit(ctx.block(1)) if ctx.block(1) else None

        elseLabel = self.cg.new_label()
        endLabel = self.cg.new_label()

        code = condition.code
        code.append(f"if False {condition.place} goto {elseLabel}")
        code += thenBlock.code
        code.append(f"goto {endLabel}")
        code.append(f"{elseLabel}:")

        if elseBlock:
            code += elseBlock.code

        code.append(f"{endLabel}:")
        
        return CodeFragment(code, None, "void")
    
    def visitBlock(self, ctx: CompiscriptParser.BlockContext):
        code = []
        for stmt in ctx.statement():
            frag = self.visit(stmt)
            if isinstance(frag, CodeFragment):
                code.extend(frag.code)
        return CodeFragment(code, None, "void")

    def visitWhileStatement(self, ctx:CompiscriptParser.WhileStatementContext):
        # Increase loop depth
        self.loop_depth += 1

        start_label = self.cg.new_label()
        body_label = self.cg.new_label()
        end_label = self.cg.new_label()

        condition = self.visit(ctx.expression())
        body = self.visit(ctx.block())
        
        # Allow only boolean conditions
        if condition.type != "boolean":
            self.add_error("Condition in 'while' must be boolean", ctx)
    
        code = []
        code.append(f"{start_label}:")
        code += condition.code
        code.append(f"ifFalse {condition.place} goto {end_label}")
        code += body.code
        code.append(f"goto {start_label}")
        code.append(f"{end_label}:")

        self.loop_depth -= 1
        return CodeFragment(code, None, "void")

    def visitDoWhileStatement(self, ctx: CompiscriptParser.DoWhileStatementContext):
        self.loop_depth += 1

        start_label = self.cg.new_label()
        condition_label = self.cg.new_label()
        end_label = self.cg.new_label()

        body = self.visit(ctx.block())
        condition = self.visit(ctx.expression())

        if condition.type != "boolean":
            self.add_error("Condition in 'do-while' must be boolean", ctx)

        code = []
        code.append(f"{start_label}:")
        code += body.code
        code.append(f"{condition_label}:")
        code += condition.code
        code.append(f"ifTrue {condition.place} goto {start_label}")
        code.append(f"{end_label}:")

        self.loop_depth -= 1
        return CodeFragment(code, None, "void")

    def visitForStatement(self, ctx: CompiscriptParser.ForStatementContext):
        self.loop_depth += 1

        init_code = []
        if ctx.variableDeclaration():
            init_code = self.visit(ctx.variableDeclaration()).code
        elif ctx.assignment():
            init_code = self.visit(ctx.assignment()).code

        start_label = self.cg.new_label()
        body_label = self.cg.new_label()
        end_label = self.cg.new_label()

        condition = self.visit(ctx.expression(0)) if ctx.expression(0) else None
        increment = self.visit(ctx.expression(1)) if ctx.expression(1) else None
        body = self.visit(ctx.block())

        code = []
        code += init_code
        code.append(f"{start_label}:")
        if condition:
            code += condition.code
            code.append(f"ifFalse {condition.place} goto {end_label}")
        code += body.code
        if increment:
            code += increment.code
        code.append(f"goto {start_label}")
        code.append(f"{end_label}:")

        self.loop_depth -= 1
        return CodeFragment(code, None, "void")

    def visitForeachStatement(self, ctx: CompiscriptParser.ForeachStatementContext):
        self.loop_depth += 1

        iterable = self.visit(ctx.expression())
        var_name = ctx.Identifier().getText()

        if not iterable.type.endswith("[]"):
            self.add_error("Foreach requires an array to iterate over", ctx)
            elem_type = "unknown"
        else:
            elem_type = iterable.type.replace("[]", "", 1)

        # Add loop variable
        self.symbol_table[var_name] = {"type": elem_type, "const": False}

        start_label = self.cg.new_label()
        loop_label = self.cg.new_label()
        end_label = self.cg.new_label()
        index_temp = self.cg.new_temp()

        body = self.visit(ctx.block())

        code = []
        code += iterable.code
        code.append(f"{index_temp} = 0")
        code.append(f"{start_label}:")
        code.append(f"if {index_temp} >= len({iterable.place}) goto {end_label}")
        temp_elem = self.cg.new_temp()
        code.append(f"{temp_elem} = {iterable.place}[{index_temp}]")
        code.append(f"{var_name} = {temp_elem}")
        code += body.code
        code.append(f"{index_temp} = {index_temp} + 1")
        code.append(f"goto {start_label}")
        code.append(f"{end_label}:")

        del self.symbol_table[var_name]
        self.loop_depth -= 1
        return CodeFragment(code, None, "void")

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

    def visitFunctionDeclaration(self, ctx: CompiscriptParser.FunctionDeclarationContext):
        func_name = ctx.Identifier().getText()

        if func_name in self.symbol_table:
            self.add_error(f"Function '{func_name}' already declared", ctx)
            return CodeFragment([], None, "unknown")

        return_type = ctx.type_().getText() if ctx.type_() else "void"

        param_types = {}
        if ctx.parameters():
            for param in ctx.parameters().parameter():
                pname = param.Identifier().getText()
                ptype = param.type_().getText() if param.type_() else "unknown"
                param_types[pname] = ptype

        self.symbol_table[func_name] = {
            "type": return_type,
            "params": param_types,
            "const": True
        }

        old_symbols = self.symbol_table.copy()
        for pname, ptype in param_types.items():
            self.symbol_table[pname] = {"type": ptype, "const": False}

        self.function_stack.append(return_type)

        body = self.visit(ctx.block())

        start_label = self.cg.new_label()
        end_label = self.cg.new_label()
        code = [f"{func_name}:"] + body.code + [f"{end_label}:"]

        self.symbol_table = old_symbols
        self.function_stack.pop()

        return CodeFragment(code, func_name, "function")

    def visitReturnStatement(self, ctx: CompiscriptParser.ReturnStatementContext):
        if not self.function_stack:
            self.add_error("'return' used outside of function", ctx)
            return CodeFragment([], None, "unknown")

        expected_type = self.function_stack[-1]
        expr = self.visit(ctx.expression()) if ctx.expression() else None

        if expr and expr.type != expected_type and expected_type != "unknown":
            self.add_error(f"Type error: function expects {expected_type} but got {expr.type}", ctx)

        code = []
        if expr:
            code += expr.code + [f"return {expr.place}"]
        else:
            code.append("return")

        return CodeFragment(code, None, expected_type)

    def visitCallExpr(self, ctx:CompiscriptParser.CallExprContext):
        # Handle function call expressions
        # Get the function name from the parent context (primaryAtom)
        function_name = ctx.parentCtx.getChild(0).getText()

        if function_name not in self.symbol_table:
            self.add_error(f"Function '{function_name}' not declared", ctx)
            return CodeFragment([], None, "unknown")

        func_info = self.symbol_table[function_name]
        if "params" not in func_info:
            self.add_error(f"'{function_name}' is not a function", ctx)
            return CodeFragment([], None, "unknown")

        expected_params = list(func_info["params"].values())
        args = []
        if ctx.arguments():
            args = [self.visit(arg) for arg in ctx.arguments().expression()]

        if len(args) != len(expected_params):
            self.add_error(f"Function '{function_name}' expects {len(expected_params)} args, got {len(args)}", ctx)
            return CodeFragment([], None, func_info["type"])

        code = []
        for arg in args:
            code += arg.code
            code.append(f"param {arg.place}")

        temp = self.cg.new_temp()
        code.append(f"{temp} = call {function_name}, {len(args)}")

        return CodeFragment(code, temp, func_info["type"])

    # *************************
    # *** Classes & Objects ***
    # *************************

    def visitClassDeclaration(self, ctx: CompiscriptParser.ClassDeclarationContext):
        """
        Maneja declaraciones de clases con métodos y atributos.
        """
        class_name = ctx.Identifier(0).getText()  # Primer identificador es el nombre de la clase

        # Verificar herencia
        parent_class = None
        if ctx.getChildCount() > 3 and ctx.Identifier(1):  # Si hay segundo identificador, es herencia
            parent_class = ctx.Identifier(1).getText()
            if parent_class not in self.symbol_table:
                self.add_error(f"Parent class '{parent_class}' not defined", ctx)

        # Verificar si la clase ya existe
        if class_name in self.symbol_table:
            self.add_error(f"Class '{class_name}' already declared", ctx)
            return CodeFragment([], None, "unknown")

        # Crear entrada en tabla de símbolos para la clase
        class_info = {
            "type": "class",
            "parent": parent_class,
            "methods": {},
            "attributes": {},
            "const": True
        }

        # Guardar contexto actual de la tabla de símbolos
        old_symbols = self.symbol_table.copy()

        # Agregar 'this' al contexto de la clase
        self.symbol_table["this"] = {"type": class_name, "const": True}

        code = []
        code.append(f"# Class {class_name}")

        # PRIMERO: Procesar atributos para que estén disponibles para los métodos
        if ctx.classMember():
            for member in ctx.classMember():
                if member.variableDeclaration():
                    # Es un atributo
                    var_ctx = member.variableDeclaration()
                    attr_name = var_ctx.Identifier().getText()
                    attr_type = var_ctx.typeAnnotation().type_().getText() if var_ctx.typeAnnotation() else "unknown"

                    class_info["attributes"][attr_name] = attr_type

                    # Los atributos se manejan como offsets en la estructura
                    code.append(f"# Attribute {class_name}.{attr_name}: {attr_type}")

        # SEGUNDO: Procesar métodos (ahora con atributos ya registrados)
        if ctx.classMember():
            for member in ctx.classMember():
                if member.functionDeclaration():
                    # Es un método
                    method_ctx = member.functionDeclaration()
                    method_name = method_ctx.Identifier().getText()
                    method_return_type = method_ctx.type_().getText() if method_ctx.type_() else "void"

                    # Obtener parámetros
                    param_types = {}
                    if method_ctx.parameters():
                        for param in method_ctx.parameters().parameter():
                            pname = param.Identifier().getText()
                            ptype = param.type_().getText() if param.type_() else "unknown"
                            param_types[pname] = ptype

                    class_info["methods"][method_name] = {
                        "type": method_return_type,
                        "params": param_types
                    }

                    # Generar TAC para el método
                    # Nombre del método incluye el nombre de la clase
                    qualified_method_name = f"{class_name}_{method_name}"
                    code.append(f"{qualified_method_name}:")

                    # Agregar atributos de clase al contexto (para que los métodos puedan accederlos)
                    for attr_name, attr_type in class_info["attributes"].items():
                        self.symbol_table[attr_name] = {"type": attr_type, "const": False}

                    # Agregar parámetros al contexto
                    for pname, ptype in param_types.items():
                        self.symbol_table[pname] = {"type": ptype, "const": False}

                    self.function_stack.append(method_return_type)
                    body = self.visit(method_ctx.block())
                    code.extend(body.code)

                    end_label = self.cg.new_label()
                    code.append(f"{end_label}:")

                    self.function_stack.pop()

                    # Limpiar atributos del contexto
                    for attr_name in class_info["attributes"].keys():
                        if attr_name in self.symbol_table:
                            del self.symbol_table[attr_name]

                    # Limpiar parámetros
                    for pname in param_types.keys():
                        if pname in self.symbol_table:
                            del self.symbol_table[pname]

        # Guardar clase en tabla de símbolos
        self.symbol_table[class_name] = class_info

        # Restaurar tabla de símbolos
        del self.symbol_table["this"]
        for key in list(self.symbol_table.keys()):
            if key not in old_symbols and key != class_name:
                del self.symbol_table[key]

        return CodeFragment(code, class_name, "class")

    def visitNewExpr(self, ctx: CompiscriptParser.NewExprContext):
        """
        Maneja creación de objetos: new ClassName(args)
        """
        class_name = ctx.Identifier().getText()

        if class_name not in self.symbol_table:
            self.add_error(f"Class '{class_name}' not defined", ctx)
            return CodeFragment([], None, "unknown")

        class_info = self.symbol_table[class_name]
        if class_info.get("type") != "class":
            self.add_error(f"'{class_name}' is not a class", ctx)
            return CodeFragment([], None, "unknown")

        # Generar código para crear instancia
        temp = self.cg.new_temp()
        code = [f"{temp} = new {class_name}"]

        # Si hay constructor, llamarlo
        if class_info.get("methods") and "constructor" in class_info["methods"]:
            # Manejar argumentos del constructor
            if ctx.arguments():
                args = [self.visit(arg) for arg in ctx.arguments().expression()]
                for arg in args:
                    code.extend(arg.code)
                    code.append(f"param {arg.place}")

                code.append(f"call {class_name}_constructor, {len(args)}")

        return CodeFragment(code, temp, class_name)

    # **********************
    # *** Try-Catch ********
    # **********************

    def visitTryCatchStatement(self, ctx: CompiscriptParser.TryCatchStatementContext):
        """
        Maneja bloques try-catch para manejo de excepciones.
        """
        # Obtener el nombre de la variable de excepción
        exception_var = ctx.Identifier().getText()

        # Generar etiquetas
        try_label = self.cg.new_label()
        catch_label = self.cg.new_label()
        end_label = self.cg.new_label()

        code = []

        # Inicio del bloque try
        code.append(f"{try_label}:")
        code.append(f"# Setup exception handler: {catch_label}")

        # Visitar bloque try
        try_block = self.visit(ctx.block(0))
        code.extend(try_block.code)

        # Si no hubo excepciones, saltar el catch
        code.append(f"goto {end_label}")

        # Bloque catch
        code.append(f"{catch_label}:")
        code.append(f"# Exception caught in {exception_var}")

        # Agregar variable de excepción al contexto
        old_symbols = self.symbol_table.copy()
        self.symbol_table[exception_var] = {"type": "exception", "const": False}

        # Visitar bloque catch
        catch_block = self.visit(ctx.block(1))
        code.extend(catch_block.code)

        # Restaurar tabla de símbolos
        self.symbol_table = old_symbols

        # Fin del try-catch
        code.append(f"{end_label}:")

        return CodeFragment(code, None, "void")

    def visitProgram(self, ctx:CompiscriptParser.ProgramContext):
        code = []

        for stmt in ctx.statement():
            frag = self.visit(stmt)
            if isinstance(frag, CodeFragment):
                code.extend(frag.code)

        # Generar código intermedio (TAC)
        tac_code = "\n".join(code)
        self.generated_code = tac_code
        print("=== Código Intermedio (TAC) ===")
        print(tac_code)

        # Generar código MIPS a partir del TAC
        mips_code = self.mips_gen.translate_tac_to_mips(tac_code)
        self.mips_code = mips_code
        print("\n=== Código MIPS ===")
        print(mips_code)

        return tac_code