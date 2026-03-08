"""
This helper module provides functions for managing permissions.

Permissions are handled on a role and user basis. Decorators can be
utilised in order to check what kind of permission needs to be checked
before performing said command, else the user is alerted to their lack
of permissions.

The `check` decorator is a user facing permission check, while
`exclusive` is a bot administrator check. Use accordingly.
"""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, cast

import fluxer
import toml

if TYPE_CHECKING:
    from typing import Callable


def check() -> Callable:
    """
    A decorator that checks if the user has permission to use a command.
    
    For fluxer, this is currently a placeholder that always allows access.
    In a full implementation, you would check against a database or config.
    """
    def decorator(func):
        return func
    return decorator


def exclusive() -> Callable:
    """
    A decorator that checks if the user is a bot administrator.
    
    For fluxer, this is currently a placeholder that always allows access.
    In a full implementation, you would check against a database or config.
    """
    def decorator(func):
        return func
    return decorator
