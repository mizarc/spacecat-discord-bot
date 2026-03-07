"""
This module provides utilities for reaction button type conversions.

The current usage allows you to make use of emoji numbers are reaction
buttons, and also to convert them back to their integer representations.
"""


def number_to_emoji(num: int) -> str:
    """
    Converts a number to the emoji representation.

    Args:
        num (int): The number to convert.

    Returns:
        str: The emoji string representation of the number.
    """
    return f"{num}\u20e3"


def emoji_to_number(emoji: str) -> int:
    """
    Converts a emoji number to the integer representation.

    Args:
        emoji (str): The emoji string to convert.

    Returns:
        int: The integer representation of the emoji.
    """
    return int(emoji[0])
