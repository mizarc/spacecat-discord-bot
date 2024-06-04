"""
This module is used for scheduling events to happen in the future.

The `Event` class is utilised for complex scheduling tasks, making
use of modular `Actions` to build upon its instruction set. Events
should have configurable time scheduling, being able to set specific
times and repeat intervals.
"""

from __future__ import annotations

import asyncio
import datetime
import math
import time
import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Generic, Self, TypeVar, get_args

import discord
import discord.ext.commands

if TYPE_CHECKING:
    import sqlite3


FIVE_MINUTES_IN_SECONDS = 300


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
    def get_name() -> str:
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


class EventAction:
    """
    Represents an action associated with an event.

    This allows a self sorting way to order actions within the event,
    making use of ids that point to the action that comes before in
    order to build a chain of actions within the event.
    """

    def __init__(
        self: EventAction,
        id_: uuid.UUID,
        event_id: uuid.UUID,
        action_type: str,
        action_id: uuid.UUID,
        previous_id: uuid.UUID,
    ) -> None:
        """
        Initializes a new instance of the EventAction class.

        Args:
            id_ (uuid.UUID): The unique identifier of the event action.
            event_id (uuid.UUID): The unique identifier of the event.
            action_type (str): The type of the action.
            action_id (uuid.UUID): The unique identifier of the action.
            previous_id (uuid.UUID): The unique identifier of the
                previous action.
        """
        self.id: uuid.UUID = id_
        self.event_id: uuid.UUID = event_id
        self.action_type: str = action_type
        self.action_id: uuid.UUID = action_id
        self.previous_id: uuid.UUID | None = previous_id

    @classmethod
    def create_new(
        cls: type[EventAction],
        event_id: uuid.UUID,
        action_type: str,
        action_id: uuid.UUID,
        previous_id: uuid.UUID,
    ) -> EventAction:
        """
        Creates a new Event Action to append to the end of an Event.

        Args:
            cls (type[EventAction]): The class object of the EventAction
                class.
            event_id (uuid.UUID): The unique identifier of the event.
            action_type (str): The type of the action.
            action_id (uuid.UUID): The unique identifier of the action.
            previous_id (uuid.UUID): The unique identifier of the
                previous action.

        Returns:
            EventAction: A new instance of the EventAction class.
        """
        return cls(uuid.uuid4(), event_id, action_type, action_id, previous_id)


class EventActionRepository:
    """
    Repository for managing event actions.

    This class provides common functionality for managing event actions,
    such as adding, retrieving, and removing event actions from a
    database.
    """

    def __init__(self: EventActionRepository, database: sqlite3.Connection) -> None:
        """
        Initializes a new instance of the EventActionRepository class.

        Args:
            database (sqlite3.Connection): The database connection.
        """
        self.db = database
        cursor = self.db.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS event_actions "
            "(id TEXT PRIMARY KEY, event_id INTEGER, action_type TEXT, action_id INTEGER, "
            "previous_id TEXT)"
        )

    def get_by_id(self: Self, id_: uuid.UUID) -> EventAction | None:
        """
        Retrieves an event action by its unique identifier.

        Args:
            id_ (uuid.UUID): The unique identifier of the event action.

        Returns:
            EventAction | None: The event action object with the
                specified identifier, or None if the event action is not
                found.
        """
        result = (
            self.db.cursor()
            .execute("SELECT * FROM event_actions WHERE id=?", (str(id_),))
            .fetchone()
        )
        return self._result_to_event_action(result)

    def get_by_event(self: Self, event_id: uuid.UUID) -> list[EventAction]:
        """
        Retrieves EventAction objects associated with a specific event.

        Args:
            event_id (uuid.UUID): The unique identifier of the event.

        Returns:
            list[EventAction]: A list of EventAction objects associated
                with the event.
        """
        results = (
            self.db.cursor()
            .execute("SELECT * FROM event_actions WHERE event_id=?", (str(event_id),))
            .fetchall()
        )
        return [self._result_to_event_action(result) for result in results]

    def get_by_action(self: Self, action_id: uuid.UUID) -> EventAction | None:
        """
        Retrieves an EventAction object by a linked action's identifier.

        Args:
            action_id (uuid.UUID): The unique identifier of the action.

        Returns:
            EventAction | None: The EventAction object with the
                specified action identifier, or None if the object is
                not found.
        """
        result = (
            self.db.cursor()
            .execute("SELECT * FROM event_actions WHERE action_id=?", (str(action_id),))
            .fetchone()
        )
        return self._result_to_event_action(result)

    def get_by_action_in_event(
        self: Self, action_id: uuid.UUID, event_id: uuid.UUID
    ) -> EventAction | None:
        """
        Retrieves an EventAction object by both event and action id.

        Args:
            action_id (uuid.UUID): The unique identifier of the action.
            event_id (uuid.UUID): The unique identifier of the event.

        Returns:
            EventAction | None: The EventAction object with the
                specified action and event identifiers, or None if the object is
                not found.
        """
        result = (
            self.db.cursor()
            .execute(
                "SELECT * FROM event_actions WHERE action_id=? AND event_id=?",
                (str(action_id), str(event_id)),
            )
            .fetchone()
        )
        return self._result_to_event_action(result)

    def get_by_previous(self: Self, id_: uuid.UUID) -> EventAction | None:
        """
        Retrieves an EventAction object by its previous_id.

        Args:
            id_ (uuid.UUID): The unique identifier of the previous
                EventAction.

        Returns:
            EventAction | None: The EventAction object with the
                specified previous_id, or None if the object is not
                found.
        """
        result = (
            self.db.cursor()
            .execute("SELECT * FROM event_actions WHERE previous_id=?", (str(id_),))
            .fetchone()
        )
        return self._result_to_event_action(result)

    def add(self: Self, event_action: EventAction) -> None:
        """
        Adds an EventAction object to the database.

        Args:
            event_action (EventAction): The EventAction object to be
                added.
        """
        values = (
            str(event_action.id),
            str(event_action.event_id),
            event_action.action_type,
            str(event_action.action_id),
            str(event_action.previous_id),
        )
        cursor = self.db.cursor()
        cursor.execute("INSERT INTO event_actions VALUES (?, ?, ?, ?, ?)", values)
        self.db.commit()

    def update(self: Self, event_action: EventAction) -> None:
        """
        Updates an existing EventAction object in the database.

        Args:
            event_action (EventAction): The EventAction object to be
                updated.
        """
        values = (
            event_action.event_id,
            event_action.action_type,
            event_action.action_id,
            event_action.previous_id,
            event_action.id,
        )
        self.db.cursor().execute(
            "UPDATE event_actions SET event_id=?, action_type=?, action_id=?, previous_id=? "
            "WHERE id=?",
            values,
        )
        self.db.commit()

    def remove(self: Self, id_: uuid.UUID) -> None:
        """
        Remove an EventAction object by its unique identifier.

        Args:
            id_ (uuid.UUID): The unique identifier of the EventAction
                object to be removed.
        """
        self.db.cursor().execute("DELETE FROM event_actions WHERE id=?", (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_event_action(result: tuple) -> EventAction:
        """
        Converts a database result tuple to an EventAction object.

        Args:
            result (tuple): A tuple fetched from the database containing
                the data for creating an EventAction object. The tuple
                should have the following structure: (event_id (str),
                action_id (str), action_type, previous_id (str),
                id (str))

        Returns:
            EventAction: An EventAction object created from the result
                tuple.
        """
        return EventAction(
            uuid.UUID(result[0]),
            uuid.UUID(result[1]),
            result[2],
            uuid.UUID(result[3]),
            uuid.UUID(result[4]),
        )


class EventService:
    """
    Manages events and their associated actions.

    This provides easy to use methods for adding, removing and
    dispatching events. Actions can easily be associated and configured
    within the events.
    """

    def __init__(
        self: EventService,
        bot: discord.ext.commands.Bot,
        event_actions: EventActionRepository,
        events: EventRepository,
    ) -> None:
        """
        Initializes an instance of the EventService class.

        Args:
            bot (discord.ext.commands.Bot): The Discord bot instance.
            event_actions (EventActionRepository): The repository for event actions.
            events (EventRepository): The repository for events.
        """
        self.bot = bot
        self.events: EventRepository = events
        self.actions_collection: dict[str, ActionRepository] = {}
        self.event_actions: EventActionRepository = event_actions

    def add_action_repository(self: Self, action_repository: ActionRepository) -> None:
        """Adds an ActionRepository to utilise as storage."""
        # This looks like a nightmare, but all it does it get the name of the name of the action
        # that the repository manages.
        self.actions_collection[
            get_args(type(action_repository).__orig_bases__[0])[0].get_name()  # type: ignore a
        ] = action_repository

    def remove_event(self: Self, event: Event) -> None:
        """Removes an event and all associated actions from storage.

        Args:
            event (Event): The selected event to remove from the
                collection.
        """
        found_event_actions = self.event_actions.get_by_event(event.id)
        for event_action in found_event_actions:
            actions = self.actions_collection.get(event_action.action_type)
            if actions is None:
                continue
            actions.remove(event_action.action_id)
            self.event_actions.remove(event_action.id)
        self.events.remove(event.id)

    def get_actions(self: Self, event: Event) -> list[Action]:
        """Returns all Actions associated with an event.

        Args:
            event: The selected event to query

        Returns:
            list of Action: The Actions associated with the event
        """
        event_action_links = {}
        event_actions = self.event_actions.get_by_event(event.id)
        for event_action in event_actions:
            event_action_links[event_action.previous_id] = event_action

        # Sort actions using linked previous_id
        sorted_actions: list[Action] = []
        next_event_action = event_action_links.get(uuid.UUID(int=0))
        while next_event_action is not None:
            actions = self.actions_collection.get(next_event_action.action_type, None)
            if actions is None:
                continue
            sorted_actions.append(actions.get_by_id(next_event_action.action_id))
            next_event_action = event_action_links.get(next_event_action.id)

        return sorted_actions

    def get_action_at_position(self: Self, event: Event, index: int) -> Action:
        """Returns the action of an event at a specified index.

        Args:
            event: The event to get the action from
            index: The position of the action

        Returns:
            Action: The action at the position in the event
        """
        actions = self.get_actions(event)
        return actions[index]

    def add_action(self: Self, event: Event, action: Action) -> None:
        """Links a new action to a specified event.

        The action is added to the Actions collection, with a new
        EventActions object being created for the purposes of
        associating the action with an Event.

        Args:
            event: The event to link the action to
            action: The action to be linked
        """
        actions = self.actions_collection.get(action.get_name())
        if actions is None:
            return
        actions.add(action)

        event_actions = self._get_event_actions(event)
        previous_id = event_actions[-1].id if event_actions else uuid.UUID(int=0)
        event_action = EventAction.create_new(event.id, action.get_name(), action.id, previous_id)
        self.event_actions.add(event_action)

    def remove_action(self: Self, event: Event, action: Action) -> None:
        """Removes and unlinks an action from an event.

        The specified action is removed from the Actions collection,
        while also removing the linked EventAction from the EventAction
        collection.

        Args:
            event (Event): The event to remove the action from
            action (Action): The action to remove
        """
        actions = self.actions_collection.get(action.get_name())
        if actions is None:
            return
        actions.remove(action.id)

        event_action = self.event_actions.get_by_action_in_event(action.id, event.id)
        if event_action is None:
            return

        next_action = self.event_actions.get_by_previous(event_action.id)

        # Ensure that the action after the one that was removed is relinked
        if next_action:
            if event_action.previous_id:
                next_action.previous_id = event_action.previous_id
            else:
                next_action.previous_id = None
            self.event_actions.update(next_action)
        self.event_actions.remove(event_action.id)

    def reorder_action(self: Self, event: Event, action_index: int, new_index: int) -> None:
        """
        Changes the position of an action in an event's execution order.

        Args:
            event: The event to reorder the action's of
            action_index: The index of the target action
            new_index: The new position of the action
        """
        event_actions = self.event_actions.get_by_event(event.id)

        # Automatically put new position within bounds
        if new_index > len(event_actions):
            new_index = len(event_actions)
        elif new_index < 1:
            new_index = 1

        action_to_move = event_actions[action_index - 1]
        action_to_replace = event_actions[new_index - 1]

        # If moving up, song after new position should be re-referenced to moved song
        if new_index > action_index:
            action_to_move.previous_id = action_to_replace.id
            try:
                action_after_new = event_actions[new_index]
                action_after_new.previous_id = action_to_move.id
                self.event_actions.update(action_after_new)
            except IndexError:
                pass

        # If moving down, song at new position should be re-referenced to moved song
        else:
            action_to_move.previous_id = action_to_replace.previous_id
            action_to_replace.previous_id = action_to_move.id
            self.event_actions.update(action_to_replace)

        # Fill in the gap at the original song position
        try:
            action_after_selected = event_actions[action_index]
            action_before_selected = event_actions[action_index - 2]
            action_after_selected.previous_id = action_before_selected.id
            self.event_actions.update(action_after_selected)
        except IndexError:
            pass
        self.event_actions.update(action_to_move)

    def dispatch_event(self: Self, event: Event) -> None:
        """Triggers all the actions linked to an event.

        Each action is triggered sequentially in the order that was
        specified by the user.

        Args:
            event: The event to run
        """
        event.last_run_time = int(datetime.datetime.now(tz=datetime.UTC).timestamp())
        for action in self.get_actions(event):
            self.bot.dispatch(f"{action.get_name()}_action", action)
        self.events.update(event)

    def _get_event_actions(self: Self, event: Event) -> list[EventAction]:
        """Returns all EventActions associated with an event.

        Args:
            event: The selected event to query

        Returns:
            list of EventAction: The EventActions associated with the event
        """
        event_action_links = {}
        event_actions = self.event_actions.get_by_event(event.id)
        for event_action in event_actions:
            event_action_links[event_action.previous_id] = event_action

        # Sort actions using linked previous_id
        sorted_actions: list[EventAction] = []
        next_event_action = event_action_links.get(uuid.UUID(int=0))
        while next_event_action is not None:
            sorted_actions.append(next_event_action)
            next_event_action = event_action_links.get(next_event_action.id)

        return sorted_actions


class EventScheduler:
    """
    A scheduler that handles the automated dispatching of events.

    Its usage is as simple as passing an event through the schedule
    function. The event should have data pertaining to the execution
    time, which should then process the action through the event
    service
    """

    def __init__(
        self: EventScheduler, event_service: EventService, cache_release_time: int = -1
    ) -> None:
        """
        Initializes a new instance of the class.

        Args:
            event_service (EventService): The event service to dispatch
                events to.
            cache_release_time (int, optional): The time in seconds for
                how close to the expected dispatch time the event must
                be to be loaded in memory. A lower value reduces the
                amount of memory used at any given time, but also
                requires more frequent cache releases. Defaults to -1.
        """
        self.event_service = event_service
        self.cache_release_time = cache_release_time
        self.scheduled_events: dict[uuid.UUID, asyncio.Task] = {}

    def is_scheduled(self: Self, event: Event) -> bool:
        """Returns true if the specified event is currently scheduled.

        Args:
            event: The event to query

        Returns:
            bool: True if event is scheduled
        """
        return event in self.scheduled_events

    def schedule(self: Self, event: Event) -> None:
        """Schedules an event to run at its next dispatch time.

        If a cache release time has been specified as a class attribute,
        the event will be unloaded if the next dispatch time is greater
        than the threshold is exceeded. This is a memory saving measure.

        Args:
            event: The event to schedule.
        """
        # Don't add if already scheduled
        if event.id in self.scheduled_events:
            return

        # Don't add if paused
        if event.is_paused:
            return

        # Only add repeating events if next dispatch is within cache release time
        if (
            self.calculate_next_run(event) - datetime.datetime.now(tz=datetime.UTC).timestamp()
            > self.cache_release_time
        ):
            return

        # Only add non repeating event if it is at most 5 minutes past execution time
        if (
            event.repeat_interval == Repeat.No
            and event.dispatch_time > datetime.datetime.now(tz=datetime.UTC).timestamp() + 300
        ):
            return

        self.scheduled_events[event.id] = asyncio.create_task(self._task_loop(event))

    def schedule_saved(self: Self) -> None:
        """Loads all events that are due to be scheduled.

        If a cache release time is specified, it is highly recommend to
        set up a recurring task that triggers this event at the same
        interval so that new events are loaded into memory. All events
        are loaded in from event repository if cache_release_time set to
        -1.
        """
        events = (
            self.event_service.events.get_all()
            if self.cache_release_time < 0
            else self.event_service.events.get_before_timestamp(
                int(datetime.datetime.now(tz=datetime.UTC).timestamp() + self.cache_release_time)
            )
        )
        for event in events:
            if not self.is_scheduled(event) and not event.is_paused:
                self.schedule(event)

    def unschedule(self: Self, event: Event) -> None:
        """Stops the event from running at its next dispatch time.

        Args:
            event: The event to unschedule
        """
        if event.id not in self.scheduled_events:
            return

        self.scheduled_events[event.id].cancel()
        self.scheduled_events.pop(event.id)

    def unschedule_all(self: Self) -> None:
        """Stops all events from dispatching at their next dispatch time."""
        for event in self.scheduled_events.values():
            event.cancel()
        self.scheduled_events.clear()

    async def _task_loop(self: Self, event: Event) -> None:
        """An indefinite loop to dispatch events.

        Should only be run through the schedule function

        Args:
            event: The event to run.
        """
        dispatch_time = self.calculate_next_run(event)
        try:
            while True:
                if dispatch_time >= time.time():
                    await asyncio.sleep(dispatch_time - time.time())
                    continue
                break
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed):
            self.unschedule(event)
            self.schedule(event)

        await self._dispatch_event(event)

    async def _dispatch_event(self: Self, event: Event) -> None:
        """
        Triggers all the actions linked to this event.

        Each action is triggered sequentially in the order that was
        specified by the user.

        Args:
            event: The event to dispatch
        """
        self.event_service.dispatch_event(event)
        self.unschedule(event)

        # Only renew if it is a repeating event that is within the bounds of the cache release time
        total_interval = event.repeat_interval.value * event.repeat_multiplier
        if event.repeat_interval != Repeat.No and 0 < total_interval < self.cache_release_time:
            self.schedule(event)

    @staticmethod
    def calculate_next_run(event: Event) -> float:
        """Calculates the time for when the event should run next.

        A repeating event should return the next time it should run. A
        non repeating event should just return the set dispatch time.

        Args:
            event: The event to get calculate the interval of

        Returns:
            float: The timestamp for when the event should next be
                dispatched.
        """
        # Non repeating events just use the user specified dispatch time
        if event.repeat_interval == Repeat.No:
            return event.dispatch_time

        # Repeating events should set the dispatch time in the past if the previous dispatch was
        # missed by 5 minutes due to bot downtime. Otherwise, set dispatch time in the future at
        # the correct interval.
        interval = event.repeat_interval.value * event.repeat_multiplier
        now = datetime.datetime.now(tz=datetime.UTC).timestamp()
        elapsed_seconds = now - event.dispatch_time
        previous_dispatch_delta = math.ceil(elapsed_seconds / interval - 1) * interval
        if (
            event.last_run_time
            and now < event.dispatch_time + previous_dispatch_delta + 300
            and now - event.last_run_time > FIVE_MINUTES_IN_SECONDS
        ):
            dispatch_time = event.dispatch_time + previous_dispatch_delta
        else:
            next_dispatch_delta = math.ceil(elapsed_seconds / interval) * interval
            dispatch_time = event.dispatch_time + next_dispatch_delta

        return dispatch_time
