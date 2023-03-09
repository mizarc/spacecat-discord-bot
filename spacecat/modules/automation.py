import asyncio
import math
import sqlite3
from abc import ABC, abstractmethod
from enum import Enum
from typing import Generic, TypeVar, get_args

import discord
import discord.ext.commands
import toml
from discord import app_commands
from discord.ext import commands, tasks

import datetime
import pytz
import time
import uuid

from spacecat.helpers import constants
from spacecat.helpers.views import PaginatedView, EmptyPaginatedView
from spacecat.modules.administration import ServerSettingsRepository
from spacecat.spacecat import SpaceCat


class Repeat(Enum):
    No = 0
    Hourly = 3600
    Daily = 86400
    Weekly = 604800


class InvalidTimeException(Exception):
    """Raised when a string cannot be converted to a valid time"""
    pass


class InvalidDateException(Exception):
    """Raised when a string cannot be converted to a valid date"""
    pass


class Reminder:
    def __init__(self, id_: uuid.UUID, user_id, guild_id, channel_id, message_id, creation_time, dispatch_time,
                 message):
        self.id: uuid.UUID = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.message_id = message_id
        self.creation_time = creation_time
        self.dispatch_time = dispatch_time
        self.message = message

    @classmethod
    def create_new(cls, user, guild, channel, confirmation_message, creation_time, dispatch_time, message):
        return cls(uuid.uuid4(), user.id, guild.id, channel.id, confirmation_message.id, creation_time, dispatch_time,
                   message)


class ReminderRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS reminders (id TEXT PRIMARY KEY, user_id INTEGER, guild_id INTEGER, '
                       'channel_id INTEGER, message_id INTEGER, creation_time INTEGER, dispatch_time INTEGER, '
                       'message TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all reminders"""
        results = self.db.cursor().execute('SELECT * FROM reminders').fetchall()
        reminders = []
        for result in results:
            reminders.append(self._result_to_reminder(result))
        return reminders

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM reminders WHERE id=?', (str(id_),)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6], result[7])

    def get_by_guild(self, guild_id: int):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM reminders WHERE guild_id=?', (guild_id,))
        results = cursor.fetchall()
        reminders = []
        for result in results:
            reminders.append(self._result_to_reminder(result))
        return reminders

    def get_by_guild_and_user(self, guild_id: int, user_id: int):
        # Get reminder by guild and reminder name
        cursor = self.db.cursor()
        cursor.execute(
            'SELECT * FROM reminders WHERE guild_id=? AND user_id=? ORDER BY dispatch_time', (guild_id, user_id))
        results = cursor.fetchall()
        reminders = []
        for result in results:
            reminders.append(self._result_to_reminder(result))
        return reminders

    def get_before_timestamp(self, timestamp):
        result = self.db.cursor().execute(
            'SELECT * FROM reminders WHERE dispatch_time < ? ORDER BY dispatch_time', (timestamp,)).fetchall()
        return self._result_to_reminder(result)

    def add(self, reminder):
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO reminders VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (str(reminder.id), reminder.user_id, reminder.guild_id, reminder.channel_id, reminder.message_id,
                        reminder.creation_time, reminder.dispatch_time, reminder.message))
        self.db.commit()

    def update(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.user_id, reminder.guild_id, reminder.channel_id, reminder.message_id,
                  reminder.creation_time, reminder.dispatch_time, reminder.message, str(reminder.id))
        cursor.execute('UPDATE reminders SET user_id=?, guild_id=?, channel_id=?, message_id=?'
                       'creation_time=?, dispatch_time=?, message=? WHERE id=?', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM reminders WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_reminder(result):
        return Reminder(uuid.UUID(result[0]), result[1], result[2], result[3],
                        result[4], result[5], result[6], result[7])


class Event:
    def __init__(self, id_: uuid.UUID, guild_id, dispatch_time, last_run_time, repeat_interval,
                 repeat_multiplier, is_paused, name, description):
        self.id: uuid.UUID = id_
        self.guild_id = guild_id
        self.dispatch_time: int = dispatch_time
        self.last_run_time = last_run_time
        self.repeat_interval: Repeat = repeat_interval
        self.repeat_multiplier = repeat_multiplier
        self.is_paused = is_paused
        self.name = name
        self.description = description

    @classmethod
    def create_new(cls, guild_id, dispatch_time, repeat_interval, repeat_multiplier, name):
        return cls(uuid.uuid4(), guild_id, dispatch_time, None,
                   repeat_interval, repeat_multiplier, False, name, "")


class EventRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, guild_id INTEGER, '
                       'dispatch_time INTEGER, last_run_time INTEGER, repeat_interval TEXT, repeat_multiplier INTEGER, '
                       'is_paused INTEGER, name TEXT, description TEXT)')
        self.db.commit()

    def get_all(self):
        """Get list of all reminders"""
        results = self.db.cursor().execute('SELECT * FROM events').fetchall()
        reminders = []
        for result in results:
            event = self._result_to_event(result)
            reminders.append(event)
        return reminders

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM events WHERE id=?', (str(id_),)).fetchone()
        return self._result_to_event(result)

    def get_by_name(self, name):
        result = self.db.cursor().execute('SELECT * FROM events WHERE name=?', (name,)).fetchone()
        if not result:
            return None
        return self._result_to_event(result)

    def get_by_guild(self, guild_id):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        values = (guild_id,)
        cursor.execute('SELECT * FROM events WHERE guild_id=?', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(self._result_to_event(result))
        return reminders

    def get_by_name_in_guild(self, name, guild_id):
        values = (name, guild_id)
        result = self.db.cursor().execute('SELECT * FROM events WHERE name=? AND guild_id=?', values).fetchone()
        if not result:
            return None
        return self._result_to_event(result)

    def get_repeating(self):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        cursor.execute('SELECT * FROM events WHERE NOT repeat_interval=? AND is_paused=0', ('No',))
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(self._result_to_event(result))
        return reminders

    def get_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        results = cursor.execute('SELECT * FROM events WHERE dispatch_time < ? ORDER BY dispatch_time',
                                 (timestamp,)).fetchall()

        reminders = []
        for result in results:
            reminders.append(self._result_to_event(result))
        return reminders

    def get_first_non_repeating_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        result = cursor.execute('SELECT * FROM events '
                                'WHERE dispatch_time < ? AND repeat_interval="No" '
                                'ORDER BY dispatch_time',
                                (timestamp,)).fetchone()
        return self._result_to_event(result)

    def add(self, event):
        cursor = self.db.cursor()
        values = (str(event.id), event.guild_id, event.dispatch_time, event.last_run_time,
                  event.repeat_interval.name, event.repeat_multiplier, int(event.is_paused), event.name,
                  event.description)
        cursor.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, event):
        cursor = self.db.cursor()
        values = (event.guild_id, event.dispatch_time, event.last_run_time, event.repeat_interval.name,
                  event.repeat_multiplier, int(event.is_paused), event.name, event.description, str(event.id))
        cursor.execute('UPDATE events SET guild_id=?, dispatch_time=?, last_run_time=?, repeat_interval=?, '
                       'repeat_multiplier=?, is_paused=?, name=?, description=? WHERE id=?', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        self.db.cursor().execute('DELETE FROM events WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_event(result):
        return Event(uuid.UUID(result[0]), result[1], result[2], result[3],
                     Repeat[result[4]], result[5], bool(result[6]), result[7], result[8])


class Action(ABC):
    def __init__(self, id_: uuid.UUID):
        self.id: uuid.UUID = id_

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def get_formatted_output(self):
        pass


T_Action = TypeVar("T_Action", bound=Action)


class ActionRepository(ABC, Generic[T_Action]):
    def __init__(self, database):
        self.db = database

    @abstractmethod
    def get_by_id(self, id_: uuid):
        pass

    @abstractmethod
    def add(self, action: T_Action):
        pass

    @abstractmethod
    def remove(self, id_: uuid):
        pass


class MessageAction(Action):
    def __init__(self, id_: uuid.UUID, text_channel_id, message):
        super().__init__(id_)
        self.text_channel_id = text_channel_id
        self.message = message

    @classmethod
    def create_new(cls, text_channel_id, message):
        return cls(uuid.uuid4(), text_channel_id, message)

    @classmethod
    def get_name(cls):
        return "message"

    def get_formatted_output(self):
        return f"Sends a message starting with '{self.message[:20]}' to channel <#{self.text_channel_id}>."


class MessageActionRepository(ActionRepository[MessageAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_message '
                       '(id TEXT PRIMARY KEY, text_channel INTEGER, message TEXT)')
        self.db.commit()

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM action_message WHERE id=?', (str(id_),)).fetchone()
        return self._result_to_action(result)

    def add(self, action: MessageAction):
        values = (str(action.id), action.text_channel_id, action.message)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_message VALUES (?, ?, ?)', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_message WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_action(result):
        return MessageAction(uuid.UUID(result[0]), result[1], result[2]) if result else None


class BroadcastAction(Action):
    def __init__(self, id_: uuid.UUID, text_channel_id, title, message):
        super().__init__(id_)
        self.text_channel_id = text_channel_id
        self.title = title
        self.message = message

    @classmethod
    def create_new(cls, text_channel_id, title, message):
        return cls(uuid.uuid4(), text_channel_id, title, message)

    @classmethod
    def get_name(cls):
        return "broadcast"

    def get_formatted_output(self):
        return f"Sends a broadcast titled '{self.title}' to channel <#{self.text_channel_id}>."


class BroadcastActionRepository(ActionRepository[BroadcastAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_broadcast '
                       '(id TEXT PRIMARY KEY, text_channel INTEGER, title TEXT, message TEXT)')
        self.db.commit()

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM action_broadcast WHERE id=?', (str(id_),)).fetchone()
        return self._result_to_action(result)

    def add(self, action: BroadcastAction):
        values = (str(action.id), action.text_channel_id, action.title, action.message)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_broadcast VALUES (?, ?, ?, ?)', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_broadcast WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_action(result):
        return BroadcastAction(uuid.UUID(result[0]), result[1], result[2], result[3]) if result else None


class VoiceKickAction(Action):
    def __init__(self, id_: uuid.UUID, voice_channel_id):
        super().__init__(id_)
        self.voice_channel_id = voice_channel_id

    @classmethod
    def create_new(cls, voice_channel_id):
        return cls(uuid.uuid4(), voice_channel_id)

    @classmethod
    def get_name(cls):
        return "voice_kick"

    def get_formatted_output(self):
        return f"Kicks all users out of voice channel <#{self.voice_channel_id}>."


class VoiceKickActionRepository(ActionRepository[VoiceKickAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_voice_kick (id TEXT PRIMARY KEY, voice_channel_id TEXT)')
        self.db.commit()

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM action_voice_kick WHERE id=?', (str(id_),)).fetchone()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: VoiceKickAction):
        values = (str(action.id), action.voice_channel_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_voice_kick VALUES (?, ?)', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_voice_kick WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return VoiceKickAction(uuid.UUID(result[0]), result[1]) if result else None


class VoiceMoveAction(Action):
    def __init__(self, id_: uuid.UUID, current_voice_channel_id, new_voice_channel_id):
        super().__init__(id_)
        self.current_voice_channel_id = current_voice_channel_id
        self.new_voice_channel_id = new_voice_channel_id

    @classmethod
    def create_new(cls, current_voice_channel_id, new_voice_channel_id):
        return cls(uuid.uuid4(), current_voice_channel_id, new_voice_channel_id)

    @classmethod
    def get_name(cls):
        return "voice_move"

    def get_formatted_output(self):
        return f"Moves all users from voice channel " \
               f"<#{self.current_voice_channel_id}> to <#{self.new_voice_channel_id}>."


class VoiceMoveActionRepository(ActionRepository[VoiceMoveAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_voice_move '
                       '(id TEXT PRIMARY KEY, current_voice_channel_id INTEGER, new_voice_channel_id INTEGER)')
        self.db.commit()

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM action_voice_move WHERE id=?', (str(id_),)).fetchone()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: VoiceMoveAction):
        values = (str(action.id), action.current_voice_channel_id, action.new_voice_channel_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_voice_move VALUES (?, ?, ?)', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_voice_move WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return VoiceMoveAction(uuid.UUID(result[0]), result[1], result[2]) if result else None


class ChannelPrivateAction(Action):
    def __init__(self, id_: uuid.UUID, channel_id):
        super().__init__(id_)
        self.channel_id = channel_id

    @classmethod
    def create_new(cls, channel_id):
        return cls(uuid.uuid4(), channel_id)

    @classmethod
    def get_name(cls):
        return "channel_private"

    def get_formatted_output(self):
        return f"Sets channel <#{self.channel_id}> to private visibility."


class ChannelPrivateActionRepository(ActionRepository[ChannelPrivateAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_channel_private (id TEXT PRIMARY KEY, channel_id INTEGER)')
        self.db.commit()

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM action_channel_private WHERE id=?', (str(id_),)).fetchone()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: ChannelPrivateAction):
        values = (str(action.id), action.channel_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_channel_private VALUES (?, ?)', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_channel_private WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return VoiceMoveAction(uuid.UUID(result[0]), result[1], result[2]) if result else None


class ChannelPublicAction(Action):
    def __init__(self, id_: uuid.UUID, channel_id):
        super().__init__(id_)
        self.channel_id = channel_id

    @classmethod
    def create_new(cls, channel_id):
        return cls(uuid.uuid4(), channel_id)

    @classmethod
    def get_name(cls):
        return "channel_public"

    def get_formatted_output(self):
        return f"Sets channel <#{self.channel_id}> to public visibility."


class ChannelPublicActionRepository(ActionRepository[ChannelPublicAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_channel_public (id TEXT PRIMARY KEY, channel_id INTEGER)')
        self.db.commit()

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM action_channel_public WHERE id=?', (str(id_),)).fetchone()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: ChannelPublicAction):
        values = (str(action.id), action.channel_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_channel_public VALUES (?, ?)', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_channel_public WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return ChannelPublicAction(uuid.UUID(result[0]), result[1]) if result else None


class EventAction:
    def __init__(self, id_: uuid.UUID, event_id: uuid.UUID, action_type, action_id: uuid.UUID, previous_id):
        self.id: uuid.UUID = id_
        self.event_id: uuid.UUID = event_id
        self.action_type: str = action_type
        self.action_id: uuid.UUID = action_id
        self.previous_id: uuid.UUID = previous_id

    @classmethod
    def create_new(cls, event_id, action_type, action_id, previous_id):
        return cls(uuid.uuid4(), event_id, action_type, action_id, previous_id)


class EventActionRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS event_actions '
                       '(id TEXT PRIMARY KEY, event_id INTEGER, action_type TEXT, action_id INTEGER, previous_id TEXT)')

    def get_by_id(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM event_actions WHERE id=?', (str(id_),)).fetchone()
        return self._result_to_event_action(result)

    def get_by_event(self, event_id: uuid.UUID):
        results = self.db.cursor().execute('SELECT * FROM event_actions WHERE event_id=?', (str(event_id),)).fetchall()
        event_actions = []
        for result in results:
            event_actions.append(self._result_to_event_action(result))
        return event_actions

    def get_by_action(self, action_id: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM event_actions WHERE action_id=?', (str(action_id),)).fetchone()
        return self._result_to_event_action(result)

    def get_by_action_in_event(self, action_id: uuid.UUID, event_id: uuid.UUID):
        result = self.db.cursor().execute(
            'SELECT * FROM event_actions WHERE action_id=? AND event_id=?', (str(action_id), str(event_id))).fetchone()
        return self._result_to_event_action(result)

    def get_by_previous(self, id_: uuid.UUID):
        result = self.db.cursor().execute('SELECT * FROM event_actions WHERE previous_id=?', (str(id_),)).fetchone()
        return self._result_to_event_action(result)

    def add(self, event_action: EventAction):
        values = (str(event_action.id), str(event_action.event_id), event_action.action_type,
                  str(event_action.action_id), str(event_action.previous_id))
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO event_actions VALUES (?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, event_action: EventAction):
        values = (event_action.event_id, event_action.action_type, event_action.action_id, event_action.previous_id,
                  event_action.id)
        self.db.cursor().execute('UPDATE event_actions SET event_id=?, action_type=?, action_id=?, previous_id=? '
                                 'WHERE id=?', values)
        self.db.commit()

    def remove(self, id_: uuid.UUID):
        self.db.cursor().execute('DELETE FROM event_actions WHERE id=?', (str(id_),))
        self.db.commit()

    @staticmethod
    def _result_to_event_action(result):
        return EventAction(uuid.UUID(result[0]), uuid.UUID(result[1]), result[2], uuid.UUID(result[3]),
                           uuid.UUID(result[4])) if result else None


class EventService:
    """
    A layer for creating, destroying, and dispatching events and their associated actions

    Attributes:
        bot: The bot instance, required to know where to dispatch objects to
        events: A collection of events
        actions_collection: A dictionary linking a keyword to a certain type of action collection
        event_actions: A collection of event actions
    """

    def __init__(self, bot: discord.ext.commands.Bot, event_actions, events):
        self.bot = bot
        self.events: EventRepository = events
        self.actions_collection: dict[str, ActionRepository] = {}
        self.event_actions: EventActionRepository = event_actions

    def add_action_repository(self, action_repository: ActionRepository):
        """Adds a specific type of action repository to be able to query from"""
        self.actions_collection[get_args(type(action_repository).__orig_bases__[0])[0].get_name()] = action_repository

    def remove_event(self, event: Event):
        """Removes an event and all associated actions from storage.

        Args:
            event (Event): The selected event to remove from the collection
        """
        found_event_actions = self.event_actions.get_by_event(event.id)
        for event_action in found_event_actions:
            self.actions_collection.get(event_action.action_type).remove(event_action.action_id)
            self.event_actions.remove(event_action.id)
        self.events.remove(event.id)

    def get_actions(self, event: Event) -> list[Action]:
        """Returns all Actions associated with an event

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
            actions = self.actions_collection.get(next_event_action.action_type)
            sorted_actions.append(actions.get_by_id(next_event_action.action_id))
            next_event_action = event_action_links.get(next_event_action.id)

        return sorted_actions

    def get_action_at_position(self, event: Event, index: int) -> Action:
        """Returns the action of an event at a specified index

        Args:
            event: The event to get the action from
            index: The position of the action

        Returns:
            Action: The action at the position in the event
        """
        actions = self.get_actions(event)
        return actions[index]

    def add_action(self, event: Event, action: Action):
        """Links a new action to a specified event

        The action is added to the Actions collection, with a new EventActions object being created for the purposes of
        associating the action with an Event.

        Args:
            event: The event to link the action to
            action: The action to be linked
        """
        actions = self.actions_collection.get(action.get_name())
        actions.add(action)

        event_actions = self._get_event_actions(event)
        if event_actions:
            previous_id = event_actions[-1].id
        else:
            previous_id = uuid.UUID(int=0)
        event_action = EventAction.create_new(event.id, action.get_name(), action.id, previous_id)
        self.event_actions.add(event_action)

    def remove_action(self, event: Event, action: Action):
        """Removes and unlinks an action from an event

        The specified action is removed from the Actions collection, while also removing the linked EventAction from the
        EventAction collection.

        Args:
            event: The event to remove the action from
            action: The action to remove
        """
        actions = self.actions_collection.get(action.get_name())
        actions.remove(action.id)

        event_action = self.event_actions.get_by_action_in_event(action.id, event.id)
        next_action = self.event_actions.get_by_previous(event_action.id)

        # Ensure that the action after the one that was removed is relinked
        if next_action:
            if event_action.previous_id:
                next_action.previous_id = event_action.previous_id
            else:
                next_action.previous_id = None
            self.event_actions.update(next_action)
        self.event_actions.remove(event_action.id)

    def reorder_action(self, event: Event, action_index: int, new_index: int):
        """Changes the position of an action in the event's execution order

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

    def dispatch_event(self, event: Event):
        """Triggers all the actions linked to an event

        Each action is triggered sequentially in the order that was specified by the user.

        Args:
            event: The event to run
        """
        event.last_run_time = datetime.datetime.now().timestamp()
        for action in self.get_actions(event):
            self.bot.dispatch(f"{action.get_name()}_action", action)
        self.events.update(event)

    def _get_event_actions(self, event: Event) -> list[EventAction]:
        """Returns all EventActions associated with an event

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
    """A scheduler that handles the automated dispatching of events

    Its usage is as simple as passing an event through the schedule function. The event should have data pertaining
    to the execution time, which should then process the action through the event service.

    Attributes:
        event_service: The service to dispatch events to
        cache_release_time: The time in seconds for how close to the expected dispatch time the event must be to be
        loaded in memory. A lower value reduces the amount of memory used at any given time, but also requires more
        frequent database lookups for new events.
        scheduled_events: A dictionary of events currently being scheduled for dispatch
    """

    def __init__(self, event_service: EventService, cache_release_time: int = -1):
        self.event_service = event_service
        self.cache_release_time = cache_release_time
        self.scheduled_events: dict[uuid.UUID, asyncio.Task] = {}

    def is_scheduled(self, event: Event) -> bool:
        """Returns true if the specified event is currently scheduled

        Args:
            event: The event to query

        Returns:
            bool: True if event is scheduled
        """
        return event in self.scheduled_events

    def schedule(self, event: Event):
        """Schedules an event to run at its next dispatch time

        If a cache release time has been specified as a class attribute, the event will be unloaded if the next dispatch
        time is greater than the threshold is exceeded. This is a memory saving measure.

        Args:
            event: The event to schedule
        """
        # Don't add if already scheduled
        if event.id in self.scheduled_events:
            return

        # Don't add if paused
        if event.is_paused:
            return

        # Only add repeating events if next dispatch is within cache release time
        if self.calculate_next_run(event) - datetime.datetime.now().timestamp() > self.cache_release_time:
            return

        # Only add non repeating event if it is at most 5 minutes past execution time
        if event.repeat_interval == Repeat.No and event.dispatch_time > datetime.datetime.now().timestamp() + 300:
            return

        self.scheduled_events[event.id] = asyncio.create_task(self._task_loop(event))

    def schedule_saved(self):
        """Loads all events that are due to be scheduled sooner than the cache release time

        If a cache release time is specified, it is highly recommend to set up a recurring task that triggers this event
        at the same interval. All events are loaded in from event repository if cache_release_time set to -1.
        """
        events = self.event_service.events.get_all() \
            if self.cache_release_time < 0 \
            else self.event_service.events.get_before_timestamp(
            datetime.datetime.now().timestamp() + self.cache_release_time)
        for event in events:
            if not self.is_scheduled(event) and not event.is_paused:
                self.schedule(event)

    def unschedule(self, event: Event):
        """Stops the event from running at its next dispatch time

        Args:
            event: The event to unschedule
        """

        if event.id not in self.scheduled_events.keys():
            return

        self.scheduled_events[event.id].cancel()
        self.scheduled_events.pop(event.id)

    def unschedule_all(self):
        """Stops all events from dispatching at their next dispatch time"""
        for event in self.scheduled_events.values():
            event.cancel()
        self.scheduled_events.clear()

    async def _task_loop(self, event):
        """An indefinite loop to dispatch events. Should only be run through the schedule function

        Args:
            event: The event to run
        """
        dispatch_time = self.calculate_next_run(event)
        try:
            while True:
                if dispatch_time >= time.time():
                    await asyncio.sleep(dispatch_time - time.time())
                    continue
                await self._dispatch_event(event)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed):
            self.unschedule(event)
            self.schedule(event)

    async def _dispatch_event(self, event):
        """Triggers all the actions linked to this event

        Each action is triggered sequentially in the order that was specified by the user.

        Args:
            event: The event to dispatch
        """
        self.event_service.dispatch_event(event)
        self.unschedule(event)

        # Only renew if it is a repeating event that is within the bounds of the cache release time
        total_interval = event.repeat_interval.value * event.repeat_multiplier
        if event.repeat_interval != Repeat.No and 0 < total_interval < self.cache_release_time:
            self.schedule(event)

        await asyncio.sleep(0)  # This isn't useless. It forces an async task switch so that it actually cancels

    @staticmethod
    def calculate_next_run(event) -> float:
        """Calculates the time for when the event should run next

        A repeating event should return the next time it should run. A non repeating event should just return the
        set dispatch time.

        Args:
            event: The event to get calculate the interval of

        Returns:
            float: The timestamp for when the event should next dispatch
        """
        # Non repeating events just use the user specified dispatch time
        if event.repeat_interval == Repeat.No:
            return event.dispatch_time

        # Repeating events should set the dispatch time in the past if the previous dispatch was missed by 5 minutes due
        # to bot downtime. Otherwise, set dispatch time in the future at the correct interval.
        interval = event.repeat_interval.value * event.repeat_multiplier
        now = datetime.datetime.now().timestamp()
        elapsed_seconds = now - event.dispatch_time
        previous_dispatch_delta = math.ceil(elapsed_seconds / interval - 1) * interval
        if now < event.dispatch_time + previous_dispatch_delta + 300 and now - event.last_run_time > 300:
            dispatch_time = event.dispatch_time + previous_dispatch_delta
        else:
            next_dispatch_delta = math.ceil(elapsed_seconds / interval) * interval
            dispatch_time = event.dispatch_time + next_dispatch_delta

        return dispatch_time


class ReminderService:
    """A layer that handles the dispatching of reminders

    Attributes:
        bot: The bot instance
        reminders The reminder repository
    """
    def __init__(self, bot: discord.ext.commands.Bot, reminders: ReminderRepository):
        self.bot = bot
        self.reminders = reminders

    def dispatch(self, reminder: Reminder):
        """Sends a reminder dispatch alert alongside object data for the bot to handle

        Reminder dispatching is expected to output a message targeted towards the user who initially set the reminder.

        Args:
            reminder: The reminder to dispatch
        """
        self.bot.dispatch("reminder", reminder)
        self.reminders.remove(reminder.id)


class ReminderScheduler:
    """A scheduler that handles the automated dispatching of reminders

        Its usage is as simple as passing a reminder through the schedule function. The reminder should have data
        pertaining to the execution time, which should then process the action through the reminder service.

        Attributes:
            reminder_service: The service to dispatch events to
            cache_release_time: The time in seconds for how close to the expected dispatch time the event must be to be
            loaded in memory. A lower value reduces the amount of memory used at any given time, but also requires more
            frequent database lookups for new events.
            scheduled_reminders: A dictionary of reminders currently being scheduled for dispatch
        """

    def __init__(self, reminder_service: ReminderService, cache_release_time: int = -1):
        self.reminder_service = reminder_service
        self.cache_release_time = cache_release_time
        self.scheduled_reminders: dict[uuid.UUID, asyncio.Task] = {}

    def is_scheduled(self, reminder: Reminder) -> bool:
        """Returns true if the specified reminder is currently scheduled

        Args:
            reminder: The reminder to query

        Returns:
            bool: True if event is scheduled
        """
        return reminder in self.scheduled_reminders

    def schedule(self, reminder: Reminder):
        """Schedules a reminder to run at its dispatch time

        If a cache release time has been specified as a class attribute, the reminder will not be added if the set
        dispatch time is greater than the cache release time. This is a memory saving measure.

        Args:
            reminder: The reminder to schedule
        """
        self.scheduled_reminders[reminder.id] = asyncio.create_task(self._task_loop(reminder))

    def schedule_saved(self):
        """Loads all reminders that are due to be scheduled sooner than the cache release time

        If a cache release time is specified, we highly recommend setting up a recurring task that triggers this method
        at the same interval. All reminders are loaded in from reminder repository if cache_release_time set to -1.
        """
        events = self.reminder_service.reminders.get_all() \
            if self.cache_release_time < 0 \
            else self.reminder_service.reminders.get_before_timestamp(
            datetime.datetime.now().timestamp() + self.cache_release_time)
        for event in events:
            if not self.is_scheduled(event):
                self.schedule(event)

    def unschedule(self, reminder: Reminder):
        """Stops the reminder from running at its next dispatch time

        Args:
            reminder: The reminder to unschedule
        """
        self.scheduled_reminders[reminder.id].cancel()
        self.scheduled_reminders.pop(reminder.id)

    def unschedule_all(self):
        """Stops all reminders from dispatching from their next dispatch time"""
        for event in self.scheduled_reminders.values():
            event.cancel()
        self.scheduled_reminders.clear()

    async def _task_loop(self, reminder):
        """An indefinite loop to dispatch reminders. Should only be run through the task

        Args:
            reminder: The event to run
        """
        while True:
            if reminder.dispatch_time >= time.time():
                await asyncio.sleep(reminder.dispatch_time - time.time())
            await self._dispatch(reminder)

    async def _dispatch(self, reminder):
        """Triggers the dispatching of the reminder

        Args:
            reminder: The event to dispatch
        """
        self.unschedule(reminder)
        self.reminder_service.dispatch(reminder)
        await asyncio.sleep(0)


class Automation(commands.Cog):
    """Schedule events to run at a later date"""
    MAX_EVENTS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"The server has reach its event limit. Delete an event before adding another one."
    )

    MAX_ACTIONS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"This event has reached its action limit. Delete an action before adding another one."
    )

    PAST_TIME_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"You cannot set a date and time in the past. Remember that time is in 24 hour format by default. "
                    f"Add `am/pm` if you would like to work with 12 hour time."
    )

    NAME_ALREADY_EXISTS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"An event of that name already exists."
    )

    EVENT_DOES_NOT_EXIST_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"An event of that name does not exist."
    )

    INVALID_TIME_ENUM = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"Selected time is invalid. Ensure time is in `hours:minutes` format. You may add `am/pm` to the "
                    f"end to use 12 hour time."
    )

    INVALID_DATE_ENUM = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"Selected date is invalid. Ensure date is in `date/month/year` format."
    )

    def __init__(self, bot):
        self.bot: SpaceCat = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.reminders = ReminderRepository(self.database)
        self.reminder_service = ReminderService(self.bot, self.reminders)
        self.reminder_scheduler = ReminderScheduler(self.reminder_service, 90000)
        self.events = EventRepository(self.database)
        self.event_actions = EventActionRepository(self.database)
        self.event_service = self.init_event_service()
        self.event_scheduler = EventScheduler(self.event_service, 90000)

    async def cog_load(self):
        self.load_upcoming_events.start()

        # Add config keys
        config = toml.load(constants.DATA_DIR + 'config.toml')
        if 'automation' not in config:
            config['automation'] = {}
        if 'max_reminders_per_player' not in config['automation']:
            config['automation']['max_reminders_per_player'] = 5
        if 'max_events_per_server' not in config['automation']:
            config['automation']['max_events_per_server'] = 10
        if 'max_actions_per_event' not in config['automation']:
            config['automation']['max_actions_per_event'] = 15
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

    def init_event_service(self):
        event_service = EventService(self.bot, self.event_actions, self.events)

        action_repositories = [
            MessageActionRepository(self.database),
            BroadcastActionRepository(self.database),
            VoiceKickActionRepository(self.database),
            VoiceMoveActionRepository(self.database),
            ChannelPrivateActionRepository(self.database),
            ChannelPublicActionRepository(self.database)
        ]

        for action_repository in action_repositories:
            event_service.add_action_repository(action_repository)
        return event_service

    @tasks.loop(hours=24)
    async def load_upcoming_reminders(self):
        self.reminder_scheduler.schedule_saved()

    @tasks.loop(hours=24)
    async def load_upcoming_events(self):
        self.event_scheduler.schedule_saved()

    @commands.Cog.listener()
    async def on_reminder(self, reminder):
        channel = await self.bot.fetch_channel(reminder.channel_id)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.DEFAULT} Reminder!",
            description=f"<@{reminder.user_id}>**, <t:{int(reminder.creation_time)}:R> "
                        f"you asked me to remind you:** \n {reminder.message}")
        view = discord.ui.View()
        view.add_item(discord.ui.Button(label='Go to original message',
                                        url=f'https://discord.com/channels/{reminder.guild_id}/'
                                            f'{reminder.channel_id}/{reminder.message_id}'))
        await channel.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_message_action(self, action: MessageAction):
        channel = await self.bot.fetch_channel(action.text_channel_id)
        await channel.send(action.message)

    @commands.Cog.listener()
    async def on_broadcast_action(self, action: BroadcastAction):
        channel = await self.bot.fetch_channel(action.text_channel_id)
        await channel.send(embed=discord.Embed(
            colour=constants.EmbedStatus.SPECIAL.value,
            title=f"{action.title}",
            description=f"{action.message}"))

    @commands.Cog.listener()
    async def on_voice_kick_action(self, action: VoiceKickAction):
        voice_channel = await self.bot.fetch_channel(action.voice_channel_id)
        for member in voice_channel.members:
            await member.move_to(None)

    @commands.Cog.listener()
    async def on_voice_move_action(self, action: VoiceMoveAction):
        current_channel = await self.bot.fetch_channel(action.current_voice_channel_id)
        new_channel = await self.bot.fetch_channel(action.new_voice_channel_id)
        for member in current_channel.members:
            await member.move_to(new_channel)

    @commands.Cog.listener()
    async def on_channel_private_action(self, action: ChannelPrivateAction):
        channel: discord.abc.GuildChannel = await self.bot.fetch_channel(action.channel_id)
        await channel.set_permissions(channel.guild.default_role, connect=False, view_channel=False)

    @commands.Cog.listener()
    async def on_channel_public_action(self, action: ChannelPublicAction):
        channel: discord.abc.GuildChannel = await self.bot.fetch_channel(action.channel_id)
        await channel.set_permissions(channel.guild.default_role, connect=None, view_channel=None)

    @app_commands.command()
    async def remindme(self, interaction, message: str, seconds: int = 0, minutes: int = 0, hours: int = 0,
                       days: int = 0, weeks: int = 0, months: int = 0, years: int = 0):
        if await self.is_over_reminder_limit(interaction.guild_id, interaction.user.id):
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"You have reached your reminder limit. Delete one before adding another one."))
            return

        timestamp = await self.to_seconds(seconds, minutes, hours, days, weeks, months, years)
        dispatch_time = timestamp + time.time()

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Reminder has been set for "
                        f"{await self.format_datetime(datetime.timedelta(seconds=timestamp))}")
        await interaction.response.send_message(embed=embed)

        reminder = Reminder.create_new(interaction.user, interaction.guild, interaction.channel,
                                       await interaction.original_response(), time.time(), dispatch_time, message)
        self.reminders.add(reminder)
        self.reminder_scheduler.schedule(reminder)

    reminder_group = app_commands.Group(
        name="reminder", description="Configure existing reminders.")
    event_group = app_commands.Group(
        name="event", description="Allows you to run an function at a scheduled time.")
    event_add_group = app_commands.Group(
        parent=event_group, name="add", description="Add a new scheudled event.")

    @reminder_group.command(name="list")
    async def reminder_list(self, interaction: discord.Interaction, page: int = 1):
        reminders = self.reminders.get_by_guild_and_user(interaction.guild.id, interaction.user.id)
        if not reminders:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You have no set reminders."))
            return

        # Reminders into pretty listings
        reminder_listings = []
        for reminder in reminders:
            reminder_listings.append(f"{reminder.message[0:30]} | <t:{int(reminder.dispatch_time)}:R>")

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Your Reminders")
        paginated_view = PaginatedView(embed, f"{len(reminders)} available", reminder_listings, 5, page)
        await paginated_view.send(interaction)

    @reminder_group.command(name="remove")
    async def reminder_remove(self, interaction: discord.Interaction, index: int):
        reminders = self.reminders.get_by_guild_and_user(interaction.guild.id, interaction.user.id)
        if not reminders:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You have no set reminders."))
            return

        try:
            reminder = reminders[index - 1]
        except IndexError:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="A reminder by that index doesn't exist."))
            return

        self.reminder_scheduler.unschedule(reminder)
        self.reminders.remove(reminder.id)

        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"Reminder at index {index} has been removed."))
        return

    @event_group.command(name="list")
    async def event_list(self, interaction, page: int = 1):
        events = self.events.get_by_guild(interaction.guild_id)
        if not events:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no scheduled events")
            await interaction.response.send_message(embed=embed)
            return

        # Format playlist songs into pretty listings
        event_listings = []
        for event in events:
            listing = f"{event.name}"
            if not event.dispatch_time:
                listing += f" | `Expired`"
            elif event.repeat_interval != Repeat.No and event.is_paused:
                listing += f" | `Repeating {event.repeat_interval.name} (Paused)`"
            elif event.repeat_interval != Repeat.No:
                listing += f" | `Repeating {event.repeat_interval.name}`"
            event_listings.append(listing)

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Events")
        paginated_view = PaginatedView(embed, f"{len(events)} available", event_listings, 5, page)
        await paginated_view.send(interaction)

    @event_group.command(name="create")
    async def event_create(self, interaction: discord.Interaction, name: str, time_string: str, date_string: str,
                           repeat: Repeat = Repeat.No, repeat_multiplier: int = 1):
        if await self.is_over_event_limit(interaction.guild_id):
            await interaction.response.send_message(embed=self.MAX_EVENTS_EMBED)
            return

        event = self.events.get_by_name_in_guild(name, interaction.guild_id)
        if event:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="An event by that name already exists.")
            await interaction.response.send_message(embed=embed)
            return

        try:
            selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        except InvalidTimeException:
            return await interaction.response.send_message(embed=self.INVALID_TIME_ENUM)
        except InvalidDateException:
            return await interaction.response.send_message(embed=self.INVALID_DATE_ENUM)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event = Event.create_new(interaction.guild_id, selected_datetime.timestamp(), repeat, repeat_multiplier, name)
        self.events.add(event)
        self.event_scheduler.schedule(event)

        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Event `{name}` has been created, set to trigger on "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)} Use `/event add` to "
                        f"assign actions."))
        return

    @event_group.command(name="destroy")
    async def event_destroy(self, interaction: discord.Interaction, event_name: str):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="An event by that name does not exist.")
            await interaction.response.send_message(embed=embed)
            return

        self.event_service.remove_event(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Event '{event_name}' has been deleted."))
        return

    @event_group.command(name="view")
    async def event_view(self, interaction: discord.Interaction, name: str, page: int = 1):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"Event '{event.name}'",
            description=event.description)

        # Embed category for time and interval
        time_fields = []
        timezone = await self.get_guild_timezone(interaction.guild_id)
        dt_format = '%-H:%M:%S %-d/%-m/%Y'

        if event.dispatch_time:
            dispatch_time = datetime.datetime.fromtimestamp(event.dispatch_time).astimezone(timezone)\
                .strftime(dt_format)
            label = "Initial Time" if event.repeat_interval is not Repeat.No else "Dispatch Time"
            time_fields.append(f"**{label}:** {dispatch_time}")

        repeating = await self.format_repeat_message_alt(event.repeat_interval, event.repeat_multiplier)
        time_fields.append(f"**Repeating:** {repeating}{' (Paused)' if event.is_paused else ''}")

        if event.last_run_time:
            time_fields.append(
                f"**Last Run:** "
                f"{datetime.datetime.fromtimestamp(event.last_run_time).astimezone(timezone).strftime(dt_format)}")

        if event.repeat_interval is not Repeat.No:
            next_run_time = datetime.datetime.fromtimestamp(EventScheduler.calculate_next_run(event))\
                .astimezone(timezone)
            time_fields.append(f"**Next Run:** {'N/A' if event.is_paused else next_run_time.strftime(dt_format)}")

        embed.add_field(name="Trigger", value='\n'.join(time_fields), inline=False)

        # Embed category for actions
        action_fields = []
        actions = self.event_service.get_actions(event)
        for action in actions:
            action_fields.append(f"{action.get_formatted_output()}")

        if actions:
            paginated_view = PaginatedView(embed, "Actions", action_fields, 5, page)
        else:
            paginated_view = EmptyPaginatedView(embed, f"Actions", "No actions have been set.")
        await paginated_view.send(interaction)

    @event_add_group.command(name="message")
    async def event_add_message(self, interaction: discord.Interaction, event_name: str, channel: discord.TextChannel,
                                message: str):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = MessageAction.create_new(channel.id, message)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Message action has been added to event '{event_name}'"))

    @event_add_group.command(name="broadcast")
    async def event_add_broadcast(self, interaction: discord.Interaction, event_name: str, channel: discord.TextChannel,
                                  title: str, message: str):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = BroadcastAction.create_new(channel.id, title, message)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Broadcast action has been added to event '{event_name}'"))

    @event_add_group.command(name="voicekick")
    async def event_add_voicekick(self, interaction, event_name: str, voice_channel: discord.VoiceChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = VoiceKickAction.create_new(voice_channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Voice Kick action has been added to event '{event_name}'"))

    @event_add_group.command(name="voicemove")
    async def event_add_voicemove(self, interaction, event_name: str, current_channel: discord.VoiceChannel,
                                  new_channel: discord.VoiceChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = VoiceMoveAction.create_new(current_channel.id, new_channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Voice Move action has been added to event '{event_name}'"))

    @event_add_group.command(name="channelprivate")
    async def event_add_channelprivate(self, interaction, event_name: str, channel: discord.abc.GuildChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = ChannelPrivateAction.create_new(channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Channel Private action has been added to event '{event_name}'"))

    @event_add_group.command(name="channelpublic")
    async def event_add_channelpublic(self, interaction, event_name: str, channel: discord.abc.GuildChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(event):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = ChannelPublicAction.create_new(channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Channel Public action has been added to event '{event_name}'"))

    @event_group.command(name="remove")
    async def event_remove(self, interaction, name: str, index: int):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        action = self.event_service.get_action_at_position(event, index - 1)
        self.event_service.remove_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Action '{action.get_name()}' at index {index} has been removed from event {event.name}."))

    @event_group.command(name="reorder")
    async def event_reorder(self, interaction, name: str, original_position: int, new_position: int):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        action = self.event_service.get_action_at_position(event, original_position)
        self.event_service.reorder_action(event, original_position, new_position)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"Action of type '{action.get_name()}' in event '{name}' has been moved from position "
                        f"`{original_position}` to `{new_position}`"))
        return

    @event_group.command(name="pause")
    async def event_pause(self, interaction, name: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        if event.repeat_interval == Repeat.No:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"You cannot pause one time events. You may reschedule or remove it instead."))
            return

        if event.is_paused:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Event '{name}' is already paused."))
            return

        event.is_paused = True
        self.events.update(event)
        self.event_scheduler.unschedule(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Event '{name}' has been paused and will not run on its next scheduled run time."))
        return

    @event_group.command(name="resume")
    async def event_resume(self, interaction, name: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        if not event.is_paused:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"Event '{name}' is not paused."))
            return

        event.is_paused = False
        self.events.update(event)
        self.event_scheduler.schedule(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Event {name} has now been resumed and will run at the scheduled time."))
        return

    @event_group.command(name="rename")
    async def event_rename(self, interaction, name: str, new_name: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        if any(event.name == new_name for event in self.events.get_by_guild(interaction.guild_id)):
            await interaction.response.send_message(embed=self.NAME_ALREADY_EXISTS_EMBED)
            return

        event.name = new_name
        self.events.update(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Event {name} has been renamed to {new_name}."))
        return

    @event_group.command(name="description")
    async def event_description(self, interaction, name: str, description: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        event.description = description
        self.events.update(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Description has been set for event {name}."))
        return

    @event_group.command(name="reschedule")
    async def event_reschedule(self, interaction, name: str, time_string: str, date_string: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        try:
            selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        except InvalidTimeException:
            return await interaction.response.send_message(embed=self.INVALID_TIME_ENUM)
        except InvalidDateException:
            return await interaction.response.send_message(embed=self.INVALID_DATE_ENUM)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event.dispatch_time = selected_datetime.timestamp()
        self.events.update(event)
        self.event_scheduler.unschedule(event)
        self.event_scheduler.schedule(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Event '{name}' has been rescheduled to {date_string} at {time_string}."))
        return

    @event_group.command(name="interval")
    async def event_interval(self, interaction, name: str, interval: Repeat, multiplier: int = 1):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        event.repeat_interval = interval
        event.repeat_multiplier = multiplier
        self.events.update(event)

        if self.event_scheduler.is_scheduled(event):
            self.event_scheduler.schedule(event)
            self.event_scheduler.unschedule(event)

        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Interval has been changed for event {name}."))
        return

    @event_group.command(name="trigger")
    async def event_trigger(self, interaction, name: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        self.event_service.dispatch_event(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Event '{event.name}' has been manually triggered."))
        return

    async def fetch_future_datetime(self, guild: discord.Guild, time_string: str, date_string: str = None):
        try:
            time_ = await self.parse_time(time_string)
        except InvalidTimeException:
            raise InvalidTimeException

        try:
            if date_string is None:
                date = datetime.date.today()
            else:
                date = await self.parse_date(date_string)
        except InvalidDateException:
            raise InvalidDateException

        timezone = await self.get_guild_timezone(guild.id)
        combined = timezone.localize(datetime.datetime.combine(date, time_))
        timestamp = combined.timestamp()
        if timestamp < time.time():
            combined.replace(day=combined.day + 1)
        return combined

    async def get_guild_timezone(self, guild_id):
        administration = self.bot.get_cog("Administration")
        servers_settings: ServerSettingsRepository = administration.server_settings
        server_settings = servers_settings.get_by_guild(guild_id)
        if server_settings.timezone is not None:
            return pytz.timezone(server_settings.timezone)
        return pytz.utc

    async def is_over_reminder_limit(self, guild_id, user_id):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return len(self.reminders.get_by_guild_and_user(guild_id, user_id)) > \
            config['automation']['max_reminders_per_player']

    async def is_over_event_limit(self, guild_id):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return len(self.events.get_by_guild(guild_id)) > config['automation']['max_events_per_server']

    async def is_over_action_limit(self, event):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return len(self.event_service.get_actions(event)) > config['automation']['max_actions_per_event']

    @staticmethod
    async def parse_time(time_string):
        split = time_string.split(':')

        if split[-1][-2:] == "am":
            split[-1] = split[-1][:-2]
        elif time_string[-2:] == "pm":
            split[-1] = split[-1][:-2]
            split[0] = int(split[0]) + 12

        try:
            time_ = datetime.time(hour=int(split[0]), minute=int(split[1]))
            return time_
        except ValueError:
            raise InvalidTimeException

    @staticmethod
    async def parse_date(date_string):
        split = date_string.split('/')
        if not split:
            split = date_string.split(':')
        if not split:
            raise InvalidDateException

        try:
            date = datetime.date(day=int(split[0]), month=int(split[1]), year=int(split[2]))
            return date
        except ValueError:
            raise InvalidDateException

    @staticmethod
    async def to_seconds(seconds=0, minutes=0, hours=0, days=0, weeks=0, months=0, years=0) -> int:
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
        years = timedelta.days // 365
        months = (timedelta.days - years * 365) // 30
        weeks = (timedelta.days - years * 365 - months * 30) // 7
        days = (timedelta.days - years * 365 - months * 30 - weeks * 7)

        hours = timedelta.seconds // 3600
        minutes = (timedelta.seconds - hours * 3600) // 60
        seconds = (timedelta.seconds - hours * 3600 - minutes * 60)

        output = ""
        if years:
            if years > 1:
                output += f"{years} years, "
            else:
                output += f"{years} year, "
        if months:
            if months > 1:
                output += f"{months} months, "
            else:
                output += f"{months} month, "
        if weeks:
            if weeks > 1:
                output += f"{weeks} weeks, "
            else:
                output += f"{weeks} week, "
        if days:
            if days > 1:
                output += f"{days} days, "
            else:
                output += f"{days} day, "
        if hours:
            if hours > 1:
                output += f"{hours} hours, "
            else:
                output += f"{hours} hour, "
        if minutes:
            if minutes > 1:
                output += f"{minutes} minutes, "
            else:
                output += f"{minutes} minute, "
        if seconds:
            if seconds > 1:
                output += f"{seconds} seconds, "
            else:
                output += f"{seconds} second, "
        return output[:-2]

    @staticmethod
    async def format_repeat_message(interval: Repeat, multiplier: int):
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
    async def format_repeat_message_alt(interval: Repeat, multiplier: int):
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


async def setup(bot):
    await bot.add_cog(Automation(bot))
