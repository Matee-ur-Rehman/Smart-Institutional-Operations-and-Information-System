"""Small helpers shared by the Member 2 tests."""
from datetime import date, timedelta


def day(offset: int = 0) -> str:
    """ISO date `offset` days from today (negative = past)."""
    return (date.today() + timedelta(days=offset)).isoformat()


def ids(items: list[dict]) -> set[str]:
    return {item["id"] for item in items}
