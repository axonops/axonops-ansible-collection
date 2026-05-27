class HTTPCodeError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def remove_not_alphanumeric(s: str) -> str:
    """Remove non-alphanumeric characters from a string."""
    return ''.join(c for c in s if c.isalnum())
