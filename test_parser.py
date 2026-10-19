"""
test_parser.py  –  Mini Compiler  (Member 2)
---------------------------------------------
Unit tests for the recursive-descent parser.

Tests compare complete AST trees using dataclass equality (==).
The test suite uses *only* the standard library (unittest).

Run with:
    python -m unittest -v
"""
import unittest

from lexer import lexer
from parser import parse, ParseError
from ast_nodes import (
    Program, Assign, Print, If, While,
    BinOp, Num, Var,
)


def _parse(src: str) -> Program:
    """Lex then parse a source string."""
    return parse(lexer(src))


# ===========================================================================
# Helpers / smoke
# ===========================================================================

class TestSmoke(unittest.TestCase):
    """Basic sanity – parse returns a Program node."""

    def test_empty_program(self):
        self.assertEqual(_parse(""), Program(body=[]))

    def test_blank_lines_only(self):
        # Multiple blank lines should yield an empty program body
        self.assertEqual(_parse("\n\n\n"), Program(body=[]))


# ===========================================================================
# Assignment
# ===========================================================================

class TestAssign(unittest.TestCase):

    def test_simple_num(self):
        tree = _parse("x = 42\n")
        self.assertEqual(tree, Program(body=[
            Assign(name="x", value=Num(42))
        ]))

    def test_simple_id_rhs(self):
        tree = _parse("y = z\n")
        self.assertEqual(tree, Program(body=[
            Assign(name="y", value=Var("z"))
        ]))

    def test_multiple_assignments(self):
        tree = _parse("a = 1\nb = 2\n")
        self.assertEqual(tree, Program(body=[
            Assign("a", Num(1)),
            Assign("b", Num(2)),
        ]))


# ===========================================================================
# Print
# ===========================================================================

class TestPrint(unittest.TestCase):

    def test_print_num(self):
        tree = _parse("print 7\n")
        self.assertEqual(tree, Program(body=[
            Print(value=Num(7))
        ]))

    def test_print_var(self):
        tree = _parse("print foo\n")
        self.assertEqual(tree, Program(body=[
            Print(value=Var("foo"))
        ]))

    def test_print_expr(self):
        tree = _parse("print 1 + 2\n")
        self.assertEqual(tree, Program(body=[
            Print(value=BinOp("+", Num(1), Num(2)))
        ]))


# ===========================================================================
# Operator precedence
# ===========================================================================

class TestPrecedence(unittest.TestCase):

    def test_mul_binds_tighter_than_add(self):
        # 2 + 3 * 4  ->  2 + (3 * 4)
        tree = _parse("x = 2 + 3 * 4\n")
        expected = Program(body=[
            Assign("x", BinOp("+", Num(2), BinOp("*", Num(3), Num(4))))
        ])
        self.assertEqual(tree, expected)

    def test_mul_left_of_add(self):
        # 3 * 4 + 2  ->  (3 * 4) + 2
        tree = _parse("x = 3 * 4 + 2\n")
        expected = Program(body=[
            Assign("x", BinOp("+", BinOp("*", Num(3), Num(4)), Num(2)))
        ])
        self.assertEqual(tree, expected)

    def test_div_binds_tighter_than_sub(self):
        # 10 - 6 / 2  ->  10 - (6 / 2)
        tree = _parse("x = 10 - 6 / 2\n")
        expected = Program(body=[
            Assign("x", BinOp("-", Num(10), BinOp("/", Num(6), Num(2))))
        ])
        self.assertEqual(tree, expected)


# ===========================================================================
# Left-associativity
# ===========================================================================

class TestLeftAssoc(unittest.TestCase):

    def test_sub_left_assoc(self):
        # 10 - 4 - 3  ->  (10 - 4) - 3
        tree = _parse("x = 10 - 4 - 3\n")
        expected = Program(body=[
            Assign("x", BinOp("-", BinOp("-", Num(10), Num(4)), Num(3)))
        ])
        self.assertEqual(tree, expected)

    def test_add_left_assoc(self):
        # 1 + 2 + 3  ->  (1 + 2) + 3
        tree = _parse("x = 1 + 2 + 3\n")
        expected = Program(body=[
            Assign("x", BinOp("+", BinOp("+", Num(1), Num(2)), Num(3)))
        ])
        self.assertEqual(tree, expected)

    def test_mul_left_assoc(self):
        # 2 * 3 * 4  ->  (2 * 3) * 4
        tree = _parse("x = 2 * 3 * 4\n")
        expected = Program(body=[
            Assign("x", BinOp("*", BinOp("*", Num(2), Num(3)), Num(4)))
        ])
        self.assertEqual(tree, expected)


# ===========================================================================
# Parentheses
# ===========================================================================

class TestParentheses(unittest.TestCase):

    def test_parens_override_precedence(self):
        # (2 + 3) * 4  ->  BinOp('*', BinOp('+', 2, 3), 4)
        tree = _parse("x = (2 + 3) * 4\n")
        expected = Program(body=[
            Assign("x", BinOp("*", BinOp("+", Num(2), Num(3)), Num(4)))
        ])
        self.assertEqual(tree, expected)

    def test_parens_nested(self):
        # ((1 + 2))  ->  just 1+2, no extra node
        tree = _parse("x = ((1 + 2))\n")
        expected = Program(body=[
            Assign("x", BinOp("+", Num(1), Num(2)))
        ])
        self.assertEqual(tree, expected)

    def test_parens_in_arith(self):
        tree = _parse("x = 1 * (y + 2)\n")
        expected = Program(body=[
            Assign("x", BinOp("*", Num(1), BinOp("+", Var("y"), Num(2))))
        ])
        self.assertEqual(tree, expected)


# ===========================================================================
# Comparison operators
# ===========================================================================

class TestComparisons(unittest.TestCase):

    def _cmp(self, op_text: str, op_sym: str):
        src = f"x = a {op_text} b\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            Assign("x", BinOp(op_sym, Var("a"), Var("b")))
        ]))

    def test_eq(self):  self._cmp("==", "==")
    def test_neq(self): self._cmp("!=", "!=")
    def test_lt(self):  self._cmp("<",  "<")
    def test_gt(self):  self._cmp(">",  ">")

    def test_cmp_with_arith_rhs(self):
        # a > b + 1  ->  BinOp('>', Var(a), BinOp('+', Var(b), Num(1)))
        tree = _parse("r = a > b + 1\n")
        expected = Program(body=[
            Assign("r", BinOp(">", Var("a"), BinOp("+", Var("b"), Num(1))))
        ])
        self.assertEqual(tree, expected)

    def test_cmp_in_if_condition(self):
        tree = _parse("if x == 0 then\nprint x\nend\n")
        expected = Program(body=[
            If(
                condition=BinOp("==", Var("x"), Num(0)),
                body=[Print(value=Var("x"))],
            )
        ])
        self.assertEqual(tree, expected)


# ===========================================================================
# If statement
# ===========================================================================

class TestIf(unittest.TestCase):

    def test_simple_if(self):
        src = "if x > 0 then\nprint x\nend\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            If(
                condition=BinOp(">", Var("x"), Num(0)),
                body=[Print(value=Var("x"))],
            )
        ]))

    def test_if_multiple_body_stmts(self):
        src = "if a < b then\nx = 1\ny = 2\nend\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            If(
                condition=BinOp("<", Var("a"), Var("b")),
                body=[
                    Assign("x", Num(1)),
                    Assign("y", Num(2)),
                ],
            )
        ]))

    def test_if_empty_body(self):
        src = "if x > 0 then\nend\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            If(condition=BinOp(">", Var("x"), Num(0)), body=[])
        ]))


# ===========================================================================
# While statement
# ===========================================================================

class TestWhile(unittest.TestCase):

    def test_simple_while(self):
        src = "while x > 0 do\nx = x - 1\nend\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            While(
                condition=BinOp(">", Var("x"), Num(0)),
                body=[Assign("x", BinOp("-", Var("x"), Num(1)))],
            )
        ]))

    def test_while_empty_body(self):
        src = "while n > 0 do\nend\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            While(condition=BinOp(">", Var("n"), Num(0)), body=[])
        ]))


# ===========================================================================
# Nested blocks
# ===========================================================================

class TestNestedBlocks(unittest.TestCase):

    def test_if_inside_while(self):
        src = (
            "while x > 0 do\n"
            "if x > 5 then\n"
            "x = x - 2\n"
            "end\n"
            "x = x - 1\n"
            "end\n"
        )
        tree = _parse(src)
        expected = Program(body=[
            While(
                condition=BinOp(">", Var("x"), Num(0)),
                body=[
                    If(
                        condition=BinOp(">", Var("x"), Num(5)),
                        body=[Assign("x", BinOp("-", Var("x"), Num(2)))],
                    ),
                    Assign("x", BinOp("-", Var("x"), Num(1))),
                ],
            )
        ])
        self.assertEqual(tree, expected)

    def test_while_inside_if(self):
        src = (
            "if flag > 0 then\n"
            "while n > 0 do\n"
            "n = n - 1\n"
            "end\n"
            "end\n"
        )
        tree = _parse(src)
        expected = Program(body=[
            If(
                condition=BinOp(">", Var("flag"), Num(0)),
                body=[
                    While(
                        condition=BinOp(">", Var("n"), Num(0)),
                        body=[Assign("n", BinOp("-", Var("n"), Num(1)))],
                    )
                ],
            )
        ])
        self.assertEqual(tree, expected)


# ===========================================================================
# Blank lines inside / between statements
# ===========================================================================

class TestBlankLines(unittest.TestCase):

    def test_blank_line_between_stmts(self):
        src = "x = 1\n\ny = 2\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            Assign("x", Num(1)),
            Assign("y", Num(2)),
        ]))

    def test_blank_lines_inside_block(self):
        src = "if x > 0 then\n\nx = 1\n\nend\n"
        tree = _parse(src)
        self.assertEqual(tree, Program(body=[
            If(
                condition=BinOp(">", Var("x"), Num(0)),
                body=[Assign("x", Num(1))],
            )
        ]))


# ===========================================================================
# Integration – full program from the spec
# ===========================================================================

class TestIntegration(unittest.TestCase):

    def test_spec_program(self):
        """
        The spec example:
            x = 10
            y = 3
            if x > y then
            z = x + y
            end
            print z
        """
        src = "x = 10\ny = 3\nif x > y then\nz = x + y\nend\nprint z\n"
        tree = _parse(src)
        expected = Program(body=[
            Assign("x", Num(10)),
            Assign("y", Num(3)),
            If(
                condition=BinOp(">", Var("x"), Var("y")),
                body=[
                    Assign("z", BinOp("+", Var("x"), Var("y")))
                ],
            ),
            Print(value=Var("z")),
        ])
        self.assertEqual(tree, expected)

    def test_while_countdown(self):
        src = (
            "x = 5\n"
            "while x > 0 do\n"
            "x = x - 1\n"
            "print x\n"
            "end\n"
        )
        tree = _parse(src)
        expected = Program(body=[
            Assign("x", Num(5)),
            While(
                condition=BinOp(">", Var("x"), Num(0)),
                body=[
                    Assign("x", BinOp("-", Var("x"), Num(1))),
                    Print(value=Var("x")),
                ],
            ),
        ])
        self.assertEqual(tree, expected)


# ===========================================================================
# Error tests
# ===========================================================================

class TestParseErrors(unittest.TestCase):
    """All of these must raise ParseError (a subclass of SyntaxError)."""

    def _assertParseError(self, src: str):
        with self.assertRaises(ParseError):
            _parse(src)

    # -- missing operand --------------------------------------------------

    def test_missing_rhs_operand(self):
        # "x = 2 +"  -> nothing after the operator
        self._assertParseError("x = 2 +\n")

    # -- missing THEN / DO / END ------------------------------------------

    def test_missing_then(self):
        # "if x > 1\n"  -> no THEN
        self._assertParseError("if x > 1\n")

    def test_missing_do(self):
        self._assertParseError("while x > 0\nx = 1\nend\n")

    def test_missing_end_for_if(self):
        # if block never closed
        self._assertParseError("if x > 0 then\nx = 1\n")

    def test_missing_end_for_while(self):
        self._assertParseError("while x > 0 do\nx = 1\n")

    # -- unclosed parenthesis ----------------------------------------------

    def test_unclosed_paren(self):
        self._assertParseError("x = (2 + 3\n")

    # -- unexpected token --------------------------------------------------

    def test_unexpected_token_assign(self):
        # double ASSIGN:  "x = = 3"
        self._assertParseError("x = = 3\n")

    def test_trailing_tokens(self):
        # well-formed statement followed by garbage
        self._assertParseError("x = 1\ny = 2 3\n")

    # -- incomplete statement / unexpected end of input --------------------

    def test_incomplete_statement_eof(self):
        # Feed a raw token list: a syntactically complete assignment but with
        # no terminating NEWLINE token.  The parser must raise ParseError
        # (not accept the statement or raise IndexError/similar).
        # Token stream: ID ASSIGN NUM  (no NEWLINE)
        with self.assertRaises(ParseError):
            parse([("ID", "x"), ("ASSIGN", "="), ("NUM", "1")])

    # -- lexer error passes through as SyntaxError -------------------------

    def test_lexer_error_passthrough(self):
        """
        An illegal character in the source causes the *lexer* to raise
        SyntaxError.  ParseError is a subclass of SyntaxError, so we
        just check for SyntaxError.
        """
        with self.assertRaises(SyntaxError):
            _parse("x = 5 $ 3\n")   # '$' is illegal in the lexer


# ===========================================================================
# Line-number accuracy in error messages
# ===========================================================================

class TestLineNumbers(unittest.TestCase):

    def test_line_number_in_error(self):
        src = "x = 1\ny = 2 +\n"   # error on line 2
        try:
            _parse(src)
            self.fail("ParseError not raised")
        except ParseError as e:
            self.assertIn("Line 2", str(e))

    def test_line_1_error(self):
        src = "x = +\n"             # error on line 1
        try:
            _parse(src)
            self.fail("ParseError not raised")
        except ParseError as e:
            self.assertIn("Line 1", str(e))

    def test_error_after_blank_lines(self):
        src = "\n\nx = 2 +\n"       # two blank lines then error on line 3
        try:
            _parse(src)
            self.fail("ParseError not raised")
        except ParseError as e:
            self.assertIn("Line 3", str(e))


if __name__ == "__main__":
    unittest.main()
