"""
lexer.py  -  Stage 1 of the Mini Compiler (Member 1)
A table-driven DFA lexer with maximal munch (longest match).
Output contract: list of (TOKEN_TYPE, TEXT) tuples.
"""
import string

KEYWORDS = {"if", "then", "end", "while", "do", "print"}

LETTERS = set(string.ascii_letters + "_")
DIGITS = set(string.digits)

def char_class(ch):
    if ch in LETTERS: return "LETTER"
    if ch in DIGITS:  return "DIGIT"
    if ch in "+-*/":  return "OPCH"
    return ch          # = ! < > ( ) \n and anything else stand for themselves

# DFA transition table: (state, input class) -> next state
TRANSITIONS = {
    ("START", "LETTER"): "IN_ID",
    ("START", "DIGIT"):  "IN_NUM",
    ("START", "="):      "SAW_EQ",
    ("START", "!"):      "SAW_BANG",
    ("START", "<"):      "SAW_LT",
    ("START", ">"):      "SAW_GT",
    ("START", "OPCH"):   "OP",
    ("START", "("):      "LPAREN",
    ("START", ")"):      "RPAREN",
    ("START", "\n"):     "NEWLINE",
    ("IN_ID", "LETTER"): "IN_ID",
    ("IN_ID", "DIGIT"):  "IN_ID",
    ("IN_NUM", "DIGIT"): "IN_NUM",
    ("SAW_EQ", "="):     "SAW_EQEQ",
    ("SAW_BANG", "="):   "SAW_NEQ",
}

# Accepting states -> token type they produce
ACCEPTING = {
    "IN_ID": "ID", "IN_NUM": "NUM", "SAW_EQ": "ASSIGN", "SAW_EQEQ": "EQ",
    "SAW_NEQ": "NEQ", "SAW_LT": "LT", "SAW_GT": "GT", "OP": "OP",
    "LPAREN": "LPAREN", "RPAREN": "RPAREN", "NEWLINE": "NEWLINE",
}

def lexer(code):
    if not code.endswith("\n"):
        code += "\n"                       # every statement must end with NEWLINE
    tokens = []
    i, line, col, n = 0, 1, 1, len(code)
    while i < n:
        if code[i] in " \t\r":             # skip whitespace
            i += 1; col += 1
            continue
        state, j, last_acc = "START", i, None
        while j < n:                       # run the DFA as far as it can go
            nxt = TRANSITIONS.get((state, char_class(code[j])))
            if nxt is None:
                break
            state = nxt
            j += 1
            if state in ACCEPTING:
                last_acc = (state, j)      # remember the longest accepted match
        if last_acc is None:
            raise SyntaxError(
                f"Lexical error: illegal character {code[i]!r} at line {line}, column {col}")
        acc_state, end = last_acc
        text = code[i:end]
        ttype = ACCEPTING[acc_state]
        if ttype == "ID" and text in KEYWORDS:
            ttype = text.upper()           # keyword check after an ID is recognised
        tokens.append((ttype, text if ttype != "NEWLINE" else ""))
        if ttype == "NEWLINE":
            line += 1; col = 1
        else:
            col += end - i
        i = end
    return tokens

if __name__ == "__main__":
    src = "x = 10\ny = 3\nif x > y then\nz = x + y\nend\nprint z\n"
    print(lexer(src))
