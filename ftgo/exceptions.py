"""Exceptions raised by the ftgo library."""


class FTMarketsError(Exception):
    """FT Markets returned a response that could not be understood.

    Raised when a response is not in the expected format, for example when a
    request is rejected with an HTML page instead of JSON or when the page
    layout has changed. Network and HTTP errors are raised as the underlying
    ``requests`` exceptions, and invalid arguments as ``ValueError``.
    """
