"""A strict parser for first-order TPTP (fof/cnf).

Only this subset reaches the provers, re-serialised from the syntax tree, so
`include` directives, file paths, prover options or other unexpected text in
user input can never be passed to a prover.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fvp.tptp.ast import (
    ROLES,
    Atom,
    Binary,
    Equality,
    Fn,
    Formula,
    Not,
    Problem,
    Quantified,
    Statement,
    Term,
    Truth,
    Var,
    free_variables,
)

MAX_SOURCE_CHARS = 65_536
MAX_STATEMENTS = 1_000
MAX_DEPTH = 200
MAX_TOKENS = 50_000


class TPTPSyntaxError(ValueError):
    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"line {line}, column {column}: {message}")
        self.message = message
        self.line = line
        self.column = column


@dataclass(frozen=True)
class Token:
    kind: str
    text: str
    line: int
    column: int


_TOKEN_SPEC = [
    ("WS", r"[ \t\r\n]+"),
    ("LINE_COMMENT", r"%[^\n]*"),
    ("BLOCK_COMMENT", r"/\*.*?\*/"),
    ("OP", r"<~>|<=>|=>|<=|~\||~&|!=|[(),.\[\]:!?~&|=]"),
    ("DOLLAR", r"\$[a-z][A-Za-z0-9_]*"),
    ("LOWER", r"[a-z][A-Za-z0-9_]*"),
    ("UPPER", r"[A-Z][A-Za-z0-9_]*"),
    ("INT", r"[0-9]+"),
]
_TOKEN_RE = re.compile("|".join(f"(?P<{k}>{p})" for k, p in _TOKEN_SPEC), re.DOTALL)
_BINARY_OPS = {"&", "|", "=>", "<=", "<=>", "<~>", "~|", "~&"}
_ASSOCIATIVE = {"&", "|"}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    line, line_start, pos = 1, 0, 0
    while pos < len(source):
        match = _TOKEN_RE.match(source, pos)
        if match is None:
            char = source[pos]
            if source.startswith("/*", pos):
                raise TPTPSyntaxError("unterminated comment", line, pos - line_start + 1)
            shown = char if char.isprintable() else repr(char)
            raise TPTPSyntaxError(f"unexpected character {shown!r}", line, pos - line_start + 1)
        kind, text = match.lastgroup or "", match.group()
        if kind not in ("WS", "LINE_COMMENT", "BLOCK_COMMENT"):
            tokens.append(Token(kind, text, line, pos - line_start + 1))
            if len(tokens) > MAX_TOKENS:
                raise TPTPSyntaxError("problem is too large", line, 1)
        newlines = text.count("\n")
        if newlines:
            line += newlines
            line_start = match.start() + text.rfind("\n") + 1
        pos = match.end()
    tokens.append(Token("EOF", "", line, pos - line_start + 1))
    return tokens


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.depth = 0

    # ----------------------------------------------------------- helpers
    @property
    def tok(self) -> Token:
        return self.tokens[self.pos]

    def error(self, message: str, token: Token | None = None) -> TPTPSyntaxError:
        token = token or self.tok
        return TPTPSyntaxError(message, token.line, token.column)

    def advance(self) -> Token:
        token = self.tok
        self.pos += 1
        return token

    def expect(self, text: str) -> Token:
        if self.tok.text != text or self.tok.kind not in ("OP",):
            found = self.tok.text or "end of input"
            raise self.error(f"expected '{text}' but found '{found}'")
        return self.advance()

    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise self.error("formula is nested too deeply")

    def leave(self) -> None:
        self.depth -= 1

    # --------------------------------------------------------- top level
    def problem(self) -> Problem:
        statements: list[Statement] = []
        while self.tok.kind != "EOF":
            start = self.tok
            if start.kind != "LOWER":
                raise self.error("expected fof(...) or cnf(...)")
            if start.text == "include":
                raise self.error("include directives are not allowed; paste the axioms instead")
            if start.text not in ("fof", "cnf"):
                raise self.error(f"'{start.text}' is not supported; use fof or cnf (first-order TPTP)")
            statements.append(self.statement())
            if len(statements) > MAX_STATEMENTS:
                raise self.error(f"too many formulas (maximum {MAX_STATEMENTS})")
        if not statements:
            raise TPTPSyntaxError("the problem contains no formulas", 1, 1)
        conjectures = [s for s in statements if s.role == "conjecture"]
        if len(conjectures) > 1:
            raise TPTPSyntaxError("only one conjecture is allowed per problem", conjectures[1].line, 1)
        return Problem(tuple(statements))

    def statement(self) -> Statement:
        language_token = self.advance()
        language = language_token.text
        self.expect("(")
        name_token = self.advance()
        if name_token.kind not in ("LOWER", "INT"):
            raise self.error("formula names must be lower-case words or integers", name_token)
        self.expect(",")
        role_token = self.advance()
        if role_token.kind != "LOWER" or role_token.text not in ROLES:
            raise self.error(f"unsupported role '{role_token.text}'", role_token)
        if language == "cnf" and role_token.text == "conjecture":
            raise self.error("cnf formulas cannot be conjectures; use negated_conjecture", role_token)
        self.expect(",")
        formula = self.cnf_formula() if language == "cnf" else self.fof_formula()
        if self.tok.text == ",":
            raise self.error("annotations after the formula are not supported")
        self.expect(")")
        self.expect(".")
        if language == "fof":
            free = free_variables(formula)
            if free:
                raise self.error(
                    f"fof formula '{name_token.text}' has unquantified variable(s): {', '.join(free)}", name_token
                )
        return Statement(language, name_token.text, role_token.text, formula, language_token.line)  # type: ignore[arg-type]

    # ---------------------------------------------------------------- FOF
    def fof_formula(self) -> Formula:
        self.enter()
        left = self.unitary()
        if self.tok.kind == "OP" and self.tok.text in _BINARY_OPS:
            op = self.advance().text
            right = self.unitary()
            result: Formula = Binary(op, left, right)  # type: ignore[arg-type]
            if op in _ASSOCIATIVE:
                while self.tok.text == op:
                    self.advance()
                    result = Binary(op, result, self.unitary())  # type: ignore[arg-type]
            if self.tok.kind == "OP" and self.tok.text in _BINARY_OPS:
                raise self.error("mixed connectives need parentheses")
            left = result
        self.leave()
        return left

    def unitary(self) -> Formula:
        self.enter()
        token = self.tok
        if token.text in ("!", "?") and token.kind == "OP":
            self.advance()
            self.expect("[")
            variables = [self.variable_name()]
            while self.tok.text == ",":
                self.advance()
                variables.append(self.variable_name())
            self.expect("]")
            self.expect(":")
            result: Formula = Quantified(token.text, tuple(variables), self.unitary())  # type: ignore[arg-type]
        elif token.text == "~" and token.kind == "OP":
            self.advance()
            result = Not(self.unitary())
        elif token.text == "(" and token.kind == "OP":
            self.advance()
            result = self.fof_formula()
            self.expect(")")
        else:
            result = self.atomic()
        self.leave()
        return result

    def variable_name(self) -> str:
        token = self.advance()
        if token.kind != "UPPER":
            raise self.error("expected a variable (starts with an upper-case letter)", token)
        return token.text

    # ---------------------------------------------------------------- CNF
    def cnf_formula(self) -> Formula:
        if self.tok.text == "(":
            self.advance()
            result = self.disjunction()
            self.expect(")")
            return result
        return self.disjunction()

    def disjunction(self) -> Formula:
        result = self.literal()
        while self.tok.text == "|":
            self.advance()
            result = Binary("|", result, self.literal())
        return result

    def literal(self) -> Formula:
        if self.tok.text == "~":
            self.advance()
            return Not(self.atomic())
        return self.atomic()

    # ------------------------------------------------------ atoms & terms
    def atomic(self) -> Formula:
        token = self.tok
        if token.kind == "DOLLAR":
            self.advance()
            if token.text == "$true":
                return Truth(True)
            if token.text == "$false":
                return Truth(False)
            raise self.error(f"'{token.text}' is not supported", token)
        if token.kind not in ("LOWER", "UPPER"):
            found = token.text or "end of input"
            raise self.error(f"expected a formula but found '{found}'")
        left = self.term()
        if self.tok.text in ("=", "!="):
            negated = self.advance().text == "!="
            return Equality(left, self.term(), negated)
        if isinstance(left, Var):
            raise self.error("a variable cannot be used as a formula", token)
        return Atom(left.name, left.args)

    def term(self) -> Term:
        self.enter()
        token = self.advance()
        if token.kind == "UPPER":
            self.leave()
            return Var(token.text)
        if token.kind != "LOWER":
            found = token.text or "end of input"
            raise self.error(f"expected a term but found '{found}'", token)
        args: list[Term] = []
        if self.tok.text == "(":
            self.advance()
            args.append(self.term())
            while self.tok.text == ",":
                self.advance()
                args.append(self.term())
            self.expect(")")
        self.leave()
        return Fn(token.text, tuple(args))


_INCLUDE = re.compile(r"^[ \t]*include[ \t]*\(", re.MULTILINE)


def parse(source: str) -> Problem:
    if len(source) > MAX_SOURCE_CHARS:
        raise TPTPSyntaxError(f"problem is larger than {MAX_SOURCE_CHARS} characters", 1, 1)
    include = _INCLUDE.search(source)
    if include:  # give a clear message even though the tokenizer would also reject it
        line = source.count("\n", 0, include.start()) + 1
        raise TPTPSyntaxError("include directives are not allowed; paste the axioms instead", line, 1)
    return _Parser(tokenize(source)).problem()
