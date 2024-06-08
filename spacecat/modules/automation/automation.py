"""
This module provides a cog for creating and scheduling events.

This provides a basic command for users to create reminders, as well as
a complex event command structure that allows for the creation,
modification, and execution of actions.
"""

from __future__ import annotations

import datetime
import sqlite3
import time
from typing import TYPE_CHECKING, Self

import discord
import discord.ext.commands
import pytz
from discord import TextChannel, app_commands
from discord.ext import commands, tasks

from spacecat.helpers import constants
from spacecat.helpers.views import EmptyPaginatedView, PaginatedView
from spacecat.modules.administration import Administration, ServerSettingsRepository
from spacecat.modules.automation import actions, event_scheduler, reminder_scheduler
from spacecat.modules.automation.event_scheduler import Event, EventScheduler, Repeat
from spacecat.modules.automation.reminder_scheduler import Reminder

if TYPE_CHECKING:
    from spacecat.spacecat import SpaceCat


class InvalidTimeError(Exception):
    """Raised when a string cannot be converted to a valid time."""


class InvalidDateError(Exception):
    """Raised when a string cannot be converted to a valid date."""


class Automation(commands.Cog):
    """Schedule events to run at a later date."""

    MAX_EVENTS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="The server has reach its event limit. "
        "Delete an event before adding another one.",
    )

    MAX_ACTIONS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="This event has reached its action limit. "
        "Delete an action before adding another one.",
    )

    PAST_TIME_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="You cannot set a date and time in the past. "
        "Remember that time is in 24 hour format by default. "
        "Add `am/pm` if you would like to work with 12 hour time.",
    )

    NAME_ALREADY_EXISTS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="An event of that name already exists.",
    )

    EVENT_DOES_NOT_EXIST_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="An event of that name does not exist.",
    )

    INVALID_TIME_ENUM = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="Selected time is invalid. Ensure time is in `hours:minutes` format. "
        "You may add `am/pm` to the end to use 12 hour time.",
    )

    INVALID_DATE_ENUM = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description="Selected date is invalid. Ensure date is in `date/month/year` format.",
    )

    def __init__(self: Automation, bot: SpaceCat) -> None:
        """
        Initializes a new instance of the Automation class.

        Args:
            bot (SpaceCat): The SpaceCat bot instance.
        """
        self.bot: SpaceCat = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.reminders = reminder_scheduler.ReminderRepository(self.database)
        self.reminder_service = reminder_scheduler.ReminderService(self.bot, self.reminders)
        self.reminder_scheduler = reminder_scheduler.ReminderScheduler(
            self.reminder_service, 90000
        )
        self.events = event_scheduler.EventRepository(self.database)
        self.event_actions = event_scheduler.EventActionRepository(self.database)
        self.event_service = self.init_event_service()
        self.event_scheduler = event_scheduler.EventScheduler(self.event_service, 90000)

    async def cog_load(self: Self) -> None:
        """Sets up event loading and config values on cog load."""
        self.load_upcoming_events.start()

        # Add config keys
        config = self.bot.instance.get_config()
        if "automation" not in config:
            config["automation"] = {}
        if "max_reminders_per_player" not in config["automation"]:
            config["automation"]["max_reminders_per_player"] = 5
        if "max_events_per_server" not in config["automation"]:
            config["automation"]["max_events_per_server"] = 10
        if "max_actions_per_event" not in config["automation"]:
            config["automation"]["max_actions_per_event"] = 15
        self.bot.instance.save_config(config)

    def init_event_service(self: Self) -> event_scheduler.EventService:
        """
        Initializes event repositories and services.

        Returns:
            event_scheduler.EventService: The initialized EventService
                instance.
        """
        event_service = event_scheduler.EventService(self.bot, self.event_actions, self.events)

        action_repositories = [
            actions.MessageActionRepository(self.database),
            actions.BroadcastActionRepository(self.database),
            actions.VoiceKickActionRepository(self.database),
            actions.VoiceMoveActionRepository(self.database),
            actions.ChannelPrivateActionRepository(self.database),
            actions.ChannelPublicActionRepository(self.database),
        ]

        for action_repository in action_repositories:
            event_service.add_action_repository(action_repository)
        return event_service

    @tasks.loop(hours=24)
    async def load_upcoming_reminders(self: Self) -> None:
        """
        Loads upcoming reminders at regular intervals.

        This function is a task loop that runs every 24 hours.
        It is responsible for loading upcoming reminders into the cache
        to ensure that they can be dispatched.
        """
        self.reminder_scheduler.schedule_saved()

    @tasks.loop(hours=24)
    async def load_upcoming_events(self: Self) -> None:
        """
        Loads upcoming events at regular intervals.

        This function is a task loop that runs every 24 hours.
        It is responsible for loading upcoming events into the cache
        to ensure that they can be dispatched.
        """
        self.event_scheduler.schedule_saved()

    @commands.Cog.listener()
    async def on_reminder(self: Self, reminder: reminder_scheduler.Reminder) -> None:
        """
        Listener that sends a message reminder to a user.

        Args:
            reminder (reminder_scheduler.Reminder): The reminder action
                containing information about the reminder.
        """
        channel = await self.bot.fetch_channel(reminder.channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DEFAULT} Reminder!",
            description=f"<@{reminder.user_id}>**, <t:{int(reminder.creation_time)}:R> "
            f"you asked me to remind you:** \n {reminder.message}",
        )
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(
                label="Go to original message",
                url=f"https://discord.com/channels/{reminder.guild_id}/"
                f"{reminder.channel_id}/{reminder.message_id}",
            )
        )
        await channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message_action(self: Self, action: actions.MessageAction) -> None:
        """
        Listener that sends a message action to a text channel.

        Args:
            action (actions.MessageAction): The message action
                containing information about the message to be sent.
        """
        channel = await self.bot.fetch_channel(action.text_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        await channel.send(action.message)

    @commands.Cog.listener()
    async def on_broadcast_action(self: Self, action: actions.BroadcastAction) -> None:
        """
        Listener that sends a broadcast action to a text channel.

        Args:
            action (actions.BroadcastAction): The broadcast action
                containing information about the message to be sent.
        """
        channel = await self.bot.fetch_channel(action.text_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        await channel.send(
            embed=discord.Embed(
                colour=constants.EmbedStatus.SPECIAL.value,
                title=f"{action.title}",
                description=f"{action.message}",
            )
        )

    @commands.Cog.listener()
    async def on_voice_kick_action(self: Self, action: actions.VoiceKickAction) -> None:
        """
        Listener that handles the kicking of users from the channel.

        Args:
            action (actions.VoiceKickAction): The voice kick action
                containing information about the voice channel to be
                kicked from.
        """
        voice_channel = await self.bot.fetch_channel(action.voice_channel_id)
        if not isinstance(voice_channel, discord.VoiceChannel):
            return

        for member in voice_channel.members:
            await member.move_to(None)

    @commands.Cog.listener()
    async def on_voice_move_action(self: Self, action: actions.VoiceMoveAction) -> None:
        """
        Listener that handles the moving of users to a channel.

        Args:
            action (actions.VoiceMoveAction): The voice move action
                containing information about the current and new voice
                channels.
        """
        current_channel = await self.bot.fetch_channel(action.current_voice_channel_id)
        if not isinstance(current_channel, discord.VoiceChannel):
            return

        new_channel = await self.bot.fetch_channel(action.new_voice_channel_id)
        if not isinstance(new_channel, discord.VoiceChannel):
            return

        for member in current_channel.members:
            await member.move_to(new_channel)

    @commands.Cog.listener()
    async def on_channel_private_action(self: Self, action: actions.ChannelPrivateAction) -> None:
        """
        Listener that handles the setting of a channel to private.

        Args:
            self (Self): The instance of the class.
            action (actions.ChannelPrivateAction): The channel private
                action containing information about the channel.

        Returns:
            None
        """
        channel = await self.bot.fetch_channel(action.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return

        await channel.set_permissions(
            channel.guild.default_role, connect=False, view_channel=False
        )

    @commands.Cog.listener()
    async def on_channel_public_action(self: Self, action: actions.ChannelPublicAction) -> None:
        """
        Listener that handles the setting of a channel to public.

        Args:
            action (actions.ChannelPublicAction): The channel public
                action containing information about the channel.
        """
        channel = await self.bot.fetch_channel(action.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return

        await channel.set_permissions(channel.guild.default_role, connect=None, view_channel=None)

    @app_commands.command()
    async def remindme(
        self: Self,
        interaction: discord.Interaction,
        message: str,
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        weeks: int = 0,
        months: int = 0,
        years: int = 0,
    ) -> None:
        """
        Sets a reminder to send a message after an amount of time.

        Args:
            interaction (discord.Interaction): The user interaction.
            message (str): The message to be sent in the reminder.
            seconds (int, optional): The number of seconds.
            minutes (int, optional): The number of minutes.
            hours (int, optional): The number of hours.
            days (int, optional): The number of days.
            weeks (int, optional): The number of weeks.
            months (int, optional): The number of months.
            years (int, optional): The number of years.
        """
        # Send alert if interaction is not in a text channel within a guild.
        if interaction.guild is None or not isinstance(interaction.channel, TextChannel):
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild's text channel.",
                )
            )
            return

        # Send alert if over reminder limit.
        if await self.is_over_reminder_limit(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="You have reached your reminder limit. "
                    "Delete one before adding another one.",
                )
            )
            return

        timestamp = await self.to_seconds(seconds, minutes, hours, days, weeks, months, years)
        dispatch_time = timestamp + time.time()

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Reminder has been set for "
            f"{await self.format_datetime(datetime.timedelta(seconds=timestamp))}",
        )
        await interaction.response.send_message(embed=embed)

        reminder = Reminder.create_new(
            interaction.user,
            interaction.guild,
            interaction.channel,
            await interaction.original_response(),
            int(time.time()),
            int(dispatch_time),
            message,
        )
        self.reminders.add(reminder)
        self.reminder_scheduler.schedule(reminder)

    reminder_group = app_commands.Group(
        name="reminder", description="Configure existing reminders."
    )
    event_group = app_commands.Group(
        name="event", description="Allows you to run an function at a scheduled time."
    )
    event_add_group = app_commands.Group(
        parent=event_group, name="add", description="Add a new scheudled event."
    )

    @reminder_group.command(name="list")
    async def reminder_list(self: Self, interaction: discord.Interaction, page: int = 1) -> None:
        """
        List all reminders in the current guild.

        Args:
            interaction (discord.Interaction): The user's interaction.
            page (int, optional): The page number of the reminders to
                display. Defaults to 1.
        """
        # Send alert if interaction is not in a guild.
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        # Send alert if no reminders exist.
        reminders = self.reminders.get_by_guild_and_user(interaction.guild.id, interaction.user.id)
        if not reminders:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="You have no set reminders.",
                )
            )
            return

        # Reminders into pretty listings
        reminder_listings = [
            f"{reminder.message[0:30]} | <t:{int(reminder.dispatch_time)}:R>"
            for reminder in reminders
        ]

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Your Reminders",
        )
        paginated_view = PaginatedView(
            embed, f"{len(reminders)} available", reminder_listings, 5, page
        )
        await paginated_view.send(interaction)

    @reminder_group.command(name="remove")
    async def reminder_remove(self: Self, interaction: discord.Interaction, index: int) -> None:
        """
        Removes a reminder based on the provided index.

        Args:
            interaction (discord.Interaction): The user's interaction.
            index (int): The index of the reminder to be removed.
        """
        # Send alert if interaction is not in a guild.
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        reminders = self.reminders.get_by_guild_and_user(interaction.guild.id, interaction.user.id)
        if not reminders:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="You have no set reminders.",
                )
            )
            return

        try:
            reminder = reminders[index - 1]
        except IndexError:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="A reminder by that index doesn't exist.",
                )
            )
            return

        self.reminder_scheduler.unschedule(reminder)
        self.reminders.remove(reminder.id)

        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Reminder at index {index} has been removed.",
            )
        )
        return

    @event_group.command(name="list")
    async def event_list(self: Self, interaction: discord.Interaction, page: int = 1) -> None:
        """
        Lists all scheduled events in the current guild.

        Parameters:
            interaction (discord.Interaction): The user's interaction.
            page (int, optional): The page number of the events list to
                display. Defaults to 1.
        """
        # Send alert if interaction is not in a guild.
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        events = self.events.get_by_guild(interaction.guild.id)
        if not events:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no scheduled events",
            )
            await interaction.response.send_message(embed=embed)
            return

        # Format playlist songs into pretty listings
        event_listings = []
        for event in events:
            listing = f"{event.name}"
            if not event.dispatch_time:
                listing += " | `Expired`"
            elif event.repeat_interval != Repeat.No and event.is_paused:
                listing += f" | `Repeating {event.repeat_interval.name} (Paused)`"
            elif event.repeat_interval != Repeat.No:
                listing += f" | `Repeating {event.repeat_interval.name}`"
            event_listings.append(listing)

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value, title=f"{constants.EmbedIcon.MUSIC} Events"
        )
        paginated_view = PaginatedView(embed, f"{len(events)} available", event_listings, 5, page)
        await paginated_view.send(interaction)

    @event_group.command(name="create")
    async def event_create(  # noqa: PLR0911
        self: Self,
        interaction: discord.Interaction,
        name: str,
        time_string: str,
        date_string: str,
        repeat: Repeat = Repeat.No,
        repeat_multiplier: int = 1,
    ) -> None:
        """
        Create a new event in the guild.

        Parameters:
            - interaction: The user interaction.
            - name: The name of the event.
            - time_string: The time string in the format "HH:MM".
            - date_string: The date string in the format "DD/MM/YYYY".
            - repeat: The repeat interval of the event.
                Defaults to Repeat.No.
            - repeat_multiplier: The multiplier for the repeat interval.
                Defaults to 1.
        """
        # Send alert if interaction is not in a guild.
        if interaction.guild is None or interaction.channel is not TextChannel:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return None

        if await self.is_over_event_limit(interaction.guild.id):
            await interaction.response.send_message(embed=self.MAX_EVENTS_EMBED)
            return None

        event = self.events.get_by_name_in_guild(name, interaction.guild.id)
        if event:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="An event by that name already exists.",
            )
            await interaction.response.send_message(embed=embed)
            return None

        try:
            selected_datetime = await self.fetch_future_datetime(
                interaction.guild, time_string, date_string
            )
        except InvalidTimeError:
            return await interaction.response.send_message(embed=self.INVALID_TIME_ENUM)
        except InvalidDateError:
            return await interaction.response.send_message(embed=self.INVALID_DATE_ENUM)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return None

        event = Event.create_new(
            interaction.guild.id,
            int(selected_datetime.timestamp()),
            repeat,
            repeat_multiplier,
            name,
        )
        self.events.add(event)
        self.event_scheduler.schedule(event)

        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Event `{name}` has been created, set to trigger on "
                f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                f"at {selected_datetime.hour}:{selected_datetime.minute}"
                f"{await self.format_repeat_message(repeat, repeat_multiplier)} Use `/event add` "
                f"to assign actions.",
            )
        )
        return None

    @event_group.command(name="destroy")
    async def event_destroy(self: Self, interaction: discord.Interaction, event_name: str) -> None:
        """
        Destroys an event by name.

        Events

        Args:
            interaction (discord.Interaction): The user interaction.
            event_name (str): The name of the event to be destroyed.
        """
        # Send alert if interaction is not in a guild.
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name_in_guild(event_name, interaction.guild.id)
        if not event:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="An event by that name does not exist.",
            )
            await interaction.response.send_message(embed=embed)
            return

        self.event_service.remove_event(event)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Event '{event_name}' has been deleted.",
            )
        )
        return

    @event_group.command(name="view")
    async def event_view(
        self: Self, interaction: discord.Interaction, name: str, page: int = 1
    ) -> None:
        """
        View the details of an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event.
            page (int, optional): The page number of the actions to
                display. Defaults to 1.
        """
        # Send alert if interaction is not in a guild.
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"Event '{event.name}'",
            description=event.description,
        )

        # Embed category for time and interval
        time_fields = []
        timezone = await self.get_guild_timezone(interaction.guild.id)
        dt_format = "%-H:%M:%S %-d/%-m/%Y"

        if event.dispatch_time:
            dispatch_time = (
                datetime.datetime.fromtimestamp(event.dispatch_time)
                .astimezone(timezone)
                .strftime(dt_format)
            )
            label = "Initial Time" if event.repeat_interval is not Repeat.No else "Dispatch Time"
            time_fields.append(f"**{label}:** {dispatch_time}")

        repeating = await self.format_repeat_message_alt(
            event.repeat_interval, event.repeat_multiplier
        )
        time_fields.append(f"**Repeating:** {repeating}{' (Paused)' if event.is_paused else ''}")

        if event.last_run_time:
            time_fields.append(
                f"**Last Run:** "
                f"{datetime.datetime.fromtimestamp(event.last_run_time)
                   .astimezone(timezone).strftime(dt_format)}"
            )

        if event.repeat_interval is not Repeat.No:
            next_run_time = datetime.datetime.fromtimestamp(
                EventScheduler.calculate_next_run(event)
            ).astimezone(timezone)
            time_fields.append(
                f"**Next Run:** {'N/A' if event.is_paused else next_run_time.strftime(dt_format)}"
            )

        embed.add_field(name="Trigger", value="\n".join(time_fields), inline=False)

        # Embed category for actions
        actions = self.event_service.get_actions(event)
        action_fields = [f"{action.get_formatted_output()}" for action in actions]

        if actions:
            paginated_view = PaginatedView(embed, "Actions", action_fields, 5, page)
        else:
            paginated_view = EmptyPaginatedView(embed, "Actions", "No actions have been set.")
        await paginated_view.send(interaction)

    @event_add_group.command(name="message")
    async def event_add_message(
        self: Self,
        interaction: discord.Interaction,
        event_name: str,
        channel: discord.TextChannel,
        message: str,
    ) -> None:
        """
        Adds a message action to an event.

        Args:
            interaction: The user interaction.
            event_name: The name of the event to add the action to.
            channel: The text channel where the message will be sent.
            message: The content of the message to be sent.
        """
        # Send alert if interaction is not in a guild.
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name_in_guild(event_name, interaction.guild.id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = actions.MessageAction.create_new(channel.id, message)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Message action has been added to event '{event_name}'",
            )
        )

    @event_add_group.command(name="broadcast")
    async def event_add_broadcast(
        self: Self,
        interaction: discord.Interaction,
        event_name: str,
        channel: discord.TextChannel,
        title: str,
        message: str,
    ) -> None:
        """
        Adds a broadcast action to an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            event_name (str): The name of the event to add the
                action to.
            channel (discord.TextChannel): The channel where the
                broadcast will be sent.
            title (str): The title of the broadcast.
            message (str): The message of the broadcast.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name_in_guild(event_name, interaction.guild.id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = actions.BroadcastAction.create_new(channel.id, title, message)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Broadcast action has been added to event '{event_name}'",
            )
        )

    @event_add_group.command(name="voicekick")
    async def event_add_voicekick(
        self: Self,
        interaction: discord.Interaction,
        event_name: str,
        voice_channel: discord.VoiceChannel,
    ) -> None:
        """
        Adds a Voice Kick action to an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            event_name (str): The name of the event.
            voice_channel (discord.VoiceChannel): The voice channel to
                kick users from.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name_in_guild(event_name, interaction.guild.id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = actions.VoiceKickAction.create_new(voice_channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Voice Kick action has been added to event '{event_name}'",
            )
        )

    @event_add_group.command(name="voicemove")
    async def event_add_voicemove(
        self: Self,
        interaction: discord.Interaction,
        event_name: str,
        current_channel: discord.VoiceChannel,
        new_channel: discord.VoiceChannel,
    ) -> None:
        """
        Adds a Voice Move action to an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            event_name (str): The name of the event.
            current_channel (discord.VoiceChannel): The voice channel
                where the action should be performed.
            new_channel (discord.VoiceChannel): The voice channel where
                the users should be moved to.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name_in_guild(event_name, interaction.guild.id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = actions.VoiceMoveAction.create_new(current_channel.id, new_channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Voice Move action has been added to event '{event_name}'",
            )
        )

    @event_add_group.command(name="channelprivate")
    async def event_add_channelprivate(
        self: Self,
        interaction: discord.Interaction,
        event_name: str,
        channel: discord.abc.GuildChannel,
    ) -> None:
        """
        Add a Channel Private action to an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            event_name (str): The name of the event.
            channel (discord.abc.GuildChannel): The channel to be made
                private.

        Returns:
            None
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name_in_guild(event_name, interaction.guild.id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = actions.ChannelPrivateAction.create_new(channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Channel Private action has been added to event '{event_name}'",
            )
        )

    @event_add_group.command(name="channelpublic")
    async def event_add_channelpublic(
        self: Self,
        interaction: discord.Interaction,
        event_name: str,
        channel: discord.abc.GuildChannel,
    ) -> None:
        """
        Add a ChannelPublic action to an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            event_name (str): The name of the event to add the
                action to.
            channel (discord.abc.GuildChannel): The channel to set to
                public.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name_in_guild(event_name, interaction.guild.id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = actions.ChannelPublicAction.create_new(channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Channel Public action has been added to event '{event_name}'",
            )
        )

    @event_group.command(name="remove")
    async def event_remove(
        self: Self, interaction: discord.Interaction, name: str, index: int
    ) -> None:
        """
        Removes an action from an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event to remove the action from.
            index (int): The index of the action to be removed.
        """
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        action = self.event_service.get_action_at_position(event, index - 1)
        self.event_service.remove_action(event, action)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Action '{action.get_name()}' at index {index} has been removed "
                "from event {event.name}.",
            )
        )

    @event_group.command(name="reorder")
    async def event_reorder(
        self: Self,
        interaction: discord.Interaction,
        name: str,
        original_position: int,
        new_position: int,
    ) -> None:
        """
        Reorders an action within an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event.
            original_position (int): The original position of the
                action.
            new_position (int): The new position of the action.
        """
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        action = self.event_service.get_action_at_position(event, original_position)
        self.event_service.reorder_action(event, original_position, new_position)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Action of type '{action.get_name()}' in event '{name}' "
                f"has been moved from position `{original_position}` to `{new_position}`",
            )
        )
        return

    @event_group.command(name="pause")
    async def event_pause(self: Self, interaction: discord.Interaction, name: str) -> None:
        """
        Pauses a given event to not run on dipatch.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event.
        """
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        if event.repeat_interval == Repeat.No:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="You cannot pause one time events. "
                    "You may reschedule or remove it instead.",
                )
            )
            return

        if event.is_paused:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"Event '{name}' is already paused.",
                )
            )
            return

        event.is_paused = True
        self.events.update(event)
        self.event_scheduler.unschedule(event)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Event '{name}' has been paused and will not run on its next "
                "scheduled run time.",
            )
        )
        return

    @event_group.command(name="resume")
    async def event_resume(self: Self, interaction: discord.Interaction, name: str) -> None:
        """
        Resumes a paused event.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event to resume.
        """
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        if not event.is_paused:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"Event '{name}' is not paused.",
                )
            )
            return

        event.is_paused = False
        self.events.update(event)
        self.event_scheduler.schedule(event)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Event {name} has now been resumed and will run at the "
                "scheduled time.",
            )
        )
        return

    @event_group.command(name="rename")
    async def event_rename(
        self: Self, interaction: discord.Interaction, name: str, new_name: str
    ) -> None:
        """
        Rename an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The current name of the event.
            new_name (str): The new name for the event.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        if any(event.name == new_name for event in self.events.get_by_guild(interaction.guild.id)):
            await interaction.response.send_message(embed=self.NAME_ALREADY_EXISTS_EMBED)
            return

        event.name = new_name
        self.events.update(event)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Event {name} has been renamed to {new_name}.",
            )
        )
        return

    @event_group.command(name="description")
    async def event_description(
        self: Self, interaction: discord.Interaction, name: str, description: str
    ) -> None:
        """
        Sets the description of an event.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event.
            description (str): The new description for the event.
        """
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        event.description = description
        self.events.update(event)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Description has been set for event {name}.",
            )
        )
        return

    @event_group.command(name="reschedule")
    async def event_reschedule(
        self: Self, interaction: discord.Interaction, name: str, time_string: str, date_string: str
    ) -> None:
        """
        Reschedules an event with a new time and date.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event to reschedule.
            time_string (str): The new time for the event.
            date_string (str): The new date for the event.
        """
        if interaction.guild is None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description="This command can only be used in a guild.",
                )
            )
            return

        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        try:
            selected_datetime = await self.fetch_future_datetime(
                interaction.guild, time_string, date_string
            )
        except InvalidTimeError:
            await interaction.response.send_message(embed=self.INVALID_TIME_ENUM)
            return
        except InvalidDateError:
            await interaction.response.send_message(embed=self.INVALID_DATE_ENUM)
            return
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event.dispatch_time = int(selected_datetime.timestamp())
        self.events.update(event)
        self.event_scheduler.unschedule(event)
        self.event_scheduler.schedule(event)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Event '{name}' has been rescheduled to "
                f"{date_string} at {time_string}.",
            )
        )
        return

    @event_group.command(name="interval")
    async def event_interval(
        self: Self,
        interaction: discord.Interaction,
        name: str,
        interval: Repeat,
        multiplier: int = 1,
    ) -> None:
        """
        Sets the interval for a scheduled event.

        Args:
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event.
            interval (Repeat): The interval for the event.
            multiplier (int, optional): The multiplier for the interval.
                Defaults to 1.
        """
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        event.repeat_interval = interval
        event.repeat_multiplier = multiplier
        self.events.update(event)

        if self.event_scheduler.is_scheduled(event):
            self.event_scheduler.schedule(event)
            self.event_scheduler.unschedule(event)

        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Interval has been changed for event {name}.",
            )
        )
        return

    @event_group.command(name="trigger")
    async def event_trigger(self: Self, interaction: discord.Interaction, name: str) -> None:
        """
        Manually triggers a specified event.

        Args:
            self (Self): The instance of the class.
            interaction (discord.Interaction): The user interaction.
            name (str): The name of the event to trigger.
        """
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(
                embed=discord.Embed(
                    colour=constants.EmbedStatus.FAIL.value,
                    description=f"An event going by the name '{name}' does not exist.",
                )
            )
            return

        self.event_service.dispatch_event(event)
        await interaction.response.send_message(
            embed=discord.Embed(
                colour=constants.EmbedStatus.YES.value,
                description=f"Event '{event.name}' has been manually triggered.",
            )
        )
        return

    async def fetch_future_datetime(
        self: Self, guild: discord.Guild, time_string: str, date_string: str | None = None
    ) -> datetime.datetime:
        """
        Fetches a future datetime based on the given guild, time string, and optional date string.

        Args:
            self (Self): The instance of the class.
            guild (discord.Guild): The guild to fetch the future datetime for.
            time_string (str): The time string in the format HH:MM.
            date_string (str | None, optional): The date string in the
                format YYYY-MM-DD. Defaults to None.

        Returns:
            datetime.datetime: The future datetime.
        """
        time_ = await self.parse_time(time_string)
        if date_string is None:
            date = datetime.datetime.now(tz=pytz.utc).date()
        else:
            date = await self.parse_date(date_string)

        timezone = await self.get_guild_timezone(guild.id)
        combined = timezone.localize(datetime.datetime.combine(date, time_))
        timestamp = combined.timestamp()
        if timestamp < time.time():
            combined.replace(day=combined.day + 1)
        return combined

    async def get_guild_timezone(self: Self, guild_id: int) -> pytz.BaseTzInfo:
        """
        Retrieves the timezone for a specific guild.

        Args:
            guild_id (int): The ID of the guild.

        Returns:
            pytz.BaseTzInfo: The timezone for the guild. If no timezone
                is available, UTC is returned.
        """
        administration = self.bot.get_cog("Administration")
        if not isinstance(administration, Administration):
            msg = (
                f"The fetched cog is not of type {Administration.__name__}, got "
                f"{type(administration).__name__}"
            )
            raise TypeError(msg)
        servers_settings: ServerSettingsRepository = administration.server_settings
        server_settings = servers_settings.get_by_guild(guild_id)
        if server_settings.timezone is not None:
            return pytz.timezone(server_settings.timezone)
        return pytz.utc

    async def is_over_reminder_limit(self: Self, guild_id: int, user_id: int) -> bool:
        """
        Check if user has too many reminders in a guild.

        Args:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user.

        Returns:
            bool: True if the number of reminders exceeds the maximum
                limit, False otherwise.
        """
        config = self.bot.instance.get_config()
        return (
            len(self.reminders.get_by_guild_and_user(guild_id, user_id))
            > config["automation"]["max_reminders_per_player"]
        )

    async def is_over_event_limit(self: Self, guild_id: int) -> bool:
        """
        Check if the number of events in a guild exceeds the limit.

        Args:
            guild_id (int): The ID of the guild.

        Returns:
            bool: True if the number of events exceeds the maximum
                limit, False otherwise.
        """
        config = self.bot.instance.get_config()
        return (
            len(self.events.get_by_guild(guild_id)) > config["automation"]["max_events_per_server"]
        )

    async def is_over_action_limit(self: Self, event: Event) -> bool:
        """
        Check if the number of actions in an event exceeds the limit.

        Args:
            event (Event): The event to check.

        Returns:
            bool: True if the number of actions exceeds the maximum
                limit, False otherwise.
        """
        config = self.bot.instance.get_config()
        return (
            len(self.event_service.get_actions(event))
            > config["automation"]["max_actions_per_event"]
        )

    @staticmethod
    async def parse_time(time_string: str) -> datetime.time:
        """
        Parses a time string and converts it into a time object.

        Args:
            time_string (str): The time string to parse. Must be in
                "HH:MM AM/PM" format.

        Returns:
            datetime.time: The parsed time object.
        """
        split = time_string.split(":")

        if split[-1][-2:] == "am":
            split[-1] = split[-1][:-2]
        elif time_string[-2:] == "pm":
            split[-1] = split[-1][:-2]
            split[0] = str(int(split[0]) + 12)

        try:
            return datetime.time(hour=int(split[0]), minute=int(split[1]))
        except ValueError as error:
            raise InvalidTimeError from error

    @staticmethod
    async def parse_date(date_string: str) -> datetime.date:
        """
        Parses a date string and returns a `datetime.date` object.

        Args:
            date_string (str): The date string to be parsed. The string
                should be in the format "DD/MM/YYYY".

        Returns:
            datetime.date: The parsed `datetime.date` object.
        """
        split = date_string.split("/")
        if not split:
            split = date_string.split(":")
        if not split:
            raise InvalidDateError

        try:
            return datetime.date(day=int(split[0]), month=int(split[1]), year=int(split[2]))
        except ValueError as error:
            raise InvalidDateError from error

    @staticmethod
    async def to_seconds(
        seconds: int = 0,
        minutes: int = 0,
        hours: int = 0,
        days: int = 0,
        weeks: int = 0,
        months: int = 0,
        years: int = 0,
    ) -> int:
        """
        Calculates the total number of seconds based on the given time.

        Args:
            seconds (int, optional): The number of seconds.
                Defaults to 0.
            minutes (int, optional): The number of minutes.
                Defaults to 0.
            hours (int, optional): The number of hours.
                Defaults to 0.
            days (int, optional): The number of days.
                Defaults to 0.
            weeks (int, optional): The number of weeks.
                Defaults to 0.
            months (int, optional): The number of months.
                Defaults to 0.
            years (int, optional): The number of years.
                Defaults to 0.

        Returns:
            int: The total number of seconds.
        """
        total = seconds
        total += minutes * 60
        total += hours * 3600
        total += days * 86400
        total += weeks * 604800
        total += months * 2592000
        total += years * 31536000
        return total

    @staticmethod
    async def format_datetime(timedelta: datetime.timedelta) -> str:
        """
        Formats a given timedelta object into a string representation.

        This is formatted as "X years, X months, X weeks, X days,
        X hours, X minutes, X seconds", with each type of interval only
        existing if required.

        Args:
            timedelta (datetime.timedelta): The timedelta object to be
                formatted.

        Returns:
            str: The formatted string representation of the time
                duration.
        """
        days, seconds = timedelta.days, timedelta.seconds
        years, days = divmod(days, 365)
        months, days = divmod(days, 30)
        weeks, days = divmod(days, 7)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)

        components = [
            (years, "year"),
            (months, "month"),
            (weeks, "week"),
            (days, "day"),
            (hours, "hour"),
            (minutes, "minute"),
            (seconds, "second"),
        ]

        return ", ".join(
            f"{value} {name}{'s' if value > 1 else ''}" for value, name in components if value
        )

    @staticmethod
    async def format_repeat_message(interval: Repeat, multiplier: int) -> str:
        """
        Formats a repeat message based on the given interval.

        This is formatted as ", repeating every <x> <y>.", with x being
        the multiplier if the multiplier is more than one, and y being
        the internval.

        Args:
            interval (Repeat): The repeat interval.
            multiplier (int): The repeat multiplier.

        Returns:
            str: The formatted repeat message, using the interval to
                determine the message.
        """
        if interval == Repeat.Hourly:
            interval_string = "hour"
        elif interval == Repeat.Daily:
            interval_string = "day"
        elif interval == Repeat.Weekly:
            interval_string = "week"
        else:
            return "."

        if multiplier:
            return f", repeating every {interval_string}."
        return f", repeating every {multiplier} {interval_string}s."

    @staticmethod
    async def format_repeat_message_alt(interval: Repeat, multiplier: int) -> str:
        """
        Alternative repeat message based on the given interval.

        This is formatted as "Every <x> <y>.", with x being the
        multiplier if more than one, and y being the interval.

        Args:
            interval (Repeat): The repeat interval.
            multiplier (int): The repeat multiplier.

        Returns:
            str: The formatted repeat message, using the interval and
            multiplier to determine the message.
        """
        if multiplier == 1:
            return interval.name

        if interval == Repeat.Hourly:
            interval_string = "hours"
        elif interval == Repeat.Daily:
            interval_string = "days"
        elif interval == Repeat.Weekly:
            interval_string = "weeks"
        else:
            return ""
        return f"Every {multiplier} {interval_string}"


async def setup(bot: SpaceCat) -> None:
    """
    Set up the bot by adding the Automation cog.

    Args:
        bot (Bot): The bot instance.
    """
    await bot.add_cog(Automation(bot))
