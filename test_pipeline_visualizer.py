import unittest

from pipeline_visualizer import render_pipeline


class TestPipelineVisualizer(unittest.TestCase):
    def test_successful_pipeline_contains_all_stages(self):
        page = render_pipeline("x = 2 + 3\nprint x\n")
        self.assertIn("Mini Compiler Pipeline", page)
        self.assertIn("Source", page)
        self.assertIn("Lexer", page)
        self.assertIn("Parser", page)
        self.assertIn("Generated Python", page)
        self.assertIn("AST", page)
        self.assertIn("BinOp: +", page)
        self.assertIn("print(x)", page)
        self.assertIn('class="badge ok">success', page)

    def test_lexer_error_is_visible(self):
        page = render_pipeline("x = @\n")
        self.assertIn("Lexical error", page)
        self.assertIn('class="badge error">error', page)
        self.assertIn('class="badge blocked">blocked', page)
        self.assertIn("Waiting for a valid AST", page)

    def test_parser_error_is_visible(self):
        page = render_pipeline("if x then\n")
        self.assertIn("expected", page)
        self.assertIn('class="badge error">error', page)


if __name__ == "__main__":
    unittest.main()
