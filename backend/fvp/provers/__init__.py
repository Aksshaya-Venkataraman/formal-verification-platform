"""Prover registry and the verification workflow."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from fvp.provers.adapters import PROVER_CLASSES
from fvp.provers.base import (
    COUNTER_SATISFIABLE,
    SATISFIABLE,
    THEOREM,
    UNSATISFIABLE,
    Prover,
    ProverBusyError,
    ProverResult,
)
from fvp.tptp.ast import Problem

__all__ = ["ProverBusyError", "ProverRegistry", "ProverResult", "verdict"]


class ProverRegistry:
    def __init__(self, paths: dict[str, str], max_concurrent: int) -> None:
        self.provers: dict[str, Prover] = {name: cls(paths.get(name)) for name, cls in PROVER_CLASSES.items()}
        self._slots = threading.BoundedSemaphore(max_concurrent)

    def describe(self) -> list[dict]:
        return [
            {"name": p.name, "label": p.label, "available": p.available, "version": p.version}
            for p in self.provers.values()
        ]

    def run(self, problem: Problem, names: list[str], time_limit: int) -> list[ProverResult]:
        """Run the selected provers in parallel on the same problem."""
        selected = [self.provers[n] for n in names]
        with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix="prover") as pool:
            futures = [pool.submit(p.run, problem, time_limit, self._slots) for p in selected]
            return [f.result() for f in futures]


def verdict(results: list[ProverResult]) -> str:
    statuses = {r.status for r in results}
    proved = statuses & {THEOREM, UNSATISFIABLE}
    refuted = statuses & {COUNTER_SATISFIABLE, SATISFIABLE}
    if proved and refuted:
        return "conflict"  # provers disagree: worth investigating, never silently resolved
    if proved:
        return "theorem" if THEOREM in proved else "unsatisfiable"
    if refuted:
        return "counter_satisfiable" if COUNTER_SATISFIABLE in refuted else "satisfiable"
    return "unknown"
