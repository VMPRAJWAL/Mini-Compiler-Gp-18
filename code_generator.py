"""Generate readable Python source from the mini-compiler AST."""

from __future__ import annotations

from ast_nodes import Assign, BinOp, If, Num, Print, Program, Var, While


class CodeGenerationError(ValueError):
    """Raised when an AST node cannot be converted to Python."""


def _expression(node: object) -> str:
    if isinstance(node, Num):
        return str(node.value)
    if isinstance(node, Var):
        return node.name
    if isinstance(node, BinOp):
        return f"({_expression(node.left)} {node.op} {_expression(node.right)})"
    raise CodeGenerationError(
        f"Unsupported expression node: {type(node).__name__}"
    )


def _statements(statements: list[object], indent: int) -> list[str]:
    lines: list[str] = []
    for statement in statements:
        lines.extend(_statement(statement, indent))
    return lines


def _statement(node: object, indent: int) -> list[str]:
    prefix = " " * indent
    if isinstance(node, Assign):
        return [f"{prefix}{node.name} = {_expression(node.value)}"]
    if isinstance(node, Print):
        return [f"{prefix}print({_expression(node.value)})"]
    if isinstance(node, (If, While)):
        keyword, condition = (
            ("if", node.condition) if isinstance(node, If)
            else ("while", node.condition)
        )
        lines = [f"{prefix}{keyword} {_expression(condition)}:"]
        body = _statements(node.body, indent + 4)
        return lines + (body or [f"{prefix}    pass"])
    raise CodeGenerationError(f"Unsupported statement node: {type(node).__name__}")


def generate(tree: Program) -> str:
    """Return executable Python source for *tree*."""
    if not isinstance(tree, Program):
        raise CodeGenerationError(
            f"Expected Program root, got {type(tree).__name__}"
        )
    lines = _statements(tree.body, 0)
    return "\n".join(lines) + ("\n" if lines else "")
