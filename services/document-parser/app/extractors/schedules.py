"""
Phase 2 schedule parsers (deferred).

P1 filing types not implemented in Phase 1 gate:
- SCHEDULE_A_B
- SCHEDULE_D
- SCHEDULE_E_F
- SOFA (P2)

Implement after Form 201 / creditor matrix accuracy gates pass.
See docs/workflows/document-parse.md and SYS-02A plan Phase 6.
"""

from app.models.schemas import CreditorRow


def parse_schedule_ab(_text: str) -> list[CreditorRow]:
    raise NotImplementedError("SCHEDULE_A_B parser deferred to Phase 2")


def parse_schedule_d(_text: str) -> list[CreditorRow]:
    raise NotImplementedError("SCHEDULE_D parser deferred to Phase 2")


def parse_schedule_ef(_text: str) -> list[CreditorRow]:
    raise NotImplementedError("SCHEDULE_E_F parser deferred to Phase 2")


def parse_sofa(_text: str) -> dict:
    raise NotImplementedError("SOFA parser deferred to Phase 2")
