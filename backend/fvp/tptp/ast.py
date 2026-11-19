"""Abstract syntax for the first-order TPTP subset the platform accepts (FOF and CNF)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

BinaryOp = Literal["&", "|", "=>", "<=", "<=>", "<~>", "~|", "~&"]
Quantifier = Literal["!", "?"]


@dataclass(frozen=True)
class Var:
    name: str


@dataclass(frozen=True)
class Fn:
    """A function or constant symbol applied to arguments (constants have no args)."""

    name: str
    args: tuple[Term, ...] = ()


Term = Var | Fn


@dataclass(frozen=True)
class Atom:
    predicate: str
    args: tuple[Term, ...] = ()


@dataclass(frozen=True)
class Equality:
    left: Term
    right: Term
    negated: bool = False


@dataclass(frozen=True)
class Truth:
    value: bool


@dataclass(frozen=True)
class Not:
    body: Formula


@dataclass(frozen=True)
class Binary:
    op: BinaryOp
    left: Formula
    right: Formula


@dataclass(frozen=True)
class Quantified:
    quantifier: Quantifier
    variables: tuple[str, ...]
    body: Formula


Formula = Atom | Equality | Truth | Not | Binary | Quantified

AXIOM_ROLES = frozenset(
    {"axiom", "hypothesis", "definition", "assumption", "lemma", "theorem", "corollary", "plain", "unknown"}
)
ROLES = AXIOM_ROLES | {"conjecture", "negated_conjecture"}


@dataclass(frozen=True)
class Statement:
    language: Literal["fof", "cnf"]
    name: str
    role: str
    formula: Formula
    line: int


@dataclass(frozen=True)
class Problem:
    statements: tuple[Statement, ...]

    @property
    def conjecture(self) -> Statement | None:
        return next((s for s in self.statements if s.role == "conjecture"), None)

    @property
    def has_goal(self) -> bool:
        """True if the problem asks to prove something (a conjecture or a negated one)."""
        return any(s.role in ("conjecture", "negated_conjecture") for s in self.statements)

    def symbols(self) -> dict[str, set[tuple[str, int]]]:
        functions: set[tuple[str, int]] = set()
        predicates: set[tuple[str, int]] = set()

        def term(t: Term) -> None:
            if isinstance(t, Fn):
                functions.add((t.name, len(t.args)))
                for arg in t.args:
                    term(arg)

        stack: list[Formula] = [s.formula for s in self.statements]
        while stack:
            f = stack.pop()
            if isinstance(f, Atom):
                predicates.add((f.predicate, len(f.args)))
                for arg in f.args:
                    term(arg)
            elif isinstance(f, Equality):
                term(f.left)
                term(f.right)
            elif isinstance(f, Not):
                stack.append(f.body)
            elif isinstance(f, Binary):
                stack.extend((f.left, f.right))
            elif isinstance(f, Quantified):
                stack.append(f.body)
        return {"functions": functions, "predicates": predicates}


def free_variables(f: Formula, bound: frozenset[str] = frozenset()) -> list[str]:
    found: list[str] = []

    def term(t: Term, bound: frozenset[str]) -> None:
        if isinstance(t, Var):
            if t.name not in bound and t.name not in found:
                found.append(t.name)
        else:
            for arg in t.args:
                term(arg, bound)

    def walk(node: Formula, bound: frozenset[str]) -> None:
        if isinstance(node, Atom):
            for arg in node.args:
                term(arg, bound)
        elif isinstance(node, Equality):
            term(node.left, bound)
            term(node.right, bound)
        elif isinstance(node, Not):
            walk(node.body, bound)
        elif isinstance(node, Binary):
            walk(node.left, bound)
            walk(node.right, bound)
        elif isinstance(node, Quantified):
            walk(node.body, bound | set(node.variables))

    walk(f, bound)
    return found
