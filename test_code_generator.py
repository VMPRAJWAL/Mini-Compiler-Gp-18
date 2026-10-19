import unittest

from ast_nodes import Assign, BinOp, If, Num, Print, Program, Var, While
from code_generator import generate


class TestCodeGenerator(unittest.TestCase):
    def test_expressions_and_statements(self):
        tree = Program([
            Assign("x", BinOp("+", Num(2), BinOp("*", Num(3), Num(4)))),
            Print(Var("x")),
        ])
        self.assertEqual(
            generate(tree),
            "x = (2 + (3 * 4))\nprint(x)\n",
        )

    def test_nested_blocks_and_empty_blocks(self):
        tree = Program([
            If(BinOp(">", Var("x"), Num(0)), [
                While(BinOp(">", Var("x"), Num(1)), []),
            ])
        ])
        self.assertEqual(
            generate(tree),
            "if (x > 0):\n    while (x > 1):\n        pass\n",
        )

    def test_empty_program(self):
        self.assertEqual(generate(Program()), "")


if __name__ == "__main__":
    unittest.main()
