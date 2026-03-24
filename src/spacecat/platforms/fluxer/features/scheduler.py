"""
Fluxer-specific scheduler module.

This module provides Fluxer platform-specific implementations of the core
scheduler functionality, including commands and event handlers for reminders
and scheduled events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

import fluxer
from dateutil import parser

from spacecat.core.features.scheduler import reminder_list
from spacecat.core.features.scheduler import remindme as create_reminder
from spacecat.platforms.fluxer.helpers import permissions
from spacecat.platforms.fluxer.helpers.utils import parse_quoted_args

if TYPE_CHECKING:
    from spacecat.platforms.fluxer.client import FluxerClient


class Scheduler(fluxer.Cog):
    """Schedule events and reminders for Fluxer."""

    def __init__(self: Scheduler, bot: fluxer.Bot) -> None:
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

    @fluxer.Cog.command()
    @permissions.check()
    async def reminders(self: Self, ctx: fluxer.Message) -> None:
        """
        Lists all your reminders in the current server.

        Args:
            ctx: The command context.
        """
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server!")
            return

        result = await reminder_list(ctx.guild.id, ctx.author.id)

        # Create a nice embed for the reminders
        embed = fluxer.Embed(title=result["title"], color=0x3498DB)

        embed.description = result["display"]

        await ctx.reply(embed=embed)

    @fluxer.Cog.command()
    @permissions.check()
    async def delreminder(
        self: Self,
        ctx,
        index: int,
    ) -> None:
        """
        Deletes a reminder by its index number.

        Args:
            ctx: The command context.
            index (int): The index of the reminder to delete.
        """
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server!")
            return

        reminders = self.reminders.get_by_guild_and_user(ctx.guild.id, ctx.author.id)
        if not reminders:
            await ctx.reply("You have no reminders to delete!")
            return

        try:
            reminder = reminders[index - 1]
        except IndexError:
            await ctx.reply(f"Invalid reminder number! You have {len(reminders)} reminder(s).")
            return

        # Unschedule and remove the reminder
        await self.reminder_scheduler.unschedule(reminder)
        self.reminders.remove(reminder.id)

        await ctx.reply(f"✅ Reminder #{index} has been deleted!")


async def setup(bot: FluxerClient) -> None:
    """
    Load the Scheduler cog.

    Args:
        bot (FluxerClient): The Fluxer bot instance.
    """
    await bot.add_cog(Scheduler(bot))
