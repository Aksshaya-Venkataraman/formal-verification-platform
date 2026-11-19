"""Serialise a parsed problem for each prover: TPTP (SPASS, Vampire) and Otter."""

from __future__ import annotations

from fvp.tptp.ast import (
    AXIOM_ROLES,
    Atom,
    Binary,
    Equality,
    Fn,
    Formula,
    Not,
    Problem,
    Quantified,
    Term,
    Truth,
    Var,
    free_variables,
)

# ------------------------------------------------------------------- TPTP


def tptp_term(t: Term) -> str:
    if isinstance(t, Var):
        return t.name
    if not t.args:
        return t.name
    return f"{t.name}({','.join(tptp_term(a) for a in t.args)})"


def tptp_formula(f: Formula) -> str:
    if isinstance(f, Truth):
        return "$true" if f.value else "$false"
    if isinstance(f, Atom):
        return tptp_term(Fn(f.predicate, f.args))
    if isinstance(f, Equality):
        return f"{tptp_term(f.left)} {'!=' if f.negated else '='} {tptp_term(f.right)}"
    if isinstance(f, Not):
        return f"~ ({tptp_formula(f.body)})"
    if isinstance(f, Binary):
        return f"({tptp_formula(f.left)} {f.op} {tptp_formula(f.right)})"
    if isinstance(f, Quantified):
        return f"{f.quantifier}[{','.join(f.variables)}] : ({tptp_formula(f.body)})"
    raise TypeError(f"unknown formula node {type(f).__name__}")


def _cnf_literal(f: Formula) -> str:
    if isinstance(f, Not):
        return f"~ {tptp_formula(f.body)}"
    return tptp_formula(f)


def _cnf_clause(f: Formula) -> str:
    if isinstance(f, Binary) and f.op == "|":
        return f"{_cnf_clause(f.left)} | {_cnf_clause(f.right)}"
    return _cnf_literal(f)


def to_tptp(problem: Problem) -> str:
    lines = []
    for s in problem.statements:
        body = f"({_cnf_clause(s.formula)})" if s.language == "cnf" else tptp_formula(s.formula)
        lines.append(f"{s.language}({s.name}, {s.role}, {body}).")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ Otter

# Names that Otter would read as keywords or built-ins.
_OTTER_RESERVED = {
    "all",
    "exists",
    "list",
    "formula_list",
    "end_of_list",
    "set",
    "clear",
    "assign",
    "op",
    "make_evaluable",
    "lex",
    "weight_list",
    "include",
}
_TOP = "fvp_true_"


def _otter_name(name: str) -> str:
    return f"s_{name}" if name in _OTTER_RESERVED or name.startswith("fvp_") else name


def otter_term(t: Term) -> str:
    if isinstance(t, Var):
        return t.name
    name = _otter_name(t.name)
    return name if not t.args else f"{name}({','.join(otter_term(a) for a in t.args)})"


def otter_formula(f: Formula) -> str:
    if isinstance(f, Truth):
        # Otter has no truth constants in formulas; use a tautology / contradiction.
        return f"({_TOP} | -{_TOP})" if f.value else f"({_TOP} & -{_TOP})"
    if isinstance(f, Atom):
        return otter_term(Fn(f.predicate, f.args))
    if isinstance(f, Equality):
        return f"({otter_term(f.left)} {'!=' if f.negated else '='} {otter_term(f.right)})"
    if isinstance(f, Not):
        return f"-({otter_formula(f.body)})"
    if isinstance(f, Binary):
        a, b = otter_formula(f.left), otter_formula(f.right)
        return {
            "&": f"({a} & {b})",
            "|": f"({a} | {b})",
            "=>": f"({a} -> {b})",
            "<=": f"({b} -> {a})",
            "<=>": f"({a} <-> {b})",
            "<~>": f"-({a} <-> {b})",
            "~|": f"-({a} | {b})",
            "~&": f"-({a} & {b})",
        }[f.op]
    if isinstance(f, Quantified):
        word = "all" if f.quantifier == "!" else "exists"
        return f"({word} {' '.join(f.variables)} ({otter_formula(f.body)}))"
    raise TypeError(f"unknown formula node {type(f).__name__}")


def to_otter(problem: Problem, time_limit: int) -> str:
    """Otter 3.3 input in autonomous mode with TPTP-style (upper-case) variables.

    Every statement becomes a closed formula (CNF clauses get explicit
    universal quantifiers), and the conjecture is negated for refutation.
    """
    formulas = []
    for s in problem.statements:
        body = s.formula
        free = free_variables(body)
        text = otter_formula(body)
        if free:
            text = f"(all {' '.join(free)} ({text}))"
        if s.role == "conjecture":
            text = f"-({text})"
        elif s.role not in AXIOM_ROLES and s.role != "negated_conjecture":
            raise ValueError(f"unsupported role {s.role}")
        formulas.append(f"{text}.")
    return "\n".join(
        [
            "set(prolog_style_variables).",
            "set(auto).",
            f"assign(max_seconds, {int(time_limit)}).",
            "assign(max_mem, 1000000).",
            "formula_list(usable).",
            *formulas,
            "end_of_list.",
            "",
        ]
    )
