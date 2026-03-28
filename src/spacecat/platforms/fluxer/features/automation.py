"""
Fluxer-specific scheduler module.

This module provides Fluxer platform-specific implementations of the core
scheduler functionality, including commands and event handlers for reminders
and scheduled events.
"""

from __future__ import annotations

import json
import shlex
from typing import TYPE_CHECKING, Self

import dateparser
import fluxer

import spacecat.core.features.automation as core_automation
from spacecat.core.models.actions import REQUIRED_KEYS
from spacecat.platforms.fluxer.helpers import permissions
from spacecat.platforms.fluxer.helpers.utils import parse_quoted_args

if TYPE_CHECKING:
    from spacecat.platforms.fluxer.client import FluxerClient


def _parse_action_args(args: list[str]) -> dict:
    """
    Parses a list of key=value strings into a dictionary.

    Args:
        args: A list of strings in 'key=value' format.

    Returns:
        dict: The parsed configuration dictionary.
    """
    config = {}
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            # Clean up quotes and try to convert numbers
            value = value.strip("'\"")
            if value.isdigit():
                value = int(value)
            config[key] = value
    return config


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
        # Parse arguments with quote support
        args = parse_quoted_args(reminder_text)
        arg_count = 2
        if len(args) < arg_count:
            await ctx.reply('Usage: !remindme "time" "message"')
            return

        time_input, message = args[0], args[1]

        # Use the core remindme function to create and schedule the reminder
        result = await core_automation.remindme(
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
        result = await core_automation.reminder_list(
            ctx.guild.id if ctx.guild else 0, ctx.author.id
        )

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
        # Delete the reminder
        result = await core_automation.reminder_remove(
            ctx.guild.id if ctx.guild else 0, ctx.author.id, index
        )

        await ctx.reply(result["display"])

    @fluxer.Cog.command(name="task list")
    @permissions.check()
    async def task_list(self: Self, ctx: fluxer.Message) -> None:
        """
        Lists all your tasks in the current server.

        Args:
            ctx: The command context.
        """
        result = await core_automation.task_list(ctx.guild.id if ctx.guild else 0)

        embed = fluxer.Embed(title=result["title"], color=0x2ECC71)
        embed.description = result["body"]
        if result.get("footer"):
            embed.set_footer(text=result["footer"])

        await ctx.reply(embed=embed)

    @fluxer.Cog.command(name="task create")
    @permissions.check()
    async def task_create(
        self: Self, ctx: fluxer.Message, name: str, *, description: str = ""
    ) -> None:
        """
        Create a new task in the guild.

        Args:
            ctx: The command context.
            name: The name of the task.
            description: Optional description for the task.
        """
        result = await core_automation.task_create(
            guild_id=ctx.guild.id if ctx.guild else 0, name=name, description=description
        )
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task delete")
    @permissions.check()
    async def task_delete(self: Self, ctx: fluxer.Message, name: str) -> None:
        """
        Delete a task by name.

        Args:
            ctx: The command context.
            name: The name of the task.
        """
        result = await core_automation.task_delete(ctx.guild.id if ctx.guild else 0, name)
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task info")
    @permissions.check()
    async def task_info(self: Self, ctx: fluxer.Message, name: str) -> None:
        """
        Show details of a task.

        Args:
            ctx: The command context.
            name: The name of the task.
        """
        result = await core_automation.task_info(ctx.guild.id if ctx.guild else 0, name)
        if result["success"]:
            await ctx.reply(result["display"])
        else:
            await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task pause")
    @permissions.check()
    async def task_pause(self: Self, ctx: fluxer.Message, name: str) -> None:
        """
        Pause a task.

        Args:
            ctx: The command context.
            name: The name of the task.
        """
        result = await core_automation.task_pause(ctx.guild.id if ctx.guild else 0, name)
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task resume")
    @permissions.check()
    async def task_resume(self: Self, ctx: fluxer.Message, name: str) -> None:
        """
        Resume a task.

        Args:
            ctx: The command context.
            name: The name of the task.
        """
        result = await core_automation.task_resume(ctx.guild.id if ctx.guild else 0, name)
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task rename")
    @permissions.check()
    async def task_rename(self: Self, ctx: fluxer.Message, old_name: str, new_name: str) -> None:
        """
        Rename a task.

        Args:
            ctx: The command context.
            old_name: The current name of the task.
            new_name: The new name for the task.
        """
        result = await core_automation.task_rename(
            ctx.guild.id if ctx.guild else 0, old_name, new_name
        )
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task description")
    @permissions.check()
    async def task_description(
        self: Self, ctx: fluxer.Message, name: str, *, description: str
    ) -> None:
        """
        Update task description.

        Args:
            ctx: The command context.
            name: The name of the task.
            description: The new description.
        """
        result = await core_automation.task_description(
            ctx.guild.id if ctx.guild else 0, name, description
        )
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task reschedule")
    @permissions.check()
    async def task_reschedule(
        self: Self, ctx: fluxer.Message, name: str, *, time_text: str
    ) -> None:
        """
        Reschedule a task.

        Args:
            ctx: The command context.
            name: The name of the task.
            time_text: Human readable time.
        """
        target_time = dateparser.parse(time_text)
        if not target_time:
            await ctx.reply("Could not parse time input.")
            return

        new_timestamp = int(target_time.timestamp())
        result = await core_automation.task_reschedule(
            ctx.guild.id if ctx.guild else 0, name, new_timestamp
        )
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task interval")
    @permissions.check()
    async def task_interval(
        self: Self, ctx: fluxer.Message, name: str, interval: str, multiplier: int = 1
    ) -> None:
        """
        Set task repeat interval.

        Args:
            ctx: The command context.
            name: The name of the task.
            interval: hourly, daily, weekly, or no.
            multiplier: Interval multiplier.
        """
        result = await core_automation.task_interval(
            ctx.guild.id if ctx.guild else 0, name, interval, multiplier
        )
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task trigger")
    @permissions.check()
    async def task_trigger(self: Self, ctx: fluxer.Message, name: str) -> None:
        """
        Manually trigger a task.

        Args:
            ctx: The command context.
            name: The name of the task.
        """
        result = await core_automation.task_trigger(ctx.guild.id if ctx.guild else 0, name)
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task action add")
    @permissions.check()
    async def task_action_add(
        self: Self, ctx: fluxer.Message, task_name: str, action_type: str, *, action_info: str
    ) -> None:
        """
        Add an action to a task.

        Args:
            ctx: The command context.
            task_name: The name of the task.
            action_type: The type of action.
            action_info: Space-separated key=value pairs
                (e.g., channel_id=123 content="Hello").
        """
        # Parse the action info as key value pairs
        try:
            args = shlex.split(action_info)
        except ValueError:
            await ctx.reply("❌ Error parsing arguments. Check your quotes!")
            return

        # Map those args to a dictionary
        config = _parse_action_args(args)

        # Check if they provided the right keys before even calling the backend
        if action_type in REQUIRED_KEYS:
            missing = [k for k in REQUIRED_KEYS[action_type] if k not in config]
            if missing:
                usage = " ".join([f"{k}=value" for k in REQUIRED_KEYS[action_type]])
                await ctx.reply(f"❌ Missing keys for `{action_type}`. Usage: `{usage}`")
                return

        # Pass the cleaned config to your existing logic
        result = await core_automation.task_action_add(
            ctx.guild.id if ctx.guild else 0, task_name, action_type, config
        )
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task action remove")
    @permissions.check()
    async def task_action_remove(
        self: Self, ctx: fluxer.Message, task_name: str, index: int
    ) -> None:
        """
        Remove an action from a task.

        Args:
            ctx: The command context.
            task_name: The name of the task.
            index: 1-based index of the action.
        """
        result = await core_automation.task_action_remove(
            ctx.guild.id if ctx.guild else 0, task_name, index
        )
        await ctx.reply(result["message"])

    @fluxer.Cog.command(name="task action reorder")
    @permissions.check()
    async def task_action_reorder(self: Self, ctx: fluxer.Message, task_name: str) -> None:
        """
        Reorder task actions.

        Args:
            ctx: The command context.
            task_name: The name of the task.
        """
        result = await core_automation.task_action_reorder(
            ctx.guild.id if ctx.guild else 0, task_name
        )
        await ctx.reply(result["message"])


async def setup(bot: FluxerClient) -> None:
    """
    Load the Scheduler cog.

    Args:
        bot (FluxerClient): The Fluxer bot instance.
    """
    await bot.add_cog(Automation(bot))
