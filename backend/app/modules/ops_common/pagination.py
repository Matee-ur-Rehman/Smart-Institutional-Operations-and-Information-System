"""?page=&page_size= pagination, response shape from docs/API_CONTRACT.md section 1."""
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def paginate(db: Session, stmt, params: PageParams, scalars: bool = True) -> tuple[list, int]:
    """Run a SELECT with LIMIT/OFFSET. Returns (rows, total). scalars=False keeps multi-column rows."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    result = db.execute(stmt.offset(params.offset).limit(params.page_size))
    rows = list(result.scalars().all()) if scalars else list(result.all())
    return rows, total


def page_of(items: list, total: int, params: PageParams) -> dict:
    return {"items": items, "total": total, "page": params.page, "page_size": params.page_size}
