import threading

import pytest
from conftest import needs_provers

from fvp.examples import EXAMPLES
from fvp.provers import ProverRegistry, verdict
from fvp.provers.adapters import Otter, Spass, Vampire
from fvp.provers.base import ProverResult
from fvp.tptp import parse

GOAL = parse("fof(c, conjecture, p).")
NO_GOAL = parse("cnf(a, axiom, p).\ncnf(b, negated_conjecture, ~p).")


@pytest.mark.parametrize(
    ("output", "problem", "expected"),
    [
        ("% SZS status Theorem for x", GOAL, "Theorem"),
        ("% SZS status CounterSatisfiable for x", GOAL, "CounterSatisfiable"),
        ("% SZS status Timeout for x", GOAL, "Timeout"),
        ("% SZS status MemoryOut for x", GOAL, "GaveUp"),
        ("Segmentation fault", GOAL, "Error"),
    ],
)
def test_vampire_status_parsing(output, problem, expected):
    assert Vampire(None).interpret(output, 0, problem) == expected


@pytest.mark.parametrize(
    ("output", "problem", "expected"),
    [
        ("SPASS beiseite: Proof found.", GOAL, "Theorem"),
        ("SPASS beiseite: Proof found.", NO_GOAL, "Unsatisfiable"),
        ("SPASS beiseite: Completion found.", GOAL, "CounterSatisfiable"),
        ("SPASS beiseite: Ran out of time.", GOAL, "Timeout"),
        ("Parse error", GOAL, "Error"),
    ],
)
def test_spass_status_parsing(output, problem, expected):
    assert Spass(None).interpret(output, 0, problem) == expected


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [(103, "Theorem"), (104, "GaveUp"), (106, "Timeout"), (109, "GaveUp"), (101, "Error")],
)
def test_otter_exit_codes(exit_code, expected):
    assert Otter(None).interpret("", exit_code, GOAL) == expected


def test_missing_binary_reports_unavailable():
    prover = Vampire("definitely-not-installed-prover")
    assert not prover.available
    result = prover.run(GOAL, 5, threading.BoundedSemaphore(1))
    assert result.status == "Unavailable"


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        (["Theorem", "Timeout", "GaveUp"], "theorem"),
        (["Unsatisfiable"], "unsatisfiable"),
        (["CounterSatisfiable", "Timeout"], "counter_satisfiable"),
        (["Timeout", "GaveUp", "Error"], "unknown"),
        (["Theorem", "CounterSatisfiable"], "conflict"),
    ],
)
def test_verdict(statuses, expected):
    assert verdict([ProverResult("p", s, 0.1, 0, "") for s in statuses]) == expected


@needs_provers
@pytest.mark.parametrize("example", EXAMPLES, ids=[e["id"] for e in EXAMPLES])
def test_real_provers_never_contradict_known_answers(example):
    registry = ProverRegistry({"spass": "SPASS", "vampire": "vampire", "otter": "otter"}, max_concurrent=3)
    results = registry.run(parse(example["source"]), ["spass", "vampire", "otter"], 5)
    solved = {
        r.prover: r.status
        for r in results
        if r.status in ("Theorem", "Unsatisfiable", "CounterSatisfiable", "Satisfiable")
    }
    assert solved, f"no prover solved {example['id']}"
    assert set(solved.values()) == {example["expected"]}, solved


@needs_provers
def test_runaway_prover_is_killed_at_the_time_limit():
    # Vampire's own limit is set to the same value, so test the server-side
    # wall-clock guard with a problem no prover finishes quickly.
    hard = parse("""
        fof(a, axiom, ![X, Y, Z]: m(m(X, Y), Z) = m(X, m(Y, Z))).
        fof(c, conjecture, ![X, Y]: m(X, Y) = m(Y, X)).
    """)
    registry = ProverRegistry({"spass": "SPASS", "vampire": "vampire", "otter": "otter"}, max_concurrent=3)
    results = registry.run(hard, ["spass", "otter"], 2)
    assert all(r.seconds < 2 + 4 for r in results)
    assert all(r.status in ("Timeout", "GaveUp", "CounterSatisfiable") for r in results)
