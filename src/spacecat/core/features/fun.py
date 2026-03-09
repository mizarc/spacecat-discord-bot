"""Shared fun command logic."""

import random


def diceroll(sides: int = 6) -> str:
    """Roll a die and return the result.
    
    Args:
        sides: Number of sides on the dice. Defaults to 6.
        
    Returns:
        A formatted message with the roll result.
    """
    result = random.randint(1, sides)
    return f"You rolled a {result} on a {sides} sided dice"


def coinflip() -> str:
    """Flip a coin and return the result.

    Returns:
        The word 'Heads' or 'Tails' based on the random result.
    """
    return "Heads" if random.randint(0, 1) else "Tails"
