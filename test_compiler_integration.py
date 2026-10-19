import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from compiler import compile_source


ROOT = Path(__file__).parent
EXAMPLES = sorted((ROOT / "examples").glob("*.mc"))
EXPECTED_OUTPUTS = {
    "01_assignment": "10\n3\n",
    "02_arithmetic": "14\n",
    "03_parentheses": "20\n",
    "04_comparisons": "10\n",
    "05_if_else_free": "3\n",
    "06_while": "3\n2\n1\n",
    "07_empty_blocks": "7\n",
    "08_nested_blocks": "2\n",
    "09_multiple_statements": "1\n2\n3\n",
    "10_loop_expression": "4\n",
}


class TestCompilerIntegration(unittest.TestCase):
    def test_all_examples_generate_valid_python(self):
        self.assertEqual(len(EXAMPLES), 10)
        with tempfile.TemporaryDirectory() as directory:
            for source_path in EXAMPLES:
                output_path = Path(directory) / f"{source_path.stem}.py"
                result = subprocess.run(
                    [sys.executable, "compiler.py", str(source_path), "-o", str(output_path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(output_path.exists())
                compile(output_path.read_text(encoding="utf-8"), str(output_path), "exec")
                run_result = subprocess.run(
                    [sys.executable, str(output_path)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(run_result.returncode, 0, run_result.stderr)
                self.assertEqual(run_result.stdout, EXPECTED_OUTPUTS[source_path.stem])

    def test_compiled_program_can_run(self):
        source = "x = 3\nwhile x > 0 do\nprint x\nx = x - 1\nend\n"
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "program.py"
            output_path.write_text(compile_source(source), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(output_path)],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "3\n2\n1\n")

    def test_invalid_programs_fail_gracefully(self):
        invalid_sources = [
            "x = @\n",
            "x =\n",
            "if x\nprint x\nend\n",
            "while x > 0 do\nprint x\n",
            "x = (1 + 2\n",
        ]
        for source in invalid_sources:
            with self.subTest(source=source):
                with tempfile.TemporaryDirectory() as directory:
                    source_path = Path(directory) / "invalid.mc"
                    source_path.write_text(source, encoding="utf-8")
                    result = subprocess.run(
                        [sys.executable, str(ROOT / "compiler.py"), str(source_path)],
                        capture_output=True,
                        text=True,
                    )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("failed", result.stderr)

    def test_cli_run_flag_executes_generated_program(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "program.mc"
            source_path.write_text("print 42\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "compiler.py"), str(source_path), "--run"],
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0)
        self.assertIn("42\n", result.stdout)


if __name__ == "__main__":
    unittest.main()
