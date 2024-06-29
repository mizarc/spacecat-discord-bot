"""
This module provides functions for outputting messages to the console.

Various types of output are provided for use depending on what the
intent behind the message is. It also helps to avoid linter warnings for
print statements, as they're all ignored here.
"""


def message(message: str) -> None:
    """
    Prints the given message directly to the console.

    No prefixes, just the raw string output. Use this instead of a
    direct print to avoid linter warnings.

    Args:
        message (str): The message to be printed.
    """
    print(message)  # noqa: T201


def log(message: str) -> None:
    """
    Prints a prefixed log message to the console.

    Used to print useful logging information that the administrator
    should be aware of.

    Args:
        message (str): The error message to be printed.
    """
    print(f"[LOG] {message}")  # noqa: T201


def debug(message: str) -> None:
    """
    Prints a prefixed debug message to the console.

    Used for debugging purposes, but should not be used in production.

    Args:
        message (str): The error message to be printed.
    """
    print(f"[LOG] {message}")  # noqa: T201


def error(message: str) -> None:
    """
    Prints a prefixed error message to the console.

    If things go wrong, this is the output type that should be used to
    draw immediate attention to the problem.

    Args:
        message (str): The error message to be printed.
    """
    print(f"[ERROR] {message}")  # noqa: T201
