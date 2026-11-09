# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Exception types shared across the SDK.

:class:`UnexpectedStatus` is raised by the generated HTTP client behind the
remote storage backend. :class:`HackAgentError` and :class:`ApiError` are
re-exported from :mod:`hackagent` for callers that wrap the SDK.
"""


class UnexpectedStatus(Exception):
    """An HTTP response with a status the API schema does not document.

    Raised by the generated HTTP client only when it was built with
    ``raise_on_unexpected_status=True``; otherwise the response comes back
    with ``parsed`` set to None. ``content`` is the raw response body.
    """

    def __init__(self, status_code: int, content: bytes):
        self.status_code = status_code
        self.content = content
        super().__init__(
            f"Unexpected status code: {status_code}\n\nResponse content:\n{content.decode(errors='ignore')}"
        )


class HackAgentError(Exception):
    """Base class of the exceptions HackAgent defines for its callers."""

    pass


class ApiError(HackAgentError):
    """A failed call to the HackAgent API.

    Carries the server's ``status_code`` and decoded ``response`` body when
    they are known.
    """

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
