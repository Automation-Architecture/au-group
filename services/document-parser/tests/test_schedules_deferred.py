import pytest
from app.extractors import schedules


def test_schedule_parsers_deferred() -> None:
    with pytest.raises(NotImplementedError):
        schedules.parse_schedule_ef("sample")
