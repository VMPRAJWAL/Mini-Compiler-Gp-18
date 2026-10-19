# Mini Compiler Gp 18

A small educational compiler implemented in Python. The project translates a
simple line-oriented language into tokens, builds a dataclass-based abstract
syntax tree (AST), generates executable Python, and includes an HTML pipeline
visualizer for inspecting each stage.

The current implementation focuses on:

1. Lexical analysis using a table-driven deterministic finite automaton (DFA).
2. Recursive-descent parsing with operator precedence and nested blocks.
3. AST construction using Python dataclasses.
4. Python code generation from the AST.
5. Error reporting with the unexpected token and source line number.
6. Visual inspection of every pipeline stage.

## Requirements

- Python 3.10 or newer
- No third-party Python packages

The project uses only the Python standard library. A virtual environment is
optional.

## Quick start

Clone the repository and run the test suite:

```bash
git clone https://github.com/VMPRAJWAL/Mini-Compiler-Gp-18.git
cd Mini-Compiler-Gp-18
python -m unittest -v
```

On systems where `python` refers to Python 2, use `python3` instead.

## How to write, compile, and run a program

### 1. Create a source file

Write a mini-language program in a file with a `.mc` extension, for example
`program.mc`:

```text
x = 5
while x > 0 do
    print x
    x = x - 1
end
```

### 2. Compile the source to Python

The compiler runs the complete pipeline:

```text
program.mc -> lexer -> tokens -> parser -> AST -> generated Python
```

Compile a source file with:

```bash
python compiler.py program.mc -o program.py
```

If `-o` is omitted, the compiler writes `program.py` next to `program.mc`.
The generated file is ordinary Python and can be run with:

```bash
python program.py
```

You can also compile and run in one explicit command:

```bash
python compiler.py program.mc --run
```

Invalid characters produce a lexer error; invalid syntax produces a parser
error with the source line number. Compilation failures return a non-zero
exit code.

### 3. Visualize the pipeline

To inspect the source, tokens, parser result, and AST in a browser:

```bash
python pipeline_visualizer.py program.mc --open
```

The visualizer writes an HTML report and displays the generated Python. It
does not execute code; use `compiler.py --run` or run the generated `.py` file
explicitly.

## Mini-language reference

### Statements

The language supports assignments, output, conditionals, and loops:

```text
x = 10
y = 3
print x

if x > y then
    print x
end

while x > 0 do
    x = x - 1
end
```

Supported statements:

```text
identifier = expression
print expression
if expression then
    ...statements...
end
while expression do
    ...statements...
end
```

Blank lines are accepted between statements and inside blocks. Every
statement is terminated by a newline. The lexer adds a final newline when the
input string does not already end with one.

### Expressions

The expression syntax supports:

- Integer literals, such as `0`, `42`, and `100`
- Identifiers containing letters, digits, and underscores
- Parentheses
- Arithmetic operators: `+`, `-`, `*`, `/`
- Comparisons: `==`, `!=`, `<`, `>`

Operator precedence is:

1. Parentheses
2. Multiplication and division
3. Addition and subtraction
4. Comparisons

Arithmetic operators are left-associative. For example:

```text
x = 2 + 3 * 4       # 2 + (3 * 4)
y = 10 - 4 - 3      # (10 - 4) - 3
z = (2 + 3) * 4     # parentheses override precedence
```

The parser accepts at most one comparison operator in an expression; chained
comparisons such as `a < b < c` are not part of the current grammar.

## Technical architecture

The compiler is organized as a pipeline:

```text
source text
    |
    v
lexer.py
    |  list of (TOKEN_TYPE, TEXT) tuples
    v
parser.py
    |  ast_nodes.Program
    v
abstract syntax tree
    |
    v
code_generator.py
    |  generated Python
    v
compiler.py / Python interpreter
```

### Lexical analysis

[lexer.py](./lexer.py) implements a table-driven DFA. It scans the input using
maximal munch, meaning it keeps the longest accepted token at each position.
It recognizes:

- Keywords: `if`, `then`, `end`, `while`, `do`, `print`
- Identifiers
- Integer literals
- Assignment and comparison operators
- Arithmetic operators
- Parentheses
- Newlines

The public API is:

```python
from lexer import lexer

tokens = lexer("x = 2 + 3\n")
print(tokens)
```

The result is a list such as:

```python
[
    ("ID", "x"),
    ("ASSIGN", "="),
    ("NUM", "2"),
    ("OP", "+"),
    ("NUM", "3"),
    ("NEWLINE", ""),
]
```

Illegal characters raise `SyntaxError` with the line and column where the
problem was found.

### Parsing

[parser.py](./parser.py) implements a hand-written recursive-descent parser.
Each grammar rule has a corresponding parser method. The parser builds an AST
while it consumes the token list; it does not retain punctuation such as
parentheses in the AST.

The public API is:

```python
from lexer import lexer
from parser import parse

tree = parse(lexer("x = 2 + 3\n"))
print(tree)
```

Syntax errors raise `ParseError`, which is a subclass of `SyntaxError`.
Messages include:

- The expected construct
- The token type and text that were found
- The one-based source line number

### Code generation

[code_generator.py](./code_generator.py) walks the AST and emits readable,
executable Python. Arithmetic and comparison expressions are parenthesized to
preserve AST grouping. Empty `if` and `while` blocks receive `pass` so the
generated file remains valid Python.

```python
from code_generator import generate
from lexer import lexer
from parser import parse

python_source = generate(parse(lexer("x = 2 + 3\nprint x\n")))
print(python_source)
```

### Compiler API and CLI

[compiler.py](./compiler.py) composes lexing, parsing, and code generation:

```python
from compiler import compile_source

python_source = compile_source("x = 2 + 3\nprint x\n")
```

The CLI writes generated Python and only runs it when `--run` is explicitly
provided.

### Grammar

The parser implements the following grammar:

```text
program   -> (NEWLINE | statement)*
statement -> ID ASSIGN expr NEWLINE
           | PRINT expr NEWLINE
           | IF expr THEN NEWLINE block END NEWLINE
           | WHILE expr DO NEWLINE block END NEWLINE
block     -> (NEWLINE | statement)*
expr      -> arith ((EQ | NEQ | LT | GT) arith)?
arith     -> term (OP[+,-] term)*
term      -> factor (OP[*,/] factor)*
factor    -> NUM | ID | LPAREN expr RPAREN
```

### AST model

[ast_nodes.py](./ast_nodes.py) defines the AST with standard-library
`dataclasses`:

- `Program(body)`
- `Assign(name, value)`
- `Print(value)`
- `If(condition, body)`
- `While(condition, body)`
- `BinOp(op, left, right)`
- `Num(value)`
- `Var(name)`

For example, `x = 2 + 3` becomes conceptually:

```text
Program
`- Assign: x
   `- BinOp: +
      |- Num: 2
      `- Num: 3
```

## Pipeline visualizer

[pipeline_visualizer.py](./pipeline_visualizer.py) creates a self-contained
HTML report containing:

- The original source text
- The token table generated by the lexer
- Lexer and parser status badges
- Generated Python source and code-generation status
- Parser error messages, when applicable
- A text representation and SVG diagram of the AST

Create a source file, for example `program.mc`:

```text
x = 5
while x > 0 do
    print x
    x = x - 1
end
```

Generate the report:

```bash
python pipeline_visualizer.py program.mc
```

By default, the report is written to the system temporary directory as
`mini-compiler-pipeline.html`. Choose an output file with `-o`:

```bash
python pipeline_visualizer.py program.mc -o pipeline.html
```

Generate the report and open it in the default browser:

```bash
python pipeline_visualizer.py program.mc --open
```

The visualizer can also be embedded in another Python program:

```python
from pipeline_visualizer import render_pipeline

html = render_pipeline("x = 2 + 3\nprint x\n")
with open("pipeline.html", "w", encoding="utf-8") as report:
    report.write(html)
```

Invalid input is shown in the report rather than causing the visualizer to
terminate without a result. A lexer error blocks parsing; a parser error is
shown alongside the successfully generated token table.

## Testing

Run all tests:

```bash
python -m unittest -v
```

The test suite uses only `unittest` and covers:

- Empty programs and blank lines
- Assignments and print statements
- Arithmetic precedence
- Left associativity
- Parenthesized expressions
- Comparisons
- Nested `if` and `while` blocks
- Missing or unexpected tokens
- Lexer error propagation
- Visualizer success and error states
- Code-generation output and compiler CLI behavior
- Ten example programs compiled and executed end-to-end
- Graceful diagnostics for invalid source programs

Run only the parser tests:

```bash
python -m unittest -v test_parser
```

Run compiler and integration tests:

```bash
python -m unittest -v test_code_generator test_compiler_integration
```

The ten end-to-end programs are stored in the
[examples/](./examples/) directory.

Run only the visualizer tests:

```bash
python -m unittest -v test_pipeline_visualizer
```

## Repository layout

```text
.
├── ast_nodes.py                 AST dataclasses
├── lexer.py                     DFA-based lexical analyzer
├── parser.py                    Recursive-descent parser
├── code_generator.py            AST-to-Python code generator
├── compiler.py                  Compiler API and CLI
├── pipeline_visualizer.py       HTML pipeline and AST visualizer
├── examples/                    Ten end-to-end source programs
├── test_parser.py               Parser and lexer integration tests
├── test_code_generator.py       Code-generation unit tests
├── test_compiler_integration.py Compiler CLI and end-to-end tests
├── test_pipeline_visualizer.py  Visualizer tests
└── README.md                    Project documentation
```

## Current scope

This repository implements a complete educational compiler pipeline:
lexing, parsing and AST construction, and Python code generation. It does not
generate native machine code; Python is the target language for generated
programs. The generated Python is executed only when explicitly requested with
`compiler.py --run` or by running the generated `.py` file.
