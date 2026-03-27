"""
Fluxer-specific scheduler module.

This module provides Fluxer platform-specific implementations of the core
scheduler functionality, including commands and event handlers for reminders
and scheduled events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import fluxer

from spacecat.core.features.automation import reminder_list
from spacecat.core.features.automation import reminder_remove as delete_reminder
from spacecat.core.features.automation import remindme as create_reminder
from spacecat.platforms.fluxer.helpers import permissions
from spacecat.platforms.fluxer.helpers.utils import parse_quoted_args

if TYPE_CHECKING:
    from spacecat.platforms.fluxer.client import FluxerClient


class Automation(fluxer.Cog):
    """Schedule events and reminders for Fluxer."""

    def __init__(self: Automation, bot: fluxer.Bot) -> None:
        """
        Initializes a new instance of the Scheduler class.

        Args:
            bot (FluxerClient): The Fluxer bot instance.
        """
        super().__init__(bot)

    @fluxer.Cog.command()
    @permissions.check()
    async def remindme(
        self: Self,
        ctx: fluxer.Message,
        *,
        reminder_text: str,
    ) -> None:
        """
        Set a reminder to send a message after a specified time.

        Args:
            ctx: The command context.
            reminder_text: Full reminder text in format "time message"
                (e.g., '30m' 'Meeting time')
        """
        # Parse two arguments with quote support
        time_input, message = parse_quoted_args(reminder_text)

        # Use the core remindme function to create and schedule the reminder
        result = await create_reminder(
            user_id=str(ctx.author.id),
            message=message,
            dispatch_time_text=time_input,
            guild_id=ctx.guild.id if ctx.guild else 0,
            channel_id=ctx.channel.id,
            message_id=ctx.id,
        )

        # Send confirmation
        await ctx.reply(result["display"])

    @fluxer.Cog.command(name="reminder list")
    @permissions.check()
    async def reminder_list(self: Self, ctx: fluxer.Message) -> None:
        """
        Lists all your reminders in the current server.

        Args:
            ctx: The command context.
        """
        result = await reminder_list(ctx.guild.id, ctx.author.id)

        # Create a nice embed for the reminders
        embed = fluxer.Embed(title=result["title"], color=0x3498DB)

        embed.description = result["display"]

        await ctx.reply(embed=embed)

    @fluxer.Cog.command(name="reminder remove")
    @permissions.check()
    async def reminder_remove(
        self: Self,
        ctx: fluxer.Message,
        index: int,
    ) -> None:
        """
        Delete a reminder by its index number.

        Args:
            ctx: The command context.
            index: The index of the reminder to delete.
        """
        index = int(index)

        # Delete the reminder
        result = await delete_reminder(ctx.guild.id, ctx.author.id, index)

        await ctx.reply(result["display"])


async def setup(bot: FluxerClient) -> None:
    """
    Load the Scheduler cog.

    Args:
        bot (FluxerClient): The Fluxer bot instance.
    """
    await bot.add_cog(Automation(bot))
