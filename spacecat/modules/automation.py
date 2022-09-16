import asyncio
import sqlite3
from abc import ABC, abstractmethod
from enum import Enum
from itertools import islice
from typing import Generic, TypeVar, get_args

import discord
import toml
from discord import app_commands
from discord.ext import commands, tasks

import datetime
import pytz
import time
import uuid

from spacecat.helpers import constants
from spacecat.modules.administration import ServerSettingsRepository
from spacecat.spacecat import SpaceCat


class Repeat(Enum):
    No = 0
    Hourly = 3600
    Daily = 86400
    Weekly = 604800


class Reminder:
    def __init__(self, id_, user_id, guild_id, channel_id, message_id, creation_time, dispatch_time, message):
        self.id = id_
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
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6],
                                      result[7]))
        return reminders

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM reminders WHERE id=?', (id_,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6], result[7])

    def get_by_guild(self, guild):
        # Get list of all reminders in a guild
        cursor = self.db.cursor()
        values = (guild.id,)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=?', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6],
                                      result[7]))
        return reminders

    def get_by_guild_and_user(self, guild_id, user_id):
        # Get reminder by guild and reminder name
        cursor = self.db.cursor()
        values = (guild_id, user_id)
        cursor.execute('SELECT * FROM reminders WHERE guild_id=? AND user_id=? ORDER BY dispatch_time', values)
        results = cursor.fetchall()

        reminders = []
        for result in results:
            reminders.append(Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6],
                                      result[7]))
        return reminders

    def get_first_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        result = cursor.execute('SELECT * FROM reminders WHERE dispatch_time < ? ORDER BY dispatch_time',
                                (timestamp,)).fetchone()
        return Reminder(result[0], result[1], result[2], result[3], result[4], result[5], result[6], result[7])

    def add(self, reminder):
        cursor = self.db.cursor()
        values = (str(reminder.id), reminder.user_id, reminder.guild_id, reminder.channel_id, reminder.message_id,
                  reminder.creation_time, reminder.dispatch_time, reminder.message)
        cursor.execute('INSERT INTO reminders VALUES (?, ?, ?, ?, ?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.user_id, reminder.guild_id, reminder.channel_id, reminder.message_id,
                  reminder.creation_time, reminder.dispatch_time, reminder.message, str(reminder.id))
        cursor.execute('UPDATE reminders SET user_id=?, guild_id=?, channel_id=?, message_id=?'
                       'creation_time=?, dispatch_time=?, message=? WHERE id=?', values)
        self.db.commit()

    def remove(self, reminder):
        cursor = self.db.cursor()
        values = (reminder.id,)
        cursor.execute('DELETE FROM reminders WHERE id=?', values)
        self.db.commit()


class Event:
    def __init__(self, id_, guild_id, dispatch_time, last_run_time, repeat_interval,
                 repeat_multiplier, is_paused, name, description):
        self.id = id_
        self.guild_id = guild_id
        self.dispatch_time = dispatch_time
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
        cursor.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, user_id INTEGER, guild_id INTEGER, '
                       'dispatch_time INTEGER, last_run_time INTEGER, repeat_interval TEXT, repeat_multiplier INTEGER, '
                       'is_paused INTEGER, name TEXT, description TEXT)')
        self.db.commit()
        self.create_event_argument_tables()

    def create_event_argument_tables(self):
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS event_message_args '
                       '(event_id, TEXT PRIMARY KEY, title TEXT, description TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS event_voicekick_args '
                       '(event_id, TEXT PRIMARY KEY, channel_id INTEGER)')
        cursor.execute('CREATE TABLE IF NOT EXISTS event_voicemove_args '
                       '(event_id, TEXT PRIMARY KEY, current_channel INTEGER, new_channel INTEGER)')
        cursor.execute('CREATE TABLE IF NOT EXISTS event_voicemove_args '
                       '(event_id, TEXT PRIMARY KEY, channel_id INTEGER)')
        self.db.commit()

    def get_all(self):
        """Get list of all reminders"""
        results = self.db.cursor().execute('SELECT * FROM events').fetchall()
        reminders = []
        for result in results:
            event = self._result_to_event(result)
            reminders.append(event)
        return reminders

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM events WHERE id=?', (id_,)).fetchone()
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

    def get_repeating_before_timestamp(self, timestamp):
        cursor = self.db.cursor()
        results = cursor.execute('SELECT * FROM events '
                                 'WHERE dispatch_time < ? AND NOT repeat_interval="No" '
                                 'ORDER BY dispatch_time',
                                 (timestamp,)).fetchall()

        reminders = []
        for result in results:
            reminders.append(self._result_to_event(result))
        return reminders

    def get_first_before_timestamp(self, timestamp):
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
        values = (event.user_id, event.guild_id, event.dispatch_time, event.last_run_time, event.repeat_interval.name,
                  event.repeat_multiplier, int(event.is_paused), event.name, event.description, event.function_name,
                  event.arguments, str(event.id))
        cursor.execute('UPDATE events SET user_id=?, guild_id=?, dispatch_time=?, last_run_time=?, repeat_interval=?, '
                       'repeat_multiplier=?, is_paused=?, name=?, description=?, function_name=?, arguments=? '
                       'WHERE id=?', values)
        self.db.commit()

    def remove(self, event):
        cursor = self.db.cursor()
        values = (event.id,)
        cursor.execute('DELETE FROM events WHERE id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_event(result):
        return Event(result[0], result[1], result[2], result[3], result[4], Repeat[result[5]], result[6],
                     bool(result[7]), result[8])


class Action(ABC):
    def __init__(self, id_):
        self.id = id_

    @abstractmethod
    def get_name(self):
        pass


T_Action = TypeVar("T_Action", bound=Action)


class ActionRepository(ABC, Generic[T_Action]):
    def __init__(self, database):
        self.db = database

    @abstractmethod
    def get_by_id(self, id_):
        pass

    @abstractmethod
    def add(self, action: T_Action):
        pass

    @abstractmethod
    def remove(self, id_: int):
        pass


class MessageAction(Action):
    def __init__(self, id_, text_channel_id, title, message):
        super().__init__(id_)
        self.text_channel_id = text_channel_id
        self.title = title
        self.message = message

    @classmethod
    def create_new(cls, text_channel_id, title, message):
        return cls(uuid.uuid4(), text_channel_id, title, message)

    def get_name(self):
        return "message"


class MessageActionRepository(ActionRepository[MessageAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_message '
                       '(id TEXT PRIMARY KEY, text_channel INTEGER, title TEXT, message TEXT)')
        self.db.commit()

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM action_message WHERE id=?', (id_,)).fetch_one()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: MessageAction):
        values = (action.id, action.text_channel_id, action.title, action.message)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_message VALUES (?, ?, ?, ?)', values)
        self.db.commit()

    def remove(self, action: MessageAction):
        values = (action.id,)
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_message WHERE id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return MessageAction(result[0], result[1], result[2], result[3])


class VoiceKickAction(Action):
    def __init__(self, id_, voice_channel_id):
        super().__init__(id_)
        self.channel = voice_channel_id

    @classmethod
    def create_new(cls, voice_channel_id):
        return cls(uuid.uuid4(), voice_channel_id)

    def get_name(self):
        return "voice_kick"


class VoiceKickActionRepository(ActionRepository[VoiceKickAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_voice_kick (id TEXT PRIMARY KEY, voice_channel_id TEXT)')
        self.db.commit()

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM action_voice_kick WHERE id=?', (id_,)).fetch_one()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: VoiceKickAction):
        values = (action.id, action.channel)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_voice_kick VALUES (?, ?)', values)
        self.db.commit()

    def remove(self, action: VoiceKickAction):
        values = (action.id,)
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_voice_kick WHERE id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return VoiceKickAction(result[0], result[1])


class VoiceMoveAction(Action):
    def __init__(self, id_, current_voice_channel_id, new_voice_channel_id):
        super().__init__(id_)
        self.current_voice_channel_id = current_voice_channel_id
        self.new_voice_channel_id = new_voice_channel_id

    @classmethod
    def create_new(cls, current_voice_channel_id, new_voice_channel_id):
        return cls(uuid.uuid4(), current_voice_channel_id, new_voice_channel_id)

    def get_name(self):
        return "voice_move"


class VoiceMoveActionRepository(ActionRepository[VoiceMoveAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_voice_move '
                       '(id TEXT PRIMARY KEY, current_voice_channel_id INTEGER, new_voice_channel_id INTEGER)')
        self.db.commit()

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM action_voice_move WHERE id=?', (id_,)).fetch_one()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: VoiceMoveAction):
        values = (action.id, action.current_voice_channel_id, action.new_voice_channel_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_voice_move VALUES (?, ?, ?)', values)
        self.db.commit()

    def remove(self, action: VoiceMoveAction):
        values = (action.id,)
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_voice_move WHERE id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return VoiceMoveAction(result[0], result[1], result[2])


class ChannelPrivateAction(Action):
    def __init__(self, id_, channel_id):
        super().__init__(id_)
        self.channel_id = channel_id

    @classmethod
    def create_new(cls, channel_id):
        return cls(uuid.uuid4(), channel_id)

    def get_name(self):
        return "channel_private"


class ChannelPrivateActionRepository(ActionRepository[ChannelPrivateAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS action_channel_private (id TEXT PRIMARY KEY, channel_id INTEGER)')
        self.db.commit()

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM action_channel_private WHERE id=?', (id_,)).fetch_one()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: ChannelPrivateAction):
        values = (action.id, action.channel_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO action_channel_private VALUES (?, ?)', values)
        self.db.commit()

    def remove(self, action: ChannelPrivateAction):
        values = (action.id,)
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM action_channel_private WHERE id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return VoiceMoveAction(result[0], result[1], result[2])


class ChannelPublicAction(Action):
    def __init__(self, id_, channel_id):
        super().__init__(id_)
        self.channel_id = channel_id

    @classmethod
    def create_new(cls, channel_id):
        return cls(uuid.uuid4(), channel_id)

    def get_name(self):
        return "channel_public"


class ChannelPublicActionRepository(ActionRepository[ChannelPublicAction]):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS event_channelpublic_args '
                       '(id TEXT PRIMARY KEY, channel_id INTEGER)')
        self.db.commit()

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM event_channelpublic_args WHERE id=?', (id_,)).fetch_one()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, action: ChannelPublicAction):
        values = (action.id, action.channel_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO event_channelpublic_args VALUES (?, ?)', values)
        self.db.commit()

    def remove(self, action: ChannelPublicAction):
        values = (action.id,)
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM event_channelpublic_args WHERE id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return ChannelPublicAction(result[0], result[1])


class EventAction:
    def __init__(self, id_, event_id, action_type, action_id, previous_id):
        self.id: uuid = id_
        self.event_id: int = event_id
        self.action_type: str = action_type
        self.action_id: int = action_id
        self.previous_id: uuid = previous_id


class EventActionRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS event_actions '
                       '(id TEXT PRIMARY KEY, event_id INTEGER, action_type TEXT, action_id INTEGER, previous_id TEXT)')

    def get_by_id(self, id_):
        result = self.db.cursor().execute('SELECT * FROM event_actions WHERE id=?', (id_,)).fetchone()
        return self._result_to_event_action(result)

    def get_by_event(self, event_id):
        results = self.db.cursor().execute('SELECT * FROM event_actions WHERE event_id=?', (event_id,)).fetchall()
        event_actions = []
        for result in results:
            event_actions.append(self._result_to_event_action(result))
        return event_actions

    def get_by_action(self, action_id):
        result = self.db.cursor().execute('SELECT * FROM event_actions WHERE action_id=?', (action_id,)).fetchone()
        return self._result_to_event_action(result)

    def get_by_action_in_event(self, action_id, event_id):
        result = self.db.cursor().execute('SELECT * FROM event_actions WHERE action_id=? AND event_id=?',
                                          (action_id,)).fetchone()
        return self._result_to_event_action(result)

    def get_by_previous(self, action_id):
        result = self.db.cursor().execute('SELECT * FROM event_actions WHERE previous_id=?', (action_id,)).fetchone()
        return self._result_to_event_action(result)

    def add(self, event_id, action, previous_id=None):
        values = (event_id, action.get_name(), action.id, previous_id)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO event_actions VALUES (?, ?, ?, ?)', values)
        self.db.commit()

    def update(self, event_action: EventAction):
        values = (event_action.id, event_action.event_id, event_action.action_type, event_action.action_id,
                  event_action.previous_id)
        self.db.cursor().execute('UPDATE event_actions SET event_id=?, action_type=?, action_id=?, previous_id=? '
                                 'WHERE id=?', values)
        self.db.commit()

    def remove(self, id_):
        self.db.cursor().execute('DELETE FROM event_actions WHERE id=?', (id_,))
        self.db.commit()

    @staticmethod
    def _result_to_event_action(result):
        return EventAction(result[0], result[1], result[2], result[3], result[4])


class EventService:
    def __init__(self, event_actions, events):
        self.event_actions: EventActionRepository = event_actions
        self.events: EventRepository = events
        self.actions_collection: dict[str, ActionRepository] = {}

    def add_action_repository(self, action_repository: ActionRepository):
        self.actions_collection[get_args(action_repository)[0].get_name()] = action_repository

    def remove_event(self, event: Event):
        found_event_actions = self.event_actions.get_by_event(event.id)
        for event_action in found_event_actions:
            self.actions_collection.get(event_action.action_type).remove(event_action.action_id)
            self.event_actions.remove(event.id, event_action.action_id)
        self.events.remove(event.id)

    def get_event_actions(self, event):
        event_action_links = {}
        event_actions = self.event_actions.get_by_event(event.id)

        for event_action in event_actions:
            actions = self.actions_collection.get(event_action.action_type)
            event_action_links[event_action.previous_id](actions.get_by_id(event_action.action_id))

        # Sort actions using linked previous_id
        sorted_actions = []
        next_action = event_action_links.get(None)
        while next_action is not None:
            sorted_actions.append(next_action)
            next_action = event_action_links.get(next_action.id)

        return sorted_actions

    def add_action(self, event: Event, action: Action):
        actions = self.actions_collection.get(action.get_name())
        actions.add(action)

        actions = self.get_event_actions(event)
        if actions:
            self.event_actions.add(event.id, action, actions[-1])
            return
        self.event_actions.add(event.id, action)

    def remove_action(self, event: Event, action: Action):
        actions = self.actions_collection.get(action.get_name())
        actions.remove(action.id)
        self.event_actions.remove(event.id, action.id)


class RepeatJob:
    def __init__(self, bot: commands.Bot, event: Event, timezone: pytz.tzinfo):
        self.bot = bot
        self.event = event
        self.timezone = timezone
        self.interval = self.calculate_interval()
        self.next_run_time = self.calculate_next_run()
        self.job_task = None

    def run_task(self):
        self.job_task = asyncio.create_task(self.job_loop())

    def calculate_next_run(self):
        next_run_time = self.event.dispatch_time
        if self.event.last_run_time:
            next_run_time = self.event.last_run_time
        while next_run_time <= datetime.datetime.now(tz=self.timezone).timestamp() + 1:
            next_run_time += self.interval
        return next_run_time

    def calculate_interval(self):
        return self.event.repeat_interval.value * self.event.repeat_multiplier

    async def job_loop(self):
        while True:
            if self.next_run_time >= time.time():
                await asyncio.sleep(self.next_run_time - time.time())
            await self.dispatch_event()

    async def dispatch_event(self):
        self.bot.dispatch(f"{self.event.function_name}_event", self.event)
        self.event.last_run_time = self.next_run_time
        self.next_run_time = self.calculate_next_run()
        self.job_task.cancel()
        self.job_task = asyncio.create_task(self.job_loop())


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
        description=f"You cannot set a date and time in the past."
    )

    NAME_ALREADY_EXISTS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"An event of that name already exists."
    )

    EVENT_DOES_NOT_EXIST_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"An event of that name does not exist."
    )

    def __init__(self, bot):
        self.bot: SpaceCat = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.reminders = ReminderRepository(self.database)
        self.events = EventRepository(self.database)
        self.event_actions = EventActionRepository(self.database)
        self.reminder_task = bot.loop.create_task(self.reminder_loop())
        self.event_task = bot.loop.create_task(self.event_loop())
        self.repeating_events: dict[str, RepeatJob] = {}
        self.event_service = await self.init_event_service()

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

    async def init_event_service(self):
        event_service = EventService(self.event_actions, self.events)

        action_repositories = [
            MessageActionRepository(self.database),
            VoiceKickActionRepository(self.database),
            VoiceMoveActionRepository(self.database),
            ChannelPrivateActionRepository(self.database),
            ChannelPublicActionRepository(self.database)
        ]

        for action_repository in action_repositories:
            event_service.add_action_repository(action_repository)
        return event_service

    async def reminder_loop(self):
        try:
            while not self.bot.is_closed():
                reminder = self.reminders.get_first_before_timestamp(time.time() + 90000)  # Get timers within 25 hours
                if reminder.dispatch_time >= time.time():
                    sleep_duration = (reminder.dispatch_time - time.time())
                    await asyncio.sleep(sleep_duration)

                await self.dispatch_reminder(reminder)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed):
            self.reminder_task.cancel()
            self.reminder_task = self.bot.loop.create_task(self.reminder_loop())

    async def dispatch_reminder(self, reminder: Reminder):
        self.reminders.remove(reminder)
        self.bot.dispatch("reminder", reminder)

    async def event_loop(self):
        try:
            while not self.bot.is_closed():
                event = self.events.get_first_before_timestamp(time.time() + 86400)  # Get timers within 24 hours
                if event.dispatch_time >= time.time():
                    sleep_duration = (event.dispatch_time - time.time())
                    await asyncio.sleep(sleep_duration)

                await self.dispatch_event(event)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed):
            self.event_task.cancel()
            self.event_task = self.bot.loop.create_task(self.event_loop())

    async def dispatch_event(self, event: Event):
        self.events.remove(event)
        self.bot.dispatch(f"{event.function_name}_event", event)

    @tasks.loop(hours=24)
    async def load_upcoming_events(self):
        events = self.events.get_repeating_before_timestamp(time.time() + 90000)
        for event in events:
            if event.id in self.repeating_events:
                continue
            repeat_job = RepeatJob(self.bot, event, await self.get_guild_timezone(event.guild_id))
            repeat_job.run_task()
            self.repeating_events[event.id] = repeat_job

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
    async def on_message_event(self, event):
        self.events.update(event)
        channel = await self.bot.fetch_channel(int(event.arguments.split(' ')[0]))
        await channel.send(embed=discord.Embed(
            colour=constants.EmbedStatus.SPECIAL.value,
            title=f"{event.name}",
            description=f"{event.arguments.split(' ', 1)[1]}"
        ))

    @commands.Cog.listener()
    async def on_voicekick_event(self, event):
        self.events.update(event)
        voice_channel = self.bot.get_channel(int(event.arguments.split(' ')[0]))
        for member in voice_channel.members:
            await member.move_to(None)

    @commands.Cog.listener()
    async def on_voicemove_event(self, event):
        self.events.update(event)
        current_channel = self.bot.get_channel(int(event.arguments.split(' ')[0]))
        new_channel = self.bot.get_channel(int(event.arguments.split(' ')[1]))
        for member in current_channel.members:
            await member.move_to(new_channel)

    @commands.Cog.listener()
    async def on_channelprivate_event(self, event):
        self.events.update(event)
        guild = self.bot.get_guild(event.guild_id)
        channel: discord.abc.GuildChannel = await self.bot.fetch_channel(event.arguments)
        await channel.set_permissions(guild.default_role, connect=False, view_channel=False)

    @commands.Cog.listener()
    async def on_channelpublic_event(self, event):
        self.events.update(event)
        guild = self.bot.get_guild(event.guild_id)
        channel: discord.abc.GuildChannel = await self.bot.fetch_channel(event.arguments)
        await channel.set_permissions(guild.default_role, connect=None, view_channel=None)

    @app_commands.command()
    async def remindme(self, interaction, message: str, seconds: int = 0, minutes: int = 0, hours: int = 0,
                       days: int = 0, weeks: int = 0, months: int = 0, years: int = 0):
        if self.is_over_reminder_limit(interaction.guild_id, interaction.user.id):
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
        self.reminder_task.cancel()
        self.reminder_task = self.bot.loop.create_task(self.reminder_loop())

    reminder_group = app_commands.Group(
        name="reminder", description="Configure existing reminders.")
    schedule_group = app_commands.Group(
        name="schedule", description="Allows you to run an function at a scheduled time.")
    schedule_add_group = app_commands.Group(
        parent=schedule_group, name="add", description="Add a new scheudled event.")

    @reminder_group.command(name="list")
    async def reminder_list(self, interaction: discord.Interaction):
        reminders = self.reminders.get_by_guild_and_user(interaction.guild, interaction.user.id)
        if not reminders:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You have no set reminders."))
            return

        # Reminders into pretty listings
        reminder_listings = []
        for index, reminder in enumerate(islice(reminders, 0, 10)):
            listing = f"{index + 1}. {reminder.message[0:30]} | <t:{int(reminder.dispatch_time)}:R>"
            reminder_listings.append(listing)

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Your Reminders")
        reminder_output = '\n'.join(reminder_listings)
        embed.add_field(
            name=f"{len(reminders)} available",
            value=reminder_output, inline=False)
        await interaction.response.send_message(embed=embed)

    @reminder_group.command(name="remove")
    async def reminder_remove(self, interaction: discord.Interaction, index: int):
        reminders = self.reminders.get_by_guild_and_user(interaction.guild, interaction.user.id)
        if not reminders:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="You have no set reminders."))
            return

        if len(reminders) < index:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="A reminder by that index doesn't exist."))
            return

        self.reminders.remove(reminders[index - 1])

        # If reminder isn't first in list, then it's probably not currently queued up. No need to refresh task loop.
        if index > 1:
            self.reminder_task.cancel()
            self.reminder_task = self.bot.loop.create_task(self.reminder_loop())

        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"Reminder at index {index} has been removed."))
        return

    @schedule_group.command(name="list")
    async def schedule_list(self, interaction):
        events = self.events.get_by_guild(interaction.guild_id)
        if not events:
            embed = discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description="There are no scheduled events")
            await interaction.response.send_message(embed=embed)
            return

        # Format playlist songs into pretty listings
        event_listings = []
        for index, event in enumerate(islice(events, 0, 10)):
            listing = f"{index + 1}. {event.name}"
            if event.repeat_interval != Repeat.No:
                listing += f" | `Repeating {event.repeat_interval.name}`"
            event_listings.append(listing)

        # Output results to chat
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            title=f"{constants.EmbedIcon.MUSIC} Events")
        playlist_output = '\n'.join(event_listings)
        embed.add_field(
            name=f"{len(events)} available",
            value=playlist_output, inline=False)
        await interaction.response.send_message(embed=embed)

    @schedule_group.command(name="create")
    async def schedule_create(self, interaction: discord.Interaction, name: str, time_string: str, date_string: str,
                              repeat: Repeat = Repeat.No, repeat_multiplier: int = 0):
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

        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event = Event.create_new(interaction.guild_id, selected_datetime.timestamp(), repeat, repeat_multiplier, name)
        self.events.add(event)

        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"An event by the name of '{name}' has been created, set to trigger on "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}. Use `/schedule add` to"
                        f"assign actions."))
        return

    @schedule_group.command(name="destroy")
    async def schedule_destroy(self, interaction: discord.Interaction, event_name: str):
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
            description=f"Event {event_name} has been deleted."))
        return

    @schedule_group.command(name="view")
    async def schedule_view(self, interaction, name: str):
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

        time_fields = []
        if event.last_run_time:
            time_fields.append(
                f"**Initial Time:** {datetime.datetime.fromtimestamp(event.dispatch_time).strftime('%X %x')}")
        else:
            time_fields.append(
                f"**Dispatch Time: {datetime.datetime.fromtimestamp(event.dispatch_time).strftime('%X %x')}")

        if event.is_paused:
            time_fields.append(
                f"**Repeating:** "
                f"{await self.format_repeat_message_alt(event.repeat_interval, event.repeat_multiplier)} (Paused)")
        else:
            time_fields.append(
                f"**Repeating:** "
                f"{await self.format_repeat_message_alt(event.repeat_interval, event.repeat_multiplier)}")

        if event.last_run_time:
            time_fields.append(
                f"**Last Run:** {datetime.datetime.fromtimestamp(event.last_run_time).strftime('%X %x')}")

        if event.repeat_interval:
            repeat_job = RepeatJob(self.bot, event, await self.get_guild_timezone(interaction.guild.id))
            time_fields.append(
                f"**Next Run:** {datetime.datetime.fromtimestamp(repeat_job.calculate_next_run()).strftime('%X %x')}")

        embed.add_field(name="Execution Time", value='\n'.join(time_fields))

        function_fields = [f"**Function:** {event.function_name}", f"**Arguments:** {event.arguments}"]
        embed.add_field(name="To Run", value='\n'.join(function_fields))
        await interaction.response.send_message(embed=embed)

    @schedule_add_group.command(name="message")
    async def schedule_add_message(self, interaction: discord.Interaction, event_name: str,
                                   channel: discord.TextChannel, title: str, message: str):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(interaction.guild_id, event.id):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = MessageAction.create_new(channel, title, message)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Message action has been added to event '{event_name}'"))

    @schedule_add_group.command(name="voicekick")
    async def schedule_add_voicekick(self, interaction, event_name: str, voice_channel: discord.VoiceChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(interaction.guild_id, event.id):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = VoiceKickAction.create_new(voice_channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Voice Kick action has been added to event '{event_name}'"))

    @schedule_add_group.command(name="voicemove")
    async def schedule_add_voicemove(self, interaction, event_name: str, current_channel: discord.VoiceChannel,
                                     new_channel: discord.VoiceChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(interaction.guild_id, event.id):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = VoiceMoveAction.create_new(current_channel.id, new_channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Voice Move action has been added to event '{event_name}'"))

    @schedule_add_group.command(name="channelprivate")
    async def schedule_add_channelprivate(self, interaction, event_name: str, channel: discord.abc.GuildChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(interaction.guild_id, event.id):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = ChannelPrivateAction.create_new(channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Channel Private action has been added to event '{event_name}'"))

    @schedule_add_group.command(name="channelpublic")
    async def schedule_add_channelpublic(self, interaction, event_name: str, channel: discord.abc.GuildChannel):
        event = self.events.get_by_name_in_guild(event_name, interaction.guild_id)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        if await self.is_over_action_limit(interaction.guild_id, event.id):
            await interaction.response.send_message(embed=self.MAX_ACTIONS_EMBED)
            return

        action = ChannelPublicAction.create_new(channel.id)
        self.event_service.add_action(event, action)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"Channel Public action has been added to event '{event_name}'"))

    @schedule_group.command(name="remove")
    async def schedule_remove(self, interaction, name: str, index: int):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=self.EVENT_DOES_NOT_EXIST_EMBED)
            return

        self.event_service.remove_action(event, )
        await self.unload_event(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Scheduled event '{name}' has been removed."))

    @schedule_group.command(name="pause")
    async def schedule_pause(self, interaction, name: str):
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
        await self.unload_event(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"Event '{name}' has been paused and will not run on its next scheduled run time."))
        return

    @schedule_group.command(name="resume")
    async def schedule_resume(self, interaction, name: str):
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
        await self.load_event(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.FAIL.value,
            description=f"Event {name} has now been resumed and will run at the scheduled time."))
        return

    @schedule_group.command(name="rename")
    async def schedule_rename(self, interaction, name: str, new_name: str):
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

    @schedule_group.command(name="description")
    async def schedule_description(self, interaction, name: str, description: str):
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

    @schedule_group.command(name="reschedule")
    async def schedule_reschedule(self, interaction, name: str, date: str, time_: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_, date)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"You cannot set a date and time in the past."))
            return

        event.dispatch_time = selected_datetime
        self.events.update(event)
        if self.repeating_events.get(event.id):
            await self.unload_event(event)
            await self.load_event(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Dispatch time has been set for event {name}."))
        return

    @schedule_group.command(name="interval")
    async def schedule_interval(self, interaction, name: str, interval: Repeat, multiplier: int = 1):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist."))
            return

        event.repeat_interval = interval
        event.repeat_multiplier = multiplier
        self.events.update(event)

        if self.repeating_events.get(event.id):
            await self.unload_event(event)
            await self.load_event(event)
        await interaction.response.send_message(embed=discord.Embed(
            colour=constants.EmbedStatus.YES.value,
            description=f"Interval has been changed for event {name}."))
        return

    async def load_event(self, event):
        if event.repeat_interval == Repeat.No:
            self.event_task.cancel()
            self.event_task = self.bot.loop.create_task(self.event_loop())
            return
        repeat_job = RepeatJob(self.bot, event, await self.get_guild_timezone(event.guild_id))
        repeat_job.run_task()
        self.repeating_events[event.id] = repeat_job

    async def unload_event(self, event):
        if event.repeat_interval == Repeat.No:
            self.event_task.cancel()
            self.event_task = self.bot.loop.create_task(self.event_loop())
            return

        repeat_job = self.repeating_events[event.id]
        if repeat_job:
            repeat_job.job_task.cancel()
            self.repeating_events.pop(event.id)

    async def fetch_future_datetime(self, guild: discord.Guild, time_string: str, date_string: str = None):
        time_ = await self.parse_time(time_string)
        timezone = await self.get_guild_timezone(guild.id)
        if date_string is None:
            date = datetime.date.today()
        else:
            date = await self.parse_date(date_string)

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

    async def is_over_action_limit(self, guild_id, event_id):
        config = toml.load(constants.DATA_DIR + 'config.toml')
        return len(self.events.get_by_guild(guild_id)) > config['automation']['max_actions_per_event']

    @staticmethod
    async def parse_time(time_string):
        split = time_string.split(':')
        return datetime.time(hour=int(split[0]), minute=int(split[1]))

    @staticmethod
    async def parse_date(date_string):
        split = date_string.split('/')
        if not split:
            split = date_string.split(':')
        if not split:
            raise
        return datetime.date(day=int(split[0]), month=int(split[1]), year=int(split[2]))

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
