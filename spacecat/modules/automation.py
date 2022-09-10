import asyncio
import sqlite3
from enum import Enum
from itertools import islice

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
    def __init__(self, id_, user_id, guild_id, dispatch_time, last_run_time, repeat_interval,
                 repeat_multiplier, is_paused, name, description, function_name, arguments):
        self.id = id_
        self.user_id = user_id
        self.guild_id = guild_id
        self.dispatch_time = dispatch_time
        self.last_run_time = last_run_time
        self.repeat_interval: Repeat = repeat_interval
        self.repeat_multiplier = repeat_multiplier
        self.is_paused = is_paused
        self.name = name
        self.description = description
        self.function_name = function_name
        self.arguments = arguments

    @classmethod
    def create_new(cls, user_id, guild_id, dispatch_time, repeat_interval,
                   repeat_multiplier, name, function_name, arguments):
        return cls(uuid.uuid4(), user_id, guild_id, dispatch_time, None, repeat_interval,
                   repeat_multiplier, False, name, "", function_name, arguments)


class EventArgsRepository:
    def __init__(self, database):
        self.db = database


class MessageEventArgs:
    def __init__(self, title, message):
        self.title = title
        self.message = message


class VoiceKickEventArgs:
    def __init__(self, channel):
        self.channel = channel


class VoiceMoveEventArgs:
    def __init__(self, current_channel, new_channel):
        self.current_channel = current_channel
        self.new_channel = new_channel


class ChannelPrivateArgs:
    def __init__(self, channel):
        self.channel = channel


class ChannelPublicArgs:
    def __init__(self, id_, event_id, channel):
        self.id = id_
        self.event_id = event_id
        self.channel = channel


class ChannelPublicArgsRepository(EventArgsRepository):
    def __init__(self, database):
        super().__init__(database)
        cursor = self.db.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS event_channelpublic_args '
                       '(event_id, TEXT PRIMARY KEY, channel_id INTEGER)')
        self.db.commit()

    def get_by_event(self, event):
        result = self.db.cursor().execute(
            'SELECT * FROM event_channelpublic_args WHERE event_id=?', (event.id,)).fetch_one()
        self.db.commit()
        return self._result_to_args(result)

    def add(self, event, channel_public_args: ChannelPublicArgs):
        values = (event.id, channel_public_args.channel)
        cursor = self.db.cursor()
        cursor.execute('INSERT INTO event_channelpublic_args VALUES (?, ?)', values)
        self.db.commit()

    def update(self, event, channel_public_args: ChannelPublicArgs):
        values = (event.id, channel_public_args.channel)
        cursor = self.db.cursor()
        cursor.execute('UPDATE event_channelpublic_args SET event_id=?, channel_id=?', values)
        self.db.commit()

    def remove(self, event, channel_public_args: ChannelPublicArgs):
        values = (event.id, channel_public_args.channel)
        cursor = self.db.cursor()
        cursor.execute('DELETE FROM event_channelpublic_args WHERE event_id=?, channel_id=?', values)
        self.db.commit()

    @staticmethod
    def _result_to_args(result):
        return ChannelPublicArgs(result[0], result[1], result[2])


class EventRepository:
    def __init__(self, database):
        self.db = database
        cursor = self.db.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, user_id INTEGER, guild_id INTEGER, '
                       'dispatch_time INTEGER, last_run_time INTEGER, repeat_interval TEXT, repeat_multiplier INTEGER, '
                       'is_paused INTEGER, name TEXT, description TEXT, function_name TEXT, arguments TEXT)')
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
        values = (str(event.id), event.user_id, event.guild_id, event.dispatch_time, event.last_run_time,
                  event.repeat_interval.name, event.repeat_multiplier, int(event.is_paused), event.name,
                  event.description, event.function_name, event.arguments)
        cursor.execute('INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', values)
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
                     bool(result[7]), result[8], result[9], result[10])


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
        description=f"The server has reach its event limit. Delete an event before adding another one.")

    PAST_TIME_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"You cannot set a date and time in the past.")

    NAME_ALREADY_EXISTS_EMBED = discord.Embed(
        colour=constants.EmbedStatus.FAIL.value,
        description=f"An event of that name already exists.")

    def __init__(self, bot):
        self.bot: SpaceCat = bot
        self.database = sqlite3.connect(constants.DATA_DIR + "spacecat.db")
        self.reminders = ReminderRepository(self.database)
        self.events = EventRepository(self.database)
        self.reminder_task = bot.loop.create_task(self.reminder_loop())
        self.event_task = bot.loop.create_task(self.event_loop())
        self.repeating_events: dict[str, RepeatJob] = {}

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
        with open(constants.DATA_DIR + 'config.toml', 'w') as config_file:
            toml.dump(config, config_file)

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
    async def schedule_add_message(self, interaction, title: str, message: str, channel: discord.TextChannel,
                                   time_string: str, date_string: str, repeat: Repeat = Repeat.No,
                                   repeat_multiplier: int = 0):
        if await self.is_over_event_limit(interaction.guild_id):
            await interaction.response.send_message(embed=self.MAX_EVENTS_EMBED)
            return

        if any(event.name == title for event in self.events.get_by_guild(interaction.guild_id)):
            await interaction.response.send_message(embed=self.NAME_ALREADY_EXISTS_EMBED)
            return

        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "message", f"{channel.id} {message}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A message event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_add_group.command(name="voicekick")
    async def schedule_add_voicekick(self, interaction, title: str, voice_channel: discord.VoiceChannel,
                                     time_string: str, date_string: str, repeat: Repeat = Repeat.No,
                                     repeat_multiplier: int = 0):
        if await self.is_over_event_limit(interaction.guild_id):
            await interaction.response.send_message(embed=self.MAX_EVENTS_EMBED)
            return

        if any(event.name == title for event in self.events.get_by_guild(interaction.guild_id)):
            await interaction.response.send_message(embed=self.NAME_ALREADY_EXISTS_EMBED)
            return

        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "voicekick", f"{voice_channel.id}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A voicekick event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_add_group.command(name="voicemove")
    async def schedule_add_voicemove(self, interaction, title: str, current_channel: discord.VoiceChannel,
                                     new_channel: discord.VoiceChannel, time_string: str, date_string: str,
                                     repeat: Repeat = Repeat.No, repeat_multiplier: int = 0):
        if await self.is_over_event_limit(interaction.guild_id):
            await interaction.response.send_message(embed=self.MAX_EVENTS_EMBED)
            return

        if any(event.name == title for event in self.events.get_by_guild(interaction.guild_id)):
            await interaction.response.send_message(embed=self.NAME_ALREADY_EXISTS_EMBED)
            return

        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "voicemove",
                                 f"{current_channel.id} {new_channel.id}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A voicemove event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_add_group.command(name="channelprivate")
    async def schedule_add_channelprivate(self, interaction, title: str, channel: discord.abc.GuildChannel,
                                          time_string: str, date_string: str, repeat: Repeat = Repeat.No,
                                          repeat_multiplier: int = 0):
        if await self.is_over_event_limit(interaction.guild_id):
            await interaction.response.send_message(embed=self.MAX_EVENTS_EMBED)
            return

        if any(event.name == title for event in self.events.get_by_guild(interaction.guild_id)):
            await interaction.response.send_message(embed=self.NAME_ALREADY_EXISTS_EMBED)
            return

        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "channelprivate", f"{channel.id}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A channelprivate event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_add_group.command(name="channelpublic")
    async def schedule_add_channelpublic(self, interaction, title: str, channel: discord.abc.GuildChannel,
                                         time_string: str, date_string: str, repeat: Repeat = Repeat.No,
                                         repeat_multiplier: int = 0):
        if await self.is_over_event_limit(interaction.guild_id):
            await interaction.response.send_message(embed=self.MAX_EVENTS_EMBED)
            return

        if any(event.name == title for event in self.events.get_by_guild(interaction.guild_id)):
            await interaction.response.send_message(embed=self.NAME_ALREADY_EXISTS_EMBED)
            return

        selected_datetime = await self.fetch_future_datetime(interaction.guild, time_string, date_string)
        if selected_datetime.timestamp() < time.time():
            await interaction.response.send_message(embed=self.PAST_TIME_EMBED)
            return

        event = Event.create_new(interaction.user.id, interaction.guild_id, selected_datetime.timestamp(),
                                 repeat, repeat_multiplier, title, "channelpublic",
                                 f"{channel.id}")
        self.events.add(event)
        await self.load_event(event)
        embed = discord.Embed(
            colour=constants.EmbedStatus.INFO.value,
            description=f"A channelpublic event named '{title}' has been set for "
                        f"{selected_datetime.day}/{selected_datetime.month}/{selected_datetime.year} "
                        f"at {selected_datetime.hour}:{selected_datetime.minute}"
                        f"{await self.format_repeat_message(repeat, repeat_multiplier)}")
        await interaction.response.send_message(embed=embed)

    @schedule_group.command(name="remove")
    async def schedule_remove(self, interaction, name: str):
        event = self.events.get_by_name(name)
        if not event:
            await interaction.response.send_message(embed=discord.Embed(
                colour=constants.EmbedStatus.FAIL.value,
                description=f"An event going by the name '{name}' does not exist"))
            return

        self.events.remove(event)
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
