"""Utility commands for general bot functionality."""

from __future__ import annotations

import time
from typing import Self

import fluxer

from spacecat.platforms.fluxer.helpers import permissions
import spacecat.core.features.utility as core_utility


class Utility(fluxer.Cog):
    """General utility commands."""

    def __init__(self: Utility, bot: fluxer.Bot) -> None:
        """Initialise the Utility cog.

        Args:
            bot: The bot instance.
        """
        super().__init__(bot)
        self.start_time = time.time()

    @fluxer.Cog.command()
    @permissions.check()
    async def echo(self: Self, ctx, *, message: str) -> None:
        """Repeats a given message.

        Args:
            ctx: The command context.
            message: The message to repeat.
        """
        response = core_utility.echo(message)
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def ping(self: Self, ctx) -> None:
        """Check bot latency.

        Args:
            ctx: The command context.
        """
        response = core_utility.ping()
        await ctx.reply(response)

    @fluxer.Cog.command()
    @permissions.check()
    async def avatar(self: Self, ctx, user: fluxer.User | None = None) -> None:
        """Get a user's avatar URL.

        Args:
            ctx: The command context.
            user: The user to get avatar for. Defaults to command author.
        """
        clean_id = user.replace("<@", "").replace("!", "").replace(">", "")
        user_instance = await self.bot.fetch_user(clean_id)
        if user_instance.avatar_url:
            await ctx.reply(user_instance.avatar_url)
        else:
            await ctx.reply("This user doesn't have an avatar.")

    @fluxer.Cog.command()
    @permissions.check()
    async def userinfo(self: Self, ctx, user: fluxer.User | None = None) -> None:
        """Display information about a user.

        Args:
            ctx: The command context.
            user: The user to get info for. Defaults to command author.
        """
        clean_id = user.replace("<@", "").replace("!", "").replace(">", "")
        user_instance = await self.bot.fetch_user(clean_id)
        info = f"**User:** {user_instance.display_name}\n**ID:** {user_instance.id}\n**Created:** {user_instance.created_at}"
        await ctx.reply(info)

    @fluxer.Cog.command()
    @permissions.check()
    async def uptime(self: Self, ctx) -> None:
        """Check how long the bot has been running.

        Args:
            ctx: The command context.
        """
        uptime_info = core_utility.format_uptime(self.start_time)
        await ctx.reply(f"Uptime: {uptime_info.hours}h {uptime_info.minutes}m {uptime_info.seconds}s")


async def setup(bot: fluxer.Bot) -> None:
    """Load the Utility cog.

    Args:
        bot: The Fluxer bot instance.
    """
    await bot.add_cog(Utility(bot))