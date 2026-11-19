"""SPASS, Vampire and Otter adapters: input format, command line, result parsing."""

from __future__ import annotations

import re
from pathlib import Path

from fvp.provers.base import (
    COUNTER_SATISFIABLE,
    ERROR,
    GAVE_UP,
    SATISFIABLE,
    THEOREM,
    TIMEOUT,
    UNSATISFIABLE,
    Prover,
    solved_status,
)
from fvp.tptp import to_otter, to_tptp
from fvp.tptp.ast import Problem


class Vampire(Prover):
    name, label = "vampire", "Vampire"
    _status = re.compile(r"^% SZS status (\w+)", re.MULTILINE)
    _known = {THEOREM, UNSATISFIABLE, COUNTER_SATISFIABLE, SATISFIABLE, TIMEOUT, GAVE_UP}

    def version_args(self) -> list[str]:
        return ["--version"]

    def parse_version(self, text: str) -> str | None:
        match = re.search(r"Vampire\s+([0-9][\w.\-]*)", text)
        return match.group(1) if match else None

    def render_input(self, problem: Problem, time_limit: int) -> str:
        return to_tptp(problem)

    def command(self, input_path: Path, time_limit: int) -> list[str]:
        return [
            self.binary or "vampire",
            "--mode",
            "casc",
            "--input_syntax",
            "tptp",
            "--time_limit",
            f"{time_limit}s",
            "--memory_limit",
            "2048",
            str(input_path),
        ]

    def interpret(self, output: str, exit_code: int | None, problem: Problem) -> str:
        match = self._status.search(output)
        if match is None:
            return ERROR
        status = match.group(1)
        if status in self._known:
            return status
        return GAVE_UP if status in {"ResourceOut", "MemoryOut", "Unknown", "Incomplete"} else ERROR


class Spass(Prover):
    name, label = "spass", "SPASS"

    def version_args(self) -> list[str]:
        return []

    def parse_version(self, text: str) -> str | None:
        match = re.search(r"SPASS V\s*([0-9][\w.]*)", text)
        return match.group(1) if match else None

    def render_input(self, problem: Problem, time_limit: int) -> str:
        return to_tptp(problem)

    def command(self, input_path: Path, time_limit: int) -> list[str]:
        return [self.binary or "SPASS", "-TPTP", "-DocProof", f"-TimeLimit={time_limit}", str(input_path)]

    def interpret(self, output: str, exit_code: int | None, problem: Problem) -> str:
        if "SPASS beiseite: Proof found." in output:
            return solved_status(problem, refuted=True)
        if "SPASS beiseite: Completion found." in output:
            return solved_status(problem, refuted=False)
        if "SPASS beiseite: Ran out of time." in output:
            return TIMEOUT
        if "SPASS beiseite: Maximal number of loops exceeded." in output:
            return GAVE_UP
        return ERROR


class Otter(Prover):
    name, label = "otter", "Otter"
    uses_stdin = True
    # Exit codes from the Otter 3.3 manual, section 16.
    PROOF, SOS_EMPTY, MAX_SECONDS, INPUT_ERROR = 103, 104, 106, 101
    _RESOURCE = {105, 107, 108, 109, 110, 114, 115}

    def version_args(self) -> list[str]:
        return []

    def parse_version(self, text: str) -> str | None:
        match = re.search(r"Otter\s+([0-9][\w.]*)", text)
        return match.group(1) if match else None

    def render_input(self, problem: Problem, time_limit: int) -> str:
        return to_otter(problem, time_limit)

    def command(self, input_path: Path, time_limit: int) -> list[str]:
        return [self.binary or "otter"]

    def interpret(self, output: str, exit_code: int | None, problem: Problem) -> str:
        if exit_code == self.PROOF or "-------- PROOF --------" in output:
            return solved_status(problem, refuted=True)
        if exit_code == self.MAX_SECONDS:
            return TIMEOUT
        if exit_code == self.SOS_EMPTY or exit_code in self._RESOURCE:
            # Auto mode is not a complete strategy, so an exhausted search
            # does not prove the conjecture false.
            return GAVE_UP
        return ERROR


PROVER_CLASSES: dict[str, type[Prover]] = {"spass": Spass, "vampire": Vampire, "otter": Otter}
