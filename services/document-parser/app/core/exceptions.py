"""Domain errors mapped to HTTP responses in main.py."""


class DocumentProcessingError(ValueError):
    """Client should wait or poll job status instead of forcing a re-parse."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class BackgroundJobBusyError(Exception):
    """Too many concurrent background parse jobs."""

    def __init__(self, message: str = "Too many concurrent parse jobs; retry later") -> None:
        super().__init__(message)


class BankruptcyIdRequiredError(ValueError):
    """Parse requests must include bankruptcy_id when enforcement is enabled."""

    def __init__(
        self, message: str = "bankruptcy_id is required for document parse"
    ) -> None:
        super().__init__(message)
