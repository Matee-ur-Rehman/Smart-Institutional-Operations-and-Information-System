"""Building blocks shared by Member 2's models and schemas."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Sequence

from pydantic import Field, PlainSerializer
from sqlalchemy import CheckConstraint, DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def check_in(table: str, column: str, values: Sequence[str]) -> CheckConstraint:
    """CHECK (column IN (...)) with a fixed name, so models and hand-written migrations agree."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=f"ck_{table}_{column}")


# JSON numbers (not strings) for money, as promised in docs/API_CONTRACT.md section 1.
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]
# Request-side money: positive, at most 2 decimals.
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]
