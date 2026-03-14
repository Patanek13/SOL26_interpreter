"""
This module contains the main logic of the interpreter.

IPP: You must definitely modify this file. Bend it to your will.

Author: Ondřej Ondryáš <iondryas@fit.vut.cz>
Author:
"""

import logging
from pathlib import Path
from typing import TextIO

from lxml import etree
from lxml.etree import ParseError
from pydantic import ValidationError

from interpreter.error_codes import ErrorCode
from interpreter.exceptions import InterpreterError
from interpreter.input_model import Assign, ClassDef, Expr, Program

logger = logging.getLogger(__name__)


class SolClass:
    """Representation of SOL26 class in memory"""

    def __init__(self, name: str, parent_name: str | None, ast_node: ClassDef):
        self.name = name
        self.parent_name = parent_name
        self.ast_node = ast_node


class SolInst:
    """Representation of specific object in memory"""

    def __init__(self, sol_class: SolClass):
        self.sol_class = sol_class
        self.attrs: dict[str, SolInst] = {}


class LocalFrame:
    """Represents local variables for blocks or methods"""

    def __init__(self) -> None:
        self.vars: dict[str, SolInst] = {}


class Interpreter:
    """
    The main interpreter class, responsible for loading the source file and executing the program.
    """

    def __init__(self) -> None:
        self.current_program: Program | None = None
        self.class_table: dict[str, SolClass] = {}  # Memory for classes

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

    def execute(self, input_io: TextIO) -> None:
        """
        Executes the currently loaded program, using the provided input stream as standard input.
        """
        logger.info("Executing program")

        # Check for mypy that program is not None
        if self.current_program is None:
            return

        # First we have to fill our tables with all classes
        for ast_class in self.current_program.classes:
            class_name = ast_class.name

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

        # Find run method in Main class
        run_method_node = None
        for method in main_cls_def.ast_node.methods:
            if method.selector == "run":
                run_method_node = method
                break

        # Check for mypy but run should be checked already (defensive programming ig)
        if run_method_node is None:
            raise InterpreterError(
                error_code=ErrorCode.SEM_ERROR, message="Method run or its block is missing"
            )

        # Local frame where we save self as ptr to object on which we call the method
        curr_frame = LocalFrame()
        curr_frame.vars["self"] = main_inst

        logger.info("Start method Main.run")

        # Blocks in method run
        for assign_node in run_method_node.block.assigns:
            self.eval_assign(assign_node, curr_frame)

    def eval_assign(self, assign_node: Assign, curr_frame: LocalFrame) -> None:
        """Evaluates assign cmd and saves result into current frame"""

        # Evaluate the expr (right side)
        final_result = self.eval_expr(assign_node.expr, curr_frame)

        # Track the name of variable
        var_name = assign_node.target.name

        # Save result into local memory (curr_frame), we don't need to save _var
        if var_name == "_":
            logger.info("Assign: not saving result of var '_' ")
        else:
            curr_frame.vars[var_name] = final_result
            logger.info(f"Assign: Saved object into {var_name}")

    def eval_expr(self, expr_node: Expr, curr_fram: LocalFrame) -> SolInst:
        """Evaluates any expression (var, literal, block, send) and returns final object"""
        logger.info("Evaluating expression")

        return SolInst(sol_class=self.class_table["Main"])
