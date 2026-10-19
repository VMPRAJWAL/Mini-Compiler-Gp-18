"""Command-line compiler for the mini-language."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from code_generator import generate
from lexer import lexer
from parser import parse


def compile_source(source: str) -> str:
    """Lex, parse, and generate Python for a source string."""
    return generate(parse(lexer(source)))


def compile_file(source_path: Path, output_path: Path) -> str:
    """Compile *source_path*, write Python to *output_path*, and return it."""
    source = source_path.read_text(encoding="utf-8")
    generated = compile_source(source)
    output_path.write_text(generated, encoding="utf-8")
    return generated


def main(argv: list[str] | None = None) -> int:
    argument_parser = argparse.ArgumentParser(
        description="Compile mini-language source into Python."
    )
    argument_parser.add_argument("source", type=Path, help="Input .mc source file")
    argument_parser.add_argument(
        "-o", "--output", type=Path, help="Generated Python output path"
    )
    argument_parser.add_argument(
        "--run", action="store_true", help="Run generated Python after compilation"
    )
    args = argument_parser.parse_args(argv)
    output_path = args.output or args.source.with_suffix(".py")

    try:
        compile_file(args.source, output_path)
        print(f"Generated Python written to {output_path}")
        if args.run:
            completed = subprocess.run([sys.executable, str(output_path)], check=False)
            return completed.returncode
    except (OSError, SyntaxError, ValueError) as error:
        print(f"Compilation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
