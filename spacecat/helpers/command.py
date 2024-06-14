from collections.abc import Callable
from typing import Self

import discord
from discord import app_commands
from discord.ext import commands


class CatCog(commands.Cog):
    """Base class for cogs that can be easily extended."""

    def permission_check(self: Self) -> Callable:
        """Checks if the user has permission to use the command."""

        def predicate(interaction: discord.Interaction) -> bool:
            return False

        return app_commands.check(predicate)
