"""
This module is responsible for scheduling reminders messages for users.

It provides an interface to create and manage reminder reminder tasks,
which are then stored in a database and called upon when they are due.
The provided scheduler then handles the dispatch of these tasks, which
are to be handled by the bot.
"""

from __future__ import annotations

import asyncio
import datetime
import time
import uuid
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    import sqlite3

    import discord
    import discord.ext.commands


class Reminder:
    """
    Represents a reminder that a user can set.

    Reminders are utilised by users to remind them of something at a set
    time. This class encapsulates all the data required to perform a
    reminder call, including the time and message to send.
    """

    def __init__(
        self: Reminder,
        id_: uuid.UUID,
        user_id: int,
        guild_id: int,
        channel_id: int,
        message_id: int,
        creation_time: int,
        dispatch_time: int,
        message: str,
    ) -> None:
        """
        Initializes a new instance of the Reminder class.

        Args:
            self (Reminder): The Reminder instance being initialized.
            id_ (uuid.UUID): The unique identifier for the reminder.
            user_id (int): The ID of the user associated with the
                reminder.
            guild_id (int): The ID of the guild associated with the
                reminder.
            channel_id (int): The ID of the channel where the reminder
                was created.
            message_id (int): The ID of the message that triggered the
                reminder.
            creation_time (int): The timestamp when the reminder was
                created.
            dispatch_time (int): The timestamp when the reminder should
                be dispatched.
            message (str): The message content of the reminder.

        Returns:
            None
        """
        self.id: uuid.UUID = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.creation_time = creation_time
        self.dispatch_time = dispatch_time
        self.message = message

    @classmethod
    def create_new(
        cls: type[Reminder],
        user: discord.abc.User,
        guild: discord.Guild,
        channel: discord.TextChannel,
        confirmation_message: discord.Message,
        creation_time: int,
        dispatch_time: int,
        message: str,
    ) -> Reminder:
        """
        Creates a new instance of the Reminder class.

        Args:
            cls (type[Reminder]): The class object.
            user (discord.User): The associated user
            guild (discord.Guild): The associated guild.
            channel (discord.TextChannel): The channel where the
                reminder was created.
            confirmation_message (discord.Message): The message that
                triggered the reminder.
            creation_time (int): The timestamp when the reminder was
                created.
            dispatch_time (int): The timestamp when the reminder should
                be dispatched.
            message (str): The message content of the reminder.

        Returns:
            Reminder: The newly created Reminder instance.
        """
        return cls(
            uuid.uuid4(),
            user.id,
            guild.id,
            channel.id,
            confirmation_message.id,
            creation_time,
            dispatch_time,
            message,
        )


class ReminderRepository:
    """
    Repository class for managing reminders.

    This class provides common functionality for managing reminders
    objects, such as adding, retrieving, and removing reminders objects
    from a database.
    """

    def __init__(self: ReminderRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a new instance of the ReminderRepository class.

        Args:
            database (sqlite3.Connection): The database connection object.
        """
        self.db = database
        cursor = self.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, user_id INTEGER, "
            "guild_id INTEGER, channel_id INTEGER, message_id INTEGER, creation_time INTEGER, "
            "dispatch_time INTEGER, message TEXT)"
        )
        self.db.commit()

    def get_all(self: Self) -> list[Reminder]:
        """Get list of all reminders."""
        results = self.db.cursor().execute("SELECT * FROM reminders").fetchall()
        return [self._result_to_reminder(result) for result in results]

    def get_by_id(self: Self, id_: uuid.UUID) -> Reminder:
        """
        Get a reminder by its ID.

        Args:
            id_ (uuid.UUID): The ID of the reminder.

        Returns:
            Reminder: The reminder object with the given ID.
        """
        result = (
            self.db.cursor().execute("SELECT * FROM reminders WHERE id=?", (str(id_),)).fetchone()
        )
        return Reminder(
            result[0], result[1], result[2], result[3], result[4], result[5], result[6], result[7]
        )

    def get_by_guild(self: Self, guild_id: int) -> list[Reminder]:
        """
        Get a list of reminders associated with a specific guild.

        Parameters:
            guild_id (int): The ID of the guild.

        Returns:
            list[Reminder]: A list of reminders associated with the
                guild.
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM reminders WHERE guild_id=?", (guild_id,))
        results = cursor.fetchall()
        return [self._result_to_reminder(result) for result in results]

    def get_by_guild_and_user(self: Self, guild_id: int, user_id: int) -> list[Reminder]:
        """
        Get a list of reminders associated with a specific guild and user.

        Parameters:
            guild_id (int): The ID of the guild.
            user_id (int): The ID of the user.

        Returns:
            list[Reminder]: A list of Reminder objects associated with
                the guild and user, ordered by dispatch time.
        """
        # Get reminder by guild and reminder name
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM reminders WHERE guild_id=? AND user_id=? ORDER BY dispatch_time",
            (guild_id, user_id),
        )
        results = cursor.fetchall()
        return [self._result_to_reminder(result) for result in results]

    def get_before_timestamp(self: Self, timestamp: int) -> list[Reminder]:
        """
        Retrieves reminders set to dispatch before a given timestamp.

        Args:
            timestamp (int): The timestamp to compare against the
                dispatch_time column in the reminders table.

        Returns:
            list[Reminder]: A list of Reminder objects that have a
                dispatch time before the given timestamp, ordered by
                dispatch time.
        """
        result = (
            self.db.cursor()
            .execute(
                "SELECT * FROM reminders WHERE dispatch_time < ? ORDER BY dispatch_time",
                (timestamp,),
            )
            .fetchall()
        )
        return [self._result_to_reminder(result) for result in result]

    def add(self: Self, reminder: Reminder) -> None:
        """
        Inserts a new reminder into the reminders table.

        Args:
            reminder (Reminder): The reminder object to be inserted.
        """
        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO reminders VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(reminder.id),
                reminder.user_id,
                reminder.guild_id,
                reminder.channel_id,
                reminder.message_id,
                reminder.creation_time,
                reminder.dispatch_time,
                reminder.message,
            ),
        )
        self.db.commit()

    def update(self: Self, reminder: Reminder) -> None:
        """
        Updates an existing reminder in the reminders table.

        Args:
            reminder (Reminder): The reminder object to be updated.
        """
        cursor = self.db.cursor()
        values = (
            reminder.user_id,
            reminder.guild_id,
            reminder.channel_id,
            reminder.message_id,
            reminder.creation_time,
            reminder.dispatch_time,
            reminder.message,
            str(reminder.id),
        )
        cursor.execute(
            "UPDATE reminders SET user_id=?, guild_id=?, channel_id=?, message_id=?"
            "creation_time=?, dispatch_time=?, message=? WHERE id=?",
            values,
        )
        self.db.commit()

    def remove(self: Self, id_: uuid.UUID) -> None:
        """
        Remove a reminder from the reminders table.

        Args:
            id_ (uuid.UUID): The ID of the reminder to be removed.
        """
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM reminders WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_reminder(result: tuple) -> Reminder:
        return Reminder(
            uuid.UUID(result[0]),
            result[1],
            result[2],
            result[3],
            result[4],
            result[5],
            result[6],
            result[7],
        )


class ReminderService:
    """A layer that handles the dispatching of reminders."""

    def __init__(
        self: ReminderService, bot: discord.ext.commands.Bot, reminders: ReminderRepository
    ) -> None:
        """
        Initializes a new instance of the ReminderService class.

        Args:
            bot (discord.ext.commands.Bot): The bot instance.
            reminders (ReminderRepository): The reminder repository.

        Returns:
            None
        """
        self.bot = bot
        self.reminders = reminders

    def dispatch(self: Self, reminder: Reminder) -> None:
        """Sends a reminder dispatch alert with the Reminder object.

        Args:
            reminder: The reminder to dispatch
        """
        self.bot.dispatch("reminder", reminder)
        self.reminders.remove(reminder.id)


class ReminderScheduler:
    """A scheduler that handles the automated dispatching of reminders.

    Its usage is as simple as passing a reminder through the schedule
    function. The reminder should have data pertaining to the execution
    time, which should then process the action through the reminder
    service.
    """

    def __init__(
        self: ReminderScheduler, reminder_service: ReminderService, cache_release_time: int = -1
    ) -> None:
        """
        Initializes a new instance of the ReminderScheduler class.

        Args:
            reminder_service (ReminderService): The reminder service to
                use for dispatching reminders.
            cache_release_time (int, optional): The time in seconds for
                how close to the expected dispatch time the event must
                be to be loaded in memory. A lower value reduces the
                amount of memory used at any given time, but also
                requires more frequent database lookups for new events.
                Defaults to -1.
        """
        self.reminder_service = reminder_service
        self.cache_release_time = cache_release_time
        self.scheduled_reminders: dict[uuid.UUID, asyncio.Task] = {}

    def is_scheduled(self: Self, reminder: Reminder) -> bool:
        """Returns true if the reminder is currently scheduled.

        Args:
            reminder: The reminder to query.

        Returns:
            bool: True if event is scheduled
        """
        return reminder in self.scheduled_reminders

    def schedule(self: Self, reminder: Reminder) -> None:
        """Schedules a reminder to run at its dispatch time.

        If a cache release time has been specified as a class attribute,
        the reminder will not be added if the set dispatch time is
        greater than the cache release time. This is a memory saving
        measure.

        Args:
            reminder: The reminder to schedule
        """
        self.scheduled_reminders[reminder.id] = asyncio.create_task(self._task_loop(reminder))

    def schedule_saved(self: Self) -> None:
        """Loads all reminders that are due to be scheduled.

        If a cache release time is specified, we highly recommend
        setting up a recurring task that triggers this method at the
        same interval. All reminders are loaded in from reminder
        repository if cache_release_time set to -1.
        """
        events = (
            self.reminder_service.reminders.get_all()
            if self.cache_release_time < 0
            else self.reminder_service.reminders.get_before_timestamp(
                int(
                    datetime.datetime.now(tz=datetime.timezone.utc).timestamp()
                    + self.cache_release_time
                )
            )
        )
        for event in events:
            if not self.is_scheduled(event):
                self.schedule(event)

    def unschedule(self: Self, reminder: Reminder) -> None:
        """Stops a specified reminder from dispatching.

        Args:
            reminder: The reminder to unschedule
        """
        self.scheduled_reminders[reminder.id].cancel()
        self.scheduled_reminders.pop(reminder.id)

    def unschedule_all(self: Self) -> None:
        """Stops all reminders from dispatching."""
        for event in self.scheduled_reminders.values():
            event.cancel()
        self.scheduled_reminders.clear()

    async def _task_loop(self: Self, reminder: Reminder) -> None:
        """An indefinite loop to dispatch reminders.

        Args:
            reminder: The event to run
        """
        while True:
            if reminder.dispatch_time >= time.time():
                await asyncio.sleep(reminder.dispatch_time - time.time())
            await self._dispatch(reminder)

    async def _dispatch(self: Self, reminder: Reminder) -> None:
        """Triggers the dispatching of the reminder.

        Args:
            reminder: The event to dispatch
        """
        self.unschedule(reminder)
        self.reminder_service.dispatch(reminder)
        await asyncio.sleep(0)
