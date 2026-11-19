from __future__ import annotations

from typing import Annotated, Any, Literal

from flask import request
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
)

from fvp.tptp.parser import MAX_SOURCE_CHARS


def _not_trivial(value: str) -> str:
    if len(set(value)) < 6:
        raise ValueError("password is too repetitive")
    return value


SafeText = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[^<>\x00-\x1f\x7f]*$")]
Password = Annotated[str, StringConstraints(min_length=12, max_length=128), AfterValidator(_not_trivial)]
ProverName = Literal["spass", "vampire", "otter"]
Source = Annotated[str, StringConstraints(min_length=1, max_length=MAX_SOURCE_CHARS)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(_Strict):
    email: Annotated[EmailStr, AfterValidator(str.lower)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class Registration(_Strict):
    email: Annotated[EmailStr, AfterValidator(str.lower)]
    password: Password


class PasswordChange(_Strict):
    current_password: Annotated[str, StringConstraints(max_length=128)]
    new_password: Password


class VerifyRequest(_Strict):
    source: Source
    provers: list[ProverName] = Field(min_length=1, max_length=3)
    time_limit: int = Field(default=10, ge=1, le=300)
    title: Annotated[SafeText, StringConstraints(max_length=120)] = "Untitled problem"

    @field_validator("provers")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("each prover can only be selected once")
        return value


class ValidateRequest(_Strict):
    source: Source


class ProblemIn(_Strict):
    title: Annotated[SafeText, StringConstraints(min_length=1, max_length=120)]
    domain: Annotated[SafeText, StringConstraints(min_length=1, max_length=60)] = "General"
    description: Annotated[SafeText, StringConstraints(max_length=500)] = ""
    source: Source


class RequestValidationError(Exception):
    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("invalid request")
        self.errors = errors


def parse_body[M: BaseModel](model: type[M]) -> M:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise RequestValidationError([{"field": "body", "message": "expected a JSON object"}])
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        # Report field and message only; never echo submitted values back.
        raise RequestValidationError(
            [{"field": ".".join(str(p) for p in e["loc"]) or "body", "message": e["msg"]} for e in exc.errors()]
        ) from None
    except ValueError as exc:
        raise RequestValidationError([{"field": "body", "message": str(exc)}]) from None
