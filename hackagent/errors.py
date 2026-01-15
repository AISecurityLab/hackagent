"""Contains shared errors types that can be raised from API functions"""


class UnexpectedStatus(Exception):
    """Raised by api functions when the response status an undocumented status and Client.raise_on_unexpected_status is True"""

    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content

        super().__init__(
            f"Unexpected status code: {status_code}\n\nResponse content:\n{content.decode(errors='ignore')}"
        )


class HackAgentError(Exception):
    """Base exception class for HackAgent errors"""

    pass


class ApiError(HackAgentError):
    """Raised when an API call fails"""

    def __init__(
        self, message: str, status_code: int | None = None, response: dict | None = None
    ):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(message)


# Alias for backward compatibility with tests
UnexpectedStatusError = UnexpectedStatus

__all__ = ["UnexpectedStatus", "UnexpectedStatusError", "HackAgentError", "ApiError"]
