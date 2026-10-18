"""
parser.py  –  Mini Compiler  (Member 2)
----------------------------------------
Hand-written recursive-descent parser.

Public API
----------
    from parser import parse, ParseError
    from lexer  import lexer

    tokens = lexer(source_code)   # Member 1's lexer
    tree   = parse(tokens)        # returns ast_nodes.Program

Grammar implemented
-------------------
    program   -> (NEWLINE | statement)*
    statement -> ID ASSIGN expr NEWLINE
               | PRINT expr NEWLINE
               | IF expr THEN NEWLINE block END NEWLINE
               | WHILE expr DO NEWLINE block END NEWLINE
    block     -> (NEWLINE | statement)*     # stops when END is the lookahead
    expr      -> arith ((EQ|NEQ|LT|GT) arith)?     # no chaining
    arith     -> term (OP[+,-] term)*               # left-associative
    term      -> factor (OP[*,/] factor)*           # left-associative
    factor    -> NUM | ID | LPAREN expr RPAREN

Error messages always include:
    - what was expected
    - what was found (type + text)
    - the 1-based line number (1 + number of NEWLINE tokens before the
      error position in the token list)
"""

from ast_nodes import (
    Program, Assign, Print, If, While,
    BinOp, Num, Var,
)

# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------

class ParseError(SyntaxError):
    """Raised for any syntactic error detected by the parser."""


# ---------------------------------------------------------------------------
# Internal parser implementation
# ---------------------------------------------------------------------------

_CMP_OPS  = {"EQ", "NEQ", "LT", "GT"}          # token types that are comparison ops
_ADD_OPS  = {"+", "-"}                          # OP token text values for additive
_MUL_OPS  = {"*", "/"}                          # OP token text values for multiplicative

# Maps comparison token type to operator symbol used in BinOp
_CMP_TYPE_TO_SYM = {"EQ": "==", "NEQ": "!=", "LT": "<", "GT": ">"}


class _Parser:
    """
    One-shot parser instance.  Create with a token list; call .parse().

    Tokens are (TYPE, TEXT) tuples exactly as returned by lexer.lexer().
    """

    def __init__(self, tokens: list):
        self._tokens = tokens
        self._pos    = 0                 # index of the current token

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _line(self, pos: int = None) -> int:
        """Return 1-based line number at position pos (default: current)."""
        if pos is None:
            pos = self._pos
        # Count how many NEWLINE tokens appear *before* this position.
        return 1 + sum(1 for i in range(min(pos, len(self._tokens)))
                       if self._tokens[i][0] == "NEWLINE")

    def _peek(self) -> tuple:
        """Current token (TYPE, TEXT), or ('EOF', '') if exhausted."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return ("EOF", "")

    def _peek_type(self) -> str:
        return self._peek()[0]

    def _advance(self) -> tuple:
        """Consume and return the current token."""
        tok = self._peek()
        self._pos += 1
        return tok

    def _expect(self, ttype: str) -> tuple:
        """
        Consume the current token asserting it has type *ttype*.
        Raises ParseError with line number on mismatch or EOF.
        """
        tok = self._peek()
        if tok[0] != ttype:
            raise ParseError(
                f"Line {self._line()}: expected {ttype!r}, "
                f"got {tok[0]!r} ({tok[1]!r})"
            )
        self._pos += 1
        return tok

    def _error(self, msg: str) -> ParseError:
        """Build a ParseError pinned to the current position."""
        tok = self._peek()
        return ParseError(
            f"Line {self._line()}: {msg} (got {tok[0]!r} {tok[1]!r})"
        )

    # ------------------------------------------------------------------
    # Grammar rules  (one method per rule)
    # ------------------------------------------------------------------

    def parse(self) -> Program:
        """Entry point: program -> (NEWLINE | statement)*"""
        body = self._parse_block(stop_at=None)
        # After the full program there should be nothing left.
        if self._peek_type() != "EOF":
            tok = self._peek()
            raise ParseError(
                f"Line {self._line()}: unexpected token {tok[0]!r} ({tok[1]!r}) "
                f"after end of program"
            )
        return Program(body=body)

    def _parse_block(self, stop_at) -> list:
        """
        block -> (NEWLINE | statement)*

        Reads statements until:
          - stop_at token type is the lookahead  (e.g. 'END')
          - EOF

        stop_at=None means only stop at EOF (used for the top-level program).
        """
        stmts = []
        while True:
            tt = self._peek_type()
            if tt == "EOF":
                break
            if stop_at is not None and tt == stop_at:
                break
            if tt == "NEWLINE":
                self._advance()          # blank line – skip silently
                continue
            stmts.append(self._parse_statement())
        return stmts

    def _parse_statement(self) -> object:
        """
        statement -> ID ASSIGN expr NEWLINE
                   | PRINT expr NEWLINE
                   | IF expr THEN NEWLINE block END NEWLINE
                   | WHILE expr DO NEWLINE block END NEWLINE
        """
        tt, text = self._peek()

        if tt == "ID":
            return self._parse_assign()
        elif tt == "PRINT":
            return self._parse_print()
        elif tt == "IF":
            return self._parse_if()
        elif tt == "WHILE":
            return self._parse_while()
        else:
            raise ParseError(
                f"Line {self._line()}: expected a statement "
                f"(ID, PRINT, IF, or WHILE), got {tt!r} ({text!r})"
            )

    # -- assign -------------------------------------------------------

    def _parse_assign(self) -> Assign:
        """ID ASSIGN expr NEWLINE"""
        id_tok = self._expect("ID")
        self._expect("ASSIGN")
        value = self._parse_expr()
        self._expect_newline("assignment")
        return Assign(name=id_tok[1], value=value)

    # -- print --------------------------------------------------------

    def _parse_print(self) -> Print:
        """PRINT expr NEWLINE"""
        self._expect("PRINT")
        value = self._parse_expr()
        self._expect_newline("print statement")
        return Print(value=value)

    # -- if -----------------------------------------------------------

    def _parse_if(self) -> If:
        """IF expr THEN NEWLINE block END NEWLINE"""
        self._expect("IF")
        condition = self._parse_expr()
        self._expect("THEN")
        self._expect_newline("if header")
        body = self._parse_block(stop_at="END")
        if self._peek_type() == "EOF":
            raise ParseError(
                f"Line {self._line()}: 'end' expected to close 'if' block, "
                f"got end-of-input"
            )
        self._expect("END")
        self._expect_newline("if statement")
        return If(condition=condition, body=body)

    # -- while --------------------------------------------------------

    def _parse_while(self) -> While:
        """WHILE expr DO NEWLINE block END NEWLINE"""
        self._expect("WHILE")
        condition = self._parse_expr()
        self._expect("DO")
        self._expect_newline("while header")
        body = self._parse_block(stop_at="END")
        if self._peek_type() == "EOF":
            raise ParseError(
                f"Line {self._line()}: 'end' expected to close 'while' block, "
                f"got end-of-input"
            )
        self._expect("END")
        self._expect_newline("while statement")
        return While(condition=condition, body=body)

    # -- expr ---------------------------------------------------------

    def _parse_expr(self) -> object:
        """expr -> arith ((EQ|NEQ|LT|GT) arith)?   (no chaining)"""
        left = self._parse_arith()
        tt = self._peek_type()
        if tt in _CMP_OPS:
            op_tok = self._advance()
            right = self._parse_arith()
            sym = _CMP_TYPE_TO_SYM[op_tok[0]]
            return BinOp(op=sym, left=left, right=right)
        return left

    # -- arith --------------------------------------------------------

    def _parse_arith(self) -> object:
        """arith -> term (OP[+,-] term)*   left-associative"""
        left = self._parse_term()
        while True:
            tok = self._peek()
            if tok[0] == "OP" and tok[1] in _ADD_OPS:
                self._advance()
                right = self._parse_term()
                left = BinOp(op=tok[1], left=left, right=right)
            else:
                break
        return left

    # -- term ---------------------------------------------------------

    def _parse_term(self) -> object:
        """term -> factor (OP[*,/] factor)*   left-associative"""
        left = self._parse_factor()
        while True:
            tok = self._peek()
            if tok[0] == "OP" and tok[1] in _MUL_OPS:
                self._advance()
                right = self._parse_factor()
                left = BinOp(op=tok[1], left=left, right=right)
            else:
                break
        return left

    # -- factor -------------------------------------------------------

    def _parse_factor(self) -> object:
        """factor -> NUM | ID | LPAREN expr RPAREN"""
        tok = self._peek()
        tt, text = tok

        if tt == "NUM":
            self._advance()
            return Num(value=int(text))

        if tt == "ID":
            self._advance()
            return Var(name=text)

        if tt == "LPAREN":
            self._advance()                   # consume '('
            node = self._parse_expr()
            if self._peek_type() != "RPAREN":
                raise ParseError(
                    f"Line {self._line()}: unclosed parenthesis, "
                    f"expected ')' but got {self._peek_type()!r} "
                    f"({self._peek()[1]!r})"
                )
            self._advance()                   # consume ')'
            return node

        # Nothing matched – we have a missing / unexpected primary
        if tt == "EOF":
            raise ParseError(
                f"Line {self._line()}: unexpected end of input; "
                f"expected a number, identifier, or '('"
            )
        raise ParseError(
            f"Line {self._line()}: expected a number, identifier, or '(', "
            f"got {tt!r} ({text!r})"
        )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _expect_newline(self, ctx: str):
        """
        Expect a NEWLINE token as a statement terminator.
        If the next token is not NEWLINE, raise ParseError.

        EOF is *not* a valid substitute: a missing trailing newline is a
        syntax error.
        """
        tt = self._peek_type()
        if tt == "NEWLINE":
            self._advance()
        elif tt == "EOF":
            raise ParseError(
                f"Line {self._line()}: unexpected end of input, expected NEWLINE"
            )
        else:
            tok = self._peek()
            raise ParseError(
                f"Line {self._line()}: expected end of line after {ctx}, "
                f"got {tok[0]!r} ({tok[1]!r})"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(tokens: list) -> Program:
    """
    Parse a token list produced by lexer.lexer() and return a Program node.

    Raises
    ------
    ParseError  – on any syntactic error detected by the parser.
    SyntaxError – if the token list itself came from a lexer error
                  (the lexer raises SyntaxError before we even see it,
                  but we document the contract here for clarity).
    """
    return _Parser(tokens).parse()
