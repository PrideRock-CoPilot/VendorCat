from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ApiErrorPayload:
    code: str
    message: str
    request_id: str
    details: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
