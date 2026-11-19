import pytest

from fvp.examples import EXAMPLES
from fvp.tptp import TPTPSyntaxError, parse, to_otter, to_tptp
from fvp.tptp.ast import Binary, Equality, Not, Quantified


def test_parses_quantifiers_connectives_and_equality():
    problem = parse("""
        % a comment
        fof(a1, axiom, ![X, Y]: ((p(X) & q(f(X, Y))) => X = Y)).
        /* block
           comment */
        fof(c, conjecture, ?[Z]: ~ r(Z) | c != d).
    """)
    first, second = problem.statements
    assert isinstance(first.formula, Quantified)
    assert first.formula.variables == ("X", "Y")
    assert isinstance(first.formula.body, Binary) and first.formula.body.op == "=>"
    assert isinstance(second.formula, Binary) and second.formula.op == "|"
    assert isinstance(second.formula.left, Quantified)  # quantifier binds tighter than |
    assert problem.conjecture is second
    assert problem.symbols()["functions"] == {("f", 2), ("c", 0), ("d", 0)}


def test_parses_cnf_and_associative_chains():
    problem = parse("cnf(c1, axiom, ~p(X) | q(X) | X = a).\nfof(f, axiom, a & b & c).")
    clause = problem.statements[0].formula
    assert isinstance(clause, Binary) and isinstance(clause.left.left, Not)
    assert isinstance(clause.right, Equality)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("include('Axioms/SET001-0.ax').", "include directives are not allowed"),
        ("thf(a, axiom, p).", "not supported"),
        ("fof(a, axiom, p(X)).", "unquantified variable"),
        ("fof(a, axiom, p => q => r).", "mixed connectives need parentheses"),
        ("fof(a, axiom, (p & q | r)).", "mixed connectives need parentheses"),
        ("fof(a, banana, p).", "unsupported role"),
        ("cnf(a, conjecture, p).", "negated_conjecture"),
        ("fof(a, conjecture, p).\nfof(b, conjecture, q).", "only one conjecture"),
        ("fof(a, axiom, p", "expected ')'"),
        ("fof(a, axiom, p) . fof(b, axiom, $distinct).", "not supported"),
        ("fof('quoted', axiom, p).", "unexpected character"),
        ("fof(a, axiom, p; rm -rf /).", "unexpected character"),
        ("/* never closed", "unterminated comment"),
        ("", "no formulas"),
        ("fof(a, axiom, p, [annotation]).", "annotations"),
    ],
)
def test_rejects_unsupported_or_unsafe_input(source, message):
    with pytest.raises(TPTPSyntaxError) as info:
        parse(source)
    assert message in str(info.value)


def test_reports_line_and_column():
    with pytest.raises(TPTPSyntaxError) as info:
        parse("fof(a, axiom, p).\nfof(b, axiom, q @ r).")
    assert (info.value.line, info.value.column) == (2, 17)


def test_size_and_depth_limits():
    with pytest.raises(TPTPSyntaxError, match="larger than"):
        parse("%" * 70_000)
    with pytest.raises(TPTPSyntaxError, match="nested too deeply"):
        parse("fof(a, axiom, " + "~" * 500 + "p).")


@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_examples_round_trip_through_tptp(example):
    problem = parse(example["source"])
    assert parse(to_tptp(problem)) == problem


def test_otter_translation():
    problem = parse("""
        fof(a, axiom, ![X]: (p(X) <= q(X))).
        fof(b, axiom, all <~> exists).
        cnf(c, axiom, ~ r(Y) | $false).
        fof(goal, conjecture, ?[X]: p(X)).
    """)
    text = to_otter(problem, time_limit=7)
    assert "set(prolog_style_variables)." in text
    assert "assign(max_seconds, 7)." in text
    assert "(all X ((q(X) -> p(X))))." in text  # reverse implication flipped
    assert "-(s_all <-> s_exists)." in text  # reserved words renamed, xor
    assert "(all Y ((-(r(Y)) | (fvp_true_ & -fvp_true_))))." in text  # free CNF variables bound
    assert "-((exists X (p(X))))." in text  # conjecture negated
