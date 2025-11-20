import re

class MIPSGenerator:
    """
    Genera código MIPS a partir de código intermedio de tres direcciones (TAC).
    Implementa asignación de registros y manejo del stack para funciones.
    """

    def __init__(self):
        # Registros temporales disponibles: $t0-$t9
        self.temp_registers = [f"$t{i}" for i in range(10)]
        # Registros salvados: $s0-$s7 (para variables que necesitan preservarse)
        self.saved_registers = [f"$s{i}" for i in range(8)]

        # Mapeo de variables/temporales a registros
        self.register_map = {}

        # Stack de registros disponibles
        self.available_temp_regs = self.temp_registers.copy()
        self.available_saved_regs = self.saved_registers.copy()

        # Contador para offset del stack
        self.stack_offset = 0

        # Variables que están en el stack
        self.stack_vars = {}

        # Código MIPS generado
        self.mips_code = []

        # Parámetros de función en espera
        self.params = []

        # Variables declaradas (para saber si necesitan espacio en .data)
        self.declared_vars = set()

        # Estamos dentro de una función
        self.in_function = False

        # Nombre de la función actual (para detectar métodos de clase)
        self.current_function = None

        # Contador de parámetros encontrados en la función actual
        self.param_counter = 0

    def get_register(self, var):
        """
        Implementación de getReg(): Asigna un registro a una variable.
        Si no hay registros disponibles, usa el stack.
        """
        # Si la variable ya tiene un registro asignado, retornarlo
        if var in self.register_map:
            return self.register_map[var]

        # Si hay registros temporales disponibles, usar uno
        if self.available_temp_regs:
            reg = self.available_temp_regs.pop(0)
            self.register_map[var] = reg
            return reg

        # Si hay registros salvados disponibles, usar uno
        if self.available_saved_regs:
            reg = self.available_saved_regs.pop(0)
            self.register_map[var] = reg
            return reg

        # Si no hay registros disponibles, usar el stack
        self.stack_offset += 4
        self.stack_vars[var] = self.stack_offset
        return f"-{self.stack_offset}($sp)"

    def free_register(self, var):
        """
        Libera el registro asociado a una variable temporal.
        """
        if var in self.register_map:
            reg = self.register_map[var]
            del self.register_map[var]

            if reg in self.temp_registers and reg not in self.available_temp_regs:
                self.available_temp_regs.append(reg)
            elif reg in self.saved_registers and reg not in self.available_saved_regs:
                self.available_saved_regs.append(reg)

    def load_value(self, operand, reg):
        """
        Carga un valor (literal o variable) en un registro.
        """
        # Si es un número literal
        if operand.lstrip('-').isdigit():
            self.mips_code.append(f"    li {reg}, {operand}")
        # Si es una variable o temporal
        elif operand in self.register_map:
            # Ya está en un registro
            src_reg = self.register_map[operand]
            if src_reg != reg:
                self.mips_code.append(f"    move {reg}, {src_reg}")
        elif operand in self.stack_vars:
            # Está en el stack
            offset = self.stack_vars[operand]
            self.mips_code.append(f"    lw {reg}, -{offset}($sp)")
        # Si es un temporal del TAC (t1, t2, etc.)
        elif operand.startswith('t') and len(operand) > 1 and operand[1:].isdigit():
            # Asignar registro si no tiene uno
            if operand not in self.register_map:
                temp_reg = self.get_register(operand)
                if temp_reg.startswith('$'):
                    # Ya está asignado, mover si es necesario
                    if temp_reg != reg:
                        self.mips_code.append(f"    move {reg}, {temp_reg}")
                else:
                    # Está en stack
                    self.mips_code.append(f"    lw {reg}, {temp_reg}")
            else:
                # Ya tiene registro asignado
                temp_reg = self.register_map[operand]
                if temp_reg != reg and temp_reg.startswith('$'):
                    self.mips_code.append(f"    move {reg}, {temp_reg}")
                elif not temp_reg.startswith('$'):
                    self.mips_code.append(f"    lw {reg}, {temp_reg}")
        # Si es un identificador (variable)
        elif operand.replace('_', '').replace('$', '').isalnum():
            # Verificar si es una variable declarada en .data
            if operand in self.declared_vars:
                # Cargar desde memoria global
                self.mips_code.append(f"    lw {reg}, var_{operand}")
            elif operand not in self.register_map:
                # Puede ser un parámetro de función
                # Si estamos en una función y es un identificador simple, asumimos que es parámetro
                if self.in_function and operand.isalpha():
                    # Determinar si es un método de clase (tiene underscore: ClassName_methodName)
                    is_method = '_' in self.current_function if self.current_function else False

                    # Para métodos, $a0 es 'this', parámetros empiezan en $a1
                    # Para funciones normales, parámetros empiezan en $a0
                    param_start = 1 if is_method else 0
                    param_reg_index = param_start + self.param_counter

                    if param_reg_index < 4:  # MIPS tiene $a0-$a3
                        param_reg = f"$a{param_reg_index}"
                        self.register_map[operand] = param_reg
                        self.param_counter += 1
                        if reg != param_reg:
                            self.mips_code.append(f"    move {reg}, {param_reg}")
                    else:
                        # Si hay más de 4 parámetros, están en el stack
                        # (por simplicidad, por ahora usamos un registro temporal)
                        var_reg = self.get_register(operand)
                        if var_reg.startswith('$') and var_reg != reg:
                            self.mips_code.append(f"    move {reg}, {var_reg}")
                else:
                    # Asignar un registro nuevo
                    var_reg = self.get_register(operand)
                    if var_reg.startswith('$') and var_reg != reg:
                        # Es un registro, mover si es necesario
                        self.mips_code.append(f"    move {reg}, {var_reg}")
                    elif not var_reg.startswith('$'):
                        # Está en stack
                        self.mips_code.append(f"    lw {reg}, {var_reg}")
            else:
                var_reg = self.register_map[operand]
                if var_reg.startswith('$') and var_reg != reg:
                    self.mips_code.append(f"    move {reg}, {var_reg}")
                elif not var_reg.startswith('$'):
                    self.mips_code.append(f"    lw {reg}, {var_reg}")
        else:
            self.mips_code.append(f"    # No se pudo cargar: {operand}")

    def translate_tac_to_mips(self, tac_code):
        """
        Traduce código TAC completo a MIPS.
        """
        if isinstance(tac_code, str):
            lines = tac_code.strip().split('\n')
        else:
            lines = tac_code

        # PRIMER PASO: Analizar para detectar variables, funciones y clases
        variables = set()
        arrays = set()
        objects = set()  # Para instancias de clases
        has_main = False

        for line in lines:
            line = line.strip()
            if line.startswith('main:'):
                has_main = True
                continue

            # Detectar asignaciones de variables (no temporales)
            if '=' in line and not line.endswith(':'):
                parts = line.split('=')
                var_name = parts[0].strip()

                # Detectar creación de objetos primero (usar regex para palabra completa "new")
                if re.match(r'(\w+)\s*=\s*new\s+(\w+)', line):
                    objects.add(var_name)
                # Si no es temporal (t1, t2, etc.) y no es llamada a función
                elif not (var_name.startswith('t') and var_name[1:].isdigit()):
                    if 'call' not in line:
                        variables.add(var_name)

                # Detectar arrays
                if '[]' in line or 'push(' in line:
                    arrays.add(var_name)

        # SEGUNDO PASO: Inicializar código MIPS con sección .data
        self.mips_code = [".data"]

        # Agregar variables declaradas
        for var in sorted(variables):
            self.mips_code.append(f"    var_{var}: .word 0")
            self.declared_vars.add(var)

        # Agregar arrays declarados (con espacio para 100 elementos por defecto)
        for arr in sorted(arrays):
            self.mips_code.append(f"    array_{arr}: .space 400  # Espacio para 100 integers")

        # Agregar objetos (instancias de clases)
        for obj in sorted(objects):
            self.mips_code.append(f"    obj_{obj}: .space 64  # Espacio para objeto (16 atributos max)")

        # constantes útiles
        # self.mips_code.extend([
        #     "    newline: .asciiz \"\\n\"",
        #     "    true_str: .asciiz \"true\"",
        #     "    false_str: .asciiz \"false\"",
        #     "    exception_msg: .asciiz \"Exception: \"",
        #     ""
        # ])

        # TERCER PASO: Sección de texto
        self.mips_code.extend([
            ".text",
            ".globl main"
        ])

        # Separar código main de definiciones de funciones
        main_code = []
        function_code = []
        current_list = main_code
        in_function_def = False

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped or line_stripped.startswith("#"):
                continue

            # Si encontramos una etiqueta de función (no Lnumero), cambiar a function_code
            if line_stripped.endswith(':') and not re.match(r'L\d+:', line_stripped):
                if not line_stripped.startswith('main:'):
                    current_list = function_code
                    in_function_def = True
                else:
                    current_list = main_code
                    in_function_def = False
            # Si vemos 'return', significa que la función terminará pronto
            elif 'return' in line_stripped and in_function_def:
                current_list.append(line_stripped)
                # Siguiente etiqueta (Lnumero) sigue siendo parte de la función
                continue
            # Si encontramos una etiqueta Lnumero después de un return, es el final de la función
            elif line_stripped.endswith(':') and re.match(r'L\d+:', line_stripped) and in_function_def:
                # Esta etiqueta es el final de la función
                current_list.append(line_stripped)
                # Volver a código main para el resto
                current_list = main_code
                in_function_def = False
                continue

            current_list.append(line_stripped)

        # Si no hay función main explícita, crear una
        if not has_main:
            self.mips_code.extend([
                "main:",
                "    # Inicializar frame pointer",
                "    move $fp, $sp",
                ""
            ])

        # CUARTO PASO: Traducir código main
        for line in main_code:
            self.translate_instruction(line)

        # Finalizar main si hay código main
        if not self.in_function or not has_main:
            self.mips_code.extend([
                "",
                "    # Terminar programa",
                "    li $v0, 10",
                "    syscall"
            ])

        # QUINTO PASO: Traducir funciones
        for line in function_code:
            self.translate_instruction(line)

        return "\n".join(self.mips_code)

    def translate_instruction(self, instruction):
        """
        Traduce una instrucción TAC individual a MIPS.
        """
        # Etiquetas de función (nombre seguido de :, no Lnumero:)
        if instruction.endswith(':') and not re.match(r'L\d+:', instruction):
            func_name = instruction[:-1]
            self.mips_code.append(f"\n{func_name}:")
            self.in_function = True
            self.current_function = func_name
            self.param_counter = 0  # Resetear contador de parámetros
            # Prólogo de función: guardar $ra y $fp
            self.mips_code.append("    # Prólogo de función")
            self.mips_code.append("    addi $sp, $sp, -8")
            self.mips_code.append("    sw $ra, 4($sp)")
            self.mips_code.append("    sw $fp, 0($sp)")
            self.mips_code.append("    move $fp, $sp")
            return

        # Etiquetas normales: L1:
        elif instruction.endswith(':'):
            # Si estamos en una función y es una etiqueta Lnumero, es el final de la función
            if self.in_function and re.match(r'L\d+:', instruction):
                # Agregar epilogo antes de la etiqueta
                self.mips_code.append("    # Epilogo de funcion")
                self.mips_code.append("    lw $fp, 0($sp)")
                self.mips_code.append("    lw $ra, 4($sp)")
                self.mips_code.append("    addi $sp, $sp, 8")
                self.mips_code.append("    jr $ra")
                self.in_function = False
                self.current_function = None
                self.param_counter = 0
            # La etiqueta ya incluye los :
            self.mips_code.append(f"\n{instruction}")

        # Creación de objetos: t1 = new ClassName (debe ir ANTES de asignación simple)
        elif re.match(r'(\w+)\s*=\s*new\s+(\w+)', instruction):
            self.translate_new_object(instruction)

        # Asignación simple: x = y
        elif '=' in instruction and not any(op in instruction for op in ['+', '-', '*', '/', '%', '<', '>', '==', '!=', '&&', '||', '!', 'call']):
            self.translate_assignment(instruction)

        # Operaciones aritméticas: x = y op z
        elif re.match(r'(\w+)\s*=\s*(.+?)\s*([+\-*/%])\s*(.+)', instruction):
            self.translate_arithmetic(instruction)

        # Operaciones relacionales: x = y relop z
        elif re.match(r'(\w+)\s*=\s*(.+?)\s*(==|!=|<|>|<=|>=)\s*(.+)', instruction):
            self.translate_relational(instruction)

        # Operaciones lógicas: x = y && z o x = y || z
        elif re.match(r'(\w+)\s*=\s*(.+?)\s*(\&\&|\|\|)\s*(.+)', instruction):
            self.translate_logical(instruction)

        # Operación unaria: x = -y o x = !y
        elif re.match(r'(\w+)\s*=\s*([-!])\s*(.+)', instruction):
            self.translate_unary(instruction)

        # Saltos condicionales: if condition goto L
        elif instruction.startswith('if'):
            self.translate_conditional_jump(instruction)

        # Salto incondicional: goto L
        elif instruction.startswith('goto'):
            label = instruction.split()[1]
            self.mips_code.append(f"    j {label}")

        # Parámetros de función: param x
        elif instruction.startswith('param'):
            param = instruction.split()[1]
            self.params.append(param)

        # Llamada a función: x = call f, n
        elif 'call' in instruction:
            self.translate_function_call(instruction)

        # Return: return x o return
        elif instruction.startswith('return'):
            self.translate_return(instruction)

        # Setup exception handler: # Setup exception handler: label
        elif instruction.startswith('# Setup exception handler:'):
            label = instruction.split(':')[1].strip()
            self.mips_code.append(f"    # Exception handler setup for {label}")
            # En MIPS real, configurar registro de excepciones
            self.mips_code.append(f"    la $k0, {label}")  # $k0 para exception handler

        # Exception caught: # Exception caught in var
        elif instruction.startswith('# Exception caught'):
            self.mips_code.append(f"    {instruction}")

        # Array operations: push, array access, etc.
        elif instruction.startswith('push'):
            self.translate_push(instruction)

        elif '[' in instruction and ']' in instruction:
            self.translate_array_access(instruction)

        else:
            # Instrucción no reconocida, agregar como comentario
            self.mips_code.append(f"    # {instruction}")

    def translate_assignment(self, instruction):
        """
        Traduce asignaciones simples: x = y
        """
        parts = instruction.split('=')
        dest = parts[0].strip()
        src = parts[1].strip()

        # Si el destino es una variable declarada en .data
        if dest in self.declared_vars:
            temp_reg = "$t9"
            self.load_value(src, temp_reg)
            self.mips_code.append(f"    sw {temp_reg}, var_{dest}")
            return

        # Obtener registro para el destino
        dest_reg = self.get_register(dest)

        # Cargar el valor fuente
        if dest_reg.startswith('$'):
            self.load_value(src, dest_reg)
        else:
            # Destino está en el stack
            temp_reg = "$t9"
            self.load_value(src, temp_reg)
            self.mips_code.append(f"    sw {temp_reg}, {dest_reg}")

    def translate_arithmetic(self, instruction):
        """
        Traduce operaciones aritméticas: x = y op z
        """
        match = re.match(r'(\w+)\s*=\s*(.+?)\s*([+\-*/%])\s*(.+)', instruction)
        if not match:
            return

        dest, left, op, right = match.groups()

        # Obtener registros
        dest_reg = self.get_register(dest)

        # Si el destino está en stack, usar registro temporal
        if not dest_reg.startswith('$'):
            actual_dest = "$t9"
        else:
            actual_dest = dest_reg

        # Cargar operandos
        left_reg = "$t7"
        right_reg = "$t8"

        self.load_value(left.strip(), left_reg)
        self.load_value(right.strip(), right_reg)

        # Generar operación MIPS
        if op == '+':
            self.mips_code.append(f"    add {actual_dest}, {left_reg}, {right_reg}")
        elif op == '-':
            self.mips_code.append(f"    sub {actual_dest}, {left_reg}, {right_reg}")
        elif op == '*':
            self.mips_code.append(f"    mul {actual_dest}, {left_reg}, {right_reg}")
        elif op == '/':
            self.mips_code.append(f"    div {left_reg}, {right_reg}")
            self.mips_code.append(f"    mflo {actual_dest}")
        elif op == '%':
            self.mips_code.append(f"    div {left_reg}, {right_reg}")
            self.mips_code.append(f"    mfhi {actual_dest}")

        # Guardar resultado
        if dest in self.declared_vars:
            # Guardar en variable global
            self.mips_code.append(f"    sw {actual_dest}, var_{dest}")
        elif not dest_reg.startswith('$'):
            # Guardar en stack
            self.mips_code.append(f"    sw {actual_dest}, {dest_reg}")

    def translate_relational(self, instruction):
        """
        Traduce operaciones relacionales: x = y relop z
        """
        match = re.match(r'(\w+)\s*=\s*(.+?)\s*(==|!=|<|>|<=|>=)\s*(.+)', instruction)
        if not match:
            return

        dest, left, op, right = match.groups()

        dest_reg = self.get_register(dest)
        if not dest_reg.startswith('$'):
            actual_dest = "$t9"
        else:
            actual_dest = dest_reg

        left_reg = "$t7"
        right_reg = "$t8"

        self.load_value(left.strip(), left_reg)
        self.load_value(right.strip(), right_reg)

        if op == '==':
            self.mips_code.append(f"    seq {actual_dest}, {left_reg}, {right_reg}")
        elif op == '!=':
            self.mips_code.append(f"    sne {actual_dest}, {left_reg}, {right_reg}")
        elif op == '<':
            self.mips_code.append(f"    slt {actual_dest}, {left_reg}, {right_reg}")
        elif op == '>':
            self.mips_code.append(f"    sgt {actual_dest}, {left_reg}, {right_reg}")
        elif op == '<=':
            self.mips_code.append(f"    sle {actual_dest}, {left_reg}, {right_reg}")
        elif op == '>=':
            self.mips_code.append(f"    sge {actual_dest}, {left_reg}, {right_reg}")

        if not dest_reg.startswith('$'):
            self.mips_code.append(f"    sw {actual_dest}, {dest_reg}")

    def translate_logical(self, instruction):
        """
        Traduce operaciones lógicas: x = y && z o x = y || z
        """
        match = re.match(r'(\w+)\s*=\s*(.+?)\s*(\&\&|\|\|)\s*(.+)', instruction)
        if not match:
            return

        dest, left, op, right = match.groups()

        dest_reg = self.get_register(dest)
        if not dest_reg.startswith('$'):
            actual_dest = "$t9"
        else:
            actual_dest = dest_reg

        left_reg = "$t7"
        right_reg = "$t8"

        self.load_value(left.strip(), left_reg)
        self.load_value(right.strip(), right_reg)

        if op == '&&':
            self.mips_code.append(f"    and {actual_dest}, {left_reg}, {right_reg}")
        elif op == '||':
            self.mips_code.append(f"    or {actual_dest}, {left_reg}, {right_reg}")

        if not dest_reg.startswith('$'):
            self.mips_code.append(f"    sw {actual_dest}, {dest_reg}")

    def translate_unary(self, instruction):
        """
        Traduce operaciones unarias: x = -y o x = !y
        """
        match = re.match(r'(\w+)\s*=\s*([-!])\s*(.+)', instruction)
        if not match:
            return

        dest, op, operand = match.groups()

        dest_reg = self.get_register(dest)
        if not dest_reg.startswith('$'):
            actual_dest = "$t9"
        else:
            actual_dest = dest_reg

        operand_reg = "$t7"
        self.load_value(operand.strip(), operand_reg)

        if op == '-':
            self.mips_code.append(f"    neg {actual_dest}, {operand_reg}")
        elif op == '!':
            # NOT lógico: si es 0 → 1, si es != 0 → 0
            self.mips_code.append(f"    seq {actual_dest}, {operand_reg}, $zero")

        if not dest_reg.startswith('$'):
            self.mips_code.append(f"    sw {actual_dest}, {dest_reg}")

    def translate_conditional_jump(self, instruction):
        """
        Traduce saltos condicionales: if condition goto L o ifFalse condition goto L
        """
        # Formato: "if False condition goto label" o "ifFalse condition goto label"
        parts = instruction.split()

        if 'ifFalse' in instruction or 'if False' in instruction:
            # ifFalse condition goto label
            if len(parts) >= 4:
                condition = parts[-3]
                label = parts[-1]

                cond_reg = "$t7"
                self.load_value(condition, cond_reg)
                self.mips_code.append(f"    beqz {cond_reg}, {label}")
        elif 'ifTrue' in instruction or 'if True' in instruction:
            # ifTrue condition goto label
            if len(parts) >= 4:
                condition = parts[-3]
                label = parts[-1]

                cond_reg = "$t7"
                self.load_value(condition, cond_reg)
                self.mips_code.append(f"    bnez {cond_reg}, {label}")
        elif instruction.startswith('if '):
            # if condition goto label (asumimos que es "if condition != 0")
            parts = instruction.replace('goto', '').split()
            if len(parts) >= 3:
                condition = parts[1]
                label = parts[2]

                cond_reg = "$t7"
                self.load_value(condition, cond_reg)
                self.mips_code.append(f"    bnez {cond_reg}, {label}")

    def translate_function_call(self, instruction):
        """
        Traduce llamadas a función: x = call f, n
        Maneja el stack frame y los parámetros.
        """
        # Guardar registros en el stack antes de llamar
        self.mips_code.append("    # Guardar registros en el stack")

        # Pasar parámetros (los primeros 4 van en $a0-$a3, el resto en stack)
        for i, param in enumerate(self.params):
            if i < 4:
                arg_reg = f"$a{i}"
                self.load_value(param, arg_reg)
            else:
                # Parámetros adicionales van al stack
                temp_reg = "$t9"
                self.load_value(param, temp_reg)
                self.mips_code.append(f"    sw {temp_reg}, -{(i-3)*4}($sp)")

        # Extraer nombre de la función
        match = re.search(r'call\s+(\w+)', instruction)
        if match:
            func_name = match.group(1)

            # Llamar a la función
            self.mips_code.append(f"    jal {func_name}")

            # El resultado está en $v0
            if '=' in instruction:
                dest = instruction.split('=')[0].strip()
                dest_reg = self.get_register(dest)

                if dest_reg.startswith('$'):
                    self.mips_code.append(f"    move {dest_reg}, $v0")
                else:
                    self.mips_code.append(f"    sw $v0, {dest_reg}")

        # Limpiar parámetros
        self.params = []

    def translate_return(self, instruction):
        """
        Traduce return: return x o return
        """
        parts = instruction.split()

        if len(parts) > 1:
            # return value
            return_value = parts[1]
            self.load_value(return_value, "$v0")

        # Epílogo de función: restaurar frame pointer y retornar
        self.mips_code.append("    # Epílogo de función")
        self.mips_code.append("    lw $fp, 0($sp)")
        self.mips_code.append("    lw $ra, 4($sp)")
        self.mips_code.append("    addi $sp, $sp, 8")
        self.mips_code.append("    jr $ra")
        self.in_function = False
        self.current_function = None
        self.param_counter = 0

    def translate_push(self, instruction):
        """
        Traduce push para arrays (operación auxiliar)
        """
        # Por ahora, comentario
        self.mips_code.append(f"    # {instruction}")

    def translate_array_access(self, instruction):
        """
        Traduce acceso a arrays: x = arr[i] o arr[i] = x
        """
        if '=' in instruction:
            parts = instruction.split('=')
            left = parts[0].strip()
            right = parts[1].strip()

            if '[' in left:
                # arr[i] = x
                match = re.match(r'(\w+)\[(.+)\]', left)
                if match:
                    arr, index = match.groups()

                    # Cargar índice
                    index_reg = "$t7"
                    self.load_value(index, index_reg)

                    # Multiplicar índice por 4 (tamaño de palabra)
                    self.mips_code.append(f"    sll {index_reg}, {index_reg}, 2")

                    # Cargar valor a guardar
                    value_reg = "$t8"
                    self.load_value(right, value_reg)

                    # Guardar en array
                    self.mips_code.append(f"    sw {value_reg}, {arr}({index_reg})")
            else:
                # x = arr[i]
                match = re.match(r'(\w+)\[(.+)\]', right)
                if match:
                    arr, index = match.groups()

                    index_reg = "$t7"
                    self.load_value(index, index_reg)

                    self.mips_code.append(f"    sll {index_reg}, {index_reg}, 2")

                    dest_reg = self.get_register(left)
                    if dest_reg.startswith('$'):
                        self.mips_code.append(f"    lw {dest_reg}, {arr}({index_reg})")
                    else:
                        self.mips_code.append(f"    lw $t9, {arr}({index_reg})")
                        self.mips_code.append(f"    sw $t9, {dest_reg}")

    def translate_new_object(self, instruction):
        """
        Traduce creación de objetos: t1 = new ClassName
        """
        match = re.match(r'(\w+)\s*=\s*new\s+(\w+)', instruction)
        if not match:
            self.mips_code.append(f"    # Could not parse: {instruction}")
            return

        dest, class_name = match.groups()

        # Obtener dirección del objeto en .data
        temp_reg = "$t9"
        self.mips_code.append(f"    # Create new object of class {class_name}")
        self.mips_code.append(f"    la {temp_reg}, obj_{dest}")

        # Asignar a variable o temporal
        dest_reg = self.get_register(dest)
        if dest_reg.startswith('$'):
            if dest_reg != temp_reg:
                self.mips_code.append(f"    move {dest_reg}, {temp_reg}")
        else:
            self.mips_code.append(f"    sw {temp_reg}, {dest_reg}")
