from __future__ import annotations


class UserInputError(Exception):
    """Raised for invalid user input."""

    pass


class ExternalServiceError(Exception):
    """Raised when external services fail."""

    pass


class InternalError(Exception):
    """Raised for unexpected internal errors."""

    pass
