class HTTPCodeError(Exception):
    pass


def remove_not_alphanumeric(s: str) -> str:
    """Remove non-alphanumeric characters from a string."""
    return ''.join(c for c in s if c.isalnum())
