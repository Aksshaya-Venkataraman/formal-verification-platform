"""Running theorem provers safely.

Each run gets a private temporary directory, a minimal environment, no shell,
resource limits (CPU time, memory, file size, open files, no core dumps) via
`prlimit`, a wall-clock timeout that kills the whole process group, and a cap
on how many provers run at once across the server.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import signal
import subprocess  # nosec B404 - commands are fixed argument lists, never a shell
import tempfile
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path

from fvp.tptp.ast import Problem

log = logging.getLogger(__name__)

THEOREM, UNSATISFIABLE = "Theorem", "Unsatisfiable"
COUNTER_SATISFIABLE, SATISFIABLE = "CounterSatisfiable", "Satisfiable"
TIMEOUT, GAVE_UP, ERROR, UNAVAILABLE = "Timeout", "GaveUp", "Error", "Unavailable"
SOLVED = {THEOREM, UNSATISFIABLE, COUNTER_SATISFIABLE, SATISFIABLE}

MAX_OUTPUT_BYTES = 5 * 1024 * 1024  # hard cap enforced by RLIMIT_FSIZE
KEEP_HEAD, KEEP_TAIL = 40_000, 10_000  # what is stored and shown to the user
MEMORY_LIMIT_BYTES = 3 * 1024**3
GRACE_SECONDS = 3


class ProverBusyError(RuntimeError):
    """All prover slots are in use."""


@dataclass
class ProverResult:
    prover: str
    status: str
    seconds: float
    exit_code: int | None
    output: str

    def to_dict(self) -> dict:
        return asdict(self)


class Prover(ABC):
    name: str
    label: str

    def __init__(self, binary: str | None) -> None:
        self.binary = shutil.which(binary) if binary else None

    @property
    def available(self) -> bool:
        return self.binary is not None

    @cached_property
    def version(self) -> str | None:
        if not self.binary:
            return None
        try:
            proc = subprocess.run(  # nosec B603 - fixed argv, no shell
                [self.binary, *self.version_args()],
                capture_output=True,
                timeout=5,
                text=True,
                stdin=subprocess.DEVNULL,
                env=_safe_env(tempfile.gettempdir()),
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return self.parse_version(proc.stdout + proc.stderr)

    # ---- per-prover hooks -------------------------------------------------
    @abstractmethod
    def version_args(self) -> list[str]: ...

    @abstractmethod
    def parse_version(self, text: str) -> str | None: ...

    @abstractmethod
    def render_input(self, problem: Problem, time_limit: int) -> str: ...

    @abstractmethod
    def command(self, input_path: Path, time_limit: int) -> list[str]: ...

    @abstractmethod
    def interpret(self, output: str, exit_code: int | None, problem: Problem) -> str: ...

    uses_stdin = False

    # ---- execution ----------------------------------------------------------
    def run(self, problem: Problem, time_limit: int, slots: threading.BoundedSemaphore) -> ProverResult:
        if not self.available:
            return ProverResult(self.name, UNAVAILABLE, 0.0, None, f"{self.label} is not installed on this server.")
        if not slots.acquire(timeout=time_limit + 10):
            raise ProverBusyError("all prover slots are busy")
        try:
            return self._run(problem, time_limit)
        finally:
            slots.release()

    def _run(self, problem: Problem, time_limit: int) -> ProverResult:
        with tempfile.TemporaryDirectory(prefix="fvp-") as workdir:
            work = Path(workdir)
            input_path = work / "problem.in"
            fd = os.open(input_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as handle:
                handle.write(self.render_input(problem, time_limit))
            output_path = work / "output.txt"

            argv = _sandbox_prefix(time_limit) + self.command(input_path, time_limit)
            started = time.monotonic()
            timed_out = False
            with open(output_path, "wb") as out, open(input_path, "rb") as stdin_file:
                proc = subprocess.Popen(  # nosec B603 - fixed argv built from trusted paths, no shell
                    argv,
                    cwd=work,
                    env=_safe_env(workdir),
                    stdin=stdin_file if self.uses_stdin else subprocess.DEVNULL,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # own process group, so the whole tree can be killed
                )
                try:
                    proc.wait(timeout=time_limit + GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    _kill_group(proc)
                    proc.wait()
            elapsed = round(time.monotonic() - started, 3)
            raw = output_path.read_bytes()[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")

        status = TIMEOUT if timed_out else self.interpret(raw, proc.returncode, problem)
        if status == ERROR:
            log.warning("%s returned an error (exit %s)", self.name, proc.returncode)
        return ProverResult(self.name, status, elapsed, None if timed_out else proc.returncode, _clip(raw))


def _sandbox_prefix(time_limit: int) -> list[str]:
    prlimit = shutil.which("prlimit")
    if prlimit is None:  # e.g. macOS development machines
        log.warning("prlimit not found: provers run without resource limits")
        return []
    return [
        prlimit,
        f"--cpu={time_limit + GRACE_SECONDS}",
        f"--as={MEMORY_LIMIT_BYTES}",
        f"--fsize={MAX_OUTPUT_BYTES}",
        "--nofile=64",
        "--core=0",
        "--",
    ]


def _safe_env(home: str) -> dict[str, str]:
    return {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": home, "TMPDIR": home}


def _kill_group(proc: subprocess.Popen) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(proc.pid, signal.SIGKILL)


def _clip(text: str) -> str:
    if len(text) <= KEEP_HEAD + KEEP_TAIL:
        return text
    skipped = len(text) - KEEP_HEAD - KEEP_TAIL
    return f"{text[:KEEP_HEAD]}\n\n... [{skipped} characters omitted] ...\n\n{text[-KEEP_TAIL:]}"


def solved_status(problem: Problem, refuted: bool) -> str:
    """Name the result the way SZS does: Theorem/CounterSatisfiable only with a conjecture."""
    if problem.conjecture is not None:
        return THEOREM if refuted else COUNTER_SATISFIABLE
    return UNSATISFIABLE if refuted else SATISFIABLE
