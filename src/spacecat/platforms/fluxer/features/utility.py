"""Utility commands for general bot functionality."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Self

import fluxer

from spacecat.platforms.fluxer.helpers import permissions
from spacecat.platforms.fluxer.helpers.embeds import format_universal_embed
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
    async def avatar(self: Self, ctx, user: fluxer.User | None = None) -> None:
        """Get a user's avatar URL.

        Args:
            ctx: The command context.
            user: The user to get avatar for. Defaults to command author.
        """
        clean_id = user.replace("<@", "").replace("!", "").replace(">", "")
        user_instance = await self.bot.fetch_user(clean_id)
        response = core_utility.avatar(user_instance.avatar_url)
        await ctx.reply(response)

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
        await core_utility.ping(
            send_func=ctx.reply,
            edit_func=lambda msg, content: msg.edit(content=content)
        )

    @fluxer.Cog.command()
    @permissions.check()
    async def qrcode(self: Self, ctx, *, data: str) -> None:
        """Generates a QR code from the provided text or URL.

        Args:
            ctx: The command context.
            data: The URL or text to encode.
        """
        # 1. Logic call
        buffer = core_utility.qrcode(data)

        # 2. Prepare the file
        file = fluxer.File(fp=buffer, filename="qrcode.png")

        await ctx.reply(file=file)

    @fluxer.Cog.command()
    @permissions.check()
    async def uptime(self: Self, ctx) -> None:
        """Check how long the bot has been running.

        Args:
            ctx: The command context.
        """
        response = core_utility.uptime(self.start_time)
        await ctx.reply(response)


async def setup(bot: fluxer.Bot) -> None:
    """Load the Utility cog.

    Args:
        bot: The Fluxer bot instance.
    """
    await bot.add_cog(Utility(bot))
