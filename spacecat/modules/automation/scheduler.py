"""
This module is used for scheduling events to happen in the future.

These events can be either simple reminders messages for users, or more
complex actions that are available to server administrators.

Simple reminders should make use of the `Reminder` class and associated
repository, storing basic information that pertain to where and when to
send the message as well as what should be sent.

The `Event` class is utilised for more complex scheduling tasks, making
use of modular `Actions` to build upon its instruction set. Events
should have configurable time scheduling, being able to set specific
times and repeat intervals.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Generic, Self, TypeVar

if TYPE_CHECKING:
    import sqlite3

    import discord


class Repeat(Enum):
    """
    Represents the time at which a reminder should be repeated.

    Attributes:
        No (int): No repeats will be set.
        Hourly (int): The reminder will be set to repeat every hour.
        Daily (int): The reminder will be set to repeat every day.
        Weekly (int): The reminder will be set to repeat every week.
    """

    No = 0
    Hourly = 3600
    Daily = 86400
    Weekly = 604800


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
        user: discord.User,
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


class Event:
    """
    A representation of an Event.

    This class holds information required about an event, such as the
    name and guild for access, as well as dispatch time and intervals
    in order to determine when to execute the actions.
    """

    def __init__(
        self: Event,
        id_: uuid.UUID,
        guild_id: int,
        dispatch_time: int,
        last_run_time: int | None,
        repeat_interval: Repeat,
        repeat_multiplier: int,
        name: str,
        description: str,
        *,
        is_paused: bool,
    ) -> None:
        """
        Initializes a new Event instance.

        Args:
            id_ (uuid.UUID): The unique identifier of the event.
            guild_id (int): The ID of the guild.
            dispatch_time (int): The time when the event should be
                dispatched.
            last_run_time (int | None): The time when the event was last
                run, or None if it has not been run yet.
            repeat_interval (Repeat): The interval at which the event
                should repeat.
            repeat_multiplier (int): The multiplier for the repeat
                interval.
            name (str): The name of the event.
            description (str): The description of the event.
            is_paused (bool): Indicates whether the event is paused or
                not.

        Returns:
            None
        """
        self.id: uuid.UUID = id_
        self.guild_id = guild_id
        self.dispatch_time: int = dispatch_time
        self.last_run_time = last_run_time
        self.repeat_interval: Repeat = repeat_interval
        self.repeat_multiplier = repeat_multiplier
        self.name = name
        self.description = description
        self.is_paused = is_paused

    @classmethod
    def create_new(
        cls: type[Self],
        guild_id: int,
        dispatch_time: int,
        repeat_interval: Repeat,
        repeat_multiplier: int,
        name: str,
    ) -> Self:
        """
        Creates a new Event using the minimum required values.

        Args:
            guild_id (int): The ID of the guild.
            dispatch_time (int): The time when the event should be
                dispatched.
            repeat_interval (Repeat): The interval at which the event
                should repeat.
            repeat_multiplier (int): The multiplier for the repeat
                interval.
            name (str): The name of the event.

        Returns:
            Self: A new instance of the class.
        """
        return cls(
            uuid.uuid4(),
            guild_id,
            dispatch_time,
            None,
            repeat_interval,
            repeat_multiplier,
            name,
            "",
            is_paused=False,
        )


class EventRepository:
    """
    Repository for managing events.

    This class provides common functionality for managing event objects,
    such as adding, retrieving, and removing event objects from a
    database.
    """

    def __init__(self: EventRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a new instance of the EventRepository class.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        self.db = database
        cursor = self.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, guild_id INTEGER, "
            "dispatch_time INTEGER, last_run_time INTEGER, repeat_interval TEXT, "
            "repeat_multiplier INTEGER, is_paused INTEGER, name TEXT, description TEXT)"
        )
        self.db.commit()

    def get_all(self: Self) -> list[Event]:
        """Get list of all reminders."""
        results = self.db.cursor().execute("SELECT * FROM events").fetchall()
        reminders = []
        for result in results:
            event = self._result_to_event(result)
            reminders.append(event)
        return reminders

    def get_by_id(self: Self, id_: uuid.UUID) -> Event | None:
        """
        Retrieves an event by its unique identifier.

        Args:
            id_ (uuid.UUID): The unique identifier of the event.

        Returns:
            Event | None: The event object with the specified
                identifier, or None if the event is not found.
        """
        result = (
            self.db.cursor().execute("SELECT * FROM events WHERE id=?", (str(id_),)).fetchone()
        )
        return self._result_to_event(result)

    def get_by_name(self: Self, name: str) -> Event | None:
        """
        Retrieves an event by its name.

        Args:
            name (str): The name of the event.

        Returns:
            Event | None: The event object with the specified name, or
                None if the event is not found.
        """
        result = self.db.cursor().execute("SELECT * FROM events WHERE name=?", (name,)).fetchone()
        return self._result_to_event(result) if result else None

    def get_by_guild(self: Self, guild_id: int) -> list[Event]:
        """
        Retrieves a list of all events in a guild.

        Args:
            guild_id (int): The ID of the guild.

        Returns:
            list[Event]: A list of Events that exist in the guild.
        """
        cursor = self.db.cursor()
        values = (guild_id,)
        cursor.execute("SELECT * FROM events WHERE guild_id=?", values)
        results = cursor.fetchall()
        return [
            event for result in results if (event := self._result_to_event(result)) is not None
        ]

    def get_by_name_in_guild(self: Self, name: str, guild_id: int) -> Event | None:
        """
        Retrieves an event by its name within a specific guild.

        Args:
            name (str): The name of the event.
            guild_id (int): The ID of the guild.

        Returns:
            Event | None: The event object with the specified name
                within the guild, or None if the event is not found.
        """
        values = (name, guild_id)
        result = (
            self.db.cursor()
            .execute("SELECT * FROM events WHERE name=? AND guild_id=?", values)
            .fetchone()
        )
        return self._result_to_event(result) if result else None

    def get_repeating(self: Self) -> list[Event]:
        """
        Retrieves a list of all repeating events.

        Returns:
            list[Event]: A list of Events that are set to repeat.
        """
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM events WHERE NOT repeat_interval=? AND is_paused=0", ("No",))
        results = cursor.fetchall()
        return [
            event for result in results if (event := self._result_to_event(result)) is not None
        ]

    def get_before_timestamp(self: Self, timestamp: int) -> list[Event]:
        """
        Retrieves all events set to dispatch before a given timestamp.

        Args:
            timestamp (int): The timestamp to compare against the
                dispatch_time column in the events table.

        Returns:
            list[Event]: A list of Event objects that have a
                dispatch time before the given timestamp.
        """
        cursor = self.db.cursor()
        results = cursor.execute(
            "SELECT * FROM events WHERE dispatch_time < ? ORDER BY dispatch_time", (timestamp,)
        ).fetchall()
        return [
            event for result in results if (event := self._result_to_event(result)) is not None
        ]

    def get_first_non_repeating_before_timestamp(self: Self, timestamp: int) -> Event | None:
        """
        Retrieves the first non-repeating event that is set to dispatch.

        This function is useful for getting the next scheduled event

        Args:
            timestamp (int): The timestamp to compare against the
                dispatch_time column in the events table.

        Returns:
            Event | None: The first non-repeating event that is
                scheduled to dispatch before the given timestamp,
                or None if no such event exists.
        """
        cursor = self.db.cursor()
        result = cursor.execute(
            "SELECT * FROM events "
            'WHERE dispatch_time < ? AND repeat_interval="No" '
            "ORDER BY dispatch_time",
            (timestamp,),
        ).fetchone()
        return self._result_to_event(result)

    def add(self: Self, event: Event) -> None:
        """
        Inserts a new event into the events table in the database.

        Args:
            event (Event): The event object to be inserted.

        Returns:
            None
        """
        cursor = self.db.cursor()
        values = (
            str(event.id),
            event.guild_id,
            event.dispatch_time,
            event.last_run_time,
            event.repeat_interval.name,
            event.repeat_multiplier,
            int(event.is_paused),
            event.name,
            event.description,
        )
        cursor.execute("INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", values)
        self.db.commit()

    def update(self: Self, event: Event) -> None:
        """
        Updates an existing event in the database.

        Args:
            event (Event): The event object to update.
        """
        cursor = self.db.cursor()
        values = (
            event.guild_id,
            event.dispatch_time,
            event.last_run_time,
            event.repeat_interval.name,
            event.repeat_multiplier,
            int(event.is_paused),
            event.name,
            event.description,
            str(event.id),
        )
        cursor.execute(
            "UPDATE events SET guild_id=?, dispatch_time=?, last_run_time=?, repeat_interval=?, "
            "repeat_multiplier=?, is_paused=?, name=?, description=? WHERE id=?",
            values,
        )
        self.db.commit()

    def remove(self: Self, id_: uuid.UUID) -> None:
        """
        Remove an event based on its ID.

        Parameters:
            id_ (uuid.UUID): The ID of the event to be removed.
        """
        self.db.cursor().execute("DELETE FROM events WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_event(result: tuple) -> Event | None:
        """
        Convert a database result tuple to an Event object.

        Args:
            result (tuple): A database result tuple.

        Returns:
            Event | None: An Event object representing the event data,
                or None if the result is None.
        """
        return Event(
            uuid.UUID(result[0]),
            result[1],
            result[2],
            result[3],
            Repeat[result[4]],
            result[5],
            result[7],
            result[8],
            is_paused=bool(result[6]),
        )


class Action(ABC):
    """
    Abstract class representing an action.

    This class provides common functionality for actions, such as
    storing the unique identifier as well as providing the methods for
    displaying action information.
    """

    def __init__(self: Action, id_: uuid.UUID) -> None:
        """
        Initialize an instance of the Action class.

        Args:
            id_ (uuid.UUID): The unique identifier for the action.
        """
        self.id: uuid.UUID = id_

    @abstractmethod
    def get_name(self: Self) -> str:
        """
        Get the display name of the action.

        Returns:
            str: The display name of the action.
        """

    @abstractmethod
    def get_formatted_output(self: Self) -> str:
        """
        Get the formatted output text of the action.

        This is to be used when a response needs to be generated to the
        user to explain what the action will do.

        Returns:
            str: The formatted output text.
        """


T_Action = TypeVar("T_Action", bound=Action)


class ActionRepository(ABC, Generic[T_Action]):
    """
    Abstract class for repositories that store and retrieve actions.

    This class provides common functionality for managing actions, such
    as adding, retrieving, and removing actions from a database.

    Attributes:
        db (sqlite3.Connection): The database connection object.
    """

    def __init__(self: ActionRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a new instance of the ActionRepository class.

        Args:
            database (sqlite3.Connection): The database connection object.
        """
        self.db = database

    @abstractmethod
    def get_by_id(self: Self, id_: uuid.UUID) -> T_Action:
        """
        Retrieves an action by its unique identifier.

        Args:
            id_ (uuid): The unique identifier of the action.

        Returns:
            T_Action: The action object with the specified identifier.
        """

    @abstractmethod
    def add(self: Self, action: T_Action) -> None:
        """
        Adds an action to the repository.

        Args:
            action (T_Action): The action to be added.
        """

    @abstractmethod
    def remove(self: Self, id_: uuid.UUID) -> None:
        """
        Remove an item from the repository by its unique identifier.

        Args:
            id_ (uuid.UUID): The unique identifier of the item to be
                removed.
        """
