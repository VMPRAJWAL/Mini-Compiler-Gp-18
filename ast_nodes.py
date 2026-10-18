"""
ast_nodes.py  –  Mini Compiler  (Member 2)
------------------------------------------
Dataclass-based AST nodes shared between the parser (Member 2) and
the code generator (Member 3).

All bodies are plain Python lists of statement nodes.
op is always the literal symbol string: "+", "-", "*", "/",
"==", "!=", "<", ">".

No node exists for parentheses; they affect grouping only and are
resolved during parsing.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Any


# ---------------------------------------------------------------------------
# Statement nodes
# ---------------------------------------------------------------------------

@dataclass
class Program:
    """Root node.  body is a list of statement nodes."""
    body: List[Any] = field(default_factory=list)


@dataclass
class Assign:
    """ID = value"""
    name: str
    value: Any   # expression node


@dataclass
class Print:
    """print value"""
    value: Any   # expression node


@dataclass
class If:
    """if condition then NEWLINE body end"""
    condition: Any          # expression node
    body: List[Any] = field(default_factory=list)


@dataclass
class While:
    """while condition do NEWLINE body end"""
    condition: Any          # expression node
    body: List[Any] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Expression nodes
# ---------------------------------------------------------------------------

@dataclass
class BinOp:
    """Binary operation.
    op is one of: '+', '-', '*', '/', '==', '!=', '<', '>'
    """
    op: str
    left: Any    # expression node
    right: Any   # expression node


@dataclass
class Num:
    """Integer literal.  value is a Python int."""
    value: int


@dataclass
class Var:
    """Variable reference."""
    name: str
