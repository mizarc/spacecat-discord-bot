"""
Fluxer-specific scheduler module.

This module provides Fluxer platform-specific implementations of the core
scheduler functionality, including commands and event handlers for reminders
and scheduled events.
"""

from __future__ import annotations

import asyncio
import datetime
import sqlite3
import time
from typing import TYPE_CHECKING, Self

import fluxer

from spacecat.core.features.scheduler import (
    Event,
    EventRepository,
    EventScheduler,
    EventService,
    MessageAction,
    MessageActionRepository,
    Reminder,
    ReminderRepository,
    ReminderScheduler,
    ReminderService,
    Repeat,
)
from spacecat.platforms.fluxer.helpers import permissions

if TYPE_CHECKING:
    from spacecat.platforms.fluxer.client import FluxerClient


class FluxerReminderService(ReminderService):
    """Fluxer-specific implementation of ReminderService."""

    async def dispatch_reminder(self: FluxerReminderService, reminder: Reminder) -> None:
        """
        Dispatches a reminder in Fluxer.

        Args:
            reminder (Reminder): The reminder to dispatch.
        """
        try:
            # Get the channel
            channel = await self.bot.fetch_channel(reminder.channel_id)
            if not channel:
                return

            # Create reminder message
            reminder_text = (
                f"**Reminder!** <@{reminder.user_id}>, "
                f"you asked me to remind you: {reminder.message}"
            )

            # Send the reminder
            await channel.send(reminder_text)

        except Exception as e:
            print(f"Error dispatching Fluxer reminder {reminder.id}: {e}")


class FluxerMessageAction(MessageAction):
    """Fluxer-specific implementation of MessageAction."""

    async def execute(self: FluxerMessageAction, bot) -> None:
        """
        Executes the message action in Fluxer.

        Args:
            bot: The bot instance.
        """
        try:
            # Get the channel
            channel = await bot.fetch_channel(self.channel_id)
            if not channel:
                return

            # Send the message
            await channel.send(self.message)

        except Exception as e:
            print(f"Error executing Fluxer message action {self.id}: {e}")


class Scheduler(fluxer.Cog):
    """Schedule events and reminders for Fluxer."""

    def __init__(self: Scheduler, bot: FluxerClient) -> None:
        """
        Initializes a new instance of the Scheduler class.

        Args:
            bot (FluxerClient): The Fluxer bot instance.
        """
        self.bot: FluxerClient = bot
        self.database = sqlite3.connect("data/spacecat.db")

        # Initialize reminder system
        self.reminders = ReminderRepository(self.database)
        self.reminder_service = FluxerReminderService(self.bot, self.reminders)
        self.reminder_scheduler = ReminderScheduler(self.reminder_service, 90000)

        # Initialize event system
        self.events = EventRepository(self.database)
        self.event_actions = MessageActionRepository(self.database)
        self.event_service = EventService(self.bot, self.events)
        self.event_service.add_action_repository(self.event_actions)
        self.event_scheduler = EventScheduler(self.event_service, 90000)

    async def cog_load(self: Self) -> None:
        """Sets up event loading and starts schedulers on cog load."""
        # Start the schedulers
        await self.reminder_scheduler.start()
        await self.event_scheduler.start()

        # Load existing reminders and events
        await self.reminder_scheduler.schedule_saved()
        await self.event_scheduler.schedule_saved()

    async def cog_unload(self: Self) -> None:
        """Stops schedulers on cog unload."""
        await self.reminder_scheduler.stop()
        await self.event_scheduler.stop()

    @fluxer.Cog.command()
    @permissions.check()
    async def remindme(
        self: Self,
        ctx: fluxer.Message,
        message: str,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        weeks: int = 0,
    ) -> None:
        """
        Sets a reminder to send a message after an amount of time.

        Args:
            ctx: The command context.
            message (str): The message to be sent in the reminder.
            seconds (int): The number of seconds.
            minutes (int): The number of minutes.
            hours (int): The number of hours.
            days (int): The number of days.
            weeks (int): The number of weeks.
        """
        # Calculate total time in seconds
        total_seconds = (
            seconds + (minutes * 60) + (hours * 3600) + (days * 86400) + (weeks * 604800)
        )

        if total_seconds <= 0:
            await ctx.reply("Please specify a valid time duration!")
            return

        dispatch_time = int(time.time()) + total_seconds

        # Create the reminder
        reminder = Reminder.create_new(
            ctx.author.id,
            ctx.guild.id if ctx.guild else 0,
            ctx.channel.id,
            ctx.message.id,
            int(time.time()),
            dispatch_time,
            message,
        )

        # Save and schedule the reminder
        self.reminders.add(reminder)
        await self.reminder_scheduler.schedule(reminder)

        # Send confirmation
        time_str = self._format_duration(total_seconds)
        await ctx.reply(f"✅ Reminder set for {time_str} from now!")

    @fluxer.Cog.command()
    @permissions.check()
    async def reminders(self: Self, ctx) -> None:
        """
        Lists all your reminders in the current server.

        Args:
            ctx: The command context.
        """
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server!")
            return

        reminders = self.reminders.get_by_guild_and_user(ctx.guild.id, ctx.author.id)
        if not reminders:
            await ctx.reply("You have no active reminders!")
            return

        # Format reminders
        reminder_list = []
        for i, reminder in enumerate(reminders, 1):
            time_until = reminder.dispatch_time - time.time()
            if time_until > 0:
                time_str = self._format_duration(int(time_until))
                reminder_list.append(
                    f"{i}. {reminder.message[:50]}{'...' if len(reminder.message) > 50 else ''} - {time_str}"
                )

        if reminder_list:
            await ctx.reply("**Your active reminders:**\n" + "\n".join(reminder_list))
        else:
            await ctx.reply("You have no active reminders!")

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

    @fluxer.Cog.command()
    @permissions.check()
    async def event(
        self: Self,
        ctx,
        action: str = None,
        name: str = None,
        time_str: str = None,
        date_str: str = None,
        message: str = None,
    ) -> None:
        """
        Manage scheduled events.

        Usage:
        !event create <name> <time> <date> - Create a new event
        !event list - List all events
        !event addmessage <name> <message> - Add message action to event
        !event delete <name> - Delete an event

        Args:
            ctx: The command context.
            action (str): The action to perform (create, list, addmessage, delete).
            name (str): The event name.
            time_str (str): The time in HH:MM format.
            date_str (str): The date in DD/MM/YYYY format.
            message (str): The message for message actions.
        """
        if not action:
            await self._event_help(ctx)
            return

        action = action.lower()

        if action == "create":
            await self._event_create(ctx, name, time_str, date_str)
        elif action == "list":
            await self._event_list(ctx)
        elif action == "addmessage":
            await self._event_add_message(ctx, name, message)
        elif action == "delete":
            await self._event_delete(ctx, name)
        else:
            await self._event_help(ctx)

    async def _event_create(self: Self, ctx, name: str, time_str: str, date_str: str) -> None:
        """Creates a new event."""
        if not all([name, time_str, date_str]):
            await ctx.reply("Usage: `!event create <name> <time> <date>`")
            return

        if not ctx.guild:
            await ctx.reply("This command can only be used in a server!")
            return

        try:
            # Parse time and date
            event_time = self._parse_time(time_str)
            event_date = self._parse_date(date_str)

            # Combine into datetime
            event_datetime = datetime.datetime.combine(event_date, event_time)

            # Check if time is in the past
            if event_datetime.timestamp() < time.time():
                await ctx.reply("Cannot create events in the past!")
                return

            # Create the event
            event = Event.create_new(
                ctx.guild.id,
                int(event_datetime.timestamp()),
                Repeat.No,
                1,
                name,
                "Scheduled event",
            )

            # Save and schedule the event
            self.events.add(event)
            await self.event_scheduler.schedule(event)

            await ctx.reply(
                f"✅ Event '{name}' created for {event_datetime.strftime('%d/%m/%Y %H:%M')}!"
            )

        except ValueError as e:
            await ctx.reply(f"Invalid time/date format: {str(e)}")

    async def _event_list(self: Self, ctx) -> None:
        """Lists all events in the server."""
        if not ctx.guild:
            await ctx.reply("This command can only be used in a server!")
            return

        events = self.events.get_by_guild(ctx.guild.id)
        if not events:
            await ctx.reply("No events scheduled in this server!")
            return

        event_list = []
        for event in events:
            if event.dispatch_time > time.time():
                time_str = datetime.datetime.fromtimestamp(event.dispatch_time).strftime(
                    "%d/%m/%Y %H:%M"
                )
                event_list.append(f"• **{event.name}** - {time_str}")

        if event_list:
            await ctx.reply("**Scheduled Events:**\n" + "\n".join(event_list))
        else:
            await ctx.reply("No upcoming events!")

    async def _event_add_message(self: Self, ctx, name: str, message: str) -> None:
        """Adds a message action to an event."""
        if not all([name, message]):
            await ctx.reply("Usage: `!event addmessage <name> <message>`")
            return

        if not ctx.guild:
            await ctx.reply("This command can only be used in a server!")
            return

        event = self.events.get_by_name_in_guild(name, ctx.guild.id)
        if not event:
            await ctx.reply(f"Event '{name}' not found!")
            return

        # Create the message action
        action = FluxerMessageAction.create_new(event.id, ctx.channel.id, message)
        self.event_actions.add(action)

        await ctx.reply(f"✅ Message action added to event '{name}'!")

    async def _event_delete(self: Self, ctx, name: str) -> None:
        """Deletes an event."""
        if not name:
            await ctx.reply("Usage: `!event delete <name>`")
            return

        if not ctx.guild:
            await ctx.reply("This command can only be used in a server!")
            return

        event = self.events.get_by_name_in_guild(name, ctx.guild.id)
        if not event:
            await ctx.reply(f"Event '{name}' not found!")
            return

        # Remove the event and its actions
        self.event_service.remove_event(event)

        await ctx.reply(f"✅ Event '{name}' has been deleted!")

    async def _event_help(self: Self, ctx) -> None:
        """Shows help for the event command."""
        help_text = """
        **Event Commands:**
        • `!event create <name> <time> <date>` - Create a new event
        • `!event list` - List all events
        • `!event addmessage <name> <message>` - Add message action to event
        • `!event delete <name>` - Delete an event
        
        **Examples:**
        • `!event create "Daily Update" 09:00 25/12/2025`
        • `!event addmessage "Daily Update" "Good morning everyone!"`
        • `!event delete "Daily Update"`
        
        **Time Format:** HH:MM (24-hour)
        **Date Format:** DD/MM/YYYY
        """
        await ctx.reply(help_text)

    def _format_duration(self: Self, seconds: int) -> str:
        """Formats a duration in seconds into a human-readable string."""
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            days = seconds // 86400
            return f"{days} day{'s' if days != 1 else ''}"

    def _parse_time(self: Self, time_str: str) -> datetime.time:
        """Parses a time string in HH:MM format."""
        try:
            hours, minutes = map(int, time_str.split(":"))
            if not (0 <= hours <= 23 and 0 <= minutes <= 59):
                raise ValueError("Invalid time range")
            return datetime.time(hours, minutes)
        except (ValueError, AttributeError):
            raise ValueError("Time must be in HH:MM format (24-hour)")

    def _parse_date(self: Self, date_str: str) -> datetime.date:
        """Parses a date string in DD/MM/YYYY format."""
        try:
            day, month, year = map(int, date_str.split("/"))
            return datetime.date(year, month, day)
        except (ValueError, AttributeError):
            raise ValueError("Date must be in DD/MM/YYYY format")


async def setup(bot: FluxerClient) -> None:
    """
    Load the Scheduler cog.

    Args:
        bot (FluxerClient): The Fluxer bot instance.
    """
    await bot.add_cog(Scheduler(bot))
