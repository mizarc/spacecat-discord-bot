from typing import Protocol, runtime_checkable


@runtime_checkable
class BotInterface(Protocol):
    """
    Defines the minimum requirements for a bot instance
    to work with the EventService.
    """
    # Add any common methods or attributes your actions need
    # e.g., if actions need to fetch a guild or send a log
    pass