"""
This module contains the main logic of the interpreter.

IPP: You must definitely modify this file. Bend it to your will.

Author: Ondřej Ondryáš <iondryas@fit.vut.cz>
Author: Patrik Lošťák <xlostap00>
"""

import logging
import operator
import sys
from pathlib import Path
from typing import Any, TextIO

from lxml import etree
from lxml.etree import ParseError
from pydantic import ValidationError

from interpreter.error_codes import ErrorCode
from interpreter.exceptions import InterpreterError
from interpreter.input_model import Assign, ClassDef, Expr, Program, Send, Var

logger = logging.getLogger(__name__)


class SolClass:
    """Representation of SOL26 class in memory"""

    # ast_node can be empty beacuse of builtins (classes without xml)
    def __init__(
        self, name: str, parent_name: str | None = None, ast_node: ClassDef | None = None
    ):
        self.name = name
        self.parent_name = parent_name
        self.ast_node = ast_node


class SolInst:
    """Representation of specific object in memory"""

    def __init__(self, sol_class: SolClass, val: int | str | bool | tuple[Any, Any] | None = None):
        self.sol_class = sol_class
        self.attrs: dict[str, SolInst] = {}
        self.val = val


class LocalFrame:
    """Represents local variables for blocks or methods"""

    def __init__(
        self, owner_class: SolClass | None = None, parent_frame: LocalFrame | None = None
    ) -> None:
        self.vars: dict[str, SolInst] = {}
        self.owner_class = owner_class
        self.params: set[str] = set()  # Set of parameter names for blocks
        self.parent_frame = (
            parent_frame  # Reference to parent frame for nested blocks (closures painful omg)
        )


class Interpreter:
    """
    The main interpreter class, responsible for loading the source file and executing the program.
    """

    def __init__(self) -> None:
        self.current_program: Program | None = None
        self.class_table: dict[str, SolClass] = {}  # Memory for classes

        dummy_cls = SolClass(name="Dummy")

        # Add vars for singletons (True, False, Nil)
        # Needed to avoid mypy checks, use dummy class
        # which initialize but will be rewritten in initialize_builtins
        # cool trick xd
        self.nil_singleton: SolInst = SolInst(dummy_cls)
        self.true_singleton: SolInst = SolInst(dummy_cls)
        self.false_singleton: SolInst = SolInst(dummy_cls)

    def load_program(self, source_file_path: Path) -> None:
        """
        Reads the source SOL-XML file and stores it as the target program for this interpreter.
        If any program was previously loaded, it is replaced by the new one.

        IPP: If you wish to run static checks on the program before execution, this is a good place
             to call them from.
        """
        logger.info("Opening source file: %s", source_file_path)
        try:
            xml_tree = etree.parse(source_file_path)
        except ParseError as e:
            raise InterpreterError(
                error_code=ErrorCode.INT_XML, message="Error parsing input XML"
            ) from e
        try:
            self.current_program = Program.from_xml_tree(xml_tree.getroot())  # type: ignore
        except ValidationError as e:
            raise InterpreterError(
                error_code=ErrorCode.INT_STRUCTURE, message="Invalid SOL-XML structure"
            ) from e

        # Start static checks
        self._static_check()

    def _static_check(self) -> None:
        """Checks the program if Main class exists and checks also for run method"""
        # Extra check if the program was loaded
        if self.current_program is None:
            return

        # Check if the Main class is defined
        main_class = None
        for cls in self.current_program.classes:
            if cls.name == "Main":
                main_class = cls
                break

        # Throw an error if the Main class is missing
        if main_class is None:
            raise InterpreterError(
                error_code=ErrorCode.SEM_MAIN, message="Main class is missing in the program!"
            )

        run_method = None
        for method in main_class.methods:
            if method.selector == "run":
                run_method = method
                break

        if run_method is None:
            raise InterpreterError(
                error_code=ErrorCode.SEM_MAIN, message="run method is missing in Main class!"
            )

        logger.info("Static check successful!")

    def initialize_builtins(self) -> None:
        """Initialize class_table with builtins (builtin classes of SOL26)"""

        # All classes inherits from class Object
        self.class_table["Object"] = SolClass(name="Object")

        # Data types
        self.class_table["Integer"] = SolClass(name="Integer", parent_name="Object")
        self.class_table["String"] = SolClass(name="String", parent_name="Object")
        self.class_table["Nil"] = SolClass(name="Nil", parent_name="Object")
        self.class_table["Block"] = SolClass(name="Block", parent_name="Object")

        # Logical values
        self.class_table["True"] = SolClass(name="True", parent_name="Object")
        self.class_table["False"] = SolClass(name="False", parent_name="Object")

        # Initialize singletons
        self.nil_singleton = SolInst(self.class_table["Nil"], None)
        self.true_singleton = SolInst(self.class_table["True"], True)
        self.false_singleton = SolInst(self.class_table["False"], False)

        logger.info("All bultin classes were loaded")

    def execute(self, input_io: TextIO) -> None:
        """
        Executes the currently loaded program, using the provided input stream as standard input.
        """
        logger.info("Executing program")

        # Check for mypy that program is not None
        if self.current_program is None:
            return

        # Load builtins
        self.initialize_builtins()

        # First we have to fill our tables with all classes
        for ast_class in self.current_program.classes:
            class_name = ast_class.name

            for method in ast_class.methods:
                # Expected arity is number of ':'
                expected_arity = method.selector.count(":")
                if method.block is not None and method.block.arity != expected_arity:
                    raise InterpreterError(
                        ErrorCode.SEM_ARITY,
                        f"Method {method.selector} in class {class_name} has arity \
                        {method.block.arity} but expected {expected_arity}",
                    )

            # Check for redefinitions
            if class_name in self.class_table:
                raise InterpreterError(
                    error_code=ErrorCode.SEM_ERROR,
                    message=f"Redefinition of existing class: {class_name}",
                )

            # Save to memory
            self.class_table[class_name] = SolClass(
                name=class_name,
                # Check if class has parent, assign None when not
                parent_name=ast_class.parent if ast_class.parent else None,
                ast_node=ast_class,
            )

        # Create first instance
        main_cls_def = self.class_table["Main"]
        main_inst = SolInst(sol_class=main_cls_def)

        # Defensive programming, mypy is tough
        if main_cls_def.ast_node is None:
            raise InterpreterError(
                error_code=ErrorCode.SEM_ERROR, message="Class Main doesn't have AST node"
            )

        # Find run method in Main class
        run_method_node = None
        for method in main_cls_def.ast_node.methods:
            if method.selector == "run":
                run_method_node = method
                break

        # Check for mypy but run should be checked already (defensive programming ig)
        if run_method_node is None:
            raise InterpreterError(
                error_code=ErrorCode.SEM_MAIN, message="Method run or its block is missing"
            )

        # Local frame where we save self as ptr to object on which we call the method
        curr_frame = LocalFrame(owner_class=main_cls_def)
        curr_frame.vars["self"] = main_inst

        logger.info("Start method Main.run")

        # Blocks in method run
        for assign_node in run_method_node.block.assigns:
            self.eval_assign(assign_node, curr_frame)

    def eval_assign(self, assign_node: Assign, curr_frame: LocalFrame) -> SolInst:
        """Evaluates assign cmd and saves result into current frame"""

        # Evaluate the expr (right side)
        final_result = self.eval_expr(assign_node.expr, curr_frame)

        # Track the name of variable
        var_name = assign_node.target.name

        if var_name in ["self", "super"]:
            raise InterpreterError(
                ErrorCode.SEM_ERROR, f"Cannot assign to reserved variable '{var_name}'"
            )

        if var_name in curr_frame.params:
            raise InterpreterError(
                ErrorCode.SEM_COLLISION, f"Cannot assign to parameter variable '{var_name}'"
            )

        # Save result into local memory (curr_frame), we don't need to save _var
        if var_name == "_":
            logger.info("Assign: not saving result of var '_' ")
            return final_result

        # We need to find in which frame var lives and update it
        frame: LocalFrame | None = curr_frame
        found = False
        while frame is not None:
            # Cant ovewrite params of block with outer vars of same name
            if var_name in frame.vars and var_name not in frame.params:
                logger.info(f"Assign: updating variable '{var_name}' in existing frame")
                frame.vars[var_name] = final_result
                found = True
                break
            frame = frame.parent_frame

        # If var not found in any frame we save it in current frame
        if not found:
            logger.info(f"Assign: saving variable '{var_name}' in current frame")
            curr_frame.vars[var_name] = final_result

        logger.info(f"Assign: Saved object into {var_name}")
        return final_result

    def _var_expr(self, var_node: Var, curr_frame: LocalFrame) -> SolInst:
        """Helper function to evaluate variable expression, used in eval_expr"""
        var_name = var_node.name
        logger.info(f"Reading var {var_name}")
        # Super is just alias for self when we read var
        choose_name = "self" if var_name == "super" else var_name
        # Look for vars in curr frame and its parents (closures)
        frame: LocalFrame | None = curr_frame
        while frame is not None:
            if choose_name in frame.vars:
                return frame.vars[choose_name]
            frame = frame.parent_frame

        # if not in local vars look for self and its attrs
        curr_self = None
        frame = curr_frame
        while frame is not None:
            if "self" in frame.vars:
                curr_self = frame.vars["self"]
                break
            frame = frame.parent_frame
        # if attr called "super" idk its not forbidden
        if curr_self and var_name in curr_self.attrs:
            return curr_self.attrs[var_name]

        # Undefined variable
        raise InterpreterError(
            error_code=ErrorCode.SEM_UNDEF,
            message=f"Try to read undefined variable {var_name}",
        )

    def eval_expr(self, expr_node: Expr, curr_frame: LocalFrame) -> SolInst:
        """Evaluates any expression (var, literal, block, send) and returns final object"""
        logger.info("Evaluating expression")

        # Read variable
        if expr_node.var is not None:
            return self._var_expr(expr_node.var, curr_frame)

        # Literal (integer, string, nil, true, false)
        if expr_node.literal is not None:
            literal_value = expr_node.literal.value
            literal_class = expr_node.literal.class_id
            logger.info(f"Processing literal: class '{literal_class}', value '{literal_value}'")

            # Class literals
            if literal_class == "class":
                class_name = str(literal_value)
                if class_name not in self.class_table:
                    raise InterpreterError(
                        error_code=ErrorCode.SEM_UNDEF,
                        message=f"Unknown class {class_name} in class literal",
                    )
                return SolInst(sol_class=self.class_table[class_name], val="CLASS_REF")

            # Extra check if the class exists in table
            if literal_class not in self.class_table:
                raise InterpreterError(
                    error_code=ErrorCode.SEM_UNDEF,
                    message=f"Unknown builtin class {literal_class}",
                )

            sol_class = self.class_table[literal_class]

            # Convert values from XML to real values
            real_val: int | str | bool | None = None

            if literal_class == "Integer":
                real_val = int(literal_value)
            elif literal_class == "String":
                real_val = str(literal_value)
            elif literal_class == "True":
                return self.true_singleton
            elif literal_class == "False":
                return self.false_singleton
            elif literal_class == "Nil":
                return self.nil_singleton

            return SolInst(sol_class=sol_class, val=real_val)

        # Send
        if expr_node.send is not None:
            logger.info("SEND: executing...")
            # Process the message
            return self.eval_send(expr_node.send, curr_frame)

        if expr_node.block is not None:
            logger.info("BLOCK: accessing...")
            # Save block AST node and current frame
            block_data = (expr_node.block, curr_frame)
            return SolInst(sol_class=self.class_table["Block"], val=block_data)

        # Extra check but shouldn't get here, we have validator
        raise InterpreterError(
            error_code=ErrorCode.INT_STRUCTURE, message="Unknown expression type in AST"
        )

    def _builtin_integer(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst | None:
        "Integer class methods"
        # always int but extra check for mypy
        if not isinstance(receiver.val, int):
            raise InterpreterError(
                ErrorCode.INT_OTHER, "Receiver of Integer method doesn't have int value"
            )
        val_receiver = int(receiver.val)

        # Numeric operations (1 arg required)
        # Use dict to avoid to many elifs
        # really like this feature
        math_ops = {
            "plus:": (operator.add, "Integer"),
            "minus:": (operator.sub, "Integer"),
            "multiplyBy:": (operator.mul, "Integer"),
            "divBy:": (operator.floordiv, "Integer"),  # floordiv ret int
            "equalTo:": (operator.eq, "Bool"),
            "greaterThan:": (operator.gt, "Bool"),
        }

        if selector in math_ops:
            if len(parsed_args) != 1:
                raise InterpreterError(
                    error_code=ErrorCode.INT_OTHER,
                    message=f"Message {selector} requires 1 argument",
                )

            arg_obj = parsed_args[0]
            if self._get_boss_cls_name(arg_obj.sol_class) != "Integer":
                raise InterpreterError(
                    error_code=ErrorCode.INT_INVALID_ARG,
                    message=f"Argument for {selector} has to be Integer",
                )
            # Extra check for mypy
            if not isinstance(arg_obj.val, int):
                raise InterpreterError(
                    error_code=ErrorCode.INT_OTHER,
                    message=f"Argument for {selector} doesn't have int value",
                )
            val_arg = int(arg_obj.val)

            # These operations return int
            if selector == "divBy:" and val_arg == 0:
                raise InterpreterError(ErrorCode.INT_INVALID_ARG, "Division by zero")

            # Call proper operation and right ret type from dict
            op_func, ret_type = math_ops[selector]
            result = op_func(val_receiver, val_arg)
            logger.info(f"Result of {val_receiver} {selector} {val_arg} is {result}")

            if ret_type == "Integer":
                return SolInst(self.class_table["Integer"], result)

            # Or bool ret type
            return self.true_singleton if result else self.false_singleton

        if selector == "isNumber":
            return self.true_singleton
        if (selector == "asString" or selector == "asInteger") and len(parsed_args) != 0:
            raise InterpreterError(
                ErrorCode.INT_OTHER, f"Message {selector} doesn't require and argument"
            )
        if selector == "asString":
            return SolInst(self.class_table["String"], str(val_receiver))
        if selector == "asInteger":
            return receiver  # returns itself

        # Cycle
        if selector == "timesRepeat:":
            return self._times_repeat_helper(val_receiver, parsed_args)

        return None

    def _times_repeat_helper(self, val_receiver: int, parsed_args: list[SolInst]) -> SolInst:
        """Helper function for timesRepeat: message at Integer class, hate rule C901"""
        logger.info(f"message timesRepeat: called with number {val_receiver}")
        if len(parsed_args) != 1:
            raise InterpreterError(
                ErrorCode.INT_OTHER, "Message 'timesRepeat:' requires 1 argument"
            )

        block_arg = parsed_args[0]
        # If 0 block won't be executed and returns Nil
        if val_receiver <= 0:
            return self.nil_singleton

        last_result = self.nil_singleton

        # Run block n-times
        for n in range(1, val_receiver + 1):
            # Create new object Integer representing number of current iteration
            iter_obj = SolInst(self.class_table["Integer"], n)

            # Send block a message with number of iteration and call builtin block
            result = self._eval_builtin_send(block_arg, "value:", [iter_obj])

            # If arg is not object and DNU message "value:" --> INT.DNU
            if result is None:
                raise InterpreterError(
                    ErrorCode.INT_DNU, "Argument for 'timesRepeat' DNU the message 'value:'"
                )

            last_result = result

        return last_result

    def _builtin_string(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst | None:
        """String class methods"""
        val_str = str(receiver.val)

        # Prints string to stdout without format chars
        if selector == "print":
            logger.info(f"[Interpret prints]: >>>{val_str}<<<")
            print(val_str, end="")
            return receiver
        # asString returns itself
        if selector == "asString":
            return receiver
        if selector == "isString":
            return self.true_singleton
        # length returns INT of chars (1 esc seq = 1 char)
        if selector == "length":
            return SolInst(self.class_table["Integer"], len(val_str))
        # asInteger returns INT if can be converted, otherwise Nil
        if selector == "asInteger":
            try:
                return SolInst(self.class_table["Integer"], int(val_str))
            except ValueError:
                return self.nil_singleton
        if selector == "equalTo:":
            # Return false if comparsion does't make sense
            if len(parsed_args) != 1 or parsed_args[0].sol_class.name != "String":
                return self.false_singleton
            is_eq = val_str == str(parsed_args[0].val)
            return self.true_singleton if is_eq else self.false_singleton
        # concatenateWith returns Nil if arg is not String otherwise returns joined String
        if selector == "concatenateWith:":
            if len(parsed_args) != 1 or parsed_args[0].sol_class.name != "String":
                return self.nil_singleton
            return SolInst(self.class_table["String"], val_str + str(parsed_args[0].val))
        # startsWith:endsBefore: indexes from 1, bad args -> nil, args diff <= 0 -> ""
        if selector == "startsWith:endsBefore:":
            return self._string_helper(val_str, parsed_args)

        return None

    def _string_helper(self, val_str: str, parsed_args: list[SolInst]) -> SolInst:
        """Helper function for startsWith:endsBefore at String class"""
        if len(parsed_args) != 2:
            raise InterpreterError(
                ErrorCode.INT_OTHER, "startsWith:endsBefore: requires 2 arguments"
            )
        # Checks for arguments
        arg1, arg2 = parsed_args[0], parsed_args[1]
        if arg1.sol_class.name != "Integer" or arg2.sol_class.name != "Integer":
            return self.nil_singleton
        # Extra check for mypy
        if not isinstance(arg1.val, int) or not isinstance(arg2.val, int):
            raise InterpreterError(
                error_code=ErrorCode.INT_OTHER,
                message="Arguments for startsWith:endsBefore: must have int values",
            )
        start, end = int(arg1.val), int(arg2.val)
        if start <= 0 or end <= 0:
            return self.nil_singleton
        # args difference <= 0 returns ""
        if (end - start) <= 0:
            return SolInst(self.class_table["String"], "")

        # Indexes from 1, convert it to 0 because better
        start_idx = start - 1
        end_idx = end - 1

        final = val_str[start_idx:end_idx] if end_idx <= len(val_str) else val_str[start_idx:]
        return SolInst(self.class_table["String"], final)

    def _builtin_boolean(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst | None:
        """True/False class methods"""
        is_true = receiver.sol_class.name == "True"

        # Returns true/false string for true/false
        if selector == "asString":
            return SolInst(self.class_table["String"], "true" if is_true else "false")
        # Returns negation of true/false
        if selector == "not":
            return self.false_singleton if is_true else self.true_singleton
        # returns true
        if selector == "isBoolean":
            return self.true_singleton

        # Take argument as block and run it (send block message value:)
        if selector == "ifTrue:ifFalse:":
            if len(parsed_args) != 2:
                raise InterpreterError(ErrorCode.INT_OTHER, "ifTrue:ifFalse: requires 2 arguments")
            # if receiver is "true" the first arg is evaluated (send message value: ),
            # if receiver is "false" the second arg is evaluated (send message value: )
            target_block = parsed_args[0] if is_true else parsed_args[1]
            return self._eval_builtin_send(target_block, "value", [])

        if selector == "and:":
            if not is_true:
                return receiver  # if false returns false, if true send message value:
            return self._eval_builtin_send(parsed_args[0], "value", [])

        if selector == "or:":
            if is_true:
                return receiver  # If true returns true, otherwise send message value:
            return self._eval_builtin_send(parsed_args[0], "value", [])

        return None

    def _builtin_nil(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst | None:
        """Handle nil class methods"""
        if selector == "isNil":
            return self.true_singleton
        if selector == "asString":
            return SolInst(self.class_table["String"], "nil")
        return None

    def _builtin_block(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst | None:
        """Methods for code blocks"""
        if selector == "isBlock":
            return self.true_singleton

        block_val = receiver.val
        if selector.startswith("value"):
            # Process empty block with arity 0
            if block_val is None:
                if len(parsed_args) != 0:
                    raise InterpreterError(
                        ErrorCode.INT_DNU,
                        f"Block expects 0 arguments and got {parsed_args}",
                    )
                # Empty block returns nil
                return self.nil_singleton
            # Look into the block and its env (closer)
            if not isinstance(block_val, tuple):
                raise InterpreterError(ErrorCode.INT_OTHER, "Block is corrupted")

            block_node, outer_frame = block_val

            if len(parsed_args) != block_node.arity:
                raise InterpreterError(
                    ErrorCode.INT_DNU,
                    f"Block expects {block_node.arity} arguments and got {parsed_args}",
                )

            # Frame referencing to its parent
            block_frame = LocalFrame(owner_class=outer_frame.owner_class, parent_frame=outer_frame)
            # Save parameters of block
            for param in range(block_node.arity):
                param_name = block_node.parameters[param].name
                block_frame.vars[param_name] = parsed_args[param]
                block_frame.params.add(param_name)

            # Evaluate the block content
            last_result = self.nil_singleton
            for assign_node in block_node.assigns:
                last_result = self.eval_assign(assign_node, block_frame)
            return last_result  # return the last value of last command

        if selector == "whileTrue:":
            if len(parsed_args) != 1:
                raise InterpreterError(ErrorCode.INT_OTHER, "whileTrue: requires 1 argument")

            block_body = parsed_args[0]
            last_result = self.nil_singleton

            while True:
                # Run block from receiver (condition)
                cond = self._eval_builtin_send(receiver, "value", [])
                if cond is None or cond.sol_class.name != "True":
                    break
                # Cond is true we execute the block body
                result = self._eval_builtin_send(block_body, "value", [])
                if result is None:
                    raise InterpreterError(ErrorCode.INT_DNU, "Block body DNU the message value")
                last_result = result
            return last_result
        return None

    def _builtin_object(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst | None:
        """Methods accessible to all objects"""
        # Compares if 2 objects are identical (if same object)
        if selector == "identicalTo:":
            if len(parsed_args) != 1:
                raise InterpreterError(ErrorCode.INT_OTHER, "identicalTo: requires 1 argument")
            is_ident = receiver is parsed_args[0]
            return self.true_singleton if is_ident else self.false_singleton
        # Compares 2 objects based on their data, if no attributes same as identicalTo:
        if selector == "equalTo:":
            if len(parsed_args) != 1:
                raise InterpreterError(ErrorCode.INT_OTHER, "equalTo: requires 1 argument")
            if receiver.val is None and parsed_args[0].val is None:
                is_eq = receiver is parsed_args[0]
            else:
                is_eq = receiver.val == parsed_args[0].val
            return self.true_singleton if is_eq else self.false_singleton
        # returns ''
        if selector == "asString":
            if len(parsed_args) != 0:
                raise InterpreterError(
                    ErrorCode.INT_OTHER, "asString doesn't require any arguments"
                )
            return SolInst(self.class_table["String"], "")
        # returns false
        if selector in ["isNumber", "isString", "isBlock", "isNil", "isBoolean"]:
            if len(parsed_args) != 0:
                raise InterpreterError(
                    ErrorCode.INT_OTHER, f"Message {selector} doesn't require argument"
                )
            return self.false_singleton

        return None

    def _eval_builtin_send(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst | None:
        """Evaluate message as builtin method, if not builtin returns None"""
        class_name = self._get_boss_cls_name(receiver.sol_class)

        if class_name == "Integer":
            result = self._builtin_integer(receiver, selector, parsed_args)
            if result is not None:
                return result
        elif class_name == "String":
            result = self._builtin_string(receiver, selector, parsed_args)
            if result is not None:
                return result
        elif class_name in ["True", "False"]:
            result = self._builtin_boolean(receiver, selector, parsed_args)
            if result is not None:
                return result
        elif class_name == "Nil":
            result = self._builtin_nil(receiver, selector, parsed_args)
            if result is not None:
                return result
        elif class_name == "Block":
            result = self._builtin_block(receiver, selector, parsed_args)
            if result is not None:
                return result
        # All objects including Main goes into object
        return self._builtin_object(receiver, selector, parsed_args)

    def _eval_attr_access(
        self, receiver: SolInst, selector: str, parsed_args: list[SolInst]
    ) -> SolInst:
        """Process read/write of instance attribute if method wasn't found, otherwise DNU error"""
        # Getter (0 args and doesn't end with ':')
        if len(parsed_args) == 0 and not selector.endswith(":"):
            if selector in receiver.attrs:
                logger.info(f"Reading instance attribute {selector}")
                return receiver.attrs[selector]
            raise InterpreterError(
                error_code=ErrorCode.INT_DNU,
                message=f"Receiver DNU the message {selector}",
            )

        # Setter (1 arg and ends with ':')
        if len(parsed_args) == 1 and selector.endswith(":"):
            attr_name = selector[:-1]  # Remove the ':' ("vysl:" --> "vysl")

            # Check collision in AST nodes
            curr_cls: SolClass | None = receiver.sol_class
            while curr_cls is not None:
                if curr_cls.ast_node is not None:
                    for method in curr_cls.ast_node.methods:
                        if method.selector == attr_name:
                            raise InterpreterError(
                                ErrorCode.INT_INST_ATTR,
                                f"ERROR: attribute {attr_name} collides with existing method",
                            )
                # Move to parent class
                curr_cls = (
                    self.class_table.get(curr_cls.parent_name) if curr_cls.parent_name else None
                )
            # Check collision with builtin methods with no params
            builtin_methods = [
                "asString",
                "isNumber",
                "isString",
                "isBlock",
                "isNil",
                "isBoolean",
                "print",
                "value",
                "length",
                "asInteger",
                "not",
            ]
            if attr_name in builtin_methods:
                raise InterpreterError(
                    ErrorCode.INT_INST_ATTR,
                    f"ERROR: attribute {attr_name} collides with existing builtin method",
                )
            # Save value
            logger.info(f"Writing instance attribute {attr_name}")
            receiver.attrs[attr_name] = parsed_args[0]
            return receiver

        raise InterpreterError(
            ErrorCode.INT_DNU,
            f"Receiver of class {receiver.sol_class.name} DNU message {selector}",
        )

    def _get_boss_cls_name(self, start_cls: SolClass) -> str:
        """Helper function to get the name of the boss class (the one without parent)
        for given class
        """
        curr_cls: SolClass | None = start_cls
        while curr_cls is not None:
            if curr_cls.name in ["Object", "Integer", "String", "Nil", "True", "False", "Block"]:
                return curr_cls.name
            curr_cls = self.class_table.get(curr_cls.parent_name) if curr_cls.parent_name else None
        return "Object"  # Default boss class if no parent found, should not happen

    def _cls_msg_new(
        self, class_receiver: SolClass, receiver_boss: str, parsed_args: list[SolInst]
    ) -> SolInst:
        """Helper function to process message 'new'"""
        if len(parsed_args) != 0:
            raise InterpreterError(
                ErrorCode.INT_OTHER, "Message 'new' doesn't require any arguments"
            )
        # No new instances, just return singletons
        if receiver_boss == "Nil":
            return self.nil_singleton
        if receiver_boss == "True":
            return self.true_singleton
        if receiver_boss == "False":
            return self.false_singleton

        # Create new instance of class_receiver
        new_inst = SolInst(sol_class=class_receiver)
        # Initialize instance attributes with default values
        if receiver_boss == "Integer":
            new_inst.val = 0
        elif receiver_boss == "String":
            new_inst.val = ""
        elif receiver_boss == "Nil":
            new_inst.val = None
        elif receiver_boss == "True":
            new_inst.val = True
        elif receiver_boss == "False":
            new_inst.val = False

        return new_inst

    def _cls_msg_from(
        self, class_receiver: SolClass, receiver_boss: str, parsed_args: list[SolInst]
    ) -> SolInst:
        """Helper function to process message 'from:' for classes"""
        if len(parsed_args) != 1:
            raise InterpreterError(ErrorCode.INT_OTHER, "Message 'from:' requires 1 argument")
        # No new instances, just return singletons
        if receiver_boss == "Nil":
            return self.nil_singleton
        if receiver_boss == "True":
            return self.true_singleton
        if receiver_boss == "False":
            return self.false_singleton

        arg = parsed_args[0]
        arg_boss = self._get_boss_cls_name(arg.sol_class)
        # Check if argument is compatible with receiver class
        if receiver_boss != "Object" and arg_boss != receiver_boss:
            raise InterpreterError(
                ErrorCode.INT_INVALID_ARG,
                f"Class expects internal attribute of type {receiver_boss} but got {arg_boss}",
            )
        # Create new instance of class_receiver with value from argument
        new_inst = SolInst(sol_class=class_receiver)
        new_inst.val = arg.val
        new_inst.attrs = arg.attrs.copy()  # Copy attributes from argument

        return new_inst

    def _cls_msg_read(
        self, class_receiver: SolClass, receiver_boss: str, parsed_args: list[SolInst]
    ) -> SolInst:
        """Helper function to process message 'read' for classes"""
        if receiver_boss != "String":
            raise InterpreterError(
                ErrorCode.SEM_UNDEF,
                f"Message 'read' is only valid for class String but got {receiver_boss}",
            )
        if len(parsed_args) != 0:
            raise InterpreterError(
                ErrorCode.INT_OTHER, "Message 'read' doesn't require any arguments"
            )
        # Read line from input and create new instance of String with it
        input_line = sys.stdin.readline()
        if input_line.endswith("\n"):
            input_line = input_line[:-1]  # Remove trailing newline
        if input_line.endswith("\r"):
            input_line = input_line[:-1]  # Remove trailing carriage return (for Windows)

        return SolInst(self.class_table["String"], input_line)

    def _eval_cls_msg(
        self, class_receiver: SolClass, selector: str, parsed_args: list[SolInst]
    ) -> SolInst:
        """Main function to process messages that are sent to classes ('new','from:','read')"""
        receiver_boss = self._get_boss_cls_name(class_receiver)

        if selector == "new":
            return self._cls_msg_new(class_receiver, receiver_boss, parsed_args)
        if selector == "from:":
            return self._cls_msg_from(class_receiver, receiver_boss, parsed_args)
        if selector == "read":
            return self._cls_msg_read(class_receiver, receiver_boss, parsed_args)

        raise InterpreterError(
            ErrorCode.SEM_UNDEF,
            f"Class {class_receiver.name} DNU the message {selector}",
        )

    def eval_send(self, send_node: Send, curr_frame: LocalFrame) -> SolInst:
        """Processes sending messages"""
        selector = send_node.selector
        logger.info(f"Processing message: {selector}")

        # Check if it's super send, then we have to look for method in parent cls of curr cls
        is_super = send_node.receiver.var is not None and send_node.receiver.var.name == "super"

        # Who is the receiver
        message_receiver = self.eval_expr(send_node.receiver, curr_frame)

        # Now parse all args, which we pass to the method
        parsed_args = []
        for arg in send_node.args:
            # args have expr node
            arg_obj = self.eval_expr(arg.expr, curr_frame)
            parsed_args.append(arg_obj)

        # Search for method in class of receiver
        class_receiver = message_receiver.sol_class
        found_method = None

        # Class messages
        if message_receiver.val == "CLASS_REF":
            return self._eval_cls_msg(class_receiver, selector, parsed_args)

        if is_super:
            # If it's super send we have to look for method in parent class of current class
            if curr_frame.owner_class is None or curr_frame.owner_class.parent_name is None:
                start_cls = None
            else:
                start_cls = self.class_table.get(curr_frame.owner_class.parent_name)
        else:
            # If it's normal send we start looking for method in class of receiver
            start_cls = message_receiver.sol_class

        found_method = None
        method_owner_cls = None
        curr_cls = start_cls

        while curr_cls is not None:
            if curr_cls.ast_node is not None:
                for method in curr_cls.ast_node.methods:
                    if method.selector == selector:
                        found_method = method
                        method_owner_cls = curr_cls
                        break
            if found_method is not None:
                break
            # Move to parent class if method not found in current class
            curr_cls = self.class_table.get(curr_cls.parent_name) if curr_cls.parent_name else None

        # If method in user classes found, we will execute it
        if (
            found_method is not None
            and found_method.block is not None
            and method_owner_cls is not None
        ):
            method_block = found_method.block
            if len(parsed_args) != method_block.arity:
                raise InterpreterError(
                    ErrorCode.INT_OTHER,
                    f"Method {selector} expects {method_block.arity}"
                    "arguments but got {len(parsed_args)}",
                )
            # Create new frame for method execution and save self in it
            method_frame = LocalFrame(owner_class=method_owner_cls)
            method_frame.vars["self"] = message_receiver

            # Save method parameters into method frame
            for param in range(method_block.arity):
                param_name = method_block.parameters[param].name
                method_frame.vars[param_name] = parsed_args[param]
                method_frame.params.add(param_name)

            logger.info(f"===> Accessing method: {method_owner_cls.name}>>{selector}")
            # If method block is empty, self is returned by default
            last_result = message_receiver
            for assign_node in method_block.assigns:
                last_result = self.eval_assign(assign_node, method_frame)
            logger.info(f"<===Leaving method: {method_owner_cls.name}>>{selector}")

            return last_result  # return the last value of last command in method block

        # Parse builtin classes
        builtin_result = self._eval_builtin_send(message_receiver, selector, parsed_args)
        if builtin_result is not None:
            # return the result
            return builtin_result

        # Process it as access to instance attribute (getter/setter) if method not found
        return self._eval_attr_access(message_receiver, selector, parsed_args)
